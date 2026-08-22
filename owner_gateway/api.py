from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from .app_server import AppServerPlanner
from .annotations import region
from .auth import FirebaseVerifier, OwnerDependency, OwnerIdentity
from .control_store import ControlStore
from .execution import CommandRunner
from .firebase_hosting import FirebaseHostingPublisher
from .landing import candidates_response, prepare_landing_build, templates_response
from .landing_pipeline import LandingBuildCoordinator
from .landing_repository import LandingBuildRepository
from .platform import PlatformRepository
from .read_models import DomainReadModels
from .settings import Settings


def create_app(
    settings: Settings,
    verifier: FirebaseVerifier | None = None,
    landing_coordinator: LandingBuildCoordinator | None = None,
) -> FastAPI:
    store = ControlStore(settings.control_database_path)
    platform = PlatformRepository(settings.platform_database_url, settings.platform_owner_telegram_id)
    read = DomainReadModels(settings.idea_database_url, settings.commander_database_url)
    planner = AppServerPlanner(settings.codex_executable, settings.repository_path)
    runner = CommandRunner(settings.codex_executable, settings.repository_path, store, platform)
    if (
        landing_coordinator is None
        and settings.firebase_landing_site_id
        and settings.firebase_landing_service_account_path is not None
    ):
        landing_coordinator = LandingBuildCoordinator(
            repository=LandingBuildRepository(settings.commander_database_url),
            publisher=FirebaseHostingPublisher(
                project_id=settings.firebase_project_id,
                site_id=settings.firebase_landing_site_id,
                credential_path=settings.firebase_landing_service_account_path,
            ),
            output_root=settings.landing_output_root,
            stopped=platform.emergency_stop,
        )
    owner = OwnerDependency(verifier or FirebaseVerifier(settings))
    tasks: set[asyncio.Task[Any]] = set()
    operation_start_lock = asyncio.Lock()
    interrupted_commands = store.recover_interrupted_commands()
    for interrupted in interrupted_commands:
        platform_job_id = interrupted.get("platform_job_id")
        if platform_job_id is None:
            continue
        try:
            platform.complete_job(
                int(platform_job_id),
                success=False,
                result={"error": "owner gateway restarted during operation"},
            )
        except Exception:
            # Gateway startup must remain available even if the platform DB is
            # the dependency being diagnosed. Local exclusion state is repaired.
            pass

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if landing_coordinator is not None:
            await asyncio.to_thread(landing_coordinator.recover_interrupted)
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
            async with httpx.AsyncClient(timeout=15) as client:
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

    async def commander_bridge(
        method: str, path: str, *, body: Mapping[str, Any] | None = None
    ) -> httpx.Response:
        if not settings.telegram_bot_token:
            raise HTTPException(status_code=503, detail="Commander validation bridge is not configured")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.request(
                    method,
                    f"{settings.commander_service_url}{path}",
                    headers={"X-PTW-Bridge-Token": settings.telegram_bot_token},
                    json=dict(body) if body is not None else None,
                )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=503, detail="Commander validation service is unavailable") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(status_code=response.status_code, detail=detail or "Commander validation request failed")
        return response

    async def active_heavy_operation() -> Mapping[str, Any] | None:
        response = await laval_bridge("GET", "/internal/web/activity")
        activity = response.json()
        return activity if activity.get("active") else None

    def require_no_active_codex(*, exclude_id: str | None = None) -> None:
        if landing_coordinator is not None:
            active_landing = landing_coordinator.active()
            if active_landing is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Natal landing build {active_landing['id']} is active "
                        f"({active_landing['status']}); wait before starting another heavy operation"
                    ),
                )
        active = store.active_command(exclude_id=exclude_id)
        if active is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Codex operation {active['id']} is active ({active['status']}); "
                    "wait before starting another heavy operation"
                ),
            )

    async def require_no_active_laval() -> None:
        active = await active_heavy_operation()
        if active is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{active.get('operation') or 'Heavy'} run {active['run_id']} is active; "
                    "wait before starting Codex"
                ),
            )

    def require_landing_builder() -> LandingBuildCoordinator:
        if landing_coordinator is None:
            raise HTTPException(status_code=503, detail="Natal Firebase publisher is not configured")
        return landing_coordinator

    def landing_response(build: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: build.get(key)
            for key in (
                "id", "request_id", "idea_run_id", "thesis_id", "template_id", "brief",
                "status", "build_manifest", "artifact_sha256", "firebase_site_id",
                "firebase_version", "public_url", "error_code", "error_message",
                "created_at", "updated_at", "completed_at",
            )
        }

    def creative_gone() -> None:
        if not settings.creative_runtime_enabled:
            raise HTTPException(status_code=410, detail="creative production and review are retired")

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

    @app.get("/api/v1/branding/providers")
    async def branding_providers(
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await laval_bridge("GET", "/internal/web/branding/providers")).json()

    @app.get("/api/v1/landings/templates")
    def landing_templates(
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return templates_response()

    @app.get("/api/v1/landings/candidates")
    async def landing_candidates(
        limit: int = Query(default=30, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        cases = (
            await laval_bridge(
                "GET", "/internal/web/branding/cases", params={"limit": limit}
            )
        ).json()
        return candidates_response(cases.get("items") or [])

    async def start_landing_build(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_running()
        coordinator = require_landing_builder()
        request_id = str(request.get("request_id") or uuid4())
        try:
            UUID(request_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="request_id must be a UUID") from error
        existing = coordinator.by_request(request_id)
        if existing is not None:
            return landing_response(existing)
        idea_run_id = str(request.get("idea_run_id") or "").strip()
        require_laval_id(idea_run_id)
        template_id = str(request.get("template_id") or "auto").strip().lower()
        overrides = request.get("brief") or {}
        if not isinstance(overrides, Mapping):
            raise HTTPException(status_code=400, detail="brief must be an object")
        try:
            cases = (
                await laval_bridge(
                    "GET", "/internal/web/branding/cases", params={"limit": 100}
                )
            ).json()
            candidate = next(
                item for item in cases.get("items") or []
                if str(item.get("idea_run_id")) == idea_run_id
            )
            prepared = prepare_landing_build(candidate, template_id, overrides)
        except StopIteration as error:
            raise HTTPException(status_code=404, detail="completed Idea evaluation not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        async with operation_start_lock:
            await require_no_active_laval()
            require_no_active_codex()
            try:
                build, created = coordinator.create(
                    prepared,
                    request_id=request_id,
                    requested_by=f"firebase:{identity.uid}",
                )
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            if created:
                background(coordinator.run(str(build["id"])))
        return landing_response(build)

    @app.post("/api/v1/landings/builds", status_code=202)
    async def create_landing_build(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return await start_landing_build(request, identity)

    @app.post("/api/v1/landings/builder-jobs", status_code=202)
    async def create_landing_builder_job_compatibility(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        build = await start_landing_build(request, identity)
        return {
            **build,
            "mode": "execute",
            "title": "Natal landing build and Firebase publish",
            "created_by": f"firebase:{identity.uid}",
            "landing": {
                "build_id": build["id"],
                "idea_run_id": build["idea_run_id"],
                "template_id": build["template_id"],
                "recommended_template_id": build["template_id"],
                "output_path": f"Firebase · {build['firebase_site_id']}",
                "brief": build["brief"],
            },
        }

    @app.get("/api/v1/landings/builds")
    def landing_builds(
        limit: int = Query(default=30, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        coordinator = require_landing_builder()
        return {"items": [landing_response(item) for item in coordinator.list(limit)], "next_cursor": None}

    @app.get("/api/v1/landings/builds/{build_id}")
    def landing_build(
        build_id: str, _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        coordinator = require_landing_builder()
        try:
            UUID(build_id)
            return landing_response(coordinator.get(build_id))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Natal landing build not found") from error

    @app.post("/api/v1/landings/builds/{build_id}/retry", status_code=202)
    async def retry_landing_build(
        build_id: str,
        _request: Mapping[str, Any],
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_running()
        coordinator = require_landing_builder()
        try:
            UUID(build_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="Natal landing build not found") from error
        async with operation_start_lock:
            await require_no_active_laval()
            require_no_active_codex()
            try:
                build = coordinator.retry(build_id)
            except (KeyError, ValueError) as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            background(coordinator.run(build_id))
        return landing_response(build)

    @app.get("/api/v1/branding/cases")
    async def branding_cases(
        limit: int = Query(default=30, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (
            await laval_bridge(
                "GET", "/internal/web/branding/cases", params={"limit": limit}
            )
        ).json()

    @app.get("/api/v1/branding/runs")
    async def branding_runs(
        limit: int = Query(default=30, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (
            await laval_bridge(
                "GET", "/internal/web/branding/runs", params={"limit": limit}
            )
        ).json()

    def decorate_brand_project(project: dict[str, Any]) -> dict[str, Any]:
        active = project.get("active_kit")
        if isinstance(active, dict) and active.get("logo_artifact_digest"):
            digest = str(active["logo_artifact_digest"])
            active["logo_asset"] = {
                "digest": digest, "mime_type": "image/png", "width": 1024,
                "height": 1024, "url": f"/api/v1/branding/assets/{digest}",
                "cache": "private, no-store",
            }
        for kit in project.get("kits") or []:
            digest = kit.get("logo_artifact_digest")
            if digest:
                kit["logo_asset"] = {
                    "digest": digest, "mime_type": "image/png", "width": 1024,
                    "height": 1024, "url": f"/api/v1/branding/assets/{digest}",
                    "cache": "private, no-store",
                }
        for revision in project.get("logo_revisions") or []:
            source = revision.get("source_artifact_digest")
            result = revision.get("artifact_digest")
            if source:
                revision["before_asset"] = {
                    "digest": source, "mime_type": "image/png", "width": 1024,
                    "height": 1024, "url": f"/api/v1/branding/assets/{source}",
                    "cache": "private, no-store",
                }
            if result:
                revision["after_asset"] = {
                    "digest": result, "mime_type": "image/png", "width": 1024,
                    "height": 1024, "url": f"/api/v1/branding/assets/{result}",
                    "cache": "private, no-store",
                }
        return project

    @app.get("/api/v1/branding/projects")
    async def branding_projects(
        limit: int = Query(default=30, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        result = (
            await laval_bridge(
                "GET", "/internal/web/branding/projects", params={"limit": limit}
            )
        ).json()
        result["items"] = [
            decorate_brand_project(item) for item in result.get("items") or []
        ]
        return result

    @app.get("/api/v1/branding/projects/{project_id}")
    async def branding_project(
        project_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(project_id)
        result = (
            await laval_bridge(
                "GET", f"/internal/web/branding/projects/{project_id}"
            )
        ).json()
        return decorate_brand_project(result)

    @app.get("/api/v1/branding/projects/{project_id}/active-kit")
    async def branding_project_active_kit(
        project_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(project_id)
        result = (
            await laval_bridge(
                "GET", f"/internal/web/branding/projects/{project_id}/active-kit"
            )
        ).json()
        digest = result.get("logo_artifact_digest")
        if digest:
            result["logo_asset"] = {
                "digest": digest, "mime_type": "image/png", "width": 1024,
                "height": 1024, "url": f"/api/v1/branding/assets/{digest}",
                "cache": "private, no-store",
            }
        return result

    @app.get("/api/v1/branding/projects/{project_id}/history")
    async def branding_project_history(
        project_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(project_id)
        return (
            await laval_bridge(
                "GET", f"/internal/web/branding/projects/{project_id}/history"
            )
        ).json()

    @app.post("/api/v1/branding/projects/{project_id}/rebuild")
    async def rebuild_branding_project(
        project_id: str, request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(project_id)
        require_running()
        async with operation_start_lock:
            require_no_active_codex()
            return (
                await laval_bridge(
                    "POST", f"/internal/web/branding/projects/{project_id}/rebuild",
                    body={**dict(request), "confirmed": True,
                          "actor": f"firebase:{identity.uid}"},
                )
            ).json()

    @app.post("/api/v1/branding/projects/{project_id}/logo-revisions")
    async def create_branding_project_logo_revision(
        project_id: str, request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(project_id)
        require_running()
        comment = str(request.get("feedback") or request.get("comment") or "").strip()
        client_request_id = str(request.get("client_request_id") or "").strip()
        if not comment or len(comment) > 2000:
            raise HTTPException(status_code=409, detail="logo feedback must contain 1-2000 characters")
        if not client_request_id or len(client_request_id) > 200:
            raise HTTPException(status_code=409, detail="client_request_id is required")
        actor = f"firebase:{identity.uid}"
        try:
            async with operation_start_lock:
                require_no_active_codex()
                current = (
                    await laval_bridge(
                        "GET", f"/internal/web/branding/projects/{project_id}"
                    )
                ).json()
                existing = next((
                    item for item in current.get("logo_revisions") or []
                    if item.get("client_request_id") == client_request_id
                ), None)
                if existing:
                    return existing
                active = await active_heavy_operation()
                if active is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=f"{active.get('operation') or 'Heavy'} run {active['run_id']} is active",
                    )
                providers = (
                    await laval_bridge("GET", "/internal/web/branding/providers")
                ).json()
                if providers.get("revision_ready") is not True:
                    raise HTTPException(
                        status_code=409,
                        detail="Branding reference-edit contract is unavailable",
                    )
                target = read.brand_project_review_target(project_id)
                feedback = read.review(
                    creative_id=target["creative_id"],
                    artifact_digest=target["artifact_digest"], rating=None,
                    comment=comment, predicted_ctr=None, annotations=(),
                    decision="changes", actor=actor,
                    policy_path=settings.commander_policy_path,
                    asset_directory=settings.commander_asset_root,
                    supersedes_feedback_id=target["latest_feedback_id"],
                )
                return (
                    await laval_bridge(
                        "POST", f"/internal/web/branding/projects/{project_id}/logo-revisions",
                        body={
                            "feedback_id": feedback["feedback_id"],
                            "client_request_id": client_request_id, "actor": actor,
                        },
                    )
                ).json()
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/branding/projects/{project_id}/logo-revisions/{revision_id}")
    async def branding_project_logo_revision(
        project_id: str, revision_id: str,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(project_id); require_laval_id(revision_id)
        revision = (
            await laval_bridge(
                "GET", f"/internal/web/branding/projects/{project_id}/logo-revisions/{revision_id}"
            )
        ).json()
        return decorate_brand_project({"logo_revisions": [revision]})["logo_revisions"][0]

    @app.post("/api/v1/branding/projects/{project_id}/logo-revisions/{revision_id}/retry")
    async def retry_branding_project_logo_revision(
        project_id: str, revision_id: str,
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(project_id); require_laval_id(revision_id); require_running()
        async with operation_start_lock:
            require_no_active_codex()
            return (
                await laval_bridge(
                    "POST", f"/internal/web/branding/projects/{project_id}/logo-revisions/{revision_id}/retry",
                    body={"actor": f"firebase:{identity.uid}"},
                )
            ).json()

    @app.post("/api/v1/branding/projects/{project_id}/logo-revisions/{revision_id}/decision")
    async def decide_branding_project_logo_revision(
        project_id: str, revision_id: str, request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(project_id); require_laval_id(revision_id); require_running()
        decision = str(request.get("decision") or "").strip().lower()
        if decision not in {"approve", "reject"}:
            raise HTTPException(status_code=409, detail="decision must be approve or reject")
        if decision == "approve":
            async with operation_start_lock:
                require_no_active_codex()
                return (
                    await laval_bridge(
                        "POST", f"/internal/web/branding/projects/{project_id}/logo-revisions/{revision_id}/decision",
                        body={"decision": decision, "actor": f"firebase:{identity.uid}"},
                    )
                ).json()
        return (
            await laval_bridge(
                "POST", f"/internal/web/branding/projects/{project_id}/logo-revisions/{revision_id}/decision",
                body={"decision": decision, "actor": f"firebase:{identity.uid}"},
            )
        ).json()

    @app.post("/api/v1/branding/runs")
    async def create_branding_run(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_running()
        async with operation_start_lock:
            require_no_active_codex()
            return (
                await laval_bridge(
                    "POST",
                    "/internal/web/branding/runs",
                    body={**dict(request), "actor": f"firebase:{identity.uid}"},
                )
            ).json()

    @app.get("/api/v1/branding/runs/{run_id}")
    async def branding_run_status(
        run_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        result = (
            await laval_bridge("GET", f"/internal/web/branding/runs/{run_id}")
        ).json()
        for direction in result.get("directions") or []:
            digest = direction.get("artifact_digest")
            if digest:
                direction["logo_asset"] = {
                    "digest": digest,
                    "mime_type": "image/png",
                    "width": 1024,
                    "height": 1024,
                    "generation_provenance": direction.get("generation_provenance") or {},
                    "url": f"/api/v1/branding/assets/{digest}",
                    "cache": "private, no-store",
                }
        return result

    @app.get("/api/v1/branding/runs/{run_id}/stages")
    async def branding_run_stages(
        run_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        return (
            await laval_bridge(
                "GET", f"/internal/web/branding/runs/{run_id}/stages"
            )
        ).json()

    @app.get("/api/v1/branding/runs/{run_id}/show")
    async def branding_stage_output(
        run_id: str,
        stage: str,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        return (
            await laval_bridge(
                "GET",
                f"/internal/web/branding/runs/{run_id}/show",
                params={"stage": stage},
            )
        ).json()

    @app.get("/api/v1/branding/runs/{run_id}/directions")
    async def branding_directions(
        run_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        result = (
            await laval_bridge(
                "GET", f"/internal/web/branding/runs/{run_id}/directions"
            )
        ).json()
        for direction in result.get("items") or []:
            digest = direction.get("artifact_digest")
            if digest:
                direction["logo_asset"] = {
                    "digest": digest,
                    "mime_type": "image/png",
                    "width": 1024,
                    "height": 1024,
                    "generation_provenance": direction.get("generation_provenance") or {},
                    "url": f"/api/v1/branding/assets/{digest}",
                    "cache": "private, no-store",
                }
        return result

    @app.post("/api/v1/branding/runs/{run_id}/directions/{direction_id}/review")
    async def review_brand_logo(
        run_id: str,
        direction_id: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        require_laval_id(direction_id)
        require_running()
        try:
            target = read.brand_review_target(run_id, direction_id)
            decision = str(request.get("decision") or "changes").strip().lower()
            if decision not in {"changes", "approve"}:
                raise ValueError("review decision must be changes or approve")
            raw_annotations = request.get("annotations", request.get("regions", [])) or []
            if not isinstance(raw_annotations, list) or len(raw_annotations) > 100:
                raise ValueError("reviews support at most 100 annotations")
            annotations = tuple(region(item) for item in raw_annotations)
            raw_rating = request.get("rating")
            rating = None if raw_rating in (None, "") else int(raw_rating)
            if rating is not None and rating not in range(1, 6):
                raise ValueError("rating must be 1..5")
            comment = str(request.get("comment") or "").strip()
            if decision == "changes" and rating is None and not comment:
                raise ValueError("text feedback must not be empty")
            if decision == "approve" and (comment or rating is not None or annotations):
                raise ValueError("approval must not include correction feedback")
            async with operation_start_lock:
                if decision == "changes":
                    require_no_active_codex()
                    active = await active_heavy_operation()
                    if active is not None:
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                f"{active.get('operation') or 'Heavy'} run "
                                f"{active['run_id']} is active"
                            ),
                        )
                result = read.review(
                    creative_id=target["creative_id"],
                    artifact_digest=target["artifact_digest"],
                    rating=rating,
                    comment=comment,
                    predicted_ctr=None,
                    annotations=annotations,
                    decision=decision,
                    actor=f"firebase:{identity.uid}",
                    policy_path=settings.commander_policy_path,
                    asset_directory=settings.commander_asset_root,
                    supersedes_feedback_id=target["latest_feedback_id"],
                )
                if decision == "changes":
                    regeneration = (
                        await laval_bridge(
                            "POST",
                            f"/internal/web/branding/runs/{run_id}/directions/{direction_id}/regenerate",
                            body={
                                "feedback_id": result["feedback_id"],
                                "actor": f"firebase:{identity.uid}",
                            },
                        )
                    ).json()
                    return {
                        **result, "direction_id": direction_id,
                        "decision": decision, "regeneration": regeneration,
                    }
            return {**result, "direction_id": direction_id, "decision": decision}
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/v1/branding/runs/{run_id}/directions/{direction_id}/regenerate"
    )
    async def retry_brand_logo_regeneration(
        run_id: str,
        direction_id: str,
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        require_laval_id(direction_id)
        require_running()
        try:
            target = read.brand_review_target(run_id, direction_id)
            if not target["latest_feedback_id"]:
                raise ValueError("the current logo has no correction feedback")
            async with operation_start_lock:
                require_no_active_codex()
                active = await active_heavy_operation()
                if active is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"{active.get('operation') or 'Heavy'} run "
                            f"{active['run_id']} is active"
                        ),
                    )
                return (
                    await laval_bridge(
                        "POST",
                        f"/internal/web/branding/runs/{run_id}/directions/{direction_id}/regenerate",
                        body={
                            "feedback_id": target["latest_feedback_id"],
                            "actor": f"firebase:{identity.uid}",
                        },
                    )
                ).json()
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/branding/runs/{run_id}/directions/{direction_id}/reviews")
    def brand_logo_reviews(
        run_id: str,
        direction_id: str,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        require_laval_id(direction_id)
        try:
            target = read.brand_review_target(run_id, direction_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"items": read.creative_reviews(target["creative_id"])}

    @app.post("/api/v1/branding/runs/{run_id}/{action}")
    async def control_branding_run(
        run_id: str,
        action: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        if action not in {"pause", "resume", "rerun", "approve"}:
            raise HTTPException(status_code=404, detail="unknown Branding action")
        if action != "pause":
            require_running()
        payload = {**dict(request), "actor": f"firebase:{identity.uid}"}
        if action in {"resume", "rerun", "approve"}:
            async with operation_start_lock:
                require_no_active_codex()
                return (
                    await laval_bridge(
                        "POST",
                        f"/internal/web/branding/runs/{run_id}/{action}",
                        body=payload,
                    )
                ).json()
        return (
            await laval_bridge(
                "POST",
                f"/internal/web/branding/runs/{run_id}/{action}",
                body=payload,
            )
        ).json()

    @app.get("/api/v1/branding/kits/{kit_id}")
    async def brand_kit(
        kit_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(kit_id)
        result = (
            await laval_bridge("GET", f"/internal/web/branding/kits/{kit_id}")
        ).json()
        digest = result.get("zip_digest")
        if digest:
            result["download"] = {
                "digest": digest,
                "mime_type": "application/zip",
                "url": f"/api/v1/branding/kits/{kit_id}/download",
                "cache": "private, no-store",
            }
        return result

    @app.get("/api/v1/branding/assets/{digest}")
    async def brand_asset(
        digest: str, _identity: OwnerIdentity = Depends(owner)
    ) -> Response:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise HTTPException(status_code=400, detail="invalid artifact digest")
        response = await laval_bridge(
            "GET", f"/internal/web/branding/assets/{digest}"
        )
        return Response(
            response.content,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            headers={"Cache-Control": "private, no-store"},
        )

    @app.get("/api/v1/branding/kits/{kit_id}/download")
    async def download_brand_kit(
        kit_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> Response:
        require_laval_id(kit_id)
        kit = (
            await laval_bridge("GET", f"/internal/web/branding/kits/{kit_id}")
        ).json()
        digest = str(kit.get("zip_digest") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise HTTPException(status_code=404, detail="Brand Kit archive is unavailable")
        response = await laval_bridge(
            "GET", f"/internal/web/branding/assets/{digest}"
        )
        return Response(
            response.content,
            media_type="application/zip",
            headers={
                "Content-Disposition": response.headers.get(
                    "content-disposition", 'attachment; filename="brand-kit.zip"'
                ),
                "Cache-Control": "private, no-store",
            },
        )

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

    @app.get("/api/v1/laval/runs/{run_id}/theses")
    async def laval_theses(
        run_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        return (await laval_bridge("GET", f"/internal/web/laval/runs/{run_id}/theses")).json()

    @app.post("/api/v1/laval/runs/{run_id}/theses/{thesis_id}/select")
    async def select_laval_thesis(
        run_id: str,
        thesis_id: str,
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        require_laval_id(thesis_id)
        require_running()
        theses = (await laval_bridge("GET", f"/internal/web/laval/runs/{run_id}/theses")).json()
        thesis = next((item for item in theses.get("items") or [] if str(item.get("id")) == thesis_id), None)
        if not thesis:
            raise HTTPException(status_code=404, detail="product thesis not found")
        if thesis.get("verdict") != "survives" or not thesis.get("commander_hypothesis_id"):
            raise HTTPException(status_code=409, detail="only a published surviving thesis can enter validation")
        actor = f"firebase:{identity.uid}"
        validation = (await commander_bridge("POST", "/internal/validations/select", body={
            "hypothesis_id": thesis["commander_hypothesis_id"],
            "run_id": run_id,
            "thesis_id": thesis_id,
            "actor": actor,
        })).json()
        workspace_id = str((validation.get("workspace") or {}).get("id") or "")
        if not workspace_id:
            raise HTTPException(status_code=502, detail="Commander did not return a validation workspace")
        selection = (await laval_bridge(
            "POST", f"/internal/web/laval/runs/{run_id}/theses/{thesis_id}/select",
            body={"workspace_id": workspace_id, "actor": actor},
        )).json()
        return {**validation, "selection": selection}

    @app.post("/api/v1/laval/runs/{run_id}/youtube-transcripts")
    async def add_laval_youtube_transcript(
        run_id: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(run_id)
        require_running()
        return (await laval_bridge(
            "POST", f"/internal/web/laval/runs/{run_id}/youtube-transcripts",
            body={**dict(request), "actor": f"firebase:{identity.uid}"},
        )).json()

    @app.get("/api/v1/validations")
    async def validations(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await commander_bridge("GET", "/internal/validations")).json()

    @app.get("/api/v1/validations/{workspace_id}")
    async def validation(
        workspace_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(workspace_id)
        return (await commander_bridge("GET", f"/internal/validations/{workspace_id}")).json()

    @app.post("/api/v1/validations/{workspace_id}/probes")
    async def create_probe(
        workspace_id: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(workspace_id)
        require_running()
        return (await commander_bridge(
            "POST", f"/internal/validations/{workspace_id}/probes",
            body={**dict(request), "actor": f"firebase:{identity.uid}"},
        )).json()

    @app.post("/api/v1/probes/{probe_id}/start")
    async def start_probe(
        probe_id: str, identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        require_laval_id(probe_id)
        require_running()
        return (await commander_bridge(
            "POST", f"/internal/probes/{probe_id}/start",
            body={"actor": f"firebase:{identity.uid}"},
        )).json()

    async def record_probe_result(
        probe_id: str, request: Mapping[str, Any], identity: OwnerIdentity
    ) -> dict[str, Any]:
        require_laval_id(probe_id)
        require_running()
        return (await commander_bridge(
            "POST", f"/internal/probes/{probe_id}/observations",
            body={**dict(request), "actor": f"firebase:{identity.uid}"},
        )).json()

    @app.post("/api/v1/probes/{probe_id}/observations")
    async def probe_observation(
        probe_id: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return await record_probe_result(probe_id, request, identity)

    @app.post("/api/v1/probes/{probe_id}/complete")
    async def complete_probe(
        probe_id: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return await record_probe_result(probe_id, request, identity)

    @app.post("/api/v1/validations/{workspace_id}/decision")
    async def validation_decision(
        workspace_id: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(workspace_id)
        require_running()
        return (await commander_bridge(
            "POST", f"/internal/validations/{workspace_id}/decision",
            body={**dict(request), "actor": f"firebase:{identity.uid}"},
        )).json()

    @app.post("/api/v1/validations/{workspace_id}/plan")
    async def plan_validation(
        workspace_id: str,
        request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        require_laval_id(workspace_id)
        require_running()
        actor = f"firebase:{identity.uid}"
        context = (await commander_bridge(
            "POST", f"/internal/validations/{workspace_id}/consume-context", body={"actor": actor}
        )).json()
        requested = str(request.get("request") or "Create a product implementation plan from the validated thesis. Do not execute it.").strip()
        instruction = (
            f"{requested}\n\nUse this bounded PTW validation context. Treat recorded observations as facts and insights as interpretations. "
            "Do not request UUID copying and do not broaden into external execution.\n\n"
            + json.dumps(context, ensure_ascii=False, default=str)[:16_000]
        )
        async with operation_start_lock:
            await require_no_active_laval()
            require_no_active_codex()
            try:
                command = store.create_command("plan", instruction)
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            background(build_plan(command["id"], instruction))
            return command

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
        format: str = Query(default="json", pattern="^(json|md|pdf)$"),
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
        if action not in {"run", "pause", "resume", "resume-market-signals", "approve", "rerun", "override", "notify"}:
            raise HTTPException(status_code=404, detail="unknown Laval action")
        if action == "notify" and not settings.outbound_notifications_enabled:
            raise HTTPException(status_code=410, detail="outbound notifications are retired")
        if action not in {"pause", "notify"}:
            require_running()
        payload = {**dict(request), "actor": f"firebase:{identity.uid}"}
        if action in {"run", "resume", "resume-market-signals", "approve", "rerun"}:
            async with operation_start_lock:
                require_no_active_codex()
                return (await laval_bridge("POST", f"/internal/web/laval/runs/{run_id}/{action}", body=payload)).json()
        return (await laval_bridge("POST", f"/internal/web/laval/runs/{run_id}/{action}", body=payload)).json()

    @app.get("/api/v1/posts")
    def posts(
        limit: int = Query(default=20, ge=1, le=100),
        review_status: str | None = Query(default=None, pattern="^(pending|reviewed)$"),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        creative_gone()
        return read.posts(limit=limit, review_status=review_status)

    @app.post("/api/v1/posts")
    def create_post(request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        creative_gone()
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
        creative_gone()
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
        creative_gone()
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", creative_id):
            raise HTTPException(status_code=400, detail="invalid Creative UUID")
        return {"items": read.creative_reviews(creative_id)}

    @app.get("/api/v1/artifacts/{digest}")
    def artifact(digest: str, _identity: OwnerIdentity = Depends(owner)) -> FileResponse:
        creative_gone()
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
    async def create_job(request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        mode = str(request.get("mode", "plan"))
        instruction = str(request.get("instruction", "")).strip()
        if mode not in {"plan", "execute"} or not instruction or len(instruction) > 20_000:
            raise HTTPException(status_code=400, detail="mode and 1-20000 character instruction are required")
        async with operation_start_lock:
            await require_no_active_laval()
            require_no_active_codex()
            try:
                command = store.create_command(mode, instruction)
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            background(build_plan(command["id"], instruction))
            return command

    @app.get("/api/v1/command-sessions")
    def command_sessions(limit: int = Query(default=30, ge=1, le=100), _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return {"items": store.commands(limit), "next_cursor": None}

    @app.get("/api/v1/issues")
    def issues(limit: int = Query(default=30, ge=1, le=100), _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return {"items": platform.issues(limit), "next_cursor": None}

    @app.post("/api/v1/command-sessions/{session_id}/approve")
    async def approve(session_id: str, request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        destructive_allowed = request.get("destructive_confirmation") == "EXECUTE DESTRUCTIVE PLAN"
        async with operation_start_lock:
            await require_no_active_laval()
            require_no_active_codex(exclude_id=session_id)
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
