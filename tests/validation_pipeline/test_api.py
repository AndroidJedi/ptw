from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest
from unittest.mock import patch

HAS_FASTAPI_TEST = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None
if HAS_FASTAPI_TEST:
    from fastapi.testclient import TestClient
    from validation_pipeline.api import _requests_generated_graphic, create_app
    from validation_pipeline.config import Settings


CREATIVE_ID = "018f07ea-7f20-7000-8000-000000000001"


class FakeRepository:
    def __init__(self):
        self.grouped = None; self.restored = None; self.rerun = None
        self.project_filter = None; self.batch_project_filter = None; self.renamed = None
        self.studio_calls = []
    def recover_interrupted(self): return {"briefs": 0, "batches": 0}
    def connection(self): raise AssertionError("readiness DB is not used in this test")
    def image(self, _creative_id): return {"bytes": b"jpeg-fixture", "sha256": "a" * 64, "mime_type": "image/jpeg"}
    def list_projects(self, _limit): return []
    def list_briefs(self, _limit, *, project_id=None): self.project_filter = project_id; return []
    def list_batches(self, _limit, *, brief_id=None, project_id=None):
        self.batch_project_filter = (brief_id, project_id); return []
    def rename_project(self, project_id, *, name, requested_by):
        self.renamed = (project_id, name, requested_by)
        return {"project_id": project_id, "name": name, "name_source": "owner"}
    def plan_proposals(self, domain, proposal_ids, *, command_session_id):
        self.grouped = (domain, proposal_ids, command_session_id)
        return {"command_session_id": command_session_id, "items": []}
    def restore_proposals(self, command_session_id):
        self.restored = command_session_id
        return {"matched": True, "command_session_id": command_session_id, "proposal_count": 2}
    def create_lesson_rerun(self, source_batch_id, **values):
        self.rerun = (source_batch_id, values)
        return ({"batch_id": CREATIVE_ID, "status": "queued"}, False)
    def acquire_operation(self, kind, operation_id):
        self.studio_calls.append(("acquire", operation_id, {"kind": kind})); return True
    def release_operation(self, operation_id):
        self.studio_calls.append(("release", operation_id, {}))
    def list_studio_brand_kits(self, project_id): return [{"brand_kit_id": CREATIVE_ID, "project_id": project_id}]
    def create_studio_brand_kit(self, project_id, **values):
        self.studio_calls.append(("brand_kit", project_id, values)); return {"brand_kit_id": CREATIVE_ID}
    def list_studio_templates(self, project_id): return [{"template_id": CREATIVE_ID, "project_id": project_id}]
    def create_studio_template(self, project_id, **values):
        self.studio_calls.append(("template", project_id, values)); return {"template_id": CREATIVE_ID}
    def studio_sample_template_media(self, _template_id): return None
    def apply_studio_template(self, template_id, **values):
        self.studio_calls.append(("apply_template", template_id, values))
        return {"template_id": template_id, "recipe": {"recipe_id": CREATIVE_ID}, "created": True}
    def list_studio_source_assets(self, project_id): return []
    def studio_source_asset(self, _source_asset_id):
        return {"bytes": b"source", "sha256": "c" * 64, "mime_type": "image/png"}
    def list_studio_sample_sets(self, project_id):
        return [{"sample_set_id": CREATIVE_ID, "project_id": project_id, "items": []}]
    def get_studio_sample_set_for_batch(self, _batch_id):
        return {"sample_set_id": CREATIVE_ID, "items": []}
    def get_studio_sample_set(self, sample_set_id):
        return {"sample_set_id": sample_set_id, "items": []}
    def studio_sample_set_download(self, _sample_set_id):
        return {"bytes": b"zip", "sha256": "d" * 64, "mime_type": "application/zip"}
    def list_studio_recipes(self, project_id): return [{"recipe_id": CREATIVE_ID, "project_id": project_id}]
    def get_studio_recipe(self, recipe_id): return {"recipe_id": recipe_id}
    def create_studio_recipe(self, project_id, **values):
        self.studio_calls.append(("recipe", project_id, values)); return {"recipe_id": CREATIVE_ID}
    def render_studio_recipe(self, recipe_id, _renderer):
        self.studio_calls.append(("render", recipe_id, {})); return {"render_id": recipe_id}
    def list_studio_renders(self, recipe_id): return [{"render_id": CREATIVE_ID, "recipe_id": recipe_id}]
    def create_studio_wizard_proposal(self, recipe_id, **values):
        self.studio_calls.append(("wizard", recipe_id, values)); return {
            "proposal_id": CREATIVE_ID, "recipe_id": recipe_id,
            "preview_sha256": "e" * 64, "preview_mime_type": "image/jpeg",
        }
    def list_studio_wizard_proposals(self, recipe_id):
        return [{"proposal_id": CREATIVE_ID, "recipe_id": recipe_id, "preview_sha256": "e" * 64}]
    def studio_wizard_preview(self, _proposal_id):
        return {"bytes": b"preview", "sha256": "e" * 64, "mime_type": "image/jpeg"}
    def apply_studio_wizard_proposal(self, proposal_id, **values):
        self.studio_calls.append(("apply_wizard", proposal_id, values))
        return {"proposal": {"proposal_id": proposal_id}, "recipe": {"recipe_id": CREATIVE_ID}, "render": {"render_id": CREATIVE_ID}}
    def studio_render_asset(self, _render_id): return {"bytes": b"studio", "sha256": "b" * 64, "mime_type": "video/mp4"}
    def get_studio_render(self, render_id): return {"render_id": render_id, "manifest": {"schema": "ptw.studio.manifest.v1"}}
    def publish_studio_render(self, render_id, **values):
        self.studio_calls.append(("publish", render_id, values)); return {"render_id": render_id, "published": True}
    def record_studio_feedback(self, render_id, **values):
        self.studio_calls.append(("feedback", render_id, values)); return {"feedback_id": CREATIVE_ID, "proposal_id": CREATIVE_ID}


