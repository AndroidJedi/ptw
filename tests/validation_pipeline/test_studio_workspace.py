from __future__ import annotations

import base64
from hashlib import sha256
from io import BytesIO
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validation_pipeline.images import PexelsPhoto
from validation_pipeline.studio_universal import (
    DEFAULT_CONFIG, DEFAULT_CONTENT, SEMANTIC_ROLES, build_universal_template,
    normalize_universal_config, universal_content_from_generation,
)
from validation_pipeline.studio_workspace import UniversalStudioWorkspace


HAS_PILLOW = importlib.util.find_spec("PIL") is not None
HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


def _image_bytes(*, mime_type: str = "image/png", object_on_white: bool = False) -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1080, 1080), "white" if object_on_white else "#56738A")
    if object_on_white:
        ImageDraw.Draw(image).ellipse((260, 180, 820, 900), fill="#D54232")
    output = BytesIO()
    image.save(output, format="PNG" if mime_type == "image/png" else "JPEG")
    return output.getvalue()


class FakePexels:
    def __init__(self) -> None:
        self.calls: list[tuple[str, set[str]]] = []

    def select(self, query: str, _category: str, *, used_ids: set[str]):
        photo_id = str(1000 + len(self.calls))
        self.calls.append((query, set(used_ids)))
        return PexelsPhoto(
            photo_id=photo_id, width=1080, height=1080,
            image_url=f"https://images.pexels.com/photos/{photo_id}/image.jpeg",
            page_url=f"https://www.pexels.com/photo/{photo_id}/",
            photographer="Studio Test", photographer_url="https://www.pexels.com/@studio-test/",
            alt="Test object",
        ), _image_bytes(mime_type="image/jpeg", object_on_white=query == "red object")


