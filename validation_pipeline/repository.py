"""PostgreSQL authority for immutable briefs, creatives, assets, and feedback."""

from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
import hashlib
import json
import zipfile
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7


def _sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _project_name(value: str) -> str:
    return " ".join(value.split())[:120]


class ValidationRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _project_select() -> str:
        return """SELECT project.entity_id,project.request_id,project.owner_idea_source_id,
                         project.name,project.name_source,project.requested_by,project.created_at,
                         project.updated_at,latest.entity_id,latest.status,
                         (SELECT count(*) FROM product_briefs brief
                           WHERE brief.project_id=project.entity_id) AS brief_count,
                         (SELECT count(*) FROM creative_batches batch
                           JOIN product_briefs brief ON brief.entity_id=batch.brief_id
                          WHERE brief.project_id=project.entity_id) AS ad_batch_count
                    FROM validation_projects project
                    LEFT JOIN LATERAL (
                        SELECT brief.entity_id,brief.status
                          FROM product_briefs brief
                         WHERE brief.project_id=project.entity_id
                         ORDER BY brief.created_at DESC LIMIT 1
                    ) latest ON true"""

    @staticmethod
    def _project_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "project_id": str(row[0]), "request_id": str(row[1]),
            "owner_idea_source_id": str(row[2]), "name": row[3], "name_source": row[4],
            "requested_by": row[5], "created_at": row[6].isoformat(),
            "updated_at": row[7].isoformat(),
            "latest_brief_id": None if row[8] is None else str(row[8]),
            "latest_brief_status": row[9], "brief_count": int(row[10]),
            "ad_batch_count": int(row[11]),
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
                self._project_select() + " ORDER BY project.created_at DESC LIMIT %s",
                (min(limit, 100),),
            ).fetchall()
        return [self._project_row(row) for row in rows]

    def rename_project(self, project_id: str, *, name: str, requested_by: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        normalized = " ".join(name.split())
        if not 1 <= len(normalized) <= 120:
            raise ValueError("Project name must contain 1-120 characters")
        project_uuid = UUID(project_id)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT name FROM validation_projects WHERE entity_id=%s FOR UPDATE",
                (project_uuid,),
            ).fetchone()
            if row is None:
                raise KeyError(project_id)
            connection.execute(
                """UPDATE validation_projects
                      SET name=%s,name_source='owner',updated_at=clock_timestamp()
                    WHERE entity_id=%s""",
                (normalized, project_uuid),
            )
            connection.execute(
                """INSERT INTO commander_audit_events(id,actor,action,target_id,details)
                   VALUES(%s,%s,'validation_project_renamed',%s,%s)""",
                (
                    UUID(new_uuid7()), requested_by, project_uuid,
                    Jsonb({"previous_name": row[0], "name": normalized}),
                ),
            )
        return self.get_project(project_id)

    @staticmethod
    def _brief_select() -> str:
        return """SELECT brief.entity_id,brief.request_id,brief.owner_idea_source_id,source.content,
                         brief.base_brief_id,brief.feedback_id,brief.status,brief.document,
                         brief.document_sha256,brief.quality_gates,brief.failure_count,
                         brief.error_code,brief.error_message,brief.requested_by,brief.created_at,
                         brief.updated_at,brief.completed_at,
                         EXISTS(SELECT 1 FROM product_brief_approvals approval WHERE approval.brief_id=brief.entity_id),
                         batch.entity_id,batch.status,brief.project_id,project.name
                  FROM product_briefs brief
                  JOIN commander_sources source ON source.entity_id=brief.owner_idea_source_id
                  JOIN validation_projects project ON project.entity_id=brief.project_id
                  LEFT JOIN LATERAL (
                      SELECT entity_id,status FROM creative_batches
                       WHERE brief_id=brief.entity_id ORDER BY created_at DESC LIMIT 1
                  ) batch ON true"""

    @staticmethod
    def _brief_row(row: Sequence[Any]) -> dict[str, Any]:
        document = None if row[7] is None else dict(row[7])
        return {
            "brief_id": str(row[0]), "request_id": str(row[1]),
            "owner_idea_source_id": str(row[2]), "raw_idea": row[3],
            "base_brief_id": None if row[4] is None else str(row[4]),
            "feedback_id": None if row[5] is None else str(row[5]),
            "status": row[6], "document": document, "document_sha256": row[8],
            "quality_gates": row[9], "failure_count": int(row[10]),
            "error_code": row[11], "error_message": row[12], "requested_by": row[13],
            "created_at": row[14].isoformat(), "updated_at": row[15].isoformat(),
            "completed_at": None if row[16] is None else row[16].isoformat(),
            "approved": bool(row[17]),
            "creative_batch_id": None if row[18] is None else str(row[18]),
            "creative_batch_status": row[19],
            "project_id": str(row[20]), "project_name": row[21],
            **({} if document is None else document),
        }

    def create_brief(self, *, request_id: str, raw_idea: str, requested_by: str) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        request_uuid = UUID(request_id)
        normalized = raw_idea.strip()
        if not 1 <= len(normalized) <= 10_000:
            raise ValueError("raw_idea must contain 1-10000 characters")
        with self.connection() as connection:
            existing = connection.execute(
                self._brief_select() + " WHERE brief.request_id=%s", (request_uuid,)
            ).fetchone()
            if existing is not None:
                item = self._brief_row(existing)
                if item["raw_idea"] != normalized or item["base_brief_id"] is not None:
                    raise ValueError("request_id was already used with different Product Brief input")
                return item, False
            source_id, project_id, brief_id = (UUID(new_uuid7()) for _ in range(3))
            digest = hashlib.sha256(normalized.encode()).hexdigest()
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'source',%s)",
                (source_id, Jsonb({"source_type": "owner_idea"})),
            )
            connection.execute(
                """INSERT INTO commander_sources(
                       entity_id,source_type,title,provider,external_id,content,content_sha256,metadata
                   ) VALUES(%s,'owner_idea','Owner idea','owner',%s,%s,%s,'{}'::jsonb)""",
                (source_id, request_uuid.hex, normalized, digest),
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'validation_project',%s)",
                (project_id, Jsonb({"schema_version": 1})),
            )
            connection.execute(
                """INSERT INTO validation_projects(
                       entity_id,request_id,owner_idea_source_id,name,name_source,requested_by
                   ) VALUES(%s,%s,%s,%s,'raw_idea',%s)""",
                (project_id, request_uuid, source_id, _project_name(normalized), requested_by),
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
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return self.get_brief(str(brief_id)), True

    def create_revision(
        self, *, base_brief_id: str, request_id: str, instruction: str, requested_by: str
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        request_uuid = UUID(request_id)
        normalized = instruction.strip()
        if not 1 <= len(normalized) <= 2000:
            raise ValueError("instruction must contain 1-2000 characters")
        with self.connection() as connection:
            existing = connection.execute(
                self._brief_select() + " WHERE brief.request_id=%s", (request_uuid,)
            ).fetchone()
            if existing is not None:
                item = self._brief_row(existing)
                if item["base_brief_id"] != str(UUID(base_brief_id)):
                    raise ValueError("request_id was already used for another Product Brief")
                return item, False
            base = connection.execute(
                "SELECT status,document,owner_idea_source_id,project_id FROM product_briefs WHERE entity_id=%s FOR SHARE",
                (UUID(base_brief_id),),
            ).fetchone()
            if base is None:
                raise KeyError(base_brief_id)
            if base[0] != "completed" or base[1] is None:
                raise ValueError("only a completed Product Brief can be corrected")
            feedback_id, weight_id, brief_id, proposal_id = (UUID(new_uuid7()) for _ in range(4))
            for entity_id, kind, attributes in (
                (feedback_id, "human_feedback", {"domain": "product_brief"}),
                (weight_id, "weight_update", {"delta": 0}),
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
                (feedback_id, UUID(base_brief_id), normalized, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,'product_brief',0,'Product Brief feedback is append-only')""",
                (weight_id, feedback_id),
            )
            connection.execute(
                """INSERT INTO product_briefs(
                       entity_id,project_id,request_id,owner_idea_source_id,base_brief_id,feedback_id,status,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,'queued',%s)""",
                (brief_id, base[3], request_uuid, base[2], UUID(base_brief_id), feedback_id, requested_by),
            )
            lesson = f"Apply this owner preference to future Product Briefs when relevant: {normalized}"[:500]
            connection.execute(
                """INSERT INTO product_brief_skill_proposals(id,feedback_id,brief_id,lesson,status)
                   VALUES(%s,%s,%s,%s,'pending')""",
                (proposal_id, feedback_id, brief_id, lesson),
            )
            edges = (
                (base[3], "contains", brief_id, {"member": "product_brief"}),
                (brief_id, "derived_from", base[2], {"input": "owner_idea"}),
                (brief_id, "derived_from", feedback_id, {"input": "owner_feedback"}),
                (brief_id, "supersedes", UUID(base_brief_id), {}),
                (feedback_id, "evaluates", UUID(base_brief_id), {"section_id": "product_brief"}),
                (weight_id, "adjusts", feedback_id, {"delta": 0}),
            )
            for source, relation, target, attributes in edges:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
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
        suffix, params = "", []
        if project_id:
            suffix, params = " WHERE brief.project_id=%s", [UUID(project_id)]
        params.append(min(limit, 100))
        with self.connection() as connection:
            rows = connection.execute(
                self._brief_select() + suffix + " ORDER BY brief.created_at DESC LIMIT %s",
                tuple(params),
            ).fetchall()
        return [self._brief_row(row) for row in rows]

    def source(self, brief_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT source.entity_id,source.content FROM commander_sources source
                   JOIN product_briefs brief ON brief.owner_idea_source_id=source.entity_id
                   WHERE brief.entity_id=%s""",
                (UUID(brief_id),),
            ).fetchone()
        if row is None:
            raise KeyError(brief_id)
        return {"id": str(row[0]), "content": row[1]}

    def feedback(self, feedback_id: str) -> dict[str, str]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT section_id,instruction FROM commander_human_feedback WHERE entity_id=%s",
                (UUID(feedback_id),),
            ).fetchone()
        if row is None:
            raise KeyError(feedback_id)
        return {"section_id": row[0], "instruction": row[1]}

    def acquire_operation(self, kind: str, operation_id: str) -> bool:
        """Reserve the singleton guard; return false when this exact work already owns it."""
        with self.connection() as connection:
            row = connection.execute(
                "SELECT operation_kind,operation_id FROM commander_operation_guard WHERE singleton FOR UPDATE"
            ).fetchone()
            if row is not None and row[0] == kind and row[1] == UUID(operation_id):
                return False
            if row is None or row[1] is not None:
                active = "unknown" if row is None else f"{row[0]} {row[1]}"
                raise ValueError(f"heavy operation {active} is already active")
            connection.execute(
                "UPDATE commander_operation_guard SET operation_kind=%s,operation_id=%s,acquired_at=clock_timestamp() WHERE singleton",
                (kind, UUID(operation_id)),
            )
        return True

    def release_operation(self, operation_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton AND operation_id=%s""",
                (UUID(operation_id),),
            )

    def start_attempt(self, target_id: str, *, stage: str) -> tuple[str, int]:
        attempt_id = UUID(new_uuid7())
        table = "product_briefs" if stage == "product_brief" else "creative_batches"
        with self.connection() as connection:
            row = connection.execute(
                f"SELECT status FROM {table} WHERE entity_id=%s FOR UPDATE", (UUID(target_id),)
            ).fetchone()
            if row is None:
                raise KeyError(target_id)
            if row[0] not in {"queued", "failed"}:
                raise ValueError("only a queued or failed generation target can start")
            number = int(connection.execute(
                "SELECT COALESCE(max(attempt_number),0)+1 FROM validation_generation_attempts WHERE target_id=%s",
                (UUID(target_id),),
            ).fetchone()[0])
            connection.execute(
                "INSERT INTO validation_generation_attempts(id,target_id,stage,attempt_number,status) VALUES(%s,%s,%s,%s,'started')",
                (attempt_id, UUID(target_id), stage, number),
            )
            connection.execute(
                f"UPDATE {table} SET status='generating',error_code=NULL,error_message=NULL,updated_at=clock_timestamp() WHERE entity_id=%s",
                (UUID(target_id),),
            )
        return str(attempt_id), number

    def create_invocation(
        self, *, target_id: str, attempt_id: str, mode: str, idempotency_key: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        invocation_id = UUID(new_uuid7())
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO validation_provider_invocations(
                       id,target_id,attempt_id,provider,mode,idempotency_key,request_sha256,status
                   ) VALUES(%s,%s,%s,'codex_bridge',%s,%s,%s,'submitted')""",
                (invocation_id, UUID(target_id), UUID(attempt_id), mode, idempotency_key, _sha(request)),
            )
        return {"id": str(invocation_id)}

    def complete_invocation(self, invocation_id: str, response: Mapping[str, Any], provenance: Mapping[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute(
                """UPDATE validation_provider_invocations SET response_sha256=%s,status='completed',invocation=%s,
                          completed_at=clock_timestamp() WHERE id=%s AND status='submitted'""",
                (_sha(response), Jsonb(dict(provenance)), UUID(invocation_id)),
            )

    def fail_invocation(self, invocation_id: str, error: Exception) -> None:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute(
                """UPDATE validation_provider_invocations SET status='failed',invocation=%s,
                          completed_at=clock_timestamp() WHERE id=%s AND status='submitted'""",
                (Jsonb({"error_code": type(error).__name__, "error_message": str(error)[:1000]}), UUID(invocation_id)),
            )

    def record_notification_callback_failure(
        self, target_id: str, attempt_id: str, *, error: Exception
    ) -> None:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO commander_audit_events(id,actor,action,target_id,details)
                   VALUES(%s,'validation','telegram_generation_failure_callback_failed',%s,%s)""",
                (
                    UUID(new_uuid7()),
                    UUID(target_id),
                    Jsonb({
                        "attempt_id": str(UUID(attempt_id)),
                        "status": "failed",
                        "error_code": type(error).__name__,
                        "error_message": "Owner Gateway notification callback failed",
                    }),
                ),
            )

    def failure_notification(self, target_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT action,details,created_at FROM commander_audit_events
                   WHERE target_id=%s AND action IN (
                       'telegram_generation_failure_reserved',
                       'telegram_generation_failure_result',
                       'telegram_generation_failure_callback_failed'
                   )
                   ORDER BY created_at DESC LIMIT 1""",
                (UUID(target_id),),
            ).fetchone()
        if row is None:
            return None
        details = dict(row[1])
        return {
            "status": details.get("status", "pending"),
            "attempt_id": details.get("attempt_id"),
            "recorded_at": row[2].isoformat(),
        }

    def last_failed_attempt(self, target_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id,attempt_number,error_code,error_message,started_at,completed_at
                   FROM validation_generation_attempts
                   WHERE target_id=%s AND status='failed'
                   ORDER BY attempt_number DESC LIMIT 1""",
                (UUID(target_id),),
            ).fetchone()
        if row is None:
            return None
        return {
            "attempt_id": str(row[0]),
            "attempt_number": int(row[1]),
            "error_code": row[2],
            "error_message": row[3],
            "started_at": row[4].isoformat(),
            "completed_at": None if row[5] is None else row[5].isoformat(),
        }

    def finish_brief(
        self, brief_id: str, attempt_id: str, document: Mapping[str, Any], digest: str, quality: Mapping[str, Any]
    ) -> None:
        from psycopg.types.json import Jsonb
        generated_name = _project_name(str(document.get("product") or ""))
        if not generated_name:
            raise ValueError("completed Product Brief product cannot be empty")
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE product_briefs SET status='completed',document=%s,document_sha256=%s,quality_gates=%s,
                          completed_at=clock_timestamp(),updated_at=clock_timestamp()
                   WHERE entity_id=%s AND status='generating' AND document IS NULL""",
                (Jsonb(dict(document)), digest, Jsonb(dict(quality)), UUID(brief_id)),
            ).rowcount
            if changed != 1:
                raise ValueError("Product Brief completion lost its state transition")
            connection.execute(
                "UPDATE validation_generation_attempts SET status='completed',completed_at=clock_timestamp() WHERE id=%s AND status='started'",
                (UUID(attempt_id),),
            )
            connection.execute(
                """UPDATE validation_projects project
                      SET name=%s,name_source='product_brief',updated_at=clock_timestamp()
                     FROM product_briefs brief
                    WHERE brief.entity_id=%s
                      AND brief.project_id=project.entity_id
                      AND project.name_source <> 'owner'""",
                (generated_name, UUID(brief_id)),
            )

    def fail_attempt(self, target_id: str, attempt_id: str, *, stage: str, error: Exception) -> None:
        table = "product_briefs" if stage == "product_brief" else "creative_batches"
        with self.connection() as connection:
            connection.execute(
                f"""UPDATE {table} SET status='failed',failure_count=failure_count+1,error_code=%s,
                          error_message=%s,updated_at=clock_timestamp() WHERE entity_id=%s AND status='generating'""",
                (type(error).__name__, str(error)[:1000], UUID(target_id)),
            )
            connection.execute(
                """UPDATE validation_generation_attempts SET status='failed',error_code=%s,error_message=%s,
                          completed_at=clock_timestamp() WHERE id=%s AND status='started'""",
                (type(error).__name__, str(error)[:1000], UUID(attempt_id)),
            )

    def queue_retry(self, target_id: str, *, stage: str) -> dict[str, Any]:
        table = "product_briefs" if stage == "product_brief" else "creative_batches"
        with self.connection() as connection:
            changed = connection.execute(
                f"""UPDATE {table} SET status='queued',error_code=NULL,error_message=NULL,
                          updated_at=clock_timestamp() WHERE entity_id=%s AND status='failed'""",
                (UUID(target_id),),
            ).rowcount
        if changed != 1:
            raise ValueError("only a failed generation can be retried")
        return self.get_brief(target_id) if stage == "product_brief" else self.get_batch(target_id)

    def approve_and_queue_batch(self, brief_id: str, approved_by: str) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        should_start = False
        with self.connection() as connection:
            brief = connection.execute(
                "SELECT status,document FROM product_briefs WHERE entity_id=%s FOR UPDATE", (UUID(brief_id),)
            ).fetchone()
            if brief is None:
                raise KeyError(brief_id)
            if brief[0] != "completed" or brief[1] is None:
                raise ValueError("only a completed Product Brief can be approved")
            child = connection.execute(
                "SELECT 1 FROM product_briefs WHERE base_brief_id=%s LIMIT 1", (UUID(brief_id),)
            ).fetchone()
            if child is not None:
                raise ValueError("a superseded Product Brief cannot be approved")
            existing = connection.execute(
                """SELECT entity_id,status FROM creative_batches WHERE brief_id=%s
                    ORDER BY created_at DESC LIMIT 1""", (UUID(brief_id),)
            ).fetchone()
            if existing is not None:
                batch_id = str(existing[0])
                should_start = existing[1] == "queued"
            else:
                approval_id, batch_uuid = UUID(new_uuid7()), UUID(new_uuid7())
                batch_id = str(batch_uuid)
                connection.execute(
                    "INSERT INTO product_brief_approvals(id,brief_id,approved_by) VALUES(%s,%s,%s)",
                    (approval_id, UUID(brief_id), approved_by),
                )
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_batch',%s)",
                    (batch_uuid, Jsonb({"creative_count": 5})),
                )
                connection.execute(
                    "INSERT INTO creative_batches(entity_id,brief_id,status) VALUES(%s,%s,'queued')",
                    (batch_uuid, UUID(brief_id)),
                )
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                    (UUID(new_uuid7()), batch_uuid, UUID(brief_id), Jsonb({"input": "approved_product_brief"})),
                )
                should_start = True
            if should_start:
                guard = connection.execute(
                    "SELECT operation_kind,operation_id FROM commander_operation_guard WHERE singleton FOR UPDATE"
                ).fetchone()
                if (
                    guard is not None
                    and guard[0] == "ad_creative_batch"
                    and guard[1] == UUID(batch_id)
                ):
                    should_start = False
                    return self.get_batch(batch_id), should_start
                if guard is None or guard[1] is not None:
                    active = "unknown" if guard is None else f"{guard[0]} {guard[1]}"
                    raise ValueError(f"heavy operation {active} is already active")
                connection.execute(
                    """UPDATE commander_operation_guard
                       SET operation_kind='ad_creative_batch',operation_id=%s,acquired_at=clock_timestamp()
                       WHERE singleton""",
                    (UUID(batch_id),),
                )
        return self.get_batch(batch_id), should_start

    def create_lesson_rerun(
        self,
        source_batch_id: str,
        *,
        request_id: str,
        requested_by: str,
        skill_sha256: str,
    ) -> tuple[dict[str, Any], bool]:
        """Create one immutable child batch after the source feedback lesson was promoted."""
        from psycopg.types.json import Jsonb

        source_uuid, request_uuid = UUID(source_batch_id), UUID(request_id)
        if len(skill_sha256) != 64:
            raise ValueError("the Ad Creative skill snapshot digest is invalid")
        should_start = False
        with self.connection() as connection:
            existing_request = connection.execute(
                """SELECT entity_id,rerun_of_batch_id FROM creative_batches
                    WHERE request_id=%s FOR UPDATE""",
                (request_uuid,),
            ).fetchone()
            if existing_request is not None:
                if existing_request[1] != source_uuid:
                    raise ValueError("request_id was already used for another creative rerun")
                return self.get_batch(str(existing_request[0])), False

            source = connection.execute(
                """SELECT brief_id,status FROM creative_batches
                    WHERE entity_id=%s FOR UPDATE""",
                (source_uuid,),
            ).fetchone()
            if source is None:
                raise KeyError(source_batch_id)
            if source[1] != "completed":
                raise ValueError("only a completed creative batch can start a learned rerun")

            existing_child = connection.execute(
                """SELECT entity_id FROM creative_batches
                    WHERE rerun_of_batch_id=%s FOR UPDATE""",
                (source_uuid,),
            ).fetchone()
            if existing_child is not None:
                return self.get_batch(str(existing_child[0])), False

            lesson_counts = connection.execute(
                """SELECT proposal.status,count(*)
                     FROM ad_creative_skill_proposals proposal
                     JOIN ad_creatives creative ON creative.entity_id=proposal.creative_id
                    WHERE creative.batch_id=%s GROUP BY proposal.status""",
                (source_uuid,),
            ).fetchall()
            counts = {str(row[0]): int(row[1]) for row in lesson_counts}
            unfinished = sum(counts.get(status, 0) for status in ("pending", "planning", "failed"))
            if unfinished:
                raise ValueError("finish or dismiss every feedback lesson from this batch before rerunning")
            if counts.get("promoted", 0) < 1:
                raise ValueError("promote feedback from this batch before generating its learned rerun")

            guard = connection.execute(
                "SELECT operation_kind,operation_id FROM commander_operation_guard WHERE singleton FOR UPDATE"
            ).fetchone()
            if guard is None or guard[1] is not None:
                active = "unknown" if guard is None else f"{guard[0]} {guard[1]}"
                raise ValueError(f"heavy operation {active} is already active")

            batch_uuid = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_batch',%s)",
                (batch_uuid, Jsonb({"creative_count": 5, "reason": "owner_lesson_rerun"})),
            )
            connection.execute(
                """INSERT INTO creative_batches(
                       entity_id,brief_id,status,request_id,rerun_of_batch_id,requested_by,skill_sha256
                   ) VALUES(%s,%s,'queued',%s,%s,%s,%s)""",
                (batch_uuid, source[0], request_uuid, source_uuid, requested_by, skill_sha256),
            )
            for relation, target_id, attributes in (
                ("derived_from", source[0], {"input": "approved_product_brief"}),
                ("rerun_of", source_uuid, {"reason": "promoted_owner_lesson"}),
            ):
                connection.execute(
                    """INSERT INTO commander_relationships(
                           id,source_id,relation,target_id,attributes
                       ) VALUES(%s,%s,%s,%s,%s)""",
                    (UUID(new_uuid7()), batch_uuid, relation, target_id, Jsonb(attributes)),
                )
            connection.execute(
                """UPDATE commander_operation_guard
                   SET operation_kind='ad_creative_batch',operation_id=%s,acquired_at=clock_timestamp()
                   WHERE singleton""",
                (batch_uuid,),
            )
            should_start = True
        return self.get_batch(str(batch_uuid)), should_start

    @staticmethod
    def _batch_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "batch_id": str(row[0]), "brief_id": str(row[1]), "status": row[2],
            "batch_sha256": row[3], "quality_gates": row[4], "failure_count": int(row[5]),
            "error_code": row[6], "error_message": row[7], "created_at": row[8].isoformat(),
            "updated_at": row[9].isoformat(),
            "completed_at": None if row[10] is None else row[10].isoformat(),
            "approved_offer": row[11],
            "request_id": None if row[12] is None else str(row[12]),
            "rerun_of_batch_id": None if row[13] is None else str(row[13]),
            "requested_by": row[14], "skill_sha256": row[15],
            "rerun_batch_id": None if row[16] is None else str(row[16]),
            "lesson_status_counts": dict(row[17] or {}),
            "project_id": str(row[18]), "project_name": row[19],
            "brief_product": row[20],
        }

    @staticmethod
    def _batch_select() -> str:
        return """SELECT entity_id,brief_id,status,batch_sha256,quality_gates,failure_count,
                         error_code,error_message,created_at,updated_at,completed_at,
                         (SELECT brief.document->>'offer' FROM product_briefs brief
                          WHERE brief.entity_id=creative_batches.brief_id) AS approved_offer,
                         request_id,rerun_of_batch_id,requested_by,skill_sha256,
                         (SELECT child.entity_id FROM creative_batches child
                           WHERE child.rerun_of_batch_id=creative_batches.entity_id) AS rerun_batch_id,
                         (SELECT jsonb_object_agg(status,total) FROM (
                              SELECT proposal.status,count(*) AS total
                                FROM ad_creative_skill_proposals proposal
                                JOIN ad_creatives creative ON creative.entity_id=proposal.creative_id
                               WHERE creative.batch_id=creative_batches.entity_id
                               GROUP BY proposal.status
                          ) lesson_counts) AS lesson_status_counts,
                         (SELECT brief.project_id FROM product_briefs brief
                           WHERE brief.entity_id=creative_batches.brief_id) AS project_id,
                         (SELECT project.name FROM validation_projects project
                           JOIN product_briefs brief ON brief.project_id=project.entity_id
                          WHERE brief.entity_id=creative_batches.brief_id) AS project_name,
                         (SELECT brief.document->>'product' FROM product_briefs brief
                           WHERE brief.entity_id=creative_batches.brief_id) AS brief_product
                  FROM creative_batches"""

    def get_batch(self, batch_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._batch_select() + " WHERE entity_id=%s", (UUID(batch_id),)
            ).fetchone()
            if row is None:
                raise KeyError(batch_id)
            batch = self._batch_row(row)
            creative_rows = connection.execute(
                """SELECT creative.entity_id,creative.brief_id,creative.ordinal,creative.angle,creative.content,
                          creative.content_sha256,asset.entity_id,asset.bytes_sha256,
                          source.external_id,source.source_uri,source.metadata
                   FROM ad_creatives creative
                   JOIN ad_creative_assets asset ON asset.creative_id=creative.entity_id
                   JOIN commander_sources source ON source.entity_id=asset.source_id
                   WHERE creative.batch_id=%s ORDER BY creative.ordinal""",
                (UUID(batch_id),),
            ).fetchall()
        batch["creatives"] = [self._creative_row(item) for item in creative_rows]
        batch["last_failed_attempt"] = self.last_failed_attempt(batch_id)
        batch["failure_notification"] = self.failure_notification(batch_id)
        return batch

    def get_creative(self, creative_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT creative.entity_id,creative.brief_id,creative.ordinal,creative.angle,creative.content,
                          creative.content_sha256,asset.entity_id,asset.bytes_sha256,
                          source.external_id,source.source_uri,source.metadata,
                          creative.batch_id,brief.project_id
                     FROM ad_creatives creative
                     JOIN ad_creative_assets asset ON asset.creative_id=creative.entity_id
                     JOIN commander_sources source ON source.entity_id=asset.source_id
                     JOIN product_briefs brief ON brief.entity_id=creative.brief_id
                    WHERE creative.entity_id=%s""",
                (UUID(creative_id),),
            ).fetchone()
        if row is None:
            raise KeyError(creative_id)
        result = self._creative_row(row[:11])
        result["batch_id"] = str(row[11])
        result["project_id"] = str(row[12])
        return result

    @staticmethod
    def _creative_row(row: Sequence[Any]) -> dict[str, Any]:
        content = dict(row[4])
        metadata = dict(row[10])
        return {
            "creative_id": str(row[0]), "brief_id": str(row[1]),
            "ordinal": int(row[2]), "angle": row[3],
            **content, "content_sha256": row[5],
            "image": {
                "asset_id": str(row[6]), "url": f"/api/v1/ad-creatives/{row[0]}/image",
                "mime_type": "image/jpeg", "width": 1080, "height": 1080,
                "sha256": row[7], "provider": "pexels", "source_photo_id": row[8],
                "source_url": row[9], **metadata,
            },
        }

    def list_batches(
        self,
        limit: int = 100,
        *,
        brief_id: str | None = None,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions, params = [], []
        if brief_id:
            conditions.append("brief_id=%s")
            params.append(UUID(brief_id))
        if project_id:
            conditions.append(
                "brief_id IN (SELECT entity_id FROM product_briefs WHERE project_id=%s)"
            )
            params.append(UUID(project_id))
        suffix = "" if not conditions else " WHERE " + " AND ".join(conditions)
        params.append(min(limit, 100))
        with self.connection() as connection:
            rows = connection.execute(
                self._batch_select() + suffix + " ORDER BY created_at DESC LIMIT %s", tuple(params)
            ).fetchall()
        return [self.get_batch(str(row[0])) for row in rows]

    def finish_batch(
        self,
        batch_id: str,
        attempt_id: str,
        *,
        brief_id: str,
        creatives: Sequence[Mapping[str, Any]],
        digest: str,
        quality: Mapping[str, Any],
    ) -> None:
        from psycopg.types.json import Jsonb

        if len(creatives) != 5:
            raise ValueError("a completed creative batch must contain exactly five creatives")
        creative_ids = {str(item.get("creative_id")) for item in creatives}
        asset_ids = {str(item.get("asset_id")) for item in creatives}
        photo_ids = {str(dict(item.get("photo") or {}).get("external_id")) for item in creatives}
        if len(creative_ids) != 5 or len(asset_ids) != 5 or len(photo_ids) != 5:
            raise ValueError("creative, asset, and Pexels photo IDs must be distinct")
        from PIL import Image
        for item in creatives:
            asset_bytes = bytes(item["asset_bytes"])
            actual_digest = hashlib.sha256(asset_bytes).hexdigest()
            if actual_digest != item["asset_digest"]:
                raise ValueError("creative asset digest does not match its exact bytes")
            try:
                image = Image.open(BytesIO(asset_bytes))
                image.load()
            except Exception as error:
                raise ValueError("creative asset is not a decodable image") from error
            if image.format != "JPEG" or image.size != (1080, 1080):
                raise ValueError("creative asset must be an exact 1080x1080 JPEG")
        with self.connection() as connection:
            status = connection.execute(
                "SELECT status FROM creative_batches WHERE entity_id=%s FOR UPDATE", (UUID(batch_id),)
            ).fetchone()
            if status is None or status[0] != "generating":
                raise ValueError("creative batch completion lost its state transition")
            for ordinal, item in enumerate(creatives):
                creative_id = UUID(str(item["creative_id"]))
                asset_id = UUID(str(item["asset_id"]))
                photo = dict(item["photo"])
                source_row = connection.execute(
                    "SELECT entity_id FROM commander_sources WHERE provider='pexels' AND external_id=%s",
                    (photo["external_id"],),
                ).fetchone()
                if source_row is None:
                    source_id = UUID(new_uuid7())
                    source_content = str(photo.get("alt") or photo.get("attribution") or "Pexels photo")
                    connection.execute(
                        "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'source',%s)",
                        (source_id, Jsonb({"source_type": "stock_photo"})),
                    )
                    connection.execute(
                        """INSERT INTO commander_sources(
                               entity_id,source_type,title,source_uri,provider,external_id,content,content_sha256,metadata
                           ) VALUES(%s,'stock_photo',%s,%s,'pexels',%s,%s,%s,%s)""",
                        (
                            source_id, photo["attribution"], photo["source_uri"], photo["external_id"],
                            source_content, hashlib.sha256(source_content.encode()).hexdigest(), Jsonb(photo),
                        ),
                    )
                else:
                    source_id = source_row[0]
                content = dict(item["content"])
                for entity_id, kind, attributes in (
                    (creative_id, "ad_creative", {"angle": content["angle"]}),
                    (asset_id, "artifact", {"mime_type": "image/jpeg"}),
                ):
                    connection.execute(
                        "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                        (entity_id, kind, Jsonb(attributes)),
                    )
                content_digest = _sha(content)
                connection.execute(
                    """INSERT INTO ad_creatives(
                           entity_id,batch_id,brief_id,ordinal,angle,content,content_sha256
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                    (creative_id, UUID(batch_id), UUID(brief_id), ordinal, content["angle"], Jsonb(content), content_digest),
                )
                connection.execute(
                    """INSERT INTO ad_creative_assets(
                           entity_id,creative_id,source_id,mime_type,width,height,bytes,bytes_sha256
                       ) VALUES(%s,%s,%s,'image/jpeg',1080,1080,%s,%s)""",
                    (asset_id, creative_id, source_id, item["asset_bytes"], item["asset_digest"]),
                )
                edges = (
                    (UUID(batch_id), "contains", creative_id, {"ordinal": ordinal}),
                    (creative_id, "derived_from", UUID(brief_id), {"input": "product_brief"}),
                    (creative_id, "contains", asset_id, {}),
                    (asset_id, "derived_from", source_id, {"adaptation": "square_post_v1"}),
                )
                for source, relation, target, attributes in edges:
                    connection.execute(
                        "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                        (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                    )
            connection.execute(
                """UPDATE creative_batches SET status='completed',batch_sha256=%s,quality_gates=%s,
                          completed_at=clock_timestamp(),updated_at=clock_timestamp() WHERE entity_id=%s""",
                (digest, Jsonb(dict(quality)), UUID(batch_id)),
            )
            connection.execute(
                "UPDATE validation_generation_attempts SET status='completed',completed_at=clock_timestamp() WHERE id=%s AND status='started'",
                (UUID(attempt_id),),
            )

    def image(self, creative_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT asset.bytes,asset.bytes_sha256,asset.mime_type FROM ad_creative_assets asset
                   WHERE asset.creative_id=%s""",
                (UUID(creative_id),),
            ).fetchone()
        if row is None:
            raise KeyError(creative_id)
        return {"bytes": bytes(row[0]), "sha256": row[1], "mime_type": row[2]}

    def record_creative_feedback(self, creative_id: str, *, comment: str, requested_by: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        normalized = comment.strip()
        if not 1 <= len(normalized) <= 2000:
            raise ValueError("feedback must contain 1-2000 characters")
        feedback_id, weight_id, proposal_id = (UUID(new_uuid7()) for _ in range(3))
        with self.connection() as connection:
            row = connection.execute(
                "SELECT batch_id FROM ad_creatives WHERE entity_id=%s", (UUID(creative_id),)
            ).fetchone()
            if row is None:
                raise KeyError(creative_id)
            for entity_id, kind, attributes in (
                (feedback_id, "human_feedback", {"domain": "ad_creative"}),
                (weight_id, "weight_update", {"delta": 0}),
            ):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                    (entity_id, kind, Jsonb(attributes)),
                )
            connection.execute(
                """INSERT INTO commander_human_feedback(entity_id,target_id,domain,section_id,instruction,actor)
                   VALUES(%s,%s,'ad_creative','complete_creative',%s,%s)""",
                (feedback_id, UUID(creative_id), normalized, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,'ad_creative',0,'Creative feedback is append-only')""",
                (weight_id, feedback_id),
            )
            lesson = f"Apply this owner preference to future Ad Creatives when relevant: {normalized}"[:500]
            connection.execute(
                """INSERT INTO ad_creative_skill_proposals(id,feedback_id,creative_id,lesson,status)
                   VALUES(%s,%s,%s,%s,'pending')""",
                (proposal_id, feedback_id, UUID(creative_id), lesson),
            )
            for source, relation, target, attributes in (
                (feedback_id, "evaluates", UUID(creative_id), {}),
                (weight_id, "adjusts", feedback_id, {"delta": 0}),
            ):
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return {"feedback_id": str(feedback_id), "weight_update_id": str(weight_id), "proposal_id": str(proposal_id)}

    def proposals(self, domain: str, *, target_id: str | None = None) -> list[dict[str, Any]]:
        if domain == "product_brief":
            table, target_column = "product_brief_skill_proposals", "brief_id"
        elif domain == "ad_creative":
            table, target_column = "ad_creative_skill_proposals", "creative_id"
        elif domain == "ad_studio":
            table, target_column = "ad_studio_skill_proposals", "render_id"
        else:
            raise ValueError("unknown skill-proposal domain")
        suffix, params = "", []
        if target_id:
            suffix, params = f" WHERE {target_column}=%s", [UUID(target_id)]
        with self.connection() as connection:
            rows = connection.execute(
                f"""SELECT id,feedback_id,{target_column},lesson,status,command_session_id,created_at,updated_at
                    FROM {table}{suffix} ORDER BY created_at""", tuple(params)
            ).fetchall()
        return [{
            "proposal_id": str(row[0]), "feedback_id": str(row[1]), "target_id": str(row[2]),
            "lesson": row[3], "status": row[4],
            "command_session_id": None if row[5] is None else str(row[5]),
            "created_at": row[6].isoformat(), "updated_at": row[7].isoformat(),
        } for row in rows]

    def update_proposal(self, domain: str, proposal_id: str, *, lesson: str | None = None, status: str | None = None, command_session_id: str | None = None) -> dict[str, Any]:
        if domain == "product_brief":
            table = "product_brief_skill_proposals"
        elif domain == "ad_creative":
            table = "ad_creative_skill_proposals"
        elif domain == "ad_studio":
            table = "ad_studio_skill_proposals"
        else:
            raise ValueError("unknown skill-proposal domain")
        updates, params = [], []
        if lesson is not None:
            normalized = lesson.strip()
            if not 1 <= len(normalized) <= 500:
                raise ValueError("lesson must contain 1-500 characters")
            updates.append("lesson=%s"); params.append(normalized)
        if status is not None:
            updates.append("status=%s"); params.append(status)
        if command_session_id is not None:
            updates.append("command_session_id=%s"); params.append(UUID(command_session_id))
        if not updates:
            raise ValueError("proposal update is empty")
        params.append(UUID(proposal_id))
        with self.connection() as connection:
            changed = connection.execute(
                f"UPDATE {table} SET {','.join(updates)},updated_at=clock_timestamp() WHERE id=%s AND status='pending'",
                tuple(params),
            ).rowcount
        if changed != 1:
            raise ValueError("only a pending proposal can be updated")
        return next(item for item in self.proposals(domain) if item["proposal_id"] == proposal_id)

    def plan_proposals(
        self, domain: str, proposal_ids: list[str], *, command_session_id: str
    ) -> dict[str, Any]:
        if domain == "product_brief":
            table = "product_brief_skill_proposals"
        elif domain == "ad_creative":
            table = "ad_creative_skill_proposals"
        elif domain == "ad_studio":
            table = "ad_studio_skill_proposals"
        else:
            raise ValueError("unknown skill-proposal domain")
        if not 1 <= len(proposal_ids) <= 100:
            raise ValueError("one to 100 proposal IDs are required")
        normalized_ids = [UUID(value) for value in proposal_ids]
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("proposal IDs must be unique")
        session_uuid = UUID(command_session_id)
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT id,status FROM {table} WHERE id=ANY(%s) FOR UPDATE",
                (normalized_ids,),
            ).fetchall()
            if len(rows) != len(normalized_ids) or any(row[1] != "pending" for row in rows):
                raise ValueError("all grouped proposals must exist and be pending")
            changed = connection.execute(
                f"""UPDATE {table} SET status='planning',command_session_id=%s,
                            updated_at=clock_timestamp() WHERE id=ANY(%s) AND status='pending'""",
                (session_uuid, normalized_ids),
            ).rowcount
            if changed != len(normalized_ids):
                raise ValueError("all grouped proposals must enter planning together")
        proposals = {item["proposal_id"]: item for item in self.proposals(domain)}
        return {
            "command_session_id": command_session_id,
            "items": [proposals[str(proposal_id)] for proposal_id in normalized_ids],
        }

    def finish_proposal(self, command_session_id: str, *, status: str) -> dict[str, Any]:
        if status not in {"promoted", "failed"}:
            raise ValueError("proposal completion status must be promoted or failed")
        session_uuid = UUID(command_session_id)
        matched: tuple[str, list[str]] | None = None
        with self.connection() as connection:
            for domain, table in (
                ("product_brief", "product_brief_skill_proposals"),
                ("ad_creative", "ad_creative_skill_proposals"),
                ("ad_studio", "ad_studio_skill_proposals"),
            ):
                rows = connection.execute(
                    f"""UPDATE {table} SET status=%s,updated_at=clock_timestamp()
                        WHERE command_session_id=%s AND status='planning' RETURNING id""",
                    (status, session_uuid),
                ).fetchall()
                if rows:
                    matched = (domain, [str(row[0]) for row in rows])
                    break
        if matched is not None:
            domain, proposal_ids = matched
            proposals = {item["proposal_id"]: item for item in self.proposals(domain)}
            first = proposals[proposal_ids[0]]
            return {**first, "proposal_count": len(proposal_ids), "items": [proposals[item] for item in proposal_ids]}
        return {"matched": False, "command_session_id": command_session_id, "status": status}

    def restore_proposals(self, command_session_id: str) -> dict[str, Any]:
        session_uuid = UUID(command_session_id)
        matches: list[tuple[str, str, list[tuple[Any, ...]]]] = []
        with self.connection() as connection:
            for domain, table in (
                ("product_brief", "product_brief_skill_proposals"),
                ("ad_creative", "ad_creative_skill_proposals"),
                ("ad_studio", "ad_studio_skill_proposals"),
            ):
                rows = connection.execute(
                    f"SELECT id,status FROM {table} WHERE command_session_id=%s FOR UPDATE",
                    (session_uuid,),
                ).fetchall()
                if rows:
                    matches.append((domain, table, rows))
            if len(matches) > 1:
                raise ValueError("one command session cannot restore proposals from multiple domains")
            if not matches:
                return {"matched": False, "command_session_id": command_session_id}
            domain, table, rows = matches[0]
            if any(row[1] != "failed" for row in rows):
                raise ValueError("only a wholly failed proposal group can be restored")
            changed = connection.execute(
                f"""UPDATE {table} SET status='planning',updated_at=clock_timestamp()
                    WHERE command_session_id=%s AND status='failed'""",
                (session_uuid,),
            ).rowcount
            if changed != len(rows):
                raise ValueError("all grouped proposals must be restored together")
        proposals = {item["proposal_id"]: item for item in self.proposals(domain)}
        proposal_ids = [str(row[0]) for row in rows]
        return {
            "matched": True,
            "domain": domain,
            "command_session_id": command_session_id,
            "proposal_count": len(proposal_ids),
            "items": [proposals[proposal_id] for proposal_id in proposal_ids],
        }

    @staticmethod
    def _studio_brand_kit_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "brand_kit_id": str(row[0]), "project_id": str(row[1]),
            "parent_brand_kit_id": None if row[2] is None else str(row[2]),
            "document": dict(row[3]), "document_sha256": row[4],
            "created_by": row[5], "created_at": row[6].isoformat(),
        }

    def create_studio_brand_kit(
        self,
        project_id: str,
        *,
        document: Mapping[str, Any],
        parent_brand_kit_id: str | None,
        requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import validate_brand_kit

        project_uuid = UUID(project_id)
        parent_uuid = None if parent_brand_kit_id is None else UUID(parent_brand_kit_id)
        normalized = validate_brand_kit(document)
        logo_uuid = None if normalized["logo_source_asset_id"] is None else UUID(normalized["logo_source_asset_id"])
        entity_id = UUID(new_uuid7())
        with self.connection() as connection:
            if connection.execute(
                "SELECT 1 FROM validation_projects WHERE entity_id=%s", (project_uuid,)
            ).fetchone() is None:
                raise KeyError(project_id)
            if parent_uuid is not None and connection.execute(
                "SELECT 1 FROM ad_studio_brand_kits WHERE entity_id=%s AND project_id=%s",
                (parent_uuid, project_uuid),
            ).fetchone() is None:
                raise ValueError("parent brand kit must belong to the same Project")
            if logo_uuid is not None and connection.execute(
                "SELECT 1 FROM ad_studio_source_assets WHERE entity_id=%s AND project_id=%s AND left(mime_type,6)='image/'",
                (logo_uuid, project_uuid),
            ).fetchone() is None:
                raise ValueError("brand logo must be a Project image source asset")
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_brand_kit',%s)",
                (entity_id, Jsonb({"schema_version": 1})),
            )
            connection.execute(
                """INSERT INTO ad_studio_brand_kits(
                       entity_id,project_id,parent_brand_kit_id,logo_source_asset_id,
                       document,document_sha256,created_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (entity_id, project_uuid, parent_uuid, logo_uuid, Jsonb(normalized), _sha(normalized), requested_by),
            )
            for source, relation, target, attributes in (
                (project_uuid, "contains", entity_id, {"member": "studio_brand_kit"}),
                *((entity_id, "derived_from", logo_uuid, {"input": "logo_source_asset"}) for _ in [0] if logo_uuid is not None),
                *((entity_id, "supersedes", parent_uuid, {}) for _ in [0] if parent_uuid is not None),
            ):
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return self.get_studio_brand_kit(str(entity_id))

    def get_studio_brand_kit(self, brand_kit_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,project_id,parent_brand_kit_id,document,document_sha256,
                          created_by,created_at FROM ad_studio_brand_kits WHERE entity_id=%s""",
                (UUID(brand_kit_id),),
            ).fetchone()
        if row is None:
            raise KeyError(brand_kit_id)
        return self._studio_brand_kit_row(row)

    def list_studio_brand_kits(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id,project_id,parent_brand_kit_id,document,document_sha256,
                          created_by,created_at FROM ad_studio_brand_kits
                   WHERE project_id=%s ORDER BY created_at DESC""",
                (UUID(project_id),),
            ).fetchall()
        return [self._studio_brand_kit_row(row) for row in rows]

    @staticmethod
    def _studio_template_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "template_id": str(row[0]), "project_id": str(row[1]), "name": row[2],
            "placement_tool_id": row[3], "document": dict(row[4]),
            "document_sha256": row[5], "created_by": row[6], "created_at": row[7].isoformat(),
        }

    def create_studio_template(
        self,
        project_id: str,
        *,
        name: str,
        document: Mapping[str, Any],
        requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import recipe_tools, validate_template

        project_uuid = UUID(project_id)
        normalized_name = " ".join(name.split())
        if not 1 <= len(normalized_name) <= 120:
            raise ValueError("Studio template name must contain 1-120 characters")
        normalized = validate_template(document)
        normalized_tools = recipe_tools(normalized)
        entity_id = UUID(new_uuid7())
        with self.connection() as connection:
            if connection.execute(
                "SELECT 1 FROM validation_projects WHERE entity_id=%s", (project_uuid,)
            ).fetchone() is None:
                raise KeyError(project_id)
            for tool in normalized_tools:
                for asset_id in tool["source_asset_ids"]:
                    if connection.execute(
                        "SELECT 1 FROM ad_studio_source_assets WHERE entity_id=%s AND project_id=%s",
                        (UUID(asset_id), project_uuid),
                    ).fetchone() is None:
                        raise ValueError("template source assets must belong to this Project")
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_template',%s)",
                (entity_id, Jsonb({"schema_version": normalized["schema_version"], "placement_tool_id": normalized["placement_tool_id"]})),
            )
            connection.execute(
                """INSERT INTO ad_studio_templates(
                       entity_id,project_id,name,placement_tool_id,document,document_sha256,created_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    entity_id, project_uuid, normalized_name, normalized["placement_tool_id"],
                    Jsonb(normalized), _sha(normalized), requested_by,
                ),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                (UUID(new_uuid7()), project_uuid, entity_id, Jsonb({"member": "studio_template"})),
            )
            for asset_id in {
                asset_id for tool in normalized_tools for asset_id in tool["source_asset_ids"]
            }:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                    (UUID(new_uuid7()), entity_id, UUID(asset_id), Jsonb({"input": "studio_source_asset"})),
                )
        return self.get_studio_template(str(entity_id))

    def get_studio_template(self, template_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,project_id,name,placement_tool_id,document,document_sha256,
                          created_by,created_at FROM ad_studio_templates WHERE entity_id=%s""",
                (UUID(template_id),),
            ).fetchone()
        if row is None:
            raise KeyError(template_id)
        return self._studio_template_row(row)

    def list_studio_templates(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id,project_id,name,placement_tool_id,document,document_sha256,
                          created_by,created_at FROM ad_studio_templates
                   WHERE project_id=%s ORDER BY created_at DESC LIMIT 100""",
                (UUID(project_id),),
            ).fetchall()
        return [self._studio_template_row(row) for row in rows]

    def apply_studio_template(
        self,
        template_id: str,
        *,
        brief_id: str,
        creative_id: str | None,
        brand_kit_id: str,
        photo_source_asset_id: str | None,
        request_id: str,
        requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.errors import UniqueViolation
        from .studio import _v2_submission, resolve_template_v2, validate_recipe

        template = self.get_studio_template(template_id)
        request_uuid = UUID(request_id)
        with self.connection() as connection:
            existing = connection.execute(
                """SELECT entity_id,template_id,brief_id,brand_kit_id,application_creative_id
                     FROM ad_studio_recipes WHERE application_request_id=%s""",
                (request_uuid,),
            ).fetchone()
        if existing is not None:
            expected_creative = None if creative_id is None else UUID(creative_id)
            if (
                existing[1] != UUID(template_id) or existing[2] != UUID(brief_id)
                or existing[3] != UUID(brand_kit_id) or existing[4] != expected_creative
            ):
                raise ValueError("template application request_id was already used with different input")
            return {
                "template_id": template_id, "project_id": template["project_id"],
                "brief_id": brief_id, "creative_id": creative_id, "brand_kit_id": brand_kit_id,
                "recipe": self.get_studio_recipe(str(existing[0])), "created": False,
            }
        if template["document"].get("schema_version") != 2:
            raise ValueError("typed application requires a StudioTemplateV2")
        brief = self.get_brief(brief_id)
        if not brief["approved"] or brief["status"] != "completed" or brief["project_id"] != template["project_id"]:
            raise ValueError("template and approved Brief must belong to the same Project")
        kit = self.get_studio_brand_kit(brand_kit_id)
        if kit["project_id"] != template["project_id"] or not kit["document"].get("logo_source_asset_id"):
            raise ValueError("template brand kit must belong to the same Project and contain a logo")
        uses_creative = any(
            binding["source"].startswith("creative.")
            for binding in template["document"]["bindings"].values()
        )
        if uses_creative and (creative_id is None or photo_source_asset_id is None):
            raise ValueError("template creative bindings require one selected creative")
        if creative_id is None:
            creative = {
                "hook": brief["promise"], "primary_text": brief["promise"],
                "image_description": "Natal branded editorial visual",
            }
            if photo_source_asset_id is None:
                photo_source_asset_id = str(kit["document"]["logo_source_asset_id"])
        else:
            creative = self.get_creative(creative_id)
            if creative["brief_id"] != brief_id or creative["project_id"] != template["project_id"]:
                raise ValueError("template creative must belong to the selected Brief and Project")
            source = self.get_studio_source_asset(str(photo_source_asset_id))
            if source["project_id"] != template["project_id"]:
                raise ValueError("resolved creative photo must belong to the same Project")
        document = resolve_template_v2(
            template["document"], brief=brief, creative=creative,
            photo_source_asset_id=str(photo_source_asset_id),
            logo_source_asset_id=str(kit["document"]["logo_source_asset_id"]),
        )
        contract = validate_recipe(
            document, project_id=template["project_id"], brief_id=brief_id,
            brand_kit_id=brand_kit_id, brief=brief,
        )
        try:
            created = self.create_studio_recipe(
                template["project_id"], brief_id=brief_id, brand_kit_id=brand_kit_id,
                document=_v2_submission(contract.value), requested_by=requested_by,
                template_id=template_id, application_request_id=request_id,
                application_creative_id=creative_id,
            )
        except UniqueViolation as error:
            # The application request UUID is the write reservation. If two owner
            # retries race, the committed winner is the sole immutable result.
            if error.diag.constraint_name != "ad_studio_recipes_application_request_id_key":
                raise
            return self.apply_studio_template(
                template_id, brief_id=brief_id, creative_id=creative_id,
                brand_kit_id=brand_kit_id, photo_source_asset_id=photo_source_asset_id,
                request_id=request_id, requested_by=requested_by,
            )
        return {
            "template_id": template_id, "project_id": template["project_id"],
            "brief_id": brief_id, "creative_id": creative_id, "brand_kit_id": brand_kit_id,
            "recipe": created, "created": True,
        }

    def studio_sample_template_media(self, template_id: str) -> str | None:
        from .studio import recipe_tools

        with self.connection() as connection:
            row = connection.execute(
                """SELECT recipe.document FROM ad_studio_sample_set_items item
                     JOIN ad_studio_recipes recipe ON recipe.entity_id=item.recipe_id
                    WHERE item.template_id=%s""",
                (UUID(template_id),),
            ).fetchone()
        if row is None:
            return None
        media = next((
            item for item in recipe_tools(dict(row[0]))
            if item["tool_id"] == "studio.frame.media.v1" and item["source_asset_ids"]
        ), None)
        return None if media is None else str(media["source_asset_ids"][0])

    @staticmethod
    def _studio_source_row(row: Sequence[Any], *, include_bytes: bool = False) -> dict[str, Any]:
        offset = 1 if include_bytes else 0
        result = {
            "source_asset_id": str(row[0]), "project_id": str(row[1]), "origin": row[2],
            "title": row[3], "mime_type": row[4], "width": int(row[5]), "height": int(row[6]),
            "duration_seconds": None if row[7] is None else float(row[7]),
            "bytes_sha256": row[8], "source_uri": row[9], "provider": row[10],
            "external_id": row[11], "license": row[12], "attribution": row[13],
            "metadata": dict(row[14] or {}), "created_by": row[15], "created_at": row[16].isoformat(),
            "asset_url": f"/api/v1/ad-studio/sources/{row[0]}/asset",
        }
        if include_bytes:
            result["bytes"] = bytes(row[17])
        return result

    def create_studio_source_asset(
        self,
        project_id: str,
        *,
        title: str,
        data: bytes,
        mime_type: str,
        origin: str,
        provider: str,
        external_id: str | None,
        source_uri: str | None,
        license_name: str | None,
        attribution: str | None,
        metadata: Mapping[str, Any],
        requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import inspect_media

        project_uuid = UUID(project_id)
        normalized_title = " ".join(title.split())[:200]
        if not normalized_title:
            raise ValueError("Studio source title is required")
        if origin not in {"owner_upload", "pexels", "canonical_brand", "ai_generated"}:
            raise ValueError("unknown Studio source origin")
        inspected = inspect_media(data, mime_type)
        digest = hashlib.sha256(data).hexdigest()
        stable_external_id = external_id or digest
        with self.connection() as connection:
            existing = connection.execute(
                """SELECT entity_id FROM ad_studio_source_assets
                   WHERE project_id=%s AND provider=%s AND external_id=%s""",
                (project_uuid, provider, stable_external_id),
            ).fetchone()
            if existing is not None:
                return self.get_studio_source_asset(str(existing[0]))
            if connection.execute(
                "SELECT 1 FROM validation_projects WHERE entity_id=%s", (project_uuid,)
            ).fetchone() is None:
                raise KeyError(project_id)
            entity_id = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_source_asset',%s)",
                (entity_id, Jsonb({"origin": origin, "mime_type": mime_type})),
            )
            connection.execute(
                """INSERT INTO ad_studio_source_assets(
                       entity_id,project_id,origin,title,mime_type,width,height,duration_seconds,
                       bytes,bytes_sha256,source_uri,provider,external_id,license,attribution,
                       metadata,created_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    entity_id, project_uuid, origin, normalized_title, inspected["mime_type"],
                    inspected["width"], inspected["height"], inspected["duration_seconds"], data,
                    digest, source_uri, provider, stable_external_id, license_name, attribution,
                    Jsonb(dict(metadata)), requested_by,
                ),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                (UUID(new_uuid7()), project_uuid, entity_id, Jsonb({"member": "studio_source_asset"})),
            )
        return self.get_studio_source_asset(str(entity_id))

    def get_studio_source_asset(self, source_asset_id: str, *, include_bytes: bool = False) -> dict[str, Any]:
        columns = ",bytes" if include_bytes else ""
        with self.connection() as connection:
            row = connection.execute(
                f"""SELECT entity_id,project_id,origin,title,mime_type,width,height,duration_seconds,
                           bytes_sha256,source_uri,provider,external_id,license,attribution,metadata,
                           created_by,created_at{columns}
                    FROM ad_studio_source_assets WHERE entity_id=%s""",
                (UUID(source_asset_id),),
            ).fetchone()
        if row is None:
            raise KeyError(source_asset_id)
        return self._studio_source_row(row, include_bytes=include_bytes)

    def list_studio_source_assets(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id,project_id,origin,title,mime_type,width,height,duration_seconds,
                          bytes_sha256,source_uri,provider,external_id,license,attribution,metadata,
                          created_by,created_at FROM ad_studio_source_assets
                   WHERE project_id=%s ORDER BY created_at DESC LIMIT 100""",
                (UUID(project_id),),
            ).fetchall()
        return [self._studio_source_row(row) for row in rows]

    def studio_source_asset(self, source_asset_id: str) -> dict[str, Any]:
        value = self.get_studio_source_asset(source_asset_id, include_bytes=True)
        return {"bytes": value["bytes"], "sha256": value["bytes_sha256"], "mime_type": value["mime_type"]}

    def ensure_natal_brand_kit(
        self, project_id: str, *, logo_data: bytes, requested_by: str,
    ) -> dict[str, Any]:
        logo = self.create_studio_source_asset(
            project_id, title="Natal canonical logo", data=logo_data, mime_type="image/png",
            origin="canonical_brand", provider="natal", external_id="logo-natal-v1",
            source_uri="natal/assets/logo-natal.png", license_name="PTW canonical brand asset",
            attribution="Natal canonical logo", metadata={
                "canonical_path": "natal/assets/logo-natal.png",
                "immutable_identity": True,
            }, requested_by=requested_by,
        )
        for item in self.list_studio_brand_kits(project_id):
            if (
                item["document"].get("name") == "Natal"
                and item["document"].get("logo_source_asset_id") == logo["source_asset_id"]
            ):
                return item
        return self.create_studio_brand_kit(
            project_id, parent_brand_kit_id=None, requested_by=requested_by,
            document={
                "name": "Natal",
                "colors": ["#0C0E12", "#181C25", "#F4F6FA", "#A3ADBD", "#43BDD3", "#87D0DD"],
                "fonts": ["Inter"],
                "tone_notes": "Compact, direct, calm, high-contrast and personally specific.",
                "logo_source_asset_id": logo["source_asset_id"],
            },
        )

    @staticmethod
    def _studio_recipe_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "recipe_id": str(row[0]), "project_id": str(row[1]), "brief_id": str(row[2]),
            "brand_kit_id": str(row[3]), "parent_recipe_id": None if row[4] is None else str(row[4]),
            "placement_tool_id": row[5], "document": dict(row[6]), "document_sha256": row[7],
            "renderer_version": row[8], "created_by": row[9], "created_at": row[10].isoformat(),
        }

    def create_studio_recipe(
        self,
        project_id: str,
        *,
        brief_id: str,
        brand_kit_id: str,
        document: Mapping[str, Any],
        requested_by: str,
        template_id: str | None = None,
        application_request_id: str | None = None,
        application_creative_id: str | None = None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import validate_recipe

        project_uuid, brief_uuid, kit_uuid = UUID(project_id), UUID(brief_id), UUID(brand_kit_id)
        template_uuid = None if template_id is None else UUID(template_id)
        application_uuid = None if application_request_id is None else UUID(application_request_id)
        application_creative_uuid = None if application_creative_id is None else UUID(application_creative_id)
        if (template_uuid is None) != (application_uuid is None):
            raise ValueError("template applications require template_id and application_request_id together")
        with self.connection() as connection:
            row = connection.execute(
                """SELECT brief.document FROM product_briefs brief
                   JOIN product_brief_approvals approval ON approval.brief_id=brief.entity_id
                   WHERE brief.entity_id=%s AND brief.project_id=%s AND brief.status='completed'""",
                (brief_uuid, project_uuid),
            ).fetchone()
            if row is None:
                raise ValueError("Studio recipes require an approved completed Brief in this Project")
            if connection.execute(
                "SELECT 1 FROM ad_studio_brand_kits WHERE entity_id=%s AND project_id=%s",
                (kit_uuid, project_uuid),
            ).fetchone() is None:
                raise ValueError("Studio brand kit must belong to this Project")
            if template_uuid is not None and connection.execute(
                "SELECT 1 FROM ad_studio_templates WHERE entity_id=%s AND project_id=%s",
                (template_uuid, project_uuid),
            ).fetchone() is None:
                raise ValueError("Studio template must belong to this Project")
            contract = validate_recipe(
                document, project_id=project_id, brief_id=brief_id,
                brand_kit_id=brand_kit_id, brief=dict(row[0]),
            )
            parent_uuid = None if contract.value["parent_recipe_id"] is None else UUID(contract.value["parent_recipe_id"])
            if parent_uuid is not None and connection.execute(
                "SELECT 1 FROM ad_studio_recipes WHERE entity_id=%s AND project_id=%s",
                (parent_uuid, project_uuid),
            ).fetchone() is None:
                raise ValueError("parent Studio recipe must belong to this Project")
            for asset_id in contract.value["source_asset_ids"]:
                if connection.execute(
                    "SELECT 1 FROM ad_studio_source_assets WHERE entity_id=%s AND project_id=%s",
                    (UUID(asset_id), project_uuid),
                ).fetchone() is None:
                    raise ValueError("every Studio source asset must belong to this Project")
            entity_id = UUID(new_uuid7())
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_recipe',%s)",
                (entity_id, Jsonb({"schema_version": contract.value["schema_version"], "placement_tool_id": contract.value["placement_tool_id"]})),
            )
            connection.execute(
                """INSERT INTO ad_studio_recipes(
                       entity_id,project_id,brief_id,brand_kit_id,template_id,application_request_id,
                       application_creative_id,
                       parent_recipe_id,placement_tool_id,
                       document,document_sha256,renderer_version,created_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    entity_id, project_uuid, brief_uuid, kit_uuid, template_uuid, application_uuid,
                    application_creative_uuid, parent_uuid,
                    contract.value["placement_tool_id"], Jsonb(dict(contract.value)),
                    contract.digest, contract.value["renderer_version"], requested_by,
                ),
            )
            edges = [
                (project_uuid, "contains", entity_id, {"member": "studio_recipe"}),
                (entity_id, "derived_from", brief_uuid, {"input": "product_brief"}),
                (entity_id, "derived_from", kit_uuid, {"input": "brand_kit"}),
                *((entity_id, "derived_from", UUID(asset_id), {"input": "studio_source_asset"})
                  for asset_id in contract.value["source_asset_ids"]),
                *([(entity_id, "derived_from", template_uuid, {"input": "studio_template"})]
                  if template_uuid is not None else []),
                *([(entity_id, "derived_from", application_creative_uuid, {"input": "ad_creative"})]
                  if application_creative_uuid is not None else []),
                *([(entity_id, "supersedes", parent_uuid, {})] if parent_uuid is not None else []),
            ]
            for source, relation, target, attributes in edges:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return self.get_studio_recipe(str(entity_id))

    def get_studio_recipe(self, recipe_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,project_id,brief_id,brand_kit_id,parent_recipe_id,
                          placement_tool_id,document,document_sha256,renderer_version,created_by,created_at
                   FROM ad_studio_recipes WHERE entity_id=%s""",
                (UUID(recipe_id),),
            ).fetchone()
        if row is None:
            raise KeyError(recipe_id)
        return self._studio_recipe_row(row)

    def list_studio_recipes(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id,project_id,brief_id,brand_kit_id,parent_recipe_id,
                          placement_tool_id,document,document_sha256,renderer_version,created_by,created_at
                   FROM ad_studio_recipes WHERE project_id=%s ORDER BY created_at DESC LIMIT 100""",
                (UUID(project_id),),
            ).fetchall()
        return [self._studio_recipe_row(row) for row in rows]

    def render_studio_recipe(self, recipe_id: str, renderer: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import build_manifest

        recipe = self.get_studio_recipe(recipe_id)
        brand_kit = self.get_studio_brand_kit(recipe["brand_kit_id"])
        assets = {
            asset_id: self.get_studio_source_asset(asset_id, include_bytes=True)
            for asset_id in recipe["document"]["source_asset_ids"]
        }
        attempt_id, render_id = UUID(new_uuid7()), UUID(new_uuid7())
        with self.connection() as connection:
            number = int(connection.execute(
                "SELECT COALESCE(max(attempt_number),0)+1 FROM ad_studio_render_attempts WHERE recipe_id=%s",
                (UUID(recipe_id),),
            ).fetchone()[0])
            connection.execute(
                "INSERT INTO ad_studio_render_attempts(id,recipe_id,attempt_number,status) VALUES(%s,%s,%s,'started')",
                (attempt_id, UUID(recipe_id), number),
            )
        try:
            rendered = renderer.render(
                recipe_id=recipe_id, recipe_digest=recipe["document_sha256"],
                recipe=recipe["document"], brand_kit=brand_kit, assets=assets,
            )
            manifest = build_manifest(
                render_id=str(render_id), recipe_id=recipe_id, recipe_digest=recipe["document_sha256"],
                recipe=recipe["document"], brand_kit=brand_kit, assets=assets, rendered=rendered,
            )
            with self.connection() as connection:
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_render',%s)",
                    (render_id, Jsonb({"mime_type": rendered["mime_type"]})),
                )
                connection.execute(
                    """INSERT INTO ad_studio_renders(
                           entity_id,recipe_id,attempt_id,mime_type,width,height,duration_seconds,
                           bytes,bytes_sha256,manifest,manifest_sha256,embedded_manifest,renderer_version
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        render_id, UUID(recipe_id), attempt_id, rendered["mime_type"],
                        recipe["document"]["width"], recipe["document"]["height"], rendered["duration_seconds"],
                        rendered["bytes"], manifest["output"]["bytes_sha256"], Jsonb(manifest),
                        _sha(manifest), rendered["embedded_manifest"], recipe["renderer_version"],
                    ),
                )
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                    (UUID(new_uuid7()), UUID(recipe_id), render_id, Jsonb({"artifact": "studio_render"})),
                )
                for asset_id in recipe["document"]["source_asset_ids"]:
                    connection.execute(
                        "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                        (UUID(new_uuid7()), render_id, UUID(asset_id), Jsonb({"source": "studio_asset"})),
                    )
                connection.execute(
                    "UPDATE ad_studio_render_attempts SET status='completed',completed_at=clock_timestamp() WHERE id=%s",
                    (attempt_id,),
                )
            return self.get_studio_render(str(render_id))
        except Exception as error:
            with self.connection() as connection:
                connection.execute(
                    """UPDATE ad_studio_render_attempts SET status='failed',error_code=%s,error_message=%s,
                              completed_at=clock_timestamp() WHERE id=%s AND status='started'""",
                    (type(error).__name__, str(error)[:1000], attempt_id),
                )
            raise

    @staticmethod
    def _studio_render_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "render_id": str(row[0]), "recipe_id": str(row[1]), "mime_type": row[2],
            "width": int(row[3]), "height": int(row[4]),
            "duration_seconds": None if row[5] is None else float(row[5]),
            "bytes_sha256": row[6], "manifest": dict(row[7]), "manifest_sha256": row[8],
            "renderer_version": row[9], "published": bool(row[10]),
            "created_at": row[11].isoformat(),
            "asset_url": f"/api/v1/ad-studio/renders/{row[0]}/asset",
            "manifest_url": f"/api/v1/ad-studio/renders/{row[0]}/manifest",
        }

    def get_studio_render(self, render_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT render.entity_id,render.recipe_id,render.mime_type,render.width,render.height,
                          render.duration_seconds,render.bytes_sha256,render.manifest,render.manifest_sha256,
                          render.renderer_version,
                          EXISTS(SELECT 1 FROM ad_studio_publications publication WHERE publication.render_id=render.entity_id),
                          render.created_at
                   FROM ad_studio_renders render WHERE render.entity_id=%s""",
                (UUID(render_id),),
            ).fetchone()
        if row is None:
            raise KeyError(render_id)
        return self._studio_render_row(row)

    def list_studio_renders(self, recipe_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT render.entity_id,render.recipe_id,render.mime_type,render.width,render.height,
                          render.duration_seconds,render.bytes_sha256,render.manifest,render.manifest_sha256,
                          render.renderer_version,
                          EXISTS(SELECT 1 FROM ad_studio_publications publication WHERE publication.render_id=render.entity_id),
                          render.created_at
                   FROM ad_studio_renders render WHERE render.recipe_id=%s
                   ORDER BY render.created_at DESC LIMIT 100""",
                (UUID(recipe_id),),
            ).fetchall()
        return [self._studio_render_row(row) for row in rows]

    def studio_render_asset(self, render_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT bytes,bytes_sha256,mime_type FROM ad_studio_renders WHERE entity_id=%s",
                (UUID(render_id),),
            ).fetchone()
        if row is None:
            raise KeyError(render_id)
        return {"bytes": bytes(row[0]), "sha256": row[1], "mime_type": row[2]}

    def _insert_studio_creative_validation(
        self,
        connection: Any,
        *,
        recipe_id: UUID,
        render_id: UUID | None,
        wizard_proposal_id: UUID | None,
        value: Mapping[str, Any],
    ) -> str:
        from psycopg.types.json import Jsonb

        validation_id = UUID(new_uuid7())
        attempts = list(value.get("attempts") or [])
        attempt_count = int(value.get("attempt_count") or 0)
        raw_recreation_count = value.get("recreation_count")
        recreation_count = -1 if raw_recreation_count is None else int(raw_recreation_count)
        if (
            value.get("status") != "approved"
            or not 1 <= attempt_count <= 4
            or recreation_count != attempt_count - 1
            or len(attempts) != attempt_count
        ):
            raise ValueError("Studio creative validation persistence is inconsistent")
        connection.execute(
            "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_creative_validation',%s)",
            (validation_id, Jsonb({
                "schema_version": 1, "status": "approved",
                "attempt_count": attempt_count, "recreation_count": recreation_count,
            })),
        )
        connection.execute(
            """INSERT INTO ad_studio_creative_validations(
                   entity_id,recipe_id,wizard_proposal_id,render_id,status,attempt_count,
                   recreation_count,skill_sha256,attempts
               ) VALUES(%s,%s,%s,%s,'approved',%s,%s,%s,%s)""",
            (
                validation_id, recipe_id, wizard_proposal_id, render_id,
                attempt_count, recreation_count, str(value["skill_sha256"]), Jsonb(attempts),
            ),
        )
        evaluated = wizard_proposal_id or render_id
        if evaluated is None:
            raise ValueError("approved Studio creative validation requires an evaluated artifact")
        for relation, target_id, attributes in (
            ("derived_from", recipe_id, {"input": "studio_recipe"}),
            ("evaluates", evaluated, {"result": "approved"}),
        ):
            connection.execute(
                """INSERT INTO commander_relationships(
                       id,source_id,relation,target_id,attributes
                   ) VALUES(%s,%s,%s,%s,%s)""",
                (UUID(new_uuid7()), validation_id, relation, target_id, Jsonb(attributes)),
            )
        return str(validation_id)

    def _studio_creative_validation(
        self, *, render_id: str | None = None, wizard_proposal_id: str | None = None,
    ) -> dict[str, Any] | None:
        if (render_id is None) == (wizard_proposal_id is None):
            raise ValueError("creative validation lookup requires exactly one target")
        field, target = (
            ("render_id", render_id) if render_id is not None
            else ("wizard_proposal_id", wizard_proposal_id)
        )
        with self.connection() as connection:
            row = connection.execute(
                f"""SELECT entity_id,recipe_id,status,attempt_count,recreation_count,
                            skill_sha256,attempts,created_at
                       FROM ad_studio_creative_validations WHERE {field}=%s""",
                (UUID(str(target)),),
            ).fetchone()
        if row is None:
            return None
        attempts = list(row[6])
        final = dict(attempts[-1]) if attempts else {}
        return {
            "validation_id": str(row[0]), "recipe_id": str(row[1]), "status": row[2],
            "attempt_count": int(row[3]), "recreation_count": int(row[4]),
            "skill_sha256": row[5], "attempts": attempts,
            "final_summary": final.get("summary"), "final_scores": final.get("scores"),
            "created_at": row[7].isoformat(),
        }

    def create_studio_sample_set(
        self,
        batch_id: str,
        *,
        brand_kit_id: str,
        media_by_angle: Mapping[str, str],
        renderer: Any,
        creative_validator: Any,
        requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.errors import UniqueViolation
        from psycopg.types.json import Jsonb
        from .studio import (
            SAMPLE_ANGLES, build_manifest, build_sample_documents,
            recipe_tools, template_from_validated_recipe, validate_recipe, validate_template,
        )

        batch_uuid = UUID(batch_id)
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT entity_id FROM ad_studio_sample_sets WHERE batch_id=%s", (batch_uuid,)
            ).fetchone()
        if existing is not None:
            return self.get_studio_sample_set(str(existing[0]))
        batch = self.get_batch(batch_id)
        if batch["status"] != "completed" or len(batch["creatives"]) != 5:
            raise ValueError("Studio samples require one completed five-creative batch")
        if tuple(item["angle"] for item in batch["creatives"]) != SAMPLE_ANGLES:
            raise ValueError("Studio sample batch angles are not in canonical order")
        brief = self.get_brief(batch["brief_id"])
        project_id = brief["project_id"]
        kit = self.get_studio_brand_kit(brand_kit_id)
        if kit["project_id"] != project_id or not kit["document"].get("logo_source_asset_id"):
            raise ValueError("Studio samples require the canonical Project brand kit and logo")
        for angle, asset_id in media_by_angle.items():
            if angle not in SAMPLE_ANGLES:
                raise ValueError("unknown Studio sample angle")
            asset = self.get_studio_source_asset(asset_id)
            if asset["project_id"] != project_id or not asset["mime_type"].startswith("image/"):
                raise ValueError("every Studio sample visual must be a Project image")
        documents = build_sample_documents(
            brief=brief, creatives=batch["creatives"], media_by_angle=media_by_angle,
            logo_source_asset_id=str(kit["document"]["logo_source_asset_id"]),
        )
        creative_by_angle = {item["angle"]: item["creative_id"] for item in batch["creatives"]}
        for item in documents:
            item["source_creative_id"] = creative_by_angle[item["angle"]]
        sample_set_id = UUID(new_uuid7())
        completed: list[dict[str, Any]] = []
        for item in documents:
            template_id, recipe_id, attempt_id, render_id = (UUID(new_uuid7()) for _ in range(4))
            template_document = validate_template(item["template"])
            recipe_contract = validate_recipe(
                item["recipe"], project_id=project_id, brief_id=batch["brief_id"],
                brand_kit_id=brand_kit_id, brief=brief,
            )
            assets = {
                asset_id: self.get_studio_source_asset(asset_id, include_bytes=True)
                for asset_id in recipe_contract.value["source_asset_ids"]
            }
            validation = creative_validator.review_and_recreate(
                recipe_id=str(recipe_id), recipe=recipe_contract.value,
                project_id=project_id, brief_id=batch["brief_id"],
                brand_kit_id=brand_kit_id, brief=brief, brand_kit=kit, assets=assets,
                context={
                    "workflow": "studio_sample_set", "batch_id": batch_id,
                    "angle": item["angle"], "source_creative_id": item["source_creative_id"],
                },
            )
            recipe_contract = validation.contract
            rendered = validation.rendered
            template_document = template_from_validated_recipe(
                template_document, recipe_contract.value,
            )
            manifest = build_manifest(
                render_id=str(render_id), recipe_id=str(recipe_id),
                recipe_digest=recipe_contract.digest, recipe=recipe_contract.value,
                brand_kit=kit, assets=assets, rendered=rendered,
            )
            completed.append({
                **item, "template_id": template_id, "recipe_id": recipe_id,
                "attempt_id": attempt_id, "render_id": render_id,
                "template_document": template_document, "recipe_contract": recipe_contract,
                "rendered": rendered, "manifest": manifest,
                "creative_validation": validation.persistence(),
                "caption": recipe_contract.value["share"]["caption"],
                "alt_text": recipe_contract.value["share"]["alt_text"],
            })
        try:
            with self.connection() as connection:
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_sample_set',%s)",
                    (sample_set_id, Jsonb({"schema_version": 1, "creative_count": 5})),
                )
                connection.execute(
                    """INSERT INTO ad_studio_sample_sets(
                           entity_id,project_id,brief_id,batch_id,brand_kit_id,status,created_by
                       ) VALUES(%s,%s,%s,%s,%s,'completed',%s)""",
                    (sample_set_id, UUID(project_id), UUID(batch["brief_id"]), batch_uuid, UUID(brand_kit_id), requested_by),
                )
                for item in completed:
                    template_id, recipe_id = item["template_id"], item["recipe_id"]
                    render_id, attempt_id = item["render_id"], item["attempt_id"]
                    contract = item["recipe_contract"]
                    rendered, manifest = item["rendered"], item["manifest"]
                    for entity_id, kind, attributes in (
                        (template_id, "studio_template", {"schema_version": 2, "placement_tool_id": contract.value["placement_tool_id"]}),
                        (recipe_id, "studio_recipe", {"schema_version": 2, "placement_tool_id": contract.value["placement_tool_id"]}),
                        (render_id, "studio_render", {"mime_type": rendered["mime_type"]}),
                    ):
                        connection.execute(
                            "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                            (entity_id, kind, Jsonb(attributes)),
                        )
                    connection.execute(
                        """INSERT INTO ad_studio_templates(
                               entity_id,project_id,name,placement_tool_id,document,document_sha256,created_by
                           ) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            template_id, UUID(project_id), item["name"], contract.value["placement_tool_id"],
                            Jsonb(item["template_document"]), _sha(item["template_document"]), requested_by,
                        ),
                    )
                    connection.execute(
                        """INSERT INTO ad_studio_recipes(
                               entity_id,project_id,brief_id,brand_kit_id,parent_recipe_id,placement_tool_id,
                               document,document_sha256,renderer_version,created_by
                           ) VALUES(%s,%s,%s,%s,NULL,%s,%s,%s,%s,%s)""",
                        (
                            recipe_id, UUID(project_id), UUID(batch["brief_id"]), UUID(brand_kit_id),
                            contract.value["placement_tool_id"], Jsonb(dict(contract.value)),
                            contract.digest, contract.value["renderer_version"], requested_by,
                        ),
                    )
                    connection.execute(
                        """INSERT INTO ad_studio_render_attempts(
                               id,recipe_id,attempt_number,status,completed_at
                           ) VALUES(%s,%s,1,'completed',clock_timestamp())""",
                        (attempt_id, recipe_id),
                    )
                    connection.execute(
                        """INSERT INTO ad_studio_renders(
                               entity_id,recipe_id,attempt_id,mime_type,width,height,duration_seconds,
                               bytes,bytes_sha256,manifest,manifest_sha256,embedded_manifest,renderer_version
                           ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            render_id, recipe_id, attempt_id, rendered["mime_type"],
                            contract.value["width"], contract.value["height"], rendered["duration_seconds"],
                            rendered["bytes"], manifest["output"]["bytes_sha256"], Jsonb(manifest),
                            _sha(manifest), rendered["embedded_manifest"], contract.value["renderer_version"],
                        ),
                    )
                    self._insert_studio_creative_validation(
                        connection, recipe_id=recipe_id, render_id=render_id,
                        wizard_proposal_id=None, value=item["creative_validation"],
                    )
                    connection.execute(
                        """INSERT INTO ad_studio_sample_set_items(
                               id,sample_set_id,ordinal,angle,name,source_creative_id,
                               template_id,recipe_id,render_id,caption,alt_text
                           ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            UUID(new_uuid7()), sample_set_id, item["ordinal"], item["angle"], item["name"],
                            UUID(item["source_creative_id"]), template_id, recipe_id, render_id,
                            item["caption"], item["alt_text"],
                        ),
                    )
                    edges = [
                        (UUID(project_id), "contains", template_id, {"member": "studio_template"}),
                        (UUID(project_id), "contains", recipe_id, {"member": "studio_recipe"}),
                        (recipe_id, "derived_from", UUID(batch["brief_id"]), {"input": "product_brief"}),
                        (recipe_id, "derived_from", UUID(brand_kit_id), {"input": "brand_kit"}),
                        (recipe_id, "contains", render_id, {"artifact": "studio_render"}),
                        *[(recipe_id, "derived_from", UUID(asset_id), {"input": "studio_source_asset"})
                          for asset_id in contract.value["source_asset_ids"]],
                        *[(render_id, "derived_from", UUID(asset_id), {"source": "studio_asset"})
                          for asset_id in contract.value["source_asset_ids"]],
                    ]
                    for source_id, relation, target_id, attributes in edges:
                        connection.execute(
                            "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                            (UUID(new_uuid7()), source_id, relation, target_id, Jsonb(attributes)),
                        )
                relationships = [
                    (UUID(project_id), "contains", sample_set_id, {"member": "studio_sample_set"}),
                    (sample_set_id, "derived_from", batch_uuid, {"input": "completed_creative_batch"}),
                    (sample_set_id, "derived_from", UUID(batch["brief_id"]), {"input": "approved_product_brief"}),
                    *[(sample_set_id, "derived_from", UUID(item["source_creative_id"]), {
                        "ordinal": item["ordinal"], "input": "source_ad_creative",
                    }) for item in completed],
                    *[(sample_set_id, "contains", item["recipe_id"], {
                        "ordinal": item["ordinal"], "angle": item["angle"],
                    }) for item in completed],
                ]
                for source_id, relation, target_id, attributes in relationships:
                    connection.execute(
                        "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                        (UUID(new_uuid7()), source_id, relation, target_id, Jsonb(attributes)),
                    )
        except UniqueViolation:
            with self.connection() as connection:
                existing = connection.execute(
                    "SELECT entity_id FROM ad_studio_sample_sets WHERE batch_id=%s", (batch_uuid,)
                ).fetchone()
            if existing is None:
                raise
            return self.get_studio_sample_set(str(existing[0]))
        return self.get_studio_sample_set(str(sample_set_id))

    def get_studio_sample_set(
        self, sample_set_id: str, *, include_download_digest: bool = True,
    ) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,project_id,brief_id,batch_id,brand_kit_id,status,created_by,created_at
                     FROM ad_studio_sample_sets WHERE entity_id=%s""",
                (UUID(sample_set_id),),
            ).fetchone()
            if row is None:
                raise KeyError(sample_set_id)
            item_rows = connection.execute(
                """SELECT ordinal,angle,name,source_creative_id,template_id,recipe_id,render_id,caption,alt_text
                     FROM ad_studio_sample_set_items WHERE sample_set_id=%s ORDER BY ordinal""",
                (UUID(sample_set_id),),
            ).fetchall()
        if len(item_rows) != 5:
            raise ValueError("completed Studio sample set must contain exactly five items")
        items = [{
            "ordinal": int(item[0]), "angle": item[1], "name": item[2],
            "source_creative_id": str(item[3]),
            "template_id": str(item[4]), "recipe_id": str(item[5]), "render_id": str(item[6]),
            "caption": item[7], "alt_text": item[8],
            "template": self.get_studio_template(str(item[4])),
            "recipe": self.get_studio_recipe(str(item[5])),
            "render": self.get_studio_render(str(item[6])),
            "creative_validation": self._studio_creative_validation(render_id=str(item[6])),
        } for item in item_rows]
        result = {
            "sample_set_id": str(row[0]), "project_id": str(row[1]), "brief_id": str(row[2]),
            "batch_id": str(row[3]), "brand_kit_id": str(row[4]), "status": row[5],
            "created_by": row[6], "created_at": row[7].isoformat(), "items": items,
            "download_url": f"/api/v1/ad-studio/sample-sets/{row[0]}/download",
            "download_mime_type": "application/zip",
        }
        if include_download_digest:
            result["download_sha256"] = self.studio_sample_set_download(str(row[0]))["sha256"]
        return result

    def list_studio_sample_sets(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id FROM ad_studio_sample_sets
                     WHERE project_id=%s ORDER BY created_at DESC LIMIT 20""",
                (UUID(project_id),),
            ).fetchall()
        return [self.get_studio_sample_set(str(row[0])) for row in rows]

    def get_studio_sample_set_for_batch(self, batch_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT entity_id FROM ad_studio_sample_sets WHERE batch_id=%s", (UUID(batch_id),)
            ).fetchone()
        return None if row is None else self.get_studio_sample_set(str(row[0]))

    def studio_sample_set_download(self, sample_set_id: str) -> dict[str, Any]:
        value = self.get_studio_sample_set(sample_set_id, include_download_digest=False)
        package_manifest = {
            "schema": "ptw.studio.share-package.v1",
            "sample_set_id": value["sample_set_id"], "project_id": value["project_id"],
            "brief_id": value["brief_id"], "batch_id": value["batch_id"],
            "items": [{
                "ordinal": item["ordinal"], "angle": item["angle"], "name": item["name"],
                "template_id": item["template_id"], "recipe_id": item["recipe_id"],
                "source_creative_id": item["source_creative_id"],
                "render_id": item["render_id"], "render_sha256": item["render"]["bytes_sha256"],
                "caption": item["caption"], "alt_text": item["alt_text"],
                "sources": item["render"]["manifest"].get("source_assets", []),
            } for item in value["items"]],
        }
        output = BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
            def write(name: str, data: bytes) -> None:
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o644 << 16
                archive.writestr(info, data)
            for item in value["items"]:
                stem = f'{item["ordinal"] + 1:02d}-{item["angle"]}'
                write(f"{stem}.jpg", self.studio_render_asset(item["render_id"])["bytes"])
                write(f"{stem}-caption.txt", (item["caption"] + "\n").encode())
                write(f"{stem}-alt.txt", (item["alt_text"] + "\n").encode())
            write("manifest.json", json.dumps(
                package_manifest, ensure_ascii=False, sort_keys=True, indent=2,
            ).encode() + b"\n")
        data = output.getvalue()
        return {"bytes": data, "sha256": hashlib.sha256(data).hexdigest(), "mime_type": "application/zip"}

    @staticmethod
    def _studio_wizard_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "proposal_id": str(row[0]), "recipe_id": str(row[1]), "instruction": row[2],
            "target_instance_id": None if row[3] is None else str(row[3]), "patch": list(row[4]),
            "before_sha256": row[5], "after_sha256": row[6], "preview_sha256": row[7],
            "preview_mime_type": row[8],
            "generated_source_asset_id": None if row[9] is None else str(row[9]),
            "provider_provenance": dict(row[10]), "status": row[11],
            "applied_recipe_id": None if row[12] is None else str(row[12]),
            "applied_render_id": None if row[13] is None else str(row[13]),
            "created_by": row[14], "created_at": row[15].isoformat(),
            "applied_at": None if row[16] is None else row[16].isoformat(),
            "preview_url": f"/api/v1/ad-studio/wizard-proposals/{row[0]}/preview",
        }

    def get_studio_wizard_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT entity_id,recipe_id,instruction,target_instance_id,patch,before_sha256,
                          after_sha256,preview_sha256,preview_mime_type,generated_source_asset_id,
                          provider_provenance,status,applied_recipe_id,applied_render_id,
                          created_by,created_at,applied_at
                     FROM ad_studio_wizard_proposals WHERE entity_id=%s""",
                (UUID(proposal_id),),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        result = self._studio_wizard_row(row)
        result["creative_validation"] = self._studio_creative_validation(
            wizard_proposal_id=proposal_id,
        )
        return result

    def list_studio_wizard_proposals(self, recipe_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT entity_id,recipe_id,instruction,target_instance_id,patch,before_sha256,
                          after_sha256,preview_sha256,preview_mime_type,generated_source_asset_id,
                          provider_provenance,status,applied_recipe_id,applied_render_id,
                          created_by,created_at,applied_at
                     FROM ad_studio_wizard_proposals WHERE recipe_id=%s
                     ORDER BY created_at DESC LIMIT 50""",
                (UUID(recipe_id),),
            ).fetchall()
        values = [self._studio_wizard_row(row) for row in rows]
        for value in values:
            value["creative_validation"] = self._studio_creative_validation(
                wizard_proposal_id=value["proposal_id"],
            )
        return values

    def create_studio_wizard_proposal(
        self,
        recipe_id: str,
        *,
        instruction: str,
        target_instance_id: str | None,
        proposal_builder: Any,
        renderer: Any,
        creative_validator: Any,
        requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import (
            validate_recipe, validate_recipe_recomposition_diff,
            validate_recipe_revision_diff,
        )

        recipe = self.get_studio_recipe(recipe_id)
        brief = self.get_brief(recipe["brief_id"])
        built = proposal_builder(
            recipe["document"], instruction=instruction, target_instance_id=target_instance_id,
            requested_by=requested_by,
        )
        if len(built) == 2:
            _untrusted_patch, submitted = built
            builder_context = {
                "generated_source_asset_id": None,
                "provider_provenance": {"provider": "injected", "contract": "studio-recipe-revision-v1"},
            }
        else:
            _untrusted_patch, submitted, builder_context = built
        patch = validate_recipe_revision_diff(
            recipe["document"], submitted, target_instance_id=target_instance_id,
        )
        submitted = dict(submitted)
        submitted["parent_recipe_id"] = recipe_id
        contract = validate_recipe(
            submitted, project_id=recipe["project_id"], brief_id=recipe["brief_id"],
            brand_kit_id=recipe["brand_kit_id"], brief=brief,
        )
        generated_source_asset_id = builder_context.get("generated_source_asset_id")
        generated_uuid = None if generated_source_asset_id is None else UUID(str(generated_source_asset_id))
        if generated_uuid is not None:
            generated = self.get_studio_source_asset(str(generated_uuid))
            if generated["project_id"] != recipe["project_id"] or generated["origin"] != "ai_generated":
                raise ValueError("wizard generated source must be an AI-generated asset in this Project")
            if str(generated_uuid) not in contract.value["source_asset_ids"]:
                raise ValueError("wizard generated source must be bound by the proposed recipe")
        provenance = builder_context.get("provider_provenance")
        if not isinstance(provenance, Mapping) or not provenance:
            raise ValueError("wizard proposal is missing immutable provider provenance")
        for asset_id in contract.value["source_asset_ids"]:
            source = self.get_studio_source_asset(asset_id)
            if source["project_id"] != recipe["project_id"]:
                raise ValueError("wizard recipe sources must remain in the same Project")
        brand_kit = self.get_studio_brand_kit(recipe["brand_kit_id"])
        assets = {
            asset_id: self.get_studio_source_asset(asset_id, include_bytes=True)
            for asset_id in contract.value["source_asset_ids"]
        }
        proposal_id = UUID(new_uuid7())
        validation = creative_validator.review_and_recreate(
            recipe_id=str(proposal_id), recipe=contract.value,
            project_id=recipe["project_id"], brief_id=recipe["brief_id"],
            brand_kit_id=recipe["brand_kit_id"], brief=brief,
            brand_kit=brand_kit, assets=assets,
            context={
                "workflow": "studio_wizard_preview", "base_recipe_id": recipe_id,
                "owner_instruction": " ".join(instruction.split()),
                "target_instance_id": target_instance_id,
            },
        )
        contract = validation.contract
        rendered = validation.rendered
        if generated_uuid is not None and str(generated_uuid) not in contract.value["source_asset_ids"]:
            raise ValueError("creative validator cannot discard the explicitly generated Wizard source")
        patch = validate_recipe_recomposition_diff(recipe["document"], contract.value)
        if rendered["mime_type"] != "image/jpeg":
            raise ValueError("wizard preview currently supports square static JPEG recipes")
        preview_sha256 = hashlib.sha256(rendered["bytes"]).hexdigest()
        target_uuid = None if target_instance_id is None else UUID(target_instance_id)
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'studio_wizard_proposal',%s)",
                (proposal_id, Jsonb({"schema_version": 1, "status": "previewed"})),
            )
            connection.execute(
                """INSERT INTO ad_studio_wizard_proposals(
                       entity_id,recipe_id,instruction,target_instance_id,patch,before_sha256,
                       after_document,after_sha256,preview_bytes,preview_sha256,preview_mime_type,
                       generated_source_asset_id,provider_provenance,status,created_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'image/jpeg',%s,%s,'previewed',%s)""",
                (
                    proposal_id, UUID(recipe_id), " ".join(instruction.split()), target_uuid,
                    Jsonb(patch), recipe["document_sha256"], Jsonb(dict(contract.value)),
                    contract.digest, rendered["bytes"], preview_sha256, generated_uuid,
                    Jsonb(dict(provenance)), requested_by,
                ),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                (UUID(new_uuid7()), proposal_id, UUID(recipe_id), Jsonb({"input": "studio_recipe"})),
            )
            if generated_uuid is not None:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                    (UUID(new_uuid7()), proposal_id, generated_uuid, Jsonb({"input": "generated_studio_source"})),
                )
            self._insert_studio_creative_validation(
                connection, recipe_id=UUID(recipe_id), render_id=None,
                wizard_proposal_id=proposal_id, value=validation.persistence(),
            )
        return self.get_studio_wizard_proposal(str(proposal_id))

    def studio_wizard_preview(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT preview_bytes,preview_sha256,preview_mime_type FROM ad_studio_wizard_proposals WHERE entity_id=%s",
                (UUID(proposal_id),),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return {"bytes": bytes(row[0]), "sha256": row[1], "mime_type": row[2]}

    def apply_studio_wizard_proposal(
        self, proposal_id: str, *, renderer: Any, requested_by: str,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        from .studio import build_manifest

        proposal_uuid = UUID(proposal_id)
        with self.connection() as connection:
            row = connection.execute(
                """SELECT proposal.status,proposal.applied_recipe_id,proposal.applied_render_id,
                          proposal.after_document,recipe.project_id,recipe.brief_id,recipe.brand_kit_id,
                          proposal.recipe_id,proposal.after_sha256
                     FROM ad_studio_wizard_proposals proposal
                     JOIN ad_studio_recipes recipe ON recipe.entity_id=proposal.recipe_id
                    WHERE proposal.entity_id=%s""",
                (proposal_uuid,),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if row[0] == "applied":
            return {
                "proposal": self.get_studio_wizard_proposal(proposal_id),
                "recipe": self.get_studio_recipe(str(row[1])),
                "render": self.get_studio_render(str(row[2])),
            }
        document = dict(row[3])
        brand_kit = self.get_studio_brand_kit(str(row[6]))
        assets = {
            asset_id: self.get_studio_source_asset(asset_id, include_bytes=True)
            for asset_id in document["source_asset_ids"]
        }
        recipe_uuid, attempt_uuid, render_uuid = (UUID(new_uuid7()) for _ in range(3))
        rendered = renderer.render(
            recipe_id=str(recipe_uuid), recipe_digest=str(row[8]), recipe=document,
            brand_kit=brand_kit, assets=assets,
        )
        manifest = build_manifest(
            render_id=str(render_uuid), recipe_id=str(recipe_uuid), recipe_digest=str(row[8]),
            recipe=document, brand_kit=brand_kit, assets=assets, rendered=rendered,
        )
        existing_ids: tuple[str, str] | None = None
        with self.connection() as connection:
            current = connection.execute(
                """SELECT status,applied_recipe_id,applied_render_id
                     FROM ad_studio_wizard_proposals WHERE entity_id=%s FOR UPDATE""",
                (proposal_uuid,),
            ).fetchone()
            if current is None:
                raise KeyError(proposal_id)
            if current[0] == "applied":
                existing_ids = (str(current[1]), str(current[2]))
            else:
                for entity_id, kind, attributes in (
                    (recipe_uuid, "studio_recipe", {"schema_version": 2, "placement_tool_id": document["placement_tool_id"]}),
                    (render_uuid, "studio_render", {"mime_type": rendered["mime_type"]}),
                ):
                    connection.execute(
                        "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                        (entity_id, kind, Jsonb(attributes)),
                    )
                connection.execute(
                    """INSERT INTO ad_studio_recipes(
                           entity_id,project_id,brief_id,brand_kit_id,parent_recipe_id,placement_tool_id,
                           document,document_sha256,renderer_version,created_by
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        recipe_uuid, row[4], row[5], row[6], row[7], document["placement_tool_id"],
                        Jsonb(document), row[8], document["renderer_version"], requested_by,
                    ),
                )
                connection.execute(
                    """INSERT INTO ad_studio_render_attempts(
                           id,recipe_id,attempt_number,status,completed_at
                       ) VALUES(%s,%s,1,'completed',clock_timestamp())""",
                    (attempt_uuid, recipe_uuid),
                )
                connection.execute(
                    """INSERT INTO ad_studio_renders(
                           entity_id,recipe_id,attempt_id,mime_type,width,height,duration_seconds,
                           bytes,bytes_sha256,manifest,manifest_sha256,embedded_manifest,renderer_version
                       ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        render_uuid, recipe_uuid, attempt_uuid, rendered["mime_type"],
                        document["width"], document["height"], rendered["duration_seconds"],
                        rendered["bytes"], manifest["output"]["bytes_sha256"], Jsonb(manifest),
                        _sha(manifest), rendered["embedded_manifest"], document["renderer_version"],
                    ),
                )
                connection.execute(
                """UPDATE ad_studio_wizard_proposals
                      SET status='applied',applied_recipe_id=%s,applied_render_id=%s,
                          applied_at=clock_timestamp()
                    WHERE entity_id=%s""",
                    (recipe_uuid, render_uuid, proposal_uuid),
                )
                edges = [
                    (UUID(str(row[4])), "contains", recipe_uuid, {"member": "studio_recipe"}),
                    (recipe_uuid, "derived_from", UUID(str(row[5])), {"input": "product_brief"}),
                    (recipe_uuid, "derived_from", UUID(str(row[6])), {"input": "brand_kit"}),
                    (recipe_uuid, "supersedes", UUID(str(row[7])), {}),
                    (recipe_uuid, "contains", render_uuid, {"artifact": "studio_render"}),
                    (proposal_uuid, "contains", recipe_uuid, {"result": "applied_recipe"}),
                    *[(recipe_uuid, "derived_from", UUID(asset_id), {"input": "studio_source_asset"})
                      for asset_id in document["source_asset_ids"]],
                    *[(render_uuid, "derived_from", UUID(asset_id), {"source": "studio_asset"})
                      for asset_id in document["source_asset_ids"]],
                ]
                for source_id, relation, target_id, attributes in edges:
                    connection.execute(
                        "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                        (UUID(new_uuid7()), source_id, relation, target_id, Jsonb(attributes)),
                    )
        if existing_ids is not None:
            return {
                "proposal": self.get_studio_wizard_proposal(proposal_id),
                "recipe": self.get_studio_recipe(existing_ids[0]),
                "render": self.get_studio_render(existing_ids[1]),
            }
        return {
            "proposal": self.get_studio_wizard_proposal(proposal_id),
            "recipe": self.get_studio_recipe(str(recipe_uuid)),
            "render": self.get_studio_render(str(render_uuid)),
        }

    def publish_studio_render(self, render_id: str, *, requested_by: str) -> dict[str, Any]:
        publication_id = UUID(new_uuid7())
        with self.connection() as connection:
            if connection.execute(
                "SELECT 1 FROM ad_studio_renders WHERE entity_id=%s", (UUID(render_id),)
            ).fetchone() is None:
                raise KeyError(render_id)
            connection.execute(
                """INSERT INTO ad_studio_publications(id,render_id,published_by)
                   VALUES(%s,%s,%s) ON CONFLICT(render_id) DO NOTHING""",
                (publication_id, UUID(render_id), requested_by),
            )
        return self.get_studio_render(render_id)

    def record_studio_feedback(self, render_id: str, *, comment: str, requested_by: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        normalized = comment.strip()
        if not 1 <= len(normalized) <= 2000:
            raise ValueError("feedback must contain 1-2000 characters")
        feedback_id, weight_id, proposal_id = (UUID(new_uuid7()) for _ in range(3))
        with self.connection() as connection:
            if connection.execute(
                """SELECT 1 FROM ad_studio_publications publication
                   WHERE publication.render_id=%s""",
                (UUID(render_id),),
            ).fetchone() is None:
                raise ValueError("only a published Studio render can receive training feedback")
            for entity_id, kind, attributes in (
                (feedback_id, "human_feedback", {"domain": "ad_studio"}),
                (weight_id, "weight_update", {"delta": 0}),
            ):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                    (entity_id, kind, Jsonb(attributes)),
                )
            connection.execute(
                """INSERT INTO commander_human_feedback(entity_id,target_id,domain,section_id,instruction,actor)
                   VALUES(%s,%s,'ad_studio','published_render',%s,%s)""",
                (feedback_id, UUID(render_id), normalized, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,'ad_studio',0,'Studio feedback is append-only')""",
                (weight_id, feedback_id),
            )
            lesson = f"Apply this owner preference to future Studio recipes when relevant: {normalized}"[:500]
            connection.execute(
                """INSERT INTO ad_studio_skill_proposals(id,feedback_id,render_id,lesson,status)
                   VALUES(%s,%s,%s,%s,'pending')""",
                (proposal_id, feedback_id, UUID(render_id), lesson),
            )
            for source, relation, target, attributes in (
                (feedback_id, "evaluates", UUID(render_id), {}),
                (weight_id, "adjusts", feedback_id, {"delta": 0}),
            ):
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return {"feedback_id": str(feedback_id), "weight_update_id": str(weight_id), "proposal_id": str(proposal_id)}

    def recover_interrupted(self) -> dict[str, int]:
        with self.connection() as connection:
            briefs = connection.execute(
                """UPDATE product_briefs SET status='failed',failure_count=failure_count+1,
                          error_code='Interrupted',error_message='service restarted during generation',
                          updated_at=clock_timestamp() WHERE status='generating'"""
            ).rowcount
            batches = connection.execute(
                """UPDATE creative_batches SET status='failed',failure_count=failure_count+1,
                          error_code='Interrupted',error_message='service restarted during generation',
                          updated_at=clock_timestamp() WHERE status='generating'"""
            ).rowcount
            connection.execute(
                """UPDATE validation_generation_attempts SET status='failed',error_code='Interrupted',
                          error_message='service restarted during generation',completed_at=clock_timestamp()
                   WHERE status='started'"""
            )
            connection.execute(
                """UPDATE validation_provider_invocations SET status='failed',
                          invocation='{"error_code":"Interrupted"}'::jsonb,completed_at=clock_timestamp()
                   WHERE status='submitted'"""
            )
            connection.execute(
                """UPDATE ad_studio_render_attempts SET status='failed',error_code='Interrupted',
                          error_message='service restarted during Studio render',completed_at=clock_timestamp()
                   WHERE status='started'"""
            )
            connection.execute(
                """UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton AND operation_kind IN (
                       'product_brief','ad_creative_batch','ad_studio_render',
                       'ad_studio_sample_set','ad_studio_wizard'
                   )"""
            )
        return {"briefs": briefs, "batches": batches}

    def activity(self) -> dict[str, Any]:
        with self.connection() as connection:
            guard = connection.execute(
                "SELECT operation_kind,operation_id,acquired_at FROM commander_operation_guard WHERE singleton"
            ).fetchone()
            counts = connection.execute(
                """SELECT (SELECT count(*) FROM product_briefs),
                          (SELECT count(*) FROM product_brief_approvals),
                          (SELECT count(*) FROM creative_batches),
                          (SELECT count(*) FROM ad_creatives),
                          (SELECT count(*) FROM ad_studio_templates),
                          (SELECT count(*) FROM ad_studio_recipes),
                          (SELECT count(*) FROM ad_studio_renders),
                          (SELECT count(*) FROM ad_studio_publications)"""
            ).fetchone()
        return {
            "operation": None if guard is None or guard[1] is None else {
                "kind": guard[0], "id": str(guard[1]), "acquired_at": guard[2].isoformat()
            },
            "briefs": int(counts[0]), "approved_briefs": int(counts[1]),
            "creative_batches": int(counts[2]), "creatives": int(counts[3]),
            "studio_templates": int(counts[4]), "studio_recipes": int(counts[5]),
            "studio_renders": int(counts[6]), "studio_publications": int(counts[7]),
        }
