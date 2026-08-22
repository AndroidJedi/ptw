"""Owner-facing Branding application service and restartable runner."""

from __future__ import annotations

import threading
from typing import Any, Callable, Mapping

from commander.ids import new_uuid7

from .brand_pipeline import BrandPipeline
from .brand_repository import BrandRepository
from .laval_domain import json_safe
from .operation_guard import HeavyOperationGuard, OperationConflict


class BrandRunner:
    def __init__(self, pipeline: BrandPipeline, operation_guard: HeavyOperationGuard) -> None:
        self.pipeline = pipeline
        self.operation_guard = operation_guard
        self._guard = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}
        self.on_idle: Callable[[], None] | None = None

    def start(
        self, run_id: str, *, start_stage: str | None = None,
        guard_acquired: bool = False,
    ) -> bool:
        with self._guard:
            current = self._threads.get(run_id)
            if current and current.is_alive():
                return False
            if not guard_acquired:
                self.operation_guard.acquire("branding", run_id)
            elif self.operation_guard.snapshot() != {
                "active": True, "operation": "branding", "run_id": run_id
            }:
                raise RuntimeError("Branding operation guard reservation was lost")
            thread = threading.Thread(
                target=self._execute,
                kwargs={"run_id": run_id, "start_stage": start_stage},
                name=f"branding-{run_id}",
                daemon=True,
            )
            self._threads[run_id] = thread
            try:
                thread.start()
            except Exception:
                self._threads.pop(run_id, None)
                self.operation_guard.release("branding", run_id)
                raise
            return True

    def start_revision(
        self, run_id: str, revision_id: str, *, guard_acquired: bool = False,
    ) -> bool:
        with self._guard:
            current = self._threads.get(run_id)
            if current and current.is_alive():
                return False
            if not guard_acquired:
                self.operation_guard.acquire("branding", run_id)
            elif self.operation_guard.snapshot() != {
                "active": True, "operation": "branding", "run_id": run_id
            }:
                raise RuntimeError("Branding operation guard reservation was lost")
            thread = threading.Thread(
                target=self._execute_revision,
                kwargs={"run_id": run_id, "revision_id": revision_id},
                name=f"branding-logo-revision-{revision_id}",
                daemon=True,
            )
            self._threads[run_id] = thread
            try:
                thread.start()
            except Exception:
                self._threads.pop(run_id, None)
                self.operation_guard.release("branding", run_id)
                raise
            return True

    def start_kit_revision(
        self, project_id: str, revision_id: str, *, guard_acquired: bool = False,
    ) -> bool:
        with self._guard:
            current = self._threads.get(project_id)
            if current and current.is_alive():
                return False
            if not guard_acquired:
                self.operation_guard.acquire("branding", project_id)
            elif self.operation_guard.snapshot() != {
                "active": True, "operation": "branding", "run_id": project_id
            }:
                raise RuntimeError("Branding operation guard reservation was lost")
            thread = threading.Thread(
                target=self._execute_kit_revision,
                kwargs={"project_id": project_id, "revision_id": revision_id},
                name=f"branding-kit-logo-revision-{revision_id}", daemon=True,
            )
            self._threads[project_id] = thread
            try:
                thread.start()
            except Exception:
                self._threads.pop(project_id, None)
                self.operation_guard.release("branding", project_id)
                raise
            return True

    def _execute(self, *, run_id: str, start_stage: str | None) -> None:
        try:
            self.pipeline.run(run_id, start_stage=start_stage)
        except Exception as error:
            run = self.pipeline.repository.run(run_id)
            if run["status"] == "running":
                self.pipeline.repository.fail_stage(
                    run_id, str(run.get("current_stage") or "REFERENCE_PLAN"), error
                )
        finally:
            with self._guard:
                self._threads.pop(run_id, None)
            self.operation_guard.release("branding", run_id)
            if self.on_idle is not None:
                try:
                    self.on_idle()
                except Exception:
                    # The durable queue remains restartable; handoff failures
                    # must not rewrite the completed run's state.
                    pass

    def _execute_revision(self, *, run_id: str, revision_id: str) -> None:
        try:
            self.pipeline.regenerate_logo(revision_id)
        except Exception as error:
            from .brand_pipeline import BrandRunPaused

            if isinstance(error, BrandRunPaused):
                self.pipeline.repository.pause_logo_revision(revision_id)
            else:
                self.pipeline.repository.fail_logo_revision(revision_id, error)
        finally:
            with self._guard:
                self._threads.pop(run_id, None)
            self.operation_guard.release("branding", run_id)
            if self.on_idle is not None:
                try:
                    self.on_idle()
                except Exception:
                    pass

    def _execute_kit_revision(self, *, project_id: str, revision_id: str) -> None:
        try:
            self.pipeline.revise_approved_kit(revision_id)
        except Exception as error:
            revision = self.pipeline.repository.kit_logo_revision(revision_id)
            if revision["status"] not in {"failed", "completed", "approved", "rejected"}:
                self.pipeline.repository.fail_kit_logo_revision(revision_id, error)
        finally:
            with self._guard:
                self._threads.pop(project_id, None)
            self.operation_guard.release("branding", project_id)
            if self.on_idle is not None:
                try:
                    self.on_idle()
                except Exception:
                    pass

    def active(self, run_id: str) -> bool:
        with self._guard:
            thread = self._threads.get(run_id)
            return bool(thread and thread.is_alive())

    def resume_incomplete(self) -> None:
        kit_revision = self.pipeline.repository.pending_kit_logo_revision()
        if kit_revision:
            project_id = str(kit_revision["source_laval_run_id"])
            try:
                self.operation_guard.acquire("branding", project_id)
            except OperationConflict:
                return
            try:
                self.start_kit_revision(
                    project_id, str(kit_revision["id"]), guard_acquired=True
                )
            except Exception:
                self.operation_guard.release("branding", project_id)
                raise
            return
        revision = self.pipeline.repository.pending_logo_revision()
        if revision:
            run_id = str(revision["run_id"])
            try:
                self.operation_guard.acquire("branding", run_id)
            except OperationConflict:
                return
            try:
                self.pipeline.store.execute(
                    """UPDATE brand_runs SET status='running',current_stage='OWNER_REVIEW',
                              error_text=NULL,updated_at=NOW() WHERE id=%s RETURNING 1""",
                    (run_id,),
                )
                self.start_revision(
                    run_id, str(revision["id"]), guard_acquired=True
                )
            except Exception:
                self.operation_guard.release("branding", run_id)
                raise
            return
        row = self.pipeline.store.fetchone(
            """SELECT id FROM brand_runs
               WHERE status IN ('pending','running') ORDER BY created_at LIMIT 1"""
        )
        if not row:
            return
        run_id = str(row["id"])
        try:
            self.operation_guard.acquire("branding", run_id)
        except OperationConflict:
            # The durable pending/running projection remains resumable after the
            # operation that won startup serialization finishes.
            return
        try:
            self.pipeline.repository.ready_after_restart(run_id)
            self.start(run_id, guard_acquired=True)
        except Exception:
            self.operation_guard.release("branding", run_id)
            raise


