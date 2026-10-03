"""Bounded, non-coding agent input/output contract for Studio manual editing."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Mapping
from uuid import UUID

from .image_reference import decode_reference
from .provider import StructuredContractError
from .phone_hero_styles import (
    PHONE_HERO_BACKGROUND_DIRECTIVES,
    PHONE_HERO_STYLE_DIRECTIVES,
)


STUDIO_MANUAL_AGENT_PROMPT_VERSION = "studio-manual-agent-v8"
STUDIO_MANUAL_AGENT_REASONING_EFFORT = "high"
MAX_AGENT_SCREENSHOTS = 4
MAX_AGENT_SCREENSHOT_BYTES = 20 * 1024 * 1024
MAX_AGENT_HISTORY_MESSAGES = 4
MAX_AGENT_HISTORY_BYTES = 4 * 1024
MAX_AGENT_EDITS = 64


class StudioManualAgentProviderError(RuntimeError):
    """Sanitized provider failure that is not a Studio state conflict."""

    def __init__(self, *, timed_out: bool, contract_failed: bool = False) -> None:
        self.timed_out = timed_out
        self.contract_failed = contract_failed
        super().__init__(
            "Studio Agent could not prepare its bounded request; the draft was not changed."
            if contract_failed else
            "Studio Agent timed out before returning a validated edit; the draft was not changed."
            if timed_out else
            "Studio Agent provider could not return a validated edit; the draft was not changed."
        )


def studio_manual_agent_provider_error(error: Exception) -> StudioManualAgentProviderError:
    attempts = getattr(error, "attempts", ())
    error_types = {
        str(item.get("error_type") or "")
        for item in attempts if isinstance(item, Mapping)
    }
    timed_out = (
        isinstance(error, TimeoutError)
        or "TimeoutExpired" in error_types
        or "TimeoutError" in error_types
    )
    return StudioManualAgentProviderError(
        timed_out=timed_out, contract_failed=isinstance(error, StructuredContractError),
    )


def _normalized_instruction(value: str) -> str:
    return " ".join(value.casefold().replace("’", "'").split())


def _contains_any(value: str, fragments: tuple[str, ...]) -> bool:
    return any(fragment in value for fragment in fragments)


def manual_agent_request_constraints(
    *, surface: str, message: str, image_slots: list[str],
) -> dict[str, Any]:
    """Resolve a few high-impact compound intents before provider inference.

    The provider still translates the complete natural-language request. These
    constraints cover interactions where individually valid controls can make
    the requested result invisible or semantically backwards.
    """

    normalized = _normalized_instruction(message)
    phone_removed = _contains_any(normalized, (
        "remove the phone", "remove phone", "hide the phone", "hide phone",
        "without the phone", "without phone", "phone removed",
        "прибери телефон", "прибрати телефон", "забери телефон",
        "сховай телефон", "видали телефон", "без телефону",
        "убери телефон", "скрой телефон", "удали телефон", "без телефона",
    ))
    generation_negated = _contains_any(normalized, (
        "do not generate", "don't generate", "dont generate",
        "without generating", "no image generation",
        "не генеруй", "не генерувати", "без генерації",
        "не генерируй", "не генерировать", "без генерации",
    ))
    explicit_image_operation = _contains_any(normalized, (
        "generate an image", "generate image", "generate artwork",
        "replace the image", "replace image", "replace the artwork",
        "enhance the image", "enhance image", "enhance the artwork",
        "згенеруй зображ", "згенерувати зображ", "згенеруй картин",
        "заміни зображ", "замінити зображ", "покращ зображ",
        "сгенерируй изображ", "замени изображ", "улучши изображ",
    ))
    natural_image_transformation = _contains_any(normalized, (
        "image look like", "picture look like", "artwork look like",
        "image should show", "picture should show", "artwork should show",
        "show in the image", "show in the picture", "depict in the image",
        "на картинці вигляд", "на картинке вид", "на зображенні вигляд",
        "зображення має показ", "картинка має показ", "покажи на картин",
        "покажи на зображ", "зобрази на картин", "зобрази на зображ",
        "изображение должно показ", "картинка должна показ",
        "покажи на изображ", "изобрази на изображ",
    )) or (
        _contains_any(normalized, ("зроби так", "сделай так", "make it"))
        and _contains_any(normalized, (
            "image", "picture", "artwork", "картин", "зображ", "изображ",
        ))
        and _contains_any(normalized, ("look", "show", "вигляд", "показ", "вид"))
    )
    image_change = (
        not generation_negated
        and (explicit_image_operation or natural_image_transformation)
    )
    remove_one_logo = bool(re.search(
        r"(?:remove|hide|прибери|прибрати|забери|сховай|видали|"
        r"убери|скрой|удали)\s+(?:one|один|одну|1)\s+(?:natal\s+)?логотип|"
        r"(?:remove|hide)\s+(?:one|1)\s+(?:natal\s+)?logo",
        normalized,
    ))
    numeric_metrics = (
        _contains_any(normalized, (
            "more numbers", "more figures", "use numbers", "numeric values",
            "більше цифр", "більше чисел", "використай цифр", "додай цифр",
            "больше цифр", "больше чисел", "используй цифр", "добавь цифр",
        ))
        and _contains_any(normalized, (
            "metric", "card", "bottom button", "lower button",
            "метрик", "карт", "нижн", "кноп",
        ))
    )

    required_outcomes: list[dict[str, Any]] = []
    if surface == "post:phone_metrics" and image_change and "phone_screen" in image_slots:
        required_outcomes.append({
            "id": "change_visible_artwork",
            "required_image_action_slot": "phone_screen",
            "instruction": (
                "The owner described a desired change to the pixels/content of the image. "
                "This is an explicit image operation even without the word ‘generate’; return "
                "one image action whose visual direction represents that requested subject."
            ),
        })
    if surface == "post:phone_metrics" and phone_removed and image_change:
        required_outcomes.append({
            "id": "artwork_without_phone_hardware",
            "required_settings": {
                "configuration.device.enabled": True,
                "configuration.visual_mode": "image",
            },
            "instruction": (
                "The owner wants the requested artwork to remain visible while phone hardware/UI "
                "is removed. Use Image only; device.enabled must remain true because it owns the "
                "artwork area. Setting device.enabled=false would hide the requested image too."
            ),
        })
    if surface == "post:phone_metrics" and remove_one_logo:
        required_outcomes.append({
            "id": "keep_one_natal_logo",
            "required_settings": {
                "configuration.logo.enabled": True,
                "configuration.phone_screen.logo_enabled": False,
            },
            "instruction": (
                "With no location specified, keep the outer Post Natal identity and hide the "
                "duplicate in-phone Natal mark so restoring Phone mode does not restore two logos."
            ),
        })
    if surface == "post:phone_metrics" and numeric_metrics:
        required_outcomes.append({
            "id": "numeric_lower_metric_cards",
            "required_settings": {
                "configuration.metric_cards[*].enabled": True,
                "content.stats[*].value": "a numeral-bearing value on every card",
            },
            "instruction": (
                "The lower three blocks are Metric cards, not in-phone buttons. Keep value as the "
                "prominent numeral-bearing field and label as its short descriptor. If the owner "
                "did not supply quantities, propose plausible domain-specific numeric benefit hypotheses "
                "for later validation. Do not label them as measured results or use generic numbered steps."
            ),
        })
    return {
        "schema": "ptw.studio.agent-request-constraints.v1",
        "instructions": [
            "Treat each required outcome as an end-state invariant, not as optional advice.",
            "Resolve interactions across all clauses, then verify every requested result is visible in the final state.",
        ],
        "required_outcomes": required_outcomes,
    }


def validate_manual_agent_semantics(
    *, surface: str, constraints: Mapping[str, Any],
    configuration: Mapping[str, Any], content: Mapping[str, Any],
    image_actions: list[dict[str, Any]],
) -> None:
    """Reject schema-valid responses whose combined controls defeat the request."""

    outcome_ids = {
        str(item.get("id")) for item in constraints.get("required_outcomes", [])
        if isinstance(item, Mapping)
    }
    if "change_visible_artwork" in outcome_ids and not image_actions:
        raise ValueError(
            "The owner explicitly requested a visible artwork-content change; return one image action."
        )
    if surface != "post:phone_metrics":
        return
    device = configuration.get("device")
    phone_screen = configuration.get("phone_screen")
    logo = configuration.get("logo")
    metric_cards = configuration.get("metric_cards")
    stats = content.get("stats")
    device_enabled = isinstance(device, Mapping) and device.get("enabled") is True
    visual_mode = configuration.get("visual_mode", "phone")

    if image_actions and not device_enabled:
        raise ValueError(
            "A phone_screen image action would be invisible because configuration.device.enabled "
            "is false; keep the artwork area enabled and use visual_mode=image when removing hardware."
        )
    if "change_visible_artwork" in outcome_ids and not any(
        action.get("slot") == "phone_screen" for action in image_actions
    ):
        raise ValueError(
            "The owner explicitly requested a visible artwork-content change; return one phone_screen image action."
        )
    if "artwork_without_phone_hardware" in outcome_ids and (
        not device_enabled or visual_mode != "image"
    ):
        raise ValueError(
            "Removing phone hardware while keeping requested artwork visible requires "
            "configuration.device.enabled=true and configuration.visual_mode=image."
        )
    if "keep_one_natal_logo" in outcome_ids and not (
        isinstance(logo, Mapping) and logo.get("enabled") is True
        and isinstance(phone_screen, Mapping) and phone_screen.get("logo_enabled") is False
    ):
        raise ValueError(
            "Removing one unspecified duplicate logo requires the outer Post logo enabled and the in-phone logo disabled."
        )
    if "numeric_lower_metric_cards" in outcome_ids:
        if not isinstance(metric_cards, list) or len(metric_cards) != 3 or any(
            not isinstance(card, Mapping) or card.get("enabled") is not True
            for card in metric_cards
        ):
            raise ValueError("The requested lower three Metric cards must all remain visible.")
        if not isinstance(stats, list) or len(stats) != 3 or any(
            not isinstance(stat, Mapping)
            or not any(character.isdigit() for character in str(stat.get("value") or ""))
            for stat in stats
        ):
            raise ValueError(
                "The owner requested more numbers in the lower Metric cards; every content.stats value must contain a numeral."
            )


# This layer deliberately describes controls rather than inventing another
# editor schema.  The catalog remains the authority for the exact currently
# available setting paths; this contract gives those paths their owner-facing
# meaning so a structured provider does not have to infer it from IDs alone.
_SURFACE_COMPONENT_CONTRACTS: dict[str, dict[str, dict[str, Any]]] = {
    "post:phone_metrics": {
        "phone_metrics.background": {
            "name": "Background",
            "purpose": "Sets the material canvas behind the Post copy and device area.",
            "visible_result": "Changes the main and copy-area texture treatments.",
            "dependencies": "Textures are bounded renderer presets; the canvas colour and device geometry remain fixed.",
            "controllers": [{"name": "Textures", "allowed_values": "main: none, grain, concrete, or travertine; copy area: the same bounded presets."}],
        },
        "phone_metrics.brand": {
            "name": "Natal identity",
            "purpose": "Controls the Post-level canonical Natal lock-up.",
            "visible_result": "Shows or hides the lock-up and changes its bounded symbol/name colours.",
            "dependencies": "The in-phone Natal lock-up is controlled separately by the Device component.",
            "controllers": [{"name": "Brand", "allowed_values": "visibility and six-digit hexadecimal symbol/name colours."}],
        },
        "phone_metrics.offer": {
            "name": "Eyebrow",
            "purpose": "Displays the small label above the headline.",
            "visible_result": "Shows or hides the eyebrow and changes its bounded copy and typography.",
            "dependencies": "Typography is role-specific and does not alter other text roles.",
            "controllers": [{"name": "Eyebrow", "allowed_values": "visibility, bounded copy, catalog font, and 16–42 size."}],
        },
        "phone_metrics.hero_title": {
            "name": "Hero title",
            "purpose": "Displays the primary Post message.",
            "visible_result": "Shows or hides the headline and changes bounded copy, typography, highlight colour, and inline bold/highlight markup.",
            "dependencies": "Inline markup is editor syntax only and never renders as delimiters.",
            "controllers": [{"name": "Headline", "allowed_values": "visibility, bounded copy, catalog font, 42–110 size, and six-digit highlight colour."}],
        },
        "phone_metrics.supporting_text": {
            "name": "Supporting text",
            "purpose": "Explains the Post message beneath the headline.",
            "visible_result": "Shows or hides supporting copy and changes its typography, highlight colour, and inline markup.",
            "dependencies": "Inline markup is editor syntax only and never renders as delimiters.",
            "controllers": [{"name": "Supporting copy", "allowed_values": "visibility, bounded copy, catalog font, 20–46 size, and six-digit highlight colour."}],
        },
        "phone_metrics.device": {
            "name": "Device and app screen",
            "purpose": "Controls the optional iPhone/device area and its renderer-owned app screen.",
            "visible_result": "Can hide the device entirely, show the framed phone with its UI, or show only selected artwork without phone hardware or interface.",
            "dependencies": "device.enabled=false removes the complete visual area, including its artwork. visual_mode=image keeps device.enabled=true but removes phone hardware/UI and shows only the selected artwork. If one request both removes the phone and asks what the picture should show, Image only is the required visible result. The device frame and system chrome are fixed.",
            "controllers": [
                {"name": "Device visibility", "allowed_values": "true keeps the complete visual area available; false removes that entire area, including artwork, without generating an image."},
                {"name": "Visual mode", "allowed_values": "phone shows Phone frame & buttons; image shows the selected artwork while removing phone hardware, system chrome, Natal screen mark, screen title, and app buttons."},
                {"name": "App screen", "allowed_values": "bounded screen texture, in-phone Natal visibility, title visibility, bounded title, and three independently visible app buttons with Filled/Elevated/Outlined/Text styles and Square/Rounded/Pill shapes. These controls are not the three lower Post Metric cards."},
            ],
        },
        "phone_metrics.metrics": {
            "name": "Metric cards",
            "purpose": "Displays the three large lower Post cards, each with a prominent value and a smaller label.",
            "visible_result": "Changes card visibility, value/label copy, typography, colours, style, and shape; remaining cards redistribute deterministically.",
            "dependencies": "The fixed component has exactly three cards and cannot add more. ‘Lower/bottom buttons/cards’ normally refers to these Post Metric cards, not the buttons inside the phone. Keep requested numbers in content.stats[*].value and descriptors in content.stats[*].label. Preserve supplied figures; otherwise use domain-specific numeric hypotheses, never claimed measured evidence.",
            "controllers": [{"name": "Metrics", "allowed_values": "per-card visibility; prominent content.stats[*].value plus descriptive content.stats[*].label; Filled or Outlined; Square, Rounded, or Pill; bounded typography and colours."}],
        },
        "phone_metrics.cta": {
            "name": "Call to action",
            "purpose": "Displays the full-width Post CTA band.",
            "visible_result": "Shows or hides the band and changes its bounded copy, typography, and colours.",
            "dependencies": "Empty CTA copy removes the whole band; this does not configure an advertising destination.",
            "controllers": [{"name": "CTA", "allowed_values": "visibility, 0–60 character copy, catalog font, 20–52 size, and six-digit colours."}],
        },
    },
    "landing:project_landing": {
        "project_landing.theme": {
            "name": "Theme and component treatment",
            "purpose": "Page palette, typography, spacing and component treatments.",
            "visible_result": "Applies Studio, Editorial, or Soft bloom design directions, or bounded individual colours/fonts/radius/spacing/button/card/icon/contact treatments.",
            "dependencies": "Presets preserve copy, crops and images.",
            "controllers": [{"name": "Theme", "allowed_values": "Studio, Editorial, Soft bloom; catalog fonts; 0–48 corner radius; 0.85–1.15 heading scale; compact/comfortable/airy spacing; bounded component styles."}],
        },
        "project_landing.hero": {
            "name": "Hero",
            "purpose": "Main title, supporting copy, CTA and artwork.",
            "visible_result": "Changes bounded title/supporting/CTA copy, alignment, artwork placement/crop, CTA destination, and image direction.",
            "dependencies": "Image mode retains artwork without phone hardware or UI.",
            "controllers": [{"name": "Hero", "allowed_values": "left/center alignment; left/right/below image placement; contacts, Telegram bot, email, or phone CTA target; bounded crop focus."}],
        },
        "project_landing.app_feature": {
            "name": "App feature",
            "purpose": "Hero's fixed three-row app demonstration.",
            "visible_result": "Changes phone screen theme/layout and its bounded title, description, action label, and three label/detail rows.",
            "dependencies": "Phone mode shows the frame; image mode shows artwork only. This is a demonstration.",
            "controllers": [{"name": "App screen", "allowed_values": "Light, Dark, or Glass theme; Overview, Booking, or Checklist layout; fixed three rows."}],
        },
        "project_landing.features": {
            "name": "Features",
            "purpose": "Three feature cards and their copy.",
            "visible_result": "Changes bounded card copy and switches the group between three columns and a stacked layout.",
            "dependencies": "Keep exactly three cards.",
            "controllers": [{"name": "Feature cards", "allowed_values": "three_columns or stacked; bounded title and description for each fixed card."}],
        },
        "project_landing.social_proof": {
            "name": "Feedback cards",
            "purpose": "Editable feedback section copy and presentation.",
            "visible_result": "Changes the heading, each card's statement and attribution, and the card or quote presentation.",
            "dependencies": "Keep feedback relevant to this Project and preserve the existing card count unless the owner explicitly changes it in Studio.",
            "controllers": [{"name": "Feedback cards", "allowed_values": "heading; bounded statement and attribution for each card; cards or quote layout."}],
        },
        "project_landing.visual_break": {
            "name": "Visual break",
            "purpose": "Supporting artwork, crop and direction.",
            "visible_result": "Changes height, crop focus, visual direction, and the selected/generated artwork.",
            "dependencies": "Generate only for requested image changes.",
            "controllers": [{"name": "Supporting artwork", "allowed_values": "small, medium, or large; bounded crop focus and owner-directed visual direction."}],
        },
        "project_landing.contacts": {
            "name": "Contact panel",
            "purpose": "Contact heading, supporting copy and layout.",
            "visible_result": "Changes heading, supporting copy, alignment, CTA target, and shared contact-panel treatment.",
            "dependencies": "Preserve email, phone, Telegram and Instagram endpoints.",
            "controllers": [{"name": "Contact presentation", "allowed_values": "left/center alignment and Contrast/Surface/Accent treatment; no endpoint changes."}],
        },
        "project_landing.faq": {
            "name": "FAQ",
            "purpose": "Three FAQ questions and answers.",
            "visible_result": "Changes bounded question/answer copy and uses divided or card presentation.",
            "dependencies": "Keep exactly three FAQs.",
            "controllers": [{"name": "FAQ", "allowed_values": "divided or cards; bounded copy for each fixed question/answer."}],
        },
    },
}

_STYLE_NAMES = {
    "business_professional": "Business professional",
    "ultra_realistic_lifestyle": "Ultra-realistic lifestyle",
    "cinematic": "Cinematic",
    "premium_editorial": "Premium editorial",
    "contemporary_3d": "Contemporary 3D",
    "minimal_sculptural": "Minimal sculptural",
    "artistic_illustration": "Artistic illustration",
    "playful_balloons": "Playful balloons",
    "tactile_handmade": "Tactile handmade",
    "futuristic_tech": "Futuristic tech",
}
_BACKGROUND_NAMES = {
    "scene": "Scene background",
    "isolated_key_element": "Isolated key element",
}

_STYLE_OPTIONS = [{
    "id": identifier,
    "name": _STYLE_NAMES[identifier],
    "direction": directive,
} for identifier, directive in PHONE_HERO_STYLE_DIRECTIVES.items()]


def agent_control_contract(surface: str, catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Build the semantic agent contract from the current live catalog.

    Missing coverage is deliberately a runtime error: adding a visible Studio
    component must also add its agent explanation instead of silently leaving
    the provider to infer a new controller from an internal identifier.
    """

    declarations = _SURFACE_COMPONENT_CONTRACTS.get(surface)
    if catalog.get("schema") == "ptw.studio.daddy-catalog.v1":
        return {"schema": "ptw.studio.agent-control-contract.v3", "surface": surface,
            "instructions": ["Use the same bounded block controls as the manual editor. Changing preset applies its defaults, preserves copy/assets and then applies your other scalar edits.",
                "Preserve unrelated settings, owner choices, exact Brief/Brand Identity and fixed Natal identity. Never invent claims or performance evidence.",
                "Screen is generated UI; depicted text changes require an image action. Scene, subject, screen, feature and props are independent. No hands in phone imagery."],
            "presets": [{k:v for k,v in item.items() if k != "configuration"} for item in catalog["presets"]],
            "bounds": catalog["bounds"], "options": catalog["enums"]}

    if surface.startswith("post:") and catalog.get("schema") == "ptw.studio.authored-post-catalog.v1":
        declarations = {
            "authored.text": {
                "purpose": "The selected accepted Post template's named text and button fields, each with its semantic role.",
                "dependencies": ["Edit only content.template_text fields. Preserve unrelated legacy Phone Metrics copy; it is not displayed by this template.", "The template owns field count, positions and bullet marks. New fields or layout changes require a new accepted template version."],
            },
            "authored.typography": {
                "purpose": "Independent font family and 12–180px font size for each named text field.",
                "dependencies": ["Use the listed font families and bounds. Fields sharing typography_group must use the same font and size; editing one updates every peer.", "Font changes affect this draft only, leaving the accepted template definition unchanged."],
            },
            "authored.brand": {
                "purpose": "The shared Natal symbol and name colors for every lock-up in this Post.",
                "dependencies": ["Only symbol_color and name_color are editable. Preserve canonical identity, alpha, dimensions and placement."],
            },
        }
        if any(item.get("component_id") == "authored.palette" for item in catalog.get("components", [])):
            declarations["authored.palette"] = {
                "purpose": "The selected template's full-canvas background gradient colors.",
                "dependencies": ["Edit gradient_start and gradient_end as #RRGGBB colors. Preserve fixed badges, cards and registered artwork."],
            }
    if surface == "landing:app_showcase":
        declarations = {key: value for key, value in _SURFACE_COMPONENT_CONTRACTS["landing:project_landing"].items() if key != "project_landing.app_feature"}
        if any("configuration.showcase.hero_body_mode" in item.get("setting_ids", []) for item in catalog.get("components", [])):
            declarations["project_landing.hero"] = {
                **declarations["project_landing.hero"],
                "purpose": "Main title, editable eyebrow, switchable supporting text or exactly three hero bullets, CTA and artwork.",
                "visible_result": "The line above the title uses content.hero.eyebrow. configuration.showcase.hero_body_mode selects text or bullets below the title; content.hero.bullets[0..2] supplies the bullet copy.",
                "dependencies": "Preserve both text and bullets when switching formats. Complete all three bullets before selecting bullets. Image edits need an image action.",
            }
        declarations["app_showcase.screens"] = {
            "purpose": "Three static screen interiors, captions, scale and offset.",
            "dependencies": ["Match app_screen_1/2/3 actions to content.app_screens[index].visual_direction. Depicted UI edits need an image action; external captions are copy.", "Preserve Natal identity and source claims."],
        }
    if declarations is not None and any(item.get("component_id") == "landing.marketing" for item in catalog.get("components", [])):
        declarations = {**declarations, "landing.marketing": {
            "purpose": "Gradients, motifs, carousel, comparison, steps, values, feedback examples, store buttons and footer.",
            "dependencies": ["Use listed gradient presets and per-item enabled toggles. Unsupported copy stays blank for owner completion.", "walkthrough_visual contains complete phones; app_screen slots contain interiors. Match actions to the slot's visual_direction; depicted edits require image actions.", "Use the social_proof cards for visible generated feedback; legacy feedback_examples are used only when those cards are empty. Preserve store and legal URLs. Empty store URLs open early access."],
        }}
    if declarations is None:
        raise ValueError(f"Studio Agent surface contract is unavailable: {surface}")
    catalog_components = list(catalog.get("components") or [])
    catalog_ids = {str(item.get("component_id")) for item in catalog_components}
    if catalog_ids != set(declarations):
        raise RuntimeError("Studio Agent contract does not cover the live component catalog")
    components: list[dict[str, Any]] = []
    for item in catalog_components:
        component_id = str(item["component_id"])
        contract = declarations[component_id]
        components.append({
            "component_id": component_id,
            "purpose": contract["purpose"],
            "dependencies": contract["dependencies"],
        })
    result: dict[str, Any] = {
        "schema": "ptw.studio.agent-control-contract.v3",
        "surface": surface,
        "instructions": [
            "Return only scalar edits needed for the owner's latest request; preserve every omitted path.",
            "Resolve dependencies across all clauses and verify that each requested result remains visible.",
            "Describing what an image should show is an image operation unless explicitly negated.",
            "If the fixed editor cannot represent a request, make no related edit and explain briefly.",
        ],
        "immutable_boundaries": [
            "No new components, code, asset slots, unsupported claims, contacts, or social proof.",
            "Never Save, Approve, Publish, deploy, or modify code.",
        ],
        "components": components,
    }
    result.update({
        "image_style_options": [
            {"id": item["id"], "name": item["name"]} for item in _STYLE_OPTIONS
        ],
        "background_treatments": [{
            "id": identifier, "name": _BACKGROUND_NAMES[identifier],
        } for identifier in PHONE_HERO_BACKGROUND_DIRECTIVES],
    })
    if surface.startswith("landing:"):
        # The skill supplies the shared instructions. Keep the complete live
        # component semantics and values, without repeating that guidance.
        result.pop("instructions")
        result.pop("immutable_boundaries")
        result["image_style_options"] = [item["id"] for item in _STYLE_OPTIONS]
        result["background_treatments"] = list(PHONE_HERO_BACKGROUND_DIRECTIVES)
    if catalog.get("schema") == "ptw.studio.authored-post-catalog.v1":
        result["text_fields"] = deepcopy(catalog["text_fields"])
        result["typography"] = deepcopy(catalog["typography"])
        result["image_dependencies"] = [
            "phone_screen is the shared raw artwork used by this template's mutable image components; it does not mean this Post uses the Phone Metrics layout.",
            "Use the supplied image tools for requested artwork changes. Preserve fixed registered images, badges, Natal marks and component geometry.",
        ]
    if surface == "post:phone_metrics":
        result["owner_phrase_mappings"] = {
            "hide_or_remove_phone_device": {
                "surface": "post:phone_metrics",
                "setting_path": "configuration.device.enabled",
                "value": False,
                "image_action": "none",
                "applies_when": "The owner wants the complete visual area gone and does not request visible artwork in the same instruction.",
            },
            "show_only_artwork_without_phone_or_interface": {
                "surface": "post:phone_metrics",
                "setting_paths": {
                    "configuration.device.enabled": True,
                    "configuration.visual_mode": "image",
                },
                "image_action": "none unless separately requested",
            },
            "remove_phone_and_change_visible_picture": {
                "surface": "post:phone_metrics",
                "setting_paths": {
                    "configuration.device.enabled": True,
                    "configuration.visual_mode": "image",
                },
                "image_action": "one phone_screen action using the requested picture subject",
                "result": "Artwork remains visible without phone hardware, system chrome, or app interface.",
            },
            "remove_one_unspecified_logo": {
                "surface": "post:phone_metrics",
                "setting_paths": {
                    "configuration.logo.enabled": True,
                    "configuration.phone_screen.logo_enabled": False,
                },
                "result": "Keeps the outer Post identity and removes the duplicate in-phone mark.",
            },
            "use_more_numbers_on_lower_cards": {
                "surface": "post:phone_metrics",
                "setting_paths": {
                    "configuration.metric_cards[*].enabled": True,
                    "content.stats[*].value": "numeral-bearing prominent values",
                    "content.stats[*].label": "short descriptors",
                },
                "boundary": "When quantities are missing propose domain-specific numeric hypotheses for later validation, not numbered steps or measured proof.",
            },
            "bring_phone_back": {
                "surface": "post:phone_metrics",
                "setting_paths": {
                    "configuration.device.enabled": True,
                    "configuration.visual_mode": "phone",
                },
                "image_action": "none",
            },
        }
    elif surface == "landing:project_landing":
        result["owner_phrase_mappings"] = {
            "show_only_artwork_without_phone_or_interface": {
                "surface": "landing:project_landing",
                "setting_path": "configuration.visual_mode",
                "value": "image",
                "image_action": "none unless separately requested",
            },
        }
    return result


