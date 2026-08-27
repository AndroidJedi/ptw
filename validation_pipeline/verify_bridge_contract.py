"""Deployment canaries for the Result-only bridge modes."""

from __future__ import annotations

from io import BytesIO
import hashlib
import json
from uuid import uuid4

from commander.ids import new_uuid7

from .content import (
    CandidateV2, INSTAGRAM_REQUIRED_VISUAL_ROLES, SLIDER_NAMES, candidate_output_schema,
    critic_output_schema, validate_critic_response,
)
from .config import Settings
from .domain import ProductBriefV1, product_brief_schema
from .provider import StructuredBridge
from .service import load_product_brief_skill, product_brief_system_prompt


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

    candidate_id, candidate_source_id = new_uuid7(), new_uuid7()
    candidate_brief = {
        "language": "en", "product": "Decision Session",
        "target_audience": "Adults facing one specific career decision",
        "main_pain": "The same unresolved choice keeps consuming attention",
        "promise": "Turn one uncertain decision into a practical next step",
        "key_benefits": ["A focused conversation", "A transparent sequence", "One next action"],
        "cta": "Book a session", "trust_strategy": "Explain the process before commitment",
        "offer": "First short assessment free",
    }
    candidate_payload = {
        "candidate_id": candidate_id, "canary_source_id": candidate_source_id,
        "approved_brief": {"document": candidate_brief},
        "task": "Create one honest Instagram feed-square direction for the approved Brief.",
        "output_profile": "instagram_static_ad_v1",
        "identifier_rule": (
            f"Every visual source_ids array must be empty or contain only {candidate_source_id}. "
            "Never place studio tool IDs in source_ids."
        ),
    }
    candidate = provider.generate_content_candidate(
        system_prompt=(
            "Deployment canary. Return exactly one strict CandidateV2 JSON object. Preserve the "
            "supplied offer and CTA exactly. Request one Pexels real photo with source_asset_id null. "
            "Include each required Instagram visual role exactly once and in this order: "
            + ", ".join(INSTAGRAM_REQUIRED_VISUAL_ROLES)
            + ". Follow the identifier_rule exactly."
        ),
        input_payload=candidate_payload,
        output_schema=candidate_output_schema(
            output_profile="instagram_static_ad_v1",
            allowed_source_ids=[candidate_id, candidate_source_id], approved_asset_ids=[],
        ),
        prompt_version="ptw_result_bridge_canary_v1",
        idempotency_key=f"canary:{marker}:content_candidate_generation",
        response_validator=lambda value: CandidateV2.from_dict(
            value, brief=candidate_brief, output_profile="instagram_static_ad_v1",
            allowed_source_ids=[candidate_id, candidate_source_id], approved_asset_ids=[],
        ).value,
    )
    candidate_document = CandidateV2.from_dict(
        candidate["response"], brief=candidate_brief, output_profile="instagram_static_ad_v1",
        allowed_source_ids=[candidate_id, candidate_source_id], approved_asset_ids=[],
    )
    invocations.append({
        "mode": "content_candidate_generation",
        "request_id": candidate["invocation"].get("bridge_request_id"),
        "response_sha256": candidate_document.digest,
    })

    from PIL import Image
    output = BytesIO()
    Image.new("RGB", (1080, 1080), "#181C25").save(output, format="JPEG", quality=85)
    image = output.getvalue()
    digest = hashlib.sha256(image).hexdigest()
    critic_element_id = new_uuid7()
    critic_parameters = {name: 50 for name in SLIDER_NAMES}
    critic_payload = {
        "run_id": new_uuid7(), "pass": 1,
        "approved_brief": {"document": candidate_brief},
        "task": candidate_payload["task"], "output_profile": "instagram_static_ad_v1",
        "protected": {
            "offer": candidate_brief["offer"], "cta": candidate_brief["cta"],
            "project_id": new_uuid7(), "brand_kit_id": new_uuid7(),
            "source_policy": {"synthetic_people_faces": "prohibited"},
        },
        "candidates": [{
            "candidate_id": candidate_id, "anonymous_alias": "A1",
            "document": candidate_document.value,
            "document_sha256": candidate_document.digest,
            "elements": [{
                "element_id": critic_element_id, "display_alias": "A1.HOOK.01",
                "slot": "hook", "payload": {"text": candidate_document.value["hook"]},
            }],
            "parameters": critic_parameters, "regeneration_count": 0,
            "render_mapping": digest,
        }],
        "prior_pass_summaries": [],
    }
    critic = provider.generate_content_critic(
        system_prompt=(
            "Deployment canary. Inspect the exact mapped JPEG and return a strict critic Pass 1 "
            "document. Evaluate the single candidate and its single supplied element. Set every "
            "hard gate true, every element and candidate score to 10, complexity to none, ranking "
            "to the supplied candidate, pairwise and actions to empty arrays, one concise "
            "observation, and final_selection to null."
        ),
        input_payload=critic_payload,
        images=[{
            "candidate_id": candidate_id, "bytes": image, "sha256": digest,
            "mime_type": "image/jpeg", "width": 1080, "height": 1080,
        }],
        output_schema=critic_output_schema(1, [candidate_id], [critic_element_id]),
        prompt_version="ptw_result_bridge_canary_v1",
        idempotency_key=f"canary:{marker}:content_result_critic",
        response_validator=lambda value: validate_critic_response(
            value, pass_number=1, candidate_ids=[candidate_id],
            element_ids=[critic_element_id], templates={},
            candidate_parameters={candidate_id: critic_parameters},
            candidate_templates=None,
            candidate_element_ids={candidate_id: [critic_element_id]},
            candidate_regeneration_counts={candidate_id: 0},
        ),
    )
    if critic["response"].get("pass") != 1 or critic["response"].get("ranking") != [candidate_id]:
        raise SystemExit("bridge canary failed for content_result_critic")
    invocations.append({"mode": "content_result_critic", "request_id": critic["invocation"].get("bridge_request_id"), "input_sha256": digest})

    print(json.dumps({
        "status": "ok", "canary_id": marker, "capabilities": capabilities,
        "invocations": invocations,
    }, indent=2))


if __name__ == "__main__":
    main()
