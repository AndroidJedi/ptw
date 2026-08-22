"""Strict logo-revision planning, deterministic lettermarks, and compliance."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import re
from typing import Any, Mapping

from .brand_domain import FONT_ASSET_ROOT, FONT_CATALOG


REVISION_STRATEGIES = frozenset({"reference_edit", "lettermark", "new_concept"})
_STRUCTURAL = re.compile(
    r"\b(letter|letters|text|word|monogram|initial|shape|symbol|icon|geometry|layout|"
    r"rearrange|simpl|remove|replace|play|ptw|літер|букв|текст|форм|геометр|перекомп)\w*",
    re.I,
)
_COLOR = re.compile(r"\b(colou?r|palette|hue|shade|tone|колір|кольор|палітр|відтін)\w*", re.I)
_LITERAL_PATTERNS = (
    re.compile(r"(?:letters?|initials?|monogram|word|text|літери?|букви?)\s+[\"“']?([A-ZА-ЯІЇЄҐ0-9]{2,12})[\"”']?", re.I),
    re.compile(r"[\"“']([A-ZА-ЯІЇЄҐ0-9]{2,12})[\"”']"),
    re.compile(r"\b(PTW)\b", re.I),
)


@dataclass(frozen=True, slots=True)
class ComplianceResult:
    passed: bool
    details: dict[str, Any]


def infer_literal_text(instruction: str) -> str | None:
    for pattern in _LITERAL_PATTERNS:
        match = pattern.search(instruction)
        if match:
            return match.group(1).upper()
    return None


def deterministic_revision_plan(instruction: str) -> dict[str, Any]:
    requested = instruction.strip()
    if not requested:
        raise ValueError("logo correction feedback has no actionable text")
    literal = infer_literal_text(requested)
    asks_new = bool(re.search(r"\b(new concept|from scratch|entirely new|нов(?:а|ий) концепц|з нуля)\b", requested, re.I))
    strategy = "lettermark" if literal else "new_concept" if asks_new else "reference_edit"
    structural = bool(_STRUCTURAL.search(requested)) or not bool(_COLOR.search(requested))
    return validate_revision_plan({
        "strategy": strategy,
        "requested_change": requested[:2000],
        "literal_text": literal,
        "invariants": [
            "original design only; do not copy another brand",
            "preserve a genuinely transparent background",
            "retain favicon-size clarity and a strong silhouette",
        ],
        "structural_change": structural,
        "layout": "interlock" if literal else "preserve_anchor",
    }, instruction=requested)


def validate_revision_plan(raw: Mapping[str, Any], *, instruction: str) -> dict[str, Any]:
    strategy = str(raw.get("strategy") or "").strip()
    if strategy not in REVISION_STRATEGIES:
        raise ValueError("revision planner returned an unsupported strategy")
    requested = str(raw.get("requested_change") or instruction).strip()[:2000]
    literal_raw = raw.get("literal_text")
    literal = str(literal_raw).strip().upper() if literal_raw not in (None, "") else None
    inferred = infer_literal_text(instruction)
    if inferred and literal != inferred:
        raise ValueError("revision planner lost or changed the owner's exact literal text")
    if literal and strategy != "lettermark":
        raise ValueError("exact logo text must use the deterministic lettermark strategy")
    if strategy == "lettermark" and not literal:
        raise ValueError("lettermark revisions require exact literal text")
    invariants = [str(item).strip()[:300] for item in raw.get("invariants") or [] if str(item).strip()]
    fixed = [
        "original design only; do not copy another brand",
        "preserve a genuinely transparent background",
        "retain favicon-size clarity and a strong silhouette",
    ]
    invariants = list(dict.fromkeys([*invariants, *fixed]))[:12]
    structural = bool(raw.get("structural_change"))
    if _STRUCTURAL.search(instruction):
        structural = True
    layout = str(raw.get("layout") or ("interlock" if literal else "preserve_anchor"))
    if layout not in {"preserve_anchor", "interlock", "stack", "orbit"}:
        layout = "preserve_anchor"
    return {
        "strategy": strategy,
        "requested_change": requested,
        "literal_text": literal,
        "invariants": invariants,
        "structural_change": structural,
        "layout": layout,
        "owner_overrides_soft_constraints": True,
    }


def _font_path(manifest: Mapping[str, Any]) -> Path:
    typography = manifest.get("typography") or {}
    family = str(typography.get("display") or "Montserrat")
    details = FONT_CATALOG.get(family) or FONT_CATALOG["Montserrat"]
    return FONT_ASSET_ROOT / str(details["font_file"])


def render_lettermark(
    source_path: Path,
    source_digest: str,
    manifest: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> bytes:
    """Render exact text with a bundled font while deriving color from the source."""

    from PIL import Image, ImageDraw, ImageFont

    content = source_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != source_digest:
        raise ValueError("source logo digest does not match its immutable PNG")
    with Image.open(io.BytesIO(content)) as source:
        source.load()
        if source.format != "PNG":
            raise ValueError("source logo must be a PNG")
        rgba = source.convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
        opaque = [pixel[:3] for pixel in rgba.getdata() if pixel[3] >= 64]
    palette = manifest.get("palette") or {}
    light = palette.get("light") or {}
    primary = str(light.get("primary") or "#f4066e")
    accent = str(light.get("accent") or "#ffffff")
    if opaque:
        # Keep a clear visual reference to the approved mark without copying its
        # pixels: its two most frequent opaque colors seed the lettermark.
        counts: dict[tuple[int, int, int], int] = {}
        for color in opaque[:: max(1, len(opaque) // 50_000)]:
            bucket = tuple((channel // 24) * 24 for channel in color)
            counts[bucket] = counts.get(bucket, 0) + 1
        ranked = sorted(counts, key=counts.get, reverse=True)
        if ranked:
            primary = ranked[0]
        if len(ranked) > 1:
            accent = ranked[1]

    literal = str(plan.get("literal_text") or "")
    if not literal:
        raise ValueError("lettermark renderer requires literal text")
    image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font_size = 360 if len(literal) <= 3 else max(150, 880 // len(literal))
    font = ImageFont.truetype(str(_font_path(manifest)), font_size)
    spacing = -max(10, font_size // 14) if str(plan.get("layout")) == "interlock" else 8
    widths = [draw.textlength(char, font=font) for char in literal]
    total = sum(widths) + spacing * (len(literal) - 1)
    x = (1024 - total) / 2
    bbox = draw.textbbox((0, 0), literal, font=font)
    y = (1024 - (bbox[3] - bbox[1])) / 2 - bbox[1]
    colors = (primary, accent)
    for index, (char, width) in enumerate(zip(literal, widths)):
        draw.text((round(x), round(y)), char, font=font, fill=colors[index % 2], stroke_width=0)
        x += width + spacing
    # A small source-derived proof notch makes the silhouette intentionally new
    # while retaining the approved direction's upward/progress character.
    draw.polygon([(765, 730), (845, 650), (845, 730)], fill=colors[0])
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return stream.getvalue()


def validate_logo_result(
    source_content: bytes,
    result_content: bytes,
    *,
    plan: Mapping[str, Any],
    reference_used: bool,
    rendered_literal_text: str | None = None,
) -> ComplianceResult:
    from PIL import Image, ImageChops

    details: dict[str, Any] = {
        "strategy": plan.get("strategy"),
        "literal_text": plan.get("literal_text"),
        "reference_required": plan.get("strategy") == "reference_edit",
        "reference_used": reference_used,
    }
    try:
        with Image.open(io.BytesIO(source_content)) as before_raw:
            before_raw.load()
            before = before_raw.convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
        with Image.open(io.BytesIO(result_content)) as after_raw:
            after_raw.load()
            details.update({"format": after_raw.format, "size": list(after_raw.size)})
            after = after_raw.convert("RGBA")
            png_ok = after_raw.format == "PNG" and after_raw.size == (1024, 1024)
    except Exception as error:
        return ComplianceResult(False, {**details, "reason": f"invalid PNG: {type(error).__name__}"})
    alpha_ok = after.getchannel("A").getextrema()[0] < 255
    before_alpha = before.getchannel("A").point(lambda value: 255 if value >= 32 else 0)
    after_alpha = after.getchannel("A").point(lambda value: 255 if value >= 32 else 0)
    intersection = ImageChops.multiply(before_alpha, after_alpha).histogram()[255]
    union = ImageChops.lighter(before_alpha, after_alpha).histogram()[255]
    silhouette_iou = intersection / union if union else 1.0
    pixel_delta = sum(ImageChops.difference(before, after).convert("RGB").resize((64, 64)).getdata(0)) / (64 * 64 * 255)
    structural = bool(plan.get("structural_change"))
    changed = hashlib.sha256(source_content).digest() != hashlib.sha256(result_content).digest()
    structure_ok = silhouette_iou < 0.985 if structural else silhouette_iou >= 0.90
    change_ok = changed and (structural or pixel_delta >= 0.005)
    reference_ok = plan.get("strategy") != "reference_edit" or reference_used
    literal_ok = (
        plan.get("strategy") != "lettermark"
        or rendered_literal_text == plan.get("literal_text")
    )
    passed = png_ok and alpha_ok and reference_ok and literal_ok and structure_ok and change_ok
    details.update({
        "png": png_ok,
        "alpha": alpha_ok,
        "literal_exact": literal_ok,
        "silhouette_iou": round(silhouette_iou, 6),
        "pixel_delta": round(pixel_delta, 6),
        "changed": changed,
        "structural_change": structural,
        "structural_change_passed": structure_ok,
        "passed": passed,
    })
    if not passed:
        failures = [key for key, ok in {
            "png_or_size": png_ok, "alpha": alpha_ok, "reference": reference_ok,
            "literal": literal_ok, "geometry": structure_ok, "changed": change_ok,
        }.items() if not ok]
        details["reason"] = "logo compliance failed: " + ", ".join(failures)
    return ComplianceResult(passed, details)
