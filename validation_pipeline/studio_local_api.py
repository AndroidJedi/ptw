"""Loopback-only API for the complete local Owner app."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException

from .images import PexelsClient
from .local_owner_demo import LocalOwnerDemo, local_owner_demo_router
from .studio_routes import studio_router
from .studio_tune import StudioTuneService, studio_tune_router
from .studio_workspace import UniversalStudioWorkspace


LOCAL_OWNER_TOKEN = "e2e-owner-token"
LOCAL_APP_CHECK_TOKEN = "e2e-app-check"


def create_app(*, tune_service: StudioTuneService | None = None) -> FastAPI:
    workspace_path = Path(os.environ.get(
        "STUDIO_WORKSPACE_PATH", ".local/studio-workspace",
    ))
    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    workspace = UniversalStudioWorkspace(
        workspace_path,
        pexels=PexelsClient(pexels_key) if pexels_key else None,
    )
    app = FastAPI(
        title="PTW Local Owner App", version="1.0.0",
        docs_url=None, redoc_url=None,
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
    app.include_router(local_owner_demo_router(
        LocalOwnerDemo(), dependencies=[Depends(authorize)],
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
        )
        app.include_router(studio_tune_router(
            service, prefix="/api/v1/studio", dependencies=[Depends(authorize)],
        ))
    return app
