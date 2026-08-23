"""PostgreSQL authority for private v2 Natal draft sets and scoped edits."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7
from natal.page import BLOCK_IDS


def _digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _audit_failure(
    connection: Any, *, action: str, target_id: UUID, code: str, message: str
) -> None:
    from psycopg.types.json import Jsonb

    connection.execute(
        """INSERT INTO commander_audit_events(id,actor,action,target_id,details)
           VALUES(%s,'system',%s,%s,%s)""",
        (
            UUID(new_uuid7()), action, target_id,
            Jsonb({"error_code": code[:100], "error_message": message[:2000]}),
        ),
    )


class LandingDraftRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _set_select() -> str:
        return """SELECT entity_id,request_id,positioning_project_id,positioning_revision_id,
                         privacy_policy_url,source_brief,status,population_summary,population_invocation,
                         error_code,error_message,requested_by,created_at,updated_at,completed_at
                  FROM landing_draft_sets"""

    @staticmethod
    def _set_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "request_id": str(row[1]),
            "positioning_project_id": str(row[2]), "positioning_revision_id": str(row[3]),
            "privacy_policy_url": row[4], "brief": row[5], "status": row[6],
            "population_summary": row[7], "population_invocation": row[8],
            "error_code": row[9], "error_message": row[10], "requested_by": row[11],
            "created_at": row[12].isoformat(), "updated_at": row[13].isoformat(),
            "completed_at": None if row[14] is None else row[14].isoformat(),
            "skill_memory_feedback_ids": [],
        }

    @staticmethod
    def _snapshot_select() -> str:
        return """SELECT entity_id,draft_set_id,template_id,snapshot_number,parent_snapshot_id,
                         source_feedback_id,page_content,page_content_sha256,preview_html,summary,
                         invocation,is_current,created_at FROM landing_draft_snapshots"""

    @staticmethod
    def _snapshot_row(row: Sequence[Any], *, include_html: bool = False) -> dict[str, Any]:
        result = {
            "id": str(row[0]), "draft_set_id": str(row[1]), "template_id": row[2],
            "snapshot_number": int(row[3]),
            "parent_snapshot_id": None if row[4] is None else str(row[4]),
            "source_feedback_id": None if row[5] is None else str(row[5]),
            "page_content": row[6], "page_content_sha256": row[7],
            "artifact_sha256": hashlib.sha256(row[8].encode()).hexdigest(),
            "summary": row[9], "invocation": row[10], "is_current": bool(row[11]),
            "created_at": row[12].isoformat(),
        }
        if include_html:
            result["preview_html"] = row[8]
        return result

    def get(self, draft_set_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._set_select() + " WHERE entity_id=%s", (UUID(draft_set_id),)
            ).fetchone()
            if row is None:
                raise KeyError(draft_set_id)
            result = self._set_row(row)
            snapshots = connection.execute(
                self._snapshot_select() + " WHERE draft_set_id=%s ORDER BY template_id,snapshot_number DESC",
                (UUID(draft_set_id),),
            ).fetchall()
        result["snapshots"] = [self._snapshot_row(item) for item in snapshots]
        result["current_snapshots"] = {
            item["template_id"]: item for item in result["snapshots"] if item["is_current"]
        }
        return result

    def latest(self, positioning_revision_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                self._set_select() + " WHERE positioning_revision_id=%s ORDER BY created_at DESC LIMIT 1",
                (UUID(positioning_revision_id),),
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
            row = connection.execute(
                self._set_select() + " WHERE status IN ('queued','populating') ORDER BY created_at LIMIT 1"
            ).fetchone()
            edit = connection.execute(
                """SELECT request_id,draft_set_id,template_id,base_snapshot_id,block_id,
                          instruction,feedback_id,proposal_id,result_snapshot_id,status,
                          error_code,error_message,created_at,updated_at,completed_at
                   FROM landing_draft_edits WHERE status IN ('queued','editing') ORDER BY created_at LIMIT 1"""
            ).fetchone()
        if row is not None:
            return {"kind": "draft_set", **self._set_row(row)}
        return None if edit is None else {"kind": "draft_edit", **self._edit_row(edit)}

    def recover_interrupted(self) -> int:
        with self.connection() as connection:
            set_ids = [row[0] for row in connection.execute(
                "SELECT entity_id FROM landing_draft_sets WHERE status IN ('queued','populating') FOR UPDATE"
            ).fetchall()]
            edit_ids = [row[0] for row in connection.execute(
                "SELECT request_id FROM landing_draft_edits WHERE status IN ('queued','editing') FOR UPDATE"
            ).fetchall()]
            connection.execute(
                """UPDATE landing_draft_sets SET status='failed',error_code='InterruptedError',
                       error_message='gateway restarted during population',updated_at=clock_timestamp(),
                       completed_at=clock_timestamp() WHERE status IN ('queued','populating')"""
            )
            connection.execute(
                """UPDATE landing_draft_edits SET status='failed',error_code='InterruptedError',
                       error_message='gateway restarted during edit',updated_at=clock_timestamp(),
                       completed_at=clock_timestamp() WHERE status IN ('queued','editing')"""
            )
            connection.execute(
                """UPDATE landing_skill_proposals proposal SET status='failed',updated_at=clock_timestamp()
                   FROM landing_draft_edits edit WHERE edit.proposal_id=proposal.id
                     AND edit.status='failed' AND proposal.status='pending_generation'"""
            )
            for target_id in set_ids:
                _audit_failure(
                    connection, action="landing.population.failed", target_id=target_id,
                    code="InterruptedError", message="gateway restarted during population",
                )
            for target_id in edit_ids:
                _audit_failure(
                    connection, action="landing.edit.failed", target_id=target_id,
                    code="InterruptedError", message="gateway restarted during edit",
                )
        return len(set_ids) + len(edit_ids)

    def create(
        self,
        prepared: Mapping[str, Any],
        *,
        request_id: str,
        requested_by: str,
        feedback_ids: Sequence[str] = (),
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        existing = self.by_request(request_id)
        if existing is not None:
            if (
                existing["positioning_revision_id"] != str(prepared["positioning_revision_id"])
                or existing["privacy_policy_url"] != str(prepared["brief"]["privacy_policy_url"])
            ):
                raise ValueError("request_id was already used for another Landing draft set")
            return existing, False
        draft_id = UUID(new_uuid7())
        project_id = UUID(str(prepared["positioning_project_id"]))
        revision_id = UUID(str(prepared["positioning_revision_id"]))
        brief = dict(prepared["brief"])
        with self.connection() as connection:
            approved = connection.execute(
                """SELECT 1 FROM positioning_approvals
                   WHERE project_id=%s AND revision_id=%s AND revoked_at IS NULL""",
                (project_id, revision_id),
            ).fetchone()
            if approved is None:
                raise ValueError("Landing requires the active approved positioning revision")
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_draft_set',%s)",
                (draft_id, Jsonb({"brand": "Natal"})),
            )
            connection.execute(
                """INSERT INTO landing_draft_sets(
                       entity_id,request_id,positioning_project_id,positioning_revision_id,
                       privacy_policy_url,source_brief,status,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,'queued',%s)""",
                (draft_id, UUID(request_id), project_id, revision_id, brief["privacy_policy_url"], Jsonb(brief), requested_by),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                (UUID(new_uuid7()), draft_id, revision_id, Jsonb({"input": "approved_positioning"})),
            )
        return self.get(str(draft_id)), True

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
            status = connection.execute(
                "SELECT status FROM landing_draft_sets WHERE entity_id=%s FOR UPDATE",
                (UUID(draft_set_id),),
            ).fetchone()
            if status is None:
                raise KeyError(draft_set_id)
            if status[0] != "populating":
                raise ValueError("draft set is not being populated")
            for template_id in ("product", "community", "waitlist"):
                self._insert_snapshot(
                    connection, draft_set_id=UUID(draft_set_id), template_id=template_id,
                    snapshot_number=1, parent_snapshot_id=None, feedback_id=None,
                    page_content=pages[template_id], preview_html=previews[template_id],
                    summary=summary, invocation=invocation,
                )
            connection.execute(
                """UPDATE landing_draft_sets SET status='completed',population_summary=%s,
                       population_invocation=%s,error_code=NULL,error_message=NULL,
                       updated_at=clock_timestamp(),completed_at=clock_timestamp() WHERE entity_id=%s""",
                (summary, Jsonb(dict(invocation)), UUID(draft_set_id)),
            )
        return self.get(draft_set_id)

    def fail_population(self, draft_set_id: str, *, code: str, message: str) -> dict[str, Any]:
        target_id = UUID(draft_set_id)
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE landing_draft_sets SET status='failed',error_code=%s,error_message=%s,
                       updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE entity_id=%s AND status IN ('queued','populating')""",
                (code[:100], message[:2000], target_id),
            ).rowcount
            if changed:
                _audit_failure(
                    connection, action="landing.population.failed", target_id=target_id,
                    code=code, message=message,
                )
        if not changed:
            raise ValueError("draft population cannot be failed from its current state")
        return self.get(draft_set_id)

    def retry_population(self, draft_set_id: str) -> dict[str, Any]:
        self._set_status(draft_set_id, "queued", ("failed",), clear=True)
        return self.get(draft_set_id)

    def _set_status(self, draft_set_id: str, status: str, expected: Sequence[str], *, clear: bool = False) -> None:
        clear_sql = ",error_code=NULL,error_message=NULL,completed_at=NULL" if clear else ""
        with self.connection() as connection:
            changed = connection.execute(
                f"UPDATE landing_draft_sets SET status=%s,updated_at=clock_timestamp(){clear_sql} WHERE entity_id=%s AND status=ANY(%s)",
                (status, UUID(draft_set_id), list(expected)),
            ).rowcount
        if not changed:
            raise ValueError("invalid draft-set transition")

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
        if not 1 <= len(normalized) <= 2000:
            raise ValueError("block instruction must contain 1-2000 characters")
        try:
            return self.edit(request_id), False
        except KeyError:
            pass
        feedback_id, weight_id, proposal_id = (UUID(new_uuid7()) for _ in range(3))
        with self.connection() as connection:
            snapshot = connection.execute(
                """SELECT draft_set_id,template_id,is_current FROM landing_draft_snapshots
                   WHERE entity_id=%s FOR SHARE""",
                (UUID(snapshot_id),),
            ).fetchone()
            if snapshot is None:
                raise KeyError(snapshot_id)
            if not snapshot[2]:
                raise ValueError("selected landing snapshot is stale")
            for entity_id, kind, attributes in (
                (feedback_id, "human_feedback", {"domain": "landing", "block_id": block_id}),
                (weight_id, "weight_update", {"delta": 0}),
            ):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                    (entity_id, kind, Jsonb(attributes)),
                )
            connection.execute(
                """INSERT INTO commander_human_feedback(entity_id,target_id,domain,section_id,instruction,actor)
                   VALUES(%s,%s,'landing',%s,%s,%s)""",
                (feedback_id, UUID(snapshot_id), block_id, normalized, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,%s,0,'Landing feedback is append-only and does not silently mutate weights')""",
                (weight_id, feedback_id, f"natal:{snapshot[1]}:{block_id}"),
            )
            connection.execute(
                "INSERT INTO landing_skill_proposals(id,feedback_id,lesson,status) VALUES(%s,%s,'Pending agent generalization','pending_generation')",
                (proposal_id, feedback_id),
            )
            connection.execute(
                """INSERT INTO landing_draft_edits(
                       request_id,draft_set_id,template_id,base_snapshot_id,block_id,
                       instruction,feedback_id,proposal_id,status
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'queued')""",
                (UUID(request_id), snapshot[0], snapshot[1], UUID(snapshot_id), block_id, normalized, feedback_id, proposal_id),
            )
            for source, relation, target, attributes in (
                (feedback_id, "evaluates", UUID(snapshot_id), {"block_id": block_id}),
                (weight_id, "adjusts", feedback_id, {"delta": 0}),
            ):
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return self.edit(request_id), True

    def edit(self, request_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT request_id,draft_set_id,template_id,base_snapshot_id,block_id,
                          instruction,feedback_id,proposal_id,result_snapshot_id,status,
                          error_code,error_message,created_at,updated_at,completed_at
                   FROM landing_draft_edits WHERE request_id=%s""",
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
            "updated_at": row[13].isoformat(), "completed_at": None if row[14] is None else row[14].isoformat(),
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
            edit = connection.execute(
                """SELECT draft_set_id,template_id,base_snapshot_id,feedback_id,proposal_id,status
                   FROM landing_draft_edits WHERE request_id=%s FOR UPDATE""",
                (UUID(request_id),),
            ).fetchone()
            if edit is None:
                raise KeyError(request_id)
            if edit[5] != "editing":
                raise ValueError("draft edit is not active")
            current = connection.execute(
                "SELECT is_current,snapshot_number FROM landing_draft_snapshots WHERE entity_id=%s FOR UPDATE",
                (edit[2],),
            ).fetchone()
            if current is None or not current[0]:
                raise ValueError("selected landing snapshot became stale")
            connection.execute(
                "UPDATE landing_draft_snapshots SET is_current=false WHERE entity_id=%s", (edit[2],)
            )
            new_id = self._insert_snapshot(
                connection, draft_set_id=edit[0], template_id=edit[1],
                snapshot_number=int(current[1]) + 1, parent_snapshot_id=edit[2],
                feedback_id=edit[3], page_content=page_content, preview_html=preview_html,
                summary=summary, invocation=invocation,
            )
            connection.execute(
                """UPDATE landing_draft_edits SET result_snapshot_id=%s,status='completed',
                       error_code=NULL,error_message=NULL,updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE request_id=%s""",
                (new_id, UUID(request_id)),
            )
            connection.execute(
                "UPDATE landing_skill_proposals SET lesson=%s,status='pending',updated_at=clock_timestamp() WHERE id=%s",
                (lesson[:500], edit[4]),
            )
        return self.edit(request_id)

    def fail_edit(self, request_id: str, *, code: str, message: str) -> dict[str, Any]:
        target_id = UUID(request_id)
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE landing_draft_edits SET status='failed',error_code=%s,error_message=%s,
                       updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE request_id=%s AND status IN ('queued','editing')""",
                (code[:100], message[:2000], target_id),
            ).rowcount
            connection.execute(
                """UPDATE landing_skill_proposals proposal SET status='failed',updated_at=clock_timestamp()
                   FROM landing_draft_edits edit WHERE edit.request_id=%s AND edit.proposal_id=proposal.id
                     AND proposal.status='pending_generation'""",
                (target_id,),
            )
            if changed:
                _audit_failure(
                    connection, action="landing.edit.failed", target_id=target_id,
                    code=code, message=message,
                )
        if not changed:
            raise ValueError("draft edit cannot be failed from its current state")
        return self.edit(request_id)

    def retry_edit(self, request_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            edit = connection.execute(
                "SELECT base_snapshot_id,proposal_id,status FROM landing_draft_edits WHERE request_id=%s FOR UPDATE",
                (UUID(request_id),),
            ).fetchone()
            if edit is None:
                raise KeyError(request_id)
            if edit[2] != "failed":
                raise ValueError("only a failed edit can be retried")
            current = connection.execute(
                "SELECT is_current FROM landing_draft_snapshots WHERE entity_id=%s", (edit[0],)
            ).fetchone()
            if current is None or not current[0]:
                raise ValueError("failed edit base is stale")
            connection.execute(
                """UPDATE landing_draft_edits SET status='queued',error_code=NULL,error_message=NULL,
                       completed_at=NULL,updated_at=clock_timestamp() WHERE request_id=%s""",
                (UUID(request_id),),
            )
            connection.execute(
                "UPDATE landing_skill_proposals SET status='pending_generation',updated_at=clock_timestamp() WHERE id=%s",
                (edit[1],),
            )
        return self.edit(request_id)

    def _edit_status(self, request_id: str, status: str, expected: Sequence[str]) -> None:
        with self.connection() as connection:
            changed = connection.execute(
                "UPDATE landing_draft_edits SET status=%s,updated_at=clock_timestamp() WHERE request_id=%s AND status=ANY(%s)",
                (status, UUID(request_id), list(expected)),
            ).rowcount
        if not changed:
            raise ValueError("invalid draft-edit transition")

    def proposals(self, draft_set_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT DISTINCT proposal.id,proposal.feedback_id,proposal.lesson,proposal.status,
                          proposal.command_session_id,proposal.created_at,proposal.updated_at
                   FROM landing_skill_proposals proposal
                   JOIN commander_human_feedback feedback ON feedback.entity_id=proposal.feedback_id
                   LEFT JOIN landing_draft_edits edit ON edit.proposal_id=proposal.id
                   LEFT JOIN landing_draft_sets edit_draft ON edit_draft.entity_id=edit.draft_set_id
                   LEFT JOIN landing_builds build ON build.entity_id=feedback.target_id
                   WHERE COALESCE(edit_draft.positioning_revision_id,build.positioning_revision_id)=(
                       SELECT positioning_revision_id FROM landing_draft_sets WHERE entity_id=%s
                   ) ORDER BY proposal.created_at DESC""",
                (UUID(draft_set_id),),
            ).fetchall()
        return [self._proposal_row(row) for row in rows]

    def proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id,feedback_id,lesson,status,command_session_id,created_at,updated_at
                   FROM landing_skill_proposals WHERE id=%s""",
                (UUID(proposal_id),),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return self._proposal_row(row)

    @staticmethod
    def _proposal_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "feedback_id": str(row[1]), "lesson": row[2], "status": row[3],
            "command_session_id": None if row[4] is None else str(row[4]),
            "created_at": row[5].isoformat(), "updated_at": row[6].isoformat(),
        }

    def dismiss_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            changed = connection.execute(
                "UPDATE landing_skill_proposals SET status='rejected',updated_at=clock_timestamp() WHERE id=%s AND status='pending'",
                (UUID(proposal_id),),
            ).rowcount
        if not changed:
            raise ValueError("only a pending proposal can be dismissed")
        return self.proposal(proposal_id)

    def mark_proposal_planning(self, proposal_id: str, *, lesson: str, command_session_id: str) -> dict[str, Any]:
        normalized = lesson.strip()
        if not 1 <= len(normalized) <= 500:
            raise ValueError("lesson must contain 1-500 characters")
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE landing_skill_proposals SET lesson=%s,status='planning',command_session_id=%s,
                       updated_at=clock_timestamp() WHERE id=%s AND status='pending'""",
                (normalized, UUID(command_session_id), UUID(proposal_id)),
            ).rowcount
        if not changed:
            raise ValueError("only a pending proposal can be promoted")
        return self.proposal(proposal_id)

    @staticmethod
    def _insert_snapshot(
        connection: Any,
        *,
        draft_set_id: UUID,
        template_id: str,
        snapshot_number: int,
        parent_snapshot_id: UUID | None,
        feedback_id: UUID | None,
        page_content: Mapping[str, Any],
        preview_html: str,
        summary: str,
        invocation: Mapping[str, Any],
    ) -> UUID:
        from psycopg.types.json import Jsonb
        snapshot_id = UUID(new_uuid7())
        digest = _digest(page_content)
        connection.execute(
            "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_draft',%s)",
            (snapshot_id, Jsonb({"template_id": template_id, "snapshot_number": snapshot_number})),
        )
        connection.execute(
            """INSERT INTO landing_draft_snapshots(
                   entity_id,draft_set_id,template_id,snapshot_number,parent_snapshot_id,
                   source_feedback_id,page_content,page_content_sha256,preview_html,summary,invocation,is_current
               ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true)""",
            (snapshot_id, draft_set_id, template_id, snapshot_number, parent_snapshot_id,
             feedback_id, Jsonb(dict(page_content)), digest, preview_html, summary, Jsonb(dict(invocation))),
        )
        connection.execute(
            "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
            (UUID(new_uuid7()), draft_set_id, snapshot_id, Jsonb({"template_id": template_id, "snapshot_number": snapshot_number})),
        )
        if parent_snapshot_id is not None:
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'supersedes',%s,%s)",
                (UUID(new_uuid7()), snapshot_id, parent_snapshot_id, Jsonb({"snapshot_number": snapshot_number})),
            )
        if feedback_id is not None:
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                (UUID(new_uuid7()), snapshot_id, feedback_id, Jsonb({"input": "owner_feedback"})),
            )
        return snapshot_id
