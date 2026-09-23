from copy import deepcopy
import unittest

from validation_pipeline.image_generation_policy import (
    IMAGE_POLICY_VERSION, build_image_context, compile_image_prompt, image_provenance,
    instruction_context, resolve_instruction,
)
from validation_pipeline.metric_hypotheses import generated_metrics, reconcile_metrics


class DomainImagePolicyTests(unittest.TestCase):
    def context(self, **overrides):
        direction = "Рука гостя зі смартфоном сканує QR-картку в затишному готельному номері"
        args = dict(direction=direction, instruction=instruction_context(direction, origin="owner"),
                    brief={"brief_id": "hotel-brief", "document": {"product": "Hotel service chatbot", "target_audience": "Hotel operators"}},
                    settings={"style": "ultra_realistic_lifestyle", "background": "isolated_key_element"},
                    destination={"mode": "image", "surface": "post", "slot": "phone_screen"},
                    operation="generate_new", base_sha256="a" * 64)
        return build_image_context(**(args | overrides))

    def test_hotel_request_survives_presets_and_carries_approved_domain(self):
        context = self.context()
        prompt = compile_image_prompt(context)
        self.assertIn(context["instruction"]["owner_instruction"], prompt)
        self.assertIn("Hotel service chatbot", prompt)
        self.assertIn("Hotel operators", prompt)
        self.assertIn("explicit scene request overrides isolation", prompt)
        for obsolete in ("do not show people", "no people", "no devices", "direct, first-person live camera view", "Non-negotiable output constraint"):
            self.assertNotIn(obsolete, prompt)
        self.assertIn("standalone artwork", prompt)

    def test_origin_and_original_agent_message_survive_regeneration(self):
        suggestion = "A card beside a smartphone"
        context = self.context(direction=suggestion, instruction=instruction_context(suggestion, origin="generated"))
        old = image_provenance(context) | {"visual_direction": suggestion}
        self.assertEqual("generated", resolve_instruction(suggestion, previous=old)["origin"])
        self.assertEqual("owner", resolve_instruction("A guest using a phone", previous=old)["origin"])
        self.assertEqual("legacy_unknown", resolve_instruction(suggestion, previous={"visual_direction": suggestion})["origin"])
        agent = resolve_instruction(suggestion, requested={"origin": "agent", "owner_instruction": "Show a guest ordering laundry. Add the label SPA."})
        self.assertIn("label SPA", agent["owner_instruction"])
        self.assertEqual(suggestion, agent["subject_suggestion"])
        with self.assertRaises(ValueError):
            resolve_instruction(suggestion, requested={"origin": "agent"})
        with self.assertRaises(ValueError):
            resolve_instruction(suggestion, requested=[])

    def test_changed_settings_override_reference_without_resetting_others(self):
        old = self.context()
        settings = {**old["settings"], "style": "cinematic"}
        edit = self.context(settings=settings, operation="enhance_current", previous=image_provenance(old))
        self.assertEqual({"style": "cinematic"}, edit["changed_settings"])
        self.assertNotIn("background", edit["changed_settings"])
        self.assertIn("preserve unspecified reference characteristics", compile_image_prompt(edit))

    def test_uploaded_reference_explicit_changes_and_request_validation(self):
        from validation_pipeline.image_reference import generation_request
        context = self.context(operation="uploaded_reference", changed_settings=["style"])
        self.assertEqual({"style": "ultra_realistic_lifestyle"}, context["changed_settings"])
        request = generation_request({"base_sha256": "a" * 64, "visual_direction": "A guest scans the QR card",
                                      "changed_image_settings": ["style"], "instruction_context": {"origin": "owner"}})
        self.assertEqual(["style"], request["changed_image_settings"])
        with self.assertRaisesRegex(ValueError, "Changed image settings"):
            generation_request({**request, "changed_image_settings": ["unsafe"]})
        landing = self.context(destination={"surface": "landing", "mode": "phone", "slot": "hero_visual"})
        self.assertIn("backdrop behind", compile_image_prompt(landing))
        self.assertNotIn("app controls", compile_image_prompt(landing))

    def test_modes_and_landing_crop_have_separate_guidance(self):
        phone = self.context(destination={"mode": "phone", "slot": "phone_screen"})
        image = self.context(destination={"mode": "image", "slot": "visual_break_visual"})
        self.assertIn("reserved areas", compile_image_prompt(phone))
        self.assertIn("central horizontal band", compile_image_prompt(image))
        self.assertNotIn("reserved areas", compile_image_prompt(image))
        self.assertNotEqual(image_provenance(phone)["image_context_sha256"], image_provenance(image)["image_context_sha256"])

    def test_project_context_is_independent_and_large_requests_are_not_truncated(self):
        one = self.context()
        two = self.context(brief={"brief_id": "other", "document": {"product": "Laundry pickup"}})
        self.assertNotIn("Hotel service chatbot", compile_image_prompt(two))
        self.assertEqual("hotel-brief", one["brief"]["brief_id"])
        self.assertEqual(IMAGE_POLICY_VERSION, image_provenance(two)["generation_policy_version"])
        with self.assertRaisesRegex(ValueError, "budget"):
            self.context(brief={"document": {"product": "x" * 24000}})


class MetricHypothesisTests(unittest.TestCase):
    def test_numeric_hypotheses_and_exact_brief_support(self):
        stats = [{"value": "1", "label": "Free month"}, {"value": "−25%", "label": "Reception calls"}, {"value": "2×", "label": "Faster handling"}]
        basis = [{"origin": "brief_supported", "evidence": "1 free month"}, *[{"origin": "ai_hypothesis", "evidence": ""}] * 2]
        provenance = generated_metrics(stats, basis, {"offer": "1 free month"})
        self.assertEqual(["brief_supported", "ai_hypothesis", "ai_hypothesis"], [p["origin"] for p in provenance])
        self.assertTrue(all(p["validation_status"] == "unvalidated" for p in provenance))
        changed = deepcopy(stats)
        changed[0]["value"] = "35%"
        with self.assertRaisesRegex(ValueError, "supporting Brief excerpt"):
            generated_metrics(changed, basis, {"offer": "1 free month"})
        changed[0]["value"] = "FAST"
        with self.assertRaisesRegex(ValueError, "numeral"):
            generated_metrics(changed, basis, {})

    def test_owner_edit_is_allowed_and_provenance_binds_exact_copy(self):
        stats = [{"value": "+35%", "label": "More orders"}] * 3
        provenance = generated_metrics(stats, [{"origin": "ai_hypothesis", "evidence": ""}] * 3, {})
        changed = deepcopy(stats)
        changed[0] = {"value": "Convenient", "label": "Owner wording"}
        next_sources = reconcile_metrics(changed, provenance)
        self.assertEqual("owner_supplied", next_sources[0]["origin"])
        self.assertEqual("ai_hypothesis", next_sources[1]["origin"])
        with self.assertRaisesRegex(ValueError, "match"):
            reconcile_metrics(changed, provenance, supplied=provenance)
        ai_edit = reconcile_metrics(stats, [], owner_instruction="Add plausible numeric hypotheses")
        self.assertTrue(all(p["origin"] == "ai_hypothesis" for p in ai_edit))


if __name__ == "__main__":
    unittest.main()
