"""Destructive-to-test-data integration checks for the live Compose database."""

import os
import time
from unittest.mock import patch

import psycopg

from commander.main import persist_update
from common.database import apply_migrations, database_url
from common.events import append_event
from worker.main import process_one, status_response


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    allowed = min(int(value) for value in os.environ["TELEGRAM_ALLOWED_USER_IDS"].split(","))
    marker = int(time.time())
    apply_migrations()
    with psycopg.connect(database_url()) as connection:
        check(connection.execute("SELECT 1").fetchone()[0] == 1, "database connection")
        tables = {
            row[0] for row in connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
        }
        check({"users", "sessions", "jobs", "events"} <= tables, "migrations")
        append_event(connection, "HEALTH_CHECK", "integration-test", payload={"marker": marker})

    unauthorized = {"message_id": marker, "from": {"id": -marker}, "chat": {"id": -marker}, "text": "/ping"}
    check(persist_update(unauthorized) is False, "unauthorized command rejection")
    authorized = {"message_id": marker, "from": {"id": allowed}, "chat": {"id": allowed}, "text": "/ping"}
    check(isinstance(persist_update(authorized), int), "authorized command handling")

    with patch("worker.main.send_telegram") as sender:
        with psycopg.connect(database_url()) as connection:
            check(process_one(connection) is True, "job claimed")
            sender.assert_called_once_with(
                {"chat_id": allowed, "reply_to_message_id": marker, "repo": "ptw", "task": ""}, "pong"
            )
            job = connection.execute(
                "SELECT id, session_id, status FROM jobs WHERE parameters->>'reply_to_message_id' = %s",
                (str(marker),),
            ).fetchone()
            check(job is not None and job[2] == "completed", "ping job lifecycle")
            sequence = [
                row[0] for row in connection.execute(
                    "SELECT event_type FROM events WHERE session_id = %s ORDER BY id", (job[1],)
                )
            ]
            check(sequence == ["COMMAND_ACCEPTED", "JOB_CREATED", "JOB_STARTED", "JOB_COMPLETED", "RESPONSE_SENT"], "event sequence")
            check("PTW Commander v0.1" in status_response(connection), "status response")

            connection.execute("DELETE FROM events WHERE session_id = %s OR (actor = 'integration-test' AND payload->>'marker' = %s) OR actor = %s", (job[1], str(marker), f"telegram:{-marker}"))
            connection.execute("DELETE FROM jobs WHERE session_id = %s", (job[1],))
            connection.execute("DELETE FROM sessions WHERE id = %s", (job[1],))
            connection.execute("DELETE FROM users u WHERE telegram_user_id = %s AND NOT EXISTS (SELECT 1 FROM sessions s WHERE s.user_id = u.id)", (allowed,))
    print("Integration checks passed")


if __name__ == "__main__":
    main()
