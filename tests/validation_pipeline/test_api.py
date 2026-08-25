from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest

HAS_FASTAPI_TEST = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None
if HAS_FASTAPI_TEST:
    from fastapi.testclient import TestClient
    from validation_pipeline.api import create_app
    from validation_pipeline.config import Settings


CREATIVE_ID = "018f07ea-7f20-7000-8000-000000000001"


class FakeRepository:
    def __init__(self): self.grouped = None; self.restored = None; self.rerun = None
    def recover_interrupted(self): return {"briefs": 0, "batches": 0}
    def connection(self): raise AssertionError("readiness DB is not used in this test")
    def image(self, _creative_id): return {"bytes": b"jpeg-fixture", "sha256": "a" * 64, "mime_type": "image/jpeg"}
    def list_briefs(self, _limit): return []
    def plan_proposals(self, domain, proposal_ids, *, command_session_id):
        self.grouped = (domain, proposal_ids, command_session_id)
        return {"command_session_id": command_session_id, "items": []}
    def restore_proposals(self, command_session_id):
        self.restored = command_session_id
        return {"matched": True, "command_session_id": command_session_id, "proposal_count": 2}
    def create_lesson_rerun(self, source_batch_id, **values):
        self.rerun = (source_batch_id, values)
        return ({"batch_id": CREATIVE_ID, "status": "queued"}, False)


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
        self.client = TestClient(create_app(settings, repository=self.repository, runner=FakeRunner()))
        self.headers = {"X-PTW-Owner-Gateway-Token": "gateway-token"}

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    def test_internal_api_requires_gateway_auth_and_legacy_routes_are_absent(self) -> None:
        self.assertEqual(401, self.client.get("/internal/v1/briefs").status_code)
        self.assertEqual(200, self.client.get("/internal/v1/briefs", headers=self.headers).status_code)
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


if __name__ == "__main__":
    unittest.main()
