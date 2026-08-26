"""Independent pixel-aware validation and bounded Studio recomposition."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7

from .studio import (
    PLACEMENTS,
    TOOL_CATALOG,
    _v2_submission,
    tool_catalog,
    validate_recipe,
)


MAX_RECREATIONS = 3
MIN_APPROVAL_SCORE = 8
SCORE_FIELDS = (
    "stop_scroll",
    "hook_quality",
    "message_clarity",
    "visual_copy_fit",
    "composition",
    "hierarchy",
    "legibility",
    "brand_consistency",
    "credibility",
    "placement_fit",
    "accessibility",
)
CHECK_FIELDS = (
    "offer_exact_and_visible",
    "cta_exact_and_visible",
    "claims_honest",
    "hook_specific",
    "one_coherent_message",
    "visual_matches_copy",
    "crop_preserves_subject",
    "components_positioned_safely",
    "hierarchy_clear",
    "small_screen_legible",
    "brand_consistent",
    "caption_matches",
    "alt_text_matches",
    "placement_native",
)
PARAM_PROPERTIES = {
    "text": {"type": "string", "maxLength": 2200},
    "color": {"type": "string"},
    "background": {"type": "string"},
    "font_size": {"type": "integer", "minimum": 12, "maximum": 200},
    "align": {"type": "string", "enum": ["left", "center", "right"]},
    "vertical_align": {"type": "string", "enum": ["top", "center", "bottom"]},
    "line_height": {"type": "number", "minimum": 0.8, "maximum": 2},
    "max_lines": {"type": "integer", "minimum": 1, "maximum": 20},
    "min_font_size": {"type": "integer", "minimum": 12, "maximum": 200},
    "trim_start_seconds": {"type": "number", "minimum": 0, "maximum": 30},
    "original_audio": {"type": "string", "enum": ["preserve", "mute"]},
    "fit": {"type": "string", "enum": ["cover", "contain"]},
    "focal_x": {"type": "number", "minimum": 0, "maximum": 1},
    "focal_y": {"type": "number", "minimum": 0, "maximum": 1},
    "opacity": {"type": "number", "minimum": 0, "maximum": 1},
    "radius": {"type": "integer", "minimum": 0, "maximum": 500},
}


class StudioCreativeValidationError(ValueError):
    """The rendered creative did not pass after all bounded recreations."""

    def __init__(self, attempts: Sequence[Mapping[str, Any]]) -> None:
        self.attempts = tuple(dict(item) for item in attempts)
        comments = list(self.attempts[-1].get("improvement_comments") or []) if attempts else []
        detail = "; ".join(str(item) for item in comments[:3]) or "unspecified review failure"
        super().__init__(
            f"creative validation did not pass after {MAX_RECREATIONS} automatic recreations: {detail}"
        )


@dataclass(frozen=True, slots=True)
class StudioCreativeValidationResult:
    contract: Any
    rendered: Mapping[str, Any]
    attempts: tuple[Mapping[str, Any], ...]
    skill_sha256: str

    @property
    def recreation_count(self) -> int:
        return len(self.attempts) - 1

    def persistence(self) -> dict[str, Any]:
        return {
            "status": "approved",
            "attempt_count": len(self.attempts),
            "recreation_count": self.recreation_count,
            "skill_sha256": self.skill_sha256,
            "attempts": [dict(item) for item in self.attempts],
        }


def _exact(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields do not match the creative validator contract")


def _const_schema(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean", "const": value}
    if isinstance(value, int):
        return {"type": "integer", "const": value}
    if isinstance(value, float):
        return {"type": "number", "const": value}
    if isinstance(value, str):
        return {"type": "string", "const": value}
    if isinstance(value, list):
        return {"type": "array", "const": value}
    raise TypeError("unsupported creative validator constant")


def _params_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": PARAM_PROPERTIES,
        "additionalProperties": False,
    }


def _instance_id_schema(existing_ids: Sequence[str]) -> dict[str, Any]:
    choices: list[dict[str, Any]] = [{"type": "null"}]
    if existing_ids:
        choices.insert(0, {"type": "string", "enum": list(existing_ids)})
    return {"anyOf": choices}


def studio_creative_validation_output_schema(value: Mapping[str, Any]) -> dict[str, Any]:
    """Allow a complete V2 recomposition while keeping protected context constant."""
    document = _v2_submission(value)
    placement = PLACEMENTS[str(document["placement_tool_id"])]
    frame_ids = [str(item["instance_id"]) for item in document["frames"]]
    modifier_ids = [str(item["instance_id"]) for item in document["modifiers"]]
    source_ids = list(value.get("source_asset_ids") or [])
    frame_tools = [
        item["tool_id"] for item in TOOL_CATALOG
        if item["kind"] in {"frame", "motion"}
        and placement["media"] in item["supported_placements"]
        and not item["deprecated"]
    ]
    modifier_tools = [
        item["tool_id"] for item in TOOL_CATALOG
        if item["kind"] in {"layout", "color", "effect"}
        and placement["media"] in item["supported_placements"]
        and not item["deprecated"]
    ]
    frame_schema = {
        "type": "object", "additionalProperties": False,
        "required": [
            "instance_id", "tool_id", "frame", "z_index", "params", "timeline",
            "source_asset_ids",
        ],
        "properties": {
            "instance_id": _instance_id_schema(frame_ids),
            "tool_id": {"type": "string", "enum": frame_tools},
            "frame": {
                "type": "object", "additionalProperties": False,
                "required": ["x", "y", "width", "height"],
                "properties": {
                    key: {"type": "number", "minimum": 0, "maximum": 1}
                    for key in ("x", "y", "width", "height")
                },
            },
            "z_index": {"type": "integer", "minimum": 0, "maximum": 127},
            "params": _params_schema(),
            "timeline": (
                {"type": "null"} if placement["media"] == "static" else {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object", "additionalProperties": False,
                            "required": ["start", "end"],
                            "properties": {
                                "start": {"type": "number", "minimum": 0, "maximum": 30},
                                "end": {"type": "number", "minimum": 0, "maximum": 30},
                            },
                        },
                    ]
                }
            ),
            "source_asset_ids": {
                "type": "array", "maxItems": len(source_ids), "uniqueItems": True,
                "items": ({"type": "string", "enum": source_ids} if source_ids else {"type": "string"}),
            },
        },
    }
    modifier_schema = {
        "type": "object", "additionalProperties": False,
        "required": ["instance_id", "tool_id", "params"],
        "properties": {
            "instance_id": _instance_id_schema(modifier_ids),
            "tool_id": {"type": "string", "enum": modifier_tools},
            "params": _params_schema(),
        },
    }
    document_schema = {
        "type": "object", "additionalProperties": False,
        "required": list(document),
        "properties": {
            "schema_version": {"type": "integer", "const": 2},
            "parent_recipe_id": _const_schema(document["parent_recipe_id"]),
            "placement_tool_id": _const_schema(document["placement_tool_id"]),
            "duration_seconds": _const_schema(document["duration_seconds"]),
            "frame_rate": _const_schema(document["frame_rate"]),
            "frames": {"type": "array", "minItems": 1, "maxItems": 64, "items": frame_schema},
            "modifiers": {"type": "array", "maxItems": 32, "items": modifier_schema},
            "strategy_ids": _const_schema(document["strategy_ids"]),
            "validation_ids": _const_schema(document["validation_ids"]),
            "source_reference_ids": _const_schema(document["source_reference_ids"]),
            "share": {
                "type": "object", "additionalProperties": False,
                "required": ["caption", "alt_text"],
                "properties": {
                    "caption": {"type": "string", "minLength": 1, "maxLength": 2200},
                    "alt_text": {"type": "string", "minLength": 1, "maxLength": 1000},
                },
            },
        },
    }
    return {
        "type": "object", "additionalProperties": False,
        "required": [
            "schema_version", "verdict", "summary", "improvement_comments", "scores",
            "checks", "document",
        ],
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "verdict": {"type": "string", "enum": ["approve", "revise"]},
            "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
            "improvement_comments": {
                "type": "array", "maxItems": 12,
                "items": {"type": "string", "minLength": 1, "maxLength": 500},
            },
            "scores": {
                "type": "object", "additionalProperties": False,
                "required": list(SCORE_FIELDS),
                "properties": {
                    key: {"type": "integer", "minimum": 1, "maximum": 10}
                    for key in SCORE_FIELDS
                },
            },
            "checks": {
                "type": "object", "additionalProperties": False,
                "required": list(CHECK_FIELDS),
                "properties": {key: {"type": "boolean"} for key in CHECK_FIELDS},
            },
            "document": document_schema,
        },
    }


def _materialize_new_ids(
    proposed: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any]:
    value = {key: proposed[key] for key in proposed}
    value["frames"] = [dict(item) for item in proposed["frames"]]
    value["modifiers"] = [dict(item) for item in proposed["modifiers"]]
    current_frame_ids = {str(item["instance_id"]) for item in current["frames"]}
    current_modifier_ids = {str(item["instance_id"]) for item in current["modifiers"]}
    seen: set[str] = set()
    for name, allowed in (("frames", current_frame_ids), ("modifiers", current_modifier_ids)):
        for item in value[name]:
            raw_id = item.get("instance_id")
            if raw_id is None:
                item["instance_id"] = new_uuid7()
            else:
                instance_id = str(UUID(str(raw_id)))
                if instance_id not in allowed:
                    raise ValueError("creative validator may retain existing IDs or request server-assigned new IDs")
                item["instance_id"] = instance_id
            if item["instance_id"] in seen:
                raise ValueError("creative validator component IDs must remain unique")
            seen.add(item["instance_id"])
    return value


def validate_studio_creative_review(
    response: Mapping[str, Any], *, current: Mapping[str, Any], project_id: str,
    brief_id: str, brand_kit_id: str, brief: Mapping[str, Any],
) -> tuple[dict[str, Any], Any]:
    """Validate the judgment and enforce every recipe invariant server-side."""
    expected = {
        "schema_version", "verdict", "summary", "improvement_comments", "scores", "checks", "document",
    }
    _exact(response, expected, "creative_review")
    if response.get("schema_version") != 1 or response.get("verdict") not in {"approve", "revise"}:
        raise ValueError("creative validator version or verdict is invalid")
    summary = " ".join(str(response.get("summary") or "").split())
    if not 1 <= len(summary) <= 1000:
        raise ValueError("creative validator summary must contain 1-1000 characters")
    raw_comments = response.get("improvement_comments")
    if not isinstance(raw_comments, list) or len(raw_comments) > 12:
        raise ValueError("creative validator comments must contain at most 12 items")
    comments = [" ".join(str(item).split()) for item in raw_comments]
    if any(not 1 <= len(item) <= 500 for item in comments):
        raise ValueError("creative validator comments must contain 1-500 characters")
    scores = response.get("scores")
    checks = response.get("checks")
    if not isinstance(scores, Mapping) or set(scores) != set(SCORE_FIELDS):
        raise ValueError("creative validator scores do not match the rubric")
    if not isinstance(checks, Mapping) or set(checks) != set(CHECK_FIELDS):
        raise ValueError("creative validator checks do not match the rubric")
    if any(type(scores[key]) is not int for key in SCORE_FIELDS):
        raise ValueError("creative validator scores must be integers")
    normalized_scores = {key: scores[key] for key in SCORE_FIELDS}
    if any(not 1 <= score <= 10 for score in normalized_scores.values()):
        raise ValueError("creative validator scores must be between 1 and 10")
    if any(not isinstance(checks[key], bool) for key in CHECK_FIELDS):
        raise ValueError("creative validator checks must be booleans")
    normalized_checks = {key: bool(checks[key]) for key in CHECK_FIELDS}
    proposed = response.get("document")
    if not isinstance(proposed, Mapping) or set(proposed) != set(_v2_submission(current)):
        raise ValueError("creative validator document does not match StudioRecipeV2")
    materialized = _materialize_new_ids(proposed, _v2_submission(current))
    protected = _v2_submission(current)
    for key in (
        "schema_version", "parent_recipe_id", "placement_tool_id", "duration_seconds",
        "frame_rate", "strategy_ids", "validation_ids", "source_reference_ids",
    ):
        if materialized[key] != protected[key]:
            raise ValueError(f"creative validator cannot change protected recipe field {key}")
    allowed_sources = set(current.get("source_asset_ids") or [])
    proposed_sources = {
        str(source_id)
        for item in materialized["frames"]
        for source_id in item.get("source_asset_ids") or []
    }
    if not proposed_sources <= allowed_sources:
        raise ValueError("creative validator cannot introduce an unapproved source")
    contract = validate_recipe(
        materialized, project_id=project_id, brief_id=brief_id,
        brand_kit_id=brand_kit_id, brief=brief,
    )
    verdict = str(response["verdict"])
    if verdict == "approve":
        if comments or not all(normalized_checks.values()) or min(normalized_scores.values()) < MIN_APPROVAL_SCORE:
            raise ValueError("creative validator approval does not satisfy the complete rubric")
        if _v2_submission(contract.value) != _v2_submission(current):
            raise ValueError("creative validator approval must preserve the reviewed recipe")
    else:
        if not comments:
            raise ValueError("creative validator revision requires actionable comments")
        if _v2_submission(contract.value) == _v2_submission(current):
            raise ValueError("creative validator revision must recreate the recipe")
    return {
        "verdict": verdict, "summary": summary, "improvement_comments": comments,
        "scores": normalized_scores, "checks": normalized_checks,
    }, contract


class StudioCreativeValidator:
    """Render, inspect, recompose, and re-inspect one Studio creative."""

    def __init__(self, bridge: Any, renderer: Any, *, skill_path: Path) -> None:
        self.bridge = bridge
        self.renderer = renderer
        self.skill_path = skill_path
        self._skill_snapshot()

    def _skill_snapshot(self) -> tuple[str, str]:
        if not self.skill_path.is_file():
            raise RuntimeError(f"canonical creative validator skill is unavailable: {self.skill_path}")
        parts = [self.skill_path.read_text(encoding="utf-8")]
        references = self.skill_path.parent / "references"
        if references.is_dir():
            for item in sorted(references.glob("*.md")):
                parts.append(f"\nREFERENCE {item.name}:\n{item.read_text(encoding='utf-8')}")
        content = "\n".join(parts)[:40_000]
        return content, hashlib.sha256(content.encode()).hexdigest()

    def review_and_recreate(
        self, *, recipe_id: str, recipe: Mapping[str, Any], project_id: str,
        brief_id: str, brand_kit_id: str, brief: Mapping[str, Any],
        brand_kit: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]],
        context: Mapping[str, Any],
    ) -> StudioCreativeValidationResult:
        skill, skill_sha256 = self._skill_snapshot()
        contract = validate_recipe(
            _v2_submission(recipe), project_id=project_id, brief_id=brief_id,
            brand_kit_id=brand_kit_id, brief=brief,
        )
        attempts: list[dict[str, Any]] = []
        for iteration in range(MAX_RECREATIONS + 1):
            rendered = self.renderer.render(
                recipe_id=recipe_id, recipe_digest=contract.digest,
                recipe=contract.value, brand_kit=brand_kit, assets=assets,
            )
            if rendered.get("mime_type") != "image/jpeg":
                raise ValueError("automatic creative validation currently requires a static JPEG")
            image = bytes(rendered["bytes"])
            image_sha256 = hashlib.sha256(image).hexdigest()
            source_metadata = [{
                key: value.get(key) for key in (
                    "source_asset_id", "origin", "title", "mime_type", "width", "height",
                    "provider", "external_id", "license", "attribution", "bytes_sha256",
                )
            } for value in assets.values()]
            reviewed = self.bridge.validate_studio_creative(
                system_prompt=(
                    skill
                    + "\nThe exact rendered JPEG is attached. Inspect its pixels. Return one strict review. "
                      "Approve only when every rubric check passes and every score is at least 8. "
                      "On revise, return one complete replacement recipe implementing all comments; "
                      "use null instance_id for every new frame or modifier."
                ),
                input_payload={
                    "iteration": iteration,
                    "maximum_recreations": MAX_RECREATIONS,
                    "render_sha256": image_sha256,
                    "current_recipe_sha256": contract.digest,
                    "current_recipe": _v2_submission(contract.value),
                    "approved_brief": dict(brief),
                    "brand_kit": dict(brand_kit),
                    "approved_sources": source_metadata,
                    "tool_catalog": tool_catalog(),
                    "context": dict(context),
                },
                image_bytes=image,
                image_sha256=image_sha256,
                output_schema=studio_creative_validation_output_schema(contract.value),
                prompt_version="ptw-ad-studio-creative-validation-v1",
            )
            judgment, proposed_contract = validate_studio_creative_review(
                reviewed["response"], current=contract.value, project_id=project_id,
                brief_id=brief_id, brand_kit_id=brand_kit_id, brief=brief,
            )
            attempts.append({
                "iteration": iteration, "render_sha256": image_sha256,
                "recipe_sha256": contract.digest, **judgment,
                "provider_provenance": dict(reviewed["invocation"]),
            })
            if judgment["verdict"] == "approve":
                return StudioCreativeValidationResult(
                    contract=contract, rendered=rendered, attempts=tuple(attempts),
                    skill_sha256=skill_sha256,
                )
            if iteration == MAX_RECREATIONS:
                raise StudioCreativeValidationError(attempts)
            contract = proposed_contract
        raise AssertionError("bounded creative validation loop exhausted unexpectedly")
