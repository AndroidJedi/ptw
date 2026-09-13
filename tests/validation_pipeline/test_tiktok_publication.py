from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.meta_ads import LocalMetaAdsAuthority, MetaAdsConfiguration, MetaAdsService
from validation_pipeline.social_publishing.providers.tiktok import TikTokConfiguration, TikTokProviderError, TikTokPublishingAdapter
from validation_pipeline.tiktok_publication import LocalTikTokAuthority, TikTokPublicationService
from validation_pipeline.tiktok_publication_routes import tiktok_media_router, tiktok_router
from test_meta_ads import CREATIVE_ID, FakeStudio, FakeWorkspace, PROJECT_ID, REQUEST_ID

ROOT = Path(__file__).resolve().parents[2]


class TikTokWorkspace(FakeWorkspace):
    def __init__(self) -> None:
        output = io.BytesIO()
        Image.new("RGB", (1080, 1350), "#101828").save(output, format="PNG")
        self.png = output.getvalue()

    def version_detail(self, version: int) -> dict[str, object]:
        value = dict(super().version_detail(version))
        value["render_sha256"] = hashlib.sha256(self.png).hexdigest()
        value["assets"] = [{"slot": "phone_screen", "source": {"origin": "openai", "generation_mode": "generate"}}]
        return value


