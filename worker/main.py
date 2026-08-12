import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import httpx
import psycopg
from psycopg.types.json import Jsonb

from common.database import database_url
from common.events import append_event
from common.secrets import EnvironmentSecretStore
from common.telegram import send_telegram as send_telegram_message
from engineering.service import execute_engineering_job
from engineering.runner import StageFailure

logging.basicConfig(
    level=os.getenv("PTW_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ptw.worker")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
running = True
secrets = EnvironmentSecretStore()


def stop(_signum: int, _frame: object) -> None:
    global running
    running = False


def heartbeat(connection: psycopg.Connection) -> None:
    connection.execute(
        """
        INSERT INTO service_heartbeats (service, seen_at) VALUES ('commander-worker', now())
        ON CONFLICT (service) DO UPDATE SET seen_at = excluded.seen_at
        """
    )


def command_available(command: str) -> bool:
    executable = shutil.which(command)
    if not executable:
        return False
    try:
        subprocess.run(
            [executable, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=3, check=False,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def codex_available() -> bool:
    """Detect Codex directly or via host-generated, read-only metadata."""
    if command_available("codex"):
        return True
    metadata = Path(os.getenv("CODEX_METADATA_FILE", "/run/ptw-host/codex-version"))
    try:
        return metadata.is_file() and metadata.read_text(encoding="utf-8").startswith("codex-cli ")
    except OSError:
        return False


def status_response(connection: psycopg.Connection) -> str:
    checks: dict[str, bool] = {}
    try:
        response = httpx.get("http://commander-api:8000/health/ready", timeout=3)
        checks["Commander"] = response.status_code == 200
    except httpx.HTTPError:
        checks["Commander"] = False
    checks["Worker"] = True
    try:
        connection.execute("SELECT 1")
        checks["PostgreSQL"] = True
    except psycopg.Error:
        checks["PostgreSQL"] = False
    checks["Git"] = command_available("git")
    checks["Codex"] = codex_available()
    usage = shutil.disk_usage(Path("/"))
    checks["Disk"] = usage.free >= 512 * 1024 * 1024
    queued = connection.execute("SELECT count(*) FROM jobs WHERE status = 'queued'").fetchone()[0]
    failed = connection.execute("SELECT count(*) FROM jobs WHERE status = 'failed'").fetchone()[0]
    lines = ["PTW Commander v0.1"]
    lines.extend(f"{name:<14}{'✅' if ok else '❌'}" for name, ok in checks.items())
    lines.extend((f"Queued jobs: {queued}", f"Failed jobs: {failed}"))
    return "\n".join(lines)


def execute_job(connection: psycopg.Connection, job_type: str, job_id: int | None = None, parameters: dict | None = None) -> str:
    if job_type == "ping":
        return "pong"
    if job_type == "version":
        return "PTW Commander v0.1"
    if job_type == "help":
        return "PTW Commander v0.2\n/engineer repo=ptw <task> - create validated PR\n/ping - test job execution\n/status - dependency status\n/version - show version\n/help - show commands"
    if job_type == "status":
        return status_response(connection)
    if job_type == "engineer" and job_id is not None and parameters is not None:
        return execute_engineering_job(connection, job_id, parameters)
    raise ValueError(f"Unsupported job type: {job_type}")


def send_telegram(parameters: dict, text: str) -> None:
    send_telegram_message(parameters["chat_id"], text,
                          reply_to_message_id=parameters.get("reply_to_message_id"))


def process_one(connection: psycopg.Connection) -> bool:
    job = connection.execute(
        """
        SELECT id, session_id, type, parameters FROM jobs
        WHERE status = 'queued' ORDER BY created_at, id
        FOR UPDATE SKIP LOCKED LIMIT 1
        """
    ).fetchone()
    if not job:
        heartbeat(connection)
        connection.commit()
        return False
    job_id, session_id, job_type, parameters = job
    connection.execute(
        "UPDATE jobs SET status = 'running', started_at = now() WHERE id = %s", (job_id,)
    )
    append_event(
        connection, "JOB_STARTED", "commander-worker", status="running",
        session_id=session_id, job_id=job_id, payload={"job_type": job_type},
    )
    connection.commit()
    try:
        text = execute_job(connection, job_type, job_id, parameters)
        send_telegram(parameters, text)
        connection.execute(
            "UPDATE jobs SET status = 'completed', result = %s, finished_at = now() WHERE id = %s",
            (Jsonb({"response": text}), job_id),
        )
        append_event(
            connection, "JOB_COMPLETED", "commander-worker", status="completed",
            session_id=session_id, job_id=job_id, payload={"job_type": job_type},
        )
        append_event(
            connection, "RESPONSE_SENT", "commander-worker", status="sent",
            session_id=session_id, job_id=job_id, payload={"channel": "telegram"},
        )
        connection.execute(
            "UPDATE sessions SET status = 'completed', updated_at = now() WHERE id = %s",
            (session_id,),
        )
    except Exception as exc:
        logger.warning("Job %s failed: %s", job_id, type(exc).__name__)
        connection.execute(
            """
            UPDATE jobs SET status = 'failed', error_code = %s, error_message = %s,
                            finished_at = now() WHERE id = %s
            """,
            (type(exc).__name__, "Job execution failed; inspect service logs", job_id),
        )
        append_event(
            connection, "JOB_FAILED", "commander-worker", status="failed",
            session_id=session_id, job_id=job_id,
            payload={"error_type": type(exc).__name__},
        )
        if isinstance(exc, StageFailure):
            connection.execute(
                "UPDATE engineering_runs SET status='failed',failure_stage=%s,updated_at=now() WHERE job_id=%s",
                (exc.stage, job_id),
            )
        connection.execute(
            "UPDATE sessions SET status = 'failed', updated_at = now() WHERE id = %s",
            (session_id,),
        )
    heartbeat(connection)
    connection.commit()
    return True


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    poll_seconds = max(1, int(os.getenv("WORKER_POLL_SECONDS", "2")))
    logger.info("Commander worker started")
    while running:
        try:
            with psycopg.connect(database_url(secrets), connect_timeout=3) as connection:
                worked = process_one(connection)
        except Exception as exc:
            worked = False
            logger.warning("Worker cycle failed: %s", type(exc).__name__)
        if not worked:
            time.sleep(poll_seconds)
    logger.info("Commander worker stopped")


if __name__ == "__main__":
    main()
