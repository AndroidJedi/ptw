"""Fresh schema-bound canaries for every PTW v2 structured bridge mode."""

from __future__ import annotations

import json
from uuid import uuid4

from .config import Settings
from .provider import BridgeProvider, POSITIONING_MODES


CANARY_SCHEMA = {
    "type": "object",
    "properties": {"canary": {"type": "string", "const": "ptw-v2-ok"}},
    "required": ["canary"],
    "additionalProperties": False,
}


def main() -> None:
    settings = Settings.from_environment()
    provider = BridgeProvider(settings.bridge_url, settings.bridge_token, settings.model)
    capabilities = provider.capabilities()
    actual = set(capabilities["marketing_positioning_modes"])
    expected = set(POSITIONING_MODES)
    if not expected.issubset(actual):
        raise SystemExit(f"PTW positioning bridge modes missing: expected={sorted(expected)} actual={sorted(actual)}")
    if set(capabilities["landing_modes"]) != {"natal_landing_revision"}:
        raise SystemExit("PTW landing bridge allowlist must contain only natal_landing_revision")
    marker = str(uuid4())
    invocations = []
    for mode in (*POSITIONING_MODES, "natal_landing_revision"):
        result = provider.generate_structured(
            mode,
            "This is a deployment canary. Return exactly the JSON object allowed by the schema.",
            {"canary_id": marker, "mode": mode, "expected": {"canary": "ptw-v2-ok"}},
            CANARY_SCHEMA,
        )
        if result != {"canary": "ptw-v2-ok"}:
            raise SystemExit(f"schema-bound bridge canary failed for {mode}")
        invocations.append({"mode": mode, "bridge_request_id": provider.last_invocation.get("bridge_request_id")})
    print(json.dumps({"status": "ok", "canary_id": marker, "invocations": invocations}, indent=2))


if __name__ == "__main__":
    main()
