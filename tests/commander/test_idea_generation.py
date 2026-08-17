from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from idea_generation.engine import EvolutionEngine
from idea_generation.provider import MockLLMProvider
from idea_generation.recovery import RecoveryExhausted, recover
from idea_generation.seeds import load
from idea_generation.store import PostgresStore
from idea_generation.telegram import TelegramController
from idea_generation.validation import StructuredOutputError, evaluations, idea


class IdeaGenerationContractTests(unittest.TestCase):
    def test_authoritative_seed_is_exact(self) -> None:
        mission, contexts = load(Path("ideaGeneration"))
        self.assertIn("MISSION_20M_3Y", mission)
        self.assertEqual([f"C{i:02d}" for i in range(1, 11)], [item["code"] for item in contexts])

    def test_slot_mix(self) -> None:
        self.assertEqual(["initial"] * 10, EvolutionEngine._modes(10, 1))
        modes = EvolutionEngine._modes(10, 2)
        self.assertEqual(7, modes.count("exploit"))
        self.assertEqual(3, modes.count("explore"))
        reduced = EvolutionEngine._modes(8, 2)
        self.assertEqual(6, reduced.count("exploit"))
        self.assertEqual(2, reduced.count("explore"))

    def test_bounded_recovery_first_attempt(self) -> None:
        calls=[]; notices=[]
        def operation(attempt:int)->str:
            calls.append(attempt)
            if len(calls)==1: raise TimeoutError()
            return "ok"
        self.assertEqual("ok", recover("G1 / GENERATE / C01",operation,notices.append))
        self.assertEqual([1,2],calls)
        self.assertIn("Recovery succeeded",notices[-1])

    def test_bounded_recovery_second_attempt(self) -> None:
        calls=[]
        def operation(attempt:int)->str:
            calls.append(attempt)
            if len(calls)<3: raise ValueError()
            return "ok"
        self.assertEqual("ok",recover("step",operation,lambda _:None))
        self.assertEqual(3,len(calls))

    def test_bounded_recovery_stops_after_two_recoveries(self) -> None:
        calls=[]
        with self.assertRaises(RecoveryExhausted):
            recover("step",lambda attempt:(calls.append(attempt),(_ for _ in ()).throw(ValueError()))[1],lambda _:None)
        self.assertEqual([1,2,3],calls)

    def test_invalid_parent_is_rejected(self) -> None:
        payload=MockLLMProvider().generate_structured("generate","",{"context":{"code":"C01"}}, {})
        payload["parent_ids"]=[999]
        with self.assertRaises(StructuredOutputError): idea(payload,{1},True)

    def test_evaluator_must_return_exact_batch(self) -> None:
        provider=MockLLMProvider()
        payload={"context":{"code":"C01"},"ideas":[{"id":n} for n in range(1,11)]}
        result=provider.generate_structured("evaluate","",payload,{})
        self.assertEqual(10,len(evaluations(result,list(range(1,11)))))
        result["evaluations"][0]["idea_id"]=2
        with self.assertRaises(StructuredOutputError): evaluations(result,list(range(1,11)))

    def test_freeform_intents_are_bounded(self) -> None:
        self.assertEqual("/ranking",TelegramController._freeform("покажи текущий рейтинг"))
        self.assertEqual("/idea_add hello",TelegramController._freeform("добавь мою идею: hello"))
        self.assertEqual("ambiguous",TelegramController._freeform("ambiguous"))

    def test_owner_normalization_preserves_the_raw_concept(self) -> None:
        raw = "PROVE THEM WRONG\nA persistent public goal and proof journey."
        payload = MockLLMProvider().generate_structured(
            "normalize_human", "", {"context": {"code": "owner"}, "raw_text": raw}, {}
        )
        self.assertEqual("PROVE THEM WRONG", payload["title"]["en"])
        self.assertIn(raw, payload["details"]["problem"]["en"])
        self.assertEqual([], payload["parent_ids"])

    def test_ads_from_validates_and_snapshots_the_selected_idea(self) -> None:
        submitted = []

        class Store:
            def mission(self):
                return {"id": 1, "task_text": "task"}

            def execute(self, sql, params=()):
                return 1

            def fetchone(self, sql, params=()):
                if "FROM ideas" in sql:
                    return {
                        "id": 77,
                        "title": "Proof Sprint",
                        "one_liner": "A visible proof journey.",
                        "details": {"problem": "Goals fade"},
                        "mode": "explore",
                        "parent_ids": [12],
                        "created_at": "2026-08-16T12:00:00+03:00",
                        "generation_number": 5,
                        "aggregate_score": 82.5,
                    }
                return None

        def submit(chat_id, idea, key):
            submitted.append((chat_id, idea, key))
            return {"batch_id": "batch-uuid", "status": "queued"}

        controller = TelegramController(
            Store(), object(), frozenset({123}), ad_batch_submitter=submit
        )
        result = controller.handle(
            123, "/ads from 77", idempotency_key="telegram-update:900"
        )
        self.assertIn("batch-uuid", result)
        self.assertEqual(123, submitted[0][0])
        self.assertEqual("Proof Sprint", submitted[0][1]["title"])
        self.assertEqual("telegram-update:900", submitted[0][2])


