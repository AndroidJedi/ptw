from __future__ import annotations

import unittest

from natal.page import page_content_from_brief
from owner_gateway.landing_revision import LandingRevisionProvider, MODE


RUN_ID = "01234567-89ab-7def-8123-456789abcdef"


def brief() -> dict:
    return {
        "schema_version": 1,
        "brand": "Natal",
        "language": "uk",
        "source": {"laval_run_id": RUN_ID},
        "business_idea": "Початкова ідея",
        "target_audience": "Власники сервісних бізнесів",
        "pain": "Клієнти зникають непомітно",
        "promise": "Наступна дія стає видимою",
        "key_features": [{"title": "Сигнали", "description": "Показують ризик"}],
        "steps": [
            {"title": "01", "description": "Підключити дані"},
            {"title": "02", "description": "Побачити ризик"},
        ],
        "proof_points": ["Перевірений доказ"],
        "faq": [],
        "cta": {"label": "Спробувати Natal", "url": "#contact"},
    }


class Bridge:
    def __init__(self) -> None:
        self.last_invocation = {
            "session_id": "61234567-89ab-7def-8123-456789abcdef",
            "session_mode": "fresh",
            "conversation_reused": False,
        }
        self.prepared = None
        self.call = None

    def capabilities(self):
        return {"landing_modes": [MODE]}

    def prepare_invocation(self, version: str, context_hash: str):
        self.prepared = (version, context_hash)

    def generate_structured(self, mode, system_prompt, payload, schema):
        self.call = (mode, system_prompt, payload, schema)
        return {
            "brief": {
                "language": "uk",
                "business_idea": "Коротша ідея",
                "target_audience": "Власники сервісних бізнесів",
                "pain": "Втрата клієнтів стає видимою надто пізно",
                "promise": "Покажіть наступну дію раніше",
                "key_features": [{"title": "Сигнал", "description": "Показує ризик раніше"}],
                "steps": [
                    {"title": "01", "description": "Підключіть дані"},
                    {"title": "02", "description": "Оберіть дію"},
                ],
                "proof_points": ["Перевірений доказ", "Вигаданий доказ"],
                "faq": [],
                "cta": {"label": "Побачити наступну дію", "url": "https://malicious.test"},
            },
            "application_summary": "Скорочено hero й посилено CTA.",
        }


class LandingRevisionProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = LandingRevisionProvider.__new__(LandingRevisionProvider)
        self.provider.skill_contract = "Keep the Natal brand and apply owner feedback."
        self.provider.bridge = Bridge()

    def test_requires_landing_bridge_mode(self) -> None:
        self.provider.verify_ready()
        self.provider.bridge.capabilities = lambda: {"landing_modes": []}
        with self.assertRaisesRegex(RuntimeError, "mode is unavailable"):
            self.provider.verify_ready()

    def test_applies_skill_memory_but_preserves_source_cta_target_and_verified_proof(self) -> None:
        revised, summary, invocation = self.provider.revise(
            template_id="community",
            brief=brief(),
            skill_memory=[{
                "id": "11234567-89ab-7def-8123-456789abcdef",
                "template_id": "product",
                "revision_number": 1,
                "comment": "Shorten the hero and strengthen the CTA.",
            }],
        )
        self.assertEqual("Коротша ідея", revised["business_idea"])
        self.assertEqual({"laval_run_id": RUN_ID}, revised["source"])
        self.assertEqual("#contact", revised["cta"]["url"])
        self.assertEqual(["Перевірений доказ"], revised["proof_points"])
        self.assertEqual("Скорочено hero й посилено CTA.", summary)
        self.assertEqual(MODE, invocation["mode"])
        self.assertEqual(["11234567-89ab-7def-8123-456789abcdef"], invocation["feedback_ids"])
        self.assertEqual(MODE, self.provider.bridge.call[0])
        self.assertEqual("community", self.provider.bridge.call[2]["target_template"]["id"])

    def test_populates_all_templates_in_one_strict_call_and_reapplies_proof(self) -> None:
        calls = []

        def generate(mode, system_prompt, payload, schema):
            calls.append((mode, system_prompt, payload, schema))
            pages = {
                template_id: page_content_from_brief(template_id, brief()).to_dict()
                for template_id in ("product", "community", "waitlist")
            }
            for page in pages.values():
                page["blocks"]["proof"]["items"] = ["Вигаданий доказ"]
            return {"pages": pages, "application_summary": "Підготовлено три окремі варіанти."}

        self.provider.bridge.generate_structured = generate
        pages, summary, invocation = self.provider.populate_set(
            brief=brief(), skill_memory=[]
        )
        self.assertEqual(1, len(calls))
        self.assertEqual({"product", "community", "waitlist"}, set(pages))
        for template_id, page in pages.items():
            self.assertEqual(template_id, page["template_id"])
            self.assertEqual(["Перевірений доказ"], page["blocks"]["proof"]["items"])
        self.assertEqual("Підготовлено три окремі варіанти.", summary)
        self.assertEqual("populate_set", invocation["operation"])
        schema = calls[0][3]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(["product", "community", "waitlist"], schema["properties"]["pages"]["required"])

    def test_population_rejects_fields_outside_the_strict_response_schema(self) -> None:
        pages = {
            template_id: page_content_from_brief(template_id, brief()).to_dict()
            for template_id in ("product", "community", "waitlist")
        }
        self.provider.bridge.generate_structured = lambda *args: {
            "pages": pages,
            "application_summary": "Підготовлено варіанти.",
            "unexpected": True,
        }
        with self.assertRaisesRegex(ValueError, "strict response schema"):
            self.provider.populate_set(brief=brief(), skill_memory=[])

    def test_block_edit_returns_only_target_block_with_scoped_memory(self) -> None:
        current = page_content_from_brief("community", brief()).to_dict()

        def generate(mode, system_prompt, payload, schema):
            self.provider.bridge.call = (mode, system_prompt, payload, schema)
            return {
                "block": {
                    "eyebrow": "Конкретний результат",
                    "title": "Побачте ризик раніше",
                    "items": [{"title": "Сигнал", "description": "Показує наступну дію"}],
                },
                "application_summary": "Оновлено лише features.",
                "reusable_lesson": "Починайте features з конкретного результату.",
            }

        self.provider.bridge.generate_structured = generate
        block, summary, lesson, invocation = self.provider.edit_block(
            template_id="community", brief=brief(), page_content=current,
            block_id="features", instruction="Зроби результат конкретним",
            skill_memory=[{
                "id": "11234567-89ab-7def-8123-456789abcdef",
                "template_id": "community", "block_id": "hero",
                "snapshot_number": 1, "revision_number": 0, "comment": "Коротший hero",
            }],
        )
        self.assertEqual("Побачте ризик раніше", block["title"])
        self.assertNotIn("hero", block)
        self.assertEqual("Оновлено лише features.", summary)
        self.assertEqual("Починайте features з конкретного результату.", lesson)
        self.assertEqual("edit_block:features", invocation["operation"])
        payload = self.provider.bridge.call[2]
        self.assertEqual("features", payload["target_block"])
        self.assertEqual("hero", payload["skill_memory"][0]["reviewed_block"])
        self.assertFalse(self.provider.bridge.call[3]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
