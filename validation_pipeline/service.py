"""Product Brief generation feeding the Result-only content pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .domain import ProductBriefV1, product_brief_schema
from .provider import StructuredBridge
from .repository import ValidationRepository


class ValidationRunner:
    def __init__(
        self,
        repository: ValidationRepository,
        bridge: StructuredBridge,
        *,
        product_brief_skill_path: Path,
    ) -> None:
        self.repository = repository
        self.bridge = bridge
        self.product_brief_skill_path = product_brief_skill_path
        self._skill()

    def _skill(self) -> str:
        path = self.product_brief_skill_path
        if not path.is_file():
            raise RuntimeError(f"canonical Product Brief skill is unavailable: {path}")
        parts = [path.read_text(encoding="utf-8")]
        references = path.parent / "references"
        if references.is_dir():
            for item in sorted(references.glob("*.md")):
                parts.append(f"\nREFERENCE {item.name}:\n{item.read_text(encoding='utf-8')}")
        content = "\n".join(parts)
        if len(content) > 40_000:
            raise RuntimeError("Product Brief skill context exceeds its explicit limit")
        return content

    def verify_ready(self) -> dict[str, Any]:
        return {"ready": True, "market_research": False, **self.bridge.capabilities()}

    def generate_brief(self, brief_id: str, *, operation_reserved: bool = False) -> dict[str, Any]:
        brief = self.repository.get_brief(brief_id)
        if brief["status"] not in {"queued", "failed"}:
            raise ValueError("only a queued or failed Product Brief can be generated")
        if not operation_reserved:
            self.repository.acquire_operation("product_brief", brief_id)
        attempt_id = ""
        try:
            attempt_id, attempt_number = self.repository.start_attempt(brief_id, stage="product_brief")
            source = self.repository.source(brief_id)
            base = None
            correction = None
            mode = "product_brief"
            if brief.get("base_brief_id"):
                base = self.repository.get_brief(brief["base_brief_id"])
                if not base.get("document"):
                    raise RuntimeError("base Product Brief is unavailable")
                correction = self.repository.feedback(brief["feedback_id"])
                mode = "product_brief_revision"
            payload = {
                "brief_id": brief_id,
                "raw_idea": source["content"],
                "base_brief": None if base is None else base["document"],
                "owner_correction": correction,
            }
            invocation = self.repository.create_invocation(
                target_id=brief_id,
                attempt_id=attempt_id,
                mode=mode,
                idempotency_key=f"{brief_id}:{mode}:attempt-{attempt_number}",
                request=payload,
            )
            try:
                result = self.bridge.generate(
                    mode=mode,
                    system_prompt=(
                        "Use the canonical Product Brief Generator skill below. Return one strict "
                        "ProductBriefV1 object. The raw idea is the only business input. Infer Ukrainian "
                        "or English, choose one hypothesis, include one honest low-friction offer, and "
                        "never invent research, testimonials, ratings, results, or proof. A correction "
                        "returns a complete immutable replacement.\n\nCANONICAL_SKILL:\n" + self._skill()
                    ),
                    input_payload=payload,
                    output_schema=product_brief_schema(),
                    prompt_version=f"product_brief_v1:{mode}",
                    idempotency_key=f"{brief_id}:{mode}",
                )
                document = ProductBriefV1.from_dict(result, raw_idea=source["content"])
                self.repository.complete_invocation(
                    invocation["id"], document.to_dict(), self.bridge.last_invocation
                )
            except Exception as error:
                self.repository.fail_invocation(invocation["id"], error)
                raise
            self.repository.finish_brief(
                brief_id, attempt_id, document.to_dict(), document.digest, document.quality_gates
            )
            return self.repository.get_brief(brief_id)
        except Exception as error:
            if attempt_id:
                self.repository.fail_attempt(brief_id, attempt_id, stage="product_brief", error=error)
            raise
        finally:
            self.repository.release_operation(brief_id)


def validate_create_input(value: Mapping[str, Any]) -> dict[str, str]:
    from uuid import UUID

    if set(value) != {"request_id", "raw_idea"}:
        raise ValueError("Product Brief request fields do not match the v1 contract")
    raw = str(value.get("raw_idea") or "").strip()
    if not 1 <= len(raw) <= 10_000:
        raise ValueError("raw_idea must contain 1-10000 characters")
    return {"request_id": str(UUID(str(value["request_id"]))), "raw_idea": raw}


def validate_revision_input(value: Mapping[str, Any]) -> dict[str, str]:
    from uuid import UUID

    if set(value) != {"request_id", "instruction"}:
        raise ValueError("Product Brief correction fields do not match the v1 contract")
    instruction = str(value.get("instruction") or "").strip()
    if not 1 <= len(instruction) <= 2000:
        raise ValueError("instruction must contain 1-2000 characters")
    return {"request_id": str(UUID(str(value["request_id"]))), "instruction": instruction}
