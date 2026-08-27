from __future__ import annotations

import importlib.util
import copy
import hashlib
import json
from pathlib import Path
import unittest

from commander.ids import new_uuid7
from validation_pipeline.content import (
    CandidateV2, CorpusStore, INSTAGRAM_REQUIRED_VISUAL_ROLES, TemplateRegistry,
    candidate_output_schema, critic_output_schema, final_eligible, weighted_candidate_score,
)
from validation_pipeline.content_adapters import InstagramStaticAdapter
from validation_pipeline.natal_brand import (
    NATAL_COLORS, NATAL_FONT_PATH, NATAL_FONT_SHA256, NATAL_LOGO_SHA256,
    natal_brand_document, natal_logo_bytes,
)
from validation_pipeline.studio import StudioRenderer, tool_catalog, validate_recipe
from validation_pipeline.studio_templates import (
    StudioTemplateRegistry, apply_studio_template, replay_template_application,
)
from validation_pipeline.verify_studio_templates import run_canary


ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "skills/content-candidate-generator/references"


class ResultContractsTests(unittest.TestCase):
    @staticmethod
    def _recipe_run(template, brand, brief):
        return {
            "candidate_template_id": template.template_id,
            "candidate_parameters": dict(template.defaults),
            "context_bundle": {
                "brand_kit": {"document": brand}, "brief": {"document": brief},
                "template_versions": [{
                    "template_id": template.template_id, "version": template.version,
                    "digest": template.digest,
                    "studio_template_version": template.studio_template_version,
                    "studio_template_sha256": template.studio_template_sha256,
                }],
            },
        }

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
        brief = {"offer": candidate["offer"], "cta": candidate["cta"]}
        recipe = adapter._recipe(
            candidate=candidate,
            run=self._recipe_run(template, brand, brief),
            element_ids=element_ids,
            media_id=media_id,
        )
        contract = validate_recipe(
            recipe, project_id=project_id, brief_id=brief_id,
            brand_kit_id=brand_kit_id,
            brief=brief, brand_document=brand,
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

    @unittest.skipUnless(importlib.util.find_spec("PIL") is not None, "Pillow is required")
    def test_non_persisting_five_template_canary(self) -> None:
        report = run_canary()
        self.assertEqual("ok", report["status"])
        self.assertEqual(5, len(report["templates"]))
        self.assertEqual(10, len(report["pairwise_distinction"]))
        self.assertEqual({"en": 5, "uk": 5}, report["language_renders"])

    @unittest.skipUnless(importlib.util.find_spec("PIL") is not None, "Pillow is required")
    def test_historical_v1_renderer_pixels_remain_byte_identical(self) -> None:
        from io import BytesIO
        from PIL import Image

        media = BytesIO()
        Image.new("RGB", (1080, 1080), "#765A50").save(media, format="JPEG", quality=90)
        recipe = {
            "width": 1080, "height": 1080,
            "placement_tool_id": "studio.placement.instagram.feed_square.v1",
            "frames": [
                {"instance_id":"01900000-0000-7000-8000-000000000001","tool_id":"studio.frame.shape.v1","frame":{"x":0,"y":0,"width":1,"height":1},"z_index":0,"params":{"background":"#0C0E12","opacity":1,"radius":0},"timeline":None,"source_asset_ids":[]},
                {"instance_id":"01900000-0000-7000-8000-000000000002","tool_id":"studio.frame.media.v1","frame":{"x":0,"y":0,"width":1,"height":0.5},"z_index":1,"params":{"fit":"cover","focal_x":0.5,"focal_y":0.5},"timeline":None,"source_asset_ids":["01900000-0000-7000-8000-000000000010"]},
                {"instance_id":"01900000-0000-7000-8000-000000000003","tool_id":"studio.frame.headline.v1","frame":{"x":0.06,"y":0.55,"width":0.88,"height":0.12},"z_index":2,"params":{"text":"A stable historical headline","color":"#F4F6FA","font_size":54,"min_font_size":21,"max_lines":4,"line_height":1.02},"timeline":None,"source_asset_ids":[]},
                {"instance_id":"01900000-0000-7000-8000-000000000004","tool_id":"studio.frame.body.v1","frame":{"x":0.06,"y":0.7,"width":0.88,"height":0.08},"z_index":3,"params":{"text":"Historical body remains byte stable.","color":"#F4F6FA","font_size":25,"min_font_size":17,"max_lines":4,"line_height":1.04},"timeline":None,"source_asset_ids":[]},
            ],
            "modifiers": [], "strategy_ids": [], "validation_ids": [],
        }
        rendered = StudioRenderer().render(
            recipe_id="01900000-0000-7000-8000-000000000020", recipe_digest="b" * 64,
            recipe=recipe, brand_kit={"document": {"colors": list(NATAL_COLORS), "fonts": ["Inter"]}},
            assets={"01900000-0000-7000-8000-000000000010": {
                "bytes": media.getvalue(), "mime_type": "image/jpeg",
            }},
        )
        self.assertEqual(
            "083bddb9bbb6981a4e8a78a0368ffcd0dc30761395381f31326d2fc2be99ad6d",
            hashlib.sha256(rendered["bytes"]).hexdigest(),
        )

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
        studios = StudioTemplateRegistry().load_active(templates)
        self.assertEqual([item.template_id for item in templates], [item.template_id for item in studios])
        self.assertTrue(all(item.version == 2 for item in studios))

    def test_catalog_components_are_strict_predefined_and_tunable(self) -> None:
        catalog = tool_catalog()
        self.assertEqual(2, catalog["schema_version"])
        self.assertEqual(64, len(catalog["catalog_sha256"]))
        components = [item for item in catalog["items"] if item["kind"] == "frame"]
        self.assertEqual(
            {"media", "logo", "headline", "body", "offer", "cta", "badge", "shape"},
            {item["tool_id"].split(".")[-2] for item in components},
        )
        for component in components:
            self.assertFalse(component["parameter_schema"]["additionalProperties"])
            self.assertEqual(["studio.placement.instagram.feed_square.v1"], component["allowed_placements"])
            self.assertTrue(component["tunable_paths"])

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

    def test_critic_schema_binds_action_ids_and_complete_slider_shape(self) -> None:
        candidate_ids = [new_uuid7(), new_uuid7()]
        element_ids = [new_uuid7(), new_uuid7()]
        schema = critic_output_schema(3, candidate_ids, element_ids)
        action = schema["properties"]["actions"]["items"]["properties"]

        self.assertEqual([None, *candidate_ids], action["base_candidate_id"]["enum"])
        self.assertEqual([None], action["template_id"]["enum"])
        self.assertFalse(action["slider_values"]["additionalProperties"])
        self.assertEqual(
            {
                "hook_pressure", "emotional_intensity", "conceptual_novelty",
                "information_density", "visual_complexity",
            },
            set(action["slider_values"]["required"]),
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
        brand = natal_brand_document(logo_id)
        adapter = InstagramStaticAdapter(None, None, None, None)
        structural_signatures = set()
        application_digests = set()
        for template in templates:
            brief = {"offer": candidate["offer"], "cta": candidate["cta"]}
            run = self._recipe_run(template, brand, brief)
            recipe = adapter._recipe(
                candidate=candidate, run=run, element_ids=element_ids, media_id=media_id,
            )
            contract = validate_recipe(
                recipe, project_id=project_id, brief_id=brief_id,
                brand_kit_id=brand_kit_id,
                brief=brief, brand_document=brand,
            )
            metadata = recipe["modifiers"][0]["params"]
            structural_signatures.add(tuple(
                (component["key"], component["tool_id"], component["z_index"], component["optional"])
                for component in metadata["template_snapshot"]["components"]
            ))
            application_digests.add(hashlib.sha256(json.dumps(
                metadata, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest())
            self.assertEqual(recipe, replay_template_application(metadata))
            self.assertEqual(contract.digest, hashlib.sha256(json.dumps(
                contract.value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest())
        self.assertEqual(5, len(structural_signatures))
        self.assertEqual(5, len(application_digests))

    def test_each_slider_changes_only_declared_component_paths(self) -> None:
        strategies = TemplateRegistry(REFERENCES / "templates").load_active()
        studios = StudioTemplateRegistry().load_active(strategies)
        logo_id, media_id = new_uuid7(), new_uuid7()
        brand = natal_brand_document(logo_id)
        brief = {"offer": "First consultation free", "cta": "Book now"}
        candidate = {
            "hook": "One visible customer moment", "supporting_text": "One concrete mechanism.",
            "caption": "A complete caption.", "alt_text": "A complete alt description.",
        }
        semantic_ids = {role: new_uuid7() for role in (
            "background", "primary_subject", "headline_block", "supporting_text_block",
            "offer_block", "cta_block", "brand_mark",
        )}
        for strategy, studio in zip(strategies, studios):
            strategy_identity = {
                "template_id": strategy.template_id, "version": strategy.version,
                "sha256": strategy.digest,
            }
            base = apply_studio_template(
                template=studio, strategy_template=strategy_identity,
                slider_values=strategy.defaults, candidate=candidate, brief=brief,
                brand_document=brand, media_asset_id=media_id,
                semantic_instance_ids=semantic_ids,
            )
            metadata = base["modifiers"][0]["params"]
            base_by_id = {item["instance_id"]: item for item in base["frames"]}
            for slider in strategy.defaults:
                low, high = strategy.envelopes[slider]
                value = strategy.defaults[slider]
                adjusted_value = value + 10 if value + 10 <= high else value - 10
                self.assertGreaterEqual(adjusted_value, low)
                adjusted = {**dict(strategy.defaults), slider: adjusted_value}
                tuned = apply_studio_template(
                    template=studio, strategy_template=strategy_identity,
                    slider_values=adjusted, candidate=candidate, brief=brief,
                    brand_document=brand, media_asset_id=media_id,
                    semantic_instance_ids=semantic_ids,
                    reserved_component_instances=metadata["component_instances"],
                    reserved_modifier_instance_id=metadata["modifier_instance_id"],
                )
                tuned_by_id = {item["instance_id"]: item for item in tuned["frames"]}
                allowed_keys = {
                    rule["component_key"] for rule in studio.document["tuning_rules"]
                    if rule["slider"] == slider
                }
                allowed_ids = {metadata["component_instances"][key] for key in allowed_keys}
                changed_ids = {
                    instance_id for instance_id in set(base_by_id) | set(tuned_by_id)
                    if base_by_id.get(instance_id) != tuned_by_id.get(instance_id)
                }
                self.assertTrue(changed_ids, f"{strategy.template_id}.{slider}")
                self.assertTrue(changed_ids <= allowed_ids, f"{strategy.template_id}.{slider}")
                self.assertEqual(tuned, replay_template_application(tuned["modifiers"][0]["params"]))
                validate_recipe(
                    tuned, project_id=new_uuid7(), brief_id=new_uuid7(), brand_kit_id=new_uuid7(),
                    brief=brief, brand_document=brand,
                )
                self.assertEqual(metadata["bindings"], tuned["modifiers"][0]["params"]["bindings"])

    def test_template_replay_rejects_protected_copy_changes(self) -> None:
        strategy = TemplateRegistry(REFERENCES / "templates").load_active()[0]
        studio = StudioTemplateRegistry().get(strategy.template_id)
        logo_id, media_id = new_uuid7(), new_uuid7()
        brief = {"offer": "First consultation free", "cta": "Book now"}
        recipe = apply_studio_template(
            template=studio,
            strategy_template={"template_id": strategy.template_id, "version": 2, "sha256": strategy.digest},
            slider_values=strategy.defaults,
            candidate={
                "hook": "A concrete moment", "supporting_text": "A concrete mechanism.",
                "caption": "Caption", "alt_text": "Alt text",
            },
            brief=brief, brand_document=natal_brand_document(logo_id), media_asset_id=media_id,
            semantic_instance_ids={role: new_uuid7() for role in (
                "background", "primary_subject", "headline_block", "supporting_text_block",
                "offer_block", "cta_block", "brand_mark",
            )},
        )
        tampered = copy.deepcopy(recipe)
        next(item for item in tampered["frames"] if item["tool_id"] == "studio.frame.offer.v1")["params"]["text"] = "Changed"
        with self.assertRaisesRegex(ValueError, "exact Product Brief|differs from its protected template"):
            validate_recipe(
                tampered, project_id=new_uuid7(), brief_id=new_uuid7(), brand_kit_id=new_uuid7(),
                brief=brief, brand_document=natal_brand_document(logo_id),
            )

    def test_improved_template_application_carries_parent_recipe_lineage(self) -> None:
        strategy = TemplateRegistry(REFERENCES / "templates").load_active()[0]
        studio = StudioTemplateRegistry().get(strategy.template_id)
        logo_id, media_id, parent_recipe_id = new_uuid7(), new_uuid7(), new_uuid7()
        parent_digest = "a" * 64
        brief = {"offer": "First consultation free", "cta": "Book now"}
        recipe = apply_studio_template(
            template=studio,
            strategy_template={"template_id": strategy.template_id, "version": 2, "sha256": strategy.digest},
            slider_values=strategy.defaults,
            candidate={
                "hook": "A concrete moment", "supporting_text": "A concrete mechanism.",
                "caption": "Caption", "alt_text": "Alt text",
            }, brief=brief, brand_document=natal_brand_document(logo_id), media_asset_id=media_id,
            semantic_instance_ids={role: new_uuid7() for role in (
                "background", "primary_subject", "headline_block", "supporting_text_block",
                "offer_block", "cta_block", "brand_mark",
            )}, parent_recipe_id=parent_recipe_id, base_recipe_sha256=parent_digest,
        )
        metadata = recipe["modifiers"][0]["params"]
        self.assertEqual(parent_recipe_id, recipe["parent_recipe_id"])
        self.assertEqual(parent_recipe_id, metadata["parent_recipe_id"])
        self.assertEqual(parent_digest, metadata["base_recipe_sha256"])
        self.assertEqual(recipe, replay_template_application(metadata))


if __name__ == "__main__":
    unittest.main()
