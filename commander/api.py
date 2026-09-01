"""Minimal Commander boundary for readiness and established Telegram emergency controls."""

from __future__ import annotations

import hmac
import json
from typing import Any, Mapping
from urllib import error, parse, request

from fastapi import FastAPI, Header, HTTPException

from .settings import Settings


def telegram_command(raw: str) -> str:
    first = raw.strip().partition(" ")[0].split("@", 1)[0].lower()
    return first if first in {"/help", "/status", "/stop"} else ""


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="PTW Commander", version="2.0.0", docs_url=None, redoc_url=None)

    def connection() -> Any:
        import psycopg
        return psycopg.connect(settings.database_url, connect_timeout=5)

    def authorize(token: str) -> None:
        if not hmac.compare_digest(token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")

    def authorize_internal(authorization: str) -> None:
        expected = f"Bearer {settings.internal_bridge_token}"
        if not settings.internal_bridge_token or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=403, detail="invalid internal notification token")

    def status() -> dict[str, Any]:
        import psycopg
        with connection() as database:
            control = database.execute(
                "SELECT emergency_stop,updated_at FROM commander_control WHERE singleton"
            ).fetchone()
            operation = database.execute(
                "SELECT operation_kind,operation_id FROM commander_operation_guard WHERE singleton"
            ).fetchone()
            counts = database.execute(
                """SELECT
                     (SELECT count(*) FROM validation_projects),
                     (SELECT count(*) FROM product_briefs),
                     (SELECT count(*) FROM content_generation_runs),
                     (SELECT count(*) FROM content_generation_runs WHERE status='approved')"""
            ).fetchone()
        with psycopg.connect(settings.platform_database_url, connect_timeout=5) as platform:
            platform_control = platform.execute(
                "SELECT emergency_stop FROM platform_control WHERE singleton=true"
            ).fetchone()
        return {
            "emergency_stop": bool(platform_control and platform_control[0]),
            "updated_at": None if not control else control[1].isoformat(),
            "active_operation": None if not operation or operation[1] is None else {
                "kind": operation[0], "id": str(operation[1]),
            },
            "validation_projects": int(counts[0]),
            "product_briefs": int(counts[1]),
            "result_runs": int(counts[2]),
            "results": int(counts[3]),
        }

    def set_stop(active: bool, actor: str) -> None:
        with connection() as database:
            database.execute(
                """UPDATE commander_control SET emergency_stop=%s,updated_by=%s,
                       updated_at=clock_timestamp() WHERE singleton""",
                (active, actor[:200]),
            )

    def set_platform_stop(actor: str) -> None:
        import psycopg
        with psycopg.connect(settings.platform_database_url, connect_timeout=5) as platform:
            platform.execute(
                """INSERT INTO platform_control(singleton,emergency_stop,updated_at,updated_by)
                   VALUES(true,true,now(),%s)
                   ON CONFLICT(singleton) DO UPDATE SET emergency_stop=true,
                     updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
                (actor[:200],),
            )
            platform.execute(
                """UPDATE jobs SET
                     status=CASE WHEN status='queued' THEN 'cancelled' ELSE 'cancel_requested' END,
                     finished_at=CASE WHEN status='queued' THEN now() ELSE finished_at END
                   WHERE status IN ('queued','running','blocked')"""
            )

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> dict[str, Any]:
        try:
            current = status()
        except Exception as error:
            raise HTTPException(status_code=503, detail="Result database unavailable") from error
        return {"status": "ready", "domain": "result_v1", **current}

    @app.post("/internal/emergency-stop")
    def internal_emergency_stop(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, bool]:
        authorize(x_ptw_bridge_token)
        if set(request) != {"active", "actor"} or not isinstance(request.get("active"), bool):
            raise HTTPException(status_code=400, detail="active boolean and actor are required")
        set_stop(bool(request["active"]), str(request["actor"] or "owner-gateway"))
        return {"emergency_stop": bool(request["active"])}

    @app.post("/internal/telegram/update")
    def internal_telegram_update(
        update: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        # The established root-owned poller is the only getUpdates owner. This
        # endpoint performs no polling and sends no Telegram message itself.
        authorize(x_ptw_bridge_token)
        message = update.get("message")
        if not isinstance(message, Mapping):
            raise HTTPException(status_code=400, detail="update has no supported message")
        try:
            user_id = int((message.get("from") or {})["id"])
            chat_id = int((message.get("chat") or {})["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail="Telegram identity is invalid") from error
        if user_id not in settings.allowed_user_ids or chat_id not in settings.allowed_chat_ids:
            raise HTTPException(status_code=403, detail="unauthorized Telegram identity")
        raw = str(message.get("text") or message.get("caption") or "").strip()
        command = telegram_command(raw)
        if command == "/help":
            reply = f"PTW Telegram: /help, /status, /stop.\nAll normal work: {settings.owner_web_url}"
        elif command == "/status":
            current = status()
            reply = (
                f"Commander {'STOPPED' if current['emergency_stop'] else 'active'}\n"
                f"Active operation: {current['active_operation'] or 'none'}\n"
                f"Web: {settings.owner_web_url}"
            )
        elif command == "/stop":
            set_platform_stop(f"telegram:{user_id}")
            set_stop(True, f"telegram:{user_id}")
            reply = f"Emergency stop enabled. Recovery and all other controls: {settings.owner_web_url}"
        else:
            reply = f"This command is available only in the web console: {settings.owner_web_url}"
        return {"ok": True, "duplicate": False, "result": {"response": reply}}

    @app.post("/internal/review-notifications")
    def internal_review_notification(
        event: Mapping[str, Any], authorization: str = Header(default=""),
    ) -> dict[str, Any]:
        authorize_internal(authorization)
        expected = {
            "schema", "notification_id", "run_id", "project_id", "project_name",
            "platform", "creative_count",
        }
        if set(event) != expected or event.get("schema") != "ptw.owner-review-notification.v1":
            raise HTTPException(status_code=400, detail="review notification fields do not match v1")
        if int(event.get("creative_count") or 0) != 5:
            raise HTTPException(status_code=400, detail="owner review notification requires five posts")
        project_name = " ".join(str(event["project_name"] or "").split())[:160]
        platform = " ".join(str(event["platform"] or "").split())[:40]
        deep_link = (
            f"{settings.owner_web_url}/?"
            + parse.urlencode({
                "project": str(event["project_id"]), "run": str(event["run_id"]),
                "view": "result-review",
            })
        )
        message = f"{project_name} · {platform}\nfive posts ready\n{deep_link}"
        body = json.dumps({
            "chat_id": settings.owner_chat_id, "text": message,
            "disable_web_page_preview": True,
        }, separators=(",", ":")).encode()
        outgoing = request.Request(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            data=body, method="POST", headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(outgoing, timeout=10) as response:
                value = json.loads(response.read().decode())
        except error.HTTPError as failure:
            return {
                "status": "definite_failure", "provider_message_id": None,
                "error_code": f"telegram_http_{failure.code}",
                "error_message": "Telegram rejected the notification request",
            }
        except (TimeoutError, error.URLError, OSError, json.JSONDecodeError) as failure:
            return {
                "status": "ambiguous", "provider_message_id": None,
                "error_code": type(failure).__name__,
                "error_message": "Telegram delivery outcome is unknown",
            }
        result = value.get("result") if isinstance(value, Mapping) else None
        if value.get("ok") is not True or not isinstance(result, Mapping):
            return {
                "status": "definite_failure", "provider_message_id": None,
                "error_code": "telegram_not_ok", "error_message": "Telegram did not accept the message",
            }
        return {
            "status": "delivered", "provider_message_id": str(result.get("message_id")),
            "error_code": None, "error_message": None,
        }

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
