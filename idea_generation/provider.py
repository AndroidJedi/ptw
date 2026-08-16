from __future__ import annotations

import json
from typing import Any, Protocol


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

    def generate_structured(
        self, mode: str, system_prompt: str, input_payload: dict[str, Any], output_schema: dict[str, Any]
    ) -> dict[str, Any]:
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
                    "criteria": {"exit_potential": score * .25, "founder_independence": score * .20,
                                 "distribution": score * .15, "scalability_economics": score * .15,
                                 "defensibility": score * .15, "speed_capital_efficiency": score * .10},
                    "strengths": "Clear leverage and validation path.",
                    "critique": "Distribution assumptions need direct testing.", "fatal_flaw": None,
                })
            return {"evaluations": evaluations}
        context = input_payload["context"]["code"]
        ordinal = len([call for call in self.calls if call[0] in {"generate", "evolve"}])
        parents = []
        if mode == "evolve" and input_payload.get("mode") == "exploit":
            parents = [input_payload["current_generation"][ordinal % len(input_payload["current_generation"])]["id"]]
        return {"title": f"{context} Candidate {ordinal}", "one_liner": "Automated software for a costly recurring workflow.",
                "details": {"customer": "Global operating teams", "problem": "A costly recurring manual workflow",
                    "product": "A self-serve automation platform", "business_model": "Recurring subscription and usage fees",
                    "distribution": "Embedded integrations and partner channels", "automation": "Software delivery and support automation",
                    "five_year_exit_logic": "Recurring revenue, workflow data, and distribution make a strategic acquisition plausible.",
                    "key_risks": ["Adoption", "Incumbent response"], "first_validation_test": "Pre-sell a narrow workflow to five teams."},
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
        if not content: raise RuntimeError("provider returned an empty response")
        result = json.loads(content)
        if not isinstance(result, dict): raise ValueError("provider response must be a JSON object")
        return result
