import json
import subprocess
from pathlib import Path

from common.repositories import Repository
from engineering.runner import StageFailure, enforce_push_branch, run


def push_agent_branch(checkout: Path, branch: str) -> None:
    enforce_push_branch(branch)
    current = run(["git", "branch", "--show-current"], cwd=checkout).stdout.strip()
    if current != branch: raise StageFailure("GIT_PUSH", "Current branch does not match approved task branch")
    pushed = run(["git", "push", "--set-upstream", "origin", f"HEAD:refs/heads/{branch}"], cwd=checkout)
    if pushed.returncode: raise StageFailure("GIT_PUSH", pushed.stdout[-2000:])


def pull_request_body(job_id: int, task: str, criteria: list[str], files: list[str], validation: list) -> str:
    checks = "\n".join(f"- {'✅' if item.passed else '❌'} `{item.command}`" for item in validation)
    return (f"## Task\n{task}\n\n## Acceptance criteria\n" + "\n".join(f"- {item}" for item in criteria) +
            "\n\n## Files changed\n" + "\n".join(f"- `{item}`" for item in files) +
            f"\n\n## Validation\n{checks}\n\nPTW engineering job: #{job_id}\n")


def create_or_get_pr(repository: Repository, branch: str, title: str, body: str) -> tuple[int, str, bool]:
    enforce_push_branch(branch)
    slug = repository.clone_url.split(":", 1)[1].removesuffix(".git")
    existing = subprocess.run(["gh", "pr", "list", "--repo", slug, "--head", branch, "--state", "open", "--json", "number,url"], text=True, capture_output=True, timeout=30, check=True)
    rows = json.loads(existing.stdout)
    if rows: return int(rows[0]["number"]), rows[0]["url"], False
    created = subprocess.run(["gh", "pr", "create", "--repo", slug, "--head", branch, "--base", repository.default_branch, "--title", title[:120], "--body", body], text=True, capture_output=True, timeout=60, check=True)
    url = created.stdout.strip()
    return int(url.rstrip("/").rsplit("/", 1)[1]), url, True
