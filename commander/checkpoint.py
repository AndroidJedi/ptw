"""Bounded, integrity-checked resume state for Commander/Codex sessions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


CHECKPOINT_VERSION = 1
MAX_ITEMS = 100
MAX_TEXT = 4000


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _bounded_text(value: object, field: str) -> str:
    text = str(value).strip()
    if not text or len(text) > MAX_TEXT:
        raise ValueError(f"{field} must be 1-{MAX_TEXT} characters")
    return text


def _bounded_json(value: object, field: str) -> object:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if len(encoded) > MAX_TEXT * MAX_ITEMS:
        raise ValueError(f"{field} is too large")
    return json.loads(encoded)


def _items(value: object, field: str) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a list")
    if len(value) > MAX_ITEMS:
        raise ValueError(f"{field} may contain at most {MAX_ITEMS} items")
    return tuple(_bounded_json(item, field) for item in value)


@dataclass(frozen=True, slots=True)
class SessionCheckpoint:
    checkpoint_id: str
    scope: str
    workspace_session_id: str
    agreed_decisions: tuple[object, ...]
    active_tasks: tuple[object, ...]
    active_issues: tuple[object, ...]
    deployment_state: Mapping[str, Any]
    verification_evidence: tuple[object, ...]
    next_action: str
    created_at: datetime
    checksum: str
    version: int = CHECKPOINT_VERSION

    def payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "scope": self.scope,
            "workspace_session_id": self.workspace_session_id,
            "agreed_decisions": list(self.agreed_decisions),
            "active_tasks": list(self.active_tasks),
            "active_issues": list(self.active_issues),
            "deployment_state": dict(self.deployment_state),
            "verification_evidence": list(self.verification_evidence),
            "next_action": self.next_action,
        }

    def integrity_valid(self) -> bool:
        return self.checksum == checkpoint_checksum(self.payload())

    def age_seconds(self, now: datetime | None = None) -> float:
        current = _utc(now or datetime.now(timezone.utc))
        return max(0.0, (current - _utc(self.created_at)).total_seconds())

    def restore_status(self, max_age_seconds: int, now: datetime | None = None) -> str:
        if not self.integrity_valid():
            return "corrupt"
        return "fresh" if self.age_seconds(now) <= max_age_seconds else "stale"


def normalize_checkpoint(request: Mapping[str, object]) -> dict[str, object]:
    deployment = request.get("deployment_state")
    if not isinstance(deployment, Mapping):
        raise ValueError("deployment_state must be an object")
    return {
        "version": CHECKPOINT_VERSION,
        "scope": _bounded_text(request.get("scope", "commander"), "scope"),
        "workspace_session_id": _bounded_text(
            request.get("workspace_session_id", ""), "workspace_session_id"
        ),
        "agreed_decisions": list(_items(request.get("agreed_decisions", []), "agreed_decisions")),
        "active_tasks": list(_items(request.get("active_tasks", []), "active_tasks")),
        "active_issues": list(_items(request.get("active_issues", []), "active_issues")),
        "deployment_state": _bounded_json(dict(deployment), "deployment_state"),
        "verification_evidence": list(
            _items(request.get("verification_evidence", []), "verification_evidence")
        ),
        "next_action": _bounded_text(request.get("next_action", ""), "next_action"),
    }


def checkpoint_checksum(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def checkpoint_response(
    checkpoint: SessionCheckpoint, max_age_seconds: int
) -> dict[str, object]:
    return {
        "status": checkpoint.restore_status(max_age_seconds),
        "checkpoint_id": checkpoint.checkpoint_id,
        "created_at": checkpoint.created_at.isoformat(),
        "age_seconds": checkpoint.age_seconds(),
        "checksum": checkpoint.checksum,
        "checkpoint": checkpoint.payload(),
    }


def startup_checkpoint_canary(
    store: object, max_age_seconds: int, scope: str = "commander"
) -> dict[str, object]:
    restore = getattr(store, "latest_session_checkpoint", None)
    if restore is None:
        return {"status": "unsupported", "checkpoint": None}
    try:
        checkpoint = restore(scope)
    except KeyError:
        return {"status": "absent", "checkpoint": None}
    except Exception as error:
        return {"status": "error", "checkpoint": None, "detail": type(error).__name__}
    return checkpoint_response(checkpoint, max_age_seconds)
