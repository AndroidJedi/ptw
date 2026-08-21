"""Single-process guard for heavy Idea-service operations."""

from __future__ import annotations

import threading
from typing import Any


class OperationConflict(RuntimeError):
    def __init__(self, active: dict[str, str]) -> None:
        self.active = active
        super().__init__(
            f"{active['operation']} run {active['run_id']} is already active"
        )


class HeavyOperationGuard:
    """Serialize Laval and Branding without coupling their pipelines."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: dict[str, str] | None = None

    def acquire(self, operation: str, run_id: str) -> None:
        with self._lock:
            if self._active is not None:
                raise OperationConflict(dict(self._active))
            self._active = {"operation": operation, "run_id": run_id}

    def ensure_available(self) -> None:
        with self._lock:
            if self._active is not None:
                raise OperationConflict(dict(self._active))

    def release(self, operation: str, run_id: str) -> None:
        with self._lock:
            if self._active == {"operation": operation, "run_id": run_id}:
                self._active = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            active = dict(self._active) if self._active else None
        return {
            "active": active is not None,
            "operation": active["operation"] if active else None,
            "run_id": active["run_id"] if active else None,
        }