class BrandService:
    def __init__(
        self,
        repository: BrandRepository,
        runner: BrandRunner,
        pipeline: BrandPipeline,
        *,
        readiness: Mapping[str, Any],
    ) -> None:
        self.repository = repository
        self.runner = runner
        self.pipeline = pipeline
        self.readiness = dict(readiness)

    def create(self, request: Mapping[str, Any], *, actor: str) -> dict[str, Any]:
        idea_run_id = str(request.get("idea_run_id") or "")
        intent = str(request.get("intent") or "initial").strip().lower()
        client_request_id = str(request.get("client_request_id") or "").strip() or None
        if intent == "full_rebuild" and request.get("confirmed") is not True:
            raise ValueError("full_rebuild requires explicit confirmation")
        existing = self.repository.existing_create(
            idea_run_id, intent=intent, client_request_id=client_request_id
        )
        if existing and existing.get("project_exists"):
            raise ValueError(
                "Brand Project already exists; open its history or use intent=full_rebuild"
            )
        if existing:
            return {
                "run_id": str(existing["id"]), "project_id": idea_run_id,
                "project_version": int(existing["project_version"]),
                "status": str(existing["status"]), "started": False,
                "existing": True,
            }
        if not self.readiness.get("ready"):
            missing = ", ".join(str(item) for item in self.readiness.get("missing") or [])
            raise RuntimeError(
                "Branding generation provider is not configured"
                + (f"; missing: {missing}" if missing else "")
            )
        run_id = new_uuid7()
        self.runner.operation_guard.acquire("branding", run_id)
        try:
            result = self.repository.create(
                idea_run_id, run_id=run_id,
                constraints_text=str(request.get("constraints") or ""),
                reference_urls=request.get("reference_urls") or [],
                manual_transcripts=request.get("manual_transcripts") or [],
                actor=actor,
                provider_snapshot=self.readiness,
                intent=intent,
                client_request_id=client_request_id,
            )
            if result.get("existing"):
                self.runner.operation_guard.release("branding", run_id)
                return {**result, "started": False}
            self.repository.ready(run_id)
            started = self.runner.start(run_id, guard_acquired=True)
            return {**result, "started": started, "status": "running"}
        except Exception:
            self.runner.operation_guard.release("branding", run_id)
            raise

    def revise_approved_logo(
        self, project_id: str, feedback_id: str, *, client_request_id: str,
        actor: str,
    ) -> dict[str, Any]:
        if not self.readiness.get("revision_ready"):
            raise RuntimeError("Branding reference-edit contract is unavailable")
        existing = self.repository.store.fetchone(
            """SELECT * FROM brand_kit_logo_revisions
               WHERE source_laval_run_id=%s AND client_request_id=%s""",
            (project_id, client_request_id),
        )
        if existing:
            return {**json_safe(existing), "started": False}
        self.runner.operation_guard.acquire("branding", project_id)
        try:
            revision = self.repository.queue_kit_logo_revision(
                project_id, feedback_id, client_request_id=client_request_id,
                actor=actor, provider=self.pipeline.provider.name,
                model=self.pipeline.provider.image_model,
            )
            started = self.runner.start_kit_revision(
                project_id, str(revision["id"]), guard_acquired=True
            )
            return {**revision, "started": started}
        except Exception:
            self.runner.operation_guard.release("branding", project_id)
            raise

    def retry_approved_logo_revision(
        self, project_id: str, revision_id: str, *, actor: str,
    ) -> dict[str, Any]:
        revision = self.repository.kit_logo_revision(revision_id)
        if str(revision["source_laval_run_id"]) != project_id:
            raise KeyError("Brand Project logo revision not found")
        self.runner.operation_guard.acquire("branding", project_id)
        try:
            self.repository.requeue_kit_logo_revision(revision_id)
            return {
                "revision_id": revision_id, "status": "running",
                "started": self.runner.start_kit_revision(
                    project_id, revision_id, guard_acquired=True
                ),
            }
        except Exception:
            self.runner.operation_guard.release("branding", project_id)
            raise

    def decide_approved_logo_revision(
        self, project_id: str, revision_id: str, *, decision: str, actor: str,
    ) -> dict[str, Any]:
        revision = self.repository.kit_logo_revision(revision_id)
        if str(revision["source_laval_run_id"]) != project_id:
            raise KeyError("Brand Project logo revision not found")
        if decision == "reject":
            return self.repository.reject_kit_logo_revision(revision_id, actor=actor)
        if decision != "approve":
            raise ValueError("logo revision decision must be approve or reject")
        self.runner.operation_guard.acquire("branding", project_id)
        try:
            return self.pipeline.approve_kit_logo_revision(revision_id, actor=actor)
        finally:
            self.runner.operation_guard.release("branding", project_id)

    def resume(self, run_id: str, *, actor: str) -> dict[str, Any]:
        self.runner.operation_guard.acquire("branding", run_id)
        try:
            revision = self.repository.pending_logo_revision(run_id)
            if revision:
                self.repository.store.execute(
                    """UPDATE brand_runs SET status='running',current_stage='OWNER_REVIEW',
                              error_text=NULL,updated_at=NOW() WHERE id=%s RETURNING 1""",
                    (run_id,),
                )
                self.repository.record_action(
                    run_id, "logo_revision_resumed", actor=actor,
                    details={"revision_id": str(revision["id"])},
                )
                return {
                    "run_id": run_id,
                    "revision_id": str(revision["id"]),
                    "started": self.runner.start_revision(
                        run_id, str(revision["id"]), guard_acquired=True
                    ),
                    "status": "running",
                }
            self.repository.ready(run_id)
            self.repository.record_action(run_id, "resumed", actor=actor)
            return {
                "run_id": run_id,
                "started": self.runner.start(run_id, guard_acquired=True),
                "status": "running",
            }
        except Exception:
            self.runner.operation_guard.release("branding", run_id)
            raise

    def pause(self, run_id: str, *, actor: str) -> dict[str, Any]:
        self.repository.pause(run_id, actor=actor)
        return {"run_id": run_id, "status": "paused"}

    def rerun(self, run_id: str, stage: str, *, actor: str) -> dict[str, Any]:
        self.runner.operation_guard.acquire("branding", run_id)
        try:
            self.repository.invalidate_from(run_id, stage, actor=actor)
            self.repository.ready(run_id)
            return {
                "run_id": run_id,
                "stage": stage.upper(),
                "started": self.runner.start(
                    run_id, start_stage=stage.upper(), guard_acquired=True
                ),
                "status": "running",
            }
        except Exception:
            self.runner.operation_guard.release("branding", run_id)
            raise

    def approve(self, run_id: str, direction_id: str, *, actor: str) -> dict[str, Any]:
        run = self.repository.run(run_id)
        if run["status"] == "completed" and run.get("commander_brand_kit_id"):
            return self.pipeline.approve(run_id, direction_id, actor=actor)
        self.runner.operation_guard.acquire("branding", run_id)
        try:
            return self.pipeline.approve(run_id, direction_id, actor=actor)
        finally:
            self.runner.operation_guard.release("branding", run_id)

    def regenerate_logo(
        self, run_id: str, direction_id: str, feedback_id: str, *, actor: str,
    ) -> dict[str, Any]:
        self.runner.operation_guard.acquire("branding", run_id)
        try:
            revision = self.repository.queue_logo_revision(
                run_id, direction_id, feedback_id, actor=actor,
                provider=self.pipeline.provider.name,
                model=self.pipeline.provider.image_model,
            )
            if revision["status"] == "completed":
                self.runner.operation_guard.release("branding", run_id)
                return {
                    "run_id": run_id,
                    "direction_id": direction_id,
                    "revision_id": str(revision["id"]),
                    "status": "completed",
                    "started": False,
                }
            started = self.runner.start_revision(
                run_id, str(revision["id"]), guard_acquired=True
            )
            return {
                "run_id": run_id,
                "direction_id": direction_id,
                "revision_id": str(revision["id"]),
                "status": "running",
                "started": started,
            }
        except Exception:
            snapshot = self.runner.operation_guard.snapshot()
            if snapshot == {
                "active": True, "operation": "branding", "run_id": run_id
            }:
                self.runner.operation_guard.release("branding", run_id)
            raise
