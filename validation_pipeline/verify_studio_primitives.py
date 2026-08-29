"""Render two non-product primitive-engine expressiveness benchmarks."""

from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .studio import StudioRenderer
from .studio_primitives import load_primitive_template, primitive_catalog


BENCHMARK_DIRECTORY = Path(__file__).with_name("studio_templates") / "benchmarks"
BENCHMARK_ASSET_DIRECTORY = BENCHMARK_DIRECTORY / "assets"


def _png(image: Any) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _texture() -> bytes:
    from PIL import Image, ImageDraw

    width = height = 1080
    image = Image.new("RGB", (width, height), "#43A99E")
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            grain = ((x * 17 + y * 29 + (x * y) % 31) % 23) - 11
            pixels[x, y] = (
                max(0, min(255, 67 + grain)),
                max(0, min(255, 169 + grain)),
                max(0, min(255, 158 + grain)),
            )
    draw = ImageDraw.Draw(image, "RGBA")
    for index in range(34):
        x = (index * 137) % width
        y = (index * 211) % height
        draw.arc((x - 120, y - 40, x + 240, y + 80), 5, 170, fill=(230, 255, 245, 20), width=2)
    return _png(image)


def _medallion() -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (360, 360), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    gold, light_gold, black = "#E4AF55", "#F8DA91", "#101112"
    draw.ellipse((55, 55, 305, 305), fill=gold)
    for index in range(20):
        angle = index * 18 * 3.141592653589793 / 180
        cx = 180 + 132 * __import__("math").cos(angle)
        cy = 180 + 132 * __import__("math").sin(angle)
        draw.regular_polygon((cx, cy, 18), n_sides=3, rotation=index * 18, fill=light_gold)
    draw.ellipse((74, 74, 286, 286), fill=black, outline=light_gold, width=6)
    draw.arc((118, 112, 242, 250), 205, 335, fill=light_gold, width=10)
    draw.arc((105, 105, 220, 238), 25, 150, fill=light_gold, width=9)
    draw.arc((140, 105, 255, 238), 30, 155, fill=light_gold, width=9)
    draw.ellipse((163, 235, 197, 269), fill="#16BFA7", outline=light_gold, width=4)
    for x, y in ((115, 136), (248, 155), (132, 248), (240, 230)):
        draw.regular_polygon((x, y, 8), n_sides=4, rotation=45, fill="#FFF5CF")
    draw.rounded_rectangle((165, 17, 195, 74), radius=13, outline=gold, width=9)
    return _png(image)


def _necklace() -> bytes:
    import math
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (760, 1320), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    gold, light = "#E0A84C", "#F7D98F"
    points = []
    for index in range(121):
        t = index / 120
        x = 65 + t * 630
        y = -80 + 1120 * (1 - 4 * (t - 0.5) ** 2)
        points.append((x, y))
    draw.line(points, fill=gold, width=7)
    for index in range(0, len(points), 3):
        x, y = points[index]
        draw.ellipse((x - 5, y - 7, x + 5, y + 7), outline=light, width=2)
    draw.rounded_rectangle((352, 1060, 408, 1145), radius=22, fill=gold, outline=light, width=5)
    draw.ellipse((270, 1110, 490, 1329), fill=gold, outline=light, width=8)
    draw.ellipse((294, 1134, 466, 1306), fill="#F3CB79")
    for angle in (25, 75, 140, 205, 300):
        radius = 56 if angle % 2 else 72
        x = 380 + math.cos(math.radians(angle)) * radius
        y = 1220 + math.sin(math.radians(angle)) * radius
        draw.regular_polygon((x, y, 10), n_sides=4, rotation=45, fill="#FFF8DB", outline="#A77A2C")
    return _png(image)


