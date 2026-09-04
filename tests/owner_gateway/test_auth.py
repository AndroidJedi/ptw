from __future__ import annotations

from dataclasses import replace
import importlib.util
import unittest

from owner_gateway.settings import Settings

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
if HAS_FASTAPI:
    from fastapi import HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from owner_gateway.api import create_app
    from owner_gateway.auth import validate_owner_claims


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
        configured = replace(
            self.settings,
            public_origin="https://provethemwrong-86123.firebaseapp.com",
            owner_public_origins=(
                "https://provethemwrong-86123.firebaseapp.com",
                "https://provethemwrong-86123.web.app",
            ),
        )
        middleware = next(
            item for item in create_app(configured).user_middleware if item.cls is CORSMiddleware
        )
        self.assertEqual(list(configured.owner_public_origins), middleware.kwargs["allow_origins"])

    def test_route_table_is_briefs_plus_owner_universal_studio(self) -> None:
        class Verifier:
            def verify(self, _token: str, _app_check: str):  # pragma: no cover
                raise AssertionError

        paths = {route.path for route in create_app(self.settings, verifier=Verifier()).routes}
        required = {
            "/api/v1/projects", "/api/v1/briefs",
            "/api/v1/studio",
            "/api/v1/studio/configuration",
            "/api/v1/studio/templates/apply",
            "/api/v1/studio/assets/{slot}",
            "/api/v1/studio/pexels",
            "/api/v1/studio/phone-screen/generate",
            "/api/v1/studio/phone-screen/select",
            "/api/v1/studio/phone-screen/history/{sha256}",
            "/api/v1/studio/preview",
            "/api/v1/studio/component-settings",
            "/api/v1/studio/versions/{version}/render",
            "/api/v1/studio/versions/{version}",
            "/api/v1/studio/approve",
        }
        self.assertTrue(required <= paths)
        self.assertNotIn("/api/v1/project-assets", paths)
        self.assertNotIn("/api/v1/project-brand-kits", paths)
        self.assertFalse([path for path in paths if "/content-runs" in path])
        forbidden_fragments = ("ad-batches", "ad-creatives", "ad-studio", "landing", "publish", "campaign")
        self.assertFalse([
            path for path in paths if any(fragment in path for fragment in forbidden_fragments)
        ])

    def test_wrong_owner_or_app_is_denied(self) -> None:
        with self.assertRaises(HTTPException):
            validate_owner_claims(
                self.settings, {**self.claims, "email": "other@example.com"},
                {"app_id": "firebase-app"},
            )
        with self.assertRaises(HTTPException):
            validate_owner_claims(self.settings, self.claims, {"app_id": "wrong"})
