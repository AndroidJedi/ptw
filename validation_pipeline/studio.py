"""Versioned contracts and deterministic renderers for the additive Ad Studio."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7

from .domain import RATING_PATTERN, TESTIMONIAL_PATTERN, UNSUPPLIED_PROOF_PATTERN


COLOR_SOURCE = "https://www.manypixels.co/blog/social-media-design/instagram-color"
ADS_SOURCE = "https://www.manypixels.co/blog/social-media-design/best-instagram-ads"
RENDERER_VERSION = "ptw-studio-renderer-v2"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_VIDEO_SECONDS = 30.0
SUPPORTED_FONTS = {
    "Inter": Path("/app/natal/assets/inter.ttf"),
    "DejaVu Sans": Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    "DejaVu Serif": Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    "DejaVu Mono": Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
}
URGENCY_PATTERN = re.compile(
    r"\b(?:act now|last chance|only \d+ left|ends today|limited time|hurry|"
    r"останній шанс|лише \d+ залиш|тільки сьогодні|поспіш)\b",
    re.IGNORECASE,
)


def _schema(properties: Mapping[str, Any] | None = None) -> dict[str, Any]:
    values = dict(properties or {})
    return {
        "type": "object",
        "properties": values,
        "additionalProperties": True,
    }


def _tool(
    tool_id: str,
    kind: str,
    label: str,
    *,
    placements: Sequence[str] = ("static", "motion"),
    renderer: str = "manifest",
    source: str = ADS_SOURCE,
    properties: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "tool_id": tool_id,
        "kind": kind,
        "label": label,
        "parameter_schema": _schema(properties),
        "supported_placements": list(placements),
        "renderer_handler": renderer,
        "defaults": {},
        "bounds": {"frame": "normalized_0_1"},
        "source_refs": [source],
        "deprecated": False,
    }


PLACEMENTS: dict[str, dict[str, Any]] = {
    "studio.placement.instagram.feed_square.v1": {
        "width": 1080, "height": 1080, "media": "static", "label": "Instagram feed · square",
    },
    "studio.placement.instagram.feed_portrait.v1": {
        "width": 1080, "height": 1350, "media": "static", "label": "Instagram feed · portrait",
    },
    "studio.placement.instagram.story_vertical.v1": {
        "width": 1080, "height": 1920, "media": "motion", "label": "Instagram Story",
    },
    "studio.placement.instagram.reel_vertical.v1": {
        "width": 1080, "height": 1920, "media": "motion", "label": "Instagram Reel",
    },
    "studio.placement.instagram.carousel_square.v1": {
        "width": 1080, "height": 1080, "media": "static", "label": "Instagram carousel · square",
    },
    "studio.placement.instagram.carousel_portrait.v1": {
        "width": 1080, "height": 1350, "media": "static", "label": "Instagram carousel · portrait",
    },
    "studio.placement.tiktok.vertical_video.v1": {
        "width": 1080, "height": 1920, "media": "motion", "label": "TikTok vertical video",
    },
}


def _catalog() -> tuple[dict[str, Any], ...]:
    entries: list[dict[str, Any]] = []
    for tool_id, placement in PLACEMENTS.items():
        placement_defaults = {
            "width": placement["width"], "height": placement["height"],
            "duration_seconds": 8 if placement["media"] == "motion" else None,
            "frame_rate": 30 if placement["media"] == "motion" else None,
        }
        if tool_id == "studio.placement.tiktok.vertical_video.v1":
            placement_defaults["derivation_note"] = (
                "PTW extension of placement-native vertical-video principles; "
                "not a direct conclusion from the Instagram references"
            )
        entries.append({
            **_tool(
                tool_id, "placement", placement["label"], placements=(placement["media"],),
                renderer="placement", source=ADS_SOURCE,
            ),
            "defaults": placement_defaults,
            "bounds": {
                "width": placement["width"], "height": placement["height"],
                "duration_seconds": [3, 30] if placement["media"] == "motion" else None,
            },
        })
    for name, label, renderer in (
        ("media", "Media frame", "media"), ("product", "Product frame", "media"),
        ("logo", "Logo frame", "media"), ("headline", "Headline frame", "text"),
        ("body", "Body-copy frame", "text"), ("offer", "Offer frame", "text"),
        ("cta", "Call-to-action frame", "text"), ("badge", "Badge frame", "text"),
        ("shape", "Shape frame", "shape"),
    ):
        entries.append(_tool(
            f"studio.frame.{name}.v1", "frame", label, renderer=renderer,
            properties={
                "text": {"type": "string"}, "color": {"type": "string"},
                "background": {"type": "string"}, "font_size": {"type": "integer"},
                "align": {"enum": ["left", "center", "right"]},
                "vertical_align": {"enum": ["top", "center", "bottom"]},
                "line_height": {"type": "number", "minimum": 0.8, "maximum": 2},
                "max_lines": {"type": "integer", "minimum": 1, "maximum": 20},
                "min_font_size": {"type": "integer", "minimum": 12, "maximum": 200},
                "trim_start_seconds": {"type": "number", "minimum": 0, "maximum": 30},
                "original_audio": {"enum": ["preserve", "mute"]},
                "fit": {"enum": ["cover", "contain"]},
                "focal_x": {"type": "number", "minimum": 0, "maximum": 1},
                "focal_y": {"type": "number", "minimum": 0, "maximum": 1},
                "opacity": {"type": "number", "minimum": 0, "maximum": 1},
                "radius": {"type": "integer", "minimum": 0, "maximum": 500},
            },
        ))
    for name, label in (
        ("single_visual", "Single visual"), ("type_led", "Type-led"),
        ("editorial_product_split", "Editorial and product split"),
        ("before_after", "Before and after"), ("catalog_grid", "Catalog grid"),
        ("carousel_sequence", "Carousel sequence"), ("claim_proof", "Claim and proof"),
    ):
        entries.append(_tool(f"studio.layout.{name}.v1", "layout", label))
    for name, label in (
        ("monochrome", "Monochromatic palette"), ("analogous", "Analogous palette"),
        ("complementary", "Complementary palette"), ("triadic", "Triadic palette"),
        ("neutral_plus", "Neutral-plus palette"),
    ):
        entries.append(_tool(
            f"studio.color.palette.{name}.v1", "color", label,
            source=COLOR_SOURCE, renderer="palette",
        ))
    entries.append(_tool(
        "studio.color.ratio_60_30_10.v1", "color", "60/30/10 color ratio",
        source=COLOR_SOURCE, renderer="palette",
    ))
    for name, label in (
        ("photo_tint", "Photo tint"), ("duotone", "Duotone"),
        ("filter_preset", "Filter preset"),
    ):
        entries.append(_tool(
            f"studio.effect.{name}.v1", "effect", label,
            source=COLOR_SOURCE, renderer="effect",
        ))
    for name, label in (
        ("first_second_hook", "First-second hook"), ("kinetic_type", "Kinetic type"),
        ("pan_zoom", "Pan and zoom"), ("product_demo", "Product demonstration"),
        ("ugc_caption", "UGC captions"), ("narrative_arc", "Narrative arc"),
        ("transition", "Transition"),
    ):
        entries.append(_tool(
            f"studio.motion.{name}.v1", "motion", label,
            placements=("motion",), renderer="motion",
        ))
    for name, label in (
        ("one_message", "One-message discipline"), ("specific_cta", "Specific CTA"),
        ("question_hook", "Question hook"), ("native_ugc", "Native UGC"),
        ("visual_proof", "Visual proof"), ("range_browse", "Range browsing"),
    ):
        entries.append(_tool(f"studio.strategy.{name}.v1", "strategy", label, renderer="validator"))
    for name, label in (
        ("safe_zone", "Placement safe zones"),
        ("small_screen_hierarchy", "Small-screen hierarchy"),
        ("contrast", "Accessible contrast"),
        ("brand_consistency", "Project brand consistency"),
        ("claim_integrity", "Claim integrity"),
        ("source_lineage", "Source lineage"),
    ):
        entries.append(_tool(f"studio.guard.{name}.v1", "guard", label, renderer="validator"))
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
SAFE_ZONES = {
    "static": {"left": .04, "top": .04, "right": .96, "bottom": .96},
    "motion": {"left": .05, "top": .08, "right": .95, "bottom": .95},
}
SAFE_ZONE_TOOLS = {
    "studio.frame.logo.v1", "studio.frame.headline.v1", "studio.frame.body.v1",
    "studio.frame.offer.v1", "studio.frame.cta.v1", "studio.frame.badge.v1",
}


def tool_catalog() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "renderer_version": RENDERER_VERSION,
        "items": [dict(item) for item in TOOL_CATALOG],
    }


def _canonical(value: Mapping[str, Any]) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


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
    if not 1 <= len(fonts) <= 3 or any(not 1 <= len(item) <= 100 for item in fonts):
        raise ValueError("brand kit fonts must contain one to three names")
    if any(item not in SUPPORTED_FONTS for item in fonts):
        raise ValueError("brand kit font is not available in the deterministic renderer")
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
        raise ValueError("Studio copy contains unsupported proof, urgency, or scarcity")


@dataclass(frozen=True, slots=True)
class StudioRecipeV1:
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
    ) -> "StudioRecipeV1":
        expected = {
            "schema_version", "parent_recipe_id", "placement_tool_id", "duration_seconds",
            "frame_rate", "tools", "strategy_ids", "validation_ids", "source_reference_ids",
        }
        if set(value) != expected or value.get("schema_version") != 1:
            raise ValueError("Studio recipe fields or schema version do not match v1")
        placement_id = str(value.get("placement_tool_id") or "")
        if placement_id not in PLACEMENTS:
            raise ValueError("unknown Studio placement tool ID")
        placement = PLACEMENTS[placement_id]
        parent = value.get("parent_recipe_id")
        if parent is not None:
            parent = str(UUID(str(parent)))
        duration = value.get("duration_seconds")
        frame_rate = value.get("frame_rate")
        if placement["media"] == "motion":
            duration = float(duration)
            frame_rate = int(frame_rate)
            if not 3 <= duration <= MAX_VIDEO_SECONDS or frame_rate not in {24, 25, 30}:
                raise ValueError("motion recipes require 3-30 seconds at 24, 25, or 30 fps")
        elif duration is not None or frame_rate is not None:
            raise ValueError("static recipes cannot declare duration or frame rate")
        raw_tools = value.get("tools")
        if not isinstance(raw_tools, list) or not 1 <= len(raw_tools) <= 64:
            raise ValueError("Studio recipes require one to 64 tool instances")
        tools: list[dict[str, Any]] = []
        seen_instances: set[str] = set()
        source_assets: set[str] = set()
        for index, raw in enumerate(raw_tools):
            if not isinstance(raw, Mapping) or set(raw) != {
                "instance_id", "tool_id", "frame", "z_index", "params", "timeline", "source_asset_ids",
            }:
                raise ValueError(f"tools[{index}] fields do not match the v1 contract")
            parsed_instance_id = UUID(str(raw["instance_id"]))
            if parsed_instance_id.version != 7:
                raise ValueError("Studio tool instance IDs must be UUIDv7")
            instance_id = str(parsed_instance_id)
            if instance_id in seen_instances:
                raise ValueError("Studio tool instance IDs must be distinct")
            seen_instances.add(instance_id)
            tool_id = str(raw.get("tool_id") or "")
            definition = TOOLS_BY_ID.get(tool_id)
            if definition is None or definition["deprecated"] or definition["kind"] == "placement":
                raise ValueError(f"unknown or unavailable Studio tool ID: {tool_id}")
            if placement["media"] not in definition["supported_placements"]:
                raise ValueError(f"{tool_id} is not compatible with {placement_id}")
            params = raw.get("params")
            if not isinstance(params, Mapping):
                raise ValueError(f"tools[{index}].params must be an object")
            if "trim_start_seconds" in params and not 0 <= float(params["trim_start_seconds"]) <= MAX_VIDEO_SECONDS:
                raise ValueError("video trim start must remain inside the bounded duration")
            if "original_audio" in params and params["original_audio"] not in {"preserve", "mute"}:
                raise ValueError("original_audio must be preserve or mute")
            for item in params.values():
                if isinstance(item, str):
                    _assert_honest_text(item)
            timeline = raw.get("timeline")
            if timeline is not None:
                if placement["media"] != "motion" or not isinstance(timeline, Mapping) or set(timeline) != {"start", "end"}:
                    raise ValueError("tool timelines are available only for motion recipes")
                timeline = {"start": float(timeline["start"]), "end": float(timeline["end"])}
                if timeline["start"] < 0 or timeline["end"] <= timeline["start"] or timeline["end"] > duration:
                    raise ValueError("tool timeline must stay inside the motion duration")
            asset_ids = [str(UUID(str(item))) for item in raw.get("source_asset_ids") or []]
            source_assets.update(asset_ids)
            tools.append({
                "instance_id": instance_id, "tool_id": tool_id,
                "frame": _frame(raw["frame"], f"tools[{index}]"),
                "z_index": int(raw["z_index"]), "params": dict(params),
                "timeline": timeline, "source_asset_ids": asset_ids,
            })
        zone = SAFE_ZONES[placement["media"]]
        for item in tools:
            if item["tool_id"] not in SAFE_ZONE_TOOLS:
                continue
            frame = item["frame"]
            if (
                frame["x"] < zone["left"] or frame["y"] < zone["top"]
                or frame["x"] + frame["width"] > zone["right"]
                or frame["y"] + frame["height"] > zone["bottom"]
            ):
                raise ValueError(f'{item["tool_id"]} must stay inside the placement safe zone')
        if len({item["z_index"] for item in tools}) != len(tools):
            raise ValueError("Studio tool z-index values must be distinct")
        offer_values = [
            str(item["params"].get("text") or "").strip()
            for item in tools if item["tool_id"] == "studio.frame.offer.v1"
        ]
        cta_values = [
            str(item["params"].get("text") or "").strip()
            for item in tools if item["tool_id"] == "studio.frame.cta.v1"
        ]
        if offer_values != [brief["offer"]] or cta_values != [brief["cta"]]:
            raise ValueError("Studio recipe must contain one exact Product Brief offer and CTA frame")
        strategy_ids = [str(item) for item in value.get("strategy_ids") or []]
        validation_ids = [str(item) for item in value.get("validation_ids") or []]
        for tool_id in strategy_ids:
            if TOOLS_BY_ID.get(tool_id, {}).get("kind") != "strategy":
                raise ValueError(f"unknown Studio strategy ID: {tool_id}")
        for tool_id in validation_ids:
            if TOOLS_BY_ID.get(tool_id, {}).get("kind") != "guard":
                raise ValueError(f"unknown Studio validation ID: {tool_id}")
        if set(DEFAULT_GUARDS) - set(validation_ids):
            raise ValueError("Studio recipe is missing one or more required validation guards")
        source_refs = [str(item) for item in value.get("source_reference_ids") or []]
        if not source_refs or any(item not in DEFAULT_SOURCE_REFS for item in source_refs):
            raise ValueError("Studio source references must use the approved provenance URLs")
        normalized = {
            "schema_version": 1, "project_id": str(UUID(project_id)), "brief_id": str(UUID(brief_id)),
            "parent_recipe_id": parent, "brand_kit_id": str(UUID(brand_kit_id)),
            "placement_tool_id": placement_id,
            "width": placement["width"], "height": placement["height"],
            "duration_seconds": duration, "frame_rate": frame_rate,
            "tools": sorted(tools, key=lambda item: item["z_index"]),
            "strategy_ids": strategy_ids, "validation_ids": validation_ids,
            "source_reference_ids": source_refs, "source_asset_ids": sorted(source_assets),
            "renderer_version": RENDERER_VERSION,
        }
        _, digest = _canonical(normalized)
        return cls(normalized, digest)


def _v2_submission(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return only owner-submitted V2 fields from a normalized stored document."""
    return {
        key: value[key] for key in (
            "schema_version", "parent_recipe_id", "placement_tool_id", "duration_seconds",
            "frame_rate", "frames", "modifiers", "strategy_ids", "validation_ids",
            "source_reference_ids", "share",
        )
    }


