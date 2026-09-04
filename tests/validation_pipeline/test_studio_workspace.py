from __future__ import annotations

import base64
import copy
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validation_pipeline.images import PexelsPhoto
from validation_pipeline.natal_brand import NATAL_LOGO_SHA256
from validation_pipeline.studio import StudioRenderer
from validation_pipeline.studio_universal import (
    DEFAULT_CONFIG, DEFAULT_CONTENT, FONT_FAMILIES, SEMANTIC_ROLES, TEXTURE_PRESETS,
    build_universal_template, isolate_object, normalize_universal_config, semantic_data, texture_asset,
    universal_ad_catalog,
    universal_alignment_rectangle, universal_component_settings,
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
            alt="Photograph of a real red ceramic object",
        ), _image_bytes(mime_type="image/jpeg", object_on_white=query == "red object")


@unittest.skipUnless(HAS_PILLOW, "Pillow is required")
class UniversalStudioWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = UniversalStudioWorkspace(Path(self.temporary.name), pexels=FakePexels())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_sticker_isolation_rejects_a_retained_rectangular_scene(self) -> None:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1080, 1080), "#202060")
        draw = ImageDraw.Draw(image)
        draw.rectangle((540, 0, 1080, 540), fill="#D05020")
        draw.rectangle((0, 540, 540, 1080), fill="#20A060")
        draw.rectangle((540, 540, 1080, 1080), fill="#E0C030")
        output = BytesIO()
        image.save(output, format="JPEG", quality=94)
        with self.assertRaisesRegex(ValueError, "rectangular scene"):
            isolate_object(output.getvalue())

    def test_sticker_isolation_rejects_an_edge_cropped_subject(self) -> None:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1080, 1080), "#F5F2EA")
        ImageDraw.Draw(image).ellipse((240, 180, 1120, 900), fill="#D54232")
        output = BytesIO()
        image.save(output, format="JPEG", quality=94)
        with self.assertRaisesRegex(ValueError, "edge-cropped subject"):
            isolate_object(output.getvalue())

    def test_one_fixed_template_opens_with_requested_investment_post(self) -> None:
        detail = self.workspace.detail()
        self.assertEqual("universal_ad", detail["catalog"]["template_id"])
        self.assertEqual("ptw.studio.workspace.v8", detail["schema"])
        self.assertFalse(detail["phone_screen_generation_available"])
        self.assertEqual(["universal_ad", "phone_metrics"], [
            item["template_id"] for item in detail["templates"]
        ])
        self.assertEqual("ptw.studio.universal-ad-catalog.v6", detail["catalog"]["schema"])
        self.assertTrue(detail["catalog"]["setting_definitions"])
        setting_definitions = {
            item["setting_id"]: item for item in detail["catalog"]["setting_definitions"]
        }
        self.assertFalse(any(key.startswith("configuration.logo.") for key in setting_definitions))
        sticker_width = setting_definitions["configuration.sticker.width"]
        self.assertEqual("universal_ad.sticker", sticker_width["component_id"])
        self.assertEqual((120, 720, 1), (
            sticker_width["minimum"], sticker_width["maximum"], sticker_width["step"],
        ))
        self.assertIn("розмір стікера", sticker_width["aliases"])
        self.assertEqual(11, detail["catalog"]["template_version"])
        self.assertEqual(list(SEMANTIC_ROLES), detail["catalog"]["semantic_roles"])
        self.assertEqual(
            [f"universal_ad.{role}" for role in SEMANTIC_ROLES],
            [item["component_id"] for item in detail["catalog"]["components"]],
        )
        self.assertEqual(
            universal_component_settings(detail["configuration"], detail["content"]),
            detail["component_settings"],
        )
        components = {
            item["component_id"]: item for item in detail["component_settings"]["components"]
        }
        background_settings = {
            item["setting_id"]: item["value"]
            for item in components["universal_ad.background"]["settings"]
        }
        logo_settings = {
            item["setting_id"]: item["value"]
            for item in components["universal_ad.logo"]["settings"]
        }
        self.assertEqual("texture", background_settings["configuration.background.mode"])
        self.assertEqual(0.56, background_settings["configuration.background.overlay_opacity"])
        self.assertNotIn("configuration.logo.background_enabled", logo_settings)
        self.assertNotIn("configuration.logo.background_color", logo_settings)
        self.assertEqual(
            ["canvas", "background_media", "readability_overlay"],
            components["universal_ad.background"]["node_ids"],
        )
        self.assertEqual(["background_image"], components["universal_ad.background"]["asset_slot_ids"])
        self.assertEqual(["logo"], components["universal_ad.logo"]["node_ids"])
        self.assertEqual({"background_image", "sticker_object", "logo"}, {
            item["slot"] for item in detail["assets"]
        })
        assets = {item["slot"]: item for item in detail["assets"]}
        self.assertFalse(assets["background_image"]["available"])
        self.assertFalse(assets["sticker_object"]["available"])
        self.assertTrue(assets["logo"]["available"])
        self.assertEqual(NATAL_LOGO_SHA256, assets["logo"]["sha256"])
        self.assertEqual(
            "canonical_natal_brand_asset", assets["logo"]["source"]["origin"],
        )
        self.assertEqual("logo-natal.png", assets["logo"]["source"]["filename"])
        self.assertEqual("texture", detail["configuration"]["background"]["mode"])
        self.assertFalse(detail["configuration"]["sticker"]["enabled"])
        self.assertTrue(detail["configuration"]["bullets"]["enabled"])
        self.assertTrue(detail["configuration"]["logo"]["enabled"])
        self.assertEqual("top_right", detail["configuration"]["logo"]["position"])
        self.assertEqual(180, detail["configuration"]["logo"]["width"])
        self.assertFalse(detail["configuration"]["logo"]["background_enabled"])
        self.assertEqual("#FFFFFF", detail["configuration"]["logo"]["background_color"])
        self.assertEqual(3, len(detail["content"]["bullets"]))
        preview = self.workspace.render_preview(state_sha256=detail["state_sha256"])
        self.assertEqual((1080, 1080), (preview["width"], preview["height"]))
        self.assertEqual("ptw.studio.preview.v1", preview["resolved"]["schema"])
        self.assertTrue({
            "bullet_marker_1", "bullet_1", "bullet_marker_2",
            "bullet_2", "bullet_marker_3", "bullet_3", "logo",
        } <= set(
            preview["resolved"]["nodes"]
        ))
        self.assertNotIn("sticker_object", preview["resolved"]["nodes"])
        self.assertNotIn("sticker_patch", preview["resolved"]["nodes"])
        self.assertEqual(
            NATAL_LOGO_SHA256, preview["resolved"]["asset_sha256"]["logo"],
        )
        self.assertNotIn("logo_surface", preview["resolved"]["nodes"])
        logo = preview["resolved"]["nodes"]["logo"]
        alignment = universal_alignment_rectangle(detail["configuration"])
        self.assertAlmostEqual(alignment["y"] / 1080, logo["box"]["y"])
        self.assertAlmostEqual(
            (alignment["x"] + alignment["width"]) / 1080,
            logo["box"]["x"] + logo["box"]["width"],
        )
        self.assertEqual(detail["component_settings"], preview["resolved"]["component_settings"])

        agent_context = self.workspace.agent_context()
        self.assertEqual("ptw.studio.agent-context.v3", agent_context["schema"])
        self.assertEqual(detail["state_sha256"], agent_context["state_sha256"])
        self.assertEqual(detail["component_settings"], agent_context["component_settings"])
        self.assertRegex(agent_context["sha256"], r"^[0-9a-f]{64}$")

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

    def test_logo_copy_and_cta_share_one_alignment_rectangle(self) -> None:
        detail = self.workspace.detail()
        config = copy.deepcopy(detail["configuration"])
        config["cta"]["position"] = "bottom_left"
        template = build_universal_template(config, detail["content"])
        nodes = {
            node["id"]: node["props"]
            for node in template.document["root"]["children"]
        }
        alignment = universal_alignment_rectangle(config)
        left, top = alignment["x"], alignment["y"]
        right = left + alignment["width"]
        bottom = top + alignment["height"]
        self.assertEqual((left, top), (nodes["hero_title"]["x"], nodes["hero_title"]["y"]))
        self.assertLessEqual(nodes["hero_title"]["x"] + nodes["hero_title"]["width"], right)
        self.assertEqual((left, bottom), (
            nodes["cta"]["x"], nodes["cta"]["y"] + nodes["cta"]["height"],
        ))
        self.assertEqual((top, right), (
            nodes["logo"]["y"], nodes["logo"]["x"] + nodes["logo"]["width"],
        ))

        config["cta"]["position"] = "bottom_right"
        config["logo"].update({"position": "top_left", "background_enabled": True})
        template = build_universal_template(config, detail["content"])
        nodes = {
            node["id"]: node["props"]
            for node in template.document["root"]["children"]
        }
        self.assertNotIn("logo_surface", nodes)
        self.assertEqual((left, top), (nodes["logo"]["x"], nodes["logo"]["y"]))
        self.assertLessEqual(nodes["logo"]["x"] + nodes["logo"]["width"], right)
        self.assertEqual((right, bottom), (
            nodes["cta"]["x"] + nodes["cta"]["width"],
            nodes["cta"]["y"] + nodes["cta"]["height"],
        ))

    def test_protected_long_cta_reports_and_passes_exact_text_fit(self) -> None:
        detail = self.workspace.detail()
        content = copy.deepcopy(detail["content"])
        content["cta"] = "Get your first opportunity for free."
        configuration = copy.deepcopy(detail["configuration"])
        configuration["layout"].update({"content_x": 500, "content_width": 500})
        configuration["bullets"]["enabled"] = False
        rendered = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=configuration, content=content,
        )
        cta = rendered["resolved"]["nodes"]["cta"]
        self.assertIsNotNone(cta["text_layout"])
        self.assertLessEqual(cta["text_layout"]["source_line_count"], 2)
        self.assertLessEqual(cta["text_layout"]["line_count"], 2)
        self.assertGreaterEqual(cta["text_layout"]["font_size"], 18)
        self.assertFalse(cta["text_layout"]["overflow"])
        self.assertFalse(cta["text_layout"]["truncated"])

    def test_long_ukrainian_cta_fits_completely_in_two_lines(self) -> None:
        detail = self.workspace.detail()
        content = copy.deepcopy(detail["content"])
        content["cta"] = "Записатися на безкоштовну 15-хвилинну розмову"
        configuration = copy.deepcopy(detail["configuration"])
        configuration["layout"].update({"content_x": 500, "content_width": 500})
        configuration["bullets"]["enabled"] = False

        rendered = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=configuration, content=content,
        )
        layout = rendered["resolved"]["nodes"]["cta"]["text_layout"]

        self.assertLessEqual(layout["line_count"], 2)
        self.assertGreaterEqual(layout["font_size"], 18)
        self.assertFalse(layout["overflow"])
        self.assertFalse(layout["truncated"])

    def test_cta_font_size_is_bounded_and_changes_authoritative_pixels(self) -> None:
        detail = self.workspace.detail()
        base = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=detail["configuration"], content=detail["content"],
        )
        configuration = copy.deepcopy(detail["configuration"])
        configuration["cta"]["font_size"] = 38
        changed = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=configuration, content=detail["content"],
        )
        self.assertEqual(38, changed["resolved"]["nodes"]["cta"]["props"]["font_size"])
        self.assertNotEqual(base["bytes_sha256"], changed["bytes_sha256"])
        configuration["cta"]["font_size"] = 42
        long_content = copy.deepcopy(detail["content"])
        long_content["cta"] = "Get your first opportunity for free."
        maximum = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=configuration, content=long_content,
        )
        self.assertFalse(maximum["resolved"]["nodes"]["cta"]["text_layout"]["overflow"])
        self.assertFalse(maximum["resolved"]["nodes"]["cta"]["text_layout"]["truncated"])
        configuration["cta"]["font_size"] = 43
        with self.assertRaisesRegex(ValueError, "cta.font_size"):
            normalize_universal_config(configuration)

    def test_draft_preview_changes_pixels_without_persisting_editor_state(self) -> None:
        detail = self.workspace.detail()
        persisted = self.workspace.render_preview(state_sha256=detail["state_sha256"])
        draft = {**detail["configuration"], "bullets": {
            **detail["configuration"]["bullets"], "enabled": False,
        }}
        rendered = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=draft,
            content=detail["content"],
        )
        self.assertNotEqual(persisted["bytes_sha256"], rendered["bytes_sha256"])
        self.assertNotIn("bullet_1", rendered["resolved"]["nodes"])
        unchanged = self.workspace.detail()
        self.assertEqual(detail["state_sha256"], unchanged["state_sha256"])
        self.assertTrue(unchanged["configuration"]["bullets"]["enabled"])
        with self.assertRaisesRegex(ValueError, "configuration and content together"):
            self.workspace.render_preview(
                state_sha256=detail["state_sha256"], configuration=draft,
            )

    def test_draft_component_metadata_has_stable_ids_and_exact_typed_values(self) -> None:
        detail = self.workspace.detail()
        draft = copy.deepcopy(detail["configuration"])
        draft["background"]["texture_intensity"] = 0.23
        draft["cta"]["style"] = "outlined"
        metadata = self.workspace.component_settings(
            state_sha256=detail["state_sha256"],
            configuration=draft,
            content=detail["content"],
        )
        components = {item["component_id"]: item for item in metadata["components"]}
        background = {
            item["setting_id"]: item["value"]
            for item in components["universal_ad.background"]["settings"]
        }
        cta = {
            item["setting_id"]: item["value"]
            for item in components["universal_ad.cta"]["settings"]
        }
        self.assertEqual(0.23, background["configuration.background.texture_intensity"])
        self.assertEqual("outlined", cta["configuration.cta.style"])
        self.assertEqual("below_text", cta["configuration.cta.position"])
        self.assertNotEqual(detail["component_settings"]["sha256"], metadata["sha256"])
        self.assertEqual(detail["state_sha256"], self.workspace.detail()["state_sha256"])

    def test_configuration_is_bounded_and_texture_bullets_render(self) -> None:
        base = self.workspace.detail()
        initial = self.workspace.render_preview(state_sha256=base["state_sha256"])
        config = {**base["configuration"], "background": {
            **base["configuration"]["background"], "mode": "texture", "texture": "grain",
        }, "bullets": {"enabled": True, "style": "circle_outline"}}
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

    def test_background_controls_have_exact_visible_render_effects(self) -> None:
        from PIL import Image

        detail = self.workspace.detail()
        clear = copy.deepcopy(detail["configuration"])
        clear["background"]["overlay_opacity"] = 0
        clear_render = self.workspace.render_preview(
            state_sha256=detail["state_sha256"], configuration=clear, content=detail["content"],
        )
        dark = copy.deepcopy(clear)
        dark["background"]["overlay_opacity"] = 0.85
        dark_render = self.workspace.render_preview(
            state_sha256=detail["state_sha256"], configuration=dark, content=detail["content"],
        )
        clear_pixel = Image.open(BytesIO(clear_render["bytes"])).convert("RGB").getpixel((20, 20))
        dark_pixel = Image.open(BytesIO(dark_render["bytes"])).convert("RGB").getpixel((20, 20))
        overlay = (7, 24, 46)
        distance = lambda pixel: sum(abs(pixel[index] - overlay[index]) for index in range(3))
        self.assertNotEqual(clear_render["bytes_sha256"], dark_render["bytes_sha256"])
        self.assertLess(distance(dark_pixel), distance(clear_pixel))

        stone = copy.deepcopy(clear)
        stone["background"].update({
            "mode": "texture", "texture": "stone", "texture_intensity": 1,
        })
        stone_render = self.workspace.render_preview(
            state_sha256=detail["state_sha256"], configuration=stone, content=detail["content"],
        )
        hidden = copy.deepcopy(stone)
        hidden["background"]["texture_intensity"] = 0
        hidden_render = self.workspace.render_preview(
            state_sha256=detail["state_sha256"], configuration=hidden, content=detail["content"],
        )
        self.assertIn("background_media", stone_render["resolved"]["nodes"])
        self.assertNotIn("background_media", hidden_render["resolved"]["nodes"])
        self.assertNotEqual(stone_render["bytes_sha256"], hidden_render["bytes_sha256"])

        catalog = universal_ad_catalog()["variation"]["texture_presets"]
        self.assertEqual(list(TEXTURE_PRESETS), catalog)
        self.assertNotIn("paper", catalog)
        texture_digests = {preset: texture_asset(preset)["sha256"] for preset in catalog}
        self.assertEqual(len(catalog), len(set(texture_digests.values())))

    def test_image_mix_bullet_cta_and_sticker_variants_are_bounded(self) -> None:
        detail = self.workspace.detail()
        detail = self.workspace.upload_asset(
            "background_image", base_sha256=detail["state_sha256"], mime_type="image/png",
            bytes_base64=base64.b64encode(_image_bytes()).decode(),
        )
        detail = self.workspace.source_pexels(
            "sticker_object", base_sha256=detail["state_sha256"],
            query="red object", isolate=True,
        )
        for image_percent, expected_x, expected_width in ((75, 0.25, 0.75), (25, 0.75, 0.25)):
            config = copy.deepcopy(detail["configuration"])
            config["background"].update({
                "mode": "image", "image_layout": "right", "image_percent": image_percent,
            })
            rendered = self.workspace.render_preview(
                state_sha256=detail["state_sha256"], configuration=config, content=detail["content"],
            )
            box = rendered["resolved"]["nodes"]["background_media"]["box"]
            self.assertAlmostEqual(expected_x, box["x"])
            self.assertAlmostEqual(expected_width, box["width"])

        markers = {"check": "✓", "circle": "●", "circle_outline": "○"}
        for style, marker in markers.items():
            config = copy.deepcopy(detail["configuration"])
            config["bullets"]["style"] = style
            data = semantic_data(config, detail["content"])
            self.assertEqual(marker, data["content.bullet_marker_1"])
            self.assertEqual(detail["content"]["bullets"][0], data["content.bullet_1"])

        cta_nodes = {}
        cta_style_digests = set()
        for style in ("filled", "gradient", "reverse", "link", "outlined"):
            config = copy.deepcopy(detail["configuration"])
            config["cta"]["style"] = style
            cta_nodes[style] = next(
                node for node in build_universal_template(config, detail["content"]).document["root"]["children"]
                if node["id"] == "cta"
            )["props"]
            cta_style_digests.add(self.workspace.render_preview(
                state_sha256=detail["state_sha256"],
                configuration=config,
                content=detail["content"],
            )["bytes_sha256"])
        self.assertEqual([], cta_nodes["filled"]["background_gradient"])
        self.assertEqual(2, len(cta_nodes["gradient"]["background_gradient"]))
        self.assertEqual(detail["configuration"]["cta"]["text_color"], cta_nodes["reverse"]["background_color"])
        self.assertIsNone(cta_nodes["link"]["background_color"])
        self.assertEqual(4.0, cta_nodes["outlined"]["border_width"])
        self.assertEqual(5, len(cta_style_digests))
        custom_colors = copy.deepcopy(detail["configuration"])
        custom_colors["cta"].update({
            "style": "filled", "background_color": "#E2385A", "text_color": "#F9F4EA",
        })
        custom_cta = next(
            node for node in build_universal_template(
                custom_colors, detail["content"],
            ).document["root"]["children"] if node["id"] == "cta"
        )["props"]
        self.assertEqual("#E2385A", custom_cta["background_color"])
        self.assertEqual("#F9F4EA", custom_cta["label_color"])

        cta_positions = {}
        cta_position_digests = set()
        for position in ("below_text", "bottom_left", "bottom_right"):
            config = copy.deepcopy(detail["configuration"])
            config["cta"]["position"] = position
            cta_positions[position] = next(
                node for node in build_universal_template(
                    config, detail["content"],
                ).document["root"]["children"] if node["id"] == "cta"
            )["props"]
            cta_position_digests.add(self.workspace.render_preview(
                state_sha256=detail["state_sha256"],
                configuration=config,
                content=detail["content"],
            )["bytes_sha256"])
        self.assertLess(cta_positions["below_text"]["y"], 944)
        alignment = universal_alignment_rectangle(detail["configuration"])
        self.assertEqual((alignment["x"], 944), (
            cta_positions["bottom_left"]["x"], cta_positions["bottom_left"]["y"],
        ))
        self.assertEqual(944, cta_positions["bottom_right"]["y"])
        self.assertEqual(
            alignment["x"] + alignment["width"] - cta_positions["bottom_right"]["width"],
            cta_positions["bottom_right"]["x"],
        )
        self.assertEqual(
            ["below_text", "bottom_left", "bottom_right"],
            universal_ad_catalog()["variation"]["cta_positions"],
        )
        self.assertEqual(3, len(cta_position_digests))

        anchored = copy.deepcopy(detail["configuration"])
        anchored["sticker"].update({
            "position": "cta", "width": 720, "object_scale": 1.5,
            "offset_right": 40, "offset_bottom": 30,
        })
        neutral = copy.deepcopy(anchored)
        neutral["sticker"].update({"offset_right": 0, "offset_bottom": 0})
        anchored_node = next(
            node for node in build_universal_template(anchored, detail["content"]).document["root"]["children"]
            if node["id"] == "sticker_object"
        )
        neutral_node = next(
            node for node in build_universal_template(neutral, detail["content"]).document["root"]["children"]
            if node["id"] == "sticker_object"
        )
        self.assertEqual(1080.0, anchored_node["props"]["width"])
        self.assertAlmostEqual(neutral_node["props"]["x"] - 40, anchored_node["props"]["x"])
        self.assertAlmostEqual(neutral_node["props"]["y"] - 30, anchored_node["props"]["y"])
        self.assertIn("right_edge", universal_ad_catalog()["variation"]["sticker_positions"])

    def test_each_sticker_control_changes_the_draft_render(self) -> None:
        detail = self.workspace.detail()
        detail = self.workspace.source_pexels(
            "sticker_object", base_sha256=detail["state_sha256"],
            query="red object", isolate=True,
        )
        base_configuration = copy.deepcopy(detail["configuration"])
        base_configuration["sticker"]["enabled"] = True
        baseline = self.workspace.render_preview(
            state_sha256=detail["state_sha256"], configuration=base_configuration,
            content=detail["content"],
        )
        baseline_node = next(
            node for node in build_universal_template(
                base_configuration, detail["content"],
            ).document["root"]["children"]
            if node["id"] == "sticker_object"
        )
        variants = {
            "rotation": 7,
            "width": 700,
            "object_scale": 1.25,
            "offset_right": 500,
            "offset_bottom": 500,
        }
        rendered_nodes = {}
        for setting, value in variants.items():
            config = copy.deepcopy(base_configuration)
            config["sticker"][setting] = value
            rendered = self.workspace.render_preview(
                state_sha256=detail["state_sha256"],
                configuration=config,
                content=detail["content"],
            )
            self.assertNotEqual(
                baseline["bytes_sha256"], rendered["bytes_sha256"],
                f"sticker.{setting} must visibly change the draft PNG",
            )
            rendered_nodes[setting] = next(
                node for node in build_universal_template(
                    config, detail["content"],
                ).document["root"]["children"]
                if node["id"] == "sticker_object"
            )

        self.assertEqual(7, rendered_nodes["rotation"]["props"]["rotation"])
        self.assertEqual(630, rendered_nodes["width"]["props"]["width"])
        self.assertEqual(375, rendered_nodes["object_scale"]["props"]["width"])
        self.assertEqual(
            baseline_node["props"]["x"] - 500,
            rendered_nodes["offset_right"]["props"]["x"],
        )
        self.assertEqual(
            baseline_node["props"]["y"] - 500,
            rendered_nodes["offset_bottom"]["props"]["y"],
        )

    def test_font_moods_render_ukrainian_and_benefit_check_marker(self) -> None:
        renderer = StudioRenderer()
        sample = "ІНВЕСТУВАТИ Ї Є Ґ і ї є ґ"
        rendered_digests = set()
        detail = self.workspace.detail()
        for family in FONT_FAMILIES:
            font = renderer._font(54, family, 700)
            missing = font.getmask(chr(0x10FFFF))
            for character in sample:
                if character.isspace():
                    continue
                glyph = font.getmask(character)
                self.assertFalse(
                    glyph.size == missing.size and bytes(glyph) == bytes(missing),
                    f"{family} does not render {character}",
                )
            config = copy.deepcopy(detail["configuration"])
            config["typography"]["font_family"] = family
            config["typography"]["benefits_font_family"] = family
            rendered = self.workspace.render_preview(
                state_sha256=detail["state_sha256"],
                configuration=config,
                content=detail["content"],
            )
            nodes = rendered["resolved"]["nodes"]
            self.assertEqual(family, nodes["hero_title"]["props"]["font_family"])
            self.assertEqual(family, nodes["bullet_1"]["props"]["font_family"])
            self.assertEqual("Inter", nodes["bullet_marker_1"]["props"]["font_family"])
            self.assertIsNotNone(nodes["bullet_marker_1"]["visible_bounds"])
            self.assertFalse(nodes["bullet_1"]["text_layout"]["overflow"])
            rendered_digests.add(rendered["bytes_sha256"])
        self.assertEqual(len(FONT_FAMILIES), len(rendered_digests))

    def test_owner_background_upload_selects_image_mode(self) -> None:
        detail = self.workspace.detail()
        config = copy.deepcopy(detail["configuration"])
        config["background"]["mode"] = "solid"
        detail = self.workspace.save_configuration(
            base_sha256=detail["state_sha256"], configuration=config, content=detail["content"],
        )
        uploaded = self.workspace.upload_asset(
            "background_image", base_sha256=detail["state_sha256"], mime_type="image/png",
            bytes_base64=base64.b64encode(_image_bytes()).decode(),
        )
        self.assertEqual("image", uploaded["configuration"]["background"]["mode"])
        background = next(item for item in uploaded["assets"] if item["slot"] == "background_image")
        self.assertEqual("owner_upload", background["source"]["origin"])

    def test_owner_logo_upload_is_rejected_and_natal_remains_enabled(self) -> None:
        detail = self.workspace.detail()
        config = copy.deepcopy(detail["configuration"])
        config["logo"]["enabled"] = False
        detail = self.workspace.save_configuration(
            base_sha256=detail["state_sha256"], configuration=config, content=detail["content"],
        )
        self.assertTrue(detail["configuration"]["logo"]["enabled"])
        with self.assertRaisesRegex(ValueError, "fixed Studio identity"):
            self.workspace.upload_asset(
                "logo", base_sha256=detail["state_sha256"], mime_type="image/png",
                bytes_base64=base64.b64encode(_image_bytes()).decode(),
            )
        rendered = self.workspace.render_preview(state_sha256=detail["state_sha256"])
        self.assertNotIn("logo_surface", rendered["resolved"]["nodes"])
        self.assertIn("logo", rendered["resolved"]["nodes"])

    def test_logo_position_width_remain_bounded_but_toggle_is_ignored(self) -> None:
        detail = self.workspace.detail()
        baseline = self.workspace.render_preview(state_sha256=detail["state_sha256"])
        top_left = copy.deepcopy(detail["configuration"])
        top_left["logo"].update({
            "position": "top_left", "width": 280, "background_enabled": False,
        })
        rendered = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=top_left,
            content=detail["content"],
        )
        self.assertNotEqual(baseline["bytes_sha256"], rendered["bytes_sha256"])
        nodes = rendered["resolved"]["nodes"]
        logo_box = nodes["logo"]["box"]
        self.assertNotIn("logo_surface", nodes)
        self.assertIsNotNone(nodes["logo"]["visible_bounds"])
        alignment = universal_alignment_rectangle(top_left)
        self.assertAlmostEqual(alignment["x"] / 1080, logo_box["x"])
        self.assertAlmostEqual(alignment["y"] / 1080, logo_box["y"])
        self.assertAlmostEqual(280 / 1080, logo_box["width"])
        self.assertGreaterEqual(
            nodes["hero_title"]["visible_bounds"]["y"],
            logo_box["y"] + logo_box["height"] + 23 / 1080,
        )

        with_background = copy.deepcopy(top_left)
        with_background["logo"].update({
            "background_enabled": True, "background_color": "#43BDD3",
        })
        background_render = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=with_background,
            content=detail["content"],
        )
        self.assertEqual(rendered["bytes_sha256"], background_render["bytes_sha256"])
        self.assertFalse(normalize_universal_config(with_background)["logo"]["background_enabled"])
        self.assertNotIn("logo_surface", background_render["resolved"]["nodes"])

        hidden = copy.deepcopy(top_left)
        hidden["logo"]["enabled"] = False
        hidden_render = self.workspace.render_preview(
            state_sha256=detail["state_sha256"],
            configuration=hidden,
            content=detail["content"],
        )
        self.assertNotIn("logo_surface", hidden_render["resolved"]["nodes"])
        self.assertIn("logo", hidden_render["resolved"]["nodes"])

    def test_image_sticker_logo_and_immutable_version(self) -> None:
        detail = self.workspace.detail()
        for slot in ("background_image",):
            data = _image_bytes()
            detail = self.workspace.upload_asset(
                slot, base_sha256=detail["state_sha256"], mime_type="image/png",
                bytes_base64=base64.b64encode(data).decode(),
            )
        detail = self.workspace.source_pexels(
            "sticker_object", base_sha256=detail["state_sha256"],
            query="red object", isolate=True,
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
        version = self.workspace.version_detail(1)
        self.assertEqual(detail["component_settings"], version["component_settings"])
        self.assertEqual(detail["configuration"], version["configuration"])
        self.assertRegex(version["version_sha256"], r"^[0-9a-f]{64}$")
        path = self.workspace.versions / "universal_ad_v1.json"
        tampered = json.loads(path.read_text())
        tampered["component_settings"]["components"][0]["settings"][0]["value"] = "solid"
        path.write_text(json.dumps(tampered))
        with self.assertRaisesRegex(ValueError, "version digest mismatch"):
            self.workspace.version_detail(1)

    def test_failed_atomic_approval_restores_pending_configuration(self) -> None:
        detail = self.workspace.detail()
        changed = copy.deepcopy(detail["configuration"])
        changed["background"]["color"] = "#123456"

        with self.assertRaisesRegex(ValueError, "change note"):
            self.workspace.approve_configuration(
                base_sha256=detail["state_sha256"], configuration=changed,
                content=detail["content"], change_note="",
            )

        restored = self.workspace.detail()
        self.assertEqual(detail["state_sha256"], restored["state_sha256"])
        self.assertEqual([], restored["versions"])

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
        self.assertEqual("photograph", sticker["source"]["media_type"])
        self.assertEqual(
            "ptw.pexels-photographic-object-evidence.v1",
            sticker["source"]["photographic_object_evidence"]["schema"],
        )
        self.assertTrue(detail["configuration"]["sticker"]["enabled"])
        self.workspace.render_preview(state_sha256=detail["state_sha256"])

    def test_direct_sticker_upload_is_rejected(self) -> None:
        detail = self.workspace.detail()
        pexels_call_count = len(self.workspace.pexels.calls)
        with self.assertRaisesRegex(ValueError, "non-photographic"):
            self.workspace.source_pexels(
                "sticker_object", base_sha256=detail["state_sha256"],
                query="3D compass icon", isolate=True,
            )
        self.assertEqual(pexels_call_count, len(self.workspace.pexels.calls))
        with self.assertRaisesRegex(ValueError, "Pexels photograph"):
            self.workspace.upload_asset(
                "sticker_object", base_sha256=detail["state_sha256"],
                mime_type="image/png",
                bytes_base64=base64.b64encode(_image_bytes()).decode(),
            )
        self.workspace._store_asset(
            "sticker_object", mime_type="image/png", data=_image_bytes(),
            source={"origin": "owner_upload"},
        )
        current = self.workspace.detail()
        sticker = next(
            item for item in current["assets"] if item["slot"] == "sticker_object"
        )
        self.assertFalse(sticker["available"])
        configuration = copy.deepcopy(current["configuration"])
        configuration["sticker"]["enabled"] = True
        with self.assertRaisesRegex(ValueError, "screened Pexels photograph"):
            self.workspace.render_preview(
                state_sha256=current["state_sha256"], configuration=configuration,
                content=current["content"],
            )

    def test_template_builder_keeps_optional_roles_mapped_when_omitted(self) -> None:
        template = build_universal_template(DEFAULT_CONFIG, DEFAULT_CONTENT)
        self.assertEqual(set(SEMANTIC_ROLES), set(template.document["semantic_roles"]))
        self.assertEqual("approved", template.document["status"])
        self.assertEqual([], template.document["provenance"]["reference_ids"])
        sticker = next(
            node for node in template.document["root"]["children"]
            if node["id"] == "sticker_object"
        )
        logo = next(
            node for node in template.document["root"]["children"]
            if node["id"] == "logo"
        )
        self.assertEqual(["sticker_object"], template.document["semantic_roles"]["sticker"])
        self.assertEqual(["logo"], template.document["semantic_roles"]["logo"])
        self.assertEqual("#FFFFFF", sticker["props"]["alpha_outline_color"])
        self.assertEqual(0.06, sticker["props"]["alpha_outline_width_ratio"])
        self.assertEqual(10, logo["props"]["z_index"])

@unittest.skipUnless(HAS_PILLOW and HAS_FASTAPI, "FastAPI and Pillow are required")
class UniversalStudioApiTests(unittest.TestCase):
    def test_loopback_app_serves_every_visible_owner_destination(self) -> None:
        from fastapi.testclient import TestClient
        from validation_pipeline.studio_local_api import create_app

        headers = {
            "Authorization": "Bearer e2e-owner-token",
            "X-Firebase-AppCheck": "e2e-app-check",
        }
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {
            "STUDIO_WORKSPACE_PATH": temporary,
            "LOCAL_BRIEF_PATH": str(Path(temporary) / "briefs"),
            "PEXELS_API_KEY": "",
        }, clear=False):
            with TestClient(create_app()) as client:
                self.assertEqual(401, client.get("/api/v1/projects").status_code)
                projects = client.get("/api/v1/projects?limit=100", headers=headers)
                self.assertEqual(200, projects.status_code, projects.text)
                self.assertEqual([], projects.json()["items"])
                self.assertEqual([], client.get("/api/v1/briefs?limit=100", headers=headers).json()["items"])
                self.assertEqual(404, client.get("/api/v1/posts", headers=headers).status_code)
                self.assertEqual(404, client.get("/api/v1/learning-summary", headers=headers).status_code)
                self.assertEqual(404, client.get("/api/v1/studio", headers=headers).status_code)
                templates = client.get("/api/v1/studio/templates", headers=headers)
                self.assertEqual(200, templates.status_code, templates.text)
                self.assertEqual(
                    {"universal_ad", "phone_metrics"},
                    {item["template_id"] for item in templates.json()["items"]},
                )
                self.assertEqual(404, client.get("/api/v1/studio/tune", headers=headers).status_code)

    def test_loopback_phone_screen_generation_is_authenticated_and_bounded(self) -> None:
        from fastapi.testclient import TestClient
        from validation_pipeline.studio_local_api import create_app

        class ImageProvider:
            def __init__(self) -> None:
                self.prompts: list[str] = []
                self.references: list[bytes | None] = []

            def generate(self, prompt: str, *, reference_image: bytes | None = None) -> dict:
                self.prompts.append(prompt)
                self.references.append(reference_image)
                return {
                    "bytes": _image_bytes(object_on_white=len(self.prompts) > 1),
                    "mime_type": "image/png",
                    "source": {
                        "origin": "openai_image_api", "provider": "openai",
                        "model": "fake-image-model",
                        "text_in_screen": "prohibited_by_prompt",
                    },
                }

        headers = {
            "Authorization": "Bearer e2e-owner-token",
            "X-Firebase-AppCheck": "e2e-app-check",
        }
        provider = ImageProvider()
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {
            "STUDIO_WORKSPACE_PATH": temporary,
            "LOCAL_BRIEF_PATH": str(Path(temporary) / "briefs"),
            "PEXELS_API_KEY": "",
            "OPENAI_API_KEY": "",
        }, clear=False):
            from validation_pipeline.local_brief_store import LocalBriefStore
            from validation_pipeline.local_briefs import LocalBriefService

            class StructuredProvider:
                def call(self, **request):
                    self.request = request
                    defaults = request["input_payload"]["template_defaults"]
                    return {
                        "response": {
                            "configuration": defaults["configuration"],
                            "content": defaults["content"],
                            "visual_direction": "Folded cobalt glass with one warm lime sphere",
                        },
                        "invocation": {"provider": "test", "model": "test-studio"},
                    }

            store = LocalBriefStore(Path(temporary) / "briefs")
            structured = StructuredProvider()
            brief_service = LocalBriefService(
                store=store, provider=structured,
                repository_root=Path(__file__).resolve().parents[2],
            )
            project, brief, _created = brief_service.create_brief(
                request_id="01900000-0000-7000-8000-000000000031",
                raw_idea="A focused owner idea", required_language="en",
                requested_by="test",
            )
            document = {
                "schema_version": 1, "language": "en", "product": "Focused product",
                "target_audience": "Independent founders", "main_pain": "Lost time",
                "promise": "Make the next decision clearer", "key_benefits": [
                    "One next step", "Less busywork", "Clear boundaries",
                ], "cta": "Start", "trust_strategy": "Show the process",
                "offer": "A guided first setup",
            }
            store.append("briefs", brief["brief_id"], {
                **brief, "status": "completed", "document": document,
                "document_sha256": "a" * 64, "approved": False,
            })
            with TestClient(create_app(
                brief_service=brief_service, phone_screen_image_provider=provider,
            )) as client:
                approval = client.post(
                    f'/api/v1/briefs/{brief["brief_id"]}/approve', headers=headers,
                    json={"honor_confirmed": True, "template_id": "phone_metrics"},
                )
                self.assertEqual(202, approval.status_code, approval.text)
                creative_id = approval.json()["creative"]["creative_id"]
                creative_path = (
                    f'/api/v1/studio/projects/{project["project_id"]}/creatives/{creative_id}'
                )
                phone = client.get(creative_path, headers=headers).json()
                self.assertEqual("draft", phone["status"])
                self.assertEqual("completed", phone["generation"]["phone_image"]["status"])
                self.assertEqual(1, len(provider.prompts))
                self.assertEqual([None], provider.references)
                wrong_project_path = (
                    f"/api/v1/studio/projects/01900000-0000-7000-8000-000000000099/"
                    f"creatives/{creative_id}"
                )
                self.assertEqual(404, client.get(wrong_project_path, headers=headers).status_code)
                self.assertEqual(404, client.post(
                    f"{wrong_project_path}/configuration", headers=headers, json={
                        "base_sha256": phone["state_sha256"],
                        "configuration": phone["configuration"], "content": phone["content"],
                    },
                ).status_code)
                self.assertEqual(404, client.post(
                    f"{wrong_project_path}/component-settings", headers=headers,
                    json={"state_sha256": phone["state_sha256"]},
                ).status_code)
                request = {
                    "base_sha256": phone["state_sha256"],
                    "visual_direction": "Preserve the form and improve material detail.",
                    "enhance_current": True,
                }
                self.assertEqual(
                    401,
                    client.post(f"{creative_path}/phone-screen/generate", json=request).status_code,
                )
                enhanced = client.post(
                    f"{creative_path}/phone-screen/generate", headers=headers, json=request,
                )
                self.assertEqual(200, enhanced.status_code, enhanced.text)
                self.assertTrue(enhanced.json()["phone_screen_generation_available"])
                self.assertEqual(_image_bytes(), provider.references[1])
                screen = next(
                    item for item in phone["assets"]
                    if item["slot"] == "phone_screen"
                )
                self.assertTrue(screen["available"])
                enhanced_screen = next(
                    item for item in enhanced.json()["assets"]
                    if item["slot"] == "phone_screen"
                )
                self.assertEqual(
                    screen["sha256"],
                    enhanced_screen["source"]["reference_asset_sha256"],
                )
                self.assertEqual(2, len(enhanced.json()["phone_screen_history"]))
                history_image_path = (
                    f'{creative_path}/phone-screen/history/{screen["sha256"]}'
                )
                self.assertEqual(401, client.get(history_image_path).status_code)
                history_image = client.get(history_image_path, headers=headers)
                self.assertEqual(200, history_image.status_code, history_image.text)
                self.assertEqual(_image_bytes(), history_image.content)
                self.assertEqual("private, no-store", history_image.headers["cache-control"])
                self.assertEqual(f'"{screen["sha256"]}"', history_image.headers["etag"])
                selected = client.post(
                    f"{creative_path}/phone-screen/select", headers=headers, json={
                        "base_sha256": enhanced.json()["state_sha256"],
                        "sha256": screen["sha256"],
                    },
                )
                self.assertEqual(200, selected.status_code, selected.text)
                self.assertEqual(
                    [False, True],
                    [item["selected"] for item in selected.json()["phone_screen_history"]],
                )
                self.assertEqual(
                    screen["sha256"],
                    next(
                        item for item in selected.json()["assets"]
                        if item["slot"] == "phone_screen"
                    )["sha256"],
                )
                invalid_selection = client.post(
                    f"{creative_path}/phone-screen/select", headers=headers, json={
                        "base_sha256": selected.json()["state_sha256"],
                        "sha256": screen["sha256"],
                        "unexpected": True,
                    },
                )
                self.assertEqual(400, invalid_selection.status_code)
                invalid = client.post(
                    f"{creative_path}/phone-screen/generate", headers=headers, json={
                        "base_sha256": enhanced.json()["state_sha256"],
                        "visual_direction": "Preserve the form and improve material detail.",
                        "enhance_current": "yes",
                    },
                )
                self.assertEqual(400, invalid.status_code)
