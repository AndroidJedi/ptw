"""Project-scoped Studio creative orchestration and edit checkpoints."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Callable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid5

from commander.ids import new_uuid7

from .metric_hypotheses import (
    METRIC_NUMERAL_PATTERN, metric_basis_schema, generated_metrics, reconcile_metrics,
)
from .agent_context import compact_active_skills
from .image_generation_policy import build_image_context, resolve_instruction
from .local_brief_store import LocalBriefStore, sha256_json, utc_now
from .local_codex import sanitized
from .natal_brand import (
    NATAL_NAME_COLOR, NATAL_SYMBOL_COLOR, normalize_natal_logo_colors,
)
from .phone_hero_styles import (
    normalize_phone_hero_creative_direction,
    phone_hero_direction_options,
)
from .studio import STUDIO_FONT_FAMILIES
from .studio_manual_agent import (
    STUDIO_MANUAL_AGENT_PROMPT_VERSION, STUDIO_MANUAL_AGENT_REASONING_EFFORT,
    apply_manual_agent_edits, manual_agent_editable_values, manual_agent_payload,
    manual_agent_schema, response_reply, screenshot_artifacts,
    studio_manual_agent_provider_error, validate_image_actions,
    validate_manual_agent_semantics,
)
from .studio_phone_metrics import (
    PHONE_ACTION_BUTTON_SHAPES,
    PHONE_ACTION_BUTTON_STYLES,
    PHONE_BACKGROUND_TEXTURES,
    PHONE_COPY_BACKGROUND_TEXTURES,
    PHONE_DEVICE_BOUNDS,
    PHONE_METRIC_CARD_SHAPES,
    PHONE_METRIC_CARD_STYLES,
    PHONE_METRICS_TEMPLATE_ID,
    PHONE_SCREEN_TEXTURES,
    PHONE_TEXTURE_INTENSITY_BOUNDS,
    PHONE_TYPOGRAPHY_BOUNDS,
    PHONE_VISUAL_MODES,
    normalize_phone_metrics_config,
    normalize_phone_metrics_content,
)
from .post_templates import POST_TEMPLATE_REGISTRY


CREATIVE_STATUSES = frozenset({"queued", "composing", "generating_image", "draft", "failed"})
TEMPLATE_IDS = frozenset(POST_TEMPLATE_REGISTRY.ids)
ACTIVE_TEMPLATE_IDS = TEMPLATE_IDS
GLOBAL_SKILL_SCOPE = "global"
PROJECT_SKILL_SCOPE = "project"
STUDIO_COMPOSER_PROMPT_VERSION = "studio-creative-composer-v5"


def post_composition_payload(
    *, creative_id: str, approved_product_brief: Mapping[str, Any],
    template_id: str, configuration: Mapping[str, Any],
    content: Mapping[str, Any], active_creative_skills: Mapping[str, Any],
    creative_direction: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build one compact registry-backed Post composition request."""

    definition = POST_TEMPLATE_REGISTRY.get(template_id)
    return {
        "creative_id": creative_id,
        "approved_product_brief": deepcopy(dict(approved_product_brief)),
        "selected_template_id": template_id,
        "live_template_catalog": definition.agent_catalog(),
        "template_defaults": {
            "configuration": deepcopy(dict(configuration)),
            "content": deepcopy(dict(content)),
        },
        "active_creative_skills": compact_active_skills(
            active_creative_skills, surface="post",
        ),
        **({"creative_direction": deepcopy(dict(creative_direction))}
           if creative_direction is not None else {}),
    }


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{field} must be a UUID") from error


def _compact(value: Any, field: str, minimum: int, maximum: int) -> str:
    result = " ".join(str(value or "").split())
    if not minimum <= len(result) <= maximum:
        raise ValueError(f"{field} must contain {minimum}-{maximum} characters")
    return result


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _skill_document(name: str, title: str, lessons: list[str]) -> str:
    lines = [
        "---", f"name: {name}",
        f"description: Runtime Studio learning snapshot for {title}.", "---", "",
        f"# {title}", "",
    ]
    if lessons:
        lines.extend(f"- {lesson}" for lesson in lessons[-40:])
    else:
        lines.append("No owner-approved Studio lessons yet.")
    return "\n".join(lines).strip() + "\n"


def _append_lesson(document: str, lesson: str) -> str:
    lines = [line[2:] for line in document.splitlines() if line.startswith("- ")]
    lines.append(_compact(lesson, "skill lesson", 8, 800))
    title = "Global Studio skill" if "studio-runtime-global" in document else "Project Studio skill"
    name = "studio-runtime-global" if title.startswith("Global") else "studio-runtime-project"
    return _skill_document(name, title, lines)


def verified_skill_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    """Verify both the immutable digest and the minimal SKILL.md envelope."""

    result = deepcopy(dict(value))
    content = str(result.get("content") or "")
    if hashlib.sha256(content.encode()).hexdigest() != result.get("content_sha256"):
        raise RuntimeError("Studio runtime skill digest mismatch")
    if (
        not content.startswith("---\nname: ")
        or "\ndescription: " not in content
        or "\n---\n\n# " not in content
    ):
        raise RuntimeError("Studio runtime skill is not a SKILL.md document")
    result["content"] = content
    return result


