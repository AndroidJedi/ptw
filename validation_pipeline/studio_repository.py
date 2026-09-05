"""PostgreSQL authority and restart-safe caches for Project Studio creatives."""

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
from .phone_hero_styles import normalize_phone_hero_creative_direction
from .studio_creatives import (
    GLOBAL_SKILL_SCOPE, PROJECT_SKILL_SCOPE, _append_lesson, _skill_document,
    verified_skill_snapshot,
)


_MUTATING_METHODS = frozenset({
    "save_configuration", "apply_template", "upload_asset", "select_phone_screen",
    "generate_phone_screen", "source_pexels", "approve_version", "approve_configuration",
})


class StudioRepository:
    """Store scoped mutable creative snapshots plus immutable members."""

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

    def load_creative(self, workspace_id: str) -> tuple[str, dict[str, bytes]] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT state_sha256 FROM universal_studio_workspaces WHERE entity_id=%s",
                (UUID(workspace_id),),
            ).fetchone()
            if row is None:
                raise KeyError(workspace_id)
            if row[0] is None:
                return None
            files = connection.execute(
                """SELECT relative_path,content,content_sha256
                     FROM universal_studio_workspace_files WHERE workspace_id=%s
                     ORDER BY relative_path""",
                (UUID(workspace_id),),
            ).fetchall()
        restored: dict[str, bytes] = {}
        for relative, content, digest in files:
            data = bytes(content)
            if hashlib.sha256(data).hexdigest() != digest:
                raise RuntimeError("Studio database file digest mismatch")
            restored[str(relative)] = data
        return str(row[0]), restored

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

    def persist_creative(
        self, root: Path, *, workspace_id: str, state_sha256: str,
        template_id: str, template_version: int, template_sha256: str,
    ) -> str:
        """Persist one already-reserved creative workspace and immutable members."""

        from psycopg.types.json import Jsonb

        workspace_uuid = UUID(workspace_id)
        files = self._files(root)
        assets = self._asset_documents(root)
        versions = self._version_documents(root)
        with self.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"studio-creative:{workspace_id}",),
            )
            changed = connection.execute(
                """UPDATE universal_studio_workspaces SET template_id=%s,template_version=%s,
                         template_sha256=%s,state_sha256=%s,updated_at=clock_timestamp()
                     WHERE entity_id=%s""",
                (template_id, template_version, template_sha256, state_sha256, workspace_uuid),
            ).rowcount
            if changed != 1:
                raise KeyError(workspace_id)
            retained = set(files)
            for relative, content in files.items():
                connection.execute(
                    """INSERT INTO universal_studio_workspace_files(
                           workspace_id,relative_path,content_sha256,content
                       ) VALUES(%s,%s,%s,%s)
                       ON CONFLICT(workspace_id,relative_path) DO UPDATE SET
                         content_sha256=excluded.content_sha256,content=excluded.content,
                         updated_at=clock_timestamp()""",
                    (workspace_uuid, relative, hashlib.sha256(content).hexdigest(), content),
                )
            connection.execute(
                "DELETE FROM universal_studio_workspace_files WHERE workspace_id=%s AND NOT(relative_path=ANY(%s))",
                (workspace_uuid, list(retained) or ["__no_files__"]),
            )
            asset_ids: dict[str, UUID] = {}
            for asset in assets:
                existing = connection.execute(
                    """SELECT entity_id FROM universal_studio_assets
                         WHERE workspace_id=%s AND content_sha256=%s""",
                    (workspace_uuid, asset["sha256"]),
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
                            asset_id, workspace_uuid, asset["slot"], asset["sha256"],
                            asset["mime_type"], asset["width"], asset["height"],
                            asset["content"], Jsonb(asset["source"]),
                        ),
                    )
                    self._insert_edge(
                        connection, workspace_uuid, "contains", asset_id,
                        {"member": "studio_asset", "slot": asset["slot"]},
                    )
                    reference_digest = asset["source"].get("reference_asset_sha256")
                    if isinstance(reference_digest, str):
                        reference = connection.execute(
                            """SELECT entity_id FROM universal_studio_assets
                                 WHERE workspace_id=%s AND content_sha256=%s""",
                            (workspace_uuid, reference_digest),
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
                    (workspace_uuid, record["version"]),
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
                            version_id, workspace_uuid, record["version"],
                            record["version_sha256"], record["state_sha256"],
                            record["render_sha256"], Jsonb(record), item["render"],
                        ),
                    )
                    self._insert_edge(
                        connection, workspace_uuid, "contains", version_id,
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
        return workspace_id

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


class DatabaseCreativeWorkspace:
    """Expose one reserved creative with PostgreSQL-owned workspace bytes."""

    def __init__(
        self, workspace: UniversalStudioWorkspace, repository: StudioRepository,
        workspace_id: str,
    ) -> None:
        self.workspace = workspace
        self.repository = repository
        self.workspace_id = str(UUID(workspace_id))
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

    def _persist(self) -> None:
        detail = self.workspace.detail()
        for name, value in (
            ("template.json", {"schema": "ptw.studio.template-selection.v1", "template_id": detail.get("template_id") or detail["catalog"]["template_id"]}),
            ("configuration.json", detail["configuration"]),
            ("content.json", detail["content"]),
        ):
            path = self.workspace.root / name
            if not path.is_file():
                self.workspace._atomic_json(path, value)
        detail = self.workspace.detail()
        self.repository.persist_creative(
            self.workspace.root, workspace_id=self.workspace_id,
            state_sha256=detail["state_sha256"],
            template_id=str(detail.get("template_id") or detail["catalog"]["template_id"]),
            template_version=int(detail["catalog"]["template_version"]),
            template_sha256=str(detail["template_sha256"]),
        )

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        stored = self.repository.load_creative(self.workspace_id)
        if stored is not None:
            expected, files = stored
            self._restore(files)
            if self.workspace.detail()["state_sha256"] != expected:
                raise RuntimeError("Studio database state digest does not match its restored files")
        self._persist()
        self._loaded = True

    def _enrich(self, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        identifiers = self.repository.identifiers(self.workspace_id)
        result = dict(value)
        if result.get("schema") == "ptw.studio.workspace.v8":
            result["workspace_id"] = self.workspace_id
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
                        stored = self.repository.load_creative(self.workspace_id)
                        if stored is not None:
                            _expected, files = stored
                            self._restore(files)
                        raise
                    if isinstance(value, dict) and value.get("schema") == "ptw.studio.workspace.v8":
                        value = self.workspace.detail()
                return self._enrich(value)
        return call


class DatabaseStudioAuthority:
    """PostgreSQL metadata and graph authority for project Studio creatives."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.repository = StudioRepository(database_url)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        with self.repository.connection() as connection:
            yield connection

    def project(self, project_id: str) -> dict[str, Any]:
        from .repository import ValidationRepository
        return ValidationRepository(self.database_url).get_project(str(UUID(project_id)))

    def brief(self, brief_id: str) -> dict[str, Any]:
        from .repository import ValidationRepository
        return ValidationRepository(self.database_url).get_brief(str(UUID(brief_id)))

    @staticmethod
    def _creative_row(row: Any) -> dict[str, Any]:
        return {
            "creative_id": str(row[0]),
            "project_id": str(row[1]),
            "source_brief_id": str(row[2]),
            "ordinal": int(row[3]), "origin": row[4], "template_id": row[5],
            "template_version": row[6], "template_sha256": row[7], "status": row[8],
            "state_sha256": row[9], "generation": dict(row[10] or {}),
            "learning_baseline": None if row[11] is None else dict(row[11]),
            "learning_baseline_sha256": row[12],
            "latest_checkpoint_id": None if row[13] is None else str(row[13]),
            "requested_by": row[14], "created_at": row[15].isoformat(),
            "updated_at": row[16].isoformat(), "approved_version_count": int(row[17]),
        }

    @staticmethod
    def _creative_select() -> str:
        return """SELECT workspace.entity_id,workspace.project_id,workspace.source_brief_id,
                         workspace.ordinal,workspace.origin,workspace.template_id,
                         workspace.template_version,workspace.template_sha256,workspace.status,
                         workspace.state_sha256,workspace.generation,workspace.learning_baseline,
                         workspace.learning_baseline_sha256,workspace.latest_checkpoint_id,
                         workspace.requested_by,workspace.created_at,workspace.updated_at,
                         (SELECT count(*) FROM universal_studio_versions version
                           WHERE version.workspace_id=workspace.entity_id)
                    FROM universal_studio_workspaces workspace"""

    def get_creative(self, creative_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._creative_select() + " WHERE workspace.entity_id=%s", (UUID(creative_id),),
            ).fetchone()
        if row is None:
            raise KeyError(creative_id)
        return self._creative_row(row)

    def list_creatives(self, project_id: str) -> list[dict[str, Any]]:
        self.project(project_id)
        with self.connection() as connection:
            rows = connection.execute(
                self._creative_select() + " WHERE workspace.project_id=%s ORDER BY workspace.created_at DESC",
                (UUID(project_id),),
            ).fetchall()
        return [self._creative_row(row) for row in rows]

    def create_creative(
        self, *, project_id: str, brief_id: str, template_id: str,
        requested_by: str, origin: str, creative_direction: Mapping[str, Any] | None = None,
        require_approved_previous: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        project = self.project(project_id)
        if template_id not in {"universal_ad", "phone_metrics"}:
            raise ValueError("Studio template is invalid")
        if template_id == "phone_metrics":
            if creative_direction is None:
                raise ValueError("Phone Metrics creative direction is required")
            creative_direction = normalize_phone_hero_creative_direction(creative_direction)
        elif creative_direction is not None:
            raise ValueError("creative direction is available only for Phone Metrics")
        if origin not in {"brief_generation", "approved_variant"}:
            raise ValueError("Studio creative requires approved Product Brief lineage")
        with self.connection() as connection:
            brief = self.brief(brief_id)
            if brief["project_id"] != project_id or not brief["approved"]:
                raise ValueError("Studio creative requires an approved Brief in this Project")
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"studio-brief:{brief_id}",),
            )
            siblings = connection.execute(
                "SELECT entity_id,ordinal,template_id,generation FROM universal_studio_workspaces WHERE source_brief_id=%s ORDER BY ordinal",
                (UUID(brief_id),),
            ).fetchall()
            if siblings and not require_approved_previous:
                if siblings[0][2] != template_id:
                    raise ValueError("Product Brief already reserved a different Studio template")
                if template_id == "phone_metrics" and dict(siblings[0][3] or {}).get("creative_direction") != creative_direction:
                    raise ValueError("Product Brief already reserved a different Phone Metrics creative direction")
                return self.get_creative(str(siblings[0][0])), False
            if require_approved_previous:
                if not siblings:
                    raise ValueError("create the first creative through Brief approval")
                approved = connection.execute(
                    """SELECT 1 FROM universal_studio_versions version
                        WHERE version.workspace_id=%s LIMIT 1""",
                    (siblings[-1][0],),
                ).fetchone()
                if approved is None:
                    raise ValueError("approve the current creative before creating another from this Brief")
            ordinal = len(siblings) + 1
            creative_id = UUID(new_uuid7())
            attributes = {"schema_version": 1, "project_id": project_id, "origin": origin}
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_workspace',%s)",
                (creative_id, Jsonb(attributes)),
            )
            connection.execute(
                """INSERT INTO universal_studio_workspaces(
                       entity_id,project_id,source_brief_id,ordinal,origin,template_id,status,requested_by,generation
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    creative_id, UUID(project_id), UUID(brief_id),
                    ordinal, origin, template_id, "queued", requested_by,
                    Jsonb({} if creative_direction is None else {"creative_direction": creative_direction}),
                ),
            )
            self.repository._insert_edge(
                connection, UUID(project_id), "contains", creative_id,
                {"member": "studio_creative", "ordinal": ordinal},
            )
            self.repository._insert_edge(
                connection, creative_id, "derived_from", UUID(brief_id),
                {"input": "approved_product_brief"},
            )
        self.ensure_project_skill(project_id)
        self.ensure_global_skill()
        value = self.get_creative(str(creative_id))
        value["project_name"] = project["name"]
        return value, True

    def approve_and_create_creative(
        self, *, brief_id: str, template_id: str, requested_by: str,
        creative_direction: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool, bool]:
        """Atomically approve one completed Brief and reserve its first creative."""

        from psycopg.types.json import Jsonb

        if template_id not in {"universal_ad", "phone_metrics"}:
            raise ValueError("Studio template is invalid")
        if template_id == "phone_metrics":
            if creative_direction is None:
                raise ValueError("Phone Metrics creative direction is required")
            creative_direction = normalize_phone_hero_creative_direction(creative_direction)
        elif creative_direction is not None:
            raise ValueError("creative direction is available only for Phone Metrics")
        brief_uuid = UUID(brief_id)
        with self.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"studio-brief:{brief_id}",),
            )
            brief = connection.execute(
                "SELECT project_id,status,document FROM product_briefs WHERE entity_id=%s",
                (brief_uuid,),
            ).fetchone()
            if brief is None:
                raise KeyError(brief_id)
            if brief[1] != "completed" or brief[2] is None:
                raise ValueError("only a completed Product Brief can be approved")
            approved_now = connection.execute(
                """INSERT INTO product_brief_approvals(id,brief_id,approved_by)
                   VALUES(%s,%s,%s) ON CONFLICT(brief_id) DO NOTHING""",
                (UUID(new_uuid7()), brief_uuid, requested_by),
            ).rowcount == 1
            existing = connection.execute(
                """SELECT entity_id,generation FROM universal_studio_workspaces
                    WHERE source_brief_id=%s AND ordinal=1""",
                (brief_uuid,),
            ).fetchone()
            if existing is not None:
                creative_id = existing[0]
                existing_template = connection.execute(
                    "SELECT template_id FROM universal_studio_workspaces WHERE entity_id=%s",
                    (creative_id,),
                ).fetchone()[0]
                if existing_template != template_id:
                    raise ValueError("Product Brief already reserved a different Studio template")
                if template_id == "phone_metrics" and dict(existing[1] or {}).get("creative_direction") != creative_direction:
                    raise ValueError("Product Brief already reserved a different Phone Metrics creative direction")
                creative_created = False
            else:
                creative_id = UUID(new_uuid7())
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_workspace',%s)",
                    (creative_id, Jsonb({
                        "schema_version": 1, "project_id": str(brief[0]),
                        "origin": "brief_generation",
                    })),
                )
                connection.execute(
                    """INSERT INTO universal_studio_workspaces(
                           entity_id,project_id,source_brief_id,ordinal,origin,template_id,status,requested_by,generation
                       ) VALUES(%s,%s,%s,1,'brief_generation',%s,'queued',%s,%s)""",
                    (
                        creative_id, brief[0], brief_uuid, template_id, requested_by,
                        Jsonb({} if creative_direction is None else {"creative_direction": creative_direction}),
                    ),
                )
                self.repository._insert_edge(
                    connection, brief[0], "contains", creative_id,
                    {"member": "studio_creative", "ordinal": 1},
                )
                self.repository._insert_edge(
                    connection, creative_id, "derived_from", brief_uuid,
                    {"input": "approved_product_brief"},
                )
                creative_created = True
        self.ensure_project_skill(str(brief[0]))
        self.ensure_global_skill()
        return self.get_creative(str(creative_id)), approved_now, creative_created

    def update_creative(self, creative_id: str, **patch: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        allowed = {
            "template_id", "template_version", "template_sha256", "status", "state_sha256",
            "generation", "learning_baseline", "learning_baseline_sha256", "latest_checkpoint_id",
        }
        if not set(patch) <= allowed:
            raise ValueError("Studio creative update fields are invalid")
        assignments = []
        values: list[Any] = []
        for key, value in patch.items():
            assignments.append(f"{key}=%s")
            if key in {"generation", "learning_baseline"} and value is not None:
                value = Jsonb(value)
            elif key == "latest_checkpoint_id" and value is not None:
                value = UUID(value)
            values.append(value)
        if not assignments:
            return self.get_creative(creative_id)
        values.append(UUID(creative_id))
        with self.connection() as connection:
            changed = connection.execute(
                f"UPDATE universal_studio_workspaces SET {','.join(assignments)},updated_at=clock_timestamp() WHERE entity_id=%s",
                values,
            ).rowcount
        if changed != 1:
            raise KeyError(creative_id)
        return self.get_creative(creative_id)

    @staticmethod
    def _skill_row(row: Any) -> dict[str, Any]:
        content = str(row[4])
        return verified_skill_snapshot({
            "skill_snapshot_id": str(row[0]), "scope": row[1],
            "project_id": None if row[2] is None else str(row[2]), "version": int(row[3]),
            "content": content, "content_sha256": row[5],
            "source_checkpoint_id": None if row[6] is None else str(row[6]),
            "created_at": row[7].isoformat(),
        })

    def _append_skill(
        self, *, scope: str, project_id: str | None, content: str,
        source_checkpoint_id: str | None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        with self.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"studio-skill:{scope}:{project_id or 'global'}",),
            )
            if source_checkpoint_id is not None:
                existing = connection.execute(
                    """SELECT entity_id,scope,project_id,version,content,content_sha256,
                              source_checkpoint_id,created_at FROM studio_skill_snapshots
                        WHERE scope=%s AND project_id IS NOT DISTINCT FROM %s
                          AND source_checkpoint_id=%s""",
                    (
                        scope, None if project_id is None else UUID(project_id),
                        UUID(source_checkpoint_id),
                    ),
                ).fetchone()
                if existing is not None:
                    return self._skill_row(existing)
            previous = connection.execute(
                """SELECT entity_id,version FROM studio_skill_snapshots
                    WHERE scope=%s AND project_id IS NOT DISTINCT FROM %s
                    ORDER BY version DESC LIMIT 1""",
                (scope, None if project_id is None else UUID(project_id)),
            ).fetchone()
            snapshot_id = UUID(new_uuid7())
            version = 1 if previous is None else int(previous[1]) + 1
            digest = hashlib.sha256(content.encode()).hexdigest()
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_skill_snapshot',%s)",
                (snapshot_id, Jsonb({"scope": scope, "version": version})),
            )
            connection.execute(
                """INSERT INTO studio_skill_snapshots(
                       entity_id,scope,project_id,version,content,content_sha256,source_checkpoint_id
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    snapshot_id, scope, None if project_id is None else UUID(project_id), version,
                    content, digest, None if source_checkpoint_id is None else UUID(source_checkpoint_id),
                ),
            )
            if project_id:
                self.repository._insert_edge(
                    connection, UUID(project_id), "contains", snapshot_id,
                    {"member": "studio_skill_snapshot"},
                )
            if source_checkpoint_id:
                self.repository._insert_edge(
                    connection, snapshot_id, "derived_from", UUID(source_checkpoint_id),
                    {"input": "studio_edit_checkpoint"},
                )
            if previous:
                self.repository._insert_edge(
                    connection, snapshot_id, "supersedes", previous[0], {"scope": scope},
                )
        return self.latest_skill(scope, project_id)

    def latest_skill(self, scope: str, project_id: str | None = None) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,scope,project_id,version,content,content_sha256,
                          source_checkpoint_id,created_at FROM studio_skill_snapshots
                    WHERE scope=%s AND project_id IS NOT DISTINCT FROM %s
                    ORDER BY version DESC LIMIT 1""",
                (scope, None if project_id is None else UUID(project_id)),
            ).fetchone()
        if row is None:
            return self._append_skill(
                scope=scope, project_id=project_id,
                content=_skill_document(
                    "studio-runtime-global" if scope == GLOBAL_SKILL_SCOPE else "studio-runtime-project",
                    "Global Studio skill" if scope == GLOBAL_SKILL_SCOPE else "Project Studio skill", [],
                ), source_checkpoint_id=None,
            )
        return self._skill_row(row)

    def ensure_project_skill(self, project_id: str) -> dict[str, Any]:
        self.project(project_id)
        return self.latest_skill(PROJECT_SKILL_SCOPE, project_id)

    def ensure_global_skill(self) -> dict[str, Any]:
        return self.latest_skill(GLOBAL_SKILL_SCOPE)

    def record_generation(
        self, *, creative_id: str, stage: str, status: str,
        provenance: Mapping[str, Any] | None = None, error: Exception | None = None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            attempt = int(connection.execute(
                "SELECT COALESCE(max(attempt),0)+1 FROM studio_generation_runs WHERE workspace_id=%s",
                (UUID(creative_id),),
            ).fetchone()[0])
            run_id = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_generation_run',%s)",
                (run_id, Jsonb({"stage": stage, "attempt": attempt})),
            )
            connection.execute(
                """INSERT INTO studio_generation_runs(
                       entity_id,workspace_id,attempt,stage,status,provenance,error_type,error_message
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    run_id, UUID(creative_id), attempt, stage, status, Jsonb(dict(provenance or {})),
                    None if error is None else type(error).__name__,
                    None if error is None else str(error)[:1000],
                ),
            )
            self.repository._insert_edge(
                connection, UUID(creative_id), "contains", run_id,
                {"member": "studio_generation_run", "stage": stage},
            )
        return {"generation_run_id": str(run_id), "attempt": attempt, "stage": stage, "status": status}

    def record_checkpoint(self, value: Mapping[str, Any]) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        checkpoint_id = UUID(str(value["checkpoint_id"]))
        with self.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"studio-checkpoint:{value['creative_id']}:{value['before_state_sha256']}:{value['after_state_sha256']}:{value['kind']}",),
            )
            existing = connection.execute(
                """SELECT entity_id FROM studio_edit_checkpoints
                    WHERE workspace_id=%s AND before_state_sha256=%s
                      AND after_state_sha256=%s AND checkpoint_kind=%s""",
                (
                    UUID(str(value["creative_id"])), value["before_state_sha256"],
                    value["after_state_sha256"], value["kind"],
                ),
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_edit_checkpoint',%s)",
                    (checkpoint_id, Jsonb({"kind": value["kind"]})),
                )
                connection.execute(
                    """INSERT INTO studio_edit_checkpoints(
                           entity_id,workspace_id,project_id,checkpoint_kind,before_state_sha256,
                           after_state_sha256,changed_paths,before_snapshot,after_snapshot,version
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        checkpoint_id, UUID(str(value["creative_id"])), UUID(str(value["project_id"])),
                        value["kind"], value["before_state_sha256"], value["after_state_sha256"],
                        Jsonb(value["changed_paths"]), Jsonb(value["before_snapshot"]),
                        Jsonb(value["after_snapshot"]), value.get("version"),
                    ),
                )
                self.repository._insert_edge(
                    connection, UUID(str(value["creative_id"])), "contains", checkpoint_id,
                    {"member": "studio_edit_checkpoint"},
                )
            else:
                checkpoint_id = existing[0]
        return self.get_checkpoint(str(checkpoint_id))

    def record_learning_result(
        self, checkpoint_id: str, *, status: str, edit_summary: str | None,
        project_lesson: str | None, project_skill_snapshot_id: str | None,
        provider: Mapping[str, Any] | None, error: Exception | None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        if status not in {"completed", "failed"}:
            raise ValueError("Studio learning result status is invalid")
        checkpoint_uuid = UUID(checkpoint_id)
        with self.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"studio-learning:{checkpoint_id}",),
            )
            existing_completed = connection.execute(
                """SELECT entity_id FROM studio_learning_runs
                    WHERE checkpoint_id=%s AND status='completed'""",
                (checkpoint_uuid,),
            ).fetchone()
            if existing_completed is not None:
                return self.get_checkpoint(checkpoint_id)
            attempt = int(connection.execute(
                "SELECT COALESCE(max(attempt),0)+1 FROM studio_learning_runs WHERE checkpoint_id=%s",
                (checkpoint_uuid,),
            ).fetchone()[0])
            run_id = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_learning_run',%s)",
                (run_id, Jsonb({"status": status, "attempt": attempt})),
            )
            connection.execute(
                """INSERT INTO studio_learning_runs(
                       entity_id,checkpoint_id,attempt,status,edit_summary,project_lesson,
                       project_skill_snapshot_id,provider,error_type,error_message
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    run_id, checkpoint_uuid, attempt, status, edit_summary, project_lesson,
                    None if project_skill_snapshot_id is None else UUID(project_skill_snapshot_id),
                    Jsonb(dict(provider or {})), None if error is None else type(error).__name__,
                    None if error is None else str(error)[:1000],
                ),
            )
            self.repository._insert_edge(
                connection, checkpoint_uuid, "contains", run_id,
                {"member": "studio_learning_run", "attempt": attempt},
            )
        return self.get_checkpoint(checkpoint_id)

    @staticmethod
    def _checkpoint_row(row: Any) -> dict[str, Any]:
        return {
            "checkpoint_id": str(row[0]), "creative_id": str(row[1]),
            "project_id": str(row[2]), "kind": row[3],
            "before_state_sha256": row[4], "after_state_sha256": row[5],
            "changed_paths": list(row[6] or []),
            "before_snapshot": dict(row[7] or {}), "after_snapshot": dict(row[8] or {}),
            "version": row[9], "created_at": row[10].isoformat(),
            "learning_run_id": None if row[11] is None else str(row[11]),
            "learning_attempt": row[12],
            "status": "completed" if row[13] == "completed" else "queued",
            "edit_summary": row[14], "project_lesson": row[15],
            "project_skill_snapshot_id": None if row[16] is None else str(row[16]),
            "provider": dict(row[17] or {}), "error_type": row[18],
            "error_message": row[19],
        }

    @staticmethod
    def _checkpoint_select() -> str:
        return """SELECT checkpoint.entity_id,checkpoint.workspace_id,checkpoint.project_id,
                         checkpoint.checkpoint_kind,checkpoint.before_state_sha256,
                         checkpoint.after_state_sha256,checkpoint.changed_paths,
                         checkpoint.before_snapshot,checkpoint.after_snapshot,
                         checkpoint.version,checkpoint.created_at,
                         learning.entity_id,learning.attempt,learning.status,
                         learning.edit_summary,learning.project_lesson,
                         learning.project_skill_snapshot_id,learning.provider,
                         learning.error_type,learning.error_message
                    FROM studio_edit_checkpoints checkpoint
                    LEFT JOIN LATERAL (
                        SELECT * FROM studio_learning_runs candidate
                         WHERE candidate.checkpoint_id=checkpoint.entity_id
                         ORDER BY candidate.attempt DESC LIMIT 1
                    ) learning ON true"""

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._checkpoint_select() + " WHERE checkpoint.entity_id=%s",
                (UUID(checkpoint_id),),
            ).fetchone()
        if row is None:
            raise KeyError(checkpoint_id)
        return self._checkpoint_row(row)

    def queued_checkpoints(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                self._checkpoint_select()
                + " WHERE NOT EXISTS (SELECT 1 FROM studio_learning_runs completed WHERE completed.checkpoint_id=checkpoint.entity_id AND completed.status='completed') ORDER BY checkpoint.created_at",
            ).fetchall()
        return [self._checkpoint_row(row) for row in rows]

    def create_project_skill(self, *, project_id: str, lesson: str, checkpoint_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,scope,project_id,version,content,content_sha256,
                          source_checkpoint_id,created_at FROM studio_skill_snapshots
                    WHERE scope='project' AND project_id=%s AND source_checkpoint_id=%s""",
                (UUID(project_id), UUID(checkpoint_id)),
            ).fetchone()
        if row is not None:
            return self._skill_row(row)
        previous = self.latest_skill(PROJECT_SKILL_SCOPE, project_id)
        return self._append_skill(
            scope=PROJECT_SKILL_SCOPE, project_id=project_id,
            content=_append_lesson(previous["content"], lesson),
            source_checkpoint_id=checkpoint_id,
        )

    def create_proposal(
        self, *, checkpoint_id: str, project_skill_snapshot_id: str, global_rule: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            existing = connection.execute(
                """SELECT entity_id,project_skill_snapshot_id,global_rule,global_rule_sha256
                     FROM studio_learning_proposals WHERE checkpoint_id=%s""",
                (UUID(checkpoint_id),),
            ).fetchone()
        if existing is not None:
            return {
                "proposal_id": str(existing[0]), "checkpoint_id": checkpoint_id,
                "project_skill_snapshot_id": str(existing[1]),
                "global_rule": existing[2], "global_rule_sha256": existing[3],
                "decision": "pending",
            }
        proposal_id = UUID(new_uuid7())
        digest = hashlib.sha256(global_rule.encode()).hexdigest()
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_learning_proposal',%s)",
                (proposal_id, Jsonb({"schema_version": 1})),
            )
            connection.execute(
                """INSERT INTO studio_learning_proposals(
                       entity_id,checkpoint_id,project_skill_snapshot_id,global_rule,global_rule_sha256
                   ) VALUES(%s,%s,%s,%s,%s)""",
                (proposal_id, UUID(checkpoint_id), UUID(project_skill_snapshot_id), global_rule, digest),
            )
            self.repository._insert_edge(
                connection, UUID(checkpoint_id), "contains", proposal_id,
                {"member": "studio_learning_proposal"},
            )
        return {
            "proposal_id": str(proposal_id), "checkpoint_id": checkpoint_id,
            "project_skill_snapshot_id": project_skill_snapshot_id,
            "global_rule": global_rule, "global_rule_sha256": digest, "decision": "pending",
        }

    def decide_proposal(self, proposal_id: str, decision: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        if decision not in {"global", "project_only"}:
            raise ValueError("learning decision must be global or project_only")
        with self.connection() as connection:
            row = connection.execute(
                """SELECT proposal.checkpoint_id,proposal.project_skill_snapshot_id,
                          proposal.global_rule,proposal.global_rule_sha256,
                          decision.decision,decision.global_skill_snapshot_id
                     FROM studio_learning_proposals proposal
                     LEFT JOIN studio_learning_decisions decision ON decision.proposal_id=proposal.entity_id
                    WHERE proposal.entity_id=%s""",
                (UUID(proposal_id),),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if row[4] is not None:
            if row[4] != decision:
                raise RuntimeError("learning proposal already has a different decision")
            return {"proposal_id": proposal_id, "decision": row[4], "global_skill_snapshot_id": None if row[5] is None else str(row[5])}
        global_snapshot = None
        if decision == "global":
            previous = self.latest_skill(GLOBAL_SKILL_SCOPE)
            global_snapshot = self._append_skill(
                scope=GLOBAL_SKILL_SCOPE, project_id=None,
                content=_append_lesson(previous["content"], row[2]),
                source_checkpoint_id=str(row[0]),
            )
        decision_id = UUID(new_uuid7())
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_learning_decision',%s)",
                (decision_id, Jsonb({"decision": decision})),
            )
            connection.execute(
                """INSERT INTO studio_learning_decisions(
                       entity_id,proposal_id,decision,global_skill_snapshot_id
                   ) VALUES(%s,%s,%s,%s)""",
                (
                    decision_id, UUID(proposal_id), decision,
                    None if global_snapshot is None else UUID(global_snapshot["skill_snapshot_id"]),
                ),
            )
            self.repository._insert_edge(
                connection, UUID(proposal_id), "contains", decision_id,
                {"member": "studio_learning_decision"},
            )
            if global_snapshot is not None:
                self.repository._insert_edge(
                    connection, UUID(global_snapshot["skill_snapshot_id"]), "derived_from",
                    UUID(proposal_id), {"input": "accepted_global_proposal"},
                )
        return {
            "proposal_id": proposal_id, "decision_id": str(decision_id), "decision": decision,
            "global_skill_snapshot_id": None if global_snapshot is None else global_snapshot["skill_snapshot_id"],
        }

    def proposal_checkpoint(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT checkpoint.entity_id,checkpoint.workspace_id,checkpoint.project_id
                     FROM studio_learning_proposals proposal
                     JOIN studio_edit_checkpoints checkpoint ON checkpoint.entity_id=proposal.checkpoint_id
                    WHERE proposal.entity_id=%s""",
                (UUID(proposal_id),),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return {
            "checkpoint_id": str(row[0]), "creative_id": str(row[1]),
            "project_id": str(row[2]),
        }

    def recover_interrupted(self) -> list[str]:
        with self.connection() as connection:
            rows = connection.execute(
                """UPDATE universal_studio_workspaces SET
                          status=CASE WHEN status='composing' THEN 'queued' ELSE status END,
                          generation=generation || jsonb_build_object(
                              'recovered_after_restart',true,'recovered_from_stage',status
                          ),
                          updated_at=clock_timestamp()
                    WHERE status IN ('queued','composing','generating_image')
                RETURNING entity_id"""
            ).fetchall()
        return [str(row[0]) for row in rows]
