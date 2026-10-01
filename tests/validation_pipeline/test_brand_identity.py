"""Versioned brand strategy: real language/claim bounds and frozen readers."""
from copy import deepcopy
import unittest

from tests.validation_pipeline.test_marketing_approaches import document
from tests.validation_pipeline.test_studio_agent_copy import BRIEF as UK_BRIEF
from validation_pipeline.domain import ProductBriefV2, ProductBriefV3, parse_product_brief, product_brief_schema
from validation_pipeline.marketing import generation_settings
from validation_pipeline.service import product_brief_system_prompt
from validation_pipeline.image_generation_policy import build_image_context, compile_image_prompt, instruction_context, MAX_IMAGE_PROMPT_CHARS


class BrandIdentityTests(unittest.TestCase):
    def test_both_approaches_and_languages_match_the_reserved_contract(self):
        for language in ("en", "uk"):
            for selected in ("benefit_led", "identity_led"):
                with self.subTest(language=language, selected=selected):
                    value = document(selected, version=3) if language == "en" else deepcopy(UK_BRIEF)
                    value["positioning"]["marketing_approach"] = selected
                    settings = generation_settings(selected)
                    parsed = parse_product_brief(value, raw_idea="planner", required_language=language, generation_settings=settings)
                    self.assertEqual(value, parsed.to_dict())
                    self.assertTrue(parsed.quality_gates["brand_identity_bounded"])
                    schema = product_brief_schema(language, generation_settings=settings)
                    self.assertIn("brand_identity", schema["required"])
                    self.assertEqual(3, schema["properties"]["schema_version"]["const"])

    def test_brand_rejects_missing_extra_nontext_wrong_language_and_false_proof(self):
        for field, invalid in (("belief", ""), ("values", 42), ("proof_anchor", "Trusted by 500 customers"),
                               ("voice", "Ми пояснюємо зрозуміло"), ("belief", "x" * 261),
                               ("identity_signal", ""), ("emotional_reward", "")):
            value = document(version=3)
            value["brand_identity"][field] = invalid
            with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                ProductBriefV3.from_dict(value, raw_idea="planner")
        for extra in (True, False):
            value = document(version=3)
            if extra:
                value["brand_identity"]["new_logo"] = "Invented"
            else:
                value["brand_identity"].pop("belief")
            with self.assertRaisesRegex(ValueError, "fields mismatch"):
                ProductBriefV3.from_dict(value, raw_idea="planner")

    def test_optional_mechanics_and_aggregate_unicode_limit(self):
        value = document("benefit_led", version=3)
        for field in ("identity_signal", "emotional_reward", "cultural_tension", "ritual"):
            value["brand_identity"][field] = ""
        ProductBriefV3.from_dict(value, raw_idea="planner")
        value = deepcopy(UK_BRIEF)
        value["brand_identity"] = {field: "а" * 200 for field in value["brand_identity"]}
        with self.assertRaisesRegex(ValueError, "3072 UTF-8"):
            ProductBriefV3.from_dict(value, raw_idea="planner", required_language="uk")

    def test_v2_has_no_brand_and_cannot_be_silently_read_as_v3(self):
        value = document()
        old_settings = {**generation_settings("identity_led"), "output_schema_version": 2}
        self.assertEqual(value, parse_product_brief(value, raw_idea="planner", generation_settings=old_settings).to_dict())
        self.assertNotIn("brand_identity", product_brief_schema("en", generation_settings=old_settings)["properties"])
        self.assertIn("historical V2", product_brief_system_prompt("skill", "en", old_settings))
        with self.assertRaises(ValueError):
            parse_product_brief(value, raw_idea="planner", generation_settings=generation_settings("identity_led"))
        with self.assertRaises(ValueError):
            ProductBriefV2.from_dict(document(version=3), raw_idea="planner")

    def test_full_ukrainian_brand_and_owner_direction_fit_image_contract(self):
        for mode in ("image", "app_mockup", "app_screen"):
            owner = "Покажи людей біля авто. " * 170
            context = build_image_context(direction=owner, instruction=instruction_context(owner, origin="owner"),
                brief={"brief_id": "pinned-source", "document": UK_BRIEF}, settings={"style": "cinematic"},
                destination={"surface": "landing", "mode": mode, "slot": "hero_visual"},
                operation="generate", base_sha256="a" * 64)
            self.assertEqual(UK_BRIEF["brand_identity"], context["brief"]["document"]["brand_identity"])
            prompt = compile_image_prompt(context)
            self.assertIn("brand_identity.visual_world", prompt)
            self.assertLess(len(prompt), MAX_IMAGE_PROMPT_CHARS)
