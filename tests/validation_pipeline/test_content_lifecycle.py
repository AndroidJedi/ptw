from __future__ import annotations

import os
from pathlib import Path
import unittest
from uuid import uuid4

from validation_pipeline.content import ContentContextAssembler, CorpusStore, TemplateRegistry
from validation_pipeline.content_repository import ContentResultRepository
from validation_pipeline.content_service import CandidateGenerationOrchestrator
from validation_pipeline.domain import ProductBriefV1
from validation_pipeline.images import PexelsPhoto
from validation_pipeline.natal_brand import natal_logo_bytes
from validation_pipeline.repository import ValidationRepository
from validation_pipeline.studio import StudioRenderer


ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "skills/content-candidate-generator/references"


class FakeBridge:
    def __init__(self) -> None:
        self.candidate_calls: list[dict] = []
        self.critic_calls: list[dict] = []
        self.last_invocation: dict = {}

    def generate_content_candidate(self, *, input_payload: dict, **_kwargs) -> dict:
        call = len(self.candidate_calls) + 1
        self.candidate_calls.append(input_payload)
        brief = input_payload["approved_brief"]["document"]
        instagram = input_payload["output_profile"] == "instagram_static_ad_v1"
        response = {
            "schema_version": 2,
            "hook": f"At 23:00, one question is still open · {call}",
            "headline": "Turn one uncertain moment into a clear next step",
            "primary_text": "Start with a short, transparent conversation about the decision in front of you.",
            "supporting_text": "One question, a visible process, and no invented promises.",
            "offer": brief["offer"],
            "cta": brief["cta"],
            "caption": "A specific first step for the decision that is already taking your attention.",
            "alt_text": (
                "A real photograph beside a concise decision-session offer."
                if instagram else "A text Result explaining one clear first step."
            ),
            "desired_emotion": "calm confidence",
            "visual_concept": (
                "One candid real scene with a clear subject and reserved text hierarchy."
                if instagram else "No visual is requested for the text profile."
            ),
            "media_request": ({
                "kind": "pexels_real_photo", "query": "adult making a decision at desk",
                "source_asset_id": None, "reason": "A real photograph supports the supplied moment.",
            } if instagram else {
                "kind": "none", "query": "", "source_asset_id": None,
                "reason": "The selected profile is text only.",
            }),
            "visual_components": ([{
                "role": role, "content": role.replace("_", " "), "source_ids": [],
            } for role in (
                "background", "primary_subject", "headline_block", "supporting_text_block",
                "offer_block", "cta_block", "brand_mark", "lighting_style", "composition",
            )] if instagram else []),
        }
        invocation = {
            "bridge_request_id": call, "bridge_attempt": 1,
            "prior_failed_request_ids": [], "provider": "fake",
        }
        self.last_invocation = invocation
        return {"response": response, "invocation": invocation}

    def generate_content_critic(
        self, *, input_payload: dict, images: list[dict], response_validator, **_kwargs,
    ) -> dict:
        pass_number = int(input_payload["pass"])
        candidates = list(input_payload["candidates"])
        ids = [item["candidate_id"] for item in candidates]
        self.critic_calls.append({"pass": pass_number, "ids": ids, "images": images})
        evaluations = []
        for index, item in enumerate(candidates):
            score = 10 - index
            evaluations.append({
                "candidate_id": item["candidate_id"],
                "hard_gates": {
                    "task_brief_relevance": True, "exact_offer_cta": True,
                    "language_required_fields": True, "honest_claims": True,
                    "project_brand_media_tools": True, "one_coherent_message": True,
                    "no_synthetic_people_faces": True, "safe_crop_layout": True,
                    "protected_copy_legible": True, "caption_alt_text_accessible": True,
                },
                "element_scores": [{
                    "element_id": element["element_id"],
                        "task_fit": score, "clarity": score,
                        "contribution": score, "coherence": score,
                    }
                    for element in item["elements"]
                ],
                "scores": {
                    "task_brief_suitability": score, "hook_strength": score,
                    "message_clarity": score, "persuasion_action": score,
                    "coherence": score, "specificity_credibility": score,
                    "composition_legibility": score, "originality_tone": score,
                },
                "complexity": "none", "reason_codes": ["eligible"],
            })
        pairwise = []
        pairs = [(0, 1)] if pass_number == 3 else [(0, 1), (0, 2), (1, 2)]
        for left, right in pairs:
            pairwise.append({
                "left": ids[left], "right": ids[right], "winner": ids[left],
                "reason_codes": ["clearer"],
            })
        actions = []
        if pass_number in {1, 2}:
            for ordinal in range(2):
                base = candidates[ordinal]
                by_slot = {item["slot"]: item["element_id"] for item in base["elements"]}
                actions.append({
                    "action_type": "recompose" if pass_number == 1 else "regenerate_elements",
                    "base_candidate_id": base["candidate_id"], "template_id": None,
                    "locked_element_ids": [by_slot["hook"], by_slot["cta"]],
                    "target_element_ids": [by_slot["supporting_text"]],
                    "source_element_ids": [by_slot["visual_concept"]],
                    "slider_values": None, "reason_codes": ["targeted_improvement"],
                })
        final_selection = None
        if pass_number == 3:
            final_selection = {
                "candidate_id": ids[0],
                "decision_summary": [
                    "The hook begins with a concrete customer moment.",
                    "The message makes the next step immediately understandable.",
                ],
            }
        response = {
            "pass": pass_number, "evaluations": evaluations, "ranking": ids,
            "pairwise": pairwise, "actions": actions,
            "observations": [f"Pass {pass_number} completed within its bounded scope."],
            "final_selection": final_selection,
        }
        invocation = {
            "bridge_request_id": 100 + pass_number, "bridge_attempt": 1,
            "prior_failed_request_ids": [], "provider": "fake",
        }
        self.last_invocation = invocation
        return {"response": dict(response_validator(response)), "invocation": invocation}


