"""Versioned Instagram-square adapter for local Universal Studio experiments."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import hashlib
from typing import Any, Mapping

from PIL import Image

from .content import TEMPLATE_IDS
from .studio_universal import normalize_universal_config


PROFILE_ID = "universal_ad_experiment_v1"
ADAPTER_VERSION = 1
PHOTO_STRATEGIES = frozenset({
    "moment_tension", "contrast_reframe", "mechanism_proof", "human_story",
})

# These paths are the complete local strategy authority.  Palette, logo,
# protected copy, component IDs, and undeclared settings remain immutable.
STRATEGY_PATCHES: dict[str, dict[str, Any]] = {
    "moment_tension": {
        "background.mode": "image", "background.image_layout": "full",
        "background.image_percent": 75, "background.image_fit": "cover",
        "background.overlay_opacity": 0.62, "typography.font_family": "Oswald",
        "typography.hero_size": 112, "typography.hero_weight": 800,
        "typography.supporting_size": 28, "layout.content_x": 72,
        "layout.content_y": 190, "layout.content_width": 700, "layout.gap": 14,
        "bullets.enabled": False, "cta.position": "below_text",
        "sticker.enabled": False,
    },
    "contrast_reframe": {
        "background.mode": "image", "background.image_layout": "left",
        "background.image_percent": 75, "background.image_fit": "cover",
        "background.overlay_opacity": 0.68, "typography.font_family": "Inter",
        "typography.hero_size": 104, "typography.hero_weight": 900,
        "typography.supporting_size": 28, "layout.content_x": 520,
        "layout.content_y": 150, "layout.content_width": 500, "layout.gap": 16,
        "bullets.enabled": False, "cta.position": "below_text",
        "sticker.enabled": False,
    },
    "mechanism_proof": {
        "background.mode": "image", "background.image_layout": "left",
        "background.image_percent": 25, "background.image_fit": "cover",
        "background.overlay_opacity": 0.38, "typography.font_family": "Manrope",
        "typography.benefits_font_family": "Manrope", "typography.hero_size": 82,
        "typography.hero_weight": 800, "typography.supporting_size": 26,
        "layout.content_x": 338, "layout.content_y": 142,
        "layout.content_width": 680, "layout.gap": 15,
        "bullets.enabled": True, "bullets.style": "check",
        "cta.position": "below_text", "sticker.enabled": False,
    },
    "human_story": {
        "background.mode": "image", "background.image_layout": "full",
        "background.image_percent": 75, "background.image_fit": "cover",
        "background.overlay_opacity": 0.58,
        "typography.font_family": "Cormorant Garamond",
        "typography.benefits_font_family": "Inter", "typography.hero_size": 102,
        "typography.hero_weight": 700, "typography.supporting_size": 30,
        "layout.content_x": 72, "layout.content_y": 270,
        "layout.content_width": 720, "layout.gap": 18,
        "bullets.enabled": False, "cta.position": "bottom_left",
        "sticker.enabled": False,
    },
    "direct_offer": {
        "background.mode": "texture", "background.texture": "grain",
        "background.texture_intensity": 0.34, "background.overlay_opacity": 0.0,
        "typography.font_family": "Inter", "typography.hero_size": 116,
        "typography.hero_weight": 900, "typography.supporting_size": 38,
        "layout.content_x": 84, "layout.content_y": 170,
        "layout.content_width": 820, "layout.gap": 20,
        "bullets.enabled": False, "cta.style": "filled",
        "cta.position": "below_text", "sticker.enabled": False,
    },
}


def _get(root: Mapping[str, Any], path: str) -> Any:
    group, key = path.split(".", 1)
    return root[group][key]


def resolve_strategy_patch(
    base: Mapping[str, Any], strategy_id: str, sliders: Mapping[str, int], *,
    sticker_available: bool = False,
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

    # Sliders affect only declared, already strategy-owned paths.
    density = int(sliders["information_density"])
    complexity = int(sliders["visual_complexity"])
    hook = int(sliders["hook_pressure"])
    resolved_patch["layout.gap"] = max(8, min(32, int(resolved_patch["layout.gap"]) + round((50 - density) / 10)))
    resolved_patch["typography.hero_size"] = max(64, min(180, int(resolved_patch["typography.hero_size"]) + round((hook - 50) / 5)))
    if strategy_id == "contrast_reframe" and complexity >= 70 and sticker_available:
        resolved_patch["sticker.enabled"] = True
        resolved_patch["sticker.position"] = "right_edge"
        resolved_patch["sticker.width"] = 180
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
        "requires_photo": strategy_id in PHOTO_STRATEGIES,
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
