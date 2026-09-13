"""TikTok Direct Post adapter for one pinned PTW owner account."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import io
import json
import os
import re
import stat
import time
from typing import Any, Mapping
from urllib.parse import urlencode, urlsplit

import httpx

from validation_pipeline.meta_ads import _sha
from validation_pipeline.social_publishing.contracts import TransferStatus


API_ROOT = "https://open.tiktokapis.com/v2"
AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
REQUIRED_SCOPES = frozenset({"user.info.basic", "video.publish"})
ANALYTICS_SCOPES = frozenset({"video.list"})
AUTHORIZATION_SCOPES = REQUIRED_SCOPES | ANALYTICS_SCOPES
_SECRET_KEYS = frozenset({
    "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_TOKEN_ENCRYPTION_KEY",
})


def _secret_file_values() -> dict[str, str]:
    path = os.environ.get("TIKTOK_SECRETS_PATH", "").strip()
    if not path or not os.path.exists(path):
        return {}
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("TikTok secrets path must be a regular file")
    if stat.S_IMODE(metadata.st_mode) not in {0o400, 0o440, 0o600, 0o640}:
        raise RuntimeError("TikTok secrets file must use mode 400, 440, 600, or 640")
    values: dict[str, str] = {}
    with open(path, encoding="utf-8") as secrets:
        for number, raw in enumerate(secrets, 1):
            line = raw.rstrip("\r\n")
            if not line or line.lstrip().startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or key not in _SECRET_KEYS or key in values:
                raise RuntimeError(f"TikTok secrets file has an invalid entry on line {number}")
            values[key] = value.strip()
    return values


def media_origin(value: str = "") -> str:
    value = (value or os.environ.get("TIKTOK_MEDIA_ORIGIN", "")).strip().rstrip("/")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return ""
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.path or parts.query or parts.fragment or port not in {None, 443}
            or parts.hostname in {"localhost", "127.0.0.1", "::1"}):
        return ""
    return value


@dataclass(frozen=True, slots=True)
class TikTokConfiguration:
    client_key: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)
    token_encryption_key: str = field(default="", repr=False)
    expected_username: str = "natal_cast"
    redirect_uri: str = "https://commander.proove-them-wrong.com/api/v1/tiktok/oauth/callback"
    media_origin: str = ""
    direct_post_audited: bool = False
    photo_analytics_audited: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.client_key and self.client_secret and self.token_encryption_key)

    @classmethod
    def from_environment(cls) -> "TikTokConfiguration":
        values = _secret_file_values()
        def value(key: str, default: str = "") -> str:
            return os.environ.get(key, "").strip() or values.get(key, default).strip()
        username = value("TIKTOK_EXPECTED_USERNAME", "natal_cast").lstrip("@").lower()
        if not re.fullmatch(r"[a-z0-9._]{2,24}", username):
            raise RuntimeError("TIKTOK_EXPECTED_USERNAME is invalid")
        redirect = value(
            "TIKTOK_REDIRECT_URI",
            "https://commander.proove-them-wrong.com/api/v1/tiktok/oauth/callback",
        )
        parts = urlsplit(redirect)
        if parts.scheme != "https" or not parts.hostname or parts.fragment:
            raise RuntimeError("TIKTOK_REDIRECT_URI must be an HTTPS URL")
        audited = value("TIKTOK_DIRECT_POST_AUDITED", "0").lower()
        if audited not in {"0", "1", "false", "true"}:
            raise RuntimeError("TIKTOK_DIRECT_POST_AUDITED must be true or false")
        analytics_audited = value("TIKTOK_PHOTO_ANALYTICS_AUDITED", "0").lower()
        if analytics_audited not in {"0", "1", "false", "true"}:
            raise RuntimeError("TIKTOK_PHOTO_ANALYTICS_AUDITED must be true or false")
        return cls(
            client_key=value("TIKTOK_CLIENT_KEY"),
            client_secret=value("TIKTOK_CLIENT_SECRET"),
            token_encryption_key=value("TIKTOK_TOKEN_ENCRYPTION_KEY"),
            expected_username=username, redirect_uri=redirect,
            media_origin=media_origin(value("TIKTOK_MEDIA_ORIGIN")),
            direct_post_audited=audited in {"1", "true"},
            photo_analytics_audited=analytics_audited in {"1", "true"},
        )


class TikTokProviderError(RuntimeError):
    def __init__(self, outcome: str, *, status_code: int | None = None, code: str | None = None) -> None:
        self.outcome, self.status_code, self.code = outcome, status_code, code
        detail = ", ".join(f"{k}={v}" for k, v in (("http", status_code), ("code", code)) if v)
        super().__init__(f"{outcome}{f' ({detail})' if detail else ''}")


class TokenCipher:
    """AES-GCM envelope; plaintext OAuth tokens never enter publication records."""

    def __init__(self, encoded_key: str) -> None:
        try:
            key = bytes.fromhex(encoded_key) if re.fullmatch(r"[0-9a-fA-F]{64}", encoded_key) else base64.urlsafe_b64decode(encoded_key + "=" * (-len(encoded_key) % 4))
        except (ValueError, TypeError) as error:
            raise RuntimeError("TIKTOK_TOKEN_ENCRYPTION_KEY is invalid") from error
        if len(key) != 32:
            raise RuntimeError("TIKTOK_TOKEN_ENCRYPTION_KEY must encode 32 bytes")
        self._key = key

    def encrypt(self, value: Mapping[str, Any]) -> tuple[bytes, bytes]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        data = json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode()
        return nonce, AESGCM(self._key).encrypt(nonce, data, b"ptw:tiktok:oauth:v1")

    def decrypt(self, nonce: bytes, ciphertext: bytes) -> dict[str, Any]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        try:
            value = json.loads(AESGCM(self._key).decrypt(nonce, ciphertext, b"ptw:tiktok:oauth:v1"))
        except Exception as error:
            raise RuntimeError("Stored TikTok authorization cannot be decrypted") from error
        if not isinstance(value, dict):
            raise RuntimeError("Stored TikTok authorization is invalid")
        return value


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"TikTok {field} must be text")
    result = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if any(ord(char) < 32 and char not in "\n\t" for char in result):
        raise ValueError(f"TikTok {field} contains unsupported control characters")
    if _utf16_length(result) > maximum:
        raise ValueError(f"TikTok {field} exceeds {maximum} characters")
    return result


def jpeg_delivery(png: bytes, digest: str) -> bytes:
    from PIL import Image
    if hashlib.sha256(png).hexdigest() != digest:
        raise ValueError("Approved Post image digest mismatch")
    with Image.open(io.BytesIO(png)) as source:
        source.load()
        if source.width < 360 or source.height < 360 or source.width > 4096 or source.height > 4096:
            raise ValueError("Approved Post dimensions are unsupported by TikTok")
        rgba = source.convert("RGBA")
        image = Image.new("RGB", rgba.size, "white")
        image.paste(rgba, mask=rgba.getchannel("A"))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=95, subsampling=0, optimize=False, progressive=False)
    result = output.getvalue()
    if len(result) > 20 * 1024 * 1024:
        raise ValueError("TikTok image exceeds 20 MB")
    return result


def artifact_is_aigc(artifact: Mapping[str, Any]) -> bool:
    record = artifact.get("record") if isinstance(artifact.get("record"), Mapping) else {}
    assets = record.get("assets") if isinstance(record, Mapping) else None
    if not isinstance(assets, list):
        return False
    for asset in assets:
        source = asset.get("source") if isinstance(asset, Mapping) else None
        if not isinstance(source, Mapping):
            continue
        origin = str(source.get("origin") or source.get("provider") or "").lower()
        if origin in {"pexels", "owner_upload", "canonical_natal_brand_asset", "bundled"}:
            continue
        if source.get("generation_mode") or source.get("model") or origin in {"openai", "imagegen", "generated"}:
            return True
    return False


class TikTokPublishingAdapter:
    provider = "tiktok"

    def __init__(self, authority: Any, configuration: TikTokConfiguration, *, client: Any = None, sleep: Any = time.sleep) -> None:
        self.authority, self.configuration, self._client, self.sleep = authority, configuration, client, sleep
        self.cipher = TokenCipher(configuration.token_encryption_key) if configuration.token_encryption_key else None

    def capabilities(self) -> Mapping[str, Any]:
        return {"commit_strategy": "on_transfer_create", "media_path": "/api/v1/public/tiktok-media", "media_after_terminal": True, "poll_attempts": 1, "poll_interval": 0, "transfer_attempt_stage": "transfer"}

    def _call(self, method: str, path: str, *, token: str | None = None, data: Mapping[str, Any] | None = None, json_body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            if self._client is None:
                with httpx.Client(timeout=httpx.Timeout(30, connect=10)) as client:
                    response = client.request(method, f"{API_ROOT}/{path.lstrip('/')}", headers=headers, data=data, json=json_body)
            else:
                response = self._client.request(method, f"{API_ROOT}/{path.lstrip('/')}", headers=headers, data=data, json=json_body)
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise TikTokProviderError("TikTok request failed") from error
        provider_error = payload.get("error") if isinstance(payload, Mapping) else None
        if isinstance(provider_error, Mapping):
            code = str(provider_error.get("code")) if provider_error.get("code") else None
        elif provider_error:
            # OAuth errors use a top-level string while Content Posting uses an
            # error object. Treat both forms as provider failures.
            code = str(provider_error)
        else:
            code = None
        if response.status_code >= 400 or not isinstance(payload, Mapping) or (code and code != "ok"):
            raise TikTokProviderError("TikTok request failed", status_code=response.status_code, code=code)
        return dict(payload)

    def oauth_url(self, state: str) -> str:
        query = urlencode({"client_key": self.configuration.client_key, "scope": ",".join(sorted(AUTHORIZATION_SCOPES)), "response_type": "code", "redirect_uri": self.configuration.redirect_uri, "state": state})
        return f"{AUTHORIZE_URL}?{query}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        return self._call("POST", "/oauth/token/", data={"client_key": self.configuration.client_key, "client_secret": self.configuration.client_secret, "code": code, "grant_type": "authorization_code", "redirect_uri": self.configuration.redirect_uri})

    def revoke(self) -> None:
        record = self.authority.connection_record()
        if not record or not record.get("connected"):
            return
        _record, tokens = self._tokens()
        self._call("POST", "/oauth/revoke/", data={"client_key": self.configuration.client_key, "client_secret": self.configuration.client_secret, "token": tokens["access_token"]})

    def _tokens(self) -> tuple[dict[str, Any], dict[str, Any]]:
        record = self.authority.connection_record()
        if not record or not record.get("connected") or self.cipher is None:
            raise TikTokProviderError("TikTok is not connected")
        if not REQUIRED_SCOPES <= set(record.get("scopes") or []):
            raise TikTokProviderError("TikTok authorization is missing required scopes")
        tokens = self.cipher.decrypt(bytes(record["token_nonce"]), bytes(record["token_ciphertext"]))
        expires = datetime.fromisoformat(str(record["access_expires_at"]))
        if expires <= datetime.now(timezone.utc) + timedelta(minutes=5):
            with self.authority.lock("oauth-refresh"):
                record = self.authority.connection_record()
                if not record or not record.get("connected"):
                    raise TikTokProviderError("TikTok is not connected")
                tokens = self.cipher.decrypt(bytes(record["token_nonce"]), bytes(record["token_ciphertext"]))
                expires = datetime.fromisoformat(str(record["access_expires_at"]))
                if expires <= datetime.now(timezone.utc) + timedelta(minutes=5):
                    value = self._call("POST", "/oauth/token/", data={"client_key": self.configuration.client_key, "client_secret": self.configuration.client_secret, "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]})
                    if str(value.get("open_id") or "") != str(record["open_id"]):
                        raise TikTokProviderError("Refreshed TikTok authorization changed account identity")
                    if not REQUIRED_SCOPES <= set(str(value.get("scope") or "").split(",")):
                        raise TikTokProviderError("Refreshed TikTok authorization lost required scopes")
                    tokens = {"access_token": value["access_token"], "refresh_token": value["refresh_token"]}
                    nonce, ciphertext = self.cipher.encrypt(tokens)
                    record = self.authority.save_connection({**record, "token_nonce": nonce, "token_ciphertext": ciphertext, "access_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=int(value["expires_in"]))).isoformat(), "refresh_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=int(value["refresh_expires_in"]))).isoformat(), "scopes": str(value.get("scope", "")).split(",")})
        return record, tokens

    def creator_info(self, token: str) -> dict[str, Any]:
        payload = self._call("POST", "/post/publish/creator_info/query/", token=token, json_body={})
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise TikTokProviderError("TikTok creator information is unavailable")
        return dict(data)

    def connection(self, *, verify: bool = True) -> dict[str, Any]:
        base = {"provider": self.provider, "configured": self.configuration.configured, "verified": False, "media_ready": bool(self.configuration.media_origin), "direct_post_audited": self.configuration.direct_post_audited, "expected_username": self.configuration.expected_username, "required_scopes": sorted(REQUIRED_SCOPES)}
        record = self.authority.connection_record()
        if not self.configuration.configured:
            return {**base, "explanation": "Configure TikTok client credentials and token encryption before connecting."}
        if not record or not record.get("connected"):
            return {**base, "explanation": f"Connect the exact TikTok account @{self.configuration.expected_username}."}
        base["account"] = {"open_id": record["open_id"], "username": record["username"], "nickname": record.get("nickname")}
        if not verify:
            return base
        try:
            record, tokens = self._tokens()
            creator = self.creator_info(str(tokens["access_token"]))
            username = str(creator.get("creator_username") or "").lstrip("@").lower()
            if username != self.configuration.expected_username or str(record["open_id"]) != str(creator.get("creator_open_id") or record["open_id"]):
                raise TikTokProviderError("Connected TikTok account does not match the pinned account")
            options = [str(item) for item in creator.get("privacy_level_options", []) if isinstance(item, str)]
            if not self.configuration.direct_post_audited:
                options = [item for item in options if item == "SELF_ONLY"]
            snapshot = {"open_id": record["open_id"], "username": username, "nickname": creator.get("creator_nickname") or record.get("nickname"), "privacy_level_options": sorted(set(options)), "comment_disabled": bool(creator.get("comment_disabled"))}
            base.update(verified=bool(self.configuration.media_origin and options), account={"open_id": record["open_id"], "username": username, "nickname": snapshot["nickname"]}, creator=snapshot, creator_snapshot_sha256=_sha(snapshot))
            if not self.configuration.media_origin:
                base["explanation"] = "Configure the verified public TikTok media origin."
            elif not options:
                base["explanation"] = "TikTok Direct Post is unavailable until the app audit permits this account."
        except (TikTokProviderError, RuntimeError) as error:
            base.update(verified=False, explanation=str(error))
        return base

    def analytics_connection(self, *, verify: bool = True) -> dict[str, Any]:
        base = {
            "provider": self.provider, "configured": self.configuration.configured,
            "available": False, "required_scopes": sorted(ANALYTICS_SCOPES),
            "public_photo_canary_required": True,
            "public_photo_canary_verified": self.configuration.photo_analytics_audited,
        }
        record = self.authority.connection_record()
        if not self.configuration.configured or not record or not record.get("connected"):
            return {**base, "explanation": "Connect TikTok before collecting video insights."}
        missing = sorted(ANALYTICS_SCOPES - set(record.get("scopes") or []))
        if missing:
            return {**base, "explanation": "Reauthorize TikTok with video.list; publishing remains available independently."}
        if not self.configuration.photo_analytics_audited:
            return {**base, "explanation": "TikTok photo analytics remains gated until a real audited public-photo canary succeeds."}
        if verify:
            try:
                self._tokens()
            except (TikTokProviderError, RuntimeError) as error:
                return {**base, "explanation": str(error)}
        return {**base, "available": True, "explanation": None}

    def video_insights(self, post_ids: list[str]) -> dict[str, Any]:
        readiness = self.analytics_connection(verify=True)
        if not readiness.get("available"):
            raise TikTokProviderError(str(readiness.get("explanation") or "TikTok analytics is unavailable"))
        if not 1 <= len(post_ids) <= 20 or any(not re.fullmatch(r"[0-9]{1,40}", str(item)) for item in post_ids):
            raise ValueError("TikTok insight refresh accepts 1-20 video IDs")
        _record, tokens = self._tokens()
        fields = "id,create_time,like_count,comment_count,share_count,view_count"
        value = self._call(
            "POST", f"/video/query/?fields={fields}", token=str(tokens["access_token"]),
            json_body={"filters": {"video_ids": [str(item) for item in post_ids]}},
        )
        videos = (value.get("data") or {}).get("videos") if isinstance(value.get("data"), Mapping) else None
        if not isinstance(videos, list):
            raise TikTokProviderError("TikTok video insights returned no videos")
        expected = set(post_ids)
        selected = [item for item in videos if isinstance(item, Mapping) and str(item.get("id")) in expected]
        if len(selected) != len(expected):
            raise TikTokProviderError("TikTok video insights did not match every requested post")
        try:
            return {
                field: sum(max(0, int(item.get(field) or 0)) for item in selected)
                for field in ("view_count", "like_count", "comment_count", "share_count")
            }
        except (TypeError, ValueError) as error:
            raise TikTokProviderError("TikTok video insights contained invalid counts") from error

    def normalize_review(self, request: Mapping[str, Any]) -> dict[str, Any]:
        expected = {"request_id", "source", "content", "settings", "creator_snapshot_sha256", "consent"}
        if set(request) != expected:
            raise ValueError("TikTok publication fields are invalid")
        source, content, settings, consent = request["source"], request["content"], request["settings"], request["consent"]
        if not isinstance(source, Mapping) or set(source) != {"creative_id", "version"}:
            raise ValueError("TikTok publication source is invalid")
        if not isinstance(content, Mapping) or set(content) != {"title", "description"}:
            raise ValueError("TikTok publication content is invalid")
        required_settings = {"privacy_level", "allow_comment", "auto_add_music", "commercial_content"}
        if not isinstance(settings, Mapping) or set(settings) != required_settings:
            raise ValueError("TikTok publication settings are invalid")
        commercial = settings["commercial_content"]
        if not isinstance(commercial, Mapping) or set(commercial) != {"enabled", "own_brand", "branded_content"}:
            raise ValueError("TikTok commercial-content settings are invalid")
        if not isinstance(consent, Mapping) or set(consent) != {"music_usage_confirmed"}:
            raise ValueError("TikTok consent is invalid")
        bools = [settings["allow_comment"], settings["auto_add_music"], commercial["enabled"], commercial["own_brand"], commercial["branded_content"], consent["music_usage_confirmed"]]
        if any(not isinstance(item, bool) for item in bools):
            raise ValueError("TikTok publication controls must be explicit booleans")
        if not consent["music_usage_confirmed"]:
            raise ValueError("Confirm TikTok music usage before posting")
        if commercial["enabled"] != bool(commercial["own_brand"] or commercial["branded_content"]):
            raise ValueError("TikTok commercial-content disclosure is inconsistent")
        if commercial["branded_content"] and settings["privacy_level"] == "SELF_ONLY":
            raise ValueError("Branded content cannot be posted with Only me privacy")
        snapshot = request["creator_snapshot_sha256"]
        if not isinstance(snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", snapshot):
            raise ValueError("TikTok creator snapshot is required")
        return {"request_id": request["request_id"], "source": dict(source), "content": {"title": _text(content["title"], "title", 90), "description": _text(content["description"], "description", 4000)}, "settings": {"privacy_level": str(settings["privacy_level"]), "allow_comment": settings["allow_comment"], "auto_add_music": settings["auto_add_music"], "commercial_content": dict(commercial)}, "creator_snapshot_sha256": snapshot, "consent": {"music_usage_confirmed": True}}

    def request_fingerprint(self, project_id: str, review: Mapping[str, Any]) -> str:
        return _sha({"provider": self.provider, "project_id": project_id, **dict(review)})

    def validate_review(self, review: Mapping[str, Any], connection: Mapping[str, Any]) -> None:
        if review["creator_snapshot_sha256"] != connection.get("creator_snapshot_sha256"):
            raise ValueError("TikTok creator settings changed; review the current posting options")
        creator = connection.get("creator") or {}
        privacy = review["settings"]["privacy_level"]
        if privacy not in creator.get("privacy_level_options", []):
            raise ValueError("Select a currently available TikTok privacy level")
        if review["settings"]["allow_comment"] and creator.get("comment_disabled"):
            raise ValueError("Comments are disabled for this TikTok account")
        if privacy != "SELF_ONLY" and not self.configuration.direct_post_audited:
            raise ValueError("Public TikTok posting is disabled until Direct Post audit approval")

    def build_delivery(self, png: bytes, digest: str) -> bytes:
        return jpeg_delivery(png, digest)

    def account(self, connection: Mapping[str, Any]) -> dict[str, Any]:
        return deepcopy(dict(connection.get("account") or {}))

    def account_matches(self, specification: Mapping[str, Any]) -> bool:
        record = self.authority.connection_record()
        account = specification.get("account") or {}
        return bool(record and record.get("connected") and str(record.get("open_id")) == str(account.get("open_id")) and str(record.get("username", "")).lower() == self.configuration.expected_username)

    def provider_specification(self, review: Mapping[str, Any], artifact: Mapping[str, Any], connection: Mapping[str, Any], delivery: bytes) -> dict[str, Any]:
        return {"tiktok_open_id": connection["account"]["open_id"], "tiktok_username": connection["account"]["username"], "is_aigc": artifact_is_aigc(artifact)}

    def state(self, record: Mapping[str, Any]) -> dict[str, Any]:
        state = dict(record["state"])
        state.setdefault("phase", state.get("status", "queued"))
        state.setdefault("transfer_id", state.get("publish_id"))
        state.setdefault("post_ids", [])
        state.setdefault("transfer_started", False)
        state.setdefault("commit_started", False)
        return state

    def state_patch(self, **canonical: Any) -> dict[str, Any]:
        patch = deepcopy(canonical)
        if "phase" in patch:
            patch["status"] = patch["phase"]
        if "transfer_id" in patch:
            patch["publish_id"] = patch["transfer_id"]
        return patch

    def compatibility(self, record: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
        return {"status": state["phase"], "publish_started": bool(state.get("commit_started")), "publish_id": state.get("transfer_id"), "post_ids": list(state.get("post_ids") or []), "permalink": state.get("permalink")}

    def create_transfer(self, media_url: str, specification: Mapping[str, Any]) -> str:
        _record, tokens = self._tokens()
        settings = specification["settings"]
        commercial = settings["commercial_content"]
        payload = {"post_info": {"title": specification["content"]["title"], "description": specification["content"]["description"], "privacy_level": settings["privacy_level"], "disable_comment": not settings["allow_comment"], "auto_add_music": settings["auto_add_music"], "brand_content_toggle": commercial["branded_content"], "brand_organic_toggle": commercial["own_brand"]}, "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0, "photo_images": [media_url]}, "post_mode": "DIRECT_POST", "media_type": "PHOTO", "is_aigc": bool(specification["is_aigc"])}
        result = self._call("POST", "/post/publish/content/init/", token=str(tokens["access_token"]), json_body=payload)
        publish_id = (result.get("data") or {}).get("publish_id")
        if not publish_id:
            raise TikTokProviderError("TikTok did not return a publish identity")
        return str(publish_id)

    def transfer_status(self, identifier: str, specification: Mapping[str, Any]) -> TransferStatus:
        _record, tokens = self._tokens()
        result = self._call("POST", "/post/publish/status/fetch/", token=str(tokens["access_token"]), json_body={"publish_id": identifier})
        data = result.get("data") or {}
        status = str(data.get("status") or "UNKNOWN")
        if status == "PUBLISH_COMPLETE":
            ids = tuple(str(item) for item in data.get("publicaly_available_post_id", []) if item)
            final_phase = "published" if specification["settings"]["privacy_level"] == "SELF_ONLY" else "published_unresolved"
            return TransferStatus("complete", status, ids, final_phase=final_phase)
        if status in {"PROCESSING_DOWNLOAD", "PROCESSING_UPLOAD", "SEND_TO_USER_INBOX"}:
            return TransferStatus("processing", status)
        if status == "FAILED":
            return TransferStatus("failed", status, error="TikTok rejected the publication")
        return TransferStatus("unknown", status)

    def commit(self, identifier: str, specification: Mapping[str, Any]) -> tuple[str, ...]:
        raise RuntimeError("TikTok Direct Post starts during transfer creation")

    def resolve(self, post_ids: tuple[str, ...], specification: Mapping[str, Any]) -> dict[str, Any]:
        return {"permalink": None, "provider_status": "PUBLISH_COMPLETE"}

    def classify_error(self, error: Exception, *, uncertain: bool) -> str:
        if uncertain:
            return "uncertain"
        if isinstance(error, ValueError):
            return "terminal"
        if isinstance(error, TikTokProviderError):
            return "retryable" if error.status_code in {429, 500, 502, 503, 504} or error.code in {"internal_error", "rate_limit_exceeded"} else "terminal"
        return "retryable"

    def public_error(self, error: Exception, *, uncertain: bool) -> str:
        if uncertain:
            return "TikTok may have accepted this post. Sync status; PTW will not submit it again."
        return "TikTok publication failed. Refresh the connection and review the current creator options before retrying."

    def wait(self, seconds: float) -> None:
        self.sleep(seconds)
