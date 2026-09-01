from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from uuid import uuid4
import zipfile

from PIL import Image, ImageDraw

from validation_pipeline.content import HARD_GATES, WEIGHTS
from validation_pipeline.local_codex import (
    LocalCodexCancelled, LocalCodexError, LocalCodexStructuredProvider,
)
from validation_pipeline.local_experiment_store import LocalExperimentStore
from validation_pipeline.local_experiments import LocalExperimentService, LOCAL_VISUAL_ROLES
from validation_pipeline.images import PexelsPhoto
from validation_pipeline.studio_workspace import UniversalStudioWorkspace


class FakeStructuredProvider:
    def __init__(self, *, eligible: bool = True) -> None:
        self.calls: list[dict] = []
        self.eligible = eligible

    def call(self, *, mode, input_payload, response_validator=None, **kwargs):
        self.calls.append({"mode": mode, "payload": input_payload, "images": kwargs.get("images") or []})
        if mode in {"product_brief", "product_brief_revision"}:
            response = {
                "schema_version": 1, "language": "en",
                "product": "Guided planning session",
                "target_audience": "Independent founders planning a first launch",
                "main_pain": "The next useful action is unclear",
                "promise": "Leave with one clear next step",
                "key_benefits": ["One focused conversation", "A visible sequence", "A practical next action"],
                "cta": "Book the call", "trust_strategy": "A transparent real-person consultation",
                "offer": "Free 15-minute consultation",
            }
        elif mode == "content_candidate_generation":
            strategy = input_payload["strategy"]["template_id"]
            asset = input_payload["assigned_asset"]
            asset_id = None if asset is None else asset["source_asset_id"]
            response = {
                "schema_version": 2,
                "hook": f"A visible {strategy.replace('_', ' ')} moment",
                "headline": f"One clear step · {strategy.replace('_', ' ')}",
                "primary_text": "See the small sequence before making a larger commitment.",
                "supporting_text": "A practical first conversation with a transparent process.",
                "offer": input_payload["approved_brief"]["offer"],
                "cta": input_payload["approved_brief"]["cta"],
                "caption": f"A focused {strategy.replace('_', ' ')} direction for the first step.",
                "alt_text": f"A square Universal Studio post using the {strategy.replace('_', ' ')} direction.",
                "desired_emotion": "calm confidence",
                "visual_concept": "One coherent Universal Studio composition.",
                "media_request": {
                    "kind": "none" if asset_id is None else "approved_asset",
                    "query": "", "source_asset_id": asset_id,
                    "reason": "Use only the isolated server-assigned asset policy.",
                },
                "visual_components": [{
                    "role": role, "content": f"Resolved {role.replace('_', ' ')} role.",
                    "source_ids": [asset_id] if asset_id and role == "background" else [],
                } for role in LOCAL_VISUAL_ROLES],
            }
        elif mode == "content_result_critic":
            candidates = input_payload["candidates"]
            evaluations = []
            for index, candidate in enumerate(candidates):
                score = max(7, 10 - index)
                evaluations.append({
                    "candidate_id": candidate["candidate_id"],
                    "hard_gates": {key: True for key in HARD_GATES},
                    "element_scores": [{
                        "element_id": element_id, "task_fit": score, "clarity": score,
                        "contribution": score, "coherence": score,
                    } for element_id in candidate["element_ids"]],
                    "scores": {key: score for key in WEIGHTS},
                    "complexity": "none", "reason_codes": ["clear_and_eligible"],
                })
            ranking = [item["candidate_id"] for item in candidates]
            compared = ranking[: min(3, len(ranking))]
            pairs = []
            if len(compared) == 3:
                pairs = [
                    {"left": compared[0], "right": compared[1], "winner": compared[0], "reason_codes": ["clearer"]},
                    {"left": compared[0], "right": compared[2], "winner": compared[0], "reason_codes": ["clearer"]},
                    {"left": compared[1], "right": compared[2], "winner": compared[1], "reason_codes": ["clearer"]},
                ]
            elif len(compared) == 2 and input_payload["pass"] == 3:
                pairs = [{"left": compared[0], "right": compared[1], "winner": compared[0], "reason_codes": ["clearer"]}]
            response = {
                "pass": input_payload["pass"], "evaluations": evaluations,
                "ranking": ranking, "pairwise": pairs, "actions": [],
                "observations": ["The leading direction is clear and passes every deterministic gate."],
                "final_selection": None if input_payload["pass"] < 3 or not self.eligible else {
                    "candidate_id": ranking[0],
                    "decision_summary": ["Protected copy is clear.", "The rendered hierarchy is eligible."],
                },
            }
        else:
            raise AssertionError(mode)
        if response_validator is not None:
            response = dict(response_validator(response))
        return {
            "response": response,
            "invocation": {"provider": "fake", "mode": mode, "attempts": [{"attempt": 1, "status": "completed"}]},
        }


