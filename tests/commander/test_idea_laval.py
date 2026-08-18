from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest

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
    FixtureSearchProvider,
    FixtureTrendProvider,
    FixtureWebPageProvider,
    NullResearchSink,
    ProviderBundle,
)
from idea_generation.laval_repository import LavalRepository
from idea_generation.laval_service import LavalRunner, LavalService
from idea_generation.provider import MockLLMProvider
from idea_generation.seeds import load
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
        mission, contexts = load(Path("ideaGeneration"))
        cls.store.seed(mission, contexts)

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
        with TestClient(create_app(settings, lambda _chat, _text: None)) as client:
            self.assertEqual(403, client.post("/internal/web/laval/runs", json={"text": "idea"}).status_code)
            created = client.post(
                "/internal/web/laval/runs",
                headers=headers,
                json={"text": "A visible accountability proof journey.", "config": {"approval_mode": "automatic"}},
            )
            self.assertEqual(200, created.status_code)
            run_id = created.json()["run_id"]
            status = client.get(f"/internal/web/laval/runs/{run_id}", headers=headers)
            self.assertEqual("pending", status.json()["run"]["status"])
            exported = client.get(f"/internal/web/laval/runs/{run_id}/export?stage=OWNER_CAPTURE&format=json", headers=headers)
            self.assertEqual(200, exported.status_code)
            self.assertIn("raw_text", exported.text)


if __name__ == "__main__":
    unittest.main()
