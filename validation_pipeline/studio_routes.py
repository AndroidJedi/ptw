"""Shared FastAPI routes for the bounded Universal Studio templates."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends as DependsParameter
from fastapi.responses import Response

from .studio_workspace import UniversalStudioWorkspace


def studio_router(
    workspace: UniversalStudioWorkspace, *, prefix: str,
    dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    def fail(error: Exception) -> HTTPException:
        if isinstance(error, KeyError):
            return HTTPException(status_code=404, detail=str(error).strip("'"))
        if isinstance(error, (RuntimeError, FileExistsError)):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=400, detail=str(error))

    @router.get("")
    def detail() -> dict[str, Any]:
        try:
            return workspace.detail()
        except ValueError as error:
            raise fail(error) from error

    @router.post("/configuration")
    def configuration(request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"base_sha256", "configuration", "content"}:
            raise HTTPException(status_code=400, detail="Studio universal configuration fields are invalid")
        if not isinstance(request["configuration"], Mapping) or not isinstance(request["content"], Mapping):
            raise HTTPException(status_code=400, detail="Studio universal configuration must contain objects")
        try:
            return workspace.save_configuration(
                base_sha256=str(request["base_sha256"]),
                configuration=request["configuration"],
                content=request["content"],
            )
        except (ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/templates/apply")
    def apply_template(request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"base_sha256", "template_id"}:
            raise HTTPException(status_code=400, detail="Studio template apply fields are invalid")
        try:
            return workspace.apply_template(
                base_sha256=str(request["base_sha256"]), template_id=str(request["template_id"]),
            )
        except (ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/assets/{slot}")
    def asset(slot: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"base_sha256", "mime_type", "bytes_base64"}:
            raise HTTPException(status_code=400, detail="Studio fixed asset fields are invalid")
        try:
            return workspace.upload_asset(
                slot,
                base_sha256=str(request["base_sha256"]),
                mime_type=str(request["mime_type"]),
                bytes_base64=str(request["bytes_base64"]),
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/pexels")
    def pexels(request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"base_sha256", "slot", "query", "isolate"} or not isinstance(request["isolate"], bool):
            raise HTTPException(status_code=400, detail="Studio Pexels sourcing fields are invalid")
        try:
            return workspace.source_pexels(
                str(request["slot"]),
                base_sha256=str(request["base_sha256"]),
                query=str(request["query"]),
                isolate=request["isolate"],
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/preview")
    def preview(request: Mapping[str, Any]) -> Response:
        persisted_fields = {"state_sha256"}
        draft_fields = {"state_sha256", "configuration", "content"}
        if set(request) not in (persisted_fields, draft_fields):
            raise HTTPException(status_code=400, detail="Studio preview fields are invalid")
        if set(request) == draft_fields and (
            not isinstance(request["configuration"], Mapping)
            or not isinstance(request["content"], Mapping)
        ):
            raise HTTPException(status_code=400, detail="Studio draft preview must contain objects")
        try:
            rendered = workspace.render_preview(
                state_sha256=str(request["state_sha256"]),
                configuration=request.get("configuration"),
                content=request.get("content"),
            )
        except (KeyError, ValueError, RuntimeError) as error:
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

    @router.post("/component-settings")
    def component_settings(request: Mapping[str, Any]) -> dict[str, Any]:
        persisted_fields = {"state_sha256"}
        draft_fields = {"state_sha256", "configuration", "content"}
        if set(request) not in (persisted_fields, draft_fields):
            raise HTTPException(status_code=400, detail="Studio component metadata fields are invalid")
        if set(request) == draft_fields and (
            not isinstance(request["configuration"], Mapping)
            or not isinstance(request["content"], Mapping)
        ):
            raise HTTPException(status_code=400, detail="Studio component metadata must contain objects")
        try:
            return workspace.component_settings(
                state_sha256=str(request["state_sha256"]),
                configuration=request.get("configuration"),
                content=request.get("content"),
            )
        except (ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/approve")
    def approve(request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"state_sha256", "change_note"}:
            raise HTTPException(status_code=400, detail="Studio approval fields are invalid")
        try:
            return workspace.approve_version(
                state_sha256=str(request["state_sha256"]),
                change_note=str(request["change_note"]),
            )
        except (KeyError, ValueError, RuntimeError, FileExistsError) as error:
            raise fail(error) from error

    @router.get("/versions/{version}/render")
    def version_render(version: int) -> Response:
        try:
            rendered = workspace.version_render(version)
        except (KeyError, ValueError) as error:
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

    @router.get("/versions/{version}")
    def version_detail(version: int) -> dict[str, Any]:
        try:
            return workspace.version_detail(version)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    return router
