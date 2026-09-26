"""Append-only Templates authority with identical SQLite and PostgreSQL semantics."""
from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from .template_components import canonical, sha

KINDS = {"run", "version", "request", "builtin"}
MAX_RECORD_BYTES = 256_000


class TemplateConflict(RuntimeError):
    pass


class TemplateTransaction:
    def __init__(self, connection, postgres=False, namespace="template_authoring"):
        self.connection, self.postgres, self.namespace = connection, postgres, namespace

    def execute(self, sql, values=()):
        sql = sql.replace("template_authoring_", self.namespace + "_")
        return self.connection.execute(sql.replace("?", "%s") if self.postgres else sql, values)

    def get(self, kind: str, key: str) -> dict | None:
        row = self.execute("SELECT payload FROM template_authoring_records WHERE kind=? AND record_key=? ORDER BY revision DESC LIMIT 1", (kind, key)).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if value.get("state_sha256") != sha({k: v for k, v in value.items() if k != "state_sha256"}):
            raise RuntimeError("Template record failed its integrity check")
        return value

    def list(self, kind: str, limit: int = 100) -> list[dict]:
        rows = self.execute("""SELECT r.payload FROM template_authoring_records r
            JOIN (SELECT record_key,max(revision) revision FROM template_authoring_records WHERE kind=? GROUP BY record_key) h
            ON r.record_key=h.record_key AND r.revision=h.revision WHERE r.kind=?
            ORDER BY r.created_at DESC,r.record_key LIMIT ?""", (kind, kind, min(200, max(1, limit)))).fetchall()
        return [json.loads(row[0]) for row in rows]

    def history(self, kind: str, key: str, limit: int = 200) -> list[dict]:
        rows = self.execute(
            "SELECT payload FROM template_authoring_records WHERE kind=? AND record_key=? ORDER BY revision DESC LIMIT ?",
            (kind, key, min(200, max(1, limit))),
        ).fetchall()
        values = [json.loads(row[0]) for row in rows]
        for value in values:
            if value.get("state_sha256") != sha({k: v for k, v in value.items() if k != "state_sha256"}):
                raise RuntimeError("Template record failed its integrity check")
        return values

    def append(self, kind: str, key: str, value: dict, *, expected: str | None = None) -> dict:
        if kind not in KINDS or not isinstance(key, str) or not 1 <= len(key) <= 160:
            raise ValueError("Template record identity is invalid")
        previous = self.get(kind, key)
        if (previous or {}).get("state_sha256") != expected:
            raise TemplateConflict("Template state changed; refresh before retrying")
        if previous is not None and kind != "run":
            raise TemplateConflict("Template records are immutable")
        revision = 1 if previous is None else previous["revision"] + 1
        result = {**value, "revision": revision}
        result.pop("state_sha256", None)
        result["state_sha256"] = sha(result)
        payload = canonical(result)
        if len(payload.encode()) > MAX_RECORD_BYTES:
            raise ValueError("Template record exceeds its bounded byte budget")
        self.execute("INSERT INTO template_authoring_records(kind,record_key,revision,state_sha256,payload) VALUES(?,?,?,?,?)",
                     (kind, key, revision, result["state_sha256"], payload))
        return result

    def media(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 12 * 1024 * 1024:
            raise ValueError("Template preview media is invalid")
        self.execute("INSERT INTO template_authoring_media(sha256,png) VALUES(?,?) ON CONFLICT(sha256) DO NOTHING", (digest, data))
        return digest

    def read_media(self, digest: str) -> bytes:
        row = self.execute("SELECT png FROM template_authoring_media WHERE sha256=?", (digest,)).fetchone()
        if row is None:
            raise KeyError("Template preview is unavailable")
        data = bytes(row[0])
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError("Template preview failed its digest check")
        return data


class TemplateStore:
    def __init__(self, path: Path | None = None, *, database_url: str | None = None, namespace="template_authoring"):
        if namespace not in {"template_authoring", "creation_studio"}:
            raise ValueError("Unknown authoring namespace")
        self.namespace = namespace
        self.path, self.database_url = path, database_url
        if database_url is None:
            if path is None:
                raise ValueError("Template authority is required")
            path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(path)) as db:
                db.executescript("""
                    PRAGMA journal_mode=WAL;
                    CREATE TABLE IF NOT EXISTS template_authoring_records (
                        kind TEXT NOT NULL,record_key TEXT NOT NULL,revision INTEGER NOT NULL,
                        state_sha256 TEXT NOT NULL,payload TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                        PRIMARY KEY(kind,record_key,revision), CHECK(kind='run' OR revision=1));
                    CREATE TABLE IF NOT EXISTS template_authoring_media(sha256 TEXT PRIMARY KEY,png BLOB NOT NULL);
                    CREATE TRIGGER IF NOT EXISTS template_records_no_update BEFORE UPDATE ON template_authoring_records BEGIN SELECT RAISE(ABORT,'immutable template record'); END;
                    CREATE TRIGGER IF NOT EXISTS template_records_no_delete BEFORE DELETE ON template_authoring_records BEGIN SELECT RAISE(ABORT,'immutable template record'); END;
                    CREATE TRIGGER IF NOT EXISTS template_media_no_update BEFORE UPDATE ON template_authoring_media BEGIN SELECT RAISE(ABORT,'immutable template media'); END;
                    CREATE TRIGGER IF NOT EXISTS template_media_no_delete BEFORE DELETE ON template_authoring_media BEGIN SELECT RAISE(ABORT,'immutable template media'); END;
                """.replace("template_authoring_", namespace + "_").replace("template_records_", namespace + "_records_").replace("template_media_", namespace + "_media_"))

    @contextmanager
    def transaction(self):
        if self.database_url:
            import psycopg
            with psycopg.connect(self.database_url) as connection:
                with connection.transaction():
                    # Serialize short state transitions across workers; never hold during inference/rendering.
                    connection.execute("SELECT pg_advisory_xact_lock(719260013)")
                    yield TemplateTransaction(connection, True, self.namespace)
        else:
            with closing(sqlite3.connect(self.path, timeout=30)) as connection:
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    yield TemplateTransaction(connection, namespace=self.namespace)

    def get(self, kind: str, key: str) -> dict:
        with self.transaction() as tx:
            result = tx.get(kind, key)
        if result is None:
            raise KeyError("Template record does not exist")
        return result

    def list(self, kind: str, limit: int = 100) -> list[dict]:
        with self.transaction() as tx:
            return tx.list(kind, limit)

    def history(self, kind: str, key: str, limit: int = 200) -> list[dict]:
        with self.transaction() as tx:
            return tx.history(kind, key, limit)
