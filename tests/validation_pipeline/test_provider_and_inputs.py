from __future__ import annotations

import unittest
import hashlib
from uuid import uuid4
from unittest.mock import patch

from validation_pipeline.provider import STUDIO_MODES, StructuredBridge, VALIDATION_MODES
from validation_pipeline.service import validate_create_input, validate_revision_input


class ProviderAndInputTests(unittest.TestCase):
    def test_bridge_requires_exact_three_validation_modes(self) -> None:
        provider = StructuredBridge("https://bridge.example/internal/structured", "token", "model")
        provider._request = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "validation_modes": list(VALIDATION_MODES), "studio_modes": list(STUDIO_MODES),
            "max_request_bytes": 1_000_000,
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
            "validation_modes": ["product_brief"], "studio_modes": list(STUDIO_MODES),
            "max_request_bytes": 1_000_000,
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
                "validation_modes": values, "studio_modes": list(STUDIO_MODES),
                "max_request_bytes": 1_000_000,
            }
            with self.subTest(modes=modes), self.assertRaisesRegex(RuntimeError, "do not match"):
                provider.capabilities()

    def test_bridge_requires_exact_separate_studio_modes_and_reads_nested_image(self) -> None:
        provider = StructuredBridge("https://bridge.example/internal/llm/structured", "token", "model")
        provider._request = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "validation_modes": list(VALIDATION_MODES), "studio_modes": ["ad_studio_recipe_revision"],
            "max_request_bytes": 1_000_000,
        }
        with self.assertRaisesRegex(RuntimeError, "Studio modes"):
            provider.capabilities()

        states = iter([
            {"request_id": 42, "status": "queued"},
            {"status": "completed", "result": {
                "response": '{"title":"Route","alt_text":"Abstract route"}',
                "invocation": {"resolved_model": "gpt-image-2"},
                "image": {
                    "digest": "a" * 64, "output_digest": "a" * 64, "mime_type": "image/png",
                    "width": 1024, "height": 1024, "provider": "codex_chatgpt_imagegen",
                    "request_id": "request-42", "asset_url": "/internal/llm/structured/42/asset",
                    "generation_policy": {
                        "non_human_graphics_only": True, "synthetic_people": "prohibited",
                        "embedded_text": "prohibited", "embedded_logos": "prohibited",
                        "watermarks": "prohibited",
                    },
                },
            }, "error": None},
        ])
        provider._request = lambda *_args, **_kwargs: next(states)  # type: ignore[method-assign]
        provider._download_studio_asset = lambda job_id, image: {  # type: ignore[method-assign]
            "bytes": b"png", "bytes_sha256": image["digest"]
        }
        result = provider.generate_studio_graphic(
            system_prompt="bounded", input_payload={}, output_schema={},
        )
        self.assertEqual("Route", result["response"]["title"])
        self.assertEqual(b"png", result["image"]["bytes"])
        self.assertEqual(42, result["invocation"]["bridge_request_id"])

    def test_studio_graphic_asset_is_same_origin_authenticated_and_digest_checked(self) -> None:
        provider = StructuredBridge("https://bridge.example/internal/llm/structured", "secret", "model")
        data = b"\x89PNG\r\n\x1a\n" + b"bounded-fixture"
        digest = hashlib.sha256(data).hexdigest()

        class FakeResponse:
            headers = {"Content-Type": "image/png", "ETag": f'"{digest}"'}
            def __enter__(self): return self
            def __exit__(self, *_args): return None
            def read(self, _limit): return data

        image = {
            "digest": digest, "output_digest": digest, "mime_type": "image/png",
            "width": 1024, "height": 1024,
            "asset_url": "/internal/llm/structured/9/asset",
            "generation_policy": {
                "non_human_graphics_only": True, "synthetic_people": "prohibited",
                "embedded_text": "prohibited", "embedded_logos": "prohibited",
                "watermarks": "prohibited",
            },
        }
        with patch("urllib.request.urlopen", return_value=FakeResponse()) as opened:
            value = provider._download_studio_asset(9, image)
        request = opened.call_args.args[0]
        self.assertEqual("https://bridge.example/internal/llm/structured/9/asset", request.full_url)
        self.assertEqual("secret", request.headers["X-ptw-bridge-token"])
        self.assertEqual(digest, value["bytes_sha256"])

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
