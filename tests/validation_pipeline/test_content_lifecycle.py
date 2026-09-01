from __future__ import annotations

import os
from pathlib import Path
import unittest
from uuid import uuid4

from validation_pipeline.content import ContentContextAssembler, CorpusStore, TemplateRegistry
from validation_pipeline.content_repository import ContentResultRepository
from validation_pipeline.content_service import CandidateGenerationOrchestrator
from validation_pipeline.domain import ProductBriefV1
from validation_pipeline.natal_brand import natal_logo_bytes
from validation_pipeline.repository import ValidationRepository
from validation_pipeline.review_notifications import NotificationAttempt
from validation_pipeline.studio import StudioRenderer


ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "skills/content-candidate-generator/references"


class FakeBridge:
    def __init__(self) -> None:
        self.candidate_calls: list[dict] = []
        self.last_invocation: dict = {}
        self.fail_next = False

    def generate_content_candidate(self, *, input_payload: dict, **_kwargs) -> dict:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("injected generation failure")
        call = len(self.candidate_calls) + 1
        self.candidate_calls.append(input_payload)
        brief = input_payload["approved_brief"]["document"]
        response = {
            "schema_version": 2,
            "hook": f"At 23:00, one question is still open · {call}",
            "headline": f"Turn uncertainty into one clear next step · {call}",
            "primary_text": "Start with a short, transparent conversation about the decision in front of you.",
            "supporting_text": "One question, a visible process, and no invented promises.",
            "offer": brief["offer"], "cta": brief["cta"],
            "caption": f"A specific first step for the decision taking your attention · {call}.",
            "alt_text": f"A text post explaining one clear first step, direction {call}.",
            "desired_emotion": "calm confidence",
            "visual_concept": "No visual is requested for the text profile.",
            "media_request": {
                "kind": "none", "query": "", "source_asset_id": None,
                "reason": "The selected profile is text only.",
            },
            "visual_components": [],
        }
        invocation = {
            "bridge_request_id": f"fake-{call}", "bridge_attempt": 1,
            "prior_failed_request_ids": [], "provider": "fake",
        }
        self.last_invocation = invocation
        return {"response": response, "invocation": invocation}


class FakeNotifier:
    def __init__(self, *statuses: str) -> None:
        self.statuses = list(statuses or ("delivered",))
        self.events: list[dict] = []

    def notify(self, event: dict) -> NotificationAttempt:
        self.events.append(dict(event))
        status = self.statuses.pop(0) if self.statuses else "delivered"
        return NotificationAttempt(
            status,
            provider_message_id="telegram-1" if status == "delivered" else None,
            error_code=None if status == "delivered" else "FakeDeliveryFailure",
        )


