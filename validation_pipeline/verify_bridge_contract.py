"""Deployment canaries for Product Brief plus phone generate/edit media calls."""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from .config import Settings
from .domain import ProductBriefV1, product_brief_schema
from .openai_images import ResultBridgePhoneScreenImageProvider
from .provider import StructuredBridge
from .service import load_product_brief_skill, product_brief_system_prompt


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
