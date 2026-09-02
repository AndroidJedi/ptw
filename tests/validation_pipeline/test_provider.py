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
                "json_modes": ["product_brief", "product_brief_revision"],
                "media_modes": [], "max_request_bytes": 1000,
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

    def test_capabilities_are_brief_only(self) -> None:
        value = FakeBridge().capabilities()
        self.assertEqual(["product_brief", "product_brief_revision"], value["json_modes"])
        self.assertEqual([], value["media_modes"])

    def test_other_modes_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported Product Brief"):
            FakeBridge().generate(
                mode="content_candidate_generation", system_prompt="x",
                input_payload={}, output_schema={}, idempotency_key="x",
                prompt_version="x",
            )


if __name__ == "__main__":
    unittest.main()
