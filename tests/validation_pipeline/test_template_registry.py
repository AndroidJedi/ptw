from __future__ import annotations

import json
import unittest

from validation_pipeline.agent_context import compact_active_skills
from validation_pipeline.landing_templates import (
    LANDING_TEMPLATE_REGISTRY,
    resolve_post_template_reference,
)
from validation_pipeline.post_templates import POST_TEMPLATE_REGISTRY


class TemplateRegistryTests(unittest.TestCase):
    def test_post_and_landing_definitions_are_independent(self) -> None:
        self.assertEqual("post", POST_TEMPLATE_REGISTRY.surface)
        self.assertEqual(("phone_metrics",), POST_TEMPLATE_REGISTRY.ids)
        self.assertEqual("landing", LANDING_TEMPLATE_REGISTRY.surface)
        self.assertEqual(("project_landing", "app_showcase"), LANDING_TEMPLATE_REGISTRY.ids)
        with self.assertRaisesRegex(ValueError, "Post template is not registered"):
            POST_TEMPLATE_REGISTRY.get("project_landing")
        with self.assertRaisesRegex(ValueError, "Landing template is not registered"):
            LANDING_TEMPLATE_REGISTRY.get("phone_metrics")
        for registry in (POST_TEMPLATE_REGISTRY, LANDING_TEMPLATE_REGISTRY):
            definition = registry.all()[0]
            self.assertLess(
                len(json.dumps(definition.agent_catalog()).encode()),
                len(json.dumps(definition.catalog()).encode()),
            )

    def test_landing_design_reference_is_versioned_and_contains_no_project_data(self) -> None:
        identity = POST_TEMPLATE_REGISTRY.get("phone_metrics").identity
        resolved = resolve_post_template_reference({
            "template_id": identity.template_id,
            "template_version": identity.template_version,
            "template_sha256": identity.template_sha256,
        })
        self.assertEqual(identity.to_reference(), resolved["identity"])
        self.assertEqual({
            "identity", "name", "description", "canvas", "components",
        }, set(resolved))
        self.assertNotIn("project_id", str(resolved))
        self.assertNotIn("creative_id", str(resolved))
        self.assertNotIn("content", resolved)
        self.assertNotIn("assets", resolved)

        with self.assertRaisesRegex(ValueError, "reference is stale"):
            resolve_post_template_reference({
                "template_id": identity.template_id,
                "template_version": identity.template_version + 1,
                "template_sha256": identity.template_sha256,
            })

    def test_agent_skill_context_is_surface_filtered_and_byte_bounded(self) -> None:
        rules = [{
            "surface": "post" if index % 2 else "landing",
            "family": "copy", "instruction": f"Rule {index} " + "x" * 900,
            "target": {"semantic_role": "headline"}, "active": True,
            "tombstone": False, "evidence": [{"large": "y" * 2000}],
        } for index in range(40)]
        compact = compact_active_skills({
            "project": {
                "skill_snapshot_id": "project", "rules_sha256": "a" * 64,
                "rules": rules,
            },
            "global": None,
            "precedence": ["project_rules", "template_defaults"],
        }, surface="post")
        project = compact["project"]
        self.assertGreater(project["omitted_rule_count"], 0)
        self.assertTrue(all(rule["surface"] == "post" for rule in project["rules"]))
        self.assertNotIn("evidence", str(project))
        self.assertLess(len(json.dumps(compact).encode()), 6_000)


if __name__ == "__main__":
    unittest.main()
