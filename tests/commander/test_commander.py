from __future__ import annotations

import json
import importlib.util
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path

from commander.demo import run_demo
from commander.context import ContextBroker
from commander.ids import new_uuid7
from commander.model import Entity, EntityKind, RelationType, Relationship
from commander.policy import CommanderPolicy, PolicyDenied
from commander.postgres_store import OutboxMessage, PostgresKnowledgeStore
from commander.service import Commander
from commander.research import (
    CreativeIdeationResearchService, CreativeResearchResult, HypothesisProposal,
    ResearchFinding, ResearchKnowledgeService,
)
from commander.store import JsonlKnowledgeStore, MemoryKnowledgeStore
from commander.telegram import TelegramControlPlane, TelegramUnauthorized


ROOT = Path(__file__).resolve().parents[2]


class IdTests(unittest.TestCase):
    def test_uuid7_has_expected_version_and_variant(self) -> None:
        value = uuid.UUID(new_uuid7(timestamp_ms=1_700_000_000_000))
        self.assertEqual(value.version, 7)
        self.assertEqual(value.variant, uuid.RFC_4122)


class StoreTests(unittest.TestCase):
    def test_relationship_endpoints_and_duplicates_are_enforced(self) -> None:
        store = MemoryKnowledgeStore()
        first = Entity(EntityKind.SOURCE, {"name": "one"})
        second = Entity(EntityKind.HYPOTHESIS, {"claim": "two"})
        store.add_entity(first)
        store.add_entity(second)
        store.add_relationship(Relationship(second.id, RelationType.DERIVED_FROM, first.id))
        with self.assertRaises(ValueError):
            store.add_relationship(Relationship(second.id, RelationType.DERIVED_FROM, first.id))

    def test_jsonl_store_replays_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            store = JsonlKnowledgeStore(path)
            store.add_entity(Entity(EntityKind.SOURCE, {"name": "durable"}))
            replayed = JsonlKnowledgeStore(path)
            self.assertEqual(len(replayed.entities(EntityKind.SOURCE)), 1)
            self.assertTrue((path / "projection.json").exists())


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = CommanderPolicy.load(ROOT / "config/commander/policies.json")

    def test_experiment_requires_approval(self) -> None:
        with self.assertRaises(PolicyDenied):
            self.policy.check_experiment(approved=False, budget_minor=10, running=0)

    def test_low_confidence_decision_requires_owner(self) -> None:
        store = MemoryKnowledgeStore()
        commander = Commander(store, self.policy)
        insight = commander.create_entity(
            EntityKind.INSIGHT,
            {"interpretation": "limited"},
            reasoning_summary="test insight",
        )
        hypothesis = commander.create_entity(
            EntityKind.HYPOTHESIS,
            {"claim": "claim"},
            reasoning_summary="test hypothesis",
        )
        with self.assertRaises(PolicyDenied):
            commander.decide(
                insight=insight,
                hypothesis=hypothesis,
                decision_key="test.decision",
                action="act",
                confidence=0.5,
            )


class ContextBrokerTests(unittest.TestCase):
    def test_retrieves_only_the_classified_bundle(self) -> None:
        broker = ContextBroker(
            ROOT, ROOT / "config/commander/context_routes.json"
        )
        bundle = broker.retrieve("backend")
        self.assertEqual(len(bundle.canonical_paths), 1)
        self.assertTrue(bundle.canonical_paths[0].name.endswith("review.md"))
        self.assertNotIn(ROOT / "DESIGN_RULES.md", bundle.canonical_paths)

    def test_unknown_route_fails_closed(self) -> None:
        broker = ContextBroker(
            ROOT, ROOT / "config/commander/context_routes.json"
        )
        with self.assertRaises(KeyError):
            broker.retrieve("read_everything")


