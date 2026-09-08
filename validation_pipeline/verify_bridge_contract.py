"""Deployment canaries for every retained Brief, Studio, and media mode."""

from __future__ import annotations

import hashlib
import json
import tempfile
from uuid import uuid4

from .config import Settings
from .domain import ProductBriefV1, product_brief_schema
from .landing_pages import landing_generation_schema, validate_landing_composition
from .landing_workspace import LandingWorkspace
from .openai_images import ResultBridgePhoneScreenImageProvider
from .provider import StructuredBridge
from .service import load_product_brief_skill, product_brief_system_prompt
from .studio_creatives import (
    creative_generation_schema, studio_edit_learning_schema,
    validate_studio_edit_learning,
)
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

    def accept(value: dict[str, object], mode: str) -> None:
        invocation = value["invocation"]
        if invocation.get("bridge_attempt") != 1:
            raise RuntimeError(f"{mode} canary required a corrective attempt")
        fingerprint = invocation.get("request_fingerprint")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise RuntimeError(f"{mode} canary omitted its request fingerprint")
        invocations.append({
            "mode": mode,
            "request_id": invocation.get("bridge_request_id"),
            "request_fingerprint": fingerprint,
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
    with tempfile.TemporaryDirectory(prefix="ptw-studio-canary-") as temporary:
        workspace = UniversalStudioWorkspace(temporary)
        detail = workspace.detail()

        def validate_universal_composition(value):
            if set(value) != {"configuration", "content"}:
                raise ValueError("Universal Studio canary response fields are invalid")
            workspace.component_settings(
                state_sha256=detail["state_sha256"],
                configuration=value["configuration"], content=value["content"],
            )
            return value

        composed = provider.call(
            mode="studio_creative_generation", system_prompt=(
                studio_skill + "\n\nThe live catalog in INPUT_JSON is authoritative. "
                "Return a complete bounded configuration and content object."
            ),
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
            prompt_version="studio-creative-composer-v3",
            idempotency_key=f"canary:{marker}:studio_creative_generation",
            response_validator=validate_universal_composition,
        )
    accept(composed, "studio_creative_generation")
    with tempfile.TemporaryDirectory(prefix="ptw-phone-studio-canary-") as temporary:
        phone_workspace = UniversalStudioWorkspace(temporary)
        phone_detail = phone_workspace.apply_template(
            base_sha256=phone_workspace.detail()["state_sha256"],
            template_id="phone_metrics",
        )

        def validate_phone_composition(value):
            if set(value) != {"configuration", "content", "visual_direction"}:
                raise ValueError("Phone Metrics canary response fields are invalid")
            phone_workspace.component_settings(
                state_sha256=phone_detail["state_sha256"],
                configuration=value["configuration"], content=value["content"],
            )
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
            prompt_version="studio-creative-composer-v3",
            idempotency_key=f"canary:{marker}:studio_phone_metrics:v3",
            response_validator=validate_phone_composition,
        )
    accept(phone_composed, "studio_creative_generation_phone_metrics")

    with tempfile.TemporaryDirectory(prefix="ptw-landing-canary-") as temporary:
        landing_detail = LandingWorkspace(temporary).detail()
        landing = provider.call(
            mode="studio_creative_generation",
            system_prompt=settings.landing_composer_skill_path.read_text(encoding="utf-8"),
            input_payload={
                "landing_id": marker,
                "approved_product_brief": base_document,
                "source_post_version": {
                    "template_id": "universal_ad",
                    "configuration": detail["configuration"],
                    "content": detail["content"],
                    "generation": {}, "assets": [], "version_sha256": "0" * 64,
                },
                "live_landing_catalog": landing_detail["catalog"],
                "template_defaults": {
                    "configuration": landing_detail["configuration"],
                    "content": landing_detail["content"],
                },
                "global_landing_skill": "No accepted global Landing lessons yet.",
                "project_landing_skill": "No accepted Project Landing lessons yet.",
            },
            output_schema=landing_generation_schema(),
            prompt_version="landing-page-composer-v4",
            idempotency_key=f"canary:{marker}:landing_composition",
            response_validator=validate_landing_composition,
        )
    accept(landing, "landing_composition")

    studio_private_marker = f"project-private-{marker}"

    def validate_studio_learning(value):
        result = validate_studio_edit_learning(value)
        if studio_private_marker.casefold() in result["global_rule"].casefold():
            raise ValueError("Studio learning canary leaked Project content globally")
        return result

    learned = provider.call(
        mode="studio_edit_learning",
        system_prompt=settings.studio_learner_skill_path.read_text(encoding="utf-8"),
        input_payload={
            "checkpoint_kind": "save", "changed_paths": ["content.hero_title"],
            "before": {"content": {"hero_title": "A useful product"}},
            "after": {"content": {"hero_title": "A clearer useful product"}},
            "project_name": studio_private_marker,
        },
        output_schema=studio_edit_learning_schema(),
        prompt_version="studio-edit-learner-v1",
        idempotency_key=f"canary:{marker}:studio_edit_learning",
        response_validator=validate_studio_learning,
    )
    accept(learned, "studio_edit_learning")
    landing_private_marker = f"landing-private-{marker}"

    def validate_landing_learning(value):
        result = validate_studio_edit_learning(value)
        if landing_private_marker.casefold() in result["global_rule"].casefold():
            raise ValueError("Landing learning canary leaked page content globally")
        return result

    landing_learned = provider.call(
        mode="studio_edit_learning",
        system_prompt=settings.landing_learner_skill_path.read_text(encoding="utf-8"),
        input_payload={
            "checkpoint_kind": "save", "changed_paths": ["content.hero.title"],
            "before": {"content": {"hero": {"title": landing_private_marker}}},
            "after": {"content": {"hero": {"title": "A clearer useful service"}}},
        },
        output_schema=studio_edit_learning_schema(),
        prompt_version="landing-edit-learner-v1",
        idempotency_key=f"canary:{marker}:landing_edit_learning",
        response_validator=validate_landing_learning,
    )
    accept(landing_learned, "landing_edit_learning")
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
