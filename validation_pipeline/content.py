"""Generic contracts and deterministic context selection for Result generation.

The module deliberately contains no Instagram rendering or persistence.  It is
the channel-neutral boundary shared by every future content profile.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID

from .domain import (
    RATING_PATTERN, TESTIMONIAL_PATTERN, UNSUPPLIED_PROOF_PATTERN,
    require_language,
)


OUTPUT_PROFILES = (
    "marketing_copy_v1", "instagram_static_ad_v1", "tiktok_photo_post_v1",
)
SLIDER_NAMES = (
    "hook_pressure",
    "emotional_intensity",
    "conceptual_novelty",
    "information_density",
    "visual_complexity",
)
TEMPLATE_IDS = (
    "moment_tension",
    "contrast_reframe",
    "mechanism_proof",
    "human_story",
    "direct_offer",
)
ELEMENT_SLOTS = (
    "hook", "headline", "primary_text", "supporting_text", "offer", "cta",
    "caption", "alt_text", "desired_emotion", "visual_concept", "media_request",
    "background", "primary_subject", "headline_block", "supporting_text_block",
    "offer_block", "cta_block", "brand_mark", "badge", "decorative_element",
    "lighting_style", "composition",
)
REQUIRED_COPY_SLOTS = (
    "hook", "headline", "primary_text", "supporting_text", "offer", "cta",
    "caption", "alt_text", "desired_emotion", "visual_concept", "media_request",
)
VISUAL_ROLES = (
    "background", "primary_subject", "headline_block", "supporting_text_block",
    "offer_block", "cta_block", "brand_mark", "badge", "decorative_element",
    "lighting_style", "composition",
)
INSTAGRAM_REQUIRED_VISUAL_ROLES = (
    "background", "primary_subject", "headline_block", "supporting_text_block",
    "offer_block", "cta_block", "brand_mark", "lighting_style", "composition",
)
STATIC_SOCIAL_PROFILES = frozenset({
    "instagram_static_ad_v1", "tiktok_photo_post_v1",
})
MAX_WRITING_BUNDLE_TOKENS = 6_500
MAX_SYSTEM_CONTEXT_TOKENS = 8_000
URGENCY_PATTERN = re.compile(
    r"\b(?:act now|last chance|only \d+ left|ends today|limited time|hurry|"
    r"останній шанс|лише \d+ залиш|тільки сьогодні|поспіш)\b",
    re.IGNORECASE,
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def digest_locked_reference(path: Path) -> tuple[str, str]:
    """Read one reference only when its checked-in SHA-256 sidecar matches."""
    if not path.is_file():
        raise RuntimeError(f"required Result context reference is unavailable: {path}")
    digest_path = path.with_suffix(".sha256")
    if not digest_path.is_file():
        raise RuntimeError(f"required Result context digest is unavailable: {digest_path}")
    text = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode()).hexdigest()
    expected = digest_path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest != expected:
        raise RuntimeError(f"Result context reference digest mismatch: {path}")
    return text, digest


def estimate_tokens(value: str) -> int:
    """Return a deterministic conservative token estimate without a model tokenizer."""
    return math.ceil(len(value.encode("utf-8")) / 3.2)


def assert_honest_text(value: str) -> None:
    if (
        TESTIMONIAL_PATTERN.search(value)
        or RATING_PATTERN.search(value)
        or UNSUPPLIED_PROOF_PATTERN.search(value)
        or URGENCY_PATTERN.search(value)
    ):
        raise ValueError("content contains unsupported proof, urgency, scarcity, or testimonial language")


def _bounded_text(value: Any, name: str, *, minimum: int = 1, maximum: int) -> str:
    normalized = str(value or "").strip()
    if not minimum <= len(normalized) <= maximum:
        raise ValueError(f"{name} must contain {minimum}-{maximum} characters")
    assert_honest_text(normalized)
    return normalized


@dataclass(frozen=True, slots=True)
class StrategyTemplate:
    template_id: str
    version: int
    philosophy: str
    narrative_sequence: tuple[str, ...]
    visual_grammar: tuple[str, ...]
    defaults: Mapping[str, int]
    envelopes: Mapping[str, tuple[int, int]]
    strengths: tuple[str, ...]
    failure_modes: tuple[str, ...]
    prompt_fragment: str
    document: Mapping[str, Any]
    digest: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StrategyTemplate":
        expected = {
            "template_id", "version", "active", "philosophy", "narrative_sequence",
            "visual_grammar", "defaults", "envelopes", "strengths", "failure_modes",
            "prompt_fragment",
        }
        if set(value) != expected:
            raise ValueError("template document fields do not match v1")
        template_id = str(value["template_id"])
        if template_id not in TEMPLATE_IDS or value.get("active") is not True:
            raise ValueError("template must be one of the five active Result strategies")
        version = int(value["version"])
        if version != 3:
            raise ValueError("active strategy templates must use version 3")
        defaults = value.get("defaults")
        envelopes = value.get("envelopes")
        if not isinstance(defaults, Mapping) or set(defaults) != set(SLIDER_NAMES):
            raise ValueError("template defaults must define all five sliders")
        if not isinstance(envelopes, Mapping) or set(envelopes) != set(SLIDER_NAMES):
            raise ValueError("template envelopes must define all five sliders")
        normalized_defaults: dict[str, int] = {}
        normalized_envelopes: dict[str, tuple[int, int]] = {}
        for slider in SLIDER_NAMES:
            default = int(defaults[slider])
            envelope = envelopes[slider]
            if not isinstance(envelope, list) or len(envelope) != 2:
                raise ValueError(f"{slider} envelope must be [minimum, maximum]")
            low, high = int(envelope[0]), int(envelope[1])
            if not 0 <= low <= default <= high <= 100:
                raise ValueError(f"{slider} default must stay inside its 0-100 envelope")
            normalized_defaults[slider] = default
            normalized_envelopes[slider] = (low, high)
        sequence = tuple(str(item).strip() for item in value.get("narrative_sequence") or [])
        grammar = tuple(str(item).strip() for item in value.get("visual_grammar") or [])
        strengths = tuple(str(item).strip() for item in value.get("strengths") or [])
        failures = tuple(str(item).strip() for item in value.get("failure_modes") or [])
        if min(map(len, (sequence, grammar, strengths, failures)), default=0) < 1:
            raise ValueError("template strategy lists cannot be empty")
        document = json.loads(canonical_json(value))
        return cls(
            template_id=template_id,
            version=version,
            philosophy=_bounded_text(value["philosophy"], "template philosophy", maximum=1000),
            narrative_sequence=sequence,
            visual_grammar=grammar,
            defaults=normalized_defaults,
            envelopes=normalized_envelopes,
            strengths=strengths,
            failure_modes=failures,
            prompt_fragment=_bounded_text(value["prompt_fragment"], "template prompt fragment", maximum=3000),
            document=document,
            digest=sha256_json(document),
        )

    def validate_adjustment(self, current: Mapping[str, int], proposed: Mapping[str, int]) -> dict[str, int]:
        if set(current) != set(SLIDER_NAMES) or set(proposed) != set(SLIDER_NAMES):
            raise ValueError("slider adjustment must retain all five dimensions")
        changed: list[str] = []
        result: dict[str, int] = {}
        for slider in SLIDER_NAMES:
            before, after = int(current[slider]), int(proposed[slider])
            low, high = self.envelopes[slider]
            if not low <= after <= high:
                raise ValueError("owner tune slider values must stay inside the template envelope")
            if before != after:
                if abs(after - before) < 10 or (after - before) % 5:
                    raise ValueError("owner tune slider changes must move by a multiple of five and at least ten")
                changed.append(slider)
            result[slider] = after
        if not 1 <= len(changed) <= 2:
            raise ValueError("one owner tune adjustment may change one or two slider dimensions")
        return result

    def runtime_bands(self, values: Mapping[str, int]) -> dict[str, str]:
        descriptions = {
            "hook_pressure": ("calm invitation", "clear interruption", "sharp tension without false urgency"),
            "emotional_intensity": ("restrained warmth", "visible human stakes", "high but non-manipulative emotion"),
            "conceptual_novelty": ("familiar framing", "distinctive reframe", "surprising but relevant concept"),
            "information_density": ("one essential detail", "several concrete details", "dense process or proof"),
            "visual_complexity": ("one subject and minimal type", "layered but clear composition", "rich multi-frame treatment"),
        }
        result: dict[str, str] = {}
        for name in SLIDER_NAMES:
            value = int(values[name])
            band = 0 if value <= 33 else 1 if value <= 66 else 2
            result[name] = f"{value}/100 — {descriptions[name][band]}"
        return result


class TemplateRegistry:
    """Load exactly five immutable strategy YAML documents stored in Git.

    The checked-in documents use JSON syntax, which is a strict YAML subset and
    lets the runtime avoid a second parser dependency.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def load_active(self) -> tuple[StrategyTemplate, ...]:
        templates: list[StrategyTemplate] = []
        for path in sorted(self.directory.glob("*.yaml")):
            try:
                value = json.loads(path.read_text())
            except json.JSONDecodeError as error:
                raise ValueError(f"template {path.name} must use the supported JSON-compatible YAML form") from error
            if not isinstance(value, Mapping):
                raise ValueError(f"template {path.name} is not one document")
            if value.get("active") is True:
                templates.append(StrategyTemplate.from_dict(value))
        ids = [item.template_id for item in templates]
        if len(templates) != 5 or len(set(ids)) != 5 or set(ids) != set(TEMPLATE_IDS):
            raise ValueError("template registry must contain exactly five distinct active strategy IDs")
        ordered = tuple(sorted(templates, key=lambda item: TEMPLATE_IDS.index(item.template_id)))
        from .studio_templates import StudioTemplateRegistry
        StudioTemplateRegistry().load_active(ordered)
        return ordered


