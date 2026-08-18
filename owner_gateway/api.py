from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from .app_server import AppServerPlanner
from .annotations import region
from .auth import FirebaseVerifier, OwnerDependency, OwnerIdentity
from .control_store import ControlStore
from .execution import CommandRunner
from .platform import PlatformRepository
from .read_models import DomainReadModels
from .settings import Settings


def create_app(settings: Settings, verifier: FirebaseVerifier | None = None) -> FastAPI:
    store = ControlStore(settings.control_database_path)
    platform = PlatformRepository(settings.platform_database_url, settings.platform_owner_telegram_id)
    read = DomainReadModels(settings.idea_database_url, settings.commander_database_url)
    planner = AppServerPlanner(settings.codex_executable, settings.repository_path)
    runner = CommandRunner(settings.codex_executable, settings.repository_path, store, platform)
    owner = OwnerDependency(verifier or FirebaseVerifier(settings))
    tasks: set[asyncio.Task[Any]] = set()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(title="PTW Owner Gateway", version="1.0.0", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.public_origin], allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
    )

    def background(coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    def require_running() -> None:
        if platform.emergency_stop():
            raise HTTPException(
                status_code=423,
                detail="PTW emergency stop is active; resume it from Docs / System",
            )

    def require_laval_id(run_id: str) -> None:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", run_id):
            raise HTTPException(status_code=400, detail="invalid Laval run UUID")

    async def laval_bridge(
        method: str, path: str, *, body: Mapping[str, Any] | None = None, params: Mapping[str, Any] | None = None
    ) -> httpx.Response:
        if not settings.idea_service_token:
            raise HTTPException(status_code=503, detail="Idea Laval bridge is not configured")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.request(
                    method,
                    f"{settings.idea_service_url}{path}",
                    headers={"X-PTW-Owner-Gateway-Token": settings.idea_service_token},
                    json=dict(body) if body is not None else None,
                    params=dict(params or {}),
                )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=503, detail="Idea Laval service is unavailable") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(status_code=response.status_code, detail=detail or "Idea Laval request failed")
        return response

    async def propagate_emergency_stop(active: bool, actor: str) -> list[str]:
        if not settings.telegram_bot_token:
            raise HTTPException(status_code=503, detail="emergency bridge token is not configured")
        failures: list[str] = []
        targets = {
            "commander": f"{settings.commander_service_url}/internal/emergency-stop",
            "ideas": f"{settings.idea_service_url}/internal/emergency-stop",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            for name, url in targets.items():
                try:
                    response = await client.post(
                        url,
                        headers={"X-PTW-Bridge-Token": settings.telegram_bot_token},
                        json={"active": active, "actor": actor},
                    )
                    if response.status_code >= 400:
                        failures.append(name)
                except httpx.HTTPError:
                    failures.append(name)
        return failures

    async def build_plan(session_id: str, instruction: str) -> None:
        async def sink(event: dict[str, Any]) -> None:
            store.event(session_id, event)
        try:
            plan = await planner.plan(instruction, sink)
            store.set_plan(session_id, plan)
        except Exception as error:
            store.update(session_id, "failed", error=f"{type(error).__name__}: {str(error)[:1000]}")
            store.event(session_id, {"type": "plan.failed", "error": type(error).__name__})

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/overview")
    def overview(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return read.overview(platform.summary())

    @app.get("/api/v1/laval/runs")
    async def laval_runs(
        limit: int = Query(default=30, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await laval_bridge("GET", "/internal/web/laval/runs", params={"limit": limit})).json()

    @app.get("/api/v1/laval/providers")
    async def laval_providers(
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await laval_bridge("GET", "/internal/web/laval/providers")).json()

    @app.post("/api/v1/laval/runs")
    async def create_laval_run(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        payload = {"text": request.get("text"), "config": request.get("config") or {}, "mode": request.get("mode") or "demo", "actor": f"firebase:{identity.uid}"}
        return (await laval_bridge("POST", "/internal/web/laval/runs", body=payload)).json()

    @app.get("/api/v1/laval/runs/{run_id}")
    async def laval_run_status(
        run_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        return (await laval_bridge("GET", f"/internal/web/laval/runs/{run_id}")).json()

    @app.get("/api/v1/laval/runs/{run_id}/stages")
    async def laval_run_stages(
        run_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        return (await laval_bridge("GET", f"/internal/web/laval/runs/{run_id}/stages")).json()

    @app.get("/api/v1/laval/runs/{run_id}/show")
    async def laval_stage_output(
        run_id: str,
        stage: str,
        view: str | None = None,
        country: str | None = None,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        return (await laval_bridge(
            "GET", f"/internal/web/laval/runs/{run_id}/show",
            params={key: value for key, value in {"stage": stage, "view": view, "country": country}.items() if value},
        )).json()

    @app.get("/api/v1/laval/runs/{run_id}/export")
    async def export_laval_run(
        run_id: str,
        stage: str | None = None,
        format: str = Query(default="json", pattern="^(json|md)$"),
        _identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        require_laval_id(run_id)
        response = await laval_bridge(
            "GET", f"/internal/web/laval/runs/{run_id}/export",
            params={key: value for key, value in {"stage": stage, "format": format}.items() if value},
        )
        return Response(
            response.content,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            headers={"Content-Disposition": response.headers.get("content-disposition", "attachment"), "Cache-Control": "no-store, private"},
        )

    @app.post("/api/v1/laval/runs/{run_id}/{action}")
    async def control_laval_run(
        run_id: str,
        action: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        if action not in {"run", "pause", "resume", "approve", "rerun", "override"}:
            raise HTTPException(status_code=404, detail="unknown Laval action")
        if action != "pause":
            require_running()
        payload = {**dict(request), "actor": f"firebase:{identity.uid}"}
        return (await laval_bridge("POST", f"/internal/web/laval/runs/{run_id}/{action}", body=payload)).json()

    @app.get("/api/v1/posts")
    def posts(
        limit: int = Query(default=20, ge=1, le=100),
        review_status: str | None = Query(default=None, pattern="^(pending|reviewed)$"),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return read.posts(limit=limit, review_status=review_status)

    @app.post("/api/v1/posts")
    def create_post(request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        try:
            return read.create_single_post(
                request_text=str(request.get("request_text", "")), actor=f"firebase:{identity.uid}",
                policy_path=settings.commander_policy_path, asset_directory=settings.commander_asset_root,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/v1/creatives/{creative_id}/reviews")
    def review_creative(creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", creative_id):
            raise HTTPException(status_code=400, detail="invalid Creative UUID")
        try:
            raw_annotations = request.get("regions") or []
            if not isinstance(raw_annotations, list) or len(raw_annotations) > 100:
                raise ValueError("reviews support at most 100 annotations")
            annotations = tuple(region(item) for item in raw_annotations)
            rating = int(request.get("rating"))
            if rating not in range(1, 6):
                raise ValueError("rating must be 1..5")
            predicted = request.get("predicted_ctr")
            predicted_ctr = None if predicted is None else float(predicted)
            supersedes = request.get("supersedes_feedback_id")
            supersedes_feedback_id = None if supersedes is None else str(supersedes)
            if supersedes_feedback_id and not re.fullmatch(r"[0-9a-fA-F-]{36}", supersedes_feedback_id):
                raise ValueError("invalid superseded feedback UUID")
            return read.review(
                creative_id=creative_id, artifact_digest=str(request.get("artifact_digest", "")),
                rating=rating, comment=str(request.get("comment", "")), predicted_ctr=predicted_ctr,
                annotations=annotations, actor=f"firebase:{identity.uid}",
                policy_path=settings.commander_policy_path, asset_directory=settings.commander_asset_root,
                supersedes_feedback_id=supersedes_feedback_id,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/creatives/{creative_id}/reviews")
    def creative_reviews(creative_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", creative_id):
            raise HTTPException(status_code=400, detail="invalid Creative UUID")
        return {"items": read.creative_reviews(creative_id)}

    @app.get("/api/v1/artifacts/{digest}")
    def artifact(digest: str, _identity: OwnerIdentity = Depends(owner)) -> FileResponse:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise HTTPException(status_code=400, detail="invalid artifact digest")
        try:
            path = read.artifact_path(digest, settings.commander_asset_root)
        except (KeyError, PermissionError) as error:
            raise HTTPException(status_code=404, detail="artifact not found") from error
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store, private"})

    @app.get("/api/v1/jobs")
    def jobs(limit: int = Query(default=30, ge=1, le=100), _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        local = store.commands(limit)
        for item in local:
            item["mode"] = item["mode"]
            item["created_at"] = item["created_at"]
        return {"items": local + platform.state(max(0, limit - len(local))), "next_cursor": None}

    @app.post("/api/v1/jobs")
    @app.post("/api/v1/command-sessions")
    def create_job(request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        mode = str(request.get("mode", "plan"))
        instruction = str(request.get("instruction", "")).strip()
        if mode not in {"plan", "execute"} or not instruction or len(instruction) > 20_000:
            raise HTTPException(status_code=400, detail="mode and 1-20000 character instruction are required")
        command = store.create_command(mode, instruction)
        background(build_plan(command["id"], instruction))
        return command

    @app.get("/api/v1/command-sessions")
    def command_sessions(limit: int = Query(default=30, ge=1, le=100), _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return {"items": store.commands(limit), "next_cursor": None}

    @app.get("/api/v1/issues")
    def issues(limit: int = Query(default=30, ge=1, le=100), _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return {"items": platform.issues(limit), "next_cursor": None}

    @app.post("/api/v1/command-sessions/{session_id}/approve")
    def approve(session_id: str, request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        destructive_allowed = request.get("destructive_confirmation") == "EXECUTE DESTRUCTIVE PLAN"
        try:
            command = store.approve_once(
                session_id, str(request.get("plan_digest", "")),
                destructive_allowed=destructive_allowed,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="command session not found") from error
        except PermissionError as error:
            raise HTTPException(status_code=412, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        background(runner.execute(session_id))
        return command

    @app.post("/api/v1/jobs/{session_id}/cancel")
    @app.post("/api/v1/command-sessions/{session_id}/cancel")
    async def cancel(session_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, bool]:
        try:
            await runner.cancel(session_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="command session not found") from error
        return {"cancelled": True}

    @app.post("/api/v1/ws-tickets")
    def ws_ticket(request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, str]:
        path = str(request.get("path", ""))
        if path != "/api/v1/root-sessions" and not re.fullmatch(r"/api/v1/jobs/[0-9a-f-]{36}/events", path):
            raise HTTPException(status_code=400, detail="unsupported WebSocket path")
        return {"ticket": store.issue_ticket(identity.uid, path)}

    @app.websocket("/api/v1/jobs/{session_id}/events")
    async def job_events(websocket: WebSocket, session_id: str, ticket: str = Query(default="")) -> None:
        path = f"/api/v1/jobs/{session_id}/events"
        try:
            store.consume_ticket(ticket, path)
            store.command(session_id)
        except (PermissionError, KeyError):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        sequence = 0
        try:
            while True:
                events = store.events(session_id, sequence)
                for event in events:
                    sequence = event["sequence"]
                    await websocket.send_text(json.dumps(event, ensure_ascii=False))
                if store.command(session_id)["status"] in {"completed", "failed", "cancelled", "awaiting_approval"} and not events:
                    await websocket.close(code=1000)
                    return
                await asyncio.sleep(.5)
        except WebSocketDisconnect:
            return

    @app.websocket("/api/v1/root-sessions")
    async def root_session(websocket: WebSocket, ticket: str = Query(default="")) -> None:
        path = "/api/v1/root-sessions"
        try:
            uid = store.consume_ticket(ticket, path)
            metadata_id = store.start_root_session(uid)
        except (PermissionError, ValueError):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        reason = "client_closed"
        try:
            reader, writer = await asyncio.open_unix_connection(str(settings.root_broker_socket))
            writer.write(b'{"type":"terminal"}\n')
            await writer.drain()
            async def browser_to_broker() -> None:
                while True:
                    message = await websocket.receive_text()
                    writer.write((message + "\n").encode())
                    await writer.drain()
            async def broker_to_browser() -> None:
                while raw := await reader.readline():
                    await websocket.send_text(raw.decode().rstrip("\n"))
            done, pending = await asyncio.wait(
                {asyncio.create_task(browser_to_broker()), asyncio.create_task(broker_to_browser())},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            writer.close(); await writer.wait_closed()
            for task in done:
                if task.exception():
                    raise task.exception()
        except WebSocketDisconnect:
            reason = "client_disconnected"
        except Exception as error:
            reason = type(error).__name__
            await websocket.close(code=1011)
        finally:
            store.end_root_session(metadata_id, reason)

    @app.get("/api/v1/docs")
    def docs(limit: int = Query(default=50, ge=1, le=50), _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return {"items": read.docs(settings.repository_path, limit)}

    @app.get("/api/v1/system/health")
    def system_health(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        revision = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=settings.repository_path,
            text=True, capture_output=True, check=False, timeout=5,
        ).stdout.strip() or "unknown"
        return {
            "git_revision": revision,
            "services": {"gateway": "ok", "root_broker": "ok" if settings.root_broker_socket.exists() else "unavailable"},
            "emergency_stop": platform.emergency_stop(),
            "reset": {"permitted": True},
        }

    @app.post("/api/v1/system/emergency-stop")
    async def emergency_stop(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        active = request.get("active") is True
        actor = f"firebase:{identity.uid}"
        if active:
            platform.set_emergency_stop(True, actor=actor)
            failures = await propagate_emergency_stop(True, actor)
        else:
            failures = await propagate_emergency_stop(False, actor)
            if not failures:
                platform.set_emergency_stop(False, actor=actor)
        if failures:
            raise HTTPException(
                status_code=503,
                detail=(
                    "emergency stop remains active; unavailable services: "
                    + ", ".join(failures)
                ),
            )
        return {"emergency_stop": active}

    @app.post("/api/v1/system/reset")
    async def reset(request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        if request.get("confirmation") != "RESET PTW PRODUCTION":
            raise HTTPException(status_code=412, detail="exact reset confirmation is required")
        try:
            reader, writer = await asyncio.open_unix_connection(str(settings.root_broker_socket))
            writer.write(b'{"type":"operation","name":"reset"}\n')
            await writer.drain()
            final: dict[str, Any] | None = None
            while raw := await asyncio.wait_for(reader.readline(), timeout=900):
                message = json.loads(raw)
                if message.get("type") in {"operation.completed", "operation.failed", "error"}:
                    final = message
                    break
            writer.close()
            await writer.wait_closed()
        except (OSError, asyncio.TimeoutError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=503, detail="root operation channel unavailable") from error
        if not final or final.get("type") != "operation.completed" or final.get("return_code") != 0:
            raise HTTPException(status_code=500, detail="reset failed; inspect root-only operation logs")
        return {"status": "reset"}

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
