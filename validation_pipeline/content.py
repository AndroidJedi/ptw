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

from .domain import RATING_PATTERN, TESTIMONIAL_PATTERN, UNSUPPLIED_PROOF_PATTERN


OUTPUT_PROFILES = ("marketing_copy_v1", "instagram_static_ad_v1")
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
ACTION_TYPES = (
    "recompose", "regenerate_elements", "rerun_template", "discard", "select_final",
)
MAX_WRITING_BUNDLE_TOKENS = 5_500
MAX_SYSTEM_CONTEXT_TOKENS = 8_000
MAX_ACTIVE_BY_PASS = {1: 5, 2: 5, 3: 2}
HARD_GATES = (
    "task_brief_relevance", "exact_offer_cta", "language_required_fields",
    "honest_claims", "project_brand_media_tools", "one_coherent_message",
    "no_synthetic_people_faces", "safe_crop_layout", "protected_copy_legible",
    "caption_alt_text_accessible",
)
WEIGHTS = {
    "task_brief_suitability": 0.20,
    "hook_strength": 0.15,
    "message_clarity": 0.15,
    "persuasion_action": 0.15,
    "coherence": 0.15,
    "specificity_credibility": 0.10,
    "composition_legibility": 0.05,
    "originality_tone": 0.05,
}
URGENCY_PATTERN = re.compile(
    r"\b(?:act now|last chance|only \d+ left|ends today|limited time|hurry|"
    r"останній шанс|лише \d+ залиш|тільки сьогодні|поспіш)\b",
    re.IGNORECASE,
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


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
        if version < 1:
            raise ValueError("template version must be a positive integer")
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
                raise ValueError("critic slider values must stay inside the template envelope")
            if before != after:
                if abs(after - before) < 10 or (after - before) % 5:
                    raise ValueError("critic slider changes must move by a multiple of five and at least ten")
                changed.append(slider)
            result[slider] = after
        if not 1 <= len(changed) <= 2:
            raise ValueError("one critic adjustment may change one or two slider dimensions")
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
        return tuple(sorted(templates, key=lambda item: TEMPLATE_IDS.index(item.template_id)))


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
        self, *, generator_skill_path: Path, critic_skill_path: Path,
        template_registry: TemplateRegistry, corpus_store: CorpusStore,
    ) -> None:
        self.generator_skill_path = generator_skill_path
        self.critic_skill_path = critic_skill_path
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
        return "ad-copy.md" if output_profile == "instagram_static_ad_v1" else "concise-product-copy.md"

    def assemble(
        self, *, brief: Mapping[str, Any], task: str, output_profile: str,
        brand_kit: Mapping[str, Any], approved_sources: Sequence[Mapping[str, Any]],
        tool_catalog: Mapping[str, Any], template: StrategyTemplate,
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
        critic_reference_root = self.critic_skill_path.parent / "references"
        critic_parts = self._read_required((
            self.critic_skill_path,
            critic_reference_root / "evaluation-contract.md",
            critic_reference_root / "owner-lessons.md",
        ))
        critic_snapshot = "\n\n".join(critic_parts)
        manifest, examples, corpus_digest = self.corpus_store.load()
        selected = self.corpus_store.retrieve(
            examples,
            language=str(brief["document"].get("language") or "uk"),
            output_profile=output_profile,
            technique=technique_name.removesuffix(".md"),
            audience=str(brief["document"].get("target_audience") or ""),
        )
        writing_sections = (
            generator_core, principles, anti_patterns, technique, owner_lessons,
            template.prompt_fragment,
        )
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
            },
            "versions": {
                "generator_skill_sha256": hashlib.sha256(generator_core.encode()).hexdigest(),
                "critic_skill_sha256": hashlib.sha256(critic_snapshot.encode()).hexdigest(),
                "corpus_version": int(manifest["version"]), "corpus_sha256": corpus_digest,
            },
            "source_policy": {
                "raw_idea": "excluded", "research": "excluded", "prior_outputs": "excluded",
                "owner_history": "excluded", "performance_data": "excluded",
                "synthetic_people_faces": "prohibited",
            },
        }
        return ContextBundleV1(document, sha256_json(document), writing_tokens, system_tokens)

    def assemble_run(
        self, *, brief: Mapping[str, Any], task: str, output_profile: str,
        brand_kit: Mapping[str, Any], approved_sources: Sequence[Mapping[str, Any]],
        tool_catalog: Mapping[str, Any], templates: Sequence[StrategyTemplate],
    ) -> ContextBundleV1:
        if len(templates) != 5 or {item.template_id for item in templates} != set(TEMPLATE_IDS):
            raise ValueError("a Result run context requires the five active strategy templates")
        bundles = [
            self.assemble(
                brief=brief, task=task, output_profile=output_profile, brand_kit=brand_kit,
                approved_sources=approved_sources, tool_catalog=tool_catalog, template=template,
            )
            for template in templates
        ]
        first = bundles[0].document
        critic_context = self.critic_context()
        document = {
            "schema_version": 1,
            "brief": first["brief"], "task": first["task"],
            "output_profile": first["output_profile"], "brand_kit": first["brand_kit"],
            "approved_sources": first["approved_sources"], "tool_catalog": first["tool_catalog"],
            "tool_catalog_sha256": first["tool_catalog_sha256"],
            "source_policy": first["source_policy"], "versions": first["versions"],
            "critic_context": critic_context,
            "candidate_contexts": {
                template.template_id: bundle.document for template, bundle in zip(templates, bundles)
            },
            "template_versions": [{
                "template_id": template.template_id, "version": template.version,
                "digest": template.digest, "defaults": dict(template.defaults),
                "envelopes": {name: list(bounds) for name, bounds in template.envelopes.items()},
            } for template in templates],
        }
        document["versions"] = {
            **dict(document["versions"]),
            "critic_context_sha256": critic_context["context_sha256"],
        }
        return ContextBundleV1(
            document=document, digest=sha256_json(document),
            writing_bundle_tokens=max(item.writing_bundle_tokens for item in bundles),
            system_context_tokens=max(item.system_context_tokens for item in bundles),
        )

    def critic_context(self) -> Mapping[str, Any]:
        reference_root = self.generator_skill_path.parent / "references"
        critic, evaluation_contract, owner_lessons, principles, anti_patterns = self._read_required((
            self.critic_skill_path,
            self.critic_skill_path.parent / "references" / "evaluation-contract.md",
            self.critic_skill_path.parent / "references" / "owner-lessons.md",
            reference_root / "writing-principles.md",
            reference_root / "anti-patterns.md",
        ))
        _, examples, corpus_digest = self.corpus_store.load()
        anchors = sorted(
            (item for item in examples if item.quality_tier == "canonical" and "critic_anchor" in item.techniques),
            key=lambda item: item.example_id,
        )[:2]
        if len(anchors) != 2:
            raise ValueError("critic context requires exactly two neutral anchor examples")
        document = {
            "critic_core": critic, "evaluation_contract": evaluation_contract,
            "owner_lessons": owner_lessons,
            "principles": principles, "anti_patterns": anti_patterns,
            "anchors": [{"example_id": item.example_id, "excerpt": item.excerpt} for item in anchors],
            "corpus_sha256": corpus_digest,
        }
        tokens = estimate_tokens("\n\n".join((
            critic, evaluation_contract, owner_lessons, principles, anti_patterns,
            *(item.excerpt for item in anchors),
        )))
        if tokens > MAX_SYSTEM_CONTEXT_TOKENS:
            raise ValueError(f"Result critic context overflow: system={tokens}; context was not truncated")
        return {
            **document,
            "system_context_tokens": tokens,
            "context_sha256": sha256_json(document),
        }


