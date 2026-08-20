from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Protocol

from commander.ids import new_uuid7


class StructuredProvider(Protocol):
    def generate_structured(
        self, mode: str, system_prompt: str, input_payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> dict[str, Any]: ...


class MockLLMProvider:
    """Deterministic acceptance provider. It never performs a network call."""

    model_name = "mock-v1"

    def __init__(self, failures: list[Exception | dict[str, Any]] | None = None) -> None:
        self.failures = list(failures or [])
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.last_invocation: dict[str, Any] = {}

    def generate_structured(
        self, mode: str, system_prompt: str, input_payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.last_invocation = {"session_id": str(new_uuid7()), "session_mode": "fresh"}
        self.calls.append((mode, input_payload))
        if self.failures:
            result = self.failures.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        if mode == "laval_owner_dna":
            raw = str(input_payload.get("owner_idea") or "Owner idea")
            return {"owner_dna": {
                "problem": raw,
                "target_user": "People described by the owner idea",
                "core_mechanism": raw[:500],
                "core_emotion": "Motivation and accountability",
                "why_now": "Current demand must be validated with evidence",
                "must_preserve": [raw[:500]],
                "assumptions": ["Users repeat the behavior"],
                "unknowns": ["Willingness to pay"],
            }}
        if mode == "laval_query_plan":
            mechanism = str((input_payload.get("owner_dna") or {}).get("core_mechanism") or "product")
            return {"query_intents": [
                {
                    "family": family,
                    "base_query": f"{mechanism[:80]} {family} product",
                    "translations": [
                        {"language": str(language), "query": f"{mechanism[:60]} {family} {language}"}
                        for language in input_payload.get("languages") or []
                    ],
                }
                for family in input_payload.get("families") or []
                for _ in range(int(input_payload.get("queries_per_family") or 1))
            ]}
        if mode == "laval_competitor_dossier":
            competitor = input_payload.get("competitor") or {}
            evidence = input_payload.get("evidence") or []
            claims = [str(item.get("claim") or item.get("excerpt") or "") for item in evidence]
            evidence_ids = [str(item.get("id")) for item in evidence if item.get("id")]
            return {"dossier": {
                "competitor_id": str(competitor.get("id") or ""),
                "name": str(competitor.get("name") or "Competitor"),
                "url": str(competitor.get("url") or ""),
                "type": str(competitor.get("result_type") or "direct_product"),
                "country_presence": ["US"],
                "positioning": claims[:2] or ["Evidence-backed positioning"],
                "audiences": ["Target users"],
                "features": ["Core workflow"],
                "pricing": ["Pricing requires validation"],
                "distribution": ["Search and sharing"],
                "hooks": claims[:2] or ["Clear outcome"],
                "strengths": ["Existing discoverability"],
                "complaints": ["Users need a simpler workflow"],
                "gaps": ["A narrower evidence-backed workflow"],
                "keywords": ["accountability", "proof"],
                "evidence_ids": evidence_ids,
                "confidence": .72,
            }}
        if mode == "laval_opportunity_matrix":
            return {"opportunities": [
                {
                    "statement": f"Users need a better supported alternative to {dossier.get('name') or 'the existing product'}.",
                    "pain": str((dossier.get("complaints") or ["Unmet need"])[0]),
                    "affected_segment": str((dossier.get("audiences") or ["Target users"])[0]),
                    "competitor_ids": [str(dossier.get("competitor_id"))],
                    "countries": list(dossier.get("country_presence") or []),
                    "evidence_ids": list(dossier.get("evidence_ids") or []),
                    "scores": {
                        "frequency": .6, "severity": .65, "coverage_gap": .7,
                        "cross_market": .5, "owner_relevance": .8, "confidence": .7,
                    },
                }
                for dossier in input_payload.get("dossiers") or []
                if dossier.get("competitor_id") and dossier.get("evidence_ids")
            ]}
        if mode == "laval_market_signal_relevance":
            return {"classifications": [
                {
                    "opportunity_id": str(item.get("opportunity_id") or ""),
                    "evidence_id": str(item.get("evidence_id") or ""),
                    "relevant": True,
                }
                for item in input_payload.get("pairs") or []
            ]}
        if mode == "laval_idea_expansion":
            opportunities = input_payload.get("opportunities") or []
            trends = input_payload.get("trend_scores") or []
            discoveries = input_payload.get("trend_discoveries") or []
            market = input_payload.get("market_signal_scores") or []
            evidence_ids = list(input_payload.get("selected_evidence_ids") or [])
            count = int((input_payload.get("generation_requirements") or {}).get("variants_per_operator") or 3)
            operators = input_payload.get("transformation_operators") or []
            variants = []
            for operator in operators:
                for ordinal in range(count):
                    opportunity = opportunities[(len(variants)) % len(opportunities)] if opportunities else {}
                    angles = ("onboarding", "retention", "referral", "pricing", "community", "proof")
                    angle = angles[ordinal % len(angles)]
                    title = f"{str(operator).replace('_', ' ').title()} {angle} concept"
                    variants.append({
                        "title": {"en": title, "uk": f"Концепція {ordinal + 1}: {operator}"},
                        "one_liner": {"en": f"An evidence-backed product concept focused on {angle}.", "uk": f"Продуктова концепція на основі доказів: {angle}."},
                        "mechanism": {"en": f"Apply {operator} to the validated opportunity.", "uk": f"Застосувати {operator} до перевіреної можливості."},
                        "target_user": {"en": str(opportunity.get("affected_segment") or "Target users"), "uk": "Цільові користувачі"},
                        "why_new": {"en": "It combines a measured gap with a distinct operator.", "uk": "Поєднує виміряну прогалину з окремим оператором."},
                        "operator": str(operator),
                        "opportunity_ids": [str(opportunity["id"])] if opportunity.get("id") else [],
                        "trend_signal_ids": [str(trends[0]["id"])] if trends else [],
                        "trend_discovery_ids": [str(discoveries[0]["id"])] if discoveries else [],
                        "market_signal_ids": [str(market[0]["id"])] if market else [],
                        "evidence_ids": evidence_ids[:8],
                    })
            return {"variants": variants}
        if mode == "laval_idea_evaluation":
            return {"evaluations": [
                {
                    "idea_id": str(item["id"]),
                    "score": .7,
                    "dimensions": {
                        "owner_fit": .75, "differentiation": .7, "opportunity_support": .75,
                        "trend_support": .6, "distribution_potential": .68, "novelty": .65,
                    },
                    "strengths": "Clear evidence lineage and a testable mechanism.",
                    "critique": "Distribution and willingness to pay still require direct testing.",
                    "fatal_flaw": None,
                }
                for item in input_payload.get("variants") or []
            ]}
        if mode == "laval_youtube_observation":
            kinds = (
                "workaround", "challenge_format", "motivation", "repeated_question",
                "complaint", "transformation_narrative", "audience_vocabulary",
                "creator_distribution", "substitute",
            )
            videos = input_payload.get("videos") or []
            return {"observations": [
                {
                    "observation_type": kinds[index % len(kinds)],
                    "statement": f"Independent creators repeatedly show behavior pattern {index + 1}.",
                    "video_ids": [str(video.get("id"))],
                    "evidence_ids": [str(video.get("evidence_id"))],
                    "confidence": .68,
                }
                for index, video in enumerate(videos[:12])
                if video.get("id") and video.get("evidence_id")
            ]}
        if mode == "laval_mechanism_extraction":
            variants = input_payload.get("variants") or []
            observations = input_payload.get("behavior_observations") or []
            mechanism_types = ("value", "behavior", "trust", "retention", "distribution", "proof")
            mechanisms = []
            for index, mechanism_type in enumerate(mechanism_types):
                parents = [item for offset, item in enumerate(variants) if offset % len(mechanism_types) == index]
                selected = parents or variants[:1]
                evidence_ids = list(dict.fromkeys(
                    str(value) for item in selected for value in item.get("evidence_ids") or []
                ))
                mechanisms.append({
                    "name": {"en": f"{mechanism_type.title()} loop", "uk": f"Механізм: {mechanism_type}"},
                    "description": {"en": f"Reusable {mechanism_type} mechanism extracted across candidate variants.", "uk": f"Повторно використовуваний механізм {mechanism_type}."},
                    "mechanism_type": mechanism_type,
                    "source_variant_ids": [str(item["id"]) for item in selected if item.get("id")],
                    "opportunity_ids": list(dict.fromkeys(str(value) for item in selected for value in item.get("opportunity_ids") or [])),
                    "market_signal_ids": list(dict.fromkeys(str(value) for item in selected for value in item.get("market_signal_ids") or [])),
                    "behavior_observation_ids": [str(item["id"]) for item in observations[index::len(mechanism_types)] if item.get("id")],
                    "evidence_ids": evidence_ids,
                })
            return {"mechanisms": mechanisms}
        if mode == "laval_thesis_synthesis":
            mechanisms = input_payload.get("mechanisms") or []
            owner = input_payload.get("owner_dna") or {}
            groups = [mechanisms[:5], mechanisms[1:6], mechanisms[-5:]]
            theses = []
            for index, group in enumerate(groups):
                group = list({str(item.get("id")): item for item in group if item.get("id")}.values())
                if len(group) < 3:
                    continue
                evidence = list(dict.fromkeys(str(value) for item in group for value in item.get("evidence_ids") or []))
                theses.append({
                    "title": {"en": f"Evidence loop {index + 1}", "uk": f"Доказовий цикл {index + 1}"},
                    "target_user": {"en": str(owner.get("target_user") or "Target users"), "uk": "Цільові користувачі"},
                    "problem": {"en": str(owner.get("problem") or "Unmet behavior"), "uk": "Непідтверджена потреба"},
                    "loop_steps": [
                        {"en": value, "uk": f"Крок: {value}"}
                        for value in ("Arrive", "Commit", "Act", "Create proof", "Share result", "Return")
                    ],
                    "value_moment": {"en": "The user produces credible proof of progress.", "uk": "Користувач створює достовірний доказ прогресу."},
                    "zero_audience_behavior": {"en": "The commitment remains useful as a private proof log.", "uk": "Зобов’язання корисне як приватний журнал доказів."},
                    "substitutes": [{"en": "Spreadsheets and accountability groups", "uk": "Таблиці та групи підзвітності"}],
                    "dangerous_assumptions": [
                        {"id": f"assumption-{index + 1}-behavior", "statement": {"en": "Users repeat the core behavior.", "uk": "Користувачі повторюють основну поведінку."}, "severity": "high"},
                        {"id": f"assumption-{index + 1}-sharing", "statement": {"en": "Proof creates qualified sharing.", "uk": "Доказ створює релевантне поширення."}, "severity": "medium"},
                    ],
                    "success_criterion": {"metric": "validated_demand_signal", "operator": ">=", "threshold": .1, "sample_target": 10},
                    "mechanism_ids": [str(item["id"]) for item in group],
                    "evidence_ids": evidence,
                })
            return {"theses": theses[:3]}
        if mode == "laval_thesis_falsification":
            return {"reports": [
                {
                    "thesis_id": str(thesis["id"]),
                    "verdict": "survives" if index == 0 else "weak",
                    "risks": [
                        {
                            "assumption_id": str(assumption["id"]),
                            "severity": str(assumption["severity"]),
                            "supported": index == 0,
                            "objection": "Behavioral demand is not yet proven by a real market probe.",
                            "counterargument": "Independent observations provide enough support to justify a bounded probe.",
                            "evidence_ids": list(thesis.get("evidence_ids") or [])[:3],
                            "mechanism_ids": list(thesis.get("mechanism_ids") or [])[:3],
                            "fatal": False,
                        }
                        for assumption in thesis.get("dangerous_assumptions") or []
                    ],
                    "fatal_objection": None,
                }
                for index, thesis in enumerate(input_payload.get("theses") or [])
            ]}
        if mode == "evaluate":
            evaluations = []
            evaluator = input_payload["context"]["code"]
            bias = int(evaluator[1:])
            for idea in input_payload["ideas"]:
                score = 55 + ((int(idea["id"]) * 3 + bias) % 35)
                evaluations.append({
                    "idea_id": idea["id"], "score": score,
                    "criteria": {"three_year_exit_potential": score * .25, "remote_operability_autonomy": score * .25,
                                 "distribution": score * .15, "scalability_economics": score * .15,
                                 "defensibility": score * .10, "speed_capital_efficiency": score * .10},
                    "strengths": "Clear leverage and validation path.",
                    "critique": "Distribution assumptions need direct testing.", "fatal_flaw": None,
                })
            return {"evaluations": evaluations}
        context = input_payload["context"]["code"]
        if mode == "normalize_human":
            raw = str(input_payload.get("raw_text", "")).strip()
            title = next((line.strip("# ") for line in raw.splitlines() if line.strip()), "Owner idea")[:160]
            return {
                "title": {"en": title, "uk": title},
                "one_liner": {"en": raw[:1000], "uk": raw[:1000]},
                "details": {
                    "customer": {"en": "Defined by the owner submission and to be validated", "uk": "Визначено заявкою власника; потребує перевірки"},
                    "problem": {"en": raw, "uk": raw},
                    "product": {"en": raw, "uk": raw},
                    "business_model": {"en": "To be validated", "uk": "Потребує перевірки"},
                    "distribution": {"en": "To be validated", "uk": "Потребує перевірки"},
                    "automation": {"en": "To be validated", "uk": "Потребує перевірки"},
                    "three_year_exit_logic": {"en": "To be validated against the mission", "uk": "Потребує перевірки відносно місії"},
                    "key_risks": {"en": ["Owner concept requires structured validation"], "uk": ["Концепція власника потребує структурованої перевірки"]},
                    "first_validation_test": {"en": "Test the central assumption with five target users.", "uk": "Перевірити центральне припущення з п’ятьма цільовими користувачами."},
                },
                "parent_ids": [],
                "lineage_note": "Owner submission normalized without changing the concept",
            }
        ordinal = len([call for call in self.calls if call[0] in {"generate", "evolve"}])
        parents = []
        if mode == "evolve" and input_payload.get("mode") == "exploit":
            parents = [input_payload["current_generation"][ordinal % len(input_payload["current_generation"])]["id"]]
        return {"title": {"en": f"{context} Candidate {ordinal}", "uk": f"{context} Кандидат {ordinal}"},
                "one_liner": {"en": "Automated software for a costly recurring workflow.", "uk": "Автоматизоване ПЗ для дорогого повторюваного процесу."},
                "details": {
                    "customer": {"en": "Global operating teams", "uk": "Операційні команди в усьому світі"},
                    "problem": {"en": "A costly recurring manual workflow", "uk": "Дорогий повторюваний ручний процес"},
                    "product": {"en": "A self-serve automation platform", "uk": "Self-service платформа автоматизації"},
                    "business_model": {"en": "Recurring subscription and usage fees", "uk": "Підписка та оплата за використання"},
                    "distribution": {"en": "Embedded integrations and partner channels", "uk": "Вбудовані інтеграції та партнерські канали"},
                    "automation": {"en": "Software delivery and support automation", "uk": "Програмна доставка та автоматизація підтримки"},
                    "three_year_exit_logic": {"en": "Recurring revenue, workflow data, and distribution can support a strategic acquisition within 36 months.", "uk": "Повторювана виручка, workflow-дані та дистрибуція можуть обґрунтувати стратегічне придбання за 36 місяців."},
                    "key_risks": {"en": ["Adoption", "Incumbent response"], "uk": ["Прийняття ринком", "Відповідь чинних гравців"]},
                    "first_validation_test": {"en": "Pre-sell a narrow workflow to five teams.", "uk": "Попередньо продати вузький workflow п’ятьом командам."}},
                "parent_ids": parents, "lineage_note": "Mocked deterministic candidate"}


class OpenAIProvider:
    """Optional production adapter; acceptance tests use ``MockLLMProvider`` only."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key: raise RuntimeError("OPENAI_API_KEY is required for LLM_PROVIDER=openai")
        from openai import OpenAI
        self.client, self.model_name = OpenAI(api_key=api_key), model

    def generate_structured(
        self, mode: str, system_prompt: str, input_payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": system_prompt + " Return one JSON object only."},
                      {"role": "user", "content": json.dumps(input_payload, ensure_ascii=False, default=str)}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        self.last_invocation = {
            "session_id": str(response.id),
            "session_mode": "fresh",
            "conversation_reused": False,
        }
        if not content: raise RuntimeError("provider returned an empty response")
        result = json.loads(content)
        if not isinstance(result, dict): raise ValueError("provider response must be a JSON object")
        return result


class BridgeProvider:
    """Use the established authenticated Codex worker through its internal API."""

    def __init__(self, url: str, token: str, model: str = "codex-cli-default", timeout_seconds: int = 360) -> None:
        if not url or not token:
            raise RuntimeError("LLM_BRIDGE_URL and TELEGRAM_BOT_TOKEN are required for bridge mode")
        self.url = url.rstrip("/")
        self.token = token
        self.model_name = model or "codex-cli-default"
        self.timeout_seconds = timeout_seconds
        self.last_invocation: dict[str, Any] = {}
        self._request_metadata: dict[str, str] = {}

    def prepare_invocation(self, prompt_template_version: str, context_hash: str) -> None:
        self._request_metadata = {
            "prompt_template_version": prompt_template_version,
            "context_hash": context_hash,
        }

    def capabilities(self) -> dict[str, Any]:
        payload = self._request(
            f"{self.url}/capabilities",
            None,
            {"X-PTW-Bridge-Token": self.token},
            timeout_seconds=5,
        )
        modes = payload.get("laval_modes")
        max_request_bytes = payload.get("max_request_bytes")
        if (
            not isinstance(modes, list)
            or not all(isinstance(mode, str) for mode in modes)
            or not isinstance(max_request_bytes, int)
            or max_request_bytes < 1
        ):
            raise ValueError("LLM bridge returned invalid capabilities")
        return {
            "laval_modes": sorted(set(modes)),
            "max_request_bytes": max_request_bytes,
        }

    def generate_structured(
        self, mode: str, system_prompt: str, input_payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> dict[str, Any]:
        headers = {"X-PTW-Bridge-Token": self.token}
        request = {
            "mode": mode,
            "system_prompt": system_prompt,
            "input_payload": input_payload,
            "output_schema": output_schema,
            **self._request_metadata,
        }
        if self.model_name != "codex-cli-default":
            request["model"] = self.model_name
        request_id = int(self._request(self.url, request, headers)["request_id"])
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            payload = self._request(f"{self.url}/{request_id}", None, headers)
            if payload["status"] == "completed":
                result = payload.get("result") or {}
                self.last_invocation = dict(result.get("invocation") or {}) if isinstance(result, dict) else {}
                body = result.get("response") if isinstance(result, dict) else None
                decoded = json.loads(body) if isinstance(body, str) else body
                if not isinstance(decoded, dict):
                    raise ValueError("LLM bridge response must contain one JSON object")
                return decoded
            if payload["status"] in {"failed", "cancelled"}:
                raise RuntimeError(f"LLM bridge job {request_id} {payload['status']}")
            time.sleep(1)
        raise TimeoutError(f"LLM bridge job {request_id} timed out")

    @staticmethod
    def _request(
        url: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
        *,
        timeout_seconds: int = 30,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, default=str).encode()
        request = urllib.request.Request(
            url, data=body, headers={**headers, "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                result = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raw = error.read(4097)[:4096]
            detail = "request rejected"
            try:
                decoded = json.loads(raw.decode("utf-8", errors="replace"))
                if isinstance(decoded, dict) and isinstance(decoded.get("detail"), str):
                    detail = decoded["detail"]
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            detail = re.sub(
                r"(?i)(token|password|secret|api[_-]?key|authorization)(\s*[:=]\s*)(\S+)",
                r"\1\2[REDACTED]",
                detail[:1000],
            )
            raise RuntimeError(f"LLM bridge HTTP {error.code}: {detail}") from error
        if not isinstance(result, dict):
            raise ValueError("LLM bridge returned invalid JSON")
        return result
