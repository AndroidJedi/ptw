"""Authenticated project-scoped routes for private Landing Studio pages."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.params import Depends as DependsParameter
from fastapi.responses import Response


def landing_page_router(service: Any, *, prefix: str, dependencies: Sequence[DependsParameter] = ()) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    def fail(error: Exception) -> HTTPException:
        if isinstance(error, KeyError):
            return HTTPException(status_code=404, detail=str(error).strip("'"))
        if isinstance(error, (RuntimeError, FileExistsError)):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=400, detail=str(error))

    def fields(request: Mapping[str, Any], expected: set[str], message: str) -> None:
        if set(request) != expected:
            raise HTTPException(status_code=400, detail=message)

    @router.get("/projects/{project_id}/source-posts")
    def source_posts(project_id: str) -> dict[str, Any]:
        try:
            return service.source_versions(project_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.get("/projects/{project_id}/pages")
    def pages(project_id: str) -> dict[str, Any]:
        try:
            return service.list_pages(project_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    def reserve(project_id: str, request: Mapping[str, Any], background: BackgroundTasks, *, additional: bool) -> dict[str, Any]:
        fields(request, {"source_creative_id", "source_version"}, "Landing creation fields are invalid")
        if isinstance(request["source_version"], bool) or not isinstance(request["source_version"], int):
            raise HTTPException(status_code=400, detail="Landing source Post version is invalid")
        try:
            page, created = service.reserve_from_post(
                project_id=project_id, source_creative_id=str(request["source_creative_id"]),
                source_version=request["source_version"], requested_by="owner-web", additional=additional,
            )
            if created:
                background.add_task(service.generate, page["landing_id"])
            return {"landing": page, "created": created}
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/pages", status_code=202)
    def create_page(project_id: str, request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
        return reserve(project_id, request, background, additional=False)

    @router.post("/projects/{project_id}/pages/variants", status_code=202)
    def create_variant(project_id: str, request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
        return reserve(project_id, request, background, additional=True)

    @router.get("/projects/{project_id}/pages/{landing_id}")
    def detail(project_id: str, landing_id: str) -> dict[str, Any]:
        try:
            return service.detail(project_id, landing_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/pages/{landing_id}/retry", status_code=202)
    def retry(project_id: str, landing_id: str, request: Mapping[str, Any], background: BackgroundTasks) -> dict[str, Any]:
        fields(request, set(), "Landing retry has no input fields")
        try:
            value = service.retry_generation(project_id, landing_id)
            background.add_task(service.generate, landing_id)
            return value
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/pages/{landing_id}/configuration")
    def configuration(project_id: str, landing_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"base_sha256", "configuration", "content"}, "Landing configuration fields are invalid")
        if not isinstance(request["configuration"], Mapping) or not isinstance(request["content"], Mapping):
            raise HTTPException(status_code=400, detail="Landing configuration must contain objects")
        try:
            return service.mutate(project_id, landing_id, "save_configuration", base_sha256=str(request["base_sha256"]), configuration=request["configuration"], content=request["content"])
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/pages/{landing_id}/visuals/{slot}/generate")
    def generate_visual(project_id: str, landing_id: str, slot: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) not in ({"base_sha256", "visual_direction"}, {"base_sha256", "visual_direction", "enhance_current"}) or not isinstance(request.get("enhance_current", False), bool):
            raise HTTPException(status_code=400, detail="Landing visual generation fields are invalid")
        try:
            page = service.authority.get_page(landing_id)
            return service.mutate(project_id, landing_id, "generate_visual", base_sha256=str(request["base_sha256"]), slot=slot, visual_direction=str(request["visual_direction"]), prompt=service._image_prompt(page, slot, str(request["visual_direction"])), enhance_current=bool(request.get("enhance_current", False)))
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/pages/{landing_id}/visuals/{slot}/select")
    def select_visual(project_id: str, landing_id: str, slot: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"base_sha256", "sha256"}, "Landing visual selection fields are invalid")
        try:
            return service.mutate(project_id, landing_id, "select_visual", base_sha256=str(request["base_sha256"]), slot=slot, sha256=str(request["sha256"]))
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.get("/projects/{project_id}/pages/{landing_id}/visuals/{slot}/history/{sha256}")
    def visual_history(project_id: str, landing_id: str, slot: str, sha256: str) -> Response:
        try:
            service.detail(project_id, landing_id)
            image = service._workspace(landing_id).visual_image(slot, sha256)
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error
        return Response(content=image["bytes"], media_type=image["mime_type"], headers={"Cache-Control": "private, no-store", "ETag": f'"{image["sha256"]}"', "X-PTW-Content-SHA256": image["sha256"], "X-Content-Type-Options": "nosniff"})

    @router.post("/projects/{project_id}/pages/{landing_id}/save")
    def save(project_id: str, landing_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"base_sha256", "configuration", "content"}, "Landing save fields are invalid")
        try:
            return service.checkpoint(project_id, landing_id, kind="save", base_sha256=str(request["base_sha256"]), configuration=request["configuration"], content=request["content"])
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/pages/{landing_id}/approve")
    def approve(project_id: str, landing_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"base_sha256", "configuration", "content", "change_note"}, "Landing approval fields are invalid")
        try:
            return service.checkpoint(project_id, landing_id, kind="approve", base_sha256=str(request["base_sha256"]), configuration=request["configuration"], content=request["content"], change_note=str(request["change_note"]))
        except (KeyError, ValueError, RuntimeError, FileExistsError) as error:
            raise fail(error) from error

    @router.get("/projects/{project_id}/pages/{landing_id}/versions/{version}")
    def version(project_id: str, landing_id: str, version: int) -> dict[str, Any]:
        try:
            service.detail(project_id, landing_id)
            return service._workspace(landing_id).version_detail(version)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/pages/{landing_id}/learning/{proposal_id}")
    def learning(project_id: str, landing_id: str, proposal_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"decision"}, "Landing learning decision is required")
        try:
            return service.decide_learning(project_id, landing_id, proposal_id, str(request["decision"]))
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/pages/{landing_id}/learning/{checkpoint_id}/retry")
    def retry_learning(project_id: str, landing_id: str, checkpoint_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, set(), "Landing learning retry has no input fields")
        try:
            return service.retry_learning(project_id, landing_id, checkpoint_id)
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    return router
