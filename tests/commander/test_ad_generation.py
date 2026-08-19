from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None


@unittest.skipUnless(PIL_AVAILABLE, "Pillow is required")
class AdGenerationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        from commander.ad_provider import DeterministicAdProvider
        from commander.ad_repository import MemoryAdWorkflowRepository
        from commander.policy import CommanderPolicy
        from commander.service import Commander
        from commander.store import MemoryKnowledgeStore

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = MemoryKnowledgeStore()
        self.commander = Commander(
            self.store, CommanderPolicy.load(Path("config/commander/policies.json"))
        )
        self.repository = MemoryAdWorkflowRepository()
        self.provider = DeterministicAdProvider()
        self.engine = self._engine(self.provider)
        self.idea = {
            "id": 42,
            "title": "Proof Sprint",
            "one_liner": "Turn a doubted goal into a visible daily proof journey.",
            "details": {
                "problem": "Private goals fade without accountability.",
                "solution": "A structured public proof journey.",
                "customer": "Ambitious people with a concrete goal.",
            },
        }

    def _engine(self, provider):
        from commander.ad_generation import AdGenerationEngine

        return AdGenerationEngine(
            self.commander, self.repository, provider, Path(self.directory.name)
        )

    def _batch(self, key: str = "telegram-update:1"):
        return self.engine.enqueue_batch(
            idea_snapshot=self.idea,
            chat_id=123,
            requested_by="telegram:456",
            idempotency_key=key,
        )

    def test_generates_exact_ten_before_serialized_review(self) -> None:
        from commander.ad_provider import DeterministicAdProvider
        from commander.model import EntityKind

        outer = self

        class DeliveryObservingProvider(DeterministicAdProvider):
            def generate_image(self, spec):
                outer.assertFalse(any(
                    item["topic"] == "telegram.send_photo" for item in outer.store.outbox
                ))
                return super().generate_image(spec)

        self.provider = DeliveryObservingProvider()
        self.engine = self._engine(self.provider)

        batch = self._batch()
        original = self.repository.slot(batch.campaign_id, 1).context
        self.engine.revise_context(
            "A01",
            name="Changed later",
            prompt="Future-only prompt",
            actor="owner",
            note="test",
        )

        self.assertEqual(1, self.engine.process_once())
        slots = self.repository.slots(batch.campaign_id)
        self.assertEqual(10, len(self.provider.spec_calls))
        self.assertEqual(10, len(self.provider.image_calls))
        self.assertTrue(all(item.creative_id and item.artifact_id for item in slots))
        self.assertEqual(original, slots[0].context)
        photos = [item for item in self.store.outbox if item["topic"] == "telegram.send_photo"]
        self.assertEqual(1, len(photos))
        self.assertEqual(slots[0].creative_id, photos[0]["payload"]["creative_id"])
        artifacts = self.store.entities(EntityKind.ARTIFACT)
        self.assertEqual(10, len(artifacts))
        for artifact in artifacts:
            self.assertEqual("deterministic-image-v1", artifact.attributes["resolved_model"])
            self.assertEqual("high", artifact.attributes["quality"])
            self.assertEqual((1536, 1920), (
                artifact.attributes["source_width"], artifact.attributes["source_height"]
            ))
            self.assertEqual((1080, 1350), (
                artifact.attributes["width"], artifact.attributes["height"]
            ))
            self.assertEqual(64, len(str(artifact.attributes["sha256"])))
            self.assertEqual("Proof Sprint", self.store.get_entity(
                next(
                    edge.source_id for edge in self.store.relationships()
                    if edge.target_id == artifact.id and edge.relation.value == "generated"
                )
            ).attributes["spec"]["concept_name"])

    def test_feedback_precedes_same_context_conclusion_and_next_delivery(self) -> None:
        from commander.ad_provider import DeterministicAdProvider
        from commander.model import EntityKind

        outer = self

        class InspectingProvider(DeterministicAdProvider):
            def conclude(self, **values):
                feedback = outer.store.entities(EntityKind.HUMAN_FEEDBACK)
                outer.assertEqual(len(self.conclusion_calls) + 1, len(feedback))
                outer.assertEqual(
                    values["context"].code,
                    outer.repository.slot_by_creative(
                        str(outer.repository.batch(batch.campaign_id).current_position
                            and outer.repository.slot(
                                batch.campaign_id,
                                int(outer.repository.batch(batch.campaign_id).current_position),
                            ).creative_id)
                    ).context.code,
                )
                return super().conclude(**values)

        self.provider = InspectingProvider()
        self.engine = self._engine(self.provider)
        batch = self._batch()
        self.engine.process_once()
        for position in range(1, 11):
            slot = self.repository.slot(batch.campaign_id, position)
            result = self.engine.record_estimate(
                creative_id=str(slot.creative_id),
                predicted_ctr=float(11 - position),
                rating=5 if position % 2 else 4,
                comment=f"Owner feedback {position}",
                actor="telegram:456",
            )
            self.assertIsNotNone(result.feedback_id)
            if position == 1:
                with self.assertRaises(ValueError):
                    self.engine.record_estimate(
                        creative_id=str(slot.creative_id), predicted_ctr=1, rating=3,
                        comment="duplicate", actor="telegram:456"
                    )
            self.engine.process_once()
            self.assertEqual(position, len(self.provider.conclusion_calls))
            self.assertEqual(position, len(self.store.entities(EntityKind.INSIGHT)))
            photos = [item for item in self.store.outbox if item["topic"] == "telegram.send_photo"]
            self.assertEqual(min(position + 1, 10), len(photos))

        status = self.engine.status(batch.campaign_id)
        self.assertEqual("completed", status["status"])
        self.assertEqual((10, 10, 10), (
            status["images"], status["estimates"], status["conclusions"]
        ))
        self.assertEqual([f"A{i:02d}" for i in range(1, 11)], self.provider.conclusion_calls)
        ranking = self.engine.ranking(batch.campaign_id)
        self.assertEqual("A01", ranking[0]["context_code"])
        self.assertEqual("A10", ranking[-1]["context_code"])
        self.assertTrue(all(item["conclusion"]["recommended_direction"] for item in ranking))

    def test_generation_recovery_preserves_completed_slots(self) -> None:
        from commander.ad_provider import DeterministicAdProvider

        class FailingProvider(DeterministicAdProvider):
            fail = True

            def generate_image(self, spec):
                if self.fail and "Mechanism" in spec.angle:
                    self.image_calls.append(spec.angle)
                    raise RuntimeError("configured image provider unavailable")
                return super().generate_image(spec)

        self.provider = FailingProvider()
        self.engine = self._engine(self.provider)
        batch = self._batch()
        self.engine.process_once()
        self.assertEqual("failed", self.repository.batch(batch.campaign_id).status)
        self.assertTrue(all(
            self.repository.slot(batch.campaign_id, position).creative_id
            for position in range(1, 4)
        ))
        prior_ids = tuple(
            self.repository.slot(batch.campaign_id, position).creative_id
            for position in range(1, 4)
        )
        mechanism_failures = [
            item for item in self.repository.executions
            if item["phase"] == "image" and item["position"] == 4 and item["status"] == "failed"
        ]
        self.assertEqual(3, len(mechanism_failures))

        self.provider.fail = False
        self.engine.continue_batch(batch.campaign_id)
        restarted = self._engine(self.provider)
        restarted.process_once()
        self.assertEqual(prior_ids, tuple(
            self.repository.slot(batch.campaign_id, position).creative_id
            for position in range(1, 4)
        ))
        self.assertEqual("awaiting_owner", self.repository.batch(batch.campaign_id).status)

    def test_analytics_are_append_only_idempotent_and_compare_ctr(self) -> None:
        from commander.model import EntityKind

        batch = self._batch()
        self.engine.process_once()
        slots = self.repository.slots(batch.campaign_id)
        for slot in slots:
            self.engine.record_estimate(
                creative_id=str(slot.creative_id), predicted_ctr=2.0, rating=4,
                comment="solid", actor="telegram:456"
            )
            self.engine.process_once()
        payload = {
            "source_system": "telegram-analytics-export",
            "import_id": "export-100",
            "captured_at": "2026-08-16T12:00:00+03:00",
            "attribution_window": "7d-click",
            "creatives": [
                {"creative_id": slot.creative_id, "impressions": 1000, "link_clicks": 30}
                for slot in slots
            ],
        }
        first = self.engine.import_metrics(
            batch_id=batch.campaign_id, payload=payload, actor="analytics:test"
        )
        before = len(self.store.entities(EntityKind.METRIC_SET))
        second = self.engine.import_metrics(
            batch_id=batch.campaign_id, payload=payload, actor="analytics:test"
        )
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(10, before)
        self.assertEqual(before, len(self.store.entities(EntityKind.METRIC_SET)))
        metric = self.store.entities(EntityKind.METRIC_SET)[0]
        self.assertEqual(3.0, metric.attributes["values"]["link_ctr_percent"])
        self.assertEqual(1.0, metric.attributes["actual_minus_predicted_percent_points"])

    def test_openai_image_adapter_requests_only_best_high_quality_contract(self) -> None:
        import base64

        from commander.ad_provider import AdCreativeSpec, OpenAIAdProvider

        calls = []

        class Images:
            def generate(self, **values):
                calls.append(values)
                return SimpleNamespace(
                    model="gpt-image-2-2026-04-21",
                    data=[SimpleNamespace(b64_json=base64.b64encode(b"image").decode())],
                )

        provider = object.__new__(OpenAIAdProvider)
        provider.client = SimpleNamespace(images=Images())
        provider.image_model = "gpt-image-2"
        provider.spec_model = "gpt-5-mini"
        provider.conclusion_model = "gpt-5-mini"
        result = provider.generate_image(
            AdCreativeSpec(
                concept_name="Proof Sprint",
                audience="Goal setters",
                angle="Make progress visible",
                hook="Show the work",
                supporting_copy="Build a proof journey",
                cta="LEARN MORE",
                visual_prompt="Text-free editorial portrait with negative space",
            )
        )
        self.assertEqual("gpt-image-2", calls[0]["model"])
        self.assertEqual("high", calls[0]["quality"])
        self.assertEqual("1536x1920", calls[0]["size"])
        self.assertEqual("gpt-image-2-2026-04-21", result.resolved_model)

    def test_older_image_model_is_rejected_instead_of_falling_back(self) -> None:
        from commander.ad_generation import AdGenerationEngine
        from commander.ad_provider import GeneratedAdImage

        with self.assertRaisesRegex(ValueError, "gpt-image-2"):
            AdGenerationEngine._validate_generated_image(
                GeneratedAdImage(
                    content=b"old",
                    requested_model="gpt-image-1",
                    resolved_model="gpt-image-1",
                    prompt="old",
                    quality="high",
                    width=1536,
                    height=1920,
                )
            )

    def test_ad_context_edit_history_restore_and_activation_controls(self) -> None:
        original = self.engine.context("A03")
        version = self.engine.revise_context(
            "A03",
            name="Sharper contrarian reframe",
            prompt="Challenge one assumption without unsupported claims.",
            actor="telegram:456",
            note="owner edit",
        )
        self.assertEqual(2, version)
        self.assertEqual(2, len(self.engine.context_history("A03")))
        restored = self.engine.restore_context("A03", 1, actor="telegram:456")
        self.assertEqual(3, restored)
        self.assertEqual(original["name"], self.engine.context("A03")["name"])
        self.engine.set_context_active("A03", False)
        with self.assertRaisesRegex(ValueError, "A01-A10"):
            self._batch("disabled-context")
        self.engine.set_context_active("A03", True)
        self.assertEqual(10, len(self.engine.contexts()))


