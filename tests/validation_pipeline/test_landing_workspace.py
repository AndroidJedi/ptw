from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

try:
    from PIL import Image
except ModuleNotFoundError:  # Runtime visual tests execute in the built image.
    Image = None  # type: ignore[assignment]

from validation_pipeline.landing_workspace import (
    DEFAULT_CONFIGURATION, DEFAULT_CONTENT, DEFAULT_PRESENTATION, LandingWorkspace, normalize_composed_content, normalize_configuration, sha256_json, normalize_content,
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
    value["app_feature"] = {"title": "Home inventory", "description": "View items and add a package photo.", "action_label": "Explore inventory", "items": [{"label": label, "value": ""} for label in ("Add a photo", "View inventory", "Review categories")]}
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

    @unittest.skipUnless(LocalLandingAuthority is not None, "Landing dependencies are required")
    def test_learning_decision_cannot_cross_a_page_boundary(self):
        from validation_pipeline.landing_pages import LandingService
        service = object.__new__(LandingService)
        service.detail = Mock()
        service.authority = Mock()
        service.authority.get_proposal.return_value = {"checkpoint_id": "checkpoint"}
        service.authority.get_checkpoint.return_value = {"landing_id": "01900000-0000-7000-8000-000000000001"}
        with self.assertRaises(KeyError):
            service.decide_learning("01900000-0000-7000-8000-000000000003", "01900000-0000-7000-8000-000000000002", "proposal", "apply_global")
        service.authority.decide_proposal.assert_not_called()


@unittest.skipUnless(Image is not None, "Pillow is required for Landing visual workspace tests")
class LandingWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.images = FakeImages()
        self.workspace = LandingWorkspace(Path(self.temporary.name), image_provider=self.images)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_phone_configuration_content_and_composition_contract(self):
        from validation_pipeline.landing_design import PHONE_MOCKUP_OPTIONS, APP_FEATURE_LIMITS
        from validation_pipeline.landing_pages import landing_generation_schema
        self.assertIn("app_feature", landing_generation_schema()["properties"]["content"]["required"])
        for theme in PHONE_MOCKUP_OPTIONS["theme"]:
            for layout in PHONE_MOCKUP_OPTIONS["layout"]:
                configuration = {**deepcopy(DEFAULT_CONFIGURATION), "phone_mockup": {"theme": theme, "layout": layout}}
                self.assertEqual(configuration, normalize_configuration(configuration))
        with self.assertRaisesRegex(ValueError, "phone_mockup"):
            normalize_configuration({**DEFAULT_CONFIGURATION, "phone_mockup": {"theme": "unknown", "layout": "booking"}})
        content = complete_content()
        for key in ("title", "description", "action_label"):
            candidate = deepcopy(content)
            candidate["app_feature"][key] = "я" * (APP_FEATURE_LIMITS[key] + 1)
            with self.assertRaisesRegex(ValueError, "app_feature"):
                normalize_content(candidate)
        content["app_feature"]["items"].pop()
        with self.assertRaisesRegex(ValueError, "three UI rows"):
            normalize_content(content)
        content = complete_content()
        content.pop("app_feature")
        with self.assertRaisesRegex(ValueError, "app feature screen"):
            normalize_composed_content(content)

    def test_phone_edits_are_immutable_and_incomplete_approval_is_atomic(self):
        detail = self.prepared(configuration={**DEFAULT_CONFIGURATION, "phone_mockup": {"theme": "dark", "layout": "checklist"}})
        approved = self.workspace.approve_configuration(base_sha256=detail["state_sha256"], configuration=detail["configuration"], content=detail["content"], change_note="App feature ready")
        version = self.workspace.version_detail(1)
        candidate = deepcopy(approved["content"])
        candidate["app_feature"]["items"][0]["label"] = ""
        with self.assertRaisesRegex(ValueError, "app feature"):
            self.workspace.approve_configuration(base_sha256=approved["state_sha256"], configuration=approved["configuration"], content=candidate, change_note="Incomplete screen")
        self.assertEqual(approved["state_sha256"], self.workspace.detail()["state_sha256"])
        candidate["app_feature"]["items"][0]["label"] = "Updated feature"
        changed = self.workspace.save_configuration(base_sha256=approved["state_sha256"], configuration=approved["configuration"], content=candidate)
        self.assertEqual("Updated feature", changed["content"]["app_feature"]["items"][0]["label"])
        self.assertEqual(version, self.workspace.version_detail(1))

    def test_requires_copy_contacts_and_visuals_before_approval(self) -> None:
        detail = self.workspace.detail()
        with self.assertRaisesRegex(ValueError, "section copy"):
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

    def prepared(self, content=None, configuration=None):
        detail = self.workspace.detail()
        detail = self.workspace.save_configuration(
            base_sha256=detail['state_sha256'], configuration=configuration or deepcopy(DEFAULT_CONFIGURATION),
            content=content or complete_content(),
        )
        for slot in ('hero_visual', 'visual_break_visual'):
            detail = self.workspace.generate_visual(base_sha256=detail['state_sha256'], slot=slot,
                visual_direction='A centered abstract product illustration', prompt='test artwork')
        return detail

    def test_approval_accepts_absent_proof_and_checks_each_supplied_entry(self):
        content = complete_content()
        content['social_proof'] = {'heading': '', 'items': []}
        detail = self.prepared(content)
        approved = self.workspace.approve_configuration(base_sha256=detail['state_sha256'],
            configuration=detail['configuration'], content=content, change_note='Honest early prototype')
        original = self.workspace.version_detail(1)
        content['social_proof'] = {'heading': 'Evidence', 'items': [{'statement': 'Owner evidence', 'attribution': ''}]}
        with self.assertRaisesRegex(ValueError, 'attribution'):
            self.workspace.approve_configuration(base_sha256=approved['state_sha256'],
                configuration=approved['configuration'], content=content, change_note='Incomplete evidence')
        self.assertEqual(approved['state_sha256'], self.workspace.detail()['state_sha256'])
        self.assertEqual(original, self.workspace.version_detail(1))

    def test_failed_approval_and_save_leave_files_untouched(self):
        detail = self.prepared()
        before = {p.name: p.read_bytes() for p in self.workspace.root.glob('*.json')}
        changed = deepcopy(detail['configuration'])
        changed['theme']['accent_color'] = '#aabbcc'
        for content, note in (({**detail['content'], 'hero': {**detail['content']['hero'], 'title': ''}}, 'Incomplete'), (detail['content'], '')):
            with self.assertRaises(ValueError):
                self.workspace.approve_configuration(base_sha256=detail['state_sha256'], configuration=changed, content=content, change_note=note)
            self.assertEqual(before, {p.name: p.read_bytes() for p in self.workspace.root.glob('*.json')})
        with self.assertRaises(ValueError):
            self.workspace.save_configuration(base_sha256=detail['state_sha256'], configuration=changed,
                content={**detail['content'], 'contacts': {**detail['content']['contacts'], 'url': 'javascript:alert(1)'}})
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.workspace.root.glob('*.json')})

    def test_every_cta_destination_requires_its_valid_endpoint(self):
        detail = self.prepared()
        for target, endpoint in (('contacts', ''), ('url', 'https://example.test/book'), ('email', 'owner@example.test'), ('phone', '+380 (50) 123-45-67')):
            candidate = deepcopy(detail)
            candidate['configuration']['presentation'] = {**deepcopy(DEFAULT_PRESENTATION), 'cta_target': target}
            if target != 'contacts':
                candidate['content']['contacts'][target] = ''
                with self.assertRaisesRegex(ValueError, 'CTA destination'):
                    self.workspace.approval_ready(candidate)
                candidate['content']['contacts'][target] = endpoint
            self.workspace.approval_ready(candidate)
        for field, values in {'url': ['https://', 'https://user:pass@example.test', 'http://example.test'], 'phone': ['call us', '++12345'], 'email': ['a@', 'a b@example.test']}.items():
            for value in values:
                candidate = complete_content()
                candidate['contacts'][field] = value
                with self.assertRaises(ValueError):
                    normalize_content(candidate)

    def test_presentation_bounds_and_reading_without_rewriting(self):
        detail = self.prepared()
        digest = detail['state_sha256']
        before = (self.workspace.root / 'configuration.json').read_bytes()
        self.assertNotIn('presentation', self.workspace.detail()['configuration'])
        self.assertEqual(digest, self.workspace.detail()['state_sha256'])
        self.assertEqual(before, (self.workspace.root / 'configuration.json').read_bytes())
        for key, value in [('heading_scale', 1.16), ('heading_scale', float('nan')), ('spacing', 'huge'), ('hero_focus', {'x': 101, 'y': 50}), ('language', 'xx'), ('cta_target', 'script')]:
            with self.assertRaises(ValueError):
                normalize_configuration({**deepcopy(DEFAULT_CONFIGURATION), 'presentation': {**deepcopy(DEFAULT_PRESENTATION), key: value}})
        config = {**deepcopy(DEFAULT_CONFIGURATION), 'presentation': deepcopy(DEFAULT_PRESENTATION)}
        self.assertEqual(config, normalize_configuration(config))

class LandingDesignTests(unittest.TestCase):
    def test_natal_is_the_fixed_catalog_identity(self):
        from validation_pipeline.landing_workspace import landing_catalog
        self.assertEqual('Natal', landing_catalog()['brand'])
        with self.assertRaises(ValueError):
            normalize_configuration({**deepcopy(DEFAULT_CONFIGURATION), 'identity': {'app_name': 'Another brand'}})

    def test_presets_and_all_component_options_are_bounded(self):
        from validation_pipeline.landing_design import THEME_PRESETS, COMPONENT_OPTIONS, DEFAULT_COMPONENTS
        for preset in THEME_PRESETS:
            candidate = {**deepcopy(DEFAULT_CONFIGURATION), **{key: deepcopy(preset[key]) for key in ('theme', 'components', 'faq')}}
            self.assertEqual(candidate, normalize_configuration(candidate))
        for key, choices in COMPONENT_OPTIONS.items():
            for choice in choices:
                normalize_configuration({**deepcopy(DEFAULT_CONFIGURATION), 'components': {**DEFAULT_COMPONENTS, key: choice}})
            with self.assertRaises(ValueError):
                normalize_configuration({**deepcopy(DEFAULT_CONFIGURATION), 'components': {**DEFAULT_COMPONENTS, key: 'arbitrary-css'}})

    @unittest.skipUnless(LocalLandingAuthority is not None, 'Landing service dependencies required')
    def test_selected_image_styles_override_post_and_keep_slot_crops(self):
        from validation_pipeline.landing_design import DEFAULT_IMAGE_DIRECTIONS, PHONE_HERO_STYLE_DIRECTIVES, LANDING_BACKGROUND_DIRECTIVES
        from validation_pipeline.landing_pages import LandingService
        service = object.__new__(LandingService)
        page = {'source_post_snapshot': {'template_id': 'universal_ad', 'configuration': {}, 'content': {}, 'version_sha256': 'a' * 64}}
        for style, directive in PHONE_HERO_STYLE_DIRECTIVES.items():
            for background, treatment in LANDING_BACKGROUND_DIRECTIVES.items():
                config = {**deepcopy(DEFAULT_CONFIGURATION), 'image_directions': deepcopy(DEFAULT_IMAGE_DIRECTIONS)}
                config['theme']['accent_color'] = '#123456'
                config['image_directions']['hero_visual'] = {'style': style, 'background': background}
                prompt = service._image_prompt(page, 'hero_visual', 'A small cabinet', config)
                self.assertIn(directive, prompt)
                self.assertIn(treatment, prompt)
                self.assertIn('#123456', prompt)
                self.assertIn('balanced hero crop', prompt)
                self.assertIn('central horizontal band', service._image_prompt(page, 'visual_break_visual', 'Another cabinet', config))
                self.assertIn('premium_editorial', service._image_prompt(page, 'visual_break_visual', 'Another cabinet', config))
        config['image_directions']['hero_visual']['style'] = 'unknown'
        with self.assertRaises(ValueError):
            normalize_configuration(config)

    @unittest.skipUnless(LocalLandingAuthority is not None and Image is not None, 'Landing runtime dependencies required')
    def test_manual_generate_and_enhance_use_persisted_style_and_exact_reference(self):
        from validation_pipeline.landing_design import DEFAULT_IMAGE_DIRECTIONS
        from validation_pipeline.landing_pages import LandingService
        with tempfile.TemporaryDirectory() as root:
            provider = FakeImages()
            provider.generate = Mock(wraps=provider.generate)
            workspace = LandingWorkspace(root, image_provider=provider)
            config = {**deepcopy(DEFAULT_CONFIGURATION), 'image_directions': deepcopy(DEFAULT_IMAGE_DIRECTIONS)}
            config['image_directions']['hero_visual']['style'] = 'tactile_handmade'
            workspace.save_configuration(base_sha256=workspace.detail()['state_sha256'], configuration=config, content=complete_content())
            service = object.__new__(LandingService)
            service.detail = Mock()
            service.summary = Mock(return_value={})
            service._workspace = Mock(return_value=workspace)
            service.authority = Mock()
            service.authority.get_page.return_value = {'source_post_snapshot': {'template_id': 'universal_ad', 'configuration': {}, 'content': {}, 'version_sha256': 'a' * 64}}
            generated = service.mutate('project', 'page', 'generate_visual', base_sha256=workspace.detail()['state_sha256'], slot='hero_visual', visual_direction='A paper cabinet')
            self.assertIn('Handmade tactile materials', provider.generate.call_args.args[0])
            raw = (workspace.assets / f"{generated['assets'][0]['sha256']}.png").read_bytes()
            config['image_directions']['hero_visual']['style'] = 'contemporary_3d'
            changed = workspace.save_configuration(base_sha256=generated['state_sha256'], configuration=config, content=complete_content())
            service.mutate('project', 'page', 'generate_visual', base_sha256=changed['state_sha256'], slot='hero_visual', visual_direction='A dimensional cabinet', enhance_current=True)
            self.assertIn('Tactile contemporary 3D', provider.generate.call_args.args[0])
            self.assertEqual(raw, provider.generate.call_args.kwargs['reference_image'])
