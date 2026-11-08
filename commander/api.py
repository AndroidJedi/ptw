"""Minimal Commander boundary for readiness and established Telegram emergency controls."""

from __future__ import annotations

import hmac
from typing import Any, Mapping
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException

from .agent_bot import AgentBotService
from .settings import Settings


def telegram_command(raw: str) -> str:
    first = raw.strip().partition(" ")[0].split("@", 1)[0].lower()
    return first if first in {"/help", "/status", "/stop"} else ""


def create_app(settings: Settings, *, agent_bot_service: AgentBotService | None = None) -> FastAPI:
    app = FastAPI(title="PTW Commander", version="2.0.0", docs_url=None, redoc_url=None)
    bot_service = agent_bot_service

    def agent_bot() -> AgentBotService:
        nonlocal bot_service
        if bot_service is None:
            bot_service = AgentBotService(settings.database_url)
            app.state.agent_bot = bot_service
        return bot_service

    def owner_gateway_authorize(token: str) -> None:
        if not settings.owner_gateway_bridge_token or not hmac.compare_digest(token, settings.owner_gateway_bridge_token):
            raise HTTPException(status_code=401, detail="invalid owner gateway token")

    def connection() -> Any:
        import psycopg
        return psycopg.connect(settings.database_url, connect_timeout=5)

    def authorize(token: str) -> None:
        if not hmac.compare_digest(token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")

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
                     (SELECT count(*) FROM product_briefs)"""
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
            raise HTTPException(status_code=503, detail="validation database unavailable") from error
        return {"status": "ready", "domain": "brief_v1", **current}

    @app.get("/internal/v1/agent-bot")
    def agent_bot_status(x_ptw_owner_gateway_token: str = Header(default="")) -> dict[str, Any]:
        owner_gateway_authorize(x_ptw_owner_gateway_token)
        return agent_bot().status()

    @app.post("/internal/v1/agent-bot/conversations", status_code=201)
    def create_agent_bot_conversation(
        request: Mapping[str, Any], x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        owner_gateway_authorize(x_ptw_owner_gateway_token)
        if set(request) - {"title"} or (request.get("title") is not None and not isinstance(request.get("title"), str)):
            raise HTTPException(status_code=400, detail="Only an optional conversation title is accepted")
        return agent_bot().create_conversation(str(request.get("title") or ""))

    @app.get("/internal/v1/agent-bot/conversations/{conversation_id}")
    def agent_bot_conversation(
        conversation_id: UUID, x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        owner_gateway_authorize(x_ptw_owner_gateway_token)
        try:
            return agent_bot().conversation(str(conversation_id))
        except KeyError:
            raise HTTPException(status_code=404, detail="Commander Bot conversation not found") from None

    @app.post("/internal/v1/agent-bot/conversations/{conversation_id}/messages", status_code=202)
    def send_agent_bot_message(
        conversation_id: UUID, request: Mapping[str, Any], x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        owner_gateway_authorize(x_ptw_owner_gateway_token)
        if set(request) != {"request_id", "message"}:
            raise HTTPException(status_code=400, detail="request_id and message are required")
        try:
            return agent_bot().send_message(str(conversation_id), str(UUID(str(request["request_id"]))), str(request["message"]))
        except KeyError:
            raise HTTPException(status_code=404, detail="Commander Bot conversation not found") from None
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.post("/internal/v1/agent-bot/conversations/{conversation_id}/actions/{action_id}")
    def decide_agent_bot_action(
        conversation_id: UUID, action_id: UUID, request: Mapping[str, Any],
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        owner_gateway_authorize(x_ptw_owner_gateway_token)
        if set(request) != {"decision"} or request.get("decision") not in {"approved", "rejected"}:
            raise HTTPException(status_code=400, detail="decision must be approved or rejected")
        try:
            return agent_bot().decide_action(str(conversation_id), str(action_id), str(request["decision"]))
        except KeyError:
            raise HTTPException(status_code=404, detail="Commander Bot action not found") from None
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.post("/internal/v1/agent-bot/conversations/{conversation_id}/tasks/{task_id}/stop", status_code=202)
    def stop_agent_bot_task(
        conversation_id: UUID, task_id: UUID, x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        owner_gateway_authorize(x_ptw_owner_gateway_token)
        try:
            return agent_bot().stop_task(str(conversation_id), str(task_id))
        except KeyError:
            raise HTTPException(status_code=404, detail="Commander Bot conversation not found") from None

    @app.on_event("shutdown")
    def close_agent_bot() -> None:
        if bot_service is not None:
            bot_service.close()

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

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
