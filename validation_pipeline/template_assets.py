"""Offline, digest-pinned assets available to declarative Studio templates."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ASSET_ROOT = Path(__file__).with_name("studio_assets") / "template-assets"
RENDERER_VERSION = "studio.declarative.pillow.v6"

_manifest = json.loads((ASSET_ROOT / "manifest.json").read_text(encoding="utf-8"))
if _manifest.get("schema") != "ptw.template-assets.v1" or not isinstance(_manifest.get("assets"), list):
    raise RuntimeError("Template asset manifest is invalid")
_ASSETS: dict[str, dict[str, Any]] = {
    str(item["asset_id"]): {**item, "mime_type": "image/png", "immutable": True}
    for item in _manifest["assets"]
}
if set(_ASSETS) != {"app_store_badge_en", "google_play_badge_en", "owner_app_store_badge_v1", "owner_google_play_badge_v1", "neutral_person_stock_v1"}:
    raise RuntimeError("Template asset manifest registrations are invalid")

ASSET_IDS = ("", "natal_symbol", *_ASSETS)


def _checked_file(name: str, digest: str) -> bytes:
    data = (ASSET_ROOT / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError(f"Template asset digest mismatch: {name}")
    return data


def asset_bytes(asset_id: str) -> tuple[bytes, str]:
    if asset_id == "natal_symbol":
        from .natal_brand import natal_symbol_bytes
        data = natal_symbol_bytes("#B8F4F2")
        return data, "image/png"
    item = _ASSETS.get(asset_id)
    if item is None:
        raise ValueError("Template asset is not registered")
    return _checked_file(item["file"], item["sha256"]), item["mime_type"]


def asset_metadata(asset_id: str) -> dict[str, Any]:
    if asset_id == "natal_symbol":
        data, mime_type = asset_bytes(asset_id)
        return {
            "asset_id": asset_id,
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_url": "ptw://natal/canonical-symbol",
            "locale": None,
            "license_type": "PTW canonical brand asset",
            "mime_type": mime_type,
            "immutable": True,
        }
    item = _ASSETS[asset_id]
    _checked_file(item["source_file"], item["source_sha256"])
    return {"asset_id": asset_id, **deepcopy(item)}


def document_asset_manifest(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    identifiers = sorted({str(item.get("asset_id") or "") for item in document.get("components", [])} - {""})
    return [asset_metadata(identifier) for identifier in identifiers]
