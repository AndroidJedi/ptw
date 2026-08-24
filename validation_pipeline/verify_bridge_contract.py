from __future__ import annotations

import json
from uuid import uuid4

from .config import Settings
from .provider import StructuredBridge, VALIDATION_MODES


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
    print(json.dumps({"status": "ok", "canary_id": marker, "invocations": invocations}, indent=2))


if __name__ == "__main__":
    main()

