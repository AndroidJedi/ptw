from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import ipaddress
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .app_server import AppServerPlanner
from .auth import FirebaseVerifier, OwnerDependency, OwnerIdentity
from .control_store import ControlStore
from .execution import CommandRunner
from .firebase_hosting import FirebaseHostingPublisher
from .landing import prepare_draft_set, prepare_landing_build, templates_response
from .landing_draft_repository import LandingDraftRepository
from .landing_drafts import LandingDraftCoordinator
from .landing_pipeline import LandingBuildCoordinator
from .landing_repository import LandingBuildRepository
from .landing_revision import LandingRevisionProvider
from .leads import ExistingBotLeadNotifier, LandingLeadRepository
from .platform import PlatformRepository
from .settings import Settings


def create_app(
    settings: Settings,
    verifier: FirebaseVerifier | None = None,
    landing_coordinator: LandingBuildCoordinator | None = None,
    draft_coordinator: LandingDraftCoordinator | None = None,
    lead_repository: LandingLeadRepository | None = None,
    lead_notifier: ExistingBotLeadNotifier | None = None,
) -> FastAPI:
    store = ControlStore(settings.control_database_path)
    platform = PlatformRepository(settings.platform_database_url, settings.platform_owner_telegram_id)
    planner = AppServerPlanner(settings.codex_executable, settings.repository_path)
    runner = CommandRunner(settings.codex_executable, settings.repository_path, store, platform)
    build_repository = LandingBuildRepository(settings.commander_database_url)
    draft_repository = LandingDraftRepository(settings.commander_database_url)
    reviser: LandingRevisionProvider | None = None
    if settings.landing_llm_bridge_url and settings.telegram_bot_token:
        reviser = LandingRevisionProvider(
            bridge_url=settings.landing_llm_bridge_url,
            token=settings.telegram_bot_token,
            skill_path=settings.repository_path / "skills/natal-landing-builder/SKILL.md",
            model=settings.landing_llm_model,
        )
    if landing_coordinator is None and settings.firebase_landing_service_account_path is not None:
        lead_origin = urlsplit(settings.landing_lead_api_base_url)
        landing_coordinator = LandingBuildCoordinator(
            repository=build_repository,
            publisher=FirebaseHostingPublisher(
                project_id=settings.firebase_project_id,
                site_id=settings.firebase_landing_site_id,
                credential_path=settings.firebase_landing_service_account_path,
                lead_api_origin=f"{lead_origin.scheme}://{lead_origin.netloc}",
            ),
            output_root=settings.landing_output_root,
            stopped=platform.emergency_stop,
            lead_api_base_url=settings.landing_lead_api_base_url,
        )
    if draft_coordinator is None and reviser is not None:
        draft_coordinator = LandingDraftCoordinator(
            repository=draft_repository,
            build_repository=build_repository,
            reviser=reviser,
            stopped=platform.emergency_stop,
        )
    lead_repository = lead_repository or LandingLeadRepository(
        settings.commander_database_url, settings.landing_lead_hmac_secret
    )
    if lead_notifier is None and settings.telegram_bot_token:
        lead_notifier = ExistingBotLeadNotifier(
            lead_repository,
            bot_token=settings.telegram_bot_token,
            owner_chat_id=settings.owner_chat_id,
            allowed_chat_ids=settings.telegram_allowed_chat_ids,
            emergency_stopped=platform.emergency_stop,
        )
    owner = OwnerDependency(verifier or FirebaseVerifier(settings))
    tasks: set[asyncio.Task[Any]] = set()
    operation_start_lock = asyncio.Lock()
    interrupted_commands = store.recover_interrupted_commands()
    for interrupted in interrupted_commands:
        if interrupted.get("platform_job_id") is not None:
            try:
                platform.complete_job(
                    int(interrupted["platform_job_id"]), success=False,
                    result={"error": "owner gateway restarted during operation"},
                )
            except Exception:
                pass

    def orphan_gateway_guard() -> None:
        with build_repository.connection() as connection:
            connection.execute(
                """UPDATE commander_operation_guard
                   SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton AND operation_kind IN ('landing_agent','codex_plan','codex_execute')"""
            )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await asyncio.to_thread(orphan_gateway_guard)
        if landing_coordinator is not None:
            await asyncio.to_thread(landing_coordinator.recover_interrupted)
        if draft_coordinator is not None:
            await asyncio.to_thread(draft_coordinator.recover_interrupted)
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(
        title="PTW Owner Gateway", version="2.0.0", docs_url=None, redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.public_origin, *settings.landing_public_origins],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
    )

    def background(coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    def require_running() -> None:
        if platform.emergency_stop():
            raise HTTPException(status_code=423, detail="PTW emergency stop is active; resume it from Admin / System")

    def visitor_ip(request: Request) -> str:
        peer = request.client.host if request.client else ""
        try:
            peer_address = ipaddress.ip_address(peer)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="visitor network address is unavailable") from error
        trusted = any(
            peer_address in ipaddress.ip_network(network, strict=False)
            for network in settings.landing_trusted_proxy_networks
        )
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if trusted and forwarded:
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError as error:
                raise HTTPException(status_code=400, detail="forwarded visitor address is invalid") from error
        return str(peer_address)

    async def positioning_bridge(
        method: str, path: str, *, body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None, actor: str = "owner-web",
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method, f"{settings.positioning_service_url}{path}",
                    headers={
                        "X-PTW-Owner-Gateway-Token": settings.positioning_service_token,
                        "X-PTW-Actor": actor,
                    },
                    json=None if body is None else dict(body), params=dict(params or {}),
                )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=503, detail="Marketing Positioning service is unavailable") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(status_code=response.status_code, detail=detail or "Marketing Positioning request failed")
        return response

    def operation_activity() -> dict[str, Any]:
        with build_repository.connection() as connection:
            row = connection.execute(
                "SELECT operation_kind,operation_id,acquired_at FROM commander_operation_guard WHERE singleton"
            ).fetchone()
        return {
            "active": bool(row and row[1]), "operation": None if not row else row[0],
            "operation_id": None if not row or row[1] is None else str(row[1]),
            "acquired_at": None if not row or row[2] is None else row[2].isoformat(),
        }

    def acquire_operation(kind: str, operation_id: str) -> None:
        with build_repository.connection() as connection:
            row = connection.execute(
                "SELECT operation_kind,operation_id FROM commander_operation_guard WHERE singleton FOR UPDATE"
            ).fetchone()
            if row is None or row[1] is not None:
                active = "unknown" if row is None else f"{row[0]} {row[1]}"
                raise ValueError(f"heavy operation {active} is already active")
            connection.execute(
                "UPDATE commander_operation_guard SET operation_kind=%s,operation_id=%s,acquired_at=clock_timestamp() WHERE singleton",
                (kind, UUID(operation_id)),
            )

    def release_operation(operation_id: str) -> None:
        with build_repository.connection() as connection:
            connection.execute(
                """UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL
                   WHERE singleton AND operation_id=%s""",
                (UUID(operation_id),),
            )

    def require_no_active_operation() -> None:
        active = operation_activity()
        if active["active"]:
            raise HTTPException(
                status_code=409,
                detail=f"{active['operation']} {active['operation_id']} is active; wait before starting another heavy operation",
            )

    def require_landing_builder() -> LandingBuildCoordinator:
        if landing_coordinator is None:
            raise HTTPException(status_code=503, detail="Natal Firebase publisher is not configured")
        return landing_coordinator

    def require_landing_drafts() -> LandingDraftCoordinator:
        if draft_coordinator is None:
            raise HTTPException(status_code=503, detail="Natal landing agent is not configured")
        return draft_coordinator

    async def populate_and_release(coordinator: LandingDraftCoordinator, draft_set_id: str) -> None:
        try:
            await coordinator.populate(draft_set_id)
        finally:
            await asyncio.to_thread(release_operation, draft_set_id)

    async def edit_and_release(coordinator: LandingDraftCoordinator, request_id: str) -> None:
        try:
            await coordinator.edit(request_id)
        finally:
            await asyncio.to_thread(release_operation, request_id)

    async def plan_and_release(session_id: str, instruction: str) -> None:
        async def sink(event: dict[str, Any]) -> None:
            store.event(session_id, event)
        try:
            plan = await planner.plan(instruction, sink)
            store.set_plan(session_id, plan)
        except Exception as error:
            store.update(session_id, "failed", error=f"{type(error).__name__}: {str(error)[:1000]}")
            store.event(session_id, {"type": "plan.failed", "error": type(error).__name__})
        finally:
            await asyncio.to_thread(release_operation, session_id)

    async def execute_and_release(session_id: str) -> None:
        try:
            await runner.execute(session_id)
        finally:
            await asyncio.to_thread(release_operation, session_id)

    async def propagate_emergency_stop(active: bool, actor: str) -> list[str]:
        failures: list[str] = []
        targets = (
            ("commander", f"{settings.commander_service_url}/internal/emergency-stop", {"X-PTW-Bridge-Token": settings.telegram_bot_token}),
            ("positioning", f"{settings.positioning_service_url}/internal/emergency-stop", {"X-PTW-Owner-Gateway-Token": settings.positioning_service_token}),
        )
        async with httpx.AsyncClient(timeout=20) as client:
            for name, url, headers in targets:
                try:
                    response = await client.post(url, headers=headers, json={"active": active, "actor": actor})
                    if response.status_code >= 400:
                        failures.append(name)
                except httpx.HTTPError:
                    failures.append(name)
        return failures

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/overview")
    def overview(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        with build_repository.connection() as connection:
            positioning = connection.execute(
                """SELECT count(*)::int,
                          count(*) FILTER (WHERE approved.revision_id IS NOT NULL)::int
                   FROM positioning_projects project
                   LEFT JOIN positioning_approvals approved ON approved.project_id=project.entity_id AND approved.revoked_at IS NULL"""
            ).fetchone()
            landings = connection.execute(
                """SELECT count(*)::int,
                          count(*) FILTER (WHERE status='published')::int FROM landing_builds"""
            ).fetchone()
            leads = int(connection.execute("SELECT count(*) FROM landing_leads").fetchone()[0])
        return {
            "positionings": {"total": positioning[0], "approved": positioning[1]},
            "landings": {"total": landings[0], "published": landings[1]},
            "leads": {"total": leads}, "jobs": platform.summary(),
            "emergency_stop": platform.emergency_stop(),
        }

    # Marketing Positioning owner API.
    @app.get("/api/v1/positionings/catalog")
    async def positioning_catalog(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await positioning_bridge("GET", "/internal/v1/catalog")).json()

    @app.post("/api/v1/positionings", status_code=202)
    async def create_positioning(request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        async with operation_start_lock:
            require_no_active_operation()
            return (await positioning_bridge(
                "POST", "/internal/v1/positionings", body=request, actor=f"firebase:{identity.uid}"
            )).json()

    @app.get("/api/v1/positionings")
    async def list_positionings(limit: int = Query(default=50, ge=1, le=100), _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await positioning_bridge("GET", "/internal/v1/positionings", params={"limit": limit})).json()

    @app.get("/api/v1/positionings/{project_id}")
    async def positioning(project_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await positioning_bridge("GET", f"/internal/v1/positionings/{project_id}")).json()

    @app.post("/api/v1/positionings/{project_id}/revisions", status_code=202)
    async def revise_positioning(project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        async with operation_start_lock:
            require_no_active_operation()
            return (await positioning_bridge(
                "POST", f"/internal/v1/positionings/{project_id}/revisions",
                body=request, actor=f"firebase:{identity.uid}",
            )).json()

    @app.post("/api/v1/positioning-revisions/{revision_id}/retry", status_code=202)
    async def retry_positioning(revision_id: str, identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        async with operation_start_lock:
            require_no_active_operation()
            return (await positioning_bridge(
                "POST", f"/internal/v1/positioning-revisions/{revision_id}/retry",
                actor=f"firebase:{identity.uid}",
            )).json()

    @app.post("/api/v1/positioning-revisions/{revision_id}/approve")
    async def approve_positioning(revision_id: str, identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        return (await positioning_bridge(
            "POST", f"/internal/v1/positioning-revisions/{revision_id}/approve",
            actor=f"firebase:{identity.uid}",
        )).json()

    @app.get("/api/v1/positioning-revisions/{revision_id}/export.md")
    async def export_positioning(revision_id: str, _identity: OwnerIdentity = Depends(owner)) -> Response:
        response = await positioning_bridge("GET", f"/internal/v1/positioning-revisions/{revision_id}/export.md")
        return Response(
            response.content, media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": response.headers.get("Content-Disposition", "attachment")},
        )

    @app.get("/api/v1/positionings/{project_id}/skill-proposals")
    async def positioning_skill_proposals(project_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await positioning_bridge(
            "GET", f"/internal/v1/positionings/{project_id}/skill-proposals"
        )).json()

    @app.post("/api/v1/positioning-skill-proposals/{proposal_id}/update")
    async def update_positioning_skill_proposal(proposal_id: str, request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await positioning_bridge(
            "POST", f"/internal/v1/positioning-skill-proposals/{proposal_id}/update", body=request
        )).json()

    @app.post("/api/v1/positioning-skill-proposals/{proposal_id}/dismiss")
    async def dismiss_positioning_skill_proposal(proposal_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await positioning_bridge(
            "POST", f"/internal/v1/positioning-skill-proposals/{proposal_id}/dismiss"
        )).json()

    @app.post("/api/v1/positioning-skill-proposals/{proposal_id}/plan", status_code=202)
    async def plan_positioning_skill_proposal(proposal_id: str, request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        if set(request) != {"lesson"} or not 1 <= len(str(request["lesson"]).strip()) <= 500:
            raise HTTPException(status_code=400, detail="lesson must contain 1-500 characters")
        lesson = str(request["lesson"]).strip()
        instruction = (
            "Update only skills/marketing-positioning/references/owner-lessons.md. "
            "Add this reviewed generalized owner lesson without changing evidence rules: "
            f"{lesson}\nDo not edit any other file. Run python3 scripts/verify_ptw_skills.py and the skill quick validator."
        )
        async with operation_start_lock:
            require_no_active_operation()
            command = store.create_command("plan", instruction)
            try:
                acquire_operation("codex_plan", command["id"])
                proposal = (await positioning_bridge(
                    "POST", f"/internal/v1/positioning-skill-proposals/{proposal_id}/plan",
                    body={"lesson": lesson, "command_session_id": command["id"]},
                )).json()
            except Exception:
                store.update(command["id"], "failed", error="Skill proposal planning could not start")
                release_operation(command["id"])
                raise
            background(plan_and_release(command["id"], instruction))
            return {"proposal": proposal, "command_session": command}

    # Landing workspace.
    @app.get("/api/v1/landings/templates")
    def landing_templates(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return templates_response()

    @app.post("/api/v1/landings/draft-sets", status_code=202)
    async def create_landing_draft_set(request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        expected = {"request_id", "positioning_project_id", "positioning_revision_id", "privacy_policy_url"}
        if set(request) != expected:
            raise HTTPException(status_code=400, detail="draft-set request fields do not match the v2 contract")
        try:
            request_id = str(UUID(str(request["request_id"])))
            project_id = str(UUID(str(request["positioning_project_id"])))
            revision_id = str(UUID(str(request["positioning_revision_id"])))
        except ValueError as error:
            raise HTTPException(status_code=400, detail="request and positioning IDs must be UUIDs") from error
        project = (await positioning_bridge("GET", f"/internal/v1/positionings/{project_id}")).json()
        revision = next((item for item in project.get("revisions") or [] if item["id"] == revision_id), None)
        if revision is None or project.get("active_approved_revision_id") != revision_id:
            raise HTTPException(status_code=409, detail="Landing requires the active approved positioning revision")
        try:
            prepared = prepare_draft_set(
                project, revision, privacy_policy_url=str(request["privacy_policy_url"])
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        coordinator = require_landing_drafts()
        existing = coordinator.by_request(request_id)
        if existing is not None:
            return existing
        async with operation_start_lock:
            require_no_active_operation()
            try:
                await asyncio.to_thread(coordinator.verify_ready)
                draft_set, created = coordinator.create(
                    prepared, request_id=request_id, requested_by=f"firebase:{identity.uid}"
                )
                if created:
                    acquire_operation("landing_agent", draft_set["id"])
                    background(populate_and_release(coordinator, draft_set["id"]))
                return draft_set
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except RuntimeError as error:
                raise HTTPException(status_code=503, detail=str(error)) from error

    @app.get("/api/v1/landings/draft-sets/latest")
    def latest_landing_draft_set(positioning_revision_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        try:
            value = require_landing_drafts().latest(str(UUID(positioning_revision_id)))
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid positioning revision UUID") from error
        if value is None:
            raise HTTPException(status_code=404, detail="Landing draft set not found")
        return value

    @app.get("/api/v1/landings/draft-sets/{draft_set_id}")
    def landing_draft_set(draft_set_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        try:
            return require_landing_drafts().get(str(UUID(draft_set_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Landing draft set not found") from error

    @app.post("/api/v1/landings/draft-sets/{draft_set_id}/retry", status_code=202)
    async def retry_landing_draft_set(draft_set_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        coordinator = require_landing_drafts()
        try:
            draft_set_id = str(UUID(draft_set_id))
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Landing draft-set UUID") from error
        async with operation_start_lock:
            require_no_active_operation()
            try:
                draft_set = coordinator.retry_population(draft_set_id)
                acquire_operation("landing_agent", draft_set_id)
                background(populate_and_release(coordinator, draft_set_id))
                return draft_set
            except (KeyError, ValueError) as error:
                raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/landings/draft-snapshots/{snapshot_id}/preview")
    def landing_preview(snapshot_id: str, _identity: OwnerIdentity = Depends(owner)) -> JSONResponse:
        try:
            preview = require_landing_drafts().preview(str(UUID(snapshot_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Landing snapshot not found") from error
        return JSONResponse(preview, headers={"Cache-Control": "no-store, private"})

    @app.post("/api/v1/landings/draft-snapshots/{snapshot_id}/edits", status_code=202)
    async def edit_landing_snapshot(snapshot_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        if set(request) != {"request_id", "block_id", "instruction"}:
            raise HTTPException(status_code=400, detail="edit request fields do not match the v2 contract")
        try:
            request_id = str(UUID(str(request["request_id"])))
            snapshot_id = str(UUID(snapshot_id))
        except ValueError as error:
            raise HTTPException(status_code=400, detail="request and snapshot IDs must be UUIDs") from error
        coordinator = require_landing_drafts()
        try:
            existing = coordinator.get_edit(request_id)
            return existing
        except KeyError:
            pass
        async with operation_start_lock:
            require_no_active_operation()
            try:
                edit, created = coordinator.create_edit(
                    snapshot_id, request_id=request_id, block_id=str(request["block_id"]),
                    instruction=str(request["instruction"]), requested_by=f"firebase:{identity.uid}",
                )
                if created:
                    acquire_operation("landing_agent", request_id)
                    background(edit_and_release(coordinator, request_id))
                return edit
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/landings/draft-edits/{request_id}")
    def landing_edit(request_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        try:
            return require_landing_drafts().get_edit(str(UUID(request_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Landing edit not found") from error

    @app.post("/api/v1/landings/draft-edits/{request_id}/retry", status_code=202)
    async def retry_landing_edit(request_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        request_id = str(UUID(request_id))
        coordinator = require_landing_drafts()
        async with operation_start_lock:
            require_no_active_operation()
            try:
                edit = coordinator.retry_edit(request_id)
                acquire_operation("landing_agent", request_id)
                background(edit_and_release(coordinator, request_id))
                return edit
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/v1/landings/draft-snapshots/{snapshot_id}/publish", status_code=202)
    async def publish_landing(snapshot_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        if set(request) != {"request_id"}:
            raise HTTPException(status_code=400, detail="publication requires request_id")
        try:
            request_id = str(UUID(str(request["request_id"])))
            snapshot = draft_repository.snapshot(str(UUID(snapshot_id)))
            draft_set = draft_repository.get(snapshot["draft_set_id"])
            prepared = prepare_landing_build(draft_set, snapshot)
            coordinator = require_landing_builder()
            build, created = coordinator.create(
                prepared, request_id=request_id, requested_by=f"firebase:{identity.uid}"
            )
            if created:
                background(coordinator.run(build["id"]))
            return build
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Landing snapshot not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/landings")
    def landings(limit: int = Query(default=50, ge=1, le=100), positioning_revision_id: str | None = None, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return {"items": build_repository.list(limit, positioning_revision_id=positioning_revision_id), "next_cursor": None}

    @app.get("/api/v1/landings/{build_id}")
    def landing(build_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        try:
            return build_repository.get(str(UUID(build_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Landing not found") from error

    @app.post("/api/v1/landings/{build_id}/retry", status_code=202)
    async def retry_landing(build_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        try:
            coordinator = require_landing_builder()
            build = coordinator.retry(str(UUID(build_id)))
            background(coordinator.run(build["id"]))
            return build
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/v1/landings/{build_id}/feedback")
    def landing_feedback(build_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        if set(request) != {"comment"}:
            raise HTTPException(status_code=400, detail="feedback requires one comment")
        try:
            return build_repository.record_feedback(
                str(UUID(build_id)), comment=str(request["comment"]), requested_by=f"firebase:{identity.uid}"
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/landings/draft-sets/{draft_set_id}/skill-proposals")
    def landing_skill_proposals(draft_set_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        try:
            return {"items": require_landing_drafts().proposals(str(UUID(draft_set_id)))}
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Landing draft set not found") from error

    @app.post("/api/v1/landing-skill-proposals/{proposal_id}/dismiss")
    def dismiss_landing_skill_proposal(proposal_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        try:
            return require_landing_drafts().dismiss_proposal(str(UUID(proposal_id)))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Landing lesson proposal not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/v1/landing-skill-proposals/{proposal_id}/plan", status_code=202)
    async def plan_landing_skill_proposal(proposal_id: str, request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        require_running()
        if set(request) != {"lesson"} or not 1 <= len(str(request["lesson"]).strip()) <= 500:
            raise HTTPException(status_code=400, detail="lesson must contain 1-500 characters")
        lesson = str(request["lesson"]).strip()
        instruction = (
            "Update only skills/natal-landing-builder/references/owner-lessons.md. "
            f"Add this reviewed generalized owner lesson: {lesson}\n"
            "Do not edit any other file. Run python3 scripts/verify_ptw_skills.py and the skill quick validator."
        )
        coordinator = require_landing_drafts()
        async with operation_start_lock:
            require_no_active_operation()
            command = store.create_command("plan", instruction)
            try:
                acquire_operation("codex_plan", command["id"])
                proposal = coordinator.mark_proposal_planning(
                    str(UUID(proposal_id)), lesson=lesson, command_session_id=command["id"]
                )
            except Exception:
                store.update(command["id"], "failed", error="Skill proposal planning could not start")
                release_operation(command["id"])
                raise
            background(plan_and_release(command["id"], instruction))
            return {"proposal": proposal, "command_session": command}

    # Ads is intentionally read-only until generation/publishing is implemented.
    @app.get("/api/v1/ads")
    async def ads(positioning_project_id: str | None = None, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        projects = (await positioning_bridge("GET", "/internal/v1/positionings", params={"limit": 100})).json().get("items") or []
        approved = [item for item in projects if item.get("active_approved_revision_id")]
        selected = None
        if positioning_project_id:
            if not any(item["id"] == positioning_project_id for item in approved):
                raise HTTPException(status_code=404, detail="approved positioning project not found")
            detail = (await positioning_bridge("GET", f"/internal/v1/positionings/{positioning_project_id}")).json()
            selected = next(
                item for item in detail["revisions"]
                if item["id"] == detail["active_approved_revision_id"]
            )
        return {
            "positionings": approved,
            "selected_revision": selected,
            "ad_concepts": [] if selected is None else selected["document"]["ad_concepts"],
            "implemented": False,
            "message": "Generation and publishing are not implemented",
        }

    # Public lead endpoint persists before any notification attempt.
    @app.post("/api/v1/public/landings/{build_id}/leads", status_code=202)
    async def submit_lead(build_id: str, request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
            if not isinstance(payload, Mapping):
                raise ValueError("lead body must be one object")
            remote_ip = visitor_ip(request)
            lead, created = await asyncio.to_thread(
                lead_repository.create, str(UUID(build_id)), payload, remote_ip=remote_ip
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="published Landing not found") from error
        except PermissionError as error:
            raise HTTPException(status_code=429, detail=str(error)) from error
        except (ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if lead is None:
            return {"accepted": True}
        if created:
            try:
                if lead_notifier is None:
                    await asyncio.to_thread(
                        lead_repository.record_attempt, lead["id"], status="failed",
                        chat_id=settings.owner_chat_id, error_code="NotifierUnavailable",
                        error_message="existing PTW bot notifier is unavailable",
                    )
                else:
                    # The committed lead is reloaded inside notify; notification
                    # can fail without changing the visitor response.
                    await asyncio.to_thread(lead_notifier.notify, lead["id"])
            except Exception:
                # Persistence already committed. A notifier or attempt-recording
                # failure must never reject the visitor submission.
                pass
        return {"accepted": True, "lead_id": lead["id"]}

    @app.get("/api/v1/landing-leads")
    def landing_leads(limit: int = Query(default=100, ge=1, le=100), build_id: str | None = None, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return {"items": lead_repository.list(limit, build_id=build_id), "next_cursor": None}

    @app.post("/api/v1/landing-leads/{lead_id}/retry-notification")
    def retry_lead_notification(lead_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        if lead_notifier is None:
            raise HTTPException(status_code=503, detail="existing PTW bot notifier is unavailable")
        try:
            return lead_notifier.notify(str(UUID(lead_id)))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="lead not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    # Admin: Jobs, Docs/System, and break-glass terminal.
    @app.get("/api/v1/jobs")
    def jobs(limit: int = Query(default=30, ge=1, le=100), _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        local = store.commands(limit)
        return {"items": local + platform.state(max(0, limit - len(local))), "next_cursor": None}

    @app.post("/api/v1/jobs")
    @app.post("/api/v1/command-sessions")
    async def create_job(request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        mode = str(request.get("mode", "plan")); instruction = str(request.get("instruction", "")).strip()
        if set(request) != {"mode", "instruction"} or mode not in {"plan", "execute"} or not 1 <= len(instruction) <= 20_000:
            raise HTTPException(status_code=400, detail="mode and 1-20000 character instruction are required")
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
            require_no_active_operation()
            try:
                command = store.approve_once(session_id, str(request.get("plan_digest", "")), destructive_allowed=destructive_allowed)
                acquire_operation("codex_execute", session_id)
            except KeyError as error:
                raise HTTPException(status_code=404, detail="command session not found") from error
            except PermissionError as error:
                raise HTTPException(status_code=412, detail=str(error)) from error
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            background(execute_and_release(session_id))
            return command

    @app.post("/api/v1/jobs/{session_id}/cancel")
    @app.post("/api/v1/command-sessions/{session_id}/cancel")
    async def cancel(session_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, bool]:
        try:
            await runner.cancel(session_id)
            await asyncio.to_thread(release_operation, session_id)
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
            store.consume_ticket(ticket, path); store.command(session_id)
        except (PermissionError, KeyError):
            await websocket.close(code=4401); return
        await websocket.accept(); sequence = 0
        try:
            while True:
                events = store.events(session_id, sequence)
                for event in events:
                    sequence = event["sequence"]; await websocket.send_text(json.dumps(event, ensure_ascii=False))
                if store.command(session_id)["status"] in {"completed", "failed", "cancelled", "awaiting_approval"} and not events:
                    await websocket.close(code=1000); return
                await asyncio.sleep(.5)
        except WebSocketDisconnect:
            return

    @app.websocket("/api/v1/root-sessions")
    async def root_session(websocket: WebSocket, ticket: str = Query(default="")) -> None:
        path = "/api/v1/root-sessions"
        try:
            uid = store.consume_ticket(ticket, path); metadata_id = store.start_root_session(uid)
        except (PermissionError, ValueError):
            await websocket.close(code=4401); return
        await websocket.accept(); reason = "client_closed"
        try:
            reader, writer = await asyncio.open_unix_connection(str(settings.root_broker_socket))
            writer.write(b'{"type":"terminal"}\n'); await writer.drain()
            async def browser_to_broker() -> None:
                while True:
                    message = await websocket.receive_text(); writer.write((message + "\n").encode()); await writer.drain()
            async def broker_to_browser() -> None:
                while raw := await reader.readline(): await websocket.send_text(raw.decode().rstrip("\n"))
            done, pending = await asyncio.wait(
                {asyncio.create_task(browser_to_broker()), asyncio.create_task(broker_to_browser())},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending: task.cancel()
            writer.close(); await writer.wait_closed()
            for task in done:
                if task.exception(): raise task.exception()
        except WebSocketDisconnect:
            reason = "client_disconnected"
        except Exception as error:
            reason = type(error).__name__; await websocket.close(code=1011)
        finally:
            store.end_root_session(metadata_id, reason)

    @app.get("/api/v1/docs")
    def docs(limit: int = Query(default=50, ge=1, le=50), _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        allowed = [
            "README.md", "docs/README.md", "docs/architecture/commander-current-state.md",
            "docs/architecture/ptw-v2-marketing-workspaces.md",
            "docs/operations/owner-control-plane.md", "docs/operations/disaster-recovery.md",
        ]
        items = []
        for relative in allowed[:limit]:
            path = settings.repository_path / relative
            if path.is_file():
                body = path.read_text(); title = next((line[2:] for line in body.splitlines() if line.startswith("# ")), path.name)
                items.append({"path": relative, "title": title, "body": body})
        return {"items": items}

    @app.get("/api/v1/system/health")
    async def system_health(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        revision = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=settings.repository_path,
            text=True, capture_output=True, check=False, timeout=5,
        ).stdout.strip() or "unknown"
        try:
            positioning_ready = (await positioning_bridge("GET", "/readyz")).json()
        except HTTPException as error:
            positioning_ready = {"ready": False, "error": error.detail}
        return {
            "git_revision": revision,
            "services": {
                "gateway": "ok", "positioning": positioning_ready,
                "root_broker": "ok" if settings.root_broker_socket.exists() else "unavailable",
            },
            "heavy_operation": operation_activity(), "emergency_stop": platform.emergency_stop(),
            "reset": {"permitted": True, "target": "ptw_commander.public only"},
        }

    @app.post("/api/v1/system/emergency-stop")
    async def emergency_stop(request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        active = request.get("active") is True; actor = f"firebase:{identity.uid}"
        if active:
            platform.set_emergency_stop(True, actor=actor); failures = await propagate_emergency_stop(True, actor)
        else:
            failures = await propagate_emergency_stop(False, actor)
            if not failures: platform.set_emergency_stop(False, actor=actor)
        if failures:
            raise HTTPException(status_code=503, detail="emergency stop remains active; unavailable services: " + ", ".join(failures))
        return {"emergency_stop": active}

    @app.post("/api/v1/system/reset")
    async def reset(request: Mapping[str, Any], _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        if request.get("confirmation") != "RESET PTW PRODUCTION":
            raise HTTPException(status_code=412, detail="exact reset confirmation is required")
        try:
            reader, writer = await asyncio.open_unix_connection(str(settings.root_broker_socket))
            writer.write(b'{"type":"operation","name":"reset"}\n'); await writer.drain(); final = None
            while raw := await asyncio.wait_for(reader.readline(), timeout=900):
                message = json.loads(raw)
                if message.get("type") in {"operation.completed", "operation.failed", "error"}:
                    final = message; break
            writer.close(); await writer.wait_closed()
        except (OSError, asyncio.TimeoutError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=503, detail="root operation channel unavailable") from error
        if not final or final.get("type") != "operation.completed" or final.get("return_code") != 0:
            raise HTTPException(status_code=500, detail="reset failed; inspect root-only operation logs")
        return {"status": "reset"}

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
