"""Analytics authority and reviewed creative-performance learning."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
import threading
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from commander.ids import new_uuid7

from .landing_workspace import landing_catalog
from .local_brief_store import LocalBriefStore, utc_now
from .local_codex import sanitized
from .studio_phone_metrics import (
    PHONE_BACKGROUND_TEXTURES, PHONE_COMPONENTS, PHONE_COPY_BACKGROUND_TEXTURES,
    PHONE_SCREEN_TEXTURES,
)
from .studio_universal import COMPONENT_DEFINITIONS, UNIVERSAL_SETTING_DEFINITIONS


WINDOWS = {7, 30, 90, 0}
MILESTONE_HOURS = (24, 72, 168, 336, 720)
EVENT_TYPES = {"landing_view", "primary_cta_click", "contact_click"}
EVENT_SURFACES = {"page", "hero", "phone", "telegram", "instagram", "email"}
EVENT_TARGETS = {"page", "contacts", "telegram", "instagram", "email", "phone"}
VIEWPORTS = {"mobile", "tablet", "desktop"}
RULE_FAMILIES = {"ui", "copy", "image", "domain", "spirit"}
RULE_SURFACES = {"post", "landing", "both"}
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
DIGEST = re.compile(r"[0-9a-f]{64}")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _uuid(value: Any, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{field} must be a UUID") from error


def _timestamp(value: Any) -> datetime:
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return result if result.tzinfo else result.replace(tzinfo=timezone.utc)


def due_milestone(age_hours: int) -> int | None:
    """Return only a currently observable milestone, never a missed one."""
    return next((
        milestone for milestone in reversed(MILESTONE_HOURS)
        if milestone <= age_hours < milestone + 6
    ), None)


def comparison_age_band(age_hours: float) -> int:
    """Map a mature creative to the nearest bounded comparison cohort."""
    return 72 if age_hours < 168 else 168 if age_hours < 336 else 336 if age_hours < 720 else 720


def safe_landing_learning_content(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep visible copy while replacing contact endpoints with presence flags."""
    content = deepcopy(dict(value))
    contacts = dict(content.get("contacts") or {})
    channels = [
        channel for channel in ("url", "instagram", "email", "phone")
        if bool(str(contacts.get(channel) or "").strip())
    ]
    content["contacts"] = {
        key: contacts[key] for key in ("heading", "supporting_text") if key in contacts
    }
    content["contacts"]["available_channels"] = channels
    return content


def tracked_url(url: str, token: str) -> str:
    if not TOKEN.fullmatch(token):
        raise ValueError("attribution token is invalid")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise ValueError("published Landing URL is invalid")
    query = [(key, value) for key, value in parse_qsl(parts.query) if key != "ptw_attribution"]
    query.append(("ptw_attribution", token))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def _number(value: Any) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def normalized_outcomes(provider: str, metrics: Mapping[str, Any]) -> dict[str, float]:
    if provider == "instagram":
        views = _number(metrics.get("views") or metrics.get("reach") or metrics.get("impressions"))
        likes = _number(metrics.get("likes") or metrics.get("like_count"))
        comments = _number(metrics.get("comments") or metrics.get("comments_count"))
        shares = _number(metrics.get("shares") or metrics.get("shares_count"))
        saves = _number(metrics.get("saved") or metrics.get("saves"))
    else:
        views = _number(metrics.get("view_count"))
        likes = _number(metrics.get("like_count"))
        comments = _number(metrics.get("comment_count"))
        shares = _number(metrics.get("share_count"))
        saves = 0.0
    return {
        "views": views, "likes": likes, "comments": comments,
        "shares": shares, "saves": saves,
    }


def visual_descriptor_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "subject": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 80}, "maxItems": 8},
            "detail": {"type": "string", "enum": ["low", "medium", "high"]},
            "composition": {"type": "string", "enum": ["centered", "left_weighted", "right_weighted", "balanced", "full_bleed", "layered"]},
            "density": {"type": "string", "enum": ["sparse", "moderate", "dense"]},
            "palette": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 40}, "minItems": 1, "maxItems": 8},
            "contrast": {"type": "string", "enum": ["low", "medium", "high"]},
            "human_presence": {"type": "string", "enum": ["none", "silhouette", "person", "group"]},
        },
        "required": ["subject", "detail", "composition", "density", "palette", "contrast", "human_presence"],
        "additionalProperties": False,
    }


def validate_visual_descriptor(value: Mapping[str, Any]) -> dict[str, Any]:
    schema = visual_descriptor_schema()
    if set(value) != set(schema["required"]):
        raise ValueError("visual descriptor fields are invalid")
    result = {
        "subject": [" ".join(str(item).split()) for item in value["subject"]],
        "detail": str(value["detail"]), "composition": str(value["composition"]),
        "density": str(value["density"]),
        "palette": [" ".join(str(item).split()) for item in value["palette"]],
        "contrast": str(value["contrast"]), "human_presence": str(value["human_presence"]),
    }
    if not 0 <= len(result["subject"]) <= 8 or any(not 1 <= len(item) <= 80 for item in result["subject"]):
        raise ValueError("visual subjects are invalid")
    if not 1 <= len(result["palette"]) <= 8 or any(not 1 <= len(item) <= 40 for item in result["palette"]):
        raise ValueError("visual palette is invalid")
    for field in ("detail", "composition", "density", "contrast", "human_presence"):
        if result[field] not in schema["properties"][field]["enum"]:
            raise ValueError(f"visual {field} is invalid")
    return result