@dataclass(frozen=True, slots=True)
class CorpusExample:
    example_id: str
    excerpt: str
    source_project: str
    source_repository: str
    source_path: str
    source_commit: str
    excerpt_sha256: str
    language: str
    artifact_type: str
    output_profiles: tuple[str, ...]
    audience: tuple[str, ...]
    product: str
    funnel_stage: str
    techniques: tuple[str, ...]
    quality_tier: str
    restrictions: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CorpusExample":
        required = {
            "example_id", "excerpt", "source_project", "source_repository", "source_path",
            "source_commit", "excerpt_sha256", "language", "artifact_type", "output_profiles",
            "audience", "product", "funnel_stage", "techniques", "quality_tier", "restrictions",
        }
        if set(value) != required:
            raise ValueError("corpus example fields do not match v1")
        excerpt = str(value["excerpt"])
        if hashlib.sha256(excerpt.encode()).hexdigest() != value["excerpt_sha256"]:
            raise ValueError(f"corpus excerpt digest mismatch: {value['example_id']}")
        tier = str(value["quality_tier"])
        if tier not in {"canonical", "supporting", "negative"}:
            raise ValueError("unknown corpus quality tier")
        return cls(
            example_id=str(value["example_id"]), excerpt=excerpt,
            source_project=str(value["source_project"]),
            source_repository=str(value["source_repository"]),
            source_path=str(value["source_path"]), source_commit=str(value["source_commit"]),
            excerpt_sha256=str(value["excerpt_sha256"]), language=str(value["language"]),
            artifact_type=str(value["artifact_type"]),
            output_profiles=tuple(map(str, value["output_profiles"])),
            audience=tuple(map(str, value["audience"])), product=str(value["product"]),
            funnel_stage=str(value["funnel_stage"]), techniques=tuple(map(str, value["techniques"])),
            quality_tier=tier, restrictions=tuple(map(str, value["restrictions"])),
        )


