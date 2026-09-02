"""Authenticated structured bridge client for Product Brief generation."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Mapping
import urllib.error
import urllib.request


JSON_MODES = ("product_brief", "product_brief_revision")


class StructuredBridge:
    def __init__(self, url: str, token: str, model: str, *, timeout_seconds: int = 420) -> None:
        if not url or not token:
            raise RuntimeError("the authenticated structured bridge is required")
        self.url = url.rstrip("/")
        self.token = token
        self.model = model or "codex-cli-default"
        self.timeout_seconds = timeout_seconds
        self.last_invocation: dict[str, Any] = {}
        self._slots = threading.BoundedSemaphore(2)

    def capabilities(self) -> dict[str, Any]:
        value = self._request(f"{self.url}/capabilities", None, timeout=5)
        json_modes = value.get("json_modes")
        media_modes = value.get("media_modes")
        maximum = value.get("max_request_bytes")
        if (
            not isinstance(json_modes, list)
            or not all(isinstance(item, str) for item in json_modes)
            or not isinstance(media_modes, list)
            or not all(isinstance(item, str) for item in media_modes)
            or not isinstance(maximum, int)
        ):
            raise ValueError("structured bridge capabilities are invalid")
        if set(json_modes) != set(JSON_MODES) or len(json_modes) != len(JSON_MODES):
            raise RuntimeError("structured bridge JSON modes do not match the Product Brief contract")
        if media_modes:
            raise RuntimeError("the Product Brief bridge must not expose media-generation modes")
        return {
            "json_modes": sorted(json_modes),
            "media_modes": [],
            "max_request_bytes": maximum,
        }

    def generate(
        self, *, mode: str, system_prompt: str, input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any], prompt_version: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if mode not in JSON_MODES:
            raise ValueError("unsupported Product Brief bridge mode")
        if not self._slots.acquire(timeout=max(0, self.timeout_seconds)):
            raise TimeoutError(f"{mode} could not enter its bounded execution slot")
        try:
            result = self._call(
                mode=mode, system_prompt=system_prompt, input_payload=input_payload,
                output_schema=output_schema, prompt_version=prompt_version,
                idempotency_key=idempotency_key,
            )
        finally:
            self._slots.release()
        self.last_invocation = dict(result["invocation"])
        return result

    def _call(
        self, *, mode: str, system_prompt: str, input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any], prompt_version: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        context_hash = self._digest(input_payload)
        request_document: dict[str, Any] = {
            "mode": mode,
            "system_prompt": system_prompt,
            "input_payload": dict(input_payload),
            "output_schema": dict(output_schema),
            "prompt_template_version": prompt_version,
            "context_hash": context_hash,
            "idempotency_key": f"{idempotency_key}:attempt:1",
        }
        if self.model != "codex-cli-default":
            request_document["model"] = self.model
        queued = self._request(self.url, request_document)
        request_id = int(queued["request_id"])
        result = self._await(request_id, deadline=time.monotonic() + self.timeout_seconds)
        if result.get("image") is not None:
            raise ValueError("Product Brief modes must not return generated media")
        response = self._response_object(result)
        invocation = {
            "bridge_request_id": request_id,
            "prompt_template_version": prompt_version,
            "context_hash": context_hash,
            "bridge_attempt": 1,
            **dict(result.get("invocation") or {}),
        }
        return {"response": response, "invocation": invocation}

    def _await(self, request_id: int, *, deadline: float) -> Mapping[str, Any]:
        while time.monotonic() < deadline:
            state = self._request(f"{self.url}/{request_id}", None)
            status = state.get("status")
            if status == "completed":
                result = state.get("result")
                if not isinstance(result, Mapping):
                    raise ValueError("structured bridge completed without a result object")
                return result
            if status == "failed":
                raise RuntimeError(f"structured bridge request {request_id} failed")
            if status == "cancelled":
                raise RuntimeError(f"structured bridge request {request_id} was cancelled")
            time.sleep(1)
        raise TimeoutError(f"structured bridge request {request_id} timed out")

    @staticmethod
    def _response_object(result: Mapping[str, Any]) -> dict[str, Any]:
        raw = result.get("response")
        decoded = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(decoded, dict):
            raise ValueError("structured bridge response is not one JSON object")
        return decoded

    @staticmethod
    def _digest(value: Mapping[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()

    def _request(
        self, url: str, payload: Mapping[str, Any] | None, *, timeout: int = 30,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(
            payload, ensure_ascii=False, default=str,
        ).encode()
        outgoing = urllib.request.Request(
            url, data=body,
            headers={
                "X-PTW-Bridge-Token": self.token,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(outgoing, timeout=timeout) as response:
                value = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raw = error.read(4096).decode("utf-8", errors="replace")
            raise RuntimeError(f"structured bridge HTTP {error.code}: {raw[:500]}") from error
        if not isinstance(value, dict):
            raise ValueError("structured bridge returned invalid JSON")
        return value
