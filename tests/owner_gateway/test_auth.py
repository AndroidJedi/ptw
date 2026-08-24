from __future__ import annotations

import tempfile
import unittest
import importlib.util
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

from owner_gateway.settings import Settings

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
if HAS_FASTAPI:
    from fastapi import HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from owner_gateway.auth import validate_owner_claims
    from owner_gateway.api import create_app


def settings(root: Path) -> Settings:
    return Settings(
        firebase_project_id="provethemwrong-86123", firebase_app_id="firebase-app",
        owner_email="sgolovaschuk@gmail.com",
        owner_uid="owner-uid", service_account_path=None,
        validation_database_url="postgres://validation",
        validation_service_url="http://validation", validation_service_token="bridge",
        commander_database_url="postgres://commander",
        platform_database_url="postgres://platform", platform_owner_telegram_id=1, owner_chat_id=1,
        telegram_allowed_chat_ids=frozenset({1}),
        control_database_path=root / "control.sqlite3", repository_path=root,
        codex_executable="codex", root_broker_socket=root / "root.sock",
        public_origin="https://example.test",
    )


@unittest.skipUnless(HAS_FASTAPI, "fastapi is required")
class OwnerClaimsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.settings = settings(Path(self.temp.name))
        self.claims = {
            "uid": "owner-uid", "email": "sgolovaschuk@gmail.com", "email_verified": True,
            "firebase": {"sign_in_provider": "google.com"},
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_exact_owner_is_allowed(self) -> None:
        identity = validate_owner_claims(self.settings, self.claims, {"app_id": "firebase-app"})
        self.assertEqual("owner-uid", identity.uid)

    def test_both_code_owned_owner_hostnames_are_cors_origins(self) -> None:
        firebaseapp = "https://provethemwrong-86123.firebaseapp.com"
        webapp = "https://provethemwrong-86123.web.app"
        configured = replace(
            self.settings,
            public_origin=firebaseapp,
            owner_public_origins=(firebaseapp, webapp),
        )
        middleware = next(
            item for item in create_app(configured).user_middleware
            if item.cls is CORSMiddleware
        )
        self.assertEqual([firebaseapp, webapp], middleware.kwargs["allow_origins"])
        self.assertEqual(["ETag", "Content-Length"], middleware.kwargs["expose_headers"])

    def test_disabled_gateway_import_does_not_load_pillow_or_ad_runtime(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; import owner_gateway.api; "
                    "assert 'PIL' not in sys.modules; "
                    "assert 'commander.ad_generation' not in sys.modules"
                ),
            ],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_route_table_contains_only_v2_workspaces(self) -> None:
        class Verifier:
            def verify_id_token(self, _token): return self.claims
            def verify_app_check(self, _token): return {"app_id": "firebase-app"}

        verifier = Verifier()
        verifier.claims = self.claims
        paths = {route.path for route in create_app(self.settings, verifier=verifier).routes}
        for required in (
            "/api/v1/briefs", "/api/v1/briefs/{brief_id}/correct",
            "/api/v1/briefs/{brief_id}/approve",
            "/api/v1/ad-batches", "/api/v1/ad-creatives/{creative_id}/image",
            "/api/v1/ad-creatives/{creative_id}/feedback", "/api/v1/jobs",
            "/api/v1/skill-proposals/{domain}/plan",
            "/api/v1/system/health",
            "/internal/v1/validation-failures",
        ):
            self.assertIn(required, paths)
        for retired in (
            "/api/v1/ideas", "/api/v1/branding", "/api/v1/posts",
            "/api/v1/positionings", "/api/v1/ads", "/api/v1/landings/draft-sets",
            "/api/v1/public/landings/{build_id}/leads",
            "/api/v1/briefs/{brief_id}/revisions",
        ):
            self.assertNotIn(retired, paths)

    def test_wrong_email_uid_provider_verification_or_app_check_is_denied(self) -> None:
        variants = [
            {**self.claims, "email": "other@example.com"},
            {**self.claims, "uid": "other"},
            {**self.claims, "email_verified": False},
            {**self.claims, "firebase": {"sign_in_provider": "password"}},
        ]
        for claims in variants:
            with self.subTest(claims=claims), self.assertRaises(HTTPException):
                validate_owner_claims(self.settings, claims, {"app_id": "firebase-app"})
        with self.assertRaises(HTTPException):
            validate_owner_claims(self.settings, self.claims, {})
        with self.assertRaises(HTTPException):
            validate_owner_claims(self.settings, self.claims, {"app_id": "wrong-app"})
