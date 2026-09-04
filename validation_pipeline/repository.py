"""PostgreSQL authority for Projects and Product Briefs."""

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
                         project.created_at,project.updated_at,
                         (SELECT brief.entity_id FROM product_briefs brief
                           WHERE brief.project_id=project.entity_id ORDER BY brief.created_at DESC LIMIT 1),
                         (SELECT brief.status FROM product_briefs brief
                           WHERE brief.project_id=project.entity_id ORDER BY brief.created_at DESC LIMIT 1),
                         (SELECT count(*) FROM product_briefs brief WHERE brief.project_id=project.entity_id)
                    FROM validation_projects project"""

    @staticmethod
    def _project_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "project_id": str(row[0]), "request_id": str(row[1]),
            "owner_idea_source_id": str(row[2]), "name": row[3], "name_source": row[4],
            "requested_by": row[5], "created_at": row[6].isoformat(),
            "updated_at": row[7].isoformat(),
            "latest_brief_id": None if row[8] is None else str(row[8]),
            "latest_brief_status": row[9], "brief_count": int(row[10]),
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
            from .studio_creatives import _skill_document
            project_skill_id = UUID(new_uuid7())
            project_skill_content = _skill_document(
                "studio-runtime-project", "Project Studio skill", [],
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_skill_snapshot',%s)",
                (project_skill_id, Jsonb({"scope": "project", "version": 1})),
            )
            connection.execute(
                """INSERT INTO studio_skill_snapshots(
                       entity_id,scope,project_id,version,content,content_sha256
                   ) VALUES(%s,'project',%s,1,%s,%s)""",
                (
                    project_skill_id, project_id, project_skill_content,
                    hashlib.sha256(project_skill_content.encode()).hexdigest(),
                ),
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
                (project_id, "contains", project_skill_id, {"member": "studio_skill_snapshot"}),
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
        return self.get_brief(brief_id), True

    @staticmethod
    def _acquire_operation(connection: Any, kind: str, operation_id: str) -> None:
        if kind != "product_brief":
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
            connection.execute(
                """UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton"""
            )
        return {"briefs": briefs}

    def activity(self) -> dict[str, Any]:
        with self.connection() as connection:
            guard = connection.execute(
                "SELECT operation_kind,operation_id,acquired_at FROM commander_operation_guard WHERE singleton"
            ).fetchone()
            counts = connection.execute(
                """SELECT (SELECT count(*) FROM validation_projects),
                          (SELECT count(*) FROM product_briefs),
                          (SELECT count(*) FROM product_brief_approvals)"""
            ).fetchone()
        return {
            "operation": None if guard is None or guard[1] is None else {
                "kind": guard[0], "id": str(guard[1]), "acquired_at": guard[2].isoformat(),
            },
            "projects": int(counts[0]), "briefs": int(counts[1]),
            "approved_briefs": int(counts[2]),
        }
