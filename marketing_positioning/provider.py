"""Authenticated structured bridge for Marketing Positioning synthesis."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping
import urllib.error
import urllib.request


POSITIONING_MODES = (
    "marketing_positioning_document",
    "marketing_positioning_revision",
)

EVIDENCE_STATEMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "minLength": 1, "maxLength": 2000},
        "source_ids": {"type": "array", "maxItems": 20, "items": {"type": "string", "format": "uuid"}},
        "assumption": {"type": "boolean"},
    },
    "required": ["text", "source_ids", "assumption"],
    "additionalProperties": False,
}

POSITIONING_DOCUMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "schema_version": {"const": 1},
        "output_language": {"type": "string", "enum": ["uk", "en"]},
        "positioning_foundation": {
            "type": "object",
            "properties": {
                "category": EVIDENCE_STATEMENT_SCHEMA,
                "competitive_alternatives": {"type": "array", "minItems": 1, "maxItems": 6, "items": EVIDENCE_STATEMENT_SCHEMA},
                "definitive_audience": EVIDENCE_STATEMENT_SCHEMA,
                "jobs": {"type": "array", "minItems": 1, "maxItems": 6, "items": EVIDENCE_STATEMENT_SCHEMA},
                "pains": {"type": "array", "minItems": 1, "maxItems": 6, "items": EVIDENCE_STATEMENT_SCHEMA},
                "gains": {"type": "array", "minItems": 1, "maxItems": 6, "items": EVIDENCE_STATEMENT_SCHEMA},
                "uvp": EVIDENCE_STATEMENT_SCHEMA,
            },
            "required": ["category", "competitive_alternatives", "definitive_audience", "jobs", "pains", "gains", "uvp"],
            "additionalProperties": False,
        },
        "messaging_matrix": {
            "type": "array", "minItems": 1, "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {key: EVIDENCE_STATEMENT_SCHEMA for key in ("feature", "functional_benefit", "emotional_reward")},
                "required": ["feature", "functional_benefit", "emotional_reward"],
                "additionalProperties": False,
            },
        },
        "landing_copy": {
            "type": "object",
            "properties": {
                "hero": {
                    "type": "object",
                    "properties": {key: EVIDENCE_STATEMENT_SCHEMA for key in ("eyebrow", "headline", "subheadline", "cta")},
                    "required": ["eyebrow", "headline", "subheadline", "cta"],
                    "additionalProperties": False,
                },
                "value_sections": {
                    "type": "array", "minItems": 3, "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {"title": EVIDENCE_STATEMENT_SCHEMA, "body": EVIDENCE_STATEMENT_SCHEMA},
                        "required": ["title", "body"], "additionalProperties": False,
                    },
                },
                "honest_limitation": EVIDENCE_STATEMENT_SCHEMA,
                "lead_capture_strategy": EVIDENCE_STATEMENT_SCHEMA,
            },
            "required": ["hero", "value_sections", "honest_limitation", "lead_capture_strategy"],
            "additionalProperties": False,
        },
        "ad_concepts": {
            "type": "array", "minItems": 2, "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["contextual_relatable", "direct_problem_solution"]},
                    "hook": EVIDENCE_STATEMENT_SCHEMA, "body": EVIDENCE_STATEMENT_SCHEMA,
                    "visual_direction": EVIDENCE_STATEMENT_SCHEMA,
                },
                "required": ["kind", "hook", "body", "visual_direction"], "additionalProperties": False,
            },
        },
        "aeo_faqs": {
            "type": "array", "minItems": 3, "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {key: EVIDENCE_STATEMENT_SCHEMA for key in ("question", "definition", "data", "context")},
                "required": ["question", "definition", "data", "context"], "additionalProperties": False,
            },
        },
        "evidence_references": {"type": "array", "minItems": 1, "maxItems": 50, "items": {"type": "string", "format": "uuid"}},
        "assumptions": {"type": "array", "maxItems": 30, "items": {"type": "string", "minLength": 1, "maxLength": 500}},
    },
    "required": ["schema_version", "output_language", "positioning_foundation", "messaging_matrix", "landing_copy", "ad_concepts", "aeo_faqs", "evidence_references", "assumptions"],
    "additionalProperties": False,
}

class BridgeProvider:
    def __init__(self, url: str, token: str, model: str, *, timeout_seconds: int = 420) -> None:
        if not url or not token:
            raise RuntimeError("the authenticated structured bridge is required")
        self.url = url.rstrip("/")
        self.token = token
        self.model = model or "codex-cli-default"
        self.timeout_seconds = timeout_seconds
        self.last_invocation: dict[str, Any] = {}
        self._prepared: dict[str, str] = {}

    def prepare_invocation(self, prompt_template_version: str, context_hash: str) -> None:
        self._prepared = {
            "prompt_template_version": prompt_template_version,
            "context_hash": context_hash,
        }

    def capabilities(self) -> dict[str, Any]:
        payload = self._request(f"{self.url}/capabilities", None, timeout=5)
        modes = payload.get("marketing_positioning_modes")
        landing = payload.get("landing_modes")
        maximum = payload.get("max_request_bytes")
        if (
            not isinstance(modes, list)
            or not all(isinstance(item, str) for item in modes)
            or not isinstance(landing, list)
            or not all(isinstance(item, str) for item in landing)
            or not isinstance(maximum, int)
        ):
            raise ValueError("structured bridge capabilities are invalid")
        missing = set(POSITIONING_MODES) - set(modes)
        if missing or "natal_landing_revision" not in landing:
            raise RuntimeError(f"structured bridge is missing required modes: {sorted(missing)}")
        return {
            "marketing_positioning_modes": sorted(set(modes)),
            "landing_modes": sorted(set(landing)),
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
        if mode not in POSITIONING_MODES:
            raise ValueError("unsupported Marketing Positioning bridge mode")
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

    def generate_structured(
        self,
        mode: str,
        system_prompt: str,
        input_payload: dict[str, Any],
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        if mode != "natal_landing_revision" and mode not in POSITIONING_MODES:
            raise ValueError("unsupported structured bridge mode")
        prompt_version = self._prepared.get("prompt_template_version", "structured_v1")
        context_hash = self._prepared.get("context_hash") or hashlib.sha256(
            json.dumps(input_payload, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()
        request: dict[str, Any] = {
            "mode": mode, "system_prompt": system_prompt,
            "input_payload": input_payload, "output_schema": output_schema,
            "prompt_template_version": prompt_version, "context_hash": context_hash,
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
                    "bridge_request_id": request_id, "prompt_template_version": prompt_version,
                    "context_hash": context_hash, **dict(result.get("invocation") or {}),
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
                result = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raw = error.read(4096).decode("utf-8", errors="replace")
            raise RuntimeError(f"structured bridge HTTP {error.code}: {raw[:500]}") from error
        if not isinstance(result, dict):
            raise ValueError("structured bridge returned invalid JSON")
        return result
