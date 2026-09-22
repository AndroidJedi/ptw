"""Authenticated structured bridge client for PTW Brief and Studio JSON modes."""

from __future__ import annotations

import hashlib
import base64
import json
import re
import threading
import time
from typing import Any, Callable, Mapping, Sequence
import urllib.error
import urllib.request


JSON_MODES = (
    "product_brief", "product_brief_revision", "studio_creative_generation",
    "studio_manual_edit", "creative_performance_learning", "creative_visual_analysis",
)
BRIDGE_JSON_MODES = JSON_MODES
OPTIONAL_TEMPLATE_MODE = "template_creation"
JSON_MODES = (*JSON_MODES, OPTIONAL_TEMPLATE_MODE)
BRIDGE_MEDIA_MODES = ("content_non_human_graphic_generation",)
BRIDGE_MULTIMODAL_MODES = ("creative_visual_analysis", "studio_manual_edit")
BRIDGE_IDEMPOTENCY_KEY_LIMIT = 240
BRIDGE_CONCURRENT_SLOT_LIMIT = 1
BRIDGE_STRUCTURED_CONTRACT_LIMIT_BYTES = 512_000
BRIDGE_INPUT_ARTIFACT_LIMIT_BYTES = 8_388_608
STRUCTURED_REASONING_EFFORTS = frozenset({"low", "medium", "high", "xhigh"})
TEMPLATE_CREATION_REASONING_EFFORT = "xhigh"
TEMPLATE_CORRECTION_RESERVE_BYTES = 3072
TEMPLATE_CORRECTION_KEY = "_ptw_validation_correction"
STRUCTURED_MODE_BUDGETS: dict[str, dict[str, int]] = {
    "template_creation": {
        # Leave room for the bounded second-attempt validation correction while
        # retaining the same 52 KiB total contract ceiling.
        "system_prompt": 6 * 1024, "input_payload": 40 * 1024,
        "output_schema": 8 * 1024, "total": 52 * 1024, "response": 20 * 1024,
    },
    "studio_manual_edit": {
        "system_prompt": 8 * 1024,
        "input_payload": 20 * 1024,
        "output_schema": 6 * 1024,
        "total": 32 * 1024,
        "response": 16 * 1024,
    },
    "studio_creative_generation": {
        "system_prompt": 8 * 1024,
        "input_payload": 20 * 1024,
        "output_schema": 12 * 1024,
        "total": 36 * 1024,
        "response": 16 * 1024,
    },
}


def _input_artifacts(
    value: Sequence[Mapping[str, Any]] | None, *, mode: str,
) -> tuple[list[dict[str, str]], dict[str, str], int]:
    if value is None:
        return [], {}, 0
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("structured input artifacts are invalid")
    if mode == "creative_visual_analysis" and len(value) != 1:
        raise ValueError("structured visual analysis requires exactly one input artifact")
    if mode == "studio_manual_edit" and not 1 <= len(value) <= 4:
        raise ValueError("Studio manual editing supports one to four screenshot artifacts")
    if mode == OPTIONAL_TEMPLATE_MODE and not 1 <= len(value) <= 4:
        raise ValueError("Template creation supports at most four artifacts")
    normalized: list[dict[str, str]] = []
    digests: dict[str, str] = {}
    total_bytes = 0
    for index, artifact in enumerate(value, start=1):
        if set(artifact) != {"name", "mime_type", "sha256", "bytes_base64"}:
            raise ValueError("structured input artifact fields are invalid")
        name = str(artifact["name"])
        mime_type = str(artifact["mime_type"])
        expected_digest = str(artifact["sha256"])
        expected_name = "approved_png" if mode == "creative_visual_analysis" else f"studio_screenshot_{index}"
        if mode == OPTIONAL_TEMPLATE_MODE:
            expected_name = f"template_image_{index}"
        if name != expected_name or mime_type != "image/png":
            raise ValueError("structured input artifact name or MIME type is invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise ValueError("structured input artifact digest is invalid")
        try:
            raw = base64.b64decode(str(artifact["bytes_base64"]), validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError("structured input artifact is not valid base64") from error
        if not raw or len(raw) > BRIDGE_INPUT_ARTIFACT_LIMIT_BYTES:
            raise ValueError("structured input artifact exceeds its bounded byte budget")
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("structured input artifact is not a PNG")
        actual_digest = hashlib.sha256(raw).hexdigest()
        if actual_digest != expected_digest:
            raise ValueError("structured input artifact digest does not match its bytes")
        normalized.append({
            "name": name, "mime_type": mime_type, "sha256": expected_digest,
            "bytes_base64": str(artifact["bytes_base64"]),
        })
        digests[name] = expected_digest
        total_bytes += len(raw)
    if total_bytes > 20 * 1024 * 1024:
        raise ValueError("structured input artifacts exceed their bounded byte budget")
    return normalized, digests, total_bytes


def _validation_error(error: Exception) -> str:
    message = " ".join(str(error).split())[:500] or type(error).__name__
    return re.sub(
        r"(?i)(token|secret|credential|password)\s*[:=]\s*\S+",
        r"\1=[redacted]", message,
    )


def _json_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
        ).encode()
    ).hexdigest()