class TikTokApi:
    def __init__(self) -> None:
        self.init_calls = 0
        self.fail_init = False
        self.status = "PUBLISH_COMPLETE"
        self.public_post_ids = [9988]
        self.requests: list[httpx.Request] = []
        self.username = "natal_cast"
        self.oauth_error: str | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/creator_info/query/"):
            return httpx.Response(200, json={"data": {"creator_username": self.username, "creator_nickname": "Natal", "privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"], "comment_disabled": False}, "error": {"code": "ok"}})
        if request.url.path.endswith("/oauth/token/"):
            if self.oauth_error:
                return httpx.Response(200, json={"error": self.oauth_error, "error_description": "rejected"})
            body = request.content.decode()
            refreshed = "grant_type=refresh_token" in body
            return httpx.Response(200, json={"open_id": "open-natal", "scope": "user.info.basic,video.publish", "access_token": "access-rotated" if refreshed else "access-oauth", "refresh_token": "refresh-rotated" if refreshed else "refresh-oauth", "expires_in": 86400, "refresh_expires_in": 31536000})
        if request.url.path.endswith("/oauth/revoke/"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/content/init/"):
            self.init_calls += 1
            if self.fail_init:
                raise httpx.ReadTimeout("lost response containing private detail")
            return httpx.Response(200, json={"data": {"publish_id": "pub-1"}, "error": {"code": "ok"}})
        if request.url.path.endswith("/status/fetch/"):
            ids = self.public_post_ids if self.status == "PUBLISH_COMPLETE" else []
            return httpx.Response(200, json={"data": {"status": self.status, "publicaly_available_post_id": ids}, "error": {"code": "ok"}})
        if request.url.path.endswith("/video/query/"):
            return httpx.Response(200, json={"data": {"videos": [{"id": "9988", "view_count": 120, "like_count": 12, "comment_count": 3, "share_count": 4}]}, "error": {"code": "ok"}})
        raise AssertionError(str(request.url))


class TikTokPublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.store = LocalBriefStore(Path(self.directory.name))
        self.store.append("projects", PROJECT_ID, {"project_id": PROJECT_ID, "name": "Example"})
        self.studio = FakeStudio()
        self.studio.workspace = TikTokWorkspace()
        self.sources = MetaAdsService(LocalMetaAdsAuthority(self.store), self.studio, MetaAdsConfiguration())
        self.authority = LocalTikTokAuthority(self.store)
        self.configuration = TikTokConfiguration(client_key="client", client_secret="secret", token_encryption_key="11" * 32, expected_username="natal_cast", media_origin="https://media.example.com", direct_post_audited=True)
        self.provider = TikTokApi()
        self.http = httpx.Client(transport=httpx.MockTransport(self.provider.handler))
        self.adapter = TikTokPublishingAdapter(self.authority, self.configuration, client=self.http)
        nonce, ciphertext = self.adapter.cipher.encrypt({"access_token": "access-secret", "refresh_token": "refresh-secret"})
        now = datetime.now(timezone.utc)
        self.authority.save_connection({"open_id": "open-natal", "username": "natal_cast", "nickname": "Natal", "scopes": ["user.info.basic", "video.publish"], "token_nonce": nonce, "token_ciphertext": ciphertext, "access_expires_at": (now + timedelta(hours=12)).isoformat(), "refresh_expires_at": (now + timedelta(days=300)).isoformat(), "connected": True, "connected_at": now.isoformat()})
        self.service = TikTokPublicationService(self.authority, self.sources, self.configuration, self.adapter)

    def tearDown(self) -> None:
        self.http.close()
        self.directory.cleanup()

    def request(self, *, privacy: str = "PUBLIC_TO_EVERYONE") -> dict[str, object]:
        connection = self.service.connection()
        return {"request_id": REQUEST_ID, "source": {"creative_id": CREATIVE_ID, "version": 1}, "content": {"title": "Natal support", "description": "Reviewed description"}, "settings": {"privacy_level": privacy, "allow_comment": False, "auto_add_music": True, "commercial_content": {"enabled": True, "own_brand": True, "branded_content": False}}, "creator_snapshot_sha256": connection["creator_snapshot_sha256"], "consent": {"music_usage_confirmed": True}}

    def test_direct_post_uses_common_shape_and_server_aigc(self) -> None:
        publication, created = self.service.reserve(PROJECT_ID, self.request(), "owner-test")
        self.assertTrue(created)
        self.assertEqual("tiktok", publication["provider"])
        self.assertEqual("queued", publication["phase"])
        self.assertTrue(publication["specification"]["is_aigc"])
        token = self.authority.get(publication["publication_id"])["state"]["media_token"]
        result = self.service.execute(publication["publication_id"])
        self.assertEqual("published", result["phase"])
        self.assertEqual(["9988"], result["external"]["post_ids"])
        self.assertEqual(1, self.provider.init_calls)
        init = next(item for item in self.provider.requests if item.url.path.endswith("/content/init/"))
        payload = json.loads(init.content)
        self.assertEqual("DIRECT_POST", payload["post_mode"])
        self.assertEqual([f"https://media.example.com/api/v1/public/tiktok-media/{token}.jpg"], payload["source_info"]["photo_images"])
        self.assertTrue(payload["is_aigc"])
        self.assertNotIn("is_aigc", payload["post_info"])
        self.assertTrue(self.service.media(token).startswith(b"\xff\xd8"))
        self.assertNotIn("access-secret", json.dumps(result))

    def test_lost_content_init_response_is_uncertain_and_never_replayed(self) -> None:
        publication, _ = self.service.reserve(PROJECT_ID, self.request(), "owner-test")
        self.provider.fail_init = True
        result = self.service.execute(publication["publication_id"])
        self.assertEqual("uncertain", result["phase"])
        self.assertTrue(result["external"]["transfer_started"])
        self.assertTrue(result["external"]["commit_started"])
        self.assertFalse(result["retryable"])
        self.assertEqual(1, self.provider.init_calls)
        self.service.execute(publication["publication_id"])
        self.service.execute(publication["publication_id"], reconcile_only=True)
        self.assertEqual(1, self.provider.init_calls)
        with self.assertRaises(RuntimeError):
            self.service.retry(PROJECT_ID, publication["publication_id"])

    def test_duplicate_request_and_creator_snapshot_are_enforced(self) -> None:
        request = self.request()
        first, _ = self.service.reserve(PROJECT_ID, request, "owner-test")
        same, created = self.service.reserve(PROJECT_ID, request, "owner-test")
        self.assertFalse(created)
        self.assertEqual(first["publication_id"], same["publication_id"])
        with self.assertRaises(ValueError):
            self.service.reserve(PROJECT_ID, {**request, "content": {"title": "Changed", "description": "Reviewed description"}}, "owner-test")
        changed = {**self.request(), "request_id": "01900000-0000-7000-8000-000000000099", "creator_snapshot_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "creator settings changed"):
            self.service.reserve(PROJECT_ID, changed, "owner-test")

    def test_unaudited_connection_exposes_private_only(self) -> None:
        config = TikTokConfiguration(client_key="client", client_secret="secret", token_encryption_key="11" * 32, expected_username="natal_cast", media_origin="https://media.example.com", direct_post_audited=False)
        adapter = TikTokPublishingAdapter(self.authority, config, client=self.http)
        connection = adapter.connection()
        self.assertTrue(connection["verified"])
        self.assertEqual(["SELF_ONLY"], connection["creator"]["privacy_level_options"])

    def test_analytics_requires_its_scope_and_a_separate_public_photo_canary(self) -> None:
        self.assertIn("video.list", self.adapter.oauth_url("state"))
        self.assertIn("video.list", self.adapter.analytics_connection()["explanation"])
        current = self.authority.connection_record()
        self.authority.save_connection({**current, "scopes": ["user.info.basic", "video.publish", "video.list"]})

        gated = TikTokPublishingAdapter(self.authority, self.configuration, client=self.http)
        self.assertFalse(gated.analytics_connection()["available"])
        self.assertFalse(gated.analytics_connection()["public_photo_canary_verified"])

        ready_configuration = TikTokConfiguration(
            client_key="client", client_secret="secret",
            token_encryption_key="11" * 32, expected_username="natal_cast",
            media_origin="https://media.example.com", direct_post_audited=True,
            photo_analytics_audited=True,
        )
        ready = TikTokPublishingAdapter(self.authority, ready_configuration, client=self.http)
        self.assertTrue(ready.analytics_connection()["available"])
        self.assertEqual({
            "view_count": 120, "like_count": 12,
            "comment_count": 3, "share_count": 4,
        }, ready.video_insights(["9988"]))
        query = next(item for item in self.provider.requests if item.url.path.endswith("/video/query/"))
        self.assertEqual({"filters": {"video_ids": ["9988"]}}, json.loads(query.content))

    def test_private_complete_without_public_id_is_published(self) -> None:
        self.provider.public_post_ids = []
        publication, _ = self.service.reserve(PROJECT_ID, self.request(privacy="SELF_ONLY"), "owner-test")
        result = self.service.execute(publication["publication_id"])
        self.assertEqual("published", result["phase"])
        self.assertEqual([], result["external"]["post_ids"])

    def test_connection_identity_is_sticky(self) -> None:
        current = self.authority.connection_record()
        with self.assertRaisesRegex(ValueError, "cannot be replaced"):
            self.authority.save_connection({**current, "open_id": "different"})

    def test_live_creator_username_is_required(self) -> None:
        self.provider.username = ""
        connection = self.service.connection()
        self.assertFalse(connection["verified"])
        self.assertIn("pinned account", connection["explanation"])

    def test_disconnect_revokes_then_clears_tokens_but_keeps_identity(self) -> None:
        self.assertEqual({"connected": False}, self.service.disconnect())
        value = self.authority.connection_record()
        self.assertEqual("open-natal", value["open_id"])
        self.assertFalse(value["connected"])
        self.assertIsNone(value["token_ciphertext"])
        self.assertTrue(any(request.url.path.endswith("/oauth/revoke/") for request in self.provider.requests))

    def test_oauth_pins_account_encrypts_tokens_and_rejects_state_replay(self) -> None:
        disconnected = LocalTikTokAuthority(self.store)
        disconnected.disconnect_connection()
        adapter = TikTokPublishingAdapter(disconnected, self.configuration, client=self.http)
        service = TikTokPublicationService(disconnected, self.sources, self.configuration, adapter)
        started = service.oauth_start("owner-test", "/?page=studio")
        state = started["authorization_url"].split("state=", 1)[1]
        result = service.oauth_callback("oauth-code", state)
        self.assertEqual("natal_cast", result["account"]["username"])
        raw = self.store.list("tiktok_connections")[0]
        self.assertNotIn("access-oauth", json.dumps(raw))
        self.assertNotIn("refresh-oauth", json.dumps(raw))
        with self.assertRaisesRegex(ValueError, "already used"):
            service.oauth_callback("oauth-code", state)

    def test_refresh_rotates_encrypted_refresh_token(self) -> None:
        current = self.authority.connection_record()
        self.authority.save_connection({**current, "access_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()})
        self.assertTrue(self.service.connection()["verified"])
        saved = self.authority.connection_record()
        tokens = self.adapter.cipher.decrypt(saved["token_nonce"], saved["token_ciphertext"])
        self.assertEqual("refresh-rotated", tokens["refresh_token"])

    def test_wrong_oauth_account_and_incomplete_disclosure_are_rejected(self) -> None:
        self.provider.username = "someone_else"
        started = self.service.oauth_start("owner-test")
        state = started["authorization_url"].split("state=", 1)[1]
        with self.assertRaisesRegex(ValueError, "Only @natal_cast"):
            self.service.oauth_callback("oauth-code", state)
        self.provider.username = "natal_cast"
        request = self.request()
        request["request_id"] = "01900000-0000-7000-8000-000000000098"
        request["settings"]["commercial_content"] = {"enabled": True, "own_brand": False, "branded_content": False}
        with self.assertRaisesRegex(ValueError, "disclosure is inconsistent"):
            self.service.reserve(PROJECT_ID, request, "owner-test")

    def test_oauth_top_level_error_is_rejected(self) -> None:
        self.provider.oauth_error = "invalid_grant"
        started = self.service.oauth_start("owner-test")
        state = started["authorization_url"].split("state=", 1)[1]
        with self.assertRaisesRegex(TikTokProviderError, "TikTok request failed"):
            self.service.oauth_callback("bad-code", state)

    def test_common_routes_are_authenticated_and_media_is_capability_bounded(self) -> None:
        app = FastAPI()
        def auth(x_test: str = Header(default="")) -> None:
            if x_test != "owner": raise HTTPException(401)
        app.include_router(tiktok_router(self.service, prefix="/api/v1/tiktok", dependencies=[Depends(auth)]))
        app.include_router(tiktok_media_router(self.service, prefix="/api/v1/public/tiktok-media"))
        with TestClient(app) as client:
            base = f"/api/v1/tiktok/projects/{PROJECT_ID}"
            self.assertEqual(401, client.get(base).status_code)
            self.assertEqual(200, client.get(base, headers={"X-Test": "owner"}).status_code)
            response = client.post(base + "/publications", json=self.request(), headers={"X-Test": "owner"})
            self.assertEqual(202, response.status_code)
            publication = response.json()["publication"]
            self.assertEqual("tiktok", publication["provider"])
            self.assertNotIn("media_token", response.text)
            token = self.authority.get(publication["publication_id"])["state"]["media_token"]
            media = client.get(f"/api/v1/public/tiktok-media/{token}.jpg")
            self.assertEqual("image/jpeg", media.headers["content-type"])
            self.assertEqual(404, client.get("/api/v1/public/tiktok-media/bad.jpg").status_code)


class TikTokConfiguratorTests(unittest.TestCase):
    def test_hidden_configurator_writes_only_locked_server_credentials(self) -> None:
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.env"
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/configure_tiktok.sh")],
                env={**os.environ, "TIKTOK_SECRETS_FILE": str(target)},
                input="client-key\nclient-secret-never-print\n" + "22" * 32 + "\n",
                text=True, capture_output=True, check=True,
            )
            self.assertNotIn("client-secret-never-print", result.stdout + result.stderr)
            self.assertEqual(0o600, target.stat().st_mode & 0o777)
            fields = dict(line.split("=", 1) for line in target.read_text().splitlines())
            self.assertEqual({"TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_TOKEN_ENCRYPTION_KEY"}, set(fields))


if __name__ == "__main__":
    unittest.main()
