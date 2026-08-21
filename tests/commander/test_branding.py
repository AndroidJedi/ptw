from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from commander.ids import new_uuid7
from commander.branding import BrandPublishingService
from commander.model import EntityKind, RelationType
from commander.policy import CommanderPolicy
from commander.service import Commander
from commander.store import MemoryKnowledgeStore
from idea_generation.brand_domain import (
    BRAND_STAGES,
    FONT_CATALOG,
    evaluate_direction,
    normalize_direction,
    public_https_url,
)
from idea_generation.brand_providers import (
    BRAND_BRIDGE_MODES,
    BRAND_OUTPUT_SCHEMAS,
    CodexBridgeBrandProvider,
    DeterministicBrandProvider,
)
from idea_generation.operation_guard import HeavyOperationGuard, OperationConflict


PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None
POSTGRES_AVAILABLE = bool(
    os.environ.get("BRANDING_TEST_DATABASE_URL") and importlib.util.find_spec("psycopg")
)


class BrandingDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = DeterministicBrandProvider()
        evidence = [new_uuid7() for _ in range(4)]
        self.synthesis = self.provider.structured(
            "DIRECTION_SYNTHESIS", {"evidence_ids": evidence}
        )

    def test_fixed_topology_and_exact_direction_contract(self) -> None:
        self.assertEqual(10, len(BRAND_STAGES))
        self.assertEqual("CASE_SNAPSHOT", BRAND_STAGES[0])
        self.assertEqual("KIT_ASSEMBLY", BRAND_STAGES[-1])
        self.assertEqual(12, len(self.synthesis["name_candidates"]))
        self.assertEqual(3, len(self.synthesis["directions"]))
        normalized = [
            normalize_direction(value, index)
            for index, value in enumerate(self.synthesis["directions"], 1)
        ]
        self.assertEqual(3, len({item["name"] for item in normalized}))
        for item in normalized:
            evaluation = evaluate_direction(item, ["Competitor"], [])
            self.assertTrue(evaluation["passed"], evaluation)
            self.assertTrue(evaluation["checks"]["font_coverage"]["ukrainian_cyrillic"])
            for theme in ("light", "dark"):
                ratios = evaluation["checks"]["contrast"]["ratios"][theme]
                self.assertGreaterEqual(ratios["text_background"], 4.5)
                self.assertGreaterEqual(ratios["text_surface"], 4.5)

    def test_public_reference_urls_fail_closed_for_private_networks(self) -> None:
        with patch(
            "idea_generation.brand_domain.socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
        ):
            with self.assertRaisesRegex(ValueError, "non-public"):
                public_https_url("https://reference.example/path")
        for value in (
            "http://example.com", "https://localhost/page", "https://user@example.com",
            "https://example.com:8443/page",
        ):
            with self.assertRaises(ValueError, msg=value):
                public_https_url(value, resolve=False)

    def test_one_guard_serializes_laval_branding_and_codex_visible_activity(self) -> None:
        guard = HeavyOperationGuard()
        guard.acquire("laval", "run-a")
        self.assertEqual(
            {"active": True, "operation": "laval", "run_id": "run-a"},
            guard.snapshot(),
        )
        with self.assertRaises(OperationConflict) as caught:
            guard.acquire("branding", "run-b")
        self.assertEqual("laval", caught.exception.active["operation"])
        guard.release("laval", "run-a")
        guard.acquire("branding", "run-b")
        self.assertEqual("branding", guard.snapshot()["operation"])

    def test_every_live_brand_output_schema_is_strict_at_nested_objects(self) -> None:
        def inspect(value: object) -> None:
            if isinstance(value, dict):
                if value.get("type") == "object":
                    self.assertFalse(value.get("additionalProperties", True))
                    self.assertEqual(set(value.get("properties") or {}), set(value.get("required") or []))
                for item in value.values():
                    inspect(item)
            elif isinstance(value, list):
                for item in value:
                    inspect(item)

        self.assertEqual(
            {"REFERENCE_PLAN", "DESIGN_PRINCIPLES", "BRAND_BRIEF", "DIRECTION_SYNTHESIS"},
            set(BRAND_OUTPUT_SCHEMAS),
        )
        inspect(BRAND_OUTPUT_SCHEMAS)

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required")
    def test_brand_kit_is_immutable_digest_addressed_and_has_required_code(self) -> None:
        from idea_generation.brand_kit import assemble_brand_kit

        manifest = normalize_direction(self.synthesis["directions"][0], 1)
        logo = self.provider.logo(manifest)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logo_path = root / "logo.png"
            logo_path.write_bytes(logo.content)
            path, digest, kit = assemble_brand_kit(manifest, logo_path, root / "kit")
            self.assertEqual(digest, __import__("hashlib").sha256(path.read_bytes()).hexdigest())
            self.assertEqual("branding_v1", kit["pipeline_version"])
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                required = {
                    "package.json", "README.md", "brand-kit.json", "src/tokens.css",
                    "src/theme.ts", "src/components.tsx", "src/index.ts",
                    "assets/logo-symbol.png", "assets/wordmark-light.png",
                    "assets/wordmark-dark.png", "assets/app-icon.png", "assets/favicon.png",
                    "fonts/catalog.json",
                }
                self.assertTrue(required.issubset(names))
                selected_fonts = set(manifest["typography"].values())
                for font_name in selected_fonts:
                    details = FONT_CATALOG[font_name]
                    font_bytes = archive.read(f"fonts/{details['font_file']}")
                    license_bytes = archive.read(f"fonts/{details['license_file']}")
                    self.assertEqual(details["font_sha256"], __import__("hashlib").sha256(font_bytes).hexdigest())
                    self.assertEqual(details["license_sha256"], __import__("hashlib").sha256(license_bytes).hexdigest())
                from PIL import ImageFont
                display = FONT_CATALOG[manifest["typography"]["display"]]
                font_path = root / str(display["font_file"])
                font_path.write_bytes(archive.read(f"fonts/{display['font_file']}"))
                font = ImageFont.truetype(str(font_path), 42)
                self.assertIsNotNone(font.getbbox("Український інтерфейс"))
                components = archive.read("src/components.tsx").decode()
                for component in (
                    "Button", "IconButton", "TextField", "Select", "Checkbox", "Switch",
                    "Card", "Badge", "Alert", "Tabs",
                ):
                    self.assertIn(f"function {component}", components)
                self.assertIn("data-brand-theme", archive.read("README.md").decode())


