from __future__ import annotations

import unittest

from natal.page import page_content_from_brief
from owner_gateway.landing_revision import LandingRevisionProvider, page_content_schema


PROJECT_ID = "018f07ea-7f20-7000-8000-000000000001"
REVISION_ID = "018f07ea-7f20-7000-8000-000000000002"


def brief() -> dict[str, object]:
    return {
        "language": "en",
        "source": {
            "positioning_project_id": PROJECT_ID,
            "positioning_revision_id": REVISION_ID,
        },
        "privacy_policy_url": "https://example.com/privacy",
        "business_idea": "A focused Natal workflow",
        "target_audience": "Small teams",
        "pain": "Manual follow-up is hard to track",
        "promise": "Keep one useful next step visible",
        "honest_limitation": "Results are not yet verified.",
        "key_features": [{"title": "Focus", "description": "Keep the next step visible"}],
        "steps": [
            {"title": "01", "description": "Share intent"},
            {"title": "02", "description": "Review response"},
        ],
        "proof_points": [],
        "faq": [],
        "cta": {"label": "Leave details", "url": "#lead-form"},
    }


class FakeBridge:
    last_invocation: dict[str, object] = {}

    def prepare_invocation(self, *_args: object) -> None:
        return None

    def generate_structured(self, *_args: object) -> dict[str, object]:
        return {
            "block": {
                "form_id": "waitlist",
                "heading": "Join this community",
                "body": "Leave the relevant details.",
            },
            "application_summary": "Tailored only the form copy.",
            "reusable_lesson": "Keep form context specific to the community.",
        }


class LandingRevisionProtectionTests(unittest.TestCase):
    def test_const_schema_fields_declare_their_json_type(self) -> None:
        schema = page_content_schema("product")
        self.assertEqual({"type": "integer", "const": 2}, schema["properties"]["schema_version"])
        self.assertEqual("string", schema["properties"]["template_id"]["type"])

    def test_lead_form_edit_cannot_change_the_code_owned_field_set(self) -> None:
        provider = LandingRevisionProvider.__new__(LandingRevisionProvider)
        provider.skill_contract = "test contract"
        provider.bridge = FakeBridge()
        current = page_content_from_brief("community", brief())
        block, _, _, _ = provider.edit_block(
            template_id="community", brief=brief(), page_content=current.to_dict(),
            block_id="lead_form", instruction="Tailor the form context",
            skill_memory=[],
        )
        self.assertEqual("community_interest", block["form_id"])
        self.assertEqual("Join this community", block["heading"])


if __name__ == "__main__":
    unittest.main()
