"""Loopback-only API routes for durable owner Creative review."""

from __future__ import annotations

import base64
from typing import Any, Mapping, Sequence

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.params import Depends as DependsParameter
from fastapi.responses import Response

from .local_experiments import LocalExperimentService


def local_experiment_router(
    service: LocalExperimentService, *,
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
                required_language=str(request["language"]),
                requested_by="loopback:owner",
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
    def correct_brief(brief_id: str, request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
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
    def retry_brief(brief_id: str, request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
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

    @router.get("/projects/{project_id}/assets")
    @router.get("/project-assets")
    def assets(project_id: str) -> dict[str, Any]:
        try:
            return {"items": service.list_assets(project_id)}
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/assets", status_code=201)
    def upload_asset(project_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"title", "mime_type", "bytes_base64"}:
            raise HTTPException(status_code=400, detail="local Project asset fields do not match v1")
        try:
            data = base64.b64decode(str(request["bytes_base64"]), validate=True)
            return service.upload_asset(
                project_id=project_id, title=str(request["title"]),
                mime_type=str(request["mime_type"]), data=data,
                requested_by="loopback:owner",
            )
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/assets/pexels", status_code=201)
    def pexels_asset(project_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"query"}:
            raise HTTPException(status_code=400, detail="Pexels asset request requires one query")
        try:
            return service.source_pexels_asset(
                project_id, query=str(request["query"]), requested_by="loopback:owner",
            )
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/assets/{asset_id}/decision")
    def asset_decision(project_id: str, asset_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"approved"} or not isinstance(request.get("approved"), bool):
            raise HTTPException(status_code=400, detail="asset decision requires approved boolean")
        try:
            value = service.approve_asset(
                asset_id, approved=bool(request["approved"]), requested_by="loopback:owner",
            )
            if value["project_id"] != project_id:
                raise KeyError("asset does not belong to the requested Project")
            return value
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.get("/project-assets/{asset_id}/asset")
    def asset_bytes(asset_id: str) -> Response:
        try:
            value = service.asset_bytes(asset_id)
            return Response(
                content=value["bytes"], media_type=value["mime_type"],
                headers={"Cache-Control": "private, no-store", "ETag": f'"{value["sha256"]}"'},
            )
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/content-runs", status_code=202)
    def create_run(request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
        expected = {"request_id", "brief_id", "platform", "studio_state_sha256"}
        if set(request) != expected:
            raise HTTPException(status_code=400, detail="local Result run fields do not match v1")
        try:
            run, created = service.create_run(
                request_id=str(request["request_id"]), brief_id=str(request["brief_id"]),
                platform=str(request["platform"]),
                studio_state_sha256=str(request["studio_state_sha256"]),
                requested_by="loopback:owner",
            )
            if created:
                background.add_task(service.execute_run, run["run_id"])
            return {**run, "created": created}
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.get("/content-runs")
    def runs(project_id: str, limit: int = Query(default=100, ge=1, le=100)) -> dict[str, Any]:
        try:
            return {"items": service.list_runs(project_id, limit), "next_cursor": None}
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.get("/content-runs/{run_id}")
    def run(run_id: str) -> dict[str, Any]:
        try:
            return service.get_run(run_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/content-runs/{run_id}/terminate")
    def terminate_run(run_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if request:
            raise HTTPException(status_code=400, detail="local Result termination has no input fields")
        try:
            return service.terminate_run(run_id, "loopback:owner")
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.get("/content-runs/{run_id}/review")
    def review(run_id: str) -> dict[str, Any]:
        try:
            return service.get_review(run_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    def image_response(value: Mapping[str, Any]) -> Response:
        return Response(
            content=value["bytes"], media_type=str(value["mime_type"]),
            headers={
                "Cache-Control": "private, no-store", "ETag": f'"{value["sha256"]}"',
                "X-PTW-Content-SHA256": str(value["sha256"]),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/content-runs/{run_id}/creatives/{creative_id}/asset")
    def creative_asset(run_id: str, creative_id: str) -> Response:
        try:
            return image_response(service.creative_asset(run_id, creative_id))
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.get("/content-runs/{run_id}/creatives/{creative_id}/source.png")
    def creative_source(run_id: str, creative_id: str) -> Response:
        try:
            return image_response(service.creative_asset(run_id, creative_id, source_png=True))
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/content-runs/{run_id}/review/approve")
    def approve(run_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"request_id", "creative_id"}:
            raise HTTPException(status_code=400, detail="Approve requires request_id and creative_id")
        try:
            return service.approve(
                run_id, request_id=str(request["request_id"]),
                creative_id=str(request["creative_id"]), requested_by="loopback:owner",
            )
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/content-runs/{run_id}/review/regenerate-all", status_code=202)
    def regenerate_all(run_id: str, request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
        if set(request) != {"request_id"}:
            raise HTTPException(status_code=400, detail="Regenerate all requires one request_id")
        try:
            child, created = service.regenerate_all(
                run_id, request_id=str(request["request_id"]),
                requested_by="loopback:owner",
            )
            if created:
                background.add_task(service.execute_run, child["run_id"])
            return {**child, "created": created}
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/content-runs/{run_id}/review/tune", status_code=202)
    def tune(run_id: str, request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
        if set(request) != {"request_id", "creative_id", "comment"}:
            raise HTTPException(status_code=400, detail="Tune requires request_id, creative_id, and comment")
        try:
            child, created = service.tune(
                run_id, request_id=str(request["request_id"]),
                creative_id=str(request["creative_id"]), comment=str(request["comment"]),
                requested_by="loopback:owner",
            )
            if created:
                background.add_task(service.execute_run, child["run_id"])
            return {**child, "created": created}
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/content-runs/{run_id}/review-notification/retry")
    def retry_notification(run_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if request:
            raise HTTPException(status_code=400, detail="notification retry has no input fields")
        try:
            return service.retry_review_notification(run_id)
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/content-runs/{run_id}/retry", status_code=202)
    def retry_run(run_id: str, request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
        if set(request) != {"request_id"}:
            raise HTTPException(status_code=400, detail="local Result retry requires one request_id")
        try:
            child, created = service.retry_run(
                run_id, request_id=str(request["request_id"]), requested_by="loopback:owner",
            )
            if created:
                background.add_task(service.execute_run, child["run_id"])
            return {**child, "created": created}
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.get("/content-runs/{run_id}/creatives/{creative_id}/export")
    def export(run_id: str, creative_id: str) -> Response:
        try:
            run = service.get_run(run_id)
            if run.get("approved_creative_id") != creative_id:
                raise ValueError("only the approved Creative can be exported")
            value = service.release_download(run_id)
            return Response(
                content=value["bytes"], media_type="application/zip",
                headers={
                    "Cache-Control": "private, no-store", "ETag": f'"{value["sha256"]}"',
                    "X-PTW-Content-SHA256": value["sha256"],
                    "Content-Disposition": f'attachment; filename="ptw-instagram-{value["release_id"]}.zip"',
                },
            )
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.get("/learning-summary")
    def learning_summary(project_id: str | None = None) -> dict[str, Any]:
        try:
            return service.learning_summary(project_id)
        except ValueError as error:
            raise fail(error) from error

    return router
