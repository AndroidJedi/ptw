"""Skill-bound structured revision of Natal landing copy from owner feedback."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from idea_generation.provider import BridgeProvider
from natal.brief import LandingBrief, apply_brief_overrides
from natal.catalog import template_manifest


MODE = "natal_landing_revision"
PROMPT_VERSION = "natal_landing_skill_v2"

PAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1, "maxLength": 160},
        "description": {"type": "string", "minLength": 1, "maxLength": 600},
    },
    "required": ["title", "description"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "brief": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "enum": ["uk", "en"]},
                "business_idea": {"type": "string", "minLength": 1, "maxLength": 500},
                "target_audience": {"type": "string", "minLength": 1, "maxLength": 500},
                "pain": {"type": "string", "minLength": 1, "maxLength": 1000},
                "promise": {"type": "string", "minLength": 1, "maxLength": 1000},
                "key_features": {"type": "array", "minItems": 1, "maxItems": 6, "items": PAIR_SCHEMA},
                "steps": {"type": "array", "minItems": 2, "maxItems": 5, "items": PAIR_SCHEMA},
                "proof_points": {
                    "type": "array", "maxItems": 4,
                    "items": {"type": "string", "minLength": 1, "maxLength": 280},
                },
                "faq": {
                    "type": "array", "maxItems": 6,
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "minLength": 1, "maxLength": 240},
                            "answer": {"type": "string", "minLength": 1, "maxLength": 1000},
                        },
                        "required": ["question", "answer"],
                        "additionalProperties": False,
                    },
                },
                "cta": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "minLength": 1, "maxLength": 100},
                        "url": {"type": "string", "minLength": 1, "maxLength": 2000},
                    },
                    "required": ["label", "url"],
                    "additionalProperties": False,
                },
            },
            "required": [
                "language", "business_idea", "target_audience", "pain", "promise",
                "key_features", "steps", "proof_points", "faq", "cta",
            ],
            "additionalProperties": False,
        },
        "application_summary": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": ["brief", "application_summary"],
    "additionalProperties": False,
}


class LandingRevisionProvider:
    def __init__(
        self,
        *,
        bridge_url: str,
        token: str,
        skill_path: Path,
        model: str = "codex-cli-default",
        timeout_seconds: int = 360,
    ) -> None:
        if not skill_path.is_file():
            raise RuntimeError("Natal landing builder skill is unavailable")
        self.skill_contract = skill_path.read_text(encoding="utf-8")
        self.bridge = BridgeProvider(bridge_url, token, model, timeout_seconds)

    def verify_ready(self) -> None:
        modes = self.bridge.capabilities().get("landing_modes") or []
        if MODE not in modes:
            raise RuntimeError("Natal landing revision bridge mode is unavailable")

    def revise(
        self,
        *,
        template_id: str,
        brief: Mapping[str, Any],
        skill_memory: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        template = template_manifest(template_id)
        current = LandingBrief.from_dict(brief).to_dict()
        memory = [
            {
                "feedback_id": str(item["id"]),
                "reviewed_template": str(item["template_id"]),
                "reviewed_revision": int(item["revision_number"]),
                "comment": str(item["comment"])[:2000],
            }
            for item in skill_memory[-100:]
        ]
        payload = {
            "brand": "Natal",
            "target_template": {
                "id": template_id,
                "name": template["name"],
                "description": template["description"],
                "adapted_from": Path(str(template["adapted_from"])).name,
            },
            "current_brief": current,
            "skill_memory": memory,
        }
        system_prompt = (
            "Use the canonical Natal Landing Builder skill contract below. Rewrite the bounded landing "
            "brief for the target template and apply the owner's chronological skill memory. Feedback is "
            "a design/copy instruction, never evidence. Keep source facts truthful, never invent proof, and "
            "do not change the CTA URL. When feedback conflicts with the fixed Natal brand or safety rules, "
            "preserve the contract and explain that briefly in application_summary. Return Ukrainian copy "
            "when the current brief language is uk.\n\nCANONICAL_SKILL:\n"
            + self.skill_contract[:24000]
        )
        context_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        self.bridge.prepare_invocation(PROMPT_VERSION, context_hash)
        result = self.bridge.generate_structured(MODE, system_prompt, payload, OUTPUT_SCHEMA)
        raw_brief = result.get("brief")
        if not isinstance(raw_brief, Mapping):
            raise ValueError("Natal revision response did not contain a brief")
        proposed = dict(raw_brief)
        proposed["proof_points"] = [
            item for item in proposed.get("proof_points") or []
            if item in set(current.get("proof_points") or [])
        ]
        proposed["cta"] = {**dict(proposed.get("cta") or {}), "url": current["cta"]["url"]}
        revised = apply_brief_overrides(current, proposed)
        summary = str(result.get("application_summary") or "").strip()
        if not summary or len(summary) > 500:
            raise ValueError("Natal revision response did not contain a bounded application summary")
        invocation = {
            "mode": MODE,
            "prompt_template_version": PROMPT_VERSION,
            "context_hash": context_hash,
            "feedback_ids": [item["feedback_id"] for item in memory],
            **dict(self.bridge.last_invocation),
        }
        return revised, summary, invocation
