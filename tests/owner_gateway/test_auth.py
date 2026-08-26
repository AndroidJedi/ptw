from __future__ import annotations

import tempfile
import unittest
import importlib.util
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from owner_gateway.settings import Settings

HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
if HAS_FASTAPI:
    from fastapi import HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.testclient import TestClient
    from owner_gateway.auth import OwnerIdentity, validate_owner_claims
    from owner_gateway.api import create_app


def settings(root: Path) -> Settings:
    return Settings(
        firebase_project_id="provethemwrong-86123", firebase_app_id="firebase-app",
        owner_email="sgolovaschuk@gmail.com",
        owner_uid="owner-uid", service_account_path=None,
        validation_database_url="postgres://validation",
        validation_service_url="http://validation", validation_service_token="bridge",
        commander_database_url="postgres://commander",
        platform_database_url="postgres://platform", platform_owner_telegram_id=1, owner_chat_id=1,
        telegram_allowed_chat_ids=frozenset({1}),
        control_database_path=root / "control.sqlite3", repository_path=root,
        codex_executable="codex", root_broker_socket=root / "root.sock",
        public_origin="https://example.test",
    )


@unittest.skipUnless(HAS_FASTAPI, "fastapi is required")
class OwnerClaimsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.settings = settings(Path(self.temp.name))
        self.claims = {
            "uid": "owner-uid", "email": "sgolovaschuk@gmail.com", "email_verified": True,
            "firebase": {"sign_in_provider": "google.com"},
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_exact_owner_is_allowed(self) -> None:
        identity = validate_owner_claims(self.settings, self.claims, {"app_id": "firebase-app"})
        self.assertEqual("owner-uid", identity.uid)

    def test_both_code_owned_owner_hostnames_are_cors_origins(self) -> None:
        firebaseapp = "https://provethemwrong-86123.firebaseapp.com"
        webapp = "https://provethemwrong-86123.web.app"
        configured = replace(
            self.settings,
            public_origin=firebaseapp,
            owner_public_origins=(firebaseapp, webapp),
        )
        middleware = next(
            item for item in create_app(configured).user_middleware
            if item.cls is CORSMiddleware
        )
        self.assertEqual([firebaseapp, webapp], middleware.kwargs["allow_origins"])
        self.assertEqual(["ETag", "Content-Length"], middleware.kwargs["expose_headers"])

    def test_disabled_gateway_import_does_not_load_pillow_or_ad_runtime(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; import owner_gateway.api; "
                    "assert 'PIL' not in sys.modules; "
                    "assert 'commander.ad_generation' not in sys.modules"
                ),
            ],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_route_table_contains_only_v2_workspaces(self) -> None:
        class Verifier:
            def verify_id_token(self, _token): return self.claims
            def verify_app_check(self, _token): return {"app_id": "firebase-app"}

        verifier = Verifier()
        verifier.claims = self.claims
        paths = {route.path for route in create_app(self.settings, verifier=verifier).routes}
        for required in (
            "/api/v1/projects", "/api/v1/projects/{project_id}/rename",
            "/api/v1/briefs", "/api/v1/briefs/{brief_id}/correct",
            "/api/v1/briefs/{brief_id}/approve",
            "/api/v1/ad-batches", "/api/v1/ad-batches/{batch_id}/rerun",
            "/api/v1/ad-creatives/{creative_id}/image",
            "/api/v1/ad-creatives/{creative_id}/feedback", "/api/v1/jobs",
            "/api/v1/ad-studio/tools", "/api/v1/ad-studio/brand-kits",
            "/api/v1/ad-studio/templates", "/api/v1/ad-studio/templates/{template_id}/apply",
            "/api/v1/ad-studio/sources/upload", "/api/v1/ad-studio/sources/{source_asset_id}/asset",
            "/api/v1/ad-studio/sample-sets", "/api/v1/ad-studio/sample-sets/{sample_set_id}",
            "/api/v1/ad-studio/sample-sets/{sample_set_id}/download",
            "/api/v1/ad-studio/recipes", "/api/v1/ad-studio/recipes/{recipe_id}/render",
            "/api/v1/ad-studio/recipes/{recipe_id}/renders",
            "/api/v1/ad-studio/recipes/{recipe_id}/wizard-proposals",
            "/api/v1/ad-studio/wizard-proposals/{proposal_id}/preview",
            "/api/v1/ad-studio/wizard-proposals/{proposal_id}/apply",
            "/api/v1/ad-studio/renders/{render_id}/asset",
            "/api/v1/ad-studio/renders/{render_id}/publish",
            "/api/v1/ad-studio/renders/{render_id}/feedback",
            "/api/v1/jobs/{session_id}/restore",
            "/api/v1/skill-proposals/{domain}/plan",
            "/api/v1/system/health",
            "/internal/v1/validation-failures",
        ):
            self.assertIn(required, paths)
        for retired in (
            "/api/v1/ideas", "/api/v1/branding", "/api/v1/posts",
            "/api/v1/positionings", "/api/v1/ads", "/api/v1/landings/draft-sets",
            "/api/v1/public/landings/{build_id}/leads",
            "/api/v1/briefs/{brief_id}/revisions",
        ):
            self.assertNotIn(retired, paths)

    def test_wrong_email_uid_provider_verification_or_app_check_is_denied(self) -> None:
        variants = [
            {**self.claims, "email": "other@example.com"},
            {**self.claims, "uid": "other"},
            {**self.claims, "email_verified": False},
            {**self.claims, "firebase": {"sign_in_provider": "password"}},
        ]
        for claims in variants:
            with self.subTest(claims=claims), self.assertRaises(HTTPException):
                validate_owner_claims(self.settings, claims, {"app_id": "firebase-app"})
        with self.assertRaises(HTTPException):
            validate_owner_claims(self.settings, self.claims, {})
        with self.assertRaises(HTTPException):
            validate_owner_claims(self.settings, self.claims, {"app_id": "wrong-app"})

    def test_job_cancel_requires_explicit_server_confirmation(self) -> None:
        class Verifier:
            def verify(inner, _token, _app_check):
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")

        client = TestClient(create_app(self.settings, verifier=Verifier()))
        response = client.post(
            "/api/v1/jobs/018f07ea-7f20-7000-8000-000000000001/cancel",
            headers={"Authorization": "Bearer owner", "X-Firebase-AppCheck": "app"},
            json={},
        )
        self.assertEqual(412, response.status_code)
        self.assertIn("explicit confirmation", response.json()["detail"])
        client.close()

    def test_studio_upload_rejects_oversized_base64_before_bridge(self) -> None:
        class Verifier:
            def verify(inner, _token, _app_check):
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")

        client = TestClient(create_app(self.settings, verifier=Verifier()))
        with patch("owner_gateway.api.MAX_STUDIO_UPLOAD_BASE64", 8):
            response = client.post(
                "/api/v1/ad-studio/sources/upload",
                headers={"Authorization": "Bearer owner", "X-Firebase-AppCheck": "app"},
                json={"project_id": "018f07ea-7f20-7000-8000-000000000001", "title": "too large", "mime_type": "video/mp4", "base64": "x" * 9},
            )
        self.assertEqual(413, response.status_code)
        self.assertIn("bounded size", response.json()["detail"])
        client.close()

    def test_learned_batch_rerun_requires_explicit_server_confirmation(self) -> None:
        class Verifier:
            def verify(inner, _token, _app_check):
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")

        client = TestClient(create_app(self.settings, verifier=Verifier()))
        response = client.post(
            "/api/v1/ad-batches/018f07ea-7f20-7000-8000-000000000001/rerun",
            headers={"Authorization": "Bearer owner", "X-Firebase-AppCheck": "app"},
            json={"request_id": "018f07ea-7f20-7000-8000-000000000002"},
        )
        self.assertEqual(412, response.status_code)
        self.assertIn("explicit confirmation", response.json()["detail"])
        client.close()

    def test_project_routes_and_stage_filters_are_proxied_to_validation(self) -> None:
        calls = []

        class Verifier:
            def verify(inner, _token, _app_check):
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")

        class Response:
            status_code = 200
            def json(self): return {"items": [], "next_cursor": None}

        class AsyncClient:
            def __init__(self, *, timeout): self.timeout = timeout
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def request(self, method, url, *, headers, json, params):
                calls.append((method, url, headers, json, params))
                return Response()

        project_id = "018f07ea-7f20-7000-8000-000000000001"
        headers = {"Authorization": "Bearer owner", "X-Firebase-AppCheck": "app"}
        with (
            patch("owner_gateway.api.httpx.AsyncClient", AsyncClient),
            patch("owner_gateway.platform.PlatformRepository.emergency_stop", return_value=False),
        ):
            client = TestClient(create_app(self.settings, verifier=Verifier()))
            self.assertEqual(200, client.get("/api/v1/projects?limit=7", headers=headers).status_code)
            self.assertEqual(
                200,
                client.get(
                    f"/api/v1/briefs?project_id={project_id}&limit=8", headers=headers
                ).status_code,
            )
            self.assertEqual(
                200,
                client.get(
                    f"/api/v1/ad-batches?project_id={project_id}&limit=9", headers=headers
                ).status_code,
            )
            self.assertEqual(
                200,
                client.post(
                    f"/api/v1/projects/{project_id}/rename",
                    headers=headers, json={"name": "Focused project"},
                ).status_code,
            )
            client.close()

        self.assertEqual("/internal/v1/projects", calls[0][1].split("http://validation")[-1])
        self.assertEqual({"limit": 7}, calls[0][4])
        self.assertEqual({"limit": 8, "project_id": project_id}, calls[1][4])
        self.assertEqual({"limit": 9, "project_id": project_id}, calls[2][4])
        self.assertEqual({"name": "Focused project"}, calls[3][3])
        self.assertEqual("firebase:owner-uid", calls[3][2]["X-PTW-Actor"])

    def test_new_studio_proxies_require_owner_tokens_forward_actor_and_preserve_etags(self) -> None:
        calls = []

        class Verifier:
            def verify(inner, _token, _app_check):
                return OwnerIdentity(uid="owner-uid", email="sgolovaschuk@gmail.com")

        class Response:
            def __init__(self, *, status_code=200, binary=False):
                self.status_code = status_code
                self.content = b"studio-binary" if binary and status_code != 304 else b""
                self.headers = {
                    "etag": f'"{"f" * 64}"',
                    "cache-control": "private, max-age=31536000, immutable",
                    "content-type": "image/jpeg",
                    "content-disposition": "attachment; filename=studio.zip",
                }
            def json(self): return {"items": [], "created": True}

        class AsyncClient:
            def __init__(self, *, timeout): self.timeout = timeout
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return None
            async def request(self, method, url, *, headers, json, params):
                path = url.split("http://validation", 1)[-1]
                calls.append((method, path, dict(headers), json, params, self.timeout))
                binary = path.endswith("/asset") or path.endswith("/download") or path.endswith("/preview")
                return Response(
                    status_code=304 if headers.get("If-None-Match") else 200,
                    binary=binary,
                )

        item_id = "018f07ea-7f20-7000-8000-000000000001"
        auth = {"Authorization": "Bearer owner", "X-Firebase-AppCheck": "app"}
        requests = [
            ("post", f"/api/v1/ad-studio/templates/{item_id}/apply", {
                "request_id": item_id, "brief_id": item_id, "creative_id": None, "brand_kit_id": item_id,
            }),
            ("get", f"/api/v1/ad-studio/sources/{item_id}/asset", None),
            ("get", f"/api/v1/ad-studio/sample-sets?project_id={item_id}", None),
            ("post", "/api/v1/ad-studio/sample-sets", {"batch_id": item_id}),
            ("get", f"/api/v1/ad-studio/sample-sets/{item_id}", None),
            ("get", f"/api/v1/ad-studio/sample-sets/{item_id}/download", None),
            ("get", f"/api/v1/ad-studio/recipes/{item_id}/renders", None),
            ("post", f"/api/v1/ad-studio/recipes/{item_id}/wizard-proposals", {
                "instruction": "Shorten the headline", "target_instance_id": None,
            }),
            ("get", f"/api/v1/ad-studio/recipes/{item_id}/wizard-proposals", None),
            ("get", f"/api/v1/ad-studio/wizard-proposals/{item_id}/preview", None),
            ("post", f"/api/v1/ad-studio/wizard-proposals/{item_id}/apply", {}),
        ]
        with (
            patch("owner_gateway.api.httpx.AsyncClient", AsyncClient),
            patch("owner_gateway.platform.PlatformRepository.emergency_stop", return_value=False),
        ):
            client = TestClient(create_app(self.settings, verifier=Verifier()))
            for method, path, body in requests:
                with self.subTest(authentication=path):
                    denied = client.request(method.upper(), path, json=body)
                    self.assertEqual(401, denied.status_code)
                accepted = client.request(method.upper(), path, headers=auth, json=body)
                self.assertIn(accepted.status_code, {200, 201})
            for path in (
                f"/api/v1/ad-studio/sources/{item_id}/asset",
                f"/api/v1/ad-studio/sample-sets/{item_id}/download",
                f"/api/v1/ad-studio/wizard-proposals/{item_id}/preview",
            ):
                first = client.get(path, headers=auth)
                self.assertEqual(f'"{"f" * 64}"', first.headers["etag"])
                cached = client.get(path, headers={**auth, "If-None-Match": first.headers["etag"]})
                self.assertEqual(304, cached.status_code)
            client.close()

        mutation_calls = [call for call in calls if call[0] == "POST"]
        self.assertTrue(mutation_calls)
        self.assertTrue(all(call[2]["X-PTW-Actor"] == "firebase:owner-uid" for call in mutation_calls))
        self.assertTrue(any(call[5] == 2400 for call in calls if call[1].endswith("/wizard-proposals")))
        self.assertTrue(any(call[2].get("If-None-Match") for call in calls))
