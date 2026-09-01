from __future__ import annotations

from io import BytesIO
import hashlib
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

from validation_pipeline.domain import infer_language
from validation_pipeline.local_codex import (
    LocalCodexCancelled, LocalCodexError, LocalCodexStructuredProvider,
)
from validation_pipeline.local_experiment_store import LocalExperimentStore
from validation_pipeline.local_experiments import LocalExperimentService, LOCAL_VISUAL_ROLES
from validation_pipeline.images import PexelsPhoto
from validation_pipeline.review_notifications import NotificationAttempt
from validation_pipeline.studio_workspace import UniversalStudioWorkspace


class FakeStructuredProvider:
    def __init__(self, *, wrong_candidate_language: bool = False) -> None:
        self.calls: list[dict] = []
        self.wrong_candidate_language = wrong_candidate_language
        self.fail_candidate = False

    def call(self, *, mode, input_payload, response_validator=None, **kwargs):
        self.calls.append({
            "mode": mode, "payload": input_payload, "images": kwargs.get("images") or [],
            "system_prompt": kwargs.get("system_prompt") or "",
            "prompt_version": kwargs.get("prompt_version") or "",
        })
        if mode in {"product_brief", "product_brief_revision"}:
            if input_payload["required_language"] == "uk":
                response = {
                    "schema_version": 1, "language": "uk",
                    "product": "Сесія планування запуску",
                    "target_audience": "Незалежні засновники, які планують перший запуск",
                    "main_pain": "Наступна корисна дія залишається незрозумілою",
                    "promise": "Завершити розмову з одним чітким наступним кроком",
                    "key_benefits": [
                        "Одна сфокусована розмова", "Видима послідовність",
                        "Практична наступна дія",
                    ],
                    "cta": "Забронювати розмову",
                    "trust_strategy": "Прозора консультація з реальною людиною",
                    "offer": "Безкоштовна 15-хвилинна консультація",
                }
            else:
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
            if self.fail_candidate:
                raise RuntimeError("injected candidate failure")
            strategy = input_payload["strategy"]["template_id"]
            call_number = len([
                item for item in self.calls if item["mode"] == "content_candidate_generation"
            ])
            asset = input_payload["assigned_asset"]
            asset_id = None if asset is None else asset["source_asset_id"]
            candidate_language = (
                "en" if self.wrong_candidate_language else input_payload["required_language"]
            )
            localized = candidate_language == "uk"
            response = {
                "schema_version": 2,
                "hook": (
                    f"Видимий момент стратегії {strategy.replace('_', ' ')}"
                    if localized else f"A visible {strategy.replace('_', ' ')} moment"
                ),
                "headline": (
                    f"Один чіткий крок · {strategy.replace('_', ' ')} · {call_number}"
                    if localized else f"One clear step · {strategy.replace('_', ' ')} · {call_number}"
                ),
                "primary_text": (
                    "Побачте малу послідовність до більшого зобов'язання."
                    if localized else "See the small sequence before making a larger commitment."
                ),
                "supporting_text": (
                    "Практична перша розмова з прозорим процесом."
                    if localized else "A practical first conversation with a transparent process."
                ),
                "offer": input_payload["approved_brief"]["offer"],
                "cta": input_payload["approved_brief"]["cta"],
                "caption": (
                    f"Сфокусований напрям {strategy.replace('_', ' ')} для першого кроку."
                    if localized else f"A focused {strategy.replace('_', ' ')} direction for the first step."
                ),
                "alt_text": (
                    f"Квадратний допис Universal Studio у напрямі {strategy.replace('_', ' ')}."
                    if localized else f"A square Universal Studio post using the {strategy.replace('_', ' ')} direction."
                ),
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


class FakeNotifier:
    def __init__(self, *statuses: str) -> None:
        self.statuses = list(statuses or ("delivered",))
        self.events: list[dict] = []

    def notify(self, event):
        self.events.append(dict(event))
        status = self.statuses.pop(0) if self.statuses else "delivered"
        return NotificationAttempt(
            status,
            provider_message_id="tg-1" if status == "delivered" else None,
            error_code=None if status == "delivered" else "FakeDeliveryFailure",
        )


def image_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (1200, 1200), color)
    output = BytesIO()
    image.save(output, format="JPEG", quality=92)
    return output.getvalue()


