from __future__ import annotations

from io import BytesIO
import unittest
import urllib.error
from unittest.mock import patch

from validation_pipeline.provider import (
    BRIDGE_CONCURRENT_SLOT_LIMIT, BRIDGE_IDEMPOTENCY_KEY_LIMIT,
    BRIDGE_STRUCTURED_CONTRACT_LIMIT_BYTES, StructuredBridge,
)


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
    def test_client_concurrency_matches_the_single_production_worker(self) -> None:
        self.assertEqual(1, BRIDGE_CONCURRENT_SLOT_LIMIT)

    def test_product_brief_call_uses_one_stable_attempt_key(self) -> None:
        bridge = FakeBridge()
        value = bridge.generate(
            mode="product_brief", system_prompt="Generate one brief.",
            input_payload={"raw_idea": "test"}, output_schema={"type": "object"},
            idempotency_key="brief-uuid:product_brief", prompt_version="brief-v2",
            response_validator=lambda response: response,
        )

        self.assertEqual({"schema_version": 1}, value["response"])
        self.assertRegex(
            bridge.posted["idempotency_key"],
            r"^brief-uuid:product_brief:request:[0-9a-f]{64}:attempt:1$",
        )
        self.assertIn(
            value["invocation"]["request_fingerprint"],
            bridge.posted["idempotency_key"],
        )
        self.assertEqual(1, value["invocation"]["bridge_attempt"])
        self.assertGreater(value["invocation"]["contract_bytes"]["total"], 0)
        self.assertEqual(
            value["invocation"]["contract_bytes"]["total"],
            sum(value["invocation"]["contract_bytes"][key] for key in (
                "system_prompt", "input_payload", "output_schema",
            )),
        )

    def test_oversized_structured_contract_is_rejected_before_submission(self) -> None:
        bridge = FakeBridge()
        with self.assertRaisesRegex(ValueError, "safe byte budget"):
            bridge.generate(
                mode="product_brief", system_prompt="Generate one brief.",
                input_payload={"raw_idea": "x" * BRIDGE_STRUCTURED_CONTRACT_LIMIT_BYTES},
                output_schema={"type": "object"},
                idempotency_key="brief-uuid:product_brief", prompt_version="brief-v2",
                response_validator=lambda response: response,
            )
        self.assertIsNone(bridge.posted)

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
                prompt_version="x", response_validator=lambda response: response,
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
        self.assertRegex(
            bridge.posts[0]["idempotency_key"],
            r"^studio-creative:creative-uuid:request:[0-9a-f]{64}:attempt:1$",
        )
        self.assertEqual(
            bridge.posts[0]["idempotency_key"].removesuffix("attempt:1") + "attempt:2",
            bridge.posts[1]["idempotency_key"],
        )
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
        self.assertRegex(
            bridge.posts[0]["idempotency_key"],
            r"^studio-creative:creative-uuid:request:[0-9a-f]{64}:attempt:1$",
        )

    def test_every_semantic_request_dependency_changes_the_fingerprint(self) -> None:
        base = {
            "mode": "product_brief",
            "system_prompt": "Generate one brief.",
            "input_payload": {"raw_idea": "first"},
            "output_schema": {"type": "object"},
            "idempotency_key": "brief-uuid:product_brief",
            "prompt_version": "brief-v2",
            "response_validator": lambda response: response,
        }
        variants = [
            {},
            {"system_prompt": "Generate one bounded brief."},
            {"input_payload": {"raw_idea": "second"}},
            {"output_schema": {"type": "object", "maxProperties": 1}},
            {"prompt_version": "brief-v3"},
        ]
        keys = []
        for patch in variants:
            bridge = FakeBridge()
            bridge.generate(**{**base, **patch})
            keys.append(bridge.posted["idempotency_key"])
        model_bridge = FakeBridge()
        model_bridge.model = "different-model"
        model_bridge.generate(**base)
        keys.append(model_bridge.posted["idempotency_key"])
        self.assertEqual(len(keys), len(set(keys)))

        ordered = FakeBridge()
        reordered = FakeBridge()
        ordered.generate(**{
            **base, "input_payload": {"first": 1, "second": 2},
        })
        reordered.generate(**{
            **base, "input_payload": {"second": 2, "first": 1},
        })
        self.assertEqual(
            ordered.posted["idempotency_key"], reordered.posted["idempotency_key"],
        )

    def test_long_base_key_is_bounded_without_losing_collision_resistance(self) -> None:
        bridge = FakeBridge()
        bridge.generate(
            mode="product_brief", system_prompt="Generate one brief.",
            input_payload={"raw_idea": "test"}, output_schema={"type": "object"},
            idempotency_key="brief:" + "x" * 400, prompt_version="brief-v2",
            response_validator=lambda response: response,
        )
        self.assertEqual(BRIDGE_IDEMPOTENCY_KEY_LIMIT, len(bridge.posted["idempotency_key"]))
        self.assertRegex(bridge.posted["idempotency_key"], r":request:[0-9a-f]{64}:attempt:1$")
        other = FakeBridge()
        other.generate(
            mode="product_brief", system_prompt="Generate one brief.",
            input_payload={"raw_idea": "test"}, output_schema={"type": "object"},
            idempotency_key="brief:" + "y" * 400, prompt_version="brief-v2",
            response_validator=lambda response: response,
        )
        self.assertNotEqual(
            bridge.posted["idempotency_key"], other.posted["idempotency_key"],
        )

    def test_domain_validator_is_mandatory(self) -> None:
        with self.assertRaisesRegex(ValueError, "domain response validator"):
            FakeBridge().call(
                mode="product_brief", system_prompt="Generate one brief.",
                input_payload={}, output_schema={}, idempotency_key="brief",
                prompt_version="brief-v2", response_validator=None,
            )

    def test_http_failure_never_reflects_provider_body_or_secret(self) -> None:
        error = urllib.error.HTTPError(
            "https://bridge.invalid", 500, "failed", {},
            BytesIO(b"token=should-never-be-reflected private provider output"),
        )
        bridge = StructuredBridge(
            "https://bridge.invalid/internal/llm/structured", "bridge-secret", "model",
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, r"structured bridge HTTP 500") as caught:
                bridge._request(bridge.url, {"safe": True})
        self.assertNotIn("token", str(caught.exception).casefold())
        self.assertNotIn("private provider output", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
