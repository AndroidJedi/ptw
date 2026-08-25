"""PostgreSQL authority for immutable briefs, creatives, assets, and feedback."""

from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
import hashlib
import json
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7


def _sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class ValidationRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _brief_select() -> str:
        return """SELECT brief.entity_id,brief.request_id,brief.owner_idea_source_id,source.content,
                         brief.base_brief_id,brief.feedback_id,brief.status,brief.document,
                         brief.document_sha256,brief.quality_gates,brief.failure_count,
                         brief.error_code,brief.error_message,brief.requested_by,brief.created_at,
                         brief.updated_at,brief.completed_at,
                         EXISTS(SELECT 1 FROM product_brief_approvals approval WHERE approval.brief_id=brief.entity_id),
                         batch.entity_id,batch.status
                  FROM product_briefs brief
                  JOIN commander_sources source ON source.entity_id=brief.owner_idea_source_id
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
            source_id, brief_id = UUID(new_uuid7()), UUID(new_uuid7())
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
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'product_brief',%s)",
                (brief_id, Jsonb({"schema_version": 1})),
            )
            connection.execute(
                """INSERT INTO product_briefs(
                       entity_id,request_id,owner_idea_source_id,status,requested_by
                   ) VALUES(%s,%s,%s,'queued',%s)""",
                (brief_id, request_uuid, source_id, requested_by),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                (UUID(new_uuid7()), brief_id, source_id, Jsonb({"input": "owner_idea"})),
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
                "SELECT status,document,owner_idea_source_id FROM product_briefs WHERE entity_id=%s FOR SHARE",
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
                       entity_id,request_id,owner_idea_source_id,base_brief_id,feedback_id,status,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,'queued',%s)""",
                (brief_id, request_uuid, base[2], UUID(base_brief_id), feedback_id, requested_by),
            )
            lesson = f"Apply this owner preference to future Product Briefs when relevant: {normalized}"[:500]
            connection.execute(
                """INSERT INTO product_brief_skill_proposals(id,feedback_id,brief_id,lesson,status)
                   VALUES(%s,%s,%s,%s,'pending')""",
                (proposal_id, feedback_id, brief_id, lesson),
            )
            edges = (
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

    def list_briefs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                self._brief_select() + " ORDER BY brief.created_at DESC LIMIT %s", (min(limit, 100),)
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
                          ) lesson_counts) AS lesson_status_counts
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

    def list_batches(self, limit: int = 100, *, brief_id: str | None = None) -> list[dict[str, Any]]:
        suffix, params = "", []
        if brief_id:
            suffix, params = " WHERE brief_id=%s", [UUID(brief_id)]
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
                """UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton AND operation_kind IN ('product_brief','ad_creative_batch')"""
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
                          (SELECT count(*) FROM ad_creatives)"""
            ).fetchone()
        return {
            "operation": None if guard is None or guard[1] is None else {
                "kind": guard[0], "id": str(guard[1]), "acquired_at": guard[2].isoformat()
            },
            "briefs": int(counts[0]), "approved_briefs": int(counts[1]),
            "creative_batches": int(counts[2]), "creatives": int(counts[3]),
        }
