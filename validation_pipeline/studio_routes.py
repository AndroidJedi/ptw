"""Shared FastAPI routes for the bounded Universal Studio templates."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.params import Depends as DependsParameter
from fastapi.responses import Response

def studio_creative_router(
    service: Any, *, prefix: str,
    dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    """Expose only Project- and creative-scoped Studio mutations."""

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

    @router.get("/templates")
    def templates() -> dict[str, Any]:
        return service.templates()

    @router.get("/projects/{project_id}/creatives")
    def creatives(project_id: str) -> dict[str, Any]:
        try:
            return service.list_creatives(project_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives", status_code=202)
    def create_variant(
        project_id: str, request: Mapping[str, Any], background: BackgroundTasks,
    ) -> dict[str, Any]:
        fields(
            request, {"source_brief_id", "template_id"},
            "Studio creative variant requires source_brief_id and template_id",
        )
        try:
            creative, created = service.reserve_from_brief(
                brief_id=str(request["source_brief_id"]),
                template_id=str(request["template_id"]), requested_by="owner-web",
                additional=True,
            )
            if creative["project_id"] != project_id:
                raise KeyError("Studio creative was not found in this Project")
            if created:
                background.add_task(service.generate, creative["creative_id"])
            return {"creative": creative, "created": created}
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    def creative(project_id: str, creative_id: str) -> dict[str, Any]:
        return service.detail(project_id, creative_id)

    @router.get("/projects/{project_id}/creatives/{creative_id}")
    def detail(project_id: str, creative_id: str) -> dict[str, Any]:
        try:
            return creative(project_id, creative_id)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/retry", status_code=202)
    def retry(
        project_id: str, creative_id: str, request: Mapping[str, Any],
        background: BackgroundTasks,
    ) -> dict[str, Any]:
        fields(request, set(), "Studio creative retry has no input fields")
        try:
            value = service.retry_generation(project_id, creative_id)
            background.add_task(service.generate, creative_id)
            return value
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/phone-screen/retry", status_code=202)
    def retry_phone_image(
        project_id: str, creative_id: str, request: Mapping[str, Any],
        background: BackgroundTasks,
    ) -> dict[str, Any]:
        fields(request, set(), "Studio phone image retry has no input fields")
        try:
            value = service.queue_phone_image_retry(project_id, creative_id)
            background.add_task(service.retry_phone_image, project_id, creative_id)
            return value
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/configuration")
    def configuration(project_id: str, creative_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(
            request, {"base_sha256", "configuration", "content"},
            "Studio configuration fields are invalid",
        )
        if not isinstance(request["configuration"], Mapping) or not isinstance(request["content"], Mapping):
            raise HTTPException(status_code=400, detail="Studio configuration must contain objects")
        try:
            return service.mutate(
                project_id, creative_id, "save_configuration",
                base_sha256=str(request["base_sha256"]),
                configuration=request["configuration"], content=request["content"],
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/save")
    def save(project_id: str, creative_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(
            request, {"base_sha256", "configuration", "content"},
            "Save creative fields are invalid",
        )
        try:
            return service.checkpoint(
                project_id, creative_id, kind="save",
                base_sha256=str(request["base_sha256"]),
                configuration=request["configuration"], content=request["content"],
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/templates/apply")
    def apply_template(project_id: str, creative_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"base_sha256", "template_id"}, "Studio template apply fields are invalid")
        try:
            return service.mutate(
                project_id, creative_id, "apply_template",
                base_sha256=str(request["base_sha256"]), template_id=str(request["template_id"]),
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/assets/{slot}")
    def asset(project_id: str, creative_id: str, slot: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"base_sha256", "mime_type", "bytes_base64"}, "Studio asset fields are invalid")
        try:
            return service.mutate(
                project_id, creative_id, "upload_asset", slot,
                base_sha256=str(request["base_sha256"]), mime_type=str(request["mime_type"]),
                bytes_base64=str(request["bytes_base64"]),
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/phone-screen/select")
    def select_phone(project_id: str, creative_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"base_sha256", "sha256"}, "Studio phone selection fields are invalid")
        try:
            return service.mutate(
                project_id, creative_id, "select_phone_screen",
                base_sha256=str(request["base_sha256"]), sha256=str(request["sha256"]),
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/phone-screen/generate")
    def generate_phone(project_id: str, creative_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) not in (
            {"base_sha256", "visual_direction"},
            {"base_sha256", "visual_direction", "enhance_current"},
        ) or not isinstance(request.get("enhance_current", False), bool):
            raise HTTPException(status_code=400, detail="Studio phone generation fields are invalid")
        try:
            return service.mutate(
                project_id, creative_id, "generate_phone_screen",
                base_sha256=str(request["base_sha256"]),
                visual_direction=str(request["visual_direction"]),
                enhance_current=bool(request.get("enhance_current", False)),
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.get("/projects/{project_id}/creatives/{creative_id}/phone-screen/history/{sha256}")
    def phone_history(project_id: str, creative_id: str, sha256: str) -> Response:
        try:
            service.detail(project_id, creative_id)
            image = service._workspace(creative_id).phone_screen_history_image(sha256)
        except (KeyError, ValueError) as error:
            raise fail(error) from error
        return Response(
            content=image["bytes"], media_type=image["mime_type"],
            headers={
                "Cache-Control": "private, no-store", "ETag": f'"{image["sha256"]}"',
                "X-PTW-Content-SHA256": image["sha256"], "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post("/projects/{project_id}/creatives/{creative_id}/pexels")
    def pexels(project_id: str, creative_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(request, {"base_sha256", "slot", "query", "isolate"}, "Studio Pexels fields are invalid")
        if not isinstance(request["isolate"], bool):
            raise HTTPException(status_code=400, detail="Studio Pexels isolate must be boolean")
        try:
            workspace = service._workspace(creative_id)
            service.detail(project_id, creative_id)
            value = workspace.source_pexels(
                str(request["slot"]), base_sha256=str(request["base_sha256"]),
                query=str(request["query"]), isolate=request["isolate"],
            )
            service.authority.update_creative(creative_id, state_sha256=value["state_sha256"])
            return {**value, **service.summary(creative_id)}
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/preview")
    def preview(project_id: str, creative_id: str, request: Mapping[str, Any]) -> Response:
        if set(request) not in ({"state_sha256"}, {"state_sha256", "configuration", "content"}):
            raise HTTPException(status_code=400, detail="Studio preview fields are invalid")
        try:
            service.detail(project_id, creative_id)
            rendered = service._workspace(creative_id).render_preview(
                state_sha256=str(request["state_sha256"]),
                configuration=request.get("configuration"), content=request.get("content"),
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error
        return Response(
            content=rendered["bytes"], media_type="image/png",
            headers={
                "Cache-Control": "private, no-store", "ETag": f'"{rendered["bytes_sha256"]}"',
                "X-PTW-Content-SHA256": rendered["bytes_sha256"], "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post("/projects/{project_id}/creatives/{creative_id}/component-settings")
    def component_settings(project_id: str, creative_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) not in ({"state_sha256"}, {"state_sha256", "configuration", "content"}):
            raise HTTPException(status_code=400, detail="Studio component metadata fields are invalid")
        try:
            service.detail(project_id, creative_id)
            return service._workspace(creative_id).component_settings(
                state_sha256=str(request["state_sha256"]),
                configuration=request.get("configuration"), content=request.get("content"),
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/approve")
    def approve(project_id: str, creative_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        fields(
            request, {"base_sha256", "configuration", "content", "change_note"},
            "Approve creative fields are invalid",
        )
        try:
            return service.checkpoint(
                project_id, creative_id, kind="approve",
                base_sha256=str(request["base_sha256"]),
                configuration=request["configuration"], content=request["content"],
                change_note=str(request["change_note"]),
            )
        except (KeyError, ValueError, RuntimeError, FileExistsError) as error:
            raise fail(error) from error

    @router.get("/projects/{project_id}/creatives/{creative_id}/versions/{version}/render")
    def version_render(project_id: str, creative_id: str, version: int) -> Response:
        try:
            service.detail(project_id, creative_id)
            rendered = service._workspace(creative_id).version_render(version)
        except (KeyError, ValueError) as error:
            raise fail(error) from error
        return Response(
            content=rendered["bytes"], media_type=rendered["mime_type"],
            headers={
                "Cache-Control": "private, no-store", "ETag": f'"{rendered["sha256"]}"',
                "X-PTW-Content-SHA256": rendered["sha256"], "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/projects/{project_id}/creatives/{creative_id}/versions/{version}")
    def version_detail(project_id: str, creative_id: str, version: int) -> dict[str, Any]:
        try:
            service.detail(project_id, creative_id)
            return service._workspace(creative_id).version_detail(version)
        except (KeyError, ValueError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/learning/{proposal_id}")
    def learning(
        project_id: str, creative_id: str, proposal_id: str, request: Mapping[str, Any],
    ) -> dict[str, Any]:
        fields(request, {"decision"}, "Studio learning decision is required")
        try:
            return service.decide_learning(
                project_id, creative_id, proposal_id, str(request["decision"]),
            )
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    @router.post("/projects/{project_id}/creatives/{creative_id}/checkpoints/{checkpoint_id}/retry")
    def retry_learning(
        project_id: str, creative_id: str, checkpoint_id: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        fields(request, set(), "Studio learning retry has no input fields")
        try:
            return service.retry_learning(project_id, creative_id, checkpoint_id)
        except (KeyError, ValueError, RuntimeError) as error:
            raise fail(error) from error

    return router
