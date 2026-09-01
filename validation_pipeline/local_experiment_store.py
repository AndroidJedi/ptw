"""Digest-verified append-only file authority for local owner experiments."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Callable, Mapping

from commander.ids import new_uuid7


_KIND = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_ACTIVE_RUN_STATUSES = frozenset({"queued", "generating"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class LocalExperimentStore:
    """One-record-per-revision authority; projections are reconstructed on read."""

    schema = "ptw.local-owner-experiment-store.v2"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.records = self.root / "records"
        self.artifacts = self.root / "artifacts"
        self.idempotency = self.root / "idempotency"
        self._lock = threading.RLock()
        for path in (self.records, self.artifacts, self.idempotency):
            path.mkdir(parents=True, exist_ok=True)
        marker = self.root / "store.json"
        if not marker.exists():
            self._atomic_json(marker, {"schema": self.schema, "created_at": utc_now()})
        else:
            value = json.loads(marker.read_text(encoding="utf-8"))
            if value.get("schema") != self.schema:
                raise ValueError("local experiment store schema is invalid")

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{new_uuid7()}.tmp")
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    @staticmethod
    def _atomic_bytes(path: Path, data: bytes, *, replace: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{new_uuid7()}.tmp")
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if not replace and path.exists():
            temporary.unlink()
            raise FileExistsError(f"immutable local artifact already exists: {path.name}")
        os.replace(temporary, path)

    @staticmethod
    def _kind(kind: str) -> str:
        if not _KIND.fullmatch(kind):
            raise ValueError("local record kind is invalid")
        return kind

    def _entity_dir(self, kind: str, entity_id: str) -> Path:
        return self.records / self._kind(kind) / str(entity_id)

    def append(self, kind: str, entity_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            directory = self._entity_dir(kind, entity_id)
            paths = sorted(directory.glob("*.json")) if directory.exists() else []
            previous_sha256 = None
            if paths:
                previous = self._read_envelope(paths[-1])
                previous_sha256 = previous["record_sha256"]
            revision = len(paths) + 1
            body = {
                "schema": "ptw.local-append-record.v1",
                "kind": kind,
                "entity_id": str(entity_id),
                "revision": revision,
                "previous_sha256": previous_sha256,
                "recorded_at": utc_now(),
                "payload": deepcopy(dict(payload)),
            }
            envelope = {**body, "record_sha256": sha256_json(body)}
            path = directory / f"{revision:08d}.json"
            if path.exists():
                raise FileExistsError("append-only local revision already exists")
            self._atomic_json(path, envelope)
            return deepcopy(envelope)

    @staticmethod
    def _read_envelope(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"local record is unreadable: {path}") from error
        digest = value.get("record_sha256")
        body = {key: item for key, item in value.items() if key != "record_sha256"}
        if not isinstance(digest, str) or sha256_json(body) != digest:
            raise ValueError(f"local record digest mismatch: {path}")
        return value

    def history(self, kind: str, entity_id: str) -> list[dict[str, Any]]:
        directory = self._entity_dir(kind, entity_id)
        paths = sorted(directory.glob("*.json")) if directory.exists() else []
        values = [self._read_envelope(path) for path in paths]
        previous = None
        for index, value in enumerate(values, 1):
            if value["revision"] != index or value["previous_sha256"] != previous:
                raise ValueError("local append-only record chain is broken")
            previous = value["record_sha256"]
        return values

    def get(self, kind: str, entity_id: str) -> dict[str, Any]:
        values = self.history(kind, entity_id)
        if not values:
            raise KeyError(f"local {kind} was not found")
        return deepcopy(values[-1]["payload"])

    def list(self, kind: str) -> list[dict[str, Any]]:
        root = self.records / self._kind(kind)
        if not root.is_dir():
            return []
        values = [self.get(kind, path.name) for path in root.iterdir() if path.is_dir()]
        return sorted(values, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    def reserve_request(
        self, *, scope: str, request_id: str, fingerprint: Mapping[str, Any],
        create_target: Callable[[], str] = new_uuid7,
    ) -> tuple[str, bool]:
        scope = self._kind(scope)
        digest = sha256_json(fingerprint)
        path = self.idempotency / scope / f"{request_id}.json"
        with self._lock:
            if path.exists():
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get("request_sha256") != digest:
                    raise ValueError("idempotency request ID was reused with different input")
                return str(value["target_id"]), False
            target_id = create_target()
            self._atomic_json(path, {
                "schema": "ptw.local-idempotency.v1", "scope": scope,
                "request_id": request_id, "request_sha256": digest,
                "target_id": target_id, "created_at": utc_now(),
            })
            return target_id, True

    def request_target(
        self, *, scope: str, request_id: str, fingerprint: Mapping[str, Any],
    ) -> str | None:
        """Resolve an existing idempotency reservation without creating one."""

        scope = self._kind(scope)
        path = self.idempotency / scope / f"{request_id}.json"
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("request_sha256") != sha256_json(fingerprint):
            raise ValueError("idempotency request ID was reused with different input")
        return str(value["target_id"])

    def write_artifact(
        self, namespace: str, artifact_id: str, filename: str, data: bytes,
    ) -> dict[str, Any]:
        if Path(filename).name != filename or not filename:
            raise ValueError("local artifact filename must be one safe basename")
        path = self.artifacts / self._kind(namespace) / artifact_id / filename
        digest = hashlib.sha256(data).hexdigest()
        with self._lock:
            if path.exists():
                existing = path.read_bytes()
                if hashlib.sha256(existing).hexdigest() != digest:
                    raise FileExistsError("immutable artifact path contains different bytes")
            else:
                self._atomic_bytes(path, data)
        return {"path": str(path.relative_to(self.root)), "sha256": digest, "byte_count": len(data)}

    def artifact(self, relative_path: str, *, expected_sha256: str | None = None) -> bytes:
        path = (self.root / relative_path).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("local artifact path escapes its authority root")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("local artifact digest mismatch")
        return data

    def edge(self, *, source_id: str, relation: str, target_id: str, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        edge_id = new_uuid7()
        value = {
            "edge_id": edge_id, "source_id": source_id, "relation": relation,
            "target_id": target_id, "evidence": dict(evidence or {}),
            "created_at": utc_now(),
        }
        self.append("edges", edge_id, value)
        return value

    def active_run_ids(self) -> list[str]:
        return [
            str(item["run_id"]) for item in self.list("runs")
            if item.get("status") in _ACTIVE_RUN_STATUSES
        ]

    def recover_interrupted(self) -> list[str]:
        recovered: list[str] = []
        for run in self.list("runs"):
            if run.get("status") not in _ACTIVE_RUN_STATUSES:
                continue
            checkpoints = [
                item for item in self.list("checkpoints")
                if item.get("run_id") == run["run_id"]
            ]
            latest = checkpoints[0] if checkpoints else None
            updated = {
                **run, "status": "queued", "current_stage": "queued",
                "recovered_from_checkpoint_id": None if latest is None else latest["checkpoint_id"],
                "updated_at": utc_now(),
            }
            self.append("runs", str(run["run_id"]), updated)
            recovered.append(str(run["run_id"]))
        return recovered
