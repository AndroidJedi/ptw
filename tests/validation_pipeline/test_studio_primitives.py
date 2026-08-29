from __future__ import annotations

from io import BytesIO
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

from validation_pipeline.studio import StudioRenderer
from validation_pipeline.studio_primitives import (
    PRIMITIVE_TYPES, PrimitiveTemplate, PrimitiveTemplateEditor,
    apply_primitive_operations, load_primitive_template, primitive_catalog,
)
from validation_pipeline.verify_studio_primitives import (
    BENCHMARK_CONTENT, BENCHMARK_DIRECTORY, benchmark_assets, render_benchmarks,
)


PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None


def _template(
    *, children: list[dict] | None = None, status: str = "draft",
    semantic_roles: dict[str, list[str]] | None = None,
    assets: dict | None = None,
) -> PrimitiveTemplate:
    return PrimitiveTemplate.from_dict({
        "schema": "ptw.studio.primitive-template.v1",
        "template_id": "test_template",
        "template_type": "test_square",
        "version": 1,
        "status": status,
        "root": {
            "id": "canvas", "type": "frame",
            "props": {"width": 100, "height": 100, "background_color": "#FFFFFF"},
            "children": children or [{
                "id": "headline", "type": "text",
                "props": {
                    "position": "absolute", "x": 8, "y": 8, "width": 84, "height": 30,
                    "font_size": 20, "min_font_size": 8, "text": "Fallback",
                },
                "bindings": [
                    {"target": "text", "source": "content.headline", "required": True},
                ],
            }],
        },
        "semantic_roles": semantic_roles or {"headline": ["headline"]},
        "assets": assets or {},
        "rules": [],
        "provenance": {
            "base_template_id": None, "base_version": None, "base_sha256": None,
            "reference_ids": ["unit-test"], "change_note": "Unit fixture",
        },
    })


