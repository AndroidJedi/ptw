"""Compact, deterministic context shared by Post and Landing agents."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping, Sequence


_SKILL_CONTEXT_BUDGETS = {"project": 4_500, "global": 2_500}
_SKILL_PRECEDENCE = [
    "catalog_brand_and_brief", "explicit_owner_direction",
    "project_rules", "global_spirit", "template_defaults",
]


def _json_bytes(value: Any) -> int:
    return len(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=str,
    ).encode("utf-8"))


def _agent_rule(value: Mapping[str, Any]) -> dict[str, Any]:
    """Drop graph/audit fields that do not affect a composition decision."""

    return {
        "surface": value.get("surface"),
        "family": value.get("family"),
        "instruction": value.get("instruction"),
        "target": deepcopy(value.get("target") or {}),
    }


def _compact_snapshot(
    value: Mapping[str, Any] | None, *, surface: str, byte_budget: int,
) -> dict[str, Any] | None:
    if value is None:
        return None
    rules = [
        _agent_rule(rule) for rule in value.get("rules", [])
        if isinstance(rule, Mapping)
        and bool(rule.get("active", True))
        and not bool(rule.get("tombstone", False))
        and rule.get("surface") in {surface, "both"}
    ]
    selected: list[dict[str, Any]] = []
    # Newer accepted rules are selected first. Reverse again so the model sees
    # them in their original stable order.
    for rule in reversed(rules):
        candidate = [rule, *selected]
        if _json_bytes(candidate) <= byte_budget:
            selected = candidate
    return {
        "skill_snapshot_id": value.get("skill_snapshot_id"),
        "rules_sha256": value.get("rules_sha256"),
        "rules": selected,
        "included_rule_count": len(selected),
        "omitted_rule_count": len(rules) - len(selected),
    }


def compact_active_skills(
    value: Mapping[str, Any], *, surface: str,
) -> dict[str, Any]:
    """Bound agent context while retaining immutable snapshot provenance."""

    if surface not in {"post", "landing"}:
        raise ValueError("Agent skill surface is invalid")
    precedence = value.get("precedence")
    if not isinstance(precedence, Sequence) or isinstance(precedence, (str, bytes)):
        precedence = _SKILL_PRECEDENCE
    return {
        "project": _compact_snapshot(
            value.get("project") if isinstance(value.get("project"), Mapping) else None,
            surface=surface, byte_budget=_SKILL_CONTEXT_BUDGETS["project"],
        ),
        "global": _compact_snapshot(
            value.get("global") if isinstance(value.get("global"), Mapping) else None,
            surface=surface, byte_budget=_SKILL_CONTEXT_BUDGETS["global"],
        ),
        "precedence": [str(item) for item in precedence],
    }
