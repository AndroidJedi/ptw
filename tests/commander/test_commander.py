from __future__ import annotations

import json
import importlib.util
import tempfile
import unittest
import uuid
from pathlib import Path

from commander.demo import run_demo
from commander.context import ContextBroker
from commander.ids import new_uuid7
from commander.model import Entity, EntityKind, RelationType, Relationship
from commander.policy import CommanderPolicy, PolicyDenied
from commander.postgres_store import OutboxMessage, PostgresKnowledgeStore
from commander.service import Commander
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


class RuntimeImageTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow is not installed")
    def test_renderer_creates_exact_story_png(self) -> None:
        from PIL import Image
        from commander.renderer import InstagramStoryRenderer

        with tempfile.TemporaryDirectory() as directory:
            path, digest = InstagramStoryRenderer(Path(directory)).render(
                creative_id=new_uuid7(),
                hook="They said I would quit.",
                caption="Day one starts now.",
                cta="FOLLOW THE JOURNEY",
            )
            with Image.open(path) as image:
                self.assertEqual(image.size, (1080, 1920))
                self.assertEqual(image.format, "PNG")
            self.assertEqual(len(digest), 64)

    @unittest.skipUnless(importlib.util.find_spec("fastapi"), "FastAPI is not installed")
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
            duplicate = client.post("/telegram/webhook", json=update, headers=headers)
            self.assertEqual(duplicate.json(), {"ok": True, "duplicate": True})

    @unittest.skipUnless(importlib.util.find_spec("fastapi"), "FastAPI is not installed")
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

    @unittest.skipUnless(importlib.util.find_spec("fastapi"), "FastAPI is not installed")
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
            client = TestClient(create_app(settings, Store(), TelegramClient()))
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


if __name__ == "__main__":
    unittest.main()
