"""Landing component presets and shared Post image art directions."""
from __future__ import annotations

from .phone_hero_styles import PHONE_HERO_STYLE_DIRECTIVES

PHONE_MOCKUP_OPTIONS = {"theme": ["light", "dark", "glass"], "layout": ["overview", "booking", "checklist"]}
DEFAULT_PHONE_MOCKUP = {"theme": "light", "layout": "overview"}
APP_FEATURE_LIMITS = {"title": 72, "description": 160, "action_label": 36, "label": 60, "value": 80}
DEFAULT_APP_FEATURE = {"title": "", "description": "", "action_label": "", "items": [{"label": "", "value": ""} for _ in range(3)]}

DEFAULT_COMPONENTS = {
    "button_style": "filled", "button_shape": "rounded",
    "button_color": "#1f55d9", "button_text_color": "#ffffff",
    "card_style": "filled", "icon_style": "soft", "contact_style": "contrast",
}
DEFAULT_IMAGE_DIRECTIONS = {
    slot: {"style": "premium_editorial", "background": "scene"}
    for slot in ("hero_visual", "visual_break_visual")
}
LANDING_BACKGROUND_DIRECTIVES = {
    "scene": "Place the focal subject in a contextual, uncluttered supporting scene. Keep scenery subordinate to the focal subject.",
    "isolated_key_element": "Show one isolated focal object on a clean off-white or brand-tinted tonal field, with no additional objects or scenery; do not use transparency.",
}
COMPONENT_OPTIONS = {
    "button_style": ["filled", "outlined", "elevated", "text"],
    "button_shape": ["square", "rounded", "pill"],
    "card_style": ["filled", "outlined", "elevated", "minimal"],
    "icon_style": ["soft", "solid", "line", "hidden"],
    "contact_style": ["contrast", "surface", "accent"],
}
THEME_PRESETS = [
    {"id": "studio", "en": "Studio", "uk": "Студія", "description_en": "Crisp blue, confident type, clean cards", "description_uk": "Чіткий синій, виразний шрифт, лаконічні картки",
     "theme": {"background_color": "#f7f8fc", "surface_color": "#ffffff", "text_color": "#182238", "accent_color": "#1f55d9", "font_family": "Manrope", "heading_font_family": "Manrope", "corner_radius": 20},
     "components": DEFAULT_COMPONENTS, "faq": {"style": "divided"}},
    {"id": "editorial", "en": "Editorial", "uk": "Редакційна", "description_en": "Warm paper, serif headlines, fine borders", "description_uk": "Теплий папір, антиква, тонкі контури",
     "theme": {"background_color": "#f7f3eb", "surface_color": "#fffcf6", "text_color": "#322b25", "accent_color": "#87502d", "font_family": "Source Sans 3", "heading_font_family": "Lora", "corner_radius": 4},
     "components": {**DEFAULT_COMPONENTS, "button_style": "outlined", "button_shape": "square", "button_color": "#87502d", "button_text_color": "#ffffff", "card_style": "minimal", "icon_style": "line", "contact_style": "surface"}, "faq": {"style": "divided"}},
    {"id": "soft", "en": "Soft bloom", "uk": "М’якість", "description_en": "Fresh sage, rounded surfaces, gentle depth", "description_uk": "Свіжа шавлія, округлі форми, м’які тіні",
     "theme": {"background_color": "#f0f6f2", "surface_color": "#ffffff", "text_color": "#193c32", "accent_color": "#28674f", "font_family": "Manrope", "heading_font_family": "Manrope", "corner_radius": 32},
     "components": {**DEFAULT_COMPONENTS, "button_style": "elevated", "button_shape": "pill", "button_color": "#28674f", "card_style": "elevated", "icon_style": "solid", "contact_style": "accent"}, "faq": {"style": "cards"}},
]


def design_catalog():
    return {"phone_mockup_defaults": DEFAULT_PHONE_MOCKUP, "phone_mockup_options": PHONE_MOCKUP_OPTIONS, "app_feature_limits": APP_FEATURE_LIMITS, "brand": "Natal", "component_defaults": DEFAULT_COMPONENTS,
            "component_options": COMPONENT_OPTIONS, "theme_presets": THEME_PRESETS,
            "image_direction_defaults": DEFAULT_IMAGE_DIRECTIONS,
            "image_direction_options": {"styles": list(PHONE_HERO_STYLE_DIRECTIVES), "backgrounds": list(LANDING_BACKGROUND_DIRECTIVES)}}
