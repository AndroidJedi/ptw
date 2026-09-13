"""Shared publication routes plus TikTok OAuth connection extensions."""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import APIRouter, Header, HTTPException, Query

from .social_publishing.routes import social_media_router, social_publishing_router


def tiktok_router(service: Any, *, prefix: str, dependencies: list[Any] | None = None) -> APIRouter:
    router = social_publishing_router(
        service, prefix=prefix, label="TikTok", dependencies=dependencies or (),
    )

    @router.post("/oauth/start")
    def oauth_start(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        if set(request) - {"return_to"}:
            raise HTTPException(422, "TikTok OAuth fields are invalid")
        try:
            return service.oauth_start(x_ptw_actor[:200], str(request.get("return_to") or "/"))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error

    @router.get("/oauth/callback")
    def oauth_callback(
        code: str = Query(min_length=1, max_length=1024),
        state: str = Query(min_length=43, max_length=43),
    ) -> dict[str, Any]:
        try:
            return service.oauth_callback(code, state)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error

    @router.post("/disconnect")
    def disconnect(request: Mapping[str, Any]) -> dict[str, Any]:
        if request:
            raise HTTPException(422, "TikTok disconnect body must be empty")
        return service.disconnect()

    return router


def tiktok_media_router(service: Any, *, prefix: str, dependencies: list[Any] | None = None) -> APIRouter:
    return social_media_router(
        service, prefix=prefix, dependencies=dependencies or (),
    )
