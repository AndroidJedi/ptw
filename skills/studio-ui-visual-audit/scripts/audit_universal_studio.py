#!/usr/bin/env python3
"""Fail when representative Universal Studio layouts clip, collide, or drift."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from validation_pipeline.studio_universal import (
    DEFAULT_CONFIG, DEFAULT_CONTENT, universal_alignment_rectangle,
)
from validation_pipeline.studio_phone_metrics import (
    DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_CONTENT, PHONE_METRICS_TEMPLATE_ID,
)
from validation_pipeline.studio_workspace import UniversalStudioWorkspace


CANVAS_SIZE = 1080
BOUND_EPSILON = 1 / CANVAS_SIZE
TEXT_NODES = (
    "hero_title", "supporting_text", "offer", "bullet_1", "bullet_2", "bullet_3",
)
MARKER_NODES = ("bullet_marker_1", "bullet_marker_2", "bullet_marker_3")
FLOW_NODES = (*TEXT_NODES, "cta")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def pixels(value: float) -> float:
    return value * CANVAS_SIZE


def audit_variant(
    name: str, preview: Mapping[str, Any], configuration: Mapping[str, Any],
) -> dict[str, Any]:
    nodes = preview["resolved"]["nodes"]
    alignment = universal_alignment_rectangle(configuration)
    alignment_left = alignment["x"] / CANVAS_SIZE
    alignment_top = alignment["y"] / CANVAS_SIZE
    alignment_right = (alignment["x"] + alignment["width"]) / CANVAS_SIZE
    alignment_bottom = (alignment["y"] + alignment["height"]) / CANVAS_SIZE
    inspected: dict[str, Any] = {}
    for node_id in TEXT_NODES:
        if node_id not in nodes:
            continue
        node = nodes[node_id]
        box, visible, layout = node["box"], node["visible_bounds"], node["text_layout"]
        require(visible is not None, f"{name}: {node_id} has no visible pixels")
        require(layout is not None, f"{name}: {node_id} has no text-layout diagnostics")
        require(not layout["overflow"], f"{name}: {node_id} overflows or truncates")
        require(
            abs(pixels(visible["y"] - box["y"])) <= 1,
            f"{name}: {node_id} visible ink is not top-aligned to its box",
        )
        require(
            pixels(visible["x"]) >= pixels(box["x"]) - 1
            and pixels(visible["x"] + visible["width"])
            <= pixels(box["x"] + box["width"]) - 1,
            f"{name}: {node_id} visible ink touches or crosses its horizontal box edge",
        )
        require(
            pixels(visible["y"] + visible["height"])
            <= pixels(box["y"] + box["height"]) - 1,
            f"{name}: {node_id} visible ink touches or crosses its bottom box edge",
        )
        inspected[node_id] = {
            "font_size": layout["font_size"],
            "line_count": layout["line_count"],
            "visible_top": round(pixels(visible["y"]), 2),
            "visible_bottom": round(pixels(visible["y"] + visible["height"]), 2),
        }

    for index, marker_id in enumerate(MARKER_NODES, 1):
        bullet_id = f"bullet_{index}"
        if bullet_id not in nodes:
            continue
        require(marker_id in nodes, f"{name}: {bullet_id} has no marker node")
        marker = nodes[marker_id]
        require(marker["visible_bounds"] is not None, f"{name}: {marker_id} has no visible pixels")
        require(marker["props"]["font_family"] == "Inter", f"{name}: {marker_id} lost its symbol font")
        require(not marker["text_layout"]["overflow"], f"{name}: {marker_id} overflows")
        require(
            marker["visible_bounds"]["x"] + marker["visible_bounds"]["width"]
            < nodes[bullet_id]["visible_bounds"]["x"],
            f"{name}: {marker_id} collides with {bullet_id}",
        )

    visible_flow = [node_id for node_id in FLOW_NODES if node_id in nodes]
    for previous_id, current_id in zip(visible_flow, visible_flow[1:]):
        previous = nodes[previous_id]["visible_bounds"]
        current = nodes[current_id]["visible_bounds"]
        require(previous is not None and current is not None, f"{name}: flow node is not visible")
        gap = pixels(current["y"] - previous["y"] - previous["height"])
        require(gap >= 2, f"{name}: {previous_id} collides with {current_id} ({gap:.2f}px)")

    cta_node = nodes["cta"]
    cta = cta_node["box"]
    cta_layout = cta_node["text_layout"]
    require(cta_layout is not None, f"{name}: CTA has no text-layout diagnostics")
    require(not cta_layout["overflow"], f"{name}: CTA overflows or truncates")
    require(not cta_layout["truncated"], f"{name}: CTA text is truncated")
    inspected["cta"] = {
        "font_size": cta_layout["font_size"],
        "line_count": cta_layout["line_count"],
    }
    require(
        cta["x"] >= alignment_left - BOUND_EPSILON
        and cta["x"] + cta["width"] <= alignment_right + BOUND_EPSILON,
        f"{name}: CTA leaves the shared alignment rectangle",
    )
    require(
        cta["y"] >= alignment_top - BOUND_EPSILON
        and cta["y"] + cta["height"] <= alignment_bottom + BOUND_EPSILON,
        f"{name}: CTA leaves the shared alignment rectangle",
    )
    for node_id in TEXT_NODES:
        if node_id not in nodes:
            continue
        box = nodes[node_id]["box"]
        require(
            box["x"] >= alignment_left - BOUND_EPSILON
            and box["x"] + box["width"] <= alignment_right + BOUND_EPSILON
            and box["y"] >= alignment_top - BOUND_EPSILON
            and box["y"] + box["height"] <= alignment_bottom + BOUND_EPSILON,
            f"{name}: {node_id} leaves the shared alignment rectangle",
        )
    if "logo" in nodes:
        logo = nodes["logo"]
        surface = nodes.get("logo_surface")
        require(surface is None, f"{name}: removed logo backing surface reappeared")
        logo_box = logo["box"]
        collision_box = logo_box
        require(logo["visible_bounds"] is not None, f"{name}: logo has no visible pixels")
        require(
            collision_box["x"] >= alignment_left - BOUND_EPSILON
            and collision_box["y"] >= alignment_top - BOUND_EPSILON
            and collision_box["x"] + collision_box["width"]
            <= alignment_right + BOUND_EPSILON
            and collision_box["y"] + collision_box["height"]
            <= alignment_bottom + BOUND_EPSILON,
            f"{name}: logo treatment leaves the shared alignment rectangle",
        )
        for node_id in FLOW_NODES:
            if node_id not in nodes or nodes[node_id]["visible_bounds"] is None:
                continue
            visible = nodes[node_id]["visible_bounds"]
            overlaps = (
                visible["x"] < collision_box["x"] + collision_box["width"]
                and visible["x"] + visible["width"] > collision_box["x"]
                and visible["y"] < collision_box["y"] + collision_box["height"]
                and visible["y"] + visible["height"] > collision_box["y"]
            )
            require(not overlaps, f"{name}: logo collides with {node_id}")
        inspected["logo"] = {
            "position": [round(pixels(logo_box["x"]), 2), round(pixels(logo_box["y"]), 2)],
            "size": [round(pixels(logo_box["width"]), 2), round(pixels(logo_box["height"]), 2)],
            "background": False,
        }
    return {"name": name, "text": inspected}


def _overlaps(first: Mapping[str, float], second: Mapping[str, float]) -> bool:
    return bool(
        first["x"] < second["x"] + second["width"]
        and first["x"] + first["width"] > second["x"]
        and first["y"] < second["y"] + second["height"]
        and first["y"] + first["height"] > second["y"]
    )


def audit_phone_metrics(preview: Mapping[str, Any], detail: Mapping[str, Any]) -> dict[str, Any]:
    """Check the owner-approved 4:5 phone reference characteristics exactly."""

    require((preview["width"], preview["height"]) == (1080, 1350), "phone: canvas is not 1080x1350")
    require(detail["template_id"] == PHONE_METRICS_TEMPLATE_ID, "phone: wrong template selected")
    nodes = preview["resolved"]["nodes"]
    required = {
        "paper_texture", "logo", "offer", "hero_title", "supporting_text", "phone_device",
        "metric_card_1", "metric_card_2", "metric_card_3", "metric_value_1", "metric_value_2",
        "metric_value_3", "metric_label_1", "metric_label_2", "metric_label_3", "cta",
    }
    require(required <= set(nodes), "phone: required reference nodes are missing")
    # The static black device and its screen are one image layer: they cannot
    # drift apart through an editor transform.
    require([node_id for node_id in nodes if node_id == "phone_device"] == ["phone_device"], "phone: device is not one grouped layer")

    logo = nodes["logo"]["visible_bounds"]
    hero = nodes["hero_title"]
    support = nodes["supporting_text"]
    device = nodes["phone_device"]
    require(logo is not None and logo["x"] < .1 and logo["y"] < .12, "phone: Natal lock-up left safe area drift")
    require(hero["visible_bounds"] is not None and support["visible_bounds"] is not None, "phone: dark copy is not visible")
    require(hero["box"]["x"] < .1 and hero["box"]["x"] + hero["box"]["width"] <= .5, "phone: headline leaves the left safe area")
    require(support["box"]["x"] < .1 and support["box"]["x"] + support["box"]["width"] <= .5, "phone: supporting text leaves the left safe area")
    require(not hero["text_layout"]["overflow"] and not support["text_layout"]["overflow"], "phone: left copy overflows")
    visible_device = device["visible_bounds"]
    require(visible_device is not None, "phone: device has no visible pixels")
    require(visible_device["x"] >= .48 and visible_device["y"] <= .1, "phone: device is not upper-right")
    require(visible_device["x"] + visible_device["width"] <= .99 and visible_device["y"] + visible_device["height"] <= .74, "phone: device leaves safe bounds")
    require(not _overlaps(hero["visible_bounds"], visible_device), "phone: headline overlaps device")
    require(not _overlaps(support["visible_bounds"], visible_device), "phone: supporting text overlaps device")

    cards = [nodes[f"metric_card_{index}"]["box"] for index in range(1, 4)]
    require(len({round(card["y"], 5) for card in cards}) == 1, "phone: metric cards do not share one row")
    require(len({round(card["width"], 5) for card in cards}) == 1, "phone: metric cards are not equal")
    require(cards[0]["y"] >= .73 and cards[-1]["x"] + cards[-1]["width"] <= .95, "phone: metric row drift")
    for index in range(1, 4):
        for kind in ("metric_value", "metric_label"):
            layout = nodes[f"{kind}_{index}"]["text_layout"]
            require(layout is not None and not layout["overflow"] and not layout["truncated"], f"phone: {kind}_{index} clips")
    cta = nodes["cta"]["box"]
    require(cta["x"] == 0 and cta["width"] == 1 and cta["y"] >= .89 and cta["y"] + cta["height"] == 1, "phone: CTA is not a bottom band")
    require(not nodes["cta"]["text_layout"]["overflow"], "phone: CTA clips")

    # Full-resolution colour checks intentionally read the render rather than
    # trusting template declarations.
    from io import BytesIO
    from PIL import Image

    with Image.open(BytesIO(preview["bytes"])) as image:
        pixels_rgba = image.convert("RGB")
        top = pixels_rgba.getpixel((420, 30))
        require(min(top) >= 224 and max(top) - min(top) <= 16, "phone: background is not off-white")
        texture_colours = {
            pixels_rgba.getpixel((x, y))
            for x in range(340, 520, 31) for y in range(18, 122, 19)
        }
        require(len(texture_colours) >= 3, "phone: off-white background lost its texture")
        require(pixels_rgba.getpixel((110, 1100)) == (36, 87, 200), "phone: first metric card is not cobalt")
        require(pixels_rgba.getpixel((540, 1100)) == (36, 87, 200), "phone: second metric card is not cobalt")
        require(pixels_rgba.getpixel((930, 1100)) == (36, 87, 200), "phone: third metric card is not cobalt")
        require(pixels_rgba.getpixel((16, 1300)) == (49, 108, 255), "phone: CTA band is not cobalt")
    require(detail["content"]["phone_hero_title"] == "", "phone: audit fixture unexpectedly adds owner phone text")
    phone_asset = next(item for item in detail["assets"] if item["slot"] == "phone_screen")
    require(not phone_asset["available"], "phone: audit fixture unexpectedly supplied generated art")
    return {
        "name": "phone_metrics_reference", "canvas": [preview["width"], preview["height"]],
        "device_visible_bounds": visible_device, "metric_row_y": cards[0]["y"],
        "cta_y": cta["y"], "checks": [
            "off_white_texture", "natal_upper_left", "left_safe_copy", "angled_right_rail_phone",
            "three_equal_cobalt_cards", "cobalt_cta_band", "no_clipping_or_overlap", "no_generated_screen_text",
        ],
    }


def variants() -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    default = ("default", copy.deepcopy(DEFAULT_CONFIG), copy.deepcopy(DEFAULT_CONTENT))

    high_density_config = copy.deepcopy(DEFAULT_CONFIG)
    high_density_config["typography"].update({"hero_size": 180, "supporting_size": 52})
    high_density_config["layout"].update({"content_y": 360, "gap": 56})
    high_density = (
        "high_density",
        high_density_config,
        copy.deepcopy(DEFAULT_CONTENT),
    )

    centered_config = copy.deepcopy(DEFAULT_CONFIG)
    centered_config["typography"]["alignment"] = "center"
    centered_config["layout"].update({"content_y": 72, "content_width": 936, "gap": 8})
    centered_config["bullets"]["enabled"] = False
    centered_config["sticker"]["enabled"] = False
    centered = ("centered_minimal", centered_config, copy.deepcopy(DEFAULT_CONTENT))

    editorial_config = copy.deepcopy(DEFAULT_CONFIG)
    editorial_config["background"].update({"mode": "texture", "texture": "marble"})
    editorial_config["typography"].update({
        "font_family": "Cormorant Garamond", "benefits_font_family": "Manrope",
    })
    editorial_config["cta"]["position"] = "bottom_left"
    editorial_config["sticker"]["enabled"] = False
    editorial = ("editorial_bottom_left", editorial_config, copy.deepcopy(DEFAULT_CONTENT))

    urgent_config = copy.deepcopy(DEFAULT_CONFIG)
    urgent_config["typography"].update({
        "font_family": "Oswald", "benefits_font_family": "Oswald",
    })
    urgent_config["cta"]["position"] = "bottom_right"
    urgent_config["sticker"]["enabled"] = False
    urgent = ("urgent_bottom_right", urgent_config, copy.deepcopy(DEFAULT_CONTENT))

    logo_no_background_config = copy.deepcopy(DEFAULT_CONFIG)
    logo_no_background_config["background"].update({
        "mode": "solid", "color": "#F4F6FA", "overlay_opacity": 0,
    })
    logo_no_background_config["typography"]["text_color"] = "#10233F"
    logo_no_background_config["sticker"]["enabled"] = False
    logo_no_background_config["logo"]["background_enabled"] = False
    logo_no_background = (
        "logo_no_background", logo_no_background_config, copy.deepcopy(DEFAULT_CONTENT),
    )
    return [default, high_density, centered, editorial, urgent, logo_no_background]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional directory for the exact audited 1080x1080 PNG variants.",
    )
    arguments = parser.parse_args()
    output_dir = arguments.output_dir
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    reports = []
    with tempfile.TemporaryDirectory(prefix="ptw-studio-ui-audit-") as temporary:
        workspace = UniversalStudioWorkspace(temporary)
        state = workspace.detail()["state_sha256"]
        for name, configuration, content in variants():
            preview = workspace.render_preview(
                state_sha256=state,
                configuration=configuration,
                content=content,
            )
            report = audit_variant(name, preview, configuration)
            if output_dir is not None:
                preview_path = output_dir / f"{name}.png"
                preview_path.write_bytes(preview["bytes"])
                report["preview_path"] = str(preview_path.resolve())
            reports.append(report)
        phone_workspace = UniversalStudioWorkspace(Path(temporary) / "phone")
        initial = phone_workspace.detail()
        phone = phone_workspace.apply_template(
            base_sha256=initial["state_sha256"], template_id=PHONE_METRICS_TEMPLATE_ID,
        )
        phone_preview = phone_workspace.render_preview(state_sha256=phone["state_sha256"])
        phone_report = audit_phone_metrics(phone_preview, phone)
        if output_dir is not None:
            phone_path = output_dir / "phone_metrics_reference.png"
            phone_path.write_bytes(phone_preview["bytes"])
            phone_report["preview_path"] = str(phone_path.resolve())
        reports.append(phone_report)
    print(json.dumps({"status": "passed", "variants": reports}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
