"""Authenticated structured bridge client for PTW Brief and Studio JSON modes."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from typing import Any, Callable, Mapping
import urllib.error
import urllib.request


JSON_MODES = (
    "product_brief", "product_brief_revision", "studio_creative_generation",
    "studio_edit_learning",
)
BRIDGE_JSON_MODES = JSON_MODES
BRIDGE_MEDIA_MODES = ("content_non_human_graphic_generation",)


def _validation_error(error: Exception) -> str:
    message = " ".join(str(error).split())[:500] or type(error).__name__
    return re.sub(
        r"(?i)(token|secret|credential|password)\s*[:=]\s*\S+",
        r"\1=[redacted]", message,
    )


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
        if set(json_modes) != set(BRIDGE_JSON_MODES) or len(json_modes) != len(BRIDGE_JSON_MODES):
            raise RuntimeError("structured bridge JSON modes do not match the deployed provider contract")
        if set(media_modes) != set(BRIDGE_MEDIA_MODES) or len(media_modes) != len(BRIDGE_MEDIA_MODES):
            raise RuntimeError("structured bridge media modes do not match the deployed provider contract")
        return {
            "json_modes": sorted(json_modes),
            "media_modes": sorted(media_modes),
            "max_request_bytes": maximum,
        }

    def generate(
        self, *, mode: str, system_prompt: str, input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any], prompt_version: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if mode not in JSON_MODES:
            raise ValueError("unsupported structured bridge mode")
        if not self._slots.acquire(timeout=max(0, self.timeout_seconds)):
            raise TimeoutError(f"{mode} could not enter its bounded execution slot")
        try:
            result = self._call(
                mode=mode, system_prompt=system_prompt, input_payload=input_payload,
                output_schema=output_schema, prompt_version=prompt_version,
                idempotency_key=idempotency_key, attempt=1,
            )
        finally:
            self._slots.release()
        self.last_invocation = dict(result["invocation"])
        return result

    def call(
        self, *, mode: str, system_prompt: str, input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any], prompt_version: str,
        idempotency_key: str,
        response_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Validate a completed response and make at most one fresh correction.

        Transport, timeout, and provider failures keep their original attempt key
        and are never converted into an uncertain second mutation. A second bridge
        job is created only after PTW has received a completed JSON object and its
        deterministic domain validator has rejected that object.
        """

        if response_validator is None:
            return self.generate(
                mode=mode, system_prompt=system_prompt, input_payload=input_payload,
                output_schema=output_schema, prompt_version=prompt_version,
                idempotency_key=idempotency_key,
            )
        if mode not in JSON_MODES:
            raise ValueError("unsupported structured bridge mode")
        if not self._slots.acquire(timeout=max(0, self.timeout_seconds)):
            raise TimeoutError(f"{mode} could not enter its bounded execution slot")
        validation_attempts: list[dict[str, Any]] = []
        correction: str | None = None
        try:
            for attempt in (1, 2):
                result = self._call(
                    mode=mode, system_prompt=system_prompt, input_payload=input_payload,
                    output_schema=output_schema, prompt_version=prompt_version,
                    idempotency_key=idempotency_key, attempt=attempt,
                    correction=correction,
                )
                try:
                    validated = dict(response_validator(result["response"]))
                except (KeyError, TypeError, ValueError) as error:
                    correction = _validation_error(error)
                    validation_attempts.append({
                        "bridge_request_id": result["invocation"]["bridge_request_id"],
                        "bridge_attempt": attempt,
                        "status": "rejected",
                        "error_type": type(error).__name__,
                        "error_message": correction,
                    })
                    if attempt == 2:
                        raise
                    continue
                validation_attempts.append({
                    "bridge_request_id": result["invocation"]["bridge_request_id"],
                    "bridge_attempt": attempt,
                    "status": "completed",
                })
                result = {
                    **result,
                    "response": validated,
                    "invocation": {
                        **result["invocation"],
                        "validation_attempts": validation_attempts,
                    },
                }
                self.last_invocation = dict(result["invocation"])
                return result
        finally:
            self._slots.release()
        raise RuntimeError("structured bridge validation attempts were exhausted")

    def _call(
        self, *, mode: str, system_prompt: str, input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any], prompt_version: str,
        idempotency_key: str, attempt: int, correction: str | None = None,
    ) -> dict[str, Any]:
        context_hash = self._digest(input_payload)
        prompt = system_prompt
        if correction is not None:
            prompt += (
                "\n\nCORRECTION_REQUIRED: The previous completed structured response "
                f"was rejected by PTW validation: {correction}. Return a corrected "
                "object that obeys that exact constraint."
            )
        request_document: dict[str, Any] = {
            "mode": mode,
            "system_prompt": prompt,
            "input_payload": dict(input_payload),
            "output_schema": dict(output_schema),
            "prompt_template_version": prompt_version,
            "context_hash": context_hash,
            "idempotency_key": f"{idempotency_key}:attempt:{attempt}",
        }
        if self.model != "codex-cli-default":
            request_document["model"] = self.model
        queued = self._request(self.url, request_document)
        request_id = int(queued["request_id"])
        result = self._await(request_id, deadline=time.monotonic() + self.timeout_seconds)
        if result.get("image") is not None:
            raise ValueError("structured JSON modes must not return generated media")
        response = self._response_object(result)
        invocation = {
            "bridge_request_id": request_id,
            "prompt_template_version": prompt_version,
            "context_hash": context_hash,
            "bridge_attempt": attempt,
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