class CorpusStore:
    def __init__(self, manifest_path: Path, examples_path: Path) -> None:
        self.manifest_path = manifest_path
        self.examples_path = examples_path

    def load(self) -> tuple[Mapping[str, Any], tuple[CorpusExample, ...], str]:
        manifest = json.loads(self.manifest_path.read_text())
        examples = tuple(
            CorpusExample.from_dict(json.loads(line))
            for line in self.examples_path.read_text().splitlines() if line.strip()
        )
        if int(manifest.get("example_count") or 0) != len(examples):
            raise ValueError("corpus manifest example count does not match examples.jsonl")
        ids = [item.example_id for item in examples]
        if len(ids) != len(set(ids)):
            raise ValueError("corpus example IDs must be unique")
        digest = hashlib.sha256(self.examples_path.read_bytes()).hexdigest()
        if manifest.get("examples_sha256") != digest:
            raise ValueError("corpus manifest digest does not match examples.jsonl")
        return manifest, examples, digest

    @staticmethod
    def retrieve(
        examples: Sequence[CorpusExample], *, language: str, output_profile: str,
        technique: str, audience: str, count: int = 6,
    ) -> tuple[CorpusExample, ...]:
        if not 4 <= count <= 6:
            raise ValueError("generator retrieval requires four to six examples")
        usable = [item for item in examples if item.quality_tier != "negative"]
        audience_words = {word for word in re.findall(r"\w+", audience.casefold()) if len(word) > 2}

        def rank(item: CorpusExample) -> tuple[Any, ...]:
            item_words = set(re.findall(r"\w+", " ".join(item.audience).casefold()))
            return (
                -(item.language == language),
                -(output_profile in item.output_profiles),
                -(technique in item.techniques),
                -len(audience_words & item_words),
                item.source_project,
                item.example_id,
            )

        selected: list[CorpusExample] = []
        per_project: dict[str, int] = {}
        for item in sorted(usable, key=rank):
            if per_project.get(item.source_project, 0) >= 2:
                continue
            selected.append(item)
            per_project[item.source_project] = per_project.get(item.source_project, 0) + 1
            if len(selected) == count:
                break
        if len(selected) < 4:
            raise ValueError("corpus cannot satisfy source-diverse retrieval")
        return tuple(selected)


