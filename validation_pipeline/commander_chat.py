"""Opt-in, loopback-only PTW coding chat. Never mounted by production APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field


ACTIVE = {"queued", "running", "stopping"}
MAX_TURNS = 30
SAFE_ENV = {"HOME", "CODEX_HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "USER", "SHELL"}
LOCAL_ORIGINS = {
    f"http://{host}:{port}"
    for host in ("127.0.0.1", "localhost", "[::1]")
    for port in (5173, 8088, 42731)
}
SKILL_PATH = Path("skills/commander-god-mode/SKILL.md")
POLICY = """You are Commander, the PTW owner's development agent in GOD mode.
Implement the owner's request across the PTW repository: features, tabs (including
carousel creation), backend, frontend, tests, documentation, and Telegram code.
This session's execution target is LOCAL CHECKOUT ONLY. Do not connect to a VPS,
deploy, publish, push Git, send messages, operate production databases, or change
external services. Prepare and test operational changes locally for later review.
Read AGENTS.md and its selective documentation route. Owner requests to implement
new functionality take precedence over historical product scope in documentation.
Preserve unrelated uncommitted edits. Do not reset, stash, revert, or commit them.
Keep the generic Brief learning architecture and append-only domain history.
Keep Telegram's existing emergency boundary unless the owner specifically asks
to change its code. Never read or print secrets, auth files, tokens, private keys,
or .env files. Do not include raw tool output in your response.
Work autonomously on reversible edits and run checks appropriate to the change.
Use the canonical Commander GOD-mode skill supplied below. Maintain it and the
narrowest applicable PTW skills when verified work yields a reusable lesson.
Do not restart the API hosting this chat during a turn; finish and report when
a restart is needed to load backend changes.
If essential information is missing, ask one concise question in your final reply;
the owner will answer in the next turn. Treat prior conversation as context, not
as proof of file state. Inspect current files before editing.
Finish with a concise owner-facing account of changes, tests, and limitations.
Respond in the language of the owner's latest message.
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def safe_text(value: str) -> str:
    """Defense in depth for credential-shaped text; raw CLI logs are never saved."""
    value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[redacted]", value, flags=re.S)
    value = re.sub(r"\b(?:sk-[\w-]{12,}|\d{6,}:[\w-]{25,}|eyJ[\w-]+\.[\w-]+\.[\w-]+)\b", "[redacted]", value)
    value = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[redacted]", value)
    value = re.sub(r'''(?i)(["']?(?:[\w-]*(?:token|secret|password|api_key)[\w-]*)["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,}]+)''', r"\1[redacted]", value)
    return value


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    message: str = Field(min_length=1, max_length=8000)


