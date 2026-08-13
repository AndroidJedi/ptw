import asyncio
import logging
import os
from pathlib import Path
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
SUPPORTED_COMMANDS = {"/ping", "/status", "/version", "/help", "/engineer", "/task"}


def allowed_user_ids() -> set[int]:
    raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    try:
        return {int(value.strip()) for value in raw.split(",") if value.strip()}
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_IDS must contain numeric IDs") from exc


def normalized_command(text: str) -> str:
    first = text.strip().split(maxsplit=1)[0].lower() if text.strip() else ""
    return first.split("@", maxsplit=1)[0]


def engineering_task(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return ""
    task = parts[1].strip()
    if task.startswith("repo=ptw"):
        task = task.removeprefix("repo=ptw").strip()
    return task


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
        attachments = []
        if command in {"/engineer", "/task"}:
            attachments = [row[0] for row in connection.execute(
                """SELECT local_path FROM telegram_attachments WHERE telegram_user_id=%s
                   AND status='pending' AND expires_at>now() AND local_path IS NOT NULL
                   ORDER BY created_at DESC LIMIT 3""", (telegram_user_id,)).fetchall()]
        job_id = connection.execute(
            """
            INSERT INTO jobs (session_id, type, status, requested_by, parameters)
            VALUES (%s, %s, 'queued', %s, %s) RETURNING id
            """,
            (
                session_id,
                "engineer" if command == "/task" else command.removeprefix("/"),
                user_id,
                Jsonb({"chat_id": chat_id, "reply_to_message_id": message_id,
                       "repo": "ptw", "task": engineering_task(text) if command in {"/engineer", "/task"} else ""}),
            ),
        ).fetchone()[0]
        if attachments:
            connection.execute("UPDATE jobs SET parameters=parameters || %s WHERE id=%s", (Jsonb({"attachments":attachments}), job_id))
            connection.execute("UPDATE telegram_attachments SET status='linked',job_id=%s WHERE telegram_user_id=%s AND status='pending' AND local_path=ANY(%s)", (job_id,telegram_user_id,attachments))
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
                    if message.get("photo"):
                        caption_command = normalized_command(message.get("caption", ""))
                        if caption_command == "/creative":
                            message["text"] = message.get("caption", "")
                        else:
                            await persist_photo(client, message)
                        if caption_command not in {"/engineer", "/task", "/creative"}:
                            continue
                        message["text"] = message.get("caption", "")
                    if normalized_command(message.get("text") or "") in {"/creative", "/feedback", "/graph", "/research"}:
                        if (message.get("from") or {}).get("id") not in allowed_user_ids():
                            await send_rejection(client, message, False)
                            continue
                        try:
                            async with httpx.AsyncClient(timeout=60) as bridge:
                                response = await bridge.post(
                                    os.getenv(
                                        "CREATIVE_SERVICE_URL",
                                        "http://ptw-creative-api:8080/internal/telegram/update",
                                    ),
                                    json=update,
                                    headers={"X-PTW-Bridge-Token": token},
                                )
                                response.raise_for_status()
                        except httpx.HTTPError as exc:
                            logger.warning("Creative service forwarding failed: %s", type(exc).__name__)
                            await client.post(
                                "sendMessage",
                                json={"chat_id": message["chat"]["id"], "text": "Creative service is temporarily unavailable."},
                            )
                        continue
                    accepted = await asyncio.to_thread(persist_update, message)
                    if not accepted or normalized_command(message.get("text") or "") not in SUPPORTED_COMMANDS:
                        await send_rejection(client, message, accepted)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Telegram polling failed: %s", type(exc).__name__)
                await asyncio.sleep(5)


async def persist_photo(client: httpx.AsyncClient, message: dict) -> None:
    sender_id = (message.get("from") or {}).get("id")
    chat_id = (message.get("chat") or {}).get("id")
    if sender_id not in allowed_user_ids() or not chat_id:
        return
    photo = message["photo"][-1]
    response = await client.get("getFile", params={"file_id": photo["file_id"]}); response.raise_for_status()
    remote_path = response.json()["result"]["file_path"]
    suffix = Path(remote_path).suffix if Path(remote_path).suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"
    directory = Path(os.getenv("ATTACHMENT_INBOX_ROOT", "/opt/ptw/workspaces/incoming")); directory.mkdir(parents=True, exist_ok=True)
    local = directory / f"{sender_id}-{message['message_id']}{suffix}"
    download = await client.get(f"https://api.telegram.org/file/bot{secrets.get('TELEGRAM_BOT_TOKEN')}/{remote_path}"); download.raise_for_status()
    local.write_bytes(download.content); local.chmod(0o600)
    with psycopg.connect(database_url(secrets)) as connection:
        connection.execute("""INSERT INTO telegram_attachments(telegram_user_id,chat_id,telegram_file_id,file_type,caption,local_path)
                              VALUES(%s,%s,%s,'image',%s,%s)""", (sender_id,chat_id,photo["file_id"],message.get("caption"),str(local)))


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


@app.get("/health")
def public_health() -> dict[str, str]:
    """Minimal public health response; dependency detail remains internal."""
    return {"status": "ok"}


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