def learning_output_schema(scope: str) -> dict[str, Any]:
    families = ["spirit"] if scope == "global" else sorted(RULE_FAMILIES - {"spirit"})
    typed_value = {
        "anyOf": [
            {"type": "string"}, {"type": "number"}, {"type": "boolean"},
            {
                "type": "array", "maxItems": 24,
                "items": {"anyOf": [
                    {"type": "string"}, {"type": "number"}, {"type": "boolean"},
                ]},
            },
        ],
    }
    target = {
        "anyOf": [
            {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            {
                "type": "object",
                "properties": {"semantic_role": {"type": "string", "minLength": 1, "maxLength": 120}},
                "required": ["semantic_role"], "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {"asset_slot": {"type": "string", "minLength": 1, "maxLength": 120}},
                "required": ["asset_slot"], "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string", "minLength": 1, "maxLength": 120},
                    "component_id": {"type": "string", "minLength": 1, "maxLength": 160},
                    "setting_id": {"type": "string", "minLength": 1, "maxLength": 200},
                    "operation": {"type": "string", "enum": ["set", "prefer", "avoid"]},
                    "value": typed_value,
                },
                "required": ["template_id", "component_id", "setting_id", "operation", "value"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string", "minLength": 1, "maxLength": 120},
                    "component_id": {"type": "string", "minLength": 1, "maxLength": 160},
                    "setting_id": {"type": "string", "minLength": 1, "maxLength": 200},
                    "operation": {"type": "string", "enum": ["range"]},
                    "minimum": {"type": "number"}, "maximum": {"type": "number"},
                },
                "required": ["template_id", "component_id", "setting_id", "operation", "minimum", "maximum"],
                "additionalProperties": False,
            },
        ],
    }
    return {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array", "maxItems": 12,
                "items": {
                    "type": "object",
                    "properties": {
                        "surface": {"type": "string", "enum": sorted(RULE_SURFACES)},
                        "family": {"type": "string", "enum": families},
                        "instruction": {"type": "string", "minLength": 8, "maxLength": 1000},
                        "target": target,
                        "evidence": {
                            "type": "object",
                            "properties": {
                                "metric": {"type": "string", "minLength": 1, "maxLength": 120},
                                "summary": {"type": "string", "minLength": 1, "maxLength": 600},
                                "winning_item_indexes": {
                                    "type": "array", "minItems": 1, "maxItems": 24,
                                    "items": {"type": "integer", "minimum": 0},
                                },
                            },
                            "required": ["metric", "summary", "winning_item_indexes"],
                            "additionalProperties": False,
                        },
                        "confidence": {
                            "type": "object",
                            "properties": {
                                "level": {"type": "string", "enum": ["exploratory", "directional", "strong", "owner"]},
                                "sample_size": {"type": "integer", "minimum": 0},
                                "project_count": {"type": "integer", "minimum": 0},
                            },
                            "required": ["level", "sample_size", "project_count"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["surface", "family", "instruction", "target", "evidence", "confidence"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["candidates"], "additionalProperties": False,
    }


def _landing_ui_catalog() -> dict[tuple[str, str], dict[str, Any]]:
    definitions = landing_catalog().get("setting_definitions") or []
    return {(item["component_id"], item["setting_id"]): dict(item) for item in definitions}


def _post_ui_catalog() -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for component in COMPONENT_DEFINITIONS:
        for setting in component["setting_ids"]:
            definition = dict(UNIVERSAL_SETTING_DEFINITIONS.get(setting) or {"value_type": "structured"})
            result[("universal_ad", component["component_id"], setting)] = definition
    phone_enums = {
        "configuration.visual_mode": ["phone", "image"],
        "configuration.background.texture": list(PHONE_BACKGROUND_TEXTURES),
        "configuration.copy_background.texture": list(PHONE_COPY_BACKGROUND_TEXTURES),
        "configuration.phone_screen.texture": list(PHONE_SCREEN_TEXTURES),
    }
    phone_booleans = {
        "configuration.logo.enabled", "configuration.offer.enabled",
        "configuration.cta.enabled", "configuration.phone_screen.logo_enabled",
    }
    phone_colors = {
        "configuration.cta.background_color", "configuration.cta.text_color",
        "configuration.hero_title.highlight_color",
        "configuration.supporting_text.highlight_color",
    }
    for component in PHONE_COMPONENTS:
        for setting in component["setting_ids"]:
            if setting in phone_enums:
                definition = {"value_type": "enum", "values": phone_enums[setting]}
            elif setting in phone_booleans:
                definition = {"value_type": "boolean"}
            elif setting in phone_colors:
                definition = {"value_type": "color"}
            elif setting.startswith("content.") and setting not in {"content.stats", "content.phone_buttons"}:
                definition = {"value_type": "string"}
            else:
                definition = {"value_type": "structured"}
            result[("phone_metrics", component["component_id"], setting)] = definition
    return result


def _validate_typed_value(definition: Mapping[str, Any], target: Mapping[str, Any]) -> None:
    operation = target.get("operation")
    if operation not in {"set", "prefer", "avoid", "range"}:
        raise ValueError("UI rule operation is invalid")
    if operation == "range":
        if set(target) - {"template_id", "component_id", "setting_id", "operation", "minimum", "maximum"}:
            raise ValueError("UI range target fields are invalid")
        minimum, maximum = target.get("minimum"), target.get("maximum")
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in (minimum, maximum)) or minimum > maximum:
            raise ValueError("UI rule range is invalid")
        if definition.get("value_type") not in {"integer", "number"}:
            raise ValueError("UI range is allowed only for numeric settings")
        if definition.get("minimum") is not None and minimum < definition["minimum"]:
            raise ValueError("UI rule range is below the catalog minimum")
        if definition.get("maximum") is not None and maximum > definition["maximum"]:
            raise ValueError("UI rule range is above the catalog maximum")
        return
    if set(target) - {"template_id", "component_id", "setting_id", "operation", "value"}:
        raise ValueError("UI value target fields are invalid")
    if "value" not in target:
        raise ValueError("UI rule value is required")
    value_type = definition.get("value_type")
    value = target["value"]
    if value_type == "boolean" and not isinstance(value, bool):
        raise ValueError("UI rule value must be boolean")
    if value_type in {"integer", "number"} and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise ValueError("UI rule value must be numeric")
    if value_type in {"color", "enum"} and not isinstance(value, str):
        raise ValueError("UI rule value must be text")
    if value_type == "color" and not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("UI rule color must be six-digit hex")
    if value_type == "string" and not isinstance(value, str):
        raise ValueError("UI rule value must be text")
    if value_type == "structured" and not isinstance(value, (dict, list)):
        raise ValueError("UI rule value must be structured JSON")
    if value_type == "structured" and len(_canonical(value)) > 4000:
        raise ValueError("UI rule structured value is too large")
    if definition.get("values") and value not in definition["values"]:
        raise ValueError("UI rule value is outside the catalog")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if definition.get("minimum") is not None and value < definition["minimum"]:
            raise ValueError("UI rule value is below the catalog minimum")
        if definition.get("maximum") is not None and value > definition["maximum"]:
            raise ValueError("UI rule value is above the catalog maximum")


def normalize_rule(value: Mapping[str, Any], *, scope: str, project_id: str | None) -> dict[str, Any]:
    allowed = {"rule_id", "surface", "family", "instruction", "target", "evidence", "confidence", "active", "tombstone"}
    if set(value) - allowed:
        raise ValueError("creative skill rule fields are invalid")
    family, surface = str(value.get("family") or ""), str(value.get("surface") or "")
    if family not in RULE_FAMILIES or surface not in RULE_SURFACES:
        raise ValueError("creative skill family or surface is invalid")
    if scope == "global" and family != "spirit":
        raise ValueError("global creative skills accept spirit principles only")
    if scope == "project" and family == "spirit":
        raise ValueError("spirit principles belong to the global skill")
    instruction = " ".join(str(value.get("instruction") or "").split())
    if not 8 <= len(instruction) <= 1000:
        raise ValueError("creative skill instruction must contain 8-1000 characters")
    target = dict(value.get("target") or {})
    if family == "ui":
        if surface == "both":
            raise ValueError("UI rules require one exact post or landing surface")
        required = {"template_id", "component_id", "setting_id", "operation"}
        if not required <= set(target):
            raise ValueError("UI rule requires an exact catalog target")
        template = str(target["template_id"])
        key = (template, str(target["component_id"]), str(target["setting_id"]))
        if template == "project_landing":
            definition = _landing_ui_catalog().get((key[1], key[2]))
        else:
            definition = _post_ui_catalog().get(key)
        if definition is None:
            raise ValueError("UI rule target does not exist in the live catalog")
        if (surface == "post" and template == "project_landing") or (surface == "landing" and template != "project_landing"):
            raise ValueError("UI rule target conflicts with its surface")
        _validate_typed_value(definition, target)
    elif family == "copy":
        if surface == "both":
            raise ValueError("copy rules require one exact post or landing semantic role")
        semantic_role = str(target.get("semantic_role") or "")
        post_roles = {str(item["role"]) for item in (*COMPONENT_DEFINITIONS, *PHONE_COMPONENTS)}
        landing_roles = {str(item["role"]) for item in landing_catalog()["components"]}
        allowed_roles = post_roles if surface == "post" else landing_roles
        if set(target) != {"semantic_role"} or semantic_role not in allowed_roles:
            raise ValueError("copy rule requires one bounded semantic_role")
    elif family == "image":
        if surface == "both":
            raise ValueError("image rules require one exact post or landing asset slot")
        asset_slot = str(target.get("asset_slot") or "")
        post_slots = {
            str(slot) for item in (*COMPONENT_DEFINITIONS, *PHONE_COMPONENTS)
            for slot in item["asset_slot_ids"]
        }
        landing_slots = {str(slot) for slot in landing_catalog()["visual_slots"]}
        allowed_slots = post_slots if surface == "post" else landing_slots
        if set(target) != {"asset_slot"} or asset_slot not in allowed_slots:
            raise ValueError("image rule requires one bounded asset_slot")
    elif target:
        raise ValueError("domain and spirit rules do not accept implementation targets")
    evidence, confidence = dict(value.get("evidence") or {}), dict(value.get("confidence") or {})
    sample_size = confidence.get("sample_size", 0)
    if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 0:
        raise ValueError("creative skill confidence sample_size is invalid")
    level = confidence.get("level", "owner")
    if level not in {"exploratory", "directional", "strong", "owner"}:
        raise ValueError("creative skill confidence level is invalid")
    project_count = confidence.get("project_count", 0 if scope == "global" else 1)
    if isinstance(project_count, bool) or not isinstance(project_count, int) or project_count < 0:
        raise ValueError("creative skill confidence project_count is invalid")
    return {
        "rule_id": _uuid(value.get("rule_id") or new_uuid7(), "rule_id"),
        "scope": scope, "project_id": project_id, "surface": surface,
        "family": family, "instruction": instruction, "target": target,
        "evidence": sanitized(evidence),
        "confidence": {
            **sanitized(confidence), "sample_size": sample_size,
            "project_count": project_count, "level": level,
        },
        "active": bool(value.get("active", True)) and not bool(value.get("tombstone", False)),
        "tombstone": bool(value.get("tombstone", False)),
    }


def _rules_conflict(rules: Sequence[Mapping[str, Any]]) -> bool:
    seen: set[str] = set()
    for rule in rules:
        if not rule.get("active"):
            continue
        applied_surfaces = ("post", "landing") if rule["surface"] == "both" else (rule["surface"],)
        for applied_surface in applied_surfaces:
            if rule["family"] == "ui":
                key = _canonical({"surface": applied_surface, "family": "ui", "target": rule["target"] | {"operation": None, "value": None, "minimum": None, "maximum": None}})
            elif rule["family"] in {"copy", "image"}:
                key = _canonical({"surface": applied_surface, "family": rule["family"], "target": rule["target"]})
            else:
                continue
            if key in seen:
                return True
            seen.add(key)
    return False


class LocalCreativeAnalyticsAuthority:
    def __init__(self, store: LocalBriefStore) -> None:
        self.store = store
        self._lock = threading.RLock()

    def project_ids(self) -> list[str]:
        return [str(item["project_id"]) for item in self.store.list("projects")]

    def attribution_for_source(self, source_entity_id: str) -> dict[str, Any] | None:
        return next((item for item in self.store.list("creative_attribution_sources") if item["source_entity_id"] == source_entity_id), None)

    def attribution_for_token(self, token: str) -> dict[str, Any] | None:
        return next((item for item in self.store.list("creative_attribution_sources") if item["token"] == token), None)

    def register_attribution(self, value: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            previous = self.attribution_for_source(str(value["source_entity_id"]))
            if previous:
                if previous["token_sha256"] != value["token_sha256"]:
                    raise ValueError("publication already has a different attribution token")
                return previous
            record = {**deepcopy(dict(value)), "attribution_source_id": new_uuid7(), "created_at": utc_now()}
            self.store.append("creative_attribution_sources", record["attribution_source_id"], record)
            self.store.edge(source_id=record["source_entity_id"], relation="contains", target_id=record["attribution_source_id"], evidence={"member": "creative_attribution_source"})
            return record

    def record_insight(self, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        previous = next((item for item in self.store.list("creative_insight_snapshots") if item["capture_key"] == value["capture_key"]), None)
        if previous:
            return previous, False
        record = {**deepcopy(dict(value)), "insight_id": new_uuid7(), "created_at": utc_now()}
        self.store.append("creative_insight_snapshots", record["insight_id"], record)
        self.store.edge(source_id=record["source_entity_id"], relation="contains", target_id=record["insight_id"], evidence={"member": "creative_insight_snapshot"})
        return record, True

    def list_insights(self, project_ids: Sequence[str]) -> list[dict[str, Any]]:
        selected = set(project_ids)
        return [item for item in self.store.list("creative_insight_snapshots") if item["project_id"] in selected]

    def event_input(self, event_id: str) -> str | None:
        try:
            return str(self.store.get("landing_analytics_events", event_id)["input_sha256"])
        except KeyError:
            return None

    def record_event(self, context: Mapping[str, Any], payload: Mapping[str, Any], attribution_id: str | None) -> tuple[dict[str, Any], bool]:
        event_id = str(payload["event_id"])
        try:
            prior = self.store.get("landing_analytics_events", event_id)
            if prior["input_sha256"] != payload["input_sha256"]:
                raise ValueError("event_id was reused with different analytics input")
            return prior, False
        except KeyError:
            pass
        record = {**deepcopy(dict(payload)), **deepcopy(dict(context)), "attribution_source_id": attribution_id, "created_at": utc_now()}
        self.store.append("landing_analytics_events", event_id, record)
        dimensions = (record["project_id"], record["landing_version_id"], record["event_type"], record["surface"], record["target"], attribution_id, record["created_at"][:10])
        previous = [item for item in self.store.list("landing_analytics_rollups") if (item["project_id"], item["landing_version_id"], item["event_type"], item["surface"], item["target"], item.get("attribution_source_id"), item["day"]) == dimensions]
        rollup = {key: record[key] for key in ("project_id", "landing_publication_event_id", "landing_version_id", "landing_version_sha256", "event_type", "surface", "target")}
        rollup.update({"rollup_id": new_uuid7(), "day": record["created_at"][:10], "attribution_source_id": attribution_id, "cumulative_count": max((int(item["cumulative_count"]) for item in previous), default=0) + 1, "source_event_id": event_id, "created_at": utc_now()})
        self.store.append("landing_analytics_rollups", rollup["rollup_id"], rollup)
        self.store.edge(source_id=record["landing_publication_event_id"], relation="contains", target_id=rollup["rollup_id"], evidence={"member": "landing_analytics_rollup_snapshot"})
        return record, True

    def list_rollups(self, project_ids: Sequence[str], cutoff: datetime | None) -> list[dict[str, Any]]:
        selected = set(project_ids)
        values = [item for item in self.store.list("landing_analytics_rollups") if item["project_id"] in selected and (cutoff is None or _timestamp(item["day"] + "T00:00:00+00:00") >= cutoff)]
        latest: dict[str, dict[str, Any]] = {}
        for item in values:
            key = _canonical({field: item.get(field) for field in ("project_id", "landing_version_id", "day", "event_type", "surface", "target", "attribution_source_id")})
            if key not in latest or _timestamp(item["created_at"]) > _timestamp(latest[key]["created_at"]):
                latest[key] = item
        return list(latest.values())

    def descriptor(self, artifact_sha256: str) -> dict[str, Any] | None:
        return next((item for item in self.store.list("creative_visual_descriptors") if item["artifact_sha256"] == artifact_sha256), None)

    def record_descriptor(self, value: Mapping[str, Any]) -> dict[str, Any]:
        previous = self.descriptor(str(value["artifact_sha256"]))
        if previous:
            self.bind_descriptor(
                previous["visual_descriptor_id"], str(value["source_version_id"]),
                str(value["project_id"]),
            )
            return previous
        record = {**deepcopy(dict(value)), "visual_descriptor_id": new_uuid7(), "created_at": utc_now()}
        self.store.append("creative_visual_descriptors", record["visual_descriptor_id"], record)
        self.bind_descriptor(
            record["visual_descriptor_id"], record["source_version_id"], record["project_id"],
        )
        return record

    def bind_descriptor(self, descriptor_id: str, source_version_id: str, project_id: str) -> None:
        key = f"{descriptor_id}:{source_version_id}"
        if not any(item.get("descriptor_source_id") == key for item in self.store.list("creative_visual_descriptor_sources")):
            self.store.append("creative_visual_descriptor_sources", key, {
                "descriptor_source_id": key, "visual_descriptor_id": descriptor_id,
                "source_version_id": source_version_id, "project_id": project_id,
                "created_at": utc_now(),
            })
            self.store.edge(source_id=source_version_id, relation="contains", target_id=descriptor_id, evidence={"member": "creative_visual_descriptor"})

    def create_learning_run(self, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        previous = next((item for item in self.store.list("creative_learning_runs") if item["request_id"] == value["request_id"]), None)
        if previous:
            if previous["request_sha256"] != value["request_sha256"]:
                raise ValueError("learning request_id was reused with different input")
            return previous, False
        record = {**deepcopy(dict(value)), "learning_run_id": new_uuid7(), "created_at": utc_now(), "completed_at": None}
        self.store.append("creative_learning_runs", record["learning_run_id"], record)
        return record, True

    def update_learning_run(self, run_id: str, **patch: Any) -> dict[str, Any]:
        record = {**self.get_learning_run(run_id), **deepcopy(patch)}
        self.store.append("creative_learning_runs", run_id, record)
        return record

    def get_learning_run(self, run_id: str) -> dict[str, Any]:
        return self.store.get("creative_learning_runs", _uuid(run_id, "learning_run_id"))

    def list_learning_runs(self, scope: str, project_id: str | None) -> list[dict[str, Any]]:
        return [item for item in self.store.list("creative_learning_runs") if item["scope"] == scope and item.get("project_id") == project_id]

    def latest_skill(self, scope: str, project_id: str | None) -> dict[str, Any] | None:
        items = [item for item in self.store.list("creative_skill_snapshots") if item["scope"] == scope and item.get("project_id") == project_id]
        return max(items, key=lambda item: int(item["version"])) if items else None

    def append_skill(self, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        previous_request = next((item for item in self.store.list("creative_skill_snapshots") if item["request_id"] == value["request_id"]), None)
        if previous_request:
            if previous_request["rules_sha256"] != value["rules_sha256"]:
                raise ValueError("skill request_id was reused with different input")
            return previous_request, False
        previous = self.latest_skill(str(value["scope"]), value.get("project_id"))
        record = {**deepcopy(dict(value)), "skill_snapshot_id": new_uuid7(), "version": 1 if previous is None else int(previous["version"]) + 1, "created_at": utc_now()}
        self.store.append("creative_skill_snapshots", record["skill_snapshot_id"], record)
        return record, True

    def decision(self, run_id: str) -> dict[str, Any] | None:
        return next((item for item in self.store.list("creative_learning_decisions") if item["learning_run_id"] == run_id), None)

    def record_decision(self, value: Mapping[str, Any]) -> dict[str, Any]:
        previous = self.decision(str(value["learning_run_id"]))
        if previous:
            if previous["request_id"] != value["request_id"] or previous["request_sha256"] != value["request_sha256"]:
                raise ValueError("learning run already has a decision")
            return previous
        reused = next((item for item in self.store.list("creative_learning_decisions") if item["request_id"] == value["request_id"]), None)
        if reused:
            raise ValueError("learning decision request_id was reused")
        record = {**deepcopy(dict(value)), "decision_id": new_uuid7(), "created_at": utc_now()}
        self.store.append("creative_learning_decisions", record["decision_id"], record)
        return record

    def purge_events(self) -> int:
        # Local append-only fixtures deliberately retain their tiny event set.
        return 0


class DatabaseCreativeAnalyticsAuthority:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            with connection.transaction():
                yield connection

    @staticmethod
    def _edge(connection: Any, source: str, relation: str, target: str, attributes: Mapping[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        connection.execute("INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes) VALUES(%s,%s,%s,%s,%s)", (UUID(new_uuid7()), UUID(source), relation, UUID(target), Jsonb(dict(attributes))))

    def project_ids(self) -> list[str]:
        with self.connection() as connection:
            rows = connection.execute("SELECT entity_id FROM validation_projects ORDER BY created_at").fetchall()
        return [str(row[0]) for row in rows]

    @staticmethod
    def _attribution(row: Sequence[Any]) -> dict[str, Any]:
        return {"attribution_source_id": str(row[0]), "token": row[1], "token_sha256": row[2], "project_id": str(row[3]), "channel": row[4], "provider": row[5], "source_entity_id": str(row[6]), "landing_publication_id": str(row[7]), "landing_publication_event_id": str(row[8]), "created_at": row[9].isoformat()}

    _attribution_select = "SELECT entity_id,token,token_sha256,project_id,channel,provider,source_entity_id,landing_publication_id,landing_publication_event_id,created_at FROM creative_attribution_sources"

    def attribution_for_source(self, source_entity_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(self._attribution_select + " WHERE source_entity_id=%s", (UUID(source_entity_id),)).fetchone()
        return None if row is None else self._attribution(row)

    def attribution_for_token(self, token: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(self._attribution_select + " WHERE token=%s", (token,)).fetchone()
        return None if row is None else self._attribution(row)

    def register_attribution(self, value: Mapping[str, Any]) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        source_id, attribution_id = UUID(str(value["source_entity_id"])), UUID(new_uuid7())
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"creative-attribution:{source_id}",))
            row = connection.execute(self._attribution_select + " WHERE source_entity_id=%s", (source_id,)).fetchone()
            if row:
                prior = self._attribution(row)
                if prior["token_sha256"] != value["token_sha256"]:
                    raise ValueError("publication already has a different attribution token")
                return prior
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_attribution_source',%s)", (attribution_id, Jsonb({"channel": value["channel"], "provider": value["provider"]})))
            connection.execute("INSERT INTO creative_attribution_sources(entity_id,token,token_sha256,project_id,channel,provider,source_entity_id,landing_publication_id,landing_publication_event_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)", (attribution_id, value["token"], value["token_sha256"], UUID(str(value["project_id"])), value["channel"], value["provider"], source_id, UUID(str(value["landing_publication_id"])), UUID(str(value["landing_publication_event_id"]))))
            self._edge(connection, str(source_id), "contains", str(attribution_id), {"member": "creative_attribution_source"})
        return self.attribution_for_source(str(source_id))  # type: ignore[return-value]

    @staticmethod
    def _insight(row: Sequence[Any]) -> dict[str, Any]:
        return {"insight_id": str(row[0]), "project_id": str(row[1]), "source_entity_id": str(row[2]), "provider": row[3], "capture_kind": row[4], "milestone_hours": row[5], "capture_key": row[6], "source_published_at": row[7].isoformat(), "metrics": dict(row[8]), "created_at": row[9].isoformat()}

    _insight_select = "SELECT entity_id,project_id,source_entity_id,provider,capture_kind,milestone_hours,capture_key,source_published_at,metrics,created_at FROM creative_insight_snapshots"

    def record_insight(self, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            row = connection.execute(self._insight_select + " WHERE capture_key=%s", (value["capture_key"],)).fetchone()
            if row:
                return self._insight(row), False
            identifier = UUID(new_uuid7())
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_insight_snapshot',%s)", (identifier, Jsonb({"provider": value["provider"], "capture_kind": value["capture_kind"]})))
            connection.execute("INSERT INTO creative_insight_snapshots(entity_id,project_id,source_entity_id,provider,capture_kind,milestone_hours,capture_key,source_published_at,metrics) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)", (identifier, UUID(str(value["project_id"])), UUID(str(value["source_entity_id"])), value["provider"], value["capture_kind"], value.get("milestone_hours"), value["capture_key"], value["source_published_at"], Jsonb(dict(value["metrics"]))))
            self._edge(connection, str(value["source_entity_id"]), "contains", str(identifier), {"member": "creative_insight_snapshot", "capture_kind": value["capture_kind"]})
        with self.connection() as connection:
            row = connection.execute(self._insight_select + " WHERE entity_id=%s", (identifier,)).fetchone()
        return self._insight(row), True

    def list_insights(self, project_ids: Sequence[str]) -> list[dict[str, Any]]:
        if not project_ids:
            return []
        with self.connection() as connection:
            rows = connection.execute(self._insight_select + " WHERE project_id=ANY(%s) ORDER BY created_at DESC", ([UUID(item) for item in project_ids],)).fetchall()
        return [self._insight(row) for row in rows]

    def event_input(self, event_id: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT input_sha256 FROM landing_analytics_events WHERE event_id=%s",
                (UUID(event_id),),
            ).fetchone()
        return None if row is None else str(row[0])

    def record_event(self, context: Mapping[str, Any], payload: Mapping[str, Any], attribution_id: str | None) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        event_id = UUID(str(payload["event_id"]))
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"landing-analytics-event:{event_id}",))
            prior = connection.execute("SELECT input_sha256 FROM landing_analytics_events WHERE event_id=%s", (event_id,)).fetchone()
            if prior:
                if prior[0] != payload["input_sha256"]:
                    raise ValueError("event_id was reused with different analytics input")
                return {**dict(payload), **dict(context), "attribution_source_id": attribution_id}, False
            connection.execute("INSERT INTO landing_analytics_events(event_id,visit_id,project_id,landing_publication_id,landing_publication_event_id,landing_version_id,landing_version_sha256,input_sha256,event_type,surface,target,attribution_source_id,viewport_class) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (event_id, UUID(str(payload["visit_id"])), UUID(str(context["project_id"])), UUID(str(context["landing_publication_id"])), UUID(str(context["landing_publication_event_id"])), UUID(str(context["landing_version_id"])), context["landing_version_sha256"], payload["input_sha256"], payload["event_type"], payload["surface"], payload["target"], None if attribution_id is None else UUID(attribution_id), payload["viewport_class"]))
            dimensions = (UUID(str(context["project_id"])), UUID(str(context["landing_version_id"])), payload["event_type"], payload["surface"], payload["target"], None if attribution_id is None else UUID(attribution_id))
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("landing-analytics-rollup:" + ":".join(str(item) for item in dimensions),))
            prior_count = connection.execute("SELECT cumulative_count FROM landing_analytics_rollup_snapshots WHERE project_id=%s AND landing_version_id=%s AND day=current_date AND event_type=%s AND surface=%s AND target=%s AND attribution_source_id IS NOT DISTINCT FROM %s ORDER BY created_at DESC LIMIT 1", dimensions).fetchone()
            rollup_id = UUID(new_uuid7())
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'landing_analytics_rollup_snapshot',%s)", (rollup_id, Jsonb({"event_type": payload["event_type"], "day": datetime.now(timezone.utc).date().isoformat()})))
            connection.execute("INSERT INTO landing_analytics_rollup_snapshots(entity_id,project_id,landing_publication_event_id,landing_version_id,landing_version_sha256,day,event_type,surface,target,attribution_source_id,cumulative_count,source_event_id) VALUES(%s,%s,%s,%s,%s,current_date,%s,%s,%s,%s,%s,%s)", (rollup_id, UUID(str(context["project_id"])), UUID(str(context["landing_publication_event_id"])), UUID(str(context["landing_version_id"])), context["landing_version_sha256"], payload["event_type"], payload["surface"], payload["target"], None if attribution_id is None else UUID(attribution_id), (int(prior_count[0]) if prior_count else 0) + 1, event_id))
            self._edge(connection, str(context["landing_publication_event_id"]), "contains", str(rollup_id), {"member": "landing_analytics_rollup_snapshot"})
        return {**dict(payload), **dict(context), "attribution_source_id": attribution_id}, True

    def list_rollups(self, project_ids: Sequence[str], cutoff: datetime | None) -> list[dict[str, Any]]:
        if not project_ids:
            return []
        condition = " AND day >= %s" if cutoff else ""
        params: list[Any] = [[UUID(item) for item in project_ids]]
        if cutoff:
            params.append(cutoff.date())
        query = """SELECT DISTINCT ON (project_id,landing_version_id,day,event_type,surface,target,attribution_source_id)
                    entity_id,project_id,landing_publication_event_id,landing_version_id,landing_version_sha256,
                    day,event_type,surface,target,attribution_source_id,cumulative_count,source_event_id,created_at
                   FROM landing_analytics_rollup_snapshots WHERE project_id=ANY(%s)""" + condition + " ORDER BY project_id,landing_version_id,day,event_type,surface,target,attribution_source_id,created_at DESC"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [{"rollup_id": str(row[0]), "project_id": str(row[1]), "landing_publication_event_id": str(row[2]), "landing_version_id": str(row[3]), "landing_version_sha256": row[4], "day": row[5].isoformat(), "event_type": row[6], "surface": row[7], "target": row[8], "attribution_source_id": None if row[9] is None else str(row[9]), "cumulative_count": int(row[10]), "source_event_id": str(row[11]), "created_at": row[12].isoformat()} for row in rows]

    def descriptor(self, artifact_sha256: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT entity_id,artifact_sha256,source_version_id,project_id,descriptor,descriptor_sha256,provider,created_at FROM creative_visual_descriptors WHERE artifact_sha256=%s", (artifact_sha256,)).fetchone()
        return None if row is None else {"visual_descriptor_id": str(row[0]), "artifact_sha256": row[1], "source_version_id": str(row[2]), "project_id": str(row[3]), "descriptor": dict(row[4]), "descriptor_sha256": row[5], "provider": dict(row[6]), "created_at": row[7].isoformat()}

    def record_descriptor(self, value: Mapping[str, Any]) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        previous = self.descriptor(str(value["artifact_sha256"]))
        if previous:
            self.bind_descriptor(
                previous["visual_descriptor_id"], str(value["source_version_id"]),
                str(value["project_id"]),
            )
            return previous
        identifier = UUID(new_uuid7())
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_visual_descriptor',%s)", (identifier, Jsonb({"artifact_sha256": value["artifact_sha256"]})))
            connection.execute("INSERT INTO creative_visual_descriptors(entity_id,artifact_sha256,source_version_id,project_id,descriptor,descriptor_sha256,provider) VALUES(%s,%s,%s,%s,%s,%s,%s)", (identifier, value["artifact_sha256"], UUID(str(value["source_version_id"])), UUID(str(value["project_id"])), Jsonb(dict(value["descriptor"])), value["descriptor_sha256"], Jsonb(dict(value.get("provider") or {}))))
        self.bind_descriptor(str(identifier), str(value["source_version_id"]), str(value["project_id"]))
        return self.descriptor(str(value["artifact_sha256"]))  # type: ignore[return-value]

    def bind_descriptor(self, descriptor_id: str, source_version_id: str, project_id: str) -> None:
        with self.connection() as connection:
            created = connection.execute(
                "INSERT INTO creative_visual_descriptor_sources(descriptor_id,source_version_id,project_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (UUID(descriptor_id), UUID(source_version_id), UUID(project_id)),
            ).rowcount
            if created:
                self._edge(connection, source_version_id, "contains", descriptor_id, {"member": "creative_visual_descriptor"})

    @staticmethod
    def _learning(row: Sequence[Any]) -> dict[str, Any]:
        return {"learning_run_id": str(row[0]), "request_id": str(row[1]), "request_sha256": row[2], "scope": row[3], "project_id": None if row[4] is None else str(row[4]), "surface": row[5], "status": row[6], "dataset": dict(row[7]), "dataset_sha256": row[8], "candidates": list(row[9]), "provider": dict(row[10]), "error_type": row[11], "error_message": row[12], "created_at": row[13].isoformat(), "completed_at": None if row[14] is None else row[14].isoformat()}

    _learning_select = "SELECT entity_id,request_id,request_sha256,scope,project_id,surface,status,dataset,dataset_sha256,candidates,provider,error_type,error_message,created_at,completed_at FROM creative_learning_runs"

    def create_learning_run(self, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            row = connection.execute(self._learning_select + " WHERE request_id=%s", (UUID(str(value["request_id"])),)).fetchone()
            if row:
                prior = self._learning(row)
                if prior["request_sha256"] != value["request_sha256"]:
                    raise ValueError("learning request_id was reused with different input")
                return prior, False
            identifier = UUID(new_uuid7())
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_learning_run',%s)", (identifier, Jsonb({"scope": value["scope"], "surface": value["surface"]})))
            connection.execute("INSERT INTO creative_learning_runs(entity_id,request_id,request_sha256,scope,project_id,surface,status,dataset,dataset_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)", (identifier, UUID(str(value["request_id"])), value["request_sha256"], value["scope"], None if value.get("project_id") is None else UUID(str(value["project_id"])), value["surface"], value["status"], Jsonb(dict(value["dataset"])), value["dataset_sha256"]))
        return self.get_learning_run(str(identifier)), True

    def update_learning_run(self, run_id: str, **patch: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        allowed = {"status", "candidates", "provider", "error_type", "error_message", "completed_at"}
        if set(patch) - allowed:
            raise ValueError("learning run update is invalid")
        assignments, values = [], []
        for key, value in patch.items():
            assignments.append(f"{key}=%s")
            values.append(Jsonb(value) if key in {"candidates", "provider"} else value)
        values.append(UUID(run_id))
        with self.connection() as connection:
            connection.execute(f"UPDATE creative_learning_runs SET {','.join(assignments)} WHERE entity_id=%s", values)
        return self.get_learning_run(run_id)

    def get_learning_run(self, run_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(self._learning_select + " WHERE entity_id=%s", (UUID(run_id),)).fetchone()
        if row is None:
            raise KeyError("creative learning run was not found")
        return self._learning(row)

    def list_learning_runs(self, scope: str, project_id: str | None) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(self._learning_select + " WHERE scope=%s AND project_id IS NOT DISTINCT FROM %s ORDER BY created_at DESC LIMIT 50", (scope, None if project_id is None else UUID(project_id))).fetchall()
        return [self._learning(row) for row in rows]

    @staticmethod
    def _skill(row: Sequence[Any]) -> dict[str, Any]:
        return {"skill_snapshot_id": str(row[0]), "request_id": str(row[1]), "scope": row[2], "project_id": None if row[3] is None else str(row[3]), "version": int(row[4]), "rules": list(row[5]), "rules_sha256": row[6], "source_learning_run_id": None if row[7] is None else str(row[7]), "requested_by": row[8], "created_at": row[9].isoformat()}

    _skill_select = "SELECT entity_id,request_id,scope,project_id,version,rules,rules_sha256,source_learning_run_id,requested_by,created_at FROM creative_skill_snapshots"

    def latest_skill(self, scope: str, project_id: str | None) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(self._skill_select + " WHERE scope=%s AND project_id IS NOT DISTINCT FROM %s ORDER BY version DESC LIMIT 1", (scope, None if project_id is None else UUID(project_id))).fetchone()
        return None if row is None else self._skill(row)

    def append_skill(self, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"creative-skill:{value['scope']}:{value.get('project_id')}",))
            row = connection.execute(self._skill_select + " WHERE request_id=%s", (UUID(str(value["request_id"])),)).fetchone()
            if row:
                prior = self._skill(row)
                if prior["rules_sha256"] != value["rules_sha256"]:
                    raise ValueError("skill request_id was reused with different input")
                return prior, False
            previous = connection.execute("SELECT COALESCE(max(version),0) FROM creative_skill_snapshots WHERE scope=%s AND project_id IS NOT DISTINCT FROM %s", (value["scope"], None if value.get("project_id") is None else UUID(str(value["project_id"])))).fetchone()[0]
            identifier = UUID(new_uuid7())
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_skill_snapshot',%s)", (identifier, Jsonb({"scope": value["scope"], "version": int(previous) + 1})))
            connection.execute("INSERT INTO creative_skill_snapshots(entity_id,request_id,scope,project_id,version,rules,rules_sha256,source_learning_run_id,requested_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)", (identifier, UUID(str(value["request_id"])), value["scope"], None if value.get("project_id") is None else UUID(str(value["project_id"])), int(previous) + 1, Jsonb(list(value["rules"])), value["rules_sha256"], None if value.get("source_learning_run_id") is None else UUID(str(value["source_learning_run_id"])), value["requested_by"]))
            if value.get("project_id"):
                self._edge(connection, str(value["project_id"]), "contains", str(identifier), {"member": "creative_skill_snapshot"})
            if value.get("source_learning_run_id"):
                self._edge(connection, str(identifier), "derived_from", str(value["source_learning_run_id"]), {"input": "reviewed_performance_learning"})
        return self.latest_skill(str(value["scope"]), value.get("project_id")), True  # type: ignore[return-value]

    def decision(self, run_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT entity_id,request_id,request_sha256,learning_run_id,decision,selected_rules,skill_snapshot_id,requested_by,created_at FROM creative_learning_decisions WHERE learning_run_id=%s", (UUID(run_id),)).fetchone()
        return None if row is None else {"decision_id": str(row[0]), "request_id": str(row[1]), "request_sha256": row[2], "learning_run_id": str(row[3]), "decision": row[4], "selected_rules": list(row[5]), "skill_snapshot_id": None if row[6] is None else str(row[6]), "requested_by": row[7], "created_at": row[8].isoformat()}

    def record_decision(self, value: Mapping[str, Any]) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"creative-learning-decision:{value['learning_run_id']}",),
            )
            row = connection.execute(
                "SELECT entity_id,request_id,request_sha256,learning_run_id,decision,selected_rules,skill_snapshot_id,requested_by,created_at FROM creative_learning_decisions WHERE learning_run_id=%s",
                (UUID(str(value["learning_run_id"])),),
            ).fetchone()
            if row:
                previous = {
                    "decision_id": str(row[0]), "request_id": str(row[1]),
                    "request_sha256": row[2], "learning_run_id": str(row[3]),
                    "decision": row[4], "selected_rules": list(row[5]),
                    "skill_snapshot_id": None if row[6] is None else str(row[6]),
                    "requested_by": row[7], "created_at": row[8].isoformat(),
                }
                if previous["request_id"] != value["request_id"] or previous["request_sha256"] != value["request_sha256"]:
                    raise ValueError("learning run already has a decision")
                return previous
            reused = connection.execute(
                "SELECT 1 FROM creative_learning_decisions WHERE request_id=%s",
                (UUID(str(value["request_id"])),),
            ).fetchone()
            if reused:
                raise ValueError("learning decision request_id was reused")
            identifier = UUID(new_uuid7())
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'creative_learning_decision',%s)", (identifier, Jsonb({"decision": value["decision"]})))
            connection.execute("INSERT INTO creative_learning_decisions(entity_id,request_id,request_sha256,learning_run_id,decision,selected_rules,skill_snapshot_id,requested_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", (identifier, UUID(str(value["request_id"])), value["request_sha256"], UUID(str(value["learning_run_id"])), value["decision"], Jsonb(list(value["selected_rules"])), None if value.get("skill_snapshot_id") is None else UUID(str(value["skill_snapshot_id"])), value["requested_by"]))
            self._edge(connection, str(value["learning_run_id"]), "contains", str(identifier), {"member": "creative_learning_decision"})
        return self.decision(str(value["learning_run_id"]))  # type: ignore[return-value]

    def purge_events(self) -> int:
        with self.connection() as connection:
            result = connection.execute("DELETE FROM landing_analytics_events WHERE created_at < clock_timestamp() - interval '90 days'")
            return int(result.rowcount)


class CreativeAnalyticsService:
    """Combine provider snapshots, cookieless funnel data and reviewed rules."""

    def __init__(
        self, authority: Any, *, studio: Any, landing_pages: Any,
        landing_publications: Any, meta_ads: Any, structured_provider: Any | None,
        performance_skill_path: Path, visual_skill_path: Path,
        instagram: Any | None = None, tiktok: Any | None = None,
    ) -> None:
        self.authority, self.studio, self.landing_pages = authority, studio, landing_pages
        self.landing_publications, self.meta_ads = landing_publications, meta_ads
        self.structured_provider = structured_provider
        self.performance_skill = performance_skill_path.read_text(encoding="utf-8")
        self.visual_skill = visual_skill_path.read_text(encoding="utf-8")
        self.instagram, self.tiktok = instagram, tiktok
        self._event_lock = threading.RLock()
        self._decision_lock = threading.RLock()
        self._event_buckets: dict[str, list[datetime]] = {}
        self._event_route_buckets: dict[str, list[datetime]] = {}

    @staticmethod
    def prepare_attribution(landing: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not landing:
            return None
        token = secrets.token_urlsafe(32)
        return {"token": token, "token_sha256": hashlib.sha256(token.encode()).hexdigest(), "tracked_url": tracked_url(str(landing["canonical_url"]), token)}

    def register_attribution(self, *, prepared: Mapping[str, Any] | None, project_id: str, channel: str, provider: str, source_entity_id: str, landing: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not prepared or not landing:
            return None
        return self.authority.register_attribution({"token": prepared["token"], "token_sha256": prepared["token_sha256"], "project_id": _uuid(project_id, "project_id"), "channel": channel, "provider": provider, "source_entity_id": _uuid(source_entity_id, "source_entity_id"), "landing_publication_id": _uuid(landing["publication_id"], "landing_publication_id"), "landing_publication_event_id": _uuid(landing["event_id"], "landing_publication_event_id")})

    def attribution_projection(self, source_entity_id: str) -> dict[str, Any] | None:
        item = self.authority.attribution_for_source(source_entity_id)
        if not item:
            return None
        landing = self.landing_publications.get(item["project_id"])
        if not landing:
            return None
        return {"token": item["token"], "tracked_url": tracked_url(landing["canonical_url"], item["token"]), "source_id": item["attribution_source_id"]}

    def publication_projection(
        self, *, provider: str, project_id: str, source_entity_id: str,
    ) -> dict[str, Any]:
        services = {"instagram": self.instagram, "tiktok": self.tiktok}
        service = services.get(provider)
        checker = None if service is None else getattr(service, "analytics_connection", None)
        readiness = (
            checker(verify=False) if callable(checker)
            else {"provider": provider, "available": False, "explanation": "Analytics capability is unavailable"}
        )
        latest = max(
            (
                item for item in self.authority.list_insights([_uuid(project_id, "project_id")])
                if item["provider"] == provider and item["source_entity_id"] == source_entity_id
            ),
            key=lambda item: _timestamp(item["created_at"]),
            default=None,
        )
        attribution = self.attribution_projection(source_entity_id)
        return {
            "readiness": readiness,
            "freshness": None if latest is None else latest["created_at"],
            "capture_kind": None if latest is None else latest["capture_kind"],
            "attribution_token": None if attribution is None else attribution["token"],
            "attribution_source_id": None if attribution is None else attribution["source_id"],
            "tracked_url": None if attribution is None else attribution["tracked_url"],
        }

    @staticmethod
    def _event_payload(request: Mapping[str, Any]) -> dict[str, Any]:
        expected = {"event_id", "visit_id", "route", "landing_version_sha256", "event_type", "surface", "target", "attribution_token", "viewport_class"}
        if set(request) != expected:
            raise ValueError("Landing analytics event fields are invalid")
        event_type, surface, target = str(request["event_type"]), str(request["surface"]), str(request["target"])
        if event_type not in EVENT_TYPES or surface not in EVENT_SURFACES or target not in EVENT_TARGETS:
            raise ValueError("Landing analytics event semantics are invalid")
        valid_semantics = (
            event_type == "landing_view" and surface == target == "page"
            or event_type == "primary_cta_click" and surface in {"hero", "phone"} and target in {"contacts", "telegram", "instagram", "email", "phone"}
            or event_type == "contact_click" and surface in {"telegram", "instagram", "email", "phone"} and target == surface
        )
        if not valid_semantics:
            raise ValueError("Landing analytics event surface and target do not match")
        route = str(request["route"])
        if not re.fullmatch(r"/(?:ai|la|wa)/[a-z0-9]+(?:-[a-z0-9]+)*", route) or len(route) > 80:
            raise ValueError("Landing analytics route is invalid")
        digest = str(request["landing_version_sha256"])
        if not DIGEST.fullmatch(digest):
            raise ValueError("Landing analytics version digest is invalid")
        token = request["attribution_token"]
        if token is not None and (not isinstance(token, str) or not TOKEN.fullmatch(token)):
            raise ValueError("Landing analytics attribution token is invalid")
        viewport = str(request["viewport_class"])
        if viewport not in VIEWPORTS:
            raise ValueError("Landing analytics viewport is invalid")
        return {"event_id": _uuid(request["event_id"], "event_id"), "visit_id": _uuid(request["visit_id"], "visit_id"), "route": route, "landing_version_sha256": digest, "event_type": event_type, "surface": surface, "target": target, "attribution_token": token, "viewport_class": viewport}

    def record_landing_event(self, request: Mapping[str, Any]) -> dict[str, Any]:
        payload = self._event_payload(request)
        namespace, slug = payload["route"].strip("/").split("/", 1)
        publication, event, _project_name, _record = self.landing_publications._active(namespace, slug)
        if event["landing_version_sha256"] != payload["landing_version_sha256"]:
            raise ValueError("Landing analytics version is no longer current")
        attribution = None
        if payload["attribution_token"]:
            attribution = self.authority.attribution_for_token(payload["attribution_token"])
            if not attribution or attribution["project_id"] != publication["project_id"] or attribution["landing_publication_id"] != publication["publication_id"]:
                raise ValueError("Landing analytics attribution is invalid")
        context = {"project_id": publication["project_id"], "landing_publication_id": publication["publication_id"], "landing_publication_event_id": event["event_id"], "landing_version_id": event["landing_version_id"], "landing_version_sha256": event["landing_version_sha256"]}
        stored = {key: payload[key] for key in ("event_id", "visit_id", "landing_version_sha256", "event_type", "surface", "target", "viewport_class")}
        stored["input_sha256"] = _sha(payload)
        previous_input = self.authority.event_input(payload["event_id"])
        if previous_input is not None:
            if previous_input != stored["input_sha256"]:
                raise ValueError("event_id was reused with different analytics input")
            return {"accepted": True, "created": False, "event_id": payload["event_id"]}
        now = datetime.now(timezone.utc)
        with self._event_lock:
            def recent(bucket: Mapping[str, list[datetime]], key: str) -> list[datetime]:
                return [stamp for stamp in bucket.get(key, []) if now - stamp < timedelta(minutes=1)]

            visit_events = recent(self._event_buckets, payload["visit_id"])
            route_events = recent(self._event_route_buckets, payload["route"])
            if len(visit_events) >= 60 or len(route_events) >= 600:
                raise RuntimeError("Landing analytics event rate limit exceeded")
            self._event_buckets = {
                key: stamps for key in self._event_buckets
                if (stamps := recent(self._event_buckets, key))
            }
            self._event_route_buckets = {
                key: stamps for key in self._event_route_buckets
                if (stamps := recent(self._event_route_buckets, key))
            }
            self._event_buckets[payload["visit_id"]] = [*visit_events, now]
            self._event_route_buckets[payload["route"]] = [*route_events, now]
        _recorded, created = self.authority.record_event(context, stored, None if attribution is None else attribution["attribution_source_id"])
        return {"accepted": True, "created": created, "event_id": payload["event_id"]}

    def _project_ids(self, project_id: str | None) -> list[str]:
        if project_id is None:
            return self.authority.project_ids()
        project_id = _uuid(project_id, "project_id")
        if project_id not in self.authority.project_ids():
            raise KeyError("Project was not found")
        return [project_id]

    @staticmethod
    def _publication_time(publication: Mapping[str, Any]) -> datetime:
        state = publication.get("state") or {}
        return _timestamp(state.get("published_at") or publication["created_at"])

    def _publications(self, project_ids: Sequence[str]) -> list[tuple[str, Any, dict[str, Any]]]:
        selected = set(project_ids)
        result: list[tuple[str, Any, dict[str, Any]]] = []
        for provider, service in (("instagram", self.instagram), ("tiktok", self.tiktok)):
            if service is None:
                continue
            for record in service.authority.list():
                if record["project_id"] in selected and service.safe(record).get("phase") in {"published", "published_unresolved"}:
                    result.append((provider, service, record))
        return result

    def _analytics_readiness(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for provider, service in (("instagram", self.instagram), ("tiktok", self.tiktok)):
            if service is None:
                result[provider] = {"available": False, "explanation": f"{provider.title()} service is unavailable"}
                continue
            checker = getattr(service, "analytics_connection", None)
            result[provider] = checker(verify=True) if callable(checker) else {"available": False, "explanation": f"{provider.title()} analytics capability is unavailable"}
        meta_checker = getattr(self.meta_ads, "connection", None)
        meta = meta_checker(verify=True) if callable(meta_checker) else {
            "verified": False, "explanation": "Meta Ads analytics capability is unavailable",
        }
        result["meta"] = {
            **meta, "available": bool(meta.get("verified")), "separate_from_organic": True,
        }
        result["landing"] = {"available": True, "cookieless": True, "consent_required": False}
        return result

    def _ensure_visual(self, provider: str, service: Any, publication: Mapping[str, Any]) -> dict[str, Any] | None:
        specification = publication["specification"]
        source = specification.get("source") or specification
        digest = str(source.get("render_sha256") or specification.get("render_sha256") or "")
        source_version_id = str(source.get("version_id") or specification.get("source_version_id") or "")
        if not DIGEST.fullmatch(digest) or not source_version_id:
            return None
        previous = self.authority.descriptor(digest)
        if previous:
            binder = getattr(self.authority, "bind_descriptor", None)
            if callable(binder):
                binder(previous["visual_descriptor_id"], source_version_id, publication["project_id"])
            return previous
        if self.structured_provider is None:
            return None
        artifact = self.meta_ads._artifact(publication["project_id"], str(source["creative_id"]), int(source["version"]))
        png = bytes(artifact["rendered"]["bytes"])
        if hashlib.sha256(png).hexdigest() != digest:
            raise ValueError("approved PNG digest changed before visual analysis")
        result = self.structured_provider.call(mode="creative_visual_analysis", system_prompt=self.visual_skill, input_payload={"artifact_sha256": digest, "surface": "post", "provider": provider}, output_schema=visual_descriptor_schema(), prompt_version="creative-visual-analyzer-v1", idempotency_key=f"creative-visual:{digest}", response_validator=validate_visual_descriptor, input_artifacts=[{"name": "approved_png", "mime_type": "image/png", "sha256": digest, "bytes_base64": base64.b64encode(png).decode()}])
        descriptor = validate_visual_descriptor(result["response"])
        return self.authority.record_descriptor({"artifact_sha256": digest, "source_version_id": source_version_id, "project_id": publication["project_id"], "descriptor": descriptor, "descriptor_sha256": _sha(descriptor), "provider": sanitized(result.get("invocation") or {})})

    def refresh(self, *, project_id: str | None, provider: str, backfill: bool = False, scheduled: bool = False) -> dict[str, Any]:
        if provider not in {"all", "instagram", "tiktok", "meta"}:
            raise ValueError("analytics provider is invalid")
        project_ids = self._project_ids(project_id)
        existing_capture_keys = {
            str(item["capture_key"]) for item in self.authority.list_insights(project_ids)
        }
        recorded, skipped, errors, visual_errors = 0, 0, [], []
        for name, service, publication in self._publications(project_ids):
            if provider not in {"all", name}:
                continue
            safe = service.safe(publication)
            post_ids = list((safe.get("external") or {}).get("post_ids") or [])
            if not post_ids:
                skipped += 1
                continue
            published_at = self._publication_time(publication)
            age_hours = int((datetime.now(timezone.utc) - published_at).total_seconds() // 3600)
            captures: list[tuple[str, int | None, str]] = []
            if backfill:
                captures.append(("backfill", None, f"backfill:{name}:{publication['publication_id']}"))
            elif not scheduled:
                captures.append(("manual", None, f"manual:{name}:{publication['publication_id']}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"))
            # A scheduled capture may label only the milestone it is currently
            # observing. Historical provider totals cannot be replayed, so a
            # late scheduler must never stamp today's totals as several missed
            # milestones. Older publications use the explicit backfill path.
            if scheduled:
                milestone = due_milestone(age_hours)
                if milestone is not None:
                    captures.append((
                        "milestone",
                        milestone,
                        f"milestone:{name}:{publication['publication_id']}:{milestone}",
                    ))
            captures = [item for item in captures if item[2] not in existing_capture_keys]
            try:
                self._ensure_visual(name, service, publication)
            except Exception as error:
                visual_errors.append({"provider": name, "publication_id": publication["publication_id"], "detail": str(error)[:300]})
            if not captures:
                skipped += 1
                continue
            try:
                metrics = service.insights(post_ids)
                for capture_kind, milestone, capture_key in captures:
                    _item, created = self.authority.record_insight({"project_id": publication["project_id"], "source_entity_id": publication["publication_id"], "provider": name, "capture_kind": capture_kind, "milestone_hours": milestone, "capture_key": capture_key, "source_published_at": published_at.isoformat(), "metrics": sanitized(metrics)})
                    recorded += int(created)
                    skipped += int(not created)
            except Exception as error:
                errors.append({"provider": name, "publication_id": publication["publication_id"], "detail": str(error)[:300]})
        paid = 0
        if not scheduled and provider in {"all", "meta"}:
            for selected_project in project_ids:
                for deployment in self.meta_ads.authority.list_deployments(selected_project):
                    if not deployment.get("meta_ad_id"):
                        continue
                    try:
                        self.meta_ads.refresh_insights(selected_project, deployment["deployment_id"], 7)
                        paid += 1
                    except Exception as error:
                        errors.append({"provider": "meta", "deployment_id": deployment["deployment_id"], "detail": str(error)[:300]})
        return {"recorded": recorded, "skipped": skipped, "paid_refreshed": paid, "errors": errors, "visual_errors": visual_errors, "backfill": backfill, "scheduled": scheduled}

    def maintain(self) -> dict[str, Any]:
        result = self.refresh(project_id=None, provider="all", backfill=False, scheduled=True)
        result["raw_events_purged"] = self.authority.purge_events()
        return result

    @staticmethod
    def _latest_by_source(insights: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for item in insights:
            source = str(item["source_entity_id"])
            if source not in result or _timestamp(item["created_at"]) > _timestamp(result[source]["created_at"]):
                result[source] = item
        return result

    def _organic_rows(self, project_ids: Sequence[str], cutoff: datetime | None, rollups: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        latest = self._latest_by_source(self.authority.list_insights(project_ids))
        attributed: dict[str, dict[str, int]] = {}
        for item in rollups:
            attribution_id = item.get("attribution_source_id")
            if attribution_id:
                bucket = attributed.setdefault(str(attribution_id), {event: 0 for event in EVENT_TYPES})
                bucket[item["event_type"]] += int(item["cumulative_count"])
        rows = []
        for provider, service, publication in self._publications(project_ids):
            published_at = self._publication_time(publication)
            if cutoff and published_at < cutoff:
                continue
            insight = latest.get(publication["publication_id"])
            metrics = normalized_outcomes(provider, {} if insight is None else insight["metrics"])
            attribution = self.authority.attribution_for_source(publication["publication_id"])
            funnel = attributed.get(str((attribution or {}).get("attribution_source_id") or ""), {event: 0 for event in EVENT_TYPES})
            views = metrics["views"]
            age_hours = max(0.0, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600)
            source = publication["specification"].get("source") or publication["specification"]
            landing = self.landing_publications.get(publication["project_id"])
            analytics = None
            if attribution is not None and landing is not None:
                analytics = {
                    "attribution_source_id": attribution["attribution_source_id"],
                    "tracked_url": tracked_url(str(landing["canonical_url"]), attribution["token"]),
                }
            rows.append({
                "provider": provider, "publication_id": publication["publication_id"],
                "project_id": publication["project_id"],
                "source": {
                    "creative_id": source.get("creative_id"), "version": source.get("version"),
                    "version_id": source.get("version_id") or publication["specification"].get("source_version_id"),
                    "render_sha256": source.get("render_sha256") or publication["specification"].get("render_sha256"),
                },
                "published_at": published_at.isoformat(), "age_hours": round(age_hours, 1),
                "metrics": metrics, "funnel": funnel,
                "rates": {
                    "outbound_contact": None if views <= 0 else funnel["contact_click"] / views,
                    "primary_cta": None if views <= 0 else funnel["primary_cta_click"] / views,
                    "high_intent": None if views <= 0 else (metrics["comments"] + metrics["shares"] + metrics["saves"]) / views,
                    "interaction": None if views <= 0 else (metrics["likes"] + metrics["comments"] + metrics["shares"] + metrics["saves"]) / views,
                    "view_velocity_per_day": views / max(1.0, age_hours / 24),
                },
                "insight": insight, "analytics": analytics,
            })
        return sorted(rows, key=lambda item: (
            item["rates"]["outbound_contact"] or 0,
            item["rates"]["primary_cta"] or 0,
            item["rates"]["high_intent"] or 0,
            item["rates"]["interaction"] or 0,
            item["rates"]["view_velocity_per_day"] or 0,
        ), reverse=True)

    def _paid_rows(self, project_ids: Sequence[str]) -> list[dict[str, Any]]:
        result = []
        for project_id in project_ids:
            for deployment in self.meta_ads.authority.list_deployments(project_id):
                insights = self.meta_ads.authority.list_insights(deployment["deployment_id"])
                result.append({"project_id": project_id, "deployment_id": deployment["deployment_id"], "destination_type": deployment["specification"].get("destination_type"), "status": deployment["status"], "meta_ad_id": deployment.get("meta_ad_id"), "latest_insight": insights[0] if insights else None})
        return result

    @staticmethod
    def _funnel(rollups: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        totals = {event: 0 for event in EVENT_TYPES}
        surfaces: dict[str, int] = {}
        for item in rollups:
            count = int(item["cumulative_count"])
            totals[item["event_type"]] += count
            surfaces[item["surface"]] = surfaces.get(item["surface"], 0) + count
        views = totals["landing_view"]
        return {**totals, "primary_cta_rate": None if views == 0 else totals["primary_cta_click"] / views, "outbound_contact_rate": None if views == 0 else totals["contact_click"] / views, "surfaces": surfaces, "conversion_label": "Outbound contact click · conversion proxy"}

    def active_skills(self, project_id: str) -> dict[str, Any]:
        project = self.authority.latest_skill("project", _uuid(project_id, "project_id"))
        global_skill = self.authority.latest_skill("global", None)
        return {"project": project, "global": global_skill, "precedence": ["catalog_brand_and_brief", "explicit_owner_direction", "project_rules", "global_spirit", "template_defaults"]}

    def workspace(self, *, project_id: str | None, window: int) -> dict[str, Any]:
        if window not in WINDOWS:
            raise ValueError("analytics window must be 7, 30, 90, or 0 for all time")
        project_ids = self._project_ids(project_id)
        cutoff = None if window == 0 else datetime.now(timezone.utc) - timedelta(days=window)
        rollups = self.authority.list_rollups(project_ids, cutoff)
        organic = self._organic_rows(project_ids, cutoff, rollups)
        scope, scoped_project = ("global", None) if project_id is None else ("project", project_ids[0])
        skill = self.authority.latest_skill(scope, scoped_project)
        runs = [
            {**item, "decision": self.authority.decision(item["learning_run_id"])}
            for item in self.authority.list_learning_runs(scope, scoped_project)
        ]
        learning_curve: dict[str, dict[str, Any]] = {}
        for item in organic:
            try:
                artifact = self.meta_ads._artifact(item["project_id"], item["source"]["creative_id"], int(item["source"]["version"]))
                generation = artifact["record"].get("generation") or artifact["detail"].get("generation") or {}
            except Exception:
                generation = {}
            key = ":".join(str(generation.get(name) or "none") for name in ("project_skill_snapshot_id", "global_skill_snapshot_id"))
            group = learning_curve.setdefault(key, {"project_skill_snapshot_id": generation.get("project_skill_snapshot_id"), "global_skill_snapshot_id": generation.get("global_skill_snapshot_id"), "items": 0, "views": 0.0, "contact_clicks": 0})
            group["items"] += 1; group["views"] += item["metrics"]["views"]; group["contact_clicks"] += item["funnel"]["contact_click"]
        metric_definitions = {
            "landing_views": {"numerator": "accepted landing_view events", "denominator": "1", "source": "cookieless PTW daily rollups; near-real-time", "limitation": "event count, not unique visitors"},
            "landing_primary_cta_rate": {"numerator": "primary_cta_click", "denominator": "landing_view", "source": "cookieless PTW daily rollups; near-real-time", "limitation": "click intent, not completed contact"},
            "landing_outbound_contact_rate": {"numerator": "contact_click", "denominator": "landing_view", "source": "cookieless PTW daily rollups; near-real-time", "limitation": "conversion proxy; not a lead or sale"},
            "measured_posts": {"numerator": "published posts represented in the selected window", "denominator": "1", "source": "PTW publication authority plus latest immutable provider snapshot", "limitation": "an unavailable snapshot remains missing rather than zero"},
            "provider_views": {"numerator": "provider reach or views", "denominator": "1", "source": "latest immutable provider snapshot; row shows capture time", "limitation": "Instagram and TikTok definitions differ"},
            "outbound_contact_rate": {"numerator": "attributed contact_click", "denominator": "provider reach/views", "source": "PTW Landing rollup plus latest provider snapshot", "limitation": "conversion proxy; not a lead or sale"},
            "primary_cta_rate": {"numerator": "attributed primary_cta_click", "denominator": "provider reach/views", "source": "PTW Landing rollup plus latest provider snapshot", "limitation": "click intent, not completed contact"},
            "high_intent_rate": {"numerator": "comments + shares + saves", "denominator": "provider reach/views", "source": "latest immutable provider snapshot", "limitation": "TikTok saves are unavailable and platform definitions differ"},
            "interaction_rate": {"numerator": "likes + comments + shares + saves", "denominator": "provider reach/views", "source": "latest immutable provider snapshot", "limitation": "platform-separated for learning"},
            "view_velocity": {"numerator": "provider reach/views", "denominator": "age in days (minimum 1)", "source": "publication time plus latest provider snapshot", "limitation": "coarse normalization; does not model distribution decay"},
            "paid_snapshot": {"numerator": "provider-reported result", "denominator": "provider-defined exposure/result denominator", "source": "latest immutable Meta insight snapshot and capture time", "limitation": "read-only; Meta controls attribution and optimization definitions"},
            "learning_curve_cohort": {"numerator": "views and attributed contact clicks for generations using the same skill snapshot IDs", "denominator": "items in that cohort", "source": "generation provenance, provider snapshots, and PTW rollups", "limitation": "observational cohort; not causal proof"},
        }
        return {"schema": "ptw.analytics.workspace.v1", "scope": scope, "project_id": scoped_project, "project_ids": project_ids, "window_days": window, "readiness": self._analytics_readiness(), "organic": organic, "paid": self._paid_rows(project_ids), "landing_funnel": self._funnel(rollups), "skills": {"snapshot": skill, "rules": [] if skill is None else skill["rules"]}, "learning_runs": runs, "learning_curve": list(learning_curve.values()), "freshness": {provider: max((item["insight"]["created_at"] for item in organic if item["provider"] == provider and item["insight"]), default=None) for provider in ("instagram", "tiktok")}, "metric_definitions": metric_definitions}

    def _dataset(self, *, project_id: str | None, surface: str) -> dict[str, Any]:
        workspace = self.workspace(project_id=project_id, window=0)
        if surface == "post":
            mature = [item for item in workspace["organic"] if item["age_hours"] >= 72 and item["metrics"]["views"] > 0]
            comparable = [item for item in mature if sum(
                1 for candidate in mature
                if candidate["provider"] == item["provider"]
                and comparison_age_band(candidate["age_hours"]) == comparison_age_band(item["age_hours"])
            ) >= 2]
            for item in comparable:
                item["age_band_hours"] = comparison_age_band(item["age_hours"])
                artifact = self.meta_ads._artifact(
                    item["project_id"], item["source"]["creative_id"],
                    int(item["source"]["version"]),
                )
                record = artifact["record"]
                item["creative"] = {
                    "template_id": artifact["detail"].get("template_id"),
                    "configuration": deepcopy(record.get("configuration") or {}),
                    "content": deepcopy(record.get("content") or {}),
                    "generation": deepcopy(
                        record.get("generation") or artifact["detail"].get("generation") or {}
                    ),
                    "artifact_sha256": item["source"].get("render_sha256"),
                    "visual_descriptor": deepcopy(
                        (self.authority.descriptor(str(item["source"].get("render_sha256") or "")) or {}).get("descriptor")
                    ),
                }
            items = comparable
        else:
            rollups = self.authority.list_rollups(workspace["project_ids"], None)
            grouped: dict[str, dict[str, Any]] = {}
            for item in rollups:
                publication = self.landing_publications.get(item["project_id"])
                published = next((event for event in (publication or {}).get("events", []) if event.get("landing_version_id") == item["landing_version_id"] and event.get("action") == "publish"), None)
                age_hours = 0.0 if published is None else max(0.0, (datetime.now(timezone.utc) - _timestamp(published["created_at"])).total_seconds() / 3600)
                group = grouped.setdefault(item["landing_version_id"], {
                    "landing_version_id": item["landing_version_id"],
                    "project_id": item["project_id"],
                    "version_sha256": item["landing_version_sha256"],
                    "age_hours": round(age_hours, 1),
                    "events": {event: 0 for event in EVENT_TYPES},
                })
                group["events"][item["event_type"]] += int(item["cumulative_count"])
            items = []
            for item in grouped.values():
                if item["age_hours"] < 72 or item["events"]["landing_view"] <= 0:
                    continue
                publication = self.landing_publications.get(item["project_id"])
                published = next(
                    (
                        event for event in (publication or {}).get("events", [])
                        if event.get("landing_version_id") == item["landing_version_id"]
                        and event.get("action") == "publish"
                    ),
                    None,
                )
                if published is None:
                    continue
                try:
                    version = self.landing_pages.approved_version_detail(
                        item["project_id"], published["landing_id"],
                        int(published["landing_version"]),
                    )
                except (AttributeError, KeyError, ValueError):
                    continue
                item["creative"] = {
                    "template_id": version["template_id"],
                    "configuration": deepcopy(version["configuration"]),
                    "content": safe_landing_learning_content(version["content"]),
                    "assets": deepcopy(version.get("assets") or []),
                    "generation": deepcopy(version.get("generation") or {}),
                    "version_sha256": version["version_sha256"],
                }
                items.append(item)
            for item in items:
                item["age_band_hours"] = comparison_age_band(item["age_hours"])
            items = [item for item in items if sum(
                1 for candidate in items
                if candidate["age_band_hours"] == item["age_band_hours"]
            ) >= 2]
        return {"schema": "ptw.creative-learning.dataset.v1", "scope": "global" if project_id is None else "project", "project_id": project_id, "surface": surface, "minimum_age_hours": 72, "platform_separated": True, "priority": ["attributable_outbound_contact_rate", "primary_cta_rate", "high_intent_engagement", "interaction_rate", "reach_or_view_velocity"], "items": items, "sample_size": len(items), "project_count": len({item["project_id"] for item in items}), "confidence": "insufficient" if len(items) < 2 else "exploratory" if len(items) < 5 else "directional"}

    def run_learning(self, *, project_id: str | None, request_id: str, surface: str) -> dict[str, Any]:
        if surface not in {"post", "landing"}:
            raise ValueError("learning surface must be post or landing")
        if project_id is not None:
            self._project_ids(project_id)
        request_id = _uuid(request_id, "request_id")
        scope = "global" if project_id is None else "project"
        dataset = self._dataset(project_id=project_id, surface=surface)
        fingerprint = _sha({"request_id": request_id, "scope": scope, "project_id": project_id, "surface": surface, "dataset_sha256": _sha(dataset)})
        status = "insufficient_data" if dataset["sample_size"] < 2 else "running"
        run, created = self.authority.create_learning_run({"request_id": request_id, "request_sha256": fingerprint, "scope": scope, "project_id": project_id, "surface": surface, "status": status, "dataset": dataset, "dataset_sha256": _sha(dataset)})
        if not created or status == "insufficient_data":
            if created:
                run = self.authority.update_learning_run(run["learning_run_id"], status="insufficient_data", candidates=[], completed_at=utc_now())
            return run
        try:
            if self.structured_provider is None:
                raise RuntimeError("performance learning provider is unavailable")
            def validate_candidates(value: Mapping[str, Any]) -> dict[str, Any]:
                if not isinstance(value, Mapping) or set(value) != {"candidates"} or not isinstance(value["candidates"], list):
                    raise ValueError("performance learner returned invalid candidate fields")
                if len(value["candidates"]) > 12:
                    raise ValueError("performance learner returned too many candidates")
                rules = []
                for candidate in value["candidates"]:
                    if not isinstance(candidate, Mapping):
                        raise ValueError("performance learner candidate is invalid")
                    normalized = normalize_rule(candidate, scope=scope, project_id=project_id)
                    normalized["confidence"] = {
                        **normalized["confidence"],
                        "sample_size": dataset["sample_size"],
                        "project_count": dataset["project_count"],
                        "level": dataset["confidence"],
                    }
                    rules.append(normalized)
                return {"candidates": rules}

            result = self.structured_provider.call(mode="creative_performance_learning", system_prompt=self.performance_skill, input_payload={"dataset": dataset, "active_skills": self.active_skills(project_id) if project_id else {"global": self.authority.latest_skill("global", None)}}, output_schema=learning_output_schema(scope), prompt_version="creative-performance-learner-v1", idempotency_key=f"creative-learning:{run['learning_run_id']}", response_validator=validate_candidates)
            candidates = [
                {**rule, "candidate_id": new_uuid7(), "active": False, "tombstone": False}
                for rule in result["response"]["candidates"]
            ]
            run = self.authority.update_learning_run(run["learning_run_id"], status="completed", candidates=candidates, provider=sanitized(result.get("invocation") or {}), error_type=None, error_message=None, completed_at=utc_now())
        except Exception as error:
            run = self.authority.update_learning_run(run["learning_run_id"], status="failed", candidates=[], provider={}, error_type=type(error).__name__, error_message=str(error)[:1000], completed_at=utc_now())
        return run

    def decide(self, *, project_id: str | None, run_id: str, request_id: str, decision: str, rules: Sequence[Mapping[str, Any]], actor: str) -> dict[str, Any]:
        with self._decision_lock:
            if decision not in {"activate", "reject"}:
                raise ValueError("learning decision must be activate or reject")
            project_id = None if project_id is None else _uuid(project_id, "project_id")
            request_id = _uuid(request_id, "request_id")
            run_id = _uuid(run_id, "learning_run_id")
            run = self.authority.get_learning_run(run_id)
            expected_scope = "global" if project_id is None else "project"
            if run["scope"] != expected_scope or run.get("project_id") != project_id:
                raise KeyError("creative learning run was not found in this scope")
            if run["status"] != "completed":
                raise ValueError("only a completed learning run can be decided")
            selected: list[dict[str, Any]] = []
            snapshot = None
            if decision == "activate":
                candidate_ids = {str(item["candidate_id"]) for item in run["candidates"]}
                for value in rules:
                    if str(value.get("candidate_id") or "") not in candidate_ids:
                        raise ValueError("selected rule is not from this learning run")
                    selected.append(normalize_rule(
                        {key: item for key, item in value.items() if key not in {"candidate_id", "scope", "project_id"}},
                        scope=expected_scope, project_id=project_id,
                    ))
                if not selected:
                    raise ValueError("activate requires at least one selected rule")
                previous = self.authority.latest_skill(expected_scope, project_id)
                combined = list((previous or {}).get("rules") or []) + selected
                if _rules_conflict(combined):
                    raise ValueError("selected rules conflict with an active rule")
                snapshot, _created = self.authority.append_skill({"request_id": request_id, "scope": expected_scope, "project_id": project_id, "rules": combined, "rules_sha256": _sha(combined), "source_learning_run_id": run_id, "requested_by": actor})
            decision_sha256 = _sha({"request_id": request_id, "learning_run_id": run_id, "decision": decision, "selected_rules": selected, "skill_snapshot_id": None if snapshot is None else snapshot["skill_snapshot_id"]})
            recorded = self.authority.record_decision({"request_id": request_id, "request_sha256": decision_sha256, "learning_run_id": run_id, "decision": decision, "selected_rules": selected, "skill_snapshot_id": None if snapshot is None else snapshot["skill_snapshot_id"], "requested_by": actor})
            return {"decision": recorded, "skill_snapshot": snapshot}

    def revise_rule(self, *, project_id: str | None, request_id: str, rule: Mapping[str, Any], actor: str, delete: bool = False) -> dict[str, Any]:
        if project_id is not None:
            project_id = self._project_ids(project_id)[0]
        scope = "global" if project_id is None else "project"
        previous = self.authority.latest_skill(scope, project_id)
        rules = list((previous or {}).get("rules") or [])
        identifier = _uuid(rule.get("rule_id") or new_uuid7(), "rule_id")
        match = next((item for item in rules if item["rule_id"] == identifier), None)
        if delete and match is None:
            raise KeyError("creative skill rule was not found")
        candidate = normalize_rule({**(match or {}), **dict(rule), "rule_id": identifier, "active": not delete, "tombstone": delete}, scope=scope, project_id=project_id)
        next_rules = [item for item in rules if item["rule_id"] != identifier] + [candidate]
        if _rules_conflict(next_rules):
            raise ValueError("creative skill rule conflicts with an active rule")
        snapshot, _created = self.authority.append_skill({"request_id": _uuid(request_id, "request_id"), "scope": scope, "project_id": project_id, "rules": next_rules, "rules_sha256": _sha(next_rules), "source_learning_run_id": None, "requested_by": actor})
        return snapshot
