from __future__ import annotations

import json
from uuid import uuid4

from .config import Settings
from .provider import STUDIO_MODES, StructuredBridge, VALIDATION_MODES


CANARY_SCHEMA = {
    "type": "object",
    "properties": {"canary": {"type": "string", "const": "ptw-validation-ok"}},
    "required": ["canary"],
    "additionalProperties": False,
}


def main() -> None:
    settings = Settings.from_environment()
    provider = StructuredBridge(settings.bridge_url, settings.bridge_token, settings.model)
    provider.capabilities()
    marker = str(uuid4())
    invocations = []
    for mode in VALIDATION_MODES:
        result = provider.generate(
            mode=mode,
            system_prompt="Deployment canary. Return only the object allowed by the schema.",
            input_payload={"canary_id": marker, "mode": mode},
            output_schema=CANARY_SCHEMA,
            prompt_version="ptw_validation_canary_v1",
        )
        if result != {"canary": "ptw-validation-ok"}:
            raise SystemExit(f"schema-bound bridge canary failed for {mode}")
        invocations.append({"mode": mode, "bridge_request_id": provider.last_invocation.get("bridge_request_id")})
    revision = provider.generate_studio_recipe_revision(
        system_prompt="Deployment canary. Do not use image generation. Return only the schema object.",
        input_payload={"canary_id": marker, "mode": "ad_studio_recipe_revision"},
        output_schema=CANARY_SCHEMA,
        prompt_version="ptw_studio_recipe_canary_v1",
    )
    if revision["response"] != {"canary": "ptw-validation-ok"}:
        raise SystemExit("schema-bound bridge canary failed for ad_studio_recipe_revision")
    invocations.append({
        "mode": "ad_studio_recipe_revision",
        "bridge_request_id": revision["invocation"].get("bridge_request_id"),
    })
    graphic = provider.generate_studio_graphic(
        system_prompt=(
            "Deployment canary. Generate exactly one abstract non-human square PNG with no text, "
            "people, faces, logos, or watermark, then return only the schema object."
        ),
        input_payload={"canary_id": marker, "mode": "ad_studio_graphic_generation"},
        output_schema=CANARY_SCHEMA,
        prompt_version="ptw_studio_graphic_canary_v1",
    )
    if graphic["response"] != {"canary": "ptw-validation-ok"}:
        raise SystemExit("schema-bound bridge canary failed for ad_studio_graphic_generation")
    if graphic["image"]["bytes_sha256"] != graphic["image"]["output_digest"]:
        raise SystemExit("Studio graphic canary asset digest mismatch")
    invocations.append({
        "mode": "ad_studio_graphic_generation",
        "bridge_request_id": graphic["invocation"].get("bridge_request_id"),
        "asset_sha256": graphic["image"]["bytes_sha256"],
    })
    print(json.dumps({"status": "ok", "canary_id": marker, "invocations": invocations}, indent=2))


if __name__ == "__main__":
    main()
