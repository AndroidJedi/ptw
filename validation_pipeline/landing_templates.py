"""Registered Landing template definitions and Post-template references."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .landing_workspace import (
    DEFAULT_CONFIGURATION,
    DEFAULT_CONTENT,
    LANDING_TEMPLATE_ID,
    LANDING_TEMPLATE_VERSION,
    landing_catalog,
    normalize_configuration,
    normalize_content,
)
from .post_templates import POST_TEMPLATE_REGISTRY
from .template_registry import (
    TemplateCapabilities,
    TemplateDefinition,
    TemplateIdentity,
    TemplateRegistry,
)


def _configuration() -> dict:
    return normalize_configuration(deepcopy(DEFAULT_CONFIGURATION))


def _content() -> dict:
    return normalize_content(deepcopy(DEFAULT_CONTENT))


def _agent_catalog() -> dict[str, Any]:
    """Expose only composition-relevant Landing metadata to the text agent."""

    catalog = landing_catalog()
    return {
        "schema": catalog["schema"],
        "template_id": catalog["template_id"],
        "template_version": catalog["template_version"],
        "section_order": deepcopy(catalog["section_order"]),
        "visual_slots": deepcopy(catalog["visual_slots"]),
        "components": [{
            "component_id": item["component_id"],
            "role": item["role"],
            "setting_ids": deepcopy(item["setting_ids"]),
        } for item in catalog["components"]],
        "brand": catalog["brand"],
        "sha256": catalog["sha256"],
    }


def _component_settings(
    configuration: Mapping[str, Any], content: Mapping[str, Any],
) -> dict[str, Any]:
    catalog = landing_catalog()
    return {
        "schema": "ptw.landing.component-settings.v1",
        "template_id": LANDING_TEMPLATE_ID,
        "template_version": LANDING_TEMPLATE_VERSION,
        "components": [
            {
                "component_id": item["component_id"],
                "setting_ids": list(item["setting_ids"]),
            }
            for item in catalog["components"]
        ],
        "configuration": normalize_configuration(configuration),
        "content": normalize_content(content),
    }


_catalog = landing_catalog()
PROJECT_LANDING_DEFINITION = TemplateDefinition(
    identity=TemplateIdentity(
        surface="landing",
        template_id=LANDING_TEMPLATE_ID,
        template_version=LANDING_TEMPLATE_VERSION,
        template_sha256=str(_catalog["sha256"]),
    ),
    name="Project landing",
    description="Responsive Natal landing page derived from an approved Post.",
    canvas=None,
    catalog=landing_catalog,
    agent_catalog=_agent_catalog,
    default_configuration=_configuration,
    default_content=_content,
    normalize_configuration=normalize_configuration,
    normalize_content=normalize_content,
    component_settings=_component_settings,
    capabilities=TemplateCapabilities(
        image_slots=("hero_visual", "visual_break_visual"),
    ),
    renderer_key="landing.project_landing.react",
    editor_key="landing.project_landing.react",
)

LANDING_TEMPLATE_REGISTRY = TemplateRegistry(
    "landing", (PROJECT_LANDING_DEFINITION,),
)


def resolve_post_template_reference(value: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve a future Landing-template design reference without Project data."""

    definition = POST_TEMPLATE_REGISTRY.resolve_reference(value)
    return {
        "identity": definition.identity.to_reference(),
        "name": definition.name,
        "description": definition.description,
        "canvas": None if definition.canvas is None else dict(definition.canvas),
        "components": [
            {
                "component_id": component["component_id"],
                "role": component["role"],
            }
            for component in definition.catalog()["components"]
        ],
    }
