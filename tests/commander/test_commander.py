from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from pathlib import Path

from commander.demo import run_demo
from commander.context import ContextBroker
from commander.ids import new_uuid7
from commander.model import Entity, EntityKind, RelationType, Relationship
from commander.policy import CommanderPolicy, PolicyDenied
from commander.service import Commander
from commander.store import JsonlKnowledgeStore, MemoryKnowledgeStore


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


if __name__ == "__main__":
    unittest.main()