def recipe_tools(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expose one renderer view across the immutable V1 and V2 contracts."""
    if int(value.get("schema_version") or 1) == 1:
        return [dict(item) for item in value.get("tools") or []]
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


@dataclass(frozen=True, slots=True)
class StudioRecipeV2:
    """Editable frames, non-visual modifiers, and share copy in one recipe revision."""

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
    ) -> "StudioRecipeV2":
        expected = {
            "schema_version", "parent_recipe_id", "placement_tool_id", "duration_seconds",
            "frame_rate", "frames", "modifiers", "strategy_ids", "validation_ids",
            "source_reference_ids", "share",
        }
        if set(value) != expected or value.get("schema_version") != 2:
            raise ValueError("Studio recipe fields or schema version do not match v2")
        raw_frames = value.get("frames")
        raw_modifiers = value.get("modifiers")
        if not isinstance(raw_frames, list) or not raw_frames:
            raise ValueError("Studio V2 recipes require one or more visual frames")
        if not isinstance(raw_modifiers, list):
            raise ValueError("Studio V2 recipe modifiers must be a list")
        flattened = [dict(item) for item in raw_frames]
        next_z = max((int(item.get("z_index", -1)) for item in flattened), default=-1) + 1
        for index, raw in enumerate(raw_modifiers):
            if not isinstance(raw, Mapping) or set(raw) != {"instance_id", "tool_id", "params"}:
                raise ValueError(f"modifiers[{index}] fields do not match the v2 contract")
            tool_id = str(raw.get("tool_id") or "")
            definition = TOOLS_BY_ID.get(tool_id)
            if definition is None or definition["kind"] not in {"layout", "color", "effect"}:
                raise ValueError(f"unknown or unavailable Studio modifier ID: {tool_id}")
            flattened.append({
                "instance_id": raw["instance_id"], "tool_id": tool_id,
                "frame": {"x": 0, "y": 0, "width": 1, "height": 1},
                "z_index": next_z + index, "params": dict(raw.get("params") or {}),
                "timeline": None, "source_asset_ids": [],
            })
        v1 = StudioRecipeV1.from_dict({
            "schema_version": 1,
            "parent_recipe_id": value["parent_recipe_id"],
            "placement_tool_id": value["placement_tool_id"],
            "duration_seconds": value["duration_seconds"],
            "frame_rate": value["frame_rate"],
            "tools": flattened,
            "strategy_ids": value["strategy_ids"],
            "validation_ids": value["validation_ids"],
            "source_reference_ids": value["source_reference_ids"],
        }, project_id=project_id, brief_id=brief_id, brand_kit_id=brand_kit_id, brief=brief)
        share = value.get("share")
        if not isinstance(share, Mapping) or set(share) != {"caption", "alt_text"}:
            raise ValueError("Studio V2 share fields must contain caption and alt_text")
        caption = str(share.get("caption") or "").strip()
        alt_text = str(share.get("alt_text") or "").strip()
        if not 1 <= len(caption) <= 2200:
            raise ValueError("Studio share caption must contain 1-2200 characters")
        if not 1 <= len(alt_text) <= 1000:
            raise ValueError("Studio alt text must contain 1-1000 characters")
        _assert_honest_text(caption)
        normalized_frames = [item for item in v1.value["tools"] if TOOLS_BY_ID[item["tool_id"]]["kind"] in {"frame", "motion"}]
        normalized_modifiers = [{
            "instance_id": item["instance_id"], "tool_id": item["tool_id"], "params": item["params"],
        } for item in v1.value["tools"] if TOOLS_BY_ID[item["tool_id"]]["kind"] in {"layout", "color", "effect"}]
        normalized = {
            **{key: v1.value[key] for key in (
                "project_id", "brief_id", "parent_recipe_id", "brand_kit_id", "placement_tool_id",
                "width", "height", "duration_seconds", "frame_rate", "strategy_ids",
                "validation_ids", "source_reference_ids", "source_asset_ids", "renderer_version",
            )},
            "schema_version": 2, "frames": normalized_frames,
            "modifiers": normalized_modifiers, "share": {"caption": caption, "alt_text": alt_text},
        }
        _, digest = _canonical(normalized)
        return cls(normalized, digest)


def validate_recipe(
    value: Mapping[str, Any], *, project_id: str, brief_id: str,
    brand_kit_id: str, brief: Mapping[str, Any],
) -> StudioRecipeV1 | StudioRecipeV2:
    if value.get("schema_version") == 2:
        return StudioRecipeV2.from_dict(
            value, project_id=project_id, brief_id=brief_id,
            brand_kit_id=brand_kit_id, brief=brief,
        )
    return StudioRecipeV1.from_dict(
        value, project_id=project_id, brief_id=brief_id,
        brand_kit_id=brand_kit_id, brief=brief,
    )


def _validate_template_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version", "placement_tool_id", "duration_seconds", "frame_rate",
        "frames", "modifiers", "strategy_ids", "bindings",
    }
    if set(value) != expected:
        raise ValueError("Studio template fields do not match v2")
    frames = value.get("frames")
    modifiers = value.get("modifiers")
    bindings = value.get("bindings")
    if not isinstance(frames, list) or not frames or not isinstance(modifiers, list):
        raise ValueError("Studio V2 templates require frames and modifiers")
    if not isinstance(bindings, Mapping) or not bindings:
        raise ValueError("Studio V2 templates require typed bindings")
    next_z = max((int(item.get("z_index", -1)) for item in frames), default=-1) + 1
    flattened = [dict(item) for item in frames]
    for index, item in enumerate(modifiers):
        if not isinstance(item, Mapping) or set(item) != {"instance_id", "tool_id", "params"}:
            raise ValueError("Studio V2 template modifier fields do not match")
        flattened.append({
            "instance_id": item["instance_id"], "tool_id": item["tool_id"],
            "frame": {"x": 0, "y": 0, "width": 1, "height": 1},
            "z_index": next_z + index, "params": dict(item.get("params") or {}),
            "timeline": None, "source_asset_ids": [],
        })
    v1 = validate_template({
        "schema_version": 1, "placement_tool_id": value["placement_tool_id"],
        "duration_seconds": value["duration_seconds"], "frame_rate": value["frame_rate"],
        "tools": flattened, "strategy_ids": value["strategy_ids"],
    })
    normalized_frames = [item for item in v1["tools"] if TOOLS_BY_ID[item["tool_id"]]["kind"] in {"frame", "motion"}]
    normalized_modifiers = [{
        "instance_id": item["instance_id"], "tool_id": item["tool_id"], "params": item["params"],
    } for item in v1["tools"] if TOOLS_BY_ID[item["tool_id"]]["kind"] in {"layout", "color", "effect"}]
    normalized_bindings: dict[str, dict[str, str]] = {}
    frame_ids = {item["instance_id"] for item in normalized_frames}
    allowed_sources = {
        "creative.hook", "creative.photo", "creative.primary_text",
        "creative.image_description",
        "brief.offer", "brief.cta", "brief.trust_strategy", "brand.logo",
    }
    for name, raw in bindings.items():
        if not isinstance(raw, Mapping) or set(raw) != {"target", "source"}:
            raise ValueError("Studio template binding fields must contain target and source")
        target, source = str(raw["target"]), str(raw["source"])
        if not target or not source:
            raise ValueError("Studio template bindings cannot be empty")
        if source not in allowed_sources and re.fullmatch(r"brief\.key_benefits\[[0-4]\]", source) is None:
            raise ValueError("Studio template binding source is not supported")
        if target != "/share/caption":
            match = re.fullmatch(r"/frames/([0-9a-f-]{36})/(params/text|source_asset_ids)", target)
            if match is None or match.group(1) not in frame_ids:
                raise ValueError("Studio template binding target must reference one template frame")
        normalized_bindings[str(name)] = {"target": target, "source": source}
    return {
        "schema_version": 2, "placement_tool_id": v1["placement_tool_id"],
        "duration_seconds": v1["duration_seconds"], "frame_rate": v1["frame_rate"],
        "frames": normalized_frames, "modifiers": normalized_modifiers,
        "strategy_ids": v1["strategy_ids"], "bindings": normalized_bindings,
    }


def validate_template(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a reusable Project template without binding it to one Brief."""
    if value.get("schema_version") == 2:
        return _validate_template_v2(value)
    expected = {"schema_version", "placement_tool_id", "duration_seconds", "frame_rate", "tools", "strategy_ids"}
    if set(value) != expected or value.get("schema_version") != 1:
        raise ValueError("Studio template fields or schema version do not match v1")
    placement_id = str(value.get("placement_tool_id") or "")
    if placement_id not in PLACEMENTS:
        raise ValueError("unknown Studio placement tool ID")
    placement = PLACEMENTS[placement_id]
    duration = value.get("duration_seconds")
    frame_rate = value.get("frame_rate")
    if placement["media"] == "motion":
        try:
            duration, frame_rate = float(duration), int(frame_rate)
        except (TypeError, ValueError) as error:
            raise ValueError("motion templates require duration and frame rate") from error
        if not 3 <= duration <= MAX_VIDEO_SECONDS or frame_rate not in {24, 25, 30}:
            raise ValueError("motion templates require 3-30 seconds at 24, 25, or 30 fps")
    elif duration is not None or frame_rate is not None:
        raise ValueError("static templates cannot declare duration or frame rate")
    raw_tools = value.get("tools")
    if not isinstance(raw_tools, list) or not 1 <= len(raw_tools) <= 64:
        raise ValueError("Studio templates require one to 64 tool instances")
    tools: list[dict[str, Any]] = []
    instance_ids: set[str] = set()
    for index, raw in enumerate(raw_tools):
        if not isinstance(raw, Mapping) or set(raw) != {
            "instance_id", "tool_id", "frame", "z_index", "params", "timeline", "source_asset_ids",
        }:
            raise ValueError(f"template tools[{index}] fields do not match v1")
        tool_id = str(raw.get("tool_id") or "")
        definition = TOOLS_BY_ID.get(tool_id)
        if definition is None or definition["deprecated"] or definition["kind"] in {"placement", "guard"}:
            raise ValueError(f"unknown or unavailable Studio template tool ID: {tool_id}")
        if placement["media"] not in definition["supported_placements"]:
            raise ValueError(f"{tool_id} is not compatible with {placement_id}")
        params = dict(raw.get("params") or {})
        for item in params.values():
            if isinstance(item, str) and item not in {"{{offer}}", "{{cta}}"}:
                _assert_honest_text(item)
        parsed_instance_id = UUID(str(raw["instance_id"]))
        if parsed_instance_id.version != 7:
            raise ValueError("Studio template tool instance IDs must be UUIDv7")
        instance_id = str(parsed_instance_id)
        if instance_id in instance_ids:
            raise ValueError("Studio template tool instance IDs must be distinct")
        instance_ids.add(instance_id)
        timeline = raw.get("timeline")
        if timeline is not None:
            if placement["media"] != "motion" or not isinstance(timeline, Mapping) or set(timeline) != {"start", "end"}:
                raise ValueError("template timelines are available only for motion placements")
            timeline = {"start": float(timeline["start"]), "end": float(timeline["end"])}
            if timeline["start"] < 0 or timeline["end"] <= timeline["start"] or timeline["end"] > duration:
                raise ValueError("template timeline must stay inside the motion duration")
        tools.append({
            "instance_id": instance_id, "tool_id": tool_id,
            "frame": _frame(raw["frame"], f"template tools[{index}]"),
            "z_index": int(raw["z_index"]), "params": params,
            "timeline": timeline,
            "source_asset_ids": [str(UUID(str(item))) for item in raw.get("source_asset_ids") or []],
        })
    if len({item["z_index"] for item in tools}) != len(tools):
        raise ValueError("Studio template z-index values must be distinct")
    if sum(item["tool_id"] == "studio.frame.offer.v1" for item in tools) != 1 or sum(item["tool_id"] == "studio.frame.cta.v1" for item in tools) != 1:
        raise ValueError("Studio templates require one offer frame and one CTA frame")
    offer = next(item for item in tools if item["tool_id"] == "studio.frame.offer.v1")
    cta = next(item for item in tools if item["tool_id"] == "studio.frame.cta.v1")
    if offer["params"].get("text") != "{{offer}}" or cta["params"].get("text") != "{{cta}}":
        raise ValueError("Studio templates must use exact {{offer}} and {{cta}} placeholders")
    strategies = [str(item) for item in value.get("strategy_ids") or []]
    if any(TOOLS_BY_ID.get(item, {}).get("kind") != "strategy" for item in strategies):
        raise ValueError("Studio template contains an unknown strategy ID")
    return {
        "schema_version": 1, "placement_tool_id": placement_id,
        "duration_seconds": duration, "frame_rate": frame_rate,
        "tools": sorted(tools, key=lambda item: item["z_index"]), "strategy_ids": strategies,
    }


def inspect_media(data: bytes, declared_mime: str) -> dict[str, Any]:
    if declared_mime in {"image/jpeg", "image/png", "image/webp"}:
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Studio image exceeds the bounded size")
        from PIL import Image
        try:
            image = Image.open(BytesIO(data)); image.load()
        except Exception as error:
            raise ValueError("Studio image cannot be decoded") from error
        actual = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
        if actual != declared_mime:
            raise ValueError("Studio image MIME does not match its decoded format")
        if image.width < 64 or image.height < 64 or image.width > 12000 or image.height > 12000:
            raise ValueError("Studio image dimensions are outside the bounded range")
        return {"mime_type": actual, "width": image.width, "height": image.height, "duration_seconds": None}
    if declared_mime not in {"video/mp4", "video/quicktime"}:
        raise ValueError("unsupported Studio source media type")
    if not data or len(data) > MAX_VIDEO_BYTES:
        raise ValueError("Studio video exceeds the bounded size")
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required to inspect Studio video")
    suffix = ".mp4" if declared_mime == "video/mp4" else ".mov"
    with tempfile.TemporaryDirectory(prefix="ptw-studio-probe-") as root:
        path = Path(root) / f"source{suffix}"
        path.write_bytes(data)
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,codec_name:format=duration,format_name", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=10, check=False,
        )
    if result.returncode != 0:
        raise ValueError("Studio video cannot be decoded")
    try:
        value = json.loads(result.stdout); stream = value["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        duration = float(value["format"]["duration"]); codec = str(stream["codec_name"])
        container = str(value["format"]["format_name"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Studio video metadata is incomplete") from error
    if width < 64 or height < 64 or width > 7680 or height > 7680 or not 0 < duration <= MAX_VIDEO_SECONDS:
        raise ValueError("Studio video dimensions or duration are outside the bounded range")
    if codec not in {"h264", "hevc", "prores", "mjpeg"}:
        raise ValueError("Studio video codec is not supported")
    if not {"mov", "mp4"}.intersection(container.split(",")):
        raise ValueError("Studio video container does not match MP4/MOV")
    return {"mime_type": declared_mime, "width": width, "height": height, "duration_seconds": duration, "codec": codec}


def _hex(value: str, fallback: str) -> tuple[int, int, int]:
    chosen = value if re.fullmatch(r"#[0-9A-Fa-f]{6}", value or "") else fallback
    return tuple(int(chosen[index:index + 2], 16) for index in (1, 3, 5))


class StudioRenderer:
    """Render a bounded recipe without changing the active Stage 2 renderer."""

    def __init__(self, font_path: Path = Path("/app/natal/assets/inter.ttf")) -> None:
        self.font_path = font_path

    def _font(self, size: int, font_name: str = "Inter"):
        from PIL import ImageFont
        path = self.font_path if font_name == "Inter" else SUPPORTED_FONTS.get(font_name, self.font_path)
        try:
            return ImageFont.truetype(str(path), max(12, size))
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
        chosen: tuple[Any, list[str], int] | None = None
        for size in range(requested, minimum - 1, -1):
            font = self._font(size, font_name)
            lines = self._wrap_text(draw, text, font, width)
            spacing = max(0, round(size * (line_ratio - 1)))
            bounds = draw.multiline_textbbox((0, 0), "\n".join(lines), font=font, spacing=spacing)
            if len(lines) <= max_lines and bounds[2] - bounds[0] <= width and bounds[3] - bounds[1] <= height:
                chosen = (font, lines, spacing)
                break
        if chosen is None:
            label = "protected offer/CTA" if protected else "frame"
            raise ValueError(f"Studio text overflow in {label}; resize the frame or shorten editable copy")
        font, lines, spacing = chosen
        value = "\n".join(lines)
        bounds = draw.multiline_textbbox((0, 0), value, font=font, spacing=spacing)
        text_width, text_height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        align = str(params.get("align") or "left")
        x = box[0] if align == "left" else box[2] - text_width if align == "right" else box[0] + (width - text_width) / 2
        vertical = str(params.get("vertical_align") or "top")
        y = box[1] if vertical == "top" else box[3] - text_height if vertical == "bottom" else box[1] + (height - text_height) / 2
        draw.multiline_text((round(x), round(y)), value, font=font, fill=fill, spacing=spacing, align=align)

    def _canvas(
        self,
        recipe: Mapping[str, Any],
        brand_kit: Mapping[str, Any],
        assets: Mapping[str, Mapping[str, Any]],
        *,
        transparent: bool = False,
        min_z: int | None = None,
        max_z: int | None = None,
    ):
        from PIL import Image, ImageDraw, ImageEnhance, ImageOps
        width, height = int(recipe["width"]), int(recipe["height"])
        colors = list(brand_kit["document"]["colors"])
        font_name = str((brand_kit["document"].get("fonts") or ["Inter"])[0])
        tools = recipe_tools(recipe)
        effect_ids = {item["tool_id"] for item in tools}
        canvas = Image.new(
            "RGBA" if transparent else "RGB", (width, height),
            (0, 0, 0, 0) if transparent else _hex(colors[0], "#111111"),
        )
        draw = ImageDraw.Draw(canvas)
        for item in tools:
            if min_z is not None and item["z_index"] <= min_z:
                continue
            if max_z is not None and item["z_index"] > max_z:
                continue
            tool_id = item["tool_id"]
            frame = item["frame"]
            box = (
                round(frame["x"] * width), round(frame["y"] * height),
                round((frame["x"] + frame["width"]) * width),
                round((frame["y"] + frame["height"]) * height),
            )
            params = item["params"]
            if tool_id in {"studio.frame.media.v1", "studio.frame.product.v1", "studio.frame.logo.v1"}:
                if not item["source_asset_ids"]:
                    continue
                source = assets.get(item["source_asset_ids"][0])
                if source is None or not str(source["mime_type"]).startswith("image/"):
                    continue
                with Image.open(BytesIO(source["bytes"])) as original:
                    target_mode = "RGBA" if transparent or original.mode == "RGBA" or tool_id == "studio.frame.logo.v1" else "RGB"
                    prepared = original.convert(target_mode)
                    fit = str(params.get("fit") or ("contain" if tool_id == "studio.frame.logo.v1" else "cover"))
                    focal = (
                        max(0.0, min(1.0, float(params.get("focal_x", .5)))),
                        max(0.0, min(1.0, float(params.get("focal_y", .5)))),
                    )
                    size = (box[2] - box[0], box[3] - box[1])
                    if fit == "contain":
                        fitted = ImageOps.contain(prepared, size)
                        layer = Image.new("RGBA", size, (0, 0, 0, 0))
                        layer.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2), fitted if fitted.mode == "RGBA" else None)
                        fitted = layer
                    else:
                        fitted = ImageOps.fit(prepared, size, centering=focal)
                if "studio.effect.duotone.v1" in effect_ids:
                    alpha = fitted.getchannel("A") if transparent else None
                    fitted = ImageOps.colorize(
                        ImageOps.grayscale(fitted), _hex(colors[0], "#111111"), _hex(colors[2], "#4466AA")
                    ).convert("RGBA" if transparent else "RGB")
                    if alpha is not None:
                        fitted.putalpha(alpha)
                elif "studio.effect.photo_tint.v1" in effect_ids:
                    tint = Image.new(fitted.mode, fitted.size, _hex(colors[2], "#4466AA"))
                    fitted = Image.blend(fitted, tint, .28)
                if "studio.effect.filter_preset.v1" in effect_ids:
                    fitted = ImageEnhance.Contrast(fitted).enhance(1.12)
                alpha = fitted if fitted.mode == "RGBA" else None
                canvas.paste(fitted, (box[0], box[1]), alpha)
                # Pillow may replace or detach the destination image core during a
                # paste.  Rebind ImageDraw before the next frame so text following
                # a composited media/logo layer is always drawn on the live canvas.
                draw = ImageDraw.Draw(canvas)
            elif tool_id == "studio.frame.shape.v1":
                opacity = max(0.0, min(1.0, float(params.get("opacity", 1))))
                fill = (*_hex(str(params.get("background") or ""), colors[1]), round(255 * opacity))
                if canvas.mode == "RGBA":
                    draw.rounded_rectangle(box, radius=int(params.get("radius", 18)), fill=fill)
                else:
                    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                    ImageDraw.Draw(overlay).rounded_rectangle(box, radius=int(params.get("radius", 18)), fill=fill)
                    canvas.paste(overlay.convert("RGB"), (0, 0), overlay)
                    # In particular, CTA text commonly follows its RGB button
                    # shape immediately.  A stale drawing context made that label
                    # disappear nondeterministically while the shape remained.
                    draw = ImageDraw.Draw(canvas)
            elif tool_id.startswith("studio.frame.") or tool_id == "studio.motion.ugc_caption.v1":
                text = str(params.get("text") or "")
                fill = _hex(str(params.get("color") or ""), colors[-1])
                self._draw_fitted_text(
                    draw, text=text, box=box, params=params, fill=fill, font_name=font_name,
                    protected=tool_id in {"studio.frame.offer.v1", "studio.frame.cta.v1"},
                )
        return canvas

    @staticmethod
    def _compact_manifest(recipe_id: str, recipe_digest: str, tool_ids: Sequence[str]) -> str:
        return json.dumps({
            "schema": "ptw.studio.manifest.v1", "recipe_id": recipe_id,
            "recipe_sha256": recipe_digest, "tool_ids": list(dict.fromkeys(tool_ids)),
        }, sort_keys=True, separators=(",", ":"))

    def render(
        self,
        *,
        recipe_id: str,
        recipe_digest: str,
        recipe: Mapping[str, Any],
        brand_kit: Mapping[str, Any],
        assets: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        from PIL import Image
        canvas = self._canvas(recipe, brand_kit, assets)
        tool_ids = [recipe["placement_tool_id"], *[item["tool_id"] for item in recipe_tools(recipe)], *recipe["strategy_ids"], *recipe["validation_ids"]]
        compact = self._compact_manifest(recipe_id, recipe_digest, tool_ids)
        if recipe["duration_seconds"] is None:
            output = BytesIO()
            exif = Image.Exif(); exif[0x9286] = compact
            canvas.save(output, format="JPEG", quality=90, optimize=True, progressive=False, exif=exif)
            data = output.getvalue()
            return {"bytes": data, "mime_type": "image/jpeg", "duration_seconds": None, "embedded_manifest": compact}
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is required for Studio motion rendering")
        with tempfile.TemporaryDirectory(prefix="ptw-studio-render-") as root:
            base = Path(root) / "base.png"; target = Path(root) / "creative.mp4"
            transition = any(item["tool_id"] == "studio.motion.transition.v1" for item in recipe["tools"])
            fade = ""
            if transition:
                fade = f",fade=t=in:st=0:d=.25,fade=t=out:st={max(0, float(recipe['duration_seconds']) - .25)}:d=.25"
            video_item = next((
                item for item in recipe["tools"]
                if item["source_asset_ids"]
                and str(assets.get(item["source_asset_ids"][0], {}).get("mime_type", "")).startswith("video/")
            ), None)
            if video_item is None:
                canvas.save(base, format="PNG")
                command = [
                    "ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(base),
                    "-t", str(recipe["duration_seconds"]), "-r", str(recipe["frame_rate"]),
                    "-vf", f"format=yuv420p{fade}", "-an", "-map_metadata", "-1",
                ]
            else:
                source = assets[video_item["source_asset_ids"][0]]
                suffix = ".mov" if source["mime_type"] == "video/quicktime" else ".mp4"
                video_path = Path(root) / f"source{suffix}"; video_path.write_bytes(source["bytes"])
                lower = self._canvas(recipe, brand_kit, assets, max_z=video_item["z_index"])
                overlay = self._canvas(recipe, brand_kit, assets, transparent=True, min_z=video_item["z_index"])
                lower.save(base, format="PNG"); overlay_path = Path(root) / "overlay.png"; overlay.save(overlay_path, format="PNG")
                frame = video_item["frame"]
                x, y = round(frame["x"] * recipe["width"]), round(frame["y"] * recipe["height"])
                box_width, box_height = round(frame["width"] * recipe["width"]), round(frame["height"] * recipe["height"])
                trim = max(0, float(video_item["params"].get("trim_start_seconds", 0)))
                if trim >= float(source["duration_seconds"]):
                    raise ValueError("video trim start must be before the source duration")
                filters = (
                    f"[0:v]scale={box_width}:{box_height}:force_original_aspect_ratio=increase,"
                    f"crop={box_width}:{box_height}[clip];"
                    f"[1:v][clip]overlay={x}:{y}[media];[media][2:v]overlay=0:0,format=yuv420p{fade}[outv]"
                )
                command = [
                    "ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-ss", str(trim), "-i", str(video_path),
                    "-loop", "1", "-i", str(base), "-loop", "1", "-i", str(overlay_path),
                    "-t", str(recipe["duration_seconds"]), "-r", str(recipe["frame_rate"]),
                    "-filter_complex", filters, "-map", "[outv]",
                ]
                if video_item["params"].get("original_audio", "mute") == "preserve":
                    command.extend(["-map", "0:a?", "-c:a", "aac", "-b:a", "128k"])
                else:
                    command.append("-an")
                command.extend(["-map_metadata", "-1"])
            command.extend([
                "-metadata", f"comment={compact}", "-fflags", "+bitexact",
                "-c:v", "libx264", "-preset", "veryfast", "-threads", "2",
                "-movflags", "+faststart", str(target),
            ])
            result = subprocess.run(command, capture_output=True, timeout=45, check=False)
            if result.returncode != 0 or not target.is_file():
                raise RuntimeError("Studio motion render failed")
            data = target.read_bytes()
        return {"bytes": data, "mime_type": "video/mp4", "duration_seconds": recipe["duration_seconds"], "embedded_manifest": compact}


def build_manifest(
    *,
    render_id: str,
    recipe_id: str,
    recipe_digest: str,
    recipe: Mapping[str, Any],
    brand_kit: Mapping[str, Any],
    assets: Mapping[str, Mapping[str, Any]],
    rendered: Mapping[str, Any],
) -> dict[str, Any]:
    tool_instances = []
    for ordinal, item in enumerate(recipe_tools(recipe)):
        _, params_digest = _canonical(dict(item["params"]))
        tool_instances.append({
            "instance_id": item["instance_id"], "tool_id": item["tool_id"],
            "params_sha256": params_digest, "frame": item["frame"],
            "timeline": item["timeline"], "z_index": item["z_index"],
            "ordinal": ordinal, "source_asset_ids": list(item["source_asset_ids"]),
        })
    return {
        "schema": "ptw.studio.manifest.v1", "render_id": render_id,
        "recipe_id": recipe_id, "recipe_sha256": recipe_digest,
        "project_id": recipe["project_id"], "brief_id": recipe["brief_id"],
        "brand_kit_id": brand_kit["brand_kit_id"],
        "brand_kit_sha256": brand_kit.get("document_sha256"),
        "renderer_version": RENDERER_VERSION,
        "placement_tool_id": recipe["placement_tool_id"], "tool_instances": tool_instances,
        "strategy_ids": list(recipe["strategy_ids"]), "validation_ids": list(recipe["validation_ids"]),
        "share": dict(recipe.get("share") or {}),
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
        "output": {
            "mime_type": rendered["mime_type"], "width": recipe["width"], "height": recipe["height"],
            "duration_seconds": rendered["duration_seconds"],
            "bytes_sha256": hashlib.sha256(rendered["bytes"]).hexdigest(),
        },
    }


SAMPLE_ANGLES = ("emotional", "practical", "curiosity", "authority", "problem_first")
SAMPLE_NAMES = {
    "emotional": "Вікно ясності",
    "practical": "Одне питання — три кроки",
    "curiosity": "Прихований маршрут",
    "authority": "Прозорий процес",
    "problem_first": "Не загальний гороскоп",
}
SAMPLE_HOOKS = {
    "emotional": "Що насправді стоїть за вашим «не знаю, як далі»?",
    "practical": "Одне питання. Ваші дані. Зрозумілі орієнтири.",
    "curiosity": "Чому саме це питання не відпускає вас?",
    "authority": "Персональний розбір починається з точних даних, а не загальних фраз.",
    "problem_first": "Загальний гороскоп не знає, між чим ви обираєте.",
}
SAMPLE_ALT_TEXTS = {
    "emotional": "Людина праворуч у задумі; ліворуч — запитання про ясність наступного кроку та кнопка Natal.",
    "practical": "Редакційне фото поруч із трьома кроками персонального розбору: питання, дані та орієнтири.",
    "curiosity": "Абстрактний блакитний маршрут відокремлюється від темних орбіт і веде до спокійної точки.",
    "authority": "Консультант праворуч і прозоре пояснення персонального розбору на темній картці Natal.",
    "problem_first": "Серед повторюваних темних карток один блакитний персональний шлях виходить за межі шаблону.",
}


def build_sample_documents(
    *, brief: Mapping[str, Any], creatives: Sequence[Mapping[str, Any]],
    media_by_angle: Mapping[str, str], logo_source_asset_id: str,
) -> list[dict[str, Any]]:
    """Build five distinct, editable V2 template/recipe pairs from one completed batch."""
    by_angle = {str(item["angle"]): item for item in creatives}
    if tuple(by_angle) != SAMPLE_ANGLES or len(by_angle) != 5:
        raise ValueError("Studio samples require the completed five-angle batch in canonical order")
    if set(media_by_angle) != set(SAMPLE_ANGLES):
        raise ValueError("Studio samples require one resolved source visual for every angle")

    def frame(
        tool_id: str, x: float, y: float, width: float, height: float, z: int,
        *, params: Mapping[str, Any] | None = None, assets: Sequence[str] = (),
    ) -> dict[str, Any]:
        return {
            "instance_id": new_uuid7(), "tool_id": tool_id,
            "frame": {"x": x, "y": y, "width": width, "height": height},
            "z_index": z, "params": dict(params or {}), "timeline": None,
            "source_asset_ids": list(assets),
        }

    def design(angle: str, *, template: bool) -> list[dict[str, Any]]:
        media_id = media_by_angle[angle]
        hook = "{{creative.hook}}" if template else SAMPLE_HOOKS[angle]
        offer = "{{offer}}" if template else str(brief["offer"])
        cta = "{{cta}}" if template else str(brief["cta"])
        common = [
            frame("studio.frame.media.v1", 0, 0, 1, 1, 0, params={
                "fit": "cover", "focal_x": .75 if angle in {"emotional", "authority"} else .5,
                "focal_y": .5,
            }, assets=[] if template else [media_id]),
            frame("studio.frame.logo.v1", .06, .055, .22, .075, 2,
                  params={"fit": "contain"}, assets=[] if template else [logo_source_asset_id]),
        ]
        if angle == "emotional":
            common += [
                frame("studio.frame.shape.v1", 0, 0, .72, 1, 1,
                      params={"background": "#0C0E12", "opacity": .82, "radius": 0}),
                frame("studio.frame.headline.v1", .06, .18, .58, .31, 3, params={
                    "text": hook, "color": "#F4F6FA", "font_size": 74, "min_font_size": 42,
                    "max_lines": 5, "line_height": 1.03,
                }),
            ]
        elif angle == "practical":
            common += [
                frame("studio.frame.shape.v1", 0, 0, .58, 1, 1,
                      params={"background": "#0C0E12", "opacity": .94, "radius": 0}),
                frame("studio.frame.headline.v1", .06, .15, .48, .20, 3, params={
                    "text": hook, "color": "#F4F6FA", "font_size": 58,
                    "min_font_size": 34, "max_lines": 4, "line_height": 1.04,
                }),
                frame("studio.frame.body.v1", .06, .39, .44, .075, 4, params={
                    "text": "01  Сформулюйте питання", "color": "#87D0DD", "font_size": 31, "max_lines": 2,
                }),
                frame("studio.frame.body.v1", .06, .48, .44, .095, 5, params={
                    "text": "02  Додайте дату, час і місце народження", "color": "#F4F6FA", "font_size": 28, "max_lines": 3,
                }),
                frame("studio.frame.body.v1", .06, .59, .44, .085, 6, params={
                    "text": "03  Отримайте персональні орієнтири", "color": "#F4F6FA", "font_size": 28, "max_lines": 3,
                }),
            ]
        elif angle == "curiosity":
            common += [
                frame("studio.frame.shape.v1", 0, 0, .67, 1, 1,
                      params={"background": "#0C0E12", "opacity": .70, "radius": 0}),
                frame("studio.frame.badge.v1", .06, .17, .30, .055, 3, params={
                    "text": "ПЕРСОНАЛЬНИЙ МАРШРУТ", "color": "#87D0DD", "font_size": 22, "max_lines": 1,
                }),
                frame("studio.frame.headline.v1", .06, .25, .57, .28, 4, params={
                    "text": hook, "color": "#F4F6FA", "font_size": 72,
                    "min_font_size": 40, "max_lines": 5, "line_height": 1.02,
                }),
            ]
        elif angle == "authority":
            common += [
                frame("studio.frame.shape.v1", 0, 0, .62, 1, 1,
                      params={"background": "#0C0E12", "opacity": .92, "radius": 0}),
                frame("studio.frame.headline.v1", .06, .16, .53, .27, 3, params={
                    "text": hook, "color": "#F4F6FA", "font_size": 58,
                    "min_font_size": 34, "max_lines": 6, "line_height": 1.03,
                }),
                frame("studio.frame.body.v1", .06, .46, .50, .18, 4, params={
                    "text": "{{brief.trust_strategy}}" if template else str(brief["trust_strategy"]),
                    "color": "#A3ADBD", "font_size": 30, "min_font_size": 21,
                    "max_lines": 6, "line_height": 1.1,
                }),
            ]
        else:
            common += [
                frame("studio.frame.shape.v1", 0, 0, .69, 1, 1,
                      params={"background": "#0C0E12", "opacity": .72, "radius": 0}),
                frame("studio.frame.badge.v1", .06, .17, .34, .055, 3, params={
                    "text": "НЕ ЗАГАЛЬНА ПОРАДА", "color": "#87D0DD", "font_size": 22, "max_lines": 1,
                }),
                frame("studio.frame.headline.v1", .06, .25, .59, .28, 4, params={
                    "text": hook, "color": "#F4F6FA", "font_size": 68,
                    "min_font_size": 38, "max_lines": 5, "line_height": 1.02,
                }),
            ]
        common += [
            frame("studio.frame.offer.v1", .06, .70, .88, .095, 8, params={
                "text": offer, "color": "#F4F6FA", "font_size": 34,
                "min_font_size": 20, "max_lines": 3, "line_height": 1.04,
            }),
            frame("studio.frame.shape.v1", .05, .825, .56, .11, 9,
                  params={"background": "#43BDD3", "opacity": 1, "radius": 24}),
            frame("studio.frame.cta.v1", .08, .845, .50, .07, 10, params={
                "text": cta, "color": "#0C0E12", "font_size": 31,
                "min_font_size": 20, "max_lines": 2, "align": "center", "vertical_align": "center",
            }),
        ]
        return common

    result: list[dict[str, Any]] = []
    for ordinal, angle in enumerate(SAMPLE_ANGLES):
        creative = by_angle[angle]
        template_frames = design(angle, template=True)
        recipe_frames = design(angle, template=False)
        template_by_tool = {item["tool_id"]: item for item in template_frames}
        template = {
            "schema_version": 2,
            "placement_tool_id": "studio.placement.instagram.feed_square.v1",
            "duration_seconds": None, "frame_rate": None,
            "frames": template_frames,
            "modifiers": [{
                "instance_id": new_uuid7(), "tool_id": "studio.layout.single_visual.v1", "params": {},
            }],
            "strategy_ids": ["studio.strategy.one_message.v1", "studio.strategy.specific_cta.v1"],
            "bindings": {
                "hook": {"target": f'/frames/{template_by_tool["studio.frame.headline.v1"]["instance_id"]}/params/text', "source": "creative.hook"},
                "photo": {"target": f'/frames/{template_by_tool["studio.frame.media.v1"]["instance_id"]}/source_asset_ids', "source": "creative.photo"},
                "caption": {"target": "/share/caption", "source": "creative.primary_text"},
                "offer": {"target": f'/frames/{template_by_tool["studio.frame.offer.v1"]["instance_id"]}/params/text', "source": "brief.offer"},
                "cta": {"target": f'/frames/{template_by_tool["studio.frame.cta.v1"]["instance_id"]}/params/text', "source": "brief.cta"},
                "logo": {"target": f'/frames/{template_by_tool["studio.frame.logo.v1"]["instance_id"]}/source_asset_ids', "source": "brand.logo"},
            },
        }
        if angle == "authority":
            body = template_by_tool["studio.frame.body.v1"]
            template["bindings"]["trust"] = {
                "target": f'/frames/{body["instance_id"]}/params/text', "source": "brief.trust_strategy",
            }
        if angle == "practical":
            bodies = [item for item in template_frames if item["tool_id"] == "studio.frame.body.v1"]
            for index, body in enumerate(bodies):
                body["params"]["text"] = f"{{{{brief.key_benefits[{index}]}}}}"
                template["bindings"][f"benefit_{index + 1}"] = {
                    "target": f'/frames/{body["instance_id"]}/params/text',
                    "source": f"brief.key_benefits[{index}]",
                }
        recipe = {
            "schema_version": 2, "parent_recipe_id": None,
            "placement_tool_id": "studio.placement.instagram.feed_square.v1",
            "duration_seconds": None, "frame_rate": None,
            "frames": recipe_frames,
            "modifiers": [{
                "instance_id": new_uuid7(), "tool_id": "studio.layout.single_visual.v1", "params": {},
            }],
            "strategy_ids": ["studio.strategy.one_message.v1", "studio.strategy.specific_cta.v1"],
            "validation_ids": list(DEFAULT_GUARDS),
            "source_reference_ids": list(DEFAULT_SOURCE_REFS),
            "share": {
                "caption": str(creative["primary_text"]),
                "alt_text": SAMPLE_ALT_TEXTS[angle],
            },
        }
        result.append({
            "ordinal": ordinal, "angle": angle, "name": SAMPLE_NAMES[angle],
            "caption": recipe["share"]["caption"], "alt_text": recipe["share"]["alt_text"],
            "template": template, "recipe": recipe,
        })
    return result


def validate_recipe_revision_diff(
    before: Mapping[str, Any], after: Mapping[str, Any], *, target_instance_id: str | None,
) -> list[dict[str, Any]]:
    """Derive the authoritative patch and enforce component scope independently of the model."""
    if before.get("schema_version") != 2 or after.get("schema_version") != 2:
        raise ValueError("wizard revisions require V2 recipes")
    original = _v2_submission(before)
    proposed = dict(after)
    if set(proposed) != set(original):
        raise ValueError("wizard revision fields do not match the V2 owner contract")
    for name in ("frames", "modifiers"):
        if not isinstance(proposed.get(name), list) or any(not isinstance(item, Mapping) for item in proposed[name]):
            raise ValueError(f"wizard revision {name} must contain objects")
    if not isinstance(proposed.get("share"), Mapping):
        raise ValueError("wizard revision share must be an object")
    original_frame_ids = [str(item["instance_id"]) for item in original["frames"]]
    proposed_frame_ids = [str(item.get("instance_id") or "") for item in proposed["frames"]]
    original_modifier_ids = [str(item["instance_id"]) for item in original["modifiers"]]
    proposed_modifier_ids = [str(item.get("instance_id") or "") for item in proposed["modifiers"]]
    if len(set(proposed_frame_ids)) != len(proposed_frame_ids) or len(set(proposed_modifier_ids)) != len(proposed_modifier_ids):
        raise ValueError("wizard revision instance IDs must remain unique")
    original_frames = dict(zip(original_frame_ids, original["frames"], strict=True))
    proposed_frames = dict(zip(proposed_frame_ids, proposed["frames"], strict=True))
    if list(original_frames) != list(proposed_frames):
        raise ValueError("wizard revisions cannot add, remove, or reorder visual frames")
    original_modifiers = dict(zip(original_modifier_ids, original["modifiers"], strict=True))
    proposed_modifiers = dict(zip(proposed_modifier_ids, proposed["modifiers"], strict=True))
    if list(original_modifiers) != list(proposed_modifiers):
        raise ValueError("wizard revisions cannot add, remove, or reorder modifiers")
    for instance_id in original_frames:
        if proposed_frames[instance_id].get("tool_id") != original_frames[instance_id].get("tool_id"):
            raise ValueError("wizard revisions cannot replace semantic frame tools")
    for instance_id in original_modifiers:
        if proposed_modifiers[instance_id].get("tool_id") != original_modifiers[instance_id].get("tool_id"):
            raise ValueError("wizard revisions cannot replace semantic modifier tools")
    original["parent_recipe_id"] = proposed["parent_recipe_id"] = None
    if target_instance_id is not None:
        target = str(UUID(target_instance_id))
        if target not in original_frames:
            raise ValueError("wizard target must be a visual frame in this recipe")
        stripped_before = json.loads(json.dumps(original, ensure_ascii=False))
        stripped_after = json.loads(json.dumps(proposed, ensure_ascii=False))
        before_target = next(item for item in stripped_before["frames"] if item["instance_id"] == target)
        after_target = next(item for item in stripped_after["frames"] if item["instance_id"] == target)
        stripped_before["frames"][stripped_before["frames"].index(before_target)] = {"instance_id": target}
        stripped_after["frames"][stripped_after["frames"].index(after_target)] = {"instance_id": target}
        if stripped_before != stripped_after:
            raise ValueError("selected-component wizard revision changed content outside its target")
    changes: list[dict[str, Any]] = []
    for instance_id, prior in original_frames.items():
        current = proposed_frames[instance_id]
        if prior != current:
            _, prior_digest = _canonical(prior)
            _, current_digest = _canonical(current)
            changes.append({
                "op": "replace", "target": f"frames/{instance_id}",
                "before_sha256": prior_digest, "after_sha256": current_digest,
                "value": current,
            })
    for instance_id, prior in original_modifiers.items():
        current = proposed_modifiers[instance_id]
        if prior != current:
            _, prior_digest = _canonical(prior)
            _, current_digest = _canonical(current)
            changes.append({
                "op": "replace", "target": f"modifiers/{instance_id}",
                "before_sha256": prior_digest, "after_sha256": current_digest,
                "value": current,
            })
    if original["share"] != proposed["share"]:
        _, prior_digest = _canonical(original["share"])
        _, current_digest = _canonical(proposed["share"])
        changes.append({
            "op": "replace", "target": "share", "before_sha256": prior_digest,
            "after_sha256": current_digest, "value": proposed["share"],
        })
    scalar_keys = set(original) - {"frames", "modifiers", "share", "parent_recipe_id"}
    if any(original[key] != proposed[key] for key in scalar_keys):
        raise ValueError("wizard revisions cannot change placement, timing, strategies, or guards")
    if not changes:
        raise ValueError("wizard proposal does not change the recipe")
    return changes


def resolve_template_v2(
    template: Mapping[str, Any], *, brief: Mapping[str, Any], creative: Mapping[str, Any],
    photo_source_asset_id: str, logo_source_asset_id: str,
) -> dict[str, Any]:
    """Resolve every typed binding and assign fresh instance UUIDv7s without persistence."""
    normalized = validate_template(template)
    if normalized["schema_version"] != 2:
        raise ValueError("typed application requires a StudioTemplateV2")
    frames = json.loads(json.dumps(normalized["frames"], ensure_ascii=False))
    resolvers: dict[str, Any] = {
        "creative.hook": str(creative["hook"]),
        "creative.photo": [str(UUID(photo_source_asset_id))],
        "creative.primary_text": str(creative["primary_text"]),
        "creative.image_description": str(creative.get("image_description") or "Natal editorial visual"),
        "brief.offer": str(brief["offer"]), "brief.cta": str(brief["cta"]),
        "brief.trust_strategy": str(brief["trust_strategy"]),
        "brand.logo": [str(UUID(logo_source_asset_id))],
    }
    for index, benefit in enumerate(brief.get("key_benefits") or []):
        resolvers[f"brief.key_benefits[{index}]"] = str(benefit)
    share = {
        "caption": str(creative["primary_text"]),
        "alt_text": str(creative.get("image_description") or "Natal editorial visual"),
    }
    by_id = {item["instance_id"]: item for item in frames}
    for binding in normalized["bindings"].values():
        target, source = binding["target"], binding["source"]
        if source not in resolvers:
            raise ValueError("Studio template binding source is unavailable for this Brief")
        value = resolvers[source]
        if target == "/share/caption":
            share["caption"] = str(value)
            continue
        match = re.fullmatch(r"/frames/([0-9a-f-]{36})/(params/text|source_asset_ids)", target)
        if match is None or match.group(1) not in by_id:
            raise ValueError("Studio template binding target cannot be resolved")
        frame_item = by_id[match.group(1)]
        if match.group(2) == "params/text":
            frame_item["params"]["text"] = str(value)
        else:
            if not isinstance(value, list):
                raise ValueError("Studio media binding must resolve to source asset IDs")
            frame_item["source_asset_ids"] = list(value)
    for item in frames:
        item["instance_id"] = new_uuid7()
    modifiers = json.loads(json.dumps(normalized["modifiers"], ensure_ascii=False))
    for item in modifiers:
        item["instance_id"] = new_uuid7()
    return {
        "schema_version": 2, "parent_recipe_id": None,
        "placement_tool_id": normalized["placement_tool_id"],
        "duration_seconds": normalized["duration_seconds"], "frame_rate": normalized["frame_rate"],
        "frames": frames, "modifiers": modifiers, "strategy_ids": normalized["strategy_ids"],
        "validation_ids": list(DEFAULT_GUARDS), "source_reference_ids": list(DEFAULT_SOURCE_REFS),
        "share": share,
    }
