from __future__ import annotations

import copy
import unittest

from marketing_positioning.domain import PositioningDocumentV1, markdown_export


OWNER = "018f07ea-7f20-7000-8000-000000000001"
RESEARCH = "018f07ea-7f20-7000-8000-000000000002"


def statement(text: str, source: str = RESEARCH) -> dict[str, object]:
    return {"text": text, "source_ids": [source] if source else [], "assumption": not bool(source)}


def document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "output_language": "en",
        "positioning_foundation": {
            "category": statement("A focused planning tool", OWNER),
            "competitive_alternatives": [statement("Spreadsheets and manual reminders")],
            "definitive_audience": statement("Small teams coordinating follow-up"),
            "jobs": [statement("Keep one next action visible")],
            "pains": [statement("Manual follow-up becomes scattered")],
            "gains": [statement("A clear shared next step")],
            "uvp": statement("Natal keeps a useful next step visible", OWNER),
        },
        "messaging_matrix": [{
            "feature": statement("Shared next-step view", OWNER),
            "functional_benefit": statement("The team sees the current action", OWNER),
            "emotional_reward": statement("The team can feel less uncertain", ""),
        }],
        "landing_copy": {
            "hero": {
                "eyebrow": statement("For small teams"), "headline": statement("See the next step", OWNER),
                "subheadline": statement("Natal keeps the current action visible", OWNER), "cta": statement("Leave details", OWNER),
            },
            "value_sections": [
                {"title": statement(f"Value {index}"), "body": statement(f"Source-backed detail {index}")}
                for index in range(1, 4)
            ],
            "honest_limitation": statement("Results are not yet verified.", ""),
            "lead_capture_strategy": statement("Ask only for contact details", OWNER),
        },
        "ad_concepts": [
            {"kind": "contextual_relatable", "hook": statement("When the follow-up note gets lost"), "body": statement("Keep the next step visible", OWNER), "visual_direction": statement("Show a real planning moment", "")},
            {"kind": "direct_problem_solution", "hook": statement("Scattered follow-up needs one view"), "body": statement("Natal keeps the action visible", OWNER), "visual_direction": statement("Show the current-action view", OWNER)},
        ],
        "aeo_faqs": [
            {"question": statement(f"What is Natal {index}?", OWNER), "definition": statement("Natal is a focused planning tool.", OWNER), "data": statement("Available results are not yet verified.", ""), "context": statement("It is intended for small-team follow-up.", OWNER)}
            for index in range(1, 4)
        ],
        "evidence_references": [OWNER, RESEARCH],
        "assumptions": ["Emotional rewards and unverified results remain assumptions."],
    }


class PositioningDocumentTests(unittest.TestCase):
    def test_accepts_exact_five_section_contract_and_is_deterministic(self) -> None:
        first = PositioningDocumentV1.from_dict(document(), allowed_source_ids=[OWNER, RESEARCH], output_language="en")
        second = PositioningDocumentV1.from_dict(document(), allowed_source_ids=[RESEARCH, OWNER], output_language="en")
        self.assertEqual(first.digest, second.digest)
        self.assertTrue(first.quality_gates["passed"])
        self.assertEqual(len(first.value["ad_concepts"]), 2)
        self.assertEqual(len(first.value["aeo_faqs"]), 3)

    def test_rejects_unknown_source_uuid(self) -> None:
        candidate = document()
        candidate["positioning_foundation"]["category"] = statement("Unknown", "018f07ea-7f20-7000-8000-000000000099")
        with self.assertRaisesRegex(ValueError, "outside this revision"):
            PositioningDocumentV1.from_dict(candidate, allowed_source_ids=[OWNER, RESEARCH], output_language="en")

    def test_rejects_uncited_metric(self) -> None:
        candidate = document()
        candidate["messaging_matrix"][0]["emotional_reward"] = statement("Save 50% every week", "")
        with self.assertRaisesRegex(ValueError, "unsupported metric"):
            PositioningDocumentV1.from_dict(candidate, allowed_source_ids=[OWNER, RESEARCH], output_language="en")

    def test_rejects_invented_unsourced_limitation(self) -> None:
        candidate = document()
        candidate["landing_copy"]["honest_limitation"] = statement("We are charmingly imperfect.", "")
        with self.assertRaisesRegex(ValueError, "results are not yet verified"):
            PositioningDocumentV1.from_dict(candidate, allowed_source_ids=[OWNER, RESEARCH], output_language="en")

    def test_markdown_keeps_source_and_assumption_markers(self) -> None:
        value = PositioningDocumentV1.from_dict(document(), allowed_source_ids=[OWNER, RESEARCH], output_language="en")
        exported = markdown_export(value.value)
        self.assertIn("## 5. AEO FAQs", exported)
        self.assertIn(f"[sources: {OWNER}]", exported)
        self.assertIn("[assumption]", exported)


if __name__ == "__main__":
    unittest.main()
