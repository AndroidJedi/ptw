"""Deployment canaries for the Result-only bridge modes."""

from __future__ import annotations

import json
from uuid import uuid4

from commander.ids import new_uuid7

from .content import (
    CandidateV2, INSTAGRAM_REQUIRED_VISUAL_ROLES, candidate_output_schema,
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
        document = ProductBriefV1.from_dict(
            value["response"], raw_idea=raw_idea, required_language=required_language,
        )
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

    print(json.dumps({
        "status": "ok", "canary_id": marker, "capabilities": capabilities,
        "invocations": invocations,
    }, indent=2))


if __name__ == "__main__":
    main()
