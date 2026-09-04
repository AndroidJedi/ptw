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
    PHONE_ACTION_BUTTON_RADII, PHONE_ACTION_BUTTON_SHAPES,
    PHONE_ACTION_BUTTON_STYLES, PHONE_COPY_BACKGROUND_TEXTURES,
    PHONE_METRIC_CARD_RADII,
    PHONE_METRIC_CARD_SHAPES, PHONE_METRIC_CARD_STYLES,
    PHONE_HERO_ART_OFFSET_Y, PHONE_METRICS_TEMPLATE_ID,
    PHONE_SCREEN_ART_SIZE, PHONE_SCREEN_TEXTURES, _draw_status_network_icons,
    _fixed_screen_shell, _position_phone_hero_art,
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


class FakePhoneScreenImageProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.references: list[bytes | None] = []
        self.colors = ["#6AAFC8", "#C586D8", "#E3A451", "#77B989", "#8D91D8"]

    def generate(self, prompt: str, *, reference_image: bytes | None = None) -> dict:
        self.prompts.append(prompt)
        self.references.append(reference_image)
        return {
            "bytes": _screen_bytes(self.colors[(len(self.prompts) - 1) % len(self.colors)]),
            "mime_type": "image/png",
            "source": {
                "origin": "codex_builtin_image_generation", "provider": "openai",
                "transport": "authenticated_codex_cli",
                "model": "codex-builtin-image-generation",
                "text_in_screen": "prohibited_by_prompt",
            },
        }


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
            "front_natal_app_shell_v13", composite["source"]["screen_composition"],
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
                (x, y) for y in range(1700, 2400) for x in range(100, 1190)
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

            # The image and its selected finish must ease into the lower white
            # content area together; an unfaded texture used to leave a crisp
            # horizontal cutoff immediately above the title.
            shell = _fixed_screen_shell(
                Image.new("RGBA", PHONE_SCREEN_ART_SIZE, "#6AAFC8"),
                "ІНВЕСТУЙТЕ В МАЙБУТНЄ", "ДІЗНАТИСЯ БІЛЬШЕ", "grain",
            ).convert("RGB")
            fade_pixels = [shell.getpixel((20, y)) for y in range(720, 1080)]
            fade_luminance = [sum(pixel) / 3 for pixel in fade_pixels]
            self.assertGreater(fade_luminance[-1], fade_luminance[0] + 75)
            boundary_steps = [
                max(abs(first - second) for first, second in zip(before, after))
                for before, after in zip(fade_pixels, fade_pixels[1:])
            ]
            self.assertLessEqual(max(boundary_steps[-45:]), 3)

            # A solid-color fixture still gains visible, deterministic material
            # variation in the hero region after the app shell is composed.
            grain_colours = {
                device_image.getpixel((x, y))
                for x in range(300, 1000, 19) for y in range(1200, 1370, 17)
            }
            self.assertGreaterEqual(len(grain_colours), 6)

    def test_phone_hero_subject_is_lowered_but_artwork_still_reaches_the_top(self) -> None:
        from PIL import Image, ImageDraw

        self.assertEqual(220, PHONE_HERO_ART_OFFSET_Y)
        source = Image.new("RGBA", (832, 832), "#6AAFC8")
        ImageDraw.Draw(source).rectangle((300, 180, 532, 360), fill="#E12D8C")
        positioned = _position_phone_hero_art(
            source, (PHONE_SCREEN_ART_SIZE[0], 1050),
        )

        self.assertEqual((106, 175, 200, 255), positioned.getpixel((20, 0)))
        self.assertTrue(all(positioned.getpixel((20, y))[3] == 255 for y in range(1050)))
        marker = [
            (x, y)
            for y in range(1050) for x in range(positioned.width)
            if positioned.getpixel((x, y))[:3] == (225, 45, 140)
        ]
        self.assertTrue(marker)
        self.assertGreaterEqual(min(y for _x, y in marker), 400)
        self.assertGreaterEqual(
            min(y for _x, y in marker),
            PHONE_HERO_ART_OFFSET_Y + 200,
        )

    def test_status_bar_network_signal_has_four_bars_and_complete_wifi(self) -> None:
        from PIL import Image, ImageDraw

        status = Image.new("RGBA", (832, 100), (0, 0, 0, 0))
        _draw_status_network_icons(ImageDraw.Draw(status, "RGBA"))
        alpha = status.getchannel("A")

        bar_tops = []
        for x in (636, 650, 664, 678):
            ink = [y for y in range(100) if alpha.getpixel((x, y))]
            self.assertTrue(ink)
            bar_tops.append(min(ink))
        self.assertEqual(sorted(bar_tops, reverse=True), bar_tops)
        self.assertEqual(4, len(set(bar_tops)))

        wifi_center = [bool(alpha.getpixel((718, y))) for y in range(20, 85)]
        wifi_runs = sum(
            current and not previous
            for previous, current in zip([False, *wifi_center], wifi_center)
        )
        self.assertEqual(4, wifi_runs)
        self.assertFalse(any(alpha.getpixel((x, y)) for x in range(750, 756) for y in range(20, 85)))

    def test_metric_cards_are_compact_equal_and_smoothly_rounded(self) -> None:
        template = build_phone_metrics_template(DEFAULT_PHONE_CONFIG, DEFAULT_PHONE_CONTENT)
        nodes = {item["id"]: item for item in template.document["root"]["children"]}
        cards = [nodes[f"metric_card_{index}"]["props"] for index in range(1, 4)]
        self.assertEqual([280, 280, 280], [card["width"] for card in cards])
        self.assertEqual([140, 140, 140], [card["height"] for card in cards])
        self.assertEqual([28, 28, 28], [card["radius"] for card in cards])
        self.assertEqual([92, 400, 708], [card["x"] for card in cards])
        self.assertEqual(["#2457C8"] * 3, [card["background_color"] for card in cards])
        self.assertEqual([None] * 3, [card["border_color"] for card in cards])
        self.assertEqual(
            ["#FFFFFF"] * 6,
            [
                nodes[f"metric_{kind}_{index}"]["props"]["color"]
                for index in range(1, 4) for kind in ("value", "label")
            ],
        )

    def test_metric_buttons_independently_tune_style_text_background_and_shape(self) -> None:
        config = deepcopy(DEFAULT_PHONE_CONFIG)
        config["metric_cards"] = [
            {
                "style": "outlined", "text_color": "#101B31",
                "background_color": "#CEDD3C", "shape": "square",
            },
            {
                "style": "filled", "text_color": "#101B31",
                "background_color": "#CEDD3C", "shape": "pill",
            },
            {
                "style": "filled", "text_color": "#FFFFFF",
                "background_color": "#D12F7A", "shape": "rounded",
            },
        ]
        content = deepcopy(DEFAULT_PHONE_CONTENT)
        content["stats"] = [
            {"value": "42%", "label": "conversion"},
            {"value": "24h", "label": "review"},
            {"value": "95", "label": "startups"},
        ]
        template = build_phone_metrics_template(config, content)
        nodes = {item["id"]: item for item in template.document["root"]["children"]}

        first = nodes["metric_card_1"]["props"]
        self.assertIsNone(first["background_color"])
        self.assertEqual("#CEDD3C", first["border_color"])
        self.assertEqual(4.0, first["border_width"])
        self.assertEqual(PHONE_METRIC_CARD_RADII["square"], first["radius"])
        second = nodes["metric_card_2"]["props"]
        self.assertEqual("#CEDD3C", second["background_color"])
        self.assertIsNone(second["border_color"])
        self.assertEqual(PHONE_METRIC_CARD_RADII["pill"], second["radius"])
        self.assertEqual("#D12F7A", nodes["metric_card_3"]["props"]["background_color"])
        self.assertEqual("#101B31", nodes["metric_value_1"]["props"]["color"])
        self.assertEqual("#FFFFFF", nodes["metric_label_3"]["props"]["color"])

        catalog = phone_metrics_catalog()["variation"]
        self.assertEqual(list(PHONE_METRIC_CARD_STYLES), catalog["metric_card_styles"])
        self.assertEqual(list(PHONE_METRIC_CARD_SHAPES), catalog["metric_card_shapes"])
        settings = {
            setting["setting_id"]: setting["value"]
            for component in phone_metrics_component_settings(config, content)["components"]
            for setting in component["settings"]
        }
        self.assertEqual(config["metric_cards"], settings["configuration.metric_cards"])
        self.assertEqual(content["stats"], settings["content.stats"])

        phone = self._phone()
        default_preview = self.workspace.render_preview(state_sha256=phone["state_sha256"])
        tuned_preview = self.workspace.render_preview(
            state_sha256=phone["state_sha256"], configuration=config, content=content,
        )
        self.assertNotEqual(
            default_preview["bytes_sha256"], tuned_preview["bytes_sha256"],
        )
        for index in range(1, 4):
            self.assertFalse(
                tuned_preview["resolved"]["nodes"][f"metric_value_{index}"]["text_layout"]["overflow"]
            )
            self.assertFalse(
                tuned_preview["resolved"]["nodes"][f"metric_label_{index}"]["text_layout"]["overflow"]
            )

        for field, invalid_value in (
            ("style", "glass"), ("shape", "circle"),
            ("text_color", "white"), ("background_color", "blue"),
        ):
            invalid = deepcopy(DEFAULT_PHONE_CONFIG)
            invalid["metric_cards"][0][field] = invalid_value
            with self.assertRaises(ValueError):
                normalize_phone_metrics_config(invalid)
        invalid = deepcopy(DEFAULT_PHONE_CONFIG)
        invalid["metric_cards"].pop()
        with self.assertRaisesRegex(ValueError, "exactly three metric cards"):
            normalize_phone_metrics_config(invalid)

    def test_in_phone_bottom_buttons_match_reference_and_are_independently_tunable(self) -> None:
        from PIL import Image

        self.assertEqual(
            ["filled", "elevated", "text"],
            [button["style"] for button in DEFAULT_PHONE_CONFIG["phone_buttons"]],
        )
        self.assertEqual(
            ["Створити новий акаунт", "Увійти", "Можливо пізніше"],
            DEFAULT_PHONE_CONTENT["phone_buttons"],
        )
        catalog = phone_metrics_catalog()["variation"]
        self.assertEqual(
            list(PHONE_ACTION_BUTTON_STYLES), catalog["phone_button_styles"],
        )
        self.assertEqual(
            list(PHONE_ACTION_BUTTON_SHAPES), catalog["phone_button_shapes"],
        )

        shell = _fixed_screen_shell(
            Image.new("RGBA", PHONE_SCREEN_ART_SIZE, "#F9FAFA"),
            "ІНВЕСТУЙТЕ В МАЙБУТНЄ", "ЗОВНІШНІЙ CTA", "none",
            list(DEFAULT_PHONE_CONTENT["phone_buttons"]),
            deepcopy(DEFAULT_PHONE_CONFIG["phone_buttons"]),
        ).convert("RGB")
        self.assertEqual((22, 117, 248), shell.getpixel((120, 1320)))
        self.assertEqual((255, 255, 255), shell.getpixel((120, 1440)))
        self.assertEqual((255, 255, 255), shell.getpixel((120, 1560)))
        tertiary_blue = sum(
            shell.getpixel((x, y)) == (22, 117, 248)
            for y in range(1532, 1607) for x in range(70, 763)
        )
        self.assertGreater(tertiary_blue, 50)
        self.assertNotEqual((249, 250, 250), shell.getpixel((416, 1521)))
        self.assertNotEqual((22, 117, 248), shell.getpixel((70, 1284)))

        config = deepcopy(DEFAULT_PHONE_CONFIG)
        config["phone_buttons"] = [
            {
                "style": "outlined", "text_color": "#101B31",
                "background_color": "#D12F7A", "shape": "square",
            },
            {
                "style": "filled", "text_color": "#101B31",
                "background_color": "#CEDD3C", "shape": "square",
            },
            {
                "style": "elevated", "text_color": "#FFFFFF",
                "background_color": "#2457C8", "shape": "rounded",
            },
        ]
        content = deepcopy(DEFAULT_PHONE_CONTENT)
        content["phone_buttons"] = ["Почати", "Увійти зараз", "Продовжити"]
        normalized_config = normalize_phone_metrics_config(config)
        normalized_content = normalize_phone_metrics_content(content)
        settings = {
            setting["setting_id"]: setting["value"]
            for component in phone_metrics_component_settings(config, content)["components"]
            for setting in component["settings"]
        }
        self.assertEqual(config["phone_buttons"], settings["configuration.phone_buttons"])
        self.assertEqual(content["phone_buttons"], settings["content.phone_buttons"])
        tuned = _fixed_screen_shell(
            Image.new("RGBA", PHONE_SCREEN_ART_SIZE, "#F9FAFA"),
            "ІНВЕСТУЙТЕ", "ЗОВНІШНІЙ CTA", "none",
            normalized_content["phone_buttons"], normalized_config["phone_buttons"],
        ).convert("RGB")
        self.assertEqual((209, 47, 122), tuned.getpixel((70, 1284)))
        self.assertEqual((255, 255, 255), tuned.getpixel((416, 1336)))
        self.assertEqual((206, 221, 60), tuned.getpixel((70, 1410)))
        self.assertEqual(
            PHONE_ACTION_BUTTON_RADII["rounded"],
            PHONE_ACTION_BUTTON_RADII[config["phone_buttons"][2]["shape"]],
        )

        for field, invalid_value in (
            ("style", "glass"), ("shape", "circle"),
            ("text_color", "white"), ("background_color", "blue"),
        ):
            invalid = deepcopy(DEFAULT_PHONE_CONFIG)
            invalid["phone_buttons"][0][field] = invalid_value
            with self.assertRaises(ValueError):
                normalize_phone_metrics_config(invalid)
        invalid = deepcopy(DEFAULT_PHONE_CONFIG)
        invalid["phone_buttons"].pop()
        with self.assertRaisesRegex(ValueError, "exactly three phone buttons"):
            normalize_phone_metrics_config(invalid)
        invalid_content = deepcopy(DEFAULT_PHONE_CONTENT)
        invalid_content["phone_buttons"].pop()
        with self.assertRaisesRegex(ValueError, "exactly three phone buttons"):
            normalize_phone_metrics_content(invalid_content)

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

    def test_template_apply_replaces_mutable_draft_and_preserves_approved_version(self) -> None:
        detail = self.workspace.detail()
        self.workspace.approve_version(
            state_sha256=detail["state_sha256"], change_note="Approved universal creative",
        )
        # Create one mutable asset before replacing the draft template.
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

    def test_owner_direction_generates_and_persists_one_text_free_phone_visual(self) -> None:
        provider = FakePhoneScreenImageProvider()
        self.workspace.image_provider = provider
        phone = self._phone()
        self.assertTrue(phone["phone_screen_generation_available"])
        before = self.workspace.render_preview(state_sha256=phone["state_sha256"])

        with self.assertRaisesRegex(ValueError, "requires an existing"):
            self.workspace.generate_phone_screen(
                base_sha256=phone["state_sha256"],
                visual_direction="Polish the current sculptural direction.",
                enhance_current=True,
            )
        self.assertEqual([], provider.prompts)

        generated = self.workspace.generate_phone_screen(
            base_sha256=phone["state_sha256"],
            visual_direction="  Translucent glass steps in soft blue light with one lime accent.  ",
        )

        self.assertEqual(1, len(provider.prompts))
        self.assertEqual([None], provider.references)
        self.assertIn("Translucent glass steps", provider.prompts[0])
        screen = next(item for item in generated["assets"] if item["slot"] == "phone_screen")
        self.assertTrue(screen["available"])
        self.assertEqual("codex_builtin_image_generation", screen["source"]["origin"])
        self.assertEqual(
            "Translucent glass steps in soft blue light with one lime accent.",
            screen["source"]["visual_direction"],
        )
        self.assertEqual(
            "owner_directed_text_free_phone_hero_v1",
            screen["source"]["prompt_contract"],
        )
        self.assertEqual("generate_new", screen["source"]["generation_mode"])
        self.assertEqual(1, len(generated["phone_screen_history"]))
        self.assertTrue(generated["phone_screen_history"][0]["selected"])
        after = self.workspace.render_preview(state_sha256=generated["state_sha256"])
        self.assertNotEqual(before["bytes_sha256"], after["bytes_sha256"])

        enhanced = self.workspace.generate_phone_screen(
            base_sha256=generated["state_sha256"],
            visual_direction="Keep the unicorn composition and improve its material polish.",
            enhance_current=True,
        )
        self.assertEqual(2, len(provider.prompts))
        self.assertIn("Edit the supplied current hero image", provider.prompts[1])
        self.assertEqual(_screen_bytes("#6AAFC8"), provider.references[1])
        enhanced_screen = next(
            item for item in enhanced["assets"] if item["slot"] == "phone_screen"
        )
        self.assertEqual("enhance_current", enhanced_screen["source"]["generation_mode"])
        self.assertEqual(
            "owner_directed_text_free_phone_hero_enhancement_v1",
            enhanced_screen["source"]["prompt_contract"],
        )
        self.assertEqual(screen["sha256"], enhanced_screen["source"]["reference_asset_sha256"])
        self.assertEqual(2, len(enhanced["phone_screen_history"]))
        self.assertEqual(enhanced_screen["sha256"], enhanced["phone_screen_history"][0]["sha256"])

        class FailingProvider:
            @staticmethod
            def generate(_prompt: str, *, reference_image: bytes | None = None) -> dict:
                self.assertIsNotNone(reference_image)
                raise RuntimeError("provider unavailable")

        self.workspace.image_provider = FailingProvider()
        with self.assertRaisesRegex(RuntimeError, "previous visual was preserved"):
            self.workspace.generate_phone_screen(
                base_sha256=enhanced["state_sha256"],
                visual_direction="A different premium sculptural direction.",
                enhance_current=True,
            )
        after_failure = self.workspace.detail()
        current_screen = next(
            item for item in after_failure["assets"]
            if item["slot"] == "phone_screen"
        )
        self.assertEqual(enhanced_screen["sha256"], current_screen["sha256"])
        self.assertEqual(enhanced["phone_screen_history"], after_failure["phone_screen_history"])

    def test_phone_screen_history_keeps_three_and_selected_image_drives_enhancement(self) -> None:
        provider = FakePhoneScreenImageProvider()
        self.workspace.image_provider = provider
        detail = self._phone()
        generated_digests = []
        for index in range(4):
            detail = self.workspace.generate_phone_screen(
                base_sha256=detail["state_sha256"],
                visual_direction=f"Distinct premium hero direction number {index + 1}.",
            )
            current = next(
                item for item in detail["assets"] if item["slot"] == "phone_screen"
            )
            generated_digests.append(current["sha256"])

        history = detail["phone_screen_history"]
        self.assertEqual(3, len(history))
        self.assertEqual(list(reversed(generated_digests[1:])), [item["sha256"] for item in history])
        self.assertEqual([True, False, False], [item["selected"] for item in history])
        self.assertEqual(3, len(list(self.workspace.assets.glob("phone_screen_history_*.png"))))
        with self.assertRaisesRegex(KeyError, "not found"):
            self.workspace.phone_screen_history_image(generated_digests[0])

        selected_sha256 = history[2]["sha256"]
        selected_bytes = self.workspace.phone_screen_history_image(selected_sha256)["bytes"]
        before_selection_render = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
        )
        selected = self.workspace.select_phone_screen(
            base_sha256=detail["state_sha256"], sha256=selected_sha256,
        )
        self.assertEqual(
            [False, False, True],
            [item["selected"] for item in selected["phone_screen_history"]],
        )
        self.assertEqual(
            selected_sha256,
            next(item for item in selected["assets"] if item["slot"] == "phone_screen")["sha256"],
        )
        after_selection_render = self.workspace.render_preview(
            state_sha256=selected["state_sha256"],
        )
        self.assertNotEqual(
            before_selection_render["bytes_sha256"], after_selection_render["bytes_sha256"],
        )

        enhanced = self.workspace.generate_phone_screen(
            base_sha256=selected["state_sha256"],
            visual_direction="Preserve this selected composition and polish its material finish.",
            enhance_current=True,
        )
        self.assertEqual(selected_bytes, provider.references[-1])
        self.assertEqual(3, len(enhanced["phone_screen_history"]))
        with self.assertRaisesRegex(ValueError, "digest"):
            self.workspace.select_phone_screen(
                base_sha256=enhanced["state_sha256"], sha256="not-a-digest",
            )
