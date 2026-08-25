from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import importlib.util
import json
import shutil
import subprocess
import unittest

from commander.ids import new_uuid7
from validation_pipeline.studio import (
    ADS_SOURCE,
    COLOR_SOURCE,
    DEFAULT_GUARDS,
    PLACEMENTS,
    StudioRecipeV1,
    StudioRecipeV2,
    StudioRenderer,
    build_manifest,
    build_sample_documents,
    inspect_media,
    tool_catalog,
    validate_brand_kit,
    validate_recipe_revision_diff,
    validate_template,
    resolve_template_v2,
)


PROJECT_ID = "018f07ea-7f20-7000-8000-000000000001"
BRIEF_ID = "018f07ea-7f20-7000-8000-000000000002"
KIT_ID = "018f07ea-7f20-7000-8000-000000000003"
OFFER_ID = "018f07ea-7f20-7000-8000-000000000004"
CTA_ID = "018f07ea-7f20-7000-8000-000000000005"
VIDEO_ID = "018f07ea-7f20-7000-8000-000000000006"


def brief():
    return {"offer": "Free first consultation", "cta": "Book a call"}


def recipe(**changes):
    value = {
        "schema_version": 1,
        "parent_recipe_id": None,
        "placement_tool_id": "studio.placement.instagram.feed_square.v1",
        "duration_seconds": None,
        "frame_rate": None,
        "tools": [
            {
                "instance_id": OFFER_ID, "tool_id": "studio.frame.offer.v1",
                "frame": {"x": .08, "y": .68, "width": .84, "height": .1},
                "z_index": 1, "params": {"text": "Free first consultation", "color": "#FFFFFF"},
                "timeline": None, "source_asset_ids": [],
            },
            {
                "instance_id": CTA_ID, "tool_id": "studio.frame.cta.v1",
                "frame": {"x": .08, "y": .82, "width": .5, "height": .1},
                "z_index": 2, "params": {"text": "Book a call", "color": "#FFFFFF"},
                "timeline": None, "source_asset_ids": [],
            },
        ],
        "strategy_ids": ["studio.strategy.one_message.v1"],
        "validation_ids": list(DEFAULT_GUARDS),
        "source_reference_ids": [COLOR_SOURCE, ADS_SOURCE],
    }
    value.update(changes)
    return value


