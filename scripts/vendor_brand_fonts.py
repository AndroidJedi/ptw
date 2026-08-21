#!/usr/bin/env python3
"""Vendor the immutable OFL font catalog used by Branding kits.

The upstream revision is intentionally pinned. Run this script only when the
catalog is deliberately upgraded, then review the generated checksums.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


UPSTREAM_REVISION = "ec626514f79f831f1ab848a82114a0ce7e2d6372"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "idea_generation" / "assets" / "brand_fonts"
BASE = f"https://raw.githubusercontent.com/google/fonts/{UPSTREAM_REVISION}/ofl"
CATALOG = {
    "Inter": ("inter/Inter%5Bopsz%2Cwght%5D.ttf", "inter/OFL.txt"),
    "Manrope": ("manrope/Manrope%5Bwght%5D.ttf", "manrope/OFL.txt"),
    "Montserrat": ("montserrat/Montserrat%5Bwght%5D.ttf", "montserrat/OFL.txt"),
    "IBM Plex Sans": ("ibmplexsans/IBMPlexSans%5Bwdth%2Cwght%5D.ttf", "ibmplexsans/OFL.txt"),
    "IBM Plex Serif": ("ibmplexserif/IBMPlexSerif-Regular.ttf", "ibmplexserif/OFL.txt"),
    "IBM Plex Mono": ("ibmplexmono/IBMPlexMono-Regular.ttf", "ibmplexmono/OFL.txt"),
}


def slug(value: str) -> str:
    return value.casefold().replace(" ", "-")


def fetch(relative: str) -> bytes:
    result = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "30", f"{BASE}/{relative}"],
        check=True,
        capture_output=True,
    )
    data = result.stdout
    if len(data) > 8 * 1024 * 1024:
        raise RuntimeError(f"upstream asset is unexpectedly large: {relative}")
    return data


def normalize_license(data: bytes) -> bytes:
    """Keep the upstream license text while making repository diffs portable."""
    text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return ("\n".join(line.rstrip() for line in text.splitlines()) + "\n").encode("utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    entries = {}
    for family, (font_source, license_source) in CATALOG.items():
        family_slug = slug(family)
        font_name = f"{family_slug}.ttf"
        license_name = f"{family_slug}-OFL.txt"
        font = fetch(font_source)
        license_text = normalize_license(fetch(license_source))
        (OUTPUT / font_name).write_bytes(font)
        (OUTPUT / license_name).write_bytes(license_text)
        entries[family] = {
            "font_file": font_name,
            "font_sha256": hashlib.sha256(font).hexdigest(),
            "license_file": license_name,
            "license_sha256": hashlib.sha256(license_text).hexdigest(),
            "source_revision": UPSTREAM_REVISION,
            "source_url": f"{BASE}/{font_source}",
        }
    (OUTPUT / "catalog.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
