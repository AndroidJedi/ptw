"""Public Landing lead persistence and direct existing-bot notification."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import hmac
from html import escape
import json
import re
from typing import Any, Callable, Iterator, Mapping, Sequence
from uuid import UUID

try:  # Keep pure validation tests runnable outside the built runtime image.
    import httpx
except ModuleNotFoundError:  # pragma: no cover - production image installs it
    httpx = None  # type: ignore[assignment]

from commander.ids import new_uuid7
from natal.forms import allowed_field_names, form_definition


EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,253}\.[^\s@]{2,63}$")
TELEGRAM = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")
LIMITS = {"name": 160, "email": 320, "note": 1000, "telegram_handle": 33}


class LandingLeadRepository:
    def __init__(self, database_url: str, ip_hmac_secret: str, *, hourly_limit: int = 5) -> None:
        if len(ip_hmac_secret.encode()) < 32:
            raise RuntimeError("LANDING_LEAD_HMAC_SECRET must contain at least 32 bytes")
        self.database_url = database_url
        self.secret = ip_hmac_secret.encode()
        self.hourly_limit = hourly_limit

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "build_id": str(row[1]), "form_id": row[2],
            "fields": row[3], "submitted_at": row[4].isoformat(),
            "positioning_project_id": str(row[5]), "positioning_revision_id": str(row[6]),
            "template_id": row[7], "public_url": row[8],
        }

    @staticmethod
    def _select() -> str:
        return """SELECT lead.entity_id,lead.build_id,lead.form_id,lead.fields,lead.submitted_at,
                         build.positioning_project_id,build.positioning_revision_id,
                         build.template_id,build.public_url
                  FROM landing_leads lead JOIN landing_builds build ON build.entity_id=lead.build_id"""

    def create(
        self, build_id: str, payload: Mapping[str, Any], *, remote_ip: str
    ) -> tuple[dict[str, Any] | None, bool]:
        from psycopg.types.json import Jsonb
        if str(payload.get("website") or "").strip():
            return None, False
        with self.connection() as connection:
            build = connection.execute(
                """SELECT status,page_content,positioning_project_id,positioning_revision_id
                   FROM landing_builds WHERE entity_id=%s FOR SHARE""",
                (UUID(build_id),),
            ).fetchone()
            if build is None or build[0] != "published":
                raise KeyError(build_id)
            try:
                expected_form = str(build[1]["blocks"]["lead_form"]["form_id"])
            except (KeyError, TypeError) as error:
                raise ValueError("published Landing has no valid lead form") from error
            form_id = str(payload.get("form_id") or "")
            if form_id != expected_form:
                raise ValueError("form_id does not match the published Landing")
            allowed = allowed_field_names(form_id)
            if set(payload) - allowed - {"form_id", "website"}:
                raise ValueError("lead contains fields outside the published form")
            fields = self._fields(form_id, payload)
            ip_hash = hmac.new(self.secret, remote_ip.encode(), hashlib.sha256).hexdigest()
            canonical = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            dedupe = hmac.new(self.secret, f"{build_id}|{form_id}|{canonical}".encode(), hashlib.sha256).hexdigest()
            existing = connection.execute(
                self._select() + " WHERE lead.build_id=%s AND lead.dedupe_sha256=%s",
                (UUID(build_id), dedupe),
            ).fetchone()
            if existing is not None:
                return self._row(existing), False
            count = int(connection.execute(
                """SELECT count(*) FROM landing_leads
                   WHERE ip_hmac=%s AND submitted_at > clock_timestamp() - interval '1 hour'""",
                (ip_hash,),
            ).fetchone()[0])
            if count >= self.hourly_limit:
                raise PermissionError("lead submission rate limit exceeded")
            lead_id = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'lead_submission',%s)",
                (lead_id, Jsonb({"form_id": form_id})),
            )
            connection.execute(
                """INSERT INTO landing_leads(entity_id,build_id,form_id,fields,dedupe_sha256,ip_hmac)
                   VALUES(%s,%s,%s,%s,%s,%s)""",
                (lead_id, UUID(build_id), form_id, Jsonb(fields), dedupe, ip_hash),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'submitted_to',%s,%s)",
                (UUID(new_uuid7()), lead_id, UUID(build_id), Jsonb({"form_id": form_id})),
            )
        return self.get(str(lead_id)), True

    @staticmethod
    def _fields(form_id: str, payload: Mapping[str, Any]) -> dict[str, str]:
        result: dict[str, str] = {}
        definitions = {item["name"]: item for item in form_definition(form_id, "en")["fields"]}
        for name, definition in definitions.items():
            value = str(payload.get(name) or "").strip()
            if definition["required"] and not value:
                raise ValueError(f"{name} is required")
            if len(value) > LIMITS[name]:
                raise ValueError(f"{name} is too long")
            if name == "email" and not EMAIL.fullmatch(value):
                raise ValueError("email is invalid")
            if name == "telegram_handle" and value and not TELEGRAM.fullmatch(value):
                raise ValueError("Telegram handle is invalid")
            if value:
                result[name] = value
        return result

    def get(self, lead_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(self._select() + " WHERE lead.entity_id=%s", (UUID(lead_id),)).fetchone()
        if row is None:
            raise KeyError(lead_id)
        return self._row(row)

    def list(self, limit: int = 100, *, build_id: str | None = None) -> list[dict[str, Any]]:
        suffix, params = "", []
        if build_id:
            suffix = " WHERE lead.build_id=%s"
            params.append(UUID(build_id))
        params.append(min(limit, 100))
        with self.connection() as connection:
            rows = connection.execute(self._select() + suffix + " ORDER BY lead.submitted_at DESC LIMIT %s", params).fetchall()
        return [self._row(row) | {"notification_attempts": self.attempts(str(row[0]))} for row in rows]

    def attempts(self, lead_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT id,attempt_number,status,telegram_chat_id,telegram_message_id,
                          error_code,error_message,created_at,completed_at
                   FROM landing_lead_notification_attempts WHERE lead_id=%s ORDER BY attempt_number""",
                (UUID(lead_id),),
            ).fetchall()
        return [{
            "id": str(row[0]), "attempt_number": int(row[1]), "status": row[2],
            "telegram_chat_id": int(row[3]), "telegram_message_id": row[4],
            "error_code": row[5], "error_message": row[6],
            "created_at": row[7].isoformat(), "completed_at": row[8].isoformat(),
        } for row in rows]

    def record_attempt(
        self,
        lead_id: str,
        *,
        status: str,
        chat_id: int,
        message_id: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"sent", "failed", "ambiguous", "suppressed"}:
            raise ValueError("unknown notification status")
        attempt_id = UUID(new_uuid7())
        with self.connection() as connection:
            number = int(connection.execute(
                "SELECT COALESCE(max(attempt_number),0)+1 FROM landing_lead_notification_attempts WHERE lead_id=%s",
                (UUID(lead_id),),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO landing_lead_notification_attempts(
                       id,lead_id,attempt_number,status,telegram_chat_id,telegram_message_id,error_code,error_message
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (attempt_id, UUID(lead_id), number, status, chat_id, message_id,
                 None if error_code is None else error_code[:100],
                 None if error_message is None else error_message[:1000]),
            )
        return self.attempts(lead_id)[-1]


class ExistingBotLeadNotifier:
    """One direct sendMessage call; this class contains no polling path."""

    def __init__(
        self,
        repository: LandingLeadRepository,
        *,
        bot_token: str,
        owner_chat_id: int,
        allowed_chat_ids: frozenset[int],
        emergency_stopped: Callable[[], bool],
    ) -> None:
        if not bot_token or owner_chat_id not in allowed_chat_ids:
            raise RuntimeError("existing PTW bot and allowlisted owner chat are required")
        self.repository = repository
        self.bot_token = bot_token
        self.owner_chat_id = owner_chat_id
        self.allowed_chat_ids = allowed_chat_ids
        self.emergency_stopped = emergency_stopped

    def notify(self, lead_id: str) -> dict[str, Any]:
        if httpx is None:
            raise RuntimeError("httpx is required for Telegram sendMessage")
        lead = self.repository.get(lead_id)
        prior = self.repository.attempts(lead_id)
        if prior and prior[-1]["status"] == "sent":
            raise ValueError("lead notification was already sent")
        if self.owner_chat_id not in self.allowed_chat_ids:
            raise RuntimeError("notification chat is outside the existing allowlist")
        if self.emergency_stopped():
            return self.repository.record_attempt(
                lead_id, status="suppressed", chat_id=self.owner_chat_id,
                error_code="EmergencyStop", error_message="outbound send suppressed until explicit owner retry",
            )
        message = self._message(lead)
        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": self.owner_chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=20,
            )
            response.raise_for_status()
            body = response.json()
            if body.get("ok") is not True or not isinstance(body.get("result"), Mapping):
                raise RuntimeError("Telegram returned an invalid sendMessage response")
            message_id = int(body["result"]["message_id"])
            return self.repository.record_attempt(
                lead_id, status="sent", chat_id=self.owner_chat_id, message_id=message_id
            )
        except httpx.TimeoutException as error:
            return self.repository.record_attempt(
                lead_id, status="ambiguous", chat_id=self.owner_chat_id,
                error_code=type(error).__name__, error_message="sendMessage timed out; delivery is unknown",
            )
        except Exception as error:
            return self.repository.record_attempt(
                lead_id, status="failed", chat_id=self.owner_chat_id,
                error_code=type(error).__name__, error_message="existing PTW bot sendMessage failed",
            )

    @staticmethod
    def _message(lead: Mapping[str, Any]) -> str:
        lines = [
            "<b>PTW Landing lead</b>",
            f"Lead UUID: <code>{escape(str(lead['id']))}</code>",
            f"Form: <code>{escape(str(lead['form_id']))}</code>",
            f"Landing: <code>{escape(str(lead['build_id']))}</code> ({escape(str(lead['template_id']))})",
            f"Landing URL: {escape(str(lead.get('public_url') or 'unavailable'))}",
            f"Positioning project: <code>{escape(str(lead['positioning_project_id']))}</code>",
            f"Positioning revision: <code>{escape(str(lead['positioning_revision_id']))}</code>",
            f"Submitted: {escape(str(lead['submitted_at']))}",
        ]
        for name, value in lead["fields"].items():
            lines.append(f"{escape(str(name))}: {escape(str(value))}")
        return "\n".join(lines)
