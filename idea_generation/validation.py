from __future__ import annotations

from decimal import Decimal
from typing import Any

DETAIL_KEYS = {"customer", "problem", "product", "business_model", "distribution", "automation",
               "three_year_exit_logic", "key_risks", "first_validation_test"}
CRITERIA = {"three_year_exit_potential", "remote_operability_autonomy", "distribution", "scalability_economics",
            "defensibility", "speed_capital_efficiency"}


class StructuredOutputError(ValueError):
    pass


def localized(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"en", "uk"}:
        raise StructuredOutputError(f"{field} must contain exactly en and uk")
    for language in ("en", "uk"):
        content = value[language]
        if isinstance(content, str):
            if not content.strip():
                raise StructuredOutputError(f"{field}.{language} must not be empty")
        elif isinstance(content, list):
            if not content or any(not isinstance(item, str) or not item.strip() for item in content):
                raise StructuredOutputError(f"{field}.{language} must be a non-empty string list")
        else:
            raise StructuredOutputError(f"{field}.{language} has an invalid type")
    return value


def idea(payload: dict[str, Any], valid_parent_ids: set[int], require_parent: bool) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StructuredOutputError("idea must be an object")
    localized(payload.get("title"), "title")
    localized(payload.get("one_liner"), "one_liner")
    if not payload.get("title") or not payload.get("one_liner"):
        raise StructuredOutputError("idea title and one_liner are required")
    details = payload.get("details")
    if not isinstance(details, dict) or not DETAIL_KEYS.issubset(details):
        raise StructuredOutputError("idea details are incomplete")
    for key in DETAIL_KEYS:
        localized(details[key], f"details.{key}")
    parents = payload.get("parent_ids", [])
    if not isinstance(parents, list) or any(type(value) is not int for value in parents):
        raise StructuredOutputError("parent_ids must be integer IDs")
    if not set(parents).issubset(valid_parent_ids):
        raise StructuredOutputError("unknown parent ID")
    if require_parent and not parents:
        raise StructuredOutputError("exploit idea requires a parent")
    return payload


def evaluations(payload: dict[str, Any], idea_ids: list[int]) -> list[dict[str, Any]]:
    rows = payload.get("evaluations") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != len(idea_ids):
        raise StructuredOutputError("one evaluation per idea is required")
    returned = [row.get("idea_id") for row in rows if isinstance(row, dict)]
    if len(returned) != len(rows) or set(returned) != set(idea_ids) or len(set(returned)) != len(returned):
        raise StructuredOutputError("evaluation IDs must exactly match the batch")
    for row in rows:
        score = Decimal(str(row.get("score")))
        if score < 0 or score > 100 or set(row.get("criteria", {})) != CRITERIA:
            raise StructuredOutputError("invalid score or rubric criteria")
        criteria = {key: Decimal(str(value)) for key, value in row["criteria"].items()}
        expected = {
            "three_year_exit_potential": Decimal("25"),
            "remote_operability_autonomy": Decimal("25"),
            "distribution": Decimal("15"),
            "scalability_economics": Decimal("15"),
            "defensibility": Decimal("10"),
            "speed_capital_efficiency": Decimal("10"),
        }
        if any(value < 0 or value > expected[key] for key, value in criteria.items()):
            raise StructuredOutputError("rubric criterion exceeds its weight")
        if abs(sum(criteria.values()) - score) > Decimal("0.01"):
            raise StructuredOutputError("rubric criteria must sum to score")
        if not isinstance(row.get("strengths"), str) or not isinstance(row.get("critique"), str):
            raise StructuredOutputError("evaluation narrative is required")
    return rows
