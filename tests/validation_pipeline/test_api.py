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
    def recover_interrupted(self): return {"briefs": 0, "batches": 0}
    def connection(self): raise AssertionError("readiness DB is not used in this test")
    def image(self, _creative_id): return {"bytes": b"jpeg-fixture", "sha256": "a" * 64, "mime_type": "image/jpeg"}
    def list_briefs(self, _limit): return []


class FakeRunner:
    def verify_ready(self): return {"ready": True}


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
        self.client = TestClient(create_app(settings, repository=FakeRepository(), runner=FakeRunner()))
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


if __name__ == "__main__":
    unittest.main()