def _hand_cutout() -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (920, 700), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    skin, edge, nail = "#A7613F", "#6F3927", "#D98C6C"
    draw.polygon(
        [(-20, 205), (205, 182), (330, 156), (780, 152), (870, 178),
         (805, 216), (388, 247), (342, 310), (270, 386), (194, 640),
         (-20, 694)],
        fill=skin,
    )
    draw.ellipse((92, 190, 370, 442), fill=skin)
    draw.polygon(
        [(184, 338), (318, 330), (548, 408), (640, 462), (587, 498),
         (486, 469), (294, 424), (166, 456)],
        fill=skin,
    )
    draw.ellipse((515, 410, 653, 494), fill=skin)
    draw.ellipse((785, 160, 881, 217), fill=skin)
    draw.ellipse((556, 439, 653, 492), fill=nail)
    draw.line([(6, 207), (330, 170), (787, 166)], fill=edge, width=5)
    draw.line([(170, 455), (294, 420), (505, 467)], fill=edge, width=4)
    draw.ellipse((98, 202, 190, 287), fill="#D5B58B", outline=edge, width=5)
    draw.ellipse((118, 218, 170, 270), fill="#E9D9B6", outline="#917246", width=4)
    draw.regular_polygon((144, 244, 26), n_sides=8, rotation=22, fill="#F4E9D1", outline="#5C4B38")
    return _png(image)


def benchmark_assets() -> dict[str, dict[str, Mapping[str, Any]]]:
    return {
        "layered_product_reference": {
            "turquoise_texture": {"bytes": _texture(), "mime_type": "image/png"},
            "necklace_cutout": {"bytes": _necklace(), "mime_type": "image/png"},
            "medallion_cutout": {"bytes": _medallion(), "mime_type": "image/png"},
        },
        "editorial_cutout_reference": {
            "hand_cutout": {
                "bytes": (BENCHMARK_ASSET_DIRECTORY / "aquarius_hand_generated_v2.png").read_bytes(),
                "mime_type": "image/png",
            },
        },
    }


BENCHMARK_CONTENT = {
    "layered_product_reference": {
        "content.headline": "GEMINI",
        "content.description": "TWO VACATIONS, EIGHT GROUP CHATS,\nZERO CONFIRMED PLANS.\nEXTREMELY ON BRAND.",
        "content.cta": "ZOOM IN",
        "media.product_primary": "necklace_cutout",
        "media.product_secondary": "medallion_cutout",
    },
    "editorial_cutout_reference": {
        "content.headline": "Aquarius, Zoom In",
        "content.description": "Your ideas look great",
        "media.hero": "hand_cutout",
    },
}


def render_benchmarks(output_dir: Path | str) -> dict[str, Any]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    renderer = StudioRenderer()
    asset_sets = benchmark_assets()
    reports = []
    for path in sorted(BENCHMARK_DIRECTORY.glob("*_v1.json")):
        template = load_primitive_template(path)
        template_id = str(template.document["template_id"])
        preview = renderer.render_preview(
            template,
            semantic_data=BENCHMARK_CONTENT[template_id],
            assets=asset_sets[template_id],
        )
        output_path = destination / f"{template_id}.png"
        output_path.write_bytes(preview["bytes"])
        reports.append({
            "template_id": template_id,
            "template_path": str(path),
            "template_sha256": template.digest,
            "preview_path": str(output_path),
            "preview_sha256": preview["bytes_sha256"],
            "width": preview["width"],
            "height": preview["height"],
            "node_count": preview["resolved"]["node_count"],
        })
    if len(reports) != 2:
        raise RuntimeError("primitive-engine benchmark requires exactly two configurations")
    if len({item["preview_sha256"] for item in reports}) != 2:
        raise RuntimeError("primitive-engine benchmark previews must be materially distinct bytes")
    catalog = primitive_catalog()
    manifest = {
        "schema": "ptw.studio.expressiveness-benchmark.v1",
        "catalog": {"version": catalog["version"], "sha256": catalog["sha256"]},
        "templates": reports,
    }
    raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (destination / "manifest.json").write_text(raw)
    return manifest


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=".local/studio-primitives")
    args = parser.parse_args()
    print(json.dumps(render_benchmarks(args.output_dir), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
