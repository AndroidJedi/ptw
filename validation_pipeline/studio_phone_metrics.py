"""Bounded 4:5 phone-and-metrics Studio template.

The template is intentionally a fixed composition rather than a generic device
mock-up editor.  Its only mutable visual is a text-free phone-screen image;
the Natal lock-up, device frame, pose, copy geometry, statistic cards, and CTA
remain server-owned so a saved render is deterministic and reviewable.
"""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import random
import re
import textwrap
from typing import Any, Mapping

from .studio_primitives import PrimitiveTemplate


PHONE_METRICS_TEMPLATE_ID = "phone_metrics"
PHONE_METRICS_CONFIG_SCHEMA = "ptw.studio.phone-metrics-config.v1"
PHONE_METRICS_CONTENT_SCHEMA = "ptw.studio.phone-metrics-content.v1"
PHONE_METRICS_COMPONENT_SETTINGS_SCHEMA = "ptw.studio.phone-metrics-component-settings.v1"
PHONE_METRICS_TEMPLATE_VERSION = 1
PHONE_METRICS_CANVAS = (1080, 1350)
IPHONE_FRAME_PATH = Path(__file__).with_name("studio_assets") / "iphone-15-pro-black-perspective.png"
IPHONE_FRAME_SHA256 = "3766facd3f1ca3febb76875c69b76c2ba165ce875a0c8c5e33b657f2fd41b331"
# This is the owner-supplied perspective pose. Rendering it taller than its
# transparent bounding canvas preserves the 4:5 reference composition while
# keeping the visible right-side rail and angled screen plane.
IPHONE_RENDER_ASPECT = 1.74
# The aperture is a fixed inner quadrilateral of the checked-in pose. Screen
# art is masked here and then covered by the same static hardware bitmap.
IPHONE_SCREEN_POLYGON = ((548, 62), (956, 96), (602, 1176), (156, 1064))
IPHONE_SCREEN_BOX = (156, 62, 956, 1176)
IPHONE_FRAME_SOURCE = {
    "origin": "owner_supplied_mockup_adapted_v1",
    "source": "Owner-supplied angled iPhone mockup in the Studio request on 2026-09-03.",
    "transformation": "GPT Image edit to black hardware, then one-time local matte removal and aperture preparation.",
    "license": "Owner-authorized use in this Studio implementation; do not redistribute as a standalone frame.",
    "filename": IPHONE_FRAME_PATH.name,
    "sha256": IPHONE_FRAME_SHA256,
}

PHONE_ASSET_SLOTS: dict[str, dict[str, Any]] = {
    "phone_screen": {
        "role": "device_screen",
        "allowed_mime_types": ("image/png", "image/webp", "image/jpeg"),
        "description": "Text-free visual-only artwork rendered inside the fixed Natal phone frame.",
    },
}

PHONE_COMPONENTS: tuple[dict[str, Any], ...] = (
    {"component_id": "phone_metrics.background", "role": "background", "node_ids": ("canvas", "paper_texture"), "asset_slot_ids": (), "setting_ids": ()},
    {"component_id": "phone_metrics.brand", "role": "brand", "node_ids": ("logo",), "asset_slot_ids": (), "setting_ids": ()},
    {"component_id": "phone_metrics.offer", "role": "offer", "node_ids": ("offer",), "asset_slot_ids": (), "setting_ids": ("content.offer",)},
    {"component_id": "phone_metrics.hero_title", "role": "hero_title", "node_ids": ("hero_title",), "asset_slot_ids": (), "setting_ids": ("content.hero_title",)},
    {"component_id": "phone_metrics.supporting_text", "role": "supporting_text", "node_ids": ("supporting_text",), "asset_slot_ids": (), "setting_ids": ("content.supporting_text",)},
    {"component_id": "phone_metrics.device", "role": "device_mockup", "node_ids": ("phone_device",), "asset_slot_ids": ("phone_screen",), "setting_ids": ("content.phone_hero_title",)},
    {"component_id": "phone_metrics.metrics", "role": "metrics", "node_ids": ("metric_card_1", "metric_card_2", "metric_card_3", "metric_value_1", "metric_value_2", "metric_value_3", "metric_label_1", "metric_label_2", "metric_label_3"), "asset_slot_ids": (), "setting_ids": ("content.stats",)},
    {"component_id": "phone_metrics.cta", "role": "cta", "node_ids": ("cta",), "asset_slot_ids": (), "setting_ids": ("content.cta",)},
)

