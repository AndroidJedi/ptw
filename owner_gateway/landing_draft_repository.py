"""PostgreSQL authority for private Natal draft sets and block edits."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID, uuid4

from natal.page import BLOCK_IDS


class LandingDraftRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg

        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _set_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "request_id": str(row[1]), "idea_run_id": str(row[2]),
            "thesis_id": None if row[3] is None else str(row[3]), "brief": row[4],
            "recommended_template_id": row[5],
            "skill_memory_feedback_ids": [str(item) for item in row[6]],
            "status": row[7], "population_summary": row[8], "population_invocation": row[9],
            "error_code": row[10], "error_message": row[11], "requested_by": row[12],
            "created_at": row[13].isoformat(), "updated_at": row[14].isoformat(),
            "completed_at": None if row[15] is None else row[15].isoformat(),
        }

    @staticmethod
    def _set_select() -> str:
        return """SELECT entity_id,request_id,source_laval_run_id,source_thesis_id,
                         source_brief,recommended_template_id,skill_memory_feedback_ids,status,
                         population_summary,population_invocation,error_code,error_message,
                         requested_by,created_at,updated_at,completed_at
                  FROM natal_landing_draft_sets"""

    @staticmethod
    def _snapshot_row(row: Sequence[Any], *, include_html: bool = False) -> dict[str, Any]:
        result = {
            "id": str(row[0]), "draft_set_id": str(row[1]), "template_id": row[2],
            "snapshot_number": int(row[3]),
            "parent_snapshot_id": None if row[4] is None else str(row[4]),
            "source_feedback_id": None if row[5] is None else str(row[5]),
            "page_content": row[6], "page_content_sha256": row[7],
            "artifact_sha256": row[9], "is_current": bool(row[10]),
            "application_summary": row[11], "invocation": row[12],
            "created_at": row[13].isoformat(),
        }
        if include_html:
            result["preview_html"] = row[8]
        return result

    @staticmethod
    def _snapshot_select() -> str:
        return """SELECT entity_id,draft_set_id,template_id,snapshot_number,parent_snapshot_id,
                         source_feedback_id,page_content,page_content_sha256,preview_html,
                         artifact_sha256,is_current,application_summary,invocation,created_at
                  FROM natal_landing_draft_snapshots"""

    def get(self, draft_set_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._set_select() + " WHERE entity_id=%s", (UUID(draft_set_id),)
            ).fetchone()
            if row is None:
                raise KeyError(draft_set_id)
            snapshots = connection.execute(
                self._snapshot_select()
                + " WHERE draft_set_id=%s AND is_current ORDER BY template_id",
                (UUID(draft_set_id),),
            ).fetchall()
            edits = connection.execute(
                """SELECT request_id,draft_set_id,template_id,base_snapshot_id,block_id,
                          instruction,feedback_id,proposal_id,result_snapshot_id,status,
                          error_code,error_message,created_at,updated_at,completed_at
                   FROM natal_landing_draft_edits WHERE draft_set_id=%s
                   ORDER BY created_at DESC LIMIT 30""",
                (UUID(draft_set_id),),
            ).fetchall()
        result = self._set_row(row)
        result["variants"] = [self._snapshot_row(item) for item in snapshots]
        result["edits"] = [self._edit_row(item) for item in edits]
        return result

    def latest(self, idea_run_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                self._set_select()
                + " WHERE source_laval_run_id=%s ORDER BY created_at DESC LIMIT 1",
                (UUID(idea_run_id),),
            ).fetchone()
        return None if row is None else self.get(str(row[0]))

    def by_request(self, request_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                self._set_select() + " WHERE request_id=%s", (UUID(request_id),)
            ).fetchone()
        return None if row is None else self.get(str(row[0]))

    def active(self) -> dict[str, Any] | None:
        with self.connection() as connection:
            draft = connection.execute(
                self._set_select() + " WHERE status IN ('queued','populating') ORDER BY created_at LIMIT 1"
            ).fetchone()
            edit = connection.execute(
                """SELECT request_id,draft_set_id,template_id,base_snapshot_id,block_id,
                          instruction,feedback_id,proposal_id,result_snapshot_id,status,
                          error_code,error_message,created_at,updated_at,completed_at
                   FROM natal_landing_draft_edits
                   WHERE status IN ('queued','editing') ORDER BY created_at LIMIT 1"""
            ).fetchone()
        if draft is not None:
            return {"kind": "draft_set", **self._set_row(draft)}
        return None if edit is None else {"kind": "draft_edit", **self._edit_row(edit)}

    def recover_interrupted(self) -> int:
        with self.connection() as connection:
            drafts = connection.execute(
                """UPDATE natal_landing_draft_sets
                   SET status='failed',error_code='InterruptedError',
                       error_message='gateway restarted while draft population was active',
                       updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE status IN ('queued','populating')"""
            ).rowcount
            edits = connection.execute(
                """UPDATE natal_landing_draft_edits
                   SET status='failed',error_code='InterruptedError',
                       error_message='gateway restarted while block editing was active',
                       updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE status IN ('queued','editing')"""
            ).rowcount
            connection.execute(
                """UPDATE natal_landing_skill_proposals proposal
                   SET status='failed',updated_at=clock_timestamp()
                   FROM natal_landing_draft_edits edit
                   WHERE edit.proposal_id=proposal.entity_id AND edit.status='failed'
                     AND proposal.status='pending_generation'"""
            )
        return int(drafts) + int(edits)

    def create(
        self,
        prepared: Mapping[str, Any],
        *,
        request_id: str,
        requested_by: str,
        feedback_ids: Sequence[str],
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        existing = self.by_request(request_id)
        if existing is not None:
            return existing, False
        draft_set_id = uuid4()
        run_id = UUID(str(prepared["idea_run_id"]))
        brief = dict(prepared["brief"])
        raw_thesis = str((brief.get("source") or {}).get("thesis_id") or "")
        thesis_id = UUID(raw_thesis) if raw_thesis else None
        memory_ids = [UUID(item) for item in feedback_ids]
        with self.connection() as connection:
            connection.execute("BEGIN")
            source_id = self._source(connection, run_id, thesis_id)
            for feedback_id in memory_ids:
                exists = connection.execute(
                    "SELECT 1 FROM natal_landing_feedback WHERE feedback_id=%s AND source_laval_run_id=%s",
                    (feedback_id, run_id),
                ).fetchone()
                if exists is None:
                    raise ValueError("draft skill-memory feedback belongs to another Idea evaluation")
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_draft',%s)",
                (draft_set_id, Jsonb({"draft_type": "set", "idea_run_id": str(run_id)})),
            )
            connection.execute(
                """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                   VALUES(%s,%s,'derived_from',%s,%s)""",
                (uuid4(), draft_set_id, source_id, Jsonb({"thesis_id": raw_thesis or None})),
            )
            for feedback_id in memory_ids:
                connection.execute(
                    """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                       VALUES(%s,%s,'derived_from',%s,%s)""",
                    (uuid4(), draft_set_id, feedback_id, Jsonb({"input": "natal_skill_memory"})),
                )
            connection.execute(
                """INSERT INTO natal_landing_draft_sets(
                       entity_id,request_id,source_laval_run_id,source_thesis_id,source_brief,
                       recommended_template_id,skill_memory_feedback_ids,status,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,'queued',%s)""",
                (
                    draft_set_id, UUID(request_id), run_id, thesis_id, Jsonb(brief),
                    prepared["recommended_template_id"], memory_ids, requested_by,
                ),
            )
        return self.get(str(draft_set_id)), True

    @staticmethod
    def _source(connection: Any, run_id: UUID, thesis_id: UUID | None) -> UUID:
        from psycopg.types.json import Jsonb

        alias = connection.execute(
            "SELECT entity_id FROM commander_external_aliases WHERE system='idea_laval_run' AND external_id=%s",
            (str(run_id),),
        ).fetchone()
        if alias is not None:
            return alias[0]
        source_id = uuid4()
        connection.execute(
            "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'source',%s)",
            (source_id, Jsonb({"source_type": "idea_laval_evaluation", "idea_run_id": str(run_id), "thesis_id": None if thesis_id is None else str(thesis_id)})),
        )
        connection.execute(
            "INSERT INTO commander_external_aliases(system,external_id,entity_id) VALUES('idea_laval_run',%s,%s)",
            (str(run_id), source_id),
        )
        return source_id

    def mark_populating(self, draft_set_id: str) -> dict[str, Any]:
        self._set_status(draft_set_id, "populating", ("queued",))
        return self.get(draft_set_id)

    def complete_population(
        self,
        draft_set_id: str,
        *,
        pages: Mapping[str, Mapping[str, Any]],
        previews: Mapping[str, str],
        summary: str,
        invocation: Mapping[str, Any],
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        with self.connection() as connection:
            connection.execute("BEGIN")
            current = connection.execute(
                "SELECT status FROM natal_landing_draft_sets WHERE entity_id=%s FOR UPDATE",
                (UUID(draft_set_id),),
            ).fetchone()
            if current is None:
                raise KeyError(draft_set_id)
            if current[0] != "populating":
                raise ValueError("draft set is not being populated")
            for template_id in ("product", "community", "waitlist"):
                self._insert_snapshot(
                    connection,
                    draft_set_id=UUID(draft_set_id), template_id=template_id,
                    snapshot_number=1, parent_snapshot_id=None, source_feedback_id=None,
                    page_content=pages[template_id], preview_html=previews[template_id],
                    summary=summary, invocation=invocation,
                )
            connection.execute(
                """UPDATE natal_landing_draft_sets
                   SET status='ready',population_summary=%s,population_invocation=%s,
                       error_code=NULL,error_message=NULL,updated_at=clock_timestamp(),
                       completed_at=clock_timestamp() WHERE entity_id=%s""",
                (summary, Jsonb(dict(invocation)), UUID(draft_set_id)),
            )
        return self.get(draft_set_id)

    def fail_population(self, draft_set_id: str, *, code: str, message: str) -> dict[str, Any]:
        with self.connection() as connection:
            connection.execute(
                """UPDATE natal_landing_draft_sets
                   SET status='failed',error_code=%s,error_message=%s,updated_at=clock_timestamp(),
                       completed_at=clock_timestamp() WHERE entity_id=%s AND status IN ('queued','populating')""",
                (code[:120], message[:2000], UUID(draft_set_id)),
            )
        return self.get(draft_set_id)

    def retry_population(self, draft_set_id: str) -> dict[str, Any]:
        self._set_status(draft_set_id, "queued", ("failed",), clear=True)
        return self.get(draft_set_id)

    def _set_status(
        self, draft_set_id: str, status: str, expected: Sequence[str], *, clear: bool = False
    ) -> None:
        clear_sql = ",error_code=NULL,error_message=NULL,completed_at=NULL" if clear else ""
        with self.connection() as connection:
            cursor = connection.execute(
                f"UPDATE natal_landing_draft_sets SET status=%s,updated_at=clock_timestamp(){clear_sql} WHERE entity_id=%s AND status=ANY(%s)",
                (status, UUID(draft_set_id), list(expected)),
            )
        if cursor.rowcount != 1:
            raise ValueError("invalid draft set state transition")

    def snapshot(self, snapshot_id: str, *, include_html: bool = False) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._snapshot_select() + " WHERE entity_id=%s", (UUID(snapshot_id),)
            ).fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        return self._snapshot_row(row, include_html=include_html)

    def create_edit(
        self,
        snapshot_id: str,
        *,
        request_id: str,
        block_id: str,
        instruction: str,
        requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        if block_id not in BLOCK_IDS:
            raise ValueError("unknown landing block")
        normalized = instruction.strip()
        if not normalized or len(normalized) > 2000:
            raise ValueError("block instruction must contain 1-2000 characters")
        with self.connection() as connection:
            duplicate = connection.execute(
                """SELECT request_id,draft_set_id,template_id,base_snapshot_id,block_id,
                          instruction,feedback_id,proposal_id,result_snapshot_id,status,error_code,
                          error_message,created_at,updated_at,completed_at
                   FROM natal_landing_draft_edits WHERE request_id=%s""",
                (UUID(request_id),),
            ).fetchone()
            if duplicate is not None:
                return self._edit_row(duplicate), False
            connection.execute("BEGIN")
            snapshot = connection.execute(
                """SELECT draft_set_id,template_id,snapshot_number,artifact_sha256,is_current
                   FROM natal_landing_draft_snapshots WHERE entity_id=%s FOR UPDATE""",
                (UUID(snapshot_id),),
            ).fetchone()
            if snapshot is None:
                raise KeyError(snapshot_id)
            draft_set_id, template_id, snapshot_number, artifact_sha256, is_current = snapshot
            if not is_current:
                raise ValueError("draft snapshot is stale; reload the current preview")
            feedback_id = uuid4()
            update_id = uuid4()
            proposal_id = uuid4()
            component_id = self._component(connection, template_id, block_id)
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'human_feedback',%s)",
                (feedback_id, Jsonb({
                    "draft_set_id": str(draft_set_id), "snapshot_id": snapshot_id,
                    "template_id": template_id, "block_id": block_id,
                    "snapshot_number": int(snapshot_number), "comment": normalized,
                    "actor": requested_by, "feedback_type": "natal_landing_block_instruction",
                    "artifact_sha256": artifact_sha256,
                })),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'evaluates',%s,%s)",
                (uuid4(), feedback_id, UUID(snapshot_id), Jsonb({"artifact_sha256": artifact_sha256, "block_id": block_id})),
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'weight_update',%s)",
                (update_id, Jsonb({
                    "component_id": str(component_id), "previous_weight": 0.5, "delta": 0.0,
                    "new_weight": 0.5, "algorithm": "owner_text_feedback_v1", "rating": None,
                })),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,'{}'::jsonb)",
                (uuid4(), update_id, feedback_id),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'adjusts',%s,'{}'::jsonb)",
                (uuid4(), update_id, component_id),
            )
            connection.execute(
                """INSERT INTO natal_landing_feedback(
                       feedback_id,landing_build_id,target_entity_id,source_laval_run_id,
                       template_id,comment,artifact_sha256,requested_by,draft_set_id,
                       block_id,snapshot_number)
                   SELECT %s,NULL,%s,source_laval_run_id,%s,%s,%s,%s,%s,%s,%s
                   FROM natal_landing_draft_sets WHERE entity_id=%s""",
                (
                    feedback_id, UUID(snapshot_id), template_id, normalized, artifact_sha256,
                    requested_by, draft_set_id, block_id, snapshot_number, draft_set_id,
                ),
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'knowledge_assertion',%s)",
                (proposal_id, Jsonb({"assertion_type": "natal_skill_lesson_proposal", "status": "pending_generation"})),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,'{}'::jsonb)",
                (uuid4(), proposal_id, feedback_id),
            )
            connection.execute(
                """INSERT INTO natal_landing_skill_proposals(
                       entity_id,feedback_id,draft_set_id,template_id,block_id,status
                   ) VALUES(%s,%s,%s,%s,%s,'pending_generation')""",
                (proposal_id, feedback_id, draft_set_id, template_id, block_id),
            )
            connection.execute(
                """INSERT INTO natal_landing_draft_edits(
                       request_id,draft_set_id,template_id,base_snapshot_id,block_id,instruction,
                       feedback_id,proposal_id,status
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'queued')""",
                (UUID(request_id), draft_set_id, template_id, UUID(snapshot_id), block_id, normalized, feedback_id, proposal_id),
            )
        return self.edit(request_id), True

    def edit(self, request_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT request_id,draft_set_id,template_id,base_snapshot_id,block_id,
                          instruction,feedback_id,proposal_id,result_snapshot_id,status,error_code,
                          error_message,created_at,updated_at,completed_at
                   FROM natal_landing_draft_edits WHERE request_id=%s""",
                (UUID(request_id),),
            ).fetchone()
        if row is None:
            raise KeyError(request_id)
        return self._edit_row(row)

    @staticmethod
    def _edit_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "request_id": str(row[0]), "draft_set_id": str(row[1]), "template_id": row[2],
            "base_snapshot_id": str(row[3]), "block_id": row[4], "instruction": row[5],
            "feedback_id": str(row[6]), "proposal_id": str(row[7]),
            "result_snapshot_id": None if row[8] is None else str(row[8]), "status": row[9],
            "error_code": row[10], "error_message": row[11], "created_at": row[12].isoformat(),
            "updated_at": row[13].isoformat(),
            "completed_at": None if row[14] is None else row[14].isoformat(),
        }

    def mark_editing(self, request_id: str) -> dict[str, Any]:
        self._edit_status(request_id, "editing", ("queued",))
        return self.edit(request_id)

    def complete_edit(
        self,
        request_id: str,
        *,
        page_content: Mapping[str, Any],
        preview_html: str,
        summary: str,
        lesson: str,
        invocation: Mapping[str, Any],
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        with self.connection() as connection:
            connection.execute("BEGIN")
            edit = connection.execute(
                """SELECT draft_set_id,template_id,base_snapshot_id,feedback_id,proposal_id,status
                   FROM natal_landing_draft_edits WHERE request_id=%s FOR UPDATE""",
                (UUID(request_id),),
            ).fetchone()
            if edit is None:
                raise KeyError(request_id)
            draft_set_id, template_id, base_snapshot_id, feedback_id, proposal_id, status = edit
            if status != "editing":
                raise ValueError("draft edit is not active")
            base = connection.execute(
                "SELECT snapshot_number,is_current FROM natal_landing_draft_snapshots WHERE entity_id=%s FOR UPDATE",
                (base_snapshot_id,),
            ).fetchone()
            if base is None or not base[1]:
                raise ValueError("draft snapshot became stale; reload the current preview")
            connection.execute(
                "UPDATE natal_landing_draft_snapshots SET is_current=false WHERE entity_id=%s",
                (base_snapshot_id,),
            )
            result_id = self._insert_snapshot(
                connection, draft_set_id=draft_set_id, template_id=template_id,
                snapshot_number=int(base[0]) + 1, parent_snapshot_id=base_snapshot_id,
                source_feedback_id=feedback_id, page_content=page_content,
                preview_html=preview_html, summary=summary, invocation=invocation,
            )
            connection.execute(
                """UPDATE natal_landing_draft_edits
                   SET result_snapshot_id=%s,status='completed',error_code=NULL,error_message=NULL,
                       updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE request_id=%s""",
                (result_id, UUID(request_id)),
            )
            connection.execute(
                """UPDATE natal_landing_skill_proposals
                   SET proposed_lesson=%s,status='pending_review',updated_at=clock_timestamp()
                   WHERE entity_id=%s""",
                (lesson, proposal_id),
            )
            connection.execute(
                "UPDATE commander_entities SET attributes=attributes || %s WHERE id=%s",
                (Jsonb({"status": "pending_review", "proposed_lesson": lesson}), proposal_id),
            )
        return self.edit(request_id)

    def fail_edit(self, request_id: str, *, code: str, message: str) -> dict[str, Any]:
        with self.connection() as connection:
            connection.execute("BEGIN")
            row = connection.execute(
                """UPDATE natal_landing_draft_edits
                   SET status='failed',error_code=%s,error_message=%s,updated_at=clock_timestamp(),
                       completed_at=clock_timestamp()
                   WHERE request_id=%s AND status IN ('queued','editing') RETURNING proposal_id""",
                (code[:120], message[:2000], UUID(request_id)),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "UPDATE natal_landing_skill_proposals SET status='failed',updated_at=clock_timestamp() WHERE entity_id=%s AND status='pending_generation'",
                    (row[0],),
                )
        return self.edit(request_id)

    def retry_edit(self, request_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            connection.execute("BEGIN")
            edit = connection.execute(
                "SELECT base_snapshot_id,proposal_id,status FROM natal_landing_draft_edits WHERE request_id=%s FOR UPDATE",
                (UUID(request_id),),
            ).fetchone()
            if edit is None:
                raise KeyError(request_id)
            if edit[2] != "failed":
                raise ValueError("only a failed draft edit can be retried")
            current = connection.execute(
                "SELECT is_current FROM natal_landing_draft_snapshots WHERE entity_id=%s",
                (edit[0],),
            ).fetchone()
            if current is None or not current[0]:
                raise ValueError("failed edit targets a stale snapshot; create a new instruction")
            connection.execute(
                """UPDATE natal_landing_draft_edits SET status='queued',error_code=NULL,
                       error_message=NULL,completed_at=NULL,updated_at=clock_timestamp()
                   WHERE request_id=%s""",
                (UUID(request_id),),
            )
            connection.execute(
                "UPDATE natal_landing_skill_proposals SET status='pending_generation',updated_at=clock_timestamp() WHERE entity_id=%s",
                (edit[1],),
            )
        return self.edit(request_id)

    def _edit_status(self, request_id: str, status: str, expected: Sequence[str]) -> None:
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE natal_landing_draft_edits SET status=%s,updated_at=clock_timestamp() WHERE request_id=%s AND status=ANY(%s)",
                (status, UUID(request_id), list(expected)),
            )
        if cursor.rowcount != 1:
            raise ValueError("invalid draft edit state transition")

    def proposals(self, draft_set_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT proposal.entity_id,proposal.feedback_id,proposal.draft_set_id,
                          proposal.template_id,proposal.block_id,proposal.proposed_lesson,
                          proposal.reviewed_lesson,proposal.status,proposal.command_session_id,
                          feedback.comment,proposal.created_at,proposal.updated_at
                   FROM natal_landing_skill_proposals proposal
                   JOIN natal_landing_feedback feedback ON feedback.feedback_id=proposal.feedback_id
                   WHERE proposal.draft_set_id=%s ORDER BY proposal.created_at DESC""",
                (UUID(draft_set_id),),
            ).fetchall()
        return [self._proposal_row(row) for row in rows]

    def proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT proposal.entity_id,proposal.feedback_id,proposal.draft_set_id,
                          proposal.template_id,proposal.block_id,proposal.proposed_lesson,
                          proposal.reviewed_lesson,proposal.status,proposal.command_session_id,
                          feedback.comment,proposal.created_at,proposal.updated_at
                   FROM natal_landing_skill_proposals proposal
                   JOIN natal_landing_feedback feedback ON feedback.feedback_id=proposal.feedback_id
                   WHERE proposal.entity_id=%s""",
                (UUID(proposal_id),),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return self._proposal_row(row)

    @staticmethod
    def _proposal_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "feedback_id": str(row[1]), "draft_set_id": str(row[2]),
            "template_id": row[3], "block_id": row[4], "proposed_lesson": row[5],
            "reviewed_lesson": row[6], "status": row[7], "command_session_id": row[8],
            "comment": row[9], "created_at": row[10].isoformat(), "updated_at": row[11].isoformat(),
        }

    def dismiss_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            cursor = connection.execute(
                """UPDATE natal_landing_skill_proposals SET status='dismissed',updated_at=clock_timestamp()
                   WHERE entity_id=%s AND status IN ('pending_review','failed')""",
                (UUID(proposal_id),),
            )
        if cursor.rowcount != 1:
            raise ValueError("only a reviewable skill proposal can be dismissed")
        return self.proposal(proposal_id)

    def mark_proposal_planning(
        self, proposal_id: str, *, lesson: str, command_session_id: str
    ) -> dict[str, Any]:
        normalized = lesson.strip()
        if not normalized or len(normalized) > 500:
            raise ValueError("reviewed lesson must contain 1-500 characters")
        with self.connection() as connection:
            cursor = connection.execute(
                """UPDATE natal_landing_skill_proposals
                   SET reviewed_lesson=%s,status='planning',command_session_id=%s,
                       updated_at=clock_timestamp()
                   WHERE entity_id=%s AND status='pending_review'""",
                (normalized, command_session_id, UUID(proposal_id)),
            )
        if cursor.rowcount != 1:
            raise ValueError("only a pending skill proposal can be promoted")
        return self.proposal(proposal_id)

    @staticmethod
    def _component(connection: Any, template_id: str, block_id: str) -> UUID:
        from psycopg.types.json import Jsonb

        external_id = f"{template_id}:{block_id}"
        alias = connection.execute(
            "SELECT entity_id FROM commander_external_aliases WHERE system='natal_landing_block' AND external_id=%s",
            (external_id,),
        ).fetchone()
        if alias is not None:
            return alias[0]
        component_id = uuid4()
        connection.execute(
            "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_component',%s)",
            (component_id, Jsonb({"component_type": "natal_landing_block", "template_id": template_id, "block_id": block_id})),
        )
        connection.execute(
            "INSERT INTO commander_external_aliases(system,external_id,entity_id) VALUES('natal_landing_block',%s,%s)",
            (external_id, component_id),
        )
        return component_id

    def _insert_snapshot(
        self,
        connection: Any,
        *,
        draft_set_id: UUID,
        template_id: str,
        snapshot_number: int,
        parent_snapshot_id: UUID | None,
        source_feedback_id: UUID | None,
        page_content: Mapping[str, Any],
        preview_html: str,
        summary: str,
        invocation: Mapping[str, Any],
    ) -> UUID:
        from psycopg.types.json import Jsonb

        normalized = json.dumps(page_content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        content_digest = hashlib.sha256(normalized.encode()).hexdigest()
        artifact_digest = hashlib.sha256(preview_html.encode()).hexdigest()
        snapshot_id = uuid4()
        connection.execute(
            "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_draft',%s)",
            (snapshot_id, Jsonb({
                "draft_type": "snapshot", "draft_set_id": str(draft_set_id),
                "template_id": template_id, "snapshot_number": snapshot_number,
                "artifact_sha256": artifact_digest,
            })),
        )
        connection.execute(
            "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,'{}'::jsonb)",
            (uuid4(), draft_set_id, snapshot_id),
        )
        connection.execute(
            "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,'{}'::jsonb)",
            (uuid4(), snapshot_id, draft_set_id),
        )
        if parent_snapshot_id is not None:
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'supersedes',%s,'{}'::jsonb)",
                (uuid4(), snapshot_id, parent_snapshot_id),
            )
        if source_feedback_id is not None:
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,'{}'::jsonb)",
                (uuid4(), snapshot_id, source_feedback_id),
            )
        for block_id in BLOCK_IDS:
            component_id = self._component(connection, template_id, block_id)
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                (uuid4(), snapshot_id, component_id, Jsonb({"block_id": block_id})),
            )
        connection.execute(
            """INSERT INTO natal_landing_draft_snapshots(
                   entity_id,draft_set_id,template_id,snapshot_number,parent_snapshot_id,
                   source_feedback_id,page_content,page_content_sha256,preview_html,
                   artifact_sha256,is_current,application_summary,invocation
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s,%s)""",
            (
                snapshot_id, draft_set_id, template_id, snapshot_number, parent_snapshot_id,
                source_feedback_id, Jsonb(dict(page_content)), content_digest, preview_html,
                artifact_digest, summary, Jsonb(dict(invocation)),
            ),
        )
        return snapshot_id
