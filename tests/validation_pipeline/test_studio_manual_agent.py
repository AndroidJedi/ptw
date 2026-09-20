from __future__ import annotations

import base64
from io import BytesIO
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from validation_pipeline.landing_routes import landing_page_router
from validation_pipeline.studio_manual_agent import (
    StudioManualAgentProviderError,
    apply_manual_agent_edits,
    manual_agent_schema,
    manual_agent_request,
    validate_image_actions,
)
from validation_pipeline.studio_routes import studio_creative_router


def _reference_payload() -> dict[str, str]:
    output = BytesIO()
    Image.new("RGB", (64, 64), "#808080").save(output, format="PNG")
    return {
        "mime_type": "image/png",
        "bytes_base64": base64.b64encode(output.getvalue()).decode(),
    }


class StudioManualAgentContractTests(unittest.TestCase):
    @staticmethod
    def _request() -> dict:
        return {
            "request_id": "11111111-1111-4111-8111-111111111111",
            "base_sha256": "a" * 64,
            "message": "Adjust the draft",
            "history": [], "configuration": {}, "content": {}, "screenshots": [],
        }

    def test_request_normalizes_screenshots_without_persistable_metadata(self) -> None:
        result = manual_agent_request({
            "request_id": "11111111-1111-4111-8111-111111111111",
            "base_sha256": "a" * 64,
            "message": "  Make   the hierarchy calmer.  ",
            "history": [{"role": "assistant", "content": "  Ready.  "}],
            "configuration": {"theme": {"surface_color": "#ffffff"}},
            "content": {"title": "Current title"},
            "screenshots": [_reference_payload()],
        })

        self.assertEqual("Make the hierarchy calmer.", result["message"])
        self.assertEqual([{"role": "assistant", "content": "Ready."}], result["history"])
        self.assertTrue(result["screenshots"][0].startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertNotIn("bytes_base64", result)

    def test_request_rejects_unbounded_or_unknown_input(self) -> None:
        request = self._request()
        with self.assertRaisesRegex(ValueError, "fields are invalid"):
            manual_agent_request({**request, "shell_command": "do not run"})
        with self.assertRaisesRegex(ValueError, "at most four"):
            manual_agent_request({**request, "screenshots": [_reference_payload()] * 5})

    def test_image_actions_are_slot_bounded_and_require_existing_pixels_for_enhancement(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing current image"):
            validate_image_actions([{
                "slot": "hero_visual", "visual_direction": "Refine the current image",
                "enhance_current": True, "reference_index": 0,
            }], slots=["hero_visual"], screenshot_count=0, available_slots=set())
        with self.assertRaisesRegex(ValueError, "enhancement or a screenshot"):
            validate_image_actions([{
                "slot": "hero_visual", "visual_direction": "Use the supplied visual reference",
                "enhance_current": True, "reference_index": 1,
            }], slots=["hero_visual"], screenshot_count=1, available_slots={"hero_visual"})

    def test_surface_without_image_slots_has_a_strict_zero_item_schema(self) -> None:
        schema = manual_agent_schema(
            editable_paths=["content.hero_title"],
            image_slots=[], screenshot_count=0,
        )
        actions = schema["properties"]["image_actions"]
        self.assertEqual(0, actions["maxItems"])
        self.assertEqual(False, actions["items"]["additionalProperties"])
        self.assertEqual({}, actions["items"]["properties"])

    def test_scalar_edits_are_path_and_type_bounded(self) -> None:
        current = {"configuration.logo.enabled": True, "content.hero_title": "Before"}
        result = apply_manual_agent_edits(
            [{"path": "content.hero_title", "value": "After"}],
            current_values=current,
            configuration={"logo": {"enabled": True}},
            content={"hero_title": "Before"},
        )
        self.assertEqual("After", result["content"]["hero_title"])
        with self.assertRaisesRegex(ValueError, "path"):
            apply_manual_agent_edits(
                [{"path": "content.unknown", "value": "After"}],
                current_values=current, configuration={"logo": {"enabled": True}},
                content={"hero_title": "Before"},
            )
        with self.assertRaisesRegex(ValueError, "type"):
            apply_manual_agent_edits(
                [{"path": "configuration.logo.enabled", "value": "false"}],
                current_values=current, configuration={"logo": {"enabled": True}},
                content={"hero_title": "Before"},
            )

    def test_provider_timeout_is_504_for_post_and_landing_agent_routes(self) -> None:
        class Service:
            def manual_agent_edit(self, *_args, **_kwargs):
                raise StudioManualAgentProviderError(timed_out=True)

        app = FastAPI()
        app.include_router(studio_creative_router(Service(), prefix="/studio"))
        app.include_router(landing_page_router(Service(), prefix="/landings"))
        with TestClient(app) as client:
            responses = (
                client.post("/studio/projects/project/creatives/creative/agent", json=self._request()),
                client.post("/landings/projects/project/pages/page/agent", json=self._request()),
            )
        for response in responses:
            self.assertEqual(504, response.status_code, response.text)
            self.assertEqual(
                "Studio Agent timed out before returning a validated edit; the draft was not changed.",
                response.json()["detail"],
            )


if __name__ == "__main__":
    unittest.main()