DEFAULT_PHONE_CONFIG: dict[str, Any] = {
    "schema": PHONE_METRICS_CONFIG_SCHEMA,
    "background": {"color": "#F4F5F2", "texture_intensity": 0.13},
    # The shared device asset is deliberately rendered as one layer.  Its
    # reference pose is baked into the owner-supplied frame, so its aperture
    # cannot move independently of the hardware or visible right-side rail.
    "device": {"x": 550, "y": 120, "width": 470, "rotation": 0.0},
}

DEFAULT_PHONE_CONTENT: dict[str, Any] = {
    "schema": PHONE_METRICS_CONTENT_SCHEMA,
    "offer": "NATAL",
    "hero_title": "Ваш головний меседж тут",
    "supporting_text": "Додайте коротке пояснення, яке допоможе зробити наступний крок.",
    "cta": "ДІЗНАТИСЯ БІЛЬШЕ",
    "stats": [
        {"value": "ВАШЕ", "label": "значення"},
        {"value": "ВАШЕ", "label": "значення"},
        {"value": "ВАШЕ", "label": "значення"},
    ],
    "phone_hero_title": "",
}

_COLOR = re.compile(r"#[0-9A-F]{6}")


def _canonical(value: Any) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def _object(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(f"{label} fields do not match the phone metrics contract")
    return value


def _number(value: Any, label: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized) or not minimum <= normalized <= maximum:
        raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}")
    return normalized


def _text(value: Any, label: str, minimum: int, maximum: int, *, allow_empty: bool = False) -> str:
    normalized = " ".join(str(value or "").split())
    if allow_empty and not normalized:
        return ""
    if not minimum <= len(normalized) <= maximum:
        raise ValueError(f"{label} must contain {minimum}-{maximum} characters")
    return normalized


def normalize_phone_metrics_config(value: Mapping[str, Any]) -> dict[str, Any]:
    root = _object(value, set(DEFAULT_PHONE_CONFIG), "Studio phone metrics configuration")
    if root["schema"] != PHONE_METRICS_CONFIG_SCHEMA:
        raise ValueError("Studio phone metrics configuration schema is invalid")
    background = _object(root["background"], set(DEFAULT_PHONE_CONFIG["background"]), "phone metrics background")
    device = _object(root["device"], set(DEFAULT_PHONE_CONFIG["device"]), "phone metrics device")
    color = str(background["color"]).upper()
    if not _COLOR.fullmatch(color):
        raise ValueError("phone metrics background.color must be a six-digit hex color")
    # Values are stored in the payload for reproducibility but normalized to
    # the sole approved composition; callers cannot turn this into a device
    # layout editor.
    return {
        "schema": PHONE_METRICS_CONFIG_SCHEMA,
        "background": {
            "color": color,
            "texture_intensity": _number(background["texture_intensity"], "phone metrics texture intensity", 0.04, 0.24),
        },
        "device": {
            "x": _number(device["x"], "phone metrics device.x", 530, 590),
            "y": _number(device["y"], "phone metrics device.y", 110, 180),
            "width": _number(device["width"], "phone metrics device.width", 440, 490),
            "rotation": _number(device["rotation"], "phone metrics device.rotation", 0.0, 0.0),
        },
    }


