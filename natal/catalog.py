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


def recommend_template(positioning_document: Mapping[str, Any]) -> str:
    """Choose an advisory structure from the approved Positioning document."""

    searchable = _flatten(positioning_document).lower()
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


def _flatten(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(item) for item in value)
    return str(value or "")
