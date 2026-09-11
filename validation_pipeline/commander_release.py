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
import tempfile
import threading
import stat
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field


CONFIRMATION = "DEPLOY NEW CHANGES"
WORKFLOW_POLL_SECONDS = 90
ACTIVE = {"preparing", "queued", "running"}
TERMINAL = {"succeeded", "failed"}
GITHUB_REPOSITORY = "AndroidJedi/ptw"
BRANCH_PREFIX = "god-deploy/"
MAX_CHANGED_FILES = 500
REQUEST_PATH = ".ptw-release-request.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class DeploymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    # Older clients can still send the old confirmation; authenticated owner
    # POSTs are the authorization boundary, not a second magic-word dialog.
    confirmation: str | None = None
    chat_id: UUID | None = None
    owner_message_id: UUID | None = None


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
        # A fresh controller must reconcile an active workflow immediately;
        # only subsequent refreshes are rate-limited.
        self._last_workflow_poll = float("-inf")
        self._preparing = set()
        self._create_lock = threading.RLock()
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
            columns = {r[1] for r in db.execute("PRAGMA table_info(deployments)")}
            for column in ("request_revision", "chat_id", "owner_message_id"):
                if column not in columns:
                    db.execute(f"ALTER TABLE deployments ADD COLUMN {column} TEXT")
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
        configured = subprocess.run(["git", "-C", str(self.repository), "config", "--name-only", "--get-regexp", r"^filter\."],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        filters = []
        for key in configured.stdout.splitlines():
            if key.startswith("filter.") and key.rsplit(".", 1)[-1] in {"clean", "smudge", "process", "required"}:
                filters.extend(["-c", key + ("=false" if key.endswith(".required") else "=")])
        return subprocess.check_output(
            ["git", "-C", str(self.repository), "--git-dir=" + str(self.repository / ".git"),
             "--work-tree=" + str(self.repository), "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
             "-c", "credential.helper=", "-c", "protocol.allow=never", "-c", "protocol.ext.allow=never",
             "-c", "protocol.ssh.allow=always", "-c", "protocol.https.allow=always", "-c", "ssh.variant=ssh", *filters, *arguments],
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
        return [path for path in paths if any(part.startswith(".env") and not part.endswith(".example") for part in Path(path).parts)]

    def _request_commit(self, base: str, revision: str, identifier: str) -> str:
        """Publish trusted workflow bytes with only an immutable request added.

        A private Git index leaves the owner's checkout and index untouched.
        Candidate code cannot replace the workflow performing its own release.
        """
        manifest = json.dumps({"version": 2, "id": identifier, "base_revision": base,
                               "revision": revision, "candidate_branch": f"god-candidate/{identifier}"}, sort_keys=True)
        blob = subprocess.check_output(["git", "-C", str(self.repository), "hash-object", "-w", "--stdin"],
                                       input=manifest, text=True).strip()
        with tempfile.TemporaryDirectory(prefix="release-index-", dir=self.state) as temporary:
            environment = {**os.environ, "GIT_INDEX_FILE": str(Path(temporary) / "index")}
            self._git("read-tree", base, environment=environment)
            self._git("update-index", "--add", "--cacheinfo", f"100644,{blob},{REQUEST_PATH}", environment=environment)
            tree = self._git("write-tree", environment=environment)
            return self._git("-c", "user.name=PTW Commander", "-c", "user.email=commander@proove-them-wrong.com",
                             "commit-tree", tree, "-p", base, "-m", f"Deploy PTW candidate {identifier}")

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
        receipt_path = self.deployed_revision_file.parent / "commander-releases" / (row["id"] + ".json")
        try:
            receipt = json.loads(receipt_path.read_text())
            if receipt.get("id") == row["id"] and receipt.get("revision") == row["revision"] and receipt.get("phase") in {
                "preparing", "application", "hosting", "infrastructure", "accepted", "rolled_back", "recovery_failed",
            }:
                value["phase"] = receipt["phase"]
        except (OSError, ValueError):
            pass
        return value

    def _refresh(self, row: sqlite3.Row | None) -> sqlite3.Row | None:
        if row is None or row["status"] not in {"preparing", "queued", "running"}:
            return row
        if row["status"] == "preparing":
            if row["id"] in self._preparing:
                return row
            if row["request_revision"]:
                try:
                    remote = self._git("ls-remote", "https://github.com/" + self.github_repository + ".git", "refs/heads/" + row["branch"])
                except subprocess.CalledProcessError:
                    return row
                if not remote.startswith(row["request_revision"] + "\t"):
                    with self._db() as db:
                        db.execute("UPDATE deployments SET status='failed',error_code='candidate_publish_interrupted' WHERE id=?", (row["id"],))
                        return db.execute("SELECT * FROM deployments WHERE id=?", (row["id"],)).fetchone()
                with self._db() as db:
                    db.execute("UPDATE deployments SET status='queued' WHERE id=?", (row["id"],))
                    row = db.execute("SELECT * FROM deployments WHERE id=?", (row["id"],)).fetchone()
            else:
                with self._db() as db:
                    db.execute("UPDATE deployments SET status='failed',error_code='candidate_prepare_interrupted' WHERE id=?", (row["id"],))
                    return db.execute("SELECT * FROM deployments WHERE id=?", (row["id"],)).fetchone()
        if time.monotonic() - self._last_workflow_poll < WORKFLOW_POLL_SECONDS:
            return row
        self._last_workflow_poll = time.monotonic()
        workflow_revision = row["request_revision"] or row["revision"]
        params = urlencode({"head_sha": workflow_revision, "event": "push", "per_page": 5})
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
        run = next((item for item in runs if item.get("head_sha") == workflow_revision), None)
        if not run:
            return row
        workflow_status = run.get("status")
        conclusion = run.get("conclusion")
        status = "running" if workflow_status != "completed" else "succeeded" if conclusion == "success" else "failed"
        if workflow_status == "completed":
            try:
                deployed = self._deployed_revision()
            except RuntimeError:
                deployed = None
            if deployed == row["revision"] and conclusion != "success":
                status = "bookkeeping_required"
            elif conclusion == "success" and deployed != row["revision"]:
                status = "failed"
        error = None if status != "failed" else "release_workflow_failed"
        url = run.get("html_url") if isinstance(run.get("html_url"), str) else None
        with self._db() as db:
            db.execute(
                "UPDATE deployments SET status=?,error_code=?,workflow_url=?,updated_at=? WHERE id=?",
                (status, error, url, now(), row["id"]),
            )
            return db.execute("SELECT * FROM deployments WHERE id=?", (row["id"],)).fetchone()

    def detail(self, chat_id: str | None = None) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM deployments ORDER BY rowid DESC LIMIT 1").fetchone()
        row = self._refresh(row)
        with self._db() as db:
            history = db.execute("SELECT * FROM deployments WHERE chat_id=? ORDER BY rowid DESC LIMIT 30", (chat_id,)).fetchall() if chat_id else []
        return {"candidate": self._candidate(), "deployment": self._deployment(row), "history": [self._deployment(r) for r in history]}

    def create(self, body: DeploymentRequest) -> dict[str, Any]:
        with self._create_lock:
            return self._create(body)

    def _create(self, body: DeploymentRequest) -> dict[str, Any]:
        if body.confirmation is not None and body.confirmation != CONFIRMATION:
            raise ValueError(f"Type {CONFIRMATION} to authorize this production deployment")
        with self._db() as db:
            prior = db.execute("SELECT * FROM deployments WHERE request_id=?", (str(body.request_id),)).fetchone()
            if prior:
                if prior["chat_id"] != (str(body.chat_id) if body.chat_id else None) or prior["owner_message_id"] != (str(body.owner_message_id) if body.owner_message_id else None):
                    raise ValueError("Request UUID belongs to another deployment instruction")
                return {"candidate": self._candidate(), "deployment": self._deployment(self._refresh(prior))}
            if db.execute("SELECT 1 FROM deployments WHERE status IN ('preparing','queued','running')").fetchone():
                raise ValueError("A production deployment is already active")
        candidate = self._candidate()
        if not candidate.get("deployable"):
            if candidate.get("protected_files"):
                raise ValueError("Runtime secret files cannot be included in a source release")
            if not candidate.get("changed_files"):
                raise ValueError("There are no new GOD-mode changes to deploy")
            raise RuntimeError(candidate.get("unavailable_reason") or "Mobile deployment is unavailable")

        deployment_id = str(uuid4())
        self._preparing.add(deployment_id)
        branch = f"{BRANCH_PREFIX}{deployment_id}"
        stamp = now()
        with self._db() as db:
            db.execute(
                "INSERT INTO deployments(id,request_id,base_revision,branch,status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (deployment_id, str(body.request_id), candidate["base_revision"], branch, "preparing", stamp, stamp),
            )
            db.execute("UPDATE deployments SET chat_id=?,owner_message_id=? WHERE id=?",
                       (str(body.chat_id) if body.chat_id else None, str(body.owner_message_id) if body.owner_message_id else None, deployment_id))
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
                    # Never execute owner-controlled hooks or clean filters in
                    # the publisher, which alone can read its publishing key.
                    for name in checked["changed_files"]:
                        path = self.repository / name
                        if not path.exists() and not path.is_symlink():
                            self._git("update-index", "--force-remove", "--", name)
                            continue
                        info = path.lstat()
                        if stat.S_ISLNK(info.st_mode):
                            content, mode = os.readlink(path).encode(), "120000"
                        elif stat.S_ISREG(info.st_mode):
                            content = path.read_bytes()
                            mode = "100755" if info.st_mode & stat.S_IXUSR else "100644"
                        else:
                            raise ValueError("Release candidate contains an unsupported file type")
                        blob = subprocess.check_output(["git", "-C", str(self.repository), "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "hash-object", "--no-filters", "-w", "--stdin"], input=content).decode().strip()
                        self._git("update-index", "--add", "--cacheinfo", f"{mode},{blob},{name}")
                    self._git("diff", "--cached", "--check")
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
                request_revision = self._request_commit(candidate["base_revision"], revision, deployment_id)
                with self._db() as db:
                    db.execute("UPDATE deployments SET revision=?,request_revision=? WHERE id=?", (revision, request_revision, deployment_id))
                environment = {**os.environ, "GIT_SSH_COMMAND": (
                    f"ssh -i {self.deploy_key} -o IdentitiesOnly=yes "
                    f"-o UserKnownHostsFile={self.known_hosts} -o StrictHostKeyChecking=yes"
                )}
                self._git(
                    "push", "--atomic", "git@github.com:" + self.github_repository + ".git",
                    f"{revision}:refs/heads/god-candidate/{deployment_id}",
                    f"{request_revision}:refs/heads/{branch}", environment=environment,
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
                    # A disconnected push can have succeeded remotely. Keep
                    # its exact request revision reconcilable instead of
                    # misreporting failure and permitting a second rollout.
                    "UPDATE deployments SET status=CASE WHEN request_revision IS NOT NULL THEN 'preparing' ELSE 'failed' END,"
                    "error_code=CASE WHEN request_revision IS NOT NULL THEN NULL ELSE 'candidate_publish_failed' END,updated_at=? WHERE id=?",
                    (now(), deployment_id),
                )
            raise RuntimeError("Candidate publication needs reconciliation; retry the same request") from None
        finally:
            self._preparing.discard(deployment_id)
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
    def detail(chat_id: UUID | None = None):
        return service.detail(str(chat_id) if chat_id else None)

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
