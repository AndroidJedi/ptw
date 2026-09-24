from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from commander.ids import new_uuid7
from validation_pipeline.local_brief_store import LocalBriefStore, sha256_json, utc_now
from validation_pipeline.studio_creatives import (
    LocalStudioAuthority, StudioCreativeService, creative_generation_schema,
)
from validation_pipeline.studio_workspace import PostStudioWorkspace


PHONE_DIRECTION = {
    "schema": "ptw.studio.phone-hero-direction.v1",
    "style": "cinematic",
    "background": "scene",
}


def _png(color: str = "#f4f3ef") -> bytes:
    output = BytesIO()
    Image.new("RGB", (1024, 1024), color).save(output, format="PNG")
    return output.getvalue()


class FakeStructuredProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.invalid_generation = False
        self.manual_image_actions: list[dict] = []
        self.manual_logo_colors: dict[str, str] | None = None
        self.manual_phone_update: dict[str, object] = {}
        self.manual_phone_screen_logo: bool | None = None
        self.manual_phone_stats: list[dict[str, str]] | None = None
        self.manual_creative_direction: dict[str, str] | None = None

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
                response["content"]["stats"] = [{"value": "+35%", "label": "More service requests"}, {"value": "−25%", "label": "Fewer calls"}, {"value": "2×", "label": "Faster handling"}]
                response["metric_basis"] = [{"origin": "ai_hypothesis", "evidence": ""} for _ in range(3)]
                response["visual_direction"] = (
                    "A translucent staircase rising through calm blue studio light"
                )
            return {
                "response": response,
                "invocation": {"provider": "fake", "model": "test-composer"},
            }
        if request["mode"] == "studio_manual_edit":
            current = request["input_payload"]["current_editable_values"]
            if "content.hero_title" not in current:
                raise AssertionError("manual Agent payload omitted the editable headline")
            edits = [{"path": "content.hero_title", "value": "Owner-directed agent headline"}]
            if self.manual_logo_colors:
                edits.extend(
                    {"path": f"configuration.logo.{field}", "value": value}
                    for field, value in self.manual_logo_colors.items()
                )
            if request["input_payload"]["surface"] == "post:phone_metrics":
                if "device_enabled" in self.manual_phone_update:
                    edits.append({"path": "configuration.device.enabled", "value": self.manual_phone_update["device_enabled"]})
                if "visual_mode" in self.manual_phone_update:
                    edits.append({"path": "configuration.visual_mode", "value": self.manual_phone_update["visual_mode"]})
                if self.manual_phone_screen_logo is not None:
                    edits.append({"path": "configuration.phone_screen.logo_enabled", "value": self.manual_phone_screen_logo})
            if self.manual_phone_stats is not None:
                for index, stat in enumerate(self.manual_phone_stats):
                    edits.extend((
                        {"path": f"content.stats[{index}].value", "value": stat["value"]},
                        {"path": f"content.stats[{index}].label", "value": stat["label"]},
                    ))
            direction = self.manual_creative_direction
            if direction:
                edits.extend((
                    {"path": "creative_direction.style", "value": direction["style"]},
                    {"path": "creative_direction.background", "value": direction["background"]},
                ))
            response = {
                "edits": edits,
                "image_actions": deepcopy(self.manual_image_actions),
                "reply": "Adjusted the requested editor controls.",
            }
            return {
                "response": response,
                "invocation": {"provider": "fake", "model": "test-agent"},
            }
        raise AssertionError(request["mode"])


