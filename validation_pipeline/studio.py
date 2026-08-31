"""Strict static-social recipe contract and deterministic Result renderer."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from uuid import UUID

from .domain import RATING_PATTERN, TESTIMONIAL_PATTERN, UNSUPPLIED_PROOF_PATTERN
from .natal_brand import NATAL_FONT_PATH


COLOR_SOURCE = "https://www.manypixels.co/blog/social-media-design/instagram-color"
ADS_SOURCE = "https://www.manypixels.co/blog/social-media-design/best-instagram-ads"
RENDERER_VERSION = "ptw-result-instagram-renderer-v2"
RENDERER_CONTRACT = {
    "version": RENDERER_VERSION,
    "canvas": [1080, 1080],
    "format": "image/jpeg",
    "font": "Natal Inter variable",
    "handlers": ["media", "shape", "text"],
    "quantization": "normalized geometry 0.001; typography 1px/100 weight",
}
TIKTOK_RENDERER_VERSION = "ptw-result-tiktok-photo-renderer-v1"
TIKTOK_RENDERER_CONTRACT = {
    "version": TIKTOK_RENDERER_VERSION,
    "canvas": [1080, 1920],
    "format": "image/jpeg",
    "font": "Natal Inter variable",
    "handlers": ["media", "shape", "text"],
    "quantization": "normalized geometry 0.001; typography 1px/100 weight",
}
MAX_IMAGE_BYTES = 12 * 1024 * 1024
SUPPORTED_FONTS = {
    "Inter": NATAL_FONT_PATH,
    "DejaVu Sans": Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    "DejaVu Serif": Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    "DejaVu Mono": Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
}
STUDIO_PREVIEW_FONTS = {
    # Historical engineering benchmarks still replay Roboto; Universal Studio
    # does not expose it in its owner-selectable FONT_FAMILIES contract.
    "Roboto Condensed": Path(__file__).with_name("studio_assets") / "fonts" / "Roboto-Variable.ttf",
    "Manrope": Path(__file__).with_name("studio_assets") / "fonts" / "Manrope-Variable.ttf",
    "Oswald": Path(__file__).with_name("studio_assets") / "fonts" / "Oswald-Variable.ttf",
    "Cormorant Garamond": (
        Path(__file__).with_name("studio_assets") / "fonts" / "CormorantGaramond-Variable.ttf"
    ),
}
URGENCY_PATTERN = re.compile(
    r"\b(?:act now|last chance|only \d+ left|ends today|limited time|hurry|"
    r"останній шанс|лише \d+ залиш|тільки сьогодні|поспіш)\b",
    re.IGNORECASE,
)


def _tool(
    tool_id: str, kind: str, label: str, renderer: str, *,
    parameter_schema: Mapping[str, Any] | None = None,
    defaults: Mapping[str, Any] | None = None,
    bounds: Mapping[str, Any] | None = None,
    allowed_placements: Sequence[str] = (),
    tunable_paths: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "tool_id": tool_id,
        "kind": kind,
        "label": label,
        "supported_profiles": ["instagram_static_ad_v1"],
        "renderer_handler": renderer,
        "source_refs": [ADS_SOURCE],
        "parameter_schema": dict(parameter_schema or {
            "type": "object", "additionalProperties": False, "properties": {}, "required": [],
        }),
        "defaults": dict(defaults or {}),
        "bounds": dict(bounds or {}),
        "allowed_placements": list(allowed_placements),
        "tunable_paths": list(tunable_paths),
        "deprecated": False,
    }


PLACEMENT_ID = "studio.placement.instagram.feed_square.v1"
PLACEMENT = {"width": 1080, "height": 1080, "label": "Instagram feed · square"}
TIKTOK_PLACEMENT_ID = "studio.placement.tiktok.photo_vertical.v1"
TIKTOK_PLACEMENT = {"width": 1080, "height": 1920, "label": "TikTok photo · vertical"}
PROFILE_PLACEMENTS = {
    "instagram_static_ad_v1": PLACEMENT_ID,
    "tiktok_photo_post_v1": TIKTOK_PLACEMENT_ID,
}
PLACEMENTS = {
    PLACEMENT_ID: {
        **PLACEMENT,
        "profile": "instagram_static_ad_v1",
        "safe_zone": {"left": .04, "top": .04, "right": .96, "bottom": .96},
        "renderer_version": RENDERER_VERSION,
    },
    TIKTOK_PLACEMENT_ID: {
        **TIKTOK_PLACEMENT,
        "profile": "tiktok_photo_post_v1",
        "safe_zone": {"left": .06, "top": .08, "right": .82, "bottom": .84},
        "renderer_version": TIKTOK_RENDERER_VERSION,
    },
}


def _property(kind: str, *, minimum: float | None = None, maximum: float | None = None,
              values: Sequence[Any] = ()) -> dict[str, Any]:
    value: dict[str, Any] = {"type": kind}
    if minimum is not None:
        value["minimum"] = minimum
    if maximum is not None:
        value["maximum"] = maximum
    if values:
        value["enum"] = list(values)
    return value


TEXT_PROPERTIES = {
    "text": _property("string"),
    "color": _property("color"),
    "font_size": _property("number", minimum=12, maximum=160),
    "min_font_size": _property("number", minimum=12, maximum=80),
    "font_weight": _property("integer", values=range(100, 1000, 100)),
    "max_lines": _property("integer", minimum=1, maximum=20),
    "line_height": _property("number", minimum=.8, maximum=2),
    "align": _property("string", values=("left", "center", "right")),
    "vertical_align": _property("string", values=("top", "center", "bottom")),
}
MEDIA_PROPERTIES = {
    "fit": _property("string", values=("cover", "contain")),
    "focal_x": _property("number", minimum=0, maximum=1),
    "focal_y": _property("number", minimum=0, maximum=1),
    "opacity": _property("number", minimum=0, maximum=1),
    "radius": _property("number", minimum=0, maximum=160),
}
SHAPE_PROPERTIES = {
    "background": _property("color"),
    "opacity": _property("number", minimum=0, maximum=1),
    "radius": _property("number", minimum=0, maximum=160),
}


def _schema(properties: Mapping[str, Any], required: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object", "additionalProperties": False,
        "properties": {key: dict(value) for key, value in properties.items()},
        "required": list(required),
    }


def _catalog() -> tuple[dict[str, Any], ...]:
    entries = [_tool(PLACEMENT_ID, "placement", PLACEMENT["label"], "placement")]
    text_defaults = {
        "font_size": 32, "min_font_size": 16, "font_weight": 500,
        "max_lines": 6, "line_height": 1.08, "align": "left", "vertical_align": "top",
    }
    frame_paths = ("frame.x", "frame.y", "frame.width", "frame.height")
    for name, label, renderer, schema, defaults, paths in (
        ("media", "Media frame", "media", _schema(MEDIA_PROPERTIES, ("fit",)),
         {"fit": "cover", "focal_x": .5, "focal_y": .5, "opacity": 1, "radius": 0},
         (*frame_paths, "params.fit", "params.focal_x", "params.focal_y", "params.opacity", "params.radius")),
        ("logo", "Logo frame", "media", _schema(MEDIA_PROPERTIES, ("fit",)),
         {"fit": "contain", "focal_x": .5, "focal_y": .5, "opacity": 1, "radius": 0},
         (*frame_paths, "params.fit", "params.focal_x", "params.focal_y", "params.opacity", "params.radius")),
        ("headline", "Headline frame", "text", _schema(TEXT_PROPERTIES, ("text", "color")),
         text_defaults, (*frame_paths, "params.font_size", "params.font_weight", "params.line_height", "params.align")),
        ("body", "Body-copy frame", "text", _schema(TEXT_PROPERTIES, ("text", "color")),
         text_defaults, (*frame_paths, "params.font_size", "params.font_weight", "params.line_height", "params.align")),
        ("offer", "Offer frame", "text", _schema(TEXT_PROPERTIES, ("text", "color")),
         text_defaults, (*frame_paths, "params.font_size", "params.font_weight", "params.line_height", "params.align")),
        ("cta", "Call-to-action frame", "text", _schema(TEXT_PROPERTIES, ("text", "color")),
         text_defaults, (*frame_paths, "params.font_size", "params.font_weight", "params.line_height", "params.align")),
        ("badge", "Badge frame", "text", _schema(TEXT_PROPERTIES, ("text", "color")),
         text_defaults, (*frame_paths, "params.font_size", "params.font_weight", "params.line_height", "params.align")),
        ("shape", "Shape frame", "shape", _schema(SHAPE_PROPERTIES, ("background",)),
         {"opacity": 1, "radius": 0}, (*frame_paths, "params.opacity", "params.radius")),
    ):
        entries.append(_tool(
            f"studio.frame.{name}.v1", "frame", label, renderer,
            parameter_schema=schema, defaults=defaults,
            bounds={
                **{path: [0, 1] for path in frame_paths},
                **{
                    f"params.{key}": [definition["minimum"], definition["maximum"]]
                    for key, definition in schema["properties"].items()
                    if "minimum" in definition and "maximum" in definition
                },
            },
            allowed_placements=(PLACEMENT_ID,), tunable_paths=paths,
        ))
    entries.append(_tool(
        "studio.layout.single_visual.v1", "layout", "Legacy single visual", "layout",
        parameter_schema={"type": "object", "additionalProperties": True, "properties": {}, "required": []},
        allowed_placements=(PLACEMENT_ID,),
    ))
    entries.append(_tool(
        "studio.layout.template_application.v1", "layout", "Template application", "layout",
        parameter_schema={"type": "object", "additionalProperties": True, "properties": {}, "required": []},
        allowed_placements=(PLACEMENT_ID,),
    ))
    for name, label in (
        ("one_message", "One-message discipline"),
        ("specific_cta", "Specific CTA"),
        ("visual_proof", "Visual proof"),
    ):
        entries.append(_tool(f"studio.strategy.{name}.v1", "strategy", label, "validator"))
    for name, label in (
        ("safe_zone", "Placement safe zones"),
        ("small_screen_hierarchy", "Small-screen hierarchy"),
        ("contrast", "Accessible contrast"),
        ("brand_consistency", "Project brand consistency"),
        ("claim_integrity", "Claim integrity"),
        ("source_lineage", "Source lineage"),
    ):
        entries.append(_tool(f"studio.guard.{name}.v1", "guard", label, "validator"))
    return tuple(entries)


TOOL_CATALOG = _catalog()
TOOLS_BY_ID = {item["tool_id"]: item for item in TOOL_CATALOG}
DEFAULT_SOURCE_REFS = (COLOR_SOURCE, ADS_SOURCE)
DEFAULT_GUARDS = (
    "studio.guard.safe_zone.v1",
    "studio.guard.small_screen_hierarchy.v1",
    "studio.guard.contrast.v1",
    "studio.guard.brand_consistency.v1",
    "studio.guard.claim_integrity.v1",
    "studio.guard.source_lineage.v1",
)
SAFE_ZONE = {"left": .04, "top": .04, "right": .96, "bottom": .96}
SAFE_ZONE_TOOLS = {
    "studio.frame.logo.v1", "studio.frame.headline.v1", "studio.frame.body.v1",
    "studio.frame.offer.v1", "studio.frame.cta.v1", "studio.frame.badge.v1",
}


def tool_catalog() -> dict[str, Any]:
    catalog = {
        "schema_version": 2,
        "catalog_version": "ptw-studio-component-catalog-v2",
        "renderer_version": RENDERER_VERSION,
        "profile": "instagram_static_ad_v1",
        "items": [dict(item) for item in TOOL_CATALOG],
    }
    _, digest = _canonical(catalog)
    return {**catalog, "catalog_sha256": digest}


def tool_catalog_for_profile(profile: str) -> dict[str, Any]:
    """Return the immutable channel catalog without changing Instagram v2 digests."""
    if profile == "instagram_static_ad_v1":
        return tool_catalog()
    if profile != "tiktok_photo_post_v1":
        raise ValueError("unknown static social profile")
    items = json.loads(json.dumps(TOOL_CATALOG))
    for item in items:
        item["supported_profiles"] = [profile]
        if item["tool_id"] == PLACEMENT_ID:
            item["tool_id"] = TIKTOK_PLACEMENT_ID
            item["label"] = TIKTOK_PLACEMENT["label"]
        item["allowed_placements"] = [
            TIKTOK_PLACEMENT_ID if value == PLACEMENT_ID else value
            for value in item["allowed_placements"]
        ]
    catalog = {
        "schema_version": 2,
        "catalog_version": "ptw-studio-component-catalog-tiktok-v1",
        "renderer_version": TIKTOK_RENDERER_VERSION,
        "profile": profile,
        "items": items,
    }
    _, digest = _canonical(catalog)
    return {**catalog, "catalog_sha256": digest}


def _canonical(value: Mapping[str, Any]) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def renderer_identity(profile: str = "instagram_static_ad_v1") -> dict[str, str]:
    contract = (
        RENDERER_CONTRACT if profile == "instagram_static_ad_v1"
        else TIKTOK_RENDERER_CONTRACT if profile == "tiktok_photo_post_v1"
        else None
    )
    if contract is None:
        raise ValueError("unknown static social renderer profile")
    _, digest = _canonical(contract)
    return {"version": str(contract["version"]), "sha256": digest}


def validate_brand_kit(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = {"name", "colors", "fonts", "tone_notes", "logo_source_asset_id"}
    if set(value) != expected:
        raise ValueError("brand kit fields do not match the v1 contract")
    name = " ".join(str(value.get("name") or "").split())
    if not 1 <= len(name) <= 120:
        raise ValueError("brand kit name must contain 1-120 characters")
    colors = [str(item).strip().upper() for item in value.get("colors") or []]
    if not 4 <= len(colors) <= 6 or any(not re.fullmatch(r"#[0-9A-F]{6}", item) for item in colors):
        raise ValueError("brand kit colors must contain four to six six-digit hex values")
    if len(set(colors)) != len(colors):
        raise ValueError("brand kit colors must be distinct")
    fonts = [" ".join(str(item).split()) for item in value.get("fonts") or []]
    if not 1 <= len(fonts) <= 3 or any(item not in SUPPORTED_FONTS for item in fonts):
        raise ValueError("brand kit fonts must name one to three deterministic renderer fonts")
    tone = str(value.get("tone_notes") or "").strip()
    if len(tone) > 500:
        raise ValueError("brand kit tone notes must contain at most 500 characters")
    logo = value.get("logo_source_asset_id")
    if logo is not None:
        logo = str(UUID(str(logo)))
    return {"name": name, "colors": colors, "fonts": fonts, "tone_notes": tone, "logo_source_asset_id": logo}


def _frame(value: Any, name: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != {"x", "y", "width", "height"}:
        raise ValueError(f"{name}.frame must contain x, y, width, and height")
    frame = {key: float(value[key]) for key in ("x", "y", "width", "height")}
    if frame["width"] <= 0 or frame["height"] <= 0:
        raise ValueError(f"{name}.frame dimensions must be positive")
    if any(number < 0 or number > 1 for number in frame.values()):
        raise ValueError(f"{name}.frame values must be normalized from zero to one")
    if frame["x"] + frame["width"] > 1.000001 or frame["y"] + frame["height"] > 1.000001:
        raise ValueError(f"{name}.frame must remain inside the canvas")
    return frame


def _assert_honest_text(value: str) -> None:
    if (
        TESTIMONIAL_PATTERN.search(value)
        or RATING_PATTERN.search(value)
        or UNSUPPLIED_PROOF_PATTERN.search(value)
        or URGENCY_PATTERN.search(value)
    ):
        raise ValueError("Result copy contains unsupported proof, urgency, or scarcity")


def _validate_component_params(
    *, tool_id: str, params: Mapping[str, Any], brand_colors: Sequence[str] | None,
) -> dict[str, Any]:
    tool = TOOLS_BY_ID[tool_id]
    schema = tool["parameter_schema"]
    properties = schema["properties"]
    if schema.get("additionalProperties") is not True and not set(params) <= set(properties):
        unknown = sorted(set(params) - set(properties))
        raise ValueError(f"{tool_id} contains unknown parameters: {', '.join(unknown)}")
    missing = sorted(set(schema.get("required") or ()) - set(params))
    if missing:
        raise ValueError(f"{tool_id} is missing required parameters: {', '.join(missing)}")
    normalized: dict[str, Any] = {}
    palette = {str(item).upper() for item in brand_colors or ()}
    for name, raw in params.items():
        definition = properties.get(name)
        if definition is None:
            normalized[name] = raw
            continue
        kind = definition["type"]
        if kind in {"number", "integer"}:
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"{tool_id}.{name} must be numeric")
            value: int | float = int(raw) if kind == "integer" else float(raw)
            if kind == "integer" and float(raw) != value:
                raise ValueError(f"{tool_id}.{name} must be an integer")
            if "minimum" in definition and value < definition["minimum"]:
                raise ValueError(f"{tool_id}.{name} is below its catalog bound")
            if "maximum" in definition and value > definition["maximum"]:
                raise ValueError(f"{tool_id}.{name} is above its catalog bound")
        elif kind in {"string", "color"}:
            if not isinstance(raw, str):
                raise ValueError(f"{tool_id}.{name} must be a string")
            value = raw
            if kind == "color":
                value = value.upper()
                if not re.fullmatch(r"#[0-9A-F]{6}", value):
                    raise ValueError(f"{tool_id}.{name} must be a six-digit hex color")
                if palette and value not in palette:
                    raise ValueError(f"{tool_id}.{name} is outside the Project palette")
        else:
            raise ValueError(f"{tool_id}.{name} has an unsupported catalog type")
        if definition.get("enum") and value not in definition["enum"]:
            raise ValueError(f"{tool_id}.{name} is outside its allowed values")
        normalized[name] = value
    return normalized


def _relative_luminance(color: str) -> float:
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    adjusted = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
    return .2126 * adjusted[0] + .7152 * adjusted[1] + .0722 * adjusted[2]


def _contrast_ratio(left: str, right: str) -> float:
    low, high = sorted((_relative_luminance(left), _relative_luminance(right)))
    return (high + .05) / (low + .05)


@dataclass(frozen=True, slots=True)
class StudioRecipeV2:
    """The sole structured visual contract for static-social Results."""

    value: Mapping[str, Any]
    digest: str

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        project_id: str,
        brief_id: str,
        brand_kit_id: str,
        brief: Mapping[str, Any],
        brand_document: Mapping[str, Any] | None = None,
    ) -> "StudioRecipeV2":
        expected = {
            "schema_version", "parent_recipe_id", "placement_tool_id", "duration_seconds",
            "frame_rate", "frames", "modifiers", "strategy_ids", "validation_ids",
            "source_reference_ids", "share",
        }
        if set(value) != expected or value.get("schema_version") != 2:
            raise ValueError("Result recipe fields or schema version do not match StudioRecipeV2")
        parent_recipe_id = value["parent_recipe_id"]
        if parent_recipe_id is not None:
            parsed_parent = UUID(str(parent_recipe_id))
            if parsed_parent.version != 7:
                raise ValueError("parent recipe ID must be a UUIDv7")
            parent_recipe_id = str(parsed_parent)
        placement_tool_id = str(value["placement_tool_id"])
        placement = PLACEMENTS.get(placement_tool_id)
        if placement is None:
            raise ValueError("the static-social placement is unavailable")
        if value["duration_seconds"] is not None or value["frame_rate"] is not None:
            raise ValueError("Static-social recipes cannot declare duration or frame rate")

        raw_frames = value.get("frames")
        if not isinstance(raw_frames, list) or not 1 <= len(raw_frames) <= 32:
            raise ValueError("Result recipes require one to 32 visual frames")
        frames: list[dict[str, Any]] = []
        instance_ids: set[str] = set()
        source_assets: set[str] = set()
        for index, raw in enumerate(raw_frames):
            if not isinstance(raw, Mapping) or set(raw) != {
                "instance_id", "tool_id", "frame", "z_index", "params", "timeline", "source_asset_ids",
            }:
                raise ValueError(f"frames[{index}] fields do not match StudioRecipeV2")
            parsed_id = UUID(str(raw["instance_id"]))
            if parsed_id.version != 7:
                raise ValueError("Result frame instance IDs must be UUIDv7")
            instance_id = str(parsed_id)
            if instance_id in instance_ids:
                raise ValueError("Result frame instance IDs must be distinct")
            instance_ids.add(instance_id)
            tool_id = str(raw.get("tool_id") or "")
            if TOOLS_BY_ID.get(tool_id, {}).get("kind") != "frame":
                raise ValueError(f"unknown Result frame tool ID: {tool_id}")
            if raw.get("timeline") is not None:
                raise ValueError("static-social frames cannot declare a timeline")
            params = raw.get("params")
            if not isinstance(params, Mapping):
                raise ValueError(f"frames[{index}].params must be an object")
            params = _validate_component_params(
                tool_id=tool_id, params=params,
                brand_colors=None if brand_document is None else brand_document.get("colors") or (),
            )
            for item in params.values():
                if isinstance(item, str):
                    _assert_honest_text(item)
            asset_ids = [str(UUID(str(item))) for item in raw.get("source_asset_ids") or []]
            expected_assets = 1 if tool_id in {"studio.frame.media.v1", "studio.frame.logo.v1"} else 0
            if len(asset_ids) != expected_assets:
                raise ValueError(f"{tool_id} requires exactly {expected_assets} source assets")
            source_assets.update(asset_ids)
            frame = _frame(raw["frame"], f"frames[{index}]")
            safe_zone = placement["safe_zone"]
            if tool_id in SAFE_ZONE_TOOLS and (
                frame["x"] < safe_zone["left"]
                or frame["y"] < safe_zone["top"]
                or frame["x"] + frame["width"] > safe_zone["right"]
                or frame["y"] + frame["height"] > safe_zone["bottom"]
            ):
                raise ValueError(f"{tool_id} must stay inside the placement safe zone")
            frames.append({
                "instance_id": instance_id,
                "tool_id": tool_id,
                "frame": frame,
                "z_index": int(raw["z_index"]),
                "params": dict(params),
                "timeline": None,
                "source_asset_ids": asset_ids,
            })
        if len({item["z_index"] for item in frames}) != len(frames):
            raise ValueError("Result frame z-index values must be distinct")
        protected_layout = [item for item in frames if item["tool_id"] in SAFE_ZONE_TOOLS]
        for index, left in enumerate(protected_layout):
            a = left["frame"]
            for right in protected_layout[index + 1:]:
                b = right["frame"]
                overlaps = (
                    min(a["x"] + a["width"], b["x"] + b["width"]) > max(a["x"], b["x"])
                    and min(a["y"] + a["height"], b["y"] + b["height"]) > max(a["y"], b["y"])
                )
                if overlaps:
                    raise ValueError(
                        f"Result protected layout collision: {left['tool_id']} and {right['tool_id']}"
                    )
        shapes = [item for item in frames if item["tool_id"] == "studio.frame.shape.v1"]
        for text_frame in protected_layout:
            if text_frame["tool_id"] == "studio.frame.logo.v1":
                continue
            box = text_frame["frame"]
            center = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            surfaces = [item for item in shapes if item["z_index"] < text_frame["z_index"] and (
                item["frame"]["x"] <= center[0] <= item["frame"]["x"] + item["frame"]["width"]
                and item["frame"]["y"] <= center[1] <= item["frame"]["y"] + item["frame"]["height"]
            )]
            if not surfaces:
                raise ValueError(f"{text_frame['tool_id']} has no declared contrast surface")
            surface = max(surfaces, key=lambda item: item["z_index"])
            foreground = str(text_frame["params"].get("color") or "")
            background = str(surface["params"].get("background") or "")
            if _contrast_ratio(foreground, background) < 3:
                raise ValueError(f"{text_frame['tool_id']} fails the minimum large-text contrast ratio")
        offers = [str(item["params"].get("text") or "").strip() for item in frames if item["tool_id"] == "studio.frame.offer.v1"]
        ctas = [str(item["params"].get("text") or "").strip() for item in frames if item["tool_id"] == "studio.frame.cta.v1"]
        if offers != [brief["offer"]] or ctas != [brief["cta"]]:
            raise ValueError("Result recipe must contain one exact Product Brief offer and CTA frame")

        modifiers: list[dict[str, Any]] = []
        raw_modifiers = value.get("modifiers")
        if not isinstance(raw_modifiers, list) or len(raw_modifiers) > 8:
            raise ValueError("Result recipe modifiers must be a bounded list")
        for index, raw in enumerate(raw_modifiers):
            if not isinstance(raw, Mapping) or set(raw) != {"instance_id", "tool_id", "params"}:
                raise ValueError(f"modifiers[{index}] fields do not match StudioRecipeV2")
            parsed_id = UUID(str(raw["instance_id"]))
            if parsed_id.version != 7 or str(parsed_id) in instance_ids:
                raise ValueError("Result modifier instance IDs must be distinct UUIDv7s")
            instance_ids.add(str(parsed_id))
            tool_id = str(raw.get("tool_id") or "")
            if TOOLS_BY_ID.get(tool_id, {}).get("kind") != "layout":
                raise ValueError(f"unknown Result modifier tool ID: {tool_id}")
            params = raw.get("params")
            if not isinstance(params, Mapping):
                raise ValueError("Result modifier params must be an object")
            modifiers.append({"instance_id": str(parsed_id), "tool_id": tool_id, "params": dict(params)})

        template_modifiers = [
            item for item in modifiers
            if item["tool_id"] == "studio.layout.template_application.v1"
        ]
        if template_modifiers:
            if len(template_modifiers) != 1 or len(modifiers) != 1:
                raise ValueError("configured Studio recipes require one exact template-application modifier")
            from .studio_templates import validate_template_application
            validate_template_application(
                submission=value, metadata=template_modifiers[0]["params"],
                modifier_instance_id=template_modifiers[0]["instance_id"],
            )

        strategy_ids = [str(item) for item in value.get("strategy_ids") or []]
        if not strategy_ids or any(TOOLS_BY_ID.get(item, {}).get("kind") != "strategy" for item in strategy_ids):
            raise ValueError("Result recipe contains an unknown or empty strategy list")
        validation_ids = [str(item) for item in value.get("validation_ids") or []]
        if set(validation_ids) != set(DEFAULT_GUARDS) or len(validation_ids) != len(DEFAULT_GUARDS):
            raise ValueError("Result recipe must declare every required validation guard exactly once")
        source_refs = [str(item) for item in value.get("source_reference_ids") or []]
        if not source_refs or any(item not in DEFAULT_SOURCE_REFS for item in source_refs):
            raise ValueError("Result recipe source references are outside the approved catalog")
        share = value.get("share")
        if not isinstance(share, Mapping) or set(share) != {"caption", "alt_text"}:
            raise ValueError("Result recipe share fields must contain caption and alt_text")
        caption = str(share.get("caption") or "").strip()
        alt_text = str(share.get("alt_text") or "").strip()
        if not 1 <= len(caption) <= 2200 or not 1 <= len(alt_text) <= 1000:
            raise ValueError("Result caption or alt text is outside its bounded length")
        _assert_honest_text(caption)
        normalized = {
            "schema_version": 2,
            "project_id": str(UUID(project_id)),
            "brief_id": str(UUID(brief_id)),
            "parent_recipe_id": parent_recipe_id,
            "brand_kit_id": str(UUID(brand_kit_id)),
            "placement_tool_id": placement_tool_id,
            "width": int(placement["width"]),
            "height": int(placement["height"]),
            "duration_seconds": None,
            "frame_rate": None,
            "frames": sorted(frames, key=lambda item: item["z_index"]),
            "modifiers": modifiers,
            "strategy_ids": strategy_ids,
            "validation_ids": validation_ids,
            "source_reference_ids": source_refs,
            "source_asset_ids": sorted(source_assets),
            "renderer_version": str(placement["renderer_version"]),
            "share": {"caption": caption, "alt_text": alt_text},
        }
        _, digest = _canonical(normalized)
        return cls(normalized, digest)


def validate_recipe(
    value: Mapping[str, Any], *, project_id: str, brief_id: str,
    brand_kit_id: str, brief: Mapping[str, Any],
    brand_document: Mapping[str, Any] | None = None,
) -> StudioRecipeV2:
    return StudioRecipeV2.from_dict(
        value, project_id=project_id, brief_id=brief_id,
        brand_kit_id=brand_kit_id, brief=brief, brand_document=brand_document,
    )


def recipe_tools(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    frames = [dict(item) for item in value.get("frames") or []]
    base_z = max((int(item["z_index"]) for item in frames), default=-1) + 1
    for index, item in enumerate(value.get("modifiers") or []):
        frames.append({
            "instance_id": str(item["instance_id"]), "tool_id": str(item["tool_id"]),
            "frame": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            "z_index": base_z + index, "params": dict(item.get("params") or {}),
            "timeline": None, "source_asset_ids": [],
        })
    return sorted(frames, key=lambda item: item["z_index"])


def inspect_media(data: bytes, declared_mime: str) -> dict[str, Any]:
    if declared_mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Result source assets must be JPEG, PNG, or WebP images")
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Result source image exceeds the bounded size")
    from PIL import Image
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception as error:
        raise ValueError("Result source image cannot be decoded") from error
    actual = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
    if actual != declared_mime:
        raise ValueError("Result source image MIME does not match its decoded format")
    if image.width < 64 or image.height < 64 or image.width > 12000 or image.height > 12000:
        raise ValueError("Result source image dimensions are outside the bounded range")
    return {"mime_type": actual, "width": image.width, "height": image.height, "duration_seconds": None}


def _hex(value: str, fallback: str) -> tuple[int, int, int]:
    chosen = value if re.fullmatch(r"#[0-9A-Fa-f]{6}", value or "") else fallback
    return tuple(int(chosen[index:index + 2], 16) for index in (1, 3, 5))


class StudioRenderer:
    """Render one validated static-social Result deterministically."""

    def __init__(self, font_path: Path = SUPPORTED_FONTS["Inter"]) -> None:
        self.font_path = font_path

    def _font(self, size: int, font_name: str = "Inter", weight: int | None = None):
        from PIL import ImageFont
        path = STUDIO_PREVIEW_FONTS.get(font_name, SUPPORTED_FONTS.get(font_name, self.font_path))
        try:
            font = ImageFont.truetype(str(path), max(12, size))
            if weight is not None:
                try:
                    values = []
                    for axis in font.get_variation_axes():
                        name = bytes(axis["name"]).decode("ascii", "ignore").lower()
                        if "width" in name and font_name == "Roboto Condensed":
                            values.append(75)
                        elif "weight" in name:
                            values.append(max(axis["minimum"], min(axis["maximum"], int(weight))))
                        else:
                            values.append(axis["default"])
                    font.set_variation_by_axes(values)
                    return font
                except (AttributeError, KeyError, OSError, TypeError, ValueError):
                    pass
                variation = {
                    100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular",
                    500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black",
                }.get(int(weight), "Medium")
                try:
                    font.set_variation_by_name(variation)
                except (AttributeError, OSError, ValueError):
                    pass
            return font
        except OSError:
            return ImageFont.load_default()

    @staticmethod
    def _wrap_text(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
        lines: list[str] = []
        for paragraph in text.splitlines() or [""]:
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = ""
            for word in words:
                candidate = word if not current else f"{current} {word}"
                if draw.textlength(candidate, font=font) <= max_width:
                    current = candidate
                    continue
                if current:
                    lines.append(current)
                    current = ""
                if draw.textlength(word, font=font) <= max_width:
                    current = word
                    continue
                fragment = ""
                for character in word:
                    candidate = fragment + character
                    if fragment and draw.textlength(candidate, font=font) > max_width:
                        lines.append(fragment)
                        fragment = character
                    else:
                        fragment = candidate
                current = fragment
            if current:
                lines.append(current)
        return lines

    def _draw_fitted_text(
        self, draw: Any, *, text: str, box: tuple[int, int, int, int],
        params: Mapping[str, Any], fill: tuple[int, int, int], font_name: str,
        protected: bool,
    ) -> None:
        if not text:
            return
        width, height = box[2] - box[0], box[3] - box[1]
        requested = max(12, int(params.get("font_size") or max(24, width // 10)))
        minimum = max(12, min(requested, int(params.get("min_font_size") or 18)))
        max_lines = max(1, min(20, int(params.get("max_lines") or 20)))
        line_ratio = max(.8, min(2.0, float(params.get("line_height") or 1.12)))
        weight = None if "font_weight" not in params else int(params["font_weight"])
        chosen: tuple[Any, list[str], int] | None = None
        for size in range(requested, minimum - 1, -1):
            font = self._font(size, font_name, weight)
            lines = self._wrap_text(draw, text, font, width)
            spacing = max(0, round(size * (line_ratio - 1)))
            bounds = draw.multiline_textbbox((0, 0), "\n".join(lines), font=font, spacing=spacing)
            if len(lines) <= max_lines and bounds[2] - bounds[0] <= width and bounds[3] - bounds[1] <= height:
                chosen = (font, lines, spacing)
                break
        if chosen is None:
            label = "protected offer/CTA" if protected else "frame"
            raise ValueError(f"Result text overflow in {label}; resize the frame or shorten editable copy")
        font, lines, spacing = chosen
        rendered = "\n".join(lines)
        bounds = draw.multiline_textbbox((0, 0), rendered, font=font, spacing=spacing)
        text_width, text_height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        align = str(params.get("align") or "left")
        if align == "right":
            x = box[2] - text_width
        elif align == "center":
            x = box[0] + (width - text_width) / 2
        else:
            x = box[0]
        vertical = str(params.get("vertical_align") or "top")
        if vertical == "bottom":
            y = box[3] - text_height
        elif vertical == "center":
            y = box[1] + (height - text_height) / 2
        else:
            y = box[1]
        draw.multiline_text(
            (round(x), round(y)), rendered, font=font, fill=fill,
            spacing=spacing, align=align,
        )

    def _canvas(
        self, recipe: Mapping[str, Any], brand_kit: Mapping[str, Any],
        assets: Mapping[str, Mapping[str, Any]],
    ):
        from PIL import Image, ImageDraw, ImageOps
        width, height = int(recipe["width"]), int(recipe["height"])
        colors = list(brand_kit["document"]["colors"])
        font_name = str((brand_kit["document"].get("fonts") or ["Inter"])[0])
        canvas = Image.new("RGB", (width, height), _hex(colors[0], "#111111"))
        draw = ImageDraw.Draw(canvas)
        for item in recipe_tools(recipe):
            tool_id = item["tool_id"]
            if TOOLS_BY_ID.get(tool_id, {}).get("kind") != "frame":
                continue
            frame = item["frame"]
            box = (
                round(frame["x"] * width), round(frame["y"] * height),
                round((frame["x"] + frame["width"]) * width),
                round((frame["y"] + frame["height"]) * height),
            )
            params = item["params"]
            if tool_id in {"studio.frame.media.v1", "studio.frame.logo.v1"}:
                if not item["source_asset_ids"]:
                    continue
                source = assets.get(item["source_asset_ids"][0])
                if source is None or not str(source["mime_type"]).startswith("image/"):
                    raise ValueError("Result recipe references an unavailable image asset")
                with Image.open(BytesIO(source["bytes"])) as original:
                    target_mode = "RGBA" if original.mode == "RGBA" or tool_id.endswith("logo.v1") else "RGB"
                    prepared = original.convert(target_mode)
                    size = (box[2] - box[0], box[3] - box[1])
                    default_fit = "contain" if tool_id.endswith("logo.v1") else "cover"
                    if str(params.get("fit") or default_fit) == "contain":
                        fitted = ImageOps.contain(prepared, size)
                        layer = Image.new("RGBA", size, (0, 0, 0, 0))
                        layer.paste(
                            fitted,
                            ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2),
                            fitted if fitted.mode == "RGBA" else None,
                        )
                        fitted = layer
                    else:
                        focal = (
                            max(0.0, min(1.0, float(params.get("focal_x", .5)))),
                            max(0.0, min(1.0, float(params.get("focal_y", .5)))),
                        )
                        fitted = ImageOps.fit(prepared, size, centering=focal)
                opacity = max(0.0, min(1.0, float(params.get("opacity", 1))))
                radius = max(0, int(params.get("radius", 0)))
                if fitted.mode != "RGBA" and (opacity < 1 or radius > 0):
                    fitted = fitted.convert("RGBA")
                if fitted.mode == "RGBA" and (opacity < 1 or radius > 0):
                    alpha = fitted.getchannel("A")
                    if opacity < 1:
                        alpha = alpha.point(lambda value: round(value * opacity))
                    if radius > 0:
                        mask = Image.new("L", size, 0)
                        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
                        from PIL import ImageChops
                        alpha = ImageChops.multiply(alpha, mask)
                    fitted.putalpha(alpha)
                canvas.paste(fitted, (box[0], box[1]), fitted if fitted.mode == "RGBA" else None)
                draw = ImageDraw.Draw(canvas)
            elif tool_id == "studio.frame.shape.v1":
                opacity = max(0.0, min(1.0, float(params.get("opacity", 1))))
                overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                fill = (*_hex(str(params.get("background") or ""), colors[1]), round(255 * opacity))
                ImageDraw.Draw(overlay).rounded_rectangle(
                    box, radius=int(params.get("radius", 18)), fill=fill,
                )
                canvas.paste(overlay.convert("RGB"), (0, 0), overlay)
                draw = ImageDraw.Draw(canvas)
            else:
                self._draw_fitted_text(
                    draw,
                    text=str(params.get("text") or ""),
                    box=box,
                    params=params,
                    fill=_hex(str(params.get("color") or ""), colors[-1]),
                    font_name=font_name,
                    protected=tool_id in {"studio.frame.offer.v1", "studio.frame.cta.v1"},
                )
        return canvas

    @staticmethod
    def _compact_manifest(recipe_id: str, recipe_digest: str, tool_ids: Sequence[str]) -> str:
        return json.dumps({
            "schema": "ptw.result.render-manifest.v1",
            "recipe_id": recipe_id,
            "recipe_sha256": recipe_digest,
            "tool_ids": list(dict.fromkeys(tool_ids)),
        }, sort_keys=True, separators=(",", ":"))

    def render(
        self, *, recipe_id: str, recipe_digest: str, recipe: Mapping[str, Any],
        brand_kit: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        from PIL import Image
        canvas = self._canvas(recipe, brand_kit, assets)
        tool_ids = [
            recipe["placement_tool_id"],
            *[item["tool_id"] for item in recipe_tools(recipe)],
            *recipe["strategy_ids"],
            *recipe["validation_ids"],
        ]
        compact = self._compact_manifest(recipe_id, recipe_digest, tool_ids)
        output = BytesIO()
        exif = Image.Exif()
        exif[0x9286] = compact
        canvas.save(output, format="JPEG", quality=90, optimize=True, progressive=False, exif=exif)
        return {
            "bytes": output.getvalue(), "mime_type": "image/jpeg",
            "duration_seconds": None, "embedded_manifest": compact,
        }

    def render_preview(
        self, template: Any, *, semantic_data: Mapping[str, Any],
        assets: Mapping[str, Mapping[str, Any]], width: int | None = None,
        height: int | None = None,
    ) -> dict[str, Any]:
        """Render one v1 primitive-tree draft without changing Result recipes.

        Importing lazily keeps the historical flat-frame compatibility path and
        its byte contract independent from the universal-ad configuration model.
        """
        from .studio_primitives import PrimitivePreviewRenderer

        return PrimitivePreviewRenderer(self._font).render(
            template, semantic_data=semantic_data, assets=assets,
            width=width, height=height,
        )


def build_manifest(
    *, render_id: str, recipe_id: str, recipe_digest: str,
    recipe: Mapping[str, Any], brand_kit: Mapping[str, Any],
    assets: Mapping[str, Mapping[str, Any]], rendered: Mapping[str, Any],
) -> dict[str, Any]:
    tool_instances = []
    for ordinal, item in enumerate(recipe_tools(recipe)):
        _, params_digest = _canonical(dict(item["params"]))
        tool_instances.append({
            "instance_id": item["instance_id"], "tool_id": item["tool_id"],
            "params_sha256": params_digest, "frame": item["frame"],
            "timeline": None, "z_index": item["z_index"], "ordinal": ordinal,
            "source_asset_ids": list(item["source_asset_ids"]),
        })
    application = next((
        dict(item["params"]) for item in recipe.get("modifiers") or []
        if item["tool_id"] == "studio.layout.template_application.v1"
    ), None)
    manifest = {
        "schema": "ptw.result.render-manifest.v1",
        "render_id": render_id, "recipe_id": recipe_id,
        "recipe_sha256": recipe_digest, "project_id": recipe["project_id"],
        "brief_id": recipe["brief_id"], "brand_kit_id": brand_kit["brand_kit_id"],
        "brand_kit_sha256": brand_kit.get("document_sha256"),
        "renderer_version": recipe.get("renderer_version", RENDERER_VERSION),
        "renderer_sha256": renderer_identity(
            str(PLACEMENTS[recipe["placement_tool_id"]]["profile"])
        )["sha256"] if application else None,
        "placement_tool_id": recipe["placement_tool_id"],
        "tool_instances": tool_instances,
        "strategy_ids": list(recipe["strategy_ids"]),
        "validation_ids": list(recipe["validation_ids"]),
        "share": dict(recipe["share"]),
        "source_assets": [{
            "source_asset_id": asset_id, "origin": assets[asset_id]["origin"],
            "provider": assets[asset_id].get("provider"),
            "external_id": assets[asset_id].get("external_id"),
            "source_uri": assets[asset_id].get("source_uri"),
            "license": assets[asset_id].get("license"),
            "attribution": assets[asset_id].get("attribution"),
            "bytes_sha256": assets[asset_id]["bytes_sha256"],
        } for asset_id in recipe["source_asset_ids"]],
        "source_refs": list(recipe["source_reference_ids"]),
        "resolved_recipe": {"document": dict(recipe), "sha256": recipe_digest},
        "output": {
            "mime_type": rendered["mime_type"],
            "width": int(recipe["width"]), "height": int(recipe["height"]),
            "duration_seconds": None,
            "bytes_sha256": hashlib.sha256(rendered["bytes"]).hexdigest(),
        },
    }
    if application is not None:
        manifest["production"] = {
            "schema": application["schema"],
            "strategy_template": dict(application["strategy_template"]),
            "studio_template": dict(application["studio_template"]),
            "catalog": dict(application["catalog"]),
            "renderer": dict(application["renderer"]),
            "slider_input": dict(application["slider_input"]),
            "slider_normalized": dict(application["slider_normalized"]),
            "component_instances": dict(application["component_instances"]),
            "components_sha256": application["components_sha256"],
            "bindings_sha256": application["bindings_sha256"],
            "patch_sha256": application["patch_sha256"],
            "parent_recipe_id": application["parent_recipe_id"],
            "base_recipe_sha256": application["base_recipe_sha256"],
        }
    return manifest
