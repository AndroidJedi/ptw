"""Local authority for one registered Post Studio template workspace."""

from __future__ import annotations

from .image_reference import generate_image

import base64
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .natal_brand import (
    NATAL_LOGO_PATH, natal_logo_bytes, natal_logo_colored_bytes,
    normalize_natal_logo_colors,
)
from .image_generation_policy import IMAGE_POLICY_VERSION, compile_image_prompt, image_provenance
from .openai_images import phone_screen_art_prompt
from .studio_phone_metrics import (
    PHONE_METRICS_TEMPLATE_ID,
    compose_phone_device_asset, iphone_frame_record, normalize_phone_metrics_config,
    normalize_phone_metrics_content,
)
from .studio import MAX_IMAGE_BYTES, StudioRenderer, inspect_media
from .studio_textures import texture_asset
from .post_templates import POST_TEMPLATE_REGISTRY


_BUNDLED_ASSETS = {
    "logo": {
        "path": NATAL_LOGO_PATH,
        "origin": "canonical_natal_brand_asset",
    },
}
_WORKSPACE_SCHEMA = "ptw.studio.workspace.v8"
_TEMPLATE_SELECTION_SCHEMA = "ptw.studio.template-selection.v1"
_TEMPLATE_VERSION_SCHEMA = "ptw.studio.template-version.v1"
_AGENT_CONTEXT_SCHEMA = "ptw.studio.agent-context.v3"
_PHONE_SCREEN_HISTORY_SCHEMA = "ptw.studio.phone-screen-history.v1"
_PHONE_SCREEN_HISTORY_LIMIT = 3
_TEMPLATE_SUMMARIES = tuple(
    definition.summary() for definition in POST_TEMPLATE_REGISTRY.all()
)


def _canonical(value: Any) -> tuple[str, str]:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


