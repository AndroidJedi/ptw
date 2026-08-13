"""Research provenance and initial hypothesis synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Protocol

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
    research_type: str = "creative_ideation"

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
                "research_type": finding.research_type,
                "owner_agent": "marketing.creative.instagram",
                "knowledge_domain": "marketing.creative",
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
        attributes: dict[str, object] | None = None,
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
            attributes=attributes,
        )
        return hypothesis


@dataclass(frozen=True, slots=True)
class HypothesisProposal:
    claim: str
    source_indexes: tuple[int, ...]
    creative_direction: str
    success_metric: str = "link_ctr"
    threshold: float = 0.02


@dataclass(frozen=True, slots=True)
class CreativeResearchResult:
    findings: tuple[ResearchFinding, ...]
    hypotheses: tuple[HypothesisProposal, ...]


class CreativeResearchProvider(Protocol):
    def research(self, topic: str) -> CreativeResearchResult: ...


class CreativeIdeationResearchService:
    """Persist provider research as sourced, testable creative hypotheses."""

    def __init__(self, commander: Commander, provider: CreativeResearchProvider) -> None:
        self.commander = commander
        self.provider = provider

    def run(self, topic: str, *, actor: str) -> tuple[tuple[Entity, ...], tuple[Entity, ...]]:
        topic = topic.strip()
        if not topic:
            raise ValueError("usage: /research creative <topic>")
        result = self.provider.research(topic)
        if not result.findings or not result.hypotheses:
            raise ValueError("research provider returned no sourced hypotheses")
        with self.commander.store.transaction():
            sources = tuple(
                ResearchKnowledgeService(self.commander).record_finding(item, actor=actor)
                for item in result.findings
            )
            hypotheses = []
            for proposal in result.hypotheses:
                try:
                    evidence = tuple(sources[index] for index in proposal.source_indexes)
                except IndexError as error:
                    raise ValueError("research hypothesis references an unknown source") from error
                hypothesis = ResearchKnowledgeService(self.commander).propose_hypothesis(
                    claim=proposal.claim,
                    success_metric=proposal.success_metric,
                    threshold=proposal.threshold,
                    scope=f"creative_ideation:instagram:{topic[:160]}",
                    findings=evidence,
                    actor=actor,
                    attributes={
                        "research_type": "creative_ideation",
                        "research_topic": topic,
                        "creative_direction": proposal.creative_direction,
                        "owner_agent": "marketing.creative.instagram",
                        "knowledge_domain": "marketing.creative",
                    },
                )
                hypotheses.append(hypothesis)
        return sources, tuple(hypotheses)
