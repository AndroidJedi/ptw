"""Restart-safe intake for PTW tasks originating in a Codex workspace."""

from __future__ import annotations

import argparse
import os
import time

import psycopg
from psycopg.types.json import Jsonb

from common.database import database_url
from common.events import append_event
from common.secrets import EnvironmentSecretStore


def _single_allowed_identity() -> tuple[int, int]:
    raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    users = {int(value.strip()) for value in raw.split(",") if value.strip()}
    user_value = os.getenv("WORKSPACE_TELEGRAM_USER_ID", "").strip()
    chat_value = os.getenv("WORKSPACE_TELEGRAM_CHAT_ID", "").strip()
    if user_value and chat_value:
        user_id, chat_id = int(user_value), int(chat_value)
        if user_id not in users:
            raise RuntimeError("WORKSPACE_TELEGRAM_USER_ID is not allowed")
        return user_id, chat_id
    if len(users) != 1:
        raise RuntimeError(
            "Set WORKSPACE_TELEGRAM_USER_ID and WORKSPACE_TELEGRAM_CHAT_ID when the allowlist is not singular"
        )
    user_id = next(iter(users))
    return user_id, user_id


def register(scope: str, session_id: str, *, job_type: str = "engineer") -> int:
    if not scope.strip() or len(scope) > 4000:
        raise ValueError("scope must contain 1-4000 characters")
    user_id, chat_id = _single_allowed_identity()
    secrets = EnvironmentSecretStore()
    with psycopg.connect(database_url(secrets)) as connection:
        owner_id = connection.execute(
            """INSERT INTO users(telegram_user_id,role) VALUES(%s,'operator')
               ON CONFLICT(telegram_user_id) DO UPDATE SET role=users.role RETURNING id""",
            (user_id,),
        ).fetchone()[0]
        durable_session = connection.execute(
            "INSERT INTO sessions(user_id,status,summary) VALUES(%s,'active',%s) RETURNING id",
            (owner_id, f"Codex workspace {session_id}"),
        ).fetchone()[0]
        parameters = {
            "chat_id": chat_id,
            "repo": "ptw",
            "task": scope.strip(),
            "workspace_session_id": session_id[:200],
            "source": "codex_workspace",
        }
        job_id = connection.execute(
            """INSERT INTO jobs(session_id,type,status,requested_by,parameters)
               VALUES(%s,%s,'awaiting_ack',%s,%s) RETURNING id""",
            (durable_session, job_type, owner_id, Jsonb(parameters)),
        ).fetchone()[0]
        append_event(
            connection, "JOB_CREATED", f"codex-workspace:{session_id[:100]}",
            status="awaiting_ack", session_id=durable_session, job_id=job_id,
            payload={"job_type": "task", "source": "codex_workspace"},
        )
    return job_id


def wait_for_ack(job_id: int, timeout: int) -> None:
    secrets = EnvironmentSecretStore()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with psycopg.connect(database_url(secrets)) as connection:
            row = connection.execute(
                """SELECT status, EXISTS(
                       SELECT 1 FROM events WHERE job_id=%s AND event_type='ACKNOWLEDGEMENT_SENT'
                   ) FROM jobs WHERE id=%s""",
                (job_id, job_id),
            ).fetchone()
        if row and row[1] and row[0] in {"queued", "running", "completed"}:
            return
        time.sleep(1)
    raise RuntimeError(f"TASK-{job_id} Telegram acknowledgement was not delivered")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--canary", action="store_true",
        help="verify acknowledgement delivery using a harmless ping job",
    )
    args = parser.parse_args()
    job_id = register(args.scope, args.session_id, job_type="ping" if args.canary else "engineer")
    print(f"TASK-{job_id} registered; waiting for Telegram acknowledgement", flush=True)
    wait_for_ack(job_id, args.timeout)
    print(f"TASK-{job_id} acknowledged in Telegram; execution released")


if __name__ == "__main__":
    main()
