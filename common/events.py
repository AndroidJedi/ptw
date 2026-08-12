from collections.abc import Mapping
from typing import Any

from psycopg.types.json import Jsonb

SENSITIVE_FRAGMENTS = ("secret", "token", "password", "credential", "api_key")


def _safe_payload(value: Any, key: str = "") -> Any:
    if any(fragment in key.lower() for fragment in SENSITIVE_FRAGMENTS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): _safe_payload(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_payload(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def append_event(
    connection: Any,
    event_type: str,
    actor: str,
    *,
    status: str | None = None,
    session_id: int | None = None,
    job_id: int | None = None,
    payload: Mapping[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO events (session_id, job_id, actor, event_type, status, payload)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (session_id, job_id, actor, event_type, status, Jsonb(_safe_payload(payload or {}))),
    )
