from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID

from validation_pipeline.studio import DEFAULT_GUARDS, DEFAULT_SOURCE_REFS
from validation_pipeline.studio_validation import (
    CHECK_FIELDS,
    SCORE_FIELDS,
    StudioCreativeValidationError,
    StudioCreativeValidator,
    studio_creative_validation_output_schema,
    validate_studio_creative_review,
)


PROJECT_ID = "018f07ea-7f20-7000-8000-000000000001"
BRIEF_ID = "018f07ea-7f20-7000-8000-000000000002"
KIT_ID = "018f07ea-7f20-7000-8000-000000000003"
FRAME_IDS = [f"018f07ea-7f20-7000-8000-00000000001{index}" for index in range(4)]
BRIEF = {
    "offer": "First consultation free",
    "cta": "Book consultation",
}


def frame(tool_id: str, instance_id: str, y: float, text: str = "") -> dict:
    return {
        "instance_id": instance_id, "tool_id": tool_id,
        "frame": {"x": .08, "y": y, "width": .84, "height": .12},
        "z_index": FRAME_IDS.index(instance_id),
        "params": {"text": text, "color": "#F4F6FA", "font_size": 32},
        "timeline": None, "source_asset_ids": [],
    }


def recipe() -> dict:
    return {
        "schema_version": 2, "parent_recipe_id": None,
        "placement_tool_id": "studio.placement.instagram.feed_square.v1",
        "duration_seconds": None, "frame_rate": None,
        "frames": [
            frame("studio.frame.headline.v1", FRAME_IDS[0], .08, "A clear question?"),
            frame("studio.frame.body.v1", FRAME_IDS[1], .30, "One useful supporting thought."),
            frame("studio.frame.offer.v1", FRAME_IDS[2], .60, BRIEF["offer"]),
            frame("studio.frame.cta.v1", FRAME_IDS[3], .78, BRIEF["cta"]),
        ],
        "modifiers": [],
        "strategy_ids": ["studio.strategy.one_message.v1"],
        "validation_ids": list(DEFAULT_GUARDS),
        "source_reference_ids": list(DEFAULT_SOURCE_REFS),
        "share": {
            "caption": f"{BRIEF['offer']}. One clear next step.",
            "alt_text": "A clear Natal post with a question and consultation action.",
        },
    }


def review(document: dict, verdict: str = "approve") -> dict:
    return {
        "schema_version": 1, "verdict": verdict,
        "summary": "The complete creative is ready." if verdict == "approve" else "Add visual emphasis.",
        "improvement_comments": [] if verdict == "approve" else ["Add one restrained shape behind the hook."],
        "scores": {key: 8 for key in SCORE_FIELDS},
        "checks": {key: True for key in CHECK_FIELDS},
        "document": document,
    }


class FakeRenderer:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def render(self, **values):
        self.calls.append(values)
        return {
            "bytes": b"\xff\xd8reviewed-jpeg\xff\xd9", "mime_type": "image/jpeg",
            "duration_seconds": None, "embedded_manifest": "{}",
        }


class RevisingBridge:
    def __init__(self, revisions: int) -> None:
        self.revisions = revisions
        self.calls: list[dict] = []

    def validate_studio_creative(self, **values):
        self.calls.append(values)
        current = json.loads(json.dumps(values["input_payload"]["current_recipe"]))
        if len(self.calls) <= self.revisions:
            current["frames"].append({
                "instance_id": None,
                "tool_id": "studio.frame.shape.v1",
                "frame": {"x": .06, "y": .06 + len(self.calls) * .01, "width": .88, "height": .18},
                "z_index": 10 + len(self.calls),
                "params": {"background": "#181C25", "opacity": .8, "radius": 20},
                "timeline": None, "source_asset_ids": [],
            })
            result = review(current, "revise")
        else:
            result = review(current, "approve")
        return {"response": result, "invocation": {"bridge_request_id": len(self.calls)}}


class StudioCreativeValidationTests(unittest.TestCase):
    def test_schema_allows_server_assigned_new_components(self) -> None:
        normalized = {
            **recipe(), "source_asset_ids": [], "project_id": PROJECT_ID,
            "brief_id": BRIEF_ID, "brand_kit_id": KIT_ID,
        }
        schema = studio_creative_validation_output_schema(normalized)
        instance = schema["properties"]["document"]["properties"]["frames"]["items"]
        self.assertIn({"type": "null"}, instance["properties"]["instance_id"]["anyOf"])
        self.assertIn("studio.frame.shape.v1", instance["properties"]["tool_id"]["enum"])

    def test_approval_requires_every_check_and_score_at_least_eight(self) -> None:
        value = review(recipe())
        value["scores"]["composition"] = 7
        with self.assertRaisesRegex(ValueError, "complete rubric"):
            validate_studio_creative_review(
                value, current={**recipe(), "source_asset_ids": []},
                project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=BRIEF,
            )

        value = review(recipe())
        value["scores"]["composition"] = "8"
        with self.assertRaisesRegex(ValueError, "scores must be integers"):
            validate_studio_creative_review(
                value, current={**recipe(), "source_asset_ids": []},
                project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=BRIEF,
            )

    def test_rejected_render_is_recomposed_with_a_new_server_uuid_and_rechecked(self) -> None:
        bridge, renderer = RevisingBridge(1), FakeRenderer()
        with TemporaryDirectory() as directory:
            skill = Path(directory) / "SKILL.md"
            skill.write_text("validator skill", encoding="utf-8")
            validator = StudioCreativeValidator(bridge, renderer, skill_path=skill)
            result = validator.review_and_recreate(
                recipe_id=BRIEF_ID, recipe=recipe(), project_id=PROJECT_ID,
                brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=BRIEF,
                brand_kit={"document": {"colors": ["#0C0E12", "#181C25", "#43BDD3", "#F4F6FA"]}},
                assets={}, context={"workflow": "test"},
            )
        self.assertEqual(2, len(bridge.calls))
        self.assertEqual(2, len(renderer.calls))
        self.assertEqual(1, result.recreation_count)
        added = result.contract.value["frames"][-1]
        self.assertEqual(7, UUID(added["instance_id"]).version)
        self.assertEqual("studio.frame.shape.v1", added["tool_id"])

    def test_validator_stops_after_exactly_three_recreations(self) -> None:
        bridge, renderer = RevisingBridge(99), FakeRenderer()
        with TemporaryDirectory() as directory:
            skill = Path(directory) / "SKILL.md"
            skill.write_text("validator skill", encoding="utf-8")
            validator = StudioCreativeValidator(bridge, renderer, skill_path=skill)
            with self.assertRaises(StudioCreativeValidationError) as failed:
                validator.review_and_recreate(
                    recipe_id=BRIEF_ID, recipe=recipe(), project_id=PROJECT_ID,
                    brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=BRIEF,
                    brand_kit={"document": {"colors": ["#0C0E12", "#181C25", "#43BDD3", "#F4F6FA"]}},
                    assets={}, context={"workflow": "test"},
                )
        self.assertEqual(4, len(bridge.calls))
        self.assertEqual(4, len(renderer.calls))
        self.assertEqual(4, len(failed.exception.attempts))


if __name__ == "__main__":
    unittest.main()
