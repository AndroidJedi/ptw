from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
import threading
import unittest


HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
if HAS_FASTAPI:
    from fastapi.testclient import TestClient
    from validation_pipeline.api import create_app
    from validation_pipeline.config import Settings


@unittest.skipUnless(HAS_FASTAPI, "fastapi is required")
class ValidationApiRouteTests(unittest.TestCase):
    @staticmethod
    def settings() -> Settings:
        return Settings(
            database_url="postgresql://unused",
            owner_gateway_token="owner-token",
            bridge_url="http://bridge",
            bridge_token="bridge-token",
            pexels_api_key="pexels-key",
            product_brief_skill_path=Path("unused-product-brief-skill"),
        )

    def test_background_starting_routes_execute_on_the_event_loop(self) -> None:
        app = create_app(
            self.settings(),
            repository=object(),
            runner=object(),
        )
        background_routes = {
            ("POST", "/internal/v1/briefs"),
            ("POST", "/internal/v1/briefs/{brief_id}/correct"),
            ("POST", "/internal/v1/briefs/{brief_id}/retry"),
        }
        handlers = {
            (method, route.path): route.endpoint
            for route in app.routes
            for method in (getattr(route, "methods", None) or set())
            if (method, route.path) in background_routes
        }

        self.assertEqual(background_routes, set(handlers))
        self.assertTrue(all(inspect.iscoroutinefunction(handler) for handler in handlers.values()))

    def test_create_brief_schedules_generation_and_returns_accepted(self) -> None:
        brief_id = "01900000-0000-7000-8000-000000000001"
        project_id = "01900000-0000-7000-8000-000000000002"

        class Repository:
            def __init__(self) -> None:
                self.create_input = None

            def recover_interrupted(self) -> dict[str, int]:
                return {"briefs": 0}

            def create_brief(self, **_value):
                self.create_input = _value
                return ({"brief_id": brief_id, "project_id": project_id, "status": "queued"}, True)

            def acquire_operation(self, kind: str, identifier: str) -> bool:
                return kind == "product_brief" and identifier == brief_id

            def get_project(self, identifier: str) -> dict[str, str]:
                return {"project_id": identifier}

        class Runner:
            def __init__(self) -> None:
                self.called = threading.Event()

            def generate_brief(self, identifier: str, *, operation_reserved: bool = False) -> None:
                if identifier == brief_id and operation_reserved:
                    self.called.set()

        repository = Repository()
        runner = Runner()
        app = create_app(
            self.settings(), repository=repository, runner=runner,
        )

        with TestClient(app) as client:
            response = client.post(
                "/internal/v1/briefs",
                headers={"X-PTW-Owner-Gateway-Token": "owner-token"},
                json={
                    "request_id": "01900000-0000-7000-8000-000000000003",
                    "raw_idea": "One focused validation idea.",
                    "language": "uk",
                },
            )
            self.assertEqual(202, response.status_code, response.text)
            self.assertTrue(runner.called.wait(timeout=1))
            self.assertEqual("uk", repository.create_input["required_language"])

    def test_busy_brief_admission_returns_conflict_instead_of_500(self) -> None:
        class Repository:
            def recover_interrupted(self) -> dict[str, int]:
                return {"briefs": 0}

            def create_brief(self, **_value):
                raise RuntimeError("another generation operation is active")

        app = create_app(
            self.settings(), repository=Repository(), runner=object(),
        )

        with TestClient(app) as client:
            response = client.post(
                "/internal/v1/briefs",
                headers={"X-PTW-Owner-Gateway-Token": "owner-token"},
                json={
                    "request_id": "01900000-0000-7000-8000-000000000004",
                    "raw_idea": "A concurrent idea.",
                    "language": "en",
                },
            )

        self.assertEqual(409, response.status_code, response.text)
        self.assertEqual("another generation operation is active", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