class ResearchKnowledgeTests(unittest.TestCase):
    def test_creative_research_populates_sourced_hypotheses(self) -> None:
        class Provider:
            def research(self, topic: str) -> CreativeResearchResult:
                return CreativeResearchResult(
                    findings=(
                        ResearchFinding("Study", "https://example.test/study", "Specific goals improve follow-through.", "Example", credibility=0.8),
                        ResearchFinding("Report", "https://example.test/report", "Public commitments can increase action.", "Example", credibility=0.7),
                    ),
                    hypotheses=(HypothesisProposal(
                        "A public commitment hook will increase link CTR.", (0, 1),
                        "Make your goal public | Show the first proof today | START NOW",
                    ),),
                )

        store = MemoryKnowledgeStore()
        commander = Commander(store, CommanderPolicy.load(ROOT / "config/commander/policies.json"))
        sources, hypotheses = CreativeIdeationResearchService(commander, Provider()).run(
            "commitment hooks", actor="telegram:7"
        )
        self.assertEqual(len(sources), 2)
        self.assertEqual(hypotheses[0].attributes["research_type"], "creative_ideation")
        edges = [edge for edge in store.relationships() if edge.source_id == hypotheses[0].id]
        self.assertEqual({edge.target_id for edge in edges}, {item.id for item in sources})

    def test_multiple_research_findings_preserve_hypothesis_lineage(self) -> None:
        store = MemoryKnowledgeStore()
        commander = Commander(
            store, CommanderPolicy.load(ROOT / "config/commander/policies.json")
        )
        research = ResearchKnowledgeService(commander)
        first = research.record_finding(
            ResearchFinding(
                title="Accountability study",
                source_uri="https://research.example/study-1",
                finding_summary="Public commitment correlated with completion.",
                publisher="Example University",
                published_on=date(2025, 1, 2),
                credibility=0.8,
            ),
            actor="researcher:test",
        )
        second = research.record_finding(
            ResearchFinding(
                title="Challenge framing experiment",
                source_uri="https://research.example/study-2",
                finding_summary="Challenge framing increased response in the tested cohort.",
                publisher="Example Lab",
                credibility=0.7,
            ),
            actor="researcher:test",
        )
        hypothesis = research.propose_hypothesis(
            claim="Public challenge framing increases PTW activation.",
            success_metric="activation_rate",
            threshold=0.1,
            scope="New PTW visitors",
            findings=(first, second),
            actor="researcher:test",
        )
        evidence_edges = {
            edge.target_id
            for edge in store.relationships()
            if edge.source_id == hypothesis.id and edge.relation == RelationType.DERIVED_FROM
        }
        self.assertEqual(evidence_edges, {first.id, second.id})
        self.assertEqual(hypothesis.attributes["status"], "proposed")
        snapshot = commander.graph_snapshot("hypotheses")
        self.assertEqual(set(snapshot["hypotheses"][0]["source_ids"]), {first.id, second.id})

    def test_research_requires_provenance_and_valid_credibility(self) -> None:
        with self.assertRaises(ValueError):
            ResearchFinding("", "https://example.com", "finding", "publisher")
        with self.assertRaises(ValueError):
            ResearchFinding("title", "https://example.com", "finding", "publisher", credibility=2)


class VerticalLoopTests(unittest.TestCase):
    def test_complete_loop_is_persisted_with_separate_epistemic_entities(self) -> None:
        previous = Path.cwd()
        try:
            # The demo intentionally resolves versioned policy from repository root.
            import os

            os.chdir(ROOT)
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "demo"
                result = run_demo(output)
                projection = json.loads((output / "projection.json").read_text())
        finally:
            os.chdir(previous)

        kinds = [entity["kind"] for entity in projection["entities"]]
        for expected in (
            "hypothesis",
            "creative",
            "experiment",
            "metric_set",
            "observation",
            "insight",
            "decision",
            "knowledge_assertion",
            "task",
        ):
            self.assertIn(expected, kinds)
        self.assertEqual(len(result["loop"]), 9)
        self.assertGreater(result["relationship_count"], 10)
        state_values = [
            entity["attributes"]["status"]
            for entity in projection["entities"]
            if entity["kind"] == "experiment_state"
        ]
        self.assertEqual(state_values, ["running", "completed", "evaluated"])


class TelegramControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = MemoryKnowledgeStore()
        self.commander = Commander(
            self.store, CommanderPolicy.load(ROOT / "config/commander/policies.json")
        )
        self.telegram = TelegramControlPlane(
            self.commander, allowed_user_ids={7}, allowed_chat_ids={11}
        )

    def update(self, text: str, *, user_id: int = 7) -> dict[str, object]:
        return {
            "message": {
                "from": {"id": user_id},
                "chat": {"id": 11},
                "text": text,
            }
        }

    def test_status_and_emergency_stop_are_authenticated(self) -> None:
        stopped = self.telegram.handle_update(self.update("/stop"))
        self.assertIn("enabled", stopped.text)
        self.assertIn("STOPPED", self.telegram.handle_update(self.update("/status")).text)
        self.telegram.handle_update(self.update("/resume"))
        self.assertIn("active", self.telegram.handle_update(self.update("/status")).text)
        with self.assertRaises(TelegramUnauthorized):
            self.telegram.handle_update(self.update("/status", user_id=999))

    def test_research_command_returns_graph_ids(self) -> None:
        class Provider:
            def research(self, topic: str) -> CreativeResearchResult:
                return CreativeResearchResult(
                    (ResearchFinding("Source", "https://example.test", "Finding", "Publisher"),),
                    (HypothesisProposal("Test a proof hook", (0,), "Proof beats promises | Show it | TRY IT"),),
                )
        telegram = TelegramControlPlane(
            self.commander, allowed_user_ids={7}, allowed_chat_ids={11},
            research_service=CreativeIdeationResearchService(self.commander, Provider()),
        )
        reply = telegram.handle_update(self.update("/research creative hooks for skeptical founders"))
        hypothesis = self.store.entities(EntityKind.HYPOTHESIS)[0]
        self.assertIn(hypothesis.id, reply.text)
        self.assertIn("/creative from", reply.text)
        self.assertEqual(hypothesis.attributes["owner_agent"], "marketing.creative.instagram")
        self.assertTrue(all(
            item.attributes["knowledge_domain"] == "marketing.creative"
            for item in self.store.entities(EntityKind.SOURCE)
        ))
        product = telegram.handle_update(self.update("/research product retention evidence"))
        self.assertIn("product.strategy research stored", product.text)
        product_hypothesis = self.store.entities(EntityKind.HYPOTHESIS)[-1]
        self.assertEqual(product_hypothesis.attributes["owner_agent"], "product.strategy")
        self.assertEqual(product_hypothesis.attributes["research_type"], "product_discovery")
        self.assertIn("/task from", product.text)
        with self.assertRaisesRegex(ValueError, "research agent"):
            telegram.handle_update(self.update("/research coder improve tests"))

    def test_pending_experiment_can_be_approved_once(self) -> None:
        source = self.commander.create_entity(
            EntityKind.SOURCE, {}, reasoning_summary="source"
        )
        hypothesis = self.commander.create_hypothesis(
            claim="claim",
            success_metric="ctr",
            threshold=0.1,
            scope="test",
            source=source,
        )
        creative = self.commander.create_entity(
            EntityKind.CREATIVE, {}, reasoning_summary="creative"
        )
        audience = self.commander.create_entity(
            EntityKind.AUDIENCE, {}, reasoning_summary="audience"
        )
        request = self.commander.request_experiment_approval(
            hypothesis=hypothesis,
            creative=creative,
            audience=audience,
            budget_minor=100,
            requested_by="test",
        )
        reply = self.telegram.handle_update(self.update(f"/approve {request.id}"))
        self.assertIn("is running", reply.text)
        with self.assertRaises(ValueError):
            self.telegram.handle_update(self.update(f"/approve {request.id}"))

    def test_feedback_updates_reusable_components_through_ids(self) -> None:
        from commander.instagram import InstagramCreativeAdapter, InstagramCreativeSpec

        source = self.commander.create_entity(
            EntityKind.SOURCE, {}, reasoning_summary="source"
        )
        hypothesis = self.commander.create_hypothesis(
            claim="claim", success_metric="ctr", threshold=0.1, scope="test", source=source
        )
        creative = InstagramCreativeAdapter(self.commander).generate(
            hypothesis=hypothesis,
            spec=InstagramCreativeSpec("Hook", "hero", "support", "Caption", "CTA"),
        )
        reply = self.telegram.handle_update(
            self.update(f"/feedback {creative.id} 5 Strong hook, weak CTA")
        )
        self.assertIn("Updated 5 component weights", reply.text)
        feedback = self.store.entities(EntityKind.HUMAN_FEEDBACK)[0]
        updates = self.store.entities(EntityKind.WEIGHT_UPDATE)
        self.assertEqual(len(updates), 5)
        self.assertTrue(all(item.attributes["new_weight"] == 0.6 for item in updates))
        edges = self.store.relationships()
        self.assertTrue(any(
            edge.source_id == feedback.id
            and edge.relation == RelationType.EVALUATES
            and edge.target_id == creative.id
            for edge in edges
        ))
        adjusted_ids = {
            edge.target_id for edge in edges if edge.relation == RelationType.ADJUSTS
        }
        component_ids = {
            edge.target_id for edge in edges
            if edge.source_id == creative.id and edge.relation == RelationType.CONTAINS
        }
        self.assertEqual(adjusted_ids, component_ids)
        with self.assertRaises(ValueError):
            self.telegram.handle_update(self.update(f"/feedback {creative.id} 4 duplicate"))
        summary = self.telegram.handle_update(self.update("/graph"))
        self.assertIn("human_feedback=1", summary.text)
        self.assertIn("Edges:", summary.text)
        weights = self.telegram.handle_update(self.update("/graph weights"))
        self.assertIn("0.60", weights.text)
        self.assertIn(next(iter(component_ids)), weights.text)
        lineage = self.telegram.handle_update(self.update(f"/graph creative {creative.id}"))
        self.assertIn(feedback.id, lineage.text)
        self.assertIn(creative.id, lineage.text)


