from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from threading import Barrier
import unittest
from uuid import UUID, uuid4

HAS_PILLOW = importlib.util.find_spec("PIL") is not None
if HAS_PILLOW:
    from PIL import Image

from commander.ids import new_uuid7
from validation_pipeline.domain import CREATIVE_ANGLES, ProductBriefV1
from validation_pipeline.repository import ValidationRepository
from validation_pipeline.studio import (
    ADS_SOURCE, COLOR_SOURCE, DEFAULT_GUARDS, SAMPLE_ANGLES, StudioRenderer, _v2_submission,
)


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
        self.assertEqual(7, UUID(brief["project_id"]).version)
        project = self.repository.get_project(brief["project_id"])
        self.assertEqual("Online psychologist consultations", project["name"])
        self.assertEqual("raw_idea", project["name_source"])
        duplicate, duplicate_created = self.repository.create_brief(
            request_id=request_id,
            raw_idea="Online psychologist consultations",
            requested_by="integration-owner",
        )
        self.assertFalse(duplicate_created)
        self.assertEqual(brief["brief_id"], duplicate["brief_id"])
        self.assertEqual(brief["project_id"], duplicate["project_id"])
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
        named_project = self.repository.get_project(brief["project_id"])
        self.assertEqual("Online psychologist consultations.", named_project["name"])
        self.assertEqual("product_brief", named_project["name_source"])
        return self.repository.get_brief(brief["brief_id"])

    def test_project_membership_filters_rename_and_generated_name_protection(self) -> None:
        base = self.complete_brief()
        project_id = base["project_id"]
        with self.assertRaisesRegex(Exception, "product_briefs_one_root_per_project_key"):
            with self.repository.connection() as connection:
                second_root_id = new_uuid7()
                connection.execute(
                    "INSERT INTO commander_entities(id,kind) VALUES(%s,'product_brief')",
                    (second_root_id,),
                )
                connection.execute(
                    """INSERT INTO product_briefs(
                           entity_id,project_id,request_id,owner_idea_source_id,status,requested_by
                       ) VALUES(%s,%s,%s,%s,'queued','integration-owner')""",
                    (second_root_id, project_id, str(uuid4()), base["owner_idea_source_id"]),
                )
        renamed = self.repository.rename_project(
            project_id, name="  Owner   validation workspace  ", requested_by="integration-owner"
        )
        self.assertEqual("Owner validation workspace", renamed["name"])
        self.assertEqual("owner", renamed["name_source"])
        with self.assertRaisesRegex(ValueError, "1-120"):
            self.repository.rename_project(
                project_id, name="x" * 121, requested_by="integration-owner"
            )

        replacement, created = self.repository.create_revision(
            base_brief_id=base["brief_id"], request_id=str(uuid4()),
            instruction="Use a narrower first customer.", requested_by="integration-owner",
        )
        self.assertTrue(created)
        self.assertEqual(project_id, replacement["project_id"])
        attempt_id, _ = self.repository.start_attempt(
            replacement["brief_id"], stage="product_brief"
        )
        replacement_document = {**document(), "product": "A generated replacement name."}
        value = ProductBriefV1.from_dict(
            replacement_document, raw_idea="Online psychologist consultations"
        )
        self.repository.finish_brief(
            replacement["brief_id"], attempt_id, value.to_dict(), value.digest, value.quality_gates
        )
        self.assertEqual("Owner validation workspace", self.repository.get_project(project_id)["name"])
        self.assertEqual(
            [replacement["brief_id"], base["brief_id"]],
            [item["brief_id"] for item in self.repository.list_briefs(project_id=project_id)],
        )

        other = self.complete_brief()
        self.assertNotEqual(project_id, other["project_id"])
        self.assertEqual(
            [other["brief_id"]],
            [item["brief_id"] for item in self.repository.list_briefs(project_id=other["project_id"])],
        )
        with self.repository.connection() as connection:
            audit = connection.execute(
                """SELECT actor,details->>'previous_name',details->>'name'
                     FROM commander_audit_events
                    WHERE target_id=%s AND action='validation_project_renamed'""",
                (project_id,),
            ).fetchone()
            containment = connection.execute(
                """SELECT count(*) FROM commander_relationships
                    WHERE source_id=%s AND relation='contains'""",
                (project_id,),
            ).fetchone()[0]
        self.assertEqual(
            ("integration-owner", "Online psychologist consultations.", "Owner validation workspace"),
            tuple(audit),
        )
        self.assertEqual(2, containment)

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
        self.assertEqual(brief["project_id"], completed["project_id"])
        self.assertEqual(
            [batch["batch_id"]],
            [item["batch_id"] for item in self.repository.list_batches(project_id=brief["project_id"])],
        )
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
        self.assertEqual(brief["project_id"], rerun["project_id"])
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

    def test_ad_studio_templates_revisions_manifest_publication_and_feedback(self) -> None:
        brief = self.complete_brief()
        batch, _ = self.repository.approve_and_queue_batch(brief["brief_id"], "integration-owner")
        self.repository.release_operation(batch["batch_id"])

        source_bytes = BytesIO()
        Image.new("RGB", (320, 240), "#4a6278").save(source_bytes, "PNG")
        source = self.repository.create_studio_source_asset(
            brief["project_id"], title="Owner product photo", data=source_bytes.getvalue(),
            mime_type="image/png", origin="owner_upload", provider="owner",
            external_id=None, source_uri=None, license_name="Owner supplied",
            attribution="Owner-supplied media", metadata={"fixture": True},
            requested_by="integration-owner",
        )
        kit = self.repository.create_studio_brand_kit(
            brief["project_id"], parent_brand_kit_id=None, requested_by="integration-owner",
            document={
                "name": "Project brand", "colors": ["#101010", "#FFFFFF", "#4466AA", "#F0C040"],
                "fonts": ["Inter"], "tone_notes": "Calm and direct", "logo_source_asset_id": None,
            },
        )

        def tools(offer: str, cta: str) -> list[dict[str, object]]:
            return [
                {
                    "instance_id": new_uuid7(), "tool_id": "studio.frame.media.v1",
                    "frame": {"x": 0, "y": 0, "width": 1, "height": .62}, "z_index": 0,
                    "params": {}, "timeline": None, "source_asset_ids": [source["source_asset_id"]],
                },
                {
                    "instance_id": new_uuid7(), "tool_id": "studio.frame.offer.v1",
                    "frame": {"x": .08, "y": .68, "width": .84, "height": .1}, "z_index": 1,
                    "params": {"text": offer, "color": "#FFFFFF"}, "timeline": None,
                    "source_asset_ids": [],
                },
                {
                    "instance_id": new_uuid7(), "tool_id": "studio.frame.cta.v1",
                    "frame": {"x": .08, "y": .82, "width": .5, "height": .1}, "z_index": 2,
                    "params": {"text": cta, "color": "#FFFFFF"}, "timeline": None,
                    "source_asset_ids": [],
                },
            ]

        template = self.repository.create_studio_template(
            brief["project_id"], name="Reusable square", requested_by="integration-owner",
            document={
                "schema_version": 1,
                "placement_tool_id": "studio.placement.instagram.feed_square.v1",
                "duration_seconds": None, "frame_rate": None,
                "tools": tools("{{offer}}", "{{cta}}"),
                "strategy_ids": ["studio.strategy.one_message.v1"],
            },
        )
        self.assertEqual("{{offer}}", template["document"]["tools"][1]["params"]["text"])
        self.assertEqual(7, UUID(template["template_id"]).version)

        recipe_document = {
            "schema_version": 1, "parent_recipe_id": None,
            "placement_tool_id": "studio.placement.instagram.feed_square.v1",
            "duration_seconds": None, "frame_rate": None,
            "tools": tools(brief["offer"], brief["cta"]),
            "strategy_ids": ["studio.strategy.one_message.v1"],
            "validation_ids": list(DEFAULT_GUARDS),
            "source_reference_ids": [COLOR_SOURCE, ADS_SOURCE],
        }
        recipe = self.repository.create_studio_recipe(
            brief["project_id"], brief_id=brief["brief_id"], brand_kit_id=kit["brand_kit_id"],
            document=recipe_document, requested_by="integration-owner",
        )
        render = self.repository.render_studio_recipe(
            recipe["recipe_id"], StudioRenderer(font_path=Path("/missing/inter.ttf")),
        )
        stored = self.repository.studio_render_asset(render["render_id"])
        self.assertEqual(render["bytes_sha256"], hashlib.sha256(stored["bytes"]).hexdigest())
        self.assertEqual(render["bytes_sha256"], render["manifest"]["output"]["bytes_sha256"])
        embedded = json.loads(Image.open(BytesIO(stored["bytes"])).getexif()[0x9286])
        self.assertEqual(recipe["document_sha256"], embedded["recipe_sha256"])
        self.assertIn("studio.frame.offer.v1", embedded["tool_ids"])

        published = self.repository.publish_studio_render(
            render["render_id"], requested_by="integration-owner"
        )
        self.assertTrue(published["published"])
        feedback = self.repository.record_studio_feedback(
            render["render_id"], comment="Keep stronger contrast around the CTA.",
            requested_by="integration-owner",
        )
        self.assertEqual(
            feedback["proposal_id"], self.repository.proposals("ad_studio")[0]["proposal_id"]
        )
        with self.assertRaisesRegex(Exception, "append-only"):
            with self.repository.connection() as connection:
                connection.execute(
                    "UPDATE ad_studio_templates SET name='Changed' WHERE entity_id=%s",
                    (template["template_id"],),
                )
        with self.repository.connection() as connection:
            edges = {
                (row[0], row[1]) for row in connection.execute(
                    "SELECT relation,target_id FROM commander_relationships WHERE source_id=%s",
                    (recipe["recipe_id"],),
                ).fetchall()
            }
        self.assertIn(("derived_from", UUID(source["source_asset_id"])), edges)
        self.assertIn(("contains", UUID(render["render_id"])), edges)

    def test_five_sample_set_template_apply_and_wizard_are_atomic_and_idempotent(self) -> None:
        brief = self.complete_brief()
        batch, _ = self.repository.approve_and_queue_batch(brief["brief_id"], "integration-owner")
        attempt_id, _ = self.repository.start_attempt(batch["batch_id"], stage="ad_creative_batch")
        prepared = prepared_creatives()
        self.repository.finish_batch(
            batch["batch_id"], attempt_id, brief_id=brief["brief_id"], creatives=prepared,
            digest="e" * 64, quality={"passed": True},
        )
        self.repository.release_operation(batch["batch_id"])

        def source(title: str, color: str, *, origin: str = "owner_upload") -> dict[str, object]:
            output = BytesIO(); Image.new("RGB", (1254, 1254), color).save(output, "PNG")
            return self.repository.create_studio_source_asset(
                brief["project_id"], title=title, data=output.getvalue(), mime_type="image/png",
                origin=origin, provider="integration", external_id=title, source_uri=None,
                license_name="Integration fixture", attribution="Integration fixture",
                metadata={"no_synthetic_people": origin == "ai_generated"}, requested_by="integration-owner",
            )

        logo = source("canonical-logo", "#f4f6fa", origin="canonical_brand")
        kit = self.repository.create_studio_brand_kit(
            brief["project_id"], parent_brand_kit_id=None, requested_by="integration-owner",
            document={
                "name": "Natal", "colors": ["#0C0E12", "#181C25", "#F4F6FA", "#A3ADBD", "#43BDD3", "#87D0DD"],
                "fonts": ["Inter"], "tone_notes": "Direct and calm",
                "logo_source_asset_id": logo["source_asset_id"],
            },
        )
        media = {
            angle: source(f"sample-{angle}", f"#{index + 2:02x}6677")["source_asset_id"]
            for index, angle in enumerate(SAMPLE_ANGLES)
        }
        renderer = StudioRenderer(font_path=Path("/missing/inter.ttf"))
        sample = self.repository.create_studio_sample_set(
            batch["batch_id"], brand_kit_id=kit["brand_kit_id"],
            media_by_angle=media, renderer=renderer, requested_by="integration-owner",
        )
        self.assertEqual(5, len(sample["items"]))
        self.assertEqual(
            [item["creative_id"] for item in self.repository.get_batch(batch["batch_id"])["creatives"]],
            [item["source_creative_id"] for item in sample["items"]],
        )
        self.assertEqual(sample["sample_set_id"], self.repository.create_studio_sample_set(
            batch["batch_id"], brand_kit_id=kit["brand_kit_id"],
            media_by_angle=media, renderer=renderer, requested_by="integration-owner",
        )["sample_set_id"])
        package = self.repository.studio_sample_set_download(sample["sample_set_id"])
        self.assertEqual(package["sha256"], hashlib.sha256(package["bytes"]).hexdigest())

        selected = sample["items"][2]
        application_id = str(uuid4())
        applied_template = self.repository.apply_studio_template(
            selected["template_id"], brief_id=brief["brief_id"],
            creative_id=selected["source_creative_id"], brand_kit_id=kit["brand_kit_id"],
            photo_source_asset_id=media["curiosity"], request_id=application_id,
            requested_by="integration-owner",
        )
        self.assertTrue(applied_template["created"])
        same_application = self.repository.apply_studio_template(
            selected["template_id"], brief_id=brief["brief_id"],
            creative_id=selected["source_creative_id"], brand_kit_id=kit["brand_kit_id"],
            photo_source_asset_id=media["curiosity"], request_id=application_id,
            requested_by="integration-owner",
        )
        self.assertFalse(same_application["created"])
        self.assertEqual(applied_template["recipe"]["recipe_id"], same_application["recipe"]["recipe_id"])

        concurrent_request_id = str(uuid4())
        start = Barrier(2)
        def concurrent_apply():
            start.wait()
            return self.repository.apply_studio_template(
                selected["template_id"], brief_id=brief["brief_id"],
                creative_id=selected["source_creative_id"], brand_kit_id=kit["brand_kit_id"],
                photo_source_asset_id=media["curiosity"], request_id=concurrent_request_id,
                requested_by="integration-owner",
            )
        with ThreadPoolExecutor(max_workers=2) as executor:
            concurrent = [future.result() for future in (
                executor.submit(concurrent_apply), executor.submit(concurrent_apply),
            )]
        self.assertEqual({True, False}, {item["created"] for item in concurrent})
        self.assertEqual(1, len({item["recipe"]["recipe_id"] for item in concurrent}))

        other_brief = self.complete_brief()
        with self.assertRaisesRegex(ValueError, "same Project"):
            self.repository.apply_studio_template(
                selected["template_id"], brief_id=other_brief["brief_id"],
                creative_id=None, brand_kit_id=kit["brand_kit_id"],
                photo_source_asset_id=None, request_id=str(uuid4()),
                requested_by="integration-owner",
            )

        generated = source("wizard-generated", "#43bdd3", origin="ai_generated")
        root_recipe = selected["recipe"]
        media_frame = next(
            item for item in root_recipe["document"]["frames"]
            if item["tool_id"] == "studio.frame.media.v1"
        )
        def builder(document, **_values):
            proposed = _v2_submission(document)
            proposed = json.loads(json.dumps(proposed))
            next(item for item in proposed["frames"] if item["instance_id"] == media_frame["instance_id"])["source_asset_ids"] = [generated["source_asset_id"]]
            return [], proposed, {
                "generated_source_asset_id": generated["source_asset_id"],
                "provider_provenance": {"mode": "ad_studio_graphic_generation", "request_id": "fixture"},
            }
        proposal = self.repository.create_studio_wizard_proposal(
            root_recipe["recipe_id"], instruction="Replace the background with a generated graphic",
            target_instance_id=media_frame["instance_id"], proposal_builder=builder,
            renderer=renderer, requested_by="integration-owner",
        )
        self.assertEqual(generated["source_asset_id"], proposal["generated_source_asset_id"])
        first_apply = self.repository.apply_studio_wizard_proposal(
            proposal["proposal_id"], renderer=renderer, requested_by="integration-owner",
        )
        second_apply = self.repository.apply_studio_wizard_proposal(
            proposal["proposal_id"], renderer=renderer, requested_by="integration-owner",
        )
        self.assertEqual(first_apply["recipe"]["recipe_id"], second_apply["recipe"]["recipe_id"])
        with self.repository.connection() as connection:
            self.assertEqual(1, connection.execute(
                """SELECT count(*) FROM commander_relationships
                     WHERE source_id=%s AND relation='derived_from' AND target_id=%s""",
                (proposal["proposal_id"], generated["source_asset_id"]),
            ).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
