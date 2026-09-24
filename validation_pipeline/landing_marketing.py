"""Optional, shared marketing sections. Absent blocks preserve historical pages."""
from copy import deepcopy
from colorsys import rgb_to_hsv
from urllib.parse import urlsplit

GRADIENTS = [
    {"id": "ocean", "en": "Ocean · clear & connected", "uk": "Океан · ясність і зв’язок", "start": "#347ff0", "end": "#08cdb3"},
    {"id": "aurora", "en": "Aurora · calm & mindful", "uk": "Аврора · спокій і увага", "start": "#7562c6", "end": "#51b8ae"},
    {"id": "forest", "en": "Forest · natural & grounded", "uk": "Ліс · природа й рівновага", "start": "#27785c", "end": "#81b875"},
    {"id": "sunrise", "en": "Sunrise · warm & welcoming", "uk": "Світанок · тепло і турбота", "start": "#da6e45", "end": "#efa663"},
    {"id": "rose", "en": "Rose · gentle & personal", "uk": "Троянда · ніжність і турбота", "start": "#bd4f83", "end": "#e7a08d"},
    {"id": "electric", "en": "Electric · bold & inventive", "uk": "Електрик · сміливість і новизна", "start": "#514bea", "end": "#b560da"},
    {"id": "sky", "en": "Sky · open & reliable", "uk": "Небо · відкритість і довіра", "start": "#176eac", "end": "#55b7d0"},
    {"id": "earth", "en": "Earth · crafted & enduring", "uk": "Земля · майстерність і сталість", "start": "#986748", "end": "#c7a77c"},
    {"id": "midnight", "en": "Midnight · precise & premium", "uk": "Північ · точність і якість", "start": "#263751", "end": "#577c8d"},
    {"id": "citrus", "en": "Citrus · fresh & energetic", "uk": "Цитрус · свіжість і енергія", "start": "#64893d", "end": "#b8be51"},
]
DEFAULT_CONFIGURATION = {"gradient_id": "ocean", "logo_color": "#ffffff", "motifs_enabled": True,
    "motif_opacity": .09, "carousel_enabled": True, "carousel_autoplay": True, "carousel_speed": 6,
    "comparison_enabled": True, "walkthrough_enabled": True, "benefits_enabled": True,
    "reference_reviews_enabled": True, "cta_enabled": True, "footer_enabled": True,
    "downloads_enabled": True, "missing_store_target": "contacts"}
DEFAULT_CONTENT = {"introduction": "", "comparison_heading": "", "comparison_rows": [{"text": "", "enabled": True} for _ in range(6)],
    "walkthrough_heading": "", "walkthrough_steps": [{"title": "", "description": "", "enabled": True} for _ in range(4)],
    "walkthrough_visual_direction": "", "benefits_heading": "", "benefits_supporting": "", "benefit_highlight_title": "", "benefit_highlight_text": "",
    "values": [{"title": "", "description": "", "enabled": True} for _ in range(4)],
    "cta_heading": "", "cta_text": "", "store_label": "", "apple_url": "", "google_url": "", "privacy_url": "", "terms_url": ""}
TEXT_LIMITS = {"introduction": 360, "comparison_heading": 140, "walkthrough_heading": 140,
    "walkthrough_visual_direction": 600, "benefits_heading": 140, "benefits_supporting": 300,
    "benefit_highlight_title": 90, "benefit_highlight_text": 200, "cta_heading": 180, "cta_text": 300, "store_label": 60}
URL_FIELDS = ("apple_url", "google_url", "privacy_url", "terms_url")


def normalize_configuration(value):
    import math
    from .landing_workspace import _object, _color
    value = _object(value, set(DEFAULT_CONFIGURATION), "marketing configuration")
    result = deepcopy(value)
    if value["gradient_id"] not in {g["id"] for g in GRADIENTS}:
        raise ValueError("Landing gradient is invalid")
    result["logo_color"] = _color(value["logo_color"], "logo color")
    for key, default in DEFAULT_CONFIGURATION.items():
        if isinstance(default, bool) and type(value[key]) is not bool:
            raise ValueError(f"Landing {key} must be boolean")
    for key, low, high in (("motif_opacity", .03, .25), ("carousel_speed", 3, 12)):
        n = value[key]
        if type(n) not in (int, float) or not math.isfinite(n) or not low <= n <= high:
            raise ValueError(f"Landing {key} is out of bounds")
    if value["missing_store_target"] not in ("contacts", "hide"):
        raise ValueError("Landing missing store target is invalid")
    return result