class FakePexels:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.counter = 0
        self.reject_first_sticker = False
        self.sticker_calls = 0

    def select(self, query: str, category: str, *, used_ids: set[str]):
        while True:
            self.counter += 1
            photo_id = str(700000 + self.counter)
            if photo_id not in used_ids:
                break
        is_sticker = "compass" in query
        if is_sticker:
            self.sticker_calls += 1
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
        alt = (
            "3D rendered compass icon"
            if is_sticker and self.reject_first_sticker and self.sticker_calls == 1
            else "A real photographed brass compass"
            if is_sticker else "A real editorial photograph"
        )
        self.calls.append({
            "query": query, "category": category, "photo_id": photo_id, "alt": alt,
        })
        return PexelsPhoto(
            photo_id=photo_id, width=1200, height=1200,
            image_url=f"https://images.pexels.com/photos/{photo_id}/image.jpeg",
            page_url=f"https://www.pexels.com/photo/{photo_id}/",
            photographer=f"Photographer {photo_id}",
            photographer_url=f"https://www.pexels.com/@photographer-{photo_id}/",
            alt=alt,
        ), output.getvalue()


class LocalExperimentFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.provider = FakeStructuredProvider()
        self.notifier = FakeNotifier()
        self.pexels = FakePexels()
        self.workspace = UniversalStudioWorkspace(self.root / "studio")
        self.store = LocalExperimentStore(self.root / "experiments")
        self.service = LocalExperimentService(
            store=self.store, workspace=self.workspace, provider=self.provider,
            repository_root=Path(__file__).resolve().parents[2], pexels=self.pexels,
            notifier=self.notifier,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _approved_brief(self):
        project, brief, created = self.service.create_brief(
            request_id=str(uuid4()), raw_idea="A guided launch-planning conversation.",
            required_language="en",
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

    def test_project_creation_language_is_immutable_and_inherited(self) -> None:
        request_id = str(uuid4())
        project, brief, created = self.service.create_brief(
            request_id=request_id,
            raw_idea="An English idea for a guided launch-planning conversation.",
            required_language="uk", requested_by="test-owner",
        )
        self.assertTrue(created)
        completed = self.service.generate_brief(brief["brief_id"])
        self.assertEqual("uk", completed["document"]["language"])
        self.assertIn("Безкоштовна", completed["document"]["offer"])
        self.assertIn("Забронювати", completed["document"]["cta"])

        replacement, created = self.service.correct_brief(
            completed["brief_id"], request_id=str(uuid4()),
            instruction="Make the audience narrower.", requested_by="test-owner",
        )
        self.assertTrue(created)
        corrected = self.service.generate_brief(replacement["brief_id"])
        self.assertEqual("uk", corrected["document"]["language"])
        revision_call = next(
            call for call in reversed(self.provider.calls)
            if call["mode"] == "product_brief_revision"
        )
        self.assertEqual("uk", revision_call["payload"]["required_language"])

        with self.assertRaisesRegex(ValueError, "different input"):
            self.service.create_brief(
                request_id=request_id,
                raw_idea="An English idea for a guided launch-planning conversation.",
                required_language="en", requested_by="test-owner",
            )

        source = self.store.get("sources", brief["owner_idea_source_id"])
        self.assertEqual("uk", source["required_language"])
        self.assertEqual(project["project_id"], completed["project_id"])

        _project_en, brief_en, created_en = self.service.create_brief(
            request_id=str(uuid4()),
            raw_idea="Українська ідея для однієї сфокусованої розмови.",
            required_language="en", requested_by="test-owner",
        )
        self.assertTrue(created_en)
        completed_en = self.service.generate_brief(brief_en["brief_id"])
        self.assertEqual("en", completed_en["document"]["language"])
        self.assertIn("Free", completed_en["document"]["offer"])

        _project_retry, brief_retry, _ = self.service.create_brief(
            request_id=str(uuid4()), raw_idea="Another English idea.",
            required_language="uk", requested_by="test-owner",
        )
        self.store.append("briefs", brief_retry["brief_id"], {
            **brief_retry, "status": "failed", "failure_count": 1,
            "error_code": "ProviderError", "error_message": "temporary failure",
        })
        self.service.retry_brief(brief_retry["brief_id"])
        retried = self.service.generate_brief(brief_retry["brief_id"])
        self.assertEqual("uk", retried["document"]["language"])
        retry_call = next(
            call for call in reversed(self.provider.calls) if call["mode"] == "product_brief"
        )
        self.assertEqual("uk", retry_call["payload"]["required_language"])

    def test_local_prompts_include_all_four_post_style_sources(self) -> None:
        anchors = (
            "Система, що повертає клієнтів. Поки ви займаєтесь роботою.",
            "5 незнайомців. 1 стіл.",
            "Не соцмережа. Не застосунок для знайомств.",
            "Track Your Wins, Not Your Slips",
        )
        for template in self.service.templates:
            prompt = self.service._candidate_prompt(template)
            self.assertTrue(all(anchor in prompt for anchor in anchors))
        self.assertEqual(
            self.service.post_copy_style_sha256,
            hashlib.sha256(self.service.post_copy_style_path.read_bytes()).hexdigest(),
        )

    def test_wrong_language_candidate_is_rejected_before_persistence(self) -> None:
        self.provider.wrong_candidate_language = True
        project, brief, created = self.service.create_brief(
            request_id=str(uuid4()), raw_idea="An English idea for one planning session.",
            required_language="uk", requested_by="test-owner",
        )
        self.assertTrue(created)
        brief = self.service.generate_brief(brief["brief_id"])
        brief, _ = self.service.approve_brief(brief["brief_id"], "test-owner")
        self._assets(project["project_id"])
        run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )

        failed = self.service.execute_run(run["run_id"])

        self.assertEqual("failed", failed["status"])
        self.assertIn("required language uk", failed["error_message"])
        self.assertEqual([], self.store.list("creatives"))

    def test_ukrainian_brief_produces_ukrainian_post_copy(self) -> None:
        project, brief, _ = self.service.create_brief(
            request_id=str(uuid4()), raw_idea="An English idea for one planning session.",
            required_language="uk", requested_by="test-owner",
        )
        brief = self.service.generate_brief(brief["brief_id"])
        brief, _ = self.service.approve_brief(brief["brief_id"], "test-owner")
        self._assets(project["project_id"])
        run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )

        completed = self.service.execute_run(run["run_id"])

        self.assertEqual("awaiting_review", completed["status"], completed.get("error_message"))
        review = self.service.get_review(run["run_id"])
        copy = review["creatives"][0]["document"]
        fields = (
            "hook", "headline", "primary_text", "supporting_text", "offer", "cta",
            "caption", "alt_text",
        )
        self.assertEqual("uk", infer_language(" ".join(copy[field] for field in fields)))
        self.assertEqual(brief["document"]["offer"], copy["offer"])
        self.assertEqual(brief["document"]["cta"], copy["cta"])

    def test_five_creatives_notify_approve_and_feed_future_learning(self) -> None:
        project, brief = self._approved_brief()
        self._assets(project["project_id"])
        run, created = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )
        self.assertTrue(created)

        awaiting = self.service.execute_run(run["run_id"])
        review = self.service.get_review(run["run_id"])
        creative_calls = [
            item for item in self.provider.calls if item["mode"] == "content_candidate_generation"
        ]
        self.assertEqual("awaiting_review", awaiting["status"])
        self.assertEqual(5, len(awaiting["generated_creative_ids"]))
        self.assertEqual(awaiting["generated_creative_ids"], awaiting["review_creative_ids"])
        self.assertEqual(5, len(creative_calls))
        self.assertEqual(5, len(review["creatives"]))
        self.assertEqual(5, len({item["preview"]["sha256"] for item in review["creatives"]}))
        self.assertTrue(all(item["layout_audit"]["passed"] for item in review["creatives"]))
        self.assertEqual(1, len(self.notifier.events))
        self.assertEqual(5, self.notifier.events[0]["creative_count"])
        self.assertEqual("delivered", review["notification"]["status"])
        self.assertTrue(all(
            not ({"score", "rank", "eligibility", "assessment"} & set(item))
            for item in review["creatives"]
        ))

        selected = review["creatives"][2]
        request_id = str(uuid4())
        approved = self.service.approve(
            run["run_id"], request_id=request_id,
            creative_id=selected["creative_id"], requested_by="test-owner",
        )
        repeated = self.service.approve(
            run["run_id"], request_id=request_id,
            creative_id=selected["creative_id"], requested_by="test-owner",
        )
        self.assertEqual("approved", approved["run"]["status"])
        self.assertEqual(selected["creative_id"], approved["run"]["approved_creative_id"])
        self.assertEqual(approved["release"]["release_id"], repeated["release"]["release_id"])
        with self.assertRaisesRegex(RuntimeError, "stale"):
            self.service.regenerate_all(
                run["run_id"], request_id=str(uuid4()), requested_by="test-owner",
            )

        package = self.service.release_download(run["run_id"])
        with zipfile.ZipFile(BytesIO(package["bytes"])) as archive:
            self.assertIn("owner-review.json", archive.namelist())
            self.assertNotIn("decision-trace.json", archive.namelist())
        feedback = self.store.list("feedback")
        weights = self.store.list("weight_updates")
        rules = self.store.list("learning_rules")
        self.assertEqual(["accepted"], [item["decision"] for item in feedback])
        self.assertEqual(1, len(weights))
        self.assertEqual({"preferred_direction", "preferred_layout"}, {
            item["rule_type"] for item in rules
        })

        next_run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )
        snapshot = self.store.get("learning_snapshots", next_run["learning_snapshot_id"])
        self.assertEqual({item["rule_id"] for item in rules}, {
            item["rule_id"] for item in snapshot["rules"]
        })

    def test_local_review_remains_available_without_commander_notification_relay(self) -> None:
        project, brief = self._approved_brief()
        self._assets(project["project_id"])
        self.service.notifier = None

        run, created = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )
        self.assertTrue(created)
        self.assertEqual("not_configured", run["notification_state"])

        awaiting = self.service.execute_run(run["run_id"])
        review = self.service.get_review(run["run_id"])
        self.assertEqual("awaiting_review", awaiting["status"])
        self.assertEqual(5, len(review["creatives"]))
        self.assertEqual("not_configured", awaiting["notification_state"])
        self.assertIsNone(awaiting["notification_receipt_id"])
        self.assertIsNone(review["notification"])

    def test_tune_replaces_one_slot_and_failed_child_preserves_parent(self) -> None:
        project, brief = self._approved_brief()
        self._assets(project["project_id"])
        parent, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )
        parent = self.service.execute_run(parent["run_id"])
        selected = parent["review_creative_ids"][1]
        comment = "Make the headline calmer and keep the same direction."
        child, created = self.service.tune(
            parent["run_id"], request_id=str(uuid4()), creative_id=selected,
            comment=comment, requested_by="test-owner",
        )
        self.assertTrue(created)
        tuned = self.service.execute_run(child["run_id"])
        self.assertEqual("awaiting_review", tuned["status"], tuned.get("error_message"))
        self.assertEqual(1, len(tuned["generated_creative_ids"]))
        self.assertEqual(5, len(tuned["review_creative_ids"]))
        self.assertNotIn(selected, tuned["review_creative_ids"])
        self.assertEqual(
            set(parent["review_creative_ids"]) - {selected},
            set(tuned["review_creative_ids"]) - set(tuned["generated_creative_ids"]),
        )
        tune_call = [
            item for item in self.provider.calls if item["mode"] == "content_candidate_generation"
        ][-1]
        self.assertEqual(comment, tune_call["payload"]["revision_instruction"]["comment"])
        self.assertEqual("superseded", self.service.get_run(parent["run_id"])["status"])

        project2, brief2 = self._approved_brief()
        self._assets(project2["project_id"])
        parent2, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief2["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )
        parent2 = self.service.execute_run(parent2["run_id"])
        self.provider.fail_candidate = True
        failed_child, _ = self.service.tune(
            parent2["run_id"], request_id=str(uuid4()),
            creative_id=parent2["review_creative_ids"][0],
            comment="Keep the structure but soften the opening.", requested_by="test-owner",
        )
        failed = self.service.execute_run(failed_child["run_id"])
        self.assertEqual("failed", failed["status"])
        self.assertEqual("awaiting_review", self.service.get_run(parent2["run_id"])["status"])
        action = next(
            item for item in self.store.list("review_actions")
            if item.get("child_run_id") == failed_child["run_id"]
        )
        self.assertEqual("failed", action["status"])

    def test_notification_failures_are_reviewable_and_retry_policy_is_bounded(self) -> None:
        project, brief = self._approved_brief()
        self._assets(project["project_id"])
        self.notifier = FakeNotifier(
            "definite_failure", "definite_failure", "definite_failure", "delivered",
        )
        self.service.notifier = self.notifier
        run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )
        awaiting = self.service.execute_run(run["run_id"])
        self.assertEqual("awaiting_review", awaiting["status"])
        self.assertEqual("definite_failure", awaiting["notification_state"])
        receipt = self.store.get(
            "notification_receipts", awaiting["notification_receipt_id"]
        )
        self.assertEqual(3, receipt["attempt_count"])
        retried = self.service.retry_review_notification(run["run_id"])
        self.assertEqual("delivered", retried["status"])
        self.assertEqual(4, retried["attempt_count"])

        project2, brief2 = self._approved_brief()
        self._assets(project2["project_id"])
        self.notifier = FakeNotifier("ambiguous", "delivered")
        self.service.notifier = self.notifier
        ambiguous_run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief2["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )
        ambiguous = self.service.execute_run(ambiguous_run["run_id"])
        self.assertEqual("ambiguous", ambiguous["notification_state"])
        self.assertNotIn(
            ambiguous_run["run_id"], self.service.recover_interrupted()["notification_run_ids"]
        )
        self.assertEqual(1, len(self.notifier.events))
        self.assertEqual(
            "delivered", self.service.retry_review_notification(ambiguous_run["run_id"])["status"]
        )

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
        self.assertEqual([], terminated["review_creative_ids"])
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
        self.assertIsNone(retry["parent_run_id"])
        self.assertEqual("queued", retry["status"])

    def test_regenerate_all_rejects_five_and_creates_five_fresh_identities(self) -> None:
        project, brief = self._approved_brief()
        self._assets(project["project_id"])
        parent, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=self.workspace.detail()["state_sha256"],
            requested_by="test-owner",
        )
        parent = self.service.execute_run(parent["run_id"])
        request_id = str(uuid4())
        child, created = self.service.regenerate_all(
            parent["run_id"], request_id=request_id, requested_by="test-owner",
        )
        self.assertTrue(created)
        repeated, repeated_created = self.service.regenerate_all(
            parent["run_id"], request_id=request_id, requested_by="test-owner",
        )
        self.assertFalse(repeated_created)
        self.assertEqual(child["run_id"], repeated["run_id"])
        regenerated = self.service.execute_run(child["run_id"])
        self.assertEqual("awaiting_review", regenerated["status"], regenerated.get("error_message"))
        self.assertEqual(5, len(regenerated["generated_creative_ids"]))
        self.assertTrue(set(parent["review_creative_ids"]).isdisjoint(
            regenerated["review_creative_ids"]
        ))
        parent_creatives = [self.store.get("creatives", item) for item in parent["review_creative_ids"]]
        child_creatives = [
            self.store.get("creatives", item) for item in regenerated["review_creative_ids"]
        ]
        for field in ("creative_id", "document_sha256", "media_identity_sha256", "provider_invocation_id"):
            self.assertTrue(
                {str(item[field]) for item in parent_creatives}.isdisjoint(
                    {str(item[field]) for item in child_creatives}
                ), field,
            )
        self.assertTrue(
            {item["preview"]["sha256"] for item in parent_creatives}.isdisjoint(
                {item["preview"]["sha256"] for item in child_creatives}
            )
        )
        rejected = [item for item in self.store.list("feedback") if item["decision"] == "rejected"]
        self.assertEqual(set(parent["review_creative_ids"]), {
            item["creative_id"] for item in rejected
        })

    def test_empty_asset_pool_sources_three_fresh_pexels_photos_and_real_sticker(self) -> None:
        self.pexels.reject_first_sticker = True
        project, brief = self._approved_brief()
        studio = self.workspace.detail()
        run, _ = self.service.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"], platform="instagram",
            studio_state_sha256=studio["state_sha256"], requested_by="test-owner",
        )
        completed = self.service.execute_run(run["run_id"])
        self.assertEqual("awaiting_review", completed["status"], completed.get("error_message"))
        initial = [
            item for item in self.store.list("creatives")
            if item["run_id"] == run["run_id"] and item["generation_kind"] == "initial"
        ]
        initial.sort(key=lambda item: item["slot"])
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
        self.assertEqual("photograph", sticker_source["media_type"])
        self.assertEqual("fresh_photographic_object_v2", sticker_source["selection_policy"])
        self.assertEqual(
            "ptw.pexels-photographic-object-evidence.v1",
            sticker_source["photographic_object_evidence"]["schema"],
        )
        self.assertEqual(2, self.pexels.sticker_calls)
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
        diversity = completed["diversity_audit"]
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
        self.assertEqual([], self.store.list("creatives"))

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
            self.assertEqual("awaiting_review", completed["status"], completed.get("error_message"))
            candidates = [
                item for item in self.store.list("creatives")
                if item["run_id"] == run["run_id"] and item["generation_kind"] == "initial"
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

    def test_fresh_structured_retry_uses_distinct_attempt_identity(self) -> None:
        calls = []

        def execute(command, **kwargs):
            calls.append({"command": list(command)})
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text("not-json" if len(calls) == 1 else '{"ok":true}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="event", stderr="")

        provider = LocalCodexStructuredProvider("codex-test", executor=execute)
        result = provider.call(
            mode="content_candidate_generation", system_prompt="Return the object.",
            input_payload={"value": 1},
            output_schema={
                "type": "object", "additionalProperties": False,
                "required": ["ok"], "properties": {"ok": {"type": "boolean"}},
            }, idempotency_key="retry", prompt_version="v1",
        )
        self.assertEqual(2, len(calls))
        self.assertEqual(["failed", "completed"], [item["status"] for item in result["invocation"]["attempts"]])

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
                "run_id": run_id, "status": "generating", "current_stage": "generating_creatives",
                "created_at": "2026-08-31T00:00:00Z", "updated_at": "2026-08-31T00:00:00Z",
            })
            store.append("checkpoints", checkpoint_id, {
                "checkpoint_id": checkpoint_id, "run_id": run_id, "stage": "generating_creatives",
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
                [
                    str(target), "--scope", "owner-experiments",
                    "--confirm=RESET PTW LOCAL RESULT DATA",
                ],
                cwd=repository, text=True, capture_output=True, check=False,
                env={**os.environ, "PATH": os.environ.get("PATH", "")},
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("preserve", sentinel.read_text(encoding="utf-8"))
            self.assertEqual([], list((local / "owner-experiments").iterdir()))
            for name in ("studio-workspace", "studio-tune"):
                self.assertEqual(["old.json"], [item.name for item in (local / name).iterdir()])


if __name__ == "__main__":
    unittest.main()
