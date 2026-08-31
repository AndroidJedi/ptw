#!/usr/bin/env python3
"""Render the current no-photo human-story fallback as a diagnostic only."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

from PIL import Image


EVALUATION_DIR = Path(__file__).resolve().parent
SKYNET_ROOT = EVALUATION_DIR.parents[1]
REPOSITORY_ROOT = SKYNET_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from validation_pipeline.studio_universal import DEFAULT_CONFIG
from validation_pipeline.studio_workspace import UniversalStudioWorkspace
from validation_pipeline.universal_experiment import (
    audit_universal_render,
    resolve_strategy_patch,
)
from skynet.tools.preflight_creatives import audit_logo


EVALUATION_ID = "eval-20260831-003-human-story-fallback"
SLIDERS = {
    "hook_pressure": 65,
    "emotional_intensity": 75,
    "conceptual_novelty": 60,
    "information_density": 40,
    "visual_complexity": 65,
}
CONTENT = {
    "schema": "ptw.studio.universal-ad-content.v2",
    "hero_title": "ХТО ПОВЕРНЕТЬСЯ?",
    "supporting_text": (
        "Після кожного візиту Natal оновлює статус. Для клієнта в «Ризику» "
        "запускайте доречний сценарій повернення."
    ),
    "offer": "90 ДНІВ БЕЗКОШТОВНО",
    "bullets": [],
    "cta": "СПРОБУВАТИ NATAL",
}
BRIEF_PROTECTED = {
    "offer": "90 ДНІВ БЕЗКОШТОВНО",
    "cta": "СПРОБУВАТИ NATAL",
}
SOURCE_PATHS = {
    "blocked_packet": SKYNET_ROOT / "plans/exp-20260831-005-generation-packet.json",
    "approved_brief": SKYNET_ROOT / "experiments/exp-20260831-001/brief.json",
    "universal_experiment": REPOSITORY_ROOT / "validation_pipeline/universal_experiment.py",
    "studio_universal": REPOSITORY_ROOT / "validation_pipeline/studio_universal.py",
    "studio_workspace": REPOSITORY_ROOT / "validation_pipeline/studio_workspace.py",
    "visual_audit": REPOSITORY_ROOT / "skills/studio-ui-visual-audit/scripts/audit_universal_studio.py",
    "pixel_preflight": SKYNET_ROOT / "tools/preflight_creatives.py",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def atomic_json(path: Path, value: object) -> None:
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    atomic_bytes(path, data)


def load_visual_audit_module():
    source = SOURCE_PATHS["visual_audit"]
    spec = importlib.util.spec_from_file_location("ptw_studio_visual_audit", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("Studio visual-audit module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resized_png(source: bytes, size: int) -> bytes:
    with Image.open(BytesIO(source)) as image:
        resized = image.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
        output = BytesIO()
        resized.save(output, format="PNG", optimize=False, compress_level=6)
        return output.getvalue()


def main() -> None:
    resolved_strategy = resolve_strategy_patch(
        deepcopy(DEFAULT_CONFIG),
        "human_story",
        SLIDERS,
        sticker_available=False,
        photo_available=False,
    )
    if resolved_strategy["requires_photo"]:
        raise RuntimeError("No-photo fallback unexpectedly requires a photo")
    if resolved_strategy["media_mode"] != "deterministic_texture":
        raise RuntimeError("No-photo fallback did not resolve to deterministic texture")
    configuration = resolved_strategy["configuration"]
    if configuration["background"]["mode"] != "texture":
        raise RuntimeError("No-photo fallback did not select texture mode")

    with tempfile.TemporaryDirectory(prefix="skynet-fallback-integrity-") as temporary:
        workspace = UniversalStudioWorkspace(Path(temporary) / "workspace")
        rendered = workspace.render_experiment(
            configuration=configuration,
            content=CONTENT,
            background_asset=None,
        )

    raw_png = rendered["bytes"]
    preview_360 = resized_png(raw_png, 360)
    preview_120 = resized_png(raw_png, 120)
    layout_audit = audit_universal_render(
        rendered["resolved"],
        configuration=configuration,
        content=CONTENT,
        brief=BRIEF_PROTECTED,
    )
    strict_visual_audit = load_visual_audit_module().audit_variant(
        "human_story_no_photo",
        rendered,
        configuration,
    )
    logo_box = rendered["resolved"]["nodes"]["logo"]["box"]
    pixel_logo_box = {
        key: round(float(logo_box[key]) * 1080)
        for key in ("x", "y", "width", "height")
    }
    with Image.open(BytesIO(raw_png)) as image:
        brand_audit = audit_logo(
            image.convert("RGB"),
            {
                "box": pixel_logo_box,
                "target_colors": ["#383840", "#87D0DD"],
                "minimum_ink_pixels": 1000,
                "minimum_visible_width": 145,
                "minimum_visible_height": 35,
                "minimum_bbox_area_ratio": 0.0045,
                "minimum_wordmark_contrast": 4.5,
            },
            1080 * 1080,
        )
    if not layout_audit["passed"]:
        raise RuntimeError("Fallback failed the local Universal layout audit")

    outputs = {
        "render.png": raw_png,
        "preview-360.png": preview_360,
        "preview-120.png": preview_120,
    }
    for name, data in outputs.items():
        atomic_bytes(EVALUATION_DIR / name, data)

    selected_nodes = {}
    for node_id in ("hero_title", "supporting_text", "offer", "cta", "logo"):
        node = rendered["resolved"]["nodes"][node_id]
        selected_nodes[node_id] = {
            "box": node.get("box"),
            "visible_bounds": node.get("visible_bounds"),
            "text_layout": node.get("text_layout"),
        }
    manifest = {
        "schema": "ptw.skynet.fallback-integrity-render.v1",
        "evaluation_id": EVALUATION_ID,
        "target_packet_id": "packet-exp-20260831-005-e-v1",
        "target_candidate_id": "cand-20260831-005-e",
        "artifact_class": "diagnostic_only_not_a_candidate",
        "candidate_activation_authorized": False,
        "purpose": (
            "Test the current canonical Universal adapter's human_story no-photo "
            "fallback without mutating or satisfying packet 005."
        ),
        "strategy": {
            "template_id": "human_story",
            "template_version": 3,
            "sliders": SLIDERS,
            "media_mode": resolved_strategy["media_mode"],
            "requires_photo": resolved_strategy["requires_photo"],
            "setting_patch": resolved_strategy["setting_patch"],
        },
        "content": CONTENT,
        "protected_copy": BRIEF_PROTECTED,
        "configuration": configuration,
        "source_sha256": {
            name: sha256_bytes(path.read_bytes()) for name, path in SOURCE_PATHS.items()
        },
        "outputs": {
            name: {
                "sha256": sha256_bytes(data),
                "byte_count": len(data),
                "width": int(name.split("-")[1].split(".")[0]) if name.startswith("preview-") else 1080,
                "height": int(name.split("-")[1].split(".")[0]) if name.startswith("preview-") else 1080,
            }
            for name, data in outputs.items()
        },
        "resolved_assets": rendered["resolved"].get("asset_sha256"),
        "selected_nodes": selected_nodes,
        "layout_audit": layout_audit,
        "strict_visual_audit": strict_visual_audit,
        "brand_prominence_audit": brand_audit,
        "limits": [
            "This render bypasses CandidateV2 generation and is not eligible for competition submission.",
            "The supplied human_story template and packet 005 still require real candid photography.",
            "Geometry success does not establish visual-message coherence, advertising outcome, or permission to activate Candidate E.",
        ],
    }
    atomic_json(EVALUATION_DIR / "render-manifest.json", manifest)


if __name__ == "__main__":
    main()