def normalize_phone_metrics_content(value: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, Mapping) and "schema" not in value:
        value = {"schema": PHONE_METRICS_CONTENT_SCHEMA, **dict(value)}
    root = _object(value, set(DEFAULT_PHONE_CONTENT), "Studio phone metrics content")
    if root["schema"] != PHONE_METRICS_CONTENT_SCHEMA:
        raise ValueError("Studio phone metrics content schema is invalid")
    raw_stats = root["stats"]
    if not isinstance(raw_stats, list) or len(raw_stats) != 3:
        raise ValueError("phone metrics content requires exactly three statistics")
    stats = []
    for index, item in enumerate(raw_stats, 1):
        stat = _object(item, {"value", "label"}, f"phone metrics stats[{index}]")
        stats.append({
            "value": _text(stat["value"], f"phone metrics stats[{index}].value", 1, 24),
            "label": _text(stat["label"], f"phone metrics stats[{index}].label", 1, 38),
        })
    return {
        "schema": PHONE_METRICS_CONTENT_SCHEMA,
        "offer": _text(root["offer"], "phone metrics offer", 1, 32),
        "hero_title": _text(root["hero_title"], "phone metrics hero_title", 1, 140),
        "supporting_text": _text(root["supporting_text"], "phone metrics supporting_text", 1, 220),
        "cta": _text(root["cta"], "phone metrics cta", 1, 60),
        "stats": stats,
        "phone_hero_title": _text(root["phone_hero_title"], "phone metrics phone_hero_title", 0, 72, allow_empty=True),
    }


def _node(node_id: str, kind: str, props: Mapping[str, Any], *, binding: tuple[str, str, bool] | None = None) -> dict[str, Any]:
    return {
        "id": node_id, "type": kind, "props": dict(props),
        "bindings": [] if binding is None else [{"target": binding[0], "source": binding[1], "required": binding[2]}],
        "constraints": [], "responsive": [], "children": [],
    }


