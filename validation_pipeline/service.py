"""Single-call Product Brief generation and five-creative execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from commander.ids import new_uuid7

from .domain import CreativeSetV1, ProductBriefV1, creative_set_schema, product_brief_schema
from .images import PexelsClient, SquareCreativeRenderer
from .notifications import FailureNotificationClient
from .provider import StructuredBridge
from .repository import ValidationRepository


class ValidationRunner:
    def __init__(
        self,
        repository: ValidationRepository,
        bridge: StructuredBridge,
        pexels: PexelsClient,
        renderer: SquareCreativeRenderer,
        *,
        product_brief_skill_path: Path,
        ad_creative_skill_path: Path,
        failure_notifier: FailureNotificationClient | None = None,
    ) -> None:
        self.repository = repository
        self.bridge = bridge
        self.pexels = pexels
        self.renderer = renderer
        self.product_brief_skill = self._skill(product_brief_skill_path)
        self.ad_creative_skill = self._skill(ad_creative_skill_path)
        self.failure_notifier = failure_notifier

    @staticmethod
    def _skill(path: Path) -> str:
        if not path.is_file():
            raise RuntimeError(f"canonical skill is unavailable: {path}")
        parts = [path.read_text(encoding="utf-8")]
        references = path.parent / "references"
        if references.is_dir():
            for item in sorted(references.glob("*.md")):
                parts.append(f"\nREFERENCE {item.name}:\n{item.read_text(encoding='utf-8')}")
        return "\n".join(parts)[:40_000]

    def verify_ready(self) -> dict[str, Any]:
        return {
            "ready": True,
            "market_research": False,
            "stock_provider": "pexels",
            **self.bridge.capabilities(),
        }

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
                        "Use the canonical Product Brief Generator skill below. Return only one strict ProductBriefV1 object. "
                        "The raw idea is the only business input. Infer Ukrainian or English from that idea, defaulting to "
                        "English when ambiguous. Choose one promising hypothesis, not alternatives. Always include one strong, "
                        "low-friction validation offer. The offer is marketing, not a product change. Do not research, browse, "
                        "use SEO or YouTube data, invent testimonials, ratings, customer results, or proof. A correction returns "
                        "a complete coherent replacement.\n\nCANONICAL_SKILL:\n" + self.product_brief_skill
                    ),
                    input_payload=payload,
                    output_schema=product_brief_schema(),
                    prompt_version=f"product_brief_v1:{mode}",
                )
                document = ProductBriefV1.from_dict(result, raw_idea=source["content"])
                self.repository.complete_invocation(invocation["id"], document.to_dict(), self.bridge.last_invocation)
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

    def generate_batch(self, batch_id: str, *, operation_reserved: bool = False) -> dict[str, Any]:
        batch = self.repository.get_batch(batch_id)
        if batch["status"] not in {"queued", "failed"}:
            raise ValueError("only a queued or failed creative batch can be generated")
        if not operation_reserved:
            self.repository.acquire_operation("ad_creative_batch", batch_id)
        attempt_id = ""
        try:
            attempt_id, attempt_number = self.repository.start_attempt(batch_id, stage="ad_creative_batch")
            brief = self.repository.get_brief(batch["brief_id"])
            if not brief["approved"] or not brief.get("document"):
                raise RuntimeError("creative generation requires the approved Product Brief")
            # The runtime business payload contains the Product Brief and nothing else.
            payload = {"brief": {"brief_id": brief["brief_id"], **dict(brief["document"])}}
            invocation = self.repository.create_invocation(
                target_id=batch_id,
                attempt_id=attempt_id,
                mode="ad_creative_batch",
                idempotency_key=f"{batch_id}:ad_creative_batch:attempt-{attempt_number}",
                request=payload,
            )
            try:
                result = self.bridge.generate(
                    mode="ad_creative_batch",
                    system_prompt=(
                        "Use the canonical Ad Creative Generator skill below. Return only one strict CreativeSetV1 object. "
                        "Generate exactly five complete creatives in the required fixed angle order. Use only the approved "
                        "Product Brief as business input. Copy its CTA and offer exactly into the corresponding fields of "
                        "every creative. Keep the offer wording visibly intact in each hook or primary_text; sentence "
                        "punctuation may surround it but must not change its words. "
                        "Describe authentic real photography and emit useful English Pexels search queries even when the ad "
                        "copy is Ukrainian. Apply the immutable Natal identity. For each proposed visual, silently generate "
                        "multiple headline candidates, apply the skill's semantic-alignment self-check, and return only the "
                        "strongest hook in the strict output. Do not create AI artwork, publish an ad, invent proof, or "
                        "optimize from performance.\n\n"
                        "CANONICAL_SKILL:\n" + self.ad_creative_skill
                    ),
                    input_payload=payload,
                    output_schema=creative_set_schema(brief=brief["document"]),
                    prompt_version="ad_creative_batch_v3_natal_visual_alignment",
                )
                creative_set = CreativeSetV1.from_dict(result, brief=brief["document"])
                self.repository.complete_invocation(
                    invocation["id"], {"schema_version": 1, "creatives": list(creative_set.value)},
                    self.bridge.last_invocation,
                )
            except Exception as error:
                self.repository.fail_invocation(invocation["id"], error)
                raise
            prepared = self._prepare_assets(creative_set.value, brief["document"])
            self.repository.finish_batch(
                batch_id,
                attempt_id,
                brief_id=brief["brief_id"],
                creatives=prepared,
                digest=creative_set.digest,
                quality={**creative_set.quality_gates, "five_real_assets": True, "square_jpegs": True},
            )
            return self.repository.get_batch(batch_id)
        except Exception as error:
            if attempt_id:
                self.repository.fail_attempt(batch_id, attempt_id, stage="ad_creative_batch", error=error)
                if self.failure_notifier is not None:
                    try:
                        self.failure_notifier.notify(
                            target_id=batch_id,
                            attempt_id=attempt_id,
                            stage="ad_creative_batch",
                        )
                    except Exception as notification_error:
                        self.repository.record_notification_callback_failure(
                            batch_id,
                            attempt_id,
                            error=notification_error,
                        )
            raise
        finally:
            self.repository.release_operation(batch_id)

    def _prepare_assets(
        self, creatives: Sequence[Mapping[str, Any]], brief: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        used: set[str] = set()
        prepared = []
        for creative in creatives:
            photo, source = self.pexels.select(
                creative["image_search_query"], creative["image_category"], used_ids=used
            )
            used.add(photo.photo_id)
            asset, digest = self.renderer.render(
                source,
                hook=creative["hook"],
                offer=brief["offer"],
                cta=creative["cta"],
                crop_focus=creative["crop_focus"],
            )
            prepared.append({
                "creative_id": new_uuid7(),
                "asset_id": new_uuid7(),
                "content": dict(creative),
                "photo": photo.source_metadata(),
                "asset_bytes": asset,
                "asset_digest": digest,
            })
        return prepared


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
