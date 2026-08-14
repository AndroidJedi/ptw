"""Machine-readable, secret-scrubbed Commander state export."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from typing import Any

import psycopg

from common.database import database_url
from common.events import _safe_payload
from common.secrets import EnvironmentSecretStore
from engineering.issues import issue_details, parse_reference, task_details


TABLES = (
    "users", "sessions", "jobs", "events", "engineering_runs",
    "engineering_artifacts", "engineering_issues", "engineering_issue_logs",
    "project_memory", "repositories", "service_heartbeats",
)


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def export_state(connection: Any, reference: str | None = None) -> dict[str, object]:
    if reference:
        kind, identifier = parse_reference(reference)
        value = task_details(connection, identifier) if kind == "task" else issue_details(connection, identifier)
        return {"schema_version": 1, "scope": reference.upper(), "state": _safe_payload(value)}
    state: dict[str, object] = {"schema_version": 1, "scope": "commander"}
    for table in TABLES:
        cursor = connection.execute(f"SELECT * FROM {table} ORDER BY 1")
        columns = [item.name for item in cursor.description]
        state[table] = [
            _safe_payload(dict(zip(columns, row, strict=True))) for row in cursor.fetchall()
        ]
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Export reviewable Commander state as JSON")
    parser.add_argument("reference", nargs="?", help="optional TASK-<id> or ISSUE-<id>")
    parser.add_argument("--output", help="write to a file instead of stdout")
    arguments = parser.parse_args()
    with psycopg.connect(database_url(EnvironmentSecretStore())) as connection:
        encoded = json.dumps(
            export_state(connection, arguments.reference),
            indent=2,
            sort_keys=True,
            default=_json_default,
        ) + "\n"
    if arguments.output:
        from pathlib import Path
        target = Path(arguments.output)
        target.write_text(encoded, encoding="utf-8")
        target.chmod(0o600)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
