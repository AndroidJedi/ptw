from __future__ import annotations

from pathlib import Path
import unittest

from validation_pipeline.domain import product_brief_schema
from validation_pipeline.service import ValidationRunner


ROOT = Path(__file__).resolve().parents[2]
BRIEF_ID = "01900000-0000-7000-8000-000000000011"


class FakeRepository:
    def __init__(self, attempt_number: int = 2, required_language: str | None = "en") -> None:
        self.attempt_number = attempt_number
        self.required_language = required_language
        self.created_invocation: dict = {}
        self.completed_invocation: dict = {}
        self.failed_invocation: dict = {}
        self.finished = False
        self.released = False

    def get_brief(self, _brief_id: str) -> dict:
        return {"brief_id": BRIEF_ID, "status": "queued", "base_brief_id": None}

    def start_attempt(self, _brief_id: str, *, stage: str) -> tuple[str, int]:
        self.assert_stage = stage
        return "01900000-0000-7000-8000-000000000012", self.attempt_number

    def source(self, _brief_id: str) -> dict[str, str | None]:
        return {
            "content": "An English idea for one focused validation service.",
            "required_language": self.required_language,
        }

    def create_invocation(self, **value) -> dict[str, str]:
        self.created_invocation = value
        return {"id": "01900000-0000-7000-8000-000000000013"}

    def complete_invocation(self, invocation_id: str, response: dict, provenance: dict) -> None:
        self.completed_invocation = {
            "invocation_id": invocation_id, "response": response, "provenance": provenance,
        }

    def fail_invocation(
        self, invocation_id: str, error: Exception, provenance: dict | None = None,
    ) -> None:
        self.failed_invocation = {
            "invocation_id": invocation_id, "error": error,
            "provenance": dict(provenance or {}),
        }

    def finish_brief(self, *_args) -> None:
        self.finished = True

    def fail_attempt(self, *_args, **_kwargs) -> None:
        return None

    def release_operation(self, _brief_id: str) -> None:
        self.released = True


class FakeBridge:
    def __init__(self, language: str = "en") -> None:
        self.language = language
        self.call: dict = {}

    def generate(self, **value) -> dict:
        self.call = value
        if self.language == "uk":
            document = {
                "schema_version": 1,
                "language": "uk",
                "product": "Сесія сфокусованої перевірки",
                "target_audience": "Люди, які перевіряють одну ранню ідею послуги",
                "main_pain": "Перша ринкова обіцянка досі нечітка",
                "promise": "Перетворити одну ідею на конкретний крок перевірки",
                "key_benefits": [
                    "Одна сфокусована гіпотеза", "Один практичний наступний крок",
                    "Простіший початок",
                ],
                "cta": "Забронювати першу сесію",
                "trust_strategy": "Пояснити процес і межі до зобов'язання",
                "offer": "Безкоштовна 15-хвилинна консультація наставника",
            }
        else:
            document = {
                "schema_version": 1,
                "language": "en",
                "product": "Focused Validation Session",
                "target_audience": "People testing one early service idea",
                "main_pain": "The first market promise is still unclear",
                "promise": "Turn one idea into a concrete validation step",
                "key_benefits": [
                    "One focused hypothesis", "One practical next step", "A lower-friction start",
                ],
                "cta": "Book the first session",
                "trust_strategy": "Explain the process and scope before commitment",
                "offer": "Free 15-minute mentor call",
            }
        return {
            "response": document,
            "invocation": {"bridge_request_id": 912, "bridge_attempt": 1},
        }


class ProductBriefServiceTests(unittest.TestCase):
    def test_schema_can_bind_the_owner_selected_language(self) -> None:
        self.assertEqual("en", product_brief_schema("en")["properties"]["language"]["const"])
        with self.assertRaisesRegex(ValueError, "must be uk or en"):
            product_brief_schema("fr")

    def test_generation_binds_language_and_uses_a_fresh_attempt_key(self) -> None:
        repository = FakeRepository(attempt_number=2)
        bridge = FakeBridge()
        runner = ValidationRunner(
            repository, bridge,
            product_brief_skill_path=ROOT / "skills/product-brief-generator/SKILL.md",
        )

        runner.generate_brief(BRIEF_ID, operation_reserved=True)

        expected_key = f"{BRIEF_ID}:product_brief:attempt-2"
        self.assertEqual("en", bridge.call["input_payload"]["required_language"])
        self.assertEqual("en", bridge.call["output_schema"]["properties"]["language"]["const"])
        self.assertIn("required_language=en", bridge.call["system_prompt"])
        self.assertEqual(expected_key, bridge.call["idempotency_key"])
        self.assertEqual(expected_key, repository.created_invocation["idempotency_key"])
        self.assertEqual(912, repository.completed_invocation["provenance"]["bridge_request_id"])
        self.assertTrue(repository.finished)
        self.assertTrue(repository.released)

    def test_language_rejection_preserves_provider_request_provenance(self) -> None:
        repository = FakeRepository()
        runner = ValidationRunner(
            repository, FakeBridge(language="uk"),
            product_brief_skill_path=ROOT / "skills/product-brief-generator/SKILL.md",
        )

        with self.assertRaisesRegex(ValueError, "required language"):
            runner.generate_brief(BRIEF_ID, operation_reserved=True)

        self.assertEqual(912, repository.failed_invocation["provenance"]["bridge_request_id"])
        self.assertFalse(repository.finished)
        self.assertTrue(repository.released)

    def test_english_idea_uses_persisted_ukrainian_language(self) -> None:
        repository = FakeRepository(required_language="uk")
        bridge = FakeBridge(language="uk")
        runner = ValidationRunner(
            repository, bridge,
            product_brief_skill_path=ROOT / "skills/product-brief-generator/SKILL.md",
        )

        runner.generate_brief(BRIEF_ID, operation_reserved=True)

        self.assertEqual("uk", bridge.call["input_payload"]["required_language"])
        self.assertEqual("uk", repository.completed_invocation["response"]["language"])
        self.assertIn("Безкоштовна", repository.completed_invocation["response"]["offer"])


if __name__ == "__main__":
    unittest.main()
