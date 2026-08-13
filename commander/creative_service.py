"""Telegram request to persisted and rendered Instagram creative."""

from __future__ import annotations

from pathlib import Path

from .instagram import InstagramCreativeAdapter, InstagramCreativeSpec
from .model import Entity, EntityKind, RelationType
from .renderer import InstagramStoryRenderer
from .service import Commander


class CreativeProductionService:
    def __init__(self, commander: Commander, renderer: InstagramStoryRenderer) -> None:
        self.commander = commander
        self.renderer = renderer

    def create_instagram_story(
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
            direction = str(hypothesis.attributes.get("creative_direction") or hypothesis.attributes["claim"])
            hook, caption, cta = self._parse(direction)
        else:
            hook, caption, cta = self._parse(request_text)
            source = self.commander.create_entity(
                EntityKind.SOURCE,
                {"source_type": "telegram_request", "request": request_text, "actor": requested_by},
                actor=requested_by,
                reasoning_summary="Captured the owner's creative request as provenance.",
            )
            hypothesis = self.commander.create_hypothesis(
                claim=f"The requested hook can meet the configured link CTR threshold: {hook}",
                success_metric="link_ctr", threshold=0.02,
                scope="Instagram Story requested through Telegram", source=source,
            )
        creative = InstagramCreativeAdapter(self.commander).generate(
            hypothesis=hypothesis,
            spec=InstagramCreativeSpec(
                hook=hook,
                hero_image_uri=str(hero_image) if hero_image else "generated://ptw-gradient",
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
                "width": 1080,
                "height": 1920,
                "sha256": digest,
                "storage_uri": str(path),
            },
            actor=requested_by,
            reasoning_summary="Rendered the creative through the deterministic Instagram adapter.",
            evidence_ids=(creative.id,),
        )
        self.commander.relate(creative, RelationType.GENERATED, artifact)
        return creative, artifact, path

    def hypothesis_from_request(self, request_text: str) -> Entity | None:
        parts = request_text.strip().split()
        if len(parts) == 3 and parts[0].split("@", 1)[0].lower() == "/creative" and parts[1].lower() == "from":
            return self.commander.store.get_entity(parts[2])
        return None

    @staticmethod
    def _parse(value: str) -> tuple[str, str, str]:
        body = value.strip()
        if body.lower().startswith("/creative"):
            body = body[len("/creative") :].strip()
        parts = [part.strip() for part in body.split("|")]
        hook = parts[0] if parts and parts[0] else "They said you couldn't. Prove them wrong."
        caption = parts[1] if len(parts) > 1 and parts[1] else "Make the goal public. Show the work."
        cta = parts[2] if len(parts) > 2 and parts[2] else "START YOUR CHALLENGE"
        return hook[:180], caption[:240], cta[:60]
