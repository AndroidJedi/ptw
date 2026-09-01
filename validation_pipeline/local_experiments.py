"""Local Product Brief -> five reviewable Creatives -> owner learning workflow."""

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
    SLIDER_NAMES, TEMPLATE_IDS, StrategyTemplate, TemplateRegistry,
    digest_locked_reference,
)
from .domain import (
    ProductBriefV1, RATING_PATTERN, TESTIMONIAL_PATTERN, UNSUPPLIED_PROOF_PATTERN,
    infer_language, product_brief_schema, require_language,
)
from .images import (
    PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA, PexelsClient,
    validate_pexels_photographic_object,
)
from .local_codex import LocalCodexCancelled, LocalCodexStructuredProvider, sanitized
from .local_experiment_store import LocalExperimentStore, sha256_json, utc_now
from .review_notifications import NotificationAttempt, ReviewNotifier
from .service import load_product_brief_skill, product_brief_system_prompt
from .studio import inspect_media
from .studio_universal import (
    SEMANTIC_ROLES, UNIVERSAL_AD_CONTENT_SCHEMA, isolate_object,
    normalize_universal_config, normalize_universal_content,
    universal_content_from_generation,
)
from .studio_workspace import UniversalStudioWorkspace
from .universal_experiment import (
    MINIMUM_IMAGE_BACKGROUND_DIRECTIONS, PEXELS_IMAGE_BACKGROUND_STRATEGIES,
    PHOTO_FALLBACK_PATCHES, PHOTO_STRATEGIES, PROFILE_ID, STRATEGY_PATCHES,
    audit_creative_diversity, audit_universal_render,
    deterministic_jpeg, resolve_strategy_patch,
)


LOCAL_TASK = "Create one Instagram-square validation post from the approved Product Brief."
LOCAL_OUTPUT_PROFILE = "instagram_static_ad_v1"
LOCAL_CANDIDATE_SCHEMA = "ptw.local-universal-candidate.v1"
LOCAL_VISUAL_ROLES = tuple(SEMANTIC_ROLES)
COPY_ELEMENT_SLOTS = (
    "hook", "headline", "primary_text", "supporting_text", "offer", "cta",
    "caption", "alt_text", "desired_emotion", "visual_concept", "media_request",
)


