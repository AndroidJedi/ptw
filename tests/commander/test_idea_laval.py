from __future__ import annotations

import importlib.util
import inspect
import os
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

from commander.ids import new_uuid7
from idea_generation.laval_context import ContextCompiler
from idea_generation.laval_domain import (
    LavalConfig,
    canonical_domain,
    canonical_evidence_url,
    canonical_url,
    competitor_score,
    deduplicate_queries,
    idea_score,
    input_hash,
    market_signal_score,
    opportunity_score,
    trend_score,
)
from idea_generation.laval_pipeline import LavalPipeline, _opportunity_validation_error
from idea_generation.laval_fresh_stage import FreshStageRunner
from idea_generation.laval_notifications import LavalTelegramNotifier, format_laval_status_message
from idea_generation.laval_providers import (
    DataForSEOSearchProvider,
    FixtureSearchProvider,
    FixtureTrendProvider,
    FixtureWebPageProvider,
    NullResearchSink,
    ProviderBundle,
)
from idea_generation.laval_repository import LavalRepository
from idea_generation.laval_schemas import SCHEMAS, output_schema, strictly_describes_nested_values
from idea_generation.laval_service import LavalRunner, LavalService
from idea_generation.provider import MockLLMProvider
from idea_generation.store import PostgresStore


