from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
import hmac
import json
import re
import subprocess
from typing import Any, Iterator, Mapping
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .app_server import AppServerPlanner
from .auth import FirebaseVerifier, OwnerDependency, OwnerIdentity
from .control_store import ControlStore
from .execution import CommandRunner
from .platform import PlatformRepository
from .settings import Settings
from .validation_notifications import (
    ExistingBotValidationFailureNotifier,
    ValidationFailureNotificationRepository,
)

MAX_STUDIO_UPLOAD_BASE64 = ((50 * 1024 * 1024 + 2) // 3) * 4


def create_app(settings: Settings, verifier: FirebaseVerifier | None = None) -> FastAPI:
    store = ControlStore(settings.control_database_path)
    platform = PlatformRepository(settings.platform_database_url, settings.platform_owner_telegram_id)
    planner = AppServerPlanner(settings.codex_executable, settings.repository_path)
    runner = CommandRunner(settings.codex_executable, settings.repository_path, store, platform)
    owner = OwnerDependency(verifier or FirebaseVerifier(settings))
    tasks: set[asyncio.Task[Any]] = set()
    operation_start_lock = asyncio.Lock()
    failure_notifier = ExistingBotValidationFailureNotifier(
        ValidationFailureNotificationRepository(settings.validation_database_url),
        bot_token=settings.telegram_bot_token,
        owner_chat_id=settings.owner_chat_id,
        allowed_chat_ids=settings.telegram_allowed_chat_ids,
        owner_console_url=settings.public_origin,
    )

    for interrupted in store.recover_interrupted_commands():
        if interrupted.get("platform_job_id") is not None:
            try:
                platform.complete_job(
                    int(interrupted["platform_job_id"]), success=False,
                    result={"error": "owner gateway restarted during operation"},
                )
            except Exception:
                pass

    @contextmanager
    def validation_connection() -> Iterator[Any]:
        import psycopg
        with psycopg.connect(settings.validation_database_url, connect_timeout=5) as connection:
            yield connection

    def orphan_gateway_guard() -> None:
        with validation_connection() as connection:
            connection.execute(
                """UPDATE commander_operation_guard
                   SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton AND operation_kind IN ('codex_plan','codex_execute')"""
            )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await asyncio.to_thread(orphan_gateway_guard)
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(
        title="PTW Owner Gateway", version="3.0.0", docs_url=None, redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys([settings.public_origin, *settings.owner_public_origins])),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
        expose_headers=["ETag", "Content-Length"],
    )

    def background(coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    def require_running() -> None:
        if platform.emergency_stop():
            raise HTTPException(
                status_code=423,
                detail="PTW emergency stop is active; resume it from Admin / System",
            )

    def authorize_validation(x_ptw_owner_gateway_token: str = Header(default="")) -> None:
        if not settings.validation_service_token or not hmac.compare_digest(
            x_ptw_owner_gateway_token,
            settings.validation_service_token,
        ):
            raise HTTPException(status_code=401, detail="Validation callback authentication required")

    async def validation_bridge(
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        actor: str = "owner-web",
        timeout: float = 30,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                headers = {
                    "X-PTW-Owner-Gateway-Token": settings.validation_service_token,
                    "X-PTW-Actor": actor,
                    **dict(extra_headers or {}),
                }
                response = await client.request(
                    method,
                    f"{settings.validation_service_url}{path}",
                    headers=headers,
                    json=None if body is None else dict(body),
                    params=dict(params or {}),
                )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=503, detail="Validation service is unavailable") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(
                status_code=response.status_code,
                detail=detail or "Validation service request failed",
            )
        return response

    def operation_activity() -> dict[str, Any]:
        with validation_connection() as connection:
            row = connection.execute(
                "SELECT operation_kind,operation_id,acquired_at FROM commander_operation_guard WHERE singleton"
            ).fetchone()
        return {
            "active": bool(row and row[1]),
            "operation": None if not row else row[0],
            "operation_id": None if not row or row[1] is None else str(row[1]),
            "acquired_at": None if not row or row[2] is None else row[2].isoformat(),
        }

    def acquire_operation(kind: str, operation_id: str) -> None:
        with validation_connection() as connection:
            row = connection.execute(
                "SELECT operation_kind,operation_id FROM commander_operation_guard WHERE singleton FOR UPDATE"
            ).fetchone()
            if row is None or row[1] is not None:
                active = "unknown" if row is None else f"{row[0]} {row[1]}"
                raise ValueError(f"heavy operation {active} is already active")
            connection.execute(
                """UPDATE commander_operation_guard
                   SET operation_kind=%s,operation_id=%s,acquired_at=clock_timestamp()
                   WHERE singleton""",
                (kind, UUID(operation_id)),
            )

    def release_operation(operation_id: str) -> None:
        with validation_connection() as connection:
            connection.execute(
                """UPDATE commander_operation_guard
                   SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton AND operation_id=%s""",
                (UUID(operation_id),),
            )

    def require_no_active_operation() -> None:
        active = operation_activity()
        if active["active"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{active['operation']} {active['operation_id']} is active; "
                    "wait before starting another heavy operation"
                ),
            )

    async def plan_and_release(session_id: str, instruction: str) -> None:
        async def sink(event: dict[str, Any]) -> None:
            store.event(session_id, event)
        try:
            plan = await planner.plan(instruction, sink)
            if store.command(session_id)["status"] != "planning":
                store.event(session_id, {"type": "plan.discarded_after_cancel"})
                return
            store.set_plan(session_id, plan)
        except Exception as error:
            if store.command(session_id)["status"] == "cancelled":
                store.event(session_id, {"type": "plan.discarded_after_cancel"})
            else:
                store.update(session_id, "failed", error=f"{type(error).__name__}: {str(error)[:1000]}")
                store.event(session_id, {"type": "plan.failed", "error": type(error).__name__})
                try:
                    await validation_bridge(
                        "POST", f"/internal/v1/skill-proposals/by-command/{session_id}/finish",
                        body={"status": "failed"},
                    )
                except HTTPException:
                    pass
        finally:
            await asyncio.to_thread(release_operation, session_id)

    async def execute_and_release(session_id: str) -> None:
        try:
            await runner.execute(session_id)
            status = "promoted" if store.command(session_id)["status"] == "completed" else "failed"
            try:
                await validation_bridge(
                    "POST", f"/internal/v1/skill-proposals/by-command/{session_id}/finish",
                    body={"status": status},
                )
            except HTTPException:
                pass
        finally:
            await asyncio.to_thread(release_operation, session_id)

    async def propagate_emergency_stop(active: bool, actor: str) -> list[str]:
        failures: list[str] = []
        targets = (
            (
                "commander",
                f"{settings.commander_service_url}/internal/emergency-stop",
                {"X-PTW-Bridge-Token": settings.telegram_bot_token},
            ),
            (
                "validation",
                f"{settings.validation_service_url}/internal/emergency-stop",
                {"X-PTW-Owner-Gateway-Token": settings.validation_service_token},
            ),
        )
        async with httpx.AsyncClient(timeout=20) as client:
            for name, url, headers in targets:
                try:
                    response = await client.post(
                        url, headers=headers, json={"active": active, "actor": actor}
                    )
                    if response.status_code >= 400:
                        failures.append(name)
                except httpx.HTTPError:
                    failures.append(name)
        return failures

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/internal/v1/validation-failures",
        dependencies=[Depends(authorize_validation)],
    )
    def validation_failure_notification(request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"target_id", "attempt_id", "stage"}:
            raise HTTPException(status_code=400, detail="target_id, attempt_id, and stage are required")
        stage = str(request.get("stage") or "")
        if stage != "ad_creative_batch":
            raise HTTPException(status_code=400, detail="unsupported Validation notification stage")
        try:
            return failure_notifier.notify(
                str(UUID(str(request["target_id"]))),
                str(UUID(str(request["attempt_id"]))),
                stage,
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/overview")
    async def overview(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        briefs = (await validation_bridge("GET", "/internal/v1/briefs", params={"limit": 100})).json()["items"]
        batches = (await validation_bridge("GET", "/internal/v1/ad-batches", params={"limit": 100})).json()["items"]
        return {
            "briefs": {
                "total": len(briefs),
                "approved": sum(bool(item.get("approved")) for item in briefs),
            },
            "ad_batches": {
                "total": len(batches),
                "completed": sum(item.get("status") == "completed" for item in batches),
            },
            "landing": {"status": "stage_3_pending"},
            "jobs": platform.summary(),
            "emergency_stop": platform.emergency_stop(),
        }

    @app.get("/api/v1/projects")
    async def list_projects(
        limit: int = Query(default=100, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", "/internal/v1/projects", params={"limit": limit}
        )).json()

    @app.post("/api/v1/projects/{project_id}/rename")
    async def rename_project(
        project_id: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/projects/{project_id}/rename", body=request,
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.post("/api/v1/briefs", status_code=202)
    async def create_brief(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        return (await validation_bridge(
            "POST", "/internal/v1/briefs", body=request, actor=f"firebase:{identity.uid}"
        )).json()

    @app.get("/api/v1/briefs")
    async def list_briefs(
        project_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if project_id:
            params["project_id"] = project_id
        return (await validation_bridge(
            "GET", "/internal/v1/briefs", params=params
        )).json()

    @app.get("/api/v1/briefs/{brief_id}")
    async def brief(brief_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/briefs/{brief_id}")).json()

    @app.post("/api/v1/briefs/{brief_id}/correct", status_code=202)
    async def revise_brief(
        brief_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        return (await validation_bridge(
            "POST", f"/internal/v1/briefs/{brief_id}/correct", body=request,
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.post("/api/v1/briefs/{brief_id}/retry", status_code=202)
    async def retry_brief(
        brief_id: str, identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        return (await validation_bridge(
            "POST", f"/internal/v1/briefs/{brief_id}/retry", body={},
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.post("/api/v1/briefs/{brief_id}/approve", status_code=202)
    async def approve_brief(
        brief_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        if set(request) != {"honor_confirmed"} or request.get("honor_confirmed") is not True:
            raise HTTPException(
                status_code=412,
                detail="confirm that the Product Brief promise and offer can be honored",
            )
        require_running()
        return (await validation_bridge(
            "POST", f"/internal/v1/briefs/{brief_id}/approve", body={},
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.get("/api/v1/ad-batches")
    async def list_batches(
        brief_id: str | None = None,
        project_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if brief_id:
            params["brief_id"] = brief_id
        if project_id:
            params["project_id"] = project_id
        return (await validation_bridge(
            "GET", "/internal/v1/ad-batches", params=params
        )).json()

    @app.get("/api/v1/ad-batches/{batch_id}")
    async def batch(batch_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/ad-batches/{batch_id}")).json()

    @app.post("/api/v1/ad-batches/{batch_id}/retry", status_code=202)
    async def retry_batch(
        batch_id: str, identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        return (await validation_bridge(
            "POST", f"/internal/v1/ad-batches/{batch_id}/retry", body={},
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.post("/api/v1/ad-batches/{batch_id}/rerun", status_code=202)
    async def rerun_batch(
        batch_id: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        if (
            set(request) != {"request_id", "confirmation"}
            or request.get("confirmation") != "GENERATE NEW BATCH"
        ):
            raise HTTPException(
                status_code=412,
                detail="generating a learned rerun requires explicit confirmation",
            )
        try:
            request_id = str(UUID(str(request["request_id"])))
        except ValueError as error:
            raise HTTPException(status_code=400, detail="request_id must be a UUID") from error
        require_running()
        return (await validation_bridge(
            "POST", f"/internal/v1/ad-batches/{batch_id}/rerun",
            body={"request_id": request_id},
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.get("/api/v1/ad-creatives/{creative_id}/image")
    async def creative_image(
        creative_id: str,
        if_none_match: str = Header(default=""),
        _identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        response = await validation_bridge(
            "GET", f"/internal/v1/ad-creatives/{creative_id}/image", timeout=60,
            extra_headers={} if not if_none_match else {"If-None-Match": if_none_match},
        )
        headers = {
            key: value for key, value in response.headers.items()
            if key.lower() in {"etag", "cache-control"}
        }
        if response.status_code == 304:
            return Response(status_code=304, headers=headers)
        return Response(
            content=response.content,
            media_type=response.headers.get("content-type", "image/jpeg"),
            headers=headers,
        )

    @app.post("/api/v1/ad-creatives/{creative_id}/feedback")
    async def creative_feedback(
        creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/ad-creatives/{creative_id}/feedback", body=request,
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.get("/api/v1/ad-studio/tools")
    async def studio_tools(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", "/internal/v1/ad-studio/tools")).json()

    @app.get("/api/v1/ad-studio/brand-kits")
    async def studio_brand_kits(
        project_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", "/internal/v1/ad-studio/brand-kits", params={"project_id": project_id}
        )).json()

    @app.post("/api/v1/ad-studio/brand-kits", status_code=201)
    async def create_studio_brand_kit(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", "/internal/v1/ad-studio/brand-kits", body=request,
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.get("/api/v1/ad-studio/templates")
    async def studio_templates(
        project_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", "/internal/v1/ad-studio/templates", params={"project_id": project_id}
        )).json()

    @app.post("/api/v1/ad-studio/templates", status_code=201)
    async def create_studio_template(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", "/internal/v1/ad-studio/templates", body=request,
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.post("/api/v1/ad-studio/templates/{template_id}/apply")
    async def apply_studio_template(
        template_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/ad-studio/templates/{template_id}/apply", body=request,
            actor=f"firebase:{identity.uid}", timeout=120,
        )).json()

    @app.get("/api/v1/ad-studio/sources")
    async def studio_sources(
        project_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", "/internal/v1/ad-studio/sources", params={"project_id": project_id}
        )).json()

    @app.get("/api/v1/ad-studio/sources/{source_asset_id}/asset")
    async def studio_source_asset(
        source_asset_id: str, if_none_match: str = Header(default=""),
        _identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        response = await validation_bridge(
            "GET", f"/internal/v1/ad-studio/sources/{source_asset_id}/asset", timeout=60,
            extra_headers={} if not if_none_match else {"If-None-Match": if_none_match},
        )
        headers = {key: value for key, value in response.headers.items() if key.lower() in {"etag", "cache-control"}}
        if response.status_code == 304:
            return Response(status_code=304, headers=headers)
        return Response(response.content, media_type=response.headers.get("content-type", "application/octet-stream"), headers=headers)

    @app.post("/api/v1/ad-studio/sources/upload", status_code=201)
    async def upload_studio_source(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        encoded = request.get("base64")
        if not isinstance(encoded, str) or len(encoded) > MAX_STUDIO_UPLOAD_BASE64:
            raise HTTPException(status_code=413, detail="Studio upload exceeds the bounded size")
        return (await validation_bridge(
            "POST", "/internal/v1/ad-studio/sources/upload", body=request,
            actor=f"firebase:{identity.uid}", timeout=60,
        )).json()

    @app.get("/api/v1/ad-studio/pexels/search")
    async def search_studio_pexels(
        query: str = Query(min_length=1, max_length=160),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", "/internal/v1/ad-studio/pexels/search", params={"query": query}, timeout=60,
        )).json()

    @app.post("/api/v1/ad-studio/sources/pexels", status_code=201)
    async def import_studio_pexels(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", "/internal/v1/ad-studio/sources/pexels", body=request,
            actor=f"firebase:{identity.uid}", timeout=60,
        )).json()

    @app.get("/api/v1/ad-studio/sample-sets")
    async def studio_sample_sets(
        project_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", "/internal/v1/ad-studio/sample-sets", params={"project_id": project_id}, timeout=300,
        )).json()

    @app.post("/api/v1/ad-studio/sample-sets", status_code=201)
    async def create_studio_sample_set(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        return (await validation_bridge(
            "POST", "/internal/v1/ad-studio/sample-sets", body=request,
            actor=f"firebase:{identity.uid}", timeout=300,
        )).json()

    @app.get("/api/v1/ad-studio/sample-sets/{sample_set_id}")
    async def studio_sample_set(
        sample_set_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/ad-studio/sample-sets/{sample_set_id}", timeout=300,
        )).json()

    @app.get("/api/v1/ad-studio/sample-sets/{sample_set_id}/download")
    async def studio_sample_set_download(
        sample_set_id: str, if_none_match: str = Header(default=""),
        _identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        response = await validation_bridge(
            "GET", f"/internal/v1/ad-studio/sample-sets/{sample_set_id}/download", timeout=300,
            extra_headers={} if not if_none_match else {"If-None-Match": if_none_match},
        )
        headers = {key: value for key, value in response.headers.items() if key.lower() in {"etag", "cache-control", "content-disposition"}}
        if response.status_code == 304:
            return Response(status_code=304, headers=headers)
        return Response(response.content, media_type="application/zip", headers=headers)

    @app.get("/api/v1/ad-studio/recipes")
    async def studio_recipes(
        project_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", "/internal/v1/ad-studio/recipes", params={"project_id": project_id}
        )).json()

    @app.get("/api/v1/ad-studio/recipes/{recipe_id}")
    async def studio_recipe(
        recipe_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/ad-studio/recipes/{recipe_id}"
        )).json()

    @app.post("/api/v1/ad-studio/recipes", status_code=201)
    async def create_studio_recipe(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", "/internal/v1/ad-studio/recipes", body=request,
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.post("/api/v1/ad-studio/recipes/{recipe_id}/render", status_code=201)
    async def render_studio_recipe(
        recipe_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        return (await validation_bridge(
            "POST", f"/internal/v1/ad-studio/recipes/{recipe_id}/render", body={}, timeout=60,
        )).json()

    @app.get("/api/v1/ad-studio/recipes/{recipe_id}/renders")
    async def studio_recipe_renders(
        recipe_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/ad-studio/recipes/{recipe_id}/renders"
        )).json()

    @app.post("/api/v1/ad-studio/recipes/{recipe_id}/wizard-proposals", status_code=201)
    async def create_studio_wizard_proposal(
        recipe_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        return (await validation_bridge(
            "POST", f"/internal/v1/ad-studio/recipes/{recipe_id}/wizard-proposals",
            body=request, actor=f"firebase:{identity.uid}", timeout=600,
        )).json()

    @app.get("/api/v1/ad-studio/recipes/{recipe_id}/wizard-proposals")
    async def studio_wizard_proposals(
        recipe_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/ad-studio/recipes/{recipe_id}/wizard-proposals"
        )).json()

    @app.get("/api/v1/ad-studio/wizard-proposals/{proposal_id}/preview")
    async def studio_wizard_preview(
        proposal_id: str, if_none_match: str = Header(default=""),
        _identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        response = await validation_bridge(
            "GET", f"/internal/v1/ad-studio/wizard-proposals/{proposal_id}/preview", timeout=60,
            extra_headers={} if not if_none_match else {"If-None-Match": if_none_match},
        )
        headers = {key: value for key, value in response.headers.items() if key.lower() in {"etag", "cache-control"}}
        if response.status_code == 304:
            return Response(status_code=304, headers=headers)
        return Response(response.content, media_type="image/jpeg", headers=headers)

    @app.post("/api/v1/ad-studio/wizard-proposals/{proposal_id}/apply")
    async def apply_studio_wizard_proposal(
        proposal_id: str, identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        return (await validation_bridge(
            "POST", f"/internal/v1/ad-studio/wizard-proposals/{proposal_id}/apply", body={},
            actor=f"firebase:{identity.uid}", timeout=300,
        )).json()

    @app.get("/api/v1/ad-studio/renders/{render_id}/asset")
    async def studio_render_asset(
        render_id: str,
        if_none_match: str = Header(default=""),
        _identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        response = await validation_bridge(
            "GET", f"/internal/v1/ad-studio/renders/{render_id}/asset", timeout=60,
            extra_headers={} if not if_none_match else {"If-None-Match": if_none_match},
        )
        headers = {
            key: value for key, value in response.headers.items()
            if key.lower() in {"etag", "cache-control"}
        }
        if response.status_code == 304:
            return Response(status_code=304, headers=headers)
        return Response(
            content=response.content,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            headers=headers,
        )

    @app.get("/api/v1/ad-studio/renders/{render_id}/manifest")
    async def studio_render_manifest(
        render_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/ad-studio/renders/{render_id}/manifest"
        )).json()

    @app.post("/api/v1/ad-studio/renders/{render_id}/publish")
    async def publish_studio_render(
        render_id: str, identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/ad-studio/renders/{render_id}/publish", body={},
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.post("/api/v1/ad-studio/renders/{render_id}/feedback")
    async def studio_render_feedback(
        render_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/ad-studio/renders/{render_id}/feedback", body=request,
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.get("/api/v1/skill-proposals/{domain}")
    async def skill_proposals(
        domain: str,
        target_id: str | None = None,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        params = {} if target_id is None else {"target_id": target_id}
        return (await validation_bridge(
            "GET", f"/internal/v1/skill-proposals/{domain}", params=params
        )).json()

    @app.post("/api/v1/skill-proposals/{domain}/{proposal_id}/update")
    async def update_skill_proposal(
        domain: str,
        proposal_id: str,
        request: Mapping[str, Any],
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/skill-proposals/{domain}/{proposal_id}/update", body=request
        )).json()

    @app.post("/api/v1/skill-proposals/{domain}/{proposal_id}/dismiss")
    async def dismiss_skill_proposal(
        domain: str,
        proposal_id: str,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/skill-proposals/{domain}/{proposal_id}/dismiss", body={}
        )).json()

    @app.post("/api/v1/skill-proposals/{domain}/plan", status_code=202)
    async def plan_grouped_skill_proposals(
        domain: str,
        request: Mapping[str, Any],
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        if domain not in {"product_brief", "ad_creative", "ad_studio"}:
            raise HTTPException(status_code=404, detail="skill proposal domain not found")
        lesson = str(request.get("lesson", "")).strip()
        raw_ids = request.get("proposal_ids")
        if set(request) != {"proposal_ids", "lesson"} or not isinstance(raw_ids, list):
            raise HTTPException(status_code=400, detail="proposal_ids and lesson are required")
        try:
            proposal_ids = [str(UUID(str(value))) for value in raw_ids]
        except ValueError as error:
            raise HTTPException(status_code=400, detail="proposal_ids must contain UUIDs") from error
        if not 1 <= len(proposal_ids) <= 100 or len(set(proposal_ids)) != len(proposal_ids):
            raise HTTPException(status_code=400, detail="one to 100 unique proposal_ids are required")
        if not 1 <= len(lesson) <= 4000:
            raise HTTPException(status_code=400, detail="a 1-4000 character lesson is required")
        path = {
            "product_brief": "skills/product-brief-generator/references/owner-lessons.md",
            "ad_creative": "skills/ad-creative-generator/references/owner-lessons.md",
            "ad_studio": "skills/ad-studio-composer/references/owner-lessons.md",
        }[domain]
        instruction = (
            f"Update only {path}. Consolidate the following owner-approved pending feedback into "
            f"one generalized lesson without adding proposal IDs or changing any other file:\n{lesson}"
        )
        command: dict[str, Any] | None = None
        async with operation_start_lock:
            require_no_active_operation()
            try:
                command = store.create_command("plan", instruction)
                acquire_operation("codex_plan", command["id"])
                await validation_bridge(
                    "POST", f"/internal/v1/skill-proposals/{domain}/plan",
                    body={"proposal_ids": proposal_ids, "command_session_id": command["id"]},
                )
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except HTTPException:
                if command is not None:
                    store.update(command["id"], "failed", error="Validation proposals could not enter planning")
                    release_operation(command["id"])
                raise
            background(plan_and_release(command["id"], instruction))
            return command

    @app.post("/api/v1/skill-proposals/{domain}/{proposal_id}/plan", status_code=202)
    async def plan_skill_proposal(
        domain: str,
        proposal_id: str,
        request: Mapping[str, Any],
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        if domain not in {"product_brief", "ad_creative", "ad_studio"}:
            raise HTTPException(status_code=404, detail="skill proposal domain not found")
        lesson = str(request.get("lesson", "")).strip()
        if set(request) != {"lesson"} or not 1 <= len(lesson) <= 4000:
            raise HTTPException(status_code=400, detail="a 1-4000 character lesson is required")
        path = {
            "product_brief": "skills/product-brief-generator/references/owner-lessons.md",
            "ad_creative": "skills/ad-creative-generator/references/owner-lessons.md",
            "ad_studio": "skills/ad-studio-composer/references/owner-lessons.md",
        }[domain]
        instruction = (
            f"Update only {path}. Incorporate this owner-approved lesson without changing any "
            f"other file: {lesson}"
        )
        command: dict[str, Any] | None = None
        async with operation_start_lock:
            require_no_active_operation()
            try:
                command = store.create_command("plan", instruction)
                acquire_operation("codex_plan", command["id"])
                await validation_bridge(
                    "POST", f"/internal/v1/skill-proposals/{domain}/{proposal_id}/plan",
                    body={"lesson": lesson, "command_session_id": command["id"]},
                )
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except HTTPException:
                if command is not None:
                    store.update(command["id"], "failed", error="Validation proposal could not enter planning")
                    release_operation(command["id"])
                raise
            background(plan_and_release(command["id"], instruction))
            return command

    # Admin: Jobs, Docs/System, and break-glass terminal.
    @app.get("/api/v1/jobs")
    def jobs(
        limit: int = Query(default=30, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        local = store.commands(limit)
        return {"items": local + platform.state(max(0, limit - len(local))), "next_cursor": None}

    @app.post("/api/v1/jobs")
    @app.post("/api/v1/command-sessions")
    async def create_job(
        request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        mode = str(request.get("mode", "plan"))
        instruction = str(request.get("instruction", "")).strip()
        if (
            set(request) != {"mode", "instruction"}
            or mode not in {"plan", "execute"}
            or not 1 <= len(instruction) <= 20_000
        ):
            raise HTTPException(
                status_code=400,
                detail="mode and 1-20000 character instruction are required",
            )
        async with operation_start_lock:
            require_no_active_operation()
            try:
                command = store.create_command(mode, instruction)
                acquire_operation("codex_plan", command["id"])
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            background(plan_and_release(command["id"], instruction))
            return command

    @app.get("/api/v1/command-sessions")
    def command_sessions(
        limit: int = Query(default=30, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return {"items": store.commands(limit), "next_cursor": None}

    @app.get("/api/v1/issues")
    def issues(
        limit: int = Query(default=30, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return {"items": platform.issues(limit), "next_cursor": None}

    @app.post("/api/v1/command-sessions/{session_id}/approve")
    async def approve_command(
        session_id: str,
        request: Mapping[str, Any],
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_running()
        destructive_allowed = request.get("destructive_confirmation") == "EXECUTE DESTRUCTIVE PLAN"
        async with operation_start_lock:
            require_no_active_operation()
            try:
                command = store.approve_once(
                    session_id,
                    str(request.get("plan_digest", "")),
                    destructive_allowed=destructive_allowed,
                )
                acquire_operation("codex_execute", session_id)
            except KeyError as error:
                raise HTTPException(status_code=404, detail="command session not found") from error
            except PermissionError as error:
                raise HTTPException(status_code=412, detail=str(error)) from error
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            background(execute_and_release(session_id))
            return command

    @app.post("/api/v1/jobs/{session_id}/restore", status_code=202)
    async def restore_command_plan(
        session_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        async with operation_start_lock:
            require_no_active_operation()
            proposal_result: dict[str, Any] | None = None
            command_restored = False
            try:
                existing = store.command(session_id)
                if existing["status"] not in {"failed", "cancelled"} or existing["execution_count"] != 0:
                    raise ValueError("only an unexecuted failed or cancelled plan can be restored")
                proposal_result = (await validation_bridge(
                    "POST", f"/internal/v1/skill-proposals/by-command/{session_id}/restore",
                    body={},
                )).json()
                command = store.restore_plan(session_id)
                command_restored = True
                if command["status"] == "planning":
                    acquire_operation("codex_plan", session_id)
                    background(plan_and_release(session_id, command["instruction"]))
                return {**command, "restored_proposal_count": proposal_result.get("proposal_count", 0)}
            except KeyError as error:
                raise HTTPException(status_code=404, detail="command session not found") from error
            except (ValueError, HTTPException) as error:
                if command_restored and store.command(session_id)["status"] == "planning":
                    store.update(session_id, "failed", error="plan restoration could not start")
                if proposal_result and proposal_result.get("matched"):
                    try:
                        await validation_bridge(
                            "POST", f"/internal/v1/skill-proposals/by-command/{session_id}/finish",
                            body={"status": "failed"},
                        )
                    except HTTPException:
                        pass
                if isinstance(error, ValueError):
                    raise HTTPException(status_code=409, detail=str(error)) from error
                raise

    @app.post("/api/v1/jobs/{session_id}/cancel")
    @app.post("/api/v1/command-sessions/{session_id}/cancel")
    async def cancel_command(
        session_id: str,
        request: Mapping[str, Any],
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, bool]:
        if set(request) != {"confirmation"} or request.get("confirmation") != "CANCEL JOB":
            raise HTTPException(status_code=412, detail="cancellation requires explicit confirmation")
        try:
            async with operation_start_lock:
                command = store.command(session_id)
                if command["status"] not in {"planning", "queued", "running", "cancel_requested"}:
                    raise ValueError("only an active job can be cancelled")
                await runner.cancel(session_id)
                if command["status"] != "planning":
                    await asyncio.to_thread(release_operation, session_id)
                try:
                    await validation_bridge(
                        "POST", f"/internal/v1/skill-proposals/by-command/{session_id}/finish",
                        body={"status": "failed"},
                    )
                except HTTPException:
                    pass
        except KeyError as error:
            raise HTTPException(status_code=404, detail="command session not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"cancelled": True}

    @app.post("/api/v1/ws-tickets")
    def ws_ticket(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, str]:
        path = str(request.get("path", ""))
        if path != "/api/v1/root-sessions" and not re.fullmatch(
            r"/api/v1/jobs/[0-9a-f-]{36}/events", path
        ):
            raise HTTPException(status_code=400, detail="unsupported WebSocket path")
        return {"ticket": store.issue_ticket(identity.uid, path)}

    @app.websocket("/api/v1/jobs/{session_id}/events")
    async def job_events(
        websocket: WebSocket, session_id: str, ticket: str = Query(default="")
    ) -> None:
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
                if (
                    store.command(session_id)["status"]
                    in {"completed", "failed", "cancelled", "awaiting_approval"}
                    and not events
                ):
                    await websocket.close(code=1000)
                    return
                await asyncio.sleep(0.5)
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
                {
                    asyncio.create_task(browser_to_broker()),
                    asyncio.create_task(broker_to_browser()),
                },
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            writer.close()
            await writer.wait_closed()
            for task in done:
                if task.exception():
                    raise task.exception()  # pragma: no cover - transport failure
        except WebSocketDisconnect:
            reason = "client_disconnected"
        except Exception as error:
            reason = type(error).__name__
            await websocket.close(code=1011)
        finally:
            store.end_root_session(metadata_id, reason)

    @app.get("/api/v1/docs")
    def docs(
        limit: int = Query(default=50, ge=1, le=50),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        allowed = [
            "README.md",
            "docs/README.md",
            "docs/architecture/commander-current-state.md",
            "docs/architecture/simplified-validation-pipeline.md",
            "docs/operations/owner-control-plane.md",
            "docs/operations/disaster-recovery.md",
        ]
        items = []
        for relative in allowed[:limit]:
            path = settings.repository_path / relative
            if path.is_file():
                body = path.read_text()
                title = next(
                    (line[2:] for line in body.splitlines() if line.startswith("# ")),
                    path.name,
                )
                items.append({"path": relative, "title": title, "body": body})
        return {"items": items}

    @app.get("/api/v1/system/health")
    async def system_health(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        revision = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=settings.repository_path,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        ).stdout.strip() or "unknown"
        try:
            validation_ready = (await validation_bridge("GET", "/readyz")).json()
        except HTTPException as error:
            validation_ready = {"ready": False, "error": error.detail}
        return {
            "git_revision": revision,
            "services": {
                "gateway": "ok",
                "validation": validation_ready,
                "root_broker": "ok" if settings.root_broker_socket.exists() else "unavailable",
            },
            "heavy_operation": operation_activity(),
            "emergency_stop": platform.emergency_stop(),
            "reset": {"permitted": True, "target": "ptw_commander.public only"},
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
    async def reset(
        request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        if request.get("confirmation") != "RESET PTW PRODUCTION":
            raise HTTPException(status_code=412, detail="exact reset confirmation is required")
        try:
            reader, writer = await asyncio.open_unix_connection(str(settings.root_broker_socket))
            writer.write(b'{"type":"operation","name":"reset"}\n')
            await writer.drain()
            final = None
            while raw := await asyncio.wait_for(reader.readline(), timeout=900):
                message = json.loads(raw)
                if message.get("type") in {"operation.completed", "operation.failed", "error"}:
                    final = message
                    break
            writer.close()
            await writer.wait_closed()
        except (OSError, asyncio.TimeoutError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=503, detail="root operation channel unavailable") from error
        if (
            not final
            or final.get("type") != "operation.completed"
            or final.get("return_code") != 0
        ):
            raise HTTPException(
                status_code=500,
                detail="reset failed; inspect root-only operation logs",
            )
        return {"status": "reset"}

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
