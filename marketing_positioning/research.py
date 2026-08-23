from __future__ import annotations

from typing import Any, Mapping

from .repository import PositioningRepository


class ResearchKnowledgeService:
    """The only entry point for permanent positioning research findings."""

    def __init__(self, repository: PositioningRepository) -> None:
        self.repository = repository

    def record_finding(
        self,
        revision_id: str,
        *,
        title: str,
        source_uri: str,
        publisher: str,
        finding_summary: str,
        country: str,
        language: str,
        provider: str,
        external_id: str,
        metadata: Mapping[str, Any],
    ) -> str:
        if not title.strip() or not source_uri.strip() or not finding_summary.strip():
            raise ValueError("research title, URI, and finding summary are required")
        return self.repository.add_research_source(
            revision_id,
            title=title.strip(), uri=source_uri.strip(), publisher=publisher.strip(),
            content=finding_summary.strip(), country=country, language=language,
            provider=provider, external_id=external_id, metadata=metadata,
        )
