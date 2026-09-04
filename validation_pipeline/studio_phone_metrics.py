"""Bounded 4:5 phone-and-metrics Studio template.

The template is intentionally a fixed composition rather than a generic device
mock-up editor. Its only mutable visual is text-free hero artwork inside a
fixed app shell; the Natal lock-up, device frame, pose, copy geometry,
statistic-button geometry, and CTA remain server-owned. Button appearance is a
bounded saved configuration, so every render stays deterministic and reviewable.
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

from .studio import STUDIO_FONT_FAMILIES, STUDIO_PREVIEW_FONTS, SUPPORTED_FONTS
from .studio_primitives import PrimitiveTemplate


PHONE_METRICS_TEMPLATE_ID = "phone_metrics"
PHONE_METRICS_CONFIG_SCHEMA = "ptw.studio.phone-metrics-config.v8"
PHONE_METRICS_CONTENT_SCHEMA = "ptw.studio.phone-metrics-content.v2"
PHONE_METRICS_COMPONENT_SETTINGS_SCHEMA = "ptw.studio.phone-metrics-component-settings.v2"
PHONE_METRICS_TEMPLATE_VERSION = 22
PHONE_METRICS_CANVAS = (1080, 1350)
PHONE_BACKGROUND_TEXTURES = ("none", "grain", "concrete", "travertine")
PHONE_COPY_BACKGROUND_TEXTURES = PHONE_BACKGROUND_TEXTURES
PHONE_SCREEN_TEXTURES = ("none", "grain", "paper", "frosted")
PHONE_METRIC_CARD_STYLES = ("filled", "outlined")
PHONE_METRIC_CARD_SHAPES = ("square", "rounded", "pill")
PHONE_METRIC_CARD_RADII = {"square": 0, "rounded": 28, "pill": 70}
PHONE_ACTION_BUTTON_STYLES = ("filled", "elevated", "outlined", "text")
PHONE_ACTION_BUTTON_SHAPES = ("square", "rounded", "pill")
PHONE_ACTION_BUTTON_RADII = {"square": 0, "rounded": 24, "pill": 52}
PHONE_TYPOGRAPHY_BOUNDS = {
    "offer": (16, 42),
    "hero_title": (42, 110),
    "supporting_text": (20, 46),
    "cta": (20, 52),
    "metric_value": (20, 56),
    "metric_label": (14, 36),
    "phone_title": (24, 72),
    "phone_buttons": (16, 36),
}
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
PHONE_HERO_ART_OFFSET_Y = 220
PHONE_HERO_ART_FEATHER_Y = 130
PHONE_HERO_BOTTOM_FADE_Y = 300
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
        "description": "Server-generated text-free hero artwork inside the fixed Natal app screen and phone frame.",
    },
}

PHONE_COMPONENTS: tuple[dict[str, Any], ...] = (
    {"component_id": "phone_metrics.background", "role": "background", "node_ids": ("canvas", "background_texture", "copy_background_texture"), "asset_slot_ids": (), "setting_ids": ("configuration.background.texture", "configuration.copy_background.texture")},
    {"component_id": "phone_metrics.brand", "role": "brand", "node_ids": ("logo",), "asset_slot_ids": (), "setting_ids": ()},
    {"component_id": "phone_metrics.offer", "role": "offer", "node_ids": ("offer",), "asset_slot_ids": (), "setting_ids": ("configuration.offer.enabled", "configuration.typography.offer", "content.offer")},
    {"component_id": "phone_metrics.hero_title", "role": "hero_title", "node_ids": ("hero_title",), "asset_slot_ids": (), "setting_ids": ("configuration.typography.hero_title", "content.hero_title")},
    {"component_id": "phone_metrics.supporting_text", "role": "supporting_text", "node_ids": ("supporting_text",), "asset_slot_ids": (), "setting_ids": ("configuration.typography.supporting_text", "configuration.supporting_text.highlight_color", "content.supporting_text")},
    {"component_id": "phone_metrics.device", "role": "device_mockup", "node_ids": ("phone_device",), "asset_slot_ids": ("phone_screen",), "setting_ids": ("configuration.phone_screen.texture", "configuration.typography.phone_title", "configuration.typography.phone_buttons", "configuration.phone_buttons", "content.phone_hero_title", "content.phone_buttons")},
    {"component_id": "phone_metrics.metrics", "role": "metrics", "node_ids": ("metric_card_1", "metric_card_2", "metric_card_3", "metric_value_1", "metric_value_2", "metric_value_3", "metric_label_1", "metric_label_2", "metric_label_3"), "asset_slot_ids": (), "setting_ids": ("configuration.typography.metric_value", "configuration.typography.metric_label", "configuration.metric_cards", "content.stats")},
    {"component_id": "phone_metrics.cta", "role": "cta", "node_ids": ("cta",), "asset_slot_ids": (), "setting_ids": ("configuration.typography.cta", "content.cta")},
)

DEFAULT_PHONE_CONFIG: dict[str, Any] = {
    "schema": PHONE_METRICS_CONFIG_SCHEMA,
    "background": {
        "color": "#F4F5F2", "texture": "concrete", "texture_intensity": 0.13,
    },
    "copy_background": {"texture": "none"},
    "offer": {"enabled": True},
    "supporting_text": {"highlight_color": "#1675F8"},
    "typography": {
        "offer": {"font_family": "Manrope", "font_size": 23},
        "hero_title": {"font_family": "Manrope", "font_size": 76},
        "supporting_text": {"font_family": "Manrope", "font_size": 29},
        "cta": {"font_family": "Manrope", "font_size": 34},
        "metric_value": {"font_family": "Manrope", "font_size": 43},
        "metric_label": {"font_family": "Manrope", "font_size": 22},
        "phone_title": {"font_family": "Manrope", "font_size": 55},
        "phone_buttons": {"font_family": "Manrope", "font_size": 28},
    },
    "phone_screen": {"texture": "grain"},
    "metric_cards": [
        {
            "style": "filled", "text_color": "#FFFFFF",
            "background_color": "#2457C8", "shape": "rounded",
        }
        for _index in range(3)
    ],
    "phone_buttons": [
        {
            "style": "filled", "text_color": "#FFFFFF",
            "background_color": "#1675F8", "shape": "pill",
        },
        {
            "style": "elevated", "text_color": "#1675F8",
            "background_color": "#FFFFFF", "shape": "pill",
        },
        {
            "style": "text", "text_color": "#1675F8",
            "background_color": "#FFFFFF", "shape": "pill",
        },
    ],
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
    "phone_buttons": [
        "Створити новий акаунт",
        "Увійти",
        "Можливо пізніше",
    ],
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
    typography = _object(
        root["typography"], set(DEFAULT_PHONE_CONFIG["typography"]),
        "phone metrics typography",
    )
    normalized_typography = {}
    for role, bounds in PHONE_TYPOGRAPHY_BOUNDS.items():
        appearance = _object(
            typography[role], {"font_family", "font_size"},
            f"phone metrics typography.{role}",
        )
        normalized_typography[role] = {
            "font_family": _enum(
                appearance["font_family"], STUDIO_FONT_FAMILIES,
                f"phone metrics typography.{role}.font_family",
            ),
            "font_size": _number(
                appearance["font_size"],
                f"phone metrics typography.{role}.font_size", *bounds,
            ),
        }
    phone_screen = _object(
        root["phone_screen"], set(DEFAULT_PHONE_CONFIG["phone_screen"]),
        "phone metrics phone screen",
    )
    raw_metric_cards = root["metric_cards"]
    if not isinstance(raw_metric_cards, list) or len(raw_metric_cards) != 3:
        raise ValueError("phone metrics configuration requires exactly three metric cards")
    metric_cards = []
    for index, item in enumerate(raw_metric_cards, 1):
        card = _object(
            item, {"style", "text_color", "background_color", "shape"},
            f"phone metrics metric_cards[{index}]",
        )
        text_color = str(card["text_color"]).upper()
        background_color = str(card["background_color"]).upper()
        if not _COLOR.fullmatch(text_color):
            raise ValueError(
                f"phone metrics metric_cards[{index}].text_color must be a six-digit hex color"
            )
        if not _COLOR.fullmatch(background_color):
            raise ValueError(
                f"phone metrics metric_cards[{index}].background_color must be a six-digit hex color"
            )
        metric_cards.append({
            "style": _enum(
                card["style"], PHONE_METRIC_CARD_STYLES,
                f"phone metrics metric_cards[{index}].style",
            ),
            "text_color": text_color,
            "background_color": background_color,
            "shape": _enum(
                card["shape"], PHONE_METRIC_CARD_SHAPES,
                f"phone metrics metric_cards[{index}].shape",
            ),
        })
    raw_phone_buttons = root["phone_buttons"]
    if not isinstance(raw_phone_buttons, list) or len(raw_phone_buttons) != 3:
        raise ValueError("phone metrics configuration requires exactly three phone buttons")
    phone_buttons = []
    for index, item in enumerate(raw_phone_buttons, 1):
        button = _object(
            item, {"style", "text_color", "background_color", "shape"},
            f"phone metrics phone_buttons[{index}]",
        )
        text_color = str(button["text_color"]).upper()
        background_color = str(button["background_color"]).upper()
        if not _COLOR.fullmatch(text_color):
            raise ValueError(
                f"phone metrics phone_buttons[{index}].text_color must be a six-digit hex color"
            )
        if not _COLOR.fullmatch(background_color):
            raise ValueError(
                f"phone metrics phone_buttons[{index}].background_color must be a six-digit hex color"
            )
        phone_buttons.append({
            "style": _enum(
                button["style"], PHONE_ACTION_BUTTON_STYLES,
                f"phone metrics phone_buttons[{index}].style",
            ),
            "text_color": text_color,
            "background_color": background_color,
            "shape": _enum(
                button["shape"], PHONE_ACTION_BUTTON_SHAPES,
                f"phone metrics phone_buttons[{index}].shape",
            ),
        })
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
            "highlight_color": highlight_color,
        },
        "typography": normalized_typography,
        "phone_screen": {
            "texture": _enum(
                phone_screen["texture"], PHONE_SCREEN_TEXTURES,
                "phone metrics phone_screen.texture",
            ),
        },
        "metric_cards": metric_cards,
        "phone_buttons": phone_buttons,
        "device": {
            "x": _number(device["x"], "phone metrics device.x", 580, 640),
            "y": _number(device["y"], "phone metrics device.y", 70, 130),
            "width": _number(device["width"], "phone metrics device.width", 380, 430),
            "rotation": _number(device["rotation"], "phone metrics device.rotation", 0.0, 0.0),
        },
    }


def normalize_phone_metrics_content(value: Mapping[str, Any]) -> dict[str, Any]:
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
    raw_phone_buttons = root["phone_buttons"]
    if not isinstance(raw_phone_buttons, list) or len(raw_phone_buttons) != 3:
        raise ValueError("phone metrics content requires exactly three phone buttons")
    phone_buttons = [
        _text(text, f"phone metrics phone_buttons[{index}]", 1, 48)
        for index, text in enumerate(raw_phone_buttons, 1)
    ]
    return {
        "schema": PHONE_METRICS_CONTENT_SCHEMA,
        "offer": _text(root["offer"], "phone metrics offer", 1, 32),
        "hero_title": _text(root["hero_title"], "phone metrics hero_title", 1, 140),
        "supporting_text": _text(root["supporting_text"], "phone metrics supporting_text", 1, 220),
        "cta": _text(root["cta"], "phone metrics cta", 1, 60),
        "stats": stats,
        "phone_hero_title": _text(root["phone_hero_title"], "phone metrics phone_hero_title", 0, 72, allow_empty=True),
        "phone_buttons": phone_buttons,
    }


def normalize_phone_metrics_texture_choices(value: Mapping[str, Any]) -> dict[str, str]:
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
    typography = config["typography"]
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
            "font_family": typography["hero_title"]["font_family"],
            "font_size": typography["hero_title"]["font_size"], "min_font_size": 42, "font_weight": 800,
            "line_height": 0.94, "letter_spacing": -2.5, "color": "#101B31", "text_fit": "shrink", "max_lines": 5, "z_index": 6,
        }, binding=("text", "content.hero_title", True)),
        _node("supporting_text", "rich_text", {
            "position": "absolute", "x": 70, "y": 675, "width": 418, "height": 218,
            "font_family": typography["supporting_text"]["font_family"],
            "font_size": typography["supporting_text"]["font_size"],
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
            "font_family": typography["offer"]["font_family"],
            "font_size": typography["offer"]["font_size"], "min_font_size": 16, "font_weight": 800,
            "letter_spacing": 1.5, "color": "#101B31", "text_fit": "shrink", "max_lines": 1, "z_index": 6,
        }, binding=("text", "content.offer", True)))
    for index in range(3):
        x = card_x + index * (card_width + card_gap)
        metric_card = config["metric_cards"][index]
        filled = metric_card["style"] == "filled"
        children.extend([
            _node(f"metric_card_{index + 1}", "card", {
                "position": "absolute", "x": x, "y": cards_y, "width": card_width, "height": card_height,
                "background_color": metric_card["background_color"] if filled else None,
                "border_color": None if filled else metric_card["background_color"],
                "border_width": 0 if filled else 4,
                "radius": PHONE_METRIC_CARD_RADII[metric_card["shape"]], "z_index": 8,
            }),
            _node(f"metric_value_{index + 1}", "text", {
                "position": "absolute", "x": x + 14, "y": cards_y + 18, "width": card_width - 28, "height": 50,
                "font_family": typography["metric_value"]["font_family"],
                "font_size": typography["metric_value"]["font_size"], "min_font_size": 20, "font_weight": 800,
                "color": metric_card["text_color"], "text_align": "center", "text_fit": "shrink", "max_lines": 1, "z_index": 9,
            }, binding=("text", f"content.stats_{index + 1}_value", True)),
            _node(f"metric_label_{index + 1}", "text", {
                "position": "absolute", "x": x + 18, "y": cards_y + 75, "width": card_width - 36, "height": 48,
                "font_family": typography["metric_label"]["font_family"],
                "font_size": typography["metric_label"]["font_size"], "min_font_size": 14, "font_weight": 500,
                "line_height": 0.98, "color": metric_card["text_color"], "text_align": "center", "text_fit": "shrink", "max_lines": 2, "z_index": 9,
            }, binding=("text", f"content.stats_{index + 1}_label", True)),
        ])
    children.append(_node("cta", "button", {
        "position": "absolute", "x": 0, "y": 1206, "width": width, "height": 144,
        "background_color": "#316CFF", "radius": 0, "label_color": "#FFFFFF",
        "font_family": typography["cta"]["font_family"],
        "font_size": typography["cta"]["font_size"], "min_font_size": 20, "font_weight": 700, "text_align": "left", "vertical_align": "center",
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
            "phone_device": {"kind": "image", "allowed_mime_types": ["image/png"], "required": True, "provenance": "Server-composited fixed front-facing black iPhone, crisp Natal app shell, and server-generated or deterministic fallback text-free hero artwork."},
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
        "provenance": {"base_template_id": None, "base_version": None, "base_sha256": None, "reference_ids": ["owner-reference-phone-metrics-v1"], "change_note": "Natal phone-and-metrics v22 gives every editable text role an independent bounded font family and size while preserving the fixed Natal identity and system chrome; alpha cutouts keep the selected screen texture visible and never stretch subject pixels into the header."},
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
    for index, label in enumerate(normalized["phone_buttons"], 1):
        result[f"content.phone_buttons_{index}"] = label
    return result


def phone_metrics_component_settings(config: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
    config = normalize_phone_metrics_config(config)
    content = normalize_phone_metrics_content(content)
    values = {
        "configuration.background.texture": config["background"]["texture"],
        "configuration.copy_background.texture": config["copy_background"]["texture"],
        "configuration.offer.enabled": config["offer"]["enabled"],
        "configuration.supporting_text.highlight_color": config["supporting_text"]["highlight_color"],
        "configuration.phone_screen.texture": config["phone_screen"]["texture"],
        "configuration.metric_cards": deepcopy(config["metric_cards"]),
        "configuration.phone_buttons": deepcopy(config["phone_buttons"]),
        "content.offer": content["offer"], "content.hero_title": content["hero_title"],
        "content.supporting_text": content["supporting_text"], "content.cta": content["cta"],
        "content.stats": deepcopy(content["stats"]), "content.phone_hero_title": content["phone_hero_title"],
        "content.phone_buttons": deepcopy(content["phone_buttons"]),
        **{
            f"configuration.typography.{role}": deepcopy(appearance)
            for role, appearance in config["typography"].items()
        },
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
        "schema": "ptw.studio.phone-metrics-catalog.v2", "template_id": PHONE_METRICS_TEMPLATE_ID,
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
            "metric_card_styles": list(PHONE_METRIC_CARD_STYLES),
            "metric_card_shapes": list(PHONE_METRIC_CARD_SHAPES),
            "phone_button_styles": list(PHONE_ACTION_BUTTON_STYLES),
            "phone_button_shapes": list(PHONE_ACTION_BUTTON_SHAPES),
            "font_families": list(STUDIO_FONT_FAMILIES),
            "typography": {
                role: {
                    "minimum": bounds[0], "maximum": bounds[1],
                    "default": DEFAULT_PHONE_CONFIG["typography"][role]["font_size"],
                }
                for role, bounds in PHONE_TYPOGRAPHY_BOUNDS.items()
            },
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
    """Polished non-text hero art used before a generated hero is available."""
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

    # A deliberate sculptural cluster provides a neutral deterministic fallback.
    sphere((580, 480), 172, (32, 39, 51))
    sphere((640, 700), 150, (49, 57, 71))
    sphere((430, 770), 132, (24, 31, 43))
    sphere((645, 915), 112, (229, 244, 57))
    sphere((280, 585), 72, (228, 244, 57))
    output = BytesIO(); image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _screen_font(size: int, weight: int, font_family: str = "Manrope"):
    from PIL import ImageFont

    path = STUDIO_PREVIEW_FONTS.get(
        font_family, SUPPORTED_FONTS.get(font_family, SUPPORTED_FONTS["Inter"]),
    )
    try:
        font = ImageFont.truetype(str(path), size)
        try:
            axes = []
            for axis in font.get_variation_axes():
                name = bytes(axis["name"]).decode("ascii", "ignore").lower()
                axes.append(
                    max(axis["minimum"], min(axis["maximum"], weight))
                    if "weight" in name else axis["default"]
                )
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
    max_lines: int, spacing: int = 8, font_family: str = "Manrope",
) -> None:
    if not value:
        return
    max_width = box[2] - box[0]
    max_height = box[3] - box[1]
    fitted: tuple[Any, list[str], int] | None = None
    for size in range(maximum_size, minimum_size - 1, -2):
        font = _screen_font(size, weight, font_family)
        lines = _wrapped_lines(draw, value, font, max_width)
        if len(lines) > max_lines:
            continue
        text = "\n".join(lines)
        bounds = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center")
        if bounds[2] - bounds[0] <= max_width and bounds[3] - bounds[1] <= max_height:
            fitted = (font, lines, size)
            break
    if fitted is None:
        font = _screen_font(minimum_size, weight, font_family)
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


def _clear_phone_hero_edge_matte(image: Any) -> Any:
    """Turn a generated pale edge matte into alpha without erasing bright details.

    Phone-hero generators sometimes return an RGB image with an apparently
    clear cream background instead of a real alpha channel.  Only a connected
    near-white border is removed: white details enclosed by the subject (such
    as a target ring or highlight) remain intact, and photographic/full-bleed
    artwork is left unchanged.
    """

    from collections import deque
    from PIL import Image, ImageChops, ImageFilter, ImageOps

    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 250:
        return image
    width, height = image.size
    pixels = image.load()

    def pale_matte(x: int, y: int) -> bool:
        red, green, blue, value_alpha = pixels[x, y]
        return value_alpha > 0 and min(red, green, blue) >= 208 and max(red, green, blue) - min(red, green, blue) <= 48

    perimeter = [
        *( (x, 0) for x in range(width) ),
        *( (x, height - 1) for x in range(width) ),
        *( (0, y) for y in range(1, height - 1) ),
        *( (width - 1, y) for y in range(1, height - 1) ),
    ]
    if sum(pale_matte(x, y) for x, y in perimeter) < len(perimeter) * 0.88:
        return image

    matte = Image.new("L", image.size, 0)
    matte_pixels = matte.load()
    pending = deque((x, y) for x, y in perimeter if pale_matte(x, y))
    while pending:
        x, y = pending.popleft()
        if matte_pixels[x, y] or not pale_matte(x, y):
            continue
        matte_pixels[x, y] = 255
        if x:
            pending.append((x - 1, y))
        if x + 1 < width:
            pending.append((x + 1, y))
        if y:
            pending.append((x, y - 1))
        if y + 1 < height:
            pending.append((x, y + 1))

    if sum(matte.histogram()[1:]) < width * height * 0.15:
        return image
    # A narrow antialiased transition removes the hard matte edge without
    # softening the object itself or changing enclosed white subject detail.
    visible = ImageOps.invert(matte.filter(ImageFilter.GaussianBlur(1.2)))
    image.putalpha(ImageChops.multiply(alpha, visible))
    return image


def _position_phone_hero_art(screen: Any, size: tuple[int, int]) -> Any:
    """Lower the subject and extend only full-bleed artwork to the top."""

    from PIL import Image, ImageChops, ImageOps

    hero = ImageOps.fit(
        screen, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.44),
    )
    hero = _clear_phone_hero_edge_matte(hero)
    positioned = Image.new("RGBA", size, (0, 0, 0, 0))
    has_alpha_background = hero.getchannel("A").getextrema()[0] < 250
    continuation_height = PHONE_HERO_ART_OFFSET_Y + PHONE_HERO_ART_FEATHER_Y
    if not has_alpha_background:
        # Stretch only the first, usually background-only strip of genuinely
        # full-bleed artwork through the header. Doing this to a cutout would
        # stretch the subject's top edge into a triangular plume.
        continuation = hero.crop((0, 0, hero.width, PHONE_HERO_ART_FEATHER_Y + 1))
        continuation = continuation.resize(
            (hero.width, continuation_height), Image.Resampling.BICUBIC,
        )
        positioned.alpha_composite(continuation, (0, 0))

    lowered = Image.new("RGBA", size, (0, 0, 0, 0))
    lowered.alpha_composite(hero, (0, PHONE_HERO_ART_OFFSET_Y))
    feather = Image.new("L", (1, size[1]), 255)
    feather_pixels = feather.load()
    for y in range(continuation_height):
        feather_pixels[0, y] = (
            0 if y < PHONE_HERO_ART_OFFSET_Y
            else round(
                255 * (y - PHONE_HERO_ART_OFFSET_Y)
                / PHONE_HERO_ART_FEATHER_Y
            )
        )
    feather = feather.resize(size)
    lowered.putalpha(ImageChops.multiply(lowered.getchannel("A"), feather))
    positioned.alpha_composite(lowered)
    return positioned


def _draw_status_network_icons(draw: Any) -> None:
    """Draw crisp cellular and complete Wi-Fi indicators at app-screen scale."""

    color = "#101B31"
    for index, height in enumerate((12, 20, 29, 38)):
        x = 632 + index * 14
        draw.rounded_rectangle(
            (x, 66 - height, x + 9, 66), radius=4, fill=color,
        )

    # Three separated arcs and a dot preserve the familiar Wi-Fi silhouette
    # after the app screen is resampled into the high-resolution phone frame.
    for box, width in (
        ((690, 30, 746, 78), 7),
        ((700, 42, 736, 73), 6),
        ((709, 53, 727, 69), 5),
    ):
        start, end = 205, 335
        draw.arc(box, start, end, fill=color, width=width)
        left, top, right, bottom = box
        center_x, center_y = (left + right) / 2, (top + bottom) / 2
        radius_x, radius_y = (right - left) / 2, (bottom - top) / 2
        cap_radius = width / 2
        for angle in (start, end):
            radians = math.radians(angle)
            x = center_x + radius_x * math.cos(radians)
            y = center_y + radius_y * math.sin(radians)
            draw.ellipse(
                (x - cap_radius, y - cap_radius, x + cap_radius, y + cap_radius),
                fill=color,
            )
    draw.ellipse((714, 66, 722, 74), fill=color)


def _draw_phone_action_button(
    canvas: Any, text: str, appearance: Mapping[str, Any],
    box: tuple[int, int, int, int], typography: Mapping[str, Any],
) -> None:
    """Draw one bounded in-phone action without softening its label."""

    from PIL import Image, ImageDraw, ImageFilter

    style = str(appearance["style"])
    radius = min(
        PHONE_ACTION_BUTTON_RADII[str(appearance["shape"])],
        (box[3] - box[1]) // 2,
    )
    if style == "elevated":
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow, "RGBA")
        shadow_draw.rounded_rectangle(
            (box[0], box[1] + 7, box[2], box[3] + 7),
            radius=radius, fill=(16, 27, 49, 38),
        )
        canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(11)))

    draw = ImageDraw.Draw(canvas, "RGBA")
    if style in {"filled", "elevated"}:
        draw.rounded_rectangle(
            box, radius=radius, fill=str(appearance["background_color"]),
        )
    elif style == "outlined":
        draw.rounded_rectangle(
            box, radius=radius, outline=str(appearance["background_color"]),
            width=4,
        )
    _draw_fitted_screen_text(
        draw, text, (box[0] + 36, box[1] + 12, box[2] - 36, box[3] - 12),
        maximum_size=int(typography["font_size"]), minimum_size=16, weight=600,
        fill=str(appearance["text_color"]), max_lines=1, spacing=4,
        font_family=str(typography["font_family"]),
    )


def _fixed_screen_shell(
    screen: Any, phone_title: str, cta: str, screen_texture: str,
    phone_button_texts: list[str] | None = None,
    phone_button_appearances: list[Mapping[str, Any]] | None = None,
    typography: Mapping[str, Mapping[str, Any]] | None = None,
) -> Any:
    """Place visual-only art inside the deterministic Natal app screen."""

    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
    from .natal_brand import natal_logo_bytes

    canvas = Image.new("RGBA", PHONE_SCREEN_ART_SIZE, "#F9FAFA")
    resolved_typography = typography or DEFAULT_PHONE_CONFIG["typography"]
    # Cover the complete upper screen with an image-derived continuation while
    # lowering the sharp subject away from the status and Natal header.
    # The optional title occupies a reserved stack slot below the hero.  Keep
    # the hero box constant so changing that text cannot rescale or vertically
    # shift the owner-selected artwork.
    hero_box = (0, 0, canvas.width, 1050)
    hero = _position_phone_hero_art(
        screen, (hero_box[2] - hero_box[0], hero_box[3] - hero_box[1]),
    )
    # First lay the texture beneath the visual-only hero. This matters for
    # PNG/WebP assets with an alpha background: their transparent pixels must
    # reveal the selected screen material rather than the flat shell base.
    texture = _phone_hero_texture((canvas.width, hero_box[3]), screen_texture)
    canvas.alpha_composite(texture, hero_box[:2])
    canvas.alpha_composite(hero, hero_box[:2])

    # Preserve the existing material finish on opaque hero pixels, but mask
    # that foreground pass with the fitted artwork alpha. A transparent pixel
    # therefore receives only the underlying texture above, never a texture
    # layer flattened over a white shell.
    foreground_texture = texture.copy()
    foreground_texture.putalpha(ImageChops.multiply(
        foreground_texture.getchannel("A"), hero.getchannel("A"),
    ))
    canvas.alpha_composite(foreground_texture, hero_box[:2])

    # Fade the image and its selected finish together, preventing a straight
    # texture edge immediately above the headline.

    # Feather the complete hero surface into white with an eased, zero-slope
    # finish. The longer overlap keeps detail visible while avoiding a visible
    # horizontal boundary where the image layer ends.
    fade = Image.new("RGBA", canvas.size, (255, 255, 255, 0))
    fade_alpha = Image.new("L", (1, canvas.height), 0)
    fade_pixels = fade_alpha.load()
    for y in range(canvas.height):
        top = max(0.0, min(1.0, (310 - y) / 130))
        bottom_start = hero_box[3] - PHONE_HERO_BOTTOM_FADE_Y
        bottom_progress = max(
            0.0, min(1.0, (y - bottom_start) / PHONE_HERO_BOTTOM_FADE_Y),
        )
        bottom = bottom_progress * bottom_progress * (3 - 2 * bottom_progress)
        alpha = round(255 * max(top, bottom))
        if alpha:
            fade_pixels[0, y] = alpha
    fade_alpha = fade_alpha.resize(canvas.size)
    fade.putalpha(fade_alpha.filter(ImageFilter.GaussianBlur(12)))
    canvas.alpha_composite(fade)

    draw = ImageDraw.Draw(canvas, "RGBA")
    status_font = _screen_font(27, 700)
    draw.text((52, 42), "9:41", font=status_font, fill="#101B31", anchor="lm")
    _draw_status_network_icons(draw)
    draw.rounded_rectangle((756, 38, 794, 65), radius=7, outline="#101B31", width=4)
    draw.rounded_rectangle((762, 44, 787, 59), radius=4, fill="#101B31")
    draw.rounded_rectangle((794, 46, 800, 57), radius=2, fill="#101B31")

    with Image.open(BytesIO(natal_logo_bytes())) as source:
        logo = ImageOps.contain(source.convert("RGBA"), (390, 132), method=Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo, ((canvas.width - logo.width) // 2, 105))

    if phone_title:
        _draw_fitted_screen_text(
            draw, phone_title.upper(), (78, 1055, 754, 1255),
            maximum_size=int(resolved_typography["phone_title"]["font_size"]),
            minimum_size=24, weight=800, fill="#101B31", max_lines=3, spacing=8,
            font_family=str(resolved_typography["phone_title"]["font_family"]),
        )

    # The post-level CTA is rendered outside the device. These three actions
    # belong to the app screen and default to the owner reference screenshot.
    _ = cta  # Retained in the public composition signature for old callers.
    resolved_texts = phone_button_texts or list(DEFAULT_PHONE_CONTENT["phone_buttons"])
    resolved_appearances = phone_button_appearances or deepcopy(
        DEFAULT_PHONE_CONFIG["phone_buttons"],
    )
    for text, appearance, box in zip(
        resolved_texts,
        resolved_appearances,
        (
            (70, 1284, 762, 1388),
            (70, 1410, 762, 1514),
            (70, 1532, 762, 1606),
        ),
        strict=True,
    ):
        _draw_phone_action_button(
            canvas, text, appearance, box, resolved_typography["phone_buttons"],
        )
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((218, 1642, 614, 1655), radius=7, fill="#101B31")
    return canvas


def compose_phone_device_asset(
    screen_data: bytes | None, phone_title: str, cta: str = "ДІЗНАТИСЯ БІЛЬШЕ",
    screen_texture: str = "grain",
    phone_button_texts: list[str] | None = None,
    phone_button_appearances: list[Mapping[str, Any]] | None = None,
    typography: Mapping[str, Mapping[str, Any]] | None = None,
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
    screen = _fixed_screen_shell(
        screen, phone_title, cta, screen_texture,
        phone_button_texts, phone_button_appearances, typography,
    )
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
    return {"bytes": data, "mime_type": "image/png", "source": {"origin": "server_composited_fixed_phone", "frame_sha256": IPHONE_FRAME_SHA256, "screen_sha256": hashlib.sha256(resolved_screen).hexdigest(), "screen_composition": "front_natal_app_shell_v18", "hero_texture": texture_provenance}}
