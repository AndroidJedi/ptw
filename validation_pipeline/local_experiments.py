"""Local Product Brief -> Universal candidates -> critic -> learning workflow."""

from __future__ import annotations

import base64
from copy import deepcopy
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import threading
from typing import Any, Mapping, Sequence
from uuid import UUID
import zipfile

from commander.ids import new_uuid7

from .content import (
    HARD_GATES, SLIDER_NAMES, TEMPLATE_IDS, CandidateV2, StrategyTemplate,
    TemplateRegistry, critic_output_schema, final_eligible, validate_critic_response,
)
from .domain import (
    ProductBriefV1, RATING_PATTERN, TESTIMONIAL_PATTERN, UNSUPPLIED_PROOF_PATTERN,
    infer_language, product_brief_schema,
)
from .images import PexelsClient
from .local_codex import LocalCodexStructuredProvider, sanitized
from .local_experiment_store import LocalExperimentStore, sha256_json, utc_now
from .service import load_product_brief_skill, product_brief_system_prompt
from .studio import inspect_media
from .studio_universal import (
    SEMANTIC_ROLES, UNIVERSAL_AD_CONTENT_SCHEMA, normalize_universal_config,
    normalize_universal_content, universal_content_from_generation,
)
from .studio_workspace import UniversalStudioWorkspace
from .universal_experiment import (
    PHOTO_FALLBACK_PATCHES, PHOTO_STRATEGIES, PROFILE_ID, STRATEGY_PATCHES,
    audit_universal_render, deterministic_analysis_jpeg, deterministic_jpeg,
    resolve_strategy_patch,
)


LOCAL_TASK = "Create one Instagram-square validation post from the approved Product Brief."
LOCAL_OUTPUT_PROFILE = "instagram_static_ad_v1"
LOCAL_CANDIDATE_SCHEMA = "ptw.local-universal-candidate.v1"
LOCAL_VISUAL_ROLES = tuple(SEMANTIC_ROLES)
LESSON_TARGETS = (
    "product-brief-generator", "content-candidate-generator",
    "content-result-critic", "universal_ad_layout_policy",
)
COPY_ELEMENT_SLOTS = (
    "hook", "headline", "primary_text", "supporting_text", "offer", "cta",
    "caption", "alt_text", "desired_emotion", "visual_concept", "media_request",
)


def _uuid(value: Any, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a UUID") from error


def _compact(value: Any, label: str, minimum: int, maximum: int) -> str:
    result = " ".join(str(value or "").split())
    if not minimum <= len(result) <= maximum:
        raise ValueError(f"{label} must contain {minimum}-{maximum} characters")
    return result


def _candidate_schema(asset_id: str | None) -> dict[str, Any]:
    text = {"type": "string", "minLength": 1}
    return {
        "type": "object", "additionalProperties": False,
        "required": [
            "schema_version", "hook", "headline", "primary_text", "supporting_text",
            "offer", "cta", "caption", "alt_text", "desired_emotion", "visual_concept",
            "media_request", "visual_components",
        ],
        "properties": {
            "schema_version": {"type": "integer", "const": 2},
            **{key: text for key in (
                "hook", "headline", "primary_text", "supporting_text", "offer", "cta",
                "caption", "alt_text", "desired_emotion", "visual_concept",
            )},
            "media_request": {
                "type": "object", "additionalProperties": False,
                "required": ["kind", "query", "source_asset_id", "reason"],
                "properties": {
                    "kind": {"type": "string", "const": "approved_asset" if asset_id else "none"},
                    "query": {"type": "string"},
                    "source_asset_id": {"type": ["string", "null"], "enum": [asset_id]},
                    "reason": text,
                },
            },
            "visual_components": {
                "type": "array", "minItems": len(LOCAL_VISUAL_ROLES),
                "maxItems": len(LOCAL_VISUAL_ROLES),
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["role", "content", "source_ids"],
                    "properties": {
                        "role": {"type": "string", "enum": list(LOCAL_VISUAL_ROLES)},
                        "content": text,
                        "source_ids": {
                            "type": "array", "items": {"type": "string", "enum": [] if asset_id is None else [asset_id]},
                        },
                    },
                },
            },
        },
    }


def _validate_local_candidate(
    value: Mapping[str, Any], *, brief: Mapping[str, Any], asset_id: str | None,
) -> dict[str, Any]:
    expected = {
        "schema_version", "hook", "headline", "primary_text", "supporting_text",
        "offer", "cta", "caption", "alt_text", "desired_emotion", "visual_concept",
        "media_request", "visual_components",
    }
    if set(value) != expected or value.get("schema_version") != 2:
        raise ValueError("local Universal candidate fields do not match v1")
    limits = {
        "hook": 240, "headline": 140, "primary_text": 280, "supporting_text": 280,
        "offer": 160, "cta": 60, "caption": 2200, "alt_text": 1000,
        "desired_emotion": 160, "visual_concept": 1200,
    }
    result: dict[str, Any] = {"schema_version": 2}
    for key, maximum in limits.items():
        result[key] = _compact(value[key], key, 1, maximum)
        if (
            TESTIMONIAL_PATTERN.search(result[key])
            or RATING_PATTERN.search(result[key])
            or UNSUPPLIED_PROOF_PATTERN.search(result[key])
        ):
            raise ValueError(f"{key} contains fabricated proof")
    if result["offer"] != brief["offer"] or result["cta"] != brief["cta"]:
        raise ValueError("candidate must preserve the Product Brief offer and CTA byte-for-byte")
    media = value.get("media_request")
    if not isinstance(media, Mapping) or set(media) != {"kind", "query", "source_asset_id", "reason"}:
        raise ValueError("candidate media request fields do not match v1")
    expected_kind = "approved_asset" if asset_id else "none"
    if media.get("kind") != expected_kind or media.get("source_asset_id") != asset_id:
        raise ValueError("candidate must use only its isolated server-assigned asset policy")
    result["media_request"] = {
        "kind": expected_kind, "query": str(media.get("query") or "")[:300],
        "source_asset_id": asset_id,
        "reason": _compact(media.get("reason"), "media_request.reason", 1, 500),
    }
    raw_components = value.get("visual_components")
    if not isinstance(raw_components, list) or len(raw_components) != len(LOCAL_VISUAL_ROLES):
        raise ValueError("Universal candidate requires exactly eight visual roles")
    if [item.get("role") for item in raw_components if isinstance(item, Mapping)] != list(LOCAL_VISUAL_ROLES):
        raise ValueError("Universal candidate visual roles must use the stable canonical order")
    components: list[dict[str, Any]] = []
    for index, item in enumerate(raw_components):
        if not isinstance(item, Mapping) or set(item) != {"role", "content", "source_ids"}:
            raise ValueError("Universal candidate visual component fields do not match v1")
        sources = list(item["source_ids"])
        if any(source != asset_id for source in sources) or (asset_id is None and sources):
            raise ValueError("Universal candidate visual component references an unauthorized asset")
        components.append({
            "role": str(item["role"]),
            "content": _compact(item["content"], f"visual_components[{index}].content", 1, 1000),
            "source_ids": sources,
        })
    result["visual_components"] = components
    return result


