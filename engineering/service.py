import os
import time
from pathlib import Path
from collections.abc import Callable
from typing import Any

from psycopg.types.json import Jsonb

from common.events import append_event
from common.repositories import RepositoryRegistry
from engineering.brain import acceptance_criteria, classify, decompose, render_spec
from engineering.components import describe_manifest, load_manifest
from engineering.github import (create_or_get_pr, merge_pull_request,
                                pull_request_body, push_agent_branch)
from engineering.issues import (append_issue_log, create_issue, issue_details,
                                transition_issue)
from engineering.memory import retrieve
from engineering.runner import (EngineeringResult, JobCancelled, StageFailure, commit_changes,
                                copy_attachments, create_workspace, invoke_codex,
                                render_result, validate)


def event(connection: Any, kind: str, job_id: int, status: str, payload: dict | None = None) -> None:
    append_event(connection, kind, "engineering-runner", job_id=job_id, status=status, payload=payload or {})


def _report(reporter: Callable[[str], None] | None, text: str) -> None:
    if reporter is not None:
        reporter(text)


def _recover_issue(
    connection: Any,
    *,
    job_id: int,
    stage: str,
    error: StageFailure,
    checkout: Path,
    spec_path: Path,
    attachment_paths: list[Path],
    output: Path,
    cancelled: Callable[[], bool],
    reporter: Callable[[str], None] | None,
    agent_resolution: bool = True,
) -> int:
    """Switch to a blocking issue, attempt repair, then return to the task."""
    issue_id = create_issue(connection, job_id=job_id, stage=stage, error=error)
    connection.execute("UPDATE jobs SET status='blocked',stage=%s WHERE id=%s", (stage, job_id))
    event(connection, "TASK_BLOCKED", job_id, "blocked", {"issue_id": issue_id, "stage": stage})
    connection.commit()
    diagnostic = str(issue_details(connection, issue_id)["summary"])
    _report(
        reporter,
        f"TASK-{job_id} blocked by ISSUE-{issue_id} during {stage}.\n"
        f"{type(error).__name__}: {diagnostic[-1200:]}\n"
        "Automatic resolution has started. Use /inspect ISSUE-"
        f"{issue_id} for its log or /cancel {job_id} to interrupt.",
    )
    maximum = max(1, int(os.getenv("ISSUE_MAX_RESOLUTION_ATTEMPTS", "2")))
    for attempt in range(1, maximum + 1):
        if cancelled():
            transition_issue(connection, issue_id, "cancelled", summary="Parent task was cancelled")
            connection.commit()
            raise JobCancelled("Job cancelled while resolving an issue")
        transition_issue(
            connection,
            issue_id,
            "resolving",
            summary=f"Automatic resolution attempt {attempt} of {maximum}",
        )
        connection.commit()
        if not agent_resolution:
            append_issue_log(
                connection, issue_id, "info",
                "External operation recovery uses a bounded idempotent retry; no repository edits were made.",
                {"attempt": attempt},
            )
            transition_issue(
                connection, issue_id, "resolved",
                summary=f"External operation prepared for retry on attempt {attempt}",
            )
            connection.execute("UPDATE jobs SET status='running',stage=%s WHERE id=%s", (stage, job_id))
            event(connection, "TASK_RESUMED", job_id, "running", {"issue_id": issue_id, "stage": stage})
            connection.commit()
            _report(reporter, f"ISSUE-{issue_id} recovery prepared. TASK-{job_id} is retrying {stage}.")
            return issue_id
        instruction = (
            "Resolve the blocking issue described below while preserving the original task in spec.md. "
            "Inspect the repository and diagnostic, make only scoped code/configuration changes, and do not "
            "push, merge, deploy, erase logs, or hide failures. Finish with a working tree ready to resume "
            f"the parent task.\n\nBlocking stage: {stage}\nDiagnostic:\n{str(error)[-4000:]}"
        )
        completed = invoke_codex(
            checkout, spec_path, attachment_paths, output, cancelled, instruction=instruction
        )
        append_issue_log(
            connection,
            issue_id,
            "info" if completed.returncode == 0 else "warning",
            completed.stdout[-3000:] or f"Resolver exited with code {completed.returncode}",
            {"attempt": attempt, "returncode": completed.returncode},
        )
        if completed.returncode == 0:
            transition_issue(
                connection,
                issue_id,
                "resolved",
                summary=f"Resolver completed successfully on attempt {attempt}",
            )
            connection.execute("UPDATE jobs SET status='running',stage=%s WHERE id=%s", (stage, job_id))
            event(connection, "TASK_RESUMED", job_id, "running", {"issue_id": issue_id, "stage": stage})
            connection.commit()
            _report(reporter, f"ISSUE-{issue_id} resolved. TASK-{job_id} resumed at {stage}.")
            return issue_id
    transition_issue(
        connection,
        issue_id,
        "unresolved",
        summary=f"Automatic resolution exhausted {maximum} attempts",
    )
    connection.commit()
    _report(
        reporter,
        f"ISSUE-{issue_id} could not be resolved after {maximum} attempts. "
        f"TASK-{job_id} will fail with its full issue log retained.",
    )
    raise StageFailure(stage, f"ISSUE-{issue_id} unresolved: {error}")