def _text(value: Any, field: str, minimum: int, maximum: int) -> str:
    result = str(value or "") if field == "message" else " ".join(str(value or "").split())
    if not minimum <= len(result) <= maximum or not result.strip():
        raise ValueError(f"Studio Agent {field} must contain {minimum}-{maximum} characters")
    return result


def manual_agent_request(request: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "request_id", "base_sha256", "message", "history",
        "configuration", "content", "screenshots",
    }
    if not isinstance(request, Mapping) or set(request) != expected:
        raise ValueError("Studio Agent request fields are invalid")
    try:
        request_id = str(UUID(str(request["request_id"])))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("Studio Agent request_id must be a UUID") from error
    base_sha256 = str(request["base_sha256"])
    if len(base_sha256) != 64 or any(character not in "0123456789abcdef" for character in base_sha256):
        raise ValueError("Studio Agent base state digest is invalid")
    if not isinstance(request["configuration"], Mapping) or not isinstance(request["content"], Mapping):
        raise ValueError("Studio Agent requires configuration and content objects")
    history = request["history"]
    if not isinstance(history, list) or len(history) > 8:
        raise ValueError("Studio Agent history supports at most eight messages")
    normalized_history: list[dict[str, str]] = []
    for item in history[-MAX_AGENT_HISTORY_MESSAGES:]:
        if not isinstance(item, Mapping) or set(item) != {"role", "content"} or item["role"] not in {"user", "assistant"}:
            raise ValueError("Studio Agent history message is invalid")
        normalized_history.append({
            "role": str(item["role"]),
            "content": _text(item["content"], "history message", 1, 1000),
        })
    def history_bytes() -> int:
        return len(json.dumps(
            normalized_history, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8"))

    while history_bytes() > MAX_AGENT_HISTORY_BYTES:
        if len(normalized_history) > 1:
            normalized_history.pop(0)
            continue
        content = normalized_history[0]["content"]
        encoded = content.encode("utf-8")[:MAX_AGENT_HISTORY_BYTES - 100]
        normalized_history[0]["content"] = encoded.decode("utf-8", errors="ignore").strip()
        break
    screenshots = request["screenshots"]
    if not isinstance(screenshots, list) or len(screenshots) > MAX_AGENT_SCREENSHOTS:
        raise ValueError("Studio Agent supports at most four screenshots")
    normalized_screenshots = [decode_reference(item) for item in screenshots]
    if sum(len(item) for item in normalized_screenshots) > MAX_AGENT_SCREENSHOT_BYTES:
        raise ValueError("Studio Agent screenshots exceed the 20 MB request budget")
    return {
        "request_id": request_id,
        "base_sha256": base_sha256,
        "message": _text(request["message"], "message", 1, 4000),
        "history": normalized_history,
        "configuration": deepcopy(dict(request["configuration"])),
        "content": deepcopy(dict(request["content"])),
        "screenshots": normalized_screenshots,
    }


def screenshot_artifacts(screenshots: list[bytes]) -> list[dict[str, str]]:
    return [{
        "name": f"studio_screenshot_{index}",
        "mime_type": "image/png",
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes_base64": base64.b64encode(data).decode(),
    } for index, data in enumerate(screenshots, start=1)]


def image_action_schema(slots: list[str], screenshot_count: int) -> dict[str, Any]:
    if not slots:
        return {
            "type": "array",
            "items": {
                "type": "object", "properties": {}, "required": [],
                "additionalProperties": False,
            },
            "maxItems": 0,
        }
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "slot": {"type": "string", "enum": slots},
                "visual_direction": {"type": "string", "minLength": 8, "maxLength": 600},
                "enhance_current": {"type": "boolean"},
                "reference_index": {
                    "type": "integer", "minimum": 0, "maximum": screenshot_count,
                },
            },
            "required": ["slot", "visual_direction", "enhance_current", "reference_index"],
            "additionalProperties": False,
        },
        "maxItems": len(slots),
    }


