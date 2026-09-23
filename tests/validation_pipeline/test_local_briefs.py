from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.local_briefs import LocalBriefService


BRIEF = {
    "schema_version": 1,
    "language": "en",
    "product": "Focus planner",
    "target_audience": "Independent professionals managing many priorities",
    "main_pain": "Daily priorities get lost across disconnected tools",
    "promise": "Turn scattered work into one calm daily plan",
    "key_benefits": [
        "See today's priorities in one place",
        "Reduce time spent reorganizing tasks",
        "Finish important work with less distraction",
    ],
    "cta": "Request early access",
    "trust_strategy": "Show the workflow without unsupported claims",
    "offer": "Free early access for the first validation group",
}


class FakeProvider:
    def call(self, **kwargs):
        response = kwargs["response_validator"](BRIEF)
        return {
            "response": response,
            "invocation": {"provider": "test", "mode": kwargs["mode"]},
        }


class LocalBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = LocalBriefStore(Path(self.temporary.name))
        self.service = LocalBriefService(
            store=self.store,
            provider=FakeProvider(),
            repository_root=Path(__file__).resolve().parents[2],
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_project_and_brief(self):
        project, project_created = self.service.create_project(
            request_id=str(uuid4()), name="Focus Planner", requested_by="test-owner",
        )
        project, brief, brief_created = self.service.create_brief(
            project_id=project["project_id"], request_id=str(uuid4()),
            raw_idea="A calmer focus planner", required_language="en",
            requested_by="test-owner",
        )
        return project, brief, project_created, brief_created

    def test_empty_project_is_persisted_before_its_first_brief(self) -> None:
        request_id = str(uuid4())
        project, created = self.service.create_project(
            request_id=request_id, name="Owner Chosen Name", requested_by="test-owner",
        )
        repeated, repeated_created = self.service.create_project(
            request_id=request_id, name="Owner Chosen Name", requested_by="test-owner",
        )

        self.assertTrue(created)
        self.assertFalse(repeated_created)
        self.assertEqual(project["project_id"], repeated["project_id"])
        self.assertEqual("Owner Chosen Name", project["name"])
        self.assertIsNone(project["owner_idea_source_id"])
        self.assertEqual(0, project["brief_count"])

    def test_create_generate_and_approve_are_brief_only(self) -> None:
        project, queued, project_created, created = self.create_project_and_brief()
        self.assertTrue(project_created)
        self.assertTrue(created)
        completed = self.service.generate_brief(queued["brief_id"])
        approved, approved_now = self.service.approve_brief(
            completed["brief_id"], "test-owner",
        )

        self.assertEqual(completed["status"], "completed")
        self.assertTrue(approved_now)
        self.assertTrue(approved["approved"])
        self.assertEqual(self.service.list_projects()[0]["brief_count"], 1)
        self.assertEqual("Focus Planner", self.service.list_projects()[0]["name"])
        self.assertNotIn("result_run_count", project)
        self.assertFalse((Path(self.temporary.name) / "artifacts").exists())

    def test_first_brief_is_idempotent_and_a_second_root_is_rejected(self) -> None:
        project, _ = self.service.create_project(
            request_id=str(uuid4()), name="Stable Name", requested_by="test-owner",
        )
        request_id = str(uuid4())
        first_project, first, created = self.service.create_brief(
            project_id=project["project_id"], request_id=request_id,
            raw_idea="First idea", required_language="en", requested_by="test-owner",
        )
        repeated_project, repeated, repeated_created = self.service.create_brief(
            project_id=project["project_id"], request_id=request_id,
            raw_idea="First idea", required_language="en", requested_by="test-owner",
        )

        self.assertTrue(created)
        self.assertFalse(repeated_created)
        self.assertEqual(first["brief_id"], repeated["brief_id"])
        self.assertEqual("Stable Name", first_project["name"])
        self.assertEqual("Stable Name", repeated_project["name"])
        with self.assertRaisesRegex(ValueError, "already has its first"):
            self.service.create_brief(
                project_id=project["project_id"], request_id=str(uuid4()),
                raw_idea="Second idea", required_language="en", requested_by="test-owner",
            )

    def test_project_deletion_requires_name_and_is_idempotently_hidden(self) -> None:
        project, _ = self.service.create_project(
            request_id=str(uuid4()), name="Project to remove", requested_by="test-owner",
        )
        request_id = str(uuid4())
        with self.assertRaisesRegex(ValueError, "name confirmation"):
            self.service.delete_project(
                project["project_id"], request_id=request_id,
                confirmation_name="wrong", requested_by="test-owner",
            )

        deleted = self.service.delete_project(
            project["project_id"], request_id=request_id,
            confirmation_name=project["name"], requested_by="test-owner",
        )
        repeated = self.service.delete_project(
            project["project_id"], request_id=request_id,
            confirmation_name=project["name"], requested_by="test-owner",
        )

        self.assertTrue(deleted["deleted"])
        self.assertEqual(deleted, repeated)
        self.assertEqual([], self.service.list_projects())
        with self.assertRaises(KeyError):
            self.store.get("projects", project["project_id"])
        retained = self.store.get(
            "projects", project["project_id"], include_deleted=True,
        )
        self.assertEqual(request_id, retained["delete_request_id"])
        self.assertEqual("test-owner", retained["deleted_by"])
        with self.assertRaisesRegex(ValueError, "request_id belongs to a deleted Project"):
            self.service.create_project(
                request_id=project["request_id"], name=project["name"],
                requested_by="test-owner",
            )
        with self.assertRaises(KeyError):
            self.service.delete_project(
                project["project_id"], request_id=str(uuid4()),
                confirmation_name=project["name"], requested_by="test-owner",
            )

    def test_project_deletion_refuses_active_generation(self) -> None:
        project, _brief, _, _ = self.create_project_and_brief()
        with self.assertRaisesRegex(RuntimeError, "Product Brief"):
            self.service.delete_project(
                project["project_id"], request_id=str(uuid4()),
                confirmation_name=project["name"], requested_by="test-owner",
            )
        self.assertEqual(project["project_id"], self.service.list_projects()[0]["project_id"])

    def test_project_deletion_refuses_active_validation_and_learning(self) -> None:
        instagram_project, _ = self.service.create_project(
            request_id=str(uuid4()), name="Active Instagram test", requested_by="test-owner",
        )
        test_id = str(uuid4())
        self.store.append("instagram_validation_tests", test_id, {
            "test_id": test_id, "project_id": instagram_project["project_id"],
        })
        event_id = str(uuid4())
        self.store.append("instagram_validation_test_events", event_id, {
            "event_id": event_id, "test_id": test_id, "action": "activated",
        })
        with self.assertRaisesRegex(RuntimeError, "Instagram test"):
            self.service.delete_project(
                instagram_project["project_id"], request_id=str(uuid4()),
                confirmation_name=instagram_project["name"], requested_by="test-owner",
            )

        analytics_project, _ = self.service.create_project(
            request_id=str(uuid4()), name="Active Analytics learning", requested_by="test-owner",
        )
        run_id = str(uuid4())
        self.store.append("creative_learning_runs", run_id, {
            "learning_run_id": run_id, "project_id": analytics_project["project_id"],
            "status": "running",
        })
        with self.assertRaisesRegex(RuntimeError, "Analytics learning"):
            self.service.delete_project(
                analytics_project["project_id"], request_id=str(uuid4()),
                confirmation_name=analytics_project["name"], requested_by="test-owner",
            )

    def test_restart_requeues_only_interrupted_briefs(self) -> None:
        _, brief, _, _ = self.create_project_and_brief()
        self.store.append("briefs", brief["brief_id"], {
            **brief, "status": "generating",
        })

        self.assertEqual(self.service.recover_interrupted(), [brief["brief_id"]])
        self.assertEqual(self.store.get("briefs", brief["brief_id"])["status"], "queued")

    def test_successful_generation_clears_stale_current_failure(self) -> None:
        _, brief, _, _ = self.create_project_and_brief()
        self.store.append("briefs", brief["brief_id"], {
            **brief, "status": "failed", "failure_count": 1,
            "error_code": "ValueError", "error_message": "stale failure",
        })

        completed = self.service.generate_brief(brief["brief_id"])

        self.assertEqual(completed["status"], "completed")
        self.assertIsNone(completed["error_code"])
        self.assertIsNone(completed["error_message"])

    def test_correction_records_feedback_weight_and_complete_lineage(self) -> None:
        project, queued, _, _ = self.create_project_and_brief()
        completed = self.service.generate_brief(queued["brief_id"])
        replacement, created = self.service.correct_brief(
            completed["brief_id"], request_id=str(uuid4()),
            instruction="Make the audience more specific.", requested_by="test-owner",
        )

        self.assertTrue(created)
        feedback = self.store.get("feedback", replacement["feedback_id"])
        weight = self.store.get("weight_updates", feedback["weight_update_id"])
        self.assertEqual(weight["component"], "product_brief")
        self.assertEqual(weight["feedback_id"], feedback["feedback_id"])
        relations = {
            (edge["source_id"], edge["relation"], edge["target_id"])
            for edge in self.store.list("edges")
        }
        self.assertIn(
            (project["project_id"], "contains", replacement["brief_id"]), relations,
        )
        self.assertIn(
            (feedback["feedback_id"], "contains", weight["weight_update_id"]), relations,
        )
        self.assertIn(
            (weight["weight_update_id"], "adjusts", feedback["feedback_id"]), relations,
        )


if __name__ == "__main__":
    unittest.main()