@unittest.skipUnless(HAS_PILLOW, "Pillow is required")
class UniversalStudioWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = UniversalStudioWorkspace(Path(self.temporary.name), pexels=FakePexels())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_one_fixed_template_opens_with_requested_investment_post(self) -> None:
        detail = self.workspace.detail()
        self.assertEqual("universal_ad", detail["catalog"]["template_id"])
        self.assertEqual(list(SEMANTIC_ROLES), detail["catalog"]["semantic_roles"])
        self.assertEqual({"background_image", "sticker_object", "logo"}, {
            item["slot"] for item in detail["assets"]
        })
        assets = {item["slot"]: item for item in detail["assets"]}
        self.assertTrue(assets["background_image"]["available"])
        self.assertTrue(assets["sticker_object"]["available"])
        self.assertEqual("bundled_tune_asset", assets["background_image"]["source"]["origin"])
        self.assertEqual(
            "investment-hryvnia-sticker.png",
            assets["sticker_object"]["source"]["filename"],
        )
        self.assertFalse(assets["logo"]["available"])
        self.assertEqual("image", detail["configuration"]["background"]["mode"])
        self.assertTrue(detail["configuration"]["sticker"]["enabled"])
        self.assertTrue(detail["configuration"]["bullets"]["enabled"])
        self.assertFalse(detail["configuration"]["logo"]["enabled"])
        self.assertEqual(3, len(detail["content"]["bullets"]))
        preview = self.workspace.render_preview(state_sha256=detail["state_sha256"])
        self.assertEqual((1080, 1080), (preview["width"], preview["height"]))
        self.assertEqual("ptw.studio.preview.v1", preview["resolved"]["schema"])
        self.assertTrue({"sticker_object", "bullet_1", "bullet_2", "bullet_3"} <= set(
            preview["resolved"]["nodes"]
        ))
        self.assertNotIn("sticker_patch", preview["resolved"]["nodes"])
        self.assertEqual("#FFFFFF", preview["resolved"]["nodes"]["sticker_object"]["props"]["alpha_outline_color"])
        sticker = preview["resolved"]["nodes"]["sticker_object"]["props"]
        self.assertEqual(0.06, sticker["alpha_outline_width_ratio"])
        self.assertEqual("#00000020", sticker["alpha_outline_shadow_color"])
        self.assertEqual(2.0, sticker["alpha_outline_shadow_blur"])
        self.assertEqual(2.0, sticker["alpha_outline_shadow_y"])
        self.assertNotIn("logo", preview["resolved"]["nodes"])

        nodes = preview["resolved"]["nodes"]
        title = nodes["hero_title"]
        supporting = nodes["supporting_text"]
        title_box, title_visible = title["box"], title["visible_bounds"]
        supporting_visible = supporting["visible_bounds"]
        self.assertLessEqual(abs(title_visible["y"] - title_box["y"]), 1 / 1080)
        self.assertGreaterEqual(
            supporting_visible["y"] - title_visible["y"] - title_visible["height"],
            18 / 1080,
        )
        for node_id in ("hero_title", "supporting_text", "bullet_1", "bullet_2", "bullet_3"):
            self.assertFalse(nodes[node_id]["text_layout"]["overflow"], node_id)

    def test_draft_preview_changes_pixels_without_persisting_editor_state(self) -> None:
        detail = self.workspace.detail()
        persisted = self.workspace.render_preview(state_sha256=detail["state_sha256"])
        draft = {**detail["configuration"], "sticker": {
            **detail["configuration"]["sticker"], "enabled": False,
        }}
        rendered = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=draft,
            content=detail["content"],
        )
        self.assertNotEqual(persisted["bytes_sha256"], rendered["bytes_sha256"])
        self.assertNotIn("sticker_object", rendered["resolved"]["nodes"])
        unchanged = self.workspace.detail()
        self.assertEqual(detail["state_sha256"], unchanged["state_sha256"])
        self.assertTrue(unchanged["configuration"]["sticker"]["enabled"])
        with self.assertRaisesRegex(ValueError, "configuration and content together"):
            self.workspace.render_preview(
                state_sha256=detail["state_sha256"], configuration=draft,
            )

    def test_configuration_is_bounded_and_texture_bullets_render(self) -> None:
        base = self.workspace.detail()
        initial = self.workspace.render_preview(state_sha256=base["state_sha256"])
        config = {**base["configuration"], "background": {
            **base["configuration"]["background"], "mode": "texture", "texture": "grain",
        }, "bullets": {"enabled": True, "marker": "→"}}
        content = {**base["content"], "bullets": ["One promise", "One audience", "One action"]}
        changed = self.workspace.save_configuration(
            base_sha256=base["state_sha256"], configuration=config, content=content,
        )
        rendered = self.workspace.render_preview(state_sha256=changed["state_sha256"])
        self.assertNotEqual(initial["bytes_sha256"], rendered["bytes_sha256"])
        self.assertIn("background_texture", rendered["resolved"]["asset_sha256"])
        self.assertIn("bullet_3", rendered["resolved"]["nodes"])
        with self.assertRaisesRegex(RuntimeError, "reload"):
            self.workspace.save_configuration(
                base_sha256=base["state_sha256"], configuration=config, content=content,
            )
        invalid = {**DEFAULT_CONFIG, "arbitrary_tree": {}}
        with self.assertRaisesRegex(ValueError, "fields"):
            normalize_universal_config(invalid)

        extreme = changed["configuration"]
        extreme["typography"]["hero_size"] = 180
        extreme["typography"]["supporting_size"] = 52
        extreme["layout"]["content_y"] = 360
        extreme["layout"]["gap"] = 56
        fitted = self.workspace.save_configuration(
            base_sha256=changed["state_sha256"], configuration=extreme, content=content,
        )
        fitted_render = self.workspace.render_preview(state_sha256=fitted["state_sha256"])
        cta_box = fitted_render["resolved"]["nodes"]["cta"]["box"]
        self.assertLessEqual(cta_box["y"] + cta_box["height"], 0.96)

    def test_image_sticker_logo_and_immutable_version(self) -> None:
        detail = self.workspace.detail()
        for slot in ("background_image", "sticker_object", "logo"):
            data = _image_bytes()
            detail = self.workspace.upload_asset(
                slot, base_sha256=detail["state_sha256"], mime_type="image/png",
                bytes_base64=base64.b64encode(data).decode(),
            )
        config = detail["configuration"]
        config["background"]["mode"] = "image"
        config["background"]["image_layout"] = "right"
        config["sticker"]["enabled"] = True
        config["logo"]["enabled"] = True
        detail = self.workspace.save_configuration(
            base_sha256=detail["state_sha256"], configuration=config, content=detail["content"],
        )
        preview = self.workspace.render_preview(state_sha256=detail["state_sha256"])
        self.assertEqual(
            {"background_image", "sticker_object", "logo"},
            set(preview["resolved"]["asset_sha256"]),
        )
        approved = self.workspace.approve_version(
            state_sha256=detail["state_sha256"], change_note="First demand-test creative",
        )
        self.assertEqual(1, len(approved["versions"]))
        stored = self.workspace.version_render(1)
        self.assertEqual(preview["bytes_sha256"], stored["sha256"])

    def test_pexels_reuse_sources_background_and_isolated_sticker(self) -> None:
        detail = self.workspace.detail()
        detail = self.workspace.source_pexels(
            "background_image", base_sha256=detail["state_sha256"],
            query="calm workspace", isolate=False,
        )
        self.assertEqual("image", detail["configuration"]["background"]["mode"])
        background = next(item for item in detail["assets"] if item["slot"] == "background_image")
        self.assertEqual("pexels", background["source"]["provider"])
        detail = self.workspace.source_pexels(
            "sticker_object", base_sha256=detail["state_sha256"],
            query="red object", isolate=True,
        )
        sticker = next(item for item in detail["assets"] if item["slot"] == "sticker_object")
        self.assertEqual("image/png", sticker["mime_type"])
        self.assertEqual("edge_color_soft_alpha_v1", sticker["source"]["transformation"])
        self.assertTrue(detail["configuration"]["sticker"]["enabled"])
        self.workspace.render_preview(state_sha256=detail["state_sha256"])

    def test_template_builder_keeps_optional_roles_mapped_when_omitted(self) -> None:
        template = build_universal_template(DEFAULT_CONFIG, DEFAULT_CONTENT)
        self.assertEqual(set(SEMANTIC_ROLES), set(template.document["semantic_roles"]))
        self.assertEqual("approved", template.document["status"])
        self.assertEqual([], template.document["provenance"]["reference_ids"])
        sticker = next(
            node for node in template.document["root"]["children"]
            if node["id"] == "sticker_object"
        )
        self.assertEqual(["sticker_object"], template.document["semantic_roles"]["sticker"])
        self.assertEqual("#FFFFFF", sticker["props"]["alpha_outline_color"])
        self.assertEqual(0.06, sticker["props"]["alpha_outline_width_ratio"])

    def test_existing_generation_copy_maps_to_universal_semantic_content(self) -> None:
        content = universal_content_from_generation({
            "headline": "A calmer first step",
            "primary_text": "Meet a real psychologist and see whether it feels right.",
            "supporting_text": "This remains a fallback only.",
            "cta": "Book the first conversation",
        }, brief={"key_benefits": ["Real profiles", "Simple booking", "No card"]})
        self.assertEqual("A calmer first step", content["hero_title"])
        self.assertEqual("Meet a real psychologist and see whether it feels right.", content["supporting_text"])
        self.assertEqual(["Real profiles", "Simple booking", "No card"], content["bullets"])


