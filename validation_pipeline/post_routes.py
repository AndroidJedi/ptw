"""Loopback-only routes for the single-post draft workflow."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.params import Depends as DependsParameter
from fastapi.responses import Response

from .post_workflow import SimplePostService


def simple_post_router(
    service: SimplePostService, *, dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/posts", dependencies=list(dependencies))

    def fail(error: Exception) -> HTTPException:
        if isinstance(error, KeyError):
            return HTTPException(status_code=404, detail=str(error).strip("'"))
        if isinstance(error, (RuntimeError, FileExistsError)):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=400, detail=str(error))

    @router.get("")
    def posts(
        project_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            return {"items": service.list_posts(project_id)[:limit], "next_cursor": None}
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("", status_code=202)
    def create_post(
        request: Mapping[str, Any], background: BackgroundTasks,
    ) -> dict[str, Any]:
        if set(request) != {"request_id", "brief_id"}:
            raise HTTPException(status_code=400, detail="simple post request fields do not match v1")
        try:
            post, created = service.create_post(
                request_id=str(request["request_id"]), brief_id=str(request["brief_id"]),
                requested_by="loopback:owner",
            )
            if created or post["status"] == "queued":
                background.add_task(service.generate_post, post["post_id"])
            return {"post": post, "created": created}
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.get("/{post_id}")
    def post(post_id: str) -> dict[str, Any]:
        try:
            return service.get_post(post_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/{post_id}/retry", status_code=202)
    def retry_post(
        post_id: str, request: Mapping[str, Any], background: BackgroundTasks,
    ) -> dict[str, Any]:
        if request:
            raise HTTPException(status_code=400, detail="simple post retry has no input fields")
        try:
            post = service.retry_post(post_id)
            background.add_task(service.generate_post, post["post_id"])
            return post
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/{post_id}/tune", status_code=202)
    def tune_post(
        post_id: str, request: Mapping[str, Any], background: BackgroundTasks,
    ) -> dict[str, Any]:
        if set(request) != {"request_id", "comment"}:
            raise HTTPException(status_code=400, detail="simple post tune fields do not match v1")
        try:
            post, created = service.create_tune(
                post_id, request_id=str(request["request_id"]),
                comment=str(request["comment"]), requested_by="loopback:owner",
            )
            if created:
                background.add_task(service.apply_tune, post["active_tune_id"])
            return {"post": post, "created": created}
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/{post_id}/preview")
    def preview(post_id: str, request: Mapping[str, Any]) -> Response:
        if set(request) != {"state_sha256"}:
            raise HTTPException(status_code=400, detail="simple post preview fields do not match v1")
        try:
            rendered = service.render_preview(post_id, str(request["state_sha256"]))
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error
        return Response(
            content=rendered["bytes"], media_type="image/png",
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{rendered["bytes_sha256"]}"',
                "X-PTW-Content-SHA256": rendered["bytes_sha256"],
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post("/{post_id}/approve")
    def approve_post(post_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"state_sha256"}:
            raise HTTPException(status_code=400, detail="simple post approval fields do not match v1")
        try:
            post, created = service.approve_post(
                post_id, state_sha256=str(request["state_sha256"]),
                approved_by="loopback:owner",
            )
            return {"post": post, "asset_created": created}
        except (KeyError, RuntimeError, ValueError, FileExistsError) as error:
            raise fail(error) from error

    @router.get("/assets/{asset_id}/render")
    def asset_render(asset_id: str) -> Response:
        try:
            rendered = service.asset_render(asset_id)
        except (KeyError, OSError, ValueError) as error:
            raise fail(error) from error
        return Response(
            content=rendered["bytes"], media_type=rendered["mime_type"],
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{rendered["sha256"]}"',
                "X-PTW-Content-SHA256": rendered["sha256"],
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
