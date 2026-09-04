"""Deployment canaries for every retained Brief, Studio, and media mode."""

from __future__ import annotations

import hashlib
import json
import tempfile
from uuid import uuid4

from .config import Settings
from .domain import ProductBriefV1, product_brief_schema
from .openai_images import ResultBridgePhoneScreenImageProvider
from .provider import StructuredBridge
from .service import load_product_brief_skill, product_brief_system_prompt
from .studio_creatives import creative_generation_schema, studio_edit_learning_schema
from .studio_workspace import UniversalStudioWorkspace


def main() -> None:
    settings = Settings.from_environment()
    provider = StructuredBridge(settings.bridge_url, settings.bridge_token, settings.model)
    capabilities = provider.capabilities()
    marker = str(uuid4())
    raw_idea = "A guided decision service for people who need one clear next step."
    required_language = "en"
    skill_snapshot = load_product_brief_skill(settings.product_brief_skill_path)
    base_document: dict[str, object] | None = None
    invocations: list[dict[str, object]] = []
    for mode in ("product_brief", "product_brief_revision"):
        value = provider.generate(
            mode=mode,
            system_prompt=product_brief_system_prompt(skill_snapshot, required_language),
            input_payload={
                "brief_id": marker, "raw_idea": raw_idea,
                "required_language": required_language, "base_brief": base_document,
                "owner_correction": (
                    None if base_document is None
                    else {"section_id": "product_brief", "instruction": "Make the promise more concrete."}
                ),
            },
            output_schema=product_brief_schema(required_language),
            prompt_version="ptw_brief_bridge_canary_v1",
            idempotency_key=f"canary:{marker}:{mode}",
        )
        document = ProductBriefV1.from_dict(
            value["response"], raw_idea=raw_idea,
            required_language=required_language,
        )
        base_document = document.to_dict()
        invocations.append({
            "mode": mode,
            "request_id": value["invocation"].get("bridge_request_id"),
        })
    with tempfile.TemporaryDirectory(prefix="ptw-studio-canary-") as temporary:
        detail = UniversalStudioWorkspace(temporary).detail()
    studio_skill = settings.studio_composer_skill_path.read_text(encoding="utf-8")
    composed = provider.generate(
        mode="studio_creative_generation", system_prompt=studio_skill,
        input_payload={
            "creative_id": marker, "approved_product_brief": base_document,
            "selected_template_id": "universal_ad",
            "live_template_catalog": detail["catalog"],
            "template_defaults": {
                "configuration": detail["configuration"], "content": detail["content"],
            },
            "global_skill": "No accepted global Studio lessons yet.",
            "project_skill": "No accepted Project Studio lessons yet.",
        },
        output_schema=creative_generation_schema(detail),
        prompt_version="studio-creative-composer-v1",
        idempotency_key=f"canary:{marker}:studio_creative_generation",
    )
    invocations.append({
        "mode": "studio_creative_generation",
        "request_id": composed["invocation"].get("bridge_request_id"),
    })
    learned = provider.generate(
        mode="studio_edit_learning",
        system_prompt=settings.studio_learner_skill_path.read_text(encoding="utf-8"),
        input_payload={
            "checkpoint_kind": "save", "changed_paths": ["content.hero_title"],
            "before": {"content": {"hero_title": "A useful product"}},
            "after": {"content": {"hero_title": "A clearer useful product"}},
            "project_name": "Provider canary",
        },
        output_schema=studio_edit_learning_schema(),
        prompt_version="studio-edit-learner-v1",
        idempotency_key=f"canary:{marker}:studio_edit_learning",
    )
    invocations.append({
        "mode": "studio_edit_learning",
        "request_id": learned["invocation"].get("bridge_request_id"),
    })
    media = ResultBridgePhoneScreenImageProvider(
        settings.bridge_url, settings.bridge_token, settings.model,
    )
    generated = media.generate(
        "Create a text-free polished translucent glass unicorn on a warm white field. "
        f"Treat {marker} only as a nonvisual request nonce and never render it.",
    )
    enhanced = media.generate(
        "Refine the same glass unicorn with cleaner lighting and material detail while "
        f"preserving its composition. Treat {marker} only as a nonvisual request nonce.",
        reference_image=generated["bytes"],
    )
    invocations.extend((
        {
            "mode": "phone_screen_generate",
            "request_id": generated["source"].get("bridge_request_id"),
            "output_sha256": hashlib.sha256(generated["bytes"]).hexdigest(),
        },
        {
            "mode": "phone_screen_enhance",
            "request_id": enhanced["source"].get("bridge_request_id"),
            "reference_sha256": enhanced["source"].get("reference_image_sha256"),
            "output_sha256": hashlib.sha256(enhanced["bytes"]).hexdigest(),
        },
    ))
    print(json.dumps({
        "status": "ok", "canary_id": marker,
        "capabilities": capabilities, "invocations": invocations,
    }, indent=2))


if __name__ == "__main__":
    main()
