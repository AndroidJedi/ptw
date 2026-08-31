#!/usr/bin/env python3
"""Render all current photo-strategy fallbacks as a non-candidate matrix."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

from PIL import Image


EVALUATION_DIR = Path(__file__).resolve().parent
SKYNET_ROOT = EVALUATION_DIR.parents[1]
REPOSITORY_ROOT = SKYNET_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from validation_pipeline.studio_universal import DEFAULT_CONFIG
from validation_pipeline.studio_workspace import UniversalStudioWorkspace
from validation_pipeline.universal_experiment import (
    PHOTO_STRATEGIES,
    audit_universal_render,
    resolve_strategy_patch,
)
from skynet.tools.preflight_creatives import audit_logo
from skynet.tools.universal_candidate_gate import audit_universal_candidate_activation


EVALUATION_ID = "eval-20260831-004-photo-fallback-matrix"
STRATEGY_ORDER = (
    "moment_tension",
    "contrast_reframe",
    "mechanism_proof",
    "human_story",
)
CONTENT = {
    "schema": "ptw.studio.universal-ad-content.v2",
    "hero_title": "ХТО ПОВЕРНЕТЬСЯ?",
    "supporting_text": (
        "Після кожного візиту Natal оновлює статус і підказує доречний "
        "сценарій повернення."
    ),
    "offer": "90 ДНІВ БЕЗКОШТОВНО",
    "bullets": [
        "Статус оновлюється після візиту",
        "«Ризик» показує, хто охолов",
        "Запустіть доречний сценарій",
    ],
    "cta": "СПРОБУВАТИ NATAL",
}
BRIEF_PROTECTED = {
    "offer": "90 ДНІВ БЕЗКОШТОВНО",
    "cta": "СПРОБУВАТИ NATAL",
}
TEMPLATE_PATHS = {
    strategy_id: REPOSITORY_ROOT
    / "skills/content-candidate-generator/references/templates"
    / f"{strategy_id}_v3.yaml"
    for strategy_id in STRATEGY_ORDER
}
SOURCE_PATHS = {
    "approved_brief": SKYNET_ROOT / "experiments/exp-20260831-001/brief.json",
    "universal_experiment": REPOSITORY_ROOT / "validation_pipeline/universal_experiment.py",
    "studio_universal": REPOSITORY_ROOT / "validation_pipeline/studio_universal.py",
    "studio_workspace": REPOSITORY_ROOT / "validation_pipeline/studio_workspace.py",
    "visual_audit": REPOSITORY_ROOT
    / "skills/studio-ui-visual-audit/scripts/audit_universal_studio.py",
    "pixel_preflight": SKYNET_ROOT / "tools/preflight_creatives.py",
    "candidate_activation_gate": SKYNET_ROOT / "tools/universal_candidate_gate.py",
    **{f"template_{key}": value for key, value in TEMPLATE_PATHS.items()},
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


def png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=6)
    return output.getvalue()


def resized_png(source: bytes, size: int) -> bytes:
    with Image.open(BytesIO(source)) as image:
        return png_bytes(
            image.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
        )


def contact_png(images: list[bytes], tile_size: int, *, nearest_scale: int = 1) -> bytes:
    if len(images) != 4:
        raise ValueError("The fallback matrix requires exactly four images")
    contact = Image.new("RGB", (tile_size * 2, tile_size * 2), "white")
    for index, data in enumerate(images):
        with Image.open(BytesIO(data)) as tile:
            contact.paste(tile.convert("RGB"), ((index % 2) * tile_size, (index // 2) * tile_size))
    if nearest_scale > 1:
        contact = contact.resize(
            (contact.width * nearest_scale, contact.height * nearest_scale),
            Image.Resampling.NEAREST,
        )
    return png_bytes(contact)


def selected_nodes(resolved: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for node_id in (
        "hero_title",
        "supporting_text",
        "offer",
        "bullet_1",
        "bullet_2",
        "bullet_3",
        "cta",
        "logo",
    ):
        if node_id not in resolved["nodes"]:
            continue
        node = resolved["nodes"][node_id]
        result[node_id] = {
            "box": node.get("box"),
            "visible_bounds": node.get("visible_bounds"),
            "text_layout": node.get("text_layout"),
        }
    return result


def output_record(data: bytes, width: int, height: int) -> dict[str, Any]:
    return {
        "sha256": sha256_bytes(data),
        "byte_count": len(data),
        "width": width,
        "height": height,
    }


def main() -> None:
    if set(STRATEGY_ORDER) != set(PHOTO_STRATEGIES):
        raise RuntimeError("Matrix strategy order no longer matches current photo strategies")

    visual_audit = load_visual_audit_module()
    strategy_records: dict[str, Any] = {}
    raw_outputs: dict[str, bytes] = {}
    previews_360: list[bytes] = []
    previews_120: list[bytes] = []

    for strategy_id in STRATEGY_ORDER:
        template = json.loads(TEMPLATE_PATHS[strategy_id].read_text())
        sliders = template["defaults"]
        resolved_strategy = resolve_strategy_patch(
            deepcopy(DEFAULT_CONFIG),
            strategy_id,
            sliders,
            sticker_available=False,
            photo_available=False,
        )
        if resolved_strategy["requires_photo"]:
            raise RuntimeError(f"{strategy_id} no-photo fallback unexpectedly requires a photo")
        if resolved_strategy["media_mode"] != "deterministic_texture":
            raise RuntimeError(f"{strategy_id} did not resolve to deterministic texture")
        configuration = resolved_strategy["configuration"]
        if configuration["background"]["mode"] != "texture":
            raise RuntimeError(f"{strategy_id} did not select texture mode")

        with tempfile.TemporaryDirectory(prefix=f"skynet-fallback-{strategy_id}-") as temporary:
            workspace = UniversalStudioWorkspace(Path(temporary) / "workspace")
            rendered = workspace.render_experiment(
                configuration=configuration,
                content=CONTENT,
                background_asset=None,
            )

        raw_png = rendered["bytes"]
        preview_360 = resized_png(raw_png, 360)
        preview_120 = resized_png(raw_png, 120)
        raw_outputs[strategy_id] = raw_png
        previews_360.append(preview_360)
        previews_120.append(preview_120)

        layout_audit = audit_universal_render(
            rendered["resolved"],
            configuration=configuration,
            content=CONTENT,
            brief=BRIEF_PROTECTED,
        )
        try:
            strict_visual_audit = {
                "status": "passed",
                "report": visual_audit.audit_variant(
                    f"{strategy_id}_no_photo", rendered, configuration
                ),
            }
        except RuntimeError as error:
            strict_visual_audit = {"status": "failed", "failure": str(error)}

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
        candidate_activation_gate = audit_universal_candidate_activation(
            strategy_id=strategy_id,
            media_mode=resolved_strategy["media_mode"],
            layout_audit=layout_audit,
            strict_visual_audit=strict_visual_audit,
            brand_prominence_audit=brand_audit,
        )

        raw_name = f"{strategy_id}-1080.png"
        preview_360_name = f"{strategy_id}-360.png"
        preview_120_name = f"{strategy_id}-120.png"
        atomic_bytes(EVALUATION_DIR / raw_name, raw_png)
        atomic_bytes(EVALUATION_DIR / preview_360_name, preview_360)
        atomic_bytes(EVALUATION_DIR / preview_120_name, preview_120)
        strategy_records[strategy_id] = {
            "template": {
                "version": template["version"],
                "philosophy": template["philosophy"],
                "visual_grammar": template["visual_grammar"],
                "defaults": sliders,
            },
            "resolved_strategy": {
                "media_mode": resolved_strategy["media_mode"],
                "requires_photo": resolved_strategy["requires_photo"],
                "setting_patch": resolved_strategy["setting_patch"],
            },
            "configuration": configuration,
            "outputs": {
                raw_name: output_record(raw_png, 1080, 1080),
                preview_360_name: output_record(preview_360, 360, 360),
                preview_120_name: output_record(preview_120, 120, 120),
            },
            "resolved_assets": rendered["resolved"].get("asset_sha256"),
            "selected_nodes": selected_nodes(rendered["resolved"]),
            "layout_audit": layout_audit,
            "strict_visual_audit": strict_visual_audit,
            "brand_prominence_audit": brand_audit,
            "candidate_activation_gate": candidate_activation_gate,
        }

    contact_360 = contact_png(previews_360, 360)
    contact_120_nearest = contact_png(previews_120, 120, nearest_scale=3)
    atomic_bytes(EVALUATION_DIR / "contact-360.png", contact_360)
    atomic_bytes(EVALUATION_DIR / "contact-120-nearest.png", contact_120_nearest)

    manifest = {
        "schema": "ptw.skynet.photo-fallback-matrix-render.v1",
        "evaluation_id": EVALUATION_ID,
        "artifact_class": "diagnostic_only_not_candidates",
        "candidate_activation_authorized": False,
        "purpose": (
            "Test whether the current adapter's four deterministic photo-strategy "
            "fallbacks systematically fail Natal brand contrast or strategy-message fit."
        ),
        "controlled_design": {
            "strategy_order_row_major": list(STRATEGY_ORDER),
            "shared_content": CONTENT,
            "protected_copy": BRIEF_PROTECTED,
            "strategy_sliders": "exact canonical v3 defaults",
            "photo_available": False,
            "sticker_available": False,
        },
        "source_sha256": {
            name: sha256_bytes(path.read_bytes()) for name, path in SOURCE_PATHS.items()
        },
        "strategies": strategy_records,
        "contacts": {
            "contact-360.png": output_record(contact_360, 720, 720),
            "contact-120-nearest.png": output_record(contact_120_nearest, 720, 720),
        },
        "limits": [
            "These renders bypass CandidateV2 generation and are not eligible for competition submission.",
            "Texture availability does not satisfy any strategy's visual grammar or authorize a new candidate.",
            "Automated geometry and contrast checks do not establish advertising effectiveness.",
        ],
    }
    atomic_json(EVALUATION_DIR / "render-manifest.json", manifest)


if __name__ == "__main__":
    main()