@dataclass(frozen=True, slots=True)
class CandidateV2:
    value: Mapping[str, Any]
    digest: str

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, brief: Mapping[str, Any], output_profile: str,
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
        raw_media = value.get("media_request")
        media_fields = {"kind", "query", "source_asset_id", "reason"}
        if not isinstance(raw_media, Mapping) or set(raw_media) != media_fields:
            raise ValueError("media_request fields do not match v1")
        kind = str(raw_media.get("kind") or "")
        if kind not in {"none", "approved_asset", "pexels_real_photo", "non_human_graphic"}:
            raise ValueError("candidate requested an unsupported media kind")
        source_asset_id = raw_media.get("source_asset_id")
        if source_asset_id is not None:
            source_asset_id = str(UUID(str(source_asset_id)))
        if kind == "approved_asset" and source_asset_id is None:
            raise ValueError("approved_asset media requests require a source_asset_id")
        if kind != "approved_asset" and source_asset_id is not None:
            raise ValueError("only approved_asset media requests may identify a source asset")
        if output_profile == "marketing_copy_v1" and kind != "none":
            raise ValueError("the marketing copy profile cannot request visual media")
        if output_profile == "instagram_static_ad_v1" and kind == "none":
            raise ValueError("the Instagram profile requires approved real or non-human media")
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
        for index, raw in enumerate(raw_components):
            if not isinstance(raw, Mapping) or set(raw) != {"role", "content", "source_ids"}:
                raise ValueError(f"visual_components[{index}] fields do not match v1")
            role = str(raw.get("role") or "")
            if role not in VISUAL_ROLES:
                raise ValueError("unknown visual component role")
            if role != "decorative_element" and role in seen_roles:
                raise ValueError("required visual component roles must be unique")
            seen_roles.add(role)
            source_ids = [str(UUID(str(item))) for item in raw.get("source_ids") or []]
            components.append({
                "role": role,
                "content": _bounded_text(raw.get("content"), f"visual_components[{index}].content", maximum=1000),
                "source_ids": source_ids,
            })
        if output_profile == "instagram_static_ad_v1":
            required_visuals = {
                "background", "primary_subject", "headline_block", "supporting_text_block",
                "offer_block", "cta_block", "brand_mark", "lighting_style", "composition",
            }
            if required_visuals - seen_roles:
                raise ValueError("Instagram candidate is missing required structured visual roles")
        elif components:
            raise ValueError("the marketing copy profile cannot return visual components")
        normalized["visual_components"] = components
        return cls(normalized, sha256_json(normalized))