def manual_agent_schema(
    *, editable_paths: list[str], image_slots: list[str], screenshot_count: int,
) -> dict[str, Any]:
    if not editable_paths:
        raise ValueError("Studio Agent requires editable paths")
    properties: dict[str, Any] = {
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "enum": editable_paths},
                    "value": {
                        "anyOf": [
                            {"type": "string"}, {"type": "number"},
                            {"type": "boolean"}, {"type": "null"},
                        ],
                    },
                },
                "required": ["path", "value"],
                "additionalProperties": False,
            },
            "maxItems": min(MAX_AGENT_EDITS, len(editable_paths)),
        },
        "image_actions": image_action_schema(image_slots, screenshot_count),
        "reply": {"type": "string", "minLength": 1, "maxLength": 800},
    }
    return {
        "type": "object", "properties": properties,
        "required": list(properties), "additionalProperties": False,
    }


def _flatten_scalars(value: Any, path: str, result: dict[str, Any]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _flatten_scalars(item, f"{path}.{key}" if path else str(key), result)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _flatten_scalars(item, f"{path}[{index}]", result)
        return
    if value is None or isinstance(value, (str, int, float, bool)):
        result[path] = value


def _path_is_within(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + ".") or path.startswith(prefix + "[")


def manual_agent_editable_values(
    *, catalog: Mapping[str, Any], configuration: Mapping[str, Any],
    content: Mapping[str, Any], creative_direction: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return only catalog-backed scalar leaves that Agent mode may edit."""

    state: dict[str, Any] = {
        "configuration": deepcopy(dict(configuration)),
        "content": deepcopy(dict(content)),
    }
    prefixes = [
        str(setting)
        for component in catalog.get("components") or []
        for setting in component.get("setting_ids") or []
    ]
    if creative_direction is not None:
        state["creative_direction"] = deepcopy(dict(creative_direction))
        prefixes.extend(("creative_direction.style", "creative_direction.background"))
    flattened: dict[str, Any] = {}
    _flatten_scalars(state, "", flattened)
    immutable = (
        "content.contacts.email", "content.contacts.phone",
        "content.contacts.url", "content.contacts.instagram",
        "content.marketing.apple_url", "content.marketing.google_url", "content.marketing.privacy_url", "content.marketing.terms_url",
    )
    return {
        path: flattened[path]
        for path in sorted(flattened)
        if any(_path_is_within(path, prefix) for prefix in prefixes)
        and not any(_path_is_within(path, prefix) for prefix in immutable)
        and not path.endswith(".schema")
    }


_PATH_PART = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def manual_agent_value_tree(values: Mapping[str, Any]) -> dict[str, Any]:
    """Transmit every allowed leaf without repeating its parent path."""

    root: dict[str, Any] = {}
    for path, value in values.items():
        parts = [int(index) if index else key for key, index in _PATH_PART.findall(path)]
        target: Any = root
        for position, part in enumerate(parts[:-1]):
            container = [] if isinstance(parts[position + 1], int) else {}
            if isinstance(target, list):
                while len(target) <= part:
                    target.append({})
                if not target[part]:
                    target[part] = container
            else:
                target.setdefault(part, container)
            target = target[part]
        if isinstance(target, list):
            while len(target) <= parts[-1]:
                target.append({})
        target[parts[-1]] = deepcopy(value)
    return root


def manual_agent_brief_context(
    brief: Mapping[str, Any], *, brief_id: str, project_id: str,
) -> dict[str, Any]:
    """Pin the editor's approved source document, excluding graph/audit data."""

    document = brief.get("document")
    if not brief.get("approved") or not isinstance(document, Mapping) or not document:
        raise ValueError("Studio Agent requires its approved source Product Brief")
    if brief.get("brief_id", brief_id) != brief_id or brief.get("project_id", project_id) != project_id:
        raise ValueError("Studio Agent source Product Brief does not match this draft")
    document = deepcopy(dict(document))
    digest = hashlib.sha256(json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {"brief_id": brief_id, "document_sha256": digest, "document": document}


def _assign_path(root: dict[str, Any], path: str, value: Any) -> None:
    parts: list[str | int] = [
        int(index) if index else key
        for key, index in _PATH_PART.findall(path)
    ]
    if not parts or not isinstance(parts[0], str):
        raise ValueError("Studio Agent edit path is invalid")
    target: Any = root
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value


def apply_manual_agent_edits(
    value: Any, *, current_values: Mapping[str, Any],
    configuration: Mapping[str, Any], content: Mapping[str, Any],
    creative_direction: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, list) or len(value) > min(MAX_AGENT_EDITS, len(current_values)):
        raise ValueError("Studio Agent edits are invalid")
    state: dict[str, Any] = {
        "configuration": deepcopy(dict(configuration)),
        "content": deepcopy(dict(content)),
    }
    if creative_direction is not None:
        state["creative_direction"] = deepcopy(dict(creative_direction))
    used: set[str] = set()
    for edit in value:
        if not isinstance(edit, Mapping) or set(edit) != {"path", "value"}:
            raise ValueError("Studio Agent edit fields are invalid")
        path = str(edit["path"])
        if path not in current_values or path in used:
            raise ValueError("Studio Agent edit path is invalid or duplicated")
        next_value = edit["value"]
        current_value = current_values[path]
        valid_type = (
            next_value is None and current_value is None
            or isinstance(current_value, bool) and isinstance(next_value, bool)
            or isinstance(current_value, str) and isinstance(next_value, str)
            or not isinstance(current_value, bool)
            and isinstance(current_value, (int, float))
            and not isinstance(next_value, bool)
            and isinstance(next_value, (int, float))
        )
        if not valid_type:
            raise ValueError("Studio Agent edit value type does not match the current setting")
        _assign_path(state, path, next_value)
        used.add(path)
    return state


def validate_image_actions(
    value: Any, *, slots: list[str], screenshot_count: int,
    available_slots: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > len(slots):
        raise ValueError("Studio Agent image actions are invalid")
    result: list[dict[str, Any]] = []
    used: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {
            "slot", "visual_direction", "enhance_current", "reference_index",
        }:
            raise ValueError("Studio Agent image action fields are invalid")
        slot = str(item["slot"])
        if slot not in slots or slot in used:
            raise ValueError("Studio Agent image action slot is invalid or duplicated")
        enhance = item["enhance_current"]
        reference_index = item["reference_index"]
        if not isinstance(enhance, bool) or isinstance(reference_index, bool) or not isinstance(reference_index, int):
            raise ValueError("Studio Agent image action mode is invalid")
        if not 0 <= reference_index <= screenshot_count:
            raise ValueError("Studio Agent screenshot reference is invalid")
        if enhance and reference_index:
            raise ValueError("Studio Agent must choose enhancement or a screenshot reference")
        if enhance and slot not in available_slots:
            raise ValueError("Studio Agent cannot enhance a missing current image")
        result.append({
            "slot": slot,
            "visual_direction": _text(item["visual_direction"], "visual direction", 8, 600),
            "enhance_current": enhance,
            "reference_index": reference_index,
        })
        used.add(slot)
    return result


def manual_agent_payload(
    *, surface: str, entity_id: str, message: str,
    history: list[dict[str, str]], configuration: Mapping[str, Any],
    content: Mapping[str, Any], catalog: Mapping[str, Any],
    screenshot_artifact_values: list[dict[str, str]], image_slots: list[str],
    current_images: list[str], creative_direction: Mapping[str, Any] | None = None,
    approved_product_brief: Mapping[str, Any],
) -> dict[str, Any]:
    request_constraints = manual_agent_request_constraints(
        surface=surface, message=message, image_slots=image_slots,
    )
    editable_values = manual_agent_editable_values(
        catalog=catalog, configuration=configuration, content=content,
        creative_direction=creative_direction,
    )
    return {
        "surface": surface,
        "entity_id": entity_id,
        "owner_message": message,
        "recent_conversation": deepcopy(history),
        "approved_product_brief": deepcopy(dict(approved_product_brief)),
        "current_editable_values": manual_agent_value_tree(editable_values),
        "agent_control_contract": agent_control_contract(surface, catalog),
        "request_constraints": request_constraints,
        "image_tools": {
            "allowed_slots": image_slots,
            "current_image_slots": current_images,
            "screenshot_references": [{
                "reference_index": index,
                "sha256": item["sha256"],
            } for index, item in enumerate(screenshot_artifact_values, start=1)],
        },
    }


def response_reply(value: Any) -> str:
    return _text(value, "reply", 1, 800)
