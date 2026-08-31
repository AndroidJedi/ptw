"""Non-persisting five-template render, metadata, and replay canary."""

from __future__ import annotations

from io import BytesIO
import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from commander.ids import new_uuid7

from .content import TemplateRegistry
from .natal_brand import natal_brand_document, natal_logo_bytes
from .studio import StudioRenderer, build_manifest, validate_recipe
from .studio_templates import (
    StudioTemplateRegistry, apply_studio_template, replay_template_application,
)


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_DIRECTORY = Path(os.environ.get(
    "CONTENT_CANDIDATE_GENERATOR_SKILL_PATH",
    str(ROOT / "skills/content-candidate-generator/SKILL.md"),
)).parent / "references/templates"


def _jpeg(*, width: int, height: int) -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), "#735A52")
    draw = ImageDraw.Draw(image)
    for index in range(12):
        color = (55 + index * 12, 76 + index * 8, 96 + index * 5)
        left = round(index * width / 12)
        right = round((index + 1) * width / 12)
        draw.rectangle((left, 0, right, height), fill=color)
    draw.ellipse((round(width * .51), round(height * .12), round(width * .95), round(height * .56)), fill="#D9B69C")
    draw.rectangle((round(width * .56), round(height * .48), round(width * .87), round(height * .96)), fill="#4C3542")
    output = BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True, progressive=False)
    return output.getvalue()


