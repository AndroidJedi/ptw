from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HAS_RUNTIME = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None

if HAS_RUNTIME:
    import httpx
    from fastapi.testclient import TestClient

    from owner_gateway.api import create_app
    from owner_gateway.auth import OwnerIdentity
    from owner_gateway.control_store import ControlStore
    from owner_gateway.settings import Settings


@unittest.skipUnless(HAS_RUNTIME, "FastAPI and httpx are required")
class BrandingGatewayProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.settings = Settings(
            firebase_project_id="project", firebase_app_id="app", owner_email="owner@example.test",
            owner_uid="owner", service_account_path=None, idea_database_url="postgres://idea",
            idea_service_url="http://idea", idea_service_token="bridge-token",
            commander_database_url="postgres://commander", platform_database_url="postgres://platform",
            platform_owner_telegram_id=1, owner_chat_id=1, control_database_path=root / "control.sqlite3",
            repository_path=root, codex_executable="codex", root_broker_socket=root / "broker.sock",
            commander_asset_root=root / "assets", commander_policy_path=root / "policy.json",
            public_origin="https://example.test",
        )
        self.headers = {
            "Authorization": "Bearer owner-token",
            "X-Firebase-AppCheck": "app-token",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    class Verifier:
        def verify(self, token: str, app_token: str) -> OwnerIdentity:
            if token != "owner-token" or app_token != "app-token":
                raise ValueError("invalid exact-owner credentials")
            return OwnerIdentity("owner", "owner@example.test")

    def test_authenticated_contract_asset_privacy_and_active_codex_conflict(self) -> None:
        calls: list[tuple[str, str, dict[str, object]]] = []
        run_id = "01234567-89ab-7def-8123-456789abcdef"

        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def request(self, method: str, url: str, **kwargs):
                calls.append((method, url, kwargs))
                if "/assets/" in url:
                    return httpx.Response(200, content=b"png", headers={"content-type": "image/png"})
                if url.endswith("/providers"):
                    return httpx.Response(200, json={"ready": True, "paid_seo_enabled": False})
                if url.endswith("/activity"):
                    return httpx.Response(200, json={"active": False, "operation": None, "run_id": None})
                if method == "POST":
                    return httpx.Response(200, json={"run_id": run_id, "status": "running"})
                return httpx.Response(200, json={"items": [], "next_cursor": None})

        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=Client()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier())) as client,
        ):
            self.assertEqual(200, client.get("/api/v1/branding/providers", headers=self.headers).status_code)
            self.assertEqual(200, client.get("/api/v1/branding/cases", headers=self.headers).status_code)
            created = client.post(
                "/api/v1/branding/runs", headers=self.headers,
                json={"idea_run_id": run_id, "constraints": "truthful"},
            )
            self.assertEqual(200, created.status_code)
            denied = client.get("/api/v1/branding/assets/" + "a" * 64)
            self.assertIn(denied.status_code, {401, 403})
            asset = client.get("/api/v1/branding/assets/" + "a" * 64, headers=self.headers)
            self.assertEqual(b"png", asset.content)
            self.assertEqual("private, no-store", asset.headers["cache-control"])

            ControlStore(self.settings.control_database_path).create_command("plan", "already active")
            conflict = client.post(
                "/api/v1/branding/runs", headers=self.headers,
                json={"idea_run_id": run_id},
            )
            self.assertEqual(409, conflict.status_code)
            self.assertIn("Codex operation", conflict.json()["detail"])

        create_call = next(item for item in calls if item[0] == "POST" and item[1].endswith("/branding/runs"))
        self.assertEqual("firebase:owner", create_call[2]["json"]["actor"])
        self.assertEqual("bridge-token", create_call[2]["headers"]["X-PTW-Owner-Gateway-Token"])

    def test_review_resolves_creative_and_digest_server_side_and_appends_correction(self) -> None:
        run_id = "01234567-89ab-7def-8123-456789abcdef"
        direction_id = "11234567-89ab-7def-8123-456789abcdef"
        creative_id = "21234567-89ab-7def-8123-456789abcdef"
        feedback_id = "31234567-89ab-7def-8123-456789abcdef"
        captured: dict[str, object] = {}

        def target(*_args):
            return {
                "run_id": run_id, "direction_id": direction_id, "creative_id": creative_id,
                "artifact_digest": "b" * 64, "latest_feedback_id": feedback_id,
            }

        def review(_self, **kwargs):
            captured.update(kwargs)
            return {"feedback_id": "41234567-89ab-7def-8123-456789abcdef", "weight_update_ids": []}

        with (
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            patch("owner_gateway.api.DomainReadModels.brand_review_target", side_effect=target),
            patch("owner_gateway.api.DomainReadModels.review", new=review),
            TestClient(create_app(self.settings, self.Verifier())) as client,
        ):
            response = client.post(
                f"/api/v1/branding/runs/{run_id}/directions/{direction_id}/review",
                headers=self.headers,
                json={"comment": "Keep the symbol"},
            )
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(creative_id, captured["creative_id"])
        self.assertEqual("b" * 64, captured["artifact_digest"])
        self.assertEqual(feedback_id, captured["supersedes_feedback_id"])
        self.assertEqual("firebase:owner", captured["actor"])
        self.assertIsNone(captured["rating"])
        self.assertEqual((), captured["annotations"])

    def test_text_only_brand_review_rejects_an_empty_comment(self) -> None:
        run_id = "01234567-89ab-7def-8123-456789abcdef"
        direction_id = "11234567-89ab-7def-8123-456789abcdef"
        with (
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            patch("owner_gateway.api.DomainReadModels.brand_review_target", return_value={
                "run_id": run_id, "direction_id": direction_id,
                "creative_id": "21234567-89ab-7def-8123-456789abcdef",
                "artifact_digest": "b" * 64, "latest_feedback_id": None,
            }),
            TestClient(create_app(self.settings, self.Verifier())) as client,
        ):
            response = client.post(
                f"/api/v1/branding/runs/{run_id}/directions/{direction_id}/review",
                headers=self.headers, json={"comment": "   "},
            )
        self.assertEqual(409, response.status_code)
        self.assertIn("must not be empty", response.json()["detail"])

    def test_bridge_timeout_is_bounded_and_reported_as_unavailable(self) -> None:
        class TimeoutClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def request(self, *_args, **_kwargs):
                raise httpx.ReadTimeout("bounded timeout")

        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=TimeoutClient()),
            TestClient(create_app(self.settings, self.Verifier())) as client,
        ):
            response = client.get("/api/v1/branding/providers", headers=self.headers)
        self.assertEqual(503, response.status_code)
        self.assertEqual("Idea Laval service is unavailable", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