class BrandingBridgeProviderTests(unittest.TestCase):
    def capabilities(self) -> dict[str, object]:
        return {
            "laval_modes": [],
            "branding_modes": sorted(BRAND_BRIDGE_MODES.values()),
            "branding_image": {
                "ready": True,
                "model": "gpt-image-2",
                "provider": "codex_chatgpt_imagegen",
                "max_images_per_request": 1,
                "asset_transport": "commander_asset_volume",
            },
            "max_request_bytes": 1_000_000,
        }

    def provider(self, asset_root: Path) -> CodexBridgeBrandProvider:
        provider = CodexBridgeBrandProvider(
            "http://bridge/internal/llm/structured",
            "bridge-token",
            "codex-cli-default",
            "gpt-image-2",
            asset_root,
        )
        provider.bridge.capabilities = self.capabilities
        return provider

    def test_exact_bridge_contract_uses_existing_codex_auth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = self.provider(Path(directory))
            self.assertEqual(
                sorted(BRAND_BRIDGE_MODES.values()),
                provider.capabilities()["branding_modes"],
            )
            provider.bridge.capabilities = lambda: {
                **self.capabilities(),
                "branding_modes": ["branding_reference_plan"],
            }
            with self.assertRaisesRegex(RuntimeError, "contract mismatch"):
                provider.capabilities()

    def test_structured_brand_stage_is_fresh_schema_bound_bridge_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = self.provider(Path(directory))
            captured = {}

            def generate(mode, prompt, payload, schema):
                captured.update({"mode": mode, "prompt": prompt, "payload": payload, "schema": schema})
                provider.bridge.last_invocation = {
                    "session_id": "fresh-brand-text",
                    "input_tokens": 21,
                    "output_tokens": 8,
                }
                return {"competitors": [], "youtube_queries": [], "principle_questions": []}

            provider.bridge.generate_structured = generate
            result = provider.structured("REFERENCE_PLAN", {"evidence_ids": ["e-1"]})
            self.assertEqual([], result["competitors"])
            self.assertEqual("branding_reference_plan", captured["mode"])
            self.assertEqual(BRAND_OUTPUT_SCHEMAS["REFERENCE_PLAN"], captured["schema"])
            self.assertIn("Do not request SEO", captured["prompt"])
            self.assertEqual({"input_tokens": 21, "output_tokens": 8}, provider.consume_usage())
            self.assertEqual("codex_included_usage", provider.cost_metadata()["billing_mode"])

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required")
    def test_logo_reads_one_immutable_bridge_asset_and_normalizes_to_1024(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = self.provider(root)
            raw = __import__("io").BytesIO()
            image = Image.new("RGBA", (1254, 1254), (255, 0, 128, 0))
            image.paste((15, 15, 20, 255), (300, 300, 954, 954))
            image.save(raw, "PNG")
            content = raw.getvalue()
            digest = __import__("hashlib").sha256(content).hexdigest()
            path = root / "brand-provider" / digest[:2] / f"{digest}.png"
            path.parent.mkdir(parents=True)
            path.write_bytes(content)
            captured = {}

            def execute(mode, prompt, payload, schema):
                captured.update({"mode": mode, "prompt": prompt, "payload": payload, "schema": schema})
                return {
                    "response": '{"generated":true}',
                    "invocation": {"session_id": "brand-image-session", "input_tokens": 5, "output_tokens": 2},
                    "image": {
                        "digest": digest,
                        "path": str(path),
                        "mime_type": "image/png",
                        "width": 1254,
                        "height": 1254,
                        "requested_model": "gpt-image-2",
                        "resolved_model": "gpt-image-2",
                        "provider": "codex_chatgpt_imagegen",
                        "request_id": "brand-image-session",
                    },
                }

            provider.bridge.execute_contract = execute
            logo = provider.logo({"logo_prompt": "Original proof symbol"})
            with Image.open(__import__("io").BytesIO(logo.content)) as normalized:
                self.assertEqual((1024, 1024), normalized.size)
                self.assertEqual("PNG", normalized.format)
            self.assertEqual("branding_logo_generation", captured["mode"])
            self.assertIn("$imagegen", captured["prompt"])
            self.assertIn("exactly once", captured["prompt"])
            self.assertEqual("gpt-image-2", logo.resolved_model)
            self.assertEqual("brand-image-session", logo.request_id)
            self.assertEqual({"input_tokens": 5, "output_tokens": 2}, provider.consume_usage())


class BrandingGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryKnowledgeStore()
        self.commander = Commander(
            self.store, CommanderPolicy.load(Path("config/commander/policies.json"))
        )
        self.publisher = BrandPublishingService(self.commander, self.store)
        self.source = self.commander.create_entity(
            EntityKind.SOURCE,
            {
                "source_type": "research_finding", "title": "Owner evidence",
                "source_uri": "https://example.com/evidence", "finding_summary": "Visible proof matters",
            },
            actor="test", reasoning_summary="Test permanent source.",
        )
        self.hypothesis = self.commander.create_entity(
            EntityKind.HYPOTHESIS,
            {"claim": "Visible proof supports a return loop"},
            actor="test", reasoning_summary="Test published hypothesis.",
            evidence_ids=(self.source.id,),
        )
        self.manifests = [
            normalize_direction(item, index)
            for index, item in enumerate(
                DeterministicBrandProvider().structured(
                    "DIRECTION_SYNTHESIS", {"evidence_ids": [self.source.id]}
                )["directions"],
                1,
            )
        ]

    def publish_reviewed_run(self, run_id: str) -> list[dict[str, str]]:
        published = []
        for manifest in self.manifests:
            result = self.publisher.publish_direction({
                "run_id": run_id,
                "direction_id": new_uuid7(),
                "source_laval_run_id": new_uuid7(),
                "hypothesis_ids": [self.hypothesis.id],
                "source_ids": [self.source.id],
                "manifest": manifest,
                "evaluation": {"passed": True},
                "artifact": {
                    "sha256": __import__("hashlib").sha256(manifest["name"].encode()).hexdigest(),
                    "storage_uri": f"/var/lib/ptw/assets/{manifest['name']}.png",
                    "width": 1024, "height": 1024,
                    "generation": {"provider": "fixture", "model": "deterministic"},
                },
            })
            creative = self.store.get_entity(result["creative_id"])
            artifact = next(
                self.store.get_entity(edge.target_id)
                for edge in self.store.relationships()
                if edge.source_id == creative.id and edge.relation == RelationType.GENERATED
            )
            feedback, updates = self.commander.record_annotated_feedback(
                creative=creative,
                artifact_digest=str(artifact.attributes["sha256"]),
                rating=4,
                comment="Distinct and clear",
                annotations=(), actor="firebase:owner",
            )
            self.assertTrue(updates)
            published.append({**result, "feedback_id": feedback.id})
        return published

    def test_three_reviews_approval_and_later_kit_supersedes_without_deletion(self) -> None:
        idea_run_id = new_uuid7()
        first_run = new_uuid7()
        first = self.publish_reviewed_run(first_run)
        first_kit = self.publisher.approve({
            "run_id": first_run,
            "direction_id": next(
                item.attributes["brand_direction_external_id"]
                for item in self.store.entities(EntityKind.BRAND_DIRECTION)
                if item.id == first[0]["direction_id"]
            ),
            "source_laval_run_id": idea_run_id,
            "source_snapshot_hash": "a" * 64,
            "manifest": self.manifests[0],
            "actor": "firebase:owner",
            "artifact": {"sha256": "b" * 64, "storage_uri": "/var/lib/ptw/assets/first.zip"},
        })
        self.assertIsNone(first_kit["previous_brand_kit_id"])
        second_run = new_uuid7()
        second = self.publish_reviewed_run(second_run)
        second_kit = self.publisher.approve({
            "run_id": second_run,
            "direction_id": next(
                item.attributes["brand_direction_external_id"]
                for item in self.store.entities(EntityKind.BRAND_DIRECTION)
                if item.id == second[1]["direction_id"]
            ),
            "source_laval_run_id": idea_run_id,
            "source_snapshot_hash": "c" * 64,
            "manifest": self.manifests[1],
            "actor": "firebase:owner",
            "artifact": {"sha256": "d" * 64, "storage_uri": "/var/lib/ptw/assets/second.zip"},
        })
        self.assertEqual(first_kit["brand_kit_id"], second_kit["previous_brand_kit_id"])
        self.assertEqual(2, len(self.store.entities(EntityKind.BRAND_KIT)))
        self.assertTrue(any(
            edge.source_id == second_kit["brand_kit_id"]
            and edge.target_id == first_kit["brand_kit_id"]
            and edge.relation == RelationType.SUPERSEDES
            for edge in self.store.relationships()
        ))

    def test_completed_case_without_survivor_derives_direction_from_sources_only(self) -> None:
        manifest = self.manifests[0]
        with self.assertRaisesRegex(ValueError, "surviving Idea thesis"):
            self.publisher.publish_direction({
                "run_id": new_uuid7(), "direction_id": new_uuid7(),
                "source_laval_run_id": new_uuid7(), "hypothesis_ids": [],
                "source_has_surviving_thesis": True,
                "source_ids": [self.source.id], "manifest": manifest,
                "evaluation": {"passed": True},
                "artifact": {
                    "sha256": __import__("hashlib").sha256(b"invalid-source-only").hexdigest(),
                    "storage_uri": "/var/lib/ptw/assets/invalid-source-only.png",
                },
            })
        result = self.publisher.publish_direction({
            "run_id": new_uuid7(),
            "direction_id": new_uuid7(),
            "source_laval_run_id": new_uuid7(),
            "hypothesis_ids": [],
            "source_has_surviving_thesis": False,
            "source_ids": [self.source.id],
            "manifest": manifest,
            "evaluation": {"passed": True},
            "artifact": {
                "sha256": __import__("hashlib").sha256(b"source-only").hexdigest(),
                "storage_uri": "/var/lib/ptw/assets/source-only.png",
                "width": 1024,
                "height": 1024,
                "generation": {"provider": "fixture", "model": "deterministic"},
            },
        })
        direction = self.store.get_entity(result["direction_id"])
        self.assertTrue(direction.attributes["source_had_no_surviving_thesis"])
        self.assertTrue(any(
            edge.source_id == direction.id
            and edge.target_id == self.source.id
            and edge.relation == RelationType.DERIVED_FROM
            for edge in self.store.relationships()
        ))


@unittest.skipUnless(POSTGRES_AVAILABLE and PIL_AVAILABLE, "BRANDING_TEST_DATABASE_URL, psycopg, and Pillow are required")
class BrandingPostgresPipelineTests(unittest.TestCase):
    """The built-image suite supplies PostgreSQL and executes the full fixture worker."""

    @classmethod
    def setUpClass(cls) -> None:
        from idea_generation.store import PostgresStore

        cls.store = PostgresStore(os.environ["BRANDING_TEST_DATABASE_URL"])
        if cls.store.fetchone("SELECT to_regclass('commander_entities') present")["present"] is None:
            for path in sorted(Path("db/migrations").glob("*.sql")):
                with cls.store.transaction() as connection:
                    connection.execute(path.read_text())
        cls.store.migrate(Path("db/idea_generation"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.store.close()

    def test_migration_exposes_append_only_branding_projections(self) -> None:
        tables = self.store.fetchall(
            """SELECT tablename FROM pg_tables WHERE schemaname='public'
               AND tablename LIKE 'brand_%%' ORDER BY tablename"""
        )
        names = {item["tablename"] for item in tables}
        self.assertTrue({
            "brand_runs", "brand_stage_runs", "brand_sources", "brand_directions",
            "brand_kits", "brand_provider_tasks", "brand_cost_events", "brand_run_actions",
        }.issubset(names))
        self.assertEqual("branding_v1", self.store.fetchone(
            "SELECT column_default FROM information_schema.columns WHERE table_name='brand_runs' AND column_name='pipeline_version'"
        )["column_default"].strip("'::text"))
        self.assertEqual("YES", self.store.fetchone(
            """SELECT is_nullable FROM information_schema.columns
                WHERE table_name='commander_ad_batches' AND column_name='brand_kit_id'"""
        )["is_nullable"])

    def test_deterministic_pipeline_reviews_and_approved_zip_end_to_end(self) -> None:
        from commander.ad_repository import PostgresAdWorkflowRepository
        from commander.postgres_store import connect_postgres
        from idea_generation.brand_pipeline import BrandPipeline
        from idea_generation.brand_providers import FixtureBrandPageProvider
        from idea_generation.brand_repository import BrandRepository
        from idea_generation.laval_providers import FixtureYouTubeObservationProvider

        commander_store = connect_postgres(os.environ["BRANDING_TEST_DATABASE_URL"])
        self.addCleanup(commander_store.connection.close)
        commander = Commander(
            commander_store, CommanderPolicy.load(Path("config/commander/policies.json"))
        )
        publisher = BrandPublishingService(commander, commander_store)

        class LocalBridge:
            def sources(self, findings):
                return publisher.record_sources(findings)

            def direction(self, payload):
                return publisher.publish_direction(payload)

            def approve(self, payload):
                return publisher.approve(payload)

        with self.store.transaction() as connection:
            for table in (
                "brand_run_actions", "brand_cost_events", "brand_provider_tasks", "brand_kits",
                "brand_directions", "brand_sources", "brand_stage_runs", "brand_runs",
                "laval_llm_invocations", "laval_product_theses", "laval_product_mechanisms",
                "laval_evidence", "laval_competitors", "laval_owner_ideas", "laval_runs",
            ):
                connection.execute(f"DELETE FROM {table}")
        self.store.seed_laval_mission()
        permanent_source = commander.create_entity(
            EntityKind.SOURCE,
            {
                "source_type": "research_finding", "title": "Permanent case evidence",
                "source_uri": "https://evidence.example/progress",
                "finding_summary": "Users return when credible progress is visible.",
                "external_id": new_uuid7(),
            }, actor="test", reasoning_summary="Created permanent evidence for Branding test.",
        )
        hypothesis = commander.create_entity(
            EntityKind.HYPOTHESIS,
            {"claim": "Visible proof supports a truthful retention loop"},
            actor="test", reasoning_summary="Created completed Idea hypothesis for Branding test.",
            evidence_ids=(permanent_source.id,),
        )
        run_id, owner_id, mechanism_id, evidence_id, thesis_id, competitor_id = (
            new_uuid7() for _ in range(6)
        )
        mission_id = self.store.fetchone(
            "SELECT id FROM missions WHERE is_active=TRUE LIMIT 1"
        )["id"]
        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO laval_runs(
                       id,mission_id,status,current_stage,config,approval_mode,created_by,
                       completed_at,evidence_mode,provider_snapshot,pipeline_version
                   ) VALUES(%s,%s,'completed','PRODUCT_THESIS',%s::jsonb,'automatic','test',
                            NOW(),'live_market_signals',%s::jsonb,'mechanism_thesis_v1')""",
                (run_id, mission_id, json.dumps({"countries": ["US"]}), json.dumps({"search": "live", "youtube": "fixture"})),
            )
            connection.execute(
                "INSERT INTO laval_owner_ideas(id,run_id,raw_text) VALUES(%s,%s,%s)",
                (owner_id, run_id, "An app that turns doubted goals into visible daily proof."),
            )
            connection.execute("UPDATE laval_runs SET owner_idea_id=%s WHERE id=%s", (owner_id, run_id))
            connection.execute(
                """INSERT INTO laval_competitors(
                       id,run_id,name,domain,url,result_type,score,selected,components
                   ) VALUES(%s,%s,'ProofFlow','proofflow.example','https://proofflow.example',
                            'direct_product',.8,TRUE,%s::jsonb)""",
                (competitor_id, run_id, json.dumps({"pricing": "subscription"})),
            )
            connection.execute(
                """INSERT INTO laval_evidence(
                       id,run_id,source_type,source_url,source_title,publisher,excerpt,claim,
                       confidence,metadata,commander_source_id
                   ) VALUES(%s,%s,'website','https://evidence.example/progress','Progress study',
                            'Evidence Lab','People return to log credible progress.',
                            'Visible proof supports return behavior',.82,%s::jsonb,%s)""",
                (evidence_id, run_id, json.dumps({"permanent": True}), permanent_source.id),
            )
            connection.execute(
                """INSERT INTO laval_product_mechanisms(
                       id,run_id,name,description,mechanism_type,evidence_ids,support_dimensions
                   ) VALUES(%s,%s,%s::jsonb,%s::jsonb,'retention',%s::uuid[],%s::jsonb)""",
                (
                    mechanism_id, run_id,
                    json.dumps({"en": "Visible proof", "uk": "Видимий доказ"}),
                    json.dumps({"en": "A credible progress timeline", "uk": "Достовірна шкала прогресу"}),
                    [evidence_id], json.dumps({"behavior": .8, "trust": .9}),
                ),
            )
            connection.execute(
                """INSERT INTO laval_product_theses(
                       id,run_id,title,target_user,problem,loop_steps,value_moment,
                       zero_audience_behavior,substitutes,dangerous_assumptions,success_criterion,
                       mechanism_ids,evidence_ids,verdict,recommended,recommendation_reason,
                       commander_hypothesis_id
                   ) VALUES(%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                            %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::uuid[],%s::uuid[],
                            'survives',TRUE,'Strongest evidence lineage',%s)""",
                (
                    thesis_id, run_id,
                    json.dumps({"en": "Proof journey", "uk": "Шлях доказів"}),
                    json.dumps({"en": "People pursuing a doubted goal", "uk": "Люди з метою, у яку не вірять"}),
                    json.dumps({"en": "Momentum fades in private", "uk": "Приватний прогрес згасає"}),
                    json.dumps([{"en": "Set a milestone", "uk": "Визначити етап"}, {"en": "Log proof", "uk": "Додати доказ"}]),
                    json.dumps({"en": "See a credible proof timeline", "uk": "Побачити достовірну шкалу"}),
                    json.dumps({"en": "Useful privately", "uk": "Корисно приватно"}),
                    json.dumps([{"en": "Spreadsheet", "uk": "Таблиця"}]),
                    json.dumps([{"id": "trust", "statement": {"en": "Proof stays credible", "uk": "Доказ лишається достовірним"}, "severity": "high"}]),
                    json.dumps({"metric": "weekly_return", "operator": ">=", "threshold": .3, "sample_target": 20}),
                    [mechanism_id], [evidence_id], hypothesis.id,
                ),
            )

        class RetryProvider(DeterministicBrandProvider):
            def __init__(self):
                self.calls: dict[str, int] = {}

            def structured(self, stage, payload):
                self.calls[stage] = self.calls.get(stage, 0) + 1
                if stage == "DIRECTION_SYNTHESIS" and self.calls[stage] == 1:
                    return {"name_candidates": ["invalid"], "directions": []}
                return super().structured(stage, payload)

        provider = RetryProvider()
        repository = BrandRepository(self.store)
        with tempfile.TemporaryDirectory() as asset_directory:
            created = repository.create(
                run_id,
                constraints_text="Energetic but never manipulative",
                reference_urls=[],
                manual_transcripts=[{
                    "title": "Owner research note",
                    "video_url": "https://www.youtube.com/watch?v=manual123",
                    "transcript": "Users want proof without fake urgency.",
                }],
                actor="firebase:owner",
                provider_snapshot={"provider": provider.name, "paid_seo_enabled": False},
            )
            brand_run_id = str(created["run_id"])
            snapshot = repository.run(brand_run_id)["source_snapshot"]
            self.assertEqual("An app that turns doubted goals into visible daily proof.", snapshot["owner_idea"])
            self.assertEqual(1, len(snapshot["theses"]))
            self.assertEqual(1, len(snapshot["mechanisms"]))
            self.assertEqual(1, len(snapshot["competitors"]))
            self.assertEqual(1, len(snapshot["evidence"]))
            repository.ready(brand_run_id)
            unknown_task_id = new_uuid7()
            self.store.execute(
                """INSERT INTO brand_provider_tasks(
                       id,run_id,stage,item_key,provider,status,request_hash,request_count
                   ) VALUES(%s,%s,'REFERENCE_PLAN','structured:1:1',
                            'deterministic_brand_fixture','unknown',%s,1) RETURNING 1""",
                (unknown_task_id, brand_run_id, "f" * 64),
            )
            repository.invalidate_from(
                brand_run_id, "REFERENCE_PLAN", actor="firebase:owner"
            )
            self.assertEqual(
                "failed",
                self.store.fetchone(
                    "SELECT status FROM brand_provider_tasks WHERE id=%s",
                    (unknown_task_id,),
                )["status"],
            )
            repository.ready(brand_run_id)
            pipeline = BrandPipeline(
                repository, provider, FixtureBrandPageProvider(),
                FixtureYouTubeObservationProvider(), LocalBridge(), Path(asset_directory),
            )
            pipeline.run(brand_run_id)
            status = repository.status(brand_run_id)
            self.assertEqual("awaiting_review", status["run"]["status"])
            self.assertEqual(3, len(status["directions"]))
            self.assertEqual(3, sum(bool(item["artifact_digest"]) for item in status["directions"]))
            self.assertEqual(2, provider.calls["DIRECTION_SYNTHESIS"])
            self.assertTrue(any(item["source_type"] == "manual_transcript" for item in repository.sources(brand_run_id)))
            self.assertEqual(0, status["stages"][2]["metrics"]["paid_seo_calls"])
            self.assertEqual(0, self.store.fetchone(
                """SELECT count(*) n FROM brand_provider_tasks
                    WHERE run_id=%s AND lower(provider) LIKE '%%dataforseo%%'""",
                (brand_run_id,),
            )["n"])
            self.assertEqual(3, self.store.fetchone(
                "SELECT count(*) n FROM brand_provider_tasks WHERE run_id=%s AND stage='LOGO_GENERATION' AND status='completed'",
                (brand_run_id,),
            )["n"])

            first_direction = repository.directions(brand_run_id)[0]
            with self.assertRaisesRegex(ValueError, "all three current logo reviews"):
                pipeline.approve(
                    brand_run_id, str(first_direction["id"]), actor="firebase:owner"
                )

            review_repository = PostgresAdWorkflowRepository(commander_store)
            for item in repository.directions(brand_run_id):
                creative = commander_store.get_entity(str(item["creative_id"]))
                with commander_store.transaction():
                    feedback, updates = commander.record_annotated_feedback(
                        creative=creative,
                        artifact_digest=str(item["artifact_digest"]),
                        rating=4, comment="Current owner review", annotations=(),
                        actor="firebase:owner",
                    )
                    review_repository.save_review_projection(
                        feedback_id=feedback.id, creative_id=creative.id,
                        artifact_digest=str(item["artifact_digest"]), rating=4,
                        comment="Current owner review", predicted_ctr=None, annotations=(),
                    )
                self.assertTrue(updates)
            selected = repository.directions(brand_run_id)[0]
            kit = pipeline.approve(brand_run_id, str(selected["id"]), actor="firebase:owner")
            self.assertEqual("approved", kit["status"])
            self.assertEqual(
                kit["commander_brand_kit_id"],
                pipeline.approve(
                    brand_run_id, str(selected["id"]), actor="firebase:owner"
                )["commander_brand_kit_id"],
            )
            self.assertTrue(Path(str(kit["zip_path"])).is_file())
            with zipfile.ZipFile(str(kit["zip_path"])) as archive:
                self.assertIn("src/components.tsx", archive.namelist())
                self.assertIn("brand-kit.json", archive.namelist())
            cached_logo_tasks = self.store.fetchone(
                "SELECT sum(request_count)::int n FROM brand_provider_tasks WHERE run_id=%s AND stage='LOGO_GENERATION'",
                (brand_run_id,),
            )["n"]
            cached_reference_tasks = self.store.fetchone(
                """SELECT sum(request_count)::int n FROM brand_provider_tasks
                    WHERE run_id=%s AND stage='REFERENCE_COLLECTION'""",
                (brand_run_id,),
            )["n"]
            pipeline.run(brand_run_id)
            self.assertEqual(cached_logo_tasks, self.store.fetchone(
                "SELECT sum(request_count)::int n FROM brand_provider_tasks WHERE run_id=%s AND stage='LOGO_GENERATION'",
                (brand_run_id,),
            )["n"])
            self.assertEqual(cached_reference_tasks, self.store.fetchone(
                """SELECT sum(request_count)::int n FROM brand_provider_tasks
                    WHERE run_id=%s AND stage='REFERENCE_COLLECTION'""",
                (brand_run_id,),
            )["n"])
            self.store.execute(
                """UPDATE laval_product_theses
                      SET recommendation_reason='Material owner correction'
                    WHERE id=%s RETURNING 1""",
                (thesis_id,),
            )
            self.assertTrue(repository.status(brand_run_id)["run"]["source_stale"])
            self.assertEqual(
                "stale", repository.kit(str(kit["commander_brand_kit_id"]))["status"]
            )
            self.assertEqual(
                "stale",
                commander_store.get_entity(str(kit["commander_brand_kit_id"])).attributes["status"],
            )
            self.store.execute(
                "UPDATE laval_product_theses SET verdict='rejected',recommended=FALSE WHERE id=%s RETURNING 1",
                (thesis_id,),
            )
            candidates = repository.candidates()
            rejected_case = next(
                item for item in candidates["items"] if item["idea_run_id"] == run_id
            )
            self.assertEqual(0, rejected_case["surviving_thesis_count"])
            self.assertEqual("rejected", rejected_case["theses"][0]["verdict"])


if __name__ == "__main__":
    unittest.main()