@unittest.skipUnless(HAS_PILLOW and HAS_FASTAPI, "FastAPI and Pillow are required")
class UniversalStudioApiTests(unittest.TestCase):
    def test_loopback_app_serves_every_visible_owner_destination(self) -> None:
        from fastapi.testclient import TestClient
        from validation_pipeline.local_owner_demo import PROJECT_ID, RUN_ID
        from validation_pipeline.studio_local_api import create_app

        headers = {
            "Authorization": "Bearer e2e-owner-token",
            "X-Firebase-AppCheck": "e2e-app-check",
        }
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {
            "STUDIO_WORKSPACE_PATH": temporary,
            "PEXELS_API_KEY": "",
        }, clear=False):
            with TestClient(create_app()) as client:
                self.assertEqual(401, client.get("/api/v1/projects").status_code)
                projects = client.get("/api/v1/projects?limit=100", headers=headers)
                self.assertEqual(200, projects.status_code, projects.text)
                self.assertEqual(PROJECT_ID, projects.json()["items"][0]["project_id"])

                briefs = client.get(
                    f"/api/v1/briefs?limit=100&project_id={PROJECT_ID}", headers=headers,
                )
                self.assertEqual(200, briefs.status_code, briefs.text)
                brief_id = briefs.json()["items"][0]["brief_id"]
                self.assertEqual(200, client.get(
                    f"/api/v1/briefs/{brief_id}", headers=headers,
                ).status_code)

                runs = client.get(
                    f"/api/v1/content-runs?limit=50&project_id={PROJECT_ID}", headers=headers,
                )
                self.assertEqual(200, runs.status_code, runs.text)
                self.assertEqual(RUN_ID, runs.json()["items"][0]["run_id"])
                result = client.get(f"/api/v1/content-runs/{RUN_ID}/result", headers=headers)
                self.assertEqual(200, result.status_code, result.text)
                asset = client.get(result.json()["asset_url"], headers=headers)
                self.assertEqual(200, asset.status_code, asset.text)
                self.assertEqual("image/jpeg", asset.headers["content-type"])
                self.assertEqual(result.json()["asset_sha256"], sha256(asset.content).hexdigest())

                debug = client.get(f"/api/v1/content-runs/{RUN_ID}/debug", headers=headers)
                self.assertEqual(200, debug.status_code, debug.text)
                candidates = debug.json()["candidates"]
                self.assertEqual(5, len(candidates))
                self.assertEqual(5, len({item["preview"]["sha256"] for item in candidates}))
                for candidate in candidates:
                    preview = client.get(candidate["preview"]["asset_url"], headers=headers)
                    self.assertEqual(200, preview.status_code, preview.text)
                    self.assertEqual(candidate["preview"]["sha256"], sha256(preview.content).hexdigest())

                self.assertEqual(409, client.post(
                    f"/api/v1/content-runs/{RUN_ID}/feedback",
                    headers=headers, json={"decision": "accepted"},
                ).status_code)
                self.assertEqual(200, client.get("/api/v1/studio", headers=headers).status_code)
                self.assertEqual(404, client.get("/api/v1/studio/templates", headers=headers).status_code)
                self.assertEqual(404, client.get("/api/v1/studio/tune", headers=headers).status_code)

    def test_loopback_contract_has_no_template_library_or_reference_routes(self) -> None:
        from fastapi.testclient import TestClient
        from validation_pipeline.studio_local_api import LOCAL_APP_CHECK_TOKEN, LOCAL_OWNER_TOKEN
        from validation_pipeline.studio_routes import studio_router
        from fastapi import FastAPI

        with tempfile.TemporaryDirectory() as temporary:
            app = FastAPI()
            app.include_router(studio_router(
                UniversalStudioWorkspace(temporary), prefix="/api/v1/studio",
            ))
            with TestClient(app) as client:
                detail = client.get("/api/v1/studio")
                self.assertEqual(200, detail.status_code, detail.text)
                preview = client.post("/api/v1/studio/preview", json={
                    "state_sha256": detail.json()["state_sha256"],
                })
                self.assertEqual(200, preview.status_code, preview.text)
                self.assertEqual("private, no-store", preview.headers["cache-control"])
                draft_configuration = detail.json()["configuration"]
                draft_configuration["sticker"]["enabled"] = False
                draft_preview = client.post("/api/v1/studio/preview", json={
                    "state_sha256": detail.json()["state_sha256"],
                    "configuration": draft_configuration,
                    "content": detail.json()["content"],
                })
                self.assertEqual(200, draft_preview.status_code, draft_preview.text)
                self.assertNotEqual(preview.content, draft_preview.content)
                self.assertEqual(
                    detail.json()["state_sha256"],
                    client.get("/api/v1/studio").json()["state_sha256"],
                )
                self.assertEqual(404, client.get("/api/v1/studio/templates").status_code)
                self.assertEqual(404, client.get("/api/v1/studio/reference").status_code)
                self.assertEqual(404, client.post("/api/v1/studio/calibrate", json={}).status_code)
        self.assertEqual("e2e-owner-token", LOCAL_OWNER_TOKEN)
        self.assertEqual("e2e-app-check", LOCAL_APP_CHECK_TOKEN)
