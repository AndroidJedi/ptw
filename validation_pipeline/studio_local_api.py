"""Loopback-only API for Product Briefs and Project-scoped Studio creatives."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import shutil
from typing import Any, Mapping

from fastapi import Depends, FastAPI, Header, HTTPException

from .images import PexelsClient
from .local_brief_routes import local_brief_router
from .local_brief_store import LocalBriefStore
from .local_briefs import LocalBriefService
from .local_codex import LocalCodexStructuredProvider
from .openai_images import (
    LocalCodexPhoneScreenImageProvider, OpenAIPhoneScreenImageProvider,
)
from .studio_creatives import LocalStudioAuthority, StudioCreativeService
from .studio_routes import studio_creative_router
from .studio_tune import StudioTuneService, studio_tune_router
from .studio_workspace import UniversalStudioWorkspace


LOCAL_OWNER_TOKEN = "e2e-owner-token"
LOCAL_APP_CHECK_TOKEN = "e2e-app-check"


def create_app(
    *, tune_service: StudioTuneService | None = None,
    brief_service: LocalBriefService | None = None,
    phone_screen_image_provider: Any | None = None,
) -> FastAPI:
    tune_enabled = os.environ.get("STUDIO_TUNE_MODE", "").strip() == "1"
    workspace_path = Path(os.environ.get(
        "STUDIO_WORKSPACE_PATH", ".local/studio-workspace",
    ))
    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    pexels = PexelsClient(pexels_key) if pexels_key else None
    codex_binary = os.environ.get("LOCAL_CODEX_BIN", "").strip() or "codex"
    openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    phone_screen_images = phone_screen_image_provider
    if phone_screen_images is None:
        image_provider_mode = os.environ.get(
            "STUDIO_PHONE_IMAGE_PROVIDER", "codex",
        ).strip().casefold()
        if image_provider_mode == "codex":
            resolved_codex = shutil.which(codex_binary)
            if resolved_codex:
                try:
                    phone_screen_images = LocalCodexPhoneScreenImageProvider(
                        resolved_codex,
                        timeout_seconds=int(os.environ.get(
                            "STUDIO_PHONE_IMAGE_TIMEOUT_SECONDS", "300",
                        )),
                    )
                except RuntimeError:
                    phone_screen_images = None
        elif image_provider_mode == "openai_api":
            if openai_api_key:
                phone_screen_images = OpenAIPhoneScreenImageProvider(openai_api_key)
        elif image_provider_mode != "disabled":
            raise RuntimeError(
                "STUDIO_PHONE_IMAGE_PROVIDER must be codex, openai_api, or disabled"
            )
    local_store = brief_service.store if brief_service is not None else LocalBriefStore(Path(os.environ.get(
        "LOCAL_BRIEF_PATH", ".local/owner-briefs",
    )))
    authority = LocalStudioAuthority(local_store)
    structured_provider = brief_service.provider if brief_service is not None else LocalCodexStructuredProvider(
            codex_binary,
            model=os.environ.get("LOCAL_CODEX_MODEL", "").strip() or None,
            reasoning_effort=os.environ.get(
                "LOCAL_CODEX_REASONING_EFFORT", "xhigh",
            ).strip().casefold(),
            timeout_seconds=int(os.environ.get("LOCAL_CODEX_TIMEOUT_SECONDS", "420")),
        )
    repository_root = Path(__file__).resolve().parents[1]
    brief_service = brief_service or LocalBriefService(
        store=local_store, provider=structured_provider,
        repository_root=repository_root, on_project_created=authority.ensure_project_skill,
    )
    studio_creatives = StudioCreativeService(
        root=workspace_path, authority=authority,
        workspace_factory=lambda path: UniversalStudioWorkspace(
            path, pexels=pexels, image_provider=phone_screen_images,
        ),
        structured_provider=structured_provider,
        composer_skill_path=repository_root / "skills/studio-creative-composer/SKILL.md",
        learner_skill_path=repository_root / "skills/studio-edit-learner/SKILL.md",
        phone_skill_path=repository_root / "skills/studio-phone-hero-generator/SKILL.md",
    )
    recovery_tasks: set[asyncio.Task[Any]] = set()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        for brief_id in brief_service.recover_interrupted():
            task = asyncio.create_task(asyncio.to_thread(brief_service.generate_brief, brief_id))
            recovery_tasks.add(task)
            task.add_done_callback(recovery_tasks.discard)
        for creative_id in studio_creatives.recover_interrupted():
            task = asyncio.create_task(asyncio.to_thread(studio_creatives.generate, creative_id))
            recovery_tasks.add(task)
            task.add_done_callback(recovery_tasks.discard)
        for item in studio_creatives.recover_learning():
            task = asyncio.create_task(asyncio.to_thread(
                studio_creatives.retry_learning, item["project_id"],
                item["creative_id"], item["checkpoint_id"],
            ))
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

    app.include_router(studio_creative_router(
        studio_creatives, prefix="/api/v1/studio", dependencies=[Depends(authorize)],
    ))
    app.include_router(local_brief_router(
        brief_service, studio_creatives=studio_creatives, dependencies=[Depends(authorize)],
    ))
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
