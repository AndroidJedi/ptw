from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from commander.ids import new_uuid7
from validation_pipeline.content import (
    CandidateV2, CorpusStore, INSTAGRAM_REQUIRED_VISUAL_ROLES, TemplateRegistry,
    candidate_output_schema, final_eligible, weighted_candidate_score,
)
from validation_pipeline.content_adapters import InstagramStaticAdapter
from validation_pipeline.natal_brand import (
    NATAL_FONT_PATH, NATAL_FONT_SHA256, NATAL_LOGO_SHA256,
    natal_brand_document, natal_logo_bytes,
)
from validation_pipeline.studio import StudioRenderer, validate_recipe


ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "skills/content-candidate-generator/references"


class ResultContractsTests(unittest.TestCase):
    def test_natal_identity_assets_and_contract_are_canonical(self) -> None:
        import hashlib

        self.assertEqual(NATAL_LOGO_SHA256, hashlib.sha256(natal_logo_bytes()).hexdigest())
        self.assertEqual(NATAL_FONT_SHA256, hashlib.sha256(NATAL_FONT_PATH.read_bytes()).hexdigest())
        document = natal_brand_document(new_uuid7())
        self.assertEqual("Natal", document["name"])
        self.assertEqual("#0C0E12", document["colors"][0])
        self.assertEqual(["Inter"], document["fonts"])

    @unittest.skipUnless(importlib.util.find_spec("PIL") is not None, "Pillow is required")
    def test_restored_natal_logo_and_inter_render_inside_instagram_jpeg(self) -> None:
        from io import BytesIO
        from PIL import Image

        project_id, brief_id, brand_kit_id, logo_id, media_id = [new_uuid7() for _ in range(5)]
        element_ids = {
            role: new_uuid7() for role in (
                "background", "primary_subject", "headline_block", "supporting_text_block",
                "offer_block", "cta_block", "brand_mark",
            )
        }
        candidate = {
            "hook": "One visible customer moment",
            "supporting_text": "A short, concrete mechanism.",
            "offer": "First consultation free", "cta": "Book now",
            "caption": "A complete caption.",
            "alt_text": "A real scene that demonstrates the customer moment.",
            "visual_components": [
                {"role": "composition", "content": "Subject on the right", "source_ids": []},
                {"role": "lighting_style", "content": "Natural daylight", "source_ids": []},
            ],
        }
        brand = natal_brand_document(logo_id)
        template = TemplateRegistry(REFERENCES / "templates").load_active()[0]
        adapter = InstagramStaticAdapter(None, None, None, None)
        recipe = adapter._recipe(
            candidate=candidate,
            run={
                "candidate_template_id": template.template_id,
                "candidate_parameters": dict(template.defaults),
                "context_bundle": {"brand_kit": {"document": brand}},
            },
            element_ids=element_ids,
            media_id=media_id,
        )
        contract = validate_recipe(
            recipe, project_id=project_id, brief_id=brief_id,
            brand_kit_id=brand_kit_id,
            brief={"offer": candidate["offer"], "cta": candidate["cta"]},
        )
        media_output = BytesIO()
        Image.new("RGB", (1080, 1080), "#4A4A4A").save(media_output, format="JPEG")
        rendered = StudioRenderer().render(
            recipe_id=new_uuid7(), recipe_digest=contract.digest,
            recipe=contract.value, brand_kit={"document": brand},
            assets={
                logo_id: {"bytes": natal_logo_bytes(), "mime_type": "image/png"},
                media_id: {"bytes": media_output.getvalue(), "mime_type": "image/jpeg"},
            },
        )
        with Image.open(BytesIO(rendered["bytes"])) as image:
            self.assertEqual((1080, 1080), image.size)
            self.assertEqual("JPEG", image.format)

    def test_registry_contains_exactly_five_distinct_strategies(self) -> None:
        templates = TemplateRegistry(REFERENCES / "templates").load_active()
        self.assertEqual(5, len(templates))
        self.assertEqual(5, len({item.template_id for item in templates}))
        self.assertEqual(
            [
                "moment_tension", "contrast_reframe", "mechanism_proof",
                "human_story", "direct_offer",
            ],
            [item.template_id for item in templates],
        )

    def test_slider_adjustments_are_meaningful_and_bounded(self) -> None:
        template = TemplateRegistry(REFERENCES / "templates").load_active()[0]
        current = dict(template.defaults)
        invalid = dict(current); invalid["hook_pressure"] -= 5
        with self.assertRaisesRegex(ValueError, "at least ten"):
            template.validate_adjustment(current, invalid)
        valid = dict(current); valid["hook_pressure"] -= 10
        self.assertEqual(valid, template.validate_adjustment(current, valid))

    def test_corpus_is_exactly_40_and_negative_examples_are_not_retrieved(self) -> None:
        store = CorpusStore(REFERENCES / "corpus/manifest.json", REFERENCES / "corpus/examples.jsonl")
        _manifest, examples, _digest = store.load()
        self.assertEqual(40, len(examples))
        selected = store.retrieve(
            examples, language="uk", output_profile="instagram_static_ad_v1",
            technique="hooks", audience="small business owner", count=6,
        )
        self.assertTrue(all(item.quality_tier != "negative" for item in selected))
        self.assertTrue(all(sum(one.source_project == item.source_project for one in selected) <= 2 for item in selected))

    def test_candidate_preserves_exact_offer_and_cta(self) -> None:
        brief = {"offer": "First consultation free", "cta": "Book now"}
        value = {
            "schema_version": 2, "hook": "At 23:00, the question is still open.",
            "headline": "Start with one conversation", "primary_text": "A clear first step.",
            "supporting_text": "Real people. Transparent process.",
            "offer": brief["offer"], "cta": brief["cta"], "caption": "One next step.",
            "alt_text": "Text-only marketing result.", "desired_emotion": "calm confidence",
            "visual_concept": "No visual for text profile.",
            "media_request": {"kind": "none", "query": "", "source_asset_id": None, "reason": "Text profile."},
            "visual_components": [],
        }
        self.assertEqual(brief["offer"], CandidateV2.from_dict(
            value, brief=brief, output_profile="marketing_copy_v1"
        ).value["offer"])
        value["cta"] = "Different"
        with self.assertRaisesRegex(ValueError, "exact Product Brief"):
            CandidateV2.from_dict(value, brief=brief, output_profile="marketing_copy_v1")

    def test_candidate_schema_allows_only_server_supplied_uuid_references(self) -> None:
        brief_id, logo_id, approved_photo_id = [new_uuid7() for _ in range(3)]
        schema = candidate_output_schema(
            output_profile="instagram_static_ad_v1",
            allowed_source_ids=[brief_id, logo_id, approved_photo_id],
            approved_asset_ids=[logo_id, approved_photo_id],
        )

        media_schema = schema["properties"]["media_request"]["properties"]["source_asset_id"]
        source_schema = schema["properties"]["visual_components"]["items"]["properties"]["source_ids"]
        self.assertEqual([None, *sorted([logo_id, approved_photo_id])], media_schema["enum"])
        self.assertEqual(sorted([brief_id, logo_id, approved_photo_id]), source_schema["items"]["enum"])
        self.assertNotIn("studio.frame.media.v1", source_schema["items"]["enum"])
        visual_schema = schema["properties"]["visual_components"]
        self.assertEqual(9, visual_schema["minItems"])
        self.assertEqual(9, visual_schema["maxItems"])
        self.assertEqual(
            list(INSTAGRAM_REQUIRED_VISUAL_ROLES),
            visual_schema["items"]["properties"]["role"]["enum"],
        )
        self.assertNotIn(
            "decorative_element", visual_schema["items"]["properties"]["role"]["enum"]
        )

        value = {
            "schema_version": 2, "hook": "A concrete opening",
            "headline": "One clear next step", "primary_text": "A specific mechanism.",
            "supporting_text": "A bounded supporting line.",
            "offer": "First consultation free", "cta": "Book now",
            "caption": "A complete caption.", "alt_text": "A complete alt description.",
            "desired_emotion": "calm confidence", "visual_concept": "One real scene.",
            "media_request": {
                "kind": "pexels_real_photo", "query": "adult at desk",
                "source_asset_id": None, "reason": "A real photograph supports the message.",
            },
            "visual_components": [
                {"role": role, "content": role.replace("_", " "), "source_ids": []}
                for role in (
                    "background", "primary_subject", "headline_block", "supporting_text_block",
                    "offer_block", "cta_block", "brand_mark", "lighting_style", "composition",
                )
            ],
        }
        value["visual_components"][0]["source_ids"] = ["studio.frame.media.v1"]
        with self.assertRaisesRegex(ValueError, "server-supplied UUIDs"):
            CandidateV2.from_dict(
                value, brief={"offer": value["offer"], "cta": value["cta"]},
                output_profile="instagram_static_ad_v1",
                allowed_source_ids=[brief_id, logo_id, approved_photo_id],
                approved_asset_ids=[logo_id, approved_photo_id],
            )

    def test_final_thresholds_fail_closed(self) -> None:
        scores = {
            "task_brief_suitability": 8, "hook_strength": 7, "message_clarity": 8,
            "persuasion_action": 7, "coherence": 8, "specificity_credibility": 10,
            "composition_legibility": 10, "originality_tone": 10,
        }
        self.assertGreaterEqual(weighted_candidate_score(scores, "none"), 80)
        evaluation = {
            "complexity": "none", "hard_gates": {"all": True}, "scores": scores,
            "element_scores": {"hook": {"contribution": 7}},
        }
        self.assertTrue(final_eligible(evaluation))
        evaluation["element_scores"] = {"hook": {"contribution": 6}}
        self.assertFalse(final_eligible(evaluation))

    def test_five_templates_map_to_five_valid_distinct_instagram_layouts(self) -> None:
        templates = TemplateRegistry(REFERENCES / "templates").load_active()
        project_id, brief_id, brand_kit_id, logo_id, media_id = [new_uuid7() for _ in range(5)]
        element_ids = {
            role: new_uuid7() for role in (
                "background", "primary_subject", "headline_block", "supporting_text_block",
                "offer_block", "cta_block", "brand_mark",
            )
        }
        candidate = {
            "hook": "One visible customer moment",
            "headline": "A specific headline",
            "supporting_text": "A short, concrete mechanism.",
            "offer": "First consultation free",
            "cta": "Book now",
            "caption": "A complete caption.",
            "alt_text": "A real scene that demonstrates the customer moment.",
            "visual_components": [
                {"role": "composition", "content": "Subject on the right", "source_ids": []},
                {"role": "lighting_style", "content": "Natural daylight", "source_ids": []},
            ],
        }
        brand = {
            "name": "PTW Test", "colors": ["#111111", "#FFFFFF", "#43BDD3", "#F4F2EC"],
            "fonts": ["Inter"], "tone_notes": "Direct", "logo_source_asset_id": logo_id,
        }
        adapter = InstagramStaticAdapter(None, None, None, None)
        layouts = set()
        for template in templates:
            run = {
                "candidate_template_id": template.template_id,
                "candidate_parameters": dict(template.defaults),
                "context_bundle": {"brand_kit": {"document": brand}},
            }
            recipe = adapter._recipe(
                candidate=candidate, run=run, element_ids=element_ids, media_id=media_id,
            )
            contract = validate_recipe(
                recipe, project_id=project_id, brief_id=brief_id,
                brand_kit_id=brand_kit_id,
                brief={"offer": candidate["offer"], "cta": candidate["cta"]},
            )
            frame_map = tuple(
                (frame["tool_id"], tuple(frame["frame"].values()))
                for frame in contract.value["frames"]
                if frame["tool_id"] in {"studio.frame.media.v1", "studio.frame.headline.v1"}
            )
            layouts.add(frame_map)
        self.assertEqual(5, len(layouts))


if __name__ == "__main__":
    unittest.main()
