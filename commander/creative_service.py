"""Telegram request to persisted and rendered Instagram creative."""

from __future__ import annotations

from pathlib import Path
import re

from .instagram import InstagramCreativeAdapter, InstagramCreativeSpec
from .model import Entity, EntityKind, RelationType
from .renderer import InstagramPostRenderer
from .service import Commander


class CreativeProductionService:
    DEFAULT_HOOK = "They said you couldn't. Prove them wrong."

    def __init__(self, commander: Commander, renderer: InstagramPostRenderer) -> None:
        self.commander = commander
        self.renderer = renderer

    def create_instagram_post(
        self,
        *,
        request_text: str,
        requested_by: str,
        hero_image: Path | None = None,
        hypothesis: Entity | None = None,
    ) -> tuple[Entity, Entity, Path]:
        if hypothesis is not None:
            if hypothesis.kind != EntityKind.HYPOTHESIS:
                raise TypeError("creative source must be a hypothesis")
            if hypothesis.attributes.get("research_type") != "creative_ideation":
                raise ValueError("/creative from requires a creative-ideation hypothesis")
            if hypothesis.attributes.get("owner_agent") != "marketing.creative.instagram":
                raise ValueError("hypothesis does not belong to the Instagram creative agent")
            direction = str(hypothesis.attributes.get("creative_direction") or hypothesis.attributes["claim"])
            hook, caption, cta = self._parse(direction)
            hook = self._hook_variant(hook, self._hypothesis_usage_count(hypothesis.id))
        else:
            hook, caption, cta = self._parse(request_text)
            variant_index = sum(
                item.attributes.get("source_type") == "telegram_request"
                and item.attributes.get("request") == request_text
                for item in self.commander.store.entities(EntityKind.SOURCE)
            )
            hook = self._hook_variant(hook, variant_index)
            source = self.commander.create_entity(
                EntityKind.SOURCE,
                {"source_type": "telegram_request", "request": request_text,
                 "actor": requested_by, "variant_index": variant_index},
                actor=requested_by,
                reasoning_summary="Captured the owner's creative request as provenance.",
            )
            hypothesis = self.commander.create_hypothesis(
                claim=f"The requested hook can meet the configured link CTR threshold: {hook}",
                success_metric="link_ctr", threshold=0.02,
                scope="Instagram feed post requested through Telegram", source=source,
            )
        creative = InstagramCreativeAdapter(self.commander).generate(
            hypothesis=hypothesis,
            spec=InstagramCreativeSpec(
                hook=hook,
                hero_image_uri=str(hero_image) if hero_image else "generated://ptw-post-artwork",
                supporting_visual_uri="generated://none",
                caption=caption,
                cta=cta,
            ),
        )
        path, digest = self.renderer.render(
            creative_id=creative.id,
            hook=hook,
            caption=caption,
            cta=cta,
            hero_image=hero_image,
        )
        artifact = self.commander.create_entity(
            EntityKind.ARTIFACT,
            {
                "media_type": "image/png",
                "width": self.renderer.width,
                "height": self.renderer.height,
                "sha256": digest,
                "storage_uri": str(path),
            },
            actor=requested_by,
            reasoning_summary=(
                "Rendered a complete Instagram feed-post image through the "
                "deterministic adapter."
            ),
            evidence_ids=(creative.id,),
        )
        self.commander.relate(creative, RelationType.GENERATED, artifact)
        return creative, artifact, path

    # Compatibility for callers that predate feed-post generation.
    create_instagram_story = create_instagram_post

    def hypothesis_from_request(self, request_text: str) -> Entity | None:
        parts = request_text.strip().split()
        if len(parts) == 3 and parts[0].split("@", 1)[0].lower() == "/creative" and parts[1].lower() == "from":
            return self.commander.store.get_entity(parts[2])
        return None

    def text_hook_from_request(
        self, request_text: str, *, requested_by: str = "commander"
    ) -> tuple[str, Entity] | None:
        """Return researched text for `/creative hook [brief]`; never render it."""

        if "|" in request_text:
            return None
        parts = request_text.strip().split(maxsplit=2)
        if (len(parts) < 2 or parts[0].split("@", 1)[0].lower() != "/creative"
                or parts[1].lower() not in {"hook", "hooks"}):
            return None
        brief_terms = set(re.findall(r"[a-z0-9]{3,}", parts[2].lower())) if len(parts) > 2 else set()
        candidates = [
            item for item in self.commander.store.entities(EntityKind.HYPOTHESIS)
            if item.attributes.get("research_type") == "creative_ideation"
            and item.attributes.get("owner_agent") == "marketing.creative.instagram"
        ]
        selected: Entity | None = None
        if candidates:
            def score(item: Entity) -> tuple[int, int, object]:
                searchable = " ".join(str(item.attributes.get(key, "")) for key in (
                    "research_topic", "claim", "creative_direction"
                )).lower()
                return (
                    sum(term in searchable for term in brief_terms),
                    -self._hypothesis_usage_count(item.id),
                    item.created_at,
                )
            selected = max(candidates, key=score)
            direction = str(selected.attributes.get("creative_direction") or "")
            base_hook = direction.partition("|")[0].strip() or self.DEFAULT_HOOK
        else:
            base_hook = self.DEFAULT_HOOK
        variant_index = self._hook_usage_count(base_hook)
        hook = self._hook_variant(base_hook, variant_index)
        creative = self.commander.create_entity(
            EntityKind.CREATIVE,
            {
                "delivery_mode": "text_hook",
                "base_hook": base_hook,
                "hook": hook,
                "variant_index": variant_index,
                "hypothesis_id": selected.id if selected else None,
                "request": request_text[:500],
            },
            actor=requested_by,
            reasoning_summary="Selected a non-repeating researched text-hook variant.",
            evidence_ids=(selected.id,) if selected else (),
        )
        component = next(
            (
                item
                for item in self.commander.store.entities(EntityKind.CREATIVE_COMPONENT)
                if item.attributes.get("vertical") == "instagram"
                and item.attributes.get("component_kind") == "hook"
                and item.attributes.get("value") == hook
            ),
            None,
        )
        if component is None:
            component = self.commander.create_entity(
                EntityKind.CREATIVE_COMPONENT,
                {"component_kind": "hook", "value": hook, "vertical": "instagram"},
                actor=requested_by,
                reasoning_summary="Created a reusable Instagram text-hook component.",
                evidence_ids=(selected.id,) if selected else (creative.id,),
            )
        self.commander.relate(creative, RelationType.CONTAINS, component)
        if selected:
            self.commander.relate(creative, RelationType.GENERATED, selected)
        return hook, creative

    def _hypothesis_usage_count(self, hypothesis_id: str) -> int:
        return sum(
            edge.relation == RelationType.GENERATED and edge.target_id == hypothesis_id
            for edge in self.commander.store.relationships()
        )

    def _hook_usage_count(self, base_hook: str) -> int:
        return sum(
            item.attributes.get("base_hook") == base_hook
            for item in self.commander.store.entities(EntityKind.CREATIVE)
        )

    @staticmethod
    def _hook_variant(base_hook: str, index: int) -> str:
        if index == 0:
            return base_hook[:180]
        formats = (
            "POV: {hook}",
            "Receipt #{number}: {hook}",
            "They doubted it. {hook}",
            "Plot twist: {hook}",
        )
        return formats[(index - 1) % len(formats)].format(
            hook=base_hook, number=index + 1
        )[:180]

    @staticmethod
    def _parse(value: str) -> tuple[str, str, str]:
        body = value.strip()
        if body.lower().startswith("/creative"):
            body = body[len("/creative") :].strip()
        parts = [part.strip() for part in body.split("|")]
        hook = parts[0] if parts and parts[0] else CreativeProductionService.DEFAULT_HOOK
        caption = parts[1] if len(parts) > 1 and parts[1] else "Make the goal public. Show the work."
        cta = parts[2] if len(parts) > 2 and parts[2] else "START YOUR CHALLENGE"
        return hook[:180], caption[:240], cta[:60]
