from __future__ import annotations

import unittest

from validation_pipeline.provider import StructuredBridge


class FakeBridge(StructuredBridge):
    def __init__(self) -> None:
        super().__init__("https://bridge.invalid/internal/llm/structured", "token", "model")
        self.posted = None

    def _request(self, url, payload, *, timeout=30):
        if url.endswith("/capabilities"):
            return {
                "json_modes": [
                    "product_brief", "product_brief_revision",
                    "studio_creative_generation", "studio_edit_learning",
                ],
                "media_modes": ["content_non_human_graphic_generation"],
                "max_request_bytes": 1000,
            }
        if payload is not None:
            self.posted = payload
            return {"request_id": 7}
        return {
            "status": "completed",
            "result": {
                "response": {"schema_version": 1},
                "invocation": {"provider": "fake"},
            },
        }


class CorrectingFakeBridge(StructuredBridge):
    def __init__(self) -> None:
        super().__init__("https://bridge.invalid/internal/llm/structured", "token", "model")
        self.posts = []
        self.active_request_id = 0

    def _request(self, url, payload, *, timeout=30):
        if payload is not None:
            self.posts.append(payload)
            self.active_request_id = len(self.posts)
            return {"request_id": self.active_request_id}
        intensity = 0 if self.active_request_id == 1 else 0.13
        return {
            "status": "completed",
            "result": {
                "response": {"texture_intensity": intensity},
                "invocation": {"provider": "fake"},
            },
        }


class FailedProviderBridge(StructuredBridge):
    def __init__(self) -> None:
        super().__init__("https://bridge.invalid/internal/llm/structured", "token", "model")
        self.posts = []

    def _request(self, url, payload, *, timeout=30):
        if payload is not None:
            self.posts.append(payload)
            return {"request_id": 9}
        return {"status": "failed"}


class StructuredBridgeTests(unittest.TestCase):
    def test_product_brief_call_uses_one_stable_attempt_key(self) -> None:
        bridge = FakeBridge()
        value = bridge.generate(
            mode="product_brief", system_prompt="Generate one brief.",
            input_payload={"raw_idea": "test"}, output_schema={"type": "object"},
            idempotency_key="brief-uuid:product_brief", prompt_version="brief-v2",
        )

        self.assertEqual({"schema_version": 1}, value["response"])
        self.assertEqual(
            "brief-uuid:product_brief:attempt:1",
            bridge.posted["idempotency_key"],
        )
        self.assertEqual(1, value["invocation"]["bridge_attempt"])

    def test_capabilities_match_the_deployed_provider_contract(self) -> None:
        value = FakeBridge().capabilities()
        self.assertEqual([
            "product_brief", "product_brief_revision",
            "studio_creative_generation", "studio_edit_learning",
        ], value["json_modes"])
        self.assertEqual(["content_non_human_graphic_generation"], value["media_modes"])

    def test_other_modes_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported structured bridge"):
            FakeBridge().generate(
                mode="content_candidate_generation", system_prompt="x",
                input_payload={}, output_schema={}, idempotency_key="x",
                prompt_version="x",
            )

    def test_completed_invalid_response_gets_one_fresh_corrective_attempt(self) -> None:
        bridge = CorrectingFakeBridge()

        def validate(response):
            intensity = response["texture_intensity"]
            if not 0.04 <= intensity <= 0.24:
                raise ValueError("texture intensity must be between 0.04 and 0.24")
            return response

        value = bridge.call(
            mode="studio_creative_generation", system_prompt="Compose one creative.",
            input_payload={"template": "phone_metrics"},
            output_schema={"type": "object"},
            idempotency_key="studio-creative:creative-uuid", prompt_version="studio-v2",
            response_validator=validate,
        )

        self.assertEqual({"texture_intensity": 0.13}, value["response"])
        self.assertEqual([
            "studio-creative:creative-uuid:attempt:1",
            "studio-creative:creative-uuid:attempt:2",
        ], [post["idempotency_key"] for post in bridge.posts])
        self.assertNotEqual(
            bridge.posts[0]["system_prompt"], bridge.posts[1]["system_prompt"],
        )
        self.assertIn("between 0.04 and 0.24", bridge.posts[1]["system_prompt"])
        self.assertEqual(2, value["invocation"]["bridge_attempt"])
        self.assertEqual(
            ["rejected", "completed"],
            [item["status"] for item in value["invocation"]["validation_attempts"]],
        )

    def test_provider_failure_does_not_create_a_second_attempt(self) -> None:
        bridge = FailedProviderBridge()

        with self.assertRaisesRegex(RuntimeError, "structured bridge request 9 failed"):
            bridge.call(
                mode="studio_creative_generation", system_prompt="Compose one creative.",
                input_payload={"template": "phone_metrics"},
                output_schema={"type": "object"},
                idempotency_key="studio-creative:creative-uuid", prompt_version="studio-v2",
                response_validator=lambda response: response,
            )

        self.assertEqual(1, len(bridge.posts))
        self.assertEqual(
            "studio-creative:creative-uuid:attempt:1",
            bridge.posts[0]["idempotency_key"],
        )


if __name__ == "__main__":
    unittest.main()
