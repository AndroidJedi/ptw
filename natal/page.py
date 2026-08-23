"""Validated, independently editable copy blocks for Natal landing pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .brief import LandingBrief


BLOCK_IDS = ("hero", "problem", "features", "steps", "proof", "faq", "final_cta")


def _exact_keys(value: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unexpected = set(value) - allowed
    if unexpected:
        raise ValueError(f"{name} contains unsupported fields: {', '.join(sorted(unexpected))}")


def _text(value: Any, name: str, limit: int) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{name} is required")
    if len(result) > limit:
        raise ValueError(f"{name} must contain at most {limit} characters")
    return result


def _items(value: Any, name: str, maximum: int) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValueError(f"{name} must be an array with at most {maximum} items")
    return value


def _pairs(value: Any, name: str, maximum: int) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in _items(value, name, maximum):
        if not isinstance(item, Mapping):
            raise ValueError(f"each {name} item must be an object")
        _exact_keys(item, {"title", "description"}, name)
        result.append({
            "title": _text(item.get("title"), f"{name}.title", 160),
            "description": _text(item.get("description"), f"{name}.description", 600),
        })
    return result


def _faq(value: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in _items(value, "faq.items", 6):
        if not isinstance(item, Mapping):
            raise ValueError("each faq item must be an object")
        _exact_keys(item, {"question", "answer"}, "faq.items")
        result.append({
            "question": _text(item.get("question"), "faq.question", 240),
            "answer": _text(item.get("answer"), "faq.answer", 1000),
        })
    return result


@dataclass(frozen=True, slots=True)
class LandingPageContent:
    template_id: str
    language: str
    blocks: Mapping[str, Mapping[str, Any]]

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, expected_template_id: str | None = None
    ) -> "LandingPageContent":
        _exact_keys(value, {"schema_version", "template_id", "language", "blocks"}, "page_content")
        if "schema_version" in value and value["schema_version"] != 1:
            raise ValueError("page_content.schema_version must be 1")
        template_id = str(value.get("template_id") or expected_template_id or "")
        if template_id not in {"product", "community", "waitlist"}:
            raise ValueError("page_content.template_id is invalid")
        if expected_template_id is not None and template_id != expected_template_id:
            raise ValueError("page_content template does not match the requested template")
        language = str(value.get("language") or "uk")
        if language not in {"uk", "en"}:
            raise ValueError("page_content.language must be uk or en")
        raw_blocks = value.get("blocks")
        if not isinstance(raw_blocks, Mapping) or set(raw_blocks) != set(BLOCK_IDS):
            raise ValueError("page_content must contain every canonical landing block exactly once")

        blocks: dict[str, dict[str, Any]] = {}
        for block_id in BLOCK_IDS:
            raw = raw_blocks.get(block_id)
            if not isinstance(raw, Mapping):
                raise ValueError(f"page_content.blocks.{block_id} must be an object")
            if block_id == "hero":
                _exact_keys(raw, {"eyebrow", "title", "body", "cta_label"}, "hero")
                blocks[block_id] = {
                    "eyebrow": _text(raw.get("eyebrow"), "hero.eyebrow", 500),
                    "title": _text(raw.get("title"), "hero.title", 500),
                    "body": _text(raw.get("body"), "hero.body", 1000),
                    "cta_label": _text(raw.get("cta_label"), "hero.cta_label", 100),
                }
            elif block_id == "problem":
                _exact_keys(raw, {"eyebrow", "title", "body"}, "problem")
                blocks[block_id] = {
                    "eyebrow": _text(raw.get("eyebrow"), "problem.eyebrow", 100),
                    "title": _text(raw.get("title"), "problem.title", 1000),
                    "body": _text(raw.get("body"), "problem.body", 1000),
                }
            elif block_id in {"features", "steps"}:
                _exact_keys(raw, {"eyebrow", "title", "items"}, block_id)
                items = _pairs(raw.get("items"), f"{block_id}.items", 6 if block_id == "features" else 5)
                minimum = 1 if block_id == "features" else 2
                if len(items) < minimum:
                    raise ValueError(f"{block_id}.items must contain at least {minimum} item(s)")
                blocks[block_id] = {
                    "eyebrow": _text(raw.get("eyebrow"), f"{block_id}.eyebrow", 100),
                    "title": _text(raw.get("title"), f"{block_id}.title", 500),
                    "items": items,
                }
            elif block_id == "proof":
                _exact_keys(raw, {"eyebrow", "title", "items", "empty_text"}, "proof")
                blocks[block_id] = {
                    "eyebrow": _text(raw.get("eyebrow"), "proof.eyebrow", 100),
                    "title": _text(raw.get("title"), "proof.title", 500),
                    "items": [
                        _text(item, "proof.items", 280)
                        for item in _items(raw.get("items"), "proof.items", 4)
                    ],
                    "empty_text": _text(raw.get("empty_text"), "proof.empty_text", 500),
                }
            elif block_id == "faq":
                _exact_keys(raw, {"eyebrow", "title", "items"}, "faq")
                blocks[block_id] = {
                    "eyebrow": _text(raw.get("eyebrow"), "faq.eyebrow", 100),
                    "title": _text(raw.get("title"), "faq.title", 500),
                    "items": _faq(raw.get("items")),
                }
            else:
                _exact_keys(raw, {"title", "body", "cta_label"}, "final_cta")
                blocks[block_id] = {
                    "title": _text(raw.get("title"), "final_cta.title", 500),
                    "body": _text(raw.get("body"), "final_cta.body", 1000),
                    "cta_label": _text(raw.get("cta_label"), "final_cta.cta_label", 100),
                }
        return cls(template_id=template_id, language=language, blocks=blocks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "template_id": self.template_id,
            "language": self.language,
            "blocks": {key: dict(value) for key, value in self.blocks.items()},
        }

    def replace_block(self, block_id: str, block: Mapping[str, Any]) -> "LandingPageContent":
        if block_id not in BLOCK_IDS:
            raise ValueError("unknown landing block")
        candidate = self.to_dict()
        candidate["blocks"] = {**candidate["blocks"], block_id: dict(block)}
        return LandingPageContent.from_dict(candidate, expected_template_id=self.template_id)


def page_content_from_brief(
    template_id: str, brief_value: Mapping[str, Any] | LandingBrief
) -> LandingPageContent:
    brief = brief_value if isinstance(brief_value, LandingBrief) else LandingBrief.from_dict(brief_value)
    uk = brief.language == "uk"
    faq = list(brief.faq) or [
        {
            "question": "Що саме вже доступно?" if uk else "What exactly is available?",
            "answer": (
                "Ця сторінка представляє оцінену концепцію. Перед запуском підтвердьте деталі надання послуги."
                if uk else
                "This page presents the evaluated concept. Confirm delivery details before launch."
            ),
        },
        {
            "question": "Продукт називається Natal?" if uk else "Is the product called Natal?",
            "answer": (
                "Так. Кожен лендинг у цьому наборі використовує назву Natal і канонічний логотип."
                if uk else
                "Yes. Every landing in this kit uses the Natal name and canonical logo."
            ),
        },
    ]
    return LandingPageContent.from_dict({
        "template_id": template_id,
        "language": brief.language,
        "blocks": {
            "hero": {
                "eyebrow": brief.target_audience,
                "title": brief.business_idea,
                "body": brief.promise,
                "cta_label": brief.cta["label"],
            },
            "problem": {
                "eyebrow": "Проблема" if uk else "The problem",
                "title": brief.pain,
                "body": brief.target_audience,
            },
            "features": {
                "eyebrow": "Що змінює Natal" if uk else "What Natal changes",
                "title": "Менше тертя. Зрозуміліший наступний крок." if uk else "Less friction. A clearer next step.",
                "items": list(brief.key_features),
            },
            "steps": {
                "eyebrow": "Як це працює" if uk else "How it works",
                "title": "Від першого наміру до корисного прогресу" if uk else "From first intent to useful progress",
                "items": list(brief.steps),
            },
            "proof": {
                "eyebrow": "Докази" if uk else "Evidence",
                "title": "Що підтверджує цю обіцянку" if uk else "What supports this promise",
                "items": list(brief.proof_points),
                "empty_text": (
                    "Ми ще не заявляємо про результати клієнтів. Додайте лише перевірені докази після експерименту."
                    if uk else
                    "No customer result is claimed yet. Add verified proof after the experiment."
                ),
            },
            "faq": {
                "eyebrow": "Питання" if uk else "Questions",
                "title": "Перед початком" if uk else "Before you start",
                "items": faq,
            },
            "final_cta": {
                "title": "Готові до простішого наступного кроку?" if uk else "Ready for a simpler next step?",
                "body": brief.promise,
                "cta_label": brief.cta["label"],
            },
        },
    })


def protect_page_content(
    proposed: Mapping[str, Any], *, template_id: str, brief: Mapping[str, Any]
) -> LandingPageContent:
    """Reapply server-owned evidence after an agent-generated content proposal."""

    current = LandingBrief.from_dict(brief)
    page = LandingPageContent.from_dict(proposed, expected_template_id=template_id)
    proof = dict(page.blocks["proof"])
    proof["items"] = list(current.proof_points)
    return page.replace_block("proof", proof)
