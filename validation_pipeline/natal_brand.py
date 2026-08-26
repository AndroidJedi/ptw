"""Canonical Natal identity used by every owner-created Instagram Result."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any


NATAL_LOGO_PATH = Path(__file__).resolve().parents[1] / "natal/assets/logo-natal.png"
NATAL_FONT_PATH = Path(__file__).resolve().parents[1] / "natal/assets/inter.ttf"
NATAL_LOGO_SHA256 = "f465a0e11be3c1ff1943bcc1bcd19246a9a54957fd5c1c6162081aec9a59c8ba"
NATAL_FONT_SHA256 = "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"


def _verified_bytes(path: Path, expected_digest: str, label: str) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise RuntimeError(f"canonical Natal {label} is unavailable") from error
    if hashlib.sha256(data).hexdigest() != expected_digest:
        raise RuntimeError(f"canonical Natal {label} digest does not match the approved asset")
    return data


@lru_cache(maxsize=1)
def natal_logo_bytes() -> bytes:
    _verified_bytes(NATAL_FONT_PATH, NATAL_FONT_SHA256, "font")
    return _verified_bytes(NATAL_LOGO_PATH, NATAL_LOGO_SHA256, "logo")


def natal_brand_document(logo_source_asset_id: str) -> dict[str, Any]:
    return {
        "name": "Natal",
        "colors": ["#0C0E12", "#181C25", "#F4F6FA", "#A3ADBD", "#43BDD3", "#87D0DD"],
        "fonts": ["Inter"],
        "tone_notes": "Compact, direct, calm, high-contrast and personally specific.",
        "logo_source_asset_id": logo_source_asset_id,
    }
