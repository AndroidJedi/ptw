"""Instagram-specific mapping kept outside the generic learning core."""

from __future__ import annotations

from dataclasses import dataclass

from .model import Entity, EntityKind, RelationType
from .service import Commander


@dataclass(frozen=True, slots=True)
class InstagramCreativeSpec:
    hook: str
    hero_image_uri: str
    supporting_visual_uri: str
    caption: str
    cta: str


class InstagramCreativeAdapter:
    component_kinds = ("hook", "hero_image", "supporting_visual", "caption", "cta")

    def __init__(self, commander: Commander) -> None:
        self.commander = commander

    def generate(self, *, hypothesis: Entity, spec: InstagramCreativeSpec) -> Entity:
        values = (
            spec.hook,
            spec.hero_image_uri,
            spec.supporting_visual_uri,
            spec.caption,
            spec.cta,
        )
        components: list[Entity] = []
        for component_kind, value in zip(self.component_kinds, values, strict=True):
            existing = next(
                (
                    item for item in self.commander.store.entities(EntityKind.CREATIVE_COMPONENT)
                    if item.attributes.get("vertical") == "instagram"
                    and item.attributes.get("component_kind") == component_kind
                    and item.attributes.get("value") == value
                ),
                None,
            )
            components.append(
                existing or self.commander.create_entity(
                    EntityKind.CREATIVE_COMPONENT,
                    {"component_kind": component_kind, "value": value, "vertical": "instagram"},
                    reasoning_summary=f"Created reusable Instagram {component_kind} component.",
                    evidence_ids=(hypothesis.id,),
                )
            )
        creative = self.commander.create_entity(
            EntityKind.CREATIVE,
            {
                "vertical": "instagram",
                "format": "story_1080x1920",
                "status": "generated",
                "generator_adapter": "instagram_demo_v1",
                "component_weight_mean": sum(
                    self.commander.component_weight(item) for item in components
                ) / len(components),
            },
            reasoning_summary="Composed independently identifiable components for the experiment.",
            evidence_ids=(hypothesis.id, *(component.id for component in components)),
        )
        for component in components:
            self.commander.relate(creative, RelationType.CONTAINS, component)
        self.commander.relate(creative, RelationType.GENERATED, hypothesis)
        return creative
