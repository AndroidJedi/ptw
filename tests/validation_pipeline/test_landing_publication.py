from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from validation_pipeline.landing_publication import (
    LocalLandingPublicationAuthority, normalized_slug,
)
from validation_pipeline.local_brief_store import LocalBriefStore, utc_now
from validation_pipeline.landing_workspace import DEFAULT_CONFIGURATION, DEFAULT_CONTENT


class FakeWorkspace:
    def __init__(self, assets: dict[tuple[str, str], bytes]) -> None:
        self.assets = assets

    def visual_image(self, slot: str, digest: str):
        try:
            data = self.assets[(slot, digest)]
        except KeyError as error:
            raise KeyError("Landing visual was not found") from error
        return {"bytes": data, "mime_type": "image/png", "sha256": digest}


class LandingPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = LocalBriefStore(Path(self.temporary.name))
        self.assets: dict[str, dict[tuple[str, str], bytes]] = {}
        self.service = LocalLandingPublicationAuthority(
            self.store, lambda landing_id: FakeWorkspace(self.assets[landing_id]),
        )
        self.project_id = self._project("Owner Project")
        self.landing_id = str(uuid4())
        self.store.append("landing_pages", self.landing_id, {
            "landing_id": self.landing_id, "project_id": self.project_id,
            "created_at": utc_now(),
        })
        self._version(1, b"hero one", b"break one")
        self._version(2, b"hero two", b"break two")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _project(self, name: str) -> str:
        project_id = str(uuid4())
        self.store.append("projects", project_id, {
            "project_id": project_id, "request_id": str(uuid4()),
            "owner_idea_source_id": None, "name": name, "name_source": "owner",
            "requested_by": "test", "created_at": utc_now(), "updated_at": utc_now(),
        })
        return project_id

    def _version(self, version: int, hero: bytes, visual_break: bytes) -> dict:
        digests = {
            "hero_visual": hashlib.sha256(hero).hexdigest(),
            "visual_break_visual": hashlib.sha256(visual_break).hexdigest(),
        }
        self.assets.setdefault(self.landing_id, {}).update({
            ("hero_visual", digests["hero_visual"]): hero,
            ("visual_break_visual", digests["visual_break_visual"]): visual_break,
        })
        version_id = str(uuid4())
        record = {
            "schema": "ptw.landing.version.v1", "version": version,
            "state_sha256": str(version) * 64,
            "configuration": deepcopy(DEFAULT_CONFIGURATION),
            "content": deepcopy(DEFAULT_CONTENT),
            "provider_invocation": {"private": "must never be public"},
            "assets": [
                {"slot": slot, "available": True, "sha256": digest, "history": []}
                for slot, digest in digests.items()
            ],
            "change_note": f"Approved {version}",
        }
        from validation_pipeline.landing_publication import sha256_json
        record["content"]["hero"]["title"] = f"Version {version}"
        record["content"]["hero"]["supporting_text"] = "Public supporting text"
        record["content"]["hero"]["cta_label"] = "Start"
        record["version_sha256"] = sha256_json({key: item for key, item in record.items() if key != "version_sha256"})
        value = {
            "version_id": version_id, "landing_id": self.landing_id,
            "version": version, "version_sha256": record["version_sha256"],
            "state_sha256": record["state_sha256"], "record": record,
            "created_at": utc_now(),
        }
        self.store.append("landing_versions", version_id, value)
        return value

    def _publish(self, version: int, **extra):
        return self.service.publish(
            project_id=self.project_id, request_id=str(uuid4()),
            landing_id=self.landing_id, version=version, requested_by="test-owner",
            **extra,
        )

    def test_slug_validation_is_manual_ascii_only(self) -> None:
        self.assertEqual("project-123", normalized_slug("project-123"))
        for invalid in ("ab", "Project", "project--one", "проєкт", " project "):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalized_slug(invalid)

    def test_first_publish_reserves_url_and_is_uuid_idempotent(self) -> None:
        request_id = str(uuid4())
        first = self.service.publish(
            project_id=self.project_id, request_id=request_id,
            landing_id=self.landing_id, version=1, namespace="ai", slug="owner-project",
            requested_by="test-owner",
        )
        repeated = self.service.publish(
            project_id=self.project_id, request_id=request_id,
            landing_id=self.landing_id, version=1, namespace="ai", slug="owner-project",
            requested_by="test-owner",
        )

        self.assertTrue(first["created"])
        self.assertFalse(repeated["created"])
        self.assertEqual(first["event"]["event_id"], repeated["event"]["event_id"])
        self.assertEqual("https://natal-service.com/ai/owner-project", first["publication"]["canonical_url"])

    def test_collision_and_cross_project_versions_fail_closed(self) -> None:
        self._publish(1, namespace="la", slug="stable-path")
        other_project = self._project("Other")
        other_landing = str(uuid4())
        self.store.append("landing_pages", other_landing, {
            "landing_id": other_landing, "project_id": other_project, "created_at": utc_now(),
        })
        other = LocalLandingPublicationAuthority(self.store, lambda _landing_id: FakeWorkspace({}))
        with self.assertRaisesRegex(ValueError, "already reserved"):
            other.publish(
                project_id=other_project, request_id=str(uuid4()), landing_id=other_landing,
                version=1, namespace="la", slug="stable-path", requested_by="test-owner",
            )
        with self.assertRaisesRegex(ValueError, "from this Project"):
            self.service.publish(
                project_id=other_project, request_id=str(uuid4()), landing_id=self.landing_id,
                version=1, namespace="wa", slug="cross-project", requested_by="test-owner",
            )

    def test_republish_rolls_forward_and_back_without_changing_url(self) -> None:
        first = self._publish(1, namespace="wa", slug="rollback-demo")
        second = self._publish(2, namespace=None, slug=None)
        rollback = self._publish(1, namespace=None, slug=None)

        self.assertEqual(1, first["event"]["sequence"])
        self.assertEqual(2, second["event"]["sequence"])
        self.assertEqual(3, rollback["event"]["sequence"])
        snapshot = self.service.snapshot("wa", "rollback-demo")
        self.assertEqual(
            {
                "canonical_url", "project_name", "configuration", "content",
                "assets", "version_sha256", "published_at",
            },
            set(snapshot),
        )
        self.assertEqual("Version 1", snapshot["content"]["hero"]["title"])
        self.assertEqual(first["event"]["landing_version_sha256"], snapshot["version_sha256"])
        self.assertNotIn("project_id", snapshot)
        self.assertNotIn("landing_id", snapshot)
        self.assertNotIn("events", snapshot)
        self.assertNotIn("provider_invocation", snapshot)

    def test_only_current_selected_assets_are_public_and_unpublish_is_404(self) -> None:
        first = self._publish(1, namespace="ai", slug="asset-boundary")
        snapshot = self.service.snapshot("ai", "asset-boundary")
        hero_url = snapshot["assets"]["hero_visual"]
        hero_digest = hero_url.rsplit("/", 1)[1].removesuffix(".png")
        asset = self.service.asset(
            "ai", "asset-boundary", snapshot["version_sha256"], "hero_visual", hero_digest,
        )
        self.assertEqual(b"hero one", asset["bytes"])
        self._publish(2, namespace=None, slug=None)
        with self.assertRaises(KeyError):
            self.service.asset(
                "ai", "asset-boundary", first["event"]["landing_version_sha256"],
                "hero_visual", hero_digest,
            )
        result = self.service.unpublish(
            project_id=self.project_id, request_id=str(uuid4()), requested_by="test-owner",
        )
        self.assertTrue(result["created"])
        self.assertEqual([3, 2, 1], [event["sequence"] for event in result["publication"]["events"]])
        with self.assertRaises(KeyError):
            self.service.snapshot("ai", "asset-boundary")

    def test_publication_and_permanent_reservation_survive_authority_restart(self) -> None:
        first = self._publish(1, namespace="la", slug="restart-proof")
        restarted_store = LocalBriefStore(Path(self.temporary.name))
        restarted = LocalLandingPublicationAuthority(
            restarted_store, lambda landing_id: FakeWorkspace(self.assets[landing_id]),
        )

        snapshot = restarted.snapshot("la", "restart-proof")
        self.assertEqual(first["event"]["landing_version_sha256"], snapshot["version_sha256"])
        unpublish_request_id = str(uuid4())
        first_unpublish = restarted.unpublish(
            project_id=self.project_id, request_id=unpublish_request_id, requested_by="test-owner",
        )

        after_unpublish = LocalLandingPublicationAuthority(
            LocalBriefStore(Path(self.temporary.name)),
            lambda landing_id: FakeWorkspace(self.assets[landing_id]),
        )
        publication = after_unpublish.get(self.project_id)
        self.assertEqual("la", publication["namespace"])
        self.assertEqual("restart-proof", publication["slug"])
        self.assertEqual("unpublished", publication["status"])
        repeated_unpublish = after_unpublish.unpublish(
            project_id=self.project_id, request_id=unpublish_request_id,
            requested_by="test-owner",
        )
        self.assertFalse(repeated_unpublish["created"])
        self.assertEqual(
            first_unpublish["event"]["event_id"], repeated_unpublish["event"]["event_id"],
        )
        with self.assertRaises(KeyError):
            after_unpublish.snapshot("la", "restart-proof")


if __name__ == "__main__":
    unittest.main()
