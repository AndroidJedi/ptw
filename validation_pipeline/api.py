from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Mapping
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import Response

from .config import Settings
from .images import PexelsClient, SquareCreativeRenderer
from .notifications import FailureNotificationClient
from .provider import StructuredBridge
from .repository import ValidationRepository
from .service import ValidationRunner, validate_create_input, validate_revision_input


def create_app(
    settings: Settings | None = None,
    *,
    repository: ValidationRepository | None = None,
    runner: ValidationRunner | None = None,
) -> FastAPI:
    settings = settings or Settings.from_environment()
    repository = repository or ValidationRepository(settings.database_url)
    runner_error: Exception | None = None
    if runner is None:
        try:
            runner = ValidationRunner(
                repository,
                StructuredBridge(settings.bridge_url, settings.bridge_token, settings.model),
                PexelsClient(settings.pexels_api_key),
                SquareCreativeRenderer(),
                product_brief_skill_path=settings.product_brief_skill_path,
                ad_creative_skill_path=settings.ad_creative_skill_path,
                failure_notifier=FailureNotificationClient(
                    settings.failure_notification_url,
                    settings.owner_gateway_token,
                ),
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
        title="PTW Validation API", version="1.0.0", docs_url=None, redoc_url=None, lifespan=lifespan
    )

    def authorize(x_ptw_owner_gateway_token: str = Header(default="")) -> None:
        if not settings.owner_gateway_token or x_ptw_owner_gateway_token != settings.owner_gateway_token:
            raise HTTPException(status_code=401, detail="owner gateway authentication required")

    def require_runner() -> ValidationRunner:
        if runner is None:
            raise HTTPException(status_code=503, detail=str(runner_error or "validation runner is unavailable"))
        if stopped:
            raise HTTPException(status_code=423, detail="PTW emergency stop is active")
        return runner

    def background(method: Any, target_id: str, *, reserved: bool = False) -> None:
        active = require_runner()
        async def execute() -> None:
            try:
                await asyncio.to_thread(method, target_id, operation_reserved=reserved)
            except Exception:
                return
        task = asyncio.create_task(execute())
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> dict[str, Any]:
        active = require_runner()
        try:
            with repository.connection() as connection:
                connection.execute("SELECT 1").fetchone()
            return active.verify_ready()
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"validation dependency unavailable: {type(error).__name__}") from error

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

    @app.post("/internal/v1/briefs", dependencies=[Depends(authorize)], status_code=202)
    async def create_brief(request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        active = require_runner()
        try:
            value = validate_create_input(request)
            brief, created = repository.create_brief(**value, requested_by=x_ptw_actor[:200])
            if brief["status"] == "queued":
                if repository.acquire_operation("product_brief", brief["brief_id"]):
                    background(active.generate_brief, brief["brief_id"], reserved=True)
            return {"brief": brief, "created": created}
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/briefs", dependencies=[Depends(authorize)])
    def briefs(limit: int = Query(default=100, ge=1, le=100)) -> dict[str, Any]:
        return {"items": repository.list_briefs(limit), "next_cursor": None}

    @app.get("/internal/v1/briefs/{brief_id}", dependencies=[Depends(authorize)])
    def brief(brief_id: str) -> dict[str, Any]:
        try:
            return repository.get_brief(str(UUID(brief_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error

    @app.post("/internal/v1/briefs/{brief_id}/correct", dependencies=[Depends(authorize)], status_code=202)
    async def revise_brief(brief_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        active = require_runner()
        try:
            value = validate_revision_input(request)
            replacement, created = repository.create_revision(
                base_brief_id=str(UUID(brief_id)), requested_by=x_ptw_actor[:200], **value
            )
            if replacement["status"] == "queued":
                if repository.acquire_operation("product_brief", replacement["brief_id"]):
                    background(active.generate_brief, replacement["brief_id"], reserved=True)
            return {"brief": replacement, "created": created}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="base Product Brief not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/briefs/{brief_id}/retry", dependencies=[Depends(authorize)], status_code=202)
    async def retry_brief(brief_id: str) -> dict[str, Any]:
        active = require_runner()
        try:
            brief_id = str(UUID(brief_id))
            acquired = repository.acquire_operation("product_brief", brief_id)
            if not acquired:
                return repository.get_brief(brief_id)
            try:
                value = repository.queue_retry(brief_id, stage="product_brief")
            except Exception:
                repository.release_operation(brief_id)
                raise
            background(active.generate_brief, brief_id, reserved=True)
            return value
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/briefs/{brief_id}/approve", dependencies=[Depends(authorize)], status_code=202)
    async def approve_brief(brief_id: str, x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        active = require_runner()
        try:
            batch, should_start = repository.approve_and_queue_batch(str(UUID(brief_id)), x_ptw_actor[:200])
            if should_start:
                background(active.generate_batch, batch["batch_id"], reserved=True)
            return {
                "brief": repository.get_brief(brief_id),
                "batch": batch,
                "generation_started": should_start,
            }
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/ad-batches", dependencies=[Depends(authorize)])
    def batches(brief_id: str | None = None, limit: int = Query(default=100, ge=1, le=100)) -> dict[str, Any]:
        try:
            normalized_brief_id = None if brief_id is None else str(UUID(brief_id))
            return {"items": repository.list_batches(limit, brief_id=normalized_brief_id), "next_cursor": None}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Product Brief ID") from error

    @app.get("/internal/v1/ad-batches/{batch_id}", dependencies=[Depends(authorize)])
    def batch(batch_id: str) -> dict[str, Any]:
        try:
            return repository.get_batch(str(UUID(batch_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="creative batch not found") from error

    @app.post("/internal/v1/ad-batches/{batch_id}/retry", dependencies=[Depends(authorize)], status_code=202)
    async def retry_batch(batch_id: str) -> dict[str, Any]:
        active = require_runner()
        try:
            batch_id = str(UUID(batch_id))
            acquired = repository.acquire_operation("ad_creative_batch", batch_id)
            if not acquired:
                return repository.get_batch(batch_id)
            try:
                value = repository.queue_retry(batch_id, stage="ad_creative_batch")
            except Exception:
                repository.release_operation(batch_id)
                raise
            background(active.generate_batch, batch_id, reserved=True)
            return value
        except KeyError as error:
            raise HTTPException(status_code=404, detail="creative batch not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/ad-creatives/{creative_id}/image", dependencies=[Depends(authorize)])
    def creative_image(creative_id: str, if_none_match: str = Header(default="")) -> Response:
        try:
            value = repository.image(str(UUID(creative_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="creative image not found") from error
        etag = f'"{value["sha256"]}"'
        headers = {"ETag": etag, "Cache-Control": "private, max-age=31536000, immutable"}
        if if_none_match == etag:
            return Response(status_code=304, headers=headers)
        return Response(value["bytes"], media_type=value["mime_type"], headers=headers)

    @app.post("/internal/v1/ad-creatives/{creative_id}/feedback", dependencies=[Depends(authorize)])
    def creative_feedback(creative_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        if set(request) != {"comment"}:
            raise HTTPException(status_code=400, detail="feedback requires one comment")
        try:
            return repository.record_creative_feedback(
                str(UUID(creative_id)), comment=str(request["comment"]), requested_by=x_ptw_actor[:200]
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="creative not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/skill-proposals/{domain}", dependencies=[Depends(authorize)])
    def proposals(domain: str, target_id: str | None = None) -> dict[str, Any]:
        try:
            return {"items": repository.proposals(domain, target_id=target_id)}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/{domain}/{proposal_id}/update", dependencies=[Depends(authorize)])
    def update_proposal(domain: str, proposal_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"lesson"}:
            raise HTTPException(status_code=400, detail="lesson is required")
        try:
            return repository.update_proposal(domain, str(UUID(proposal_id)), lesson=str(request["lesson"]))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/{domain}/{proposal_id}/dismiss", dependencies=[Depends(authorize)])
    def dismiss_proposal(domain: str, proposal_id: str) -> dict[str, Any]:
        try:
            return repository.update_proposal(domain, str(UUID(proposal_id)), status="rejected")
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/{domain}/{proposal_id}/plan", dependencies=[Depends(authorize)])
    def plan_proposal(domain: str, proposal_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"lesson", "command_session_id"}:
            raise HTTPException(status_code=400, detail="lesson and command_session_id are required")
        try:
            return repository.update_proposal(
                domain, str(UUID(proposal_id)), lesson=str(request["lesson"]), status="planning",
                command_session_id=str(UUID(str(request["command_session_id"]))),
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/by-command/{command_session_id}/finish", dependencies=[Depends(authorize)])
    def finish_proposal(command_session_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"status"} or request.get("status") not in {"promoted", "failed"}:
            raise HTTPException(status_code=400, detail="status must be promoted or failed")
        try:
            return repository.finish_proposal(
                str(UUID(command_session_id)), status=str(request["status"])
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