class BlockingStructuredProvider(FakeStructuredProvider):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.cancelled = threading.Event()

    def call(self, *, mode, input_payload, response_validator=None, **kwargs):
        if mode != "content_candidate_generation":
            return super().call(
                mode=mode, input_payload=input_payload,
                response_validator=response_validator, **kwargs,
            )
        self.calls.append({"mode": mode, "payload": input_payload, "images": []})
        cancel_event = kwargs.get("cancel_event")
        if not isinstance(cancel_event, threading.Event):
            raise AssertionError("active Result provider call requires a cancellation event")
        self.started.set()
        if not cancel_event.wait(timeout=5):
            raise AssertionError("active Result provider call was not cancelled")
        self.cancelled.set()
        raise LocalCodexCancelled([{
            "attempt": 1, "status": "terminated", "error_type": "LocalCodexCancelled",
        }])


def image_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (1200, 1200), color)
    output = BytesIO()
    image.save(output, format="JPEG", quality=92)
    return output.getvalue()


class FakePexels:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.counter = 0

    def select(self, query: str, category: str, *, used_ids: set[str]):
        while True:
            self.counter += 1
            photo_id = str(700000 + self.counter)
            if photo_id not in used_ids:
                break
        is_sticker = "compass object" in query
        image = Image.new("RGB", (1200, 1200), (238, 225, 199) if is_sticker else (
            30 + self.counter * 23 % 190,
            40 + self.counter * 37 % 170,
            50 + self.counter * 47 % 160,
        ))
        if is_sticker:
            draw = ImageDraw.Draw(image)
            accent = self.counter % 37
            draw.ellipse(
                (315, 250, 885, 820), fill=(25, 49 + accent, 78),
                outline=(183, 136, 49 + accent), width=34,
            )
            draw.polygon(((600, 305), (710, 650), (600, 585), (490, 650)), fill=(222, 174, 61))
            draw.polygon(((600, 765), (490, 475), (600, 535), (710, 475)), fill=(108, 27, 70))
        output = BytesIO()
        image.save(output, format="JPEG", quality=94)
        self.calls.append({"query": query, "category": category, "photo_id": photo_id})
        return PexelsPhoto(
            photo_id=photo_id, width=1200, height=1200,
            image_url=f"https://images.pexels.com/photos/{photo_id}/image.jpeg",
            page_url=f"https://www.pexels.com/photo/{photo_id}/",
            photographer=f"Photographer {photo_id}",
            photographer_url=f"https://www.pexels.com/@photographer-{photo_id}/",
            alt="A real photographed object" if is_sticker else "A real editorial photograph",
        ), output.getvalue()


class LocalExperimentFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.provider = FakeStructuredProvider()
        self.pexels = FakePexels()
        self.workspace = UniversalStudioWorkspace(self.root / "studio")
        self.store = LocalExperimentStore(self.root / "experiments")
        self.service = LocalExperimentService(
            store=self.store, workspace=self.workspace, provider=self.provider,
            repository_root=Path(__file__).resolve().parents[2], pexels=self.pexels,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _approved_brief(self):
        project, brief, created = self.service.create_brief(
            request_id=str(uuid4()), raw_idea="A guided launch-planning conversation.",
            requested_by="test-owner",
        )
        self.assertTrue(created)
        brief = self.service.generate_brief(brief["brief_id"])
        self.assertEqual("completed", brief["status"])
        brief, approved_now = self.service.approve_brief(brief["brief_id"], "test-owner")
        self.assertTrue(approved_now)
        return project, brief

    def _assets(self, project_id: str):
        for index, color in enumerate(((180, 40, 30), (30, 160, 80), (20, 80, 190), (190, 140, 20))):
            asset = self.service.upload_asset(
                project_id=project_id, title=f"Photo {index + 1}", mime_type="image/jpeg",
                data=image_bytes(color), requested_by="test-owner",
            )
            self.service.approve_asset(asset["source_asset_id"], approved=True, requested_by="test-owner")

    def test_complete_run_release_and_owner_lesson_snapshot(self) -> None:
        project, brief = self._approved_brief()
        self._assets(project["project_id"])
        studio = self.workspace.detail()
        run, created = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=studio["state_sha256"], requested_by="test-owner",
        )
        self.assertTrue(created)
        completed = self.service.execute_run(run["run_id"])
        self.assertEqual("completed", completed["status"], completed.get("error_message"))
        debug = self.service.debug(run["run_id"])
        initial = [item for item in debug["candidates"] if item["generation_kind"] == "initial"]
        self.assertEqual(5, len(initial))
        self.assertEqual(5, len({item["preview"]["sha256"] for item in initial}))
        self.assertTrue(all(
            item["preview"]["width"] == item["preview"]["height"] == 1080
            and item["analysis_preview"]["width"] == item["analysis_preview"]["height"] == 480
            and item["analysis_preview"]["source_preview_sha256"] == item["preview"]["sha256"]
            and item["analysis_preview"]["source_png_sha256"] == item["png"]["sha256"]
            and item["analysis_preview"]["byte_count"] < item["preview"]["byte_count"]
            and item["analysis_preview"]["source_width"]
            * item["analysis_preview"]["source_height"]
            >= 5 * item["analysis_preview"]["width"]
            * item["analysis_preview"]["height"]
            for item in initial
        ))
        self.assertTrue(all(
            "saved Natal logo is visible" in item["document"]["alt_text"]
            and "no logo" not in item["document"]["alt_text"].casefold()
            and next(
                component for component in item["document"]["visual_components"]
                if component["role"] == "logo"
            )["content"].startswith("The saved canonical Natal logo")
            and any(
                transformation["field"] == "alt_text"
                for transformation in item["document_transformations"]
            )
            for item in initial
        ))
        self.assertTrue(all(
            (
                next(
                    component for component in item["document"]["visual_components"]
                    if component["role"] == "bullet_list"
                )["content"].startswith("Visible bullet list:")
            ) == item["configuration"]["bullets"]["enabled"]
            for item in initial
        ))
        candidate_calls = [
            item for item in self.provider.calls if item["mode"] == "content_candidate_generation"
        ]
        self.assertTrue(all(
            call["payload"]["resolved_render_contract"]["logo"]["visible"]
            and call["payload"]["resolved_render_contract"]["logo"]["authority"]
            == "captured_saved_studio_identity"
            for call in candidate_calls[:5]
        ))
        critic_calls = [
            item for item in self.provider.calls if item["mode"] == "content_result_critic"
        ]
        self.assertEqual([3, 2, 2], [len(item["images"]) for item in critic_calls])
        self.assertEqual(
            ["screening_group_1_of_2", "screening_group_2_of_2", "group_winner_comparison"],
            [item["payload"]["critic_scope"] for item in critic_calls],
        )
        self.assertEqual([], critic_calls[1]["payload"]["previous_pass_summaries"])
        self.assertEqual(2, len(critic_calls[2]["payload"]["previous_pass_summaries"]))
        self.assertTrue(all(
            candidate["render"]["asset_provenance"]["logo"]["authority"]
            == "captured_saved_studio_identity"
            for call in critic_calls for candidate in call["payload"]["candidates"]
        ))
        first_winner = critic_calls[0]["payload"]["candidates"][0]["candidate_id"]
        second_winner = critic_calls[1]["payload"]["candidates"][0]["candidate_id"]
        self.assertEqual(
            [first_winner, second_winner],
            [item["candidate_id"] for item in critic_calls[2]["payload"]["candidates"]],
        )
        self.assertEqual(
            [first_winner, second_winner],
            [
                item["group_winner_candidate_id"]
                for item in critic_calls[2]["payload"]["previous_pass_summaries"]
            ],
        )
        self.assertTrue(all(
            image["width"] == image["height"] == 480
            and Image.open(BytesIO(image["bytes"])).size == (480, 480)
            for call in critic_calls for image in call["images"]
        ))
        self.assertEqual(3, len({item["asset_id"] for item in initial if item["asset_id"]}))
        self.assertEqual([1, 2, 3], [item["pass_number"] for item in debug["critic_passes"]])
        self.assertTrue(all(item["layout_audit"]["passed"] for item in initial))
        self.assertTrue(all(item["content"]["offer"] == brief["document"]["offer"] for item in initial))

        studio_before_ready = self.workspace.detail()
        with self.assertRaisesRegex(ValueError, "locked until owner Ready"):
            self.service.release_download(run["run_id"])
        ready = self.service.ready(run["run_id"], "test-owner")
        self.assertEqual(studio_before_ready, self.workspace.detail())
        package = self.service.release_download(run["run_id"])
        self.assertEqual(ready["release"]["package_sha256"], package["sha256"])
        with zipfile.ZipFile(BytesIO(package["bytes"])) as archive:
            self.assertEqual({
                "alt-text.txt", "asset-provenance.json", "caption.txt", "decision-trace.json",
                "digest-manifest.json", "post.jpg", "product-brief.json", "source.png",
                "universal-manifest.json",
            }, set(archive.namelist()))
            self.assertEqual(self.service.get_result(run["run_id"])["asset_sha256"], __import__("hashlib").sha256(archive.read("post.jpg")).hexdigest())

        proposals = self.service.list_lesson_proposals("pending")
        self.assertEqual(4, len(proposals))
        layout_proposal = next(item for item in proposals if item["target"] == "universal_ad_layout_policy")
        approved = self.service.decide_lesson(
            layout_proposal["proposal_id"], decision="approved", edited_text="Keep the selected safe layout relationships.",
            approval_authority="owner", requested_by="test-owner",
        )
        self.assertEqual("owner", approved["lesson"]["approval_authority"])
        rejected_target = next(item for item in proposals if item["proposal_id"] != layout_proposal["proposal_id"])
        with self.assertRaisesRegex(ValueError, "agent lesson approval"):
            self.service.decide_lesson(
                rejected_target["proposal_id"], decision="approved", edited_text=None,
                approval_authority="agent", requested_by="test-owner",
            )
        rejected = self.service.decide_lesson(
            rejected_target["proposal_id"], decision="rejected", edited_text=None,
            approval_authority="owner", requested_by="test-owner",
        )
        self.assertIsNone(rejected["lesson"])
        next_run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=studio["state_sha256"], requested_by="test-owner",
        )
        snapshot = self.store.get("lesson_snapshots", next_run["learning_snapshot_id"])
        snapshot_ids = [item["lesson_id"] for item in snapshot["lessons"]]
        self.assertEqual([approved["lesson"]["lesson_id"]], snapshot_ids)
        next_completed = self.service.execute_run(next_run["run_id"])
        self.assertEqual("completed", next_completed["status"], next_completed.get("error_message"))
        next_candidates = [
            item for item in self.service.debug(next_run["run_id"])["candidates"]
            if item["generation_kind"] == "initial"
        ]
        self.assertTrue(any(item["applied_layout_lessons"] for item in next_candidates))

    def test_no_eligible_finalist_fails_without_result(self) -> None:
        self.provider.eligible = False
        project, brief = self._approved_brief()
        self._assets(project["project_id"])
        studio = self.workspace.detail()
        run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=studio["state_sha256"], requested_by="test-owner",
        )
        failed = self.service.execute_run(run["run_id"])
        self.assertEqual("failed", failed["status"])
        self.assertIn("selected no eligible", failed["error_message"])
        with self.assertRaisesRegex(ValueError, "not completed"):
            self.service.get_result(run["run_id"])

    def test_owner_terminates_active_run_and_can_retry_as_child(self) -> None:
        _project, brief = self._approved_brief()
        provider = BlockingStructuredProvider()
        self.service.provider = provider
        run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )
        outcome: dict[str, dict] = {}
        worker = threading.Thread(
            target=lambda: outcome.setdefault("run", self.service.execute_run(run["run_id"])),
            daemon=True,
        )
        worker.start()
        self.assertTrue(provider.started.wait(timeout=5))

        terminated = self.service.terminate_run(run["run_id"], "test-owner")
        worker.join(timeout=5)

        self.assertFalse(worker.is_alive())
        self.assertTrue(provider.cancelled.is_set())
        self.assertEqual("terminated", terminated["status"])
        self.assertEqual("terminated", terminated["current_stage"])
        self.assertEqual("test-owner", terminated["terminated_by"])
        self.assertEqual("terminated", outcome["run"]["status"])
        self.assertIsNone(terminated["final_result_id"])
        invocation = self.store.list("provider_invocations")[0]
        self.assertEqual("terminated", invocation["status"])
        self.assertEqual("LocalCodexCancelled", invocation["error_type"])
        checkpoints = [
            item for item in self.store.list("checkpoints")
            if item["run_id"] == run["run_id"]
        ]
        self.assertEqual(1, len([item for item in checkpoints if item["stage"] == "terminated"]))
        history_length = len(self.store.history("runs", run["run_id"]))
        self.assertEqual(
            terminated,
            self.service.terminate_run(run["run_id"], "test-owner"),
        )
        self.assertEqual(history_length, len(self.store.history("runs", run["run_id"])))

        retry, created = self.service.retry_run(
            run["run_id"], request_id=str(uuid4()), requested_by="test-owner",
        )
        self.assertTrue(created)
        self.assertEqual(run["run_id"], retry["parent_run_id"])
        self.assertEqual("queued", retry["status"])

    def test_improve_starts_immutable_child_and_replay_ignores_later_draft(self) -> None:
        project, brief = self._approved_brief()
        self._assets(project["project_id"])
        studio = self.workspace.detail()
        request_id = str(uuid4())
        run, _ = self.service.create_run(
            request_id=request_id, brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=studio["state_sha256"], requested_by="test-owner",
        )
        self.assertEqual("completed", self.service.execute_run(run["run_id"])["status"])
        result = self.service.get_result(run["run_id"])
        selected = self.store.get("candidates", result["selected_candidate_id"])
        child, created = self.service.improve(
            run["run_id"], request_id=str(uuid4()), comment="Make the hierarchy calmer.",
            requested_by="test-owner",
        )
        self.assertTrue(created)
        self.assertEqual(run["run_id"], child["parent_run_id"])
        self.assertEqual(selected["asset_id"], child["immutable_base_asset_id"])
        self.assertEqual(selected["configuration"], child["studio_export"]["configuration"])
        later = self.workspace.detail()
        changed_configuration = json.loads(json.dumps(later["configuration"]))
        changed_configuration["layout"]["gap"] = 31
        self.workspace.save_configuration(
            base_sha256=later["state_sha256"], configuration=changed_configuration,
            content=later["content"],
        )
        replay, created = self.service.create_run(
            request_id=request_id, brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=studio["state_sha256"], requested_by="test-owner",
        )
        self.assertFalse(created)
        self.assertEqual(run["run_id"], replay["run_id"])

    def test_empty_asset_pool_sources_three_fresh_pexels_photos_and_real_sticker(self) -> None:
        project, brief = self._approved_brief()
        studio = self.workspace.detail()
        run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=studio["state_sha256"], requested_by="test-owner",
        )
        completed = self.service.execute_run(run["run_id"])
        self.assertEqual("completed", completed["status"], completed.get("error_message"))
        initial = [
            item for item in self.service.debug(run["run_id"])["candidates"]
            if item["generation_kind"] == "initial"
        ]
        photo_capable = [item for item in initial if item["template_id"] != "direct_offer"]
        self.assertEqual(3, len([item for item in photo_capable if item["asset_id"]]))
        by_strategy = {item["template_id"]: item for item in initial}
        self.assertEqual(
            ["image", "image", "texture", "image", "solid"],
            [item["configuration"]["background"]["mode"] for item in initial],
        )
        self.assertEqual(5, len({
            item["configuration"]["background"]["color"] for item in initial
        }))
        pexels_backgrounds = [
            item for item in photo_capable
            if item["asset_provenance"].get("source", {}).get("provider") == "pexels"
        ]
        self.assertEqual(
            {"moment_tension", "contrast_reframe", "human_story"},
            {item["template_id"] for item in pexels_backgrounds},
        )
        self.assertEqual(3, len({item["asset_provenance"]["sha256"] for item in pexels_backgrounds}))
        self.assertTrue(all(
            item["render_asset_provenance"]["background"]["authority"]
            == "approved_pexels_photo"
            and item["asset_provenance"]["source"]["selection_policy"]
            == "fresh_distinct_per_run_v1"
            for item in pexels_backgrounds
        ))
        self.assertEqual(
            {"mechanism_proof"},
            {
                item["template_id"] for item in photo_capable
                if item["asset_provenance"]["origin"] == "deterministic_studio_texture"
            },
        )
        self.assertTrue(all(
            "logo_surface" not in item["universal_manifest"]["nodes"]
            and not item["configuration"]["logo"]["background_enabled"]
            for item in initial
        ))
        self.assertEqual(
            ["contrast_reframe"],
            [item["template_id"] for item in initial if item["configuration"]["sticker"]["enabled"]],
        )
        self.assertEqual(
            "approved_pexels_photo_sticker",
            by_strategy["contrast_reframe"]["render_asset_provenance"]["sticker"]["authority"],
        )
        sticker_source = by_strategy["contrast_reframe"]["render_asset_provenance"]["sticker"]["source"]
        self.assertEqual("pexels", sticker_source["provider"])
        self.assertEqual("edge_color_soft_alpha_v1", sticker_source["transformation"])
        self.assertEqual("warm matte paper", sticker_source["texture_alignment"]["surface"])
        self.assertIn("solid-color background", by_strategy["direct_offer"]["document"]["alt_text"])
        self.assertNotIn("textured background", by_strategy["direct_offer"]["document"]["alt_text"])
        self.assertEqual(5, len({
            (
                item["configuration"]["background"]["mode"],
                item["configuration"]["background"]["color"],
                item["configuration"]["typography"]["font_family"],
                item["configuration"]["cta"]["style"],
                item["configuration"]["sticker"]["enabled"],
            )
            for item in initial
        }))
        self.assertEqual(5, len([
            item for item in self.provider.calls if item["mode"] == "content_candidate_generation"
        ]))
        diversity_checkpoint = next(
            item for item in self.store.list("checkpoints")
            if item["run_id"] == run["run_id"] and item["stage"] == "critic_pass_1"
        )
        diversity = diversity_checkpoint["evidence"]["diversity_audit"]
        self.assertTrue(diversity["passed"])
        self.assertTrue(all(diversity["gates"].values()))
        self.assertEqual(3, len(diversity["image_backgrounds"]))
        self.assertEqual(3, len(diversity["distinct_image_background_sha256"]))
        self.assertGreaterEqual(diversity["minimum_setting_differences"], 8)
        self.assertGreaterEqual(diversity["minimum_mean_rgb_delta"], 12.0)

    def test_missing_pexels_configuration_fails_closed_without_generated_fallback(self) -> None:
        _project, brief = self._approved_brief()
        self.service.pexels = None
        with self.assertRaisesRegex(RuntimeError, "PEXELS_API_KEY is required"):
            self.service.create_run(
                request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
                studio_state_sha256=self.workspace.detail()["state_sha256"],
                requested_by="test-owner",
            )
        self.assertEqual([], self.store.list("runs"))
        self.assertEqual([], self.store.list("candidates"))

    def test_pexels_backgrounds_are_fresh_across_runs_and_distinct_within_each_run(self) -> None:
        _project, brief = self._approved_brief()
        studio = self.workspace.detail()
        external_ids_by_run: list[set[str]] = []
        for _index in range(2):
            run, created = self.service.create_run(
                request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
                studio_state_sha256=studio["state_sha256"], requested_by="test-owner",
            )
            self.assertTrue(created)
            completed = self.service.execute_run(run["run_id"])
            self.assertEqual("completed", completed["status"], completed.get("error_message"))
            candidates = [
                item for item in self.service.debug(run["run_id"])["candidates"]
                if item["generation_kind"] == "initial"
                and item["configuration"]["background"]["mode"] == "image"
            ]
            self.assertEqual(3, len(candidates))
            external_ids = {
                item["asset_provenance"]["source"]["external_id"] for item in candidates
            }
            self.assertEqual(3, len(external_ids))
            external_ids_by_run.append(external_ids)
        self.assertTrue(external_ids_by_run[0].isdisjoint(external_ids_by_run[1]))


