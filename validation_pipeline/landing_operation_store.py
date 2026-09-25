"""Durable Landing request identities and append-only progress, SQLite/PG parity."""
from contextlib import contextmanager, closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from uuid import UUID

ACTIVE = {"queued", "running"}


class OperationStore:
    def __init__(self, path: Path, database_url: str | None = None):
        self.path, self.database_url = path, database_url
        if not database_url:
            path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(path)) as db:
                db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS landing_operations(operation_id TEXT PRIMARY KEY,
                  landing_id TEXT NOT NULL,project_id TEXT NOT NULL,request_id TEXT NOT NULL,
                  status TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(landing_id,request_id));
                CREATE UNIQUE INDEX IF NOT EXISTS landing_one_active_operation ON landing_operations(landing_id) WHERE status IN ('queued','running');
                CREATE TABLE IF NOT EXISTS landing_operation_events(operation_id TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(operation_id,revision));
                CREATE TRIGGER IF NOT EXISTS landing_operation_events_no_update BEFORE UPDATE ON landing_operation_events BEGIN SELECT RAISE(ABORT,'immutable operation event'); END;
                CREATE TRIGGER IF NOT EXISTS landing_operation_events_no_delete BEFORE DELETE ON landing_operation_events BEGIN SELECT RAISE(ABORT,'immutable operation event'); END;
                """)

    @contextmanager
    def transaction(self):
        if self.database_url:
            import psycopg
            with psycopg.connect(self.database_url) as db:
                db.execute("SELECT pg_advisory_xact_lock(719260018)")
                yield lambda sql, args=(): db.execute(sql.replace("?", "%s"), args)
        else:
            with closing(sqlite3.connect(self.path, timeout=30)) as db:
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    yield db.execute

    def get(self, operation_id):
        operation_id = str(UUID(operation_id))
        with self.transaction() as query:
            row = query("SELECT payload FROM landing_operations WHERE operation_id=?", (operation_id,)).fetchone()
        if row is None:
            raise KeyError("Landing operation was not found")
        return json.loads(row[0])

    def list(self, landing_id=None, active=False, limit=200):
        with self.transaction() as query:
            where, args = ("landing_id=?", (landing_id,)) if landing_id else ("1=1", ())
            if active:
                where += " AND status IN ('queued','running')"
            return [json.loads(row[0]) for row in query(f"SELECT payload FROM landing_operations WHERE {where} ORDER BY created_at DESC LIMIT ?", args + (max(1,min(200,int(limit))),)).fetchall()]

    def save(self, value, expected=None):
        value = deepcopy(value)
        with self.transaction() as query:
            row = query("SELECT payload FROM landing_operations WHERE operation_id=?", (value["operation_id"],)).fetchone()
            previous = json.loads(row[0]) if row else None
            if (previous or {}).get("revision") != expected:
                raise RuntimeError("Landing operation changed; refresh its status")
            if value["status"] in ACTIVE:
                active = query("SELECT operation_id FROM landing_operations WHERE landing_id=? AND status IN ('queued','running') AND operation_id<>?", (value["landing_id"], value["operation_id"])).fetchone()
                if active:
                    raise RuntimeError("Another Landing operation is still running")
            value["revision"] = (expected or 0) + 1
            payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(payload.encode()) > 256_000:
                raise ValueError("Landing operation exceeded its bounded state budget")
            if previous:
                query("UPDATE landing_operations SET status=?,revision=?,payload=? WHERE operation_id=?", (value["status"], value["revision"], payload, value["operation_id"]))
            else:
                if self.database_url:
                    from psycopg.types.json import Jsonb
                    query("INSERT INTO commander_entities(id,kind,attributes) VALUES(?,'landing_operation',?)", (UUID(value["operation_id"]), Jsonb({"schema_version": 1, "kind": value["kind"]})))
                    from uuid import uuid4
                    query("INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(?,?,'contains',?,?)", (uuid4(), UUID(value["landing_id"]), UUID(value["operation_id"]), Jsonb({"member": "landing_operation"})))
                query("INSERT INTO landing_operations(operation_id,landing_id,project_id,request_id,status,revision,payload,created_at) VALUES(?,?,?,?,?,?,?,?)", tuple(value[k] for k in ("operation_id", "landing_id", "project_id", "request_id", "status", "revision")) + (payload,value["started_at"]))
            query("INSERT INTO landing_operation_events(operation_id,revision,payload) VALUES(?,?,?)", (value["operation_id"], value["revision"], payload))
        return value
