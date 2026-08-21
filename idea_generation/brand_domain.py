"""Branding v1 constants, validation, and deterministic quality checks."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin, urlsplit


BRAND_PIPELINE_VERSION = "branding_v1"
BRAND_STAGES = (
    "CASE_SNAPSHOT",
    "REFERENCE_PLAN",
    "REFERENCE_COLLECTION",
    "DESIGN_PRINCIPLES",
    "BRAND_BRIEF",
    "DIRECTION_SYNTHESIS",
    "DIRECTION_EVALUATION",
    "LOGO_GENERATION",
    "OWNER_REVIEW",
    "KIT_ASSEMBLY",
)
FONT_ASSET_ROOT = Path(__file__).resolve().parent / "assets" / "brand_fonts"
_FONT_FILES = json.loads((FONT_ASSET_ROOT / "catalog.json").read_text(encoding="utf-8"))
_FONT_CATEGORIES = {
    "Inter": "sans", "Manrope": "sans", "Montserrat": "sans",
    "IBM Plex Sans": "sans", "IBM Plex Serif": "serif", "IBM Plex Mono": "mono",
}
FONT_CATALOG = {
    name: {
        **details,
        "category": _FONT_CATEGORIES[name],
        "cyrillic": True,
        "license": "OFL-1.1",
        "variable": name in {"Inter", "Manrope", "Montserrat", "IBM Plex Sans"},
    }
    for name, details in _FONT_FILES.items()
}
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def stable_hash(*values: Any) -> str:
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()


def public_https_url(value: str, *, resolve: bool = True) -> str:
    raw = value.strip()
    parts = urlsplit(raw)
    if parts.scheme.lower() != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("reference URLs must be public HTTPS URLs")
    if parts.port not in {None, 443}:
        raise ValueError("reference URLs may not use a custom port")
    hostname = parts.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith((".local", ".internal")):
        raise ValueError("reference URL host is not public")
    if resolve:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)}
        except socket.gaierror as error:
            raise ValueError("reference URL host cannot be resolved") from error
        if not addresses:
            raise ValueError("reference URL host cannot be resolved")
        for raw_address in addresses:
            address = ipaddress.ip_address(raw_address)
            if not address.is_global:
                raise ValueError("reference URL resolves to a non-public address")
    return raw


def safe_redirect(current: str, location: str) -> str:
    return public_https_url(urljoin(current, location))


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.removeprefix("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def contrast_ratio(foreground: str, background: str) -> float:
    def luminance(color: str) -> float:
        channels = []
        for value in _rgb(color):
            normalized = value / 255
            channels.append(normalized / 12.92 if normalized <= .04045 else ((normalized + .055) / 1.055) ** 2.4)
        return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]
    a, b = luminance(foreground), luminance(background)
    return (max(a, b) + .05) / (min(a, b) + .05)


def normalize_direction(raw: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    name = str(raw.get("name") or "").strip()
    if not name or len(name) > 100:
        raise ValueError("each brand direction requires a 1-100 character name")
    palette = raw.get("palette")
    typography = raw.get("typography")
    if not isinstance(palette, Mapping) or not isinstance(typography, Mapping):
        raise ValueError("each brand direction requires palette and typography")
    required_colors = {"primary", "secondary", "accent", "background", "surface", "text", "muted", "success", "warning", "error"}
    normalized_palette: dict[str, dict[str, str]] = {}
    for theme in ("light", "dark"):
        values = palette.get(theme)
        if not isinstance(values, Mapping) or not required_colors.issubset(values):
            raise ValueError(f"palette.{theme} is incomplete")
        normalized_palette[theme] = {key: str(values[key]).lower() for key in required_colors}
        if not all(HEX_COLOR.fullmatch(value) for value in normalized_palette[theme].values()):
            raise ValueError(f"palette.{theme} contains an invalid color")
    display = str(typography.get("display") or "")
    body = str(typography.get("body") or "")
    mono = str(typography.get("mono") or "IBM Plex Mono")
    if any(value not in FONT_CATALOG for value in (display, body, mono)):
        raise ValueError("typography must use the bundled OFL catalog")
    tagline = raw.get("tagline")
    if not isinstance(tagline, Mapping) or set(tagline) < {"en", "uk"}:
        raise ValueError("direction tagline must contain en and uk")
    principles = [str(item).strip()[:500] for item in raw.get("design_principles") or [] if str(item).strip()]
    if not 3 <= len(principles) <= 8:
        raise ValueError("direction must contain 3-8 design principles")
    return {
        "ordinal": ordinal,
        "name": name,
        "tagline": {"en": str(tagline["en"])[:300], "uk": str(tagline["uk"])[:300]},
        "positioning": dict(raw.get("positioning") or {}),
        "personality": [str(item)[:100] for item in raw.get("personality") or []][:6],
        "palette": normalized_palette,
        "typography": {"display": display, "body": body, "mono": mono},
        "voice": dict(raw.get("voice") or {}),
        "design_principles": principles,
        "retention_patterns": [str(item)[:500] for item in raw.get("retention_patterns") or []][:8],
        "ui_system": dict(raw.get("ui_system") or {}),
        "logo_prompt": str(raw.get("logo_prompt") or "")[:1800],
        "evidence_ids": [str(item) for item in raw.get("evidence_ids") or []][:80],
    }


def evaluate_direction(
    direction: Mapping[str, Any],
    competitor_names: Sequence[str],
    existing_names: Sequence[str],
    *,
    allowed_evidence_ids: Sequence[str] | None = None,
    case_content: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    name = str(direction["name"])
    collisions = []
    for candidate in (*competitor_names, *existing_names):
        ratio = SequenceMatcher(None, name.casefold(), str(candidate).casefold()).ratio()
        if ratio >= .78:
            collisions.append({"name": str(candidate), "similarity": round(ratio, 3)})
    palette = direction["palette"]
    contrast = {
        theme: {
            "text_background": round(contrast_ratio(values["text"], values["background"]), 2),
            "text_surface": round(contrast_ratio(values["text"], values["surface"]), 2),
        }
        for theme, values in palette.items()
    }
    contrast_pass = all(value >= 4.5 for item in contrast.values() for value in item.values())
    typography = direction["typography"]
    font_pass = all(FONT_CATALOG.get(str(value), {}).get("cyrillic") is True for value in typography.values())
    unsupported = re.compile(r"(?:#1\b|\b(?:best|guaranteed|millions? of users|clinically proven|limited time)\b)", re.I)
    claim_text = json.dumps(direction, ensure_ascii=False)
    truthful = unsupported.search(claim_text) is None
    evidence_ids = [str(item) for item in direction.get("evidence_ids") or []]
    allowed = set(str(item) for item in allowed_evidence_ids or [])
    unknown_evidence = [item for item in evidence_ids if allowed and item not in allowed]
    positioning = direction.get("positioning") or {}
    case_fit = bool(
        isinstance(positioning, Mapping)
        and str(positioning.get("en") or "").strip()
        and str(positioning.get("uk") or "").strip()
        and direction.get("design_principles")
        and direction.get("retention_patterns")
        and evidence_ids
        and (not case_content or str(case_content.get("owner_idea") or "").strip())
    )
    checks = {
        "name_collision": {"passed": not collisions, "collisions": collisions, "clearance": "screen_only_not_trademark_or_domain"},
        "contrast": {"passed": contrast_pass, "ratios": contrast},
        "font_coverage": {"passed": font_pass, "latin": True, "ukrainian_cyrillic": font_pass},
        "truthful_design": {"passed": truthful},
        "evidence_lineage": {
            "passed": bool(evidence_ids) and not unknown_evidence,
            "evidence_ids": evidence_ids,
            "unknown_evidence_ids": unknown_evidence,
        },
        "case_fit": {"passed": case_fit},
    }
    return {"passed": all(item["passed"] for item in checks.values()), "checks": checks}