class LocalCodexProviderTests(unittest.TestCase):
    def test_command_is_ephemeral_read_only_and_environment_is_sanitized(self) -> None:
        captured = {}

        def execute(command, **kwargs):
            captured.update({"command": command, **kwargs})
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text('{"ok":true}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="event", stderr="")

        provider = LocalCodexStructuredProvider("codex-test", executor=execute)
        result = provider.call(
            mode="test", system_prompt="Return the object.", input_payload={"value": 1},
            output_schema={
                "type": "object", "additionalProperties": False,
                "required": ["ok"], "properties": {"ok": {"type": "boolean"}},
            }, idempotency_key="one", prompt_version="v1",
        )
        self.assertEqual({"ok": True}, result["response"])
        self.assertIn("--ephemeral", captured["command"])
        self.assertEqual("read-only", captured["command"][captured["command"].index("--sandbox") + 1])
        self.assertEqual(
            'model_reasoning_effort="xhigh"',
            captured["command"][captured["command"].index("--config") + 1],
        )
        self.assertNotIn("OPENAI_API_KEY", captured["env"])
        self.assertNotEqual(Path.cwd(), Path(captured["cwd"]))
        self.assertEqual("xhigh", result["invocation"]["reasoning_effort"])

    def test_reasoning_effort_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "reasoning effort"):
            LocalCodexStructuredProvider("codex-test", reasoning_effort="ultra")

    def test_fresh_retry_and_exact_image_attachment(self) -> None:
        calls = []
        jpeg = image_bytes((8, 40, 90))
        digest = __import__("hashlib").sha256(jpeg).hexdigest()

        def execute(command, **kwargs):
            image_path = Path(command[command.index("--image") + 1])
            calls.append({"command": list(command), "image": image_path.read_bytes()})
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text("not-json" if len(calls) == 1 else '{"ok":true}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="event", stderr="")

        provider = LocalCodexStructuredProvider("codex-test", executor=execute)
        result = provider.call(
            mode="critic", system_prompt="Return the object.", input_payload={"value": 1},
            output_schema={
                "type": "object", "additionalProperties": False,
                "required": ["ok"], "properties": {"ok": {"type": "boolean"}},
            }, idempotency_key="retry", prompt_version="v1",
            images=[{"bytes": jpeg, "sha256": digest, "mime_type": "image/jpeg"}],
        )
        self.assertEqual(2, len(calls))
        self.assertEqual(jpeg, calls[0]["image"])
        self.assertEqual(["failed", "completed"], [item["status"] for item in result["invocation"]["attempts"]])
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            provider.call(
                mode="critic", system_prompt="Return the object.", input_payload={},
                output_schema={"type": "object"}, idempotency_key="bad-image",
                prompt_version="v1", images=[{
                    "bytes": jpeg, "sha256": "0" * 64, "mime_type": "image/jpeg",
                }],
            )

    def test_timeout_records_two_sanitized_failures(self) -> None:
        def execute(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        provider = LocalCodexStructuredProvider("codex-test", executor=execute)
        with self.assertRaises(LocalCodexError) as captured:
            provider.call(
                mode="test", system_prompt="Return the object.", input_payload={"secret": "hidden"},
                output_schema={"type": "object"}, idempotency_key="timeout", prompt_version="v1",
            )
        self.assertEqual(2, len(captured.exception.attempts))
        self.assertEqual(["TimeoutExpired", "TimeoutExpired"], [
            item["error_type"] for item in captured.exception.attempts
        ])

    def test_cancellation_terminates_the_active_cli_process_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "started"
            executable = root / "codex-test"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "import time\n"
                f"Path({str(marker)!r}).write_text('started', encoding='utf-8')\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            provider = LocalCodexStructuredProvider(str(executable), timeout_seconds=30)
            cancel_event = threading.Event()
            errors: list[BaseException] = []

            def invoke() -> None:
                try:
                    provider.call(
                        mode="test", system_prompt="Return the object.",
                        input_payload={"value": 1}, output_schema={"type": "object"},
                        idempotency_key="cancel", prompt_version="v1",
                        cancel_event=cancel_event,
                    )
                except BaseException as error:
                    errors.append(error)

            worker = threading.Thread(target=invoke, daemon=True)
            worker.start()
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists())
            cancel_event.set()
            worker.join(timeout=5)

            self.assertFalse(worker.is_alive())
            self.assertEqual(1, len(errors))
            self.assertIsInstance(errors[0], LocalCodexCancelled)
            self.assertEqual(
                ["terminated"],
                [item["status"] for item in errors[0].attempts],
            )


class LocalExperimentStoreTests(unittest.TestCase):
    def test_checkpoint_recovery_is_append_only_and_restart_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = LocalExperimentStore(Path(temporary))
            run_id = str(uuid4())
            checkpoint_id = str(uuid4())
            store.append("runs", run_id, {
                "run_id": run_id, "status": "generating", "current_stage": "critic_pass_2",
                "created_at": "2026-08-31T00:00:00Z", "updated_at": "2026-08-31T00:00:00Z",
            })
            store.append("checkpoints", checkpoint_id, {
                "checkpoint_id": checkpoint_id, "run_id": run_id, "stage": "critic_pass_2",
                "progress_percent": 66, "evidence": {}, "created_at": "2026-08-31T00:00:01Z",
            })
            recovered = LocalExperimentStore(Path(temporary)).recover_interrupted()
            self.assertEqual([run_id], recovered)
            latest = store.get("runs", run_id)
            self.assertEqual("queued", latest["status"])
            self.assertEqual(checkpoint_id, latest["recovered_from_checkpoint_id"])
            self.assertEqual(2, len(store.history("runs", run_id)))


class LocalResetTests(unittest.TestCase):
    def test_reset_clears_only_exact_allowlist_and_preserves_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "checkout"
            scripts = repository / "scripts"
            scripts.mkdir(parents=True)
            source = Path(__file__).resolve().parents[2] / "scripts/reset_ptw_local.sh"
            target = scripts / source.name
            shutil.copy2(source, target)
            target.chmod(0o755)
            local = repository / ".local"
            sentinel = local / "diagnostics/sentinel.txt"
            sentinel.parent.mkdir(parents=True)
            sentinel.write_text("preserve", encoding="utf-8")
            for name in ("studio-workspace", "studio-tune", "owner-experiments"):
                path = local / name
                path.mkdir(parents=True)
                (path / "old.json").write_text("{}", encoding="utf-8")
            completed = subprocess.run(
                [str(target), "--confirm=RESET PTW LOCAL OWNER DATA"],
                cwd=repository, text=True, capture_output=True, check=False,
                env={**os.environ, "PATH": os.environ.get("PATH", "")},
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("preserve", sentinel.read_text(encoding="utf-8"))
            for name in ("studio-workspace", "studio-tune", "owner-experiments"):
                self.assertEqual([], list((local / name).iterdir()))


if __name__ == "__main__":
    unittest.main()
