from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Mapping
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse

from .catalog import catalog
from .config import Settings
from .domain import markdown_export
from .provider import BridgeProvider, DataForSEOProvider
from .repository import PositioningRepository
from .service import PositioningRunner, validate_create_input, validate_revision_input


def create_app(
    settings: Settings | None = None,
    *,
    repository: PositioningRepository | None = None,
    runner: PositioningRunner | None = None,
) -> FastAPI:
    settings = settings or Settings.from_environment()
    repository = repository or PositioningRepository(settings.database_url)
    runner_error: Exception | None = None
    if runner is None:
        try:
            if settings.research_provider != "dataforseo" or not settings.dataforseo_verified:
                raise RuntimeError("live Marketing Positioning requires verified DataForSEO; no fallback is allowed")
            runner = PositioningRunner(
                repository,
                BridgeProvider(settings.bridge_url, settings.bridge_token, settings.model),
                DataForSEOProvider(
                    settings.dataforseo_login, settings.dataforseo_password,
                    poll_timeout_seconds=settings.dataforseo_poll_timeout_seconds,
                ),
                skill_path=settings.skill_path,
                max_spend_usd=settings.max_spend_usd,
            )
        except Exception as error:
            runner_error = error
    tasks: set[asyncio.Task[Any]] = set()
    stopped = False

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await asyncio.to_thread(repository.recover_interrupted)
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(
        title="PTW Marketing Positioning API", version="1.0.0",
        docs_url=None, redoc_url=None, lifespan=lifespan,
    )

    def authorize(x_ptw_owner_gateway_token: str = Header(default="")) -> None:
        if not settings.owner_gateway_token or x_ptw_owner_gateway_token != settings.owner_gateway_token:
            raise HTTPException(status_code=401, detail="owner gateway authentication required")

    def require_runner() -> PositioningRunner:
        if runner is None:
            raise HTTPException(status_code=503, detail=str(runner_error or "positioning runner is unavailable"))
        if stopped:
            raise HTTPException(status_code=423, detail="PTW emergency stop is active")
        return runner

    def background_generate(revision_id: str, *, operation_reserved: bool = False) -> None:
        active_runner = require_runner()
        if not operation_reserved:
            repository.acquire_operation("marketing_positioning", revision_id)
        async def execute() -> None:
            try:
                await asyncio.to_thread(
                    active_runner.generate, revision_id, operation_reserved=True
                )
            except Exception:
                # Durable revision and attempt rows carry the bounded failure.
                return
        task = asyncio.create_task(execute())
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> dict[str, Any]:
        if runner is None:
            raise HTTPException(status_code=503, detail=str(runner_error or "runner unavailable"))
        try:
            with repository.connection() as connection:
                connection.execute("SELECT 1").fetchone()
            readiness = runner.verify_ready()
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"positioning dependency unavailable: {type(error).__name__}") from error
        return readiness

    @app.get("/internal/v1/catalog", dependencies=[Depends(authorize)])
    def provider_catalog() -> dict[str, object]:
        return catalog()

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

    @app.post("/internal/v1/positionings", dependencies=[Depends(authorize)])
    async def create_positioning(request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        require_runner()
        try:
            value = validate_create_input(request)
            project, revision, created = repository.create_project(**value, requested_by=x_ptw_actor[:200])
            if created:
                background_generate(revision["id"])
            return {"project": project, "revision": revision, "created": created}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/internal/v1/positionings", dependencies=[Depends(authorize)])
    def list_positionings(limit: int = Query(default=50, ge=1, le=100)) -> dict[str, Any]:
        return {"items": repository.list_projects(limit), "next_cursor": None}

    @app.get("/internal/v1/positionings/{project_id}", dependencies=[Depends(authorize)])
    def positioning(project_id: str) -> dict[str, Any]:
        try:
            return repository.get_project(str(UUID(project_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="positioning project not found") from error

    @app.post("/internal/v1/positionings/{project_id}/revisions", dependencies=[Depends(authorize)])
    async def create_revision(project_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        require_runner()
        try:
            value = validate_revision_input(request)
            revision, created = repository.create_revision(
                project_id=str(UUID(project_id)), requested_by=x_ptw_actor[:200], **value
            )
            if created:
                background_generate(revision["id"])
            return {"revision": revision, "created": created}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="base positioning revision not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/internal/v1/positioning-revisions/{revision_id}/retry", dependencies=[Depends(authorize)])
    async def retry_revision(revision_id: str) -> dict[str, Any]:
        require_runner()
        try:
            revision_id = str(UUID(revision_id))
            repository.get_revision(revision_id)
            repository.acquire_operation("marketing_positioning", revision_id)
            try:
                revision = repository.queue_retry(revision_id)
            except Exception:
                repository.release_operation(revision_id)
                raise
            background_generate(revision["id"], operation_reserved=True)
            return revision
        except KeyError as error:
            raise HTTPException(status_code=404, detail="positioning revision not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/positioning-revisions/{revision_id}/approve", dependencies=[Depends(authorize)])
    def approve_revision(revision_id: str, x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        try:
            return repository.approve(str(UUID(revision_id)), x_ptw_actor[:200])
        except KeyError as error:
            raise HTTPException(status_code=404, detail="positioning revision not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get(
        "/internal/v1/positioning-revisions/{revision_id}/export.md",
        dependencies=[Depends(authorize)], response_class=PlainTextResponse,
    )
    def export_revision(revision_id: str) -> PlainTextResponse:
        try:
            revision = repository.get_revision(str(UUID(revision_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="positioning revision not found") from error
        if revision["status"] != "completed" or not revision["document"]:
            raise HTTPException(status_code=409, detail="positioning revision is not complete")
        return PlainTextResponse(
            markdown_export(revision["document"]),
            headers={"Content-Disposition": f'attachment; filename="positioning-{revision_id}.md"'},
        )

    @app.get("/internal/v1/positionings/{project_id}/skill-proposals", dependencies=[Depends(authorize)])
    def positioning_skill_proposals(project_id: str) -> dict[str, Any]:
        try:
            repository.get_project(str(UUID(project_id)))
            return {"items": repository.skill_proposals(str(UUID(project_id)))}
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="positioning project not found") from error

    @app.post("/internal/v1/positioning-skill-proposals/{proposal_id}/update", dependencies=[Depends(authorize)])
    def update_positioning_skill_proposal(proposal_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"lesson"}:
            raise HTTPException(status_code=400, detail="lesson is required")
        try:
            return repository.update_skill_proposal(str(UUID(proposal_id)), str(request["lesson"]))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="positioning lesson proposal not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/positioning-skill-proposals/{proposal_id}/dismiss", dependencies=[Depends(authorize)])
    def dismiss_positioning_skill_proposal(proposal_id: str) -> dict[str, Any]:
        try:
            return repository.dismiss_skill_proposal(str(UUID(proposal_id)))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="positioning lesson proposal not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/positioning-skill-proposals/{proposal_id}/plan", dependencies=[Depends(authorize)])
    def plan_positioning_skill_proposal(proposal_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"lesson", "command_session_id"}:
            raise HTTPException(status_code=400, detail="lesson and command_session_id are required")
        try:
            return repository.plan_skill_proposal(
                str(UUID(proposal_id)), str(request["lesson"]), str(UUID(str(request["command_session_id"])))
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="positioning lesson proposal not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
