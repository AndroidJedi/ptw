"""Owner-safe handoff from completed Idea Laval cases to the Natal builder."""

from __future__ import annotations

import json
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


def prepare_builder_job(
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
    output_path = f"output/landings/{str(prepared['idea_run_id'])[:8]}-{template_id}-{build_id[:8]}"
    brief_path = f".local/natal-briefs/{build_id}.json"
    instruction = (
        "Use $natal-landing-builder to generate one previewable Natal landing from the "
        "completed Idea Laval evaluation below. Read and follow the repository skill. "
        f"Use template `{template_id}` and preserve the server-resolved source IDs. "
        f"Write the supplied JSON brief to `{brief_path}`, then run the deterministic "
        f"builder with output `{output_path}`. Verify the generated site at mobile and "
        "desktop widths. Do not deploy, publish, contact users, spend money, modify the "
        "canonical Natal identity/assets, or invent proof, testimonials, pricing, or scarcity.\n\n"
        "Landing brief JSON:\n"
        + json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True)
    )
    if len(instruction) > 20_000:
        raise ValueError("landing builder instruction exceeds the Commander limit")
    return {
        "build_id": build_id,
        "idea_run_id": prepared["idea_run_id"],
        "template_id": template_id,
        "recommended_template_id": recommended,
        "output_path": output_path,
        "brief": brief,
        "instruction": instruction,
    }
