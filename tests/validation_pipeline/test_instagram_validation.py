import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from validation_pipeline.instagram_validation import (
    InstagramValidationService, LocalInstagramValidationAuthority,
)
from validation_pipeline.instagram_validation_routes import instagram_validation_router
from validation_pipeline.local_brief_store import LocalBriefStore


class AnalyticsAuthority:
    def __init__(self):
        self.items = {}
        self.rollups = []

    def attribution_for_source(self, source_id):
        return self.items.get(source_id)

    def list_rollups(self, _projects, _cutoff):
        return list(self.rollups)


class Analytics:
    def __init__(self):
        self.authority = AnalyticsAuthority()
        self.ordinal = 0

    def prepare_attribution(self, landing):
        if not landing:
            return None
        self.ordinal += 1
        token = (f"token{self.ordinal}" + "x" * 43)[:43]
        return {"token": token, "token_sha256": "a" * 64,
                "tracked_url": f"{landing['canonical_url']}?ptw_attribution={token}"}

    def register_attribution(self, *, prepared, project_id, channel, provider, source_entity_id, landing):
        value = {**prepared, "project_id": project_id, "channel": channel, "provider": provider,
                 "source_entity_id": source_entity_id, "attribution_source_id": str(uuid4())}
        self.authority.items[source_entity_id] = value
        return value

    def attribution_projection(self, source_id):
        item = self.authority.items.get(source_id)
        return None if item is None else {"token": item["token"], "tracked_url": item["tracked_url"], "source_id": item["attribution_source_id"]}


class Workspace:
    def version_render(self, _version):
        return {"bytes": b"approved-png", "sha256": "b" * 64}


class Studio:
    def _workspace(self, _creative_id):
        return Workspace()


class Sources:
    def __init__(self):
        self.project_id = str(uuid4()); self.creative_ids = [str(uuid4()), str(uuid4())]
        self.version_ids = [str(uuid4()), str(uuid4())]
        self.studio = Studio()

    def project(self, project_id):
        if project_id != self.project_id: raise KeyError(project_id)
        return {"project_id": project_id, "name": "Idea"}

    def landing(self, project_id):
        self.project(project_id)
        return {"publication_id": str(uuid4()), "event_id": str(uuid4()), "landing_version_id": str(uuid4()),
                "landing_version": 1, "landing_version_sha256": "c" * 64,
                "canonical_url": "https://natal-service.com/ai/idea"}

    def source(self, project_id, creative_id, version):
        self.project(project_id); index = self.creative_ids.index(creative_id)
        if version != 1: raise KeyError(version)
        return {"creative_id": creative_id, "creative_ordinal": index + 1, "template_id": "phone_metrics",
                "version": 1, "version_id": self.version_ids[index], "version_sha256": "a" * 64,
                "render_sha256": "b" * 64, "change_note": "approved",
                "defaults": {"headline": f"Idea {index + 1}", "primary_text": "Support\n\nOffer",
                             "instagram_caption": f"Idea {index + 1}\n\nSupport\n\nOffer", "welcome_message": "Hi"}}

    def _sources(self, project_id):
        return [self.source(project_id, creative_id, 1) for creative_id in self.creative_ids]


