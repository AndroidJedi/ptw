"""Local authority for the bounded Universal Studio template workspace."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .images import (
    PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA, PexelsClient,
    validate_pexels_photographic_object, validate_pexels_photographic_object_query,
)
from .natal_brand import NATAL_LOGO_PATH, natal_logo_bytes
from .openai_images import phone_screen_art_prompt
from .studio_phone_metrics import (
    DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_CONTENT, IPHONE_FRAME_SOURCE,
    PHONE_ASSET_SLOTS, PHONE_METRICS_CONFIG_SCHEMA, PHONE_METRICS_TEMPLATE_ID,
    PHONE_METRICS_TEMPLATE_VERSION, build_phone_metrics_template,
    compose_phone_device_asset, iphone_frame_record, normalize_phone_metrics_config,
    normalize_phone_metrics_content, phone_metrics_catalog,
    phone_metrics_component_settings, phone_metrics_semantic_data,
)
from .studio import MAX_IMAGE_BYTES, StudioRenderer, inspect_media
from .studio_universal import (
    ASSET_SLOTS, DEFAULT_CONFIG, DEFAULT_CONTENT, UNIVERSAL_AD_TEMPLATE_ID,
    UNIVERSAL_AD_VERSION_SCHEMA, UNIVERSAL_AD_WORKSPACE_SCHEMA,
    build_universal_template, isolate_object, normalize_universal_config,
    normalize_universal_content, semantic_data, texture_asset,
    universal_ad_catalog, universal_component_settings,
)


_BUNDLED_ASSETS = {
    "logo": {
        "path": NATAL_LOGO_PATH,
        "origin": "canonical_natal_brand_asset",
    },
}
_WORKSPACE_SCHEMA = "ptw.studio.workspace.v7"
_TEMPLATE_SELECTION_SCHEMA = "ptw.studio.template-selection.v1"
_TEMPLATE_VERSION_SCHEMA = "ptw.studio.template-version.v1"
_AGENT_CONTEXT_SCHEMA = "ptw.studio.agent-context.v3"
_TEMPLATE_SUMMARIES = (
    {
        "template_id": UNIVERSAL_AD_TEMPLATE_ID,
        "name": "Universal ad",
        "description": "Editable square composition with a fixed Natal brand lock-up.",
        "canvas": {"width": 1080, "height": 1080},
    },
    {
        "template_id": PHONE_METRICS_TEMPLATE_ID,
        "name": "Phone & metrics",
        "description": "Natal 4:5 phone creative with three metrics and a full-width CTA.",
        "canvas": {"width": 1080, "height": 1350},
    },
)


def _canonical(value: Any) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def _approved_sticker_photo(record: Mapping[str, Any] | None) -> bool:
    source = {} if record is None else record.get("source") or {}
    return bool(
        source.get("provider") == "pexels"
        and source.get("media_type") == "photograph"
        and source.get("subject_type") == "physical_object"
        and source.get("transformation") == "edge_color_soft_alpha_v1"
        and source.get("photographic_object_evidence", {}).get("schema")
        == PEXELS_PHOTOGRAPHIC_OBJECT_EVIDENCE_SCHEMA
    )


class UniversalStudioWorkspace:
    """Persist one selected bounded Studio template and immutable outputs."""

    def __init__(
        self, root: Path | str, *, renderer: StudioRenderer | None = None,
        pexels: PexelsClient | None = None, image_provider: Any | None = None,
    ) -> None:
        self.root = Path(root)
        self.renderer = renderer or StudioRenderer()
        self.pexels = pexels
        self.image_provider = image_provider
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

    def _selected_template_id(self) -> str:
        path = self.root / "template.json"
        if not path.is_file():
            # A missing selector is the exact legacy universal workspace.
            return UNIVERSAL_AD_TEMPLATE_ID
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio template selection is unreadable") from error
        if not isinstance(value, Mapping) or set(value) != {"schema", "template_id"}:
            raise ValueError("Studio template selection fields are invalid")
        if value["schema"] != _TEMPLATE_SELECTION_SCHEMA or value["template_id"] not in {
            UNIVERSAL_AD_TEMPLATE_ID, PHONE_METRICS_TEMPLATE_ID,
        }:
            raise ValueError("Studio template selection is invalid")
        return str(value["template_id"])

    def _asset_slots(self) -> Mapping[str, Mapping[str, Any]]:
        return PHONE_ASSET_SLOTS if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID else ASSET_SLOTS

    def _normalize_configuration(self, value: Mapping[str, Any]) -> dict[str, Any]:
        if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
            return normalize_phone_metrics_config(value)
        return normalize_universal_config(value)

    def _normalize_content(self, value: Mapping[str, Any]) -> dict[str, Any]:
        if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
            return normalize_phone_metrics_content(value)
        return normalize_universal_content(value)

    def _build_template(self, config: Mapping[str, Any], content: Mapping[str, Any]):
        if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
            return build_phone_metrics_template(config, content)
        return build_universal_template(config, content)

    def _catalog(self) -> dict[str, Any]:
        if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
            return phone_metrics_catalog()
        return universal_ad_catalog()

    def _component_settings(self, config: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
        if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
            return phone_metrics_component_settings(config, content)
        return universal_component_settings(config, content)

    def _configuration(self) -> dict[str, Any]:
        path = self.root / "configuration.json"
        if not path.is_file():
            if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
                return normalize_phone_metrics_config(DEFAULT_PHONE_CONFIG)
            return normalize_universal_config(DEFAULT_CONFIG)
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio configuration is unreadable") from error
        return self._normalize_configuration(value)

    def _content(self) -> dict[str, Any]:
        path = self.root / "content.json"
        if not path.is_file():
            if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
                return normalize_phone_metrics_content(DEFAULT_PHONE_CONTENT)
            return normalize_universal_content(DEFAULT_CONTENT)
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio content is unreadable") from error
        return self._normalize_content(value)

    def _asset_record(self, slot: str) -> dict[str, Any] | None:
        # Natal is never replaced by a draft upload. An old workspace may still
        # contain logo metadata, but new renders deliberately ignore it.
        if slot == "logo":
            data = natal_logo_bytes()
            inspected = inspect_media(data, "image/png")
            return {
                "filename": NATAL_LOGO_PATH.name, "mime_type": "image/png",
                "sha256": hashlib.sha256(data).hexdigest(), "width": inspected["width"],
                "height": inspected["height"], "byte_count": len(data),
                "source": {"origin": "canonical_natal_brand_asset", "filename": NATAL_LOGO_PATH.name},
                "bytes": data,
            }
        if slot == "iphone_frame":
            return iphone_frame_record()
        metadata_path = self.assets / f"{slot}.json"
        if not metadata_path.is_file():
            bundled = _BUNDLED_ASSETS.get(slot)
            if bundled is None:
                return None
            path = bundled["path"]
            data = natal_logo_bytes()
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

    def _asset_records(self, config: Mapping[str, Any], content: Mapping[str, Any] | None = None) -> dict[str, Mapping[str, Any]]:
        if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
            normalized_content = self._content() if content is None else normalize_phone_metrics_content(content)
            screen = self._asset_record("phone_screen")
            device = compose_phone_device_asset(
                None if screen is None else screen["bytes"], normalized_content["phone_hero_title"],
                normalized_content["cta"],
                str(config["phone_screen"]["texture"]),
                list(normalized_content["phone_buttons"]),
                list(config["phone_buttons"]),
            )
            logo = self._asset_record("logo")
            if logo is None:
                raise RuntimeError("Canonical Natal logo is unavailable")
            records = {
                "logo": {"bytes": logo["bytes"], "mime_type": logo["mime_type"]},
                "phone_device": {"bytes": device["bytes"], "mime_type": device["mime_type"]},
            }
            if config["background"]["texture"] != "none":
                records["background_texture"] = texture_asset(
                    str(config["background"]["texture"]),
                )
            if config["copy_background"]["texture"] != "none":
                records["copy_background_texture"] = texture_asset(
                    str(config["copy_background"]["texture"]),
                )
            return records
        records: dict[str, Mapping[str, Any]] = {}
        for slot in ASSET_SLOTS:
            record = self._asset_record(slot)
            if slot == "sticker_object" and not _approved_sticker_photo(record):
                continue
            if record is not None:
                records[slot] = {"bytes": record["bytes"], "mime_type": record["mime_type"]}
        if config["background"]["mode"] == "texture":
            records["background_texture"] = texture_asset(str(config["background"]["texture"]))
        return records

    def _asset_summaries(self) -> list[dict[str, Any]]:
        if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
            summaries = []
            for slot, declaration in PHONE_ASSET_SLOTS.items():
                record = self._asset_record(slot)
                summaries.append({
                    "slot": slot, "role": declaration["role"], "description": declaration["description"],
                    "allowed_mime_types": list(declaration["allowed_mime_types"]), "editable": False,
                    "available": record is not None, "mime_type": None if record is None else record["mime_type"],
                    "sha256": None if record is None else record["sha256"], "byte_count": None if record is None else record["byte_count"],
                    "source": None if record is None else record["source"],
                })
            for slot, role, description in (
                ("iphone_frame", "device_frame", "Fixed checked-in black iPhone frame."),
                ("logo", "brand", "Fixed canonical Natal logo and name."),
            ):
                record = self._asset_record(slot)
                summaries.append({
                    "slot": slot, "role": role, "description": description,
                    "allowed_mime_types": ["image/png"], "editable": False, "available": True,
                    "mime_type": record["mime_type"], "sha256": record["sha256"],
                    "byte_count": record["byte_count"], "source": record["source"],
                })
            return summaries
        summaries = []
        for slot, declaration in ASSET_SLOTS.items():
            record = self._asset_record(slot)
            if slot == "sticker_object" and not _approved_sticker_photo(record):
                record = None
            summaries.append({
                "slot": slot,
                "role": declaration["role"],
                "description": declaration["description"],
                "allowed_mime_types": list(declaration["allowed_mime_types"]),
                "editable": slot != "logo",
                "available": record is not None,
                "mime_type": None if record is None else record["mime_type"],
                "sha256": None if record is None else record["sha256"],
                "byte_count": None if record is None else record["byte_count"],
                "source": None if record is None else record["source"],
            })
        return summaries

    def _snapshot(self) -> dict[str, Any]:
        return {
            "template_id": self._selected_template_id(),
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
        for path in sorted(self.versions.glob("*_v*.json")):
            try:
                value = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError(f"Studio version is invalid: {path.name}") from error
            if value.get("schema") not in {UNIVERSAL_AD_VERSION_SCHEMA, _TEMPLATE_VERSION_SCHEMA}:
                raise ValueError(f"Studio version schema is invalid: {path.name}")
            stored_digest = value.get("version_sha256")
            digest_value = {key: item for key, item in value.items() if key != "version_sha256"}
            if not isinstance(stored_digest, str) or _canonical(digest_value)[1] != stored_digest:
                raise ValueError(f"Studio version digest mismatch: {path.name}")
            versions.append(value)
        versions.sort(key=lambda item: int(item["version"]))
        for index, item in enumerate(versions, 1):
            if item["version"] != index:
                raise ValueError("Studio versions must be contiguous")
        return versions

    def detail(self) -> dict[str, Any]:
        config, content = self._configuration(), self._content()
        template = self._build_template(config, content)
        versions = self._version_records()
        return {
            "schema": _WORKSPACE_SCHEMA,
            "template_id": self._selected_template_id(),
            "templates": [json.loads(json.dumps(item)) for item in _TEMPLATE_SUMMARIES],
            "catalog": self._catalog(),
            "state_sha256": self.state_sha256(),
            "template_sha256": template.digest,
            "configuration": config,
            "content": content,
            "component_settings": self._component_settings(config, content),
            "assets": self._asset_summaries(),
            "pexels_available": self.pexels is not None,
            "phone_screen_generation_available": self.image_provider is not None,
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
        config = self._configuration() if configuration is None else self._normalize_configuration(configuration)
        normalized_content = self._content() if content is None else self._normalize_content(content)
        return self._component_settings(config, normalized_content)

    def agent_context(self) -> dict[str, Any]:
        """Return the bounded Studio state captured by a Tune agent run."""

        config, content = self._configuration(), self._content()
        template = self._build_template(config, content)
        value = {
            "schema": _AGENT_CONTEXT_SCHEMA,
            "template_id": self._selected_template_id(),
            "template_version": template.document["version"],
            "state_sha256": self.state_sha256(),
            "template_sha256": template.digest,
            "component_settings": self._component_settings(config, content),
            "assets": self._snapshot()["assets"],
        }
        _, digest = _canonical(value)
        return {**value, "sha256": digest}

    def capture_saved_export(self, state_sha256: str) -> dict[str, Any]:
        """Capture the saved—not draft—Universal Studio state."""

        self._assert_state(state_sha256)
        config, content = self._configuration(), self._content()
        template = self._build_template(config, content)
        value = {
            "schema": "ptw.studio.template-export.v1",
            "template_id": self._selected_template_id(),
            "template_version": template.document["version"],
            "state_sha256": state_sha256,
            "template_sha256": template.digest,
            "configuration": config,
            "content": content,
            "component_settings": self._component_settings(config, content),
            "assets": self._snapshot()["assets"],
            "primitive_template": template.document,
        }
        _, digest = _canonical(value)
        return {**value, "sha256": digest}

    def render_experiment(
        self, *, configuration: Mapping[str, Any], content: Mapping[str, Any],
        background_asset: Mapping[str, Any] | None = None,
        sticker_asset: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Render one isolated local Studio preview."""

        if self._selected_template_id() != UNIVERSAL_AD_TEMPLATE_ID:
            raise ValueError("Studio Tune experiments support only the universal ad template")
        config = normalize_universal_config(configuration)
        normalized_content = normalize_universal_content(content)
        assets: dict[str, Mapping[str, Any]] = {}
        if config["background"]["mode"] == "image":
            if background_asset is None:
                raise ValueError("photo background requires one explicit Studio image")
            assets["background_image"] = {
                "bytes": bytes(background_asset["bytes"]),
                "mime_type": str(background_asset["mime_type"]),
            }
        elif config["background"]["mode"] == "texture":
            assets["background_texture"] = texture_asset(str(config["background"]["texture"]))
        if config["logo"]["enabled"]:
            logo = self._asset_record("logo")
            if logo is None:
                raise ValueError("Universal experiment requires the saved canonical logo identity")
            assets["logo"] = {"bytes": logo["bytes"], "mime_type": logo["mime_type"]}
        if config["sticker"]["enabled"]:
            sticker = sticker_asset or self._asset_record("sticker_object")
            if not _approved_sticker_photo(sticker):
                raise ValueError(
                    "Universal experiment sticker requires a screened Pexels photograph"
                )
            assets["sticker_object"] = {
                "bytes": sticker["bytes"], "mime_type": sticker["mime_type"],
            }
        template = build_universal_template(config, normalized_content)
        rendered = self.renderer.render_preview(
            template, semantic_data=semantic_data(config, normalized_content), assets=assets,
        )
        rendered["resolved"]["component_settings"] = universal_component_settings(
            config, normalized_content,
        )
        return rendered

    def save_configuration(
        self, *, base_sha256: str, configuration: Mapping[str, Any], content: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._assert_state(base_sha256)
        normalized_config = self._normalize_configuration(configuration)
        normalized_content = self._normalize_content(content)
        self._atomic_json(self.root / "configuration.json", normalized_config)
        self._atomic_json(self.root / "content.json", normalized_content)
        return self.detail()

    def apply_template(self, *, base_sha256: str, template_id: str) -> dict[str, Any]:
        """Replace the entire mutable Studio draft with one preset template."""

        self._assert_state(base_sha256)
        if template_id not in {UNIVERSAL_AD_TEMPLATE_ID, PHONE_METRICS_TEMPLATE_ID}:
            raise ValueError("Studio template is not registered")
        # The workspace asset directory has no immutable version material. List
        # exact paths before removal so applying a template cannot touch any
        # sibling authority or version history.
        for path in list(self.assets.iterdir()):
            if path.is_file():
                path.unlink()
        for name in ("configuration.json", "content.json"):
            path = self.root / name
            if path.exists():
                path.unlink()
        self._atomic_json(self.root / "template.json", {
            "schema": _TEMPLATE_SELECTION_SCHEMA, "template_id": template_id,
        })
        return self.detail()

    def _store_asset(
        self, slot: str, *, mime_type: str, data: bytes, source: Mapping[str, Any],
    ) -> None:
        asset_slots = self._asset_slots()
        if slot not in asset_slots:
            raise KeyError(f"Studio asset slot not found: {slot}")
        if mime_type not in asset_slots[slot]["allowed_mime_types"]:
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
        if slot == "logo":
            raise ValueError("Natal is the fixed Studio identity and cannot be replaced")
        if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
            raise ValueError(
                "Phone & metrics screen art is generated server-side and cannot be uploaded or replaced"
            )
        elif slot == "sticker_object":
            raise ValueError(
                "Studio stickers must be isolated from a screened Pexels photograph; "
                "direct sticker uploads are not allowed"
            )
        try:
            data = base64.b64decode(bytes_base64, validate=True)
        except (TypeError, ValueError) as error:
            raise ValueError("Studio asset bytes are not valid base64") from error
        self._store_asset(slot, mime_type=mime_type, data=data, source={"origin": "owner_upload"})
        if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID:
            return self.detail()
        if slot == "background_image":
            config = self._configuration()
        if slot == "background_image":
            config["background"]["mode"] = "image"
            self._atomic_json(self.root / "configuration.json", normalize_universal_config(config))
        return self.detail()

    def store_generated_phone_screen(
        self, *, base_sha256: str, data: bytes, source: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist only validated server-generated artwork for the phone aperture."""

        self._assert_state(base_sha256)
        if self._selected_template_id() != PHONE_METRICS_TEMPLATE_ID:
            raise ValueError("generated phone-screen artwork requires the phone-and-metrics template")
        if source.get("origin") not in {
            "codex_builtin_image_generation", "openai_image_api",
        } or source.get("text_in_screen") != "prohibited_by_prompt":
            raise ValueError("phone-screen artwork must carry verified text-free generation provenance")
        self._store_asset(
            "phone_screen", mime_type="image/png", data=data,
            source=source,
        )
        return self.detail()

    def generate_phone_screen(
        self, *, base_sha256: str, visual_direction: str,
        enhance_current: bool = False,
    ) -> dict[str, Any]:
        """Generate or reference-edit one mutable, text-free phone hero artwork."""

        self._assert_state(base_sha256)
        if self._selected_template_id() != PHONE_METRICS_TEMPLATE_ID:
            raise ValueError("phone-screen generation requires the phone-and-metrics template")
        if self.image_provider is None:
            raise RuntimeError("Codex image generation is unavailable in this local Studio runtime")
        if not isinstance(enhance_current, bool):
            raise ValueError("enhance current phone-screen setting must be boolean")
        current_screen = self._asset_record("phone_screen")
        if enhance_current and current_screen is None:
            raise ValueError(
                "Enhance current image requires an existing generated phone visual"
            )
        normalized_direction = " ".join(str(visual_direction or "").split())
        prompt = phone_screen_art_prompt(
            normalized_direction, enhance_current=enhance_current,
        )
        try:
            generated = (
                self.image_provider.generate(
                    prompt, reference_image=bytes(current_screen["bytes"]),
                )
                if enhance_current and current_screen is not None
                else self.image_provider.generate(prompt)
            )
        except ValueError:
            raise
        except Exception as error:
            raise RuntimeError(
                "Phone-screen image generation failed; the previous visual was preserved"
            ) from error
        if generated.get("mime_type") != "image/png":
            raise RuntimeError("Phone-screen image generation did not return a PNG")
        source = dict(generated.get("source") or {})
        source.update({
            "visual_direction": normalized_direction,
            "visual_direction_sha256": hashlib.sha256(
                normalized_direction.encode()
            ).hexdigest(),
            "generation_mode": (
                "enhance_current" if enhance_current else "generate_new"
            ),
            "prompt_contract": (
                "owner_directed_text_free_phone_hero_enhancement_v1"
                if enhance_current else "owner_directed_text_free_phone_hero_v1"
            ),
        })
        if enhance_current and current_screen is not None:
            source.update({
                "reference_asset_sha256": current_screen["sha256"],
                "reference_image_sha256": current_screen["sha256"],
            })
        return self.store_generated_phone_screen(
            base_sha256=base_sha256, data=bytes(generated.get("bytes") or b""),
            source=source,
        )

    def source_pexels(
        self, slot: str, *, base_sha256: str, query: str, isolate: bool,
        required_subject_terms: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        self._assert_state(base_sha256)
        if self._selected_template_id() != UNIVERSAL_AD_TEMPLATE_ID:
            raise ValueError("Pexels sourcing is unavailable for the fixed phone-and-metrics template")
        if slot not in {"background_image", "sticker_object"}:
            raise ValueError("Pexels is available only for the background and sticker slots")
        if self.pexels is None:
            raise RuntimeError("Pexels is not configured for this Studio runtime")
        if slot == "sticker_object" and not isolate:
            raise ValueError(
                "Pexels sticker objects must use the bounded background-isolation transform"
            )
        query = " ".join(query.split())
        if not 2 <= len(query) <= 160:
            raise ValueError("Pexels query must contain 2 to 160 characters")
        subject_terms = tuple(sorted({
            " ".join(str(term).casefold().split())
            for term in required_subject_terms
            if " ".join(str(term).casefold().split())
        }))
        if required_subject_terms and not subject_terms:
            raise ValueError("Pexels required sticker subject terms are empty")
        if slot != "sticker_object" and subject_terms:
            raise ValueError("Pexels background requests cannot require sticker subjects")
        if slot == "sticker_object":
            validate_pexels_photographic_object_query(query)
        used_ids = {
            str(record["source"].get("external_id"))
        for record in (self._asset_record(item) for item in ASSET_SLOTS)
            if record is not None and isinstance(record.get("source"), Mapping)
            and record["source"].get("provider") == "pexels"
        }
        photo = None
        data = b""
        photographic_object_evidence = None
        last_error: Exception | None = None
        attempts = 6 if slot == "sticker_object" else 1
        for _attempt in range(attempts):
            try:
                select_kwargs: dict[str, Any] = {"used_ids": used_ids}
                if subject_terms:
                    select_kwargs["required_alt_terms"] = subject_terms
                photo, data = self.pexels.select(
                    query,
                    (
                        "real physical object on a plain warm background close-up photograph"
                        if slot == "sticker_object" else query
                    ),
                    **select_kwargs,
                )
                used_ids.add(photo.photo_id)
                if slot == "sticker_object":
                    photographic_object_evidence = validate_pexels_photographic_object(
                        photo, data, query=query, required_subject_terms=subject_terms,
                    )
                    data = isolate_object(data)
                break
            except Exception as error:
                last_error = error
                photo = None
        if photo is None:
            if slot == "sticker_object":
                raise RuntimeError(
                    "Pexels did not return an isolatable real photographed object"
                ) from last_error
            raise RuntimeError(
                "Pexels did not return a usable photographic background"
            ) from last_error
        mime_type = "image/jpeg"
        transformation = "none"
        if slot == "sticker_object":
            mime_type = "image/png"
            transformation = "edge_color_soft_alpha_v1"
        source = {
            "origin": "pexels",
            **photo.source_metadata(),
            "query": query,
            "transformation": transformation,
            "media_type": "photograph",
        }
        if slot == "sticker_object":
            source.update({
                "subject_type": "physical_object",
                "photographic_object_evidence": photographic_object_evidence,
            })
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
        config = self._configuration() if configuration is None else self._normalize_configuration(configuration)
        normalized_content = self._content() if content is None else self._normalize_content(content)
        template = self._build_template(config, normalized_content)
        assets = self._asset_records(config, normalized_content)
        if self._selected_template_id() == UNIVERSAL_AD_TEMPLATE_ID and config["sticker"]["enabled"] and "sticker_object" not in assets:
            raise ValueError("Studio sticker requires a screened Pexels photograph")
        rendered = self.renderer.render_preview(
            template,
            semantic_data=(
                phone_metrics_semantic_data(config, normalized_content)
                if self._selected_template_id() == PHONE_METRICS_TEMPLATE_ID
                else semantic_data(config, normalized_content)
            ),
            assets=assets,
        )
        rendered["resolved"]["component_settings"] = self._component_settings(config, normalized_content)
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
        template = self._build_template(config, content)
        versions = self._version_records()
        version = len(versions) + 1
        template_id = self._selected_template_id()
        legacy_universal = template_id == UNIVERSAL_AD_TEMPLATE_ID
        record = {
            "schema": UNIVERSAL_AD_VERSION_SCHEMA if legacy_universal else _TEMPLATE_VERSION_SCHEMA,
            "template_id": template_id,
            "version": version,
            "state_sha256": state_sha256,
            "template_sha256": template.digest,
            "render_sha256": preview["bytes_sha256"],
            "change_note": self._change_note(change_note),
            "configuration": config,
            "content": content,
            "component_settings": self._component_settings(config, content),
            "assets": self._snapshot()["assets"],
            "primitive_template": template.document,
        }
        stem = f"{template_id}_v{version}"
        if not legacy_universal:
            record["render_filename"] = f"{stem}.png"
        raw, digest = _canonical(record)
        record = {**json.loads(raw), "version_sha256": digest}
        json_path = self.versions / f"{stem}.json"
        png_path = self.versions / f"{stem}.png"
        if json_path.exists() or png_path.exists():
            raise FileExistsError("Studio template version already exists")
        self._atomic_bytes(png_path, preview["bytes"])
        self._atomic_json(json_path, record)
        return self.detail()

    def version_detail(self, version: int) -> dict[str, Any]:
        if isinstance(version, bool) or version < 1:
            raise KeyError(f"Studio version not found: {version}")
        records = self._version_records()
        if version > len(records):
            raise KeyError(f"Studio version not found: {version}")
        return json.loads(json.dumps(records[version - 1], ensure_ascii=False))

    def version_render(self, version: int) -> dict[str, Any]:
        if isinstance(version, bool) or version < 1:
            raise KeyError(f"Studio version not found: {version}")
        records = self._version_records()
        if version > len(records):
            raise KeyError(f"Studio version not found: {version}")
        record = records[version - 1]
        try:
            filename = record.get("render_filename") or f"{record['template_id']}_v{version}.png"
            data = (self.versions / str(filename)).read_bytes()
        except OSError as error:
            raise ValueError(f"Studio version render is unavailable: {version}") from error
        digest = hashlib.sha256(data).hexdigest()
        if digest != record["render_sha256"]:
            raise ValueError(f"Studio template render digest mismatch: {version}")
        return {"bytes": data, "mime_type": "image/png", "sha256": digest}
