"""Internal HTTP composition for the established PTW Telegram poller."""

from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from typing import Any, Callable, Mapping

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

    def notify(text: str, reply_markup: Mapping[str, Any] | None = None) -> None:
        for chat_id in settings.allowed_chat_ids:
            if sender is not None:
                sender(chat_id, text)
                continue
            body: dict[str, Any] = {"chat_id": chat_id, "text": text[:4096]}
            if reply_markup is not None:
                body["reply_markup"] = reply_markup
            response = httpx.post(
                f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
                json=body, timeout=20,
            )
            response.raise_for_status()

    def submit_ad_batch(
        chat_id: int, idea: Mapping[str, Any], idempotency_key: str
    ) -> Mapping[str, Any]:
        if not settings.ad_batch_bridge_url:
            raise RuntimeError("AD_BATCH_BRIDGE_URL is not configured")
        response = httpx.post(
            settings.ad_batch_bridge_url,
            headers={"X-PTW-Bridge-Token": settings.telegram_token},
            json={
                "chat_id": chat_id,
                "requested_by": "idea-evolution",
                "idempotency_key": idempotency_key,
                "idea": dict(idea),
            },
            timeout=30,
        )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = None
            raise RuntimeError(detail or f"Commander ad bridge returned HTTP {response.status_code}")
        result = response.json()
        if not isinstance(result, Mapping) or not result.get("batch_id"):
            raise RuntimeError("Commander ad bridge returned an invalid response")
        return result

    engine = EvolutionEngine(store, _provider(settings), notify)
    controller = TelegramController(
        store, engine, settings.allowed_chat_ids, ad_batch_submitter=submit_ad_batch
    )

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
        callback = update.get("callback_query") or {}
        message = update.get("message") or callback.get("message") or {}
        sender_id = ((update.get("message") or callback).get("from") or {}).get("id")
        chat_id = (message.get("chat") or {}).get("id")
        text = callback.get("data") or message.get("text") or message.get("caption") or ""
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
        result = controller.handle(
            int(chat_id), text, idempotency_key=f"telegram-update:{update_id}"
        )
        store.execute(
            "UPDATE telegram_inbox SET response_text=%s,completed_at=NOW() WHERE update_id=%s RETURNING update_id",
            (result, update_id),
        )
        try:
            markup = None
            command, _, raw_id = str(text).strip().partition(" ")
            if (
                command.split("@", 1)[0].lower() == "/idea"
                and raw_id.strip().isdigit()
                and not result.startswith("Idea not found")
            ):
                markup = {
                    "inline_keyboard": [[{
                        "text": "Generate 10 ads",
                        "callback_data": f"/ads from {int(raw_id)}",
                    }]]
                }
            notify(result, markup)
            if callback.get("id") and sender is None:
                answer = httpx.post(
                    f"https://api.telegram.org/bot{settings.telegram_token}/answerCallbackQuery",
                    json={"callback_query_id": callback["id"]},
                    timeout=20,
                )
                answer.raise_for_status()
        except Exception as error:
            raise HTTPException(status_code=503, detail="Telegram send failed") from error
        return {"ok": True}

    return app
