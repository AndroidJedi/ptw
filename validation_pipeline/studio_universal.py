"""One bounded universal-ad configuration rendered by Studio primitives.

The primitive catalog remains an internal rendering mechanism.  This module is
the public Studio design contract: stable semantic roles, three fixed asset
slots, and a deliberately small set of settings with visible creative impact.
"""

from __future__ import annotations

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
UNIVERSAL_AD_CONFIG_SCHEMA = "ptw.studio.universal-ad-config.v1"
UNIVERSAL_AD_VERSION_SCHEMA = "ptw.studio.universal-ad-version.v1"
UNIVERSAL_AD_WORKSPACE_SCHEMA = "ptw.studio.universal-ad-workspace.v1"
UNIVERSAL_AD_TEMPLATE_VERSION = 3

SEMANTIC_ROLES = (
    "background", "sticker", "hero_title", "supporting_text",
    "bullet_list", "cta", "logo",
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
        "description": "Optional isolated object rendered with a die-cut alpha contour.",
    },
    "logo": {
        "role": "logo",
        "allowed_mime_types": ("image/png", "image/webp"),
        "description": "Optional transparent brand mark.",
    },
}

DEFAULT_CONFIG: dict[str, Any] = {
    "schema": UNIVERSAL_AD_CONFIG_SCHEMA,
    "background": {
        "mode": "image",
        "color": "#10233F",
        "texture": "paper",
        "image_layout": "full",
        "image_fit": "cover",
        "focal_x": 0.5,
        "focal_y": 0.5,
        "overlay_color": "#07182E",
        "overlay_opacity": 0.56,
    },
    "typography": {
        "font_family": "Inter",
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
        "marker": "✓",
    },
    "cta": {
        "background_color": "#FFD84D",
        "text_color": "#10233F",
        "radius": 24,
    },
    "sticker": {
        "enabled": True,
        "position": "bottom_right",
        "rotation": 5,
        "paper_width": 300,
        "paper_color": "#FFF5D1",
        "object_scale": 0.9,
    },
    "logo": {
        "enabled": False,
        "position": "top_left",
        "width": 160,
    },
}

