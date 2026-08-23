"""Strict, source-ID-explicit Marketing Positioning document contract."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID


SECTION_IDS = (
    "positioning_foundation",
    "messaging_matrix",
    "landing_copy",
    "ad_concepts",
    "aeo_faqs",
)
AD_KINDS = ("contextual_relatable", "direct_problem_solution")
METRIC_PATTERN = re.compile(
    r"(?<![\w-])(?:\d+(?:\.\d+)?\s*%|\$\s*\d|\d+(?:\.\d+)?\s*(?:x|times|users|customers|reviews))",
    re.IGNORECASE,
)
TESTIMONIAL_PATTERN = re.compile(r"\b(?:customer|client|user)\s+(?:said|says|reported)\b", re.IGNORECASE)


def _exact(value: Mapping[str, Any], keys: set[str], name: str) -> None:
    if set(value) != keys:
        missing = keys - set(value)
        extra = set(value) - keys
        raise ValueError(f"{name} fields mismatch; missing={sorted(missing)} extra={sorted(extra)}")


def _text(value: Any, name: str, maximum: int = 2000) -> str:
    result = str(value or "").strip()
    if not result or len(result) > maximum:
        raise ValueError(f"{name} must contain 1-{maximum} characters")
    return result


def _array(value: Any, name: str, *, minimum: int, maximum: int) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{name} must contain {minimum}-{maximum} items")
    return value


def _uuid(value: Any, name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a UUID") from error


def _statement(
    value: Any,
    name: str,
    allowed_sources: set[str],
    *,
    maximum: int = 2000,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an evidence statement")
    _exact(value, {"text", "source_ids", "assumption"}, name)
    text = _text(value.get("text"), f"{name}.text", maximum)
    raw_sources = value.get("source_ids")
    if not isinstance(raw_sources, (list, tuple)) or len(raw_sources) > 20:
        raise ValueError(f"{name}.source_ids must be an array")
    source_ids = list(dict.fromkeys(_uuid(item, f"{name}.source_ids") for item in raw_sources))
    unknown = set(source_ids) - allowed_sources
    if unknown:
        raise ValueError(f"{name} references sources outside this revision: {sorted(unknown)}")
    assumption = value.get("assumption") is True
    if not source_ids and not assumption:
        raise ValueError(f"{name} must cite a source or be visibly marked as an assumption")
    if (METRIC_PATTERN.search(text) or TESTIMONIAL_PATTERN.search(text)) and not source_ids:
        raise ValueError(f"{name} contains an unsupported metric or testimonial")
    return {"text": text, "source_ids": source_ids, "assumption": assumption}


def _statements(
    value: Any,
    name: str,
    allowed_sources: set[str],
    *,
    minimum: int = 1,
    maximum: int = 8,
) -> list[dict[str, Any]]:
    return [
        _statement(item, f"{name}[{index}]", allowed_sources)
        for index, item in enumerate(_array(value, name, minimum=minimum, maximum=maximum))
    ]


@dataclass(frozen=True, slots=True)
class PositioningDocumentV1:
    value: Mapping[str, Any]
    digest: str
    quality_gates: Mapping[str, Any]

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        allowed_source_ids: Iterable[str],
        output_language: str,
    ) -> "PositioningDocumentV1":
        if output_language not in {"uk", "en"}:
            raise ValueError("output_language must be uk or en")
        _exact(value, {"schema_version", "output_language", *SECTION_IDS, "evidence_references", "assumptions"}, "document")
        if value.get("schema_version") != 1 or value.get("output_language") != output_language:
            raise ValueError("document version or output language does not match the project")
        allowed = {_uuid(item, "allowed_source_ids") for item in allowed_source_ids}
        references = list(dict.fromkeys(
            _uuid(item, "evidence_references")
            for item in _array(value.get("evidence_references"), "evidence_references", minimum=1, maximum=50)
        ))
        if set(references) - allowed:
            raise ValueError("document evidence_references contains a source outside the revision")

        raw_foundation = value.get("positioning_foundation")
        if not isinstance(raw_foundation, Mapping):
            raise ValueError("positioning_foundation must be an object")
        _exact(raw_foundation, {"category", "competitive_alternatives", "definitive_audience", "jobs", "pains", "gains", "uvp"}, "positioning_foundation")
        foundation = {
            "category": _statement(raw_foundation.get("category"), "category", allowed),
            "competitive_alternatives": _statements(raw_foundation.get("competitive_alternatives"), "competitive_alternatives", allowed, maximum=6),
            "definitive_audience": _statement(raw_foundation.get("definitive_audience"), "definitive_audience", allowed),
            "jobs": _statements(raw_foundation.get("jobs"), "jobs", allowed, maximum=6),
            "pains": _statements(raw_foundation.get("pains"), "pains", allowed, maximum=6),
            "gains": _statements(raw_foundation.get("gains"), "gains", allowed, maximum=6),
            "uvp": _statement(raw_foundation.get("uvp"), "uvp", allowed),
        }

        matrix = []
        for index, item in enumerate(_array(value.get("messaging_matrix"), "messaging_matrix", minimum=1, maximum=8)):
            if not isinstance(item, Mapping):
                raise ValueError("messaging_matrix items must be objects")
            _exact(item, {"feature", "functional_benefit", "emotional_reward"}, f"messaging_matrix[{index}]")
            matrix.append({key: _statement(item.get(key), f"messaging_matrix[{index}].{key}", allowed) for key in item})

        raw_landing = value.get("landing_copy")
        if not isinstance(raw_landing, Mapping):
            raise ValueError("landing_copy must be an object")
        _exact(raw_landing, {"hero", "value_sections", "honest_limitation", "lead_capture_strategy"}, "landing_copy")
        raw_hero = raw_landing.get("hero")
        if not isinstance(raw_hero, Mapping):
            raise ValueError("landing_copy.hero must be an object")
        _exact(raw_hero, {"eyebrow", "headline", "subheadline", "cta"}, "landing_copy.hero")
        hero = {key: _statement(raw_hero.get(key), f"landing_copy.hero.{key}", allowed) for key in raw_hero}
        value_sections = []
        for index, item in enumerate(_array(raw_landing.get("value_sections"), "landing_copy.value_sections", minimum=3, maximum=3)):
            if not isinstance(item, Mapping):
                raise ValueError("landing value sections must be objects")
            _exact(item, {"title", "body"}, f"landing_copy.value_sections[{index}]")
            value_sections.append({key: _statement(item.get(key), f"landing_copy.value_sections[{index}].{key}", allowed) for key in item})
        limitation = _statement(raw_landing.get("honest_limitation"), "landing_copy.honest_limitation", allowed)
        if not limitation["source_ids"]:
            lower = limitation["text"].lower()
            markers = ("not yet verified", "results are not verified", "ще не підтвердж", "результати не підтвердж")
            if not any(marker in lower for marker in markers):
                raise ValueError("an unsourced honest limitation must say that results are not yet verified")
        landing = {
            "hero": hero,
            "value_sections": value_sections,
            "honest_limitation": limitation,
            "lead_capture_strategy": _statement(raw_landing.get("lead_capture_strategy"), "landing_copy.lead_capture_strategy", allowed),
        }

        ads = []
        raw_ads = _array(value.get("ad_concepts"), "ad_concepts", minimum=2, maximum=2)
        for index, expected_kind in enumerate(AD_KINDS):
            item = raw_ads[index]
            if not isinstance(item, Mapping):
                raise ValueError("ad concepts must be objects")
            _exact(item, {"kind", "hook", "body", "visual_direction"}, f"ad_concepts[{index}]")
            if item.get("kind") != expected_kind:
                raise ValueError(f"ad_concepts[{index}].kind must be {expected_kind}")
            ads.append({
                "kind": expected_kind,
                "hook": _statement(item.get("hook"), f"ad_concepts[{index}].hook", allowed),
                "body": _statement(item.get("body"), f"ad_concepts[{index}].body", allowed),
                "visual_direction": _statement(item.get("visual_direction"), f"ad_concepts[{index}].visual_direction", allowed),
            })

        faqs = []
        for index, item in enumerate(_array(value.get("aeo_faqs"), "aeo_faqs", minimum=3, maximum=3)):
            if not isinstance(item, Mapping):
                raise ValueError("AEO FAQs must be objects")
            _exact(item, {"question", "definition", "data", "context"}, f"aeo_faqs[{index}]")
            faq = {key: _statement(item.get(key), f"aeo_faqs[{index}].{key}", allowed) for key in item}
            for key in ("definition", "data", "context"):
                if len(re.findall(r"[.!?](?:\s|$)", faq[key]["text"])) != 1:
                    raise ValueError(f"aeo_faqs[{index}].{key} must be exactly one sentence")
            faqs.append(faq)

        assumptions = [_text(item, "assumptions", 500) for item in _array(value.get("assumptions"), "assumptions", minimum=0, maximum=30)]
        normalized = {
            "schema_version": 1,
            "output_language": output_language,
            "positioning_foundation": foundation,
            "messaging_matrix": matrix,
            "landing_copy": landing,
            "ad_concepts": ads,
            "aeo_faqs": faqs,
            "evidence_references": references,
            "assumptions": assumptions,
        }
        cited = set()
        assumption_count = 0
        def collect(node: Any) -> None:
            nonlocal assumption_count
            if isinstance(node, Mapping):
                if set(node) == {"text", "source_ids", "assumption"}:
                    cited.update(node["source_ids"])
                    if node["assumption"]:
                        assumption_count += 1
                else:
                    for child in node.values():
                        collect(child)
            elif isinstance(node, list):
                for child in node:
                    collect(child)
        collect(normalized)
        if cited != set(references):
            raise ValueError("evidence_references must exactly match the sources cited by fields")
        if assumption_count and not assumptions:
            raise ValueError("assumption fields require a visible top-level assumptions list")
        quality = {
            "strict_shape": True,
            "source_ids_valid": True,
            "unsupported_metrics_absent": True,
            "three_value_sections": len(value_sections) == 3,
            "two_ordered_ad_concepts": [item["kind"] for item in ads] == list(AD_KINDS),
            "three_definition_data_context_faqs": len(faqs) == 3,
            "honest_limitation_present": True,
            "assumptions_visible": assumption_count == 0 or bool(assumptions),
            "passed": True,
        }
        canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return cls(normalized, hashlib.sha256(canonical.encode()).hexdigest(), quality)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.value)


def markdown_export(document: Mapping[str, Any]) -> str:
    """Render the five-section deliverable without weakening evidence markers."""
    def show(item: Mapping[str, Any]) -> str:
        sources = ", ".join(item.get("source_ids") or [])
        suffix = f" [sources: {sources}]" if sources else " [assumption]"
        return str(item["text"]) + suffix

    foundation = document["positioning_foundation"]
    lines = ["# Marketing Positioning", "", "## 1. Positioning foundation", ""]
    lines += [f"- Category: {show(foundation['category'])}", f"- Audience: {show(foundation['definitive_audience'])}", f"- UVP: {show(foundation['uvp'])}"]
    for label, key in (("Alternatives", "competitive_alternatives"), ("Jobs", "jobs"), ("Pains", "pains"), ("Gains", "gains")):
        lines += ["", f"### {label}", *[f"- {show(item)}" for item in foundation[key]]]
    lines += ["", "## 2. Layered messaging", ""]
    for item in document["messaging_matrix"]:
        lines.append(f"- {show(item['feature'])} → {show(item['functional_benefit'])} → {show(item['emotional_reward'])}")
    landing = document["landing_copy"]
    lines += ["", "## 3. Landing copy", "", f"### {show(landing['hero']['headline'])}", show(landing['hero']['subheadline'])]
    for item in landing["value_sections"]:
        lines += ["", f"### {show(item['title'])}", show(item["body"])]
    lines += ["", f"Limitation: {show(landing['honest_limitation'])}", f"Lead capture: {show(landing['lead_capture_strategy'])}"]
    lines += ["", "## 4. Ad concepts", ""]
    for item in document["ad_concepts"]:
        lines += [f"### {item['kind']}", show(item["hook"]), "", show(item["body"]), "", f"Visual: {show(item['visual_direction'])}", ""]
    lines += ["## 5. AEO FAQs", ""]
    for item in document["aeo_faqs"]:
        lines += [f"### {show(item['question'])}", " ".join(show(item[key]) for key in ("definition", "data", "context")), ""]
    if document.get("assumptions"):
        lines += ["## Assumptions", "", *[f"- {item}" for item in document["assumptions"]], ""]
    return "\n".join(lines).strip() + "\n"
