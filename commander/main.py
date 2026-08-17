import asyncio
import logging
import os
import re
import hmac
from pathlib import Path
from contextlib import asynccontextmanager

import httpx
import psycopg
from psycopg.types.json import Jsonb
from fastapi import FastAPI, HTTPException, Header

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
SUPPORTED_COMMANDS = {"/ping", "/status", "/version", "/help", "/engineer", "/task", "/cancel", "/inspect"}
TRACKED_BRIDGE_COMMANDS = frozenset({"/creative", "/research"})
COMMANDER_BRIDGE_COMMANDS = frozenset({
    "/creative", "/graph", "/research", "/estimate", "/ad_contexts",
})
IDEA_COMMANDS = frozenset({
    "/status", "/run", "/stop", "/continue", "/pause", "/resume", "/autopilot",
    "/ranking", "/generation", "/idea", "/top", "/history", "/lineage", "/report",
    "/reports", "/idea_add", "/idea_done", "/idea_abort", "/idea_queue", "/idea_cancel", "/guidance",
    "/guidance_list", "/guidance_clear", "/feedback", "/keep", "/reject", "/contexts",
    "/context", "/context_set", "/context_name", "/context_history", "/context_restore",
    "/context_enable", "/context_disable", "/executions", "/errors", "/cost", "/task", "/help",
})


def bridge_target(command: str, text: str) -> str | None:
    """Select the internal owner for a Telegram command without another poller."""
    if command == "/ads":
        argument = text.strip().split(maxsplit=2)
        return "idea" if len(argument) > 1 and argument[1].lower() == "from" else "commander"
    if command in COMMANDER_BRIDGE_COMMANDS or command.startswith("/ad_context"):
        return "commander"
    if command in IDEA_COMMANDS or not command.startswith("/"):
        return "idea"
    return None


def bridge_service_url(target: str) -> str:
    if target == "commander":
        return os.getenv(
            "CREATIVE_SERVICE_URL",
            "http://ptw-commander-api:8080/internal/telegram/update",
        )
    return os.getenv(
        "IDEA_SERVICE_URL",
        "http://ptw-idea-api:8080/internal/telegram/update",
    )


def safe_bridge_error(error: Exception) -> str:
    value = f"{type(error).__name__}: {str(error)[-2000:]}"
    return re.sub(
        r"(?i)(token|password|secret|api[_-]?key|authorization)(\s*[:=]\s*)(\S+)",
        r"\1\2[REDACTED]", value,
    )


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


def task_research_reference(task: str) -> tuple[str | None, str]:
    if not task.lower().startswith("from "):
        return None, task
    parts = task.split(maxsplit=2)
    if len(parts) < 3:
        raise ValueError("usage: /task from <hypothesis-id> <request>")
    return parts[1], parts[2]


def fetch_research_context(hypothesis_id: str) -> dict:
    response = httpx.get(
        os.getenv("CREATIVE_SERVICE_URL", "http://ptw-creative-api:8080/internal/telegram/update")
        .replace("/telegram/update", f"/research/context/{hypothesis_id}"),
        headers={"X-PTW-Bridge-Token": secrets.get("TELEGRAM_BOT_TOKEN")}, timeout=15,
    )
    response.raise_for_status()
    context = response.json()
    if context.get("owner_agent") == "marketing.creative.instagram":
        raise ValueError("creative research must be consumed with /creative from <hypothesis-id>")
    return context


