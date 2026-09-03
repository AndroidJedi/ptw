"""One local post draft derived from an approved Product Brief.

The workflow deliberately reuses Universal Studio's public configuration,
component IDs, renderer, and Pexels provenance boundary.  A generated or tuned
post remains a mutable draft.  Only explicit owner approval creates an
immutable PNG asset.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import UUID

from commander.ids import new_uuid7

from .local_brief_store import LocalBriefStore, sha256_json, utc_now
from .local_codex import LocalCodexStructuredProvider, sanitized
from .studio_phone_metrics import (
    DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_TEXTURE_CHOICES,
    PHONE_METRICS_TEMPLATE_ID, normalize_phone_metrics_content,
    normalize_phone_metrics_texture_choices,
)
from .studio_universal import (
    DEFAULT_CONFIG, DEFAULT_CONTENT, UNIVERSAL_AD_TEMPLATE_ID, UNIVERSAL_SETTING_DEFINITIONS,
    normalize_universal_config, normalize_universal_content,
    normalize_universal_setting, universal_ad_catalog, universal_component_settings,
)
from .studio_workspace import UniversalStudioWorkspace


POST_SCHEMA = "ptw.simple-post.v2"
LEGACY_POST_SCHEMA = "ptw.simple-post.v1"
POST_ASSET_SCHEMA = "ptw.simple-post-asset.v1"
POST_STATUSES = frozenset({"queued", "generating", "draft", "tuning", "failed", "approved"})
CONTENT_SETTING_IDS = (
    "content.hero_title", "content.supporting_text", "content.offer",
    "content.bullets", "content.cta",
)
POST_GENERATION_SETTING_IDS = tuple(
    setting_id for setting_id in UNIVERSAL_SETTING_DEFINITIONS
    if not setting_id.startswith(("configuration.sticker.", "configuration.logo."))
)
POST_TUNE_SETTING_IDS = tuple(
    setting_id for setting_id in UNIVERSAL_SETTING_DEFINITIONS
    if not setting_id.startswith("configuration.logo.")
)
POST_DEFAULT_CONFIG = deepcopy(DEFAULT_CONFIG)
POST_DEFAULT_CONFIG["sticker"]["enabled"] = False
POST_DEFAULT_CONFIG["logo"]["enabled"] = True
STICKER_INTENT_TERMS = ("sticker", "stiker", "стікер", "стикер", "наліп", "наклей")
STICKER_HIDE_TERMS = (
    "hide", "remove", "disable", "turn off", "without", "delete",
    "схов", "прибери", "вимк", "без стік", "без стик", "видали",
)


def _sticker_comment_intent(comment: str) -> str | None:
    normalized = " ".join(str(comment).casefold().split())
    if not any(term in normalized for term in STICKER_INTENT_TERMS):
        return None
    if any(term in normalized for term in STICKER_HIDE_TERMS):
        return "hide"
    return "source"


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a UUID") from error


def _compact(value: Any, label: str, minimum: int, maximum: int) -> str:
    normalized = " ".join(str(value or "").split())
    if not minimum <= len(normalized) <= maximum:
        raise ValueError(f"{label} must contain {minimum}-{maximum} characters")
    return normalized


def _command_value_schema() -> dict[str, Any]:
    return {
        "anyOf": [
            {"type": "string"}, {"type": "number"}, {"type": "boolean"},
            {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        ],
    }


def _commands_schema(setting_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "array", "maxItems": 64,
        "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "setting_id": {"type": "string", "enum": setting_ids},
                "value": _command_value_schema(),
            },
            "required": ["setting_id", "value"],
        },
    }


def initial_post_output_schema() -> dict[str, Any]:
    """Strict output contract for one Brief-to-post generation plan."""

    content_properties = {
        "schema": {"type": "string", "const": "ptw.studio.universal-ad-content.v2"},
        "hero_title": {"type": "string", "minLength": 1, "maxLength": 140},
        "supporting_text": {"type": "string", "minLength": 1, "maxLength": 280},
        "offer": {"type": "string", "minLength": 1, "maxLength": 160},
        "bullets": {
            "type": "array", "maxItems": 3,
            "items": {"type": "string", "minLength": 1, "maxLength": 100},
        },
        "cta": {"type": "string", "minLength": 1, "maxLength": 60},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object", "additionalProperties": False,
        "properties": {
            "content": {
                "type": "object", "additionalProperties": False,
                "properties": content_properties,
                "required": list(content_properties),
            },
            "commands": _commands_schema(list(POST_GENERATION_SETTING_IDS)),
            "image_query": {"type": "string", "minLength": 2, "maxLength": 160},
        },
        "required": ["content", "commands", "image_query"],
    }


def tune_post_output_schema(*, required_image_slot: str | None = None) -> dict[str, Any]:
    """Strict output contract for comment-to-Studio-command translation."""

    if required_image_slot not in {None, "sticker_object"}:
        raise ValueError("unsupported required post image slot")

    background_request = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "slot": {"type": "string", "const": "background_image"},
            "query": {"type": "string", "minLength": 2, "maxLength": 160},
        },
        "required": ["slot", "query"],
    }
    sticker_candidate = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 160},
            "required_subject_terms": {
                "type": "array", "minItems": 1, "maxItems": 3,
                "items": {"type": "string", "minLength": 2, "maxLength": 40},
            },
        },
        "required": ["query", "required_subject_terms"],
    }
    sticker_request = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "slot": {"type": "string", "const": "sticker_object"},
            **sticker_candidate["properties"],
            "fallbacks": {
                "type": "array", "maxItems": 2,
                "items": sticker_candidate,
            },
        },
        "required": ["slot", "query", "required_subject_terms", "fallbacks"],
    }
    image_request_schema: dict[str, Any] = {
        "anyOf": [{"type": "null"}, background_request, sticker_request],
    }
    if required_image_slot == "sticker_object":
        image_request_schema = sticker_request
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object", "additionalProperties": False,
        "properties": {
            "commands": _commands_schema([
                *POST_TUNE_SETTING_IDS, *CONTENT_SETTING_IDS,
            ]),
            "image_request": image_request_schema,
        },
        "required": ["commands", "image_request"],
    }


def _post_generation_prompt(language: str) -> str:
    return f"""You create exactly one square validation post from one approved Product Brief.
