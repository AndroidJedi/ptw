"""One bounded universal-ad configuration rendered by Studio primitives.

The primitive catalog remains an internal rendering mechanism.  This module is
the public Studio design contract: stable semantic roles, three fixed asset
slots, and a deliberately small set of settings with visible creative impact.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from io import BytesIO
import hashlib
import json
import math
import random
import re
from typing import Any, Mapping

from .studio_primitives import PrimitiveTemplate


UNIVERSAL_AD_TEMPLATE_ID = "universal_ad"
UNIVERSAL_AD_CONFIG_SCHEMA = "ptw.studio.universal-ad-config.v5"
UNIVERSAL_AD_CONTENT_SCHEMA = "ptw.studio.universal-ad-content.v2"
UNIVERSAL_AD_COMPONENT_SETTINGS_SCHEMA = "ptw.studio.universal-ad-component-settings.v2"
UNIVERSAL_AD_TEMPLATE_VERSION = 11

FONT_FAMILIES = ("Inter", "Manrope", "Oswald", "Cormorant Garamond")
TEXTURE_PRESETS = (
    "grain", "stone", "marble", "concrete", "granite", "slate", "travertine",
)
CTA_POSITIONS = ("below_text", "bottom_left", "bottom_right")
STICKER_POSITIONS = (
    "top_left", "top_right", "bottom_left", "bottom_right", "right_edge",
    "bottom_edge", "bullet_list", "hero_title", "cta",
)
COLOR_VALUE_ALIASES: dict[str, tuple[str, ...]] = {
    "#FFFFFF": ("white", "білий", "біла", "біле", "білим", "білою"),
    "#000000": ("black", "чорний", "чорна", "чорне", "чорним", "чорною"),
    "#FF0000": ("red", "червоний", "червона", "червоне", "червоним", "червоною"),
    "#00FF00": ("green", "зелений", "зелена", "зелене", "зеленим", "зеленою"),
    "#0000FF": ("blue", "синій", "синя", "синє", "синім", "синьою"),
    "#FFD84D": ("yellow", "жовтий", "жовта", "жовте", "жовтим", "жовтою"),
    "#10233F": ("navy", "dark navy", "темно-синій", "темно-синя", "темно-синім", "темно-синьою"),
}

SEMANTIC_ROLES = (
    "background", "sticker", "hero_title", "supporting_text",
    "offer", "bullet_list", "cta", "logo",
)
ASSET_SLOTS: dict[str, dict[str, Any]] = {
    "background_image": {
        "role": "background",
        "allowed_mime_types": ("image/jpeg", "image/png", "image/webp"),
        "description": "Optional Pexels or owner-provided photographic background.",
    },
    "sticker_object": {
        "role": "sticker",
        "allowed_mime_types": ("image/png", "image/webp"),
        "description": (
            "Optional Pexels photograph of a physical object, screened and isolated "
            "before its die-cut alpha contour is rendered."
        ),
    },
    "logo": {
        "role": "logo",
        "allowed_mime_types": ("image/png", "image/webp"),
        "description": (
            "Canonical Natal transparent brand mark. This identity is fixed in all new Studio drafts."
        ),
    },
}

# Stable public identities connect editor controls to renderer nodes, asset
# slots, immutable versions, Tune-agent context, and later learning records.
COMPONENT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "component_id": "universal_ad.background",
        "role": "background",
        "node_ids": ("canvas", "background_media", "readability_overlay"),
        "asset_slot_ids": ("background_image",),
        "setting_ids": (
            "configuration.background.mode", "configuration.background.color",
            "configuration.background.texture", "configuration.background.texture_intensity",
            "configuration.background.image_layout", "configuration.background.image_percent",
            "configuration.background.image_fit", "configuration.background.focal_x",
            "configuration.background.focal_y", "configuration.background.overlay_color",
            "configuration.background.overlay_opacity",
        ),
    },
    {
        "component_id": "universal_ad.sticker",
        "role": "sticker",
        "node_ids": ("sticker_object",),
        "asset_slot_ids": ("sticker_object",),
        "setting_ids": (
            "configuration.sticker.enabled", "configuration.sticker.position",
            "configuration.sticker.rotation", "configuration.sticker.width",
            "configuration.sticker.object_scale", "configuration.sticker.offset_right",
            "configuration.sticker.offset_bottom",
        ),
    },
    {
        "component_id": "universal_ad.hero_title",
        "role": "hero_title",
        "node_ids": ("hero_title",),
        "asset_slot_ids": (),
        "setting_ids": (
            "content.hero_title", "configuration.typography.font_family",
            "configuration.typography.hero_size", "configuration.typography.hero_weight",
            "configuration.typography.text_color", "configuration.typography.alignment",
            "configuration.layout.content_x", "configuration.layout.content_y",
            "configuration.layout.content_width", "configuration.layout.gap",
        ),
    },
    {
        "component_id": "universal_ad.supporting_text",
        "role": "supporting_text",
        "node_ids": ("supporting_text",),
        "asset_slot_ids": (),
        "setting_ids": (
            "content.supporting_text", "configuration.typography.font_family",
            "configuration.typography.supporting_size", "configuration.typography.text_color",
            "configuration.typography.alignment", "configuration.layout.content_x",
            "configuration.layout.content_y", "configuration.layout.content_width",
            "configuration.layout.gap",
        ),
    },
    {
        "component_id": "universal_ad.offer",
        "role": "offer",
        "node_ids": ("offer",),
        "asset_slot_ids": (),
        "setting_ids": (
            "content.offer", "configuration.typography.font_family",
            "configuration.typography.supporting_size", "configuration.typography.text_color",
            "configuration.typography.alignment", "configuration.layout.content_x",
            "configuration.layout.content_y", "configuration.layout.content_width",
            "configuration.layout.gap",
        ),
    },
    {
        "component_id": "universal_ad.bullet_list",
        "role": "bullet_list",
        "node_ids": (
            "bullet_marker_1", "bullet_1", "bullet_marker_2", "bullet_2",
            "bullet_marker_3", "bullet_3",
        ),
        "asset_slot_ids": (),
        "setting_ids": (
            "content.bullets", "configuration.bullets.enabled",
            "configuration.bullets.style", "configuration.typography.benefits_font_family",
            "configuration.typography.supporting_size", "configuration.typography.text_color",
            "configuration.layout.content_x", "configuration.layout.content_y",
            "configuration.layout.content_width",
            "configuration.layout.gap",
        ),
    },
    {
        "component_id": "universal_ad.cta",
        "role": "cta",
        "node_ids": ("cta",),
        "asset_slot_ids": (),
        "setting_ids": (
            "content.cta", "configuration.cta.style",
            "configuration.cta.position",
            "configuration.cta.background_color", "configuration.cta.text_color",
            "configuration.cta.radius", "configuration.cta.font_size",
            "configuration.typography.font_family",
            "configuration.typography.alignment", "configuration.layout.content_x",
            "configuration.layout.content_y", "configuration.layout.content_width",
            "configuration.layout.gap",
        ),
    },
    {
        "component_id": "universal_ad.logo",
        "role": "logo",
        "node_ids": ("logo",),
        "asset_slot_ids": ("logo",),
        # Natal is a fixed brand lock-up. The retained configuration members
        # exist only to read older saved drafts and immutable versions.
        "setting_ids": (),
    },
)


def _setting(
    component_id: str, value_type: str, aliases: tuple[str, ...], *,
    minimum: int | float | None = None, maximum: int | float | None = None,
    step: int | float | None = None, values: tuple[Any, ...] = (),
    value_aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "component_id": component_id, "value_type": value_type,
        "aliases": list(aliases),
    }
    if minimum is not None:
        result["minimum"] = minimum
    if maximum is not None:
        result["maximum"] = maximum
    if step is not None:
        result["step"] = step
    if values:
        result["values"] = list(values)
    if value_aliases:
        result["value_aliases"] = {
            key: list(items) for key, items in value_aliases.items()
        }
    return result


# This is the one public source of truth for Studio controls, Tune resolution,
# validation bounds, and strict planner schemas. Aliases intentionally contain
# only precise owner language; fuzzy or copy-related comments remain Codex work.
UNIVERSAL_SETTING_DEFINITIONS: dict[str, dict[str, Any]] = {
    "configuration.background.mode": _setting(
        "universal_ad.background", "enum", ("background mode", "режим фону"),
        values=("solid", "texture", "image"),
        value_aliases={
            "solid": ("solid", "суцільний"), "texture": ("texture", "текстура"),
            "image": ("image", "photo", "зображення", "фото"),
        },
    ),
    "configuration.background.color": _setting(
        "universal_ad.background", "color", ("background color", "колір фону"),
        value_aliases=COLOR_VALUE_ALIASES,
    ),
    "configuration.background.texture": _setting(
        "universal_ad.background", "enum", ("background texture", "текстура фону"),
        values=TEXTURE_PRESETS,
    ),
    "configuration.background.texture_intensity": _setting(
        "universal_ad.background", "number", ("texture intensity", "інтенсивність текстури"),
        minimum=0, maximum=1, step=0.05,
    ),
    "configuration.background.image_layout": _setting(
        "universal_ad.background", "enum", ("image layout", "розміщення зображення"),
        values=("full", "left", "right", "top", "bottom"),
        value_aliases={
            "full": ("full", "повністю"), "left": ("left", "ліворуч"),
            "right": ("right", "праворуч"), "top": ("top", "зверху"),
            "bottom": ("bottom", "знизу"),
        },
    ),
    "configuration.background.image_percent": _setting(
        "universal_ad.background", "integer", ("image percent", "відсоток зображення"),
        values=(25, 75),
    ),
    "configuration.background.image_fit": _setting(
        "universal_ad.background", "enum", ("image fit", "масштабування зображення"),
        values=("cover", "contain"),
        value_aliases={"cover": ("cover", "заповнити"), "contain": ("contain", "вмістити")},
    ),
    "configuration.background.focal_x": _setting(
        "universal_ad.background", "number", ("horizontal focal point", "фокус по горизонталі"),
        minimum=0, maximum=1, step=0.05,
    ),
    "configuration.background.focal_y": _setting(
        "universal_ad.background", "number", ("vertical focal point", "фокус по вертикалі"),
        minimum=0, maximum=1, step=0.05,
    ),
    "configuration.background.overlay_color": _setting(
        "universal_ad.background", "color", ("overlay color", "колір накладки"),
        value_aliases=COLOR_VALUE_ALIASES,
    ),
    "configuration.background.overlay_opacity": _setting(
        "universal_ad.background", "number", ("overlay opacity", "прозорість накладки"),
        minimum=0, maximum=0.85, step=0.05,
    ),
    "configuration.typography.font_family": _setting(
        "universal_ad.hero_title", "enum", ("font", "font family", "шрифт"),
        values=FONT_FAMILIES,
    ),
    "configuration.typography.benefits_font_family": _setting(
        "universal_ad.bullet_list", "enum", ("benefits font", "шрифт переваг"),
        values=FONT_FAMILIES,
    ),
    "configuration.typography.hero_size": _setting(
        "universal_ad.hero_title", "integer", (
            "headline size", "headline font size", "hero size", "розмір заголовка",
            "розмір шрифту заголовка",
        ),
        minimum=64, maximum=180, step=1,
    ),
    "configuration.typography.hero_weight": _setting(
        "universal_ad.hero_title", "integer", ("headline weight", "товщина заголовка"),
        minimum=400, maximum=900, step=100,
    ),
    "configuration.typography.supporting_size": _setting(
        "universal_ad.supporting_text", "integer", (
            "supporting text size", "supporting font size", "розмір додаткового тексту",
            "розмір шрифту додаткового тексту",
        ),
        minimum=22, maximum=52, step=1,
    ),
    "configuration.typography.text_color": _setting(
        "universal_ad.hero_title", "color", ("text color", "post text color", "колір тексту", "колір тексту допису"),
        value_aliases=COLOR_VALUE_ALIASES,
    ),
    "configuration.typography.alignment": _setting(
        "universal_ad.hero_title", "enum", ("text alignment", "вирівнювання тексту"),
        values=("left", "center"),
        value_aliases={"left": ("left", "ліворуч"), "center": ("center", "centre", "по центру", "центр")},
    ),
    "configuration.layout.content_x": _setting(
        "universal_ad.hero_title", "integer", ("content x", "горизонтальна позиція контенту"),
        minimum=48, maximum=520, step=1,
    ),
    "configuration.layout.content_y": _setting(
        "universal_ad.hero_title", "integer", ("content y", "вертикальна позиція контенту"),
        minimum=72, maximum=360, step=1,
    ),
    "configuration.layout.content_width": _setting(
        "universal_ad.hero_title", "integer", ("content width", "ширина контенту"),
        minimum=420, maximum=936, step=1,
    ),
    "configuration.layout.gap": _setting(
        "universal_ad.hero_title", "integer", ("spacing", "gap", "відступ", "інтервал"),
        minimum=8, maximum=56, step=1,
    ),
    "configuration.bullets.enabled": _setting(
        "universal_ad.bullet_list", "boolean", ("bullets", "bullet list", "маркери", "список переваг"),
    ),
    "configuration.bullets.style": _setting(
        "universal_ad.bullet_list", "enum", ("bullet style", "стиль маркерів"),
        values=("check", "circle", "circle_outline"),
        value_aliases={
            "check": ("check", "checkmark", "галочка"),
            "circle": ("circle", "filled circle", "коло"),
            "circle_outline": ("circle outline", "outlined circle", "контурне коло"),
        },
    ),
    "configuration.cta.style": _setting(
        "universal_ad.cta", "enum", ("cta style", "button style", "стиль cta", "стиль кнопки"),
        values=("filled", "gradient", "reverse", "link", "outlined"),
        value_aliases={
            "filled": ("filled", "залитий", "залитою"), "gradient": ("gradient", "градієнт", "градієнтною"),
            "reverse": ("reverse", "інверсний", "інверсною"), "link": ("link", "посиланням"),
            "outlined": ("outlined", "outline", "контурний", "контурною"),
        },
    ),
    "configuration.cta.position": _setting(
        "universal_ad.cta", "enum", ("cta position", "button position", "позиція cta", "позиція кнопки"),
        values=CTA_POSITIONS,
        value_aliases={
            "below_text": ("below text", "під текстом"),
            "bottom_left": ("bottom left", "знизу ліворуч", "внизу зліва"),
            "bottom_right": ("bottom right", "знизу праворуч", "внизу справа"),
        },
    ),
    "configuration.cta.background_color": _setting(
        "universal_ad.cta", "color", ("cta background color", "button color", "колір кнопки", "колір фону cta"),
        value_aliases=COLOR_VALUE_ALIASES,
    ),
    "configuration.cta.text_color": _setting(
        "universal_ad.cta", "color", ("cta text color", "button text color", "колір тексту кнопки", "колір тексту cta"),
        value_aliases=COLOR_VALUE_ALIASES,
    ),
    "configuration.cta.radius": _setting(
        "universal_ad.cta", "integer", ("cta radius", "button radius", "радіус кнопки"),
        minimum=0, maximum=40, step=1,
    ),
    "configuration.cta.font_size": _setting(
        "universal_ad.cta", "integer", ("cta text size", "button text size", "розмір тексту кнопки"),
        minimum=18, maximum=42, step=1,
    ),
    "configuration.sticker.enabled": _setting(
        "universal_ad.sticker", "boolean", ("sticker", "стікер", "наліпка"),
    ),
    "configuration.sticker.position": _setting(
        "universal_ad.sticker", "enum", ("sticker position", "позиція стікера", "позиція наліпки"),
        values=STICKER_POSITIONS,
        value_aliases={
            "top_left": ("top left", "зверху ліворуч", "вгорі зліва"),
            "top_right": ("top right", "зверху праворуч", "вгорі справа"),
            "bottom_left": ("bottom left", "знизу ліворуч", "внизу зліва"),
            "bottom_right": ("bottom right", "знизу праворуч", "внизу справа"),
            "right_edge": ("right edge", "правий край"),
            "bottom_edge": ("bottom edge", "нижній край"),
            "bullet_list": ("bullet list", "список переваг"),
            "hero_title": ("headline", "hero title", "заголовок"),
            "cta": ("cta", "button", "кнопка"),
        },
    ),
    "configuration.sticker.rotation": _setting(
        "universal_ad.sticker", "number", ("sticker rotation", "поворот стікера", "поворот наліпки"),
        minimum=-18, maximum=18, step=1,
    ),
    "configuration.sticker.width": _setting(
        "universal_ad.sticker", "integer", ("sticker width", "sticker size", "ширина стікера", "розмір стікера", "розмір наліпки"),
        minimum=120, maximum=720, step=1,
    ),
    "configuration.sticker.object_scale": _setting(
        "universal_ad.sticker", "number", ("sticker scale", "масштаб стікера", "масштаб наліпки"),
        minimum=0.35, maximum=1.5, step=0.05,
    ),
    "configuration.sticker.offset_right": _setting(
        "universal_ad.sticker", "integer", ("sticker right offset", "відступ стікера справа"),
        minimum=-720, maximum=720, step=1,
    ),
    "configuration.sticker.offset_bottom": _setting(
        "universal_ad.sticker", "integer", ("sticker bottom offset", "відступ стікера знизу"),
        minimum=-720, maximum=720, step=1,
    ),
    "configuration.logo.enabled": _setting(
        "universal_ad.logo", "boolean", ("logo", "логотип"),
    ),
    "configuration.logo.position": _setting(
        "universal_ad.logo", "enum", ("logo position", "позиція логотипа"),
        values=("top_left", "top_right"),
        value_aliases={
            "top_left": ("top left", "зверху ліворуч", "вгорі зліва"),
            "top_right": ("top right", "зверху праворуч", "вгорі справа"),
        },
    ),
    "configuration.logo.width": _setting(
        "universal_ad.logo", "integer", ("logo width", "logo size", "ширина логотипа", "розмір логотипа"),
        minimum=80, maximum=280, step=1,
    ),
}

DEFAULT_CONFIG: dict[str, Any] = {
    "schema": UNIVERSAL_AD_CONFIG_SCHEMA,
    "background": {
        "mode": "texture",
        "color": "#10233F",
        "texture": "stone",
        "texture_intensity": 0.7,
        "image_layout": "full",
        "image_percent": 75,
        "image_fit": "cover",
        "focal_x": 0.5,
        "focal_y": 0.5,
        "overlay_color": "#07182E",
        "overlay_opacity": 0.56,
    },
    "typography": {
        "font_family": "Inter",
        "benefits_font_family": "Manrope",
        "hero_size": 94,
        "hero_weight": 800,
        "supporting_size": 30,
        "text_color": "#FFFFFF",
        "alignment": "left",
    },
    "layout": {
        "content_x": 76,
        "content_y": 128,
        "content_width": 650,
        "gap": 20,
    },
    "bullets": {
        "enabled": True,
        "style": "check",
    },
    "cta": {
        "style": "filled",
        "position": "below_text",
        "background_color": "#FFD84D",
        "text_color": "#10233F",
        "radius": 24,
        "font_size": 27,
    },
    "sticker": {
        "enabled": False,
        "position": "bottom_right",
        "rotation": 5,
        "width": 300,
        "object_scale": 0.9,
        "offset_right": 0,
        "offset_bottom": 0,
    },
    "logo": {
        "enabled": True,
        "position": "top_right",
        "width": 180,
        "background_enabled": False,
        "background_color": "#FFFFFF",
    },
}

DEFAULT_CONTENT: dict[str, Any] = {
    "schema": UNIVERSAL_AD_CONTENT_SCHEMA,
    "hero_title": "ІНВЕСТУВАТИ В УКРАЇНІ — ПРОСТІШЕ",
    "supporting_text": "Аналізуємо ваші цілі й підказуємо інструменти, що відповідають саме вам.",
    "offer": "Безкоштовна 15-хвилинна консультація",
    "bullets": [
        "Персональний підбір інструментів",
        "Зрозуміле порівняння ризику",
        "Наступний крок без зайвого шуму",
    ],
    "cta": "ЗНАЙТИ СВОЄ",
}

_COLOR = re.compile(r"#[0-9A-F]{6}")


def _canonical(value: Any) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def _object(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(f"{label} fields do not match the universal ad contract")
    return value


def _enum(value: Any, allowed: tuple[str, ...], label: str) -> str:
    normalized = str(value)
    if normalized not in allowed:
        raise ValueError(f"{label} is outside its allowed values")
    return normalized


def _number(value: Any, label: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized) or not minimum <= normalized <= maximum:
        raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}")
    return normalized


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    normalized = _number(value, label, minimum, maximum)
    if int(normalized) != normalized:
        raise ValueError(f"{label} must be an integer")
    return int(normalized)


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _color(value: Any, label: str) -> str:
    normalized = str(value).upper()
    if not _COLOR.fullmatch(normalized):
        raise ValueError(f"{label} must be a six-digit hex color")
    return normalized


def normalize_universal_setting(setting_id: str, value: Any) -> Any:
    """Normalize one public control from the canonical Studio registry."""

    definition = UNIVERSAL_SETTING_DEFINITIONS.get(setting_id)
    if definition is None:
        raise ValueError(f"Studio setting is not registered: {setting_id}")
    label = setting_id.removeprefix("configuration.")
    value_type = definition["value_type"]
    if value_type == "boolean":
        return _boolean(value, label)
    if value_type == "color":
        return _color(value, label)
    if value_type == "enum":
        return _enum(value, tuple(definition["values"]), label)
    if value_type == "integer":
        if definition.get("values"):
            normalized = _integer(value, label, min(definition["values"]), max(definition["values"]))
            if normalized not in definition["values"]:
                raise ValueError(f"{label} is outside its allowed values")
            return normalized
        return _integer(value, label, definition["minimum"], definition["maximum"])
    if value_type == "number":
        return _number(value, label, definition["minimum"], definition["maximum"])
    raise ValueError(f"Studio setting has unsupported registered type: {setting_id}")


def normalize_universal_config(value: Mapping[str, Any]) -> dict[str, Any]:
    root = _object(value, set(DEFAULT_CONFIG), "Studio universal configuration")
    if root["schema"] != UNIVERSAL_AD_CONFIG_SCHEMA:
        raise ValueError("Studio universal configuration schema is invalid")
    background = _object(root["background"], set(DEFAULT_CONFIG["background"]), "background")
    typography = _object(root["typography"], set(DEFAULT_CONFIG["typography"]), "typography")
    layout = _object(root["layout"], set(DEFAULT_CONFIG["layout"]), "layout")
    bullets = _object(root["bullets"], set(DEFAULT_CONFIG["bullets"]), "bullets")
    cta = _object(root["cta"], set(DEFAULT_CONFIG["cta"]), "cta")
    sticker = _object(root["sticker"], set(DEFAULT_CONFIG["sticker"]), "sticker")
    logo = _object(root["logo"], set(DEFAULT_CONFIG["logo"]), "logo")
    _boolean(logo["background_enabled"], "logo.background_enabled")
    logo_background_color = _color(
        logo["background_color"], "logo.background_color",
    )
    normalized = {
        "schema": UNIVERSAL_AD_CONFIG_SCHEMA,
        "background": {
            key: normalize_universal_setting(f"configuration.background.{key}", background[key])
            for key in DEFAULT_CONFIG["background"]
        },
        "typography": {
            key: normalize_universal_setting(f"configuration.typography.{key}", typography[key])
            for key in DEFAULT_CONFIG["typography"]
        },
        "layout": {
            key: normalize_universal_setting(f"configuration.layout.{key}", layout[key])
            for key in DEFAULT_CONFIG["layout"]
        },
        "bullets": {
            key: normalize_universal_setting(f"configuration.bullets.{key}", bullets[key])
            for key in DEFAULT_CONFIG["bullets"]
        },
        "cta": {
            key: normalize_universal_setting(f"configuration.cta.{key}", cta[key])
            for key in DEFAULT_CONFIG["cta"]
        },
        "sticker": {
            key: normalize_universal_setting(f"configuration.sticker.{key}", sticker[key])
            for key in DEFAULT_CONFIG["sticker"]
        },
        "logo": {
            # Every draft renders the canonical Natal identity. The explicit
            # values keep deterministic version and render digests.
            "enabled": True,
            "position": normalize_universal_setting("configuration.logo.position", logo["position"]),
            "width": normalize_universal_setting("configuration.logo.width", logo["width"]),
            # The logo component has no backing-surface node.
            "background_enabled": False,
            "background_color": logo_background_color,
        },
    }
    if normalized["layout"]["content_x"] + normalized["layout"]["content_width"] > 1032:
        raise ValueError("layout.content_x plus content_width must stay inside the safe canvas")
    return normalized


def normalize_universal_content(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = set(DEFAULT_CONTENT)
    source = _object(value, expected, "Studio universal content")
    if source["schema"] != UNIVERSAL_AD_CONTENT_SCHEMA:
        raise ValueError("Studio universal content schema is invalid")

    def text(value: Any, label: str, maximum: int) -> str:
        normalized = " ".join(str(value).split())
        if not normalized or len(normalized) > maximum:
            raise ValueError(f"{label} must be a non-empty string of at most {maximum} characters")
        return normalized

    raw_bullets = source["bullets"]
    if not isinstance(raw_bullets, list) or len(raw_bullets) > 3:
        raise ValueError("Studio universal content supports at most three bullets")
    bullets = [text(item, f"content.bullets[{index}]", 100) for index, item in enumerate(raw_bullets)]
    return {
        "schema": UNIVERSAL_AD_CONTENT_SCHEMA,
        "hero_title": text(source["hero_title"], "content.hero_title", 140),
        "supporting_text": text(source["supporting_text"], "content.supporting_text", 280),
        "offer": text(source["offer"], "content.offer", 160),
        "bullets": bullets,
        "cta": text(source["cta"], "content.cta", 60),
    }


def _setting_value(
    setting_id: str, configuration: Mapping[str, Any], content: Mapping[str, Any],
) -> Any:
    parts = setting_id.split(".")
    if not parts or parts[0] not in {"configuration", "content"}:
        raise ValueError(f"Studio component setting ID is invalid: {setting_id}")
    current: Any = configuration if parts[0] == "configuration" else content
    for part in parts[1:]:
        if not isinstance(current, Mapping) or part not in current:
            raise ValueError(f"Studio component setting ID is unresolved: {setting_id}")
        current = current[part]
    return json.loads(json.dumps(current, ensure_ascii=False))


def universal_component_settings(
    configuration: Mapping[str, Any], content: Mapping[str, Any],
) -> dict[str, Any]:
    """Return canonical, agent-readable component IDs and exact selected values."""

    normalized_configuration = normalize_universal_config(configuration)
    normalized_content = normalize_universal_content(content)
    value = {
        "schema": UNIVERSAL_AD_COMPONENT_SETTINGS_SCHEMA,
        "template_id": UNIVERSAL_AD_TEMPLATE_ID,
        "template_version": UNIVERSAL_AD_TEMPLATE_VERSION,
        "configuration_schema": UNIVERSAL_AD_CONFIG_SCHEMA,
        "components": [
            {
                "component_id": declaration["component_id"],
                "role": declaration["role"],
                "node_ids": list(declaration["node_ids"]),
                "asset_slot_ids": list(declaration["asset_slot_ids"]),
                "settings": [
                    {
                        "setting_id": setting_id,
                        "value": _setting_value(
                            setting_id, normalized_configuration, normalized_content,
                        ),
                    }
                    for setting_id in declaration["setting_ids"]
                ],
            }
            for declaration in COMPONENT_DEFINITIONS
        ],
    }
    _, digest = _canonical(value)
    return {**value, "sha256": digest}


def universal_ad_catalog() -> dict[str, Any]:
    value = {
        "schema": "ptw.studio.universal-ad-catalog.v6",
        "template_id": UNIVERSAL_AD_TEMPLATE_ID,
        "template_version": UNIVERSAL_AD_TEMPLATE_VERSION,
        "semantic_roles": list(SEMANTIC_ROLES),
        "components": [
            {
                "component_id": declaration["component_id"],
                "role": declaration["role"],
                "node_ids": list(declaration["node_ids"]),
                "asset_slot_ids": list(declaration["asset_slot_ids"]),
                "setting_ids": list(declaration["setting_ids"]),
            }
            for declaration in COMPONENT_DEFINITIONS
        ],
        "asset_slots": {
            key: {
                "role": item["role"],
                "allowed_mime_types": list(item["allowed_mime_types"]),
                "description": item["description"],
            }
            for key, item in ASSET_SLOTS.items()
        },
        "setting_definitions": [
            {"setting_id": setting_id, **deepcopy(definition)}
            for setting_id, definition in UNIVERSAL_SETTING_DEFINITIONS.items()
            # Fixed identity values remain renderer-owned and do not become
            # editable controls.
            if not setting_id.startswith("configuration.logo.")
        ],
        "variation": {
            "background_modes": ["solid", "texture", "image"],
            "image_layouts": ["full", "left", "right", "top", "bottom"],
            "image_percents": [25, 75],
            "texture_presets": list(TEXTURE_PRESETS),
            "bullet_styles": ["check", "circle", "circle_outline"],
            "cta_styles": ["filled", "gradient", "reverse", "link", "outlined"],
            "cta_positions": list(CTA_POSITIONS),
            "cta_font_size": {"minimum": 18, "maximum": 42, "default": 27},
            "sticker_positions": list(STICKER_POSITIONS),
            "font_families": list(FONT_FAMILIES),
            "optional_elements": ["sticker", "bullet_list"],
        },
    }
    _, digest = _canonical(value)
    return {**value, "sha256": digest}


def _node(
    node_id: str, kind: str, props: Mapping[str, Any], *,
    binding: tuple[str, str, bool] | None = None,
) -> dict[str, Any]:
    bindings = [] if binding is None else [{
        "target": binding[0], "source": binding[1], "required": binding[2],
    }]
    return {
        "id": node_id, "type": kind, "props": dict(props), "bindings": bindings,
        "constraints": [], "responsive": [], "children": [],
    }


def _background_box(layout: str, image_percent: int) -> tuple[int, int, int, int]:
    extent = round(1080 * image_percent / 100)
    if layout == "left":
        return 0, 0, extent, 1080
    if layout == "right":
        return 1080 - extent, 0, extent, 1080
    if layout == "top":
        return 0, 0, 1080, extent
    if layout == "bottom":
        return 0, 1080 - extent, 1080, extent
    return 0, 0, 1080, 1080


def _corner_position(position: str, width: float, height: float, inset: int) -> tuple[float, float]:
    x = inset if position.endswith("left") else 1080 - inset - width
    y = inset if position.startswith("top") else 1080 - inset - height
    return x, y


def _mix_color(color: str, target: str, amount: float) -> str:
    first = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
    second = tuple(int(target[index:index + 2], 16) for index in (1, 3, 5))
    mixed = tuple(round(start * (1 - amount) + end * amount) for start, end in zip(first, second))
    return "#" + "".join(f"{channel:02X}" for channel in mixed)


def _gradient_end(color: str) -> str:
    channels = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
    target = "#000000" if sum(channels) > 420 else "#FFFFFF"
    return _mix_color(color, target, 0.32)


def _sticker_position(
    position: str, width: float, height: float, *, content_x: float, content_width: float,
    hero_y: float, hero_height: float, bullet_y: float, bullet_height: float,
    cta_x: float, cta_y: float, cta_width: float, offset_right: float, offset_bottom: float,
) -> tuple[float, float]:
    if position in {"top_left", "top_right", "bottom_left", "bottom_right"}:
        x, y = _corner_position(position, width, height, 54)
    elif position == "right_edge":
        x, y = 1080 - width * 0.72, (1080 - height) / 2
    elif position == "bottom_edge":
        x, y = (1080 - width) / 2, 1080 - height * 0.72
    else:
        anchor_right = content_x + content_width
        if position == "hero_title":
            anchor_top, anchor_bottom = hero_y, hero_y + hero_height
        elif position == "bullet_list":
            anchor_top, anchor_bottom = bullet_y, bullet_y + bullet_height
        else:
            anchor_right = cta_x + cta_width
            anchor_top, anchor_bottom = cta_y, cta_y + 82
        x = anchor_right - width * 0.15
        y = (anchor_top + anchor_bottom) / 2 - height * 0.5
    return x - offset_right, y - offset_bottom


def universal_alignment_rectangle(config: Mapping[str, Any]) -> dict[str, float]:
    """Return the shared logo, copy, and CTA alignment rectangle in canvas pixels."""

    normalized = normalize_universal_config(config)
    layout = normalized["layout"]
    content_x = layout["content_x"]
    if normalized["typography"]["alignment"] == "center":
        content_x = round((1080 - layout["content_width"]) / 2)
    alignment_right = max(
        content_x + layout["content_width"],
        1080 - content_x,
    )
    alignment_bottom = 1026
    return {
        "x": float(content_x),
        "y": float(layout["content_y"]),
        "width": float(alignment_right - content_x),
        "height": float(alignment_bottom - layout["content_y"]),
    }


def build_universal_template(config: Mapping[str, Any], content: Mapping[str, Any]) -> PrimitiveTemplate:
    config = normalize_universal_config(config)
    content = normalize_universal_content(content)
    background, typography = config["background"], config["typography"]
    layout, sticker, logo = config["layout"], config["sticker"], config["logo"]
    cta = config["cta"]
    bullets_enabled = config["bullets"]["enabled"] and bool(content["bullets"])
    background_asset = {
        "texture": "background_texture", "image": "background_image",
    }.get(background["mode"])
    bx, by, bw, bh = _background_box(
        background["image_layout"], background["image_percent"],
    )
    alignment_rectangle = universal_alignment_rectangle(config)
    content_x = alignment_rectangle["x"]
    alignment_top = alignment_rectangle["y"]
    alignment_right = alignment_rectangle["x"] + alignment_rectangle["width"]
    alignment_bottom = alignment_rectangle["y"] + alignment_rectangle["height"]
    logo_height = logo["width"] * 0.42
    object_width = sticker["width"] * sticker["object_scale"]
    object_height = object_width * 0.58
    logo_x = (
        alignment_rectangle["x"]
        if logo["position"] == "top_left" else alignment_right - logo["width"]
    )
    logo_y = alignment_top
    if (
        sticker["enabled"] and sticker["position"].startswith("top")
        and logo["position"] == sticker["position"]
    ):
        logo_y += object_height + 28
    logo_collision_x = logo_x
    logo_collision_y = logo_y
    logo_collision_width = logo["width"]
    logo_collision_height = logo_height
    content_y = layout["content_y"]
    if (
        logo["enabled"]
        and content_x < logo_collision_x + logo_collision_width
        and content_x + layout["content_width"] > logo_collision_x
    ):
        content_y = max(
            content_y, math.ceil(logo_collision_y + logo_collision_height + 24),
        )
    hero_height = max(170, round(typography["hero_size"] * 2.25))
    supporting_height = max(96, round(typography["supporting_size"] * 3.2))
    bullet_count = len(content["bullets"]) if bullets_enabled else 0
    bullet_step = max(42, round(typography["supporting_size"] * 1.45))
    offer_height = max(62, round(typography["supporting_size"] * 2.0))
    gap_count = 4 if bullet_count else 3
    ideal_before_cta = (
        hero_height + supporting_height + offer_height + bullet_step * bullet_count
        + layout["gap"] * gap_count
    )
    available_before_cta = alignment_bottom - 82 - content_y
    vertical_scale = min(1.0, available_before_cta / ideal_before_cta)
    hero_height = round(hero_height * vertical_scale)
    supporting_height = round(supporting_height * vertical_scale)
    offer_height = round(offer_height * vertical_scale)
    bullet_step = round(bullet_step * vertical_scale)
    effective_gap = round(layout["gap"] * vertical_scale)
    supporting_y = content_y + hero_height + effective_gap
    offer_y = supporting_y + supporting_height + effective_gap
    bullet_y = offer_y + offer_height + effective_gap
    bullet_space = bullet_step * bullet_count + effective_gap if bullets_enabled else 0
    flowing_cta_y = bullet_y + bullet_space
    common_text = {
        "position": "absolute", "x": content_x, "width": layout["content_width"],
        "font_family": typography["font_family"], "color": typography["text_color"],
        "text_align": typography["alignment"], "text_fit": "shrink", "z_index": 5,
    }
    children = [
        _node("background_media", "image", {
            "position": "absolute", "x": bx, "y": by, "width": bw, "height": bh,
            "z_index": 0, "asset": background_asset, "fit": background["image_fit"],
            "focal_x": background["focal_x"], "focal_y": background["focal_y"],
            "opacity": (
                background["texture_intensity"] if background["mode"] == "texture" else 1
            ),
            "visible": (
                background_asset is not None
                and (background["mode"] != "texture" or background["texture_intensity"] > 0)
            ),
        }),
        _node("readability_overlay", "shape", {
            "position": "absolute", "x": 0, "y": 0, "width": 1080, "height": 1080,
            "z_index": 1, "fill": background["overlay_color"],
            "opacity": background["overlay_opacity"], "visible": background["overlay_opacity"] > 0,
        }),
        _node("hero_title", "text", {
            **common_text, "y": content_y, "height": hero_height,
            "font_size": typography["hero_size"], "min_font_size": 44,
            "font_weight": typography["hero_weight"], "line_height": 0.94,
            "letter_spacing": -2.0, "max_lines": 3,
        }, binding=("text", "content.hero_title", True)),
        _node("supporting_text", "text", {
            **common_text, "y": supporting_y, "height": supporting_height,
            "font_size": typography["supporting_size"], "min_font_size": 18,
            "font_weight": 500, "line_height": 1.18, "max_lines": 4,
        }, binding=("text", "content.supporting_text", True)),
        _node("offer", "text", {
            **common_text, "y": offer_y, "height": offer_height,
            "font_size": max(22, typography["supporting_size"] - 2), "min_font_size": 18,
            "font_weight": 800, "line_height": 1.1, "max_lines": 2,
        }, binding=("text", "content.offer", True)),
    ]
    marker_width = 38
    marker_gap = 12
    bullet_group_inset = 0 if typography["alignment"] == "left" else round(layout["content_width"] * 0.12)
    bullet_x = content_x + bullet_group_inset
    bullet_width = layout["content_width"] - bullet_group_inset * 2
    for index in range(3):
        visible = bullets_enabled and index < len(content["bullets"])
        children.append(_node(f"bullet_marker_{index + 1}", "text", {
            **common_text, "x": bullet_x, "y": bullet_y + index * bullet_step,
            "width": marker_width, "height": bullet_step, "font_family": "Inter",
            "font_size": max(20, typography["supporting_size"] - 4), "min_font_size": 16,
            "font_weight": 700, "line_height": 1.1, "max_lines": 1,
            "text_align": "left", "visible": visible,
        }, binding=("text", f"content.bullet_marker_{index + 1}", False)))
        children.append(_node(f"bullet_{index + 1}", "text", {
            **common_text, "x": bullet_x + marker_width + marker_gap,
            "y": bullet_y + index * bullet_step,
            "width": bullet_width - marker_width - marker_gap, "height": bullet_step,
            "font_family": typography["benefits_font_family"], "text_align": "left",
            "font_size": max(20, typography["supporting_size"] - 4), "min_font_size": 16,
            "font_weight": 600, "line_height": 1.1, "max_lines": 2,
            "visible": visible,
        }, binding=("text", f"content.bullet_{index + 1}", False)))
    # Protected CTA copy can be up to 60 characters. Keep the one-line button
    # useful even in the narrow 500px editorial content column.
    cta_width = min(520, max(440, round(layout["content_width"] * 0.75)))
    if cta["position"] == "bottom_left":
        cta_x, cta_y = alignment_rectangle["x"], alignment_bottom - 82
    elif cta["position"] == "bottom_right":
        cta_x, cta_y = alignment_right - cta_width, alignment_bottom - 82
    else:
        cta_x = content_x if typography["alignment"] == "left" else round((1080 - cta_width) / 2)
        cta_y = flowing_cta_y
    cta_style = cta["style"]
    cta_background = cta["background_color"]
    cta_text = cta["text_color"]
    cta_surface: dict[str, Any] = {
        "background_color": cta_background,
        "background_gradient": [], "border_color": None, "border_width": 0,
        "label_color": cta_text, "radius": cta["radius"],
    }
    if cta_style == "gradient":
        cta_surface.update({
            "background_color": None,
            "background_gradient": [cta_background, _gradient_end(cta_background)],
        })
    elif cta_style == "reverse":
        cta_surface.update({"background_color": cta_text, "label_color": cta_background})
    elif cta_style == "link":
        cta_surface.update({"background_color": None, "radius": 0})
    elif cta_style == "outlined":
        cta_surface.update({
            "background_color": None, "border_color": cta_background, "border_width": 4,
        })
    bullet_anchor_height = bullet_step * bullet_count if bullet_count else supporting_height
    bullet_anchor_y = bullet_y if bullet_count else supporting_y
    object_x, object_y = _sticker_position(
        sticker["position"], object_width, object_height,
        content_x=content_x, content_width=layout["content_width"],
        hero_y=content_y, hero_height=hero_height,
        bullet_y=bullet_anchor_y, bullet_height=bullet_anchor_height,
        cta_x=cta_x, cta_y=cta_y, cta_width=cta_width,
        offset_right=sticker["offset_right"], offset_bottom=sticker["offset_bottom"],
    )
    children.extend([
        _node("cta", "button", {
            "position": "absolute", "x": cta_x, "y": cta_y, "width": cta_width, "height": 82,
            "z_index": 6, **cta_surface,
            "font_family": typography["font_family"], "font_size": cta["font_size"],
            "min_font_size": 18,
            "font_weight": 800, "text_align": "center", "vertical_align": "center",
            "text_fit": "shrink", "max_lines": 2,
            "padding": {"top": 10, "right": 24, "bottom": 10, "left": 24},
        }, binding=("label", "content.cta", True)),
        _node("sticker_object", "image", {
            "position": "absolute", "x": object_x, "y": object_y,
            "width": object_width, "height": object_height, "z_index": 9,
            "asset": "sticker_object", "fit": "contain", "rotation": sticker["rotation"],
            "alpha_outline_color": "#FFFFFF", "alpha_outline_width_ratio": 0.06,
            "alpha_outline_shadow_color": "#00000020",
            "alpha_outline_shadow_blur": 2, "alpha_outline_shadow_y": 2,
            "visible": sticker["enabled"],
        }),
        _node("logo", "image", {
            "position": "absolute", "x": logo_x, "y": logo_y,
            "width": logo["width"], "height": logo_height, "z_index": 10,
            "asset": "logo", "fit": "contain", "visible": logo["enabled"],
        }),
    ])
    document = {
        "schema": "ptw.studio.primitive-template.v1",
        "template_id": UNIVERSAL_AD_TEMPLATE_ID,
        "template_type": "universal_ad",
        "version": UNIVERSAL_AD_TEMPLATE_VERSION,
        "status": "approved",
        "root": {
            "id": "canvas", "type": "frame",
            "props": {
                "width": 1080, "height": 1080, "background_color": background["color"],
                "overflow": "clip",
            },
            "bindings": [], "constraints": [], "responsive": [], "children": children,
        },
        "semantic_roles": {
            "background": ["canvas", "background_media", "readability_overlay"],
            "sticker": ["sticker_object"],
            "hero_title": ["hero_title"],
            "supporting_text": ["supporting_text"],
            "offer": ["offer"],
            "bullet_list": [
                "bullet_marker_1", "bullet_1", "bullet_marker_2", "bullet_2",
                "bullet_marker_3", "bullet_3",
            ],
            "cta": ["cta"],
            "logo": ["logo"],
        },
        "assets": {
            key: {
                "kind": "image", "allowed_mime_types": list(item["allowed_mime_types"]),
                "required": False, "provenance": item["description"],
            }
            for key, item in ASSET_SLOTS.items()
        } | {
            "background_texture": {
                "kind": "image", "allowed_mime_types": ["image/png"], "required": False,
                "provenance": "Deterministic built-in grain or mineral texture generated by Studio.",
            },
        },
        "rules": [
            *[
                {"id": f"role_{role}", "scope": "template", "type": "required_role", "params": {"role": role}}
                for role in SEMANTIC_ROLES
            ],
            {"id": "fixed_tree", "scope": "template", "type": "max_nodes", "params": {"maximum": 17}},
        ],
        "provenance": {
            "base_template_id": None, "base_version": None, "base_sha256": None,
            "reference_ids": [],
            "change_note": "Canonical single universal-ad structure; variation is configuration-only.",
        },
    }
    return PrimitiveTemplate.from_dict(document)


def semantic_data(config: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, str]:
    config = normalize_universal_config(config)
    content = normalize_universal_content(content)
    data = {
        "content.hero_title": content["hero_title"],
        "content.supporting_text": content["supporting_text"],
        "content.offer": content["offer"],
        "content.cta": content["cta"],
    }
    marker = {
        "check": "✓", "circle": "●", "circle_outline": "○",
    }[config["bullets"]["style"]]
    for index, item in enumerate(content["bullets"], 1):
        data[f"content.bullet_marker_{index}"] = marker
        data[f"content.bullet_{index}"] = item
    return data


@lru_cache(maxsize=len(TEXTURE_PRESETS))
def texture_asset(preset: str) -> dict[str, Any]:
    """Return a small deterministic transparent texture for the solid base."""
    from PIL import Image, ImageDraw

    preset = _enum(preset, TEXTURE_PRESETS, "background.texture")
    rng = random.Random(f"ptw-universal-{preset}-v2")
    canvas_size = 192 if preset == "grain" else 540
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if preset == "grain":
        for _ in range(4100):
            value = rng.choice((0, 255))
            alpha = rng.randint(3, 20)
            draw.point((rng.randrange(192), rng.randrange(192)), fill=(value, value, value, alpha))
    elif preset == "stone":
        for _ in range(1450):
            x, y = rng.randrange(canvas_size), rng.randrange(canvas_size)
            radius_x, radius_y = rng.randint(1, 9), rng.randint(1, 6)
            value = rng.choice((18, 38, 68, 178, 212, 238))
            alpha = rng.randint(7, 28)
            draw.ellipse(
                (x - radius_x, y - radius_y, x + radius_x, y + radius_y),
                fill=(value, value, value, alpha),
            )
        for _ in range(18):
            start_y = rng.randint(-40, canvas_size + 40)
            points = [(0, start_y)]
            drift = 0
            for x in range(54, canvas_size + 54, 54):
                drift += rng.randint(-18, 18)
                points.append((x, start_y + drift))
            value = rng.choice((32, 224))
            draw.line(
                points, fill=(value, value, value, rng.randint(11, 25)),
                width=rng.choice((1, 1, 2)),
            )
        for _ in range(5200):
            value = rng.choice((0, 255))
            draw.point(
                (rng.randrange(canvas_size), rng.randrange(canvas_size)),
                fill=(value, value, value, rng.randint(3, 13)),
            )
    elif preset == "marble":
        for _ in range(14):
            start_y = rng.randint(-80, canvas_size + 80)
            points = [(0, start_y)]
            drift = 0
            for x in range(36, canvas_size + 36, 36):
                drift += rng.randint(-22, 22)
                points.append((x, start_y + drift))
            tone = rng.choice((34, 52, 210, 232))
            draw.line(points, fill=(tone, tone, tone, rng.randint(10, 24)), width=rng.randint(3, 7))
            draw.line(points, fill=(tone, tone, tone, rng.randint(20, 42)), width=1)
        for _ in range(2600):
            tone = rng.choice((24, 235))
            draw.point(
                (rng.randrange(canvas_size), rng.randrange(canvas_size)),
                fill=(tone, tone, tone, rng.randint(2, 9)),
            )
    elif preset == "concrete":
        for _ in range(3100):
            x, y = rng.randrange(canvas_size), rng.randrange(canvas_size)
            radius = rng.randint(1, 7)
            tone = rng.choice((24, 48, 76, 188, 216, 240))
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(tone, tone, tone, rng.randint(3, 17)),
            )
        for _ in range(520):
            x, y = rng.randrange(canvas_size), rng.randrange(canvas_size)
            draw.ellipse((x, y, x + rng.randint(1, 4), y + rng.randint(1, 3)), fill=(12, 12, 12, rng.randint(16, 36)))
    elif preset == "granite":
        for _ in range(6200):
            x, y = rng.randrange(canvas_size), rng.randrange(canvas_size)
            tone = rng.choice((12, 36, 62, 118, 176, 220, 246))
            radius = rng.choice((1, 1, 1, 2, 3))
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(tone, tone, tone, rng.randint(7, 31)),
            )
        for _ in range(130):
            x, y = rng.randrange(canvas_size), rng.randrange(canvas_size)
            draw.ellipse((x - 4, y - 2, x + 4, y + 2), fill=(238, 238, 238, rng.randint(22, 48)))
    elif preset == "slate":
        for offset in range(-canvas_size, canvas_size * 2, 22):
            jitter = rng.randint(-6, 6)
            tone = rng.choice((28, 54, 188, 220))
            draw.line(
                ((-30, offset + jitter), (canvas_size + 30, offset - 86 + jitter)),
                fill=(tone, tone, tone, rng.randint(7, 22)), width=rng.choice((1, 1, 2)),
            )
        for _ in range(2600):
            tone = rng.choice((16, 228))
            draw.point(
                (rng.randrange(canvas_size), rng.randrange(canvas_size)),
                fill=(tone, tone, tone, rng.randint(3, 12)),
            )
    else:  # travertine
        for y in range(0, canvas_size, 9):
            tone = rng.choice((42, 70, 205, 232))
            draw.line(
                ((0, y + rng.randint(-2, 2)), (canvas_size, y + rng.randint(-2, 2))),
                fill=(tone, tone, tone, rng.randint(4, 15)), width=rng.choice((1, 1, 2)),
            )
        for _ in range(760):
            x, y = rng.randrange(canvas_size), rng.randrange(canvas_size)
            radius_x, radius_y = rng.randint(2, 11), rng.randint(1, 3)
            tone = rng.choice((22, 48, 214))
            draw.ellipse(
                (x - radius_x, y - radius_y, x + radius_x, y + radius_y),
                fill=(tone, tone, tone, rng.randint(8, 30)),
            )
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    data = output.getvalue()
    return {"bytes": data, "mime_type": "image/png", "sha256": hashlib.sha256(data).hexdigest()}


def isolate_object(data: bytes) -> bytes:
    """Create a deterministic soft-alpha cutout for simple Pexels object shots.

    The transform intentionally targets backgrounds close to the image-edge
    color. It is bounded and reproducible; complex scenes fail instead of being
    accepted as a rectangular or non-photographic sticker.
    """
    from PIL import Image, ImageStat

    with Image.open(BytesIO(data)) as original:
        image = original.convert("RGBA")
    width, height = image.size
    border = max(1, min(width, height) // 40)
    samples = [
        image.crop((0, 0, border, border)),
        image.crop((width - border, 0, width, border)),
        image.crop((0, height - border, border, height)),
        image.crop((width - border, height - border, width, height)),
    ]
    means = [ImageStat.Stat(sample.convert("RGB")).mean for sample in samples]
    background = tuple(sum(mean[channel] for mean in means) / len(means) for channel in range(3))
    pixels = []
    visible = 0
    for red, green, blue, original_alpha in image.getdata():
        distance = math.sqrt(
            (red - background[0]) ** 2 + (green - background[1]) ** 2 + (blue - background[2]) ** 2
        )
        if distance <= 24:
            alpha = 0
        elif distance >= 92:
            alpha = original_alpha
        else:
            alpha = round(original_alpha * (distance - 24) / 68)
        visible += alpha > 24
        pixels.append((red, green, blue, alpha))
    if visible < width * height * 0.04:
        raise ValueError("Pexels sticker isolation removed almost the entire object; choose another source")
    image.putdata(pixels)
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Pexels sticker isolation produced no visible object")
    image = image.crop(bounds)
    alpha = image.getchannel("A")
    total = image.width * image.height
    transparent_ratio = sum(alpha.histogram()[:25]) / total
    corner = max(1, min(image.size) // 20)
    corner_means = [
        ImageStat.Stat(alpha.crop(box)).mean[0]
        for box in (
            (0, 0, corner, corner),
            (image.width - corner, 0, image.width, corner),
            (0, image.height - corner, corner, image.height),
            (image.width - corner, image.height - corner, image.width, image.height),
        )
    ]
    if transparent_ratio < 0.08 or sum(value <= 32 for value in corner_means) < 3:
        raise ValueError(
            "Pexels sticker isolation retained a rectangular scene; choose a simpler object source"
        )
    if bounds[0] <= 0 or bounds[1] <= 0 or bounds[2] >= width or bounds[3] >= height:
        raise ValueError(
            "Pexels sticker isolation retained an edge-cropped subject; "
            "choose a fully visible object source"
        )
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()
