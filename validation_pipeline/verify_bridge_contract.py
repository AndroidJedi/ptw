"""Deployment canaries for every retained Brief, Studio, and media mode."""

from __future__ import annotations

import hashlib
import base64
import json
import tempfile
from uuid import uuid4

from .config import Settings
from .domain import ProductBriefV1, product_brief_schema
from .landing_pages import (
    LANDING_COMPOSER_PROMPT_VERSION, landing_composition_payload,
    landing_generation_schema, validate_landing_composition,
)
from .landing_workspace import LandingWorkspace
from .creative_analytics import (
    learning_output_schema, normalize_rule, validate_visual_descriptor,
    visual_descriptor_schema,
)
from .openai_images import ResultBridgePhoneScreenImageProvider
from .provider import BRIDGE_STRUCTURED_CONTRACT_LIMIT_BYTES, StructuredBridge
from .service import load_product_brief_skill, product_brief_system_prompt
from .studio_creatives import creative_generation_schema
from .studio_manual_agent import (
    STUDIO_MANUAL_AGENT_PROMPT_VERSION, apply_manual_agent_edits,
    manual_agent_editable_values, manual_agent_payload,
    manual_agent_schema, response_reply, screenshot_artifacts,
)
from .studio_workspace import PostStudioWorkspace


