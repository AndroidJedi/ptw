from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

try:
    from PIL import Image
except ModuleNotFoundError:  # Runtime visual tests execute in the built image.
    Image = None  # type: ignore[assignment]

from validation_pipeline.landing_workspace import (
    DEFAULT_CONFIGURATION, DEFAULT_CONTENT, DEFAULT_PRESENTATION, LandingWorkspace, normalize_composed_content, normalize_configuration, sha256_json, normalize_content,
)
from validation_pipeline.local_brief_store import LocalBriefStore

try:
    from validation_pipeline.landing_pages import DatabaseLandingAuthority, LocalLandingAuthority
except ModuleNotFoundError:  # Full service tests run in the built image.
    DatabaseLandingAuthority = None  # type: ignore[assignment,misc]
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
    @unittest.skipUnless(DatabaseLandingAuthority is not None, "Landing authority dependencies are required")
    def test_database_reservation_records_typed_lineage_edges_in_argument_order(self) -> None:
        project_id = "01900000-0000-7000-8000-000000000001"
        brief_id = "01900000-0000-7000-8000-000000000003"
        creative_id = "01900000-0000-7000-8000-000000000004"

        class Result:
            def fetchall(self):
                return []

        class Connection:
            def execute(self, _query, _values=()):
                return Result()

        class RecordingAuthority(DatabaseLandingAuthority):  # type: ignore[misc,valid-type]
            def __init__(self):
                self.edges = []

            @contextmanager
            def connection(self):
                yield Connection()

            def _source_version(self, received_project_id, received_creative_id, version):
                self.assert_source = (received_project_id, received_creative_id, version)
                return {
                    "source_brief_id": brief_id, "version_sha256": "a" * 64,
                    "configuration": {}, "content": {}, "assets": [],
                }

            def _edge(self, _connection, source_id, relation, target_id, attributes):
                evidence = attributes.get("input", attributes.get("member"))
                self.edges.append((source_id, relation, target_id, evidence))

            def ensure_skill(self, _scope, _project_id=None):
                return None

            def get_page(self, landing_id):
                return {"landing_id": landing_id}

        authority = RecordingAuthority()
        page, created = authority.create_page(
            project_id=project_id, source_creative_id=creative_id,
            source_version=1, requested_by="test",
        )

        self.assertTrue(created)
        self.assertEqual((project_id, creative_id, 1), authority.assert_source)
        landing_id = page["landing_id"]
        self.assertEqual([
            (project_id, "contains", landing_id, "landing_page"),
            (landing_id, "derived_from", brief_id, "approved_product_brief"),
            (landing_id, "derived_from", creative_id, "approved_post_version"),
        ], authority.edges)

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
                "template_id": "phone_metrics", "created_at": "2026-01-01T00:00:00Z",
            })
            version_path = root / "studio" / "creatives" / creative_id / "versions" / "phone_metrics_v1.json"
            version_path.parent.mkdir(parents=True)
            version_path.write_text(json.dumps({
                "version": 1, "version_sha256": "a" * 64, "template_id": "phone_metrics",
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
        generated["contacts"]["url"] = "https://t.me/invented_helper_bot"
        with self.assertRaisesRegex(ValueError, "contact endpoints"):
            normalize_composed_content(generated)
        generated["contacts"]["url"] = ""
        generated["social_proof"]["items"] = [{"statement": "Invented", "attribution": "Invented"}]
        with self.assertRaisesRegex(ValueError, "social proof"):
            normalize_composed_content(generated)

    @unittest.skipUnless(LocalLandingAuthority is not None, "Landing dependencies are required")
    def test_composition_payload_is_bounded_and_excludes_presentation_state(self) -> None:
        from validation_pipeline.landing_pages import landing_composition_payload
        from validation_pipeline.landing_workspace import landing_catalog
        from validation_pipeline.post_templates import POST_TEMPLATE_REGISTRY
        identity = POST_TEMPLATE_REGISTRY.get("phone_metrics").identity
        skills = {
            "project": {"skill_snapshot_id": "project", "rules": []},
            "global": {"skill_snapshot_id": "global", "rules": []},
            "precedence": ["catalog_brand_and_brief", "explicit_owner_direction", "project_rules", "global_spirit", "template_defaults"],
        }
        payload = landing_composition_payload(
            landing_id="01900000-0000-7000-8000-000000000001",
            approved_product_brief={"language": "en"},
            source_post_snapshot={
                "template_id": "phone_metrics", "content": {"hero_title": "Hello"},
                "configuration": {"must_not_reach_ai": True}, "assets": ["large"],
                "version_sha256": "a" * 64,
                "template_version": identity.template_version,
                "template_sha256": identity.template_sha256,
            },
            content_defaults=DEFAULT_CONTENT,
            active_creative_skills=skills,
            live_landing_catalog=landing_catalog(),
        )
        self.assertEqual("ptw.landing.catalog.v2", payload["live_landing_catalog"]["schema"])
        self.assertNotIn("configuration", payload["source_post_copy"])
        self.assertNotIn("assets", payload["source_post_copy"])
        self.assertEqual({
            "template_id": identity.template_id,
            "template_version": identity.template_version,
            "template_sha256": identity.template_sha256,
        }, payload["source_post_template_reference"])
        self.assertEqual(
            skills["precedence"], payload["active_creative_skills"]["precedence"],
        )
        self.assertEqual([], payload["active_creative_skills"]["project"]["rules"])
        self.assertEqual(0, payload["active_creative_skills"]["global"]["omitted_rule_count"])

    @unittest.skipUnless(LocalLandingAuthority is not None, "Landing dependencies are required")
    def test_save_approve_learning_entrypoint_is_retired(self):
        from validation_pipeline.landing_pages import LandingService
        self.assertFalse(hasattr(LandingService, "decide_learning"))
        self.assertFalse(hasattr(LandingService, "retry_learning"))


@unittest.skipUnless(Image is not None, "Pillow is required for Landing visual workspace tests")
class LandingWorkspaceTests(unittest.TestCase):
    def test_visual_mode_survives_save_restart_and_immutable_approval(self):
        detail = self.prepared(configuration={**DEFAULT_CONFIGURATION, "visual_mode": "image"})
        approved = self.workspace.approve_configuration(base_sha256=detail["state_sha256"], configuration=detail["configuration"], content=detail["content"], change_note="Image hero")
        version = self.workspace.version_detail(1)
        self.assertEqual("image", version["configuration"]["visual_mode"])
        reopened = LandingWorkspace(Path(self.temporary.name), image_provider=self.images)
        self.assertEqual("image", reopened.detail()["configuration"]["visual_mode"])
        restored = reopened.save_configuration(base_sha256=approved["state_sha256"], configuration={**approved["configuration"], "visual_mode": "phone"}, content=approved["content"])
        self.assertEqual(detail["content"], restored["content"])
        self.assertEqual(detail["assets"], restored["assets"])
        self.assertEqual(version, reopened.version_detail(1))
        self.assertNotIn("visual_mode", normalize_configuration(DEFAULT_CONFIGURATION))
        with self.assertRaisesRegex(ValueError, "visual_mode"):
            normalize_configuration({**DEFAULT_CONFIGURATION, "visual_mode": "invalid"})

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.images = FakeImages()
        self.workspace = LandingWorkspace(Path(self.temporary.name), image_provider=self.images)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_phone_configuration_content_and_composition_contract(self):
        from validation_pipeline.landing_design import PHONE_MOCKUP_OPTIONS, APP_FEATURE_LIMITS
        from validation_pipeline.landing_pages import (
            landing_generation_schema, validate_landing_composition,
        )
        schema = landing_generation_schema()
        self.assertEqual({"content"}, set(schema["properties"]))
        self.assertEqual(["content"], schema["required"])
        self.assertIn("app_feature", schema["properties"]["content"]["required"])
        content_schema = schema["properties"]["content"]["properties"]
        self.assertEqual(
            [""], content_schema["contacts"]["properties"]["url"]["enum"],
        )
        self.assertEqual(
            APP_FEATURE_LIMITS["description"],
            content_schema["app_feature"]["properties"]["description"]["maxLength"],
        )
        self.assertEqual(
            600, content_schema["hero"]["properties"]["visual_direction"]["maxLength"],
        )
        generated = complete_content()
        generated["social_proof"]["items"] = []
        generated["contacts"].update({"email": "", "phone": "", "url": ""})
        self.assertEqual(generated, validate_landing_composition({"content": generated})["content"])
        with self.assertRaisesRegex(ValueError, "response fields"):
            validate_landing_composition({
                "configuration": deepcopy(DEFAULT_CONFIGURATION), "content": generated,
            })
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

    def test_uploaded_reference_for_both_slots_is_not_a_workspace_asset(self):
        from tests.validation_pipeline.test_image_reference import upload
        from validation_pipeline.image_reference import decode_reference
        reference = decode_reference(upload())
        for slot in ("hero_visual", "visual_break_visual"):
            before = self.workspace.detail()
            after = self.workspace.generate_visual(base_sha256=before["state_sha256"], slot=slot,
                visual_direction="Keep the composition, change the background", prompt="Text-free artwork only",
                reference_image=reference)
            self.assertEqual(reference, self.images.references[-1])
            self.assertNotIn("bytes_base64", json.dumps(after))
            for path in self.workspace.root.rglob("*"):
                if path.is_file():
                    self.assertNotEqual(reference, path.read_bytes())
            with patch.object(self.images, 'generate', side_effect=RuntimeError('unavailable')):
                with self.assertRaises(RuntimeError):
                    self.workspace.generate_visual(base_sha256=after["state_sha256"], slot=slot,
                        visual_direction="Change the background again", prompt="Text-free artwork only", reference_image=reference)
            self.assertEqual(after["state_sha256"], self.workspace.detail()["state_sha256"])

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
        for target, endpoint in (('contacts', ''), ('url', 'https://t.me/natal_helper_bot'), ('email', 'owner@example.test'), ('phone', '+380 (50) 123-45-67')):
            candidate = deepcopy(detail)
            candidate['configuration']['presentation'] = {**deepcopy(DEFAULT_PRESENTATION), 'cta_target': target}
            if target != 'contacts':
                candidate['content']['contacts'][target] = ''
                with self.assertRaisesRegex(ValueError, 'CTA destination'):
                    self.workspace.approval_ready(candidate)
                candidate['content']['contacts'][target] = endpoint
            self.workspace.approval_ready(candidate)
        instagram = complete_content()
        instagram['contacts'] = {**instagram['contacts'], 'email': '', 'instagram': 'https://www.instagram.com/natal_service/'}
        normalized = normalize_content(instagram)
        self.assertEqual('https://www.instagram.com/natal_service/', normalized['contacts']['instagram'])
        self.workspace.approval_ready(self.prepared(normalized))
        self.assertNotIn('instagram', normalize_content(complete_content())['contacts'])
        for field, values in {'url': ['https://', 'https://example.test/book', 'https://t.me/not_a_bot_user', 'https://t.me/natal_helper_bot?start=landing', 'http://t.me/natal_helper_bot'], 'instagram': ['https://instagram.com/', 'https://instagram.com/natal/service', 'https://evil.test/natal_service', 'http://instagram.com/natal_service'], 'phone': ['call us', '++12345'], 'email': ['a@', 'a b@example.test']}.items():
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
    @unittest.skipUnless(LocalLandingAuthority is not None and Image is not None, 'Landing runtime dependencies required')
    def test_manual_agent_returns_bounded_unsaved_draft_and_preserves_owner_evidence(self):
        from validation_pipeline.landing_pages import LandingService

        landing_id = "01900000-0000-7000-8000-000000000011"
        project_id = "01900000-0000-7000-8000-000000000012"

        class Authority:
            def __init__(self):
                self.page = {
                    "landing_id": landing_id, "project_id": project_id,
                    "source_brief_id": "01900000-0000-7000-8000-000000000013",
                    "status": "draft", "state_sha256": None,
                }

            def get_page(self, _landing_id):
                return self.page

        class Provider:
            change_contact = False
            change_optional_controls = False

            def call(self, **kwargs):
                edits = [{
                    "path": "content.hero.title",
                    "value": "Agent-adjusted Landing headline",
                }]
                if self.change_optional_controls:
                    edits.extend((
                        {"path": "configuration.presentation.spacing", "value": "airy"},
                        {"path": "content.app_feature.title", "value": "Agent-adjusted app feature"},
                    ))
                if self.change_contact:
                    edits.append({
                        "path": "content.contacts.email", "value": "invented@example.test",
                    })
                value = {
                    "edits": edits, "image_actions": [],
                    "reply": "Adjusted the Landing hierarchy.",
                }
                return {
                    "response": kwargs["response_validator"](value),
                    "invocation": {"provider": "fake"},
                }

        with tempfile.TemporaryDirectory() as root:
            authority, provider = Authority(), Provider()
            service = LandingService(
                root=root, authority=authority,
                workspace_factory=lambda path: LandingWorkspace(path, image_provider=FakeImages()),
                structured_provider=provider,
                composer_skill_path=Path("skills/landing-page-composer/SKILL.md"),
            )
            workspace = service._workspace(landing_id)
            initial = workspace.detail()
            content = complete_content()
            content.pop("app_feature")
            initial = workspace.save_configuration(
                base_sha256=initial["state_sha256"],
                configuration=initial["configuration"], content=content,
            )
            authority.page["state_sha256"] = initial["state_sha256"]

            result = service.manual_agent_edit(
                project_id, landing_id,
                request_id="01900000-0000-7000-8000-000000000014",
                base_sha256=initial["state_sha256"], message="Make the hero clearer",
                history=[], configuration=initial["configuration"], content=initial["content"],
                screenshots=[],
            )
            self.assertEqual("Agent-adjusted Landing headline", result["content"]["hero"]["title"])
            self.assertEqual(initial["content"]["contacts"], result["content"]["contacts"])
            self.assertEqual(initial["content"]["social_proof"], result["content"]["social_proof"])
            self.assertNotIn("presentation", result["configuration"])
            self.assertNotIn("app_feature", result["content"])
            self.assertEqual(initial["state_sha256"], workspace.detail()["state_sha256"])
            provider.change_optional_controls = True
            expanded = service.manual_agent_edit(
                project_id, landing_id,
                request_id="01900000-0000-7000-8000-000000000016",
                base_sha256=initial["state_sha256"], message="Use airy spacing and adjust the app feature",
                history=[], configuration=initial["configuration"], content=initial["content"],
                screenshots=[],
            )
            self.assertEqual("airy", expanded["configuration"]["presentation"]["spacing"])
            self.assertEqual("Agent-adjusted app feature", expanded["content"]["app_feature"]["title"])
            self.assertIn("configuration.presentation.spacing", expanded["changed_paths"])
            self.assertIn("content.app_feature.title", expanded["changed_paths"])
            provider.change_optional_controls = False
            provider.change_contact = True
            with self.assertRaisesRegex(ValueError, "edit path"):
                service.manual_agent_edit(
                    project_id, landing_id,
                    request_id="01900000-0000-7000-8000-000000000015",
                    base_sha256=initial["state_sha256"], message="Invent contact details",
                    history=[], configuration=initial["configuration"], content=initial["content"],
                    screenshots=[],
                )

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

    def test_instagram_contact_is_optional_bounded_owner_evidence(self):
        legacy = complete_content()
        self.assertNotIn('instagram', normalize_content(legacy)['contacts'])
        supplied = deepcopy(legacy)
        supplied['contacts']['instagram'] = 'https://www.instagram.com/natal_service/'
        self.assertEqual(
            'https://www.instagram.com/natal_service/',
            normalize_content(supplied)['contacts']['instagram'],
        )
        for value in (
            'http://www.instagram.com/natal_service/',
            'https://www.instagram.com/',
            'https://www.instagram.com/natal/service',
            'https://www.instagram.com/natal_service//',
            'https://example.test/natal_service',
        ):
            invalid = deepcopy(legacy)
            invalid['contacts']['instagram'] = value
            with self.assertRaisesRegex(ValueError, 'instagram'):
                normalize_content(invalid)

    @unittest.skipUnless(LocalLandingAuthority is not None and Image is not None, 'Landing runtime dependencies required')
    def test_generation_preserves_server_configuration_and_accepts_content_only(self):
        from validation_pipeline.landing_pages import (
            LANDING_COMPOSER_PROMPT_VERSION, LandingService,
        )

        landing_id = "01900000-0000-7000-8000-000000000001"
        project_id = "01900000-0000-7000-8000-000000000002"
        brief_id = "01900000-0000-7000-8000-000000000003"
        generated = complete_content()
        generated["social_proof"]["items"] = []
        generated["contacts"].update({"email": "", "phone": "", "url": ""})

        class Authority:
            def __init__(self):
                self.page = {
                    "landing_id": landing_id, "project_id": project_id,
                    "source_brief_id": brief_id, "status": "queued",
                    "source_post_snapshot": {
                        "template_id": "phone_metrics",
                        "configuration": {"must_not_reach_ai": True},
                        "content": {"hero_title": "Frozen source copy"},
                        "assets": ["must_not_reach_ai"], "generation": {},
                        "version_sha256": "a" * 64,
                    },
                }
                self.runs = []

            def get_page(self, _landing_id):
                return self.page

            def brief(self, _brief_id):
                return {"approved": True, "document": {"language": "en"}}

            def latest_skill(self, _scope, _project_id=None):
                return {"content": "No owner-approved Landing lessons yet.", "content_sha256": "b" * 64}

            def update_page(self, _landing_id, **patch):
                self.page.update(deepcopy(patch))
                return self.page

            def record_generation_run(self, **value):
                self.runs.append(value)

        class Provider:
            def call(self, **kwargs):
                self.kwargs = kwargs
                return {
                    "response": kwargs["response_validator"]({"content": generated}),
                    "invocation": {"bridge_attempt": 1, "request_fingerprint": "c" * 64},
                }

        with tempfile.TemporaryDirectory() as root:
            authority, provider, images = Authority(), Provider(), FakeImages()
            service = LandingService(
                root=root, authority=authority,
                workspace_factory=lambda path: LandingWorkspace(path, image_provider=images),
                structured_provider=provider,
                composer_skill_path=Path("skills/landing-page-composer/SKILL.md"),
            )
            workspace = service._workspace(landing_id)
            detail = workspace.detail()
            configuration = deepcopy(detail["configuration"])
            configuration["theme"]["accent_color"] = "#123456"
            workspace.save_configuration(
                base_sha256=detail["state_sha256"], configuration=configuration,
                content=detail["content"],
            )

            service.generate(landing_id)

            self.assertEqual(configuration, workspace.detail()["configuration"])
            self.assertEqual(generated, workspace.detail()["content"])
            self.assertEqual("draft", authority.page["status"])
            self.assertEqual(LANDING_COMPOSER_PROMPT_VERSION, provider.kwargs["prompt_version"])
            self.assertEqual({"content"}, set(provider.kwargs["output_schema"]["properties"]))
            self.assertEqual("ptw.landing.catalog.v2", provider.kwargs["input_payload"]["live_landing_catalog"]["schema"])
            self.assertEqual(["catalog_brand_and_brief", "explicit_owner_direction", "project_rules", "global_spirit", "template_defaults"], provider.kwargs["input_payload"]["active_creative_skills"]["precedence"])
            self.assertNotIn("configuration", provider.kwargs["input_payload"]["source_post_copy"])

    @unittest.skipUnless(LocalLandingAuthority is not None, 'Landing service dependencies required')
    def test_selected_image_styles_override_post_and_keep_slot_crops(self):
        from validation_pipeline.landing_design import DEFAULT_IMAGE_DIRECTIONS, PHONE_HERO_STYLE_DIRECTIVES, LANDING_BACKGROUND_DIRECTIVES
        from validation_pipeline.landing_pages import LandingService
        service = object.__new__(LandingService)
        page = {'landing_id': 'page', 'project_id': 'project', 'source_brief_id': 'brief', 'source_post_snapshot': {'template_id': 'phone_metrics', 'configuration': {}, 'content': {}, 'version_sha256': 'a' * 64}}
        service.analytics = None
        service.authority = Mock()
        service.authority.brief.return_value = {'brief_id': 'brief', 'document': {'product': 'Hotel service'}}
        service._workspace = Mock()
        service._workspace.return_value._history.return_value = []
        service._workspace.return_value._content.return_value = deepcopy(DEFAULT_CONTENT)
        service._workspace.return_value.state_sha256.return_value = 'a' * 64
        for style, directive in PHONE_HERO_STYLE_DIRECTIVES.items():
            for background, treatment in LANDING_BACKGROUND_DIRECTIVES.items():
                config = {**deepcopy(DEFAULT_CONFIGURATION), 'image_directions': deepcopy(DEFAULT_IMAGE_DIRECTIONS)}
                config['theme']['accent_color'] = '#123456'
                config['image_directions']['hero_visual'] = {'style': style, 'background': background}
                prompt = service._image_prompt(page, 'hero_visual', 'A small cabinet', config)
                self.assertIn(directive, prompt)
                self.assertIn(treatment, prompt)
                self.assertIn('#123456', prompt)
                self.assertIn('visible crop', prompt)
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
            service.analytics = None
            service.authority.brief.return_value = {'brief_id': 'brief', 'document': {'product': 'Hotel service'}}
            service.authority.get_page.return_value = {'landing_id': 'page', 'project_id': 'project', 'source_brief_id': 'brief', 'source_post_snapshot': {'template_id': 'phone_metrics', 'configuration': {}, 'content': {}, 'version_sha256': 'a' * 64}}
            generated = service.mutate('project', 'page', 'generate_visual', base_sha256=workspace.detail()['state_sha256'], slot='hero_visual', visual_direction='A paper cabinet')
            self.assertIn('Handmade tactile materials', provider.generate.call_args.args[0])
            raw = (workspace.assets / f"{generated['assets'][0]['sha256']}.png").read_bytes()
            config['image_directions']['hero_visual']['style'] = 'contemporary_3d'
            changed = workspace.save_configuration(base_sha256=generated['state_sha256'], configuration=config, content=complete_content())
            service.mutate('project', 'page', 'generate_visual', base_sha256=changed['state_sha256'], slot='hero_visual', visual_direction='A dimensional cabinet', enhance_current=True)
            self.assertIn('Tactile contemporary 3D', provider.generate.call_args.args[0])
            self.assertEqual(raw, provider.generate.call_args.kwargs['reference_image'])
