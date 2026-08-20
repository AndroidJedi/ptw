"""Reusable Idea Laval application service and in-process run coordinator."""

from __future__ import annotations

import threading
from typing import Any, Mapping

from commander.ids import new_uuid7

from .laval_domain import LavalConfig, canonical_domain, canonical_url, stage_index
from .laval_pipeline import LavalPipeline
from .laval_repository import LavalRepository


class LavalRunner:
    def __init__(self, pipeline: LavalPipeline, notifier: Any | None = None) -> None:
        self.pipeline = pipeline
        self.notifier = notifier
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
            active = [key for key, value in self._threads.items() if value.is_alive()]
            if active:
                raise RuntimeError(f"Laval run {active[0]} is already active")
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
            if self.notifier is not None:
                try:
                    state = self.pipeline.repository.run(run_id)["status"]
                    if state in {"failed", "paused", "completed"}:
                        self.notifier.send(run_id, str(state))
                except Exception:
                    # Notification audit is durable, but delivery must never corrupt run state.
                    pass
            with self._guard:
                self._threads.pop(run_id, None)

    def active(self, run_id: str) -> bool:
        with self._guard:
            thread = self._threads.get(run_id)
            return bool(thread and thread.is_alive())

    def active_run_ids(self) -> tuple[str, ...]:
        with self._guard:
            return tuple(
                run_id for run_id, thread in self._threads.items() if thread.is_alive()
            )

    def resume_incomplete(self) -> None:
        rows = self.pipeline.store.fetchall(
            "SELECT id FROM laval_runs WHERE status IN ('pending','running') ORDER BY created_at"
        )
        if rows:
            self.start(str(rows[0]["id"]))


class LavalService:
    def __init__(self, repository: LavalRepository, runner: LavalRunner, *, readiness: Mapping[str, Any] | None = None, notifier: Any | None = None) -> None:
        self.repository = repository
        self.runner = runner
        self.store = repository.store
        self.readiness = dict(readiness or {})
        self.notifier = notifier

    def create(self, text: str, config: Mapping[str, Any] | None, *, actor: str, requested_mode: str = "demo") -> dict[str, Any]:
        parsed = LavalConfig.from_mapping(config)
        if requested_mode not in {"demo", "live"}:
            raise ValueError("mode must be demo or live")
        if requested_mode == "demo" and not self.readiness.get("demo_available", True):
            raise RuntimeError("Demo mode is unavailable while live providers are active")
        if requested_mode == "live" and not self.readiness.get("llm_live_ready", False):
            raise RuntimeError("Live research requires a complete Idea Laval LLM bridge contract")
        if requested_mode == "live" and not self.readiness.get("search_live_ready"):
            raise RuntimeError("Live research requires verified DataForSEO credentials")
        if requested_mode == "live" and not self.readiness.get("youtube_live_ready"):
            raise RuntimeError("Live mechanism/thesis research requires verified YouTube Data API access")
        evidence_mode = "demo_fixture" if requested_mode == "demo" else "live_market_signals"
        snapshot = {
            "search": "fixture" if evidence_mode == "demo_fixture" else self.readiness.get("search_provider", "unavailable"),
            "web": "fixture" if evidence_mode == "demo_fixture" else "http",
            "trends": "fixture" if evidence_mode == "demo_fixture" else self.readiness.get("trend_provider", "unavailable"),
            "llm": self.readiness.get("llm_provider", "unknown"),
            "youtube": "fixture" if evidence_mode == "demo_fixture" else self.readiness.get("youtube_provider", "unavailable"),
        }
        result = self.repository.create_run(
            text, parsed, actor=actor, evidence_mode=evidence_mode, provider_snapshot=snapshot,
            max_spend_usd=float(self.readiness.get("max_spend_usd", .05)),
            reserved_spend_usd=float(self.readiness.get("reserved_spend_usd", .04)),
            pipeline_version="mechanism_thesis_v1",
        )
        return {**result, "status": "pending", "config": parsed.to_dict()}

    def list(self, limit: int = 30) -> dict[str, Any]:
        return {"items": self.repository.list_runs(limit), "next_cursor": None}

    def theses(self, run_id: str) -> dict[str, Any]:
        return self.repository.theses(run_id)

    def select_thesis(self, run_id: str, thesis_id: str, workspace_id: str, *, actor: str) -> dict[str, Any]:
        return self.repository.select_thesis(run_id, thesis_id, workspace_id, actor=actor)

    def add_manual_youtube_transcript(
        self, run_id: str, *, video_url: str, title: str, transcript: str, actor: str,
    ) -> dict[str, Any]:
        return self.repository.add_manual_youtube_transcript(
            run_id, video_url=video_url, title=title, transcript=transcript, actor=actor,
        )

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

    def resume(self, run_id: str, *, actor: str = "system") -> dict[str, Any]:
        run = self.repository.run(run_id)
        if run["status"] == "completed":
            raise ValueError("completed Laval run does not need resume")
        if run.get("awaiting_reason") == "awaiting_trends_provider":
            if not self.readiness.get("trends_live_ready"):
                raise RuntimeError("Google Trends provider is not ready; synthesis and shortlist remain blocked")
            self.repository.enable_live_trends(run_id, str(self.readiness.get("trend_provider") or "google_trends"))
        recovery = self.repository.recovery(run_id)
        action_id = self.repository.record_action(
            run_id,
            "resume_requested",
            stage=str(run.get("current_stage") or "") or None,
            actor=actor,
            previous_status=str(run.get("status") or ""),
            outcome="requested",
            details={
                "attempt": recovery["attempt"],
                "failure": recovery.get("failure"),
                "provider_tasks": recovery["provider_tasks"],
                "reuses_persisted_remote_ids": True,
                "reposts_submitted_tasks": False,
                "duplicates_recorded_cost": False,
            },
        )
        self.repository.ready(run_id)
        started = self.runner.start(run_id)
        self.store.execute(
            "UPDATE laval_run_actions SET outcome=%s WHERE id=%s RETURNING 1",
            ("started" if started else "already_running", action_id),
        )
        return {
            "run_id": run_id,
            "started": started,
            "status": "pending",
            "recovery_action_id": action_id,
            "resume_behavior": recovery["resume_behavior"],
            "provider_tasks": recovery["provider_tasks"],
        }

    def resume_with_market_signals(self, run_id: str, *, actor: str) -> dict[str, Any]:
        action_id = self.repository.upgrade_to_market_signals(run_id, actor=actor)
        started = self.runner.start(run_id, start_stage="MARKET_SIGNAL_PLAN")
        return {
            "run_id": run_id,
            "started": started,
            "status": "pending",
            "action_id": action_id,
            "resume_behavior": {
                "reuses_persisted_remote_ids": True,
                "reposts_submitted_tasks": False,
                "duplicates_recorded_cost": False,
            },
        }

    def notify(self, run_id: str, *, actor: str) -> dict[str, Any]:
        self.repository.run(run_id)
        if self.notifier is None:
            raise RuntimeError("Telegram status notifications are not configured")
        sent = int(self.notifier.send(run_id, "owner_status", force=True, actor=actor))
        if sent < 1:
            raise RuntimeError("Telegram status notification could not be sent")
        return {
            "run_id": run_id,
            "sent": sent,
            "queued": 0,
            "status": self.repository.run(run_id)["status"],
        }

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
        if not reason:
            raise ValueError("manual correction requires a reason for the audit log")
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
            invalidate = (
                "MARKET_SIGNAL_PLAN"
                if self.repository.run(run_id).get("pipeline_version") == "market_signals_v2"
                else "TREND_QUERY_PLAN"
            )
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
