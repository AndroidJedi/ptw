"""Authenticated routes for PAUSED-only, Project-scoped Meta Ads staging."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.params import Depends as DependsParameter


def meta_ads_router(
    service: Any, *, prefix: str,
    dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    def fail(error: Exception) -> HTTPException:
        if isinstance(error, KeyError):
            return HTTPException(status_code=404, detail=str(error).strip("'"))
        if isinstance(error, RuntimeError):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=400, detail=str(error))

    def no_fields(request: Mapping[str, Any], message: str) -> None:
        if request:
            raise HTTPException(status_code=400, detail=message)

    @router.get("/connection")
    def connection() -> dict[str, Any]:
        return service.connection()

    @router.get("/presets")
    def presets() -> dict[str, Any]:
        return service.presets()

    @router.get("/locations")
    def locations(
        query: str = Query(min_length=2, max_length=80),
        country_code: str = Query(min_length=2, max_length=2),
    ) -> dict[str, Any]:
        try:
            return service.locations(query, country_code)
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/presets", status_code=201)
    def create_preset(request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return service.create_preset(request)
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.get("/projects/{project_id}")
    def workspace(project_id: str) -> dict[str, Any]:
        try:
            return service.workspace(project_id)
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/deployments", status_code=202)
    def deploy(
        project_id: str, request: Mapping[str, Any], background: BackgroundTasks,
    ) -> dict[str, Any]:
        try:
            deployment, created = service.reserve(project_id, request)
            if created:
                background.add_task(service.execute, deployment["deployment_id"])
            return {"deployment": deployment, "created": created}
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/deployments/{deployment_id}/retry", status_code=202)
    def retry(
        project_id: str, deployment_id: str, request: Mapping[str, Any],
        background: BackgroundTasks,
    ) -> dict[str, Any]:
        no_fields(request, "Meta Ads retry has no input fields")
        try:
            deployment = service.retry(project_id, deployment_id)
            background.add_task(service.execute, deployment_id)
            return {"deployment": deployment}
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/deployments/{deployment_id}/sync")
    def sync(
        project_id: str, deployment_id: str, request: Mapping[str, Any],
    ) -> dict[str, Any]:
        no_fields(request, "Meta Ads sync has no input fields")
        try:
            return {"deployment": service.sync(project_id, deployment_id)}
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    return router