@dataclass(frozen=True, slots=True)
class ContextBundleV1:
    document: Mapping[str, Any]
    digest: str
    writing_bundle_tokens: int
    system_context_tokens: int


class ContentContextAssembler:
    """Build one complete, bounded and reproducible context snapshot."""

    def __init__(
        self, *, generator_skill_path: Path,
        template_registry: TemplateRegistry, corpus_store: CorpusStore,
    ) -> None:
        self.generator_skill_path = generator_skill_path
        self.template_registry = template_registry
        self.corpus_store = corpus_store

    @staticmethod
    def _read_required(paths: Iterable[Path]) -> tuple[str, ...]:
        values: list[str] = []
        for path in paths:
            if not path.is_file():
                raise RuntimeError(f"required Result context reference is unavailable: {path}")
            values.append(path.read_text())
        return tuple(values)

    @staticmethod
    def _technique_name(task: str, output_profile: str) -> str:
        normalized = task.casefold()
        if any(marker in normalized for marker in (
            "founder", "origin story", "personal story", "narrative", "заснов", "істор",
        )):
            return "landing-and-story.md"
        if any(marker in normalized for marker in ("hook", "headline", "заголов", "гачок")):
            return "hooks.md"
        if any(marker in normalized for marker in ("concise", "short", "brief", "корот", "стисл")):
            return "concise-product-copy.md"
        return "ad-copy.md" if output_profile in STATIC_SOCIAL_PROFILES else "concise-product-copy.md"

    def assemble(
        self, *, brief: Mapping[str, Any], task: str, output_profile: str,
        brand_kit: Mapping[str, Any], approved_sources: Sequence[Mapping[str, Any]],
        tool_catalog: Mapping[str, Any], template: StrategyTemplate,
        revision_instruction: Mapping[str, Any] | None = None,
    ) -> ContextBundleV1:
        if output_profile not in OUTPUT_PROFILES:
            raise ValueError("unknown content output profile")
        if not brief.get("approved") or brief.get("status") != "completed" or not brief.get("document"):
            raise ValueError("Result generation requires one approved completed Product Brief")
        normalized_task = _bounded_text(task, "task", maximum=4_000)
        reference_root = self.generator_skill_path.parent / "references"
        technique_name = self._technique_name(normalized_task, output_profile)
        paths = (
            self.generator_skill_path,
            reference_root / "writing-principles.md",
            reference_root / "anti-patterns.md",
            reference_root / "techniques" / technique_name,
            reference_root / "owner-lessons.md",
        )
        generator_core, principles, anti_patterns, technique, owner_lessons = self._read_required(paths)
        post_copy_style = ""
        post_copy_style_sha256 = ""
        if output_profile in STATIC_SOCIAL_PROFILES:
            post_copy_style, post_copy_style_sha256 = digest_locked_reference(
                reference_root / "post-copy-style.md"
            )
        manifest, examples, corpus_digest = self.corpus_store.load()
        selected = self.corpus_store.retrieve(
            examples,
            language=str(brief["document"].get("language") or "uk"),
            output_profile=output_profile,
            technique=technique_name.removesuffix(".md"),
            audience=str(brief["document"].get("target_audience") or ""),
        )
        writing_sections = tuple(item for item in (
            generator_core, principles, anti_patterns, technique, post_copy_style,
            owner_lessons, template.prompt_fragment,
        ) if item)
        writing_bundle = "\n\n".join((*writing_sections, *(item.excerpt for item in selected)))
        writing_tokens = estimate_tokens(writing_bundle)
        system_context = "\n\n".join((*writing_sections, *(item.excerpt for item in selected)))
        system_tokens = estimate_tokens(system_context)
        if writing_tokens > MAX_WRITING_BUNDLE_TOKENS or system_tokens > MAX_SYSTEM_CONTEXT_TOKENS:
            raise ValueError(
                f"Result context overflow: writing={writing_tokens}, system={system_tokens}; context was not truncated"
            )
        source_snapshot = [{
            key: item.get(key) for key in (
                "source_asset_id", "origin", "title", "mime_type", "width", "height",
                "provider", "external_id", "bytes_sha256", "license", "attribution", "metadata",
            )
        } for item in approved_sources]
        selected_records = [{
            "example_id": item.example_id,
            "excerpt": item.excerpt,
            "excerpt_sha256": item.excerpt_sha256,
            "source_project": item.source_project,
            "source_repository": item.source_repository,
            "source_path": item.source_path,
            "source_commit": item.source_commit,
            "language": item.language,
            "artifact_type": item.artifact_type,
            "output_profiles": list(item.output_profiles),
            "audience": list(item.audience),
            "product": item.product,
            "funnel_stage": item.funnel_stage,
            "techniques": list(item.techniques),
            "quality_tier": item.quality_tier,
            "restrictions": list(item.restrictions),
        } for item in selected]
        document = {
            "schema_version": 1,
            "brief": {
                "brief_id": brief["brief_id"], "project_id": brief["project_id"],
                "document": dict(brief["document"]), "document_sha256": brief["document_sha256"],
            },
            "task": normalized_task,
            "output_profile": output_profile,
            "brand_kit": {
                "brand_kit_id": brand_kit["brand_kit_id"],
                "document": dict(brand_kit["document"]),
                "document_sha256": brand_kit["document_sha256"],
            },
            "approved_sources": source_snapshot,
            "tool_catalog": dict(tool_catalog),
            "tool_catalog_sha256": sha256_json(tool_catalog),
            "template": {
                "template_id": template.template_id, "version": template.version,
                "digest": template.digest, "document": dict(template.document),
                "runtime_bands": template.runtime_bands(template.defaults),
            },
            "writing": {
                "generator_core": generator_core, "principles": principles,
                "anti_patterns": anti_patterns, "technique": technique,
                "owner_lessons": owner_lessons,
                "example_ids": [item.example_id for item in selected],
                "examples": [item.excerpt for item in selected],
                "example_records": selected_records,
                "selection_order": [item.example_id for item in selected],
                "technique_id": technique_name.removesuffix(".md"),
                "writing_bundle_tokens": writing_tokens,
                **({"post_copy_style": post_copy_style} if post_copy_style else {}),
            },
            "versions": {
                "generator_skill_sha256": hashlib.sha256(generator_core.encode()).hexdigest(),
                "corpus_version": int(manifest["version"]), "corpus_sha256": corpus_digest,
                **({
                    "post_copy_style_sha256": post_copy_style_sha256,
                } if post_copy_style else {}),
            },
            "source_policy": {
                "raw_idea": "excluded", "research": "excluded", "prior_outputs": "excluded",
                "owner_history": "excluded", "performance_data": "excluded",
                "synthetic_people_faces": "prohibited",
            },
        }
        if revision_instruction is not None:
            expected = {"schema_version", "feedback_id", "parent_run_id", "creative_id", "comment"}
            if set(revision_instruction) != expected or int(revision_instruction["schema_version"]) != 1:
                raise ValueError("revision instruction fields do not match v1")
            comment = " ".join(str(revision_instruction["comment"] or "").split())
            if not 3 <= len(comment) <= 2_000:
                raise ValueError("revision comment must contain 3-2000 characters")
            normalized_revision = {
                "schema_version": 1,
                "feedback_id": str(UUID(str(revision_instruction["feedback_id"]))),
                "parent_run_id": str(UUID(str(revision_instruction["parent_run_id"]))),
                "creative_id": str(UUID(str(revision_instruction["creative_id"]))),
                "comment": comment,
            }
            document["revision_instruction"] = normalized_revision
            document["source_policy"] = {
                **document["source_policy"],
                "selected_revision_feedback": "included_exactly",
            }
        return ContextBundleV1(document, sha256_json(document), writing_tokens, system_tokens)

    def assemble_run(
        self, *, brief: Mapping[str, Any], task: str, output_profile: str,
        brand_kit: Mapping[str, Any], approved_sources: Sequence[Mapping[str, Any]],
        tool_catalog: Mapping[str, Any], templates: Sequence[StrategyTemplate],
        revision_instruction: Mapping[str, Any] | None = None,
    ) -> ContextBundleV1:
        if len(templates) != 5 or {item.template_id for item in templates} != set(TEMPLATE_IDS):
            raise ValueError("a Result run context requires the five active strategy templates")
        bundles = [
            self.assemble(
                brief=brief, task=task, output_profile=output_profile, brand_kit=brand_kit,
                approved_sources=approved_sources, tool_catalog=tool_catalog, template=template,
                revision_instruction=revision_instruction,
            )
            for template in templates
        ]
        first = bundles[0].document
        from .studio_templates import StudioTemplateRegistry
        studio_output_profile = (
            output_profile if output_profile in STATIC_SOCIAL_PROFILES
            else "instagram_static_ad_v1"
        )
        studio_templates = {
            item.template_id: item
            for item in StudioTemplateRegistry(output_profile=studio_output_profile).load_active(templates)
        }
        document = {
            "schema_version": 1,
            "brief": first["brief"], "task": first["task"],
            "output_profile": first["output_profile"], "brand_kit": first["brand_kit"],
            "approved_sources": first["approved_sources"], "tool_catalog": first["tool_catalog"],
            "tool_catalog_sha256": first["tool_catalog_sha256"],
            "source_policy": first["source_policy"], "versions": first["versions"],
            "candidate_contexts": {
                template.template_id: {
                    **dict(bundle.document),
                    "studio_template": {
                        "template_id": studio_templates[template.template_id].template_id,
                        "version": studio_templates[template.template_id].version,
                        "digest": studio_templates[template.template_id].digest,
                        "document": dict(studio_templates[template.template_id].document),
                    },
                }
                for template, bundle in zip(templates, bundles)
            },
            "template_versions": [{
                "template_id": template.template_id, "version": template.version,
                "digest": template.digest, "defaults": dict(template.defaults),
                "studio_template_version": studio_templates[template.template_id].version,
                "studio_template_sha256": studio_templates[template.template_id].digest,
                "envelopes": {name: list(bounds) for name, bounds in template.envelopes.items()},
            } for template in templates],
        }
        if "revision_instruction" in first:
            document["revision_instruction"] = first["revision_instruction"]
        return ContextBundleV1(
            document=document, digest=sha256_json(document),
            writing_bundle_tokens=max(item.writing_bundle_tokens for item in bundles),
            system_context_tokens=max(item.system_context_tokens for item in bundles),
        )

