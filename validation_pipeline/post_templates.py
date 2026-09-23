"""Registered Post template definitions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .studio_phone_metrics import (
    DEFAULT_PHONE_CONFIG,
    DEFAULT_PHONE_CONTENT,
    PHONE_ASSET_SLOTS,
    PHONE_METRICS_TEMPLATE_ID,
    PHONE_METRICS_TEMPLATE_VERSION,
    build_phone_metrics_template,
    normalize_phone_metrics_config,
    normalize_phone_metrics_content,
    phone_metrics_catalog,
    phone_metrics_component_settings,
    phone_metrics_semantic_data,
)
from .template_registry import (
    TemplateCapabilities,
    TemplateDefinition,
    TemplateIdentity,
    TemplateRegistry,
)


@dataclass(frozen=True)
class PostTemplateDefinition(TemplateDefinition):
    """Registered Post metadata plus its renderer-facing runtime hooks."""

    build_template: Callable[[Mapping[str, Any], Mapping[str, Any]], Any]
    semantic_data: Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, str]]
    asset_slots: Callable[[], Mapping[str, Mapping[str, Any]]]


def _configuration() -> dict:
    return normalize_phone_metrics_config(deepcopy(DEFAULT_PHONE_CONFIG))


def _content() -> dict:
    return normalize_phone_metrics_content(deepcopy(DEFAULT_PHONE_CONTENT))


def _agent_catalog() -> dict[str, Any]:
    """Keep generation context descriptive; the output schema owns constraints."""

    catalog = phone_metrics_catalog()
    slots = deepcopy(catalog["asset_slots"])
    slots["phone_screen"]["description"] = "Owner-directed artwork in the selected visual mode; text and UI are omitted by default but allowed when requested."
    return {
        "schema": catalog["schema"],
        "template_id": catalog["template_id"],
        "template_version": catalog["template_version"],
        "canvas": deepcopy(catalog["canvas"]),
        "semantic_roles": deepcopy(catalog["semantic_roles"]),
        "components": [{
            "component_id": item["component_id"],
            "role": item["role"],
            "setting_ids": deepcopy(item["setting_ids"]),
        } for item in catalog["components"]],
        "asset_slots": slots,
        "sha256": catalog["sha256"],
    }


def _asset_slots() -> Mapping[str, Mapping[str, Any]]:
    return PHONE_ASSET_SLOTS


_catalog = phone_metrics_catalog()
_default_configuration = _configuration()
_default_content = _content()
_template = build_phone_metrics_template(_default_configuration, _default_content)
PHONE_METRICS_DEFINITION = PostTemplateDefinition(
    identity=TemplateIdentity(
        surface="post",
        template_id=PHONE_METRICS_TEMPLATE_ID,
        template_version=PHONE_METRICS_TEMPLATE_VERSION,
        template_sha256=_template.digest,
    ),
    name="Phone & metrics",
    description="Natal 4:5 phone creative with three metrics and a full-width CTA.",
    canvas={"width": 1080, "height": 1350},
    catalog=phone_metrics_catalog,
    agent_catalog=_agent_catalog,
    default_configuration=_configuration,
    default_content=_content,
    normalize_configuration=normalize_phone_metrics_config,
    normalize_content=normalize_phone_metrics_content,
    component_settings=phone_metrics_component_settings,
    capabilities=TemplateCapabilities(image_slots=tuple(PHONE_ASSET_SLOTS)),
    renderer_key="post.phone_metrics.pillow",
    editor_key="post.phone_metrics.react",
    build_template=build_phone_metrics_template,
    semantic_data=phone_metrics_semantic_data,
    asset_slots=_asset_slots,
)

POST_TEMPLATE_REGISTRY = TemplateRegistry(
    "post", (PHONE_METRICS_DEFINITION,),
)
