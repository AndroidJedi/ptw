"""Reusable Idea Laval application service and in-process run coordinator."""

from __future__ import annotations

import threading
from typing import Any, Mapping

from commander.ids import new_uuid7

from .laval_domain import LavalConfig, canonical_domain, canonical_url, stage_index
from .laval_pipeline import LavalPipeline
from .laval_repository import LavalRepository


class LavalRunner:
    def __init__(self, pipeline: LavalPipeline) -> None:
        self.pipeline = pipeline
        self._guard = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}

    def start(
        self,
        run_id: str,
        *,
        through_stage: str | None = None,
        start_stage: str | None = None,
        force: bool = False,
        country: str | None = None,
    ) -> bool:
        with self._guard:
            current = self._threads.get(run_id)
            if current and current.is_alive():
                return False
            thread = threading.Thread(
                target=self._execute,
                kwargs={"run_id": run_id, "through_stage": through_stage, "start_stage": start_stage, "force": force, "country": country},
                name=f"idea-laval-{run_id}",
                daemon=True,
            )
            self._threads[run_id] = thread
            thread.start()
            return True

    def _execute(self, **kwargs: Any) -> None:
        run_id = str(kwargs["run_id"])
        try:
            self.pipeline.run(**kwargs)
        except Exception:
            # The pipeline has already persisted a bounded failure record.
            pass
        finally:
            with self._guard:
                self._threads.pop(run_id, None)

    def active(self, run_id: str) -> bool:
        with self._guard:
            thread = self._threads.get(run_id)
            return bool(thread and thread.is_alive())

    def resume_incomplete(self) -> None:
        rows = self.pipeline.store.fetchall(
            "SELECT id FROM laval_runs WHERE status IN ('pending','running') ORDER BY created_at"
        )
        for row in rows:
            self.start(str(row["id"]))


