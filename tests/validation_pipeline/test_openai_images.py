from __future__ import annotations

import base64
from io import BytesIO
import json
import unittest

import httpx

from validation_pipeline.openai_images import (
    OPENAI_IMAGES_ENDPOINT, PHONE_SCREEN_IMAGE_MODEL,
    PHONE_SCREEN_IMAGE_SIZE, OpenAIPhoneScreenImageProvider,
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
        self.assertEqual("prohibited_by_prompt", result["source"]["text_in_screen"])
        self.assertEqual("request_123", result["source"]["request_id"])
        self.assertNotIn("api_key", result["source"])
        self.assertEqual((64, 128), (result["width"], result["height"]))

    def test_rejects_a_non_png_image_response(self) -> None:
        with httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={
            "data": [{"b64_json": base64.b64encode(b"not a PNG").decode()}],
        }))) as client:
            with self.assertRaises(ValueError):
                OpenAIPhoneScreenImageProvider("test-key", client=client).generate(
                    "Text-free abstract editorial composition with soft mineral forms.",
                )
