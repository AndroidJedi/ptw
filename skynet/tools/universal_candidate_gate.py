"""Fail closed before a Universal adapter render receives candidate identity."""

from __future__ import annotations

from typing import Any, Mapping


SCHEMA = "ptw.skynet.universal-candidate-activation-gate.v1"
SUPPORTED_MEDIA_MODES = frozenset({
    "approved_photo",
    "deterministic_texture",
    "native_non_photo",
})
DIAGNOSTIC_ONLY_TEXTURE_STRATEGIES = frozenset({
    "moment_tension",
    "contrast_reframe",
    "mechanism_proof",
    "human_story",
})


def audit_universal_candidate_activation(
    *,
    strategy_id: str,
    media_mode: str,
    layout_audit: Mapping[str, Any],
    strict_visual_audit: Mapping[str, Any],
    brand_prominence_audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a deterministic activation decision from pre-candidate evidence.

    Adapter-v3 deterministic textures keep local rendering available, but the
    four-strategy matrix showed that they are not strategy-complete media and
    systematically fail Natal wordmark contrast. A genuinely non-photo
    creative must use a matching non-photo strategy instead of laundering one
    of these fallbacks into candidate identity.
    """

    if media_mode not in SUPPORTED_MEDIA_MODES:
        raise ValueError(f"unsupported Universal media mode: {media_mode}")

    failures = []
    if (
        strategy_id in DIAGNOSTIC_ONLY_TEXTURE_STRATEGIES
        and media_mode == "deterministic_texture"
    ):
        failures.append({
            "code": "deterministic_texture_diagnostic_only",
            "message": (
                "The current photo-strategy texture fallback is render-only "
                "diagnostic media and cannot receive candidate identity."
            ),
        })
    if layout_audit.get("passed") is not True:
        failures.append({
            "code": "layout_audit_failed",
            "message": "The Universal layout audit did not pass.",
        })
    if strict_visual_audit.get("status") != "passed":
        failures.append({
            "code": "strict_visual_audit_failed",
            "message": "The strict visible-geometry audit did not pass.",
        })
    if brand_prominence_audit.get("status") != "passed":
        failures.append({
            "code": "brand_prominence_failed",
            "message": "The pixel-level brand-prominence audit did not pass.",
        })

    return {
        "schema": SCHEMA,
        "strategy_id": strategy_id,
        "media_mode": media_mode,
        "candidate_activation_authorized": not failures,
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }
