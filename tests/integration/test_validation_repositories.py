from __future__ import annotations

from io import BytesIO
import hashlib
import importlib.util
import os
import unittest
from uuid import UUID, uuid4

HAS_PILLOW = importlib.util.find_spec("PIL") is not None
if HAS_PILLOW:
    from PIL import Image

from commander.ids import new_uuid7
from validation_pipeline.domain import CREATIVE_ANGLES, ProductBriefV1
from validation_pipeline.repository import ValidationRepository


DATABASE_URL = os.environ.get("PTW_VALIDATION_TEST_DATABASE_URL", "")


def document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "language": "en",
        "product": "Online psychologist consultations.",
        "target_audience": "First-time therapy seekers.",
        "main_pain": "Starting support feels risky.",
        "promise": "Take a trustworthy first step.",
        "key_benefits": ["Real profiles", "Easy booking", "Low-risk start"],
        "cta": "Get free consultation",
        "trust_strategy": "Real consultants, clear pricing, no card.",
        "offer": "First consultation free",
    }


def jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1080, 1080), "#6c7687").save(output, "JPEG")
    return output.getvalue()


def prepared_creatives() -> list[dict[str, object]]:
    artifact = jpeg()
    values = []
    for ordinal, angle in enumerate(CREATIVE_ANGLES):
        photo_id = f"{uuid4().int % 10**14}"
        values.append({
            "creative_id": new_uuid7(),
            "asset_id": new_uuid7(),
            "content": {
                "angle": angle,
                "hook": f"{angle} support",
                "primary_text": "First consultation free. Meet a real psychologist.",
                "image_description": "Real people in a professional conversation.",
                "cta": "Get free consultation",
                "offer": "First consultation free",
                "desired_emotion": "confidence",
                "image_category": "professional conversation",
                "image_search_query": f"real {angle} professional conversation",
                "crop_focus": "center",
            },
            "photo": {
                "provider": "pexels", "external_id": photo_id,
                "source_uri": f"https://www.pexels.com/photo/{photo_id}/",
                "photographer": f"Photographer {ordinal}",
                "photographer_url": "https://www.pexels.com/@fixture",
                "license": "Pexels License", "license_url": "https://www.pexels.com/license/",
                "attribution": f"Photo by Photographer {ordinal} on Pexels",
                "alt": "Real professional conversation",
            },
            "asset_bytes": artifact,
            "asset_digest": hashlib.sha256(artifact).hexdigest(),
        })
    return values


