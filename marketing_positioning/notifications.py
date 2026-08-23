"""Terminal Marketing Positioning notifications through the existing PTW bot."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping

try:  # Keep pure tests runnable outside the built runtime image.
    import httpx
except ModuleNotFoundError:  # pragma: no cover - production image installs it
    httpx = None  # type: ignore[assignment]

from .repository import PositioningRepository


class ExistingBotPositioningNotifier:
    """One direct sendMessage call after a durable terminal generation attempt."""

    def __init__(
        self,
        repository: PositioningRepository,
        *,
        bot_token: str,
        owner_chat_id: int,
        allowed_chat_ids: frozenset[int],
    ) -> None:
        if not bot_token or owner_chat_id not in allowed_chat_ids:
            raise RuntimeError("existing PTW bot and allowlisted owner chat are required")
        self.repository = repository
        self.bot_token = bot_token
        self.owner_chat_id = owner_chat_id
        self.allowed_chat_ids = allowed_chat_ids

    def notify(self, revision_id: str, generation_attempt_id: str) -> Mapping[str, Any]:
        if httpx is None:
            raise RuntimeError("httpx is required for Telegram sendMessage")
        prior = self.repository.notification_attempt(generation_attempt_id)
        if prior is not None:
            return prior
        revision = self.repository.get_revision(revision_id)
        attempt = self.repository.generation_attempt(generation_attempt_id)
        if attempt["revision_id"] != revision_id:
            raise ValueError("generation attempt does not belong to the positioning revision")
        terminal_status = str(revision["status"])
        expected_attempt = "completed" if terminal_status == "completed" else "failed"
        if terminal_status not in {"completed", "failed"} or attempt["status"] != expected_attempt:
            raise ValueError("positioning notification requires matching durable terminal states")
        if self.owner_chat_id not in self.allowed_chat_ids:
            raise RuntimeError("notification chat is outside the existing allowlist")
        if self.repository.emergency_stopped():
            return self.repository.record_notification_attempt(
                revision_id, generation_attempt_id,
                terminal_status=terminal_status, status="suppressed",
                chat_id=self.owner_chat_id, error_code="EmergencyStop",
                error_message="outbound send suppressed while PTW emergency stop is active",
            )
        project = self.repository.get_project(revision["project_id"])
        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.owner_chat_id,
                    "text": self._message(project, revision, attempt),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("ok") is not True or not isinstance(body.get("result"), Mapping):
                raise RuntimeError("Telegram returned an invalid sendMessage response")
            return self.repository.record_notification_attempt(
                revision_id, generation_attempt_id,
                terminal_status=terminal_status, status="sent",
                chat_id=self.owner_chat_id,
                message_id=int(body["result"]["message_id"]),
            )
        except httpx.TimeoutException as error:
            return self.repository.record_notification_attempt(
                revision_id, generation_attempt_id,
                terminal_status=terminal_status, status="ambiguous",
                chat_id=self.owner_chat_id, error_code=type(error).__name__,
                error_message="sendMessage timed out; delivery is unknown",
            )
        except Exception as error:
            return self.repository.record_notification_attempt(
                revision_id, generation_attempt_id,
                terminal_status=terminal_status, status="failed",
                chat_id=self.owner_chat_id, error_code=type(error).__name__,
                error_message="existing PTW bot sendMessage failed",
            )

    @staticmethod
    def _message(
        project: Mapping[str, Any],
        revision: Mapping[str, Any],
        attempt: Mapping[str, Any],
    ) -> str:
        completed = revision["status"] == "completed"
        lines = [
            f"<b>PTW Positioning {'completed' if completed else 'failed'}</b>",
            f"Project: <code>{escape(str(project['id']))}</code>",
            f"Revision: <code>{escape(str(revision['id']))}</code> (#{int(revision['revision_number'])})",
            f"Generation attempt: {int(attempt['attempt_number'])}",
            f"Market: {escape(str(project['target_country']))} / {escape(str(project['research_language']))}",
            f"Output: {escape(str(project['output_language']))}",
            f"Idea: {escape(str(project['raw_idea'])[:500])}",
        ]
        if completed:
            lines.append("Ready for owner review and approval in the web console.")
        else:
            lines.extend([
                f"Error: <code>{escape(str(revision.get('error_code') or 'GenerationError'))}</code>",
                escape(str(revision.get("error_message") or "Positioning generation failed")[:1000]),
            ])
        return "\n".join(lines)