@unittest.skipUnless(os.environ.get("PTW_TEST_DATABASE_URL"), "disposable PostgreSQL is required")
class ContentLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authority = ValidationRepository(os.environ["PTW_TEST_DATABASE_URL"])
        self.repository = ContentResultRepository(self.authority)
        with self.authority.connection() as connection:
            connection.execute("TRUNCATE commander_entities CASCADE")
            connection.execute(
                "UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL WHERE singleton"
            )
        self.bridge = FakeBridge()
        self.notifier = FakeNotifier()
        templates = TemplateRegistry(REFERENCES / "templates")
        assembler = ContentContextAssembler(
            generator_skill_path=ROOT / "skills/content-candidate-generator/SKILL.md",
            template_registry=templates,
            corpus_store=CorpusStore(
                REFERENCES / "corpus/manifest.json", REFERENCES / "corpus/examples.jsonl",
            ),
        )
        self.orchestrator = CandidateGenerationOrchestrator(
            repository=self.repository, bridge=self.bridge,
            context_assembler=assembler, template_registry=templates,
            recipe_renderer=StudioRenderer(), pexels=object(), notifier=self.notifier,
        )

    def _approved_brief(self) -> dict:
        raw_idea = "A guided decision service for people who need one clear next step."
        brief, _ = self.authority.create_brief(
            request_id=str(uuid4()), raw_idea=raw_idea, required_language="en",
            requested_by="test",
        )
        attempt_id, _ = self.authority.start_attempt(brief["brief_id"], stage="product_brief")
        document = ProductBriefV1.from_dict({
            "schema_version": 1, "language": "en", "product": "Decision Session",
            "target_audience": "People facing one specific personal or business decision",
            "main_pain": "The same unresolved question keeps consuming attention",
            "promise": "Turn one uncertain decision into a practical next step",
            "key_benefits": [
                "A focused conversation", "A transparent sequence", "A practical next action",
            ],
            "cta": "Book a session",
            "trust_strategy": "Explain the process before asking for commitment",
            "offer": "First short consultation free",
        }, raw_idea=raw_idea)
        self.authority.finish_brief(
            brief["brief_id"], attempt_id, document.to_dict(), document.digest,
            document.quality_gates,
        )
        self.authority.approve_brief(brief["brief_id"], "test")
        return self.authority.get_brief(brief["brief_id"])

    def _run(self) -> dict:
        brief = self._approved_brief()
        run, created = self.orchestrator.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"],
            task="Create five concise owner-review directions for the approved service.",
            output_profile="marketing_copy_v1", requested_by="test",
        )
        self.assertTrue(created)
        self.assertEqual("Natal", run["context_bundle"]["brand_kit"]["document"]["name"])
        logo_id = run["context_bundle"]["brand_kit"]["document"]["logo_source_asset_id"]
        self.assertEqual("canonical_brand", self.authority.get_project_asset(logo_id)["origin"])
        repeated_brand = self.authority.ensure_natal_brand_kit(
            brief["project_id"], logo_data=natal_logo_bytes(), requested_by="test",
        )
        self.assertEqual(run["brand_kit_id"], repeated_brand["brand_kit_id"])
        return run

    def test_five_creatives_notify_and_approve(self) -> None:
        run = self._run()
        awaiting = self.orchestrator.execute(run["run_id"])
        review = self.repository.get_review(run["run_id"])

        self.assertEqual("awaiting_review", awaiting["status"])
        self.assertEqual(5, len(self.bridge.candidate_calls))
        self.assertEqual(5, len(awaiting["generated_creative_ids"]))
        self.assertEqual(awaiting["generated_creative_ids"], awaiting["review_creative_ids"])
        self.assertEqual(5, len(review["creatives"]))
        self.assertEqual(5, len({item["document_sha256"] for item in review["creatives"]}))
        self.assertEqual(5, len({item["preview"]["sha256"] for item in review["creatives"]}))
        self.assertEqual(1, len(self.notifier.events))
        self.assertEqual("delivered", review["notification"]["status"])
        self.assertTrue(all(
            not ({"score", "rank", "eligibility", "assessment"} & set(item))
            for item in review["creatives"]
        ))

        selected = review["creatives"][0]["creative_id"]
        request_id = str(uuid4())
        approved = self.orchestrator.approve(
            run_id=run["run_id"], request_id=request_id,
            creative_id=selected, requested_by="test",
        )
        repeated = self.orchestrator.approve(
            run_id=run["run_id"], request_id=request_id,
            creative_id=selected, requested_by="test",
        )
        self.assertEqual("approved", approved["run"]["status"])
        self.assertEqual(selected, approved["run"]["approved_creative_id"])
        self.assertEqual(approved["action"]["action_id"], repeated["action"]["action_id"])
        self.assertGreater(len(self.repository.creative_export(run["run_id"], selected)["bytes"]), 100)
        with self.authority.connection() as connection:
            counts = connection.execute(
                """SELECT
                     (SELECT count(*) FROM commander_human_feedback),
                     (SELECT count(*) FROM commander_weight_updates),
                     (SELECT count(*) FROM content_learning_rules),
                     (SELECT count(*) FROM content_creative_approvals),
                     (SELECT count(*) FROM commander_relationships
                       WHERE relation IN ('evaluates','contains','derived_from','adjusts'))"""
            ).fetchone()
        self.assertEqual((1, 1, 2, 1), tuple(map(int, counts[:4])))
        self.assertGreater(int(counts[4]), 0)

    def test_tune_replaces_one_slot_and_failure_keeps_parent_actionable(self) -> None:
        parent = self.orchestrator.execute(self._run()["run_id"])
        selected = parent["review_creative_ids"][2]
        comment = "Make the opening calmer while retaining this strategy."
        child, created = self.orchestrator.tune(
            run_id=parent["run_id"], request_id=str(uuid4()), creative_id=selected,
            comment=comment, requested_by="test",
        )
        self.assertTrue(created)
        tuned = self.orchestrator.execute(child["run_id"])
        self.assertEqual("awaiting_review", tuned["status"])
        self.assertEqual(1, len(tuned["generated_creative_ids"]))
        self.assertEqual(5, len(tuned["review_creative_ids"]))
        self.assertNotIn(selected, tuned["review_creative_ids"])
        self.assertEqual(
            set(parent["review_creative_ids"]) - {selected},
            set(tuned["review_creative_ids"]) - set(tuned["generated_creative_ids"]),
        )
        self.assertEqual("superseded", self.repository.get_run(parent["run_id"])["status"])
        self.assertEqual(comment, self.bridge.candidate_calls[-1]["revision_instruction"]["comment"])
        self.assertEqual(5, len(self.repository.get_review(child["run_id"])["creatives"]))

        parent2 = self.orchestrator.execute(self._run()["run_id"])
        child2, _ = self.orchestrator.tune(
            run_id=parent2["run_id"], request_id=str(uuid4()),
            creative_id=parent2["review_creative_ids"][0],
            comment="Keep this direction but soften the first line.", requested_by="test",
        )
        self.bridge.fail_next = True
        failed = self.orchestrator.execute(child2["run_id"])
        self.assertEqual("failed", failed["status"])
        self.assertEqual("awaiting_review", self.repository.get_run(parent2["run_id"])["status"])
        with self.authority.connection() as connection:
            action_status = connection.execute(
                "SELECT status FROM content_review_actions WHERE child_run_id=%s",
                (child2["run_id"],),
            ).fetchone()[0]
        self.assertEqual("failed", action_status)

    def test_regenerate_all_is_idempotent_and_excludes_prior_identities(self) -> None:
        parent = self.orchestrator.execute(self._run()["run_id"])
        request_id = str(uuid4())
        child, created = self.orchestrator.regenerate_all(
            run_id=parent["run_id"], request_id=request_id, requested_by="test",
        )
        repeated, repeated_created = self.orchestrator.regenerate_all(
            run_id=parent["run_id"], request_id=request_id, requested_by="test",
        )
        self.assertTrue(created)
        self.assertFalse(repeated_created)
        self.assertEqual(child["run_id"], repeated["run_id"])
        regenerated = self.orchestrator.execute(child["run_id"])
        self.assertEqual("awaiting_review", regenerated["status"])
        self.assertEqual(5, len(regenerated["generated_creative_ids"]))
        self.assertTrue(set(parent["review_creative_ids"]).isdisjoint(
            regenerated["review_creative_ids"]
        ))
        parent_creatives = [self.repository.get_creative(item) for item in parent["review_creative_ids"]]
        child_creatives = [self.repository.get_creative(item) for item in regenerated["review_creative_ids"]]
        for field in ("creative_id", "document_sha256", "provider_invocation_id"):
            self.assertTrue(
                {item[field] for item in parent_creatives}.isdisjoint(
                    {item[field] for item in child_creatives}
                ), field,
            )
        with self.authority.connection() as connection:
            rejected = connection.execute(
                """SELECT feedback.target_id FROM commander_human_feedback feedback
                    JOIN commander_entities entity ON entity.id=feedback.entity_id
                    WHERE entity.attributes->>'decision'='rejected'"""
            ).fetchall()
        self.assertEqual(set(parent["review_creative_ids"]), {str(row[0]) for row in rejected})


if __name__ == "__main__":
    unittest.main()
