"""Semantic coverage for the bounded Studio Manual Agent contract."""

from __future__ import annotations

from copy import deepcopy
import json
import unittest

from validation_pipeline.landing_workspace import landing_catalog
from validation_pipeline.studio_manual_agent import (
    StudioManualAgentProviderError,
    agent_control_contract,
    manual_agent_request_constraints,
    manual_agent_payload,
    studio_manual_agent_provider_error,
    validate_manual_agent_semantics,
)
from validation_pipeline.studio_phone_metrics import (
    DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_CONTENT, phone_metrics_catalog,
)


class StudioAgentControlContractTests(unittest.TestCase):
    def test_every_live_component_has_an_english_semantic_contract(self) -> None:
        surfaces = (
            ("post:phone_metrics", phone_metrics_catalog()),
            ("landing:project_landing", landing_catalog()),
        )
        for surface, catalog in surfaces:
            with self.subTest(surface=surface):
                contract = agent_control_contract(surface, catalog)
                self.assertLessEqual(
                    len(json.dumps(contract, ensure_ascii=False).encode()), 16_000,
                )
                self.assertEqual("ptw.studio.agent-control-contract.v3", contract["schema"])
                self.assertEqual(
                    [item["component_id"] for item in catalog["components"]],
                    [item["component_id"] for item in contract["components"]],
                )
                catalog_paths = {
                    item["component_id"]: item["setting_ids"]
                    for item in catalog["components"]
                }
                for component in contract["components"]:
                    self.assertTrue(component["purpose"])
                    self.assertTrue(component["dependencies"])
                    self.assertIn(component["component_id"], catalog_paths)

    def test_phone_and_art_direction_phrase_mappings_are_explicit(self) -> None:
        contract = agent_control_contract("post:phone_metrics", phone_metrics_catalog())
        mappings = contract["owner_phrase_mappings"]
        self.assertEqual(False, mappings["hide_or_remove_phone_device"]["value"])
        self.assertEqual(
            "configuration.device.enabled",
            mappings["hide_or_remove_phone_device"]["setting_path"],
        )
        self.assertEqual(
            {
                "configuration.device.enabled": True,
                "configuration.visual_mode": "image",
            },
            mappings["show_only_artwork_without_phone_or_interface"]["setting_paths"],
        )
        self.assertEqual(
            "one phone_screen action using the requested picture subject",
            mappings["remove_phone_and_change_visible_picture"]["image_action"],
        )
        self.assertEqual("phone", mappings["bring_phone_back"]["setting_paths"]["configuration.visual_mode"])
        self.assertEqual([
            "Business professional", "Ultra-realistic lifestyle", "Cinematic",
            "Premium editorial", "Contemporary 3D", "Minimal sculptural",
            "Artistic illustration", "Playful balloons", "Tactile handmade",
            "Futuristic tech",
        ], [item["name"] for item in contract["image_style_options"]])
        self.assertEqual(
            {
                "scene": "Scene background",
                "isolated_key_element": "Isolated key element",
            },
            {item["id"]: item["name"] for item in contract["background_treatments"]},
        )

    def test_payload_is_compact_and_uses_catalog_backed_scalar_values(self) -> None:
        catalog = phone_metrics_catalog()
        payload = manual_agent_payload(
            surface="post:phone_metrics", entity_id="creative-id", message="Hide the phone",
            history=[], configuration=DEFAULT_PHONE_CONFIG, content=DEFAULT_PHONE_CONTENT,
            catalog=catalog, screenshot_artifact_values=[], image_slots=[], current_images=[],
        )
        self.assertNotIn("live_catalog", payload)
        self.assertNotIn("current_editor_state", payload)
        self.assertEqual("post:phone_metrics", payload["agent_control_contract"]["surface"])
        self.assertIn("configuration.device.enabled", payload["current_editable_values"])
        self.assertNotIn("configuration.schema", payload["current_editable_values"])
        self.assertEqual(
            "ptw.studio.agent-request-constraints.v1",
            payload["request_constraints"]["schema"],
        )

    def test_compound_ukrainian_request_resolves_to_one_visible_artwork_and_numeric_metrics(self) -> None:
        message = (
            "Прибери 1 логотип також зроби так ніби це на картинці вигляд домашньої "
            "аптечки і програма класифікує наявні медикаменти у програмі спробуй "
            "прибрати телефон на нижніх кнопка також застосує більше цифр для впевненості"
        )
        constraints = manual_agent_request_constraints(
            surface="post:phone_metrics", message=message,
            image_slots=["phone_screen"],
        )
        self.assertEqual({
            "change_visible_artwork", "artwork_without_phone_hardware",
            "keep_one_natal_logo", "numeric_lower_metric_cards",
        }, {item["id"] for item in constraints["required_outcomes"]})

        configuration = deepcopy(DEFAULT_PHONE_CONFIG)
        configuration.update({"visual_mode": "image"})
        configuration["phone_screen"]["logo_enabled"] = False
        content = deepcopy(DEFAULT_PHONE_CONTENT)
        content["stats"] = [
            {"value": "01", "label": "Фото упаковок"},
            {"value": "02", "label": "Класифікація"},
            {"value": "03", "label": "Домашній список"},
        ]
        action = [{
            "slot": "phone_screen",
            "visual_direction": "A text-free open home medicine cabinet with medicines grouped visually by category.",
            "enhance_current": False,
            "reference_index": 0,
        }]
        validate_manual_agent_semantics(
            surface="post:phone_metrics", constraints=constraints,
            configuration=configuration, content=content, image_actions=action,
        )

        hidden = deepcopy(configuration)
        hidden["device"]["enabled"] = False
        with self.assertRaisesRegex(ValueError, "would be invisible"):
            validate_manual_agent_semantics(
                surface="post:phone_metrics", constraints=constraints,
                configuration=hidden, content=content, image_actions=action,
            )
        slogans = deepcopy(content)
        slogans["stats"] = [
            {"value": "ЗА ФОТО", "label": "облік ліків"},
            {"value": "ШВИДКИЙ ОГЛЯД", "label": "домашня аптечка"},
            {"value": "СПИСОК", "label": "що бракує"},
        ]
        with self.assertRaisesRegex(ValueError, "every content.stats value"):
            validate_manual_agent_semantics(
                surface="post:phone_metrics", constraints=constraints,
                configuration=configuration, content=slogans, image_actions=action,
            )

    def test_style_selection_and_explicit_no_generation_do_not_request_pixels(self) -> None:
        for message in (
            "Choose Cinematic image style and a scene background",
            "Прибери телефон, але не генеруй і не змінюй зображення",
        ):
            with self.subTest(message=message):
                constraints = manual_agent_request_constraints(
                    surface="post:phone_metrics", message=message,
                    image_slots=["phone_screen"],
                )
                self.assertNotIn("change_visible_artwork", {
                    item["id"] for item in constraints["required_outcomes"]
                })

    def test_provider_timeout_is_sanitized_and_not_a_state_conflict(self) -> None:
        class Failure(RuntimeError):
            attempts = [{"error_type": "TimeoutExpired", "error_message": "must not escape"}]

        result = studio_manual_agent_provider_error(Failure("/private/path --output-schema secret"))
        self.assertIsInstance(result, StudioManualAgentProviderError)
        self.assertTrue(result.timed_out)
        self.assertIn("draft was not changed", str(result))
        self.assertNotIn("/private/path", str(result))


if __name__ == "__main__":
    unittest.main()