Use the Brief as the complete strategic authority. Write all visible copy in {language}.
Return concise, honest copy that preserves the promise, offer, CTA, and intended first customer.
Do not invent proof, metrics, testimonials, urgency, scarcity, or capabilities.

Choose one concrete Pexels search query for a real square photograph that reinforces the
post's main human situation. The query may describe a face, expression, posture, object,
or setting when that is the clearest visual. Do not request illustration or generated art.

The commands array is the same typed setting-command vocabulary used by Universal Studio.
Use only supplied setting IDs and allowed values. Omit settings that should retain their
    defaults. Return only the JSON object required by the supplied schema."""


def phone_screen_output_schema() -> dict[str, Any]:
    """A visual direction only; visible phone-screen text is never generated."""

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object", "additionalProperties": False,
        "properties": {
            "image_prompt": {"type": "string", "minLength": 24, "maxLength": 1_200},
        },
        "required": ["image_prompt"],
    }


def _phone_screen_prompt(language: str) -> str:
    return f"""Create one concise visual-art direction for the hero artwork inside a vertical
    phone app screen. The approved Product Brief is strategic context: use its audience, promise,
    mood, and product domain to choose one clear metaphorical subject or sculptural editorial
    composition, but never turn its copy into visible words. Keep the subject concentrated in the
    upper-middle of a bright off-white field, with dimensional materials, soft studio light,
    confident depth, dark graphite forms, and at most one vivid accent colour. The result must feel
    premium and specific to the Brief rather than like random wallpaper.

    Return the direction in English so an image model can use it. The generated hero artwork must
    contain no letters, numbers, logos, brand names, UI labels, buttons, charts, metrics, devices,
    or readable interface. Studio adds the fixed Natal app shell, owner title, CTA, and black iPhone
    frame after generation. The post copy itself is in {language}; do not repeat or paraphrase it
    in the image direction. Return only the JSON object required by the supplied schema."""


def _post_tune_prompt() -> str:
    return """Translate one owner comment into exact Universal Studio setting commands.
The comment may refer to visual intent instead of control names. Infer the smallest coherent
set of commands that satisfies it while preserving every unrelated current setting.

When the owner asks to pick, replace, find, or use an image, translate the visual meaning
into one concrete English Pexels query in image_request. For example, a request for a
'thinking human face' should become a photographic search query for a thoughtful person
with a clearly visible face, not a literal or keyword-only control update.

A sticker request always means the optional universal_ad.sticker component. Never imitate
a sticker by inserting an emoji, glyph, symbol, label, or punctuation into visible copy.
To add or replace a sticker, request sticker_object with a concrete English Pexels query
for one real physical object on a plain background that can be isolated, and enable
configuration.sticker.enabled. Supply one to three required_subject_terms naming that exact
physical object so off-subject search results fail closed. Avoid flat rectangular objects
such as phones, screens, books, paper, or signs because they make poor die-cut silhouettes.
If the owner names an object, preserve that exact object and return no fallbacks. If the
owner only asks for a generic sticker, include two fallback candidates with different,
contextually relevant compact objects that have clear irregular silhouettes (for example a
light bulb, key, mug, or small plant). To hide it, disable
configuration.sticker.enabled without changing the copy. Preserve all unrelated sticker
geometry unless the comment changes it.

