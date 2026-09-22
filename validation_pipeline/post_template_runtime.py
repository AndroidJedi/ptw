"""Bind immutable authored layouts to an existing Project Post's copy and image."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping

from .post_templates import PHONE_METRICS_DEFINITION, PostTemplateDefinition
from .studio_phone_metrics import normalize_phone_metrics_content
from .studio_primitives import PrimitiveTemplate
from .template_components import bounded_text, normalize_document, primitive, sha
from .template_registry import TemplateCapabilities, TemplateIdentity


@dataclass(frozen=True)
class AuthoredPostDefinition(PostTemplateDefinition):
    document: dict


def text_fields(document):
    return [{"id": c["id"], "role": c["role"]} for c in document["components"]
            if c["type"] in {"text", "button"}]


def bind_content(document, content, previous_fields=()):
    """Map by semantic role and occurrence; never use gallery placeholder copy."""
    original = {k: deepcopy(v) for k, v in content.items() if k != "template_text"}
    source = normalize_phone_metrics_content(original)
    roles = {
        "headline": [source["hero_title"], source["phone_hero_title"]],
        "description": [source["supporting_text"], *[s["label"] for s in source["stats"]]],
        "cta": [source["cta"], *source["phone_buttons"]],
        "meta": [source["offer"], *[s["value"] for s in source["stats"]]],
    }
    previous = {}
    for field in previous_fields:
        previous.setdefault(field["role"], []).append(content.get("template_text", {}).get(field["id"], ""))
    roles.update(previous)
    counters, values = {}, {}
    for field in text_fields(document):
        role = field["role"]
        index = counters.get(role, 0)
        candidates = roles.get(role, [])
        from .approved_posts import plain_studio_text
        values[field["id"]] = plain_studio_text(candidates[index]) if index < len(candidates) else ""
        counters[role] = index + 1
    return {**source, "template_text": values}


def post_definition(record):
    if record["surface"] != "post" or record.get("builtin"):
        raise ValueError("Select an accepted Post template")
    doc = normalize_document(record["document"])
    fields = text_fields(doc)
    identity = TemplateIdentity("post", record["template_id"], record["template_version"], record["template_sha256"])

    def content(value):
        if not isinstance(value, Mapping):
            raise ValueError("Post content must be an object")
        source = normalize_phone_metrics_content({k: v for k, v in value.items() if k != "template_text"})
        texts = value.get("template_text")
        if not isinstance(texts, dict) or set(texts) != {f["id"] for f in fields}:
            raise ValueError("Post text must match the selected template's fields")
        return {**source, "template_text": {k: bounded_text(v, 500, "Post text", empty=True) for k, v in texts.items()}}

    def build(configuration, value, *, variant_seed=""):
        result = deepcopy(primitive(doc, surface="post", content=content(value)["template_text"],
                                    variant_seed=variant_seed).document)
        result.update(template_id=identity.template_id, version=identity.template_version)
        for node in result["root"]["children"]:
            if node["type"] == "text":
                node["props"].update(text_fit="shrink", min_font_size=14)
        return PrimitiveTemplate.from_dict(result)

    def catalog():
        return {"schema": "ptw.studio.authored-post-catalog.v1", **identity.to_reference(),
                "name": doc["name"], "canvas": doc["canvas"], "semantic_roles": [f["role"] for f in fields],
                "components": [], "asset_slots": PHONE_METRICS_DEFINITION.asset_slots(),
                "sha256": sha(doc)}

    def settings(configuration, value):
        normalized = content(value)
        result = {"template_id": identity.template_id, "template_reference": identity.to_reference(),
                  "content": normalized["template_text"], "logo": configuration["logo"]}
        return {**result, "sha256": sha(result)}

    return AuthoredPostDefinition(
        document=doc,
        identity=identity, name=doc["name"], description=doc["description"], canvas=doc["canvas"],
        catalog=catalog, agent_catalog=catalog,
        default_configuration=PHONE_METRICS_DEFINITION.default_configuration,
        default_content=lambda: bind_content(doc, PHONE_METRICS_DEFINITION.default_content()),
        normalize_configuration=PHONE_METRICS_DEFINITION.normalize_configuration, normalize_content=content,
        component_settings=settings, capabilities=TemplateCapabilities(image_slots=("phone_screen",), supports_manual_agent=False, supports_generation=False),
        renderer_key="post.declarative.pillow.v1", editor_key="post.declarative.react",
        build_template=build, semantic_data=lambda configuration, value: {},
        asset_slots=PHONE_METRICS_DEFINITION.asset_slots,
    )
