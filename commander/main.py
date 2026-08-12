import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
import psycopg
from psycopg.types.json import Jsonb
from fastapi import FastAPI, HTTPException

from common.database import apply_migrations, database_url
from common.events import append_event
from common.secrets import EnvironmentSecretStore

logging.basicConfig(
    level=os.getenv("PTW_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ptw.commander")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
secrets = EnvironmentSecretStore()
SUPPORTED_COMMANDS = {"/ping", "/status", "/version", "/help"}


def allowed_user_ids() -> set[int]:
    raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    try:
        return {int(value.strip()) for value in raw.split(",") if value.strip()}
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_IDS must contain numeric IDs") from exc


def normalized_command(text: str) -> str:
    first = text.strip().split(maxsplit=1)[0].lower() if text.strip() else ""
    return first.split("@", maxsplit=1)[0]


def persist_update(message: dict) -> bool:
    sender = message.get("from") or {}
    telegram_user_id = sender.get("id")
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    text = message.get("text") or ""
    command = normalized_command(text)
    actor = f"telegram:{telegram_user_id}" if telegram_user_id else "telegram:unknown"

    with psycopg.connect(database_url(secrets)) as connection:
        append_event(
            connection,
            "USER_MESSAGE_RECEIVED",
            actor,
            status="received",
            payload={"message_id": message_id, "command": command or None},
        )
        if telegram_user_id not in allowed_user_ids():
            append_event(
                connection,
                "COMMAND_REJECTED",
                actor,
                status="unauthorized",
                payload={"message_id": message_id, "command": command or None},
            )
            return False
        if command not in SUPPORTED_COMMANDS:
            append_event(
                connection,
                "COMMAND_REJECTED",
                actor,
                status="unsupported",
                payload={"message_id": message_id, "command": command or None},
            )
            return True

        user_id = connection.execute(
            """
            INSERT INTO users (telegram_user_id, role) VALUES (%s, 'operator')
            ON CONFLICT (telegram_user_id) DO UPDATE SET role = users.role
            RETURNING id
            """,
            (telegram_user_id,),
        ).fetchone()[0]
        session_id = connection.execute(
            "INSERT INTO sessions (user_id, status, summary) VALUES (%s, 'active', %s) RETURNING id",
            (user_id, f"Telegram command {command}"),
        ).fetchone()[0]
        append_event(
            connection,
            "COMMAND_ACCEPTED",
            actor,
            status="accepted",
            session_id=session_id,
            payload={"command": command, "message_id": message_id},
        )
        job_id = connection.execute(
            """
            INSERT INTO jobs (session_id, type, status, requested_by, parameters)
            VALUES (%s, %s, 'queued', %s, %s) RETURNING id
            """,
            (
                session_id,
                command.removeprefix("/"),
                user_id,
                Jsonb({"chat_id": chat_id, "reply_to_message_id": message_id}),
            ),
        ).fetchone()[0]
        append_event(
            connection,
            "JOB_CREATED",
            actor,
            status="queued",
            session_id=session_id,
            job_id=job_id,
            payload={"job_type": command.removeprefix("/")},
        )
    return True


async def send_rejection(client: httpx.AsyncClient, message: dict, authorized: bool) -> None:
    chat_id = (message.get("chat") or {}).get("id")
    if not chat_id:
        return
    response = "Unsupported command. Use /help." if authorized else "Unauthorized."
    try:
        await client.post("sendMessage", json={"chat_id": chat_id, "text": response})
    except httpx.HTTPError as exc:
        logger.warning("Telegram rejection response failed: %s", type(exc).__name__)


async def telegram_loop() -> None:
    token = secrets.get("TELEGRAM_BOT_TOKEN")
    base_url = f"https://api.telegram.org/bot{token}/"
    offset: int | None = None
    timeout = httpx.Timeout(35.0, connect=10.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        while True:
            try:
                response = await client.get(
                    "getUpdates", params={"timeout": 25, "offset": offset, "allowed_updates": '["message"]'}
                )
                response.raise_for_status()
                for update in response.json().get("result", []):
                    offset = int(update["update_id"]) + 1
                    message = update.get("message")
                    if not message:
                        continue
                    accepted = await asyncio.to_thread(persist_update, message)
                    if not accepted or normalized_command(message.get("text") or "") not in SUPPORTED_COMMANDS:
                        await send_rejection(client, message, accepted)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Telegram polling failed: %s", type(exc).__name__)
                await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(apply_migrations)
    task = None
    if secrets.exists("TELEGRAM_BOT_TOKEN") and allowed_user_ids():
        task = asyncio.create_task(telegram_loop())
    else:
        logger.warning("Telegram integration disabled: token or allowlist is missing")
    try:
        yield
    finally:
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


app = FastAPI(
    title="PTW Commander", version="0.1.0", docs_url=None, redoc_url=None, lifespan=lifespan
)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "commander-api"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        with psycopg.connect(database_url(secrets), connect_timeout=3) as connection:
            connection.execute("SELECT 1")
            append_event(
                connection, "HEALTH_CHECK", "commander-api", status="ready",
                payload={"check": "readiness"},
            )
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
