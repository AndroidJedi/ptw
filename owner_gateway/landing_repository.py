"""PostgreSQL authority for Natal landing revisions and skill feedback memory."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID, uuid4


ACTIVE_STATUSES = ("queued", "revising", "building", "publishing")


class LandingBuildRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg

        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "request_id": str(row[1]),
            "idea_run_id": str(row[2]),
            "thesis_id": None if row[3] is None else str(row[3]),
            "template_id": row[4],
            "parent_build_id": None if row[5] is None else str(row[5]),
            "revision_number": int(row[6]),
            "input_brief": row[7],
            "brief": row[8],
            "skill_memory_feedback_ids": [str(item) for item in row[9]],
            "revision_summary": row[10],
            "revision_invocation": row[11],
            "status": row[12],
            "output_path": row[13],
            "build_manifest": row[14],
            "artifact_sha256": row[15],
            "firebase_site_id": row[16],
            "firebase_version": row[17],
            "public_url": row[18],
            "error_code": row[19],
            "error_message": row[20],
            "requested_by": row[21],
            "created_at": row[22].isoformat(),
            "updated_at": row[23].isoformat(),
            "completed_at": None if row[24] is None else row[24].isoformat(),
        }

    @staticmethod
    def _select() -> str:
        return """SELECT entity_id,request_id,source_laval_run_id,source_thesis_id,
                         template_id,parent_build_id,revision_number,input_brief,brief,
                         skill_memory_feedback_ids,revision_summary,revision_invocation,
                         status,output_path,build_manifest,artifact_sha256,firebase_site_id,
                         firebase_version,public_url,error_code,error_message,requested_by,
                         created_at,updated_at,completed_at
                  FROM natal_landing_builds"""

    def get(self, build_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._select() + " WHERE entity_id=%s", (UUID(build_id),)
            ).fetchone()
        if row is None:
            raise KeyError(build_id)
        return self._row(row)

    def by_request(self, request_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                self._select() + " WHERE request_id=%s", (UUID(request_id),)
            ).fetchone()
        return None if row is None else self._row(row)

    def list(self, limit: int = 30, *, idea_run_id: str | None = None) -> list[dict[str, Any]]:
        suffix = ""
        params: list[Any] = []
        if idea_run_id:
            suffix = " WHERE source_laval_run_id=%s"
            params.append(UUID(idea_run_id))
        params.append(min(limit, 100))
        with self.connection() as connection:
            rows = connection.execute(
                self._select() + suffix + " ORDER BY created_at DESC LIMIT %s", params
            ).fetchall()
        return [self._row(row) for row in rows]

    def active(self) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                self._select() + " WHERE status=ANY(%s) ORDER BY created_at LIMIT 1",
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
            return existing, False
        build_id = UUID(str(prepared["build_id"]))
        brief = dict(prepared["brief"])
        run_id = UUID(str(prepared["idea_run_id"]))
        raw_thesis = str((brief.get("source") or {}).get("thesis_id") or "")
        thesis_id = UUID(raw_thesis) if raw_thesis else None
        parent_id = UUID(str(prepared["parent_build_id"])) if prepared.get("parent_build_id") else None
        feedback_ids = [UUID(str(item)) for item in prepared.get("skill_memory_feedback_ids") or []]
        with self.connection() as connection:
            connection.execute("BEGIN")
            if parent_id is not None:
                parent = connection.execute(
                    "SELECT source_laval_run_id,status FROM natal_landing_builds WHERE entity_id=%s",
                    (parent_id,),
                ).fetchone()
                if parent is None or parent[0] != run_id:
                    raise ValueError("parent landing revision must belong to the same Idea evaluation")
                if parent[1] != "published":
                    raise ValueError("only a published landing can be used as a revision parent")
            revision_number = int(connection.execute(
                "SELECT COALESCE(max(revision_number),0)+1 FROM natal_landing_builds WHERE source_laval_run_id=%s",
                (run_id,),
            ).fetchone()[0])
            alias = connection.execute(
                "SELECT entity_id FROM commander_external_aliases WHERE system='idea_laval_run' AND external_id=%s",
                (str(run_id),),
            ).fetchone()
            if alias is None:
                source_id = uuid4()
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'source',%s)",
                    (
                        source_id,
                        Jsonb({
                            "source_type": "idea_laval_evaluation",
                            "idea_run_id": str(run_id),
                            **({"thesis_id": str(thesis_id)} if thesis_id else {}),
                        }),
                    ),
                )
                connection.execute(
                    "INSERT INTO commander_external_aliases(system,external_id,entity_id) VALUES('idea_laval_run',%s,%s)",
                    (str(run_id), source_id),
                )
            else:
                source_id = alias[0]
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing',%s)",
                (
                    build_id,
                    Jsonb({
                        "brand": "Natal", "template_id": prepared["template_id"],
                        "idea_run_id": str(run_id), "revision_number": revision_number,
                    }),
                ),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                (uuid4(), build_id, source_id, Jsonb({"thesis_id": raw_thesis or None})),
            )
            if parent_id is not None:
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'supersedes',%s,%s)",
                    (uuid4(), build_id, parent_id, Jsonb({"revision_number": revision_number})),
                )
            for feedback_id in feedback_ids:
                exists = connection.execute(
                    "SELECT 1 FROM natal_landing_feedback WHERE feedback_id=%s AND source_laval_run_id=%s",
                    (feedback_id, run_id),
                ).fetchone()
                if exists is None:
                    raise ValueError("skill-memory feedback must belong to the same Idea evaluation")
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                    (uuid4(), build_id, feedback_id, Jsonb({"input": "natal_skill_memory"})),
                )
            connection.execute(
                """INSERT INTO natal_landing_builds(
                       entity_id,request_id,source_laval_run_id,source_thesis_id,template_id,
                       parent_build_id,revision_number,input_brief,brief,skill_memory_feedback_ids,
                       status,output_path,firebase_site_id,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s,%s)""",
                (
                    build_id, UUID(request_id), run_id, thesis_id, prepared["template_id"],
                    parent_id, revision_number, Jsonb(brief), Jsonb(brief), feedback_ids,
                    output_path, firebase_site_id, requested_by,
                ),
            )
        return self.get(str(build_id)), True

    def record_feedback(self, build_id: str, *, comment: str, requested_by: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        normalized = comment.strip()
        if not normalized or len(normalized) > 2000:
            raise ValueError("feedback must contain 1-2000 characters")
        feedback_id = uuid4()
        update_id = uuid4()
        with self.connection() as connection:
            connection.execute("BEGIN")
            build = connection.execute(
                """SELECT source_laval_run_id,template_id,status,artifact_sha256,revision_number
                   FROM natal_landing_builds WHERE entity_id=%s FOR SHARE""",
                (UUID(build_id),),
            ).fetchone()
            if build is None:
                raise KeyError(build_id)
            run_id, template_id, status, artifact_sha256, revision_number = build
            if status != "published" or not artifact_sha256:
                raise ValueError("feedback can be recorded only for a published landing revision")
            alias = connection.execute(
                "SELECT entity_id FROM commander_external_aliases WHERE system='natal_landing_template' AND external_id=%s",
                (template_id,),
            ).fetchone()
            if alias is None:
                component_id = uuid4()
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_component',%s)",
                    (component_id, Jsonb({"component_type": "natal_landing_template", "template_id": template_id})),
                )
                connection.execute(
                    "INSERT INTO commander_external_aliases(system,external_id,entity_id) VALUES('natal_landing_template',%s,%s)",
                    (template_id, component_id),
                )
            else:
                component_id = alias[0]
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'human_feedback',%s)",
                (feedback_id, Jsonb({
                    "landing_build_id": build_id, "template_id": template_id,
                    "revision_number": int(revision_number), "comment": normalized,
                    "actor": requested_by, "feedback_type": "natal_landing_skill_memory",
                    "artifact_sha256": artifact_sha256,
                })),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'evaluates',%s,%s)",
                (uuid4(), feedback_id, UUID(build_id), Jsonb({"artifact_sha256": artifact_sha256})),
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'weight_update',%s)",
                (update_id, Jsonb({
                    "component_id": str(component_id), "previous_weight": 0.5,
                    "delta": 0.0, "new_weight": 0.5,
                    "algorithm": "owner_text_feedback_v1", "rating": None,
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
            created_at = connection.execute(
                """INSERT INTO natal_landing_feedback(
                       feedback_id,landing_build_id,source_laval_run_id,template_id,
                       comment,artifact_sha256,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING created_at""",
                (feedback_id, UUID(build_id), run_id, template_id, normalized, artifact_sha256, requested_by),
            ).fetchone()[0]
        return {
            "id": str(feedback_id), "build_id": build_id, "idea_run_id": str(run_id),
            "template_id": template_id, "revision_number": int(revision_number),
            "comment": normalized, "weight_update_id": str(update_id),
            "created_at": created_at.isoformat(),
        }

    def skill_memory(self, idea_run_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT memory.feedback_id,memory.landing_build_id,memory.template_id,
                          memory.revision_number,memory.comment,memory.created_at
                   FROM (
                     SELECT feedback.feedback_id,feedback.landing_build_id,feedback.template_id,
                            build.revision_number,feedback.comment,feedback.created_at
                     FROM natal_landing_feedback feedback
                     JOIN natal_landing_builds build ON build.entity_id=feedback.landing_build_id
                     WHERE feedback.source_laval_run_id=%s
                     ORDER BY feedback.created_at DESC,feedback.feedback_id DESC LIMIT %s
                   ) memory
                   ORDER BY memory.created_at,memory.feedback_id""",
                (UUID(idea_run_id), min(limit, 100)),
            ).fetchall()
        return [
            {
                "id": str(row[0]), "build_id": str(row[1]), "template_id": row[2],
                "revision_number": int(row[3]), "comment": row[4], "created_at": row[5].isoformat(),
            }
            for row in rows
        ]

    def _transition(
        self,
        build_id: str,
        expected: Sequence[str],
        status: str,
        *,
        complete: bool = False,
        clear_completed: bool = False,
        **values: Any,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        allowed = {
            "brief", "revision_summary", "revision_invocation", "build_manifest",
            "artifact_sha256", "firebase_version", "public_url", "error_code", "error_message",
        }
        if not set(values).issubset(allowed):
            raise ValueError("invalid landing build update")
        normalized = {
            key: Jsonb(value) if key in {"brief", "revision_invocation", "build_manifest"} and value is not None else value
            for key, value in values.items()
        }
        assignments = ["status=%s", "updated_at=clock_timestamp()"] + [f"{key}=%s" for key in normalized]
        if complete:
            assignments.append("completed_at=clock_timestamp()")
        elif clear_completed:
            assignments.append("completed_at=NULL")
        params = [status, *normalized.values(), UUID(build_id), list(expected)]
        with self.connection() as connection:
            row = connection.execute(
                f"UPDATE natal_landing_builds SET {','.join(assignments)} WHERE entity_id=%s AND status=ANY(%s) RETURNING entity_id",
                params,
            ).fetchone()
        if row is None:
            raise ValueError(f"landing build {build_id} cannot transition to {status}")
        return self.get(build_id)

    def mark_revising(self, build_id: str) -> dict[str, Any]:
        return self._transition(build_id, ("queued",), "revising", error_code=None, error_message=None)

    def mark_building(
        self,
        build_id: str,
        *,
        brief: Mapping[str, Any] | None = None,
        summary: str | None = None,
        invocation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        values: dict[str, Any] = {"error_code": None, "error_message": None}
        if brief is not None:
            values.update(brief=dict(brief), revision_summary=summary, revision_invocation=dict(invocation or {}))
        return self._transition(build_id, ("queued", "revising"), "building", **values)

    def mark_publishing(
        self, build_id: str, *, manifest: Mapping[str, Any], artifact_sha256: str
    ) -> dict[str, Any]:
        return self._transition(
            build_id, ("building",), "publishing",
            build_manifest=dict(manifest), artifact_sha256=artifact_sha256,
        )

    def mark_published(self, build_id: str, *, version: str, public_url: str) -> dict[str, Any]:
        return self._transition(
            build_id, ("publishing",), "published",
            firebase_version=version, public_url=public_url, complete=True,
        )

    def refresh_publication(
        self, build_id: str, *, version: str, public_url: str
    ) -> dict[str, Any]:
        return self._transition(
            build_id, ("published",), "published",
            firebase_version=version, public_url=public_url,
        )

    def mark_failed(self, build_id: str, *, code: str, message: str) -> dict[str, Any]:
        return self._transition(
            build_id, ACTIVE_STATUSES, "failed",
            error_code=code[:120], error_message=message[:1000], complete=True,
        )

    def retry(self, build_id: str) -> dict[str, Any]:
        return self._transition(
            build_id, ("failed",), "queued",
            error_code=None, error_message=None, clear_completed=True,
        )

    def recover_interrupted(self) -> int:
        with self.connection() as connection:
            cursor = connection.execute(
                """UPDATE natal_landing_builds
                   SET status='failed',error_code='gateway_restarted',
                       error_message='Owner Gateway restarted during build; retry is safe',
                       updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE status IN ('queued','revising','building','publishing')"""
            )
            recovered = cursor.rowcount
        return recovered

    def published(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                self._select() + " WHERE status='published' ORDER BY created_at DESC",
            ).fetchall()
        return [self._row(row) for row in rows]
