"""Read-only inspection of retained Universal Ad Posts.

The active Post registry does not offer this retired template for creation or
editing. Historical workspace bytes remain authoritative in PostgreSQL.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .images import PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA
from .natal_brand import NATAL_LOGO_PATH, natal_logo_bytes, natal_logo_colored_bytes
from .studio import StudioRenderer, inspect_media
from .studio_universal import (
    ASSET_SLOTS, DEFAULT_CONFIG, DEFAULT_CONTENT, UNIVERSAL_AD_TEMPLATE_ID, build_universal_template,
    normalize_universal_config, normalize_universal_content, semantic_data,
    texture_asset,
)


def _document(files: Mapping[str, bytes]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        selection = json.loads(files["template.json"])
        configuration = json.loads(files["configuration.json"])
        content = json.loads(files["content.json"])
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError("Retained Post files are unreadable") from error
    if selection != {"schema": "ptw.studio.template-selection.v1", "template_id": UNIVERSAL_AD_TEMPLATE_ID}:
        raise ValueError("Retained Post template selection is invalid")
    return normalize_universal_config(configuration), normalize_universal_content(content)


def detail(files: Mapping[str, bytes], *, state_sha256: str) -> dict[str, Any]:
    configuration, content = _document(files)
    return {
        "schema": "ptw.studio.legacy-post-review.v1",
        "template_id": UNIVERSAL_AD_TEMPLATE_ID,
        "template_name": "Universal ad",
        "editor_key": "post.legacy.readonly",
        "legacy_read_only": True,
        "legacy_sample_content": (
            configuration == normalize_universal_config(DEFAULT_CONFIG)
            and content == normalize_universal_content(DEFAULT_CONTENT)
        ),
        "state_sha256": state_sha256,
        "configuration": configuration,
        "content": content,
        "versions": [],
    }


def _asset(files: Mapping[str, bytes], slot: str) -> dict[str, Any] | None:
    metadata_bytes = files.get(f"assets/{slot}.json")
    if metadata_bytes is None:
        return None
    try:
        metadata = json.loads(metadata_bytes)
        if not isinstance(metadata, Mapping):
            raise ValueError("Retained Post asset metadata is invalid")
        filename = metadata["filename"]
        if not isinstance(filename, str) or "/" in filename or filename in {"", ".", ".."}:
            raise ValueError("Retained Post asset filename is invalid")
        data = files[f"assets/{filename}"]
        mime_type = metadata["mime_type"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Retained Post asset is unreadable: {slot}") from error
    if mime_type not in ASSET_SLOTS[slot]["allowed_mime_types"]:
        raise ValueError(f"Retained Post asset type is invalid: {slot}")
    if hashlib.sha256(data).hexdigest() != metadata.get("sha256"):
        raise ValueError(f"Retained Post asset digest mismatch: {slot}")
    inspected = inspect_media(data, mime_type)
    if inspected["width"] != metadata.get("width") or inspected["height"] != metadata.get("height"):
        raise ValueError(f"Retained Post asset size mismatch: {slot}")
    if slot == "sticker_object":
        source = metadata.get("source") or {}
        if not (
            source.get("provider") == "pexels"
            and source.get("media_type") == "photograph"
            and source.get("subject_type") == "physical_object"
            and source.get("transformation") == "edge_color_soft_alpha_v1"
            and source.get("photographic_object_evidence", {}).get("schema")
            == PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA
        ):
            return None
    return {"bytes": data, "mime_type": mime_type, "sha256": metadata["sha256"],
            "source": metadata.get("source")}


def verify_state(files: Mapping[str, bytes], state_sha256: str) -> None:
    """Check the old v8 workspace snapshot, including fixed and optional art."""

    configuration, content = _document(files)
    assets = []
    for slot in ASSET_SLOTS:
        if slot == "logo" and f"assets/{slot}.json" not in files:
            logo = natal_logo_bytes()
            record = {"mime_type": "image/png", "sha256": hashlib.sha256(logo).hexdigest(),
                      "source": {"origin": "canonical_natal_brand_asset", "filename": NATAL_LOGO_PATH.name}}
        else:
            record = _asset(files, slot)
        assets.append({
            "slot": slot, "available": record is not None,
            "mime_type": None if record is None else record["mime_type"],
            "sha256": None if record is None else record["sha256"],
            "source": None if record is None else record["source"],
        })
    snapshot = {"template_id": UNIVERSAL_AD_TEMPLATE_ID,
                "configuration": configuration, "content": content, "assets": assets}
    canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical(snapshot).encode()).hexdigest()
    if digest != state_sha256:
        raw_configuration = json.loads(files["configuration.json"])
        if raw_configuration.get("schema") in {
            "ptw.studio.universal-ad-config.v6", "ptw.studio.universal-ad-config.v7",
        }:
            snapshot["configuration"] = raw_configuration
            digest = hashlib.sha256(canonical(snapshot).encode()).hexdigest()
    if digest != state_sha256:
        raise RuntimeError("Retained Post state digest does not match its files")


def preview(files: Mapping[str, bytes]) -> dict[str, Any]:
    configuration, content = _document(files)
    assets: dict[str, Mapping[str, Any]] = {}
    for slot in ("background_image", "sticker_object"):
        record = _asset(files, slot)
        if record is not None:
            assets[slot] = record
    if configuration["logo"]["enabled"]:
        assets["logo"] = {
            "bytes": natal_logo_colored_bytes(
                configuration["logo"]["symbol_color"], configuration["logo"]["name_color"]
            ),
            "mime_type": "image/png",
        }
    if configuration["background"]["mode"] == "texture":
        assets["background_texture"] = texture_asset(configuration["background"]["texture"])
    return StudioRenderer().render_preview(
        build_universal_template(configuration, content),
        semantic_data=semantic_data(configuration, content), assets=assets,
    )
