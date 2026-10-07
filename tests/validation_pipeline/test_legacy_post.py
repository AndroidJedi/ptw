"""Retained Universal Posts remain inspectable without reactivating the template."""

from __future__ import annotations

from copy import deepcopy
import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from validation_pipeline.legacy_post import detail, preview
from validation_pipeline.post_templates import POST_TEMPLATE_REGISTRY
from validation_pipeline.studio_creatives import StudioCreativeService
from validation_pipeline.studio_routes import studio_creative_router
from validation_pipeline.studio_universal import DEFAULT_CONFIG, DEFAULT_CONTENT


PROJECT_ID = "11111111-1111-4111-8111-111111111111"
CREATIVE_ID = "22222222-2222-4222-8222-222222222222"
STATE_SHA = "0262242d16ac0360b405029190730c642eed6c8ca3014bb85d11c954ba8da6af"


def retained_files() -> dict[str, bytes]:
    return {
        "template.json": json.dumps({
            "schema": "ptw.studio.template-selection.v1", "template_id": "universal_ad",
        }).encode(),
        "configuration.json": json.dumps(deepcopy(DEFAULT_CONFIG)).encode(),
        "content.json": json.dumps(deepcopy(DEFAULT_CONTENT)).encode(),
    }


class LegacyPostTests(unittest.TestCase):
    def test_saved_draft_opens_and_renders_without_reactivating_template(self) -> None:
        files = retained_files()
        self.assertNotIn("universal_ad", POST_TEMPLATE_REGISTRY.ids)
        self.assertTrue(detail(files, state_sha256=STATE_SHA)["legacy_read_only"])
        rendered = preview(files)
        self.assertEqual("image/png", rendered["mime_type"])
        self.assertTrue(rendered["bytes"].startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(files, retained_files())

    def test_service_checks_project_and_stale_state_before_rendering(self) -> None:
        files = retained_files()

        class Repository:
            def load_creative(self, creative_id):
                self_id = creative_id
                assert self_id == CREATIVE_ID
                return STATE_SHA, files

        class Authority:
            repository = Repository()

            def get_creative(self, creative_id):
                assert creative_id == CREATIVE_ID
                return {"project_id": PROJECT_ID, "template_id": "universal_ad", "state_sha256": STATE_SHA}

        service = object.__new__(StudioCreativeService)
        service.authority = Authority()
        service.summary = lambda _creative_id: {"creative_id": CREATIVE_ID}
        service._workspace = lambda _creative_id: self.fail("legacy read entered the active workspace")
        self.assertEqual("post.legacy.readonly", service.detail(PROJECT_ID, CREATIVE_ID)["editor_key"])
        with self.assertRaises(KeyError):
            service.detail("33333333-3333-4333-8333-333333333333", CREATIVE_ID)
        with self.assertRaises(RuntimeError):
            service.legacy_preview(PROJECT_ID, CREATIVE_ID, state_sha256="b" * 64)
        self.assertTrue(service.legacy_preview(PROJECT_ID, CREATIVE_ID, state_sha256=STATE_SHA)["bytes"])

    def test_tampered_optional_asset_is_rejected(self) -> None:
        files = retained_files()
        files["assets/background_image.json"] = json.dumps({
            "filename": "background.png", "sha256": "0" * 64,
            "mime_type": "image/png", "width": 1080, "height": 1080,
        }).encode()
        files["assets/background.png"] = b"not an image"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            preview(files)

    def test_state_digest_mismatch_blocks_a_retained_read(self) -> None:
        files = retained_files()
        content = json.loads(files["content.json"])
        content["hero_title"] = "Changed without updating the workspace digest"
        files["content.json"] = json.dumps(content).encode()

        class Repository:
            def load_creative(self, _creative_id):
                return STATE_SHA, files

        class Authority:
            repository = Repository()

            def get_creative(self, _creative_id):
                return {"project_id": PROJECT_ID, "template_id": "universal_ad", "state_sha256": STATE_SHA}

        service = object.__new__(StudioCreativeService)
        service.authority = Authority()
        with self.assertRaisesRegex(RuntimeError, "state digest"):
            service.detail(PROJECT_ID, CREATIVE_ID)

    def test_exact_internal_http_read_and_private_preview(self) -> None:
        files = retained_files()

        class Repository:
            def load_creative(self, _creative_id):
                return STATE_SHA, files

        class Authority:
            repository = Repository()

            def get_creative(self, _creative_id):
                return {"project_id": PROJECT_ID, "template_id": "universal_ad", "state_sha256": STATE_SHA}

        service = object.__new__(StudioCreativeService)
        service.authority = Authority()
        service.summary = lambda _creative_id: {"creative_id": CREATIVE_ID}
        app = FastAPI()
        app.include_router(studio_creative_router(service, prefix="/internal/v1/studio"))
        path = f"/internal/v1/studio/projects/{PROJECT_ID}/creatives/{CREATIVE_ID}"
        with TestClient(app) as client:
            opened = client.get(path)
            self.assertEqual(200, opened.status_code, opened.text)
            self.assertTrue(opened.json()["legacy_sample_content"])
            rendered = client.post(path + "/preview", json={"state_sha256": STATE_SHA})
            self.assertEqual(200, rendered.status_code, rendered.text)
            self.assertEqual("private, no-store", rendered.headers["cache-control"])
            self.assertEqual("image/png", rendered.headers["content-type"])
            rejected = client.post(path + "/preview", json={
                "state_sha256": STATE_SHA, "configuration": {}, "content": {},
            })
            self.assertEqual(400, rejected.status_code)


if __name__ == "__main__":
    unittest.main()
