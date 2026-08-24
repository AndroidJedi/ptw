from __future__ import annotations

import unittest

from validation_pipeline.domain import (
    CREATIVE_ANGLES,
    CreativeSetV1,
    ProductBriefV1,
    creative_set_schema,
    infer_language,
    product_brief_schema,
)


def brief(**changes):
    value = {
        "schema_version": 1,
        "language": "en",
        "product": "Online consultations with licensed psychologists.",
        "target_audience": "English-speaking first-time therapy seekers.",
        "main_pain": "Finding a trustworthy first consultation feels difficult.",
        "promise": "Meet a suitable psychologist with a low-risk first step.",
        "key_benefits": ["Simple matching", "Real consultant profiles", "Easy booking"],
        "cta": "Get free consultation",
        "trust_strategy": "Show real consultants and transparent pricing; no card required.",
        "offer": "First consultation free",
    }
    value.update(changes)
    return value


def creative_set(**item_changes):
    return {
        "schema_version": 1,
        "creatives": [
            {
                "angle": angle,
                "hook": f"{angle.replace('_', ' ').title()} path to support",
                "primary_text": "First consultation free. Meet a real psychologist with less friction.",
                "image_description": "A real adult speaking calmly with a professional.",
                "cta": "Get free consultation",
                "offer": "First consultation free",
                "desired_emotion": "calm confidence",
                "image_category": "professional conversation",
                "image_search_query": f"real people {angle} professional conversation",
                "crop_focus": "center",
                **item_changes,
            }
            for angle in CREATIVE_ANGLES
        ],
    }


class ProductBriefContractTests(unittest.TestCase):
    def test_language_inference_prefers_dominant_script_and_defaults_to_english(self) -> None:
        self.assertEqual("uk", infer_language("Онлайн консультації психолога"))
        self.assertEqual("en", infer_language("Online consultation"))
        self.assertEqual("en", infer_language("12345!?"))

    def test_strict_shape_benefit_bounds_offer_and_digest(self) -> None:
        first = ProductBriefV1.from_dict(brief(), raw_idea="Psychologist consultations online")
        second = ProductBriefV1.from_dict(brief(), raw_idea="Psychologist consultations online")
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(64, len(first.digest))
        for bad in (
            brief(key_benefits=["one", "two"]),
            brief(key_benefits=["one", "two", "three", "four", "five", "six"]),
            brief(offer=""),
            brief(offer="A pleasant welcome"),
            {**brief(), "market_report": "forbidden"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ProductBriefV1.from_dict(bad, raw_idea="Psychologist consultations online")

    def test_fabricated_testimonial_rating_and_customer_count_are_rejected(self) -> None:
        for promise in (
            "Our customer said this changed her life",
            "Rated 4.9/5",
            "Trusted by 10,000 customers",
        ):
            with self.subTest(promise=promise), self.assertRaisesRegex(ValueError, "fabricated proof"):
                ProductBriefV1.from_dict(brief(promise=promise), raw_idea="Psychologist consultations online")

    def test_creatives_require_fixed_angles_exact_cta_and_offer(self) -> None:
        value = CreativeSetV1.from_dict(creative_set(), brief=brief())
        self.assertEqual(CREATIVE_ANGLES, tuple(item["angle"] for item in value.value))
        self.assertTrue(value.quality_gates["brief_offer_preserved"])
        wrong_order = creative_set()
        wrong_order["creatives"][0]["angle"] = "practical"
        with self.assertRaisesRegex(ValueError, "angle"):
            CreativeSetV1.from_dict(wrong_order, brief=brief())
        with self.assertRaisesRegex(ValueError, "CTA"):
            CreativeSetV1.from_dict(creative_set(cta="Click"), brief=brief())
        with self.assertRaisesRegex(ValueError, "offer"):
            CreativeSetV1.from_dict(creative_set(primary_text="A lower-friction next step."), brief=brief())
        with self.assertRaisesRegex(ValueError, "offer field"):
            CreativeSetV1.from_dict(creative_set(offer="First session discounted"), brief=brief())

    def test_offer_field_is_exact_but_copy_allows_sentence_punctuation(self) -> None:
        product_brief = brief(offer="Free 15-minute mentor call.")
        value = creative_set(
            offer=product_brief["offer"],
            primary_text="Continue with a Free 15-minute mentor call from a real mentor.",
        )
        result = CreativeSetV1.from_dict(value, brief=product_brief)
        self.assertTrue(result.quality_gates["brief_offer_preserved"])

    def test_json_schemas_type_every_const_and_forbid_extra_fields(self) -> None:
        self.assertEqual({"type": "integer", "const": 1}, product_brief_schema()["properties"]["schema_version"])
        self.assertEqual({"type": "integer", "const": 1}, creative_set_schema()["properties"]["schema_version"])
        bound = creative_set_schema(brief=brief())["properties"]["creatives"]["items"]["properties"]
        self.assertEqual({"type": "string", "const": brief()["offer"]}, bound["offer"])
        self.assertEqual({"type": "string", "const": brief()["cta"]}, bound["cta"])
        self.assertFalse(product_brief_schema()["additionalProperties"])
        self.assertEqual(5, creative_set_schema()["properties"]["creatives"]["minItems"])


if __name__ == "__main__":
    unittest.main()
