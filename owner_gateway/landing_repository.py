"""PostgreSQL authority for Natal landing build and publication state."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID, uuid4


ACTIVE_STATUSES = ("queued", "building", "publishing")


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
            "brief": row[5],
            "status": row[6],
            "output_path": row[7],
            "build_manifest": row[8],
            "artifact_sha256": row[9],
            "firebase_site_id": row[10],
            "firebase_version": row[11],
            "public_url": row[12],
            "error_code": row[13],
            "error_message": row[14],
            "requested_by": row[15],
            "created_at": row[16].isoformat(),
            "updated_at": row[17].isoformat(),
            "completed_at": None if row[18] is None else row[18].isoformat(),
        }

    @staticmethod
    def _select() -> str:
        return """SELECT entity_id,request_id,source_laval_run_id,source_thesis_id,
                         template_id,brief,status,output_path,build_manifest,artifact_sha256,
                         firebase_site_id,firebase_version,public_url,error_code,error_message,
                         requested_by,created_at,updated_at,completed_at
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

    def list(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                self._select() + " ORDER BY created_at DESC LIMIT %s", (min(limit, 100),)
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
        with self.connection() as connection:
            connection.execute("BEGIN")
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
                        "brand": "Natal",
                        "template_id": prepared["template_id"],
                        "idea_run_id": str(run_id),
                    }),
                ),
            )
            connection.execute(
                "INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,'derived_from',%s,%s)",
                (uuid4(), build_id, source_id, Jsonb({"thesis_id": raw_thesis or None})),
            )
            connection.execute(
                """INSERT INTO natal_landing_builds(
                       entity_id,request_id,source_laval_run_id,source_thesis_id,template_id,
                       brief,status,output_path,firebase_site_id,requested_by
                   ) VALUES(%s,%s,%s,%s,%s,%s,'queued',%s,%s,%s)""",
                (
                    build_id, UUID(request_id), run_id, thesis_id, prepared["template_id"],
                    Jsonb(brief), output_path, firebase_site_id, requested_by,
                ),
            )
        return self.get(str(build_id)), True

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
            "build_manifest", "artifact_sha256", "firebase_version", "public_url",
            "error_code", "error_message",
        }
        if not set(values).issubset(allowed):
            raise ValueError("invalid landing build update")
        normalized = {
            key: Jsonb(value) if key == "build_manifest" and value is not None else value
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

    def mark_building(self, build_id: str) -> dict[str, Any]:
        return self._transition(build_id, ("queued",), "building", error_code=None, error_message=None)

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
                   WHERE status IN ('queued','building','publishing')"""
            )
            recovered = cursor.rowcount
        return recovered

    def published(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                self._select() + " WHERE status='published' ORDER BY created_at DESC LIMIT %s",
                (min(limit, 100),),
            ).fetchall()
        return [self._row(row) for row in rows]
