"""Skill-bound structured revision of Natal landing copy from owner feedback."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from idea_generation.provider import BridgeProvider
from natal.brief import LandingBrief, apply_brief_overrides
from natal.catalog import template_manifest
from natal.page import BLOCK_IDS, LandingPageContent, protect_page_content


MODE = "natal_landing_revision"
PROMPT_VERSION = "natal_landing_skill_v3"

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

BASE_COPY = {"type": "string", "minLength": 1, "maxLength": 1000}
BLOCK_SCHEMAS: dict[str, dict[str, Any]] = {
    "hero": {
        "type": "object",
        "properties": {
            "eyebrow": {**BASE_COPY, "maxLength": 500},
            "title": {**BASE_COPY, "maxLength": 500},
            "body": BASE_COPY,
            "cta_label": {**BASE_COPY, "maxLength": 100},
        },
        "required": ["eyebrow", "title", "body", "cta_label"],
        "additionalProperties": False,
    },
    "problem": {
        "type": "object",
        "properties": {
            "eyebrow": {**BASE_COPY, "maxLength": 100},
            "title": BASE_COPY,
            "body": BASE_COPY,
        },
        "required": ["eyebrow", "title", "body"],
        "additionalProperties": False,
    },
    "features": {
        "type": "object",
        "properties": {
            "eyebrow": {**BASE_COPY, "maxLength": 100},
            "title": {**BASE_COPY, "maxLength": 500},
            "items": {"type": "array", "minItems": 1, "maxItems": 6, "items": PAIR_SCHEMA},
        },
        "required": ["eyebrow", "title", "items"],
        "additionalProperties": False,
    },
    "steps": {
        "type": "object",
        "properties": {
            "eyebrow": {**BASE_COPY, "maxLength": 100},
            "title": {**BASE_COPY, "maxLength": 500},
            "items": {"type": "array", "minItems": 2, "maxItems": 5, "items": PAIR_SCHEMA},
        },
        "required": ["eyebrow", "title", "items"],
        "additionalProperties": False,
    },
    "proof": {
        "type": "object",
        "properties": {
            "eyebrow": {**BASE_COPY, "maxLength": 100},
            "title": {**BASE_COPY, "maxLength": 500},
            "items": {
                "type": "array", "maxItems": 4,
                "items": {"type": "string", "minLength": 1, "maxLength": 280},
            },
            "empty_text": {**BASE_COPY, "maxLength": 500},
        },
        "required": ["eyebrow", "title", "items", "empty_text"],
        "additionalProperties": False,
    },
    "faq": {
        "type": "object",
        "properties": {
            "eyebrow": {**BASE_COPY, "maxLength": 100},
            "title": {**BASE_COPY, "maxLength": 500},
            "items": OUTPUT_SCHEMA["properties"]["brief"]["properties"]["faq"],
        },
        "required": ["eyebrow", "title", "items"],
        "additionalProperties": False,
    },
    "final_cta": {
        "type": "object",
        "properties": {
            "title": {**BASE_COPY, "maxLength": 500},
            "body": BASE_COPY,
            "cta_label": {**BASE_COPY, "maxLength": 100},
        },
        "required": ["title", "body", "cta_label"],
        "additionalProperties": False,
    },
}


def page_content_schema(template_id: str | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "template_id": {
                "type": "string",
                **({"const": template_id} if template_id else {"enum": ["product", "community", "waitlist"]}),
            },
            "language": {"type": "string", "enum": ["uk", "en"]},
            "blocks": {
                "type": "object",
                "properties": BLOCK_SCHEMAS,
                "required": list(BLOCK_IDS),
                "additionalProperties": False,
            },
        },
        "required": ["template_id", "language", "blocks"],
        "additionalProperties": False,
    }


POPULATE_SCHEMA = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "object",
            "properties": {template_id: page_content_schema(template_id) for template_id in ("product", "community", "waitlist")},
            "required": ["product", "community", "waitlist"],
            "additionalProperties": False,
        },
        "application_summary": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": ["pages", "application_summary"],
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
        skill_parts = [skill_path.read_text(encoding="utf-8")]
        for name in ("block-contract.md", "content-guidelines.md", "owner-lessons.md"):
            reference = skill_path.parent / "references" / name
            if reference.is_file():
                skill_parts.append(f"\nREFERENCE {name}:\n{reference.read_text(encoding='utf-8')}")
        self.skill_contract = "\n".join(skill_parts)
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
        self._require_exact_keys(result, {"brief", "application_summary"}, "revision response")
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

    def populate_set(
        self,
        *,
        brief: Mapping[str, Any],
        skill_memory: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], str, dict[str, Any]]:
        current = LandingBrief.from_dict(brief).to_dict()
        memory = self._memory(skill_memory)
        payload = {
            "operation": "populate_set",
            "brand": "Natal",
            "templates": [
                {
                    "id": template_id,
                    "name": template_manifest(template_id)["name"],
                    "description": template_manifest(template_id)["description"],
                }
                for template_id in ("product", "community", "waitlist")
            ],
            "source_brief": current,
            "skill_memory": memory,
        }
        result, context_hash = self._generate(
            operation="populate_set", payload=payload, schema=POPULATE_SCHEMA,
            instruction=(
                "Create three distinct, complete Natal landing page content models in one response. "
                "Keep every canonical block, tailor only the copy to each fixed template, use plain "
                "outcome-led Ukrainian when language is uk, and never invent proof, urgency, price, "
                "availability, integrations, or customer results."
            ),
        )
        self._require_exact_keys(result, {"pages", "application_summary"}, "population response")
        raw_pages = result.get("pages")
        if not isinstance(raw_pages, Mapping):
            raise ValueError("Natal population response did not contain three pages")
        self._require_exact_keys(
            raw_pages, {"product", "community", "waitlist"}, "population pages"
        )
        pages = {
            template_id: protect_page_content(
                raw_pages.get(template_id) if isinstance(raw_pages.get(template_id), Mapping) else {},
                template_id=template_id,
                brief=current,
            ).to_dict()
            for template_id in ("product", "community", "waitlist")
        }
        summary = self._summary(result)
        return pages, summary, self._invocation("populate_set", context_hash, memory)

    def edit_block(
        self,
        *,
        template_id: str,
        brief: Mapping[str, Any],
        page_content: Mapping[str, Any],
        block_id: str,
        instruction: str,
        skill_memory: Sequence[Mapping[str, Any]],
    ) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
        if block_id not in BLOCK_IDS:
            raise ValueError("unknown landing block")
        normalized_instruction = instruction.strip()
        if not normalized_instruction or len(normalized_instruction) > 2000:
            raise ValueError("block instruction must contain 1-2000 characters")
        current_brief = LandingBrief.from_dict(brief).to_dict()
        current_page = LandingPageContent.from_dict(
            page_content, expected_template_id=template_id
        )
        memory = self._memory(skill_memory)
        schema = {
            "type": "object",
            "properties": {
                "block": BLOCK_SCHEMAS[block_id],
                "application_summary": {"type": "string", "minLength": 1, "maxLength": 500},
                "reusable_lesson": {"type": "string", "minLength": 1, "maxLength": 500},
            },
            "required": ["block", "application_summary", "reusable_lesson"],
            "additionalProperties": False,
        }
        payload = {
            "operation": "edit_block",
            "brand": "Natal",
            "target_template": template_id,
            "target_block": block_id,
            "owner_instruction": normalized_instruction,
            "source_brief": current_brief,
            "current_page": current_page.to_dict(),
            "skill_memory": memory,
        }
        result, context_hash = self._generate(
            operation=f"edit_block:{block_id}", payload=payload, schema=schema,
            instruction=(
                f"Rewrite only the {block_id} block requested by the owner. Return that complete block, "
                "not the page. Preserve factual truth and express a concise generalized reusable lesson "
                "for optional owner review; do not turn the comment itself into evidence."
            ),
        )
        self._require_exact_keys(
            result, {"block", "application_summary", "reusable_lesson"}, "block edit response"
        )
        raw_block = result.get("block")
        if not isinstance(raw_block, Mapping):
            raise ValueError("Natal block edit response did not contain a block")
        candidate = current_page.replace_block(block_id, raw_block)
        if block_id == "proof":
            candidate = protect_page_content(
                candidate.to_dict(), template_id=template_id, brief=current_brief
            )
        block = dict(candidate.blocks[block_id])
        lesson = str(result.get("reusable_lesson") or "").strip()
        if not lesson or len(lesson) > 500:
            raise ValueError("Natal block edit response did not contain a bounded reusable lesson")
        return block, self._summary(result), lesson, self._invocation(
            f"edit_block:{block_id}", context_hash, memory
        )

    def _generate(
        self, *, operation: str, payload: Mapping[str, Any], schema: Mapping[str, Any], instruction: str
    ) -> tuple[dict[str, Any], str]:
        system_prompt = (
            "Use the canonical Natal Landing Builder skill and references below. "
            + instruction
            + " Source facts, verified proof, Natal brand assets, template structure, and CTA destination "
            "are server-owned. Return strict schema output only.\n\nCANONICAL_SKILL:\n"
            + self.skill_contract[:30000]
        )
        context_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        self.bridge.prepare_invocation(f"{PROMPT_VERSION}:{operation}", context_hash)
        return dict(self.bridge.generate_structured(MODE, system_prompt, payload, schema)), context_hash

    def _invocation(
        self, operation: str, context_hash: str, memory: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        return {
            "mode": MODE,
            "operation": operation,
            "prompt_template_version": PROMPT_VERSION,
            "context_hash": context_hash,
            "feedback_ids": [item["feedback_id"] for item in memory],
            **dict(self.bridge.last_invocation),
        }

    @staticmethod
    def _summary(result: Mapping[str, Any]) -> str:
        summary = str(result.get("application_summary") or "").strip()
        if not summary or len(summary) > 500:
            raise ValueError("Natal agent response did not contain a bounded application summary")
        return summary

    @staticmethod
    def _require_exact_keys(
        value: Mapping[str, Any], expected: set[str], name: str
    ) -> None:
        if set(value) != expected:
            raise ValueError(f"Natal {name} did not match the strict response schema")

    @staticmethod
    def _memory(skill_memory: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "feedback_id": str(item["id"]),
                "reviewed_template": str(item.get("template_id") or ""),
                "reviewed_block": str(item.get("block_id") or "whole_page"),
                "reviewed_revision": int(item.get("revision_number") or 0),
                "comment": str(item["comment"])[:2000],
            }
            for item in skill_memory[-100:]
        ]