class _FakeCursor:
    def __init__(self, connection: "_FakeConnection") -> None:
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] = ()) -> None:
        normalized = " ".join(query.split())
        self.connection.statements.append((normalized, params))
        if self.connection.fail_on and self.connection.fail_on in normalized:
            raise RuntimeError("injected database failure")

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _FakeConnection:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class PostgresStoreTests(unittest.TestCase):
    def test_entity_and_outbox_commit_together(self) -> None:
        connection = _FakeConnection()
        store = PostgresKnowledgeStore(connection)
        store.add_entity(Entity(EntityKind.SOURCE, {"name": "source"}))
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        sql = "\n".join(statement for statement, _ in connection.statements)
        self.assertIn("INSERT INTO commander_entities", sql)
        self.assertIn("INSERT INTO commander_outbox", sql)

    def test_outbox_failure_rolls_back_entity(self) -> None:
        connection = _FakeConnection(fail_on="INSERT INTO commander_outbox")
        store = PostgresKnowledgeStore(connection)
        with self.assertRaises(RuntimeError):
            store.add_entity(Entity(EntityKind.SOURCE, {"name": "source"}))
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_workspace_task_registration_and_ack_are_transactional(self) -> None:
        connection = _FakeConnection()
        store = PostgresKnowledgeStore(connection)
        record = store.register_workspace_task(
            task_id="TASK-59",
            interpreted_scope="Repair the restart-safe acknowledgement bridge.",
            workspace_session_id="workspace-job-59",
            chat_id=11,
        )
        self.assertEqual(record.status, "pending")
        self.assertEqual(connection.commits, 1)
        sql = "\n".join(statement for statement, _ in connection.statements)
        self.assertIn("INSERT INTO commander_entities", sql)
        self.assertIn("INSERT INTO commander_outbox", sql)
        self.assertIn("INSERT INTO commander_tasks", sql)
        self.assertLess(
            sql.index("INSERT INTO commander_outbox"),
            sql.index("INSERT INTO commander_tasks"),
        )
        payload = next(
            params[2]
            for statement, params in connection.statements
            if "INSERT INTO commander_outbox" in statement
        )
        self.assertIn("TASK-59 accepted", str(payload))
        self.assertIn("Repair the restart-safe acknowledgement bridge", str(payload))

    def test_workspace_registration_rolls_back_if_ack_cannot_be_queued(self) -> None:
        connection = _FakeConnection(fail_on="INSERT INTO commander_outbox")
        store = PostgresKnowledgeStore(connection)
        with self.assertRaises(RuntimeError):
            store.register_workspace_task(
                task_id="TASK-59",
                interpreted_scope="scope",
                workspace_session_id="session",
                chat_id=11,
            )
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)


