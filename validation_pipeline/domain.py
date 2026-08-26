"""Strict contract for the approved Product Brief input to Result generation."""

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
