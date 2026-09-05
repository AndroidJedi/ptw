"""Project-scoped Studio creative orchestration and runtime learning."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import threading
from typing import Any, Callable, Mapping
from uuid import UUID

from commander.ids import new_uuid7

from .local_brief_store import LocalBriefStore, sha256_json, utc_now
from .local_codex import sanitized
from .phone_hero_styles import (
    normalize_phone_hero_creative_direction,
    phone_hero_direction_options,
)
from .studio_phone_metrics import PHONE_METRICS_TEMPLATE_ID
from .studio_workspace import UniversalStudioWorkspace


CREATIVE_STATUSES = frozenset({"queued", "composing", "generating_image", "draft", "failed"})
TEMPLATE_IDS = frozenset({"universal_ad", PHONE_METRICS_TEMPLATE_ID})
GLOBAL_SKILL_SCOPE = "global"
PROJECT_SKILL_SCOPE = "project"
_DIGEST = re.compile(r"\b[0-9a-fA-F]{64}\b")


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
        content = properties["content"]["properties"]
        for field, minimum, maximum in (
            ("offer", 1, 32), ("hero_title", 1, 140),
            ("supporting_text", 1, 220), ("cta", 1, 60),
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
    return {
        "type": "object", "properties": properties,
        "required": list(properties), "additionalProperties": False,
    }


def studio_edit_learning_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "edit_summary": {"type": "string", "minLength": 8, "maxLength": 1200},
            "project_lesson": {"type": "string", "minLength": 8, "maxLength": 800},
            "global_rule": {"type": "string", "minLength": 8, "maxLength": 800},
        },
        "required": ["edit_summary", "project_lesson", "global_rule"],
        "additionalProperties": False,
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
        "template_sha256": detail.get("template_sha256"),
        "configuration": deepcopy(detail.get("configuration")),
        "content": deepcopy(detail.get("content")),
        "assets": assets,
        "phone_screen_history": phone_history,
    }


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
        self.ensure_project_skill(project_id)
        self.ensure_global_skill()
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
        attempts = [item for item in self.store.list("studio_learning_runs") if (
            item["checkpoint_id"] == checkpoint_id
        )]
        latest = max(attempts, key=lambda item: int(item["attempt"])) if attempts else None
        return {
            **checkpoint,
            "status": "completed" if latest and latest["status"] == "completed" else "queued",
            "learning_run_id": None if latest is None else latest["learning_run_id"],
            "learning_attempt": None if latest is None else latest["attempt"],
            "edit_summary": None if latest is None else latest.get("edit_summary"),
            "project_lesson": None if latest is None else latest.get("project_lesson"),
            "project_skill_snapshot_id": None if latest is None else latest.get("project_skill_snapshot_id"),
            "provider": {} if latest is None else latest.get("provider") or {},
            "error_type": None if latest is None else latest.get("error_type"),
            "error_message": None if latest is None else latest.get("error_message"),
        }

    def queued_checkpoints(self) -> list[dict[str, Any]]:
        return [
            self.get_checkpoint(str(item["checkpoint_id"]))
            for item in self.store.list("studio_edit_checkpoints")
            if self.get_checkpoint(str(item["checkpoint_id"])).get("status") == "queued"
        ]

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
    """Coordinate template workspaces, generation, and checkpoint learning."""

    def __init__(
        self, *, root: Path | str, authority: Any,
        workspace_factory: Callable[[Path], Any], structured_provider: Any | None,
        composer_skill_path: Path, learner_skill_path: Path,
        phone_skill_path: Path,
    ) -> None:
        self.root = Path(root)
        self.creatives_root = self.root / "creatives"
        self.creatives_root.mkdir(parents=True, exist_ok=True)
        self.authority = authority
        self.workspace_factory = workspace_factory
        self.structured_provider = structured_provider
        self.composer_skill = composer_skill_path.read_text(encoding="utf-8")
        self.learner_skill = learner_skill_path.read_text(encoding="utf-8")
        self.phone_skill = phone_skill_path.read_text(encoding="utf-8")
        self._workspaces: dict[str, Any] = {}
        self._lock = threading.RLock()

    def templates(self) -> dict[str, Any]:
        templates = []
        with tempfile.TemporaryDirectory(prefix=".catalog-", dir=self.root) as temporary:
            scratch = UniversalStudioWorkspace(Path(temporary))
            for template_id in sorted(TEMPLATE_IDS):
                detail = scratch.detail()
                if (detail.get("template_id") or detail["catalog"]["template_id"]) != template_id:
                    detail = scratch.apply_template(
                        base_sha256=detail["state_sha256"], template_id=template_id,
                    )
                templates.append({
                    **next(item for item in detail["templates"] if item["template_id"] == template_id),
                    "template_version": detail["catalog"]["template_version"],
                    "template_sha256": detail["template_sha256"],
                    **({"creative_direction_options": phone_hero_direction_options()}
                       if template_id == PHONE_METRICS_TEMPLATE_ID else {}),
                })
        return {"schema": "ptw.studio.template-catalog.v1", "items": templates}

    def _workspace(self, creative_id: str) -> Any:
        creative_id = _uuid(creative_id, "creative_id")
        self.authority.get_creative(creative_id)
        if creative_id not in self._workspaces:
            self._workspaces[creative_id] = self.workspace_factory(self.creatives_root / creative_id)
        return self._workspaces[creative_id]

    @staticmethod
    def _template_id(detail: Mapping[str, Any]) -> str:
        return str(detail.get("template_id") or detail["catalog"]["template_id"])

    def _initialize_workspace(self, creative: Mapping[str, Any]) -> dict[str, Any]:
        workspace = self._workspace(str(creative["creative_id"]))
        detail = workspace.detail()
        if self._template_id(detail) != creative["template_id"]:
            detail = workspace.apply_template(
                base_sha256=detail["state_sha256"], template_id=str(creative["template_id"]),
            )
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

    def approve_brief_and_reserve(
        self, *, brief_id: str, template_id: str, requested_by: str,
        brief_approver: Callable[[str, str], tuple[dict[str, Any], bool]],
        creative_direction: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool, dict[str, Any], bool]:
        """Approve and reserve idempotently; PostgreSQL performs both in one transaction."""

        if template_id not in TEMPLATE_IDS:
            raise ValueError("Studio template is invalid")
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
        if detail.get("template_id") != PHONE_METRICS_TEMPLATE_ID:
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
        return {**detail, **self.summary(creative_id)}

    def _provider_call(self, **kwargs: Any) -> dict[str, Any]:
        if self.structured_provider is None:
            raise RuntimeError("Studio structured provider is unavailable")
        response_validator = kwargs.pop("response_validator", None)
        if hasattr(self.structured_provider, "call"):
            return self.structured_provider.call(
                **kwargs, response_validator=response_validator,
            )
        result = self.structured_provider.generate(**kwargs)
        if response_validator is None:
            return result
        return {**result, "response": dict(response_validator(result["response"]))}

    def _phone_skill_context(self, creative: Mapping[str, Any]) -> str:
        """Build the bounded, model-independent context used by every hero call."""

        project_skill = self.authority.latest_skill(
            PROJECT_SKILL_SCOPE, str(creative["project_id"]),
        )
        global_skill = self.authority.latest_skill(GLOBAL_SKILL_SCOPE)
        return "\n\n".join((
            self.phone_skill,
            "Accepted global Studio lessons:\n" + str(global_skill["content"]),
            "Accepted Project Studio lessons:\n" + str(project_skill["content"]),
        ))[:6000]

    def _finish_draft(
        self, creative_id: str, detail: Mapping[str, Any], generation: Mapping[str, Any],
    ) -> dict[str, Any]:
        baseline = _state_snapshot(detail)
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
                enhance_current=False, skill_context=self._phone_skill_context(creative),
                creative_direction=creative_direction,
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
        project_skill = self.authority.latest_skill(PROJECT_SKILL_SCOPE, creative["project_id"])
        global_skill = self.authority.latest_skill(GLOBAL_SKILL_SCOPE)
        existing_generation = dict(creative.get("generation") or {})
        self.authority.update_creative(creative_id, status="composing", generation={
            **existing_generation, "stage": "composing", "project_skill_snapshot_id": project_skill["skill_snapshot_id"],
            "project_skill_sha256": project_skill["content_sha256"],
            "global_skill_snapshot_id": global_skill["skill_snapshot_id"],
            "global_skill_sha256": global_skill["content_sha256"],
        })
        generation_context = {
            "source_brief_id": creative["source_brief_id"],
            "template_id": creative["template_id"],
            "template_version": detail["catalog"]["template_version"],
            "template_sha256": detail["template_sha256"],
            "project_skill_snapshot_id": project_skill["skill_snapshot_id"],
            "project_skill_sha256": project_skill["content_sha256"],
            "global_skill_snapshot_id": global_skill["skill_snapshot_id"],
            "global_skill_sha256": global_skill["content_sha256"],
            **({"creative_direction": self._creative_direction(creative)}
               if creative["template_id"] == PHONE_METRICS_TEMPLATE_ID else {}),
        }
        payload = {
            "creative_id": creative_id, "approved_product_brief": brief["document"],
            "selected_template_id": creative["template_id"], "live_template_catalog": detail["catalog"],
            "template_defaults": {
                "configuration": detail["configuration"], "content": detail["content"],
            },
            "global_skill": global_skill["content"], "project_skill": project_skill["content"],
            **({"creative_direction": self._creative_direction(creative)}
               if creative["template_id"] == PHONE_METRICS_TEMPLATE_ID else {}),
        }
        system_prompt = (
            self.composer_skill + "\n\nThe live catalog in INPUT_JSON is authoritative. "
            "Return a complete bounded configuration and content object."
        )

        def validate_composition(value: Mapping[str, Any]) -> Mapping[str, Any]:
            expected_fields = {"configuration", "content"}
            if creative["template_id"] == PHONE_METRICS_TEMPLATE_ID:
                expected_fields.add("visual_direction")
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
            return value

        try:
            result = self._provider_call(
                mode="studio_creative_generation", system_prompt=system_prompt,
                input_payload=payload, output_schema=creative_generation_schema(detail),
                idempotency_key=f"studio-creative:{creative_id}",
                prompt_version="studio-creative-composer-v2",
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
            }
            self.authority.record_generation(
                creative_id=creative_id, stage="composition", status="completed",
                provenance={**generation_context, "provider": generation["composition"]},
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
        self.authority.update_creative(creative_id, status="queued")
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
        self.detail(project_id, creative_id)
        workspace = self._workspace(creative_id)
        target = getattr(workspace, method)
        if method == "generate_phone_screen":
            creative = self.authority.get_creative(creative_id)
            direction = self._creative_direction(creative)
            if direction is None:
                raise ValueError("Select a Phone Metrics visual style before generating an image")
            kwargs["skill_context"] = self._phone_skill_context(creative)
            kwargs["creative_direction"] = direction
        value = target(*args, **kwargs)
        if isinstance(value, dict) and value.get("state_sha256"):
            self.authority.update_creative(
                creative_id, state_sha256=value["state_sha256"],
                template_id=self._template_id(value),
                template_version=value["catalog"]["template_version"],
                template_sha256=value["template_sha256"],
            )
            return {**value, **self.summary(creative_id)}
        return value

    def _unsafe_global_rule(
        self, rule: str, *, creative: Mapping[str, Any], before: Mapping[str, Any],
        after: Mapping[str, Any],
    ) -> bool:
        lowered = rule.casefold()
        forbidden = [str(creative["project_id"]), str(creative.get("source_brief_id") or "")]
        project = self.authority.project(str(creative["project_id"]))
        forbidden.append(str(project.get("name") or ""))
        for snapshot in (before, after):
            for value in _walk_strings(snapshot.get("content")):
                if len(value) >= 12:
                    forbidden.append(value)
            for value in _walk_strings(snapshot.get("assets")):
                if len(value) >= 3:
                    forbidden.append(value)
            for value in _walk_strings(snapshot.get("phone_screen_history")):
                if len(value) >= 3:
                    forbidden.append(value)
        personal_data = re.search(
            r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://\S+|\+?\d[\d ()-]{7,}\d)",
            rule,
        )
        return bool(
            _DIGEST.search(rule) or personal_data
            or any(value and value.casefold() in lowered for value in forbidden)
        )

    def _learn_checkpoint(
        self, checkpoint: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        checkpoint = deepcopy(dict(checkpoint))
        checkpoint_id = str(checkpoint["checkpoint_id"])
        creative_id = str(checkpoint["creative_id"])
        project_id = str(checkpoint["project_id"])
        creative = self.authority.get_creative(creative_id)
        before = checkpoint["before_snapshot"]
        after = checkpoint["after_snapshot"]
        paths = list(checkpoint["changed_paths"])
        payload = {
            "checkpoint_kind": checkpoint["kind"], "changed_paths": paths,
            "before": before, "after": after,
            "project_name": self.authority.project(project_id).get("name"),
        }
        try:
            result = self._provider_call(
                mode="studio_edit_learning", system_prompt=self.learner_skill,
                input_payload=payload, output_schema=studio_edit_learning_schema(),
                idempotency_key=f"studio-checkpoint:{checkpoint_id}",
                prompt_version="studio-edit-learner-v1",
            )
            learned = result["response"]
            summary = _compact(learned["edit_summary"], "edit_summary", 8, 1200)
            project_lesson = _compact(learned["project_lesson"], "project_lesson", 8, 800)
            global_rule = _compact(learned["global_rule"], "global_rule", 8, 800)
            if self._unsafe_global_rule(
                global_rule, creative=creative, before=before, after=after,
            ):
                raise ValueError("global Studio proposal contains project-specific or sensitive content")
            project_skill = self.authority.create_project_skill(
                project_id=project_id, lesson=project_lesson, checkpoint_id=checkpoint_id,
            )
            proposal = self.authority.create_proposal(
                checkpoint_id=checkpoint_id,
                project_skill_snapshot_id=project_skill["skill_snapshot_id"],
                global_rule=global_rule,
            )
            self.authority.record_learning_result(
                checkpoint_id, status="completed", edit_summary=summary,
                project_lesson=project_lesson,
                project_skill_snapshot_id=project_skill["skill_snapshot_id"],
                provider=sanitized(result.get("invocation") or {}), error=None,
            )
            return self.authority.get_checkpoint(checkpoint_id), proposal
        except Exception as error:
            self.authority.record_learning_result(
                checkpoint_id, status="failed",
                edit_summary=checkpoint.get("edit_summary")
                or f"Saved changes: {', '.join(paths[:12])}",
                project_lesson=None, project_skill_snapshot_id=None,
                provider={}, error=error,
            )
            return self.authority.get_checkpoint(checkpoint_id), None

    def checkpoint(
        self, project_id: str, creative_id: str, *, kind: str,
        base_sha256: str, configuration: Mapping[str, Any], content: Mapping[str, Any],
        change_note: str = "",
    ) -> dict[str, Any]:
        if kind not in {"save", "approve"}:
            raise ValueError("Studio checkpoint kind is invalid")
        creative = self.authority.get_creative(creative_id)
        if creative["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Studio creative was not found in this Project")
        workspace = self._workspace(creative_id)
        current = workspace.detail()
        if base_sha256 != current["state_sha256"]:
            raise RuntimeError("Studio state changed; reload before saving")
        pending_changes = (
            _canonical(configuration) != _canonical(current["configuration"])
            or _canonical(content) != _canonical(current["content"])
        )
        version_created = False
        if kind == "approve":
            versions = current.get("versions", [])
            if pending_changes or not versions or versions[-1]["state_sha256"] != current["state_sha256"]:
                current = workspace.approve_configuration(
                    base_sha256=base_sha256, configuration=configuration,
                    content=content,
                    change_note=_compact(change_note, "change_note", 1, 240),
                )
                version_created = True
        elif pending_changes:
            current = workspace.save_configuration(
                base_sha256=base_sha256, configuration=configuration, content=content,
            )
        after = _state_snapshot(current)
        after_sha = sha256_json(after)
        before = creative.get("learning_baseline") or after
        before_sha = creative.get("learning_baseline_sha256") or sha256_json(before)
        if after_sha == before_sha:
            updated = self.authority.update_creative(
                creative_id, state_sha256=current["state_sha256"],
                approved_version_count=len(current.get("versions", [])),
            )
            return {
                "creative": {**current, **{k: v for k, v in updated.items() if k != "learning_baseline"}},
                "checkpoint_created": False, "version_created": version_created,
                "checkpoint": None, "learning_proposal": None,
            }
        paths = _diff_paths(before, after)
        checkpoint_id = new_uuid7()
        checkpoint = {
            "checkpoint_id": checkpoint_id, "creative_id": creative_id,
            "project_id": project_id, "kind": kind, "before_state_sha256": before_sha,
            "after_state_sha256": after_sha, "changed_paths": paths,
            "before_snapshot": before, "after_snapshot": after,
            "status": "learning", "version": len(current.get("versions", [])) if kind == "approve" else None,
            "created_at": utc_now(),
        }
        checkpoint = self.authority.record_checkpoint(checkpoint)
        checkpoint_id = str(checkpoint["checkpoint_id"])
        self.authority.update_creative(
            creative_id, state_sha256=current["state_sha256"],
            learning_baseline=after, learning_baseline_sha256=after_sha,
            latest_checkpoint_id=checkpoint_id,
            approved_version_count=len(current.get("versions", [])),
        )
        checkpoint, proposal = self._learn_checkpoint(checkpoint)
        return {
            "creative": self.detail(project_id, creative_id),
            "checkpoint_created": True, "version_created": version_created,
            "checkpoint": {key: value for key, value in checkpoint.items() if key not in {"before_snapshot", "after_snapshot"}},
            "learning_proposal": proposal,
        }

    def retry_learning(
        self, project_id: str, creative_id: str, checkpoint_id: str,
    ) -> dict[str, Any]:
        self.detail(project_id, creative_id)
        checkpoint = self.authority.get_checkpoint(_uuid(checkpoint_id, "checkpoint_id"))
        if (
            str(checkpoint["creative_id"]) != str(creative_id)
            or str(checkpoint["project_id"]) != str(project_id)
        ):
            raise KeyError("Studio checkpoint was not found in this creative")
        if checkpoint.get("status") != "queued":
            raise ValueError("only queued Studio learning can be retried")
        learned, proposal = self._learn_checkpoint(checkpoint)
        return {
            "checkpoint": {
                key: value for key, value in learned.items()
                if key not in {"before_snapshot", "after_snapshot"}
            },
            "learning_proposal": proposal,
        }

    def recover_learning(self) -> list[dict[str, str]]:
        if not hasattr(self.authority, "queued_checkpoints"):
            return []
        return [{
            "project_id": str(item["project_id"]),
            "creative_id": str(item["creative_id"]),
            "checkpoint_id": str(item["checkpoint_id"]),
        } for item in self.authority.queued_checkpoints()]

    def decide_learning(
        self, project_id: str, creative_id: str, proposal_id: str, decision: str,
    ) -> dict[str, Any]:
        self.detail(project_id, creative_id)
        if hasattr(self.authority, "proposal_checkpoint"):
            checkpoint = self.authority.proposal_checkpoint(proposal_id)
            if (
                str(checkpoint["creative_id"]) != str(creative_id)
                or str(checkpoint["project_id"]) != str(project_id)
            ):
                raise KeyError("Studio learning proposal was not found in this creative")
        return self.authority.decide_proposal(proposal_id, decision)

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


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [" ".join(value.split())]
    if isinstance(value, Mapping):
        result: list[str] = []
        for item in value.values():
            result.extend(_walk_strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_walk_strings(item))
        return result
    return []
