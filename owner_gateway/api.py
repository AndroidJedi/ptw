"""Firebase-authenticated owner API for Product Briefs and Universal Ad Studio."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping
from uuid import UUID

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
        allow_origins=list(dict.fromkeys([
            settings.public_origin, *settings.owner_public_origins,
            *settings.landing_public_origins,
        ])),
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "POST"],
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

    async def commander_bridge(
        method: str, path: str, *, body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not settings.commander_service_url:
            raise HTTPException(status_code=503, detail="Commander hosted runtime is unavailable")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method,
                    f"{settings.commander_service_url}/internal/v1/settings/commander{path}",
                    headers={"X-PTW-Owner-Gateway-Token": settings.validation_service_token},
                    json=None if body is None else dict(body),
                )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=503, detail="Commander hosted runtime is unavailable") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(
                status_code=response.status_code,
                detail=detail or "Commander hosted runtime request failed",
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise HTTPException(status_code=503, detail="Commander hosted runtime is unavailable") from error
        if not isinstance(payload, dict):
            raise HTTPException(status_code=503, detail="Commander hosted runtime is unavailable")
        return payload

    async def commander_attachment_bridge(path: str) -> tuple[bytes, str]:
        if not settings.commander_service_url:
            raise HTTPException(status_code=503, detail="Commander hosted runtime is unavailable")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                upstream = await client.get(
                    f"{settings.commander_service_url}/internal/v1/settings/commander{path}",
                    headers={"X-PTW-Owner-Gateway-Token": settings.validation_service_token},
                )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=503, detail="Commander hosted runtime is unavailable") from error
        if upstream.status_code >= 400:
            raise HTTPException(status_code=upstream.status_code, detail="Commander conversation image is unavailable")
        content_type = upstream.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        digest = upstream.headers.get("x-ptw-content-sha256", "").lower()
        data = upstream.content
        if (
            content_type != "image/png" or len(data) > 8 * 1024 * 1024
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or hashlib.sha256(data).hexdigest() != digest
        ):
            raise HTTPException(status_code=502, detail="Commander conversation image failed its integrity check")
        return data, digest

    async def commander_release_bridge(
        method: str, *, body: Mapping[str, Any] | None = None, chat_id: UUID | None = None,
    ) -> dict[str, Any]:
        if not settings.commander_release_url:
            raise HTTPException(status_code=503, detail="Commander mobile deployment is unavailable")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method,
                    f"{settings.commander_release_url}/internal/v1/settings/commander/deployments",
                    headers={"X-PTW-Owner-Gateway-Token": settings.validation_service_token},
                    json=None if body is None else dict(body),
                    params={"chat_id": str(chat_id)} if chat_id else None,
                )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=503, detail="Commander mobile deployment is unavailable") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            raise HTTPException(response.status_code, detail or "Commander deployment request failed")
        try:
            payload = response.json()
        except ValueError as error:
            raise HTTPException(status_code=503, detail="Commander mobile deployment is unavailable") from error
        if not isinstance(payload, dict):
            raise HTTPException(status_code=503, detail="Commander mobile deployment is unavailable")
        return payload

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

    @app.get("/api/v1/settings/commander")
    async def commander_status(
        response: Response, _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("GET", "")

    @app.post("/api/v1/settings/commander/chats", status_code=201)
    async def create_commander_chat(
        response: Response, _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("POST", "/chats", body={})

    @app.get("/api/v1/settings/commander/chats/{chat_id}")
    async def commander_chat(
        chat_id: UUID, response: Response, before: int | None = None, _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("GET", f"/chats/{chat_id}" + (f"?before={before}" if before is not None else ""))

    @app.get("/api/v1/settings/commander/capabilities")
    async def commander_capabilities(response: Response, _identity: OwnerIdentity = Depends(owner)):
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("GET", "/capabilities")

    @app.get("/api/v1/settings/commander/chats/{chat_id}/events")
    async def commander_events(chat_id: UUID, response: Response, after: int = 0, _identity: OwnerIdentity = Depends(owner)):
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("GET", f"/chats/{chat_id}/events?after={max(0, after)}")

    @app.post("/api/v1/settings/commander/chats/{chat_id}/preferences")
    async def commander_preferences(chat_id: UUID, request: Mapping[str, Any], response: Response, _identity: OwnerIdentity = Depends(owner)):
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("POST", f"/chats/{chat_id}/preferences", body=request)

    @app.post("/api/v1/settings/commander/chats/{chat_id}/deploy", status_code=202)
    async def commander_deploy_action(chat_id: UUID, request: Mapping[str, Any], response: Response, _identity: OwnerIdentity = Depends(owner)):
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("POST", f"/chats/{chat_id}/deploy", body=request)

    @app.post("/api/v1/settings/commander/chats/{chat_id}/questions/{question_id}/answers")
    async def commander_answer(chat_id: UUID, question_id: UUID, request: Mapping[str, Any], response: Response, _identity: OwnerIdentity = Depends(owner)):
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("POST", f"/chats/{chat_id}/questions/{question_id}/answers", body=request)

    @app.post("/api/v1/settings/commander/chats/{chat_id}/messages", status_code=202)
    async def send_commander_message(
        chat_id: UUID, request: Mapping[str, Any], response: Response,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("POST", f"/chats/{chat_id}/messages", body=request)

    @app.get("/api/v1/settings/commander/chats/{chat_id}/turns/{turn_id}/attachments/{attachment_id}")
    async def commander_attachment(
        chat_id: UUID, turn_id: UUID, attachment_id: str,
        _identity: OwnerIdentity = Depends(owner),
    ) -> Response:
        data, digest = await commander_attachment_bridge(
            f"/chats/{chat_id}/turns/{turn_id}/attachments/{attachment_id}"
        )
        return Response(
            content=data, media_type="image/png",
            headers={
                "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                "X-PTW-Content-SHA256": digest, "ETag": f'"{digest}"',
            },
        )

    @app.post(
        "/api/v1/settings/commander/chats/{chat_id}/turns/{turn_id}/stop",
        status_code=202,
    )
    async def stop_commander_turn(
        chat_id: UUID, turn_id: UUID, response: Response,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_bridge("POST", f"/chats/{chat_id}/turns/{turn_id}/stop", body={})

    @app.get("/api/v1/settings/commander/deployments")
    async def commander_deployment(
        response: Response, chat_id: UUID | None = None, _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_release_bridge("GET", chat_id=chat_id)

    @app.post("/api/v1/settings/commander/deployments", status_code=202)
    async def deploy_commander_changes(
        request: Mapping[str, Any], response: Response,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "private, no-store"
        return await commander_release_bridge("POST", body=request)

    @app.get("/api/v1/projects")
    async def projects(
        limit: int = Query(default=100, ge=1, le=100),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge("GET", "/internal/v1/projects", params={"limit": limit})).json()

    @app.post("/api/v1/projects")
    async def create_project(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", "/internal/v1/projects", body=request, actor=actor(identity)
        )).json()

    @app.post("/api/v1/projects/{project_id}/rename")
    async def rename_project(
        project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/projects/{project_id}/rename", body=request, actor=actor(identity)
        )).json()

    @app.post("/api/v1/projects/{project_id}/briefs", status_code=202)
    async def create_brief(
        project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/projects/{project_id}/briefs",
            body=request, actor=actor(identity),
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

    @app.post("/api/v1/studio/projects/{project_id}/creatives/{creative_id}/creative-direction")
    async def studio_creative_direction(project_id: str, creative_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return await creative_post(project_id, creative_id, "/creative-direction", request, identity, timeout=60)

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

    @app.get("/api/v1/landings/projects/{project_id}/publication")
    async def landing_publication(project_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/landings/projects/{project_id}/publication", timeout=60,
        )).json()

    @app.get("/api/v1/landings/projects/{project_id}/publication/availability")
    async def landing_publication_availability(
        project_id: str, namespace: str, slug: str,
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/landings/projects/{project_id}/publication/availability",
            params={"namespace": namespace, "slug": slug}, timeout=60,
        )).json()

    @app.post("/api/v1/landings/projects/{project_id}/publication/publish")
    async def landing_publish(
        project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/landings/projects/{project_id}/publication/publish",
            body=request, actor=actor(identity), timeout=60,
        )).json()

    @app.post("/api/v1/landings/projects/{project_id}/publication/unpublish")
    async def landing_unpublish(
        project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/landings/projects/{project_id}/publication/unpublish",
            body=request, actor=actor(identity), timeout=60,
        )).json()

    @app.api_route("/api/v1/public/landings/{namespace}/{slug}", methods=["GET", "HEAD"])
    async def public_landing(namespace: str, slug: str) -> Response:
        response = await validation_bridge(
            "GET", f"/internal/v1/public/landings/{namespace}/{slug}", timeout=60,
        )
        return Response(
            content=response.content,
            media_type=response.headers.get("content-type", "application/json"),
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.api_route("/api/v1/public/landings/{namespace}/{slug}/versions/{version_sha256}/assets/{slot}/{sha256}.png", methods=["GET", "HEAD"])
    async def public_landing_asset(
        namespace: str, slug: str, version_sha256: str, slot: str, sha256: str,
    ) -> Response:
        response = await validation_bridge(
            "GET", f"/internal/v1/public/landings/{namespace}/{slug}/versions/{version_sha256}/assets/{slot}/{sha256}.png",
            timeout=60,
        )
        return Response(
            content=response.content, media_type=response.headers.get("content-type", "image/png"),
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Content-Type-Options": "nosniff",
                **({"ETag": response.headers["etag"]} if response.headers.get("etag") else {}),
            },
        )

    @app.get("/api/v1/instagram/connection")
    async def instagram_connection(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", "/internal/v1/instagram/connection", timeout=120)).json()

    @app.get("/api/v1/instagram/projects/{project_id}")
    async def instagram_workspace(project_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/instagram/projects/{project_id}", timeout=60)).json()

    @app.get("/api/v1/instagram/projects/{project_id}/publications")
    async def instagram_publications(project_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/instagram/projects/{project_id}/publications", timeout=60)).json()

    @app.get("/api/v1/instagram/projects/{project_id}/publications/{publication_id}")
    async def instagram_publication(project_id: str, publication_id: str, _identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", f"/internal/v1/instagram/projects/{project_id}/publications/{publication_id}", timeout=60)).json()

    @app.post("/api/v1/instagram/projects/{project_id}/publications", status_code=202)
    async def instagram_publish(project_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("POST", f"/internal/v1/instagram/projects/{project_id}/publications", body=request, actor=actor(identity), timeout=120)).json()

    @app.post("/api/v1/instagram/projects/{project_id}/publications/{publication_id}/retry", status_code=202)
    async def instagram_retry(project_id: str, publication_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("POST", f"/internal/v1/instagram/projects/{project_id}/publications/{publication_id}/retry", body=request, actor=actor(identity), timeout=60)).json()

    @app.post("/api/v1/instagram/projects/{project_id}/publications/{publication_id}/sync")
    async def instagram_sync(project_id: str, publication_id: str, request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("POST", f"/internal/v1/instagram/projects/{project_id}/publications/{publication_id}/sync", body=request, actor=actor(identity), timeout=60)).json()

    @app.api_route("/api/v1/public/instagram-media/{token}.jpg", methods=["GET", "HEAD"])
    async def instagram_media(token: str) -> Response:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise HTTPException(404, "Media unavailable")
        response = await validation_bridge("GET", f"/internal/v1/public/instagram-media/{token}.jpg", timeout=60)
        return Response(response.content, media_type="image/jpeg", headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-Robots-Tag": "noindex, noarchive",
        })

    @app.get("/api/v1/ads/connection")
    async def meta_ads_connection(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", "/internal/v1/ads/connection", timeout=120)).json()

    @app.get("/api/v1/ads/presets")
    async def meta_ads_presets(_identity: OwnerIdentity = Depends(owner)) -> dict[str, Any]:
        return (await validation_bridge("GET", "/internal/v1/ads/presets", timeout=60)).json()

    @app.get("/api/v1/ads/locations")
    async def meta_ads_locations(
        query: str = Query(min_length=2, max_length=80),
        country_code: str = Query(min_length=2, max_length=2),
        _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", "/internal/v1/ads/locations",
            params={"query": query, "country_code": country_code}, timeout=60,
        )).json()

    @app.post("/api/v1/ads/presets", status_code=201)
    async def meta_ads_create_preset(
        request: Mapping[str, Any], identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", "/internal/v1/ads/presets", body=request,
            actor=actor(identity), timeout=60,
        )).json()

    @app.get("/api/v1/ads/projects/{project_id}")
    async def meta_ads_workspace(
        project_id: str, _identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "GET", f"/internal/v1/ads/projects/{project_id}", timeout=60,
        )).json()

    @app.post("/api/v1/ads/projects/{project_id}/deployments", status_code=202)
    async def meta_ads_deploy(
        project_id: str, request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/ads/projects/{project_id}/deployments",
            body=request, actor=actor(identity), timeout=120,
        )).json()

    @app.post("/api/v1/ads/projects/{project_id}/deployments/{deployment_id}/retry", status_code=202)
    async def meta_ads_retry(
        project_id: str, deployment_id: str, request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/ads/projects/{project_id}/deployments/{deployment_id}/retry",
            body=request, actor=actor(identity), timeout=60,
        )).json()

    @app.post("/api/v1/ads/projects/{project_id}/deployments/{deployment_id}/sync")
    async def meta_ads_sync(
        project_id: str, deployment_id: str, request: Mapping[str, Any],
        identity: OwnerIdentity = Depends(owner),
    ) -> dict[str, Any]:
        return (await validation_bridge(
            "POST", f"/internal/v1/ads/projects/{project_id}/deployments/{deployment_id}/sync",
            body=request, actor=actor(identity), timeout=60,
        )).json()

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