def build_phone_metrics_template(config: Mapping[str, Any], content: Mapping[str, Any]) -> PrimitiveTemplate:
    config = normalize_phone_metrics_config(config)
    content = normalize_phone_metrics_content(content)
    width, height = PHONE_METRICS_CANVAS
    device = config["device"]
    device_height = round(float(device["width"]) * IPHONE_RENDER_ASPECT)
    cards_y, card_height, card_gap, card_x = 1002, 162, 28, 62
    card_width = round((width - card_x * 2 - card_gap * 2) / 3)
    children: list[dict[str, Any]] = [
        _node("paper_texture", "image", {
            "position": "absolute", "x": 0, "y": 0, "width": width, "height": height,
            "asset": "paper_texture", "fit": "cover", "opacity": config["background"]["texture_intensity"], "z_index": 1,
        }),
        _node("logo", "image", {
            "position": "absolute", "x": 68, "y": 72, "width": 198, "height": 82,
            "asset": "logo", "fit": "contain", "z_index": 10,
        }),
        _node("offer", "text", {
            "position": "absolute", "x": 70, "y": 212, "width": 430, "height": 40,
            "font_family": "Manrope", "font_size": 23, "min_font_size": 16, "font_weight": 800,
            "letter_spacing": 1.5, "color": "#101B31", "text_fit": "shrink", "max_lines": 1, "z_index": 6,
        }, binding=("text", "content.offer", True)),
        _node("hero_title", "text", {
            "position": "absolute", "x": 68, "y": 274, "width": 448, "height": 365,
            "font_family": "Manrope", "font_size": 76, "min_font_size": 42, "font_weight": 800,
            "line_height": 0.94, "letter_spacing": -2.5, "color": "#101B31", "text_fit": "shrink", "max_lines": 5, "z_index": 6,
        }, binding=("text", "content.hero_title", True)),
        _node("supporting_text", "text", {
            "position": "absolute", "x": 70, "y": 675, "width": 418, "height": 218,
            "font_family": "Manrope", "font_size": 29, "min_font_size": 19, "font_weight": 500,
            "line_height": 1.04, "letter_spacing": -0.8, "color": "#101B31", "text_fit": "shrink", "max_lines": 5, "z_index": 6,
        }, binding=("text", "content.supporting_text", True)),
        _node("phone_device", "image", {
            "position": "absolute", "x": device["x"], "y": device["y"], "width": device["width"], "height": device_height,
            "asset": "phone_device", "fit": "stretch", "rotation": device["rotation"], "transform_origin_x": 0.5,
            "transform_origin_y": 0.5, "z_index": 5,
        }),
    ]
    for index in range(3):
        x = card_x + index * (card_width + card_gap)
        children.extend([
            _node(f"metric_card_{index + 1}", "card", {
                "position": "absolute", "x": x, "y": cards_y, "width": card_width, "height": card_height,
                "background_color": "#2457C8", "radius": 17, "z_index": 8,
            }),
            _node(f"metric_value_{index + 1}", "text", {
                "position": "absolute", "x": x + 14, "y": cards_y + 25, "width": card_width - 28, "height": 54,
                "font_family": "Manrope", "font_size": 43, "min_font_size": 20, "font_weight": 800,
                "color": "#FFFFFF", "text_align": "center", "text_fit": "shrink", "max_lines": 1, "z_index": 9,
            }, binding=("text", f"content.stats_{index + 1}_value", True)),
            _node(f"metric_label_{index + 1}", "text", {
                "position": "absolute", "x": x + 18, "y": cards_y + 86, "width": card_width - 36, "height": 54,
                "font_family": "Manrope", "font_size": 22, "min_font_size": 14, "font_weight": 500,
                "line_height": 0.98, "color": "#FFFFFF", "text_align": "center", "text_fit": "shrink", "max_lines": 2, "z_index": 9,
            }, binding=("text", f"content.stats_{index + 1}_label", True)),
        ])
    children.append(_node("cta", "button", {
        "position": "absolute", "x": 0, "y": 1206, "width": width, "height": 144,
        "background_color": "#316CFF", "radius": 0, "label_color": "#FFFFFF", "font_family": "Manrope",
        "font_size": 34, "min_font_size": 20, "font_weight": 700, "text_align": "left", "vertical_align": "center",
        "text_fit": "shrink", "max_lines": 1, "padding": {"top": 22, "right": 64, "bottom": 22, "left": 68}, "z_index": 10,
    }, binding=("label", "content.cta", True)))
    document = {
        "schema": "ptw.studio.primitive-template.v1", "template_id": PHONE_METRICS_TEMPLATE_ID,
        "template_type": "phone_metrics", "version": PHONE_METRICS_TEMPLATE_VERSION, "status": "approved",
        "root": {"id": "canvas", "type": "frame", "props": {"width": width, "height": height, "background_color": config["background"]["color"], "overflow": "clip"}, "bindings": [], "constraints": [], "responsive": [], "children": children},
        "semantic_roles": {
            "background": ["canvas", "paper_texture"], "brand": ["logo"], "offer": ["offer"],
            "hero_title": ["hero_title"], "supporting_text": ["supporting_text"], "device_mockup": ["phone_device"],
            "metrics": ["metric_card_1", "metric_card_2", "metric_card_3"], "cta": ["cta"],
        },
        "assets": {
            "logo": {"kind": "image", "allowed_mime_types": ["image/png"], "required": True, "provenance": "Canonical Natal brand lock-up."},
            "paper_texture": {"kind": "image", "allowed_mime_types": ["image/png"], "required": True, "provenance": "Deterministic low-intensity paper/mineral texture."},
            "phone_device": {"kind": "image", "allowed_mime_types": ["image/png"], "required": True, "provenance": "Server-composited fixed black iPhone frame and text-free screen artwork."},
        },
        "rules": [
            *[{"id": f"role_{role}", "scope": "template", "type": "required_role", "params": {"role": role}} for role in ("background", "brand", "offer", "hero_title", "supporting_text", "device_mockup", "metrics", "cta")],
            {"id": "fixed_tree", "scope": "template", "type": "max_nodes", "params": {"maximum": 18}},
        ],
        "provenance": {"base_template_id": None, "base_version": None, "base_sha256": None, "reference_ids": ["owner-reference-phone-metrics-v1"], "change_note": "Natal phone-and-metrics composition with fixed device pose."},
    }
    return PrimitiveTemplate.from_dict(document)


