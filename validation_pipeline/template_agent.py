"""Small structured contracts for reference analysis, composition and comparison."""
from __future__ import annotations

import base64
import hashlib
from typing import Any, Mapping

from .template_components import (COMPONENT_FIELDS, COMPONENT_TYPES, PLACEHOLDERS, ROLES,
    STUDIO_FONT_FAMILIES, apply_edits, bounded_text, box, canonical, catalog, number)
from .provider import enforce_structured_contract_budget, enforce_structured_response_budget

MODE = "template_creation"
PROMPT_VERSION = "template-creation-v1"
REASONING_EFFORT = "xhigh"
from pathlib import Path

_SKILL = Path("/run/ptw-auth/skills/template-creation-agent/SKILL.md")
if not _SKILL.is_file():
    _SKILL = Path(__file__).resolve().parents[1] / "skills/template-creation-agent/SKILL.md"
SYSTEM = _SKILL.read_text(encoding="utf-8")


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def text_schema(maximum=240):
    return {"type": "string", "maxLength": maximum}


BOX_SCHEMA = {"description": "[x,y,width,height] in 0–1000 canvas units, never 0–1 fractions. Width and height >=1; x+width and y+height <=1000.", "type": "array", "items": {"type": "number", "minimum": 0, "maximum": 1000}, "minItems": 4, "maxItems": 4}
ANALYSIS_FIELDS = ("canvas_background", "hierarchy", "alignment_spacing", "proportions", "typography",
                   "placement", "treatments", "crops_focal_points", "density", "responsive")
ANALYSIS_SCHEMA = obj({**{key: text_schema() for key in ANALYSIS_FIELDS},
    "regions": {"type": "array", "maxItems": 12, "items": obj({"role": {"type": "string", "enum": list(ROLES)}, "box": BOX_SCHEMA})},
    "component_types": {"type": "array", "maxItems": 8, "items": {"type": "string", "enum": list(COMPONENT_TYPES)}}})
COMPONENT_SCHEMA = obj({
    **{key: text_schema(40) for key in ("id", "type", "role", "fill", "color", "border_color", "font_family", "align", "placeholder", "fit")},
    **{key: {"type": "number"} for key in ("border_width", "radius", "opacity", "font_size", "font_weight", "focal_x", "focal_y")},
    "box": BOX_SCHEMA, "mobile_box": BOX_SCHEMA, "enabled": {"type": "boolean"},
    "gradient": {"type": "array", "items": text_schema(7), "maxItems": 2}})
EDIT_SCHEMA = obj({"surface": {"type": "string", "enum": ["post", "landing"]}, "path": text_schema(100),
    "value": {"anyOf": [text_schema(320), {"type": "number"}, {"type": "boolean"}, BOX_SCHEMA,
        {"type": "array", "items": text_schema(7), "maxItems": 2}, COMPONENT_SCHEMA]}})
DIFFERENCE_SCHEMA = obj({"surface": {"type": "string", "enum": ["post", "landing"]}, "role": {"type": "string", "enum": list(ROLES)},
    "issue": text_schema(), "severity": {"type": "string", "enum": ["minor", "meaningful"]}, "solvable": {"type": "boolean"}})
GAP_SCHEMA = obj({"capability": text_schema(60), "affected_surfaces": {"type": "array", "maxItems": 2, "items": {"type": "string", "enum": ["post", "landing"]}},
    "evidence": text_schema(400), "proposed_abstraction": text_schema(400), "why_composition_insufficient": text_schema(400)})
STEP_SCHEMA = obj({"edits": {"type": "array", "maxItems": 64, "items": EDIT_SCHEMA},
    "differences": {"type": "array", "maxItems": 16, "items": DIFFERENCE_SCHEMA},
    "capability_gap": {"anyOf": [{"type": "null"}, GAP_SCHEMA]}, "complete": {"type": "boolean"}})


def validate_analysis(value: Mapping[str, Any]) -> dict:
    if set(value) != set(ANALYSIS_SCHEMA["properties"]):
        raise ValueError("Reference analysis fields are invalid")
    result = {key: bounded_text(value[key], 240, key) for key in ANALYSIS_FIELDS}
    if not isinstance(value["regions"], list) or len(value["regions"]) > 12:
        raise ValueError("Reference analysis has too many regions")
    result["regions"] = []
    for region in value["regions"]:
        if not isinstance(region, dict) or set(region) != {"role", "box"} or region["role"] not in ROLES:
            raise ValueError("Reference region is invalid")
        result["regions"].append({"role": region["role"], "box": box(region["box"])})
    types = value["component_types"]
    if not isinstance(types, list) or not 1 <= len(types) <= 8 or any(t not in COMPONENT_TYPES for t in types):
        raise ValueError("Reference component selection is invalid")
    result["component_types"] = list(dict.fromkeys(types))
    return result


