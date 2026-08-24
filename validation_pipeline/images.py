"""Pexels selection and deterministic square-ad rendering."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
from pathlib import Path
import textwrap
from typing import Any
from urllib.parse import urlparse
import urllib.error
import urllib.parse
import urllib.request


MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
PEXELS_API_HOST = "api.pexels.com"
PEXELS_IMAGE_HOST = "images.pexels.com"


def _is_https_host(value: str, host: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname == host


def _is_pexels_page(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in {"pexels.com", "www.pexels.com"}


@dataclass(frozen=True, slots=True)
class PexelsPhoto:
    photo_id: str
    width: int
    height: int
    image_url: str
    page_url: str
    photographer: str
    photographer_url: str
    alt: str

    def source_metadata(self) -> dict[str, Any]:
        return {
            "provider": "pexels",
            "external_id": self.photo_id,
            "source_uri": self.page_url,
            "photographer": self.photographer,
            "photographer_url": self.photographer_url,
            "license": "Pexels License",
            "license_url": "https://www.pexels.com/license/",
            "attribution": f"Photo by {self.photographer} on Pexels",
            "alt": self.alt,
        }


class PexelsClient:
    def __init__(self, api_key: str, *, timeout_seconds: int = 20) -> None:
        if not api_key:
            raise RuntimeError("PEXELS_API_KEY is required for real-photo creatives")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, *, per_page: int = 10) -> list[PexelsPhoto]:
        normalized = query.strip()
        if not normalized:
            raise ValueError("Pexels search query is required")
        params = urllib.parse.urlencode({"query": normalized, "orientation": "square", "per_page": min(per_page, 10)})
        request = urllib.request.Request(
            f"https://{PEXELS_API_HOST}/v1/search?{params}",
            headers={"Authorization": self.api_key, "User-Agent": "PTW-Validation/1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(MAX_DOWNLOAD_BYTES + 1)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise RuntimeError("Pexels search rate limit reached") from error
            raise RuntimeError(f"Pexels search failed with HTTP {error.code}") from error
        if len(raw) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Pexels search response exceeds the bounded size")
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("Pexels search returned invalid JSON") from error
        photos = value.get("photos") if isinstance(value, dict) else None
        if not isinstance(photos, list):
            raise ValueError("Pexels search returned invalid JSON")
        result: list[PexelsPhoto] = []
        for item in photos:
            if not isinstance(item, dict) or not isinstance(item.get("src"), dict):
                continue
            image_url = str(item["src"].get("large2x") or item["src"].get("original") or "")
            page_url = str(item.get("url") or "")
            photographer_url = str(item.get("photographer_url") or "")
            photo_id = str(item.get("id") or "")
            if (
                not photo_id
                or not _is_https_host(image_url, PEXELS_IMAGE_HOST)
                or not _is_pexels_page(page_url)
                or not _is_pexels_page(photographer_url)
            ):
                continue
            result.append(PexelsPhoto(
                photo_id=photo_id,
                width=int(item.get("width") or 0),
                height=int(item.get("height") or 0),
                image_url=image_url,
                page_url=page_url,
                photographer=str(item.get("photographer") or "Pexels contributor"),
                photographer_url=photographer_url,
                alt=str(item.get("alt") or "Real stock photograph"),
            ))
        return result

    def select(self, query: str, category: str, *, used_ids: set[str]) -> tuple[PexelsPhoto, bytes]:
        for search_term in (query, category):
            for photo in self.search(search_term):
                if photo.photo_id in used_ids or photo.width < 1080 or photo.height < 1080:
                    continue
                try:
                    return photo, self.download(photo)
                except (RuntimeError, ValueError):
                    continue
        raise RuntimeError("Pexels did not return a distinct usable square photo")

    def download(self, photo: PexelsPhoto) -> bytes:
        if not _is_https_host(photo.image_url, PEXELS_IMAGE_HOST):
            raise ValueError("Pexels image URL is outside the allowed CDN")
        request = urllib.request.Request(photo.image_url, headers={"User-Agent": "PTW-Validation/1"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            if not _is_https_host(response.geturl(), PEXELS_IMAGE_HOST):
                raise ValueError("Pexels download redirected outside the allowed CDN")
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            if content_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ValueError("Pexels download is not a supported image")
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
        if not data or len(data) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Pexels download exceeds the bounded size")
        return data


class SquareCreativeRenderer:
    WIDTH = 1080
    HEIGHT = 1080

    def __init__(self, font_path: Path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")) -> None:
        self.font_path = font_path

    def render(self, source: bytes, *, hook: str, offer: str, cta: str, crop_focus: str) -> tuple[bytes, str]:
        from PIL import Image, ImageDraw, ImageFont, ImageOps

        try:
            original = Image.open(BytesIO(source))
            original.load()
        except Exception as error:
            raise ValueError("downloaded photo cannot be decoded") from error
        if original.width < self.WIDTH or original.height < self.HEIGHT:
            raise ValueError("downloaded photo is too small")
        centering = {"left": (0.25, 0.5), "center": (0.5, 0.5), "right": (0.75, 0.5)}[crop_focus]
        image = ImageOps.fit(original.convert("RGB"), (self.WIDTH, self.HEIGHT), centering=centering)
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        gradient = Image.new("L", (1, self.HEIGHT))
        gradient.putdata([int(35 + 180 * (y / (self.HEIGHT - 1))) for y in range(self.HEIGHT)])
        alpha = gradient.resize(image.size)
        overlay.paste((7, 11, 18, 230), (0, 0, self.WIDTH, self.HEIGHT), alpha)
        composed = Image.alpha_composite(image.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(composed)
        font_regular = ImageFont.truetype(str(self.font_path), 42)
        font_hook = ImageFont.truetype(str(self.font_path), 74)
        font_cta = ImageFont.truetype(str(self.font_path), 36)
        draw.text((72, 70), "PTW · VALIDATION CREATIVE", font=font_regular, fill=(255, 255, 255, 210))
        hook_lines = textwrap.wrap(hook, width=24)[:4]
        draw.multiline_text((72, 250), "\n".join(hook_lines), font=font_hook, fill="white", spacing=16)
        offer_lines = textwrap.wrap(offer, width=42)[:3]
        draw.multiline_text((72, 760), "\n".join(offer_lines), font=font_regular, fill=(255, 224, 126), spacing=10)
        cta_text = textwrap.shorten(cta, width=42, placeholder="…")
        box = draw.textbbox((0, 0), cta_text, font=font_cta)
        box_width = box[2] - box[0]
        draw.rounded_rectangle((72, 930, min(1008, 128 + box_width), 1008), radius=18, fill=(255, 255, 255, 235))
        draw.text((100, 948), cta_text, font=font_cta, fill=(8, 17, 31))
        output = BytesIO()
        composed.convert("RGB").save(output, format="JPEG", quality=88, optimize=True, progressive=True)
        data = output.getvalue()
        return data, hashlib.sha256(data).hexdigest()
