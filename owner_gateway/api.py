"""Firebase-authenticated owner API for Product Briefs and Results."""

from __future__ import annotations

from typing import Any, Mapping

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .auth import FirebaseVerifier, OwnerDependency, OwnerIdentity
from .settings import Settings


INSTAGRAM_TASK = (
    "Create one ready-to-publish Instagram feed post for the approved Product Brief "
    "using Natal's canonical visual identity."
)


def instagram_run_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Map the no-form owner action to the sole public Result profile."""
    if set(request) != {"request_id", "brief_id"}:
        raise ValueError("Instagram post creation requires only request_id and brief_id")
    return {
        "request_id": request["request_id"],
        "brief_id": request["brief_id"],
        "task": INSTAGRAM_TASK,
        "output_profile": "instagram_static_ad_v1",
    }


def create_app(settings: Settings, verifier: FirebaseVerifier | None = None) -> FastAPI:
    owner = OwnerDependency(verifier or FirebaseVerifier(settings))
    app = FastAPI(title="PTW Result Gateway", version="1.0.0", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys([settings.public_origin, *settings.owner_public_origins])),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
        expose_headers=["ETag", "Content-Length"],
    )

    async def validation_bridge(
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        actor: str = "owner-web",
        timeout: float = 30,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method,
                    f"{settings.validation_service_url}{path}",
                    headers={
                        "X-PTW-Owner-Gateway-Token": settings.validation_service_token,
                        "X-PTW-Actor": actor,
                    },
                    json=None if body is None else dict(body),
                    params=dict(params or {}),
                )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=503, detail="Result service is unavailable") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(
                status_code=response.status_code,
                detail=detail or "Result service request failed",
            )
        return response

    def actor(identity: OwnerIdentity) -> str:
        return f"firebase:{identity.uid}"[:200]

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/overview")
    async def overview(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        projects = (await validation_bridge("GET", "/internal/v1/projects", params={"limit": 100})).json()["items"]
        return {
            "projects": len(projects),
            "briefs": sum(int(item["brief_count"]) for item in projects),
            "result_runs": sum(int(item["result_run_count"]) for item in projects),
        }

    @app.get("/api/v1/projects")
    async def projects(
        limit: int = Query(default=100, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge("GET", "/internal/v1/projects", params={"limit": limit})).json()

    @app.post("/api/v1/projects/{project_id}/rename")
    async def rename_project(
        project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/projects/{project_id}/rename", body=request, actor=actor(identity)
        )).json()

    @app.post("/api/v1/briefs", status_code=202)
    async def create_brief(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", "/internal/v1/briefs", body=request, actor=actor(identity)
        )).json()

    @app.get("/api/v1/briefs")
    async def briefs(
        project_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if project_id:
            params["project_id"] = project_id
        return (await validation_bridge("GET", "/internal/v1/briefs", params=params)).json()

    @app.get("/api/v1/briefs/{brief_id}")
    async def brief(brief_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/briefs/{brief_id}")).json()

    @app.post("/api/v1/briefs/{brief_id}/correct", status_code=202)
    async def correct_brief(
        brief_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/briefs/{brief_id}/correct", body=request, actor=actor(identity)
        )).json()

    @app.post("/api/v1/briefs/{brief_id}/retry", status_code=202)
    async def retry_brief(
        brief_id: str, identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/briefs/{brief_id}/retry", body={}, actor=actor(identity)
        )).json()

    @app.post("/api/v1/briefs/{brief_id}/approve")
    async def approve_brief(
        brief_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/briefs/{brief_id}/approve", body=request, actor=actor(identity)
        )).json()

    @app.post("/api/v1/content-runs", status_code=202)
    async def create_content_run(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        try:
            body = instagram_run_request(request)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return (await validation_bridge(
            "POST", "/internal/v1/content-runs", body=body,
            actor=actor(identity), timeout=60,
        )).json()

    @app.get("/api/v1/content-runs")
    async def content_runs(
        project_id: str, limit: int = Query(default=50, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", "/internal/v1/content-runs", params={"project_id": project_id, "limit": limit}
        )).json()

    @app.get("/api/v1/content-runs/{run_id}")
    async def content_run(run_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/content-runs/{run_id}")).json()

    @app.get("/api/v1/content-runs/{run_id}/result")
    async def content_result(run_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/content-runs/{run_id}/result")).json()

    @app.get("/api/v1/content-runs/{run_id}/result/asset")
    async def content_result_asset(
        run_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> Response:
        response = await validation_bridge(
            "GET", f"/internal/v1/content-runs/{run_id}/result/asset", timeout=60
        )
        headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
        if response.headers.get("etag"):
            headers["ETag"] = response.headers["etag"]
        return Response(
            content=response.content,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            headers=headers,
        )

    @app.get("/api/v1/content-runs/{run_id}/candidates/{candidate_id}/asset")
    async def content_candidate_asset(
        run_id: str, candidate_id: str, _identity: OwnerIdentity = Depends(owner)
    ) -> Response:
        response = await validation_bridge(
            "GET",
            f"/internal/v1/content-runs/{run_id}/candidates/{candidate_id}/asset",
            timeout=60,
        )
        headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
        if response.headers.get("etag"):
            headers["ETag"] = response.headers["etag"]
        return Response(
            content=response.content,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            headers=headers,
        )

    @app.get("/api/v1/content-runs/{run_id}/debug")
    async def content_debug(run_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/content-runs/{run_id}/debug")).json()

    @app.post("/api/v1/content-runs/{run_id}/retry", status_code=202)
    async def retry_content_run(
        run_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/content-runs/{run_id}/retry", body=request,
            actor=actor(identity), timeout=60,
        )).json()

    @app.post("/api/v1/content-runs/{run_id}/feedback")
    async def content_feedback(
        run_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/content-runs/{run_id}/feedback", body=request,
            actor=actor(identity),
        )).json()

    @app.post("/api/v1/content-runs/{run_id}/outcomes")
    async def content_outcome(
        run_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/content-runs/{run_id}/outcomes", body=request,
            actor=actor(identity),
        )).json()

    @app.get("/api/v1/system/health")
    async def system_health(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        try:
            response = await validation_bridge("GET", "/readyz", timeout=5)
            return {"gateway": "ok", "result_service": response.json()}
        except HTTPException as error:
            return {"gateway": "ok", "result_service": {"status": "unavailable", "detail": error.detail}}

    @app.post("/api/v1/system/emergency-stop")
    async def emergency_stop(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        if set(request) != {"active"} or not isinstance(request.get("active"), bool):
            raise HTTPException(status_code=400, detail="active boolean is required")
        return (await validation_bridge(
            "POST", "/internal/emergency-stop",
            body={"active": request["active"], "actor": actor(identity)},
            actor=actor(identity),
        )).json()

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
