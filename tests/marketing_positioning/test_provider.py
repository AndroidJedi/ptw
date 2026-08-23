from __future__ import annotations

import socket
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from marketing_positioning.provider import (
    BridgeProvider, DataForSEOProvider, POSITIONING_MODES, SafePageFetcher,
)
from marketing_positioning.service import validate_create_input, validate_revision_input


class ProviderContractTests(unittest.TestCase):
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

    def test_safe_page_validation_rejects_non_https_credentials_and_private_dns(self) -> None:
        for url in ("http://example.com", "https://user:secret@example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                SafePageFetcher._validated(url)
        private = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with patch("marketing_positioning.provider.socket.getaddrinfo", return_value=private):
            with self.assertRaisesRegex(ValueError, "non-public"):
                SafePageFetcher._validated("https://example.com")

    def test_market_language_and_revision_inputs_are_strict(self) -> None:
        request = validate_create_input({
            "request_id": str(uuid4()), "raw_idea": "Useful idea", "target_country": "us",
            "research_language": "en", "output_language": "uk",
        })
        self.assertEqual("US", request["target_country"])
        with self.assertRaisesRegex(ValueError, "verified provider catalog"):
            validate_create_input({**request, "request_id": str(uuid4()), "target_country": "ZZ"})
        correction = validate_revision_input({
            "request_id": str(uuid4()), "base_revision_id": str(uuid4()),
            "section_id": "landing_copy", "instruction": "Use a clearer headline",
        })
        self.assertEqual("landing_copy", correction["section_id"])
        with self.assertRaisesRegex(ValueError, "invalid"):
            validate_revision_input({**correction, "request_id": str(uuid4()), "section_id": "all"})

    def test_dataforseo_terminal_failure_does_not_poll_as_pending(self) -> None:
        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {
                    "status_code": 20000,
                    "tasks": [{"status_code": 40501, "status_message": "fixture failure"}],
                }

        fake_httpx = SimpleNamespace(get=lambda *_args, **_kwargs: Response())
        provider = DataForSEOProvider("login", "password")
        with patch.dict(sys.modules, {"httpx": fake_httpx}):
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                provider.fetch("paid-task-fixture")


if __name__ == "__main__":
    unittest.main()
