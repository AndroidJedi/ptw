"""Providers used exclusively by Branding; no SEO search adapter is present."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .brand_domain import FONT_CATALOG, public_https_url, safe_redirect


@dataclass(frozen=True, slots=True)
class GeneratedLogo:
    content: bytes
    requested_model: str
    resolved_model: str
    prompt: str
    width: int
    height: int
    request_id: str = ""


class BrandProvider(Protocol):
    name: str
    text_model: str
    image_model: str

    def structured(self, stage: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...
    def logo(self, direction: Mapping[str, Any]) -> GeneratedLogo: ...
    def consume_usage(self) -> dict[str, int]: ...


class PublicBrandPageProvider:
    """Fetch bounded public HTML while checking every redirect target."""

    name = "public_https"

    def __init__(self, *, timeout: float = 20, max_bytes: int = 2_000_000) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch(self, url: str) -> dict[str, Any]:
        import httpx

        current = public_https_url(url)
        with httpx.Client(timeout=self.timeout, follow_redirects=False, headers={
            "User-Agent": "PTW-Branding/1.0 (+design evidence research)",
            "Accept": "text/html,application/xhtml+xml",
        }) as client:
            for _ in range(4):
                with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("public page redirect has no location")
                        current = safe_redirect(current, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if not any(value in content_type.lower() for value in ("text/html", "application/xhtml+xml")):
                        raise ValueError("reference page must return public HTML")
                    chunks = bytearray()
                    truncated = False
                    for chunk in response.iter_bytes():
                        remaining = self.max_bytes - len(chunks)
                        if remaining <= 0:
                            truncated = True
                            break
                        chunks.extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            truncated = True
                            break
                    final_url = str(response.url)
                    encoding = response.encoding or "utf-8"
                    break
            else:
                raise ValueError("public page exceeded redirect limit")
        text = bytes(chunks).decode(encoding, errors="replace")
        colors = list(dict.fromkeys(re.findall(r"#[0-9a-fA-F]{6}\b", text)))[:40]
        font_families = []
        for match in re.findall(r"font-family\s*:\s*([^;}]+)", text, re.I):
            cleaned = re.sub(r"[\"']", "", match).strip()
            if cleaned and cleaned not in font_families:
                font_families.append(cleaned[:200])
        css_tokens = []
        for name, value in re.findall(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;}]{1,200})", text):
            item = {"name": name[:100], "value": value.strip()[:200]}
            if item not in css_tokens:
                css_tokens.append(item)
        headings = [re.sub(r"<[^>]+>", " ", item).strip() for item in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", text, re.I | re.S)]
        buttons = [re.sub(r"<[^>]+>", " ", item).strip() for item in re.findall(r"<(?:button|a)[^>]*(?:class=[\"'][^\"']*(?:button|btn|cta)[^\"']*[\"'])[^>]*>(.*?)</(?:button|a)>", text, re.I | re.S)]
        imagery = [
            {"src": src[:1000], "alt": re.sub(r"\s+", " ", alt).strip()[:300]}
            for src, alt in re.findall(
                r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*?(?:alt=[\"']([^\"']*)[\"'])?[^>]*>",
                text, re.I,
            )[:12]
        ]
        structure = {
            tag: len(re.findall(rf"<{tag}\b", text, re.I))
            for tag in ("header", "nav", "main", "section", "article", "form", "footer")
        }
        metadata = {}
        for key in ("theme-color", "og:image", "og:title", "description"):
            pattern = rf"<meta[^>]+(?:name|property)=[\"']{re.escape(key)}[\"'][^>]+content=[\"']([^\"']+)"
            match = re.search(pattern, text, re.I)
            if match:
                metadata[key] = match.group(1)[:1000]
        plain = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
        plain = re.sub(r"<[^>]+>", " ", plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        return {
            "url": final_url,
            "content_type": content_type,
            "text": plain[:30_000],
            "signals": {
                "colors": colors,
                "font_families": font_families[:20],
                "css_tokens": css_tokens[:40],
                "structure": structure,
                "headings": [item for item in headings if item][:20],
                "calls_to_action": [item for item in buttons if item][:20],
                "imagery": imagery,
                "metadata": metadata,
            },
            "truncated": truncated,
        }


class FixtureBrandPageProvider:
    name = "fixture_public_pages"

    def fetch(self, url: str) -> dict[str, Any]:
        return {
            "url": url,
            "content_type": "text/html; fixture=true",
            "text": "A focused product with visible progress, proof, anticipation, and a calm return loop.",
            "signals": {
                "colors": ["#15162b", "#ff4f8b", "#f7f7fb"],
                "font_families": ["Inter"],
                "headings": ["Make progress visible"],
                "calls_to_action": ["Start a challenge"],
                "metadata": {"fixture": True},
            },
            "truncated": False,
        }


class CommanderBrandBridge:
    def __init__(self, base_url: str, token: str, *, timeout: float = 90) -> None:
        if not base_url or not token:
            raise RuntimeError("Branding Commander bridge URL and token are required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def post(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        import httpx

        response = httpx.post(
            f"{self.base_url}/{path.lstrip('/')}",
            headers={"X-PTW-Bridge-Token": self.token},
            json=dict(payload),
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Commander Branding bridge returned invalid JSON")
        return result

    def sources(self, findings: Sequence[Mapping[str, Any]]) -> dict[str, str]:
        return {str(key): str(value) for key, value in (self.post("sources", {"findings": list(findings)}).get("sources") or {}).items()}

    def direction(self, payload: Mapping[str, Any]) -> dict[str, str]:
        return {str(key): str(value) for key, value in self.post("directions", payload).items() if value}

    def logo_revision(self, payload: Mapping[str, Any]) -> dict[str, str]:
        return {
            str(key): str(value)
            for key, value in self.post("logo-revisions", payload).items()
            if value
        }

    def approve(self, payload: Mapping[str, Any]) -> dict[str, str | None]:
        result = self.post("approve", payload)
        return {str(key): (None if value is None else str(value)) for key, value in result.items()}


class DeterministicBrandProvider:
    name = "deterministic_brand_fixture"
    text_model = "deterministic-brand-v1"
    image_model = "deterministic-logo-v1"

    def consume_usage(self) -> dict[str, int]:
        return {}

    def structured(self, stage: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        evidence_ids = [str(item) for item in payload.get("evidence_ids") or []]
        if stage == "REFERENCE_PLAN":
            competitors = list(payload.get("competitors") or [])[:5]
            return {
                "competitors": competitors,
                "youtube_queries": [f"{item.get('name', 'product')} app design onboarding retention review" for item in competitors][:5],
                "principle_questions": ["How is value made immediate?", "What signals progress and return?", "How does the visual system create distinctiveness without dark patterns?"],
            }
        if stage == "DESIGN_PRINCIPLES":
            return {"principles": [
                {"name": "Visible momentum", "description": "Make progress and accumulated proof the visual hero.", "evidence_ids": evidence_ids[:6]},
                {"name": "Earned anticipation", "description": "Use upcoming milestones and return cues without fake urgency.", "evidence_ids": evidence_ids[2:8] or evidence_ids[:3]},
                {"name": "Social energy", "description": "Use compact, shareable proof moments instead of fabricated popularity.", "evidence_ids": evidence_ids[4:10] or evidence_ids[:3]},
                {"name": "Calm action", "description": "Keep one dominant action and reduce ornamental friction.", "evidence_ids": evidence_ids[:5]},
            ], "avoid": ["copied competitor marks", "fake scarcity", "unsupported social proof", "manipulative streak loss"]}
        if stage == "BRAND_BRIEF":
            snapshot = payload.get("snapshot") or {}
            return {"brief": {
                "product_truth": str(snapshot.get("owner_idea") or "Evidence-backed product")[:1000],
                "audience": "People described by the completed Idea case",
                "promise": "Turn an important intention into visible, repeatable progress.",
                "personality": ["bold", "credible", "energizing", "human"],
                "must_preserve": ["truthful proof", "clear value moment", "zero-audience usefulness"],
                "must_avoid": ["false urgency", "generic startup gradients", "copied trade dress"],
            }}
        if stage == "DIRECTION_SYNTHESIS":
            names = ["Proofrise", "Momentum", "Verity Loop", "Upmark", "Pactly", "Signal Run", "Evident", "Commitra", "Traceway", "Bravely", "Progressa", "Loopmark"]
            palettes = [
                ({"primary": "#ee1765", "secondary": "#4426a8", "accent": "#ffb000", "background": "#ffffff", "surface": "#f6f2f5", "text": "#171116", "muted": "#655b62", "success": "#087a55", "warning": "#875500", "error": "#b42336"}, {"primary": "#ff4f91", "secondary": "#9b83ff", "accent": "#ffd05a", "background": "#0b090c", "surface": "#191419", "text": "#fff7fb", "muted": "#bcaeb7", "success": "#55d6a6", "warning": "#ffd06a", "error": "#ff788a"}),
                ({"primary": "#1457d9", "secondary": "#6938b8", "accent": "#d34100", "background": "#ffffff", "surface": "#f1f5fb", "text": "#111827", "muted": "#566174", "success": "#087a55", "warning": "#855400", "error": "#b42336"}, {"primary": "#79a7ff", "secondary": "#c3a6ff", "accent": "#ff9564", "background": "#08101e", "surface": "#121d31", "text": "#f8faff", "muted": "#b0bdd2", "success": "#58d9aa", "warning": "#ffd16e", "error": "#ff7b8b"}),
                ({"primary": "#00796b", "secondary": "#36506b", "accent": "#bc3d71", "background": "#fffef8", "surface": "#f2f4ec", "text": "#17201d", "muted": "#5c6863", "success": "#087a55", "warning": "#835400", "error": "#ae2941"}, {"primary": "#58d8c3", "secondary": "#a7bdd5", "accent": "#ff82b2", "background": "#08110f", "surface": "#14201d", "text": "#f6fff8", "muted": "#afc0b8", "success": "#58d8aa", "warning": "#ffd16e", "error": "#ff7b8b"}),
            ]
            font_pairs = [("Montserrat", "Inter"), ("Manrope", "IBM Plex Sans"), ("IBM Plex Serif", "IBM Plex Sans")]
            directions = []
            for index in range(3):
                display, body = font_pairs[index]
                directions.append({
                    "name": names[index],
                    "tagline": {"en": ["Make progress undeniable.", "Momentum you can see.", "Proof that brings you back."][index], "uk": ["Зробіть прогрес незаперечним.", "Прогрес, який видно.", "Доказ, до якого хочеться повертатися."][index]},
                    "positioning": {"en": "A credible progress system built around visible proof.", "uk": "Система достовірного прогресу, побудована навколо видимого доказу."},
                    "personality": [["charged", "direct", "credible"], ["focused", "optimistic", "clear"], ["considered", "human", "premium"]][index],
                    "palette": {"light": palettes[index][0], "dark": palettes[index][1]},
                    "typography": {"display": display, "body": body, "mono": "IBM Plex Mono"},
                    "voice": {"principle": "Energetic and specific; never inflate evidence.", "examples": ["Show the next proof", "Your progress is visible"]},
                    "design_principles": ["Visible momentum", "Earned anticipation", "Social energy", "Calm action"],
                    "retention_patterns": ["progress checkpoint", "proof timeline", "next milestone", "private-first return loop"],
                    "ui_system": {"radius": [8, 14, 22], "spacing": [4, 8, 12, 16, 24, 32, 48], "motion_ms": 180, "density": "comfortable"},
                    "logo_prompt": f"Text-free abstract symbol for {names[index]}; bold geometric proof and upward momentum; original mark; transparent background; no letters, words, badges, gradients, or competitor resemblance.",
                    "evidence_ids": evidence_ids[:12],
                })
            return {"name_candidates": names, "directions": directions}
        raise ValueError(f"unsupported deterministic brand stage {stage}")

    def logo(self, direction: Mapping[str, Any]) -> GeneratedLogo:
        from PIL import Image, ImageDraw

        palette = direction["palette"]["light"]
        primary = palette["primary"]
        accent = palette["accent"]
        image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        digest = hashlib.sha256(
            f"{direction['name']}|{direction.get('logo_prompt') or ''}".encode()
        ).digest()
        inset = 170 + digest[0] % 50
        draw.rounded_rectangle((inset, inset, 1024 - inset, 1024 - inset), radius=150, fill=primary)
        draw.polygon([(320, 590), (480, 745), (750, 325), (640, 275), (470, 570), (390, 500)], fill=accent)
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return GeneratedLogo(stream.getvalue(), self.image_model, self.image_model, str(direction.get("logo_prompt") or ""), 1024, 1024, "fixture")


class UnavailableBrandProvider:
    """Keeps provider readiness inspectable when live credentials are absent."""

    name = "unavailable"

    def __init__(self, text_model: str, image_model: str) -> None:
        self.text_model = text_model
        self.image_model = image_model

    def consume_usage(self) -> dict[str, int]:
        return {}

    def structured(self, stage: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        raise RuntimeError("OpenAI Branding provider is not configured")

    def logo(self, direction: Mapping[str, Any]) -> GeneratedLogo:
        raise RuntimeError("OpenAI Branding provider is not configured")


def _strict_object(properties: Mapping[str, Any], required: Sequence[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required or properties.keys()),
        "additionalProperties": False,
    }


_STRING = {"type": "string"}
_I18N = _strict_object({"en": _STRING, "uk": _STRING})
_STRING_ARRAY = {"type": "array", "items": _STRING}
_COLOR = {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}
_COLOR_KEYS = (
    "primary", "secondary", "accent", "background", "surface", "text",
    "muted", "success", "warning", "error",
)
_PALETTE_THEME = _strict_object({key: _COLOR for key in _COLOR_KEYS})
_DIRECTION = _strict_object({
    "name": {"type": "string", "minLength": 1, "maxLength": 100},
    "tagline": _I18N,
    "positioning": _I18N,
    "personality": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 6},
    "palette": _strict_object({"light": _PALETTE_THEME, "dark": _PALETTE_THEME}),
    "typography": _strict_object({
        "display": {"type": "string", "enum": list(FONT_CATALOG)},
        "body": {"type": "string", "enum": list(FONT_CATALOG)},
        "mono": {"type": "string", "enum": list(FONT_CATALOG)},
    }),
    "voice": _strict_object({
        "principle": _STRING,
        "examples": {"type": "array", "items": _STRING, "maxItems": 6},
    }),
    "design_principles": {"type": "array", "items": _STRING, "minItems": 3, "maxItems": 8},
    "retention_patterns": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 8},
    "ui_system": _strict_object({
        "radius": {"type": "array", "items": {"type": "number"}, "minItems": 1, "maxItems": 6},
        "spacing": {"type": "array", "items": {"type": "number"}, "minItems": 1, "maxItems": 12},
        "motion_ms": {"type": "number"},
        "density": _STRING,
    }),
    "logo_prompt": {"type": "string", "minLength": 1, "maxLength": 1800},
    "evidence_ids": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 80},
})
BRAND_OUTPUT_SCHEMAS = {
    "REFERENCE_PLAN": _strict_object({
        "competitors": {
            "type": "array", "minItems": 0, "maxItems": 5,
            "items": _strict_object({"name": _STRING, "url": _STRING}),
        },
        "youtube_queries": {"type": "array", "items": _STRING, "maxItems": 5},
        "principle_questions": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 8},
    }),
    "DESIGN_PRINCIPLES": _strict_object({
        "principles": {
            "type": "array", "minItems": 3, "maxItems": 12,
            "items": _strict_object({
                "name": _STRING,
                "description": _STRING,
                "evidence_ids": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 20},
            }),
        },
        "avoid": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 12},
    }),
    "BRAND_BRIEF": _strict_object({
        "brief": _strict_object({
            "product_truth": _STRING,
            "audience": _STRING,
            "promise": _STRING,
            "personality": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 8},
            "must_preserve": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 12},
            "must_avoid": {"type": "array", "items": _STRING, "minItems": 1, "maxItems": 12},
        }),
    }),
    "DIRECTION_SYNTHESIS": _strict_object({
        "name_candidates": {"type": "array", "items": {"type": "string", "maxLength": 100}, "minItems": 12, "maxItems": 12},
        "directions": {"type": "array", "items": _DIRECTION, "minItems": 3, "maxItems": 3},
    }),
}

BRAND_BRIDGE_MODES = {
    "REFERENCE_PLAN": "branding_reference_plan",
    "DESIGN_PRINCIPLES": "branding_design_principles",
    "BRAND_BRIEF": "branding_brand_brief",
    "DIRECTION_SYNTHESIS": "branding_direction_synthesis",
    "LOGO_GENERATION": "branding_logo_generation",
}


def _brand_instruction(stage: str) -> str:
    instructions = {
        "REFERENCE_PLAN": "Plan bounded direct competitor-page and official YouTube design research. Do not request SEO search or captions.",
        "DESIGN_PRINCIPLES": "Derive evidence-cited visual, hype-without-deception, and retention design principles. Never copy trade dress.",
        "BRAND_BRIEF": "Create a concise bilingual brand brief faithful to the completed product case.",
        "DIRECTION_SYNTHESIS": "Create exactly three distinct complete brand directions and twelve internal candidate names. Use only allowed fonts and supplied evidence IDs. Include accessible light/dark semantic colors and a text-free symbol prompt.",
    }
    return instructions[stage]


class CodexBridgeBrandProvider:
    """Brand text and symbols through PTW's existing ChatGPT-authenticated Codex worker."""

    name = "codex_brand_bridge"

    def __init__(
        self,
        bridge_url: str,
        token: str,
        text_model: str,
        image_model: str,
        asset_root: Path,
        *,
        timeout_seconds: int = 360,
    ) -> None:
        if image_model != "gpt-image-2":
            raise RuntimeError("BRAND_IMAGE_MODEL must be gpt-image-2; fallback is forbidden")
        from .provider import BridgeProvider

        self.bridge = BridgeProvider(bridge_url, token, text_model, timeout_seconds)
        self.text_model = text_model or "codex-cli-default"
        self.image_model = image_model
        self.asset_root = asset_root.resolve()
        self._usage: dict[str, int] = {}

    def capabilities(self) -> dict[str, Any]:
        capabilities = self.bridge.capabilities()
        required = set(BRAND_BRIDGE_MODES.values())
        actual = set(capabilities.get("branding_modes") or [])
        if actual != required:
            raise RuntimeError(
                "Branding bridge contract mismatch: "
                f"missing_modes={len(required - actual)} unexpected_modes={len(actual - required)}"
            )
        image = capabilities.get("branding_image") or {}
        if (
            image.get("ready") is not True
            or image.get("model") != self.image_model
            or image.get("provider") != "codex_chatgpt_imagegen"
            or image.get("max_images_per_request") != 1
            or image.get("asset_transport") != "commander_asset_volume"
        ):
            raise RuntimeError("Branding bridge image contract is unavailable")
        return capabilities

    def consume_usage(self) -> dict[str, int]:
        usage, self._usage = self._usage, {}
        return usage

    @staticmethod
    def cost_metadata() -> dict[str, Any]:
        return {
            "billing_mode": "codex_included_usage",
            "monetary_cost_status": "no_usd_amount_reported",
        }

    def _capture_usage(self, invocation: Mapping[str, Any]) -> None:
        self._usage = {
            "input_tokens": int(invocation.get("input_tokens") or 0),
            "output_tokens": int(invocation.get("output_tokens") or 0),
        }

    def structured(self, stage: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        mode = BRAND_BRIDGE_MODES[stage]
        allowed = ", ".join(FONT_CATALOG)
        system_prompt = (
            f"{_brand_instruction(stage)} English is source; provide faithful Ukrainian where requested. "
            "Reject fake urgency, scarcity, rankings, testimonials, adoption claims, and unsupported numbers. "
            f"Allowed fonts: {allowed}."
        )
        context_hash = hashlib.sha256(
            json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()
        self.bridge.prepare_invocation("branding_v1", context_hash)
        result = self.bridge.generate_structured(
            mode,
            system_prompt,
            dict(payload),
            BRAND_OUTPUT_SCHEMAS[stage],
        )
        self._capture_usage(self.bridge.last_invocation)
        return result

    def logo(self, direction: Mapping[str, Any]) -> GeneratedLogo:
        symbol_prompt = str(direction.get("logo_prompt") or "").strip()
        system_prompt = (
            "$imagegen Use built-in image generation exactly once to create one premium original brand symbol "
            "on a transparent background. No words, letters, numbers, monograms, watermarks, badges, "
            "app-interface text, copied logos, or claims. Use a simple square composition and silhouette that "
            "remains recognizable at favicon size. Do not use shell tools, do not save or copy the image, and "
            "do not invoke image generation a second time. After the image tool completes, return the required "
            "JSON acknowledgement."
        )
        payload = {"logo_prompt": symbol_prompt}
        context_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        self.bridge.prepare_invocation("branding_v1", context_hash)
        result = self.bridge.execute_contract(
            BRAND_BRIDGE_MODES["LOGO_GENERATION"],
            system_prompt,
            payload,
            {
                "type": "object",
                "properties": {"generated": {"type": "boolean", "const": True}},
                "required": ["generated"],
                "additionalProperties": False,
            },
        )
        invocation = dict(result.get("invocation") or {})
        self._capture_usage(invocation)
        image_result = result.get("image")
        if not isinstance(image_result, Mapping):
            raise RuntimeError("Branding bridge returned no image artifact")
        if (
            image_result.get("mime_type") != "image/png"
            or image_result.get("requested_model") != self.image_model
            or image_result.get("resolved_model") != self.image_model
            or image_result.get("provider") != "codex_chatgpt_imagegen"
        ):
            raise RuntimeError("Branding bridge returned invalid image provenance")
        path = Path(str(image_result.get("path") or "")).resolve()
        provider_root = (self.asset_root / "brand-provider").resolve()
        if provider_root not in path.parents or path.suffix.lower() != ".png":
            raise RuntimeError("Branding bridge image path is outside the immutable asset root")
        content = path.read_bytes() if path.is_file() else b""
        source_digest = hashlib.sha256(content).hexdigest() if content else ""
        if not content or source_digest != image_result.get("digest") or path.stem != source_digest:
            raise RuntimeError("Branding bridge image digest does not match its immutable asset")

        from PIL import Image

        with Image.open(io.BytesIO(content)) as source:
            source.load()
            if (
                source.format != "PNG"
                or source.width != source.height
                or source.width < 512
                or source.width > 2048
            ):
                raise RuntimeError("Branding bridge image must be a bounded square PNG")
            rgba = source.convert("RGBA")
            if rgba.getchannel("A").getextrema()[0] == 255:
                raise RuntimeError("Branding bridge image must preserve a transparent background")
            normalized = rgba.resize((1024, 1024), Image.Resampling.LANCZOS)
            stream = io.BytesIO()
            normalized.save(stream, format="PNG", compress_level=9)
        return GeneratedLogo(
            stream.getvalue(),
            self.image_model,
            self.image_model,
            symbol_prompt,
            1024,
            1024,
            str(image_result.get("request_id") or invocation.get("session_id") or ""),
        )


class OpenAIBrandProvider:
    name = "openai_brand"

    def __init__(self, api_key: str, text_model: str, image_model: str) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for live Branding")
        if image_model != "gpt-image-2":
            raise RuntimeError("BRAND_IMAGE_MODEL must be gpt-image-2; fallback is forbidden")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.text_model = text_model
        self.image_model = image_model
        self._usage: dict[str, int] = {}

    def consume_usage(self) -> dict[str, int]:
        usage, self._usage = self._usage, {}
        return usage

    def structured(self, stage: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        allowed = ", ".join(FONT_CATALOG)
        prompt = (
            f"{_brand_instruction(stage)} Return one JSON object only. English is source; provide faithful Ukrainian where requested. "
            "Reject fake urgency, scarcity, rankings, testimonials, adoption claims, and unsupported numbers. "
            f"Allowed fonts: {allowed}.\n\nInput:\n{json.dumps(dict(payload), ensure_ascii=False, default=str)}"
        )
        response = self.client.responses.create(
            model=self.text_model,
            input=prompt,
            store=False,
            text={
                "format": {
                    "type": "json_schema",
                    "name": f"branding_{stage.casefold()}",
                    "strict": True,
                    "schema": BRAND_OUTPUT_SCHEMAS[stage],
                }
            },
        )
        usage = getattr(response, "usage", None)
        self._usage = {
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        }
        text = str(response.output_text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
        result = json.loads(text)
        if not isinstance(result, dict):
            raise ValueError("brand provider must return one JSON object")
        return result

    def logo(self, direction: Mapping[str, Any]) -> GeneratedLogo:
        prompt = (
            f"{direction.get('logo_prompt', '')}\n\nCreate one premium original brand symbol on a transparent background. "
            "No words, letters, numbers, monograms, watermarks, badges, app-interface text, copied logos, or claims. "
            "Use a simple silhouette that remains recognizable at favicon size."
        )
        response = self.client.images.generate(
            model=self.image_model,
            prompt=prompt,
            quality="high",
            size="1024x1024",
            background="transparent",
            output_format="png",
            n=1,
        )
        usage = getattr(response, "usage", None)
        self._usage = {
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        }
        if not response.data or not response.data[0].b64_json:
            raise RuntimeError("brand image provider returned no image")
        return GeneratedLogo(
            base64.b64decode(response.data[0].b64_json),
            self.image_model,
            str(getattr(response, "model", None) or self.image_model),
            prompt,
            1024,
            1024,
            str(getattr(response, "id", "") or ""),
        )