def main() -> None:
    settings = Settings.from_environment()
    provider = StructuredBridge(settings.bridge_url, settings.bridge_token, settings.model)
    capabilities = provider.capabilities()
    marker = str(uuid4())
    raw_idea = "A guided decision service for people who need one clear next step."
    required_language = "en"
    canary_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZgL8AAAAASUVORK5CYII="
    )
    skill_snapshot = load_product_brief_skill(settings.product_brief_skill_path)
    base_document: dict[str, object] | None = None
    invocations: list[dict[str, object]] = []

    def accept(value: dict[str, object], mode: str) -> None:
        invocation = value["invocation"]
        if invocation.get("bridge_attempt") != 1:
            raise RuntimeError(f"{mode} canary required a corrective attempt")
        fingerprint = invocation.get("request_fingerprint")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise RuntimeError(f"{mode} canary omitted its request fingerprint")
        contract_bytes = invocation.get("contract_bytes")
        if (
            not isinstance(contract_bytes, dict)
            or set(contract_bytes) != {
                "system_prompt", "input_payload", "output_schema", "total",
            }
            or any(not isinstance(item, int) or item < 0 for item in contract_bytes.values())
            or contract_bytes["total"] != sum(
                contract_bytes[key] for key in (
                    "system_prompt", "input_payload", "output_schema",
                )
            )
            or contract_bytes["total"] > BRIDGE_STRUCTURED_CONTRACT_LIMIT_BYTES
        ):
            raise RuntimeError(f"{mode} canary reported an invalid contract budget")
        if mode == "landing_composition" and (
            contract_bytes["input_payload"] > 64_000
            or contract_bytes["output_schema"] > 16_000
        ):
            raise RuntimeError("Landing composition canary exceeded its compact contract budget")
        invocations.append({
            "mode": mode,
            "request_id": invocation.get("bridge_request_id"),
            "request_fingerprint": fingerprint,
            "contract_bytes": contract_bytes,
        })

    for mode in ("product_brief", "product_brief_revision"):
        value = provider.call(
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
            response_validator=lambda response: ProductBriefV1.from_dict(
                response, raw_idea=raw_idea, required_language=required_language,
            ).to_dict(),
        )
        document = ProductBriefV1.from_dict(
            value["response"], raw_idea=raw_idea,
            required_language=required_language,
        )
        base_document = document.to_dict()
        accept(value, mode)
    studio_skill = settings.studio_composer_skill_path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="ptw-phone-studio-canary-") as temporary:
        phone_workspace = PostStudioWorkspace(temporary)
        phone_detail = phone_workspace.apply_template(
            base_sha256=phone_workspace.detail()["state_sha256"],
            template_id="phone_metrics",
        )

        def validate_phone_composition(value):
            if set(value) != {"configuration", "content", "visual_direction", "metric_basis"}:
                raise ValueError("Phone Metrics canary response fields are invalid")
            phone_workspace.component_settings(
                state_sha256=phone_detail["state_sha256"],
                configuration=value["configuration"], content=value["content"],
            )
            from .metric_hypotheses import generated_metrics
            generated_metrics(value["content"]["stats"], value["metric_basis"], base_document)
            direction = " ".join(str(value["visual_direction"]).split())
            if not 8 <= len(direction) <= 600:
                raise ValueError("Phone Metrics canary visual direction is invalid")
            return value

        phone_composed = provider.call(
            mode="studio_creative_generation",
            system_prompt=(
                studio_skill + "\n\nThe live catalog in INPUT_JSON is authoritative. "
                "Return a complete bounded configuration and content object."
            ),
            input_payload={
                "creative_id": marker,
                "approved_product_brief": base_document,
                "selected_template_id": "phone_metrics",
                "live_template_catalog": phone_detail["catalog"],
                "template_defaults": {
                    "configuration": phone_detail["configuration"],
                    "content": phone_detail["content"],
                },
                "global_skill": "No accepted global Studio lessons yet.",
                "project_skill": "No accepted Project Studio lessons yet.",
                "creative_direction": {
                    "schema": "ptw.studio.phone-hero-direction.v1",
                    "style": "minimal_sculptural",
                    "background": "isolated_key_element",
                },
            },
            output_schema=creative_generation_schema(phone_detail),
            prompt_version="studio-creative-composer-v4",
            idempotency_key=f"canary:{marker}:studio_phone_metrics:v4",
            response_validator=validate_phone_composition,
        )
        manual_artifacts = screenshot_artifacts([canary_png])
        current_direction = {
            "schema": "ptw.studio.phone-hero-direction.v1",
            "style": "minimal_sculptural",
            "background": "isolated_key_element",
        }
        editable_values = manual_agent_editable_values(
            catalog=phone_detail["catalog"],
            configuration=phone_detail["configuration"],
            content=phone_detail["content"],
            creative_direction=current_direction,
        )

        def validate_manual_edit(value):
            if set(value) != {"edits", "image_actions", "reply"}:
                raise ValueError("Phone Metrics manual Agent canary response fields are invalid")
            if value["image_actions"] != []:
                raise ValueError("No-change Phone Metrics canary requested an image action")
            edited = apply_manual_agent_edits(
                value["edits"], current_values=editable_values,
                configuration=phone_detail["configuration"], content=phone_detail["content"],
                creative_direction=current_direction,
            )
            if edited["creative_direction"] != current_direction:
                raise ValueError("Phone Metrics canary changed the saved creative direction")
            phone_workspace.component_settings(
                state_sha256=phone_detail["state_sha256"],
                configuration=edited["configuration"], content=edited["content"],
            )
            return {
                "configuration": edited["configuration"], "content": edited["content"],
                "creative_direction": edited["creative_direction"], "image_actions": [],
                "reply": response_reply(value["reply"]),
            }

        manual_edit = provider.call(
            mode="studio_manual_edit",
            system_prompt=(
                settings.studio_manual_agent_skill_path.read_text(encoding="utf-8")
                + "\n\nPreserve values unrelated to the latest owner instruction."
            ),
            input_payload=manual_agent_payload(
                surface="post:phone_metrics", entity_id=marker,
                message="Keep the exact content and make no changes or images.", history=[],
                configuration=phone_detail["configuration"], content=phone_detail["content"],
                catalog=phone_detail["catalog"], screenshot_artifact_values=manual_artifacts,
                image_slots=["phone_screen"], current_images=[],
                creative_direction=current_direction,
            ),
            input_artifacts=manual_artifacts,
            output_schema=manual_agent_schema(
                editable_paths=list(editable_values),
                image_slots=["phone_screen"], screenshot_count=1,
            ),
            prompt_version=STUDIO_MANUAL_AGENT_PROMPT_VERSION,
            idempotency_key=f"canary:{marker}:studio_manual_edit",
            response_validator=validate_manual_edit,
        )
    accept(phone_composed, "studio_creative_generation_phone_metrics")
    accept(manual_edit, "studio_manual_edit")

    with tempfile.TemporaryDirectory(prefix="ptw-landing-canary-") as temporary:
        landing_workspace = LandingWorkspace(temporary)
        landing_detail = landing_workspace.detail()
        landing = provider.call(
            mode="studio_creative_generation",
            system_prompt=settings.landing_composer_skill_path.read_text(encoding="utf-8"),
            input_payload=landing_composition_payload(
                landing_id=marker,
                approved_product_brief=base_document,
                source_post_snapshot={
                    "template_id": "phone_metrics",
                    "configuration": phone_composed["response"]["configuration"],
                    "content": phone_composed["response"]["content"],
                    "generation": {}, "assets": [], "version_sha256": "0" * 64,
                },
                content_defaults=landing_detail["content"],
                active_creative_skills={"project": None, "global": None},
                live_landing_catalog=landing_detail["catalog"],
            ),
            output_schema=landing_generation_schema(),
            prompt_version=LANDING_COMPOSER_PROMPT_VERSION,
            idempotency_key=f"canary:{marker}:landing_composition",
            response_validator=validate_landing_composition,
        )
        landing_saved = landing_workspace.save_configuration(
            base_sha256=landing_detail["state_sha256"],
            configuration=landing_detail["configuration"],
            content=landing["response"]["content"],
        )
        if landing_saved["configuration"] != landing_detail["configuration"]:
            raise RuntimeError("Landing composition changed server-owned configuration")
    accept(landing, "landing_composition")

    def validate_performance_learning(value):
        if not isinstance(value, dict) or set(value) != {"candidates"}:
            raise ValueError("performance learning canary fields are invalid")
        if not isinstance(value["candidates"], list) or not value["candidates"]:
            raise ValueError("performance learning canary returned no candidate")
        return {
            "candidates": [
                normalize_rule(item, scope="project", project_id=marker)
                for item in value["candidates"]
            ],
        }

    performance = provider.call(
        mode="creative_performance_learning",
        system_prompt=settings.creative_performance_skill_path.read_text(encoding="utf-8"),
        input_payload={
            "dataset": {
                "schema": "ptw.creative-learning.dataset.v1",
                "scope": "project", "project_id": marker, "surface": "post",
                "minimum_age_hours": 72, "platform_separated": True,
                "sample_size": 2, "project_count": 1, "confidence": "exploratory",
                "priority": ["attributable_outbound_contact_rate", "primary_cta_rate", "high_intent_engagement", "interaction_rate", "reach_or_view_velocity"],
                "items": [
                    {"provider": "instagram", "age_band_hours": 72, "metrics": {"views": 100, "likes": 5, "comments": 2, "shares": 1, "saves": 1}, "funnel": {"landing_view": 10, "primary_cta_click": 3, "contact_click": 2}, "creative": {"template_id": "phone_metrics", "content": {"hero_title": "One clear next step"}, "configuration": {}, "visual_descriptor": {"subject": ["abstract object"], "detail": "medium", "composition": "centered", "density": "sparse", "palette": ["warm white"], "contrast": "high", "human_presence": "none"}}},
                    {"provider": "instagram", "age_band_hours": 72, "metrics": {"views": 100, "likes": 3, "comments": 1, "shares": 0, "saves": 0}, "funnel": {"landing_view": 8, "primary_cta_click": 1, "contact_click": 0}, "creative": {"template_id": "phone_metrics", "content": {"hero_title": "A useful product"}, "configuration": {}, "visual_descriptor": {"subject": ["abstract object"], "detail": "high", "composition": "layered", "density": "dense", "palette": ["blue"], "contrast": "medium", "human_presence": "none"}}},
                ],
            },
            "active_skills": {"project": None, "global": None},
        },
        output_schema=learning_output_schema("project"),
        prompt_version="creative-performance-learner-v1",
        idempotency_key=f"canary:{marker}:creative_performance_learning",
        response_validator=validate_performance_learning,
    )
    accept(performance, "creative_performance_learning")

    approved_png = canary_png
    approved_digest = hashlib.sha256(approved_png).hexdigest()
    visual = provider.call(
        mode="creative_visual_analysis",
        system_prompt=settings.creative_visual_skill_path.read_text(encoding="utf-8"),
        input_payload={"artifact_sha256": approved_digest, "surface": "post", "provider": "canary"},
        input_artifacts=[{
            "name": "approved_png", "mime_type": "image/png",
            "sha256": approved_digest,
            "bytes_base64": base64.b64encode(approved_png).decode(),
        }],
        output_schema=visual_descriptor_schema(),
        prompt_version="creative-visual-analyzer-v1",
        idempotency_key=f"canary:{marker}:creative_visual_analysis",
        response_validator=validate_visual_descriptor,
    )
    accept(visual, "creative_visual_analysis")
    media = ResultBridgePhoneScreenImageProvider(
        settings.bridge_url, settings.bridge_token, settings.model,
    )
    generated = media.generate(
        "Show a guest's hand holding a smartphone and scanning a QR card in a modern hotel room. Include the small label SPA on the card. "
        f"Treat {marker} only as a nonvisual request nonce and never render it.",
    )
    enhanced = media.generate(
        "Refine the same hotel scanning scene with cleaner lighting and material detail while "
        f"preserving its composition. Treat {marker} only as a nonvisual request nonce.",
        reference_image=generated["bytes"],
    )
    invocations.extend((
        {
            "mode": "phone_screen_generate",
            "request_id": generated["source"].get("bridge_request_id"),
            "request_fingerprint": generated["source"].get("request_fingerprint"),
            "output_sha256": hashlib.sha256(generated["bytes"]).hexdigest(),
        },
        {
            "mode": "phone_screen_enhance",
            "request_id": enhanced["source"].get("bridge_request_id"),
            "request_fingerprint": enhanced["source"].get("request_fingerprint"),
            "reference_sha256": enhanced["source"].get("reference_image_sha256"),
            "output_sha256": hashlib.sha256(enhanced["bytes"]).hexdigest(),
        },
    ))
    for invocation in invocations[-2:]:
        fingerprint = invocation.get("request_fingerprint")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise RuntimeError(f"{invocation['mode']} canary omitted its request fingerprint")
    print(json.dumps({
        "status": "ok", "canary_id": marker,
        "capabilities": capabilities, "invocations": invocations,
    }, indent=2))


if __name__ == "__main__":
    main()
