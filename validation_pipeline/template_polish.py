"""Versioned, deliberately narrow Post polish contract and immutable comparison."""
from copy import deepcopy
from pathlib import Path

from .template_components import apply_edits

PROFILE = "impeccable-post-v1"
INSTRUCTION = "Polish this Post's typography, spacing, alignment and image placement while preserving its design direction."
ORIGINAL_FIELDS = ("documents", "previews", "comparison", "instruction", "analysis", "iterations", "latest_correction")
COMPONENT_FIELDS = {"box", "mobile_box", "font_size", "font_weight", "align"}
NATIVE_FIELDS = {"x", "y", "width", "height", "title_size", "body_size", "size", "gap", "feature_x", "feature_y",
                 "feature_width", "feature_height", "feature_size", "detail_size", "padding", "align"}


def guidance(skill_path: Path) -> str:
    return (skill_path.parent / "references/impeccable-post-v1.md").read_text(encoding="utf-8")


def snapshot(run: dict) -> dict:
    return {"revision": run["revision"], "state_sha256": run["state_sha256"],
            **{key: deepcopy(run.get(key)) for key in ORIGINAL_FIELDS}}


def changes(original: dict, candidate: dict) -> list[str]:
    """Reject protected changes, including edits hidden inside a compound value."""
    before, after = deepcopy(original), deepcopy(candidate)
    categories = set()

    def allowed_fields(left, right, allowed, *, native=False):
        if left.keys() != right.keys():
            raise ValueError("Post polish must preserve all existing fields")
        for key in allowed & left.keys():
            old, new = left[key], right[key]
            if old == new:
                continue
            if key in {"box", "mobile_box"}:
                if any(abs(a-b) > 100 for a, b in zip(old, new)) or any(not .65*a <= b <= 1.4*a for a,b in zip(old[2:], new[2:])):
                    raise ValueError("Post polish must preserve the overall composition")
            elif isinstance(old, (int, float)) and not isinstance(old, bool):
                position = native and (key.endswith(("_x", "_y")) or key in {"x", "y"})
                if (position and abs(new-old) > 10) or (not position and abs(new-old) > max(2, abs(old)*.4)):
                    raise ValueError("Post polish adjustments must remain restrained")
            categories.add("typography" if key in {"font_size", "font_weight", "title_size", "body_size", "size", "feature_size", "detail_size"} else "layout")
            right[key] = deepcopy(old)

    if set(before) != {"post"} or set(after) != {"post"}:
        raise ValueError("Post polish requires a Post-only draft")
    a, b = before["post"], after["post"]
    if len(a["components"]) != len(b["components"]):
        raise ValueError("Post polish must preserve components")
    for left, right in zip(a["components"], b["components"]):
        allowed_fields(left, right, COMPONENT_FIELDS)
    for left, right in zip(a.get("text_groups", []), b.get("text_groups", [])):
        allowed_fields(left, right, {"gap", "bullet_indent"})
    if "daddy_configuration" in a and "daddy_configuration" in b:
        for block, left in a["daddy_configuration"].items():
            right = b["daddy_configuration"].get(block)
            if isinstance(left, dict) and isinstance(right, dict):
                allowed_fields(left, right, NATIVE_FIELDS, native=True)
    if before != after:
        raise ValueError("Post polish must preserve copy, assets, colors, fonts, roles and design identity")
    return sorted(categories)


def validate_edits(run: dict, edits: list) -> None:
    polish = run.get("polish")
    if polish:
        changes(polish["original"]["documents"], apply_edits(run["documents"], edits))
