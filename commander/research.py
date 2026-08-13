"""Research provenance and initial hypothesis synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .model import Entity, EntityKind
from .service import Commander


@dataclass(frozen=True, slots=True)
class ResearchFinding:
    title: str
    source_uri: str
    finding_summary: str
    publisher: str
    published_on: date | None = None
    credibility: float = 0.5
    external_id: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.source_uri.strip() or not self.finding_summary.strip():
            raise ValueError("research title, source URI, and finding summary are required")
        if not 0 <= self.credibility <= 1:
            raise ValueError("research credibility must be between 0 and 1")


class ResearchKnowledgeService:
    def __init__(self, commander: Commander) -> None:
        self.commander = commander

    def record_finding(self, finding: ResearchFinding, *, actor: str) -> Entity:
        return self.commander.create_entity(
            EntityKind.SOURCE,
            {
                "source_type": "research_finding",
                "title": finding.title.strip(),
                "source_uri": finding.source_uri.strip(),
                "publisher": finding.publisher.strip(),
                "published_on": finding.published_on.isoformat() if finding.published_on else None,
                "finding_summary": finding.finding_summary.strip(),
                "credibility": finding.credibility,
                "external_id": finding.external_id,
            },
            actor=actor,
            reasoning_summary="Recorded a bounded research finding with explicit provenance.",
        )

    def propose_hypothesis(
        self,
        *,
        claim: str,
        success_metric: str,
        threshold: float,
        scope: str,
        findings: Iterable[Entity],
        actor: str,
    ) -> Entity:
        sources = tuple(findings)
        if not sources:
            raise ValueError("at least one research finding is required")
        for source in sources:
            if source.kind != EntityKind.SOURCE or source.attributes.get("source_type") != "research_finding":
                raise TypeError("hypothesis evidence must be recorded research findings")
        hypothesis = self.commander.create_hypothesis(
            claim=claim,
            success_metric=success_metric,
            threshold=threshold,
            scope=scope,
            source=sources[0],
            additional_sources=sources[1:],
            actor=actor,
        )
        return hypothesis
