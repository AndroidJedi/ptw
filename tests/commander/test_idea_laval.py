from __future__ import annotations

import importlib.util
import inspect
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from idea_generation.laval_context import ContextCompiler
from idea_generation.laval_domain import (
    LavalConfig,
    canonical_domain,
    canonical_url,
    competitor_score,
    deduplicate_queries,
    idea_score,
    input_hash,
    opportunity_score,
    trend_score,
)
from idea_generation.laval_pipeline import LavalPipeline
from idea_generation.laval_providers import (
    DataForSEOSearchProvider,
    FixtureSearchProvider,
    FixtureTrendProvider,
    FixtureWebPageProvider,
    NullResearchSink,
    ProviderBundle,
)
from idea_generation.laval_repository import LavalRepository
from idea_generation.laval_service import LavalRunner, LavalService
from idea_generation.provider import MockLLMProvider
from idea_generation.store import PostgresStore


class LavalDomainTests(unittest.TestCase):
    def test_default_country_contract_and_custom_country_validation(self) -> None:
        config = LavalConfig.from_mapping()
        self.assertEqual(["US", "GB", "DE", "NO", "DK"], [item["code"] for item in config.countries])
        custom = LavalConfig.from_mapping({"countries": [{"code": "CA", "language": "en"}]})
        self.assertEqual("CA", custom.countries[0]["code"])
        with self.assertRaises(ValueError):
            LavalConfig.from_mapping({"countries": [{"code": "Canada", "language": "en"}]})
        with self.assertRaises(ValueError):
            LavalConfig.from_mapping({"countries": ["CA"]})
        configured = LavalConfig.from_mapping({"trends": {"max_terms": 7, "windows": ["90d"]}})
        self.assertEqual(configured, LavalConfig.from_mapping(configured.to_dict()))

    def test_query_deduplication_preserves_country_and_language_variants(self) -> None:
        values = deduplicate_queries([
            {"country": "DE", "language": "de", "query": "  Ziel App "},
            {"country": "de", "language": "DE", "query": "ziel   app"},
            {"country": "DE", "language": "en", "query": "goal app"},
        ])
        self.assertEqual(2, len(values))

    def test_url_canonicalization_removes_tracking_query_and_www(self) -> None:
        self.assertEqual("https://example.com/path", canonical_url("HTTPS://WWW.Example.com/path/?utm=1"))
        self.assertEqual("example.com", canonical_domain("https://www.example.com/a"))

    def test_scoring_uses_the_specified_normalized_weights(self) -> None:
        config = LavalConfig.from_mapping()
        ones = {key: 1 for key in config.competitor_weights}
        self.assertEqual(1, competitor_score(ones, config))
        self.assertEqual(1, opportunity_score({key: 1 for key in config.opportunity_weights}, config))
        self.assertEqual(1, trend_score({key: 1 for key in config.trend_weights}, config))
        self.assertEqual(1, idea_score({key: 1 for key in config.idea_weights}, config))

    def test_input_hash_is_order_stable_and_changes_with_inputs(self) -> None:
        self.assertEqual(input_hash({"b": 2, "a": 1}), input_hash({"a": 1, "b": 2}))
        self.assertNotEqual(input_hash({"a": 1}), input_hash({"a": 2}))

    def test_fixture_providers_are_deterministic_and_visibly_marked(self) -> None:
        search = FixtureSearchProvider()
        first = search.search("accountability", country="US", language="en", depth=10)
        second = search.search("accountability", country="US", language="en", depth=10)
        self.assertEqual(first, second)
        self.assertTrue(first[0]["provider_metadata"]["fixture"])
        trends = FixtureTrendProvider().research("accountability", country="US", window="12m")
        self.assertIn("dimensions", trends)
        self.assertTrue(trends["raw"]["fixture"])

    def test_dataforseo_uses_normal_queue_and_conservative_half_cent_budget_units(self) -> None:
        provider = DataForSEOSearchProvider("api-login", "api-password", poll_interval=0)
        self.assertEqual(.0006, provider.estimate_cost(10))
        self.assertEqual(.0012, provider.estimate_cost(20))
        self.assertNotIn("/live/", provider.task_post_endpoint)
        self.assertNotIn("site:youtube.com", inspect.getsource(LavalPipeline._competitor_evidence))
        if importlib.util.find_spec("httpx") is None:
            self.skipTest("httpx is exercised by the built-image suite")

        class Response:
            def __init__(self, payload): self.payload = payload
            def raise_for_status(self): return None
            def json(self): return self.payload

        submitted_payload = {
            "status_code": 20000,
            "tasks": [{"id": "remote-task", "status_code": 20100, "cost": .0006}],
        }
        completed_payload = {
            "status_code": 20000,
            "tasks": [{
                "id": "remote-task", "status_code": 20000, "cost": .0006,
                "data": {"depth": 10},
                "result": [{"items": [{"type": "organic", "url": "https://example.com", "domain": "example.com", "title": "Example", "rank_absolute": 1}]}],
            }],
        }
        with (
            patch("httpx.post", return_value=Response(submitted_payload)) as post,
            patch("httpx.get", return_value=Response(completed_payload)) as get,
        ):
            tasks = provider.submit_many([{"key": "one", "query": "accountability app", "country": "US", "language": "en", "depth": 10}])
            rows = provider.fetch_result(tasks[0]["remote_task_id"])
        self.assertEqual("remote-task", tasks[0]["remote_task_id"])
        self.assertEqual("https://example.com", rows[0]["url"])
        self.assertEqual(1, post.call_args.kwargs["json"][0]["priority"])
        self.assertIn("task_get/advanced/remote-task", get.call_args.args[0])

    def test_context_compiler_enforces_synthesis_limits(self) -> None:
        config = LavalConfig.from_mapping({"synthesis": {"max_opportunities": 2, "max_trend_scores": 1, "max_trend_discoveries": 1}})
        packet = ContextCompiler(config).build_synthesis_context(
            {"problem": "p"},
            [{"id": str(index), "statement": "s"} for index in range(5)],
            [{"id": str(index), "term": "t"} for index in range(5)],
            [{"id": str(index), "discovered_term": "d"} for index in range(5)],
            ["pain"] * 20,
            ["loop"] * 20,
            ["invert"],
        )
        self.assertEqual(2, len(packet["opportunities"]))
        self.assertEqual(1, len(packet["trend_scores"]))
        self.assertEqual(1, len(packet["trend_discoveries"]))