class LavalDomainTests(unittest.TestCase):
    def test_every_laval_language_schema_is_strict_at_every_nested_value(self) -> None:
        self.assertEqual(7, len(SCHEMAS))
        for mode, schema in SCHEMAS.items():
            with self.subTest(mode=mode):
                self.assertTrue(strictly_describes_nested_values(schema))
                required = next(iter(schema["properties"]))
                self.assertEqual(schema, output_schema(mode, required))

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
        self.assertEqual("https://youtube.com/watch?v=one", canonical_evidence_url("https://youtube.com/watch?v=one&utm_source=test"))
        self.assertNotEqual(canonical_evidence_url("https://youtube.com/watch?v=one"), canonical_evidence_url("https://youtube.com/watch?v=two"))

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

    def test_market_signal_v1_exact_formula_and_raw_counts(self) -> None:
        config = LavalConfig.from_mapping()
        source_types = ["reddit", "forum", "youtube", "review"]
        evidence = [{
            "id": f"00000000-0000-7000-8000-{index:012d}",
            "source_url": f"https://source{index}.example/item",
            "source_type": source_types[index % 4],
            "country": ["US", "GB", "DE", "NO", "DK"][index % 5],
            "competitor_id": f"10000000-0000-7000-8000-{index:012d}",
            "metadata": {
                "query_family": ["category", "problem", "alternative", "behavioral"][index % 4],
                "published_at": "2026-08-01T00:00:00Z",
                "purpose": "negative",
            },
        } for index in range(10)]
        result = market_signal_score(
            evidence,
            [item["id"] for item in evidence],
            config,
            as_of=datetime(2026, 8, 19, tzinfo=timezone.utc),
        )
        self.assertEqual(1, result["aggregate_score"])
        self.assertEqual({key: 1 for key in result["components"]}, result["components"])
        self.assertEqual(10, result["raw_counts"]["relevant_unique_sources"])
        self.assertEqual("market-signal-v1", result["normalization_version"])
        self.assertNotIn("coverage", result)

    def test_market_signal_missing_data_is_zero_and_explicit(self) -> None:
        result = market_signal_score(
            [], [], LavalConfig.from_mapping(),
            as_of=datetime(2026, 8, 19, tzinfo=timezone.utc),
        )
        self.assertEqual(0, result["aggregate_score"])
        self.assertEqual("no_data", result["data_status"]["overall"])
        self.assertTrue(all(value == 0 for value in result["components"].values()))

    def test_market_signal_deduplicates_urls_and_never_invents_dates(self) -> None:
        evidence = [
            {"id": "e-1", "source_url": "https://example.com/item?tracking=1", "source_type": "reddit", "country": "US", "metadata": {"query_family": "problem", "purpose": "negative"}},
            {"id": "e-2", "source_url": "https://www.example.com/item", "source_type": "reddit", "country": "GB", "retrieved_at": "2026-08-18T00:00:00Z", "metadata": {"query_family": "problem", "purpose": "negative"}},
        ]
        result = market_signal_score(
            evidence, ["e-1", "e-2"], LavalConfig.from_mapping(),
            as_of=datetime(2026, 8, 19, tzinfo=timezone.utc),
        )
        self.assertEqual(1, result["raw_counts"]["evaluated_unique_sources"])
        self.assertEqual(1, result["raw_counts"]["relevant_unique_sources"])
        self.assertEqual(0, result["raw_counts"]["recent_dated_sources_365d"])
        self.assertEqual("no_data", result["data_status"]["components"]["recent_content_activity"])

    def test_non_product_serp_pages_are_not_promoted_as_competitors(self) -> None:
        examples = [
            {"domain": "quora.com", "title": "How do I prove them wrong?", "snippet": "A discussion"},
            {"domain": "english.stackexchange.com", "title": "Grammar of prove them wrong", "snippet": "Question"},
            {"domain": "powerthesaurus.org", "title": "Prove them wrong synonyms", "snippet": "Words"},
            {"domain": "linkedin.com", "title": "Software testing: prove them wrong", "snippet": "A post"},
        ]
        self.assertTrue(all(LavalPipeline._result_type(item) not in {"direct_product", "adjacent_product", "substitute"} for item in examples))
        self.assertEqual("direct_product", LavalPipeline._result_type({
            "domain": "example.com", "title": "Public accountability app", "snippet": "A goal challenge platform",
        }))

    def test_market_signal_score_is_fully_reproducible(self) -> None:
        evidence = [{"id": "e-1", "source_url": "https://example.com", "source_type": "forum", "country": "US", "metadata": {"query_family": "category", "published_at": "2026-01-01T00:00:00Z"}}]
        config = LavalConfig.from_mapping()
        as_of = datetime(2026, 8, 19, tzinfo=timezone.utc)
        self.assertEqual(
            market_signal_score(evidence, ["e-1"], config, as_of=as_of),
            market_signal_score(evidence, ["e-1"], config, as_of=as_of),
        )

    def test_fixture_providers_are_deterministic_and_visibly_marked(self) -> None:
        search = FixtureSearchProvider()
        first = search.search("accountability", country="US", language="en", depth=10)
        second = search.search("accountability", country="US", language="en", depth=10)
        self.assertEqual(first, second)
        self.assertTrue(first[0]["provider_metadata"]["fixture"])
        trends = FixtureTrendProvider().research("accountability", country="US", window="12m")
        self.assertIn("dimensions", trends)
        self.assertTrue(trends["raw"]["fixture"])

    def test_dataforseo_uses_normal_queue_and_conservative_five_cent_budget_units(self) -> None:
        provider = DataForSEOSearchProvider("api-login", "api-password", poll_interval=0)
        self.assertEqual(3600, provider.poll_timeout)
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

    def test_telegram_status_projection_contains_error_cost_and_every_stage(self) -> None:
        stages = [
            {"stage": f"STAGE_{index}", "ordinal": index, "status": "failed" if index == 3 else "completed" if index < 3 else "pending", "attempt": 1}
            for index in range(16)
        ]
        message = format_laval_status_message({
            "run": {
                "id": "01234567-89ab-7def-8123-456789abcdef", "status": "failed",
                "current_stage": "STAGE_3", "evidence_mode": "live_search_pending_trends",
                "error_text": "provider queue timeout", "approval_gates": [],
            },
            "stages": stages,
            "cost": {"provider_actual_usd": .0192, "provider_reserved_usd": .0192, "max_spend_usd": .05},
            "recovery": {"provider_tasks": {"total": 32, "completed": 31, "submitted": 1, "persisted_remote_ids": 32}},
        }, "failed")
        self.assertIn("provider queue timeout", message)
        self.assertIn("31/32 completed", message)
        self.assertIn("does not repost or rebill", message)
        self.assertIn("S00 STAGE_0 — completed", message)
        self.assertIn("S15 STAGE_15 — pending", message)
        self.assertIn(
            "?page=ideas&run=01234567-89ab-7def-8123-456789abcdef",
            message,
        )

    def test_runner_automatically_notifies_terminal_run_state(self) -> None:
        class Repository:
            def run(self, _run_id): return {"status": "failed"}

        class Pipeline:
            repository = Repository()
            def run(self, **_kwargs): raise RuntimeError("already persisted")

        class Notifier:
            calls = []
            def send(self, run_id, event): self.calls.append((run_id, event))

        notifier = Notifier()
        runner = LavalRunner(Pipeline(), notifier)
        runner._execute(run_id="run-1")
        self.assertEqual([("run-1", "failed")], notifier.calls)

    def test_runner_rejects_a_second_concurrent_laval_run(self) -> None:
        class Pipeline:
            pass

        class ActiveThread:
            def is_alive(self): return True

        runner = LavalRunner(Pipeline())
        runner._threads["active-run"] = ActiveThread()
        with self.assertRaisesRegex(RuntimeError, "active-run"):
            runner.start("conflicting-run")
        self.assertEqual(("active-run",), runner.active_run_ids())

    def test_fresh_stage_runner_never_passes_stage_history_and_sessions_are_distinct(self) -> None:
        class Repository:
            audits = []
            def record_llm_invocation(self, *args, **kwargs):
                self.audits.append({"args": args, **kwargs})

        class Provider:
            model_name = "test-model"
            calls = []
            last_invocation = {}
            def generate_structured(self, mode, _prompt, payload, _schema):
                self.calls.append((mode, payload))
                self.last_invocation = {"session_id": f"provider-{len(self.calls)}"}
                return {"items": []}

        repository, provider = Repository(), Provider()
        runner = FreshStageRunner(repository, provider)
        runner.run("run", "STAGE_A", "mode_a", "prompt A", {"stage_a_input": 1}, "items", prompt_template_version="a-v1")
        runner.run("run", "STAGE_B", "mode_b", "prompt B", {"stage_b_input": 2}, "items", prompt_template_version="b-v1")

        self.assertEqual([{"stage_a_input": 1}, {"stage_b_input": 2}], [payload for _, payload in provider.calls])
        self.assertNotEqual(repository.audits[0]["session_id"], repository.audits[1]["session_id"])
        self.assertEqual(["provider-1", "provider-2"], [item["provider_session_id"] for item in repository.audits])

    def test_fresh_stage_runner_fails_closed_when_live_fallback_is_disabled(self) -> None:
        class Repository:
            audits = []
            def record_llm_invocation(self, *args, **kwargs):
                self.audits.append({"args": args, **kwargs})

        class Provider:
            model_name = "test-model"
            last_invocation = {}
            calls = 0
            def generate_structured(self, *_args, **_kwargs):
                self.calls += 1
                raise RuntimeError("invalid_json_schema")

        repository, provider = Repository(), Provider()
        runner = FreshStageRunner(repository, provider)
        with self.assertRaisesRegex(RuntimeError, "invalid_json_schema"):
            runner.run(
                "run", "OWNER_DNA", "laval_owner_dna", "prompt", {"raw_text": "idea"},
                "owner_dna", prompt_template_version="laval_owner_dna-v2-strict", allow_fallback=False,
            )
        self.assertEqual(2, provider.calls)
        self.assertEqual(["failed", "failed"], [item["result_status"] for item in repository.audits])
        self.assertEqual(["RuntimeError", "RuntimeError"], [item["error_type"] for item in repository.audits])
        self.assertIn("automatic-retry-2", repository.audits[1]["prompt_template_version"])

    def test_fresh_stage_runner_automatically_retries_semantic_failure_once(self) -> None:
        class Repository:
            audits = []
            def record_llm_invocation(self, *args, **kwargs):
                self.audits.append({"args": args, **kwargs})

        class Provider:
            model_name = "test-model"
            last_invocation = {}
            prompts = []
            def generate_structured(self, _mode, prompt, _payload, _schema):
                self.prompts.append(prompt)
                self.last_invocation = {"session_id": f"provider-{len(self.prompts)}"}
                return {"items": [] if len(self.prompts) == 1 else [{"id": "valid"}]}

        repository, provider = Repository(), Provider()
        result = FreshStageRunner(repository, provider).run(
            "run", "STAGE", "mode", "prompt", {"input": 1}, "items",
            prompt_template_version="mode-v3-strict-retry", allow_fallback=False,
            validator=lambda value: bool(value["items"]),
        )

        self.assertEqual([{"id": "valid"}], result["items"])
        self.assertEqual(2, len(provider.prompts))
        self.assertIn("Automatic retry", provider.prompts[1])
        self.assertEqual(["failed", "success"], [item["result_status"] for item in repository.audits])
        self.assertNotEqual(repository.audits[0]["session_id"], repository.audits[1]["session_id"])
        self.assertEqual(["provider-1", "provider-2"], [item["provider_session_id"] for item in repository.audits])

    def test_opportunity_validator_accepts_complaint_cluster_evidence_from_context(self) -> None:
        dossiers = [{
            "competitor_id": "competitor-1",
            "evidence_ids": ["top-level-evidence"],
            "complaint_clusters": [{"evidence_ids": ["cluster-evidence"]}],
        }]
        opportunity = {
            "opportunities": [{
                "statement": "A supported opportunity",
                "competitor_ids": ["competitor-1"],
                "evidence_ids": ["cluster-evidence"],
            }],
        }

        self.assertIsNone(_opportunity_validation_error(opportunity, dossiers))
        opportunity["opportunities"][0]["evidence_ids"] = ["invented-evidence"]
        error = _opportunity_validation_error(opportunity, dossiers)
        self.assertIn("rows 1", error)
        self.assertIn("unknown evidence IDs=1", error)

    def test_bridge_default_model_uses_codex_cli_default_without_model_override(self) -> None:
        from idea_generation.provider import BridgeProvider

        provider = BridgeProvider("http://bridge", "token")
        captured = {}

        def request(_url, payload, _headers):
            if payload is not None:
                captured.update(payload)
                return {"request_id": 1}
            return {
                "status": "completed",
                "result": {
                    "response": {"classifications": []},
                    "invocation": {"session_id": "fresh", "model": "codex-cli-default"},
                },
            }

        provider._request = request
        result = provider.generate_structured(
            "laval_market_signal_relevance", "binary", {}, {"type": "object"}
        )
        self.assertEqual({"classifications": []}, result)
        self.assertNotIn("model", captured)
        self.assertEqual("codex-cli-default", provider.model_name)

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
        with cls.store.transaction() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS commander_outbox(
                       id UUID PRIMARY KEY, topic TEXT NOT NULL, aggregate_id UUID, payload JSONB NOT NULL,
                       created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), published_at TIMESTAMPTZ,
                       attempts INTEGER NOT NULL DEFAULT 0, available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                       last_error TEXT
                   )"""
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.store.close()

    def setUp(self) -> None:
        with self.store.transaction() as connection:
            connection.execute("TRUNCATE laval_runs RESTART IDENTITY CASCADE")
            connection.execute("DELETE FROM commander_outbox WHERE payload->>'source'='idea-laval'")
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
        self.assertGreater(self.store.fetchone("SELECT count(*) n FROM laval_market_signal_scores WHERE run_id=%s", (created["run_id"],))["n"], 0)
        self.assertEqual(24, self.store.fetchone("SELECT count(*) n FROM laval_idea_variants WHERE run_id=%s", (created["run_id"],))["n"])
        self.assertEqual(24, self.store.fetchone(
            """SELECT count(DISTINCT source_id) n FROM laval_lineage_edges
               WHERE run_id=%s AND source_kind='idea_variant' AND relation='transformed_by'""",
            (created["run_id"],),
        )["n"])
        self.assertEqual(8, self.store.fetchone("SELECT count(*) n FROM laval_transformation_operators WHERE run_id=%s", (created["run_id"],))["n"])
        self.assertEqual(24, self.store.fetchone(
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
        opportunity_targets = self.repository.show(created["run_id"], "OPPORTUNITY_MATRIX")["override_targets"]
        self.assertTrue(opportunity_targets)
        self.assertEqual({"opportunity"}, {item["kind"] for item in opportunity_targets})
        market = self.repository.show(created["run_id"], "MARKET_SIGNAL_GATE")["output"]
        self.assertFalse(market["google_trends_required"])
        self.assertTrue(all("formula" in item and "raw_counts" in item and "evidence_ids" in item for item in market["scores"]))
        self.assertEqual(0, self.store.fetchone("SELECT count(*) n FROM laval_evidence WHERE run_id=%s AND source_type='trend'", (created["run_id"],))["n"])

        invocations = self.store.fetchall(
            "SELECT stage,session_id,provider_session_id FROM laval_llm_invocations WHERE run_id=%s ORDER BY created_at,id",
            (created["run_id"],),
        )
        generator = next(item for item in invocations if item["stage"] == "IDEA_EXPANSION")
        evaluator = next(item for item in invocations if item["stage"] == "IDEA_EVALUATION")
        self.assertNotEqual(generator["session_id"], evaluator["session_id"])
        self.assertNotEqual(generator["provider_session_id"], evaluator["provider_session_id"])
        self.assertTrue(all("history" not in payload and "messages" not in payload for _, payload in self.pipeline.providers.llm.calls))

    def test_live_language_failure_stops_before_paid_search_and_is_visible_as_invalid(self) -> None:
        pipeline = LavalPipeline(
            self.repository,
            ProviderBundle(
                llm=MockLLMProvider([
                    RuntimeError("invalid_json_schema"),
                    RuntimeError("invalid_json_schema"),
                ]),
                search=FixtureSearchProvider(),
                web=FixtureWebPageProvider(),
                trends=FixtureTrendProvider(),
                research=NullResearchSink(),
            ),
        )
        created = self.repository.create_run(
            "A live concept that must fail closed.",
            self._config(),
            actor="test",
            evidence_mode="live_market_signals",
            provider_snapshot={"search": "dataforseo", "llm": "bridge"},
        )
        with self.assertRaisesRegex(RuntimeError, "invalid_json_schema"):
            pipeline.run(created["run_id"])

        status = self.repository.status(created["run_id"])
        self.assertEqual("failed", status["run"]["status"])
        self.assertEqual("failed", self.repository.stage(created["run_id"], "OWNER_DNA")["status"])
        self.assertEqual("invalid", status["quality"]["verdict"])
        self.assertEqual(2, status["quality"]["failed"])
        self.assertEqual(2, status["quality"]["unresolved_failures"])
        self.assertEqual(0, self.store.fetchone(
            "SELECT count(*) n FROM laval_provider_tasks WHERE run_id=%s",
            (created["run_id"],),
        )["n"])

    def test_historical_live_fallback_is_not_presented_as_a_valid_artifact(self) -> None:
        created = self.repository.create_run(
            "Preserve a historical fallback as invalid history.",
            self._config(),
            evidence_mode="live_market_signals",
            provider_snapshot={"search": "dataforseo", "llm": "bridge"},
        )
        self.repository.record_llm_invocation(
            created["run_id"], "OWNER_DNA", "laval_owner_dna",
            prompt_template_version="legacy-v1", context_hash="a" * 64,
            output_schema_hash="b" * 64, model="codex-cli-default",
            session_id=str(new_uuid7()), provider_session_id=None,
            result_status="fallback", error_type="RuntimeError",
        )

        status = self.repository.status(created["run_id"])
        shown = self.repository.show(created["run_id"], "OWNER_CAPTURE")
        self.assertEqual("invalid", status["quality"]["verdict"])
        self.assertEqual(0, status["quality"]["success"])
        self.assertEqual(1, status["quality"]["fallback"])
        self.assertEqual("invalid", shown["quality"]["run"]["verdict"])

    def test_successful_automatic_retry_is_verified_but_retains_failed_attempt_audit(self) -> None:
        created = self.repository.create_run(
            "Recover one live language call automatically.",
            self._config(),
            evidence_mode="live_market_signals",
            provider_snapshot={"search": "dataforseo", "llm": "bridge"},
        )
        run_id = created["run_id"]
        self.repository.start_stage(run_id, "OWNER_DNA", "digest", provider="bridge", model="model")
        for result_status, error_type in (("failed", "InvalidStructuredResponse"), ("success", None)):
            self.repository.record_llm_invocation(
                run_id, "OWNER_DNA", "laval_owner_dna",
                prompt_template_version="laval_owner_dna-v3-strict-retry",
                context_hash="a" * 64, output_schema_hash="b" * 64,
                model="codex-cli-default", session_id=str(new_uuid7()),
                provider_session_id=str(new_uuid7()), result_status=result_status,
                error_type=error_type,
            )
        self.repository.complete_stage(run_id, "OWNER_DNA", {"owner_dna": {"problem": "valid"}})

        quality = self.repository.llm_quality(run_id)
        owner = next(item for item in quality["by_stage"] if item["stage"] == "OWNER_DNA")
        self.assertEqual("verified", owner["verdict"])
        self.assertEqual(1, owner["recovered_failures"])
        self.assertEqual(0, owner["unresolved_failures"])
        self.assertEqual(1, quality["recovered_failures"])
        self.assertEqual(0, quality["unresolved_failures"])

    def test_live_dossier_retry_replaces_current_attempt_quality_without_losing_audit(self) -> None:
        class FailSecondDossierOnce:
            model_name = "mock-v1"
            last_invocation = {}
            def __init__(self):
                self.delegate = MockLLMProvider()
                self.dossiers = 0
                self.failures = 0
            def generate_structured(self, mode, prompt, payload, schema):
                if mode == "laval_competitor_dossier":
                    self.dossiers += 1
                    if self.dossiers in {2, 3} and self.failures < 2:
                        self.failures += 1
                        raise RuntimeError("transient dossier failure")
                result = self.delegate.generate_structured(mode, prompt, payload, schema)
                self.last_invocation = self.delegate.last_invocation
                return result

        llm = FailSecondDossierOnce()
        pipeline = LavalPipeline(
            self.repository,
            ProviderBundle(
                llm=llm, search=FixtureSearchProvider(), web=FixtureWebPageProvider(),
                trends=FixtureTrendProvider(), research=NullResearchSink(),
            ),
        )
        created = self.repository.create_run(
            "Retry a partially completed live dossier stage.", self._config(),
            evidence_mode="live_market_signals",
            provider_snapshot={"search": "fixture", "llm": "mock"},
        )
        with self.assertRaisesRegex(RuntimeError, "transient dossier failure"):
            pipeline.run(created["run_id"], through_stage="COMPETITOR_DOSSIERS")
        self.repository.ready(created["run_id"], through_stage="COMPETITOR_DOSSIERS")
        resumed = pipeline.run(created["run_id"], through_stage="COMPETITOR_DOSSIERS")

        self.assertEqual("paused", resumed["run"]["status"])
        self.assertEqual("completed", self.repository.stage(created["run_id"], "COMPETITOR_DOSSIERS")["status"])
        stage_quality = next(item for item in resumed["quality"]["by_stage"] if item["stage"] == "COMPETITOR_DOSSIERS")
        self.assertEqual(0, stage_quality["failed"])
        self.assertGreater(stage_quality["success"], 1)
        self.assertEqual(2, self.store.fetchone(
            "SELECT count(*) n FROM laval_llm_invocations WHERE run_id=%s AND stage='COMPETITOR_DOSSIERS' AND result_status='failed'",
            (created["run_id"],),
        )["n"])

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
            pipeline_version="legacy-trends-v2",
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

    def test_owner_upgrade_to_market_signals_preserves_paid_tasks_cost_and_evidence(self) -> None:
        created = self.repository.create_run(
            "Resume saved live work without Google Trends.", self._config(), actor="test",
            evidence_mode="live_search_pending_trends",
            provider_snapshot={"search": "dataforseo", "trends": "unavailable"},
            pipeline_version="legacy-trends-v2",
        )
        run_id = created["run_id"]
        self.pipeline.run(run_id)
        request = {"key": "saved", "query": "saved", "country": "US", "language": "en", "depth": 10, "operation": "localized_serp"}
        task = self.repository.reserve_provider_task(run_id, "SERP_DISCOVERY", "saved", "dataforseo", request, .0006)
        self.repository.submit_provider_task(str(task["id"]), "paid-task-preserved", .0006)
        evidence_before = self.store.fetchone("SELECT count(*) n FROM laval_evidence WHERE run_id=%s", (run_id,))["n"]
        service = LavalService(self.repository, type("Runner", (), {"start": lambda self, *_args, **_kwargs: True})())

        result = service.resume_with_market_signals(run_id, actor="firebase:owner")

        self.assertTrue(result["started"])
        upgraded = self.repository.run(run_id)
        self.assertEqual("market_signals_v2", upgraded["pipeline_version"])
        self.assertEqual("live_market_signals", upgraded["evidence_mode"])
        self.assertEqual("market-signal-v1", upgraded["config"]["market_signals"]["normalization_version"])
        self.assertEqual(0.20, upgraded["config"]["market_signal_weights"]["cross_country_recurrence"])
        self.assertEqual("MARKET_SIGNAL_PLAN", upgraded["current_stage"])
        self.assertEqual("paid-task-preserved", self.repository.provider_task(run_id, "SERP_DISCOVERY", "saved")["remote_task_id"])
        self.assertEqual(evidence_before, self.store.fetchone("SELECT count(*) n FROM laval_evidence WHERE run_id=%s", (run_id,))["n"])
        self.assertEqual(1, self.store.fetchone("SELECT count(*) n FROM laval_run_actions WHERE run_id=%s AND action='resume_with_market_signals'", (run_id,))["n"])

    def test_llm_invocation_audit_is_append_only(self) -> None:
        created = self.repository.create_run("append-only audit", LavalConfig())
        invocation_id = self.repository.record_llm_invocation(
            created["run_id"], "OWNER_DNA", "laval_owner_dna",
            prompt_template_version="laval-v3", context_hash="a" * 64,
            output_schema_hash="b" * 64, model="mock-v1",
            session_id=str(new_uuid7()), provider_session_id=str(new_uuid7()),
            result_status="success", error_type=None,
        )
        with self.assertRaises(Exception):
            self.store.execute(
                "UPDATE laval_llm_invocations SET result_status='failed' WHERE id=%s RETURNING 1",
                (invocation_id,),
            )
        with self.assertRaises(Exception):
            self.store.execute(
                "DELETE FROM laval_llm_invocations WHERE id=%s RETURNING 1",
                (invocation_id,),
            )

    def test_completed_legacy_trends_run_remains_immutable_history(self) -> None:
        created = self.repository.create_run(
            "Completed Trends history must remain readable.", self._config(), actor="test",
            evidence_mode="live_complete",
            provider_snapshot={"search": "fixture", "trends": "fixture"},
            pipeline_version="legacy-trends-v2",
        )
        run_id = created["run_id"]
        before = self.pipeline.run(run_id)
        stage_names = [item["stage"] for item in before["stages"]]
        trend_count = self.store.fetchone("SELECT count(*) n FROM laval_trend_scores WHERE run_id=%s", (run_id,))["n"]

        self.store.migrate(Path("db/idea_generation"))
        after = self.repository.status(run_id)

        self.assertEqual("completed", after["run"]["status"])
        self.assertEqual("legacy-trends-v2", after["run"]["pipeline_version"])
        self.assertEqual(stage_names, [item["stage"] for item in after["stages"]])
        self.assertIn("GOOGLE_TRENDS_RESEARCH", stage_names)
        self.assertEqual(trend_count, self.store.fetchone("SELECT count(*) n FROM laval_trend_scores WHERE run_id=%s", (run_id,))["n"])
        self.assertFalse(after["resume_with_market_signals_available"])

    def test_completed_stage_artifact_and_provider_budget_are_database_invariants(self) -> None:
        created = self.repository.create_run("Budgeted live research.", self._config(), actor="test")
        with self.assertRaises(Exception):
            self.store.execute(
                "UPDATE laval_stage_runs SET status='completed',artifact=NULL WHERE run_id=%s AND stage='OWNER_CAPTURE' RETURNING 1",
                (created["run_id"],),
            )
        self.repository.reserve_provider_task(
            created["run_id"], "SERP_DISCOVERY", "large", "dataforseo",
            {"key": "large", "query": "q", "country": "US", "language": "en", "depth": 10}, .039,
        )
        with self.assertRaisesRegex(RuntimeError, "reservation budget"):
            self.repository.reserve_provider_task(
                created["run_id"], "SERP_DISCOVERY", "over", "dataforseo",
                {"key": "over", "query": "q2", "country": "GB", "language": "en", "depth": 10}, .002,
            )
        with self.assertRaises(Exception):
            self.store.execute(
                "UPDATE laval_runs SET max_spend_usd=0.06 WHERE id=%s RETURNING 1",
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

    def test_failed_stage_exposes_recovery_report_and_owner_resume_audit(self) -> None:
        created = self.repository.create_run("Recover paid search visibly.", self._config(), actor="test")
        run_id = created["run_id"]
        self.repository.start_stage(run_id, "SERP_DISCOVERY", "digest", provider="dataforseo")
        for key in ("one", "two"):
            request = {"key": key, "query": key, "country": "US", "language": "en", "depth": 10, "operation": "localized_serp"}
            task = self.repository.reserve_provider_task(run_id, "SERP_DISCOVERY", key, "dataforseo", request, .0006)
            self.repository.submit_provider_task(str(task["id"]), f"remote-{key}", .0006)
            if key == "one":
                self.repository.complete_provider_task(str(task["id"]), {"results": []})
                self.repository.record_provider_cost_once(str(task["id"]), "localized_serp")
        self.repository.fail_stage(run_id, "SERP_DISCOVERY", TimeoutError("one queued task is still pending"))
        recovery = self.repository.status(run_id)["recovery"]
        self.assertTrue(recovery["available"])
        self.assertEqual("TimeoutError", recovery["failure"]["type"])
        self.assertEqual(2, recovery["provider_tasks"]["persisted_remote_ids"])
        self.assertEqual(1, recovery["provider_tasks"]["completed"])
        self.assertEqual(1, recovery["provider_tasks"]["submitted"])

        class RecordingRunner:
            def start(self, _run_id, **_kwargs): return True

        service = LavalService(self.repository, RecordingRunner())
        resumed = service.resume(run_id, actor="firebase:owner")
        self.assertTrue(resumed["started"])
        self.assertFalse(resumed["resume_behavior"]["reposts_submitted_tasks"])
        recovered_report = self.repository.status(run_id)["recovery"]
        self.assertEqual("SERP_DISCOVERY", recovered_report["stage"])
        self.assertEqual(2, recovered_report["provider_tasks"]["persisted_remote_ids"])
        action = self.store.fetchone(
            "SELECT * FROM laval_run_actions WHERE run_id=%s AND action='resume_requested'",
            (run_id,),
        )
        self.assertEqual("firebase:owner", action["actor"])
        self.assertEqual("started", action["outcome"])

    def test_owner_can_send_telegram_snapshot_directly_without_outbox(self) -> None:
        created = self.repository.create_run("Send visible status.", self._config(), actor="test")
        run_id = created["run_id"]

        class Telegram:
            calls = []

            def send_message(self, chat_id, text):
                self.calls.append((chat_id, text))
                return {"message_id": 987}

        telegram = Telegram()
        notifier = LavalTelegramNotifier(self.repository, (123,), telegram)
        service = LavalService(self.repository, LavalRunner(self.pipeline), notifier=notifier)
        result = service.notify(run_id, actor="firebase:owner")
        self.assertEqual(1, result["sent"])
        self.assertEqual(0, result["queued"])
        self.assertEqual(123, telegram.calls[0][0])
        self.assertIn("S00 OWNER_CAPTURE — completed", telegram.calls[0][1])
        self.assertIn("S15 FINAL_SHORTLIST — pending", telegram.calls[0][1])
        row = self.store.fetchone(
            "SELECT action,outcome,details FROM laval_run_actions "
            "WHERE run_id=%s AND action='telegram_status_sent' ORDER BY created_at DESC LIMIT 1",
            (run_id,),
        )
        self.assertEqual("sent", row["outcome"])
        self.assertEqual(987, row["details"]["telegram_message_id"])

    def test_automatic_telegram_transition_is_deduplicated_without_polling(self) -> None:
        created = self.repository.create_run("Send one transition.", self._config(), actor="test")
        run_id = created["run_id"]

        class Telegram:
            calls = []

            def send_message(self, chat_id, text):
                self.calls.append((chat_id, text))
                return {"message_id": len(self.calls)}

        telegram = Telegram()
        notifier = LavalTelegramNotifier(self.repository, (123,), telegram)
        self.assertEqual(1, notifier.send(run_id, "paused"))
        self.assertEqual(0, notifier.send(run_id, "paused"))
        self.assertEqual(1, len(telegram.calls))
        self.assertEqual(
            0,
            int(self.store.fetchone(
                "SELECT count(*) n FROM commander_outbox WHERE topic='telegram.send_message'"
            )["n"]),
        )

    def test_direct_telegram_failure_is_bounded_and_audited(self) -> None:
        created = self.repository.create_run("Audit failed send.", self._config(), actor="test")
        run_id = created["run_id"]

        class Telegram:
            def send_message(self, _chat_id, _text):
                raise TimeoutError("secret provider response must not be stored")

        notifier = LavalTelegramNotifier(self.repository, (123,), Telegram())
        self.assertEqual(0, notifier.send(run_id, "failed"))
        row = self.store.fetchone(
            "SELECT details FROM laval_run_actions "
            "WHERE run_id=%s AND action='telegram_status_send_failed'",
            (run_id,),
        )
        self.assertEqual("TimeoutError", row["details"]["error_type"])
        self.assertNotIn("secret provider response", str(row["details"]))

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
        visible_targets = self.repository.show(created["run_id"], "COMPETITOR_SELECTION")["override_targets"]
        self.assertTrue(visible_targets)
        self.assertEqual({"competitor"}, {item["kind"] for item in visible_targets})
        self.assertTrue(all(item.get("name") and item.get("domain") for item in visible_targets))
        self.assertEqual([], self.repository.show(created["run_id"], "OWNER_CAPTURE")["override_targets"])
        service = LavalService(self.repository, LavalRunner(self.pipeline))
        with self.assertRaisesRegex(ValueError, "requires a reason"):
            service.override(created["run_id"], {
                "type": "competitor", "action": "reject", "target_id": visible_targets[0]["id"], "reason": "",
            }, actor="test-owner")
        added = service.override(created["run_id"], {
            "type": "competitor",
            "action": "add",
            "target_id": "https://manual-competitor.example/pricing",
            "reason": "owner observed it directly",
            "payload": {"url": "https://manual-competitor.example/pricing", "country": "DE"},
        }, actor="test-owner")
        competitor = self.store.fetchone("SELECT * FROM laval_competitors WHERE id=%s", (added["target_id"],))
        self.assertTrue(competitor["selected"])
        self.assertIn(added["target_id"], {item["id"] for item in self.repository.show(created["run_id"], "COMPETITOR_SELECTION")["override_targets"]})
        self.assertEqual("pending", self.repository.stage(created["run_id"], "COMPETITOR_EVIDENCE")["status"])
        service.override(created["run_id"], {
            "type": "competitor", "action": "reject", "target_id": added["target_id"], "reason": "not a direct competitor",
        }, actor="test-owner")
        competitor = self.store.fetchone("SELECT * FROM laval_competitors WHERE id=%s", (added["target_id"],))
        self.assertFalse(competitor["selected"])
        self.assertNotIn(added["target_id"], {item["id"] for item in self.repository.show(created["run_id"], "COMPETITOR_SELECTION")["override_targets"]})
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
            notified = client.post(f"/internal/web/laval/runs/{run_id}/notify", headers=headers, json={"actor": "firebase:owner"})
            self.assertEqual(410, notified.status_code)
            exported = client.get(f"/internal/web/laval/runs/{run_id}/export?stage=OWNER_CAPTURE&format=json", headers=headers)
            self.assertEqual(200, exported.status_code)
            self.assertIn("raw_text", exported.text)


if __name__ == "__main__":
    unittest.main()