def persist_update(message: dict) -> bool | int:
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

        if command == "/cancel":
            requested = engineering_task(text)
            if requested and not requested.isdigit():
                return True
            target_clause = "AND j.id = %s" if requested else ""
            target_params = (int(requested),) if requested else ()
            row = connection.execute(
                f"""SELECT j.id, j.session_id, j.status FROM jobs j
                    JOIN users u ON u.id = j.requested_by
                    WHERE u.telegram_user_id = %s AND j.type = 'engineer'
                      AND j.status IN ('queued','running','blocked','cancel_requested') {target_clause}
                    ORDER BY j.id DESC LIMIT 1 FOR UPDATE""",
                (telegram_user_id, *target_params),
            ).fetchone()
            if row is None:
                return True
            job_id, session_id, status = row
            new_status = "cancelled" if status == "queued" else "cancel_requested"
            connection.execute(
                "UPDATE jobs SET status=%s, finished_at=CASE WHEN %s='cancelled' THEN now() ELSE finished_at END WHERE id=%s",
                (new_status, new_status, job_id),
            )
            append_event(connection, "JOB_CANCEL_REQUESTED", actor, status=new_status,
                         session_id=session_id, job_id=job_id)
            return -job_id

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
        task_text = engineering_task(text) if command in {"/engineer", "/task", "/inspect"} else ""
        research_context = None
        if command in {"/engineer", "/task"}:
            research_id, task_text = task_research_reference(task_text)
            if research_id:
                research_context = fetch_research_context(research_id)
        parameters = {"chat_id": chat_id, "reply_to_message_id": message_id,
                      "repo": "ptw", "task": task_text}
        if research_context:
            parameters["research_context"] = research_context
        job_id = connection.execute(
            """
            INSERT INTO jobs (session_id, type, status, requested_by, parameters)
            VALUES (%s, %s, 'queued', %s, %s) RETURNING id
            """,
            (
                session_id,
                "engineer" if command == "/task" else command.removeprefix("/"),
                user_id,
                Jsonb(parameters),
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
    return job_id


def persist_bridge_task(message: dict, command: str) -> int:
    """Create a durable task before forwarding a long creative command."""
    sender = message.get("from") or {}
    telegram_user_id = int(sender["id"])
    chat_id = int((message.get("chat") or {})["id"])
    text = str(message.get("text") or message.get("caption") or "")
    with psycopg.connect(database_url(secrets)) as connection:
        user_id = connection.execute(
            """INSERT INTO users(telegram_user_id,role) VALUES(%s,'operator')
               ON CONFLICT(telegram_user_id) DO UPDATE SET role=users.role RETURNING id""",
            (telegram_user_id,),
        ).fetchone()[0]
        session_id = connection.execute(
            """INSERT INTO sessions(user_id,status,summary)
               VALUES(%s,'active',%s) RETURNING id""",
            (user_id, f"Telegram command {command}"),
        ).fetchone()[0]
        job_id = connection.execute(
            """INSERT INTO jobs(session_id,type,status,requested_by,parameters,stage,started_at)
               VALUES(%s,%s,'running',%s,%s,'BRIDGE',now()) RETURNING id""",
            (session_id, command.removeprefix("/"), user_id,
             Jsonb({"chat_id": chat_id, "reply_to_message_id": message.get("message_id"),
                    "task": text})),
        ).fetchone()[0]
        append_event(connection, "JOB_CREATED", f"telegram:{telegram_user_id}", status="queued",
                     session_id=session_id, job_id=job_id, payload={"job_type": command.removeprefix("/")})
        append_event(connection, "JOB_STARTED", "commander-api", status="running",
                     session_id=session_id, job_id=job_id, payload={"stage": "BRIDGE"})
    return job_id


def complete_bridge_task(job_id: int, result: dict) -> None:
    with psycopg.connect(database_url(secrets)) as connection:
        session_id = connection.execute(
            """UPDATE jobs SET status='completed',stage='RESULT_RECORDED',result=%s,finished_at=now()
               WHERE id=%s RETURNING session_id""",
            (Jsonb(result), job_id),
        ).fetchone()[0]
        append_event(connection, "JOB_COMPLETED", "commander-api", status="completed",
                     session_id=session_id, job_id=job_id,
                     payload={"result_keys": sorted(result)})
        connection.execute("UPDATE sessions SET status='completed',updated_at=now() WHERE id=%s", (session_id,))


def fail_bridge_task(job_id: int, stage: str, error: Exception) -> int:
    """Persist an unresolved bridge issue without placing secrets in task errors."""
    summary = safe_bridge_error(error)
    with psycopg.connect(database_url(secrets)) as connection:
        issue_id = connection.execute(
            """INSERT INTO engineering_issues(job_id,stage,status,error_type,summary,resolution_summary,resolved_at)
               VALUES(%s,%s,'unresolved',%s,%s,%s,now()) RETURNING id""",
            (job_id, stage, type(error).__name__, summary,
             "Bridge retry was exhausted; the research task requires inspection"),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO engineering_issue_logs(issue_id,level,message,metadata)
               VALUES(%s,'error',%s,'{}'::jsonb)""", (issue_id, summary),
        )
        session_id = connection.execute(
            """UPDATE jobs SET status='failed',stage=%s,error_code=%s,error_message=%s,finished_at=now()
               WHERE id=%s RETURNING session_id""",
            (stage, type(error).__name__, f"ISSUE-{issue_id}: inspect sanitized issue log", job_id),
        ).fetchone()[0]
        append_event(connection, "ISSUE_CREATED", "commander-api", status="unresolved",
                     session_id=session_id, job_id=job_id,
                     payload={"issue_id": issue_id, "stage": stage, "error_type": type(error).__name__})
        append_event(connection, "JOB_FAILED", "commander-api", status="failed",
                     session_id=session_id, job_id=job_id, payload={"issue_id": issue_id})
        connection.execute("UPDATE sessions SET status='failed',updated_at=now() WHERE id=%s", (session_id,))
    return issue_id


def open_bridge_issue(job_id: int, stage: str, error: Exception) -> int:
    summary = safe_bridge_error(error)
    with psycopg.connect(database_url(secrets)) as connection:
        issue_id = connection.execute(
            """INSERT INTO engineering_issues(job_id,stage,status,error_type,summary,attempt_count)
               VALUES(%s,%s,'resolving',%s,%s,1) RETURNING id""",
            (job_id, stage, type(error).__name__, summary),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO engineering_issue_logs(issue_id,level,message,metadata)
               VALUES(%s,'warning',%s,'{"attempt":1}'::jsonb)""", (issue_id, summary),
        )
        session_id = connection.execute(
            "UPDATE jobs SET status='blocked',stage=%s WHERE id=%s RETURNING session_id",
            (stage, job_id),
        ).fetchone()[0]
        append_event(connection, "ISSUE_CREATED", "commander-api", status="resolving",
                     session_id=session_id, job_id=job_id,
                     payload={"issue_id": issue_id, "stage": stage, "error_type": type(error).__name__})
        append_event(connection, "TASK_BLOCKED", "commander-api", status="blocked",
                     session_id=session_id, job_id=job_id, payload={"issue_id": issue_id})
    return issue_id


def resolve_bridge_issue(job_id: int, issue_id: int) -> None:
    with psycopg.connect(database_url(secrets)) as connection:
        connection.execute(
            """UPDATE engineering_issues SET status='resolved',resolution_summary=%s,
                      resolved_at=now(),updated_at=now() WHERE id=%s""",
            ("Bridge retry completed successfully", issue_id),
        )
        connection.execute(
            """INSERT INTO engineering_issue_logs(issue_id,level,message,metadata)
               VALUES(%s,'info','Bridge retry completed successfully','{"attempt":2}'::jsonb)""",
            (issue_id,),
        )
        session_id = connection.execute(
            "UPDATE jobs SET status='running',stage='BRIDGE_RETRY' WHERE id=%s RETURNING session_id",
            (job_id,),
        ).fetchone()[0]
        append_event(connection, "ISSUE_RESOLVED", "commander-api", status="resolved",
                     session_id=session_id, job_id=job_id, payload={"issue_id": issue_id})
        append_event(connection, "TASK_RESUMED", "commander-api", status="running",
                     session_id=session_id, job_id=job_id, payload={"issue_id": issue_id})


def exhaust_bridge_issue(job_id: int, issue_id: int, error: Exception) -> None:
    with psycopg.connect(database_url(secrets)) as connection:
        connection.execute(
            """UPDATE engineering_issues SET status='unresolved',resolution_summary=%s,
                      resolved_at=now(),updated_at=now() WHERE id=%s""",
            ("Bridge retry was exhausted; manual inspection is required", issue_id),
        )
        connection.execute(
            """INSERT INTO engineering_issue_logs(issue_id,level,message,metadata)
               VALUES(%s,'error',%s,'{"attempt":2}'::jsonb)""",
            (issue_id, safe_bridge_error(error)),
        )
        session_id = connection.execute(
            """UPDATE jobs SET status='failed',error_code=%s,error_message=%s,finished_at=now()
               WHERE id=%s RETURNING session_id""",
            (type(error).__name__, f"ISSUE-{issue_id}: inspect sanitized issue log", job_id),
        ).fetchone()[0]
        append_event(connection, "ISSUE_UNRESOLVED", "commander-api", status="unresolved",
                     session_id=session_id, job_id=job_id, payload={"issue_id": issue_id})
        append_event(connection, "JOB_FAILED", "commander-api", status="failed",
                     session_id=session_id, job_id=job_id, payload={"issue_id": issue_id})
        connection.execute("UPDATE sessions SET status='failed',updated_at=now() WHERE id=%s", (session_id,))


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
                    "getUpdates",
                    params={
                        "timeout": 25,
                        "offset": offset,
                        "allowed_updates": '["message","callback_query"]',
                    },
                )
                response.raise_for_status()
                for update in response.json().get("result", []):
                    offset = int(update["update_id"]) + 1
                    message = update.get("message")
                    callback = update.get("callback_query") or {}
                    if not message and callback:
                        callback_message = callback.get("message") or {}
                        if not callback_message:
                            continue
                        message = dict(callback_message)
                        message["from"] = callback.get("from") or {}
                        message["text"] = callback.get("data") or ""
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
                    bridge_command = normalized_command(message.get("text") or "")
                    target = bridge_target(bridge_command, message.get("text") or "")
                    if target is not None:
                        if (message.get("from") or {}).get("id") not in allowed_user_ids():
                            await send_rejection(client, message, False)
                            continue
                        tracked_task_id = None
                        bridge_issue_id = None
                        if bridge_command in TRACKED_BRIDGE_COMMANDS:
                            tracked_task_id = await asyncio.to_thread(
                                persist_bridge_task, message, bridge_command
                            )
                            update = dict(update)
                            update["_ptw_task_id"] = tracked_task_id
                            await client.post("sendMessage", json={
                                "chat_id": message["chat"]["id"],
                                "reply_parameters": {"message_id": message["message_id"]},
                                "text": (
                                    f"Accepted TASK-{tracked_task_id}. {bridge_command.removeprefix('/').title()} "
                                    f"started. Use /inspect TASK-{tracked_task_id} or /cancel {tracked_task_id}."
                                ),
                            })
                        try:
                            # Agent-backed web research can take longer than image rendering.
                            attempts = 2 if tracked_task_id else 1
                            for attempt in range(1, attempts + 1):
                                try:
                                    async with httpx.AsyncClient(timeout=240) as bridge:
                                        response = await bridge.post(
                                            bridge_service_url(target),
                                            json=update,
                                            headers={"X-PTW-Bridge-Token": token},
                                        )
                                        response.raise_for_status()
                                    if bridge_issue_id is not None:
                                        await asyncio.to_thread(
                                            resolve_bridge_issue, tracked_task_id, bridge_issue_id
                                        )
                                        await client.post("sendMessage", json={
                                            "chat_id": message["chat"]["id"],
                                            "text": f"ISSUE-{bridge_issue_id} resolved. TASK-{tracked_task_id} resumed.",
                                        })
                                    if tracked_task_id is not None:
                                        await asyncio.to_thread(
                                            complete_bridge_task, tracked_task_id, response.json()
                                        )
                                    break
                                except httpx.HTTPStatusError as exc:
                                    if 400 <= exc.response.status_code < 500 or attempt == attempts:
                                        raise
                                    bridge_issue_id = await asyncio.to_thread(
                                        open_bridge_issue, tracked_task_id, "CREATIVE_BRIDGE", exc
                                    )
                                except httpx.HTTPError as exc:
                                    if attempt == attempts:
                                        raise
                                    bridge_issue_id = await asyncio.to_thread(
                                        open_bridge_issue, tracked_task_id, "CREATIVE_BRIDGE", exc
                                    )
                                await client.post("sendMessage", json={
                                    "chat_id": message["chat"]["id"],
                                    "text": (
                                        f"TASK-{tracked_task_id} blocked by ISSUE-{bridge_issue_id}. "
                                        "Automatic bridge retry started. "
                                        f"Inspect with /inspect ISSUE-{bridge_issue_id}."
                                    ),
                                })
                        except httpx.HTTPStatusError as exc:
                            logger.warning("Creative service rejected request: HTTP %s", exc.response.status_code)
                            detail = ""
                            try:
                                detail = str(exc.response.json().get("detail", ""))
                            except (ValueError, AttributeError):
                                pass
                            if tracked_task_id is not None:
                                if bridge_issue_id is not None:
                                    await asyncio.to_thread(
                                        exhaust_bridge_issue, tracked_task_id, bridge_issue_id, exc
                                    )
                                    issue_id = bridge_issue_id
                                else:
                                    issue_id = await asyncio.to_thread(
                                        fail_bridge_task, tracked_task_id, "CREATIVE_BRIDGE", exc
                                    )
                                text = f"TASK-{tracked_task_id} failed as ISSUE-{issue_id}. /inspect ISSUE-{issue_id}"
                            else:
                                text = detail if 400 <= exc.response.status_code < 500 and detail else "Creative service is temporarily unavailable."
                            await client.post("sendMessage", json={"chat_id": message["chat"]["id"], "text": text})
                        except httpx.HTTPError as exc:
                            logger.warning("Creative service forwarding failed: %s", type(exc).__name__)
                            if tracked_task_id is not None:
                                if bridge_issue_id is not None:
                                    await asyncio.to_thread(
                                        exhaust_bridge_issue, tracked_task_id, bridge_issue_id, exc
                                    )
                                    issue_id = bridge_issue_id
                                else:
                                    issue_id = await asyncio.to_thread(
                                        fail_bridge_task, tracked_task_id, "CREATIVE_BRIDGE", exc
                                    )
                                failure_text = f"TASK-{tracked_task_id} failed as ISSUE-{issue_id}. /inspect ISSUE-{issue_id}"
                            else:
                                failure_text = "Creative service is temporarily unavailable."
                            await client.post(
                                "sendMessage", json={"chat_id": message["chat"]["id"], "text": failure_text},
                            )
                        continue
                    accepted = await asyncio.to_thread(persist_update, message)
                    if not accepted or normalized_command(message.get("text") or "") not in SUPPORTED_COMMANDS:
                        await send_rejection(client, message, accepted)
                    elif isinstance(accepted, int) and accepted < 0:
                        await client.post("sendMessage", json={"chat_id": message["chat"]["id"],
                            "text": f"Cancellation requested for job #{-accepted}."})
                    elif normalized_command(message.get("text") or "") == "/cancel":
                        await client.post("sendMessage", json={"chat_id": message["chat"]["id"],
                            "text": "No matching queued or running engineering job was found."})
                    elif normalized_command(message.get("text") or "") in {"/task", "/engineer"}:
                        understood = engineering_task(message.get("text") or "")
                        await client.post("sendMessage", json={"chat_id": message["chat"]["id"],
                            "reply_parameters": {"message_id": message["message_id"]},
                            "text": f"Accepted job #{accepted}. I understood the task as:\n{understood}\n\nWork is queued and will start automatically. Cancel with /cancel {accepted}."})
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

@app.post("/internal/llm/structured")
def enqueue_structured_llm(request: dict, x_ptw_bridge_token: str = Header(default="")) -> dict:
    if not hmac.compare_digest(x_ptw_bridge_token, secrets.get("TELEGRAM_BOT_TOKEN")):
        raise HTTPException(status_code=403, detail="invalid bridge token")
    allowed_modes = {"generate", "evaluate", "evolve", "normalize_human", "telegram_chat"}
    if request.get("mode") not in allowed_modes or not isinstance(request.get("input_payload"), dict):
        raise HTTPException(status_code=400, detail="invalid structured LLM request")
    owner = min(allowed_user_ids())
    with psycopg.connect(database_url(secrets)) as connection:
        user_id = connection.execute("INSERT INTO users(telegram_user_id,role) VALUES(%s,'operator') ON CONFLICT(telegram_user_id) DO UPDATE SET role=users.role RETURNING id", (owner,)).fetchone()[0]
        session_id = connection.execute("INSERT INTO sessions(user_id,status,summary) VALUES(%s,'active','internal structured LLM request') RETURNING id", (user_id,)).fetchone()[0]
        job_id = connection.execute("INSERT INTO jobs(session_id,type,status,requested_by,parameters) VALUES(%s,'llm_structured','queued',%s,%s) RETURNING id", (session_id,user_id,Jsonb(request))).fetchone()[0]
    return {"request_id": job_id, "status": "queued"}

@app.get("/internal/llm/structured/{job_id}")
def structured_llm_result(job_id: int, x_ptw_bridge_token: str = Header(default="")) -> dict:
    if not hmac.compare_digest(x_ptw_bridge_token, secrets.get("TELEGRAM_BOT_TOKEN")):
        raise HTTPException(status_code=403, detail="invalid bridge token")
    with psycopg.connect(database_url(secrets)) as connection:
        row = connection.execute("SELECT status,result,error_code FROM jobs WHERE id=%s AND type='llm_structured'", (job_id,)).fetchone()
    if not row: raise HTTPException(status_code=404, detail="unknown request")
    return {"status":row[0], "result":row[1], "error":row[2]}


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
