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
    PHONE_SCREEN_ART_SIZE, compose_phone_device_asset,
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


def audit_phone_metrics(
    preview: Mapping[str, Any], detail: Mapping[str, Any], *, name: str,
) -> dict[str, Any]:
    """Check the owner-approved 4:5 phone reference characteristics exactly."""

    require((preview["width"], preview["height"]) == (1080, 1350), "phone: canvas is not 1080x1350")
    require(detail["template_id"] == PHONE_METRICS_TEMPLATE_ID, "phone: wrong template selected")
    nodes = preview["resolved"]["nodes"]
    required = {
        "logo", "hero_title", "supporting_text", "phone_device",
        "metric_card_1", "metric_card_2", "metric_card_3", "metric_value_1", "metric_value_2",
        "metric_value_3", "metric_label_1", "metric_label_2", "metric_label_3", "cta",
    }
    require(required <= set(nodes), "phone: required reference nodes are missing")
    background_texture = detail["configuration"]["background"]["texture"]
    copy_background_texture = detail["configuration"]["copy_background"]["texture"]
    require(
        ("background_texture" in nodes) == (background_texture != "none"),
        "phone: optional background texture node does not match its selection",
    )
    require(
        ("copy_background_texture" in nodes) == (copy_background_texture != "none"),
        "phone: optional left-copy texture node does not match its selection",
    )
    if copy_background_texture != "none":
        copy_surface = nodes["copy_background_texture"]["box"]
        require(
            copy_surface["x"] < .05
            and copy_surface["x"] + copy_surface["width"] <= .51
            and copy_surface["y"] + copy_surface["height"] <= .69,
            "phone: left-copy texture is not bounded to the marked copy area",
        )
    if detail["configuration"]["offer"]["enabled"]:
        require("offer" in nodes, "phone: enabled eyebrow node is missing")
    else:
        require("offer" not in nodes, "phone: disabled eyebrow left a renderer node")
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
    require(support["type"] == "rich_text", "phone: supporting text lost rich-text rendering")
    require(support["text_layout"]["markup"] == "simple_v1", "phone: supporting text markup is not active")
    require(support["text_layout"]["delimiter_character_count"] == 8, "phone: supporting text markup delimiters were not removed")
    require(support["text_layout"]["bold_character_count"] > 0, "phone: supporting text has no bold words")
    require(support["text_layout"]["highlight_character_count"] > 0, "phone: supporting text has no highlighted words")
    supporting_config = detail["configuration"]["supporting_text"]
    require(
        support["props"]["font_size"] == supporting_config["font_size"],
        "phone: supporting text font-size control did not reach the renderer",
    )
    require(
        support["props"]["highlight_color"] == supporting_config["highlight_color"],
        "phone: supporting word colour did not reach the renderer",
    )
    visible_device = device["visible_bounds"]
    require(visible_device is not None, "phone: device has no visible pixels")
    require(visible_device["x"] >= .55 and visible_device["y"] <= .1, "phone: front device is not upper-right")
    require(visible_device["x"] + visible_device["width"] <= .99 and visible_device["y"] + visible_device["height"] <= .72, "phone: front device leaves safe bounds")
    require(not _overlaps(hero["visible_bounds"], visible_device), "phone: headline overlaps device")
    require(not _overlaps(support["visible_bounds"], visible_device), "phone: supporting text overlaps device")

    cards = [nodes[f"metric_card_{index}"]["box"] for index in range(1, 4)]
    require(len({round(card["y"], 5) for card in cards}) == 1, "phone: metric cards do not share one row")
    require(len({round(card["width"], 5) for card in cards}) == 1, "phone: metric cards are not equal")
    require(cards[0]["y"] >= .73 and cards[-1]["x"] + cards[-1]["width"] <= .95, "phone: metric row drift")
    require(all(card["width"] <= 280 / 1080 for card in cards), "phone: metric cards are not compact")
    require(all(card["height"] <= 140 / 1350 for card in cards), "phone: metric cards are too tall")
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
            for x in range(558, 600, 3) for y in range(0, 1000, 7)
        }
        require(
            len(texture_colours) == 1 if background_texture == "none"
            else len(texture_colours) >= 3,
            "phone: outer texture pixels do not match the selected optional state",
        )
        copy_texture_colours = {
            pixels_rgba.getpixel((x, y))
            for x in range(48, 63, 2) for y in range(180, 900, 7)
        }
        require(
            len(copy_texture_colours) == 1 if copy_background_texture == "none"
            else len(copy_texture_colours) >= 3,
            "phone: left-copy texture pixels do not match the selected optional state",
        )
        accent = supporting_config["highlight_color"]
        accent_rgb = tuple(int(accent[index:index + 2], 16) for index in (1, 3, 5))
        accent_pixels = sum(
            1 for y in range(675, 893) for x in range(70, 488)
            if all(
                abs(channel - expected) <= 3
                for channel, expected in zip(pixels_rgba.getpixel((x, y)), accent_rgb)
            )
        )
        require(accent_pixels > 50, "phone: highlighted word colour is absent from rendered pixels")
        for index, card in enumerate(cards, 1):
            left, top = round(card["x"] * 1080), round(card["y"] * 1350)
            require(pixels_rgba.getpixel((left + 18, top + 78)) == (36, 87, 200),
                    f"phone: metric_card_{index} is not cobalt")
            require(pixels_rgba.getpixel((left + 8, top + 5)) != (36, 87, 200),
                    f"phone: metric_card_{index} corner is too square")
            require(pixels_rgba.getpixel((left + 28, top + 8)) == (36, 87, 200),
                    f"phone: metric_card_{index} rounded top edge is malformed")
        require(pixels_rgba.getpixel((16, 1300)) == (49, 108, 255), "phone: CTA band is not cobalt")
        screen_button = [
            (x, y) for y in range(700, 880) for x in range(620, 1010)
            if (lambda pixel: pixel[2] > 180 and 70 < pixel[1] < 170 and pixel[0] < 70)(
                pixels_rgba.getpixel((x, y))
            )
        ]
        require(len(screen_button) > 5_000, "phone: crisp in-screen CTA is missing")
        screen_button_box = (
            min(point[0] for point in screen_button), min(point[1] for point in screen_button),
            max(point[0] for point in screen_button), max(point[1] for point in screen_button),
        )
        require(screen_button_box[2] - screen_button_box[0] > 260, "phone: in-screen CTA is too narrow")
        button_tops = {
            x: min(y for point_x, y in screen_button if point_x == x)
            for x in range(screen_button_box[0] + 45, screen_button_box[2] - 44)
        }
        require(max(button_tops.values()) - min(button_tops.values()) <= 2, "phone: in-screen CTA is perspective-warped")
    composed_device = compose_phone_device_asset(
        None, detail["content"]["phone_hero_title"], detail["content"]["cta"],
        detail["configuration"]["phone_screen"]["texture"],
    )
    with Image.open(BytesIO(composed_device["bytes"])) as image:
        device_pixels = image.convert("RGBA")
        for curve_pixel in ((146, 70), (1148, 70), (129, 80), (1165, 80)):
            pixel = device_pixels.getpixel(curve_pixel)
            require(pixel[3] == 255, "phone: outer background leaks into an upper screen corner")
            require(min(pixel[:3]) >= 245 and max(pixel[:3]) - min(pixel[:3]) <= 2,
                    "phone: upper screen corner is not covered by the app background")
    full_bleed_source = BytesIO()
    Image.new("RGBA", PHONE_SCREEN_ART_SIZE, "#6AAFC8").save(full_bleed_source, format="PNG")
    full_bleed_device = compose_phone_device_asset(
        full_bleed_source.getvalue(), detail["content"]["phone_hero_title"],
        detail["content"]["cta"],
        detail["configuration"]["phone_screen"]["texture"],
    )
    with Image.open(BytesIO(full_bleed_device["bytes"])) as image:
        device_pixels = image.convert("RGB")
        for edge_pixel in ((72, 900), (1221, 900)):
            red, green, blue = device_pixels.getpixel(edge_pixel)
            require(red < 125 and green > 160 and blue > 190,
                    "phone: hero artwork leaves a white gutter at a screen edge")
        for x in (160, 260, 1040, 1130):
            pixels = [device_pixels.getpixel((x, y)) for y in range(330, 356)]
            channel_steps = [
                max(abs(first - second) for first, second in zip(before, after))
                for before, after in zip(pixels, pixels[1:])
            ]
            require(max(channel_steps) <= 12,
                    "phone: hero artwork has a horizontal seam below the fixed header")
        screen_texture_colours = {
            device_pixels.getpixel((x, 1300))
            for x in range(300, 1000, 11)
        }
        screen_texture = detail["configuration"]["phone_screen"]["texture"]
        require(
            len(screen_texture_colours) <= 3 if screen_texture == "none"
            else len(screen_texture_colours) >= 3,
            "phone: in-screen hero texture pixels do not match the selected optional state",
        )
    require(detail["content"]["phone_hero_title"], "phone: audit fixture is missing the owner phone title")
    phone_asset = next(item for item in detail["assets"] if item["slot"] == "phone_screen")
    require(not phone_asset["available"], "phone: audit fixture unexpectedly supplied generated art")
    return {
        "name": name, "canvas": [preview["width"], preview["height"]],
        "eyebrow_enabled": detail["configuration"]["offer"]["enabled"],
        "background_texture": background_texture,
        "copy_background_texture": copy_background_texture,
        "phone_screen_texture": detail["configuration"]["phone_screen"]["texture"],
        "supporting_font_size": support["props"]["font_size"],
        "supporting_rendered_font_size": support["text_layout"]["font_size"],
        "supporting_highlight_color": support["props"]["highlight_color"],
        "device_visible_bounds": visible_device, "metric_row_y": cards[0]["y"],
        "cta_y": cta["y"], "checks": [
            "optional_background_texture", "optional_left_copy_texture",
            "natal_upper_left", "left_safe_copy", "front_facing_phone",
            "three_equal_cobalt_cards", "cobalt_cta_band", "no_clipping_or_overlap",
            "crisp_upright_natal_app_shell", "sealed_upper_screen_corners",
            "full_bleed_phone_hero", "continuous_header_phone_hero",
            "optional_phone_hero_texture", "optional_eyebrow_node", "no_generated_screen_text",
            "supporting_markup", "supporting_font_size", "supporting_word_colour",
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
        phone_content = copy.deepcopy(DEFAULT_PHONE_CONTENT)
        phone_content["supporting_text"] = (
            "Natal — **перевірені компанії**. Обирай і ==інвестуй від $5,000==."
        )
        phone_content["phone_hero_title"] = "ІНВЕСТУЙТЕ В МАЙБУТНІХ ЄДИНОРОГІВ"
        reference_phone_config = copy.deepcopy(DEFAULT_PHONE_CONFIG)
        reference_phone_config["copy_background"]["texture"] = "grain"
        phone = phone_workspace.save_configuration(
            base_sha256=phone["state_sha256"], configuration=reference_phone_config,
            content=phone_content,
        )
        phone_preview = phone_workspace.render_preview(state_sha256=phone["state_sha256"])
        phone_report = audit_phone_metrics(
            phone_preview, phone, name="phone_metrics_reference",
        )
        if output_dir is not None:
            phone_path = output_dir / "phone_metrics_reference.png"
            phone_path.write_bytes(phone_preview["bytes"])
            phone_report["preview_path"] = str(phone_path.resolve())
        reports.append(phone_report)
        hidden_phone_config = copy.deepcopy(DEFAULT_PHONE_CONFIG)
        hidden_phone_config["offer"]["enabled"] = False
        hidden_phone_config["background"]["texture"] = "grain"
        hidden_phone_config["copy_background"]["texture"] = "concrete"
        hidden_phone_config["phone_screen"]["texture"] = "paper"
        hidden_phone_config["supporting_text"] = {
            "font_size": 38,
            "highlight_color": "#C43A7A",
        }
        hidden_phone_preview = phone_workspace.render_preview(
            state_sha256=phone["state_sha256"], configuration=hidden_phone_config,
            content=phone_content,
        )
        hidden_phone_detail = copy.deepcopy(phone)
        hidden_phone_detail["configuration"] = hidden_phone_config
        hidden_phone_report = audit_phone_metrics(
            hidden_phone_preview, hidden_phone_detail,
            name="phone_metrics_without_eyebrow",
        )
        require(
            hidden_phone_preview["resolved"]["nodes"]["hero_title"]["box"]["y"]
            < phone_preview["resolved"]["nodes"]["hero_title"]["box"]["y"],
            "phone: removing the eyebrow did not reflow the headline",
        )
        hidden_phone_report["checks"].append("eyebrow_removed_and_headline_reflowed")
        if output_dir is not None:
            hidden_phone_path = output_dir / "phone_metrics_without_eyebrow.png"
            hidden_phone_path.write_bytes(hidden_phone_preview["bytes"])
            hidden_phone_report["preview_path"] = str(hidden_phone_path.resolve())
        reports.append(hidden_phone_report)
        for texture_name, outer_texture, copy_texture, screen_texture in (
            ("phone_metrics_travertine_frosted", "travertine", "travertine", "frosted"),
            ("phone_metrics_left_copy_concrete", "none", "concrete", "none"),
            ("phone_metrics_textures_off", "none", "none", "none"),
        ):
            texture_config = copy.deepcopy(DEFAULT_PHONE_CONFIG)
            texture_config["background"]["texture"] = outer_texture
            texture_config["copy_background"]["texture"] = copy_texture
            texture_config["phone_screen"]["texture"] = screen_texture
            texture_preview = phone_workspace.render_preview(
                state_sha256=phone["state_sha256"], configuration=texture_config,
                content=phone_content,
            )
            texture_detail = copy.deepcopy(phone)
            texture_detail["configuration"] = texture_config
            texture_report = audit_phone_metrics(
                texture_preview, texture_detail, name=texture_name,
            )
            if output_dir is not None:
                texture_path = output_dir / f"{texture_name}.png"
                texture_path.write_bytes(texture_preview["bytes"])
                texture_report["preview_path"] = str(texture_path.resolve())
            reports.append(texture_report)
    print(json.dumps({"status": "passed", "variants": reports}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
