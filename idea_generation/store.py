from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class PostgresStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                yield connection

    def migrate(self, directory: Path) -> None:
        with self.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('idea_generation_migrations'))")
            connection.execute("CREATE TABLE IF NOT EXISTS idea_schema_migrations(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            for path in sorted(directory.glob("*.sql")):
                if connection.execute("SELECT 1 FROM idea_schema_migrations WHERE version=%s", (path.name,)).fetchone():
                    continue
                connection.execute(path.read_text())
                connection.execute("INSERT INTO idea_schema_migrations(version) VALUES (%s)", (path.name,))

    def seed(self, mission_text: str, contexts: list[dict[str, str]]) -> None:
        if len(contexts) != 10 or [item["code"] for item in contexts] != [f"C{i:02d}" for i in range(1, 11)]:
            raise ValueError("seed requires exactly C01-C10")
        with self.transaction() as connection:
            connection.execute("""INSERT INTO missions(code,name,task_text) VALUES ('MISSION_450M_5Y',%s,%s)
                ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, task_text=EXCLUDED.task_text""",
                ("Build a company that could be sold for $450M within 5 years", mission_text))
            for order, item in enumerate(contexts, 1):
                row = connection.execute("""INSERT INTO contexts(code,name,prompt_text,sort_order) VALUES (%s,%s,%s,%s)
                    ON CONFLICT (code) DO NOTHING RETURNING id,version""",
                    (item["code"], item["name"], item["prompt"], order)).fetchone()
                if row is None:
                    row = connection.execute(
                        "SELECT id,version FROM contexts WHERE code=%s", (item["code"],)
                    ).fetchone()
                connection.execute("""INSERT INTO context_revisions(context_id,version,name,prompt_text,changed_by,change_note)
                    VALUES (%s,%s,%s,%s,'seed','authoritative v1 seed') ON CONFLICT DO NOTHING""",
                    (row[0], row[1], item["name"], item["prompt"]))

    def mission(self, *, lock: bool = False) -> dict[str, Any]:
        suffix = " FOR UPDATE" if lock else ""
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM missions WHERE code='MISSION_450M_5Y'" + suffix).fetchone()
            if not row: raise RuntimeError("mission is not seeded")
            return dict(zip([d.name for d in connection.execute("SELECT * FROM missions LIMIT 0").description], row))

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            cursor = connection.execute(sql, params)
            return [dict(zip([item.name for item in cursor.description], row)) for row in cursor.fetchall()]

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int | None:
        with self.transaction() as connection:
            row = connection.execute(sql, params).fetchone()
            return int(row[0]) if row else None

    def active_contexts(self) -> list[dict[str, Any]]:
        return self.fetchall("SELECT * FROM contexts WHERE active ORDER BY sort_order")

    def update_mission(self, **values: Any) -> None:
        allowed = {"status", "auto_enabled", "cadence_hours", "run_series_remaining", "stop_after_current_cycle"}
        if not values or not set(values).issubset(allowed): raise ValueError("invalid mission update")
        assignments = ",".join(f"{key}=%s" for key in values)
        self.execute(f"UPDATE missions SET {assignments},updated_at=NOW() WHERE code='MISSION_450M_5Y' RETURNING id", tuple(values.values()))

    @staticmethod
    def json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)
