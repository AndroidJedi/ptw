from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

import httpx

from validation_pipeline.local_brief_store import LocalBriefStore, sha256_json, utc_now
from validation_pipeline.meta_ads import (
    LocalMetaAdsAuthority, MetaAdsAdapter, MetaAdsConfiguration, MetaAdsService,
    normalize_preset,
)


PROJECT_ID = "01900000-0000-7000-8000-000000000001"
CREATIVE_ID = "01900000-0000-7000-8000-000000000002"
BRIEF_ID = "01900000-0000-7000-8000-000000000003"
REQUEST_ID = "01900000-0000-7000-8000-000000000004"


def form(request: httpx.Request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(request.content.decode()).items()}


class MetaAdsAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[httpx.Request] = []
        self.existing: dict[str, list[dict[str, object]]] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            path = request.url.path
            if path.endswith("/me/permissions"):
                return httpx.Response(200, json={"data": [{"permission": p, "status": "granted"} for p in ["ads_read", "ads_management"]]})
            if request.method == "GET" and path.endswith("/me/adaccounts"):
                return httpx.Response(200, json={"data": [{
                    "id": "act_123", "name": "Local test", "currency": "USD", "account_status": 1,
                }]})
            if request.method == "GET" and path.endswith("/act_123"):
                return httpx.Response(200, json={
                    "id": "act_123", "name": "Local test", "currency": "USD",
                    "account_status": 1, "promote_pages": {"data": [{"id": "456", "name": "Page"}]},
                })
            if request.method == "GET" and path.endswith("/instagram_accounts"):
                return httpx.Response(200, json={"data": [{"id": "789", "username": "ptw"}]})
            if request.method == "GET" and path.endswith("/search"):
                return httpx.Response(200, json={"data": [
                    {"key": "2420605", "name": "Kyiv", "type": "city", "country_code": "UA", "country_name": "Ukraine", "region": "Kyiv"},
                    {"key": "not-a-city", "name": "Ukraine", "type": "country", "country_code": "UA"},
                ]})
            if request.method == "GET" and path.rsplit("/", 1)[-1] in {"campaigns", "adsets", "adcreatives", "ads"}:
                return httpx.Response(200, json={"data": self.existing.get(path.rsplit("/", 1)[-1], [])})
            if request.method == "POST" and path.endswith("/campaigns"):
                return httpx.Response(200, json={"id": "campaign-1"})
            if request.method == "POST" and path.endswith("/adsets"):
                return httpx.Response(200, json={"id": "adset-1"})
            if request.method == "POST" and path.endswith("/adimages"):
                return httpx.Response(200, json={"images": {"filename": {"hash": "image-hash"}}})
            if request.method == "POST" and path.endswith("/adcreatives"):
                return httpx.Response(200, json={"id": "creative-1"})
            if request.method == "POST" and path.endswith("/ads"):
                return httpx.Response(200, json={"id": "ad-1"})
            return httpx.Response(404, json={"error": {"code": 100}})

        configuration = MetaAdsConfiguration(
            access_token="secret-system-token", ad_account_id="123",
            page_id="456", instagram_actor_id="789",
        )
        self.adapter = MetaAdsAdapter(
            configuration, client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        self.assertNotIn("secret-system-token", repr(configuration))

    def tearDown(self) -> None:
        self.adapter._client.close()

    def test_exact_paused_instagram_direct_structure_and_no_token_leak(self) -> None:
        connection = self.adapter.connection()
        self.assertTrue(connection["verified"])
        campaign = self.adapter.ensure_campaign("[PTW LOCAL] project", ["NONE"])
        ad_set = self.adapter.ensure_ad_set("[PTW LOCAL] audience", campaign_id=campaign["id"], preset={
            "countries": ["UA"], "age_min": 25, "age_max": 44,
            "gender": "women", "daily_budget_minor": 500,
        })
        png = b"\x89PNG\r\n\x1a\nverified-test-png"
        image_hash = self.adapter.upload_image(png, hashlib.sha256(png).hexdigest())
        creative = self.adapter.ensure_creative("[PTW LOCAL] creative", image_hash=image_hash, specification={
            "headline": "Headline", "primary_text": "Primary", "welcome_message": "Hello",
        })
        self.adapter.ensure_ad("[PTW LOCAL] ad", ad_set_id=ad_set["id"], creative_id=creative["id"])

        posts = {request.url.path.rsplit("/", 1)[-1]: request for request in self.requests if request.method == "POST"}
        campaign_payload = form(posts["campaigns"])
        self.assertEqual("PAUSED", campaign_payload["status"])
        self.assertEqual("OUTCOME_ENGAGEMENT", campaign_payload["objective"])
        ad_set_payload = form(posts["adsets"])
        self.assertEqual("PAUSED", ad_set_payload["status"])
        self.assertEqual("INSTAGRAM_DIRECT", ad_set_payload["destination_type"])
        self.assertEqual("CONVERSATIONS", ad_set_payload["optimization_goal"])
        self.assertEqual("IMPRESSIONS", ad_set_payload["billing_event"])
        self.assertEqual("LOWEST_COST_WITHOUT_CAP", ad_set_payload["bid_strategy"])
        targeting = json.loads(ad_set_payload["targeting"])
        self.assertEqual(["instagram"], targeting["publisher_platforms"])
        self.assertEqual(["stream"], targeting["instagram_positions"])
        self.assertEqual([2], targeting["genders"])
        creative_payload = form(posts["adcreatives"])
        story = json.loads(creative_payload["object_story_spec"])
        self.assertEqual("456", story["page_id"])
        self.assertEqual("789", story["instagram_user_id"])
        self.assertEqual("SEND_MESSAGE", story["link_data"]["call_to_action"]["type"])
        enhancements = json.loads(creative_payload["degrees_of_freedom_spec"])
        self.assertEqual("OPT_OUT", enhancements["creative_features_spec"]["standard_enhancements"]["enroll_status"])
        self.assertEqual("PAUSED", form(posts["ads"])["status"])
        for request in self.requests:
            self.assertEqual("Bearer secret-system-token", request.headers["authorization"])
            self.assertNotIn(b"secret-system-token", request.content)
            self.assertNotIn("secret-system-token", str(request.url))
            self.assertNotIn(b"ACTIVE", request.content)

    def test_website_payload_has_real_link_and_no_direct_message(self) -> None:
        self.adapter.ensure_campaign("website", ["NONE"], "OUTCOME_TRAFFIC")
        self.adapter.ensure_ad_set("website audience", campaign_id="campaign-1", destination="WEBSITE", preset={
            "countries": ["UA"], "age_min": 25, "age_max": 55, "gender": "all", "daily_budget_minor": 500,
        })
        url = "https://natal-service.com/la/example"
        self.adapter.ensure_creative("website creative", image_hash="hash", specification={
            "headline": "Headline", "primary_text": "Primary", "destination_type": "WEBSITE", "landing": {"canonical_url": url},
        })
        posts = {request.url.path.rsplit("/", 1)[-1]: form(request) for request in self.requests if request.method == "POST"}
        self.assertEqual("OUTCOME_TRAFFIC", posts["campaigns"]["objective"])
        self.assertEqual("LINK_CLICKS", posts["adsets"]["optimization_goal"])
        self.assertEqual("WEBSITE", posts["adsets"]["destination_type"])
        self.assertNotIn("promoted_object", posts["adsets"])
        creative = posts["adcreatives"]
        self.assertNotIn("page_welcome_message", creative)
        link = json.loads(creative["object_story_spec"])["link_data"]
        self.assertEqual(url, link["link"])
        self.assertEqual({"type": "LEARN_MORE", "value": {"link": url}}, link["call_to_action"])
        self.assertEqual("PAUSED", posts["campaigns"]["status"])
        self.assertEqual("PAUSED", posts["adsets"]["status"])

    def test_campaign_reconciliation_rejects_wrong_objective(self) -> None:
        self.existing["campaigns"] = [{"id": "1", "name": "website", "status": "ACTIVE", "objective": "OUTCOME_ENGAGEMENT", "special_ad_categories": []}]
        with self.assertRaisesRegex(RuntimeError, "objective"):
            self.adapter.ensure_campaign("website", ["NONE"], "OUTCOME_TRAFFIC")
        self.assertFalse(any(request.method == "POST" for request in self.requests))

    def test_rejects_changed_png_before_upload(self) -> None:
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.adapter.upload_image(b"changed", "0" * 64)
        self.assertFalse(any(request.url.path.endswith("/adimages") for request in self.requests))

    def test_searches_meta_city_keys_and_targets_city_radius_without_country_broadening(self) -> None:
        cities = self.adapter.search_cities("Kyiv", "UA")
        self.assertEqual([{
            "key": "2420605", "name": "Kyiv", "type": "city", "country_code": "UA",
            "country_name": "Ukraine", "region": "Kyiv",
        }], cities)
        search = next(request for request in self.requests if request.url.path.endswith("/search"))
        self.assertEqual("adgeolocation", search.url.params["type"])
        self.assertEqual('["city"]', search.url.params["location_types"])
        self.assertEqual("UA", search.url.params["country_code"])

        self.adapter.ensure_ad_set("Kyiv radius", campaign_id="campaign-1", preset={
            "countries": [], "cities": [{
                "key": "2420605", "name": "Kyiv", "country_code": "UA", "radius_km": 20,
            }],
            "age_min": 25, "age_max": 55, "gender": "all", "daily_budget_minor": 500,
        })
        ad_set_request = next(request for request in self.requests if request.method == "POST" and request.url.path.endswith("/adsets"))
        targeting = json.loads(form(ad_set_request)["targeting"])
        self.assertNotIn("countries", targeting["geo_locations"])
        self.assertEqual([{
            "key": "2420605", "radius": 20, "distance_unit": "kilometer",
        }], targeting["geo_locations"]["cities"])

    def test_city_preset_is_versioned_and_rejects_ambiguous_or_unsafe_geo(self) -> None:
        city = normalize_preset({
            "name": "Kyiv 20 km", "countries": [], "cities": [{
                "key": "2420605", "name": "Kyiv", "country_code": "UA", "radius_km": 20,
            }],
            "age_min": 25, "age_max": 55, "gender": "all", "daily_budget_minor": 500,
        })
        self.assertEqual("ptw.meta-ads.preset.v2", city["schema"])
        self.assertEqual([], city["countries"])
        self.assertEqual("2420605", city["cities"][0]["key"])
        with self.assertRaisesRegex(ValueError, "either countries or cities"):
            normalize_preset({**{key: value for key, value in city.items() if key not in {
                "schema", "publisher_platforms", "instagram_positions", "location_types",
            }}, "countries": ["UA"]})
        with self.assertRaisesRegex(ValueError, "between 17 and 80"):
            normalize_preset({
                "name": "Too tight", "countries": [], "cities": [{
                    "key": "2420605", "name": "Kyiv", "country_code": "UA", "radius_km": 5,
                }],
                "age_min": 25, "age_max": 55, "gender": "all", "daily_budget_minor": 500,
            })

    def test_configuration_reads_optional_locked_secret_file_without_exposing_token(self) -> None:
        with TemporaryDirectory() as temporary:
            secrets_path = Path(temporary) / "meta-ads.env"
            secrets_path.write_text(
                "META_SYSTEM_USER_ACCESS_TOKEN=server-secret\n"
                "META_AD_ACCOUNT_ID=act_123\n"
                "META_PAGE_ID=456\n"
                "META_INSTAGRAM_ACTOR_ID=789\n"
                "META_GRAPH_API_VERSION=v26.0\n"
                "META_ADS_NAME_PREFIX=[PTW VPS]\n",
                encoding="utf-8",
            )
            secrets_path.chmod(0o400)
            with patch.dict(os.environ, {"META_ADS_SECRETS_PATH": str(secrets_path)}, clear=True):
                configuration = MetaAdsConfiguration.from_environment()
            self.assertTrue(configuration.configured)
            self.assertEqual("123", configuration.ad_account_id)
            self.assertEqual("[PTW VPS]", configuration.name_prefix)
            self.assertNotIn("server-secret", repr(configuration))

    def test_configuration_rejects_broad_secret_file_permissions(self) -> None:
        with TemporaryDirectory() as temporary:
            secrets_path = Path(temporary) / "meta-ads.env"
            secrets_path.write_text("META_SYSTEM_USER_ACCESS_TOKEN=secret\n", encoding="utf-8")
            secrets_path.chmod(0o644)
            with patch.dict(os.environ, {"META_ADS_SECRETS_PATH": str(secrets_path)}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "must use mode"):
                    MetaAdsConfiguration.from_environment()

    def test_exact_name_reconciliation_resumes_without_duplicate_posts(self) -> None:
        self.existing = {
            "campaigns": [{"id": "campaign-old", "name": "campaign marker", "status": "ACTIVE", "objective": "OUTCOME_ENGAGEMENT", "special_ad_categories": []}],
            "adsets": [{"id": "adset-old", "name": "adset marker", "status": "PAUSED", "campaign_id": "campaign-old", "destination_type": "INSTAGRAM_DIRECT", "optimization_goal": "CONVERSATIONS", "billing_event": "IMPRESSIONS", "daily_budget": "500", "targeting": {"geo_locations": {"countries": ["UA"]}, "age_min": 25, "age_max": 44, "publisher_platforms": ["instagram"], "instagram_positions": ["stream"]}}],
            "adcreatives": [{"id": "creative-old", "name": "creative marker", "object_story_spec": {"page_id": "456", "instagram_user_id": "789", "link_data": {"image_hash": "hash", "name": "Headline", "message": "Primary", "call_to_action": {"type": "SEND_MESSAGE", "value": {"app_destination": "INSTAGRAM_DIRECT"}}}}}],
            "ads": [{"id": "ad-old", "name": "ad marker", "status": "PAUSED", "adset_id": "adset-old", "creative": {"id": "creative-old"}}],
        }
        campaign = self.adapter.ensure_campaign("campaign marker", ["NONE"])
        ad_set = self.adapter.ensure_ad_set("adset marker", campaign_id=campaign["id"], preset={
            "countries": ["UA"], "age_min": 25, "age_max": 44,
            "gender": "all", "daily_budget_minor": 500,
        })
        creative = self.adapter.ensure_creative("creative marker", image_hash="hash", specification={
            "headline": "Headline", "primary_text": "Primary", "welcome_message": "Hello",
        })
        ad = self.adapter.ensure_ad("ad marker", ad_set_id=ad_set["id"], creative_id=creative["id"])
        self.assertEqual(("campaign-old", "adset-old", "creative-old", "ad-old"), (
            campaign["id"], ad_set["id"], creative["id"], ad["id"],
        ))
        self.assertFalse(any(request.method == "POST" for request in self.requests))


class FakeWorkspace:
    png = b"\x89PNG\r\n\x1a\nlocal-approved"

    def version_detail(self, version: int) -> dict[str, object]:
        if version not in {1, 2}:
            raise KeyError("approved Studio version was not found")
        content = {
            "hero_title": f"Natal idea {version}", "supporting_text": "Personal guidance",
            "offer": "First session", "cta": "Write now",
        }
        return {
            "version": version, "version_id": f"01900000-0000-7000-8000-00000000000{4 + version}",
            "version_sha256": sha256_json(content), "render_sha256": hashlib.sha256(self.png).hexdigest(),
            "content": content, "configuration": {}, "change_note": "Approved",
        }

    def version_render(self, version: int) -> dict[str, object]:
        self.version_detail(version)
        return {"bytes": self.png, "sha256": hashlib.sha256(self.png).hexdigest()}


class FakeStudioAuthority:
    def brief(self, brief_id: str) -> dict[str, object]:
        if brief_id != BRIEF_ID:
            raise KeyError("brief not found")
        return {"document": {"language": "uk"}}


class FakeStudio:
    authority = FakeStudioAuthority()
    workspace = FakeWorkspace()

    def list_creatives(self, project_id: str) -> dict[str, object]:
        if project_id != PROJECT_ID:
            raise KeyError("project not found")
        return {"items": [{
            "creative_id": CREATIVE_ID, "ordinal": 1, "template_id": "universal_ad",
            "approved_version_count": 2,
        }]}

    def detail(self, project_id: str, creative_id: str) -> dict[str, object]:
        if project_id != PROJECT_ID or creative_id != CREATIVE_ID:
            raise KeyError("Studio creative was not found in this Project")
        return {
            "project_id": PROJECT_ID, "source_brief_id": BRIEF_ID,
            "versions": [{"version": 1}, {"version": 2}],
        }

    def _workspace(self, creative_id: str) -> FakeWorkspace:
        if creative_id != CREATIVE_ID:
            raise KeyError("workspace not found")
        return self.workspace


class FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_once: str | None = None

    def _record(self, stage: str) -> None:
        self.calls.append(stage)
        if self.fail_once == stage:
            self.fail_once = None
            raise httpx.TimeoutException("timeout secret must not be persisted")

    def connection(self) -> dict[str, object]:
        self._record("connection")
        return {"configured": True, "verified": True, "graph_version": "v26.0"}

    def ensure_campaign(self, name: str, categories: list[str], objective: str = "OUTCOME_ENGAGEMENT") -> dict[str, str]:
        self._record("campaign")
        return {"id": f"campaign-{self.calls.count('campaign')}"}

    def ensure_ad_set(self, name: str, *, campaign_id: str, preset: dict[str, object], destination: str = "INSTAGRAM_DIRECT") -> dict[str, str]:
        self._record("ad_set")
        return {"id": f"adset-{self.calls.count('ad_set')}"}

    def upload_image(self, png: bytes, expected_sha256: str) -> str:
        self._record("image")
        assert hashlib.sha256(png).hexdigest() == expected_sha256
        return "image-hash"

    def ensure_creative(self, name: str, *, image_hash: str, specification: dict[str, object]) -> dict[str, str]:
        self._record("creative")
        return {"id": f"creative-{self.calls.count('creative')}"}

    def ensure_ad(self, name: str, *, ad_set_id: str, creative_id: str) -> dict[str, str]:
        self._record("ad")
        return {"id": f"ad-{self.calls.count('ad')}"}

    def status(self, object_id: str, kind: str) -> dict[str, str]:
        return {"id": object_id, "status": "PAUSED", "effective_status": "PAUSED"}

    def ads_manager_url(self, campaign_id: str | None = None) -> str:
        return "https://adsmanager.facebook.com/test"


class MetaAdsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.store = LocalBriefStore(Path(self.temporary.name))
        self.store.append("projects", PROJECT_ID, {
            "project_id": PROJECT_ID, "name": "Natal service", "created_at": utc_now(),
        })
        self.authority = LocalMetaAdsAuthority(self.store)
        self.adapter = FakeAdapter()
        self.service = MetaAdsService(
            self.authority, FakeStudio(), MetaAdsConfiguration(
                access_token="not-persisted", ad_account_id="123", page_id="456", instagram_actor_id="789",
            ), self.adapter,
        )
        self.preset = self.service.create_preset({
            "name": "Ukraine women", "countries": ["UA"], "age_min": 25,
            "age_max": 44, "gender": "women", "daily_budget_minor": 500,
        })["preset"]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def request(self, request_id: str = REQUEST_ID) -> dict[str, object]:
        return {
            "request_id": request_id, "creative_id": CREATIVE_ID, "version": 1,
            "preset_id": self.preset["preset_id"], "headline": "Natal idea",
            "primary_text": "Personal guidance\n\nFirst session",
            "welcome_message": "Вітаю! Хочу дізнатися більше.",
            "special_ad_categories": ["NONE"],
        }

    def website_request(self):
        from types import SimpleNamespace
        event = {"event_id": "01900000-0000-7000-8000-000000000011", "landing_version": 1, "landing_version_sha256": "a" * 64}
        publication = {"publication_id": "01900000-0000-7000-8000-000000000012", "current_event_id": event["event_id"], "events": [event], "status": "published", "canonical_url": "https://natal-service.com/la/example"}
        self.service.landing_publications = SimpleNamespace(get=lambda _: publication)
        request = self.request()
        request.pop("welcome_message")
        request.update(destination_type="WEBSITE", landing_event_id=event["event_id"])
        return request, publication

    def test_website_and_direct_campaigns_remain_separate_with_exact_landing_lineage(self):
        request, _ = self.website_request()
        website, _ = self.service.reserve(PROJECT_ID, request)
        direct, _ = self.service.reserve(PROJECT_ID, self.request("01900000-0000-7000-8000-000000000019"))
        self.assertNotEqual(website["experiment_id"], direct["experiment_id"])
        self.assertNotEqual(website["audience_id"], direct["audience_id"])
        self.assertEqual("OUTCOME_TRAFFIC", website["specification"]["objective"])
        self.assertNotIn("welcome_message", website["specification"])
        self.assertEqual("staged", self.service.execute(website["deployment_id"])["status"])
        self.assertEqual("staged", self.service.execute(direct["deployment_id"])["status"])
        self.assertEqual(2, len(self.service.workspace(PROJECT_ID)["deployments"]))
        self.assertTrue(any(edge["source_id"] == website["deployment_id"] and edge["target_id"] == request["landing_event_id"] for edge in self.store.list("edges")))

    def test_unpublished_landing_rejects_new_work_but_reconciles_existing_request(self):
        request, publication = self.website_request()
        reserved, _ = self.service.reserve(PROJECT_ID, request)
        publication["status"] = "unpublished"
        same, created = self.service.reserve(PROJECT_ID, request)
        self.assertFalse(created)
        self.assertEqual(reserved["deployment_id"], same["deployment_id"])
        self.assertEqual("failed", self.service.execute(reserved["deployment_id"])["status"])
        self.assertEqual(0, self.adapter.calls.count("campaign"))
        with self.assertRaises(RuntimeError):
            self.service.reserve(PROJECT_ID, {**request, "request_id": "01900000-0000-7000-8000-000000000018"})

    def test_idempotent_request_and_complete_staging(self) -> None:
        deployment, created = self.service.reserve(PROJECT_ID, self.request())
        self.assertTrue(created)
        same, created_again = self.service.reserve(PROJECT_ID, self.request())
        self.assertFalse(created_again)
        self.assertEqual(deployment["deployment_id"], same["deployment_id"])
        completed = self.service.execute(deployment["deployment_id"])
        self.assertEqual("staged", completed["status"])
        self.assertEqual("ad-1", completed["meta_ad_id"])
        self.assertEqual(["connection", "connection", "campaign", "ad_set", "image", "creative", "ad"], self.adapter.calls)
        serialized = json.dumps(self.store.list("meta_ads_deployments"))
        self.assertNotIn("not-persisted", serialized)

    def test_changed_account_after_reservation_cannot_create_objects(self):
        from dataclasses import replace
        deployment, _ = self.service.reserve(PROJECT_ID, self.request())
        self.service.configuration = replace(self.service.configuration, ad_account_id="999")
        before = list(self.adapter.calls)
        failed = self.service.execute(deployment["deployment_id"])
        self.assertEqual("failed", failed["status"])
        self.assertEqual(before, self.adapter.calls)

    def test_retry_continues_after_saved_image_without_duplicates(self) -> None:
        self.adapter.fail_once = "creative"
        deployment, _ = self.service.reserve(PROJECT_ID, self.request())
        failed = self.service.execute(deployment["deployment_id"])
        self.assertEqual("failed", failed["status"])
        self.assertEqual("image-hash", failed["meta_image_hash"])
        self.service.retry(PROJECT_ID, deployment["deployment_id"])
        completed = self.service.execute(deployment["deployment_id"])
        self.assertEqual("staged", completed["status"])
        self.assertEqual(1, self.adapter.calls.count("campaign"))
        self.assertEqual(1, self.adapter.calls.count("ad_set"))
        self.assertEqual(1, self.adapter.calls.count("image"))
        self.assertEqual(2, self.adapter.calls.count("creative"))

    def test_timeout_at_each_step_is_sanitized_and_restart_safe(self) -> None:
        for stage in ("connection", "campaign", "ad_set", "image", "creative", "ad"):
            with self.subTest(stage=stage), TemporaryDirectory() as temporary:
                store = LocalBriefStore(Path(temporary))
                store.append("projects", PROJECT_ID, {
                    "project_id": PROJECT_ID, "name": "Natal service", "created_at": utc_now(),
                })
                authority = LocalMetaAdsAuthority(store)
                adapter = FakeAdapter()
                service = MetaAdsService(
                    authority, FakeStudio(), MetaAdsConfiguration(
                        access_token="not-persisted", ad_account_id="123",
                        page_id="456", instagram_actor_id="789",
                    ), adapter,
                )
                preset = service.create_preset({
                    "name": "Ukraine", "countries": ["UA"], "age_min": 25,
                    "age_max": 44, "gender": "all", "daily_budget_minor": 500,
                })["preset"]
                request = self.request()
                request["preset_id"] = preset["preset_id"]
                deployment, _ = service.reserve(PROJECT_ID, request)
                adapter.fail_once = stage
                failed = service.execute(deployment["deployment_id"])
                self.assertEqual("failed", failed["status"])
                self.assertNotIn("timeout secret", json.dumps(failed["error"]))
                service.retry(PROJECT_ID, deployment["deployment_id"])
                completed = service.execute(deployment["deployment_id"])
                self.assertEqual("staged", completed["status"])
                self.assertEqual(3 if stage == "connection" else 2, adapter.calls.count(stage))

    def test_rejects_unapproved_and_cross_project_versions(self) -> None:
        request = self.request("01900000-0000-7000-8000-000000000006")
        request["version"] = 3
        with self.assertRaises(KeyError):
            self.service.reserve(PROJECT_ID, request)
        with self.assertRaises(KeyError):
            self.service.reserve("01900000-0000-7000-8000-000000000099", self.request())

    def test_request_id_cannot_be_reused_with_changed_input(self) -> None:
        self.service.reserve(PROJECT_ID, self.request())
        changed = self.request()
        changed["headline"] = "Different"
        with self.assertRaisesRegex(ValueError, "different input"):
            self.service.reserve(PROJECT_ID, changed)

    def test_missing_credentials_disable_staging_without_reserving_objects(self) -> None:
        disabled = MetaAdsService(self.authority, FakeStudio(), MetaAdsConfiguration(), None)
        self.assertFalse(disabled.connection()["configured"])
        with self.assertRaisesRegex(RuntimeError, "staging is disabled"):
            disabled.reserve(PROJECT_ID, self.request())
        self.assertIsNone(self.authority.get_experiment(PROJECT_ID))

    def test_same_preset_reuses_ad_set_and_changed_preset_creates_a_new_one(self) -> None:
        first, _ = self.service.reserve(PROJECT_ID, self.request())
        self.service.execute(first["deployment_id"])

        second_request = self.request("01900000-0000-7000-8000-000000000006")
        second_request["version"] = 2
        second_request["headline"] = "Natal idea 2"
        second, _ = self.service.reserve(PROJECT_ID, second_request)
        second = self.service.execute(second["deployment_id"])
        self.assertEqual(1, self.adapter.calls.count("ad_set"))
        self.assertEqual("creative-2", second["meta_creative_id"])
        self.assertEqual("ad-2", second["meta_ad_id"])

        changed_preset = self.service.create_preset({
            "name": "Ukraine women higher budget", "countries": ["UA"], "age_min": 25,
            "age_max": 44, "gender": "women", "daily_budget_minor": 700,
        })["preset"]
        third_request = self.request("01900000-0000-7000-8000-000000000007")
        third_request["version"] = 2
        third_request["headline"] = "Natal idea 2"
        third_request["preset_id"] = changed_preset["preset_id"]
        third, _ = self.service.reserve(PROJECT_ID, third_request)
        self.service.execute(third["deployment_id"])
        self.assertEqual(2, self.adapter.calls.count("ad_set"))
        self.assertEqual(1, self.adapter.calls.count("campaign"))


if __name__ == "__main__":
    unittest.main()