class _RunTerminationRequested(RuntimeError):
    pass


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
    require_language(
        str(brief.get("language") or ""),
        [result[name] for name in (
            "hook", "headline", "primary_text", "supporting_text",
            "offer", "cta", "caption", "alt_text",
        )],
        "local candidate user-facing copy",
    )
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
            "An ultra-realistic isolated Pexels photograph is visibly rendered as the sticker."
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
            if background["media_kind"] == "approved_photo"
            else "перевірене фотографічне тло без людей"
            if background["media_kind"] == "reviewed_non_human_image"
            else "перевірене графічне тло без людей"
            if background["media_kind"] == "reviewed_non_human_graphic"
            else "суцільне кольорове тло"
            if background["media_kind"] == "native_non_photo"
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
            parts.append("Видно ультрареалістичний стікер із фотографії Pexels.")
    else:
        background_text = (
            "an approved photographic background"
            if background["media_kind"] == "approved_photo"
            else "a reviewed non-human photographic background"
            if background["media_kind"] == "reviewed_non_human_image"
            else "a reviewed non-human graphic background"
            if background["media_kind"] == "reviewed_non_human_graphic"
            else "a solid-color background"
            if background["media_kind"] == "native_non_photo"
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
            parts.append("An ultra-realistic sticker isolated from a Pexels photograph is visible.")
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
        pexels: PexelsClient | None = None, notifier: ReviewNotifier | None = None,
    ) -> None:
        self.store = store
        self.workspace = workspace
        self.provider = provider
        self.repository_root = repository_root
        self.pexels = pexels
        self.notifier = notifier
        self._execution_lock = threading.RLock()
        self._cancellation_lock = threading.RLock()
        self._cancellation_events: dict[str, threading.Event] = {}
        self._run_context = threading.local()
        self.product_skill_path = repository_root / "skills/product-brief-generator/SKILL.md"
        self.generator_skill_path = repository_root / "skills/content-candidate-generator/SKILL.md"
        reference_root = self.generator_skill_path.parent / "references"
        self.post_copy_style_path = reference_root / "post-copy-style.md"
        _post_copy_style, self.post_copy_style_sha256 = digest_locked_reference(
            self.post_copy_style_path
        )
        self.templates = TemplateRegistry(reference_root / "templates").load_active()
        self.templates_by_id = {item.template_id: item for item in self.templates}
        self.generator_context = self._read_context((
            self.generator_skill_path,
            reference_root / "writing-principles.md",
            reference_root / "anti-patterns.md",
            reference_root / "techniques/ad-copy.md",
            self.post_copy_style_path,
            reference_root / "owner-lessons.md",
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

    def _raise_if_termination_requested(self, run_id: str) -> None:
        event = getattr(self._run_context, "cancel_event", None)
        run = self.store.get("runs", run_id)
        if (event is not None and event.is_set()) or run.get("status") == "terminated":
            raise _RunTerminationRequested("local Result run was terminated by the owner")

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
            "status": (
                "terminated" if isinstance(error, LocalCodexCancelled)
                else "failed" if error else "completed"
            ),
            "error_type": None if error is None else type(error).__name__,
            "created_at": utc_now(),
        }
        self.store.append("provider_invocations", invocation_id, value)
        self.store.edge(source_id=target_id, relation="used_provider_invocation", target_id=invocation_id)
        return invocation_id

    def _provider_call(self, *, target_id: str, mode: str, **kwargs: Any) -> dict[str, Any]:
        payload = dict(kwargs["input_payload"])
        cancel_event = getattr(self._run_context, "cancel_event", None)
        if cancel_event is not None:
            kwargs["cancel_event"] = cancel_event
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

    def create_brief(
        self, *, request_id: str, raw_idea: str, required_language: str,
        requested_by: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        request_id = _uuid(request_id, "request_id")
        raw_idea = _compact(raw_idea, "raw_idea", 1, 10_000)
        if required_language not in {"uk", "en"}:
            raise ValueError("required_language must be uk or en")
        project_id, created = self.store.reserve_request(
            scope="brief-create", request_id=request_id,
            fingerprint={
                "request_id": request_id, "raw_idea": raw_idea,
                "required_language": required_language,
            },
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
            "required_language": required_language,
            "created_at": now,
        }
        brief = {
            "brief_id": brief_id, "project_id": project_id, "project_name": project["name"],
            "request_id": request_id, "owner_idea_source_id": source_id,
            "raw_idea": raw_idea, "base_brief_id": None, "feedback_id": None,
            "required_language": required_language,
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
        base = None
        correction = None
        mode = "product_brief"
        if brief.get("base_brief_id"):
            base = self.store.get("briefs", brief["base_brief_id"])["document"]
            correction = self.store.get("feedback", brief["feedback_id"])["comment"]
            mode = "product_brief_revision"
        source = self.store.get("sources", brief["owner_idea_source_id"])
        required_language = str(
            source.get("required_language")
            or (base or {}).get("language")
            or (brief.get("document") or {}).get("language")
            or infer_language(brief["raw_idea"])
        )
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
                idempotency_key=f"{brief_id}:{mode}", prompt_version=f"local-product-brief-v2:{mode}",
                response_validator=lambda value: ProductBriefV1.from_dict(
                    value, raw_idea=brief["raw_idea"], required_language=required_language,
                ).to_dict(),
            )
            document = ProductBriefV1.from_dict(
                result["response"], raw_idea=brief["raw_idea"],
                required_language=required_language,
            )
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

    @staticmethod
    def _pexels_background_query(brief: Mapping[str, Any], strategy_id: str) -> str:
        directions = {
            "moment_tension": "modern city business office blue hour cinematic photography",
            "contrast_reframe": "financial planning desk warm natural paper editorial photography",
            "mechanism_proof": "modern glass architecture geometric daylight photography",
            "human_story": "thoughtful workspace window natural light documentary photography",
        }
        product = " ".join(str(brief["product"]).split())[:56]
        return f"{product} {directions[strategy_id]}"[:160].rstrip()

    def _resolve_candidate_assets(
        self, run: Mapping[str, Any], brief: Mapping[str, Any],
    ) -> dict[str, str | None]:
        """Resolve exactly three distinct, run-fresh Pexels photo backgrounds."""

        all_assets = self.list_assets(run["project_id"])
        assignments = {strategy_id: None for strategy_id in PHOTO_STRATEGIES}
        used_external = {
            str(item.get("source", {}).get("external_id"))
            for item in all_assets if item.get("source", {}).get("external_id")
        }
        used_digests = {str(item["sha256"]) for item in all_assets}
        base_strategy = str(run.get("immutable_base_strategy_id") or "")
        base_asset_id = run.get("immutable_base_asset_id")
        if base_strategy in PHOTO_STRATEGIES and base_asset_id:
            base_asset = next((
                item for item in all_assets
                if item["source_asset_id"] == base_asset_id and item.get("approved")
            ), None)
            if base_asset is None:
                raise ValueError("immutable child-run base asset is no longer approved in its Project pool")
            if base_asset.get("source", {}).get("provider") != "pexels":
                raise ValueError("immutable child-run photo is not a Pexels source")
            assignments[base_strategy] = str(base_asset_id)
        for item in all_assets:
            source = item.get("source", {})
            strategy_id = str(source.get("strategy_id") or "")
            if (
                item.get("approved")
                and source.get("provider") == "pexels"
                and source.get("usage") == "candidate_background"
                and source.get("run_id") == run["run_id"]
                and strategy_id in PHOTO_STRATEGIES
                and assignments[strategy_id] is None
            ):
                assignments[strategy_id] = str(item["source_asset_id"])

        required = MINIMUM_IMAGE_BACKGROUND_DIRECTIONS - sum(
            asset_id is not None for asset_id in assignments.values()
        )
        if required > 0 and self.pexels is None:
            raise RuntimeError(
                "PEXELS_API_KEY is required: every post needs three distinct real-photo backgrounds"
            )

        strategy_order = [
            *PEXELS_IMAGE_BACKGROUND_STRATEGIES,
            *(strategy_id for strategy_id in TEMPLATE_IDS if strategy_id in PHOTO_STRATEGIES),
        ]
        open_strategies: list[str] = []
        for strategy_id in strategy_order:
            if strategy_id not in open_strategies and assignments[strategy_id] is None:
                open_strategies.append(strategy_id)

        for strategy_id in open_strategies[:required]:
            query = self._pexels_background_query(brief, strategy_id)
            selected_asset: dict[str, Any] | None = None
            for _attempt in range(3):
                photo, data = self.pexels.select(
                    query, "business editorial photography", used_ids=used_external,
                )
                used_external.add(photo.photo_id)
                digest = hashlib.sha256(data).hexdigest()
                if digest in used_digests:
                    continue
                selected_asset = self.upload_asset(
                    project_id=run["project_id"], title=f"Pexels · {photo.photographer}",
                    mime_type="image/jpeg", data=data, requested_by="local-preflight",
                    origin="pexels", source={
                        "origin": "pexels", **photo.source_metadata(), "query": query,
                        "transformation": "none", "usage": "candidate_background",
                        "strategy_id": strategy_id, "run_id": run["run_id"],
                        "selection_policy": "fresh_distinct_per_run_v1",
                        "no_synthetic_people": True,
                    }, approval_status="approved",
                )
                used_digests.add(digest)
                break
            if selected_asset is None:
                raise RuntimeError(
                    f"Pexels did not return a fresh distinct photo for {strategy_id}"
                )
            assignments[strategy_id] = str(selected_asset["source_asset_id"])

        if sum(asset_id is not None for asset_id in assignments.values()) != MINIMUM_IMAGE_BACKGROUND_DIRECTIONS:
            raise ValueError("exactly three Pexels image-backed candidate directions are required")
        return assignments

    def _resolve_sticker_asset(
        self, run: Mapping[str, Any], brief: Mapping[str, Any],
    ) -> str:
        """Resolve one ultra-realistic Pexels object and isolate it deterministically."""

        all_assets = self.list_assets(run["project_id"])
        existing = next((
            item for item in all_assets
            if item.get("approved")
            and item.get("source", {}).get("provider") == "pexels"
            and item.get("source", {}).get("usage") == "sticker_object"
            and item.get("source", {}).get("run_id") == run["run_id"]
            and item.get("source", {}).get("media_type") == "photograph"
            and item.get("source", {}).get("photographic_object_evidence", {}).get("schema")
            == PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA
        ), None)
        if existing is not None:
            return str(existing["source_asset_id"])
        base_asset_id = run.get("immutable_base_sticker_asset_id")
        if base_asset_id:
            base_asset = next((
                item for item in all_assets
                if item["source_asset_id"] == base_asset_id and item.get("approved")
            ), None)
            if (
                base_asset is None
                or base_asset.get("source", {}).get("provider") != "pexels"
                or base_asset.get("source", {}).get("usage") != "sticker_object"
                or base_asset.get("source", {}).get("media_type") != "photograph"
                or base_asset.get("source", {}).get("photographic_object_evidence", {}).get("schema")
                != PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA
            ):
                raise ValueError("immutable child-run sticker is not an approved Pexels photo object")
            return str(base_asset_id)
        if self.pexels is None:
            raise RuntimeError(
                "PEXELS_API_KEY is required: the sticker must come from a real Pexels photograph"
            )

        used_external = {
            str(item.get("source", {}).get("external_id"))
            for item in all_assets if item.get("source", {}).get("external_id")
        }
        used_digests = {str(item["sha256"]) for item in all_assets}
        query = (
            "real vintage brass compass on a plain warm beige surface, "
            "natural-light close-up photograph"
        )
        last_error: Exception | None = None
        for _attempt in range(6):
            try:
                photo, source_data = self.pexels.select(
                    query,
                    "real physical brass compass plain beige background photograph",
                    used_ids=used_external,
                )
                used_external.add(photo.photo_id)
                photo_evidence = validate_pexels_photographic_object(
                    photo, source_data, query=query,
                )
                data = isolate_object(source_data)
                digest = hashlib.sha256(data).hexdigest()
                if digest in used_digests:
                    continue
                asset = self.upload_asset(
                    project_id=run["project_id"], title=f"Pexels sticker · {photo.photographer}",
                    mime_type="image/png", data=data, requested_by="local-preflight",
                    origin="pexels", source={
                        "origin": "pexels", **photo.source_metadata(), "query": query,
                        "transformation": "edge_color_soft_alpha_v1",
                        "usage": "sticker_object", "run_id": run["run_id"],
                        "media_type": "photograph", "subject_type": "physical_object",
                        "photographic_object_evidence": photo_evidence,
                        "selection_policy": "fresh_photographic_object_v2",
                        "texture_alignment": {
                            "strategy_id": "contrast_reframe",
                            "surface": "warm matte paper",
                            "lighting": "soft warm natural light",
                            "palette": "cream navy brass",
                        },
                        "no_synthetic_people": True,
                    }, approval_status="approved",
                )
                return str(asset["source_asset_id"])
            except Exception as error:
                last_error = error
        raise RuntimeError(
            "Pexels did not return an isolatable ultra-realistic sticker object"
        ) from last_error

    # Project-scoped owner learning ----------------------------------------------

    def active_learning_snapshot(self, project_id: str) -> dict[str, Any]:
        rules = [
            item for item in self.store.list("learning_rules")
            if item["project_id"] == project_id
        ]
        superseded = {str(item["supersedes_rule_id"]) for item in rules if item.get("supersedes_rule_id")}
        rules = [item for item in rules if item["rule_id"] not in superseded]
        rules.sort(key=lambda item: (item["rule_type"], item.get("strategy_id") or "", item["rule_id"]))
        snapshot_id = new_uuid7()
        body = {
            "schema": "ptw.local-owner-learning-snapshot.v1", "snapshot_id": snapshot_id,
            "project_id": project_id,
            "rules": [{
                "rule_id": item["rule_id"], "rule_type": item["rule_type"],
                "instruction": item.get("instruction"),
                "strategy_id": item.get("strategy_id"),
                "output_profile": item.get("output_profile"),
                "layout_patch": item.get("layout_patch") or [],
                "exclusions": item.get("exclusions") or {}, "sha256": item["sha256"],
            } for item in rules],
        }
        value = {**body, "sha256": sha256_json(body), "created_at": utc_now()}
        self.store.append("learning_snapshots", snapshot_id, value)
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
        if self.pexels is None:
            raise RuntimeError(
                "PEXELS_API_KEY is required before creating a post with three photo backgrounds "
                "and a photographed sticker"
            )
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
            studio_export["parent_creative_id"] = immutable_base["creative_id"]
            studio_export["sha256"] = sha256_json({key: value for key, value in studio_export.items() if key != "sha256"})
        run_id, created = self.store.reserve_request(
            scope="content-run", request_id=request_id, fingerprint=fingerprint,
        )
        if not created:
            return self.get_run(run_id), False
        snapshot = self.active_learning_snapshot(brief["project_id"])
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
            "maximum_minutes": 45,
            "generation_kind": (
                "initial" if parent is None else
                "tune" if immutable_base is not None else "regenerate_all"
            ),
            "generated_creative_ids": [], "review_creative_ids": [],
            "approved_creative_id": None,
            "review_action_id": None, "revision_number": revision_number,
            "studio_state_sha256": studio_state_sha256,
            "studio_export": studio_export,
            "post_copy_style_sha256": self.post_copy_style_sha256,
            "learning_snapshot_id": snapshot["snapshot_id"], "learning_snapshot_sha256": snapshot["sha256"],
            "revision_instruction": None if revision_instruction is None else dict(revision_instruction),
            "immutable_base_asset_id": None if immutable_base is None else immutable_base.get("asset_id"),
            "immutable_base_sticker_asset_id": (
                None if immutable_base is None else immutable_base.get("sticker_asset_id")
            ),
            "immutable_base_strategy_id": None if immutable_base is None else immutable_base.get("template_id"),
            "tuned_creative_id": None if immutable_base is None else immutable_base.get("creative_id"),
            "notification_state": (
                "not_configured" if self.notifier is None else "not_scheduled"
            ),
            "notification_receipt_id": None,
            "created_at": now, "updated_at": now,
        }
        self.store.append("runs", run_id, run)
        self.store.edge(source_id=run_id, relation="derived_from", target_id=brief_id)
        self.store.edge(source_id=run_id, relation="derived_from", target_id=snapshot["snapshot_id"])
        if parent_run_id:
            self.store.edge(source_id=run_id, relation="derived_from", target_id=parent_run_id)
        return run, True

    def _checkpoint(self, run_id: str, stage: str, progress: int, **evidence: Any) -> dict[str, Any]:
        with self._cancellation_lock:
            self._raise_if_termination_requested(run_id)
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

    def terminate_run(self, run_id: str, requested_by: str) -> dict[str, Any]:
        run_id = _uuid(run_id, "run_id")
        with self._cancellation_lock:
            run = self.get_run(run_id)
            if run["status"] == "terminated":
                return run
            if run["status"] not in {"queued", "generating"}:
                raise ValueError("only an active local Result run can be terminated")
            event = self._cancellation_events.get(run_id)
            if event is not None:
                event.set()
            checkpoint_id = new_uuid7()
            terminated_at = utc_now()
            self.store.append("checkpoints", checkpoint_id, {
                "checkpoint_id": checkpoint_id, "run_id": run_id,
                "stage": "terminated",
                "progress_percent": int(run.get("progress_percent") or 0),
                "evidence": {"requested_by": requested_by},
                "created_at": terminated_at,
            })
            terminated = {
                **run, "status": "terminated", "current_stage": "terminated",
                "termination_checkpoint_id": checkpoint_id,
                "terminated_by": requested_by, "terminated_at": terminated_at,
                "updated_at": terminated_at,
            }
            self.store.append("runs", run_id, terminated)
            for action in self.store.list("review_actions"):
                if action.get("child_run_id") == run_id and action["status"] == "processing":
                    self.store.append("review_actions", action["action_id"], {
                        **action, "status": "failed",
                        "failure": {"error_code": "Terminated", "error_message": "child run terminated"},
                        "updated_at": terminated_at,
                    })
            return terminated

    def _lesson_texts(self, snapshot_id: str, target: str) -> list[str]:
        if target != "content-candidate-generator":
            return []
        snapshot = self.store.get("learning_snapshots", snapshot_id)
        return [
            str(item["instruction"]) for item in snapshot["rules"]
            if item["rule_type"] in {"preferred_direction", "tune_instruction"}
            and item.get("instruction")
        ]

    def _active_lesson_texts(self, target: str) -> list[str]:
        # Result feedback never mutates Product Brief generation.
        return []

    def _layout_lesson_base(
        self, base: Mapping[str, Any], *, snapshot_id: str, strategy_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        value = deepcopy(dict(base))
        allowed = set(STRATEGY_PATCHES[strategy_id]) | set(
            PHOTO_FALLBACK_PATCHES.get(strategy_id, {})
        )
        applied: list[dict[str, Any]] = []
        snapshot = self.store.get("learning_snapshots", snapshot_id)
        for lesson in snapshot["rules"]:
            if lesson["rule_type"] != "preferred_layout":
                continue
            if lesson.get("strategy_id") != strategy_id:
                # Unscoped legacy local lessons remain as textual evidence but
                # cannot mutate every strategy into the same selected recipe.
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
                    "rule_id": lesson["rule_id"], "setting_id": setting_id,
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
            "background, and saved logo exactly in visual_components and alt_text. "
            "The approved_brief.language is authoritative for every user-facing copy field; style "
            "anchors or idea text in another language never change it. "
            "A saved canonical logo is an approved Studio identity, not an invented candidate asset. "
            "Photo backgrounds "
            "and the isolated sticker are exact Pexels-sourced assets with retained provenance; never "
            "describe them as generated graphics. Use only the assigned asset for candidate-sourced "
            "media. Do not evaluate other candidates or invent "
            "proof, urgency, people, IDs, or market evidence.\n\n"
            f"STRATEGY:\n{json.dumps(template.document, ensure_ascii=False, sort_keys=True)}"
        )

    @staticmethod
    def _creative_elements(creative_id: str, document: Mapping[str, Any]) -> list[dict[str, Any]]:
        elements: list[dict[str, Any]] = []
        for slot in COPY_ELEMENT_SLOTS:
            value = document[slot]
            elements.append({
                "element_id": new_uuid7(), "creative_id": creative_id,
                "slot": slot, "role": slot, "value": value,
            })
        for item in document["visual_components"]:
            elements.append({
                "element_id": new_uuid7(), "creative_id": creative_id,
                "slot": f"visual:{item['role']}", "role": item["role"], "value": item,
            })
        return elements

    def _generate_creative(
        self, *, run: Mapping[str, Any], brief: Mapping[str, Any],
        template: StrategyTemplate, asset_id: str | None, sticker_asset_id: str,
        alias: str,
        generation_kind: str = "initial", parent: Mapping[str, Any] | None = None,
        parameters: Mapping[str, int] | None = None,
    ) -> dict[str, Any]:
        provider_candidate_id = new_uuid7()
        creative_id = new_uuid7()
        sliders = dict(parameters or template.defaults)
        assigned_asset = None if asset_id is None else self.store.get("project_assets", asset_id)
        snapshot_lessons = self._lesson_texts(run["learning_snapshot_id"], "content-candidate-generator")
        saved_assets = run["studio_export"].get("assets") or []
        resolved = resolve_strategy_patch(
            run["studio_export"]["configuration"], template.template_id, sliders,
            sticker_available=True, photo_available=asset_id is not None,
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
        background = self.asset_bytes(asset_id) if asset_id is not None else None
        sticker_asset = (
            self.asset_bytes(sticker_asset_id)
            if resolved["configuration"]["sticker"]["enabled"] else None
        )
        if background is not None and background.get("source", {}).get("provider") != "pexels":
            raise ValueError("Universal experiment photo background must retain Pexels provenance")
        if sticker_asset is not None and (
            sticker_asset.get("source", {}).get("provider") != "pexels"
            or sticker_asset.get("source", {}).get("usage") != "sticker_object"
            or sticker_asset.get("source", {}).get("media_type") != "photograph"
            or sticker_asset.get("source", {}).get("photographic_object_evidence", {}).get("schema")
            != PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA
            or sticker_asset.get("source", {}).get("transformation")
            != "edge_color_soft_alpha_v1"
        ):
            raise ValueError("Universal experiment sticker must be an isolated Pexels photo object")
        if resolved["configuration"]["logo"]["enabled"] and logo_asset is None:
            raise ValueError("Universal experiment saved logo provenance is unavailable")
        render_contract = {
            "background": {
                "mode": resolved["configuration"]["background"]["mode"],
                "texture": resolved["configuration"]["background"].get("texture"),
                "source_asset_id": asset_id,
                "media_kind": resolved["media_mode"],
                "sha256": None if background is None else background["sha256"],
                "source": (
                    None if background is None
                    else deepcopy(background.get("source") or {
                        "origin": background.get("origin"),
                        "preset": background.get("preset"),
                        "variant_id": background.get("variant_id"),
                        "selection": background.get("selection"),
                    })
                ),
                "authority": (
                    "approved_pexels_photo" if asset_id is not None
                    else "deterministic_studio_texture"
                    if resolved["media_mode"] == "deterministic_texture"
                    else "native_solid_background"
                ),
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
                "source": (
                    None if sticker_asset is None
                    else deepcopy(sticker_asset.get("source") or {})
                ),
                "source_asset_id": None if sticker_asset is None else sticker_asset_id,
                "authority": "approved_pexels_photo_sticker" if sticker_asset else None,
            },
        }
        payload = {
            "candidate_id": provider_candidate_id,
            "approved_brief": brief["document"], "task": run["task"],
            "required_language": brief["document"]["language"],
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
            "owner_tune_instruction": run.get("revision_instruction"),
            "base_candidate": None if parent is None else {
                "creative_id": parent["creative_id"], "document": parent["document"],
                "elements": parent["elements"],
            },
        }
        result = self._provider_call(
            target_id=creative_id, mode="content_candidate_generation",
            system_prompt=self._candidate_prompt(template), input_payload=payload,
            output_schema=_candidate_schema(asset_id),
            idempotency_key=f"{run['run_id']}:{creative_id}:candidate",
            prompt_version="local-universal-candidate-v4",
            response_validator=lambda value: _validate_local_candidate(
                value, brief=brief["document"], asset_id=asset_id,
            ),
        )
        document = _validate_local_candidate(result["response"], brief=brief["document"], asset_id=asset_id)
        content = universal_content_from_generation(document, brief=brief["document"])
        if content["offer"] != brief["document"]["offer"] or content["cta"] != brief["document"]["cta"]:
            raise ValueError("Universal protected copy changed during content mapping")
        rendered = self.workspace.render_experiment(
            configuration=resolved["configuration"], content=content,
            background_asset=background, sticker_asset=sticker_asset,
        )
        rendered_asset_digests = rendered["resolved"].get("asset_sha256") or {}
        for role in ("background", "logo", "sticker"):
            contract_asset = render_contract[role]
            slot = (
                "background_image" if role == "background"
                and resolved["configuration"]["background"]["mode"] == "image"
                else contract_asset.get("slot")
            )
            if (
                (contract_asset.get("visible") or role == "background" and slot is not None)
                and rendered_asset_digests.get(slot)
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
        png_artifact = self.store.write_artifact("creative_renders", creative_id, "source.png", rendered["bytes"])
        jpeg_artifact = self.store.write_artifact("creative_renders", creative_id, "preview.jpg", jpeg["bytes"])
        elements = self._creative_elements(creative_id, document)
        for element in elements:
            self.store.append("elements", element["element_id"], {**element, "created_at": utc_now()})
            self.store.edge(source_id=creative_id, relation="contains", target_id=element["element_id"])
        creative = {
            "creative_id": creative_id, "run_id": run["run_id"], "slot": alias,
            "round": 0 if parent is None else int(parent.get("round", 0)) + 1,
            "generation_kind": generation_kind,
            "parent_creative_id": None if parent is None else parent["creative_id"],
            "template_id": template.template_id, "template_version": template.version,
            "template_sha256": template.digest, "parameters": sliders,
            "document": document, "document_sha256": sha256_json(document),
            "elements": elements, "provider_invocation_id": result["invocation_id"],
            "asset_id": asset_id,
            "sticker_asset_id": sticker_asset_id,
            "document_transformations": document_transformations,
            "experiment_adapter": {
                "profile": resolved["profile"], "version": resolved["adapter_version"],
                "media_mode": resolved["media_mode"],
            },
            "asset_provenance": ({
                key: background[key] for key in (
                    "source_asset_id", "sha256", "mime_type", "origin", "source",
                )
            } if asset_id is not None and background is not None else {
                "origin": "deterministic_studio_texture",
                "preset": resolved["configuration"]["background"]["texture"],
                "sha256": rendered["resolved"]["asset_sha256"]["background_texture"],
                "review_status": "deterministic_texture_direction",
                "no_synthetic_people": True,
            } if resolved["configuration"]["background"]["mode"] == "texture" else {
                "origin": "native_solid_background",
                "color": resolved["configuration"]["background"]["color"],
                "review_status": "native_solid_direction",
                "no_synthetic_people": True,
            }),
            "render_asset_provenance": render_contract,
            "universal_manifest": rendered["resolved"],
            "resolved_setting_patch": resolved["setting_patch"],
            "resolved_setting_deltas": resolved["setting_deltas"],
            "applied_layout_lessons": applied_layout_lessons,
            "layout_audit": audit,
            "png": {**png_artifact, "mime_type": "image/png", "width": 1080, "height": 1080},
            "preview": {
                **jpeg_artifact, "mime_type": "image/jpeg", "width": 1080, "height": 1080,
                "asset_url": f"/api/v1/content-runs/{run['run_id']}/creatives/{creative_id}/asset",
            },
            "configuration": resolved["configuration"], "content": content,
            "created_at": utc_now(),
        }
        creative["media_identity_sha256"] = sha256_json({
            "creative_id": creative_id, "asset_provenance": creative["asset_provenance"],
            "render_asset_provenance": creative["render_asset_provenance"],
        })
        self.store.append("creatives", creative_id, creative)
        self.store.edge(source_id=run["run_id"], relation="contains", target_id=creative_id)
        if parent is not None:
            self.store.edge(source_id=creative_id, relation="derived_from", target_id=parent["creative_id"])
        return creative

    def _deliver_review_notification(self, run_id: str, *, manual_retry: bool = False) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] != "awaiting_review":
            raise ValueError("review notification requires an awaiting-review run")
        if self.notifier is None:
            raise RuntimeError("Commander review-notification relay is not configured")
        existing_id = run.get("notification_receipt_id")
        if existing_id:
            receipt = self.store.get("notification_receipts", existing_id)
            if receipt["status"] == "delivered":
                return receipt
            if receipt["status"] == "ambiguous" and not manual_retry:
                return receipt
            if (
                receipt["status"] == "definite_failure"
                and not manual_retry and int(receipt["attempt_count"]) >= 3
            ):
                return receipt
        else:
            existing_id = new_uuid7()
            receipt = {
                "receipt_id": existing_id, "run_id": run_id, "status": "pending",
                "attempt_count": 0, "provider_message_id": None,
                "error_code": None, "error_message": None, "created_at": utc_now(),
                "updated_at": utc_now(),
            }
            self.store.append("notification_receipts", existing_id, receipt)
            self.store.append("runs", run_id, {
                **run, "notification_state": "pending",
                "notification_receipt_id": existing_id, "updated_at": utc_now(),
            })
        project = self._project(run["project_id"])
        event = {
            "schema": "ptw.owner-review-notification.v1",
            "notification_id": existing_id, "run_id": run_id,
            "project_id": run["project_id"], "project_name": project["name"],
            "platform": run["platform"], "creative_count": 5,
        }
        attempt: NotificationAttempt | None = None
        max_attempts = 1 if manual_retry else max(0, 3 - int(receipt["attempt_count"]))
        for _ in range(max_attempts):
            attempt = self.notifier.notify(event)
            receipt = {
                **receipt, "status": attempt.status,
                "attempt_count": int(receipt["attempt_count"]) + 1,
                "provider_message_id": attempt.provider_message_id,
                "error_code": attempt.error_code, "error_message": attempt.error_message,
                "updated_at": utc_now(),
            }
            self.store.append("notification_receipts", existing_id, receipt)
            if attempt.status != "definite_failure":
                break
        final = self.get_run(run_id)
        self.store.append("runs", run_id, {
            **final, "notification_state": receipt["status"], "updated_at": utc_now(),
        })
        return receipt

    def execute_run(self, run_id: str) -> dict[str, Any]:
        run_id = _uuid(run_id, "run_id")
        with self._execution_lock:
            with self._cancellation_lock:
                run = self.get_run(run_id)
                if run["status"] in {"awaiting_review", "approved", "superseded", "terminated"}:
                    return run
                cancel_event = threading.Event()
                self._cancellation_events[run_id] = cancel_event
            self._run_context.cancel_event = cancel_event
            try:
                brief = self.get_brief(run["brief_id"])
                self._checkpoint(run_id, "generating_creatives", 10, boundary="asset_resolution")
                parent = None
                if run["generation_kind"] == "tune":
                    parent = self.store.get("creatives", run["tuned_creative_id"])
                    asset_by_strategy = {parent["template_id"]: parent["asset_id"]}
                    sticker_asset_id = parent["sticker_asset_id"]
                else:
                    asset_by_strategy = self._resolve_candidate_assets(run, brief["document"])
                    sticker_asset_id = self._resolve_sticker_asset(run, brief["document"])
                resolved_run = self.get_run(run_id)
                self.store.append("runs", run_id, {
                    **resolved_run,
                    "resolved_asset_ids_by_strategy": dict(asset_by_strategy),
                    "resolved_sticker_asset_id": sticker_asset_id,
                    "updated_at": utc_now(),
                })
                self._raise_if_termination_requested(run_id)
                run = self.get_run(run_id)
                generated: list[dict[str, Any]] = []
                templates = (
                    [self.templates_by_id[parent["template_id"]]] if parent is not None
                    else list(self.templates)
                )
                for index, template in enumerate(templates, 1):
                    self._raise_if_termination_requested(run_id)
                    generated.append(self._generate_creative(
                        run=run, brief=brief, template=template,
                        asset_id=asset_by_strategy.get(template.template_id),
                        sticker_asset_id=sticker_asset_id,
                        alias=parent["slot"] if parent is not None else f"C{index}",
                        generation_kind=run["generation_kind"], parent=parent,
                        parameters=None if parent is None else parent["parameters"],
                    ))
                if parent is None and (
                    len(generated) != 5 or len({item["preview"]["sha256"] for item in generated}) != 5
                ):
                    raise ValueError("five review Creatives must have distinct deterministic renders")
                if parent is None:
                    review = generated
                else:
                    parent_run = self.get_run(run["parent_run_id"])
                    review = [
                        generated[0] if item == parent["creative_id"] else self.store.get("creatives", item)
                        for item in parent_run["review_creative_ids"]
                    ]
                if len(review) != 5 or len({item["creative_id"] for item in review}) != 5:
                    raise ValueError("review set must contain exactly five distinct Creatives")
                if run["generation_kind"] == "regenerate_all":
                    excluded = (run.get("revision_instruction") or {}).get("excluded_identities") or {}
                    generated_identities = {
                        "creative_ids": {item["creative_id"] for item in generated},
                        "document_sha256": {item["document_sha256"] for item in generated},
                        "render_sha256": {item["preview"]["sha256"] for item in generated},
                        "media_sha256": {item["media_identity_sha256"] for item in generated},
                        "provider_invocation_ids": {item["provider_invocation_id"] for item in generated},
                    }
                    for key, values in generated_identities.items():
                        if values & set(map(str, excluded.get(key) or [])):
                            raise ValueError(f"regenerate-all reused excluded {key}")
                diversity_audit = audit_creative_diversity(
                    review,
                    png_by_creative_id={
                        item["creative_id"]: self.store.artifact(
                            item["png"]["path"], expected_sha256=item["png"]["sha256"],
                        )
                        for item in review
                    },
                )
                if not diversity_audit["passed"]:
                    failed_gates = sorted(
                        key for key, passed in diversity_audit["gates"].items() if not passed
                    )
                    raise ValueError(
                        "five review Creatives are not visibly distinct: "
                        + ", ".join(failed_gates)
                    )
                with self._cancellation_lock:
                    self._raise_if_termination_requested(run_id)
                    awaiting = {
                        **self.get_run(run_id), "status": "awaiting_review",
                        "current_stage": "awaiting_review", "progress_percent": 100,
                        "generated_creative_ids": [item["creative_id"] for item in generated],
                        "review_creative_ids": [item["creative_id"] for item in review],
                        "diversity_audit": diversity_audit, "updated_at": utc_now(),
                    }
                    self.store.append("runs", run_id, awaiting)
                    if run.get("parent_run_id"):
                        parent_run = self.get_run(run["parent_run_id"])
                        if parent_run["status"] == "awaiting_review":
                            self.store.append("runs", parent_run["run_id"], {
                                **parent_run, "status": "superseded",
                                "superseded_by_run_id": run_id, "updated_at": utc_now(),
                            })
                        for action in self.store.list("review_actions"):
                            if action.get("child_run_id") == run_id and action["status"] == "processing":
                                self.store.append("review_actions", action["action_id"], {
                                    **action, "status": "completed", "updated_at": utc_now(),
                                })
                # Loopback review does not depend on production Telegram credentials.
                # When the existing Commander relay is explicitly configured, use it;
                # otherwise the authenticated five-card review remains the delivery path.
                if self.notifier is not None:
                    self._deliver_review_notification(run_id)
                return self.get_run(run_id)
            except Exception as error:
                with self._cancellation_lock:
                    current = self.get_run(run_id)
                    if cancel_event.is_set() or current["status"] == "terminated":
                        return current
                    failed = {
                        **current, "status": "failed", "current_stage": "failed",
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
                    for action in self.store.list("review_actions"):
                        if action.get("child_run_id") == run_id and action["status"] == "processing":
                            self.store.append("review_actions", action["action_id"], {
                                **action, "status": "failed",
                                "failure": {
                                    "error_code": type(error).__name__,
                                    "error_message": str(error)[:1000],
                                },
                                "updated_at": utc_now(),
                            })
                    return failed
            finally:
                if hasattr(self._run_context, "cancel_event"):
                    del self._run_context.cancel_event
                with self._cancellation_lock:
                    if self._cancellation_events.get(run_id) is cancel_event:
                        self._cancellation_events.pop(run_id, None)

    # Read models -----------------------------------------------------------------

    def list_runs(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        project_id = _uuid(project_id, "project_id")
        self._project(project_id)
        return [item for item in self.store.list("runs") if item["project_id"] == project_id][:limit]

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.store.get("runs", _uuid(run_id, "run_id"))

    def get_review(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] not in {"awaiting_review", "approved", "superseded"}:
            raise ValueError("local Result run has no reviewable Creative set")
        creatives = [self.store.get("creatives", item) for item in run["review_creative_ids"]]
        receipt = None
        if run.get("notification_receipt_id"):
            receipt = self.store.get("notification_receipts", run["notification_receipt_id"])
        return {
            "schema": "ptw.owner-creative-review.v1", "run": run,
            "creatives": creatives, "notification": receipt,
            "owner_actions": [
                item for item in self.store.list("review_actions") if item["run_id"] == run_id
            ],
            "applied_project_rules": [
                item for item in self.store.list("learning_rules")
                if item["project_id"] == run["project_id"]
            ],
        }

    def creative_asset(self, run_id: str, creative_id: str, *, source_png: bool = False) -> dict[str, Any]:
        run_id, creative_id = _uuid(run_id, "run_id"), _uuid(creative_id, "creative_id")
        creative = self.store.get("creatives", creative_id)
        run = self.get_run(run_id)
        if creative_id not in set(run.get("review_creative_ids") or []) and creative["run_id"] != run_id:
            raise KeyError("local Creative does not belong to the requested review set")
        artifact = creative["png"] if source_png else creative["preview"]
        return {
            "bytes": self.store.artifact(artifact["path"], expected_sha256=artifact["sha256"]),
            "mime_type": "image/png" if source_png else "image/jpeg", "sha256": artifact["sha256"],
        }

    # Owner actions, learning, and immutable release ------------------------------

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

    def _release(self, run: Mapping[str, Any], creative: Mapping[str, Any]) -> dict[str, Any]:
        existing = [item for item in self.store.list("releases") if item["run_id"] == run["run_id"]]
        if existing:
            return existing[0]
        release_id = new_uuid7()
        brief = self.get_brief(run["brief_id"])
        jpeg = self.creative_asset(run["run_id"], creative["creative_id"])["bytes"]
        png = self.creative_asset(run["run_id"], creative["creative_id"], source_png=True)["bytes"]
        sources = {
            "post.jpg": jpeg, "source.png": png,
            "caption.txt": (creative["document"]["caption"] + "\n").encode(),
            "alt-text.txt": (creative["document"]["alt_text"] + "\n").encode(),
            "product-brief.json": (json.dumps(brief, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
            "universal-manifest.json": (json.dumps({
                "configuration": creative["configuration"],
                "content": creative["content"],
                "component_manifest": creative["universal_manifest"],
                "layout_audit": creative["layout_audit"],
            }, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
            "asset-provenance.json": (json.dumps(creative["asset_provenance"], ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
            "owner-review.json": (json.dumps({
                "run_id": run["run_id"], "approved_creative_id": creative["creative_id"],
                "review_creative_ids": run["review_creative_ids"],
            }, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
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
            "creative_id": creative["creative_id"], "status": "ready",
            "platform": "instagram", "artifact": artifact,
            "package_sha256": artifact["sha256"], "file_digests": digest_manifest["files"],
            "download_count": 0, "created_at": utc_now(), "updated_at": utc_now(),
        }
        self.store.append("releases", release_id, release)
        self.store.edge(source_id=release_id, relation="derived_from", target_id=creative["creative_id"])
        return release

    def _feedback_and_weight(
        self, *, run: Mapping[str, Any], creative: Mapping[str, Any], decision: str,
        comment: str | None, requested_by: str, deltas: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        feedback_id, weight_id = new_uuid7(), new_uuid7()
        feedback = {
            "feedback_id": feedback_id, "run_id": run["run_id"],
            "creative_id": creative["creative_id"], "decision": decision,
            "comment": comment, "authority": "owner", "requested_by": requested_by,
            "created_at": utc_now(),
        }
        weight = {
            "weight_update_id": weight_id, "feedback_id": feedback_id,
            "creative_id": creative["creative_id"], "deltas": dict(deltas),
            "append_only": True, "created_at": utc_now(),
        }
        self.store.append("feedback", feedback_id, feedback)
        self.store.append("weight_updates", weight_id, weight)
        self.store.edge(source_id=feedback_id, relation="evaluates", target_id=creative["creative_id"])
        self.store.edge(source_id=feedback_id, relation="contains", target_id=weight_id)
        self.store.edge(source_id=weight_id, relation="adjusts", target_id=creative["creative_id"])
        return feedback, weight

    def _append_learning_rule(
        self, *, run: Mapping[str, Any], feedback_id: str, rule_type: str,
        strategy_id: str | None = None, instruction: str | None = None,
        layout_patch: Sequence[Mapping[str, Any]] = (), exclusions: Mapping[str, Any] | None = None,
        output_profile: str | None = None,
    ) -> dict[str, Any]:
        matching = [
            item for item in self.store.list("learning_rules")
            if item["project_id"] == run["project_id"]
            and item["rule_type"] == rule_type
            and item.get("strategy_id") == strategy_id
            and item.get("output_profile") == output_profile
        ]
        superseded = {str(item["supersedes_rule_id"]) for item in matching if item.get("supersedes_rule_id")}
        active = next((item for item in matching if item["rule_id"] not in superseded), None)
        rule_id = new_uuid7()
        body = {
            "rule_id": rule_id, "project_id": run["project_id"], "rule_type": rule_type,
            "strategy_id": strategy_id, "output_profile": output_profile,
            "instruction": instruction, "layout_patch": [dict(item) for item in layout_patch],
            "exclusions": dict(exclusions or {}),
            "supersedes_rule_id": None if active is None else active["rule_id"],
            "feedback_id": feedback_id, "created_at": utc_now(),
        }
        rule = {**body, "sha256": sha256_json(body)}
        self.store.append("learning_rules", rule_id, rule)
        self.store.edge(source_id=rule_id, relation="derived_from", target_id=feedback_id)
        if active is not None:
            self.store.edge(source_id=rule_id, relation="supersedes", target_id=active["rule_id"])
        return rule

    def _review_action(
        self, *, run: Mapping[str, Any], request_id: str, action_type: str,
        fingerprint: Mapping[str, Any], requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        request_fingerprint = {
            "run_id": run["run_id"], "action_type": action_type, **dict(fingerprint),
        }
        existing_action_id = self.store.request_target(
            scope="review-action", request_id=request_id, fingerprint=request_fingerprint,
        )
        if existing_action_id is not None:
            return self.store.get("review_actions", existing_action_id), False
        self._assert_actionable(run)
        creative_id = fingerprint.get("creative_id")
        if creative_id is not None and creative_id not in run["review_creative_ids"]:
            raise ValueError("selected Creative is not in this five-item review set")
        action_id, created = self.store.reserve_request(
            scope="review-action", request_id=request_id,
            fingerprint=request_fingerprint,
        )
        if not created:
            return self.store.get("review_actions", action_id), False
        action = {
            "action_id": action_id, "request_id": request_id, "run_id": run["run_id"],
            "action_type": action_type, "status": "processing", "requested_by": requested_by,
            **dict(fingerprint), "created_at": utc_now(), "updated_at": utc_now(),
        }
        self.store.append("review_actions", action_id, action)
        self.store.edge(source_id=run["run_id"], relation="contains", target_id=action_id)
        return action, True

    def _assert_actionable(self, run: Mapping[str, Any], *, current_action_id: str | None = None) -> None:
        if run["status"] != "awaiting_review":
            raise RuntimeError("owner review action is stale; this review set is no longer actionable")
        for action in self.store.list("review_actions"):
            if action["action_id"] == current_action_id:
                continue
            if action["run_id"] != run["run_id"] or action["status"] != "processing":
                continue
            child_id = action.get("child_run_id")
            if child_id and self.get_run(child_id)["status"] in {"failed", "terminated"}:
                continue
            raise RuntimeError("another owner review action is already in progress")

    def approve(
        self, run_id: str, *, request_id: str, creative_id: str, requested_by: str,
    ) -> dict[str, Any]:
        with self._execution_lock:
            run = self.get_run(run_id)
            request_id, creative_id = _uuid(request_id, "request_id"), _uuid(creative_id, "creative_id")
            action, created = self._review_action(
                run=run, request_id=request_id, action_type="approve",
                fingerprint={"creative_id": creative_id}, requested_by=requested_by,
            )
            if not created:
                return action["response"]
            self._assert_actionable(run, current_action_id=action["action_id"])
            if creative_id not in run["review_creative_ids"]:
                raise ValueError("approved Creative is not in this five-item review set")
            creative = self.store.get("creatives", creative_id)
            if not creative["layout_audit"]["passed"]:
                raise ValueError("approved Creative failed deterministic integrity checks")
            feedback, weight = self._feedback_and_weight(
                run=run, creative=creative, decision="accepted", comment=None,
                requested_by=requested_by,
                deltas={"strategy_id": creative["template_id"], "sliders": creative["parameters"]},
            )
            outcome_id = new_uuid7()
            outcome = {
                "outcome_id": outcome_id, "run_id": run_id, "creative_id": creative_id,
                "event_type": "owner_accepted", "source": "owner_local",
                "market_performance": False, "created_at": utc_now(),
            }
            self.store.append("outcomes", outcome_id, outcome)
            self.store.edge(source_id=outcome_id, relation="derived_from", target_id=feedback["feedback_id"])
            self._append_learning_rule(
                run=run, feedback_id=feedback["feedback_id"], rule_type="preferred_direction",
                strategy_id=creative["template_id"],
                instruction=f"Prefer owner-approved strategy {creative['template_id']} with its saved sliders.",
            )
            self._append_learning_rule(
                run=run, feedback_id=feedback["feedback_id"], rule_type="preferred_layout",
                strategy_id=creative["template_id"], output_profile=run["output_profile"],
                layout_patch=creative["resolved_setting_deltas"],
            )
            approval_id = new_uuid7()
            self.store.append("creative_approvals", approval_id, {
                "approval_id": approval_id, "creative_id": creative_id,
                "feedback_id": feedback["feedback_id"], "created_at": utc_now(),
            })
            self.store.edge(source_id=approval_id, relation="derived_from", target_id=feedback["feedback_id"])
            approved = {
                **run, "status": "approved", "current_stage": "approved",
                "approved_creative_id": creative_id, "review_action_id": action["action_id"],
                "updated_at": utc_now(),
            }
            self.store.append("runs", run_id, approved)
            release = self._release(approved, creative)
            approved = {**approved, "release_id": release["release_id"], "updated_at": utc_now()}
            self.store.append("runs", run_id, approved)
            response = {"run": approved, "release": release, "feedback": feedback, "weight_update": weight}
            self.store.append("review_actions", action["action_id"], {
                **action, "status": "completed", "response": response, "updated_at": utc_now(),
            })
            return response

    def tune(
        self, run_id: str, *, request_id: str, creative_id: str,
        comment: str, requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        with self._execution_lock:
            run = self.get_run(run_id)
            request_id, creative_id = _uuid(request_id, "request_id"), _uuid(creative_id, "creative_id")
            comment = _compact(comment, "tune comment", 3, 2000)
            action, created = self._review_action(
                run=run, request_id=request_id, action_type="tune",
                fingerprint={"creative_id": creative_id, "comment": comment},
                requested_by=requested_by,
            )
            if not created:
                return self.get_run(action["child_run_id"]), False
            self._assert_actionable(run, current_action_id=action["action_id"])
            if creative_id not in run["review_creative_ids"]:
                raise ValueError("tuned Creative is not in this five-item review set")
            creative = self.store.get("creatives", creative_id)
            feedback, _weight = self._feedback_and_weight(
                run=run, creative=creative, decision="tune_requested", comment=comment,
                requested_by=requested_by,
                deltas={"preferred_strategy_id": creative["template_id"], "preference": 1},
            )
            self._append_learning_rule(
                run=run, feedback_id=feedback["feedback_id"], rule_type="tune_instruction",
                strategy_id=creative["template_id"], instruction=comment,
            )
            revision = {
                "schema_version": 1, "feedback_id": feedback["feedback_id"],
                "parent_run_id": run_id, "creative_id": creative_id, "comment": comment,
            }
            child, child_created = self.create_run(
                request_id=request_id, brief_id=run["brief_id"], platform="instagram",
                studio_state_sha256=run["studio_state_sha256"], requested_by=requested_by,
                parent_run_id=run_id, revision_instruction=revision, immutable_base=creative,
            )
            self.store.edge(source_id=child["run_id"], relation="derived_from", target_id=feedback["feedback_id"])
            self.store.edge(source_id=child["run_id"], relation="derived_from", target_id=creative_id)
            self.store.append("review_actions", action["action_id"], {
                **action, "child_run_id": child["run_id"], "updated_at": utc_now(),
            })
            return child, child_created

    def regenerate_all(
        self, run_id: str, *, request_id: str, requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        with self._execution_lock:
            run = self.get_run(run_id)
            request_id = _uuid(request_id, "request_id")
            action, created = self._review_action(
                run=run, request_id=request_id, action_type="regenerate_all",
                fingerprint={}, requested_by=requested_by,
            )
            if not created:
                return self.get_run(action["child_run_id"]), False
            self._assert_actionable(run, current_action_id=action["action_id"])
            creatives = [self.store.get("creatives", item) for item in run["review_creative_ids"]]
            feedback_ids: list[str] = []
            for creative in creatives:
                feedback, _weight = self._feedback_and_weight(
                    run=run, creative=creative, decision="rejected", comment=None,
                    requested_by=requested_by, deltas={"preference": -1, "explore": True},
                )
                feedback_ids.append(feedback["feedback_id"])
            exclusions = {
                "creative_ids": [item["creative_id"] for item in creatives],
                "document_sha256": [item["document_sha256"] for item in creatives],
                "render_sha256": [item["preview"]["sha256"] for item in creatives],
                "media_sha256": [item["media_identity_sha256"] for item in creatives],
                "provider_invocation_ids": [item["provider_invocation_id"] for item in creatives],
            }
            self._append_learning_rule(
                run=run, feedback_id=feedback_ids[0], rule_type="exploration_exclusions",
                exclusions=exclusions,
            )
            child, child_created = self.create_run(
                request_id=request_id, brief_id=run["brief_id"], platform="instagram",
                studio_state_sha256=run["studio_state_sha256"], requested_by=requested_by,
                parent_run_id=run_id,
                revision_instruction={
                    "schema_version": 1, "action": "regenerate_all", "feedback_ids": feedback_ids,
                    "excluded_identities": exclusions,
                },
            )
            for feedback_id in feedback_ids:
                self.store.edge(source_id=child["run_id"], relation="derived_from", target_id=feedback_id)
            self.store.append("review_actions", action["action_id"], {
                **action, "child_run_id": child["run_id"], "feedback_ids": feedback_ids,
                "updated_at": utc_now(),
            })
            return child, child_created

    def retry_run(self, run_id: str, *, request_id: str, requested_by: str) -> tuple[dict[str, Any], bool]:
        parent = self.get_run(run_id)
        if parent["status"] not in {"failed", "terminated"}:
            raise ValueError("a local run can be retried only after failed or terminated generation")
        return self.create_run(
            request_id=request_id, brief_id=parent["brief_id"], platform="instagram",
            studio_state_sha256=parent["studio_state_sha256"], requested_by=requested_by,
            parent_run_id=parent.get("parent_run_id"),
            revision_instruction=parent.get("revision_instruction"),
            immutable_base=(
                None if parent.get("tuned_creative_id") is None
                else self.store.get("creatives", parent["tuned_creative_id"])
            ),
        )

    def retry_review_notification(self, run_id: str) -> dict[str, Any]:
        with self._execution_lock:
            return self._deliver_review_notification(run_id, manual_retry=True)

    def resume_review_notification(self, run_id: str) -> dict[str, Any]:
        with self._execution_lock:
            return self._deliver_review_notification(run_id, manual_retry=False)

    def release_download(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] != "approved" or not run.get("release_id"):
            raise ValueError("export package is locked until owner approval")
        release = self.store.get("releases", run["release_id"])
        data = self.store.artifact(release["artifact"]["path"], expected_sha256=release["package_sha256"])
        self.store.append("releases", release["release_id"], {
            **release, "download_count": int(release["download_count"]) + 1,
            "updated_at": utc_now(),
        })
        outcome_id = new_uuid7()
        self.store.append("outcomes", outcome_id, {
            "outcome_id": outcome_id, "run_id": run_id,
            "creative_id": run["approved_creative_id"],
            "event_type": "release_downloaded", "source": "owner_local",
            "market_performance": False, "created_at": utc_now(),
        })
        return {"bytes": data, "sha256": release["package_sha256"], "release_id": release["release_id"]}

    def learning_summary(self, project_id: str | None = None) -> dict[str, Any]:
        runs = self.store.list("runs")
        if project_id is not None:
            project_id = _uuid(project_id, "project_id")
            runs = [item for item in runs if item["project_id"] == project_id]
        summaries = [{
            "run_id": run["run_id"], "status": run["status"],
            "generation_kind": run["generation_kind"],
            "review_creative_ids": run.get("review_creative_ids") or [],
            "approved_creative_id": run.get("approved_creative_id"),
            "owner_actions": [
                item for item in self.store.list("review_actions") if item["run_id"] == run["run_id"]
            ],
            "owner_outcomes": [
                item for item in self.store.list("outcomes") if item["run_id"] == run["run_id"]
            ],
            "learning_snapshot_id": run["learning_snapshot_id"],
            "learning_snapshot_sha256": run["learning_snapshot_sha256"],
        } for run in runs]
        return {
            "schema": "ptw.local-learning-summary.v1", "market_performance": False,
            "runs": summaries,
            "project_rules": [
                item for item in self.store.list("learning_rules")
                if project_id is None or item["project_id"] == project_id
            ],
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
        notification_run_ids = [
            run["run_id"] for run in self.store.list("runs")
            if run.get("status") == "awaiting_review"
            and (
                run.get("notification_state") == "pending"
                or run.get("notification_state") == "definite_failure"
                and int(self.store.get(
                    "notification_receipts", run["notification_receipt_id"]
                )["attempt_count"]) < 3
            )
        ]
        return {
            "brief_ids": briefs, "run_ids": self.store.recover_interrupted(),
            "notification_run_ids": notification_run_ids,
        }
