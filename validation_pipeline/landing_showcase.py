"""Bounded App Showcase contract shared by composition, editing and publishing."""
from copy import deepcopy
from typing import Any, Mapping

TEMPLATE_ID = "app_showcase"
SCREEN_SLOTS = ("app_screen_1", "app_screen_2", "app_screen_3")
VISUAL_SLOTS = (*SCREEN_SLOTS, "visual_break_visual")
DEFAULT_SCREENS = [{"title": "", "description": "", "visual_direction": ""} for _ in SCREEN_SLOTS]
DEFAULT_SHOWCASE = {"gradient_end": "#08cbb5", "screen_scale": 1.0, "screen_offset": 32}


def screen_direction(content: Mapping[str, Any], slot: str) -> str:
    if slot == "walkthrough_visual":
        return content.get("marketing", {}).get("walkthrough_visual_direction", "")
    if slot in SCREEN_SLOTS:
        return content["app_screens"][SCREEN_SLOTS.index(slot)]["visual_direction"]
    return content["hero" if slot == "hero_visual" else "visual_break"]["visual_direction"]


def normalize_screens(value: Any) -> list[dict]:
    from .landing_workspace import _object, _text
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("App Showcase requires exactly three screens")
    return [{key: _text(_object(item, {"title", "description", "visual_direction"}, "app screen")[key],
                       f"app screen {key}", 8 if key == "visual_direction" else 1, limit)
             for key, limit in (("title", 90), ("description", 300), ("visual_direction", 600))} for item in value]


def normalize_showcase(value: Any) -> dict:
    import math
    from .landing_workspace import _object, _color
    value = _object(value, set(DEFAULT_SHOWCASE), "showcase")
    result = {"gradient_end": _color(value["gradient_end"], "gradient end")}
    for key, low, high in (("screen_scale", .8, 1.15), ("screen_offset", 0, 64)):
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f"App Showcase {key} is invalid")
        result[key] = number
    return result


def configuration() -> dict:
    from .landing_workspace import DEFAULT_CONFIGURATION, DEFAULT_PRESENTATION
    value = deepcopy(DEFAULT_CONFIGURATION)
    value["theme"].update(background_color="#ffffff", text_color="#17263c", accent_color="#3489ed")
    value["presentation"] = deepcopy(DEFAULT_PRESENTATION)
    value["showcase"] = deepcopy(DEFAULT_SHOWCASE)
    return value


def content() -> dict:
    from .landing_workspace import DEFAULT_CONTENT
    return {**deepcopy(DEFAULT_CONTENT), "app_screens": deepcopy(DEFAULT_SCREENS)}


def catalog() -> dict:
    from .landing_workspace import landing_catalog, sha256_json
    value = deepcopy(landing_catalog())
    value.update(template_id=TEMPLATE_ID, template_version=1, visual_slots=list(VISUAL_SLOTS),
                 section_order=["hero", "features", "benefit_checklist", "app_screens", "visual_break", "social_proof", "cta", "faq", "contacts"])
    value["components"] = [c for c in value["components"] if c["role"] != "app_feature"]
    value["components"][0]["setting_ids"].append("configuration.presentation.language")
    for component in value["components"]:
        component["setting_ids"] = [path for path in component["setting_ids"] if path not in {
            "configuration.visual_mode", "configuration.presentation.hero_focus"}]
    value["components"].append({"component_id": "app_showcase.screens", "role": "app_screens", "setting_ids": ["content.app_screens", "configuration.showcase"]})
    value["setting_definitions"].extend([
        {"setting_id": "configuration.presentation.language", "component_id": "project_landing.theme", "value_type": "enum", "values": ["en", "uk"]},
        {"setting_id": "content.app_screens", "component_id": "app_showcase.screens", "value_type": "structured"},
        {"setting_id": "configuration.showcase", "component_id": "app_showcase.screens", "value_type": "structured"},
    ])
    editable = {path for component in value["components"] for path in component["setting_ids"]}
    value["setting_definitions"] = [item for item in value["setting_definitions"] if item["setting_id"] in editable]
    value["sha256"] = sha256_json({"configuration": configuration(), "content": content(), "slots": VISUAL_SLOTS, "renderer": 1})
    return value


def reference_photo() -> dict:
    from pathlib import Path
    import hashlib, json
    from io import BytesIO
    from PIL import Image
    root = Path(__file__).parent / "studio_assets" / "app-showcase"
    item = next(item for item in json.loads((root / "manifest.json").read_text())["assets"] if item["file"] == "lifestyle.jpg")
    data = (root / item["file"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise RuntimeError("Reference photo digest mismatch")
    output = BytesIO()
    with Image.open(BytesIO(data)) as image:
        image.convert("RGB").save(output, format="PNG")
    return {"bytes": output.getvalue(), "mime_type": "image/png", "source": {"origin": "registered_reference", "asset_id": "showcase_lifestyle", "source_url": item["source_url"], "source_sha256": item["sha256"]}}


def enhanced_configuration():
    from .landing_marketing import DEFAULT_CONFIGURATION
    value = configuration()
    value["marketing"] = deepcopy(DEFAULT_CONFIGURATION)
    return value


def enhanced_content():
    from .landing_marketing import DEFAULT_CONTENT
    return {**content(), "marketing": deepcopy(DEFAULT_CONTENT)}


def enhanced_catalog():
    from .landing_workspace import sha256_json
    value = catalog()
    value["template_version"] = 2
    value["visual_slots"] = [*VISUAL_SLOTS, "walkthrough_visual"]
    value["sha256"] = sha256_json({"configuration": enhanced_configuration(), "content": enhanced_content(), "renderer": 2})
    return value
