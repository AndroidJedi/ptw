"""Owner-facing Branding application service and restartable runner."""

from __future__ import annotations

import threading
from typing import Any, Callable, Mapping

from commander.ids import new_uuid7

from .brand_pipeline import BrandPipeline
from .brand_repository import BrandRepository
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

    def active(self, run_id: str) -> bool:
        with self._guard:
            thread = self._threads.get(run_id)
            return bool(thread and thread.is_alive())

    def resume_incomplete(self) -> None:
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
                str(request.get("idea_run_id") or ""), run_id=run_id,
                constraints_text=str(request.get("constraints") or ""),
                reference_urls=request.get("reference_urls") or [],
                manual_transcripts=request.get("manual_transcripts") or [],
                actor=actor,
                provider_snapshot=self.readiness,
            )
            self.repository.ready(run_id)
            started = self.runner.start(run_id, guard_acquired=True)
            return {**result, "started": started, "status": "running"}
        except Exception:
            self.runner.operation_guard.release("branding", run_id)
            raise

    def resume(self, run_id: str, *, actor: str) -> dict[str, Any]:
        self.runner.operation_guard.acquire("branding", run_id)
        try:
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
