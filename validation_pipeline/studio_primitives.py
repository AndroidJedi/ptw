"""Versioned, configuration-first primitives for internal Studio rendering.

The deployed ``StudioRecipeV2`` frame renderer remains an immutable compatibility
path. This module is reached through ``StudioRenderer.render_preview`` and is an
internal engine beneath the bounded universal-ad configuration, not an exposed
general-purpose editor.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import copy
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Sequence


PRIMITIVE_TEMPLATE_SCHEMA = "ptw.studio.primitive-template.v1"
PRIMITIVE_CATALOG_VERSION = "ptw-studio-primitive-catalog-v1"
PRIMITIVE_TYPES = (
    "frame", "container", "stack", "text", "image", "button", "icon",
    "shape", "spacer", "list", "card",
)
CONTAINER_TYPES = frozenset({"frame", "container", "stack", "list", "card"})
SEMANTIC_ROLE_NAMES = frozenset({
    "hero", "headline", "hook", "description", "cta", "proof", "brand",
    "secondary_media", "footer", "meta",
})
STATUS_VALUES = frozenset({"draft", "approved", "retired"})
SCOPE_VALUES = frozenset({"platform", "template_type", "template", "instance"})
_ID_PATTERN = re.compile(r"[a-z][a-z0-9_-]{1,63}")
_SOURCE_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,127}")
_COLOR_PATTERN = re.compile(r"#[0-9A-F]{6}(?:[0-9A-F]{2})?")
_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def _spec(kind: str, default: Any, **options: Any) -> dict[str, Any]:
    return {"kind": kind, "default": default, **options}


COMMON_PROPERTIES: dict[str, dict[str, Any]] = {
    "position": _spec("enum", "flow", values=("flow", "absolute")),
    "x": _spec("length", 0.0, allow_auto=False),
    "y": _spec("length", 0.0, allow_auto=False),
    "width": _spec("length", "auto", allow_auto=True, positive=True),
    "height": _spec("length", "auto", allow_auto=True, positive=True),
    "min_width": _spec("nullable_number", None, minimum=0.0),
    "max_width": _spec("nullable_number", None, minimum=0.0),
    "min_height": _spec("nullable_number", None, minimum=0.0),
    "max_height": _spec("nullable_number", None, minimum=0.0),
    "aspect_ratio": _spec("nullable_number", None, minimum=0.001),
    "anchor_x": _spec("enum", "left", values=("left", "center", "right")),
    "anchor_y": _spec("enum", "top", values=("top", "center", "bottom")),
    "margin": _spec("spacing", {"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0}),
    "padding": _spec("spacing", {"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0}),
    "z_index": _spec("integer", 0, minimum=-10000, maximum=10000),
    "visible": _spec("boolean", True),
    "opacity": _spec("number", 1.0, minimum=0.0, maximum=1.0),
    "overflow": _spec("enum", "visible", values=("visible", "clip")),
    "rotation": _spec("number", 0.0, minimum=-360.0, maximum=360.0),
    "scale_x": _spec("number", 1.0, minimum=0.05, maximum=10.0),
    "scale_y": _spec("number", 1.0, minimum=0.05, maximum=10.0),
    "transform_origin_x": _spec("number", 0.5, minimum=0.0, maximum=1.0),
    "transform_origin_y": _spec("number", 0.5, minimum=0.0, maximum=1.0),
    "background_color": _spec("nullable_color", None),
    "background_asset": _spec("nullable_asset", None),
    "background_gradient": _spec("color_list", []),
    "background_fit": _spec("enum", "cover", values=("cover", "contain", "stretch")),
    "background_focal_x": _spec("number", 0.5, minimum=0.0, maximum=1.0),
    "background_focal_y": _spec("number", 0.5, minimum=0.0, maximum=1.0),
    "border_color": _spec("nullable_color", None),
    "border_width": _spec("number", 0.0, minimum=0.0, maximum=200.0),
    "radius": _spec("number", 0.0, minimum=0.0, maximum=10000.0),
    "shadow_color": _spec("nullable_color", None),
    "shadow_blur": _spec("number", 0.0, minimum=0.0, maximum=300.0),
    "shadow_x": _spec("number", 0.0, minimum=-2000.0, maximum=2000.0),
    "shadow_y": _spec("number", 0.0, minimum=-2000.0, maximum=2000.0),
}

LAYOUT_PROPERTIES: dict[str, dict[str, Any]] = {
    "direction": _spec("enum", "column", values=("row", "column")),
    "gap": _spec("number", 0.0, minimum=0.0, maximum=10000.0),
    "align": _spec("enum", "start", values=("start", "center", "end", "stretch")),
    "justify": _spec(
        "enum", "start", values=("start", "center", "end", "space_between")
    ),
    "wrap": _spec("boolean", False),
}

TEXT_PROPERTIES: dict[str, dict[str, Any]] = {
    "text": _spec("string", "", maximum_length=10000),
    "color": _spec("color", "#000000"),
    "font_family": _spec("string", "Inter", maximum_length=100),
    "font_size": _spec("number", 32.0, minimum=2.0, maximum=1200.0),
    "min_font_size": _spec("number", 8.0, minimum=2.0, maximum=1200.0),
    "font_weight": _spec("integer", 400, minimum=100, maximum=900),
    "font_style": _spec("enum", "normal", values=("normal", "italic")),
    "line_height": _spec("number", 1.0, minimum=0.5, maximum=4.0),
    "letter_spacing": _spec("number", 0.0, minimum=-100.0, maximum=500.0),
    "text_align": _spec("enum", "left", values=("left", "center", "right")),
    "vertical_align": _spec("enum", "top", values=("top", "center", "bottom")),
    "max_lines": _spec("integer", 20, minimum=1, maximum=100),
    "wrap_text": _spec("enum", "word", values=("word", "none")),
    "text_fit": _spec("enum", "fixed", values=("fixed", "shrink", "truncate")),
    "casing": _spec("enum", "none", values=("none", "upper", "lower", "title")),
}

IMAGE_PROPERTIES: dict[str, dict[str, Any]] = {
    "asset": _spec("nullable_asset", None),
    "fit": _spec("enum", "cover", values=("cover", "contain", "stretch")),
    "focal_x": _spec("number", 0.5, minimum=0.0, maximum=1.0),
    "focal_y": _spec("number", 0.5, minimum=0.0, maximum=1.0),
    "mask": _spec("enum", "none", values=("none", "rounded_rect", "ellipse")),
    "alpha_outline_color": _spec("nullable_color", None),
    "alpha_outline_width": _spec("number", 0.0, minimum=0.0, maximum=100.0),
    "alpha_outline_width_ratio": _spec("number", 0.0, minimum=0.0, maximum=0.2),
    "alpha_outline_shadow_color": _spec("nullable_color", None),
    "alpha_outline_shadow_blur": _spec("number", 0.0, minimum=0.0, maximum=40.0),
    "alpha_outline_shadow_y": _spec("number", 0.0, minimum=-20.0, maximum=20.0),
}

TYPE_PROPERTIES: dict[str, dict[str, dict[str, Any]]] = {
    "frame": {
        **LAYOUT_PROPERTIES,
        "safe_area": _spec(
            "spacing", {"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0},
        ),
    },
    "container": LAYOUT_PROPERTIES,
    "stack": LAYOUT_PROPERTIES,
    "text": TEXT_PROPERTIES,
    "image": IMAGE_PROPERTIES,
    "button": {
        **TEXT_PROPERTIES,
        "label": _spec("string", "", maximum_length=1000),
        "label_color": _spec("color", "#FFFFFF"),
        "icon_asset": _spec("nullable_asset", None),
        "icon_gap": _spec("number", 8.0, minimum=0.0, maximum=1000.0),
    },
    "icon": {
        "asset": _spec("nullable_asset", None),
        "glyph": _spec("string", "", maximum_length=16),
        "fill": _spec("color", "#000000"),
        "stroke_width": _spec("number", 0.0, minimum=0.0, maximum=100.0),
    },
    "shape": {
        "shape": _spec("enum", "rectangle", values=("rectangle", "ellipse", "line")),
        "fill": _spec("color", "#000000"),
        "stroke_color": _spec("nullable_color", None),
        "stroke_width": _spec("number", 0.0, minimum=0.0, maximum=200.0),
        "line_direction": _spec("enum", "horizontal", values=("horizontal", "vertical", "diagonal")),
    },
    "spacer": {
        "flex": _spec("number", 0.0, minimum=0.0, maximum=1000.0),
        "divider_color": _spec("nullable_color", None),
        "thickness": _spec("number", 1.0, minimum=0.0, maximum=200.0),
        "orientation": _spec("enum", "horizontal", values=("horizontal", "vertical")),
    },
    "list": {
        **LAYOUT_PROPERTIES,
        "repeat": _spec("integer", 1, minimum=1, maximum=100),
        "columns": _spec("integer", 1, minimum=1, maximum=24),
    },
    "card": LAYOUT_PROPERTIES,
}


def _canonical(value: Any) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def _deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{label} must be finite")
    return normalized


def _spacing(value: Any, label: str) -> dict[str, float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = _finite_number(value, label)
        return {side: number for side in ("top", "right", "bottom", "left")}
    if not isinstance(value, Mapping) or set(value) != {"top", "right", "bottom", "left"}:
        raise ValueError(f"{label} must be a number or top/right/bottom/left object")
    return {side: _finite_number(value[side], f"{label}.{side}") for side in value}


def _normalize_property(name: str, value: Any, definition: Mapping[str, Any], label: str) -> Any:
    kind = definition["kind"]
    if kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{label} must be boolean")
        return value
    if kind == "integer":
        number = _finite_number(value, label)
        if int(number) != number:
            raise ValueError(f"{label} must be an integer")
        normalized: Any = int(number)
    elif kind == "number":
        normalized = _finite_number(value, label)
    elif kind == "nullable_number":
        if value is None:
            return None
        normalized = _finite_number(value, label)
    elif kind == "length":
        if isinstance(value, str):
            if value == "auto" and definition.get("allow_auto"):
                return value
            if re.fullmatch(r"-?(?:\d+(?:\.\d+)?|\.\d+)%", value):
                percent = float(value[:-1])
                if definition.get("positive") and percent <= 0:
                    raise ValueError(f"{label} must be positive")
                return f"{percent:g}%"
            raise ValueError(f"{label} must be a pixel number, percentage, or allowed auto")
        normalized = _finite_number(value, label)
        if definition.get("positive") and normalized <= 0:
            raise ValueError(f"{label} must be positive")
        return normalized
    elif kind in {"color", "nullable_color"}:
        if value is None and kind == "nullable_color":
            return None
        normalized = str(value).upper()
        if not _COLOR_PATTERN.fullmatch(normalized):
            raise ValueError(f"{label} must be a six- or eight-digit hex color")
        return normalized
    elif kind in {"nullable_asset"}:
        if value is None:
            return None
        normalized = str(value)
        if not _ID_PATTERN.fullmatch(normalized):
            raise ValueError(f"{label} must reference a declared asset key")
        return normalized
    elif kind == "string":
        if not isinstance(value, str) or len(value) > int(definition.get("maximum_length", 10000)):
            raise ValueError(f"{label} is not a bounded string")
        return value
    elif kind == "enum":
        if value not in definition["values"]:
            raise ValueError(f"{label} is outside its allowed values")
        return value
    elif kind == "spacing":
        return _spacing(value, label)
    elif kind == "color_list":
        if not isinstance(value, list) or len(value) > 4:
            raise ValueError(f"{label} must contain at most four colors")
        return [
            _normalize_property(name, item, {"kind": "color"}, f"{label}[{index}]")
            for index, item in enumerate(value)
        ]
    else:
        raise ValueError(f"unsupported Studio property kind: {kind}")
    minimum, maximum = definition.get("minimum"), definition.get("maximum")
    if minimum is not None and normalized < minimum:
        raise ValueError(f"{label} is below its minimum")
    if maximum is not None and normalized > maximum:
        raise ValueError(f"{label} is above its maximum")
    return normalized


def _property_schema(primitive_type: str) -> dict[str, dict[str, Any]]:
    return {**COMMON_PROPERTIES, **TYPE_PROPERTIES[primitive_type]}


def _normalize_props(primitive_type: str, value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    schema = _property_schema(primitive_type)
    unknown = sorted(set(value) - set(schema))
    if unknown:
        raise ValueError(f"{label} contains unsupported properties: {', '.join(unknown)}")
    normalized = {
        name: _normalize_property(name, value.get(name, copy.deepcopy(definition["default"])), definition, f"{label}.{name}")
        for name, definition in schema.items()
    }
    for minimum, maximum in (
        ("min_width", "max_width"), ("min_height", "max_height"),
    ):
        if (
            normalized[minimum] is not None and normalized[maximum] is not None
            and normalized[minimum] > normalized[maximum]
        ):
            raise ValueError(f"{label}.{minimum} cannot exceed {maximum}")
    return normalized


def _normalize_constraint(value: Any, *, node_id: str, properties: Mapping[str, Any]) -> dict[str, Any]:
    expected = {"path", "minimum", "maximum", "allowed", "locked"}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"{node_id} constraints must use path/minimum/maximum/allowed/locked")
    path = str(value["path"])
    if path not in properties:
        raise ValueError(f"{node_id} constraint targets an unsupported property")
    minimum = value["minimum"]
    maximum = value["maximum"]
    allowed = value["allowed"]
    if minimum is not None:
        minimum = _finite_number(minimum, f"{node_id}.{path}.minimum")
    if maximum is not None:
        maximum = _finite_number(maximum, f"{node_id}.{path}.maximum")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError(f"{node_id}.{path} constraint bounds are reversed")
    if not isinstance(allowed, list):
        raise ValueError(f"{node_id}.{path}.allowed must be a list")
    normalized = {
        "path": path, "minimum": minimum, "maximum": maximum,
        "allowed": _deep_copy(allowed), "locked": bool(value["locked"]),
    }
    current = properties[path]
    if allowed and current not in allowed:
        raise ValueError(f"{node_id}.{path} is outside its template constraint")
    if minimum is not None and (not isinstance(current, (int, float)) or current < minimum):
        raise ValueError(f"{node_id}.{path} is below its template constraint")
    if maximum is not None and (not isinstance(current, (int, float)) or current > maximum):
        raise ValueError(f"{node_id}.{path} is above its template constraint")
    return normalized


def _normalize_binding(value: Any, *, node_id: str, properties: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"target", "source", "required"}:
        raise ValueError(f"{node_id} bindings must use target/source/required")
    target, source = str(value["target"]), str(value["source"])
    if target not in properties:
        raise ValueError(f"{node_id} binding targets an unsupported property")
    if not _SOURCE_PATTERN.fullmatch(source):
        raise ValueError(f"{node_id} binding source is invalid")
    return {"target": target, "source": source, "required": bool(value["required"])}


def _normalize_responsive(
    value: Any, *, node_id: str, primitive_type: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{node_id}.responsive must be a list")
    schema = _property_schema(primitive_type)
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or set(item) != {"min_width", "max_width", "props"}:
            raise ValueError(f"{node_id}.responsive[{index}] fields are invalid")
        minimum = _finite_number(item["min_width"], f"{node_id}.responsive[{index}].min_width")
        maximum = _finite_number(item["max_width"], f"{node_id}.responsive[{index}].max_width")
        if minimum < 1 or minimum > maximum:
            raise ValueError(f"{node_id}.responsive[{index}] range is invalid")
        props = item["props"]
        if not isinstance(props, Mapping) or not props:
            raise ValueError(f"{node_id}.responsive[{index}].props must not be empty")
        unknown = sorted(set(props) - set(schema))
        if unknown:
            raise ValueError(f"{node_id}.responsive[{index}] has unsupported properties")
        normalized.append({
            "min_width": minimum, "max_width": maximum,
            "props": {
                name: _normalize_property(name, raw, schema[name], f"{node_id}.responsive.{name}")
                for name, raw in props.items()
            },
        })
    ranges = [(item["min_width"], item["max_width"]) for item in normalized]
    if ranges != sorted(ranges):
        raise ValueError(f"{node_id}.responsive ranges must be sorted")
    if any(right[0] <= left[1] for left, right in zip(ranges, ranges[1:])):
        raise ValueError(f"{node_id}.responsive ranges must not overlap")
    return normalized


def _normalize_node(value: Any, *, seen_ids: set[str], label: str) -> dict[str, Any]:
    allowed = {"id", "type", "props", "bindings", "constraints", "responsive", "children"}
    if not isinstance(value, Mapping) or not {"id", "type"} <= set(value) or not set(value) <= allowed:
        raise ValueError(f"{label} fields are invalid")
    node_id, primitive_type = str(value["id"]), str(value["type"])
    if not _ID_PATTERN.fullmatch(node_id) or node_id in seen_ids:
        raise ValueError(f"{label}.id must be stable and unique")
    if primitive_type not in PRIMITIVE_TYPES:
        raise ValueError(f"{label}.type is not in the finite Studio primitive catalog")
    seen_ids.add(node_id)
    props = _normalize_props(primitive_type, value.get("props") or {}, f"{label}.props")
    raw_bindings = value.get("bindings") or []
    if not isinstance(raw_bindings, list):
        raise ValueError(f"{label}.bindings must be a list")
    bindings = [
        _normalize_binding(item, node_id=node_id, properties=props) for item in raw_bindings
    ]
    if len({item["target"] for item in bindings}) != len(bindings):
        raise ValueError(f"{node_id} binding targets must be unique")
    raw_constraints = value.get("constraints") or []
    if not isinstance(raw_constraints, list):
        raise ValueError(f"{label}.constraints must be a list")
    constraints = [
        _normalize_constraint(item, node_id=node_id, properties=props)
        for item in raw_constraints
    ]
    if len({item["path"] for item in constraints}) != len(constraints):
        raise ValueError(f"{node_id} constraint paths must be unique")
    responsive = _normalize_responsive(
        value.get("responsive") or [], node_id=node_id, primitive_type=primitive_type,
    )
    raw_children = value.get("children") or []
    if not isinstance(raw_children, list):
        raise ValueError(f"{label}.children must be a list")
    if raw_children and primitive_type not in CONTAINER_TYPES:
        raise ValueError(f"{node_id} primitive cannot contain children")
    children = [
        _normalize_node(item, seen_ids=seen_ids, label=f"{label}.children[{index}]")
        for index, item in enumerate(raw_children)
    ]
    if primitive_type == "list" and len(children) != 1:
        raise ValueError(f"{node_id} list requires exactly one reusable item subtree")
    return {
        "id": node_id, "type": primitive_type, "props": props,
        "bindings": bindings, "constraints": constraints,
        "responsive": responsive, "children": children,
    }


def _node_ids(root: Mapping[str, Any]) -> set[str]:
    found = {str(root["id"])}
    for child in root.get("children") or []:
        found.update(_node_ids(child))
    return found


def _normalize_assets(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise ValueError("Studio template assets must be an object")
    normalized: dict[str, dict[str, Any]] = {}
    for key, item in sorted(value.items()):
        if not _ID_PATTERN.fullmatch(str(key)):
            raise ValueError("Studio template asset keys must be stable IDs")
        expected = {"kind", "allowed_mime_types", "required", "provenance"}
        if not isinstance(item, Mapping) or set(item) != expected or item["kind"] != "image":
            raise ValueError(f"Studio asset declaration {key} is invalid")
        mime_types = [str(one) for one in item["allowed_mime_types"]]
        if not mime_types or len(mime_types) != len(set(mime_types)) or not set(mime_types) <= _MIME_TYPES:
            raise ValueError(f"Studio asset declaration {key} has invalid MIME types")
        provenance = " ".join(str(item["provenance"]).split())
        if not 1 <= len(provenance) <= 500:
            raise ValueError(f"Studio asset declaration {key} requires bounded provenance")
        normalized[str(key)] = {
            "kind": "image", "allowed_mime_types": sorted(mime_types),
            "required": bool(item["required"]), "provenance": provenance,
        }
    return normalized


def _normalize_rules(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Studio template rules must be a list")
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"id", "scope", "type", "params"}:
            raise ValueError("Studio template rule fields are invalid")
        rule_id, scope, kind = str(item["id"]), str(item["scope"]), str(item["type"])
        if not _ID_PATTERN.fullmatch(rule_id) or rule_id in ids or scope not in SCOPE_VALUES:
            raise ValueError("Studio template rule identity or scope is invalid")
        if kind not in {"required_role", "max_nodes", "note"} or not isinstance(item["params"], Mapping):
            raise ValueError("Studio template rule type or params are invalid")
        ids.add(rule_id)
        normalized.append({
            "id": rule_id, "scope": scope, "type": kind, "params": _deep_copy(item["params"]),
        })
    return normalized


def primitive_catalog() -> dict[str, Any]:
    """Return the finite, agent-inspectable v1 primitive/property vocabulary."""
    items = []
    for primitive_type in PRIMITIVE_TYPES:
        schema = _property_schema(primitive_type)
        items.append({
            "type": primitive_type,
            "allows_children": primitive_type in CONTAINER_TYPES,
            "properties": {
                name: {
                    key: _deep_copy(value)
                    for key, value in definition.items() if key != "default"
                } | {"default": _deep_copy(definition["default"])}
                for name, definition in schema.items()
            },
        })
    catalog = {
        "schema": "ptw.studio.primitive-catalog.v1",
        "version": PRIMITIVE_CATALOG_VERSION,
        "primitive_types": list(PRIMITIVE_TYPES),
        "items": items,
    }
    _, digest = _canonical(catalog)
    return {**catalog, "sha256": digest}


@dataclass(frozen=True, slots=True)
class PrimitiveTemplate:
    document: Mapping[str, Any]
    digest: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PrimitiveTemplate":
        expected = {
            "schema", "template_id", "template_type", "version", "status", "root",
            "semantic_roles", "assets", "rules", "provenance",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError("primitive template fields do not match the v1 contract")
        if value["schema"] != PRIMITIVE_TEMPLATE_SCHEMA:
            raise ValueError("primitive template schema is invalid")
        template_id, template_type = str(value["template_id"]), str(value["template_type"])
        if not _ID_PATTERN.fullmatch(template_id) or not _ID_PATTERN.fullmatch(template_type):
            raise ValueError("primitive template identity is invalid")
        version = int(value["version"])
        if version < 1 or str(value["status"]) not in STATUS_VALUES:
            raise ValueError("primitive template version or status is invalid")
        seen_ids: set[str] = set()
        root = _normalize_node(value["root"], seen_ids=seen_ids, label="root")
        if root["type"] != "frame":
            raise ValueError("primitive template root must be a frame")
        if not isinstance(root["props"]["width"], (int, float)) or not isinstance(
            root["props"]["height"], (int, float)
        ):
            raise ValueError("primitive template root requires fixed pixel width and height")
        root["props"]["position"] = "absolute"
        root["props"]["x"], root["props"]["y"] = 0.0, 0.0
        root["props"]["overflow"] = "clip"
        assets = _normalize_assets(value["assets"])
        used_assets: set[str] = set()
        for node in _iter_nodes(root):
            for name in ("asset", "background_asset", "icon_asset"):
                asset = node["props"].get(name)
                if asset is not None:
                    used_assets.add(str(asset))
        undeclared = sorted(used_assets - set(assets))
        if undeclared:
            raise ValueError(f"primitive template uses undeclared assets: {', '.join(undeclared)}")
        semantic_roles = value["semantic_roles"]
        if not isinstance(semantic_roles, Mapping):
            raise ValueError("primitive template semantic_roles must be an object")
        normalized_roles: dict[str, list[str]] = {}
        for role, raw_ids in sorted(semantic_roles.items()):
            role = str(role)
            if role not in SEMANTIC_ROLE_NAMES and not _ID_PATTERN.fullmatch(role):
                raise ValueError("primitive template semantic role is invalid")
            if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) != len(set(raw_ids)):
                raise ValueError(f"semantic role {role} requires unique node IDs")
            ids = [str(item) for item in raw_ids]
            if not set(ids) <= seen_ids:
                raise ValueError(f"semantic role {role} references an unknown node")
            normalized_roles[role] = ids
        rules = _normalize_rules(value["rules"])
        for rule in rules:
            if rule["type"] == "required_role":
                role = str(rule["params"].get("role") or "")
                if role not in normalized_roles:
                    raise ValueError(f"required semantic role is not mapped: {role}")
            elif rule["type"] == "max_nodes":
                maximum = int(rule["params"].get("maximum") or 0)
                if maximum < 1 or len(seen_ids) > maximum:
                    raise ValueError("primitive template exceeds its max_nodes rule")
        provenance = value["provenance"]
        provenance_fields = {
            "base_template_id", "base_version", "base_sha256", "reference_ids", "change_note",
        }
        if not isinstance(provenance, Mapping) or set(provenance) != provenance_fields:
            raise ValueError("primitive template provenance fields are invalid")
        if not isinstance(provenance["reference_ids"], list):
            raise ValueError("primitive template reference IDs must be a list")
        reference_ids = [str(item) for item in provenance["reference_ids"]]
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("primitive template reference IDs must be unique")
        base_id = provenance["base_template_id"]
        base_version = provenance["base_version"]
        base_sha256 = provenance["base_sha256"]
        if (base_id is None) != (base_version is None) or (base_id is None) != (base_sha256 is None):
            raise ValueError("primitive template base provenance must be supplied together")
        if base_id is not None:
            if not _ID_PATTERN.fullmatch(str(base_id)) or int(base_version) < 1:
                raise ValueError("primitive template base identity is invalid")
            if not re.fullmatch(r"[0-9a-f]{64}", str(base_sha256)):
                raise ValueError("primitive template base digest is invalid")
        change_note = " ".join(str(provenance["change_note"]).split())
        if len(change_note) > 500:
            raise ValueError("primitive template change note is too long")
        document = {
            "schema": PRIMITIVE_TEMPLATE_SCHEMA,
            "template_id": template_id,
            "template_type": template_type,
            "version": version,
            "status": str(value["status"]),
            "root": root,
            "semantic_roles": normalized_roles,
            "assets": assets,
            "rules": rules,
            "provenance": {
                "base_template_id": None if base_id is None else str(base_id),
                "base_version": None if base_version is None else int(base_version),
                "base_sha256": None if base_sha256 is None else str(base_sha256),
                "reference_ids": reference_ids,
                "change_note": change_note,
            },
        }
        raw, digest = _canonical(document)
        return cls(json.loads(raw), digest)

    @classmethod
    def from_json(cls, raw: str) -> "PrimitiveTemplate":
        value = json.loads(raw)
        if not isinstance(value, Mapping):
            raise ValueError("primitive template JSON must contain one object")
        return cls.from_dict(value)

    def to_json(self, *, pretty: bool = True) -> str:
        if pretty:
            return json.dumps(self.document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        return _canonical(self.document)[0]


def load_primitive_template(path: Path | str) -> PrimitiveTemplate:
    try:
        return PrimitiveTemplate.from_json(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"primitive template is unavailable or invalid: {path}") from error


def _iter_nodes(root: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    yield root
    for child in root.get("children") or []:
        yield from _iter_nodes(child)


def _find_node(root: MutableMapping[str, Any], node_id: str) -> MutableMapping[str, Any] | None:
    if root["id"] == node_id:
        return root
    for child in root.get("children") or []:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def _find_parent(
    root: MutableMapping[str, Any], node_id: str,
) -> tuple[MutableMapping[str, Any], int] | None:
    for index, child in enumerate(root.get("children") or []):
        if child["id"] == node_id:
            return root, index
        found = _find_parent(child, node_id)
        if found is not None:
            return found
    return None


class PrimitiveTemplateEditor:
    """Apply bounded operations without mutating the supplied template version."""

    def __init__(self, template: PrimitiveTemplate) -> None:
        self.base = template
        self._document = _deep_copy(template.document)
        if template.document["status"] == "approved":
            self._document["version"] = int(template.document["version"]) + 1
            self._document["status"] = "draft"
            self._document["provenance"] = {
                "base_template_id": template.document["template_id"],
                "base_version": template.document["version"],
                "base_sha256": template.digest,
                "reference_ids": list(template.document["provenance"]["reference_ids"]),
                "change_note": "",
            }

    def _node(self, node_id: str) -> MutableMapping[str, Any]:
        node = _find_node(self._document["root"], node_id)
        if node is None:
            raise ValueError(f"unknown Studio primitive node: {node_id}")
        return node

    def _assert_editable(self, node: Mapping[str, Any], path: str) -> None:
        constraint = next((item for item in node["constraints"] if item["path"] == path), None)
        if constraint is not None and constraint["locked"]:
            raise ValueError(f"{node['id']}.{path} is locked by the template")

    def add_node(self, parent_id: str, node: Mapping[str, Any], index: int | None = None) -> "PrimitiveTemplateEditor":
        parent = self._node(parent_id)
        if parent["type"] not in CONTAINER_TYPES:
            raise ValueError("Studio nodes can be added only to container primitives")
        candidate = _normalize_node(node, seen_ids=set(), label="new_node")
        existing = _node_ids(self._document["root"])
        overlap = existing & _node_ids(candidate)
        if overlap:
            raise ValueError(f"Studio node IDs already exist: {', '.join(sorted(overlap))}")
        chosen = len(parent["children"]) if index is None else int(index)
        if not 0 <= chosen <= len(parent["children"]):
            raise ValueError("Studio add index is out of range")
        parent["children"].insert(chosen, candidate)
        return self

    def remove_node(self, node_id: str) -> "PrimitiveTemplateEditor":
        if node_id == self._document["root"]["id"]:
            raise ValueError("Studio root frame cannot be removed")
        found = _find_parent(self._document["root"], node_id)
        if found is None:
            raise ValueError(f"unknown Studio primitive node: {node_id}")
        _parent, index = found
        removed_ids = _node_ids(_parent["children"][index])
        _parent["children"].pop(index)
        for role in list(self._document["semantic_roles"]):
            retained = [item for item in self._document["semantic_roles"][role] if item not in removed_ids]
            if retained:
                self._document["semantic_roles"][role] = retained
            else:
                del self._document["semantic_roles"][role]
        return self

    def move_node(self, node_id: str, parent_id: str, index: int | None = None) -> "PrimitiveTemplateEditor":
        if node_id == self._document["root"]["id"]:
            raise ValueError("Studio root frame cannot be moved")
        node = self._node(node_id)
        if parent_id in _node_ids(node):
            raise ValueError("Studio node cannot be moved into its own subtree")
        source = _find_parent(self._document["root"], node_id)
        if source is None:
            raise ValueError(f"unknown Studio primitive node: {node_id}")
        source_parent, source_index = source
        detached = source_parent["children"].pop(source_index)
        try:
            self.add_node(parent_id, detached, index)
        except Exception:
            source_parent["children"].insert(source_index, detached)
            raise
        return self

    def reorder_node(self, node_id: str, index: int) -> "PrimitiveTemplateEditor":
        found = _find_parent(self._document["root"], node_id)
        if found is None:
            raise ValueError("Studio root cannot be reordered")
        parent, old_index = found
        chosen = int(index)
        if not 0 <= chosen < len(parent["children"]):
            raise ValueError("Studio reorder index is out of range")
        parent["children"].insert(chosen, parent["children"].pop(old_index))
        return self

    def set_property(self, node_id: str, path: str, value: Any) -> "PrimitiveTemplateEditor":
        node = self._node(node_id)
        schema = _property_schema(str(node["type"]))
        if path not in schema:
            raise ValueError(f"{node_id}.{path} is not a supported property")
        self._assert_editable(node, path)
        normalized = _normalize_property(path, value, schema[path], f"{node_id}.{path}")
        constraint = next((item for item in node["constraints"] if item["path"] == path), None)
        if constraint is not None:
            if constraint["allowed"] and normalized not in constraint["allowed"]:
                raise ValueError(f"{node_id}.{path} is outside its allowed values")
            if constraint["minimum"] is not None and normalized < constraint["minimum"]:
                raise ValueError(f"{node_id}.{path} is below its declared constraint")
            if constraint["maximum"] is not None and normalized > constraint["maximum"]:
                raise ValueError(f"{node_id}.{path} is above its declared constraint")
        node["props"][path] = normalized
        return self

    def reset_property(self, node_id: str, path: str) -> "PrimitiveTemplateEditor":
        node = self._node(node_id)
        schema = _property_schema(str(node["type"]))
        if path not in schema:
            raise ValueError(f"{node_id}.{path} is not a supported property")
        return self.set_property(node_id, path, copy.deepcopy(schema[path]["default"]))

    def bind_property(
        self, node_id: str, target: str, source: str, *, required: bool = True,
    ) -> "PrimitiveTemplateEditor":
        node = self._node(node_id)
        self._assert_editable(node, target)
        binding = _normalize_binding(
            {"target": target, "source": source, "required": required},
            node_id=node_id, properties=node["props"],
        )
        node["bindings"] = [item for item in node["bindings"] if item["target"] != target]
        node["bindings"].append(binding)
        return self

    def unbind_property(self, node_id: str, target: str) -> "PrimitiveTemplateEditor":
        node = self._node(node_id)
        self._assert_editable(node, target)
        node["bindings"] = [item for item in node["bindings"] if item["target"] != target]
        return self

    def bind_role(self, role: str, node_id: str) -> "PrimitiveTemplateEditor":
        self._node(node_id)
        if role not in SEMANTIC_ROLE_NAMES and not _ID_PATTERN.fullmatch(role):
            raise ValueError("Studio semantic role is invalid")
        ids = self._document["semantic_roles"].setdefault(role, [])
        if node_id not in ids:
            ids.append(node_id)
        return self

    def unbind_role(self, role: str, node_id: str | None = None) -> "PrimitiveTemplateEditor":
        if role not in self._document["semantic_roles"]:
            return self
        if node_id is None:
            del self._document["semantic_roles"][role]
        else:
            self._document["semantic_roles"][role] = [
                item for item in self._document["semantic_roles"][role] if item != node_id
            ]
            if not self._document["semantic_roles"][role]:
                del self._document["semantic_roles"][role]
        return self

    def set_constraint(
        self, node_id: str, path: str, *, minimum: float | None = None,
        maximum: float | None = None, allowed: Sequence[Any] = (), locked: bool = False,
    ) -> "PrimitiveTemplateEditor":
        node = self._node(node_id)
        candidate = _normalize_constraint({
            "path": path, "minimum": minimum, "maximum": maximum,
            "allowed": list(allowed), "locked": locked,
        }, node_id=node_id, properties=node["props"])
        node["constraints"] = [item for item in node["constraints"] if item["path"] != path]
        node["constraints"].append(candidate)
        return self

    def set_responsive_override(
        self, node_id: str, *, min_width: float, max_width: float,
        props: Mapping[str, Any],
    ) -> "PrimitiveTemplateEditor":
        node = self._node(node_id)
        candidate = _normalize_responsive([{
            "min_width": min_width, "max_width": max_width, "props": props,
        }], node_id=node_id, primitive_type=node["type"])[0]
        node["responsive"] = [
            item for item in node["responsive"]
            if (item["min_width"], item["max_width"])
            != (candidate["min_width"], candidate["max_width"])
        ]
        node["responsive"].append(candidate)
        node["responsive"].sort(key=lambda item: (item["min_width"], item["max_width"]))
        return self

    def replace_asset(self, key: str, declaration: Mapping[str, Any]) -> "PrimitiveTemplateEditor":
        normalized = _normalize_assets({key: declaration})
        self._document["assets"][key] = normalized[key]
        return self

    def wrap_nodes(
        self, node_ids: Sequence[str], wrapper: Mapping[str, Any],
    ) -> "PrimitiveTemplateEditor":
        if not node_ids or len(node_ids) != len(set(node_ids)):
            raise ValueError("Studio wrap requires distinct sibling nodes")
        locations = [_find_parent(self._document["root"], node_id) for node_id in node_ids]
        if any(item is None for item in locations):
            raise ValueError("Studio wrap references an unknown or root node")
        parents = [item[0] for item in locations if item is not None]
        if any(parent is not parents[0] for parent in parents):
            raise ValueError("Studio wrap requires nodes with the same parent")
        parent = parents[0]
        indexes = sorted(item[1] for item in locations if item is not None)
        selected = [parent["children"][index] for index in indexes]
        normalized = _normalize_node(wrapper, seen_ids=set(), label="wrapper")
        if normalized["type"] not in CONTAINER_TYPES or normalized["children"]:
            raise ValueError("Studio wrapper must be an empty container primitive")
        if _node_ids(normalized) & _node_ids(self._document["root"]):
            raise ValueError("Studio wrapper ID already exists")
        for index in reversed(indexes):
            parent["children"].pop(index)
        normalized["children"] = selected
        parent["children"].insert(indexes[0], normalized)
        return self

    def unwrap_node(self, node_id: str) -> "PrimitiveTemplateEditor":
        found = _find_parent(self._document["root"], node_id)
        if found is None:
            raise ValueError("Studio root cannot be unwrapped")
        parent, index = found
        wrapper = parent["children"][index]
        if wrapper["type"] not in CONTAINER_TYPES:
            raise ValueError("only a Studio container primitive can be unwrapped")
        parent["children"][index:index + 1] = wrapper["children"]
        return self

    def duplicate_subtree(
        self, node_id: str, new_root_id: str, *, parent_id: str | None = None,
        index: int | None = None,
    ) -> "PrimitiveTemplateEditor":
        original = _deep_copy(self._node(node_id))
        if not _ID_PATTERN.fullmatch(new_root_id):
            raise ValueError("Studio duplicate root ID is invalid")
        existing = _node_ids(self._document["root"])
        replacements: dict[str, str] = {}
        for ordinal, node in enumerate(_iter_nodes(original)):
            replacement = new_root_id if ordinal == 0 else f"{new_root_id}-{ordinal}"
            if replacement in existing:
                raise ValueError("Studio duplicate would reuse an existing node ID")
            replacements[str(node["id"])] = replacement
            node["id"] = replacement
        found = _find_parent(self._document["root"], node_id)
        target_parent = parent_id or (found[0]["id"] if found is not None else None)
        if target_parent is None:
            raise ValueError("Studio root duplicate requires an explicit parent")
        self.add_node(target_parent, original, index)
        for role, ids in list(self._document["semantic_roles"].items()):
            for old, new in replacements.items():
                if old in ids and new not in ids:
                    ids.append(new)
        return self

    def apply_operations(self, operations: Sequence[Mapping[str, Any]]) -> "PrimitiveTemplateEditor":
        dispatch = {
            "add": lambda item: self.add_node(item["parent_id"], item["node"], item.get("index")),
            "remove": lambda item: self.remove_node(item["node_id"]),
            "move": lambda item: self.move_node(item["node_id"], item["parent_id"], item.get("index")),
            "reorder": lambda item: self.reorder_node(item["node_id"], item["index"]),
            "set_property": lambda item: self.set_property(item["node_id"], item["path"], item["value"]),
            "reset_property": lambda item: self.reset_property(item["node_id"], item["path"]),
            "bind_property": lambda item: self.bind_property(
                item["node_id"], item["target"], item["source"], required=item.get("required", True),
            ),
            "unbind_property": lambda item: self.unbind_property(item["node_id"], item["target"]),
            "bind_role": lambda item: self.bind_role(item["role"], item["node_id"]),
            "unbind_role": lambda item: self.unbind_role(item["role"], item.get("node_id")),
            "wrap": lambda item: self.wrap_nodes(item["node_ids"], item["wrapper"]),
            "unwrap": lambda item: self.unwrap_node(item["node_id"]),
            "duplicate": lambda item: self.duplicate_subtree(
                item["node_id"], item["new_root_id"],
                parent_id=item.get("parent_id"), index=item.get("index"),
            ),
            "replace_asset": lambda item: self.replace_asset(item["key"], item["declaration"]),
            "responsive": lambda item: self.set_responsive_override(
                item["node_id"], min_width=item["min_width"],
                max_width=item["max_width"], props=item["props"],
            ),
            "constraint": lambda item: self.set_constraint(
                item["node_id"], item["path"], minimum=item.get("minimum"),
                maximum=item.get("maximum"), allowed=item.get("allowed", ()),
                locked=item.get("locked", False),
            ),
        }
        for ordinal, item in enumerate(operations):
            if not isinstance(item, Mapping) or str(item.get("op")) not in dispatch:
                raise ValueError(f"unknown internal Studio operation at index {ordinal}")
            dispatch[str(item["op"])](item)
        return self

    def document(self, *, change_note: str | None = None) -> PrimitiveTemplate:
        if change_note is not None:
            self._document["provenance"]["change_note"] = change_note
        return PrimitiveTemplate.from_dict(self._document)

    def approve(self, *, change_note: str) -> PrimitiveTemplate:
        self._document["status"] = "approved"
        self._document["provenance"]["change_note"] = change_note
        return PrimitiveTemplate.from_dict(self._document)

    def save_version(self, path: Path | str, *, change_note: str | None = None) -> PrimitiveTemplate:
        template = self.document(change_note=change_note)
        destination = Path(path)
        if destination.exists():
            existing = load_primitive_template(destination)
            if existing.digest != template.digest:
                raise FileExistsError(f"Studio version already exists with different content: {destination}")
            return existing
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(template.to_json())
        return template

    def propose_promotion(
        self, *, scope: str, summary: str, affected_paths: Sequence[str],
    ) -> dict[str, Any]:
        if scope not in SCOPE_VALUES - {"instance"}:
            raise ValueError("Studio promotion scope must be template, template_type, or platform")
        proposal = {
            "schema": "ptw.studio.promotion-proposal.v1",
            "scope": scope,
            "base_template": {
                "template_id": self.base.document["template_id"],
                "version": self.base.document["version"],
                "sha256": self.base.digest,
            },
            "summary": " ".join(summary.split()),
            "affected_paths": sorted(set(str(item) for item in affected_paths)),
            "status": "proposed",
        }
        _, digest = _canonical(proposal)
        return {**proposal, "sha256": digest}


def apply_primitive_operations(
    template: PrimitiveTemplate | Mapping[str, Any], operations: Sequence[Mapping[str, Any]],
    *, change_note: str = "",
) -> PrimitiveTemplate:
    base = template if isinstance(template, PrimitiveTemplate) else PrimitiveTemplate.from_dict(template)
    return PrimitiveTemplateEditor(base).apply_operations(operations).document(change_note=change_note)


@dataclass(frozen=True, slots=True)
class _Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True, slots=True)
class _Command:
    node: Mapping[str, Any]
    props: Mapping[str, Any]
    box: _Box
    clips: tuple[_Box, ...]
    opacity: float
    z_path: tuple[int, ...]


def _length(value: Any, total: float, auto: float) -> float:
    if value == "auto":
        return auto
    if isinstance(value, str) and value.endswith("%"):
        return total * float(value[:-1]) / 100
    return float(value)


def _resolved_props(node: Mapping[str, Any], target_width: int, semantic_data: Mapping[str, Any]) -> dict[str, Any]:
    props = _deep_copy(node["props"])
    for override in node["responsive"]:
        if override["min_width"] <= target_width <= override["max_width"]:
            props.update(_deep_copy(override["props"]))
    for binding in node["bindings"]:
        source = binding["source"]
        if source not in semantic_data:
            if binding["required"]:
                raise ValueError(f"Studio preview is missing semantic binding: {source}")
            continue
        schema = _property_schema(node["type"])
        props[binding["target"]] = _normalize_property(
            binding["target"], semantic_data[source], schema[binding["target"]],
            f"{node['id']}.{binding['target']}",
        )
    return props


def _resolve_box(props: Mapping[str, Any], parent: _Box, forced: _Box | None = None) -> _Box:
    if forced is not None:
        width, height, x, y = forced.width, forced.height, forced.x, forced.y
    else:
        width = _length(props["width"], parent.width, parent.width)
        height = _length(props["height"], parent.height, parent.height)
        if props["aspect_ratio"] is not None:
            if props["width"] == "auto" and props["height"] != "auto":
                width = height * float(props["aspect_ratio"])
            else:
                height = width / float(props["aspect_ratio"])
        x_offset = _length(props["x"], parent.width, 0)
        y_offset = _length(props["y"], parent.height, 0)
        if props["anchor_x"] == "center":
            x = parent.x + parent.width / 2 + x_offset - width / 2
        elif props["anchor_x"] == "right":
            x = parent.right - x_offset - width
        else:
            x = parent.x + x_offset
        if props["anchor_y"] == "center":
            y = parent.y + parent.height / 2 + y_offset - height / 2
        elif props["anchor_y"] == "bottom":
            y = parent.bottom - y_offset - height
        else:
            y = parent.y + y_offset
    if props["min_width"] is not None:
        width = max(width, float(props["min_width"]))
    if props["max_width"] is not None:
        width = min(width, float(props["max_width"]))
    if props["min_height"] is not None:
        height = max(height, float(props["min_height"]))
    if props["max_height"] is not None:
        height = min(height, float(props["max_height"]))
    return _Box(x, y, max(0.01, width), max(0.01, height))


def _content_box(box: _Box, props: Mapping[str, Any]) -> _Box:
    padding = props["padding"]
    safe_area = props.get("safe_area") or {side: 0.0 for side in padding}
    return _Box(
        box.x + padding["left"] + safe_area["left"],
        box.y + padding["top"] + safe_area["top"],
        max(
            0.01,
            box.width - padding["left"] - padding["right"]
            - safe_area["left"] - safe_area["right"],
        ),
        max(
            0.01,
            box.height - padding["top"] - padding["bottom"]
            - safe_area["top"] - safe_area["bottom"],
        ),
    )


def _expanded_children(node: Mapping[str, Any], props: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    children = list(node["children"])
    if node["type"] != "list":
        return children
    item = children[0]
    expanded = []
    for index in range(int(props["repeat"])):
        clone = _deep_copy(item)
        for descendant in _iter_nodes(clone):
            descendant["id"] = f"{descendant['id']}--{index + 1}"
        expanded.append(clone)
    return expanded


def _flow_layout(
    children: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]], box: _Box,
    parent_props: Mapping[str, Any],
) -> list[tuple[Mapping[str, Any], Mapping[str, Any], _Box]]:
    if not children:
        return []
    direction = parent_props.get("direction", "column")
    gap = float(parent_props.get("gap", 0))
    primary_total = box.width if direction == "row" else box.height
    cross_total = box.height if direction == "row" else box.width
    wrapping = bool(parent_props.get("wrap", False))
    columns = (
        int(parent_props["columns"])
        if direction == "row" and "columns" in parent_props
        else max(1, len(children))
    )
    explicit = 0.0
    auto_count = 0
    sizes: list[tuple[float | None, float | None]] = []
    for _node, props in children:
        main_value = props["width"] if direction == "row" else props["height"]
        cross_value = props["height"] if direction == "row" else props["width"]
        main = None if main_value == "auto" else _length(main_value, primary_total, primary_total)
        cross = None if cross_value == "auto" else _length(cross_value, cross_total, cross_total)
        if main is None:
            auto_count += 1
        else:
            explicit += main
        sizes.append((main, cross))
    available = max(0.01, primary_total - explicit - gap * max(0, len(children) - 1))
    if wrapping:
        auto_size = max(0.01, (primary_total - gap * (columns - 1)) / columns)
    else:
        auto_size = available / max(1, auto_count)
    resolved_main = [auto_size if main is None else main for main, _cross in sizes]
    if wrapping:
        lines: list[list[int]] = []
        line: list[int] = []
        consumed = 0.0
        for index, main in enumerate(resolved_main):
            next_size = main if not line else consumed + gap + main
            if line and (next_size > primary_total + 0.001 or len(line) >= columns):
                lines.append(line)
                line, consumed = [], 0.0
            line.append(index)
            consumed = main if len(line) == 1 else consumed + gap + main
        if line:
            lines.append(line)
        default_cross = max(0.01, (cross_total - gap * max(0, len(lines) - 1)) / len(lines))
        output: list[tuple[Mapping[str, Any], Mapping[str, Any], _Box]] = []
        cross_cursor = 0.0
        for line_indexes in lines:
            line_cross = max(
                (default_cross if sizes[index][1] is None else float(sizes[index][1]))
                for index in line_indexes
            )
            line_used = sum(resolved_main[index] for index in line_indexes) + gap * max(0, len(line_indexes) - 1)
            justify = parent_props.get("justify", "start")
            if justify == "center":
                cursor = max(0.0, (primary_total - line_used) / 2)
            elif justify == "end":
                cursor = max(0.0, primary_total - line_used)
            else:
                cursor = 0.0
            actual_gap = gap
            if justify == "space_between" and len(line_indexes) > 1:
                actual_gap = max(
                    gap,
                    (primary_total - sum(resolved_main[index] for index in line_indexes))
                    / (len(line_indexes) - 1),
                )
            for index in line_indexes:
                node, props = children[index]
                main = resolved_main[index]
                cross = default_cross if sizes[index][1] is None else float(sizes[index][1])
                align = parent_props.get("align", "start")
                cross_size = line_cross if align == "stretch" else cross
                if align == "center":
                    cross_offset = (line_cross - cross_size) / 2
                elif align == "end":
                    cross_offset = line_cross - cross_size
                else:
                    cross_offset = 0.0
                margin = props["margin"]
                if direction == "row":
                    forced = _Box(
                        box.x + cursor + margin["left"],
                        box.y + cross_cursor + cross_offset + margin["top"],
                        max(0.01, main - margin["left"] - margin["right"]),
                        max(0.01, cross_size - margin["top"] - margin["bottom"]),
                    )
                else:
                    forced = _Box(
                        box.x + cross_cursor + cross_offset + margin["left"],
                        box.y + cursor + margin["top"],
                        max(0.01, cross_size - margin["left"] - margin["right"]),
                        max(0.01, main - margin["top"] - margin["bottom"]),
                    )
                output.append((node, props, forced))
                cursor += main + actual_gap
            cross_cursor += line_cross + gap
        return output
    used = sum(resolved_main) + gap * max(0, len(children) - 1)
    justify = parent_props.get("justify", "start")
    if justify == "center":
        cursor = max(0.0, (primary_total - used) / 2)
    elif justify == "end":
        cursor = max(0.0, primary_total - used)
    else:
        cursor = 0.0
    actual_gap = gap
    if justify == "space_between" and len(children) > 1:
        actual_gap = max(gap, (primary_total - sum(resolved_main)) / (len(children) - 1))
    output: list[tuple[Mapping[str, Any], Mapping[str, Any], _Box]] = []
    for (node, props), main, (_raw_main, cross) in zip(children, resolved_main, sizes):
        cross_size = cross_total if cross is None or parent_props.get("align") == "stretch" else cross
        align = parent_props.get("align", "start")
        if align == "center":
            cross_offset = (cross_total - cross_size) / 2
        elif align == "end":
            cross_offset = cross_total - cross_size
        else:
            cross_offset = 0.0
        margin = props["margin"]
        if direction == "row":
            forced = _Box(
                box.x + cursor + margin["left"], box.y + cross_offset + margin["top"],
                max(0.01, main - margin["left"] - margin["right"]),
                max(0.01, cross_size - margin["top"] - margin["bottom"]),
            )
        else:
            forced = _Box(
                box.x + cross_offset + margin["left"], box.y + cursor + margin["top"],
                max(0.01, cross_size - margin["left"] - margin["right"]),
                max(0.01, main - margin["top"] - margin["bottom"]),
            )
        output.append((node, props, forced))
        cursor += main + actual_gap
    return output


class PrimitivePreviewRenderer:
    """Deterministically render one normalized primitive template to PNG."""

    def __init__(self, font_resolver: Callable[[int, str, int | None], Any]) -> None:
        self.font_resolver = font_resolver

    def _commands(
        self, template: PrimitiveTemplate, semantic_data: Mapping[str, Any], width: int, height: int,
    ) -> list[_Command]:
        root_box = _Box(0, 0, width, height)
        commands: list[_Command] = []

        def visit(
            node: Mapping[str, Any], parent_box: _Box, inherited_clips: tuple[_Box, ...],
            inherited_opacity: float, z_path: tuple[int, ...], forced: _Box | None = None,
        ) -> None:
            props = _resolved_props(node, width, semantic_data)
            if not props["visible"]:
                return
            box = root_box if node is template.document["root"] else _resolve_box(props, parent_box, forced)
            opacity = inherited_opacity * float(props["opacity"])
            commands.append(_Command(node, props, box, inherited_clips, opacity, (*z_path, -1)))
            child_clips = inherited_clips
            if node is template.document["root"] or props["overflow"] == "clip":
                child_clips = (*child_clips, box)
            if node["type"] not in CONTAINER_TYPES:
                return
            content = _content_box(box, props)
            children = _expanded_children(node, props)
            resolved = [(child, _resolved_props(child, width, semantic_data)) for child in children]
            absolute = [(child, child_props) for child, child_props in resolved if child_props["position"] == "absolute"]
            flow = [(child, child_props) for child, child_props in resolved if child_props["position"] == "flow"]
            for child, child_props, flow_box in _flow_layout(flow, content, props):
                visit(
                    child, content, child_clips, opacity,
                    (*z_path, int(child_props["z_index"])), flow_box,
                )
            for child, child_props in absolute:
                visit(
                    child, content, child_clips, opacity,
                    (*z_path, int(child_props["z_index"])), None,
                )

        visit(template.document["root"], root_box, (root_box,), 1.0, (0,))
        return sorted(commands, key=lambda item: item.z_path)

    @staticmethod
    def _rgba(color: str | None, fallback: str = "#00000000") -> tuple[int, int, int, int]:
        chosen = color or fallback
        if len(chosen) == 7:
            chosen += "FF"
        return tuple(int(chosen[index:index + 2], 16) for index in (1, 3, 5, 7))

    @staticmethod
    def _asset_record(
        key: str, declarations: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        declaration = declarations.get(key)
        record = assets.get(key)
        if declaration is None or record is None:
            raise ValueError(f"Studio preview asset is unavailable: {key}")
        mime = str(record.get("mime_type") or "")
        if mime not in declaration["allowed_mime_types"]:
            raise ValueError(f"Studio preview asset MIME is not allowed: {key}")
        data = record.get("bytes")
        if not isinstance(data, bytes) or not data:
            raise ValueError(f"Studio preview asset has no bytes: {key}")
        return record

    def _fit_image(
        self, record: Mapping[str, Any], size: tuple[int, int], *, fit: str,
        focal_x: float, focal_y: float,
    ):
        from PIL import Image, ImageOps
        with Image.open(BytesIO(record["bytes"])) as original:
            source = original.convert("RGBA")
        target = (max(1, size[0]), max(1, size[1]))
        if fit == "contain":
            fitted = ImageOps.contain(source, target)
            layer = Image.new("RGBA", target, (0, 0, 0, 0))
            layer.paste(fitted, ((target[0] - fitted.width) // 2, (target[1] - fitted.height) // 2), fitted)
            return layer
        if fit == "stretch":
            return source.resize(target, Image.Resampling.LANCZOS)
        return ImageOps.fit(source, target, centering=(float(focal_x), float(focal_y)))

    def _surface(
        self, command: _Command, declarations: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]],
    ):
        from PIL import Image, ImageChops, ImageDraw, ImageFilter
        props, box = command.props, command.box
        size = (max(1, round(box.width)), max(1, round(box.height)))
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        radius = max(0, round(float(props["radius"])))
        shadow_color = props["shadow_color"]
        if shadow_color and props["shadow_blur"] > 0:
            shadow = Image.new("RGBA", size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                (0, 0, size[0] - 1, size[1] - 1), radius=radius,
                fill=self._rgba(shadow_color),
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(float(props["shadow_blur"])))
            layer.alpha_composite(shadow, (round(props["shadow_x"]), round(props["shadow_y"])))
        if props["background_color"]:
            ImageDraw.Draw(layer).rounded_rectangle(
                (0, 0, size[0] - 1, size[1] - 1), radius=radius,
                fill=self._rgba(props["background_color"]),
            )
        gradient = props["background_gradient"]
        if gradient:
            colors = [self._rgba(item) for item in gradient]
            draw = ImageDraw.Draw(layer)
            for y in range(size[1]):
                position = 0 if size[1] == 1 else y / (size[1] - 1)
                scaled = position * (len(colors) - 1)
                left = min(len(colors) - 1, int(scaled))
                right = min(len(colors) - 1, left + 1)
                fraction = scaled - left
                color = tuple(round(colors[left][i] * (1 - fraction) + colors[right][i] * fraction) for i in range(4))
                draw.line((0, y, size[0], y), fill=color)
        if props["background_asset"]:
            record = self._asset_record(props["background_asset"], declarations, assets)
            background = self._fit_image(
                record, size, fit=props["background_fit"],
                focal_x=props["background_focal_x"], focal_y=props["background_focal_y"],
            )
            layer.alpha_composite(background)
        if radius > 0:
            mask = Image.new("L", size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
            layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        if props["border_color"] and props["border_width"] > 0:
            ImageDraw.Draw(layer).rounded_rectangle(
                (0, 0, size[0] - 1, size[1] - 1), radius=radius,
                outline=self._rgba(props["border_color"]), width=max(1, round(props["border_width"])),
            )
        return layer

    @staticmethod
    def _text_width(draw: Any, text: str, font: Any, spacing: float) -> float:
        if not text:
            return 0.0
        return sum(draw.textlength(char, font=font) for char in text) + spacing * (len(text) - 1)

    def _wrap_text(self, draw: Any, text: str, font: Any, width: int, spacing: float) -> list[str]:
        lines: list[str] = []
        for paragraph in text.splitlines() or [""]:
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = ""
            for word in words:
                candidate = word if not current else f"{current} {word}"
                if not current or self._text_width(draw, candidate, font, spacing) <= width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            if current:
                lines.append(current)
        return lines

    def _text_layer(self, command: _Command, text: str, *, color_property: str = "color"):
        from PIL import Image, ImageDraw
        props, box = command.props, command.box
        width, height = max(1, round(box.width)), max(1, round(box.height))
        casing = props["casing"]
        if casing == "upper":
            text = text.upper()
        elif casing == "lower":
            text = text.lower()
        elif casing == "title":
            text = text.title()
        requested = max(2, round(props["font_size"]))
        minimum = max(2, min(requested, round(props["min_font_size"])))
        chosen: tuple[Any, list[str], float, float] | None = None
        for size in range(requested, minimum - 1, -1):
            font = self.font_resolver(size, str(props["font_family"]), int(props["font_weight"]))
            probe = Image.new("RGBA", (max(width, 1), max(height, 1)), (0, 0, 0, 0))
            draw = ImageDraw.Draw(probe)
            letter_spacing = float(props["letter_spacing"])
            lines = [text] if props["wrap_text"] == "none" else self._wrap_text(draw, text, font, width, letter_spacing)
            lines = lines[: int(props["max_lines"])]
            line_height = size * float(props["line_height"])
            text_height = line_height * len(lines)
            widest = max((self._text_width(draw, line, font, letter_spacing) for line in lines), default=0)
            chosen = (font, lines, line_height, widest)
            if props["text_fit"] != "shrink" or (widest <= width and text_height <= height):
                break
        if chosen is None:
            return Image.new("RGBA", (width, height), (0, 0, 0, 0))
        font, lines, line_height, widest = chosen
        render_width = max(width, math.ceil(widest) + 4) if props["text_fit"] == "fixed" else width
        render_height = max(height, math.ceil(line_height * len(lines)) + 4) if props["text_fit"] == "fixed" else height
        layer = Image.new("RGBA", (render_width, render_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        total_height = line_height * len(lines)
        if props["vertical_align"] == "center":
            y = (height - total_height) / 2
        elif props["vertical_align"] == "bottom":
            y = height - total_height
        else:
            y = 0.0
        fill = self._rgba(str(props[color_property]))
        for line in lines:
            line_width = self._text_width(draw, line, font, float(props["letter_spacing"]))
            if props["text_align"] == "center":
                x = (width - line_width) / 2
            elif props["text_align"] == "right":
                x = width - line_width
            else:
                x = 0.0
            for character in line:
                draw.text((round(x), round(y)), character, font=font, fill=fill)
                x += draw.textlength(character, font=font) + float(props["letter_spacing"])
            y += line_height
        if props["font_style"] == "italic":
            skew = min(0.35, max(0.0, height / max(1, render_width) * 0.25))
            layer = layer.transform(
                (render_width + round(height * skew), render_height),
                Image.Transform.AFFINE, (1, -skew, 0, 0, 1, 0),
                resample=Image.Resampling.BICUBIC,
            )
        return layer

    def _content_layer(
        self, command: _Command, declarations: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]],
    ):
        from PIL import Image, ImageDraw, ImageChops, ImageFilter
        node, props, box = command.node, command.props, command.box
        primitive_type = node["type"]
        if primitive_type in CONTAINER_TYPES:
            return self._surface(command, declarations, assets)
        size = (max(1, round(box.width)), max(1, round(box.height)))
        if primitive_type == "text":
            return self._text_layer(command, str(props["text"]))
        if primitive_type == "button":
            surface = self._surface(command, declarations, assets)
            text_props = dict(props)
            text_props["text"] = props["label"] or props["text"]
            text_props["color"] = props["label_color"]
            inset = props["padding"]
            text_command = _Command(
                node, text_props,
                _Box(box.x + inset["left"], box.y + inset["top"],
                     max(1, box.width - inset["left"] - inset["right"]),
                     max(1, box.height - inset["top"] - inset["bottom"])),
                command.clips, command.opacity, command.z_path,
            )
            if props["icon_asset"]:
                record = self._asset_record(str(props["icon_asset"]), declarations, assets)
                icon_size = max(1, min(
                    round(text_command.box.height), round(float(props["font_size"]) * 1.2),
                ))
                icon = self._fit_image(
                    record, (icon_size, icon_size), fit="contain", focal_x=0.5, focal_y=0.5,
                )
                surface.alpha_composite(
                    icon, (round(inset["left"]), round(inset["top"])),
                )
                text_command = _Command(
                    node, text_props,
                    _Box(
                        text_command.box.x + icon_size + float(props["icon_gap"]),
                        text_command.box.y,
                        max(1, text_command.box.width - icon_size - float(props["icon_gap"])),
                        text_command.box.height,
                    ),
                    command.clips, command.opacity, command.z_path,
                )
            text = self._text_layer(text_command, str(text_props["text"]))
            surface.alpha_composite(
                text,
                (
                    round(text_command.box.x - box.x),
                    round(text_command.box.y - box.y),
                ),
            )
            return surface
        if primitive_type in {"image", "icon"} and props.get("asset"):
            record = self._asset_record(str(props["asset"]), declarations, assets)
            image = self._fit_image(
                record, size, fit=str(props.get("fit") or "contain"),
                focal_x=float(props.get("focal_x", 0.5)), focal_y=float(props.get("focal_y", 0.5)),
            )
            mask_kind = props.get("mask", "none")
            if mask_kind != "none" or props["radius"] > 0:
                mask = Image.new("L", size, 0)
                draw = ImageDraw.Draw(mask)
                if mask_kind == "ellipse":
                    draw.ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)
                else:
                    draw.rounded_rectangle(
                        (0, 0, size[0] - 1, size[1] - 1), radius=round(props["radius"]), fill=255,
                    )
                image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
            outline_color = props.get("alpha_outline_color")
            alpha = image.getchannel("A")
            alpha_bounds = alpha.getbbox()
            outline_ratio = float(props.get("alpha_outline_width_ratio", 0))
            outline_width = round(float(props.get("alpha_outline_width", 0)))
            if outline_ratio > 0 and alpha_bounds is not None:
                subject_width = alpha_bounds[2] - alpha_bounds[0]
                outline_width = max(1, min(100, round(subject_width * outline_ratio)))
            if outline_color and outline_width > 0:
                shadow_color = props.get("alpha_outline_shadow_color")
                shadow_blur = float(props.get("alpha_outline_shadow_blur", 0))
                shadow_offset = round(float(props.get("alpha_outline_shadow_y", 0)))
                shadow_room = math.ceil(shadow_blur * 2) + abs(shadow_offset) if shadow_color else 0
                padding = outline_width + shadow_room
                padded = Image.new(
                    "RGBA", (image.width + padding * 2, image.height + padding * 2),
                    (0, 0, 0, 0),
                )
                padded.alpha_composite(image, (padding, padding))
                image = padded
                alpha = image.getchannel("A")

                # Build a solid contour from the visible subject, not a blurred
                # copy of its rectangular image layer. Dilation closes tiny
                # notches while the final sub-pixel feather only antialiases the
                # edge; the source object itself is composited last and stays crisp.
                expanded = alpha.point(lambda value: 255 if value >= 8 else 0)
                remaining = outline_width
                while remaining > 0:
                    radius = min(remaining, 4)
                    expanded = expanded.filter(ImageFilter.MaxFilter(radius * 2 + 1))
                    remaining -= radius
                feather = max(0.5, min(1.0, outline_width * 0.08))
                expanded = expanded.filter(ImageFilter.GaussianBlur(feather))
                shadow_layer = None
                if shadow_color and shadow_blur > 0:
                    shadow_alpha = expanded.filter(ImageFilter.GaussianBlur(shadow_blur))
                    shadow = Image.new("RGBA", image.size, self._rgba(shadow_color))
                    shadow.putalpha(shadow_alpha)
                    shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
                    shadow_layer.alpha_composite(shadow, (0, shadow_offset))
                outline = Image.new("RGBA", image.size, self._rgba(outline_color))
                outline.putalpha(expanded)
                outline.alpha_composite(image)
                if shadow_layer is not None:
                    shadow_layer.alpha_composite(outline)
                    image = shadow_layer
                else:
                    image = outline
                image.info["ptw_unpadded_size"] = size
            return image
        if primitive_type == "icon":
            icon_props = dict(props)
            icon_props.update({
                "text": props["glyph"], "color": props["fill"], "font_size": min(size),
                "min_font_size": 2.0, "font_weight": 500, "font_style": "normal",
                "line_height": 1.0, "letter_spacing": 0.0, "text_align": "center",
                "vertical_align": "center", "max_lines": 1, "wrap_text": "none",
                "text_fit": "shrink", "casing": "none", "font_family": "Inter",
            })
            return self._text_layer(_Command(
                node, icon_props, box, command.clips, command.opacity, command.z_path,
            ), str(props["glyph"]))
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        if primitive_type == "shape":
            fill = self._rgba(props["fill"])
            outline = None if props["stroke_color"] is None else self._rgba(props["stroke_color"])
            stroke = max(1, round(props["stroke_width"])) if outline else 0
            target = (0, 0, size[0] - 1, size[1] - 1)
            if props["shape"] == "ellipse":
                draw.ellipse(target, fill=fill, outline=outline, width=stroke)
            elif props["shape"] == "line":
                if props["line_direction"] == "vertical":
                    points = ((size[0] / 2, 0), (size[0] / 2, size[1]))
                elif props["line_direction"] == "diagonal":
                    points = ((0, size[1]), (size[0], 0))
                else:
                    points = ((0, size[1] / 2), (size[0], size[1] / 2))
                draw.line(points, fill=outline or fill, width=max(1, stroke or round(min(size) / 10)))
            else:
                draw.rounded_rectangle(target, radius=round(props["radius"]), fill=fill, outline=outline, width=stroke)
        elif primitive_type == "spacer" and props["divider_color"]:
            if props["orientation"] == "vertical":
                points = ((size[0] / 2, 0), (size[0] / 2, size[1]))
            else:
                points = ((0, size[1] / 2), (size[0], size[1] / 2))
            draw.line(points, fill=self._rgba(props["divider_color"]), width=max(1, round(props["thickness"])))
        return layer

    @staticmethod
    def _transform(layer: Any, command: _Command) -> tuple[Any, int, int]:
        from PIL import Image
        props, box = command.props, command.box
        base_width, base_height = layer.info.get("ptw_unpadded_size", layer.size)
        scale_x, scale_y = float(props["scale_x"]), float(props["scale_y"])
        scaled = layer.resize(
            (max(1, round(layer.width * scale_x)), max(1, round(layer.height * scale_y))),
            Image.Resampling.LANCZOS,
        ) if scale_x != 1 or scale_y != 1 else layer
        origin_x, origin_y = float(props["transform_origin_x"]), float(props["transform_origin_y"])
        x = box.x + base_width * origin_x - scaled.width * origin_x
        y = box.y + base_height * origin_y - scaled.height * origin_y
        rotation = float(props["rotation"])
        if rotation:
            before = scaled.size
            scaled = scaled.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=True)
            x -= (scaled.width - before[0]) * origin_x
            y -= (scaled.height - before[1]) * origin_y
        return scaled, round(x), round(y)

    @staticmethod
    def _composite(canvas: Any, layer: Any, x: int, y: int, command: _Command) -> None:
        from PIL import Image, ImageChops
        full = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        destination_left, destination_top = max(0, x), max(0, y)
        source_left, source_top = max(0, -x), max(0, -y)
        copy_width = min(layer.width - source_left, canvas.width - destination_left)
        copy_height = min(layer.height - source_top, canvas.height - destination_top)
        if copy_width <= 0 or copy_height <= 0:
            return
        cropped = layer.crop((
            source_left, source_top, source_left + copy_width, source_top + copy_height,
        ))
        full.alpha_composite(cropped, (destination_left, destination_top))
        alpha = full.getchannel("A")
        if command.opacity < 1:
            alpha = alpha.point(lambda value: round(value * command.opacity))
        if command.clips:
            clip_mask = Image.new("L", canvas.size, 255)
            for clip in command.clips:
                one = Image.new("L", canvas.size, 0)
                right = max(round(clip.x), round(clip.right) - 1)
                bottom = max(round(clip.y), round(clip.bottom) - 1)
                from PIL import ImageDraw
                ImageDraw.Draw(one).rectangle(
                    (round(clip.x), round(clip.y), right, bottom), fill=255,
                )
                clip_mask = ImageChops.multiply(clip_mask, one)
            alpha = ImageChops.multiply(alpha, clip_mask)
        full.putalpha(alpha)
        canvas.alpha_composite(full)

    @staticmethod
    def _visible_bounds(layer: Any, x: int, y: int, command: _Command, width: int, height: int) -> dict[str, float] | None:
        alpha_bounds = layer.getchannel("A").getbbox()
        if alpha_bounds is None:
            return None
        left = max(0.0, float(x + alpha_bounds[0]))
        top = max(0.0, float(y + alpha_bounds[1]))
        right = min(float(width), float(x + alpha_bounds[2]))
        bottom = min(float(height), float(y + alpha_bounds[3]))
        for clip in command.clips:
            left, top = max(left, clip.x), max(top, clip.y)
            right, bottom = min(right, clip.right), min(bottom, clip.bottom)
        if right <= left or bottom <= top:
            return None
        return {
            "x": left / width,
            "y": top / height,
            "width": (right - left) / width,
            "height": (bottom - top) / height,
        }

    def render(
        self, template: PrimitiveTemplate | Mapping[str, Any], *,
        semantic_data: Mapping[str, Any], assets: Mapping[str, Mapping[str, Any]],
        width: int | None = None, height: int | None = None,
    ) -> dict[str, Any]:
        from PIL import Image
        normalized = template if isinstance(template, PrimitiveTemplate) else PrimitiveTemplate.from_dict(template)
        root_props = normalized.document["root"]["props"]
        target_width = int(width or root_props["width"])
        target_height = int(height or root_props["height"])
        if not 1 <= target_width <= 8192 or not 1 <= target_height <= 8192:
            raise ValueError("Studio preview dimensions must be between 1 and 8192 pixels")
        for key, declaration in normalized.document["assets"].items():
            if declaration["required"] and key not in assets:
                raise ValueError(f"Studio preview is missing required asset: {key}")
        canvas = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        commands = self._commands(normalized, semantic_data, target_width, target_height)
        resolved_nodes: dict[str, Any] = {}
        for command in commands:
            layer = self._content_layer(command, normalized.document["assets"], assets)
            layer, x, y = self._transform(layer, command)
            box = command.box
            resolved_nodes[str(command.node["id"])] = {
                "type": command.node["type"],
                "box": {
                    "x": box.x / target_width,
                    "y": box.y / target_height,
                    "width": box.width / target_width,
                    "height": box.height / target_height,
                },
                "visible_bounds": self._visible_bounds(
                    layer, x, y, command, target_width, target_height,
                ),
                "props": {
                    name: _deep_copy(command.props[name])
                    for name in (
                        "font_family", "font_size", "font_weight", "line_height",
                        "letter_spacing", "text_align", "scale_x", "scale_y",
                        "fit", "focal_x", "focal_y", "alpha_outline_color",
                        "alpha_outline_width", "alpha_outline_width_ratio",
                        "alpha_outline_shadow_color",
                        "alpha_outline_shadow_blur", "alpha_outline_shadow_y",
                    )
                    if name in command.props
                },
            }
            self._composite(canvas, layer, x, y, command)
        output = BytesIO()
        canvas.save(output, format="PNG", optimize=False)
        data = output.getvalue()
        resolved = {
            "schema": "ptw.studio.preview.v1",
            "template_id": normalized.document["template_id"],
            "template_version": normalized.document["version"],
            "template_sha256": normalized.digest,
            "catalog_version": PRIMITIVE_CATALOG_VERSION,
            "width": target_width,
            "height": target_height,
            "semantic_roles": _deep_copy(normalized.document["semantic_roles"]),
            "node_count": len(list(_iter_nodes(normalized.document["root"]))),
            "asset_keys": sorted(normalized.document["assets"]),
            "asset_sha256": {
                key: hashlib.sha256(assets[key]["bytes"]).hexdigest()
                for key in sorted(normalized.document["assets"])
                if key in assets
            },
            "nodes": resolved_nodes,
        }
        return {
            "bytes": data, "mime_type": "image/png", "width": target_width,
            "height": target_height, "bytes_sha256": hashlib.sha256(data).hexdigest(),
            "resolved": resolved,
        }
