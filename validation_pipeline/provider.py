"""Authenticated bridge client for Product Brief and Result generation only."""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID


JSON_MODES = (
    "product_brief",
    "product_brief_revision",
    "content_candidate_generation",
    "content_result_critic",
)
MEDIA_MODES = ("content_non_human_graphic_generation",)
MAX_GRAPHIC_BYTES = 10 * 1024 * 1024
MAX_CRITIC_IMAGE_BYTES = 1_500_000
MAX_CRITIC_TOTAL_IMAGE_BYTES = 8 * 1024 * 1024


class StructuredBridge:
    def __init__(self, url: str, token: str, model: str, *, timeout_seconds: int = 420) -> None:
        if not url or not token:
            raise RuntimeError("the authenticated structured bridge is required")
        self.url = url.rstrip("/")
        self.token = token
        self.model = model or "codex-cli-default"
        self.timeout_seconds = timeout_seconds
        self.last_invocation: dict[str, Any] = {}
        self._json_slots = threading.BoundedSemaphore(2)
        self._critic_slots = threading.BoundedSemaphore(1)
        self._media_slots = threading.BoundedSemaphore(1)

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
            raise RuntimeError("structured bridge JSON modes do not match the Result-only contract")
        if set(media_modes) != set(MEDIA_MODES) or len(media_modes) != len(MEDIA_MODES):
            raise RuntimeError("structured bridge media modes do not match the Result-only contract")
        return {
            "json_modes": sorted(json_modes),
            "media_modes": sorted(media_modes),
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
        idempotency_key: str,
    ) -> dict[str, Any]:
        if mode not in {"product_brief", "product_brief_revision"}:
            raise ValueError("unsupported Product Brief bridge mode")
        value = self._json_call(
            mode=mode,
            system_prompt=system_prompt,
            input_payload=input_payload,
            output_schema=output_schema,
            prompt_version=prompt_version,
            input_images=None,
            maximum_attempts=1,
            idempotency_key=idempotency_key,
        )
        self.last_invocation = dict(value["invocation"])
        return {
            "response": dict(value["response"]),
            "invocation": dict(value["invocation"]),
        }

    def generate_content_candidate(
        self,
        *,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        idempotency_key: str,
        prompt_version: str = "ptw-content-candidate-v2",
    ) -> dict[str, Any]:
        return self._json_call(
            mode="content_candidate_generation",
            system_prompt=system_prompt,
            input_payload=input_payload,
            output_schema=output_schema,
            prompt_version=prompt_version,
            input_images=None,
            maximum_attempts=2,
            idempotency_key=idempotency_key,
        )

    def generate_content_critic(
        self,
        *,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        images: list[Mapping[str, Any]],
        output_schema: Mapping[str, Any],
        idempotency_key: str,
        prompt_version: str = "ptw-content-result-critic-v1",
    ) -> dict[str, Any]:
        if not 1 <= len(images) <= 5:
            raise ValueError("Result critic requires one to five mapped JPEG attachments")
        encoded: list[dict[str, Any]] = []
        total = 0
        seen: set[str] = set()
        for item in images:
            if set(item) != {"candidate_id", "bytes", "sha256", "width", "height"}:
                raise ValueError("Result critic image mapping fields do not match v1")
            candidate_id = str(UUID(str(item["candidate_id"])))
            if candidate_id in seen:
                raise ValueError("Result critic candidate mappings must be unique")
            seen.add(candidate_id)
            data = bytes(item["bytes"])
            digest = hashlib.sha256(data).hexdigest()
            if (
                not data.startswith(b"\xff\xd8")
                or not data.endswith(b"\xff\xd9")
                or not 1 <= len(data) <= MAX_CRITIC_IMAGE_BYTES
                or digest != str(item["sha256"])
                or int(item["width"]) != 1080
                or int(item["height"]) != 1080
            ):
                raise ValueError("Result critic attachment is not an exact bounded 1080x1080 JPEG")
            total += len(data)
            encoded.append({
                "candidate_id": candidate_id,
                "mime_type": "image/jpeg",
                "digest": digest,
                "width": 1080,
                "height": 1080,
                "bytes_base64": base64.b64encode(data).decode("ascii"),
            })
        if total > MAX_CRITIC_TOTAL_IMAGE_BYTES:
            raise ValueError("Result critic attachments exceed the eight MB aggregate limit")
        return self._json_call(
            mode="content_result_critic",
            system_prompt=system_prompt,
            input_payload=input_payload,
            output_schema=output_schema,
            prompt_version=prompt_version,
            input_images=encoded,
            maximum_attempts=2,
            idempotency_key=idempotency_key,
        )

    def generate_non_human_graphic(
        self,
        *,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        idempotency_key: str,
        prompt_version: str = "ptw-content-non-human-graphic-v1",
    ) -> dict[str, Any]:
        """Generate once. Any ambiguous outcome fails closed and is never retried."""
        context_hash = self._digest(input_payload)
        request = self._request_document(
            mode="content_non_human_graphic_generation",
            system_prompt=system_prompt,
            input_payload=input_payload,
            output_schema=output_schema,
            prompt_version=prompt_version,
            context_hash=context_hash,
            idempotency_key=f"{idempotency_key}:attempt:1",
        )
        deadline = time.monotonic() + self.timeout_seconds
        if not self._media_slots.acquire(timeout=max(0, self.timeout_seconds)):
            raise TimeoutError("non-human graphic call could not enter its bounded execution slot")
        try:
            queued = self._request(self.url, request)
            request_id = int(queued["request_id"])
            result = self._await(request_id, deadline=deadline)
        finally:
            self._media_slots.release()
        response = self._response_object(result)
        image = result.get("image")
        if not isinstance(image, Mapping):
            raise ValueError("non-human graphic response is missing image provenance")
        invocation = {
            "bridge_request_id": request_id,
            "prompt_template_version": prompt_version,
            "context_hash": context_hash,
            "bridge_attempt": 1,
            "prior_failed_request_ids": [],
            **dict(result.get("invocation") or {}),
        }
        self.last_invocation = invocation
        return {
            "response": response,
            "invocation": invocation,
            "image": {**dict(image), **self._download_graphic(request_id, image)},
        }

    def _json_call(
        self,
        *,
        mode: str,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
        input_images: list[Mapping[str, Any]] | None,
        maximum_attempts: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        slot = self._critic_slots if mode == "content_result_critic" else self._json_slots
        if not slot.acquire(timeout=max(0, self.timeout_seconds)):
            raise TimeoutError(f"{mode} could not enter its bounded execution slot")
        try:
            return self._json_call_unlocked(
                mode=mode,
                system_prompt=system_prompt,
                input_payload=input_payload,
                output_schema=output_schema,
                prompt_version=prompt_version,
                input_images=input_images,
                maximum_attempts=maximum_attempts,
                idempotency_key=idempotency_key,
            )
        finally:
            slot.release()

    def _json_call_unlocked(
        self,
        *,
        mode: str,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
        input_images: list[Mapping[str, Any]] | None,
        maximum_attempts: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if mode not in JSON_MODES:
            raise ValueError("unsupported Result-only JSON bridge mode")
        if mode == "content_candidate_generation" and input_images:
            raise ValueError("Result candidate generation is JSON-only")
        if mode == "content_result_critic" and not input_images:
            raise ValueError("Result critic requires mapped render attachments")
        context_hash = self._digest(input_payload)
        deadline = time.monotonic() + self.timeout_seconds
        failed_request_ids: list[int] = []
        for attempt in range(1, maximum_attempts + 1):
            if time.monotonic() >= deadline:
                raise TimeoutError("Result call exceeded its original deadline")
            request = self._request_document(
                mode=mode,
                system_prompt=system_prompt,
                input_payload=input_payload,
                output_schema=output_schema,
                prompt_version=prompt_version,
                context_hash=context_hash,
                idempotency_key=f"{idempotency_key}:attempt:{attempt}",
            )
            if input_images is not None:
                request["input_images"] = [dict(item) for item in input_images]
            queued = self._request(self.url, request)
            request_id = int(queued["request_id"])
            try:
                result = self._await(request_id, deadline=deadline)
                if result.get("image") is not None:
                    raise ValueError("JSON generation modes must not return generated media")
                response = self._response_object(result)
            except (RuntimeError, ValueError, json.JSONDecodeError):
                failed_request_ids.append(request_id)
                if attempt < maximum_attempts:
                    continue
                raise RuntimeError(f"{mode} failed after {maximum_attempts} JSON attempts")
            invocation = {
                "bridge_request_id": request_id,
                "prompt_template_version": prompt_version,
                "context_hash": context_hash,
                "bridge_attempt": attempt,
                "prior_failed_request_ids": failed_request_ids,
                **dict(result.get("invocation") or {}),
            }
            self.last_invocation = invocation
            return {"response": response, "invocation": invocation}
        raise RuntimeError("Result JSON call did not complete")

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

    def _request_document(
        self,
        *,
        mode: str,
        system_prompt: str,
        input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
        context_hash: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "mode": mode,
            "system_prompt": system_prompt,
            "input_payload": dict(input_payload),
            "output_schema": dict(output_schema),
            "prompt_template_version": prompt_version,
            "context_hash": context_hash,
            "idempotency_key": idempotency_key,
        }
        if self.model != "codex-cli-default":
            request["model"] = self.model
        return request

    @staticmethod
    def _digest(value: Mapping[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()

    def _download_graphic(self, job_id: int, image: Mapping[str, Any]) -> dict[str, Any]:
        digest = str(image.get("digest") or "")
        if not digest or digest != str(image.get("output_digest") or ""):
            raise ValueError("generated graphic digests are missing or inconsistent")
        if str(image.get("mime_type") or "") != "image/png":
            raise ValueError("generated graphic must be a PNG")
        width, height = int(image.get("width") or 0), int(image.get("height") or 0)
        if width != height or not 512 <= width <= 2048:
            raise ValueError("generated graphic dimensions are outside the square contract")
        policy = image.get("generation_policy")
        if not isinstance(policy, Mapping) or policy.get("non_human_graphics_only") is not True:
            raise ValueError("generated graphic is missing its non-human policy")
        if any(policy.get(key) != "prohibited" for key in (
            "synthetic_people", "embedded_text", "embedded_logos", "watermarks",
        )):
            raise ValueError("generated graphic policy does not prohibit unsafe content")
        expected_path = f"/internal/llm/structured/{job_id}/asset"
        if str(image.get("asset_url") or "") != expected_path:
            raise ValueError("generated graphic asset URL is outside its authenticated job")
        parsed = urllib.parse.urlsplit(self.url)
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, expected_path, "", ""))
        request = urllib.request.Request(
            url, headers={"X-PTW-Bridge-Token": self.token, "User-Agent": "PTW-Result/1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
                etag = str(response.headers.get("ETag") or "")
                data = response.read(MAX_GRAPHIC_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"structured bridge asset HTTP {error.code}") from error
        if content_type != "image/png" or etag != f'"{digest}"':
            raise ValueError("generated graphic asset headers do not match provenance")
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > MAX_GRAPHIC_BYTES:
            raise ValueError("generated graphic bytes are invalid or oversized")
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("generated graphic digest does not match its bytes")
        return {"bytes": data, "bytes_sha256": digest}

    def _request(
        self, url: str, payload: Mapping[str, Any] | None, *, timeout: int = 30
    ) -> dict[str, Any]:
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
