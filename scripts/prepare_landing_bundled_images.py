#!/usr/bin/env python3
"""Reproducible display derivatives; preserve the checked-in source assets."""
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "validation_pipeline/studio_assets"
OUTPUT = ASSETS / "landing-display-v1"


def main():
    OUTPUT.mkdir(exist_ok=True)
    sources = [(ASSETS / "iphone-15-pro-black.png", None, True)]
    sources += [(ASSETS / "app-showcase" / f"{name}.png", 160, False) for name in ("iryna", "mykyta", "maryna")]
    manifest = []
    for source, width, lossless in sources:
        image = Image.open(source)
        if width:
            image.thumbnail((width, width), Image.Resampling.LANCZOS)
        destination = OUTPUT / (source.stem + ".webp")
        image.save(destination, "WEBP", quality=90, lossless=lossless, method=6, exact=True)
        manifest.append({"source": str(source.relative_to(ROOT)), "source_sha256": sha256(source.read_bytes()).hexdigest(),
                         "file": destination.name, "sha256": sha256(destination.read_bytes()).hexdigest(),
                         "width": image.width, "height": image.height, "lossless": lossless, "quality": 90})
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
