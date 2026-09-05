"""Internal API for Product Briefs and Project-scoped Studio creatives."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Mapping
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .config import Settings
from .images import PexelsClient
from .openai_images import ResultBridgePhoneScreenImageProvider
from .provider import StructuredBridge
from .repository import ValidationRepository
from .service import ValidationRunner, validate_create_input, validate_revision_input
from .studio import StudioRenderer
from .landing_pages import DatabaseLandingAuthority, DatabaseLandingWorkspace, LandingService
from .landing_routes import landing_page_router
from .landing_workspace import LandingWorkspace
from .studio_creatives import StudioCreativeService
from .studio_repository import DatabaseCreativeWorkspace, DatabaseStudioAuthority
from .studio_routes import studio_creative_router
from .studio_workspace import UniversalStudioWorkspace


def create_app(
    settings: Settings | None = None,
    *,
    repository: ValidationRepository | None = None,
    runner: ValidationRunner | None = None,
    studio_renderer: StudioRenderer | None = None,
    studio_workspace: UniversalStudioWorkspace | None = None,
    studio_creative_service: StudioCreativeService | None = None,
    landing_page_service: LandingService | None = None,
) -> FastAPI:
    settings = settings or Settings.from_environment()
    repository = repository or ValidationRepository(settings.database_url)
    bridge = StructuredBridge(settings.bridge_url, settings.bridge_token, settings.model)
    pexels = PexelsClient(settings.pexels_api_key)
    studio_renderer = studio_renderer or StudioRenderer()
    if studio_creative_service is not None:
        studio_creatives = studio_creative_service
    else:
        studio_authority = DatabaseStudioAuthority(settings.database_url)
        image_provider = ResultBridgePhoneScreenImageProvider(
            settings.bridge_url, settings.bridge_token, settings.model,
        )
        if studio_workspace is not None:
            workspace_factory = lambda _path: studio_workspace
        else:
            workspace_factory = lambda path: DatabaseCreativeWorkspace(
                UniversalStudioWorkspace(
                    path, renderer=studio_renderer, pexels=pexels,
                    image_provider=image_provider,
                ),
                studio_authority.repository, path.name,
            )
        studio_creatives = StudioCreativeService(
            root=settings.studio_workspace_path, authority=studio_authority,
            workspace_factory=workspace_factory, structured_provider=bridge,
            composer_skill_path=settings.studio_composer_skill_path,
            learner_skill_path=settings.studio_learner_skill_path,
            phone_skill_path=settings.studio_phone_skill_path,
        )
    if landing_page_service is not None:
        landing_pages = landing_page_service
    else:
        landing_authority = DatabaseLandingAuthority(settings.database_url)
        landing_images = ResultBridgePhoneScreenImageProvider(
            settings.bridge_url, settings.bridge_token, settings.model,
        )
        landing_pages = LandingService(
            root=settings.landing_workspace_path, authority=landing_authority,
            workspace_factory=lambda path: DatabaseLandingWorkspace(
                LandingWorkspace(path, image_provider=landing_images), landing_authority, path.name,
            ),
            structured_provider=bridge, composer_skill_path=settings.landing_composer_skill_path,
            learner_skill_path=settings.landing_learner_skill_path,
        )
    runner_error: Exception | None = None
    if runner is None:
        try:
            runner = ValidationRunner(
                repository, bridge, product_brief_skill_path=settings.product_brief_skill_path
            )
        except Exception as error:
            runner_error = error

    tasks: set[asyncio.Task[Any]] = set()
    stopped = False

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await asyncio.to_thread(repository.recover_interrupted)
        for creative_id in await asyncio.to_thread(studio_creatives.recover_interrupted):
            task = asyncio.create_task(asyncio.to_thread(studio_creatives.generate, creative_id))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
        for landing_id in await asyncio.to_thread(landing_pages.recover_interrupted):
            task = asyncio.create_task(asyncio.to_thread(landing_pages.generate, landing_id))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
        for item in await asyncio.to_thread(studio_creatives.recover_learning):
            task = asyncio.create_task(asyncio.to_thread(
                studio_creatives.retry_learning, item["project_id"],
                item["creative_id"], item["checkpoint_id"],
            ))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(
        title="PTW Validation API", version="1.0.0", docs_url=None, redoc_url=None,
        lifespan=lifespan,
    )

    def authorize(x_ptw_owner_gateway_token: str = Header(default="")) -> None:
        if not settings.owner_gateway_token or x_ptw_owner_gateway_token != settings.owner_gateway_token:
            raise HTTPException(status_code=401, detail="owner gateway authentication required")

    app.include_router(studio_creative_router(
        studio_creatives, prefix="/internal/v1/studio", dependencies=[Depends(authorize)],
    ))
    app.include_router(landing_page_router(
        landing_pages, prefix="/internal/v1/landings", dependencies=[Depends(authorize)],
    ))

    def require_brief_runner() -> ValidationRunner:
        if runner is None:
            raise HTTPException(status_code=503, detail=str(runner_error or "Product Brief runner unavailable"))
        if stopped:
            raise HTTPException(status_code=423, detail="PTW emergency stop is active")
        return runner

    def run_background(function: Any, identifier: str, *, reserved: bool = False) -> None:
        """Schedule work from an async route handler on the serving event loop."""
        async def execute() -> None:
            try:
                if reserved:
                    await asyncio.to_thread(function, identifier, operation_reserved=True)
                else:
                    await asyncio.to_thread(function, identifier)
            except Exception:
                return
        task = asyncio.get_running_loop().create_task(execute())
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> dict[str, Any]:
        active = require_brief_runner()
        try:
            with repository.connection() as connection:
                connection.execute("SELECT 1").fetchone()
            return active.verify_ready()
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=f"Validation dependency unavailable: {type(error).__name__}",
            ) from error

    @app.get("/internal/activity", dependencies=[Depends(authorize)])
    def activity() -> dict[str, Any]:
        return repository.activity()

    @app.post("/internal/emergency-stop", dependencies=[Depends(authorize)])
    def emergency_stop(request: Mapping[str, Any]) -> dict[str, bool]:
        nonlocal stopped
        if set(request) != {"active", "actor"} or not isinstance(request.get("active"), bool):
            raise HTTPException(status_code=400, detail="active boolean and actor are required")
        stopped = bool(request["active"])
        return {"emergency_stop": stopped}

    @app.get("/internal/v1/projects", dependencies=[Depends(authorize)])
    def projects(limit: int = Query(default=100, ge=1, le=100)) -> dict[str, Any]:
        return {"items": repository.list_projects(limit), "next_cursor": None}

    @app.post("/internal/v1/projects/{project_id}/rename", dependencies=[Depends(authorize)])
    def rename_project(
        project_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"name"} or not isinstance(request.get("name"), str):
            raise HTTPException(status_code=400, detail="Project rename requires one name")
        try:
            return repository.rename_project(
                str(UUID(project_id)), name=str(request["name"]), requested_by=x_ptw_actor[:200]
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Project not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/internal/v1/briefs", dependencies=[Depends(authorize)], status_code=202)
    async def create_brief(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        active = require_brief_runner()
        try:
            value = validate_create_input(request)
            brief, created = repository.create_brief(
                **value, requested_by=x_ptw_actor[:200], reserve_operation=True
            )
            if brief["status"] == "queued":
                run_background(active.generate_brief, brief["brief_id"], reserved=True)
            return {"project": repository.get_project(brief["project_id"]), "brief": brief, "created": created}
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/briefs", dependencies=[Depends(authorize)])
    def briefs(
        project_id: str | None = None, limit: int = Query(default=100, ge=1, le=100)
    ) -> dict[str, Any]:
        try:
            normalized = None if project_id is None else str(UUID(project_id))
            return {"items": repository.list_briefs(limit, project_id=normalized), "next_cursor": None}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Project ID") from error

    @app.get("/internal/v1/briefs/{brief_id}", dependencies=[Depends(authorize)])
    def brief(brief_id: str) -> dict[str, Any]:
        try:
            return repository.get_brief(str(UUID(brief_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error

    @app.post("/internal/v1/briefs/{brief_id}/correct", dependencies=[Depends(authorize)], status_code=202)
    async def revise_brief(
        brief_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        active = require_brief_runner()
        try:
            value = validate_revision_input(request)
            replacement, created = repository.create_revision(
                base_brief_id=str(UUID(brief_id)), requested_by=x_ptw_actor[:200],
                reserve_operation=True, **value
            )
            if replacement["status"] == "queued":
                run_background(active.generate_brief, replacement["brief_id"], reserved=True)
            return {"brief": replacement, "created": created}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="base Product Brief not found") from error
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/briefs/{brief_id}/retry", dependencies=[Depends(authorize)], status_code=202)
    async def retry_brief(brief_id: str) -> dict[str, Any]:
        active = require_brief_runner()
        try:
            normalized = str(UUID(brief_id))
            repository.acquire_operation("product_brief", normalized)
            try:
                value = repository.queue_retry(normalized, stage="product_brief")
            except Exception:
                repository.release_operation(normalized)
                raise
            run_background(active.generate_brief, normalized, reserved=True)
            return value
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/briefs/{brief_id}/approve", dependencies=[Depends(authorize)], status_code=202)
    async def approve_brief(
        brief_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        template_id = str(request.get("template_id") or "")
        expected = (
            {"honor_confirmed", "template_id", "creative_direction"}
            if template_id == "phone_metrics" else {"honor_confirmed", "template_id"}
        )
        if set(request) != expected or request.get("honor_confirmed") is not True:
            raise HTTPException(
                status_code=400,
                detail="Brief approval requires explicit confirmation that the promise and offer can be honored",
            )
        try:
            normalized = str(UUID(brief_id))
            value, created, creative, creative_created = (
                studio_creatives.approve_brief_and_reserve(
                    brief_id=normalized, template_id=template_id,
                    requested_by=x_ptw_actor[:200],
                    brief_approver=repository.approve_brief,
                    creative_direction=request.get("creative_direction"),
                )
            )
            if creative_created:
                run_background(studio_creatives.generate, creative["creative_id"])
            return {
                "brief": value, "approved_now": created,
                "creative": creative, "creative_created": creative_created,
            }
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
