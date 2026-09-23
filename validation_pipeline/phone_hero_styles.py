"""Bounded appearance defaults for owner-directed Studio artwork."""

from __future__ import annotations

from typing import Any, Mapping


PHONE_HERO_CREATIVE_DIRECTION_SCHEMA = "ptw.studio.phone-hero-direction.v1"

# These are server-owned prompt instructions.  The browser receives only the
# stable identifiers and supplies its own localized labels.
PHONE_HERO_STYLE_DIRECTIVES: dict[str, str] = {
    "business_professional": (
        "Credible, polished commercial imagery with precise composition, restrained "
        "premium colour, and clear professional lighting."
    ),
    "ultra_realistic_lifestyle": (
        "High-fidelity natural product/lifestyle imagery with authentic materials, "
        "believable light, and authentic everyday context."
    ),
    "cinematic": "Filmic light, confident depth, intentional framing, and restrained cinematic colour grading.",
    "premium_editorial": "Refined editorial art direction, luxury material detail, and a deliberate premium composition.",
    "contemporary_3d": "Tactile contemporary 3D forms, dimensional materials, and polished CGI depth.",
    "minimal_sculptural": "A minimal sculptural composition with only a few bold forms and generous negative space.",
    "artistic_illustration": "Expressive premium illustration with a coherent crafted visual language and clean focal hierarchy.",
    "playful_balloons": "Optimistic inflated objects, buoyant balloon-like forms, and playful but polished colour.",
    "tactile_handmade": "Handmade tactile materials such as paper, clay, textile, or crafted collage, with premium finish.",
    "futuristic_tech": "Luminous technology styling and optical depth while preserving the requested subject.",
}

PHONE_HERO_BACKGROUND_DIRECTIVES: dict[str, str] = {
    "scene": (
        "Place the focal subject in a contextual but uncluttered supporting scene or backdrop; "
        "preserve the complete requested interaction within the visible crop."
    ),
    "isolated_key_element": (
        "Show the complete focal subject or interaction on a clean off-white or brand-tinted tonal field, "
        "without unnecessary scenery; retain every object needed for the action. Use a solid tonal field unless transparency is explicitly requested."
    ),
}


def phone_hero_direction_options() -> dict[str, Any]:
    """Public bounded option identifiers for Studio creation controls."""

    return {
        "schema": PHONE_HERO_CREATIVE_DIRECTION_SCHEMA,
        "styles": list(PHONE_HERO_STYLE_DIRECTIVES),
        "backgrounds": list(PHONE_HERO_BACKGROUND_DIRECTIVES),
    }


def normalize_phone_hero_creative_direction(value: Mapping[str, Any]) -> dict[str, str]:
    """Validate and canonicalize one saved Phone Metrics creative direction."""

    if not isinstance(value, Mapping) or set(value) != {"schema", "style", "background"}:
        raise ValueError("Phone Metrics creative direction fields are invalid")
    if value["schema"] != PHONE_HERO_CREATIVE_DIRECTION_SCHEMA:
        raise ValueError("Phone Metrics creative direction schema is invalid")
    style = str(value["style"])
    background = str(value["background"])
    if style not in PHONE_HERO_STYLE_DIRECTIVES:
        raise ValueError("Phone Metrics creative direction style is invalid")
    if background not in PHONE_HERO_BACKGROUND_DIRECTIVES:
        raise ValueError("Phone Metrics creative direction background is invalid")
    return {
        "schema": PHONE_HERO_CREATIVE_DIRECTION_SCHEMA,
        "style": style,
        "background": background,
    }


def phone_hero_direction_prompt(value: Mapping[str, Any]) -> str:
    """Expand a validated creative direction into prompt-safe visual guidance."""

    direction = normalize_phone_hero_creative_direction(value)
    return " ".join((
        f"Selected visual style: {PHONE_HERO_STYLE_DIRECTIVES[direction['style']]}",
        f"Selected background treatment: {PHONE_HERO_BACKGROUND_DIRECTIVES[direction['background']]}",
    ))
