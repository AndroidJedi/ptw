from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


HAS_RUNTIME = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None

if HAS_RUNTIME:
    import httpx
    from fastapi.testclient import TestClient

    from owner_gateway.api import create_app
    from owner_gateway.auth import OwnerIdentity
    from owner_gateway.control_store import ControlStore
    from owner_gateway.settings import Settings


RUN_ID = "01234567-89ab-7def-8123-456789abcdef"
THESIS_ID = "11234567-89ab-7def-8123-456789abcdef"


@unittest.skipUnless(HAS_RUNTIME, "FastAPI and httpx are required")
class LandingBuilderGatewayTests(unittest.TestCase):
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
        self.headers = {"Authorization": "Bearer owner-token", "X-Firebase-AppCheck": "app-token"}
        self.case = {
            "idea_run_id": RUN_ID,
            "owner_idea": "Retention platform for service teams",
            "recommended_thesis_id": THESIS_ID,
            "quality": {"successful": 8, "attempted": 9},
            "theses": [{
                "id": THESIS_ID, "recommended": True, "verdict": "survives",
                "title": {"uk": "Утримання без таблиць", "en": "Retention without sheets"},
                "target_user": {"uk": "Команди салонів", "en": "Salon teams"},
                "problem": {"uk": "Клієнти зникають непомітно", "en": "Clients disappear silently"},
                "value_moment": {"uk": "Наступна дія видима", "en": "The next action is visible"},
                "loop_steps": [{"uk": "Підключити дані", "en": "Connect data"}, {"uk": "Побачити ризик", "en": "See risk"}],
                "mechanism_ids": [],
            }],
            "mechanisms": [],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    class Verifier:
        def verify(self, token: str, app_token: str) -> OwnerIdentity:
            if token != "owner-token" or app_token != "app-token":
                raise ValueError("invalid credentials")
            return OwnerIdentity("owner", "owner@example.test")

    def test_lists_templates_and_completed_evaluation_briefs(self) -> None:
        case = self.case

        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def request(self, _method: str, url: str, **_kwargs):
                if url.endswith("/branding/cases"):
                    return httpx.Response(200, json={"items": [case], "next_cursor": None})
                return httpx.Response(404, json={"detail": "unexpected"})

        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=Client()),
            TestClient(create_app(self.settings, self.Verifier())) as client,
        ):
            templates = client.get("/api/v1/landings/templates", headers=self.headers)
            candidates = client.get("/api/v1/landings/candidates", headers=self.headers)
        self.assertEqual(["product", "community", "waitlist"], [item["id"] for item in templates.json()["items"]])
        prepared = candidates.json()["items"][0]
        self.assertEqual(RUN_ID, prepared["brief"]["source"]["laval_run_id"])
        self.assertEqual("product", prepared["recommended_template_id"])

    def test_builder_job_resolves_source_selects_template_and_creates_skill_plan(self) -> None:
        case = self.case

        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def request(self, _method: str, url: str, **_kwargs):
                if url.endswith("/branding/cases"):
                    return httpx.Response(200, json={"items": [case], "next_cursor": None})
                if url.endswith("/activity"):
                    return httpx.Response(200, json={"active": False})
                return httpx.Response(404, json={"detail": "unexpected"})

        planner = AsyncMock(return_value="Build the bounded Natal landing and verify it.")
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=Client()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            patch("owner_gateway.api.AppServerPlanner.plan", planner),
            TestClient(create_app(self.settings, self.Verifier())) as client,
        ):
            response = client.post(
                "/api/v1/landings/builder-jobs", headers=self.headers,
                json={
                    "idea_run_id": RUN_ID, "template_id": "auto",
                    "brief": {
                        "business_idea": "Sharper evaluated idea",
                        "source": {"laval_run_id": "spoofed"},
                    },
                },
            )
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual("product", body["landing"]["template_id"])
        self.assertEqual("Sharper evaluated idea", body["landing"]["brief"]["business_idea"])
        self.assertEqual(RUN_ID, body["landing"]["brief"]["source"]["laval_run_id"])
        self.assertTrue(body["landing"]["output_path"].startswith("output/landings/01234567-product-"))
        stored = ControlStore(self.settings.control_database_path).command(body["id"])
        self.assertIn("$natal-landing-builder", stored["instruction"])
        self.assertIn(f'"laval_run_id": "{RUN_ID}"', stored["instruction"])
        self.assertIn("Do not deploy", stored["instruction"])

    def test_builder_job_rejects_unknown_template_and_missing_completed_case(self) -> None:
        case = self.case

        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def request(self, _method: str, url: str, **_kwargs):
                if url.endswith("/branding/cases"):
                    return httpx.Response(200, json={"items": [case]})
                return httpx.Response(200, json={"active": False})

        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=Client()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier())) as client,
        ):
            unknown = client.post(
                "/api/v1/landings/builder-jobs", headers=self.headers,
                json={"idea_run_id": RUN_ID, "template_id": "unknown"},
            )
            missing = client.post(
                "/api/v1/landings/builder-jobs", headers=self.headers,
                json={"idea_run_id": "21234567-89ab-7def-8123-456789abcdef", "template_id": "auto"},
            )
        self.assertEqual(400, unknown.status_code)
        self.assertEqual(404, missing.status_code)


if __name__ == "__main__":
    unittest.main()
