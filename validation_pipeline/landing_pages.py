"""Project-scoped Landing Studio orchestration and local append-only authority."""

from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Callable, Iterator, Mapping
from uuid import UUID

from commander.ids import new_uuid7

from .image_generation_policy import IMAGE_POLICY_VERSION, build_image_context, compile_image_prompt, image_provenance, resolve_instruction
from .agent_context import compact_active_skills
from .landing_workspace import (
    DEFAULT_CONFIGURATION, DEFAULT_CONTENT, DEFAULT_PRESENTATION,
    LANDING_CONTENT_LIMITS, LANDING_CONTENT_SCHEMA, LANDING_TEMPLATE_ID,
    LANDING_VISUAL_SLOTS, LandingWorkspace,
    canonical_json, normalize_composed_content, normalize_configuration,
    normalize_content, sha256_json,
)
from .landing_templates import LANDING_TEMPLATE_REGISTRY
from .landing_design import (
    APP_FEATURE_LIMITS, DEFAULT_APP_FEATURE, DEFAULT_COMPONENTS,
    DEFAULT_IMAGE_DIRECTIONS, DEFAULT_PHONE_MOCKUP,
    LANDING_BACKGROUND_DIRECTIVES, PHONE_HERO_STYLE_DIRECTIVES,
)
from .local_brief_store import LocalBriefStore, utc_now
from .local_codex import sanitized
from .studio_creatives import _json_schema
from .studio_manual_agent import (
    STUDIO_MANUAL_AGENT_PROMPT_VERSION, STUDIO_MANUAL_AGENT_REASONING_EFFORT,
    apply_manual_agent_edits, manual_agent_editable_values, manual_agent_payload,
    manual_agent_schema, response_reply, screenshot_artifacts,
    studio_manual_agent_provider_error, validate_image_actions,
    validate_manual_agent_semantics,
)


LANDING_STATUSES = frozenset({"queued", "composing", "generating_images", "draft", "failed"})
LANDING_COMPOSER_PROMPT_VERSION = "landing-page-composer-v5"


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{field} must be a UUID") from error


def _compact(value: Any, field: str, minimum: int, maximum: int) -> str:
    result = " ".join(str(value or "").split())
    if not minimum <= len(result) <= maximum:
        raise ValueError(f"Landing {field} must contain {minimum}-{maximum} characters")
    return result