def _short_alt_value(value: Any, maximum: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= maximum:
        return text
    shortened = text[:maximum - 1].rsplit(" ", 1)[0].rstrip(".,;:—-")
    return f"{shortened or text[:maximum - 1]}…"


def _render_aligned_document(
    document: Mapping[str, Any], *, content: Mapping[str, Any],
    configuration: Mapping[str, Any], render_contract: Mapping[str, Any],
    language: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Bind semantic descriptions to the exact optional roles that render."""

    result = deepcopy(dict(document))
    bullets = list(content["bullets"]) if configuration["bullets"]["enabled"] else []
    logo = render_contract["logo"]
    sticker = render_contract["sticker"]
    replacements = {
        "bullet_list": (
            "Visible bullet list: " + "; ".join(map(str, bullets))
            if bullets else "No bullet list is rendered in this strategy."
        ),
        "logo": (
            "The saved canonical Natal logo is visibly rendered from the captured Studio export."
            if logo["visible"] else "No logo is rendered in this strategy."
        ),
        "sticker": (
            "A saved approved sticker asset is visibly rendered."
            if sticker["visible"] else "No sticker is rendered in this strategy."
        ),
    }
    components: list[dict[str, Any]] = []
    transformations: list[dict[str, Any]] = []
    for raw in result["visual_components"]:
        component = deepcopy(dict(raw))
        replacement = replacements.get(str(component["role"]))
        if replacement is not None and component["content"] != replacement:
            transformations.append({
                "field": f"visual_components.{component['role']}.content",
                "before": component["content"], "after": replacement,
            })
            component["content"] = replacement
        components.append(component)
    result["visual_components"] = components

    background = render_contract["background"]
    if language == "uk":
        background_text = (
            "схвалене фотографічне тло"
            if background["mode"] == "image"
            else f"текстуроване тло «{background.get('texture') or background['mode']}»"
        )
        parts = [
            f"Квадратна реклама для Instagram; {background_text}.",
            f"Заголовок: «{_short_alt_value(content['hero_title'], 180)}».",
            f"Пояснення: «{_short_alt_value(content['supporting_text'], 260)}».",
        ]
        if bullets:
            parts.append("Видимі пункти: " + "; ".join(map(str, bullets)) + ".")
        parts.extend([
            f"Пропозиція: «{content['offer']}».", f"Кнопка: «{content['cta']}».",
        ])
        if logo["visible"]:
            parts.append("Видно збережений логотип Natal.")
        if sticker["visible"]:
            parts.append("Видно схвалений декоративний об’єкт.")
    else:
        background_text = (
            "an approved photographic background"
            if background["mode"] == "image"
            else f"a {background.get('texture') or background['mode']} textured background"
        )
        parts = [
            f"Square Instagram ad with {background_text}.",
            f"Headline: “{_short_alt_value(content['hero_title'], 180)}”.",
            f"Supporting text: “{_short_alt_value(content['supporting_text'], 260)}”.",
        ]
        if bullets:
            parts.append("Visible points: " + "; ".join(map(str, bullets)) + ".")
        parts.extend([
            f"Offer: “{content['offer']}”.", f"Button: “{content['cta']}”.",
        ])
        if logo["visible"]:
            parts.append("The saved Natal logo is visible.")
        if sticker["visible"]:
            parts.append("An approved decorative object is visible.")
    alt_text = " ".join(parts)
    if len(alt_text) > 1000:
        raise ValueError("deterministic Universal alt text exceeds 1000 characters")
    if result["alt_text"] != alt_text:
        transformations.append({
            "field": "alt_text", "before": result["alt_text"], "after": alt_text,
        })
        result["alt_text"] = alt_text
    return result, transformations


class LocalExperimentService:
    """Durable local orchestration. All model effects cross the injected provider."""

    def __init__(
        self, *, store: LocalExperimentStore, workspace: UniversalStudioWorkspace,
        provider: LocalCodexStructuredProvider, repository_root: Path,
        pexels: PexelsClient | None = None,
    ) -> None:
        self.store = store
        self.workspace = workspace
        self.provider = provider
        self.repository_root = repository_root
        self.pexels = pexels
        self._execution_lock = threading.RLock()
        self.product_skill_path = repository_root / "skills/product-brief-generator/SKILL.md"
        self.generator_skill_path = repository_root / "skills/content-candidate-generator/SKILL.md"
        self.critic_skill_path = repository_root / "skills/content-result-critic/SKILL.md"
        reference_root = self.generator_skill_path.parent / "references"
        self.templates = TemplateRegistry(reference_root / "templates").load_active()
        self.templates_by_id = {item.template_id: item for item in self.templates}
        self.generator_context = self._read_context((
            self.generator_skill_path,
            reference_root / "writing-principles.md",
            reference_root / "anti-patterns.md",
            reference_root / "techniques/ad-copy.md",
            reference_root / "owner-lessons.md",
        ))
        self.critic_context = self._read_context((
            self.critic_skill_path,
            self.critic_skill_path.parent / "references/evaluation-contract.md",
            self.critic_skill_path.parent / "references/owner-lessons.md",
            reference_root / "writing-principles.md",
            reference_root / "anti-patterns.md",
        ))
        self.product_context = load_product_brief_skill(self.product_skill_path)

    @staticmethod
    def _read_context(paths: Sequence[Path]) -> str:
        values: list[str] = []
        for path in paths:
            if not path.is_file():
                raise RuntimeError(f"required local skill context is unavailable: {path}")
            values.append(f"REFERENCE {path.name}:\n{path.read_text(encoding='utf-8')}")
        return "\n\n".join(values)

    def _record_invocation(
        self, *, target_id: str, mode: str, input_payload: Mapping[str, Any],
        response: Mapping[str, Any] | None, invocation: Mapping[str, Any] | None,
        error: Exception | None = None,
    ) -> str:
        invocation_id = new_uuid7()
        value = {
            "invocation_id": invocation_id, "target_id": target_id, "mode": mode,
            "input": sanitized(input_payload), "input_sha256": sha256_json(sanitized(input_payload)),
            "response": None if response is None else sanitized(response),
            "response_sha256": None if response is None else sha256_json(response),
            "provenance": sanitized(invocation or {}),
            "status": "failed" if error else "completed",
            "error_type": None if error is None else type(error).__name__,
            "created_at": utc_now(),
        }
        self.store.append("provider_invocations", invocation_id, value)
        self.store.edge(source_id=target_id, relation="used_provider_invocation", target_id=invocation_id)
        return invocation_id

    def _provider_call(self, *, target_id: str, mode: str, **kwargs: Any) -> dict[str, Any]:
        payload = dict(kwargs["input_payload"])
        try:
            result = self.provider.call(mode=mode, **kwargs)
        except Exception as error:
            provenance = {"attempts": getattr(error, "attempts", [])}
            self._record_invocation(
                target_id=target_id, mode=mode, input_payload=payload,
                response=None, invocation=provenance, error=error,
            )
            raise
        invocation_id = self._record_invocation(
            target_id=target_id, mode=mode, input_payload=payload,
            response=result["response"], invocation=result["invocation"],
        )
        return {**result, "invocation_id": invocation_id}

    # Projects and Product Briefs -------------------------------------------------

    def _project(self, project_id: str) -> dict[str, Any]:
        value = self.store.get("projects", _uuid(project_id, "project_id"))
        briefs = [item for item in self.store.list("briefs") if item["project_id"] == project_id]
        runs = [item for item in self.store.list("runs") if item["project_id"] == project_id]
        latest = briefs[0] if briefs else None
        return {
            **value,
            "latest_brief_id": None if latest is None else latest["brief_id"],
            "latest_brief_status": None if latest is None else latest["status"],
            "brief_count": len(briefs), "result_run_count": len(runs),
            "result_creation_enabled": any(item.get("approved") for item in briefs),
        }

    def list_projects(self, limit: int = 100) -> list[dict[str, Any]]:
        return [self._project(item["project_id"]) for item in self.store.list("projects")[:limit]]

    def rename_project(self, project_id: str, name: str) -> dict[str, Any]:
        project = self._project(project_id)
        updated = {
            **{key: value for key, value in project.items() if key not in {
                "latest_brief_id", "latest_brief_status", "brief_count",
                "result_run_count", "result_creation_enabled",
            }},
            "name": _compact(name, "Project name", 1, 160),
            "name_source": "owner", "updated_at": utc_now(),
        }
        self.store.append("projects", project_id, updated)
        return self._project(project_id)

    def create_brief(self, *, request_id: str, raw_idea: str, requested_by: str) -> tuple[dict[str, Any], dict[str, Any], bool]:
        request_id = _uuid(request_id, "request_id")
        raw_idea = _compact(raw_idea, "raw_idea", 1, 10_000)
        project_id, created = self.store.reserve_request(
            scope="brief-create", request_id=request_id,
            fingerprint={"request_id": request_id, "raw_idea": raw_idea},
        )
        if not created:
            project = self._project(project_id)
            brief = next(item for item in self.store.list("briefs") if item["request_id"] == request_id)
            return project, brief, False
        source_id, brief_id = new_uuid7(), new_uuid7()
        now = utc_now()
        project = {
            "project_id": project_id, "request_id": request_id,
            "owner_idea_source_id": source_id, "name": raw_idea[:80],
            "name_source": "raw_idea", "requested_by": requested_by,
            "created_at": now, "updated_at": now,
        }
        source = {
            "source_id": source_id, "project_id": project_id, "kind": "owner_idea",
            "content": raw_idea, "sha256": hashlib.sha256(raw_idea.encode()).hexdigest(),
            "created_at": now,
        }
        brief = {
            "brief_id": brief_id, "project_id": project_id, "project_name": project["name"],
            "request_id": request_id, "owner_idea_source_id": source_id,
            "raw_idea": raw_idea, "base_brief_id": None, "feedback_id": None,
            "status": "queued", "document": None, "document_sha256": None,
            "failure_count": 0, "approved": False, "created_at": now,
            "updated_at": now,
        }
        self.store.append("projects", project_id, project)
        self.store.append("sources", source_id, source)
        self.store.append("briefs", brief_id, brief)
        self.store.edge(source_id=project_id, relation="contains", target_id=source_id)
        self.store.edge(source_id=brief_id, relation="derived_from", target_id=source_id)
        return self._project(project_id), brief, True

    def generate_brief(self, brief_id: str) -> dict[str, Any]:
        brief = self.store.get("briefs", _uuid(brief_id, "brief_id"))
        if brief["status"] not in {"queued", "failed"}:
            return brief
        generating = {**brief, "status": "generating", "updated_at": utc_now()}
        self.store.append("briefs", brief_id, generating)
        required_language = infer_language(brief["raw_idea"])
        base = None
        correction = None
        mode = "product_brief"
        if brief.get("base_brief_id"):
            base = self.store.get("briefs", brief["base_brief_id"])["document"]
            correction = self.store.get("feedback", brief["feedback_id"])["comment"]
            mode = "product_brief_revision"
        payload = {
            "brief_id": brief_id, "raw_idea": brief["raw_idea"],
            "required_language": required_language, "base_brief": base,
            "owner_correction": correction,
        }
        try:
            result = self._provider_call(
                target_id=brief_id, mode=mode,
                system_prompt=(
                    product_brief_system_prompt(self.product_context, required_language)
                    + "\n\nACTIVE_LOCAL_OWNER_LESSONS:\n"
                    + json.dumps(
                        self._active_lesson_texts("product-brief-generator"),
                        ensure_ascii=False,
                    )
                ),
                input_payload=payload, output_schema=product_brief_schema(required_language),
                idempotency_key=f"{brief_id}:{mode}", prompt_version=f"local-product-brief-v1:{mode}",
                response_validator=lambda value: ProductBriefV1.from_dict(
                    value, raw_idea=brief["raw_idea"],
                ).to_dict(),
            )
            document = ProductBriefV1.from_dict(result["response"], raw_idea=brief["raw_idea"])
            completed = {
                **generating, "status": "completed", "document": document.to_dict(),
                "document_sha256": document.digest, "quality_gates": document.quality_gates,
                "provider_invocation_id": result["invocation_id"], "updated_at": utc_now(),
                **document.to_dict(),
            }
            self.store.append("briefs", brief_id, completed)
            project = self.store.get("projects", brief["project_id"])
            if project["name_source"] != "owner":
                self.store.append("projects", brief["project_id"], {
                    **project, "name": document.to_dict()["product"],
                    "name_source": "product_brief", "updated_at": utc_now(),
                })
            return self.store.get("briefs", brief_id)
        except Exception as error:
            failed = {
                **generating, "status": "failed", "failure_count": int(brief["failure_count"]) + 1,
                "error_code": type(error).__name__, "error_message": str(error)[:1000],
                "updated_at": utc_now(),
            }
            self.store.append("briefs", brief_id, failed)
            return failed

    def list_briefs(self, project_id: str | None, limit: int = 100) -> list[dict[str, Any]]:
        if project_id is not None:
            project_id = _uuid(project_id, "project_id")
        values = [item for item in self.store.list("briefs") if project_id is None or item["project_id"] == project_id]
        for item in values:
            item["project_name"] = self._project(item["project_id"])["name"]
        return values[:limit]

    def get_brief(self, brief_id: str) -> dict[str, Any]:
        value = self.store.get("briefs", _uuid(brief_id, "brief_id"))
        return {**value, "project_name": self._project(value["project_id"])["name"]}

    def correct_brief(self, brief_id: str, *, request_id: str, instruction: str, requested_by: str) -> tuple[dict[str, Any], bool]:
        base = self.get_brief(brief_id)
        if base["status"] != "completed":
            raise ValueError("only a completed Product Brief can be corrected")
        request_id = _uuid(request_id, "request_id")
        instruction = _compact(instruction, "instruction", 1, 2000)
        replacement_id, created = self.store.reserve_request(
            scope="brief-correction", request_id=request_id,
            fingerprint={"base_brief_id": brief_id, "instruction": instruction},
        )
        if not created:
            return self.get_brief(replacement_id), False
        feedback_id = new_uuid7()
        feedback = {
            "feedback_id": feedback_id, "project_id": base["project_id"],
            "brief_id": brief_id, "decision": "correction", "comment": instruction,
            "requested_by": requested_by, "created_at": utc_now(),
        }
        replacement = {
            **{key: value for key, value in base.items() if key not in {
                "product", "target_audience", "main_pain", "promise", "key_benefits",
                "cta", "trust_strategy", "offer", "document", "document_sha256",
                "quality_gates", "provider_invocation_id", "project_name",
            }},
            "brief_id": replacement_id, "request_id": request_id,
            "base_brief_id": brief_id, "feedback_id": feedback_id,
            "status": "queued", "document": None, "document_sha256": None,
            "failure_count": 0, "approved": False,
            "created_at": utc_now(), "updated_at": utc_now(),
        }
        self.store.append("feedback", feedback_id, feedback)
        self.store.append("briefs", replacement_id, replacement)
        self.store.edge(source_id=replacement_id, relation="supersedes", target_id=brief_id)
        self.store.edge(source_id=replacement_id, relation="derived_from", target_id=feedback_id)
        return self.get_brief(replacement_id), True

    def retry_brief(self, brief_id: str) -> dict[str, Any]:
        brief = self.get_brief(brief_id)
        if brief["status"] != "failed":
            raise ValueError("only a failed Product Brief can be retried")
        queued = {
            **brief, "status": "queued", "error_code": None, "error_message": None,
            "updated_at": utc_now(),
        }
        queued.pop("project_name", None)
        self.store.append("briefs", brief_id, queued)
        return queued

    def approve_brief(self, brief_id: str, requested_by: str) -> tuple[dict[str, Any], bool]:
        brief = self.get_brief(brief_id)
        if brief["status"] != "completed" or not brief.get("document"):
            raise ValueError("only a completed Product Brief can be approved")
        if brief.get("approved"):
            return brief, False
        approval_id = new_uuid7()
        self.store.append("approvals", approval_id, {
            "approval_id": approval_id, "brief_id": brief_id, "authority": "owner",
            "honor_confirmed": True, "requested_by": requested_by, "created_at": utc_now(),
        })
        updated = {**brief, "approved": True, "approval_id": approval_id, "updated_at": utc_now()}
        updated.pop("project_name", None)
        self.store.append("briefs", brief_id, updated)
        self.store.edge(source_id=approval_id, relation="approves", target_id=brief_id)
        return self.get_brief(brief_id), True

    # Approved Project asset pool -------------------------------------------------

    def upload_asset(
        self, *, project_id: str, title: str, mime_type: str, data: bytes,
        requested_by: str, origin: str = "owner_upload", source: Mapping[str, Any] | None = None,
        approval_status: str = "pending",
    ) -> dict[str, Any]:
        project_id = _uuid(project_id, "project_id")
        self._project(project_id)
        if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("local Project asset must be JPEG, PNG, or WebP")
        if not data or len(data) > 12 * 1024 * 1024:
            raise ValueError("local Project asset is empty or exceeds 12 MB")
        inspected = inspect_media(data, mime_type)
        asset_id = new_uuid7()
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime_type]
        artifact = self.store.write_artifact("project_assets", asset_id, f"source.{extension}", data)
        value = {
            "source_asset_id": asset_id, "project_id": project_id,
            "title": _compact(title, "asset title", 1, 160), "mime_type": mime_type,
            "sha256": artifact["sha256"], "byte_count": len(data),
            "width": inspected["width"], "height": inspected["height"],
            "origin": origin, "source": dict(source or {"origin": origin}),
            "approval_status": approval_status, "approved": approval_status == "approved",
            "artifact": artifact, "requested_by": requested_by, "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.store.append("project_assets", asset_id, value)
        self.store.edge(source_id=project_id, relation="contains", target_id=asset_id)
        return value

    def list_assets(self, project_id: str) -> list[dict[str, Any]]:
        project_id = _uuid(project_id, "project_id")
        self._project(project_id)
        return [item for item in self.store.list("project_assets") if item["project_id"] == project_id]

    def approve_asset(self, asset_id: str, *, approved: bool, requested_by: str) -> dict[str, Any]:
        value = self.store.get("project_assets", _uuid(asset_id, "asset_id"))
        decision_id = new_uuid7()
        status = "approved" if approved else "rejected"
        self.store.append("asset_decisions", decision_id, {
            "decision_id": decision_id, "source_asset_id": asset_id,
            "decision": status, "authority": "owner", "requested_by": requested_by,
            "created_at": utc_now(),
        })
        updated = {
            **value, "approval_status": status, "approved": approved,
            "approval_decision_id": decision_id, "updated_at": utc_now(),
        }
        self.store.append("project_assets", asset_id, updated)
        self.store.edge(source_id=decision_id, relation="approves" if approved else "rejects", target_id=asset_id)
        return updated

    def source_pexels_asset(self, project_id: str, *, query: str, requested_by: str) -> dict[str, Any]:
        if self.pexels is None:
            raise RuntimeError("PEXELS_API_KEY is not configured for the local asset pool")
        project_id = _uuid(project_id, "project_id")
        query = _compact(query, "Pexels query", 2, 160)
        used_ids = {
            str(item.get("source", {}).get("external_id"))
            for item in self.list_assets(project_id)
            if item.get("source", {}).get("external_id")
        }
        photo, data = self.pexels.select(query, query, used_ids=used_ids)
        return self.upload_asset(
            project_id=project_id, title=f"Pexels · {photo.photographer}",
            mime_type="image/jpeg", data=data, requested_by=requested_by,
            origin="pexels", source={
                "origin": "pexels", **photo.source_metadata(), "query": query,
                "transformation": "none", "no_synthetic_people": True,
            }, approval_status="pending",
        )

    def asset_bytes(self, asset_id: str) -> dict[str, Any]:
        value = self.store.get("project_assets", _uuid(asset_id, "asset_id"))
        data = self.store.artifact(value["artifact"]["path"], expected_sha256=value["sha256"])
        return {**value, "bytes": data}

    def _resolve_candidate_assets(
        self, run: Mapping[str, Any], brief: Mapping[str, Any],
    ) -> dict[str, str | None]:
        approved = [item for item in self.list_assets(run["project_id"]) if item.get("approved")]
        distinct: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in approved:
            if item["sha256"] not in seen:
                distinct.append(item)
                seen.add(item["sha256"])
        photo_order = [item for item in TEMPLATE_IDS if item in PHOTO_STRATEGIES]
        assignments: dict[str, str | None] = {}
        base_strategy = run.get("immutable_base_strategy_id")
        base_asset = run.get("immutable_base_asset_id")
        remaining = list(distinct)
        if base_strategy in PHOTO_STRATEGIES:
            if base_asset:
                selected = next((item for item in remaining if item["source_asset_id"] == base_asset), None)
                if selected is None:
                    raise ValueError("immutable child-run base asset is no longer approved in its Project pool")
                assignments[str(base_strategy)] = str(base_asset)
                remaining.remove(selected)
            else:
                # Preserve an immutable texture-backed parent even if photos are
                # added to the Project before the child run starts.
                assignments[str(base_strategy)] = None

        open_strategies = [item for item in photo_order if item not in assignments]
        used_external: set[str] = {
            str(item.get("source", {}).get("external_id")) for item in distinct
            if item.get("source", {}).get("external_id")
        }
        attempts = 0
        while len(remaining) < len(open_strategies) and self.pexels is not None:
            strategy = open_strategies[len(remaining)]
            query = f"{brief['product']} {brief['target_audience']} candid {strategy.replace('_', ' ')}"
            attempts += 1
            try:
                photo, data = self.pexels.select(query, brief["product"], used_ids=used_external)
                used_external.add(photo.photo_id)
                asset = self.upload_asset(
                    project_id=run["project_id"], title=f"Pexels · {photo.photographer}",
                    mime_type="image/jpeg", data=data, requested_by="local-preflight",
                    origin="pexels", source={
                        "origin": "pexels", **photo.source_metadata(), "query": query,
                        "transformation": "none", "no_synthetic_people": True,
                    }, approval_status="approved",
                )
            except Exception:
                # Pexels is optional enrichment. A provider outage or unusable
                # response falls back to the canonical deterministic texture.
                break
            if asset["sha256"] not in seen:
                remaining.append(asset)
                seen.add(asset["sha256"])
            if attempts >= len(open_strategies) * 2:
                break
        for strategy in open_strategies:
            assignments[strategy] = remaining.pop(0)["source_asset_id"] if remaining else None
        return assignments

    # Lessons ---------------------------------------------------------------------

    def active_lesson_snapshot(self) -> dict[str, Any]:
        lessons = [
            item for item in self.store.list("lessons")
            if item.get("status") == "active" and item.get("approval_authority") == "owner"
        ]
        lessons.sort(key=lambda item: (item["target"], int(item["version"]), item["lesson_id"]))
        snapshot_id = new_uuid7()
        body = {
            "schema": "ptw.local-lesson-snapshot.v1", "snapshot_id": snapshot_id,
            "lessons": [{
                "lesson_id": item["lesson_id"], "target": item["target"],
                "version": item["version"], "text": item["text"],
                "layout_patch": item.get("layout_patch") or [], "sha256": item["sha256"],
            } for item in lessons],
        }
        value = {**body, "sha256": sha256_json(body), "created_at": utc_now()}
        self.store.append("lesson_snapshots", snapshot_id, value)
        return value

    # Result run creation and candidate materialization ---------------------------

    def create_run(
        self, *, request_id: str, brief_id: str, platform: str,
        studio_state_sha256: str, requested_by: str,
        parent_run_id: str | None = None, revision_instruction: Mapping[str, Any] | None = None,
        immutable_base: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        request_id = _uuid(request_id, "request_id")
        brief = self.get_brief(_uuid(brief_id, "brief_id"))
        if platform != "instagram":
            raise ValueError("local Universal experiments are Instagram square only")
        if brief["status"] != "completed" or not brief.get("approved"):
            raise ValueError("local Result generation requires an approved completed Product Brief")
        if len(brief["document"]["offer"]) > 160 or len(brief["document"]["cta"]) > 60:
            raise ValueError(
                "Product Brief correction required: the exact offer must be at most 160 characters "
                "and the exact CTA at most 60; protected copy is never truncated"
            )
        parent = None
        if parent_run_id is not None:
            parent = self.get_run(parent_run_id)
            studio_state_sha256 = str(parent["studio_state_sha256"])
        fingerprint = {
            "request_id": request_id, "brief_id": brief_id, "platform": platform,
            "studio_state_sha256": studio_state_sha256,
            "parent_run_id": parent_run_id, "revision_instruction": revision_instruction,
        }
        existing_run_id = self.store.request_target(
            scope="content-run", request_id=request_id, fingerprint=fingerprint,
        )
        if existing_run_id is not None:
            return self.get_run(existing_run_id), False
        if parent is None:
            studio_export = self.workspace.capture_saved_export(studio_state_sha256)
        else:
            studio_export = deepcopy(dict(parent["studio_export"]))
        if immutable_base is not None:
            studio_export = deepcopy(dict(studio_export))
            studio_export["configuration"] = deepcopy(dict(immutable_base["configuration"]))
            studio_export["content"] = deepcopy(dict(immutable_base["content"]))
            studio_export["component_settings"] = deepcopy(
                dict(immutable_base["universal_manifest"]["component_settings"])
            )
            studio_export["parent_candidate_id"] = immutable_base["candidate_id"]
            studio_export["sha256"] = sha256_json({key: value for key, value in studio_export.items() if key != "sha256"})
        run_id, created = self.store.reserve_request(
            scope="content-run", request_id=request_id, fingerprint=fingerprint,
        )
        if not created:
            return self.get_run(run_id), False
        snapshot = self.active_lesson_snapshot()
        now = utc_now()
        revision_number = 0
        if parent_run_id:
            revision_number = int(self.get_run(parent_run_id).get("revision_number") or 0) + 1
        run = {
            "run_id": run_id, "request_id": request_id, "parent_run_id": parent_run_id,
            "project_id": brief["project_id"], "brief_id": brief_id,
            "output_profile": LOCAL_OUTPUT_PROFILE, "experiment_profile": PROFILE_ID,
            "platform": "instagram", "task": LOCAL_TASK,
            "status": "queued", "current_stage": "queued", "progress_percent": 0,
            "maximum_minutes": 45, "final_result_id": None,
            "review_state": "unreviewed", "review_feedback_id": None,
            "review_comment": None, "revision_number": revision_number,
            "studio_state_sha256": studio_state_sha256,
            "studio_export": studio_export,
            "learning_snapshot_id": snapshot["snapshot_id"],
            "learning_snapshot_sha256": snapshot["sha256"],
            "revision_instruction": None if revision_instruction is None else dict(revision_instruction),
            "immutable_base_asset_id": None if immutable_base is None else immutable_base.get("asset_id"),
            "immutable_base_strategy_id": None if immutable_base is None else immutable_base.get("template_id"),
            "created_at": now, "updated_at": now,
        }
        self.store.append("runs", run_id, run)
        self.store.edge(source_id=run_id, relation="derived_from", target_id=brief_id)
        self.store.edge(source_id=run_id, relation="uses", target_id=snapshot["snapshot_id"])
        if parent_run_id:
            self.store.edge(source_id=run_id, relation="derived_from", target_id=parent_run_id)
        return run, True

    def _checkpoint(self, run_id: str, stage: str, progress: int, **evidence: Any) -> dict[str, Any]:
        checkpoint_id = new_uuid7()
        checkpoint = {
            "checkpoint_id": checkpoint_id, "run_id": run_id, "stage": stage,
            "progress_percent": progress, "evidence": sanitized(evidence), "created_at": utc_now(),
        }
        self.store.append("checkpoints", checkpoint_id, checkpoint)
        run = self.store.get("runs", run_id)
        self.store.append("runs", run_id, {
            **run, "status": "generating", "current_stage": stage,
            "progress_percent": progress, "checkpoint_id": checkpoint_id,
            "updated_at": utc_now(),
        })
        return checkpoint

    def _lesson_texts(self, snapshot_id: str, target: str) -> list[str]:
        snapshot = self.store.get("lesson_snapshots", snapshot_id)
        return [item["text"] for item in snapshot["lessons"] if item["target"] == target]

    def _active_lesson_texts(self, target: str) -> list[str]:
        lessons = [
            item for item in self.store.list("lessons")
            if item.get("status") == "active"
            and item.get("approval_authority") == "owner"
            and item.get("target") == target
        ]
        lessons.sort(key=lambda item: (int(item["version"]), item["lesson_id"]))
        return [str(item["text"]) for item in lessons]

    def _layout_lesson_base(
        self, base: Mapping[str, Any], *, snapshot_id: str, strategy_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        value = deepcopy(dict(base))
        allowed = set(STRATEGY_PATCHES[strategy_id]) | set(
            PHOTO_FALLBACK_PATCHES.get(strategy_id, {})
        )
        applied: list[dict[str, Any]] = []
        snapshot = self.store.get("lesson_snapshots", snapshot_id)
        for lesson in snapshot["lessons"]:
            if lesson["target"] != "universal_ad_layout_policy":
                continue
            for delta in lesson.get("layout_patch") or []:
                setting_id = str(delta.get("setting_id") or "")
                if not setting_id.startswith("configuration."):
                    continue
                path = setting_id.removeprefix("configuration.")
                if path not in allowed:
                    continue
                group, key = path.split(".", 1)
                before = value[group][key]
                value[group][key] = deepcopy(delta.get("after"))
                applied.append({
                    "lesson_id": lesson["lesson_id"], "setting_id": setting_id,
                    "before": before, "after": value[group][key],
                })
        return value, applied

    def _candidate_prompt(self, template: StrategyTemplate) -> str:
        return (
            f"{self.generator_context}\n\nLOCAL_PROFILE:{PROFILE_ID}\n"
            "Generate one isolated Universal Studio candidate. The eight visual roles are "
            f"required exactly once and in this order: {', '.join(LOCAL_VISUAL_ROLES)}. "
            "The exact offer and CTA are protected. The resolved_render_contract is authoritative "
            "for the optional roles that will actually be visible: describe its bullets, sticker, "
            "background, and saved logo exactly in visual_components and alt_text. A saved canonical "
            "logo is an approved Studio identity, not an invented candidate asset. Use only the "
            "assigned asset for candidate-sourced media. Do not evaluate other candidates or invent "
            "proof, urgency, people, IDs, or market evidence.\n\n"
            f"STRATEGY:\n{json.dumps(template.document, ensure_ascii=False, sort_keys=True)}"
        )

    @staticmethod
    def _candidate_elements(candidate_id: str, document: Mapping[str, Any]) -> list[dict[str, Any]]:
        elements: list[dict[str, Any]] = []
        for slot in COPY_ELEMENT_SLOTS:
            value = document[slot]
            elements.append({
                "element_id": new_uuid7(), "candidate_id": candidate_id,
                "slot": slot, "role": slot, "value": value,
            })
        for item in document["visual_components"]:
            elements.append({
                "element_id": new_uuid7(), "candidate_id": candidate_id,
                "slot": f"visual:{item['role']}", "role": item["role"], "value": item,
            })
        return elements

    def _generate_candidate(
        self, *, run: Mapping[str, Any], brief: Mapping[str, Any],
        template: StrategyTemplate, asset_id: str | None, alias: str,
        generation_kind: str = "initial", parent: Mapping[str, Any] | None = None,
        action: Mapping[str, Any] | None = None, parameters: Mapping[str, int] | None = None,
    ) -> dict[str, Any]:
        candidate_id = new_uuid7()
        sliders = dict(parameters or template.defaults)
        assigned_asset = None if asset_id is None else self.store.get("project_assets", asset_id)
        snapshot_lessons = self._lesson_texts(run["learning_snapshot_id"], "content-candidate-generator")
        saved_assets = run["studio_export"].get("assets") or []
        sticker_available = any(
            item.get("slot") == "sticker_object" and item.get("available")
            and (item.get("source") or {}).get("origin") != "bundled_tune_asset"
            for item in saved_assets
        )
        resolved = resolve_strategy_patch(
            run["studio_export"]["configuration"], template.template_id, sliders,
            sticker_available=sticker_available, photo_available=asset_id is not None,
        )
        lesson_configuration, applied_layout_lessons = self._layout_lesson_base(
            resolved["configuration"], snapshot_id=run["learning_snapshot_id"],
            strategy_id=template.template_id,
        )
        if applied_layout_lessons:
            resolved["configuration"] = normalize_universal_config(lesson_configuration)
            for item in applied_layout_lessons:
                path = item["setting_id"].removeprefix("configuration.")
                group, key = path.split(".", 1)
                resolved["setting_patch"][path] = resolved["configuration"][group][key]
            resolved["setting_deltas"] = [{
                "setting_id": f"configuration.{path}",
                "before": run["studio_export"]["configuration"][path.split('.', 1)[0]][path.split('.', 1)[1]],
                "after": resolved["configuration"][path.split('.', 1)[0]][path.split('.', 1)[1]],
            } for path in sorted(resolved["setting_patch"])
                if run["studio_export"]["configuration"][path.split('.', 1)[0]][path.split('.', 1)[1]]
                != resolved["configuration"][path.split('.', 1)[0]][path.split('.', 1)[1]]]
        logo_asset = next((
            item for item in saved_assets
            if item.get("slot") == "logo" and item.get("available")
        ), None)
        sticker_asset = next((
            item for item in saved_assets
            if item.get("slot") == "sticker_object" and item.get("available")
            and (item.get("source") or {}).get("origin") != "bundled_tune_asset"
        ), None)
        if resolved["configuration"]["logo"]["enabled"] and logo_asset is None:
            raise ValueError("Universal experiment saved logo provenance is unavailable")
        render_contract = {
            "background": {
                "mode": resolved["configuration"]["background"]["mode"],
                "texture": resolved["configuration"]["background"].get("texture"),
                "source_asset_id": asset_id,
            },
            "bullets": {
                "visible": bool(resolved["configuration"]["bullets"]["enabled"]),
                "items": (
                    list(brief["document"]["key_benefits"][:3])
                    if resolved["configuration"]["bullets"]["enabled"] else []
                ),
            },
            "logo": {
                "visible": bool(resolved["configuration"]["logo"]["enabled"]),
                "slot": "logo", "sha256": None if logo_asset is None else logo_asset["sha256"],
                "mime_type": None if logo_asset is None else logo_asset["mime_type"],
                "source": None if logo_asset is None else deepcopy(logo_asset.get("source") or {}),
                "authority": "captured_saved_studio_identity",
            },
            "sticker": {
                "visible": bool(resolved["configuration"]["sticker"]["enabled"]),
                "slot": "sticker_object",
                "sha256": None if sticker_asset is None else sticker_asset["sha256"],
                "mime_type": None if sticker_asset is None else sticker_asset["mime_type"],
                "source": None if sticker_asset is None else deepcopy(sticker_asset.get("source") or {}),
                "authority": "captured_saved_studio_asset" if sticker_asset else None,
            },
        }
        payload = {
            "candidate_id": candidate_id,
            "approved_brief": brief["document"], "task": run["task"],
            "platform": "instagram", "profile": PROFILE_ID,
            "strategy": template.document, "sliders": sliders,
            "runtime_bands": template.runtime_bands(sliders),
            "universal_base": {
                "state_sha256": run["studio_state_sha256"],
                "export_sha256": run["studio_export"]["sha256"],
                "component_settings": run["studio_export"]["component_settings"],
            },
            "assigned_asset": None if assigned_asset is None else {
                key: assigned_asset[key] for key in (
                    "source_asset_id", "title", "mime_type", "sha256", "origin", "source",
                )
            },
            "resolved_render_contract": render_contract,
            "active_owner_lessons": snapshot_lessons,
            "revision_instruction": run.get("revision_instruction"),
            "improvement": None if action is None else dict(action),
            "base_candidate": None if parent is None else {
                "candidate_id": parent["candidate_id"], "document": parent["document"],
                "elements": parent["elements"],
            },
        }
        result = self._provider_call(
            target_id=candidate_id, mode="content_candidate_generation",
            system_prompt=self._candidate_prompt(template), input_payload=payload,
            output_schema=_candidate_schema(asset_id),
            idempotency_key=f"{run['run_id']}:{candidate_id}:candidate",
            prompt_version="local-universal-candidate-v2",
            response_validator=lambda value: _validate_local_candidate(
                value, brief=brief["document"], asset_id=asset_id,
            ),
        )
        document = _validate_local_candidate(result["response"], brief=brief["document"], asset_id=asset_id)
        if parent is not None and action is not None:
            locked = set(map(str, action.get("locked_element_ids") or []))
            parent_by_id = {item["element_id"]: item for item in parent["elements"]}
            for element_id in locked:
                if element_id not in parent_by_id:
                    raise ValueError("critic improvement locked an unknown element")
                element = parent_by_id[element_id]
                if element["slot"].startswith("visual:"):
                    role = element["role"]
                    actual = next(item for item in document["visual_components"] if item["role"] == role)
                else:
                    actual = document[element["slot"]]
                if actual != element["value"]:
                    raise ValueError("candidate improvement changed a critic-locked element")
        content = universal_content_from_generation(document, brief=brief["document"])
        if content["offer"] != brief["document"]["offer"] or content["cta"] != brief["document"]["cta"]:
            raise ValueError("Universal protected copy changed during content mapping")
        background = None if asset_id is None else self.asset_bytes(asset_id)
        rendered = self.workspace.render_experiment(
            configuration=resolved["configuration"], content=content,
            background_asset=background,
        )
        rendered_asset_digests = rendered["resolved"].get("asset_sha256") or {}
        for role in ("logo", "sticker"):
            contract_asset = render_contract[role]
            if (
                contract_asset["visible"]
                and rendered_asset_digests.get(contract_asset["slot"])
                != contract_asset["sha256"]
            ):
                raise ValueError(f"Universal rendered {role} does not match captured Studio provenance")
        audit = audit_universal_render(
            rendered["resolved"], configuration=resolved["configuration"],
            content=content, brief=brief["document"],
        )
        document, document_transformations = _render_aligned_document(
            document, content=content, configuration=resolved["configuration"],
            render_contract=render_contract, language=str(brief["document"]["language"]),
        )
        jpeg = deterministic_jpeg(rendered["bytes"])
        analysis_jpeg = deterministic_analysis_jpeg(rendered["bytes"])
        png_artifact = self.store.write_artifact("candidate_renders", candidate_id, "source.png", rendered["bytes"])
        jpeg_artifact = self.store.write_artifact("candidate_renders", candidate_id, "critic.jpg", jpeg["bytes"])
        analysis_artifact = self.store.write_artifact(
            "candidate_renders", candidate_id, "analysis.jpg", analysis_jpeg["bytes"],
        )
        elements = self._candidate_elements(candidate_id, document)
        for element in elements:
            self.store.append("elements", element["element_id"], {**element, "created_at": utc_now()})
            self.store.edge(source_id=candidate_id, relation="contains", target_id=element["element_id"])
        candidate = {
            "candidate_id": candidate_id, "run_id": run["run_id"], "alias": alias,
            "round": 0 if generation_kind == "initial" else int(parent.get("round", 0)) + 1,
            "generation_kind": generation_kind,
            "parent_candidate_id": None if parent is None else parent["candidate_id"],
            "template_id": template.template_id, "template_version": template.version,
            "template_sha256": template.digest, "parameters": sliders,
            "document": document, "document_sha256": sha256_json(document),
            "elements": elements, "provider_invocation_id": result["invocation_id"],
            "asset_id": asset_id,
            "document_transformations": document_transformations,
            "experiment_adapter": {
                "profile": resolved["profile"], "version": resolved["adapter_version"],
                "media_mode": resolved["media_mode"],
            },
            "asset_provenance": ({
                key: background[key] for key in (
                    "source_asset_id", "sha256", "mime_type", "origin", "source",
                )
            } if background is not None else {
                "origin": "deterministic_studio_texture",
                "preset": resolved["configuration"]["background"]["texture"],
                "sha256": rendered["resolved"]["asset_sha256"]["background_texture"],
                "review_status": "canonical_adapter_fallback",
                "no_synthetic_people": True,
            } if resolved["configuration"]["background"]["mode"] == "texture" else None),
            "render_asset_provenance": render_contract,
            "universal_manifest": rendered["resolved"],
            "resolved_setting_patch": resolved["setting_patch"],
            "resolved_setting_deltas": resolved["setting_deltas"],
            "applied_layout_lessons": applied_layout_lessons,
            "layout_audit": audit,
            "png": {**png_artifact, "mime_type": "image/png", "width": 1080, "height": 1080},
            "preview": {
                **jpeg_artifact, "mime_type": "image/jpeg", "width": 1080, "height": 1080,
                "asset_url": f"/api/v1/content-runs/{run['run_id']}/candidates/{candidate_id}/asset",
            },
            "analysis_preview": {
                **analysis_artifact,
                **{key: analysis_jpeg[key] for key in (
                    "mime_type", "width", "height", "encoder",
                    "source_png_sha256", "source_width", "source_height",
                    "scale_numerator", "scale_denominator",
                )},
                "source_preview_sha256": jpeg_artifact["sha256"],
            },
            "configuration": resolved["configuration"], "content": content,
            "created_at": utc_now(),
        }
        self.store.append("candidates", candidate_id, candidate)
        self.store.edge(source_id=run["run_id"], relation="contains", target_id=candidate_id)
        if parent is not None:
            relation = "supersedes" if generation_kind == "improvement" else "derived_from"
            self.store.edge(source_id=candidate_id, relation=relation, target_id=parent["candidate_id"])
        return candidate

    @staticmethod
    def _critic_view(candidate: Mapping[str, Any]) -> dict[str, Any]:
        analysis = candidate["analysis_preview"]
        return {
            "candidate_id": candidate["candidate_id"],
            "document": candidate["document"],
            "element_ids": [item["element_id"] for item in candidate["elements"]],
            "parameters": candidate["parameters"],
            "template_id": None,
            "resolved_frames": candidate["universal_manifest"]["nodes"],
            "layout_audit": candidate["layout_audit"],
            "render": {
                "sha256": analysis["sha256"], "mime_type": "image/jpeg",
                "width": analysis["width"], "height": analysis["height"],
                "source_preview_sha256": analysis["source_preview_sha256"],
                "source_width": analysis["source_width"],
                "source_height": analysis["source_height"],
                "scale_numerator": analysis["scale_numerator"],
                "scale_denominator": analysis["scale_denominator"],
                "asset_provenance": candidate["render_asset_provenance"],
            },
        }

    def _critic_pass(
        self, *, run: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
        pass_number: int, previous_passes: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        candidate_ids = [str(item["candidate_id"]) for item in candidates]
        candidate_element_ids = {
            str(item["candidate_id"]): [str(element["element_id"]) for element in item["elements"]]
            for item in candidates
        }
        element_ids = [element for values in candidate_element_ids.values() for element in values]
        candidate_parameters = {str(item["candidate_id"]): item["parameters"] for item in candidates}
        candidate_templates = {str(item["candidate_id"]): str(item["template_id"]) for item in candidates}
        regeneration_counts = {str(item["candidate_id"]): int(item["round"]) for item in candidates}
        layout_by_id = {str(item["candidate_id"]): item["layout_audit"] for item in candidates}
        payload = {
            "run_id": run["run_id"], "pass": pass_number,
            "critic_scope": (
                "screening_group_1_of_2" if pass_number == 1
                else "screening_group_2_of_2" if pass_number == 2
                else "group_winner_comparison"
            ),
            "approved_brief": self.get_brief(run["brief_id"])["document"],
            "task": run["task"], "output_profile": LOCAL_OUTPUT_PROFILE,
            "experiment_profile": PROFILE_ID,
            "candidates": [self._critic_view(item) for item in candidates],
            "previous_pass_summaries": [
                {
                    "pass": item["pass_number"],
                    "critic_scope": item["critic_scope"],
                    "ranking": item["ranking"],
                    "group_winner_candidate_id": item["ranking"][0],
                    "group_winner_hard_gates": item["hard_gates"][item["ranking"][0]],
                    "group_winner_candidate_score": item["candidate_scores"][item["ranking"][0]],
                    "pairwise_results": item["pairwise_results"],
                    "observations": item["observations"],
                } for item in previous_passes
            ],
            "active_owner_lessons": self._lesson_texts(
                run["learning_snapshot_id"], "content-result-critic",
            ),
        }

        def validate(value: Mapping[str, Any]) -> Mapping[str, Any]:
            # Deterministic render gates are disclosed to the critic and must not
            # be contradicted by its structured response.
            for evaluation in value.get("evaluations") or []:
                candidate_id = str(evaluation.get("candidate_id"))
                audit = layout_by_id.get(candidate_id)
                if audit is None:
                    continue
                gates = evaluation.get("hard_gates") or {}
                if not audit["passed"] and (
                    gates.get("safe_crop_layout") is not False
                    or gates.get("protected_copy_legible") is not False
                ):
                    raise ValueError("critic contradicted a deterministic Universal layout failure")
            normalized = validate_critic_response(
                value, pass_number=pass_number, candidate_ids=candidate_ids,
                element_ids=element_ids, templates=self.templates_by_id,
                candidate_parameters=candidate_parameters,
                candidate_templates=candidate_templates,
                candidate_element_ids=candidate_element_ids,
                candidate_regeneration_counts=regeneration_counts,
            )
            if pass_number < 3 and normalized["actions"]:
                raise ValueError("local grouped critic screens cannot request generation actions")
            if pass_number == 3 and normalized.get("final_selection"):
                chosen = normalized["final_selection"]["candidate_id"]
                if not layout_by_id[chosen]["passed"]:
                    raise ValueError("critic cannot select a deterministic layout-gate failure")
            return normalized

        images = []
        for candidate in candidates:
            analysis = candidate["analysis_preview"]
            data = self.store.artifact(
                analysis["path"], expected_sha256=analysis["sha256"],
            )
            inspected = inspect_media(data, "image/jpeg")
            if (inspected["width"], inspected["height"]) != (
                analysis["width"], analysis["height"],
            ):
                raise ValueError("critic analysis artifact dimensions do not match provenance")
            images.append({
                "candidate_id": candidate["candidate_id"], "bytes": data,
                "sha256": analysis["sha256"], "mime_type": "image/jpeg",
                "width": analysis["width"], "height": analysis["height"],
            })
        output_schema = critic_output_schema(pass_number, candidate_ids, element_ids)
        if pass_number < 3:
            output_schema["properties"]["actions"]["maxItems"] = 0
        if pass_number == 2:
            output_schema["properties"]["pairwise"]["maxItems"] = 0
        elif pass_number == 3:
            output_schema["properties"]["pairwise"]["maxItems"] = 1
        phase_instruction = (
            "Screen only this first group of three candidates. Return no generation actions."
            if pass_number == 1
            else "Screen only this second group of two candidates independently; leave pairwise and actions empty."
            if pass_number == 2
            else "Re-evaluate and compare only the two supplied group winners using the prior structured summaries."
        )
        result = self._provider_call(
            target_id=run["run_id"], mode="content_result_critic",
            system_prompt=(
                self.critic_context
                + "\n\nEvaluate only the supplied anonymized Universal candidates and their exact "
                "persisted 480x480 analysis JPEGs. Each analysis image is a deterministic "
                "4/9-scale derivative of the digest-bound authoritative 1080x1080 render. "
                "The supplied render.asset_provenance is authoritative: a visible saved Studio "
                "logo with captured_saved_studio_identity authority is approved and must not fail "
                "the Project/brand/media gate merely because it has no candidate asset UUID. "
                f"{phase_instruction} Apply hard gates before scoring. Return concise structured "
                "observations, never hidden reasoning."
            ),
            input_payload=payload,
            output_schema=output_schema,
            idempotency_key=f"{run['run_id']}:critic-pass-{pass_number}",
            prompt_version=f"local-universal-critic-pass-{pass_number}-v2",
            images=images, response_validator=validate,
        )
        normalized = dict(result["response"])
        pass_id = new_uuid7()
        by_id = {item["candidate_id"]: item for item in normalized["evaluations"]}
        record = {
            "pass_id": pass_id, "run_id": run["run_id"], "pass_number": pass_number,
            "critic_scope": payload["critic_scope"],
            "active_candidate_ids": candidate_ids,
            "hard_gates": {candidate_id: by_id[candidate_id]["hard_gates"] for candidate_id in candidate_ids},
            "element_scores": {candidate_id: by_id[candidate_id]["element_scores"] for candidate_id in candidate_ids},
            "candidate_scores": {candidate_id: {
                "scores": by_id[candidate_id]["scores"],
                "complexity": by_id[candidate_id]["complexity"],
                "weighted_total": by_id[candidate_id]["weighted_total"],
                "eligible": by_id[candidate_id]["eligible"],
                "reason_codes": by_id[candidate_id]["reason_codes"],
            } for candidate_id in candidate_ids},
            "ranking": normalized["ranking"], "pairwise_results": normalized["pairwise"],
            "observations": normalized["observations"], "actions": normalized["actions"],
            "final_selection": normalized["final_selection"],
            "provider_invocation_id": result["invocation_id"], "created_at": utc_now(),
        }
        self.store.append("critic_passes", pass_id, record)
        self.store.edge(source_id=run["run_id"], relation="contains", target_id=pass_id)
        for action in record["actions"]:
            action_id = new_uuid7()
            persisted = {
                "action_id": action_id, "run_id": run["run_id"], "pass_id": pass_id,
                **action, "status": "pending", "created_at": utc_now(),
            }
            self.store.append("actions", action_id, persisted)
            self.store.edge(source_id=pass_id, relation="contains", target_id=action_id)
            action["action_id"] = action_id
        return record

    def _apply_actions(
        self, *, run: Mapping[str, Any], brief: Mapping[str, Any],
        active: list[dict[str, Any]], critic_pass: Mapping[str, Any],
        remaining_budget: int, pass_limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        by_id = {item["candidate_id"]: item for item in active}
        replacements: dict[str, dict[str, Any] | None] = {}
        consumed = 0
        for action in list(critic_pass["actions"])[:pass_limit]:
            action_id = action["action_id"]
            action_record = self.store.get("actions", action_id)
            base_id = action.get("base_candidate_id")
            if action["action_type"] == "discard":
                if base_id is not None:
                    replacements[str(base_id)] = None
                self.store.append("actions", action_id, {**action_record, "status": "completed", "updated_at": utc_now()})
                continue
            if consumed >= remaining_budget or base_id is None or str(base_id) not in by_id:
                self.store.append("actions", action_id, {**action_record, "status": "skipped_budget", "updated_at": utc_now()})
                continue
            base = by_id[str(base_id)]
            parameters = base["parameters"]
            if action["action_type"] == "rerun_template":
                parameters = action["slider_values"]
            try:
                improved = self._generate_candidate(
                    run=run, brief=brief,
                    template=self.templates_by_id[base["template_id"]],
                    asset_id=base["asset_id"], alias=f"{base['alias']}.{base['round'] + 1}",
                    generation_kind="improvement", parent=base, action=action,
                    parameters=parameters,
                )
                replacements[str(base_id)] = improved
                consumed += 1
                self.store.append("actions", action_id, {
                    **action_record, "status": "completed",
                    "result_candidate_id": improved["candidate_id"], "updated_at": utc_now(),
                })
            except Exception as error:
                self.store.append("actions", action_id, {
                    **action_record, "status": "failed", "error_type": type(error).__name__,
                    "error_message": str(error)[:500], "updated_at": utc_now(),
                })
                raise
        next_active: list[dict[str, Any]] = []
        for candidate in active:
            replacement = replacements.get(candidate["candidate_id"], candidate)
            if replacement is not None:
                next_active.append(replacement)
        if len(next_active) < 2:
            # Preserve strongest unmodified candidates when discard actions would
            # make the next bounded comparison impossible.
            for candidate_id in critic_pass["ranking"]:
                if candidate_id in by_id and all(item["candidate_id"] != candidate_id for item in next_active):
                    next_active.append(by_id[candidate_id])
                if len(next_active) >= 2:
                    break
        return next_active[:5], consumed

    def execute_run(self, run_id: str) -> dict[str, Any]:
        run_id = _uuid(run_id, "run_id")
        with self._execution_lock:
            run = self.get_run(run_id)
            if run["status"] == "completed":
                return run
            brief = self.get_brief(run["brief_id"])
            try:
                self._checkpoint(run_id, "initial_candidates", 10, boundary="asset_resolution")
                asset_by_strategy = self._resolve_candidate_assets(run, brief["document"])
                run = self.get_run(run_id)
                initial: list[dict[str, Any]] = []
                for index, template in enumerate(self.templates, 1):
                    initial.append(self._generate_candidate(
                        run=run, brief=brief, template=template,
                        asset_id=asset_by_strategy.get(template.template_id), alias=f"C{index}",
                    ))
                if len(initial) != 5 or len({item["preview"]["sha256"] for item in initial}) != 5:
                    raise ValueError("five initial Universal candidates must have distinct deterministic renders")
                media_signatures: list[str] = []
                for item in initial:
                    if item["template_id"] not in PHOTO_STRATEGIES:
                        continue
                    if item["asset_id"] is not None:
                        media_signatures.append(f"asset:{item['asset_id']}")
                    else:
                        background = item["configuration"]["background"]
                        if background["mode"] != "texture":
                            raise ValueError("asset-free strategy must use a deterministic texture fallback")
                        media_signatures.append(f"texture:{background['texture']}")
                if len(media_signatures) != len(set(media_signatures)):
                    raise ValueError("photo-capable strategies must retain distinct media directions")

                first_group, second_group = initial[:3], initial[3:]
                self._checkpoint(
                    run_id, "critic_pass_1", 42,
                    candidate_ids=[item["candidate_id"] for item in first_group],
                    critic_scope="screening_group_1_of_2",
                )
                pass1 = self._critic_pass(
                    run=run, candidates=first_group, pass_number=1, previous_passes=[],
                )
                self._checkpoint(
                    run_id, "critic_pass_2", 66,
                    candidate_ids=[item["candidate_id"] for item in second_group],
                    critic_scope="screening_group_2_of_2",
                )
                pass2 = self._critic_pass(
                    run=run, candidates=second_group, pass_number=2, previous_passes=[],
                )
                by_id = {item["candidate_id"]: item for item in initial}
                finalists = [by_id[pass1["ranking"][0]], by_id[pass2["ranking"][0]]]
                if len(finalists) != 2:
                    raise ValueError("critic Pass 3 requires exactly two finalists")
                self._checkpoint(run_id, "critic_pass_3", 84, finalist_ids=[item["candidate_id"] for item in finalists])
                pass3 = self._critic_pass(
                    run=run, candidates=finalists, pass_number=3, previous_passes=[pass1, pass2],
                )
                selection = pass3.get("final_selection")
                if selection is None:
                    raise ValueError("critic selected no eligible Universal Result; correct the Brief/assets/layout and retry")
                selected = next(item for item in finalists if item["candidate_id"] == selection["candidate_id"])
                if not selected["layout_audit"]["passed"]:
                    raise ValueError("selected Universal Result failed deterministic layout gates")
                self._checkpoint(run_id, "materializing_result", 94, selected_candidate_id=selected["candidate_id"])
                result = self._create_result(run, selected, selection["decision_summary"])
                completed = {
                    **self.get_run(run_id), "status": "completed", "current_stage": "completed",
                    "progress_percent": 100, "final_result_id": result["creative_id"],
                    "preview": {
                        "asset_url": result["asset_url"], "sha256": result["asset_sha256"],
                        "mime_type": "image/jpeg", "width": 1080, "height": 1080,
                    },
                    "improvement_calls": 0, "updated_at": utc_now(),
                }
                self.store.append("runs", run_id, completed)
                return completed
            except Exception as error:
                failed = {
                    **self.get_run(run_id), "status": "failed", "current_stage": "failed",
                    "error_code": type(error).__name__, "error_message": str(error)[:1000],
                    "updated_at": utc_now(),
                }
                self.store.append("runs", run_id, failed)
                checkpoint_id = new_uuid7()
                self.store.append("checkpoints", checkpoint_id, {
                    "checkpoint_id": checkpoint_id, "run_id": run_id, "stage": "failed",
                    "progress_percent": int(failed.get("progress_percent") or 0),
                    "evidence": {"error_type": type(error).__name__}, "created_at": utc_now(),
                })
                return failed

    def _create_result(
        self, run: Mapping[str, Any], candidate: Mapping[str, Any],
        decision_summary: Sequence[str],
    ) -> dict[str, Any]:
        creative_id = new_uuid7()
        value = {
            "creative_id": creative_id, "run_id": run["run_id"],
            "selected_candidate_id": candidate["candidate_id"],
            "recipe_id": None, "render_id": None,
            "decision_summary": list(decision_summary),
            "result_sha256": sha256_json({
                "candidate_id": candidate["candidate_id"], "document": candidate["document"],
                "configuration": candidate["configuration"], "asset_sha256": candidate["preview"]["sha256"],
            }),
            "content": candidate["document"], "content_sha256": candidate["document_sha256"],
            "asset_sha256": candidate["preview"]["sha256"], "asset_mime_type": "image/jpeg",
            "asset_width": 1080, "asset_height": 1080,
            "asset_url": f"/api/v1/content-runs/{run['run_id']}/result/asset",
            "source_png_sha256": candidate["png"]["sha256"],
            "candidate_jpeg_artifact": candidate["preview"],
            "candidate_png_artifact": candidate["png"],
            "universal_manifest": candidate["universal_manifest"],
            "configuration": candidate["configuration"], "studio_content": candidate["content"],
            "experiment_adapter": candidate["experiment_adapter"],
            "asset_provenance": candidate["asset_provenance"],
            "layout_audit": candidate["layout_audit"],
            "resolved_setting_deltas": candidate["resolved_setting_deltas"],
            "learning_snapshot_id": run["learning_snapshot_id"],
            "learning_snapshot_sha256": run["learning_snapshot_sha256"],
            "created_at": utc_now(),
        }
        self.store.append("results", creative_id, value)
        self.store.edge(source_id=creative_id, relation="derived_from", target_id=candidate["candidate_id"])
        self.store.edge(source_id=run["run_id"], relation="contains", target_id=creative_id)
        return value

    # Read models -----------------------------------------------------------------

    def list_runs(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        project_id = _uuid(project_id, "project_id")
        self._project(project_id)
        return [item for item in self.store.list("runs") if item["project_id"] == project_id][:limit]

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.store.get("runs", _uuid(run_id, "run_id"))

    def get_result(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] != "completed" or not run.get("final_result_id"):
            raise ValueError("local Result run is not completed")
        return self.store.get("results", run["final_result_id"])

    def candidate_asset(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        run_id, candidate_id = _uuid(run_id, "run_id"), _uuid(candidate_id, "candidate_id")
        candidate = self.store.get("candidates", candidate_id)
        if candidate["run_id"] != run_id:
            raise KeyError("local candidate does not belong to the requested run")
        artifact = candidate["preview"]
        return {
            "bytes": self.store.artifact(artifact["path"], expected_sha256=artifact["sha256"]),
            "mime_type": "image/jpeg", "sha256": artifact["sha256"],
        }

    def result_asset(self, run_id: str, *, source_png: bool = False) -> dict[str, Any]:
        result = self.get_result(run_id)
        artifact = result["candidate_png_artifact"] if source_png else result["candidate_jpeg_artifact"]
        return {
            "bytes": self.store.artifact(artifact["path"], expected_sha256=artifact["sha256"]),
            "mime_type": "image/png" if source_png else "image/jpeg",
            "sha256": artifact["sha256"],
        }

    def debug(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        candidates = [item for item in self.store.list("candidates") if item["run_id"] == run_id]
        candidates.sort(key=lambda item: (item["round"], item["alias"], item["created_at"]))
        passes = [item for item in self.store.list("critic_passes") if item["run_id"] == run_id]
        passes.sort(key=lambda item: item["pass_number"])
        actions = [item for item in self.store.list("actions") if item["run_id"] == run_id]
        result = None
        if run.get("final_result_id"):
            result = self.store.get("results", run["final_result_id"])
        return {
            "schema": "ptw.local-universal-result-debug.v1",
            "run_id": run_id, "studio_export": run["studio_export"],
            "learning_snapshot_id": run["learning_snapshot_id"],
            "learning_snapshot_sha256": run["learning_snapshot_sha256"],
            "candidates": candidates, "critic_passes": passes, "actions": actions,
            "result": result,
            "lineage_edges": [
                item for item in self.store.list("edges")
                if item["source_id"] == run_id
                or item["target_id"] in {candidate["candidate_id"] for candidate in candidates}
            ],
        }

    # Feedback, outcomes, lessons, and immutable release --------------------------

    @staticmethod
    def _zip_bytes(files: Mapping[str, bytes]) -> bytes:
        output = BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(files):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, files[name])
        return output.getvalue()

    def _release(self, run: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
        existing = [item for item in self.store.list("releases") if item["run_id"] == run["run_id"]]
        if existing:
            return existing[0]
        release_id = new_uuid7()
        brief = self.get_brief(run["brief_id"])
        debug = self.debug(run["run_id"])
        jpeg = self.result_asset(run["run_id"])["bytes"]
        png = self.result_asset(run["run_id"], source_png=True)["bytes"]
        trace = {
            "run_id": run["run_id"], "selected_candidate_id": result["selected_candidate_id"],
            "critic_passes": debug["critic_passes"], "decision_summary": result["decision_summary"],
        }
        sources = {
            "post.jpg": jpeg, "source.png": png,
            "caption.txt": (result["content"]["caption"] + "\n").encode(),
            "alt-text.txt": (result["content"]["alt_text"] + "\n").encode(),
            "product-brief.json": (json.dumps(brief, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
            "universal-manifest.json": (json.dumps({
                "configuration": result["configuration"],
                "content": result["studio_content"],
                "component_manifest": result["universal_manifest"],
                "layout_audit": result["layout_audit"],
            }, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
            "asset-provenance.json": (json.dumps(result["asset_provenance"], ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
            "decision-trace.json": (json.dumps(trace, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
        }
        digest_manifest = {
            "schema": "ptw.local-release-digest-manifest.v1",
            "release_id": release_id, "run_id": run["run_id"],
            "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(sources.items())},
        }
        sources["digest-manifest.json"] = (
            json.dumps(digest_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
        package = self._zip_bytes(sources)
        artifact = self.store.write_artifact("releases", release_id, "instagram-ready.zip", package)
        release = {
            "release_id": release_id, "run_id": run["run_id"],
            "creative_id": result["creative_id"], "status": "ready",
            "platform": "instagram", "artifact": artifact,
            "package_sha256": artifact["sha256"], "file_digests": digest_manifest["files"],
            "download_count": 0, "created_at": utc_now(), "updated_at": utc_now(),
        }
        self.store.append("releases", release_id, release)
        self.store.edge(source_id=release_id, relation="derived_from", target_id=result["creative_id"])
        return release

    def _lesson_proposals(
        self, *, run: Mapping[str, Any], result: Mapping[str, Any], feedback: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        selected = self.store.get("candidates", result["selected_candidate_id"])
        accepted = feedback["decision"] == "accepted"
        comment = feedback.get("comment") or ""
        proposals: list[dict[str, Any]] = []
        texts = {
            "product-brief-generator": (
                "Preserve concise, renderable protected offers and CTAs when the owner accepts the final Result."
                if accepted else f"Consider this owner correction when framing future Brief hypotheses: {comment}"
            ),
            "content-candidate-generator": (
                "Prefer candidate copy whose protected offer and CTA remain visible within a compact Universal hierarchy."
                if accepted else f"Generalize this owner candidate-direction request without changing protected Brief fields: {comment}"
            ),
            "content-result-critic": (
                "Treat owner acceptance plus deterministic layout gates as evidence for clear, coherent final selection."
                if accepted else f"Use this owner rejection as a bounded critic warning: {comment}"
            ),
            "universal_ad_layout_policy": (
                "Preserve the selected strategy's safe, collision-free Universal setting relationships."
                if accepted else f"Review declared Universal layout settings against this owner request: {comment}"
            ),
        }
        for target in LESSON_TARGETS:
            proposal_id = new_uuid7()
            proposal = {
                "proposal_id": proposal_id, "target": target, "status": "pending",
                "generalized_text": texts[target],
                "layout_patch": selected["resolved_setting_deltas"] if target == "universal_ad_layout_policy" else [],
                "evidence": {
                    "run_id": run["run_id"], "creative_id": result["creative_id"],
                    "feedback_id": feedback["feedback_id"],
                    "critic_pass_ids": [
                        item["pass_id"] for item in self.store.list("critic_passes")
                        if item["run_id"] == run["run_id"]
                    ],
                },
                "created_at": utc_now(), "updated_at": utc_now(),
            }
            proposal["sha256"] = sha256_json({key: value for key, value in proposal.items() if key != "sha256"})
            self.store.append("lesson_proposals", proposal_id, proposal)
            self.store.edge(source_id=proposal_id, relation="derived_from", target_id=feedback["feedback_id"])
            proposals.append(proposal)
        return proposals

    def ready(self, run_id: str, requested_by: str) -> dict[str, Any]:
        with self._execution_lock:
            return self._ready_locked(run_id, requested_by)

    def _ready_locked(self, run_id: str, requested_by: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        result = self.get_result(run_id)
        if run.get("review_state") == "ready":
            release = next(item for item in self.store.list("releases") if item["run_id"] == run_id)
            return {"run": run, "release": release, "created": False}
        if run["status"] != "completed" or not result["layout_audit"]["passed"]:
            raise ValueError("only a completed eligible Result can be released")
        feedback_id, weight_id, outcome_id = new_uuid7(), new_uuid7(), new_uuid7()
        feedback = {
            "feedback_id": feedback_id, "run_id": run_id,
            "creative_id": result["creative_id"], "decision": "accepted", "comment": None,
            "authority": "owner", "requested_by": requested_by, "created_at": utc_now(),
        }
        weight = {
            "weight_update_id": weight_id, "feedback_id": feedback_id,
            "creative_id": result["creative_id"], "deltas": {},
            "append_only": True, "created_at": utc_now(),
        }
        outcome = {
            "outcome_id": outcome_id, "run_id": run_id, "creative_id": result["creative_id"],
            "event_type": "owner_accepted", "source": "owner_local",
            "market_performance": False, "created_at": utc_now(),
        }
        self.store.append("feedback", feedback_id, feedback)
        self.store.append("weight_updates", weight_id, weight)
        self.store.append("outcomes", outcome_id, outcome)
        self.store.edge(source_id=feedback_id, relation="evaluates", target_id=result["creative_id"])
        self.store.edge(source_id=weight_id, relation="adjusts", target_id=result["creative_id"])
        self.store.edge(source_id=feedback_id, relation="contains", target_id=weight_id)
        release = self._release(run, result)
        self._lesson_proposals(run=run, result=result, feedback=feedback)
        updated = {
            **run, "review_state": "ready", "review_feedback_id": feedback_id,
            "release_id": release["release_id"], "updated_at": utc_now(),
        }
        self.store.append("runs", run_id, updated)
        return {"run": updated, "release": release, "created": True}

    def improve(
        self, run_id: str, *, request_id: str, comment: str, requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        with self._execution_lock:
            return self._improve_locked(
                run_id, request_id=request_id, comment=comment, requested_by=requested_by,
            )

    def _improve_locked(
        self, run_id: str, *, request_id: str, comment: str, requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        run = self.get_run(run_id)
        result = self.get_result(run_id)
        request_id = _uuid(request_id, "request_id")
        comment = _compact(comment, "revision comment", 3, 2000)
        existing = next((
            item for item in self.store.list("runs")
            if item.get("request_id") == request_id and item.get("parent_run_id") == run_id
        ), None)
        if existing is not None:
            if (existing.get("revision_instruction") or {}).get("comment") != comment:
                raise ValueError("idempotency request ID was reused with different revision input")
            return existing, False
        feedback_id = new_uuid7()
        feedback = {
            "feedback_id": feedback_id, "run_id": run_id,
            "creative_id": result["creative_id"], "decision": "rejected", "comment": comment,
            "authority": "owner", "requested_by": requested_by, "created_at": utc_now(),
        }
        self.store.append("feedback", feedback_id, feedback)
        weight_id = new_uuid7()
        self.store.append("weight_updates", weight_id, {
            "weight_update_id": weight_id, "feedback_id": feedback_id,
            "creative_id": result["creative_id"], "deltas": {},
            "append_only": True, "created_at": utc_now(),
        })
        self.store.edge(source_id=feedback_id, relation="evaluates", target_id=result["creative_id"])
        self.store.edge(source_id=weight_id, relation="adjusts", target_id=result["creative_id"])
        self._lesson_proposals(run=run, result=result, feedback=feedback)
        self.store.append("runs", run_id, {
            **run, "review_state": "needs_changes", "review_feedback_id": feedback_id,
            "review_comment": comment, "updated_at": utc_now(),
        })
        selected = self.store.get("candidates", result["selected_candidate_id"])
        revision = {
            "schema_version": 1, "feedback_id": feedback_id, "parent_run_id": run_id,
            "creative_id": result["creative_id"], "comment": comment,
        }
        child, created = self.create_run(
            request_id=request_id, brief_id=run["brief_id"], platform="instagram",
            studio_state_sha256=run["studio_state_sha256"], requested_by=requested_by,
            parent_run_id=run_id, revision_instruction=revision,
            immutable_base=selected,
        )
        self.store.edge(source_id=child["run_id"], relation="derived_from", target_id=feedback_id)
        self.store.edge(source_id=child["run_id"], relation="derived_from", target_id=result["creative_id"])
        return child, created

    def retry_run(self, run_id: str, *, request_id: str, requested_by: str) -> tuple[dict[str, Any], bool]:
        parent = self.get_run(run_id)
        if parent["status"] not in {"completed", "failed"}:
            raise ValueError("a local run can be retried only after it is terminal")
        return self.create_run(
            request_id=request_id, brief_id=parent["brief_id"], platform="instagram",
            studio_state_sha256=parent["studio_state_sha256"], requested_by=requested_by,
            parent_run_id=run_id,
        )

    def release_download(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run.get("review_state") != "ready" or not run.get("release_id"):
            raise ValueError("release package is locked until owner Ready")
        release = self.store.get("releases", run["release_id"])
        data = self.store.artifact(release["artifact"]["path"], expected_sha256=release["package_sha256"])
        self.store.append("releases", release["release_id"], {
            **release, "download_count": int(release["download_count"]) + 1,
            "updated_at": utc_now(),
        })
        outcome_id = new_uuid7()
        self.store.append("outcomes", outcome_id, {
            "outcome_id": outcome_id, "run_id": run_id,
            "creative_id": self.get_result(run_id)["creative_id"],
            "event_type": "release_downloaded", "source": "owner_local",
            "market_performance": False, "created_at": utc_now(),
        })
        return {"bytes": data, "sha256": release["package_sha256"], "release_id": release["release_id"]}

    def list_lesson_proposals(self, status: str | None = None) -> list[dict[str, Any]]:
        values = self.store.list("lesson_proposals")
        if status is not None:
            if status not in {"pending", "approved", "rejected"}:
                raise ValueError("unknown lesson proposal status")
            values = [item for item in values if item["status"] == status]
        return values

    def decide_lesson(
        self, proposal_id: str, *, decision: str, edited_text: str | None,
        approval_authority: str, requested_by: str,
    ) -> dict[str, Any]:
        proposal = self.store.get("lesson_proposals", _uuid(proposal_id, "proposal_id"))
        if proposal["status"] != "pending":
            raise ValueError("lesson proposal already has an immutable owner decision")
        if decision not in {"approved", "rejected"}:
            raise ValueError("lesson decision must be approved or rejected")
        if approval_authority != "owner":
            raise ValueError("agent lesson approval is reserved but disabled in owner-only mode")
        text = proposal["generalized_text"] if edited_text is None else _compact(
            edited_text, "edited generalized lesson", 3, 2000,
        )
        decision_id = new_uuid7()
        decision_record = {
            "decision_id": decision_id, "proposal_id": proposal_id, "decision": decision,
            "approval_authority": "owner", "edited_text": text,
            "requested_by": requested_by, "created_at": utc_now(),
        }
        self.store.append("lesson_decisions", decision_id, decision_record)
        updated = {
            **proposal, "status": decision, "generalized_text": text,
            "decision_id": decision_id, "updated_at": utc_now(),
        }
        self.store.append("lesson_proposals", proposal_id, updated)
        self.store.edge(source_id=decision_id, relation=decision, target_id=proposal_id)
        lesson = None
        if decision == "approved":
            existing = [item for item in self.store.list("lessons") if item["target"] == proposal["target"]]
            lesson_id = new_uuid7()
            body = {
                "lesson_id": lesson_id, "target": proposal["target"],
                "version": len(existing) + 1, "status": "active", "text": text,
                "layout_patch": proposal.get("layout_patch") or [],
                "evidence": proposal["evidence"], "proposal_id": proposal_id,
                "decision_id": decision_id, "approval_authority": "owner",
                "created_at": utc_now(),
            }
            lesson = {**body, "sha256": sha256_json(body)}
            self.store.append("lessons", lesson_id, lesson)
            self.store.edge(source_id=lesson_id, relation="derived_from", target_id=proposal_id)
        return {"proposal": updated, "decision": decision_record, "lesson": lesson}

    def learning_summary(self, project_id: str | None = None) -> dict[str, Any]:
        runs = self.store.list("runs")
        if project_id is not None:
            project_id = _uuid(project_id, "project_id")
            runs = [item for item in runs if item["project_id"] == project_id]
        summaries: list[dict[str, Any]] = []
        for run in runs:
            passes = [item for item in self.store.list("critic_passes") if item["run_id"] == run["run_id"]]
            passes.sort(key=lambda item: item["pass_number"])
            gate_values = [
                value for critic_pass in passes for gates in critic_pass["hard_gates"].values()
                for value in gates.values()
            ]
            initial_scores = list(passes[0]["candidate_scores"].values()) if passes else []
            final_scores = list(passes[-1]["candidate_scores"].values()) if passes else []
            result = None
            if run.get("final_result_id"):
                result = self.store.get("results", run["final_result_id"])
            summaries.append({
                "run_id": run["run_id"], "status": run["status"],
                "gate_rate": None if not gate_values else round(sum(bool(item) for item in gate_values) / len(gate_values), 4),
                "initial_best_score": None if not initial_scores else max(item["weighted_total"] for item in initial_scores),
                "final_best_score": None if not final_scores else max(item["weighted_total"] for item in final_scores),
                "score_delta": None if not initial_scores or not final_scores else (
                    max(item["weighted_total"] for item in final_scores)
                    - max(item["weighted_total"] for item in initial_scores)
                ),
                "applied_setting_changes": [] if result is None else result["resolved_setting_deltas"],
                "owner_outcomes": [
                    item for item in self.store.list("outcomes") if item["run_id"] == run["run_id"]
                ],
                "release": next((
                    item for item in self.store.list("releases") if item["run_id"] == run["run_id"]
                ), None),
                "learning_snapshot_id": run["learning_snapshot_id"],
                "learning_snapshot_sha256": run["learning_snapshot_sha256"],
            })
        return {
            "schema": "ptw.local-learning-summary.v1", "market_performance": False,
            "runs": summaries,
            "lesson_queue": self.list_lesson_proposals("pending"),
            "approved_lessons": [item for item in self.store.list("lessons") if item["status"] == "active"],
        }

    def recover_interrupted(self) -> dict[str, list[str]]:
        briefs: list[str] = []
        for brief in self.store.list("briefs"):
            if brief.get("status") != "generating":
                continue
            self.store.append("briefs", brief["brief_id"], {
                **brief, "status": "queued", "recovered_after_restart": True,
                "updated_at": utc_now(),
            })
            briefs.append(brief["brief_id"])
        return {"brief_ids": briefs, "run_ids": self.store.recover_interrupted()}
