from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from owner_gateway.firebase_hosting import FirebaseHostingError, public_files
from owner_gateway.landing_pipeline import LandingBuildCoordinator


RUN_ID = "01234567-89ab-7def-8123-456789abcdef"
THESIS_ID = "11234567-89ab-7def-8123-456789abcdef"
BUILD_ID = "21234567-89ab-7def-8123-456789abcdef"


def brief() -> dict:
    return {
        "schema_version": 1,
        "brand": "Natal",
        "language": "uk",
        "source": {"laval_run_id": RUN_ID, "thesis_id": THESIS_ID},
        "business_idea": "Автоматичне утримання клієнтів",
        "target_audience": "Власники сервісного бізнесу",
        "pain": "Клієнти зникають непомітно",
        "promise": "Natal показує наступну дію",
        "key_features": [{"title": "Сигнали ризику", "description": "Помічає зміни раніше"}],
        "steps": [
            {"title": "01", "description": "Підключіть дані"},
            {"title": "02", "description": "Побачте ризик"},
        ],
        "proof_points": [],
        "faq": [],
        "cta": {"label": "Спробувати Natal", "url": "#contact"},
    }


class Repository:
    def __init__(self, output: Path) -> None:
        self.row = {
            "id": BUILD_ID,
            "request_id": "31234567-89ab-7def-8123-456789abcdef",
            "idea_run_id": RUN_ID,
            "thesis_id": THESIS_ID,
            "template_id": "waitlist",
            "brief": brief(),
            "status": "queued",
            "output_path": str(output),
            "build_manifest": None,
            "artifact_sha256": None,
            "firebase_site_id": "natal-landings-test",
            "firebase_version": None,
            "public_url": None,
            "error_code": None,
            "error_message": None,
        }

    def mark_building(self, _build_id: str):
        self.row["status"] = "building"
        return dict(self.row)

    def mark_publishing(self, _build_id: str, *, manifest, artifact_sha256: str):
        self.row.update(status="publishing", build_manifest=manifest, artifact_sha256=artifact_sha256)
        return dict(self.row)

    def mark_published(self, _build_id: str, *, version: str, public_url: str):
        self.row.update(status="published", firebase_version=version, public_url=public_url)
        return dict(self.row)

    def mark_failed(self, _build_id: str, *, code: str, message: str):
        self.row.update(status="failed", error_code=code, error_message=message)
        return dict(self.row)

    def published(self, _limit: int):
        return []


class Publisher:
    site_id = "natal-landings-test"

    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.files: dict[str, bytes] | None = None

    def publish(self, directory: Path, *, build_id: str):
        if self.failure:
            raise self.failure
        self.files = public_files(directory)
        return {
            "version": "firebase-version-1",
            "public_url": f"https://{self.site_id}.web.app/builds/{build_id}/",
        }


class LandingBuildCoordinatorTests(unittest.TestCase):
    def test_builds_and_publishes_root_and_immutable_url_without_private_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = Repository(root / "builds" / BUILD_ID)
            publisher = Publisher()
            coordinator = LandingBuildCoordinator(
                repository=repository, publisher=publisher, output_root=root, stopped=lambda: False
            )
            coordinator.run_sync(BUILD_ID)
        self.assertEqual("published", repository.row["status"])
        self.assertEqual("firebase-version-1", repository.row["firebase_version"])
        self.assertEqual(64, len(repository.row["artifact_sha256"]))
        self.assertIsNotNone(publisher.files)
        assert publisher.files is not None
        self.assertIn("/index.html", publisher.files)
        self.assertIn(f"/builds/{BUILD_ID}/index.html", publisher.files)
        self.assertNotIn("/brief.json", publisher.files)
        self.assertNotIn(f"/builds/{BUILD_ID}/build.json", publisher.files)
        self.assertIn("Автоматичне утримання клієнтів", publisher.files["/index.html"].decode())

    def test_publish_failure_is_durable_and_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = Repository(root / "builds" / BUILD_ID)
            coordinator = LandingBuildCoordinator(
                repository=repository,
                publisher=Publisher(failure=FirebaseHostingError("permission denied")),
                output_root=root,
                stopped=lambda: False,
            )
            coordinator.run_sync(BUILD_ID)
        self.assertEqual("failed", repository.row["status"])
        self.assertEqual("FirebaseHostingError", repository.row["error_code"])
        self.assertIn("permission denied", repository.row["error_message"])

    def test_emergency_stop_prevents_firebase_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = Repository(root / "builds" / BUILD_ID)
            publisher = Publisher()
            coordinator = LandingBuildCoordinator(
                repository=repository, publisher=publisher, output_root=root, stopped=lambda: True
            )
            coordinator.run_sync(BUILD_ID)
        self.assertEqual("failed", repository.row["status"])
        self.assertIsNone(publisher.files)
        self.assertIn("emergency stop", repository.row["error_message"])


if __name__ == "__main__":
    unittest.main()
