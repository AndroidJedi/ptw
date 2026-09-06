"""Firebase-authenticated owner API for Product Briefs and Universal Ad Studio."""

from __future__ import annotations

import re
from typing import Any, Mapping

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .auth import FirebaseVerifier, OwnerDependency, OwnerIdentity
from .settings import Settings


def create_app(settings: Settings, verifier: FirebaseVerifier | None = None) -> FastAPI:
    owner = OwnerDependency(verifier or FirebaseVerifier(settings))
    app = FastAPI(title="PTW Owner Gateway", version="1.0.0", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys([settings.public_origin, *settings.owner_public_origins])),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
        expose_headers=["ETag", "Content-Length", "X-PTW-Content-SHA256"],
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
            raise HTTPException(status_code=503, detail="Validation service is unavailable") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(
                status_code=response.status_code,
                detail=detail or "Validation service request failed",
            )
        return response

    def actor(identity: OwnerIdentity) -> str:
        return f"firebase:{identity.uid}"[:200]

    async def codex_authorization_bridge(method: str, path: str) -> dict[str, Any]:
        if not settings.codex_authorization_service_url or not settings.codex_authorization_bridge_token:
            raise HTTPException(status_code=503, detail="ChatGPT authorization service is unavailable")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.request(
                    method, f"{settings.codex_authorization_service_url}{path}",
                    headers={"X-PTW-Codex-Authorization-Token": settings.codex_authorization_bridge_token},
                )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=503, detail="ChatGPT authorization service is unavailable") from error
        if response.status_code >= 400:
            raise HTTPException(status_code=503, detail="ChatGPT authorization service is unavailable")
        try:
            payload = response.json()
        except ValueError as error:
            raise HTTPException(status_code=503, detail="ChatGPT authorization service is unavailable") from error
        if not isinstance(payload, dict):
            raise HTTPException(status_code=503, detail="ChatGPT authorization service is unavailable")
        # This is intentionally an allowlist. CLI output and auth-file contents
        # must never be reflected through the owner-facing API.
        status = payload.get("status")
        test_status = payload.get("test_status")
        if status not in {"authorized", "authorization_required", "authorizing", "verifying", "failed"}:
            raise HTTPException(status_code=503, detail="ChatGPT authorization service is unavailable")
        if test_status not in {None, "passed", "failed"}:
            raise HTTPException(status_code=503, detail="ChatGPT authorization service is unavailable")
        safe: dict[str, Any] = {"status": status, "test_status": test_status}
        if status == "authorizing":
            url = payload.get("authorization_url")
            code = payload.get("device_code")
            if isinstance(url, str) and re.fullmatch(r"https://auth\.openai\.com/codex/device(?:\?[^\s]{0,450})?", url):
                safe["authorization_url"] = url
            if isinstance(code, str) and re.fullmatch(r"[A-Z0-9]{4,8}-[A-Z0-9]{4,8}", code):
                safe["device_code"] = code
        return safe

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/overview")
    async def overview(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        projects = (await validation_bridge("GET", "/internal/v1/projects", params={"limit": 100})).json()["items"]
        return {
            "projects": len(projects),
            "briefs": sum(int(item["brief_count"]) for item in projects),
        }

    @app.get("/api/v1/settings/chatgpt-authorization")
    async def chatgpt_authorization(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await codex_authorization_bridge("GET", "/v1/authorization")

    @app.post("/api/v1/settings/chatgpt-authorization/refresh", status_code=202)
    async def refresh_chatgpt_authorization(
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return await codex_authorization_bridge("POST", "/v1/authorization/refresh")

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

    @app.post("/api/v1/briefs/{brief_id}/approve", status_code=202)
    async def approve_brief(
        brief_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/briefs/{brief_id}/approve", body=request, actor=actor(identity)
        )).json()

    @app.get("/api/v1/studio/templates")
    async def studio_templates(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", "/internal/v1/studio/templates", timeout=60)).json()

    @app.get("/api/v1/studio/projects/{project_id}/creatives")
    async def studio_creatives(
        project_id: str, _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/studio/projects/{project_id}/creatives", timeout=60,
        )).json()

    @app.post("/api/v1/studio/projects/{project_id}/creatives", status_code=202)
    async def studio_create_variant(
        project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/studio/projects/{project_id}/creatives",
            body=request, actor=actor(identity), timeout=60,
        )).json()

    @app.get("/api/v1/studio/projects/{project_id}/creatives/{creative_id}")
    async def studio_creative(
        project_id: str, creative_id: str, _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/studio/projects/{project_id}/creatives/{creative_id}",
            timeout=60,
        )).json()

    def creative_path(project_id: str, creative_id: str, suffix: str = "") -> str:
        return f"/internal/v1/studio/projects/{project_id}/creatives/{creative_id}{suffix}"

    async def creative_post(
        project_id: str, creative_id: str, suffix: str, request: Mapping[str, Any],
        identity: OwnerIdentity, *, timeout: float,
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", creative_path(project_id, creative_id, suffix), body=request,
            actor=actor(identity), timeout=timeout,
        )).json()

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/retry", status_code=202)
    async def studio_retry(project_id: str, creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/retry", request, identity, timeout=60)

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/phone-screen/retry", status_code=202)
    async def studio_phone_retry(project_id: str, creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/phone-screen/retry", request, identity, timeout=60)

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/configuration")
    async def studio_configuration(project_id: str, creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/configuration", request, identity, timeout=60)

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/save")
    async def studio_save(project_id: str, creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/save", request, identity, timeout=480)

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/templates/apply")
    async def studio_template_apply(project_id: str, creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/templates/apply", request, identity, timeout=60)

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/assets/{slot}")
    async def studio_asset(project_id: str, creative_id: str, slot: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, f"/assets/{slot}", request, identity, timeout=90)

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/pexels")
    async def studio_pexels(project_id: str, creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/pexels", request, identity, timeout=90)

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/phone-screen/generate")
    async def studio_phone_screen_generate(project_id: str, creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/phone-screen/generate", request, identity, timeout=480)

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/phone-screen/select")
    async def studio_phone_screen_select(project_id: str, creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/phone-screen/select", request, identity, timeout=60)

    @app.get("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/phone-screen/history/{sha256}")
    async def studio_phone_screen_history(
        project_id: str, creative_id: str, sha256: str,
        _identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        response = await validation_bridge(
            "GET", creative_path(project_id, creative_id, f"/phone-screen/history/{sha256}"), timeout=60,
        )
        digest = response.headers.get("x-ptw-content-sha256", "")
        headers = {
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        }
        if response.headers.get("etag"):
            headers["ETag"] = response.headers["etag"]
        if digest:
            headers["X-PTW-Content-SHA256"] = digest
        return Response(
            content=response.content,
            media_type=response.headers.get("content-type", "image/png"),
            headers=headers,
        )

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/preview")
    async def studio_preview(
        project_id: str, creative_id: str, request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        response = await validation_bridge(
            "POST", creative_path(project_id, creative_id, "/preview"),
            body=request, actor=actor(identity), timeout=90,
        )
        digest = response.headers.get("x-ptw-content-sha256", "")
        headers = {
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        }
        if response.headers.get("etag"):
            headers["ETag"] = response.headers["etag"]
        if digest:
            headers["X-PTW-Content-SHA256"] = digest
        return Response(
            content=response.content,
            media_type=response.headers.get("content-type", "image/png"),
            headers=headers,
        )

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/component-settings")
    async def studio_component_settings(
        project_id: str, creative_id: str, request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/component-settings", request, identity, timeout=60)

    @app.get("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/versions/{version}/render")
    async def studio_version_render(
        project_id: str, creative_id: str, version: int,
        _identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        response = await validation_bridge(
            "GET", creative_path(project_id, creative_id, f"/versions/{version}/render"), timeout=90,
        )
        digest = response.headers.get("x-ptw-content-sha256", "")
        headers = {
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        }
        if response.headers.get("etag"):
            headers["ETag"] = response.headers["etag"]
        if digest:
            headers["X-PTW-Content-SHA256"] = digest
        return Response(
            content=response.content,
            media_type=response.headers.get("content-type", "image/png"),
            headers=headers,
        )

    @app.get("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/versions/{version}")
    async def studio_version(
        project_id: str, creative_id: str, version: int,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", creative_path(project_id, creative_id, f"/versions/{version}"), timeout=60,
        )).json()

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/approve")
    async def approve_studio_template(
        project_id: str, creative_id: str, request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/approve", request, identity, timeout=480)

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/learning/{proposal_id}")
    async def studio_learning(
        project_id: str, creative_id: str, proposal_id: str,
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return await creative_post(
            project_id, creative_id, f"/learning/{proposal_id}", request, identity, timeout=60,
        )

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/checkpoints/{checkpoint_id}/retry")
    async def studio_learning_retry(
        project_id: str, creative_id: str, checkpoint_id: str,
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return await creative_post(
            project_id, creative_id, f"/checkpoints/{checkpoint_id}/retry",
            request, identity, timeout=480,
        )

    def landing_path(project_id: str, landing_id: str = "", suffix: str = "") -> str:
        base = f"/internal/v1/landings/projects/{project_id}"
        return f"{base}/pages/{landing_id}{suffix}" if landing_id else base

    async def landing_post(project_id: str, landing_id: str, suffix: str, request: Mapping[str, Any], identity: OwnerIdentity, *, timeout: float = 90) -> dict[str, Any]:
        return (await validation_bridge("POST", landing_path(project_id, landing_id, suffix), body=request, actor=actor(identity), timeout=timeout)).json()

    @app.get("/api/v1/landings/projects/{project_id}/source-posts")
    async def landing_sources(project_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/landings/projects/{project_id}/source-posts", timeout=60)).json()

    @app.get("/api/v1/landings/projects/{project_id}/pages")
    async def landing_pages(project_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/landings/projects/{project_id}/pages", timeout=60)).json()

    @app.post("/api/v1/landings/projects/{project_id}/pages", status_code=202)
    async def landing_create(project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("POST", f"/internal/v1/landings/projects/{project_id}/pages", body=request, actor=actor(identity), timeout=60)).json()

    @app.post("/api/v1/landings/projects/{project_id}/pages/variants", status_code=202)
    async def landing_variant(project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("POST", f"/internal/v1/landings/projects/{project_id}/pages/variants", body=request, actor=actor(identity), timeout=60)).json()

    @app.get("/api/v1/landings/projects/{project_id}/pages/{landing_id}")
    async def landing_detail(project_id: str, landing_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", landing_path(project_id, landing_id), timeout=60)).json()

    @app.post("/api/v1/landings/projects/{project_id}/pages/{landing_id}/retry", status_code=202)
    async def landing_retry(project_id: str, landing_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await landing_post(project_id, landing_id, "/retry", request, identity, timeout=60)

    @app.post("/api/v1/landings/projects/{project_id}/pages/{landing_id}/configuration")
    async def landing_configuration(project_id: str, landing_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await landing_post(project_id, landing_id, "/configuration", request, identity)

    @app.post("/api/v1/landings/projects/{project_id}/pages/{landing_id}/visuals/{slot}/generate")
    async def landing_visual_generate(project_id: str, landing_id: str, slot: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await landing_post(project_id, landing_id, f"/visuals/{slot}/generate", request, identity, timeout=480)

    @app.post("/api/v1/landings/projects/{project_id}/pages/{landing_id}/visuals/{slot}/select")
    async def landing_visual_select(project_id: str, landing_id: str, slot: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await landing_post(project_id, landing_id, f"/visuals/{slot}/select", request, identity)

    @app.get("/api/v1/landings/projects/{project_id}/pages/{landing_id}/visuals/{slot}/history/{sha256}")
    async def landing_visual_history(project_id: str, landing_id: str, slot: str, sha256: str, _identity: OwnerIdentity = Depends(owner)) -> Response:
        response = await validation_bridge("GET", landing_path(project_id, landing_id, f"/visuals/{slot}/history/{sha256}"), timeout=60)
        return Response(content=response.content, media_type=response.headers.get("content-type", "image/png"), headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", **({"ETag": response.headers["etag"]} if response.headers.get("etag") else {}), **({"X-PTW-Content-SHA256": response.headers["x-ptw-content-sha256"]} if response.headers.get("x-ptw-content-sha256") else {})})

    @app.post("/api/v1/landings/projects/{project_id}/pages/{landing_id}/save")
    async def landing_save(project_id: str, landing_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await landing_post(project_id, landing_id, "/save", request, identity, timeout=480)

    @app.post("/api/v1/landings/projects/{project_id}/pages/{landing_id}/approve")
    async def landing_approve(project_id: str, landing_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await landing_post(project_id, landing_id, "/approve", request, identity, timeout=480)

    @app.get("/api/v1/landings/projects/{project_id}/pages/{landing_id}/versions/{version}")
    async def landing_version(project_id: str, landing_id: str, version: int, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", landing_path(project_id, landing_id, f"/versions/{version}"), timeout=60)).json()

    @app.post("/api/v1/landings/projects/{project_id}/pages/{landing_id}/learning/{proposal_id}")
    async def landing_learning(project_id: str, landing_id: str, proposal_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await landing_post(project_id, landing_id, f"/learning/{proposal_id}", request, identity)

    @app.post("/api/v1/landings/projects/{project_id}/pages/{landing_id}/learning/{checkpoint_id}/retry")
    async def landing_learning_retry(project_id: str, landing_id: str, checkpoint_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await landing_post(project_id, landing_id, f"/learning/{checkpoint_id}/retry", request, identity, timeout=480)

    @app.get("/api/v1/system/health")
    async def system_health(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        try:
            response = await validation_bridge("GET", "/readyz", timeout=5)
            return {"gateway": "ok", "validation_service": response.json()}
        except HTTPException as error:
            return {"gateway": "ok", "validation_service": {"status": "unavailable", "detail": error.detail}}

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
