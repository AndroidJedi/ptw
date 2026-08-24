"""Owner-safe handoff from an approved positioning to fixed Natal templates."""

from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from commander.ids import new_uuid7
from natal.brief import brief_from_positioning
from natal.catalog import landing_templates, template_manifest


def templates_response() -> dict[str, Any]:
    return {"items": list(landing_templates())}


def prepare_draft_set(
    project: Mapping[str, Any],
    revision: Mapping[str, Any],
) -> dict[str, Any]:
    return brief_from_positioning(project, revision)


def prepare_landing_build(
    draft_set: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    template_id = str(snapshot["template_id"])
    template_manifest(template_id)
    if str(snapshot["draft_set_id"]) != str(draft_set["id"]) or snapshot.get("is_current") is not True:
        raise ValueError("publication requires the exact current draft snapshot")
    return {
        "build_id": new_uuid7(),
        "positioning_project_id": str(UUID(str(draft_set["positioning_project_id"]))),
        "positioning_revision_id": str(UUID(str(draft_set["positioning_revision_id"]))),
        "source_draft_snapshot_id": str(UUID(str(snapshot["id"]))),
        "template_id": template_id,
        "brief": dict(draft_set["brief"]),
        "page_content": dict(snapshot["page_content"]),
        "page_content_sha256": str(snapshot["page_content_sha256"]),
    }
