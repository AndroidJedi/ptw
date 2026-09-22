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
import random
import re
from typing import Any, Mapping

from .studio import STUDIO_FONT_FAMILIES, StudioRenderer, inspect_media
from .studio_primitives import PrimitiveTemplate, PRIMITIVE_TEMPLATE_SCHEMA
from .template_assets import ASSET_IDS, RENDERER_VERSION, asset_bytes, document_asset_manifest
from .template_registry import TemplateCapabilities, TemplateDefinition, TemplateIdentity

COMPONENT_VERSION = 6
COMPONENT_TYPES = (
    "text", "image", "cutout_image", "button", "store_badge", "card",
    "overlay", "decoration", "brand_motif", "phone", "brand",
)
ROLES = ("headline", "description", "hero", "cta", "secondary_media", "footer", "meta", "decoration", "brand")
PLACEHOLDERS = (
    "Title", "Supporting text", "Image", "Action", "Section title",
    "Body text", "Caption", "01", "02", "03", "Natal symbol",
    "App Store", "Google Play", "",
)
COMPONENT_FIELDS = {
    "id", "type", "role", "box", "mobile_box", "fill", "color", "border_color",
    "border_width", "radius", "opacity", "font_family", "font_size", "font_weight",
    "align", "placeholder", "fit", "focal_x", "focal_y", "gradient", "enabled",
    "asset_id", "rotation_degrees", "badge_surface", "repeat_min", "repeat_max",
}
REPEATLESS_COMPONENT_FIELDS = COMPONENT_FIELDS - {"repeat_min", "repeat_max"}
REPEAT_WITHOUT_SURFACE_FIELDS = COMPONENT_FIELDS - {"badge_surface"}
PREVIOUS_COMPONENT_FIELDS = REPEATLESS_COMPONENT_FIELDS - {"badge_surface"}
LEGACY_COMPONENT_FIELDS = PREVIOUS_COMPONENT_FIELDS - {"asset_id", "rotation_degrees"}
LEGACY_WITH_SURFACE_FIELDS = REPEATLESS_COMPONENT_FIELDS - {"asset_id", "rotation_degrees"}
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
    if not isinstance(value, Mapping) or frozenset(value) not in {
        frozenset(COMPONENT_FIELDS), frozenset(REPEATLESS_COMPONENT_FIELDS),
        frozenset(REPEAT_WITHOUT_SURFACE_FIELDS), frozenset(PREVIOUS_COMPONENT_FIELDS),
        frozenset(LEGACY_COMPONENT_FIELDS), frozenset(LEGACY_WITH_SURFACE_FIELDS),
    }:
        raise ValueError("Component fields are invalid")
    result = deepcopy(dict(value))
    if not result.get("asset_id"):
        result["asset_id"] = {
            "cutout_image": "neutral_person_stock_v1",
            "brand_motif": "natal_symbol",
            "store_badge": "app_store_badge_en" if value.get("placeholder") == "App Store" else "google_play_badge_en",
        }.get(str(value.get("type")), "")
    result.setdefault("rotation_degrees", 0)
    result.setdefault("badge_surface", "slot_pill")
    result.setdefault("repeat_min", 1)
    result.setdefault("repeat_max", 1)
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
    number(result["rotation_degrees"], -360, 360)
    if (type(result["repeat_min"]) is not int or type(result["repeat_max"]) is not int
            or not 1 <= result["repeat_min"] <= result["repeat_max"] <= 8
            or (value["type"] != "brand_motif" and result["repeat_max"] != 1)):
        raise ValueError("Motif repeat range must be 1–8")
    if result["asset_id"] not in ASSET_IDS:
        raise ValueError("Component asset is not registered")
    if result["badge_surface"] not in {"slot_pill", "asset_only"} or (value["type"] != "store_badge" and result["badge_surface"] != "slot_pill"):
        raise ValueError("Badge surface is not registered for this component")
    if value["font_family"] not in STUDIO_FONT_FAMILIES or value["align"] not in ("left", "center", "right"):
        raise ValueError("Typography option is not registered")
    if value["fit"] not in ("cover", "contain", "stretch") or value["placeholder"] not in PLACEHOLDERS:
        raise ValueError("Only bounded non-domain placeholders and registered crop settings are allowed")
    variants = {
        "cutout_image": {"Image"},
        "brand_motif": {"Natal symbol"},
        "store_badge": {"App Store", "Google Play"},
    }
    if value["type"] in variants and value["placeholder"] not in variants[value["type"]]:
        raise ValueError("Component variant is not registered for this reusable type")
    expected_asset = {
        "cutout_image": "neutral_person_stock_v1",
        "brand_motif": "natal_symbol",
        "store_badge": "app_store_badge_en" if value["placeholder"] == "App Store" else "google_play_badge_en",
    }.get(value["type"], "")
    allowed_assets = {expected_asset}
    if value["type"] == "store_badge":
        allowed_assets.add("owner_app_store_badge_v1" if value["placeholder"] == "App Store" else "owner_google_play_badge_v1")
    if result["asset_id"] not in allowed_assets:
        raise ValueError("Component asset does not match its registered reusable type")
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
            "focal_x": .5, "focal_y": .5, "gradient": [], "enabled": True,
            "asset_id": "", "rotation_degrees": 0, "badge_surface": "slot_pill",
            "repeat_min": 1, "repeat_max": 1}


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
    # Registered visual extensions stay visible when an older saved analysis is
    # resumed. Otherwise its historical component-type shortlist would hide the
    # capability that was added to resolve its evidenced gap.
    extensions = {"cutout_image", "brand_motif", "store_badge"}
    selected = [t for t in COMPONENT_TYPES if types is None or t in types or t in extensions]
    return {"version": COMPONENT_VERSION, "surface": surface, "types": selected, "roles": list(ROLES),
            "reused_native_components": "phone uses the existing fixed iPhone compositor with an editable hero-art slot; brand uses the canonical Natal lock-up. Neither is a generated screenshot widget.",
            "placeholders": list(PLACEHOLDERS), "fonts": list(STUDIO_FONT_FAMILIES),
            "layout": "Ordered layers; box and mobile_box are [x,y,width,height] in 0–1000 canvas units. Separate mobile composition for Landing.",
            "settings": "fill/color/border_color HEX; border_width 0–12; radius 0–200; opacity 0–1; font_size 12–180 native pixels; font_weight 100–900; align left/center/right; fit cover/contain/stretch; focal_x/y 0–1; gradient [] or 2 HEX colors; enabled boolean; rotation_degrees -360–360; brand_motif repeat_min/repeat_max 1–8 in its box, seeded per Post for stable variety; store_badge badge_surface slot_pill/asset_only; fixed visuals require an allowlisted asset_id.",
            "registered_variants": {
                "cutout_image": ["Image"],
                "brand_motif": ["Natal symbol"],
                "store_badge": ["App Store", "Google Play"],
            },
            "store_badge_assets": {"App Store": ["app_store_badge_en", "owner_app_store_badge_v1"],
                                   "Google Play": ["google_play_badge_en", "owner_google_play_badge_v1"]},
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


def neutral_cutout_image() -> bytes:
    """Compatibility accessor for the pinned stock fixture; no pixels are generated."""

    return asset_bytes("neutral_person_stock_v1")[0]


def fixed_component_assets(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Assets shared by gallery previews and Project Post rendering."""

    assets: dict[str, dict[str, Any]] = {}
    for item in normalize_document(document)["components"]:
        if not item["asset_id"]:
            continue
        data, mime_type = asset_bytes(item["asset_id"])
        assets[item["id"]] = {"bytes": data, "mime_type": mime_type}
    return assets


def _motif_nodes(c: Mapping[str, Any], props: dict, *, seed_value: str) -> list[dict]:
    """Expand one motif region into stable small instances for a given Post."""
    digest = hashlib.sha256(f"{seed_value}:{c['id']}".encode()).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    count = rng.randint(c["repeat_min"], c["repeat_max"])
    cells = [(column, row) for row in range(4) for column in range(2)]
    rng.shuffle(cells)
    cell_width, cell_height = props["width"] / 2, props["height"] / 4
    icon_width = max(10, min(cell_width * .48, cell_height * .68, 48))
    icon_height = icon_width * .8
    result = []
    for index, (column, row) in enumerate(cells[:count], 1):
        local = dict(props)
        local.update({
            "x": props["x"] + column * cell_width + (cell_width - icon_width) / 2 + rng.uniform(-.09, .09) * cell_width,
            "y": props["y"] + row * cell_height + (cell_height - icon_height) / 2 + rng.uniform(-.08, .08) * cell_height,
            "width": icon_width, "height": icon_height,
            "rotation": c["rotation_degrees"] + rng.randint(-18, 18),
        })
        result.append({"id": f"{c['id']}_{index}", "type": "image", "props": local})
    return result


def primitive(document: Mapping[str, Any], *, surface: str, mobile: bool = False,
              content: Mapping[str, str] | None = None, variant_seed: str = "") -> PrimitiveTemplate:
    doc = normalize_document(document)
    width = 360 if mobile else doc["canvas"]["width"]
    height = doc["canvas"]["mobile_height"] if mobile else doc["canvas"]["height"]
    children, roles, assets, repeated_motifs = [], {}, {}, []
    content = dict(content or {})
    if set(content) - {c["id"] for c in doc["components"] if c["type"] in ("text", "button")}:
        raise ValueError("Unknown content role")
    for c in doc["components"]:
        x, y, w, h = c["mobile_box" if mobile else "box"]
        kind = {
            "overlay": "card", "decoration": "card", "phone": "image",
            "brand": "image", "cutout_image": "image",
            "brand_motif": "image", "store_badge": "image",
        }.get(c["type"], c["type"])
        props = {"position": "absolute", "x": x * width / 1000, "y": y * height / 1000,
            "width": w * width / 1000, "height": h * height / 1000, "visible": c["enabled"],
            # Legacy badges paint the slot pill. An asset_only badge is already
            # complete artwork and must not receive another black background.
            # Other image slots remain transparent unless their primitive
            # explicitly opts into a background.
            "background_color": c["fill"] if kind not in ("text", "image") or (c["type"] == "store_badge" and c["badge_surface"] == "slot_pill") else None,
            "border_color": c["border_color"], "border_width": 0 if c["type"] == "store_badge" and c["badge_surface"] == "asset_only" else c["border_width"],
            "radius": 0 if c["type"] == "store_badge" and c["badge_surface"] == "asset_only" else c["radius"],
            "opacity": c["opacity"], "rotation": c["rotation_degrees"],
            "background_gradient": [] if c["type"] == "store_badge" and c["badge_surface"] == "asset_only" else c["gradient"]}
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
            replaceable = c["type"] in {"image", "cutout_image", "phone"}
            assets[c["id"]] = {"kind": "image", "allowed_mime_types": ["image/png", "image/jpeg", "image/webp"], "required": False,
                "provenance": "Reusable image slot; gallery uses a neutral fixture." if replaceable else "Fixed allowlisted template visual."}
        nodes = (_motif_nodes(c, props, seed_value=variant_seed or sha(doc))
                 if c["type"] == "brand_motif" and c["repeat_max"] > 1 else
                 [{"id": c["id"], "type": kind, "props": props}])
        if c["type"] == "brand_motif" and c["repeat_max"] > 1:
            repeated_motifs.extend(nodes)
        else:
            children.extend(nodes)
        roles.setdefault(c["role"], []).extend(node["id"] for node in nodes)
    if repeated_motifs:
        # Full-canvas art sits below these watermarks. Foreground surfaces,
        # including a white footer, then mask them before copy and hero paint.
        after_backdrop = next((index + 1 for index, node in enumerate(children)
                               if node["type"] == "card" and node["props"]["x"] == 0
                               and node["props"]["y"] == 0
                               and node["props"]["width"] == width
                               and node["props"]["height"] == height), 0)
        children[after_backdrop:after_backdrop] = repeated_motifs
    return PrimitiveTemplate.from_dict({"schema": PRIMITIVE_TEMPLATE_SCHEMA, "template_id": "declarative_design",
        "template_type": surface, "version": 1, "status": "draft",
        "root": {"id": "canvas", "type": "frame", "props": {"width": width, "height": height, "background_color": doc["background"]}, "children": children},
        "semantic_roles": roles, "assets": assets, "rules": [],
        "provenance": {"base_template_id": None, "base_version": None, "base_sha256": None, "reference_ids": [], "change_note": "Declarative template compiler v1"}})


def render(document: Mapping[str, Any], *, surface: str, mobile: bool = False,
           content: Mapping[str, str] | None = None, assets: Mapping[str, Any] | None = None) -> dict:
    template = primitive(document, surface=surface, mobile=mobile, content=content)
    by_id = {item["id"]: item for item in normalize_document(document)["components"]}
    fixtures = {
        key: {"bytes": placeholder_image(), "mime_type": "image/png"}
        for key in template.document["assets"] if by_id[key]["type"] in {"image", "phone"}
    }
    fixtures.update(fixed_component_assets(document))
    for key, item in by_id.items():
        if item["type"] == "brand":
            from .natal_brand import natal_logo_bytes
            fixtures[key] = {"bytes": natal_logo_bytes(), "mime_type": "image/png"}
    if assets:
        if set(assets) - set(fixtures):
            raise ValueError("Unknown image slot")
        protected = {item["id"] for item in by_id.values() if item["type"] in {"brand_motif", "store_badge", "brand"}}
        if protected & set(assets):
            raise ValueError("Fixed template visual cannot be replaced")
        for key, record in assets.items():
            if by_id[key]["type"] == "cutout_image":
                from .template_cutout import cutout_png
                source = bytes(record["bytes"])
                inspect_media(source, str(record["mime_type"]))
                fixtures[key] = {"bytes": cutout_png(source), "mime_type": "image/png"}
            else:
                fixtures[key] = record
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


def render_contract_sha256(document: Mapping[str, Any]) -> str:
    """Invalidate saved PNG reuse when the compiler or a fixed asset changes."""

    doc = normalize_document(document)
    from .template_cutout import MODEL_SHA256
    return sha({"document": doc, "renderer_version": RENDERER_VERSION,
                "cutout_model_sha256": MODEL_SHA256 if any(c["type"] == "cutout_image" for c in doc["components"]) else None,
                "assets": [{"asset_id": item["asset_id"], "sha256": item["sha256"]}
                           for item in document_asset_manifest(doc)]})


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
        capabilities=TemplateCapabilities(image_slots=tuple(c["id"] for c in doc["components"] if c["type"] in ("image", "cutout_image", "phone")), supports_manual_agent=False),
        renderer_key=RENDERER_VERSION, editor_key="templates.declarative.v1",
        render=lambda configuration=None, content=None, assets=None, mobile=False: render(doc if configuration is None else configuration, surface=record["surface"], content=content, assets=assets, mobile=mobile))
