from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from validation_pipeline.studio_repository import DatabaseCreativeWorkspace
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