def execute_engineering_job(
    connection: Any,
    job_id: int,
    parameters: dict,
    reporter: Callable[[str], None] | None = None,
) -> str:
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
                                     component_catalog=describe_manifest(component_manifest),
                                     research_context=parameters.get("research_context")), encoding="utf-8")
    if parameters.get("research_context"):
        event(connection, "RESEARCH_CONTEXT_CONSUMED", job_id, "completed", {
            "hypothesis_id": parameters["research_context"].get("hypothesis_id"),
            "owner_agent": parameters["research_context"].get("owner_agent"),
        })
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
    def cancelled() -> bool:
        return connection.execute("SELECT status='cancel_requested' FROM jobs WHERE id=%s", (job_id,)).fetchone()[0]
    for attempt in range(maximum + 1):
        executions += 1; started = time.monotonic()
        event(connection, "CODEX_STARTED", job_id, "running", {"attempt":attempt + 1})
        completed = invoke_codex(checkout, spec_path, attachment_paths, output, cancelled)
        duration = round(time.monotonic() - started, 3)
        if completed.returncode == 0:
            event(connection, "CODEX_COMPLETED", job_id, "completed", {"attempt":attempt + 1, "duration_seconds":duration})
            break
        if attempt == maximum:
            _recover_issue(
                connection, job_id=job_id, stage="CODEX", error=StageFailure("CODEX", completed.stdout[-2000:]),
                checkout=checkout, spec_path=spec_path, attachment_paths=attachment_paths,
                output=output, cancelled=cancelled, reporter=reporter,
            )
            executions += 1
            event(connection, "CODEX_RECOVERED", job_id, "completed", {"executions": executions})
            break
        connection.execute("UPDATE jobs SET retry_count=retry_count+1 WHERE id=%s", (job_id,))
    event(connection, "VALIDATION_STARTED", job_id, "running")
    started = time.monotonic()
    issue_recoveries = 0
    while True:
        try:
            validations = validate(checkout, classification.risk, component_manifest)
            break
        except StageFailure as error:
            if issue_recoveries >= max(1, int(os.getenv("TASK_MAX_ISSUES_PER_STAGE", "2"))):
                raise
            _recover_issue(
                connection, job_id=job_id, stage="VALIDATION", error=error,
                checkout=checkout, spec_path=spec_path, attachment_paths=attachment_paths,
                output=output, cancelled=cancelled, reporter=reporter,
            )
            issue_recoveries += 1
            executions += 1
    event(connection, "VALIDATION_COMPLETED", job_id, "completed", {"duration_seconds":round(time.monotonic()-started,3), "checks":len(validations)})
    try:
        sha, files = commit_changes(checkout, job_id, request)
    except StageFailure as error:
        _recover_issue(
            connection, job_id=job_id, stage="GIT_COMMIT", error=error,
            checkout=checkout, spec_path=spec_path, attachment_paths=attachment_paths,
            output=output, cancelled=cancelled, reporter=reporter,
        )
        executions += 1
        sha, files = commit_changes(checkout, job_id, request)
    event(connection, "GIT_COMMIT_CREATED", job_id, "completed", {"commit_sha":sha, "files_changed":len(files), "branch":branch})
    result = EngineeringResult(branch, sha, files, validations, executions, executions - 1)
    result_path = job_root / "result.md"; result_path.write_text(render_result(result), encoding="utf-8")
    connection.execute("INSERT INTO engineering_artifacts(job_id,kind,path) VALUES(%s,'result',%s) ON CONFLICT DO NOTHING", (job_id, str(result_path)))
    connection.execute("UPDATE engineering_runs SET commit_sha=%s,status='validated',updated_at=now() WHERE job_id=%s", (sha, job_id))
    connection.execute("UPDATE jobs SET metrics=%s WHERE id=%s", (Jsonb({"codex_executions":executions,"retries":executions-1}), job_id))
    try:
        push_agent_branch(checkout, branch)
    except StageFailure as error:
        _recover_issue(
            connection, job_id=job_id, stage="GIT_PUSH", error=error,
            checkout=checkout, spec_path=spec_path, attachment_paths=attachment_paths,
            output=output, cancelled=cancelled, reporter=reporter,
            agent_resolution=False,
        )
        executions += 1
        push_agent_branch(checkout, branch)
    event(connection, "GIT_BRANCH_PUSHED", job_id, "completed", {"branch":branch, "commit_sha":sha})
    body = pull_request_body(job_id, request, acceptance_criteria(request), files, validations)
    pr_number, pr_url, created = create_or_get_pr(repository, branch, f"Job {job_id}: {request}", body)
    if created: event(connection, "GITHUB_PR_CREATED", job_id, "completed", {"branch":branch, "pr_number":pr_number, "url":pr_url})
    connection.execute("UPDATE engineering_runs SET pull_request_number=%s,pull_request_url=%s,status='pr_created',updated_at=now() WHERE job_id=%s", (pr_number,pr_url,job_id))
    if repository.metadata.get("autonomous_main_merge"):
        try:
            rollback_sha, main_sha = merge_pull_request(repository, pr_number)
        except Exception as raw_error:
            error = raw_error if isinstance(raw_error, StageFailure) else StageFailure("MAIN_MERGE", str(raw_error))
            _recover_issue(
                connection, job_id=job_id, stage="MAIN_MERGE", error=error,
                checkout=checkout, spec_path=spec_path, attachment_paths=attachment_paths,
                output=output, cancelled=cancelled, reporter=reporter,
                agent_resolution=False,
            )
            executions += 1
            rollback_sha, main_sha = merge_pull_request(repository, pr_number)
        event(connection, "MAIN_MERGED", job_id, "completed", {
            "pr_number": pr_number, "rollback_sha": rollback_sha, "main_sha": main_sha,
            "production_triggered": bool(repository.metadata.get("production_via_main")),
        })
        connection.execute(
            "UPDATE engineering_runs SET status='merged',updated_at=now() WHERE job_id=%s", (job_id,)
        )
        production_via_main = bool(repository.metadata.get("production_via_main"))
        release_status = (
            "Production pipeline triggered by main."
            if production_via_main else
            "Production deployment is UNVERIFIED and requires a separate release check."
        )
        return (
            f"TASK-{job_id} completed and merged to main\nPR: #{pr_number} {pr_url}\n"
            f"Main: {main_sha}\nRollback: {rollback_sha}\nValidation: ✅\n"
            f"Files changed: {len(files)}\n{release_status}"
        )
    return f"TASK-{job_id} completed\nPR: #{pr_number} {pr_url}\nBranch: {branch}\nValidation: ✅\nFiles changed: {len(files)}\nMain merge disabled by repository policy."
