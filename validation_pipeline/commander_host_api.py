"""Private API for the hosted Commander development checkout."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Response

from .commander_chat import CommanderChatService, commander_chat_router


def create_app_from_env() -> FastAPI:
    token = os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("OWNER_GATEWAY_BRIDGE_TOKEN is required")
    service = CommanderChatService(
        Path(os.environ.get("PTW_COMMANDER_REPOSITORY", "/workspace")),
        Path(os.environ.get("PTW_COMMANDER_STATE", "/var/lib/ptw/commander-chat")),
        codex_binary=os.environ.get("CODEX_EXECUTABLE", "/opt/ptw-codex/bin/codex"),
        timeout_seconds=float(os.environ.get("PTW_COMMANDER_TIMEOUT_SECONDS", "2400")),
        target="hosted",
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        service.close()

    app = FastAPI(
        title="PTW Hosted Commander", version="1.0.0", docs_url=None,
        redoc_url=None, lifespan=lifespan,
    )

    def authorize(
        response: Response,
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> None:
        response.headers["Cache-Control"] = "no-store"
        if x_ptw_owner_gateway_token != token:
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(commander_chat_router(
        service,
        prefix="/internal/v1/settings/commander",
        dependencies=[Depends(authorize)],
        local_only=False,
    ))
    return app

