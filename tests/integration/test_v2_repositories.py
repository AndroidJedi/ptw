from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from marketing_positioning.domain import PositioningDocumentV1
from marketing_positioning.repository import PositioningRepository
from natal.builder import preview_document
from natal.page import LandingPageContent, page_content_from_brief
from owner_gateway.landing import prepare_draft_set, prepare_landing_build
from owner_gateway.landing_draft_repository import LandingDraftRepository
from owner_gateway.landing_repository import LandingBuildRepository
from owner_gateway.leads import LandingLeadRepository


DATABASE_URL = os.environ.get("PTW_V2_TEST_DATABASE_URL", "")


def statement(text: str, source_id: str = "") -> dict[str, object]:
    return {"text": text, "source_ids": [source_id] if source_id else [], "assumption": not bool(source_id)}


def document(owner_source: str, research_source: str) -> dict[str, object]:
    return {
        "schema_version": 1, "output_language": "en",
        "positioning_foundation": {
            "category": statement("A focused planning tool", owner_source),
            "competitive_alternatives": [statement("Spreadsheets and manual reminders", research_source)],
            "definitive_audience": statement("Small teams coordinating follow-up", research_source),
            "jobs": [statement("Keep one next action visible", research_source)],
            "pains": [statement("Manual follow-up becomes scattered", research_source)],
            "gains": [statement("A clear shared next step", research_source)],
            "uvp": statement("Natal keeps a useful next step visible", owner_source),
        },
        "messaging_matrix": [{
            "feature": statement("Shared next-step view", owner_source),
            "functional_benefit": statement("The team sees the current action", owner_source),
            "emotional_reward": statement("The team can feel less uncertain"),
        }],
        "landing_copy": {
            "hero": {
                "eyebrow": statement("For small teams", research_source),
                "headline": statement("See the next step", owner_source),
                "subheadline": statement("Natal keeps the current action visible", owner_source),
                "cta": statement("Leave details", owner_source),
            },
            "value_sections": [
                {"title": statement(f"Value {index}", research_source), "body": statement(f"Source-backed detail {index}", research_source)}
                for index in range(1, 4)
            ],
            "honest_limitation": statement("Results are not yet verified."),
            "lead_capture_strategy": statement("Ask only for contact details", owner_source),
        },
        "ad_concepts": [
            {"kind": "contextual_relatable", "hook": statement("When the follow-up note gets lost", research_source), "body": statement("Keep the next step visible", owner_source), "visual_direction": statement("Show a real planning moment")},
            {"kind": "direct_problem_solution", "hook": statement("Scattered follow-up needs one view", research_source), "body": statement("Natal keeps the action visible", owner_source), "visual_direction": statement("Show the current-action view", owner_source)},
        ],
        "aeo_faqs": [
            {"question": statement(f"What is Natal {index}?", owner_source), "definition": statement("Natal is a focused planning tool.", owner_source), "data": statement("Available results are not yet verified."), "context": statement("It is intended for small-team follow-up.", owner_source)}
            for index in range(1, 4)
        ],
        "evidence_references": [owner_source, research_source],
        "assumptions": ["Emotional rewards and unverified results remain assumptions."],
    }


