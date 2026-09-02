"""Loopback-only Product Brief API routes."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.params import Depends as DependsParameter

from .local_briefs import LocalBriefService


def local_brief_router(
    service: LocalBriefService, *,
    dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=list(dependencies))

    def fail(error: Exception) -> HTTPException:
        if isinstance(error, KeyError):
            return HTTPException(status_code=404, detail=str(error).strip("'"))
        if isinstance(error, (RuntimeError, FileExistsError)):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=400, detail=str(error))

    @router.get("/projects")
    def projects(limit: int = Query(default=100, ge=1, le=100)) -> dict[str, Any]:
        return {"items": service.list_projects(limit), "next_cursor": None}

    @router.post("/projects/{project_id}/rename")
    def rename_project(project_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"name"}:
            raise HTTPException(status_code=400, detail="Project rename requires one name")
        try:
            return service.rename_project(project_id, str(request["name"]))
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/briefs", status_code=202)
    def create_brief(request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
        if set(request) != {"request_id", "raw_idea", "language"}:
            raise HTTPException(status_code=400, detail="Product Brief request fields do not match v1")
        try:
            project, brief, created = service.create_brief(
                request_id=str(request["request_id"]), raw_idea=str(request["raw_idea"]),
                required_language=str(request["language"]), requested_by="loopback:owner",
            )
            if created:
                background.add_task(service.generate_brief, brief["brief_id"])
            return {"project": project, "brief": brief, "created": created}
        except (RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.get("/briefs")
    def briefs(
        project_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            return {"items": service.list_briefs(project_id, limit), "next_cursor": None}
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.get("/briefs/{brief_id}")
    def brief(brief_id: str) -> dict[str, Any]:
        try:
            return service.get_brief(brief_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/briefs/{brief_id}/correct", status_code=202)
    def correct_brief(
        brief_id: str, request: Mapping[str, Any], background: BackgroundTasks,
    ) -> dict[str, Any]:
        if set(request) != {"request_id", "instruction"}:
            raise HTTPException(status_code=400, detail="Product Brief correction fields do not match v1")
        try:
            replacement, created = service.correct_brief(
                brief_id, request_id=str(request["request_id"]),
                instruction=str(request["instruction"]), requested_by="loopback:owner",
            )
            if created:
                background.add_task(service.generate_brief, replacement["brief_id"])
            return {"brief": replacement, "created": created}
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/briefs/{brief_id}/retry", status_code=202)
    def retry_brief(
        brief_id: str, request: Mapping[str, Any], background: BackgroundTasks,
    ) -> dict[str, Any]:
        if request:
            raise HTTPException(status_code=400, detail="Product Brief retry has no input fields")
        try:
            value = service.retry_brief(brief_id)
            background.add_task(service.generate_brief, brief_id)
            return value
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/briefs/{brief_id}/approve")
    def approve_brief(brief_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"honor_confirmed"} or request.get("honor_confirmed") is not True:
            raise HTTPException(status_code=400, detail="Brief approval requires explicit honor confirmation")
        try:
            value, created = service.approve_brief(brief_id, "loopback:owner")
            return {"brief": value, "approved_now": created}
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    return router