def candidate_output_schema() -> dict[str, Any]:
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
                    "source_asset_id": {"type": ["string", "null"]},
                    "reason": text,
                },
            },
            "visual_components": {
                "type": "array", "maxItems": 32,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["role", "content", "source_ids"],
                    "properties": {
                        "role": {"type": "string", "enum": list(VISUAL_ROLES)},
                        "content": text,
                        "source_ids": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }


def weighted_candidate_score(scores: Mapping[str, Any], complexity: str) -> int:
    if set(scores) != set(WEIGHTS):
        raise ValueError("candidate scores must contain every weighted dimension")
    values = {name: int(scores[name]) for name in WEIGHTS}
    if any(not 1 <= value <= 10 for value in values.values()):
        raise ValueError("candidate dimension scores must be integers from one to ten")
    if complexity not in {"none", "moderate", "harmful"}:
        raise ValueError("unknown complexity correction")
    total = round(sum(values[name] * 10 * weight for name, weight in WEIGHTS.items()))
    return total - (5 if complexity == "moderate" else 0)


def final_eligible(evaluation: Mapping[str, Any]) -> bool:
    if evaluation.get("complexity") == "harmful":
        return False
    hard_gates = evaluation.get("hard_gates")
    dimensions = evaluation.get("scores")
    elements = evaluation.get("element_scores")
    if not isinstance(hard_gates, Mapping) or not hard_gates or not all(hard_gates.values()):
        return False
    if not isinstance(dimensions, Mapping) or not isinstance(elements, Mapping):
        return False
    try:
        total = weighted_candidate_score(dimensions, str(evaluation.get("complexity")))
    except (TypeError, ValueError):
        return False
    if (
        int(dimensions.get("task_brief_suitability", 0)) < 8
        or int(dimensions.get("message_clarity", 0)) < 8
        or int(dimensions.get("coherence", 0)) < 8
        or int(dimensions.get("hook_strength", 0)) < 7
        or int(dimensions.get("persuasion_action", 0)) < 7
        or total < 80
    ):
        return False
    for scores in elements.values():
        if not isinstance(scores, Mapping) or int(scores.get("contribution", 0)) < 7:
            return False
    return True


def critic_output_schema(pass_number: int, candidate_ids: Sequence[str], element_ids: Sequence[str]) -> dict[str, Any]:
    if pass_number not in {1, 2, 3}:
        raise ValueError("critic pass must be one, two, or three")
    candidate_enum = list(candidate_ids)
    element_enum = list(element_ids)
    score_properties = {name: {"type": "integer", "minimum": 1, "maximum": 10} for name in WEIGHTS}
    element_score = {
        "type": "object", "additionalProperties": False,
        "required": ["task_fit", "clarity", "contribution", "coherence"],
        "properties": {name: {"type": "integer", "minimum": 1, "maximum": 10} for name in (
            "task_fit", "clarity", "contribution", "coherence",
        )},
    }
    return {
        "type": "object", "additionalProperties": False,
        "required": ["pass", "evaluations", "ranking", "pairwise", "actions", "observations", "final_selection"],
        "properties": {
            "pass": {"type": "integer", "enum": [pass_number]},
            "evaluations": {
                "type": "array", "minItems": len(candidate_enum), "maxItems": len(candidate_enum),
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["candidate_id", "hard_gates", "element_scores", "scores", "complexity", "reason_codes"],
                    "properties": {
                        "candidate_id": {"type": "string", "enum": candidate_enum},
                        "hard_gates": {
                            "type": "object", "additionalProperties": False,
                            "required": list(HARD_GATES),
                            "properties": {name: {"type": "boolean"} for name in HARD_GATES},
                        },
                        "element_scores": {"type": "object", "propertyNames": {"enum": element_enum}, "additionalProperties": element_score},
                        "scores": {"type": "object", "additionalProperties": False, "required": list(WEIGHTS), "properties": score_properties},
                        "complexity": {"type": "string", "enum": ["none", "moderate", "harmful"]},
                        "reason_codes": {"type": "array", "maxItems": 12, "items": {"type": "string"}},
                    },
                },
            },
            "ranking": {"type": "array", "minItems": len(candidate_enum), "maxItems": len(candidate_enum), "items": {"type": "string", "enum": candidate_enum}},
            "pairwise": {
                "type": "array", "maxItems": 3,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["left", "right", "winner", "reason_codes"],
                    "properties": {
                        "left": {"type": "string", "enum": candidate_enum},
                        "right": {"type": "string", "enum": candidate_enum},
                        "winner": {"type": "string", "enum": candidate_enum},
                        "reason_codes": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
                    },
                },
            },
            "actions": {
                "type": "array", "maxItems": 4 if pass_number < 3 else 0,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["action_type", "base_candidate_id", "template_id", "locked_element_ids", "target_element_ids", "source_element_ids", "slider_values", "reason_codes"],
                    "properties": {
                        "action_type": {"type": "string", "enum": list(ACTION_TYPES[:-1])},
                        "base_candidate_id": {"type": ["string", "null"]},
                        "template_id": {"type": ["string", "null"]},
                        "locked_element_ids": {"type": "array", "items": {"type": "string", "enum": element_enum}},
                        "target_element_ids": {"type": "array", "items": {"type": "string", "enum": element_enum}},
                        "source_element_ids": {"type": "array", "items": {"type": "string", "enum": element_enum}},
                        "slider_values": {"type": ["object", "null"]},
                        "reason_codes": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
                    },
                },
            },
            "observations": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "string", "maxLength": 300}},
            "final_selection": {
                "type": ["object", "null"],
                "properties": {
                    "candidate_id": {"type": "string", "enum": candidate_enum},
                    "decision_summary": {"type": "array", "minItems": 2, "maxItems": 4, "items": {"type": "string", "maxLength": 300}},
                },
                "required": ["candidate_id", "decision_summary"], "additionalProperties": False,
            },
        },
    }


