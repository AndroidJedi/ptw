"""Executable FastAPI composition for Telegram Commander."""

from __future__ import annotations

import hmac
from pathlib import Path
from typing import Any, Mapping

from fastapi import FastAPI, Header, HTTPException

from .creative_service import CreativeProductionService
from .model import EntityKind
from .model import RelationType
from .policy import CommanderPolicy
from .postgres_store import PostgresKnowledgeStore, connect_postgres
from .renderer import InstagramStoryRenderer
from .service import Commander
from .settings import Settings
from .store import KnowledgeStore
from .telegram import TelegramControlPlane, TelegramUnauthorized
from .telegram_api import TelegramBotClient
from .openai_research import CodexCreativeResearchProvider, OpenAICreativeResearchProvider
import os
from .research import CreativeIdeationResearchService


def create_app(
    settings: Settings,
    store: PostgresKnowledgeStore,
    telegram_client: TelegramBotClient,
) -> FastAPI:
    commander = Commander(store, CommanderPolicy.load(settings.policy_path))
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
    )
    renderer = InstagramStoryRenderer(settings.asset_directory / "generated")
    production = CreativeProductionService(commander, renderer)
    app = FastAPI(title="PTW Commander", version="0.1.0")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> dict[str, str]:
        try:
            with store.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as error:
            raise HTTPException(status_code=503, detail="database unavailable") from error
        return {"status": "ready"}

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
            update = _expand_feedback_reply(update, store)
            update_id = int(update["update_id"])
            with store.transaction():
                if not store.record_inbox_once(update_id):
                    return {"ok": True, "duplicate": True}
                if _is_creative(update):
                    chat_id, user_id, text, file_id = _creative_request(update)
                    control.authorize(user_id, chat_id)
                    text_hook_result = production.text_hook_from_request(
                        text, requested_by=f"telegram:{user_id}"
                    )
                    if text_hook_result is not None:
                        text_hook, text_creative = text_hook_result
                        store.enqueue_outbox(
                            "telegram.send_message", None,
                            {"chat_id": chat_id, "text": text_hook},
                        )
                        result = {"hook": text_hook, "creative_id": text_creative.id}
                        return {"ok": True, "duplicate": False, "result": result}
                    hero = None
                    if file_id:
                        hero = telegram_client.download_photo(
                            file_id,
                            settings.asset_directory / "incoming" / f"telegram-{update_id}.jpg",
                        )
                    creative, artifact, path = production.create_instagram_story(
                        request_text=text,
                        requested_by=f"telegram:{user_id}",
                        hero_image=hero,
                        hypothesis=production.hypothesis_from_request(text),
                    )
                    store.enqueue_outbox(
                        "telegram.send_photo",
                        artifact.id,
                        {
                            "chat_id": chat_id,
                            "path": str(path),
                            "caption": (
                                f"Creative {creative.id}\n"
                                + (f"TASK-{update['_ptw_task_id']} completed.\n" if update.get("_ptw_task_id") is not None else "")
                                + "Ready for review; not published.\n\n"
                                "Reply to this image with:\n/feedback 1-5 optional comment"
                            ),
                            "creative_id": creative.id,
                        },
                    )
                    result = {"creative_id": creative.id, "artifact_id": artifact.id}
                else:
                    reply = control.handle_update(update)
                    task_id = update.get("_ptw_task_id")
                    reply_text = (
                        f"TASK-{task_id} completed.\n{reply.text}"
                        if task_id is not None else reply.text
                    )
                    store.enqueue_outbox(
                        "telegram.send_message", None,
                        {"chat_id": reply.chat_id, "text": reply_text},
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


def create_app_from_env() -> FastAPI:
    settings = Settings.from_environment()
    store = connect_postgres(settings.database_url)
    return create_app(settings, store, TelegramBotClient(settings.telegram_bot_token))


def _message(update: Mapping[str, Any]) -> Mapping[str, Any]:
    message = update.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("creative command requires a Telegram message")
    return message


def _is_creative(update: Mapping[str, Any]) -> bool:
    message = update.get("message")
    if not isinstance(message, Mapping):
        return False
    value = str(message.get("caption") or message.get("text") or "")
    return value.strip().lower().startswith("/creative")


def _creative_request(update: Mapping[str, Any]) -> tuple[int, int, str, str | None]:
    message = _message(update)
    photos = message.get("photo") or []
    file_id = str(photos[-1]["file_id"]) if photos else None
    return (
        int(message["chat"]["id"]),
        int(message["from"]["id"]),
        str(message.get("caption") or message.get("text") or ""),
        file_id,
    )


def _expand_feedback_reply(
    update: Mapping[str, Any], store: KnowledgeStore
) -> Mapping[str, Any]:
    message = update.get("message")
    if not isinstance(message, Mapping):
        return update
    text = str(message.get("text") or "").strip()
    parts = text.split(maxsplit=2)
    if not parts or parts[0].split("@", 1)[0].lower() != "/feedback":
        return update
    if len(parts) >= 2 and parts[1].isdigit():
        reply = message.get("reply_to_message")
        if not isinstance(reply, Mapping):
            raise ValueError("reply to a generated creative, or include its UUID")
        chat_id = int(message["chat"]["id"])
        entity_id = store.telegram_delivery_entity(chat_id, int(reply["message_id"]))
        if entity_id is None:
            entity_id = _creative_id_from_reply(reply, store)
        if entity_id is None:
            raise ValueError("the replied message is not a known generated creative")
        expanded = dict(update)
        expanded_message = dict(message)
        comment = f" {parts[2]}" if len(parts) > 2 else ""
        expanded_message["text"] = f"/feedback {entity_id} {parts[1]}{comment}"
        expanded["message"] = expanded_message
        return expanded
    return update


def _creative_id_from_reply(
    reply: Mapping[str, Any], store: KnowledgeStore
) -> str | None:
    """Recover delivery lineage from the caption on older generated photos."""

    first_line = str(reply.get("caption") or "").partition("\n")[0]
    prefix = "Creative "
    if not first_line.startswith(prefix):
        return None
    try:
        creative = store.get_entity(first_line.removeprefix(prefix))
    except KeyError:
        return None
    return creative.id if creative.kind == EntityKind.CREATIVE else None
