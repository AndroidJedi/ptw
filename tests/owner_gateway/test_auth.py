from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import unittest
from unittest.mock import AsyncMock, patch

from owner_gateway.settings import Settings

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
if HAS_FASTAPI:
    import httpx
    from fastapi.testclient import TestClient
    from fastapi import HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from owner_gateway.api import create_app
    from owner_gateway.auth import OwnerIdentity, validate_owner_claims
    from validation_pipeline.studio_routes import studio_creative_router


def settings() -> Settings:
    return Settings(
        firebase_project_id="provethemwrong-86123",
        firebase_app_id="firebase-app",
        owner_email="sgolovaschuk@gmail.com",
        owner_uid="owner-uid",
        service_account_path=None,
        validation_service_url="http://validation",
        validation_service_token="bridge",
        public_origin="https://example.test",
    )


@unittest.skipUnless(HAS_FASTAPI, "fastapi is required")
class OwnerClaimsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = settings()
        self.claims = {
            "uid": "owner-uid", "email": "sgolovaschuk@gmail.com", "email_verified": True,
            "firebase": {"sign_in_provider": "google.com"},
        }

    def test_exact_owner_is_allowed(self) -> None:
        identity = validate_owner_claims(self.settings, self.claims, {"app_id": "firebase-app"})
        self.assertEqual("owner-uid", identity.uid)

    def test_owner_origins_are_exact(self) -> None:
        class Verifier:
            def verify(self, _token: str, _app_check: str):  # pragma: no cover
                raise AssertionError

        configured = replace(
            self.settings,
            public_origin="https://provethemwrong-86123.firebaseapp.com",
            owner_public_origins=(
                "https://provethemwrong-86123.firebaseapp.com",
                "https://provethemwrong-86123.web.app",
            ),
        )
        middleware = next(
            item for item in create_app(configured, verifier=Verifier()).user_middleware if item.cls is CORSMiddleware
        )
        self.assertEqual([
            *configured.owner_public_origins, *configured.landing_public_origins,
        ], middleware.kwargs["allow_origins"])

    def test_every_private_api_route_keeps_owner_auth_and_public_routes_are_get_head_only(self) -> None:
        from owner_gateway.auth import OwnerDependency

        class Verifier:
            def verify(self, _token: str, _app_check: str):  # pragma: no cover
                raise AssertionError

        app = create_app(self.settings, verifier=Verifier())
        private_missing_auth = []
        public_methods = {}
        for route in app.routes:
            path = getattr(route, "path", "")
            if not path.startswith("/api/v1/"):
                continue
            methods = set(getattr(route, "methods", set()))
            if path.startswith(("/api/v1/public/landings/", "/api/v1/public/instagram-media/")):
                public_methods[path] = methods
                continue
            dependencies = getattr(getattr(route, "dependant", None), "dependencies", [])
            if not any(isinstance(getattr(item, "call", None), OwnerDependency) for item in dependencies):
                private_missing_auth.append(path)

        self.assertEqual([], private_missing_auth)
        self.assertTrue(public_methods)
        self.assertTrue(all(methods == {"GET", "HEAD"} for methods in public_methods.values()))

    def test_route_table_is_briefs_plus_project_scoped_post_and_landing_studio(self) -> None:
        class Verifier:
            def verify(self, _token: str, _app_check: str):  # pragma: no cover
                raise AssertionError

        paths = {route.path for route in create_app(self.settings, verifier=Verifier()).routes}
        creative = "/api/v1/studio/projects/{project_id}/creatives/{creative_id}"
        required = {
            "/api/v1/projects", "/api/v1/projects/{project_id}/briefs", "/api/v1/briefs",
            "/api/v1/settings/chatgpt-authorization",
            "/api/v1/settings/chatgpt-authorization/refresh",
            "/api/v1/settings/commander",
            "/api/v1/settings/commander/chats",
            "/api/v1/settings/commander/chats/{chat_id}",
            "/api/v1/settings/commander/chats/{chat_id}/messages",
            "/api/v1/settings/commander/chats/{chat_id}/turns/{turn_id}/attachments/{attachment_id}",
            "/api/v1/settings/commander/chats/{chat_id}/turns/{turn_id}/stop",
            "/api/v1/settings/commander/deployments",
            "/api/v1/studio/templates",
            "/api/v1/studio/projects/{project_id}/creatives", creative,
            f"{creative}/retry", f"{creative}/creative-direction",
            f"{creative}/configuration", f"{creative}/save",
            f"{creative}/templates/apply", f"{creative}/assets/{{slot}}",
            f"{creative}/pexels", f"{creative}/phone-screen/generate",
            f"{creative}/phone-screen/retry", f"{creative}/phone-screen/select",
            f"{creative}/phone-screen/history/{{sha256}}", f"{creative}/preview",
            f"{creative}/component-settings", f"{creative}/versions/{{version}}/render",
            f"{creative}/versions/{{version}}", f"{creative}/approve",
            f"{creative}/learning/{{proposal_id}}",
            f"{creative}/checkpoints/{{checkpoint_id}}/retry",
            "/api/v1/landings/projects/{project_id}/source-posts",
            "/api/v1/landings/projects/{project_id}/pages",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}",
            "/api/v1/landings/projects/{project_id}/pages/variants",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/retry",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/configuration",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/visuals/{slot}/generate",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/visuals/{slot}/select",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/visuals/{slot}/history/{sha256}",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/save",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/approve",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/versions/{version}",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/learning/{proposal_id}",
            "/api/v1/landings/projects/{project_id}/pages/{landing_id}/learning/{checkpoint_id}/retry",
            "/api/v1/landings/projects/{project_id}/publication",
            "/api/v1/landings/projects/{project_id}/publication/availability",
            "/api/v1/landings/projects/{project_id}/publication/publish",
            "/api/v1/landings/projects/{project_id}/publication/unpublish",
            "/api/v1/public/landings/{namespace}/{slug}",
            "/api/v1/public/landings/{namespace}/{slug}/versions/{version_sha256}/assets/{slot}/{sha256}.png",
            "/api/v1/ads/connection", "/api/v1/ads/presets", "/api/v1/ads/locations",
            "/api/v1/ads/projects/{project_id}",
            "/api/v1/ads/projects/{project_id}/deployments",
            "/api/v1/ads/projects/{project_id}/deployments/{deployment_id}/retry",
            "/api/v1/ads/projects/{project_id}/deployments/{deployment_id}/sync",
        }
        self.assertTrue(required <= paths)
        self.assertNotIn("/api/v1/studio", paths)
        self.assertNotIn("/api/v1/studio/configuration", paths)
        self.assertNotIn("/api/v1/project-assets", paths)
        self.assertNotIn("/api/v1/project-brand-kits", paths)
        self.assertFalse([path for path in paths if "/content-runs" in path])
        forbidden_fragments = ("ad-batches", "ad-creatives", "ad-studio", "campaign")
        self.assertFalse([
            path for path in paths if any(fragment in path for fragment in forbidden_fragments)
        ])

    def test_commander_routes_require_owner_and_forward_only_to_private_runtime(self) -> None:
        class Verifier:
            def verify(self, token: str, app_check_token: str) -> OwnerIdentity:
                if token != "owner-token" or app_check_token != "app-token":
                    raise AssertionError("gateway did not verify both owner credentials")
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")

        configured = replace(self.settings, commander_service_url="http://commander-god:8095")
        chat_id = "01900000-0000-7000-8000-000000000001"
        payload = {"message": "Fix Settings", "request_id": "01900000-0000-7000-8000-000000000002"}
        upstream = httpx.Response(
            202, json={"id": chat_id, "turns": []},
            request=httpx.Request("POST", "http://commander-god:8095/internal/v1/settings/commander"),
        )
        forwarded = AsyncMock(return_value=upstream)
        path = f"/api/v1/settings/commander/chats/{chat_id}/messages"
        headers = {"Authorization": "Bearer owner-token", "X-Firebase-AppCheck": "app-token"}
        with patch("httpx.AsyncClient.request", forwarded), TestClient(create_app(configured, verifier=Verifier())) as client:
            self.assertEqual(401, client.post(path, json=payload).status_code)
            response = client.post(path, headers=headers, json=payload)
        self.assertEqual(202, response.status_code)
        self.assertEqual("private, no-store", response.headers["cache-control"])
        forwarded.assert_awaited_once_with(
            "POST",
            f"http://commander-god:8095/internal/v1/settings/commander/chats/{chat_id}/messages",
            headers={"X-PTW-Owner-Gateway-Token": "bridge"},
            json=payload,
        )

    def test_mobile_deployment_requires_owner_and_forwards_exact_confirmation(self) -> None:
        class Verifier:
            def verify(self, token: str, app_check_token: str) -> OwnerIdentity:
                if token != "owner-token" or app_check_token != "app-token":
                    raise AssertionError("gateway did not verify both owner credentials")
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")

        configured = replace(self.settings, commander_release_url="http://commander-release:8096")
        payload = {"request_id": "01900000-0000-7000-8000-000000000002"}
        upstream = httpx.Response(
            202, json={"candidate": {"changed_files": []}, "deployment": {"status": "queued"}},
            request=httpx.Request("POST", "http://commander-release:8096/internal/v1/settings/commander/deployments"),
        )
        forwarded = AsyncMock(return_value=upstream)
        path = "/api/v1/settings/commander/deployments"
        headers = {"Authorization": "Bearer owner-token", "X-Firebase-AppCheck": "app-token"}
        with patch("httpx.AsyncClient.request", forwarded), TestClient(create_app(configured, verifier=Verifier())) as client:
            self.assertEqual(401, client.post(path, json=payload).status_code)
            response = client.post(path, headers=headers, json=payload)
        self.assertEqual(202, response.status_code)
        self.assertEqual("private, no-store", response.headers["cache-control"])
        forwarded.assert_awaited_once_with(
            "POST", "http://commander-release:8096/internal/v1/settings/commander/deployments",
            headers={"X-PTW-Owner-Gateway-Token": "bridge"}, json=payload, params=None,
        )

    def test_commander_image_requires_owner_and_verifies_private_upstream_bytes(self) -> None:
        class Verifier:
            def verify(self, token: str, app_check_token: str) -> OwnerIdentity:
                if token != "owner-token" or app_check_token != "app-token":
                    raise AssertionError("gateway did not verify both owner credentials")
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")

        configured = replace(self.settings, commander_service_url="http://commander-god:8095")
        data = b"private-normalized-png"
        digest = hashlib.sha256(data).hexdigest()
        upstream = httpx.Response(
            200, content=data, headers={"Content-Type": "image/png", "X-PTW-Content-SHA256": digest},
            request=httpx.Request("GET", "http://commander-god:8095/internal/v1/settings/commander/image"),
        )
        forwarded = AsyncMock(return_value=upstream)
        chat_id = "01900000-0000-7000-8000-000000000001"
        turn_id = "01900000-0000-7000-8000-000000000002"
        path = f"/api/v1/settings/commander/chats/{chat_id}/turns/{turn_id}/attachments/image-1"
        headers = {"Authorization": "Bearer owner-token", "X-Firebase-AppCheck": "app-token"}
        with patch("httpx.AsyncClient.get", forwarded), TestClient(create_app(configured, verifier=Verifier())) as client:
            self.assertEqual(401, client.get(path).status_code)
            response = client.get(path, headers=headers)
        self.assertEqual(data, response.content)
        self.assertEqual("private, no-store", response.headers["cache-control"])
        self.assertEqual(digest, response.headers["x-ptw-content-sha256"])
        forwarded.assert_awaited_once_with(
            f"http://commander-god:8095/internal/v1/settings/commander/chats/{chat_id}/turns/{turn_id}/attachments/image-1",
            headers={"X-PTW-Owner-Gateway-Token": "bridge"},
        )

    def test_gateway_and_validation_studio_routes_have_exact_method_parity(self) -> None:
        class Verifier:
            def verify(self, _token: str, _app_check: str):  # pragma: no cover
                raise AssertionError

        def contract(routes, prefix: str) -> set[tuple[str, str]]:
            return {
                (method, route.path.replace(prefix, "", 1))
                for route in routes
                if getattr(route, "path", "").startswith(prefix)
                for method in set(getattr(route, "methods", set())) & {"GET", "POST"}
            }

        gateway = create_app(self.settings, verifier=Verifier())
        validation = studio_creative_router(
            object(), prefix="/internal/v1/studio",
        )
        self.assertEqual(
            contract(validation.routes, "/internal/v1/studio"),
            contract(gateway.routes, "/api/v1/studio"),
        )

    def test_image_references_cross_both_authenticated_gateway_routes_unchanged(self):
        from tests.validation_pipeline.test_image_reference import upload
        class Verifier:
            def verify(self, token, app_check_token):
                self_identity = OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")
                return self_identity
        payload = {"base_sha256": "a" * 64, "visual_direction": "Keep the object, change the background", "reference_image": upload()}
        paths = ["/api/v1/studio/projects/project/creatives/creative/phone-screen/generate",
                 "/api/v1/landings/projects/project/pages/page/visuals/hero_visual/generate",
                 "/api/v1/landings/projects/project/pages/page/visuals/visual_break_visual/generate"]
        for path in paths:
            upstream = httpx.Response(200, json={"state_sha256": "b" * 64}, request=httpx.Request("POST", "http://validation"))
            forwarded = AsyncMock(return_value=upstream)
            with patch("httpx.AsyncClient.request", forwarded), TestClient(create_app(self.settings, verifier=Verifier())) as client:
                self.assertEqual(401, client.post(path, json=payload).status_code)
                result = client.post(path, json=payload, headers={"Authorization": "Bearer test", "X-Firebase-AppCheck": "test"})
            self.assertEqual(200, result.status_code)
            self.assertEqual(payload, forwarded.call_args.kwargs["json"])
            self.assertEqual("firebase:owner-uid", forwarded.call_args.kwargs["headers"]["X-PTW-Actor"])
            self.assertNotIn("reference_image", result.json())

    def test_instagram_routes_match_validation_and_forward_owner_and_media_boundaries(self):
        from validation_pipeline.instagram_publication_routes import instagram_router, instagram_media_router
        class Verifier:
            def verify(self, token, app_check_token):
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")
        gateway = create_app(self.settings, verifier=Verifier())
        def routes(items, prefix):
            return {(method, route.path.replace(prefix, "", 1)) for route in items
                    if getattr(route, "path", "").startswith(prefix) for method in route.methods}
        self.assertEqual(routes(gateway.routes, "/api/v1/instagram"),
                         routes(instagram_router(object(), prefix="/internal/v1/instagram").routes, "/internal/v1/instagram"))
        self.assertEqual(routes(gateway.routes, "/api/v1/public/instagram-media"),
                         routes(instagram_media_router(object(), prefix="/internal/v1/public/instagram-media").routes, "/internal/v1/public/instagram-media"))
        payload = {"request_id": "request", "creative_id": "creative", "version": 2, "caption": "Reviewed"}
        forwarded = AsyncMock(return_value=httpx.Response(202, json={"publication": {"publication_id": "pub"}}))
        path = "/api/v1/instagram/projects/project/publications"
        with patch("httpx.AsyncClient.request", forwarded), TestClient(gateway) as client:
            self.assertEqual(401, client.post(path, json=payload).status_code)
            self.assertEqual(202, client.post(path, json=payload, headers={"Authorization":"Bearer test", "X-Firebase-AppCheck":"test"}).status_code)
        self.assertEqual(payload, forwarded.call_args.kwargs["json"])
        self.assertEqual("firebase:owner-uid", forwarded.call_args.kwargs["headers"]["X-PTW-Actor"])
        forwarded = AsyncMock(return_value=httpx.Response(200, content=b"jpeg"))
        path = "/api/v1/public/instagram-media/" + "a" * 43 + ".jpg"
        with patch("httpx.AsyncClient.request", forwarded), TestClient(gateway) as client:
            response = client.get(path)
            self.assertEqual(200, response.status_code)
            self.assertEqual("no-store", response.headers["cache-control"])
            self.assertEqual("image/jpeg", response.headers["content-type"])
            self.assertEqual(405, client.post(path, json={}).status_code)
            self.assertEqual(404, client.get("/api/v1/public/instagram-media/bad.jpg").status_code)
        self.assertEqual("bridge", forwarded.call_args.kwargs["headers"]["X-PTW-Owner-Gateway-Token"])

    def test_creative_direction_crosses_authenticated_gateway_with_exact_contract(self) -> None:
        class Verifier:
            def verify(self, token: str, app_check_token: str) -> OwnerIdentity:
                if token != "owner-token" or app_check_token != "app-token":
                    raise AssertionError("gateway did not verify both owner credentials")
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")

        project_id = "01900000-0000-7000-8000-000000000001"
        creative_id = "01900000-0000-7000-8000-000000000002"
        path = f"/api/v1/studio/projects/{project_id}/creatives/{creative_id}/creative-direction"
        payload = {
            "base_sha256": "a" * 64,
            "creative_direction": {
                "schema": "ptw.studio.phone-hero-direction.v1",
                "style": "minimal_sculptural",
                "background": "isolated_key_element",
            },
        }
        upstream = httpx.Response(
            200,
            json={
                "creative_id": creative_id, "project_id": project_id,
                "state_sha256": "a" * 64,
                "generation": {"creative_direction": payload["creative_direction"]},
            },
            request=httpx.Request("POST", f"http://validation/internal{path[4:]}"),
        )
        request = AsyncMock(return_value=upstream)
        headers = {
            "Authorization": "Bearer owner-token",
            "X-Firebase-AppCheck": "app-token",
        }
        with patch("httpx.AsyncClient.request", request):
            with TestClient(create_app(self.settings, verifier=Verifier())) as client:
                missing_auth = client.post(path, json=payload)
                response = client.post(path, headers=headers, json=payload)

        self.assertEqual(401, missing_auth.status_code)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(payload["creative_direction"], response.json()["generation"]["creative_direction"])
        request.assert_awaited_once_with(
            "POST",
            f"http://validation/internal/v1/studio/projects/{project_id}/creatives/{creative_id}/creative-direction",
            headers={
                "X-PTW-Owner-Gateway-Token": "bridge",
                "X-PTW-Actor": "firebase:owner-uid",
            },
            json=payload,
            params={},
        )

    def test_wrong_owner_or_app_is_denied(self) -> None:
        with self.assertRaises(HTTPException):
            validate_owner_claims(
                self.settings, {**self.claims, "email": "other@example.com"},
                {"app_id": "firebase-app"},
            )
        with self.assertRaises(HTTPException):
            validate_owner_claims(self.settings, self.claims, {"app_id": "wrong"})

    def test_public_snapshot_needs_no_owner_token_but_private_routes_still_do(self) -> None:
        class Verifier:
            def verify(self, _token: str, _app_check: str):  # pragma: no cover
                raise AssertionError

        upstream = httpx.Response(
            200,
            json={"schema": "ptw.public-landing.v1", "canonical_url": "https://natal-service.com/ai/example"},
            request=httpx.Request("GET", "http://validation/internal/v1/public/landings/ai/example"),
        )
        request = AsyncMock(return_value=upstream)
        with patch("httpx.AsyncClient.request", request):
            with TestClient(create_app(self.settings, verifier=Verifier())) as client:
                public = client.get("/api/v1/public/landings/ai/example")
                public_head = client.head("/api/v1/public/landings/ai/example")
                private = client.get("/api/v1/projects")
                public_write = client.post("/api/v1/public/landings/ai/example")

        self.assertEqual(200, public.status_code)
        self.assertEqual("no-store", public.headers["cache-control"])
        self.assertEqual(200, public_head.status_code)
        self.assertEqual(401, private.status_code)
        self.assertEqual(405, public_write.status_code)
