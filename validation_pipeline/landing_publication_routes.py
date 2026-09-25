"""Owner and public read routes for immutable Landing publications."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.params import Depends as DependsParameter
from fastapi.responses import Response


def _failure(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error).strip("'") or "Landing was not found")
    if isinstance(error, RuntimeError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=409, detail=str(error))


def landing_publication_owner_router(
    service: Any, *, prefix: str, dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    @router.get("/projects/{project_id}/publication")
    def publication(project_id: str) -> dict[str, Any]:
        try:
            return {"publication": service.get(project_id)}
        except (KeyError, ValueError) as error:
            raise _failure(error) from error

    @router.get("/projects/{project_id}/publication/availability")
    def availability(
        project_id: str, slug: str = Query(...),
    ) -> dict[str, Any]:
        try:
            return service.availability(project_id, slug)
        except (KeyError, ValueError) as error:
            raise _failure(error) from error

    @router.post("/projects/{project_id}/publication/publish")
    def publish(
        project_id: str, request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        required = {"request_id", "landing_id", "version"}
        allowed = required | {"slug"}
        if not required <= set(request) <= allowed:
            raise HTTPException(status_code=400, detail="Landing publication fields are invalid")
        if isinstance(request["version"], bool) or not isinstance(request["version"], int):
            raise HTTPException(status_code=400, detail="Landing publication version is invalid")
        try:
            return service.publish(
                project_id=project_id, request_id=str(request["request_id"]),
                landing_id=str(request["landing_id"]), version=request["version"],
                slug=None if "slug" not in request else str(request["slug"]),
                requested_by=x_ptw_actor[:200],
            )
        except (KeyError, RuntimeError, ValueError) as error:
            raise _failure(error) from error

    @router.post("/projects/{project_id}/publication/unpublish")
    def unpublish(
        project_id: str, request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        if set(request) != {"request_id"}:
            raise HTTPException(status_code=400, detail="Landing unpublish requires one request_id")
        try:
            return service.unpublish(
                project_id=project_id, request_id=str(request["request_id"]),
                requested_by=x_ptw_actor[:200],
            )
        except (KeyError, RuntimeError, ValueError) as error:
            raise _failure(error) from error

    return router


def landing_publication_read_router(
    service: Any, *, prefix: str, dependencies: Sequence[DependsParameter] = (),
) -> APIRouter:
    router = APIRouter(prefix=prefix, dependencies=list(dependencies))

    @router.api_route("/{slug}", methods=["GET", "HEAD"])
    def snapshot(slug: str) -> Response:
        try:
            value = service.snapshot(slug)
        except (KeyError, ValueError):
            raise HTTPException(status_code=404, detail="Published Landing was not found")
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail="Published Landing is temporarily unavailable") from error
        import json
        return Response(
            content=json.dumps(value, ensure_ascii=False, separators=(",", ":")),
            media_type="application/json",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.api_route("/{slug}/versions/{version_sha256}/assets/{slot}/{sha256}.png", methods=["GET", "HEAD"])
    def asset(slug: str, version_sha256: str, slot: str, sha256: str) -> Response:
        try:
            value = service.asset(slug, version_sha256, slot, sha256)
        except (KeyError, ValueError):
            raise HTTPException(status_code=404, detail="Published Landing asset was not found")
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail="Published Landing asset is temporarily unavailable") from error
        return Response(
            content=value["bytes"], media_type=value["mime_type"],
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "ETag": f'"{value["sha256"]}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.api_route("/{slug}/versions/{version}/assets/{slot}/{source}/webp-v1/{digest}.webp", methods=["GET", "HEAD"])
    def display_asset(slug: str, version: str, slot: str, source: str, digest: str) -> Response:
        try:
            value = service.display_asset(slug, version, slot, source, digest)
        except (KeyError, ValueError):
            raise HTTPException(status_code=404, detail="Published Landing display image was not found")
        except (RuntimeError, OSError) as error:
            raise HTTPException(status_code=503, detail="Published Landing display image is temporarily unavailable") from error
        return Response(content=value["bytes"], media_type="image/webp", headers={
            "Cache-Control": "public, max-age=31536000, immutable", "ETag": f'"{digest}"',
            "X-Content-Type-Options": "nosniff",
        })

    return router