def validate_critic_response(
    value: Mapping[str, Any], *, pass_number: int, candidate_ids: Sequence[str],
    element_ids: Sequence[str], templates: Mapping[str, StrategyTemplate],
    candidate_parameters: Mapping[str, Mapping[str, int]],
    candidate_templates: Mapping[str, str] | None = None,
    candidate_element_ids: Mapping[str, Sequence[str]] | None = None,
    candidate_regeneration_counts: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    expected = {"pass", "evaluations", "ranking", "pairwise", "actions", "observations", "final_selection"}
    if set(value) != expected or int(value.get("pass") or 0) != pass_number:
        raise ValueError("critic response fields or pass number do not match")
    if len(candidate_ids) > MAX_ACTIVE_BY_PASS[pass_number] or len(candidate_ids) < (2 if pass_number == 3 else 1):
        raise ValueError("critic active candidate count exceeds the pass boundary")
    allowed_candidates, allowed_elements = set(candidate_ids), set(element_ids)
    evaluations = value.get("evaluations")
    if not isinstance(evaluations, list) or {item.get("candidate_id") for item in evaluations if isinstance(item, Mapping)} != allowed_candidates:
        raise ValueError("critic must evaluate every active candidate exactly once")
    normalized_evaluations: list[dict[str, Any]] = []
    for raw in evaluations:
        if not isinstance(raw, Mapping) or set(raw) != {
            "candidate_id", "hard_gates", "element_scores", "scores", "complexity", "reason_codes",
        }:
            raise ValueError("critic evaluation fields do not match v1")
        hard_gates = raw.get("hard_gates")
        element_scores = raw.get("element_scores")
        if (
            not isinstance(hard_gates, Mapping) or set(hard_gates) != set(HARD_GATES)
            or not all(isinstance(item, bool) for item in hard_gates.values())
        ):
            raise ValueError("critic hard gates must contain the complete boolean gate set")
        if not isinstance(element_scores, Mapping) or set(element_scores) - allowed_elements:
            raise ValueError("critic element scores reference unknown elements")
        candidate_id = str(raw["candidate_id"])
        if candidate_element_ids is not None and set(element_scores) != set(candidate_element_ids[candidate_id]):
            raise ValueError("critic must score every required element in each active candidate")
        normalized_elements: dict[str, dict[str, int]] = {}
        for element_id, score_value in element_scores.items():
            if not isinstance(score_value, Mapping) or set(score_value) != {"task_fit", "clarity", "contribution", "coherence"}:
                raise ValueError("element score fields do not match v1")
            parsed = {name: int(score_value[name]) for name in score_value}
            if any(not 1 <= score <= 10 for score in parsed.values()):
                raise ValueError("element scores must be integers from one to ten")
            normalized_elements[str(element_id)] = parsed
        complexity = str(raw.get("complexity"))
        total = weighted_candidate_score(raw.get("scores") or {}, complexity)
        normalized_evaluations.append({
            **dict(raw), "element_scores": normalized_elements, "weighted_total": total,
            "eligible": final_eligible(raw),
        })
    proposed_ranking = list(map(str, value.get("ranking") or []))
    if len(proposed_ranking) != len(allowed_candidates) or set(proposed_ranking) != allowed_candidates:
        raise ValueError("critic ranking must contain every active candidate exactly once")
    actions = value.get("actions")
    if not isinstance(actions, list) or len(actions) > (0 if pass_number == 3 else 4):
        raise ValueError("critic action count exceeds the pass boundary")
    normalized_actions: list[dict[str, Any]] = []
    for raw in actions:
        if not isinstance(raw, Mapping) or set(raw) != {
            "action_type", "base_candidate_id", "template_id", "locked_element_ids",
            "target_element_ids", "source_element_ids", "slider_values", "reason_codes",
        }:
            raise ValueError("critic action fields do not match v1")
        action_type = str(raw.get("action_type"))
        if action_type not in ACTION_TYPES[:-1]:
            raise ValueError("critic emitted an unsupported improvement action")
        base = raw.get("base_candidate_id")
        if base is not None and str(base) not in allowed_candidates:
            raise ValueError("critic action references an inactive base candidate")
        referenced = [
            *list(raw.get("locked_element_ids") or []),
            *list(raw.get("target_element_ids") or []),
            *list(raw.get("source_element_ids") or []),
        ]
        if not set(map(str, referenced)) <= allowed_elements:
            raise ValueError("critic action references an unknown element UUID")
        template_id = raw.get("template_id")
        sliders = raw.get("slider_values")
        normalized_sliders = None
        if action_type == "rerun_template":
            if base is None or not isinstance(sliders, Mapping) or candidate_templates is None:
                raise ValueError("rerun_template requires a base candidate and slider configuration")
            if template_id is not None:
                raise ValueError("an anonymized critic must not name a strategy template")
            resolved_template_id = candidate_templates[str(base)]
            normalized_sliders = templates[resolved_template_id].validate_adjustment(
                candidate_parameters[str(base)], sliders,
            )
            template_id = resolved_template_id
        elif template_id is not None or sliders is not None:
            raise ValueError("only rerun_template may change template sliders")
        normalized_actions.append({
            **dict(raw), "template_id": template_id, "slider_values": normalized_sliders,
        })
    final_selection = value.get("final_selection")
    if pass_number < 3 and final_selection is not None:
        raise ValueError("only critic Pass 3 may select a final result")
    if pass_number == 3:
        if actions:
            raise ValueError("critic Pass 3 cannot initiate generation")
        if final_selection is not None:
            if not isinstance(final_selection, Mapping) or set(final_selection) != {"candidate_id", "decision_summary"}:
                raise ValueError("final selection fields do not match v1")
            chosen = str(final_selection.get("candidate_id"))
            by_id = {item["candidate_id"]: item for item in normalized_evaluations}
            if chosen not in allowed_candidates or not by_id[chosen]["eligible"]:
                raise ValueError("critic cannot select a final candidate that is not eligible")
            summary = [str(item).strip() for item in final_selection.get("decision_summary") or []]
            if not 2 <= len(summary) <= 4 or any(not 1 <= len(item) <= 300 for item in summary):
                raise ValueError("public selection summary requires two to four concise observations")
            final_selection = {"candidate_id": chosen, "decision_summary": summary}
    by_id = {item["candidate_id"]: item for item in normalized_evaluations}
    regeneration_counts = {
        candidate_id: int((candidate_regeneration_counts or {}).get(candidate_id, 0))
        for candidate_id in allowed_candidates
    }
    complexity_order = {"none": 0, "moderate": 1, "harmful": 2}

    def score_key(candidate_id: str) -> tuple[Any, ...]:
        evaluation = by_id[candidate_id]
        return (
            not evaluation["eligible"], -int(evaluation["weighted_total"]),
            complexity_order[evaluation["complexity"]], regeneration_counts[candidate_id],
            candidate_id,
        )

    score_order = sorted(allowed_candidates, key=score_key)
    compared = score_order[:min(3, len(score_order))]
    raw_pairwise = value.get("pairwise")
    if not isinstance(raw_pairwise, list):
        raise ValueError("critic pairwise results must be a list")
    expected_pairs = (
        {frozenset((compared[0], compared[1]))}
        if pass_number == 3
        else {
            frozenset((compared[0], compared[1])),
            frozenset((compared[0], compared[2])),
            frozenset((compared[1], compared[2])),
        } if len(compared) >= 3 else set()
    )
    actual_pairs: set[frozenset[str]] = set()
    pairwise_wins = {candidate_id: 0 for candidate_id in compared}
    for item in raw_pairwise:
        if not isinstance(item, Mapping) or set(item) != {"left", "right", "winner", "reason_codes"}:
            raise ValueError("critic pairwise fields do not match v1")
        left, right, winner = str(item["left"]), str(item["right"]), str(item["winner"])
        if left == right or {left, right} - allowed_candidates or winner not in {left, right}:
            raise ValueError("critic pairwise comparison references invalid candidates or winner")
        actual_pairs.add(frozenset((left, right)))
        pairwise_wins[winner] += 1
    if actual_pairs != expected_pairs or len(raw_pairwise) != len(expected_pairs):
        raise ValueError("critic pairwise comparisons must cover the ranked top candidates exactly once")
    compared_order = sorted(
        compared,
        key=lambda candidate_id: (
            not by_id[candidate_id]["eligible"], -pairwise_wins[candidate_id],
            -int(by_id[candidate_id]["weighted_total"]),
            complexity_order[by_id[candidate_id]["complexity"]],
            regeneration_counts[candidate_id], candidate_id,
        ),
    )
    ranking = [*compared_order, *(item for item in score_order if item not in compared)]
    if proposed_ranking != ranking:
        raise ValueError("critic ranking conflicts with deterministic pairwise ordering")
    if final_selection is not None and final_selection["candidate_id"] != ranking[0]:
        raise ValueError("final selection must be the deterministic pairwise winner")
    return {
        "pass": pass_number, "evaluations": normalized_evaluations, "ranking": ranking,
        "pairwise": list(raw_pairwise), "actions": normalized_actions,
        "observations": [str(item).strip()[:300] for item in value.get("observations") or []],
        "final_selection": final_selection,
    }