def run_canary(output_profile: str = "instagram_static_ad_v1") -> dict[str, Any]:
    from PIL import Image, ImageChops, ImageStat

    strategies = TemplateRegistry(STRATEGY_DIRECTORY).load_active()
    if output_profile not in {"instagram_static_ad_v1", "tiktok_photo_post_v1"}:
        raise ValueError("Studio canary requires a static social profile")
    studios = StudioTemplateRegistry(output_profile=output_profile).load_active(strategies)
    project_id, brief_id, brand_kit_id, logo_id, media_id = [new_uuid7() for _ in range(5)]
    brand = natal_brand_document(logo_id)
    brief = {"offer": "First short assessment free", "cta": "Book a session"}
    candidate = {
        "hook": "The decision is still open at 23:00",
        "headline": "Turn one open decision into a clear next step",
        "primary_text": "A focused conversation makes the mechanism concrete and practical.",
        "supporting_text": "One focused conversation turns uncertainty into a practical next step.",
        "caption": "A focused first step for one unresolved decision.",
        "alt_text": "A person in a real setting beside a concise decision-session offer.",
    }
    width, height = (1080, 1920) if output_profile == "tiktok_photo_post_v1" else (1080, 1080)
    media_bytes = _jpeg(width=width, height=height)
    assets = {
        media_id: {
            "bytes": media_bytes, "mime_type": "image/jpeg", "origin": "canary",
            "provider": "ptw", "external_id": "studio-canary-media", "source_uri": None,
            "license": "PTW canary", "attribution": "PTW non-persisting canary",
            "bytes_sha256": hashlib.sha256(media_bytes).hexdigest(),
        },
        logo_id: {
            "bytes": natal_logo_bytes(), "mime_type": "image/png", "origin": "canonical_brand",
            "provider": "natal", "external_id": "logo-natal-v1",
            "source_uri": "natal/assets/logo-natal.png", "license": "PTW canonical brand asset",
            "attribution": "Natal canonical logo",
            "bytes_sha256": hashlib.sha256(natal_logo_bytes()).hexdigest(),
        },
    }
    brand_record = {
        "brand_kit_id": brand_kit_id, "document": brand,
        "document_sha256": hashlib.sha256(json.dumps(
            brand, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
    }
    renderer = StudioRenderer()
    images: dict[str, Any] = {}
    reports: list[dict[str, Any]] = []
    signatures: set[tuple[Any, ...]] = set()
    for strategy, studio in zip(strategies, studios):
        semantic_ids = {role: new_uuid7() for role in (
            "background", "primary_subject", "headline_block", "supporting_text_block",
            "offer_block", "cta_block", "brand_mark",
        )}
        submission = apply_studio_template(
            template=studio,
            strategy_template={
                "template_id": strategy.template_id, "version": strategy.version,
                "sha256": strategy.digest,
            },
            slider_values=strategy.defaults, candidate=candidate, brief=brief,
            brand_document=brand, media_asset_id=media_id,
            semantic_instance_ids=semantic_ids,
        )
        metadata = submission["modifiers"][0]["params"]
        replay_submission = replay_template_application(metadata)
        if replay_submission != submission:
            raise RuntimeError(f"Studio recipe submission replay failed: {strategy.template_id}")
        contract = validate_recipe(
            submission, project_id=project_id, brief_id=brief_id, brand_kit_id=brand_kit_id,
            brief=brief, brand_document=brand,
        )
        replay_contract = validate_recipe(
            replay_submission, project_id=project_id, brief_id=brief_id,
            brand_kit_id=brand_kit_id, brief=brief, brand_document=brand,
        )
        if replay_contract.digest != contract.digest:
            raise RuntimeError(f"Studio canonical recipe replay failed: {strategy.template_id}")
        recipe_id = new_uuid7()
        rendered = renderer.render(
            recipe_id=recipe_id, recipe_digest=contract.digest, recipe=contract.value,
            brand_kit=brand_record, assets=assets,
        )
        replayed_render = renderer.render(
            recipe_id=recipe_id, recipe_digest=replay_contract.digest, recipe=replay_contract.value,
            brand_kit=brand_record, assets=assets,
        )
        left = Image.open(BytesIO(rendered["bytes"])).convert("RGB")
        right = Image.open(BytesIO(replayed_render["bytes"])).convert("RGB")
        if ImageChops.difference(left, right).getbbox() is not None:
            raise RuntimeError(f"Studio decoded-pixel replay failed: {strategy.template_id}")
        manifest = build_manifest(
            render_id=new_uuid7(), recipe_id=recipe_id, recipe_digest=contract.digest,
            recipe=contract.value, brand_kit=brand_record, assets=assets, rendered=rendered,
        )
        required_production = {
            "schema", "strategy_template", "studio_template", "catalog", "renderer",
            "slider_input", "slider_normalized", "component_instances", "components_sha256",
            "bindings_sha256", "patch_sha256", "parent_recipe_id", "base_recipe_sha256",
        }
        if set(manifest.get("production") or {}) != required_production:
            raise RuntimeError(f"Studio render manifest is incomplete: {strategy.template_id}")
        if manifest["resolved_recipe"] != {"document": dict(contract.value), "sha256": contract.digest}:
            raise RuntimeError(f"Studio resolved recipe manifest is incomplete: {strategy.template_id}")
        signatures.add(tuple(
            (item["key"], item["tool_id"], item["z_index"], item["optional"])
            for item in studio.document["components"]
        ))
        images[strategy.template_id] = left
        reports.append({
            "template_id": strategy.template_id, "recipe_sha256": contract.digest,
            "components_sha256": metadata["components_sha256"],
            "patch_sha256": metadata["patch_sha256"], "frame_count": len(contract.value["frames"]),
        })
    if len(signatures) != 5:
        raise RuntimeError("Studio templates do not have five distinct structural signatures")
    distinctions: list[dict[str, Any]] = []
    names = list(images)
    for left_index, left_name in enumerate(names):
        for right_name in names[left_index + 1:]:
            difference = ImageChops.difference(images[left_name], images[right_name])
            rms = sum(ImageStat.Stat(difference).rms) / 3
            if rms < 18:
                raise RuntimeError(
                    f"Studio template renders are not materially distinct: {left_name}/{right_name}={rms:.2f}"
                )
            distinctions.append({"left": left_name, "right": right_name, "rms": round(rms, 2)})
    ukrainian_brief = {
        "offer": "Перша коротка оцінка безкоштовна", "cta": "Забронювати розмову",
    }
    ukrainian_candidate = {
        "hook": "Коли о 23:00 рішення досі не дає вам спокою",
        "headline": "Перетворіть відкрите рішення на зрозумілий наступний крок",
        "primary_text": (
            "Зосереджена розмова робить механізм конкретним і практичним."
        ),
        "supporting_text": (
            "Одна зосереджена розмова перетворює невизначеність на зрозумілий практичний крок."
        ),
        "caption": "Зосереджений перший крок для рішення, яке вже забирає вашу увагу.",
        "alt_text": "Людина в реальному середовищі поруч із короткою пропозицією розмови.",
    }
    for strategy, studio in zip(strategies, studios):
        submission = apply_studio_template(
            template=studio,
            strategy_template={
                "template_id": strategy.template_id, "version": strategy.version,
                "sha256": strategy.digest,
            },
            slider_values=strategy.defaults, candidate=ukrainian_candidate, brief=ukrainian_brief,
            brand_document=brand, media_asset_id=media_id,
            semantic_instance_ids={role: new_uuid7() for role in (
                "background", "primary_subject", "headline_block", "supporting_text_block",
                "offer_block", "cta_block", "brand_mark",
            )},
        )
        contract = validate_recipe(
            submission, project_id=project_id, brief_id=brief_id, brand_kit_id=brand_kit_id,
            brief=ukrainian_brief, brand_document=brand,
        )
        renderer.render(
            recipe_id=new_uuid7(), recipe_digest=contract.digest, recipe=contract.value,
            brand_kit=brand_record, assets=assets,
        )
    return {
        "status": "ok", "output_profile": output_profile,
        "dimensions": {"width": width, "height": height},
        "templates": reports, "pairwise_distinction": distinctions,
        "language_renders": {"en": 5, "uk": 5},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-profile",
        choices=("instagram_static_ad_v1", "tiktok_photo_post_v1"),
        default="instagram_static_ad_v1",
    )
    args = parser.parse_args()
    print(json.dumps(run_canary(args.output_profile), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