class PostStudioWorkspace:
    """Persist one selected bounded Post template and immutable outputs."""

    def __init__(
        self, root: Path | str, *, renderer: StudioRenderer | None = None,
        image_provider: Any | None = None,
        template_registry=None,
    ) -> None:
        self.root = Path(root)
        self.renderer = renderer or StudioRenderer()
        self.image_provider = image_provider
        self.template_registry = template_registry or (lambda: POST_TEMPLATE_REGISTRY)
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
            return PHONE_METRICS_TEMPLATE_ID
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio template selection is unreadable") from error
        if not isinstance(value, Mapping) or set(value) not in ({"schema", "template_id"}, {"schema", "template_id", "template_version", "template_sha256"}):
            raise ValueError("Studio template selection fields are invalid")
        if value["schema"] != _TEMPLATE_SELECTION_SCHEMA:
            raise ValueError("Studio template selection is invalid")
        return self._selection_definition(value).identity.template_id

    def _selection_definition(self, value):
        registry = POST_TEMPLATE_REGISTRY if value.get("template_id") == PHONE_METRICS_TEMPLATE_ID else self.template_registry()
        if "template_version" in value:
            return registry.resolve_reference({k: value[k] for k in ("template_id", "template_version", "template_sha256")})
        return registry.get(str(value["template_id"]))

    def _asset_slots(self) -> Mapping[str, Mapping[str, Any]]:
        return self._definition().asset_slots()

    def _definition(self):
        path = self.root / "template.json"
        return self._selection_definition(json.loads(path.read_text())) if path.is_file() else POST_TEMPLATE_REGISTRY.get(PHONE_METRICS_TEMPLATE_ID)

    def _normalize_configuration(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return self._definition().normalize_configuration(value)

    def _normalize_content(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return self._definition().normalize_content(value)

    def _build_template(self, config: Mapping[str, Any], content: Mapping[str, Any]):
        definition = self._definition()
        if definition.editor_key == "post.declarative.react":
            return definition.build_template(config, content, variant_seed=self.root.name)
        return definition.build_template(config, content)

    def _catalog(self) -> dict[str, Any]:
        return self._definition().catalog()

    def _component_settings(self, config: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
        return self._definition().component_settings(config, content)

    def _configuration(self) -> dict[str, Any]:
        path = self.root / "configuration.json"
        if not path.is_file():
            return self._definition().default_configuration()
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio configuration is unreadable") from error
        return self._normalize_configuration(value)

    def _content(self) -> dict[str, Any]:
        path = self.root / "content.json"
        if not path.is_file():
            return self._definition().default_content()
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio content is unreadable") from error
        return self._normalize_content(value)

    def _asset_record(self, slot: str) -> dict[str, Any] | None:
        # Natal is fixed and cannot be replaced by creative asset input.
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

    def _phone_screen_history_records(self) -> list[dict[str, Any]]:
        """Return the newest three raw phone heroes, including current art."""

        current = self._asset_record("phone_screen")
        path = self.assets / "phone_screen_history.json"
        if not path.is_file():
            return [] if current is None else [current]
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("Studio phone-screen history is unreadable") from error
        if (
            not isinstance(value, Mapping)
            or set(value) != {"schema", "items"}
            or value.get("schema") != _PHONE_SCREEN_HISTORY_SCHEMA
            or not isinstance(value.get("items"), list)
            or not 1 <= len(value["items"]) <= _PHONE_SCREEN_HISTORY_LIMIT
        ):
            raise ValueError("Studio phone-screen history is invalid")
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        fields = {
            "filename", "mime_type", "sha256", "width", "height",
            "byte_count", "source",
        }
        for item in value["items"]:
            if not isinstance(item, Mapping) or set(item) != fields:
                raise ValueError("Studio phone-screen history item is invalid")
            digest = item.get("sha256")
            filename = item.get("filename")
            if (
                not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or digest in seen
                or filename != f"phone_screen_history_{digest}.png"
                or item.get("mime_type") != "image/png"
                or not isinstance(item.get("source"), Mapping)
            ):
                raise ValueError("Studio phone-screen history item is invalid")
            try:
                data = (self.assets / filename).read_bytes()
            except OSError as error:
                raise ValueError("Studio phone-screen history image is unavailable") from error
            inspected = inspect_media(data, "image/png")
            if (
                hashlib.sha256(data).hexdigest() != digest
                or item.get("byte_count") != len(data)
                or item.get("width") != inspected["width"]
                or item.get("height") != inspected["height"]
            ):
                raise ValueError("Studio phone-screen history digest is invalid")
            seen.add(digest)
            records.append({**item, "bytes": data})
        if current is not None and current["sha256"] not in seen:
            raise ValueError("Current Studio phone-screen image is absent from its history")
        return records

    def _phone_screen_history_summaries(self) -> list[dict[str, Any]]:
        current = self._asset_record("phone_screen")
        selected_sha256 = None if current is None else current["sha256"]
        return [{
            "mime_type": record["mime_type"],
            "sha256": record["sha256"],
            "width": record["width"],
            "height": record["height"],
            "byte_count": record["byte_count"],
            "source": json.loads(json.dumps(record["source"])),
            "selected": record["sha256"] == selected_sha256,
        } for record in self._phone_screen_history_records()]

    def _write_phone_screen_history(self, records: list[Mapping[str, Any]]) -> None:
        kept = records[:_PHONE_SCREEN_HISTORY_LIMIT]
        items = []
        retained_filenames = set()
        for record in kept:
            digest = str(record["sha256"])
            filename = f"phone_screen_history_{digest}.png"
            retained_filenames.add(filename)
            self._atomic_bytes(self.assets / filename, bytes(record["bytes"]))
            items.append({
                "filename": filename,
                "mime_type": "image/png",
                "sha256": digest,
                "width": int(record["width"]),
                "height": int(record["height"]),
                "byte_count": int(record["byte_count"]),
                "source": json.loads(json.dumps(record["source"])),
            })
        for path in self.assets.glob("phone_screen_history_*.png"):
            if path.name not in retained_filenames:
                path.unlink()
        self._atomic_json(self.assets / "phone_screen_history.json", {
            "schema": _PHONE_SCREEN_HISTORY_SCHEMA,
            "items": items,
        })

    def _asset_records(self, config: Mapping[str, Any], content: Mapping[str, Any] | None = None) -> dict[str, Mapping[str, Any]]:
        normalized_content = self._content() if content is None else self._normalize_content(content)
        screen = self._asset_record("phone_screen")
        definition = self._definition()
        if definition.editor_key == "post.declarative.react":
            from .template_components import fixed_component_assets
            records = fixed_component_assets(definition.document)
            for component in definition.document["components"]:
                if component["type"] == "brand":
                    records[component["id"]] = {"bytes": natal_logo_colored_bytes(config["logo"]["symbol_color"], config["logo"]["name_color"]), "mime_type": "image/png"}
                elif component["type"] == "phone":
                    records[component["id"]] = compose_phone_device_asset(
                        None if screen is None else screen["bytes"], normalized_content["phone_hero_title"],
                        normalized_content["cta"], "none", normalized_content["phone_buttons"],
                        logo_symbol_color=config["logo"]["symbol_color"], logo_name_color=config["logo"]["name_color"])
                elif component["type"] in {"image", "cutout_image"} and screen:
                    if component["type"] == "cutout_image":
                        from .template_cutout import cutout_png
                        records[component["id"]] = {"bytes": cutout_png(screen["bytes"]), "mime_type": "image/png"}
                    else:
                        records[component["id"]] = {"bytes": screen["bytes"], "mime_type": screen["mime_type"]}
            return records
        device = compose_phone_device_asset(
            None if screen is None else screen["bytes"],
            normalized_content["phone_hero_title"]
            if config["phone_screen"]["title_enabled"] else "",
            normalized_content["cta"],
            str(config["phone_screen"]["texture"]),
            [
                text for text, appearance in zip(
                    normalized_content["phone_buttons"], config["phone_buttons"],
                    strict=True,
                ) if appearance["enabled"]
            ],
            [appearance for appearance in config["phone_buttons"] if appearance["enabled"]],
            config["typography"],
            bool(config["phone_screen"]["logo_enabled"]),
            visual_mode=str(config.get("visual_mode", "phone")),
            logo_symbol_color=str(config["logo"]["symbol_color"]),
            logo_name_color=str(config["logo"]["name_color"]),
        )
        records: dict[str, Mapping[str, Any]] = {
            "phone_device": {
                "bytes": device["bytes"], "mime_type": device["mime_type"],
            },
        }
        if config["logo"]["enabled"]:
            logo = self._asset_record("logo")
            if logo is None:
                raise RuntimeError("Canonical Natal logo is unavailable")
            records["logo"] = {
                "bytes": natal_logo_colored_bytes(
                    str(config["logo"]["symbol_color"]),
                    str(config["logo"]["name_color"]),
                ),
                "mime_type": logo["mime_type"],
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

    def _asset_summaries(self) -> list[dict[str, Any]]:
        summaries = []
        for slot, declaration in self._asset_slots().items():
            record = self._asset_record(slot)
            summaries.append({
                "slot": slot, "role": declaration["role"],
                "description": declaration["description"],
                "allowed_mime_types": list(declaration["allowed_mime_types"]),
                "editable": False, "available": record is not None,
                "mime_type": None if record is None else record["mime_type"],
                "sha256": None if record is None else record["sha256"],
                "byte_count": None if record is None else record["byte_count"],
                "source": None if record is None else record["source"],
            })
        for slot, role, description in (
            ("iphone_frame", "device_frame", "Fixed checked-in black iPhone frame."),
            ("logo", "brand", "Fixed canonical Natal logo and name."),
        ):
            record = self._asset_record(slot)
            if record is None:  # pragma: no cover - both are checked-in assets
                raise RuntimeError(f"Fixed Studio asset is unavailable: {slot}")
            summaries.append({
                "slot": slot, "role": role, "description": description,
                "allowed_mime_types": ["image/png"], "editable": False,
                "available": True, "mime_type": record["mime_type"],
                "sha256": record["sha256"], "byte_count": record["byte_count"],
                "source": record["source"],
            })
        return summaries

    def _snapshot(self) -> dict[str, Any]:
        return {
            **({"template_reference": self._definition().identity.to_reference()} if self._definition().editor_key == "post.declarative.react" else {}),
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

    def _legacy_configuration_state_sha256(
        self, *, template_id: str, schemas: set[str],
    ) -> str | None:
        """Reproduce an untouched stored digest during a one-save config uplift."""

        if self._selected_template_id() != template_id:
            return None
        path = self.root / "configuration.json"
        if not path.is_file():
            return None
        try:
            raw_config = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        if (
            not isinstance(raw_config, Mapping)
            or raw_config.get("schema") not in schemas
        ):
            return None
        snapshot = self._snapshot()
        snapshot["configuration"] = raw_config
        return _canonical(snapshot)[1]

    def _legacy_phone_state_sha256(self) -> str | None:
        return self._legacy_configuration_state_sha256(
            template_id=PHONE_METRICS_TEMPLATE_ID,
            schemas={
                "ptw.studio.phone-metrics-config.v8",
                "ptw.studio.phone-metrics-config.v9",
                "ptw.studio.phone-metrics-config.v10",
                "ptw.studio.phone-metrics-config.v11",
                "ptw.studio.phone-metrics-config.v12",
            },
        )

    def _assert_state(self, base_sha256: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", str(base_sha256)):
            raise RuntimeError("Studio state changed; reload before saving")
        current_sha256 = self.state_sha256()
        if current_sha256 == base_sha256:
            return
        if base_sha256 == self._legacy_phone_state_sha256():
            return
        raise RuntimeError("Studio state changed; reload before saving")

    def _version_records(self) -> list[dict[str, Any]]:
        versions: list[dict[str, Any]] = []
        for path in sorted(self.versions.glob("*_v*.json")):
            try:
                value = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError(f"Studio version is invalid: {path.name}") from error
            if value.get("schema") != _TEMPLATE_VERSION_SCHEMA:
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
        value = {
            "schema": _WORKSPACE_SCHEMA,
            "template_id": self._selected_template_id(),
            "template_reference": self._definition().identity.to_reference(),
            "template_name": self._definition().name,
            "editor_key": self._definition().editor_key,
            "templates": [json.loads(json.dumps(item)) for item in _TEMPLATE_SUMMARIES],
            "catalog": self._catalog(),
            "state_sha256": self.state_sha256(),
            "template_sha256": template.digest,
            "configuration": config,
            "content": content,
            "component_settings": self._component_settings(config, content),
            "assets": self._asset_summaries(),
            "phone_screen_generation_available": self.image_provider is not None,
            "versions": [{
                "version": item["version"],
                "state_sha256": item["state_sha256"],
                "template_sha256": item["template_sha256"],
                "render_sha256": item["render_sha256"],
                "change_note": item["change_note"],
            } for item in versions],
        }
        value["phone_screen_history"] = self._phone_screen_history_summaries()
        if self._definition().editor_key == "post.declarative.react":
            from .post_template_runtime import text_fields
            value["template_fields"] = text_fields(self._definition().document)
        return value

    def switch_template(self, *, base_sha256, template_reference, request_id, configuration, content):
        """Preserve Post content, assets and approved history; pin an accepted layout."""
        from uuid import UUID
        from .post_template_runtime import bind_content, text_fields
        request_id = str(UUID(str(request_id)))
        if not isinstance(template_reference, Mapping) or set(template_reference) != {"surface", "template_id", "template_version", "template_sha256"} or template_reference["surface"] != "post":
            raise ValueError("Select an exact Post template version")
        reference = {k: v for k, v in template_reference.items() if k != "surface"}
        target = self.template_registry().resolve_reference(reference)
        request_digest = _canonical([base_sha256, template_reference, configuration, content])[1]
        receipts_path = self.root / "template-switches.json"
        receipts = json.loads(receipts_path.read_text()) if receipts_path.exists() else {}
        if request_id in receipts:
            if receipts[request_id] != request_digest:
                raise RuntimeError("Template switch request ID was reused with different input")
            return self.detail()
        self._assert_state(base_sha256)
        config, source = self._normalize_configuration(configuration), self._normalize_content(content)
        current = self._definition()
        drafts_path = self.root / "template-drafts.json"
        drafts = json.loads(drafts_path.read_text()) if drafts_path.exists() else {}
        current_key = _canonical(current.identity.to_reference())[1]
        target_key = _canonical(target.identity.to_reference())[1]
        drafts[current_key] = {"configuration": config, "content": source}
        if current_key == target_key:
            next_content = source
        elif target.editor_key == "post.declarative.react":
            next_content = bind_content(target.document, source,
                text_fields(current.document) if current.editor_key == "post.declarative.react" else ())
        else:
            next_content = {k: v for k, v in source.items() if k != "template_text"}
            if current.editor_key == "post.declarative.react":
                role_fields = {"headline": "hero_title", "description": "supporting_text", "cta": "cta", "meta": "offer"}
                seen = set()
                for field in text_fields(current.document):
                    role = field["role"]
                    if role in role_fields and role not in seen:
                        next_content[role_fields[role]] = source["template_text"][field["id"]]
                        seen.add(role)
            # Keep authored text available on return; restore the built-in's controls.
            config = drafts.get(target_key, {}).get("configuration", config)
        next_content = target.normalize_content(next_content)
        config = target.normalize_configuration(config)
        updates = {"template.json": {"schema": _TEMPLATE_SELECTION_SCHEMA, **reference},
            "configuration.json": config, "content.json": next_content,
            "template-drafts.json": drafts, "template-switches.json": {**receipts, request_id: request_digest}}
        old = {name: (self.root / name).read_bytes() if (self.root / name).exists() else None for name in updates}
        try:
            for name, value in updates.items():
                self._atomic_json(self.root / name, value)
            result = self.detail()
            # Validate rendering before committing the replacement to the caller.
            self.render_preview(state_sha256=result["state_sha256"])
            return result
        except Exception:
            for name, data in old.items():
                if data is None:
                    (self.root / name).unlink(missing_ok=True)
                else:
                    self._atomic_bytes(self.root / name, data)
            raise

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
        """Capture the saved—not draft—Post Studio state."""

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

    def save_configuration(
        self, *, base_sha256: str, configuration: Mapping[str, Any], content: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._assert_state(base_sha256)
        normalized_config = self._normalize_configuration(configuration)
        normalized_content = self._normalize_content(content)
        self._atomic_json(self.root / "configuration.json", normalized_config)
        self._atomic_json(self.root / "content.json", normalized_content)
        return self.detail()

    def restore_approved_clone(
        self, *, base_sha256: str, configuration: Mapping[str, Any],
        content: Mapping[str, Any], assets: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Restore one approved snapshot as a new mutable draft without versions."""

        self._assert_state(base_sha256)
        normalized_config = self._normalize_configuration(configuration)
        normalized_content = self._normalize_content(content)
        allowed = {"phone_screen"}
        seen: set[str] = set()
        copied_phone: dict[str, Any] | None = None
        for item in assets:
            if not isinstance(item, Mapping) or set(item) != {"slot", "mime_type", "bytes_base64", "source"}:
                raise ValueError("Studio clone asset fields are invalid")
            slot = str(item["slot"])
            if slot not in allowed or slot in seen or not isinstance(item["source"], Mapping):
                raise ValueError("Studio clone asset is outside the selected template")
            try:
                data = base64.b64decode(str(item["bytes_base64"]), validate=True)
            except (TypeError, ValueError) as error:
                raise ValueError("Studio clone asset bytes are not valid base64") from error
            self._store_asset(
                slot, mime_type=str(item["mime_type"]), data=data,
                source=dict(item["source"]),
            )
            seen.add(slot)
            if slot == "phone_screen":
                copied_phone = self._asset_record(slot)
        if copied_phone is not None:
            self._write_phone_screen_history([copied_phone])
        self._atomic_json(self.root / "configuration.json", normalized_config)
        self._atomic_json(self.root / "content.json", normalized_content)
        return self.detail()

    def apply_template(
        self, *, base_sha256: str, template_id: str,
        logo_colors: Mapping[str, Any] | None = None,
        template_reference=None,
    ) -> dict[str, Any]:
        """Replace the entire mutable Studio draft with one preset template."""

        self._assert_state(base_sha256)
        definition = self.template_registry().resolve_reference({k: v for k, v in template_reference.items() if k != "surface"}) if template_reference else self.template_registry().get(template_id)
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
            **({k: v for k, v in definition.identity.to_reference().items() if k != "surface"} if template_reference or definition.editor_key == "post.declarative.react" else {}),
        })
        if logo_colors is not None:
            colors = normalize_natal_logo_colors(dict(logo_colors))
            config = definition.default_configuration()
            config["logo"].update(colors)
            self._atomic_json(
                self.root / "configuration.json",
                definition.normalize_configuration(config),
            )
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
        self, slot: str, *, base_sha256: str, mime_type: str,
        bytes_base64: str,
    ) -> dict[str, Any]:
        """Reject direct uploads while preserving the explicit API boundary.

        Phone artwork is accepted only through the validated generation path;
        fixed identity assets are never owner-replaceable.
        """

        self._assert_state(base_sha256)
        if slot in {"logo", "iphone_frame"}:
            raise ValueError(f"Studio {slot} is fixed Studio identity")
        if slot == "phone_screen":
            raise ValueError("Studio phone_screen cannot be uploaded")
        raise KeyError(f"Studio asset slot not found: {slot}")

    def store_generated_phone_screen(
        self, *, base_sha256: str, data: bytes, source: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist only validated server-generated artwork for the phone aperture."""

        self._assert_state(base_sha256)
        if source.get("origin") not in {
            "codex_builtin_image_generation", "openai_image_api",
            "result_bridge_image_generation",
        } or (source.get("text_in_screen") != "prohibited_by_prompt"
              and source.get("generation_policy_version") != IMAGE_POLICY_VERSION):
            raise ValueError("phone-screen artwork must carry versioned generation provenance")
        previous = self._phone_screen_history_records()
        self._store_asset(
            "phone_screen", mime_type="image/png", data=data,
            source=source,
        )
        current = self._asset_record("phone_screen")
        if current is None:  # pragma: no cover - the write above is authoritative
            raise RuntimeError("Generated phone-screen artwork was not stored")
        history = [current, *(
            record for record in previous if record["sha256"] != current["sha256"]
        )]
        self._write_phone_screen_history(history)
        return self.detail()

    def select_phone_screen(self, *, base_sha256: str, sha256: str) -> dict[str, Any]:
        """Make one retained raw hero the current render and enhancement source."""

        self._assert_state(base_sha256)
        if not re.fullmatch(r"[0-9a-f]{64}", str(sha256)):
            raise ValueError("Studio phone-screen history digest is invalid")
        records = self._phone_screen_history_records()
        selected = next((item for item in records if item["sha256"] == sha256), None)
        if selected is None:
            raise KeyError("Studio phone-screen history image not found")
        current = self._asset_record("phone_screen")
        if current is not None and current["sha256"] == sha256:
            return self.detail()
        self._store_asset(
            "phone_screen", mime_type="image/png", data=bytes(selected["bytes"]),
            source=selected["source"],
        )
        return self.detail()

    def phone_screen_history_image(self, sha256: str) -> dict[str, Any]:
        """Read one retained raw hero by its verified content digest."""

        if not re.fullmatch(r"[0-9a-f]{64}", str(sha256)):
            raise KeyError("Studio phone-screen history image not found")
        selected = next(
            (item for item in self._phone_screen_history_records() if item["sha256"] == sha256),
            None,
        )
        if selected is None:
            raise KeyError("Studio phone-screen history image not found")
        return {
            "bytes": bytes(selected["bytes"]), "mime_type": "image/png",
            "sha256": selected["sha256"],
        }

    def generate_phone_screen(
        self, *, base_sha256: str, visual_direction: str,
        enhance_current: bool = False, skill_context: str = "",
        reference_image: bytes | None = None,
        creative_direction: Mapping[str, Any] | None = None,
        image_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate or reference-edit one mutable, text-free phone hero artwork."""

        self._assert_state(base_sha256)
        if self.image_provider is None:
            raise RuntimeError("Phone-screen image generation is unavailable in this Studio runtime")
        if not isinstance(enhance_current, bool):
            raise ValueError("enhance current phone-screen setting must be boolean")
        if reference_image is not None and enhance_current:
            raise ValueError("Choose only one image reference")
        current_screen = self._asset_record("phone_screen")
        if enhance_current and current_screen is None:
            raise ValueError(
                "Enhance current image requires an existing generated phone visual"
            )
        normalized_direction = " ".join(str(visual_direction or "").split())
        if not 8 <= len(normalized_direction) <= 600:
            raise ValueError("phone-screen visual direction must contain 8-600 characters")
        prompt = compile_image_prompt(image_context) if image_context is not None else phone_screen_art_prompt(
            normalized_direction, enhance_current=enhance_current,
            skill_context=skill_context, creative_direction=creative_direction,
        )
        try:
            reference = bytes(current_screen["bytes"]) if enhance_current and current_screen else reference_image
            generated = generate_image(
                self.image_provider, prompt, reference_image=reference,
                uploaded_reference=reference_image is not None,
                output_spec=image_context.get("output_spec") if image_context is not None else None,
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
        if image_context is not None:
            source.update(image_provenance(image_context))
        source.update({
            "visual_direction": normalized_direction,
            "visual_direction_sha256": hashlib.sha256(
                normalized_direction.encode()
            ).hexdigest(),
            "generation_mode": (
                "uploaded_reference" if reference_image is not None else
                "enhance_current" if enhance_current else "generate_new"
            ),
            **({"creative_direction": dict(creative_direction)}
               if creative_direction is not None else {}),
            "prompt_contract": IMAGE_POLICY_VERSION,
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
        rendered = self.renderer.render_preview(
            template,
            semantic_data=self._definition().semantic_data(config, normalized_content),
            assets=assets,
        )
        rendered["resolved"]["component_settings"] = self._component_settings(config, normalized_content)
        if self._definition().editor_key == "post.declarative.react":
            from .template_previews import geometry
            _observations, failures = geometry(rendered)
            if failures:
                raise ValueError("Post text does not fit this template. Shorten the text or choose another template.")
        return rendered

    @staticmethod
    def _change_note(value: Any) -> str:
        normalized = " ".join(str(value).split())
        if not 1 <= len(normalized) <= 500:
            raise ValueError("Studio version change note must contain 1 to 500 characters")
        return normalized

    def approve_version(self, *, state_sha256: str, change_note: str, metric_provenance: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        self._assert_state(state_sha256)
        preview = self.render_preview(state_sha256=state_sha256)
        config, content = self._configuration(), self._content()
        template = self._build_template(config, content)
        versions = self._version_records()
        version = len(versions) + 1
        template_id = self._selected_template_id()
        stem = f"{template_id}_v{version}"
        raw_slots = ("phone_screen",)
        clone_assets: list[dict[str, Any]] = []
        clone_asset_bytes: list[tuple[str, bytes]] = []
        for slot in raw_slots:
            selected = self._asset_record(slot)
            if selected is None:
                continue
            extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[
                selected["mime_type"]
            ]
            filename = f"{stem}.asset.{slot}.{extension}"
            clone_assets.append({
                "slot": slot, "filename": filename,
                "mime_type": selected["mime_type"], "sha256": selected["sha256"],
                "source": json.loads(json.dumps(selected["source"])),
            })
            clone_asset_bytes.append((filename, bytes(selected["bytes"])))
        record = {
            **({"metric_provenance": metric_provenance} if metric_provenance is not None else {}),
            "schema": _TEMPLATE_VERSION_SCHEMA,
            "template_id": template_id,
            "template_reference": self._definition().identity.to_reference(),
            "version": version,
            "state_sha256": state_sha256,
            "template_sha256": template.digest,
            "render_sha256": preview["bytes_sha256"],
            "change_note": self._change_note(change_note),
            "configuration": config,
            "content": content,
            "component_settings": self._component_settings(config, content),
            "assets": self._snapshot()["assets"],
            "clone_assets": clone_assets,
            "primitive_template": template.document,
        }
        record["render_filename"] = f"{stem}.png"
        raw, digest = _canonical(record)
        record = {**json.loads(raw), "version_sha256": digest}
        json_path = self.versions / f"{stem}.json"
        png_path = self.versions / f"{stem}.png"
        asset_paths = [self.versions / filename for filename, _data in clone_asset_bytes]
        if json_path.exists() or png_path.exists() or any(path.exists() for path in asset_paths):
            raise FileExistsError("Studio template version already exists")
        try:
            self._atomic_bytes(png_path, preview["bytes"])
            for path, (_filename, data) in zip(asset_paths, clone_asset_bytes, strict=True):
                self._atomic_bytes(path, data)
            self._atomic_json(json_path, record)
        except Exception:
            json_path.unlink(missing_ok=True)
            png_path.unlink(missing_ok=True)
            for path in asset_paths:
                path.unlink(missing_ok=True)
            raise
        return self.detail()

    def approve_configuration(
        self, *, base_sha256: str, configuration: Mapping[str, Any],
        content: Mapping[str, Any], change_note: str,
        metric_provenance: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Save pending fields and one version as a single workspace mutation."""

        self._assert_state(base_sha256)
        configuration_path = self.root / "configuration.json"
        content_path = self.root / "content.json"
        previous_configuration = configuration_path.read_bytes() if configuration_path.is_file() else None
        previous_content = content_path.read_bytes() if content_path.is_file() else None
        template_id = self._selected_template_id()
        next_version = len(self._version_records()) + 1
        version_stem = f"{template_id}_v{next_version}"
        try:
            saved = self.save_configuration(
                base_sha256=base_sha256, configuration=configuration, content=content,
            )
            return self.approve_version(
                state_sha256=saved["state_sha256"], change_note=change_note, metric_provenance=metric_provenance,
            )
        except Exception:
            for path, previous in (
                (configuration_path, previous_configuration),
                (content_path, previous_content),
            ):
                if previous is None:
                    path.unlink(missing_ok=True)
                else:
                    self._atomic_bytes(path, previous)
            (self.versions / f"{version_stem}.json").unlink(missing_ok=True)
            (self.versions / f"{version_stem}.png").unlink(missing_ok=True)
            for path in self.versions.glob(f"{version_stem}.asset.*"):
                path.unlink()
            raise

    def version_detail(self, version: int) -> dict[str, Any]:
        if isinstance(version, bool) or version < 1:
            raise KeyError(f"Studio version not found: {version}")
        records = self._version_records()
        if version > len(records):
            raise KeyError(f"Studio version not found: {version}")
        return json.loads(json.dumps(records[version - 1], ensure_ascii=False))

    def version_clone_assets(self, version: int) -> list[dict[str, Any]]:
        """Read digest-verified raw assets frozen with one approved version."""

        record = self.version_detail(version)
        frozen = record.get("clone_assets")
        results: list[dict[str, Any]] = []
        if isinstance(frozen, list):
            for item in frozen:
                if not isinstance(item, Mapping) or set(item) != {
                    "slot", "filename", "mime_type", "sha256", "source",
                }:
                    raise ValueError("Studio version clone asset metadata is invalid")
                filename = str(item["filename"])
                if Path(filename).name != filename:
                    raise ValueError("Studio version clone asset filename is invalid")
                try:
                    data = (self.versions / filename).read_bytes()
                except OSError as error:
                    raise ValueError("Studio version clone asset is unavailable") from error
                if hashlib.sha256(data).hexdigest() != item["sha256"]:
                    raise ValueError("Studio version clone asset digest mismatch")
                results.append({**json.loads(json.dumps(item)), "bytes": data})
            return results

        # Legacy approved versions did not persist raw asset files. They can be
        # cloned only while the mutable source still contains the identical
        # digest recorded at approval; never substitute a newer asset.
        allowed = {"phone_screen"}
        for summary in record.get("assets") or []:
            if summary.get("slot") not in allowed or not summary.get("available"):
                continue
            selected = self._asset_record(str(summary["slot"]))
            if selected is None or selected["sha256"] != summary.get("sha256"):
                raise RuntimeError(
                    "This legacy approved Post no longer has its exact raw asset; "
                    "choose another approved version"
                )
            results.append({
                "slot": summary["slot"], "mime_type": selected["mime_type"],
                "sha256": selected["sha256"], "source": selected["source"],
                "bytes": bytes(selected["bytes"]),
            })
        return results

    def version_render(self, version: int) -> dict[str, Any]:
        if isinstance(version, bool) or version < 1:
            raise KeyError(f"Studio version not found: {version}")
        records = self._version_records()
        if version > len(records):
            raise KeyError(f"Studio version not found: {version}")
        record = records[version - 1]
        try:
            filename = record["render_filename"]
            data = (self.versions / str(filename)).read_bytes()
        except OSError as error:
            raise ValueError(f"Studio version render is unavailable: {version}") from error
        digest = hashlib.sha256(data).hexdigest()
        if digest != record["render_sha256"]:
            raise ValueError(f"Studio template render digest mismatch: {version}")
        return {"bytes": data, "mime_type": "image/png", "sha256": digest}