class FakePexels:
    def __init__(self) -> None:
        self.calls = 0

    def select(self, _query: str, _category: str, *, used_ids: set[str]):
        from io import BytesIO
        from PIL import Image, ImageDraw

        self.calls += 1
        photo_id = str(900000 + self.calls)
        if photo_id in used_ids:
            raise AssertionError("fake Pexels source was unexpectedly reused")
        image = Image.new("RGB", (1200, 1200), "#846B60")
        draw = ImageDraw.Draw(image)
        draw.ellipse((520, 120, 1080, 680), fill="#D3B39C")
        draw.rectangle((590, 600, 980, 1180), fill="#473540")
        output = BytesIO()
        image.save(output, format="JPEG", quality=90)
        return PexelsPhoto(
            photo_id=photo_id, width=1200, height=1200,
            image_url=f"https://images.pexels.com/photos/{photo_id}/image.jpeg",
            page_url=f"https://www.pexels.com/photo/{photo_id}/",
            photographer="PTW Canary", photographer_url="https://www.pexels.com/@ptw-canary/",
            alt="An adult considering a decision at a desk",
        ), output.getvalue()


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
        templates = TemplateRegistry(REFERENCES / "templates")
        assembler = ContentContextAssembler(
            generator_skill_path=ROOT / "skills/content-candidate-generator/SKILL.md",
            critic_skill_path=ROOT / "skills/content-result-critic/SKILL.md",
            template_registry=templates,
            corpus_store=CorpusStore(
                REFERENCES / "corpus/manifest.json", REFERENCES / "corpus/examples.jsonl",
            ),
        )
        self.orchestrator = CandidateGenerationOrchestrator(
            repository=self.repository, bridge=self.bridge,
            context_assembler=assembler, template_registry=templates,
            recipe_renderer=StudioRenderer(), pexels=FakePexels(),
        )

    def _approved_brief(self) -> dict:
        raw_idea = "A guided decision service for people who need one clear next step."
        brief, _ = self.authority.create_brief(
            request_id=str(uuid4()), raw_idea=raw_idea, requested_by="test",
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
            "cta": "Book a session", "trust_strategy": "Explain the process before asking for commitment",
            "offer": "First short assessment free",
        }, raw_idea=raw_idea)
        self.authority.finish_brief(
            brief["brief_id"], attempt_id, document.to_dict(), document.digest, document.quality_gates,
        )
        approved, _ = self.authority.approve_brief(brief["brief_id"], "test")
        return self.authority.get_brief(brief["brief_id"])

    def test_five_candidates_four_improvements_three_passes_one_result(self) -> None:
        brief = self._approved_brief()
        run, created = self.orchestrator.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"],
            task="Create one concise marketing result for the approved service.",
            output_profile="marketing_copy_v1", requested_by="test",
        )
        self.assertTrue(created)
        self.assertEqual("Natal", run["context_bundle"]["brand_kit"]["document"]["name"])
        logo_id = run["context_bundle"]["brand_kit"]["document"]["logo_source_asset_id"]
        logo = self.authority.get_project_asset(logo_id)
        self.assertEqual("canonical_brand", logo["origin"])
        self.assertEqual("natal", logo["provider"])
        repeated_brand = self.authority.ensure_natal_brand_kit(
            brief["project_id"], logo_data=natal_logo_bytes(), requested_by="test",
        )
        self.assertEqual(run["brand_kit_id"], repeated_brand["brand_kit_id"])
        result = self.orchestrator.execute(run["run_id"])

        completed = self.repository.get_run(run["run_id"])
        candidates = self.repository.list_candidates(run["run_id"])
        self.assertEqual("completed", completed["status"])
        self.assertEqual(9, len(candidates))
        self.assertEqual(5, len([item for item in candidates if item["generation_kind"] == "initial"]))
        self.assertEqual(4, len([item for item in candidates if item["generation_kind"] != "initial"]))
        self.assertEqual(9, len(self.bridge.candidate_calls))
        self.assertEqual([1, 2, 3], [item["pass"] for item in self.bridge.critic_calls])
        self.assertEqual(3, completed["critic_pass_count"])
        self.assertEqual(0, completed["budget_state"]["initial_generation_remaining"])
        self.assertEqual(0, completed["budget_state"]["improvement_generation_remaining"])
        self.assertEqual(0, completed["budget_state"]["critic_calls_remaining"])
        self.assertEqual(result["creative_id"], completed["final_result_id"])
        self.assertEqual(1, len({result["creative_id"]}))
        self.assertEqual(2, len(result["decision_summary"]))
        self.assertTrue(all(len(item["images"]) in {2, 5} for item in self.bridge.critic_calls))

        debug_before = self.repository.debug(run["run_id"])
        initial_debug = [
            item for item in debug_before["candidates"] if item["generation_kind"] == "initial"
        ]
        self.assertEqual(5, len(initial_debug))
        self.assertTrue(all(item["preview"]["mime_type"] == "image/jpeg" for item in initial_debug))
        self.assertTrue(all(item["preview"]["width"] == 1080 for item in initial_debug))
        self.assertTrue(all(
            item["preview"]["asset_url"] == (
                f"/api/v1/content-runs/{run['run_id']}/candidates/{item['candidate_id']}/asset"
            )
            for item in initial_debug
        ))
        first_preview = self.repository.candidate_preview(
            initial_debug[0]["candidate_id"], expected_run_id=run["run_id"],
        )
        self.assertEqual(initial_debug[0]["preview"]["sha256"], first_preview["sha256"])
        repeated = self.orchestrator.execute(run["run_id"])
        debug_after = self.repository.debug(run["run_id"])
        self.assertEqual(result["creative_id"], repeated["creative_id"])
        self.assertEqual(9, len(self.bridge.candidate_calls))
        self.assertEqual(3, len(self.bridge.critic_calls))
        self.assertEqual(len(debug_before["checkpoints"]), len(debug_after["checkpoints"]))
        self.assertEqual(17, len(debug_after["checkpoints"]))

        feedback = self.repository.record_feedback(
            run["run_id"], decision="accepted", comment="Keep the concrete opening.",
            requested_by="test",
        )
        self.assertEqual(result["creative_id"], feedback["creative_id"])
        self.assertEqual(2, len(feedback["proposal_ids"]))

    def test_instagram_recipes_persist_replay_metadata_and_direct_parent_edges(self) -> None:
        brief = self._approved_brief()
        run, _ = self.orchestrator.create_run(
            request_id=str(uuid4()), brief_id=brief["brief_id"],
            task="Create one concise Instagram post using a candid real photograph.",
            output_profile="instagram_static_ad_v1", requested_by="test",
        )
        self.orchestrator.execute(run["run_id"])
        candidates = self.repository.list_candidates(run["run_id"])
        self.assertEqual(9, len(candidates))
        by_candidate = {item["candidate_id"]: item for item in candidates}
        recipes = {
            item["candidate_id"]: self.authority.get_recipe(item["recipe_id"])
            for item in candidates
        }
        for candidate in candidates:
            recipe = recipes[candidate["candidate_id"]]
            metadata = recipe["document"]["modifiers"][0]["params"]
            render = self.authority.get_render(candidate["render_id"])
            self.assertEqual("studio.layout.template_application.v1", metadata["schema"])
            self.assertEqual(recipe["document_sha256"], render["manifest"]["resolved_recipe"]["sha256"])
            self.assertEqual("ptw-result-instagram-renderer-v2", render["renderer_version"])
            self.assertEqual(2, metadata["studio_template"]["version"])
            parent_candidate_id = candidate["parent_candidate_id"]
            if parent_candidate_id is None:
                self.assertIsNone(recipe["parent_recipe_id"])
                self.assertIsNone(metadata["base_recipe_sha256"])
            else:
                parent_recipe = recipes[parent_candidate_id]
                self.assertEqual(parent_recipe["recipe_id"], recipe["parent_recipe_id"])
                self.assertEqual(parent_recipe["document_sha256"], metadata["base_recipe_sha256"])
                self.assertIn(parent_candidate_id, by_candidate)
        with self.authority.connection() as connection:
            parent_edges = int(connection.execute(
                """SELECT count(*) FROM commander_relationships edge
                   JOIN commander_entities source ON source.id=edge.source_id
                   JOIN commander_entities target ON target.id=edge.target_id
                   WHERE edge.relation='derived_from' AND source.kind='studio_recipe'
                     AND target.kind='studio_recipe' AND edge.attributes->>'input'='parent_recipe'"""
            ).fetchone()[0])
        self.assertEqual(4, parent_edges)

    def test_restart_fails_orphaned_queued_brief_and_releases_operation(self) -> None:
        brief, _ = self.authority.create_brief(
            request_id=str(uuid4()), raw_idea="A queued Product Brief interrupted before its task starts.",
            requested_by="test", reserve_operation=True,
        )
        with self.assertRaisesRegex(RuntimeError, "another generation operation"):
            self.authority.create_brief(
                request_id=str(uuid4()), raw_idea="A second idea must not become an orphaned row.",
                requested_by="test", reserve_operation=True,
            )
        self.assertEqual(1, self.authority.activity()["briefs"])

        recovered = self.authority.recover_interrupted()

        failed = self.authority.get_brief(brief["brief_id"])
        self.assertEqual(1, recovered["briefs"])
        self.assertEqual("failed", failed["status"])
        self.assertEqual("Interrupted", failed["error_code"])
        self.assertIsNone(self.authority.activity()["operation"])


if __name__ == "__main__":
    unittest.main()
