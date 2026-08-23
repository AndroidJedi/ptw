"""PostgreSQL authority for immutable Marketing Positioning projects and revisions."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7


def _json_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class PositioningRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            yield connection

    @staticmethod
    def _project_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "request_id": str(row[1]),
            "owner_idea_source_id": str(row[2]), "raw_idea": row[3],
            "target_country": row[4], "research_language": row[5],
            "output_language": row[6], "requested_by": row[7],
            "created_at": row[8].isoformat(), "updated_at": row[9].isoformat(),
        }

    @staticmethod
    def _revision_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "project_id": str(row[1]), "request_id": str(row[2]),
            "revision_number": int(row[3]),
            "base_revision_id": None if row[4] is None else str(row[4]),
            "feedback_id": None if row[5] is None else str(row[5]),
            "status": row[6], "document": row[7], "document_sha256": row[8],
            "quality_gates": row[9], "failure_count": int(row[10]),
            "error_code": row[11], "error_message": row[12], "requested_by": row[13],
            "created_at": row[14].isoformat(), "updated_at": row[15].isoformat(),
            "completed_at": None if row[16] is None else row[16].isoformat(),
            "approved": bool(row[17]),
        }

    @staticmethod
    def _project_select() -> str:
        return """SELECT project.entity_id,project.request_id,project.owner_idea_source_id,
                         source.content,project.target_country,project.research_language,
                         project.output_language,project.requested_by,project.created_at,project.updated_at
                  FROM positioning_projects project
                  JOIN commander_sources source ON source.entity_id=project.owner_idea_source_id"""

    @staticmethod
    def _revision_select() -> str:
        return """SELECT revision.entity_id,revision.project_id,revision.request_id,
                         revision.revision_number,revision.base_revision_id,revision.feedback_id,
                         revision.status,revision.document,revision.document_sha256,
                         revision.quality_gates,revision.failure_count,revision.error_code,
                         revision.error_message,revision.requested_by,revision.created_at,
                         revision.updated_at,revision.completed_at,
                         EXISTS(SELECT 1 FROM positioning_approvals approval
                                WHERE approval.revision_id=revision.entity_id AND approval.revoked_at IS NULL)
                  FROM positioning_revisions revision"""

    def create_project(
        self,
        *,
        request_id: str,
        raw_idea: str,
        target_country: str,
        research_language: str,
        output_language: str,
        requested_by: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        request_uuid = UUID(request_id)
        normalized_idea = raw_idea.strip()
        idea_digest = hashlib.sha256(normalized_idea.encode()).hexdigest()
        with self.connection() as connection:
            existing = connection.execute(
                self._project_select() + " WHERE project.request_id=%s", (request_uuid,)
            ).fetchone()
            if existing is not None:
                project = self._project_row(existing)
                if (
                    project["raw_idea"] != normalized_idea
                    or project["target_country"] != target_country
                    or project["research_language"] != research_language
                    or project["output_language"] != output_language
                ):
                    raise ValueError("request_id was already used with different positioning input")
                revision = connection.execute(
                    self._revision_select() + " WHERE revision.project_id=%s ORDER BY revision.revision_number LIMIT 1",
                    (UUID(project["id"]),),
                ).fetchone()
                return project, self._revision_row(revision), False

            project_id = UUID(new_uuid7())
            source_id = UUID(new_uuid7())
            revision_id = UUID(new_uuid7())
            source_digest = hashlib.sha256(normalized_idea.encode()).hexdigest()
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'source',%s)",
                (source_id, Jsonb({"source_type": "owner_idea"})),
            )
            connection.execute(
                """INSERT INTO commander_sources(
                       entity_id,source_type,title,content,country_code,language_code,
                       provider,content_sha256,metadata
                   ) VALUES(%s,'owner_idea','Owner idea',%s,%s,%s,'owner',%s,%s)""",
                (source_id, normalized_idea, target_country, research_language, source_digest, Jsonb({})),
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'positioning_project',%s)",
                (project_id, Jsonb({"target_country": target_country, "output_language": output_language})),
            )
            connection.execute(
                """INSERT INTO positioning_projects(
                       entity_id,request_id,owner_idea_source_id,idea_sha256,target_country,
                       research_language,output_language,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (project_id, request_uuid, source_id, idea_digest, target_country, research_language, output_language, requested_by),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                (UUID(new_uuid7()), project_id, source_id, Jsonb({"input": "owner_idea"})),
            )
            connection.execute(
                "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'marketing_positioning',%s)",
                (revision_id, Jsonb({"revision_number": 1})),
            )
            connection.execute(
                """INSERT INTO positioning_revisions(
                       entity_id,project_id,request_id,revision_number,status,requested_by
                   ) VALUES(%s,%s,%s,1,'queued',%s)""",
                (revision_id, project_id, request_uuid, requested_by),
            )
            connection.execute(
                "INSERT INTO positioning_revision_sources(revision_id,source_id,citation_order) VALUES(%s,%s,0)",
                (revision_id, source_id),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                (UUID(new_uuid7()), revision_id, source_id, Jsonb({"citation_order": 0})),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'contains',%s,%s)",
                (UUID(new_uuid7()), project_id, revision_id, Jsonb({"revision_number": 1})),
            )
        return self.get_project(str(project_id)), self.get_revision(str(revision_id)), True

    def create_revision(
        self,
        *,
        project_id: str,
        request_id: str,
        base_revision_id: str,
        section_id: str,
        instruction: str,
        requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb

        request_uuid = UUID(request_id)
        with self.connection() as connection:
            existing = connection.execute(
                self._revision_select() + " WHERE revision.request_id=%s", (request_uuid,)
            ).fetchone()
            if existing is not None:
                item = self._revision_row(existing)
                if item["project_id"] != project_id or item["base_revision_id"] != base_revision_id:
                    raise ValueError("request_id was already used for another revision")
                return item, False
            base = connection.execute(
                """SELECT revision_number,status,document FROM positioning_revisions
                   WHERE entity_id=%s AND project_id=%s FOR SHARE""",
                (UUID(base_revision_id), UUID(project_id)),
            ).fetchone()
            if base is None:
                raise KeyError(base_revision_id)
            if base[1] != "completed" or base[2] is None:
                raise ValueError("only a completed positioning can be corrected")
            revision_number = int(connection.execute(
                "SELECT COALESCE(max(revision_number),0)+1 FROM positioning_revisions WHERE project_id=%s",
                (UUID(project_id),),
            ).fetchone()[0])
            feedback_id = UUID(new_uuid7())
            weight_id = UUID(new_uuid7())
            proposal_id = UUID(new_uuid7())
            revision_id = UUID(new_uuid7())
            for entity_id, kind, attributes in (
                (feedback_id, "human_feedback", {"domain": "marketing_positioning", "section_id": section_id}),
                (weight_id, "weight_update", {"delta": 0}),
                (revision_id, "marketing_positioning", {"revision_number": revision_number}),
            ):
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,%s)",
                    (entity_id, kind, Jsonb(attributes)),
                )
            connection.execute(
                """INSERT INTO commander_human_feedback(entity_id,target_id,domain,section_id,instruction,actor)
                   VALUES(%s,%s,'marketing_positioning',%s,%s,%s)""",
                (feedback_id, UUID(base_revision_id), section_id, instruction, requested_by),
            )
            connection.execute(
                """INSERT INTO commander_weight_updates(entity_id,feedback_id,component,delta,reason)
                   VALUES(%s,%s,%s,0,'Owner correction is recorded without silently changing learned weights')""",
                (weight_id, feedback_id, section_id),
            )
            connection.execute(
                """INSERT INTO positioning_revisions(
                       entity_id,project_id,request_id,revision_number,base_revision_id,
                       feedback_id,status,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,'queued',%s)""",
                (revision_id, UUID(project_id), request_uuid, revision_number, UUID(base_revision_id), feedback_id, requested_by),
            )
            lesson = f"When revising {section_id}, apply this owner preference when relevant: {instruction}"[:500]
            connection.execute(
                "INSERT INTO positioning_skill_proposals(id,feedback_id,revision_id,lesson,status) VALUES(%s,%s,%s,%s,'pending')",
                (proposal_id, feedback_id, revision_id, lesson),
            )
            sources = connection.execute(
                "SELECT source_id,citation_order FROM positioning_revision_sources WHERE revision_id=%s ORDER BY citation_order",
                (UUID(base_revision_id),),
            ).fetchall()
            for source_id, order in sources:
                connection.execute(
                    "INSERT INTO positioning_revision_sources(revision_id,source_id,citation_order) VALUES(%s,%s,%s)",
                    (revision_id, source_id, order),
                )
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                    (UUID(new_uuid7()), revision_id, source_id, Jsonb({"citation_order": order})),
                )
            for source, relation, target, attributes in (
                (feedback_id, "evaluates", UUID(base_revision_id), {"section_id": section_id}),
                (weight_id, "adjusts", feedback_id, {"delta": 0}),
                (revision_id, "supersedes", UUID(base_revision_id), {"revision_number": revision_number}),
                (revision_id, "derived_from", feedback_id, {"input": "owner_feedback"}),
                (UUID(project_id), "contains", revision_id, {"revision_number": revision_number}),
            ):
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)",
                    (UUID(new_uuid7()), source, relation, target, Jsonb(attributes)),
                )
        return self.get_revision(str(revision_id)), True

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._project_select() + " WHERE project.entity_id=%s", (UUID(project_id),)
            ).fetchone()
            if row is None:
                raise KeyError(project_id)
            project = self._project_row(row)
            revisions = connection.execute(
                self._revision_select() + " WHERE revision.project_id=%s ORDER BY revision.revision_number DESC",
                (UUID(project_id),),
            ).fetchall()
            sources = connection.execute(
                """SELECT source.entity_id,source.source_type,source.title,source.source_uri,
                          source.publisher,source.content,source.country_code,source.language_code,
                          source.provider,source.external_id,source.content_sha256,source.metadata,source.created_at
                   FROM commander_sources source
                   WHERE source.entity_id IN (
                       SELECT source_id FROM positioning_revision_sources revision_source
                       JOIN positioning_revisions revision ON revision.entity_id=revision_source.revision_id
                       WHERE revision.project_id=%s
                   ) ORDER BY source.created_at""",
                (UUID(project_id),),
            ).fetchall()
        project["revisions"] = [self._revision_row(item) for item in revisions]
        project["active_approved_revision_id"] = next(
            (item["id"] for item in project["revisions"] if item["approved"]), None
        )
        project["sources"] = [self._source_row(item) for item in sources]
        return project

    def list_projects(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                self._project_select() + " ORDER BY project.created_at DESC LIMIT %s", (min(limit, 100),)
            ).fetchall()
            approved = {
                str(row[0]): str(row[1])
                for row in connection.execute(
                    "SELECT project_id,revision_id FROM positioning_approvals WHERE revoked_at IS NULL"
                ).fetchall()
            }
            latest = {
                str(row[0]): (str(row[1]), row[2])
                for row in connection.execute(
                    """SELECT DISTINCT ON (project_id) project_id,entity_id,status
                       FROM positioning_revisions ORDER BY project_id,revision_number DESC"""
                ).fetchall()
            }
        result = []
        for row in rows:
            item = self._project_row(row)
            item["active_approved_revision_id"] = approved.get(item["id"])
            item["latest_revision_id"], item["latest_revision_status"] = latest[item["id"]]
            result.append(item)
        return result

    def get_revision(self, revision_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                self._revision_select() + " WHERE revision.entity_id=%s", (UUID(revision_id),)
            ).fetchone()
        if row is None:
            raise KeyError(revision_id)
        return self._revision_row(row)

    def queue_retry(self, revision_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE positioning_revisions SET status='queued',error_code=NULL,error_message=NULL,
                          updated_at=clock_timestamp() WHERE entity_id=%s AND status='failed'""",
                (UUID(revision_id),),
            ).rowcount
        if not changed:
            raise ValueError("only a failed revision can be retried")
        return self.get_revision(revision_id)

    def source_ids(self, revision_id: str) -> list[str]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT source_id FROM positioning_revision_sources WHERE revision_id=%s ORDER BY citation_order",
                (UUID(revision_id),),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def sources(self, revision_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT source.entity_id,source.source_type,source.title,source.source_uri,
                          source.publisher,source.content,source.country_code,source.language_code,
                          source.provider,source.external_id,source.content_sha256,source.metadata,source.created_at
                   FROM commander_sources source
                   JOIN positioning_revision_sources link ON link.source_id=source.entity_id
                   WHERE link.revision_id=%s ORDER BY link.citation_order""",
                (UUID(revision_id),),
            ).fetchall()
        return [self._source_row(row) for row in rows]

    @staticmethod
    def _source_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "source_type": row[1], "title": row[2], "source_uri": row[3],
            "publisher": row[4], "content": row[5], "country_code": row[6],
            "language_code": row[7], "provider": row[8], "external_id": row[9],
            "content_sha256": row[10], "metadata": row[11], "created_at": row[12].isoformat(),
        }

    def add_research_source(
        self,
        revision_id: str,
        *,
        title: str,
        uri: str,
        publisher: str,
        content: str,
        country: str,
        language: str,
        provider: str,
        external_id: str,
        metadata: Mapping[str, Any],
    ) -> str:
        from psycopg.types.json import Jsonb

        digest = hashlib.sha256(content.encode()).hexdigest()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT entity_id FROM commander_sources WHERE provider=%s AND external_id=%s",
                (provider, external_id),
            ).fetchone()
            source_id = row[0] if row is not None else UUID(new_uuid7())
            if row is None:
                connection.execute(
                    "INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'source',%s)",
                    (source_id, Jsonb({"source_type": "research_finding"})),
                )
                connection.execute(
                    """INSERT INTO commander_sources(
                           entity_id,source_type,title,source_uri,publisher,content,country_code,
                           language_code,provider,external_id,content_sha256,metadata
                       ) VALUES(%s,'research_finding',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (source_id, title, uri, publisher, content, country, language, provider, external_id, digest, Jsonb(dict(metadata))),
                )
            linked = connection.execute(
                "SELECT 1 FROM positioning_revision_sources WHERE revision_id=%s AND source_id=%s",
                (UUID(revision_id), source_id),
            ).fetchone()
            if linked is None:
                order = int(connection.execute(
                    "SELECT COALESCE(max(citation_order),-1)+1 FROM positioning_revision_sources WHERE revision_id=%s",
                    (UUID(revision_id),),
                ).fetchone()[0])
                connection.execute(
                    "INSERT INTO positioning_revision_sources(revision_id,source_id,citation_order) VALUES(%s,%s,%s)",
                    (UUID(revision_id), source_id, order),
                )
                connection.execute(
                    "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                    (UUID(new_uuid7()), UUID(revision_id), source_id, Jsonb({"citation_order": order})),
                )
        return str(source_id)

    def start_attempt(self, revision_id: str) -> tuple[str, int]:
        attempt_id = UUID(new_uuid7())
        with self.connection() as connection:
            number = int(connection.execute(
                "SELECT COALESCE(max(attempt_number),0)+1 FROM positioning_generation_attempts WHERE revision_id=%s",
                (UUID(revision_id),),
            ).fetchone()[0])
            connection.execute(
                "INSERT INTO positioning_generation_attempts(id,revision_id,attempt_number,status) VALUES(%s,%s,%s,'started')",
                (attempt_id, UUID(revision_id), number),
            )
            connection.execute(
                """UPDATE positioning_revisions
                   SET status='synthesizing',error_code=NULL,error_message=NULL,
                       updated_at=clock_timestamp()
                   WHERE entity_id=%s""",
                (UUID(revision_id),),
            )
        return str(attempt_id), number

    def finish_attempt(self, revision_id: str, attempt_id: str, document: Mapping[str, Any], digest: str, gates: Mapping[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute(
                "UPDATE positioning_generation_attempts SET status='completed',completed_at=clock_timestamp() WHERE id=%s",
                (UUID(attempt_id),),
            )
            connection.execute(
                """UPDATE positioning_revisions SET status='completed',document=%s,document_sha256=%s,
                       quality_gates=%s,error_code=NULL,error_message=NULL,updated_at=clock_timestamp(),
                       completed_at=clock_timestamp() WHERE entity_id=%s""",
                (Jsonb(dict(document)), digest, Jsonb(dict(gates)), UUID(revision_id)),
            )

    def fail_attempt(self, revision_id: str, attempt_id: str, error: Exception) -> None:
        code = type(error).__name__
        message = str(error)[:2000] or code
        with self.connection() as connection:
            connection.execute(
                """UPDATE positioning_generation_attempts SET status='failed',error_code=%s,
                       error_message=%s,completed_at=clock_timestamp() WHERE id=%s""",
                (code, message, UUID(attempt_id)),
            )
            connection.execute(
                """UPDATE positioning_revisions SET status='failed',failure_count=failure_count+1,
                       error_code=%s,error_message=%s,updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE entity_id=%s""",
                (code, message, UUID(revision_id)),
            )

    def generation_attempt(self, attempt_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id,revision_id,attempt_number,status,error_code,error_message,
                          started_at,completed_at
                   FROM positioning_generation_attempts WHERE id=%s""",
                (UUID(attempt_id),),
            ).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return {
            "id": str(row[0]), "revision_id": str(row[1]),
            "attempt_number": int(row[2]), "status": row[3],
            "error_code": row[4], "error_message": row[5],
            "started_at": row[6].isoformat(),
            "completed_at": None if row[7] is None else row[7].isoformat(),
        }

    def invocation(self, idempotency_key: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id,revision_id,attempt_id,provider,mode,idempotency_key,remote_task_id,
                          request_sha256,response_sha256,status,invocation,created_at,completed_at
                   FROM positioning_provider_invocations WHERE idempotency_key=%s""",
                (idempotency_key,),
            ).fetchone()
        return None if row is None else self._invocation_row(row)

    @staticmethod
    def _invocation_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "revision_id": str(row[1]), "attempt_id": str(row[2]),
            "provider": row[3], "mode": row[4], "idempotency_key": row[5],
            "remote_task_id": row[6], "request_sha256": row[7], "response_sha256": row[8],
            "status": row[9], "invocation": row[10], "created_at": row[11].isoformat(),
            "completed_at": None if row[12] is None else row[12].isoformat(),
        }

    def create_invocation(
        self,
        *,
        revision_id: str,
        attempt_id: str,
        provider: str,
        mode: str,
        idempotency_key: str,
        request: Mapping[str, Any],
        remote_task_id: str | None = None,
        invocation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        existing = self.invocation(idempotency_key)
        if existing is not None:
            return existing
        invocation_id = UUID(new_uuid7())
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO positioning_provider_invocations(
                       id,revision_id,attempt_id,provider,mode,idempotency_key,remote_task_id,
                       request_sha256,status,invocation
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'submitted',%s)""",
                (invocation_id, UUID(revision_id), UUID(attempt_id), provider, mode, idempotency_key,
                 remote_task_id, _json_sha(request), Jsonb(dict(invocation or {}))),
            )
        return self.invocation(idempotency_key) or {}

    def attach_remote_task(self, invocation_id: str, remote_task_id: str, cost: float, provider_record: Mapping[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute(
                "UPDATE positioning_provider_invocations SET remote_task_id=%s WHERE id=%s AND remote_task_id IS NULL",
                (remote_task_id, UUID(invocation_id)),
            )
            exists = connection.execute(
                "SELECT 1 FROM positioning_provider_costs WHERE invocation_id=%s", (UUID(invocation_id),)
            ).fetchone()
            if exists is None:
                connection.execute(
                    "INSERT INTO positioning_provider_costs(id,invocation_id,amount_usd,provider_record) VALUES(%s,%s,%s,%s)",
                    (UUID(new_uuid7()), UUID(invocation_id), cost, Jsonb(dict(provider_record))),
                )

    def complete_invocation(self, invocation_id: str, response: Mapping[str, Any], invocation: Mapping[str, Any] | None = None) -> None:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute(
                """UPDATE positioning_provider_invocations SET response_sha256=%s,status='completed',
                       invocation=invocation||%s,completed_at=clock_timestamp() WHERE id=%s""",
                (_json_sha(response), Jsonb(dict(invocation or {})), UUID(invocation_id)),
            )

    def fail_invocation(self, invocation_id: str, error: Exception) -> None:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute(
                """UPDATE positioning_provider_invocations SET status='failed',
                       invocation=invocation||%s,completed_at=clock_timestamp()
                   WHERE id=%s AND status<>'completed'""",
                (Jsonb({"error_code": type(error).__name__, "error_message": str(error)[:1000]}), UUID(invocation_id)),
            )

    def spend(self, revision_id: str) -> float:
        with self.connection() as connection:
            value = connection.execute(
                """SELECT COALESCE(sum(cost.amount_usd),0)
                   FROM positioning_provider_costs cost
                   JOIN positioning_provider_invocations invocation ON invocation.id=cost.invocation_id
                   WHERE invocation.revision_id=%s""",
                (UUID(revision_id),),
            ).fetchone()[0]
        return float(value)

    @staticmethod
    def _notification_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "revision_id": str(row[1]),
            "generation_attempt_id": str(row[2]), "terminal_status": row[3],
            "status": row[4], "telegram_chat_id": int(row[5]),
            "telegram_message_id": row[6], "error_code": row[7],
            "error_message": row[8], "created_at": row[9].isoformat(),
            "completed_at": row[10].isoformat(),
        }

    def notification_attempt(self, generation_attempt_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id,revision_id,generation_attempt_id,terminal_status,status,
                          telegram_chat_id,telegram_message_id,error_code,error_message,
                          created_at,completed_at
                   FROM positioning_notification_attempts WHERE generation_attempt_id=%s""",
                (UUID(generation_attempt_id),),
            ).fetchone()
        return None if row is None else self._notification_row(row)

    def record_notification_attempt(
        self,
        revision_id: str,
        generation_attempt_id: str,
        *,
        terminal_status: str,
        status: str,
        chat_id: int,
        message_id: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        if terminal_status not in {"completed", "failed"}:
            raise ValueError("positioning notification requires a terminal revision status")
        if status not in {"sent", "failed", "ambiguous", "suppressed"}:
            raise ValueError("unknown positioning notification status")
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO positioning_notification_attempts(
                       id,revision_id,generation_attempt_id,terminal_status,status,
                       telegram_chat_id,telegram_message_id,error_code,error_message
                   ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (generation_attempt_id) DO NOTHING""",
                (
                    UUID(new_uuid7()), UUID(revision_id), UUID(generation_attempt_id),
                    terminal_status, status, chat_id, message_id,
                    None if error_code is None else error_code[:100],
                    None if error_message is None else error_message[:1000],
                ),
            )
        stored = self.notification_attempt(generation_attempt_id)
        if stored is None:
            raise RuntimeError("positioning notification attempt was not persisted")
        return stored

    def emergency_stopped(self) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT emergency_stop FROM commander_control WHERE singleton"
            ).fetchone()
        return bool(row and row[0])

    def approve(self, revision_id: str, approved_by: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            row = connection.execute(
                "SELECT project_id,status,document FROM positioning_revisions WHERE entity_id=%s FOR SHARE",
                (UUID(revision_id),),
            ).fetchone()
            if row is None:
                raise KeyError(revision_id)
            project_id, status, document = row
            if status != "completed" or document is None:
                raise ValueError("only a completed positioning revision can be approved")
            existing = connection.execute(
                "SELECT revision_id FROM positioning_approvals WHERE project_id=%s AND revoked_at IS NULL FOR UPDATE",
                (project_id,),
            ).fetchone()
            if existing is not None and existing[0] == UUID(revision_id):
                return self.get_revision(revision_id)
            connection.execute(
                "UPDATE positioning_approvals SET revoked_at=clock_timestamp() WHERE project_id=%s AND revoked_at IS NULL",
                (project_id,),
            )
            connection.execute(
                "INSERT INTO positioning_approvals(id,revision_id,project_id,approved_by) VALUES(%s,%s,%s,%s)",
                (UUID(new_uuid7()), UUID(revision_id), project_id, approved_by),
            )
            connection.execute(
                "INSERT INTO commander_audit_events(id,actor,action,target_id,details) VALUES(%s,%s,'positioning.approved',%s,%s)",
                (UUID(new_uuid7()), approved_by, UUID(revision_id), Jsonb({"project_id": str(project_id)})),
            )
        return self.get_revision(revision_id)

    def approved_revision(self, revision_id: str) -> dict[str, Any]:
        revision = self.get_revision(revision_id)
        if not revision["approved"]:
            raise ValueError("Landing and Ads require the active approved positioning revision")
        return revision

    def skill_proposals(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT proposal.id,proposal.feedback_id,proposal.revision_id,proposal.lesson,
                          proposal.status,proposal.command_session_id,proposal.created_at,proposal.updated_at
                   FROM positioning_skill_proposals proposal
                   JOIN positioning_revisions revision ON revision.entity_id=proposal.revision_id
                   WHERE revision.project_id=%s ORDER BY proposal.created_at DESC""",
                (UUID(project_id),),
            ).fetchall()
        return [self._proposal_row(row) for row in rows]

    def skill_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id,feedback_id,revision_id,lesson,status,command_session_id,created_at,updated_at
                   FROM positioning_skill_proposals WHERE id=%s""",
                (UUID(proposal_id),),
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return self._proposal_row(row)

    @staticmethod
    def _proposal_row(row: Sequence[Any]) -> dict[str, Any]:
        return {
            "id": str(row[0]), "feedback_id": str(row[1]), "revision_id": str(row[2]),
            "lesson": row[3], "status": row[4],
            "command_session_id": None if row[5] is None else str(row[5]),
            "created_at": row[6].isoformat(), "updated_at": row[7].isoformat(),
        }

    def update_skill_proposal(self, proposal_id: str, lesson: str) -> dict[str, Any]:
        normalized = lesson.strip()
        if not 1 <= len(normalized) <= 500:
            raise ValueError("lesson must contain 1-500 characters")
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE positioning_skill_proposals SET lesson=%s,updated_at=clock_timestamp()
                   WHERE id=%s AND status='pending'""",
                (normalized, UUID(proposal_id)),
            ).rowcount
        if not changed:
            raise ValueError("only a pending positioning lesson can be edited")
        return self.skill_proposal(proposal_id)

    def dismiss_skill_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE positioning_skill_proposals SET status='rejected',updated_at=clock_timestamp()
                   WHERE id=%s AND status='pending'""",
                (UUID(proposal_id),),
            ).rowcount
        if not changed:
            raise ValueError("only a pending positioning lesson can be dismissed")
        return self.skill_proposal(proposal_id)

    def plan_skill_proposal(self, proposal_id: str, lesson: str, command_session_id: str) -> dict[str, Any]:
        normalized = lesson.strip()
        if not 1 <= len(normalized) <= 500:
            raise ValueError("lesson must contain 1-500 characters")
        with self.connection() as connection:
            changed = connection.execute(
                """UPDATE positioning_skill_proposals SET lesson=%s,status='planning',command_session_id=%s,
                          updated_at=clock_timestamp() WHERE id=%s AND status='pending'""",
                (normalized, UUID(command_session_id), UUID(proposal_id)),
            ).rowcount
        if not changed:
            raise ValueError("only a pending positioning lesson can be promoted")
        return self.skill_proposal(proposal_id)

    def recover_interrupted(self) -> int:
        with self.connection() as connection:
            attempts = connection.execute(
                """UPDATE positioning_generation_attempts SET status='failed',error_code='InterruptedError',
                       error_message='service restarted during generation',completed_at=clock_timestamp()
                   WHERE status='started'"""
            ).rowcount
            connection.execute(
                """UPDATE positioning_revisions SET status='failed',failure_count=failure_count+1,
                       error_code='InterruptedError',error_message='service restarted during generation',
                       updated_at=clock_timestamp(),completed_at=clock_timestamp()
                   WHERE status IN ('researching','synthesizing')"""
            )
            connection.execute(
                """UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton AND operation_kind='marketing_positioning'"""
            )
        return int(attempts)

    def acquire_operation(self, kind: str, operation_id: str) -> None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT operation_kind,operation_id FROM commander_operation_guard WHERE singleton FOR UPDATE"
            ).fetchone()
            if row is None:
                raise RuntimeError("global operation guard is missing")
            if row[1] is not None:
                raise RuntimeError(f"heavy operation {row[0]} {row[1]} is already active")
            connection.execute(
                "UPDATE commander_operation_guard SET operation_kind=%s,operation_id=%s,acquired_at=clock_timestamp() WHERE singleton",
                (kind, UUID(operation_id)),
            )

    def release_operation(self, operation_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton AND operation_id=%s""",
                (UUID(operation_id),),
            )

    def activity(self) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT operation_kind,operation_id,acquired_at FROM commander_operation_guard WHERE singleton"
            ).fetchone()
        return {
            "active": bool(row and row[1]),
            "operation": None if not row else row[0],
            "operation_id": None if not row or row[1] is None else str(row[1]),
            "acquired_at": None if not row or row[2] is None else row[2].isoformat(),
        }
