from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from commander.ids import new_uuid7
from validation_pipeline.local_brief_store import LocalBriefStore, utc_now
from validation_pipeline.studio_creatives import (
    LocalStudioAuthority, StudioCreativeService, creative_generation_schema,
)
from validation_pipeline.studio_workspace import UniversalStudioWorkspace


def _png(color: str = "#f4f3ef") -> bytes:
    output = BytesIO()
    Image.new("RGB", (1024, 1024), color).save(output, format="PNG")
    return output.getvalue()


class FakeStructuredProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.learning_failures = 0
        self.invalid_generation = False
        self.unsafe_global_proposal = False

    def generate(self, **request):
        self.calls.append(deepcopy(request))
        if request["mode"] == "studio_creative_generation":
            defaults = request["input_payload"]["template_defaults"]
            response = {
                "configuration": deepcopy(defaults["configuration"]),
                "content": deepcopy(defaults["content"]),
            }
            if self.invalid_generation:
                response["configuration"]["invented_control"] = True
            response["content"]["hero_title"] = "A clear promise for this audience"
            if request["input_payload"]["selected_template_id"] == "phone_metrics":
                response["visual_direction"] = (
                    "A translucent staircase rising through calm blue studio light"
                )
            return {
                "response": response,
                "invocation": {"provider": "fake", "model": "test-composer"},
            }
        if request["mode"] == "studio_edit_learning":
            if self.learning_failures:
                self.learning_failures -= 1
                raise RuntimeError("temporary learning provider failure")
            return {
                "response": {
                    "edit_summary": "The owner made the headline more direct.",
                    "project_lesson": "Prefer a direct headline for this Project audience.",
                    "global_rule": (
                        f"Always reuse {request['input_payload']['project_name']} campaign copy."
                        if self.unsafe_global_proposal
                        else "Prefer direct headlines when the template has limited space."
                    ),
                },
                "invocation": {"provider": "fake", "model": "test-learner"},
            }
        raise AssertionError(request["mode"])


class FakeImageProvider:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.prompts: list[str] = []
        self.references: list[bytes | None] = []

    def generate(self, prompt: str, *, reference_image: bytes | None = None):
        self.prompts.append(prompt)
        self.references.append(reference_image)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary image provider failure")
        colors = ("#f4f3ef", "#e7eff8", "#f5e8ee", "#e9f3e7")
        return {
            "bytes": _png(colors[(len(self.prompts) - 1) % len(colors)]),
            "mime_type": "image/png",
            "source": {
                "origin": "codex_builtin_image_generation",
                "provider": "fake-image", "model": "test-image",
                "text_in_screen": "prohibited_by_prompt",
            },
        }


class StudioCreativeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = LocalBriefStore(self.root / "briefs")
        self.authority = LocalStudioAuthority(self.store)
        self.provider = FakeStructuredProvider()
        self.images = FakeImageProvider()
        repository = Path(__file__).resolve().parents[2]
        self.service = StudioCreativeService(
            root=self.root / "studio", authority=self.authority,
            workspace_factory=lambda path: UniversalStudioWorkspace(
                path, image_provider=self.images,
            ),
            structured_provider=self.provider,
            composer_skill_path=repository / "skills/studio-creative-composer/SKILL.md",
            learner_skill_path=repository / "skills/studio-edit-learner/SKILL.md",
            phone_skill_path=repository / "skills/studio-phone-hero-generator/SKILL.md",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def approved_brief(self, name: str = "Project Alpha") -> tuple[str, str]:
        project_id, brief_id = new_uuid7(), new_uuid7()
        now = utc_now()
        self.store.append("projects", project_id, {
            "project_id": project_id, "request_id": new_uuid7(),
            "owner_idea_source_id": new_uuid7(), "name": name,
            "name_source": "owner", "requested_by": "test",
            "created_at": now, "updated_at": now,
        })
        self.store.append("briefs", brief_id, {
            "brief_id": brief_id, "project_id": project_id,
            "project_name": name, "request_id": new_uuid7(),
            "owner_idea_source_id": new_uuid7(), "raw_idea": "A useful product",
            "base_brief_id": None, "feedback_id": None,
            "required_language": "en", "status": "completed",
            "document": {
                "schema_version": 1, "language": "en", "product": "Useful product",
                "target_audience": "Independent operators", "main_pain": "Lost time",
                "promise": "Reach the next decision faster", "key_benefits": [
                    "Clear next step", "Less busywork", "Honest guidance",
                ],
                "cta": "Start now", "trust_strategy": "Show the workflow",
                "offer": "A guided first setup",
            },
            "document_sha256": "a" * 64, "failure_count": 0,
            "approved": True, "created_at": now, "updated_at": now,
        })
        self.authority.ensure_project_skill(project_id)
        return project_id, brief_id

    def generate_creative(self, template_id: str = "universal_ad"):
        project_id, brief_id = self.approved_brief()
        creative, created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id=template_id, requested_by="test",
        )
        self.assertTrue(created)
        self.service.generate(creative["creative_id"])
        return project_id, brief_id, self.service.detail(project_id, creative["creative_id"])

    def test_common_templates_and_project_isolation(self) -> None:
        catalog = self.service.templates()
        self.assertEqual({"phone_metrics", "universal_ad"}, {
            item["template_id"] for item in catalog["items"]
        })
        self.assertTrue(all(item["template_sha256"] for item in catalog["items"]))

        first_project, _brief, first = self.generate_creative()
        second_project, _brief, second = self.generate_creative()
        self.assertNotEqual(first["creative_id"], second["creative_id"])
        self.assertNotEqual(first_project, second_project)
        with self.assertRaises(KeyError):
            self.service.detail(second_project, first["creative_id"])

    def test_duplicate_first_creative_reservation_is_idempotent(self) -> None:
        project_id, brief_id = self.approved_brief()
        first, first_created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="universal_ad", requested_by="test",
        )
        duplicate, duplicate_created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="universal_ad", requested_by="test",
        )

        self.assertTrue(first_created)
        self.assertFalse(duplicate_created)
        self.assertEqual(first["creative_id"], duplicate["creative_id"])
        self.assertEqual("universal_ad", duplicate["template_id"])
        self.assertEqual(1, len(self.authority.list_creatives(project_id)))
        with self.assertRaisesRegex(ValueError, "different Studio template"):
            self.service.reserve_from_brief(
                brief_id=brief_id, template_id="phone_metrics", requested_by="test",
            )

    def test_stale_creative_state_is_rejected_before_mutation(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        content = deepcopy(detail["content"])
        content["cta"] = "A new action"
        with self.assertRaisesRegex(RuntimeError, "reload before saving"):
            self.service.mutate(
                project_id, detail["creative_id"], "save_configuration",
                base_sha256="0" * 64, configuration=detail["configuration"],
                content=content,
            )

    def test_invalid_composer_output_leaves_an_explicit_retryable_creative(self) -> None:
        project_id, brief_id = self.approved_brief()
        creative, _created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="universal_ad", requested_by="test",
        )
        self.provider.invalid_generation = True
        failed = self.service.generate(creative["creative_id"])
        self.assertEqual("failed", failed["status"])
        self.assertEqual("failed", failed["generation"]["stage"])
        self.assertIn("fields", failed["generation"]["error_message"])

        queued = self.service.retry_generation(project_id, creative["creative_id"])
        self.assertEqual("queued", queued["status"])
        self.provider.invalid_generation = False
        self.assertEqual("draft", self.service.generate(creative["creative_id"])["status"])

    def test_phone_generation_uses_brief_composition_and_all_skill_layers(self) -> None:
        project_id, _brief_id, detail = self.generate_creative("phone_metrics")

        self.assertEqual("draft", detail["status"])
        self.assertEqual("completed", detail["generation"]["phone_image"]["status"])
        self.assertEqual([None], self.images.references)
        self.assertIn("Studio Phone Hero Generator", self.images.prompts[0])
        self.assertIn("Accepted global Studio lessons", self.images.prompts[0])
        self.assertIn("Accepted Project Studio lessons", self.images.prompts[0])
        self.assertIn("no readable text", self.images.prompts[0])
        self.assertEqual(1, self.authority.latest_skill("project", project_id)["version"])
        generation_call = next(
            call for call in self.provider.calls
            if call["mode"] == "studio_creative_generation"
        )
        self.assertEqual(project_id, detail["project_id"])
        self.assertIn("approved_product_brief", generation_call["input_payload"])
        self.assertIn("live_template_catalog", generation_call["input_payload"])
        runs = [
            item for item in self.store.list("studio_generation_runs")
            if item["creative_id"] == detail["creative_id"]
        ]
        self.assertEqual({"composition", "phone_image"}, {item["stage"] for item in runs})
        for run in runs:
            self.assertEqual(detail["source_brief_id"], run["provenance"]["source_brief_id"])
            self.assertEqual("phone_metrics", run["provenance"]["template_id"])
            self.assertRegex(run["provenance"]["global_skill_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(run["provenance"]["project_skill_sha256"], r"^[0-9a-f]{64}$")

    def test_phone_composer_schema_enforces_the_renderer_text_limits(self) -> None:
        _project_id, brief_id = self.approved_brief()
        creative, _created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="phone_metrics", requested_by="test",
        )
        detail = self.service._workspace(creative["creative_id"]).detail()
        schema = creative_generation_schema(detail)
        content = schema["properties"]["content"]["properties"]

        self.assertEqual({"minLength": 1, "maxLength": 32}, {
            key: content["offer"][key] for key in ("minLength", "maxLength")
        })
        self.assertEqual({"minLength": 1, "maxLength": 24}, {
            key: content["stats"]["items"]["properties"]["value"][key]
            for key in ("minLength", "maxLength")
        })

    def test_runtime_skill_digest_is_verified_before_generation(self) -> None:
        project_id, _brief_id = self.approved_brief()
        snapshot_id = new_uuid7()
        self.store.append("studio_skill_snapshots", snapshot_id, {
            "skill_snapshot_id": snapshot_id, "scope": "project",
            "project_id": project_id, "version": 2,
            "content": "---\nname: studio-runtime-project\ndescription: Test.\n---\n\n# Test\n",
            "content_sha256": "0" * 64, "source_checkpoint_id": None,
            "created_at": "9999-01-01T00:00:00Z",
        })

        with self.assertRaisesRegex(RuntimeError, "digest mismatch"):
            self.authority.latest_skill("project", project_id)

    def test_phone_generation_and_selection_accumulate_in_the_next_checkpoint(self) -> None:
        project_id, _brief_id, baseline = self.generate_creative("phone_metrics")
        original_sha = baseline["phone_screen_history"][0]["sha256"]
        generated = self.service.mutate(
            project_id, baseline["creative_id"], "generate_phone_screen",
            base_sha256=baseline["state_sha256"],
            visual_direction="A calmer translucent structure in blue light",
            enhance_current=False,
        )
        self.assertEqual(2, len(generated["phone_screen_history"]))
        selected = self.service.mutate(
            project_id, baseline["creative_id"], "select_phone_screen",
            base_sha256=generated["state_sha256"], sha256=original_sha,
        )
        checkpoint = self.service.checkpoint(
            project_id, baseline["creative_id"], kind="save",
            base_sha256=selected["state_sha256"],
            configuration=selected["configuration"], content=selected["content"],
        )

        self.assertTrue(checkpoint["checkpoint_created"])
        paths = checkpoint["checkpoint"]["changed_paths"]
        self.assertTrue(any(path.startswith("phone_screen_history") for path in paths))
        saved = self.authority.get_checkpoint(checkpoint["checkpoint"]["checkpoint_id"])
        self.assertEqual(1, len(saved["before_snapshot"]["phone_screen_history"]))
        self.assertEqual(2, len(saved["after_snapshot"]["phone_screen_history"]))

    def test_learning_occurs_once_only_at_a_changed_checkpoint(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        baseline = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=detail["state_sha256"],
            configuration=detail["configuration"], content=detail["content"],
        )
        self.assertFalse(baseline["checkpoint_created"])
        self.assertFalse(any(call["mode"] == "studio_edit_learning" for call in self.provider.calls))

        changed_content = deepcopy(detail["content"])
        changed_content["hero_title"] = "A shorter owner headline"
        changed = self.service.mutate(
            project_id, detail["creative_id"], "save_configuration",
            base_sha256=detail["state_sha256"],
            configuration=detail["configuration"], content=changed_content,
        )
        checkpoint = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=changed["state_sha256"],
            configuration=changed["configuration"], content=changed["content"],
        )
        self.assertTrue(checkpoint["checkpoint_created"])
        self.assertIn("content.hero_title", checkpoint["checkpoint"]["changed_paths"])
        checkpoint_id = checkpoint["checkpoint"]["checkpoint_id"]
        self.assertEqual(
            1, len(self.store.history("studio_edit_checkpoints", checkpoint_id)),
        )
        self.assertEqual(1, len([
            item for item in self.store.list("studio_learning_runs")
            if item["checkpoint_id"] == checkpoint_id
        ]))
        self.assertEqual(2, self.authority.latest_skill("project", project_id)["version"])
        proposal = checkpoint["learning_proposal"]
        self.assertIsNotNone(proposal)

        unchanged = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=checkpoint["creative"]["state_sha256"],
            configuration=checkpoint["creative"]["configuration"],
            content=checkpoint["creative"]["content"],
        )
        self.assertFalse(unchanged["checkpoint_created"])
        self.assertEqual(1, len([
            call for call in self.provider.calls if call["mode"] == "studio_edit_learning"
        ]))
        decision = self.service.decide_learning(
            project_id, detail["creative_id"], proposal["proposal_id"], "global",
        )
        self.assertEqual("global", decision["decision"])
        self.assertEqual(2, self.authority.latest_skill("global")["version"])
        edges = self.store.list("edges")
        project_skill_id = checkpoint["checkpoint"]["project_skill_snapshot_id"]
        self.assertTrue(any(
            edge["source_id"] == project_skill_id
            and edge["relation"] == "derived_from"
            and edge["target_id"] == checkpoint_id
            for edge in edges
        ))
        self.assertTrue(any(
            edge["source_id"] == proposal["proposal_id"]
            and edge["relation"] == "contains"
            and edge["target_id"] == decision["decision_id"]
            for edge in edges
        ))

        other_project, _brief, other = self.generate_creative()
        with self.assertRaises(KeyError):
            self.service.decide_learning(
                other_project, other["creative_id"], proposal["proposal_id"], "project_only",
            )

    def test_variant_requires_the_latest_creative_to_be_approved(self) -> None:
        project_id, brief_id, first = self.generate_creative()
        with self.assertRaisesRegex(ValueError, "approve the current creative"):
            self.service.reserve_from_brief(
                brief_id=brief_id, template_id="universal_ad",
                requested_by="test", additional=True,
            )
        approved = self.service.checkpoint(
            project_id, first["creative_id"], kind="approve",
            base_sha256=first["state_sha256"], configuration=first["configuration"],
            content=first["content"], change_note="First approved creative",
        )
        self.assertTrue(approved["version_created"])
        second, created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="phone_metrics",
            requested_by="test", additional=True,
        )
        self.assertTrue(created)
        self.assertEqual(2, second["ordinal"])
        with self.assertRaisesRegex(ValueError, "approve the current creative"):
            self.service.reserve_from_brief(
                brief_id=brief_id, template_id="universal_ad",
                requested_by="test", additional=True,
            )

    def test_approval_saves_pending_changes_into_the_immutable_version(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        content = deepcopy(detail["content"])
        content["hero_title"] = "The exact owner-approved headline"
        result = self.service.checkpoint(
            project_id, detail["creative_id"], kind="approve",
            base_sha256=detail["state_sha256"], configuration=detail["configuration"],
            content=content, change_note="First owner-approved creative",
        )

        self.assertTrue(result["version_created"])
        self.assertTrue(result["checkpoint_created"])
        self.assertEqual(
            "The exact owner-approved headline", result["creative"]["content"]["hero_title"],
        )
        version = self.service._workspace(detail["creative_id"]).version_detail(1)
        self.assertEqual("ptw.studio.template-version.v1", version["schema"])
        self.assertEqual("The exact owner-approved headline", version["content"]["hero_title"])

    def test_failed_learning_is_queued_and_restart_safe_to_retry(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        self.provider.learning_failures = 1
        content = deepcopy(detail["content"])
        content["cta"] = "Take the next step"
        checkpoint = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=detail["state_sha256"],
            configuration=detail["configuration"], content=content,
        )
        self.assertEqual("queued", checkpoint["checkpoint"]["status"])
        self.assertIsNone(checkpoint["learning_proposal"])
        self.assertEqual(1, self.authority.latest_skill("project", project_id)["version"])
        self.assertEqual(1, len(self.service.recover_learning()))

        recovered = self.service.retry_learning(
            project_id, detail["creative_id"], checkpoint["checkpoint"]["checkpoint_id"],
        )
        self.assertEqual("completed", recovered["checkpoint"]["status"])
        self.assertIsNotNone(recovered["learning_proposal"])
        checkpoint_id = checkpoint["checkpoint"]["checkpoint_id"]
        self.assertEqual(
            1, len(self.store.history("studio_edit_checkpoints", checkpoint_id)),
        )
        self.assertEqual(2, len([
            item for item in self.store.list("studio_learning_runs")
            if item["checkpoint_id"] == checkpoint_id
        ]))
        self.assertEqual(2, self.authority.latest_skill("project", project_id)["version"])
        self.assertEqual([], self.service.recover_learning())

    def test_project_specific_global_proposal_is_rejected_and_retryable(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        self.provider.unsafe_global_proposal = True
        content = deepcopy(detail["content"])
        content["hero_title"] = "Owner-specific final headline"
        checkpoint = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=detail["state_sha256"],
            configuration=detail["configuration"], content=content,
        )

        self.assertEqual("queued", checkpoint["checkpoint"]["status"])
        self.assertIn("project-specific", checkpoint["checkpoint"]["error_message"])
        self.assertIsNone(checkpoint["learning_proposal"])
        self.assertEqual(1, self.authority.latest_skill("project", project_id)["version"])

        self.provider.unsafe_global_proposal = False
        recovered = self.service.retry_learning(
            project_id, detail["creative_id"], checkpoint["checkpoint"]["checkpoint_id"],
        )
        self.assertEqual("completed", recovered["checkpoint"]["status"])
        self.assertIsNotNone(recovered["learning_proposal"])

    def test_phone_failure_keeps_a_draft_and_can_be_retried_separately(self) -> None:
        self.images.failures = 1
        project_id, _brief_id, detail = self.generate_creative("phone_metrics")
        self.assertEqual("draft", detail["status"])
        self.assertEqual("failed", detail["generation"]["phone_image"]["status"])
        self.assertIn("visual_direction", detail["generation"]["phone_image"])

        queued = self.service.queue_phone_image_retry(project_id, detail["creative_id"])
        self.assertEqual("generating_image", queued["status"])
        retried = self.service.retry_phone_image(project_id, detail["creative_id"])
        self.assertEqual("draft", retried["status"])
        self.assertEqual("completed", retried["generation"]["phone_image"]["status"])


if __name__ == "__main__":
    unittest.main()