class PrimitiveStudioContractTests(unittest.TestCase):
    def test_catalog_and_benchmark_templates_use_one_finite_vocabulary(self) -> None:
        catalog = primitive_catalog()
        self.assertEqual(list(PRIMITIVE_TYPES), catalog["primitive_types"])
        self.assertEqual(11, len(catalog["items"]))
        self.assertEqual(64, len(catalog["sha256"]))
        for item in catalog["items"]:
            self.assertIn("position", item["properties"])
            self.assertIn("z_index", item["properties"])
            self.assertIn("opacity", item["properties"])

        templates = [
            load_primitive_template(path)
            for path in sorted(BENCHMARK_DIRECTORY.glob("*_v1.json"))
        ]
        self.assertEqual(2, len(templates))
        for template in templates:
            self.assertEqual(template.digest, PrimitiveTemplate.from_json(template.to_json()).digest)
            node_types = {
                node["type"]
                for node in self._nodes(template.document["root"])
            }
            self.assertTrue(node_types <= set(PRIMITIVE_TYPES))
        self.assertNotEqual(templates[0].document["root"], templates[1].document["root"])

    @staticmethod
    def _nodes(node):
        yield node
        for child in node["children"]:
            yield from PrimitiveStudioContractTests._nodes(child)

    def test_editor_operations_are_configuration_only_and_do_not_mutate_base(self) -> None:
        base = _template(status="approved")
        base_document = copy.deepcopy(base.document)
        editor = PrimitiveTemplateEditor(base)
        editor.set_property("headline", "font_size", 30)
        editor.bind_role("hook", "headline")
        editor.bind_property("headline", "color", "content.color")
        editor.set_responsive_override(
            "headline", min_width=320, max_width=420, props={"font_size": 24},
        )
        editor.duplicate_subtree("headline", "headline-copy", parent_id="canvas")
        editor.wrap_nodes(["headline", "headline-copy"], {
            "id": "headline-group", "type": "stack",
            "props": {
                "position": "absolute", "x": 0, "y": 0,
                "width": 100, "height": 70,
            },
        })
        editor.reorder_node("headline-copy", 0)
        editor.move_node("headline-copy", "canvas", 0)
        editor.unwrap_node("headline-group")
        editor.unbind_property("headline", "color")
        editor.unbind_role("hook", "headline")
        draft = editor.document(change_note="Configuration-only internal edit")

        self.assertEqual(base_document, base.document)
        self.assertEqual(2, draft.document["version"])
        self.assertEqual("draft", draft.document["status"])
        self.assertEqual(base.digest, draft.document["provenance"]["base_sha256"])
        self.assertEqual(30.0, next(
            node for node in self._nodes(draft.document["root"]) if node["id"] == "headline"
        )["props"]["font_size"])

    def test_constraints_locks_operation_files_and_version_save_are_fail_closed(self) -> None:
        base = _template()
        editor = PrimitiveTemplateEditor(base)
        editor.set_constraint("headline", "font_size", minimum=16, maximum=32, locked=True)
        with self.assertRaisesRegex(ValueError, "locked"):
            editor.set_property("headline", "font_size", 24)
        with self.assertRaisesRegex(ValueError, "unknown internal Studio operation"):
            editor.apply_operations([{"op": "write_renderer_source"}])

        changed = apply_primitive_operations(base, [{
            "op": "set_property", "node_id": "headline", "path": "letter_spacing", "value": 2,
        }], change_note="Tracking adjustment")
        self.assertNotEqual(base.digest, changed.digest)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "test_template_v1.json"
            saved = PrimitiveTemplateEditor(changed).save_version(path)
            self.assertEqual(saved.digest, load_primitive_template(path).digest)
            tampered = PrimitiveTemplateEditor(changed).set_property("headline", "font_size", 21)
            with self.assertRaises(FileExistsError):
                tampered.save_version(path)

    def test_every_primitive_serializes_in_one_tree(self) -> None:
        asset_declaration = {
            "kind": "image", "allowed_mime_types": ["image/png"], "required": True,
            "provenance": "Unit-test transparent image.",
        }
        common = {"position": "absolute", "width": 10, "height": 10}
        children = [
            {"id": "child-frame", "type": "frame", "props": {**common, "x": 0, "y": 0}},
            {"id": "child-container", "type": "container", "props": {**common, "x": 10, "y": 0}},
            {"id": "child-stack", "type": "stack", "props": {**common, "x": 20, "y": 0}},
            {"id": "child-text", "type": "text", "props": {**common, "x": 30, "y": 0, "text": "T"}},
            {"id": "child-image", "type": "image", "props": {**common, "x": 40, "y": 0, "asset": "alpha_asset"}},
            {"id": "child-button", "type": "button", "props": {**common, "x": 50, "y": 0, "label": "B"}},
            {"id": "child-icon", "type": "icon", "props": {**common, "x": 60, "y": 0, "glyph": "→"}},
            {"id": "child-shape", "type": "shape", "props": {**common, "x": 70, "y": 0, "fill": "#FF0000"}},
            {"id": "child-spacer", "type": "spacer", "props": {**common, "x": 80, "y": 0, "divider_color": "#000000"}},
            {"id": "child-list", "type": "list", "props": {**common, "x": 90, "y": 0, "repeat": 2}, "children": [
                {"id": "child-card", "type": "card", "props": {"width": "100%", "height": "100%", "background_color": "#00FF00"}},
            ]},
        ]
        template = _template(
            children=children, semantic_roles={"hero": ["child-image"]},
            assets={"alpha_asset": asset_declaration},
        )
        self.assertEqual(set(PRIMITIVE_TYPES), {node["type"] for node in self._nodes(template.document["root"])})
        if PIL_AVAILABLE:
            from PIL import Image

            output = BytesIO()
            Image.new("RGBA", (8, 8), (255, 215, 0, 180)).save(output, format="PNG")
            preview = StudioRenderer().render_preview(
                template, semantic_data={},
                assets={"alpha_asset": {"bytes": output.getvalue(), "mime_type": "image/png"}},
            )
            self.assertEqual((100, 100), (preview["width"], preview["height"]))

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required")
    def test_image_alpha_outline_follows_transparent_object_silhouette(self) -> None:
        from PIL import Image, ImageDraw

        source = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(source).ellipse((10, 10, 30, 30), fill="#D54232")
        output = BytesIO()
        source.save(output, format="PNG")
        template = _template(
            children=[{
                "id": "die-cut", "type": "image", "props": {
                    "position": "absolute", "x": 0, "y": 0,
                    "width": 40, "height": 40, "asset": "object",
                    "fit": "contain", "alpha_outline_color": "#0055FF",
                    "alpha_outline_width": 4,
                    "alpha_outline_shadow_color": "#00000066",
                    "alpha_outline_shadow_blur": 2, "alpha_outline_shadow_y": 1,
                },
            }],
            semantic_roles={"hero": ["die-cut"]},
            assets={"object": {
                "kind": "image", "allowed_mime_types": ["image/png"],
                "required": True, "provenance": "Unit-test alpha object.",
            }},
        )
        preview = StudioRenderer().render_preview(
            template, semantic_data={},
            assets={"object": {"bytes": output.getvalue(), "mime_type": "image/png"}},
        )
        rendered = Image.open(BytesIO(preview["bytes"])).convert("RGB")
        self.assertGreater(rendered.getpixel((7, 20))[2], 200)
        self.assertGreater(rendered.getpixel((20, 20))[0], 180)
        edge = rendered.getpixel((5, 20))
        self.assertGreater(edge[2], edge[0])
        self.assertGreater(edge[0], 0)
        # The transition retains enough antialiasing to avoid a jagged edge,
        # without the broad feather that would read as a glow.
        outer_red = [rendered.getpixel((x, 20))[0] for x in range(0, 8)]
        self.assertGreaterEqual(len(set(outer_red)), 3)
        self.assertEqual(sorted(outer_red, reverse=True), outer_red)
        self.assertEqual((255, 255, 255), rendered.getpixel((0, 0)))
        props = preview["resolved"]["nodes"]["die-cut"]["props"]
        self.assertEqual("#00000066", props["alpha_outline_shadow_color"])
        self.assertEqual(2.0, props["alpha_outline_shadow_blur"])
        self.assertEqual(1.0, props["alpha_outline_shadow_y"])

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required")
    def test_ratio_outline_has_room_outside_an_edge_touching_subject(self) -> None:
        from PIL import Image, ImageDraw

        source = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(source).ellipse((0, 0, 39, 39), fill="#D54232")
        output = BytesIO()
        source.save(output, format="PNG")
        template = _template(
            children=[{
                "id": "die-cut", "type": "image", "props": {
                    "position": "absolute", "x": 30, "y": 30,
                    "width": 40, "height": 40, "asset": "object",
                    "fit": "contain", "alpha_outline_color": "#0055FF",
                    "alpha_outline_width_ratio": 0.1,
                },
            }],
            semantic_roles={"hero": ["die-cut"]},
            assets={"object": {
                "kind": "image", "allowed_mime_types": ["image/png"],
                "required": True, "provenance": "Unit-test edge-touching alpha object.",
            }},
        )
        preview = StudioRenderer().render_preview(
            template, semantic_data={},
            assets={"object": {"bytes": output.getvalue(), "mime_type": "image/png"}},
        )
        rendered = Image.open(BytesIO(preview["bytes"])).convert("RGB")
        outside_contour = rendered.getpixel((26, 50))
        self.assertGreater(outside_contour[2], 180)
        self.assertGreater(outside_contour[2], outside_contour[0] + 50)
        self.assertEqual((255, 255, 255), rendered.getpixel((26, 26)))
        self.assertGreater(rendered.getpixel((50, 50))[0], 180)
        props = preview["resolved"]["nodes"]["die-cut"]["props"]
        self.assertEqual(0.1, props["alpha_outline_width_ratio"])

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required")
    def test_flow_wrap_and_list_columns_change_layout_without_renderer_code(self) -> None:
        from PIL import Image

        template = _template(
            children=[{
                "id": "flow-group", "type": "container",
                "props": {
                    "position": "absolute", "x": 0, "y": 0, "width": 100,
                    "height": 100, "direction": "row", "wrap": True,
                },
                "children": [
                    {"id": f"flow-{index}", "type": "shape", "props": {
                        "width": 40, "height": 20, "fill": color,
                    }}
                    for index, color in enumerate(("#FF0000", "#00FF00", "#0000FF"), 1)
                ],
            }],
            semantic_roles={"hero": ["flow-group"]},
        )
        preview = StudioRenderer().render_preview(template, semantic_data={}, assets={})
        image = Image.open(BytesIO(preview["bytes"])).convert("RGB")
        self.assertGreater(image.getpixel((10, 30))[2], 200)
        self.assertGreater(image.getpixel((50, 10))[1], 200)

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required")
    def test_benchmarks_render_real_distinct_previews_and_configuration_changes_pixels(self) -> None:
        assets = benchmark_assets()
        templates = {
            template.document["template_id"]: template
            for template in (
                load_primitive_template(path)
                for path in sorted(BENCHMARK_DIRECTORY.glob("*_v1.json"))
            )
        }
        renderer = StudioRenderer()
        previews = {
            template_id: renderer.render_preview(
                template,
                semantic_data=BENCHMARK_CONTENT[template_id], assets=assets[template_id],
            )
            for template_id, template in templates.items()
        }
        self.assertEqual(2, len({item["bytes_sha256"] for item in previews.values()}))
        self.assertTrue(all(item["mime_type"] == "image/png" for item in previews.values()))

        base = templates["layered_product_reference"]
        changed = PrimitiveTemplateEditor(base).set_property(
            "oversized_headline", "font_size", 170,
        ).document(change_note="Primitive-engine benchmark")
        tuned = renderer.render_preview(
            changed,
            semantic_data=BENCHMARK_CONTENT["layered_product_reference"],
            assets=assets["layered_product_reference"],
        )
        self.assertNotEqual(previews["layered_product_reference"]["bytes_sha256"], tuned["bytes_sha256"])
        self.assertEqual(226.0, next(
            node for node in self._nodes(base.document["root"])
            if node["id"] == "oversized_headline"
        )["props"]["font_size"])

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required")
    def test_off_canvas_clipping_alpha_and_z_order_are_generic(self) -> None:
        from PIL import Image

        template = _template(
            children=[
                {"id": "red-shape", "type": "shape", "props": {
                    "position": "absolute", "x": -20, "y": 20, "width": 60,
                    "height": 60, "z_index": 1, "fill": "#FF0000",
                }},
                {"id": "blue-shape", "type": "shape", "props": {
                    "position": "absolute", "x": 10, "y": 30, "width": 50,
                    "height": 50, "z_index": 2, "fill": "#0000FF", "opacity": 0.8,
                    "rotation": 8,
                }},
            ],
            semantic_roles={"hero": ["blue-shape"]},
        )
        preview = StudioRenderer().render_preview(template, semantic_data={}, assets={})
        image = Image.open(BytesIO(preview["bytes"])).convert("RGBA")
        self.assertGreater(image.getpixel((20, 45))[2], image.getpixel((20, 45))[0])
        self.assertEqual((255, 255, 255), image.getpixel((90, 90))[:3])
        self.assertEqual((100, 100), image.size)

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required")
    def test_benchmark_command_writes_two_inspectable_previews_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = render_benchmarks(temporary)
            self.assertEqual(2, len(report["templates"]))
            self.assertTrue((Path(temporary) / "manifest.json").is_file())
            for item in report["templates"]:
                self.assertTrue(Path(item["preview_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
