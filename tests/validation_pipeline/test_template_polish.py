from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests.validation_pipeline.test_template_authoring import ScriptedTemplateProvider
from validation_pipeline import template_agent as agent
from validation_pipeline.template_authoring import TemplateAuthoringService
from validation_pipeline.template_components import apply_edits, seed
from validation_pipeline.template_polish import PROFILE, changes
from validation_pipeline.template_store import TemplateConflict, TemplateStore


class PolishProvider(ScriptedTemplateProvider):
    edit = {"surface": "post", "path": "components.title.font_size", "value": 56}

    def call(self, **kwargs):
        if kwargs["input_payload"].get("refinement_profile") and kwargs["input_payload"]["phase"] == "compose":
            self.calls.append(kwargs)
            response = kwargs["response_validator"]({"edits": [self.edit], "differences": [], "capability_gap": None, "complete": False})
            return {"response": response}
        return super().call(**kwargs)


class TemplatePolishTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "templates.sqlite3"
        self.provider = PolishProvider()
        self.service = TemplateAuthoringService(TemplateStore(self.path), self.provider, asynchronous=False)
        self.addCleanup(self.service.close)

    def start(self, scope="post"):
        return self.service.start({"request_id": str(uuid4()), "scope": scope, "instruction": "Create reusable design"})

    def polish_request(self, run):
        return {"request_id": str(uuid4()), "base_sha256": run["state_sha256"], "instruction": "polish", "mode": "refine", "refinement_profile": PROFILE}

    def decision(self, run, selection):
        return {"request_id": str(uuid4()), "base_sha256": run["state_sha256"], "decision": "accept", "selection": selection}

    def test_comparison_persists_and_accepts_exact_original_or_refined(self):
        for selection in ("original", "refined"):
            original = self.start()
            self.assertEqual("proposed", original["status"])
            request = self.polish_request(original)
            refined = self.service.resume(original["run_id"], request)
            self.assertEqual("proposed", refined["status"], refined.get("failure"))
            self.assertEqual(original["previews"], refined["polish"]["original"]["previews"])
            self.assertNotEqual(original["previews"], refined["previews"])
            self.assertEqual(["typography"], refined["polish"]["changes"])
            count = len(self.provider.calls)
            self.assertEqual(refined, self.service.resume(original["run_id"], request))
            self.assertEqual(count, len(self.provider.calls))
            self.assertEqual(refined, TemplateStore(self.path).get("run", refined["run_id"]))
            with self.assertRaises(ValueError):
                self.service.decide(refined["run_id"], {k: v for k, v in self.decision(refined, selection).items() if k != "selection"})
            decision = self.decision(refined, selection)
            accepted = self.service.decide(refined["run_id"], decision)
            self.assertEqual(accepted, self.service.decide(refined["run_id"], decision))
            record = self.service.read(accepted["accepted_versions"][0])
            expected = original if selection == "original" else refined
            self.assertEqual(expected["documents"]["post"], record["document"])
            self.assertEqual(expected["previews"]["post:desktop"]["sha256"], record["previews"]["desktop"]["sha256"])
            self.assertIsNotNone(self.service.post_registry().resolve_reference({k:v for k,v in accepted["accepted_versions"][0].items() if k != "surface"}))
            from validation_pipeline.studio_workspace import PostStudioWorkspace
            from validation_pipeline.template_previews import geometry
            workspace = PostStudioWorkspace(Path(self.directory.name) / selection, template_registry=self.service.post_registry)
            detail = workspace.apply_template(base_sha256=workspace.detail()["state_sha256"], template_id=record["template_id"], template_reference=accepted["accepted_versions"][0])
            from validation_pipeline.template_components import placeholder_image
            detail = workspace.store_generated_phone_screen(base_sha256=detail["state_sha256"], data=placeholder_image(),
                source={"origin": "codex_builtin_image_generation", "text_in_screen": "prohibited_by_prompt"})
            for title in ("A clear next step", "Зрозумілий крок"):
                content = deepcopy(detail["content"])
                content["template_text"].update(title=title, support="", action="Explore" if title.startswith("A") else "Дізнатись")
                rendered = workspace.render_preview(state_sha256=detail["state_sha256"], configuration=detail["configuration"], content=content)
                self.assertTrue(rendered["bytes"].startswith(b"\x89PNG"))
                self.assertEqual([], geometry(rendered)[1])

    def test_profile_is_optional_bounded_and_compares_saved_original(self):
        original = self.start()
        self.assertTrue(all("refinement_profile" not in c["input_payload"] for c in self.provider.calls))
        refined = self.service.resume(original["run_id"], self.polish_request(original))
        compose = next(c for c in self.provider.calls if c["input_payload"].get("refinement_profile"))
        self.assertEqual(["baseline:post:desktop"], compose["input_payload"]["image_order"])
        self.assertIn("input_artifacts", compose)
        self.assertLess(agent.preflight("compare", refined)["total"], 52*1024)

    def test_restart_keeps_original_and_does_not_replay_polish(self):
        original = self.start()
        with patch.object(self.service, "_schedule"):
            queued = self.service.resume(original["run_id"], self.polish_request(original))
        count = len(self.provider.calls)
        restarted = TemplateAuthoringService(TemplateStore(self.path), self.provider, asynchronous=False)
        self.addCleanup(restarted.close)
        restarted.recover_interrupted()
        interrupted = restarted.store.get("run", queued["run_id"])
        self.assertEqual("interrupted", interrupted["status"])
        self.assertEqual(count, len(self.provider.calls))
        self.assertEqual(original["previews"], interrupted["polish"]["original"]["previews"])
        refined = restarted.resume(interrupted["run_id"], {"request_id": str(uuid4()), "base_sha256": interrupted["state_sha256"], "instruction": "", "mode": "continue"})
        self.assertEqual("proposed", refined["status"])

    def test_rejects_protected_and_excessive_changes_on_every_provider_step(self):
        original = self.start()
        for path, value in [("background", "#FFFFFF"), ("components.title.font_family", "Georgia"),
                            ("components.title.box", [600, 20, 300, 200]), ("components.title.enabled", False)]:
            run = deepcopy(original)
            run["polish"] = {"original": {"documents": original["documents"]}}
            class InvalidProvider:
                def call(self, **kwargs):
                    return {"response": {"edits": [{"surface": "post", "path": path, "value": value}], "differences": [], "capability_gap": None, "complete": False}}
            with self.subTest(path=path), self.assertRaises(ValueError):
                agent.call(InvalidProvider(), "compare", run, [])

    def test_failed_refinement_keeps_original_and_retries_or_discards(self):
        original = self.start()
        self.provider.timeout_phase = "compare"
        failed = self.service.resume(original["run_id"], self.polish_request(original))
        self.assertEqual("failed", failed["status"])
        self.assertEqual(original["previews"], failed["polish"]["original"]["previews"])
        with self.assertRaises(TemplateConflict):
            self.service.decide(failed["run_id"], self.decision(failed, "refined"))
        self.provider.timeout_phase = None
        retry = {"request_id": str(uuid4()), "base_sha256": failed["state_sha256"]}
        refined = self.service.retry_correction(failed["run_id"], retry)
        self.assertEqual("proposed", refined["status"])
        self.assertEqual(refined, self.service.retry_correction(failed["run_id"], retry))
        restored = self.service.restore_proposal(refined["run_id"], {"request_id": str(uuid4()), "base_sha256": refined["state_sha256"]})
        self.assertEqual(original["previews"], restored["previews"])
        self.assertIsNone(restored["polish"])

    def test_original_can_be_accepted_after_failure_and_stale_selection_is_rejected(self):
        original = self.start()
        self.provider.timeout_phase = "compare"
        failed = self.service.resume(original["run_id"], self.polish_request(original))
        with self.assertRaises(TemplateConflict):
            self.service.decide(failed["run_id"], self.decision(original, "original"))
        accepted = self.service.decide(failed["run_id"], self.decision(failed, "original"))
        self.assertEqual(original["documents"], accepted["documents"])

    def test_polish_is_post_only_and_cannot_replace_an_existing_candidate(self):
        for scope in ("landing", "combined"):
            original = self.start(scope)
            with self.assertRaises(TemplateConflict):
                self.service.resume(original["run_id"], self.polish_request(original))
        original = self.start()
        refined = self.service.resume(original["run_id"], self.polish_request(original))
        with self.assertRaises(TemplateConflict):
            self.service.resume(refined["run_id"], self.polish_request(refined))

    def test_excessive_layout_changes_cannot_be_accepted_as_refined(self):
        original = self.start()
        self.provider.edit = {"surface": "post", "path": "components.title.box", "value": [60, 50, 620, 100]}
        refined = self.service.resume(original["run_id"], self.polish_request(original))
        self.assertNotEqual("proposed", refined["status"])
        with self.assertRaises(TemplateConflict):
            self.service.decide(refined["run_id"], self.decision(refined, "refined"))

    def test_refined_acceptance_checks_preview_geometry_and_definition_digest(self):
        original = self.start()
        refined = self.service.resume(original["run_id"], self.polish_request(original))
        valid_previews = deepcopy(refined["previews"])
        for corruption in ({"failures": [{"issue": "Text overflows its assigned box"}]}, {"definition_sha256": "0"*64}):
            previews = deepcopy(valid_previews)
            previews["post:desktop"].update(corruption)
            refined = self.service._update(refined, previews=previews)
            with self.assertRaises(TemplateConflict):
                self.service.decide(refined["run_id"], self.decision(refined, "refined"))

    def test_native_daddy_keeps_identity_and_bounds(self):
        from validation_pipeline.studio_daddy import neutral_document, default_configuration
        from validation_pipeline.template_components import normalize_document
        original = {"post": normalize_document(neutral_document(default_configuration()))}
        after = apply_edits(original, [{"surface": "post", "path": "daddy_configuration.message.title_size", "value": original["post"]["daddy_configuration"]["message"]["title_size"]+2}])
        self.assertEqual(["typography"], changes(original, after))
        after["post"]["daddy_configuration"]["message"]["color"] = "#123456"
        with self.assertRaises(ValueError):
            changes(original, after)