def _diff_paths(before: Any, after: Any, prefix: str = "") -> list[str]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        result: list[str] = []
        for key in sorted(set(before) | set(after)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in before and isinstance(after[key], Mapping):
                result.extend(_diff_paths({}, after[key], path))
            elif key not in after and isinstance(before[key], Mapping):
                result.extend(_diff_paths(before[key], {}, path))
            elif key not in before or key not in after:
                result.append(path)
            else:
                result.extend(_diff_paths(before[key], after[key], path))
        return result
    if isinstance(before, list) and isinstance(after, list):
        return [path for index in range(max(len(before), len(after))) for path in (
            [f"{prefix}[{index}]"] if index >= len(before) or index >= len(after)
            else _diff_paths(before[index], after[index], f"{prefix}[{index}]")
        )]
    return [] if before == after else [prefix or "state"]


def _snapshot(detail: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "configuration": deepcopy(detail["configuration"]), "content": deepcopy(detail["content"]),
        "assets": deepcopy(detail["assets"]),
    }


def landing_generation_schema() -> dict[str, Any]:
    """Return only the bounded AI-owned portion of a Landing composition."""
    result = {
        "type": "object",
        "properties": {
            "content": _json_schema({**DEFAULT_CONTENT, "app_feature": DEFAULT_APP_FEATURE}),
        },
        "required": ["content"], "additionalProperties": False,
    }
    content = result["properties"]["content"]["properties"]
    content["schema"]["enum"] = [LANDING_CONTENT_SCHEMA]
    app = content["app_feature"]["properties"]
    for field in ("title", "description", "action_label"):
        app[field].update({"minLength": 1, "maxLength": APP_FEATURE_LIMITS[field]})
    for field in ("label", "value"):
        app["items"]["items"]["properties"][field].update({
            "minLength": 1, "maxLength": APP_FEATURE_LIMITS[field],
        })
    for path in (
        "hero.title", "hero.supporting_text", "hero.cta_label",
        "hero.visual_direction", "social_proof.heading",
        "visual_break.visual_direction", "contacts.heading",
        "contacts.supporting_text",
    ):
        section, field = path.split(".")
        minimum, maximum = LANDING_CONTENT_LIMITS[path]
        content[section]["properties"][field].update({
            "minLength": minimum, "maxLength": maximum,
        })
    for field in ("email", "phone", "url"):
        content["contacts"]["properties"][field]["enum"] = [""]
    for field in ("title", "description"):
        minimum, maximum = LANDING_CONTENT_LIMITS[f"feature.{field}"]
        content["features"]["items"]["properties"][field].update({
            "minLength": minimum, "maxLength": maximum,
        })
    for field in ("question", "answer"):
        minimum, maximum = LANDING_CONTENT_LIMITS[f"faq.{field}"]
        content["faq"]["items"]["properties"][field].update({
            "minLength": minimum, "maxLength": maximum,
        })
    return result


def validate_landing_composition(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"content"}:
        raise ValueError("Landing composer response fields are invalid")
    return {"content": normalize_composed_content(value["content"])}


def landing_composition_payload(
    *, landing_id: str, approved_product_brief: Mapping[str, Any],
    source_post_snapshot: Mapping[str, Any], content_defaults: Mapping[str, Any],
    active_creative_skills: Mapping[str, Any], live_landing_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the one canonical, bounded payload used by runtime and canaries."""
    definition = LANDING_TEMPLATE_REGISTRY.get(LANDING_TEMPLATE_ID)
    if live_landing_catalog.get("template_id") != definition.identity.template_id:
        raise ValueError("Landing generation catalog is not registered")
    post_reference = {
        key: source_post_snapshot[key]
        for key in ("template_id", "template_version", "template_sha256")
        if key in source_post_snapshot
    }
    return {
        "landing_id": landing_id,
        "approved_product_brief": deepcopy(dict(approved_product_brief)),
        "source_post_copy": {
            "template_id": source_post_snapshot.get("template_id"),
            "content": deepcopy(source_post_snapshot.get("content") or {}),
            "metric_provenance": deepcopy(source_post_snapshot.get("metric_provenance") or []),
            "version_sha256": source_post_snapshot.get("version_sha256"),
        },
        **({"source_post_template_reference": post_reference}
           if len(post_reference) == 3 else {}),
        "template_content_defaults": {
            "content": deepcopy(dict(content_defaults)),
        },
        "live_landing_catalog": definition.agent_catalog(),
        "active_creative_skills": compact_active_skills(
            active_creative_skills, surface="landing",
        ),
    }


def _landing_skill_document(scope: str, lessons: list[str]) -> str:
    title = "Global Landing skill" if scope == "global" else "Project Landing skill"
    name = "landing-runtime-global" if scope == "global" else "landing-runtime-project"
    lines = ["---", f"name: {name}", f"description: Runtime Landing learning snapshot for {title}.", "---", "", f"# {title}", ""]
    lines.extend(f"- {lesson}" for lesson in lessons[-40:]) or lines.append("No owner-approved Landing lessons yet.")
    return "\n".join(lines).strip() + "\n"


def _lessons(document: str) -> list[str]:
    return [line[2:] for line in document.splitlines() if line.startswith("- ")]


class LocalLandingAuthority:
    """Append-only local metadata authority.  Workspace bytes remain per-page files."""

    def __init__(self, store: LocalBriefStore, *, post_workspace_root: Path | str) -> None:
        self.store = store
        self.post_workspace_root = Path(post_workspace_root) / "creatives"
        self._lock = threading.RLock()

    def project(self, project_id: str) -> dict[str, Any]:
        return self.store.get("projects", _uuid(project_id, "project_id"))

    def brief(self, brief_id: str) -> dict[str, Any]:
        return self.store.get("briefs", _uuid(brief_id, "brief_id"))

    def _source_version(self, project_id: str, creative_id: str, version: int) -> dict[str, Any]:
        creative = self.store.get("studio_creatives", _uuid(creative_id, "source_creative_id"))
        if creative["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Post was not found in this Project")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("Landing source Post version is invalid")
        paths = list((self.post_workspace_root / creative_id / "versions").glob(f"*_v{version}.json"))
        if len(paths) != 1:
            raise ValueError("Landing requires an immutable approved Post version")
        record = json.loads(paths[0].read_text(encoding="utf-8"))
        template = record["template_id"]
        if record.get("version") != version or not isinstance(record.get("version_sha256"), str):
            raise ValueError("Landing source Post version is invalid")
        source = {
            "creative_id": creative_id, "version": version, "version_sha256": record["version_sha256"],
            "source_brief_id": creative["source_brief_id"], "template_id": template,
            "configuration": record["configuration"], "content": record["content"],
            "metric_provenance": deepcopy(record.get("metric_provenance") or []),
            "assets": record.get("assets", []), "generation": deepcopy(creative.get("generation") or {}),
        }
        if creative.get("template_version") is not None and record.get("template_sha256"):
            source.update({
                "template_version": int(record.get("template_reference", {}).get("template_version") or record.get("primitive_template", {}).get("version") or creative["template_version"]),
                "template_sha256": record["template_sha256"],
            })
        return source

    def source_versions(self, project_id: str) -> list[dict[str, Any]]:
        project_id = _uuid(project_id, "project_id")
        self.project(project_id)
        items: list[dict[str, Any]] = []
        for creative in self.store.list("studio_creatives"):
            if creative.get("project_id") != project_id:
                continue
            versions = self.post_workspace_root / str(creative["creative_id"]) / "versions"
            for path in sorted(versions.glob("*_v*.json")) if versions.is_dir() else []:
                record = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "creative_id": creative["creative_id"], "version": record["version"],
                    "version_sha256": record["version_sha256"], "template_id": record["template_id"],
                    "source_brief_id": creative["source_brief_id"],
                })
        return sorted(items, key=lambda item: (item["creative_id"], item["version"]), reverse=True)

    def create_page(self, *, project_id: str, source_creative_id: str, source_version: int, requested_by: str, additional: bool = False) -> tuple[dict[str, Any], bool]:
        project_id = _uuid(project_id, "project_id")
        source = self._source_version(project_id, source_creative_id, source_version)
        with self._lock:
            siblings = sorted(
                (item for item in self.store.list("landing_pages") if item["source_creative_id"] == source_creative_id and item["source_version"] == source_version),
                key=lambda item: int(item["ordinal"]),
            )
            if siblings and not additional:
                return siblings[0], False
            if additional and (not siblings or int(siblings[-1].get("approved_version_count") or 0) < 1):
                raise ValueError("approve the current Landing before creating another variant")
            landing_id, now = new_uuid7(), utc_now()
            value = {
                "landing_id": landing_id, "project_id": project_id, "source_brief_id": source["source_brief_id"],
                "source_creative_id": source_creative_id, "source_version": source_version,
                "source_version_sha256": source["version_sha256"], "source_post_snapshot": source,
                "ordinal": len(siblings) + 1, "origin": "approved_variant" if additional else "post_generation",
                "status": "queued", "state_sha256": None, "generation": {}, "learning_baseline": None,
                "learning_baseline_sha256": None, "approved_version_count": 0, "requested_by": requested_by,
                "created_at": now, "updated_at": now,
            }
            self.store.append("landing_pages", landing_id, value)
            self.store.edge(source_id=project_id, relation="contains", target_id=landing_id, evidence={"member": "landing_page", "ordinal": value["ordinal"]})
            self.store.edge(source_id=landing_id, relation="derived_from", target_id=source["source_brief_id"], evidence={"input": "approved_product_brief"})
            self.store.edge(source_id=landing_id, relation="derived_from", target_id=source_creative_id, evidence={"input": "approved_post_version", "version": source_version, "sha256": source["version_sha256"]})
            return value, True

    def get_page(self, landing_id: str) -> dict[str, Any]:
        return self.store.get("landing_pages", _uuid(landing_id, "landing_id"))

    def list_pages(self, project_id: str) -> list[dict[str, Any]]:
        project_id = _uuid(project_id, "project_id")
        self.project(project_id)
        return [item for item in self.store.list("landing_pages") if item["project_id"] == project_id]

    def recover_interrupted(self) -> list[str]:
        return [
            str(item["landing_id"]) for item in self.store.list("landing_pages")
            if item["status"] in {"queued", "composing", "generating_images"}
        ]

    def update_page(self, landing_id: str, **patch: Any) -> dict[str, Any]:
        value = self.get_page(landing_id)
        allowed = {"status", "state_sha256", "generation", "learning_baseline", "learning_baseline_sha256", "approved_version_count"}
        if not set(patch) <= allowed or patch.get("status", value["status"]) not in LANDING_STATUSES:
            raise ValueError("Landing update is invalid")
        next_value = {**value, **deepcopy(patch), "updated_at": utc_now()}
        self.store.append("landing_pages", landing_id, next_value)
        return next_value

    def ensure_skill(self, scope: str, project_id: str | None = None) -> dict[str, Any]:
        if scope not in {"global", "project"} or (scope == "project") != bool(project_id):
            raise ValueError("Landing skill scope is invalid")
        existing = [item for item in self.store.list("landing_skill_snapshots") if item["scope"] == scope and item.get("project_id") == project_id]
        if existing:
            return existing[0]
        return self._append_skill(scope=scope, project_id=project_id, lesson=None, checkpoint_id=None)

    def _append_skill(self, *, scope: str, project_id: str | None, lesson: str | None, checkpoint_id: str | None) -> dict[str, Any]:
        existing = [item for item in self.store.list("landing_skill_snapshots") if item["scope"] == scope and item.get("project_id") == project_id]
        previous = existing[0] if existing else None
        lessons = [] if previous is None else _lessons(previous["content"])
        if lesson:
            lessons.append(_compact(lesson, "lesson", 8, 800))
        content = _landing_skill_document(scope, lessons)
        value = {
            "skill_snapshot_id": new_uuid7(), "scope": scope, "project_id": project_id,
            "version": 1 if previous is None else int(previous["version"]) + 1, "content": content,
            "content_sha256": hashlib.sha256(content.encode()).hexdigest(), "source_checkpoint_id": checkpoint_id,
            "created_at": utc_now(),
        }
        self.store.append("landing_skill_snapshots", value["skill_snapshot_id"], value)
        return value

    def latest_skill(self, scope: str, project_id: str | None = None) -> dict[str, Any]:
        return self.ensure_skill(scope, project_id)

    def record_checkpoint(self, value: Mapping[str, Any]) -> dict[str, Any]:
        self.store.append("landing_checkpoints", str(value["checkpoint_id"]), value)
        self.store.edge(source_id=str(value["landing_id"]), relation="contains", target_id=str(value["checkpoint_id"]), evidence={"member": "landing_checkpoint"})
        return dict(value)

    def record_generation_run(self, *, landing_id: str, stage: str, status: str, input_sha256: str, output_sha256: str | None, prompt_version: str, invocation: Mapping[str, Any] | None = None, error: Exception | None = None) -> dict[str, Any]:
        if stage not in {"composition", "hero_visual", "visual_break_visual"} or status not in {"completed", "failed"}:
            raise ValueError("Landing generation run is invalid")
        run = {
            "generation_run_id": new_uuid7(), "landing_id": _uuid(landing_id, "landing_id"),
            "stage": stage, "status": status, "input_sha256": input_sha256,
            "output_sha256": output_sha256, "prompt_version": prompt_version,
            "invocation": sanitized(dict(invocation or {})),
            "error_type": None if error is None else type(error).__name__,
            "error_message": None if error is None else str(error)[:1000], "created_at": utc_now(),
        }
        self.store.append("landing_generation_runs", run["generation_run_id"], run)
        self.store.edge(source_id=run["landing_id"], relation="contains", target_id=run["generation_run_id"], evidence={"member": "landing_generation_run", "stage": stage})
        return run

    def synchronize_workspace(self, landing_id: str, workspace: LandingWorkspace) -> None:
        """Append local asset/version lineage for the durable workspace bytes."""
        landing_id = _uuid(landing_id, "landing_id")
        known_assets = {
            item["content_sha256"]: item for item in self.store.list("landing_assets")
            if item.get("landing_id") == landing_id
        }
        asset_ids: dict[str, str] = {
            digest: str(item["asset_id"]) for digest, item in known_assets.items()
        }
        for slot in LANDING_VISUAL_SLOTS:
            for item in workspace._history(slot):
                digest = item["sha256"]
                if digest in asset_ids:
                    continue
                asset = {
                    "asset_id": new_uuid7(), "landing_id": landing_id, "slot": slot,
                    "content_sha256": digest, "mime_type": item["mime_type"],
                    "source": sanitized(dict(item.get("source") or {})), "created_at": utc_now(),
                }
                self.store.append("landing_assets", asset["asset_id"], asset)
                self.store.edge(source_id=landing_id, relation="contains", target_id=asset["asset_id"], evidence={"member": "landing_asset", "slot": slot, "sha256": digest})
                asset_ids[digest] = asset["asset_id"]
        known_versions = {
            int(item["version"]): item for item in self.store.list("landing_versions")
            if item.get("landing_id") == landing_id
        }
        for summary in workspace.detail()["versions"]:
            version = int(summary["version"])
            if version in known_versions:
                continue
            record = workspace.version_detail(version)
            snapshot = {
                "version_id": new_uuid7(), "landing_id": landing_id, "version": version,
                "version_sha256": record["version_sha256"], "state_sha256": record["state_sha256"],
                "record": record, "created_at": utc_now(),
            }
            self.store.append("landing_versions", snapshot["version_id"], snapshot)
            self.store.edge(source_id=landing_id, relation="contains", target_id=snapshot["version_id"], evidence={"member": "landing_version", "version": version})
            for asset in record["assets"]:
                digest = asset.get("sha256") if isinstance(asset, Mapping) else None
                if isinstance(digest, str) and digest in asset_ids:
                    self.store.edge(source_id=snapshot["version_id"], relation="derived_from", target_id=asset_ids[digest], evidence={"input": "selected_landing_visual", "slot": asset.get("slot")})

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        return {**self.store.get("landing_checkpoints", checkpoint_id), "status": "saved"}

    def record_learning_result(self, checkpoint_id: str, **patch: Any) -> dict[str, Any]:
        value = self.get_checkpoint(checkpoint_id)
        next_value = {**value, **deepcopy(patch)}
        self.store.append("landing_checkpoints", checkpoint_id, next_value)
        return next_value

    def create_project_skill(self, *, project_id: str, lesson: str, checkpoint_id: str) -> dict[str, Any]:
        return self._append_skill(scope="project", project_id=project_id, lesson=lesson, checkpoint_id=checkpoint_id)

    def create_proposal(self, *, checkpoint_id: str, project_skill_snapshot_id: str, global_rule: str) -> dict[str, Any]:
        value = {"proposal_id": new_uuid7(), "checkpoint_id": checkpoint_id, "project_skill_snapshot_id": project_skill_snapshot_id, "global_rule": global_rule, "status": "pending", "created_at": utc_now()}
        self.store.append("landing_learning_proposals", value["proposal_id"], value)
        return value

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        return self.store.get("landing_learning_proposals", proposal_id)

    def decide_proposal(self, proposal_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"apply_global", "keep_project"}:
            raise ValueError("Landing learning decision is invalid")
        proposal = self.store.get("landing_learning_proposals", proposal_id)
        if proposal["status"] != "pending":
            return proposal
        if decision == "apply_global":
            checkpoint = self.get_checkpoint(proposal["checkpoint_id"])
            self._append_skill(scope="global", project_id=None, lesson=proposal["global_rule"], checkpoint_id=checkpoint["checkpoint_id"])
        value = {**proposal, "status": decision, "decided_at": utc_now()}
        self.store.append("landing_learning_proposals", proposal_id, value)
        return value


class DatabaseLandingWorkspace:
    """Database-backed cache wrapper for one Landing workspace's files."""

    _mutating = frozenset({"save_configuration", "generate_visual", "select_visual", "approve_configuration"})

    def __init__(self, workspace: LandingWorkspace, authority: "DatabaseLandingAuthority", landing_id: str) -> None:
        self.workspace, self.authority, self.landing_id = workspace, authority, _uuid(landing_id, "landing_id")
        self._loaded = False
        self._lock = threading.RLock()

    def _restore(self, files: Mapping[str, bytes]) -> None:
        root = self.workspace.root.resolve()
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        for relative, content in files.items():
            path = (root / relative).resolve()
            if root not in path.parents:
                raise RuntimeError("Landing database file escaped its workspace root")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.workspace.assets.mkdir(parents=True, exist_ok=True)
        self.workspace.versions.mkdir(parents=True, exist_ok=True)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        stored = self.authority.load_workspace_files(self.landing_id)
        if stored is not None:
            expected, files = stored
            self._restore(files)
            if self.workspace.detail()["state_sha256"] != expected:
                raise RuntimeError("Landing database state digest does not match restored files")
        self._persist()
        self._loaded = True

    def _persist(self) -> None:
        for name, value in (("configuration.json", self.workspace._configuration()), ("content.json", self.workspace._content())):
            path = self.workspace.root / name
            if not path.is_file():
                self.workspace._atomic_json(path, value)
        self.authority.persist_workspace_files(self.landing_id, self.workspace.root, self.workspace.detail())

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.workspace, name)
        if not callable(target):
            return target
        def call(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                self._ensure_loaded()
                value = target(*args, **kwargs)
                if name in self._mutating:
                    self._persist()
                return value
        return call


class DatabaseLandingAuthority:
    """PostgreSQL metadata, graph, workspace bytes, and Landing-only skills."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                yield connection

    def project(self, project_id: str) -> dict[str, Any]:
        from .repository import ValidationRepository
        return ValidationRepository(self.database_url).get_project(_uuid(project_id, "project_id"))

    def brief(self, brief_id: str) -> dict[str, Any]:
        from .repository import ValidationRepository
        return ValidationRepository(self.database_url).get_brief(_uuid(brief_id, "brief_id"))

    @staticmethod
    def _edge(connection: Any, source_id: str, relation: str, target_id: str, attributes: Mapping[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        connection.execute(
            """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                 VALUES(%s,%s,%s,%s,%s) ON CONFLICT(source_id,relation,target_id) DO NOTHING""",
            (UUID(new_uuid7()), UUID(source_id), relation, UUID(target_id), Jsonb(dict(attributes))),
        )

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return {
            "landing_id": str(row[0]), "project_id": str(row[1]), "source_brief_id": str(row[2]),
            "source_creative_id": str(row[3]), "source_version": int(row[4]), "source_version_sha256": row[5],
            "source_post_snapshot": dict(row[6]), "ordinal": int(row[7]), "origin": row[8], "status": row[9],
            "state_sha256": row[10], "generation": dict(row[11] or {}),
            "learning_baseline": None if row[12] is None else dict(row[12]), "learning_baseline_sha256": row[13],
            "approved_version_count": int(row[14]), "requested_by": row[15],
            "created_at": row[16].isoformat(), "updated_at": row[17].isoformat(),
        }

    @staticmethod
    def _select() -> str:
        return """SELECT page.entity_id,page.project_id,page.source_brief_id,page.source_creative_id,
                    page.source_version,page.source_version_sha256,page.source_post_snapshot,page.ordinal,
                    page.origin,page.status,page.state_sha256,page.generation,page.learning_baseline,
                    page.learning_baseline_sha256,(SELECT count(*) FROM landing_versions version WHERE version.landing_id=page.entity_id),
                    page.requested_by,page.created_at,page.updated_at FROM landing_workspaces page"""

    def get_page(self, landing_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(self._select() + " WHERE page.entity_id=%s", (UUID(_uuid(landing_id, "landing_id")),)).fetchone()
        if row is None:
            raise KeyError(landing_id)
        return self._row(row)

    def list_pages(self, project_id: str) -> list[dict[str, Any]]:
        project_id = _uuid(project_id, "project_id")
        self.project(project_id)
        with self.connection() as connection:
            rows = connection.execute(self._select() + " WHERE page.project_id=%s ORDER BY page.created_at DESC", (UUID(project_id),)).fetchall()
        return [self._row(row) for row in rows]

    def _source_version(self, project_id: str, creative_id: str, version: int) -> dict[str, Any]:
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("Landing source Post version is invalid")
        with self.connection() as connection:
            row = connection.execute(
                """SELECT workspace.source_brief_id,workspace.template_id,workspace.template_version,
                          workspace.generation,version.record,version.version_sha256
                     FROM universal_studio_workspaces workspace JOIN universal_studio_versions version
                       ON version.workspace_id=workspace.entity_id
                     WHERE workspace.entity_id=%s AND workspace.project_id=%s AND version.version=%s""",
                (UUID(_uuid(creative_id, "source_creative_id")), UUID(_uuid(project_id, "project_id")), version),
            ).fetchone()
        if row is None:
            raise ValueError("Landing requires an immutable approved Post version in this Project")
        record = dict(row[4])
        return {
            "creative_id": _uuid(creative_id, "source_creative_id"), "version": version,
            "version_sha256": row[5], "source_brief_id": str(row[0]),
            "template_id": record["template_id"], "template_version": int(record.get("template_reference", {}).get("template_version") or record.get("primitive_template", {}).get("version") or row[2]),
            "template_sha256": record["template_sha256"],
            "configuration": record["configuration"], "content": record["content"],
            "metric_provenance": deepcopy(record.get("metric_provenance") or []),
            "assets": record.get("assets", []), "generation": dict(row[3] or {}),
        }

    def source_versions(self, project_id: str) -> list[dict[str, Any]]:
        project_id = _uuid(project_id, "project_id")
        self.project(project_id)
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT workspace.entity_id,version.version,version.version_sha256,version.record->>'template_id',workspace.source_brief_id
                     FROM universal_studio_workspaces workspace JOIN universal_studio_versions version
                       ON version.workspace_id=workspace.entity_id WHERE workspace.project_id=%s
                     ORDER BY workspace.created_at DESC,version.version DESC""", (UUID(project_id),),
            ).fetchall()
        return [{"creative_id": str(row[0]), "version": int(row[1]), "version_sha256": row[2], "template_id": row[3], "source_brief_id": str(row[4])} for row in rows]

    def create_page(self, *, project_id: str, source_creative_id: str, source_version: int, requested_by: str, additional: bool = False) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        project_id = _uuid(project_id, "project_id")
        source = self._source_version(project_id, source_creative_id, source_version)
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"landing-source:{source_creative_id}:{source_version}",))
            siblings = connection.execute("SELECT entity_id FROM landing_workspaces WHERE source_creative_id=%s AND source_version=%s ORDER BY ordinal", (UUID(source_creative_id), source_version)).fetchall()
            if siblings and not additional:
                return self.get_page(str(siblings[0][0])), False
            if additional:
                if not siblings or connection.execute("SELECT 1 FROM landing_versions WHERE landing_id=%s LIMIT 1", (siblings[-1][0],)).fetchone() is None:
                    raise ValueError("approve the current Landing before creating another variant")
            landing_id = new_uuid7()
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_workspace',%s)", (UUID(landing_id), Jsonb({"schema_version": 1, "project_id": project_id})))
            connection.execute(
                """INSERT INTO landing_workspaces(entity_id,project_id,source_brief_id,source_creative_id,source_version,source_version_sha256,source_post_snapshot,ordinal,origin,status,requested_by)
                     VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued',%s)""",
                (UUID(landing_id), UUID(project_id), UUID(source["source_brief_id"]), UUID(source_creative_id), source_version, source["version_sha256"], Jsonb(source), len(siblings)+1, "approved_variant" if additional else "post_generation", requested_by),
            )
            self._edge(connection, project_id, "contains", landing_id, {"member": "landing_page", "ordinal": len(siblings)+1})
            self._edge(connection, landing_id, "derived_from", source["source_brief_id"], {"input": "approved_product_brief"})
            self._edge(connection, landing_id, "derived_from", source_creative_id, {"input": "approved_post_version", "version": source_version, "sha256": source["version_sha256"]})
        return self.get_page(landing_id), True

    def update_page(self, landing_id: str, **patch: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        allowed = {"status", "state_sha256", "generation", "learning_baseline", "learning_baseline_sha256", "approved_version_count"}
        if not set(patch) <= allowed or patch.get("status", "draft") not in LANDING_STATUSES:
            raise ValueError("Landing update is invalid")
        values, assignments = [], []
        for key, value in patch.items():
            if key == "approved_version_count":
                continue
            assignments.append(f"{key}=%s")
            values.append(Jsonb(value) if key in {"generation", "learning_baseline"} and value is not None else value)
        if not assignments:
            return self.get_page(landing_id)
        values.append(UUID(_uuid(landing_id, "landing_id")))
        with self.connection() as connection:
            if connection.execute(f"UPDATE landing_workspaces SET {','.join(assignments)},updated_at=clock_timestamp() WHERE entity_id=%s", values).rowcount != 1:
                raise KeyError(landing_id)
        return self.get_page(landing_id)

    def load_workspace_files(self, landing_id: str) -> tuple[str, dict[str, bytes]] | None:
        with self.connection() as connection:
            expected = connection.execute("SELECT state_sha256 FROM landing_workspaces WHERE entity_id=%s", (UUID(landing_id),)).fetchone()
            if expected is None:
                raise KeyError(landing_id)
            if expected[0] is None:
                return None
            rows = connection.execute("SELECT relative_path,content,content_sha256 FROM landing_workspace_files WHERE landing_id=%s", (UUID(landing_id),)).fetchall()
        files = {str(row[0]): bytes(row[1]) for row in rows}
        if any(hashlib.sha256(files[str(row[0])]).hexdigest() != row[2] for row in rows):
            raise RuntimeError("Landing database file digest mismatch")
        return str(expected[0]), files

    def persist_workspace_files(self, landing_id: str, root: Path, detail: Mapping[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        files = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"landing-workspace:{landing_id}",))
            connection.execute("UPDATE landing_workspaces SET state_sha256=%s,updated_at=clock_timestamp() WHERE entity_id=%s", (detail["state_sha256"], UUID(landing_id)))
            for relative, content in files.items():
                connection.execute("""INSERT INTO landing_workspace_files(landing_id,relative_path,content_sha256,content) VALUES(%s,%s,%s,%s)
                                      ON CONFLICT(landing_id,relative_path) DO UPDATE SET content_sha256=excluded.content_sha256,content=excluded.content,updated_at=clock_timestamp()""", (UUID(landing_id), relative, hashlib.sha256(content).hexdigest(), content))
            connection.execute("DELETE FROM landing_workspace_files WHERE landing_id=%s AND NOT(relative_path=ANY(%s))", (UUID(landing_id), list(files) or ["__none__"]))
            asset_ids: dict[str, str] = {}
            for relative, content in files.items():
                if not relative.startswith("assets/") or not relative.endswith(".history.json"):
                    continue
                slot = relative.removeprefix("assets/").removesuffix(".history.json")
                history = json.loads(content.decode("utf-8"))
                if slot not in {"hero_visual", "visual_break_visual"} or not isinstance(history, list):
                    raise RuntimeError("Landing persisted visual history is invalid")
                for item in history:
                    if not isinstance(item, Mapping) or not isinstance(item.get("sha256"), str):
                        raise RuntimeError("Landing persisted visual history is invalid")
                    digest = item["sha256"]
                    image = files.get(f"assets/{digest}.png")
                    if image is None or hashlib.sha256(image).hexdigest() != digest:
                        raise RuntimeError("Landing persisted visual asset digest mismatch")
                    existing = connection.execute("SELECT entity_id FROM landing_assets WHERE landing_id=%s AND content_sha256=%s", (UUID(landing_id), digest)).fetchone()
                    if existing is None:
                        asset_id = new_uuid7()
                        connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_asset',%s)", (UUID(asset_id), Jsonb({"schema_version": 1, "slot": slot, "content_sha256": digest})))
                        connection.execute("INSERT INTO landing_assets(entity_id,landing_id,slot,content_sha256,mime_type,content,source) VALUES(%s,%s,%s,%s,'image/png',%s,%s)", (UUID(asset_id), UUID(landing_id), slot, digest, image, Jsonb(sanitized(dict(item.get("source") or {})))))
                        self._edge(connection, landing_id, "contains", asset_id, {"member": "landing_asset", "slot": slot, "sha256": digest})
                    else:
                        asset_id = str(existing[0])
                    asset_ids[digest] = asset_id
            for version in detail["versions"]:
                record_path = root / "versions" / f"v{version['version']}.json"
                if record_path.is_file():
                    record = json.loads(record_path.read_text(encoding="utf-8"))
                    existing = connection.execute("SELECT entity_id FROM landing_versions WHERE landing_id=%s AND version=%s", (UUID(landing_id), version["version"])).fetchone()
                    if existing is None:
                        version_id = UUID(new_uuid7())
                        connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_version',%s)", (version_id, Jsonb({"schema_version": 1, "version": version["version"]})))
                        connection.execute("INSERT INTO landing_versions(entity_id,landing_id,version,version_sha256,state_sha256,record) VALUES(%s,%s,%s,%s,%s,%s)", (version_id, UUID(landing_id), version["version"], version["version_sha256"], version["state_sha256"], Jsonb(record)))
                        self._edge(connection, landing_id, "contains", str(version_id), {"member": "landing_version", "version": version["version"]})
                        for asset in record.get("assets", []):
                            if isinstance(asset, Mapping) and isinstance(asset.get("sha256"), str) and asset["sha256"] in asset_ids:
                                self._edge(connection, str(version_id), "derived_from", asset_ids[asset["sha256"]], {"input": "selected_landing_visual", "slot": asset.get("slot")})

    def record_generation_run(self, *, landing_id: str, stage: str, status: str, input_sha256: str, output_sha256: str | None, prompt_version: str, invocation: Mapping[str, Any] | None = None, error: Exception | None = None) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        if stage not in {"composition", "hero_visual", "visual_break_visual"} or status not in {"completed", "failed"}:
            raise ValueError("Landing generation run is invalid")
        run_id = new_uuid7()
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_generation_run',%s)", (UUID(run_id), Jsonb({"schema_version": 1, "stage": stage, "status": status})))
            connection.execute("INSERT INTO landing_generation_runs(entity_id,landing_id,stage,status,input_sha256,output_sha256,prompt_version,invocation,error_type,error_message) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (UUID(run_id), UUID(_uuid(landing_id, "landing_id")), stage, status, input_sha256, output_sha256, prompt_version, Jsonb(sanitized(dict(invocation or {}))), None if error is None else type(error).__name__, None if error is None else str(error)[:1000]))
            self._edge(connection, landing_id, "contains", run_id, {"member": "landing_generation_run", "stage": stage})
        return {"generation_run_id": run_id, "landing_id": landing_id, "stage": stage, "status": status}

    def ensure_skill(self, scope: str, project_id: str | None = None) -> dict[str, Any]:
        value = self.latest_skill(scope, project_id, missing_ok=True)
        return value if value is not None else self._append_skill(scope=scope, project_id=project_id, lesson=None, checkpoint_id=None)

    def latest_skill(self, scope: str, project_id: str | None = None, *, missing_ok: bool = False) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT entity_id,version,content,content_sha256,source_checkpoint_id,created_at FROM landing_skill_snapshots WHERE scope=%s AND project_id IS NOT DISTINCT FROM %s ORDER BY version DESC LIMIT 1", (scope, None if project_id is None else UUID(project_id))).fetchone()
        if row is None:
            return None if missing_ok else self.ensure_skill(scope, project_id)
        return {"skill_snapshot_id": str(row[0]), "scope": scope, "project_id": project_id, "version": int(row[1]), "content": row[2], "content_sha256": row[3], "source_checkpoint_id": None if row[4] is None else str(row[4]), "created_at": row[5].isoformat()}

    def _append_skill(self, *, scope: str, project_id: str | None, lesson: str | None, checkpoint_id: str | None) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        previous = self.latest_skill(scope, project_id, missing_ok=True)
        content = _landing_skill_document(scope, ([] if previous is None else _lessons(previous["content"])) + ([] if lesson is None else [_compact(lesson, "lesson", 8, 800)]))
        skill_id = new_uuid7()
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_skill_snapshot',%s)", (UUID(skill_id), Jsonb({"schema_version": 1, "scope": scope})))
            connection.execute("INSERT INTO landing_skill_snapshots(entity_id,scope,project_id,version,content,content_sha256,source_checkpoint_id) VALUES(%s,%s,%s,%s,%s,%s,%s)", (UUID(skill_id), scope, None if project_id is None else UUID(project_id), 1 if previous is None else previous["version"]+1, content, hashlib.sha256(content.encode()).hexdigest(), None if checkpoint_id is None else UUID(checkpoint_id)))
        return self.latest_skill(scope, project_id)  # type: ignore[return-value]

    def record_checkpoint(self, value: Mapping[str, Any]) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_edit_checkpoint',%s)", (UUID(value["checkpoint_id"]), Jsonb({"schema_version": 1, "kind": value["kind"]})))
            connection.execute("INSERT INTO landing_checkpoints(entity_id,landing_id,project_id,checkpoint_kind,before_state_sha256,after_state_sha256,changed_paths,before_snapshot,after_snapshot,version,status) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'completed')", (UUID(value["checkpoint_id"]), UUID(value["landing_id"]), UUID(value["project_id"]), value["kind"], value["before_state_sha256"], value["after_state_sha256"], Jsonb(value["changed_paths"]), Jsonb(value["before_snapshot"]), Jsonb(value["after_snapshot"]), value["version"]))
            self._edge(connection, value["landing_id"], "contains", value["checkpoint_id"], {"member": "landing_checkpoint"})
        return self.get_checkpoint(str(value["checkpoint_id"]))

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("SELECT landing_id,project_id,checkpoint_kind,before_state_sha256,after_state_sha256,changed_paths,before_snapshot,after_snapshot,version,created_at FROM landing_checkpoints WHERE entity_id=%s", (UUID(checkpoint_id),)).fetchone()
        if row is None:
            raise KeyError(checkpoint_id)
        return {"checkpoint_id": checkpoint_id, "landing_id": str(row[0]), "project_id": str(row[1]), "kind": row[2], "before_state_sha256": row[3], "after_state_sha256": row[4], "changed_paths": list(row[5]), "before_snapshot": dict(row[6]), "after_snapshot": dict(row[7]), "version": row[8], "status": "saved", "created_at": row[9].isoformat()}

    def record_learning_result(self, checkpoint_id: str, **patch: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        allowed = {"status", "edit_summary", "project_skill_snapshot_id", "error_type", "error_message"}
        if not set(patch) <= allowed:
            raise ValueError("Landing learning update is invalid")
        values, assignments = [], []
        for key, value in patch.items():
            assignments.append(f"{key}=%s")
            values.append(UUID(value) if key == "project_skill_snapshot_id" and value else value)
        values.append(UUID(checkpoint_id))
        with self.connection() as connection:
            connection.execute(f"UPDATE landing_checkpoints SET {','.join(assignments)} WHERE entity_id=%s", values)
        return self.get_checkpoint(checkpoint_id)

    def create_project_skill(self, *, project_id: str, lesson: str, checkpoint_id: str) -> dict[str, Any]:
        return self._append_skill(scope="project", project_id=project_id, lesson=lesson, checkpoint_id=checkpoint_id)

    def create_proposal(self, *, checkpoint_id: str, project_skill_snapshot_id: str, global_rule: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        proposal_id = new_uuid7()
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_learning_proposal',%s)", (UUID(proposal_id), Jsonb({"schema_version": 1})))
            connection.execute("INSERT INTO landing_learning_proposals(entity_id,checkpoint_id,project_skill_snapshot_id,global_rule,status) VALUES(%s,%s,%s,%s,'pending')", (UUID(proposal_id), UUID(checkpoint_id), UUID(project_skill_snapshot_id), global_rule))
        return {"proposal_id": proposal_id, "checkpoint_id": checkpoint_id, "project_skill_snapshot_id": project_skill_snapshot_id, "global_rule": global_rule, "status": "pending"}

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("SELECT checkpoint_id FROM landing_learning_proposals WHERE entity_id=%s", (UUID(proposal_id),)).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return {"proposal_id": proposal_id, "checkpoint_id": str(row[0])}

    def decide_proposal(self, proposal_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"apply_global", "keep_project"}:
            raise ValueError("Landing learning decision is invalid")
        with self.connection() as connection:
            row = connection.execute("SELECT checkpoint_id,global_rule,status FROM landing_learning_proposals WHERE entity_id=%s", (UUID(proposal_id),)).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if row[2] == "pending" and decision == "apply_global":
            self._append_skill(scope="global", project_id=None, lesson=row[1], checkpoint_id=str(row[0]))
        with self.connection() as connection:
            connection.execute("UPDATE landing_learning_proposals SET status=%s,decided_at=clock_timestamp() WHERE entity_id=%s AND status='pending'", (decision, UUID(proposal_id)))
        return {"proposal_id": proposal_id, "checkpoint_id": str(row[0]), "global_rule": row[1], "status": decision if row[2] == "pending" else row[2]}

    def recover_interrupted(self) -> list[str]:
        with self.connection() as connection:
            rows = connection.execute("SELECT entity_id FROM landing_workspaces WHERE status IN ('queued','composing','generating_images')").fetchall()
        return [str(row[0]) for row in rows]


class LandingService:
    """Coordinate a frozen Post design snapshot, bounded page AI, and page assets."""

    def __init__(self, *, root: Path | str, authority: Any, workspace_factory: Callable[[Path], Any], structured_provider: Any | None, composer_skill_path: Path, manual_agent_skill_path: Path | None = None) -> None:
        self.root = Path(root)
        self.pages_root = self.root / "pages"
        self.pages_root.mkdir(parents=True, exist_ok=True)
        self.authority = authority
        self.workspace_factory = workspace_factory
        self.structured_provider = structured_provider
        self.composer_skill = composer_skill_path.read_text(encoding="utf-8")
        self.manual_agent_skill = (
            manual_agent_skill_path.read_text(encoding="utf-8")
            if manual_agent_skill_path is not None else
            "Adjust only the supplied bounded Landing editor state. Never edit code, save, approve, or publish."
        )
        self.analytics: Any | None = None
        self._workspaces: dict[str, Any] = {}

    def templates(self) -> dict[str, Any]:
        return {
            "schema": "ptw.landing.template-catalog.v1",
            "items": [definition.summary() for definition in LANDING_TEMPLATE_REGISTRY.all()],
        }

    def _workspace(self, landing_id: str) -> Any:
        landing_id = _uuid(landing_id, "landing_id")
        self.authority.get_page(landing_id)
        if landing_id not in self._workspaces:
            self._workspaces[landing_id] = self.workspace_factory(self.pages_root / landing_id)
        return self._workspaces[landing_id]

    def source_versions(self, project_id: str) -> dict[str, Any]:
        return {"items": self.authority.source_versions(project_id), "next_cursor": None}

    def reserve_from_post(self, *, project_id: str, source_creative_id: str, source_version: int, requested_by: str, additional: bool = False) -> tuple[dict[str, Any], bool]:
        page, created = self.authority.create_page(project_id=project_id, source_creative_id=source_creative_id, source_version=source_version, requested_by=requested_by, additional=additional)
        if created:
            detail = self._workspace(page["landing_id"]).detail()
            self.authority.update_page(page["landing_id"], state_sha256=detail["state_sha256"], learning_baseline=_snapshot(detail), learning_baseline_sha256=sha256_json(_snapshot(detail)))
        return self.summary(page["landing_id"]), created

    def summary(self, landing_id: str) -> dict[str, Any]:
        return deepcopy(self.authority.get_page(landing_id))

    def list_pages(self, project_id: str) -> dict[str, Any]:
        return {"items": [self.summary(item["landing_id"]) for item in self.authority.list_pages(project_id)], "next_cursor": None}

    def detail(self, project_id: str, landing_id: str) -> dict[str, Any]:
        page = self.authority.get_page(landing_id)
        if page["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Landing was not found in this Project")
        return {**self._workspace(landing_id).detail(), **self.summary(landing_id)}

    def manual_agent_edit(
        self, project_id: str, landing_id: str, *, request_id: str,
        base_sha256: str, message: str, history: list[dict[str, str]],
        configuration: Mapping[str, Any], content: Mapping[str, Any],
        screenshots: list[bytes],
    ) -> dict[str, Any]:
        """Plan one bounded Landing editor turn without persisting the draft."""

        detail = self.detail(project_id, landing_id)
        if detail["status"] != "draft":
            raise ValueError("Studio Agent requires an editable Landing draft")
        if base_sha256 != detail["state_sha256"]:
            raise RuntimeError("Landing changed; reload before using Agent mode")
        editor_configuration = normalize_configuration(configuration)
        editor_content = normalize_content(content)
        agent_configuration = deepcopy(editor_configuration)
        effective_configuration_defaults = {
            "visual_mode": "phone",
            "phone_mockup": DEFAULT_PHONE_MOCKUP,
            "presentation": DEFAULT_PRESENTATION,
            "components": DEFAULT_COMPONENTS,
            "image_directions": DEFAULT_IMAGE_DIRECTIONS,
        }
        for field, default in effective_configuration_defaults.items():
            agent_configuration.setdefault(field, deepcopy(default))
        agent_content = deepcopy(editor_content)
        if "app_feature" not in agent_content:
            language = agent_configuration["presentation"]["language"]
            agent_content["app_feature"] = {
                "title": editor_content["features"][0]["title"][:APP_FEATURE_LIMITS["title"]],
                "description": editor_content["features"][0]["description"][:APP_FEATURE_LIMITS["description"]],
                "action_label": "Дізнатися більше" if language == "uk" else "Explore the app",
                "items": [{
                    "label": item["title"][:APP_FEATURE_LIMITS["label"]], "value": "",
                } for item in editor_content["features"]],
            }
        artifacts = screenshot_artifacts(screenshots)
        image_slots = list(LANDING_VISUAL_SLOTS) if detail.get("image_generation_available") else []
        current_images = [
            str(item["slot"]) for item in detail.get("assets", [])
            if item.get("available") and item.get("slot") in image_slots
        ]
        payload = manual_agent_payload(
            surface="landing:project_landing", entity_id=landing_id,
            message=message, history=history,
            configuration=agent_configuration, content=agent_content,
            catalog=detail["catalog"], screenshot_artifact_values=artifacts,
            image_slots=image_slots, current_images=current_images,
        )
        editable_values = manual_agent_editable_values(
            catalog=detail["catalog"], configuration=agent_configuration,
            content=agent_content,
        )

        def validate_response(value: Mapping[str, Any]) -> Mapping[str, Any]:
            if not isinstance(value, Mapping) or set(value) != {
                "edits", "image_actions", "reply",
            }:
                raise ValueError("Studio Agent Landing response fields are invalid")
            edited = apply_manual_agent_edits(
                value["edits"], current_values=editable_values,
                configuration=agent_configuration, content=agent_content,
            )
            expanded_configuration = normalize_configuration(edited["configuration"])
            next_configuration = deepcopy(expanded_configuration)
            for field, default in effective_configuration_defaults.items():
                if field not in editor_configuration and next_configuration[field] == default:
                    next_configuration.pop(field)
            expanded_content = normalize_content(edited["content"])
            next_content = deepcopy(expanded_content)
            if "app_feature" not in editor_content and next_content["app_feature"] == agent_content["app_feature"]:
                next_content.pop("app_feature")
            contact_fields = ("email", "phone", "url", "instagram")
            if any(
                next_content["contacts"].get(field, "") != editor_content["contacts"].get(field, "")
                for field in contact_fields
            ):
                raise ValueError("Studio Agent cannot invent or change contact endpoints")
            if next_content["social_proof"] != editor_content["social_proof"]:
                raise ValueError("Studio Agent cannot invent or change social proof")
            actions = validate_image_actions(
                value["image_actions"], slots=image_slots,
                screenshot_count=len(screenshots), available_slots=set(current_images),
            )
            directions = {
                "hero_visual": next_content["hero"]["visual_direction"],
                "visual_break_visual": next_content["visual_break"]["visual_direction"],
            }
            if any(action["visual_direction"] != directions[action["slot"]] for action in actions):
                raise ValueError("Studio Agent image action must use the matching Landing visual direction")
            validate_manual_agent_semantics(
                surface="landing:project_landing",
                constraints=payload["request_constraints"],
                configuration=expanded_configuration, content=expanded_content,
                image_actions=actions,
            )
            return {
                "configuration": next_configuration,
                "content": next_content,
                "image_actions": actions,
                "reply": response_reply(value["reply"]),
            }

        try:
            result = self._provider_call(
                mode="studio_manual_edit",
                system_prompt=(
                    self.manual_agent_skill
                    + "\n\nThe output schema accepts scalar patch operations only. Omitted paths remain unchanged; preserve contact endpoints and social proof exactly. "
                    "Decompose every clause, obey request_constraints as end-state invariants, resolve cross-control dependencies, "
                    "and verify every requested result against current_editable_values."
                ),
                input_payload=payload,
                output_schema=manual_agent_schema(
                    editable_paths=list(editable_values),
                    image_slots=image_slots, screenshot_count=len(screenshots),
                ),
                idempotency_key=f"landing-manual:{landing_id}:{request_id}",
                prompt_version=STUDIO_MANUAL_AGENT_PROMPT_VERSION,
                reasoning_effort=STUDIO_MANUAL_AGENT_REASONING_EFFORT,
                response_validator=validate_response,
                **({"input_artifacts": artifacts} if artifacts else {}),
            )
        except (RuntimeError, TimeoutError) as error:
            raise studio_manual_agent_provider_error(error) from error
        response = dict(result["response"])
        response["changed_paths"] = _diff_paths(
            {"configuration": editor_configuration, "content": editor_content},
            {"configuration": response["configuration"], "content": response["content"]},
        )
        response["owner_instruction"] = message
        response["request_id"] = request_id
        response["base_sha256"] = base_sha256
        return response

    def approved_version_detail(
        self, project_id: str, landing_id: str, version: int,
    ) -> dict[str, Any]:
        """Return one exact approved version with its generation provenance."""
        page = self.authority.get_page(landing_id)
        if page["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Landing was not found in this Project")
        record = self._workspace(landing_id).version_detail(version)
        return {
            **record,
            "landing_id": page["landing_id"],
            "project_id": page["project_id"],
            "template_id": LANDING_TEMPLATE_ID,
            "generation": deepcopy(page.get("generation") or {}),
        }

    def _provider_call(self, **kwargs: Any) -> dict[str, Any]:
        if self.structured_provider is None:
            raise RuntimeError("Landing structured provider is unavailable")
        validator = kwargs.pop("response_validator", None)
        reasoning_effort = kwargs.pop("reasoning_effort", None)
        if not callable(validator):
            raise ValueError("Landing structured calls require a domain response validator")
        if hasattr(self.structured_provider, "call"):
            if hasattr(self.structured_provider, "supported_reasoning_efforts"):
                kwargs["reasoning_effort"] = reasoning_effort
            return self.structured_provider.call(**kwargs, response_validator=validator)
        value = self.structured_provider.generate(**kwargs)
        return value if validator is None else {**value, "response": dict(validator(value["response"]))}

    @staticmethod
    def _style_snapshot(page: Mapping[str, Any]) -> dict[str, Any]:
        source = dict(page["source_post_snapshot"])
        return {
            "template_id": source["template_id"], "configuration": source["configuration"],
            "content": source["content"], "generation": source.get("generation", {}),
            "assets": source.get("assets", []), "version_sha256": source["version_sha256"],
        }

    def _image_context(self, page: Mapping[str, Any], slot: str, direction: str,
                       configuration: Mapping[str, Any], *, base_sha256: str,
                       enhance_current: bool = False, reference_image: bytes | None = None,
                       instruction: Mapping[str, Any] | None = None,
                       changed_image_settings: list[str] | None = None) -> dict[str, Any]:
        if slot not in LANDING_VISUAL_SLOTS:
            raise ValueError("Landing visual slot is invalid")
        config = normalize_configuration(configuration)
        workspace = self._workspace(str(page["landing_id"]))
        history = workspace._history(slot)
        previous = next((item.get("source") or {} for item in history
                         if item["sha256"] == workspace._selected(slot)), {})
        if not previous and instruction is None:
            initial = (page.get("generation") or {}).get("subject_suggestions", {}).get(slot)
            if initial == direction:
                instruction = {"origin": "generated"}
            else:
                # A stored legacy description is context, not evidence of authorship.
                field = "hero" if slot == "hero_visual" else "visual_break"
                previous = {"visual_direction": workspace._content()[field]["visual_direction"]}
        selected = config.get("image_directions", DEFAULT_IMAGE_DIRECTIONS)[slot]
        skills = self.analytics.active_skills(str(page["project_id"])) if self.analytics else {}
        return build_image_context(
            direction=direction, instruction=resolve_instruction(direction, requested=instruction, previous=previous),
            brief=self.authority.brief(str(page["source_brief_id"])),
            settings={**selected, "palette": {k: v for k, v in config["theme"].items() if k.endswith("_color")}},
            destination={"surface": "landing", "template_id": page.get("template_id"),
                         "slot": slot, "mode": config.get("visual_mode", "phone") if slot == "hero_visual" else "image",
                         "presentation": config.get("presentation", {}),
                         "crop": {"fit": "cover", "focus": config.get("presentation", {}).get("hero_focus" if slot == "hero_visual" else "visual_break_focus", {"x": 50, "y": 50}),
                                  "height": config.get("visual_break", {}).get("height") if slot == "visual_break_visual" else None,
                                  "responsive": True},
                         "phone_mockup": config.get("phone_mockup", {}) if slot == "hero_visual" else {}},
            operation="uploaded_reference" if reference_image is not None else "enhance_current" if enhance_current else "generate_new",
            base_sha256=base_sha256, lessons=compact_active_skills(skills, surface="landing"),
            previous=previous if enhance_current else None, changed_settings=changed_image_settings,
        )

    def _image_prompt(self, page: Mapping[str, Any], slot: str, direction: str, configuration: Mapping[str, Any] | None = None) -> str:
        return compile_image_prompt(self._image_context(page, slot, direction, configuration or DEFAULT_CONFIGURATION,
                                                       base_sha256=self._workspace(str(page["landing_id"])).state_sha256()))

    def _record_generation(self, **value: Any) -> None:
        recorder = getattr(self.authority, "record_generation_run", None)
        if callable(recorder):
            recorder(**value)

    def _synchronize_workspace(self, landing_id: str, workspace: Any) -> None:
        synchronizer = getattr(self.authority, "synchronize_workspace", None)
        if callable(synchronizer):
            synchronizer(landing_id, workspace)

    def generate(self, landing_id: str) -> dict[str, Any]:
        page = self.authority.get_page(landing_id)
        if page["status"] == "draft":
            return self.summary(landing_id)
        brief = self.authority.brief(page["source_brief_id"])
        if not brief.get("approved") or not brief.get("document"):
            raise ValueError("Landing generation requires an approved complete Product Brief")
        workspace = self._workspace(landing_id)
        detail = workspace.detail()
        skills = (
            self.analytics.active_skills(str(page["project_id"]))
            if self.analytics is not None else
            {"project": None, "global": None, "precedence": [
                "catalog_brand_and_brief", "explicit_owner_direction",
                "project_rules", "global_spirit", "template_defaults",
            ]}
        )
        project_skill, global_skill = skills["project"], skills["global"]
        skill_provenance = {
            "project_skill_snapshot_id": None if project_skill is None else project_skill["skill_snapshot_id"],
            "project_skill_sha256": None if project_skill is None else project_skill["rules_sha256"],
            "global_skill_snapshot_id": None if global_skill is None else global_skill["skill_snapshot_id"],
            "global_skill_sha256": None if global_skill is None else global_skill["rules_sha256"],
        }
        self.authority.update_page(
            landing_id, status="composing",
            generation={"stage": "composing", **skill_provenance},
        )
        payload = landing_composition_payload(
            landing_id=landing_id,
            approved_product_brief=brief["document"],
            source_post_snapshot=page["source_post_snapshot"],
            content_defaults={
                **detail["content"],
                "app_feature": detail["content"].get("app_feature", DEFAULT_APP_FEATURE),
            },
            active_creative_skills=skills,
            live_landing_catalog=detail["catalog"],
        )
        stage = "composition"
        stage_input = sha256_json(payload)
        try:
            result = self._provider_call(
                mode="studio_creative_generation", system_prompt=self.composer_skill,
                input_payload=payload, output_schema=landing_generation_schema(),
                idempotency_key=f"landing-page:{landing_id}", prompt_version=LANDING_COMPOSER_PROMPT_VERSION,
                response_validator=validate_landing_composition,
            )
            self._record_generation(landing_id=landing_id, stage="composition", status="completed", input_sha256=stage_input, output_sha256=sha256_json(result["response"]), prompt_version=LANDING_COMPOSER_PROMPT_VERSION, invocation=sanitized(result.get("invocation") or {}))
            composed = workspace.save_configuration(
                base_sha256=detail["state_sha256"],
                configuration=detail["configuration"],
                content=result["response"]["content"],
            )
            self.authority.update_page(landing_id, status="generating_images", state_sha256=composed["state_sha256"], generation={"stage": "generating_images", "subject_suggestions": {"hero_visual": composed["content"]["hero"]["visual_direction"], "visual_break_visual": composed["content"]["visual_break"]["visual_direction"]}, **skill_provenance, "composition": sanitized(result.get("invocation") or {})})
            for slot, direction in (("hero_visual", composed["content"]["hero"]["visual_direction"]), ("visual_break_visual", composed["content"]["visual_break"]["visual_direction"])):
                context = self._image_context(page, slot, direction, composed["configuration"],
                                              base_sha256=composed["state_sha256"], instruction={"origin": "generated"})
                stage, prompt = slot, compile_image_prompt(context)
                stage_input = sha256_json({"base_sha256": composed["state_sha256"], "slot": slot, "visual_direction": direction, "prompt": prompt})
                composed = workspace.generate_visual(base_sha256=composed["state_sha256"], slot=slot, visual_direction=direction, prompt=prompt, image_context=context)
                self._record_generation(landing_id=landing_id, stage=slot, status="completed", input_sha256=stage_input, output_sha256=composed["state_sha256"], prompt_version=IMAGE_POLICY_VERSION, invocation={"enhance_current": False, **image_provenance(context)})
            self._synchronize_workspace(landing_id, workspace)
            baseline = _snapshot(composed)
            self.authority.update_page(landing_id, status="draft", state_sha256=composed["state_sha256"], generation={"stage": "draft", **skill_provenance, "composition": sanitized(result.get("invocation") or {})}, learning_baseline=baseline, learning_baseline_sha256=sha256_json(baseline))
        except Exception as error:
            self._synchronize_workspace(landing_id, workspace)
            self._record_generation(landing_id=landing_id, stage=stage, status="failed", input_sha256=stage_input, output_sha256=None, prompt_version=LANDING_COMPOSER_PROMPT_VERSION if stage == "composition" else IMAGE_POLICY_VERSION, error=error)
            self.authority.update_page(landing_id, status="failed", generation={**(self.authority.get_page(landing_id).get("generation") or {}), "stage": "failed", "error_type": type(error).__name__, "error_message": str(error)[:1000]})
        return self.summary(landing_id)

    def retry_generation(self, project_id: str, landing_id: str) -> dict[str, Any]:
        detail = self.detail(project_id, landing_id)
        if detail["status"] != "failed":
            raise ValueError("only a failed Landing can be retried")
        generation = {
            key: deepcopy(item) for key, item in dict(detail.get("generation") or {}).items()
            if key not in {"error_type", "error_message"}
        }
        return self.authority.update_page(
            landing_id, status="queued", generation={**generation, "stage": "queued"},
        )

    def mutate(self, project_id: str, landing_id: str, method: str, **kwargs: Any) -> dict[str, Any]:
        self.detail(project_id, landing_id)
        workspace = self._workspace(landing_id)
        before = workspace.detail()
        reference_digest = hashlib.sha256(kwargs["reference_image"]).hexdigest() if kwargs.get("reference_image") is not None else None
        if method == "generate_visual":
            # Build from the same persisted configuration used by the digest guard.
            kwargs["image_context"] = self._image_context(
                self.authority.get_page(landing_id), kwargs["slot"], kwargs["visual_direction"],
                before["configuration"], base_sha256=before["state_sha256"],
                enhance_current=kwargs.get("enhance_current", False), reference_image=kwargs.get("reference_image"),
                instruction=kwargs.pop("instruction_context", None),
                changed_image_settings=kwargs.pop("changed_image_settings", None),
            )
            kwargs["prompt"] = compile_image_prompt(kwargs["image_context"])
        try:
            result = getattr(workspace, method)(**kwargs)
        except Exception as error:
            if method == "generate_visual" and kwargs.get("slot") in LANDING_VISUAL_SLOTS:
                self._record_generation(landing_id=landing_id, stage=str(kwargs.get("slot")), status="failed", input_sha256=sha256_json({"base_sha256": before["state_sha256"], "slot": kwargs.get("slot"), "visual_direction": kwargs.get("visual_direction"), "prompt": kwargs.get("prompt"), "reference_image_sha256": reference_digest}), output_sha256=None, prompt_version=IMAGE_POLICY_VERSION, invocation={**image_provenance(kwargs["image_context"]), "enhance_current": bool(kwargs.get("enhance_current", False)), **({"reference_image_sha256": reference_digest} if reference_digest else {})}, error=error)
            raise
        if method == "generate_visual" and kwargs.get("slot") in LANDING_VISUAL_SLOTS:
            self._record_generation(landing_id=landing_id, stage=str(kwargs["slot"]), status="completed", input_sha256=sha256_json({"base_sha256": before["state_sha256"], "slot": kwargs["slot"], "visual_direction": kwargs["visual_direction"], "prompt": kwargs["prompt"], "reference_image_sha256": reference_digest}), output_sha256=result["state_sha256"], prompt_version=IMAGE_POLICY_VERSION, invocation={**image_provenance(kwargs["image_context"]), "enhance_current": bool(kwargs.get("enhance_current", False)), **({"reference_image_sha256": reference_digest} if reference_digest else {})})
        self._synchronize_workspace(landing_id, workspace)
        self.authority.update_page(landing_id, state_sha256=result["state_sha256"])
        return {**result, **self.summary(landing_id)}

    def checkpoint(self, project_id: str, landing_id: str, *, kind: str, base_sha256: str, configuration: Mapping[str, Any], content: Mapping[str, Any], change_note: str = "") -> dict[str, Any]:
        if kind not in {"save", "approve"}:
            raise ValueError("Landing checkpoint kind is invalid")
        page = self.authority.get_page(landing_id)
        if page["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Landing was not found in this Project")
        workspace = self._workspace(landing_id)
        current = workspace.detail()
        if base_sha256 != current["state_sha256"]:
            raise RuntimeError("Landing changed; reload before saving")
        pending = canonical_json(configuration) != canonical_json(current["configuration"]) or canonical_json(content) != canonical_json(current["content"])
        version_created = False
        if kind == "approve":
            versions = current["versions"]
            if pending or not versions or versions[-1]["state_sha256"] != current["state_sha256"]:
                current = workspace.approve_configuration(base_sha256=base_sha256, configuration=configuration, content=content, change_note=change_note)
                version_created = True
            else:
                workspace.approval_ready(current)
        elif pending:
            current = workspace.save_configuration(base_sha256=base_sha256, configuration=configuration, content=content)
        after = _snapshot(current)
        before = page.get("learning_baseline") or after
        before_sha, after_sha = sha256_json(before), sha256_json(after)
        self._synchronize_workspace(landing_id, workspace)
        self.authority.update_page(landing_id, state_sha256=current["state_sha256"], approved_version_count=len(current["versions"]))
        if before_sha == after_sha:
            return {"landing": {**current, **self.summary(landing_id)}, "checkpoint_created": False, "version_created": version_created, "checkpoint": None, "learning_proposal": None}
        checkpoint = self.authority.record_checkpoint({
            "checkpoint_id": new_uuid7(), "landing_id": landing_id, "project_id": project_id, "kind": kind,
            "before_state_sha256": before_sha, "after_state_sha256": after_sha, "changed_paths": _diff_paths(before, after),
            "before_snapshot": before, "after_snapshot": after, "status": "completed", "version": len(current["versions"]) if kind == "approve" else None, "created_at": utc_now(),
        })
        self.authority.update_page(landing_id, learning_baseline=after, learning_baseline_sha256=after_sha)
        return {"landing": {**current, **self.summary(landing_id)}, "checkpoint_created": True, "version_created": version_created, "checkpoint": {**checkpoint, "status": "saved"}, "learning_proposal": None}

    def recover_interrupted(self) -> list[str]:
        """Return only pages whose initial composition did not reach a draft."""
        return list(self.authority.recover_interrupted())
