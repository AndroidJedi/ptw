from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from natal.brief import LandingBrief, apply_brief_overrides, brief_from_candidate
from natal.builder import build_landing, verify_brand_assets
from natal.catalog import landing_templates, recommend_template


RUN_ID = "01234567-89ab-7def-8123-456789abcdef"
THESIS_ID = "11234567-89ab-7def-8123-456789abcdef"


def candidate(problem: str = "Teams lose clients in manual workflows") -> dict:
    return {
        "idea_run_id": RUN_ID,
        "owner_idea": "Automate retention for service businesses",
        "recommended_thesis_id": THESIS_ID,
        "quality": {"successful": 10, "attempted": 10},
        "theses": [{
            "id": THESIS_ID,
            "recommended": True,
            "verdict": "survives",
            "title": {"uk": "Автоматичне утримання", "en": "Automated retention"},
            "target_user": {"uk": "Власники сервісного бізнесу", "en": "Service business owners"},
            "problem": {"uk": problem, "en": problem},
            "value_moment": {"uk": "Natal показує наступну дію", "en": "Natal shows the next action"},
            "mechanism_ids": ["mechanism-1"],
            "loop_steps": [
                {"uk": "Підключіть дані", "en": "Connect data"},
                {"uk": "Побачте ризик", "en": "See risk"},
                {"uk": "Запустіть наступну дію", "en": "Start the next action"},
            ],
        }],
        "mechanisms": [{
            "id": "mechanism-1",
            "name": {"uk": "Сигнали ризику", "en": "Risk signals"},
            "description": {"uk": "Помічає зміни раніше", "en": "Notices changes earlier"},
        }],
    }


class NatalLandingBuilderTests(unittest.TestCase):
    def test_catalog_and_selector_cover_the_three_source_structures(self) -> None:
        self.assertEqual(["product", "community", "waitlist"], [item["id"] for item in landing_templates()])
        self.assertEqual("product", recommend_template(candidate()))
        self.assertEqual("community", recommend_template(candidate("Офлайн зустріч для маленької спільноти")))
        self.assertEqual("waitlist", recommend_template({"owner_idea": "A new personal ritual", "theses": []}))

    def test_completed_evaluation_becomes_source_explicit_natal_brief(self) -> None:
        prepared = brief_from_candidate(candidate())
        self.assertEqual("product", prepared["recommended_template_id"])
        self.assertEqual("Natal", prepared["brief"]["brand"])
        self.assertEqual(RUN_ID, prepared["brief"]["source"]["laval_run_id"])
        self.assertEqual(THESIS_ID, prepared["brief"]["source"]["thesis_id"])
        self.assertEqual("Сигнали ризику", prepared["brief"]["key_features"][0]["title"])
        self.assertEqual([], prepared["brief"]["proof_points"])

    def test_overrides_cannot_change_brand_or_source_ids(self) -> None:
        base = brief_from_candidate(candidate())["brief"]
        changed = apply_brief_overrides(base, {
            "brand": "Another App",
            "source": {"laval_run_id": "spoofed"},
            "business_idea": "A sharper idea",
        })
        self.assertEqual("Natal", changed["brand"])
        self.assertEqual(RUN_ID, changed["source"]["laval_run_id"])
        self.assertEqual("A sharper idea", changed["business_idea"])

    def test_every_template_builds_with_canonical_assets_and_no_raw_tokens(self) -> None:
        verify_brand_assets()
        brief = brief_from_candidate(candidate())["brief"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for template in ("product", "community", "waitlist"):
                output = root / template
                result = build_landing(template, brief, output)
                document = (output / "index.html").read_text()
                normalized = json.loads((output / "brief.json").read_text())
                self.assertEqual(template, result["template_id"])
                self.assertIn('alt="Natal"', document)
                self.assertIn("Автоматичне утримання", document)
                self.assertNotIn("$business_idea", document)
                self.assertIn("не заявляємо про результати", document)
                self.assertEqual("Natal", normalized["brand"])
                self.assertEqual(RUN_ID, normalized["source"]["laval_run_id"])
                self.assertTrue((output / "assets" / "logo-natal.png").is_file())

    def test_builder_escapes_copy_rejects_unsafe_cta_and_preserves_nonempty_output(self) -> None:
        raw = brief_from_candidate(candidate())["brief"]
        raw["business_idea"] = "<script>alert(1)</script>"
        brief = LandingBrief.from_dict(raw)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            build_landing("product", brief, output)
            self.assertIn("&lt;script&gt;", (output / "index.html").read_text())
            with self.assertRaises(FileExistsError):
                build_landing("product", brief, output)
        raw["cta"] = {"label": "Click", "url": "javascript:alert(1)"}
        with self.assertRaisesRegex(ValueError, "cta.url"):
            LandingBrief.from_dict(raw)
        for unsafe_url in ("//example.test/collect", "https:missing-host"):
            raw["cta"] = {"label": "Click", "url": unsafe_url}
            with self.subTest(unsafe_url=unsafe_url), self.assertRaisesRegex(ValueError, "cta.url"):
                LandingBrief.from_dict(raw)


if __name__ == "__main__":
    unittest.main()
