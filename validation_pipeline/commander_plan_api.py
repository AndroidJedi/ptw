"""Private ephemeral Plan worker. Compose mounts /workspace read-only."""
from contextlib import asynccontextmanager
import os
from pathlib import Path
import shutil
import threading
import time
from uuid import uuid4

from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from .commander_chat import SAFE_ENV
from .commander_rpc import CodexRPC, RPCRejected


class Call(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: str
    params: dict


def create_app_from_env():
    token = os.environ["PTW_COMMANDER_PLAN_TOKEN"]
    if not token:
        raise RuntimeError("A separate Plan worker token is required")
    sessions = {}
    lock = threading.RLock()
    stopped = threading.Event()

    def reap():
        while not stopped.wait(5):
            expired = []
            with lock:
                for identifier, item in list(sessions.items()):
                    if time.monotonic() - item["seen"] > 60:
                        expired.append(item)
                        del sessions[identifier]
            for item in expired:
                if item.get("rpc"):
                    item["rpc"].close()

    @asynccontextmanager
    async def lifespan(app):
        worker = threading.Thread(target=reap, daemon=True)
        worker.start()
        yield
        stopped.set()
        with lock:
            remaining = list(sessions.values())
            sessions.clear()
        for item in remaining:
            if item.get("rpc"):
                item["rpc"].close()
        worker.join(timeout=6)

    def authorize(x_ptw_owner_gateway_token: str = Header(default="")):
        if x_ptw_owner_gateway_token != token:
            raise HTTPException(401, "unauthorized")

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    def session(identifier):
        with lock:
            if identifier not in sessions:
                raise HTTPException(404, "Plan session expired")
            item = sessions[identifier]
            item["seen"] = time.monotonic()
            return item

    @app.post("/session", dependencies=[Depends(authorize)])
    def start():
        with lock:
            if sessions:
                raise HTTPException(409, "A Plan session is already active")
            identifier = str(uuid4())
            item = {"events": [], "cursor": 0, "seen": time.monotonic()}
            sessions[identifier] = item
        try:
            def event(value):
                with lock:
                    item["cursor"] += 1
                    item["events"].append({"id": item["cursor"], "value": value})
            home = Path("/tmp/ptw-plan-home")
            home.mkdir(mode=0o700, exist_ok=True)
            shutil.copyfile(os.environ["PTW_CODEX_CREDENTIAL"], home / "auth.json")
            (home / "auth.json").chmod(0o600)
            env = {k: v for k, v in os.environ.items() if k in SAFE_ENV}
            env["CODEX_HOME"] = str(home)
            item["rpc"] = CodexRPC(os.environ["CODEX_EXECUTABLE"], Path("/workspace"), env, event)
            return {"id": identifier}
        except Exception:
            with lock:
                sessions.pop(identifier, None)
            raise

    @app.post("/session/{identifier}/request", dependencies=[Depends(authorize)])
    def request(identifier: str, body: Call):
        if body.method not in {"thread/start", "turn/start", "turn/steer", "turn/interrupt"}:
            raise HTTPException(400, "Unsupported Plan method")
        params = dict(body.params)
        if body.method == "thread/start":
            params.update(cwd="/workspace", ephemeral=True, sandbox="danger-full-access", approvalPolicy="never")
            params["dynamicTools"] = [t for t in params.get("dynamicTools", []) if t.get("name") == "conversation_history"]
        if body.method == "turn/start" and "collaborationMode" in params:
            params["collaborationMode"]["mode"] = "plan"
        try:
            return session(identifier)["rpc"].request(body.method, params)
        except RPCRejected:
            raise HTTPException(409, "Runtime explicitly rejected the request") from None

    @app.post("/session/{identifier}/respond", dependencies=[Depends(authorize)])
    def respond(identifier: str, body: dict):
        session(identifier)["rpc"].respond(body["id"], body["result"])
        return {"ok": True}

    @app.get("/session/{identifier}/events", dependencies=[Depends(authorize)])
    def events(identifier: str, after: int = 0):
        with lock:
            item = session(identifier)
            item["events"] = [e for e in item["events"] if e["id"] > after]
            return {"events": item["events"][:200]}

    @app.delete("/session/{identifier}", dependencies=[Depends(authorize)])
    def close(identifier: str):
        with lock:
            item = sessions.pop(identifier, None)
        if item:
            item["rpc"].close()
        return {"ok": True}
    return app
