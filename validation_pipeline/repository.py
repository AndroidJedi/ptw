"""PostgreSQL authority for Projects, Product Briefs, approved media, and Result renders."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7

from .domain import infer_language


def _sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _project_name(value: str) -> str:
    compact = " ".join(value.split())
    return compact[:120] or "Untitled Project"


class ValidationRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg

        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                yield connection

    @staticmethod
    def _project_select() -> str:
        return """SELECT project.entity_id,project.request_id,project.owner_idea_source_id,
                         project.name,project.name_source,project.requested_by,
                         project.result_creation_enabled,project.created_at,project.updated_at,
                         (SELECT brief.entity_id FROM product_briefs brief
                           WHERE brief.project_id=project.entity_id ORDER BY brief.created_at DESC LIMIT 1),
                         (SELECT brief.status FROM product_briefs brief
                           WHERE brief.project_id=project.entity_id ORDER BY brief.created_at DESC LIMIT 1),
                         (SELECT count(*) FROM product_briefs brief WHERE brief.project_id=project.entity_id),
                         (SELECT count(*) FROM content_generation_runs run WHERE run.project_id=project.entity_id)
                    FROM validation_projects project"""

    @staticmethod
    def _project_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "project_id": str(row[0]), "request_id": str(row[1]),
            "owner_idea_source_id": str(row[2]), "name": row[3], "name_source": row[4],
            "requested_by": row[5], "result_creation_enabled": bool(row[6]),
            "created_at": row[7].isoformat(), "updated_at": row[8].isoformat(),
            "latest_brief_id": None if row[9] is None else str(row[9]),
            "latest_brief_status": row[10], "brief_count": int(row[11]),
            "result_run_count": int(row[12]),
        }

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._project_select() + " WHERE project.entity_id=%s", (UUID(project_id),)
            ).fetchone()
        if row is None:
            raise KeyError(project_id)
        return self._project_row(row)

    def list_projects(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                self._project_select() + " ORDER BY project.updated_at DESC LIMIT %s",
                (min(100, max(1, limit)),),
            ).fetchall()
        return [self._project_row(row) for row in rows]

    def rename_project(self, project_id: str, *, name: str, requested_by: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        normalized = _project_name(name)
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE validation_projects SET name=%s,name_source='owner',updated_at=clock_timestamp()
                     WHERE entity_id=%s""",
                (normalized, UUID(project_id)),
            ).rowcount
            if changed != 1:
                raise KeyError(project_id)
            connection.execute(
                """INSERT INTO commander_audit_events(id,actor,action,target_id,details)
                   VALUES(%s,%s,'project.rename',%s,%s)""",
                (UUID(new_uuid7()), requested_by, UUID(project_id), Jsonb({"name": normalized})),
            )
        return self.get_project(project_id)

    @staticmethod
    def _brief_select() -> str:
        return """SELECT brief.entity_id,brief.project_id,project.name,brief.request_id,
                         brief.owner_idea_source_id,source.content,brief.base_brief_id,brief.feedback_id,
                         brief.status,brief.document,brief.document_sha256,brief.quality_gates,
                         brief.failure_count,brief.error_code,brief.error_message,brief.requested_by,
                         brief.created_at,brief.updated_at,brief.completed_at,
                         EXISTS(SELECT 1 FROM product_brief_approvals approval
                                 WHERE approval.brief_id=brief.entity_id)
                    FROM product_briefs brief
                    JOIN validation_projects project ON project.entity_id=brief.project_id
                    JOIN commander_sources source ON source.entity_id=brief.owner_idea_source_id"""

    @staticmethod
    def _brief_row(row: Sequence[Any]) -> dict[str, Any]:
        document = None if row[9] is None else dict(row[9])
        return {
            "brief_id": str(row[0]), "project_id": str(row[1]), "project_name": row[2],
            "request_id": str(row[3]), "owner_idea_source_id": str(row[4]), "raw_idea": row[5],
            "base_brief_id": None if row[6] is None else str(row[6]),
            "feedback_id": None if row[7] is None else str(row[7]), "status": row[8],
            "document": document, "document_sha256": row[10],
            "quality_gates": None if row[11] is None else dict(row[11]),
            "failure_count": int(row[12]), "error_code": row[13], "error_message": row[14],
            "requested_by": row[15], "created_at": row[16].isoformat(),
            "updated_at": row[17].isoformat(),
            "completed_at": None if row[18] is None else row[18].isoformat(),
            "approved": bool(row[19]),
            **({} if document is None else document),
        }

    def create_brief(
        self, *, request_id: str, raw_idea: str, required_language: str, requested_by: str,
        reserve_operation: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        request_uuid = UUID(request_id)
        idea = raw_idea.strip()
        if not 1 <= len(idea) <= 10_000:
            raise ValueError("raw idea must contain 1-10000 characters")
        if required_language not in {"uk", "en"}:
            raise ValueError("required language must be uk or en")
        with self.connection() as connection:
            existing = connection.execute(
                self._brief_select() + " WHERE brief.request_id=%s", (request_uuid,)
            ).fetchone()
            if existing is not None:
                value = self._brief_row(existing)
                source_row = connection.execute(
                    "SELECT metadata FROM commander_sources WHERE entity_id=%s",
                    (UUID(value["owner_idea_source_id"]),),
                ).fetchone()
                metadata = {} if source_row is None else dict(source_row[0] or {})
                existing_language = str(
                    metadata.get("required_language")
                    or (value.get("document") or {}).get("language")
                    or infer_language(value["raw_idea"])
                )
                if value["raw_idea"] != idea or existing_language != required_language:
                    raise ValueError("request_id was already used with different Product Brief input")
                if reserve_operation and value["status"] == "queued":
                    self._acquire_operation(connection, "product_brief", value["brief_id"])
                return value, False
            source_id, project_id, brief_id = (UUID(new_uuid7()) for _ in range(3))
            digest = hashlib.sha256(idea.encode()).hexdigest()
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'source',%s)",
                (source_id, Jsonb({"source_type": "owner_idea"})),
            )
            connection.execute(
                """INSERT INTO commander_sources(
                       entity_id,source_type,title,provider,external_id,content,content_sha256,metadata
                   ) VALUES(%s,'owner_idea','Owner idea','owner',%s,%s,%s,%s)""",
                (
                    source_id, request_uuid.hex, idea, digest,
                    Jsonb({"required_language": required_language}),
                ),
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'validation_project',%s)",
                (project_id, Jsonb({"schema_version": 1})),
            )
            connection.execute(
                """INSERT INTO validation_projects(
                       entity_id,request_id,owner_idea_source_id,name,name_source,requested_by
                   ) VALUES(%s,%s,%s,%s,'raw_idea',%s)""",
                (project_id, request_uuid, source_id, _project_name(idea), requested_by),
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'product_brief',%s)",
                (brief_id, Jsonb({"schema_version": 1})),
            )
            connection.execute(
                """INSERT INTO product_briefs(
                       entity_id,project_id,request_id,owner_idea_source_id,status,requested_by
                   ) VALUES(%s,%s,%s,%s,'queued',%s)""",
                (brief_id, project_id, request_uuid, source_id, requested_by),
            )
            for source, relation, target, attributes in (
                (project_id, "derived_from", source_id, {"input": "owner_idea"}),
                (project_id, "contains", brief_id, {"member": "product_brief"}),
                (brief_id, "derived_from", source_id, {"input": "owner_idea"}),
            ):
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
            if reserve_operation:
                self._acquire_operation(connection, "product_brief", str(brief_id))
        return self.get_brief(str(brief_id)), True

    def create_revision(
        self, base_brief_id: str, *, request_id: str, instruction: str, requested_by: str,
        reserve_operation: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        request_uuid = UUID(request_id)
        correction = instruction.strip()
        if not 1 <= len(correction) <= 2000:
            raise ValueError("correction must contain 1-2000 characters")
        base = self.get_brief(base_brief_id)
        if base["status"] != "completed":
            raise ValueError("only a completed Product Brief can be corrected")
        with self.connection() as connection:
            existing = connection.execute(
                self._brief_select() + " WHERE brief.request_id=%s", (request_uuid,)
            ).fetchone()
            if existing is not None:
                value = self._brief_row(existing)
                if value["base_brief_id"] != base_brief_id:
                    raise ValueError("request_id was already used for another Product Brief correction")
                if reserve_operation and value["status"] == "queued":
                    self._acquire_operation(connection, "product_brief", value["brief_id"])
                return value, False
            feedback_id, weight_id, brief_id = (UUID(new_uuid7()) for _ in range(3))
            for entity_id, kind, attributes in (
                (feedback_id, "human_feedback", {"domain": "product_brief"}),
                (weight_id, "weight_update", {"component": "product_brief", "delta": 0}),
                (brief_id, "product_brief", {"schema_version": 1}),
            ):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                    (entity_id, kind, Jsonb(attributes)),
                )
            connection.execute(
                """INSERT INTO commander_human_feedback(
                       entity_id,target_id,domain,section_id,instruction,actor
                   ) VALUES(%s,%s,'product_brief','product_brief',%s,%s)""",
                (feedback_id, UUID(base_brief_id), correction, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,'product_brief',0,'Owner correction requires immutable replacement')""",
                (weight_id, feedback_id),
            )
            connection.execute(
                """INSERT INTO product_briefs(
                       entity_id,project_id,request_id,owner_idea_source_id,base_brief_id,
                       feedback_id,status,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,'queued',%s)""",
                (
                    brief_id, UUID(base["project_id"]), request_uuid,
                    UUID(base["owner_idea_source_id"]), UUID(base_brief_id), feedback_id, requested_by,
                ),
            )
            for source, relation, target, attributes in (
                (feedback_id, "evaluates", UUID(base_brief_id), {}),
                (feedback_id, "contains", weight_id, {}),
                (weight_id, "adjusts", feedback_id, {"delta": 0}),
                (brief_id, "supersedes", UUID(base_brief_id), {}),
                (brief_id, "derived_from", feedback_id, {"input": "owner_correction"}),
                (UUID(base["project_id"]), "contains", brief_id, {"member": "product_brief"}),
            ):
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
            if reserve_operation:
                self._acquire_operation(connection, "product_brief", str(brief_id))
        return self.get_brief(str(brief_id)), True

    def get_brief(self, brief_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._brief_select() + " WHERE brief.entity_id=%s", (UUID(brief_id),)
            ).fetchone()
        if row is None:
            raise KeyError(brief_id)
        return self._brief_row(row)

    def list_briefs(self, limit: int = 100, *, project_id: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if project_id is not None:
            where = " WHERE brief.project_id=%s"
            params.append(UUID(project_id))
        params.append(min(100, max(1, limit)))
        with self.connection() as connection:
            rows = connection.execute(
                self._brief_select() + where + " ORDER BY brief.created_at DESC LIMIT %s", params
            ).fetchall()
        return [self._brief_row(row) for row in rows]

    def source(self, brief_id: str) -> dict[str, Any]:
        brief = self.get_brief(brief_id)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT entity_id,content,content_sha256,metadata FROM commander_sources WHERE entity_id=%s",
                (UUID(brief["owner_idea_source_id"]),),
            ).fetchone()
        if row is None:
            raise KeyError(brief_id)
        metadata = dict(row[3] or {})
        required_language = metadata.get("required_language")
        return {
            "source_id": str(row[0]), "content": row[1], "content_sha256": row[2],
            "required_language": required_language if required_language in {"uk", "en"} else None,
        }

    def feedback(self, feedback_id: str) -> dict[str, str]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT section_id,instruction FROM commander_human_feedback WHERE entity_id=%s",
                (UUID(feedback_id),),
            ).fetchone()
        if row is None:
            raise KeyError(feedback_id)
        return {"section_id": row[0], "instruction": row[1]}

    def approve_brief(self, brief_id: str, approved_by: str) -> tuple[dict[str, Any], bool]:
        brief = self.get_brief(brief_id)
        if brief["status"] != "completed":
            raise ValueError("only a completed Product Brief can be approved")
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT 1 FROM product_brief_approvals WHERE brief_id=%s", (UUID(brief_id),)
            ).fetchone()
            if existing is not None:
                return self.get_brief(brief_id), False
            connection.execute(
                "INSERT INTO product_brief_approvals(id,brief_id,approved_by) VALUES(%s,%s,%s)",
                (UUID(new_uuid7()), UUID(brief_id), approved_by),
            )
            connection.execute(
                """UPDATE validation_projects SET result_creation_enabled=true,
                          updated_at=clock_timestamp() WHERE entity_id=%s""",
                (UUID(brief["project_id"]),),
            )
        return self.get_brief(brief_id), True

    @staticmethod
    def _acquire_operation(connection: Any, kind: str, operation_id: str) -> None:
        if kind not in {"product_brief", "content_run"}:
            raise ValueError("unsupported operation kind")
        changed = connection.execute(
            """UPDATE commander_operation_guard
                  SET operation_kind=%s,operation_id=%s,acquired_at=clock_timestamp()
                WHERE singleton AND operation_id IS NULL""",
            (kind, UUID(operation_id)),
        ).rowcount
        if changed != 1:
            raise RuntimeError("another generation operation is active")

    def acquire_operation(self, kind: str, operation_id: str) -> bool:
        with self.connection() as connection:
            self._acquire_operation(connection, kind, operation_id)
        return True

    def release_operation(self, operation_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                    WHERE singleton AND operation_id=%s""",
                (UUID(operation_id),),
            )

    def start_attempt(self, target_id: str, *, stage: str) -> tuple[str, int]:
        if stage != "product_brief":
            raise ValueError("unsupported Product Brief attempt stage")
        target_uuid = UUID(target_id)
        with self.connection() as connection:
            number = int(connection.execute(
                "SELECT COALESCE(max(attempt_number),0)+1 FROM validation_generation_attempts WHERE target_id=%s",
                (target_uuid,),
            ).fetchone()[0])
            attempt_id = UUID(new_uuid7())
            connection.execute(
                """INSERT INTO validation_generation_attempts(id,target_id,stage,attempt_number,status)
                   VALUES(%s,%s,%s,%s,'started')""",
                (attempt_id, target_uuid, stage, number),
            )
            connection.execute(
                """UPDATE product_briefs SET status='generating',error_code=NULL,error_message=NULL,
                          updated_at=clock_timestamp() WHERE entity_id=%s AND status IN ('queued','failed')""",
                (target_uuid,),
            )
        return str(attempt_id), number

    def create_invocation(
        self, *, target_id: str, attempt_id: str, mode: str,
        idempotency_key: str, request: Mapping[str, Any],
    ) -> dict[str, str]:
        from psycopg.types.json import Jsonb

        if mode not in {"product_brief", "product_brief_revision"}:
            raise ValueError("unsupported Product Brief provider mode")
        invocation_id = UUID(new_uuid7())
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO validation_provider_invocations(
                       id,target_id,attempt_id,provider,mode,idempotency_key,request_sha256,status,invocation
                   ) VALUES(%s,%s,%s,'structured_bridge',%s,%s,%s,'submitted',%s)""",
                (
                    invocation_id, UUID(target_id), UUID(attempt_id), mode,
                    idempotency_key, _sha(request), Jsonb({}),
                ),
            )
        return {"id": str(invocation_id)}

    def complete_invocation(
        self, invocation_id: str, response: Mapping[str, Any], provenance: Mapping[str, Any]
    ) -> None:
        from psycopg.types.json import Jsonb

        with self.connection() as connection:
            connection.execute(
                """UPDATE validation_provider_invocations SET status='completed',response_sha256=%s,
                          invocation=%s,completed_at=clock_timestamp() WHERE id=%s AND status='submitted'""",
                (_sha(response), Jsonb(dict(provenance)), UUID(invocation_id)),
            )

    def fail_invocation(
        self, invocation_id: str, error: Exception,
        provenance: Mapping[str, Any] | None = None,
    ) -> None:
        from psycopg.types.json import Jsonb

        with self.connection() as connection:
            connection.execute(
                """UPDATE validation_provider_invocations SET status='failed',invocation=%s,
                          completed_at=clock_timestamp() WHERE id=%s AND status='submitted'""",
                (Jsonb({**dict(provenance or {}), "error": type(error).__name__}), UUID(invocation_id)),
            )

    def finish_brief(
        self, brief_id: str, attempt_id: str, document: Mapping[str, Any],
        digest: str, quality: Mapping[str, Any],
    ) -> None:
        from psycopg.types.json import Jsonb

        with self.connection() as connection:
            connection.execute(
                """UPDATE product_briefs SET status='completed',document=%s,document_sha256=%s,
                          quality_gates=%s,error_code=NULL,error_message=NULL,
                          updated_at=clock_timestamp(),completed_at=clock_timestamp()
                    WHERE entity_id=%s AND status='generating' AND document IS NULL""",
                (Jsonb(dict(document)), digest, Jsonb(dict(quality)), UUID(brief_id)),
            )
            connection.execute(
                """UPDATE validation_generation_attempts SET status='completed',completed_at=clock_timestamp()
                    WHERE id=%s AND status='started'""",
                (UUID(attempt_id),),
            )
            connection.execute(
                """UPDATE validation_projects SET name=%s,name_source='product_brief',
                          updated_at=clock_timestamp()
                    WHERE entity_id=(SELECT project_id FROM product_briefs WHERE entity_id=%s)
                      AND name_source='raw_idea'""",
                (_project_name(str(document["product"])), UUID(brief_id)),
            )

    def fail_attempt(self, target_id: str, attempt_id: str, *, stage: str, error: Exception) -> None:
        if stage != "product_brief":
            raise ValueError("unsupported Product Brief failure stage")
        with self.connection() as connection:
            connection.execute(
                """UPDATE validation_generation_attempts SET status='failed',error_code=%s,
                          error_message=%s,completed_at=clock_timestamp()
                    WHERE id=%s AND status='started'""",
                (type(error).__name__, str(error)[:1000], UUID(attempt_id)),
            )
            connection.execute(
                """UPDATE product_briefs SET status='failed',failure_count=failure_count+1,
                          error_code=%s,error_message=%s,updated_at=clock_timestamp()
                    WHERE entity_id=%s AND status='generating'""",
                (type(error).__name__, str(error)[:1000], UUID(target_id)),
            )

    def queue_retry(self, target_id: str, *, stage: str) -> dict[str, Any]:
        if stage != "product_brief":
            raise ValueError("unsupported Product Brief retry stage")
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE product_briefs SET status='queued',error_code=NULL,error_message=NULL,
                          updated_at=clock_timestamp() WHERE entity_id=%s AND status='failed'""",
                (UUID(target_id),),
            ).rowcount
        if changed != 1:
            raise ValueError("only a failed Product Brief can be retried")
        return self.get_brief(target_id)

    @staticmethod
    def _asset_row(row: Sequence[Any], *, include_bytes: bool = False) -> dict[str, Any]:
        value = {
            "source_asset_id": str(row[0]), "project_id": str(row[1]), "origin": row[2],
            "approval_status": row[3], "title": row[4], "mime_type": row[5],
            "width": int(row[6]), "height": int(row[7]), "bytes_sha256": row[8],
            "source_uri": row[9], "provider": row[10], "external_id": row[11],
            "license": row[12], "attribution": row[13], "metadata": dict(row[14]),
            "created_by": row[15], "created_at": row[16].isoformat(),
            "asset_url": f"/api/v1/project-assets/{row[0]}/asset",
        }
        if include_bytes:
            value["bytes"] = bytes(row[17])
        return value

    def create_project_asset(
        self, project_id: str, *, title: str, data: bytes, mime_type: str, origin: str,
        provider: str, external_id: str | None, source_uri: str | None,
        license_name: str | None, attribution: str | None, metadata: Mapping[str, Any],
        requested_by: str, approval_status: str = "approved",
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import inspect_media

        if approval_status not in {"approved", "pending_review", "rejected"}:
            raise ValueError("unknown Project asset approval status")
        if origin not in {"owner_upload", "pexels", "canonical_brand", "ai_generated"}:
            raise ValueError("unknown Project asset origin")
        inspected = inspect_media(data, mime_type)
        if inspected["mime_type"] not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Project assets are static images only")
        digest = hashlib.sha256(data).hexdigest()
        stable_external_id = external_id or digest
        normalized_title = " ".join(title.split())[:200]
        if not normalized_title:
            raise ValueError("Project asset title is required")
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT entity_id FROM project_assets WHERE project_id=%s AND provider=%s AND external_id=%s",
                (UUID(project_id), provider, stable_external_id),
            ).fetchone()
            if existing is not None:
                return self.get_project_asset(str(existing[0]))
            if connection.execute(
                "SELECT 1 FROM validation_projects WHERE entity_id=%s", (UUID(project_id),)
            ).fetchone() is None:
                raise KeyError(project_id)
            entity_id = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'project_asset',%s)",
                (entity_id, Jsonb({"origin": origin, "mime_type": mime_type})),
            )
            connection.execute(
                """INSERT INTO project_assets(
                       entity_id,project_id,origin,approval_status,title,mime_type,width,height,
                       bytes,bytes_sha256,source_uri,provider,external_id,license,attribution,
                       metadata,created_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    entity_id, UUID(project_id), origin, approval_status, normalized_title,
                    inspected["mime_type"], inspected["width"], inspected["height"], data, digest,
                    source_uri, provider, stable_external_id, license_name, attribution,
                    Jsonb(dict(metadata)), requested_by,
                ),
            )
            connection.execute(
                """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                   VALUES(%s,%s,'contains',%s,%s)""",
                (UUID(new_uuid7()), UUID(project_id), entity_id, Jsonb({"member": "project_asset"})),
            )
        return self.get_project_asset(str(entity_id))

    def get_project_asset(self, asset_id: str, *, include_bytes: bool = False) -> dict[str, Any]:
        extra = ",bytes" if include_bytes else ""
        with self.connection() as connection:
            row = connection.execute(
                f"""SELECT entity_id,project_id,origin,approval_status,title,mime_type,width,height,
                            bytes_sha256,source_uri,provider,external_id,license,attribution,metadata,
                            created_by,created_at{extra} FROM project_assets WHERE entity_id=%s""",
                (UUID(asset_id),),
            ).fetchone()
        if row is None:
            raise KeyError(asset_id)
        return self._asset_row(row, include_bytes=include_bytes)

    def list_project_assets(self, project_id: str, *, approved_only: bool = False) -> list[dict[str, Any]]:
        where = " AND approval_status='approved'" if approved_only else ""
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id,project_id,origin,approval_status,title,mime_type,width,height,
                          bytes_sha256,source_uri,provider,external_id,license,attribution,metadata,
                          created_by,created_at FROM project_assets
                   WHERE project_id=%s""" + where + " ORDER BY created_at DESC LIMIT 100",
                (UUID(project_id),),
            ).fetchall()
        return [self._asset_row(row) for row in rows]

    def get_creative_media_asset(self, creative_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT entity_id FROM project_assets WHERE metadata->>'content_creative_id'=%s",
                (str(UUID(creative_id)),),
            ).fetchone()
        return None if row is None else self.get_project_asset(str(row[0]))

    def project_asset_bytes(self, asset_id: str) -> dict[str, Any]:
        item = self.get_project_asset(asset_id, include_bytes=True)
        return {"bytes": item["bytes"], "sha256": item["bytes_sha256"], "mime_type": item["mime_type"]}

    @staticmethod
    def _brand_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "brand_kit_id": str(row[0]), "project_id": str(row[1]),
            "parent_brand_kit_id": None if row[2] is None else str(row[2]),
            "document": dict(row[3]), "document_sha256": row[4],
            "created_by": row[5], "created_at": row[6].isoformat(),
        }

    def create_project_brand_kit(
        self, project_id: str, *, document: Mapping[str, Any],
        parent_brand_kit_id: str | None, requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import validate_brand_kit

        normalized = validate_brand_kit(document)
        parent = None if parent_brand_kit_id is None else UUID(parent_brand_kit_id)
        logo = None if normalized["logo_source_asset_id"] is None else UUID(normalized["logo_source_asset_id"])
        entity_id = UUID(new_uuid7())
        with self.connection() as connection:
            if connection.execute(
                "SELECT 1 FROM validation_projects WHERE entity_id=%s", (UUID(project_id),)
            ).fetchone() is None:
                raise KeyError(project_id)
            if parent is not None and connection.execute(
                "SELECT 1 FROM project_brand_kits WHERE entity_id=%s AND project_id=%s",
                (parent, UUID(project_id)),
            ).fetchone() is None:
                raise ValueError("parent brand kit must belong to the Project")
            if logo is not None and connection.execute(
                """SELECT 1 FROM project_assets WHERE entity_id=%s AND project_id=%s
                     AND approval_status='approved'""",
                (logo, UUID(project_id)),
            ).fetchone() is None:
                raise ValueError("brand logo must be an approved Project asset")
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'project_brand_kit',%s)",
                (entity_id, Jsonb({"schema_version": 1})),
            )
            connection.execute(
                """INSERT INTO project_brand_kits(
                       entity_id,project_id,parent_brand_kit_id,logo_asset_id,document,
                       document_sha256,created_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    entity_id, UUID(project_id), parent, logo, Jsonb(normalized),
                    _sha(normalized), requested_by,
                ),
            )
            for source, relation, target, attrs in (
                (UUID(project_id), "contains", entity_id, {"member": "project_brand_kit"}),
                *((entity_id, "derived_from", logo, {"input": "logo_asset"}) for _ in [0] if logo),
                *((entity_id, "supersedes", parent, {}) for _ in [0] if parent),
            ):
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attrs)),
                )
        return self.get_project_brand_kit(str(entity_id))

    def get_project_brand_kit(self, brand_kit_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,project_id,parent_brand_kit_id,document,document_sha256,
                          created_by,created_at FROM project_brand_kits WHERE entity_id=%s""",
                (UUID(brand_kit_id),),
            ).fetchone()
        if row is None:
            raise KeyError(brand_kit_id)
        return self._brand_row(row)

    def list_project_brand_kits(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id,project_id,parent_brand_kit_id,document,document_sha256,
                          created_by,created_at FROM project_brand_kits
                   WHERE project_id=%s ORDER BY created_at DESC""",
                (UUID(project_id),),
            ).fetchall()
        return [self._brand_row(row) for row in rows]

    def ensure_natal_brand_kit(
        self, project_id: str, *, logo_data: bytes, requested_by: str,
    ) -> dict[str, Any]:
        """Provision the immutable Natal identity without owner setup fields."""
        from .natal_brand import natal_brand_document

        logo = self.create_project_asset(
            project_id, title="Natal canonical logo", data=logo_data, mime_type="image/png",
            origin="canonical_brand", provider="natal", external_id="logo-natal-v1",
            source_uri="natal/assets/logo-natal.png", license_name="PTW canonical brand asset",
            attribution="Natal canonical logo", metadata={
                "canonical_path": "natal/assets/logo-natal.png",
                "immutable_identity": True,
            }, requested_by=requested_by,
        )
        document = natal_brand_document(logo["source_asset_id"])
        kits = self.list_project_brand_kits(project_id)
        if kits and kits[0]["document"] == document:
            return kits[0]
        return self.create_project_brand_kit(
            project_id,
            parent_brand_kit_id=kits[0]["brand_kit_id"] if kits else None,
            requested_by=requested_by,
            document=document,
        )

    def create_recipe(
        self, project_id: str, *, creative_id: str, brief_id: str, brand_kit_id: str,
        document: Mapping[str, Any], requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import validate_recipe

        project_uuid, creative_uuid = UUID(project_id), UUID(creative_id)
        brief_uuid, kit_uuid = UUID(brief_id), UUID(brand_kit_id)
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT entity_id FROM studio_recipes WHERE creative_id=%s", (creative_uuid,),
            ).fetchone()
            if existing is not None:
                recipe = self.get_recipe(str(existing[0]))
                if (
                    recipe["project_id"] != project_id
                    or recipe["brief_id"] != brief_id
                    or recipe["brand_kit_id"] != brand_kit_id
                ):
                    raise ValueError("creative recipe ownership cannot change")
                return recipe
            if connection.execute(
                "SELECT 1 FROM commander_entities WHERE id=%s AND kind='content_creative'",
                (creative_uuid,),
            ).fetchone() is None:
                raise ValueError("recipe creative UUID was not reserved by the server")
            row = connection.execute(
                """SELECT brief.document FROM product_briefs brief
                   JOIN product_brief_approvals approval ON approval.brief_id=brief.entity_id
                   WHERE brief.entity_id=%s AND brief.project_id=%s AND brief.status='completed'""",
                (brief_uuid, project_uuid),
            ).fetchone()
            if row is None:
                raise ValueError("recipes require an approved completed Brief in the Project")
            kit_row = connection.execute(
                "SELECT document FROM project_brand_kits WHERE entity_id=%s AND project_id=%s",
                (kit_uuid, project_uuid),
            ).fetchone()
            if kit_row is None:
                raise ValueError("brand kit must belong to the Project")
            contract = validate_recipe(
                document, project_id=project_id, brief_id=brief_id,
                brand_kit_id=brand_kit_id, brief=dict(row[0]), brand_document=dict(kit_row[0]),
            )
            if contract.value["schema_version"] != 2 or contract.value["duration_seconds"] is not None:
                raise ValueError("Result rendering accepts static StudioRecipeV2 only")
            parent = None if contract.value["parent_recipe_id"] is None else UUID(contract.value["parent_recipe_id"])
            creative_parent = connection.execute(
                "SELECT parent_creative_id FROM content_creatives WHERE entity_id=%s",
                (creative_uuid,),
            ).fetchone()
            expected_parent_creative = None if creative_parent is None else creative_parent[0]
            if parent is None:
                if expected_parent_creative is not None:
                    raise ValueError("an improved creative recipe must reference its base recipe")
            else:
                parent_row = connection.execute(
                    "SELECT creative_id FROM studio_recipes WHERE entity_id=%s AND project_id=%s",
                    (parent, project_uuid),
                ).fetchone()
                if parent_row is None:
                    raise ValueError("parent recipe must belong to the Project")
                if expected_parent_creative is None or parent_row[0] != expected_parent_creative:
                    raise ValueError("parent recipe must belong to the creative's direct base")
            for asset_id in contract.value["source_asset_ids"]:
                if connection.execute(
                    """SELECT 1 FROM project_assets WHERE entity_id=%s AND project_id=%s AND (
                           approval_status='approved' OR (
                             origin='ai_generated' AND approval_status='pending_review'
                             AND metadata->>'content_creative_id'=%s
                           )
                       )""",
                    (UUID(asset_id), project_uuid, str(creative_uuid)),
                ).fetchone() is None:
                    raise ValueError("every recipe asset must be approved or scoped to this Creative")
            entity_id = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_recipe',%s)",
                (entity_id, Jsonb({"schema_version": 2})),
            )
            connection.execute(
                """INSERT INTO studio_recipes(
                       entity_id,creative_id,project_id,brief_id,brand_kit_id,parent_recipe_id,
                       placement_tool_id,document,document_sha256,renderer_version,created_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    entity_id, creative_uuid, project_uuid, brief_uuid, kit_uuid, parent,
                    contract.value["placement_tool_id"], Jsonb(dict(contract.value)),
                    contract.digest, contract.value["renderer_version"], requested_by,
                ),
            )
            edges = [
                (project_uuid, "contains", entity_id, {"member": "studio_recipe"}),
                (entity_id, "derived_from", brief_uuid, {"input": "product_brief"}),
                (entity_id, "derived_from", kit_uuid, {"input": "brand_kit"}),
                *([] if parent is None else [
                    (entity_id, "derived_from", parent, {"input": "parent_recipe"}),
                ]),
                *[(entity_id, "derived_from", UUID(asset_id), {"input": "project_asset"})
                  for asset_id in contract.value["source_asset_ids"]],
            ]
            for source, relation, target, attrs in edges:
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attrs)),
                )
        return self.get_recipe(str(entity_id))

    def get_recipe(self, recipe_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,creative_id,project_id,brief_id,brand_kit_id,parent_recipe_id,
                          placement_tool_id,document,document_sha256,renderer_version,created_by,created_at
                   FROM studio_recipes WHERE entity_id=%s""",
                (UUID(recipe_id),),
            ).fetchone()
        if row is None:
            raise KeyError(recipe_id)
        return {
            "recipe_id": str(row[0]), "creative_id": str(row[1]), "project_id": str(row[2]),
            "brief_id": str(row[3]), "brand_kit_id": str(row[4]),
            "parent_recipe_id": None if row[5] is None else str(row[5]),
            "placement_tool_id": row[6], "document": dict(row[7]), "document_sha256": row[8],
            "renderer_version": row[9], "created_by": row[10], "created_at": row[11].isoformat(),
        }

    def get_creative_recipe(self, creative_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT entity_id FROM studio_recipes WHERE creative_id=%s", (UUID(creative_id),),
            ).fetchone()
        return None if row is None else self.get_recipe(str(row[0]))

    def get_recipe_render(self, recipe_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT entity_id FROM studio_renders WHERE recipe_id=%s ORDER BY created_at LIMIT 1",
                (UUID(recipe_id),),
            ).fetchone()
        return None if row is None else self.get_render(str(row[0]))

    def render_recipe(self, recipe_id: str, renderer: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import build_manifest

        existing = self.get_recipe_render(recipe_id)
        if existing is not None:
            return existing
        recipe = self.get_recipe(recipe_id)
        brand = self.get_project_brand_kit(recipe["brand_kit_id"])
        assets = {
            asset_id: self.get_project_asset(asset_id, include_bytes=True)
            for asset_id in recipe["document"]["source_asset_ids"]
        }
        attempt_id, render_id = UUID(new_uuid7()), UUID(new_uuid7())
        with self.connection() as connection:
            number = int(connection.execute(
                "SELECT COALESCE(max(attempt_number),0)+1 FROM studio_render_attempts WHERE recipe_id=%s",
                (UUID(recipe_id),),
            ).fetchone()[0])
            connection.execute(
                """INSERT INTO studio_render_attempts(id,recipe_id,attempt_number,status)
                   VALUES(%s,%s,%s,'started')""",
                (attempt_id, UUID(recipe_id), number),
            )
        try:
            rendered = renderer.render(
                recipe_id=recipe_id, recipe_digest=recipe["document_sha256"],
                recipe=recipe["document"], brand_kit=brand, assets=assets,
            )
            if rendered["mime_type"] != "image/jpeg":
                raise ValueError("Result renderer must return one JPEG")
            manifest = build_manifest(
                render_id=str(render_id), recipe_id=recipe_id,
                recipe_digest=recipe["document_sha256"], recipe=recipe["document"],
                brand_kit=brand, assets=assets, rendered=rendered,
            )
            with self.connection() as connection:
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_render',%s)",
                    (render_id, Jsonb({"mime_type": "image/jpeg"})),
                )
                connection.execute(
                    """INSERT INTO studio_renders(
                           entity_id,recipe_id,attempt_id,mime_type,width,height,bytes,bytes_sha256,
                           manifest,manifest_sha256,embedded_manifest,renderer_version
                       ) VALUES(%s,%s,%s,'image/jpeg',%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        render_id, UUID(recipe_id), attempt_id,
                        int(recipe["document"]["width"]), int(recipe["document"]["height"]),
                        rendered["bytes"],
                        manifest["output"]["bytes_sha256"], Jsonb(manifest), _sha(manifest),
                        rendered["embedded_manifest"], recipe["renderer_version"],
                    ),
                )
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,'contains',%s,%s)""",
                    (UUID(new_uuid7()), UUID(recipe_id), render_id, Jsonb({"artifact": "render"})),
                )
                connection.execute(
                    """UPDATE studio_render_attempts SET status='completed',completed_at=clock_timestamp()
                       WHERE id=%s""",
                    (attempt_id,),
                )
            return self.get_render(str(render_id))
        except Exception as error:
            with self.connection() as connection:
                connection.execute(
                    """UPDATE studio_render_attempts SET status='failed',error_code=%s,error_message=%s,
                              completed_at=clock_timestamp() WHERE id=%s AND status='started'""",
                    (type(error).__name__, str(error)[:1000], attempt_id),
                )
            raise

    def get_render(self, render_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,recipe_id,mime_type,width,height,bytes_sha256,manifest,
                          manifest_sha256,renderer_version,created_at
                   FROM studio_renders WHERE entity_id=%s""",
                (UUID(render_id),),
            ).fetchone()
        if row is None:
            raise KeyError(render_id)
        return {
            "render_id": str(row[0]), "recipe_id": str(row[1]), "mime_type": row[2],
            "width": int(row[3]), "height": int(row[4]), "bytes_sha256": row[5],
            "manifest": dict(row[6]), "manifest_sha256": row[7], "renderer_version": row[8],
            "created_at": row[9].isoformat(),
        }

    def render_asset(self, render_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT bytes,bytes_sha256,mime_type,width,height FROM studio_renders WHERE entity_id=%s",
                (UUID(render_id),),
            ).fetchone()
        if row is None:
            raise KeyError(render_id)
        return {
            "bytes": bytes(row[0]), "sha256": row[1], "mime_type": row[2],
            "width": int(row[3]), "height": int(row[4]),
        }

    # Temporary method aliases are intentionally absent. The only vocabulary is Project/Result.

    def recover_interrupted(self) -> dict[str, int]:
        with self.connection() as connection:
            briefs = connection.execute(
                """UPDATE product_briefs SET status='failed',failure_count=failure_count+1,
                          error_code='Interrupted',
                          error_message='service restarted before or during generation',
                          updated_at=clock_timestamp() WHERE status IN ('queued','generating')"""
            ).rowcount
            connection.execute(
                """UPDATE validation_generation_attempts SET status='failed',error_code='Interrupted',
                          error_message='service restarted during generation',completed_at=clock_timestamp()
                   WHERE status='started' AND stage='product_brief'"""
            )
            connection.execute(
                """UPDATE validation_provider_invocations SET status='failed',
                          invocation='{"error_code":"Interrupted"}'::jsonb,completed_at=clock_timestamp()
                   WHERE status='submitted'"""
            )
            content_attempts = connection.execute(
                """UPDATE validation_generation_attempts SET status='failed',error_code='Interrupted',
                          error_message='service restarted during Result generation',
                          completed_at=clock_timestamp()
                   WHERE status='started' AND stage IN (
                     'content_candidate_generation',
                     'content_non_human_graphic_generation'
                   )"""
            ).rowcount
            renders = connection.execute(
                """UPDATE studio_render_attempts SET status='failed',error_code='Interrupted',
                          error_message='service restarted during rendering',completed_at=clock_timestamp()
                   WHERE status='started'"""
            ).rowcount
            connection.execute(
                """UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton"""
            )
        return {"briefs": briefs, "renders": renders, "content_attempts": content_attempts}

    def activity(self) -> dict[str, Any]:
        with self.connection() as connection:
            guard = connection.execute(
                "SELECT operation_kind,operation_id,acquired_at FROM commander_operation_guard WHERE singleton"
            ).fetchone()
            counts = connection.execute(
                """SELECT (SELECT count(*) FROM validation_projects),
                          (SELECT count(*) FROM product_briefs),
                          (SELECT count(*) FROM product_brief_approvals),
                          (SELECT count(*) FROM project_assets),
                          (SELECT count(*) FROM content_generation_runs),
                          (SELECT count(*) FROM content_generation_runs WHERE status='approved')"""
            ).fetchone()
        return {
            "operation": None if guard is None or guard[1] is None else {
                "kind": guard[0], "id": str(guard[1]), "acquired_at": guard[2].isoformat(),
            },
            "projects": int(counts[0]), "briefs": int(counts[1]),
            "approved_briefs": int(counts[2]), "project_assets": int(counts[3]),
            "result_runs": int(counts[4]), "results": int(counts[5]),
        }
