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
    class Studio:
        @staticmethod
        def recover_interrupted():
            return []

        @staticmethod
        def recover_learning():
            return []

    class Landing:
        @staticmethod
        def recover_interrupted():
            return []

    class MetaAds:
        @staticmethod
        def recover_interrupted():
            return []

        @staticmethod
        def locations(query, country_code):
            return {"items": [{"name": query, "country_code": country_code}]}

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
            studio_creative_service=self.Studio(),
            landing_page_service=self.Landing(),
            meta_ads_service=self.MetaAds(), instagram_service=self.Landing(),
        )
        background_routes = {
            ("POST", "/internal/v1/projects/{project_id}/briefs"),
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

    def test_meta_ads_staging_route_is_authenticated_and_runs_in_background(self) -> None:
        deployment_id = "01900000-0000-7000-8000-000000000010"

        class MetaAds(self.MetaAds):
            def __init__(self) -> None:
                self.called = threading.Event()

            @staticmethod
            def reserve(project_id, request):
                return ({"deployment_id": deployment_id, "project_id": project_id, "request_id": request["request_id"]}, True)

            def execute(self, identifier):
                if identifier == deployment_id:
                    self.called.set()

        meta = MetaAds()
        class Repository:
            @staticmethod
            def recover_interrupted():
                return {"briefs": 0}
        app = create_app(
            self.settings(), repository=Repository(), runner=object(),
            studio_creative_service=self.Studio(), landing_page_service=self.Landing(),
            meta_ads_service=meta, instagram_service=self.Landing(),
        )
        request = {
            "request_id": "01900000-0000-7000-8000-000000000011",
            "creative_id": "01900000-0000-7000-8000-000000000012", "version": 1,
            "preset_id": "01900000-0000-7000-8000-000000000013",
            "headline": "Headline", "primary_text": "Primary",
            "welcome_message": "Hello", "special_ad_categories": ["NONE"],
        }
        with TestClient(app) as client:
            denied = client.post(
                f"/internal/v1/ads/projects/01900000-0000-7000-8000-000000000014/deployments",
                json=request,
            )
            self.assertEqual(401, denied.status_code)
            response = client.post(
                f"/internal/v1/ads/projects/01900000-0000-7000-8000-000000000014/deployments",
                headers={"X-PTW-Owner-Gateway-Token": "owner-token"}, json=request,
            )
            self.assertEqual(202, response.status_code, response.text)
            self.assertTrue(meta.called.wait(timeout=1))

    def test_meta_ads_location_search_is_authenticated(self) -> None:
        class Repository:
            @staticmethod
            def recover_interrupted():
                return {"briefs": 0}

        app = create_app(
            self.settings(), repository=Repository(), runner=object(),
            studio_creative_service=self.Studio(), landing_page_service=self.Landing(),
            meta_ads_service=self.MetaAds(), instagram_service=self.Landing(),
        )
        with TestClient(app) as client:
            path = "/internal/v1/ads/locations?query=Kyiv&country_code=UA"
            self.assertEqual(401, client.get(path).status_code)
            response = client.get(path, headers={"X-PTW-Owner-Gateway-Token": "owner-token"})
            self.assertEqual(200, response.status_code, response.text)
            self.assertEqual("Kyiv", response.json()["items"][0]["name"])

    def test_public_read_authority_is_bridge_authenticated_and_get_head_only(self) -> None:
        class Repository:
            @staticmethod
            def recover_interrupted():
                return {"briefs": 0}

        class Publication:
            @staticmethod
            def snapshot(namespace, slug):
                return {
                    "schema": "ptw.public-landing.v1",
                    "canonical_url": f"https://natal-service.com/{namespace}/{slug}",
                }

            @staticmethod
            def asset(*_args):
                return {"bytes": b"png", "mime_type": "image/png", "sha256": "a" * 64}

        app = create_app(
            self.settings(), repository=Repository(), runner=object(),
            studio_creative_service=self.Studio(), landing_page_service=self.Landing(),
            landing_publication_service=Publication(), meta_ads_service=self.MetaAds(), instagram_service=self.Landing(),
        )
        path = "/internal/v1/public/landings/ai/example"
        with TestClient(app) as client:
            self.assertEqual(401, client.get(path).status_code)
            response = client.get(path, headers={"X-PTW-Owner-Gateway-Token": "owner-token"})
            head = client.head(path, headers={"X-PTW-Owner-Gateway-Token": "owner-token"})
            write = client.post(path, headers={"X-PTW-Owner-Gateway-Token": "owner-token"})

        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(200, head.status_code)
        self.assertEqual(b"", head.content)
        self.assertEqual(405, write.status_code)

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
            studio_creative_service=self.Studio(),
            landing_page_service=self.Landing(),
            meta_ads_service=self.MetaAds(), instagram_service=self.Landing(),
        )

        with TestClient(app) as client:
            response = client.post(
                f"/internal/v1/projects/{project_id}/briefs",
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
            self.assertEqual(project_id, repository.create_input["project_id"])

    def test_create_project_persists_owner_name_without_starting_generation(self) -> None:
        project_id = "01900000-0000-7000-8000-000000000020"

        class Repository:
            def __init__(self) -> None:
                self.input = None

            @staticmethod
            def recover_interrupted() -> dict[str, int]:
                return {"briefs": 0}

            def create_project(self, **value):
                self.input = value
                return ({
                    "project_id": project_id, "name": value["name"],
                    "owner_idea_source_id": None, "brief_count": 0,
                }, True)

        repository = Repository()
        app = create_app(
            self.settings(), repository=repository, runner=object(),
            studio_creative_service=self.Studio(), landing_page_service=self.Landing(),
            meta_ads_service=self.MetaAds(), instagram_service=self.Landing(),
        )
        with TestClient(app) as client:
            response = client.post(
                "/internal/v1/projects",
                headers={"X-PTW-Owner-Gateway-Token": "owner-token"},
                json={
                    "request_id": "01900000-0000-7000-8000-000000000021",
                    "name": "Owner Chosen Name",
                },
            )

        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual("Owner Chosen Name", response.json()["project"]["name"])
        self.assertIsNone(response.json()["project"]["owner_idea_source_id"])
        self.assertEqual("owner-web", repository.input["requested_by"])

    def test_busy_brief_admission_returns_conflict_instead_of_500(self) -> None:
        class Repository:
            def recover_interrupted(self) -> dict[str, int]:
                return {"briefs": 0}

            def create_brief(self, **_value):
                raise RuntimeError("another generation operation is active")

        app = create_app(
            self.settings(), repository=Repository(), runner=object(),
            studio_creative_service=self.Studio(),
            landing_page_service=self.Landing(),
            meta_ads_service=self.MetaAds(), instagram_service=self.Landing(),
        )

        with TestClient(app) as client:
            response = client.post(
                "/internal/v1/projects/01900000-0000-7000-8000-000000000005/briefs",
                headers={"X-PTW-Owner-Gateway-Token": "owner-token"},
                json={
                    "request_id": "01900000-0000-7000-8000-000000000004",
                    "raw_idea": "A concurrent idea.",
                    "language": "en",
                },
            )

        self.assertEqual(409, response.status_code, response.text)
        self.assertEqual("another generation operation is active", response.json()["detail"])

    def test_brief_approval_requires_template_and_starts_reserved_creative(self) -> None:
        brief_id = "01900000-0000-7000-8000-000000000011"
        creative_id = "01900000-0000-7000-8000-000000000012"

        class Repository:
            @staticmethod
            def recover_interrupted() -> dict[str, int]:
                return {"briefs": 0}

            @staticmethod
            def approve_brief(*_args):
                raise AssertionError("Studio must own the approval transaction")

        class Studio(self.Studio):
            def __init__(self) -> None:
                self.generated = threading.Event()
                self.approval = None

            def approve_brief_and_reserve(self, **value):
                self.approval = value
                return (
                    {"brief_id": brief_id, "approved": True}, True,
                    {"creative_id": creative_id, "status": "queued"}, True,
                )

            def generate(self, identifier: str) -> None:
                if identifier == creative_id:
                    self.generated.set()

        studio = Studio()
        app = create_app(
            self.settings(), repository=Repository(), runner=object(),
            studio_creative_service=studio,
            landing_page_service=self.Landing(),
            meta_ads_service=self.MetaAds(), instagram_service=self.Landing(),
        )
        headers = {"X-PTW-Owner-Gateway-Token": "owner-token"}
        with TestClient(app) as client:
            invalid = client.post(
                f"/internal/v1/briefs/{brief_id}/approve", headers=headers,
                json={"honor_confirmed": True},
            )
            missing_direction = client.post(
                f"/internal/v1/briefs/{brief_id}/approve", headers=headers,
                json={"honor_confirmed": True, "template_id": "phone_metrics"},
            )
            response = client.post(
                f"/internal/v1/briefs/{brief_id}/approve", headers=headers,
                json={
                    "honor_confirmed": True, "template_id": "phone_metrics",
                    "creative_direction": {
                        "schema": "ptw.studio.phone-hero-direction.v1",
                        "style": "cinematic", "background": "scene",
                    },
                },
            )
            self.assertTrue(studio.generated.wait(timeout=1))

        self.assertEqual(400, invalid.status_code, invalid.text)
        self.assertEqual(400, missing_direction.status_code, missing_direction.text)
        self.assertEqual(202, response.status_code, response.text)
        self.assertEqual(creative_id, response.json()["creative"]["creative_id"])
        self.assertEqual("phone_metrics", studio.approval["template_id"])
        self.assertEqual("cinematic", studio.approval["creative_direction"]["style"])


if __name__ == "__main__":
    unittest.main()
