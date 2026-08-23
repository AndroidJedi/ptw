"""Authenticated bridge, paid research, and safe-page provider adapters."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import math
import re
import socket
import time
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin, urlsplit
import urllib.error
import urllib.request


POSITIONING_MODES = (
    "marketing_positioning_research_plan",
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

RESEARCH_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "queries": {
            "type": "array", "minItems": 2, "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "enum": ["alternatives", "jobs_pains_gains", "category_language", "limitations"]},
                    "query": {"type": "string", "minLength": 2, "maxLength": 200},
                },
                "required": ["intent", "query"], "additionalProperties": False,
            },
        }
    },
    "required": ["queries"], "additionalProperties": False,
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


class DataForSEOProvider:
    name = "dataforseo"
    task_post_endpoint = "https://api.dataforseo.com/v3/serp/google/organic/task_post"
    task_get_endpoint = "https://api.dataforseo.com/v3/serp/google/organic/task_get/advanced"
    cost_per_ten = 0.0006
    locations = {
        "US": "United States", "GB": "United Kingdom", "CA": "Canada",
        "AU": "Australia", "DE": "Germany", "FR": "France", "ES": "Spain",
        "IT": "Italy", "PL": "Poland", "UA": "Ukraine", "NO": "Norway",
        "DK": "Denmark", "SE": "Sweden", "NL": "Netherlands",
    }

    def __init__(self, login: str, password: str, *, poll_timeout_seconds: int = 900) -> None:
        if not login or not password:
            raise RuntimeError("verified DataForSEO credentials are required")
        self.auth = (login, password)
        self.poll_timeout_seconds = poll_timeout_seconds

    def estimate_cost(self, depth: int) -> float:
        return self.cost_per_ten * max(1, math.ceil(depth / 10))

    def submit(self, *, query: str, country: str, language: str, depth: int, tag: str) -> tuple[str, float, dict[str, Any]]:
        import httpx
        payload = [{
            "keyword": query,
            "location_name": self.locations.get(country, country),
            "language_code": language,
            "depth": depth,
            "device": "desktop",
            "priority": 1,
            "tag": tag[:255],
        }]
        response = httpx.post(self.task_post_endpoint, auth=self.auth, json=payload, timeout=90)
        response.raise_for_status()
        body = response.json()
        tasks = body.get("tasks") or []
        task = tasks[0] if tasks else {}
        if int(body.get("status_code", 0)) != 20000 or int(task.get("status_code", 0)) != 20100 or not task.get("id"):
            raise RuntimeError(f"DataForSEO rejected task: {task.get('status_message') or body.get('status_message')}")
        return str(task["id"]), float(task.get("cost") or self.estimate_cost(depth)), {
            "status_code": task.get("status_code"), "status_message": task.get("status_message")
        }

    def fetch(self, remote_task_id: str) -> list[dict[str, Any]] | None:
        import httpx
        response = httpx.get(f"{self.task_get_endpoint}/{remote_task_id}", auth=self.auth, timeout=90)
        response.raise_for_status()
        body = response.json()
        tasks = body.get("tasks") or []
        task = tasks[0] if tasks else {}
        status = int(task.get("status_code", 0))
        if status in {20100, 40601, 40602}:
            return None
        if status != 20000:
            raise RuntimeError(f"DataForSEO task failed: {task.get('status_message')}")
        results = task.get("result") or []
        items = (results[0] if results else {}).get("items") or []
        rows = []
        for item in items:
            if item.get("type") != "organic" or not item.get("url"):
                continue
            rows.append({
                "position": int(item.get("rank_absolute") or len(rows) + 1),
                "title": str(item.get("title") or "")[:500],
                "url": str(item["url"]),
                "domain": str(item.get("domain") or urlsplit(str(item["url"])).hostname or ""),
                "snippet": str(item.get("description") or "")[:3000],
                "remote_task_id": remote_task_id,
            })
        return rows

    def wait(self, remote_task_id: str) -> list[dict[str, Any]]:
        deadline = time.monotonic() + self.poll_timeout_seconds
        while time.monotonic() < deadline:
            result = self.fetch(remote_task_id)
            if result is not None:
                return result
            time.sleep(5)
        raise TimeoutError("DataForSEO task timed out")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.ignored:
            self.ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored:
            clean = re.sub(r"\s+", " ", data).strip()
            if clean:
                self.parts.append(clean)


class SafePageFetcher:
    """Small public-HTTPS reader with redirect, DNS, MIME, and body bounds."""

    def __init__(self, *, maximum_bytes: int = 262_144, redirects: int = 3) -> None:
        self.maximum_bytes = maximum_bytes
        self.redirects = redirects

    @staticmethod
    def _validated(url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("research pages must be public HTTPS URLs")
        for result in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(result[4][0])
            if not address.is_global:
                raise ValueError("research page resolved to a non-public address")

    def fetch(self, url: str) -> str:
        import httpx
        current = url
        for _ in range(self.redirects + 1):
            self._validated(current)
            with httpx.Client(follow_redirects=False, timeout=20, trust_env=False) as client:
                with client.stream(
                    "GET", current,
                    headers={"User-Agent": "PTWResearch/2.0", "Accept": "text/html,text/plain"},
                ) as response:
                    stream = response.extensions.get("network_stream")
                    peer = None if stream is None else stream.get_extra_info("server_addr")
                    if not isinstance(peer, tuple) or not peer:
                        raise RuntimeError("research page peer address could not be verified")
                    if not ipaddress.ip_address(peer[0]).is_global:
                        raise ValueError("research page connected to a non-public address")
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise RuntimeError("research page redirect has no location")
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if content_type not in {"text/html", "text/plain"}:
                        raise ValueError("research page is not safe text content")
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > self.maximum_bytes:
                            raise ValueError("research page exceeds the safe size limit")
                        chunks.append(chunk)
                    raw = b"".join(chunks)
                    encoding = response.encoding or "utf-8"
            text = raw.decode(encoding, errors="replace")
            if content_type == "text/plain":
                return re.sub(r"\s+", " ", text).strip()[:12_000]
            parser = _TextExtractor()
            parser.feed(text)
            return " ".join(parser.parts)[:12_000]
        raise ValueError("research page exceeded the redirect limit")
