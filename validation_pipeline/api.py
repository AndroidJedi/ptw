"""Internal API for the clean-slate Product Brief → Result system."""

from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
from typing import Any, Mapping
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import Response

from .config import Settings
from .content import ContentContextAssembler, CorpusStore, TemplateRegistry
from .content_repository import ContentResultRepository
from .content_service import CandidateGenerationOrchestrator
from .images import PexelsClient
from .provider import StructuredBridge
from .review_notifications import CommanderReviewNotifier
from .repository import ValidationRepository
from .service import ValidationRunner, validate_create_input, validate_revision_input
from .studio import StudioRenderer
from .studio_routes import studio_router
from .studio_workspace import UniversalStudioWorkspace


def create_app(
    settings: Settings | None = None,
    *,
    repository: ValidationRepository | None = None,
    runner: ValidationRunner | None = None,
    recipe_renderer: StudioRenderer | None = None,
    content_repository: ContentResultRepository | None = None,
    content_runner: CandidateGenerationOrchestrator | None = None,
    studio_workspace: UniversalStudioWorkspace | None = None,
) -> FastAPI:
    settings = settings or Settings.from_environment()
    repository = repository or ValidationRepository(settings.database_url)
    bridge = StructuredBridge(settings.bridge_url, settings.bridge_token, settings.model)
    pexels = PexelsClient(settings.pexels_api_key)
    recipe_renderer = recipe_renderer or StudioRenderer()
    studio_workspace = studio_workspace or UniversalStudioWorkspace(
        settings.studio_workspace_path, renderer=recipe_renderer, pexels=pexels,
    )
    content_repository = content_repository or ContentResultRepository(repository)

    runner_error: Exception | None = None
    if runner is None:
        try:
            runner = ValidationRunner(
                repository, bridge, product_brief_skill_path=settings.product_brief_skill_path
            )
        except Exception as error:
            runner_error = error

    content_error: Exception | None = None
    if content_runner is None:
        reference_root = settings.content_candidate_generator_skill_path.parent / "references"
        templates = TemplateRegistry(reference_root / "templates")
        # Git-owned strategy and Studio definitions are a production contract, not an optional provider.
        # Refuse startup on missing, extra, or digest-mismatched active definitions.
        templates.load_active()
        try:
            assembler = ContentContextAssembler(
                generator_skill_path=settings.content_candidate_generator_skill_path,
                template_registry=templates,
                corpus_store=CorpusStore(
                    reference_root / "corpus/manifest.json",
                    reference_root / "corpus/examples.jsonl",
                ),
            )
            content_runner = CandidateGenerationOrchestrator(
                repository=content_repository,
                bridge=bridge,
                context_assembler=assembler,
                template_registry=templates,
                recipe_renderer=recipe_renderer,
                pexels=pexels,
                notifier=CommanderReviewNotifier(
                    settings.commander_review_notification_url,
                    settings.owner_gateway_token,
                ),
            )
        except Exception as error:
            content_error = error

    tasks: set[asyncio.Task[Any]] = set()
    stopped = False

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await asyncio.to_thread(repository.recover_interrupted)
        if content_runner is not None:
            task = asyncio.create_task(asyncio.to_thread(content_runner.resume_incomplete))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(
        title="PTW Result API", version="1.0.0", docs_url=None, redoc_url=None,
        lifespan=lifespan,
    )

    def authorize(x_ptw_owner_gateway_token: str = Header(default="")) -> None:
        if not settings.owner_gateway_token or x_ptw_owner_gateway_token != settings.owner_gateway_token:
            raise HTTPException(status_code=401, detail="owner gateway authentication required")

    app.include_router(studio_router(
        studio_workspace, prefix="/internal/v1/studio", dependencies=[Depends(authorize)],
    ))

    def require_brief_runner() -> ValidationRunner:
        if runner is None:
            raise HTTPException(status_code=503, detail=str(runner_error or "Product Brief runner unavailable"))
        if stopped:
            raise HTTPException(status_code=423, detail="PTW emergency stop is active")
        return runner

    def require_result_runner() -> CandidateGenerationOrchestrator:
        if content_runner is None:
            raise HTTPException(status_code=503, detail=str(content_error or "Result runner unavailable"))
        if stopped:
            raise HTTPException(status_code=423, detail="PTW emergency stop is active")
        return content_runner

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
        require_result_runner()
        try:
            with repository.connection() as connection:
                connection.execute("SELECT 1").fetchone()
            return active.verify_ready()
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=f"Result dependency unavailable: {type(error).__name__}",
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

    @app.post("/internal/v1/briefs/{brief_id}/approve", dependencies=[Depends(authorize)])
    def approve_brief(
        brief_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"honor_confirmed"} or request.get("honor_confirmed") is not True:
            raise HTTPException(
                status_code=400,
                detail="Brief approval requires explicit confirmation that the promise and offer can be honored",
            )
        try:
            value, created = repository.approve_brief(str(UUID(brief_id)), x_ptw_actor[:200])
            return {"brief": value, "approved_now": created}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/project-assets", dependencies=[Depends(authorize)])
    def project_assets(project_id: str) -> dict[str, Any]:
        try:
            return {"items": repository.list_project_assets(str(UUID(project_id)))}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Project ID") from error

    @app.post("/internal/v1/project-assets", dependencies=[Depends(authorize)], status_code=201)
    def upload_project_asset(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        expected = {"project_id", "title", "mime_type", "bytes_base64"}
        if set(request) != expected:
            raise HTTPException(status_code=400, detail="Project asset fields do not match v1")
        try:
            data = base64.b64decode(str(request["bytes_base64"]), validate=True)
            return repository.create_project_asset(
                str(UUID(str(request["project_id"]))), title=str(request["title"]), data=data,
                mime_type=str(request["mime_type"]), origin="owner_upload", provider="owner",
                external_id=None, source_uri=None, license_name="Owner supplied",
                attribution="Owner supplied", metadata={"no_synthetic_people": True},
                requested_by=x_ptw_actor[:200], approval_status="approved",
            )
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/internal/v1/project-assets/{asset_id}/asset", dependencies=[Depends(authorize)])
    def project_asset(asset_id: str) -> Response:
        try:
            value = repository.project_asset_bytes(str(UUID(asset_id)))
            return Response(
                content=value["bytes"], media_type=value["mime_type"],
                headers={"Cache-Control": "private, no-store", "ETag": f'"{value["sha256"]}"'},
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Project asset not found") from error

    @app.get("/internal/v1/project-brand-kits", dependencies=[Depends(authorize)])
    def project_brand_kits(project_id: str) -> dict[str, Any]:
        try:
            return {"items": repository.list_project_brand_kits(str(UUID(project_id)))}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Project ID") from error

    @app.post("/internal/v1/project-brand-kits", dependencies=[Depends(authorize)], status_code=201)
    def create_project_brand_kit(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"project_id", "parent_brand_kit_id", "document"}:
            raise HTTPException(status_code=400, detail="Project brand kit fields do not match v1")
        try:
            return repository.create_project_brand_kit(
                str(UUID(str(request["project_id"]))), document=dict(request["document"]),
                parent_brand_kit_id=None if request["parent_brand_kit_id"] is None else str(UUID(str(request["parent_brand_kit_id"]))),
                requested_by=x_ptw_actor[:200],
            )
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/internal/v1/content-runs", dependencies=[Depends(authorize)], status_code=202)
    async def create_content_run(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        active = require_result_runner()
        if set(request) != {"request_id", "brief_id", "task", "output_profile"}:
            raise HTTPException(status_code=400, detail="Result run fields do not match v1")
        try:
            run, created = active.create_run(
                request_id=str(UUID(str(request["request_id"]))),
                brief_id=str(UUID(str(request["brief_id"]))), task=str(request["task"]),
                output_profile=str(request["output_profile"]), requested_by=x_ptw_actor[:200],
            )
            if created:
                run_background(active.execute, run["run_id"])
            return {**run, "created": created}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="approved Brief or Project context not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/content-runs", dependencies=[Depends(authorize)])
    def content_runs(project_id: str, limit: int = Query(default=50, ge=1, le=100)) -> dict[str, Any]:
        try:
            return {
                "items": content_repository.list_runs(project_id=str(UUID(project_id)), limit=limit),
                "next_cursor": None,
            }
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Project ID") from error

    @app.get("/internal/v1/content-runs/{run_id}", dependencies=[Depends(authorize)])
    def content_run(run_id: str) -> dict[str, Any]:
        try:
            return content_repository.get_run(str(UUID(run_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Result run not found") from error

    @app.get("/internal/v1/content-runs/{run_id}/review", dependencies=[Depends(authorize)])
    def content_review(run_id: str) -> dict[str, Any]:
        try:
            return content_repository.get_review(str(UUID(run_id)))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="review set not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get(
        "/internal/v1/content-runs/{run_id}/creatives/{creative_id}/asset",
        dependencies=[Depends(authorize)],
    )
    def content_creative_asset(run_id: str, creative_id: str) -> Response:
        try:
            value = content_repository.creative_preview(
                str(UUID(creative_id)), expected_run_id=str(UUID(run_id)),
            )
            return Response(
                content=value["bytes"], media_type=value["mime_type"],
                headers={
                    "Cache-Control": "private, no-store",
                    "ETag": f'"{value["sha256"]}"',
                    "X-PTW-Content-SHA256": value["sha256"],
                },
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Creative asset not found") from error

    @app.get(
        "/internal/v1/content-runs/{run_id}/creatives/{creative_id}/export",
        dependencies=[Depends(authorize)],
    )
    def content_creative_export(run_id: str, creative_id: str) -> Response:
        try:
            value = content_repository.creative_export(
                str(UUID(run_id)), str(UUID(creative_id)),
            )
            return Response(
                content=value["bytes"], media_type="application/zip",
                headers={
                    "Cache-Control": "private, no-store",
                    "X-PTW-Content-SHA256": value["sha256"],
                    "Content-Disposition": f'attachment; filename="ptw-{creative_id}.zip"',
                },
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Creative export not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/internal/v1/content-runs/{run_id}/review/approve",
        dependencies=[Depends(authorize)],
    )
    def approve_content_review(
        run_id: str, request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        if set(request) != {"request_id", "creative_id"}:
            raise HTTPException(status_code=400, detail="Approve requires request_id and creative_id")
        try:
            return require_result_runner().approve(
                run_id=str(UUID(run_id)), request_id=str(UUID(str(request["request_id"]))),
                creative_id=str(UUID(str(request["creative_id"]))),
                requested_by=x_ptw_actor[:200],
            )
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/internal/v1/content-runs/{run_id}/review/regenerate-all",
        dependencies=[Depends(authorize)], status_code=202,
    )
    async def regenerate_content_review(
        run_id: str, request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        if set(request) != {"request_id"}:
            raise HTTPException(status_code=400, detail="Regenerate all requires one request_id")
        try:
            active = require_result_runner()
            child, created = active.regenerate_all(
                run_id=str(UUID(run_id)), request_id=str(UUID(str(request["request_id"]))),
                requested_by=x_ptw_actor[:200],
            )
            if created:
                run_background(active.execute, child["run_id"])
            return {**child, "created": created}
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/internal/v1/content-runs/{run_id}/review/tune",
        dependencies=[Depends(authorize)], status_code=202,
    )
    async def tune_content_review(
        run_id: str, request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        if set(request) != {"request_id", "creative_id", "comment"}:
            raise HTTPException(status_code=400, detail="Tune requires request_id, creative_id, and comment")
        try:
            active = require_result_runner()
            child, created = active.tune(
                run_id=str(UUID(run_id)), request_id=str(UUID(str(request["request_id"]))),
                creative_id=str(UUID(str(request["creative_id"]))),
                comment=str(request["comment"]), requested_by=x_ptw_actor[:200],
            )
            if created:
                run_background(active.execute, child["run_id"])
            return {**child, "created": created}
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/internal/v1/content-runs/{run_id}/review-notification/retry",
        dependencies=[Depends(authorize)],
    )
    def retry_content_review_notification(run_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if request:
            raise HTTPException(status_code=400, detail="notification retry has no input fields")
        try:
            return require_result_runner().retry_notification(str(UUID(run_id)))
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/internal/v1/content-runs/{run_id}/retry",
        dependencies=[Depends(authorize)], status_code=202,
    )
    async def retry_content_run(
        run_id: str, request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        if set(request) != {"request_id"}:
            raise HTTPException(status_code=400, detail="Result retry requires one request_id")
        try:
            active = require_result_runner()
            parent = content_repository.get_run(str(UUID(run_id)))
            if parent["status"] != "failed":
                raise ValueError("Result retry is available only for failed generation")
            child, created = active.create_run(
                request_id=str(UUID(str(request["request_id"]))),
                brief_id=parent["brief_id"], task=parent["task"],
                output_profile=parent["output_profile"], requested_by=x_ptw_actor[:200],
            )
            if created:
                run_background(active.execute, child["run_id"])
            return {**child, "created": created}
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