@unittest.skipUnless(
    PIL_AVAILABLE
    and importlib.util.find_spec("psycopg")
    and os.environ.get("POSTGRES_AD_TEST_DATABASE_URL"),
    "POSTGRES_AD_TEST_DATABASE_URL, psycopg, and Pillow are required",
)
class AdGenerationPostgresTests(unittest.TestCase):
    def setUp(self) -> None:
        from commander.ad_generation import AdGenerationEngine
        from commander.ad_provider import DeterministicAdProvider
        from commander.ad_repository import PostgresAdWorkflowRepository
        from commander.policy import CommanderPolicy
        from commander.postgres_store import connect_postgres
        from commander.service import Commander

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = connect_postgres(os.environ["POSTGRES_AD_TEST_DATABASE_URL"])
        self.addCleanup(self.store.connection.close)
        with self.store.transaction():
            with self.store.connection.cursor() as cursor:
                cursor.execute(
                    "TRUNCATE commander_ad_executions,commander_ad_metric_imports,"
                    "commander_ad_slots,commander_ad_batches,commander_entities CASCADE"
                )
                cursor.execute("UPDATE commander_ad_contexts SET active=true")
        self.commander = Commander(
            self.store, CommanderPolicy.load(Path("config/commander/policies.json"))
        )
        self.repository = PostgresAdWorkflowRepository(self.store)
        self.provider = DeterministicAdProvider()
        self.engine = AdGenerationEngine(
            self.commander,
            self.repository,
            self.provider,
            Path(self.directory.name),
        )

    def test_postgres_restart_and_serial_review_contract(self) -> None:
        batch = self.engine.enqueue_batch(
            idea_snapshot={
                "id": 9,
                "title": "Proof Sprint",
                "one_liner": "A visible journey for a doubted goal.",
                "details": {"problem": "Goals fade", "solution": "Show proof"},
            },
            chat_id=123,
            requested_by="telegram:456",
            idempotency_key="postgres-ad-contract-1",
        )
        duplicate = self.engine.enqueue_batch(
            idea_snapshot={
                "id": 9,
                "title": "Proof Sprint",
                "one_liner": "A visible journey for a doubted goal.",
                "details": {"problem": "Goals fade", "solution": "Show proof"},
            },
            chat_id=123,
            requested_by="telegram:456",
            idempotency_key="postgres-ad-contract-1",
        )
        self.assertEqual(batch.campaign_id, duplicate.campaign_id)
        self.engine.process_once()
        self.assertEqual("awaiting_owner", self.repository.batch(batch.campaign_id).status)
        slots = self.repository.slots(batch.campaign_id)
        self.assertEqual(10, len(slots))
        self.assertTrue(all(item.creative_id for item in slots))
        first = slots[0]
        self.engine.record_estimate(
            creative_id=str(first.creative_id),
            predicted_ctr=2.4,
            rating=4,
            comment="Strong mechanism",
            actor="telegram:456",
        )
        restarted = type(self.engine)(
            self.commander,
            self.repository,
            self.provider,
            Path(self.directory.name),
        )
        restarted.process_once()
        self.assertEqual("completed", self.repository.slot(batch.campaign_id, 1).status)
        self.assertEqual("delivered", self.repository.slot(batch.campaign_id, 2).status)
        self.assertEqual(1, len(self.provider.conclusion_calls))

    def test_authenticated_internal_batch_bridge_is_idempotent(self) -> None:
        from fastapi.testclient import TestClient

        from commander.api import create_app
        from commander.settings import Settings

        settings = Settings(
            database_url=os.environ["POSTGRES_AD_TEST_DATABASE_URL"],
            telegram_bot_token="bridge-token",
            telegram_webhook_secret="s" * 32,
            allowed_user_ids=frozenset({456}),
            allowed_chat_ids=frozenset({123}),
            asset_directory=Path(self.directory.name),
            policy_path=Path("config/commander/policies.json"),
            creative_runtime_enabled=True,
        )
        request = {
            "chat_id": 123,
            "requested_by": "idea-evolution",
            "idempotency_key": "telegram-update:1001",
            "idea": {
                "id": 10,
                "title": "Visible Momentum",
                "one_liner": "Make goal progress visible.",
                "details": {"problem": "Momentum fades", "solution": "Show it"},
            },
        }
        with TestClient(create_app(settings, self.store, object(), self.engine)) as client:
            self.assertEqual(403, client.post("/internal/ad-batches", json=request).status_code)
            first = client.post(
                "/internal/ad-batches",
                json=request,
                headers={"X-PTW-Bridge-Token": "bridge-token"},
            )
            duplicate = client.post(
                "/internal/ad-batches",
                json=request,
                headers={"X-PTW-Bridge-Token": "bridge-token"},
            )
        self.assertEqual(200, first.status_code, first.text)
        self.assertEqual(first.json()["batch_id"], duplicate.json()["batch_id"])


if __name__ == "__main__":
    unittest.main()
