from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from skynet.tools.preflight_creatives import (
    atomic_json,
    box_inside_canvas,
    contrast_ratio,
    edge_clearances,
    hex_rgb,
    recorded_entries,
    resolve_recorded_path,
)
from skynet.tools.universal_candidate_gate import audit_universal_candidate_activation


class FrozenCreativePreflightTests(unittest.TestCase):
    def test_wcag_contrast_is_symmetric_and_known(self) -> None:
        black = hex_rgb("#000000")
        white = hex_rgb("#FFFFFF")
        self.assertAlmostEqual(21.0, contrast_ratio(black, white), places=6)
        self.assertEqual(contrast_ratio(black, white), contrast_ratio(white, black))

    def test_edge_clearance_distinguishes_bottom_touch(self) -> None:
        assigned = {"x": 72, "y": 150, "width": 936, "height": 156}
        visible = (76, 161, 910, 306)
        self.assertEqual(
            {"left": 4, "top": 11, "right": 98, "bottom": 0},
            edge_clearances(assigned, visible),
        )
        self.assertTrue(box_inside_canvas(assigned, 1080, 1080))

    def test_manifest_entries_accept_old_mapping_and_new_list(self) -> None:
        old = {"brief": {"path": "brief.json"}, "empty": "ignored"}
        new = [{"path": "brief.json"}, "ignored"]
        self.assertEqual([{"path": "brief.json"}], recorded_entries(old))
        self.assertEqual([{"path": "brief.json"}], recorded_entries(new))

    def test_recorded_path_prefers_manifest_relative_then_root_relative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            experiment = root / "experiments" / "one"
            experiment.mkdir(parents=True)
            manifest = experiment / "manifest.json"
            manifest.write_text("{}")
            local = experiment / "candidate.json"
            local.write_text("{}")
            shared = root / "assets" / "logo.png"
            shared.parent.mkdir()
            shared.write_bytes(b"logo")
            self.assertEqual(local.resolve(), resolve_recorded_path(root, manifest, "candidate.json"))
            self.assertEqual(shared.resolve(), resolve_recorded_path(root, manifest, "assets/logo.png"))

    def test_atomic_json_replaces_derived_report_completely(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "report.json"
            atomic_json(target, {"status": "first"})
            atomic_json(target, {"status": "second"})
            self.assertEqual({"status": "second"}, json.loads(target.read_text()))

    def test_photo_strategy_texture_fallback_fails_closed_before_candidate_identity(self) -> None:
        report = audit_universal_candidate_activation(
            strategy_id="human_story",
            media_mode="deterministic_texture",
            layout_audit={"passed": True},
            strict_visual_audit={"status": "passed"},
            brand_prominence_audit={"status": "failed"},
        )
        self.assertEqual("failed", report["status"])
        self.assertFalse(report["candidate_activation_authorized"])
        self.assertEqual(
            ["deterministic_texture_diagnostic_only", "brand_prominence_failed"],
            [failure["code"] for failure in report["failures"]],
        )

    def test_audited_approved_photo_can_pass_activation_gate(self) -> None:
        report = audit_universal_candidate_activation(
            strategy_id="human_story",
            media_mode="approved_photo",
            layout_audit={"passed": True},
            strict_visual_audit={"status": "passed"},
            brand_prominence_audit={"status": "passed"},
        )
        self.assertEqual("passed", report["status"])
        self.assertTrue(report["candidate_activation_authorized"])
        self.assertEqual([], report["failures"])


if __name__ == "__main__":
    unittest.main()