DEFAULT_CONTENT: dict[str, Any] = {
    "hero_title": "ІНВЕСТУВАТИ В УКРАЇНІ — ПРОСТІШЕ",
    "supporting_text": "Аналізуємо ваші цілі й підказуємо інструменти, що відповідають саме вам.",
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
    marker = str(bullets["marker"])
    if not 1 <= len(marker) <= 3 or "\n" in marker:
        raise ValueError("bullets.marker must contain one compact marker")
    normalized = {
        "schema": UNIVERSAL_AD_CONFIG_SCHEMA,
        "background": {
            "mode": _enum(background["mode"], ("solid", "texture", "image"), "background.mode"),
            "color": _color(background["color"], "background.color"),
            "texture": _enum(background["texture"], ("paper", "grain"), "background.texture"),
            "image_layout": _enum(
                background["image_layout"], ("full", "left", "right", "top", "bottom"),
                "background.image_layout",
            ),
            "image_fit": _enum(background["image_fit"], ("cover", "contain"), "background.image_fit"),
            "focal_x": _number(background["focal_x"], "background.focal_x", 0, 1),
            "focal_y": _number(background["focal_y"], "background.focal_y", 0, 1),
            "overlay_color": _color(background["overlay_color"], "background.overlay_color"),
            "overlay_opacity": _number(background["overlay_opacity"], "background.overlay_opacity", 0, 0.85),
        },
        "typography": {
            "font_family": _enum(typography["font_family"], ("Inter", "Roboto Condensed"), "typography.font_family"),
            "hero_size": _integer(typography["hero_size"], "typography.hero_size", 64, 180),
            "hero_weight": _integer(typography["hero_weight"], "typography.hero_weight", 400, 900),
            "supporting_size": _integer(typography["supporting_size"], "typography.supporting_size", 22, 52),
            "text_color": _color(typography["text_color"], "typography.text_color"),
            "alignment": _enum(typography["alignment"], ("left", "center"), "typography.alignment"),
        },
        "layout": {
            "content_x": _integer(layout["content_x"], "layout.content_x", 48, 520),
            "content_y": _integer(layout["content_y"], "layout.content_y", 72, 360),
            "content_width": _integer(layout["content_width"], "layout.content_width", 420, 936),
            "gap": _integer(layout["gap"], "layout.gap", 8, 56),
        },
        "bullets": {"enabled": _boolean(bullets["enabled"], "bullets.enabled"), "marker": marker},
        "cta": {
            "background_color": _color(cta["background_color"], "cta.background_color"),
            "text_color": _color(cta["text_color"], "cta.text_color"),
            "radius": _integer(cta["radius"], "cta.radius", 0, 40),
        },
        "sticker": {
            "enabled": _boolean(sticker["enabled"], "sticker.enabled"),
            "position": _enum(
                sticker["position"], ("top_left", "top_right", "bottom_left", "bottom_right"),
                "sticker.position",
            ),
            "rotation": _number(sticker["rotation"], "sticker.rotation", -18, 18),
            "paper_width": _integer(sticker["paper_width"], "sticker.paper_width", 180, 480),
            "paper_color": _color(sticker["paper_color"], "sticker.paper_color"),
            "object_scale": _number(sticker["object_scale"], "sticker.object_scale", 0.45, 1.25),
        },
        "logo": {
            "enabled": _boolean(logo["enabled"], "logo.enabled"),
            "position": _enum(logo["position"], ("top_left", "top_right"), "logo.position"),
            "width": _integer(logo["width"], "logo.width", 80, 280),
        },
    }
    if normalized["layout"]["content_x"] + normalized["layout"]["content_width"] > 1032:
        raise ValueError("layout.content_x plus content_width must stay inside the safe canvas")
    return normalized


def normalize_universal_content(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = set(DEFAULT_CONTENT)
    source = _object(value, expected, "Studio universal content")

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
        "hero_title": text(source["hero_title"], "content.hero_title", 140),
        "supporting_text": text(source["supporting_text"], "content.supporting_text", 280),
        "bullets": bullets,
        "cta": text(source["cta"], "content.cta", 60),
    }


def universal_content_from_generation(
    candidate: Mapping[str, Any], *, brief: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Adapt existing Candidate/Product Brief copy without another generation call."""
    if not isinstance(candidate, Mapping):
        raise ValueError("Studio candidate content must be an object")
    supporting = candidate.get("primary_text") or candidate.get("supporting_text")
    benefits = [] if brief is None else brief.get("key_benefits") or []
    if not isinstance(benefits, list):
        raise ValueError("Studio Product Brief key benefits must be a list")
    return normalize_universal_content({
        "hero_title": candidate.get("headline") or "",
        "supporting_text": supporting or "",
        "bullets": benefits[:3],
        "cta": candidate.get("cta") or "",
    })


def universal_ad_catalog() -> dict[str, Any]:
    value = {
        "schema": "ptw.studio.universal-ad-catalog.v1",
        "template_id": UNIVERSAL_AD_TEMPLATE_ID,
        "template_version": UNIVERSAL_AD_TEMPLATE_VERSION,
        "semantic_roles": list(SEMANTIC_ROLES),
        "asset_slots": {
            key: {
                "role": item["role"],
                "allowed_mime_types": list(item["allowed_mime_types"]),
                "description": item["description"],
            }
            for key, item in ASSET_SLOTS.items()
        },
        "variation": {
            "background_modes": ["solid", "texture", "image"],
            "image_layouts": ["full", "left", "right", "top", "bottom"],
            "texture_presets": ["paper", "grain"],
            "font_families": ["Inter", "Roboto Condensed"],
            "optional_elements": ["sticker", "bullet_list", "logo"],
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


def _background_box(layout: str) -> tuple[int, int, int, int]:
    if layout == "left":
        return 0, 0, 594, 1080
    if layout == "right":
        return 486, 0, 594, 1080
    if layout == "top":
        return 0, 0, 1080, 594
    if layout == "bottom":
        return 0, 486, 1080, 594
    return 0, 0, 1080, 1080


def _corner_position(position: str, width: float, height: float, inset: int) -> tuple[float, float]:
    x = inset if position.endswith("left") else 1080 - inset - width
    y = inset if position.startswith("top") else 1080 - inset - height
    return x, y


def build_universal_template(config: Mapping[str, Any], content: Mapping[str, Any]) -> PrimitiveTemplate:
    config = normalize_universal_config(config)
    content = normalize_universal_content(content)
    background, typography = config["background"], config["typography"]
    layout, sticker, logo = config["layout"], config["sticker"], config["logo"]
    bullets_enabled = config["bullets"]["enabled"] and bool(content["bullets"])
    background_asset = {
        "texture": "background_texture", "image": "background_image",
    }.get(background["mode"])
    bx, by, bw, bh = _background_box(background["image_layout"])
    content_x = layout["content_x"]
    if typography["alignment"] == "center":
        content_x = round((1080 - layout["content_width"]) / 2)
    hero_height = max(170, round(typography["hero_size"] * 2.25))
    supporting_height = max(96, round(typography["supporting_size"] * 3.2))
    bullet_count = len(content["bullets"]) if bullets_enabled else 0
    bullet_step = max(42, round(typography["supporting_size"] * 1.45))
    gap_count = 3 if bullet_count else 2
    ideal_before_cta = (
        hero_height + supporting_height + bullet_step * bullet_count
        + layout["gap"] * gap_count
    )
    available_before_cta = 1024 - 82 - layout["content_y"]
    vertical_scale = min(1.0, available_before_cta / ideal_before_cta)
    hero_height = round(hero_height * vertical_scale)
    supporting_height = round(supporting_height * vertical_scale)
    bullet_step = round(bullet_step * vertical_scale)
    effective_gap = round(layout["gap"] * vertical_scale)
    supporting_y = layout["content_y"] + hero_height + effective_gap
    bullet_y = supporting_y + supporting_height + effective_gap
    bullet_space = bullet_step * bullet_count + effective_gap if bullets_enabled else 0
    cta_y = bullet_y + bullet_space
    sticker_height = sticker["paper_width"] * 0.58
    sticker_x, sticker_y = _corner_position(sticker["position"], sticker["paper_width"], sticker_height, 54)
    object_width = sticker["paper_width"] * sticker["object_scale"]
    object_height = sticker_height * sticker["object_scale"]
    object_x = sticker_x + (sticker["paper_width"] - object_width) / 2
    object_y = sticker_y + (sticker_height - object_height) / 2
    logo_height = logo["width"] * 0.42
    logo_x, logo_y = _corner_position(logo["position"], logo["width"], logo_height, 54)
    if sticker["enabled"] and sticker["position"].startswith("top") and logo["position"] == sticker["position"]:
        logo_y = sticker_y + sticker_height + 28
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
            "visible": background_asset is not None,
        }),
        _node("readability_overlay", "shape", {
            "position": "absolute", "x": 0, "y": 0, "width": 1080, "height": 1080,
            "z_index": 1, "fill": background["overlay_color"],
            "opacity": background["overlay_opacity"], "visible": background["overlay_opacity"] > 0,
        }),
        _node("hero_title", "text", {
            **common_text, "y": layout["content_y"], "height": hero_height,
            "font_size": typography["hero_size"], "min_font_size": 44,
            "font_weight": typography["hero_weight"], "line_height": 0.94,
            "letter_spacing": -2.0, "max_lines": 3,
        }, binding=("text", "content.hero_title", True)),
        _node("supporting_text", "text", {
            **common_text, "y": supporting_y, "height": supporting_height,
            "font_size": typography["supporting_size"], "min_font_size": 18,
            "font_weight": 500, "line_height": 1.18, "max_lines": 4,
        }, binding=("text", "content.supporting_text", True)),
    ]
    for index in range(3):
        children.append(_node(f"bullet_{index + 1}", "text", {
            **common_text, "y": bullet_y + index * bullet_step, "height": bullet_step,
            "font_size": max(20, typography["supporting_size"] - 4), "min_font_size": 16,
            "font_weight": 600, "line_height": 1.1, "max_lines": 2,
            "visible": bullets_enabled and index < len(content["bullets"]),
        }, binding=("text", f"content.bullet_{index + 1}", False)))
    cta_width = min(420, max(230, round(layout["content_width"] * 0.5)))
    cta_x = content_x if typography["alignment"] == "left" else round((1080 - cta_width) / 2)
    children.extend([
        _node("cta", "button", {
            "position": "absolute", "x": cta_x, "y": cta_y, "width": cta_width, "height": 82,
            "z_index": 6, "background_color": config["cta"]["background_color"],
            "label_color": config["cta"]["text_color"], "radius": config["cta"]["radius"],
            "font_family": typography["font_family"], "font_size": 27, "min_font_size": 18,
            "font_weight": 800, "text_align": "center", "vertical_align": "center",
            "text_fit": "shrink", "max_lines": 1,
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
            "bullet_list": ["bullet_1", "bullet_2", "bullet_3"],
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
                "provenance": "Deterministic built-in paper or grain texture generated by Studio.",
            },
        },
        "rules": [
            *[
                {"id": f"role_{role}", "scope": "template", "type": "required_role", "params": {"role": role}}
                for role in SEMANTIC_ROLES
            ],
            {"id": "fixed_tree", "scope": "template", "type": "max_nodes", "params": {"maximum": 13}},
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
        "content.cta": content["cta"],
    }
    marker = config["bullets"]["marker"]
    for index, item in enumerate(content["bullets"], 1):
        data[f"content.bullet_{index}"] = f"{marker}  {item}"
    return data


@lru_cache(maxsize=2)
def texture_asset(preset: str) -> dict[str, Any]:
    """Return a small deterministic transparent texture for the solid base."""
    from PIL import Image, ImageDraw

    preset = _enum(preset, ("paper", "grain"), "background.texture")
    rng = random.Random(f"ptw-universal-{preset}-v1")
    image = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if preset == "paper":
        for _ in range(1650):
            value = rng.choice((18, 26, 34, 225, 235, 245))
            alpha = rng.randint(4, 16)
            x, y = rng.randrange(192), rng.randrange(192)
            draw.point((x, y), fill=(value, value, value, alpha))
        for _ in range(42):
            y = rng.randrange(192)
            draw.line((0, y, 192, y + rng.choice((-1, 0, 1))), fill=(80, 70, 45, 7), width=1)
    else:
        for _ in range(4100):
            value = rng.choice((0, 255))
            alpha = rng.randint(3, 20)
            draw.point((rng.randrange(192), rng.randrange(192)), fill=(value, value, value, alpha))
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    data = output.getvalue()
    return {"bytes": data, "mime_type": "image/png", "sha256": hashlib.sha256(data).hexdigest()}


def isolate_object(data: bytes) -> bytes:
    """Create a deterministic soft-alpha cutout for simple Pexels object shots.

    The transform intentionally targets backgrounds close to the image-edge
    color.  It is bounded and reproducible; complex scenes should use an owner-
    supplied transparent PNG instead of pretending the cutout is reliable.
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
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()
