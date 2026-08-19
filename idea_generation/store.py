from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
import threading
from typing import Any, Iterator


class PostgresStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._connection: Any | None = None
        self._connection_guard = threading.Lock()

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        import psycopg
        with self._connection_guard:
            connection = self._connection
            if connection is None or connection.closed:
                connection = psycopg.connect(
                    self.database_url,
                    connect_timeout=5,
                    application_name="ptw-idea-api",
                )
                self._connection = connection
            try:
                with connection.transaction():
                    yield connection
            except Exception:
                if connection.closed:
                    self._connection = None
                raise

    def close(self) -> None:
        with self._connection_guard:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def migrate(self, directory: Path) -> None:
        with self.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('idea_generation_migrations'))")
            connection.execute("CREATE TABLE IF NOT EXISTS idea_schema_migrations(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
            for path in sorted(directory.glob("*.sql")):
                if connection.execute("SELECT 1 FROM idea_schema_migrations WHERE version=%s", (path.name,)).fetchone():
                    continue
                connection.execute(path.read_text())
                connection.execute("INSERT INTO idea_schema_migrations(version) VALUES (%s)", (path.name,))

    def seed_laval_mission(self) -> None:
        """Seed only the durable mission required by Laval; never seed ideas or legacy contexts."""
        with self.transaction() as connection:
            connection.execute("UPDATE missions SET is_active=FALSE WHERE is_active AND code<>'MISSION_20M_3Y'")
            connection.execute(
                """INSERT INTO missions(
                        code,name,name_i18n,task_text,is_active,activated_at,deadline_at
                    ) VALUES ('MISSION_20M_3Y',%s,%s::jsonb,%s,TRUE,NOW(),NOW() + INTERVAL '36 months')
                    ON CONFLICT (code) DO UPDATE SET
                        name=EXCLUDED.name,
                        name_i18n=EXCLUDED.name_i18n,
                        task_text=EXCLUDED.task_text,
                        is_active=TRUE,
                        activated_at=COALESCE(missions.activated_at, EXCLUDED.activated_at),
                        deadline_at=COALESCE(missions.deadline_at, EXCLUDED.deadline_at),
                        updated_at=NOW()""",
                (
                    "Build a remotely operated company worth $20M within 36 months",
                    self.json({
                        "en": "Build a remotely operated company worth $20M within 36 months",
                        "uk": "Побудувати дистанційно керовану компанію вартістю $20 млн за 36 місяців",
                    }),
                    "Evaluate and transform only owner-submitted ideas through the Idea Laval pipeline.",
                ),
            )

    def mission(self, *, lock: bool = False) -> dict[str, Any]:
        suffix = " FOR UPDATE" if lock else ""
        with self.transaction() as connection:
            cursor = connection.execute(
                "SELECT * FROM missions WHERE is_active=TRUE ORDER BY activated_at DESC NULLS LAST LIMIT 1" + suffix
            )
            row = cursor.fetchone()
            if not row: raise RuntimeError("mission is not seeded")
            return dict(zip([d.name for d in cursor.description], row))

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

    def update_mission(self, **values: Any) -> None:
        allowed = {"status", "auto_enabled", "cadence_hours", "run_series_remaining", "stop_after_current_cycle"}
        if not values or not set(values).issubset(allowed): raise ValueError("invalid mission update")
        assignments = ",".join(f"{key}=%s" for key in values)
        self.execute(
            f"UPDATE missions SET {assignments},updated_at=NOW() WHERE is_active=TRUE RETURNING id",
            tuple(values.values()),
        )

    @staticmethod
    def json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)
