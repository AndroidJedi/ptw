"""Small, server-side boundary for text-free Studio phone hero artwork.

The browser never receives the API credential.  Callers persist only the
returned image bytes and non-secret provenance, never the response body or a
credential.
"""

from __future__ import annotations

import base64
from typing import Any, Mapping

import httpx

from .studio import inspect_media


OPENAI_IMAGES_ENDPOINT = "https://api.openai.com/v1/images/generations"
PHONE_SCREEN_IMAGE_MODEL = "gpt-image-2"
# Generated pixels supply the hero artwork, not the complete phone UI. A square
# source gives the compositor a stable focal crop inside its fixed app shell.
PHONE_SCREEN_IMAGE_SIZE = "1024x1024"
PHONE_SCREEN_IMAGE_QUALITY = "medium"


class OpenAIPhoneScreenImageProvider:
    """Generate one validated PNG phone hero artwork through the server-side API."""

    def __init__(self, api_key: str, *, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for generated phone-screen artwork")
        self.api_key = api_key
        self.client = client

    def generate(self, prompt: str) -> dict[str, Any]:
        normalized_prompt = " ".join(str(prompt).split())
        if not 24 <= len(normalized_prompt) <= 4_000:
            raise ValueError("phone-screen image prompt must contain 24-4000 characters")
        payload = {
            "model": PHONE_SCREEN_IMAGE_MODEL,
            "prompt": (
                f"{normalized_prompt}\n\nNon-negotiable output constraint: no readable text, "
                "letters, numbers, logos, brand marks, UI, buttons, metrics, charts, or labels."
            ),
            "size": PHONE_SCREEN_IMAGE_SIZE,
            "quality": PHONE_SCREEN_IMAGE_QUALITY,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.client is None:
            with httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
                response = client.post(OPENAI_IMAGES_ENDPOINT, headers=headers, json=payload)
        else:
            response = self.client.post(OPENAI_IMAGES_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        try:
            body = response.json()
            encoded = body["data"][0]["b64_json"]
            data = base64.b64decode(encoded, validate=True)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RuntimeError("OpenAI image response did not contain PNG image bytes") from error
        inspected = inspect_media(data, "image/png")
        return {
            "bytes": data,
            "mime_type": "image/png",
            "source": {
                "origin": "openai_image_api",
                "provider": "openai",
                "model": PHONE_SCREEN_IMAGE_MODEL,
                "size": PHONE_SCREEN_IMAGE_SIZE,
                "quality": PHONE_SCREEN_IMAGE_QUALITY,
                "text_in_screen": "prohibited_by_prompt",
                "request_id": response.headers.get("x-request-id"),
            },
            "width": inspected["width"],
            "height": inspected["height"],
        }
