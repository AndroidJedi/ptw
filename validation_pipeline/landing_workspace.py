"""Bounded, responsive Landing Studio workspace.

The browser owns the responsive preview.  This module owns the exact editable
document, digest-checked generated media, and immutable approved snapshots.
It intentionally does not accept HTML, CSS, arbitrary section trees, or owner
uploads: the Landing is one fixed semantic composition.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from urllib.parse import urlsplit
from pathlib import Path
from typing import Any, Mapping

from .studio import inspect_media
from .landing_design import (DEFAULT_APP_FEATURE, APP_FEATURE_LIMITS, DEFAULT_PHONE_MOCKUP, PHONE_MOCKUP_OPTIONS, DEFAULT_COMPONENTS, DEFAULT_IMAGE_DIRECTIONS, COMPONENT_OPTIONS, LANDING_BACKGROUND_DIRECTIVES, PHONE_HERO_STYLE_DIRECTIVES, design_catalog)


LANDING_TEMPLATE_ID = "project_landing"
LANDING_TEMPLATE_VERSION = 4
LANDING_SCHEMA = "ptw.landing.workspace.v1"
LANDING_CONFIGURATION_SCHEMA = "ptw.landing.configuration.v1"
LANDING_CONTENT_SCHEMA = "ptw.landing.content.v1"
LANDING_VERSION_SCHEMA = "ptw.landing.version.v1"
LANDING_VISUAL_SLOTS = ("hero_visual", "visual_break_visual")
LANDING_VISUAL_HISTORY_LIMIT = 3
LANDING_FONT_FAMILIES = (
    "Inter", "Roboto Condensed", "Manrope", "Montserrat", "Source Sans 3",
    "Oswald", "Cormorant Garamond", "Cormorant Garamond Italic", "Lora",
    "Lora Italic",
)

DEFAULT_CONFIGURATION: dict[str, Any] = {
    "schema": LANDING_CONFIGURATION_SCHEMA,
    "theme": {
        "background_color": "#f7f6f2", "surface_color": "#ffffff",
        "text_color": "#1a1a1a", "accent_color": "#1f55d9",
        "font_family": "Manrope", "heading_font_family": "Manrope",
        "corner_radius": 24,
    },
    "hero": {"alignment": "left", "image_position": "right"},
    "features": {"layout": "three_columns"},
    "social_proof": {"layout": "cards"},
    "visual_break": {"height": "medium"},
    "contacts": {"alignment": "left"},
    "faq": {"style": "divided"},
}

# Optional on stored v1 documents: never materialize this block while reading.
DEFAULT_PRESENTATION: dict[str, Any] = {
    "language": "uk", "cta_target": "contacts", "heading_scale": 1.0,
    "spacing": "comfortable", "hero_focus": {"x": 50, "y": 50},
    "visual_break_focus": {"x": 50, "y": 50},
}


def normalize_presentation(value: Mapping[str, Any]) -> dict[str, Any]:
    root = _object(value, set(DEFAULT_PRESENTATION), "presentation")
    result = _copy(root)
    for field, allowed in (("language", {"uk", "en"}),
                           ("cta_target", {"contacts", "url", "email", "phone"}),
                           ("spacing", {"compact", "comfortable", "airy"})):
        if not isinstance(root[field], str) or root[field] not in allowed:
            raise ValueError(f"Landing presentation.{field} is invalid")
    def number(value: Any, minimum: float, maximum: float, field: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f"Landing presentation.{field} is invalid")
    number(root["heading_scale"], .85, 1.15, "heading_scale")
    for field in ("hero_focus", "visual_break_focus"):
        focus = _object(root[field], {"x", "y"}, field)
        for axis in ("x", "y"):
            number(focus[axis], 0, 100, f"{field}.{axis}")
    return result


def valid_contact(field: str, value: str) -> bool:
    if field == "email":
        return re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value) is not None
    if field == "phone":
        return re.fullmatch(r"\+?[0-9 ()\-]+", value) is not None and 3 <= sum(c.isdigit() for c in value) <= 15
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None and not any(c.isspace() for c in value) and "\\" not in value and (parsed.port is None or 0 < parsed.port <= 65535)
    except ValueError:
        return False


DEFAULT_CONTENT: dict[str, Any] = {
    "schema": LANDING_CONTENT_SCHEMA,
    "hero": {"title": "", "supporting_text": "", "cta_label": "", "visual_direction": ""},
    "features": [
        {"title": "", "description": ""},
        {"title": "", "description": ""},
        {"title": "", "description": ""},
    ],
    "social_proof": {"heading": "", "items": []},
    "visual_break": {"visual_direction": ""},
    "contacts": {"heading": "", "supporting_text": "", "email": "", "phone": "", "url": ""},
    "faq": [
        {"question": "", "answer": ""},
        {"question": "", "answer": ""},
        {"question": "", "answer": ""},
    ],
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _text(value: Any, field: str, minimum: int, maximum: int, *, required: bool = False) -> str:
    result = " ".join(str(value or "").split())
    if required and not result:
        raise ValueError(f"Landing {field} is required")
    if len(result) > maximum or (result and len(result) < minimum):
        raise ValueError(f"Landing {field} must contain {minimum}-{maximum} characters")
    return result


def _object(value: Any, expected: set[str], field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"Landing {field} fields are invalid")
    return value


def _color(value: Any, field: str) -> str:
    result = str(value or "")
    if len(result) != 7 or result[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in result[1:]):
        raise ValueError(f"Landing {field} must be a six-digit hex color")
    return result.lower()


def normalize_configuration(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - {"presentation", "components", "image_directions", "phone_mockup"} != set(DEFAULT_CONFIGURATION):
        raise ValueError("Landing configuration fields are invalid")
    root = value
    if root.get("schema") != LANDING_CONFIGURATION_SCHEMA:
        raise ValueError("Landing configuration schema is invalid")
    theme = _object(root["theme"], set(DEFAULT_CONFIGURATION["theme"]), "theme")
    fonts = {"font_family", "heading_font_family"}
    result = _copy(DEFAULT_CONFIGURATION)
    result["theme"] = {
        key: (str(theme[key]) if key in fonts else _color(theme[key], f"theme.{key}"))
        for key in ("background_color", "surface_color", "text_color", "accent_color", "font_family", "heading_font_family")
    }
    if result["theme"]["font_family"] not in LANDING_FONT_FAMILIES or result["theme"]["heading_font_family"] not in LANDING_FONT_FAMILIES:
        raise ValueError("Landing font family is invalid")
    radius = theme["corner_radius"]
    if isinstance(radius, bool) or not isinstance(radius, int) or not 0 <= radius <= 48:
        raise ValueError("Landing corner radius is invalid")
    result["theme"]["corner_radius"] = radius
    enums = {
        "hero": ("alignment", {"left", "center"}, "image_position", {"left", "right", "below"}),
        "features": ("layout", {"three_columns", "stacked"}, None, set()),
        "social_proof": ("layout", {"cards", "quote"}, None, set()),
        "visual_break": ("height", {"small", "medium", "large"}, None, set()),
        "contacts": ("alignment", {"left", "center"}, None, set()),
        "faq": ("style", {"divided", "cards"}, None, set()),
    }
    for section, (first, allowed_first, second, allowed_second) in enums.items():
        source = _object(root[section], set(DEFAULT_CONFIGURATION[section]), section)
        if source[first] not in allowed_first or (second and source[second] not in allowed_second):
            raise ValueError(f"Landing {section} configuration is invalid")
        result[section] = dict(source)
    if "phone_mockup" in root:
        phone = _object(root["phone_mockup"], set(DEFAULT_PHONE_MOCKUP), "phone mockup")
        for key, choices in PHONE_MOCKUP_OPTIONS.items():
            if not isinstance(phone[key], str) or phone[key] not in choices:
                raise ValueError(f"Landing phone_mockup.{key} is invalid")
        result["phone_mockup"] = dict(phone)
    if "presentation" in root:
        result["presentation"] = normalize_presentation(root["presentation"])
    if "components" in root:
        components = _object(root["components"], set(DEFAULT_COMPONENTS), "components")
        for key, choices in COMPONENT_OPTIONS.items():
            if not isinstance(components[key], str) or components[key] not in choices:
                raise ValueError(f"Landing components.{key} is invalid")
        result["components"] = {**components, **{key: _color(components[key], key) for key in ("button_color", "button_text_color")}}
    if "image_directions" in root:
        directions = _object(root["image_directions"], set(DEFAULT_IMAGE_DIRECTIONS), "image directions")
        for slot, direction in directions.items():
            direction = _object(direction, {"style", "background"}, "image direction")
            if not isinstance(direction["style"], str) or direction["style"] not in PHONE_HERO_STYLE_DIRECTIVES or not isinstance(direction["background"], str) or direction["background"] not in LANDING_BACKGROUND_DIRECTIVES:
                raise ValueError("Landing image direction is invalid")
        result["image_directions"] = _copy(directions)
    return result


def normalize_content(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - {"app_feature"} != set(DEFAULT_CONTENT):
        raise ValueError("Landing content fields are invalid")
    root = value
    if root.get("schema") != LANDING_CONTENT_SCHEMA:
        raise ValueError("Landing content schema is invalid")
    hero = _object(root["hero"], set(DEFAULT_CONTENT["hero"]), "hero")
    visual_break = _object(root["visual_break"], set(DEFAULT_CONTENT["visual_break"]), "visual break")
    contacts = _object(root["contacts"], set(DEFAULT_CONTENT["contacts"]), "contacts")
    proof = _object(root["social_proof"], set(DEFAULT_CONTENT["social_proof"]), "social proof")
    features = root["features"]
    faq = root["faq"]
    proof_items = proof["items"]
    if not isinstance(features, list) or len(features) != 3 or not isinstance(faq, list) or len(faq) != 3:
        raise ValueError("Landing requires exactly three features and three FAQs")
    if not isinstance(proof_items, list) or len(proof_items) > 3:
        raise ValueError("Landing social proof supports zero to three owner entries")
    result = _copy(DEFAULT_CONTENT)
    if "app_feature" in root:
        feature = _object(root["app_feature"], set(DEFAULT_APP_FEATURE), "app feature")
        if not isinstance(feature["items"], list) or len(feature["items"]) != 3:
            raise ValueError("Landing app feature requires three UI rows")
        result["app_feature"] = {key: _text(feature[key], f"app_feature.{key}", 1, APP_FEATURE_LIMITS[key]) for key in ("title", "description", "action_label")}
        result["app_feature"]["items"] = [{key: _text(_object(item, {"label", "value"}, "app feature row")[key], f"app_feature.{key}", 1, APP_FEATURE_LIMITS[key]) for key in ("label", "value")} for item in feature["items"]]
    result["hero"] = {
        "title": _text(hero["title"], "hero title", 1, 140),
        "supporting_text": _text(hero["supporting_text"], "hero supporting text", 1, 360),
        "cta_label": _text(hero["cta_label"], "CTA label", 1, 60),
        "visual_direction": _text(hero["visual_direction"], "hero visual direction", 8, 600),
    }
    result["features"] = [
        {
            "title": _text(_object(item, {"title", "description"}, "feature")["title"], "feature title", 1, 90),
            "description": _text(_object(item, {"title", "description"}, "feature")["description"], "feature description", 1, 300),
        }
        for item in features
    ]
    result["social_proof"] = {
        "heading": _text(proof["heading"], "social proof heading", 1, 120),
        "items": [
            {
                "statement": _text(_object(item, {"statement", "attribution"}, "social proof item")["statement"], "social proof statement", 1, 360),
                "attribution": _text(_object(item, {"statement", "attribution"}, "social proof item")["attribution"], "social proof attribution", 1, 120),
            }
            for item in proof_items
        ],
    }
    result["visual_break"] = {"visual_direction": _text(visual_break["visual_direction"], "visual-break direction", 8, 600)}
    email = _text(contacts["email"], "contact email", 3, 254)
    phone = _text(contacts["phone"], "contact phone", 3, 60)
    url = _text(contacts["url"], "contact URL", 8, 2048)
    for field, contact in (("email", email), ("phone", phone), ("url", url)):
        if contact and not valid_contact(field, contact):
            raise ValueError(f"Landing contact {field} is invalid" + ("; URL must use HTTPS" if field == "url" else ""))
    result["contacts"] = {
        "heading": _text(contacts["heading"], "contact heading", 1, 120),
        "supporting_text": _text(contacts["supporting_text"], "contact supporting text", 1, 300),
        "email": email, "phone": phone, "url": url,
    }
    result["faq"] = [
        {
            "question": _text(_object(item, {"question", "answer"}, "FAQ")["question"], "FAQ question", 1, 180),
            "answer": _text(_object(item, {"question", "answer"}, "FAQ")["answer"], "FAQ answer", 1, 500),
        }
        for item in faq
    ]
    return result


def normalize_composed_content(value: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only AI's non-factual page copy; proof and endpoints remain owner input."""
    result = normalize_content(value)
    if "app_feature" not in result:
        raise ValueError("Landing AI must provide the app feature screen")
    if result["social_proof"]["items"]:
        raise ValueError("Landing AI must not invent social proof")
    if any(result["contacts"][field] for field in ("email", "phone", "url")):
        raise ValueError("Landing AI must not invent contact endpoints")
    required = [
        result["hero"]["title"], result["hero"]["supporting_text"], result["hero"]["cta_label"], result["hero"]["visual_direction"],
        result["social_proof"]["heading"], result["visual_break"]["visual_direction"],
        result["contacts"]["heading"], result["contacts"]["supporting_text"],
    ]
    if "app_feature" in result:
        required.extend(result["app_feature"][key] for key in ("title", "description", "action_label"))
        required.extend(item["label"] for item in result["app_feature"]["items"])
    required.extend(item["title"] and item["description"] for item in result["features"])
    required.extend(item["question"] and item["answer"] for item in result["faq"])
    if not all(required):
        raise ValueError("Landing AI must complete every non-evidence page field")
    return result


