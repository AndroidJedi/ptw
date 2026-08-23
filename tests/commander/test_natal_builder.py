from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from natal.brief import LandingBrief
from natal.builder import build_landing, preview_document
from natal.forms import allowed_field_names, form_definition
from natal.page import BLOCK_IDS, LandingPageContent, page_content_from_brief, protect_page_content


PROJECT_ID = "018f07ea-7f20-7000-8000-000000000001"
REVISION_ID = "018f07ea-7f20-7000-8000-000000000002"


def brief() -> LandingBrief:
    return LandingBrief.from_dict({
        "language": "en",
        "source": {"positioning_project_id": PROJECT_ID, "positioning_revision_id": REVISION_ID},
        "privacy_policy_url": "https://example.com/privacy",
        "business_idea": "A focused Natal workflow",
        "target_audience": "Small teams",
        "pain": "Manual follow-up is hard to track",
        "promise": "Keep one useful next step visible",
        "honest_limitation": "Results are not yet verified.",
        "key_features": [{"title": "Focus", "description": "Keep the next step visible"}],
        "steps": [{"title": "01", "description": "Share intent"}, {"title": "02", "description": "Review response"}],
        "proof_points": [],
        "faq": [{"question": "What is Natal?", "answer": "Natal is the fixed product identity."}],
        "cta": {"label": "Leave details", "url": "#lead-form"},
    })


class NatalV2BuilderTests(unittest.TestCase):
    def test_all_templates_have_eight_blocks_and_code_owned_forms(self) -> None:
        expected = {"product": "contact_request", "community": "community_interest", "waitlist": "waitlist"}
        self.assertEqual(len(BLOCK_IDS), 8)
        for template_id, form_id in expected.items():
            page = page_content_from_brief(template_id, brief())
            self.assertEqual(set(page.blocks), set(BLOCK_IDS))
            self.assertEqual(page.blocks["lead_form"]["form_id"], form_id)
            self.assertEqual(page.to_dict()["schema_version"], 2)

    def test_preview_is_self_contained_and_form_is_inert(self) -> None:
        page = page_content_from_brief("waitlist", brief())
        document = preview_document("waitlist", brief(), page)
        self.assertIn('data-landing-block="lead_form"', document)
        self.assertIn(" disabled", document)
        self.assertNotIn("/api/v1/public/landings/", document)
        self.assertNotIn('href="styles.css"', document)

    def test_published_build_activates_exact_form_endpoint_and_keeps_private_json_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            page = page_content_from_brief("community", brief())
            manifest = build_landing(
                "community", brief(), output, page_content=page,
                build_id=REVISION_ID,
                lead_api_url="https://api.example.com/api/v1/public/landings",
            )
            html = (output / "index.html").read_text()
            self.assertIn(f"https://api.example.com/api/v1/public/landings/{REVISION_ID}/leads", html)
            self.assertIn("https://example.com/privacy", html)
            self.assertNotIn(" disabled", html)
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(json.loads((output / "page_content.json").read_text())["blocks"], page.to_dict()["blocks"])

    def test_proof_is_reapplied_from_positioning_brief(self) -> None:
        source = brief().to_dict()
        source["proof_points"] = ["Source-backed claim"]
        page = page_content_from_brief("product", source).to_dict()
        page["blocks"]["proof"]["items"] = ["Invented result"]
        page["blocks"]["proof"]["empty_text"] = "An invented limitation"
        page["language"] = "uk"
        protected = protect_page_content(page, template_id="product", brief=source)
        self.assertEqual(protected.blocks["proof"]["items"], ["Source-backed claim"])
        self.assertEqual(protected.blocks["proof"]["empty_text"], "Results are not yet verified.")
        self.assertEqual(protected.language, "en")

    def test_form_catalog_fields_and_success_copy_are_fixed(self) -> None:
        self.assertEqual(allowed_field_names("waitlist"), {"email"})
        self.assertEqual(allowed_field_names("contact_request"), {"name", "email", "note"})
        self.assertEqual(allowed_field_names("community_interest"), {"name", "email", "telegram_handle"})
        self.assertEqual(
            form_definition("waitlist", "en")["success_copy"],
            "Thanks. We received your details and will contact you.",
        )

    def test_schema_rejects_seven_block_legacy_page(self) -> None:
        page = page_content_from_brief("product", brief()).to_dict()
        page["blocks"].pop("lead_form")
        with self.assertRaisesRegex(ValueError, "every canonical"):
            LandingPageContent.from_dict(page)


if __name__ == "__main__":
    unittest.main()
