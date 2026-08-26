"""Deployment canaries for the Result-only bridge modes."""

from __future__ import annotations

from io import BytesIO
import hashlib
import json
from uuid import uuid4

from .config import Settings
from .domain import ProductBriefV1, product_brief_schema
from .provider import StructuredBridge
from .service import load_product_brief_skill, product_brief_system_prompt


CANARY_SCHEMA = {
    "type": "object",
    "properties": {"canary": {"type": "string", "const": "ptw-result-ok"}},
    "required": ["canary"],
    "additionalProperties": False,
}


def main() -> None:
    settings = Settings.from_environment()
    provider = StructuredBridge(settings.bridge_url, settings.bridge_token, settings.model)
    capabilities = provider.capabilities()
    marker = str(uuid4())
    invocations: list[dict[str, object]] = []
    raw_idea = "A guided decision service for people who need one clear next step."
    required_language = "en"
    skill_snapshot = load_product_brief_skill(settings.product_brief_skill_path)
    base_document: dict[str, object] | None = None
    for mode in ("product_brief", "product_brief_revision"):
        value = provider.generate(
            mode=mode,
            system_prompt=product_brief_system_prompt(skill_snapshot, required_language),
            input_payload={
                "brief_id": marker,
                "raw_idea": raw_idea,
                "required_language": required_language,
                "base_brief": base_document,
                "owner_correction": (
                    None if base_document is None
                    else {"section_id": "product_brief", "instruction": "Make the promise more concrete."}
                ),
            },
            output_schema=product_brief_schema(required_language),
            prompt_version="ptw_result_bridge_canary_v1",
            idempotency_key=f"canary:{marker}:{mode}",
        )
        document = ProductBriefV1.from_dict(value["response"], raw_idea=raw_idea)
        base_document = document.to_dict()
        invocations.append({"mode": mode, "request_id": value["invocation"].get("bridge_request_id")})

    candidate = provider.generate_content_candidate(
        system_prompt="Deployment canary. Return only the schema object.",
        input_payload={"canary_id": marker, "mode": "content_candidate_generation"},
        output_schema=CANARY_SCHEMA,
        prompt_version="ptw_result_bridge_canary_v1",
        idempotency_key=f"canary:{marker}:content_candidate_generation",
    )
    if candidate["response"] != {"canary": "ptw-result-ok"}:
        raise SystemExit("bridge canary failed for content_candidate_generation")
    invocations.append({"mode": "content_candidate_generation", "request_id": candidate["invocation"].get("bridge_request_id")})

    from PIL import Image
    output = BytesIO()
    Image.new("RGB", (1080, 1080), "#181C25").save(output, format="JPEG", quality=85)
    image = output.getvalue()
    digest = hashlib.sha256(image).hexdigest()
    critic = provider.generate_content_critic(
        system_prompt="Deployment canary. Inspect the mapped image and return only the schema object.",
        input_payload={"canary_id": marker, "mode": "content_result_critic"},
        images=[{
            "candidate_id": str(uuid4()), "bytes": image, "sha256": digest,
            "width": 1080, "height": 1080,
        }],
        output_schema=CANARY_SCHEMA,
        prompt_version="ptw_result_bridge_canary_v1",
        idempotency_key=f"canary:{marker}:content_result_critic",
    )
    if critic["response"] != {"canary": "ptw-result-ok"}:
        raise SystemExit("bridge canary failed for content_result_critic")
    invocations.append({"mode": "content_result_critic", "request_id": critic["invocation"].get("bridge_request_id"), "input_sha256": digest})

    print(json.dumps({
        "status": "ok", "canary_id": marker, "capabilities": capabilities,
        "invocations": invocations,
    }, indent=2))


if __name__ == "__main__":
    main()