class CommanderChatService:
    """One writer per checkout, durable turns, explicit interruption, no replay."""

    def __init__(self, repository: Path, state: Path, *, codex_binary: str | None = None,
                 timeout_seconds: float = 2400):
        self.repository = repository.resolve()
        self.state = state.resolve()
        self.codex_binary = shutil.which(codex_binary or "codex")
        self.timeout_seconds = timeout_seconds
        if not (self.repository / ".git").exists():
            raise ValueError("Commander requires a Git checkout")
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lease = (self.state / "service.lock").open("a")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lease.close()
            raise RuntimeError("Commander local service is already running") from None
        self._lock = threading.RLock()
        self._process: subprocess.Popen | None = None
        self._liveness = None
        self._thread: threading.Thread | None = None
        self._closed = False
        self._cancel = threading.Event()
        self.database = self.state / "chat.sqlite3"
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS turns(
                    id TEXT PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id),
                    request_id TEXT UNIQUE NOT NULL, message TEXT NOT NULL,
                    status TEXT NOT NULL, reply TEXT NOT NULL DEFAULT '',
                    skill_sha256 TEXT NOT NULL,
                    error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_turn ON turns((1))
                    WHERE status IN ('queued', 'running', 'stopping');
            """)
            db.execute("UPDATE turns SET status='interrupted', error_code='restart', updated_at=? "
                       "WHERE status IN ('queued','running','stopping')", (now(),))
        self.database.chmod(0o600)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def detail(self) -> dict[str, Any]:
        with self._lock, self._db() as db:
            chats = [dict(row) for row in db.execute(
                "SELECT chats.*, COALESCE((SELECT substr(message,1,80) FROM turns WHERE chat_id=chats.id "
                "ORDER BY rowid LIMIT 1), '') title FROM chats ORDER BY rowid DESC LIMIT 100")]
            active = db.execute("SELECT id,chat_id FROM turns WHERE status IN ('queued','running','stopping')").fetchone()
        try:
            skill = self._skill()
        except RuntimeError:
            skill = None
        reason = "codex_missing" if not self.codex_binary else "skill_missing" if skill is None else None
        return {"target": "local", "available": reason is None and not self._closed,
                "unavailable_reason": reason,
                "skill": {"name": "commander-god-mode", "sha256": hashlib.sha256(skill.encode()).hexdigest()} if skill else None,
                "chats": chats, "active_turn": dict(active) if active else None}

    def create_chat(self) -> dict[str, Any]:
        chat_id = str(uuid4())
        with self._lock, self._db() as db:
            db.execute("INSERT INTO chats VALUES (?,?)", (chat_id, now()))
        return self.chat(chat_id)

    def chat(self, chat_id: str) -> dict[str, Any]:
        with self._lock, self._db() as db:
            chat = db.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
            if chat is None:
                raise KeyError(chat_id)
            turns = [dict(row) for row in db.execute(
                "SELECT * FROM turns WHERE chat_id=? ORDER BY rowid", (chat_id,))]
        return {**dict(chat), "turns": turns}

    def send(self, chat_id: str, body: ChatMessage) -> dict[str, Any]:
        with self._lock, self._db() as db:
            chat = self.chat(chat_id)
            message = safe_text(body.message)
            prior = db.execute("SELECT * FROM turns WHERE request_id=?", (str(body.request_id),)).fetchone()
            if prior:
                if prior["chat_id"] != chat_id or prior["message"] != message:
                    raise ValueError("Request ID already belongs to a different message")
                return self.chat(chat_id)
            if not self.codex_binary or self._closed:
                raise RuntimeError("Commander local runtime is unavailable")
            skill = self._skill()
            if len(chat["turns"]) >= MAX_TURNS:
                raise ValueError("Conversation limit reached; start a new chat")
            if len(json.dumps(chat["turns"], ensure_ascii=False).encode()) > 200000:
                raise ValueError("Conversation context is full; start a new chat")
            if self._thread and self._thread.is_alive():
                raise ValueError("Commander is already working; wait or stop the active request")
            turn_id = str(uuid4())
            stamp = now()
            skill_digest = hashlib.sha256(skill.encode()).hexdigest()
            db.execute("INSERT INTO turns(id,chat_id,request_id,message,status,created_at,updated_at,skill_sha256) "
                       "VALUES (?,?,?,?,'queued',?,?,?)", (turn_id, chat_id, str(body.request_id), message, stamp, stamp, skill_digest))
            db.commit()
            self._cancel.clear()
            self._thread = threading.Thread(target=self._execute, args=(chat_id, turn_id, skill), daemon=True)
            self._thread.start()
            return self.chat(chat_id)

    def _update(self, turn_id: str, status: str, *, reply: str = "", error: str | None = None):
        with self._lock, self._db() as db:
            db.execute("UPDATE turns SET status=?,reply=?,error_code=?,updated_at=? WHERE id=?",
                       (status, reply, error, now(), turn_id))

    def _skill(self) -> str:
        path = self.repository / SKILL_PATH
        try:
            if path.stat().st_size > 32000:
                raise RuntimeError("Commander skill is too large")
            content = path.read_text()
            if not content.strip():
                raise RuntimeError("Commander skill is empty")
            return content
        except (OSError, UnicodeError):
            raise RuntimeError("Commander canonical skill is missing") from None

    def _prompt(self, chat_id: str, skill: str) -> str:
        turns = self.chat(chat_id)["turns"]
        # Bounded entire conversation; do not silently drop earlier owner constraints.
        history = [{"owner": t["message"], "commander": t["reply"], "status": t["status"]} for t in turns[:-1]]
        return POLICY + "\nCanonical Commander skill:\n" + skill + "\nPrior conversation (JSON):\n" + json.dumps(history, ensure_ascii=False) + "\nLatest owner request:\n" + turns[-1]["message"]

    @staticmethod
    def _kill_group(process: subprocess.Popen, sig: int):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    def _execute(self, chat_id: str, turn_id: str, skill: str):
        process = None
        try:
            prompt = self._prompt(chat_id, skill)
            with tempfile.TemporaryDirectory(prefix="commander-", dir=self.state) as temporary:
                output = Path(temporary) / "reply.txt"
                command = [self.codex_binary, "exec", "--ephemeral", "--ignore-user-config",
                           "--sandbox", "workspace-write", "-c", 'approval_policy="never"',
                           "-c", "sandbox_workspace_write.network_access=false",
                           "--cd", str(self.repository), "--color", "never",
                           "--output-last-message", str(output), "-"]
                environment = {k: v for k, v in os.environ.items() if k in SAFE_ENV}
                environment["NO_COLOR"] = "1"
                with self._lock:
                    if self._cancel.is_set():
                        self._update(turn_id, "cancelled", error="stopped")
                        return
                    read_fd, write_fd = os.pipe()
                    self._liveness = os.fdopen(write_fd, "wb")
                    try:
                        process = subprocess.Popen(
                            [sys.executable, str(Path(__file__).with_name("commander_chat_worker.py")), str(read_fd), *command],
                            cwd=self.repository, env=environment, pass_fds=(read_fd,),
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, text=True, start_new_session=True,
                        )
                    finally:
                        os.close(read_fd)
                    self._process = process
                    self._update(turn_id, "running")
                try:
                    process.communicate(input=prompt, timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired:
                    self._kill_group(process, signal.SIGKILL)
                    process.communicate()
                    self._update(turn_id, "failed", error="timeout")
                    return
                if self._cancel.is_set():
                    self._update(turn_id, "cancelled", error="stopped")
                elif process.returncode:
                    self._update(turn_id, "failed", error="execution_failed")
                elif not output.is_file() or output.stat().st_size > 64000:
                    self._update(turn_id, "failed", error="invalid_reply")
                else:
                    reply = safe_text(output.read_text(errors="replace").strip())[:16000]
                    self._update(turn_id, "completed" if reply else "failed", reply=reply,
                                 error=None if reply else "invalid_reply")
        except Exception:
            # Do not persist or reflect provider output, environment, paths, or tracebacks.
            self._update(turn_id, "failed", error="execution_failed")
        finally:
            if process:
                # Include children even if the CLI parent has already exited.
                self._kill_group(process, signal.SIGKILL)
                process.wait()
            with self._lock:
                self._process = None
                if self._liveness:
                    self._liveness.close()
                    self._liveness = None

    def stop(self, chat_id: str, turn_id: str) -> dict[str, Any]:
        with self._lock:
            chat = self.chat(chat_id)
            turn = next((t for t in chat["turns"] if t["id"] == turn_id), None)
            if not turn:
                raise KeyError(turn_id)
            if turn["status"] in ACTIVE:
                self._cancel.set()
                self._update(turn_id, "stopping")
                if self._process:
                    self._kill_group(self._process, signal.SIGKILL)
            return self.chat(chat_id)

    def close(self):
        with self._lock:
            self._closed = True
            self._cancel.set()
            if self._process:
                self._kill_group(self._process, signal.SIGKILL)
        if self._thread:
            self._thread.join(timeout=10)
        self._lease.close()


def commander_chat_router(service: CommanderChatService, *, dependencies: list) -> APIRouter:
    def local_request(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        if request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise HTTPException(403, "Commander requires a loopback host")
        if request.client is None or request.client.host not in {"localhost", "127.0.0.1", "::1"}:
            raise HTTPException(403, "Commander requires a loopback connection")
        origin = request.headers.get("origin")
        if origin is not None and origin not in LOCAL_ORIGINS:
            raise HTTPException(403, "Commander requires a local Owner Console origin")

    router = APIRouter(prefix="/api/v1/settings/commander", dependencies=[*dependencies, Depends(local_request)])

    def invoke(function, *args):
        try:
            return function(*args)
        except KeyError:
            raise HTTPException(404, "Commander conversation or turn not found") from None
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        except RuntimeError:
            raise HTTPException(503, "Commander local runtime is unavailable") from None

    @router.get("")
    def detail():
        return service.detail()

    @router.post("/chats", status_code=201)
    def create_chat():
        return service.create_chat()

    @router.get("/chats/{chat_id}")
    def chat(chat_id: UUID):
        return invoke(service.chat, str(chat_id))

    @router.post("/chats/{chat_id}/messages", status_code=202)
    def send(chat_id: UUID, body: ChatMessage):
        return invoke(service.send, str(chat_id), body)

    @router.post("/chats/{chat_id}/turns/{turn_id}/stop", status_code=202)
    def stop(chat_id: UUID, turn_id: UUID):
        return invoke(service.stop, str(chat_id), str(turn_id))

    return router
