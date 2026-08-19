from __future__ import annotations

import tempfile
import unittest
import importlib.util
from pathlib import Path
import subprocess
import sys

from owner_gateway.settings import Settings

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
if HAS_FASTAPI:
    from fastapi import HTTPException
    from owner_gateway.auth import validate_owner_claims


def settings(root: Path) -> Settings:
    return Settings(
        firebase_project_id="provethemwrong-86123", firebase_app_id="firebase-app",
        owner_email="sgolovaschuk@gmail.com",
        owner_uid="owner-uid", service_account_path=None, idea_database_url="postgres://idea",
        idea_service_url="http://idea", idea_service_token="bridge", commander_database_url="postgres://commander",
        platform_database_url="postgres://platform", platform_owner_telegram_id=1, owner_chat_id=1,
        control_database_path=root / "control.sqlite3", repository_path=root,
        codex_executable="codex", root_broker_socket=root / "root.sock",
        commander_asset_root=root / "assets",
        commander_policy_path=root / "policies.json", public_origin="https://example.test",
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
