from __future__ import annotations

import unittest
from uuid import uuid4

from marketing_positioning.provider import BridgeProvider, POSITIONING_DOCUMENT_SCHEMA, POSITIONING_MODES
from marketing_positioning.service import validate_create_input, validate_revision_input


class ProviderContractTests(unittest.TestCase):
    def test_const_schema_fields_declare_their_json_type(self) -> None:
        self.assertEqual(
            {"type": "integer", "const": 1},
            POSITIONING_DOCUMENT_SCHEMA["properties"]["schema_version"],
        )

    def test_bridge_allows_only_positioning_and_retained_landing_mode(self) -> None:
        provider = BridgeProvider("https://bridge.example/internal/structured", "token", "model")
        provider._request = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "marketing_positioning_modes": list(POSITIONING_MODES),
            "landing_modes": ["natal_landing_revision"],
            "max_request_bytes": 1_000_000,
        }
        capability = provider.capabilities()
        self.assertEqual(set(POSITIONING_MODES), set(capability["marketing_positioning_modes"]))
        with self.assertRaisesRegex(ValueError, "unsupported"):
            provider.generate_structured("branding_direction", "", {}, {})

    def test_bridge_readiness_fails_when_a_required_mode_is_absent(self) -> None:
        provider = BridgeProvider("https://bridge.example/internal/structured", "token", "model")
        provider._request = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "marketing_positioning_modes": [POSITIONING_MODES[0]],
            "landing_modes": ["natal_landing_revision"],
            "max_request_bytes": 1_000_000,
        }
        with self.assertRaisesRegex(RuntimeError, "missing required modes"):
            provider.capabilities()

    def test_market_language_and_revision_inputs_are_strict(self) -> None:
        request = validate_create_input({
            "request_id": str(uuid4()), "raw_idea": "Useful idea", "target_country": "us",
            "research_language": "en", "output_language": "uk",
        })
        self.assertEqual("US", request["target_country"])
        with self.assertRaisesRegex(ValueError, "supported market catalog"):
            validate_create_input({**request, "request_id": str(uuid4()), "target_country": "ZZ"})
        correction = validate_revision_input({
            "request_id": str(uuid4()), "base_revision_id": str(uuid4()),
            "section_id": "landing_copy", "instruction": "Use a clearer headline",
        })
        self.assertEqual("landing_copy", correction["section_id"])
        with self.assertRaisesRegex(ValueError, "invalid"):
            validate_revision_input({**correction, "request_id": str(uuid4()), "section_id": "all"})

if __name__ == "__main__":
    unittest.main()
