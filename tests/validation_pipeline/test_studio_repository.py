from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from validation_pipeline.studio_repository import (
    DatabaseCreativeWorkspace, DatabaseStudioAuthority,
)
from validation_pipeline.studio_workspace import UniversalStudioWorkspace


class MemoryStudioRepository:
    def __init__(self) -> None:
        self.workspace_id = "01900000-0000-7000-8000-000000000501"
        self.files: dict[str, bytes] | None = None
        self.state_sha256 = ""
        self.assets: dict[str, str] = {}
        self.versions: dict[int, str] = {}

    def load_creative(self, workspace_id: str):
        assert workspace_id == self.workspace_id
        return (
            None if self.files is None
            else (self.state_sha256, dict(self.files))
        )

    def persist_creative(
        self, root: Path, *, workspace_id: str, state_sha256: str,
        template_id: str, template_version: int, template_sha256: str,
    ) -> str:
        assert workspace_id == self.workspace_id
        del template_id, template_version, template_sha256
        self.state_sha256 = state_sha256
        self.files = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()
        }
        history = root / "assets" / "phone_screen_history.json"
        if history.is_file():
            for index, item in enumerate(json.loads(history.read_text())["items"], 1):
                self.assets.setdefault(
                    item["sha256"], f"01900000-0000-7000-8000-{index:012d}",
                )
        for path in (root / "versions").glob("*_v*.json"):
            version = int(json.loads(path.read_text())["version"])
            self.versions.setdefault(
                version, f"01900000-0000-7000-8001-{version:012d}",
            )
        return self.workspace_id

    def identifiers(self, workspace_id: str):
        assert workspace_id == self.workspace_id
        return {"assets": dict(self.assets), "versions": dict(self.versions)}


class Provider:
    def generate(self, _prompt: str, *, reference_image: bytes | None = None):
        output = BytesIO()
        Image.new("RGB", (1024, 1024), "#dff7fb").save(output, "PNG")
        data = output.getvalue()
        return {
            "bytes": data, "mime_type": "image/png",
            "source": {
                "origin": "result_bridge_image_generation",
                "provider": "test", "text_in_screen": "prohibited_by_prompt",
                "operation": "image_edit" if reference_image else "image_generation",
                **({
                    "reference_image_sha256": hashlib.sha256(reference_image).hexdigest(),
                } if reference_image else {}),
            },
        }


