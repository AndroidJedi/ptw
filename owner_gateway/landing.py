"""Owner-safe handoff from completed Idea Laval cases to the Natal builder."""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from uuid import uuid4

from natal.brief import apply_brief_overrides, brief_from_candidate
from natal.catalog import landing_templates, template_manifest


def templates_response() -> dict[str, Any]:
    return {"items": list(landing_templates())}


def candidates_response(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "items": [brief_from_candidate(item) for item in cases],
        "next_cursor": None,
    }


def prepare_landing_build(
    candidate: Mapping[str, Any],
    requested_template_id: str,
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    prepared = brief_from_candidate(candidate)
    recommended = str(prepared["recommended_template_id"])
    template_id = recommended if requested_template_id in {"", "auto"} else requested_template_id
    template_manifest(template_id)
    brief = apply_brief_overrides(prepared["brief"], overrides)
    build_id = str(uuid4())
    return {
        "build_id": build_id,
        "idea_run_id": prepared["idea_run_id"],
        "template_id": template_id,
        "recommended_template_id": recommended,
        "brief": brief,
    }


# Compatibility for older imports while the production UI rolls forward.
prepare_builder_job = prepare_landing_build
