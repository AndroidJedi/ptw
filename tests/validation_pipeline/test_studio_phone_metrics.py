from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validation_pipeline.studio_phone_metrics import (
    DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_CONTENT, IPHONE_FRAME_PATH,
    IPHONE_FRAME_SHA256, IPHONE_FRAME_SOURCE, PHONE_METRICS_TEMPLATE_ID,
    build_phone_metrics_template, compose_phone_device_asset,
    normalize_phone_metrics_content,
)
from validation_pipeline.studio_workspace import UniversalStudioWorkspace


def _screen_bytes() -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (832, 1792), "#F5F6F3")
    ImageDraw.Draw(image).ellipse((150, 260, 650, 760), fill="#CEDD3C")
    output = BytesIO(); image.save(output, format="PNG")
    return output.getvalue()


@unittest.skipUnless(__import__("importlib").util.find_spec("PIL") is not None, "Pillow is required")
class PhoneMetricsTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = UniversalStudioWorkspace(Path(self.temporary.name))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _phone(self) -> dict:
        universal = self.workspace.detail()
        return self.workspace.apply_template(
            base_sha256=universal["state_sha256"], template_id=PHONE_METRICS_TEMPLATE_ID,
        )

    def test_static_owner_selected_frame_has_checked_in_source_license_and_digest(self) -> None:
        manifest = json.loads(IPHONE_FRAME_PATH.with_suffix(".json").read_text())
        self.assertEqual(IPHONE_FRAME_SHA256, sha256(IPHONE_FRAME_PATH.read_bytes()).hexdigest())
        self.assertEqual(IPHONE_FRAME_SHA256, manifest["sha256"])
        self.assertEqual(IPHONE_FRAME_SOURCE["source"], manifest["source"])
        self.assertEqual("2026-09-03", manifest["prepared_once_on"])
        self.assertEqual("prohibited", manifest["runtime_fetch"])
        self.assertIn("owner-authorized", manifest["license"].casefold())
        with patch("urllib.request.urlopen", side_effect=AssertionError("runtime fetch")):
            self.assertEqual(IPHONE_FRAME_SHA256, compose_phone_device_asset(None, "")["source"]["frame_sha256"])

    def test_phone_template_is_4_by_5_and_fuses_screen_frame_and_right_rail(self) -> None:
        detail = self._phone()
        preview = self.workspace.render_preview(state_sha256=detail["state_sha256"])
        self.assertEqual((1080, 1350), (preview["width"], preview["height"]))
        nodes = preview["resolved"]["nodes"]
        self.assertEqual(["phone_device"], [node_id for node_id in nodes if node_id == "phone_device"])
        device = nodes["phone_device"]
        self.assertGreater(device["visible_bounds"]["x"], 0.48)
        self.assertLess(device["visible_bounds"]["y"], 0.1)
        self.assertLess(device["visible_bounds"]["x"] + device["visible_bounds"]["width"], 0.99)
        template = build_phone_metrics_template(DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_CONTENT)
        phone = next(item for item in template.document["root"]["children"] if item["id"] == "phone_device")
        self.assertEqual("phone_device", phone["props"]["asset"])
        self.assertEqual(0.0, phone["props"]["rotation"])
        self.assertGreater(phone["props"]["height"], phone["props"]["width"])
        composite = compose_phone_device_asset(_screen_bytes(), "")
        self.assertEqual(IPHONE_FRAME_SHA256, composite["source"]["frame_sha256"])
        from PIL import Image
        with Image.open(BytesIO(composite["bytes"])) as device_image:
            self.assertEqual((1201, 1310), device_image.size)
            alpha = device_image.getchannel("A")
            self.assertIsNotNone(alpha.getbbox())
            # The owner-selected perspective has a hardware rail at right and
            # the screen/frame are a single precomposited bitmap downstream.
            self.assertGreater(alpha.getpixel((900, 500)), 0)
            self.assertEqual(1, len([phone["props"]["asset"]]))

    def test_phone_content_requires_exactly_three_owner_statistics(self) -> None:
        invalid = deepcopy(DEFAULT_PHONE_CONTENT)
        invalid["stats"].pop()
        with self.assertRaisesRegex(ValueError, "exactly three"):
            normalize_phone_metrics_content(invalid)
        invalid = deepcopy(DEFAULT_PHONE_CONTENT)
        invalid["stats"].append({"value": "four", "label": "wrong"})
        with self.assertRaisesRegex(ValueError, "exactly three"):
            normalize_phone_metrics_content(invalid)

    def test_template_apply_replaces_mutable_draft_and_preserves_legacy_version(self) -> None:
        detail = self.workspace.detail()
        self.workspace.approve_version(
            state_sha256=detail["state_sha256"], change_note="Legacy universal creative",
        )
        # Create one mutable legacy asset before the replacement.
        self.workspace._store_asset(  # pylint: disable=protected-access
            "background_image", mime_type="image/png", data=_screen_bytes(),
            source={"origin": "test"},
        )
        detail = self.workspace.detail()
        phone = self.workspace.apply_template(
            base_sha256=detail["state_sha256"], template_id=PHONE_METRICS_TEMPLATE_ID,
        )
        self.assertEqual(PHONE_METRICS_TEMPLATE_ID, phone["template_id"])
        self.assertEqual(DEFAULT_PHONE_CONTENT, phone["content"])
        self.assertEqual(DEFAULT_PHONE_CONFIG, phone["configuration"])
        self.assertFalse((self.workspace.assets / "background_image.png").exists())
        self.assertEqual(1, len(phone["versions"]))
        self.assertEqual("universal_ad", self.workspace.version_detail(1)["template_id"])

    def test_natal_is_fixed_and_phone_screen_rejects_owner_upload(self) -> None:
        phone = self._phone()
        assets = {item["slot"]: item for item in phone["assets"]}
        self.assertFalse(assets["logo"]["editable"])
        self.assertFalse(assets["phone_screen"]["editable"])
        with self.assertRaisesRegex(ValueError, "cannot be uploaded"):
            self.workspace.upload_asset(
                "phone_screen", base_sha256=phone["state_sha256"], mime_type="image/png",
                bytes_base64=base64.b64encode(_screen_bytes()).decode(),
            )
        with self.assertRaisesRegex(ValueError, "fixed Studio identity"):
            self.workspace.upload_asset(
                "logo", base_sha256=phone["state_sha256"], mime_type="image/png",
                bytes_base64=base64.b64encode(_screen_bytes()).decode(),
            )
