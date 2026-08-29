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

from validation_pipeline.studio_universal import DEFAULT_CONFIG, DEFAULT_CONTENT
from validation_pipeline.studio_workspace import UniversalStudioWorkspace


CANVAS_SIZE = 1080
TEXT_NODES = ("hero_title", "supporting_text", "bullet_1", "bullet_2", "bullet_3")
FLOW_NODES = (*TEXT_NODES, "cta")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def pixels(value: float) -> float:
    return value * CANVAS_SIZE


def audit_variant(name: str, preview: Mapping[str, Any]) -> dict[str, Any]:
    nodes = preview["resolved"]["nodes"]
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

    visible_flow = [node_id for node_id in FLOW_NODES if node_id in nodes]
    for previous_id, current_id in zip(visible_flow, visible_flow[1:]):
        previous = nodes[previous_id]["visible_bounds"]
        current = nodes[current_id]["visible_bounds"]
        require(previous is not None and current is not None, f"{name}: flow node is not visible")
        gap = pixels(current["y"] - previous["y"] - previous["height"])
        require(gap >= 2, f"{name}: {previous_id} collides with {current_id} ({gap:.2f}px)")

    cta = nodes["cta"]["box"]
    require(
        cta["x"] >= 0.04 and cta["x"] + cta["width"] <= 0.96,
        f"{name}: CTA leaves the horizontal safe area",
    )
    require(cta["y"] + cta["height"] <= 0.96, f"{name}: CTA leaves the bottom safe area")
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
    return [default, high_density, centered]


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
            report = audit_variant(name, preview)
            if output_dir is not None:
                preview_path = output_dir / f"{name}.png"
                preview_path.write_bytes(preview["bytes"])
                report["preview_path"] = str(preview_path.resolve())
            reports.append(report)
    print(json.dumps({"status": "passed", "variants": reports}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
