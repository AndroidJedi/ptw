from __future__ import annotations

import json
import os,time
import httpx
from typing import Protocol


class StructuredProvider(Protocol):
    def generate_structured(self, mode: str, system_prompt: str, input_payload: dict, output_schema: dict) -> dict: ...


class DisabledProvider:
    def generate_structured(self, mode: str, system_prompt: str, input_payload: dict, output_schema: dict) -> dict:
        raise RuntimeError("Live LLM provider is not configured; no model call was made")

class BridgeProvider:
    def __init__(self):
        self.url=os.environ.get('LLM_BRIDGE_URL','http://ptw-agent-platform-commander-api-1:8000/internal/llm/structured')
        self.token=os.environ['TELEGRAM_BOT_TOKEN']
    def generate_structured(self,mode,system_prompt,input_payload,output_schema):
        headers={'X-PTW-Bridge-Token':self.token}; payload=json.loads(json.dumps({'mode':mode,'system_prompt':system_prompt,'input_payload':input_payload,'output_schema':output_schema},default=str))
        response=httpx.post(self.url,json=payload,headers=headers,timeout=30);response.raise_for_status();request_id=response.json()['request_id']
        deadline=time.monotonic()+360
        while time.monotonic()<deadline:
            state=httpx.get(f'{self.url}/{request_id}',headers=headers,timeout=30);state.raise_for_status();body=state.json()
            if body['status']=='completed': return json.loads(body['result']['response'])
            if body['status'] in {'failed','cancelled'}: raise RuntimeError(f"LLM bridge job {request_id} {body['status']}: {body.get('error') or 'unknown'}")
            time.sleep(1)
        raise TimeoutError(f'LLM bridge job {request_id} timed out')


class MockProvider:
    """Deterministic bootstrap/test provider; never performs network I/O."""
    def __init__(self, failures: dict[str, list[Exception]] | None = None):
        self.failures = failures or {}
        self.calls: list[dict] = []

    def generate_structured(self, mode: str, system_prompt: str, input_payload: dict, output_schema: dict) -> dict:
        self.calls.append({"mode": mode, "input": json.loads(json.dumps(input_payload, default=str))})
        pending = self.failures.get(mode, [])
        if pending:
            raise pending.pop(0)
        if mode in {"generate", "evolve", "normalize_human"}:
            context = input_payload.get("context", {})
            seed = len(self.calls)
            raw = input_payload.get("raw_text")
            return {"title": (raw or f"{context.get('code', 'H')} Venture {seed}")[:120],
                    "one_liner": raw or f"A scalable automated venture generated through {context.get('code', 'owner')}",
                    "details": {"customer":"Global businesses", "problem":"Expensive repetitive work",
                    "product":"Automated software workflow", "business_model":"Recurring subscription",
                    "distribution":"Embedded partner and product-led loops", "automation":"Self-service operations",
                    "five_year_exit_logic":"Recurring revenue and strategic workflow ownership support acquisition",
                    "key_risks":["adoption", "competition"], "first_validation_test":"Pre-sell to five customers"},
                    "parent_ids": input_payload.get("suggested_parent_ids", [])}
        ideas = input_payload["ideas"]
        bias = int(input_payload.get("evaluator", {}).get("code", "C01")[1:])
        def evaluation(i):
            score = 55 + ((i["id"] + bias) % 36)
            parts = [round(score*x, 2) for x in (.25, .20, .15, .15, .15)]
            parts.append(round(score-sum(parts), 2))
            keys = ("exit_potential","founder_independence","distribution",
                    "scalability_economics","defensibility","speed_capital_efficiency")
            return {"idea_id":i["id"],"score":score,"criteria":dict(zip(keys,parts)),
                    "strengths":"Scalable workflow",
                    "critique":f"Evaluator C{bias:02d} requests sharper proof","fatal_flaw":None}
        return {"evaluations":[evaluation(i) for i in ideas]}
