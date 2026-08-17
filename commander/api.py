"""Executable FastAPI composition for Telegram Commander."""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import Any, Mapping

from fastapi import FastAPI, Header, HTTPException

from .model import EntityKind
from .model import RelationType
from .policy import CommanderPolicy
from .postgres_store import PostgresKnowledgeStore, connect_postgres
from .service import Commander
from .settings import Settings
from .telegram import TelegramControlPlane, TelegramUnauthorized
from .telegram_api import TelegramBotClient
from .openai_research import CodexCreativeResearchProvider, OpenAICreativeResearchProvider
import os
import re
from .research import CreativeIdeationResearchService
from .checkpoint import checkpoint_response, startup_checkpoint_canary
from .ad_generation import AdGenerationEngine
from .ad_runtime import create_ad_engine


def create_app(
    settings: Settings,
    store: PostgresKnowledgeStore,
    telegram_client: TelegramBotClient,
    ad_engine: AdGenerationEngine | None = None,
) -> FastAPI:
    commander = Commander(store, CommanderPolicy.load(settings.policy_path))
    if ad_engine is None and isinstance(store, PostgresKnowledgeStore):
        ad_engine = create_ad_engine(settings, store, commander)
    research_provider = (
        OpenAICreativeResearchProvider(settings.openai_api_key, model=settings.research_model)
        if settings.openai_api_key
        else CodexCreativeResearchProvider(settings.codex_executable)
        if os.path.isfile(settings.codex_executable)
        else None
    )
    research_service = CreativeIdeationResearchService(commander, research_provider) if research_provider else None
    control = TelegramControlPlane(
        commander,
        allowed_user_ids=set(settings.allowed_user_ids),
        allowed_chat_ids=set(settings.allowed_chat_ids),
        research_service=research_service,
        ad_engine=ad_engine,
    )
    app = FastAPI(title="PTW Commander", version="0.1.0")
    app.state.checkpoint_canary = startup_checkpoint_canary(
        store, settings.checkpoint_max_age_seconds
    )
    app.state.restored_checkpoint = app.state.checkpoint_canary.get("checkpoint")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> dict[str, object]:
        try:
            with store.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as error:
            raise HTTPException(status_code=503, detail="database unavailable") from error
        canary = app.state.checkpoint_canary
        if settings.checkpoint_required and canary["status"] != "fresh":
            raise HTTPException(
                status_code=503,
                detail=f"checkpoint startup canary: {canary['status']}",
            )
        return {"status": "ready", "checkpoint_canary": canary["status"]}

    @app.post("/telegram/webhook")
    def telegram_webhook(
        update: Mapping[str, Any],
        x_telegram_bot_api_secret_token: str = Header(default=""),
    ) -> dict[str, object]:
        if not hmac.compare_digest(
            x_telegram_bot_api_secret_token, settings.telegram_webhook_secret
        ):
            raise HTTPException(status_code=403, detail="invalid webhook secret")
        return _process_update(update)

    @app.post("/internal/telegram/update")
    def internal_telegram_update(
        update: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        # The established PTW poller already owns getUpdates for this bot. It
        # authenticates to this internal-only route with the shared bot token.
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        return _process_update(update)

    @app.post("/internal/emergency-stop")
    def internal_emergency_stop(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, bool]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        active = request.get("active") is True
        with store.transaction():
            commander.set_emergency_stop(
                active, actor=str(request.get("actor") or "owner-gateway")
            )
        return {"emergency_stop": active}

    @app.post("/internal/ad-batches")
    def create_ad_batch(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        if ad_engine is None:
            raise HTTPException(status_code=503, detail="ad generation is not configured")
        try:
            chat_id = int(request.get("chat_id"))
            if chat_id not in settings.allowed_chat_ids:
                raise HTTPException(status_code=403, detail="unauthorized Telegram chat")
            batch = ad_engine.enqueue_batch(
                idea_snapshot=dict(request["idea"]),
                chat_id=chat_id,
                requested_by=str(request.get("requested_by") or "idea-evolution"),
                idempotency_key=str(request["idempotency_key"]),
            )
        except HTTPException:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"batch_id": batch.campaign_id, "status": batch.status}

    @app.post("/internal/ad-batches/{batch_id}/metrics")
    def import_ad_metrics(
        batch_id: str,
        request: Mapping[str, Any],
        x_ptw_bridge_token: str = Header(default=""),
    ) -> Mapping[str, Any]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        if ad_engine is None:
            raise HTTPException(status_code=503, detail="ad generation is not configured")
        try:
            return ad_engine.import_metrics(
                batch_id=batch_id,
                payload=request,
                actor=str(request.get("imported_by") or "analytics-bridge"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/internal/workspace/tasks")
    def register_workspace_task(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        task_id = str(request.get("task_id", "")).strip()
        scope = str(request.get("interpreted_scope", "")).strip()
        session_id = str(request.get("workspace_session_id", "")).strip()
        try:
            chat_id = int(request.get("chat_id"))
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail="chat_id must be numeric") from error
        if not re.fullmatch(r"TASK-[0-9]+", task_id):
            raise HTTPException(status_code=400, detail="task_id must match TASK-<number>")
        if not scope or len(scope) > 2000:
            raise HTTPException(status_code=400, detail="interpreted_scope must be 1-2000 characters")
        if not session_id or len(session_id) > 200:
            raise HTTPException(status_code=400, detail="workspace_session_id must be 1-200 characters")
        if chat_id not in settings.allowed_chat_ids:
            raise HTTPException(status_code=403, detail="unauthorized Telegram chat")
        try:
            record = store.register_workspace_task(
                task_id=task_id,
                interpreted_scope=scope,
                workspace_session_id=session_id,
                chat_id=chat_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _workspace_ack_response(record)

    @app.get("/internal/workspace/tasks/{task_id}/acknowledgement")
    def workspace_task_acknowledgement(
        task_id: str, x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        try:
            record = store.workspace_task_acknowledgement(task_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _workspace_ack_response(record)

    @app.put("/internal/workspace/checkpoint")
    def save_workspace_checkpoint(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        try:
            checkpoint = store.save_session_checkpoint(request)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        app.state.checkpoint_canary = checkpoint_response(
            checkpoint, settings.checkpoint_max_age_seconds
        )
        app.state.restored_checkpoint = checkpoint
        return app.state.checkpoint_canary

    @app.get("/internal/workspace/checkpoint")
    def restore_workspace_checkpoint(
        scope: str = "commander", x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        try:
            checkpoint = store.latest_session_checkpoint(scope)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        result = checkpoint_response(checkpoint, settings.checkpoint_max_age_seconds)
        if result["status"] == "corrupt":
            raise HTTPException(status_code=409, detail="checkpoint integrity check failed")
        return result

    @app.get("/internal/research/context/{hypothesis_id}")
    def research_context(hypothesis_id: str, x_ptw_bridge_token: str = Header(default="")) -> dict[str, object]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        try:
            hypothesis = store.get_entity(hypothesis_id)
            if hypothesis.kind != EntityKind.HYPOTHESIS:
                raise ValueError("research context ID must identify a hypothesis")
            source_ids = [edge.target_id for edge in store.relationships()
                          if edge.source_id == hypothesis.id and edge.relation == RelationType.DERIVED_FROM
                          and store.get_entity(edge.target_id).kind == EntityKind.SOURCE]
            sources = [store.get_entity(source_id) for source_id in source_ids]
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "hypothesis_id": hypothesis.id,
            "owner_agent": hypothesis.attributes.get("owner_agent"),
            "knowledge_domain": hypothesis.attributes.get("knowledge_domain"),
            "research_type": hypothesis.attributes.get("research_type"),
            "claim": hypothesis.attributes.get("claim"),
            "direction": hypothesis.attributes.get("creative_direction"),
            "sources": [{"id": item.id, "title": item.attributes.get("title"),
                         "uri": item.attributes.get("source_uri"),
                         "summary": item.attributes.get("finding_summary")}
                        for item in sources],
        }

    def _process_update(update: Mapping[str, Any]) -> dict[str, object]:
        result: dict[str, object] = {}
        try:
            update_id = int(update["update_id"])
            with store.transaction():
                if not store.record_inbox_once(update_id):
                    return {"ok": True, "duplicate": True}
                reply = control.handle_update(update)
                store.enqueue_outbox(
                    "telegram.send_message", None,
                    {"chat_id": reply.chat_id, "text": reply.text},
                )
                result = {"response": reply.text}
                if reply.callback_query_id:
                    store.enqueue_outbox(
                        "telegram.answer_callback", None,
                        {"callback_query_id": reply.callback_query_id},
                    )
        except TelegramUnauthorized as error:
            raise HTTPException(status_code=403, detail="unauthorized Telegram identity") from error
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"ok": True, "duplicate": False, "result": result}

    return app


def _workspace_ack_response(record: Any) -> dict[str, object]:
    return {
        "task_id": record.task_id,
        "interpreted_scope": record.interpreted_scope,
        "workspace_session_id": record.workspace_session_id,
        "acknowledgement_status": record.status,
        "telegram_message_id": record.telegram_message_id,
        "may_start": record.status == "acknowledged",
    }


def create_app_from_env() -> FastAPI:
    settings = Settings.from_environment()
    store = connect_postgres(settings.database_url)
    return create_app(settings, store, TelegramBotClient(settings.telegram_bot_token))