def landing_catalog() -> dict[str, Any]:
    return {
        "schema": "ptw.landing.catalog.v1", "template_id": LANDING_TEMPLATE_ID,
        "template_version": LANDING_TEMPLATE_VERSION,
        "section_order": ["hero", "features", "social_proof", "visual_break", "contacts", "faq"],
        "font_families": list(LANDING_FONT_FAMILIES),
        "visual_slots": list(LANDING_VISUAL_SLOTS),
        "presentation_defaults": _copy(DEFAULT_PRESENTATION),
        **_copy(design_catalog()),
        "sha256": sha256_json({"configuration": DEFAULT_CONFIGURATION, "content": DEFAULT_CONTENT, "presentation": DEFAULT_PRESENTATION, "design": design_catalog()}),
    }


class LandingWorkspace:
    """One page's mutable bounded state and durable generated media."""

    def __init__(self, root: Path | str, *, image_provider: Any | None = None) -> None:
        self.root = Path(root)
        self.assets = self.root / "assets"
        self.versions = self.root / "versions"
        self.image_provider = image_provider
        self.root.mkdir(parents=True, exist_ok=True)
        self.assets.mkdir(parents=True, exist_ok=True)
        self.versions.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _atomic_bytes(path: Path, value: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(value)
        temporary.replace(path)

    def _configuration(self) -> dict[str, Any]:
        path = self.root / "configuration.json"
        return normalize_configuration(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else _copy(DEFAULT_CONFIGURATION)

    def _content(self) -> dict[str, Any]:
        path = self.root / "content.json"
        return normalize_content(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else _copy(DEFAULT_CONTENT)

    def _history(self, slot: str) -> list[dict[str, Any]]:
        if slot not in LANDING_VISUAL_SLOTS:
            raise ValueError("Landing visual slot is invalid")
        path = self.assets / f"{slot}.history.json"
        if not path.is_file():
            return []
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise ValueError("Landing visual history is invalid")
        result = []
        for item in value:
            if not isinstance(item, Mapping) or not isinstance(item.get("sha256"), str):
                raise ValueError("Landing visual history is invalid")
            image = self.assets / f"{item['sha256']}.png"
            if not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Landing visual asset digest mismatch")
            result.append(dict(item))
        return result

    def _selected(self, slot: str) -> str | None:
        path = self.assets / f"{slot}.selected.json"
        if not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        selected = value.get("sha256") if isinstance(value, Mapping) else None
        return str(selected) if isinstance(selected, str) else None

    def _asset_summaries(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for slot in LANDING_VISUAL_SLOTS:
            history = self._history(slot)
            selected = self._selected(slot)
            items.append({
                "slot": slot, "available": selected is not None,
                "sha256": selected, "history": [
                    {key: value for key, value in item.items() if key != "source"} | {"selected": item["sha256"] == selected}
                    for item in history
                ],
            })
        return items

    def state_sha256(self) -> str:
        return sha256_json({"configuration": self._configuration(), "content": self._content(), "assets": self._asset_summaries()})

    def _versions(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for path in sorted(self.versions.glob("v*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            digest = value.get("version_sha256")
            if value.get("schema") != LANDING_VERSION_SCHEMA or not isinstance(digest, str):
                raise ValueError("Landing version is invalid")
            if sha256_json({key: item for key, item in value.items() if key != "version_sha256"}) != digest:
                raise ValueError("Landing version digest mismatch")
            result.append(value)
        return result

    def detail(self) -> dict[str, Any]:
        return {
            "schema": LANDING_SCHEMA, "template_id": LANDING_TEMPLATE_ID,
            "catalog": landing_catalog(), "state_sha256": self.state_sha256(),
            "configuration": self._configuration(), "content": self._content(),
            "assets": self._asset_summaries(), "image_generation_available": self.image_provider is not None,
            "versions": [{
                "version": item["version"], "state_sha256": item["state_sha256"],
                "version_sha256": item["version_sha256"], "change_note": item["change_note"],
            } for item in self._versions()],
        }

    def _assert_state(self, digest: str) -> None:
        if digest != self.state_sha256():
            raise RuntimeError("Landing changed; reload before saving")

    def save_configuration(self, *, base_sha256: str, configuration: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
        self._assert_state(base_sha256)
        normalized_configuration = normalize_configuration(configuration)
        normalized_content = normalize_content(content)
        self._atomic_json(self.root / "configuration.json", normalized_configuration)
        self._atomic_json(self.root / "content.json", normalized_content)
        return self.detail()

    def generate_visual(
        self, *, base_sha256: str, slot: str, visual_direction: str, prompt: str,
        enhance_current: bool = False,
    ) -> dict[str, Any]:
        self._assert_state(base_sha256)
        if slot not in LANDING_VISUAL_SLOTS:
            raise ValueError("Landing visual slot is invalid")
        if self.image_provider is None:
            raise RuntimeError("Landing image generation is unavailable")
        direction = _text(visual_direction, "visual direction", 8, 600)
        selected = self._selected(slot)
        reference = None
        if enhance_current:
            if not selected:
                raise ValueError("select a Landing visual before enhancement")
            reference = (self.assets / f"{selected}.png").read_bytes()
        generated = self.image_provider.generate(prompt + "\n\nVisual direction: " + direction, reference_image=reference)
        data = bytes(generated["bytes"])
        inspected = inspect_media(data, str(generated.get("mime_type") or "image/png"))
        if inspected["mime_type"] != "image/png":
            raise ValueError("Landing generated visual must be PNG")
        digest = hashlib.sha256(data).hexdigest()
        self._atomic_bytes(self.assets / f"{digest}.png", data)
        history = [item for item in self._history(slot) if item["sha256"] != digest]
        history.append({
            "sha256": digest, "mime_type": "image/png", "width": inspected["width"], "height": inspected["height"],
            "visual_direction": direction, "source": dict(generated.get("source") or {}),
        })
        while len(history) > LANDING_VISUAL_HISTORY_LIMIT:
            evicted = history.pop(0)
            (self.assets / f"{evicted['sha256']}.png").unlink(missing_ok=True)
        self._atomic_json(self.assets / f"{slot}.history.json", history)
        self._atomic_json(self.assets / f"{slot}.selected.json", {"sha256": digest})
        return self.detail()

    def select_visual(self, *, base_sha256: str, slot: str, sha256: str) -> dict[str, Any]:
        self._assert_state(base_sha256)
        if sha256 not in {item["sha256"] for item in self._history(slot)}:
            raise ValueError("Landing visual is not retained")
        self._atomic_json(self.assets / f"{slot}.selected.json", {"sha256": sha256})
        return self.detail()

    def visual_image(self, slot: str, sha256: str) -> dict[str, Any]:
        if sha256 not in {item["sha256"] for item in self._history(slot)}:
            raise KeyError("Landing visual was not found")
        data = (self.assets / f"{sha256}.png").read_bytes()
        if hashlib.sha256(data).hexdigest() != sha256:
            raise RuntimeError("Landing visual digest mismatch")
        return {"bytes": data, "mime_type": "image/png", "sha256": sha256}

    def approval_ready(self, detail: Mapping[str, Any] | None = None) -> None:
        value = self.detail() if detail is None else detail
        content = value["content"]
        required = [
            content["hero"]["title"], content["hero"]["supporting_text"], content["hero"]["cta_label"],
            content["contacts"]["heading"], content["contacts"]["supporting_text"],
        ]
        if not all(required):
            raise ValueError("Landing section copy must be completed before approval")
        feature = content.get("app_feature")
        if feature is not None and (not all(feature[key] for key in ("title", "description", "action_label")) or any(not item["label"] for item in feature["items"])):
            raise ValueError("Landing app feature copy and row labels must be completed before approval")
        proof = content["social_proof"]
        if proof["items"] and (not proof["heading"] or any(not item["statement"] or not item["attribution"] for item in proof["items"])):
            raise ValueError("Landing social proof entries require a heading, statement, and attribution")
        target = value["configuration"].get("presentation", DEFAULT_PRESENTATION)["cta_target"]
        if target != "contacts" and not content["contacts"][target]:
            raise ValueError("Landing CTA destination requires its contact endpoint")
        if not any(content["contacts"][field] for field in ("email", "phone", "url")):
            raise ValueError("Landing requires an email, phone, or HTTPS contact URL before approval")
        if any(not item["title"] or not item["description"] for item in content["features"]):
            raise ValueError("Landing features must be completed before approval")
        if any(not item["question"] or not item["answer"] for item in content["faq"]):
            raise ValueError("Landing FAQs must be completed before approval")
        if any(not item["available"] for item in value["assets"]):
            raise ValueError("Landing hero and visual-break artwork must be generated before approval")

    def approve_configuration(self, *, base_sha256: str, configuration: Mapping[str, Any], content: Mapping[str, Any], change_note: str) -> dict[str, Any]:
        self._assert_state(base_sha256)
        candidate = {**self.detail(), "configuration": normalize_configuration(configuration), "content": normalize_content(content)}
        self.approval_ready(candidate)
        note = _text(change_note, "version change note", 1, 240, required=True)
        saved = self.save_configuration(base_sha256=base_sha256, configuration=candidate["configuration"], content=candidate["content"])
        version = len(self._versions()) + 1
        record = {
            "schema": LANDING_VERSION_SCHEMA, "version": version, "state_sha256": saved["state_sha256"],
            "configuration": saved["configuration"], "content": saved["content"], "assets": saved["assets"],
            "change_note": note,
        }
        record["version_sha256"] = sha256_json(record)
        self._atomic_json(self.versions / f"v{version}.json", record)
        return self.detail()

    def version_detail(self, version: int) -> dict[str, Any]:
        for item in self._versions():
            if item["version"] == version:
                return _copy(item)
        raise KeyError("Landing version was not found")