def phone_metrics_semantic_data(config: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, str]:
    normalize_phone_metrics_config(config)
    normalized = normalize_phone_metrics_content(content)
    result = {
        "content.offer": normalized["offer"], "content.hero_title": normalized["hero_title"],
        "content.supporting_text": normalized["supporting_text"], "content.cta": normalized["cta"],
    }
    for index, stat in enumerate(normalized["stats"], 1):
        result[f"content.stats_{index}_value"] = stat["value"]
        result[f"content.stats_{index}_label"] = stat["label"]
    return result


def phone_metrics_component_settings(config: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
    config = normalize_phone_metrics_config(config)
    content = normalize_phone_metrics_content(content)
    values = {
        "content.offer": content["offer"], "content.hero_title": content["hero_title"],
        "content.supporting_text": content["supporting_text"], "content.cta": content["cta"],
        "content.stats": deepcopy(content["stats"]), "content.phone_hero_title": content["phone_hero_title"],
    }
    value = {
        "schema": PHONE_METRICS_COMPONENT_SETTINGS_SCHEMA, "template_id": PHONE_METRICS_TEMPLATE_ID,
        "template_version": PHONE_METRICS_TEMPLATE_VERSION, "configuration_schema": PHONE_METRICS_CONFIG_SCHEMA,
        "components": [{
            "component_id": component["component_id"], "role": component["role"],
            "node_ids": list(component["node_ids"]), "asset_slot_ids": list(component["asset_slot_ids"]),
            "settings": [{"setting_id": item, "value": deepcopy(values[item])} for item in component["setting_ids"]],
        } for component in PHONE_COMPONENTS],
    }
    _, digest = _canonical(value)
    return {**value, "sha256": digest}


def phone_metrics_catalog() -> dict[str, Any]:
    value = {
        "schema": "ptw.studio.phone-metrics-catalog.v1", "template_id": PHONE_METRICS_TEMPLATE_ID,
        "template_version": PHONE_METRICS_TEMPLATE_VERSION, "canvas": {"width": 1080, "height": 1350},
        "semantic_roles": [item["role"] for item in PHONE_COMPONENTS],
        "components": [{
            "component_id": item["component_id"], "role": item["role"], "node_ids": list(item["node_ids"]),
            "asset_slot_ids": list(item["asset_slot_ids"]), "setting_ids": list(item["setting_ids"]),
        } for item in PHONE_COMPONENTS],
        "asset_slots": {key: {"role": item["role"], "allowed_mime_types": list(item["allowed_mime_types"]), "description": item["description"]} for key, item in PHONE_ASSET_SLOTS.items()},
        "variation": {
            "optional_elements": [], "brand": "Natal",
            "device_pose": "baked_perspective_right_rail",
            "device_rotation_degrees": 0.0,
        },
    }
    _, digest = _canonical(value)
    return {**value, "sha256": digest}


def iphone_frame_bytes() -> bytes:
    try:
        data = IPHONE_FRAME_PATH.read_bytes()
    except OSError as error:
        raise RuntimeError("The checked-in iPhone frame is unavailable") from error
    if hashlib.sha256(data).hexdigest() != IPHONE_FRAME_SHA256:
        raise RuntimeError("The checked-in iPhone frame digest does not match its manifest")
    return data


def iphone_frame_record() -> dict[str, Any]:
    from .studio import inspect_media

    data = iphone_frame_bytes()
    inspected = inspect_media(data, "image/png")
    return {"mime_type": "image/png", "sha256": IPHONE_FRAME_SHA256, "byte_count": len(data), "width": inspected["width"], "height": inspected["height"], "source": deepcopy(IPHONE_FRAME_SOURCE), "bytes": data}


def _fallback_screen() -> bytes:
    """Neutral non-text fallback used only in standalone Studio before upload."""
    from PIL import Image, ImageDraw, ImageFilter

    image = Image.new("RGBA", (832, 1792), "#F9FAFA")
    draw = ImageDraw.Draw(image, "RGBA")
    rng = random.Random("natal-phone-screen-art-v1")
    for _ in range(14):
        x, y = rng.randint(40, 790), rng.randint(120, 1660)
        radius = rng.randint(42, 165)
        shade = rng.choice(((20, 29, 47, 220), (55, 64, 79, 190), (228, 244, 57, 225)))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=shade)
    image = image.filter(ImageFilter.GaussianBlur(15))
    output = BytesIO(); image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def compose_phone_device_asset(screen_data: bytes | None, phone_title: str) -> dict[str, Any]:
    """Fuse the fixed perspective frame, screen art, and optional owner title.

    The fuse is deliberately server-side: a mutable screen image cannot be
    moved independently from the checked-in frame, and the only text inside
    the device is renderer-owned owner copy rather than generated typography.
    """
    from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

    frame_data = iphone_frame_bytes()
    with Image.open(BytesIO(frame_data)) as source:
        frame = source.convert("RGBA")
    resolved_screen = screen_data or _fallback_screen()
    try:
        with Image.open(BytesIO(resolved_screen)) as source:
            screen = source.convert("RGBA")
    except Exception as error:
        raise ValueError("phone screen artwork cannot be decoded") from error
    screen_size = (
        IPHONE_SCREEN_BOX[2] - IPHONE_SCREEN_BOX[0],
        IPHONE_SCREEN_BOX[3] - IPHONE_SCREEN_BOX[1],
    )
    screen = ImageOps.fit(screen, screen_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    mask = Image.new("L", frame.size, 0)
    ImageDraw.Draw(mask).polygon(IPHONE_SCREEN_POLYGON, fill=255)
    screen_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    screen_layer.alpha_composite(screen, IPHONE_SCREEN_BOX[:2])
    screen_layer.putalpha(ImageChops.multiply(screen_layer.getchannel("A"), mask))
    if phone_title:
        try:
            font = ImageFont.truetype(str(Path(__file__).with_name("studio_assets") / "fonts" / "Manrope-Variable.ttf"), 38)
        except OSError:
            font = ImageFont.load_default()
        draw = ImageDraw.Draw(screen_layer)
        # The validation contract limits the source to 72 characters.  Three
        # fixed rows at this font size stay within the lower aperture even for
        # a long unbroken owner-entered word.
        text = "\n".join(textwrap.wrap(
            phone_title.upper(), width=23, break_long_words=True, break_on_hyphens=False,
        )[:3])
        # This bounded owner label occupies a fixed lower-screen region and is
        # intentionally kept out of the image-generation prompt.
        draw.multiline_text((560, 865), text, font=font, fill="#101B31", spacing=6, align="center", anchor="ma")
    # The frame contains its own right rail.  Composite it after the masked
    # screen so the aperture, hardware edge, and supplied perspective always
    # remain one downstream image layer.
    screen_layer.alpha_composite(frame)
    output = BytesIO(); screen_layer.save(output, format="PNG", optimize=False)
    data = output.getvalue()
    return {"bytes": data, "mime_type": "image/png", "source": {"origin": "server_composited_fixed_phone", "frame_sha256": IPHONE_FRAME_SHA256, "screen_sha256": hashlib.sha256(resolved_screen).hexdigest()}}
