from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator


class PlatformRepository:
    def __init__(self, database_url: str, owner_telegram_id: int) -> None:
        self.database_url = database_url
        self.owner_telegram_id = owner_telegram_id

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url) as connection:
            yield connection

    def create_running_job(self, instruction: str, command_id: str) -> int:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            user = connection.execute("SELECT id FROM users WHERE telegram_user_id=%s", (self.owner_telegram_id,)).fetchone()
            if user is None:
                raise RuntimeError("platform owner identity is not seeded")
            session_id = connection.execute(
                "INSERT INTO sessions(user_id,status,summary) VALUES(%s,'active',%s) RETURNING id",
                (user[0], f"Web Commander {command_id}"),
            ).fetchone()[0]
            job_id = connection.execute(
                """INSERT INTO jobs(session_id,type,status,requested_by,parameters,stage,started_at)
                   VALUES(%s,'web_command','running',%s,%s,'CODEX_EXEC',now()) RETURNING id""",
                (session_id, user[0], Jsonb({"task": instruction, "command_session_id": command_id, "repo": "ptw"})),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO events(session_id,job_id,actor,event_type,status,payload) VALUES(%s,%s,'owner-gateway','JOB_STARTED','running',%s)",
                (session_id, job_id, Jsonb({"command_session_id": command_id, "stage": "CODEX_EXEC"})),
            )
        return int(job_id)

    def emergency_stop(self) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT emergency_stop FROM platform_control WHERE singleton=true"
            ).fetchone()
        return bool(row and row[0])

    def set_emergency_stop(self, active: bool, *, actor: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO platform_control(singleton,emergency_stop,updated_at,updated_by)
                   VALUES(true,%s,now(),%s)
                   ON CONFLICT(singleton) DO UPDATE SET emergency_stop=excluded.emergency_stop,
                     updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
                (active, actor),
            )
            if active:
                connection.execute(
                    """UPDATE jobs SET
                         status=CASE WHEN status='queued' THEN 'cancelled' ELSE 'cancel_requested' END,
                         finished_at=CASE WHEN status='queued' THEN now() ELSE finished_at END
                       WHERE status IN ('queued','running','blocked')"""
                )

    def complete_job(self, job_id: int, *, success: bool, result: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        status = "completed" if success else "failed"
        with self.connection() as connection:
            session_id = connection.execute(
                """UPDATE jobs SET status=%s,result=%s,error_code=%s,error_message=%s,
                   stage=%s,finished_at=now() WHERE id=%s RETURNING session_id""",
                (status, Jsonb(result), None if success else "CODEX_EXEC_FAILED",
                 None if success else str(result.get("error", "execution failed"))[:2000],
                 "COMPLETED" if success else "FAILED", job_id),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO events(session_id,job_id,actor,event_type,status,payload) VALUES(%s,%s,'owner-gateway',%s,%s,%s)",
                (session_id, job_id, "JOB_COMPLETED" if success else "JOB_FAILED", status, Jsonb(result)),
            )
            connection.execute("UPDATE sessions SET status=%s,updated_at=now() WHERE id=%s", (status, session_id))

    def cancel(self, job_id: int) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE jobs SET status=CASE WHEN status='queued' THEN 'cancelled' ELSE 'cancel_requested' END WHERE id=%s AND status NOT IN ('completed','failed','cancelled')",
                (job_id,),
            )

    def state(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT j.id,j.type,j.status,j.parameters,j.result,j.created_at,
                          r.commit_sha,r.preview_url,r.pull_request_url
                   FROM jobs j LEFT JOIN engineering_runs r ON r.job_id=j.id
                   ORDER BY j.created_at DESC LIMIT %s""", (min(limit, 100),),
            ).fetchall()
        return [{
            "id": f"TASK-{row[0]}", "mode": "execute", "title": str((row[3] or {}).get("task") or row[1]),
            "status": row[2], "created_at": row[5].isoformat(), "deployment_revision": row[6],
            "preview_url": row[7], "pull_request_url": row[8],
        } for row in rows]

    def summary(self) -> dict[str, Any]:
        with self.connection() as connection:
            active = connection.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running','cancel_requested')").fetchone()[0]
            blocked = connection.execute("SELECT count(*) FROM engineering_issues WHERE status IN ('open','resolving','unresolved')").fetchone()[0]
            deploy = connection.execute("SELECT commit_sha FROM engineering_runs WHERE commit_sha IS NOT NULL ORDER BY updated_at DESC LIMIT 1").fetchone()
            stopped = connection.execute(
                "SELECT emergency_stop FROM platform_control WHERE singleton=true"
            ).fetchone()
        return {
            "active": active, "blocked": blocked,
            "last_deploy": deploy[0][:10] if deploy else None,
            "emergency_stop": bool(stopped and stopped[0]),
        }

    def issues(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT id,job_id,stage,status,error_type,summary,resolution_summary,attempt_count,created_at
                   FROM engineering_issues ORDER BY created_at DESC LIMIT %s""", (min(limit, 100),),
            ).fetchall()
        return [{
            "id": f"ISSUE-{row[0]}", "job_id": f"TASK-{row[1]}", "stage": row[2],
            "status": row[3], "error_type": row[4], "summary": row[5],
            "resolution_summary": row[6], "attempt_count": row[7], "created_at": row[8].isoformat(),
        } for row in rows]
