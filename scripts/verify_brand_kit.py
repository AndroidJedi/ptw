#!/usr/bin/env python3
"""Build, inspect, and compile the deterministic Branding kit fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from idea_generation.brand_domain import FONT_CATALOG, evaluate_direction, normalize_direction
from idea_generation.brand_kit import assemble_brand_kit
from idea_generation.brand_providers import DeterministicBrandProvider


WEB = ROOT / "apps" / "commander-web"


def main() -> None:
    provider = DeterministicBrandProvider()
    evidence = ["00000000-0000-7000-8000-000000000001"]
    synthesis = provider.structured("DIRECTION_SYNTHESIS", {"evidence_ids": evidence})
    direction = normalize_direction(synthesis["directions"][0], 1)
    evaluation = evaluate_direction(
        direction, [], [], allowed_evidence_ids=evidence,
        case_content={"owner_idea": "Український продукт із видимим прогресом"},
    )
    if not evaluation["passed"]:
        raise RuntimeError(f"fixture direction failed: {evaluation}")

    with tempfile.TemporaryDirectory(prefix=".brand-kit-verify-", dir=WEB) as raw:
        directory = Path(raw)
        logo = directory / "logo.png"
        logo.write_bytes(provider.logo(direction).content)
        archive_path, digest, _manifest = assemble_brand_kit(
            direction, logo, directory / "assembled"
        )
        if hashlib.sha256(archive_path.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Brand Kit archive digest mismatch")
        extracted = directory / "consumer"
        with zipfile.ZipFile(archive_path) as archive:
            archive.testzip()
            archive.extractall(extracted)
        catalog = json.loads((extracted / "fonts" / "catalog.json").read_text())
        for name, details in catalog.items():
            font_path = extracted / "fonts" / details["font_file"]
            license_path = extracted / "fonts" / details["license_file"]
            if hashlib.sha256(font_path.read_bytes()).hexdigest() != details["font_sha256"]:
                raise RuntimeError(f"font checksum mismatch: {name}")
            if hashlib.sha256(license_path.read_bytes()).hexdigest() != details["license_sha256"]:
                raise RuntimeError(f"license checksum mismatch: {name}")
            if not ImageFont.truetype(str(font_path), 32).getbbox("Український інтерфейс"):
                raise RuntimeError(f"Ukrainian specimen did not render: {name}")
            if name not in FONT_CATALOG:
                raise RuntimeError(f"unapproved font in kit: {name}")
        subprocess.run(
            [
                str(WEB / "node_modules" / ".bin" / "tsc"),
                "--noEmit", "--strict", "--jsx", "react-jsx",
                "--module", "ESNext", "--target", "ES2022",
                "--moduleResolution", "Bundler", "--skipLibCheck",
                str(extracted / "src" / "components.tsx"),
                str(extracted / "src" / "theme.ts"),
                str(extracted / "src" / "index.ts"),
            ],
            cwd=WEB,
            check=True,
        )
        print(json.dumps({
            "status": "ok", "archive_sha256": digest,
            "fonts": sorted(catalog), "components_compiled": 10,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
