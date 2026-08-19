"""Fresh, schema-bound LLM calls with append-only invocation audit."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from commander.ids import new_uuid7

from .laval_domain import input_hash
from .laval_repository import LavalRepository
from .provider import StructuredProvider


class FreshStageRunner:
    def __init__(self, repository: LavalRepository, provider: StructuredProvider) -> None:
        self.repository = repository
        self.provider = provider

    def run(
        self,
        run_id: str,
        stage: str,
        mode: str,
        prompt: str,
        payload: dict[str, Any],
        required: str,
        *,
        prompt_template_version: str,
        allow_fallback: bool = True,
        validator: Callable[[dict[str, Any]], bool] | None = None,
    ) -> dict[str, Any] | None:
        session_id = new_uuid7()
        context_hash = input_hash(payload)
        value_type = "object" if required in {"owner_dna", "dossier"} else "array"
        output_schema = {
            "type": "object",
            "properties": {required: {"type": value_type}},
            "required": [required],
            "additionalProperties": False,
        }
        schema_hash = hashlib.sha256(
            json.dumps(output_schema, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        model = str(getattr(self.provider, "model_name", "llm"))
        prepare = getattr(self.provider, "prepare_invocation", None)
        if callable(prepare):
            prepare(prompt_template_version, context_hash)
        try:
            result = self.provider.generate_structured(
                mode, prompt, payload, output_schema
            )
            valid = (
                isinstance(result, dict)
                and isinstance(result.get(required), (dict, list))
                and (validator is None or validator(result))
            )
            if not valid and not allow_fallback:
                raise ValueError("provider response did not match the required schema")
            status = "success" if valid else "fallback"
            self.repository.record_llm_invocation(
                run_id,
                stage,
                mode,
                prompt_template_version=prompt_template_version,
                context_hash=context_hash,
                output_schema_hash=schema_hash,
                model=model,
                session_id=session_id,
                provider_session_id=str(
                    (getattr(self.provider, "last_invocation", None) or {}).get("session_id") or ""
                ) or None,
                result_status=status,
                error_type=None if valid else "InvalidStructuredResponse",
            )
            if valid:
                return result
            return None
        except Exception as error:
            self.repository.record_llm_invocation(
                run_id,
                stage,
                mode,
                prompt_template_version=prompt_template_version,
                context_hash=context_hash,
                output_schema_hash=schema_hash,
                model=model,
                session_id=session_id,
                provider_session_id=str(
                    (getattr(self.provider, "last_invocation", None) or {}).get("session_id") or ""
                ) or None,
                result_status="fallback" if allow_fallback else "failed",
                error_type=type(error).__name__,
            )
            if allow_fallback:
                return None
            raise
