from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Iterator
from uuid import uuid4


class ControlStore:
    """Small reset-independent store for control metadata, never domain state."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _migrate(self) -> None:
        with self.connection() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS command_sessions (
                    id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL CHECK(mode IN ('plan','execute')),
                    instruction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    plan TEXT,
                    plan_digest TEXT,
                    destructive INTEGER NOT NULL DEFAULT 0,
                    execution_count INTEGER NOT NULL DEFAULT 0,
                    platform_job_id INTEGER,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS command_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES command_sessions(id),
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS command_events_session_idx ON command_events(session_id, sequence);
                CREATE TABLE IF NOT EXISTS ws_tickets (
                    digest TEXT PRIMARY KEY,
                    uid TEXT NOT NULL,
                    path TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS root_sessions (
                    id TEXT PRIMARY KEY,
                    uid TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    end_reason TEXT
                );
            """)

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def destructive_text(value: str) -> bool:
        lowered = value.lower()
        return ("recreate" in lowered and "schema" in lowered) or any(token in lowered for token in (
            "drop ", "truncate ", "delete all", "reset database", "reset production",
            "rm -", "restore ", "destroy", "recreate schema", "wipe ",
        ))

    def create_command(self, mode: str, instruction: str) -> dict[str, Any]:
        session_id = str(uuid4())
        now = self.now()
        destructive = self.destructive_text(instruction)
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO command_sessions(id,mode,instruction,status,destructive,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (session_id, mode, instruction, "planning", int(destructive), now, now),
            )
        self.event(session_id, {"type": "session.created", "mode": mode, "destructive": destructive})
        return self.command(session_id)

    def command(self, session_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM command_sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(session_id)
        result = dict(row)
        result["id"] = result.pop("id")
        result["title"] = result["instruction"][:120]
        result["destructive"] = bool(result["destructive"])
        return result

    def commands(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT id FROM command_sessions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self.command(str(row[0])) for row in rows]

    def set_plan(self, session_id: str, plan: str) -> str:
        digest = hashlib.sha256(plan.encode()).hexdigest()
        with self.connection() as connection:
            cursor = connection.execute(
                """UPDATE command_sessions
                   SET plan=?,plan_digest=?,status='awaiting_approval',
                       destructive=CASE WHEN destructive=1 OR ? THEN 1 ELSE 0 END,
                       updated_at=?
                   WHERE id=? AND status='planning'""",
                (plan, digest, int(self.destructive_text(plan)), self.now(), session_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("plan is immutable after its first completion")
        command = self.command(session_id)
        self.event(session_id, {
            "type": "plan.completed", "plan": plan, "plan_digest": digest,
            "destructive": command["destructive"],
        })
        return digest

    def approve_once(self, session_id: str, digest: str, *, destructive_allowed: bool) -> dict[str, Any]:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM command_sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise KeyError(session_id)
            if row["status"] != "awaiting_approval" or row["execution_count"] != 0:
                raise ValueError("this plan cannot be executed again")
            if not secrets.compare_digest(str(row["plan_digest"]), digest):
                raise ValueError("approved plan digest does not match")
            if bool(row["destructive"]) and not destructive_allowed:
                raise PermissionError("destructive plan requires explicit confirmation")
            connection.execute(
                "UPDATE command_sessions SET status='queued',execution_count=1,updated_at=? WHERE id=?",
                (self.now(), session_id),
            )
        self.event(session_id, {"type": "plan.approved", "plan_digest": digest})
        return self.command(session_id)

    def update(self, session_id: str, status: str, **values: Any) -> None:
        allowed = {"platform_job_id", "error"}
        if not set(values).issubset(allowed):
            raise ValueError("invalid command update")
        assignments = ["status=?", "updated_at=?"] + [f"{key}=?" for key in values]
        params = [status, self.now(), *values.values(), session_id]
        with self.connection() as connection:
            connection.execute(f"UPDATE command_sessions SET {','.join(assignments)} WHERE id=?", params)

    def event(self, session_id: str, event: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO command_events(session_id,event_json,created_at) VALUES(?,?,?)",
                (session_id, json.dumps(event, ensure_ascii=False), self.now()),
            )

    def events(self, session_id: str, after: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT sequence,event_json,created_at FROM command_events WHERE session_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                (session_id, after, min(limit, 200)),
            ).fetchall()
        return [{"sequence": row[0], "created_at": row[2], **json.loads(row[1])} for row in rows]

    def issue_ticket(self, uid: str, path: str) -> str:
        ticket = secrets.token_urlsafe(32)
        digest = hashlib.sha256(ticket.encode()).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
        with self.connection() as connection:
            connection.execute("INSERT INTO ws_tickets(digest,uid,path,expires_at) VALUES(?,?,?,?)", (digest, uid, path, expires))
        return ticket

    def consume_ticket(self, ticket: str, path: str) -> str:
        digest = hashlib.sha256(ticket.encode()).hexdigest()
        now = self.now()
        with self.connection() as connection:
            row = connection.execute("SELECT uid,path,expires_at,consumed_at FROM ws_tickets WHERE digest=?", (digest,)).fetchone()
            if row is None or row[3] is not None or row[1] != path or row[2] <= now:
                raise PermissionError("invalid or expired WebSocket ticket")
            connection.execute("UPDATE ws_tickets SET consumed_at=? WHERE digest=?", (now, digest))
        return str(row[0])

    def start_root_session(self, uid: str) -> str:
        session_id = str(uuid4())
        with self.connection() as connection:
            active = connection.execute(
                "SELECT id,started_at FROM root_sessions WHERE ended_at IS NULL LIMIT 1"
            ).fetchone()
            if active:
                started = datetime.fromisoformat(str(active[1]))
                if datetime.now(timezone.utc) - started < timedelta(minutes=60):
                    raise ValueError("a root session is already active")
                connection.execute(
                    "UPDATE root_sessions SET ended_at=?,end_reason='maximum_duration_recovered' WHERE id=?",
                    (self.now(), active[0]),
                )
            connection.execute("INSERT INTO root_sessions(id,uid,started_at) VALUES(?,?,?)", (session_id, uid, self.now()))
        return session_id

    def end_root_session(self, session_id: str, reason: str) -> None:
        with self.connection() as connection:
            connection.execute("UPDATE root_sessions SET ended_at=?,end_reason=? WHERE id=? AND ended_at IS NULL", (self.now(), reason[:120], session_id))
