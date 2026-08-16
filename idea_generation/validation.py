from __future__ import annotations

from decimal import Decimal
from typing import Any

DETAIL_KEYS = {"customer", "problem", "product", "business_model", "distribution", "automation",
               "five_year_exit_logic", "key_risks", "first_validation_test"}
CRITERIA = {"exit_potential", "founder_independence", "distribution", "scalability_economics",
            "defensibility", "speed_capital_efficiency"}


class StructuredOutputError(ValueError):
    pass


def idea(payload: dict[str, Any], valid_parent_ids: set[int], require_parent: bool) -> dict[str, Any]:
    if not isinstance(payload, dict) or not str(payload.get("title", "")).strip() or not str(payload.get("one_liner", "")).strip():
        raise StructuredOutputError("idea title and one_liner are required")
    details = payload.get("details")
    if not isinstance(details, dict) or not DETAIL_KEYS.issubset(details):
        raise StructuredOutputError("idea details are incomplete")
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
        if not isinstance(row.get("strengths"), str) or not isinstance(row.get("critique"), str):
            raise StructuredOutputError("evaluation narrative is required")
    return rows