class FakeRunner:
    def verify_ready(self): return {"ready": True}
    def ad_creative_skill_snapshot(self): return ("skill", "a" * 64)


@unittest.skipUnless(HAS_FASTAPI_TEST, "FastAPI TestClient is verified in the Validation image")
class ValidationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        root = Path(self.temp.name)
        settings = Settings(
            database_url="postgresql://unused",
            owner_gateway_token="gateway-token",
            bridge_url="https://bridge.example",
            bridge_token="bridge-token",
            pexels_api_key="pexels-key",
            product_brief_skill_path=root / "brief.md",
            ad_creative_skill_path=root / "creative.md",
        )
        self.repository = FakeRepository()
        self.client = TestClient(create_app(
            settings, repository=self.repository, runner=FakeRunner(),
            studio_recipe_provider=lambda document, **_values: ([], document, {"provider_provenance": {"fixture": True}}),
        ))
        self.headers = {"X-PTW-Owner-Gateway-Token": "gateway-token"}

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    def test_graphic_dispatch_requires_an_explicit_creation_verb_and_media_noun(self) -> None:
        self.assertFalse(_requests_generated_graphic("Make the background darker"))
        self.assertFalse(_requests_generated_graphic("Shorten the headline and improve contrast"))
        self.assertTrue(_requests_generated_graphic("Generate a new abstract graphic"))
        self.assertTrue(_requests_generated_graphic("Замініть фон на нову абстрактну ілюстрацію"))

    def test_internal_api_requires_gateway_auth_and_legacy_routes_are_absent(self) -> None:
        self.assertEqual(401, self.client.get("/internal/v1/projects").status_code)
        self.assertEqual(200, self.client.get("/internal/v1/projects", headers=self.headers).status_code)
        self.assertEqual(401, self.client.get("/internal/v1/briefs").status_code)
        self.assertEqual(200, self.client.get("/internal/v1/briefs", headers=self.headers).status_code)
        tools = self.client.get("/internal/v1/ad-studio/tools", headers=self.headers)
        self.assertEqual(200, tools.status_code)
        self.assertIn("studio.placement.tiktok.vertical_video.v1", {
            item["tool_id"] for item in tools.json()["items"]
        })
        for path in (
            "/internal/v1/positionings", "/internal/v1/ads", "/internal/v1/landings",
            "/internal/v1/catalog",
        ):
            with self.subTest(path=path):
                self.assertEqual(404, self.client.get(path, headers=self.headers).status_code)
        self.assertEqual(
            404,
            self.client.post(
                f"/internal/v1/briefs/{CREATIVE_ID}/revisions",
                headers=self.headers,
                json={"request_id": CREATIVE_ID, "instruction": "retired alias"},
            ).status_code,
        )

    def test_projects_are_filterable_and_owner_renames_are_actor_audited(self) -> None:
        response = self.client.get(
            f"/internal/v1/briefs?project_id={CREATIVE_ID}", headers=self.headers
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(CREATIVE_ID, self.repository.project_filter)
        batches = self.client.get(
            f"/internal/v1/ad-batches?project_id={CREATIVE_ID}", headers=self.headers
        )
        self.assertEqual(200, batches.status_code)
        self.assertEqual((None, CREATIVE_ID), self.repository.batch_project_filter)
        renamed = self.client.post(
            f"/internal/v1/projects/{CREATIVE_ID}/rename",
            headers={**self.headers, "X-PTW-Actor": "firebase:owner"},
            json={"name": "Focused project"},
        )
        self.assertEqual(200, renamed.status_code)
        self.assertEqual(
            (CREATIVE_ID, "Focused project", "firebase:owner"), self.repository.renamed
        )
        invalid = self.client.post(
            f"/internal/v1/projects/{CREATIVE_ID}/rename",
            headers=self.headers,
            json={"title": "wrong field"},
        )
        self.assertEqual(400, invalid.status_code)

    def test_image_stream_is_authenticated_and_has_authoritative_etag(self) -> None:
        response = self.client.get(
            f"/internal/v1/ad-creatives/{CREATIVE_ID}/image", headers=self.headers
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("image/jpeg", response.headers["content-type"])
        self.assertEqual(f'"{"a" * 64}"', response.headers["etag"])
        self.assertEqual(b"jpeg-fixture", response.content)
        self.assertIn("immutable", response.headers["cache-control"])
        cached = self.client.get(
            f"/internal/v1/ad-creatives/{CREATIVE_ID}/image",
            headers={**self.headers, "If-None-Match": response.headers["etag"]},
        )
        self.assertEqual(304, cached.status_code)
        self.assertEqual(b"", cached.content)

    def test_new_studio_contract_routes_are_authenticated_idempotent_and_etag_backed(self) -> None:
        actor_headers = {**self.headers, "X-PTW-Actor": "firebase:owner"}
        source_path = f"/internal/v1/ad-studio/sources/{CREATIVE_ID}/asset"
        self.assertEqual(401, self.client.get(source_path).status_code)
        source = self.client.get(source_path, headers=self.headers)
        self.assertEqual((200, "image/png", f'"{"c" * 64}"'), (
            source.status_code, source.headers["content-type"], source.headers["etag"],
        ))
        self.assertEqual(304, self.client.get(
            source_path, headers={**self.headers, "If-None-Match": source.headers["etag"]},
        ).status_code)

        applied = self.client.post(
            f"/internal/v1/ad-studio/templates/{CREATIVE_ID}/apply", headers=actor_headers,
            json={
                "request_id": CREATIVE_ID, "brief_id": CREATIVE_ID,
                "creative_id": None, "brand_kit_id": CREATIVE_ID,
            },
        )
        self.assertEqual(200, applied.status_code, applied.text)
        self.assertTrue(applied.json()["created"])

        self.assertEqual(200, self.client.get(
            f"/internal/v1/ad-studio/sample-sets?project_id={CREATIVE_ID}", headers=self.headers,
        ).status_code)
        built = self.client.post(
            "/internal/v1/ad-studio/sample-sets", headers=actor_headers,
            json={"batch_id": CREATIVE_ID},
        )
        self.assertEqual(CREATIVE_ID, built.json()["sample_set_id"])
        package = self.client.get(
            f"/internal/v1/ad-studio/sample-sets/{CREATIVE_ID}/download", headers=self.headers,
        )
        self.assertEqual((200, "application/zip", f'"{"d" * 64}"'), (
            package.status_code, package.headers["content-type"], package.headers["etag"],
        ))
        self.assertEqual(304, self.client.get(
            f"/internal/v1/ad-studio/sample-sets/{CREATIVE_ID}/download",
            headers={**self.headers, "If-None-Match": package.headers["etag"]},
        ).status_code)

        self.assertEqual(1, len(self.client.get(
            f"/internal/v1/ad-studio/recipes/{CREATIVE_ID}/renders", headers=self.headers,
        ).json()["items"]))
        proposal = self.client.post(
            f"/internal/v1/ad-studio/recipes/{CREATIVE_ID}/wizard-proposals", headers=actor_headers,
            json={"instruction": "Make the headline shorter", "target_instance_id": None},
        )
        self.assertEqual(201, proposal.status_code, proposal.text)
        recovered = self.client.get(
            f"/internal/v1/ad-studio/recipes/{CREATIVE_ID}/wizard-proposals", headers=self.headers,
        )
        self.assertEqual(CREATIVE_ID, recovered.json()["items"][0]["proposal_id"])
        preview = self.client.get(
            f"/internal/v1/ad-studio/wizard-proposals/{CREATIVE_ID}/preview", headers=self.headers,
        )
        self.assertEqual((200, "image/jpeg", f'"{"e" * 64}"'), (
            preview.status_code, preview.headers["content-type"], preview.headers["etag"],
        ))
        self.assertEqual(304, self.client.get(
            f"/internal/v1/ad-studio/wizard-proposals/{CREATIVE_ID}/preview",
            headers={**self.headers, "If-None-Match": preview.headers["etag"]},
        ).status_code)
        self.assertEqual(200, self.client.post(
            f"/internal/v1/ad-studio/wizard-proposals/{CREATIVE_ID}/apply",
            headers=actor_headers, json={},
        ).status_code)

    def test_grouped_lesson_plan_preserves_all_proposal_ids(self) -> None:
        proposal_ids = [
            "018f07ea-7f20-7000-8000-000000000011",
            "018f07ea-7f20-7000-8000-000000000012",
        ]
        command_session_id = "018f07ea-7f20-7000-8000-000000000013"
        response = self.client.post(
            "/internal/v1/skill-proposals/ad_creative/plan",
            headers=self.headers,
            json={"proposal_ids": proposal_ids, "command_session_id": command_session_id},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(("ad_creative", proposal_ids, command_session_id), self.repository.grouped)

        restored = self.client.post(
            f"/internal/v1/skill-proposals/by-command/{command_session_id}/restore",
            headers=self.headers,
            json={},
        )
        self.assertEqual(200, restored.status_code)
        self.assertEqual(command_session_id, self.repository.restored)

    def test_lesson_rerun_records_the_current_skill_snapshot(self) -> None:
        request_id = "018f07ea-7f20-7000-8000-000000000021"
        response = self.client.post(
            f"/internal/v1/ad-batches/{CREATIVE_ID}/rerun",
            headers={**self.headers, "X-PTW-Actor": "firebase:owner"},
            json={"request_id": request_id},
        )
        self.assertEqual(202, response.status_code)
        self.assertFalse(response.json()["generation_started"])
        self.assertEqual(
            (CREATIVE_ID, {
                "request_id": request_id,
                "requested_by": "firebase:owner",
                "skill_sha256": "a" * 64,
            }),
            self.repository.rerun,
        )

    def test_studio_owner_contract_routes_template_render_manifest_publish_and_feedback(self) -> None:
        actor_headers = {**self.headers, "X-PTW-Actor": "firebase:owner"}
        self.assertEqual(200, self.client.get(
            f"/internal/v1/ad-studio/brand-kits?project_id={CREATIVE_ID}", headers=self.headers
        ).status_code)
        self.assertEqual(200, self.client.get(
            f"/internal/v1/ad-studio/templates?project_id={CREATIVE_ID}", headers=self.headers
        ).status_code)
        template = self.client.post(
            "/internal/v1/ad-studio/templates", headers=actor_headers,
            json={"project_id": CREATIVE_ID, "name": "Reusable", "document": {"schema_version": 1}},
        )
        self.assertEqual(201, template.status_code)
        recipe = self.client.post(
            "/internal/v1/ad-studio/recipes", headers=actor_headers,
            json={"project_id": CREATIVE_ID, "brief_id": CREATIVE_ID, "brand_kit_id": CREATIVE_ID, "document": {"schema_version": 1}},
        )
        self.assertEqual(201, recipe.status_code)
        self.assertEqual(201, self.client.post(
            f"/internal/v1/ad-studio/recipes/{CREATIVE_ID}/render", headers=self.headers, json={}
        ).status_code)
        artifact = self.client.get(
            f"/internal/v1/ad-studio/renders/{CREATIVE_ID}/asset", headers=self.headers
        )
        self.assertEqual((200, "video/mp4", f'"{"b" * 64}"'), (
            artifact.status_code, artifact.headers["content-type"], artifact.headers["etag"],
        ))
        manifest = self.client.get(
            f"/internal/v1/ad-studio/renders/{CREATIVE_ID}/manifest", headers=self.headers
        )
        self.assertEqual("ptw.studio.manifest.v1", manifest.json()["schema"])
        self.assertTrue(self.client.post(
            f"/internal/v1/ad-studio/renders/{CREATIVE_ID}/publish", headers=actor_headers, json={}
        ).json()["published"])
        feedback = self.client.post(
            f"/internal/v1/ad-studio/renders/{CREATIVE_ID}/feedback", headers=actor_headers,
            json={"comment": "Keep the CTA clearer."},
        )
        self.assertEqual(200, feedback.status_code)
        self.assertIn(("feedback", CREATIVE_ID, {"comment": "Keep the CTA clearer.", "requested_by": "firebase:owner"}), self.repository.studio_calls)

    def test_studio_upload_size_is_rejected_before_decode_or_persistence(self) -> None:
        with patch("validation_pipeline.api.MAX_VIDEO_BYTES", 2):
            response = self.client.post(
                "/internal/v1/ad-studio/sources/upload", headers=self.headers,
                json={"project_id": CREATIVE_ID, "title": "oversized", "mime_type": "video/mp4", "base64": "xxxxx"},
            )
        self.assertEqual(400, response.status_code)
        self.assertIn("bounded size", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
