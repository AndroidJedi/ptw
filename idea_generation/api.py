"""Internal HTTP composition for the established PTW Telegram poller."""

from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from typing import Any, Callable

import httpx
from fastapi import FastAPI, Header, HTTPException

from .config import Settings
from .engine import EvolutionEngine
from .manage import ROOT
from .provider import BridgeProvider, MockLLMProvider, OpenAIProvider
from .seeds import load
from .store import PostgresStore
from .telegram import TelegramController


def _provider(settings: Settings):
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.openai_api_key, settings.llm_model)
    if settings.llm_provider == "bridge":
        return BridgeProvider(settings.llm_bridge_url, settings.telegram_token)
    raise RuntimeError("LLM_PROVIDER must be mock, openai, or bridge")


def create_app(
    settings: Settings | None = None,
    sender: Callable[[int, str], None] | None = None,
) -> FastAPI:
    settings = settings or Settings.from_environment()
    store = PostgresStore(settings.database_url)
    store.migrate(ROOT / "db/idea_generation")
    mission, contexts = load(ROOT / "ideaGeneration")
    store.seed(mission, contexts)

    def notify(text: str) -> None:
        for chat_id in settings.allowed_chat_ids:
            if sender is not None:
                sender(chat_id, text)
                continue
            response = httpx.post(
                f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4096]}, timeout=20,
            )
            response.raise_for_status()

    engine = EvolutionEngine(store, _provider(settings), notify)
    controller = TelegramController(store, engine, settings.allowed_chat_ids)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        controller.resume_queued_work()
        yield

    app = FastAPI(title="PTW Idea Evolution", version="1.1.0", docs_url=None, redoc_url=None, lifespan=lifespan)

    @app.get("/healthz")
    def health() -> dict[str, Any]:
        current = store.mission()
        return {
            "status": "ok",
            "mission": current["status"],
            "contexts": len(store.active_contexts()),
            "autopilot": bool(current["auto_enabled"]),
            "generations": store.fetchone("SELECT COUNT(*) n FROM generations WHERE status='completed'")["n"],
            "pending_owner_ideas": store.fetchone(
                "SELECT COUNT(*) n FROM idea_submissions WHERE status='pending'"
            )["n"],
        }

    @app.post("/internal/telegram/update")
    def telegram_update(update: dict[str, Any], x_ptw_bridge_token: str = Header(default="")) -> dict[str, bool]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        message = update.get("message") or {}
        sender_id = (message.get("from") or {}).get("id")
        chat_id = (message.get("chat") or {}).get("id")
        text = message.get("text") or message.get("caption") or ""
        if sender_id not in settings.allowed_user_ids or chat_id not in settings.allowed_chat_ids:
            raise HTTPException(status_code=403, detail="unauthorized")
        try:
            update_id = int(update["update_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail="numeric update_id is required") from error
        recorded = store.execute(
            "INSERT INTO telegram_inbox(update_id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING update_id",
            (update_id,),
        )
        if recorded is None:
            previous = store.fetchone("SELECT response_text FROM telegram_inbox WHERE update_id=%s", (update_id,))
            if previous and previous["response_text"]:
                notify(previous["response_text"])
            return {"ok": True, "duplicate": True}
        result = controller.handle(int(chat_id), text)
        store.execute(
            "UPDATE telegram_inbox SET response_text=%s,completed_at=NOW() WHERE update_id=%s RETURNING update_id",
            (result, update_id),
        )
        try:
            notify(result)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Telegram send failed") from error
        return {"ok": True}

    return app
