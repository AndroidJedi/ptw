"""Bounded reusable components compiled into the existing Studio primitive renderer.

Only design placeholders live here. Domain content and reference pixels never do.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable
import hashlib
from io import BytesIO
import json
import math
import re
from typing import Any, Mapping

from .studio import STUDIO_FONT_FAMILIES, StudioRenderer
from .studio_primitives import PrimitiveTemplate, PRIMITIVE_TEMPLATE_SCHEMA
from .template_registry import TemplateCapabilities, TemplateDefinition, TemplateIdentity

COMPONENT_VERSION = 1
COMPONENT_TYPES = ("text", "image", "button", "card", "overlay", "decoration", "phone", "brand")
ROLES = ("headline", "description", "hero", "cta", "secondary_media", "footer", "meta", "decoration", "brand")
PLACEHOLDERS = ("Title", "Supporting text", "Image", "Action", "Section title", "Body text", "Caption", "01", "02", "03", "")
COMPONENT_FIELDS = {
    "id", "type", "role", "box", "mobile_box", "fill", "color", "border_color",
    "border_width", "radius", "opacity", "font_family", "font_size", "font_weight",
    "align", "placeholder", "fit", "focal_x", "focal_y", "gradient", "enabled",
}
DOCUMENT_FIELDS = {"name", "description", "canvas", "background", "components"}
MAX_DOCUMENT_BYTES = 14_000


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def bounded_text(value: Any, maximum: int, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()) or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} must be bounded plain text")
    return value.strip()


def number(value: Any, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError("Component number is outside its bounded range")
    return value


def color(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("Component color must be #RRGGBB")
    return value.upper()


def box(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("Component box requires x, y, width, height in 0–1000 units")
    try:
        result = [number(v, 0 if i < 2 else 1, 1000) for i, v in enumerate(value)]
    except ValueError as error:
        raise ValueError("Box coordinates require 0–1000 units, width/height >=1; e.g. [60,50,880,140], not 0–1 fractions") from error
    if result[0] + result[2] > 1000 or result[1] + result[3] > 1000:
        raise ValueError("Component box exceeds the canvas")
    return result


def component(value: Any) -> dict:
    if not isinstance(value, Mapping) or set(value) != COMPONENT_FIELDS:
        raise ValueError("Component fields are invalid")
    result = deepcopy(dict(value))
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", str(value["id"])):
        raise ValueError("Component ID must describe a reusable semantic role")
    if re.search(r"reference|specific|widget|template\d", value["id"], re.I):
        raise ValueError("Reference-specific component names are not allowed")
    if value["type"] not in COMPONENT_TYPES or value["role"] not in ROLES:
        raise ValueError("Component type or role is not registered")
    for key in ("box", "mobile_box"):
        result[key] = box(value[key])
    for key in ("fill", "color", "border_color"):
        result[key] = color(value[key])
    for key, low, high in (("border_width", 0, 12), ("radius", 0, 200), ("opacity", 0, 1),
                           ("font_size", 12, 180), ("font_weight", 100, 900), ("focal_x", 0, 1), ("focal_y", 0, 1)):
        number(value[key], low, high)
    if value["font_family"] not in STUDIO_FONT_FAMILIES or value["align"] not in ("left", "center", "right"):
        raise ValueError("Typography option is not registered")
    if value["fit"] not in ("cover", "contain", "stretch") or value["placeholder"] not in PLACEHOLDERS:
        raise ValueError("Only bounded non-domain placeholders and registered crop settings are allowed")
    if not isinstance(value["enabled"], bool) or not isinstance(value["gradient"], list) or len(value["gradient"]) not in (0, 2):
        raise ValueError("Component visibility or gradient is invalid")
    result["gradient"] = [color(v) for v in value["gradient"]]
    return result


def normalize_document(value: Any) -> dict:
    if not isinstance(value, Mapping) or set(value) != DOCUMENT_FIELDS:
        raise ValueError("Template design fields are invalid")
    if len(canonical(value).encode()) > MAX_DOCUMENT_BYTES:
        raise ValueError("Template design exceeds its compact byte budget")
    canvas = value["canvas"]
    if not isinstance(canvas, Mapping) or set(canvas) != {"width", "height", "mobile_height"}:
        raise ValueError("Template canvas fields are invalid")
    for key in canvas:
        if type(canvas[key]) is not int:
            raise ValueError("Canvas dimensions must be integers")
        number(canvas[key], 360, 2400)
    if not isinstance(value["components"], list) or not 1 <= len(value["components"]) <= 16:
        raise ValueError("Template requires 1–16 reusable component instances")
    components = [component(v) for v in value["components"]]
    if len({v["id"] for v in components}) != len(components):
        raise ValueError("Component IDs must be unique")
    return {"name": bounded_text(value["name"], 80, "Template name"),
            "description": bounded_text(value["description"], 320, "Template description"),
            "canvas": dict(canvas), "background": color(value["background"]), "components": components}


def new_component(identifier: str, kind: str, role: str, bounds: list, text: str = "") -> dict:
    return {"id": identifier, "type": kind, "role": role, "box": bounds, "mobile_box": bounds,
            "fill": "#E9EEF5", "color": "#14243A", "border_color": "#CED8E4", "border_width": 0,
            "radius": 20, "opacity": 1, "font_family": "Inter", "font_size": 48,
            "font_weight": 500, "align": "left", "placeholder": text, "fit": "cover",
            "focal_x": .5, "focal_y": .5, "gradient": [], "enabled": True}


def seed(surface: str) -> dict:
    return normalize_document({"name": f"New {surface} template", "description": "Reusable design with editable component roles.",
        "canvas": {"width": 1080 if surface == "post" else 1280, "height": 1350 if surface == "post" else 1800, "mobile_height": 1800},
        "background": "#F7F8FA", "components": [
            new_component("title", "text", "headline", [60, 50, 880, 140], "Title"),
            new_component("support", "text", "description", [60, 210, 880, 90], "Supporting text"),
            new_component("visual", "image", "hero", [60, 330, 880, 440], "Image"),
            {**new_component("action", "button", "cta", [60, 830, 880, 100], "Action"), "fill": "#2463EB", "color": "#FFFFFF", "align": "center"},
        ]})


def catalog(surface: str, types: list[str] | None = None) -> dict:
    selected = [t for t in COMPONENT_TYPES if types is None or t in types]
    return {"version": COMPONENT_VERSION, "surface": surface, "types": selected, "roles": list(ROLES),
            "reused_native_components": "phone uses the existing fixed iPhone compositor with an editable hero-art slot; brand uses the canonical Natal lock-up. Neither is a generated screenshot widget.",
            "placeholders": list(PLACEHOLDERS), "fonts": list(STUDIO_FONT_FAMILIES),
            "layout": "Ordered layers; box and mobile_box are [x,y,width,height] in 0–1000 canvas units. Separate mobile composition for Landing.",
            "settings": "fill/color/border_color HEX; border_width 0–12; radius 0–200; opacity 0–1; font_size 12–180 native pixels; font_weight 100–900; align left/center/right; fit cover/contain/stretch; focal_x/y 0–1; gradient [] or 2 HEX colors; enabled boolean.",
            "priority": ["existing settings", "existing composition", "reusable parameter", "reusable component", "exception with justification"],
            "component_example": new_component("section_title", "text", "headline", [60, 40, 880, 150], "Section title")}


def apply_edits(documents: Mapping[str, dict], edits: Any) -> dict:
    if not isinstance(edits, list) or len(edits) > 64:
        raise ValueError("Template agent accepts at most 64 patches")
    result = deepcopy(dict(documents))
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"surface", "path", "value"} or edit["surface"] not in result:
            raise ValueError("Template patch scope is invalid")
        path = edit["path"]
        if not isinstance(path, str) or len(path) > 100:
            raise ValueError("Template patch path is invalid")
        parts = path.split(".")
        target = result[edit["surface"]]
        # One bounded component insertion/removal, or scalar/box setting.
        if len(parts) == 2 and parts[0] == "components" and parts[1] == "append":
            target["components"].append(component(edit["value"]))
            continue
        if len(parts) == 2 and parts[0] == "remove":
            if parts[1] not in {c["id"] for c in target["components"]}:
                raise ValueError("Unknown component removal")
            target["components"] = [c for c in target["components"] if c["id"] != parts[1]]
            continue
        if parts[0] == "components" and len(parts) == 3:
            found = [c for c in target["components"] if c["id"] == parts[1]]
            if not found or parts[2] not in COMPONENT_FIELDS - {"id"}:
                raise ValueError("Template patch component setting is invalid")
            found[0][parts[2]] = deepcopy(edit["value"])
        elif len(parts) == 2 and parts[0] == "canvas" and parts[1] in target["canvas"]:
            target["canvas"][parts[1]] = edit["value"]
        elif len(parts) == 1 and parts[0] in {"name", "description", "background"}:
            target[parts[0]] = edit["value"]
        else:
            raise ValueError("Template patch path is not editable")
    return {s: normalize_document(d) for s, d in result.items()}


def placeholder_image() -> bytes:
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (640, 480), "#DBE4F0")
    draw = ImageDraw.Draw(image)
    draw.ellipse((340, 50, 520, 230), fill="#A4BBDC")
    draw.polygon([(0, 480), (220, 160), (460, 480)], fill="#7D9EC7")
    draw.polygon([(270, 480), (480, 270), (640, 480)], fill="#ABC3DF")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def primitive(document: Mapping[str, Any], *, surface: str, mobile: bool = False,
              content: Mapping[str, str] | None = None) -> PrimitiveTemplate:
    doc = normalize_document(document)
    width = 360 if mobile else doc["canvas"]["width"]
    height = doc["canvas"]["mobile_height"] if mobile else doc["canvas"]["height"]
    children, roles, assets = [], {}, {}
    content = dict(content or {})
    if set(content) - {c["id"] for c in doc["components"] if c["type"] in ("text", "button")}:
        raise ValueError("Unknown content role")
    for c in doc["components"]:
        x, y, w, h = c["mobile_box" if mobile else "box"]
        kind = {"overlay": "card", "decoration": "card", "phone": "image", "brand": "image"}.get(c["type"], c["type"])
        props = {"position": "absolute", "x": x * width / 1000, "y": y * height / 1000,
            "width": w * width / 1000, "height": h * height / 1000, "visible": c["enabled"],
            "background_color": c["fill"] if kind not in ("text", "image") else None,
            "border_color": c["border_color"], "border_width": c["border_width"], "radius": c["radius"],
            "opacity": c["opacity"], "background_gradient": c["gradient"]}
        if kind in ("text", "button"):
            text = content.get(c["id"], c["placeholder"])
            bounded_text(text, 500, "Bound content", empty=True)
            props.update({"text" if kind == "text" else "label": text,
                "color" if kind == "text" else "label_color": c["color"], "font_family": c["font_family"],
                "font_size": max(14, c["font_size"] * (.6 if mobile else 1)), "font_weight": int(c["font_weight"]),
                "text_align": c["align"], "vertical_align": "center" if kind == "button" else "top",
                "text_fit": "fixed", "line_height": 1.15})
        if kind == "shape":
            props["fill"] = c["fill"]
        if kind == "image":
            props.update({"asset": c["id"], "fit": c["fit"], "focal_x": c["focal_x"], "focal_y": c["focal_y"], "mask": "rounded_rect" if c["type"] == "image" else "none"})
            if c["type"] in ("phone", "brand"):
                props["fit"] = "contain"
            assets[c["id"]] = {"kind": "image", "allowed_mime_types": ["image/png", "image/jpeg", "image/webp"], "required": False, "provenance": "Reusable image slot; gallery uses a neutral geometry fixture."}
        children.append({"id": c["id"], "type": kind, "props": props})
        roles.setdefault(c["role"], []).append(c["id"])
    return PrimitiveTemplate.from_dict({"schema": PRIMITIVE_TEMPLATE_SCHEMA, "template_id": "declarative_design",
        "template_type": surface, "version": 1, "status": "draft",
        "root": {"id": "canvas", "type": "frame", "props": {"width": width, "height": height, "background_color": doc["background"]}, "children": children},
        "semantic_roles": roles, "assets": assets, "rules": [],
        "provenance": {"base_template_id": None, "base_version": None, "base_sha256": None, "reference_ids": [], "change_note": "Declarative template compiler v1"}})


def render(document: Mapping[str, Any], *, surface: str, mobile: bool = False,
           content: Mapping[str, str] | None = None, assets: Mapping[str, Any] | None = None) -> dict:
    template = primitive(document, surface=surface, mobile=mobile, content=content)
    fixtures = {key: {"bytes": placeholder_image(), "mime_type": "image/png"} for key in template.document["assets"]}
    if assets:
        if set(assets) - set(fixtures):
            raise ValueError("Unknown image slot")
        fixtures.update(assets)
    for c in document["components"]:
        if c["type"] == "phone":
            from .studio_phone_metrics import compose_phone_device_asset
            fixtures[c["id"]] = compose_phone_device_asset(fixtures[c["id"]]["bytes"], "Title", "Action", "none", ["Action", "Action", "Action"])
        elif c["type"] == "brand":
            if assets and c["id"] in assets:
                raise ValueError("Canonical Natal identity cannot be replaced")
            from .natal_brand import natal_logo_bytes
            fixtures[c["id"]] = {"bytes": natal_logo_bytes(), "mime_type": "image/png"}
    return StudioRenderer().render_preview(template, semantic_data={}, assets=fixtures)


@dataclass(frozen=True)
class DeclarativeTemplateDefinition(TemplateDefinition):
    render: Callable[..., dict]


def definition(record: Mapping[str, Any]) -> TemplateDefinition:
    doc = normalize_document(record["document"])
    def normalize_content(value: Mapping) -> dict:
        primitive(doc, surface=record["surface"], content=value)
        return dict(value)
    return DeclarativeTemplateDefinition(identity=TemplateIdentity(record["surface"], record["template_id"], record["template_version"], record["template_sha256"]),
        name=doc["name"], description=doc["description"], canvas=doc["canvas"],
        catalog=lambda: catalog(record["surface"]), agent_catalog=lambda: catalog(record["surface"]),
        default_configuration=lambda: deepcopy(doc), default_content=lambda: {},
        normalize_configuration=normalize_document, normalize_content=normalize_content,
        component_settings=lambda configuration, content: {"configuration": normalize_document(configuration), "content": normalize_content(content)},
        capabilities=TemplateCapabilities(image_slots=tuple(c["id"] for c in doc["components"] if c["type"] in ("image", "phone")), supports_manual_agent=False),
        renderer_key="studio.declarative.pillow.v1", editor_key="templates.declarative.v1",
        render=lambda configuration=None, content=None, assets=None, mobile=False: render(doc if configuration is None else configuration, surface=record["surface"], content=content, assets=assets, mobile=mobile))
