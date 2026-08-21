"""Typed Commander graph publication for Branding runs and Brand Kits."""

from __future__ import annotations

from datetime import date
import re
from typing import Any, Mapping, Sequence

from .model import Entity, EntityKind, RelationType
from .research import ResearchFinding, ResearchKnowledgeService
from .research_agents import RESEARCH_AGENTS
from .service import Commander
from .store import KnowledgeStore


UUID_RE = re.compile(r"[0-9a-fA-F-]{36}")
DIGEST_RE = re.compile(r"[0-9a-f]{64}")


class BrandPublishingService:
    """Publish brand research and immutable design artifacts through Commander."""

    def __init__(self, commander: Commander, store: KnowledgeStore) -> None:
        self.commander = commander
        self.store = store

    @staticmethod
    def _uuid(value: object, label: str) -> str:
        result = str(value or "")
        if not UUID_RE.fullmatch(result):
            raise ValueError(f"{label} must be a UUID")
        return result

    def record_sources(self, findings: Sequence[Mapping[str, Any]]) -> dict[str, str]:
        if len(findings) > 100:
            raise ValueError("branding supports at most 100 source findings")
        research = ResearchKnowledgeService(self.commander)
        agent = RESEARCH_AGENTS["design"]
        existing = {
            str(item.attributes.get("external_id")): item
            for item in self.store.entities(EntityKind.SOURCE)
            if item.attributes.get("external_id")
        }
        result: dict[str, str] = {}
        with self.store.transaction():
            for raw in findings:
                external_id = str(raw.get("external_id") or "").strip()
                if not external_id or len(external_id) > 200:
                    raise ValueError("branding source external_id is required")
                source = existing.get(external_id)
                if source is None:
                    published = raw.get("published_on")
                    source = research.record_finding(
                        ResearchFinding(
                            title=str(raw.get("title") or "")[:1000],
                            source_uri=str(raw.get("source_uri") or "")[:4000],
                            finding_summary=str(raw.get("finding_summary") or "")[:10_000],
                            publisher=str(raw.get("publisher") or "")[:1000],
                            published_on=date.fromisoformat(str(published)) if published else None,
                            credibility=float(raw.get("credibility", .6)),
                            external_id=external_id,
                            research_type="brand_design",
                        ),
                        actor="brand-runner",
                        agent=agent,
                    )
                    existing[external_id] = source
                result[external_id] = source.id
        return result

    def publish_direction(self, request: Mapping[str, Any]) -> dict[str, str]:
        run_id = self._uuid(request.get("run_id"), "run_id")
        direction_id = self._uuid(request.get("direction_id"), "direction_id")
        manifest = request.get("manifest")
        if not isinstance(manifest, Mapping):
            raise ValueError("manifest must be an object")
        name = str(manifest.get("name") or "").strip()
        if not name or len(name) > 100:
            raise ValueError("brand direction name must contain 1-100 characters")
        artifact = request.get("artifact")
        if not isinstance(artifact, Mapping):
            raise ValueError("artifact must be an object")
        digest = str(artifact.get("sha256") or "")
        if not DIGEST_RE.fullmatch(digest):
            raise ValueError("logo artifact sha256 is invalid")
        existing = next((
            item for item in self.store.entities(EntityKind.BRAND_DIRECTION)
            if item.attributes.get("brand_direction_external_id") == direction_id
        ), None)
        if existing is not None:
            creative = next(
                self.store.get_entity(edge.target_id)
                for edge in self.store.relationships()
                if edge.source_id == existing.id
                and edge.relation == RelationType.CONTAINS
                and self.store.get_entity(edge.target_id).kind == EntityKind.CREATIVE
            )
            generated = next(
                self.store.get_entity(edge.target_id)
                for edge in self.store.relationships()
                if edge.source_id == creative.id
                and edge.relation == RelationType.GENERATED
                and self.store.get_entity(edge.target_id).kind == EntityKind.ARTIFACT
            )
            return {"direction_id": existing.id, "creative_id": creative.id, "artifact_id": generated.id}

        hypotheses = [self.store.get_entity(self._uuid(value, "hypothesis_id")) for value in request.get("hypothesis_ids") or []]
        sources = [self.store.get_entity(self._uuid(value, "source_id")) for value in request.get("source_ids") or []]
        if not hypotheses or any(item.kind != EntityKind.HYPOTHESIS for item in hypotheses):
            raise ValueError("brand direction requires published source hypotheses")
        if not sources or any(item.kind != EntityKind.SOURCE for item in sources):
            raise ValueError("brand direction requires permanent source entities")

        with self.store.transaction():
            direction = self.commander.create_entity(
                EntityKind.BRAND_DIRECTION,
                {
                    "brand_run_id": run_id,
                    "brand_direction_external_id": direction_id,
                    "source_laval_run_id": str(request.get("source_laval_run_id") or ""),
                    "name": name,
                    "manifest": dict(manifest),
                    "evaluation": dict(request.get("evaluation") or {}),
                    "status": "awaiting_review",
                },
                actor="brand-runner",
                reasoning_summary="Published one evidence-backed brand direction for owner review.",
                evidence_ids=tuple(item.id for item in (*hypotheses, *sources)),
            )
            for item in (*hypotheses, *sources):
                self.commander.relate(direction, RelationType.DERIVED_FROM, item)

            components: list[Entity] = []
            component_values = {
                "brand_name": name,
                "palette": manifest.get("palette") or {},
                "typography": manifest.get("typography") or {},
                "voice": manifest.get("voice") or {},
                "design_principles": manifest.get("design_principles") or [],
                "ui_system": manifest.get("ui_system") or {},
            }
            for component_kind, value in component_values.items():
                component = self.commander.create_entity(
                    EntityKind.CREATIVE_COMPONENT,
                    {
                        "component_kind": component_kind,
                        "scope": "brand_identity",
                        "value": value,
                        "brand_direction_id": direction.id,
                    },
                    actor="brand-runner",
                    reasoning_summary="Created a reusable component of a brand direction.",
                    evidence_ids=(direction.id,),
                )
                self.commander.relate(direction, RelationType.CONTAINS, component)
                components.append(component)

            creative = self.commander.create_entity(
                EntityKind.CREATIVE,
                {
                    "creative_type": "brand_logo",
                    "brand_run_id": run_id,
                    "brand_direction_id": direction.id,
                    "name": name,
                    "status": "generated",
                },
                actor="brand-runner",
                reasoning_summary="Created a logo Creative from the brand direction.",
                evidence_ids=(direction.id,),
            )
            self.commander.relate(direction, RelationType.CONTAINS, creative)
            for component in components:
                if component.attributes.get("component_kind") in {"palette", "typography", "design_principles"}:
                    self.commander.relate(creative, RelationType.CONTAINS, component)
            logo_artifact = self.commander.create_entity(
                EntityKind.ARTIFACT,
                {
                    "artifact_type": "brand_logo_png",
                    "sha256": digest,
                    "storage_uri": str(artifact.get("storage_uri") or ""),
                    "mime_type": "image/png",
                    "width": int(artifact.get("width") or 0),
                    "height": int(artifact.get("height") or 0),
                    "generation": dict(artifact.get("generation") or {}),
                },
                actor="brand-runner",
                reasoning_summary="Registered an immutable logo image artifact.",
                evidence_ids=(direction.id, creative.id),
            )
            self.commander.relate(creative, RelationType.GENERATED, logo_artifact)
            self.commander.relate(direction, RelationType.GENERATED, logo_artifact)
        return {"direction_id": direction.id, "creative_id": creative.id, "artifact_id": logo_artifact.id}

    def approve(self, request: Mapping[str, Any]) -> dict[str, str | None]:
        run_id = self._uuid(request.get("run_id"), "run_id")
        external_direction_id = self._uuid(request.get("direction_id"), "direction_id")
        direction = next((
            item for item in self.store.entities(EntityKind.BRAND_DIRECTION)
            if item.attributes.get("brand_direction_external_id") == external_direction_id
            and item.attributes.get("brand_run_id") == run_id
        ), None)
        if direction is None:
            raise KeyError("brand direction is not published")
        existing = next((
            item for item in self.store.entities(EntityKind.BRAND_KIT)
            if item.attributes.get("brand_run_id") == run_id
        ), None)
        if existing is not None:
            artifact_id = next((
                edge.target_id for edge in self.store.relationships()
                if edge.source_id == existing.id and edge.relation == RelationType.GENERATED
            ), None)
            return {"brand_kit_id": existing.id, "artifact_id": artifact_id, "previous_brand_kit_id": existing.attributes.get("previous_brand_kit_id")}

        run_directions = [
            item for item in self.store.entities(EntityKind.BRAND_DIRECTION)
            if item.attributes.get("brand_run_id") == run_id
        ]
        if len(run_directions) != 3:
            raise ValueError("Brand Kit approval requires exactly three published directions")
        current_feedback: list[Entity] = []
        for item in run_directions:
            creative = next((
                self.store.get_entity(edge.target_id)
                for edge in self.store.relationships()
                if edge.source_id == item.id
                and edge.relation == RelationType.CONTAINS
                and self.store.get_entity(edge.target_id).kind == EntityKind.CREATIVE
            ), None)
            if creative is None:
                raise ValueError("every brand direction requires a logo Creative")
            reviews = [
                review for review in self.store.entities(EntityKind.HUMAN_FEEDBACK)
                if review.attributes.get("creative_id") == creative.id
            ]
            if not reviews:
                raise ValueError("current owner feedback is required for all three logos")
            current_feedback.append(max(reviews, key=lambda review: review.created_at))
        zip_artifact = request.get("artifact")
        if not isinstance(zip_artifact, Mapping) or not DIGEST_RE.fullmatch(str(zip_artifact.get("sha256") or "")):
            raise ValueError("Brand Kit artifact is invalid")
        prior = [
            item for item in self.store.entities(EntityKind.BRAND_KIT)
            if item.attributes.get("source_laval_run_id") == request.get("source_laval_run_id")
        ]
        previous = max(prior, key=lambda item: item.created_at) if prior else None
        with self.store.transaction():
            kit = self.commander.create_entity(
                EntityKind.BRAND_KIT,
                {
                    "brand_run_id": run_id,
                    "source_laval_run_id": str(request.get("source_laval_run_id") or ""),
                    "source_snapshot_hash": str(request.get("source_snapshot_hash") or ""),
                    "name": direction.attributes.get("name"),
                    "manifest": dict(request.get("manifest") or direction.attributes.get("manifest") or {}),
                    "status": "approved",
                    "approved_by": str(request.get("actor") or "owner-gateway"),
                    "previous_brand_kit_id": previous.id if previous else None,
                },
                actor=str(request.get("actor") or "owner-gateway"),
                reasoning_summary="Approved one immutable Brand Kit after reviewing every generated logo.",
                evidence_ids=(direction.id, *(item.id for item in current_feedback)),
            )
            self.commander.relate(kit, RelationType.DERIVED_FROM, direction)
            self.commander.relate(direction, RelationType.ADOPTED_AS, kit)
            if previous is not None:
                self.commander.relate(kit, RelationType.SUPERSEDES, previous)
            for item in current_feedback:
                self.commander.relate(kit, RelationType.DERIVED_FROM, item)
            for edge in self.store.relationships():
                if edge.source_id == direction.id and edge.relation == RelationType.CONTAINS:
                    self.commander.relate(kit, RelationType.CONTAINS, self.store.get_entity(edge.target_id))
            artifact = self.commander.create_entity(
                EntityKind.ARTIFACT,
                {
                    "artifact_type": "brand_kit_zip",
                    "sha256": str(zip_artifact["sha256"]),
                    "storage_uri": str(zip_artifact.get("storage_uri") or ""),
                    "mime_type": "application/zip",
                    "size_bytes": int(zip_artifact.get("size_bytes") or 0),
                },
                actor=str(request.get("actor") or "owner-gateway"),
                reasoning_summary="Registered the immutable downloadable Brand Kit package.",
                evidence_ids=(kit.id, direction.id),
            )
            self.commander.relate(kit, RelationType.GENERATED, artifact)
        return {"brand_kit_id": kit.id, "artifact_id": artifact.id, "previous_brand_kit_id": previous.id if previous else None}
