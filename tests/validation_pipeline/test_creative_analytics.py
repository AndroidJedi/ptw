from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
from uuid import uuid4

from validation_pipeline.creative_analytics import (
    CreativeAnalyticsService, LocalCreativeAnalyticsAuthority, _rules_conflict,
    comparison_age_band, due_milestone, learning_output_schema, normalize_rule,
    safe_landing_learning_content,
)
from validation_pipeline.local_brief_store import LocalBriefStore


class _LandingPublications:
    def __init__(self, project_id: str, publication_id: str, event_id: str, version_id: str) -> None:
        self.project_id, self.publication_id = project_id, publication_id
        self.event_id, self.version_id = event_id, version_id

    def _active(self, namespace: str, slug: str):
        if (namespace, slug) != ("ai", "measured-page"):
            raise KeyError("Published Landing was not found")
        return (
            {"project_id": self.project_id, "publication_id": self.publication_id},
            {
                "event_id": self.event_id, "landing_id": str(uuid4()),
                "landing_version_id": self.version_id,
                "landing_version_sha256": "a" * 64,
            },
            "Measured Project", {},
        )

    def get(self, project_id: str):
        return None


class _EmptyMetaAuthority:
    def list_deployments(self, _project_id: str):
        return []


class _EmptyMeta:
    authority = _EmptyMetaAuthority()
    adapter = None


class _NeverCalledProvider:
    def call(self, **_kwargs):
        raise AssertionError("provider must not run for insufficient data")


class CreativeAnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ptw-analytics-test-")
        self.store = LocalBriefStore(self.temporary.name)
        self.project_id = str(uuid4())
        self.publication_id, self.event_id, self.version_id = (
            str(uuid4()), str(uuid4()), str(uuid4()),
        )
        self.store.append("projects", self.project_id, {
            "project_id": self.project_id, "created_at": "2026-09-01T00:00:00Z",
        })
        self.authority = LocalCreativeAnalyticsAuthority(self.store)
        root = Path(__file__).resolve().parents[2]
        self.service = CreativeAnalyticsService(
            self.authority, studio=object(), landing_pages=object(),
            landing_publications=_LandingPublications(
                self.project_id, self.publication_id, self.event_id, self.version_id,
            ),
            meta_ads=_EmptyMeta(), structured_provider=_NeverCalledProvider(),
            performance_skill_path=root / "skills/creative-performance-learner/SKILL.md",
            visual_skill_path=root / "skills/creative-visual-analyzer/SKILL.md",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def event(self, **patch):
        return {
            "event_id": str(uuid4()), "visit_id": str(uuid4()),
            "route": "/ai/measured-page", "landing_version_sha256": "a" * 64,
            "event_type": "landing_view", "surface": "page", "target": "page",
            "attribution_token": None, "viewport_class": "mobile", **patch,
        }

    def test_landing_events_are_idempotent_cookieless_and_roll_up_immutably(self) -> None:
        event = self.event()
        self.assertTrue(self.service.record_landing_event(event)["created"])
        for _attempt in range(65):
            self.assertFalse(self.service.record_landing_event(event)["created"])

        stored = self.store.get("landing_analytics_events", event["event_id"])
        for forbidden in ("route", "ip", "user_agent", "referrer", "url", "contact"):
            self.assertNotIn(forbidden, stored)
        rollups = self.authority.list_rollups([self.project_id], None)
        self.assertEqual(1, len(rollups))
        self.assertEqual(1, rollups[0]["cumulative_count"])

        with self.assertRaisesRegex(ValueError, "reused"):
            self.service.record_landing_event({**event, "viewport_class": "desktop"})

        instagram_cta = self.event(
            event_type="primary_cta_click", surface="hero", target="instagram",
        )
        self.assertTrue(self.service.record_landing_event(instagram_cta)["created"])
        self.assertEqual(
            {"landing_view": 1, "primary_cta_click": 1},
            {item["event_type"]: item["cumulative_count"] for item in self.authority.list_rollups([self.project_id], None)},
        )

    def test_learning_with_no_comparable_items_is_frozen_as_insufficient(self) -> None:
        request_id = str(uuid4())
        run = self.service.run_learning(
            project_id=self.project_id, request_id=request_id, surface="post",
        )
        self.assertEqual("insufficient_data", run["status"])
        self.assertEqual(0, run["dataset"]["sample_size"])
        replay = self.service.run_learning(
            project_id=self.project_id, request_id=request_id, surface="post",
        )
        self.assertEqual(run["learning_run_id"], replay["learning_run_id"])
        self.assertEqual(run["dataset_sha256"], replay["dataset_sha256"])

    def test_scheduled_snapshot_never_fabricates_a_missed_milestone(self) -> None:
        self.assertEqual(24, due_milestone(24))
        self.assertEqual(72, due_milestone(75))
        self.assertEqual(168, due_milestone(168))
        self.assertIsNone(due_milestone(30))
        self.assertIsNone(due_milestone(1000))
        self.assertEqual([72, 168, 336, 720], [
            comparison_age_band(age) for age in (72, 168, 336, 720)
        ])

    def test_learning_manifest_replaces_contact_values_with_presence(self) -> None:
        safe = safe_landing_learning_content({
            "hero": {"title": "Measured offer"},
            "contacts": {
                "heading": "Talk to us", "supporting_text": "Choose a channel",
                "url": "https://t.me/private_owner", "instagram": "private_owner",
                "email": "private@example.com", "phone": "+380000000000",
            },
        })
        self.assertEqual(
            ["url", "instagram", "email", "phone"],
            safe["contacts"]["available_channels"],
        )
        for value in ("private_owner", "private@example.com", "+380000000000"):
            self.assertNotIn(value, json.dumps(safe))

    def test_typed_rules_enforce_scope_and_landing_catalog_bounds(self) -> None:
        rule = normalize_rule({
            "surface": "landing", "family": "ui",
            "instruction": "Keep the heading scale inside the tested range.",
            "target": {
                "template_id": "project_landing", "component_id": "project_landing.theme",
                "setting_id": "configuration.presentation.heading_scale",
                "operation": "range", "minimum": .9, "maximum": 1.1,
            },
            "evidence": {}, "confidence": {"sample_size": 2, "level": "exploratory"},
        }, scope="project", project_id=self.project_id)
        self.assertEqual("ui", rule["family"])
        self.assertEqual(1, rule["confidence"]["project_count"])

        with self.assertRaisesRegex(ValueError, "catalog minimum"):
            normalize_rule({
                **{key: value for key, value in rule.items() if key not in {"rule_id", "scope", "project_id"}},
                "target": {**rule["target"], "minimum": .2},
            }, scope="project", project_id=self.project_id)
        with self.assertRaisesRegex(ValueError, "spirit"):
            normalize_rule({
                "surface": "both", "family": "copy", "instruction": "Prefer a clear promise.",
                "target": {"semantic_role": "hero_title"}, "evidence": {},
                "confidence": {"sample_size": 2, "project_count": 1, "level": "exploratory"},
            }, scope="global", project_id=None)
        phone_rule = normalize_rule({
            "surface": "post", "family": "ui",
            "instruction": "Hide the eyebrow when concise variants outperform it.",
            "target": {
                "template_id": "phone_metrics", "component_id": "phone_metrics.offer",
                "setting_id": "configuration.offer.enabled", "operation": "set",
                "value": False,
            },
            "evidence": {}, "confidence": {"sample_size": 3, "level": "exploratory"},
        }, scope="project", project_id=self.project_id)
        self.assertIs(phone_rule["target"]["value"], False)
        for template_id, component_id in (
            ("unknown_template", "unknown_template.brand"),
            ("phone_metrics", "phone_metrics.brand"),
        ):
            with self.assertRaisesRegex(ValueError, "does not exist"):
                normalize_rule({
                    "surface": "post", "family": "ui",
                    "instruction": "Change the Project brand color from measured output.",
                    "target": {
                        "template_id": template_id, "component_id": component_id,
                        "setting_id": "configuration.logo.symbol_color",
                        "operation": "set", "value": "#123456",
                    },
                    "evidence": {},
                    "confidence": {"sample_size": 3, "level": "exploratory"},
                }, scope="project", project_id=self.project_id)
        with self.assertRaisesRegex(ValueError, "asset_slot"):
            normalize_rule({
                "surface": "landing", "family": "image",
                "instruction": "Prefer a clearer visual in an exact Landing slot.",
                "target": {"asset_slot": "invented_slot"}, "evidence": {},
                "confidence": {"sample_size": 2, "level": "exploratory"},
            }, scope="project", project_id=self.project_id)
        with self.assertRaisesRegex(ValueError, "target fields"):
            normalize_rule({
                **{key: value for key, value in phone_rule.items() if key not in {"rule_id", "scope", "project_id"}},
                "target": {**phone_rule["target"], "raw_url": "https://example.invalid"},
            }, scope="project", project_id=self.project_id)
        with self.assertRaisesRegex(ValueError, "exact post or landing surface"):
            normalize_rule({
                **{key: value for key, value in phone_rule.items() if key not in {"rule_id", "scope", "project_id"}},
                "surface": "both",
            }, scope="project", project_id=self.project_id)

        common = {
            "family": "copy", "target": {"semantic_role": "hero_title"},
            "active": True,
        }
        self.assertTrue(_rules_conflict([
            {**common, "surface": "both"}, {**common, "surface": "post"},
        ]))

    def test_learning_output_schema_closes_every_object_for_codex_strict_mode(self) -> None:
        def assert_closed(node) -> None:
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False)
                    self.assertEqual(set(node.get("properties", {})), set(node.get("required", [])))
                for value in node.values():
                    assert_closed(value)
            elif isinstance(node, list):
                for value in node:
                    assert_closed(value)

        for scope in ("project", "global"):
            assert_closed(learning_output_schema(scope))


if __name__ == "__main__":
    unittest.main()
