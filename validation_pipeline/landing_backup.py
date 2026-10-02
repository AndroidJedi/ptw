"""Self-contained, digest-checked private Landing backups and draft restores."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from .landing_workspace import LandingWorkspace, sha256_json


BACKUP_SCHEMA = "ptw.landing.backup.v1"
MAX_BACKUP_BYTES = 32 * 1024 * 1024
_SAFE_PATH = re.compile(r"(?:[a-zA-Z0-9_.-]+/)*[a-zA-Z0-9_.-]+")


def _workspace(value: Any) -> LandingWorkspace:
    return value.workspace if hasattr(value, "workspace") else value


def _files(root: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Landing backup contains a symbolic link")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if not _SAFE_PATH.fullmatch(relative) or ".." in Path(relative).parts:
            raise ValueError("Landing backup contains an unsafe file path")
        raw = path.read_bytes()
        total += len(raw)
        if total > MAX_BACKUP_BYTES:
            raise ValueError("Landing backup exceeds 32 MiB")
        result[relative] = {"sha256": hashlib.sha256(raw).hexdigest(),
                            "bytes_base64": base64.b64encode(raw).decode("ascii")}
    return result


def export_backup(service: Any, project_id: str, landing_id: str, publications: Any | None = None) -> dict[str, Any]:
    page = service.authority.get_page(landing_id)
    if page["project_id"] != project_id:
        raise ValueError("Landing backup belongs to another Project")
    wrapped = service._workspace(landing_id)
    detail = wrapped.detail()  # Hydrate database-backed files before reading the cache root.
    workspace = _workspace(wrapped)
    publication = publications.get(project_id) if publications is not None else None
    events = [item for item in (publication or {}).get("events", []) if item.get("landing_id") == landing_id]
    result = {
        "schema": BACKUP_SCHEMA,
        "project_id": project_id,
        "landing_id": landing_id,
        "source_creative_id": page["source_creative_id"],
        "source_version": page["source_version"],
        "source_version_sha256": page["source_version_sha256"],
        "template_reference": detail.get("template_reference"),
        "status": page["status"],
        "state_sha256": detail["state_sha256"],
        "configuration": detail["configuration"],
        "content": detail["content"],
        "assets": detail["assets"],
        "approved_versions": [workspace.version_detail(item["version"]) for item in detail["versions"]],
        "publication": None if not events else {
            "slug": publication["slug"], "status": publication["status"],
            "current_event_id": publication["current_event_id"], "events": events,
        },
        "files": _files(workspace.root),
    }
    result["backup_sha256"] = sha256_json(result)
    return result


def validate_backup(value: Mapping[str, Any], *, project_id: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    required = {"schema", "project_id", "landing_id", "source_creative_id", "source_version",
                "source_version_sha256", "template_reference", "status", "state_sha256",
                "configuration", "content", "assets", "approved_versions", "publication", "files", "backup_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema") != BACKUP_SCHEMA:
        raise ValueError("Landing backup format is invalid")
    if value["project_id"] != project_id:
        raise ValueError("Landing backup belongs to another Project")
    if sha256_json({key: item for key, item in value.items() if key != "backup_sha256"}) != value["backup_sha256"]:
        raise ValueError("Landing backup digest mismatch")
    encoded = value["files"]
    if not isinstance(encoded, Mapping) or len(encoded) > 300:
        raise ValueError("Landing backup files are invalid")
    files: dict[str, bytes] = {}
    total = 0
    for relative, item in encoded.items():
        if not isinstance(relative, str) or not _SAFE_PATH.fullmatch(relative) or ".." in Path(relative).parts:
            raise ValueError("Landing backup file path is invalid")
        if not isinstance(item, Mapping) or set(item) != {"sha256", "bytes_base64"}:
            raise ValueError("Landing backup file record is invalid")
        try:
            raw = base64.b64decode(item["bytes_base64"], validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("Landing backup file encoding is invalid") from error
        total += len(raw)
        if total > MAX_BACKUP_BYTES or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Landing backup file digest or size is invalid")
        files[relative] = raw
    with TemporaryDirectory(prefix="ptw-landing-backup-") as temporary:
        root = Path(temporary)
        for relative, raw in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        workspace = LandingWorkspace(root)
        workspace.template_reference = value["template_reference"]
        detail = workspace.detail()
        if (detail["state_sha256"] != value["state_sha256"]
                or detail["configuration"] != value["configuration"]
                or detail["content"] != value["content"]
                or detail["assets"] != value["assets"]):
            raise ValueError("Landing backup state does not match its files")
        versions = [workspace.version_detail(item["version"]) for item in detail["versions"]]
        if versions != value["approved_versions"]:
            raise ValueError("Landing backup approved versions do not match its files")
        from .landing_delivery import variant_path
        def verify_assets(assets: Any) -> None:
            for asset in assets:
                if asset["slot"] not in workspace.visual_slots:
                    raise ValueError("Landing backup image slot is invalid")
                for entry in asset.get("history", []):
                    digest = entry["sha256"]
                    if hashlib.sha256(files.get(f"assets/{digest}.png", b"")).hexdigest() != digest:
                        raise ValueError("Landing backup image digest mismatch")
                    for variant in entry.get("variants", []):
                        variant_digest = variant["sha256"]
                        if hashlib.sha256(files.get(variant_path(digest, variant_digest), b"")).hexdigest() != variant_digest:
                            raise ValueError("Landing backup display image digest mismatch")
                    raw_digest = (entry.get("source", {}).get("preparation") or {}).get("raw_sha256")
                    if raw_digest and hashlib.sha256(files.get(f"assets/raw/{raw_digest}.png", b"")).hexdigest() != raw_digest:
                        raise ValueError("Landing backup raw image digest mismatch")
        verify_assets(detail["assets"])
        for version in versions:
            verify_assets(version.get("assets", []))
    return dict(value), files


def restore_content(value: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Map a historical draft to the current matching template without AI inference."""
    configuration = deepcopy(value["configuration"])
    content = deepcopy(value["content"])
    reference = value["template_reference"] or {}
    if reference.get("template_id") == "app_showcase" and reference.get("template_version", 1) < 3:
        language = configuration.get("presentation", {}).get("language", "uk")
        content["hero"]["eyebrow"] = "Ваш простір. Ваші можливості." if language == "uk" else "Your space. Your possibilities."
        pieces = [part.strip() for part in content["hero"]["supporting_text"].split("•") if part.strip()]
        has_bullets = len(pieces) == 3 and all(len(part) <= 160 for part in pieces)
        configuration["showcase"]["hero_body_mode"] = "bullets" if has_bullets else "text"
        content["hero"]["bullets"] = pieces if has_bullets else [item["description"][:160] for item in content["features"]]
    return configuration, content
