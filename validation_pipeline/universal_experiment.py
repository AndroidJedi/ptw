"""Versioned Instagram-square adapter for local Universal Studio experiments."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import hashlib
from itertools import combinations
from typing import Any, Mapping, Sequence

from PIL import Image, ImageChops, ImageStat

from .content import TEMPLATE_IDS
from .images import PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA
from .studio_universal import normalize_universal_config


PROFILE_ID = "universal_ad_experiment_v1"
ADAPTER_VERSION = 9
PHOTO_STRATEGIES = frozenset({
    "moment_tension", "contrast_reframe", "mechanism_proof", "human_story",
})
MINIMUM_IMAGE_BACKGROUND_DIRECTIONS = 3
PEXELS_IMAGE_BACKGROUND_STRATEGIES = (
    "moment_tension", "contrast_reframe", "human_story",
)
CANONICAL_STICKER_STRATEGY = "contrast_reframe"
MIN_PAIRWISE_SETTING_DIFFERENCES = 8
MIN_PAIRWISE_MEAN_RGB_DELTA = 12.0

# Exactly three strategies receive distinct Pexels photographs. Any other
# photo-capable strategy remains an intentionally different deterministic
# texture; generated or repository-bundled image fallbacks are forbidden.
PHOTO_FALLBACK_PATCHES: dict[str, dict[str, Any]] = {
    "moment_tension": {
        "background.mode": "texture", "background.texture": "slate",
        "background.texture_intensity": 0.72,
    },
    "contrast_reframe": {
        "background.mode": "texture", "background.texture": "marble",
        "background.texture_intensity": 0.64,
    },
    "mechanism_proof": {
        "background.mode": "texture", "background.texture": "concrete",
        "background.texture_intensity": 0.58,
    },
    "human_story": {
        "background.mode": "texture", "background.texture": "travertine",
        "background.texture_intensity": 0.76,
    },
}

# These paths are the complete local strategy authority. Each strategy owns an
# intentionally different visible palette, hierarchy, CTA treatment, and
# optional-role state. Protected copy, component IDs, brand assets, and every
# undeclared setting remain immutable.
STRATEGY_PATCHES: dict[str, dict[str, Any]] = {
    "moment_tension": {
        "background.mode": "image", "background.image_layout": "full",
        "background.image_percent": 75, "background.image_fit": "cover",
        "background.color": "#4A1634", "background.overlay_color": "#240918",
        "background.overlay_opacity": 0.46, "typography.font_family": "Oswald",
        "typography.hero_size": 112, "typography.hero_weight": 800,
        "typography.supporting_size": 28, "typography.text_color": "#FFFFFF",
        "typography.alignment": "left", "layout.content_x": 72,
        "layout.content_y": 190, "layout.content_width": 650, "layout.gap": 14,
        "bullets.enabled": False, "cta.style": "gradient",
        "cta.position": "below_text", "cta.background_color": "#FFD84D",
        "cta.text_color": "#10233F", "cta.radius": 18,
        "sticker.enabled": False, "logo.position": "top_right",
        "logo.width": 170,
    },
    "contrast_reframe": {
        "background.mode": "image", "background.image_layout": "full",
        "background.image_percent": 75, "background.image_fit": "cover",
        "background.color": "#F3E8D2", "background.overlay_color": "#F3E8D2",
        "background.overlay_opacity": 0.40, "typography.font_family": "Inter",
        "typography.hero_size": 102, "typography.hero_weight": 900,
        "typography.supporting_size": 27, "typography.text_color": "#10233F",
        "typography.alignment": "left", "layout.content_x": 500,
        "layout.content_y": 144, "layout.content_width": 500, "layout.gap": 16,
        "bullets.enabled": False, "cta.style": "outlined",
        "cta.position": "below_text", "cta.background_color": "#10233F",
        "cta.text_color": "#10233F", "cta.radius": 8,
        "sticker.enabled": True, "sticker.position": "bottom_left",
        "sticker.rotation": -8, "sticker.width": 300,
        "sticker.object_scale": 0.9, "sticker.offset_bottom": 28,
        "logo.position": "top_right",
        "logo.width": 160,
    },
    "mechanism_proof": {
        "background.mode": "image", "background.image_layout": "left",
        "background.image_percent": 25, "background.image_fit": "cover",
        "background.color": "#0C5A5C", "background.overlay_color": "#063A3B",
        "background.overlay_opacity": 0.38, "typography.font_family": "Manrope",
        "typography.benefits_font_family": "Manrope", "typography.hero_size": 82,
        "typography.hero_weight": 800, "typography.supporting_size": 25,
        "typography.text_color": "#FFFFFF", "typography.alignment": "left",
        "layout.content_x": 338, "layout.content_y": 122,
        "layout.content_width": 680, "layout.gap": 15,
        "bullets.enabled": True, "bullets.style": "check",
        "cta.style": "reverse", "cta.position": "bottom_right",
        "cta.background_color": "#FFD84D", "cta.text_color": "#10233F",
        "cta.radius": 30, "sticker.enabled": False,
        "logo.position": "top_left", "logo.width": 150,
    },
    "human_story": {
        "background.mode": "image", "background.image_layout": "full",
        "background.image_percent": 75, "background.image_fit": "cover",
        "background.color": "#6B3E2E", "background.overlay_color": "#2B140E",
        "background.overlay_opacity": 0.48,
        "typography.font_family": "Cormorant Garamond",
        "typography.benefits_font_family": "Inter", "typography.hero_size": 102,
        "typography.hero_weight": 700, "typography.supporting_size": 30,
        "typography.text_color": "#FFF6E8", "typography.alignment": "left",
        "layout.content_x": 72, "layout.content_y": 270,
        "layout.content_width": 720, "layout.gap": 18,
        "bullets.enabled": False, "cta.style": "link",
        "cta.position": "bottom_left", "cta.background_color": "#FFD84D",
        "cta.text_color": "#FFD84D", "cta.radius": 0,
        "sticker.enabled": False, "logo.position": "top_left",
        "logo.width": 180,
    },
    "direct_offer": {
        "background.mode": "solid", "background.color": "#FFD84D",
        "background.texture": "grain", "background.texture_intensity": 0.0,
        "background.overlay_color": "#FFD84D", "background.overlay_opacity": 0.0,
        "typography.font_family": "Inter", "typography.hero_size": 116,
        "typography.hero_weight": 900, "typography.supporting_size": 36,
        "typography.text_color": "#10233F", "typography.alignment": "center",
        "layout.content_x": 84, "layout.content_y": 150,
        "layout.content_width": 840, "layout.gap": 20,
        "bullets.enabled": False, "cta.style": "filled",
        "cta.position": "below_text", "cta.background_color": "#10233F",
        "cta.text_color": "#FFD84D", "cta.radius": 40,
        "sticker.enabled": False, "logo.position": "top_right",
        "logo.width": 180,
    },
}


# Every path below has direct visible impact in the resolved 1080px render.
_DIVERSITY_PATHS = (
    "background.mode", "background.color", "background.texture",
    "background.texture_intensity", "background.image_layout",
    "background.image_percent", "background.overlay_color",
    "background.overlay_opacity", "typography.font_family",
    "typography.hero_size", "typography.hero_weight",
    "typography.supporting_size", "typography.text_color",
    "typography.alignment", "layout.content_x", "layout.content_y",
    "layout.content_width", "layout.gap", "bullets.enabled", "bullets.style",
    "cta.style", "cta.position", "cta.background_color", "cta.text_color",
    "cta.radius", "sticker.enabled", "sticker.position", "sticker.rotation",
    "sticker.width", "sticker.offset_bottom", "logo.position", "logo.width",
)


def _get(root: Mapping[str, Any], path: str) -> Any:
    group, key = path.split(".", 1)
    return root[group][key]


def audit_creative_diversity(
    creatives: Sequence[Mapping[str, Any]], *, png_by_creative_id: Mapping[str, bytes],
) -> dict[str, Any]:
    """Fail closed unless all five review Creatives are visibly different."""

    if len(creatives) != 5:
        raise ValueError("Universal diversity audit requires exactly five Creatives")
    creative_ids = [str(item["creative_id"]) for item in creatives]
    if len(set(creative_ids)) != 5 or set(png_by_creative_id) != set(creative_ids):
        raise ValueError("Universal diversity audit Creative/render IDs do not match")
    configurations = {
        creative_id: normalize_universal_config(item["configuration"])
        for creative_id, item in zip(creative_ids, creatives)
    }
    signatures = {
        creative_id: tuple(_get(configuration, path) for path in _DIVERSITY_PATHS)
        for creative_id, configuration in configurations.items()
    }
    modes = {item["background"]["mode"] for item in configurations.values()}
    colors = {item["background"]["color"] for item in configurations.values()}
    fonts = {item["typography"]["font_family"] for item in configurations.values()}
    cta_styles = {item["cta"]["style"] for item in configurations.values()}
    image_backgrounds: list[dict[str, str]] = []
    image_treatments: set[tuple[Any, ...]] = set()
    sticker_sources: list[dict[str, Any]] = []
    logo_backing_absent = True
    for creative_id, creative in zip(creative_ids, creatives):
        configuration = configurations[creative_id]
        background = (
            (creative.get("render_asset_provenance") or {}).get("background") or {}
        )
        if (
            configuration["background"]["mode"] == "image"
            and background.get("media_kind") == "approved_photo"
            and background.get("source", {}).get("provider") == "pexels"
        ):
            digest = str(background.get("sha256") or "")
            if len(digest) == 64:
                image_backgrounds.append({
                    "creative_id": creative_id,
                    "sha256": digest,
                    "media_kind": str(background["media_kind"]),
                    "external_id": str(background["source"].get("external_id") or ""),
                })
                image_treatments.add((
                    configuration["background"]["image_layout"],
                    configuration["background"]["overlay_color"],
                    configuration["background"]["overlay_opacity"],
                    configuration["typography"]["font_family"],
                    configuration["typography"]["alignment"],
                    configuration["layout"]["content_x"],
                ))
        if configuration["sticker"]["enabled"]:
            sticker = ((creative.get("render_asset_provenance") or {}).get("sticker") or {})
            sticker_sources.append(sticker)
        node_ids = {
            str(node.get("id"))
            for node in ((creative.get("universal_manifest") or {}).get("nodes") or [])
            if isinstance(node, Mapping)
        }
        logo_backing_absent = (
            logo_backing_absent
            and not configuration["logo"]["background_enabled"]
            and "logo_surface" not in node_ids
        )
    image_digests = {item["sha256"] for item in image_backgrounds}
    pairs: list[dict[str, Any]] = []
    for left_id, right_id in combinations(creative_ids, 2):
        setting_differences = sum(
            left != right for left, right in zip(signatures[left_id], signatures[right_id])
        )
        with Image.open(BytesIO(png_by_creative_id[left_id])) as left_source:
            left = left_source.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
        with Image.open(BytesIO(png_by_creative_id[right_id])) as right_source:
            right = right_source.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
        mean_rgb_delta = round(sum(ImageStat.Stat(ImageChops.difference(left, right)).mean) / 3, 3)
        pairs.append({
            "left_creative_id": left_id, "right_creative_id": right_id,
            "setting_differences": setting_differences,
            "mean_rgb_delta": mean_rgb_delta,
        })
    minimum_setting_differences = min(item["setting_differences"] for item in pairs)
    minimum_mean_rgb_delta = min(item["mean_rgb_delta"] for item in pairs)
    gates = {
        "five_distinct_setting_signatures": len(set(signatures.values())) == 5,
        "five_distinct_background_colors": len(colors) == 5,
        "exactly_three_pexels_image_backgrounds": (
            len(image_backgrounds) == MINIMUM_IMAGE_BACKGROUND_DIRECTIONS
        ),
        "three_distinct_image_backgrounds": (
            len(image_digests) == MINIMUM_IMAGE_BACKGROUND_DIRECTIONS
            and len({item["external_id"] for item in image_backgrounds})
            == MINIMUM_IMAGE_BACKGROUND_DIRECTIONS
        ),
        "three_distinct_image_treatments": (
            len(image_treatments) >= MINIMUM_IMAGE_BACKGROUND_DIRECTIONS
        ),
        "multiple_background_modes": len(modes) >= 2,
        "ultra_realistic_pexels_sticker": (
            len(sticker_sources) == 1
            and sticker_sources[0].get("authority") == "approved_pexels_photo_sticker"
            and sticker_sources[0].get("source_asset_id")
            and sticker_sources[0].get("source", {}).get("provider") == "pexels"
            and sticker_sources[0].get("source", {}).get("media_type") == "photograph"
            and sticker_sources[0].get("source", {}).get("subject_type") == "physical_object"
            and sticker_sources[0].get("source", {}).get(
                "photographic_object_evidence", {},
            ).get("schema") == PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA
            and sticker_sources[0].get("source", {}).get("transformation")
            == "edge_color_soft_alpha_v1"
            and bool(sticker_sources[0].get("source", {}).get("texture_alignment"))
        ),
        "bullet_direction_present": any(item["bullets"]["enabled"] for item in configurations.values()),
        "four_typography_families": len(fonts) >= 4,
        "four_cta_treatments": len(cta_styles) >= 4,
        "pairwise_setting_distance": minimum_setting_differences >= MIN_PAIRWISE_SETTING_DIFFERENCES,
        "pairwise_pixel_distance": minimum_mean_rgb_delta >= MIN_PAIRWISE_MEAN_RGB_DELTA,
        "logo_backing_absent": logo_backing_absent,
    }
    return {
        "schema": "ptw.studio.universal-ad-diversity-audit.v4",
        "passed": all(gates.values()), "gates": gates,
        "background_modes": sorted(modes), "background_colors": sorted(colors),
        "font_families": sorted(fonts), "cta_styles": sorted(cta_styles),
        "image_backgrounds": image_backgrounds,
        "distinct_image_background_sha256": sorted(image_digests),
        "distinct_image_treatment_count": len(image_treatments),
        "minimum_setting_differences": minimum_setting_differences,
        "minimum_mean_rgb_delta": minimum_mean_rgb_delta,
        "pairs": pairs,
    }


def resolve_strategy_patch(
    base: Mapping[str, Any], strategy_id: str, sliders: Mapping[str, int], *,
    sticker_available: bool = False, photo_available: bool = True,
) -> dict[str, Any]:
    if strategy_id not in TEMPLATE_IDS or strategy_id not in STRATEGY_PATCHES:
        raise ValueError("unknown Universal experiment strategy")
    if set(sliders) != {
        "hook_pressure", "emotional_intensity", "conceptual_novelty",
        "information_density", "visual_complexity",
    }:
        raise ValueError("Universal experiment sliders do not match v1")
    config = deepcopy(dict(base))
    resolved_patch = dict(STRATEGY_PATCHES[strategy_id])
    if strategy_id in PHOTO_STRATEGIES and not photo_available:
        resolved_patch.update(PHOTO_FALLBACK_PATCHES[strategy_id])

    # Sliders affect only declared, already strategy-owned paths.
    density = int(sliders["information_density"])
    hook = int(sliders["hook_pressure"])
    resolved_patch["layout.gap"] = max(8, min(32, int(resolved_patch["layout.gap"]) + round((50 - density) / 10)))
    resolved_patch["typography.hero_size"] = max(64, min(180, int(resolved_patch["typography.hero_size"]) + round((hook - 50) / 5)))
    if strategy_id == CANONICAL_STICKER_STRATEGY:
        resolved_patch["sticker.enabled"] = bool(sticker_available)
    for path, value in resolved_patch.items():
        group, key = path.split(".", 1)
        config[group][key] = value
    normalized = normalize_universal_config(config)
    deltas = [
        {"setting_id": f"configuration.{path}", "before": _get(base, path), "after": _get(normalized, path)}
        for path in sorted(resolved_patch)
        if _get(base, path) != _get(normalized, path)
    ]
    return {
        "profile": PROFILE_ID,
        "adapter_version": ADAPTER_VERSION,
        "strategy_id": strategy_id,
        "sliders": {key: int(value) for key, value in sliders.items()},
        "setting_patch": resolved_patch,
        "setting_deltas": deltas,
        "configuration": normalized,
        "requires_photo": strategy_id in PHOTO_STRATEGIES and photo_available,
        "media_mode": (
            "approved_photo"
            if strategy_id in PHOTO_STRATEGIES and photo_available
            else "deterministic_texture"
            if strategy_id in PHOTO_STRATEGIES
            else "native_non_photo"
        ),
    }


def deterministic_jpeg(png: bytes) -> dict[str, Any]:
    with Image.open(BytesIO(png)) as source:
        image = source.convert("RGB")
        if image.size != (1080, 1080):
            raise ValueError("Universal experiment PNG must be exactly 1080x1080")
        output = BytesIO()
        image.save(
            output, format="JPEG", quality=92, subsampling=0,
            optimize=False, progressive=False,
        )
    data = output.getvalue()
    return {
        "bytes": data, "sha256": hashlib.sha256(data).hexdigest(),
        "mime_type": "image/jpeg", "width": 1080, "height": 1080,
        "encoder": "pillow-jpeg-q92-subsampling-0-v1",
    }


def audit_universal_render(
    resolved: Mapping[str, Any], *, configuration: Mapping[str, Any],
    content: Mapping[str, Any], brief: Mapping[str, Any],
) -> dict[str, Any]:
    nodes = resolved.get("nodes")
    if not isinstance(nodes, Mapping):
        raise ValueError("Universal render is missing resolved nodes")
    required = ["hero_title", "supporting_text", "offer", "cta"]
    if configuration["bullets"]["enabled"] and content["bullets"]:
        required.extend(f"bullet_{index}" for index in range(1, len(content["bullets"]) + 1))
    if configuration["logo"]["enabled"]:
        required.append("logo")
    if configuration["sticker"]["enabled"]:
        required.append("sticker_object")
    missing = [node_id for node_id in required if node_id not in nodes]
    text_ids = [node_id for node_id in required if node_id != "logo"]
    overflow = [
        node_id for node_id in text_ids
        if (nodes[node_id].get("text_layout") or {}).get("overflow")
    ]
    truncation = [
        node_id for node_id in text_ids
        if (nodes[node_id].get("text_layout") or {}).get("truncated")
    ]
    unsafe: list[str] = []
    for node_id in required:
        bounds = nodes.get(node_id, {}).get("visible_bounds") or nodes.get(node_id, {}).get("box") or {}
        x, y = float(bounds.get("x", -1)), float(bounds.get("y", -1))
        width, height = float(bounds.get("width", 0)), float(bounds.get("height", 0))
        if x < 0.04 or y < 0.04 or x + width > 0.96 or y + height > 0.96 or width <= 0 or height <= 0:
            unsafe.append(node_id)

    flow = ["hero_title", "supporting_text", "offer"]
    if configuration["bullets"]["enabled"] and content["bullets"]:
        flow.append("bullet_1")
        flow.append(f"bullet_{len(content['bullets'])}")
    if configuration["cta"]["position"] == "below_text":
        flow.append("cta")
    collisions: list[str] = []
    previous_id: str | None = None
    previous_bottom = -1.0
    for node_id in flow:
        bounds = nodes.get(node_id, {}).get("visible_bounds") or {}
        top = float(bounds.get("y", -1))
        bottom = top + float(bounds.get("height", 0))
        if previous_id is not None and top <= previous_bottom:
            collisions.append(f"{previous_id}:{node_id}")
        previous_id, previous_bottom = node_id, bottom

    contrast_ok = (
        float(configuration["background"]["overlay_opacity"]) >= 0.35
        if configuration["background"]["mode"] == "image" else True
    )
    exact_offer = content["offer"] == brief["offer"]
    exact_cta = content["cta"] == brief["cta"]
    gates = {
        "component_coverage": not missing,
        "overflow_absent": not overflow,
        "truncation_absent": not truncation,
        "collision_absent": not collisions,
        "safe_area": not unsafe,
        "contrast": contrast_ok,
        "exact_offer": exact_offer,
        "exact_cta": exact_cta,
        "semantic_flow": not collisions,
    }
    return {
        "schema": "ptw.studio.universal-ad-layout-audit.v1",
        "passed": all(gates.values()), "gates": gates,
        "missing_nodes": missing, "overflow_nodes": overflow,
        "truncated_nodes": truncation, "unsafe_nodes": unsafe,
        "collisions": collisions,
    }