class RuntimeImageTests(unittest.TestCase):
    @unittest.skipUnless(
        importlib.util.find_spec("fastapi") and importlib.util.find_spec("PIL"),
        "FastAPI or Pillow is not installed",
    )
    def test_reply_feedback_resolves_telegram_message_to_creative_uuid(self) -> None:
        from commander.api import _expand_feedback_reply

        store = MemoryKnowledgeStore()
        creative = Entity(EntityKind.CREATIVE, {"status": "generated"})
        store.add_entity(creative)
        store.record_telegram_delivery(11, 700, creative.id)
        expanded = _expand_feedback_reply(
            {
                "update_id": 8,
                "message": {
                    "from": {"id": 7},
                    "chat": {"id": 11},
                    "text": "/feedback 4 CTA needs work",
                    "reply_to_message": {"message_id": 700},
                },
            },
            store,
        )
        self.assertEqual(
            expanded["message"]["text"],
            f"/feedback {creative.id} 4 CTA needs work",
        )

    @unittest.skipUnless(
        importlib.util.find_spec("fastapi") and importlib.util.find_spec("PIL"),
        "FastAPI or Pillow is not installed",
    )
    def test_reply_feedback_recovers_creative_from_generated_caption(self) -> None:
        from commander.api import _expand_feedback_reply

        store = MemoryKnowledgeStore()
        creative = Entity(EntityKind.CREATIVE, {"status": "generated"})
        store.add_entity(creative)
        expanded = _expand_feedback_reply(
            {
                "update_id": 9,
                "message": {
                    "from": {"id": 7},
                    "chat": {"id": 11},
                    "text": "/feedback 5 Strong creative",
                    "reply_to_message": {
                        "message_id": 701,
                        "caption": (
                            f"Creative {creative.id}\n"
                            "Ready for review; not published."
                        ),
                    },
                },
            },
            store,
        )
        self.assertEqual(
            expanded["message"]["text"],
            f"/feedback {creative.id} 5 Strong creative",
        )

    @unittest.skipUnless(
        importlib.util.find_spec("fastapi") and importlib.util.find_spec("PIL"),
        "FastAPI or Pillow is not installed",
    )
    def test_reply_feedback_recovers_creative_from_generated_text(self) -> None:
        from commander.api import _expand_feedback_reply

        store = MemoryKnowledgeStore()
        creative = Entity(EntityKind.CREATIVE, {"delivery_mode": "text_hook"})
        store.add_entity(creative)
        expanded = _expand_feedback_reply(
            {
                "update_id": 10,
                "message": {
                    "from": {"id": 7},
                    "chat": {"id": 11},
                    "text": "/feedback 5 Strong hook",
                    "reply_to_message": {
                        "message_id": 702,
                        "text": f"Creative {creative.id}\nA strong hook",
                    },
                },
            },
            store,
        )
        self.assertEqual(
            expanded["message"]["text"],
            f"/feedback {creative.id} 5 Strong hook",
        )

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow is not installed")
    def test_renderer_creates_exact_feed_post_png(self) -> None:
        from PIL import Image
        from commander.renderer import InstagramPostRenderer

        with tempfile.TemporaryDirectory() as directory:
            path, digest = InstagramPostRenderer(Path(directory)).render(
                creative_id=new_uuid7(),
                hook="They said I would quit.",
                caption="Day one starts now.",
                cta="FOLLOW THE JOURNEY",
            )
            with Image.open(path) as image:
                self.assertEqual(image.size, (1080, 1350))
                self.assertEqual(image.format, "PNG")
                self.assertGreater(len(image.getcolors(maxcolors=2_000_000) or []), 100)
            self.assertEqual(len(digest), 64)

    @unittest.skipUnless(
        importlib.util.find_spec("fastapi") and importlib.util.find_spec("PIL"),
        "FastAPI or Pillow is not installed",
    )
    def test_webhook_creates_image_and_deduplicates_update(self) -> None:
        from fastapi.testclient import TestClient
        from commander.api import create_app
        from commander.settings import Settings

        class InboxStore(MemoryKnowledgeStore):
            def __init__(self) -> None:
                super().__init__()
                self.updates: set[int] = set()
                self.connection = _FakeConnection()

            def record_inbox_once(self, update_id: int) -> bool:
                if update_id in self.updates:
                    return False
                self.updates.add(update_id)
                return True

        class TelegramClient:
            def download_photo(self, file_id: str, destination: Path) -> Path:
                raise AssertionError("no photo should be downloaded")

        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                database_url="unused",
                telegram_bot_token="unused",
                telegram_webhook_secret="s" * 32,
                allowed_user_ids=frozenset({7}),
                allowed_chat_ids=frozenset({11}),
                asset_directory=Path(directory),
                policy_path=ROOT / "config/commander/policies.json",
            )
            store = InboxStore()
            client = TestClient(create_app(settings, store, TelegramClient()))
            update = {
                "update_id": 42,
                "message": {
                    "from": {"id": 7},
                    "chat": {"id": 11},
                    "text": "/creative They doubted me | Day one | WATCH ME",
                },
            }
            headers = {"X-Telegram-Bot-Api-Secret-Token": "s" * 32}
            response = client.post("/telegram/webhook", json=update, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            delivery = [item for item in store.outbox if item["topic"] == "telegram.send_photo"]
            self.assertEqual(len(delivery), 1)
            self.assertTrue(Path(str(delivery[0]["payload"]["path"])).is_file())
            creative = store.get_entity(response.json()["result"]["creative_id"])
            artifact = store.get_entity(response.json()["result"]["artifact_id"])
            self.assertEqual(creative.attributes["format"], "feed_post_1080x1350")
            self.assertEqual(
                (artifact.attributes["width"], artifact.attributes["height"]),
                (1080, 1350),
            )
            duplicate = client.post("/telegram/webhook", json=update, headers=headers)
            self.assertEqual(duplicate.json(), {"ok": True, "duplicate": True})
            repeated = dict(update)
            repeated["update_id"] = 45
            second = client.post("/telegram/webhook", json=repeated, headers=headers)
            self.assertEqual(second.status_code, 200, second.text)
            deliveries = [item for item in store.outbox if item["topic"] == "telegram.send_photo"]
            self.assertEqual(len(deliveries), 2)
            hooks = [
                str(item.attributes.get("value"))
                for item in store.entities(EntityKind.CREATIVE_COMPONENT)
                if item.attributes.get("component_kind") == "hook"
            ]
            self.assertEqual(len(hooks), 2)
            self.assertNotEqual(hooks[0], hooks[1])

    @unittest.skipUnless(
        importlib.util.find_spec("fastapi") and importlib.util.find_spec("PIL"),
        "FastAPI or Pillow is not installed",
    )
    def test_creative_hook_returns_text_without_rendering_image(self) -> None:
        from fastapi.testclient import TestClient
        from commander.api import create_app
        from commander.settings import Settings

        class InboxStore(MemoryKnowledgeStore):
            connection = _FakeConnection()

            def record_inbox_once(self, update_id: int) -> bool:
                return True

        class TelegramClient:
            def download_photo(self, file_id: str, destination: Path) -> Path:
                raise AssertionError("text-only hooks must not download a photo")

        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                database_url="unused",
                telegram_bot_token="unused",
                telegram_webhook_secret="s" * 32,
                allowed_user_ids=frozenset({7}),
                allowed_chat_ids=frozenset({11}),
                asset_directory=Path(directory),
                policy_path=ROOT / "config/commander/policies.json",
            )
            store = InboxStore()
            store.add_entity(Entity(EntityKind.HYPOTHESIS, {
                "research_type": "creative_ideation",
                "owner_agent": "marketing.creative.instagram",
                "research_topic": "successful accountability apps skeptical founders",
                "claim": "Specific antagonist quotes increase retention",
                "creative_direction": "They called it a phase. Keep the receipts. | Proof screen | START",
            }))
            client = TestClient(create_app(settings, store, TelegramClient()))
            response = client.post(
                "/telegram/webhook",
                json={
                    "update_id": 43,
                    "_ptw_task_id": 48,
                    "message": {
                        "from": {"id": 7},
                        "chat": {"id": 11},
                        "text": "/creative@ptw_commander_bot hook for skeptical founders",
                    },
                },
                headers={"X-Telegram-Bot-Api-Secret-Token": "s" * 32},
            )

            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(
                response.json()["result"]["hook"],
                "They called it a phase. Keep the receipts.",
            )
            self.assertTrue(response.json()["result"]["creative_id"])
            messages = [
                item for item in store.outbox
                if item["topic"] == "telegram.send_message"
            ]
            photos = [item for item in store.outbox if item["topic"] == "telegram.send_photo"]
            self.assertEqual(
                messages[-1]["payload"]["text"],
                (
                    f"Creative {response.json()['result']['creative_id']}\n"
                    "TASK-48 completed.\n"
                    "They called it a phase. Keep the receipts.\n\n"
                    "Reply to this message with:\n"
                    "/feedback 1-5 optional comment"
                ),
            )
            self.assertEqual(
                messages[-1]["payload"]["creative_id"],
                response.json()["result"]["creative_id"],
            )
            self.assertEqual(photos, [])
            self.assertEqual(list(Path(directory).rglob("*.png")), [])
            second = client.post(
                "/telegram/webhook",
                json={
                    "update_id": 44,
                    "_ptw_task_id": 52,
                    "message": {
                        "from": {"id": 7}, "chat": {"id": 11},
                        "text": "/creative hook for skeptical founders",
                    },
                },
                headers={"X-Telegram-Bot-Api-Secret-Token": "s" * 32},
            )
            self.assertEqual(second.status_code, 200, second.text)
            self.assertNotEqual(
                second.json()["result"]["hook"], response.json()["result"]["hook"]
            )
            text_creatives = [
                item for item in store.entities(EntityKind.CREATIVE)
                if item.attributes.get("delivery_mode") == "text_hook"
            ]
            self.assertEqual(len(text_creatives), 2)
            self.assertNotEqual(
                text_creatives[0].attributes["hook"], text_creatives[1].attributes["hook"]
            )
            hook_components = [
                edge.target_id
                for edge in store.relationships()
                if edge.source_id == text_creatives[0].id
                and edge.relation == RelationType.CONTAINS
            ]
            self.assertEqual(len(hook_components), 1)

            feedback = client.post(
                "/telegram/webhook",
                json={
                    "update_id": 46,
                    "message": {
                        "from": {"id": 7},
                        "chat": {"id": 11},
                        "text": "/feedback 5 Strong hook",
                        "reply_to_message": {
                            "message_id": 900,
                            "text": messages[-1]["payload"]["text"],
                        },
                    },
                },
                headers={"X-Telegram-Bot-Api-Secret-Token": "s" * 32},
            )
            self.assertEqual(feedback.status_code, 200, feedback.text)
            self.assertEqual(len(store.entities(EntityKind.HUMAN_FEEDBACK)), 1)
            self.assertEqual(len(store.entities(EntityKind.WEIGHT_UPDATE)), 1)

    @unittest.skipUnless(
        importlib.util.find_spec("fastapi") and importlib.util.find_spec("PIL"),
        "FastAPI or Pillow is not installed",
    )
    def test_webhook_rejects_wrong_secret(self) -> None:
        from fastapi.testclient import TestClient
        from commander.api import create_app
        from commander.settings import Settings

        class Store(MemoryKnowledgeStore):
            connection = _FakeConnection()

        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                "unused", "unused", "x" * 32, frozenset({7}), frozenset({11}),
                Path(directory), ROOT / "config/commander/policies.json"
            )
            client = TestClient(create_app(settings, Store(), object()))
            response = client.post(
                "/telegram/webhook", json={"update_id": 1},
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            )
            self.assertEqual(response.status_code, 403)

    @unittest.skipUnless(
        importlib.util.find_spec("fastapi") and importlib.util.find_spec("PIL"),
        "FastAPI or Pillow is not installed",
    )
    def test_existing_poller_bridge_requires_shared_bot_token(self) -> None:
        from fastapi.testclient import TestClient
        from commander.api import create_app
        from commander.settings import Settings

        class Store(MemoryKnowledgeStore):
            connection = _FakeConnection()
            updates: set[int] = set()

            def record_inbox_once(self, update_id: int) -> bool:
                if update_id in self.updates:
                    return False
                self.updates.add(update_id)
                return True

        class TelegramClient:
            pass

        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                "unused", "existing-bot-token", "x" * 32,
                frozenset({7}), frozenset({11}), Path(directory),
                ROOT / "config/commander/policies.json"
            )
            store = Store()
            client = TestClient(create_app(settings, store, TelegramClient()))
            update = {
                "update_id": 99,
                "message": {
                    "from": {"id": 7}, "chat": {"id": 11},
                    "text": "/creative Existing bot | Same transport | CREATE",
                },
            }
            denied = client.post(
                "/internal/telegram/update", json=update,
                headers={"X-PTW-Bridge-Token": "wrong"},
            )
            self.assertEqual(denied.status_code, 403)
            accepted = client.post(
                "/internal/telegram/update", json=update,
                headers={"X-PTW-Bridge-Token": "existing-bot-token"},
            )
            self.assertEqual(accepted.status_code, 200, accepted.text)
            tracked = client.post(
                "/internal/telegram/update",
                json={
                    "update_id": 100,
                    "_ptw_task_id": 43,
                    "message": {"from": {"id": 7}, "chat": {"id": 11}, "text": "/status"},
                },
                headers={"X-PTW-Bridge-Token": "existing-bot-token"},
            )
            self.assertEqual(tracked.status_code, 200, tracked.text)
            messages = [item for item in store.outbox if item["topic"] == "telegram.send_message"]
            self.assertTrue(messages[-1]["payload"]["text"].startswith("TASK-43 completed.\n"))
            self.assertIn("response", tracked.json()["result"])

    def test_worker_records_delivery_failure_without_crashing(self) -> None:
        from contextlib import contextmanager
        from commander.worker import deliver_once

        class Store:
            failed: list[tuple[str, str]] = []

            @contextmanager
            def transaction(self):
                yield self

            def claim_outbox(self, **_: object):
                return (
                    OutboxMessage(
                        "message-id", "telegram.send_message", None,
                        {"chat_id": 11, "text": "hello"}, 0
                    ),
                )

            def mark_outbox_failed(self, message_id: str, summary: str) -> None:
                self.failed.append((message_id, summary))

            def mark_outbox_published(self, message_id: str) -> None:
                raise AssertionError(message_id)

        class Client:
            def send_message(self, chat_id: int, text: str) -> None:
                raise RuntimeError("network down")

        store = Store()
        self.assertEqual(deliver_once(store, Client()), 0)
        self.assertEqual(store.failed[0][0], "message-id")
        self.assertIn("RuntimeError", store.failed[0][1])

    def test_worker_records_workspace_ack_only_after_telegram_delivery(self) -> None:
        from contextlib import contextmanager
        from commander.worker import deliver_once

        class Store:
            acknowledged: tuple[str, int] | None = None
            published: str | None = None

            @contextmanager
            def transaction(self):
                yield self

            def claim_outbox(self, **_: object):
                return (
                    OutboxMessage(
                        "outbox-id", "telegram.send_message", new_uuid7(),
                        {
                            "chat_id": 11,
                            "text": "TASK-59 accepted.\nInterpreted scope: repair bridge",
                            "workspace_task_id": "TASK-59",
                        },
                        0,
                    ),
                )

            def mark_workspace_task_acknowledged(self, task_id: str, message_id: int) -> None:
                self.acknowledged = (task_id, message_id)

            def mark_outbox_published(self, message_id: str) -> None:
                self.published = message_id

            def mark_outbox_failed(self, message_id: str, summary: str) -> None:
                raise AssertionError((message_id, summary))

        class Client:
            def send_message(self, chat_id: int, text: str):
                return {"message_id": 700}

        store = Store()
        self.assertEqual(deliver_once(store, Client()), 1)
        self.assertEqual(store.acknowledged, ("TASK-59", 700))
        self.assertEqual(store.published, "outbox-id")

    def test_worker_links_delivered_text_creative_for_reply_feedback(self) -> None:
        from contextlib import contextmanager
        from commander.worker import deliver_once

        creative_id = new_uuid7()

        class Store:
            delivery: tuple[int, int, str] | None = None

            @contextmanager
            def transaction(self):
                yield self

            def claim_outbox(self, **_: object):
                return (
                    OutboxMessage(
                        "message-id",
                        "telegram.send_message",
                        creative_id,
                        {"chat_id": 11, "text": "hook", "creative_id": creative_id},
                        0,
                    ),
                )

            def record_telegram_delivery(
                self, chat_id: int, message_id: int, entity_id: str
            ) -> None:
                self.delivery = (chat_id, message_id, entity_id)

            def mark_outbox_published(self, message_id: str) -> None:
                self.published = message_id

        class Client:
            def send_message(self, chat_id: int, text: str) -> dict[str, int]:
                return {"message_id": 901}

        store = Store()
        self.assertEqual(deliver_once(store, Client()), 1)
        self.assertEqual(store.delivery, (11, 901, creative_id))


if __name__ == "__main__":
    unittest.main()