class InstagramValidationTest(unittest.TestCase):
    def test_http_csv_import_is_not_captured_as_a_lifecycle_action(self):
        class RouteService:
            def import_csv(_self, project_id, test_id, request, actor):
                return {"handler": "import", "project_id": project_id, "test_id": test_id,
                        "request": request, "actor": actor}

            def transition(_self, *_args):  # pragma: no cover
                raise AssertionError("static CSV import was captured as an action")

        app = FastAPI()
        app.include_router(instagram_validation_router(RouteService(), prefix="/instagram-tests"))
        project_id, test_id = str(uuid4()), str(uuid4())
        with TestClient(app) as client:
            response = client.post(
                f"/instagram-tests/projects/{project_id}/tests/{test_id}/imports",
                json={"request_id": str(uuid4()), "csv_text": "Ad name,Amount spent\nAD-01,1",
                      "accept_ignored_rows": True},
                headers={"X-PTW-Actor": "owner-test"},
            )
        self.assertEqual(201, response.status_code)
        self.assertEqual("import", response.json()["handler"])
        self.assertEqual("owner-test", response.json()["actor"])

    def test_meta_number_formats_normalize_without_losing_thousands(self) -> None:
        self.assertEqual(1234, InstagramValidationService._metric("1,234"))
        self.assertEqual(1234, InstagramValidationService._metric("1 234"))
        self.assertEqual(123456, InstagramValidationService._money_minor("1,234.56 UAH"))
        self.assertEqual(123456, InstagramValidationService._money_minor("1.234,56 ₴"))
        self.assertEqual(123400, InstagramValidationService._money_minor("1,234"))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.sources = Sources(); self.analytics = Analytics()
        self.service = InstagramValidationService(
            LocalInstagramValidationAuthority(LocalBriefStore(Path(self.temporary.name))),
            self.sources, self.analytics,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_manual_package_gets_its_own_tracked_caption(self):
        result = self.service.create_package(self.sources.project_id, {
            "request_id": str(uuid4()), "source": {"creative_id": self.sources.creative_ids[0], "version": 1},
        }, "owner")
        package = result["package"]
        self.assertEqual("prepared", package["state"])
        self.assertTrue(package["caption"].endswith(package["tracked_url"]))
        self.assertEqual(43, len(parse_qs(urlsplit(package["tracked_url"]).query)["ptw_attribution"][0]))

    def test_test_lifecycle_csv_mapping_and_leader(self):
        created = self.service.create_test(self.sources.project_id, {
            "request_id": str(uuid4()), "name": "Two arms", "total_budget_minor": 10000,
            "currency": "USD", "duration_days": 4,
            "arms": [{"creative_id": item, "version": 1} for item in self.sources.creative_ids],
        }, "owner")["test"]
        self.assertEqual(2500, created["daily_budget_minor"])
        self.assertEqual(2, len({item["tracked_url"] for item in created["arms"]}))
        csv_text = "Ad name,Amount spent (USD),Landing page views,Impressions\n" + "\n".join(
            f"{arm['ad_name']},{10 + index},20,100" for index, arm in enumerate(created["arms"])
        )
        preview = self.service.preview_csv(self.sources.project_id, created["test_id"], csv_text)
        self.assertEqual(2, len(preview["matched_rows"]))
        imported = self.service.import_csv(self.sources.project_id, created["test_id"], {
            "request_id": str(uuid4()), "csv_text": csv_text, "accept_ignored_rows": True,
        }, "owner")["test"]
        first = imported["arms"][0]
        attribution = self.analytics.authority.items[first["arm_id"]]
        self.analytics.authority.rollups.append({"project_id": self.sources.project_id,
            "attribution_source_id": attribution["attribution_source_id"], "event_type": "primary_cta_click",
            "surface": "hero", "target": "contacts", "cumulative_count": 2})
        projected = self.service.workspace(self.sources.project_id)["tests"][0]
        self.assertEqual(first["arm_id"], projected["current_leader_arm_id"])
        active = self.service.transition(self.sources.project_id, created["test_id"], "activated", {"request_id": str(uuid4())}, "owner")["test"]
        self.assertEqual("active", active["state"])
        self.assertFalse(active["winner_declared"])
        with self.assertRaisesRegex(RuntimeError, "active Instagram test"):
            self.service.assert_landing_mutation_allowed(self.sources.project_id)
        second = self.service.create_test(self.sources.project_id, {
            "request_id": str(uuid4()), "name": "Second test",
            "total_budget_minor": 5000, "currency": "USD", "duration_days": 2,
            "arms": [{"creative_id": item, "version": 1} for item in self.sources.creative_ids],
        }, "owner")["test"]
        with self.assertRaisesRegex(RuntimeError, "already has an active"):
            self.service.transition(
                self.sources.project_id, second["test_id"], "activated",
                {"request_id": str(uuid4())}, "owner",
            )
        with self.assertRaisesRegex(ValueError, "Confirm"):
            self.service.transition(self.sources.project_id, created["test_id"], "completed", {"request_id": str(uuid4()), "campaign_stopped": False}, "owner")
        completed = self.service.transition(self.sources.project_id, created["test_id"], "completed", {"request_id": str(uuid4()), "campaign_stopped": True}, "owner")["test"]
        self.assertEqual("completed", completed["state"])
        self.service.assert_landing_mutation_allowed(self.sources.project_id)


if __name__ == "__main__":
    unittest.main()
