from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from natal.page import page_content_from_brief


HAS_RUNTIME = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None

if HAS_RUNTIME:
    import httpx
    from fastapi.testclient import TestClient

    from owner_gateway.api import create_app
    from owner_gateway.auth import OwnerIdentity
    from owner_gateway.control_store import ControlStore
    from owner_gateway.settings import Settings


RUN_ID = "01234567-89ab-7def-8123-456789abcdef"
THESIS_ID = "11234567-89ab-7def-8123-456789abcdef"
REQUEST_ID = "21234567-89ab-7def-8123-456789abcdef"


class FakeCoordinator:
    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self.requests: dict[str, str] = {}
        self.run_ids: list[str] = []
        self.feedback_items: list[dict] = []
        self.recovered = False
        self.ready = True

    def recover_interrupted(self) -> int:
        self.recovered = True
        return 0

    def verify_ready(self) -> None:
        if not self.ready:
            raise RuntimeError("Natal landing revision bridge mode is unavailable")

    def active(self):
        return next(
            (item for item in self.items.values() if item["status"] in {"queued", "revising", "building", "publishing"}),
            None,
        )

    def by_request(self, request_id: str):
        build_id = self.requests.get(request_id)
        return self.items.get(build_id) if build_id else None

    def create(self, prepared, *, request_id: str, requested_by: str):
        existing = self.by_request(request_id)
        if existing is not None:
            return existing, False
        build_id = str(prepared["build_id"])
        UUID(build_id)
        row = {
            "id": build_id,
            "request_id": request_id,
            "idea_run_id": prepared["idea_run_id"],
            "thesis_id": prepared["brief"]["source"].get("thesis_id"),
            "template_id": prepared["template_id"],
            "parent_build_id": prepared.get("parent_build_id"),
            "revision_number": len(self.items) + 1,
            "input_brief": prepared["brief"],
            "brief": prepared["brief"],
            "skill_memory_feedback_ids": [item["id"] for item in self.feedback_items],
            "revision_summary": None,
            "revision_invocation": None,
            "source_draft_snapshot_id": prepared.get("source_draft_snapshot_id"),
            "page_content": prepared.get("page_content"),
            "page_content_sha256": prepared.get("page_content_sha256"),
            "status": "queued",
            "build_manifest": None,
            "artifact_sha256": None,
            "firebase_site_id": "natal-landings-test",
            "firebase_version": None,
            "public_url": None,
            "error_code": None,
            "error_message": None,
            "requested_by": requested_by,
            "created_at": "2026-08-22T00:00:00+00:00",
            "updated_at": "2026-08-22T00:00:00+00:00",
            "completed_at": None,
        }
        self.items[build_id] = row
        self.requests[request_id] = build_id
        return row, True

    async def run(self, build_id: str) -> None:
        self.run_ids.append(build_id)

    def list(self, limit: int = 30, *, idea_run_id: str | None = None):
        items = list(self.items.values())
        if idea_run_id:
            items = [item for item in items if item["idea_run_id"] == idea_run_id]
        return items[:limit]

    def skill_memory(self, idea_run_id: str):
        return [item for item in self.feedback_items if item["idea_run_id"] == idea_run_id]

    def record_feedback(self, build_id: str, *, comment: str, requested_by: str):
        row = self.get(build_id)
        if row["status"] != "published":
            raise ValueError("feedback can be recorded only for a published landing revision")
        item = {
            "id": "41234567-89ab-7def-8123-456789abcdef",
            "build_id": build_id,
            "idea_run_id": row["idea_run_id"],
            "template_id": row["template_id"],
            "revision_number": row["revision_number"],
            "comment": comment.strip(),
            "weight_update_id": "51234567-89ab-7def-8123-456789abcdef",
            "created_at": "2026-08-22T00:00:02+00:00",
            "requested_by": requested_by,
        }
        self.feedback_items.append(item)
        return item

    def get(self, build_id: str):
        if build_id not in self.items:
            raise KeyError(build_id)
        return self.items[build_id]

    def retry(self, build_id: str):
        row = self.get(build_id)
        if row["status"] != "failed":
            raise ValueError("only a failed landing build can be retried")
        row.update(status="queued", error_code=None, error_message=None, completed_at=None)
        return row


