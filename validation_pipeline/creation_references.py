"""Passive website capture; temporary screenshots never become draft content."""
from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from PIL import Image, ImageOps


def website_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Website URL is invalid")
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or "." not in parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Use a public HTTPS website")
    return value


def normalized_png(data: bytes) -> bytes:
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("Reference image is too large")
    with Image.open(BytesIO(data)) as im:
        if im.width * im.height > 16_777_216:
            raise ValueError("Reference image has too many pixels")
        im = ImageOps.exif_transpose(im).convert("RGBA")
        im.thumbnail((2048, 2048))
        out = BytesIO()
        im.save(out, format="PNG")
        return out.getvalue()


def capture_website(url: str) -> dict:
    script = Path(__file__).resolve().parents[1] / "apps/commander-web/scripts/capture-website-reference.mjs"
    result = subprocess.run(["node", str(script), website_url(url)], capture_output=True, timeout=75, check=False)
    if result.returncode or len(result.stdout) > 24_000_000:
        raise ValueError("Could not inspect this website. Attach a screenshot instead.")
    value = json.loads(result.stdout)
    return {"url": url, "title": value["title"], "text": value["text"], "colors": value["colors"],
            "images": [normalized_png(base64.b64decode(v, validate=True)) for v in value["images"][:2]],
            "photos": [{"url": p["url"], "alt": p["alt"], "source_sha256": hashlib.sha256(base64.b64decode(p["bytes_base64"], validate=True)).hexdigest(), "bytes": normalized_png(base64.b64decode(p["bytes_base64"], validate=True))}
                       for p in value["photos"][:3]]}