Use only supplied setting IDs, typed bounds, enum values, and content fields. Do not invent
proof, metrics, testimonials, urgency, scarcity, or product capabilities. Return no command
for an unchanged value. Return only the JSON object required by the supplied schema."""


class SimplePostService:
    """Append-only local orchestration for one draft and one approved asset."""

    def __init__(
        self, root: Path | str, *, provider: LocalCodexStructuredProvider,
        brief_resolver: Callable[[str], Mapping[str, Any]], pexels: Any,
        image_provider: Any | None = None,
    ) -> None:
        self.root = Path(root)
        self.store = LocalBriefStore(self.root / "authority")
        self.provider = provider
        self.brief_resolver = brief_resolver
        self.pexels = pexels
        self.image_provider = image_provider
        self.drafts = self.root / "drafts"
        self.assets = self.root / "assets"
        self.drafts.mkdir(parents=True, exist_ok=True)
        self.assets.mkdir(parents=True, exist_ok=True)

    def _workspace(self, post_id: str) -> UniversalStudioWorkspace:
        return UniversalStudioWorkspace(
            self.drafts / _uuid(post_id, "post_id") / "studio", pexels=self.pexels,
        )

    def _record_invocation(
        self, *, target_id: str, mode: str, input_payload: Mapping[str, Any],
        response: Mapping[str, Any] | None, invocation: Mapping[str, Any] | None,
        error: Exception | None = None,
    ) -> str:
        invocation_id = new_uuid7()
        value = {
            "invocation_id": invocation_id, "target_id": target_id, "mode": mode,
            "input": sanitized(input_payload),
            "input_sha256": sha256_json(sanitized(input_payload)),
            "response": None if response is None else sanitized(response),
            "response_sha256": None if response is None else sha256_json(response),
            "provenance": sanitized(invocation or {}),
            "status": "failed" if error else "completed",
            "error_type": None if error is None else type(error).__name__,
            "error_message": None if error is None else str(error)[:1000],
            "created_at": utc_now(),
        }
        self.store.append("provider_invocations", invocation_id, value)
        self.store.edge(
            source_id=target_id, relation="used_provider_invocation",
            target_id=invocation_id,
        )
        return invocation_id

    def _provider_call(
        self, *, target_id: str, mode: str, system_prompt: str,
        input_payload: Mapping[str, Any], output_schema: Mapping[str, Any],
        response_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    ) -> dict[str, Any]:
        try:
            result = self.provider.call(
                mode=mode, system_prompt=system_prompt,
                input_payload=input_payload, output_schema=output_schema,
                idempotency_key=f"{target_id}:{mode}",
                prompt_version=f"local-simple-post-v1:{mode}",
                response_validator=response_validator,
            )
        except Exception as error:
            self._record_invocation(
                target_id=target_id, mode=mode, input_payload=input_payload,
                response=None, invocation={"attempts": getattr(error, "attempts", [])},
                error=error,
            )
            raise
        invocation_id = self._record_invocation(
            target_id=target_id, mode=mode, input_payload=input_payload,
            response=result["response"], invocation=result.get("invocation") or {},
        )
        return {**result, "invocation_id": invocation_id}

    @staticmethod
    def _template_input(
        template_id: str, template_input: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Validate immutable owner inputs before a draft locks its template."""

        if template_id == UNIVERSAL_AD_TEMPLATE_ID:
            if template_input is not None:
                raise ValueError("universal_ad does not accept template input")
            return None
        if template_id != PHONE_METRICS_TEMPLATE_ID:
            raise ValueError("post template is not registered")
        if not isinstance(template_input, Mapping) or set(template_input) not in (
            {"content"}, {"content", "textures"},
        ):
            raise ValueError("phone_metrics requires content and optional texture choices")
        textures = template_input.get("textures", DEFAULT_PHONE_TEXTURE_CHOICES)
        return {
            "content": normalize_phone_metrics_content(template_input["content"]),
            "textures": normalize_phone_metrics_texture_choices(textures),
        }

    @staticmethod
    def _validate_phone_screen_plan(value: Mapping[str, Any]) -> Mapping[str, Any]:
        if set(value) != {"image_prompt"}:
            raise ValueError("phone-screen image plan fields do not match v1")
        prompt = _compact(value["image_prompt"], "phone-screen image prompt", 24, 1_200)
        if not any(term in prompt.casefold() for term in ("abstract", "editorial", "visual")):
            raise ValueError("phone-screen image prompt must describe a visual-only composition")
        return {"image_prompt": prompt}

    @staticmethod
    def _apply_commands(
        configuration: Mapping[str, Any], content: Mapping[str, Any],
        commands: Any, *, allow_content: bool,
        allowed_configuration_ids: tuple[str, ...] = POST_GENERATION_SETTING_IDS,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        if not isinstance(commands, list) or len(commands) > 64:
            raise ValueError("post commands must be an array of at most 64 items")
        next_configuration = deepcopy(dict(configuration))
        next_content = deepcopy(dict(content))
        normalized_commands: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in commands:
            if not isinstance(item, Mapping) or set(item) != {"setting_id", "value"}:
                raise ValueError("each post command requires setting_id and value")
            setting_id = str(item["setting_id"])
            if setting_id in seen:
                raise ValueError(f"post command repeats setting ID: {setting_id}")
            seen.add(setting_id)
            if setting_id.startswith("configuration."):
                if setting_id not in allowed_configuration_ids:
                    raise ValueError(f"post command uses unknown Studio setting: {setting_id}")
                value = normalize_universal_setting(setting_id, item["value"])
                _, group, field = setting_id.split(".", 2)
                next_configuration[group][field] = value
            elif setting_id in CONTENT_SETTING_IDS and allow_content:
                field = setting_id.split(".", 1)[1]
                value = deepcopy(item["value"])
                next_content[field] = value
            else:
                raise ValueError(f"post command uses unavailable setting: {setting_id}")
            normalized_commands.append({"setting_id": setting_id, "value": value})
        return (
            normalize_universal_config(next_configuration),
            normalize_universal_content(next_content),
            normalized_commands,
        )

    @staticmethod
    def _with_image_mode_command(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mode = next((
            item for item in commands
            if item["setting_id"] == "configuration.background.mode"
        ), None)
        if mode is not None and mode["value"] != "image":
            raise ValueError("a background image request conflicts with its background mode command")
        return commands if mode is not None else [
            *commands,
            {"setting_id": "configuration.background.mode", "value": "image"},
        ]

    @staticmethod
    def _with_sticker_enabled_command(
        commands: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enabled = next((
            item for item in commands
            if item["setting_id"] == "configuration.sticker.enabled"
        ), None)
        if enabled is not None and enabled["value"] is not True:
            raise ValueError("a sticker object request conflicts with its enabled command")
        return commands if enabled is not None else [
            *commands,
            {"setting_id": "configuration.sticker.enabled", "value": True},
        ]

    @classmethod
    def _validate_initial_plan(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if set(value) != {"content", "commands", "image_query"}:
            raise ValueError("initial post plan fields do not match v1")
        content = normalize_universal_content(value["content"])
        configuration, _, commands = cls._apply_commands(
            POST_DEFAULT_CONFIG, content, value["commands"], allow_content=False,
        )
        query = _compact(value["image_query"], "image_query", 2, 160)
        return {
            "configuration": configuration, "content": content,
            "commands": commands, "image_query": query,
        }

    @classmethod
    def _validate_tune_plan(
        cls, value: Mapping[str, Any], *, owner_comment: str = "",
    ) -> Mapping[str, Any]:
        if set(value) != {"commands", "image_request"}:
            raise ValueError("post tuning plan fields do not match v1")
        commands = value["commands"]
        if not isinstance(commands, list):
            raise ValueError("post tuning commands must be an array")
        image = value["image_request"]
        normalized_image = None
        if image is not None:
            if not isinstance(image, Mapping):
                raise ValueError("post image request fields do not match v1")
            if image["slot"] not in {"background_image", "sticker_object"}:
                raise ValueError("simple posts support only background or sticker image requests")
            expected_fields = {"slot", "query"}
            subject_terms: list[str] = []
            fallbacks: list[dict[str, Any]] = []
            if image["slot"] == "sticker_object":
                expected_fields.update({"required_subject_terms", "fallbacks"})
                raw_terms = image.get("required_subject_terms")
                if not isinstance(raw_terms, list) or not 1 <= len(raw_terms) <= 3:
                    raise ValueError("sticker requests require one to three subject terms")
                subject_terms = [
                    _compact(item, "sticker subject term", 2, 40)
                    for item in raw_terms
                ]
                if len(set(term.casefold() for term in subject_terms)) != len(subject_terms):
                    raise ValueError("sticker request subject terms must be distinct")
                raw_fallbacks = image.get("fallbacks")
                if not isinstance(raw_fallbacks, list) or len(raw_fallbacks) > 2:
                    raise ValueError("sticker requests require zero to two fallback candidates")
                for fallback in raw_fallbacks:
                    if not isinstance(fallback, Mapping) or set(fallback) != {
                        "query", "required_subject_terms",
                    }:
                        raise ValueError("sticker fallback fields do not match v1")
                    fallback_terms = fallback["required_subject_terms"]
                    if not isinstance(fallback_terms, list) or not 1 <= len(fallback_terms) <= 3:
                        raise ValueError(
                            "sticker fallbacks require one to three subject terms"
                        )
                    normalized_terms = [
                        _compact(item, "sticker fallback subject term", 2, 40)
                        for item in fallback_terms
                    ]
                    if len(set(term.casefold() for term in normalized_terms)) != len(
                        normalized_terms
                    ):
                        raise ValueError("sticker fallback subject terms must be distinct")
                    fallbacks.append({
                        "query": _compact(fallback["query"], "sticker fallback query", 2, 160),
                        "required_subject_terms": normalized_terms,
                    })
            if set(image) != expected_fields:
                raise ValueError("post image request fields do not match v1")
            normalized_image = {
                "slot": str(image["slot"]),
                "query": _compact(image["query"], "image query", 2, 160),
            }
            if subject_terms:
                normalized_image["required_subject_terms"] = subject_terms
                normalized_image["fallbacks"] = fallbacks
        if not commands and normalized_image is None:
            raise ValueError("post comment did not resolve to any tuning command")
        sticker_intent = _sticker_comment_intent(owner_comment)
        if sticker_intent is not None:
            resolves_sticker = any(
                str(item.get("setting_id") or "").startswith("configuration.sticker.")
                for item in commands if isinstance(item, Mapping)
            ) or (
                normalized_image is not None
                and normalized_image["slot"] == "sticker_object"
            )
            if not resolves_sticker:
                raise ValueError(
                    "a sticker comment must resolve to the Studio sticker component, not copy"
                )
            if sticker_intent == "source" and (
                normalized_image is None
                or normalized_image["slot"] != "sticker_object"
            ):
                raise ValueError(
                    "an add or replace sticker comment must source sticker_object; "
                    "a background request or previously stored sticker cannot satisfy it"
                )
        return {"commands": deepcopy(commands), "image_request": normalized_image}

    def create_post(
        self, *, request_id: str, brief_id: str, requested_by: str,
        template_id: str = UNIVERSAL_AD_TEMPLATE_ID,
        template_input: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        request_id = _uuid(request_id, "request_id")
        brief_id = _uuid(brief_id, "brief_id")
        normalized_template_id = str(template_id)
        normalized_template_input = self._template_input(normalized_template_id, template_input)
        brief = dict(self.brief_resolver(brief_id))
        if brief.get("status") != "completed" or not brief.get("approved") or not brief.get("document"):
            raise ValueError("a simple post requires one completed, approved Product Brief")
        existing = next(
            (item for item in self.store.list("posts") if item["brief_id"] == brief_id),
            None,
        )
        if existing is not None:
            return self.get_post(existing["post_id"]), False
        post_id, created = self.store.reserve_request(
            scope="post-create", request_id=request_id,
            fingerprint={
                "request_id": request_id, "brief_id": brief_id,
                "template_id": normalized_template_id,
                "template_input": normalized_template_input,
            },
        )
        if not created:
            return self.get_post(post_id), False
        now = utc_now()
        post = {
            "schema": POST_SCHEMA, "post_id": post_id, "request_id": request_id,
            "project_id": str(brief["project_id"]), "brief_id": brief_id,
            "template_id": normalized_template_id, "template_input": normalized_template_input,
            "brief_document_sha256": str(brief.get("document_sha256") or sha256_json(brief["document"])),
            "requested_by": requested_by, "status": "queued", "failure_count": 0,
            "state_sha256": None, "template_sha256": None, "preview_sha256": None,
            "preview_width": None, "preview_height": None, "last_commands": [],
            "last_image_request": None, "last_comment": None, "last_error": None,
            "approved_asset_id": None, "created_at": now, "updated_at": now,
        }
        self.store.append("posts", post_id, post)
        self.store.edge(
            source_id=post["project_id"], relation="contains", target_id=post_id,
        )
        self.store.edge(
            source_id=post_id, relation="derived_from", target_id=brief_id,
            evidence={"brief_document_sha256": post["brief_document_sha256"]},
        )
        return self.get_post(post_id), True

    def generate_post(self, post_id: str) -> dict[str, Any]:
        post_id = _uuid(post_id, "post_id")
        post = self.store.get("posts", post_id)
        if post["status"] not in {"queued", "failed"}:
            return self.get_post(post_id)
        generating = {
            **post, "status": "generating", "last_error": None,
            "updated_at": utc_now(),
        }
        self.store.append("posts", post_id, generating)
        try:
            brief = dict(self.brief_resolver(post["brief_id"]))
            document = dict(brief["document"])
            language = "Ukrainian" if document.get("language") == "uk" else "English"
            template_id = str(post.get("template_id") or UNIVERSAL_AD_TEMPLATE_ID)
            if template_id == PHONE_METRICS_TEMPLATE_ID:
                template_input = self._template_input(template_id, post.get("template_input"))
                workspace = self._workspace(post_id)
                detail = workspace.detail()
                if detail["template_id"] != PHONE_METRICS_TEMPLATE_ID:
                    detail = workspace.apply_template(
                        base_sha256=detail["state_sha256"], template_id=PHONE_METRICS_TEMPLATE_ID,
                    )
                phone_configuration = deepcopy(DEFAULT_PHONE_CONFIG)
                phone_configuration["background"]["texture"] = template_input["textures"]["background"]
                phone_configuration["copy_background"]["texture"] = template_input["textures"]["copy_background"]
                phone_configuration["phone_screen"]["texture"] = template_input["textures"]["phone_screen"]
                saved = workspace.save_configuration(
                    base_sha256=detail["state_sha256"], configuration=phone_configuration,
                    content=template_input["content"],
                )
                prompt_result = self._provider_call(
                    target_id=post_id, mode="simple_post_phone_screen_prompt",
                    system_prompt=_phone_screen_prompt(language),
                    input_payload={
                        "post_id": post_id,
                        "product_brief": document,
                        "template": PHONE_METRICS_TEMPLATE_ID,
                        "screen_contract": "brief-derived hero art only; fixed renderer supplies logo, owner copy, CTA, and device UI",
                    },
                    output_schema=phone_screen_output_schema(),
                    response_validator=self._validate_phone_screen_plan,
                )
                if self.image_provider is None:
                    raise RuntimeError("Codex image generation is unavailable for phone-screen artwork")
                try:
                    generated_art = self.image_provider.generate(prompt_result["response"]["image_prompt"])
                    image_provenance = dict(generated_art["source"])
                    image_response = {
                        "mime_type": generated_art["mime_type"],
                        "width": generated_art["width"], "height": generated_art["height"],
                        "sha256": hashlib.sha256(generated_art["bytes"]).hexdigest(),
                    }
                    image_invocation_id = self._record_invocation(
                        target_id=post_id, mode="simple_post_phone_screen_image",
                        input_payload={"image_prompt": prompt_result["response"]["image_prompt"]},
                        response=image_response, invocation=image_provenance,
                    )
                except Exception as error:
                    self._record_invocation(
                        target_id=post_id, mode="simple_post_phone_screen_image",
                        input_payload={"image_prompt": prompt_result["response"]["image_prompt"]},
                        response=None, invocation={}, error=error,
                    )
                    raise
                rendered = workspace.store_generated_phone_screen(
                    base_sha256=saved["state_sha256"], data=generated_art["bytes"],
                    source=image_provenance,
                )
                preview = workspace.render_preview(state_sha256=rendered["state_sha256"])
                self.store.append("posts", post_id, {
                    **generating, "status": "draft", "state_sha256": rendered["state_sha256"],
                    "template_sha256": rendered["template_sha256"],
                    "preview_sha256": preview["bytes_sha256"],
                    "preview_width": preview["width"], "preview_height": preview["height"],
                    "last_commands": [],
                    "last_image_request": {
                        "slot": "phone_screen", "query": prompt_result["response"]["image_prompt"],
                    },
                    "provider_invocation_id": prompt_result["invocation_id"],
                    "image_provider_invocation_id": image_invocation_id,
                    "updated_at": utc_now(),
                })
                return self.get_post(post_id)
            if template_id != UNIVERSAL_AD_TEMPLATE_ID:
                raise ValueError("post template is not registered")
            payload = {
                "post_id": post_id, "product_brief": document,
                "studio_setting_definitions": [
                    item for item in universal_ad_catalog()["setting_definitions"]
                    if item["setting_id"] in POST_GENERATION_SETTING_IDS
                ],
                "default_component_settings": universal_component_settings(
                    POST_DEFAULT_CONFIG, DEFAULT_CONTENT,
                ),
            }
            result = self._provider_call(
                target_id=post_id, mode="simple_post_generate",
                system_prompt=_post_generation_prompt(language), input_payload=payload,
                output_schema=initial_post_output_schema(),
                response_validator=self._validate_initial_plan,
            )
            plan = result["response"]
            workspace = self._workspace(post_id)
            detail = workspace.detail()
            sourced = workspace.source_pexels(
                "background_image", base_sha256=detail["state_sha256"],
                query=plan["image_query"], isolate=False,
            )
            configuration = deepcopy(plan["configuration"])
            configuration["background"]["mode"] = "image"
            commands = self._with_image_mode_command(plan["commands"])
            saved = workspace.save_configuration(
                base_sha256=sourced["state_sha256"],
                configuration=configuration, content=plan["content"],
            )
            preview = workspace.render_preview(state_sha256=saved["state_sha256"])
            completed = {
                **generating, "status": "draft", "state_sha256": saved["state_sha256"],
                "template_sha256": saved["template_sha256"],
                "preview_sha256": preview["bytes_sha256"],
                "preview_width": preview["width"], "preview_height": preview["height"],
                "last_commands": commands,
                "last_image_request": {
                    "slot": "background_image", "query": plan["image_query"],
                },
                "provider_invocation_id": result["invocation_id"],
                "updated_at": utc_now(),
            }
            self.store.append("posts", post_id, completed)
        except Exception as error:
            self.store.append("posts", post_id, {
                **generating, "status": "failed",
                "failure_count": int(post.get("failure_count") or 0) + 1,
                "last_error": str(error)[:1000], "updated_at": utc_now(),
            })
        return self.get_post(post_id)

    def retry_post(self, post_id: str) -> dict[str, Any]:
        post = self.store.get("posts", _uuid(post_id, "post_id"))
        if post["status"] != "failed":
            raise ValueError("only a failed simple post can be retried")
        queued = {**post, "status": "queued", "last_error": None, "updated_at": utc_now()}
        self.store.append("posts", post["post_id"], queued)
        return self.get_post(post["post_id"])

    def create_tune(
        self, post_id: str, *, request_id: str, comment: str, requested_by: str,
    ) -> tuple[dict[str, Any], bool]:
        post_id = _uuid(post_id, "post_id")
        request_id = _uuid(request_id, "request_id")
        comment = _compact(comment, "comment", 1, 2000)
        post = self.store.get("posts", post_id)
        if post["status"] != "draft":
            raise ValueError("only a draft simple post can be tuned")
        if str(post.get("template_id") or UNIVERSAL_AD_TEMPLATE_ID) == PHONE_METRICS_TEMPLATE_ID:
            raise ValueError(
                "phone-and-metrics post copy is fixed when its draft starts; create a new draft to change it"
            )
        tune_id, created = self.store.reserve_request(
            scope="post-tune", request_id=request_id,
            fingerprint={"request_id": request_id, "post_id": post_id, "comment": comment},
        )
        if not created:
            return self.get_post(post_id), False
        tune = {
            "tune_id": tune_id, "post_id": post_id, "request_id": request_id,
            "comment": comment, "requested_by": requested_by, "status": "queued",
            "base_state_sha256": post["state_sha256"], "commands": [],
            "image_request": None, "error": None, "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.store.append("post_tunes", tune_id, tune)
        self.store.edge(source_id=tune_id, relation="evaluates", target_id=post_id)
        self.store.append("posts", post_id, {
            **post, "status": "tuning", "last_comment": comment,
            "last_error": None, "active_tune_id": tune_id, "updated_at": utc_now(),
        })
        return self.get_post(post_id), True

    def apply_tune(self, tune_id: str) -> dict[str, Any]:
        tune_id = _uuid(tune_id, "tune_id")
        tune = self.store.get("post_tunes", tune_id)
        post = self.store.get("posts", tune["post_id"])
        if tune["status"] not in {"queued", "running"}:
            return self.get_post(post["post_id"])
        running = {**tune, "status": "running", "updated_at": utc_now()}
        self.store.append("post_tunes", tune_id, running)
        try:
            workspace = self._workspace(post["post_id"])
            detail = workspace.detail()
            if detail["state_sha256"] != tune["base_state_sha256"]:
                raise RuntimeError("post draft changed before its comment was applied")
            payload = {
                "post_id": post["post_id"], "owner_comment": tune["comment"],
                "component_settings": detail["component_settings"],
                "assets": detail["assets"],
                "setting_definitions": [
                    item for item in detail["catalog"]["setting_definitions"]
                    if item["setting_id"] in POST_TUNE_SETTING_IDS
                ],
                "content_setting_ids": list(CONTENT_SETTING_IDS),
            }
            result = self._provider_call(
                target_id=tune_id, mode="simple_post_tune",
                system_prompt=_post_tune_prompt(), input_payload=payload,
                output_schema=tune_post_output_schema(
                    required_image_slot=(
                        "sticker_object"
                        if _sticker_comment_intent(tune["comment"]) == "source"
                        else None
                    ),
                ),
                response_validator=lambda value: self._validate_tune_plan(
                    value, owner_comment=tune["comment"],
                ),
            )
            plan = result["response"]
            configuration, content, commands = self._apply_commands(
                detail["configuration"], detail["content"], plan["commands"],
                allow_content=True,
                allowed_configuration_ids=POST_TUNE_SETTING_IDS,
            )
            current_state = detail["state_sha256"]
            image_request = plan["image_request"]
            sticker_available = any(
                asset["slot"] == "sticker_object" and asset["available"]
                for asset in detail["assets"]
            )
            if image_request is not None and image_request["slot"] == "sticker_object":
                commands = self._with_sticker_enabled_command(commands)
                configuration["sticker"]["enabled"] = True
            if (
                configuration["sticker"]["enabled"]
                and not sticker_available
                and not (
                    image_request is not None
                    and image_request["slot"] == "sticker_object"
                )
            ):
                raise ValueError(
                    "enabling the Studio sticker requires one sticker_object image request"
                )
            if image_request is not None:
                if image_request["slot"] == "background_image":
                    commands = self._with_image_mode_command(commands)
                candidates = [image_request]
                if image_request["slot"] == "sticker_object":
                    candidates.extend({
                        "slot": "sticker_object",
                        "query": fallback["query"],
                        "required_subject_terms": fallback["required_subject_terms"],
                    } for fallback in image_request.get("fallbacks") or ())
                sourced = None
                last_source_error: Exception | None = None
                for candidate in candidates:
                    try:
                        sourced = workspace.source_pexels(
                            candidate["slot"], base_sha256=current_state,
                            query=candidate["query"],
                            isolate=candidate["slot"] == "sticker_object",
                            required_subject_terms=tuple(
                                candidate.get("required_subject_terms") or ()
                            ),
                        )
                        image_request = {
                            "slot": candidate["slot"], "query": candidate["query"],
                        }
                        if candidate.get("required_subject_terms"):
                            image_request["required_subject_terms"] = list(
                                candidate["required_subject_terms"]
                            )
                        break
                    except (RuntimeError, ValueError) as error:
                        last_source_error = error
                if sourced is None:
                    raise RuntimeError(
                        "Pexels did not return an isolatable object from the agent-selected "
                        "sticker candidates"
                    ) from last_source_error
                current_state = sourced["state_sha256"]
                if image_request["slot"] == "background_image":
                    configuration["background"]["mode"] = "image"
            saved = workspace.save_configuration(
                base_sha256=current_state,
                configuration=configuration, content=content,
            )
            preview = workspace.render_preview(state_sha256=saved["state_sha256"])
            self.store.append("post_tunes", tune_id, {
                **running, "status": "completed", "commands": commands,
                "image_request": image_request,
                "provider_invocation_id": result["invocation_id"],
                "result_state_sha256": saved["state_sha256"],
                "updated_at": utc_now(),
            })
            self.store.append("posts", post["post_id"], {
                **post, "status": "draft", "state_sha256": saved["state_sha256"],
                "template_sha256": saved["template_sha256"],
                "preview_sha256": preview["bytes_sha256"],
                "preview_width": preview["width"], "preview_height": preview["height"],
                "last_commands": commands, "last_image_request": image_request,
                "last_comment": tune["comment"], "last_error": None,
                "active_tune_id": None, "updated_at": utc_now(),
            })
        except Exception as error:
            self.store.append("post_tunes", tune_id, {
                **running, "status": "failed", "error": str(error)[:1000],
                "updated_at": utc_now(),
            })
            current = self.store.get("posts", post["post_id"])
            try:
                recovered_detail = self._workspace(post["post_id"]).detail()
                recovered_preview = self._workspace(post["post_id"]).render_preview(
                    state_sha256=recovered_detail["state_sha256"],
                )
                recovery = {
                    "status": "draft", "state_sha256": recovered_detail["state_sha256"],
                    "template_sha256": recovered_detail["template_sha256"],
                    "preview_sha256": recovered_preview["bytes_sha256"],
                    "preview_width": recovered_preview["width"],
                    "preview_height": recovered_preview["height"],
                }
            except Exception:
                recovery = {
                    "status": "failed", "state_sha256": None,
                    "template_sha256": None, "preview_sha256": None,
                    "preview_width": None, "preview_height": None,
                    "failure_count": int(current.get("failure_count") or 0) + 1,
                }
            self.store.append("posts", post["post_id"], {
                **current, **recovery, "last_error": str(error)[:1000],
                "active_tune_id": None, "updated_at": utc_now(),
            })
        return self.get_post(post["post_id"])

    def list_posts(self, project_id: str | None = None) -> list[dict[str, Any]]:
        normalized_project = None if project_id is None else _uuid(project_id, "project_id")
        return [
            self.get_post(item["post_id"]) for item in self.store.list("posts")
            if normalized_project is None or item["project_id"] == normalized_project
        ]

    def _reconcile_legacy_universal_draft(
        self, post: Mapping[str, Any], studio: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Append one safe migration for a pre-template mutable draft.

        Universal Studio's fixed Natal identity changes the canonical state
        digest of historical *mutable* v1 Post workspaces.  Those drafts have
        no selected-template metadata, so their only unambiguous migration is
        to the retained `universal_ad` default. Immutable approvals and every
        v2 draft remain fail-closed if their state digest differs.
        """

        if (
            post.get("schema") != LEGACY_POST_SCHEMA
            or post.get("template_id") is not None
            or post.get("status") != "draft"
        ):
            return None
        preview = self._workspace(str(post["post_id"])).render_preview(
            state_sha256=str(studio["state_sha256"]),
        )
        migrated = {
            **dict(post), "schema": POST_SCHEMA,
            "template_id": UNIVERSAL_AD_TEMPLATE_ID, "template_input": None,
            "state_sha256": studio["state_sha256"],
            "template_sha256": studio["template_sha256"],
            "preview_sha256": preview["bytes_sha256"],
            "preview_width": preview["width"], "preview_height": preview["height"],
            "last_error": None, "updated_at": utc_now(),
        }
        self.store.append("posts", str(post["post_id"]), migrated)
        return migrated

    def get_post(self, post_id: str) -> dict[str, Any]:
        post = self.store.get("posts", _uuid(post_id, "post_id"))
        if post["status"] not in POST_STATUSES:
            raise ValueError("simple post status is invalid")
        studio = None
        if post.get("state_sha256"):
            studio = self._workspace(post["post_id"]).detail()
            if studio["state_sha256"] != post["state_sha256"]:
                migrated = self._reconcile_legacy_universal_draft(post, studio)
                if migrated is None:
                    raise ValueError("simple post state digest does not match its Studio draft")
                post = migrated
        asset = None
        if post.get("approved_asset_id"):
            asset = self.store.get("post_assets", post["approved_asset_id"])
        return {
            **post, "studio": studio,
            "preview": None if not post.get("preview_sha256") else {
                "mime_type": "image/png", "sha256": post["preview_sha256"],
                "width": post["preview_width"], "height": post["preview_height"],
            },
            "approved_asset": asset,
        }

    def render_preview(self, post_id: str, state_sha256: str) -> dict[str, Any]:
        post = self.store.get("posts", _uuid(post_id, "post_id"))
        if post["status"] not in {"draft", "tuning", "approved"}:
            raise ValueError("simple post preview is not ready")
        if state_sha256 != post.get("state_sha256"):
            raise RuntimeError("simple post changed; reload before previewing")
        return self._workspace(post["post_id"]).render_preview(state_sha256=state_sha256)

    @staticmethod
    def _write_immutable(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

    def approve_post(
        self, post_id: str, *, state_sha256: str, approved_by: str,
    ) -> tuple[dict[str, Any], bool]:
        post_id = _uuid(post_id, "post_id")
        post = self.store.get("posts", post_id)
        if post["status"] == "approved":
            return self.get_post(post_id), False
        if post["status"] != "draft" or state_sha256 != post.get("state_sha256"):
            raise ValueError("post approval requires the current complete draft")
        workspace = self._workspace(post_id)
        detail = workspace.detail()
        if str(post.get("template_id") or UNIVERSAL_AD_TEMPLATE_ID) == PHONE_METRICS_TEMPLATE_ID:
            phone_screen = next(
                (item for item in detail["assets"] if item["slot"] == "phone_screen"), None,
            )
            if (
                phone_screen is None or not phone_screen["available"]
                or phone_screen.get("source", {}).get("origin") != "openai_image_api"
                or phone_screen.get("source", {}).get("text_in_screen") != "prohibited_by_prompt"
            ):
                raise ValueError("phone-and-metrics approval requires generated text-free phone-screen artwork")
        preview = workspace.render_preview(state_sha256=state_sha256)
        asset_id = new_uuid7()
        asset = {
            "schema": POST_ASSET_SCHEMA, "asset_id": asset_id,
            "post_id": post_id, "project_id": post["project_id"],
            "brief_id": post["brief_id"], "mime_type": "image/png",
            "sha256": preview["bytes_sha256"], "width": preview["width"],
            "height": preview["height"], "state_sha256": state_sha256,
            "template_sha256": detail["template_sha256"],
            "configuration": detail["configuration"], "content": detail["content"],
            "component_settings": detail["component_settings"],
            "assets": detail["assets"], "approved_by": approved_by,
            "created_at": utc_now(),
        }
        raw = json.dumps(asset, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
        self._write_immutable(self.assets / f"{asset_id}.png", preview["bytes"])
        self._write_immutable(self.assets / f"{asset_id}.json", raw)
        self.store.append("post_assets", asset_id, asset)
        self.store.edge(source_id=post["project_id"], relation="contains", target_id=asset_id)
        self.store.edge(
            source_id=asset_id, relation="derived_from", target_id=post_id,
            evidence={"state_sha256": state_sha256},
        )
        self.store.append("posts", post_id, {
            **post, "status": "approved", "approved_asset_id": asset_id,
            "approved_at": asset["created_at"], "updated_at": asset["created_at"],
        })
        return self.get_post(post_id), True

    def asset_render(self, asset_id: str) -> dict[str, Any]:
        asset_id = _uuid(asset_id, "asset_id")
        asset = self.store.get("post_assets", asset_id)
        data = (self.assets / f"{asset_id}.png").read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != asset["sha256"]:
            raise ValueError("simple post asset digest mismatch")
        return {"bytes": data, "mime_type": asset["mime_type"], "sha256": digest}

    def recover_interrupted(self) -> dict[str, list[str]]:
        posts: list[str] = []
        tunes: list[str] = []
        for post in self.store.list("posts"):
            if post["status"] == "generating":
                self.store.append("posts", post["post_id"], {
                    **post, "status": "queued", "updated_at": utc_now(),
                })
                posts.append(post["post_id"])
            elif post["status"] == "queued":
                posts.append(post["post_id"])
        for tune in self.store.list("post_tunes"):
            if tune["status"] in {"queued", "running"}:
                if tune["status"] == "running":
                    self.store.append("post_tunes", tune["tune_id"], {
                        **tune, "status": "queued", "updated_at": utc_now(),
                    })
                tunes.append(tune["tune_id"])
        return {"posts": posts, "tunes": tunes}
