from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Protocol

from commander.ids import new_uuid7


class StructuredProvider(Protocol):
    def generate_structured(
        self, mode: str, system_prompt: str, input_payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> dict[str, Any]: ...


class MockLLMProvider:
    """Deterministic acceptance provider. It never performs a network call."""

    model_name = "mock-v1"

    def __init__(self, failures: list[Exception | dict[str, Any]] | None = None) -> None:
        self.failures = list(failures or [])
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.last_invocation: dict[str, Any] = {}

    def generate_structured(
        self, mode: str, system_prompt: str, input_payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.last_invocation = {"session_id": str(new_uuid7()), "session_mode": "fresh"}
        self.calls.append((mode, input_payload))
        if self.failures:
            result = self.failures.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        if mode == "evaluate":
            evaluations = []
            evaluator = input_payload["context"]["code"]
            bias = int(evaluator[1:])
            for idea in input_payload["ideas"]:
                score = 55 + ((int(idea["id"]) * 3 + bias) % 35)
                evaluations.append({
                    "idea_id": idea["id"], "score": score,
                    "criteria": {"three_year_exit_potential": score * .25, "remote_operability_autonomy": score * .25,
                                 "distribution": score * .15, "scalability_economics": score * .15,
                                 "defensibility": score * .10, "speed_capital_efficiency": score * .10},
                    "strengths": "Clear leverage and validation path.",
                    "critique": "Distribution assumptions need direct testing.", "fatal_flaw": None,
                })
            return {"evaluations": evaluations}
        context = input_payload["context"]["code"]
        if mode == "normalize_human":
            raw = str(input_payload.get("raw_text", "")).strip()
            title = next((line.strip("# ") for line in raw.splitlines() if line.strip()), "Owner idea")[:160]
            return {
                "title": {"en": title, "uk": title},
                "one_liner": {"en": raw[:1000], "uk": raw[:1000]},
                "details": {
                    "customer": {"en": "Defined by the owner submission and to be validated", "uk": "Визначено заявкою власника; потребує перевірки"},
                    "problem": {"en": raw, "uk": raw},
                    "product": {"en": raw, "uk": raw},
                    "business_model": {"en": "To be validated", "uk": "Потребує перевірки"},
                    "distribution": {"en": "To be validated", "uk": "Потребує перевірки"},
                    "automation": {"en": "To be validated", "uk": "Потребує перевірки"},
                    "three_year_exit_logic": {"en": "To be validated against the mission", "uk": "Потребує перевірки відносно місії"},
                    "key_risks": {"en": ["Owner concept requires structured validation"], "uk": ["Концепція власника потребує структурованої перевірки"]},
                    "first_validation_test": {"en": "Test the central assumption with five target users.", "uk": "Перевірити центральне припущення з п’ятьма цільовими користувачами."},
                },
                "parent_ids": [],
                "lineage_note": "Owner submission normalized without changing the concept",
            }
        ordinal = len([call for call in self.calls if call[0] in {"generate", "evolve"}])
        parents = []
        if mode == "evolve" and input_payload.get("mode") == "exploit":
            parents = [input_payload["current_generation"][ordinal % len(input_payload["current_generation"])]["id"]]
        return {"title": {"en": f"{context} Candidate {ordinal}", "uk": f"{context} Кандидат {ordinal}"},
                "one_liner": {"en": "Automated software for a costly recurring workflow.", "uk": "Автоматизоване ПЗ для дорогого повторюваного процесу."},
                "details": {
                    "customer": {"en": "Global operating teams", "uk": "Операційні команди в усьому світі"},
                    "problem": {"en": "A costly recurring manual workflow", "uk": "Дорогий повторюваний ручний процес"},
                    "product": {"en": "A self-serve automation platform", "uk": "Self-service платформа автоматизації"},
                    "business_model": {"en": "Recurring subscription and usage fees", "uk": "Підписка та оплата за використання"},
                    "distribution": {"en": "Embedded integrations and partner channels", "uk": "Вбудовані інтеграції та партнерські канали"},
                    "automation": {"en": "Software delivery and support automation", "uk": "Програмна доставка та автоматизація підтримки"},
                    "three_year_exit_logic": {"en": "Recurring revenue, workflow data, and distribution can support a strategic acquisition within 36 months.", "uk": "Повторювана виручка, workflow-дані та дистрибуція можуть обґрунтувати стратегічне придбання за 36 місяців."},
                    "key_risks": {"en": ["Adoption", "Incumbent response"], "uk": ["Прийняття ринком", "Відповідь чинних гравців"]},
                    "first_validation_test": {"en": "Pre-sell a narrow workflow to five teams.", "uk": "Попередньо продати вузький workflow п’ятьом командам."}},
                "parent_ids": parents, "lineage_note": "Mocked deterministic candidate"}


class OpenAIProvider:
    """Optional production adapter; acceptance tests use ``MockLLMProvider`` only."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key: raise RuntimeError("OPENAI_API_KEY is required for LLM_PROVIDER=openai")
        from openai import OpenAI
        self.client, self.model_name = OpenAI(api_key=api_key), model

    def generate_structured(
        self, mode: str, system_prompt: str, input_payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": system_prompt + " Return one JSON object only."},
                      {"role": "user", "content": json.dumps(input_payload, ensure_ascii=False, default=str)}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        self.last_invocation = {
            "session_id": str(response.id),
            "session_mode": "fresh",
            "conversation_reused": False,
        }
        if not content: raise RuntimeError("provider returned an empty response")
        result = json.loads(content)
        if not isinstance(result, dict): raise ValueError("provider response must be a JSON object")
        return result


class BridgeProvider:
    """Use the established authenticated Codex worker through its internal API."""

    def __init__(self, url: str, token: str, model: str = "codex-cli-default", timeout_seconds: int = 360) -> None:
        if not url or not token:
            raise RuntimeError("LLM_BRIDGE_URL and TELEGRAM_BOT_TOKEN are required for bridge mode")
        self.url = url.rstrip("/")
        self.token = token
        self.model_name = model or "codex-cli-default"
        self.timeout_seconds = timeout_seconds
        self.last_invocation: dict[str, Any] = {}
        self._request_metadata: dict[str, str] = {}

    def prepare_invocation(self, prompt_template_version: str, context_hash: str) -> None:
        self._request_metadata = {
            "prompt_template_version": prompt_template_version,
            "context_hash": context_hash,
        }

    def generate_structured(
        self, mode: str, system_prompt: str, input_payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> dict[str, Any]:
        headers = {"X-PTW-Bridge-Token": self.token}
        request = {
            "mode": mode,
            "system_prompt": system_prompt,
            "input_payload": input_payload,
            "output_schema": output_schema,
            "model": self.model_name,
            **self._request_metadata,
        }
        request_id = int(self._request(self.url, request, headers)["request_id"])
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            payload = self._request(f"{self.url}/{request_id}", None, headers)
            if payload["status"] == "completed":
                result = payload.get("result") or {}
                self.last_invocation = dict(result.get("invocation") or {}) if isinstance(result, dict) else {}
                body = result.get("response") if isinstance(result, dict) else None
                decoded = json.loads(body) if isinstance(body, str) else body
                if not isinstance(decoded, dict):
                    raise ValueError("LLM bridge response must contain one JSON object")
                return decoded
            if payload["status"] in {"failed", "cancelled"}:
                raise RuntimeError(f"LLM bridge job {request_id} {payload['status']}")
            time.sleep(1)
        raise TimeoutError(f"LLM bridge job {request_id} timed out")

    @staticmethod
    def _request(url: str, payload: dict[str, Any] | None, headers: dict[str, str]) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, default=str).encode()
        request = urllib.request.Request(
            url, data=body, headers={**headers, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
        if not isinstance(result, dict):
            raise ValueError("LLM bridge returned invalid JSON")
        return result
