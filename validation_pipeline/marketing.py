"""Versioned owner-selected marketing policy and immutable reservation context."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
from typing import Any, Mapping

APPROACHES = ("benefit_led", "identity_led")


def approach(value: Any = "benefit_led") -> str:
    if not isinstance(value, str) or value not in APPROACHES:
        raise ValueError("marketing_approach must be benefit_led or identity_led")
    return value


def brief_approach(brief: Mapping[str, Any]) -> str:
    document = brief.get("document") or brief
    return approach((brief.get("generation_settings") or {}).get("marketing_approach")
                    or (document.get("positioning") or {}).get("marketing_approach", "benefit_led"))


def generation_settings(selected: str = "benefit_led", *, reference: Path | None = None) -> dict[str, Any]:
    selected = approach(selected)
    if reference is None:
        skill = Path(os.environ.get("PRODUCT_BRIEF_SKILL_PATH", "/run/ptw-auth/skills/product-brief-generator/SKILL.md"))
        if not skill.is_file():
            skill = Path(__file__).resolve().parents[1] / "skills/product-brief-generator/SKILL.md"
        reference = skill.parent / "references/marketing-approaches.md"
    text = reference.read_text(encoding="utf-8")
    common, sections = text.split("\n## benefit_led\n", 1)
    benefit, identity = sections.split("\n## identity_led\n", 1)
    policy = common.strip() + "\n\n" + (benefit if selected == "benefit_led" else identity).strip()
    return {"marketing_approach": selected, "policy_version": 1,
            "policy_sha256": hashlib.sha256(policy.encode()).hexdigest(),
            "policy_text": policy, "output_schema_version": 3}


def verified_settings(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"marketing_approach", "policy_version", "policy_sha256", "policy_text", "output_schema_version"}:
        raise ValueError("Invalid Brief generation settings")
    approach(value["marketing_approach"])
    if value["policy_version"] != 1 or value["output_schema_version"] not in {2, 3}:
        raise ValueError("Unsupported Brief generation settings version")
    policy = value["policy_text"]
    if not isinstance(policy, str) or not 1 <= len(policy.encode()) <= 12_000 or hashlib.sha256(policy.encode()).hexdigest() != value["policy_sha256"]:
        raise ValueError("Brief marketing policy integrity check failed")
    return deepcopy(dict(value))


def correction_settings(base: Mapping[str, Any], selected: str | None) -> dict[str, Any]:
    chosen = brief_approach(base) if selected is None else approach(selected)
    saved = verified_settings(base.get("generation_settings"))
    # A new correction may upgrade the contract; a retry never calls this function.
    return saved if saved and saved["output_schema_version"] == 3 and chosen == saved["marketing_approach"] else generation_settings(chosen)
