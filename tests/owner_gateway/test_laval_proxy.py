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
    from owner_gateway.settings import Settings


@unittest.skipUnless(HAS_RUNTIME, "FastAPI and httpx are required")
class LavalGatewayProxyTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_exact_owner_can_create_and_read_laval_runs_through_bridge(self) -> None:
        calls: list[tuple[str, str, dict[str, object]]] = []

        class Verifier:
            def verify(self, token: str, app_token: str) -> OwnerIdentity:
                if token != "owner-token" or app_token != "app-token":
                    raise AssertionError("gateway did not forward authenticated request")
                return OwnerIdentity("owner", "owner@example.test")

        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def request(self, method: str, url: str, **kwargs):
                calls.append((method, url, kwargs))
                if method == "POST":
                    return httpx.Response(200, json={"run_id": "01234567-89ab-7def-8123-456789abcdef", "status": "pending"})
                return httpx.Response(200, json={"items": [], "next_cursor": None})

        headers = {"Authorization": "Bearer owner-token", "X-Firebase-AppCheck": "app-token"}
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=Client()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, Verifier())) as client,
        ):
            created = client.post("/api/v1/laval/runs", headers=headers, json={"text": "Owner idea", "config": {}})
            listed = client.get("/api/v1/laval/runs", headers=headers)
            for method, path in (
                ("get", "/api/v1/ideas"),
                ("post", "/api/v1/generations"),
                ("get", "/api/v1/contexts"),
                ("post", "/api/v1/post-batches"),
            ):
                self.assertEqual(404, getattr(client, method)(path, headers=headers).status_code)
        self.assertEqual(200, created.status_code)
        self.assertEqual({"items": [], "next_cursor": None}, listed.json())
        self.assertEqual("firebase:owner", calls[0][2]["json"]["actor"])
        self.assertEqual("bridge-token", calls[0][2]["headers"]["X-PTW-Owner-Gateway-Token"])
        self.assertTrue(calls[0][1].endswith("/internal/web/laval/runs"))


if __name__ == "__main__":
    unittest.main()
