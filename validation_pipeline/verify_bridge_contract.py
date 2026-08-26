"""Deployment canaries for the Result-only bridge modes."""

from __future__ import annotations

from io import BytesIO
import hashlib
import json
from uuid import uuid4

from .config import Settings
from .provider import StructuredBridge


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
    for mode in ("product_brief", "product_brief_revision"):
        value = provider.generate(
            mode=mode,
            system_prompt="Deployment canary. Return only the schema object.",
            input_payload={"canary_id": marker, "mode": mode},
            output_schema=CANARY_SCHEMA,
            prompt_version="ptw_result_bridge_canary_v1",
            idempotency_key=f"canary:{marker}:{mode}",
        )
        if value != {"canary": "ptw-result-ok"}:
            raise SystemExit(f"bridge canary failed for {mode}")
        invocations.append({"mode": mode, "request_id": provider.last_invocation.get("bridge_request_id")})

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
