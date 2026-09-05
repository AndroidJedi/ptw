from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

try:
    from PIL import Image
except ModuleNotFoundError:  # Runtime visual tests execute in the built image.
    Image = None  # type: ignore[assignment]

from validation_pipeline.landing_workspace import (
    DEFAULT_CONFIGURATION, DEFAULT_CONTENT, LandingWorkspace, normalize_composed_content,
)
from validation_pipeline.local_brief_store import LocalBriefStore

try:
    from validation_pipeline.landing_pages import LocalLandingAuthority
except ModuleNotFoundError:  # Full service tests run in the built image.
    LocalLandingAuthority = None  # type: ignore[assignment,misc]


class FakeImages:
    def __init__(self) -> None:
        self.references: list[bytes | None] = []

    def generate(self, _prompt: str, *, reference_image: bytes | None = None):
        self.references.append(reference_image)
        image = Image.new("RGB", (128, 128), (12 + len(self.references), 34, 56))
        output = BytesIO()
        image.save(output, "PNG")
        return {
            "bytes": output.getvalue(), "mime_type": "image/png",
            "source": {"origin": "test", "text_in_screen": "prohibited_by_prompt"},
        }


def complete_content() -> dict:
    value = deepcopy(DEFAULT_CONTENT)
    value["hero"] = {
        "title": "A clear honest promise", "supporting_text": "Helpful supporting copy for the owner.",
        "cta_label": "Contact us", "visual_direction": "A calm honest subject in the approved Post visual style",
    }
    value["features"] = [
        {"title": f"Feature {number}", "description": f"An honest description for feature {number}."}
        for number in range(1, 4)
    ]
    value["social_proof"] = {"heading": "Owner-provided evidence", "items": [{"statement": "Verified owner statement.", "attribution": "Named source"}]}
    value["visual_break"] = {"visual_direction": "A complementary text-free visual with a calm tonal field"}
    value["contacts"] = {"heading": "Talk to us", "supporting_text": "Choose your preferred contact method.", "email": "owner@example.test", "phone": "", "url": ""}
    value["faq"] = [
        {"question": f"Question {number}?", "answer": f"A brief honest answer {number}."}
        for number in range(1, 4)
    ]
    return value