@unittest.skipUnless(
    os.environ.get("IDEA_GENERATION_TEST_DATABASE_URL") and importlib.util.find_spec("psycopg"),
    "IDEA_GENERATION_TEST_DATABASE_URL and psycopg are required",
)
class LavalPostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = PostgresStore(os.environ["IDEA_GENERATION_TEST_DATABASE_URL"])
        cls.store.migrate(Path("db/idea_generation"))
        cls.store.seed_laval_mission()

    def setUp(self) -> None:
        with self.store.transaction() as connection:
            connection.execute("TRUNCATE laval_runs RESTART IDENTITY CASCADE")
        self.repository = LavalRepository(self.store)
        self.pipeline = LavalPipeline(
            self.repository,
            ProviderBundle(
                llm=MockLLMProvider(),
                search=FixtureSearchProvider(),
                web=FixtureWebPageProvider(),
                trends=FixtureTrendProvider(),
                research=NullResearchSink(),
            ),
        )

    def _config(self, approval_mode: str = "automatic") -> LavalConfig:
        return LavalConfig.from_mapping({
            "approval_mode": approval_mode,
            "trends": {"max_terms": 5, "windows": ["90d"]},
            "competitor_analysis": {"max_unique_competitors": 6},
        })

    def test_full_fixture_run_persists_every_stage_and_lineage(self) -> None:
        created = self.repository.create_run(
            "Public proof journeys turn doubters into durable motivation.",
            self._config(),
            actor="test",
        )
        result = self.pipeline.run(created["run_id"])
        self.assertEqual("completed", result["run"]["status"])
        self.assertEqual("demo_fixture", result["run"]["evidence_mode"])
        self.assertEqual(16, len(result["stages"]))
        self.assertTrue(all(item["status"] in {"completed", "partial"} for item in result["stages"]))
        country_slots = self.store.fetchone("SELECT count(*) n FROM laval_competitor_country_rankings WHERE run_id=%s", (created["run_id"],))["n"]
        self.assertEqual(15, country_slots)
        self.assertGreater(self.store.fetchone("SELECT count(*) n FROM laval_evidence WHERE run_id=%s", (created["run_id"],))["n"], 20)
        self.assertGreater(self.store.fetchone("SELECT count(*) n FROM laval_opportunities WHERE run_id=%s", (created["run_id"],))["n"], 0)
        self.assertGreater(self.store.fetchone("SELECT count(*) n FROM laval_trend_discoveries WHERE run_id=%s", (created["run_id"],))["n"], 0)
        self.assertEqual(21, self.store.fetchone("SELECT count(*) n FROM laval_idea_variants WHERE run_id=%s", (created["run_id"],))["n"])
        self.assertEqual(21, self.store.fetchone(
            """SELECT count(DISTINCT source_id) n FROM laval_lineage_edges
               WHERE run_id=%s AND source_kind='idea_variant' AND relation='transformed_by'""",
            (created["run_id"],),
        )["n"])
        self.assertEqual(7, self.store.fetchone("SELECT count(*) n FROM laval_transformation_operators WHERE run_id=%s", (created["run_id"],))["n"])
        self.assertEqual(21, self.store.fetchone(
            "SELECT count(*) n FROM laval_idea_variants WHERE run_id=%s AND cardinality(evidence_ids)>0",
            (created["run_id"],),
        )["n"])
        self.assertEqual(0, self.store.fetchone(
            "SELECT count(*) n FROM laval_evidence WHERE run_id=%s AND commander_source_id IS NOT NULL",
            (created["run_id"],),
        )["n"])
        self.assertEqual(0, self.store.fetchone(
            "SELECT count(*) n FROM laval_evidence WHERE run_id=%s AND source_type='trend'",
            (created["run_id"],),
        )["n"])
        self.assertGreater(self.store.fetchone("SELECT count(*) n FROM laval_lineage_edges WHERE run_id=%s", (created["run_id"],))["n"], 50)
        query_stage = self.repository.stage(created["run_id"], "QUERY_PLAN")
        self.assertGreater(query_stage["cost"]["input_tokens"], 0)
        final = self.repository.show(created["run_id"], "FINAL_SHORTLIST")["output"]
        self.assertEqual(10, len(final["shortlist"]))
        self.assertEqual(3, len(final["finalists"]))

    def test_manual_run_pauses_at_gate_and_resumes_after_approval(self) -> None:
        created = self.repository.create_run("Accountability circles for hard goals.", self._config("manual"), actor="test")
        first = self.pipeline.run(created["run_id"])
        self.assertEqual("paused", first["run"]["status"])
        self.assertEqual("COMPETITOR_SELECTION", first["run"]["current_stage"])
        self.repository.approve(created["run_id"], "COMPETITOR_SELECTION", actor="test")
        second = self.pipeline.run(created["run_id"])
        self.assertEqual("paused", second["run"]["status"])
        self.assertEqual("OPPORTUNITY_MATRIX", second["run"]["current_stage"])

    def test_live_search_without_trends_stops_before_trend_generation(self) -> None:
        created = self.repository.create_run(
            "Accountability circles backed by live search.", self._config(), actor="test",
            evidence_mode="live_search_pending_trends",
            provider_snapshot={"search": "dataforseo", "trends": "unavailable", "llm": "test"},
        )
        result = self.pipeline.run(created["run_id"])
        self.assertEqual("paused", result["run"]["status"])
        self.assertEqual("awaiting_trends_provider", result["run"]["awaiting_reason"])
        self.assertEqual("completed", self.repository.stage(created["run_id"], "OPPORTUNITY_MATRIX")["status"])
        self.assertEqual("pending", self.repository.stage(created["run_id"], "TREND_QUERY_PLAN")["status"])
        self.assertEqual(0, self.store.fetchone("SELECT count(*) n FROM laval_idea_variants WHERE run_id=%s", (created["run_id"],))["n"])
        service = LavalService(
            self.repository, LavalRunner(self.pipeline),
            readiness={"trends_live_ready": False, "trend_provider": "fixture"},
        )
        with self.assertRaisesRegex(RuntimeError, "not ready"):
            service.resume(created["run_id"])

    def test_completed_stage_artifact_and_provider_budget_are_database_invariants(self) -> None:
        created = self.repository.create_run("Budgeted live research.", self._config(), actor="test")
        with self.assertRaises(Exception):
            self.store.execute(
                "UPDATE laval_stage_runs SET status='completed',artifact=NULL WHERE run_id=%s AND stage='OWNER_CAPTURE' RETURNING 1",
                (created["run_id"],),
            )
        self.repository.reserve_provider_task(
            created["run_id"], "SERP_DISCOVERY", "large", "dataforseo",
            {"key": "large", "query": "q", "country": "US", "language": "en", "depth": 10}, .0039,
        )
        with self.assertRaisesRegex(RuntimeError, "reservation budget"):
            self.repository.reserve_provider_task(
                created["run_id"], "SERP_DISCOVERY", "over", "dataforseo",
                {"key": "over", "query": "q2", "country": "GB", "language": "en", "depth": 10}, .0002,
            )
        with self.assertRaises(Exception):
            self.store.execute(
                "UPDATE laval_runs SET max_spend_usd=0.006 WHERE id=%s RETURNING 1",
                (created["run_id"],),
            )

    def test_fixture_backfill_and_graph_exclusion_are_durable(self) -> None:
        created = self.repository.create_run("Fixture lineage must remain a demo.", self._config(), actor="test")
        self.store.execute(
            "UPDATE laval_stage_runs SET provider='fixture' WHERE run_id=%s AND stage='OWNER_CAPTURE' RETURNING 1",
            (created["run_id"],),
        )
        self.store.execute(
            "UPDATE laval_runs SET evidence_mode='live_complete',provider_snapshot='{}'::jsonb WHERE id=%s RETURNING 1",
            (created["run_id"],),
        )
        self.store.execute("DELETE FROM idea_schema_migrations WHERE version='006_laval_evidence_modes.sql' RETURNING 1")
        self.store.migrate(Path("db/idea_generation"))
        self.assertEqual("demo_fixture", self.repository.run(created["run_id"])["evidence_mode"])

        class RecordingResearch:
            name = "recording"
            calls = 0
            def record(self, _payload): self.calls += 1; return {"sources": {}}

        research = RecordingResearch()
        pipeline = LavalPipeline(self.repository, ProviderBundle(
            llm=MockLLMProvider(), search=FixtureSearchProvider(), web=FixtureWebPageProvider(),
            trends=FixtureTrendProvider(), research=research,
        ))
        result = pipeline._sync_evidence_graph(created["run_id"])
        self.assertTrue(result["demo_excluded"])
        self.assertEqual(0, research.calls)

    def test_submitted_dataforseo_task_resumes_without_reposting_or_duplicate_cost(self) -> None:
        created = self.repository.create_run(
            "Resume paid search safely.", self._config(), actor="test",
            evidence_mode="live_search_pending_trends", provider_snapshot={"search": "dataforseo"},
        )
        request = {"key": "US:en:q", "query": "accountability app", "country": "US", "language": "en", "depth": 10, "operation": "localized_serp"}
        task = self.repository.reserve_provider_task(created["run_id"], "SERP_DISCOVERY", request["key"], "dataforseo", request, .0006)
        self.repository.submit_provider_task(str(task["id"]), "remote-paid-once", .0006)

        class RestartedQueueProvider:
            name = "dataforseo"
            poll_timeout = 1
            poll_interval = 0
            submissions = 0
            fetches = 0
            def estimate_cost(self, _depth): return .0006
            def submit_many(self, _requests): self.submissions += 1; return []
            def fetch_result(self, remote_task_id):
                self.fetches += 1
                return [{"url": "https://example.com", "provider_metadata": {"task_id": remote_task_id}}]

        search = RestartedQueueProvider()
        pipeline = LavalPipeline(self.repository, ProviderBundle(
            llm=MockLLMProvider(), search=search, web=FixtureWebPageProvider(),
            trends=FixtureTrendProvider(), research=NullResearchSink(),
        ))
        first = pipeline._queued_search_batch(created["run_id"], "SERP_DISCOVERY", [request])
        second = pipeline._queued_search_batch(created["run_id"], "SERP_DISCOVERY", [request])
        self.assertEqual(first, second)
        self.assertEqual(0, search.submissions)
        self.assertEqual(1, search.fetches)
        self.assertEqual(1, self.store.fetchone(
            "SELECT count(*) n FROM laval_cost_events WHERE run_id=%s AND provider='dataforseo'",
            (created["run_id"],),
        )["n"])

    def test_country_rerun_marks_every_downstream_stage_stale(self) -> None:
        created = self.repository.create_run("Visible progress proof.", self._config(), actor="test")
        self.pipeline.run(created["run_id"], through_stage="COMPETITOR_SELECTION")
        self.repository.invalidate_from(created["run_id"], "SERP_DISCOVERY", country="DE")
        stages = {item["stage"]: item["status"] for item in self.repository.stages(created["run_id"])}
        self.assertEqual("pending", stages["SERP_DISCOVERY"])
        self.assertEqual("stale", stages["COMPETITOR_SELECTION"])
        self.assertEqual("stale", stages["FINAL_SHORTLIST"])

    def test_manual_competitor_add_and_reject_are_audited_and_invalidate_downstream(self) -> None:
        created = self.repository.create_run("Visible progress proof.", self._config(), actor="test")
        self.pipeline.run(created["run_id"], through_stage="COMPETITOR_SELECTION")
        service = LavalService(self.repository, LavalRunner(self.pipeline))
        added = service.override(created["run_id"], {
            "type": "competitor",
            "action": "add",
            "target_id": "https://manual-competitor.example/pricing",
            "reason": "owner observed it directly",
            "payload": {"url": "https://manual-competitor.example/pricing", "country": "DE"},
        }, actor="test-owner")
        competitor = self.store.fetchone("SELECT * FROM laval_competitors WHERE id=%s", (added["target_id"],))
        self.assertTrue(competitor["selected"])
        self.assertEqual("pending", self.repository.stage(created["run_id"], "COMPETITOR_EVIDENCE")["status"])
        service.override(created["run_id"], {
            "type": "competitor", "action": "reject", "target_id": added["target_id"], "reason": "not a direct competitor",
        }, actor="test-owner")
        competitor = self.store.fetchone("SELECT * FROM laval_competitors WHERE id=%s", (added["target_id"],))
        self.assertFalse(competitor["selected"])
        self.assertEqual(2, self.store.fetchone("SELECT count(*) n FROM laval_overrides WHERE run_id=%s", (created["run_id"],))["n"])

    def test_provider_retry_and_child_input_hash_cache_avoid_repeat_calls(self) -> None:
        class FlakySearch(FixtureSearchProvider):
            name = "flaky-fixture"

            def __init__(self) -> None:
                self.calls = 0
                self.seen: set[tuple[str, str, str]] = set()

            def search(self, query: str, *, country: str, language: str, depth: int):
                self.calls += 1
                key = (query, country, language)
                if key not in self.seen:
                    self.seen.add(key)
                    raise TimeoutError("first attempt")
                return super().search(query, country=country, language=language, depth=depth)

        search = FlakySearch()
        pipeline = LavalPipeline(
            self.repository,
            ProviderBundle(MockLLMProvider(), search, FixtureWebPageProvider(), FixtureTrendProvider(), NullResearchSink()),
        )
        config = LavalConfig.from_mapping({"approval_mode": "automatic", "countries": [{"code": "US", "language": "en"}]})
        created = self.repository.create_run("Accountability proof.", config, actor="test")
        pipeline.run(created["run_id"], through_stage="SERP_DISCOVERY")
        self.assertEqual(8, search.calls)
        attempts = self.store.fetchall("SELECT attempt FROM laval_stage_items WHERE run_id=%s AND stage='SERP_DISCOVERY'", (created["run_id"],))
        self.assertEqual({2}, {item["attempt"] for item in attempts})
        self.repository.ready(created["run_id"])
        pipeline._serp_discovery(created["run_id"], config, None)
        self.assertEqual(8, search.calls)

    def test_one_country_failure_is_partial_and_preserves_other_countries(self) -> None:
        class GermanFailure(FixtureSearchProvider):
            name = "partial-fixture"

            def search(self, query: str, *, country: str, language: str, depth: int):
                if country == "DE":
                    raise TimeoutError("DE unavailable")
                return super().search(query, country=country, language=language, depth=depth)

        pipeline = LavalPipeline(
            self.repository,
            ProviderBundle(MockLLMProvider(), GermanFailure(), FixtureWebPageProvider(), FixtureTrendProvider(), NullResearchSink()),
        )
        config = LavalConfig.from_mapping({"approval_mode": "automatic"})
        created = self.repository.create_run("Accountability proof.", config, actor="test")
        result = pipeline.run(created["run_id"], through_stage="SERP_DISCOVERY")
        stage = next(item for item in result["stages"] if item["stage"] == "SERP_DISCOVERY")
        self.assertEqual("partial", stage["status"])
        self.assertEqual(["DE"], stage["artifact"]["missing_countries"])
        self.assertEqual({"US", "GB", "NO", "DK"}, set(stage["artifact"]["countries"]))

    @unittest.skipUnless(importlib.util.find_spec("fastapi"), "FastAPI is required")
    def test_internal_web_api_authenticates_create_status_and_export(self) -> None:
        from fastapi.testclient import TestClient

        from idea_generation.api import create_app
        from idea_generation.config import Settings

        settings = Settings(
            database_url=os.environ["IDEA_GENERATION_TEST_DATABASE_URL"],
            telegram_token="test-token",
            allowed_chat_ids=frozenset({123}),
            allowed_user_ids=frozenset({456}),
            owner_gateway_token="owner-bridge",
        )
        headers = {"X-PTW-Owner-Gateway-Token": "owner-bridge"}
        with TestClient(create_app(settings)) as client:
            self.assertEqual(404, client.post("/internal/web/generations", json={}).status_code)
            self.assertEqual(404, client.post("/internal/telegram/update", json={}).status_code)
            self.assertEqual(403, client.post("/internal/web/laval/runs", json={"text": "idea"}).status_code)
            created = client.post(
                "/internal/web/laval/runs",
                headers=headers,
                json={"text": "A visible accountability proof journey.", "config": {"approval_mode": "automatic"}},
            )
            self.assertEqual(200, created.status_code)
            providers = client.get("/internal/web/laval/providers", headers=headers)
            self.assertFalse(providers.json()["search_live_ready"])
            blocked = client.post(
                "/internal/web/laval/runs", headers=headers,
                json={"text": "Must be live", "mode": "live", "config": {}},
            )
            self.assertEqual(400, blocked.status_code)
            run_id = created.json()["run_id"]
            status = client.get(f"/internal/web/laval/runs/{run_id}", headers=headers)
            self.assertEqual("pending", status.json()["run"]["status"])
            exported = client.get(f"/internal/web/laval/runs/{run_id}/export?stage=OWNER_CAPTURE&format=json", headers=headers)
            self.assertEqual(200, exported.status_code)
            self.assertIn("raw_text", exported.text)


if __name__ == "__main__":
    unittest.main()
