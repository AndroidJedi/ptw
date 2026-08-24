"""Audited direct Telegram notices for terminal Validation failures."""

from __future__ import annotations

from contextlib import contextmanager
from html import escape
from typing import Any, Callable, Iterator, Mapping, Sequence
from uuid import UUID

import httpx

from commander.ids import new_uuid7


class ValidationFailureNotificationRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "target_id": str(row[0]),
            "attempt_id": str(row[1]),
            "stage": row[2],
            "attempt_number": int(row[3]),
            "error_code": row[4] or "GenerationError",
            "error_message": row[5] or "generation failed",
            "failed_at": row[6].isoformat(),
        }

    def reserve(self, target_id: str, attempt_id: str, stage: str) -> dict[str, Any] | None:
        from psycopg.types.json import Jsonb

        target_uuid, attempt_uuid = UUID(target_id), UUID(attempt_id)
        with self.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (str(attempt_uuid),),
            )
            prior = connection.execute(
                """SELECT 1 FROM commander_audit_events
                   WHERE action='telegram_generation_failure_reserved'
                     AND details->>'attempt_id'=%s LIMIT 1""",
                (str(attempt_uuid),),
            ).fetchone()
            if prior is not None:
                return None
            row = connection.execute(
                """SELECT attempt.target_id,attempt.id,attempt.stage,attempt.attempt_number,
                          attempt.error_code,attempt.error_message,attempt.completed_at
                   FROM validation_generation_attempts attempt
                   WHERE attempt.target_id=%s AND attempt.id=%s AND attempt.stage=%s
                     AND attempt.status='failed' AND attempt.completed_at IS NOT NULL""",
                (target_uuid, attempt_uuid, stage),
            ).fetchone()
            if row is None:
                raise ValueError("notification target is not one failed Validation attempt")
            failure = self._row(row)
            connection.execute(
                """INSERT INTO commander_audit_events(id,actor,action,target_id,details)
                   VALUES(%s,'owner-gateway','telegram_generation_failure_reserved',%s,%s)""",
                (
                    UUID(new_uuid7()),
                    target_uuid,
                    Jsonb({
                        "attempt_id": failure["attempt_id"],
                        "stage": failure["stage"],
                        "status": "pending",
                    }),
                ),
            )
        return failure

    def record_result(
        self,
        failure: Mapping[str, Any],
        *,
        status: str,
        message_id: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        if status not in {"sent", "failed", "ambiguous", "suppressed"}:
            raise ValueError("invalid failure notification result")
        details = {
            "attempt_id": failure["attempt_id"],
            "stage": failure["stage"],
            "status": status,
            "message_id": message_id,
            "error_code": error_code,
            "error_message": error_message,
        }
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO commander_audit_events(id,actor,action,target_id,details)
                   VALUES(%s,'owner-gateway','telegram_generation_failure_result',%s,%s)""",
                (UUID(new_uuid7()), UUID(str(failure["target_id"])), Jsonb(details)),
            )
        return {"status": status, "attempt_id": failure["attempt_id"]}


class ExistingBotValidationFailureNotifier:
    """One direct sendMessage per failed attempt; no polling or retry path."""

    def __init__(
        self,
        repository: ValidationFailureNotificationRepository,
        *,
        bot_token: str,
        owner_chat_id: int,
        allowed_chat_ids: frozenset[int],
        owner_console_url: str,
        post: Callable[..., Any] = httpx.post,
    ) -> None:
        self.repository = repository
        self.bot_token = bot_token
        self.owner_chat_id = owner_chat_id
        self.allowed_chat_ids = allowed_chat_ids
        self.owner_console_url = owner_console_url.rstrip("/")
        self.post = post

    def notify(self, target_id: str, attempt_id: str, stage: str) -> dict[str, Any]:
        failure = self.repository.reserve(target_id, attempt_id, stage)
        if failure is None:
            return {"status": "already_reserved", "attempt_id": str(UUID(attempt_id))}
        if not self.bot_token or self.owner_chat_id not in self.allowed_chat_ids:
            return self.repository.record_result(
                failure,
                status="failed",
                error_code="NotificationConfigurationError",
                error_message="existing PTW bot or allowlisted owner chat is unavailable",
            )
        if self._emergency_stopped():
            return self.repository.record_result(
                failure,
                status="suppressed",
                error_code="EmergencyStop",
                error_message="outbound notification suppressed by emergency stop",
            )
        try:
            response = self.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.owner_chat_id,
                    "text": self._message(failure),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("ok") is not True or not isinstance(body.get("result"), Mapping):
                raise RuntimeError("Telegram returned an invalid sendMessage response")
            return self.repository.record_result(
                failure,
                status="sent",
                message_id=int(body["result"]["message_id"]),
            )
        except httpx.TimeoutException as error:
            return self.repository.record_result(
                failure,
                status="ambiguous",
                error_code=type(error).__name__,
                error_message="sendMessage timed out; delivery is unknown and was not retried",
            )
        except Exception as error:
            return self.repository.record_result(
                failure,
                status="failed",
                error_code=type(error).__name__,
                error_message="existing PTW bot sendMessage failed",
            )

    def _emergency_stopped(self) -> bool:
        with self.repository.connection() as connection:
            row = connection.execute(
                "SELECT emergency_stop FROM commander_control WHERE singleton"
            ).fetchone()
        return bool(row and row[0])

    def _message(self, failure: Mapping[str, Any]) -> str:
        return "\n".join((
            "<b>PTW Ad creative batch failed</b>",
            f"Target UUID: <code>{escape(str(failure['target_id']))}</code>",
            f"Attempt: {int(failure['attempt_number'])} · <code>{escape(str(failure['attempt_id']))}</code>",
            f"Reason: {escape(str(failure['error_message']))}",
            "The attempt stopped atomically; no partial creative batch was saved.",
            f'<a href="{escape(self.owner_console_url)}?page=ads">Open Ads in Owner Console</a>',
        ))