def _json_schema(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        return {
            "type": "array",
            "items": _json_schema(value[0]) if value else {"type": "string"},
            "minItems": len(value), "maxItems": len(value),
        }
    if isinstance(value, Mapping):
        return {
            "type": "object",
            "properties": {str(key): _json_schema(item) for key, item in value.items()},
            "required": [str(key) for key in value],
            "additionalProperties": False,
        }
    raise TypeError("unsupported Studio schema value")


def creative_generation_schema(detail: Mapping[str, Any]) -> dict[str, Any]:
    properties = {
        "configuration": _json_schema(detail["configuration"]),
        "content": _json_schema(detail["content"]),
    }
    if detail.get("template_id") == PHONE_METRICS_TEMPLATE_ID:
        configuration = properties["configuration"]["properties"]
        configuration["schema"]["enum"] = [detail["configuration"]["schema"]]
        if "visual_mode" in configuration:
            configuration["visual_mode"]["enum"] = list(PHONE_VISUAL_MODES)
        background = configuration["background"]["properties"]
        background["color"]["pattern"] = r"^#[0-9A-Fa-f]{6}$"
        background["texture"]["enum"] = list(PHONE_BACKGROUND_TEXTURES)
        background["texture_intensity"].update({
            "minimum": PHONE_TEXTURE_INTENSITY_BOUNDS[0],
            "maximum": PHONE_TEXTURE_INTENSITY_BOUNDS[1],
        })
        configuration["copy_background"]["properties"]["texture"]["enum"] = list(
            PHONE_COPY_BACKGROUND_TEXTURES
        )
        configuration["supporting_text"]["properties"]["highlight_color"]["pattern"] = (
            r"^#[0-9A-Fa-f]{6}$"
        )
        for field in ("symbol_color", "name_color"):
            selected = detail["configuration"]["logo"][field]
            configuration["logo"]["properties"][field].update({
                "pattern": r"^#[0-9A-Fa-f]{6}$", "enum": [selected],
            })
        for role, bounds in PHONE_TYPOGRAPHY_BOUNDS.items():
            appearance = configuration["typography"]["properties"][role]["properties"]
            appearance["font_family"]["enum"] = list(STUDIO_FONT_FAMILIES)
            appearance["font_size"].update({"minimum": bounds[0], "maximum": bounds[1]})
        configuration["phone_screen"]["properties"]["texture"]["enum"] = list(
            PHONE_SCREEN_TEXTURES
        )
        for collection, styles, shapes in (
            ("metric_cards", PHONE_METRIC_CARD_STYLES, PHONE_METRIC_CARD_SHAPES),
            ("phone_buttons", PHONE_ACTION_BUTTON_STYLES, PHONE_ACTION_BUTTON_SHAPES),
        ):
            item = configuration[collection]["items"]["properties"]
            item["style"]["enum"] = list(styles)
            item["shape"]["enum"] = list(shapes)
            item["text_color"]["pattern"] = r"^#[0-9A-Fa-f]{6}$"
            item["background_color"]["pattern"] = r"^#[0-9A-Fa-f]{6}$"
        for field, bounds in PHONE_DEVICE_BOUNDS.items():
            configuration["device"]["properties"][field].update({
                "minimum": bounds[0], "maximum": bounds[1],
            })
        content = properties["content"]["properties"]
        content["schema"]["enum"] = [detail["content"]["schema"]]
        for field, minimum, maximum in (
            ("offer", 1, 32), ("hero_title", 1, 140),
            ("supporting_text", 1, 220), ("cta", 0, 60),
            ("phone_hero_title", 0, 72),
        ):
            content[field].update({"minLength": minimum, "maxLength": maximum})
        content["stats"]["items"]["properties"]["value"].update({
            "minLength": 1, "maxLength": 24,
        })
        content["stats"]["items"]["properties"]["label"].update({
            "minLength": 1, "maxLength": 38,
        })
        content["phone_buttons"]["items"].update({"minLength": 1, "maxLength": 48})
        properties["visual_direction"] = {"type": "string", "minLength": 8, "maxLength": 600}
        properties["metric_basis"] = metric_basis_schema()
        content["stats"]["items"]["properties"]["value"]["pattern"] = METRIC_NUMERAL_PATTERN
    return {
        "type": "object", "properties": properties,
        "required": list(properties), "additionalProperties": False,
    }


def _clear_generation_failure(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        key: deepcopy(item) for key, item in dict(value or {}).items()
        if key not in {"error_type", "error_message"}
    }


def _diff_paths(before: Any, after: Any, prefix: str = "") -> list[str]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        paths: list[str] = []
        for key in sorted(set(before) | set(after)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in before or key not in after:
                paths.append(path)
            else:
                paths.extend(_diff_paths(before[key], after[key], path))
        return paths
    if isinstance(before, list) and isinstance(after, list):
        paths = []
        for index in range(max(len(before), len(after))):
            path = f"{prefix}[{index}]"
            if index >= len(before) or index >= len(after):
                paths.append(path)
            else:
                paths.extend(_diff_paths(before[index], after[index], path))
        return paths
    return [] if before == after else [prefix]


def _state_snapshot(detail: Mapping[str, Any]) -> dict[str, Any]:
    assets = [{
        "slot": item.get("slot"), "available": item.get("available"),
        "sha256": item.get("sha256"), "source": item.get("source"),
    } for item in detail.get("assets", [])]
    phone_history = [{
        "sha256": item.get("sha256"), "selected": item.get("selected"),
        "source": item.get("source"),
    } for item in detail.get("phone_screen_history", [])]
    return {
        "template_id": detail.get("template_id") or detail.get("catalog", {}).get("template_id"),
        **({"template_reference": deepcopy(detail["template_reference"])} if detail.get("editor_key") == "post.declarative.react" else {}),
        "template_sha256": detail.get("template_sha256"),
        "configuration": deepcopy(detail.get("configuration")),
        "content": deepcopy(detail.get("content")),
        "assets": assets,
        "phone_screen_history": phone_history,
    }


def _default_logo_colors() -> dict[str, str]:
    return {
        "symbol_color": NATAL_SYMBOL_COLOR,
        "name_color": NATAL_NAME_COLOR,
    }


def _normalized_checkpoint_baseline(
    before: Mapping[str, Any], after: Mapping[str, Any],
) -> dict[str, Any]:
    """Remove renderer/config uplift noise from an owner edit comparison."""

    normalized = deepcopy(dict(before))
    if normalized.get("template_id") != after.get("template_id") or normalized.get("template_reference") != after.get("template_reference"):
        return normalized
    configuration = normalized.get("configuration")
    if isinstance(configuration, Mapping):
        if normalized.get("template_id") == PHONE_METRICS_TEMPLATE_ID:
            normalized["configuration"] = normalize_phone_metrics_config(configuration)
    # A renderer release is provenance, not an owner edit. A real template
    # replacement is retained above because its template_id changes.
    normalized["template_sha256"] = after.get("template_sha256")
    return normalized


class LocalStudioAuthority:
    """Append-only metadata authority paired with per-creative workspace files."""

    def __init__(self, store: LocalBriefStore) -> None:
        self.store = store
        self._lock = threading.RLock()

    def project(self, project_id: str) -> dict[str, Any]:
        return self.store.get("projects", _uuid(project_id, "project_id"))

    def brief(self, brief_id: str) -> dict[str, Any]:
        return self.store.get("briefs", _uuid(brief_id, "brief_id"))

    def ensure_project_skill(self, project_id: str) -> dict[str, Any]:
        project_id = _uuid(project_id, "project_id")
        self.project(project_id)
        existing = [item for item in self.store.list("studio_skill_snapshots") if (
            item["scope"] == PROJECT_SKILL_SCOPE and item.get("project_id") == project_id
        )]
        if existing:
            return verified_skill_snapshot(existing[0])
        return self._append_skill(
            scope=PROJECT_SKILL_SCOPE, project_id=project_id,
            content=_skill_document("studio-runtime-project", "Project Studio skill", []),
            source_checkpoint_id=None,
        )

    def ensure_global_skill(self) -> dict[str, Any]:
        existing = [item for item in self.store.list("studio_skill_snapshots") if (
            item["scope"] == GLOBAL_SKILL_SCOPE
        )]
        if existing:
            return verified_skill_snapshot(existing[0])
        return self._append_skill(
            scope=GLOBAL_SKILL_SCOPE, project_id=None,
            content=_skill_document("studio-runtime-global", "Global Studio skill", []),
            source_checkpoint_id=None,
        )

    def _append_skill(
        self, *, scope: str, project_id: str | None, content: str,
        source_checkpoint_id: str | None,
    ) -> dict[str, Any]:
        previous = [item for item in self.store.list("studio_skill_snapshots") if (
            item["scope"] == scope and item.get("project_id") == project_id
        )]
        if source_checkpoint_id:
            for item in previous:
                if item.get("source_checkpoint_id") == source_checkpoint_id:
                    return verified_skill_snapshot(item)
        value = {
            "skill_snapshot_id": new_uuid7(), "scope": scope, "project_id": project_id,
            "version": (int(previous[0]["version"]) + 1) if previous else 1,
            "content": content, "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "source_checkpoint_id": source_checkpoint_id, "created_at": utc_now(),
        }
        self.store.append("studio_skill_snapshots", value["skill_snapshot_id"], value)
        if project_id:
            self.store.edge(
                source_id=project_id, relation="contains",
                target_id=value["skill_snapshot_id"], evidence={"member": "studio_skill_snapshot"},
            )
        if source_checkpoint_id:
            self.store.edge(
                source_id=value["skill_snapshot_id"], relation="derived_from",
                target_id=source_checkpoint_id, evidence={"input": "studio_edit_checkpoint"},
            )
        if previous:
            self.store.edge(
                source_id=value["skill_snapshot_id"], relation="supersedes",
                target_id=previous[0]["skill_snapshot_id"], evidence={"scope": scope},
            )
        return verified_skill_snapshot(value)

    def latest_skill(self, scope: str, project_id: str | None = None) -> dict[str, Any]:
        if scope == GLOBAL_SKILL_SCOPE:
            return self.ensure_global_skill()
        if scope == PROJECT_SKILL_SCOPE and project_id:
            return self.ensure_project_skill(project_id)
        raise ValueError("Studio skill scope is invalid")

    def latest_project_logo_default(self, project_id: str) -> dict[str, Any] | None:
        project_id = _uuid(project_id, "project_id")
        self.project(project_id)
        records = [
            item for item in self.store.list("studio_project_logo_defaults")
            if item["project_id"] == project_id
        ]
        if not records:
            return None
        latest = max(records, key=lambda item: (str(item["created_at"]), str(item["logo_default_id"])))
        colors = normalize_natal_logo_colors({
            "symbol_color": latest["symbol_color"],
            "name_color": latest["name_color"],
        })
        return {**deepcopy(latest), **colors}

    def create_creative(
        self, *, project_id: str, brief_id: str, template_id: str,
        requested_by: str, origin: str, creative_direction: Mapping[str, Any] | None = None,
        require_approved_previous: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        with self._lock:
            return self._create_creative(
                project_id=project_id, brief_id=brief_id, template_id=template_id,
                requested_by=requested_by, origin=origin, creative_direction=creative_direction,
                require_approved_previous=require_approved_previous,
            )

    def _create_creative(
        self, *, project_id: str, brief_id: str, template_id: str,
        requested_by: str, origin: str, creative_direction: Mapping[str, Any] | None = None,
        require_approved_previous: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        project_id = _uuid(project_id, "project_id")
        project = self.project(project_id)
        if template_id not in TEMPLATE_IDS:
            raise ValueError("Studio template is invalid")
        if template_id == PHONE_METRICS_TEMPLATE_ID:
            if creative_direction is None:
                raise ValueError("Phone Metrics creative direction is required")
            creative_direction = normalize_phone_hero_creative_direction(creative_direction)
        elif creative_direction is not None:
            raise ValueError("creative direction is available only for Phone Metrics")
        if origin not in {"brief_generation", "approved_variant"}:
            raise ValueError("Studio creative requires approved Product Brief lineage")
        brief_id = _uuid(brief_id, "brief_id")
        brief = self.brief(brief_id)
        if brief["project_id"] != project_id:
            raise ValueError("Product Brief belongs to another Project")
        if not brief.get("approved"):
            raise ValueError("Studio creative requires an approved Product Brief")
        siblings = [item for item in self.store.list("studio_creatives") if item["source_brief_id"] == brief_id]
        if siblings and not require_approved_previous:
            first = sorted(siblings, key=lambda item: int(item["ordinal"]))[0]
            if first["template_id"] != template_id:
                raise ValueError("Product Brief already reserved a different Studio template")
            if template_id == PHONE_METRICS_TEMPLATE_ID and (
                dict((first.get("generation") or {}).get("creative_direction") or {})
                != creative_direction
            ):
                raise ValueError("Product Brief already reserved a different Phone Metrics creative direction")
            return first, False
        if require_approved_previous and not siblings:
            raise ValueError("create the first creative through Brief approval")
        if require_approved_previous:
            latest = max(siblings, key=lambda item: int(item["ordinal"]))
            if int(latest.get("approved_version_count", 0)) < 1:
                raise ValueError("approve the current creative before creating another from this Brief")
        creative_id = new_uuid7()
        now = utc_now()
        value = {
            "creative_id": creative_id, "project_id": project_id,
            "project_name": project["name"], "source_brief_id": brief_id,
            "ordinal": len(siblings) + 1, "template_id": template_id,
            "template_version": None, "template_sha256": None,
            "status": "queued",
            "origin": origin, "state_sha256": None,
            "generation": ({} if creative_direction is None else {
                "creative_direction": dict(creative_direction),
            }),
            "learning_baseline": None, "learning_baseline_sha256": None,
            "approved_version_count": 0, "latest_checkpoint_id": None,
            "requested_by": requested_by, "created_at": now, "updated_at": now,
        }
        self.store.append("studio_creatives", creative_id, value)
        self.store.edge(
            source_id=project_id, relation="contains", target_id=creative_id,
            evidence={"member": "studio_creative", "ordinal": value["ordinal"]},
        )
        self.store.edge(
            source_id=creative_id, relation="derived_from", target_id=brief_id,
            evidence={"input": "approved_product_brief"},
        )
        return value, True

    def create_clone_creative(
        self, *, project_id: str, source_creative_id: str, source_version_id: str,
        source_version: int, request_id: str, requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        """Reserve one idempotent same-Project draft derived from an approved version."""

        with self._lock:
            project_id = _uuid(project_id, "project_id")
            source_creative_id = _uuid(source_creative_id, "source_creative_id")
            source_version_id = _uuid(source_version_id, "source_version_id")
            request_id = _uuid(request_id, "request_id")
            existing = next((
                item for item in self.store.list("studio_creatives")
                if (item.get("generation") or {}).get("clone_request_id") == request_id
            ), None)
            if existing:
                lineage = existing.get("generation") or {}
                if (
                    existing["project_id"] != project_id
                    or lineage.get("clone_source_version_id") != source_version_id
                ):
                    raise ValueError("idempotency request ID was reused with different clone input")
                return existing, False
            source = self.get_creative(source_creative_id)
            if source["project_id"] != project_id:
                raise ValueError("Clone source belongs to another Project")
            siblings = [
                item for item in self.store.list("studio_creatives")
                if item["source_brief_id"] == source["source_brief_id"]
            ]
            creative_id = new_uuid7()
            now = utc_now()
            generation = {
                "clone_request_id": request_id,
                "clone_source_creative_id": source_creative_id,
                "clone_source_version_id": source_version_id,
                "clone_source_version": source_version,
                **({"creative_direction": deepcopy(source.get("generation", {}).get("creative_direction"))}
                   if source.get("generation", {}).get("creative_direction") else {}),
            }
            value = {
                "creative_id": creative_id, "project_id": project_id,
                "project_name": self.project(project_id)["name"],
                "source_brief_id": source["source_brief_id"],
                "ordinal": len(siblings) + 1, "template_id": source["template_id"],
                "template_version": None, "template_sha256": None,
                "status": "queued", "origin": "approved_clone", "state_sha256": None,
                "generation": generation, "learning_baseline": None,
                "learning_baseline_sha256": None, "approved_version_count": 0,
                "latest_checkpoint_id": None, "requested_by": requested_by,
                "created_at": now, "updated_at": now,
            }
            self.store.append("studio_creatives", creative_id, value)
            self.store.edge(source_id=project_id, relation="contains", target_id=creative_id,
                            evidence={"member": "studio_creative", "ordinal": value["ordinal"]})
            self.store.edge(source_id=creative_id, relation="derived_from", target_id=source["source_brief_id"],
                            evidence={"input": "approved_product_brief"})
            self.store.edge(source_id=creative_id, relation="derived_from", target_id=source_version_id,
                            evidence={"input": "approved_post_clone"})
            return value, True

    def get_creative(self, creative_id: str) -> dict[str, Any]:
        return self.store.get("studio_creatives", _uuid(creative_id, "creative_id"))

    def list_creatives(self, project_id: str) -> list[dict[str, Any]]:
        project_id = _uuid(project_id, "project_id")
        self.project(project_id)
        return [
            item for item in self.store.list("studio_creatives")
            if item["project_id"] == project_id
        ]

    def update_creative(self, creative_id: str, **patch: Any) -> dict[str, Any]:
        value = self.get_creative(creative_id)
        updated = {**value, **deepcopy(patch), "updated_at": utc_now()}
        if updated["status"] not in CREATIVE_STATUSES:
            raise ValueError("Studio creative status is invalid")
        self.store.append("studio_creatives", creative_id, updated)
        return updated

    def record_generation(
        self, *, creative_id: str, stage: str, status: str,
        provenance: Mapping[str, Any] | None = None, error: Exception | None = None,
    ) -> dict[str, Any]:
        existing = [item for item in self.store.list("studio_generation_runs") if item["creative_id"] == creative_id]
        run_id = new_uuid7()
        value = {
            "generation_run_id": run_id, "creative_id": creative_id,
            "attempt": len(existing) + 1, "stage": stage, "status": status,
            "provenance": sanitized(provenance or {}),
            "error_type": None if error is None else type(error).__name__,
            "error_message": None if error is None else str(error)[:1000],
            "created_at": utc_now(),
        }
        self.store.append("studio_generation_runs", run_id, value)
        self.store.edge(
            source_id=creative_id, relation="contains", target_id=run_id,
            evidence={"member": "studio_generation_run", "stage": stage},
        )
        return value

    def record_checkpoint(self, value: Mapping[str, Any]) -> dict[str, Any]:
        record = deepcopy(dict(value))
        existing = [item for item in self.store.list("studio_edit_checkpoints") if (
            item["creative_id"] == record["creative_id"]
            and item["before_state_sha256"] == record["before_state_sha256"]
            and item["after_state_sha256"] == record["after_state_sha256"]
            and item["kind"] == record["kind"]
        )]
        if existing:
            return self.get_checkpoint(str(existing[0]["checkpoint_id"]))
        immutable = {
            key: record[key] for key in (
                "checkpoint_id", "creative_id", "project_id", "kind",
                "before_state_sha256", "after_state_sha256", "changed_paths",
                "before_snapshot", "after_snapshot", "version", "created_at",
            )
        }
        self.store.append(
            "studio_edit_checkpoints", str(immutable["checkpoint_id"]), immutable,
        )
        self.store.edge(
            source_id=str(immutable["creative_id"]), relation="contains",
            target_id=str(immutable["checkpoint_id"]), evidence={"member": "studio_edit_checkpoint"},
        )
        return self.get_checkpoint(str(immutable["checkpoint_id"]))

    def record_checkpoint_with_project_logo_default(
        self, value: Mapping[str, Any], logo_colors: Mapping[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        """Mirror one checkpoint-linked Project brand default in local authority."""

        with self._lock:
            checkpoint = self.record_checkpoint(value)
            checkpoint_id = str(checkpoint["checkpoint_id"])
            existing = next((
                item for item in self.store.list("studio_project_logo_defaults")
                if item["source_checkpoint_id"] == checkpoint_id
            ), None)
            if existing is not None:
                return checkpoint, False
            colors = normalize_natal_logo_colors(dict(logo_colors))
            identifier = new_uuid7()
            record = {
                "logo_default_id": identifier,
                "project_id": _uuid(str(value["project_id"]), "project_id"),
                "source_checkpoint_id": checkpoint_id,
                **colors,
                "created_at": utc_now(),
            }
            self.store.append("studio_project_logo_defaults", identifier, record)
            self.store.edge(
                source_id=record["project_id"], relation="contains",
                target_id=identifier, evidence={"member": "studio_project_logo_default"},
            )
            self.store.edge(
                source_id=identifier, relation="derived_from",
                target_id=checkpoint_id, evidence={"input": "studio_edit_checkpoint"},
            )
            return checkpoint, True

    def record_learning_result(
        self, checkpoint_id: str, *, status: str, edit_summary: str | None,
        project_lesson: str | None, project_skill_snapshot_id: str | None,
        provider: Mapping[str, Any] | None, error: Exception | None,
    ) -> dict[str, Any]:
        if status not in {"completed", "failed"}:
            raise ValueError("Studio learning result status is invalid")
        checkpoint = self.store.get(
            "studio_edit_checkpoints", _uuid(checkpoint_id, "checkpoint_id"),
        )
        previous = [item for item in self.store.list("studio_learning_runs") if (
            item["checkpoint_id"] == checkpoint_id
        )]
        completed = [item for item in previous if item.get("status") == "completed"]
        if completed:
            return max(completed, key=lambda item: int(item["attempt"]))
        value = {
            "learning_run_id": new_uuid7(), "checkpoint_id": checkpoint_id,
            "attempt": len(previous) + 1, "status": status,
            "edit_summary": edit_summary, "project_lesson": project_lesson,
            "project_skill_snapshot_id": project_skill_snapshot_id,
            "provider": sanitized(provider or {}),
            "error_type": None if error is None else type(error).__name__,
            "error_message": None if error is None else str(error)[:1000],
            "created_at": utc_now(),
        }
        self.store.append("studio_learning_runs", value["learning_run_id"], value)
        self.store.edge(
            source_id=checkpoint["checkpoint_id"], relation="contains",
            target_id=value["learning_run_id"], evidence={"member": "studio_learning_run"},
        )
        return value

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        checkpoint = self.store.get(
            "studio_edit_checkpoints", _uuid(checkpoint_id, "checkpoint_id"),
        )
        return {**checkpoint, "status": "saved"}

    def queued_checkpoints(self) -> list[dict[str, Any]]:
        return []

    def create_project_skill(
        self, *, project_id: str, lesson: str, checkpoint_id: str,
    ) -> dict[str, Any]:
        existing = [item for item in self.store.list("studio_skill_snapshots") if (
            item.get("scope") == PROJECT_SKILL_SCOPE
            and item.get("project_id") == project_id
            and item.get("source_checkpoint_id") == checkpoint_id
        )]
        if existing:
            return verified_skill_snapshot(existing[0])
        previous = self.latest_skill(PROJECT_SKILL_SCOPE, project_id)
        return self._append_skill(
            scope=PROJECT_SKILL_SCOPE, project_id=project_id,
            content=_append_lesson(previous["content"], lesson),
            source_checkpoint_id=checkpoint_id,
        )

    def create_proposal(
        self, *, checkpoint_id: str, project_skill_snapshot_id: str,
        global_rule: str,
    ) -> dict[str, Any]:
        existing = [item for item in self.store.list("studio_learning_proposals") if (
            item.get("checkpoint_id") == checkpoint_id
        )]
        if existing:
            return existing[0]
        proposal_id = new_uuid7()
        value = {
            "proposal_id": proposal_id, "checkpoint_id": checkpoint_id,
            "project_skill_snapshot_id": project_skill_snapshot_id,
            "global_rule": global_rule,
            "global_rule_sha256": hashlib.sha256(global_rule.encode()).hexdigest(),
            "decision": "pending", "created_at": utc_now(),
        }
        self.store.append("studio_learning_proposals", proposal_id, value)
        self.store.edge(
            source_id=checkpoint_id, relation="contains", target_id=proposal_id,
            evidence={"member": "studio_learning_proposal"},
        )
        return value

    def decide_proposal(self, proposal_id: str, decision: str) -> dict[str, Any]:
        proposal = self.store.get("studio_learning_proposals", _uuid(proposal_id, "proposal_id"))
        if decision not in {"global", "project_only"}:
            raise ValueError("learning decision must be global or project_only")
        existing = [item for item in self.store.list("studio_learning_decisions") if item["proposal_id"] == proposal_id]
        if existing:
            if existing[0]["decision"] != decision:
                raise RuntimeError("learning proposal already has a different decision")
            return {**proposal, **existing[0]}
        global_snapshot = None
        if decision == "global":
            previous = self.latest_skill(GLOBAL_SKILL_SCOPE)
            global_snapshot = self._append_skill(
                scope=GLOBAL_SKILL_SCOPE, project_id=None,
                content=_append_lesson(previous["content"], proposal["global_rule"]),
                source_checkpoint_id=proposal["checkpoint_id"],
            )
        record = {
            "decision_id": new_uuid7(), "proposal_id": proposal_id,
            "decision": decision,
            "global_skill_snapshot_id": None if global_snapshot is None else global_snapshot["skill_snapshot_id"],
            "created_at": utc_now(),
        }
        self.store.append("studio_learning_decisions", record["decision_id"], record)
        self.store.edge(
            source_id=proposal_id, relation="contains", target_id=record["decision_id"],
            evidence={"member": "studio_learning_decision"},
        )
        if global_snapshot is not None:
            self.store.edge(
                source_id=global_snapshot["skill_snapshot_id"], relation="derived_from",
                target_id=proposal_id, evidence={"input": "accepted_global_proposal"},
            )
        return {**proposal, **record}

    def proposal_checkpoint(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.store.get(
            "studio_learning_proposals", _uuid(proposal_id, "proposal_id"),
        )
        checkpoint = self.store.get(
            "studio_edit_checkpoints", str(proposal["checkpoint_id"]),
        )
        return {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "creative_id": checkpoint["creative_id"],
            "project_id": checkpoint["project_id"],
        }


class StudioCreativeService:
    """Coordinate template workspaces, generation, and edit checkpoints."""

    def __init__(
        self, *, root: Path | str, authority: Any,
        workspace_factory: Callable[[Path], Any], structured_provider: Any | None,
        composer_skill_path: Path, phone_skill_path: Path,
        manual_agent_skill_path: Path | None = None,
    ) -> None:
        self.root = Path(root)
        self.creatives_root = self.root / "creatives"
        self.creatives_root.mkdir(parents=True, exist_ok=True)
        self.authority = authority
        self.workspace_factory = workspace_factory
        self.structured_provider = structured_provider
        self.composer_skill = composer_skill_path.read_text(encoding="utf-8")
        self.phone_skill = phone_skill_path.read_text(encoding="utf-8")
        self.manual_agent_skill = (
            manual_agent_skill_path.read_text(encoding="utf-8")
            if manual_agent_skill_path is not None else
            "Adjust only the supplied bounded Studio editor state. Never edit code, save, approve, or publish."
        )
        self.analytics: Any | None = None
        self.template_registry = lambda: POST_TEMPLATE_REGISTRY
        self._workspaces: dict[str, Any] = {}
        self._lock = threading.RLock()

    def templates(self) -> dict[str, Any]:
        templates = [{
            **definition.summary(),
            **({"creative_direction_options": phone_hero_direction_options()}
               if definition.identity.template_id == PHONE_METRICS_TEMPLATE_ID else {}),
        } for definition in POST_TEMPLATE_REGISTRY.all()]
        return {"schema": "ptw.studio.template-catalog.v1", "items": templates}

    def _workspace(self, creative_id: str) -> Any:
        creative_id = _uuid(creative_id, "creative_id")
        self.authority.get_creative(creative_id)
        if creative_id not in self._workspaces:
            self._workspaces[creative_id] = self.workspace_factory(self.creatives_root / creative_id)
            workspace = self._workspaces[creative_id]
            getattr(workspace, "workspace", workspace).template_registry = self.template_registry
        return self._workspaces[creative_id]

    @staticmethod
    def _template_id(detail: Mapping[str, Any]) -> str:
        return str(detail.get("template_id") or detail["catalog"]["template_id"])

    def _project_logo_colors(self, project_id: str) -> dict[str, str]:
        getter = getattr(self.authority, "latest_project_logo_default", None)
        record = getter(project_id) if callable(getter) else None
        if record is None:
            return _default_logo_colors()
        return normalize_natal_logo_colors({
            "symbol_color": record["symbol_color"],
            "name_color": record["name_color"],
        })

    @staticmethod
    def _apply_logo_colors_to_draft(
        workspace: Any, detail: Mapping[str, Any], colors: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized = normalize_natal_logo_colors(dict(colors))
        if all(detail["configuration"]["logo"].get(key) == value for key, value in normalized.items()):
            return dict(detail)
        configuration = deepcopy(detail["configuration"])
        configuration["logo"].update(normalized)
        return workspace.save_configuration(
            base_sha256=str(detail["state_sha256"]),
            configuration=configuration, content=detail["content"],
        )

    def _initialize_workspace(self, creative: Mapping[str, Any], template_reference=None) -> dict[str, Any]:
        workspace = self._workspace(str(creative["creative_id"]))
        detail = workspace.detail()
        colors = self._project_logo_colors(str(creative["project_id"]))
        target_id = template_reference["template_id"] if template_reference else creative["template_id"]
        if self._template_id(detail) != target_id or (template_reference and detail.get("template_reference") != template_reference):
            detail = workspace.apply_template(
                base_sha256=detail["state_sha256"], template_id=str(target_id),
                logo_colors=colors,
                **({"template_reference": template_reference} if template_reference else {}),
            )
        else:
            detail = self._apply_logo_colors_to_draft(workspace, detail, colors)
        snapshot = _state_snapshot(detail)
        self.authority.update_creative(
            str(creative["creative_id"]), template_version=detail["catalog"]["template_version"],
            template_sha256=detail["template_sha256"], state_sha256=detail["state_sha256"],
            learning_baseline=snapshot, learning_baseline_sha256=sha256_json(snapshot),
        )
        return detail

    def reserve_from_brief(
        self, *, brief_id: str, template_id: str, requested_by: str,
        additional: bool = False, creative_direction: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        brief = self.authority.brief(_uuid(brief_id, "brief_id"))
        POST_TEMPLATE_REGISTRY.get(template_id)
        creative, created = self.authority.create_creative(
            project_id=brief["project_id"], brief_id=brief_id,
            template_id=template_id, requested_by=requested_by,
            origin="approved_variant" if additional else "brief_generation",
            creative_direction=creative_direction,
            require_approved_previous=additional,
        )
        if created:
            self._initialize_workspace(creative)
        return self.summary(str(creative["creative_id"])), created

    def clone_approved_version(
        self, *, project_id: str, source_creative_id: str, source_version: int,
        request_id: str, requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        """Create one editable same-template draft from an immutable approved Post."""

        project_id = _uuid(project_id, "project_id")
        source_creative_id = _uuid(source_creative_id, "source_creative_id")
        request_id = _uuid(request_id, "request_id")
        if isinstance(source_version, bool) or not isinstance(source_version, int) or source_version < 1:
            raise ValueError("source_version must be a positive integer")
        self.detail(project_id, source_creative_id)
        source_workspace = self._workspace(source_creative_id)
        version_record = source_workspace.version_detail(source_version)
        frozen_assets = source_workspace.version_clone_assets(source_version)
        source_version_id = str(version_record.get("version_id") or uuid5(
            NAMESPACE_URL,
            f"ptw-studio-version:{source_creative_id}:{source_version}:{version_record['version_sha256']}",
        ))
        if hasattr(self.authority, "store") and not self.authority.store.history("studio_versions", source_version_id):
            self.authority.store.append("studio_versions", source_version_id, {
                "version_id": source_version_id, "creative_id": source_creative_id,
                "version": source_version, "version_sha256": version_record["version_sha256"],
            })
        creative, created = self.authority.create_clone_creative(
            project_id=project_id, source_creative_id=source_creative_id,
            source_version_id=source_version_id, source_version=source_version,
            request_id=request_id, requested_by=requested_by,
        )
        if not created and creative.get("status") != "queued":
            return self.summary(str(creative["creative_id"])), False
        if version_record.get("metric_provenance") is not None:
            creative = self.authority.update_creative(str(creative["creative_id"]), generation={
                **dict(creative.get("generation") or {}),
                "metric_provenance": deepcopy(version_record["metric_provenance"]),
            })

        destination = self._workspace(str(creative["creative_id"]))
        version_reference = version_record.get("template_reference") or POST_TEMPLATE_REGISTRY.get(version_record["template_id"]).identity.to_reference()
        destination_detail = self._initialize_workspace(creative, version_reference)
        clone_assets = [{
            "slot": selected["slot"], "mime_type": selected["mime_type"],
            "bytes_base64": base64.b64encode(bytes(selected["bytes"])).decode(),
            "source": {
                **deepcopy(selected["source"]),
                "cloned_from_version_id": source_version_id,
            },
        } for selected in frozen_assets]
        destination_detail = destination.restore_approved_clone(
            base_sha256=destination_detail["state_sha256"],
            configuration=version_record["configuration"], content=version_record["content"],
            assets=clone_assets,
        )
        snapshot = _state_snapshot(destination_detail)
        generation = {
            **dict(creative.get("generation") or {}),
            "stage": "cloned", "status": "completed",
            "clone_source_version_sha256": version_record["version_sha256"],
            "clone_source_render_sha256": version_record["render_sha256"],
        }
        self.authority.update_creative(
            str(creative["creative_id"]), status="draft",
            template_id=destination_detail["template_id"],
            template_version=destination_detail["catalog"]["template_version"],
            template_sha256=destination_detail["template_sha256"],
            state_sha256=destination_detail["state_sha256"], generation=generation,
            learning_baseline=snapshot, learning_baseline_sha256=sha256_json(snapshot),
        )
        return self.summary(str(creative["creative_id"])), created

    def approve_brief_and_reserve(
        self, *, brief_id: str, template_id: str, requested_by: str,
        brief_approver: Callable[[str, str], tuple[dict[str, Any], bool]],
        creative_direction: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool, dict[str, Any], bool]:
        """Approve and reserve idempotently; PostgreSQL performs both in one transaction."""

        POST_TEMPLATE_REGISTRY.get(template_id)
        if template_id == PHONE_METRICS_TEMPLATE_ID:
            if creative_direction is None:
                raise ValueError("Phone Metrics creative direction is required")
            creative_direction = normalize_phone_hero_creative_direction(creative_direction)
        elif creative_direction is not None:
            raise ValueError("creative direction is available only for Phone Metrics")
        if hasattr(self.authority, "approve_and_create_creative"):
            creative, approved_now, creative_created = (
                self.authority.approve_and_create_creative(
                    brief_id=_uuid(brief_id, "brief_id"), template_id=template_id,
                    requested_by=requested_by, creative_direction=creative_direction,
                )
            )
            brief = self.authority.brief(brief_id)
            if creative_created:
                self._initialize_workspace(creative)
            return brief, approved_now, self.summary(str(creative["creative_id"])), creative_created
        with self._lock:
            brief, approved_now = brief_approver(_uuid(brief_id, "brief_id"), requested_by)
            creative, creative_created = self.reserve_from_brief(
                brief_id=brief_id, template_id=template_id, requested_by=requested_by,
                creative_direction=creative_direction,
            )
        return brief, approved_now, creative, creative_created

    @staticmethod
    def _creative_direction(creative: Mapping[str, Any]) -> dict[str, str] | None:
        value = dict(creative.get("generation") or {}).get("creative_direction")
        if value is None:
            return None
        return normalize_phone_hero_creative_direction(value)

    def set_creative_direction(
        self, project_id: str, creative_id: str, *, base_sha256: str,
        creative_direction: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Save or replace the direction used by later Phone Metrics generations."""

        detail = self.detail(project_id, creative_id)
        if "phone_screen" not in self._workspace(creative_id)._asset_slots():
            raise ValueError("creative direction is available only for Phone Metrics")
        if str(detail["state_sha256"]) != str(base_sha256):
            raise RuntimeError("Studio creative changed; reload before saving")
        direction = normalize_phone_hero_creative_direction(creative_direction)
        creative = self.authority.get_creative(_uuid(creative_id, "creative_id"))
        existing = self._creative_direction(creative)
        if existing is not None:
            if existing == direction:
                return detail
        generation = dict(creative.get("generation") or {})
        self.authority.update_creative(
            str(creative["creative_id"]),
            generation={**generation, "creative_direction": direction},
        )
        return self.detail(project_id, creative_id)

    def list_creatives(self, project_id: str) -> dict[str, Any]:
        return {
            "items": [self.summary(item["creative_id"]) for item in self.authority.list_creatives(project_id)],
            "next_cursor": None,
        }

    def summary(self, creative_id: str) -> dict[str, Any]:
        value = self.authority.get_creative(creative_id)
        return {key: deepcopy(item) for key, item in value.items() if key != "learning_baseline"}

    def detail(self, project_id: str, creative_id: str) -> dict[str, Any]:
        creative = self.authority.get_creative(_uuid(creative_id, "creative_id"))
        if creative["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Studio creative was not found in this Project")
        detail = self._workspace(creative_id).detail()
        # The renderer view may normalize an older persisted configuration.
        # Its hashes describe the fields sent to the editor; stored metadata
        # must not replace them with the pre-normalization snapshot hashes.
        return {**self.summary(creative_id), **detail}

    def manual_agent_edit(
        self, project_id: str, creative_id: str, *, request_id: str,
        base_sha256: str, message: str, history: list[dict[str, str]],
        configuration: Mapping[str, Any], content: Mapping[str, Any],
        screenshots: list[bytes],
    ) -> dict[str, Any]:
        """Plan one editor-only turn without writing workspace or authority state."""

        detail = self.detail(project_id, creative_id)
        if detail["status"] != "draft":
            raise ValueError("Studio Agent requires an editable draft")
        if base_sha256 != detail["state_sha256"]:
            raise RuntimeError("Studio creative changed; reload before using Agent mode")
        template_id = self._template_id(detail)
        if template_id == PHONE_METRICS_TEMPLATE_ID:
            editor_configuration = normalize_phone_metrics_config(configuration)
            agent_configuration = deepcopy(editor_configuration)
            agent_configuration.setdefault("visual_mode", "phone")
            editor_content = normalize_phone_metrics_content(content)
            image_slots = ["phone_screen"] if detail.get("phone_screen_generation_available") else []
        else:  # pragma: no cover - registry validation makes this unreachable
            raise ValueError("Post template is not registered")
        workspace = self._workspace(creative_id)
        workspace.component_settings(
            state_sha256=detail["state_sha256"],
            configuration=editor_configuration, content=editor_content,
        )
        artifacts = screenshot_artifacts(screenshots)
        current_images = [
            str(item["slot"]) for item in detail.get("assets", [])
            if item.get("available") and item.get("slot") in image_slots
        ]
        current_direction = self._creative_direction(self.authority.get_creative(creative_id))
        payload = manual_agent_payload(
            surface=f"post:{template_id}", entity_id=creative_id,
            message=message, history=history,
            configuration=agent_configuration, content=editor_content,
            catalog=detail["catalog"], screenshot_artifact_values=artifacts,
            image_slots=image_slots, current_images=current_images,
            creative_direction=current_direction,
        )
        editable_values = manual_agent_editable_values(
            catalog=detail["catalog"], configuration=agent_configuration,
            content=editor_content, creative_direction=current_direction,
        )

        def validate_response(value: Mapping[str, Any]) -> Mapping[str, Any]:
            if not isinstance(value, Mapping) or set(value) != {
                "edits", "image_actions", "reply",
            }:
                raise ValueError("Studio Agent response fields are invalid")
            edited = apply_manual_agent_edits(
                value["edits"], current_values=editable_values,
                configuration=agent_configuration, content=editor_content,
                creative_direction=current_direction,
            )
            if template_id == PHONE_METRICS_TEMPLATE_ID:
                next_configuration = normalize_phone_metrics_config(edited["configuration"])
                if (
                    "visual_mode" not in editor_configuration
                    and next_configuration.get("visual_mode") == "phone"
                ):
                    next_configuration.pop("visual_mode")
                next_content = normalize_phone_metrics_content(edited["content"])
            workspace.component_settings(
                state_sha256=detail["state_sha256"],
                configuration=next_configuration, content=next_content,
            )
            response: dict[str, Any] = {
                "configuration": next_configuration,
                "content": next_content,
                "reply": response_reply(value["reply"]),
            }
            response["image_actions"] = validate_image_actions(
                value["image_actions"], slots=image_slots,
                screenshot_count=len(screenshots), available_slots=set(current_images),
            )
            if current_direction is not None:
                response["creative_direction"] = normalize_phone_hero_creative_direction(
                    edited["creative_direction"]
                )
            validate_manual_agent_semantics(
                surface=f"post:{template_id}",
                constraints=payload["request_constraints"],
                configuration=next_configuration, content=next_content,
                image_actions=response["image_actions"],
            )
            return response

        try:
            result = self._provider_call(
                mode="studio_manual_edit",
                system_prompt=(
                    self.manual_agent_skill
                    + "\n\nThe output schema accepts scalar patch operations only. Omitted paths remain unchanged. "
                    "Decompose every clause, obey request_constraints as end-state invariants, resolve cross-control dependencies, "
                    "and verify every requested result against current_editable_values."
                ),
                input_payload=payload,
                output_schema=manual_agent_schema(
                    editable_paths=list(editable_values),
                    image_slots=image_slots, screenshot_count=len(screenshots),
                ),
                idempotency_key=f"studio-manual:{creative_id}:{request_id}",
                prompt_version=STUDIO_MANUAL_AGENT_PROMPT_VERSION,
                reasoning_effort=STUDIO_MANUAL_AGENT_REASONING_EFFORT,
                response_validator=validate_response,
                **({"input_artifacts": artifacts} if artifacts else {}),
            )
        except (RuntimeError, TimeoutError) as error:
            raise studio_manual_agent_provider_error(error) from error
        response = dict(result["response"])
        response["changed_paths"] = _diff_paths(
            {
                "configuration": editor_configuration, "content": editor_content,
                **({"creative_direction": current_direction}
                   if current_direction else {}),
            },
            {
                "configuration": response["configuration"], "content": response["content"],
                **({"creative_direction": response["creative_direction"]}
                   if "creative_direction" in response else {}),
            },
        )
        baseline_metrics = detail.get("generation", {}).get("metric_provenance") or [
            {**stat, "origin": "legacy_unknown", "validation_status": "unvalidated", "evidence": ""}
            for stat in editor_content["stats"]
        ]
        response["metric_provenance"] = reconcile_metrics(
            response["content"]["stats"], baseline_metrics, owner_instruction=message,
        )
        response["owner_instruction"] = message
        response["request_id"] = request_id
        response["base_sha256"] = base_sha256
        return response

    def _provider_call(self, **kwargs: Any) -> dict[str, Any]:
        if self.structured_provider is None:
            raise RuntimeError("Studio structured provider is unavailable")
        response_validator = kwargs.pop("response_validator", None)
        reasoning_effort = kwargs.pop("reasoning_effort", None)
        if not callable(response_validator):
            raise ValueError("Studio structured calls require a domain response validator")
        if hasattr(self.structured_provider, "call"):
            if hasattr(self.structured_provider, "supported_reasoning_efforts"):
                kwargs["reasoning_effort"] = reasoning_effort
            return self.structured_provider.call(
                **kwargs, response_validator=response_validator,
            )
        result = self.structured_provider.generate(**kwargs)
        if response_validator is None:
            return result
        return {**result, "response": dict(response_validator(result["response"]))}

    def _image_context(self, creative: Mapping[str, Any], detail: Mapping[str, Any], *,
                       visual_direction: str, enhance_current: bool = False,
                       reference_image: bytes | None = None,
                       instruction: Mapping[str, Any] | None = None,
                       changed_image_settings: list[str] | None = None) -> dict[str, Any]:
        source = next((asset.get("source") or {} for asset in detail.get("assets", [])
                       if asset["slot"] == "phone_screen"), {})
        config = detail["configuration"]
        direction = self._creative_direction(creative) or {}
        settings = {**direction, "palette": config.get("background", {})}
        definition = self._workspace(str(creative["creative_id"]))._definition()
        artwork_slots = [{key: item[key] for key in ("id", "type", "box", "mobile_box", "fit", "rotation", "enabled") if key in item}
                         for item in getattr(definition, "document", {}).get("components", [])
                         if item["type"] in {"image", "cutout_image", "phone"} and item.get("enabled", True)]
        mode = config.get("visual_mode", "phone") if detail["template_id"] == PHONE_METRICS_TEMPLATE_ID else (
            "phone" if artwork_slots and all(item["type"] == "phone" for item in artwork_slots) else "image")
        return build_image_context(
            direction=visual_direction,
            instruction=resolve_instruction(visual_direction, requested=instruction, previous=source),
            brief=self.authority.brief(str(creative["source_brief_id"])), settings=settings,
            destination={"surface": "post", "template_id": detail["template_id"],
                         "template_sha256": detail.get("template_sha256"), "slot": "phone_screen",
                         "mode": mode, "artwork_slots": artwork_slots,
                         "canvas": detail.get("catalog", {}).get("canvas"),
                         "geometry": ({"screen_size": [832, 1792], "hero_box": [0, 0, 832, 1050],
                                       "subject_offset_y": 220, "bottom_fade_y": [750, 1050],
                                       "fit": "cover", "centering": [0.5, 0.44]}
                                      if detail["template_id"] == PHONE_METRICS_TEMPLATE_ID and config.get("visual_mode", "phone") == "phone"
                                      else {"fit": "per_artwork_slot" if artwork_slots else "contain", "source_aspect_ratio": "1:1"}),
                         "visible_controls": {key: config.get(key) for key in ("phone_screen", "phone_buttons", "device")}},
            operation="uploaded_reference" if reference_image is not None else "enhance_current" if enhance_current else "generate_new",
            base_sha256=detail["state_sha256"],
            lessons=compact_active_skills(self._active_skills(str(creative["project_id"])), surface="post"),
            previous=source if enhance_current else None, changed_settings=changed_image_settings,
        )

    def _active_skills(self, project_id: str) -> dict[str, Any]:
        if self.analytics is None:
            return {"project": None, "global": None, "precedence": [
                "catalog_brand_and_brief", "explicit_owner_direction",
                "project_rules", "global_spirit", "template_defaults",
            ]}
        return self.analytics.active_skills(project_id)

    def _finish_draft(
        self, creative_id: str, detail: Mapping[str, Any], generation: Mapping[str, Any],
    ) -> dict[str, Any]:
        baseline = _state_snapshot(detail)
        generation = _clear_generation_failure(generation)
        self.authority.update_creative(
            creative_id, status="draft", state_sha256=detail["state_sha256"],
            template_version=detail["catalog"]["template_version"],
            template_sha256=detail["template_sha256"],
            generation={**dict(generation), "stage": "draft"},
            learning_baseline=baseline, learning_baseline_sha256=sha256_json(baseline),
        )
        return self.summary(creative_id)

    def _generate_phone_image(
        self, creative: Mapping[str, Any], detail: Mapping[str, Any],
        *, visual_direction: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        creative_id = str(creative["creative_id"])
        direction = _compact(visual_direction, "visual_direction", 8, 600)
        generation = dict(creative.get("generation") or {})
        creative_direction = self._creative_direction(creative)
        if creative_direction is None:
            raise ValueError("Select a Phone Metrics visual style before generating an image")
        provenance = {
            "source_brief_id": creative["source_brief_id"],
            "template_id": creative["template_id"],
            "template_version": detail["catalog"]["template_version"],
            "template_sha256": detail["template_sha256"],
            "global_skill_snapshot_id": generation.get("global_skill_snapshot_id"),
            "global_skill_sha256": generation.get("global_skill_sha256"),
            "project_skill_snapshot_id": generation.get("project_skill_snapshot_id"),
            "project_skill_sha256": generation.get("project_skill_sha256"),
            "visual_direction": direction,
            "creative_direction": creative_direction,
        }
        try:
            next_detail = self._workspace(creative_id).generate_phone_screen(
                base_sha256=str(detail["state_sha256"]), visual_direction=direction,
                enhance_current=False, creative_direction=creative_direction,
                image_context=self._image_context(creative, detail, visual_direction=direction,
                                                  instruction={"origin": "generated"}),
            )
            active_asset = next(
                item for item in next_detail["assets"]
                if item["slot"] == "phone_screen" and item["available"]
            )
            phone = {
                "status": "completed", "visual_direction": direction,
                "creative_direction": creative_direction,
                "asset_sha256": active_asset["sha256"],
                "provider": sanitized(active_asset.get("source") or {}),
            }
            self.authority.record_generation(
                creative_id=creative_id, stage="phone_image", status="completed",
                provenance={**provenance, **phone},
            )
            return next_detail, {**generation, "phone_image": phone}
        except Exception as image_error:
            phone = {
                "status": "failed", "visual_direction": direction,
                "creative_direction": creative_direction,
                "error_type": type(image_error).__name__,
                "error_message": str(image_error)[:1000],
            }
            self.authority.record_generation(
                creative_id=creative_id, stage="phone_image", status="failed",
                provenance=provenance, error=image_error,
            )
            return dict(detail), {**generation, "phone_image": phone}

    def generate(self, creative_id: str) -> dict[str, Any]:
        creative = self.authority.get_creative(creative_id)
        if creative["status"] == "draft":
            return self.summary(creative_id)
        if creative["status"] == "generating_image":
            detail = self._workspace(creative_id).detail()
            current_screen = next(
                (item for item in detail.get("assets", []) if item.get("slot") == "phone_screen"),
                None,
            )
            generation = dict(creative.get("generation") or {})
            if current_screen and current_screen.get("available"):
                generation["phone_image"] = {
                    **dict(generation.get("phone_image") or {}),
                    "status": "completed", "recovered_existing_asset": True,
                }
                return self._finish_draft(creative_id, detail, generation)
            direction = str(
                (generation.get("phone_image") or {}).get("visual_direction")
                or generation.get("visual_direction") or ""
            )
            if len(" ".join(direction.split())) < 8:
                raise RuntimeError("interrupted phone image generation has no saved visual direction")
            detail, generation = self._generate_phone_image(
                creative, detail, visual_direction=direction,
            )
            return self._finish_draft(creative_id, detail, generation)
        brief = self.authority.brief(str(creative["source_brief_id"]))
        if not brief.get("approved") or not brief.get("document"):
            raise ValueError("Studio generation requires an approved complete Product Brief")
        workspace = self._workspace(creative_id)
        detail = workspace.detail()
        skills = self._active_skills(str(creative["project_id"]))
        project_skill, global_skill = skills["project"], skills["global"]
        skill_provenance = {
            "project_skill_snapshot_id": None if project_skill is None else project_skill["skill_snapshot_id"],
            "project_skill_sha256": None if project_skill is None else project_skill["rules_sha256"],
            "global_skill_snapshot_id": None if global_skill is None else global_skill["skill_snapshot_id"],
            "global_skill_sha256": None if global_skill is None else global_skill["rules_sha256"],
        }
        existing_generation = _clear_generation_failure(creative.get("generation"))
        self.authority.update_creative(creative_id, status="composing", generation={
            **existing_generation, "stage": "composing", **skill_provenance,
        })
        generation_context = {
            "source_brief_id": creative["source_brief_id"],
            "template_id": creative["template_id"],
            "template_version": detail["catalog"]["template_version"],
            "template_sha256": detail["template_sha256"],
            **skill_provenance,
            **({"creative_direction": self._creative_direction(creative)}
               if creative["template_id"] == PHONE_METRICS_TEMPLATE_ID else {}),
        }
        payload = post_composition_payload(
            creative_id=creative_id,
            approved_product_brief=brief["document"],
            template_id=str(creative["template_id"]),
            configuration=detail["configuration"], content=detail["content"],
            active_creative_skills=skills,
            creative_direction=(
                self._creative_direction(creative)
                if creative["template_id"] == PHONE_METRICS_TEMPLATE_ID else None
            ),
        )
        system_prompt = (
            self.composer_skill + "\n\nThe live catalog in INPUT_JSON is authoritative. "
            "Return a complete bounded configuration and content object."
        )

        def validate_composition(value: Mapping[str, Any]) -> Mapping[str, Any]:
            expected_fields = {"configuration", "content"}
            if creative["template_id"] == PHONE_METRICS_TEMPLATE_ID:
                expected_fields.update({"visual_direction", "metric_basis"})
            if set(value) != expected_fields:
                raise ValueError("Studio composer response fields are invalid")
            configuration, content = value["configuration"], value["content"]
            if not isinstance(configuration, Mapping) or not isinstance(content, Mapping):
                raise ValueError("Studio composer configuration and content must be objects")
            workspace.component_settings(
                state_sha256=detail["state_sha256"],
                configuration=configuration, content=content,
            )
            if "visual_direction" in value:
                _compact(value["visual_direction"], "visual_direction", 8, 600)
                generated_metrics(content["stats"], value["metric_basis"], brief["document"])
            return value

        try:
            result = self._provider_call(
                mode="studio_creative_generation", system_prompt=system_prompt,
                input_payload=payload, output_schema=creative_generation_schema(detail),
                idempotency_key=(
                    f"studio-creative:{creative_id}:{STUDIO_COMPOSER_PROMPT_VERSION}"
                ),
                prompt_version=STUDIO_COMPOSER_PROMPT_VERSION,
                response_validator=validate_composition,
            )
            response = result["response"]
            composed = workspace.save_configuration(
                base_sha256=detail["state_sha256"],
                configuration=response["configuration"], content=response["content"],
            )
            generation = {
                **self.authority.get_creative(creative_id).get("generation", {}),
                "composition": sanitized(result.get("invocation") or {}),
                **({"metric_provenance": generated_metrics(response["content"]["stats"], response["metric_basis"], brief["document"])}
                   if "metric_basis" in response else {}),
            }
            self.authority.record_generation(
                creative_id=creative_id, stage="composition", status="completed",
                provenance={**generation_context, "provider": generation["composition"],
                            "metric_provenance": generation.get("metric_provenance", [])},
            )
            if creative["template_id"] == PHONE_METRICS_TEMPLATE_ID:
                direction = _compact(response["visual_direction"], "visual_direction", 8, 600)
                self.authority.update_creative(
                    creative_id, status="generating_image", state_sha256=composed["state_sha256"],
                    generation={
                        **generation, "stage": "generating_image",
                        "phone_image": {
                            "status": "generating", "visual_direction": direction,
                            "creative_direction": self._creative_direction(creative),
                        },
                    },
                )
                creative = self.authority.get_creative(creative_id)
                composed, generation = self._generate_phone_image(
                    creative, composed, visual_direction=direction,
                )
            return self._finish_draft(creative_id, composed, generation)
        except Exception as error:
            self.authority.record_generation(
                creative_id=creative_id, stage="composition", status="failed",
                provenance=generation_context, error=error,
            )
            self.authority.update_creative(creative_id, status="failed", generation={
                **self.authority.get_creative(creative_id).get("generation", {}),
                "stage": "failed", "error_type": type(error).__name__,
                "error_message": str(error)[:1000],
            })
            return self.summary(creative_id)

    def retry_generation(self, project_id: str, creative_id: str) -> dict[str, Any]:
        creative = self.authority.get_creative(creative_id)
        if creative["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Studio creative was not found in this Project")
        if creative["status"] != "failed":
            raise ValueError("only a failed Studio creative can be retried")
        if (
            creative["template_id"] == PHONE_METRICS_TEMPLATE_ID
            and self._creative_direction(creative) is None
        ):
            raise ValueError("Select a Phone Metrics visual style before retrying")
        self.authority.update_creative(
            creative_id, status="queued",
            generation=_clear_generation_failure(creative.get("generation")),
        )
        return self.summary(creative_id)

    def retry_phone_image(self, project_id: str, creative_id: str) -> dict[str, Any]:
        detail = self.detail(project_id, creative_id)
        if detail["template_id"] != PHONE_METRICS_TEMPLATE_ID:
            raise ValueError("phone image retry requires the phone_metrics template")
        if self._creative_direction(self.authority.get_creative(creative_id)) is None:
            raise ValueError("Select a Phone Metrics visual style before retrying")
        generation = detail.get("generation") or {}
        phone = generation.get("phone_image") or {}
        if phone.get("status") != "failed":
            raise ValueError("phone image generation is not failed")
        direction = str(phone.get("visual_direction") or detail.get("content", {}).get("hero_title") or "")
        if len(" ".join(direction.split())) < 8:
            direction = "Brief-relevant premium editorial object with soft dimensional light"
        workspace = self._workspace(creative_id)
        next_detail, next_generation = self._generate_phone_image(
            self.authority.get_creative(creative_id), workspace.detail(),
            visual_direction=direction[:600],
        )
        return self._finish_draft(creative_id, next_detail, next_generation)

    def queue_phone_image_retry(self, project_id: str, creative_id: str) -> dict[str, Any]:
        detail = self.detail(project_id, creative_id)
        phone = dict((detail.get("generation") or {}).get("phone_image") or {})
        if detail.get("template_id") != PHONE_METRICS_TEMPLATE_ID or phone.get("status") != "failed":
            raise ValueError("phone image generation is not failed")
        if self._creative_direction(self.authority.get_creative(creative_id)) is None:
            raise ValueError("Select a Phone Metrics visual style before retrying")
        self.authority.update_creative(
            creative_id, status="generating_image",
            generation={
                **dict(detail.get("generation") or {}), "stage": "generating_image",
                "phone_image": {**phone, "status": "failed"},
            },
        )
        return self.summary(creative_id)

    def mutate(
        self, project_id: str, creative_id: str, method: str, *args: Any, **kwargs: Any,
    ) -> Any:
        detail = self.detail(project_id, creative_id)
        if method == "switch_template" and detail["status"] in {"queued", "composing", "generating_image"}:
            raise RuntimeError("Wait for Post generation before changing its template")
        workspace = self._workspace(creative_id)
        target = getattr(workspace, method)
        if method == "apply_template":
            POST_TEMPLATE_REGISTRY.get(str(kwargs.get("template_id") or ""))
            kwargs["logo_colors"] = self._project_logo_colors(project_id)
        if method == "generate_phone_screen":
            creative = self.authority.get_creative(creative_id)
            direction = self._creative_direction(creative)
            if direction is None:
                raise ValueError("Select a Phone Metrics visual style before generating an image")
            kwargs["image_context"] = self._image_context(
                creative, detail, visual_direction=kwargs["visual_direction"],
                enhance_current=kwargs.get("enhance_current", False),
                reference_image=kwargs.get("reference_image"),
                instruction=kwargs.pop("instruction_context", None),
                changed_image_settings=kwargs.pop("changed_image_settings", None),
            )
            kwargs["creative_direction"] = direction
        metric_sources = kwargs.pop("metric_provenance", None)
        generation = dict(detail.get("generation") or {})
        if method == "save_configuration" and "stats" in kwargs.get("content", {}):
            if metric_sources is not None or kwargs["content"]["stats"] != detail["content"].get("stats"):
                generation["metric_provenance"] = reconcile_metrics(
                    kwargs["content"]["stats"], generation.get("metric_provenance"), supplied=metric_sources)
        try:
            value = target(*args, **kwargs)
        except Exception as error:
            if method == "generate_phone_screen":
                self.authority.record_generation(creative_id=creative_id, stage="phone_image", status="failed",
                    provenance={"image_context": kwargs["image_context"]}, error=error)
            raise
        if method == "generate_phone_screen":
            generated = next(asset for asset in value["assets"] if asset["slot"] == "phone_screen")
            self.authority.record_generation(creative_id=creative_id, stage="phone_image", status="completed",
                provenance={"asset_sha256": generated["sha256"], "provider": generated.get("source", {})})
        if isinstance(value, dict) and value.get("state_sha256"):
            self.authority.update_creative(
                creative_id, state_sha256=value["state_sha256"], generation=generation,
                template_id=self._template_id(value),
                template_version=value["catalog"]["template_version"],
                template_sha256=value["template_sha256"],
            )
            return {**self.summary(creative_id), **value}
        return value

    def checkpoint(
        self, project_id: str, creative_id: str, *, kind: str,
        base_sha256: str, configuration: Mapping[str, Any], content: Mapping[str, Any],
        change_note: str = "", metric_provenance: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if kind not in {"save", "approve"}:
            raise ValueError("Studio checkpoint kind is invalid")
        creative = self.authority.get_creative(creative_id)
        if creative["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Studio creative was not found in this Project")
        workspace = self._workspace(creative_id)
        current = workspace.detail()
        # Accept the same bounded legacy snapshot as preview/configuration.
        # An already-open browser can still hold its verified stored hash.
        workspace._assert_state(base_sha256)

        definition = workspace._definition()
        candidate_configuration = definition.normalize_configuration(configuration)
        candidate_content = definition.normalize_content(content)
        pending_changes = (
            _canonical(candidate_configuration) != _canonical(current["configuration"])
            or _canonical(candidate_content) != _canonical(current["content"])
        )
        generation = dict(creative.get("generation") or {})
        if "stats" in candidate_content and (metric_provenance is not None or candidate_content["stats"] != current["content"].get("stats")):
            generation["metric_provenance"] = reconcile_metrics(candidate_content["stats"], generation.get("metric_provenance"), supplied=metric_provenance)
        version_created = False
        if kind == "approve":
            versions = current.get("versions", [])
            if pending_changes or not versions or versions[-1]["state_sha256"] != current["state_sha256"]:
                current = workspace.approve_configuration(
                    base_sha256=base_sha256, configuration=candidate_configuration,
                    content=candidate_content,
                    change_note=_compact(change_note, "change_note", 1, 240),
                    metric_provenance=generation.get("metric_provenance"),
                )
                version_created = True
        elif pending_changes or creative["state_sha256"] != current["state_sha256"]:
            # On an explicit Save, persist normalized files before advancing
            # metadata, even when the owner submitted an unchanged legacy view.
            current = workspace.save_configuration(
                base_sha256=base_sha256, configuration=candidate_configuration,
                content=candidate_content,
            )
        after = _state_snapshot(current)
        after_sha = sha256_json(after)
        before = _normalized_checkpoint_baseline(
            creative.get("learning_baseline") or after, after,
        )
        before_sha = sha256_json(before)
        if after_sha == before_sha:
            updated = self.authority.update_creative(
                creative_id, state_sha256=current["state_sha256"], generation=generation,
                learning_baseline=after, learning_baseline_sha256=after_sha,
                approved_version_count=len(current.get("versions", [])),
            )
            return {
                "creative": {**{k: v for k, v in updated.items() if k != "learning_baseline"}, **current},
                "checkpoint_created": False, "version_created": version_created,
                "checkpoint": None, "learning_proposal": None,
                "project_logo_default_updated": False,
            }
        paths = _diff_paths(before, after)
        checkpoint_id = new_uuid7()
        checkpoint = {
            "checkpoint_id": checkpoint_id, "creative_id": creative_id,
            "project_id": project_id, "kind": kind, "before_state_sha256": before_sha,
            "after_state_sha256": after_sha, "changed_paths": paths,
            "before_snapshot": before, "after_snapshot": after,
            "status": "saved", "version": len(current.get("versions", [])) if kind == "approve" else None,
            "created_at": utc_now(),
        }
        logo_paths = {
            "configuration.logo.symbol_color",
            "configuration.logo.name_color",
        }
        logo_changed = bool(logo_paths.intersection(paths))
        project_logo_default_updated = False
        if logo_changed and hasattr(
            self.authority, "record_checkpoint_with_project_logo_default",
        ):
            checkpoint, project_logo_default_updated = (
                self.authority.record_checkpoint_with_project_logo_default(
                    checkpoint, {
                        "symbol_color": current["configuration"]["logo"]["symbol_color"],
                        "name_color": current["configuration"]["logo"]["name_color"],
                    },
                )
            )
        else:
            checkpoint = self.authority.record_checkpoint(checkpoint)
        checkpoint_id = str(checkpoint["checkpoint_id"])
        self.authority.update_creative(
            creative_id, state_sha256=current["state_sha256"], generation=generation,
            learning_baseline=after, learning_baseline_sha256=after_sha,
            latest_checkpoint_id=checkpoint_id,
            approved_version_count=len(current.get("versions", [])),
        )
        return {
            "creative": self.detail(project_id, creative_id),
            "checkpoint_created": True, "version_created": version_created,
            "checkpoint": {
                **{key: value for key, value in checkpoint.items() if key not in {"before_snapshot", "after_snapshot"}},
                "status": "saved",
            },
            "learning_proposal": None,
            "project_logo_default_updated": project_logo_default_updated,
        }

    def recover_interrupted(self) -> list[str]:
        if hasattr(self.authority, "recover_interrupted"):
            return list(self.authority.recover_interrupted())
        recovered = []
        projects = self.authority.store.list("projects") if hasattr(self.authority, "store") else []
        for project in projects:
            for creative in self.authority.list_creatives(project["project_id"]):
                if creative["status"] in {"queued", "composing", "generating_image"}:
                    if creative["status"] == "composing":
                        self.authority.update_creative(creative["creative_id"], status="queued")
                    recovered.append(creative["creative_id"])
        return recovered
