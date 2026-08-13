"""OpenAI web-search adapter for bounded creative-ideation research."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import os
import subprocess
import tempfile
from pathlib import Path
import shutil

from .research import CreativeResearchResult, HypothesisProposal, ResearchFinding


class OpenAICreativeResearchProvider:
    def __init__(self, api_key: str, *, model: str = "gpt-5-mini", timeout_seconds: int = 90) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required for /research")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def research(self, topic: str) -> CreativeResearchResult:
        schema = {
            "type": "object",
            "properties": {
                "findings": {"type": "array", "minItems": 2, "maxItems": 6, "items": {"type": "object", "properties": {
                    "title": {"type": "string"}, "source_uri": {"type": "string"},
                    "publisher": {"type": "string"}, "finding_summary": {"type": "string"},
                    "credibility": {"type": "number", "minimum": 0, "maximum": 1}},
                    "required": ["title", "source_uri", "publisher", "finding_summary", "credibility"], "additionalProperties": False}},
                "hypotheses": {"type": "array", "minItems": 1, "maxItems": 5, "items": {"type": "object", "properties": {
                    "claim": {"type": "string"}, "source_indexes": {"type": "array", "items": {"type": "integer"}},
                    "creative_direction": {"type": "string"}, "success_metric": {"type": "string"},
                    "threshold": {"type": "number"}},
                    "required": ["claim", "source_indexes", "creative_direction", "success_metric", "threshold"], "additionalProperties": False}},
            }, "required": ["findings", "hypotheses"], "additionalProperties": False,
        }
        payload = {
            "model": self.model,
            "tools": [{"type": "web_search"}],
            "input": (
                "Research this topic only for Instagram creative ideation: " + topic +
                ". Find reliable, directly relevant web sources. Produce concise findings and falsifiable "
                "creative hypotheses. Every hypothesis must reference zero-based indexes in findings; never "
                "present interpretation as fact. Use canonical source URLs, not search-result URLs."
            ),
            "text": {"format": {"type": "json_schema", "name": "creative_research", "strict": True, "schema": schema}},
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses", data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.load(response)
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError("creative research provider request failed") from error
        output_text = raw.get("output_text")
        if not output_text:
            for item in raw.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text = content.get("text")
        values = json.loads(str(output_text))
        findings = tuple(ResearchFinding(**item) for item in values["findings"])
        hypotheses = tuple(HypothesisProposal(**{**item, "source_indexes": tuple(item["source_indexes"])}) for item in values["hypotheses"])
        return CreativeResearchResult(findings, hypotheses)


class CodexCreativeResearchProvider:
    """Use the VPS's existing authenticated Codex runtime; no extra API key."""

    def __init__(self, executable: str, *, timeout_seconds: int = 180) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def research(self, topic: str) -> CreativeResearchResult:
        schema = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "findings": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "properties": {"title": {"type": "string"}, "source_uri": {"type": "string"},
                    "publisher": {"type": "string"}, "finding_summary": {"type": "string"},
                    "credibility": {"type": "number"}},
                    "required": ["title", "source_uri", "publisher", "finding_summary", "credibility"]}},
                "hypotheses": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "properties": {"claim": {"type": "string"}, "source_indexes": {"type": "array", "items": {"type": "integer"}},
                    "creative_direction": {"type": "string"}, "success_metric": {"type": "string"}, "threshold": {"type": "number"}},
                    "required": ["claim", "source_indexes", "creative_direction", "success_metric", "threshold"]}},
            }, "required": ["findings", "hypotheses"],
        }
        prompt = (
            "Act only as the PTW Instagram creative research agent. Browse the web and research: " + topic +
            ". Identify viral hook patterns and corresponding image concepts relevant to Proof Them Wrong. "
            "Return 2-6 concise sourced findings and 1-5 falsifiable creative hypotheses. In each "
            "creative_direction use exactly: hook | image concept and caption | CTA. Cite canonical source "
            "URLs in source_uri. Do not write code, inspect repositories, or make engineering recommendations."
        )
        with tempfile.TemporaryDirectory(prefix="ptw-research-") as directory:
            root = Path(directory)
            schema_path, output_path = root / "schema.json", root / "result.json"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            environment = dict(os.environ)
            codex_home = root / "codex-home"
            codex_home.mkdir(mode=0o700)
            auth_source = Path(environment.get("CODEX_HOME", "/run/ptw-auth")) / "auth.json"
            shutil.copyfile(auth_source, codex_home / "auth.json")
            (codex_home / "auth.json").chmod(0o600)
            environment["CODEX_HOME"] = str(codex_home)
            completed = subprocess.run(
                [self.executable, "exec", "--ephemeral", "--ignore-user-config", "--sandbox", "read-only",
                 "--skip-git-repo-check", "--cd", directory, "--output-schema", str(schema_path),
                 "--output-last-message", str(output_path), prompt],
                capture_output=True, text=True, timeout=self.timeout_seconds, env=environment,
            )
            if completed.returncode != 0:
                raise RuntimeError("creative research agent failed; try again shortly")
            values = json.loads(output_path.read_text(encoding="utf-8"))
        findings = tuple(ResearchFinding(**item) for item in values["findings"])
        hypotheses = tuple(HypothesisProposal(**{**item, "source_indexes": tuple(item["source_indexes"])}) for item in values["hypotheses"])
        return CreativeResearchResult(findings, hypotheses)
