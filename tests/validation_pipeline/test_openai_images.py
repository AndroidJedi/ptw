from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import httpx

from validation_pipeline.openai_images import (
    OPENAI_IMAGE_EDITS_ENDPOINT, OPENAI_IMAGES_ENDPOINT, PHONE_SCREEN_IMAGE_MODEL,
    PHONE_SCREEN_IMAGE_SIZE, LocalCodexPhoneScreenImageProvider,
    OpenAIPhoneScreenImageProvider,
    phone_screen_art_prompt,
)


@unittest.skipUnless(__import__("importlib").util.find_spec("PIL") is not None, "Pillow is required")
class OpenAIPhoneScreenImageProviderTests(unittest.TestCase):
    @staticmethod
    def _png() -> bytes:
        from PIL import Image

        output = BytesIO()
        Image.new("RGB", (64, 128), "#F4F5F2").save(output, format="PNG")
        return output.getvalue()

    def test_generates_validated_png_with_non_secret_text_free_provenance(self) -> None:
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["payload"] = json.loads(request.content)
            return httpx.Response(200, json={
                "data": [{"b64_json": base64.b64encode(self._png()).decode()}],
            }, headers={"x-request-id": "request_123"})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = OpenAIPhoneScreenImageProvider("test-key", client=client).generate(
                "Text-free abstract editorial composition with soft mineral forms.",
            )

        self.assertEqual(OPENAI_IMAGES_ENDPOINT, seen["url"])
        self.assertEqual(PHONE_SCREEN_IMAGE_MODEL, seen["payload"]["model"])
        self.assertEqual("1024x1024", PHONE_SCREEN_IMAGE_SIZE)
        self.assertEqual(PHONE_SCREEN_IMAGE_SIZE, seen["payload"]["size"])
        self.assertIn("no readable text", seen["payload"]["prompt"])
        self.assertEqual("openai_image_api", result["source"]["origin"])
        self.assertEqual("image_generation", result["source"]["operation"])
        self.assertEqual("prohibited_by_prompt", result["source"]["text_in_screen"])
        self.assertRegex(result["source"]["prompt_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual("request_123", result["source"]["request_id"])
        self.assertNotIn("api_key", result["source"])
        self.assertEqual((64, 128), (result["width"], result["height"]))

    def test_edits_with_the_current_png_as_a_high_fidelity_image_input(self) -> None:
        seen: dict[str, object] = {}
        reference = self._png()

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["content_type"] = request.headers["content-type"]
            seen["body"] = request.content
            return httpx.Response(200, json={
                "data": [{"b64_json": base64.b64encode(self._png()).decode()}],
            })

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = OpenAIPhoneScreenImageProvider("test-key", client=client).generate(
                "Enhance this text-free editorial hero while preserving its composition.",
                reference_image=reference,
            )

        self.assertEqual(OPENAI_IMAGE_EDITS_ENDPOINT, seen["url"])
        self.assertIn("multipart/form-data", seen["content_type"])
        self.assertIn(b'name="image"', seen["body"])
        self.assertIn(b'filename="current-phone-hero.png"', seen["body"])
        self.assertIn(reference, seen["body"])
        self.assertEqual("image_edit", result["source"]["operation"])
        self.assertEqual(
            hashlib.sha256(reference).hexdigest(),
            result["source"]["reference_image_sha256"],
        )

    def test_authenticated_codex_provider_uses_builtin_tool_and_copies_png(self) -> None:
        seen: dict[str, object] = {}
        with tempfile.TemporaryDirectory() as temporary:
            generated_root = Path(temporary) / "generated_images"
            generated_path = generated_root / "run-123" / "asset.png"

            def executor(command, **kwargs):
                seen["command"] = command
                seen["prompt"] = kwargs["input"]
                generated_path.parent.mkdir(parents=True)
                generated_path.write_bytes(self._png())
                output_path = Path(command[command.index("--output-last-message") + 1])
                output_path.write_text(str(generated_path), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            result = LocalCodexPhoneScreenImageProvider(
                "codex-test", executor=executor, generated_root=generated_root,
            ).generate(
                "Text-free abstract editorial composition with soft mineral forms.",
            )

            self.assertFalse(generated_path.exists())

        self.assertIn("--ephemeral", seen["command"])
        self.assertIn("read-only", seen["command"])
        self.assertIn("built-in image generation tool exactly once", seen["prompt"])
        self.assertEqual("codex_builtin_image_generation", result["source"]["origin"])
        self.assertEqual("image_generation", result["source"]["operation"])
        self.assertEqual("authenticated_codex_cli", result["source"]["transport"])
        self.assertNotIn("image_path", result["source"])
        self.assertEqual((64, 128), (result["width"], result["height"]))

    def test_authenticated_codex_provider_supplies_current_png_to_the_image_tool(self) -> None:
        seen: dict[str, object] = {}
        reference = self._png()
        with tempfile.TemporaryDirectory() as temporary:
            generated_root = Path(temporary) / "generated_images"
            generated_path = generated_root / "run-edit" / "asset.png"

            def executor(command, **kwargs):
                workdir = Path(command[command.index("-C") + 1])
                reference_path = workdir / "current-phone-hero.png"
                seen["reference_exists"] = reference_path.is_file()
                seen["reference_bytes"] = reference_path.read_bytes()
                seen["prompt"] = kwargs["input"]
                generated_path.parent.mkdir(parents=True)
                generated_path.write_bytes(self._png())
                output_path = Path(command[command.index("--output-last-message") + 1])
                output_path.write_text(str(generated_path), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            result = LocalCodexPhoneScreenImageProvider(
                "codex-test", executor=executor, generated_root=generated_root,
            ).generate(
                "Enhance this text-free editorial hero while preserving its composition.",
                reference_image=reference,
            )

        self.assertTrue(seen["reference_exists"])
        self.assertEqual(reference, seen["reference_bytes"])
        self.assertIn("CURRENT_HERO_IMAGE=", seen["prompt"])
        self.assertIn("sole referenced input image", seen["prompt"])
        self.assertEqual("image_edit", result["source"]["operation"])

    def test_authenticated_codex_provider_rejects_output_outside_generated_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generated_root = root / "generated_images"
            outside = root / "outside.png"
            outside.write_bytes(self._png())

            def executor(command, **_kwargs):
                output_path = Path(command[command.index("--output-last-message") + 1])
                output_path.write_text(str(outside), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            provider = LocalCodexPhoneScreenImageProvider(
                "codex-test", executor=executor, generated_root=generated_root,
            )
            with self.assertRaisesRegex(RuntimeError, "outside"):
                provider.generate(
                    "Text-free abstract editorial composition with soft mineral forms.",
                )
            self.assertTrue(outside.exists())

    def test_rejects_a_non_png_image_response(self) -> None:
        with httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={
            "data": [{"b64_json": base64.b64encode(b"not a PNG").decode()}],
        }))) as client:
            with self.assertRaises(ValueError):
                OpenAIPhoneScreenImageProvider("test-key", client=client).generate(
                    "Text-free abstract editorial composition with soft mineral forms.",
                )

    def test_owner_direction_expands_into_the_fixed_phone_art_contract(self) -> None:
        prompt = phone_screen_art_prompt(
            "Translucent glass steps in soft blue light with one lime accent.",
        )
        self.assertIn("Translucent glass steps", prompt)
        self.assertIn("the server adds the Natal identity", prompt)
        self.assertIn("lower area calm enough to fade into white", prompt)
        with self.assertRaisesRegex(ValueError, "8-600"):
            phone_screen_art_prompt("short")