class DatabaseCreativeWorkspaceTests(unittest.TestCase):
    def test_legacy_editor_save_and_noop_survive_a_fresh_database_restore(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from tests.validation_pipeline.test_studio_creatives import StudioCreativeServiceTests
        from validation_pipeline.studio_routes import studio_creative_router

        for changed, use_legacy_hash in ((True, False), (True, True), (False, False)):
            with self.subTest(changed=changed, use_legacy_hash=use_legacy_hash):
                fixture = StudioCreativeServiceTests()
                fixture.setUp()
                try:
                    project_id, _, initial = fixture.generate_creative("phone_metrics")
                    cid = initial["creative_id"]
                    workspace = fixture.service._workspace(cid)
                    config = workspace._configuration()
                    config["schema"] = "ptw.studio.phone-metrics-config.v8"
                    config.pop("logo")
                    config["phone_screen"].pop("logo_enabled")
                    (workspace.root / "configuration.json").write_text(json.dumps(config))
                    legacy_hash = workspace._legacy_phone_state_sha256()
                    fixture.authority.update_creative(cid, state_sha256=legacy_hash)
                    repository = MemoryStudioRepository()
                    repository.workspace_id = cid
                    repository.persist_creative(
                        workspace.root, workspace_id=cid, state_sha256=legacy_hash,
                        template_id="phone_metrics", template_version=22,
                        template_sha256=initial["template_sha256"],
                    )
                    original_files = deepcopy(repository.files)

                    def restart():
                        restored_root = fixture.root / ("restore-" + str(len(list(fixture.root.iterdir()))))
                        fixture.service._workspaces[cid] = DatabaseCreativeWorkspace(
                            UniversalStudioWorkspace(restored_root), repository, cid,
                        )

                    restart()
                    app = FastAPI()
                    app.include_router(studio_creative_router(fixture.service, prefix="/studio"))
                    with TestClient(app) as client:
                        path = f"/studio/projects/{project_id}/creatives/{cid}"
                        detail = client.get(path).json()
                        self.assertEqual(original_files, repository.files)
                        self.assertEqual(legacy_hash, repository.state_sha256)
                        self.assertNotEqual(legacy_hash, detail["state_sha256"])
                        content = deepcopy(detail["content"])
                        if changed:
                            content["hero_title"] = "Owner edits survive a server restart"
                        payload = {
                            "base_sha256": legacy_hash if use_legacy_hash else detail["state_sha256"],
                            "configuration": detail["configuration"], "content": content,
                        }
                        saved = client.post(path + "/save", json=payload)
                        self.assertEqual(200, saved.status_code, saved.text)
                        saved_detail = saved.json()["creative"]
                        self.assertEqual(content, saved_detail["content"])
                        self.assertEqual(saved_detail["state_sha256"], repository.state_sha256)
                        checkpoints = deepcopy(fixture.store.list("studio_edit_checkpoints"))
                        files = deepcopy(repository.files)
                        restart()
                        restored = client.get(path)
                        self.assertEqual(200, restored.status_code, restored.text)
                        self.assertEqual(saved_detail["state_sha256"], restored.json()["state_sha256"])
                        self.assertEqual(content, restored.json()["content"])
                        repeated = client.post(path + "/save", json={
                            **payload, "base_sha256": restored.json()["state_sha256"],
                        })
                        self.assertEqual(200, repeated.status_code, repeated.text)
                        self.assertFalse(repeated.json()["checkpoint_created"])
                        self.assertEqual(checkpoints, fixture.store.list("studio_edit_checkpoints"))
                        self.assertEqual(files, repository.files)
                        if changed:
                            rejected = client.post(path + "/save", json=payload)
                            self.assertEqual(409, rejected.status_code)
                            self.assertEqual(files, repository.files)
                finally:
                    fixture.tearDown()

    def test_legacy_phone_restore_is_read_only_and_preserves_approved_png(self):
        repository = MemoryStudioRepository()
        with tempfile.TemporaryDirectory() as original, tempfile.TemporaryDirectory() as restored_root:
            workspace = UniversalStudioWorkspace(original, image_provider=Provider())
            phone = workspace.apply_template(base_sha256=workspace.detail()["state_sha256"], template_id="phone_metrics")
            generated = workspace.generate_phone_screen(base_sha256=phone["state_sha256"], visual_direction="A glass sculpture.")
            workspace.approve_version(state_sha256=generated["state_sha256"], change_note="Historical image")
            png = workspace.version_render(1)["bytes"]
            config_path = Path(original) / "configuration.json"
            config = workspace._configuration()
            (Path(original) / "content.json").write_text(json.dumps(workspace._content()))
            config["schema"] = "ptw.studio.phone-metrics-config.v8"
            config.pop("logo")
            config["phone_screen"].pop("logo_enabled")
            config_path.write_text(json.dumps(config))
            old_digest = workspace._legacy_phone_state_sha256()
            repository.persist_creative(Path(original), workspace_id=repository.workspace_id,
                state_sha256=old_digest, template_id="phone_metrics", template_version=22, template_sha256="a"*64)
            original_files = dict(repository.files)
            for _ in range(2):
                restored = DatabaseCreativeWorkspace(UniversalStudioWorkspace(restored_root), repository, repository.workspace_id)
                self.assertNotEqual(old_digest, restored.detail()["state_sha256"])
                self.assertEqual(png, restored.version_render(1)["bytes"])
                self.assertEqual(original_files, repository.files)
                self.assertEqual(old_digest, repository.state_sha256)
            content = json.loads(repository.files["content.json"])
            content["hero_title"] = "Unapproved changed content"
            repository.files["content.json"] = json.dumps(content).encode()
            corrupt = DatabaseCreativeWorkspace(UniversalStudioWorkspace(restored_root), repository, repository.workspace_id)
            with self.assertRaisesRegex(RuntimeError, "state digest"):
                corrupt.detail()

    def test_database_authority_accepts_derived_version_count_during_checkpoint_finalize(self) -> None:
        workspace_id = "01900000-0000-7000-8000-000000000501"

        class Result:
            rowcount = 1

        class Connection:
            def __init__(self) -> None:
                self.calls: list[tuple[str, list[object]]] = []

            def execute(self, query, values):
                self.calls.append((query, values))
                return Result()

        class RecordingAuthority(DatabaseStudioAuthority):
            def __init__(self) -> None:
                self.database_url = "unused"
                self.connection_value = Connection()

            @contextmanager
            def connection(self):
                yield self.connection_value

            def get_creative(self, creative_id: str):
                return {
                    "creative_id": creative_id,
                    "state_sha256": "a" * 64,
                    "approved_version_count": 1,
                }

        authority = RecordingAuthority()
        updated = authority.update_creative(
            workspace_id, state_sha256="a" * 64, approved_version_count=1,
        )

        self.assertEqual(1, updated["approved_version_count"])
        self.assertEqual(1, len(authority.connection_value.calls))
        query, values = authority.connection_value.calls[0]
        self.assertNotIn("approved_version_count=", query)
        self.assertIn("state_sha256=%s", query)
        self.assertEqual("a" * 64, values[0])

    def test_restores_the_same_workspace_asset_and_version_ids_after_restart(self) -> None:
        repository = MemoryStudioRepository()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            studio = DatabaseCreativeWorkspace(
                UniversalStudioWorkspace(first, image_provider=Provider()), repository,
                repository.workspace_id,
            )
            initial = studio.detail()
            phone = studio.apply_template(
                base_sha256=initial["state_sha256"], template_id="phone_metrics",
            )
            generated = studio.generate_phone_screen(
                base_sha256=phone["state_sha256"],
                visual_direction="One polished glass unicorn on warm white.",
            )
            approved = studio.approve_version(
                state_sha256=generated["state_sha256"], change_note="Restart authority",
            )

            restored = DatabaseCreativeWorkspace(
                UniversalStudioWorkspace(second, image_provider=Provider()), repository,
                repository.workspace_id,
            ).detail()

        self.assertEqual(initial["workspace_id"], restored["workspace_id"])
        self.assertEqual("phone_metrics", restored["template_id"])
        self.assertEqual(
            generated["phone_screen_history"][0]["asset_id"],
            restored["phone_screen_history"][0]["asset_id"],
        )
        self.assertEqual(
            approved["versions"][0]["version_id"],
            restored["versions"][0]["version_id"],
        )


if __name__ == "__main__":
    unittest.main()
