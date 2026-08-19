"""Bounded, stage-specific context packets for the Idea Laval pipeline."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .laval_domain import LavalConfig, json_safe


class ContextCompiler:
    def __init__(self, config: LavalConfig) -> None:
        self.config = config

    @staticmethod
    def _compact(items: Sequence[Mapping[str, Any]], limit: int, fields: tuple[str, ...]) -> list[dict[str, Any]]:
        return [
            {key: json_safe(item.get(key)) for key in fields if item.get(key) is not None}
            for item in items[:limit]
        ]

    def build_owner_dna_context(self, raw_text: str) -> dict[str, Any]:
        return {"owner_idea": raw_text[:20_000]}

    def build_competitor_extraction_context(
        self, competitor: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        return {
            "competitor": {key: json_safe(competitor.get(key)) for key in ("id", "name", "domain", "url", "result_type")},
            "evidence": self._compact(evidence, 80, ("id", "source_type", "source_url", "claim", "excerpt", "country", "confidence")),
        }

    def build_opportunity_context(
        self, owner_dna: Mapping[str, Any], dossiers: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        return {
            "owner_dna": json_safe(owner_dna),
            "dossiers": self._compact(dossiers, self.config.max_unique_competitors, ("competitor_id", "name", "positioning", "audiences", "features", "distribution", "complaints", "complaint_clusters", "gaps", "keywords", "evidence_ids", "confidence")),
        }

    def build_trend_query_context(
        self,
        owner_dna: Mapping[str, Any],
        opportunities: Sequence[Mapping[str, Any]],
        keywords: Sequence[str],
        pains: Sequence[str],
    ) -> dict[str, Any]:
        return {
            "owner_dna": json_safe(owner_dna),
            "opportunities": self._compact(opportunities, self.config.trend_gate_candidates, ("id", "statement", "pain", "affected_segment", "countries", "evidence_ids", "aggregate_score")),
            "competitor_keywords": list(dict.fromkeys(keywords))[:50],
            "negative_pains": list(dict.fromkeys(pains))[: self.config.max_negative_pain_clusters],
            "countries": json_safe(self.config.countries),
        }

    def build_synthesis_context(
        self,
        owner_dna: Mapping[str, Any],
        opportunities: Sequence[Mapping[str, Any]],
        trend_scores: Sequence[Mapping[str, Any]],
        discoveries: Sequence[Mapping[str, Any]],
        pains: Sequence[str],
        distribution: Sequence[str],
        operators: Sequence[str],
        market_signal_scores: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        return {
            "owner_dna": json_safe(owner_dna),
            "opportunities": self._compact(opportunities, self.config.max_opportunities, ("id", "statement", "pain", "affected_segment", "evidence_ids", "aggregate_score")),
            "trend_scores": self._compact(trend_scores, self.config.max_trend_scores, ("id", "opportunity_id", "term", "country", "window", "dimensions", "aggregate_score", "evidence_ids")),
            "trend_discoveries": self._compact(discoveries, self.config.max_trend_discoveries, ("id", "seed_term", "discovered_term", "discovery_type", "country", "growth_label", "opportunity_ids", "evidence_ids", "confidence")),
            "market_signal_scores": self._compact(market_signal_scores, self.config.max_trend_scores, ("id", "opportunity_id", "normalization_version", "formula", "weights", "components", "raw_counts", "data_status", "aggregate_score", "evidence_ids", "as_of")),
            "negative_pain_clusters": list(dict.fromkeys(pains))[: self.config.max_negative_pain_clusters],
            "distribution_patterns": list(dict.fromkeys(distribution))[: self.config.max_distribution_patterns],
            "transformation_operators": list(operators),
        }

    def build_evaluation_context(self, packet: Mapping[str, Any], variants: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return {
            "owner_dna": json_safe(packet.get("owner_dna") or {}),
            "evidence_backed_directions": {
                "opportunities": json_safe(packet.get("opportunities") or []),
                "trend_scores": json_safe(packet.get("trend_scores") or []),
                "trend_discoveries": json_safe(packet.get("trend_discoveries") or []),
                "market_signal_scores": json_safe(packet.get("market_signal_scores") or []),
            },
            "variants": self._compact(variants, 100, ("id", "title", "one_liner", "mechanism", "target_user", "why_new", "operator", "opportunity_ids", "trend_signal_ids", "trend_discovery_ids", "market_signal_ids", "evidence_ids")),
            "rubric": dict(self.config.idea_weights),
        }
