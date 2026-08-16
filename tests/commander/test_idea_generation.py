from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from idea_generation.engine import EvolutionEngine
from idea_generation.provider import MockLLMProvider
from idea_generation.recovery import RecoveryExhausted, recover
from idea_generation.seeds import load
from idea_generation.telegram import TelegramController
from idea_generation.validation import StructuredOutputError, evaluations, idea


class IdeaGenerationContractTests(unittest.TestCase):
    def test_authoritative_seed_is_exact(self) -> None:
        mission, contexts = load(Path("ideaGeneration"))
        self.assertIn("MISSION_450M_5Y", mission)
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


if __name__ == "__main__": unittest.main()
