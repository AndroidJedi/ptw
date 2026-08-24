"""Authenticated structured bridge client for validation generation."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping
import urllib.error
import urllib.request


VALIDATION_MODES = ("product_brief", "product_brief_revision", "ad_creative_batch")


class StructuredBridge:
    def __init__(self, url: str, token: str, model: str, *, timeout_seconds: int = 420) -> None:
        if not url or not token:
            raise RuntimeError("the authenticated structured bridge is required")
        self.url = url.rstrip("/")
        self.token = token
        self.model = model or "codex-cli-default"
        self.timeout_seconds = timeout_seconds
        self.last_invocation: dict[str, Any] = {}

    def capabilities(self) -> dict[str, Any]:
        value = self._request(f"{self.url}/capabilities", None, timeout=5)
        modes = value.get("validation_modes")
        maximum = value.get("max_request_bytes")
        if not isinstance(modes, list) or not all(isinstance(item, str) for item in modes) or not isinstance(maximum, int):
            raise ValueError("structured bridge capabilities are invalid")
        expected = set(VALIDATION_MODES)
        actual = set(modes)
        if actual != expected or len(modes) != len(VALIDATION_MODES):
            raise RuntimeError(
                "structured bridge validation modes do not match; "
                f"missing={sorted(expected - actual)} unexpected={sorted(actual - expected)}"
            )
        return {"validation_modes": sorted(actual), "max_request_bytes": maximum}

    def generate(
        self,
        *,
        mode: str,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
    ) -> dict[str, Any]:
        if mode not in VALIDATION_MODES:
            raise ValueError("unsupported validation bridge mode")
        context_hash = hashlib.sha256(
            json.dumps(input_payload, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()
        request: dict[str, Any] = {
            "mode": mode,
            "system_prompt": system_prompt,
            "input_payload": dict(input_payload),
            "output_schema": dict(output_schema),
            "prompt_template_version": prompt_version,
            "context_hash": context_hash,
        }
        if self.model != "codex-cli-default":
            request["model"] = self.model
        queued = self._request(self.url, request)
        request_id = int(queued["request_id"])
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            state = self._request(f"{self.url}/{request_id}", None)
            if state.get("status") == "completed":
                result = state.get("result") or {}
                response = result.get("response")
                decoded = json.loads(response) if isinstance(response, str) else response
                if not isinstance(decoded, dict):
                    raise ValueError("structured bridge response is not one JSON object")
                self.last_invocation = {
                    "bridge_request_id": request_id,
                    "prompt_template_version": prompt_version,
                    "context_hash": context_hash,
                    **dict(result.get("invocation") or {}),
                }
                return decoded
            if state.get("status") in {"failed", "cancelled"}:
                raise RuntimeError(f"structured bridge request {request_id} {state.get('status')}")
            time.sleep(1)
        raise TimeoutError(f"structured bridge request {request_id} timed out")

    def _request(self, url: str, payload: Mapping[str, Any] | None, *, timeout: int = 30) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, default=str).encode()
        request = urllib.request.Request(
            url,
            data=body,
            headers={"X-PTW-Bridge-Token": self.token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                value = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raw = error.read(4096).decode("utf-8", errors="replace")
            raise RuntimeError(f"structured bridge HTTP {error.code}: {raw[:500]}") from error
        if not isinstance(value, dict):
            raise ValueError("structured bridge returned invalid JSON")
        return value
