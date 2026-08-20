"""Fail-closed release check for the independent Laval structured-LLM bridge."""

from __future__ import annotations

from .config import Settings
from .laval_schemas import SCHEMAS
from .provider import BridgeProvider


def verify() -> dict[str, int]:
    settings = Settings.from_environment()
    if settings.llm_provider != "bridge":
        raise RuntimeError("production Laval contract verification requires LLM_PROVIDER=bridge")
    capabilities = BridgeProvider(
        settings.llm_bridge_url,
        settings.telegram_token,
        settings.llm_model,
    ).capabilities()
    required = set(SCHEMAS)
    actual = set(capabilities["laval_modes"])
    missing = sorted(required - actual)
    unexpected = sorted(actual - required)
    if missing or unexpected:
        raise RuntimeError(
            "Laval bridge contract mismatch: "
            f"missing_modes={len(missing)} unexpected_modes={len(unexpected)}"
        )
    return {
        "modes": len(actual),
        "max_request_bytes": int(capabilities["max_request_bytes"]),
    }


def main() -> None:
    result = verify()
    print(
        "Idea Laval LLM bridge contract ready; "
        f"modes={result['modes']} max_request_bytes={result['max_request_bytes']}"
    )


if __name__ == "__main__":
    main()