@unittest.skipUnless(DATABASE_URL, "PTW_V2_TEST_DATABASE_URL is required")
class V2RepositoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.positioning = PositioningRepository(DATABASE_URL)
        self.drafts = LandingDraftRepository(DATABASE_URL)
        self.builds = LandingBuildRepository(DATABASE_URL)

    def test_full_immutable_lineage_approval_landing_and_lead_flow(self) -> None:
        request_id = str(uuid4())
        project, first, created = self.positioning.create_project(
            request_id=request_id, raw_idea="Natal keeps a next step visible",
            target_country="US", research_language="en", output_language="en", requested_by="test-owner",
        )
        self.assertTrue(created)
        duplicate_project, duplicate_revision, duplicate_created = self.positioning.create_project(
            request_id=request_id, raw_idea="Natal keeps a next step visible",
            target_country="US", research_language="en", output_language="en", requested_by="test-owner",
        )
        self.assertFalse(duplicate_created)
        self.assertEqual(project["id"], duplicate_project["id"])
        self.assertEqual(first["id"], duplicate_revision["id"])
        with self.assertRaisesRegex(Exception, "Positioning project input is immutable"):
            with self.positioning.connection() as connection:
                connection.execute(
                    "UPDATE positioning_projects SET target_country='UA' WHERE entity_id=%s",
                    (project["id"],),
                )
        with self.assertRaisesRegex(ValueError, "different positioning input"):
            self.positioning.create_project(
                request_id=request_id, raw_idea="Different idea", target_country="US",
                research_language="en", output_language="en", requested_by="test-owner",
            )

        research_id = self.positioning.add_research_source(
            first["id"], title="Research finding", uri="https://example.com/research",
            publisher="Example", content="Small teams report scattered follow-up.",
            country="US", language="en", provider="dataforseo_serp",
            external_id=f"fixture-{uuid4()}", metadata={"remote_task_id": "paid-task-1"},
        )
        attempt_id, _ = self.positioning.start_attempt(first["id"])
        invocation = self.positioning.create_invocation(
            revision_id=first["id"], attempt_id=attempt_id, provider="dataforseo",
            mode="dataforseo_serp", idempotency_key=f"paid-{uuid4()}", request={"query": "follow-up"},
        )
        self.positioning.attach_remote_task(invocation["id"], "paid-task-1", 0.001, {"status": "ok"})
        self.positioning.attach_remote_task(invocation["id"], "paid-task-1", 0.001, {"status": "duplicate"})
        self.assertEqual(0.001, self.positioning.spend(first["id"]))
        value = PositioningDocumentV1.from_dict(
            document(project["owner_idea_source_id"], research_id),
            allowed_source_ids=[project["owner_idea_source_id"], research_id], output_language="en",
        )
        self.positioning.finish_attempt(first["id"], attempt_id, value.to_dict(), value.digest, value.quality_gates)
        first = self.positioning.approve(first["id"], "test-owner")
        self.assertTrue(first["approved"])

        replacement, was_created = self.positioning.create_revision(
            project_id=project["id"], request_id=str(uuid4()), base_revision_id=first["id"],
            section_id="landing_copy", instruction="Lead with the practical outcome", requested_by="test-owner",
        )
        self.assertTrue(was_created)
        replacement_attempt, _ = self.positioning.start_attempt(replacement["id"])
        self.positioning.finish_attempt(
            replacement["id"], replacement_attempt, value.to_dict(), value.digest, value.quality_gates,
        )
        replacement = self.positioning.approve(replacement["id"], "test-owner")
        self.assertTrue(replacement["approved"])
        self.assertFalse(self.positioning.get_revision(first["id"])["approved"])
        detail = self.positioning.get_project(project["id"])
        self.assertEqual(replacement["id"], detail["active_approved_revision_id"])
        proposals = self.positioning.skill_proposals(project["id"])
        self.assertEqual(1, len(proposals))
        self.assertEqual("pending", proposals[0]["status"])
        with self.positioning.connection() as connection:
            feedback = connection.execute(
                """SELECT feedback.target_id,weight.delta FROM commander_human_feedback feedback
                   JOIN commander_weight_updates weight ON weight.feedback_id=feedback.entity_id
                   WHERE feedback.entity_id=%s""", (replacement["feedback_id"],),
            ).fetchone()
            self.assertEqual(first["id"], str(feedback[0]))
            self.assertEqual(0, int(feedback[1]))

        prepared = prepare_draft_set(
            detail, replacement, privacy_policy_url="https://example.com/privacy",
        )
        draft, created = self.drafts.create(
            prepared, request_id=str(uuid4()), requested_by="test-owner",
        )
        self.assertTrue(created)
        self.drafts.mark_populating(draft["id"])
        pages = {
            template: page_content_from_brief(template, prepared["brief"]).to_dict()
            for template in ("product", "community", "waitlist")
        }
        previews = {
            template: preview_document(template, prepared["brief"], page)
            for template, page in pages.items()
        }
        draft = self.drafts.complete_population(
            draft["id"], pages=pages, previews=previews,
            summary="three strict variants", invocation={"mode": "natal_landing_revision"},
        )
        self.assertEqual({"product", "community", "waitlist"}, set(draft["current_snapshots"]))
        base = draft["current_snapshots"]["community"]
        edit_request = str(uuid4())
        self.drafts.create_edit(
            base["id"], request_id=edit_request, block_id="hero",
            instruction="Make the outcome concrete", requested_by="test-owner",
        )
        self.drafts.mark_editing(edit_request)
        page = LandingPageContent.from_dict(base["page_content"], expected_template_id="community")
        hero = dict(page.blocks["hero"]); hero["title"] = "One concrete next step"
        revised_page = page.replace_block("hero", hero)
        self.drafts.complete_edit(
            edit_request, page_content=revised_page.to_dict(),
            preview_html=preview_document("community", prepared["brief"], revised_page),
            summary="hero only", lesson="Lead with one concrete next step.", invocation={"mode": "natal_landing_revision"},
        )
        draft = self.drafts.get(draft["id"])
        current = draft["current_snapshots"]["community"]
        with self.assertRaisesRegex(Exception, "Landing draft input or completed population is immutable"):
            with self.drafts.connection() as connection:
                connection.execute(
                    "UPDATE landing_draft_sets SET source_brief='{}'::jsonb WHERE entity_id=%s",
                    (draft["id"],),
                )
        self.assertEqual(2, current["snapshot_number"])
        self.assertEqual(base["page_content"]["blocks"]["proof"], current["page_content"]["blocks"]["proof"])
        self.assertNotEqual(base["page_content"]["blocks"]["hero"], current["page_content"]["blocks"]["hero"])

        build_input = prepare_landing_build(draft, current)
        with tempfile.TemporaryDirectory() as temporary:
            build, created = self.builds.create(
                build_input, request_id=str(uuid4()), requested_by="test-owner",
                output_path=str(Path(temporary) / build_input["build_id"]), firebase_site_id="fixture-site",
            )
        self.assertTrue(created)
        self.builds.mark_building(build["id"])
        self.builds.mark_publishing(build["id"], manifest={"schema_version": 2}, artifact_sha256="f" * 64)
        build = self.builds.mark_published(
            build["id"], version="fixture-version", public_url=f"https://example.com/builds/{build['id']}/",
        )
        with self.assertRaisesRegex(Exception, "Landing build input or artifact is immutable"):
            with self.builds.connection() as connection:
                connection.execute(
                    "UPDATE landing_builds SET artifact_sha256=%s WHERE entity_id=%s",
                    ("a" * 64, build["id"]),
                )
        retry_input = prepare_landing_build(draft, current)
        with tempfile.TemporaryDirectory() as temporary:
            failed_build, _ = self.builds.create(
                retry_input, request_id=str(uuid4()), requested_by="test-owner",
                output_path=str(Path(temporary) / retry_input["build_id"]),
                firebase_site_id="fixture-site",
            )
        self.builds.mark_building(failed_build["id"])
        self.builds.mark_failed(
            failed_build["id"], code="FixtureFailure", message="fixture publication failed",
        )
        retried_build = self.builds.retry(failed_build["id"])
        self.assertEqual("queued", retried_build["status"])
        self.assertIsNone(retried_build["error_code"])
        with self.builds.connection() as connection:
            durable_failure = connection.execute(
                """SELECT action,details->>'error_code' FROM commander_audit_events
                   WHERE target_id=%s ORDER BY created_at""",
                (failed_build["id"],),
            ).fetchone()
        self.assertEqual(("landing.publication.failed", "FixtureFailure"), durable_failure)
        published_feedback = self.builds.record_feedback(
            build["id"], comment="Keep the published lead form concise", requested_by="test-owner",
        )
        landing_proposals = self.drafts.proposals(draft["id"])
        self.assertIn(published_feedback["proposal_id"], {item["id"] for item in landing_proposals})
        with self.builds.connection() as connection:
            feedback_edge = connection.execute(
                "SELECT relation FROM commander_relationships WHERE source_id=%s AND target_id=%s",
                (published_feedback["id"], build["id"]),
            ).fetchone()
        self.assertEqual("evaluates", feedback_edge[0])
        leads = LandingLeadRepository(DATABASE_URL, "integration-secret-that-is-at-least-32-bytes")
        ip_bits = uuid4().hex
        remote_ip = "2001:db8:" + ":".join(ip_bits[index:index + 4] for index in range(0, 24, 4))
        lead, created = leads.create(
            build["id"], {"form_id": "community_interest", "name": "Test", "email": "test@example.com", "website": ""},
            remote_ip=remote_ip,
        )
        self.assertTrue(created)
        duplicate, duplicate_created = leads.create(
            build["id"], {"form_id": "community_interest", "name": "Test", "email": "test@example.com", "website": ""},
            remote_ip=remote_ip,
        )
        self.assertFalse(duplicate_created)
        self.assertEqual(lead["id"], duplicate["id"])
        with self.assertRaisesRegex(ValueError, "outside the published form"):
            leads.create(
                build["id"],
                {
                    "form_id": "community_interest", "name": "Test",
                    "email": "extra@example.com", "unexpected": "must fail", "website": "",
                },
                remote_ip="203.0.113.9",
            )
        for index in range(4):
            _, additional_created = leads.create(
                build["id"],
                {
                    "form_id": "community_interest", "name": f"Visitor {index}",
                    "email": f"visitor-{index}@example.com", "website": "",
                },
                remote_ip=remote_ip,
            )
            self.assertTrue(additional_created)
        with self.assertRaisesRegex(PermissionError, "rate limit"):
            leads.create(
                build["id"],
                {
                    "form_id": "community_interest", "name": "Sixth",
                    "email": "sixth@example.com", "website": "",
                },
                remote_ip=remote_ip,
            )
        first_attempt = leads.record_attempt(
            lead["id"], status="suppressed", chat_id=42,
            error_code="EmergencyStop", error_message="suppressed until owner retry",
        )
        retry_attempt = leads.record_attempt(
            lead["id"], status="sent", chat_id=42, message_id=9001,
        )
        self.assertEqual(1, first_attempt["attempt_number"])
        self.assertEqual(2, retry_attempt["attempt_number"])
        self.assertEqual(9001, retry_attempt["telegram_message_id"])
        with leads.connection() as connection:
            stored = connection.execute(
                """SELECT ip_hmac,relation FROM landing_leads lead
                   JOIN commander_relationships relation ON relation.source_id=lead.entity_id
                   WHERE lead.entity_id=%s""", (lead["id"],),
            ).fetchone()
        self.assertNotEqual(remote_ip, stored[0])
        self.assertEqual("submitted_to", stored[1])

    def test_recovery_releases_only_the_positioning_guard(self) -> None:
        with self.positioning.connection() as connection:
            operation_id = str(uuid4())
            connection.execute(
                """UPDATE commander_operation_guard SET operation_kind='codex_plan',operation_id=%s,
                          acquired_at=clock_timestamp() WHERE singleton""", (operation_id,),
            )
        self.positioning.recover_interrupted()
        with self.positioning.connection() as connection:
            row = connection.execute(
                "SELECT operation_kind,operation_id FROM commander_operation_guard WHERE singleton"
            ).fetchone()
            self.assertEqual("codex_plan", row[0])
            self.assertEqual(operation_id, str(row[1]))
            connection.execute(
                "UPDATE commander_operation_guard SET operation_kind=NULL,operation_id=NULL,acquired_at=NULL WHERE singleton"
            )

    def test_retry_queues_a_new_durable_attempt_without_erasing_failure_history(self) -> None:
        project, revision, _ = self.positioning.create_project(
            request_id=str(uuid4()), raw_idea="A retry fixture", target_country="US",
            research_language="en", output_language="en", requested_by="test-owner",
        )
        attempt_id, attempt_number = self.positioning.start_attempt(revision["id"])
        self.positioning.fail_attempt(revision["id"], attempt_id, RuntimeError("fixture failure"))
        queued = self.positioning.queue_retry(revision["id"])
        self.assertEqual("queued", queued["status"])
        self.assertEqual(1, queued["failure_count"])
        next_attempt_id, next_attempt_number = self.positioning.start_attempt(revision["id"])
        self.assertEqual(attempt_number + 1, next_attempt_number)
        self.positioning.fail_attempt(revision["id"], next_attempt_id, RuntimeError("fixture retry failure"))
        with self.positioning.connection() as connection:
            attempts = connection.execute(
                "SELECT attempt_number,status FROM positioning_generation_attempts WHERE revision_id=%s ORDER BY attempt_number",
                (revision["id"],),
            ).fetchall()
        self.assertEqual([(1, "failed"), (2, "failed")], attempts)


if __name__ == "__main__":
    unittest.main()
