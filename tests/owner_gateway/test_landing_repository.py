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

    from owner_gateway.landing_repository import LandingBuildRepository


RUN_ID = "01234567-89ab-7def-8123-456789abcdef"
THESIS_ID = "11234567-89ab-7def-8123-456789abcdef"
BUILD_ID = "21234567-89ab-7def-8123-456789abcdef"
REQUEST_ID = "31234567-89ab-7def-8123-456789abcdef"


@unittest.skipUnless(POSTGRES_AVAILABLE, "LANDING_TEST_DATABASE_URL and psycopg are required")
class LandingBuildRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = os.environ["LANDING_TEST_DATABASE_URL"]
        with psycopg.connect(cls.database_url, autocommit=True) as connection:
            if connection.execute("SELECT to_regclass('commander_entities')").fetchone()[0] is None:
                for path in sorted(Path("db/migrations").glob("*.sql")):
                    connection.execute(path.read_text())

    def setUp(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute("DELETE FROM natal_landing_builds")
            connection.execute(
                "DELETE FROM commander_relationships WHERE source_id IN (SELECT id FROM commander_entities WHERE kind='landing')"
            )
            connection.execute("DELETE FROM commander_entities WHERE kind='landing'")
            connection.execute("DELETE FROM commander_external_aliases WHERE system='idea_laval_run'")
            connection.execute(
                "DELETE FROM commander_entities WHERE kind='source' AND attributes->>'source_type'='idea_laval_evaluation'"
            )
        self.repository = LandingBuildRepository(self.database_url)
        self.prepared = {
            "build_id": BUILD_ID,
            "idea_run_id": RUN_ID,
            "template_id": "waitlist",
            "brief": {
                "schema_version": 1,
                "brand": "Natal",
                "language": "uk",
                "source": {"laval_run_id": RUN_ID, "thesis_id": THESIS_ID},
                "business_idea": "A sourced landing",
                "target_audience": "Evaluated audience",
                "pain": "Evaluated pain",
                "promise": "Evaluated promise",
                "key_features": [{"title": "Feature", "description": "Truthful detail"}],
                "steps": [{"title": "01", "description": "Start"}],
                "proof_points": [],
                "faq": [],
                "cta": {"label": "Try Natal", "url": "#contact"},
            },
        }

    def test_durable_lifecycle_and_source_lineage(self) -> None:
        created, is_new = self.repository.create(
            self.prepared,
            request_id=REQUEST_ID,
            requested_by="firebase:owner",
            output_path=f"/tmp/landings/builds/{BUILD_ID}",
            firebase_site_id="natal-landings-test",
        )
        duplicate, duplicate_is_new = self.repository.create(
            self.prepared,
            request_id=REQUEST_ID,
            requested_by="firebase:owner",
            output_path=f"/tmp/landings/builds/{BUILD_ID}",
            firebase_site_id="natal-landings-test",
        )
        self.assertTrue(is_new)
        self.assertFalse(duplicate_is_new)
        self.assertEqual(created["id"], duplicate["id"])
        self.assertEqual("queued", self.repository.active()["status"])
        self.repository.mark_building(BUILD_ID)
        self.repository.mark_publishing(
            BUILD_ID, manifest={"template_id": "waitlist"}, artifact_sha256="a" * 64
        )
        published = self.repository.mark_published(
            BUILD_ID,
            version="firebase-version-1",
            public_url=f"https://natal-landings-test.web.app/builds/{BUILD_ID}/",
        )
        self.assertEqual("published", published["status"])
        self.assertIsNotNone(published["completed_at"])
        self.assertIsNone(self.repository.active())
        with psycopg.connect(self.database_url) as connection:
            edge = connection.execute(
                """SELECT source.kind,target.kind,relation
                   FROM commander_relationships relationship
                   JOIN commander_entities source ON source.id=relationship.source_id
                   JOIN commander_entities target ON target.id=relationship.target_id
                   WHERE relationship.source_id=%s""",
                (BUILD_ID,),
            ).fetchone()
        self.assertEqual(("landing", "source", "derived_from"), tuple(edge))

    def test_failed_build_is_retryable(self) -> None:
        self.repository.create(
            self.prepared,
            request_id=REQUEST_ID,
            requested_by="firebase:owner",
            output_path=f"/tmp/landings/builds/{BUILD_ID}",
            firebase_site_id="natal-landings-test",
        )
        failed = self.repository.mark_failed(BUILD_ID, code="test", message="retry me")
        self.assertEqual("failed", failed["status"])
        retried = self.repository.retry(BUILD_ID)
        self.assertEqual("queued", retried["status"])
        self.assertIsNone(retried["error_message"])
        self.assertIsNone(retried["completed_at"])


if __name__ == "__main__":
    unittest.main()