def _structured_contract_bytes(
    *, system_prompt: str, input_payload: Mapping[str, Any],
    output_schema: Mapping[str, Any],
) -> dict[str, int]:
    parts = {
        "system_prompt": len(system_prompt.encode("utf-8")),
        "input_payload": len(json.dumps(
            input_payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str,
        ).encode("utf-8")),
        "output_schema": len(json.dumps(
            output_schema, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str,
        ).encode("utf-8")),
    }
    return {**parts, "total": sum(parts.values())}


def enforce_structured_contract_budget(
    *, mode: str, system_prompt: str, input_payload: Mapping[str, Any],
    output_schema: Mapping[str, Any],
) -> dict[str, int]:
    """Apply small per-mode budgets before a provider job is queued."""

    contract_bytes = _structured_contract_bytes(
        system_prompt=system_prompt, input_payload=input_payload,
        output_schema=output_schema,
    )
    if contract_bytes["total"] > BRIDGE_STRUCTURED_CONTRACT_LIMIT_BYTES:
        raise ValueError("structured provider contract exceeds its safe byte budget")
    budget = STRUCTURED_MODE_BUDGETS.get(mode)
    if budget is not None:
        for part in ("system_prompt", "input_payload", "output_schema", "total"):
            if contract_bytes[part] > budget[part]:
                raise ValueError(
                    f"{mode} {part.replace('_', ' ')} exceeds its compact byte budget"
                )
        if mode == OPTIONAL_TEMPLATE_MODE and TEMPLATE_CORRECTION_KEY not in input_payload:
            if any(
                budget[part] - contract_bytes[part] < TEMPLATE_CORRECTION_RESERVE_BYTES
                for part in ("input_payload", "total")
            ):
                raise ValueError("template_creation contract leaves no corrective attempt budget")
    return contract_bytes


