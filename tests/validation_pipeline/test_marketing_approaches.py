"""Approach selection, immutable lineage, legacy contracts and shared context."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests.validation_pipeline.test_local_briefs import BRIEF, FakeProvider, brief_response
from validation_pipeline.domain import ProductBriefV1, ProductBriefV2, product_brief_schema
from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.local_briefs import LocalBriefService
from validation_pipeline.marketing import generation_settings, verified_settings
from validation_pipeline.service import validate_create_input, validate_revision_input
from validation_pipeline.studio_manual_agent import manual_agent_brief_context
from validation_pipeline.image_generation_policy import build_image_context, instruction_context

ROOT = Path(__file__).resolve().parents[2]


def document(selected="identity_led"):
    return brief_response({"input_payload": {"marketing_approach": selected},
                           "output_schema": product_brief_schema("en", generation_settings=generation_settings(selected))})


class MarketingContractTests(unittest.TestCase):
    def test_both_profiles_have_selected_examples_and_integrity(self):
        benefit, identity = (generation_settings(v) for v in ("benefit_led", "identity_led"))
        self.assertNotEqual(benefit["policy_sha256"], identity["policy_sha256"])
        self.assertNotIn("Touchland/Jolie", benefit["policy_text"])
        for example in ("Touchland/Jolie", "Gathre", "Graza", "Loop/Stanley", "Starface/Welly", "Liquid Death", "Heyday"):
            self.assertIn(example, identity["policy_text"])
        self.assertEqual(identity, verified_settings(identity))
        with self.assertRaisesRegex(ValueError, "integrity"):
            verified_settings({**identity, "policy_text": "changed"})

    def test_v1_stays_strict_and_v2_binds_the_selected_approach(self):
        self.assertEqual(BRIEF, ProductBriefV1.from_dict(BRIEF, raw_idea="Planner").to_dict())
        value = document()
        result = ProductBriefV2.from_dict(value, raw_idea="Planner", marketing_approach="identity_led")
        self.assertEqual(value, result.to_dict())
        with self.assertRaises(ValueError):
            ProductBriefV1.from_dict(value, raw_idea="Planner")
        with self.assertRaisesRegex(ValueError, "selection"):
            ProductBriefV2.from_dict(value, raw_idea="Planner", marketing_approach="benefit_led")
        value["positioning"]["extra"] = "Not allowed"
        with self.assertRaises(ValueError):
            ProductBriefV2.from_dict(value, raw_idea="Planner")

    def test_positioning_language_proof_optional_identity_and_utf8_limit(self):
        value = document("benefit_led")
        value["positioning"]["desired_identity"] = ""
        self.assertEqual("", ProductBriefV2.from_dict(value, raw_idea="Planner").value["positioning"]["desired_identity"])
        for invalid in ("trusted by 500 customers", "Планувати свій день", 42):
            value["positioning"]["functional_value"] = invalid
            with self.assertRaises(ValueError):
                ProductBriefV2.from_dict(value, raw_idea="Planner")
        from tests.validation_pipeline.test_studio_agent_copy import BRIEF as UK_BRIEF
        value = {**deepcopy(UK_BRIEF), "schema_version": 2, "positioning": document()["positioning"]}
        for field in ("desired_identity", "customer_tension", "category_frame", "functional_value"):
            value["positioning"][field] = "Вода для вибору"
        ProductBriefV2.from_dict(value, raw_idea="Вода", required_language="uk")
        for field in ("desired_identity", "customer_tension", "category_frame", "functional_value"):
            value["positioning"][field] = "В" * 180
        with self.assertRaisesRegex(ValueError, "1024 UTF-8"):
            ProductBriefV2.from_dict(value, raw_idea="Вода", required_language="uk")

    def test_request_contracts_reject_unknown_approaches(self):
        request = {"request_id": str(uuid4()), "raw_idea": "Planner", "language": "en"}
        self.assertNotIn("marketing_approach", validate_create_input(request))
        self.assertEqual("identity_led", validate_create_input({**request, "marketing_approach": "identity_led"})["marketing_approach"])
        for value in (None, "luxury", [], 1):
            with self.assertRaises(ValueError):
                validate_create_input({**request, "marketing_approach": value})
            with self.assertRaises(ValueError):
                validate_revision_input({"request_id": request["request_id"], "instruction": "Change it", "marketing_approach": value})

    def test_manual_and_image_context_keep_exact_source_positioning(self):
        value = document()
        brief = {"brief_id": str(uuid4()), "project_id": str(uuid4()), "approved": True, "document": value}
        manual = manual_agent_brief_context(brief, brief_id=brief["brief_id"], project_id=brief["project_id"])
        image = build_image_context(direction="A shopper comparing labels", instruction=instruction_context("A shopper comparing labels"),
            brief=brief, settings={}, destination={"surface": "post", "slot": "phone_screen", "mode": "image"},
            operation="generate", base_sha256="a" * 64)
        self.assertEqual(value, manual["document"])
        self.assertEqual(value["positioning"], image["brief"]["document"]["positioning"])
        self.assertNotIn("generation_settings", image["brief"])


class MarketingLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = LocalBriefStore(Path(self.directory.name))
        self.service = LocalBriefService(store=self.store, provider=FakeProvider(), repository_root=ROOT)
        self.project, _ = self.service.create_project(request_id=str(uuid4()), name="Planner", requested_by="test")

    def create(self, **changes):
        request = {"project_id": self.project["project_id"], "request_id": str(uuid4()), "raw_idea": "A daily planner", "required_language": "en", "requested_by": "test", **changes}
        return request, self.service.create_brief(**request)[1]

    def test_default_identity_idempotency_and_restart(self):
        request, queued = self.create(marketing_approach="identity_led")
        self.assertEqual(queued, self.service.create_brief(**request)[1])
        with self.assertRaises(ValueError):
            self.service.create_brief(**{**request, "marketing_approach": "benefit_led"})
        completed = self.service.generate_brief(queued["brief_id"])
        self.assertEqual("completed", completed["status"])
        restored = LocalBriefService(store=LocalBriefStore(self.store.root), provider=FakeProvider(), repository_root=ROOT)
        self.assertEqual(completed["document_sha256"], restored.get_brief(queued["brief_id"])["document_sha256"])
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.store.append("briefs", queued["brief_id"], {**completed, "generation_settings": generation_settings()})

    def test_switch_creates_unapproved_replacement_and_keeps_lineage(self):
        request, queued = self.create()
        self.assertEqual("benefit_led", queued["generation_settings"]["marketing_approach"])
        self.assertEqual(queued, self.service.create_brief(**{**request, "marketing_approach": "benefit_led"})[1])
        completed = self.service.generate_brief(queued["brief_id"])
        approved, _ = self.service.approve_brief(queued["brief_id"], "test")
        correction = {"request_id": str(uuid4()), "instruction": "Use the selected approach", "requested_by": "test", "marketing_approach": "identity_led"}
        replacement, created = self.service.correct_brief(queued["brief_id"], **correction)
        self.assertTrue(created)
        with patch("validation_pipeline.local_briefs.correction_settings", side_effect=AssertionError("duplicate must use its reservation")):
            self.assertEqual(replacement["brief_id"], self.service.correct_brief(queued["brief_id"], **correction)[0]["brief_id"])
        with self.assertRaises(ValueError):
            self.service.correct_brief(queued["brief_id"], **{**correction, "marketing_approach": "benefit_led"})
        generated = self.service.generate_brief(replacement["brief_id"])
        self.assertFalse(generated["approved"])
        self.assertEqual("identity_led", generated["positioning"]["marketing_approach"])
        self.assertEqual(approved, self.service.get_brief(queued["brief_id"]))
        self.assertEqual(completed["document_sha256"], approved["document_sha256"])
        self.assertEqual(1, len(self.store.list("feedback")))
        self.assertEqual(1, len(self.store.list("weight_updates")))
        inherited, _ = self.service.correct_brief(replacement["brief_id"], request_id=str(uuid4()), instruction="Shorten copy", requested_by="test")
        self.assertEqual(generated["generation_settings"], inherited["generation_settings"])

    def test_failed_retry_keeps_snapshot_even_after_policy_changes(self):
        _, queued = self.create(marketing_approach="identity_led")
        with patch.object(self.service.provider, "call", side_effect=TimeoutError("test")):
            self.assertEqual("failed", self.service.generate_brief(queued["brief_id"])["status"])
        self.service.retry_brief(queued["brief_id"])
        with patch("validation_pipeline.marketing.generation_settings", side_effect=AssertionError("must not reload policy")):
            completed = self.service.generate_brief(queued["brief_id"])
        self.assertEqual("completed", completed["status"])
        self.assertEqual(queued["generation_settings"], completed["generation_settings"])

    def test_historical_reservation_retries_with_v1_and_correction_upgrades(self):
        # Construct a saved pre-feature record, without modifying a new reservation.
        source_id, brief_id = str(uuid4()), str(uuid4())
        self.store.append("sources", source_id, {"content": "Planner", "required_language": "en"})
        self.store.append("briefs", brief_id, {"brief_id": brief_id, "project_id": self.project["project_id"],
            "owner_idea_source_id": source_id, "raw_idea": "Planner", "status": "failed", "failure_count": 1,
            "approved": False, "document": None, "document_sha256": None})
        self.service.retry_brief(brief_id)
        completed = self.service.generate_brief(brief_id)
        self.assertEqual(1, completed["document"]["schema_version"])
        replacement, _ = self.service.correct_brief(brief_id, request_id=str(uuid4()), instruction="Improve clarity", requested_by="test")
        self.assertEqual(2, self.service.generate_brief(replacement["brief_id"])["document"]["schema_version"])

    def test_post_landing_and_artwork_keep_source_after_a_newer_brief(self):
        from tests.validation_pipeline.test_studio_creatives import FakeStructuredProvider, FakeImageProvider, PHONE_DIRECTION
        from tests.validation_pipeline.test_app_showcase import ContentProvider, REFERENCE
        from tests.validation_pipeline.test_landing_workspace import FakeImages
        from validation_pipeline.studio_creatives import LocalStudioAuthority, StudioCreativeService
        from validation_pipeline.studio_workspace import PostStudioWorkspace
        from validation_pipeline.landing_pages import LocalLandingAuthority, LandingService
        from validation_pipeline.landing_workspace import LandingWorkspace

        _, queued = self.create(marketing_approach="identity_led")
        self.service.generate_brief(queued["brief_id"])
        original, _ = self.service.approve_brief(queued["brief_id"], "test")
        provider, images = FakeStructuredProvider(), FakeImageProvider()
        post_root = self.store.root / "studio"
        posts = StudioCreativeService(root=post_root, authority=LocalStudioAuthority(self.store),
            workspace_factory=lambda path: PostStudioWorkspace(path, image_provider=images), structured_provider=provider,
            composer_skill_path=ROOT / "skills/studio-creative-composer/SKILL.md",
            phone_skill_path=ROOT / "skills/studio-phone-hero-generator/SKILL.md",
            manual_agent_skill_path=ROOT / "skills/studio-manual-agent/SKILL.md")
        post, _ = posts.reserve_from_brief(brief_id=original["brief_id"], template_id="phone_metrics",
            requested_by="test", creative_direction=PHONE_DIRECTION)
        replacement, _ = self.service.correct_brief(original["brief_id"], request_id=str(uuid4()),
            instruction="Change approach", requested_by="test", marketing_approach="benefit_led")
        self.service.generate_brief(replacement["brief_id"])
        self.service.approve_brief(replacement["brief_id"], "test")
        pid, cid = original["project_id"], post["creative_id"]
        posts.generate(cid)
        detail = posts.detail(pid, cid)
        self.assertEqual("draft", detail["status"])
        self.assertEqual(original["document"], provider.calls[0]["input_payload"]["approved_product_brief"])
        self.assertEqual(original["positioning"], detail["assets"][0]["source"]["image_context"]["brief"]["document"]["positioning"])
        posts.checkpoint(pid, cid, kind="approve", base_sha256=detail["state_sha256"],
            configuration=detail["configuration"], content=detail["content"], change_note="Test source lineage")
        landing_provider = ContentProvider()
        landings = LandingService(root=self.store.root / "landings",
            authority=LocalLandingAuthority(self.store, post_workspace_root=post_root),
            workspace_factory=lambda path: LandingWorkspace(path, image_provider=FakeImages()),
            structured_provider=landing_provider, composer_skill_path=ROOT / "skills/landing-page-composer/SKILL.md")
        self.addCleanup(landings.operations.close)
        landing, _ = landings.reserve_from_post(project_id=pid, source_creative_id=cid,
            source_version=1, requested_by="test", template_reference=REFERENCE)
        landings.generate(landing["landing_id"])
        landing = landings.detail(pid, landing["landing_id"])
        self.assertEqual("draft", landing["status"])
        self.assertEqual(original["document"], landing_provider.calls[0]["input_payload"]["approved_product_brief"])
        self.assertEqual("identity_led", landing["marketing_approach"])
        for asset in landing["assets"]:
            source = landings._workspace(landing["landing_id"])._history(asset["slot"])[-1]["source"]
            self.assertEqual(original["positioning"], source["image_context"]["brief"]["document"]["positioning"])