@dataclass(frozen=True, slots=True)
class CandidateV2:
    value: Mapping[str, Any]
    digest: str

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, brief: Mapping[str, Any], output_profile: str,
        allowed_source_ids: Sequence[str] | None = None,
        approved_asset_ids: Sequence[str] | None = None,
    ) -> "CandidateV2":
        expected = {
            "schema_version", "hook", "headline", "primary_text", "supporting_text",
            "offer", "cta", "caption", "alt_text", "desired_emotion", "visual_concept",
            "media_request", "visual_components",
        }
        if set(value) != expected or value.get("schema_version") != 2:
            raise ValueError("CandidateV2 fields or schema version do not match")
        if output_profile not in OUTPUT_PROFILES:
            raise ValueError("unknown content output profile")
        limits = {
            "hook": 240, "headline": 180, "primary_text": 1200, "supporting_text": 800,
            "offer": 500, "cta": 200, "caption": 2200, "alt_text": 1000,
            "desired_emotion": 160, "visual_concept": 1200,
        }
        normalized = {"schema_version": 2}
        for name, limit in limits.items():
            normalized[name] = _bounded_text(value[name], name, maximum=limit)
        document = brief.get("document") or brief
        if normalized["offer"] != document.get("offer") or normalized["cta"] != document.get("cta"):
            raise ValueError("candidate must preserve the exact Product Brief offer and CTA")
        require_language(
            str(document.get("language") or ""),
            [normalized[name] for name in (
                "hook", "headline", "primary_text", "supporting_text",
                "offer", "cta", "caption", "alt_text",
            )],
            "candidate user-facing copy",
        )
        raw_media = value.get("media_request")
        media_fields = {"kind", "query", "source_asset_id", "reason"}
        if not isinstance(raw_media, Mapping) or set(raw_media) != media_fields:
            raise ValueError("media_request fields do not match v1")
        kind = str(raw_media.get("kind") or "")
        if kind not in {"none", "approved_asset", "pexels_real_photo", "non_human_graphic"}:
            raise ValueError("candidate requested an unsupported media kind")
        source_asset_id = raw_media.get("source_asset_id")
        if source_asset_id is not None:
            try:
                source_asset_id = str(UUID(str(source_asset_id)))
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError(
                    "media_request.source_asset_id must be a server-supplied UUID"
                ) from error
        allowed_assets = (
            None if approved_asset_ids is None
            else {str(UUID(str(item))) for item in approved_asset_ids}
        )
        if source_asset_id is not None and allowed_assets is not None and source_asset_id not in allowed_assets:
            raise ValueError("media_request.source_asset_id was not supplied as an approved Project asset")
        if kind == "approved_asset" and source_asset_id is None:
            raise ValueError("approved_asset media requests require a source_asset_id")
        if kind != "approved_asset" and source_asset_id is not None:
            raise ValueError("only approved_asset media requests may identify a source asset")
        if output_profile == "marketing_copy_v1" and kind != "none":
            raise ValueError("the marketing copy profile cannot request visual media")
        if output_profile in STATIC_SOCIAL_PROFILES and kind == "none":
            raise ValueError("a static social profile requires approved real or non-human media")
        normalized["media_request"] = {
            "kind": kind,
            "query": str(raw_media.get("query") or "").strip()[:300],
            "source_asset_id": source_asset_id,
            "reason": _bounded_text(raw_media.get("reason"), "media request reason", maximum=500),
        }
        raw_components = value.get("visual_components")
        if not isinstance(raw_components, list) or len(raw_components) > 32:
            raise ValueError("visual_components must be a bounded list")
        components: list[dict[str, Any]] = []
        seen_roles: set[str] = set()
        allowed_sources = (
            None if allowed_source_ids is None
            else {str(UUID(str(item))) for item in allowed_source_ids}
        )
        for index, raw in enumerate(raw_components):
            if not isinstance(raw, Mapping) or set(raw) != {"role", "content", "source_ids"}:
                raise ValueError(f"visual_components[{index}] fields do not match v1")
            role = str(raw.get("role") or "")
            if role not in VISUAL_ROLES:
                raise ValueError("unknown visual component role")
            if role != "decorative_element" and role in seen_roles:
                raise ValueError("required visual component roles must be unique")
            seen_roles.add(role)
            try:
                source_ids = [str(UUID(str(item))) for item in raw.get("source_ids") or []]
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError(
                    f"visual_components[{index}].source_ids must contain only server-supplied UUIDs"
                ) from error
            if allowed_sources is not None and any(item not in allowed_sources for item in source_ids):
                raise ValueError(
                    f"visual_components[{index}].source_ids contains an identifier not supplied by the server"
                )
            components.append({
                "role": role,
                "content": _bounded_text(raw.get("content"), f"visual_components[{index}].content", maximum=1000),
                "source_ids": source_ids,
            })
        if output_profile in STATIC_SOCIAL_PROFILES:
            required_visuals = set(INSTAGRAM_REQUIRED_VISUAL_ROLES)
            if required_visuals - seen_roles:
                raise ValueError("static social candidate is missing required structured visual roles")
        elif components:
            raise ValueError("the marketing copy profile cannot return visual components")
        normalized["visual_components"] = components
        return cls(normalized, sha256_json(normalized))


