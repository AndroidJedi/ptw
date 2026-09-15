"""Durable provider-neutral publication orchestration."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from commander.ids import new_uuid7
from validation_pipeline.local_brief_store import utc_now
from validation_pipeline.meta_ads import _uuid
from validation_pipeline.approved_posts import caption_with_url


TERMINAL_PHASES = {"published", "published_unresolved", "uncertain", "failed"}


class SocialPublishingEngine:
    """Orchestrate immutable Studio artifacts through one provider adapter contract."""

    def __init__(self, authority: Any, sources: Any, adapter: Any, *, origin: str) -> None:
        self.authority = authority
        self.sources = sources
        self.adapter = adapter
        self.origin = origin.rstrip("/")
        self.analytics: Any | None = None

    @property
    def provider(self) -> str:
        return str(self.adapter.provider)

    def connection(self, *, verify: bool = True) -> dict[str, Any]:
        return self.adapter.connection(verify=verify)

    def _state(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return dict(self.adapter.state(record))

    def safe(self, record: Mapping[str, Any]) -> dict[str, Any]:
        specification = deepcopy(dict(record["specification"]))
        state = self._state(record)
        phase = str(state["phase"])
        external = {
            "transfer_id": state.get("transfer_id"),
            "post_ids": list(state.get("post_ids") or []),
            "permalink": state.get("permalink"),
            "transfer_started": bool(state.get("transfer_started")),
            "commit_started": bool(state.get("commit_started")),
            "provider_status": state.get("provider_status"),
        }
        analytics_projection = deepcopy(specification.get("analytics"))
        if self.analytics is not None:
            analytics_projection = self.analytics.publication_projection(
                provider=self.provider, project_id=str(record["project_id"]),
                source_entity_id=str(record["publication_id"]),
            )
        result = {
            "provider": self.provider,
            "publication_id": str(record["publication_id"]),
            "project_id": str(record["project_id"]),
            "request_id": str(record["request_id"]),
            "source": deepcopy(specification.get("source") or {}),
            "content": deepcopy(specification.get("content") or {}),
            "settings": deepcopy(specification.get("settings") or {}),
            "account": deepcopy(specification.get("account") or {}),
            "phase": phase,
            "external": external,
            "retryable": phase == "failed" and state.get("error_kind", "retryable") == "retryable"
                and not external["commit_started"]
                and not (external["transfer_started"] and not external["transfer_id"]),
            "syncable": bool(external["transfer_id"] or external["transfer_started"] or external["commit_started"]),
            "error": state.get("error"),
            "specification": specification,
            "analytics": analytics_projection,
            "published_at": state.get("published_at"),
            "created_at": record["created_at"],
        }
        result.update(self.adapter.compatibility(record, state))
        return result

    def _register_attribution(self, record: Mapping[str, Any]) -> None:
        if self.analytics is None:
            return
        specification = record["specification"]
        prepared = specification.get("analytics")
        landing = specification.get("landing")
        if prepared and landing:
            self.analytics.register_attribution(
                prepared=prepared, project_id=str(record["project_id"]),
                channel="organic", provider=self.provider,
                source_entity_id=str(record["publication_id"]), landing=landing,
            )

    def workspace(self, project_id: str) -> dict[str, Any]:
        self.sources.authority.project(_uuid(project_id, "project_id"))
        return {
            "provider": self.provider,
            "connection": self.connection(verify=False),
            "sources": self.sources._sources(project_id),
            "landing": self.sources.landing(project_id),
            "publications": [self.safe(item) for item in self.authority.list(project_id)],
        }

    def publications(self, project_id: str) -> dict[str, Any]:
        self.sources.authority.project(_uuid(project_id, "project_id"))
        return {"items": [self.safe(item) for item in self.authority.list(project_id)]}

    def detail(self, project_id: str, identifier: str) -> dict[str, Any]:
        value = self.authority.get(_uuid(identifier, "publication_id"))
        if value["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError(f"{self.provider} publication not found in this Project")
        return {**self.safe(value), "attempts": self.authority.attempts(identifier)}

    def reserve(
        self, project_id: str, request: Mapping[str, Any], actor: str,
    ) -> tuple[dict[str, Any], bool]:
        project_id = _uuid(project_id, "project_id")
        review = self.adapter.normalize_review(request)
        request_id = _uuid(review["request_id"], "request_id")
        source = dict(review["source"])
        creative_id = _uuid(source["creative_id"], "creative_id")
        version = source["version"]
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("Approved Post version must be a positive integer")
        review = {**review, "request_id": request_id, "source": {"creative_id": creative_id, "version": version}}
        fingerprint = self.adapter.request_fingerprint(project_id, review)
        with self.authority.lock("request:" + request_id):
            previous = self.authority.request(request_id)
            if previous:
                if previous["request_sha256"] != fingerprint:
                    raise ValueError("Request ID was reused with different publication input")
                self._register_attribution(previous)
                return self.safe(previous), False
            artifact = self.sources._artifact(project_id, creative_id, version)
            connection = self.connection()
            if not connection.get("verified"):
                raise RuntimeError(str(connection.get("explanation") or f"{self.provider} publishing is unavailable"))
            self.adapter.validate_review(review, connection)
            rendered, source_record = artifact["rendered"], artifact["record"]
            delivery = self.adapter.build_delivery(rendered["bytes"], source_record["render_sha256"])
            token = secrets.token_urlsafe(32)
            source_id = source_record.get("version_id") or str(uuid5(
                NAMESPACE_URL,
                f"ptw-studio-version:{creative_id}:{version}:{source_record['version_sha256']}",
            ))
            source_spec = {
                "creative_id": creative_id, "version": version,
                "version_id": source_id,
                "version_sha256": source_record["version_sha256"],
                "render_sha256": source_record["render_sha256"],
            }
            publication_id = new_uuid7()
            landing = self.sources.landing(project_id)
            analytics = None if self.analytics is None else self.analytics.prepare_attribution(landing)
            published_content = deepcopy(review.get("content") or {})
            if analytics and landing and self.provider == "instagram":
                published_content["description"] = caption_with_url(
                    published_content.get("description", ""), analytics["tracked_url"],
                )
            specification = {
                "source": source_spec,
                "content": published_content,
                "settings": deepcopy(review.get("settings") or {}),
                "account": self.adapter.account(connection),
                "creator_snapshot_sha256": review.get("creator_snapshot_sha256"),
                "consent": deepcopy(review.get("consent") or {}),
                "delivery_sha256": hashlib.sha256(delivery).hexdigest(),
                "requested_by": actor,
                "landing": landing,
                "analytics": analytics,
            }
            specification.update(self.adapter.provider_specification(
                review, artifact, connection, delivery,
            ))
            if analytics and landing and self.provider == "instagram":
                specification["caption"] = published_content["description"]
            expires = datetime.now(timezone.utc) + timedelta(hours=1)
            initial = self.adapter.state_patch(
                phase="queued", transfer_id=None, post_ids=[], permalink=None,
                transfer_started=False, commit_started=False, provider_status=None,
                media_token=token, media_expires_at=expires.isoformat(), error=None,
            )
            value = {
                "publication_id": publication_id, "project_id": project_id,
                "request_id": request_id, "request_sha256": fingerprint,
                "specification": specification, "created_at": utc_now(),
                "media_token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "state": initial,
            }
            stored = self.authority.reserve(value, delivery)
            self._register_attribution(stored)
            return self.safe(stored), True

    def media(self, token: str) -> bytes:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise KeyError("Media unavailable")
        value, data = self.authority.delivery(hashlib.sha256(token.encode()).hexdigest())
        state = self._state(value)
        expires = datetime.fromisoformat(str(state["media_expires_at"]))
        if expires <= datetime.now(timezone.utc):
            raise KeyError("Media unavailable")
        if state["phase"] in TERMINAL_PHASES and not self.adapter.capabilities().get("media_after_terminal", False):
            raise KeyError("Media unavailable")
        if hashlib.sha256(data).hexdigest() != value["specification"]["delivery_sha256"]:
            raise KeyError("Media unavailable")
        return data

    def _update(self, identifier: str, **canonical: Any) -> dict[str, Any]:
        return self.authority.update(identifier, **self.adapter.state_patch(**canonical))

    def _resolve(self, identifier: str, value: Mapping[str, Any], post_ids: tuple[str, ...]) -> dict[str, Any]:
        resolved = self.adapter.resolve(post_ids, value["specification"])
        keep_media = bool(self.adapter.capabilities().get("media_after_terminal"))
        state = self._state(value)
        result = self._update(
            identifier, phase="published", post_ids=list(post_ids),
            permalink=resolved.get("permalink"), error=None,
            published_at=state.get("published_at") or utc_now(),
            media_token=state.get("media_token") if keep_media else None,
            provider_status=resolved.get("provider_status", "PUBLISHED"),
        )
        return self.safe(result)

    def execute(self, identifier: str, *, reconcile_only: bool = False) -> dict[str, Any]:
        with self.authority.lock("publication:" + identifier):
            value = self.authority.get(identifier)
            state = self._state(value)
            if state["phase"] == "published" and not reconcile_only:
                return self.safe(value)
            try:
                if not self.adapter.account_matches(value["specification"]):
                    raise RuntimeError("The selected publishing account is unavailable or has changed")
                post_ids = tuple(str(item) for item in state.get("post_ids") or ())
                if post_ids:
                    if reconcile_only:
                        self.authority.attempt(
                            identifier, "sync", str(state.get("provider_status") or "published"),
                        )
                    return self._resolve(identifier, value, post_ids)
                transfer_id = state.get("transfer_id")
                capabilities = self.adapter.capabilities()
                implicit_commit = capabilities["commit_strategy"] == "on_transfer_create"
                if not transfer_id:
                    if state.get("transfer_started"):
                        uncertain = self._update(
                            identifier, phase="uncertain",
                            error="The provider transfer may have started but returned no identity. Check the provider; PTW will not submit it again.",
                        )
                        return self.safe(uncertain)
                    if reconcile_only:
                        return self.safe(value)
                    if datetime.fromisoformat(str(state["media_expires_at"])) <= datetime.now(timezone.utc):
                        raise RuntimeError("Image access expired before preparation; create a new reviewed publication")
                    value = self._update(
                        identifier, phase="preparing", error=None,
                        transfer_started=True, commit_started=implicit_commit,
                    )
                    state = self._state(value)
                    media_path = str(capabilities["media_path"])
                    media_url = f"{self.origin}{media_path}/{state['media_token']}.jpg"
                    transfer_id = self.adapter.create_transfer(media_url, value["specification"])
                    value = self._update(identifier, transfer_id=transfer_id, phase="preparing")
                    self.authority.attempt(
                        identifier,
                        str(capabilities.get("transfer_attempt_stage") or "transfer"),
                        "completed",
                    )
                    state = self._state(value)
                status = self.adapter.transfer_status(str(transfer_id), value["specification"])
                if reconcile_only:
                    self.authority.attempt(identifier, "sync", status.provider_status)
                if status.kind == "failed":
                    failed = self._update(
                        identifier, phase="failed", provider_status=status.provider_status,
                        error=status.error or "The provider rejected the publication",
                        error_kind="terminal",
                        media_token=state.get("media_token") if capabilities.get("media_after_terminal") else None,
                    )
                    return self.safe(failed)
                if implicit_commit:
                    if status.kind == "complete":
                        if status.post_ids:
                            return self._resolve(identifier, value, status.post_ids)
                        phase = status.final_phase or "published_unresolved"
                        return self.safe(self._update(
                            identifier, phase=phase, provider_status=status.provider_status,
                            published_at=state.get("published_at") or utc_now(),
                            media_token=state.get("media_token") if capabilities.get("media_after_terminal") else None,
                            error=None,
                        ))
                    if status.kind == "processing":
                        return self.safe(self._update(
                            identifier, phase="preparing", provider_status=status.provider_status,
                        ))
                    raise RuntimeError("Provider publication status is unknown")
                if state.get("commit_started"):
                    phase = "published_unresolved" if status.kind == "complete" else "uncertain"
                    return self.safe(self._update(
                        identifier, phase=phase, provider_status=status.provider_status,
                        media_token=None,
                        error="Publication outcome needs reconciliation. Check the provider before creating another post.",
                    ))
                if reconcile_only:
                    return self.safe(self.authority.get(identifier))
                attempts = int(capabilities.get("poll_attempts", 1))
                for index in range(max(1, attempts)):
                    if status.kind == "ready":
                        break
                    if status.kind != "processing":
                        raise RuntimeError("Provider media readiness is unknown")
                    if index + 1 < attempts:
                        self.adapter.wait(float(capabilities.get("poll_interval", 0)))
                        status = self.adapter.transfer_status(str(transfer_id), value["specification"])
                if status.kind != "ready":
                    raise RuntimeError("Provider image is not ready; retry preparation later")
                value = self._update(identifier, phase="publishing", commit_started=True)
                post_ids = self.adapter.commit(str(transfer_id), value["specification"])
                value = self._update(
                    identifier, phase="published_unresolved", post_ids=list(post_ids), media_token=None,
                )
                self.authority.attempt(identifier, "publish", "completed")
                return self._resolve(identifier, value, post_ids)
            except Exception as error:
                current = self._state(self.authority.get(identifier))
                uncertain = bool(
                    current.get("commit_started")
                    or (current.get("transfer_started") and not current.get("transfer_id"))
                )
                self.authority.attempt(
                    identifier, current["phase"], "uncertain" if uncertain else "failed",
                )
                patch: dict[str, Any] = {
                    "phase": "uncertain" if uncertain else "failed",
                    "error_kind": self.adapter.classify_error(error, uncertain=uncertain),
                    "error": self.adapter.public_error(error, uncertain=uncertain),
                }
                if not self.adapter.capabilities().get("media_after_terminal", False):
                    patch["media_token"] = None
                return self.safe(self._update(identifier, **patch))

    def retry(self, project_id: str, identifier: str) -> dict[str, Any]:
        self.detail(project_id, identifier)
        with self.authority.lock("publication:" + identifier):
            value = self.authority.get(identifier)
            state = self._state(value)
            if (state["phase"] != "failed" or state.get("commit_started")
                    or (state.get("transfer_started") and not state.get("transfer_id"))):
                raise RuntimeError("This publication must be reconciled instead of published again")
            return self.safe(self._update(identifier, phase="queued", error=None, error_kind=None))

    def recover_interrupted(self) -> list[str]:
        return [
            item["publication_id"] for item in self.authority.list()
            if self._state(item)["phase"] not in TERMINAL_PHASES
        ]

    def maintain(self) -> None:
        for identifier in self.recover_interrupted():
            self.execute(identifier, reconcile_only=True)