@unittest.skipUnless(
    os.environ.get("IDEA_GENERATION_TEST_DATABASE_URL") and importlib.util.find_spec("psycopg"),
    "IDEA_GENERATION_TEST_DATABASE_URL and psycopg are required",
)
class IdeaGenerationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.store = PostgresStore(os.environ["IDEA_GENERATION_TEST_DATABASE_URL"])
        cls.store.migrate(Path("db/idea_generation"))
        cls.mission_text, cls.contexts = load(Path("ideaGeneration"))
        cls.store.seed(cls.mission_text, cls.contexts)

    def setUp(self) -> None:
        with self.store.transaction() as connection:
            connection.execute(
                "TRUNCATE telegram_inbox,telegram_events,reports,executions,idea_evaluations,ideas,"
                "idea_submission_drafts,idea_submissions,generations,guidance RESTART IDENTITY CASCADE"
            )
            connection.execute(
                "UPDATE missions SET status='active',auto_enabled=FALSE,run_series_remaining=0,"
                "stop_after_current_cycle=FALSE,updated_at=NOW()"
            )

    def test_owner_idea_replaces_latest_lowest_in_new_immutable_generation(self) -> None:
        engine = EvolutionEngine(self.store, MockLLMProvider())
        self.assertEqual([1], engine.run_series(1))
        bottom = self.store.fetchone(
            """SELECT i.id FROM ideas i JOIN generations g ON g.id=i.generation_id
               JOIN idea_scores s ON s.idea_id=i.id WHERE g.number=1
               ORDER BY s.aggregate_score,i.id LIMIT 1"""
        )["id"]
        mission = self.store.mission()
        submission = self.store.execute(
            "INSERT INTO idea_submissions(mission_id,raw_text) VALUES (%s,%s) RETURNING id",
            (mission["id"], "PROVE THEM WRONG\nPublic doubt becomes a persistent proof journey."),
        )

        self.assertEqual([2], engine.run_series(1))
        modes = self.store.fetchall(
            "SELECT mode,count(*) n FROM ideas WHERE generation_id=(SELECT id FROM generations WHERE number=2) GROUP BY mode"
        )
        self.assertEqual({"human": 1, "retained": 9}, {row["mode"]: row["n"] for row in modes})
        state = self.store.fetchone(
            "SELECT status,target_generation_number,replaces_idea_id FROM idea_submissions WHERE id=%s",
            (submission,),
        )
        self.assertEqual("inserted", state["status"])
        self.assertEqual(2, state["target_generation_number"])
        self.assertEqual(bottom, state["replaces_idea_id"])
        parents = self.store.fetchall(
            "SELECT parent_ids FROM ideas WHERE generation_id=(SELECT id FROM generations WHERE number=2) AND mode='retained'"
        )
        self.assertNotIn(bottom, {row["parent_ids"][0] for row in parents})
        self.assertEqual(10, self.store.fetchone(
            "SELECT count(*) n FROM ideas WHERE generation_id=(SELECT id FROM generations WHERE number=1)"
        )["n"])
        self.assertEqual(100, self.store.fetchone(
            "SELECT count(*) n FROM idea_evaluations e JOIN ideas i ON i.id=e.idea_id "
            "WHERE i.generation_id=(SELECT id FROM generations WHERE number=2)"
        )["n"])

    def test_long_idea_draft_joins_every_part_before_queueing(self) -> None:
        controller = TelegramController(
            self.store, EvolutionEngine(self.store, MockLLMProvider()), frozenset({123})
        )
        first = "A" * TelegramController.LONG_IDEA_THRESHOLD
        second = "B" * 3445
        self.assertIn("draft started", controller.handle(123, "/idea_add " + first))
        self.assertIn("part 2 saved", controller.handle(123, second))
        self.assertIn("queued as submission", controller.handle(123, "/idea_done"))
        row = self.store.fetchone("SELECT raw_text FROM idea_submissions")
        self.assertEqual(first + "\n" + second, row["raw_text"])
        self.assertIsNone(self.store.fetchone("SELECT * FROM idea_submission_drafts"))

    def test_run_during_active_series_extends_remaining_count(self) -> None:
        self.store.update_mission(run_series_remaining=1)
        remaining, active = EvolutionEngine(self.store, MockLLMProvider()).queue_generations(2)
        self.assertTrue(active)
        self.assertEqual(3, remaining)
        self.assertEqual(3, self.store.mission()["run_series_remaining"])

    def test_restart_seed_does_not_overwrite_owner_context_revision(self) -> None:
        row = self.store.fetchone("SELECT id,version FROM contexts WHERE code='C04'")
        with self.store.transaction() as connection:
            version = row["version"] + 1
            connection.execute(
                "UPDATE contexts SET prompt_text='owner text',version=%s WHERE id=%s", (version, row["id"])
            )
            connection.execute(
                "INSERT INTO context_revisions(context_id,version,name,prompt_text,changed_by) "
                "SELECT id,%s,name,'owner text','owner' FROM contexts WHERE id=%s",
                (version, row["id"]),
            )
        self.store.seed(self.mission_text, self.contexts)
        self.assertEqual("owner text", self.store.fetchone(
            "SELECT prompt_text FROM contexts WHERE code='C04'"
        )["prompt_text"])

    @unittest.skipUnless(importlib.util.find_spec("fastapi"), "FastAPI is required")
    def test_internal_api_authenticates_and_deduplicates_forwarded_updates(self) -> None:
        from fastapi.testclient import TestClient

        from idea_generation.api import create_app
        from idea_generation.config import Settings

        sent: list[tuple[int, str]] = []
        settings = Settings(
            database_url=os.environ["IDEA_GENERATION_TEST_DATABASE_URL"],
            telegram_token="test-token",
            allowed_chat_ids=frozenset({123}),
            allowed_user_ids=frozenset({456}),
        )
        update = {
            "update_id": 9001,
            "message": {"from": {"id": 456}, "chat": {"id": 123}, "text": "/idea_queue"},
        }
        with TestClient(create_app(settings, lambda chat, text: sent.append((chat, text)))) as client:
            self.assertEqual(403, client.post("/internal/telegram/update", json=update).status_code)
            first = client.post(
                "/internal/telegram/update", json=update, headers={"X-PTW-Bridge-Token": "test-token"}
            )
            duplicate = client.post(
                "/internal/telegram/update", json=update, headers={"X-PTW-Bridge-Token": "test-token"}
            )
        self.assertEqual({"ok": True}, first.json())
        self.assertEqual({"ok": True, "duplicate": True}, duplicate.json())
        self.assertEqual(2, len(sent))


if __name__ == "__main__": unittest.main()
