"""Fail-closed release check for the independent Laval structured-LLM bridge."""

from __future__ import annotations

from .config import Settings
from .brand_providers import BRAND_BRIDGE_MODES
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
    if settings.brand_provider == "bridge":
        required_brand = set(BRAND_BRIDGE_MODES.values())
        actual_brand = set(capabilities.get("branding_modes") or [])
        missing_brand = sorted(required_brand - actual_brand)
        unexpected_brand = sorted(actual_brand - required_brand)
        image = capabilities.get("branding_image") or {}
        image_ready = (
            image.get("ready") is True
            and image.get("model") == settings.brand_image_model
            and image.get("provider") == "codex_chatgpt_imagegen"
            and image.get("max_images_per_request") == 1
            and image.get("asset_transport") == "commander_asset_volume"
        )
        if missing_brand or unexpected_brand or not image_ready:
            raise RuntimeError(
                "Branding bridge contract mismatch: "
                f"missing_modes={len(missing_brand)} "
                f"unexpected_modes={len(unexpected_brand)} image_ready={image_ready}"
            )
    else:
        actual_brand = set()
    return {
        "modes": len(actual),
        "branding_modes": len(actual_brand),
        "max_request_bytes": int(capabilities["max_request_bytes"]),
    }


def main() -> None:
    result = verify()
    print(
        "Idea Laval LLM bridge contract ready; "
        f"modes={result['modes']} branding_modes={result['branding_modes']} "
        f"max_request_bytes={result['max_request_bytes']}"
    )


if __name__ == "__main__":
    main()
