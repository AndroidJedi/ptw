"""Numeric card provenance is copy metadata, never performance evidence."""
from __future__ import annotations
import json
import re
from typing import Any, Mapping


METRIC_NUMERAL_PATTERN = r"[0-9]"
METRIC_EVIDENCE_MAX_LENGTH = 600


def metric_basis_schema() -> dict[str, Any]:
    return {"type": "array", "minItems": 3, "maxItems": 3, "items": {
        "anyOf": [
            {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "origin": {"type": "string", "enum": ["brief_supported"]},
                    "evidence": {
                        "type": "string", "minLength": 1,
                        "maxLength": METRIC_EVIDENCE_MAX_LENGTH,
                        "pattern": METRIC_NUMERAL_PATTERN,
                    },
                },
                "required": ["origin", "evidence"],
            },
            {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "origin": {"type": "string", "enum": ["ai_hypothesis"]},
                    "evidence": {"type": "string", "enum": [""]},
                },
                "required": ["origin", "evidence"],
            },
        ],
    }}


def generated_metrics(stats: list[dict[str, str]], basis: Any, brief: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(basis, list) or len(basis) != 3 or len(stats) != 3:
        raise ValueError("Three numeric metric cards and their source descriptions are required")
    document = json.dumps(brief, ensure_ascii=False)
    result = []
    for stat, source in zip(stats, basis):
        if not re.search(METRIC_NUMERAL_PATTERN, stat["value"]):
            raise ValueError("Every automatically composed metric value must contain a numeral")
        if not isinstance(source, dict) or set(source) != {"origin", "evidence"}:
            raise ValueError("Metric source fields are invalid")
        origin, evidence = source["origin"], source["evidence"]
        if (origin not in {"brief_supported", "ai_hypothesis"}
                or not isinstance(evidence, str)
                or len(evidence) > METRIC_EVIDENCE_MAX_LENGTH):
            raise ValueError("Metric source is invalid")
        if origin == "brief_supported" and (not evidence or evidence not in document or
                not all(number in evidence for number in re.findall(r"\d+(?:[.,]\d+)?", stat["value"]))):
            raise ValueError("Brief-supported metrics require an exact supporting Brief excerpt containing the quantity")
        if origin == "ai_hypothesis" and evidence:
            raise ValueError("AI metric hypotheses require empty evidence")
        result.append({**stat, "origin": origin, "validation_status": "unvalidated",
                       "evidence": evidence if origin == "brief_supported" else ""})
    return result


def reconcile_metrics(stats: list[dict[str, str]], previous: Any, *, owner_instruction: str | None = None,
                      supplied: Any = None) -> list[dict[str, Any]]:
    previous = previous if isinstance(previous, list) else []
    if supplied is not None:
        if not isinstance(supplied, list) or len(supplied) != 3:
            raise ValueError("Metric provenance requires three records")
        for stat, source in zip(stats, supplied):
            if not isinstance(source, dict) or set(source) != {"value", "label", "origin", "validation_status", "evidence"}:
                raise ValueError("Metric provenance fields are invalid")
            if source["value"] != stat["value"] or source["label"] != stat["label"] or source["origin"] not in {"owner_supplied", "brief_supported", "ai_hypothesis", "legacy_unknown"} or source["validation_status"] != "unvalidated" or not isinstance(source["evidence"], str) or len(source["evidence"]) > 600:
                raise ValueError("Metric provenance does not match the current cards")
        return [dict(item) for item in supplied]
    result = []
    for index, stat in enumerate(stats):
        old = previous[index] if index < len(previous) else {}
        if all(old.get(key) == stat[key] for key in ("value", "label")):
            result.append(dict(old))
            continue
        origin = "owner_supplied"
        if owner_instruction is not None:
            numbers = re.findall(r"\d+(?:[.,]\d+)?", stat["value"])
            if not numbers or not all(number in owner_instruction for number in numbers):
                origin = "ai_hypothesis"
        result.append({**stat, "origin": origin, "validation_status": "unvalidated", "evidence": ""})
    return result
