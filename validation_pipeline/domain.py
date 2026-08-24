"""Strict contracts for the two active idea-validation stages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence


BRIEF_FIELDS = (
    "product",
    "target_audience",
    "main_pain",
    "promise",
    "key_benefits",
    "cta",
    "trust_strategy",
    "offer",
)
BRIEF_CORRECTION_SECTION = "product_brief"
CREATIVE_ANGLES = ("emotional", "practical", "curiosity", "authority", "problem_first")
CROP_FOCI = ("left", "center", "right")
TESTIMONIAL_PATTERN = re.compile(
    r"\b(?:customer|client|user|клієнт|користувач)\s+(?:said|says|reported|каже|сказав|повідомив)\b",
    re.IGNORECASE,
)
RATING_PATTERN = re.compile(r"(?<!\w)(?:[4-5](?:\.\d)?\s*/\s*5|[4-5](?:\.\d)?\s*stars?|[4-5](?:\.\d)?\s*зір)", re.IGNORECASE)
UNSUPPLIED_PROOF_PATTERN = re.compile(
    r"\b(?:(?:trusted|used|loved)\s+by\s+\d|\d[\d,.\s]*\+?\s+(?:customers?|clients?|users?|клієнт(?:и|ів)?|користувач(?:і|ів)?))\b",
    re.IGNORECASE,
)
VALIDATION_OFFER_PATTERN = re.compile(
    r"(?:\bfree\b|\bcomplimentary\b|\bno[- ]cost\b|\bdiscount\b|\bpromo(?:tional)?\s+code\b|"
    r"\bearly\s+access\b|\bfree\s+trial\b|\binvitation\b|"
    r"безкоштовн|безоплатн|знижк|промокод|ранн(?:ій|ього|ьому)?\s+доступ|пробн(?:ий|ого|ому)?\s+період|запрошенн)",
    re.IGNORECASE,
)
OFFER_SENTENCE_PUNCTUATION = " .!?\u2026\u3002\uff01\uff1f"


def _exact(value: Mapping[str, Any], keys: set[str], name: str) -> None:
    if set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        raise ValueError(f"{name} fields mismatch; missing={missing} extra={extra}")


def _text(value: Any, name: str, maximum: int) -> str:
    result = str(value or "").strip()
    if not 1 <= len(result) <= maximum:
        raise ValueError(f"{name} must contain 1-{maximum} characters")
    if (
        TESTIMONIAL_PATTERN.search(result)
        or RATING_PATTERN.search(result)
        or UNSUPPLIED_PROOF_PATTERN.search(result)
    ):
        raise ValueError(f"{name} contains fabricated proof")
    return result


def _items(value: Any, name: str, minimum: int, maximum: int) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{name} must contain {minimum}-{maximum} items")
    return value


def _offer_is_visible(copy: str, offer: str) -> bool:
    """Keep offer wording exact while allowing surrounding sentence punctuation."""
    normalized_copy = " ".join(copy.split()).casefold()
    visible_offer = " ".join(offer.split()).rstrip(OFFER_SENTENCE_PUNCTUATION).casefold()
    return bool(visible_offer) and visible_offer in normalized_copy


def infer_language(raw_idea: str) -> str:
    """Infer the only two supported output languages; ties default to English."""
    cyrillic = len(re.findall(r"[А-Яа-яІіЇїЄєҐґ]", raw_idea))
    latin = len(re.findall(r"[A-Za-z]", raw_idea))
    return "uk" if cyrillic > latin else "en"


def _canonical(value: Mapping[str, Any]) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ProductBriefV1:
    value: Mapping[str, Any]
    digest: str
    quality_gates: Mapping[str, bool]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, raw_idea: str) -> "ProductBriefV1":
        expected = {"schema_version", "language", *BRIEF_FIELDS}
        _exact(value, expected, "product_brief")
        language = infer_language(raw_idea)
        if value.get("schema_version") != 1 or value.get("language") != language:
            raise ValueError("Product Brief version or inferred language does not match")
        benefits = [
            _text(item, f"key_benefits[{index}]", 240)
            for index, item in enumerate(_items(value.get("key_benefits"), "key_benefits", 3, 5))
        ]
        if len(set(item.casefold() for item in benefits)) != len(benefits):
            raise ValueError("key_benefits must be distinct")
        offer = _text(value.get("offer"), "offer", 500)
        if not VALIDATION_OFFER_PATTERN.search(offer):
            raise ValueError("offer must contain one explicit low-friction validation promotion")
        normalized = {
            "schema_version": 1,
            "language": language,
            "product": _text(value.get("product"), "product", 500),
            "target_audience": _text(value.get("target_audience"), "target_audience", 500),
            "main_pain": _text(value.get("main_pain"), "main_pain", 500),
            "promise": _text(value.get("promise"), "promise", 500),
            "key_benefits": benefits,
            "cta": _text(value.get("cta"), "cta", 100),
            "trust_strategy": _text(value.get("trust_strategy"), "trust_strategy", 500),
            "offer": offer,
        }
        _, digest = _canonical(normalized)
        quality = {
            "strict_shape": True,
            "language_inferred": True,
            "one_hypothesis": True,
            "three_to_five_benefits": True,
            "strong_offer_present": True,
            "fabricated_proof_absent": True,
            "passed": True,
        }
        return cls(normalized, digest, quality)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.value)


@dataclass(frozen=True, slots=True)
class CreativeSetV1:
    value: tuple[Mapping[str, Any], ...]
    digest: str
    quality_gates: Mapping[str, bool]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, brief: Mapping[str, Any]) -> "CreativeSetV1":
        _exact(value, {"schema_version", "creatives"}, "creative_set")
        if value.get("schema_version") != 1:
            raise ValueError("creative_set.schema_version must be 1")
        raw_items = _items(value.get("creatives"), "creatives", 5, 5)
        creatives: list[dict[str, Any]] = []
        for index, expected_angle in enumerate(CREATIVE_ANGLES):
            item = raw_items[index]
            if not isinstance(item, Mapping):
                raise ValueError("creative items must be objects")
            _exact(item, {
                "angle", "hook", "primary_text", "image_description", "cta",
                "offer", "desired_emotion", "image_category", "image_search_query", "crop_focus",
            }, f"creatives[{index}]")
            if item.get("angle") != expected_angle:
                raise ValueError(f"creatives[{index}].angle must be {expected_angle}")
            if str(item.get("cta") or "").strip() != brief["cta"]:
                raise ValueError(
                    f"creative {index + 1} ({expected_angle}) CTA must exactly match the Product Brief"
                )
            offer = _text(item.get("offer"), f"creatives[{index}].offer", 500)
            if offer != brief["offer"]:
                raise ValueError(
                    f"creative {index + 1} ({expected_angle}) offer field must exactly match "
                    f"the Product Brief offer: {brief['offer']}"
                )
            crop = str(item.get("crop_focus") or "")
            if crop not in CROP_FOCI:
                raise ValueError("crop_focus must be left, center, or right")
            hook = _text(item.get("hook"), f"creatives[{index}].hook", 160)
            primary_text = _text(item.get("primary_text"), f"creatives[{index}].primary_text", 1000)
            if not _offer_is_visible(f"{hook} {primary_text}", brief["offer"]):
                raise ValueError(
                    f"creative {index + 1} ({expected_angle}) copy must visibly retain "
                    f"the Product Brief offer wording: {brief['offer']}"
                )
            creatives.append({
                "angle": expected_angle,
                "hook": hook,
                "primary_text": primary_text,
                "image_description": _text(item.get("image_description"), f"creatives[{index}].image_description", 500),
                "cta": brief["cta"],
                "offer": offer,
                "desired_emotion": _text(item.get("desired_emotion"), f"creatives[{index}].desired_emotion", 160),
                "image_category": _text(item.get("image_category"), f"creatives[{index}].image_category", 160),
                "image_search_query": _text(item.get("image_search_query"), f"creatives[{index}].image_search_query", 160),
                "crop_focus": crop,
            })
        _, digest = _canonical({"schema_version": 1, "creatives": creatives})
        return cls(
            tuple(creatives), digest,
            {
                "strict_shape": True,
                "five_distinct_angles": True,
                "brief_cta_preserved": True,
                "brief_offer_preserved": True,
                "real_photo_plan_present": True,
                "passed": True,
            },
        )


def product_brief_schema() -> dict[str, Any]:
    copy = {"type": "string", "minLength": 1, "maxLength": 500}
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "language": {"type": "string", "enum": ["uk", "en"]},
            "product": copy,
            "target_audience": copy,
            "main_pain": copy,
            "promise": copy,
            "key_benefits": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "string", "minLength": 1, "maxLength": 240}},
            "cta": {"type": "string", "minLength": 1, "maxLength": 100},
            "trust_strategy": copy,
            "offer": copy,
        },
        "required": ["schema_version", "language", *BRIEF_FIELDS],
        "additionalProperties": False,
    }


def creative_set_schema(*, brief: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cta = {"type": "string", "minLength": 1, "maxLength": 100}
    offer = {"type": "string", "minLength": 1, "maxLength": 500}
    if brief is not None:
        cta = {"type": "string", "const": str(brief["cta"])}
        offer = {"type": "string", "const": str(brief["offer"])}
    item = {
        "type": "object",
        "properties": {
            "angle": {"type": "string", "enum": list(CREATIVE_ANGLES)},
            "hook": {"type": "string", "minLength": 1, "maxLength": 160},
            "primary_text": {"type": "string", "minLength": 1, "maxLength": 1000},
            "image_description": {"type": "string", "minLength": 1, "maxLength": 500},
            "cta": cta,
            "offer": offer,
            "desired_emotion": {"type": "string", "minLength": 1, "maxLength": 160},
            "image_category": {"type": "string", "minLength": 1, "maxLength": 160},
            "image_search_query": {"type": "string", "minLength": 1, "maxLength": 160},
            "crop_focus": {"type": "string", "enum": list(CROP_FOCI)},
        },
        "required": [
            "angle", "hook", "primary_text", "image_description", "cta",
            "offer", "desired_emotion", "image_category", "image_search_query", "crop_focus",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "creatives": {"type": "array", "minItems": 5, "maxItems": 5, "items": item},
        },
        "required": ["schema_version", "creatives"],
        "additionalProperties": False,
    }
