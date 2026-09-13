from __future__ import annotations

from copy import deepcopy
import hashlib
import time
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from validation_pipeline.meta_ads import MetaAdsProviderError, _sha, _text
from validation_pipeline.social_publishing.contracts import TransferStatus


class InstagramPublishingAdapter:
    provider = "instagram"

    def __init__(self, ads: Any, client: Any, *, origin: str, sleep: Any = time.sleep) -> None:
        self.ads = ads
        self.client = client
        self.origin = origin
        self.sleep = sleep

    def capabilities(self) -> Mapping[str, Any]:
        return {
            "commit_strategy": "after_transfer_ready",
            "media_path": "/api/v1/public/instagram-media",
            "media_after_terminal": False,
            "poll_attempts": 5,
            "poll_interval": 60,
            "transfer_attempt_stage": "container",
        }

    def connection(self, *, verify: bool = True) -> dict[str, Any]:
        configured = bool(
            self.client and self.ads.configuration.access_token
            and self.ads.configuration.page_id and self.ads.configuration.instagram_actor_id
        )
        result = {
            "provider": self.provider, "configured": configured, "verified": False,
            "graph_version": self.ads.configuration.graph_version,
            "required_permissions": [
                "pages_show_list", "instagram_basic", "instagram_content_publish",
                "pages_read_engagement",
            ],
            "media_ready": bool(self.origin),
        }
        if not configured:
            return {**result, "explanation": "Configure the Meta token, Facebook Page and professional Instagram account. Export is available."}
        if not verify:
            return result
        try:
            result.update(self.client.publishing_connection())
        except MetaAdsProviderError as error:
            result.update(verified=False, explanation=str(error))
        if not self.origin:
            result.update(verified=False, explanation="Configure a public HTTPS media origin for Instagram. Export is available.")
        return result

    def normalize_review(self, request: Mapping[str, Any]) -> dict[str, Any]:
        legacy = {"request_id", "creative_id", "version", "caption"}
        common = {"request_id", "source", "content", "settings", "creator_snapshot_sha256", "consent"}
        if set(request) == legacy:
            caption = request["caption"]
            source = {"creative_id": request["creative_id"], "version": request["version"]}
        elif set(request) == common:
            source = request["source"]
            content = request["content"]
            if not isinstance(content, Mapping) or set(content) != {"title", "description"}:
                raise ValueError("Instagram publication content is invalid")
            if content["title"] not in {"", None} or request["settings"] or request["consent"] or request["creator_snapshot_sha256"] is not None:
                raise ValueError("Instagram publication settings are invalid")
            caption = content["description"]
        else:
            raise ValueError("Instagram publication fields are invalid")
        if not isinstance(source, Mapping) or set(source) != {"creative_id", "version"}:
            raise ValueError("Instagram publication source is invalid")
        if not isinstance(caption, str):
            raise ValueError("Instagram caption must be text")
        caption = _text(caption, "caption", 0, 2200)
        return {
            "request_id": request["request_id"],
            "source": {"creative_id": source["creative_id"], "version": source["version"]},
            "content": {"title": "", "description": caption},
            "settings": {}, "creator_snapshot_sha256": None, "consent": {},
        }

    def validate_review(self, review: Mapping[str, Any], connection: Mapping[str, Any]) -> None:
        if not connection.get("verified"):
            raise RuntimeError("Instagram publishing is unavailable")

    def request_fingerprint(self, project_id: str, review: Mapping[str, Any]) -> str:
        return _sha({
            "project_id": project_id,
            "creative_id": review["source"]["creative_id"],
            "version": review["source"]["version"],
            "caption": review["content"]["description"],
        })

    def build_delivery(self, png: bytes, digest: str) -> bytes:
        from validation_pipeline.instagram_publication import jpeg_delivery
        return jpeg_delivery(png, digest)

    def account(self, connection: Mapping[str, Any]) -> dict[str, Any]:
        return deepcopy(dict(connection.get("instagram") or {}))

    def account_matches(self, specification: Mapping[str, Any]) -> bool:
        return bool(
            self.client and specification.get("instagram_actor_id")
            == self.ads.configuration.instagram_actor_id
        )

    def provider_specification(
        self, review: Mapping[str, Any], artifact: Mapping[str, Any],
        connection: Mapping[str, Any], delivery: bytes,
    ) -> dict[str, Any]:
        source = review["source"]
        record = artifact["record"]
        source_id = record.get("version_id") or str(uuid5(
            NAMESPACE_URL,
            f"ptw-studio-version:{source['creative_id']}:{source['version']}:{record['version_sha256']}",
        ))
        return {
            "creative_id": source["creative_id"], "version": source["version"],
            "source_version_id": source_id,
            "source_version_sha256": record["version_sha256"],
            "render_sha256": record["render_sha256"],
            "delivery_sha256": hashlib.sha256(delivery).hexdigest(),
            "caption": review["content"]["description"],
            "instagram_actor_id": self.ads.configuration.instagram_actor_id,
            "instagram": deepcopy(connection.get("instagram")),
        }

    def state(self, record: Mapping[str, Any]) -> dict[str, Any]:
        raw = dict(record["state"])
        status = str(raw.get("status") or raw.get("phase") or "queued")
        phase = str(raw.get("phase") or {
            "creating_container": "preparing", "preparing": "preparing",
            "publishing": "publishing", "published": "published",
            "published_unresolved": "published_unresolved", "uncertain": "uncertain",
            "failed": "failed", "queued": "queued",
        }.get(status, "failed"))
        post_ids = raw.get("post_ids")
        if not post_ids and raw.get("media_id"):
            post_ids = [raw["media_id"]]
        return {
            **raw, "phase": phase,
            "transfer_id": raw.get("transfer_id") or raw.get("container_id"),
            "post_ids": list(post_ids or []),
            "permalink": raw.get("permalink"),
            "transfer_started": bool(raw.get("transfer_started") or raw.get("container_id")),
            "commit_started": bool(raw.get("commit_started") or raw.get("publish_started")),
        }

    def state_patch(self, **canonical: Any) -> dict[str, Any]:
        patch = deepcopy(canonical)
        phase = patch.get("phase")
        if phase is not None:
            patch["status"] = (
                "creating_container"
                if phase == "preparing" and patch.get("transfer_started") and "transfer_id" not in patch
                else phase
            )
        if "transfer_id" in patch:
            patch["container_id"] = patch["transfer_id"]
        if "post_ids" in patch:
            patch["media_id"] = next(iter(patch["post_ids"] or []), None)
        if "commit_started" in patch:
            patch["publish_started"] = patch["commit_started"]
        return patch

    def compatibility(self, record: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
        legacy_state = deepcopy(dict(record["state"]))
        legacy_state.pop("media_token", None)
        status = str(legacy_state.get("status") or state["phase"])
        return {
            **legacy_state,
            "status": status,
            "publish_started": bool(state.get("commit_started")),
            "container_id": state.get("transfer_id"),
            "media_id": next(iter(state.get("post_ids") or []), None),
            "permalink": state.get("permalink"),
        }

    def create_transfer(self, media_url: str, specification: Mapping[str, Any]) -> str:
        return str(self.client.create_container(media_url, str(specification["caption"])))

    def transfer_status(self, identifier: str, specification: Mapping[str, Any]) -> TransferStatus:
        status = str(self.client.container_status(identifier))
        if status == "FINISHED":
            return TransferStatus("ready", status)
        if status == "IN_PROGRESS":
            return TransferStatus("processing", status)
        if status == "PUBLISHED":
            return TransferStatus("complete", status)
        if status in {"ERROR", "EXPIRED"}:
            return TransferStatus("failed", status, error="Existing Instagram container cannot be published; inspect its status")
        return TransferStatus("unknown", status)

    def commit(self, identifier: str, specification: Mapping[str, Any]) -> tuple[str, ...]:
        return (str(self.client.publish(identifier)),)

    def resolve(self, post_ids: tuple[str, ...], specification: Mapping[str, Any]) -> dict[str, Any]:
        return {"permalink": self.client.permalink(post_ids[0]), "provider_status": "PUBLISHED"}

    def classify_error(self, error: Exception, *, uncertain: bool) -> str:
        if uncertain:
            return "uncertain"
        if isinstance(error, ValueError):
            return "terminal"
        if isinstance(error, MetaAdsProviderError):
            return "retryable" if error.transient or error.status_code in {429, 500, 502, 503, 504} else "terminal"
        return "retryable"

    def public_error(self, error: Exception, *, uncertain: bool) -> str:
        message = (
            "Publication may have succeeded. Sync status and check Instagram; PTW will not publish it again."
            if uncertain else
            "Instagram publication failed. Check the connection and retry preparation or export the approved image."
        )
        if isinstance(error, MetaAdsProviderError):
            message += " " + str(error)
        return message

    def wait(self, seconds: float) -> None:
        self.sleep(seconds)
