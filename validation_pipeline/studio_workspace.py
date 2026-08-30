"""Local authority for the one-template universal advertising Studio."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .images import PexelsClient
from .natal_brand import NATAL_LOGO_PATH, natal_logo_bytes
from .studio import MAX_IMAGE_BYTES, StudioRenderer, inspect_media
from .studio_universal import (
    ASSET_SLOTS, DEFAULT_CONFIG, DEFAULT_CONTENT, UNIVERSAL_AD_TEMPLATE_ID,
    UNIVERSAL_AD_VERSION_SCHEMA, UNIVERSAL_AD_WORKSPACE_SCHEMA,
    build_universal_template, isolate_object, normalize_universal_config,
    normalize_universal_content, semantic_data, texture_asset,
    universal_ad_catalog, universal_component_settings,
)


_BUNDLED_ASSET_ROOT = Path(__file__).with_name("studio_assets") / "universal_ad"
_BUNDLED_ASSETS = {
    "background_image": {
        "path": _BUNDLED_ASSET_ROOT / "ukraine-investment-background.png",
        "origin": "bundled_tune_asset",
    },
    "sticker_object": {
        "path": _BUNDLED_ASSET_ROOT / "investment-hryvnia-sticker.png",
        "origin": "bundled_tune_asset",
    },
    "logo": {
        "path": NATAL_LOGO_PATH,
        "origin": "canonical_natal_brand_asset",
    },
}
_AGENT_CONTEXT_SCHEMA = "ptw.studio.universal-ad-agent-context.v1"


def _canonical(value: Any) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


class UniversalStudioWorkspace:
    """Persist one reusable universal-ad configuration and immutable outputs."""

    def __init__(
        self, root: Path | str, *, renderer: StudioRenderer | None = None,
        pexels: PexelsClient | None = None,
    ) -> None:
        self.root = Path(root)
        self.renderer = renderer or StudioRenderer()
        self.pexels = pexels
        self.assets = self.root / "assets"
        self.versions = self.root / "versions"
        self.root.mkdir(parents=True, exist_ok=True)
        self.assets.mkdir(parents=True, exist_ok=True)
        self.versions.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        temporary.replace(path)

    @staticmethod
    def _atomic_bytes(path: Path, value: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(value)
        temporary.replace(path)

    def _configuration(self) -> dict[str, Any]:
        path = self.root / "configuration.json"
        if not path.is_file():
            return normalize_universal_config(DEFAULT_CONFIG)
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio universal configuration is unreadable") from error
        return normalize_universal_config(value)

    def _content(self) -> dict[str, Any]:
        path = self.root / "content.json"
        if not path.is_file():
            return normalize_universal_content(DEFAULT_CONTENT)
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio universal content is unreadable") from error
        return normalize_universal_content(value)

    def _asset_record(self, slot: str) -> dict[str, Any] | None:
        metadata_path = self.assets / f"{slot}.json"
        if not metadata_path.is_file():
            bundled = _BUNDLED_ASSETS.get(slot)
            if bundled is None:
                return None
            path = bundled["path"]
            data = natal_logo_bytes() if slot == "logo" else path.read_bytes()
            filename = path.name
            inspected = inspect_media(data, "image/png")
            return {
                "filename": filename,
                "mime_type": "image/png",
                "sha256": hashlib.sha256(data).hexdigest(),
                "width": inspected["width"],
                "height": inspected["height"],
                "byte_count": len(data),
                "source": {"origin": bundled["origin"], "filename": filename},
                "bytes": data,
            }
        try:
            metadata = json.loads(metadata_path.read_text())
            data = (self.assets / str(metadata["filename"])).read_bytes()
        except (OSError, KeyError, json.JSONDecodeError) as error:
            raise ValueError(f"Studio asset metadata is invalid: {slot}") from error
        digest = hashlib.sha256(data).hexdigest()
        if digest != metadata.get("sha256"):
            raise ValueError(f"Studio asset digest mismatch: {slot}")
        return {**metadata, "bytes": data}

    def _asset_records(self, config: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        records: dict[str, Mapping[str, Any]] = {}
        for slot in ASSET_SLOTS:
            record = self._asset_record(slot)
            if record is not None:
                records[slot] = {"bytes": record["bytes"], "mime_type": record["mime_type"]}
        if config["background"]["mode"] == "texture":
            records["background_texture"] = texture_asset(str(config["background"]["texture"]))
        return records

    def _asset_summaries(self) -> list[dict[str, Any]]:
        summaries = []
        for slot, declaration in ASSET_SLOTS.items():
            record = self._asset_record(slot)
            summaries.append({
                "slot": slot,
                "role": declaration["role"],
                "description": declaration["description"],
                "allowed_mime_types": list(declaration["allowed_mime_types"]),
                "available": record is not None,
                "mime_type": None if record is None else record["mime_type"],
                "sha256": None if record is None else record["sha256"],
                "byte_count": None if record is None else record["byte_count"],
                "source": None if record is None else record["source"],
            })
        return summaries

    def _snapshot(self) -> dict[str, Any]:
        return {
            "configuration": self._configuration(),
            "content": self._content(),
            "assets": [
                {
                    "slot": item["slot"], "available": item["available"],
                    "mime_type": item["mime_type"], "sha256": item["sha256"],
                    "source": item["source"],
                }
                for item in self._asset_summaries()
            ],
        }

    def state_sha256(self) -> str:
        return _canonical(self._snapshot())[1]

    def _assert_state(self, base_sha256: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", str(base_sha256)) or self.state_sha256() != base_sha256:
            raise RuntimeError("Studio state changed; reload before saving")

    def _version_records(self) -> list[dict[str, Any]]:
        versions: list[dict[str, Any]] = []
        for path in sorted(self.versions.glob("universal_ad_v*.json")):
            try:
                value = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError(f"Studio universal version is invalid: {path.name}") from error
            if value.get("schema") != UNIVERSAL_AD_VERSION_SCHEMA:
                raise ValueError(f"Studio universal version schema is invalid: {path.name}")
            stored_digest = value.get("version_sha256")
            digest_value = {key: item for key, item in value.items() if key != "version_sha256"}
            if not isinstance(stored_digest, str) or _canonical(digest_value)[1] != stored_digest:
                raise ValueError(f"Studio universal version digest mismatch: {path.name}")
            versions.append(value)
        versions.sort(key=lambda item: int(item["version"]))
        for index, item in enumerate(versions, 1):
            if item["version"] != index:
                raise ValueError("Studio universal versions must be contiguous")
        return versions

    def detail(self) -> dict[str, Any]:
        config, content = self._configuration(), self._content()
        template = build_universal_template(config, content)
        versions = self._version_records()
        return {
            "schema": UNIVERSAL_AD_WORKSPACE_SCHEMA,
            "catalog": universal_ad_catalog(),
            "state_sha256": self.state_sha256(),
            "template_sha256": template.digest,
            "configuration": config,
            "content": content,
            "component_settings": universal_component_settings(config, content),
            "assets": self._asset_summaries(),
            "pexels_available": self.pexels is not None,
            "versions": [{
                "version": item["version"],
                "state_sha256": item["state_sha256"],
                "template_sha256": item["template_sha256"],
                "render_sha256": item["render_sha256"],
                "change_note": item["change_note"],
            } for item in versions],
        }

    def component_settings(
        self, *, state_sha256: str,
        configuration: Mapping[str, Any] | None = None,
        content: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve persisted or draft editor state into canonical component metadata."""

        self._assert_state(state_sha256)
        if (configuration is None) != (content is None):
            raise ValueError("Studio component metadata requires configuration and content together")
        config = self._configuration() if configuration is None else normalize_universal_config(configuration)
        normalized_content = self._content() if content is None else normalize_universal_content(content)
        return universal_component_settings(config, normalized_content)

    def agent_context(self) -> dict[str, Any]:
        """Return the bounded Studio state captured by a Tune agent run."""

        config, content = self._configuration(), self._content()
        template = build_universal_template(config, content)
        value = {
            "schema": _AGENT_CONTEXT_SCHEMA,
            "template_id": UNIVERSAL_AD_TEMPLATE_ID,
            "template_version": template.document["version"],
            "state_sha256": self.state_sha256(),
            "template_sha256": template.digest,
            "component_settings": universal_component_settings(config, content),
            "assets": self._snapshot()["assets"],
        }
        _, digest = _canonical(value)
        return {**value, "sha256": digest}

    def save_configuration(
        self, *, base_sha256: str, configuration: Mapping[str, Any], content: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._assert_state(base_sha256)
        normalized_config = normalize_universal_config(configuration)
        normalized_content = normalize_universal_content(content)
        self._atomic_json(self.root / "configuration.json", normalized_config)
        self._atomic_json(self.root / "content.json", normalized_content)
        return self.detail()

    def _store_asset(
        self, slot: str, *, mime_type: str, data: bytes, source: Mapping[str, Any],
    ) -> None:
        if slot not in ASSET_SLOTS:
            raise KeyError(f"Studio asset slot not found: {slot}")
        if mime_type not in ASSET_SLOTS[slot]["allowed_mime_types"]:
            raise ValueError(f"Studio {slot} MIME type is outside its fixed slot")
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Studio asset bytes are empty or exceed the 12 MB limit")
        inspected = inspect_media(data, mime_type)
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime_type]
        filename = f"{slot}.{extension}"
        digest = hashlib.sha256(data).hexdigest()
        self._atomic_bytes(self.assets / filename, data)
        self._atomic_json(self.assets / f"{slot}.json", {
            "filename": filename,
            "mime_type": mime_type,
            "sha256": digest,
            "width": inspected["width"],
            "height": inspected["height"],
            "byte_count": len(data),
            "source": json.loads(json.dumps(dict(source))),
        })

    def upload_asset(
        self, slot: str, *, base_sha256: str, mime_type: str, bytes_base64: str,
    ) -> dict[str, Any]:
        self._assert_state(base_sha256)
        try:
            data = base64.b64decode(bytes_base64, validate=True)
        except (TypeError, ValueError) as error:
            raise ValueError("Studio asset bytes are not valid base64") from error
        self._store_asset(slot, mime_type=mime_type, data=data, source={"origin": "owner_upload"})
        if slot in {"background_image", "logo"}:
            config = self._configuration()
        if slot == "background_image":
            config["background"]["mode"] = "image"
            self._atomic_json(self.root / "configuration.json", normalize_universal_config(config))
        elif slot == "logo":
            config["logo"]["enabled"] = True
            self._atomic_json(self.root / "configuration.json", normalize_universal_config(config))
        return self.detail()

    def source_pexels(
        self, slot: str, *, base_sha256: str, query: str, isolate: bool,
    ) -> dict[str, Any]:
        self._assert_state(base_sha256)
        if slot not in {"background_image", "sticker_object"}:
            raise ValueError("Pexels is available only for the background and sticker slots")
        if self.pexels is None:
            raise RuntimeError("Pexels is not configured for this Studio runtime")
        query = " ".join(query.split())
        if not 2 <= len(query) <= 160:
            raise ValueError("Pexels query must contain 2 to 160 characters")
        used_ids = {
            str(record["source"].get("external_id"))
            for record in (self._asset_record(item) for item in ASSET_SLOTS)
            if record is not None and isinstance(record.get("source"), Mapping)
            and record["source"].get("provider") == "pexels"
        }
        photo, data = self.pexels.select(query, query, used_ids=used_ids)
        mime_type = "image/jpeg"
        transformation = "none"
        if slot == "sticker_object":
            if not isolate:
                raise ValueError("Pexels sticker objects must use the bounded background-isolation transform")
            data = isolate_object(data)
            mime_type = "image/png"
            transformation = "edge_color_soft_alpha_v1"
        source = {
            "origin": "pexels",
            **photo.source_metadata(),
            "query": query,
            "transformation": transformation,
        }
        self._store_asset(slot, mime_type=mime_type, data=data, source=source)
        config = self._configuration()
        if slot == "background_image":
            config["background"]["mode"] = "image"
        else:
            config["sticker"]["enabled"] = True
        self._atomic_json(self.root / "configuration.json", normalize_universal_config(config))
        return self.detail()

    def render_preview(
        self, *, state_sha256: str,
        configuration: Mapping[str, Any] | None = None,
        content: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._assert_state(state_sha256)
        if (configuration is None) != (content is None):
            raise ValueError("Studio draft preview requires configuration and content together")
        config = self._configuration() if configuration is None else normalize_universal_config(configuration)
        normalized_content = self._content() if content is None else normalize_universal_content(content)
        template = build_universal_template(config, normalized_content)
        rendered = self.renderer.render_preview(
            template,
            semantic_data=semantic_data(config, normalized_content),
            assets=self._asset_records(config),
        )
        rendered["resolved"]["component_settings"] = universal_component_settings(
            config, normalized_content,
        )
        return rendered

    @staticmethod
    def _change_note(value: Any) -> str:
        normalized = " ".join(str(value).split())
        if not 1 <= len(normalized) <= 500:
            raise ValueError("Studio version change note must contain 1 to 500 characters")
        return normalized

    def approve_version(self, *, state_sha256: str, change_note: str) -> dict[str, Any]:
        self._assert_state(state_sha256)
        preview = self.render_preview(state_sha256=state_sha256)
        config, content = self._configuration(), self._content()
        template = build_universal_template(config, content)
        versions = self._version_records()
        version = len(versions) + 1
        record = {
            "schema": UNIVERSAL_AD_VERSION_SCHEMA,
            "template_id": UNIVERSAL_AD_TEMPLATE_ID,
            "version": version,
            "state_sha256": state_sha256,
            "template_sha256": template.digest,
            "render_sha256": preview["bytes_sha256"],
            "change_note": self._change_note(change_note),
            "configuration": config,
            "content": content,
            "component_settings": universal_component_settings(config, content),
            "assets": self._snapshot()["assets"],
            "primitive_template": template.document,
        }
        raw, digest = _canonical(record)
        record = {**json.loads(raw), "version_sha256": digest}
        json_path = self.versions / f"universal_ad_v{version}.json"
        png_path = self.versions / f"universal_ad_v{version}.png"
        if json_path.exists() or png_path.exists():
            raise FileExistsError("Studio universal version already exists")
        self._atomic_bytes(png_path, preview["bytes"])
        self._atomic_json(json_path, record)
        return self.detail()

    def version_detail(self, version: int) -> dict[str, Any]:
        if isinstance(version, bool) or version < 1:
            raise KeyError(f"Studio universal version not found: {version}")
        records = self._version_records()
        if version > len(records):
            raise KeyError(f"Studio universal version not found: {version}")
        return json.loads(json.dumps(records[version - 1], ensure_ascii=False))

    def version_render(self, version: int) -> dict[str, Any]:
        if isinstance(version, bool) or version < 1:
            raise KeyError(f"Studio universal version not found: {version}")
        records = self._version_records()
        if version > len(records):
            raise KeyError(f"Studio universal version not found: {version}")
        record = records[version - 1]
        try:
            data = (self.versions / f"universal_ad_v{version}.png").read_bytes()
        except OSError as error:
            raise ValueError(f"Studio universal render is unavailable: {version}") from error
        digest = hashlib.sha256(data).hexdigest()
        if digest != record["render_sha256"]:
            raise ValueError(f"Studio universal render digest mismatch: {version}")
        return {"bytes": data, "mime_type": "image/png", "sha256": digest}