class LavalService:
    def __init__(self, repository: LavalRepository, runner: LavalRunner, *, readiness: Mapping[str, Any] | None = None) -> None:
        self.repository = repository
        self.runner = runner
        self.store = repository.store
        self.readiness = dict(readiness or {})

    def create(self, text: str, config: Mapping[str, Any] | None, *, actor: str, requested_mode: str = "demo") -> dict[str, Any]:
        parsed = LavalConfig.from_mapping(config)
        if requested_mode not in {"demo", "live"}:
            raise ValueError("mode must be demo or live")
        if requested_mode == "demo" and not self.readiness.get("demo_available", True):
            raise RuntimeError("Demo mode is unavailable while live providers are active")
        if requested_mode == "live" and not self.readiness.get("search_live_ready"):
            raise RuntimeError("Live research requires verified DataForSEO credentials")
        evidence_mode = "demo_fixture" if requested_mode == "demo" else (
            "live_complete" if self.readiness.get("trends_live_ready") else "live_search_pending_trends"
        )
        snapshot = {
            "search": "fixture" if evidence_mode == "demo_fixture" else self.readiness.get("search_provider", "unavailable"),
            "web": "fixture" if evidence_mode == "demo_fixture" else "http",
            "trends": "fixture" if evidence_mode == "demo_fixture" else self.readiness.get("trend_provider", "unavailable"),
            "llm": self.readiness.get("llm_provider", "unknown"),
        }
        result = self.repository.create_run(
            text, parsed, actor=actor, evidence_mode=evidence_mode, provider_snapshot=snapshot,
            max_spend_usd=float(self.readiness.get("max_spend_usd", .05)),
            reserved_spend_usd=float(self.readiness.get("reserved_spend_usd", .04)),
        )
        return {**result, "status": "pending", "config": parsed.to_dict()}

    def list(self, limit: int = 30) -> dict[str, Any]:
        return {"items": self.repository.list_runs(limit), "next_cursor": None}

    def start(self, run_id: str, *, through_stage: str | None = None) -> dict[str, Any]:
        self.repository.run(run_id)
        if through_stage:
            stage_index(through_stage)
        self.repository.ready(run_id, through_stage=through_stage)
        started = self.runner.start(run_id, through_stage=through_stage)
        return {"run_id": run_id, "started": started, "status": self.repository.run(run_id)["status"]}

    def pause(self, run_id: str) -> dict[str, Any]:
        self.repository.pause(run_id)
        return {"run_id": run_id, "status": "paused"}

    def resume(self, run_id: str) -> dict[str, Any]:
        run = self.repository.run(run_id)
        if run["status"] == "completed":
            raise ValueError("completed Laval run does not need resume")
        if run.get("awaiting_reason") == "awaiting_trends_provider":
            if not self.readiness.get("trends_live_ready"):
                raise RuntimeError("Google Trends provider is not ready; synthesis and shortlist remain blocked")
            self.repository.enable_live_trends(run_id, str(self.readiness.get("trend_provider") or "google_trends"))
        self.repository.ready(run_id)
        started = self.runner.start(run_id)
        return {"run_id": run_id, "started": started, "status": "pending"}

    def approve(self, run_id: str, stage: str, *, actor: str) -> dict[str, Any]:
        result = self.repository.approve(run_id, stage.upper(), actor=actor)
        result["started"] = self.runner.start(run_id)
        return result

    def rerun(
        self, run_id: str, stage: str, *, country: str | None = None, force: bool = False, actor: str
    ) -> dict[str, Any]:
        stage = stage.upper()
        stage_index(stage)
        if country:
            country = country.upper()
            config = LavalConfig.from_mapping(self.repository.run(run_id)["config"])
            if country not in {item["code"] for item in config.countries}:
                raise ValueError("country is not configured for this run")
            if stage != "SERP_DISCOVERY":
                raise ValueError("country filter is supported only for SERP_DISCOVERY reruns")
        self.repository.override(run_id, "stage", stage, "rerun", reason="forced rerun" if force else "owner rerun", actor=actor, payload={"country": country, "force": force})
        self.repository.invalidate_from(run_id, stage, country=country)
        started = self.runner.start(run_id, start_stage=stage, force=force, country=country)
        return {"run_id": run_id, "stage": stage, "country": country, "started": started}

    def override(self, run_id: str, request: Mapping[str, Any], *, actor: str) -> dict[str, Any]:
        kind = str(request.get("type") or "").lower()
        action = str(request.get("action") or "").lower()
        target = str(request.get("target_id") or "")
        reason = str(request.get("reason") or "").strip()
        payload = dict(request.get("payload") or {})
        if kind == "competitor" and action == "add":
            url = canonical_url(str(payload.get("url") or target))
            domain = canonical_domain(url)
            country = str(payload.get("country") or "").upper()
            if not url or not country:
                raise ValueError("competitor add requires URL and country")
            config = LavalConfig.from_mapping(self.repository.run(run_id)["config"])
            if country not in {item["code"] for item in config.countries}:
                raise ValueError("country is not configured for this run")
            existing = self.store.fetchone("SELECT id FROM laval_competitors WHERE run_id=%s AND domain=%s", (run_id, domain))
            competitor_id = str(existing["id"]) if existing else new_uuid7()
            if existing:
                self.store.execute("UPDATE laval_competitors SET selected=TRUE,url=%s WHERE id=%s RETURNING 1", (url, competitor_id))
            else:
                self.store.execute(
                    """INSERT INTO laval_competitors(id,run_id,name,domain,url,result_type,score,selected,components)
                       VALUES(%s,%s,%s,%s,%s,'direct_product',1,TRUE,%s::jsonb) RETURNING 1""",
                    (competitor_id, run_id, str(payload.get("name") or domain), domain, url, self.store.json({"manual_override": 1})),
                )
            rank_row = self.store.fetchone("SELECT COALESCE(max(rank),0)+1 rank FROM laval_competitor_country_rankings WHERE run_id=%s AND country=%s", (run_id, country))
            self.store.execute(
                """INSERT INTO laval_competitor_country_rankings(run_id,competitor_id,country,rank,score)
                   VALUES(%s,%s,%s,%s,1) ON CONFLICT(run_id,country,competitor_id) DO NOTHING RETURNING 1""",
                (run_id, competitor_id, country, rank_row["rank"]),
            )
            target = competitor_id
            invalidate = "COMPETITOR_EVIDENCE"
        elif kind == "competitor" and action == "reject":
            if not self.store.fetchone("SELECT id FROM laval_competitors WHERE run_id=%s AND id=%s", (run_id, target)):
                raise KeyError("competitor not found")
            self.store.execute("DELETE FROM laval_competitor_country_rankings WHERE run_id=%s AND competitor_id=%s RETURNING 1", (run_id, target))
            self.store.execute("UPDATE laval_competitors SET selected=FALSE WHERE id=%s RETURNING 1", (target,))
            invalidate = "COMPETITOR_EVIDENCE"
        elif kind == "opportunity" and action == "disable":
            if not self.store.execute("UPDATE laval_opportunities SET enabled=FALSE WHERE run_id=%s AND id=%s RETURNING 1", (run_id, target)):
                raise KeyError("opportunity not found")
            invalidate = "TREND_QUERY_PLAN"
        elif kind in {"trend", "trend_score", "trend_discovery"} and action == "disable":
            changed = self.store.execute("UPDATE laval_trend_scores SET enabled=FALSE WHERE run_id=%s AND id=%s RETURNING 1", (run_id, target))
            if not changed:
                changed = self.store.execute("UPDATE laval_trend_discoveries SET enabled=FALSE WHERE run_id=%s AND id=%s RETURNING 1", (run_id, target))
            if not changed:
                raise KeyError("trend signal or discovery not found")
            invalidate = "SYNTHESIS_PACKET"
        else:
            raise ValueError("unsupported Laval override")
        override_id = self.repository.override(run_id, kind, target, action, reason=reason, actor=actor, payload=payload)
        self.repository.invalidate_from(run_id, invalidate)
        return {"override_id": override_id, "target_id": target, "invalidated_from": invalidate}
