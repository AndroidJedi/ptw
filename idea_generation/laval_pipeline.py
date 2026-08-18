"""Restartable Idea Laval stage executor built on persisted stage artifacts."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import re
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from commander.ids import new_uuid7

from .laval_context import ContextCompiler
from .laval_domain import (
    LavalConfig,
    OPERATORS,
    QUERY_FAMILIES,
    STAGES,
    canonical_domain,
    canonical_url,
    clamp,
    competitor_score,
    deduplicate_queries,
    idea_score,
    input_hash,
    json_safe,
    normalize_words,
    opportunity_score,
    stage_index,
    trend_score,
)
from .laval_providers import ProviderBundle
from .laval_repository import LavalRepository


class RunPaused(RuntimeError):
    pass


class LavalPipeline:
    def __init__(self, repository: LavalRepository, providers: ProviderBundle) -> None:
        self.repository = repository
        self.store = repository.store
        self.providers = providers

    def run(
        self,
        run_id: str,
        *,
        through_stage: str | None = None,
        start_stage: str | None = None,
        force: bool = False,
        country: str | None = None,
    ) -> dict[str, Any]:
        run = self.repository.run(run_id)
        config = LavalConfig.from_mapping(run["config"])
        through = (through_stage or run.get("through_stage") or "").upper() or None
        if through:
            stage_index(through)
        start = stage_index(start_stage) if start_stage else 1
        functions: dict[str, Callable[[str, LavalConfig, str | None], tuple[dict[str, Any], dict[str, Any], bool]]] = {
            "OWNER_DNA": self._owner_dna,
            "QUERY_PLAN": self._query_plan,
            "SERP_DISCOVERY": self._serp_discovery,
            "COMPETITOR_SELECTION": self._competitor_selection,
            "COMPETITOR_EVIDENCE": self._competitor_evidence,
            "COMPETITOR_DOSSIERS": self._competitor_dossiers,
            "OPPORTUNITY_MATRIX": self._opportunity_matrix,
            "TREND_QUERY_PLAN": self._trend_query_plan,
            "GOOGLE_TRENDS_RESEARCH": self._trends_research,
            "TREND_GATE": self._trend_gate,
            "SYNTHESIS_PACKET": self._synthesis_packet,
            "IDEA_EXPANSION": self._idea_expansion,
            "IDEA_CLUSTERING": self._idea_clustering,
            "IDEA_EVALUATION": self._idea_evaluation,
            "FINAL_SHORTLIST": self._final_shortlist,
        }
        for ordinal, stage in enumerate(STAGES[1:], 1):
            if ordinal < start:
                continue
            self._ensure_active(run_id)
            previous = self.repository.stage(run_id, STAGES[ordinal - 1]).get("artifact")
            overrides = self.store.fetchall(
                "SELECT override_type,target_id,action,reason,payload,created_at FROM laval_overrides WHERE run_id=%s ORDER BY created_at",
                (run_id,),
            )
            digest = input_hash(stage, config.to_dict(), previous, overrides, country if stage == "SERP_DISCOVERY" else None)
            current = self.repository.stage(run_id, stage)
            reusable = current["status"] in {"completed", "partial"} and current.get("input_hash") == digest
            if not reusable or force:
                model = str(getattr(self.providers.llm, "model_name", ""))
                provider = self._provider_for_stage(stage)
                self.repository.start_stage(run_id, stage, digest, provider=provider, model=model)
                try:
                    artifact, metrics, partial = functions[stage](run_id, config, country)
                    self.repository.complete_stage(run_id, stage, artifact, metrics=metrics, partial=partial)
                except RunPaused:
                    self.store.execute(
                        "UPDATE laval_stage_runs SET status='paused',updated_at=NOW() WHERE run_id=%s AND stage=%s RETURNING 1",
                        (run_id, stage),
                    )
                    return self.repository.status(run_id)
                except Exception as error:
                    self.repository.fail_stage(run_id, stage, error)
                    raise
            finished = self.repository.stage(run_id, stage)
            run = self.repository.run(run_id)
            if stage == "OPPORTUNITY_MATRIX" and run.get("evidence_mode") == "live_search_pending_trends":
                self.repository.await_provider(run_id, "awaiting_trends_provider")
                return self.repository.status(run_id)
            if self.repository.approval_required(run_id, stage, str(finished["input_hash"])):
                self.repository.pause(run_id)
                return self.repository.status(run_id)
            if through == stage:
                self.repository.pause(run_id)
                return self.repository.status(run_id)
        self.repository.finish_run(run_id)
        return self.repository.status(run_id)

    def _provider_for_stage(self, stage: str) -> str:
        if stage in {"SERP_DISCOVERY", "COMPETITOR_EVIDENCE"}:
            return self.providers.search.name
        if stage == "GOOGLE_TRENDS_RESEARCH":
            return self.providers.trends.name
        return str(getattr(self.providers.llm, "model_name", "deterministic+llm"))

    def _ensure_active(self, run_id: str) -> None:
        if self.repository.run(run_id)["status"] in {"paused", "cancelled"}:
            raise RunPaused("Laval run is paused")

    def _queued_search_batch(
        self, run_id: str, stage: str, requests: Sequence[Mapping[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        provider = self.providers.search
        if not all(hasattr(provider, name) for name in ("estimate_cost", "submit_many", "fetch_result")):
            return {}
        tasks: dict[str, dict[str, Any]] = {}
        for request in requests:
            key = str(request["key"])
            task = self.repository.provider_task(run_id, stage, key)
            if not task:
                task = self.repository.reserve_provider_task(
                    run_id, stage, key, provider.name, request,
                    float(provider.estimate_cost(int(request["depth"]))),  # type: ignore[attr-defined]
                )
            tasks[key] = task

        to_submit = [dict(task["request"]) for task in tasks.values() if not task.get("remote_task_id") and task["status"] == "reserved"]
        if to_submit:
            submitted = provider.submit_many(to_submit)  # type: ignore[attr-defined]
            submission_errors = []
            for item in submitted:
                task = tasks[str(item["key"])]
                if item.get("remote_task_id"):
                    self.repository.submit_provider_task(str(task["id"]), str(item["remote_task_id"]), float(item.get("cost") or 0))
                    tasks[str(item["key"])] = self.repository.provider_task(run_id, stage, str(item["key"])) or task
                else:
                    message = str(item.get("error") or "unknown error")
                    self.repository.fail_provider_task(str(task["id"]), message)
                    submission_errors.append(f"{item['key']}: {message}")
            if submission_errors:
                raise RuntimeError(f"DataForSEO task submission failed: {'; '.join(submission_errors)}")

        results: dict[str, list[dict[str, Any]]] = {}
        pending: dict[str, dict[str, Any]] = {}
        for key, task in tasks.items():
            if task["status"] == "completed" and isinstance(task.get("response"), Mapping):
                results[key] = list(task["response"].get("results") or [])
                self.repository.record_provider_cost_once(str(task["id"]), str(task["request"].get("operation") or "localized_serp"))
            elif task.get("remote_task_id"):
                pending[key] = task
        deadline = time.monotonic() + float(getattr(provider, "poll_timeout", 3600))
        while pending and time.monotonic() < deadline:
            for key, task in list(pending.items()):
                rows = provider.fetch_result(str(task["remote_task_id"]))  # type: ignore[attr-defined]
                if rows is None:
                    continue
                response = {"results": rows}
                self.repository.complete_provider_task(str(task["id"]), response)
                self.repository.record_provider_cost_once(str(task["id"]), str(task["request"].get("operation") or "localized_serp"))
                results[key] = rows
                pending.pop(key)
            if pending:
                time.sleep(float(getattr(provider, "poll_interval", 5)))
        if pending:
            raise TimeoutError(
                f"DataForSEO is still processing {len(pending)} queued task(s); tap Retry later. "
                "Existing task IDs are preserved and will not be reposted or billed again"
            )
        return results

    @staticmethod
    def _retry(operation: Callable[[], Any], before_retry: Callable[[], None] | None = None) -> Any:
        first_error: Exception | None = None
        for attempt in (1, 2):
            try:
                return operation()
            except Exception as error:
                if attempt == 2:
                    raise error from first_error
                first_error = error
                if before_retry:
                    before_retry()
        raise RuntimeError("unreachable provider retry state")

    def _llm(self, run_id: str, stage: str, mode: str, prompt: str, payload: dict[str, Any], required: str) -> dict[str, Any] | None:
        estimated_input = max(1, len(self.store.json({"prompt": prompt, "payload": payload})) // 4)
        try:
            result = self.providers.llm.generate_structured(
                mode,
                prompt,
                payload,
                {"type": "object", "required": [required]},
            )
            self.repository.record_cost(
                run_id, stage, str(getattr(self.providers.llm, "model_name", "llm")), mode,
                input_tokens=estimated_input,
                output_tokens=max(1, len(self.store.json(result)) // 4),
            )
            return result if isinstance(result.get(required), (dict, list)) else None
        except Exception as error:
            self.repository.record_cost(
                run_id,
                stage,
                str(getattr(self.providers.llm, "model_name", "llm")),
                mode,
                input_tokens=estimated_input,
                metadata={"fallback": True, "error": type(error).__name__},
            )
            return None

    def _owner_dna(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        owner = self.repository.owner(run_id)
        compiler = ContextCompiler(config)
        result = self._llm(
            run_id,
            "OWNER_DNA",
            "laval_owner_dna",
            "Extract Owner DNA from the English source. Preserve must-preserve constraints and explicitly list assumptions and unknowns. Return JSON only.",
            compiler.build_owner_dna_context(owner["raw_text"]),
            "owner_dna",
        )
        dna = result.get("owner_dna") if result else None
        required = {"problem", "target_user", "core_mechanism", "core_emotion", "why_now", "must_preserve", "assumptions", "unknowns"}
        if not isinstance(dna, Mapping) or not required.issubset(dna):
            raw = owner["raw_text"].strip()
            first = next((line.strip("# -") for line in raw.splitlines() if line.strip()), "Owner idea")
            dna = {
                "owner_idea_id": owner["id"],
                "raw_text": raw,
                "problem": raw[:4000],
                "target_user": "The users explicitly or implicitly described by the owner",
                "core_mechanism": first[:500],
                "core_emotion": "The motivation or tension expressed by the owner",
                "why_now": "Must be validated with current market and trend evidence",
                "must_preserve": [first[:500]],
                "assumptions": ["The described problem is frequent and costly enough to motivate adoption"],
                "unknowns": ["Segment size", "willingness to pay", "repeat usage", "distribution efficiency"],
            }
        dna = {**json_safe(dna), "owner_idea_id": owner["id"], "raw_text": owner["raw_text"]}
        self.store.execute(
            "UPDATE laval_owner_ideas SET structured_dna=%s::jsonb WHERE id=%s RETURNING 1",
            (self.store.json(dna), owner["id"]),
        )
        return {"owner_dna": dna}, {"must_preserve": len(dna.get("must_preserve") or [])}, False

    @staticmethod
    def _query_seed(dna: Mapping[str, Any]) -> str:
        mechanism = str(dna.get("core_mechanism") or dna.get("problem") or "new product idea")
        words = normalize_words(mechanism)
        return " ".join(words[:7]) or "new product idea"

    @staticmethod
    def _local_query(query: str, language: str, family: str) -> str:
        templates = {
            "de": {"category": "beste {q} Software", "problem": "wie {q} lösen", "alternative": "Alternativen für {q}", "behavioral": "{q} Verhalten Plattform"},
            "no": {"category": "beste {q} app", "problem": "hvordan løse {q}", "alternative": "alternativer til {q}", "behavioral": "{q} utfordring plattform"},
            "da": {"category": "bedste {q} app", "problem": "hvordan løser man {q}", "alternative": "alternativer til {q}", "behavioral": "{q} udfordring platform"},
        }
        return templates.get(language, {}).get(family, "{q}").format(q=query)

    def _query_plan(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        dna = self.repository.stage(run_id, "OWNER_DNA")["artifact"]["owner_dna"]
        seed = self._query_seed(dna)
        fallback_queries = {
            "category": [f"{seed} software", f"best {seed} app", f"{seed} platform"],
            "problem": [f"how to solve {seed}", f"why {seed} fails", f"tools for {seed}"],
            "alternative": [f"best alternatives for {seed}", f"apps like {seed}", f"{seed} competitor"],
            "behavioral": [f"{seed} behavior", f"{seed} challenge", f"share {seed} progress"],
        }
        languages = sorted({str(item["language"]) for item in config.countries} | {
            str(item["secondary_language"]) for item in config.countries if item.get("secondary_language")
        })
        generated = self._llm(
            run_id,
            "QUERY_PLAN",
            "laval_query_plan",
            "Create compact product-discovery search intents for the four supplied families. Return query_intents with family, base_query in English, and translations keyed by requested language. A translation must retain the exact semantic intent and must not introduce a new category.",
            {
                "owner_dna": dna,
                "families": list(QUERY_FAMILIES[: config.query_families]),
                "queries_per_family": config.queries_per_family,
                "languages": languages,
            },
            "query_intents",
        )
        generated_by_family: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        if generated:
            for item in generated.get("query_intents") or []:
                if isinstance(item, Mapping) and str(item.get("family") or "").lower() in QUERY_FAMILIES:
                    generated_by_family[str(item["family"]).lower()].append(item)
        intents: list[dict[str, Any]] = []
        for family in QUERY_FAMILIES[: config.query_families]:
            candidates = generated_by_family.get(family) or [
                {"base_query": query, "translations": {}} for query in fallback_queries[family]
            ]
            for candidate in candidates[: config.queries_per_family]:
                query = str(candidate.get("base_query") or "").strip()
                if not query:
                    continue
                translations = candidate.get("translations") if isinstance(candidate.get("translations"), Mapping) else {}
                intent_id = new_uuid7()
                variants = []
                for country in config.countries:
                    languages = [country["language"]]
                    secondary = country.get("secondary_language")
                    if config.use_secondary_language and secondary and secondary not in languages:
                        languages.append(secondary)
                    for language in languages:
                        translated = str(translations.get(language) or "").strip()
                        variants.append({
                            "country": country["code"],
                            "language": language,
                            "query": query if language == "en" else translated or self._local_query(query, language, family),
                            "semantic_intent": query,
                        })
                intents.append({
                    "query_intent_id": intent_id,
                    "family": family,
                    "base_query": query,
                    "variants": deduplicate_queries(variants),
                })
        artifact = {"query_intents": intents, "countries": list(config.countries), "serp_depth": config.serp_depth}
        return artifact, {"intents": len(intents), "serps_planned": sum(len(item["variants"]) for item in intents)}, False

    def _serp_discovery(self, run_id: str, config: LavalConfig, country_filter: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        plan = self.repository.stage(run_id, "QUERY_PLAN")["artifact"]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        failures: list[dict[str, Any]] = []
        calls = 0
        queued_requests: list[dict[str, Any]] = []
        for intent in plan["query_intents"]:
            for variant in intent["variants"]:
                country = str(variant["country"]).upper()
                if country_filter and country != country_filter.upper():
                    continue
                query = str(variant["query"])
                key = f"{intent['query_intent_id']}:{country}:{variant['language']}:{input_hash(query)[:10]}"
                existing = self.store.fetchone(
                    "SELECT status,input_hash FROM laval_stage_items WHERE run_id=%s AND stage='SERP_DISCOVERY' AND item_key=%s",
                    (run_id, key),
                )
                digest = input_hash(query, country, variant["language"], config.serp_depth, self.providers.search.name)
                if not (existing and existing["status"] == "completed" and existing["input_hash"] == digest):
                    queued_requests.append({"key": key, "query": query, "country": country, "language": variant["language"], "depth": config.serp_depth, "operation": "localized_serp"})
        queued_results = self._queued_search_batch(run_id, "SERP_DISCOVERY", queued_requests)
        queued_mode = hasattr(self.providers.search, "submit_many")
        for intent in plan["query_intents"]:
            for variant in intent["variants"]:
                country = str(variant["country"]).upper()
                if country_filter and country != country_filter.upper():
                    continue
                self._ensure_active(run_id)
                query = str(variant["query"])
                key = f"{intent['query_intent_id']}:{country}:{variant['language']}:{input_hash(query)[:10]}"
                digest = input_hash(query, country, variant["language"], config.serp_depth, self.providers.search.name)
                existing = self.store.fetchone(
                    "SELECT status,input_hash,payload FROM laval_stage_items WHERE run_id=%s AND stage='SERP_DISCOVERY' AND item_key=%s",
                    (run_id, key),
                )
                if existing and existing["status"] == "completed" and existing["input_hash"] == digest:
                    grouped[country].append(json_safe(existing["payload"]))
                    self.repository.record_cost(run_id, "SERP_DISCOVERY", self.providers.search.name, "localized_serp", requests=0, cached=True)
                    continue
                self.repository.stage_item(run_id, "SERP_DISCOVERY", key, status="running", country=country, provider=self.providers.search.name, digest=digest, payload={"query": query})
                try:
                    results = queued_results.get(key)
                    if results is None:
                        results = self._retry(
                            lambda: self.providers.search.search(query, country=country, language=variant["language"], depth=config.serp_depth),
                            lambda: self.repository.stage_item(run_id, "SERP_DISCOVERY", key, status="running", country=country, provider=self.providers.search.name, digest=digest, payload={"query": query, "retry": True}),
                        )
                    calls += 1
                    normalized = []
                    cost = 0.0
                    for position, result in enumerate(results[: config.serp_depth], 1):
                        url = canonical_url(str(result.get("url") or ""))
                        if not url:
                            continue
                        is_fixture = bool((result.get("provider_metadata") or {}).get("fixture"))
                        source_type = "serp"
                        evidence_id = self.repository.add_evidence(run_id, {
                            "source_type": source_type,
                            "source_url": url,
                            "source_title": str(result.get("title") or url)[:1000],
                            "publisher": canonical_domain(url),
                            "country": country,
                            "excerpt": str(result.get("snippet") or "")[:4000],
                            "claim": f"Google organic result for {query!r} at position {int(result.get('position') or position)}",
                            "confidence": .65 if is_fixture else .8,
                            "metadata": {**dict(result.get("provider_metadata") or {}), "query_intent_id": intent["query_intent_id"], "query": query, "language": variant["language"]},
                        })
                        metadata = dict(result.get("provider_metadata") or {})
                        cost = max(cost, float(metadata.get("cost") or 0))
                        normalized.append({
                            "evidence_id": evidence_id,
                            "query_intent_id": intent["query_intent_id"],
                            "family": intent["family"],
                            "query": query,
                            "country": country,
                            "language": variant["language"],
                            "position": int(result.get("position") or position),
                            "title": str(result.get("title") or url),
                            "url": url,
                            "domain": canonical_domain(url),
                            "snippet": str(result.get("snippet") or ""),
                            "result_type": str(result.get("result_type") or "organic"),
                            "provider_metadata": metadata,
                        })
                    item_payload = {"query": variant, "results": normalized}
                    grouped[country].append(item_payload)
                    self.repository.stage_item(run_id, "SERP_DISCOVERY", key, status="completed", country=country, provider=self.providers.search.name, digest=digest, payload=item_payload)
                    if not queued_mode:
                        self.repository.record_cost(run_id, "SERP_DISCOVERY", self.providers.search.name, "localized_serp", amount_usd=cost)
                except Exception as error:
                    failure = {"country": country, "query": query, "error": type(error).__name__, "message": str(error)[:500]}
                    failures.append(failure)
                    self.repository.stage_item(run_id, "SERP_DISCOVERY", key, status="failed", country=country, provider=self.providers.search.name, digest=digest, payload={"query": variant}, error=failure)
        existing = self.repository.stage_items(run_id, "SERP_DISCOVERY")
        if country_filter:
            grouped = defaultdict(list)
            for item in existing:
                if item["status"] == "completed":
                    grouped[str(item.get("country"))].append(item["payload"])
        successes = sum(len(value) for value in grouped.values())
        if successes == 0:
            raise RuntimeError("all localized SERP requests failed")
        expected_countries = {item["code"] for item in config.countries}
        missing = sorted(expected_countries - set(grouped))
        artifact = {"countries": dict(grouped), "failures": failures, "missing_countries": missing, "provider": self.providers.search.name}
        return artifact, {"requests": calls, "successful_serps": successes, "failed_serps": len(failures), "countries": len(grouped)}, bool(failures or missing)

    @staticmethod
    def _result_type(result: Mapping[str, Any]) -> str:
        given = str(result.get("result_type") or "")
        if given in {"direct_product", "adjacent_product", "substitute", "directory", "article", "review_site", "social", "irrelevant"}:
            return given
        domain = str(result.get("domain") or "").lower()
        title = str(result.get("title") or "").lower()
        if any(value in domain for value in ("reddit.com", "youtube.com", "facebook.com", "instagram.com", "tiktok.com")):
            return "social"
        if any(value in domain for value in ("wikipedia.org", "medium.com")) or any(value in title for value in ("guide", "how to", "news")):
            return "article"
        if any(value in domain for value in ("g2.com", "capterra.com", "trustpilot.com")):
            return "review_site"
        if re.search(r"\b(best|top)\s+\d+", title) or "directory" in domain:
            return "directory"
        return "direct_product"

    def _competitor_selection(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        serp = self.repository.stage(run_id, "SERP_DISCOVERY")["artifact"]
        dna = self.repository.stage(run_id, "OWNER_DNA")["artifact"]["owner_dna"]
        owner_words = set(normalize_words(" ".join(str(dna.get(key, "")) for key in ("problem", "core_mechanism", "target_user"))))
        candidates: dict[str, dict[str, Any]] = {}
        country_query_counts = {code: max(1, len(items)) for code, items in serp.get("countries", {}).items()}
        for country, searches in serp.get("countries", {}).items():
            for search in searches:
                for result in search.get("results", []):
                    kind = self._result_type(result)
                    if kind not in {"direct_product", "adjacent_product", "substitute"}:
                        continue
                    domain = canonical_domain(str(result.get("url") or result.get("domain") or ""))
                    if not domain:
                        continue
                    candidate = candidates.setdefault(domain, {
                        "domain": domain,
                        "url": canonical_url(str(result.get("url"))),
                        "name": re.split(r"[—|:-]", str(result.get("title") or domain))[0].strip()[:300] or domain,
                        "types": [], "countries": defaultdict(list), "queries": set(), "positions": [], "evidence_ids": [], "text": [],
                    })
                    candidate["types"].append(kind)
                    candidate["countries"][country].append(result)
                    candidate["queries"].add(str(result.get("query_intent_id")))
                    candidate["positions"].append(int(result.get("position") or config.serp_depth))
                    candidate["evidence_ids"].append(str(result["evidence_id"]))
                    candidate["text"].append(f"{result.get('title', '')} {result.get('snippet', '')}")
        if not candidates:
            raise RuntimeError("SERP discovery produced no product candidates")
        total_countries = max(1, len(config.countries))
        for candidate in candidates.values():
            text_words = set(normalize_words(" ".join(candidate["text"])))
            overlap = len(owner_words & text_words) / max(1, min(len(owner_words), 10))
            direct = max(1.0 if item == "direct_product" else .72 if item == "adjacent_product" else .55 for item in candidate["types"])
            components = {
                "query_recurrence": min(1, len(candidate["queries"]) / max(1, config.query_families * config.queries_per_family)),
                "average_serp_position": max(0, 1 - (sum(candidate["positions"]) / len(candidate["positions"]) - 1) / max(1, config.serp_depth - 1)),
                "semantic_relevance": max(.35, min(1, overlap + .35)),
                "country_relevance": len(candidate["countries"]) / total_countries,
                "directness": direct,
                "evidence_confidence": min(1, .5 + .08 * len(candidate["evidence_ids"])),
            }
            candidate["components"] = components
            candidate["score"] = competitor_score(components, config)
            candidate["result_type"] = "direct_product" if direct == 1 else "adjacent_product" if direct >= .7 else "substitute"
        globally = sorted(candidates.values(), key=lambda item: (-item["score"], item["domain"]))
        selected_domains = {item["domain"] for item in globally[: config.max_unique_competitors]}
        per_country_candidates: dict[str, list[dict[str, Any]]] = {}
        for country in [item["code"] for item in config.countries]:
            local = []
            for candidate in globally:
                appearances = candidate["countries"].get(country) or []
                if not appearances:
                    continue
                recurrence = len({str(item.get("query_intent_id")) for item in appearances}) / country_query_counts.get(country, 1)
                position = sum(int(item.get("position") or config.serp_depth) for item in appearances) / len(appearances)
                local_components = {**candidate["components"], "query_recurrence": min(1, recurrence), "average_serp_position": max(0, 1 - (position - 1) / max(1, config.serp_depth - 1)), "country_relevance": 1.0}
                local.append({**candidate, "country_score": competitor_score(local_components, config), "country_components": local_components})
            local.sort(key=lambda item: (-item["country_score"], item["domain"]))
            for item in local[: config.top_competitors_per_country]:
                selected_domains.add(item["domain"])
            per_country_candidates[country] = local
        competitor_ids: dict[str, str] = {}
        for candidate in globally:
            competitor_id = new_uuid7()
            competitor_ids[candidate["domain"]] = competitor_id
            self.store.execute(
                """INSERT INTO laval_competitors(id,run_id,name,domain,url,result_type,score,selected,components)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING 1""",
                (competitor_id, run_id, candidate["name"], candidate["domain"], candidate["url"], candidate["result_type"], candidate["score"], candidate["domain"] in selected_domains, self.store.json(candidate["components"])),
            )
            for evidence_id in dict.fromkeys(candidate["evidence_ids"]):
                self.store.execute("UPDATE laval_evidence SET competitor_id=%s WHERE id=%s RETURNING 1", (competitor_id, evidence_id))
                self.repository.add_lineage(run_id, "competitor", competitor_id, "derived_from", "evidence", evidence_id)
        country_view: dict[str, list[dict[str, Any]]] = {}
        missing: list[str] = []
        for country, local in per_country_candidates.items():
            chosen = [item for item in local if item["domain"] in selected_domains][: config.top_competitors_per_country]
            if len(chosen) < config.top_competitors_per_country:
                missing.append(country)
            country_view[country] = []
            for rank, candidate in enumerate(chosen, 1):
                competitor_id = competitor_ids[candidate["domain"]]
                evidence_ids = list(dict.fromkeys(item["evidence_id"] for item in candidate["countries"][country]))
                self.store.execute(
                    """INSERT INTO laval_competitor_country_rankings(run_id,competitor_id,country,rank,score,evidence_ids)
                       VALUES(%s,%s,%s,%s,%s,%s::uuid[]) RETURNING 1""",
                    (run_id, competitor_id, country, rank, candidate["country_score"], evidence_ids),
                )
                country_view[country].append({"competitor_id": competitor_id, "name": candidate["name"], "domain": candidate["domain"], "rank": rank, "score": candidate["country_score"], "components": candidate["country_components"], "evidence_ids": evidence_ids})
        global_view = [{"competitor_id": competitor_ids[item["domain"]], "name": item["name"], "domain": item["domain"], "url": item["url"], "type": item["result_type"], "score": item["score"], "selected": item["domain"] in selected_domains, "countries": sorted(item["countries"]), "components": item["components"], "evidence_ids": list(dict.fromkeys(item["evidence_ids"]))} for item in globally]
        artifact = {"country_view": country_view, "global_deduplicated": global_view, "excluded_result_count": sum(len(search.get("results", [])) for searches in serp.get("countries", {}).values() for search in searches) - sum(len(item["evidence_ids"]) for item in globally), "missing_top_three": missing}
        return artifact, {"unique_candidates": len(globally), "selected_unique": len(selected_domains), "country_slots": sum(len(value) for value in country_view.values())}, bool(missing)

    def _competitor_evidence(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        competitors = self.store.fetchall("SELECT * FROM laval_competitors WHERE run_id=%s AND selected ORDER BY score DESC LIMIT %s", (run_id, config.max_unique_competitors))
        queued_requests: list[dict[str, Any]] = []
        for competitor in competitors:
            searches = (
                (f'{competitor["name"]} review video demo', "youtube", config.youtube_items_per_competitor),
                (f'{competitor["name"]} problems review annoying missing feature reddit', "negative", config.negative_feedback_items_per_competitor),
            )
            for query, purpose, limit in searches:
                if limit > 0:
                    queued_requests.append({"key": f'{competitor["id"]}:{purpose}', "query": query, "country": "US", "language": "en", "depth": min(100, max(3, limit)), "operation": purpose})
        queued_results = self._queued_search_batch(run_id, "COMPETITOR_EVIDENCE", queued_requests)
        queued_mode = hasattr(self.providers.search, "submit_many")
        dossiers: dict[str, dict[str, Any]] = {}
        failures: list[dict[str, Any]] = []
        for competitor in competitors:
            self._ensure_active(run_id)
            competitor_id = str(competitor["id"])
            evidence_ids: list[str] = []
            key = competitor_id
            digest = input_hash(competitor_id, competitor["url"], config.website_pages_per_competitor, config.youtube_items_per_competitor, config.negative_feedback_items_per_competitor, self.providers.web.name, self.providers.search.name)
            existing = self.store.fetchone(
                "SELECT status,input_hash,payload FROM laval_stage_items WHERE run_id=%s AND stage='COMPETITOR_EVIDENCE' AND item_key=%s",
                (run_id, key),
            )
            if existing and existing["status"] == "completed" and existing["input_hash"] == digest:
                dossiers[competitor_id] = json_safe(existing["payload"])
                self.repository.record_cost(run_id, "COMPETITOR_EVIDENCE", f"{self.providers.web.name}+{self.providers.search.name}", "competitor_evidence", requests=0, cached=True)
                continue
            self.repository.stage_item(run_id, "COMPETITOR_EVIDENCE", key, status="running", provider=f"{self.providers.web.name}+{self.providers.search.name}", payload={"competitor": competitor["name"]})
            serp_sources = self.store.fetchall(
                "SELECT source_url FROM laval_evidence WHERE run_id=%s AND competitor_id=%s AND source_type IN ('serp','fixture') ORDER BY retrieved_at",
                (run_id, competitor_id),
            )
            parsed = urlsplit(str(competitor["url"]))
            origin = urlunsplit((parsed.scheme or "https", parsed.netloc, "", "", "")).rstrip("/")
            common_product_pages = [
                origin,
                f"{origin}/features",
                f"{origin}/pricing",
                f"{origin}/how-it-works",
                f"{origin}/use-cases",
                f"{origin}/faq",
                f"{origin}/about",
                f"{origin}/customers",
                f"{origin}/testimonials",
            ]
            page_urls = list(dict.fromkeys(
                canonical_url(value)
                for value in [str(competitor["url"]), *common_product_pages, *[str(item["source_url"]) for item in serp_sources]]
                if canonical_url(value)
            ))[: config.website_pages_per_competitor]
            for page_url in page_urls:
                try:
                    page = self._retry(lambda: self.providers.web.fetch(page_url))
                    website_id = self.repository.add_evidence(run_id, {
                        "source_type": "fixture" if page.get("fixture") else "website",
                        "source_url": page["url"], "source_title": f"{competitor['name']} official product page", "publisher": competitor["domain"],
                        "competitor_id": competitor_id, "excerpt": str(page.get("text", ""))[:5000],
                        "claim": str(page.get("text", ""))[:1200], "confidence": .6 if page.get("fixture") else .82,
                        "metadata": {"content_type": page.get("content_type"), "status_code": page.get("status_code"), "truncated": page.get("truncated", False)},
                    })
                    evidence_ids.append(website_id)
                    self.repository.add_lineage(run_id, "evidence", website_id, "derived_from", "competitor", competitor_id)
                except Exception as error:
                    failures.append({"competitor_id": competitor_id, "source": "website", "url": page_url, "error": type(error).__name__})
            searches = (
                (f'{competitor["name"]} review video demo', "youtube", config.youtube_items_per_competitor),
                (f'{competitor["name"]} problems review annoying missing feature reddit', "negative", config.negative_feedback_items_per_competitor),
            )
            for query, purpose, limit in searches:
                if limit <= 0:
                    continue
                try:
                    rows = queued_results.get(f"{competitor_id}:{purpose}")
                    if rows is None and not queued_mode:
                        rows = self._retry(lambda: self.providers.search.search(query, country="US", language="en", depth=min(100, max(3, limit))))
                        self.repository.record_cost(run_id, "COMPETITOR_EVIDENCE", self.providers.search.name, purpose)
                    if rows is None:
                        raise RuntimeError(f"queued search result is missing for {purpose}")
                    selected = rows if purpose == "negative" else [item for item in rows if "youtube" in canonical_domain(str(item.get("url") or ""))]
                    if purpose == "youtube" and not selected:
                        selected = rows[:1]
                    for result in selected[:limit]:
                        url = canonical_url(str(result.get("url") or ""))
                        if not url:
                            continue
                        domain = canonical_domain(url)
                        if purpose == "youtube":
                            source_type = "youtube"
                            claim = f"Video evidence about {competitor['name']}: {result.get('snippet', '')}"
                        else:
                            source_type = "reddit" if "reddit" in domain else "review" if any(value in domain for value in ("g2.", "capterra.", "trustpilot.")) else "forum"
                            claim = f"Potential negative-feedback signal about {competitor['name']}: {result.get('snippet', '')}"
                        if bool((result.get("provider_metadata") or {}).get("fixture")):
                            source_type = "fixture"
                        evidence_id = self.repository.add_evidence(run_id, {
                            "source_type": source_type, "source_url": url, "source_title": str(result.get("title") or url), "publisher": domain,
                            "competitor_id": competitor_id, "country": "US", "excerpt": str(result.get("snippet") or ""), "claim": claim,
                            "confidence": .55 if source_type == "fixture" else .62, "metadata": {"purpose": purpose, "query": query, "provider": self.providers.search.name},
                        })
                        evidence_ids.append(evidence_id)
                        self.repository.add_lineage(run_id, "evidence", evidence_id, "derived_from", "competitor", competitor_id)
                except Exception as error:
                    failures.append({"competitor_id": competitor_id, "source": purpose, "error": type(error).__name__})
            status = "completed" if evidence_ids else "failed"
            item = {"competitor_id": competitor_id, "name": competitor["name"], "evidence_ids": evidence_ids}
            dossiers[competitor_id] = item
            self.repository.stage_item(run_id, "COMPETITOR_EVIDENCE", key, status=status, provider=f"{self.providers.web.name}+{self.providers.search.name}", digest=digest, payload=item, error=None if evidence_ids else {"message": "no evidence collected"})
        if not any(item["evidence_ids"] for item in dossiers.values()):
            raise RuntimeError("competitor evidence collection produced no evidence")
        graph = self._sync_evidence_graph(run_id)
        artifact = {"competitors": list(dossiers.values()), "failures": failures, "graph_sync": graph}
        return artifact, {"competitors": len(competitors), "evidence_items": sum(len(item["evidence_ids"]) for item in dossiers.values()), "failures": len(failures), "graph_sources": len(graph.get("sources", {}))}, bool(failures)

    def _sync_evidence_graph(self, run_id: str) -> dict[str, Any]:
        if self.repository.run(run_id).get("evidence_mode") == "demo_fixture":
            return {"sources": {}, "demo_excluded": True}
        pending = self.store.fetchall(
            """SELECT * FROM laval_evidence
               WHERE run_id=%s AND commander_source_id IS NULL AND source_type<>'fixture'
               ORDER BY retrieved_at""",
            (run_id,),
        )
        if not pending:
            return {"sources": {}, "already_synced": True}
        findings = [{
            "external_id": str(item["id"]), "title": item["source_title"], "source_uri": item["source_url"],
            "finding_summary": item["claim"] or item["excerpt"], "publisher": item["publisher"] or canonical_domain(item["source_url"]),
            "credibility": float(item["confidence"]), "research_type": "product_discovery",
        } for item in pending if item["claim"] or item["excerpt"]]
        try:
            result = self.providers.research.record(findings)
            mapping = {str(key): str(value) for key, value in (result.get("sources") or {}).items()}
            self.repository.link_commander_sources(mapping)
            return result
        except Exception as error:
            return {"sources": {}, "error": type(error).__name__, "message": str(error)[:500], "sink": self.providers.research.name}

    def _competitor_dossiers(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        competitors = self.store.fetchall("SELECT * FROM laval_competitors WHERE run_id=%s AND selected ORDER BY score DESC LIMIT %s", (run_id, config.max_unique_competitors))
        compiler = ContextCompiler(config)
        results = []
        partial = False
        for competitor in competitors:
            evidence = self.repository.evidence(run_id, competitor_id=str(competitor["id"]))
            llm = self._llm(run_id, "COMPETITOR_DOSSIERS", "laval_competitor_dossier", "Extract only evidence-supported product positioning, audience, features, pricing, distribution, hooks, strengths, complaints, gaps, and keywords. Every claim must cite supplied evidence IDs.", compiler.build_competitor_extraction_context(competitor, evidence), "dossier")
            dossier = llm.get("dossier") if llm else None
            evidence_ids = [str(item["id"]) for item in evidence]
            if not isinstance(dossier, Mapping):
                claims = [str(item.get("claim") or item.get("excerpt") or "")[:500] for item in evidence if item.get("claim") or item.get("excerpt")]
                complaints = [value for value in claims if any(word in value.lower() for word in ("problem", "fatigue", "missing", "hard", "weak", "annoy"))]
                dossier = {
                    "competitor_id": str(competitor["id"]), "name": competitor["name"], "url": competitor["url"], "type": competitor["result_type"],
                    "country_presence": [row["country"] for row in self.store.fetchall("SELECT country FROM laval_competitor_country_rankings WHERE competitor_id=%s ORDER BY country", (competitor["id"],))],
                    "positioning": claims[:3], "audiences": ["Users represented by the observed product messaging"],
                    "features": ["Workflow inferred from persisted evidence; validate against official pages"], "pricing": ["Not reliably observed"],
                    "distribution": ["Search discovery", "Shareable/referral loops"], "hooks": claims[:3],
                    "strengths": claims[:2], "complaints": complaints[:12] or ["No repeated complaint cluster met the evidence threshold"],
                    "gaps": ["Portable proof history", "Deeper accountability feedback"],
                    "keywords": list(normalize_words(" ".join(claims)))[:20], "evidence_ids": evidence_ids,
                    "confidence": min(.9, .35 + .08 * len(evidence_ids)),
                }
                partial = partial or len(evidence_ids) < 2
            valid_ids = set(evidence_ids)
            cited = [str(value) for value in dossier.get("evidence_ids", evidence_ids) if str(value) in valid_ids]
            dossier = {**json_safe(dossier), "competitor_id": str(competitor["id"]), "name": competitor["name"], "url": competitor["url"], "evidence_ids": cited or evidence_ids}
            complaint_evidence = [
                item for item in evidence
                if (item.get("metadata") or {}).get("purpose") == "negative"
                or any(word in str(item.get("claim", "")).lower() for word in ("problem", "fatigue", "missing", "hard", "weak", "annoy"))
            ]
            complaint_clusters: list[dict[str, Any]] = []
            for evidence_item in complaint_evidence:
                statement = str(evidence_item.get("claim") or evidence_item.get("excerpt") or "").strip()
                words = set(normalize_words(statement))
                cluster = next((candidate for candidate in complaint_clusters if len(words & candidate["_words"]) / max(1, len(words | candidate["_words"])) >= .4), None)
                if cluster is None:
                    cluster = {"statement": statement[:1000], "evidence_ids": [], "source_urls": [], "countries": [], "_words": words}
                    complaint_clusters.append(cluster)
                cluster["evidence_ids"].append(str(evidence_item["id"]))
                cluster["source_urls"].append(str(evidence_item["source_url"]))
                if evidence_item.get("country"):
                    cluster["countries"].append(str(evidence_item["country"]))
            for cluster in complaint_clusters:
                cluster["evidence_ids"] = list(dict.fromkeys(cluster["evidence_ids"]))
                sources = set(cluster.pop("source_urls"))
                cluster.pop("_words", None)
                cluster["frequency"] = len(cluster["evidence_ids"])
                cluster["severity"] = min(1, .45 + .08 * cluster["frequency"])
                cluster["source_diversity"] = len(sources)
                cluster["countries"] = sorted(set(cluster["countries"]))
                cluster["competitors"] = [str(competitor["id"])]
                cluster["single_source"] = len(sources) < 2
                cluster["confidence"] = min(.9, .35 + .12 * len(sources) + .06 * cluster["frequency"])
            dossier["complaint_clusters"] = complaint_clusters
            confidence = clamp(dossier.get("confidence", min(.9, .35 + .08 * len(evidence_ids))))
            dossier["confidence"] = confidence
            self.store.execute(
                """INSERT INTO laval_competitor_dossiers(competitor_id,run_id,dossier,confidence,evidence_ids)
                   VALUES(%s,%s,%s::jsonb,%s,%s::uuid[]) RETURNING 1""",
                (competitor["id"], run_id, self.store.json(dossier), confidence, dossier["evidence_ids"]),
            )
            results.append(dossier)
        return {"competitors": results}, {"dossiers": len(results), "claims": sum(len(item.get("evidence_ids", [])) for item in results)}, partial

    def _opportunity_matrix(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        dna = self.repository.stage(run_id, "OWNER_DNA")["artifact"]["owner_dna"]
        dossiers = [row["dossier"] for row in self.store.fetchall("SELECT dossier FROM laval_competitor_dossiers WHERE run_id=%s ORDER BY confidence DESC", (run_id,))]
        compiler = ContextCompiler(config)
        llm = self._llm(run_id, "OPPORTUNITY_MATRIX", "laval_opportunity_matrix", "Compress dossiers into evidence-backed opportunity vectors. Preserve all rows, cite only supplied evidence IDs, and return normalized component scores from 0 to 1.", compiler.build_opportunity_context(dna, dossiers), "opportunities")
        raw = llm.get("opportunities") if llm else None
        if not isinstance(raw, list) or not raw:
            raw = []
            for dossier in dossiers:
                complaint_clusters = dossier.get("complaint_clusters") or []
                repeated = [item for item in complaint_clusters if not item.get("single_source")]
                complaints = [item["statement"] for item in repeated] or dossier.get("complaints") or ["Users lack a reliable outcome"]
                gaps = dossier.get("gaps") or ["Existing products leave an uncovered workflow"]
                for kind, value in (("pain", complaints[0]), ("gap", gaps[0])):
                    raw.append({
                        "statement": f"Users want {value}, but {dossier.get('name', 'existing products')} does not cover it reliably.",
                        "pain": str(value), "affected_segment": (dossier.get("audiences") or [dna.get("target_user")])[0],
                        "competitor_ids": [dossier["competitor_id"]], "countries": dossier.get("country_presence") or [],
                        "evidence_ids": dossier.get("evidence_ids") or [],
                        "scores": {"frequency": .55 if kind == "pain" else .45, "severity": .65 if kind == "pain" else .5, "coverage_gap": .7 if kind == "gap" else .6, "cross_market": min(1, len(dossier.get("country_presence") or []) / max(1, len(config.countries))), "owner_relevance": .75, "confidence": dossier.get("confidence", .5)},
                    })
        all_evidence = {str(row["id"]): row for row in self.store.fetchall("SELECT * FROM laval_evidence WHERE run_id=%s", (run_id,))}
        valid_competitors = {str(row["id"]) for row in self.store.fetchall("SELECT id FROM laval_competitors WHERE run_id=%s", (run_id,))}
        rows = []
        for item in raw:
            if not isinstance(item, Mapping) or not str(item.get("statement", "")).strip():
                continue
            evidence_ids = list(dict.fromkeys(str(value) for value in item.get("evidence_ids", []) if str(value) in all_evidence))
            if not evidence_ids:
                continue
            competitor_ids = list(dict.fromkeys(str(value) for value in item.get("competitor_ids", item.get("competitors", [])) if str(value) in valid_competitors))
            evidence = [all_evidence[value] for value in evidence_ids]
            countries = sorted(set(str(value) for value in item.get("countries", []) if value) | {str(value["country"]) for value in evidence if value.get("country")})
            source_types = {str(value["source_type"]) for value in evidence}
            scores = dict(item.get("scores") or {})
            dimensions = {
                "frequency": clamp(scores.get("frequency", min(1, len(evidence_ids) / 5))),
                "severity": clamp(scores.get("severity", .5)),
                "coverage_gap": clamp(scores.get("coverage_gap", .6)),
                "cross_market": clamp(scores.get("cross_market", len(countries) / max(1, len(config.countries)))),
                "owner_relevance": clamp(scores.get("owner_relevance", .65)),
                "confidence": clamp(min(scores.get("confidence", .5), .35 + .1 * len(evidence_ids) + .08 * len(source_types))),
            }
            opportunity_id = new_uuid7()
            row = {
                "id": opportunity_id, "statement": str(item["statement"])[:4000], "pain": str(item.get("pain", ""))[:2000],
                "affected_segment": str(item.get("affected_segment", ""))[:2000], "competitor_ids": competitor_ids, "countries": countries,
                "evidence_ids": evidence_ids, "scores": dimensions, "aggregate_score": opportunity_score(dimensions, config),
                "evidence_count": len(evidence_ids), "source_type_count": len(source_types), "country_count": len(countries), "competitor_count": len(competitor_ids),
            }
            rows.append(row)
        rows.sort(key=lambda item: (-item["aggregate_score"], item["statement"]))
        for index, row in enumerate(rows):
            selected = index < config.trend_gate_candidates
            row["selected_for_trends"] = selected
            self.store.execute(
                """INSERT INTO laval_opportunities(
                       id,run_id,statement,pain,affected_segment,competitor_ids,countries,evidence_ids,scores,
                       aggregate_score,selected_for_trends,evidence_count,source_type_count,country_count,competitor_count
                   ) VALUES(%s,%s,%s,%s,%s,%s::uuid[],%s,%s::uuid[],%s::jsonb,%s,%s,%s,%s,%s,%s) RETURNING 1""",
                (row["id"], run_id, row["statement"], row["pain"], row["affected_segment"], row["competitor_ids"], row["countries"], row["evidence_ids"], self.store.json(row["scores"]), row["aggregate_score"], selected, row["evidence_count"], row["source_type_count"], row["country_count"], row["competitor_count"]),
            )
            for evidence_id in row["evidence_ids"]:
                self.repository.add_lineage(run_id, "opportunity", row["id"], "derived_from", "evidence", evidence_id)
        if not rows:
            raise RuntimeError("no evidence-backed opportunity rows could be produced")
        return {"opportunities": rows, "trend_gate_candidate_ids": [item["id"] for item in rows if item["selected_for_trends"]]}, {"opportunities": len(rows), "trend_candidates": min(len(rows), config.trend_gate_candidates)}, False

    def _trend_query_plan(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        opportunities = self.store.fetchall("SELECT * FROM laval_opportunities WHERE run_id=%s AND selected_for_trends AND enabled ORDER BY aggregate_score DESC", (run_id,))
        dna = self.repository.stage(run_id, "OWNER_DNA")["artifact"]["owner_dna"]
        owner_words = normalize_words(f"{dna.get('problem', '')} {dna.get('core_mechanism', '')}")
        owner_term = " ".join(owner_words[:4])
        terms: list[tuple[str, str]] = []
        seen: set[str] = set()
        for opportunity in opportunities:
            words = normalize_words(f"{opportunity['statement']} {opportunity['pain']}")
            candidates = (
                " ".join(words[:4]),
                " ".join(words[-4:]),
                " ".join([owner_term, " ".join(words[:2])]).strip(),
            )
            for term in candidates:
                normalized = term.strip().lower()
                if normalized and normalized not in seen and len(terms) < config.trend_max_terms:
                    seen.add(normalized)
                    terms.append((str(opportunity["id"]), term))
        queries = []
        for opportunity_id, term in terms:
            for country in config.countries:
                for window in config.trend_windows:
                    query_id = new_uuid7()
                    self.store.execute(
                        """INSERT INTO laval_trend_queries(id,run_id,opportunity_id,term,country,time_window)
                           VALUES(%s,%s,%s,%s,%s,%s) RETURNING 1""",
                        (query_id, run_id, opportunity_id, term, country["code"], window),
                    )
                    self.repository.add_lineage(run_id, "trend_query", query_id, "derived_from", "opportunity", opportunity_id)
                    queries.append({"id": query_id, "opportunity_id": opportunity_id, "term": term, "country": country["code"], "window": window})
        if not queries:
            raise RuntimeError("trend query plan is empty")
        return {"queries": queries, "unique_terms": [term for _, term in terms], "windows": list(config.trend_windows), "countries": [item["code"] for item in config.countries]}, {"queries": len(queries), "unique_terms": len(terms)}, False

    def _trends_research(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        queries = self.store.fetchall("SELECT * FROM laval_trend_queries WHERE run_id=%s AND enabled ORDER BY country,term,time_window", (run_id,))
        completed, failures = [], []
        for query in queries:
            self._ensure_active(run_id)
            query_id = str(query["id"])
            window = query["time_window"]
            query_view = {**json_safe(query), "window": window}
            query_view.pop("time_window", None)
            digest = input_hash(query["term"], query["country"], window, self.providers.trends.name)
            existing = self.store.fetchone(
                "SELECT status,input_hash,payload FROM laval_stage_items WHERE run_id=%s AND stage='GOOGLE_TRENDS_RESEARCH' AND item_key=%s",
                (run_id, query_id),
            )
            if existing and existing["status"] == "completed" and existing["input_hash"] == digest:
                completed.append(json_safe(existing["payload"]))
                self.repository.record_cost(run_id, "GOOGLE_TRENDS_RESEARCH", self.providers.trends.name, "trend_interest_and_discovery", requests=0, cached=True)
                continue
            self.repository.stage_item(run_id, "GOOGLE_TRENDS_RESEARCH", query_id, status="running", country=query["country"], provider=self.providers.trends.name, digest=digest, payload={"query": json_safe(query)})
            try:
                result = self._retry(
                    lambda: self.providers.trends.research(query["term"], country=query["country"], window=window),
                    lambda: self.repository.stage_item(run_id, "GOOGLE_TRENDS_RESEARCH", query_id, status="running", country=query["country"], provider=self.providers.trends.name, digest=digest, payload={"query": query_view, "retry": True}),
                )
                evidence_id = self.repository.add_evidence(run_id, {
                    "source_type": "fixture" if self.providers.trends.name == "fixture" else "trend",
                    "source_url": f"google-trends://{query['country']}/{window}/{query_id}",
                    "source_title": f"Google Trends: {query['term']} ({query['country']}, {window})", "publisher": "Google Trends" if self.providers.trends.name != "fixture" else "PTW fixture",
                    "country": query["country"], "excerpt": str(result.get("raw") or result)[:5000],
                    "claim": f"Trend-provider response for {query['term']} in {query['country']} over {window}",
                    "confidence": .55 if self.providers.trends.name == "fixture" else .8,
                    "metadata": {"trend_query_id": query_id, "provider": self.providers.trends.name, "fixture": self.providers.trends.name == "fixture"},
                })
                payload = {"query": query_view, "response": json_safe(result), "evidence_id": evidence_id}
                completed.append(payload)
                self.repository.stage_item(run_id, "GOOGLE_TRENDS_RESEARCH", query_id, status="completed", country=query["country"], provider=self.providers.trends.name, digest=digest, payload=payload)
                self.repository.record_cost(run_id, "GOOGLE_TRENDS_RESEARCH", self.providers.trends.name, "trend_interest_and_discovery")
            except Exception as error:
                failure = {"query_id": query_id, "country": query["country"], "term": query["term"], "error": type(error).__name__, "message": str(error)[:500]}
                failures.append(failure)
                self.repository.stage_item(run_id, "GOOGLE_TRENDS_RESEARCH", query_id, status="failed", country=query["country"], provider=self.providers.trends.name, digest=digest, payload={"query": json_safe(query)}, error=failure)
        if not completed:
            raise RuntimeError("all Google Trends provider requests failed")
        return {"raw_results": completed, "failures": failures, "provider": self.providers.trends.name}, {"completed": len(completed), "failed": len(failures)}, bool(failures)

    def _trend_gate(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        items = self.repository.stage_items(run_id, "GOOGLE_TRENDS_RESEARCH")
        scores, discoveries = [], []
        for item in items:
            if item["status"] != "completed":
                continue
            payload = item["payload"]
            query, response = payload["query"], payload["response"]
            dimensions = {key: clamp((response.get("dimensions") or {}).get(key, 0)) for key in config.trend_weights}
            score_id = new_uuid7()
            score = {
                "id": score_id, "trend_query_id": query["id"], "opportunity_id": query["opportunity_id"], "term": query["term"],
                "country": query["country"], "window": query["window"], "dimensions": dimensions,
                "aggregate_score": trend_score(dimensions, config), "evidence_ids": [payload["evidence_id"]],
            }
            self.store.execute(
                """INSERT INTO laval_trend_scores(
                       id,run_id,trend_query_id,opportunity_id,term,country,time_window,dimensions,aggregate_score,evidence_ids
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::uuid[]) RETURNING 1""",
                (score_id, run_id, query["id"], query["opportunity_id"], query["term"], query["country"], query["window"], self.store.json(dimensions), score["aggregate_score"], score["evidence_ids"]),
            )
            self.repository.add_lineage(run_id, "trend_score", score_id, "derived_from", "trend_query", str(query["id"]))
            self.repository.add_lineage(run_id, "trend_score", score_id, "derived_from", "evidence", payload["evidence_id"])
            scores.append(score)
            for raw in response.get("discoveries") or []:
                kind = str(raw.get("type") or "related_query")
                if kind not in {"related_query", "rising_query", "breakout", "related_topic"}:
                    kind = "related_query"
                discovered = str(raw.get("term") or "").strip()
                if not discovered:
                    continue
                discovery_id = new_uuid7()
                record = {"id": discovery_id, "seed_term": query["term"], "discovered_term": discovered, "discovery_type": kind, "country": query["country"], "window": query["window"], "growth_label": str(raw.get("growth_label") or ""), "opportunity_ids": [query["opportunity_id"]], "evidence_ids": [payload["evidence_id"]], "confidence": .6 if self.providers.trends.name == "fixture" else .8}
                inserted = self.store.execute(
                    """INSERT INTO laval_trend_discoveries(
                           id,run_id,seed_term,discovered_term,discovery_type,country,time_window,growth_label,
                           opportunity_ids,evidence_ids,confidence
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::uuid[],%s::uuid[],%s)
                       ON CONFLICT DO NOTHING RETURNING 1""",
                    (discovery_id, run_id, record["seed_term"], discovered, kind, record["country"], record["window"], record["growth_label"], record["opportunity_ids"], record["evidence_ids"], record["confidence"]),
                )
                if inserted:
                    self.repository.add_lineage(run_id, "trend_discovery", discovery_id, "derived_from", "trend_query", str(query["id"]))
                    self.repository.add_lineage(run_id, "trend_discovery", discovery_id, "derived_from", "evidence", payload["evidence_id"])
                    discoveries.append(record)
        scores.sort(key=lambda item: (-item["aggregate_score"], item["term"], item["country"]))
        discoveries.sort(key=lambda item: (item["discovery_type"] != "breakout", -item["confidence"], item["discovered_term"]))
        if not scores:
            raise RuntimeError("Trend Gate could not normalize any trend response")
        return {"scores": scores, "discoveries": discoveries}, {"scores": len(scores), "discoveries": len(discoveries)}, False

    def _synthesis_packet(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        dna = self.repository.stage(run_id, "OWNER_DNA")["artifact"]["owner_dna"]
        opportunities = json_safe(self.store.fetchall("SELECT * FROM laval_opportunities WHERE run_id=%s AND enabled ORDER BY aggregate_score DESC", (run_id,)))
        scores = json_safe(self.store.fetchall("SELECT * FROM laval_trend_scores WHERE run_id=%s AND enabled ORDER BY aggregate_score DESC", (run_id,)))
        discoveries = json_safe(self.store.fetchall("SELECT * FROM laval_trend_discoveries WHERE run_id=%s AND enabled ORDER BY confidence DESC", (run_id,)))
        dossiers = [row["dossier"] for row in self.store.fetchall("SELECT dossier FROM laval_competitor_dossiers WHERE run_id=%s", (run_id,))]
        pains = [
            str(cluster.get("statement"))
            for dossier in dossiers
            for cluster in dossier.get("complaint_clusters", [])
            if not cluster.get("single_source")
        ] or [str(value) for dossier in dossiers for value in dossier.get("complaints", [])]
        distribution = [str(value) for dossier in dossiers for value in dossier.get("distribution", [])]
        packet = ContextCompiler(config).build_synthesis_context(dna, opportunities, scores, discoveries, pains, distribution, OPERATORS)
        evidence_ids = list(dict.fromkeys(str(value) for group in (packet["opportunities"], packet["trend_scores"], packet["trend_discoveries"]) for item in group for value in item.get("evidence_ids", [])))
        packet["selected_evidence_ids"] = evidence_ids
        return packet, {"opportunities": len(packet["opportunities"]), "trend_scores": len(packet["trend_scores"]), "trend_discoveries": len(packet["trend_discoveries"]), "evidence_ids": len(evidence_ids)}, False

    @staticmethod
    def _i18n(en: str, uk_prefix: str) -> dict[str, str]:
        return {"en": en, "uk": f"{uk_prefix}: {en}"}

    def _idea_expansion(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        packet = self.repository.stage(run_id, "SYNTHESIS_PACKET")["artifact"]
        llm = self._llm(run_id, "IDEA_EXPANSION", "laval_idea_expansion", "Generate broad, non-duplicate idea variants. Use every transformation operator. Each variant must reference valid owner, opportunity, trend-score, trend-discovery, and evidence IDs from the synthesis packet. Every owner-facing field must have exact en and uk keys.", packet, "variants")
        raw = llm.get("variants") if llm else None
        opportunities = packet.get("opportunities") or []
        trend_scores = packet.get("trend_scores") or []
        discoveries = packet.get("trend_discoveries") or []
        owner_id = self.repository.owner(run_id)["id"]
        operator_counts = {
            operator: sum(
                1 for item in raw or []
                if isinstance(item, Mapping) and str(item.get("operator") or "").lower() == operator
            )
            for operator in OPERATORS
        }
        if (
            not isinstance(raw, list)
            or len(raw) != len(OPERATORS) * config.variants_per_operator
            or any(count != config.variants_per_operator for count in operator_counts.values())
        ):
            raw = []
            labels = {"invert": ("Invert", "Інверсія"), "remove": ("Remove", "Усунення"), "extreme": ("Extreme", "Екстремум"), "transfer": ("Transfer", "Перенесення"), "resegment": ("Resegment", "Новий сегмент"), "recombine": ("Recombine", "Рекомбінація"), "distribution_first": ("Distribution First", "Спершу дистрибуція")}
            for op_index, operator in enumerate(OPERATORS):
                for ordinal in range(config.variants_per_operator):
                    opportunity = opportunities[(op_index + ordinal) % len(opportunities)] if opportunities else {}
                    score = trend_scores[(op_index * config.variants_per_operator + ordinal) % len(trend_scores)] if trend_scores else {}
                    discovery = discoveries[(op_index + ordinal) % len(discoveries)] if discoveries else {}
                    statement = str(opportunity.get("statement") or "an uncovered user need")
                    trend_term = str(discovery.get("discovered_term") or score.get("term") or "emerging behavior")
                    en_label, uk_label = labels[operator]
                    title = f"{en_label} {ordinal + 1}: {statement[:72]}"
                    raw.append({
                        "title": self._i18n(title, uk_label),
                        "one_liner": self._i18n(f"Use {operator.replace('_', ' ')} to combine {statement} with {trend_term}.", uk_label),
                        "mechanism": self._i18n(f"A {operator.replace('_', ' ')} mechanism centered on {trend_term}.", "Механізм"),
                        "target_user": self._i18n(str(opportunity.get("affected_segment") or packet.get("owner_dna", {}).get("target_user") or "Target users to validate"), "Цільовий користувач"),
                        "why_new": self._i18n(f"It applies {operator.replace('_', ' ')} to evidence-backed gaps and a post-compression trend discovery.", "Чому це нове"),
                        "operator": operator,
                        "opportunity_ids": [opportunity["id"]] if opportunity.get("id") else [],
                        "trend_signal_ids": [score["id"]] if score.get("id") else [],
                        "trend_discovery_ids": [discovery["id"]] if discovery.get("id") else [],
                        "evidence_ids": list(dict.fromkeys((opportunity.get("evidence_ids") or []) + (score.get("evidence_ids") or []) + (discovery.get("evidence_ids") or []))),
                    })
        valid_opportunities = {str(item["id"]) for item in opportunities}
        valid_scores = {str(item["id"]) for item in trend_scores}
        valid_discoveries = {str(item["id"]) for item in discoveries}
        valid_evidence = {str(value) for value in packet.get("selected_evidence_ids") or []}
        operator_ids = {}
        instructions = {
            "invert": "Invert an important category assumption.", "remove": "Remove a repeated user pain.", "extreme": "Push a useful property to an extreme.",
            "transfer": "Import a mechanism from an adjacent behavior.", "resegment": "Apply the mechanism to a surprising plausible audience.",
            "recombine": "Combine Owner DNA, an opportunity, and trend behavior.", "distribution_first": "Rebuild the concept around a distribution loop.",
        }
        for operator in OPERATORS:
            operator_id = new_uuid7()
            operator_ids[operator] = operator_id
            self.store.execute("INSERT INTO laval_transformation_operators(id,run_id,name,instruction) VALUES(%s,%s,%s,%s) RETURNING 1", (operator_id, run_id, operator, instructions[operator]))
        variants = []
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            operator = str(item.get("operator") or "recombine").lower()
            if operator not in OPERATORS:
                operator = "recombine"
            localized = {}
            for field in ("title", "one_liner", "mechanism", "target_user", "why_new"):
                value = item.get(field)
                if isinstance(value, Mapping) and set(value) >= {"en", "uk"}:
                    localized[field] = {"en": str(value["en"]), "uk": str(value["uk"])}
                else:
                    text = str(value or "Needs validation")
                    localized[field] = {"en": text, "uk": f"Переклад: {text}"}
            opportunity_ids = [str(value) for value in item.get("opportunity_ids", []) if str(value) in valid_opportunities]
            score_ids = [str(value) for value in item.get("trend_signal_ids", []) if str(value) in valid_scores]
            discovery_ids = [str(value) for value in item.get("trend_discovery_ids", []) if str(value) in valid_discoveries]
            evidence_ids = [str(value) for value in item.get("evidence_ids", []) if str(value) in valid_evidence]
            if not opportunity_ids and opportunities:
                opportunity_ids = [str(opportunities[len(variants) % len(opportunities)]["id"])]
            if not score_ids and trend_scores:
                score_ids = [str(trend_scores[len(variants) % len(trend_scores)]["id"])]
            if not discovery_ids and discoveries:
                discovery_ids = [str(discoveries[len(variants) % len(discoveries)]["id"])]
            if not evidence_ids:
                evidence_ids = list(dict.fromkeys(str(value) for group in (opportunities, trend_scores, discoveries) for candidate in group if str(candidate.get("id")) in set(opportunity_ids + score_ids + discovery_ids) for value in candidate.get("evidence_ids", [])))
            variant_id = new_uuid7()
            variant = {"id": variant_id, **localized, "operator": operator, "owner_idea_id": owner_id, "opportunity_ids": opportunity_ids, "trend_signal_ids": score_ids, "trend_discovery_ids": discovery_ids, "evidence_ids": evidence_ids}
            self.store.execute(
                """INSERT INTO laval_idea_variants(
                       id,run_id,owner_idea_id,title,one_liner,mechanism,target_user,why_new,operator,
                       opportunity_ids,trend_signal_ids,trend_discovery_ids,evidence_ids
                   ) VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,
                            %s::uuid[],%s::uuid[],%s::uuid[],%s::uuid[]) RETURNING 1""",
                (variant_id, run_id, owner_id, self.store.json(variant["title"]), self.store.json(variant["one_liner"]), self.store.json(variant["mechanism"]), self.store.json(variant["target_user"]), self.store.json(variant["why_new"]), operator, opportunity_ids, score_ids, discovery_ids, evidence_ids),
            )
            self.repository.add_lineage(run_id, "idea_variant", variant_id, "derived_from", "owner_idea", owner_id)
            self.repository.add_lineage(run_id, "idea_variant", variant_id, "transformed_by", "transformation_operator", operator_ids[operator])
            for kind, ids in (("opportunity", opportunity_ids), ("trend_score", score_ids), ("trend_discovery", discovery_ids), ("evidence", evidence_ids)):
                for target_id in ids:
                    self.repository.add_lineage(run_id, "idea_variant", variant_id, "derived_from", kind, target_id)
            variants.append(variant)
        if not variants:
            raise RuntimeError("idea expansion produced no valid variants")
        return {"variants": variants}, {"variants": len(variants), "operators": len({item["operator"] for item in variants})}, False

    def _idea_clustering(self, run_id: str, _config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        variants = json_safe(self.store.fetchall("SELECT * FROM laval_idea_variants WHERE run_id=%s ORDER BY created_at,id", (run_id,)))
        clusters: list[dict[str, Any]] = []
        for variant in variants:
            words = set(normalize_words(f"{variant['title'].get('en', '')} {variant['one_liner'].get('en', '')}"))
            match = None
            for cluster in clusters:
                if cluster["operator"] != variant["operator"]:
                    continue
                existing = cluster["words"]
                similarity = len(words & existing) / max(1, len(words | existing))
                if similarity >= .92:
                    match = cluster
                    break
            if match is None:
                cluster_key = hashlib.sha256(" ".join(sorted(words)).encode()).hexdigest()[:16]
                match = {"cluster_key": cluster_key, "representative_id": variant["id"], "idea_ids": [], "words": words, "operator": variant["operator"]}
                clusters.append(match)
            match["idea_ids"].append(variant["id"])
            representative = variant["id"] == match["representative_id"]
            self.store.execute("UPDATE laval_idea_variants SET cluster_key=%s,representative=%s WHERE id=%s RETURNING 1", (match["cluster_key"], representative, variant["id"]))
        artifact = {"clusters": [{key: value for key, value in cluster.items() if key != "words"} for cluster in clusters], "representative_ids": [cluster["representative_id"] for cluster in clusters]}
        return artifact, {"raw_variants": len(variants), "clusters": len(clusters), "duplicates": len(variants) - len(clusters)}, False

    def _idea_evaluation(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        variants = json_safe(self.store.fetchall("SELECT * FROM laval_idea_variants WHERE run_id=%s AND representative ORDER BY created_at,id", (run_id,)))
        packet = self.repository.stage(run_id, "SYNTHESIS_PACKET")["artifact"]
        context = ContextCompiler(config).build_evaluation_context(packet, variants)
        llm = self._llm(run_id, "IDEA_EVALUATION", "laval_idea_evaluation", "Independently score every supplied idea in fresh context. Return each exact idea ID once, normalized 0..1 dimensions, an overall score, strengths, critique, and fatal flaw. Do not generate new ideas.", context, "evaluations")
        evaluations = llm.get("evaluations") if llm else []
        by_id = {str(item.get("idea_id")): item for item in evaluations if isinstance(item, Mapping) and item.get("idea_id")}
        results = []
        for ordinal, variant in enumerate(variants):
            dimensions = {
                "owner_fit": min(1, .55 + .08 * len(variant.get("opportunity_ids") or [])),
                "differentiation": .82 if variant["operator"] in {"invert", "transfer", "resegment"} else .68,
                "opportunity_support": min(1, .4 + .18 * len(variant.get("opportunity_ids") or [])),
                "trend_support": min(1, .35 + .16 * (len(variant.get("trend_signal_ids") or []) + len(variant.get("trend_discovery_ids") or []))),
                "distribution_potential": .9 if variant["operator"] == "distribution_first" else .62,
                "novelty": .5 + (int(hashlib.sha256(str(variant["id"]).encode()).hexdigest()[:2], 16) / 510),
            }
            deterministic = idea_score(dimensions, config)
            provided = by_id.get(str(variant["id"])) or {}
            evaluator_score = clamp(provided.get("score", deterministic * .94 + .03))
            evaluator = {
                "score": evaluator_score,
                "dimensions": {key: clamp((provided.get("dimensions") or {}).get(key, dimensions[key])) for key in config.idea_weights},
                "strengths": str(provided.get("strengths") or "Evidence-backed lineage and an explicit transformation operator."),
                "critique": str(provided.get("critique") or "The core adoption and distribution assumptions still require a small falsification test."),
                "fatal_flaw": provided.get("fatal_flaw"),
            }
            final = round((deterministic + evaluator_score) / 2, 6)
            score_id = new_uuid7()
            self.store.execute(
                """INSERT INTO laval_idea_scores(
                       id,run_id,idea_id,deterministic,deterministic_score,evaluator,evaluator_score,final_score
                   ) VALUES(%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s) RETURNING 1""",
                (score_id, run_id, variant["id"], self.store.json(dimensions), deterministic, self.store.json(evaluator), evaluator_score, final),
            )
            self.repository.add_lineage(run_id, "idea_score", score_id, "evaluates", "idea_variant", str(variant["id"]))
            results.append({"score_id": score_id, "idea_id": variant["id"], "title": variant["title"], "deterministic": dimensions, "deterministic_score": deterministic, "evaluator": evaluator, "evaluator_score": evaluator_score, "final_score": final})
        results.sort(key=lambda item: (-item["final_score"], str(item["idea_id"])))
        return {"scores": results}, {"evaluated": len(results), "independent_evaluator_results": len(by_id)}, len(by_id) != len(results)

    def _final_shortlist(self, run_id: str, config: LavalConfig, _country: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
        rows = self.store.fetchall(
            """SELECT s.*,v.title,v.one_liner,v.mechanism,v.target_user,v.why_new,v.operator,
                      v.opportunity_ids,v.trend_signal_ids,v.trend_discovery_ids,v.evidence_ids
               FROM laval_idea_scores s JOIN laval_idea_variants v ON v.id=s.idea_id
               WHERE s.run_id=%s ORDER BY s.final_score DESC,s.idea_id""",
            (run_id,),
        )
        shortlist = []
        for rank, row in enumerate(rows[: config.shortlist], 1):
            finalist = rank <= config.finalists
            self.store.execute("UPDATE laval_idea_scores SET rank=%s,finalist=%s WHERE id=%s RETURNING 1", (rank, finalist, row["id"]))
            shortlist.append({**json_safe(row), "rank": rank, "finalist": finalist})
        graph = self._publish_finalist_hypotheses(run_id, shortlist)
        hypothesis_map = graph.get("hypotheses") or {}
        for item in shortlist:
            hypothesis_id = hypothesis_map.get(str(item["idea_id"]))
            if hypothesis_id:
                self.store.execute("UPDATE laval_idea_scores SET commander_hypothesis_id=%s WHERE idea_id=%s RETURNING 1", (hypothesis_id, item["idea_id"]))
                item["commander_hypothesis_id"] = hypothesis_id
        artifact = {"shortlist": shortlist, "finalists": [item for item in shortlist if item["finalist"]], "graph_sync": graph}
        return artifact, {"shortlist": len(shortlist), "finalists": sum(item["finalist"] for item in shortlist), "graph_hypotheses": len(hypothesis_map)}, bool(graph.get("error"))

    def _publish_finalist_hypotheses(self, run_id: str, shortlist: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        finalists = [item for item in shortlist if item.get("finalist")]
        if not finalists:
            return {"sources": {}, "hypotheses": {}}
        evidence_ids = list(dict.fromkeys(str(value) for item in finalists for value in item.get("evidence_ids", [])))
        evidence = self.store.fetchall(
            """SELECT * FROM laval_evidence
               WHERE run_id=%s AND id=ANY(%s::uuid[]) AND source_type<>'fixture'""",
            (run_id, evidence_ids),
        ) if evidence_ids else []
        pending = [item for item in evidence if item["commander_source_id"] is None]
        findings = [{"external_id": str(item["id"]), "title": item["source_title"], "source_uri": item["source_url"], "finding_summary": item["claim"] or item["excerpt"], "publisher": item["publisher"], "credibility": float(item["confidence"]), "research_type": "product_discovery"} for item in pending]
        by_id = {str(item["id"]): item for item in evidence}
        hypotheses = []
        for item in finalists:
            ids = [str(value) for value in item.get("evidence_ids", []) if str(value) in by_id]
            hypotheses.append({
                "external_id": str(item["idea_id"]),
                "claim": str((item.get("one_liner") or {}).get("en") or (item.get("title") or {}).get("en") or "Laval finalist"),
                "success_metric": "validated_demand_signal", "threshold": .1,
                "scope": f"idea_laval:{run_id}:finalist:{item['idea_id']}",
                "evidence_external_ids": [value for value in ids if by_id[value]["commander_source_id"] is None],
                "source_ids": [str(by_id[value]["commander_source_id"]) for value in ids if by_id[value]["commander_source_id"]],
                "attributes": {"research_type": "product_discovery", "owner_agent": "product.strategy", "knowledge_domain": "product.strategy", "idea_laval_run_id": run_id, "idea_laval_variant_id": str(item["idea_id"]), "rank": item["rank"]},
            })
        try:
            result = self.providers.research.record(findings, hypotheses)
            self.repository.link_commander_sources({str(key): str(value) for key, value in (result.get("sources") or {}).items()})
            return result
        except Exception as error:
            return {"sources": {}, "hypotheses": {}, "error": type(error).__name__, "message": str(error)[:500], "sink": self.providers.research.name}
