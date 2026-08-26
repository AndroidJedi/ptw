from __future__ import annotations

import unittest

from validation_pipeline.provider import StructuredBridge


class FakeRetryBridge(StructuredBridge):
    def __init__(self) -> None:
        super().__init__("https://bridge.invalid/internal/llm/structured", "token", "model")
        self.posted_keys: list[str] = []

    def _request(self, url, payload, *, timeout=30):
        if payload is not None:
            self.posted_keys.append(payload["idempotency_key"])
            return {"request_id": len(self.posted_keys), "status": "queued"}
        request_id = int(url.rsplit("/", 1)[1])
        if request_id == 1:
            return {"status": "failed", "error": "invalid structured response"}
        return {
            "status": "completed",
            "result": {
                "response": {"candidate": "valid"},
                "invocation": {"provider": "fake"},
            },
        }


class StructuredBridgeTests(unittest.TestCase):
    def test_fresh_json_retry_uses_stable_distinct_attempt_keys(self) -> None:
        bridge = FakeRetryBridge()
        value = bridge.generate_content_candidate(
            system_prompt="Generate one candidate.",
            input_payload={"task": "test"},
            output_schema={"type": "object"},
            idempotency_key="candidate-uuid:content_candidate_generation",
        )

        self.assertEqual({"candidate": "valid"}, value["response"])
        self.assertEqual([
            "candidate-uuid:content_candidate_generation:attempt:1",
            "candidate-uuid:content_candidate_generation:attempt:2",
        ], bridge.posted_keys)
        self.assertEqual([1], value["invocation"]["prior_failed_request_ids"])
        self.assertEqual(2, value["invocation"]["bridge_attempt"])

    def test_graphic_mode_is_always_one_attempt_key(self) -> None:
        class CaptureBridge(StructuredBridge):
            def __init__(self):
                super().__init__("https://bridge.invalid/internal/llm/structured", "token", "model")
                self.key = ""

            def _request(self, url, payload, *, timeout=30):
                if payload is not None:
                    self.key = payload["idempotency_key"]
                    return {"request_id": 7}
                return {
                    "status": "completed",
                    "result": {
                        "response": {"generated": True},
                        "invocation": {},
                        "image": {
                            "digest": "a" * 64,
                            "output_digest": "a" * 64,
                            "mime_type": "image/png",
                            "width": 1024,
                            "height": 1024,
                            "asset_url": "/internal/llm/structured/7/asset",
                            "generation_policy": {
                                "non_human_graphics_only": True,
                                "synthetic_people": "prohibited",
                                "embedded_text": "prohibited",
                                "embedded_logos": "prohibited",
                                "watermarks": "prohibited",
                            },
                        },
                    },
                }

            def _download_graphic(self, job_id, image):
                return {"bytes": b"png", "bytes_sha256": image["digest"]}

        bridge = CaptureBridge()
        bridge.generate_non_human_graphic(
            system_prompt="Generate one reviewed non-human graphic.",
            input_payload={"task": "test"},
            output_schema={"type": "object"},
            idempotency_key="graphic-action-uuid",
        )
        self.assertEqual("graphic-action-uuid:attempt:1", bridge.key)


if __name__ == "__main__":
    unittest.main()
