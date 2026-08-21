"""Ten-context ad-image estimation and learning loop."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, TypeVar

from PIL import Image

from .ad_provider import (
    AdCreativeSpec,
    AdProvider,
    GeneratedAdImage,
)
from .ad_renderer import InstagramAdRenderer
from .ad_repository import AdBatchRecord, AdSlotRecord, AdWorkflowRepository
from .model import Entity, EntityKind, RelationType
from .service import Commander


T = TypeVar("T")


class AdGenerationEngine:
    """Durable coordinator; one provider call is always attributable to one context."""

    def __init__(
        self,
        commander: Commander,
        repository: AdWorkflowRepository,
        provider: AdProvider,
        asset_directory: Path,
        renderer: InstagramAdRenderer | None = None,
    ) -> None:
        self.commander = commander
        self.repository = repository
        self.provider = provider
        self.asset_directory = asset_directory
        self.visual_directory = asset_directory / "ad-visuals"
        self.visual_directory.mkdir(parents=True, exist_ok=True)
        self.renderer = renderer or InstagramAdRenderer(asset_directory / "ad-posts")

    def enqueue_batch(
        self,
        *,
        idea_snapshot: Mapping[str, Any],
        chat_id: int,
        requested_by: str,
        idempotency_key: str,
        brand_kit_id: str,
    ) -> AdBatchRecord:
        idea = self._validate_idea(idea_snapshot)
        key = idempotency_key.strip()
        if not key or len(key) > 200:
            raise ValueError("idempotency_key must be 1-200 characters")
        existing = self.repository.idempotent_batch(key)
        if existing:
            return self.repository.batch(existing)
        brand_kit = self.commander.store.get_entity(brand_kit_id)
        superseded = any(
            edge.relation == RelationType.SUPERSEDES
            and edge.target_id == brand_kit_id
            for edge in self.commander.store.relationships()
        )
        if (
            brand_kit.kind != EntityKind.BRAND_KIT
            or brand_kit.attributes.get("status") != "approved"
            or superseded
        ):
            raise ValueError(
                "ad generation requires an active, approved, non-stale Brand Kit"
            )
        contexts = self.repository.active_contexts()
        if len(contexts) != 10 or [item.code for item in contexts] != [
            f"A{index:02d}" for index in range(1, 11)
        ]:
            raise ValueError("ad generation requires exactly active contexts A01-A10")

        with self.commander.store.transaction():
            source = self.commander.create_entity(
                EntityKind.SOURCE,
                {
                    "source_type": "idea_evolution_idea_snapshot",
                    "immutable": True,
                    "external_idea_id": idea["id"],
                    "snapshot": idea,
                },
                actor=requested_by,
                reasoning_summary="Captured the selected Idea Evolution idea as immutable ad provenance.",
            )
            campaign = self.commander.create_entity(
                EntityKind.CAMPAIGN,
                {
                    "campaign_type": "ten_context_ad_estimation",
                    "external_idea_id": idea["id"],
                    "concept_brand": idea["title"],
                    "context_count": 10,
                    "requested_by": requested_by,
                    "brand_kit_id": brand_kit.id,
                },
                actor=requested_by,
                reasoning_summary="Created a durable ten-context ad estimation campaign.",
                evidence_ids=(source.id,),
            )
            self.commander.relate(campaign, RelationType.DERIVED_FROM, source)
            self.commander.relate(campaign, RelationType.DERIVED_FROM, brand_kit)
            batch = AdBatchRecord(
                campaign_id=campaign.id,
                source_id=source.id,
                chat_id=chat_id,
                requested_by=requested_by,
                external_idea_id=int(idea["id"]),
                status="queued",
                brand_kit_id=brand_kit.id,
            )
            self.repository.create_batch(batch, key, contexts)
        return self.repository.batch(campaign.id)

    def process_once(self) -> int:
        batch = self.repository.claim_generation()
        if batch is not None:
            self._generate_batch(batch)
            return 1
        slot = self.repository.claim_conclusion()
        if slot is not None:
            self._conclude(slot)
            return 1
        return 0

    def record_estimate(
        self,
        *,
        creative_id: str,
        predicted_ctr: float,
        rating: int,
        comment: str,
        actor: str,
        artifact_digest: str | None = None,
        annotations: tuple[Mapping[str, Any], ...] = (),
    ) -> AdSlotRecord:
        if not 0 <= predicted_ctr <= 100:
            raise ValueError("predicted CTR must be between 0 and 100 percent")
        if rating not in range(1, 6):
            raise ValueError("rating must be an integer from 1 to 5")
        slot = self.repository.slot_by_creative(creative_id)
        batch = self.repository.batch(slot.batch_id)
        if batch.status != "awaiting_owner" or batch.current_position != slot.position:
            raise ValueError("estimate must reply to the currently active ad image")
        if slot.feedback_id is not None:
            raise ValueError("this ad image already has an owner estimate")
        creative = self.commander.store.get_entity(creative_id)
        if artifact_digest is None:
            artifact = next(
                self.commander.store.get_entity(edge.target_id)
                for edge in self.commander.store.relationships()
                if edge.source_id == creative_id
                and edge.relation == RelationType.GENERATED
                and self.commander.store.get_entity(edge.target_id).kind == EntityKind.ARTIFACT
            )
            artifact_digest = str(artifact.attributes["sha256"])
        with self.commander.store.transaction():
            feedback, _updates = self.commander.record_ad_estimate(
                creative=creative,
                predicted_ctr=predicted_ctr,
                rating=rating,
                comment=comment,
                actor=actor,
                artifact_digest=artifact_digest,
                annotations=annotations,
            )
            result = self.repository.save_estimate(
                creative_id,
                predicted_ctr=predicted_ctr,
                rating=rating,
                comment=comment.strip(),
                feedback_id=feedback.id,
            )
            self.repository.save_review_projection(
                feedback_id=feedback.id,
                creative_id=creative_id,
                artifact_digest=artifact_digest,
                rating=rating,
                comment=comment,
                predicted_ctr=predicted_ctr,
                annotations=annotations,
            )
        return result

    def continue_batch(self, batch_id: str) -> AdBatchRecord:
        self.repository.continue_batch(batch_id)
        return self.repository.batch(batch_id)

    def status(self, batch_id: str) -> Mapping[str, Any]:
        batch = self.repository.batch(batch_id)
        slots = self.repository.slots(batch_id)
        return {
            "batch_id": batch.campaign_id,
            "status": batch.status,
            "current_position": batch.current_position,
            "images": sum(item.creative_id is not None for item in slots),
            "estimates": sum(item.feedback_id is not None for item in slots),
            "conclusions": sum(item.conclusion_id is not None for item in slots),
            "last_error": batch.last_error,
        }

    def ranking(self, batch_id: str) -> tuple[Mapping[str, Any], ...]:
        batch = self.repository.batch(batch_id)
        if batch.status != "completed":
            raise ValueError("ad ranking is available after all ten conclusions are saved")
        slots = self.repository.slots(batch_id)
        if not all(item.predicted_ctr is not None and item.rating is not None for item in slots):
            raise RuntimeError("completed ad batch is missing owner estimates")
        ranked = sorted(
            slots,
            key=lambda item: (-float(item.predicted_ctr or 0), -int(item.rating or 0), item.position),
        )
        return tuple(
            {
                "rank": index,
                "position": item.position,
                "context_code": item.context.code,
                "context_name": item.context.name,
                "creative_id": item.creative_id,
                "predicted_ctr": item.predicted_ctr,
                "rating": item.rating,
                "comment": item.owner_comment,
                "conclusion": dict(
                    self.commander.store.get_entity(str(item.conclusion_id)).attributes
                ),
            }
            for index, item in enumerate(ranked, 1)
        )

    def contexts(self) -> tuple[Mapping[str, Any], ...]:
        return self.repository.contexts()

    def context(self, code: str) -> Mapping[str, Any]:
        return self.repository.context(code)

    def context_history(self, code: str) -> tuple[Mapping[str, Any], ...]:
        return self.repository.context_history(code)

    def revise_context(
        self, code: str, *, name: str, prompt: str, actor: str, note: str
    ) -> int:
        return self.repository.revise_context(
            code, name=name, prompt=prompt, actor=actor, note=note
        )

    def restore_context(self, code: str, version: int, *, actor: str) -> int:
        revision = next(
            (item for item in self.repository.context_history(code) if item["version"] == version),
            None,
        )
        if revision is None:
            raise ValueError(f"unknown {code.upper()} context revision v{version}")
        return self.revise_context(
            code,
            name=str(revision["name"]),
            prompt=str(revision["prompt"]),
            actor=actor,
            note=f"restored from v{version}",
        )

    def set_context_active(self, code: str, active: bool) -> None:
        self.repository.set_context_active(code, active)

    def import_metrics(
        self,
        *,
        batch_id: str,
        payload: Mapping[str, Any],
        actor: str,
    ) -> Mapping[str, Any]:
        batch = self.repository.batch(batch_id)
        if batch.status != "completed":
            raise ValueError("analytics can be imported only after all ten owner estimates")
        source_system = str(payload.get("source_system", "")).strip()
        import_id = str(payload.get("import_id", "")).strip()
        attribution = str(payload.get("attribution_window", "")).strip()
        if not source_system or not import_id or not attribution:
            raise ValueError("source_system, import_id, and attribution_window are required")
        if self.repository.metric_import_exists(source_system, import_id):
            return {"duplicate": True, "source_system": source_system, "import_id": import_id}
        captured_at = self._timestamp(payload.get("captured_at"))
        raw_metrics = payload.get("creatives")
        if not isinstance(raw_metrics, list) or not raw_metrics:
            raise ValueError("creatives must be a non-empty list")
        batch_creatives = {
            str(item.creative_id): item
            for item in self.repository.slots(batch_id)
            if item.creative_id is not None
        }
        parsed: list[tuple[AdSlotRecord, int, int, float | None]] = []
        seen: set[str] = set()
        for value in raw_metrics:
            if not isinstance(value, Mapping):
                raise ValueError("each Creative metric must be an object")
            creative_id = str(value.get("creative_id", ""))
            if creative_id in seen or creative_id not in batch_creatives:
                raise ValueError("Creative metrics must be unique and belong to the batch")
            seen.add(creative_id)
            impressions = int(value.get("impressions", -1))
            clicks = int(value.get("link_clicks", -1))
            spend = value.get("spend_minor")
            if impressions < 0 or clicks < 0 or clicks > impressions:
                raise ValueError("metrics require 0 <= link_clicks <= impressions")
            if spend is not None and int(spend) < 0:
                raise ValueError("spend_minor cannot be negative")
            parsed.append((batch_creatives[creative_id], impressions, clicks, None if spend is None else float(spend)))

        with self.commander.store.transaction():
            source = self.commander.create_entity(
                EntityKind.SOURCE,
                {
                    "source_type": "ad_analytics_import",
                    "immutable": True,
                    "source_system": source_system,
                    "import_id": import_id,
                    "captured_at": captured_at.isoformat(),
                    "attribution_window": attribution,
                },
                actor=actor,
                reasoning_summary="Captured an immutable ad analytics import.",
                evidence_ids=(batch_id,),
            )
            results = []
            for slot, impressions, clicks, spend in parsed:
                actual_ctr = 0.0 if impressions == 0 else clicks / impressions * 100
                values: dict[str, float] = {
                    "impressions": float(impressions),
                    "link_clicks": float(clicks),
                    "link_ctr_percent": actual_ctr,
                }
                if spend is not None:
                    values["spend_minor"] = spend
                metric_set = self.commander.create_entity(
                    EntityKind.METRIC_SET,
                    {
                        "values": values,
                        "attribution_window": attribution,
                        "captured_at": captured_at.isoformat(),
                        "factual": True,
                        "predicted_link_ctr_percent": slot.predicted_ctr,
                        "actual_minus_predicted_percent_points": (
                            None if slot.predicted_ctr is None else actual_ctr - slot.predicted_ctr
                        ),
                    },
                    actor=actor,
                    reasoning_summary="Recorded factual ad metrics and compared actual with owner estimate.",
                    evidence_ids=(source.id, str(slot.creative_id)),
                )
                creative = self.commander.store.get_entity(str(slot.creative_id))
                self.commander.relate(creative, RelationType.MEASURED_BY, metric_set)
                self.commander.relate(metric_set, RelationType.DERIVED_FROM, source)
                results.append(
                    {
                        "creative_id": slot.creative_id,
                        "metric_set_id": metric_set.id,
                        "actual_ctr": actual_ctr,
                        "predicted_ctr": slot.predicted_ctr,
                    }
                )
            self.repository.record_metric_import(
                source_id=source.id,
                batch_id=batch_id,
                source_system=source_system,
                import_id=import_id,
                captured_at=captured_at,
                attribution_window=attribution,
            )
        return {"duplicate": False, "source_id": source.id, "creatives": results}

    def _generate_batch(self, batch: AdBatchRecord) -> None:
        idea = self._idea_for_batch(batch)
        for slot in self.repository.slots(batch.campaign_id):
            if slot.creative_id is not None:
                continue
            try:
                spec = slot.spec or self._retry(
                    batch_id=batch.campaign_id,
                    position=slot.position,
                    phase="spec",
                    model=self.provider.spec_model,
                    request={"idea": idea, "context": slot.context.code, "version": slot.context.version},
                    operation=lambda: self.provider.generate_spec(idea, slot.context),
                    response=lambda value: value.to_dict(),
                )
                if spec.concept_name.casefold() != str(idea["title"]).casefold():
                    raise ValueError("provider changed the idea-native concept brand")
                if slot.spec is None:
                    self.repository.save_spec(batch.campaign_id, slot.position, spec)
                generated = self._retry(
                    batch_id=batch.campaign_id,
                    position=slot.position,
                    phase="image",
                    model=self.provider.image_model,
                    request={"spec": spec.to_dict(), "quality": "high", "size": "1536x1920"},
                    operation=lambda: self.provider.generate_image(spec),
                    response=self._image_response,
                )
                self._validate_generated_image(generated)
                visual_path = self.visual_directory / f"{batch.campaign_id}-{slot.position:02d}.png"
                visual_path.write_bytes(generated.content)
                with Image.open(visual_path) as visual:
                    if visual.size != (1536, 1920):
                        raise ValueError("provider bytes are not a 1536x1920 image")
                final_path, checksum = self.renderer.render(
                    slot_key=f"{batch.campaign_id}-{slot.position:02d}",
                    source_path=visual_path,
                    spec=spec,
                )
                self._persist_generated(batch, slot, idea, spec, generated, visual_path, final_path, checksum)
            except Exception as error:
                with self.commander.store.transaction():
                    self.repository.fail(batch.campaign_id, slot.position, self._error(error))
                    self._enqueue_failure(batch, slot.position, error)
                return
        with self.commander.store.transaction():
            self.repository.finish_generation(batch.campaign_id)
            first = self.repository.activate_review(batch.chat_id)
            if first is not None:
                self._enqueue_review(first)

    def _persist_generated(
        self,
        batch: AdBatchRecord,
        slot: AdSlotRecord,
        idea: Mapping[str, Any],
        spec: AdCreativeSpec,
        generated: GeneratedAdImage,
        visual_path: Path,
        final_path: Path,
        checksum: str,
    ) -> None:
        source = self.commander.store.get_entity(batch.source_id)
        campaign = self.commander.store.get_entity(batch.campaign_id)
        with self.commander.store.transaction():
            hypothesis = self.commander.create_hypothesis(
                claim=f"{slot.context.code} ({slot.context.name}) can make {idea['title']} compelling as an image ad.",
                success_metric="link_ctr_percent",
                threshold=2.0,
                scope="Owner-estimated pre-build image ad",
                source=source,
                actor=batch.requested_by,
                attributes={
                    "owner_agent": f"marketing.ad.{slot.context.code.lower()}",
                    "ad_context_code": slot.context.code,
                    "ad_context_version": slot.context.version,
                    "ad_batch_id": batch.campaign_id,
                },
            )
            creative = self.commander.create_entity(
                EntityKind.CREATIVE,
                {
                    "vertical": "instagram",
                    "creative_type": "ad_image_post",
                    "format": "feed_post_1080x1350",
                    "ad_batch_id": batch.campaign_id,
                    "ad_context_code": slot.context.code,
                    "ad_context_version": slot.context.version,
                    "producing_agent": f"marketing.ad.{slot.context.code.lower()}",
                    "spec": spec.to_dict(),
                },
                actor=batch.requested_by,
                reasoning_summary="Created one ad Creative from its producing context specification.",
                evidence_ids=(hypothesis.id,),
            )
            self.commander.relate(creative, RelationType.GENERATED, hypothesis)
            self.commander.relate(campaign, RelationType.CONTAINS, creative)
            for kind, value in (
                ("concept_name", spec.concept_name),
                ("angle", spec.angle),
                ("hook", spec.hook),
                ("supporting_copy", spec.supporting_copy),
                ("cta", spec.cta),
                ("visual_prompt", spec.visual_prompt),
            ):
                component = self._component(kind, value, hypothesis, batch.requested_by)
                self.commander.relate(creative, RelationType.CONTAINS, component)
            artifact = self.commander.create_entity(
                EntityKind.ARTIFACT,
                {
                    "media_type": "image/png",
                    "storage_uri": str(final_path),
                    "sha256": checksum,
                    "width": 1080,
                    "height": 1350,
                    "source_storage_uri": str(visual_path),
                    "source_width": generated.width,
                    "source_height": generated.height,
                    "source_sha256": hashlib.sha256(generated.content).hexdigest(),
                    "requested_model": generated.requested_model,
                    "resolved_model": generated.resolved_model,
                    "prompt": generated.prompt,
                    "quality": generated.quality,
                    "context_code": slot.context.code,
                    "context_version": slot.context.version,
                },
                actor=batch.requested_by,
                reasoning_summary="Saved a checksummed high-quality GPT Image visual and deterministic final post.",
                evidence_ids=(creative.id, hypothesis.id),
            )
            self.commander.relate(creative, RelationType.GENERATED, artifact)
            self.repository.save_generated(
                batch.campaign_id,
                slot.position,
                hypothesis_id=hypothesis.id,
                creative_id=creative.id,
                artifact_id=artifact.id,
                visual_path=str(visual_path),
                final_path=str(final_path),
            )

    def _conclude(self, slot: AdSlotRecord) -> None:
        batch = self.repository.batch(slot.batch_id)
        idea = self._idea_for_batch(batch)
        if slot.spec is None or slot.final_path is None or slot.feedback_id is None:
            error = RuntimeError("conclusion input is incomplete")
            with self.commander.store.transaction():
                self.repository.fail(slot.batch_id, slot.position, str(error))
                self._enqueue_failure(batch, slot.position, error)
            return
        try:
            conclusion = self._retry(
                batch_id=slot.batch_id,
                position=slot.position,
                phase="conclusion",
                model=self.provider.conclusion_model,
                request={
                    "context": slot.context.code,
                    "version": slot.context.version,
                    "creative_id": slot.creative_id,
                    "feedback_id": slot.feedback_id,
                    "predicted_ctr": slot.predicted_ctr,
                    "rating": slot.rating,
                    "image_sha256": hashlib.sha256(Path(slot.final_path).read_bytes()).hexdigest(),
                },
                operation=lambda: self.provider.conclude(
                    idea=idea,
                    context=slot.context,
                    spec=slot.spec,
                    image_path=Path(slot.final_path),
                    predicted_ctr=float(slot.predicted_ctr),
                    rating=int(slot.rating),
                    comment=slot.owner_comment,
                ),
                response=lambda value: value.to_dict(),
            )
            with self.commander.store.transaction():
                insight = self.commander.create_entity(
                    EntityKind.INSIGHT,
                    {
                        "insight_type": "ad_context_conclusion",
                        "ad_batch_id": slot.batch_id,
                        "creative_id": slot.creative_id,
                        "producing_context_code": slot.context.code,
                        "producing_context_version": slot.context.version,
                        **conclusion.to_dict(),
                    },
                    actor=f"marketing.ad.{slot.context.code.lower()}",
                    reasoning_summary="The producing context interpreted its final image using stored owner feedback.",
                    evidence_ids=(str(slot.creative_id), slot.feedback_id, str(slot.artifact_id)),
                )
                feedback = self.commander.store.get_entity(slot.feedback_id)
                creative = self.commander.store.get_entity(str(slot.creative_id))
                artifact = self.commander.store.get_entity(str(slot.artifact_id))
                self.commander.relate(insight, RelationType.DERIVED_FROM, feedback)
                self.commander.relate(insight, RelationType.DERIVED_FROM, artifact)
                self.commander.relate(insight, RelationType.EVALUATES, creative)
                next_slot = self.repository.finish_conclusion(str(slot.creative_id), insight.id)
                if next_slot is not None:
                    self._enqueue_review(next_slot)
                else:
                    self._enqueue_ranking(batch)
                    queued = self.repository.activate_review(batch.chat_id)
                    if queued is not None:
                        self._enqueue_review(queued)
        except Exception as error:
            with self.commander.store.transaction():
                self.repository.fail(slot.batch_id, slot.position, self._error(error))
                self._enqueue_failure(batch, slot.position, error)

    def _retry(
        self,
        *,
        batch_id: str,
        position: int,
        phase: str,
        model: str,
        request: Mapping[str, Any],
        operation: Callable[[], T],
        response: Callable[[T], Mapping[str, Any]],
    ) -> T:
        digest = hashlib.sha256(
            json.dumps(dict(request), sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                result = operation()
            except Exception as error:
                last_error = error
                self.repository.record_execution(
                    batch_id=batch_id,
                    position=position,
                    phase=phase,
                    attempt=attempt,
                    status="failed",
                    model=model,
                    request_digest=digest,
                    error=self._error(error),
                )
            else:
                self.repository.record_execution(
                    batch_id=batch_id,
                    position=position,
                    phase=phase,
                    attempt=attempt,
                    status="succeeded",
                    model=model,
                    request_digest=digest,
                    response=response(result),
                )
                return result
        assert last_error is not None
        raise RuntimeError(
            f"{phase} failed after initial attempt plus two recoveries: {self._error(last_error)}"
        ) from last_error

    def _component(self, kind: str, value: str, hypothesis: Entity, actor: str) -> Entity:
        existing = next(
            (
                item
                for item in self.commander.store.entities(EntityKind.CREATIVE_COMPONENT)
                if item.attributes.get("vertical") == "instagram_ad"
                and item.attributes.get("component_kind") == kind
                and item.attributes.get("value") == value
            ),
            None,
        )
        if existing is not None:
            return existing
        return self.commander.create_entity(
            EntityKind.CREATIVE_COMPONENT,
            {"vertical": "instagram_ad", "component_kind": kind, "value": value},
            actor=actor,
            reasoning_summary="Created a reusable ad creative component.",
            evidence_ids=(hypothesis.id,),
        )

    def _enqueue_review(self, slot: AdSlotRecord) -> None:
        if slot.final_path is None or slot.creative_id is None:
            raise RuntimeError("review slot is missing its final image or Creative UUID")
        self.commander.store.enqueue_outbox(
            "telegram.send_photo",
            slot.artifact_id,
            {
                "chat_id": self.repository.batch(slot.batch_id).chat_id,
                "path": slot.final_path,
                "caption": (
                    f"Ad batch {slot.batch_id}\n"
                    f"Image {slot.position}/10 · {slot.context.code} v{slot.context.version} "
                    f"— {slot.context.name}\nCreative {slot.creative_id}\n\n"
                    "Reply to this image with:\n"
                    "/estimate <predicted CTR%> <1-5 rating> [feedback]"
                ),
                "creative_id": slot.creative_id,
            },
        )

    def _enqueue_failure(self, batch: AdBatchRecord, position: int, error: Exception) -> None:
        self.commander.store.enqueue_outbox(
            "telegram.send_message",
            batch.campaign_id,
            {
                "chat_id": batch.chat_id,
                "text": (
                    f"Ad batch {batch.campaign_id} paused at image {position}/10. "
                    f"{self._error(error)}\nFix provider/configuration, then use "
                    f"/ads continue {batch.campaign_id}. Completed work is preserved."
                )[:4096],
            },
        )

    def _enqueue_ranking(self, batch: AdBatchRecord) -> None:
        lines = [f"Ad batch {batch.campaign_id} completed: 10/10 reviewed."]
        for item in self.ranking(batch.campaign_id):
            conclusion = item["conclusion"]
            lines.append(
                f"{item['rank']}. {item['context_code']} {item['predicted_ctr']:g}% · "
                f"{item['rating']}/5 · {item['creative_id']}\n"
                f"   Feedback: {str(conclusion['feedback_interpretation'])[:90]}\n"
                f"   Effective: {str(conclusion['effective_elements'])[:80]}\n"
                f"   Improve: {str(conclusion['improvements'])[:80]}\n"
                f"   Intent fulfilled: {'yes' if conclusion['fulfilled_context_intent'] else 'no'}\n"
                f"   Next: {str(conclusion['recommended_direction'])[:90]}"
            )
        self.commander.store.enqueue_outbox(
            "telegram.send_message",
            batch.campaign_id,
            {"chat_id": batch.chat_id, "text": "\n".join(lines)[:4096]},
        )

    def _idea_for_batch(self, batch: AdBatchRecord) -> Mapping[str, Any]:
        source = self.commander.store.get_entity(batch.source_id)
        return self._validate_idea(dict(source.attributes["snapshot"]))

    @staticmethod
    def _validate_idea(value: Mapping[str, Any]) -> dict[str, Any]:
        try:
            idea_id = int(value["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("idea snapshot requires a numeric id") from error
        title = str(value.get("title", "")).strip()
        one_liner = str(value.get("one_liner", "")).strip()
        details = value.get("details")
        if not title or not one_liner or not isinstance(details, Mapping):
            raise ValueError("idea snapshot requires title, one_liner, and details")
        if len(title) > 80 or len(one_liner) > 1000:
            raise ValueError("idea title or one_liner exceeds the ad snapshot limit")
        return {**dict(value), "id": idea_id, "title": title, "one_liner": one_liner, "details": dict(details)}

    @staticmethod
    def _validate_generated_image(value: GeneratedAdImage) -> None:
        if value.requested_model != "gpt-image-2" and not value.requested_model.startswith("deterministic-"):
            raise ValueError("ad image provider must request gpt-image-2; model fallback is forbidden")
        if value.quality != "high" or (value.width, value.height) != (1536, 1920):
            raise ValueError("ad image provider must return high-quality 1536x1920 output")
        if not value.content:
            raise ValueError("ad image provider returned empty content")

    @staticmethod
    def _image_response(value: GeneratedAdImage) -> Mapping[str, Any]:
        return {
            "requested_model": value.requested_model,
            "resolved_model": value.resolved_model,
            "quality": value.quality,
            "width": value.width,
            "height": value.height,
            "sha256": hashlib.sha256(value.content).hexdigest(),
        }

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("captured_at must be an ISO-8601 timestamp") from error
        if result.tzinfo is None:
            raise ValueError("captured_at must include a timezone")
        return result

    @staticmethod
    def _error(error: Exception) -> str:
        return f"{type(error).__name__}: {error}"[:500]
