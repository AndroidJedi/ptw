"""TikTok publication persistence and service facade."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
import threading
from typing import Any, Mapping
from uuid import UUID

from commander.ids import new_uuid7
from .local_brief_store import utc_now
from .meta_ads import DatabaseMetaAdsAuthority, _uuid
from .social_publishing.engine import SocialPublishingEngine
from .social_publishing.providers.tiktok import ANALYTICS_SCOPES, REQUIRED_SCOPES, TikTokConfiguration, TikTokPublishingAdapter


class LocalTikTokAuthority:
    def __init__(self, store: Any) -> None:
        self.store = store
        self._lock = threading.RLock()

    @contextmanager
    def lock(self, key: str):
        import fcntl
        path = self.store.root / "tiktok-locks"
        path.mkdir(exist_ok=True)
        with self._lock, (path / hashlib.sha256(key.encode()).hexdigest()).open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def list(self, project_id: str | None = None) -> list[dict[str, Any]]:
        return [item for item in self.store.list("tiktok_publications") if project_id is None or item["project_id"] == project_id]

    def get(self, identifier: str) -> dict[str, Any]:
        return self.store.get("tiktok_publications", _uuid(identifier, "publication_id"))

    def request(self, request_id: str) -> dict[str, Any] | None:
        return next((item for item in self.list() if item["request_id"] == request_id), None)

    def reserve(self, record: dict[str, Any], jpeg: bytes) -> dict[str, Any]:
        value = {**deepcopy(record), "delivery_base64": base64.b64encode(jpeg).decode()}
        self.store.append("tiktok_publications", value["publication_id"], value)
        source_id = value["specification"]["source"]["version_id"]
        if not self.store.history("studio_versions", source_id):
            source = value["specification"]["source"]
            self.store.append("studio_versions", source_id, {"version_id": source_id, "creative_id": source["creative_id"], "version": source["version"], "version_sha256": source["version_sha256"]})
        self.store.edge(source_id=value["project_id"], relation="contains", target_id=value["publication_id"])
        self.store.edge(source_id=value["publication_id"], relation="derived_from", target_id=source_id)
        if value["specification"].get("landing"):
            self.store.edge(source_id=value["publication_id"], relation="derived_from", target_id=value["specification"]["landing"]["event_id"])
        return value

    def update(self, identifier: str, **patch: Any) -> dict[str, Any]:
        value = self.get(identifier)
        value["state"] = {**value["state"], **patch, "updated_at": utc_now()}
        self.store.append("tiktok_publications", identifier, value)
        return value

    def attempt(self, identifier: str, stage: str, status: str) -> None:
        attempt_id = new_uuid7()
        self.store.append("tiktok_attempts", attempt_id, {"attempt_id": attempt_id, "publication_id": identifier, "stage": stage, "status": status, "created_at": utc_now()})
        self.store.edge(source_id=identifier, relation="contains", target_id=attempt_id)

    def attempts(self, identifier: str) -> list[dict[str, Any]]:
        return [item for item in self.store.list("tiktok_attempts") if item["publication_id"] == identifier]

    def delivery(self, token_sha: str) -> tuple[dict[str, Any], bytes]:
        value = next((item for item in self.list() if item["media_token_sha256"] == token_sha), None)
        if not value:
            raise KeyError("Media unavailable")
        return value, base64.b64decode(value["delivery_base64"], validate=True)

    def connection_record(self) -> dict[str, Any] | None:
        items = self.store.list("tiktok_connections")
        if not items:
            return None
        value = deepcopy(items[0])
        for key in ("token_nonce", "token_ciphertext"):
            if isinstance(value.get(key), str):
                value[key] = base64.b64decode(value[key], validate=True)
        return value

    def save_connection(self, record: Mapping[str, Any]) -> dict[str, Any]:
        current = self.connection_record()
        if current and current.get("open_id") and str(record.get("open_id")) != current["open_id"]:
            raise ValueError("TikTok account identity cannot be replaced")
        value = {**deepcopy(dict(record)), "connection_key": "natal_cast", "updated_at": utc_now()}
        for key in ("token_nonce", "token_ciphertext"):
            if isinstance(value.get(key), bytes):
                value[key] = base64.b64encode(value[key]).decode()
        self.store.append("tiktok_connections", "natal_cast", value)
        return self.connection_record() or value

    def save_oauth_state(self, state_sha256: str, actor: str, return_to: str, expires_at: str) -> None:
        self.store.append("tiktok_oauth_states", state_sha256, {"state_sha256": state_sha256, "requested_by": actor, "return_to": return_to, "expires_at": expires_at, "consumed_at": None, "created_at": utc_now()})

    def consume_oauth_state(self, state_sha256: str) -> dict[str, Any]:
        value = self.store.get("tiktok_oauth_states", state_sha256)
        if value.get("consumed_at") or datetime.fromisoformat(value["expires_at"]) <= datetime.now(timezone.utc):
            raise ValueError("TikTok authorization state expired or was already used")
        value = {**value, "consumed_at": utc_now()}
        self.store.append("tiktok_oauth_states", state_sha256, value)
        return value

    def disconnect_connection(self) -> None:
        current = self.connection_record()
        if current:
            self.save_connection({**current, "connected": False, "token_nonce": None, "token_ciphertext": None, "access_expires_at": None, "refresh_expires_at": None})


class DatabaseTikTokAuthority(DatabaseMetaAdsAuthority):
    @contextmanager
    def lock(self, key: str):
        import psycopg
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            connection.execute("SELECT pg_advisory_lock(hashtextextended(%s,0))", ("tiktok:" + key,))
            try:
                yield
            finally:
                connection.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", ("tiktok:" + key,))

    @staticmethod
    def _record(row: Any) -> dict[str, Any]:
        return {"publication_id": str(row[0]), "project_id": str(row[1]), "request_id": str(row[2]), "request_sha256": row[3], "specification": dict(row[4]), "state": dict(row[5]), "media_token_sha256": row[6], "created_at": row[7].isoformat()}

    _select = "SELECT entity_id,project_id,request_id,request_sha256,specification,state,media_token_sha256,created_at FROM tiktok_publications"

    def list(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(self._select + (" WHERE project_id=%s" if project_id else "") + " ORDER BY created_at DESC", (UUID(project_id),) if project_id else ()).fetchall()
        return [self._record(row) for row in rows]

    def get(self, identifier: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(self._select + " WHERE entity_id=%s", (UUID(identifier),)).fetchone()
        if row is None:
            raise KeyError("TikTok publication not found")
        return self._record(row)

    def request(self, request_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(self._select + " WHERE request_id=%s", (UUID(request_id),)).fetchone()
        return None if row is None else self._record(row)

    def reserve(self, record: dict[str, Any], jpeg: bytes) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        spec, identifier = record["specification"], record["publication_id"]
        source = spec["source"]
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'tiktok_publication',%s)", (UUID(identifier), Jsonb({"project_id": record["project_id"]})))
            connection.execute("""INSERT INTO tiktok_publications(entity_id,project_id,source_creative_id,source_version_id,request_id,request_sha256,specification,state,delivery_jpeg,media_token_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (UUID(identifier), UUID(record["project_id"]), UUID(source["creative_id"]), UUID(source["version_id"]), UUID(record["request_id"]), record["request_sha256"], Jsonb(spec), Jsonb(record["state"]), jpeg, record["media_token_sha256"]))
            self._edge(connection, record["project_id"], "contains", identifier, {"member": "tiktok_publication"})
            self._edge(connection, identifier, "derived_from", source["version_id"], {"input": "approved_post"})
            if spec.get("landing"):
                self._edge(connection, identifier, "derived_from", spec["landing"]["event_id"], {"input": "published_landing"})
        return self.get(identifier)

    def update(self, identifier: str, **patch: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute("UPDATE tiktok_publications SET state=state || %s WHERE entity_id=%s", (Jsonb({**patch, "updated_at": utc_now()}), UUID(identifier)))
        return self.get(identifier)

    def attempt(self, identifier: str, stage: str, status: str) -> None:
        from psycopg.types.json import Jsonb
        attempt_id = new_uuid7()
        record = {"attempt_id": attempt_id, "publication_id": identifier, "stage": stage, "status": status, "created_at": utc_now()}
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'tiktok_publication_attempt',%s)", (UUID(attempt_id), Jsonb({"stage": stage})))
            connection.execute("INSERT INTO tiktok_publication_attempts(entity_id,publication_id,record) VALUES(%s,%s,%s)", (UUID(attempt_id), UUID(identifier), Jsonb(record)))
            self._edge(connection, identifier, "contains", attempt_id, {"member": "tiktok_publication_attempt"})

    def attempts(self, identifier: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return [dict(row[0]) for row in connection.execute("SELECT record FROM tiktok_publication_attempts WHERE publication_id=%s ORDER BY created_at", (UUID(identifier),)).fetchall()]

    def delivery(self, token_sha: str) -> tuple[dict[str, Any], bytes]:
        with self.connection() as connection:
            row = connection.execute("SELECT entity_id,delivery_jpeg FROM tiktok_publications WHERE media_token_sha256=%s", (token_sha,)).fetchone()
        if row is None:
            raise KeyError("Media unavailable")
        return self.get(str(row[0])), bytes(row[1])

    def connection_record(self) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT open_id,username,nickname,scopes,token_nonce,token_ciphertext,access_expires_at,refresh_expires_at,connected,connected_at,updated_at FROM tiktok_account_connections WHERE connection_key='natal_cast'").fetchone()
        if not row:
            return None
        return {"open_id": row[0], "username": row[1], "nickname": row[2], "scopes": list(row[3]), "token_nonce": bytes(row[4]) if row[4] is not None else None, "token_ciphertext": bytes(row[5]) if row[5] is not None else None, "access_expires_at": row[6].isoformat() if row[6] else None, "refresh_expires_at": row[7].isoformat() if row[7] else None, "connected": row[8], "connected_at": row[9].isoformat() if row[9] else None, "updated_at": row[10].isoformat()}

    def save_connection(self, record: Mapping[str, Any]) -> dict[str, Any]:
        with self.connection() as connection:
            connection.execute("""INSERT INTO tiktok_account_connections(connection_key,open_id,username,nickname,scopes,token_nonce,token_ciphertext,access_expires_at,refresh_expires_at,connected,connected_at) VALUES('natal_cast',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(connection_key) DO UPDATE SET open_id=excluded.open_id,username=excluded.username,nickname=excluded.nickname,scopes=excluded.scopes,token_nonce=excluded.token_nonce,token_ciphertext=excluded.token_ciphertext,access_expires_at=excluded.access_expires_at,refresh_expires_at=excluded.refresh_expires_at,connected=excluded.connected,connected_at=COALESCE(tiktok_account_connections.connected_at,excluded.connected_at),updated_at=clock_timestamp()""", (record.get("open_id"), record.get("username"), record.get("nickname"), list(record.get("scopes") or []), record.get("token_nonce"), record.get("token_ciphertext"), record.get("access_expires_at"), record.get("refresh_expires_at"), bool(record.get("connected")), record.get("connected_at")))
        return self.connection_record() or {}

    def save_oauth_state(self, state_sha256: str, actor: str, return_to: str, expires_at: str) -> None:
        with self.connection() as connection:
            connection.execute("INSERT INTO tiktok_oauth_states(state_sha256,requested_by,return_to,expires_at) VALUES(%s,%s,%s,%s)", (state_sha256, actor, return_to, expires_at))

    def consume_oauth_state(self, state_sha256: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("UPDATE tiktok_oauth_states SET consumed_at=clock_timestamp() WHERE state_sha256=%s AND consumed_at IS NULL AND expires_at>clock_timestamp() RETURNING requested_by,return_to,expires_at", (state_sha256,)).fetchone()
        if not row:
            raise ValueError("TikTok authorization state expired or was already used")
        return {"requested_by": row[0], "return_to": row[1], "expires_at": row[2].isoformat()}

    def disconnect_connection(self) -> None:
        with self.connection() as connection:
            connection.execute("UPDATE tiktok_account_connections SET connected=false,token_nonce=NULL,token_ciphertext=NULL,access_expires_at=NULL,refresh_expires_at=NULL,updated_at=clock_timestamp() WHERE connection_key='natal_cast'")


class TikTokPublicationService:
    def __init__(self, authority: Any, sources: Any, configuration: TikTokConfiguration, adapter: TikTokPublishingAdapter | None = None) -> None:
        self.authority, self.sources, self.configuration = authority, sources, configuration
        self.adapter = adapter or TikTokPublishingAdapter(authority, configuration)
        self.engine = SocialPublishingEngine(authority, sources, self.adapter, origin=configuration.media_origin)

    def connection(self, *, verify: bool = True) -> dict[str, Any]: return self.engine.connection(verify=verify)
    def analytics_connection(self, *, verify: bool = True) -> dict[str, Any]:
        if self.adapter is None:
            return {"provider": "tiktok", "configured": False, "available": False,
                    "required_scopes": sorted(ANALYTICS_SCOPES),
                    "explanation": "Configure TikTok before collecting video insights."}
        return self.adapter.analytics_connection(verify=verify)
    def insights(self, post_ids: list[str]) -> dict[str, Any]:
        return self.adapter.video_insights(post_ids)
    def workspace(self, project_id: str) -> dict[str, Any]: return self.engine.workspace(project_id)
    def publications(self, project_id: str) -> dict[str, Any]: return self.engine.publications(project_id)
    def detail(self, project_id: str, identifier: str) -> dict[str, Any]: return self.engine.detail(project_id, identifier)
    def reserve(self, project_id: str, request: Mapping[str, Any], actor: str) -> tuple[dict[str, Any], bool]: return self.engine.reserve(project_id, request, actor)
    def media(self, token: str) -> bytes: return self.engine.media(token)
    def execute(self, identifier: str, *, reconcile_only: bool = False) -> dict[str, Any]: return self.engine.execute(identifier, reconcile_only=reconcile_only)
    def retry(self, project_id: str, identifier: str) -> dict[str, Any]: return self.engine.retry(project_id, identifier)
    def recover_interrupted(self) -> list[str]: return self.engine.recover_interrupted()
    def maintain(self) -> None: self.engine.maintain()

    def oauth_start(self, actor: str, return_to: str = "/") -> dict[str, Any]:
        if not self.configuration.configured:
            raise RuntimeError("TikTok OAuth is not configured")
        if not re.fullmatch(r"/[A-Za-z0-9_/?&=.-]{0,500}", return_to) or return_to.startswith("//"):
            raise ValueError("TikTok return path is invalid")
        state = secrets.token_urlsafe(32)
        self.authority.save_oauth_state(hashlib.sha256(state.encode()).hexdigest(), actor, return_to, (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat())
        return {"authorization_url": self.adapter.oauth_url(state)}

    def oauth_callback(self, code: str, state: str) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9._~-]{1,1024}", code) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", state):
            raise ValueError("TikTok authorization response is invalid")
        oauth = self.authority.consume_oauth_state(hashlib.sha256(state.encode()).hexdigest())
        value = self.adapter.exchange_code(code)
        scopes = set(str(value.get("scope") or "").split(","))
        if not REQUIRED_SCOPES <= scopes:
            raise ValueError("TikTok authorization did not grant the required scopes")
        open_id = str(value.get("open_id") or "")
        creator = self.adapter.creator_info(str(value.get("access_token") or ""))
        username = str(creator.get("creator_username") or "").lstrip("@").lower()
        if not open_id or username != self.configuration.expected_username:
            raise ValueError(f"Only @{self.configuration.expected_username} may be connected")
        current = self.authority.connection_record()
        if current and current.get("open_id") and current["open_id"] != open_id:
            raise ValueError("TikTok account does not match the pinned account identity")
        nonce, ciphertext = self.adapter.cipher.encrypt({"access_token": value["access_token"], "refresh_token": value["refresh_token"]})
        now = datetime.now(timezone.utc)
        self.authority.save_connection({"open_id": open_id, "username": username, "nickname": creator.get("creator_nickname"), "scopes": sorted(scopes), "token_nonce": nonce, "token_ciphertext": ciphertext, "access_expires_at": (now + timedelta(seconds=int(value["expires_in"]))).isoformat(), "refresh_expires_at": (now + timedelta(seconds=int(value["refresh_expires_in"]))).isoformat(), "connected": True, "connected_at": now.isoformat()})
        return {"connected": True, "account": {"open_id": open_id, "username": username}, "return_to": oauth["return_to"]}

    def disconnect(self) -> dict[str, Any]:
        self.adapter.revoke()
        self.authority.disconnect_connection()
        return {"connected": False}
