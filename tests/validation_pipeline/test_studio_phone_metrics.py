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
    IPHONE_FRAME_SHA256, IPHONE_FRAME_SOURCE, PHONE_BACKGROUND_TEXTURES,
    PHONE_COPY_BACKGROUND_TEXTURES, PHONE_METRICS_TEMPLATE_ID,
    PHONE_SCREEN_TEXTURES,
    build_phone_metrics_template, compose_phone_device_asset,
    normalize_phone_metrics_config, normalize_phone_metrics_content,
    phone_metrics_catalog, phone_metrics_component_settings,
    phone_metrics_semantic_data,
)
from validation_pipeline.studio_workspace import UniversalStudioWorkspace


def _screen_bytes(background: str = "#F5F6F3") -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (832, 1792), background)
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

    def test_phone_template_is_4_by_5_and_fuses_crisp_screen_with_front_frame(self) -> None:
        detail = self._phone()
        preview = self.workspace.render_preview(state_sha256=detail["state_sha256"])
        self.assertEqual((1080, 1350), (preview["width"], preview["height"]))
        nodes = preview["resolved"]["nodes"]
        self.assertEqual(["phone_device"], [node_id for node_id in nodes if node_id == "phone_device"])
        device = nodes["phone_device"]
        self.assertGreater(device["visible_bounds"]["x"], 0.55)
        self.assertLess(device["visible_bounds"]["y"], 0.1)
        self.assertLess(device["visible_bounds"]["x"] + device["visible_bounds"]["width"], 0.99)
        self.assertLess(device["visible_bounds"]["y"] + device["visible_bounds"]["height"], 0.72)
        self.assertEqual("front_facing_upright", phone_metrics_catalog()["variation"]["device_pose"])
        template = build_phone_metrics_template(DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_CONTENT)
        phone = next(item for item in template.document["root"]["children"] if item["id"] == "phone_device")
        self.assertEqual("phone_device", phone["props"]["asset"])
        self.assertEqual(0.0, phone["props"]["rotation"])
        self.assertGreater(phone["props"]["height"], phone["props"]["width"])
        composite = compose_phone_device_asset(
            _screen_bytes(), "ІНВЕСТУЙТЕ В МАЙБУТНЄ", "ДІЗНАТИСЯ БІЛЬШЕ",
        )
        self.assertEqual(IPHONE_FRAME_SHA256, composite["source"]["frame_sha256"])
        self.assertEqual(
            "front_natal_app_shell_v8", composite["source"]["screen_composition"],
        )
        self.assertEqual(
            "deterministic_material_grain_v1", composite["source"]["hero_texture"],
        )
        from PIL import Image
        with Image.open(BytesIO(composite["bytes"])) as device_image:
            device_image = device_image.convert("RGBA")
            self.assertEqual((1293, 2656), device_image.size)
            alpha = device_image.getchannel("A")
            self.assertIsNotNone(alpha.getbbox())
            # The upright screen and frame are a single precomposited bitmap,
            # while the area outside the rounded phone stays transparent.
            self.assertGreater(alpha.getpixel((646, 1328)), 0)
            for corner in ((0, 0), (1292, 0), (0, 2655), (1292, 2655)):
                self.assertEqual(0, alpha.getpixel(corner))
            # These are real transparent aperture pixels on the two upper
            # curves. They previously fell just outside the estimated screen
            # matte and exposed the off-white creative background after scale.
            for curve_pixel in ((146, 70), (1148, 70), (129, 80), (1165, 80)):
                self.assertEqual(255, alpha.getpixel(curve_pixel))
                rgb = device_image.getpixel(curve_pixel)[:3]
                self.assertGreaterEqual(min(rgb), 245)
                self.assertLessEqual(max(rgb) - min(rgb), 2)
            self.assertEqual(1, len([phone["props"]["asset"]]))
            # Fixed app-shell pixels prove the brief artwork is no longer pasted
            # as an unstructured rectangle. The broad, horizontal blue button
            # also guards against reintroducing perspective distortion.
            blue_button = [
                (x, y) for y in range(2000, 2350) for x in range(100, 1190)
                if (lambda pixel: pixel[3] and pixel[2] > 180
                    and 70 < pixel[1] < 170 and pixel[0] < 70)(device_image.getpixel((x, y)))
            ]
            self.assertGreater(len(blue_button), 100_000)
            button_box = (
                min(point[0] for point in blue_button), min(point[1] for point in blue_button),
                max(point[0] for point in blue_button), max(point[1] for point in blue_button),
            )
            self.assertGreater(button_box[0], 140)
            self.assertGreater(button_box[2], 1120)
            self.assertGreater(button_box[2] - button_box[0], 900)
            button_tops = {
                x: min(y for point_x, y in blue_button if point_x == x)
                for x in range(320, 970)
            }
            self.assertLessEqual(max(button_tops.values()) - min(button_tops.values()), 2)
            cyan_logo_pixels = sum(
                1 for y in range(150, 500) for x in range(250, 1040)
                if (lambda pixel: pixel[3] and pixel[1] > 160 and pixel[2] > 170
                    and pixel[0] < 180)(device_image.getpixel((x, y)))
            )
            self.assertGreater(cyan_logo_pixels, 1_000)

        full_bleed = compose_phone_device_asset(
            _screen_bytes("#6AAFC8"), "ІНВЕСТУЙТЕ В МАЙБУТНЄ", "ДІЗНАТИСЯ БІЛЬШЕ",
        )
        with Image.open(BytesIO(full_bleed["bytes"])) as device_image:
            device_image = device_image.convert("RGB")
            # Mid-hero pixels immediately inside each bezel must come from the
            # artwork. The former 24px inset left these areas as white gutters.
            for edge_pixel in ((72, 900), (1221, 900)):
                red, green, blue = device_image.getpixel(edge_pixel)
                self.assertLess(red, 125)
                self.assertGreater(green, 160)
                self.assertGreater(blue, 190)
            # The artwork also continues behind the fixed header. The former
            # y=205 start produced a 17-level one-pixel jump beneath the logo.
            # A solid fixture must now transition only through the smooth
            # renderer-owned readability fade at that old boundary.
            for x in (160, 260, 1040, 1130):
                pixels = [device_image.getpixel((x, y)) for y in range(330, 356)]
                channel_steps = [
                    max(abs(first - second) for first, second in zip(before, after))
                    for before, after in zip(pixels, pixels[1:])
                ]
                self.assertLessEqual(max(channel_steps), 12)

            # A solid-color fixture still gains visible, deterministic material
            # variation in the hero region after the app shell is composed.
            grain_colours = {
                device_image.getpixel((x, y))
                for x in range(300, 1000, 19) for y in range(1200, 1370, 17)
            }
            self.assertGreaterEqual(len(grain_colours), 6)

    def test_metric_cards_are_compact_equal_and_smoothly_rounded(self) -> None:
        template = build_phone_metrics_template(DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_CONTENT)
        nodes = {item["id"]: item for item in template.document["root"]["children"]}
        cards = [nodes[f"metric_card_{index}"]["props"] for index in range(1, 4)]
        self.assertEqual([280, 280, 280], [card["width"] for card in cards])
        self.assertEqual([140, 140, 140], [card["height"] for card in cards])
        self.assertEqual([28, 28, 28], [card["radius"] for card in cards])
        self.assertEqual([92, 400, 708], [card["x"] for card in cards])

    def test_eyebrow_toggle_removes_node_and_reflows_headline(self) -> None:
        visible = build_phone_metrics_template(DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_CONTENT)
        visible_nodes = {
            item["id"]: item for item in visible.document["root"]["children"]
        }
        hidden_config = deepcopy(DEFAULT_PHONE_CONFIG)
        hidden_config["offer"]["enabled"] = False
        hidden = build_phone_metrics_template(hidden_config, DEFAULT_PHONE_CONTENT)
        hidden_nodes = {
            item["id"]: item for item in hidden.document["root"]["children"]
        }
        self.assertIn("offer", visible_nodes)
        self.assertNotIn("offer", hidden_nodes)
        self.assertNotIn("offer", hidden.document["semantic_roles"])
        self.assertNotIn(
            "content.offer",
            phone_metrics_semantic_data(hidden_config, DEFAULT_PHONE_CONTENT),
        )
        self.assertLess(
            hidden_nodes["hero_title"]["props"]["y"],
            visible_nodes["hero_title"]["props"]["y"],
        )
        self.assertEqual(["offer"], phone_metrics_catalog()["variation"]["optional_elements"])

        phone = self._phone()
        preview = self.workspace.render_preview(
            state_sha256=phone["state_sha256"], configuration=hidden_config,
            content=DEFAULT_PHONE_CONTENT,
        )
        self.assertNotIn("offer", preview["resolved"]["nodes"])

    def test_legacy_configuration_defaults_new_controls(self) -> None:
        legacy_v1 = deepcopy(DEFAULT_PHONE_CONFIG)
        legacy_v1["schema"] = "ptw.studio.phone-metrics-config.v1"
        legacy_v1.pop("offer")
        legacy_v1.pop("supporting_text")
        legacy_v1.pop("phone_screen")
        legacy_v1.pop("copy_background")
        legacy_v1["background"].pop("texture")
        self.assertEqual(DEFAULT_PHONE_CONFIG, normalize_phone_metrics_config(legacy_v1))

        legacy_v2 = deepcopy(DEFAULT_PHONE_CONFIG)
        legacy_v2["schema"] = "ptw.studio.phone-metrics-config.v2"
        legacy_v2.pop("supporting_text")
        legacy_v2.pop("phone_screen")
        legacy_v2.pop("copy_background")
        legacy_v2["background"].pop("texture")
        self.assertEqual(DEFAULT_PHONE_CONFIG, normalize_phone_metrics_config(legacy_v2))

        legacy_v3 = deepcopy(DEFAULT_PHONE_CONFIG)
        legacy_v3["schema"] = "ptw.studio.phone-metrics-config.v3"
        legacy_v3.pop("phone_screen")
        legacy_v3.pop("copy_background")
        legacy_v3["background"].pop("texture")
        self.assertEqual(DEFAULT_PHONE_CONFIG, normalize_phone_metrics_config(legacy_v3))

        legacy_v4 = deepcopy(DEFAULT_PHONE_CONFIG)
        legacy_v4["schema"] = "ptw.studio.phone-metrics-config.v4"
        legacy_v4.pop("copy_background")
        self.assertEqual(DEFAULT_PHONE_CONFIG, normalize_phone_metrics_config(legacy_v4))

    def test_three_optional_textures_change_each_bounded_surface(self) -> None:
        from PIL import Image

        catalog = phone_metrics_catalog()["variation"]
        self.assertEqual(list(PHONE_BACKGROUND_TEXTURES), catalog["background_textures"])
        self.assertEqual(
            list(PHONE_COPY_BACKGROUND_TEXTURES),
            catalog["copy_background_textures"],
        )
        self.assertEqual(list(PHONE_SCREEN_TEXTURES), catalog["phone_screen_textures"])
        self.assertEqual(3, len(PHONE_BACKGROUND_TEXTURES) - 1)
        self.assertEqual(3, len(PHONE_COPY_BACKGROUND_TEXTURES) - 1)
        self.assertEqual(3, len(PHONE_SCREEN_TEXTURES) - 1)

        for group, invalid_value in (
            ("background", "linen"), ("copy_background", "linen"),
            ("phone_screen", "canvas"),
        ):
            invalid = deepcopy(DEFAULT_PHONE_CONFIG)
            invalid[group]["texture"] = invalid_value
            with self.assertRaisesRegex(ValueError, "not an approved option"):
                normalize_phone_metrics_config(invalid)

        phone = self._phone()
        background_digests = set()
        for preset in PHONE_BACKGROUND_TEXTURES:
            config = deepcopy(DEFAULT_PHONE_CONFIG)
            config["background"]["texture"] = preset
            preview = self.workspace.render_preview(
                state_sha256=phone["state_sha256"], configuration=config,
                content=DEFAULT_PHONE_CONTENT,
            )
            nodes = preview["resolved"]["nodes"]
            self.assertEqual(preset != "none", "background_texture" in nodes)
            with Image.open(BytesIO(preview["bytes"])) as source:
                blank_surface = source.convert("RGB").crop((520, 0, 600, 1000))
                background_digests.add(sha256(blank_surface.tobytes()).hexdigest())
        self.assertEqual(4, len(background_digests))

        copy_surface_digests = set()
        outside_copy_digests = set()
        for preset in PHONE_COPY_BACKGROUND_TEXTURES:
            config = deepcopy(DEFAULT_PHONE_CONFIG)
            config["background"]["texture"] = "none"
            config["copy_background"]["texture"] = preset
            preview = self.workspace.render_preview(
                state_sha256=phone["state_sha256"], configuration=config,
                content=DEFAULT_PHONE_CONTENT,
            )
            nodes = preview["resolved"]["nodes"]
            self.assertEqual(preset != "none", "copy_background_texture" in nodes)
            if preset != "none":
                template_nodes = {
                    node["id"]: node
                    for node in build_phone_metrics_template(
                        config, DEFAULT_PHONE_CONTENT,
                    ).document["root"]["children"]
                }
                self.assertEqual(
                    "rounded_rect",
                    template_nodes["copy_background_texture"]["props"]["mask"],
                )
            with Image.open(BytesIO(preview["bytes"])) as source:
                rendered = source.convert("RGB")
                inside = rendered.crop((48, 180, 62, 900))
                outside = rendered.crop((555, 180, 590, 900))
                copy_surface_digests.add(sha256(inside.tobytes()).hexdigest())
                outside_copy_digests.add(sha256(outside.tobytes()).hexdigest())
        self.assertEqual(4, len(copy_surface_digests))
        self.assertEqual(1, len(outside_copy_digests))

        texture_provenance = {
            "none": "none",
            "grain": "deterministic_material_grain_v1",
            "paper": "deterministic_soft_paper_v1",
            "frosted": "deterministic_frosted_glass_v1",
        }
        screen_digests = set()
        for preset in PHONE_SCREEN_TEXTURES:
            composite = compose_phone_device_asset(
                _screen_bytes("#6AAFC8"), "ІНВЕСТУЙТЕ", "ДІЗНАТИСЯ БІЛЬШЕ",
                preset,
            )
            self.assertEqual(texture_provenance[preset], composite["source"]["hero_texture"])
            with Image.open(BytesIO(composite["bytes"])) as source:
                hero_surface = source.convert("RGB").crop((220, 650, 1070, 1500))
                screen_digests.add(sha256(hero_surface.tobytes()).hexdigest())
        self.assertEqual(4, len(screen_digests))

    def test_supporting_copy_markup_size_and_colour_reach_the_saved_renderer(self) -> None:
        for invalid_size in (19, 39):
            invalid = deepcopy(DEFAULT_PHONE_CONFIG)
            invalid["supporting_text"]["font_size"] = invalid_size
            with self.assertRaisesRegex(ValueError, "must be between 20 and 38"):
                normalize_phone_metrics_config(invalid)
        invalid = deepcopy(DEFAULT_PHONE_CONFIG)
        invalid["supporting_text"]["highlight_color"] = "blue"
        with self.assertRaisesRegex(ValueError, "six-digit hex color"):
            normalize_phone_metrics_config(invalid)

        config = deepcopy(DEFAULT_PHONE_CONFIG)
        config["supporting_text"] = {
            "font_size": 36,
            "highlight_color": "#D12F7A",
        }
        content = deepcopy(DEFAULT_PHONE_CONTENT)
        content["supporting_text"] = (
            "Natal — **перевірені** компанії. ==Інвестуй від $5,000==."
        )
        template = build_phone_metrics_template(config, content)
        node = next(
            item for item in template.document["root"]["children"]
            if item["id"] == "supporting_text"
        )
        self.assertEqual("rich_text", node["type"])
        self.assertEqual(36.0, node["props"]["font_size"])
        self.assertEqual("#D12F7A", node["props"]["highlight_color"])

        component_settings = phone_metrics_component_settings(config, content)
        settings = {
            setting["setting_id"]: setting["value"]
            for component in component_settings["components"]
            for setting in component["settings"]
        }
        self.assertEqual(36.0, settings["configuration.supporting_text.font_size"])
        self.assertEqual(
            "#D12F7A", settings["configuration.supporting_text.highlight_color"],
        )
        self.assertEqual("concrete", settings["configuration.background.texture"])
        self.assertEqual("none", settings["configuration.copy_background.texture"])
        self.assertEqual("grain", settings["configuration.phone_screen.texture"])

        phone = self._phone()
        preview = self.workspace.render_preview(
            state_sha256=phone["state_sha256"], configuration=config,
            content=content,
        )
        rendered_node = preview["resolved"]["nodes"]["supporting_text"]
        self.assertEqual("simple_v1", rendered_node["text_layout"]["markup"])
        self.assertGreater(rendered_node["text_layout"]["bold_character_count"], 0)
        self.assertGreater(rendered_node["text_layout"]["highlight_character_count"], 0)
        self.assertFalse(rendered_node["text_layout"]["overflow"])

        from PIL import Image
        with Image.open(BytesIO(preview["bytes"])) as source:
            supporting_area = source.convert("RGB").crop((70, 675, 488, 893))
            accent_pixels = sum(
                1 for red, green, blue in supporting_area.getdata()
                if red > 150 and green < 100 and blue > 80
            )
        self.assertGreater(accent_pixels, 100)

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
