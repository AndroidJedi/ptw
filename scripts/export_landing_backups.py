#!/usr/bin/env python3
"""Export and verify every production Landing as a private self-contained JSON file."""

from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validation_pipeline.config import Settings
from validation_pipeline.landing_pages import DatabaseLandingAuthority, DatabaseLandingWorkspace, LandingService
from validation_pipeline.landing_publication import DatabaseLandingPublicationAuthority
from validation_pipeline.landing_workspace import LandingWorkspace


def backup_module(path: str | None):
    if path is None:
        from validation_pipeline import landing_backup
        return landing_backup
    # Supports a read-only export from the accepted container before cutover.
    spec = importlib.util.spec_from_file_location("validation_pipeline.landing_backup", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Landing backup module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--expected-approved-versions", type=int, required=True)
    parser.add_argument("--backup-module")
    args = parser.parse_args()
    if args.expected_count < 1 or args.output_dir.exists():
        raise ValueError("Expected count must be positive and output directory must be new")
    backup = backup_module(args.backup_module)
    settings = Settings.from_environment()
    authority = DatabaseLandingAuthority(settings.database_url)
    publications = DatabaseLandingPublicationAuthority(settings.database_url)
    with psycopg.connect(settings.database_url) as connection:
        rows = connection.execute("SELECT project_id,entity_id FROM landing_workspaces ORDER BY project_id,entity_id").fetchall()
    if len(rows) != args.expected_count:
        raise RuntimeError(f"Expected {args.expected_count} Landings; found {len(rows)}")
    old_umask = os.umask(0o077)
    try:
        args.output_dir.mkdir(mode=0o700, parents=True)
        manifest = {"schema": "ptw.landing.backup-manifest.v1", "count": len(rows), "items": []}
        with TemporaryDirectory(prefix="ptw-landing-export-") as temporary:
            service = LandingService(
                root=Path(temporary), authority=authority,
                workspace_factory=lambda path: DatabaseLandingWorkspace(LandingWorkspace(path), authority, path.name),
                structured_provider=None, composer_skill_path=settings.landing_composer_skill_path,
                manual_agent_skill_path=settings.studio_manual_agent_skill_path,
            )
            try:
                for project, landing in rows:
                    project_id, landing_id = str(project), str(landing)
                    document = backup.export_backup(service, project_id, landing_id, publications)
                    backup.validate_backup(document, project_id=project_id)
                    raw = (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
                    filename = f"landing-{landing_id}.json"
                    path = args.output_dir / filename
                    with path.open("xb") as output:
                        output.write(raw)
                    os.chmod(path, 0o600)
                    readback = path.read_bytes()
                    if readback != raw:
                        raise RuntimeError("Landing backup readback changed")
                    backup.validate_backup(json.loads(readback), project_id=project_id)
                    manifest["items"].append({
                        "landing_id": landing_id, "project_id": project_id,
                        "filename": filename, "sha256": sha256(raw).hexdigest(),
                        "bytes": len(raw), "template_reference": document["template_reference"],
                        "approved_versions": len(document["approved_versions"]),
                        "publication_events": len((document["publication"] or {}).get("events", [])),
                    })
            finally:
                service.operations.close()
        if sum(item["approved_versions"] for item in manifest["items"]) != args.expected_approved_versions:
            raise RuntimeError("Approved Landing version count changed during export")
        manifest_path = args.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(manifest_path, 0o600)
        print(json.dumps({"count": len(rows), "approved_versions": sum(item["approved_versions"] for item in manifest["items"]),
                          "publication_events": sum(item["publication_events"] for item in manifest["items"]),
                          "total_bytes": sum(item["bytes"] for item in manifest["items"]),
                          "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest()}, sort_keys=True))
    finally:
        os.umask(old_umask)


if __name__ == "__main__":
    main()
