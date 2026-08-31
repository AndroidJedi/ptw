from __future__ import annotations

from dataclasses import replace
import importlib.util
import unittest

from owner_gateway.settings import Settings

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
if HAS_FASTAPI:
    from fastapi import HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from owner_gateway.api import (
        INSTAGRAM_TASK, TIKTOK_TASK, create_app, instagram_run_request, social_run_request,
    )
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

    def test_route_table_is_result_plus_owner_universal_studio(self) -> None:
        class Verifier:
            def verify(self, _token: str, _app_check: str):  # pragma: no cover
                raise AssertionError

        paths = {route.path for route in create_app(self.settings, verifier=Verifier()).routes}
        required = {
            "/api/v1/projects", "/api/v1/briefs", "/api/v1/content-runs",
            "/api/v1/content-runs/{run_id}/result",
            "/api/v1/content-runs/{run_id}/candidates/{candidate_id}/asset",
            "/api/v1/content-runs/{run_id}/feedback",
            "/api/v1/content-runs/{run_id}/revisions",
            "/api/v1/studio",
            "/api/v1/studio/configuration",
            "/api/v1/studio/assets/{slot}",
            "/api/v1/studio/pexels",
            "/api/v1/studio/preview",
            "/api/v1/studio/versions/{version}/render",
            "/api/v1/studio/approve",
        }
        self.assertTrue(required <= paths)
        self.assertNotIn("/api/v1/project-assets", paths)
        self.assertNotIn("/api/v1/project-brand-kits", paths)
        self.assertFalse([path for path in paths if "/studio/templates" in path])
        forbidden_fragments = ("ad-batches", "ad-creatives", "ad-studio", "landing", "publish", "campaign")
        self.assertFalse([
            path for path in paths if any(fragment in path for fragment in forbidden_fragments)
        ])

    def test_public_social_input_maps_platform_to_server_owned_contract(self) -> None:
        value = instagram_run_request({"request_id": "request", "brief_id": "brief"})
        self.assertEqual({
            "request_id": "request", "brief_id": "brief",
            "task": INSTAGRAM_TASK, "output_profile": "instagram_static_ad_v1",
        }, value)
        with self.assertRaisesRegex(ValueError, "only request_id and brief_id"):
            instagram_run_request({
                "request_id": "request", "brief_id": "brief",
                "task": "owner supplied", "output_profile": "marketing_copy_v1",
            })
        self.assertEqual({
            "request_id": "request", "brief_id": "brief",
            "task": INSTAGRAM_TASK, "output_profile": "instagram_static_ad_v1",
        }, social_run_request({"request_id": "request", "brief_id": "brief"}))
        self.assertEqual({
            "request_id": "request", "brief_id": "brief",
            "task": TIKTOK_TASK, "output_profile": "tiktok_photo_post_v1",
        }, social_run_request({
            "request_id": "request", "brief_id": "brief", "platform": "tiktok",
        }))
        with self.assertRaisesRegex(ValueError, "optional platform"):
            social_run_request({
                "request_id": "request", "brief_id": "brief", "platform": "instagram",
                "task": "client injection",
            })
        with self.assertRaisesRegex(ValueError, "instagram or tiktok"):
            social_run_request({
                "request_id": "request", "brief_id": "brief", "platform": "youtube",
            })
        with self.assertRaisesRegex(ValueError, "instagram or tiktok"):
            social_run_request({
                "request_id": "request", "brief_id": "brief", "platform": None,
            })

    def test_wrong_owner_or_app_is_denied(self) -> None:
        with self.assertRaises(HTTPException):
            validate_owner_claims(
                self.settings, {**self.claims, "email": "other@example.com"},
                {"app_id": "firebase-app"},
            )
        with self.assertRaises(HTTPException):
            validate_owner_claims(self.settings, self.claims, {"app_id": "wrong"})
