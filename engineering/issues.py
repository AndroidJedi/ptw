"""Durable issue records and bounded task/issue read models."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from psycopg.types.json import Jsonb

from common.events import _safe_payload, append_event


def _safe_text(value: object, limit: int = 4000) -> str:
    """Bound diagnostics and apply the shared payload redaction rules."""
    text = str(_safe_payload({"diagnostic": str(value)}).get("diagnostic", ""))
    text = re.sub(
        r"(?i)(token|password|secret|api[_-]?key|authorization)(\s*[:=]\s*)(\S+)",
        r"\1\2[REDACTED]",
        text,
    )
    return text[-limit:]


def create_issue(
    connection: Any, *, job_id: int, stage: str, error: BaseException
) -> int:
    summary = _safe_text(error)
    issue_id = connection.execute(
        """INSERT INTO engineering_issues(job_id,stage,error_type,summary)
           VALUES(%s,%s,%s,%s) RETURNING id""",
        (job_id, stage, type(error).__name__, summary),
    ).fetchone()[0]
    append_issue_log(connection, issue_id, "error", summary, {"stage": stage})
    append_event(
        connection,
        "ISSUE_CREATED",
        "engineering-runner",
        job_id=job_id,
        status="open",
        payload={"issue_id": issue_id, "stage": stage, "error_type": type(error).__name__},
    )
    return issue_id


def append_issue_log(
    connection: Any,
    issue_id: int,
    level: str,
    message: str,
    metadata: Mapping[str, object] | None = None,
) -> None:
    connection.execute(
        """INSERT INTO engineering_issue_logs(issue_id,level,message,metadata)
           VALUES(%s,%s,%s,%s)""",
        (issue_id, level, _safe_text(message), Jsonb(_safe_payload(metadata or {}))),
    )


def transition_issue(
    connection: Any,
    issue_id: int,
    status: str,
    *,
    summary: str | None = None,
) -> None:
    row = connection.execute(
        """UPDATE engineering_issues
           SET status=%s, resolution_summary=COALESCE(%s,resolution_summary),
               attempt_count=attempt_count + CASE WHEN %s='resolving' THEN 1 ELSE 0 END,
               resolved_at=CASE WHEN %s IN ('resolved','unresolved','cancelled') THEN now() ELSE resolved_at END,
               updated_at=now()
           WHERE id=%s RETURNING job_id""",
        (status, _safe_text(summary) if summary else None, status, status, issue_id),
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown issue: {issue_id}")
    append_issue_log(connection, issue_id, "info", summary or f"Issue transitioned to {status}")
    append_event(
        connection,
        f"ISSUE_{status.upper()}",
        "engineering-runner",
        job_id=row[0],
        status=status,
        payload={"issue_id": issue_id},
    )


def task_details(connection: Any, job_id: int) -> dict[str, object]:
    job = connection.execute(
        """SELECT id,type,status,stage,parameters,result,error_code,error_message,
                  created_at,started_at,finished_at,parent_job_id
           FROM jobs WHERE id=%s""",
        (job_id,),
    ).fetchone()
    if job is None:
        raise KeyError(f"unknown task: {job_id}")
    issues = connection.execute(
        """SELECT id,stage,status,error_type,summary,resolution_summary,attempt_count,
                  created_at,updated_at,resolved_at
           FROM engineering_issues WHERE job_id=%s ORDER BY id""",
        (job_id,),
    ).fetchall()
    events = connection.execute(
        """SELECT id,event_type,status,payload,created_at FROM events
           WHERE job_id=%s ORDER BY id DESC LIMIT 50""",
        (job_id,),
    ).fetchall()
    return {
        "id": f"TASK-{job[0]}", "type": job[1], "status": job[2], "stage": job[3],
        "request": (job[4] or {}).get("task", ""), "result": job[5],
        "error": {"code": job[6], "message": job[7]} if job[6] else None,
        "created_at": job[8], "started_at": job[9], "finished_at": job[10],
        "parent_task_id": f"TASK-{job[11]}" if job[11] else None,
        "issues": [
            {"id": f"ISSUE-{row[0]}", "stage": row[1], "status": row[2],
             "error_type": row[3], "summary": row[4], "resolution_summary": row[5],
             "attempt_count": row[6], "created_at": row[7], "updated_at": row[8],
             "resolved_at": row[9]} for row in issues
        ],
        "events": [
            {"id": row[0], "type": row[1], "status": row[2], "payload": row[3],
             "created_at": row[4]} for row in reversed(events)
        ],
    }


def issue_details(connection: Any, issue_id: int) -> dict[str, object]:
    issue = connection.execute(
        """SELECT id,job_id,stage,status,error_type,summary,resolution_summary,
                  attempt_count,created_at,updated_at,resolved_at
           FROM engineering_issues WHERE id=%s""",
        (issue_id,),
    ).fetchone()
    if issue is None:
        raise KeyError(f"unknown issue: {issue_id}")
    logs = connection.execute(
        """SELECT id,level,message,metadata,created_at FROM engineering_issue_logs
           WHERE issue_id=%s ORDER BY id DESC LIMIT 50""",
        (issue_id,),
    ).fetchall()
    return {
        "id": f"ISSUE-{issue[0]}", "task_id": f"TASK-{issue[1]}", "stage": issue[2],
        "status": issue[3], "error_type": issue[4], "summary": issue[5],
        "resolution_summary": issue[6], "attempt_count": issue[7],
        "created_at": issue[8], "updated_at": issue[9], "resolved_at": issue[10],
        "logs": [{"id": row[0], "level": row[1], "message": row[2],
                  "metadata": row[3], "created_at": row[4]} for row in reversed(logs)],
    }


def parse_reference(value: str) -> tuple[str, int]:
    normalized = value.strip().upper()
    if normalized.isdigit():
        return "task", int(normalized)
    prefix, separator, identifier = normalized.partition("-")
    if separator and identifier.isdigit() and prefix in {"TASK", "ISSUE"}:
        return prefix.lower(), int(identifier)
    raise ValueError("use TASK-<id>, ISSUE-<id>, or a numeric task ID")


def render_reference(connection: Any, reference: str) -> str:
    kind, identifier = parse_reference(reference)
    value = task_details(connection, identifier) if kind == "task" else issue_details(connection, identifier)
    if kind == "task":
        issues = value["issues"]
        latest = value["events"][-8:]
        issue_summary = ", ".join(
            f"{item['id']}[{item['status']}]" for item in issues
        ) or "none"
        return (
            f"{value['id']} [{value['status']}] stage={value['stage'] or 'none'}\n"
            f"Request: {str(value['request'])[:700] or 'none'}\n"
            f"Issues: {issue_summary}\n"
            "Recent log:\n" + "\n".join(
                f"{item['id']} {item['type']} [{item['status'] or '-'}]" for item in latest
            )
        )
    logs = value["logs"][-8:]
    return (
        f"{value['id']} [{value['status']}] blocks {value['task_id']} stage={value['stage']}\n"
        f"Error: {value['error_type']}: {str(value['summary'])[:700]}\n"
        f"Resolution: {value['resolution_summary'] or 'pending'}\n"
        "Issue log:\n" + "\n".join(
            f"{item['id']} {item['level']}: {str(item['message'])[:240]}" for item in logs
        )
    )
