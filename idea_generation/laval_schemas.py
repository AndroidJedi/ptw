"""Strict structured-output contracts for every Idea Laval language stage.

The Codex bridge uses strict JSON Schema. Every nested object therefore declares
all properties, requires them, and rejects additional properties; every array
declares its item shape. Keeping these contracts here prevents a superficially
successful run from silently falling back when the provider rejects a weak
schema before inference begins.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .laval_domain import OPERATORS, QUERY_FAMILIES


def _object(properties: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }


def _array(items: dict[str, Any], **limits: int) -> dict[str, Any]:
    return {"type": "array", "items": items, **limits}


STRING = {"type": "string"}
NUMBER = {"type": "number", "minimum": 0, "maximum": 1}
STRING_ARRAY = _array(STRING)
I18N = _object({"en": STRING, "uk": STRING})

OWNER_DNA = _object({
    "owner_dna": _object({
        "problem": STRING,
        "target_user": STRING,
        "core_mechanism": STRING,
        "core_emotion": STRING,
        "why_now": STRING,
        "must_preserve": STRING_ARRAY,
        "assumptions": STRING_ARRAY,
        "unknowns": STRING_ARRAY,
    }),
})

QUERY_PLAN = _object({
    "query_intents": _array(_object({
        "family": {"type": "string", "enum": list(QUERY_FAMILIES)},
        "base_query": STRING,
        "translations": _array(_object({"language": STRING, "query": STRING})),
    })),
})

COMPETITOR_DOSSIER = _object({
    "dossier": _object({
        "competitor_id": STRING,
        "name": STRING,
        "url": STRING,
        "type": STRING,
        "country_presence": STRING_ARRAY,
        "positioning": STRING_ARRAY,
        "audiences": STRING_ARRAY,
        "features": STRING_ARRAY,
        "pricing": STRING_ARRAY,
        "distribution": STRING_ARRAY,
        "hooks": STRING_ARRAY,
        "strengths": STRING_ARRAY,
        "complaints": STRING_ARRAY,
        "gaps": STRING_ARRAY,
        "keywords": STRING_ARRAY,
        "evidence_ids": STRING_ARRAY,
        "confidence": NUMBER,
    }),
})

OPPORTUNITY_MATRIX = _object({
    "opportunities": _array(_object({
        "statement": STRING,
        "pain": STRING,
        "affected_segment": STRING,
        "competitor_ids": STRING_ARRAY,
        "countries": STRING_ARRAY,
        "evidence_ids": STRING_ARRAY,
        "scores": _object({
            "frequency": NUMBER,
            "severity": NUMBER,
            "coverage_gap": NUMBER,
            "cross_market": NUMBER,
            "owner_relevance": NUMBER,
            "confidence": NUMBER,
        }),
    }), minItems=1),
})

MARKET_SIGNAL_RELEVANCE = _object({
    "classifications": _array(_object({
        "opportunity_id": STRING,
        "evidence_id": STRING,
        "relevant": {"type": "boolean"},
    })),
})

IDEA_EXPANSION = _object({
    "variants": _array(_object({
        "title": I18N,
        "one_liner": I18N,
        "mechanism": I18N,
        "target_user": I18N,
        "why_new": I18N,
        "operator": {"type": "string", "enum": list(OPERATORS)},
        "opportunity_ids": STRING_ARRAY,
        "trend_signal_ids": STRING_ARRAY,
        "trend_discovery_ids": STRING_ARRAY,
        "market_signal_ids": STRING_ARRAY,
        "evidence_ids": STRING_ARRAY,
    }), minItems=1),
})

IDEA_EVALUATION = _object({
    "evaluations": _array(_object({
        "idea_id": STRING,
        "score": NUMBER,
        "dimensions": _object({
            "owner_fit": NUMBER,
            "differentiation": NUMBER,
            "opportunity_support": NUMBER,
            "trend_support": NUMBER,
            "distribution_potential": NUMBER,
            "novelty": NUMBER,
        }),
        "strengths": STRING,
        "critique": STRING,
        "fatal_flaw": {"type": ["string", "null"]},
    })),
})

YOUTUBE_OBSERVATION = _object({
    "observations": _array(_object({
        "observation_type": {"type": "string", "enum": [
            "workaround", "challenge_format", "motivation", "repeated_question",
            "complaint", "transformation_narrative", "audience_vocabulary",
            "creator_distribution", "substitute",
        ]},
        "statement": STRING,
        "video_ids": STRING_ARRAY,
        "evidence_ids": STRING_ARRAY,
        "confidence": NUMBER,
    })),
})

MECHANISM_EXTRACTION = _object({
    "mechanisms": _array(_object({
        "name": I18N,
        "description": I18N,
        "mechanism_type": {"type": "string", "enum": [
            "value", "behavior", "trust", "retention", "distribution", "proof",
        ]},
        "source_variant_ids": STRING_ARRAY,
        "opportunity_ids": STRING_ARRAY,
        "market_signal_ids": STRING_ARRAY,
        "behavior_observation_ids": STRING_ARRAY,
        "evidence_ids": STRING_ARRAY,
    }), minItems=6, maxItems=20),
})

ASSUMPTION = _object({
    "id": STRING,
    "statement": I18N,
    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
})

THESIS_SYNTHESIS = _object({
    "theses": _array(_object({
        "title": I18N,
        "target_user": I18N,
        "problem": I18N,
        "loop_steps": _array(I18N, minItems=5, maxItems=8),
        "value_moment": I18N,
        "zero_audience_behavior": I18N,
        "substitutes": _array(I18N),
        "dangerous_assumptions": _array(ASSUMPTION, minItems=1),
        "success_criterion": _object({
            "metric": STRING,
            "operator": {"type": "string", "enum": [">="]},
            "threshold": {"type": "number"},
            "sample_target": {"type": "integer", "minimum": 1},
        }),
        "mechanism_ids": _array(STRING, minItems=3, maxItems=7),
        "evidence_ids": STRING_ARRAY,
    }), minItems=1, maxItems=3),
})

THESIS_FALSIFICATION = _object({
    "reports": _array(_object({
        "thesis_id": STRING,
        "verdict": {"type": "string", "enum": ["survives", "weak", "rejected"]},
        "risks": _array(_object({
            "assumption_id": STRING,
            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
            "supported": {"type": "boolean"},
            "objection": STRING,
            "counterargument": STRING,
            "evidence_ids": STRING_ARRAY,
            "mechanism_ids": STRING_ARRAY,
            "fatal": {"type": "boolean"},
        }), minItems=1),
        "fatal_objection": {"type": ["string", "null"]},
    })),
})


SCHEMAS = {
    "laval_owner_dna": OWNER_DNA,
    "laval_query_plan": QUERY_PLAN,
    "laval_competitor_dossier": COMPETITOR_DOSSIER,
    "laval_opportunity_matrix": OPPORTUNITY_MATRIX,
    "laval_market_signal_relevance": MARKET_SIGNAL_RELEVANCE,
    "laval_idea_expansion": IDEA_EXPANSION,
    "laval_idea_evaluation": IDEA_EVALUATION,
    "laval_youtube_observation": YOUTUBE_OBSERVATION,
    "laval_mechanism_extraction": MECHANISM_EXTRACTION,
    "laval_thesis_synthesis": THESIS_SYNTHESIS,
    "laval_thesis_falsification": THESIS_FALSIFICATION,
}


def output_schema(mode: str, required: str) -> dict[str, Any]:
    """Return an isolated schema and guard against mode/caller drift."""

    schema = SCHEMAS.get(mode)
    if schema is None:
        value_type = "object" if required in {"owner_dna", "dossier"} else "array"
        item: dict[str, Any] = {} if value_type == "array" else {"type": "object"}
        value = {"type": value_type, **({"items": item} if value_type == "array" else {})}
        return _object({required: value})
    if required not in schema["properties"]:
        raise ValueError(f"{mode} schema does not define required output {required!r}")
    return deepcopy(schema)


def strictly_describes_nested_values(schema: dict[str, Any]) -> bool:
    """Small contract probe used by tests and release diagnostics."""

    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties")
        return (
            isinstance(properties, dict)
            and schema.get("additionalProperties") is False
            and set(schema.get("required") or []) == set(properties)
            and all(strictly_describes_nested_values(value) for value in properties.values())
        )
    if schema_type == "array":
        return isinstance(schema.get("items"), dict) and strictly_describes_nested_values(schema["items"])
    if isinstance(schema_type, list):
        return bool(schema_type) and all(isinstance(value, str) for value in schema_type)
    return isinstance(schema_type, str)
