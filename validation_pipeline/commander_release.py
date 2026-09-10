"""Guarded release-candidate publisher for hosted Commander GOD mode."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field


CONFIRMATION = "DEPLOY NEW CHANGES"
ACTIVE = {"preparing", "queued", "running"}
TERMINAL = {"succeeded", "failed"}
GITHUB_REPOSITORY = "AndroidJedi/ptw"
BRANCH_PREFIX = "god-deploy/"
MAX_CHANGED_FILES = 500
PROTECTED_EXACT = {
    ".dockerignore", ".firebaserc", "AGENTS.md", "docker-compose.commander.yml",
    "docker-compose.validation.yml", "firebase.json", "requirements-commander-god.txt",
}
PROTECTED_PREFIXES = (
    ".github/", "commander_god/", "db/migrations/", "deploy/", "scripts/",
    "skills/ptw-vps-operations/", "validation_pipeline/commander_release.py",
)
DOCKERFILES = {
    "commander/Dockerfile", "owner_gateway/Dockerfile", "validation_pipeline/Dockerfile",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class DeploymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    confirmation: str = Field(min_length=len(CONFIRMATION), max_length=len(CONFIRMATION))


class CommanderReleaseService:
    """Commit and publish one exact candidate without production credentials."""

    def __init__(
        self,
        repository: Path,
        state: Path,
        *,
        deployed_revision_file: Path,
        deploy_key: Path,
        known_hosts: Path,
        github_repository: str = GITHUB_REPOSITORY,
    ):
        self.repository = repository.resolve()
        self.state = state.resolve()
        self.deployed_revision_file = deployed_revision_file.resolve()
        self.deploy_key = deploy_key.resolve()
        self.known_hosts = known_hosts.resolve()
        self.github_repository = github_repository
        if not (self.repository / ".git").exists():
            raise ValueError("Commander release service requires the hosted Git checkout")
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database = self.state / "releases.sqlite3"
        self._last_workflow_poll = 0.0
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS deployments(
                    id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                    base_revision TEXT NOT NULL, revision TEXT,
                    branch TEXT NOT NULL, status TEXT NOT NULL,
                    error_code TEXT, workflow_url TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_deployment ON deployments((1))
                    WHERE status IN ('preparing','queued','running');
            """)
            db.execute(
                "UPDATE deployments SET status='failed',error_code='controller_restart',updated_at=? "
                "WHERE status='preparing'", (now(),),
            )
        self.database.chmod(0o600)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _git(self, *arguments: str, environment: dict[str, str] | None = None) -> str:
        return subprocess.check_output(
            ["git", "-C", str(self.repository), *arguments],
            text=True, stderr=subprocess.DEVNULL, env=environment,
        ).strip()

    def _deployed_revision(self) -> str:
        try:
            revision = self.deployed_revision_file.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise RuntimeError("The deployed PTW revision is unavailable") from error
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise RuntimeError("The deployed PTW revision is invalid")
        try:
            resolved = self._git("rev-parse", f"{revision}^{{commit}}")
        except subprocess.CalledProcessError as error:
            raise RuntimeError("The hosted checkout does not contain the deployed revision") from error
        if resolved != revision:
            raise RuntimeError("The deployed PTW revision does not match the hosted checkout")
        return revision

    def _changed_files(self, base_revision: str) -> list[str]:
        try:
            self._git("merge-base", "--is-ancestor", base_revision, "HEAD")
            committed = self._git("diff", "--name-only", "-z", f"{base_revision}..HEAD")
            working = self._git("diff", "--name-only", "-z", "HEAD")
            staged = self._git("diff", "--cached", "--name-only", "-z", "HEAD")
            untracked = self._git("ls-files", "--others", "--exclude-standard", "-z")
        except subprocess.CalledProcessError as error:
            raise RuntimeError("The hosted checkout is not based on the deployed revision") from error
        paths = sorted({path for value in (committed, working, staged, untracked) for path in value.split("\0") if path})
        if len(paths) > MAX_CHANGED_FILES:
            raise RuntimeError("The candidate changes too many files for mobile deployment")
        return paths

    @staticmethod
    def _protected(paths: list[str]) -> list[str]:
        return [
            path for path in paths
            if path in PROTECTED_EXACT or path in DOCKERFILES
            or any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)
            or any(part.startswith(".env") for part in Path(path).parts)
        ]

    def _candidate(self) -> dict[str, Any]:
        try:
            base = self._deployed_revision()
            files = self._changed_files(base)
            protected = self._protected(files)
            reason = None if self.deploy_key.is_file() and self.known_hosts.is_file() else "publisher_unconfigured"
        except RuntimeError as error:
            return {"available": False, "unavailable_reason": str(error), "changed_files": [], "protected_files": []}
        return {
            "available": reason is None,
            "unavailable_reason": reason,
            "base_revision": base,
            "changed_files": files,
            "protected_files": protected,
            "deployable": bool(files) and not protected and reason is None,
        }

    def _deployment(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        value = dict(row)
        value.pop("request_id", None)
        return value

    def _refresh(self, row: sqlite3.Row | None) -> sqlite3.Row | None:
        if row is None or row["status"] not in {"queued", "running"} or not row["revision"]:
            return row
        if time.monotonic() - self._last_workflow_poll < 20:
            return row
        self._last_workflow_poll = time.monotonic()
        params = urlencode({"head_sha": row["revision"], "event": "push", "per_page": 5})
        request = Request(
            f"https://api.github.com/repos/{self.github_repository}/actions/runs?{params}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "ptw-commander-release"},
        )
        try:
            with urlopen(request, timeout=8) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError):
            return row
        runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
        run = next((item for item in runs if item.get("head_sha") == row["revision"]), None)
        if not run:
            return row
        workflow_status = run.get("status")
        conclusion = run.get("conclusion")
        status = "running" if workflow_status != "completed" else "succeeded" if conclusion == "success" else "failed"
        error = None if status != "failed" else "release_workflow_failed"
        url = run.get("html_url") if isinstance(run.get("html_url"), str) else None
        with self._db() as db:
            db.execute(
                "UPDATE deployments SET status=?,error_code=?,workflow_url=?,updated_at=? WHERE id=?",
                (status, error, url, now(), row["id"]),
            )
            return db.execute("SELECT * FROM deployments WHERE id=?", (row["id"],)).fetchone()

    def detail(self) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM deployments ORDER BY rowid DESC LIMIT 1").fetchone()
        row = self._refresh(row)
        return {"candidate": self._candidate(), "deployment": self._deployment(row)}

    def create(self, body: DeploymentRequest) -> dict[str, Any]:
        if body.confirmation != CONFIRMATION:
            raise ValueError(f"Type {CONFIRMATION} to authorize this production deployment")
        with self._db() as db:
            prior = db.execute("SELECT * FROM deployments WHERE request_id=?", (str(body.request_id),)).fetchone()
            if prior:
                return self.detail()
            if db.execute("SELECT 1 FROM deployments WHERE status IN ('preparing','queued','running')").fetchone():
                raise ValueError("A production deployment is already active")
        candidate = self._candidate()
        if not candidate.get("deployable"):
            if candidate.get("protected_files"):
                raise ValueError("This candidate changes protected release infrastructure and requires the normal operations path")
            if not candidate.get("changed_files"):
                raise ValueError("There are no new GOD-mode changes to deploy")
            raise RuntimeError(candidate.get("unavailable_reason") or "Mobile deployment is unavailable")

        deployment_id = str(uuid4())
        branch = f"{BRANCH_PREFIX}{deployment_id}"
        stamp = now()
        with self._db() as db:
            db.execute(
                "INSERT INTO deployments(id,request_id,base_revision,branch,status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (deployment_id, str(body.request_id), candidate["base_revision"], branch, "preparing", stamp, stamp),
            )
        lock_path = self.repository / ".git" / "ptw-commander-operation.lock"
        try:
            with lock_path.open("a") as operation_lock:
                try:
                    fcntl.flock(operation_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as error:
                    raise ValueError("Commander is still changing the checkout") from error
                # Re-evaluate after taking the cross-container checkout lock.
                checked = self._candidate()
                if checked.get("base_revision") != candidate["base_revision"] or checked.get("changed_files") != candidate["changed_files"]:
                    raise ValueError("The GOD-mode checkout changed; refresh before deploying")
                if self._git("status", "--porcelain"):
                    self._git("add", "-A")
                    subprocess.run(
                        ["git", "-C", str(self.repository), "diff", "--cached", "--check"],
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    message = (
                        f"Prepare GOD-mode mobile release {deployment_id}\n\n"
                        f"PTW-Base-Revision: {candidate['base_revision']}"
                    )
                    self._git(
                        "-c", "user.name=PTW Commander", "-c", "user.email=commander@proove-them-wrong.com",
                        "commit", "--no-gpg-sign", "-m", message,
                    )
                revision = self._git("rev-parse", "HEAD")
                if revision == candidate["base_revision"]:
                    raise ValueError("There are no committed GOD-mode changes to deploy")
                environment = {**os.environ, "GIT_SSH_COMMAND": (
                    f"ssh -i {self.deploy_key} -o IdentitiesOnly=yes "
                    f"-o UserKnownHostsFile={self.known_hosts} -o StrictHostKeyChecking=yes"
                )}
                self._git(
                    "push", "git@github.com:" + self.github_repository + ".git",
                    f"HEAD:refs/heads/{branch}", environment=environment,
                )
            with self._db() as db:
                db.execute(
                    "UPDATE deployments SET revision=?,status='queued',updated_at=? WHERE id=?",
                    (revision, now(), deployment_id),
                )
        except ValueError:
            with self._db() as db:
                db.execute(
                    "UPDATE deployments SET status='failed',error_code='candidate_changed',updated_at=? WHERE id=?",
                    (now(), deployment_id),
                )
            raise
        except (OSError, subprocess.CalledProcessError):
            with self._db() as db:
                db.execute(
                    "UPDATE deployments SET status='failed',error_code='candidate_publish_failed',updated_at=? WHERE id=?",
                    (now(), deployment_id),
                )
            raise RuntimeError("The release candidate could not be published") from None
        return self.detail()


def create_app_from_env() -> FastAPI:
    token = os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("OWNER_GATEWAY_BRIDGE_TOKEN is required")
    service = CommanderReleaseService(
        Path(os.environ.get("PTW_COMMANDER_REPOSITORY", "/workspace")),
        Path(os.environ.get("PTW_RELEASE_STATE", "/var/lib/ptw/commander-release")),
        deployed_revision_file=Path(os.environ.get(
            "PTW_DEPLOYED_REVISION", "/run/ptw-deployed/deployed-revision",
        )),
        deploy_key=Path(os.environ.get("PTW_GITHUB_DEPLOY_KEY", "/run/ptw-github/id_ed25519")),
        known_hosts=Path(os.environ.get("PTW_GITHUB_KNOWN_HOSTS", "/run/ptw-github/known_hosts")),
    )
    app = FastAPI(title="PTW Commander Release", version="1.0.0", docs_url=None, redoc_url=None)

    def authorize(response: Response, x_ptw_owner_gateway_token: str = Header(default="")):
        response.headers["Cache-Control"] = "no-store"
        if x_ptw_owner_gateway_token != token:
            raise HTTPException(401, "unauthorized")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    router = APIRouter(
        prefix="/internal/v1/settings/commander/deployments",
        dependencies=[Depends(authorize)],
    )

    @router.get("")
    def detail():
        return service.detail()

    @router.post("", status_code=202)
    def deploy(body: DeploymentRequest):
        try:
            return service.create(body)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from None

    app.include_router(router)
    return app
