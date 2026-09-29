"""Strict Product Brief validation contract."""

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


def require_language(required_language: str, values: Sequence[Any], label: str) -> None:
    """Require aggregate user-facing copy to use the owner-selected language."""
    if required_language not in {"uk", "en"}:
        raise ValueError(f"{label} required language must be uk or en")
    combined = " ".join(str(value or "") for value in values)
    if infer_language(combined) != required_language:
        raise ValueError(f"{label} must use required language {required_language}")


def _require_brief_field_language(required_language: str, value: str, label: str) -> None:
    if infer_language(value) == required_language:
        return
    letters = re.findall(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]+", value)
    is_compact_brand_name = (
        label == "product" and len(value) <= 60 and len(letters) <= 4
        and not re.search(r"[.!?…]", value)
    )
    if not is_compact_brand_name:
        raise ValueError(f"Product Brief {label} must use required language {required_language}")


def _canonical(value: Mapping[str, Any]) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ProductBriefV1:
    value: Mapping[str, Any]
    digest: str
    quality_gates: Mapping[str, bool]

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, raw_idea: str,
        required_language: str | None = None,
    ) -> "ProductBriefV1":
        expected = {"schema_version", "language", *BRIEF_FIELDS}
        _exact(value, expected, "product_brief")
        language = required_language or infer_language(raw_idea)
        if language not in {"uk", "en"}:
            raise ValueError("Product Brief required language must be uk or en")
        if value.get("schema_version") != 1 or value.get("language") != language:
            raise ValueError("Product Brief version or required language does not match")
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
        require_language(
            language,
            [normalized[field] for field in BRIEF_FIELDS if field != "key_benefits"]
            + list(normalized["key_benefits"]),
            "Product Brief",
        )
        for field in BRIEF_FIELDS:
            if field == "key_benefits":
                for index, benefit in enumerate(normalized[field]):
                    _require_brief_field_language(
                        language, benefit, f"key_benefits[{index}]",
                    )
            else:
                _require_brief_field_language(language, str(normalized[field]), field)
        _, digest = _canonical(normalized)
        quality = {
            "strict_shape": True,
            "language_required": True,
            "one_hypothesis": True,
            "three_to_five_benefits": True,
            "strong_offer_present": True,
            "fabricated_proof_absent": True,
            "passed": True,
        }
        return cls(normalized, digest, quality)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.value)


POSITIONING_FIELDS = ("desired_identity", "customer_tension", "category_frame", "functional_value")


@dataclass(frozen=True, slots=True)
class ProductBriefV2(ProductBriefV1):
    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, raw_idea: str,
                  required_language: str | None = None, marketing_approach: str | None = None) -> "ProductBriefV2":
        from .marketing import approach

        _exact(value, {"schema_version", "language", *BRIEF_FIELDS, "positioning"}, "product_brief")
        if value.get("schema_version") != 2:
            raise ValueError("Product Brief version must be 2")
        base = ProductBriefV1.from_dict(
            {**{k: v for k, v in value.items() if k != "positioning"}, "schema_version": 1},
            raw_idea=raw_idea, required_language=required_language,
        )
        positioning = value["positioning"]
        if not isinstance(positioning, Mapping):
            raise ValueError("positioning must be an object")
        _exact(positioning, {"marketing_approach", *POSITIONING_FIELDS}, "positioning")
        selected = approach(positioning["marketing_approach"])
        if marketing_approach is not None and selected != approach(marketing_approach):
            raise ValueError("positioning marketing approach differs from the owner's selection")
        normalized = {"marketing_approach": selected}
        for field in POSITIONING_FIELDS:
            item = positioning[field]
            if not isinstance(item, str):
                raise ValueError(f"positioning.{field} must be text")
            normalized[field] = "" if field == "desired_identity" and not item.strip() else _text(item, field, 200)
            if normalized[field]:
                _require_brief_field_language(base.value["language"], normalized[field], field)
        if len(_canonical(normalized)[0].encode("utf-8")) > 1024:
            raise ValueError("positioning exceeds 1024 UTF-8 bytes; shorten its sentences")
        document = {**base.to_dict(), "schema_version": 2, "positioning": normalized}
        return cls(document, _canonical(document)[1], {**base.quality_gates, "positioning_bounded": True})


def parse_product_brief(value: Mapping[str, Any], *, raw_idea: str,
                        required_language: str | None = None,
                        generation_settings: Mapping[str, Any] | None = None) -> ProductBriefV1:
    if generation_settings is None:
        return ProductBriefV1.from_dict(value, raw_idea=raw_idea, required_language=required_language)
    return ProductBriefV2.from_dict(value, raw_idea=raw_idea, required_language=required_language,
                                   marketing_approach=generation_settings["marketing_approach"])


def product_brief_schema(required_language: str | None = None, *, generation_settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if required_language not in {None, "uk", "en"}:
        raise ValueError("Product Brief schema language must be uk or en")
    copy = {"type": "string", "minLength": 1, "maxLength": 500}
    schema = {
        "type": "object",
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "language": (
                {"type": "string", "enum": ["uk", "en"]}
                if required_language is None
                else {"type": "string", "const": required_language}
            ),
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
    if generation_settings is not None:
        schema["properties"]["schema_version"]["const"] = 2
        schema["properties"]["positioning"] = {
            "type": "object", "additionalProperties": False,
            "properties": {"marketing_approach": {"type": "string", "const": generation_settings["marketing_approach"]},
                           **{field: {"type": "string", "minLength": 0 if field == "desired_identity" else 1, "maxLength": 200} for field in POSITIONING_FIELDS}},
            "required": ["marketing_approach", *POSITIONING_FIELDS],
            "description": "Complete object must fit 1024 UTF-8 bytes. Use short sentences.",
        }
        schema["required"].append("positioning")
    return schema