class FakeDraftCoordinator:
    def __init__(self) -> None:
        self.sets: dict[str, dict] = {}
        self.requests: dict[str, str] = {}
        self.edits: dict[str, dict] = {}
        self.stale_snapshots: dict[str, dict] = {}
        self.populate_calls = 0
        self.edit_calls = 0
        self.ready = True

    def recover_interrupted(self): return 0
    def verify_ready(self):
        if not self.ready: raise RuntimeError("Natal local preview bridge is unavailable")
    def active(self): return None
    def by_request(self, request_id):
        draft_id = self.requests.get(request_id)
        return self.sets.get(draft_id) if draft_id else None
    def latest(self, idea_run_id):
        return next((item for item in self.sets.values() if item["idea_run_id"] == idea_run_id), None)
    def get(self, draft_id):
        if draft_id not in self.sets: raise KeyError(draft_id)
        return self.sets[draft_id]
    def create(self, prepared, *, request_id, requested_by):
        existing = self.by_request(request_id)
        if existing: return existing, False
        draft_id = "71234567-89ab-7def-8123-456789abcdef"
        row = {
            "id": draft_id, "request_id": request_id, "idea_run_id": prepared["idea_run_id"],
            "thesis_id": prepared["brief"]["source"].get("thesis_id"), "brief": prepared["brief"],
            "recommended_template_id": prepared["recommended_template_id"],
            "skill_memory_feedback_ids": [], "status": "queued", "population_summary": None,
            "population_invocation": None, "error_code": None, "error_message": None,
            "requested_by": requested_by, "variants": [], "edits": [],
            "created_at": "2026-08-22T00:00:00+00:00", "updated_at": "2026-08-22T00:00:00+00:00",
            "completed_at": None,
        }
        self.sets[draft_id] = row
        self.requests[request_id] = draft_id
        return row, True
    async def populate(self, draft_id):
        self.populate_calls += 1
        row = self.get(draft_id)
        row.update(
            status="ready", population_summary="Prepared all three templates.",
            updated_at="2026-08-22T00:00:01+00:00", completed_at="2026-08-22T00:00:01+00:00",
        )
        row["variants"] = [self._snapshot(row, template_id, index + 8) for index, template_id in enumerate(("product", "community", "waitlist"))]
    @staticmethod
    def _snapshot(row, template_id, prefix):
        content = page_content_from_brief(template_id, row["brief"]).to_dict()
        return {
            "id": f"{prefix}1234567-89ab-7def-8123-456789abcdef", "draft_set_id": row["id"],
            "template_id": template_id, "snapshot_number": 1, "parent_snapshot_id": None,
            "source_feedback_id": None, "page_content": content,
            "page_content_sha256": "a" * 64, "artifact_sha256": "b" * 64,
            "is_current": True, "application_summary": "Initial set", "invocation": None,
            "created_at": "2026-08-22T00:00:01+00:00",
        }
    def preview(self, snapshot_id):
        snapshot = self.snapshot(snapshot_id)
        return {
            "snapshot_id": snapshot_id, "template_id": snapshot["template_id"],
            "snapshot_number": snapshot["snapshot_number"], "artifact_sha256": snapshot["artifact_sha256"],
            "html": '<!doctype html><style>body{margin:0}</style><section data-landing-block="hero">Natal</section><script>document.querySelector("a")</script>',
        }
    def snapshot(self, snapshot_id):
        if snapshot_id in self.stale_snapshots:
            return self.stale_snapshots[snapshot_id]
        for row in self.sets.values():
            for item in row["variants"]:
                if item["id"] == snapshot_id: return item
        raise KeyError(snapshot_id)
    def get_edit(self, request_id):
        if request_id not in self.edits: raise KeyError(request_id)
        return self.edits[request_id]
    def create_edit(self, snapshot_id, *, request_id, block_id, instruction, requested_by):
        try:
            return self.get_edit(request_id), False
        except KeyError:
            pass
        snapshot = self.snapshot(snapshot_id)
        if not snapshot["is_current"]: raise ValueError("draft snapshot is stale; reload the current preview")
        edit = {
            "request_id": request_id, "draft_set_id": snapshot["draft_set_id"],
            "template_id": snapshot["template_id"], "base_snapshot_id": snapshot_id,
            "block_id": block_id, "instruction": instruction.strip(),
            "feedback_id": "b1234567-89ab-7def-8123-456789abcdef",
            "proposal_id": "c1234567-89ab-7def-8123-456789abcdef",
            "result_snapshot_id": None, "status": "queued", "error_code": None,
            "error_message": None, "created_at": "2026-08-22T00:00:02+00:00",
            "updated_at": "2026-08-22T00:00:02+00:00", "completed_at": None,
        }
        self.edits[request_id] = edit
        self.get(snapshot["draft_set_id"])["edits"].insert(0, edit)
        return edit, True
    async def edit(self, request_id):
        self.edit_calls += 1
        edit = self.get_edit(request_id)
        base = self.snapshot(edit["base_snapshot_id"])
        base["is_current"] = False
        self.stale_snapshots[base["id"]] = base
        content = {**base["page_content"], "blocks": {**base["page_content"]["blocks"]}}
        content["blocks"][edit["block_id"]] = {
            **content["blocks"][edit["block_id"]], "title": "Only the selected block changed",
        }
        result = {
            **base, "id": "d1234567-89ab-7def-8123-456789abcdef", "snapshot_number": 2,
            "parent_snapshot_id": base["id"], "source_feedback_id": edit["feedback_id"],
            "page_content": content, "is_current": True,
        }
        row = self.get(edit["draft_set_id"])
        row["variants"] = [result if item["id"] == base["id"] else item for item in row["variants"]]
        edit.update(status="completed", result_snapshot_id=result["id"], completed_at="2026-08-22T00:00:03+00:00")
    def retry_population(self, draft_id): return self.get(draft_id)
    def retry_edit(self, request_id): return self.get_edit(request_id)
    def proposals(self, draft_id):
        return [{
            "id": edit["proposal_id"], "feedback_id": edit["feedback_id"], "draft_set_id": draft_id,
            "template_id": edit["template_id"], "block_id": edit["block_id"],
            "proposed_lesson": "Keep block edits outcome-first.", "reviewed_lesson": None,
            "status": "pending_review", "command_session_id": None, "comment": edit["instruction"],
            "created_at": edit["created_at"], "updated_at": edit["updated_at"],
        } for edit in self.edits.values()]


