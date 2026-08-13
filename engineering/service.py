import os
import time
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from common.events import append_event
from common.repositories import RepositoryRegistry
from engineering.brain import acceptance_criteria, classify, decompose, render_spec
from engineering.components import describe_manifest, load_manifest
from engineering.github import create_or_get_pr, pull_request_body, push_agent_branch
from engineering.memory import retrieve
from engineering.runner import (EngineeringResult, StageFailure, commit_changes,
                                copy_attachments, create_workspace, invoke_codex,
                                render_result, validate)


def event(connection: Any, kind: str, job_id: int, status: str, payload: dict | None = None) -> None:
    append_event(connection, kind, "engineering-runner", job_id=job_id, status=status, payload=payload or {})


def execute_engineering_job(connection: Any, job_id: int, parameters: dict) -> str:
    request, repository_id = parameters["task"], parameters.get("repo", "ptw")
    repository = RepositoryRegistry(connection).get(repository_id)
    classification = classify(request)
    memory = retrieve(connection, repository_id, request)
    event(connection, "PROJECT_MEMORY_RETRIEVED", job_id, "completed", {"repository":repository_id, "items":len(memory)})
    checkout, branch = create_workspace(job_id, repository, request)
    job_root = checkout.parent
    event(connection, "WORKSPACE_CREATED", job_id, "completed", {"repository":repository_id, "branch":branch})
    attachment_paths = copy_attachments([Path(path) for path in parameters.get("attachments", [])], job_root)
    spec_path = job_root / "spec.md"
    component_manifest = load_manifest(checkout)
    spec_path.write_text(render_spec(request=request, repository_id=repository_id, classification=classification,
                                     memory=memory, attachments=[str(path) for path in attachment_paths],
                                     component_catalog=describe_manifest(component_manifest)), encoding="utf-8")
    event(connection, "ENGINEERING_SPEC_CREATED", job_id, "completed", {"task_class":classification.task_class, "risk":classification.risk})
    steps = decompose(request, classification)
    if steps: event(connection, "ENGINEERING_TASK_DECOMPOSED", job_id, "completed", {"child_count":len(steps)})
    connection.execute(
        """INSERT INTO engineering_runs(job_id,repository_id,task_class,risk_level,branch,status)
           VALUES(%s,%s,%s,%s,%s,'running') ON CONFLICT(job_id) DO UPDATE SET status='running',updated_at=now()""",
        (job_id, repository_id, classification.task_class, classification.risk, branch))
    connection.execute("INSERT INTO engineering_artifacts(job_id,kind,path) VALUES(%s,'spec',%s) ON CONFLICT DO NOTHING", (job_id, str(spec_path)))
    connection.commit()
    maximum = max(0, int(os.getenv("CODEX_MAX_RETRIES", "2")))
    output = job_root / "codex-result.txt"; executions = 0
    for attempt in range(maximum + 1):
        executions += 1; started = time.monotonic()
        event(connection, "CODEX_STARTED", job_id, "running", {"attempt":attempt + 1})
        def cancelled() -> bool:
            return connection.execute("SELECT status='cancel_requested' FROM jobs WHERE id=%s", (job_id,)).fetchone()[0]
        completed = invoke_codex(checkout, spec_path, attachment_paths, output, cancelled)
        duration = round(time.monotonic() - started, 3)
        if completed.returncode == 0:
            event(connection, "CODEX_COMPLETED", job_id, "completed", {"attempt":attempt + 1, "duration_seconds":duration})
            break
        if attempt == maximum:
            raise StageFailure("CODEX", completed.stdout[-2000:])
        connection.execute("UPDATE jobs SET retry_count=retry_count+1 WHERE id=%s", (job_id,))
    event(connection, "VALIDATION_STARTED", job_id, "running")
    started = time.monotonic(); validations = validate(checkout, classification.risk, component_manifest)
    event(connection, "VALIDATION_COMPLETED", job_id, "completed", {"duration_seconds":round(time.monotonic()-started,3), "checks":len(validations)})
    sha, files = commit_changes(checkout, job_id, request)
    event(connection, "GIT_COMMIT_CREATED", job_id, "completed", {"commit_sha":sha, "files_changed":len(files), "branch":branch})
    result = EngineeringResult(branch, sha, files, validations, executions, executions - 1)
    result_path = job_root / "result.md"; result_path.write_text(render_result(result), encoding="utf-8")
    connection.execute("INSERT INTO engineering_artifacts(job_id,kind,path) VALUES(%s,'result',%s) ON CONFLICT DO NOTHING", (job_id, str(result_path)))
    connection.execute("UPDATE engineering_runs SET commit_sha=%s,status='validated',updated_at=now() WHERE job_id=%s", (sha, job_id))
    connection.execute("UPDATE jobs SET metrics=%s WHERE id=%s", (Jsonb({"codex_executions":executions,"retries":executions-1}), job_id))
    push_agent_branch(checkout, branch)
    event(connection, "GIT_BRANCH_PUSHED", job_id, "completed", {"branch":branch, "commit_sha":sha})
    body = pull_request_body(job_id, request, acceptance_criteria(request), files, validations)
    pr_number, pr_url, created = create_or_get_pr(repository, branch, f"Job {job_id}: {request}", body)
    if created: event(connection, "GITHUB_PR_CREATED", job_id, "completed", {"branch":branch, "pr_number":pr_number, "url":pr_url})
    connection.execute("UPDATE engineering_runs SET pull_request_number=%s,pull_request_url=%s,status='pr_created',updated_at=now() WHERE job_id=%s", (pr_number,pr_url,job_id))
    return f"Engineering job #{job_id} ready\nPR: #{pr_number} {pr_url}\nBranch: {branch}\nValidation: ✅\nFiles changed: {len(files)}\nRemote main unchanged."
