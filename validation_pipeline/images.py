"""Bounded Pexels real-photo selection for Instagram Result generation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import ssl
from typing import Any
from urllib.parse import urlparse
import urllib.error
import urllib.parse
import urllib.request

import certifi


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
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

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
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds, context=self.ssl_context,
            ) as response:
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
            parsed = self._parse_photo(item)
            if parsed is not None:
                result.append(parsed)
        return result

    @staticmethod
    def _parse_photo(item: Any) -> PexelsPhoto | None:
        if not isinstance(item, dict) or not isinstance(item.get("src"), dict):
            return None
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
            return None
        return PexelsPhoto(
            photo_id=photo_id, width=int(item.get("width") or 0), height=int(item.get("height") or 0),
            image_url=image_url, page_url=page_url,
            photographer=str(item.get("photographer") or "Pexels contributor"),
            photographer_url=photographer_url, alt=str(item.get("alt") or "Real stock photograph"),
        )

    def get(self, photo_id: str) -> PexelsPhoto:
        normalized = str(photo_id).strip()
        if not normalized.isdigit():
            raise ValueError("Pexels photo ID must be numeric")
        request = urllib.request.Request(
            f"https://{PEXELS_API_HOST}/v1/photos/{normalized}",
            headers={"Authorization": self.api_key, "User-Agent": "PTW-Validation/1"},
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds, context=self.ssl_context,
            ) as response:
                raw = response.read(MAX_DOWNLOAD_BYTES + 1)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise RuntimeError("Pexels photo lookup rate limit reached") from error
            raise RuntimeError(f"Pexels photo lookup failed with HTTP {error.code}") from error
        if len(raw) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Pexels photo response exceeds the bounded size")
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("Pexels photo lookup returned invalid JSON") from error
        photo = self._parse_photo(value)
        if photo is None or photo.photo_id != normalized:
            raise ValueError("Pexels photo lookup returned an invalid source")
        return photo

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
        with urllib.request.urlopen(
            request, timeout=self.timeout_seconds, context=self.ssl_context,
        ) as response:
            if not _is_https_host(response.geturl(), PEXELS_IMAGE_HOST):
                raise ValueError("Pexels download redirected outside the allowed CDN")
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            if content_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ValueError("Pexels download is not a supported image")
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
        if not data or len(data) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Pexels download exceeds the bounded size")
        return data
