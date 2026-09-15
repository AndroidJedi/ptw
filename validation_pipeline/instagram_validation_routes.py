"""Owner routes for manual Instagram posts and Ads Manager launch kits."""

from __future__ import annotations

from typing import Any, Mapping, Sequence
import hashlib

from fastapi import APIRouter, Header, HTTPException
from fastapi.params import Depends as DependsParameter
from fastapi.responses import Response


def instagram_validation_router(
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

    @router.get("/projects/{project_id}")
    def workspace(project_id: str) -> dict[str, Any]:
        try:
            return service.workspace(project_id)
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.get("/projects/{project_id}/manual-packages")
    def packages(project_id: str) -> dict[str, Any]:
        try:
            return service.packages(project_id)
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/manual-packages", status_code=201)
    def create_package(project_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        try:
            return service.create_package(project_id, request, x_ptw_actor[:200])
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/manual-packages/{package_id}/{action}")
    def package_action(project_id: str, package_id: str, action: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        try:
            return service.package_action(project_id, package_id, action, request, x_ptw_actor[:200])
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/tests", status_code=201)
    def create_test(project_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        try:
            return service.create_test(project_id, request, x_ptw_actor[:200])
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/tests/{test_id}/imports/preview")
    def preview(project_id: str, test_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"csv_text"}:
            raise HTTPException(status_code=400, detail="CSV preview requires csv_text")
        try:
            return service.preview_csv(project_id, test_id, request["csv_text"])
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/tests/{test_id}/imports", status_code=201)
    def import_csv(project_id: str, test_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        try:
            return service.import_csv(project_id, test_id, request, x_ptw_actor[:200])
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    # Keep the static imports route ahead of the dynamic lifecycle action.
    @router.post("/projects/{project_id}/tests/{test_id}/{action}")
    def transition(project_id: str, test_id: str, action: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        try:
            return service.transition(project_id, test_id, action, request, x_ptw_actor[:200])
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error

    @router.get("/projects/{project_id}/tests/{test_id}/launch-kit")
    def launch_kit(project_id: str, test_id: str) -> Response:
        try:
            content = service.launch_kit(project_id, test_id)
        except (KeyError, RuntimeError, ValueError) as error:
            raise fail(error) from error
        return Response(content=content, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="instagram-test-{test_id}.zip"',
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "X-PTW-Content-SHA256": hashlib.sha256(content).hexdigest(),
        })

    return router
