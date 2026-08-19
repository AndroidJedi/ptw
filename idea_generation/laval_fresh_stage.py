"""Fresh, schema-bound LLM calls with append-only invocation audit."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from commander.ids import new_uuid7

from .laval_domain import input_hash
from .laval_repository import LavalRepository
from .laval_schemas import output_schema
from .provider import StructuredProvider


class InvalidStructuredResponse(ValueError):
    """The provider returned JSON that violates a stage's semantic contract."""


class FreshStageRunner:
    def __init__(self, repository: LavalRepository, provider: StructuredProvider) -> None:
        self.repository = repository
        self.provider = provider
        self.last_attempt_count = 0

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
        validator: Callable[[dict[str, Any]], bool | str] | None = None,
    ) -> dict[str, Any] | None:
        context_hash = input_hash(payload)
        schema = output_schema(mode, required)
        schema_hash = hashlib.sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        model = str(getattr(self.provider, "model_name", "llm"))
        prepare = getattr(self.provider, "prepare_invocation", None)
        max_attempts = 1 if allow_fallback else 2
        self.last_attempt_count = 0
        for attempt in range(1, max_attempts + 1):
            self.last_attempt_count = attempt
            session_id = new_uuid7()
            attempt_version = (
                prompt_template_version
                if attempt == 1
                else f"{prompt_template_version}:automatic-retry-{attempt}"
            )
            attempt_prompt = prompt if attempt == 1 else (
                prompt
                + "\n\nAutomatic retry: the prior response failed application validation. "
                  "Return the complete requested result again, preserve exact supplied IDs and counts, "
                  "and do not invent or transform identifiers."
            )
            if callable(prepare):
                prepare(attempt_version, context_hash)
            last_invocation = getattr(self.provider, "last_invocation", None)
            if isinstance(last_invocation, dict):
                last_invocation.clear()
            try:
                result = self.provider.generate_structured(
                    mode, attempt_prompt, payload, schema
                )
                shape_valid = (
                    isinstance(result, dict)
                    and isinstance(result.get(required), (dict, list))
                )
                validation = validator(result) if shape_valid and validator is not None else shape_valid
                valid = shape_valid and validation is True
                if not valid:
                    detail = validation if isinstance(validation, str) else (
                        f"response must contain a valid {required!r} value"
                    )
                    raise InvalidStructuredResponse(str(detail))
                self.repository.record_llm_invocation(
                    run_id,
                    stage,
                    mode,
                    prompt_template_version=attempt_version,
                    context_hash=context_hash,
                    output_schema_hash=schema_hash,
                    model=model,
                    session_id=session_id,
                    provider_session_id=str(
                        (getattr(self.provider, "last_invocation", None) or {}).get("session_id") or ""
                    ) or None,
                    result_status="success",
                    error_type=None,
                )
                return result
            except Exception as error:
                self.repository.record_llm_invocation(
                    run_id,
                    stage,
                    mode,
                    prompt_template_version=attempt_version,
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
                if attempt == max_attempts:
                    raise
        raise AssertionError("fresh stage retry loop exhausted without a result")
