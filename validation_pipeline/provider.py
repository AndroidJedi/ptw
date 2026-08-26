"""Authenticated structured bridge client for validation generation."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request


VALIDATION_MODES = ("product_brief", "product_brief_revision", "ad_creative_batch")
STUDIO_MODES = (
    "ad_studio_graphic_generation",
    "ad_studio_recipe_revision",
    "ad_studio_creative_validation",
)
RETRYABLE_STUDIO_MODES = {
    "ad_studio_recipe_revision",
    "ad_studio_creative_validation",
}
MAX_STUDIO_ASSET_BYTES = 10 * 1024 * 1024
MAX_STUDIO_VALIDATION_IMAGE_BYTES = 2 * 1024 * 1024


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
        studio_modes = value.get("studio_modes")
        maximum = value.get("max_request_bytes")
        if (
            not isinstance(modes, list) or not all(isinstance(item, str) for item in modes)
            or not isinstance(studio_modes, list) or not all(isinstance(item, str) for item in studio_modes)
            or not isinstance(maximum, int)
        ):
            raise ValueError("structured bridge capabilities are invalid")
        expected = set(VALIDATION_MODES)
        actual = set(modes)
        if actual != expected or len(modes) != len(VALIDATION_MODES):
            raise RuntimeError(
                "structured bridge validation modes do not match; "
                f"missing={sorted(expected - actual)} unexpected={sorted(actual - expected)}"
            )
        if set(studio_modes) != set(STUDIO_MODES) or len(studio_modes) != len(STUDIO_MODES):
            raise RuntimeError("structured bridge Studio modes do not match the supported contract")
        return {
            "validation_modes": sorted(actual), "studio_modes": sorted(set(studio_modes)),
            "max_request_bytes": maximum,
        }

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

    def generate_studio_recipe_revision(
        self,
        *,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str = "ptw-ad-studio-recipe-revision-v1",
    ) -> dict[str, Any]:
        return self._generate_studio(
            mode="ad_studio_recipe_revision", system_prompt=system_prompt,
            input_payload=input_payload, output_schema=output_schema,
            prompt_version=prompt_version, expect_image=False,
        )

    def generate_studio_graphic(
        self,
        *,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str = "ptw-ad-studio-graphic-v1",
    ) -> dict[str, Any]:
        return self._generate_studio(
            mode="ad_studio_graphic_generation", system_prompt=system_prompt,
            input_payload=input_payload, output_schema=output_schema,
            prompt_version=prompt_version, expect_image=True,
        )

    def validate_studio_creative(
        self,
        *,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        image_bytes: bytes,
        image_sha256: str,
        output_schema: Mapping[str, Any],
        prompt_version: str = "ptw-ad-studio-creative-validation-v1",
    ) -> dict[str, Any]:
        data = bytes(image_bytes)
        digest = hashlib.sha256(data).hexdigest()
        if (
            not data.startswith(b"\xff\xd8")
            or not data.endswith(b"\xff\xd9")
            or not 1 <= len(data) <= MAX_STUDIO_VALIDATION_IMAGE_BYTES
            or digest != image_sha256
        ):
            raise ValueError("Studio creative validation image is not an exact bounded JPEG")
        return self._generate_studio(
            mode="ad_studio_creative_validation",
            system_prompt=system_prompt,
            input_payload=input_payload,
            output_schema=output_schema,
            prompt_version=prompt_version,
            expect_image=False,
            input_image={
                "mime_type": "image/jpeg",
                "digest": digest,
                "width": 1080,
                "height": 1080,
                "bytes_base64": base64.b64encode(data).decode("ascii"),
            },
        )

    def _generate_studio(
        self,
        *,
        mode: str,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
        expect_image: bool,
        input_image: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if mode not in STUDIO_MODES:
            raise ValueError("unsupported Studio bridge mode")
        context_hash = hashlib.sha256(
            json.dumps(input_payload, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()
        request: dict[str, Any] = {
            "mode": mode, "system_prompt": system_prompt,
            "input_payload": dict(input_payload), "output_schema": dict(output_schema),
            "prompt_template_version": prompt_version, "context_hash": context_hash,
        }
        if input_image is not None:
            request["input_image"] = dict(input_image)
        if self.model != "codex-cli-default":
            request["model"] = self.model
        deadline = time.monotonic() + self.timeout_seconds
        maximum_attempts = 2 if mode in RETRYABLE_STUDIO_MODES else 1
        failed_request_ids: list[int] = []
        for attempt in range(1, maximum_attempts + 1):
            if time.monotonic() >= deadline:
                raise TimeoutError("Automatic Studio work timed out. Try the Wizard again.")
            queued = self._request(self.url, request)
            request_id = int(queued["request_id"])
            while time.monotonic() < deadline:
                state = self._request(f"{self.url}/{request_id}", None)
                status = state.get("status")
                if status == "completed":
                    result = state.get("result") or {}
                    response = result.get("response")
                    decoded = json.loads(response) if isinstance(response, str) else response
                    if not isinstance(decoded, dict):
                        raise ValueError("structured Studio response is not one JSON object")
                    invocation = {
                        "bridge_request_id": request_id, "prompt_template_version": prompt_version,
                        "context_hash": context_hash, "bridge_attempt": attempt,
                        "prior_failed_request_ids": failed_request_ids,
                        **dict(result.get("invocation") or {}),
                    }
                    self.last_invocation = invocation
                    value: dict[str, Any] = {"response": decoded, "invocation": invocation}
                    image = result.get("image")
                    if expect_image:
                        if not isinstance(image, Mapping):
                            raise ValueError("Studio graphic response is missing image provenance")
                        value["image"] = {**dict(image), **self._download_studio_asset(request_id, image)}
                    elif image is not None:
                        raise ValueError("Studio recipe revision must not return generated media")
                    return value
                if status == "failed":
                    failed_request_ids.append(request_id)
                    break
                if status == "cancelled":
                    raise RuntimeError("Automatic Studio work was cancelled. Try the Wizard again.")
                time.sleep(1)
            else:
                raise TimeoutError("Automatic Studio work timed out. Try the Wizard again.")
            if attempt == maximum_attempts:
                labels = {
                    "ad_studio_creative_validation": "Automatic creative review",
                    "ad_studio_recipe_revision": "Studio change",
                    "ad_studio_graphic_generation": "Studio graphic generation",
                }
                attempt_label = "attempt" if maximum_attempts == 1 else "attempts"
                raise RuntimeError(
                    f"{labels[mode]} could not finish after {maximum_attempts} {attempt_label}. "
                    "Try the Wizard again."
                )
        raise RuntimeError("Automatic Studio work did not complete")

    def _download_studio_asset(self, job_id: int, image: Mapping[str, Any]) -> dict[str, Any]:
        digest = str(image.get("digest") or "")
        if not digest or digest != str(image.get("output_digest") or ""):
            raise ValueError("Studio graphic digests are missing or inconsistent")
        if str(image.get("mime_type") or "") != "image/png":
            raise ValueError("Studio graphic must be a PNG")
        width, height = int(image.get("width") or 0), int(image.get("height") or 0)
        if width != height or not 512 <= width <= 2048:
            raise ValueError("Studio graphic dimensions are outside the square contract")
        policy = image.get("generation_policy")
        if not isinstance(policy, Mapping) or policy.get("non_human_graphics_only") is not True:
            raise ValueError("Studio graphic is missing the non-human generation policy")
        if any(policy.get(key) != "prohibited" for key in (
            "synthetic_people", "embedded_text", "embedded_logos", "watermarks",
        )):
            raise ValueError("Studio graphic policy does not prohibit unsafe generated content")
        expected_path = f"/internal/llm/structured/{job_id}/asset"
        if str(image.get("asset_url") or "") != expected_path:
            raise ValueError("Studio graphic asset URL is outside the authenticated job")
        parsed = urllib.parse.urlsplit(self.url)
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, expected_path, "", ""))
        request = urllib.request.Request(
            url, headers={"X-PTW-Bridge-Token": self.token, "User-Agent": "PTW-Validation/1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
                etag = str(response.headers.get("ETag") or "")
                data = response.read(MAX_STUDIO_ASSET_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"structured bridge asset HTTP {error.code}") from error
        if content_type != "image/png" or etag != f'"{digest}"':
            raise ValueError("Studio graphic asset headers do not match its provenance")
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > MAX_STUDIO_ASSET_BYTES:
            raise ValueError("Studio graphic asset bytes are invalid or oversized")
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Studio graphic asset digest does not match its exact bytes")
        return {"bytes": data, "bytes_sha256": digest}

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
