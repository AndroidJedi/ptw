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
    PHONE_SCREEN_IMAGE_PROMPT_MAX_CHARS, PHONE_SCREEN_IMAGE_SIZE,
    LocalCodexPhoneScreenImageProvider,
    OpenAIPhoneScreenImageProvider, ResultBridgePhoneScreenImageProvider,
    phone_screen_art_prompt,
)
from validation_pipeline.phone_hero_styles import (
    PHONE_HERO_BACKGROUND_DIRECTIVES, PHONE_HERO_STYLE_DIRECTIVES,
    normalize_phone_hero_creative_direction,
)


@unittest.skipUnless(__import__("importlib").util.find_spec("PIL") is not None, "Pillow is required")
class OpenAIPhoneScreenImageProviderTests(unittest.TestCase):
    @staticmethod
    def _png() -> bytes:
        from PIL import Image

        output = BytesIO()
        Image.new("RGB", (64, 128), "#F4F5F2").save(output, format="PNG")
        return output.getvalue()

    @staticmethod
    def _square_png() -> bytes:
        from PIL import Image

        output = BytesIO()
        Image.new("RGB", (1024, 1024), "#F4F5F2").save(output, format="PNG")
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

    def test_result_bridge_provider_generates_and_verifies_private_asset(self) -> None:
        generated = self._square_png()
        digest = hashlib.sha256(generated).hexdigest()
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                seen["payload"] = json.loads(request.content)
                seen["token"] = request.headers.get("x-ptw-bridge-token")
                return httpx.Response(200, json={"request_id": 71, "status": "queued"})
            if request.url.path.endswith("/71/asset"):
                return httpx.Response(200, content=generated, headers={"content-type": "image/png"})
            return httpx.Response(200, json={
                "status": "completed",
                "result": {"response": '{"generated":true}', "image": {
                    "digest": digest, "output_digest": digest, "mime_type": "image/png",
                    "width": 1024, "height": 1024,
                    "provider": "codex_chatgpt_imagegen",
                    "request_id": "provider-request-1",
                }},
            })

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = ResultBridgePhoneScreenImageProvider(
                "http://bridge/internal/llm/structured", "bridge-token", client=client,
            ).generate("Create one text-free glass unicorn on a warm white field.")

        payload = seen["payload"]
        self.assertEqual("content_non_human_graphic_generation", payload["mode"])
        self.assertNotIn("input_images", payload)
        self.assertEqual("bridge-token", seen["token"])
        self.assertEqual(generated, result["bytes"])
        self.assertEqual("result_bridge_image_generation", result["source"]["origin"])
        self.assertEqual("image_generation", result["source"]["operation"])
        self.assertNotIn("bridge_token", result["source"])

    def test_result_bridge_provider_attaches_exact_current_png_for_enhancement(self) -> None:
        generated = self._square_png()
        digest = hashlib.sha256(generated).hexdigest()
        reference = self._square_png()
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                seen["payload"] = json.loads(request.content)
                return httpx.Response(200, json={"request_id": 72})
            if request.url.path.endswith("/72/asset"):
                return httpx.Response(200, content=generated)
            return httpx.Response(200, json={
                "status": "completed", "result": {"image": {
                    "digest": digest, "output_digest": digest, "mime_type": "image/png",
                    "width": 1024, "height": 1024,
                }},
            })

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = ResultBridgePhoneScreenImageProvider(
                "http://bridge/internal/llm/structured", "bridge-token", client=client,
            ).generate(
                "Enhance the supplied unicorn while preserving its composition and palette.",
                reference_image=reference,
            )

        attached = seen["payload"]["input_images"][0]
        self.assertEqual(reference, base64.b64decode(attached["bytes_base64"]))
        self.assertEqual(hashlib.sha256(reference).hexdigest(), attached["digest"])
        self.assertEqual("image_edit", result["source"]["operation"])
        self.assertEqual(attached["digest"], result["source"]["reference_image_sha256"])

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
        self.assertIn("direct, first-person live camera view", prompt)
        self.assertIn("non-textual computer-vision treatment is allowed", prompt)
        self.assertIn("no readable text", prompt)
        with self.assertRaisesRegex(ValueError, "8-600"):
            phone_screen_art_prompt("short")

    def test_full_bounded_direction_and_lessons_fit_the_provider_prompt_contract(self) -> None:
        prompt = phone_screen_art_prompt(
            "x" * 600, enhance_current=True, skill_context="y" * 6000,
            creative_direction={
                "schema": "ptw.studio.phone-hero-direction.v1",
                "style": "ultra_realistic_lifestyle", "background": "scene",
            },
        )
        self.assertGreater(len(prompt), 4000)
        self.assertLessEqual(len(prompt), PHONE_SCREEN_IMAGE_PROMPT_MAX_CHARS)

        with httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={
            "data": [{"b64_json": base64.b64encode(self._png()).decode()}],
        }))) as client:
            result = OpenAIPhoneScreenImageProvider("test-key", client=client).generate(prompt)
        self.assertEqual("image_generation", result["source"]["operation"])

    def test_every_style_and_background_is_bounded_and_expands_into_the_prompt(self) -> None:
        for style, style_directive in PHONE_HERO_STYLE_DIRECTIVES.items():
            for background, background_directive in PHONE_HERO_BACKGROUND_DIRECTIVES.items():
                direction = normalize_phone_hero_creative_direction({
                    "schema": "ptw.studio.phone-hero-direction.v1",
                    "style": style, "background": background,
                })
                prompt = phone_screen_art_prompt(
                    "One clear subject for the approved product.",
                    creative_direction=direction,
                )
                self.assertIn(style_directive, prompt)
                self.assertIn(background_directive, prompt)
                self.assertIn("no readable text", prompt)
                self.assertIn("the server adds the Natal identity", prompt)
        with self.assertRaisesRegex(ValueError, "style"):
            normalize_phone_hero_creative_direction({
                "schema": "ptw.studio.phone-hero-direction.v1",
                "style": "unbounded", "background": "scene",
            })
        with self.assertRaisesRegex(ValueError, "background"):
            normalize_phone_hero_creative_direction({
                "schema": "ptw.studio.phone-hero-direction.v1",
                "style": "cinematic", "background": "transparent",
            })
        with self.assertRaisesRegex(ValueError, "schema"):
            normalize_phone_hero_creative_direction({
                "schema": "ptw.studio.phone-hero-direction.v2",
                "style": "cinematic", "background": "scene",
            })
