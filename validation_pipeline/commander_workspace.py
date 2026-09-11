"""Durable Commander conversation orchestration over ephemeral Codex app-server."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .commander_chat import CommanderChatService as LegacyChatService, ChatMessage, Preferences, QuestionAnswer, SAFE_ENV, now, safe_text
from .commander_rpc import CodexRPC, PlanRPC, RPCRejected

POLICY = """You are Commander, the PTW owner's development agent in GOD mode.
Read AGENTS.md and the relevant canonical skills. Follow the owner's latest
request across application code, infrastructure, tests and skills. Preserve other
owner edits. Inspect files before acting; previous messages do not prove state.
Use the selected collaboration mode: Plan explores and discusses without edits;
Build implements. Continue dialogue and answer owner questions normally.
The host exposes deployment tools. An explicit owner deploy instruction authorizes
release without another confirmation. After implementing and checking the requested
work, call request_deployment. It queues release after this turn finishes. Never
claim deployment completed from this tool: report its queued status accurately.
If blocked or checks fail, explain and do not call request_deployment. Use
cancel_deployment when the owner cancels a previous deploy instruction.
Deployment covers all versioned PTW source, including infrastructure and migrations.
Never operate production via shell, read secrets, restart the hosting API, or push
Git yourself; the host handles release. Never put credentials or raw tool logs in
messages. Images are temporary context for this turn only.
Reply in the owner's language. Send concise progress updates. Ask clarifying
questions with request_user_input when useful; answers continue the same task.
Use conversation_history to retrieve older context when the transcript is bounded.
"""


def safe_json(value, *, sort_keys=False):
    """Redact string leaves before encoding, never redact serialized JSON."""
    def clean(item):
        if isinstance(item, str):
            return safe_text(item)
        if isinstance(item, list):
            return [clean(child) for child in item]
        if isinstance(item, dict):
            return {key: "[redacted]" if key.lower() in {"token", "password", "secret", "api_key", "access_token", "refresh_token"} and isinstance(child, str) else clean(child) for key, child in item.items()}
        return item
    return json.dumps(clean(value), ensure_ascii=False, sort_keys=sort_keys)


def authorizes_deployment(message: str) -> bool:
    # Deployment is an owner action, never a substring match in a quoted example,
    # explanation, code fence, negative instruction, or historical assistant text.
    text = re.sub(r"```[\s\S]*?```|`[^`]*`|\"[^\"]*\"|“[^”]*”", "", message.lower())
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))
    if "?" in text:
        return False
    if re.search(r"\b(?:don['’]?t|do not|never|without|не)\s+(?:ever\s+)?(?:deploy|release|ship|розгортай|розгортання)\b|^\s*(?:why|explain|how|чому|поясни)\b", text):
        return False
    return bool(re.search(r"(?:^|[.!\n])\s*(?:(?:ok|so|please)[, ]+)*(?:deploy|ship it|release (?:it|these|the changes)|розгорни|розгорнути|задеплой)\b|\b(?:and|then)\s+deploy\b", text))


class CommanderWorkspaceService(LegacyChatService):
    def __init__(self, *args, plan_url: str = "", plan_token: str = "", bridge_token: str = "", release_url: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.plan_url, self.bridge_token, self.release_url = plan_url, bridge_token, release_url
        self.plan_token = plan_token
        self.rpc = None
        self.native_thread = None
        self.native_turn = None
        self.active_chat = None
        self.active_id = None
        self._cap_lock = threading.Lock()
        self._capabilities = None
        self._cap_time = 0.
        self._done = threading.Event()
        self._native_status = ""
        self._rpc_questions = {}
        self._deploy_ready = False
        self._execution_mode = "build"
        self._steering = []
        self._accepting = False
        self._finished = threading.Condition(self._lock)
        with self._db() as db:
            for table, columns in {
                "chats": {"preferences_json": "TEXT NOT NULL DEFAULT '{}'", "deploy_owner_id": "TEXT", "context_summary": "TEXT NOT NULL DEFAULT ''"},
                "turns": {"mode": "TEXT NOT NULL DEFAULT 'build'", "model": "TEXT", "effort": "TEXT", "reply_to_message_id": "TEXT", "submission_json": "TEXT NOT NULL DEFAULT '{}'"},
            }.items():
                existing = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
                for column, definition in columns.items():
                    if column not in existing:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL,
                    turn_id TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS events_chat ON events(chat_id,id);
                CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, turn_id TEXT NOT NULL,
                    payload TEXT NOT NULL, status TEXT NOT NULL, answers TEXT, answer_request_id TEXT UNIQUE);
                CREATE TABLE IF NOT EXISTS release_handoffs(request_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL, owner_message_id TEXT NOT NULL, status TEXT NOT NULL, response TEXT);
            """)
            db.execute("UPDATE questions SET status='interrupted' WHERE status='pending'")
        self._handoff_stop = threading.Event()
        self._handoff_thread = threading.Thread(target=self._release_loop, daemon=True)
        self._handoff_thread.start()

    def create_chat(self):
        identifier = str(uuid4())
        with self._db() as db:
            db.execute("INSERT INTO chats(id,created_at) VALUES (?,?)", (identifier, now()))
        return self.chat(identifier)

    def chat(self, chat_id: str, before: int | None = None, limit: int = 60):
        limit = max(1, min(limit, 100))
        with self._db() as db:
            row = db.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
            if row is None:
                raise KeyError(chat_id)
            rows = db.execute("SELECT rowid AS cursor,* FROM turns WHERE chat_id=? AND rowid<? ORDER BY rowid DESC LIMIT ?",
                              (chat_id, before or 9223372036854775807, limit + 1)).fetchall()
            more = len(rows) > limit
            turns = []
            for item in reversed(rows[:limit]):
                value = dict(item)
                value["attachments"] = json.loads(value.pop("attachments_json"))
                value.pop("submission_json", None)
                turns.append(value)
            questions = [dict(q) for q in db.execute("SELECT * FROM questions WHERE chat_id=? ORDER BY rowid DESC LIMIT 30", (chat_id,))]
            for question in questions:
                question["payload"] = json.loads(question["payload"])
                question["answers"] = json.loads(question["answers"]) if question["answers"] else None
            cursor = db.execute("SELECT COALESCE(max(id),0) FROM events WHERE chat_id=?", (chat_id,)).fetchone()[0]
            handoffs = [dict(h) for h in db.execute("SELECT * FROM release_handoffs WHERE chat_id=? ORDER BY rowid DESC LIMIT 20", (chat_id,))]
        return {"id": chat_id, "turns": turns, "preferences": json.loads(row["preferences_json"]),
                "questions": questions, "event_cursor": cursor, "has_more": more,
                "before": turns[0]["cursor"] if turns else None, "releases": handoffs}

    def event(self, kind, payload, chat_id=None, turn_id=None):
        chat_id = chat_id or self.active_chat
        if not chat_id:
            return
        encoded = safe_json(payload)
        with self._db() as db:
            db.execute("INSERT INTO events(chat_id,turn_id,kind,payload,created_at) VALUES (?,?,?,?,?)",
                       (chat_id, turn_id or self.active_id, kind, encoded, now()))

    def events(self, chat_id, after=0):
        with self._db() as db:
            if not db.execute("SELECT 1 FROM chats WHERE id=?", (chat_id,)).fetchone():
                raise KeyError(chat_id)
            rows = db.execute("SELECT * FROM events WHERE chat_id=? AND id>? ORDER BY id LIMIT 200", (chat_id, after)).fetchall()
        events = [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]
        return {"events": events, "cursor": events[-1]["id"] if events else after}

    def environment(self):
        env = {k: v for k, v in os.environ.items() if k in SAFE_ENV}
        runtime_home = self.state / "codex-home"
        runtime_home.mkdir(mode=0o700, exist_ok=True)
        source = self.credential_source or Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
        if source.is_file():
            temporary = runtime_home / "auth.json.next"
            shutil.copyfile(source, temporary)
            temporary.chmod(0o600)
            temporary.replace(runtime_home / "auth.json")
        env.update(CODEX_HOME=str(runtime_home), NO_COLOR="1", npm_config_cache=str(self.state / "npm-cache"))
        return env

    def capabilities(self):
        with self._cap_lock:
            if self._capabilities and time.monotonic() - self._cap_time < 300:
                return self._capabilities
            rpc = CodexRPC(self.codex_binary, self.repository, self.environment(), lambda _: None)
            try:
                models, cursor = [], None
                for _ in range(20):
                    result = rpc.request("model/list", {"limit": 100, "includeHidden": False, "cursor": cursor})
                    models.extend({"id": m["model"], "name": m["displayName"], "default_effort": m["defaultReasoningEffort"],
                                   "efforts": [e["reasoningEffort"] for e in m["supportedReasoningEfforts"]],
                                   "default": m.get("isDefault", False), "input_modalities": m.get("inputModalities", ["text", "image"])}
                                  for m in result["data"] if not m.get("hidden"))
                    cursor = result.get("nextCursor")
                    if not cursor:
                        break
                modes = rpc.request("collaborationMode/list", {})
                plan = any(m.get("mode") == "plan" for m in modes.get("data", []))
                if not models:
                    raise RuntimeError("No available Commander models")
                self._capabilities = {"models": models, "modes": ["build"] + (["plan"] if plan and (self.target == "local" or self.plan_url) else [])}
                self._cap_time = time.monotonic()
                return self._capabilities
            finally:
                rpc.close()

    def preferences(self, chat_id, body: Preferences):
        cap = self.capabilities()
        model = next((m for m in cap["models"] if m["id"] == body.model), None) if body.model else next((m for m in cap["models"] if m["default"]), cap["models"][0])
        if model is None or body.mode not in cap["modes"]:
            raise ValueError("Selected model or mode is unavailable. Refresh the model list and select an available option.")
        effort = body.effort or model["default_effort"]
        if effort not in model["efforts"]:
            raise ValueError("Selected effort is unavailable for this model.")
        value = {"mode": body.mode, "model": model["id"], "effort": effort}
        with self._db() as db:
            if not db.execute("SELECT 1 FROM chats WHERE id=?", (chat_id,)).fetchone():
                raise KeyError(chat_id)
            db.execute("UPDATE chats SET preferences_json=? WHERE id=?", (json.dumps(value), chat_id))
        return value

    def send(self, chat_id: str, body: ChatMessage):
        message = safe_text(body.message)
        submission = body.model_dump(mode="json", exclude={"attachments"})
        submission["message"] = message
        prepared = self._prepare_attachments(body.attachments)
        metadata = [m for m, _ in prepared]
        submission["attachments"] = metadata
        encoded = json.dumps(submission, sort_keys=True)
        with self._lock, self._db() as db:
            prior = db.execute("SELECT * FROM turns WHERE request_id=?", (str(body.request_id),)).fetchone()
            if prior:
                if prior["chat_id"] != chat_id or prior["submission_json"] != encoded:
                    raise ValueError("Request ID already belongs to a different message")
                return self.chat(chat_id)
            chat = self.chat(chat_id)
            if body.reply_to_message_id and not db.execute("SELECT 1 FROM turns WHERE id=? AND chat_id=? AND reply<>''",
                                                          (str(body.reply_to_message_id), chat_id)).fetchone():
                raise ValueError("Reply target is not an assistant message in this conversation")
            if self._closed:
                raise RuntimeError("Commander is stopped")
            settings = {**chat["preferences"], **{k: getattr(body, k) for k in ("mode", "model", "effort") if getattr(body, k) is not None}}
        settings = self.preferences(chat_id, Preferences(**settings))
        with self._finished, self._db() as db:
            while self._thread and self._thread.is_alive() and not self._accepting:
                self._finished.wait(timeout=1)
            working = self._thread and self._thread.is_alive()
            # Reconcile duplicates again after capabilities discovery (which can
            # run concurrently with another submission using the same UUID).
            prior = db.execute("SELECT chat_id,submission_json FROM turns WHERE request_id=?", (str(body.request_id),)).fetchone()
            if prior:
                if prior["chat_id"] != chat_id or prior["submission_json"] != encoded:
                    raise ValueError("Request ID already belongs to a different message")
                return self.chat(chat_id)
            if not working and db.execute("SELECT 1 FROM release_handoffs WHERE status='pending'").fetchone():
                raise ValueError("The completed changes are being handed to deployment. Retry this message shortly.")
            if working and self.active_chat != chat_id:
                raise ValueError("Commander is working in another conversation. Open that conversation to reply.")
            identifier = str(uuid4())
            skill = self._skill()
            if not working:
                lease = (self.repository / ".git" / "ptw-commander-operation.lock").open("a")
                try:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    lease.close()
                    raise ValueError("A Commander release is preparing; wait for it to finish") from None
                self._operation_lease = lease
            effective = settings if not working else self._effective
            for meta, data in prepared:
                path = self._attachment_path(identifier, meta["id"])
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                path.write_bytes(data)
                path.chmod(0o600)
            db.execute("INSERT INTO turns(id,chat_id,request_id,message,attachments_json,status,reply,skill_sha256,created_at,updated_at,mode,model,effort,reply_to_message_id,submission_json) VALUES (?,?,?,?,?,?, '',?,?,?,?,?,?,?,?)",
                       (identifier, chat_id, str(body.request_id), message, json.dumps(metadata), "steered" if working else "queued",
                        hashlib.sha256(skill.encode()).hexdigest(), now(), now(), effective["mode"], effective["model"], effective["effort"],
                        str(body.reply_to_message_id) if body.reply_to_message_id else None, encoded))
            if effective["mode"] == "build" and authorizes_deployment(message):
                db.execute("UPDATE chats SET deploy_owner_id=? WHERE id=?", (identifier, chat_id))
            elif re.search(r"\b(don['’]?t deploy|do not deploy|cancel deployment|не розгортай)\b", message.lower()):
                db.execute("UPDATE chats SET deploy_owner_id=NULL WHERE id=?", (chat_id,))
                self._deploy_ready = False
            db.commit()
            if working:
                self._steering.append(identifier)
            else:
                self.active_chat, self.active_id = chat_id, identifier
                self._effective = settings
                self._execution_mode = settings["mode"]
                self._cancel.clear()
                self._done.clear()
                self._native_status = ""
                self._deploy_ready = False
                self._steering = []
                self._accepting = True
                self._thread = threading.Thread(target=self._execute, args=(chat_id, identifier, skill), daemon=True)
                self._thread.start()
            return self.chat(chat_id)

    def _input(self, identifier):
        with self._db() as db:
            row = db.execute("SELECT * FROM turns WHERE id=?", (identifier,)).fetchone()
            text = row["message"]
            if row["reply_to_message_id"]:
                parent = db.execute("SELECT reply FROM turns WHERE id=?", (row["reply_to_message_id"],)).fetchone()
                text = "Replying to assistant message:\n" + parent["reply"] + "\nOwner reply:\n" + text
            attachments = json.loads(row["attachments_json"])
        result = [{"type": "text", "text": text}]
        for image in attachments:
            # Inline images also work in the separate read-only worker; only
            # metadata goes to durable storage and all native threads are ephemeral.
            import base64
            data = self._attachment_path(identifier, image["id"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != image["sha256"]:
                raise RuntimeError("Image integrity check failed")
            result.append({"type": "image", "url": "data:image/png;base64," + base64.b64encode(data).decode()})
        return result

    def _context(self, chat_id, turn_id):
        with self._db() as db:
            rows = db.execute("SELECT rowid AS cursor,id,message,reply,mode,status FROM turns WHERE chat_id=? AND rowid<(SELECT rowid FROM turns WHERE id=?) ORDER BY rowid",
                              (chat_id, turn_id)).fetchall()
            questions = [dict(q) for q in db.execute("SELECT turn_id,payload,answers,status FROM questions WHERE chat_id=? ORDER BY rowid", (chat_id,))]
        # The complete archive remains available through conversation_history.
        # Preserve all owner constraints and recent assistant conclusions; older
        # assistant messages can be retrieved by ID instead of exhausting context.
        history = [dict(r) for r in rows]
        if len(json.dumps(history)) > 160000:
            for item in history[:-12]:
                item["reply"] = item["reply"][:800] + "\n[Archived; retrieve by message ID if needed.]"
        if len(json.dumps(history)) > 200000:
            history = history[-40:]
            history.insert(0, {"notice": "Earlier conversation is archived. Before acting, retrieve earlier owner constraints using conversation_history."})
        context = {"transcript": history, "clarifications": questions[-30:]}
        encoded = json.dumps(context, ensure_ascii=False)
        with self._db() as db:
            db.execute("UPDATE chats SET context_summary=? WHERE id=?", (encoded, chat_id))
        return encoded

    def _notification(self, value):
        method, params = value.get("method", ""), value.get("params", {})
        if params.get("threadId") and self.native_thread and params["threadId"] != self.native_thread:
            return
        if method == "item/agentMessage/delta":
            delta = safe_text(params.get("delta", ""))
            with self._db() as db:
                db.execute("UPDATE turns SET reply=substr(reply || ?,1,100000),updated_at=? WHERE id=?", (delta, now(), self.active_id))
            self.event("text", {"message_id": self.active_id})
        elif method == "item/started":
            item = params.get("item", {})
            kind = item.get("type", "")
            if kind == "agentMessage":
                with self._db() as db:
                    row = db.execute("SELECT reply FROM turns WHERE id=?", (self.active_id,)).fetchone()
                    if row and row[0]:
                        db.execute("UPDATE turns SET reply=reply || '\n\n' WHERE id=?", (self.active_id,))
            elif kind in {"commandExecution", "fileChange", "dynamicToolCall", "webSearch", "plan"}:
                self.event("activity", {"type": kind})
        elif method == "item/plan/delta":
            delta = safe_text(params.get("delta", ""))
            with self._db() as db:
                db.execute("UPDATE turns SET reply=substr(reply || ?,1,100000),updated_at=? WHERE id=?", (delta, now(), self.active_id))
            self.event("plan", {"message_id": self.active_id})
        elif method == "item/tool/requestUserInput":
            identifier = str(uuid4())
            payload = {"questions": params.get("questions", []), "blocking": params.get("isBlocking", True)}
            with self._db() as db:
                db.execute("INSERT INTO questions(id,chat_id,turn_id,payload,status) VALUES (?,?,?,?,'pending')",
                           (identifier, self.active_chat, self.active_id, safe_json(payload)))
            self._rpc_questions[identifier] = value["id"]
            self.event("question", {"id": identifier, **payload})
        elif method == "item/tool/call":
            tool = params.get("tool")
            args = params.get("arguments", {})
            try:
                if tool == "conversation_history":
                    history = self.chat(self.active_chat, args.get("before"), 30)
                    result = {"turns": history["turns"], "before": history["before"], "has_more": history["has_more"]}
                elif tool == "request_deployment":
                    with self._db() as db:
                        owner = db.execute("SELECT deploy_owner_id FROM chats WHERE id=?", (self.active_chat,)).fetchone()[0]
                    if self._execution_mode != "build" or not owner or not self.release_url:
                        raise ValueError("Deployment requires an explicit owner deployment instruction in Build mode.")
                    self._deploy_ready = True
                    result = {"status": "handoff_after_turn", "message": "Release will start after this coding turn completes."}
                elif tool == "cancel_deployment":
                    with self._db() as db:
                        db.execute("UPDATE chats SET deploy_owner_id=NULL WHERE id=?", (self.active_chat,))
                    self._deploy_ready = False
                    result = {"status": "cancelled"}
                else:
                    raise ValueError("Unknown Commander tool")
                self.rpc.respond(value["id"], {"success": True, "contentItems": [{"type": "inputText", "text": json.dumps(result)}]})
            except (ValueError, KeyError) as error:
                self.rpc.respond(value["id"], {"success": False, "contentItems": [{"type": "inputText", "text": str(error)}]})
        elif method in {"turn/completed", "ptw/disconnected"}:
            self._native_status = params.get("turn", {}).get("status", "failed")
            self._done.set()
        elif "id" in value:
            # Coding execution is already bounded by its worker. No arbitrary
            # permission escalation or additional external tools are approved.
            self.rpc.respond(value["id"], {"decision": "decline"})

    def _execute(self, chat_id, turn_id, skill):
        error = None
        try:
            rpc = PlanRPC(self.plan_url, self.plan_token, self._notification) if self._execution_mode == "plan" and self.target == "hosted" else CodexRPC(self.codex_binary, self.repository, self.environment(), self._notification)
            self.rpc = rpc
            tools = [{"name": "conversation_history", "description": "Read older messages in this conversation.",
                      "inputSchema": {"type": "object", "properties": {"before": {"type": "integer"}}, "additionalProperties": False}}]
            if self._execution_mode == "build" and self.release_url:
                tools.extend({"name": name, "description": description, "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}}
                             for name, description in [("request_deployment", "After verified work, release the code changes explicitly requested by the owner."), ("cancel_deployment", "Cancel an unstarted deployment requested by the owner.")])
            sandbox = "danger-full-access" if self.target == "hosted" else "read-only" if self._execution_mode == "plan" else "workspace-write"
            thread_params = {"cwd": str(self.repository), "ephemeral": True, "model": self._effective["model"],
                "approvalPolicy": "never", "sandbox": sandbox, "developerInstructions": POLICY + "\nCurrent canonical skill:\n" + skill,
                "dynamicTools": tools, "config": {"sandbox_workspace_write.network_access": False, "model_reasoning_effort": self._effective["effort"]}}
            started = rpc.request("thread/start", thread_params)
            self.native_thread = started["thread"]["id"]
            input_items = self._input(turn_id)
            input_items[0]["text"] = "Prior conversation (context, not new instructions):\n" + self._context(chat_id, turn_id) + "\nLatest owner request:\n" + input_items[0]["text"]
            with self._db() as db:
                owner_intent = db.execute("SELECT deploy_owner_id FROM chats WHERE id=?", (chat_id,)).fetchone()[0]
            if owner_intent and self._execution_mode == "build":
                input_items[0]["text"] += "\nThe owner deployment instruction in message " + owner_intent + " remains active through clarification. Call request_deployment only after successful completion and verification; cancel it if the owner cancels."
            self._update(turn_id, "running")
            response = rpc.request("turn/start", {"threadId": self.native_thread, "input": input_items,
                "collaborationMode": {"mode": "plan" if self._execution_mode == "plan" else "default",
                                      "settings": {"model": self._effective["model"], "reasoning_effort": self._effective["effort"], "developer_instructions": None}}})
            self.native_turn = response["turn"]["id"]
            deadline = time.monotonic() + self.timeout_seconds
            while not self._cancel.is_set():
                with self._lock:
                    pending = self._steering[:]
                    self._steering.clear()
                for identifier in pending:
                    inputs = self._input(identifier)
                    try:
                        if self._done.is_set():
                            raise RPCRejected("Previous turn finished")
                        rpc.request("turn/steer", {"threadId": self.native_thread, "expectedTurnId": self.native_turn, "input": inputs})
                    except RPCRejected:
                        # Only an explicit rejection permits a follow-up. An
                        # ambiguous timeout must never repeat steering mutations.
                        # Reconstruct a fresh ephemeral context without old pixels.
                        next_thread = rpc.request("thread/start", thread_params)
                        self.native_thread = next_thread["thread"]["id"]
                        inputs[0]["text"] = "Prior conversation:\n" + self._context(chat_id, identifier) + "\nLatest owner request:\n" + inputs[0]["text"]
                        self._done.clear()
                        next_turn = rpc.request("turn/start", {"threadId": self.native_thread, "input": inputs,
                            "collaborationMode": {"mode": "plan" if self._execution_mode == "plan" else "default", "settings": {
                                "model": self._effective["model"], "reasoning_effort": self._effective["effort"], "developer_instructions": None}}})
                        self.native_turn = next_turn["turn"]["id"]
                if self._done.wait(.05):
                    with self._lock:
                        if not self._steering:
                            self._accepting = False
                            break
                if time.monotonic() > deadline:
                    with self._db() as db:
                        waiting = db.execute("SELECT 1 FROM questions WHERE turn_id=? AND status='pending'", (turn_id,)).fetchone()
                    if waiting:
                        deadline = time.monotonic() + 60
                    else:
                        error = "timeout"
                        break
            status = "cancelled" if self._cancel.is_set() else "completed" if self._native_status == "completed" and not error else "failed"
            with self._db() as db:
                row = db.execute("SELECT reply FROM turns WHERE id=?", (turn_id,)).fetchone()
                reply = row[0]
                db.execute("UPDATE turns SET reply=? WHERE id=?", (safe_text(reply), turn_id))
                if status == "completed" and not reply:
                    status, error = "failed", "invalid_reply"
                db.execute("UPDATE turns SET status=?,error_code=?,updated_at=? WHERE id=?", (status, error or ("execution_failed" if status == "failed" else None), now(), turn_id))
                db.execute("UPDATE questions SET status='interrupted' WHERE turn_id=? AND status='pending'", (turn_id,))
                if status == "completed" and self._deploy_ready:
                    owner = db.execute("SELECT deploy_owner_id FROM chats WHERE id=?", (chat_id,)).fetchone()[0]
                    if owner:
                        db.execute("INSERT INTO release_handoffs VALUES (?,?,?,?,'pending',NULL)", (str(uuid4()), chat_id, turn_id, owner))
                        db.execute("UPDATE chats SET deploy_owner_id=NULL WHERE id=?", (chat_id,))
            self.event("completed", {"status": status})
        except Exception:
            with self._db() as db:
                db.execute("UPDATE turns SET status='failed',error_code='execution_failed',updated_at=? WHERE id=?", (now(), turn_id))
                db.execute("UPDATE questions SET status='interrupted' WHERE turn_id=? AND status='pending'", (turn_id,))
            self.event("completed", {"status": "failed"})
        finally:
            with self._lock:
                self._accepting = False
            if self.rpc:
                self.rpc.close()
            with self._lock:
                self.rpc = None
                self.native_thread = self.native_turn = None
                if self._operation_lease:
                    self._operation_lease.close()
                    self._operation_lease = None
                self._rpc_questions.clear()
                shutil.rmtree(self.state / "temporary-images", ignore_errors=True)
                self._thread = None
                self._finished.notify_all()

    def answer(self, chat_id, question_id, body: QuestionAnswer):
        with self._lock, self._db() as db:
            row = db.execute("SELECT * FROM questions WHERE id=? AND chat_id=?", (question_id, chat_id)).fetchone()
            if not row:
                raise KeyError(question_id)
            encoded = safe_json(body.answers, sort_keys=True)
            if len(encoded) > 16000:
                raise ValueError("Answer is too long")
            if row["answer_request_id"] == str(body.request_id) and row["answers"] == encoded:
                return self.chat(chat_id)
            if row["status"] != "pending" or question_id not in self._rpc_questions or not self.rpc:
                raise ValueError("This question is no longer waiting. Send your answer as a follow-up message.")
            allowed = {q["id"] for q in json.loads(row["payload"])["questions"]}
            if set(body.answers) != allowed or any(not values or any(not isinstance(x, str) or len(x) > 8000 for x in values) for values in body.answers.values()):
                raise ValueError("Answer each question before sending")
            db.execute("UPDATE questions SET answers=?,answer_request_id=?,status='answered' WHERE id=?", (encoded, str(body.request_id), question_id))
            db.commit()
            self.rpc.respond(self._rpc_questions.pop(question_id), {"answers": {key: {"answers": value} for key, value in body.answers.items()}})
            self.event("answer", {"id": question_id, "answers": json.loads(encoded)})
            return self.chat(chat_id)

    def _release_loop(self):
        while not self._handoff_stop.wait(2):
            if not self.release_url or (self._thread and self._thread.is_alive()):
                continue
            with self._db() as db:
                rows = db.execute("SELECT * FROM release_handoffs WHERE status='pending'").fetchall()
            for row in rows:
                try:
                    response = httpx.post(self.release_url + "/internal/v1/settings/commander/deployments",
                        headers={"X-PTW-Owner-Gateway-Token": self.bridge_token}, timeout=30,
                        json={"request_id": row["request_id"], "chat_id": row["chat_id"], "owner_message_id": row["owner_message_id"]})
                    if response.status_code >= 500:
                        continue
                    status = "submitted" if response.is_success else "failed"
                    payload = response.json() if response.is_success else {"error": "Release could not start. Review the current candidate and retry Deploy."}
                    with self._db() as db:
                        db.execute("UPDATE release_handoffs SET status=?,response=? WHERE request_id=?", (status, safe_json(payload), row["request_id"]))
                    self.event("release", payload, row["chat_id"], row["turn_id"])
                except (httpx.HTTPError, ValueError):
                    continue

    def deploy_chat(self, chat_id, request_id):
        with self._lock, self._db() as db:
            chat = self.chat(chat_id)
            prior = db.execute("SELECT * FROM turns WHERE request_id=?", (request_id,)).fetchone()
            if prior:
                if prior["chat_id"] != chat_id or prior["submission_json"] != '{"action":"deploy"}':
                    raise ValueError("Request UUID belongs to a different instruction")
                return chat
            if not self.release_url or chat["preferences"].get("mode") == "plan":
                raise ValueError("Switch to Build to deploy completed changes")
            if self._thread or db.execute("SELECT 1 FROM release_handoffs WHERE status='pending'").fetchone():
                raise ValueError("Commander is still working or handing off a release")
            identifier = str(uuid4())
            db.execute("INSERT INTO turns(id,chat_id,request_id,message,attachments_json,status,reply,skill_sha256,created_at,updated_at,mode,submission_json) VALUES (?,?,?,'Deploy current changes','[]','completed','Deployment requested. Follow release progress below.',?,?,?,'build',?)",
                       (identifier, chat_id, request_id, hashlib.sha256(self._skill().encode()).hexdigest(), now(), now(), '{"action":"deploy"}'))
            db.execute("INSERT INTO release_handoffs VALUES (?,?,?,?,'pending',NULL)", (request_id, chat_id, identifier, identifier))
            db.commit()
            return self.chat(chat_id)

    def stop(self, chat_id, turn_id):
        if chat_id != self.active_chat or turn_id != self.active_id:
            raise KeyError(turn_id)
        self._cancel.set()
        with self._db() as db:
            db.execute("UPDATE chats SET deploy_owner_id=NULL WHERE id=?", (chat_id,))
        return self.chat(chat_id)

    def close(self):
        self._closed = True
        self._cancel.set()
        self._handoff_stop.set()
        worker = self._thread
        if worker:
            worker.join(timeout=35)
        self._handoff_thread.join(timeout=35)
        self._lease.close()
