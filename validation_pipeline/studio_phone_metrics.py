"""Bounded 4:5 phone-and-metrics Studio template.

The template is intentionally a fixed composition rather than a generic device
mock-up editor. Its only mutable visual is text-free hero artwork inside a
fixed app shell; the Natal lock-up, device frame, pose, copy geometry,
statistic cards, and CTA remain server-owned so a saved render is deterministic
and reviewable.
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
from typing import Any, Mapping

from .studio_primitives import PrimitiveTemplate


PHONE_METRICS_TEMPLATE_ID = "phone_metrics"
PHONE_METRICS_CONFIG_SCHEMA = "ptw.studio.phone-metrics-config.v5"
_LEGACY_PHONE_METRICS_CONFIG_SCHEMAS = frozenset({
    "ptw.studio.phone-metrics-config.v1",
    "ptw.studio.phone-metrics-config.v2",
    "ptw.studio.phone-metrics-config.v3",
    "ptw.studio.phone-metrics-config.v4",
})
PHONE_METRICS_CONTENT_SCHEMA = "ptw.studio.phone-metrics-content.v1"
PHONE_METRICS_COMPONENT_SETTINGS_SCHEMA = "ptw.studio.phone-metrics-component-settings.v1"
PHONE_METRICS_TEMPLATE_VERSION = 10
PHONE_METRICS_CANVAS = (1080, 1350)
PHONE_BACKGROUND_TEXTURES = ("none", "grain", "concrete", "travertine")
PHONE_COPY_BACKGROUND_TEXTURES = PHONE_BACKGROUND_TEXTURES
PHONE_SCREEN_TEXTURES = ("none", "grain", "paper", "frosted")
IPHONE_FRAME_PATH = Path(__file__).with_name("studio_assets") / "iphone-15-pro-black.png"
IPHONE_FRAME_SHA256 = "04164c10370930494f2688acc6fcf65a222cd7da077c5c65c4d189ab3e083dc0"
# The earlier WithFrame asset is a true front pose. Its native aspect ratio is
# retained so the renderer never stretches the hardware or the screen UI.
IPHONE_RENDER_ASPECT = 2656 / 1293
# This rounded rectangle follows the transparent front aperture with a
# ten-pixel under-bezel overbleed. The overbleed prevents the outer canvas from
# showing through the frame's antialiased upper corners after downscaling.
IPHONE_SCREEN_BOX = (58, 50, 1236, 2606)
IPHONE_SCREEN_RADIUS = 160
PHONE_SCREEN_ART_SIZE = (832, 1792)
IPHONE_FRAME_SOURCE = {
    "origin": "withframe_static_front_mockup_v1",
    "source": "WithFrame iPhone 15 Pro black front mockup downloaded once on 2026-09-03.",
    "source_url": "https://withfra.me/shot/iphone-15-pro",
    "download_url": "https://shot.withfra.me/frames/iphone.15.pro/black",
    "license_url": "https://withfra.me/shot/iphone-15-pro",
    "transformation": "None to the hardware frame; the renderer composites the app screen behind its transparent aperture.",
    "license": "Personal and commercial use permitted; owner-authorized for bundled Studio use; do not redistribute or sell the frame standalone.",
    "filename": IPHONE_FRAME_PATH.name,
    "sha256": IPHONE_FRAME_SHA256,
}

PHONE_ASSET_SLOTS: dict[str, dict[str, Any]] = {
    "phone_screen": {
        "role": "device_screen",
        "allowed_mime_types": ("image/png", "image/webp", "image/jpeg"),
        "description": "Brief-derived text-free hero artwork inside the fixed Natal app screen and phone frame.",
    },
}

PHONE_COMPONENTS: tuple[dict[str, Any], ...] = (
    {"component_id": "phone_metrics.background", "role": "background", "node_ids": ("canvas", "background_texture", "copy_background_texture"), "asset_slot_ids": (), "setting_ids": ("configuration.background.texture", "configuration.copy_background.texture")},
    {"component_id": "phone_metrics.brand", "role": "brand", "node_ids": ("logo",), "asset_slot_ids": (), "setting_ids": ()},
    {"component_id": "phone_metrics.offer", "role": "offer", "node_ids": ("offer",), "asset_slot_ids": (), "setting_ids": ("configuration.offer.enabled", "content.offer")},
    {"component_id": "phone_metrics.hero_title", "role": "hero_title", "node_ids": ("hero_title",), "asset_slot_ids": (), "setting_ids": ("content.hero_title",)},
    {"component_id": "phone_metrics.supporting_text", "role": "supporting_text", "node_ids": ("supporting_text",), "asset_slot_ids": (), "setting_ids": ("configuration.supporting_text.font_size", "configuration.supporting_text.highlight_color", "content.supporting_text")},
    {"component_id": "phone_metrics.device", "role": "device_mockup", "node_ids": ("phone_device",), "asset_slot_ids": ("phone_screen",), "setting_ids": ("configuration.phone_screen.texture", "content.phone_hero_title")},
    {"component_id": "phone_metrics.metrics", "role": "metrics", "node_ids": ("metric_card_1", "metric_card_2", "metric_card_3", "metric_value_1", "metric_value_2", "metric_value_3", "metric_label_1", "metric_label_2", "metric_label_3"), "asset_slot_ids": (), "setting_ids": ("content.stats",)},
    {"component_id": "phone_metrics.cta", "role": "cta", "node_ids": ("cta",), "asset_slot_ids": (), "setting_ids": ("content.cta",)},
)

DEFAULT_PHONE_CONFIG: dict[str, Any] = {
    "schema": PHONE_METRICS_CONFIG_SCHEMA,
    "background": {
        "color": "#F4F5F2", "texture": "concrete", "texture_intensity": 0.13,
    },
    "copy_background": {"texture": "none"},
    "offer": {"enabled": True},
    "supporting_text": {"font_size": 29, "highlight_color": "#1675F8"},
    "phone_screen": {"texture": "grain"},
    # The fixed front frame and app screen are rendered as one layer. The pose
    # keeps readable UI in the upper-right without colliding with left copy.
    "device": {"x": 610, "y": 90, "width": 410, "rotation": 0.0},
}
DEFAULT_PHONE_TEXTURE_CHOICES = {
    "background": DEFAULT_PHONE_CONFIG["background"]["texture"],
    "copy_background": DEFAULT_PHONE_CONFIG["copy_background"]["texture"],
    "phone_screen": DEFAULT_PHONE_CONFIG["phone_screen"]["texture"],
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


def _enum(value: Any, allowed: tuple[str, ...], label: str) -> str:
    normalized = str(value)
    if normalized not in allowed:
        raise ValueError(f"{label} is not an approved option")
    return normalized


def _text(value: Any, label: str, minimum: int, maximum: int, *, allow_empty: bool = False) -> str:
    normalized = " ".join(str(value or "").split())
    if allow_empty and not normalized:
        return ""
    if not minimum <= len(normalized) <= maximum:
        raise ValueError(f"{label} must contain {minimum}-{maximum} characters")
    return normalized


def normalize_phone_metrics_config(value: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, Mapping) and value.get("schema") in _LEGACY_PHONE_METRICS_CONFIG_SCHEMAS:
        # Existing mutable v1-v4 drafts predate one or more optional controls.
        # Upgrade them in memory with the previously implicit values;
        # immutable version JSON remains untouched.
        value = dict(value)
        value.setdefault("offer", {"enabled": True})
        value.setdefault("supporting_text", deepcopy(DEFAULT_PHONE_CONFIG["supporting_text"]))
        background = dict(value.get("background") or {})
        background.setdefault("texture", DEFAULT_PHONE_CONFIG["background"]["texture"])
        value["background"] = background
        value.setdefault("copy_background", deepcopy(DEFAULT_PHONE_CONFIG["copy_background"]))
        value.setdefault("phone_screen", deepcopy(DEFAULT_PHONE_CONFIG["phone_screen"]))
        value["schema"] = PHONE_METRICS_CONFIG_SCHEMA
    root = _object(value, set(DEFAULT_PHONE_CONFIG), "Studio phone metrics configuration")
    if root["schema"] != PHONE_METRICS_CONFIG_SCHEMA:
        raise ValueError("Studio phone metrics configuration schema is invalid")
    background = _object(root["background"], set(DEFAULT_PHONE_CONFIG["background"]), "phone metrics background")
    offer = _object(root["offer"], set(DEFAULT_PHONE_CONFIG["offer"]), "phone metrics offer")
    copy_background = _object(
        root["copy_background"], set(DEFAULT_PHONE_CONFIG["copy_background"]),
        "phone metrics copy background",
    )
    supporting_text = _object(
        root["supporting_text"], set(DEFAULT_PHONE_CONFIG["supporting_text"]),
        "phone metrics supporting text",
    )
    phone_screen = _object(
        root["phone_screen"], set(DEFAULT_PHONE_CONFIG["phone_screen"]),
        "phone metrics phone screen",
    )
    device = _object(root["device"], set(DEFAULT_PHONE_CONFIG["device"]), "phone metrics device")
    color = str(background["color"]).upper()
    if not _COLOR.fullmatch(color):
        raise ValueError("phone metrics background.color must be a six-digit hex color")
    if not isinstance(offer["enabled"], bool):
        raise ValueError("phone metrics offer.enabled must be boolean")
    highlight_color = str(supporting_text["highlight_color"]).upper()
    if not _COLOR.fullmatch(highlight_color):
        raise ValueError("phone metrics supporting_text.highlight_color must be a six-digit hex color")
    # Values are stored in the payload for reproducibility but normalized to
    # the sole approved composition; callers cannot turn this into a device
    # layout editor.
    return {
        "schema": PHONE_METRICS_CONFIG_SCHEMA,
        "background": {
            "color": color,
            "texture": _enum(
                background["texture"], PHONE_BACKGROUND_TEXTURES,
                "phone metrics background.texture",
            ),
            "texture_intensity": _number(background["texture_intensity"], "phone metrics texture intensity", 0.04, 0.24),
        },
        "copy_background": {
            "texture": _enum(
                copy_background["texture"], PHONE_COPY_BACKGROUND_TEXTURES,
                "phone metrics copy_background.texture",
            ),
        },
        "offer": {"enabled": offer["enabled"]},
        "supporting_text": {
            "font_size": _number(
                supporting_text["font_size"],
                "phone metrics supporting_text.font_size", 20, 38,
            ),
            "highlight_color": highlight_color,
        },
        "phone_screen": {
            "texture": _enum(
                phone_screen["texture"], PHONE_SCREEN_TEXTURES,
                "phone metrics phone_screen.texture",
            ),
        },
        "device": {
            "x": _number(device["x"], "phone metrics device.x", 580, 640),
            "y": _number(device["y"], "phone metrics device.y", 70, 130),
            "width": _number(device["width"], "phone metrics device.width", 380, 430),
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


def normalize_phone_metrics_texture_choices(value: Mapping[str, Any]) -> dict[str, str]:
    if isinstance(value, Mapping) and set(value) == {"background", "phone_screen"}:
        value = {**dict(value), "copy_background": "none"}
    root = _object(
        value, set(DEFAULT_PHONE_TEXTURE_CHOICES), "phone metrics texture choices",
    )
    return {
        "background": _enum(
            root["background"], PHONE_BACKGROUND_TEXTURES,
            "phone metrics background texture choice",
        ),
        "copy_background": _enum(
            root["copy_background"], PHONE_COPY_BACKGROUND_TEXTURES,
            "phone metrics copy-background texture choice",
        ),
        "phone_screen": _enum(
            root["phone_screen"], PHONE_SCREEN_TEXTURES,
            "phone metrics phone-screen texture choice",
        ),
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
    # The cards deliberately occupy less of the canvas than the prior row and
    # use a larger radius for a softer, smoother silhouette.
    cards_y, card_height, card_gap, card_x, card_width = 1022, 140, 28, 92, 280
    children: list[dict[str, Any]] = [
        _node("logo", "image", {
            "position": "absolute", "x": 68, "y": 72, "width": 198, "height": 82,
            "asset": "logo", "fit": "contain", "z_index": 10,
        }),
        _node("hero_title", "text", {
            "position": "absolute", "x": 68, "y": 274 if config["offer"]["enabled"] else 212,
            "width": 448, "height": 365 if config["offer"]["enabled"] else 427,
            "font_family": "Manrope", "font_size": 76, "min_font_size": 42, "font_weight": 800,
            "line_height": 0.94, "letter_spacing": -2.5, "color": "#101B31", "text_fit": "shrink", "max_lines": 5, "z_index": 6,
        }, binding=("text", "content.hero_title", True)),
        _node("supporting_text", "rich_text", {
            "position": "absolute", "x": 70, "y": 675, "width": 418, "height": 218,
            "font_family": "Manrope", "font_size": config["supporting_text"]["font_size"],
            "min_font_size": 20, "font_weight": 500, "bold_weight": 800,
            "highlight_color": config["supporting_text"]["highlight_color"],
            "line_height": 1.04, "letter_spacing": -0.8, "color": "#101B31", "text_fit": "shrink", "max_lines": 5, "z_index": 6,
        }, binding=("text", "content.supporting_text", True)),
        _node("phone_device", "image", {
            "position": "absolute", "x": device["x"], "y": device["y"], "width": device["width"], "height": device_height,
            "asset": "phone_device", "fit": "stretch", "rotation": device["rotation"], "transform_origin_x": 0.5,
            "transform_origin_y": 0.5, "z_index": 5,
        }),
    ]
    if config["background"]["texture"] != "none":
        children.insert(0, _node("background_texture", "image", {
            "position": "absolute", "x": 0, "y": 0,
            "width": width, "height": height, "asset": "background_texture",
            "fit": "cover", "opacity": config["background"]["texture_intensity"],
            "z_index": 1,
        }))
    if config["copy_background"]["texture"] != "none":
        children.insert(1 if config["background"]["texture"] != "none" else 0, _node(
            "copy_background_texture", "image", {
                "position": "absolute", "x": 42, "y": 54,
                "width": 506, "height": 864,
                "asset": "copy_background_texture", "fit": "cover",
                "mask": "rounded_rect", "radius": 58,
                "opacity": 0.32, "z_index": 2,
            },
        ))
    if config["offer"]["enabled"]:
        children.insert(2, _node("offer", "text", {
            "position": "absolute", "x": 70, "y": 212, "width": 430, "height": 40,
            "font_family": "Manrope", "font_size": 23, "min_font_size": 16, "font_weight": 800,
            "letter_spacing": 1.5, "color": "#101B31", "text_fit": "shrink", "max_lines": 1, "z_index": 6,
        }, binding=("text", "content.offer", True)))
    for index in range(3):
        x = card_x + index * (card_width + card_gap)
        children.extend([
            _node(f"metric_card_{index + 1}", "card", {
                "position": "absolute", "x": x, "y": cards_y, "width": card_width, "height": card_height,
                "background_color": "#2457C8", "radius": 28, "z_index": 8,
            }),
            _node(f"metric_value_{index + 1}", "text", {
                "position": "absolute", "x": x + 14, "y": cards_y + 18, "width": card_width - 28, "height": 50,
                "font_family": "Manrope", "font_size": 43, "min_font_size": 20, "font_weight": 800,
                "color": "#FFFFFF", "text_align": "center", "text_fit": "shrink", "max_lines": 1, "z_index": 9,
            }, binding=("text", f"content.stats_{index + 1}_value", True)),
            _node(f"metric_label_{index + 1}", "text", {
                "position": "absolute", "x": x + 18, "y": cards_y + 75, "width": card_width - 36, "height": 48,
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
            "background": ["canvas", *(
                ["background_texture"]
                if config["background"]["texture"] != "none" else []
            ), *(
                ["copy_background_texture"]
                if config["copy_background"]["texture"] != "none" else []
            )], "brand": ["logo"], "offer": ["offer"],
            "hero_title": ["hero_title"], "supporting_text": ["supporting_text"], "device_mockup": ["phone_device"],
            "metrics": ["metric_card_1", "metric_card_2", "metric_card_3"], "cta": ["cta"],
        },
        "assets": {
            "logo": {"kind": "image", "allowed_mime_types": ["image/png"], "required": True, "provenance": "Canonical Natal brand lock-up."},
            "phone_device": {"kind": "image", "allowed_mime_types": ["image/png"], "required": True, "provenance": "Server-composited fixed front-facing black iPhone, crisp Natal app shell, and text-free hero artwork."},
            **({
                "background_texture": {
                    "kind": "image", "allowed_mime_types": ["image/png"],
                    "required": True,
                    "provenance": "Deterministic optional grain or mineral texture.",
                },
            } if config["background"]["texture"] != "none" else {}),
            **({
                "copy_background_texture": {
                    "kind": "image", "allowed_mime_types": ["image/png"],
                    "required": True,
                    "provenance": "Deterministic optional texture bounded to the left copy area.",
                },
            } if config["copy_background"]["texture"] != "none" else {}),
        },
        "rules": [
            *[{"id": f"role_{role}", "scope": "template", "type": "required_role", "params": {"role": role}} for role in ("background", "brand", "hero_title", "supporting_text", "device_mockup", "metrics", "cta")],
            {"id": "fixed_tree", "scope": "template", "type": "max_nodes", "params": {"maximum": 18}},
        ],
        "provenance": {"base_template_id": None, "base_version": None, "base_sha256": None, "reference_ids": ["owner-reference-phone-metrics-v1"], "change_note": "Natal phone-and-metrics v10 with independent optional full-canvas, left-copy-area, and in-phone hero textures, compact rounded metric cards, an optional eyebrow, and bounded supporting-copy formatting."},
    }
    if not config["offer"]["enabled"]:
        document["semantic_roles"].pop("offer")
    return PrimitiveTemplate.from_dict(document)


def phone_metrics_semantic_data(config: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, str]:
    config = normalize_phone_metrics_config(config)
    normalized = normalize_phone_metrics_content(content)
    result = {
        "content.hero_title": normalized["hero_title"],
        "content.supporting_text": normalized["supporting_text"], "content.cta": normalized["cta"],
    }
    if config["offer"]["enabled"]:
        result["content.offer"] = normalized["offer"]
    for index, stat in enumerate(normalized["stats"], 1):
        result[f"content.stats_{index}_value"] = stat["value"]
        result[f"content.stats_{index}_label"] = stat["label"]
    return result


def phone_metrics_component_settings(config: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
    config = normalize_phone_metrics_config(config)
    content = normalize_phone_metrics_content(content)
    values = {
        "configuration.background.texture": config["background"]["texture"],
        "configuration.copy_background.texture": config["copy_background"]["texture"],
        "configuration.offer.enabled": config["offer"]["enabled"],
        "configuration.supporting_text.font_size": config["supporting_text"]["font_size"],
        "configuration.supporting_text.highlight_color": config["supporting_text"]["highlight_color"],
        "configuration.phone_screen.texture": config["phone_screen"]["texture"],
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
            "optional_elements": ["offer"], "brand": "Natal",
            "device_pose": "front_facing_upright",
            "device_rotation_degrees": 0.0,
            "background_textures": list(PHONE_BACKGROUND_TEXTURES),
            "copy_background_textures": list(PHONE_COPY_BACKGROUND_TEXTURES),
            "phone_screen_textures": list(PHONE_SCREEN_TEXTURES),
            "supporting_text_font_size": {"minimum": 20, "maximum": 38, "default": 29},
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
    """Polished non-text hero art used only in standalone Studio previews."""
    from PIL import Image, ImageDraw, ImageFilter

    image = Image.new("RGBA", PHONE_SCREEN_ART_SIZE, "#F8FAF9")
    backdrop = Image.new("RGBA", image.size, (0, 0, 0, 0))
    backdrop_draw = ImageDraw.Draw(backdrop, "RGBA")
    rng = random.Random("natal-phone-screen-art-v2")
    for _ in range(7):
        x, y = rng.randint(80, 760), rng.randint(240, 1280)
        radius = rng.randint(120, 270)
        color = rng.choice(((61, 77, 101, 30), (109, 210, 225, 28), (227, 244, 62, 35)))
        backdrop_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    image.alpha_composite(backdrop.filter(ImageFilter.GaussianBlur(90)))

    def sphere(center: tuple[int, int], radius: int, color: tuple[int, int, int]) -> None:
        shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow, "RGBA").ellipse(
            (center[0] - radius + 25, center[1] - radius + 38,
             center[0] + radius + 25, center[1] + radius + 38),
            fill=(15, 24, 39, 95),
        )
        image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(48)))
        body = Image.new("RGBA", image.size, (0, 0, 0, 0))
        body_draw = ImageDraw.Draw(body, "RGBA")
        body_draw.ellipse(
            (center[0] - radius, center[1] - radius,
             center[0] + radius, center[1] + radius),
            fill=(*color, 255),
        )
        highlight = Image.new("RGBA", image.size, (0, 0, 0, 0))
        ImageDraw.Draw(highlight, "RGBA").ellipse(
            (center[0] - radius * .72, center[1] - radius * .76,
             center[0] - radius * .05, center[1] - radius * .08),
            fill=(255, 255, 255, 92),
        )
        body.alpha_composite(highlight.filter(ImageFilter.GaussianBlur(max(18, radius // 5))))
        image.alpha_composite(body)

    # A deliberate sculptural cluster mirrors the reference's material depth
    # while remaining generic enough for a standalone Studio preview.
    sphere((580, 480), 172, (32, 39, 51))
    sphere((640, 700), 150, (49, 57, 71))
    sphere((430, 770), 132, (24, 31, 43))
    sphere((645, 915), 112, (229, 244, 57))
    sphere((280, 585), 72, (228, 244, 57))
    output = BytesIO(); image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _screen_font(size: int, weight: int):
    from PIL import ImageFont

    path = Path(__file__).with_name("studio_assets") / "fonts" / "Manrope-Variable.ttf"
    try:
        font = ImageFont.truetype(str(path), size)
        try:
            axes = []
            for axis in font.get_variation_axes():
                name = bytes(axis["name"]).decode("ascii", "ignore").lower()
                axes.append(weight if "weight" in name else axis["default"])
            font.set_variation_by_axes(axes)
        except (AttributeError, KeyError, OSError, TypeError, ValueError):
            pass
        return font
    except OSError:
        return ImageFont.load_default()


def _wrapped_lines(draw: Any, value: str, font: Any, max_width: int) -> list[str]:
    """Wrap owner copy by visible width, including long unbroken words."""

    lines: list[str] = []
    current = ""
    for word in value.split():
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        fragment = ""
        for character in word:
            candidate = fragment + character
            if fragment and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
                lines.append(fragment)
                fragment = character
            else:
                fragment = candidate
        current = fragment
    if current:
        lines.append(current)
    return lines


def _draw_fitted_screen_text(
    draw: Any, value: str, box: tuple[int, int, int, int], *,
    maximum_size: int, minimum_size: int, weight: int, fill: str,
    max_lines: int, spacing: int = 8,
) -> None:
    if not value:
        return
    max_width = box[2] - box[0]
    max_height = box[3] - box[1]
    fitted: tuple[Any, list[str], int] | None = None
    for size in range(maximum_size, minimum_size - 1, -2):
        font = _screen_font(size, weight)
        lines = _wrapped_lines(draw, value, font, max_width)
        if len(lines) > max_lines:
            continue
        text = "\n".join(lines)
        bounds = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center")
        if bounds[2] - bounds[0] <= max_width and bounds[3] - bounds[1] <= max_height:
            fitted = (font, lines, size)
            break
    if fitted is None:
        font = _screen_font(minimum_size, weight)
        lines = _wrapped_lines(draw, value, font, max_width)
        fitted = (font, lines[:max_lines], minimum_size)
    font, lines, _ = fitted
    draw.multiline_text(
        ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2),
        "\n".join(lines), font=font, fill=fill, spacing=spacing,
        align="center", anchor="mm",
    )


def _phone_hero_texture(size: tuple[int, int], preset: str):
    """Build one subtle deterministic overlay for the text-free hero area."""

    from PIL import Image, ImageDraw, ImageFilter

    preset = _enum(preset, PHONE_SCREEN_TEXTURES, "phone screen texture")
    if preset == "none":
        return Image.new("RGBA", size, (0, 0, 0, 0))
    rng = random.Random(f"natal-phone-screen-texture-{preset}-v1")
    if preset == "grain":
        source_size = (104, max(1, math.ceil(size[1] / 8)))
        texture = Image.new("RGBA", source_size)
        texture.putdata([
            (16, 25, 40, rng.randint(3, 11))
            if rng.random() < .54
            else (255, 255, 255, rng.randint(2, 9))
            for _ in range(source_size[0] * source_size[1])
        ])
        return texture.resize(size, Image.Resampling.BILINEAR)
    if preset == "paper":
        source_size = (208, max(1, math.ceil(size[1] / 4)))
        texture = Image.new("RGBA", source_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(texture, "RGBA")
        for _ in range(1250):
            x, y = rng.randrange(source_size[0]), rng.randrange(source_size[1])
            length = rng.randint(2, 14)
            tone = rng.choice((24, 54, 218, 245))
            draw.line(
                (x, y, min(source_size[0] - 1, x + length), y + rng.choice((-1, 0, 1))),
                fill=(tone, tone, tone, rng.randint(3, 14)), width=1,
            )
        return texture.resize(size, Image.Resampling.BILINEAR)
    source_size = (72, max(1, math.ceil(size[1] / 12)))
    texture = Image.new("RGBA", source_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(texture, "RGBA")
    for _ in range(95):
        x, y = rng.randrange(source_size[0]), rng.randrange(source_size[1])
        radius_x, radius_y = rng.randint(4, 18), rng.randint(5, 24)
        tone = rng.choice((20, 48, 224, 255))
        draw.ellipse(
            (x - radius_x, y - radius_y, x + radius_x, y + radius_y),
            fill=(tone, tone, tone, rng.randint(3, 13)),
        )
    texture = texture.filter(ImageFilter.GaussianBlur(3.2))
    return texture.resize(size, Image.Resampling.BICUBIC)


def _fixed_screen_shell(
    screen: Any, phone_title: str, cta: str, screen_texture: str,
) -> Any:
    """Place visual-only art inside the deterministic Natal app screen."""

    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    from .natal_brand import natal_logo_bytes

    canvas = Image.new("RGBA", PHONE_SCREEN_ART_SIZE, "#F9FAFA")
    # Cover the complete upper screen. The white readability fade below keeps
    # the status bar and Natal lock-up crisp, while starting the artwork at
    # y=0 prevents generated shapes or colour from being clipped into a hard
    # horizontal seam beneath the logo.
    hero_box = (0, 0, canvas.width, 1195 if not phone_title else 1050)
    hero = ImageOps.fit(
        screen, (hero_box[2] - hero_box[0], hero_box[3] - hero_box[1]),
        method=Image.Resampling.LANCZOS, centering=(0.5, 0.44),
    )
    canvas.alpha_composite(hero, hero_box[:2])

    # Feather the generated artwork into the screen so even a visually dense
    # result reads as one polished hero area rather than a pasted rectangle.
    fade = Image.new("RGBA", canvas.size, (255, 255, 255, 0))
    fade_alpha = Image.new("L", (1, canvas.height), 0)
    fade_pixels = fade_alpha.load()
    for y in range(canvas.height):
        top = max(0.0, min(1.0, (310 - y) / 130))
        bottom_start = hero_box[3] - 180
        bottom = max(0.0, min(1.0, (y - bottom_start) / 180))
        alpha = round(255 * max(top, bottom))
        if alpha:
            fade_pixels[0, y] = alpha
    fade_alpha = fade_alpha.resize(canvas.size)
    fade.putalpha(fade_alpha.filter(ImageFilter.GaussianBlur(12)))
    canvas.alpha_composite(fade)

    # Apply only the selected deterministic texture before drawing fixed UI,
    # preserving crisp renderer-owned text, logo, status chrome, and CTA.
    texture = _phone_hero_texture((canvas.width, hero_box[3]), screen_texture)
    canvas.alpha_composite(texture, hero_box[:2])

    draw = ImageDraw.Draw(canvas, "RGBA")
    status_font = _screen_font(27, 700)
    draw.text((52, 42), "9:41", font=status_font, fill="#101B31", anchor="lm")
    for index, height in enumerate((12, 20, 29, 38)):
        x = 632 + index * 14
        draw.rounded_rectangle((x, 66 - height, x + 9, 66), radius=4, fill="#101B31")
    draw.arc((692, 31, 744, 75), 205, 335, fill="#101B31", width=7)
    draw.ellipse((714, 61, 722, 69), fill="#101B31")
    draw.rounded_rectangle((756, 38, 794, 65), radius=7, outline="#101B31", width=4)
    draw.rounded_rectangle((762, 44, 787, 59), radius=4, fill="#101B31")
    draw.rounded_rectangle((794, 46, 800, 57), radius=2, fill="#101B31")

    with Image.open(BytesIO(natal_logo_bytes())) as source:
        logo = ImageOps.contain(source.convert("RGBA"), (390, 132), method=Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo, ((canvas.width - logo.width) // 2, 105))

    if phone_title:
        _draw_fitted_screen_text(
            draw, phone_title.upper(), (78, 1070, 754, 1385), maximum_size=68,
            minimum_size=28, weight=800, fill="#101B31", max_lines=3, spacing=10,
        )

    button_box = (70, 1450, 762, 1582)
    draw.rounded_rectangle(button_box, radius=66, fill="#1675F8")
    _draw_fitted_screen_text(
        draw, cta, (112, 1470, 720, 1562), maximum_size=38,
        minimum_size=22, weight=700, fill="#FFFFFF", max_lines=2, spacing=4,
    )
    draw.rounded_rectangle((218, 1642, 614, 1655), radius=7, fill="#101B31")
    return canvas


def compose_phone_device_asset(
    screen_data: bytes | None, phone_title: str, cta: str = "ДІЗНАТИСЯ БІЛЬШЕ",
    screen_texture: str = "grain",
) -> dict[str, Any]:
    """Fuse the fixed front frame and its deterministic upright app screen.

    The fuse is deliberately server-side: a mutable screen image cannot be
    moved independently from the checked-in frame. Generated pixels remain a
    text-free hero layer; Natal, the owner title, and CTA are renderer-owned.
    """
    from PIL import Image, ImageDraw, ImageOps

    frame_data = iphone_frame_bytes()
    with Image.open(BytesIO(frame_data)) as source:
        frame = source.convert("RGBA")
    resolved_screen = screen_data or _fallback_screen()
    try:
        with Image.open(BytesIO(resolved_screen)) as source:
            screen = source.convert("RGBA")
    except Exception as error:
        raise ValueError("phone screen artwork cannot be decoded") from error
    screen_texture = _enum(
        screen_texture, PHONE_SCREEN_TEXTURES, "phone screen texture",
    )
    screen = _fixed_screen_shell(screen, phone_title, cta, screen_texture)
    screen_size = (
        IPHONE_SCREEN_BOX[2] - IPHONE_SCREEN_BOX[0],
        IPHONE_SCREEN_BOX[3] - IPHONE_SCREEN_BOX[1],
    )
    screen = ImageOps.fit(
        screen, screen_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5),
    )
    aperture = Image.new("L", screen_size, 0)
    ImageDraw.Draw(aperture).rounded_rectangle(
        (0, 0, screen_size[0] - 1, screen_size[1] - 1),
        radius=IPHONE_SCREEN_RADIUS, fill=255,
    )
    screen_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    screen_layer.paste(screen, IPHONE_SCREEN_BOX[:2], aperture)
    # The high-resolution frame contains the bezel, camera island, and side
    # controls. Composite it last so UI and hardware remain one downstream
    # layer while the screen stays perfectly front-facing and readable.
    screen_layer.alpha_composite(frame)
    output = BytesIO(); screen_layer.save(output, format="PNG", optimize=False)
    data = output.getvalue()
    texture_provenance = {
        "none": "none",
        "grain": "deterministic_material_grain_v1",
        "paper": "deterministic_soft_paper_v1",
        "frosted": "deterministic_frosted_glass_v1",
    }[screen_texture]
    return {"bytes": data, "mime_type": "image/png", "source": {"origin": "server_composited_fixed_phone", "frame_sha256": IPHONE_FRAME_SHA256, "screen_sha256": hashlib.sha256(resolved_screen).hexdigest(), "screen_composition": "front_natal_app_shell_v8", "hero_texture": texture_provenance}}
