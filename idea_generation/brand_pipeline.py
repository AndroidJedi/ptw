"""Restartable Branding v1 orchestration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from commander.ids import new_uuid7

from .brand_domain import BRAND_STAGES, evaluate_direction, normalize_direction, public_https_url, stable_hash
from .brand_kit import assemble_brand_kit
from .brand_providers import BrandProvider, CommanderBrandBridge, GeneratedLogo
from .brand_repository import BrandRepository
from .laval_providers import YouTubeObservationProvider, WebPageProvider


class BrandRunPaused(RuntimeError):
    pass


class BrandPipeline:
    def __init__(
        self,
        repository: BrandRepository,
        provider: BrandProvider,
        web: WebPageProvider,
        youtube: YouTubeObservationProvider,
        bridge: CommanderBrandBridge,
        asset_directory: Path,
    ) -> None:
        self.repository = repository
        self.store = repository.store
        self.provider = provider
        self.web = web
        self.youtube = youtube
        self.bridge = bridge
        self.asset_directory = asset_directory

    def _ensure_active(self, run_id: str) -> None:
        if self.repository.run(run_id)["status"] != "running":
            raise BrandRunPaused("Branding run is paused")

    @staticmethod
    def _model_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        """Keep the durable snapshot whole while bounding provider context."""

        def bounded(value: Any, limit: int = 1000) -> Any:
            if isinstance(value, str):
                return value[:limit]
            if isinstance(value, list):
                return [bounded(item, limit) for item in value]
            if isinstance(value, Mapping):
                return {str(key): bounded(item, limit) for key, item in value.items()}
            return value

        evidence = []
        for item in list(snapshot.get("evidence") or [])[:80]:
            evidence.append({
                "id": item.get("id"),
                "source_type": item.get("source_type"),
                "source_url": item.get("source_url"),
                "source_title": bounded(item.get("source_title"), 300),
                "publisher": bounded(item.get("publisher"), 200),
                "claim": bounded(item.get("claim"), 600),
                "excerpt": bounded(item.get("excerpt"), 800),
                "confidence": item.get("confidence"),
                "commander_source_id": item.get("commander_source_id"),
            })
        return {
            "idea_run_id": snapshot.get("idea_run_id"),
            "owner_idea": bounded(snapshot.get("owner_idea"), 4000),
            "theses": bounded(list(snapshot.get("theses") or []), 1200),
            "mechanisms": bounded(list(snapshot.get("mechanisms") or []), 1000),
            "competitors": bounded(list(snapshot.get("competitors") or [])[:50], 800),
            "evidence": evidence,
            "behavior_observations": bounded(
                list(snapshot.get("behavior_observations") or [])[:40], 800
            ),
            "quality": snapshot.get("quality") or {},
            "recommended_thesis_id": snapshot.get("recommended_thesis_id"),
        }

    def _provider_task(
        self, run_id: str, stage: str, item_key: str,
        payload: Mapping[str, Any], operation: Any, *,
        provider_name: str | None = None,
        cost_metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        task_provider = provider_name or self.provider.name
        request_hash = stable_hash(stage, item_key, payload)
        existing = self.store.fetchone(
            "SELECT * FROM brand_provider_tasks WHERE run_id=%s AND stage=%s AND item_key=%s",
            (run_id, stage, item_key),
        )
        if existing and existing["status"] == "completed":
            cached = existing.get("response") or {}
            if cached.get("kind") == "json" and isinstance(cached.get("value"), (dict, list)):
                return cached["value"]
            if cached.get("kind") == "logo":
                path = Path(str(cached.get("path") or ""))
                content = path.read_bytes() if path.is_file() else b""
                if content and hashlib.sha256(content).hexdigest() == cached.get("digest"):
                    return GeneratedLogo(
                        content=content,
                        requested_model=str(cached.get("requested_model") or ""),
                        resolved_model=str(cached.get("resolved_model") or ""),
                        prompt=str(cached.get("prompt") or ""),
                        width=int(cached.get("width") or 0),
                        height=int(cached.get("height") or 0),
                        request_id=str(cached.get("request_id") or ""),
                    )
            raise RuntimeError("completed provider task has no valid persisted response")
        if existing and existing["status"] == "running":
            self.store.execute(
                "UPDATE brand_provider_tasks SET status='unknown',updated_at=NOW() WHERE id=%s RETURNING 1",
                (existing["id"],),
            )
            raise RuntimeError("provider result is unknown after restart; use explicit stage rerun")
        if existing and existing["status"] == "unknown":
            raise RuntimeError("provider result is unknown after restart; use explicit stage rerun")
        task_id = str(existing["id"]) if existing else new_uuid7()
        with self.store.transaction() as connection:
            if existing:
                connection.execute(
                    """UPDATE brand_provider_tasks SET status='running',request_count=request_count+1,
                              provider=%s,request_hash=%s,response=NULL,response_digest=NULL,
                              remote_request_id=NULL,error_text=NULL,updated_at=NOW()
                        WHERE id=%s""",
                    (task_provider, request_hash, task_id),
                )
            else:
                connection.execute(
                    """INSERT INTO brand_provider_tasks(
                           id,run_id,stage,item_key,provider,status,request_hash,request_count
                       ) VALUES(%s,%s,%s,%s,%s,'running',%s,1)""",
                    (task_id, run_id, stage, item_key, task_provider, request_hash),
                )
        try:
            result = operation()
            consume_usage = (
                getattr(self.provider, "consume_usage", None)
                if task_provider == self.provider.name else None
            )
            usage = dict(consume_usage() if callable(consume_usage) else {})
            provider_cost_metadata = (
                getattr(self.provider, "cost_metadata", None)
                if task_provider == self.provider.name else None
            )
            recorded_cost_metadata = dict(
                cost_metadata
                or (provider_cost_metadata() if callable(provider_cost_metadata) else {})
                or {"monetary_cost_status": "provider_not_reported"}
            )
            if isinstance(result, GeneratedLogo):
                content = result.content
                response_digest = hashlib.sha256(content).hexdigest()
                cache_directory = self.asset_directory / run_id / "provider-cache"
                cache_directory.mkdir(parents=True, exist_ok=True)
                cache_path = cache_directory / f"{request_hash}.png"
                if not cache_path.exists():
                    cache_path.write_bytes(content)
                cached_response = {
                    "kind": "logo", "path": str(cache_path), "digest": response_digest,
                    "requested_model": result.requested_model,
                    "resolved_model": result.resolved_model,
                    "prompt": result.prompt, "width": result.width, "height": result.height,
                    "request_id": result.request_id,
                }
            else:
                encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str).encode()
                response_digest = hashlib.sha256(encoded).hexdigest()
                cached_response = {"kind": "json", "value": result}
            remote_id = str(getattr(result, "request_id", "") or "")
            self.store.execute(
                """UPDATE brand_provider_tasks SET status='completed',response_digest=%s,response=%s::jsonb,
                          remote_request_id=NULLIF(%s,''),input_tokens=%s,output_tokens=%s,
                          updated_at=NOW() WHERE id=%s RETURNING 1""",
                (
                    response_digest, self.store.json(cached_response), remote_id,
                    int(usage.get("input_tokens") or 0),
                    int(usage.get("output_tokens") or 0), task_id,
                ),
            )
            self.repository.record_cost(
                run_id, stage, task_provider, item_key,
                input_tokens=int(usage.get("input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
                metadata=recorded_cost_metadata,
            )
            return result
        except Exception as error:
            self.store.execute(
                "UPDATE brand_provider_tasks SET status='failed',error_text=%s,updated_at=NOW() WHERE id=%s RETURNING 1",
                (f"{type(error).__name__}: {str(error)[:800]}", task_id),
            )
            self.repository.record_cost(
                run_id, stage, task_provider, item_key,
                metadata={"failed": True, "error": type(error).__name__, **dict(cost_metadata or {})},
            )
            raise

    @staticmethod
    def _validate_structured(
        stage: str, result: dict[str, Any], payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        allowed_evidence = set(str(item) for item in payload.get("evidence_ids") or [])
        if stage == "REFERENCE_PLAN":
            if not isinstance(result.get("competitors"), list) or len(result["competitors"]) > 5:
                raise ValueError("reference plan must contain at most five competitors")
            if not isinstance(result.get("youtube_queries"), list) or len(result["youtube_queries"]) > 5:
                raise ValueError("reference plan must contain at most five YouTube queries")
            competitors = []
            for item in result["competitors"]:
                if not isinstance(item, Mapping) or not str(item.get("name") or "").strip():
                    raise ValueError("every reference-plan competitor needs a name and URL")
                competitors.append({
                    "name": str(item["name"])[:300],
                    "url": public_https_url(str(item.get("url") or ""), resolve=False),
                })
            queries = [str(item).strip()[:300] for item in result["youtube_queries"]]
            if any(not item for item in queries):
                raise ValueError("YouTube design queries may not be empty")
            result = {**result, "competitors": competitors, "youtube_queries": queries}
        elif stage == "DESIGN_PRINCIPLES":
            if not isinstance(result.get("principles"), list) or not 3 <= len(result["principles"]) <= 12:
                raise ValueError("design principles must contain 3-12 evidence-backed items")
            for principle in result["principles"]:
                if not isinstance(principle, Mapping):
                    raise ValueError("every design principle must be an object")
                evidence = [str(item) for item in principle.get("evidence_ids") or []]
                if not evidence or any(item not in allowed_evidence for item in evidence):
                    raise ValueError("every design principle must cite supplied evidence IDs")
        elif stage == "BRAND_BRIEF":
            if not isinstance(result.get("brief"), Mapping):
                raise ValueError("brand brief must be an object")
        elif stage == "DIRECTION_SYNTHESIS":
            candidates = result.get("name_candidates")
            raw_directions = result.get("directions")
            if not isinstance(candidates, list) or len(candidates) != 12:
                raise ValueError("direction synthesis must return twelve name candidates")
            if not isinstance(raw_directions, list) or len(raw_directions) != 3:
                raise ValueError("direction synthesis must return exactly three directions")
            normalized = [
                normalize_direction(item, index)
                for index, item in enumerate(raw_directions, 1)
                if isinstance(item, Mapping)
            ]
            if len(normalized) != 3 or len({item["name"].casefold() for item in normalized}) != 3:
                raise ValueError("brand directions must be three distinct valid objects")
            if any(
                any(evidence_id not in allowed_evidence for evidence_id in item["evidence_ids"])
                for item in normalized
            ):
                raise ValueError("brand directions may cite only supplied evidence IDs")
            result = {
                **result,
                "name_candidates": [str(item)[:100] for item in candidates],
                "directions": normalized,
            }
        return result

    def _structured(self, run_id: str, stage: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        errors = []
        stage_attempt = int(self.repository.stage(run_id, stage)["attempt"])
        for attempt in (1, 2):
            try:
                result = self._provider_task(
                    run_id, stage, f"structured:{stage_attempt}:{attempt}", payload,
                    lambda: self.provider.structured(stage, payload),
                )
                if not isinstance(result, dict):
                    raise ValueError("structured Branding output must be an object")
                return self._validate_structured(stage, result, payload)
            except Exception as error:
                errors.append(error)
        raise RuntimeError(f"{stage} failed strict output validation after one retry: {type(errors[-1]).__name__}: {str(errors[-1])[:600]}") from errors[-1]

    def run(self, run_id: str, *, start_stage: str | None = None) -> None:
        initial = self.repository.run(run_id)
        if initial["status"] in {"awaiting_review", "completed", "cancelled"}:
            return
        stages = self.repository.stages(run_id)
        start_index = BRAND_STAGES.index(start_stage) if start_stage else 1
        for item in stages:
            stage = str(item["stage"])
            if BRAND_STAGES.index(stage) < start_index or item["status"] == "completed":
                continue
            if stage in {"OWNER_REVIEW", "KIT_ASSEMBLY"}:
                self.repository.await_review(run_id)
                return
            self._ensure_active(run_id)
            payload = self._context(run_id, stage)
            digest = stable_hash(payload)
            self.repository.prepare_stage(
                run_id, stage, digest,
                provider=self.provider.name if stage not in {"REFERENCE_COLLECTION", "DIRECTION_EVALUATION"} else (self.web.name if stage == "REFERENCE_COLLECTION" else "code"),
                model=self.provider.text_model if stage not in {"REFERENCE_COLLECTION", "DIRECTION_EVALUATION", "LOGO_GENERATION"} else (self.provider.image_model if stage == "LOGO_GENERATION" else "deterministic"),
            )
            try:
                artifact, metrics = self._execute(run_id, stage, payload)
                self._ensure_active(run_id)
                self.repository.complete_stage(run_id, stage, artifact, metrics)
            except BrandRunPaused:
                return
            except Exception as error:
                self.repository.fail_stage(run_id, stage, error)
                return
        self.repository.await_review(run_id)

    def _context(self, run_id: str, stage: str) -> dict[str, Any]:
        run = self.repository.run(run_id)
        artifacts = {str(item["stage"]): item.get("artifact") for item in self.repository.stages(run_id)}
        complete_snapshot = run["source_snapshot"]
        snapshot = self._model_snapshot(complete_snapshot)
        evidence_ids = [str(item["id"]) for item in complete_snapshot.get("evidence") or []]
        evidence_ids.extend(str(item["id"]) for item in self.repository.sources(run_id))
        base = {
            "snapshot": snapshot,
            "constraints": run.get("constraints_text") or "",
            "reference_urls": run.get("reference_urls") or [],
            "manual_transcripts": run.get("manual_transcripts") or [],
            "evidence_ids": list(dict.fromkeys(evidence_ids)),
        }
        if stage == "REFERENCE_PLAN":
            return {**base, "competitors": snapshot.get("competitors") or []}
        if stage == "REFERENCE_COLLECTION":
            return {**base, "plan": artifacts.get("REFERENCE_PLAN") or {}}
        if stage == "DESIGN_PRINCIPLES":
            return {**base, "collection": artifacts.get("REFERENCE_COLLECTION") or {}}
        if stage == "BRAND_BRIEF":
            return {**base, "principles": artifacts.get("DESIGN_PRINCIPLES") or {}}
        if stage == "DIRECTION_SYNTHESIS":
            return {**base, "principles": artifacts.get("DESIGN_PRINCIPLES") or {}, "brief": artifacts.get("BRAND_BRIEF") or {}}
        if stage in {"DIRECTION_EVALUATION", "LOGO_GENERATION"}:
            return {**base, "directions": self.repository.directions(run_id)}
        return base

    def _execute(self, run_id: str, stage: str, payload: Mapping[str, Any]) -> tuple[Any, dict[str, Any]]:
        if stage == "REFERENCE_PLAN":
            result = self._structured(run_id, stage, payload)
            return result, {"competitors": len(result.get("competitors") or []), "youtube_queries": len(result.get("youtube_queries") or [])}
        if stage == "REFERENCE_COLLECTION":
            return self._collect_references(run_id, payload)
        if stage in {"DESIGN_PRINCIPLES", "BRAND_BRIEF"}:
            result = self._structured(run_id, stage, payload)
            return result, {"items": len(result.get("principles") or []) if stage == "DESIGN_PRINCIPLES" else 1}
        if stage == "DIRECTION_SYNTHESIS":
            result = self._structured(run_id, stage, payload)
            candidates = result["name_candidates"]
            directions = result["directions"]
            self.repository.replace_directions(run_id, directions)
            return {"name_candidates": candidates, "directions": directions}, {"name_candidates": 12, "directions": 3}
        if stage == "DIRECTION_EVALUATION":
            run = self.repository.run(run_id)
            snapshot = run["source_snapshot"]
            competitors = [str(item.get("name") or "") for item in snapshot.get("competitors") or []]
            existing = [str(item["name"]) for item in self.store.fetchall("SELECT name FROM brand_directions WHERE run_id<>%s", (run_id,))]
            evaluations = {}
            for item in self.repository.directions(run_id):
                evaluation = evaluate_direction(
                    item["manifest"], competitors, existing,
                    allowed_evidence_ids=payload.get("evidence_ids") or [],
                    case_content=snapshot,
                )
                evaluations[str(item["name"])] = evaluation
            if not all(item["passed"] for item in evaluations.values()):
                raise ValueError("one or more brand directions failed deterministic safety evaluation")
            self.repository.save_evaluations(run_id, evaluations)
            return {"directions": evaluations}, {"passed": 3, "failed": 0}
        if stage == "LOGO_GENERATION":
            return self._generate_logos(run_id)
        raise ValueError(f"unsupported Branding stage {stage}")

    def _collect_references(self, run_id: str, payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        plan = payload.get("plan") or {}
        collected: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        competitors = list(plan.get("competitors") or payload.get("snapshot", {}).get("competitors") or [])[:5]
        for competitor in competitors:
            self._ensure_active(run_id)
            raw_url = str(competitor.get("url") or "")
            if not raw_url:
                continue
            parsed = urlsplit(raw_url)
            origin = urlunsplit(("https", parsed.netloc, "", "", "")).rstrip("/")
            for url in (origin, f"{origin}/features", f"{origin}/pricing"):
                self._ensure_active(run_id)
                try:
                    requested_url = public_https_url(
                        url, resolve=self.web.name != "fixture_public_pages"
                    )
                    page = self._provider_task(
                        run_id, "REFERENCE_COLLECTION", f"page:{stable_hash(requested_url)}",
                        {"url": requested_url}, lambda: self.web.fetch(requested_url),
                        provider_name=self.web.name,
                        cost_metadata={"monetary_cost": 0, "public_https": True},
                    )
                    source_id = self.repository.add_source(
                        run_id, "competitor_page", str(page["url"]),
                        f"{competitor.get('name') or parsed.netloc} public design page",
                        str(page.get("text") or ""),
                        {"signals": page.get("signals") or {}, "truncated": bool(page.get("truncated")), "competitor_id": competitor.get("id")},
                    )
                    collected.append({"id": source_id, "type": "competitor_page", "url": page["url"], "signals": page.get("signals") or {}})
                except Exception as error:
                    failures.append({"url": url, "error": type(error).__name__})
        for url in payload.get("reference_urls") or []:
            self._ensure_active(run_id)
            try:
                requested_url = public_https_url(
                    str(url), resolve=self.web.name != "fixture_public_pages"
                )
                page = self._provider_task(
                    run_id, "REFERENCE_COLLECTION", f"page:{stable_hash(requested_url)}",
                    {"url": requested_url}, lambda: self.web.fetch(requested_url),
                    provider_name=self.web.name,
                    cost_metadata={"monetary_cost": 0, "public_https": True},
                )
                source_id = self.repository.add_source(run_id, "manual_reference", str(page["url"]), "Owner reference page", str(page.get("text") or ""), {"signals": page.get("signals") or {}, "owner_supplied": True})
                collected.append({"id": source_id, "type": "manual_reference", "url": page["url"], "signals": page.get("signals") or {}})
            except Exception as error:
                failures.append({"url": str(url), "error": type(error).__name__})
        for transcript in payload.get("manual_transcripts") or []:
            self._ensure_active(run_id)
            source_id = self.repository.add_source(run_id, "manual_transcript", str(transcript["video_url"]), str(transcript["title"]), str(transcript["transcript"]), {"owner_supplied": True, "verified": False, "caption_scraped": False})
            collected.append({"id": source_id, "type": "manual_transcript", "url": transcript["video_url"], "unverified": True})

        videos_remaining = 12
        for query in list(plan.get("youtube_queries") or [])[:5]:
            self._ensure_active(run_id)
            if videos_remaining <= 0:
                break
            try:
                search_payload = {
                    "query": str(query), "country": "US", "language": "en",
                    "limit": min(4, videos_remaining),
                }
                videos = self._provider_task(
                    run_id, "REFERENCE_COLLECTION",
                    f"youtube-search:{stable_hash(search_payload)}", search_payload,
                    lambda: self.youtube.search(**search_payload),
                    provider_name=self.youtube.name,
                    cost_metadata={"monetary_cost": 0, "official_data_api": self.youtube.name != "fixture"},
                )
                for video in videos[:videos_remaining]:
                    self._ensure_active(run_id)
                    video_id = str(video.get("video_id") or "")
                    if not video_id:
                        continue
                    comments = self._provider_task(
                        run_id, "REFERENCE_COLLECTION", f"youtube-comments:{video_id}",
                        {"video_id": video_id, "limit": 20},
                        lambda video_id=video_id: self.youtube.comments(video_id, limit=20),
                        provider_name=self.youtube.name,
                        cost_metadata={"monetary_cost": 0, "official_data_api": self.youtube.name != "fixture"},
                    )
                    excerpt = "\n".join(filter(None, [str(video.get("title") or ""), str(video.get("description") or ""), *[str(item.get("text") or "") for item in comments]]))
                    source_id = self.repository.add_source(run_id, "youtube", str(video.get("url") or f"https://www.youtube.com/watch?v={video_id}"), str(video.get("title") or "YouTube design observation"), excerpt, {"video_id": video_id, "channel_id": video.get("channel_id"), "official_data_api": self.youtube.name != "fixture", "comment_count": len(comments), "captions_retrieved": False})
                    collected.append({"id": source_id, "type": "youtube", "url": video.get("url"), "comments": len(comments)})
                    videos_remaining -= 1
            except BrandRunPaused:
                raise
            except Exception as error:
                failures.append({"url": "youtube", "error": type(error).__name__})
        sources = self.repository.sources(run_id)
        findings = [{
            "external_id": str(item["id"]),
            "title": item["title"],
            "source_uri": item["source_url"],
            "finding_summary": item["excerpt"],
            "publisher": urlsplit(str(item["source_url"])).hostname or "Owner supplied",
            "credibility": .5 if item["source_type"] == "manual_transcript" else .72,
        } for item in sources]
        self._ensure_active(run_id)
        mapping = self.bridge.sources(findings) if findings else {}
        self.repository.link_sources(mapping)
        if not collected and not payload.get("snapshot", {}).get("evidence"):
            raise RuntimeError("Branding reference collection produced no evidence")
        return {"items": collected, "failures": failures, "commander_sources": mapping, "caption_scraping": False, "paid_seo_calls": 0}, {"sources": len(collected), "failures": len(failures), "youtube_videos": 12 - videos_remaining, "paid_seo_calls": 0}

    def _generate_logos(self, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        run = self.repository.run(run_id)
        source_ids = list(run["source_snapshot"].get("commander_source_ids") or [])
        source_ids.extend(str(item["commander_source_id"]) for item in self.repository.sources(run_id) if item.get("commander_source_id"))
        source_ids = list(dict.fromkeys(source_ids))
        run_directory = self.asset_directory / run_id
        run_directory.mkdir(parents=True, exist_ok=True)
        artifacts = []
        for direction in self.repository.directions(run_id):
            if direction.get("artifact_digest") and direction.get("logo_path") and Path(str(direction["logo_path"])).is_file():
                artifacts.append({"direction_id": direction["id"], "digest": direction["artifact_digest"], "cached": True})
                continue
            generated = self._provider_task(
                run_id, "LOGO_GENERATION", f"logo:{direction['id']}", direction["manifest"],
                lambda direction=direction: self.provider.logo(direction["manifest"]),
            )
            self._ensure_active(run_id)
            from PIL import Image
            import io

            with Image.open(io.BytesIO(generated.content)) as image:
                if image.size != (1024, 1024) or image.format != "PNG":
                    raise ValueError("brand logo must be a 1024x1024 PNG")
            digest = hashlib.sha256(generated.content).hexdigest()
            path = run_directory / f"direction-{direction['ordinal']}-{digest[:16]}.png"
            if not path.exists():
                path.write_bytes(generated.content)
            graph = self.bridge.direction({
                "run_id": run_id,
                "direction_id": direction["id"],
                "source_laval_run_id": run["source_laval_run_id"],
                "hypothesis_ids": run["source_snapshot"].get("hypothesis_ids") or [],
                "source_has_surviving_thesis": bool(
                    run["source_snapshot"].get("surviving_thesis_ids")
                ),
                "source_ids": source_ids,
                "manifest": direction["manifest"],
                "evaluation": direction["evaluation"],
                "artifact": {
                    "sha256": digest,
                    "storage_uri": str(path),
                    "width": generated.width,
                    "height": generated.height,
                    "generation": {"provider": self.provider.name, "requested_model": generated.requested_model, "resolved_model": generated.resolved_model, "prompt": generated.prompt, "request_id": generated.request_id},
                },
            })
            self.repository.save_logo(str(direction["id"]), path=path, digest=digest, graph=graph)
            artifacts.append({"direction_id": direction["id"], "digest": digest, "creative_id": graph["creative_id"]})
        if len(artifacts) != 3:
            raise RuntimeError("Branding must persist exactly three logo artifacts")
        return {"items": artifacts, "successful_logos": 3}, {"successful_logos": 3, "image_calls_max": 3}

    def regenerate_logo(self, revision_id: str) -> dict[str, Any]:
        revision = self.repository.start_logo_revision(revision_id)
        run_id = str(revision["run_id"])
        if self.repository.run(run_id)["status"] != "running":
            raise BrandRunPaused("Branding logo regeneration is paused")
        direction = self.repository.direction(run_id, str(revision["direction_id"]))
        if str(direction.get("creative_id") or "") != str(revision["source_creative_id"]):
            raise ValueError("logo revision no longer targets the current Creative")
        feedback = self.repository.feedback_context(
            str(revision["feedback_id"]), str(revision["source_creative_id"])
        )
        manifest = dict(direction["manifest"])
        base_prompt = str(manifest.get("logo_prompt") or "").strip()
        manifest["logo_prompt"] = (
            f"{base_prompt}\n\nRevise the current concept using this explicit owner feedback: "
            f"{feedback['instruction']}\nCreate a meaningfully corrected new symbol, not a copy of "
            "the previous pixels. Preserve the brand direction, text-free requirement, transparency, "
            "originality, and favicon-size clarity."
        )[:4000]
        task_payload = {
            "direction": manifest,
            "feedback_id": revision["feedback_id"],
            "feedback": feedback["instruction"],
            "source_artifact_digest": revision["source_artifact_digest"],
            "revision": revision["revision"],
        }
        generated = self._provider_task(
            run_id, "LOGO_GENERATION",
            f"logo-revision:{revision_id}:attempt:{revision['attempt']}", task_payload,
            lambda: self.provider.logo(manifest),
        )
        if self.repository.run(run_id)["status"] != "running":
            raise BrandRunPaused("Branding logo regeneration is paused")
        from PIL import Image
        import io

        with Image.open(io.BytesIO(generated.content)) as image:
            if image.size != (1024, 1024) or image.format != "PNG":
                raise ValueError("brand logo revision must be a 1024x1024 PNG")
        digest = hashlib.sha256(generated.content).hexdigest()
        run_directory = self.asset_directory / run_id
        run_directory.mkdir(parents=True, exist_ok=True)
        path = run_directory / (
            f"direction-{direction['ordinal']}-r{revision['revision']}-{digest[:16]}.png"
        )
        if not path.exists():
            path.write_bytes(generated.content)
        graph = self.bridge.logo_revision({
            "run_id": run_id,
            "direction_id": direction["id"],
            "revision_id": revision_id,
            "revision": revision["revision"],
            "previous_creative_id": revision["source_creative_id"],
            "feedback_id": revision["feedback_id"],
            "artifact": {
                "sha256": digest,
                "storage_uri": str(path),
                "width": generated.width,
                "height": generated.height,
                "generation": {
                    "provider": self.provider.name,
                    "requested_model": generated.requested_model,
                    "resolved_model": generated.resolved_model,
                    "prompt": generated.prompt,
                    "request_id": generated.request_id,
                    "revision": revision["revision"],
                    "feedback_id": revision["feedback_id"],
                },
            },
        })
        self.repository.complete_logo_revision(
            revision_id, path=path, digest=digest, graph=graph
        )
        return {
            "run_id": run_id,
            "direction_id": str(direction["id"]),
            "revision_id": revision_id,
            "revision": int(revision["revision"]),
            "artifact_digest": digest,
        }

    def approve(self, run_id: str, direction_id: str, *, actor: str) -> dict[str, Any]:
        run = self.repository.run(run_id)
        if run["status"] == "completed" and run.get("commander_brand_kit_id"):
            return self.repository.kit(str(run["commander_brand_kit_id"]))
        if run["status"] != "awaiting_review" or not self.repository.reviewed(run_id):
            raise ValueError("all three current logo reviews are required before approval")
        if self.repository.refresh_source_staleness(run_id):
            raise ValueError("source Idea case changed; create a new Branding run")
        direction = self.repository.direction(run_id, direction_id)
        if not direction.get("latest_feedback_id"):
            raise ValueError("selected brand direction requires owner feedback")
        logo_path = Path(str(direction.get("logo_path") or ""))
        if not logo_path.is_file():
            raise ValueError("selected direction logo artifact is missing")
        run_directory = self.asset_directory / run_id / "kit"
        zip_path, zip_digest, kit_manifest = assemble_brand_kit(direction["manifest"], logo_path, run_directory)
        graph = self.bridge.approve({
            "run_id": run_id,
            "direction_id": direction_id,
            "source_laval_run_id": run["source_laval_run_id"],
            "source_snapshot_hash": run["source_snapshot_hash"],
            "manifest": kit_manifest,
            "current_creative_ids": {
                str(item["id"]): str(item["creative_id"])
                for item in self.repository.directions(run_id)
            },
            "actor": actor,
            "artifact": {"sha256": zip_digest, "storage_uri": str(zip_path), "size_bytes": zip_path.stat().st_size},
        })
        kit_id = new_uuid7()
        self.repository.save_kit(
            run_id, direction_id, kit_id=kit_id,
            commander_kit_id=str(graph["brand_kit_id"]),
            previous_kit_id=graph.get("previous_brand_kit_id"),
            manifest=kit_manifest, zip_path=zip_path, zip_digest=zip_digest, actor=actor,
        )
        return self.repository.kit(str(graph["brand_kit_id"]))
