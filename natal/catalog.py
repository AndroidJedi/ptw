"""Template catalog and deterministic first-pass template selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
TEMPLATES_ROOT = ROOT / "templates"
TEMPLATE_IDS = ("product", "community", "waitlist")


def landing_templates() -> tuple[dict[str, Any], ...]:
    items: list[dict[str, Any]] = []
    for template_id in TEMPLATE_IDS:
        manifest = json.loads((TEMPLATES_ROOT / template_id / "template.json").read_text())
        if manifest.get("id") != template_id:
            raise ValueError(f"Natal template manifest mismatch: {template_id}")
        items.append(manifest)
    return tuple(items)


def template_manifest(template_id: str) -> dict[str, Any]:
    return next(
        (item for item in landing_templates() if item["id"] == template_id),
        None,
    ) or _unknown_template(template_id)


def _unknown_template(template_id: str) -> dict[str, Any]:
    raise ValueError(f"unknown Natal landing template: {template_id}")


def recommend_template(candidate: Mapping[str, Any]) -> str:
    """Choose structure from the idea semantics, never from brand presentation."""

    thesis = _preferred_thesis(candidate)
    searchable = " ".join(
        _flatten(value)
        for value in (
            candidate.get("owner_idea"),
            thesis.get("title"),
            thesis.get("target_user"),
            thesis.get("problem"),
            thesis.get("value_moment"),
            thesis.get("loop_steps"),
        )
    ).lower()
    community_terms = {
        "community", "group", "event", "dinner", "meet", "offline", "club",
        "спільнот", "груп", "поді", "вечер", "зустріч", "офлайн", "клуб",
    }
    product_terms = {
        "saas", "software", "platform", "dashboard", "automation", "workflow",
        "crm", "business", "analytics", "system", "app", "service",
        "платформ", "автомат", "систем", "бізнес", "аналітик", "сервіс", "застос",
    }
    if any(term in searchable for term in community_terms):
        return "community"
    if any(term in searchable for term in product_terms):
        return "product"
    return "waitlist"


def _preferred_thesis(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
    theses = [item for item in candidate.get("theses") or [] if isinstance(item, Mapping)]
    recommended_id = str(candidate.get("recommended_thesis_id") or "")
    return next(
        (item for item in theses if str(item.get("id")) == recommended_id),
        next((item for item in theses if item.get("recommended") is True), theses[0] if theses else {}),
    )


def _flatten(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(item) for item in value)
    return str(value or "")
