"""PostgreSQL authority for exact-snapshot Natal publications."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7


ACTIVE_STATUSES = ("queued", "building", "publishing")


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


class LandingBuildRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _select() -> str:
        return """SELECT build.entity_id,build.request_id,build.positioning_project_id,
                         build.positioning_revision_id,build.source_snapshot_id,build.template_id,
                         draft.source_brief,build.page_content,build.page_content_sha256,
                         build.output_path,build.build_manifest,build.artifact_sha256,
                         build.firebase_site_id,build.firebase_version,build.public_url,build.status,
                         build.error_code,build.error_message,build.requested_by,build.created_at,
                         build.updated_at,build.completed_at
                  FROM landing_builds build
                  JOIN landing_draft_snapshots snapshot ON snapshot.entity_id=build.source_snapshot_id
                  JOIN landing_draft_sets draft ON draft.entity_id=snapshot.draft_set_id"""

    @staticmethod
    def _row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "request_id": str(row[1]),
            "positioning_project_id": str(row[2]), "positioning_revision_id": str(row[3]),
            "source_draft_snapshot_id": str(row[4]), "template_id": row[5],
            "brief": row[6], "page_content": row[7], "page_content_sha256": row[8],
            "output_path": row[9], "build_manifest": row[10], "artifact_sha256": row[11],
            "firebase_site_id": row[12], "firebase_version": row[13], "public_url": row[14],
            "status": row[15], "error_code": row[16], "error_message": row[17],
            "requested_by": row[18], "created_at": row[19].isoformat(),
            "updated_at": row[20].isoformat(), "completed_at": None if row[21] is None else row[21].isoformat(),
        }

    def get(self, build_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(self._select() + " WHERE build.entity_id=%s", (UUID(build_id),)).fetchone()
        if row is None:
            raise KeyError(build_id)
        return self._row(row)

    def by_request(self, request_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(self._select() + " WHERE build.request_id=%s", (UUID(request_id),)).fetchone()
        return None if row is None else self._row(row)

    def list(self, limit: int = 30, *, positioning_revision_id: str | None = None) -> list[dict[str, Any]]:
        suffix, params = "", []
        if positioning_revision_id:
            suffix = " WHERE build.positioning_revision_id=%s"
            params.append(UUID(positioning_revision_id))
        params.append(min(limit, 100))
        with self.connection() as connection:
            rows = connection.execute(self._select() + suffix + " ORDER BY build.created_at DESC LIMIT %s", params).fetchall()
        return [self._row(row) for row in rows]

    def active(self) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                self._select() + " WHERE build.status=ANY(%s) ORDER BY build.created_at LIMIT 1",
                (list(ACTIVE_STATUSES),),
            ).fetchone()
        return None if row is None else self._row(row)

    def create(
        self,
        prepared: Mapping[str, Any],
        *,
        request_id: str,
        requested_by: str,
        output_path: str,
        firebase_site_id: str,
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        existing = self.by_request(request_id)
        if existing is not None:
            if existing["source_draft_snapshot_id"] != str(prepared["source_draft_snapshot_id"]):
                raise ValueError("request_id was already used for another Landing snapshot")
            return existing, False
        build_id = UUID(str(prepared["build_id"]))
        project_id = UUID(str(prepared["positioning_project_id"]))
        revision_id = UUID(str(prepared["positioning_revision_id"]))
        snapshot_id = UUID(str(prepared["source_draft_snapshot_id"]))
        with self.connection() as connection:
            row = connection.execute(
                """SELECT snapshot.template_id,snapshot.page_content,snapshot.page_content_sha256,
                          snapshot.is_current,draft.positioning_project_id,draft.positioning_revision_id
                   FROM landing_draft_snapshots snapshot
                   JOIN landing_draft_sets draft ON draft.entity_id=snapshot.draft_set_id
                   WHERE snapshot.entity_id=%s FOR SHARE""",
                (snapshot_id,),
            ).fetchone()
            if row is None or not row[3]:
                raise ValueError("publication requires a current Landing snapshot")
            if (
                row[0] != prepared["template_id"] or row[4] != project_id or row[5] != revision_id
                or row[2] != prepared["page_content_sha256"] or row[1] != prepared["page_content"]
            ):
                raise ValueError("selected snapshot content or positioning lineage does not match")
            approved = connection.execute(
                """SELECT 1 FROM positioning_approvals
                   WHERE project_id=%s AND revision_id=%s AND revoked_at IS NULL""",
                (project_id, revision_id),
            ).fetchone()
            if approved is None:
                raise ValueError("publication requires the active approved positioning revision")
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing',%s)",
                (build_id, Jsonb({"brand": "Natal", "template_id": row[0]})),
            )
            connection.execute(
                """INSERT INTO landing_builds(
                       entity_id,request_id,positioning_project_id,positioning_revision_id,
                       source_snapshot_id,template_id,page_content,page_content_sha256,
                       output_path,firebase_site_id,status,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued',%s)""",
                (build_id, UUID(request_id), project_id, revision_id, snapshot_id, row[0],
                 Jsonb(dict(row[1])), row[2], output_path, firebase_site_id, requested_by),
            )
            for target, attributes in (
                (snapshot_id, {"input": "exact_snapshot"}),
                (revision_id, {"input": "approved_positioning"}),
            ):
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                    (UUID(new_uuid7()), build_id, target, Jsonb(attributes)),
                )
        return self.get(str(build_id)), True

    def record_feedback(self, build_id: str, *, comment: str, requested_by: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        normalized = comment.strip()
        if not 1 <= len(normalized) <= 2000:
            raise ValueError("feedback must contain 1-2000 characters")
        feedback_id, weight_id, proposal_id = (UUID(new_uuid7()) for _ in range(3))
        with self.connection() as connection:
            build = connection.execute(
                "SELECT status,template_id FROM landing_builds WHERE entity_id=%s FOR SHARE", (UUID(build_id),)
            ).fetchone()
            if build is None:
                raise KeyError(build_id)
            if build[0] != "published":
                raise ValueError("feedback requires a published Landing")
            for entity_id, kind, attributes in (
                (feedback_id, "human_feedback", {"domain": "landing", "section_id": "published_page"}),
                (weight_id, "weight_update", {"delta": 0}),
            ):
                connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)", (entity_id, kind, Jsonb(attributes)))
            connection.execute(
                """INSERT INTO commander_human_feedback(entity_id,target_id,domain,section_id,instruction,actor)
                   VALUES(%s,%s,'landing','published_page',%s,%s)""",
                (feedback_id, UUID(build_id), normalized, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,%s,0,'Published Landing feedback is append-only')""",
                (weight_id, feedback_id, f"natal:{build[1]}:published_page"),
            )
            connection.execute(
                "INSERT INTO landing_skill_proposals(id,feedback_id,lesson,status) VALUES(%s,%s,%s,'pending')",
                (proposal_id, feedback_id, f"Apply this owner preference when relevant: {normalized}"[:500]),
            )
            for source, relation, target in (
                (feedback_id, "evaluates", UUID(build_id)), (weight_id, "adjusts", feedback_id),
            ):
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb({"delta": 0} if relation == "adjusts" else {})),
                )
        return {"id": str(feedback_id), "weight_update_id": str(weight_id), "proposal_id": str(proposal_id)}

    def skill_memory(self, positioning_revision_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT feedback.entity_id,feedback.section_id,feedback.instruction,feedback.target_id,
                          feedback.created_at,COALESCE(snapshot.template_id,build.template_id),
                          COALESCE(snapshot.snapshot_number,0)
                   FROM commander_human_feedback feedback
                   LEFT JOIN landing_draft_snapshots snapshot ON snapshot.entity_id=feedback.target_id
                   LEFT JOIN landing_draft_sets draft ON draft.entity_id=snapshot.draft_set_id
                   LEFT JOIN landing_builds build ON build.entity_id=feedback.target_id
                   WHERE feedback.domain='landing'
                     AND COALESCE(draft.positioning_revision_id,build.positioning_revision_id)=%s
                   ORDER BY feedback.created_at LIMIT %s""",
                (UUID(positioning_revision_id), min(limit, 100)),
            ).fetchall()
        return [{
            "id": str(row[0]), "block_id": row[1], "comment": row[2], "target_id": str(row[3]),
            "created_at": row[4].isoformat(), "template_id": row[5], "revision_number": int(row[6]),
        } for row in rows]

    def mark_building(self, build_id: str) -> dict[str, Any]:
        self._transition(build_id, "building", ("queued",))
        return self.get(build_id)

    def mark_publishing(self, build_id: str, *, manifest: Mapping[str, Any], artifact_sha256: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        self._transition(build_id, "publishing", ("building",), values={"build_manifest": Jsonb(dict(manifest)), "artifact_sha256": artifact_sha256})
        return self.get(build_id)

    def mark_published(self, build_id: str, *, version: str, public_url: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            build = connection.execute(
                "SELECT positioning_revision_id,source_snapshot_id,status FROM landing_builds WHERE entity_id=%s FOR UPDATE",
                (UUID(build_id),),
            ).fetchone()
            if build is None:
                raise KeyError(build_id)
            if build[2] != "publishing":
                raise ValueError("Landing is not ready to publish")
            connection.execute(
                """UPDATE landing_builds SET status='published',firebase_version=%s,public_url=%s,
                       error_code=NULL,error_message=NULL,updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE entity_id=%s""",
                (version, public_url, UUID(build_id)),
            )
            connection.execute(
                """INSERT INTO landing_publications(
                       id,build_id,positioning_revision_id,snapshot_id,firebase_version,public_url
                   ) VALUES(%s,%s,%s,%s,%s,%s)""",
                (UUID(new_uuid7()), UUID(build_id), build[0], build[1], version, public_url),
            )
        return self.get(build_id)

    def mark_failed(self, build_id: str, *, code: str, message: str) -> dict[str, Any]:
        target_id = UUID(build_id)
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE landing_builds SET status='failed',error_code=%s,error_message=%s,
                       updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE entity_id=%s AND status=ANY(%s)""",
                (code[:100], message[:2000], target_id, list(ACTIVE_STATUSES)),
            ).rowcount
            if changed:
                _audit_failure(
                    connection, action="landing.publication.failed", target_id=target_id,
                    code=code, message=message,
                )
        if not changed:
            raise ValueError("Landing cannot fail from its current state")
        return self.get(build_id)

    def retry(self, build_id: str) -> dict[str, Any]:
        self._transition(build_id, "queued", ("failed",), clear=True)
        return self.get(build_id)

    def recover_interrupted(self) -> int:
        with self.connection() as connection:
            interrupted = [row[0] for row in connection.execute(
                "SELECT entity_id FROM landing_builds WHERE status=ANY(%s) FOR UPDATE",
                (list(ACTIVE_STATUSES),),
            ).fetchall()]
            connection.execute(
                """UPDATE landing_builds SET status='failed',error_code='InterruptedError',
                       error_message='gateway restarted during publication',updated_at=clock_timestamp(),
                       completed_at=clock_timestamp() WHERE status=ANY(%s)""",
                (list(ACTIVE_STATUSES),),
            )
            for target_id in interrupted:
                _audit_failure(
                    connection, action="landing.publication.failed", target_id=target_id,
                    code="InterruptedError", message="gateway restarted during publication",
                )
        return len(interrupted)

    def published(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(self._select() + " WHERE build.status='published' ORDER BY build.completed_at").fetchall()
        return [self._row(row) for row in rows]

    def _transition(
        self, build_id: str, status: str, expected: Sequence[str], *,
        values: Mapping[str, Any] | None = None, clear: bool = False,
    ) -> None:
        values = dict(values or {})
        assignments = ["status=%s", "updated_at=clock_timestamp()"]
        params: list[Any] = [status]
        for key, value in values.items():
            if key not in {"build_manifest", "artifact_sha256"}:
                raise ValueError("unsupported Landing transition value")
            assignments.append(f"{key}=%s")
            params.append(value)
        if clear:
            assignments += ["error_code=NULL", "error_message=NULL", "completed_at=NULL"]
        params += [UUID(build_id), list(expected)]
        with self.connection() as connection:
            changed = connection.execute(
                f"UPDATE landing_builds SET {','.join(assignments)} WHERE entity_id=%s AND status=ANY(%s)", params
            ).rowcount
        if not changed:
            raise ValueError("invalid Landing transition")
