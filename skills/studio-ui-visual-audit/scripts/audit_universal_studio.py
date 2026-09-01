#!/usr/bin/env python3
"""Fail when representative Universal Studio layouts clip or collide."""

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
    print(json.dumps({"status": "passed", "variants": reports}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
