"""Loopback-only API for the complete local Owner app."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException

from .images import PexelsClient
from .local_codex import LocalCodexStructuredProvider
from .local_experiment_routes import local_experiment_router
from .local_experiment_store import LocalExperimentStore
from .local_experiments import LocalExperimentService
from .studio_routes import studio_router
from .studio_tune import StudioTuneService, studio_tune_router
from .studio_workspace import UniversalStudioWorkspace


LOCAL_OWNER_TOKEN = "e2e-owner-token"
LOCAL_APP_CHECK_TOKEN = "e2e-app-check"


def create_app(
    *, tune_service: StudioTuneService | None = None,
    experiment_service: LocalExperimentService | None = None,
) -> FastAPI:
    workspace_path = Path(os.environ.get(
        "STUDIO_WORKSPACE_PATH", ".local/studio-workspace",
    ))
    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    workspace = UniversalStudioWorkspace(
        workspace_path,
        pexels=PexelsClient(pexels_key) if pexels_key else None,
    )
    pexels = PexelsClient(pexels_key) if pexels_key else None
    experiment_service = experiment_service or LocalExperimentService(
        store=LocalExperimentStore(Path(os.environ.get(
            "LOCAL_EXPERIMENT_PATH", ".local/owner-experiments",
        ))),
        workspace=workspace,
        provider=LocalCodexStructuredProvider(
            os.environ.get("LOCAL_CODEX_BIN", "").strip() or "codex",
            model=os.environ.get("LOCAL_CODEX_MODEL", "").strip() or None,
            reasoning_effort=os.environ.get(
                "LOCAL_CODEX_REASONING_EFFORT", "xhigh",
            ).strip().casefold(),
            timeout_seconds=int(os.environ.get("LOCAL_CODEX_TIMEOUT_SECONDS", "420")),
        ),
        repository_root=Path(__file__).resolve().parents[1],
        pexels=pexels,
    )
    recovery_tasks: set[asyncio.Task[Any]] = set()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        recovered = experiment_service.recover_interrupted()
        for brief_id in recovered["brief_ids"]:
            task = asyncio.create_task(asyncio.to_thread(experiment_service.generate_brief, brief_id))
            recovery_tasks.add(task)
            task.add_done_callback(recovery_tasks.discard)
        for run_id in recovered["run_ids"]:
            task = asyncio.create_task(asyncio.to_thread(experiment_service.execute_run, run_id))
            recovery_tasks.add(task)
            task.add_done_callback(recovery_tasks.discard)
        yield
        for task in recovery_tasks:
            task.cancel()

    app = FastAPI(
        title="PTW Local Owner App", version="1.0.0",
        docs_url=None, redoc_url=None,
        lifespan=lifespan,
    )

    def authorize(
        authorization: str = Header(default=""),
        x_firebase_appcheck: str = Header(default=""),
    ) -> None:
        if (
            authorization != f"Bearer {LOCAL_OWNER_TOKEN}"
            or x_firebase_appcheck != LOCAL_APP_CHECK_TOKEN
        ):
            raise HTTPException(status_code=401, detail="local owner authentication required")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok", "scope": "loopback-local-owner-app"}

    app.include_router(studio_router(
        workspace, prefix="/api/v1/studio", dependencies=[Depends(authorize)],
    ))
    app.include_router(local_experiment_router(
        experiment_service, dependencies=[Depends(authorize)],
    ))
    tune_enabled = os.environ.get("STUDIO_TUNE_MODE", "").strip() == "1"
    if tune_service is not None or tune_enabled:
        service = tune_service or StudioTuneService(
            Path(os.environ.get(
                "STUDIO_TUNE_REPOSITORY_ROOT", Path(__file__).resolve().parents[1],
            )),
            Path(os.environ.get(
                "STUDIO_TUNE_STATE_PATH", ".local/studio-tune",
            )),
            codex_binary=os.environ.get("STUDIO_TUNE_CODEX_BIN", "").strip() or None,
            studio_context_provider=workspace.agent_context,
        )
        app.include_router(studio_tune_router(
            service, prefix="/api/v1/studio", dependencies=[Depends(authorize)],
        ))
    return app