class LandingAuthorityTests(unittest.TestCase):
    @unittest.skipUnless(LocalLandingAuthority is not None, "Landing authority dependencies are required")
    def test_frozen_approved_post_source_is_project_scoped_and_variants_follow_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = LocalBriefStore(root / "briefs")
            project_id = "01900000-0000-7000-8000-000000000001"
            other_project_id = "01900000-0000-7000-8000-000000000002"
            brief_id = "01900000-0000-7000-8000-000000000003"
            creative_id = "01900000-0000-7000-8000-000000000004"
            for project in (project_id, other_project_id):
                store.append("projects", project, {"project_id": project, "created_at": "2026-01-01T00:00:00Z"})
            store.append("briefs", brief_id, {"brief_id": brief_id, "project_id": project_id, "created_at": "2026-01-01T00:00:00Z"})
            store.append("studio_creatives", creative_id, {
                "creative_id": creative_id, "project_id": project_id, "source_brief_id": brief_id,
                "template_id": "universal_ad", "created_at": "2026-01-01T00:00:00Z",
            })
            version_path = root / "studio" / "creatives" / creative_id / "versions" / "universal_ad_v1.json"
            version_path.parent.mkdir(parents=True)
            version_path.write_text(json.dumps({
                "version": 1, "version_sha256": "a" * 64,
                "configuration": {"frozen": "post-style"}, "content": {"frozen": "post-copy"}, "assets": [],
            }), encoding="utf-8")
            authority = LocalLandingAuthority(store, post_workspace_root=root / "studio")

            sources = authority.source_versions(project_id)
            self.assertEqual([(creative_id, 1)], [(item["creative_id"], item["version"]) for item in sources])
            page, created = authority.create_page(
                project_id=project_id, source_creative_id=creative_id, source_version=1,
                requested_by="test",
            )
            self.assertTrue(created)
            self.assertEqual("post-style", page["source_post_snapshot"]["configuration"]["frozen"])
            duplicate, created = authority.create_page(
                project_id=project_id, source_creative_id=creative_id, source_version=1,
                requested_by="test",
            )
            self.assertFalse(created)
            self.assertEqual(page["landing_id"], duplicate["landing_id"])
            with self.assertRaisesRegex(ValueError, "approve the current Landing"):
                authority.create_page(
                    project_id=project_id, source_creative_id=creative_id, source_version=1,
                    requested_by="test", additional=True,
                )
            authority.update_page(page["landing_id"], approved_version_count=1)
            variant, created = authority.create_page(
                project_id=project_id, source_creative_id=creative_id, source_version=1,
                requested_by="test", additional=True,
            )
            self.assertTrue(created)
            self.assertEqual("approved_variant", variant["origin"])
            with self.assertRaisesRegex(KeyError, "Post was not found"):
                authority.create_page(
                    project_id=other_project_id, source_creative_id=creative_id, source_version=1,
                    requested_by="test",
                )

    def test_workspace_rejects_a_stale_configuration_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = LandingWorkspace(Path(temporary))
            first = workspace.detail()
            changed = deepcopy(first["configuration"])
            changed["theme"]["accent_color"] = "#224466"
            workspace.save_configuration(
                base_sha256=first["state_sha256"], configuration=changed,
                content=first["content"],
            )
            with self.assertRaisesRegex(RuntimeError, "reload"):
                workspace.save_configuration(
                    base_sha256=first["state_sha256"], configuration=changed,
                    content=first["content"],
                )

    def test_ai_composition_cannot_invent_social_proof_or_contact_endpoints(self) -> None:
        generated = complete_content()
        generated["social_proof"]["items"] = []
        generated["contacts"]["email"] = ""
        self.assertEqual([], normalize_composed_content(generated)["social_proof"]["items"])
        generated["contacts"]["url"] = "https://invented.example"
        with self.assertRaisesRegex(ValueError, "contact endpoints"):
            normalize_composed_content(generated)
        generated["contacts"]["url"] = ""
        generated["social_proof"]["items"] = [{"statement": "Invented", "attribution": "Invented"}]
        with self.assertRaisesRegex(ValueError, "social proof"):
            normalize_composed_content(generated)


@unittest.skipUnless(Image is not None, "Pillow is required for Landing visual workspace tests")
class LandingWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.images = FakeImages()
        self.workspace = LandingWorkspace(Path(self.temporary.name), image_provider=self.images)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_requires_owner_evidence_contacts_and_visuals_before_approval(self) -> None:
        detail = self.workspace.detail()
        with self.assertRaisesRegex(ValueError, "social proof"):
            self.workspace.approve_configuration(
                base_sha256=detail["state_sha256"], configuration=detail["configuration"],
                content=detail["content"], change_note="Cannot approve incomplete Landing",
            )

    def test_keeps_bounded_visual_history_and_immutable_version(self) -> None:
        detail = self.workspace.detail()
        saved = self.workspace.save_configuration(
            base_sha256=detail["state_sha256"], configuration=deepcopy(DEFAULT_CONFIGURATION),
            content=complete_content(),
        )
        hero = self.workspace.generate_visual(
            base_sha256=saved["state_sha256"], slot="hero_visual",
            visual_direction=saved["content"]["hero"]["visual_direction"], prompt="text-free hero",
        )
        full = self.workspace.generate_visual(
            base_sha256=hero["state_sha256"], slot="visual_break_visual",
            visual_direction=hero["content"]["visual_break"]["visual_direction"], prompt="text-free break",
        )
        approved = self.workspace.approve_configuration(
            base_sha256=full["state_sha256"], configuration=full["configuration"], content=full["content"],
            change_note="Complete private Landing",
        )
        self.assertEqual(1, len(approved["versions"]))
        selected = next(item for item in approved["assets"] if item["slot"] == "hero_visual")["sha256"]
        enhanced = self.workspace.generate_visual(
            base_sha256=approved["state_sha256"], slot="hero_visual",
            visual_direction=approved["content"]["hero"]["visual_direction"], prompt="text-free hero", enhance_current=True,
        )
        self.assertEqual(2, len(next(item for item in enhanced["assets"] if item["slot"] == "hero_visual")["history"]))
        self.assertIsNotNone(self.images.references[-1])
        self.assertNotEqual(selected, next(item for item in enhanced["assets"] if item["slot"] == "hero_visual")["sha256"])
