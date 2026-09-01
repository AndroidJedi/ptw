"""Typed delivery boundary for owner-review notifications."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Protocol
from urllib import error, request


@dataclass(frozen=True, slots=True)
class NotificationAttempt:
    status: str
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"delivered", "definite_failure", "ambiguous"}:
            raise ValueError("unknown review-notification delivery status")


class ReviewNotifier(Protocol):
    def notify(self, event: Mapping[str, Any]) -> NotificationAttempt: ...


class CommanderReviewNotifier:
    """POST one typed event to Commander; Commander owns Telegram credentials."""

    def __init__(self, endpoint: str, token: str, *, timeout_seconds: float = 10.0) -> None:
        self.endpoint = endpoint.strip()
        self.token = token.strip()
        self.timeout_seconds = timeout_seconds
        if not self.endpoint or not self.token:
            raise RuntimeError("Commander review-notification relay is not configured")

    def notify(self, event: Mapping[str, Any]) -> NotificationAttempt:
        payload = json.dumps(dict(event), ensure_ascii=False, separators=(",", ":")).encode()
        outgoing = request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with request.urlopen(outgoing, timeout=self.timeout_seconds) as response:
                value = json.loads(response.read().decode())
        except (TimeoutError, error.URLError) as failure:
            reason = getattr(failure, "reason", failure)
            if isinstance(reason, TimeoutError):
                return NotificationAttempt(
                    "ambiguous", error_code=type(failure).__name__, error_message=str(failure)[:500],
                )
            return NotificationAttempt(
                "definite_failure", error_code=type(failure).__name__, error_message=str(failure)[:500],
            )
        except (OSError, json.JSONDecodeError) as failure:
            return NotificationAttempt(
                "ambiguous", error_code=type(failure).__name__, error_message=str(failure)[:500],
            )
        return NotificationAttempt(
            str(value.get("status") or "ambiguous"),
            provider_message_id=(
                None if value.get("provider_message_id") is None
                else str(value["provider_message_id"])
            ),
            error_code=None if value.get("error_code") is None else str(value["error_code"]),
            error_message=(
                None if value.get("error_message") is None else str(value["error_message"])[:500]
            ),
        )
