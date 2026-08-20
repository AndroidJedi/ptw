from __future__ import annotations

import importlib.util
import re
import unittest


@unittest.skipUnless(importlib.util.find_spec("reportlab"), "ReportLab is required")
class LavalPdfTests(unittest.TestCase):
    def test_completed_report_is_ukrainian_pdf_with_clickable_source(self) -> None:
        from idea_generation.laval_pdf import build_laval_pdf

        run_id = "01234567-89ab-7def-8123-456789abcdef"
        stages = [
            {"stage": "OWNER_CAPTURE", "ordinal": 0, "status": "completed", "attempt": 1, "provider": "owner", "artifact": {"raw_text": "Зміни & докази"}},
            {"stage": "COMPETITOR_SELECTION", "ordinal": 4, "status": "completed", "attempt": 1, "provider": "deterministic", "artifact": {"global_deduplicated": [{"name": "Конкурент", "url": "https://example.com/product", "type": "direct_product", "countries": ["US"], "score": .72, "selected": True}]}},
            {"stage": "OPPORTUNITY_MATRIX", "ordinal": 9, "status": "completed", "attempt": 1, "provider": "codex", "artifact": {"opportunities": [{"id": "opportunity", "statement": "Людям потрібен видимий доказ прогресу", "affected_segment": "Дорослі користувачі", "aggregate_score": .68, "evidence_ids": ["evidence"]}]}},
            {"stage": "MARKET_SIGNAL_GATE", "ordinal": 12, "status": "completed", "attempt": 1, "provider": "deterministic", "artifact": {"scores": [{"opportunity_id": "opportunity", "aggregate_score": .64}]}},
            {"stage": "YOUTUBE_OBSERVATION", "ordinal": 7, "status": "completed", "attempt": 1, "provider": "codex", "artifact": {"observations": [{"observation_type": "workaround", "statement": "Користувачі ведуть журнал доказів", "independent_creator_count": 3}]}},
            {"stage": "MECHANISM_SCORING", "ordinal": 18, "status": "completed", "attempt": 1, "provider": "deterministic", "artifact": {"mechanisms": [{"id": "mechanism", "name": {"uk": "Доказ до планування", "en": "Proof before planning"}, "description": {"uk": "Завершена дія створює доказ.", "en": "A completed action creates proof."}, "mechanism_type": "proof", "support_dimensions": {"source_diversity": .5, "owner_dna_fit": .8}, "evidence_ids": ["evidence"]}]}},
            {"stage": "THESIS_SHORTLIST", "ordinal": 21, "status": "completed", "attempt": 1, "provider": "deterministic", "artifact": {"status": "no_surviving_thesis", "theses": [{"title": {"uk": "Петля доказу", "en": "Proof loop"}, "target_user": {"uk": "Люди зі складною метою", "en": "People with a hard goal"}, "problem": {"uk": "Немає видимого прогресу", "en": "No visible progress"}, "loop_steps": [{"uk": "Обрати дію", "en": "Choose action"}, {"uk": "Завершити", "en": "Complete"}], "dangerous_assumptions": [{"severity": "high", "statement": {"uk": "Публічність мотивує", "en": "Public proof motivates"}}], "verdict": "rejected", "unsupported_high_severity_count": 2, "weakest_mechanism_coverage": .3, "evidence_ids": ["evidence"]}]}},
        ]

        class Repository:
            def run(self, _run_id: str):
                return {"id": run_id, "status": "completed", "evidence_mode": "live_market_signals", "pipeline_version": "mechanism_thesis_v1", "updated_at": "2026-08-20T12:00:00Z"}

            def owner(self, _run_id: str):
                return {"raw_text": "Продукт, який перетворює завершені дії на видимі докази."}

            def stages(self, _run_id: str):
                return stages

            def llm_quality(self, _run_id: str):
                return {"success": 11, "attempted": 12}

            def cost(self, _run_id: str):
                return {"provider_actual_usd": .0372, "total_usd": .0372}

            def evidence(self, _run_id: str):
                return [{"id": "evidence", "source_title": "Корисне джерело", "source_url": "https://example.com/research?one=1&two=2", "source_type": "website", "publisher": "Example", "country": "US"}]

        content = build_laval_pdf(Repository(), run_id)
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 20_000)
        self.assertGreaterEqual(len(re.findall(rb"/Type\s*/Page\b", content)), 4)
        self.assertIn(b"/URI", content)

    def test_incomplete_run_cannot_generate_final_report(self) -> None:
        from idea_generation.laval_pdf import build_laval_pdf

        class Repository:
            def run(self, _run_id: str):
                return {"status": "running"}

        with self.assertRaisesRegex(ValueError, "only for completed"):
            build_laval_pdf(Repository(), "run")


if __name__ == "__main__":
    unittest.main()
