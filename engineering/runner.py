import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from common.repositories import Repository


class StageFailure(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message); self.stage = stage


@dataclass
class ValidationResult:
    command: str
    passed: bool
    duration_seconds: float
    excerpt: str = ""


@dataclass
class EngineeringResult:
    branch: str
    commit_sha: str | None = None
    files_changed: list[str] = field(default_factory=list)
    validation: list[ValidationResult] = field(default_factory=list)
    codex_executions: int = 0
    retries: int = 0


def branch_name(job_id: int, request: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", request.lower()).strip("-")[:40] or "task"
    return f"agent/job-{job_id}-{slug}"


def enforce_push_branch(branch: str) -> None:
    if not re.fullmatch(r"agent/[a-z0-9][a-z0-9._/-]{0,100}", branch) or branch == "agent/main":
        raise StageFailure("GIT_PUSH", "Only agent/* task branches may be pushed")


def run(command: list[str], *, cwd: Path, timeout: int = 1800, input_text: str | None = None) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    environment.update({"GIT_TERMINAL_PROMPT":"0", "GIT_SSH_COMMAND":"ssh -F /etc/ptw-git/ssh_config"})
    return subprocess.run(command, cwd=cwd, env=environment, input=input_text, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)


def create_workspace(job_id: int, repository: Repository, request: str,
                     root: Path | None = None) -> tuple[Path, str]:
    base = (root or Path(os.getenv("ENGINEERING_WORKSPACE_ROOT", "/opt/ptw/workspaces/jobs"))) / str(job_id)
    if base.exists():
        raise StageFailure("CLONE", f"Workspace already exists for job {job_id}")
    base.mkdir(parents=True, mode=0o700)
    checkout = base / "repo"
    clone = run(["git", "clone", "--quiet", "--branch", repository.default_branch, "--single-branch", repository.clone_url, str(checkout)], cwd=base)
    if clone.returncode: raise StageFailure("CLONE", clone.stdout[-2000:])
    branch = branch_name(job_id, request)
    created = run(["git", "checkout", "-b", branch], cwd=checkout)
    if created.returncode: raise StageFailure("CLONE", created.stdout[-2000:])
    return checkout, branch


def copy_attachments(paths: list[Path], job_root: Path) -> list[Path]:
    target = job_root / "attachments"; target.mkdir(mode=0o700, parents=True, exist_ok=True)
    copied = []
    for index, source in enumerate(paths):
        if not source.is_file(): continue
        destination = target / f"attachment-{index}{source.suffix.lower()[:10]}"
        shutil.copyfile(source, destination); destination.chmod(0o600); copied.append(destination)
    return copied


def invoke_codex(checkout: Path, spec: Path, attachments: list[Path], output: Path) -> subprocess.CompletedProcess:
    prompt = "Execute the bounded engineering specification in spec.md. Inspect only relevant files. Do not push, merge, or deploy. Finish with the working tree containing the requested changes."
    command = [os.getenv("CODEX_EXECUTABLE", "codex"), "exec", "--ephemeral", "--ignore-user-config",
               "--sandbox", "workspace-write", "--cd", str(checkout), "--output-last-message", str(output)]
    for attachment in attachments: command.extend(("--image", str(attachment)))
    command.append(prompt + "\n\n" + spec.read_text(encoding="utf-8"))
    return run(command, cwd=checkout, timeout=int(os.getenv("CODEX_TIMEOUT_SECONDS", "1800")))


def validation_commands(checkout: Path, risk: str) -> list[list[str]]:
    commands = [["dart", "format", "--output=none", "--set-exit-if-changed", "."], ["flutter", "analyze"], ["flutter", "test"]]
    if risk in {"MEDIUM", "HIGH"} or (checkout / "web").exists(): commands.append(["flutter", "build", "web"])
    return commands


def validate(checkout: Path, risk: str) -> list[ValidationResult]:
    results = []
    for command in validation_commands(checkout, risk):
        if shutil.which(command[0]) is None:
            raise StageFailure("VALIDATION", f"Required validation tool is unavailable: {command[0]}")
        start = time.monotonic(); completed = run(command, cwd=checkout)
        result = ValidationResult(" ".join(command), completed.returncode == 0, round(time.monotonic()-start, 3), completed.stdout[-2000:])
        results.append(result)
        if not result.passed: raise StageFailure("VALIDATION", f"{result.command}\n{result.excerpt}")
    return results


def commit_changes(checkout: Path, job_id: int, request: str) -> tuple[str, list[str]]:
    changed = run(["git", "status", "--porcelain"], cwd=checkout).stdout.splitlines()
    if not changed: raise StageFailure("CODEX", "Executor produced no changes")
    run(["git", "add", "--all"], cwd=checkout)
    subject = re.sub(r"\s+", " ", request).strip()[:60]
    committed = run(["git", "-c", "user.name=PTW Engineering Agent", "-c", "user.email=engineering@localhost",
                     "commit", "-m", f"job {job_id}: {subject}"], cwd=checkout)
    if committed.returncode: raise StageFailure("GIT_COMMIT", committed.stdout[-2000:])
    sha = run(["git", "rev-parse", "HEAD"], cwd=checkout).stdout.strip()
    files = run(["git", "diff", "--name-only", "HEAD^", "HEAD"], cwd=checkout).stdout.splitlines()
    return sha, files


def render_result(result: EngineeringResult) -> str:
    checks = "\n".join(f"- {item.command}: {'PASS' if item.passed else 'FAIL'} ({item.duration_seconds}s)" for item in result.validation)
    files = "\n".join(f"- {item}" for item in result.files_changed)
    return f"# Engineering Result\n\n## Summary\nChanges committed on `{result.branch}`.\n\n## Acceptance criteria result\nValidated successfully.\n\n## Files changed\n{files}\n\n## Validation\n{checks}\n\n## Known limitations\nNone recorded.\n\n## Commit SHA\n{result.commit_sha}\n"