def validate_step(value: Mapping[str, Any], documents: dict, *, comparison: bool) -> dict:
    if set(value) != {"edits", "differences", "capability_gap", "complete"} or type(value["complete"]) is not bool:
        raise ValueError("Template agent response fields are invalid")
    apply_edits(documents, value["edits"])
    differences = value["differences"]
    if not isinstance(differences, list) or len(differences) > 16:
        raise ValueError("Template comparison exceeds its bounded observations")
    for d in differences:
        if not isinstance(d, dict) or set(d) != set(DIFFERENCE_SCHEMA["properties"]) or d["surface"] not in documents or d["role"] not in ROLES or d["severity"] not in ("minor", "meaningful") or type(d["solvable"]) is not bool:
            raise ValueError("Template comparison difference is invalid")
        bounded_text(d["issue"], 240, "Comparison issue")
    gap = value["capability_gap"]
    if gap is not None:
        if not comparison:
            raise ValueError("Try existing components and render/compare before declaring a capability gap")
        if not isinstance(gap, dict) or set(gap) != set(GAP_SCHEMA["properties"]):
            raise ValueError("Capability gap fields are invalid")
        for key in ("capability", "evidence", "proposed_abstraction", "why_composition_insufficient"):
            bounded_text(gap[key], 60 if key == "capability" else 400, key)
        surfaces = gap["affected_surfaces"]
        if not isinstance(surfaces, list) or not 1 <= len(surfaces) <= 2 or any(s not in documents for s in surfaces):
            raise ValueError("Capability gap surfaces are invalid")
        import re
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,59}", gap["capability"]) or re.search(r"reference|specific|widget|template\d", gap["capability"], re.I):
            raise ValueError("Capability must name a reusable abstraction")
        if gap["capability"] in COMPONENT_FIELDS or gap["capability"] in COMPONENT_TYPES:
            raise ValueError("The proposed capability already exists; use its existing setting/composition")
        if not any(d["severity"] == "meaningful" and not d["solvable"] for d in differences):
            raise ValueError("A capability gap requires an evidenced unsolvable comparison difference")
    return dict(value)


def artifact(data: bytes, index: int) -> dict:
    return {"name": f"template_image_{index}", "mime_type": "image/png", "sha256": hashlib.sha256(data).hexdigest(), "bytes_base64": base64.b64encode(data).decode()}


def contract(phase: str, run: dict) -> tuple[dict, dict]:
    # Whitelist every field: no registry dump, repository, Project, skills, history or graph.
    payload = {"phase": phase, "scope": run["scope"], "instruction": run["instruction"],
               "reference": run.get("reference"), "image_order": [], "post_template_design": run.get("post_design")}
    if phase == "analyze":
        payload["allowed_component_types"] = list(COMPONENT_TYPES)
        payload["geometry_units"] = "Every region box is [x,y,width,height] in 0–1000 canvas units; e.g. [60,50,880,140]. Never use 0–1 fractions."
        return payload, ANALYSIS_SCHEMA
    payload.update({"analysis": run["analysis"], "definitions": run["documents"],
                    "capabilities": {s: catalog(s, run["analysis"]["component_types"]) for s in run["documents"]}})
    if phase == "compare":
        payload["renders"] = {k: {"geometry": v["geometry"], "failures": v["failures"], "reference_geometry_deltas": v.get("reference_geometry_deltas", [])} for k, v in run["previews"].items()}
    payload["previous_differences"] = (run.get("comparison") or {}).get("differences", [])
    return payload, STEP_SCHEMA


def preflight(phase: str, run: dict) -> dict:
    payload, schema = contract(phase, run)
    return enforce_structured_contract_budget(mode=MODE, system_prompt=SYSTEM, input_payload=payload, output_schema=schema)


def call(provider, phase: str, run: dict, images: list[tuple[str, bytes]], *, cancel_event=None) -> tuple[dict, dict]:
    payload, schema = contract(phase, run)
    payload["image_order"] = [name for name, _ in images]
    measured = enforce_structured_contract_budget(mode=MODE, system_prompt=SYSTEM, input_payload=payload, output_schema=schema)
    validator = validate_analysis if phase == "analyze" else lambda value: validate_step(value, run["documents"], comparison=phase == "compare")
    kwargs = {"mode": MODE, "system_prompt": SYSTEM, "input_payload": payload, "output_schema": schema,
              "idempotency_key": f"template:{run['run_id']}:{run['revision']}:{phase}", "prompt_version": PROMPT_VERSION,
              "response_validator": validator, "reasoning_effort": REASONING_EFFORT}
    if images:
        kwargs["input_artifacts"] = [artifact(data, i) for i, (_, data) in enumerate(images, 1)]
    from .local_codex import LocalCodexStructuredProvider
    if isinstance(provider, LocalCodexStructuredProvider):
        kwargs["cancel_event"] = cancel_event
    result = provider.call(**kwargs)
    response = validator(result["response"])
    size = enforce_structured_response_budget(MODE, response)
    invocation = result.get("invocation", {})
    attempts = invocation.get("attempts", invocation.get("validation_attempts", []))
    return response, {"phase": phase, "contract_bytes": measured, "response_bytes": size,
        "attempt_count": max(1, len(attempts)), "input_artifact_bytes": sum(len(v) for _, v in images),
        "provider": str(invocation.get("provider", "structured"))[:60],
        "model": str(invocation.get("model", getattr(provider, "model", None) or "codex-cli-default"))[:80],
        "reasoning_effort": str(invocation.get("reasoning_effort", REASONING_EFFORT))[:20],
        "prompt_version": PROMPT_VERSION}