class StudioContractTests(unittest.TestCase):
    def test_catalog_has_immutable_ids_and_complete_registry_fields(self) -> None:
        catalog = tool_catalog()
        ids = [item["tool_id"] for item in catalog["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(PLACEMENTS), {item for item in ids if ".placement." in item})
        self.assertIn("studio.color.ratio_60_30_10.v1", ids)
        for item in catalog["items"]:
            self.assertEqual(
                {
                    "tool_id", "kind", "label", "parameter_schema", "supported_placements",
                    "renderer_handler", "defaults", "bounds", "source_refs", "deprecated",
                },
                set(item),
            )

    def test_brand_kit_requires_distinct_four_to_six_hex_colors(self) -> None:
        value = validate_brand_kit({
            "name": "Project kit", "colors": ["#101010", "#FFFFFF", "#4466AA", "#F0C040"],
            "fonts": ["Inter"], "tone_notes": "Direct and calm", "logo_source_asset_id": None,
        })
        self.assertEqual("#101010", value["colors"][0])
        with self.assertRaisesRegex(ValueError, "four to six"):
            validate_brand_kit({**value, "colors": ["#000000"]})

    def test_recipe_is_canonical_and_preserves_exact_offer_and_cta(self) -> None:
        first = StudioRecipeV1.from_dict(
            recipe(), project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=brief()
        )
        second = StudioRecipeV1.from_dict(
            recipe(), project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=brief()
        )
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(1080, first.value["width"])
        invalid = recipe()
        invalid["tools"][0]["params"]["text"] = "Discounted consultation"
        with self.assertRaisesRegex(ValueError, "exact Product Brief"):
            StudioRecipeV1.from_dict(
                invalid, project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=brief()
            )

    def test_recipe_rejects_unknown_tools_bounds_motion_mismatch_and_fabricated_proof(self) -> None:
        unknown = recipe(); unknown["tools"][0]["tool_id"] = "studio.frame.unknown.v1"
        outside = recipe(); outside["tools"][0]["frame"]["x"] = .9
        motion = recipe(); motion["tools"][0]["tool_id"] = "studio.motion.pan_zoom.v1"
        proof = recipe(); proof["tools"][0]["params"]["note"] = "Trusted by 5000 customers"
        for value, pattern in (
            (unknown, "unknown or unavailable"), (outside, "inside the canvas"),
            (motion, "not compatible"), (proof, "unsupported proof"),
        ):
            with self.subTest(pattern=pattern), self.assertRaisesRegex(ValueError, pattern):
                StudioRecipeV1.from_dict(
                    value, project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=brief()
                )

    def test_template_preserves_tools_but_uses_offer_and_cta_placeholders(self) -> None:
        source = recipe()
        source["tools"][0]["params"]["text"] = "{{offer}}"
        source["tools"][1]["params"]["text"] = "{{cta}}"
        value = validate_template({
            "schema_version": 1, "placement_tool_id": source["placement_tool_id"],
            "duration_seconds": None, "frame_rate": None, "tools": source["tools"],
            "strategy_ids": source["strategy_ids"],
        })
        self.assertEqual("{{offer}}", value["tools"][0]["params"]["text"])
        self.assertEqual("{{cta}}", value["tools"][1]["params"]["text"])
        invalid = json.loads(json.dumps(value))
        invalid["tools"][0]["params"]["text"] = "A fixed old offer"
        with self.assertRaisesRegex(ValueError, "placeholders"):
            validate_template(invalid)

    def test_motion_timeline_and_important_frame_safe_zone_are_bounded(self) -> None:
        outside = recipe()
        outside["tools"][1]["frame"] = {"x": .01, "y": .82, "width": .5, "height": .1}
        with self.assertRaisesRegex(ValueError, "safe zone"):
            StudioRecipeV1.from_dict(
                outside, project_id=PROJECT_ID, brief_id=BRIEF_ID,
                brand_kit_id=KIT_ID, brief=brief(),
            )
        timed = recipe(
            placement_tool_id="studio.placement.instagram.reel_vertical.v1",
            duration_seconds=3, frame_rate=30,
        )
        timed["tools"][0]["timeline"] = {"start": 0, "end": 4}
        with self.assertRaisesRegex(ValueError, "motion duration"):
            StudioRecipeV1.from_dict(
                timed, project_id=PROJECT_ID, brief_id=BRIEF_ID,
                brand_kit_id=KIT_ID, brief=brief(),
            )

    def test_five_v2_samples_have_typed_bindings_truthful_alt_and_resolve_fresh_ids(self) -> None:
        angles = ("emotional", "practical", "curiosity", "authority", "problem_first")
        approved = {
            "offer": "First consultation free", "cta": "Book a call",
            "trust_strategy": "Transparent process with no invented proof.",
            "key_benefits": ["Personal question", "Exact inputs", "Clear orientation"],
        }
        creatives = [{
            "creative_id": new_uuid7(), "angle": angle,
            "hook": f"Original {angle}", "primary_text": f"Share-ready {angle}. First consultation free.",
            "image_description": f"Original {angle} photograph",
        } for angle in angles]
        media = {angle: new_uuid7() for angle in angles}
        logo = new_uuid7()
        items = build_sample_documents(
            brief=approved, creatives=creatives, media_by_angle=media, logo_source_asset_id=logo,
        )
        self.assertEqual(list(angles), [item["angle"] for item in items])
        for item in items:
            template = validate_template(item["template"])
            contract = StudioRecipeV2.from_dict(
                item["recipe"], project_id=PROJECT_ID, brief_id=BRIEF_ID,
                brand_kit_id=KIT_ID, brief=approved,
            )
            self.assertFalse(any(frame["source_asset_ids"] for frame in template["frames"]))
            self.assertEqual(media[item["angle"]], next(
                frame["source_asset_ids"][0] for frame in contract.value["frames"]
                if frame["tool_id"] == "studio.frame.media.v1"
            ))
            if item["angle"] == "curiosity":
                self.assertIn("Абстрактний", contract.value["share"]["alt_text"])
            creative = next(value for value in creatives if value["angle"] == item["angle"])
            resolved_item = resolve_template_v2(
                template, brief=approved, creative=creative,
                photo_source_asset_id=media[item["angle"]], logo_source_asset_id=logo,
            )
            self.assertFalse(any(
                "{{" in str(frame["params"].get("text") or "") for frame in resolved_item["frames"]
            ))
            self.assertEqual(creative["primary_text"], resolved_item["share"]["caption"])
        selected = items[0]
        template = validate_template(selected["template"])
        resolved = resolve_template_v2(
            template, brief=approved, creative=creatives[0],
            photo_source_asset_id=media["emotional"], logo_source_asset_id=logo,
        )
        self.assertEqual("Original emotional", next(
            frame["params"]["text"] for frame in resolved["frames"]
            if frame["tool_id"] == "studio.frame.headline.v1"
        ))
        self.assertTrue(set(frame["instance_id"] for frame in template["frames"]).isdisjoint(
            frame["instance_id"] for frame in resolved["frames"]
        ))
        image_description_template = json.loads(json.dumps(template))
        headline_binding = next(
            binding for binding in image_description_template["bindings"].values()
            if binding["source"] == "creative.hook"
        )
        headline_binding["source"] = "creative.image_description"
        image_description = resolve_template_v2(
            validate_template(image_description_template), brief=approved, creative=creatives[0],
            photo_source_asset_id=media["emotional"], logo_source_asset_id=logo,
        )
        self.assertEqual("Original emotional photograph", next(
            frame["params"]["text"] for frame in image_description["frames"]
            if frame["tool_id"] == "studio.frame.headline.v1"
        ))

    def test_selected_component_diff_rejects_changes_outside_target(self) -> None:
        approved = {"offer": "Free first consultation", "cta": "Book a call"}
        base = {
            "schema_version": 2, "parent_recipe_id": None,
            "placement_tool_id": "studio.placement.instagram.feed_square.v1",
            "duration_seconds": None, "frame_rate": None,
            "frames": recipe()["tools"], "modifiers": [],
            "strategy_ids": ["studio.strategy.one_message.v1"],
            "validation_ids": list(DEFAULT_GUARDS), "source_reference_ids": [COLOR_SOURCE, ADS_SOURCE],
            "share": {"caption": "A clear caption", "alt_text": "A clear visual"},
        }
        contract = StudioRecipeV2.from_dict(
            base, project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=approved,
        )
        proposed = json.loads(json.dumps({key: contract.value[key] for key in (
            "schema_version", "parent_recipe_id", "placement_tool_id", "duration_seconds", "frame_rate",
            "frames", "modifiers", "strategy_ids", "validation_ids", "source_reference_ids", "share",
        )}))
        proposed["frames"][0]["params"]["font_size"] = 32
        patch = validate_recipe_revision_diff(contract.value, proposed, target_instance_id=OFFER_ID)
        self.assertEqual(f"frames/{OFFER_ID}", patch[0]["target"])
        proposed["share"]["caption"] = "Changed outside target"
        with self.assertRaisesRegex(ValueError, "outside"):
            validate_recipe_revision_diff(contract.value, proposed, target_instance_id=OFFER_ID)
        malformed = json.loads(json.dumps(proposed))
        malformed["frames"] = ["not-an-object"]
        with self.assertRaisesRegex(ValueError, "frames must contain objects"):
            validate_recipe_revision_diff(contract.value, malformed, target_instance_id=None)


@unittest.skipUnless(importlib.util.find_spec("PIL") is not None, "Pillow is required")
class StudioRenderTests(unittest.TestCase):
    def test_rgb_shape_composite_keeps_following_cta_text_on_live_canvas(self) -> None:
        value = recipe()
        value["tools"].insert(1, {
            "instance_id": "018f07ea-7f20-7000-8000-000000000008",
            "tool_id": "studio.frame.shape.v1",
            "frame": {"x": .05, "y": .81, "width": .58, "height": .13},
            "z_index": 2,
            "params": {"background": "#43BDD3", "opacity": 1, "radius": 24},
            "timeline": None, "source_asset_ids": [],
        })
        value["tools"][2]["z_index"] = 3
        value["tools"][2]["params"]["color"] = "#0C0E12"
        contract = StudioRecipeV1.from_dict(
            value, project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=brief()
        )
        kit = {
            "brand_kit_id": KIT_ID,
            "document": {"colors": ["#101010", "#FFFFFF", "#4466AA", "#F0C040"], "fonts": ["Inter"]},
        }
        canvas = StudioRenderer(font_path=Path("natal/assets/inter.ttf"))._canvas(
            contract.value, kit, {},
        )
        # The cyan button has no near-black pixels of its own.  A meaningful
        # population inside the CTA frame proves the label survived the shape
        # composite rather than accepting a blank share button.
        dark_pixels = sum(
            1 for red, green, blue in canvas.crop((86, 886, 626, 994)).getdata()
            if red < 80 and green < 80 and blue < 80
        )
        self.assertGreater(dark_pixels, 50)

    def test_image_inspection_render_metadata_and_manifest_agree(self) -> None:
        from PIL import Image
        source = BytesIO(); Image.new("RGB", (256, 256), "#445566").save(source, "PNG")
        inspected = inspect_media(source.getvalue(), "image/png")
        self.assertEqual((256, 256), (inspected["width"], inspected["height"]))
        contract = StudioRecipeV1.from_dict(
            recipe(), project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=brief()
        )
        kit = {
            "brand_kit_id": KIT_ID,
            "document": {"colors": ["#101010", "#FFFFFF", "#4466AA", "#F0C040"]},
        }
        rendered = StudioRenderer(font_path=Path("/missing/font.ttf")).render(
            recipe_id=BRIEF_ID, recipe_digest=contract.digest, recipe=contract.value,
            brand_kit=kit, assets={},
        )
        digest = hashlib.sha256(rendered["bytes"]).hexdigest()
        with Image.open(BytesIO(rendered["bytes"])) as output:
            embedded = json.loads(output.getexif()[0x9286])
        self.assertEqual(contract.digest, embedded["recipe_sha256"])
        manifest = build_manifest(
            render_id=PROJECT_ID, recipe_id=BRIEF_ID, recipe_digest=contract.digest,
            recipe=contract.value, brand_kit=kit, assets={}, rendered=rendered,
        )
        self.assertEqual(digest, manifest["output"]["bytes_sha256"])
        self.assertEqual(set(embedded["tool_ids"]), {
            contract.value["placement_tool_id"],
            *[item["tool_id"] for item in contract.value["tools"]],
            *contract.value["strategy_ids"], *contract.value["validation_ids"],
        })

    def test_duotone_effect_changes_the_bound_media_frame_deterministically(self) -> None:
        from PIL import Image
        source = BytesIO(); Image.new("RGB", (256, 256), "#808080").save(source, "PNG")
        value = recipe()
        value["tools"].insert(0, {
            "instance_id": VIDEO_ID, "tool_id": "studio.frame.media.v1",
            "frame": {"x": 0, "y": 0, "width": 1, "height": .62}, "z_index": 0,
            "params": {}, "timeline": None, "source_asset_ids": [VIDEO_ID],
        })
        value["tools"].append({
            "instance_id": "018f07ea-7f20-7000-8000-000000000007",
            "tool_id": "studio.effect.duotone.v1",
            "frame": {"x": 0, "y": 0, "width": 1, "height": 1}, "z_index": 3,
            "params": {}, "timeline": None, "source_asset_ids": [],
        })
        contract = StudioRecipeV1.from_dict(
            value, project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=brief()
        )
        kit = {"brand_kit_id": KIT_ID, "document": {"colors": ["#101010", "#FFFFFF", "#4466AA", "#F0C040"], "fonts": ["Inter"]}}
        asset = {"bytes": source.getvalue(), "mime_type": "image/png"}
        rendered = StudioRenderer(font_path=Path("/missing/font.ttf")).render(
            recipe_id=BRIEF_ID, recipe_digest=contract.digest, recipe=contract.value,
            brand_kit=kit, assets={VIDEO_ID: asset},
        )
        with Image.open(BytesIO(rendered["bytes"])) as output:
            pixel = output.getpixel((100, 100))
        self.assertNotEqual((128, 128, 128), pixel)
        self.assertGreater(pixel[2], pixel[0])

    def test_declared_image_mime_must_match_bytes(self) -> None:
        from PIL import Image
        data = BytesIO(); Image.new("RGB", (64, 64)).save(data, "PNG")
        with self.assertRaisesRegex(ValueError, "MIME"):
            inspect_media(data.getvalue(), "image/jpeg")
        with self.assertRaisesRegex(ValueError, "decoded"):
            inspect_media(b"not-an-image", "image/png")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            inspect_media(b"text", "text/plain")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
    def test_motion_render_is_deterministic_h264_and_embeds_manifest(self) -> None:
        value = recipe(
            placement_tool_id="studio.placement.instagram.story_vertical.v1",
            duration_seconds=3,
            frame_rate=24,
        )
        contract = StudioRecipeV1.from_dict(
            value, project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=brief()
        )
        kit = {
            "brand_kit_id": KIT_ID,
            "document": {"colors": ["#101010", "#FFFFFF", "#4466AA", "#F0C040"]},
        }
        renderer = StudioRenderer(font_path=Path("/missing/font.ttf"))
        first = renderer.render(
            recipe_id=BRIEF_ID, recipe_digest=contract.digest, recipe=contract.value,
            brand_kit=kit, assets={},
        )
        second = renderer.render(
            recipe_id=BRIEF_ID, recipe_digest=contract.digest, recipe=contract.value,
            brand_kit=kit, assets={},
        )
        self.assertEqual(first["bytes"], second["bytes"])
        with TemporaryDirectory() as root:
            path = Path(root) / "render.mp4"; path.write_bytes(first["bytes"])
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height:format_tags=comment", "-of", "json", str(path)],
                capture_output=True, text=True, check=True,
            )
        metadata = json.loads(result.stdout)
        self.assertEqual("h264", metadata["streams"][0]["codec_name"])
        self.assertEqual((1080, 1920), (metadata["streams"][0]["width"], metadata["streams"][0]["height"]))
        embedded = json.loads(metadata["format"]["tags"]["comment"])
        self.assertEqual(contract.digest, embedded["recipe_sha256"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
    def test_uploaded_video_trim_audio_and_caption_are_rendered(self) -> None:
        with TemporaryDirectory() as root:
            source_path = Path(root) / "source.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=#4466AA:s=160x160:r=24:d=1",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-shortest",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-threads", "1", "-c:a", "aac", str(source_path),
            ], check=True)
            source_bytes = source_path.read_bytes()
        inspected = inspect_media(source_bytes, "video/mp4")
        self.assertEqual("h264", inspected["codec"])
        value = recipe(
            placement_tool_id="studio.placement.tiktok.vertical_video.v1",
            duration_seconds=3, frame_rate=24,
        )
        value["tools"].insert(0, {
            "instance_id": VIDEO_ID, "tool_id": "studio.frame.media.v1",
            "frame": {"x": 0, "y": 0, "width": 1, "height": .62}, "z_index": 0,
            "params": {"trim_start_seconds": .1, "original_audio": "preserve"},
            "timeline": {"start": 0, "end": 3}, "source_asset_ids": [VIDEO_ID],
        })
        value["tools"].append({
            "instance_id": "018f07ea-7f20-7000-8000-000000000007",
            "tool_id": "studio.motion.ugc_caption.v1",
            "frame": {"x": .08, "y": .55, "width": .84, "height": .1}, "z_index": 3,
            "params": {"text": "A clear first-second caption", "color": "#FFFFFF", "font_size": 46},
            "timeline": {"start": 0, "end": 3}, "source_asset_ids": [],
        })
        contract = StudioRecipeV1.from_dict(
            value, project_id=PROJECT_ID, brief_id=BRIEF_ID, brand_kit_id=KIT_ID, brief=brief()
        )
        kit = {"brand_kit_id": KIT_ID, "document": {"colors": ["#101010", "#FFFFFF", "#4466AA", "#F0C040"]}}
        rendered = StudioRenderer(font_path=Path("/missing/font.ttf")).render(
            recipe_id=BRIEF_ID, recipe_digest=contract.digest, recipe=contract.value,
            brand_kit=kit, assets={VIDEO_ID: {"bytes": source_bytes, "mime_type": "video/mp4", **inspected}},
        )
        with TemporaryDirectory() as root:
            output_path = Path(root) / "output.mp4"; output_path.write_bytes(rendered["bytes"])
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(output_path)],
                capture_output=True, text=True, check=True,
            )
        self.assertEqual({"video", "audio"}, {item["codec_type"] for item in json.loads(result.stdout)["streams"]})


if __name__ == "__main__":
    unittest.main()