@unittest.skipUnless(HAS_RUNTIME, "FastAPI and httpx are required")
class LandingBuilderGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.settings = Settings(
            firebase_project_id="project", firebase_app_id="app", owner_email="owner@example.test",
            owner_uid="owner", service_account_path=None, idea_database_url="postgres://idea",
            idea_service_url="http://idea", idea_service_token="bridge-token",
            commander_database_url="postgres://commander", platform_database_url="postgres://platform",
            platform_owner_telegram_id=1, owner_chat_id=1, control_database_path=root / "control.sqlite3",
            repository_path=root, codex_executable="codex", root_broker_socket=root / "broker.sock",
            commander_asset_root=root / "assets", commander_policy_path=root / "policy.json",
            public_origin="https://example.test",
        )
        self.headers = {"Authorization": "Bearer owner-token", "X-Firebase-AppCheck": "app-token"}
        self.coordinator = FakeCoordinator()
        self.drafts = FakeDraftCoordinator()
        self.case = {
            "idea_run_id": RUN_ID,
            "owner_idea": "Retention platform for service teams",
            "recommended_thesis_id": THESIS_ID,
            "quality": {"successful": 8, "attempted": 9},
            "theses": [{
                "id": THESIS_ID, "recommended": True, "verdict": "survives",
                "title": {"uk": "Утримання без таблиць", "en": "Retention without sheets"},
                "target_user": {"uk": "Команди салонів", "en": "Salon teams"},
                "problem": {"uk": "Клієнти зникають непомітно", "en": "Clients disappear silently"},
                "value_moment": {"uk": "Наступна дія видима", "en": "The next action is visible"},
                "loop_steps": [{"uk": "Підключити дані", "en": "Connect data"}, {"uk": "Побачити ризик", "en": "See risk"}],
                "mechanism_ids": [],
            }],
            "mechanisms": [],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    class Verifier:
        def verify(self, token: str, app_token: str) -> OwnerIdentity:
            if token != "owner-token" or app_token != "app-token":
                raise ValueError("invalid credentials")
            return OwnerIdentity("owner", "owner@example.test")

    def client_fixture(self):
        case = self.case

        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def request(self, _method: str, url: str, **_kwargs):
                if url.endswith("/branding/cases"):
                    return httpx.Response(200, json={"items": [case], "next_cursor": None})
                if url.endswith("/activity"):
                    return httpx.Response(200, json={"active": False})
                return httpx.Response(404, json={"detail": "unexpected"})

        return Client()

    def test_lists_templates_and_completed_evaluation_briefs(self) -> None:
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator)) as client,
        ):
            templates = client.get("/api/v1/landings/templates", headers=self.headers)
            candidates = client.get("/api/v1/landings/candidates", headers=self.headers)
            builds = client.get("/api/v1/landings/builds", headers=self.headers)
        self.assertEqual(["product", "community", "waitlist"], [item["id"] for item in templates.json()["items"]])
        prepared = candidates.json()["items"][0]
        self.assertEqual(RUN_ID, prepared["brief"]["source"]["laval_run_id"])
        self.assertEqual("product", prepared["recommended_template_id"])
        self.assertEqual([], builds.json()["items"])
        self.assertTrue(self.coordinator.recovered)

    def test_one_request_starts_domain_build_without_creating_commander_plan(self) -> None:
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator)) as client,
        ):
            response = client.post(
                "/api/v1/landings/builds", headers=self.headers,
                json={
                    "request_id": REQUEST_ID,
                    "idea_run_id": RUN_ID, "template_id": "auto",
                    "brief": {
                        "business_idea": "Sharper evaluated idea",
                        "source": {"laval_run_id": "spoofed"},
                    },
                },
            )
            detail = client.get(
                f"/api/v1/landings/builds/{response.json()['id']}", headers=self.headers
            )
        self.assertEqual(202, response.status_code, response.text)
        body = response.json()
        self.assertEqual("queued", body["status"])
        self.assertEqual("product", body["template_id"])
        self.assertEqual("Sharper evaluated idea", body["brief"]["business_idea"])
        self.assertEqual(RUN_ID, body["brief"]["source"]["laval_run_id"])
        self.assertEqual([body["id"]], self.coordinator.run_ids)
        self.assertEqual(body["id"], detail.json()["id"])
        self.assertEqual([], ControlStore(self.settings.control_database_path).commands())

    def test_request_id_is_idempotent_and_legacy_route_starts_same_real_build(self) -> None:
        payload = {"request_id": REQUEST_ID, "idea_run_id": RUN_ID, "template_id": "community"}
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator)) as client,
        ):
            first = client.post("/api/v1/landings/builder-jobs", headers=self.headers, json=payload)
            second = client.post("/api/v1/landings/builds", headers=self.headers, json=payload)
        self.assertEqual(202, first.status_code)
        self.assertEqual("execute", first.json()["mode"])
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(1, len(self.coordinator.run_ids))

    def test_one_action_populates_three_private_drafts_idempotently_and_serves_no_store_preview(self) -> None:
        payload = {"request_id": REQUEST_ID, "idea_run_id": RUN_ID}
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator, self.drafts)) as client,
        ):
            first = client.post("/api/v1/landings/draft-sets", headers=self.headers, json=payload)
            detail = client.get(
                f"/api/v1/landings/draft-sets/{first.json()['id']}", headers=self.headers
            )
            second = client.post("/api/v1/landings/draft-sets", headers=self.headers, json=payload)
            snapshot_id = detail.json()["variants"][0]["id"]
            preview = client.get(
                f"/api/v1/landings/draft-snapshots/{snapshot_id}/preview", headers=self.headers
            )
        self.assertEqual(202, first.status_code, first.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(1, self.drafts.populate_calls)
        self.assertEqual(["product", "community", "waitlist"], [item["template_id"] for item in detail.json()["variants"]])
        self.assertEqual("private, no-store", preview.headers["cache-control"])
        self.assertIn("data-landing-block", preview.json()["html"])

    def test_block_edit_is_snapshot_scoped_and_rejects_the_superseded_snapshot(self) -> None:
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator, self.drafts)) as client,
        ):
            created = client.post(
                "/api/v1/landings/draft-sets", headers=self.headers,
                json={"request_id": REQUEST_ID, "idea_run_id": RUN_ID},
            ).json()
            current = client.get(
                f"/api/v1/landings/draft-sets/{created['id']}", headers=self.headers
            ).json()
            base = next(item for item in current["variants"] if item["template_id"] == "product")
            original_hero = base["page_content"]["blocks"]["hero"]
            edit_request = "e1234567-89ab-7def-8123-456789abcdef"
            accepted = client.post(
                f"/api/v1/landings/draft-snapshots/{base['id']}/edits", headers=self.headers,
                json={"request_id": edit_request, "block_id": "features", "instruction": "Lead with the result"},
            )
            updated = client.get(
                f"/api/v1/landings/draft-sets/{created['id']}", headers=self.headers
            ).json()
            stale = client.post(
                f"/api/v1/landings/draft-snapshots/{base['id']}/edits", headers=self.headers,
                json={"request_id": "f1234567-89ab-7def-8123-456789abcdef", "block_id": "hero", "instruction": "Shorter"},
            )
            proposals = client.get(
                f"/api/v1/landings/skill-proposals?draft_set_id={created['id']}", headers=self.headers
            )
        self.assertEqual(202, accepted.status_code, accepted.text)
        product = next(item for item in updated["variants"] if item["template_id"] == "product")
        self.assertEqual(2, product["snapshot_number"])
        self.assertEqual(original_hero, product["page_content"]["blocks"]["hero"])
        self.assertEqual("Only the selected block changed", product["page_content"]["blocks"]["features"]["title"])
        self.assertEqual(409, stale.status_code, stale.text)
        self.assertEqual("features", proposals.json()["items"][0]["block_id"])

    def test_exact_snapshot_publication_skips_revision_readiness(self) -> None:
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator, self.drafts)) as client,
        ):
            draft = client.post(
                "/api/v1/landings/draft-sets", headers=self.headers,
                json={"request_id": REQUEST_ID, "idea_run_id": RUN_ID},
            ).json()
            ready = client.get(
                f"/api/v1/landings/draft-sets/{draft['id']}", headers=self.headers
            ).json()
            snapshot = next(item for item in ready["variants"] if item["template_id"] == "community")
            self.coordinator.ready = False
            published = client.post(
                "/api/v1/landings/builds", headers=self.headers,
                json={
                    "request_id": "f1234567-89ab-7def-8123-456789abcdef",
                    "draft_snapshot_id": snapshot["id"],
                },
            )
        self.assertEqual(202, published.status_code, published.text)
        self.assertEqual(snapshot["id"], published.json()["source_draft_snapshot_id"])
        self.assertEqual(snapshot["page_content_sha256"], published.json()["page_content_sha256"])
        self.assertEqual([published.json()["id"]], self.coordinator.run_ids)

    def test_builder_readiness_fails_before_a_build_is_persisted(self) -> None:
        self.coordinator.ready = False
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator)) as client,
        ):
            response = client.post(
                "/api/v1/landings/builds", headers=self.headers,
                json={"request_id": REQUEST_ID, "idea_run_id": RUN_ID, "template_id": "product"},
            )
        self.assertEqual(503, response.status_code, response.text)
        self.assertEqual([], list(self.coordinator.items))

    def test_failed_build_can_be_retried_from_landing_domain(self) -> None:
        payload = {"request_id": REQUEST_ID, "idea_run_id": RUN_ID, "template_id": "waitlist"}
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator)) as client,
        ):
            created = client.post("/api/v1/landings/builds", headers=self.headers, json=payload).json()
            self.coordinator.items[created["id"]].update(
                status="failed", error_code="FirebaseHostingError", error_message="temporary failure"
            )
            retried = client.post(
                f"/api/v1/landings/builds/{created['id']}/retry", headers=self.headers, json={}
            )
        self.assertEqual(202, retried.status_code)
        self.assertEqual("queued", retried.json()["status"])
        self.assertEqual([created["id"], created["id"]], self.coordinator.run_ids)

    def test_published_revision_accepts_feedback_and_exposes_skill_memory(self) -> None:
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator)) as client,
        ):
            created = client.post(
                "/api/v1/landings/builds", headers=self.headers,
                json={"request_id": REQUEST_ID, "idea_run_id": RUN_ID, "template_id": "product"},
            ).json()
            self.coordinator.items[created["id"]].update(
                status="published", artifact_sha256="a" * 64,
                public_url=f"https://example.test/builds/{created['id']}/",
            )
            feedback = client.post(
                f"/api/v1/landings/builds/{created['id']}/feedback",
                headers=self.headers, json={"comment": "Shorten the hero and strengthen the CTA."},
            )
            memory = client.get(
                f"/api/v1/landings/skill-memory?idea_run_id={RUN_ID}", headers=self.headers,
            )
            next_revision = client.post(
                "/api/v1/landings/builds", headers=self.headers,
                json={
                    "request_id": "61234567-89ab-7def-8123-456789abcdef",
                    "idea_run_id": RUN_ID,
                    "template_id": "community",
                    "parent_build_id": created["id"],
                },
            )
        self.assertEqual(201, feedback.status_code, feedback.text)
        self.assertEqual("product", feedback.json()["template_id"])
        self.assertEqual([feedback.json()["id"]], [item["id"] for item in memory.json()["items"]])
        self.assertEqual(202, next_revision.status_code, next_revision.text)
        self.assertEqual(created["id"], next_revision.json()["parent_build_id"])
        self.assertEqual("community", next_revision.json()["template_id"])
        self.assertEqual(2, next_revision.json()["revision_number"])

    def test_rejects_unknown_template_and_missing_completed_case(self) -> None:
        with (
            patch("owner_gateway.api.httpx.AsyncClient", return_value=self.client_fixture()),
            patch("owner_gateway.api.PlatformRepository.emergency_stop", return_value=False),
            TestClient(create_app(self.settings, self.Verifier(), self.coordinator)) as client,
        ):
            unknown = client.post(
                "/api/v1/landings/builds", headers=self.headers,
                json={"idea_run_id": RUN_ID, "template_id": "unknown"},
            )
            missing = client.post(
                "/api/v1/landings/builds", headers=self.headers,
                json={"idea_run_id": "31234567-89ab-7def-8123-456789abcdef", "template_id": "auto"},
            )
        self.assertEqual(400, unknown.status_code)
        self.assertEqual(404, missing.status_code)


if __name__ == "__main__":
    unittest.main()