def candidate_output_schema(
    *, output_profile: str, allowed_source_ids: Sequence[str] = (),
    approved_asset_ids: Sequence[str] = (),
) -> dict[str, Any]:
    if output_profile not in OUTPUT_PROFILES:
        raise ValueError("unknown content output profile")
    allowed_sources = sorted({str(UUID(str(item))) for item in allowed_source_ids})
    approved_assets = sorted({str(UUID(str(item))) for item in approved_asset_ids})
    visual_roles = (
        INSTAGRAM_REQUIRED_VISUAL_ROLES
        if output_profile in STATIC_SOCIAL_PROFILES else VISUAL_ROLES
    )
    visual_count = (
        len(INSTAGRAM_REQUIRED_VISUAL_ROLES)
        if output_profile in STATIC_SOCIAL_PROFILES else 0
    )
    text = {"type": "string", "minLength": 1}
    return {
        "type": "object", "additionalProperties": False,
        "required": [
            "schema_version", "hook", "headline", "primary_text", "supporting_text", "offer",
            "cta", "caption", "alt_text", "desired_emotion", "visual_concept",
            "media_request", "visual_components",
        ],
        "properties": {
            "schema_version": {"type": "integer", "enum": [2]},
            **{name: text for name in (
                "hook", "headline", "primary_text", "supporting_text", "offer", "cta",
                "caption", "alt_text", "desired_emotion", "visual_concept",
            )},
            "media_request": {
                "type": "object", "additionalProperties": False,
                "required": ["kind", "query", "source_asset_id", "reason"],
                "properties": {
                    "kind": {"type": "string", "enum": [
                        "none", "approved_asset", "pexels_real_photo", "non_human_graphic",
                    ]},
                    "query": {"type": "string"},
                    "source_asset_id": {
                        "type": ["string", "null"], "enum": [None, *approved_assets],
                    },
                    "reason": text,
                },
            },
            "visual_components": {
                "type": "array", "minItems": visual_count, "maxItems": visual_count,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["role", "content", "source_ids"],
                    "properties": {
                        "role": {"type": "string", "enum": list(visual_roles)},
                        "content": text,
                        "source_ids": {
                            "type": "array",
                            "items": {"type": "string", "enum": allowed_sources},
                        },
                    },
                },
            },
        },
    }