@unittest.skipUnless(
    DATABASE_URL and HAS_PILLOW,
    "PTW_VALIDATION_TEST_DATABASE_URL and Pillow are required",
)
class ValidationRepositoryIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = ValidationRepository(DATABASE_URL)

    def complete_brief(self) -> dict[str, object]:
        request_id = str(uuid4())
        brief, created = self.repository.create_brief(
            request_id=request_id,
            raw_idea="Online psychologist consultations",
            requested_by="integration-owner",
        )
        self.assertTrue(created)
        self.assertEqual(7, UUID(brief["brief_id"]).version)
        duplicate, duplicate_created = self.repository.create_brief(
            request_id=request_id,
            raw_idea="Online psychologist consultations",
            requested_by="integration-owner",
        )
        self.assertFalse(duplicate_created)
        self.assertEqual(brief["brief_id"], duplicate["brief_id"])
        with self.assertRaisesRegex(ValueError, "different Product Brief input"):
            self.repository.create_brief(
                request_id=request_id, raw_idea="Different idea", requested_by="integration-owner"
            )
        attempt_id, attempt_number = self.repository.start_attempt(
            brief["brief_id"], stage="product_brief"
        )
        self.assertEqual(1, attempt_number)
        value = ProductBriefV1.from_dict(document(), raw_idea="Online psychologist consultations")
        self.repository.finish_brief(
            brief["brief_id"], attempt_id, value.to_dict(), value.digest, value.quality_gates
        )
        return self.repository.get_brief(brief["brief_id"])

    def test_immutable_brief_approval_atomic_batch_assets_feedback_and_lineage(self) -> None:
        brief = self.complete_brief()
        self.assertEqual("completed", brief["status"])
        self.assertEqual("First consultation free", brief["offer"])
        with self.assertRaisesRegex(Exception, "immutable Product Brief"):
            with self.repository.connection() as connection:
                connection.execute(
                    "UPDATE product_briefs SET document='{}'::jsonb WHERE entity_id=%s",
                    (brief["brief_id"],),
                )

        batch, should_start = self.repository.approve_and_queue_batch(
            brief["brief_id"], "integration-owner"
        )
        self.assertTrue(should_start)
        self.assertEqual(7, UUID(batch["batch_id"]).version)
        same_queued_batch, duplicate_start = self.repository.approve_and_queue_batch(
            brief["brief_id"], "integration-owner"
        )
        self.assertFalse(duplicate_start)
        self.assertEqual(batch["batch_id"], same_queued_batch["batch_id"])
        attempt_id, _ = self.repository.start_attempt(batch["batch_id"], stage="ad_creative_batch")
        creatives = prepared_creatives()
        self.repository.finish_batch(
            batch["batch_id"], attempt_id, brief_id=brief["brief_id"],
            creatives=creatives, digest="b" * 64,
            quality={"passed": True, "five_real_assets": True},
        )
        self.repository.release_operation(batch["batch_id"])
        completed = self.repository.get_batch(batch["batch_id"])
        self.assertEqual("completed", completed["status"])
        self.assertEqual(list(CREATIVE_ANGLES), [item["angle"] for item in completed["creatives"]])
        self.assertEqual(5, len({item["creative_id"] for item in completed["creatives"]}))
        self.assertTrue(all(UUID(item["creative_id"]).version == 7 for item in completed["creatives"]))
        self.assertTrue(all(UUID(item["image"]["asset_id"]).version == 7 for item in completed["creatives"]))
        self.assertTrue(all(item["brief_id"] == brief["brief_id"] for item in completed["creatives"]))
        with self.assertRaisesRegex(ValueError, "promote feedback"):
            self.repository.create_lesson_rerun(
                batch["batch_id"], request_id=str(uuid4()),
                requested_by="integration-owner", skill_sha256="c" * 64,
            )

        first = completed["creatives"][0]
        stored = self.repository.image(first["creative_id"])
        self.assertEqual(hashlib.sha256(stored["bytes"]).hexdigest(), stored["sha256"])
        image = Image.open(BytesIO(stored["bytes"]))
        self.assertEqual((1080, 1080), image.size)
        self.assertEqual("JPEG", image.format)
        feedback = self.repository.record_creative_feedback(
            first["creative_id"], comment="Make the person feel more approachable.",
            requested_by="integration-owner",
        )
        second_feedback = self.repository.record_creative_feedback(
            first["creative_id"], comment="Keep the crop warm and candid.",
            requested_by="integration-owner",
        )
        self.assertIn("feedback_id", feedback)
        self.assertIn("weight_update_id", feedback)
        pending = self.repository.proposals("ad_creative", target_id=first["creative_id"])
        self.assertEqual([feedback["proposal_id"], second_feedback["proposal_id"]], [item["proposal_id"] for item in pending])
        with self.assertRaisesRegex(ValueError, "must exist and be pending"):
            self.repository.plan_proposals(
                "ad_creative", [feedback["proposal_id"], str(uuid4())],
                command_session_id=str(uuid4()),
            )
        self.assertTrue(all(
            item["status"] == "pending"
            for item in self.repository.proposals(
                "ad_creative", target_id=first["creative_id"]
            )
        ))
        command_session_id = str(uuid4())
        grouped = self.repository.plan_proposals(
            "ad_creative", [feedback["proposal_id"], second_feedback["proposal_id"]],
            command_session_id=command_session_id,
        )
        self.assertEqual(2, len(grouped["items"]))
        self.assertTrue(all(item["status"] == "planning" for item in grouped["items"]))
        with self.assertRaisesRegex(ValueError, "finish or dismiss"):
            self.repository.create_lesson_rerun(
                batch["batch_id"], request_id=str(uuid4()),
                requested_by="integration-owner", skill_sha256="c" * 64,
            )
        failed_group = self.repository.finish_proposal(command_session_id, status="failed")
        self.assertEqual(2, failed_group["proposal_count"])
        restored_group = self.repository.restore_proposals(command_session_id)
        self.assertEqual(2, restored_group["proposal_count"])
        self.assertTrue(all(item["status"] == "planning" for item in restored_group["items"]))
        promoted = self.repository.finish_proposal(command_session_id, status="promoted")
        self.assertEqual("promoted", promoted["status"])
        self.assertEqual(2, promoted["proposal_count"])
        self.assertTrue(all(item["status"] == "promoted" for item in promoted["items"]))
        with self.assertRaisesRegex(Exception, "append-only"):
            with self.repository.connection() as connection:
                connection.execute(
                    "UPDATE commander_human_feedback SET instruction='changed' WHERE entity_id=%s",
                    (feedback["feedback_id"],),
                )

        same_batch, restarted = self.repository.approve_and_queue_batch(
            brief["brief_id"], "integration-owner"
        )
        self.assertFalse(restarted)
        self.assertEqual(batch["batch_id"], same_batch["batch_id"])

        source_with_lesson = self.repository.get_batch(batch["batch_id"])
        self.assertEqual(2, source_with_lesson["lesson_status_counts"]["promoted"])
        rerun_request_id = str(uuid4())
        rerun, rerun_started = self.repository.create_lesson_rerun(
            batch["batch_id"], request_id=rerun_request_id,
            requested_by="integration-owner", skill_sha256="c" * 64,
        )
        self.assertTrue(rerun_started)
        self.assertNotEqual(batch["batch_id"], rerun["batch_id"])
        self.assertEqual(batch["batch_id"], rerun["rerun_of_batch_id"])
        self.assertEqual(brief["brief_id"], rerun["brief_id"])
        self.assertEqual("c" * 64, rerun["skill_sha256"])
        self.assertEqual(rerun["batch_id"], self.repository.get_batch(batch["batch_id"])["rerun_batch_id"])
        self.repository.release_operation(rerun["batch_id"])
        same_rerun, duplicate_rerun_start = self.repository.create_lesson_rerun(
            batch["batch_id"], request_id=rerun_request_id,
            requested_by="integration-owner", skill_sha256="c" * 64,
        )
        self.assertFalse(duplicate_rerun_start)
        self.assertEqual(rerun["batch_id"], same_rerun["batch_id"])
        with self.repository.connection() as connection:
            edges = connection.execute(
                """SELECT relation,count(*) FROM commander_relationships
                   WHERE relation IN ('derived_from','rerun_of','contains','evaluates','adjusts')
                   GROUP BY relation"""
            ).fetchall()
        edge_counts = dict(edges)
        self.assertGreaterEqual(edge_counts["derived_from"], 12)
        self.assertGreaterEqual(edge_counts["contains"], 10)
        self.assertGreaterEqual(edge_counts["evaluates"], 1)
        self.assertGreaterEqual(edge_counts["adjusts"], 1)
        self.assertEqual(1, edge_counts["rerun_of"])

    def test_correction_retry_recovery_atomic_failure_and_legacy_absence(self) -> None:
        base = self.complete_brief()
        batch, _ = self.repository.approve_and_queue_batch(base["brief_id"], "integration-owner")
        attempt_id, _ = self.repository.start_attempt(batch["batch_id"], stage="ad_creative_batch")
        invalid = prepared_creatives()
        invalid[4]["asset_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest"):
            self.repository.finish_batch(
                batch["batch_id"], attempt_id, brief_id=base["brief_id"], creatives=invalid,
                digest="b" * 64, quality={"passed": True},
            )
        with self.repository.connection() as connection:
            self.assertEqual(
                0,
                connection.execute(
                    "SELECT count(*) FROM ad_creatives WHERE batch_id=%s", (batch["batch_id"],)
                ).fetchone()[0],
            )
        self.repository.fail_attempt(
            batch["batch_id"], attempt_id, stage="ad_creative_batch",
            error=ValueError("fixture digest failure"),
        )
        failed_batch = self.repository.get_batch(batch["batch_id"])
        self.assertEqual(base["offer"], failed_batch["approved_offer"])
        self.assertIsNone(failed_batch["failure_notification"])
        self.repository.record_notification_callback_failure(
            batch["batch_id"], attempt_id, error=RuntimeError("fixture callback failure")
        )
        self.assertEqual(
            "failed",
            self.repository.get_batch(batch["batch_id"])["failure_notification"]["status"],
        )
        self.repository.release_operation(batch["batch_id"])
        self.repository.acquire_operation("ad_creative_batch", batch["batch_id"])
        self.repository.queue_retry(batch["batch_id"], stage="ad_creative_batch")
        retry_attempt, retry_number = self.repository.start_attempt(
            batch["batch_id"], stage="ad_creative_batch"
        )
        self.assertEqual(2, retry_number)
        self.repository.finish_batch(
            batch["batch_id"], retry_attempt, brief_id=base["brief_id"],
            creatives=prepared_creatives(), digest="c" * 64, quality={"passed": True},
        )
        self.repository.release_operation(batch["batch_id"])
        recovered_batch = self.repository.get_batch(batch["batch_id"])
        self.assertEqual("completed", recovered_batch["status"])
        self.assertEqual(attempt_id, recovered_batch["last_failed_attempt"]["attempt_id"])
        self.assertEqual("fixture digest failure", recovered_batch["last_failed_attempt"]["error_message"])
        replacement, created = self.repository.create_revision(
            base_brief_id=base["brief_id"], request_id=str(uuid4()),
            instruction="Narrow the first customer to first-time therapy seekers.",
            requested_by="integration-owner",
        )
        self.assertTrue(created)
        self.assertEqual(7, UUID(replacement["brief_id"]).version)
        self.assertEqual(base["brief_id"], replacement["base_brief_id"])
        attempt_id, _ = self.repository.start_attempt(replacement["brief_id"], stage="product_brief")
        self.repository.fail_attempt(
            replacement["brief_id"], attempt_id, stage="product_brief",
            error=RuntimeError("fixture failure"),
        )
        queued = self.repository.queue_retry(replacement["brief_id"], stage="product_brief")
        self.assertEqual("queued", queued["status"])
        self.repository.acquire_operation("product_brief", replacement["brief_id"])
        attempt_id, attempt_number = self.repository.start_attempt(
            replacement["brief_id"], stage="product_brief"
        )
        self.assertEqual(2, attempt_number)
        recovered = self.repository.recover_interrupted()
        self.assertEqual(1, recovered["briefs"])
        self.assertEqual("failed", self.repository.get_brief(replacement["brief_id"])["status"])

        with self.repository.connection() as connection:
            relations = {
                row[0] for row in connection.execute(
                    "SELECT relation FROM commander_relationships WHERE source_id=%s",
                    (replacement["brief_id"],),
                ).fetchall()
            }
            legacy = [
                connection.execute("SELECT to_regclass(%s)", (f"public.{name}",)).fetchone()[0]
                for name in (
                    "positioning_projects", "positioning_revisions", "landing_draft_sets",
                    "landing_builds", "landing_leads", "commander_ad_batches",
                )
            ]
        self.assertIn("supersedes", relations)
        self.assertIn("derived_from", relations)
        self.assertEqual([None] * len(legacy), legacy)


if __name__ == "__main__":
    unittest.main()