def enforce_structured_response_budget(mode: str, value: Mapping[str, Any]) -> int:
    size = len(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8"))
    budget = STRUCTURED_MODE_BUDGETS.get(mode)
    if budget is not None and size > budget["response"]:
        raise ValueError(f"{mode} response exceeds its compact byte budget")
    return size


def bridge_request_fingerprint(
    *, mode: str, system_prompt: str, input_payload: Mapping[str, Any],
    output_schema: Mapping[str, Any], prompt_version: str, model: str,
    input_artifact_digests: Mapping[str, str] | None = None,
    reasoning_effort: str | None = None,
) -> str:
    """Bind provider idempotency to every semantic request dependency."""

    return _json_digest({
        "schema": "ptw.bridge-request-fingerprint.v2",
        "mode": mode,
        "model": model or "codex-cli-default",
        "reasoning_effort": reasoning_effort or "provider-default",
        "prompt_version": prompt_version,
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "input_payload_sha256": _json_digest(input_payload),
        "output_schema_sha256": _json_digest(output_schema),
        "input_artifact_digests": dict(sorted((input_artifact_digests or {}).items())),
    })


def bridge_idempotency_key(base_key: str, request_fingerprint: str, attempt: int) -> str:
    """Create one printable, collision-resistant bridge key within its hard limit."""

    if (
        not isinstance(base_key, str) or not base_key
        or any(ord(character) < 33 or ord(character) > 126 for character in base_key)
    ):
        raise ValueError("structured bridge idempotency base key is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", request_fingerprint):
        raise ValueError("structured bridge request fingerprint is invalid")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("structured bridge attempt is invalid")
    suffix = f":request:{request_fingerprint}:attempt:{attempt}"
    available = BRIDGE_IDEMPOTENCY_KEY_LIMIT - len(suffix)
    if available < 18:
        raise RuntimeError("structured bridge idempotency suffix exceeds its contract")
    if len(base_key) > available:
        digest = hashlib.sha256(base_key.encode()).hexdigest()[:16]
        base_key = f"{base_key[:available - 17]}:{digest}"
    return base_key + suffix


class StructuredBridge:
    def __init__(self, url: str, token: str, model: str, *, timeout_seconds: int = 420) -> None:
        if not url or not token:
            raise RuntimeError("the authenticated structured bridge is required")
        self.url = url.rstrip("/")
        self.token = token
        self.model = model or "codex-cli-default"
        self.timeout_seconds = timeout_seconds
        self.last_invocation: dict[str, Any] = {}
        # Production currently has one bounded worker. Serializing here prevents
        # a second request from spending its client deadline waiting in that queue.
        self._slots = threading.BoundedSemaphore(BRIDGE_CONCURRENT_SLOT_LIMIT)

    def capabilities(self) -> dict[str, Any]:
        value = self._request(f"{self.url}/capabilities", None, timeout=5)
        json_modes = value.get("json_modes")
        media_modes = value.get("media_modes")
        multimodal_modes = value.get("multimodal_modes")
        maximum = value.get("max_request_bytes")
        reasoning_efforts = value.get("reasoning_efforts", {})
        if (
            not isinstance(json_modes, list)
            or not all(isinstance(item, str) for item in json_modes)
            or not isinstance(media_modes, list)
            or not all(isinstance(item, str) for item in media_modes)
            or not isinstance(multimodal_modes, list)
            or not all(isinstance(item, str) for item in multimodal_modes)
            or not isinstance(maximum, int)
            or not isinstance(reasoning_efforts, dict)
            or not all(
                isinstance(key, str) and isinstance(effort, str)
                for key, effort in reasoning_efforts.items()
            )
        ):
            raise ValueError("structured bridge capabilities are invalid")
        if not set(BRIDGE_JSON_MODES) <= set(json_modes) <= set(JSON_MODES) or len(json_modes) != len(set(json_modes)):
            raise RuntimeError("structured bridge JSON modes do not match the deployed provider contract")
        if set(media_modes) != set(BRIDGE_MEDIA_MODES) or len(media_modes) != len(BRIDGE_MEDIA_MODES):
            raise RuntimeError("structured bridge media modes do not match the deployed provider contract")
        if not set(BRIDGE_MULTIMODAL_MODES) <= set(multimodal_modes) <= {*BRIDGE_MULTIMODAL_MODES, OPTIONAL_TEMPLATE_MODE} or len(multimodal_modes) != len(set(multimodal_modes)):
            raise RuntimeError("structured bridge multimodal modes do not match the deployed provider contract")
        if OPTIONAL_TEMPLATE_MODE in set(json_modes) | set(multimodal_modes):
            if reasoning_efforts.get(OPTIONAL_TEMPLATE_MODE) != TEMPLATE_CREATION_REASONING_EFFORT:
                raise RuntimeError("Template creation requires explicit xhigh bridge support")
        return {
            "json_modes": sorted(json_modes),
            "media_modes": sorted(media_modes),
            "multimodal_modes": sorted(multimodal_modes),
            "max_request_bytes": maximum,
            "reasoning_efforts": dict(sorted(reasoning_efforts.items())),
        }

    def generate(
        self, *, mode: str, system_prompt: str, input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any], prompt_version: str,
        idempotency_key: str,
        response_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        input_artifacts: Sequence[Mapping[str, Any]] | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        return self.call(
            mode=mode, system_prompt=system_prompt, input_payload=input_payload,
            output_schema=output_schema, prompt_version=prompt_version,
            idempotency_key=idempotency_key, response_validator=response_validator,
            input_artifacts=input_artifacts,
            reasoning_effort=reasoning_effort,
        )

    def call(
        self, *, mode: str, system_prompt: str, input_payload: Mapping[str, Any],
        output_schema: Mapping[str, Any], prompt_version: str,
        idempotency_key: str,
        response_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        input_artifacts: Sequence[Mapping[str, Any]] | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        """Validate a completed response and make at most one fresh correction.

        Transport, timeout, and provider failures keep their original attempt key
        and are never converted into an uncertain second mutation. A second bridge
        job is created only after PTW has received a completed JSON object and its
        deterministic domain validator has rejected that object.
        """

        if not callable(response_validator):
            raise ValueError("structured bridge calls require a domain response validator")
        if mode not in JSON_MODES:
            raise ValueError("unsupported structured bridge mode")
        if reasoning_effort is not None and reasoning_effort not in STRUCTURED_REASONING_EFFORTS:
            raise ValueError("structured bridge reasoning effort is invalid")
        if mode == OPTIONAL_TEMPLATE_MODE:
            if reasoning_effort != TEMPLATE_CREATION_REASONING_EFFORT:
                raise ValueError("Template creation requires xhigh reasoning effort")
            capabilities = self.capabilities()
            if mode not in capabilities.get("json_modes", []) or mode not in capabilities.get("multimodal_modes", []):
                raise RuntimeError("Template creation is not advertised by the structured bridge")
        artifacts, artifact_digests, artifact_bytes = _input_artifacts(
            input_artifacts, mode=mode,
        )
        if artifacts and mode not in (*BRIDGE_MULTIMODAL_MODES, OPTIONAL_TEMPLATE_MODE):
            raise ValueError("structured input artifacts are not allowed for this mode")
        if mode == "creative_visual_analysis" and not artifacts:
            raise ValueError("structured visual analysis requires an approved PNG")
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
                    input_artifacts=artifacts,
                    input_artifact_digests=artifact_digests,
                    input_artifact_bytes=artifact_bytes,
                    reasoning_effort=reasoning_effort,
                )
                try:
                    response_bytes = enforce_structured_response_budget(mode, result["response"])
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
                        "response_bytes": response_bytes,
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
        input_artifacts: Sequence[Mapping[str, str]] = (),
        input_artifact_digests: Mapping[str, str] | None = None,
        input_artifact_bytes: int = 0,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        request_payload = dict(input_payload)
        if correction is not None and mode == OPTIONAL_TEMPLATE_MODE:
            # Keep the canonical skill inside its 6 KiB prompt budget. The
            # first attempt reserves room in the input contract for this hint.
            request_payload[TEMPLATE_CORRECTION_KEY] = (
                "The previous completed structured response was rejected by PTW "
                f"validation: {correction}. Return a corrected object that obeys "
                "that exact constraint."
            )
        context_hash = self._digest(request_payload)
        request_fingerprint = bridge_request_fingerprint(
            mode=mode, system_prompt=system_prompt, input_payload=request_payload,
            output_schema=output_schema, prompt_version=prompt_version,
            model=self.model,
            input_artifact_digests=input_artifact_digests,
            reasoning_effort=reasoning_effort,
        )
        prompt = system_prompt
        if correction is not None and mode != OPTIONAL_TEMPLATE_MODE:
            prompt += (
                "\n\nCORRECTION_REQUIRED: The previous completed structured response "
                f"was rejected by PTW validation: {correction}. Return a corrected "
                "object that obeys that exact constraint."
            )
        contract_bytes = enforce_structured_contract_budget(
            mode=mode,
            system_prompt=prompt, input_payload=request_payload,
            output_schema=output_schema,
        )
        request_document: dict[str, Any] = {
            "mode": mode,
            "system_prompt": prompt,
            "input_payload": request_payload,
            "output_schema": dict(output_schema),
            "prompt_template_version": prompt_version,
            "context_hash": context_hash,
            "idempotency_key": bridge_idempotency_key(
                idempotency_key, request_fingerprint, attempt,
            ),
        }
        if input_artifacts:
            request_document["input_artifacts"] = list(input_artifacts)
        if self.model != "codex-cli-default":
            request_document["model"] = self.model
        if reasoning_effort is not None:
            request_document["reasoning_effort"] = reasoning_effort
        queued = self._request(self.url, request_document)
        request_id = int(queued["request_id"])
        result = self._await(request_id, deadline=time.monotonic() + self.timeout_seconds)
        if result.get("image") is not None:
            raise ValueError("structured JSON modes must not return generated media")
        response = self._response_object(result)
        invocation = {
            **dict(result.get("invocation") or {}),
            "bridge_request_id": request_id,
            "prompt_template_version": prompt_version,
            "context_hash": context_hash,
            "request_fingerprint": request_fingerprint,
            "bridge_attempt": attempt,
            "contract_bytes": contract_bytes,
            "input_artifacts": dict(input_artifact_digests or {}),
            "input_artifact_bytes": input_artifact_bytes,
            "model": self.model,
            "reasoning_effort": reasoning_effort or "provider-default",
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
            error.read(4096)
            raise RuntimeError(f"structured bridge HTTP {error.code}") from error
        except urllib.error.URLError as error:
            raise ConnectionError("structured bridge connection failed") from error
        if not isinstance(value, dict):
            raise ValueError("structured bridge returned invalid JSON")
        return value