class FakeImageProvider:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.prompts: list[str] = []
        self.references: list[bytes | None] = []

    def generate(self, prompt: str, *, reference_image: bytes | None = None, output_spec=None):
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
            workspace_factory=lambda path: PostStudioWorkspace(
                path, image_provider=self.images,
            ),
            structured_provider=self.provider,
            composer_skill_path=repository / "skills/studio-creative-composer/SKILL.md",
            phone_skill_path=repository / "skills/studio-phone-hero-generator/SKILL.md",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_numeric_hypothesis_provenance_survives_approval_edit_and_clone(self):
        project_id, _, detail = self.generate_creative()
        provenance = detail["generation"]["metric_provenance"]
        self.assertEqual(3, len(provenance))
        self.assertTrue(all(item["origin"] == "ai_hypothesis" and item["validation_status"] == "unvalidated" for item in provenance))
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from validation_pipeline.studio_routes import studio_creative_router
        app = FastAPI()
        app.include_router(studio_creative_router(self.service, prefix="/api/v1/studio"))
        with TestClient(app) as client:
            response = client.post(f"/api/v1/studio/projects/{project_id}/creatives/{detail['creative_id']}/approve", json={
                "base_sha256": detail["state_sha256"], "configuration": detail["configuration"],
                "content": detail["content"], "change_note": "Numeric draft", "metric_provenance": provenance})
        self.assertEqual(200, response.status_code, response.text)
        approved = response.json()
        version = self.service._workspace(detail["creative_id"]).version_detail(1)
        self.assertEqual(provenance, version["metric_provenance"])
        current = approved["creative"]
        edited = deepcopy(current["content"])
        edited["stats"][0] = {"value": "Owner wording", "label": "Keep editable"}
        saved = self.service.checkpoint(project_id, detail["creative_id"], kind="save",
            base_sha256=current["state_sha256"], configuration=current["configuration"], content=edited)["creative"]
        self.assertEqual("owner_supplied", saved["generation"]["metric_provenance"][0]["origin"])
        self.assertEqual(provenance, self.service._workspace(detail["creative_id"]).version_detail(1)["metric_provenance"])
        clone, _ = self.service.clone_approved_version(project_id=project_id,
            source_creative_id=detail["creative_id"], source_version=1, request_id=new_uuid7(), requested_by="test")
        self.assertEqual(provenance, clone["generation"]["metric_provenance"])
        self.service._workspaces.clear()
        reloaded = self.service.detail(project_id, detail["creative_id"])
        self.assertEqual("Owner wording", reloaded["generation"]["metric_provenance"][0]["value"])

    def test_hotel_manual_request_carries_brief_settings_origin_and_reference(self):
        project_id, _, detail = self.generate_creative()
        suggestion = detail["assets"][0]["source"]["visual_direction"]
        rerun = self.service.mutate(project_id, detail["creative_id"], "generate_phone_screen",
            base_sha256=detail["state_sha256"], visual_direction=suggestion)
        source = rerun["assets"][0]["source"]
        self.assertEqual("generated", source["image_context"]["instruction"]["origin"])
        owner = "A guest scans a QR card with a smartphone in a hotel room. Include the label SPA."
        generated = self.service.mutate(project_id, detail["creative_id"], "generate_phone_screen",
            base_sha256=rerun["state_sha256"], visual_direction="Guest scanning a hotel card",
            instruction_context={"origin": "agent", "owner_instruction": owner}, enhance_current=True)
        context = generated["assets"][0]["source"]["image_context"]
        self.assertEqual(owner, context["instruction"]["owner_instruction"])
        self.assertEqual(detail["source_brief_id"], context["brief"]["brief_id"])
        self.assertEqual("enhance_current", context["operation"])
        self.assertIn(owner, self.images.prompts[-1])
        self.assertIsNotNone(self.images.references[-1])

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
        return project_id, brief_id

    def add_approved_brief(self, project_id: str, name: str) -> str:
        source = next(
            item for item in self.store.list("briefs")
            if item["project_id"] == project_id
        )
        brief_id = new_uuid7()
        now = utc_now()
        self.store.append("briefs", brief_id, {
            **deepcopy(source), "brief_id": brief_id, "request_id": new_uuid7(),
            "project_name": name, "created_at": now, "updated_at": now,
        })
        return brief_id

    def generate_creative(self, template_id: str = "phone_metrics"):
        project_id, brief_id = self.approved_brief()
        creative, created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id=template_id, requested_by="test",
            creative_direction=PHONE_DIRECTION,
        )
        self.assertTrue(created)
        self.service.generate(creative["creative_id"])
        return project_id, brief_id, self.service.detail(project_id, creative["creative_id"])

    def test_common_templates_and_project_isolation(self) -> None:
        catalog = self.service.templates()
        self.assertEqual({"phone_metrics"}, {
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
            brief_id=brief_id, template_id="phone_metrics", requested_by="test",
            creative_direction=PHONE_DIRECTION,
        )
        duplicate, duplicate_created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="phone_metrics", requested_by="test",
            creative_direction=PHONE_DIRECTION,
        )

        self.assertTrue(first_created)
        self.assertFalse(duplicate_created)
        self.assertEqual(first["creative_id"], duplicate["creative_id"])
        self.assertEqual("phone_metrics", duplicate["template_id"])
        self.assertEqual(1, len(self.authority.list_creatives(project_id)))
        with self.assertRaisesRegex(ValueError, "different Phone Metrics creative direction"):
            self.service.reserve_from_brief(
                brief_id=brief_id, template_id="phone_metrics", requested_by="test",
                creative_direction={**PHONE_DIRECTION, "style": "premium_editorial"},
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

    def test_manual_agent_changes_only_returned_editor_state_and_accepts_ephemeral_screenshot(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        before = deepcopy(self.service.detail(project_id, detail["creative_id"]))
        screenshot = _png("#314159")

        result = self.service.manual_agent_edit(
            project_id, detail["creative_id"], request_id=new_uuid7(),
            base_sha256=detail["state_sha256"], message="Make the headline clearer",
            history=[], configuration=detail["configuration"], content=detail["content"],
            screenshots=[screenshot],
        )

        self.assertEqual("Owner-directed agent headline", result["content"]["hero_title"])
        self.assertIn("content.hero_title", result["changed_paths"])
        self.assertEqual(before["state_sha256"], result["base_sha256"])
        after = self.service.detail(project_id, detail["creative_id"])
        self.assertEqual(before["state_sha256"], after["state_sha256"])
        self.assertEqual(before["content"], after["content"])
        call = self.provider.calls[-1]
        self.assertEqual("studio_manual_edit", call["mode"])
        self.assertEqual("studio_screenshot_1", call["input_artifacts"][0]["name"])
        self.assertNotIn("bytes_base64", call["input_payload"]["image_tools"]["screenshot_references"][0])
        edit_paths = call["output_schema"]["properties"]["edits"]["items"]["properties"]["path"]["enum"]
        self.assertIn("configuration.logo.symbol_color", edit_paths)
        self.assertIn("configuration.logo.name_color", edit_paths)
        self.assertNotIn("live_catalog", call["input_payload"])
        self.assertNotIn("current_editor_state", call["input_payload"])

        self.provider.manual_logo_colors = {
            "symbol_color": "#112233", "name_color": "#445566",
        }
        recolored = self.service.manual_agent_edit(
            project_id, detail["creative_id"], request_id=new_uuid7(),
            base_sha256=detail["state_sha256"], message="Change both Natal logo colors",
            history=[], configuration=detail["configuration"], content=detail["content"],
            screenshots=[],
        )
        self.assertEqual("#112233", recolored["configuration"]["logo"]["symbol_color"])
        self.assertEqual("#445566", recolored["configuration"]["logo"]["name_color"])

    def test_phone_manual_agent_can_plan_one_existing_image_action_without_mutation(self) -> None:
        project_id, _brief_id, detail = self.generate_creative("phone_metrics")
        self.provider.manual_image_actions = [{
            "slot": "phone_screen",
            "visual_direction": "A refined blue glass object in calm studio light",
            "enhance_current": True,
            "reference_index": 0,
        }]
        result = self.service.manual_agent_edit(
            project_id, detail["creative_id"], request_id=new_uuid7(),
            base_sha256=detail["state_sha256"], message="Refine the current hero",
            history=[], configuration=detail["configuration"], content=detail["content"],
            screenshots=[],
        )
        self.assertEqual("phone_screen", result["image_actions"][0]["slot"])
        self.assertTrue(result["image_actions"][0]["enhance_current"])
        self.assertEqual(PHONE_DIRECTION, result["creative_direction"])
        self.assertEqual(detail["state_sha256"], self.service.detail(project_id, detail["creative_id"])["state_sha256"])

    def test_phone_agent_contract_maps_hide_restore_image_only_and_style_without_generation(self) -> None:
        project_id, _brief_id, detail = self.generate_creative("phone_metrics")
        self.provider.manual_phone_update = {"device_enabled": False}
        self.provider.manual_creative_direction = {
            "schema": "ptw.studio.phone-hero-direction.v1",
            "style": "premium_editorial", "background": "isolated_key_element",
        }
        removed = self.service.manual_agent_edit(
            project_id, detail["creative_id"], request_id=new_uuid7(),
            base_sha256=detail["state_sha256"], message="Hide the phone device and choose a premium editorial isolated style",
            history=[], configuration=detail["configuration"], content=detail["content"], screenshots=[],
        )
        self.assertFalse(removed["configuration"]["device"]["enabled"])
        self.assertEqual([], removed["image_actions"])
        self.assertEqual("premium_editorial", removed["creative_direction"]["style"])
        self.assertIn("configuration.device.enabled", removed["changed_paths"])
        contract = self.provider.calls[-1]["input_payload"]["agent_control_contract"]
        self.assertEqual(
            "configuration.device.enabled",
            contract["owner_phrase_mappings"]["hide_or_remove_phone_device"]["setting_path"],
        )

        self.provider.manual_phone_update = {"visual_mode": "image"}
        image_only = self.service.manual_agent_edit(
            project_id, detail["creative_id"], request_id=new_uuid7(),
            base_sha256=detail["state_sha256"], message="Show only the artwork without the phone interface",
            history=[], configuration=detail["configuration"], content=detail["content"], screenshots=[],
        )
        self.assertEqual("image", image_only["configuration"]["visual_mode"])
        self.assertEqual([], image_only["image_actions"])

        self.provider.manual_phone_update = {"device_enabled": True, "visual_mode": "phone"}
        restored = self.service.manual_agent_edit(
            project_id, detail["creative_id"], request_id=new_uuid7(),
            base_sha256=detail["state_sha256"], message="Bring the phone back",
            history=[], configuration=detail["configuration"], content=detail["content"], screenshots=[],
        )
        self.assertTrue(restored["configuration"]["device"]["enabled"])
        self.assertEqual("phone", restored["configuration"].get("visual_mode", "phone"))

    def test_phone_agent_enforces_compound_visible_result_for_reported_ukrainian_prompt(self) -> None:
        project_id, _brief_id, detail = self.generate_creative("phone_metrics")
        message = (
            "Прибери 1 логотип також зроби так ніби це на картинці вигляд домашньої "
            "аптечки і програма класифікує наявні медикаменти у програмі спробуй "
            "прибрати телефон на нижніх кнопка також застосує більше цифр для впевненості"
        )
        self.provider.manual_phone_update = {"device_enabled": False}
        self.provider.manual_image_actions = [{
            "slot": "phone_screen",
            "visual_direction": "A text-free open home medicine cabinet with medicines grouped visually by category",
            "enhance_current": False,
            "reference_index": 0,
        }]
        with self.assertRaisesRegex(ValueError, "would be invisible"):
            self.service.manual_agent_edit(
                project_id, detail["creative_id"], request_id=new_uuid7(),
                base_sha256=detail["state_sha256"], message=message,
                history=[], configuration=detail["configuration"],
                content=detail["content"], screenshots=[],
            )

        self.provider.manual_phone_update = {
            "device_enabled": True, "visual_mode": "image",
        }
        self.provider.manual_phone_screen_logo = False
        self.provider.manual_phone_stats = [
            {"value": "01", "label": "Фото упаковок"},
            {"value": "02", "label": "Класифікація"},
            {"value": "03", "label": "Домашній список"},
        ]
        result = self.service.manual_agent_edit(
            project_id, detail["creative_id"], request_id=new_uuid7(),
            base_sha256=detail["state_sha256"], message=message,
            history=[], configuration=detail["configuration"],
            content=detail["content"], screenshots=[],
        )
        self.assertTrue(result["configuration"]["device"]["enabled"])
        self.assertEqual("image", result["configuration"]["visual_mode"])
        self.assertFalse(result["configuration"]["phone_screen"]["logo_enabled"])
        self.assertEqual(["01", "02", "03"], [
            item["value"] for item in result["content"]["stats"]
        ])
        self.assertEqual("phone_screen", result["image_actions"][0]["slot"])
        self.assertIn(
            "configuration.visual_mode",
            self.provider.calls[-1]["output_schema"]["properties"]["edits"]
            ["items"]["properties"]["path"]["enum"],
        )
        self.assertEqual({
            "change_visible_artwork", "artwork_without_phone_hardware",
            "keep_one_natal_logo", "numeric_lower_metric_cards",
        }, {
            item["id"] for item in
            self.provider.calls[-1]["input_payload"]["request_constraints"]["required_outcomes"]
        })

    def test_invalid_composer_output_leaves_an_explicit_retryable_creative(self) -> None:
        project_id, brief_id = self.approved_brief()
        creative, _created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="phone_metrics", requested_by="test",
            creative_direction=PHONE_DIRECTION,
        )
        self.provider.invalid_generation = True
        failed = self.service.generate(creative["creative_id"])
        self.assertEqual("failed", failed["status"])
        self.assertEqual("failed", failed["generation"]["stage"])
        self.assertIn("fields", failed["generation"]["error_message"])

        queued = self.service.retry_generation(project_id, creative["creative_id"])
        self.assertEqual("queued", queued["status"])
        self.assertNotIn("error_type", queued["generation"])
        self.assertNotIn("error_message", queued["generation"])
        self.provider.invalid_generation = False
        recovered = self.service.generate(creative["creative_id"])
        self.assertEqual("draft", recovered["status"])
        self.assertNotIn("error_type", recovered["generation"])
        self.assertNotIn("error_message", recovered["generation"])

    def test_phone_preview_http_accepts_empty_cta_and_recovers_after_invalid_draft(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from hashlib import sha256
        from validation_pipeline.studio_routes import studio_creative_router

        project_id, _, detail = self.generate_creative("phone_metrics")
        app = FastAPI()
        app.include_router(studio_creative_router(self.service, prefix="/api/v1/studio"))
        path = f"/api/v1/studio/projects/{project_id}/creatives/{detail['creative_id']}/preview"
        request = {
            "state_sha256": detail["state_sha256"], "configuration": detail["configuration"],
            "content": {**detail["content"], "cta": "", "hero_title": ""},
        }
        with TestClient(app) as client:
            self.assertEqual(400, client.post(path, json=request).status_code)
            request["content"]["hero_title"] = "Completed owner headline"
            response = client.post(path, json=request)
        self.assertEqual(200, response.status_code, response.text[:200])
        self.assertEqual("image/png", response.headers["content-type"])
        self.assertEqual("private, no-store", response.headers["cache-control"])
        self.assertEqual(sha256(response.content).hexdigest(), response.headers["x-ptw-content-sha256"])
        self.assertEqual(detail["state_sha256"], self.service.detail(project_id, detail["creative_id"])["state_sha256"])
        self.assertEqual([], self.store.list("studio_skill_snapshots"))

    def test_phone_generation_uses_brief_composition_and_typed_skill_provenance(self) -> None:
        project_id, _brief_id, detail = self.generate_creative("phone_metrics")

        self.assertEqual("draft", detail["status"])
        self.assertEqual("completed", detail["generation"]["phone_image"]["status"])
        self.assertEqual([None], self.images.references)
        self.assertIn("ptw.domain-image.v1", self.images.prompts[0])
        self.assertIn('"global":null', self.images.prompts[0])
        self.assertIn('"project":null', self.images.prompts[0])
        self.assertIn("Omit readable text", self.images.prompts[0])
        self.assertIsNone(detail["generation"]["project_skill_snapshot_id"])
        self.assertIsNone(detail["generation"]["global_skill_snapshot_id"])
        generation_call = next(
            call for call in self.provider.calls
            if call["mode"] == "studio_creative_generation"
        )
        self.assertTrue(generation_call["idempotency_key"].endswith(
            ":studio-creative-composer-v4"
        ))
        self.assertEqual(
            "studio-creative-composer-v4", generation_call["prompt_version"],
        )
        self.assertEqual(project_id, detail["project_id"])
        self.assertIn("approved_product_brief", generation_call["input_payload"])
        self.assertIn("live_template_catalog", generation_call["input_payload"])
        self.assertEqual(PHONE_DIRECTION, generation_call["input_payload"]["creative_direction"])
        self.assertEqual(PHONE_DIRECTION, detail["generation"]["creative_direction"])
        self.assertIn("Default style", self.images.prompts[0])
        runs = [
            item for item in self.store.list("studio_generation_runs")
            if item["creative_id"] == detail["creative_id"]
        ]
        self.assertEqual({"composition", "phone_image"}, {item["stage"] for item in runs})
        for run in runs:
            self.assertEqual(detail["source_brief_id"], run["provenance"]["source_brief_id"])
            self.assertEqual("phone_metrics", run["provenance"]["template_id"])
            self.assertEqual(PHONE_DIRECTION, run["provenance"]["creative_direction"])
            self.assertIsNone(run["provenance"]["global_skill_sha256"])
            self.assertIsNone(run["provenance"]["project_skill_sha256"])

    def test_phone_direction_is_required_idempotent_and_replaceable(self) -> None:
        project_id, brief_id = self.approved_brief()
        with self.assertRaisesRegex(ValueError, "direction is required"):
            self.service.reserve_from_brief(
                brief_id=brief_id, template_id="phone_metrics", requested_by="test",
            )
        first, created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="phone_metrics", requested_by="test",
            creative_direction=PHONE_DIRECTION,
        )
        self.assertTrue(created)
        duplicate, created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="phone_metrics", requested_by="test",
            creative_direction=PHONE_DIRECTION,
        )
        self.assertFalse(created)
        self.assertEqual(first["creative_id"], duplicate["creative_id"])
        with self.assertRaisesRegex(ValueError, "different Phone Metrics"):
            self.service.reserve_from_brief(
                brief_id=brief_id, template_id="phone_metrics", requested_by="test",
                creative_direction={**PHONE_DIRECTION, "style": "business_professional"},
            )
        detail = self.service.detail(project_id, first["creative_id"])
        self.authority.update_creative(first["creative_id"], status="failed", generation={
            "phone_image": {"status": "failed", "visual_direction": "One clear subject in a calm scene."},
        })
        with self.assertRaisesRegex(ValueError, "style before retrying"):
            self.service.retry_generation(project_id, first["creative_id"])
        with self.assertRaisesRegex(ValueError, "style before retrying"):
            self.service.queue_phone_image_retry(project_id, first["creative_id"])
        legacy = self.service.set_creative_direction(
            project_id, first["creative_id"], base_sha256=detail["state_sha256"],
            creative_direction=PHONE_DIRECTION,
        )
        self.assertEqual(PHONE_DIRECTION, legacy["generation"]["creative_direction"])
        replacement_direction = {
            **PHONE_DIRECTION, "style": "ultra_realistic_lifestyle",
            "background": "isolated_key_element",
        }
        replaced = self.service.set_creative_direction(
            project_id, first["creative_id"], base_sha256=legacy["state_sha256"],
            creative_direction=replacement_direction,
        )
        self.assertEqual(replacement_direction, replaced["generation"]["creative_direction"])
        self.assertEqual(legacy["state_sha256"], replaced["state_sha256"])
        self.assertEqual([], self.store.list("studio_edit_checkpoints"))

    def test_phone_composer_schema_enforces_the_renderer_text_limits(self) -> None:
        _project_id, brief_id = self.approved_brief()
        creative, _created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="phone_metrics", requested_by="test",
            creative_direction=PHONE_DIRECTION,
        )
        detail = self.service._workspace(creative["creative_id"]).detail()
        schema = creative_generation_schema(detail)
        content = schema["properties"]["content"]["properties"]
        self.assertEqual(0, content["cta"]["minLength"])

        self.assertEqual({"minLength": 1, "maxLength": 32}, {
            key: content["offer"][key] for key in ("minLength", "maxLength")
        })
        self.assertEqual({"minLength": 1, "maxLength": 24}, {
            key: content["stats"]["items"]["properties"]["value"][key]
            for key in ("minLength", "maxLength")
        })
        configuration = schema["properties"]["configuration"]["properties"]
        self.assertEqual({"minimum": 0.04, "maximum": 0.24}, {
            key: configuration["background"]["properties"]["texture_intensity"][key]
            for key in ("minimum", "maximum")
        })
        self.assertEqual(
            ["none", "grain", "concrete", "travertine"],
            configuration["background"]["properties"]["texture"]["enum"],
        )
        self.assertEqual({"minimum": 580, "maximum": 640}, {
            key: configuration["device"]["properties"]["x"][key]
            for key in ("minimum", "maximum")
        })
        self.assertEqual(
            r"^#[0-9A-Fa-f]{6}$",
            configuration["metric_cards"]["items"]["properties"]["text_color"]["pattern"],
        )

    def test_logo_colors_are_locked_to_the_inherited_project_default(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        configuration = creative_generation_schema(detail)["properties"]["configuration"]["properties"]
        self.assertEqual(
            ["#87D0DD"], configuration["logo"]["properties"]["symbol_color"]["enum"],
        )
        self.assertEqual(
            ["#383840"], configuration["logo"]["properties"]["name_color"]["enum"],
        )

        existing_brief = self.add_approved_brief(project_id, "Existing draft")
        existing, created = self.service.reserve_from_brief(
            brief_id=existing_brief, template_id="phone_metrics",
            requested_by="test", creative_direction=PHONE_DIRECTION,
        )
        self.assertTrue(created)
        self.service._initialize_workspace(existing)
        existing_before = self.service.detail(project_id, existing["creative_id"])

        custom = deepcopy(detail["configuration"])
        custom["logo"].update({
            "symbol_color": "#123456", "name_color": "#ABCDEF",
        })
        preview = self.service.mutate(
            project_id, detail["creative_id"], "render_preview",
            state_sha256=detail["state_sha256"], configuration=custom,
            content=detail["content"],
        )
        self.assertTrue(preview["bytes_sha256"])
        self.assertIsNone(self.authority.latest_project_logo_default(project_id))

        result = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=detail["state_sha256"], configuration=custom,
            content=detail["content"],
        )
        self.assertTrue(result["checkpoint_created"])
        self.assertTrue(result["project_logo_default_updated"])
        self.assertEqual({
            "symbol_color": "#123456", "name_color": "#ABCDEF",
        }, {
            key: self.authority.latest_project_logo_default(project_id)[key]
            for key in ("symbol_color", "name_color")
        })
        record = self.store.list("studio_project_logo_defaults")[0]
        self.assertEqual(
            result["checkpoint"]["checkpoint_id"], record["source_checkpoint_id"],
        )
        self.assertEqual(
            existing_before["configuration"]["logo"],
            self.service.detail(project_id, existing["creative_id"])["configuration"]["logo"],
        )

        future_brief = self.add_approved_brief(project_id, "Future draft")
        future, created = self.service.reserve_from_brief(
            brief_id=future_brief, template_id="phone_metrics",
            requested_by="test", creative_direction=PHONE_DIRECTION,
        )
        self.assertTrue(created)
        self.service._initialize_workspace(future)
        future_detail = self.service.detail(project_id, future["creative_id"])
        self.assertEqual("#123456", future_detail["configuration"]["logo"]["symbol_color"])
        self.assertEqual("#ABCDEF", future_detail["configuration"]["logo"]["name_color"])
        replaced = self.service.mutate(
            project_id, future["creative_id"], "apply_template",
            base_sha256=future_detail["state_sha256"], template_id="phone_metrics",
        )
        self.assertEqual("#123456", replaced["configuration"]["logo"]["symbol_color"])
        self.assertEqual("#ABCDEF", replaced["configuration"]["logo"]["name_color"])
        locked = creative_generation_schema(replaced)["properties"]["configuration"]["properties"]["logo"]["properties"]
        self.assertEqual(["#123456"], locked["symbol_color"]["enum"])
        self.assertEqual(["#ABCDEF"], locked["name_color"]["enum"])

    def test_legacy_runtime_skill_snapshot_is_not_consumed_by_generation(self) -> None:
        project_id, _brief_id = self.approved_brief()
        snapshot_id = new_uuid7()
        self.store.append("studio_skill_snapshots", snapshot_id, {
            "skill_snapshot_id": snapshot_id, "scope": "project",
            "project_id": project_id, "version": 2,
            "content": "---\nname: studio-runtime-project\ndescription: Test.\n---\n\n# Test\n",
            "content_sha256": "0" * 64, "source_checkpoint_id": None,
            "created_at": "9999-01-01T00:00:00Z",
        })

        creative, _created = self.service.reserve_from_brief(
            brief_id=_brief_id, template_id="phone_metrics", requested_by="test",
            creative_direction=PHONE_DIRECTION,
        )
        self.service._initialize_workspace(creative)
        generated = self.service.generate(creative["creative_id"])
        self.assertEqual("draft", generated["status"])
        self.assertIsNone(generated["generation"]["project_skill_snapshot_id"])

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
        third = self.service.mutate(
            project_id, baseline["creative_id"], "generate_phone_screen",
            base_sha256=selected["state_sha256"],
            visual_direction="A hand-finished paper sculpture with a cobalt edge",
            enhance_current=False,
        )
        self.assertEqual(3, len(third["phone_screen_history"]))
        self.assertIn(original_sha, {item["sha256"] for item in third["phone_screen_history"]})
        fourth = self.service.mutate(
            project_id, baseline["creative_id"], "generate_phone_screen",
            base_sha256=third["state_sha256"],
            visual_direction="One refined mineral form in a quiet tonal landscape",
            enhance_current=False,
        )
        self.assertEqual(3, len(fourth["phone_screen_history"]))
        self.assertTrue(
            {item["sha256"] for item in third["phone_screen_history"][:2]}
            <= {item["sha256"] for item in fourth["phone_screen_history"]}
        )
        checkpoint = self.service.checkpoint(
            project_id, baseline["creative_id"], kind="save",
            base_sha256=fourth["state_sha256"],
            configuration=fourth["configuration"], content=fourth["content"],
        )

        self.assertTrue(checkpoint["checkpoint_created"])
        paths = checkpoint["checkpoint"]["changed_paths"]
        self.assertTrue(any(path.startswith("phone_screen_history") for path in paths))
        saved = self.authority.get_checkpoint(checkpoint["checkpoint"]["checkpoint_id"])
        self.assertEqual(1, len(saved["before_snapshot"]["phone_screen_history"]))
        self.assertEqual(3, len(saved["after_snapshot"]["phone_screen_history"]))

    def test_save_creates_one_checkpoint_and_zero_learning(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        baseline = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=detail["state_sha256"],
            configuration=detail["configuration"], content=detail["content"],
        )
        self.assertFalse(baseline["checkpoint_created"])
        self.assertFalse(any(call["mode"] == "creative_performance_learning" for call in self.provider.calls))

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
        self.assertEqual(0, len([
            item for item in self.store.list("studio_learning_runs")
            if item["checkpoint_id"] == checkpoint_id
        ]))
        self.assertEqual([], self.store.list("studio_skill_snapshots"))
        self.assertIsNone(checkpoint["learning_proposal"])

        unchanged = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=checkpoint["creative"]["state_sha256"],
            configuration=checkpoint["creative"]["configuration"],
            content=checkpoint["creative"]["content"],
        )
        self.assertFalse(unchanged["checkpoint_created"])
        self.assertEqual(0, len([
            call for call in self.provider.calls if call["mode"] == "creative_performance_learning"
        ]))
        self.assertEqual([], self.store.list("studio_learning_proposals"))
        self.assertEqual([], self.store.list("studio_learning_decisions"))

    def test_legacy_logo_color_uplift_does_not_create_a_false_checkpoint(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        workspace = self.service._workspace(detail["creative_id"])
        legacy = deepcopy(detail["configuration"])
        legacy["schema"] = "ptw.studio.phone-metrics-config.v12"
        legacy["logo"].pop("symbol_color")
        legacy["logo"].pop("name_color")
        workspace._atomic_json(workspace.root / "configuration.json", legacy)  # pylint: disable=protected-access
        legacy_sha256 = workspace._legacy_phone_state_sha256()  # pylint: disable=protected-access
        baseline = deepcopy(self.authority.get_creative(detail["creative_id"])["learning_baseline"])
        baseline["configuration"] = legacy
        baseline["template_sha256"] = "0" * 64
        self.authority.update_creative(
            detail["creative_id"], state_sha256=legacy_sha256,
            learning_baseline=baseline,
            learning_baseline_sha256=sha256_json(baseline),
        )
        normalized = self.service.detail(project_id, detail["creative_id"])
        result = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=legacy_sha256, configuration=normalized["configuration"],
            content=normalized["content"],
        )
        self.assertFalse(result["checkpoint_created"])
        self.assertFalse(result["project_logo_default_updated"])
        self.assertEqual([], self.store.list("studio_project_logo_defaults"))

    def test_variant_requires_the_latest_creative_to_be_approved(self) -> None:
        project_id, brief_id, first = self.generate_creative("phone_metrics")
        with self.assertRaisesRegex(ValueError, "approve the current creative"):
            self.service.reserve_from_brief(
                brief_id=brief_id, template_id="phone_metrics",
                requested_by="test", additional=True, creative_direction=PHONE_DIRECTION,
            )
        approved = self.service.checkpoint(
            project_id, first["creative_id"], kind="approve",
            base_sha256=first["state_sha256"], configuration=first["configuration"],
            content=first["content"], change_note="First approved creative",
        )
        self.assertTrue(approved["version_created"])
        second, created = self.service.reserve_from_brief(
            brief_id=brief_id, template_id="phone_metrics",
            requested_by="test", additional=True, creative_direction=PHONE_DIRECTION,
        )
        self.assertTrue(created)
        self.assertEqual(2, second["ordinal"])
        with self.assertRaisesRegex(ValueError, "approve the current creative"):
            self.service.reserve_from_brief(
                brief_id=brief_id, template_id="phone_metrics",
                requested_by="test", additional=True, creative_direction=PHONE_DIRECTION,
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

    def test_repeated_semantically_identical_approval_does_not_duplicate_version(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        content = deepcopy(detail["content"])
        content["hero_title"] = f"  {content['hero_title']}  "

        first = self.service.checkpoint(
            project_id, detail["creative_id"], kind="approve",
            base_sha256=detail["state_sha256"], configuration=detail["configuration"],
            content=content, change_note="First semantic approval",
        )
        repeated = self.service.checkpoint(
            project_id, detail["creative_id"], kind="approve",
            base_sha256=first["creative"]["state_sha256"],
            configuration=detail["configuration"], content=content,
            change_note="Repeated semantic approval",
        )

        self.assertTrue(first["version_created"])
        self.assertFalse(repeated["version_created"])
        self.assertEqual(1, repeated["creative"]["approved_version_count"])
        self.assertEqual(
            [1],
            [item["version"] for item in self.service._workspace(detail["creative_id"]).detail()["versions"]],
        )

    def test_clone_inherits_the_selected_approved_post_and_frozen_raw_asset(self) -> None:
        project_id, _brief_id, detail = self.generate_creative("phone_metrics")
        approved_asset_sha = detail["phone_screen_history"][0]["sha256"]
        approved_configuration = deepcopy(detail["configuration"])
        approved_configuration["logo"].update({
            "symbol_color": "#123456", "name_color": "#ABCDEF",
        })
        approved_result = self.service.checkpoint(
            project_id, detail["creative_id"], kind="approve",
            base_sha256=detail["state_sha256"], configuration=approved_configuration,
            content=detail["content"], change_note="Clone source",
        )
        self.assertTrue(approved_result["project_logo_default_updated"])
        approved = approved_result["creative"]
        changed = self.service.mutate(
            project_id, detail["creative_id"], "generate_phone_screen",
            base_sha256=approved["state_sha256"],
            visual_direction="A different cobalt object for the mutable source draft",
            enhance_current=False,
        )
        self.assertNotEqual(
            approved_asset_sha, changed["phone_screen_history"][0]["sha256"],
        )
        later_configuration = deepcopy(changed["configuration"])
        later_configuration["logo"].update({
            "symbol_color": "#654321", "name_color": "#FEDCBA",
        })
        later = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=changed["state_sha256"], configuration=later_configuration,
            content=changed["content"],
        )
        self.assertTrue(later["project_logo_default_updated"])

        request_id = new_uuid7()
        cloned, created = self.service.clone_approved_version(
            project_id=project_id, source_creative_id=detail["creative_id"],
            source_version=1, request_id=request_id, requested_by="test",
        )
        clone_detail = self.service.detail(project_id, cloned["creative_id"])
        approved_version = self.service._workspace(detail["creative_id"]).version_detail(1)
        self.assertTrue(created)
        self.assertEqual("approved_clone", clone_detail["origin"])
        self.assertEqual(approved_version["configuration"], clone_detail["configuration"])
        self.assertEqual("#123456", clone_detail["configuration"]["logo"]["symbol_color"])
        self.assertEqual("#ABCDEF", clone_detail["configuration"]["logo"]["name_color"])
        self.assertEqual(approved_version["content"], clone_detail["content"])
        self.assertEqual(approved_asset_sha, clone_detail["phone_screen_history"][0]["sha256"])
        self.assertEqual(0, clone_detail["approved_version_count"])
        duplicate, created = self.service.clone_approved_version(
            project_id=project_id, source_creative_id=detail["creative_id"],
            source_version=1, request_id=request_id, requested_by="test",
        )
        self.assertFalse(created)
        self.assertEqual(cloned["creative_id"], duplicate["creative_id"])

    def test_save_ignores_obsolete_learning_provider_failures(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        content = deepcopy(detail["content"])
        content["cta"] = "Take the next step"
        checkpoint = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=detail["state_sha256"],
            configuration=detail["configuration"], content=content,
        )
        self.assertEqual("saved", checkpoint["checkpoint"]["status"])
        self.assertIsNone(checkpoint["learning_proposal"])
        self.assertFalse(hasattr(self.service, "recover_learning"))
        self.assertFalse(hasattr(self.service, "retry_learning"))
        checkpoint_id = checkpoint["checkpoint"]["checkpoint_id"]
        self.assertEqual(
            1, len(self.store.history("studio_edit_checkpoints", checkpoint_id)),
        )
        self.assertEqual(0, len([
            item for item in self.store.list("studio_learning_runs")
            if item["checkpoint_id"] == checkpoint_id
        ]))
        learning_calls = [
            item for item in self.provider.calls
            if item["mode"] == "creative_performance_learning"
        ]
        self.assertEqual(0, len(learning_calls))
        self.assertEqual([], self.store.list("studio_skill_snapshots"))

    def test_save_never_consumes_obsolete_global_proposals(self) -> None:
        project_id, _brief_id, detail = self.generate_creative()
        content = deepcopy(detail["content"])
        content["hero_title"] = "Owner-specific final headline"
        checkpoint = self.service.checkpoint(
            project_id, detail["creative_id"], kind="save",
            base_sha256=detail["state_sha256"],
            configuration=detail["configuration"], content=content,
        )

        self.assertEqual("saved", checkpoint["checkpoint"]["status"])
        self.assertIsNone(checkpoint["learning_proposal"])
        self.assertEqual([], self.store.list("studio_learning_runs"))
        self.assertEqual([], self.store.list("studio_learning_proposals"))
        learning_calls = [
            item for item in self.provider.calls
            if item["mode"] == "creative_performance_learning"
        ]
        self.assertEqual([], learning_calls)

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
