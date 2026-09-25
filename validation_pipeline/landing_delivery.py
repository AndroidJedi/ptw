"""Versioned display copies; original Landing PNGs remain the media authority.

Only asset writes prepare copies. Reads never encode or backfill existing pages.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from typing import Any

PROFILE = "webp-v1"
# Shared slot roles, independent of template/project identity.
SLOT_ROLES = {
    "hero_visual": "hero", "visual_break_visual": "artwork",
    "app_screen_1": "screen", "app_screen_2": "screen", "app_screen_3": "screen",
    "walkthrough_visual": "artwork",
}


def prepare(data: bytes, slot: str) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    from PIL import Image, ImageOps
    role = SLOT_ROLES[slot]
    source = ImageOps.exif_transpose(Image.open(BytesIO(data)))
    source.load()
    source = source.convert("RGBA" if "A" in source.getbands() or "transparency" in source.info else "RGB")
    widths = (480, 720, 960) if role == "screen" else (960, 1440)
    variants, files = [], {}
    original = sha256(data).hexdigest()
    for width in sorted({min(width, source.width) for width in widths}):
        image = source.copy()
        image.thumbnail((width, max(1, round(source.height * width / source.width))), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, "WEBP", quality=90, method=4, exact=True)
        encoded = output.getvalue()
        digest = sha256(encoded).hexdigest()
        path = f"delivery/{PROFILE}/{original}/{digest}.webp"
        files[path] = encoded
        variants.append({"profile": PROFILE, "sha256": digest, "width": image.width,
                         "height": image.height, "mime_type": "image/webp", "byte_count": len(encoded)})
    return variants, files


def selected_variants(record: dict) -> dict[str, list[dict]]:
    result = {}
    for asset in record.get("assets", []):
        selected = next((entry for entry in asset.get("history", [])
                         if entry.get("sha256") == asset.get("sha256")), {})
        if selected.get("variants"):
            result[asset["slot"]] = selected["variants"]
    return result


def variant_path(source: str, digest: str) -> str:
    import re
    if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in (source, digest)):
        raise KeyError("Landing display image was not found")
    return f"delivery/{PROFILE}/{source}/{digest}.webp"
