from __future__ import annotations

import unittest
from uuid import uuid4

from validation_pipeline.provider import StructuredBridge, VALIDATION_MODES
from validation_pipeline.service import validate_create_input, validate_revision_input


class ProviderAndInputTests(unittest.TestCase):
    def test_bridge_requires_exact_three_validation_modes(self) -> None:
        provider = StructuredBridge("https://bridge.example/internal/structured", "token", "model")
        provider._request = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "validation_modes": list(VALIDATION_MODES), "max_request_bytes": 1_000_000,
        }
        self.assertEqual(set(VALIDATION_MODES), set(provider.capabilities()["validation_modes"]))
        with self.assertRaisesRegex(ValueError, "unsupported"):
            provider.generate(
                mode="marketing_positioning_document", system_prompt="", input_payload={},
                output_schema={}, prompt_version="retired",
            )

    def test_bridge_fails_when_any_mode_is_absent(self) -> None:
        provider = StructuredBridge("https://bridge.example/internal/structured", "token", "model")
        provider._request = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "validation_modes": ["product_brief"], "max_request_bytes": 1_000_000,
        }
        with self.assertRaisesRegex(RuntimeError, "do not match"):
            provider.capabilities()

    def test_bridge_rejects_extra_or_duplicate_advertised_modes(self) -> None:
        provider = StructuredBridge("https://bridge.example/internal/structured", "token", "model")
        for modes in (
            [*VALIDATION_MODES, "marketing_positioning_document"],
            [*VALIDATION_MODES, "product_brief"],
        ):
            provider._request = lambda *_args, values=modes, **_kwargs: {  # type: ignore[method-assign]
                "validation_modes": values, "max_request_bytes": 1_000_000,
            }
            with self.subTest(modes=modes), self.assertRaisesRegex(RuntimeError, "do not match"):
                provider.capabilities()

    def test_stage_one_inputs_are_raw_idea_only_and_corrections_are_bounded(self) -> None:
        request_id = str(uuid4())
        self.assertEqual(
            {"request_id": request_id, "raw_idea": "One idea"},
            validate_create_input({"request_id": request_id, "raw_idea": " One idea "}),
        )
        with self.assertRaisesRegex(ValueError, "fields"):
            validate_create_input({"request_id": request_id, "raw_idea": "idea", "country": "UA"})
        self.assertEqual(
            "Clarify the audience",
            validate_revision_input({
                "request_id": str(uuid4()), "instruction": "Clarify the audience"
            })["instruction"],
        )


if __name__ == "__main__":
    unittest.main()