def normalize_content(value):
    from .landing_workspace import _object, _text
    value = _object(value, set(DEFAULT_CONTENT), "marketing content")
    result = {key: _text(value[key], key, 0, limit) for key, limit in TEXT_LIMITS.items()}
    for key in URL_FIELDS:
        result[key] = _text(value[key], key, 0, 2048)
        if not result[key]:
            continue
        url = urlsplit(result[key])
        expected = {"apple_url": "apps.apple.com", "google_url": "play.google.com"}.get(key)
        if url.scheme != "https" or not url.hostname or url.username or url.password or (expected and url.hostname != expected):
            raise ValueError(f"Landing {key} requires a valid HTTPS destination")
    for key, count, limits in (("comparison_rows", 6, {"text": 220}), ("walkthrough_steps", 4, {"title": 120, "description": 300}), ("values", 4, {"title": 90, "description": 220})):
        if not isinstance(value[key], list) or len(value[key]) != count:
            raise ValueError(f"Landing {key} requires {count} items")
        result[key] = []
        for item in value[key]:
            item = _object(item, {*limits, "enabled"}, key)
            if type(item["enabled"]) is not bool:
                raise ValueError("Landing item visibility must be boolean")
            result[key].append({"enabled": item["enabled"], **{k: _text(item[k], k, 0, limit) for k, limit in limits.items()}})
    return result


def _luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))


def initial_logo_color(color, gradient):
    """Keep an inherited color when legible; this never runs on saved owner edits."""
    def contrast(candidate):
        foreground = _luminance(candidate)
        return min((max(foreground, _luminance(gradient[k])) + .05) /
                   (min(foreground, _luminance(gradient[k])) + .05) for k in ("start", "end"))
    if contrast(color) >= 3:
        return color
    return max(("#ffffff", "#102335"), key=contrast)


def initial_design(brief, source):
    """Brief-domain aura first, nearest source-logo hue when domain is unspecified."""
    import json, re
    text = json.dumps(brief, ensure_ascii=False).casefold()
    groups = [("aurora", r"wellness|mindful|meditat|aura|аур[аи]|медита|спок[іо]"), ("forest", r"garden|organic|ecolog|сад|еколог|рослин"),
        ("sunrise", r"food|kitchen|travel|їж|кух|подорож"), ("rose", r"beauty|skin|краса|космет"), ("electric", r"gaming|software|coding|ігр|програм"),
        ("sky", r"health|medicine|ліки|медич"), ("earth", r"craft|furniture|мебл|ремесл"), ("midnight", r"finance|security|фінанс|безпек"), ("citrus", r"fitness|sport|спорт|фітнес")]
    config = source.get("configuration") or {}
    logo = config.get("logo") or {}
    color = logo.get("symbol_color") or logo.get("name_color")
    if not color and isinstance(config.get("components"), list):
        color = next((c.get("props", {}).get("symbol_color") for c in config["components"] if c.get("type") == "natal_logo"), None)
    valid = isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color)
    selected = next((name for name, pattern in groups if re.search(pattern, text)), None)
    if selected is None and valid and rgb_to_hsv(*(int(color[i:i+2], 16)/255 for i in (1,3,5)))[1] > .12:
        def hue(hex): return rgb_to_hsv(*(int(hex[i:i+2], 16)/255 for i in (1,3,5)))[0]
        selected = min(GRADIENTS, key=lambda g: min(abs(hue(g["start"])-hue(color)), 1-abs(hue(g["start"])-hue(color))))["id"]
    result = deepcopy(DEFAULT_CONFIGURATION)
    gradient = next(g for g in GRADIENTS if g["id"] == (selected or "ocean"))
    result.update(gradient_id=gradient["id"], logo_color=initial_logo_color(color.lower() if valid else "#ffffff", gradient))
    return result


def extend_catalog(catalog):
    value = deepcopy(catalog)
    value["gradient_presets"] = deepcopy(GRADIENTS)
    value["components"].append({"component_id": "landing.marketing", "role": "marketing", "setting_ids": ["configuration.marketing", "content.marketing"]})
    value["setting_definitions"].extend({"setting_id": path, "component_id": "landing.marketing", "value_type": "structured"} for path in ("configuration.marketing", "content.marketing"))
    return value


def required_slots(base, configuration):
    base = tuple(slot for slot in base if slot != "walkthrough_visual")
    return (*base, "walkthrough_visual") if configuration.get("marketing", {}).get("walkthrough_enabled") else tuple(base)


def approval_ready(configuration, content):
    c, v = configuration.get("marketing"), content.get("marketing")
    if not c:
        return
    if not v:
        raise ValueError("Complete the additional sections in Landing Studio")
    for flag, key, fields in (("comparison_enabled", "comparison_rows", ("text",)), ("walkthrough_enabled", "walkthrough_steps", ("title", "description")), ("benefits_enabled", "values", ("title", "description"))):
        if c[flag] and any(item["enabled"] and not all(item[k] for k in fields) for item in v[key]):
            raise ValueError(f"Complete or hide the missing {key} in Landing Studio")
    if c["walkthrough_enabled"] and len(v["walkthrough_visual_direction"]) < 8:
        raise ValueError("Provide a walkthrough mockup direction")
