"""Git-owned Studio component templates and deterministic agent tuning."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from uuid import UUID

from commander.ids import new_uuid7

from .content import SLIDER_NAMES, TEMPLATE_IDS
from .natal_brand import NATAL_COLORS
from .studio import (
    DEFAULT_GUARDS, DEFAULT_SOURCE_REFS, PLACEMENT_ID, PROFILE_PLACEMENTS,
    TIKTOK_PLACEMENT_ID, TOOLS_BY_ID, _frame, _validate_component_params,
    renderer_identity, tool_catalog_for_profile,
)


TEMPLATE_SCHEMA = "ptw.studio.template.v1"
APPLICATION_SCHEMA = "studio.layout.template_application.v1"
APPLICATION_TOOL_ID = "studio.layout.template_application.v1"
TEMPLATE_VERSION = 3
REPLAY_TEMPLATE_VERSIONS = frozenset({2, TEMPLATE_VERSION})
TEMPLATE_DIRECTORY = Path(__file__).with_name("studio_templates") / "instagram"
TIKTOK_TEMPLATE_DIRECTORY = Path(__file__).with_name("studio_templates") / "tiktok"
REQUIRED_ELEMENT_ROLES = (
    "background", "primary_subject", "headline_block", "supporting_text_block",
    "offer_block", "cta_block", "brand_mark",
)
PALETTE_ROLES = ("dark", "ink", "light", "muted", "accent", "accent_soft")
ALLOWED_BINDING_SOURCES = {
    "candidate.headline": "text",
    "candidate.primary_text": "text",
    "candidate.hook": "text",
    "candidate.supporting_text": "text",
    "brief.offer": "text",
    "brief.cta": "text",
    "resolved.media_asset_id": "asset_id",
    "resolved.logo_asset_id": "asset_id",
    "share.caption": "text",
    "share.alt_text": "text",
    **{f"palette.{role}": "color" for role in PALETTE_ROLES},
}
COMMON_REQUIRED_BINDING_SOURCES = {
    "brief.offer", "brief.cta",
    "resolved.media_asset_id", "resolved.logo_asset_id", "share.caption", "share.alt_text",
}


def _canonical(value: Any) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def _deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _uuid7(value: str, label: str) -> str:
    parsed = UUID(str(value))
    if parsed.version != 7:
        raise ValueError(f"{label} must be a UUIDv7")
    return str(parsed)


def _path_get(component: Mapping[str, Any], path: str) -> Any:
    value: Any = component
    for part in path.split("."):
        value = value[part]
    return value


def _path_set(component: dict[str, Any], path: str, value: Any) -> None:
    target: dict[str, Any] = component
    parts = path.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value


def _quantized(value: Decimal, quantum: Decimal) -> int | float:
    result = (value / quantum).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * quantum
    if quantum >= 1:
        return int(result)
    return float(result)


def _rule_value(rule: Mapping[str, Any], slider_value: int) -> Any:
    kind = rule["type"]
    if kind == "numeric_interpolation":
        low, high = Decimal(str(rule["minimum"])), Decimal(str(rule["maximum"]))
        raw = low + (high - low) * Decimal(slider_value) / Decimal(100)
        return _quantized(raw, Decimal(str(rule["quantize"])))
    if kind == "enumerated_steps":
        chosen = rule["steps"][0]["value"]
        for step in rule["steps"]:
            if slider_value >= int(step["minimum"]):
                chosen = step["value"]
        return chosen
    if kind == "optional_component_threshold":
        return slider_value >= int(rule["minimum"])
    raise ValueError(f"unknown Studio tuning rule type: {kind}")


def _normalize_rule(raw: Mapping[str, Any], *, component: Mapping[str, Any]) -> dict[str, Any]:
    common = {"slider", "component_key", "path", "rule"}
    if set(raw) != common or str(raw["slider"]) not in SLIDER_NAMES:
        raise ValueError("Studio tuning rule fields or slider are invalid")
    if raw["component_key"] != component["key"]:
        raise ValueError("Studio tuning rule component does not match its lookup key")
    path = str(raw["path"])
    definition = raw["rule"]
    if not isinstance(definition, Mapping) or "type" not in definition:
        raise ValueError("Studio tuning rule requires one typed rule")
    kind = str(definition["type"])
    if kind == "numeric_interpolation":
        if set(definition) != {"type", "minimum", "maximum", "quantize"}:
            raise ValueError("numeric interpolation fields are invalid")
        minimum, maximum = float(definition["minimum"]), float(definition["maximum"])
        quantum = float(definition["quantize"])
        if quantum <= 0:
            raise ValueError("numeric interpolation bounds are invalid")
    elif kind == "enumerated_steps":
        if set(definition) != {"type", "steps"} or not isinstance(definition["steps"], list):
            raise ValueError("enumerated step fields are invalid")
        minimums = [int(item["minimum"]) for item in definition["steps"]]
        if not minimums or minimums != sorted(set(minimums)) or minimums[0] != 0:
            raise ValueError("enumerated steps must start at zero in strict order")
        if any(set(item) != {"minimum", "value"} or not 0 <= int(item["minimum"]) <= 100
               for item in definition["steps"]):
            raise ValueError("enumerated step entries are invalid")
    elif kind == "optional_component_threshold":
        if set(definition) != {"type", "minimum"} or not 0 <= int(definition["minimum"]) <= 100:
            raise ValueError("optional component threshold fields are invalid")
        if path != "enabled" or component["optional"] is not True:
            raise ValueError("optional thresholds may control only optional components")
    else:
        raise ValueError("Studio templates support only three deterministic tuning rule types")
    if path != "enabled":
        tool = TOOLS_BY_ID[component["tool_id"]]
        if path not in tool["tunable_paths"]:
            raise ValueError(f"{component['tool_id']} does not declare tunable path {path}")
        _path_get(component, path)
    return {
        "slider": str(raw["slider"]), "component_key": str(raw["component_key"]),
        "path": path, "rule": _deep_copy(definition),
    }


def _palette() -> dict[str, str]:
    return dict(zip(PALETTE_ROLES, NATAL_COLORS, strict=True))


@dataclass(frozen=True, slots=True)
class StudioTemplate:
    template_id: str
    version: int
    document: Mapping[str, Any]
    digest: str


def _profile_for_placement(placement_tool_id: str) -> str:
    for profile, placement in PROFILE_PLACEMENTS.items():
        if placement == placement_tool_id:
            return profile
    raise ValueError("Studio template placement is unavailable")


def _normalize_template(
    value: Mapping[str, Any], *, expected_placement_id: str | None = None,
) -> StudioTemplate:
    expected = {
        "schema", "template_id", "version", "active", "placement_tool_id",
        "components", "bindings", "tuning_rules",
    }
    if set(value) != expected or value.get("schema") != TEMPLATE_SCHEMA:
        raise ValueError("Studio template fields do not match ptw.studio.template.v1")
    template_id = str(value["template_id"])
    if template_id not in TEMPLATE_IDS or value.get("active") is not True:
        raise ValueError("Studio template identity or active flag is invalid")
    version = int(value["version"])
    placement_tool_id = str(value["placement_tool_id"])
    if (
        version not in REPLAY_TEMPLATE_VERSIONS
        or placement_tool_id not in PROFILE_PLACEMENTS.values()
        or expected_placement_id is not None and placement_tool_id != expected_placement_id
    ):
        raise ValueError("Studio templates must use a supported version and placement")
    profile = _profile_for_placement(placement_tool_id)
    catalog_tools = {
        item["tool_id"]: item for item in tool_catalog_for_profile(profile)["items"]
    }
    raw_components = value["components"]
    if not isinstance(raw_components, list) or not 7 <= len(raw_components) <= 20:
        raise ValueError("Studio templates require seven to twenty predefined components")
    components: list[dict[str, Any]] = []
    keys: set[str] = set()
    roles: list[str] = []
    z_indexes: set[int] = set()
    for index, raw in enumerate(raw_components):
        if not isinstance(raw, Mapping) or set(raw) != {
            "key", "element_role", "tool_id", "frame", "z_index", "params",
            "source_asset_ids", "optional",
        }:
            raise ValueError(f"Studio component {index} fields are invalid")
        key = str(raw["key"])
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,47}", key) or key in keys:
            raise ValueError("Studio component keys must be stable, readable, and unique")
        keys.add(key)
        tool_id = str(raw["tool_id"])
        tool = catalog_tools.get(tool_id)
        if tool is None or tool["kind"] != "frame" or placement_tool_id not in tool["allowed_placements"]:
            raise ValueError(f"Studio component uses an unavailable catalog tool: {tool_id}")
        element_role = raw["element_role"]
        if element_role is not None:
            element_role = str(element_role)
            if element_role not in REQUIRED_ELEMENT_ROLES:
                raise ValueError("Studio component element role is not a candidate semantic role")
            roles.append(element_role)
        z_index = int(raw["z_index"])
        if z_index in z_indexes:
            raise ValueError("Studio component z-index values must be unique")
        z_indexes.add(z_index)
        params = raw["params"]
        if not isinstance(params, Mapping):
            raise ValueError("Studio component params must be an object")
        if not set(params) <= set(tool["parameter_schema"]["properties"]):
            raise ValueError("Studio component contains parameters outside its predefined tool")
        source_ids = raw["source_asset_ids"]
        if not isinstance(source_ids, list) or source_ids:
            raise ValueError("Git-owned Studio templates cannot contain raw source asset IDs")
        components.append({
            "key": key, "element_role": element_role, "tool_id": tool_id,
            "frame": _frame(raw["frame"], f"components[{index}]"),
            "z_index": z_index, "params": _deep_copy(params), "source_asset_ids": [],
            "optional": bool(raw["optional"]),
        })
    if sorted(roles) != sorted(REQUIRED_ELEMENT_ROLES):
        raise ValueError("Studio templates must map every candidate semantic frame exactly once")
    by_key = {item["key"]: item for item in components}

    raw_bindings = value["bindings"]
    if not isinstance(raw_bindings, list):
        raise ValueError("Studio template bindings must be a list")
    bindings: list[dict[str, Any]] = []
    binding_targets: set[tuple[str, str]] = set()
    sources: list[str] = []
    for raw in raw_bindings:
        if not isinstance(raw, Mapping) or set(raw) != {
            "component_key", "target", "source", "value_type", "protected",
        }:
            raise ValueError("Studio template binding fields are invalid")
        source, value_type = str(raw["source"]), str(raw["value_type"])
        if ALLOWED_BINDING_SOURCES.get(source) != value_type or raw["protected"] is not True:
            raise ValueError("Studio bindings must use a protected typed source")
        component_key, target = str(raw["component_key"]), str(raw["target"])
        if component_key == "$share":
            if target not in {"caption", "alt_text"}:
                raise ValueError("share bindings may set only caption or alt_text")
        else:
            component = by_key.get(component_key)
            if component is None:
                raise ValueError("Studio binding references an unknown component key")
            if target == "source_asset_ids.0":
                if component["tool_id"] not in {"studio.frame.media.v1", "studio.frame.logo.v1"}:
                    raise ValueError("asset bindings may target only media or logo components")
            elif target.startswith("params."):
                parameter = target.removeprefix("params.")
                definition = catalog_tools[component["tool_id"]]["parameter_schema"]["properties"].get(parameter)
                expected_type = "string" if value_type == "text" else value_type
                if definition is None or definition["type"] != expected_type:
                    raise ValueError("Studio binding type does not match its component parameter")
            else:
                raise ValueError("Studio binding target is not declared")
        identity = (component_key, target)
        if identity in binding_targets:
            raise ValueError("Studio binding targets must be unique")
        binding_targets.add(identity)
        sources.append(source)
        bindings.append({
            "component_key": component_key, "target": target, "source": source,
            "value_type": value_type, "protected": True,
        })
    required_copy = (
        {"candidate.headline", "candidate.primary_text"}
        if version == TEMPLATE_VERSION
        else {"candidate.hook", "candidate.supporting_text"}
    )
    if not (COMMON_REQUIRED_BINDING_SOURCES | required_copy) <= set(sources):
        raise ValueError("Studio template is missing a required protected binding")
    if version == TEMPLATE_VERSION:
        bound_text_targets = {
            (item["component_key"], item["target"])
            for item in bindings if item["value_type"] == "text"
        }
        for component in components:
            static_text = component["params"].get("text")
            if (
                static_text is not None
                and (component["key"], "params.text") not in bound_text_targets
                and static_text not in {"↗", "→", "•"}
            ):
                raise ValueError("active Studio templates cannot contain localized static text")

    raw_rules = value["tuning_rules"]
    if not isinstance(raw_rules, list):
        raise ValueError("Studio tuning rules must be a list")
    rules: list[dict[str, Any]] = []
    rule_targets: set[tuple[str, str]] = set()
    for raw in raw_rules:
        if not isinstance(raw, Mapping) or str(raw.get("component_key")) not in by_key:
            raise ValueError("Studio tuning rule references an unknown component")
        rule = _normalize_rule(raw, component=by_key[str(raw["component_key"])])
        identity = (rule["component_key"], rule["path"])
        if identity in rule_targets or identity in binding_targets:
            raise ValueError("Studio tuning paths must be unique and cannot alter protected bindings")
        rule_targets.add(identity)
        rules.append(rule)
    if set(item["slider"] for item in rules) != set(SLIDER_NAMES):
        raise ValueError("every Studio template must declare component rules for all five sliders")
    optional_keys = {item["key"] for item in components if item["optional"]}
    threshold_keys = {
        item["component_key"] for item in rules
        if item["rule"]["type"] == "optional_component_threshold"
    }
    if optional_keys != threshold_keys:
        raise ValueError("every optional component requires one bounded threshold rule")

    # Resolve safe placeholders and validate the final component parameter shape against the catalog.
    placeholders: dict[str, Any] = {
        "candidate.headline": "Headline", "candidate.primary_text": "Primary text",
        "candidate.hook": "Headline", "candidate.supporting_text": "Body",
        "brief.offer": "Offer", "brief.cta": "CTA", "resolved.media_asset_id": new_uuid7(),
        "resolved.logo_asset_id": new_uuid7(), "share.caption": "Caption",
        "share.alt_text": "Alt text", **{f"palette.{key}": color for key, color in _palette().items()},
    }
    resolved_components = _deep_copy(components)
    resolved_by_key = {item["key"]: item for item in resolved_components}
    for binding in bindings:
        if binding["component_key"] == "$share":
            continue
        component = resolved_by_key[binding["component_key"]]
        if binding["target"] == "source_asset_ids.0":
            component["source_asset_ids"] = [placeholders[binding["source"]]]
        else:
            _path_set(component, binding["target"], placeholders[binding["source"]])
    for component in resolved_components:
        _validate_component_params(
            tool_id=component["tool_id"], params=component["params"], brand_colors=NATAL_COLORS,
        )
        expected_assets = 1 if component["tool_id"] in {
            "studio.frame.media.v1", "studio.frame.logo.v1",
        } else 0
        if len(component["source_asset_ids"]) != expected_assets:
            raise ValueError("Studio media and logo components require exact typed asset bindings")
    if version == TEMPLATE_VERSION:
        logo = next(item for item in resolved_components if item["element_role"] == "brand_mark")
        logo_frame = logo["frame"]
        containing_layers = [
            item for item in resolved_components
            if item["z_index"] < logo["z_index"]
            and item["frame"]["x"] <= logo_frame["x"]
            and item["frame"]["y"] <= logo_frame["y"]
            and item["frame"]["x"] + item["frame"]["width"]
                >= logo_frame["x"] + logo_frame["width"]
            and item["frame"]["y"] + item["frame"]["height"]
                >= logo_frame["y"] + logo_frame["height"]
        ]
        top_layer = max(containing_layers, key=lambda item: item["z_index"], default=None)
        if (
            top_layer is None
            or top_layer["tool_id"] != "studio.frame.shape.v1"
            or top_layer["params"].get("background")
                not in {_palette()["light"], _palette()["accent_soft"]}
        ):
            raise ValueError("Natal logo requires a containing high-contrast light surface")

    document = {
        "schema": TEMPLATE_SCHEMA, "template_id": template_id, "version": version,
        "active": True, "placement_tool_id": placement_tool_id,
        "components": components, "bindings": bindings, "tuning_rules": rules,
    }
    _, digest = _canonical(document)
    return StudioTemplate(template_id, version, document, digest)


class StudioTemplateRegistry:
    def __init__(
        self, directory: Path | None = None, *, output_profile: str = "instagram_static_ad_v1",
    ) -> None:
        if output_profile not in PROFILE_PLACEMENTS:
            raise ValueError("Studio template registry requires a static social profile")
        self.output_profile = output_profile
        self.placement_tool_id = PROFILE_PLACEMENTS[output_profile]
        self.directory = directory or (
            TEMPLATE_DIRECTORY
            if output_profile == "instagram_static_ad_v1"
            else TIKTOK_TEMPLATE_DIRECTORY
        )

    def load_active(self, strategy_templates: Sequence[Any] = ()) -> tuple[StudioTemplate, ...]:
        manifest_path = self.directory / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio template registry manifest is unavailable or invalid") from error
        if (
            not isinstance(manifest, Mapping)
            or set(manifest) != {"schema", "active"}
            or manifest.get("schema") != "ptw.studio.template-registry.v1"
            or not isinstance(manifest.get("active"), list)
        ):
            raise ValueError("Studio template registry manifest fields are invalid")
        registry: dict[str, Mapping[str, Any]] = {}
        for item in manifest["active"]:
            if not isinstance(item, Mapping) or set(item) != {
                "template_id", "version", "strategy_sha256", "studio_sha256",
            }:
                raise ValueError("Studio template registry entry fields are invalid")
            template_id = str(item["template_id"])
            if (
                template_id in registry or template_id not in TEMPLATE_IDS
                or int(item["version"]) != TEMPLATE_VERSION
                or not re.fullmatch(r"[0-9a-f]{64}", str(item["strategy_sha256"]))
                or not re.fullmatch(r"[0-9a-f]{64}", str(item["studio_sha256"]))
            ):
                raise ValueError("Studio template registry entry identity is invalid")
            registry[template_id] = item
        if set(registry) != set(TEMPLATE_IDS):
            raise ValueError("Studio template registry manifest must lock exactly five active IDs")
        templates: list[StudioTemplate] = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                value = json.loads(path.read_text())
            except json.JSONDecodeError as error:
                raise ValueError(f"Studio template {path.name} is not strict JSON") from error
            if not isinstance(value, Mapping):
                raise ValueError(f"Studio template {path.name} is not one document")
            if value.get("active") is True:
                templates.append(_normalize_template(
                    value, expected_placement_id=self.placement_tool_id,
                ))
        ids = [item.template_id for item in templates]
        if len(templates) != 5 or len(set(ids)) != 5 or set(ids) != set(TEMPLATE_IDS):
            raise ValueError("Studio registry must contain exactly five active template definitions")
        ordered = tuple(sorted(templates, key=lambda item: TEMPLATE_IDS.index(item.template_id)))
        for template in ordered:
            if registry[template.template_id]["studio_sha256"] != template.digest:
                raise ValueError(f"Studio template registry digest mismatch: {template.template_id}")
        if strategy_templates:
            strategies = {item.template_id: item for item in strategy_templates}
            if set(strategies) != set(ids):
                raise ValueError("active strategy and Studio template IDs are not synchronized")
            for template in ordered:
                strategy = strategies[template.template_id]
                if (
                    int(strategy.version) != TEMPLATE_VERSION
                    or int(registry[template.template_id]["version"]) != template.version
                    or str(registry[template.template_id]["strategy_sha256"]) != strategy.digest
                ):
                    raise ValueError(
                        f"strategy and Studio template version/digest mismatch: {template.template_id}"
                    )
        return ordered

    def get(self, template_id: str) -> StudioTemplate:
        return {item.template_id: item for item in self.load_active()}[template_id]


def _binding_values(
    *, candidate: Mapping[str, Any], brief: Mapping[str, Any], brand_document: Mapping[str, Any],
    media_asset_id: str,
) -> dict[str, Any]:
    if (
        brand_document.get("name") != "Natal"
        or list(brand_document.get("colors") or ()) != list(NATAL_COLORS)
        or list(brand_document.get("fonts") or ()) != ["Inter"]
    ):
        raise ValueError("configured social templates require the canonical Natal palette and Inter")
    logo_id = brand_document.get("logo_source_asset_id")
    if not logo_id:
        raise ValueError("configured social templates require the canonical Natal logo")
    return {
        "candidate.headline": str(candidate["headline"]),
        "candidate.primary_text": str(candidate["primary_text"]),
        "candidate.hook": str(candidate["hook"]),
        "candidate.supporting_text": str(candidate["supporting_text"]),
        "brief.offer": str(brief["offer"]), "brief.cta": str(brief["cta"]),
        "resolved.media_asset_id": _uuid7(media_asset_id, "resolved media asset ID"),
        "resolved.logo_asset_id": _uuid7(str(logo_id), "resolved logo asset ID"),
        "share.caption": str(candidate["caption"]), "share.alt_text": str(candidate["alt_text"]),
        **{f"palette.{key}": value for key, value in _palette().items()},
    }


def _materialize(
    *, template: StudioTemplate, strategy_template: Mapping[str, Any],
    slider_values: Mapping[str, int], binding_values: Mapping[str, Any],
    component_instances: Mapping[str, str], modifier_instance_id: str,
    parent_recipe_id: str | None, base_recipe_sha256: str | None,
) -> dict[str, Any]:
    if set(slider_values) != set(SLIDER_NAMES):
        raise ValueError("Studio template application requires all five slider values")
    sliders = {name: int(slider_values[name]) for name in SLIDER_NAMES}
    if any(not 0 <= value <= 100 for value in sliders.values()):
        raise ValueError("Studio slider values must stay between zero and one hundred")
    if set(component_instances) != {item["key"] for item in template.document["components"]}:
        raise ValueError("Studio component instance map must reserve every template component")
    instances = {
        key: _uuid7(str(value), f"component instance {key}")
        for key, value in component_instances.items()
    }
    if len(set(instances.values())) != len(instances):
        raise ValueError("Studio component instance IDs must be unique")
    modifier_id = _uuid7(modifier_instance_id, "template modifier instance ID")
    if modifier_id in instances.values():
        raise ValueError("Studio modifier ID must be separate from component IDs")
    if (parent_recipe_id is None) != (base_recipe_sha256 is None):
        raise ValueError("parent recipe and base recipe digest must be supplied together")
    parent = None if parent_recipe_id is None else _uuid7(parent_recipe_id, "parent recipe ID")
    if base_recipe_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", base_recipe_sha256):
        raise ValueError("base recipe digest must be a lowercase SHA-256")

    components = _deep_copy(template.document["components"])
    by_key = {item["key"]: item for item in components}
    enabled = {item["key"]: not item["optional"] for item in components}
    patch: list[dict[str, Any]] = []
    for ordinal, rule in enumerate(template.document["tuning_rules"]):
        component = by_key[rule["component_key"]]
        before = enabled[component["key"]] if rule["path"] == "enabled" else _path_get(component, rule["path"])
        after = _rule_value(rule["rule"], sliders[rule["slider"]])
        if before != after:
            if rule["path"] == "enabled":
                enabled[component["key"]] = bool(after)
            else:
                _path_set(component, rule["path"], after)
            patch.append({
                "ordinal": ordinal, "component_key": component["key"], "path": rule["path"],
                "before": before, "after": after, "slider": rule["slider"],
                "rule_type": rule["rule"]["type"],
            })

    binding_map: list[dict[str, Any]] = []
    share: dict[str, str] = {}
    for binding in template.document["bindings"]:
        source = binding["source"]
        if source not in binding_values:
            raise ValueError(f"Studio replay metadata is missing binding {source}")
        value = binding_values[source]
        if binding["value_type"] == "asset_id":
            value = _uuid7(str(value), source)
        elif binding["value_type"] == "color":
            value = str(value).upper()
            if value not in NATAL_COLORS:
                raise ValueError("Studio color binding is outside the Natal palette")
        else:
            value = str(value)
        if binding["component_key"] == "$share":
            share[binding["target"]] = value
        else:
            component = by_key[binding["component_key"]]
            if binding["target"] == "source_asset_ids.0":
                component["source_asset_ids"] = [value]
            else:
                _path_set(component, binding["target"], value)
        binding_map.append({**dict(binding), "value": value})

    frames: list[dict[str, Any]] = []
    for component in components:
        if not enabled[component["key"]]:
            continue
        _validate_component_params(
            tool_id=component["tool_id"], params=component["params"], brand_colors=NATAL_COLORS,
        )
        frames.append({
            "instance_id": instances[component["key"]], "tool_id": component["tool_id"],
            "frame": dict(component["frame"]), "z_index": component["z_index"],
            "params": dict(component["params"]), "timeline": None,
            "source_asset_ids": list(component["source_asset_ids"]),
        })
    frames.sort(key=lambda item: item["z_index"])
    _, components_digest = _canonical(frames)
    _, bindings_digest = _canonical(binding_map)
    _, patch_digest = _canonical(patch)
    profile = _profile_for_placement(str(template.document["placement_tool_id"]))
    catalog = tool_catalog_for_profile(profile)
    renderer = renderer_identity(profile)
    metadata = {
        "schema": APPLICATION_SCHEMA,
        "strategy_template": {
            "template_id": str(strategy_template["template_id"]),
            "version": int(strategy_template["version"]),
            "sha256": str(strategy_template["sha256"]),
        },
        "studio_template": {
            "template_id": template.template_id, "version": template.version,
            "sha256": template.digest,
        },
        "catalog": {
            "version": catalog["catalog_version"], "sha256": catalog["catalog_sha256"],
        },
        "renderer": dict(renderer), "template_snapshot": _deep_copy(template.document),
        "slider_input": sliders,
        "slider_normalized": {name: float(Decimal(value) / Decimal(100)) for name, value in sliders.items()},
        "component_instances": instances, "modifier_instance_id": modifier_id,
        "bindings": binding_map, "bindings_sha256": bindings_digest,
        "component_patch": patch, "patch_sha256": patch_digest,
        "components_sha256": components_digest,
        "parent_recipe_id": parent, "base_recipe_sha256": base_recipe_sha256,
    }
    return {
        "schema_version": 2, "parent_recipe_id": parent,
        "placement_tool_id": template.document["placement_tool_id"],
        "duration_seconds": None, "frame_rate": None,
        "frames": frames,
        "modifiers": [{"instance_id": modifier_id, "tool_id": APPLICATION_TOOL_ID, "params": metadata}],
        "strategy_ids": [
            "studio.strategy.one_message.v1", "studio.strategy.specific_cta.v1",
            "studio.strategy.visual_proof.v1",
        ],
        "validation_ids": list(DEFAULT_GUARDS),
        "source_reference_ids": list(DEFAULT_SOURCE_REFS),
        "share": share,
    }


def apply_studio_template(
    *, template: StudioTemplate, strategy_template: Mapping[str, Any],
    slider_values: Mapping[str, int], candidate: Mapping[str, Any], brief: Mapping[str, Any],
    brand_document: Mapping[str, Any], media_asset_id: str,
    semantic_instance_ids: Mapping[str, str], parent_recipe_id: str | None = None,
    base_recipe_sha256: str | None = None,
    reserved_component_instances: Mapping[str, str] | None = None,
    reserved_modifier_instance_id: str | None = None,
) -> dict[str, Any]:
    if (
        strategy_template.get("template_id") != template.template_id
        or int(strategy_template.get("version") or 0) != template.version
    ):
        raise ValueError("strategy and Studio template identities must match at application time")
    component_instances: dict[str, str] = {}
    for component in template.document["components"]:
        role = component["element_role"]
        component_instances[component["key"]] = (
            _uuid7(str(reserved_component_instances[component["key"]]), component["key"])
            if reserved_component_instances is not None else
            (_uuid7(str(semantic_instance_ids[role]), role) if role is not None else new_uuid7())
        )
    return _materialize(
        template=template, strategy_template=strategy_template, slider_values=slider_values,
        binding_values=_binding_values(
            candidate=candidate, brief=brief, brand_document=brand_document,
            media_asset_id=media_asset_id,
        ),
        component_instances=component_instances,
        modifier_instance_id=reserved_modifier_instance_id or new_uuid7(),
        parent_recipe_id=parent_recipe_id, base_recipe_sha256=base_recipe_sha256,
    )


def replay_template_application(metadata: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema", "strategy_template", "studio_template", "catalog", "renderer",
        "template_snapshot", "slider_input", "slider_normalized", "component_instances",
        "modifier_instance_id", "bindings", "bindings_sha256", "component_patch",
        "patch_sha256", "components_sha256", "parent_recipe_id", "base_recipe_sha256",
    }
    if set(metadata) != expected or metadata.get("schema") != APPLICATION_SCHEMA:
        raise ValueError("template application metadata fields are invalid")
    template = _normalize_template(metadata["template_snapshot"])
    identity = metadata["studio_template"]
    if identity != {
        "template_id": template.template_id, "version": template.version, "sha256": template.digest,
    }:
        raise ValueError("Studio template snapshot identity or digest does not match")
    profile = _profile_for_placement(str(template.document["placement_tool_id"]))
    catalog = tool_catalog_for_profile(profile)
    if metadata["catalog"] != {
        "version": catalog["catalog_version"], "sha256": catalog["catalog_sha256"],
    } or metadata["renderer"] != renderer_identity(profile):
        raise ValueError("Studio catalog or renderer identity does not match application metadata")
    normalized = {name: int(metadata["slider_input"][name]) / 100 for name in SLIDER_NAMES}
    if metadata["slider_normalized"] != normalized:
        raise ValueError("Studio normalized slider metadata does not match exact inputs")
    bindings = metadata["bindings"]
    _, binding_digest = _canonical(bindings)
    _, patch_digest = _canonical(metadata["component_patch"])
    if binding_digest != metadata["bindings_sha256"] or patch_digest != metadata["patch_sha256"]:
        raise ValueError("Studio binding or patch digest does not match")
    values: dict[str, Any] = {}
    for binding in bindings:
        source = binding["source"]
        if source in values and values[source] != binding["value"]:
            raise ValueError("Studio replay binding values conflict")
        values[source] = binding["value"]
    replayed = _materialize(
        template=template, strategy_template=metadata["strategy_template"],
        slider_values=metadata["slider_input"], binding_values=values,
        component_instances=metadata["component_instances"],
        modifier_instance_id=metadata["modifier_instance_id"],
        parent_recipe_id=metadata["parent_recipe_id"],
        base_recipe_sha256=metadata["base_recipe_sha256"],
    )
    replay_metadata = replayed["modifiers"][0]["params"]
    if replay_metadata != metadata:
        raise ValueError("Studio template application metadata is not canonical or replayable")
    return replayed


def validate_template_application(
    *, submission: Mapping[str, Any], metadata: Mapping[str, Any], modifier_instance_id: str,
) -> None:
    replayed = replay_template_application(metadata)
    if replayed["modifiers"][0]["instance_id"] != modifier_instance_id:
        raise ValueError("Studio template modifier identity does not match its application metadata")
    if _canonical(replayed)[0] != _canonical(submission)[0]:
        raise ValueError("Studio recipe differs from its protected template application replay")
