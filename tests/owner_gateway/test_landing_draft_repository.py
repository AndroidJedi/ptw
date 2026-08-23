from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest


POSTGRES_AVAILABLE = bool(
    os.environ.get("LANDING_TEST_DATABASE_URL") and importlib.util.find_spec("psycopg")
)

if POSTGRES_AVAILABLE:
    import psycopg

    from natal.builder import preview_document
    from natal.page import page_content_from_brief
    from owner_gateway.landing_draft_repository import LandingDraftRepository
    from owner_gateway.landing_repository import LandingBuildRepository


RUN_ID = "01234567-89ab-7def-8123-456789abcdef"
THESIS_ID = "11234567-89ab-7def-8123-456789abcdef"
REQUEST_ID = "21234567-89ab-7def-8123-456789abcdef"
EDIT_ID = "31234567-89ab-7def-8123-456789abcdef"


def brief() -> dict:
    return {
        "schema_version": 1, "brand": "Natal", "language": "uk",
        "source": {"laval_run_id": RUN_ID, "thesis_id": THESIS_ID},
        "business_idea": "A durable sourced landing", "target_audience": "Evaluated audience",
        "pain": "Evaluated pain", "promise": "Evaluated promise",
        "key_features": [{"title": "Feature", "description": "Truthful detail"}],
        "steps": [
            {"title": "01", "description": "Start"},
            {"title": "02", "description": "Continue"},
        ],
        "proof_points": ["Verified proof"], "faq": [],
        "cta": {"label": "Try Natal", "url": "#contact"},
    }


@unittest.skipUnless(POSTGRES_AVAILABLE, "LANDING_TEST_DATABASE_URL and psycopg are required")
class LandingDraftRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = os.environ["LANDING_TEST_DATABASE_URL"]
        with psycopg.connect(cls.database_url, autocommit=True) as connection:
            if connection.execute("SELECT to_regclass('commander_entities')").fetchone()[0] is None:
                for path in sorted(Path("db/migrations").glob("*.sql")):
                    connection.execute(path.read_text())

    def setUp(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute("TRUNCATE commander_entities CASCADE")
        self.repository = LandingDraftRepository(self.database_url)
        self.builds = LandingBuildRepository(self.database_url)
        self.prepared = {
            "idea_run_id": RUN_ID, "recommended_template_id": "product", "brief": brief(),
        }

    def populated_set(self) -> dict:
        created, is_new = self.repository.create(
            self.prepared, request_id=REQUEST_ID, requested_by="firebase:owner", feedback_ids=[]
        )
        self.assertTrue(is_new)
        self.repository.mark_populating(created["id"])
        pages = {
            template_id: page_content_from_brief(template_id, brief()).to_dict()
            for template_id in ("product", "community", "waitlist")
        }
        return self.repository.complete_population(
            created["id"], pages=pages,
            previews={
                template_id: preview_document(template_id, brief(), pages[template_id])
                for template_id in pages
            },
            summary="Prepared all three variants.",
            invocation={"mode": "natal_landing_revision", "operation": "populate_set"},
        )

    def test_population_is_idempotent_and_survives_repository_restart(self) -> None:
        ready = self.populated_set()
        duplicate, is_new = self.repository.create(
            self.prepared, request_id=REQUEST_ID, requested_by="firebase:owner", feedback_ids=[]
        )
        restarted = LandingDraftRepository(self.database_url).get(ready["id"])
        self.assertFalse(is_new)
        self.assertEqual(ready["id"], duplicate["id"])
        self.assertEqual("ready", restarted["status"])
        self.assertEqual(["community", "product", "waitlist"], [item["template_id"] for item in restarted["variants"]])
        for variant in restarted["variants"]:
            self.assertEqual(7, len(variant["page_content"]["blocks"]))
        private = self.repository.snapshot(restarted["variants"][0]["id"], include_html=True)
        self.assertIn("data:image/", private["preview_html"])
        self.assertNotIn('src="assets/', private["preview_html"])

    def test_edit_memory_snapshot_lineage_and_retryable_failure(self) -> None:
        ready = self.populated_set()
        product = next(item for item in ready["variants"] if item["template_id"] == "product")
        original = product["page_content"]
        edit, created = self.repository.create_edit(
            product["id"], request_id=EDIT_ID, block_id="hero",
            instruction="Lead with a concrete outcome", requested_by="firebase:owner",
        )
        self.assertTrue(created)
        memory = self.builds.skill_memory(RUN_ID)
        self.assertEqual("hero", memory[0]["block_id"])
        self.assertEqual(product["id"], memory[0]["snapshot_id"])
        self.repository.mark_editing(EDIT_ID)
        changed = {**original, "blocks": {**original["blocks"]}}
        changed["blocks"]["hero"] = {
            **changed["blocks"]["hero"], "title": "A concrete visible outcome",
        }
        completed = self.repository.complete_edit(
            EDIT_ID, page_content=changed,
            preview_html=preview_document("product", brief(), changed),
            summary="Changed only hero.", lesson="Lead hero copy with a concrete outcome.",
            invocation={"mode": "natal_landing_revision", "operation": "edit_block:hero"},
        )
        current = self.repository.snapshot(completed["result_snapshot_id"])
        self.assertEqual(2, current["snapshot_number"])
        self.assertEqual(original["blocks"]["features"], current["page_content"]["blocks"]["features"])
        self.assertEqual("A concrete visible outcome", current["page_content"]["blocks"]["hero"]["title"])
        with self.assertRaisesRegex(ValueError, "stale"):
            self.repository.create_edit(
                product["id"], request_id="41234567-89ab-7def-8123-456789abcdef",
                block_id="problem", instruction="Shorter", requested_by="firebase:owner",
            )

        community = next(item for item in ready["variants"] if item["template_id"] == "community")
        failed_id = "51234567-89ab-7def-8123-456789abcdef"
        self.repository.create_edit(
            community["id"], request_id=failed_id, block_id="faq",
            instruction="Clarify the first answer", requested_by="firebase:owner",
        )
        self.repository.mark_editing(failed_id)
        failed = self.repository.fail_edit(failed_id, code="TimeoutError", message="agent timed out")
        self.assertEqual("failed", failed["status"])
        self.assertTrue(self.repository.snapshot(community["id"])["is_current"])
        self.assertEqual("queued", self.repository.retry_edit(failed_id)["status"])

        proposal = self.repository.proposal(edit["proposal_id"])
        self.assertEqual("pending_review", proposal["status"])
        planned = self.repository.mark_proposal_planning(
            proposal["id"], lesson="Lead hero copy with a concrete outcome.",
            command_session_id="bounded-plan-session",
        )
        self.assertEqual("planning", planned["status"])
        self.assertEqual("bounded-plan-session", planned["command_session_id"])

        with psycopg.connect(self.database_url) as connection:
            relations = connection.execute(
                """SELECT source.kind,relationship.relation,target.kind
                   FROM commander_relationships relationship
                   JOIN commander_entities source ON source.id=relationship.source_id
                   JOIN commander_entities target ON target.id=relationship.target_id
                   WHERE relationship.source_id IN (%s,%s,%s)
                   ORDER BY source.kind,relationship.relation,target.kind""",
                (edit["feedback_id"], completed["result_snapshot_id"], product["id"]),
            ).fetchall()
            weight_edge = connection.execute(
                """SELECT count(*) FROM commander_relationships relationship
                   JOIN commander_entities source ON source.id=relationship.source_id
                   WHERE source.kind='weight_update' AND relationship.relation='adjusts'"""
            ).fetchone()[0]
        self.assertIn(("human_feedback", "evaluates", "landing_draft"), [tuple(row) for row in relations])
        self.assertIn(("landing_draft", "supersedes", "landing_draft"), [tuple(row) for row in relations])
        self.assertIn(("landing_draft", "derived_from", "human_feedback"), [tuple(row) for row in relations])
        self.assertGreaterEqual(weight_edge, 2)

    def test_published_build_derives_from_exact_current_snapshot_and_source(self) -> None:
        ready = self.populated_set()
        snapshot = next(item for item in ready["variants"] if item["template_id"] == "waitlist")
        build_id = "61234567-89ab-7def-8123-456789abcdef"
        created, is_new = self.builds.create(
            {
                "build_id": build_id, "idea_run_id": RUN_ID, "template_id": "waitlist",
                "brief": brief(), "source_draft_snapshot_id": snapshot["id"],
                "page_content": snapshot["page_content"],
                "page_content_sha256": snapshot["page_content_sha256"],
                "revision_summary": snapshot["application_summary"],
                "revision_invocation": snapshot["invocation"],
            },
            request_id="71234567-89ab-7def-8123-456789abcdef",
            requested_by="firebase:owner", output_path=f"/tmp/landings/builds/{build_id}",
            firebase_site_id="natal-landings-test",
        )
        self.assertTrue(is_new)
        self.assertEqual(snapshot["id"], created["source_draft_snapshot_id"])
        self.assertEqual(snapshot["page_content"], created["page_content"])
        with psycopg.connect(self.database_url) as connection:
            targets = connection.execute(
                """SELECT target.kind FROM commander_relationships relationship
                   JOIN commander_entities target ON target.id=relationship.target_id
                   WHERE relationship.source_id=%s AND relationship.relation='derived_from'
                   ORDER BY target.kind""",
                (build_id,),
            ).fetchall()
        self.assertEqual(["source", "landing_draft"], [row[0] for row in targets])


if __name__ == "__main__":
    unittest.main()
