"""PostgreSQL authority and restart-safe cache for the standalone Studio."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Iterator, Mapping
from uuid import UUID

from commander.ids import new_uuid7

from .studio_workspace import UniversalStudioWorkspace


_MUTATING_METHODS = frozenset({
    "save_configuration", "apply_template", "upload_asset", "select_phone_screen",
    "generate_phone_screen", "source_pexels", "approve_version",
})


class StudioRepository:
    """Store one mutable Studio snapshot plus immutable asset/version entities."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg

        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                yield connection

    @staticmethod
    def _files(root: Path) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            if relative.startswith("../") or relative.startswith("/"):
                raise RuntimeError("Studio workspace file escaped its authority root")
            files[relative] = path.read_bytes()
        return files

    def load(self) -> tuple[str, str, dict[str, bytes]] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,state_sha256 FROM universal_studio_workspaces
                     WHERE singleton=true"""
            ).fetchone()
            if row is None:
                return None
            workspace_id, state_sha256 = str(row[0]), str(row[1])
            files = connection.execute(
                """SELECT relative_path,content,content_sha256
                     FROM universal_studio_workspace_files WHERE workspace_id=%s
                     ORDER BY relative_path""",
                (row[0],),
            ).fetchall()
        restored: dict[str, bytes] = {}
        for relative, content, digest in files:
            data = bytes(content)
            if hashlib.sha256(data).hexdigest() != digest:
                raise RuntimeError("Studio database file digest mismatch")
            restored[str(relative)] = data
        return workspace_id, state_sha256, restored

    @staticmethod
    def _insert_edge(
        connection: Any, source_id: UUID, relation: str, target_id: UUID,
        attributes: Mapping[str, Any],
    ) -> None:
        from psycopg.types.json import Jsonb

        connection.execute(
            """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                 VALUES(%s,%s,%s,%s,%s) ON CONFLICT(source_id,relation,target_id) DO NOTHING""",
            (UUID(new_uuid7()), source_id, relation, target_id, Jsonb(dict(attributes))),
        )

    @staticmethod
    def _asset_documents(root: Path) -> list[dict[str, Any]]:
        documents: dict[str, dict[str, Any]] = {}
        assets = root / "assets"
        if not assets.is_dir():
            return []
        for metadata_path in sorted(assets.glob("*.json")):
            try:
                value = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entries = value.get("items") if metadata_path.name == "phone_screen_history.json" else [value]
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                filename = entry.get("filename")
                digest = entry.get("sha256")
                path = assets / str(filename)
                if not isinstance(digest, str) or not path.is_file():
                    continue
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != digest:
                    raise RuntimeError("Studio asset digest mismatch during database persistence")
                documents[digest] = {
                    "slot": (
                        "phone_screen" if str(filename).startswith("phone_screen")
                        else metadata_path.stem
                    ),
                    "sha256": digest,
                    "mime_type": entry.get("mime_type"),
                    "content": content,
                    "source": dict(entry.get("source") or {}),
                    "width": entry.get("width"),
                    "height": entry.get("height"),
                }
        return list(documents.values())

    @staticmethod
    def _version_documents(root: Path) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        versions = root / "versions"
        if not versions.is_dir():
            return values
        for path in sorted(versions.glob("*_v*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            render_path = versions / str(
                record.get("render_filename") or f"{record['template_id']}_v{record['version']}.png"
            )
            render = render_path.read_bytes()
            if hashlib.sha256(render).hexdigest() != record.get("render_sha256"):
                raise RuntimeError("Studio version render digest mismatch during database persistence")
            values.append({"record": record, "render": render})
        return values

    def persist(self, root: Path, *, state_sha256: str, template_id: str) -> str:
        from psycopg.types.json import Jsonb

        files = self._files(root)
        assets = self._asset_documents(root)
        versions = self._version_documents(root)
        with self.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended('universal-studio-singleton',0))"
            )
            row = connection.execute(
                "SELECT entity_id FROM universal_studio_workspaces WHERE singleton=true"
            ).fetchone()
            if row is None:
                workspace_id = UUID(new_uuid7())
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_workspace',%s)",
                    (workspace_id, Jsonb({"schema_version": 1, "scope": "owner_singleton"})),
                )
                connection.execute(
                    """INSERT INTO universal_studio_workspaces(
                           entity_id,singleton,template_id,state_sha256,requested_by
                       ) VALUES(%s,true,%s,%s,'owner-web')""",
                    (workspace_id, template_id, state_sha256),
                )
            else:
                workspace_id = row[0]
                connection.execute(
                    """UPDATE universal_studio_workspaces SET template_id=%s,state_sha256=%s,
                           updated_at=clock_timestamp() WHERE entity_id=%s""",
                    (template_id, state_sha256, workspace_id),
                )
            retained = set(files)
            for relative, content in files.items():
                connection.execute(
                    """INSERT INTO universal_studio_workspace_files(
                           workspace_id,relative_path,content_sha256,content
                       ) VALUES(%s,%s,%s,%s)
                       ON CONFLICT(workspace_id,relative_path) DO UPDATE SET
                         content_sha256=excluded.content_sha256,content=excluded.content,
                         updated_at=clock_timestamp()""",
                    (workspace_id, relative, hashlib.sha256(content).hexdigest(), content),
                )
            connection.execute(
                "DELETE FROM universal_studio_workspace_files WHERE workspace_id=%s AND NOT(relative_path=ANY(%s))",
                (workspace_id, list(retained) or ["__no_files__"]),
            )
            asset_ids: dict[str, UUID] = {}
            for asset in assets:
                existing = connection.execute(
                    """SELECT entity_id FROM universal_studio_assets
                         WHERE workspace_id=%s AND content_sha256=%s""",
                    (workspace_id, asset["sha256"]),
                ).fetchone()
                if existing is None:
                    asset_id = UUID(new_uuid7())
                    connection.execute(
                        "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_asset',%s)",
                        (asset_id, Jsonb({"schema_version": 1, "slot": asset["slot"]})),
                    )
                    connection.execute(
                        """INSERT INTO universal_studio_assets(
                               entity_id,workspace_id,slot,content_sha256,mime_type,width,height,
                               content,source
                           ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            asset_id, workspace_id, asset["slot"], asset["sha256"],
                            asset["mime_type"], asset["width"], asset["height"],
                            asset["content"], Jsonb(asset["source"]),
                        ),
                    )
                    self._insert_edge(
                        connection, workspace_id, "contains", asset_id,
                        {"member": "studio_asset", "slot": asset["slot"]},
                    )
                    reference_digest = asset["source"].get("reference_asset_sha256")
                    if isinstance(reference_digest, str):
                        reference = connection.execute(
                            """SELECT entity_id FROM universal_studio_assets
                                 WHERE workspace_id=%s AND content_sha256=%s""",
                            (workspace_id, reference_digest),
                        ).fetchone()
                        if reference is not None:
                            self._insert_edge(
                                connection, asset_id, "derived_from", reference[0],
                                {"input": "phone_screen_reference"},
                            )
                else:
                    asset_id = existing[0]
                asset_ids[asset["sha256"]] = asset_id
            previous_version_id: UUID | None = None
            for item in sorted(versions, key=lambda value: int(value["record"]["version"])):
                record = item["record"]
                existing = connection.execute(
                    """SELECT entity_id FROM universal_studio_versions
                         WHERE workspace_id=%s AND version=%s""",
                    (workspace_id, record["version"]),
                ).fetchone()
                if existing is None:
                    version_id = UUID(new_uuid7())
                    connection.execute(
                        "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_version',%s)",
                        (version_id, Jsonb({"schema_version": 1, "version": record["version"]})),
                    )
                    connection.execute(
                        """INSERT INTO universal_studio_versions(
                               entity_id,workspace_id,version,version_sha256,state_sha256,
                               render_sha256,record,render_png
                           ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            version_id, workspace_id, record["version"],
                            record["version_sha256"], record["state_sha256"],
                            record["render_sha256"], Jsonb(record), item["render"],
                        ),
                    )
                    self._insert_edge(
                        connection, workspace_id, "contains", version_id,
                        {"member": "studio_version", "version": record["version"]},
                    )
                    if previous_version_id is not None:
                        self._insert_edge(
                            connection, version_id, "supersedes", previous_version_id,
                            {"scope": "studio_version"},
                        )
                    for snapshot in record.get("assets", []):
                        asset_id = asset_ids.get(snapshot.get("sha256"))
                        if asset_id is not None:
                            self._insert_edge(
                                connection, version_id, "derived_from", asset_id,
                                {"input": "studio_asset", "slot": snapshot.get("slot")},
                            )
                else:
                    version_id = existing[0]
                previous_version_id = version_id
        return str(workspace_id)

    def identifiers(self, workspace_id: str) -> dict[str, dict[Any, str]]:
        with self.connection() as connection:
            assets = connection.execute(
                "SELECT content_sha256,entity_id FROM universal_studio_assets WHERE workspace_id=%s",
                (UUID(workspace_id),),
            ).fetchall()
            versions = connection.execute(
                "SELECT version,entity_id FROM universal_studio_versions WHERE workspace_id=%s",
                (UUID(workspace_id),),
            ).fetchall()
        return {
            "assets": {row[0]: str(row[1]) for row in assets},
            "versions": {int(row[0]): str(row[1]) for row in versions},
        }


class DatabaseStudioWorkspace:
    """Expose UniversalStudioWorkspace with PostgreSQL as the complete authority."""

    def __init__(self, workspace: UniversalStudioWorkspace, repository: StudioRepository) -> None:
        self.workspace = workspace
        self.repository = repository
        self._workspace_id = ""
        self._loaded = False
        self._lock = threading.RLock()

    def _restore(self, files: Mapping[str, bytes]) -> None:
        root = self.workspace.root.resolve()
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        for relative, content in files.items():
            path = (root / relative).resolve()
            if root not in path.parents:
                raise RuntimeError("Studio database file escaped its cache root")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.workspace.assets.mkdir(parents=True, exist_ok=True)
        self.workspace.versions.mkdir(parents=True, exist_ok=True)

    def _materialize_defaults(self) -> dict[str, Any]:
        """Persist implicit defaults so a later code release cannot redefine DB state."""

        detail = self.workspace.detail()
        if not (self.workspace.root / "template.json").is_file():
            self.workspace._atomic_json(self.workspace.root / "template.json", {
                "schema": "ptw.studio.template-selection.v1",
                "template_id": detail["template_id"],
            })
        if not (self.workspace.root / "configuration.json").is_file():
            self.workspace._atomic_json(
                self.workspace.root / "configuration.json", detail["configuration"],
            )
        if not (self.workspace.root / "content.json").is_file():
            self.workspace._atomic_json(
                self.workspace.root / "content.json", detail["content"],
            )
        return self.workspace.detail()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        stored = self.repository.load()
        if stored is not None:
            self._workspace_id, expected_state_sha256, files = stored
            self._restore(files)
            detail = self.workspace.detail()
            if detail["state_sha256"] != expected_state_sha256:
                raise RuntimeError("Studio database state digest does not match its restored files")
        detail = self._materialize_defaults()
        self._workspace_id = self.repository.persist(
            self.workspace.root,
            state_sha256=detail["state_sha256"], template_id=detail["template_id"],
        )
        self._loaded = True

    def _persist(self) -> None:
        detail = self._materialize_defaults()
        self._workspace_id = self.repository.persist(
            self.workspace.root,
            state_sha256=detail["state_sha256"], template_id=detail["template_id"],
        )

    def _enrich(self, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        identifiers = self.repository.identifiers(self._workspace_id)
        result = dict(value)
        if result.get("schema") == "ptw.studio.workspace.v8":
            result["workspace_id"] = self._workspace_id
            result["assets"] = [
                {**item, **({"asset_id": identifiers["assets"][item["sha256"]]}
                             if item.get("sha256") in identifiers["assets"] else {})}
                for item in result.get("assets", [])
            ]
            result["phone_screen_history"] = [
                {**item, **({"asset_id": identifiers["assets"][item["sha256"]]}
                             if item.get("sha256") in identifiers["assets"] else {})}
                for item in result.get("phone_screen_history", [])
            ]
            result["versions"] = [
                {**item, **({"version_id": identifiers["versions"][item["version"]]}
                             if item.get("version") in identifiers["versions"] else {})}
                for item in result.get("versions", [])
            ]
        elif isinstance(result.get("version"), int):
            version_id = identifiers["versions"].get(result["version"])
            if version_id:
                result["version_id"] = version_id
        return result

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.workspace, name)
        if not callable(target):
            return target

        def call(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                self._ensure_loaded()
                value = target(*args, **kwargs)
                if name in _MUTATING_METHODS:
                    try:
                        self._persist()
                    except Exception:
                        stored = self.repository.load()
                        if stored is not None:
                            self._workspace_id, _state_sha256, files = stored
                            self._restore(files)
                        raise
                    value = self.workspace.detail() if isinstance(value, dict) and value.get("schema") == "ptw.studio.workspace.v8" else value
                return self._enrich(value)

        return call
