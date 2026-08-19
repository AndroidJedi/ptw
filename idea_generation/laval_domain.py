"""Idea Laval domain constants, configuration, normalization, and scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


LEGACY_STAGES = (
    "OWNER_CAPTURE",
    "OWNER_DNA",
    "QUERY_PLAN",
    "SERP_DISCOVERY",
    "COMPETITOR_SELECTION",
    "COMPETITOR_EVIDENCE",
    "COMPETITOR_DOSSIERS",
    "OPPORTUNITY_MATRIX",
    "TREND_QUERY_PLAN",
    "GOOGLE_TRENDS_RESEARCH",
    "TREND_GATE",
    "SYNTHESIS_PACKET",
    "IDEA_EXPANSION",
    "IDEA_CLUSTERING",
    "IDEA_EVALUATION",
    "FINAL_SHORTLIST",
)

STAGES = (
    "OWNER_CAPTURE",
    "OWNER_DNA",
    "QUERY_PLAN",
    "SERP_DISCOVERY",
    "COMPETITOR_SELECTION",
    "COMPETITOR_EVIDENCE",
    "COMPETITOR_DOSSIERS",
    "OPPORTUNITY_MATRIX",
    "MARKET_SIGNAL_PLAN",
    "MARKET_SIGNAL_COLLECTION",
    "MARKET_SIGNAL_GATE",
    "SYNTHESIS_PACKET",
    "IDEA_EXPANSION",
    "IDEA_CLUSTERING",
    "IDEA_EVALUATION",
    "FINAL_SHORTLIST",
)

QUERY_FAMILIES = ("category", "problem", "alternative", "behavioral")
OPERATORS = (
    "invert",
    "remove",
    "extreme",
    "transfer",
    "resegment",
    "recombine",
    "distribution_first",
    "behavior_first",
)

MARKET_SIGNAL_NORMALIZATION_VERSION = "market-signal-v1"
MARKET_SIGNAL_FORMULA = (
    "0.20 × cross_country_recurrence + 0.20 × query_family_recurrence "
    "+ 0.15 × recent_content_activity + 0.15 × community_activity "
    "+ 0.15 × negative_pain_recurrence + 0.15 × semantic_relevance"
)
MARKET_SIGNAL_WEIGHTS = {
    "cross_country_recurrence": .20,
    "query_family_recurrence": .20,
    "recent_content_activity": .15,
    "community_activity": .15,
    "negative_pain_recurrence": .15,
    "semantic_relevance": .15,
}
COMMUNITY_SOURCE_TYPES = frozenset({"reddit", "forum", "youtube", "review"})

DEFAULT_COUNTRIES = (
    {"code": "US", "language": "en"},
    {"code": "GB", "language": "en"},
    {"code": "DE", "language": "de", "secondary_language": "en"},
    {"code": "NO", "language": "no", "secondary_language": "en"},
    {"code": "DK", "language": "da", "secondary_language": "en"},
)


def _bounded_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be {minimum}..{maximum}")
    return result


def _weights(value: Mapping[str, Any] | None, defaults: Mapping[str, float]) -> dict[str, float]:
    result = {key: float((value or {}).get(key, weight)) for key, weight in defaults.items()}
    if any(weight < 0 for weight in result.values()) or not 0.999 <= sum(result.values()) <= 1.001:
        raise ValueError("score weights must be non-negative and total 1")
    return result


@dataclass(frozen=True, slots=True)
class LavalConfig:
    countries: tuple[dict[str, str], ...] = field(
        default_factory=lambda: tuple(dict(item) for item in DEFAULT_COUNTRIES)
    )
    query_families: int = 4
    queries_per_family: int = 1
    serp_depth: int = 10
    use_secondary_language: bool = True
    top_competitors_per_country: int = 3
    max_unique_competitors: int = 10
    website_pages_per_competitor: int = 8
    youtube_items_per_competitor: int = 5
    negative_feedback_items_per_competitor: int = 20
    trend_gate_candidates: int = 15
    trend_max_terms: int = 30
    trend_windows: tuple[str, ...] = ("90d", "12m", "5y")
    max_opportunities: int = 10
    max_trend_scores: int = 8
    max_trend_discoveries: int = 8
    max_negative_pain_clusters: int = 12
    max_distribution_patterns: int = 8
    variants_per_operator: int = 3
    shortlist: int = 10
    finalists: int = 3
    approval_mode: str = "manual"
    approval_gates: tuple[str, ...] = (
        "COMPETITOR_SELECTION",
        "OPPORTUNITY_MATRIX",
        "FINAL_SHORTLIST",
    )
    competitor_weights: dict[str, float] = field(default_factory=lambda: {
        "query_recurrence": .30,
        "average_serp_position": .20,
        "semantic_relevance": .20,
        "country_relevance": .15,
        "directness": .10,
        "evidence_confidence": .05,
    })
    opportunity_weights: dict[str, float] = field(default_factory=lambda: {
        "frequency": .20,
        "severity": .20,
        "coverage_gap": .20,
        "cross_market": .15,
        "owner_relevance": .15,
        "confidence": .10,
    })
    trend_weights: dict[str, float] = field(default_factory=lambda: {
        "current_interest": .20,
        "growth": .20,
        "acceleration": .20,
        "persistence": .20,
        "geo_spread": .20,
    })
    idea_weights: dict[str, float] = field(default_factory=lambda: {
        "owner_fit": .25,
        "differentiation": .20,
        "opportunity_support": .20,
        "trend_support": .15,
        "distribution_potential": .10,
        "novelty": .10,
    })
    market_signal_weights: dict[str, float] = field(
        default_factory=lambda: dict(MARKET_SIGNAL_WEIGHTS)
    )
    market_signal_recent_source_target: int = 10
    market_signal_community_source_target: int = 10
    market_signal_complaint_target: int = 10

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None = None) -> "LavalConfig":
        raw = dict(raw or {})
        search = dict(raw.get("search") or {})
        analysis = dict(raw.get("competitor_analysis") or {})
        opportunities = dict(raw.get("opportunities") or {})
        trends = dict(raw.get("trends") or {})
        synthesis = dict(raw.get("synthesis") or {})
        generation = dict(raw.get("idea_generation") or {})
        final = dict(raw.get("final") or {})
        countries_raw = raw.get("countries", DEFAULT_COUNTRIES)
        countries: list[dict[str, str]] = []
        for item in countries_raw:
            if isinstance(item, str):
                default = next((value for value in DEFAULT_COUNTRIES if value["code"] == item.upper()), None)
                if default is None:
                    raise ValueError(f"country {item!r} requires a language")
                country = dict(default)
            else:
                country = {key: str(value).lower() if "language" in key else str(value).upper()
                           for key, value in dict(item).items() if value}
            if not re.fullmatch(r"[A-Z]{2}", country.get("code", "")):
                raise ValueError("country code must contain two uppercase letters")
            if not re.fullmatch(r"[a-z]{2,3}", country.get("language", "")):
                raise ValueError(f"country {country['code']} requires a valid language")
            countries.append(country)
        codes = [item["code"] for item in countries]
        if not countries or len(codes) != len(set(codes)):
            raise ValueError("countries must be a non-empty unique list")
        windows = tuple(str(item) for item in trends.get("windows", ("90d", "12m", "5y")))
        if not windows or not set(windows).issubset({"90d", "12m", "5y"}):
            raise ValueError("trend windows must be selected from 90d, 12m, and 5y")
        approval_mode = str(raw.get("approval_mode", "manual"))
        if approval_mode not in {"manual", "automatic"}:
            raise ValueError("approval_mode must be manual or automatic")
        gates = tuple(str(item).upper() for item in raw.get(
            "approval_gates", ("COMPETITOR_SELECTION", "OPPORTUNITY_MATRIX", "FINAL_SHORTLIST")
        ))
        if not set(gates).issubset(STAGES):
            raise ValueError("approval gates must name Laval stages")
        shortlist = _bounded_int(final.get("shortlist", 10), "shortlist", 1, 50)
        finalists = _bounded_int(final.get("finalists", 3), "finalists", 1, 10)
        if finalists > shortlist:
            raise ValueError("finalists cannot exceed shortlist size")
        return cls(
            countries=tuple(countries),
            query_families=_bounded_int(search.get("query_families", 4), "query_families", 1, 4),
            queries_per_family=_bounded_int(search.get("queries_per_family", 1), "queries_per_family", 1, 5),
            serp_depth=_bounded_int(search.get("serp_depth", 10), "serp_depth", 3, 200),
            use_secondary_language=bool(search.get("use_secondary_language", True)),
            top_competitors_per_country=_bounded_int(search.get("top_competitors_per_country", 3), "top_competitors_per_country", 1, 10),
            max_unique_competitors=_bounded_int(analysis.get("max_unique_competitors", 10), "max_unique_competitors", 3, 50),
            website_pages_per_competitor=_bounded_int(analysis.get("website_pages_per_competitor", 8), "website_pages_per_competitor", 1, 20),
            youtube_items_per_competitor=_bounded_int(analysis.get("youtube_items_per_competitor", 5), "youtube_items_per_competitor", 0, 20),
            negative_feedback_items_per_competitor=_bounded_int(analysis.get("negative_feedback_items_per_competitor", 20), "negative_feedback_items_per_competitor", 0, 100),
            trend_gate_candidates=_bounded_int(opportunities.get("trend_gate_candidates", 15), "trend_gate_candidates", 1, 50),
            trend_max_terms=_bounded_int(trends.get("max_terms", 30), "trend_max_terms", 1, 100),
            trend_windows=windows,
            max_opportunities=_bounded_int(synthesis.get("max_opportunities", 10), "max_opportunities", 1, 50),
            max_trend_scores=_bounded_int(synthesis.get("max_trend_scores", 8), "max_trend_scores", 1, 50),
            max_trend_discoveries=_bounded_int(synthesis.get("max_trend_discoveries", 8), "max_trend_discoveries", 1, 50),
            max_negative_pain_clusters=_bounded_int(synthesis.get("max_negative_pain_clusters", 12), "max_negative_pain_clusters", 1, 50),
            max_distribution_patterns=_bounded_int(synthesis.get("max_distribution_patterns", 8), "max_distribution_patterns", 1, 50),
            variants_per_operator=_bounded_int(generation.get("variants_per_operator", 3), "variants_per_operator", 1, 10),
            shortlist=shortlist,
            finalists=finalists,
            approval_mode=approval_mode,
            approval_gates=gates,
            competitor_weights=_weights(raw.get("competitor_weights"), cls().competitor_weights),
            opportunity_weights=_weights(raw.get("opportunity_weights"), cls().opportunity_weights),
            trend_weights=_weights(raw.get("trend_weights"), cls().trend_weights),
            idea_weights=_weights(raw.get("idea_weights"), cls().idea_weights),
            market_signal_weights=_weights(
                raw.get("market_signal_weights"), cls().market_signal_weights
            ),
            market_signal_recent_source_target=_bounded_int(
                (raw.get("market_signals") or {}).get("recent_source_target", 10),
                "market_signal_recent_source_target", 1, 100,
            ),
            market_signal_community_source_target=_bounded_int(
                (raw.get("market_signals") or {}).get("community_source_target", 10),
                "market_signal_community_source_target", 1, 100,
            ),
            market_signal_complaint_target=_bounded_int(
                (raw.get("market_signals") or {}).get("complaint_target", 10),
                "market_signal_complaint_target", 1, 100,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "countries": [dict(item) for item in self.countries],
            "search": {
                "query_families": self.query_families,
                "queries_per_family": self.queries_per_family,
                "serp_depth": self.serp_depth,
                "use_secondary_language": self.use_secondary_language,
                "top_competitors_per_country": self.top_competitors_per_country,
            },
            "competitor_analysis": {
                "max_unique_competitors": self.max_unique_competitors,
                "website_pages_per_competitor": self.website_pages_per_competitor,
                "youtube_items_per_competitor": self.youtube_items_per_competitor,
                "negative_feedback_items_per_competitor": self.negative_feedback_items_per_competitor,
            },
            "opportunities": {"trend_gate_candidates": self.trend_gate_candidates},
            "trends": {"max_terms": self.trend_max_terms, "windows": list(self.trend_windows)},
            "synthesis": {
                "max_opportunities": self.max_opportunities,
                "max_trend_scores": self.max_trend_scores,
                "max_trend_discoveries": self.max_trend_discoveries,
                "max_negative_pain_clusters": self.max_negative_pain_clusters,
                "max_distribution_patterns": self.max_distribution_patterns,
            },
            "idea_generation": {"variants_per_operator": self.variants_per_operator},
            "final": {"shortlist": self.shortlist, "finalists": self.finalists},
            "approval_mode": self.approval_mode,
            "approval_gates": list(self.approval_gates),
            "competitor_weights": dict(self.competitor_weights),
            "opportunity_weights": dict(self.opportunity_weights),
            "trend_weights": dict(self.trend_weights),
            "idea_weights": dict(self.idea_weights),
            "market_signals": {
                "normalization_version": MARKET_SIGNAL_NORMALIZATION_VERSION,
                "recent_source_target": self.market_signal_recent_source_target,
                "community_source_target": self.market_signal_community_source_target,
                "complaint_target": self.market_signal_complaint_target,
                "community_source_types": sorted(COMMUNITY_SOURCE_TYPES),
            },
            "market_signal_weights": dict(self.market_signal_weights),
        }


def input_hash(*values: Any) -> str:
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def clamp(value: Any) -> float:
    return max(0.0, min(1.0, float(value)))


def weighted_score(dimensions: Mapping[str, Any], weights: Mapping[str, float]) -> float:
    return round(sum(clamp(dimensions.get(key, 0)) * weight for key, weight in weights.items()), 6)


def competitor_score(dimensions: Mapping[str, Any], config: LavalConfig) -> float:
    return weighted_score(dimensions, config.competitor_weights)


def opportunity_score(dimensions: Mapping[str, Any], config: LavalConfig) -> float:
    return weighted_score(dimensions, config.opportunity_weights)


def trend_score(dimensions: Mapping[str, Any], config: LavalConfig) -> float:
    return weighted_score(dimensions, config.trend_weights)


def idea_score(dimensions: Mapping[str, Any], config: LavalConfig) -> float:
    return weighted_score(dimensions, config.idea_weights)


def _real_published_at(evidence: Mapping[str, Any]) -> datetime | None:
    value = (evidence.get("metadata") or {}).get("published_at")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def market_signal_score(
    evidence: Sequence[Mapping[str, Any]],
    relevant_evidence_ids: Sequence[str],
    config: LavalConfig,
    *,
    as_of: datetime,
) -> dict[str, Any]:
    """Compute market-signal-v1 only from persisted, explicitly evaluated evidence."""
    evaluated_by_id = {str(item.get("id")): item for item in evidence if item.get("id")}
    relevant = {str(value) for value in relevant_evidence_ids} & set(evaluated_by_id)
    source_groups: dict[str, list[Mapping[str, Any]]] = {}
    for evidence_id in sorted(evaluated_by_id):
        item = evaluated_by_id[evidence_id]
        source_key = canonical_evidence_url(str(item.get("source_url") or "")) or f"evidence:{evidence_id}"
        source_groups.setdefault(source_key, []).append(item)
    deduplicated = [
        next(item for item in items if str(item["id"]) in relevant)
        for items in source_groups.values()
        if any(str(item["id"]) in relevant for item in items)
    ]

    target_countries = {str(item["code"]).upper() for item in config.countries}
    countries = {
        str(item.get("country") or "").upper()
        for item in deduplicated
        if str(item.get("country") or "").upper() in target_countries
    }
    families = {
        str((item.get("metadata") or {}).get("query_family") or "").lower()
        for item in deduplicated
    } & set(QUERY_FAMILIES[: config.query_families])
    as_of_utc = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
    as_of_utc = as_of_utc.astimezone(timezone.utc)
    recent = [
        item for item in deduplicated
        if (published := _real_published_at(item)) is not None
        and as_of_utc - timedelta(days=365) <= published <= as_of_utc
    ]
    community = [
        item for item in deduplicated
        if str(item.get("source_type") or "").lower() in COMMUNITY_SOURCE_TYPES
    ]
    community_types = {str(item.get("source_type")).lower() for item in community}
    complaints = [
        item for item in deduplicated
        if (item.get("metadata") or {}).get("purpose") == "negative"
    ]
    complaint_competitors = {str(item.get("competitor_id")) for item in complaints if item.get("competitor_id")}
    complaint_countries = {str(item.get("country")).upper() for item in complaints if item.get("country")}

    components = {
        "cross_country_recurrence": len(countries) / max(1, len(target_countries)),
        "query_family_recurrence": len(families) / max(1, config.query_families),
        "recent_content_activity": min(len(recent) / config.market_signal_recent_source_target, 1),
        "community_activity": (
            .5 * min(len(community) / config.market_signal_community_source_target, 1)
            + .5 * len(community_types) / len(COMMUNITY_SOURCE_TYPES)
        ),
        "negative_pain_recurrence": sum((
            min(len(complaints) / config.market_signal_complaint_target, 1),
            min(len(complaint_competitors) / max(1, config.max_unique_competitors), 1),
            min(len(complaint_countries) / max(1, len(target_countries)), 1),
        )) / 3,
        "semantic_relevance": len(deduplicated) / max(1, len(source_groups)),
    }
    components = {key: round(clamp(value), 6) for key, value in components.items()}
    availability = {
        "cross_country_recurrence": "available" if countries else "no_data",
        "query_family_recurrence": "available" if families else "no_data",
        "recent_content_activity": "available" if recent else "no_data",
        "community_activity": "available" if community else "no_data",
        "negative_pain_recurrence": "available" if complaints else "no_data",
        "semantic_relevance": "available" if source_groups else "no_data",
    }
    raw_counts = {
        "target_countries": len(target_countries),
        "countries_with_independent_evidence": len(countries),
        "configured_query_families": config.query_families,
        "query_families_with_evidence": len(families),
        "evaluated_unique_sources": len(source_groups),
        "relevant_unique_sources": len(deduplicated),
        "recent_dated_sources_365d": len(recent),
        "community_unique_sources": len(community),
        "community_source_types": len(community_types),
        "independent_complaints": len(complaints),
        "competitors_with_complaints": len(complaint_competitors),
        "countries_with_complaints": len(complaint_countries),
    }
    return {
        "normalization_version": MARKET_SIGNAL_NORMALIZATION_VERSION,
        "formula": MARKET_SIGNAL_FORMULA,
        "weights": dict(config.market_signal_weights),
        "components": components,
        "raw_counts": raw_counts,
        "data_status": {
            "overall": "available" if any(value == "available" for value in availability.values()) else "no_data",
            "components": availability,
        },
        "evidence_ids": [str(item["id"]) for item in deduplicated],
        "aggregate_score": weighted_score(components, config.market_signal_weights),
    }


def canonical_url(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = "https://" + candidate
    parts = urlsplit(candidate)
    host = (parts.hostname or "").lower().removeprefix("www.")
    if not host:
        return ""
    port = f":{parts.port}" if parts.port and parts.port not in {80, 443} else ""
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower() or "https", host + port, path, "", ""))


def canonical_domain(value: str) -> str:
    normalized = canonical_url(value)
    return (urlsplit(normalized).hostname or "").removeprefix("www.")


def canonical_evidence_url(value: str) -> str:
    """Keep identity-bearing query parameters while removing tracking noise."""
    base = canonical_url(value)
    if not base:
        return ""
    parts = urlsplit(value if "://" in value else "https://" + value)
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(("utm_", "tracking"))
        and key.lower() not in {"gclid", "fbclid", "ref", "source"}
    ]
    return base + (f"?{urlencode(sorted(query))}" if query else "")


def normalize_words(value: str) -> tuple[str, ...]:
    stop = {"the", "and", "for", "with", "from", "into", "your", "that", "this", "app"}
    return tuple(sorted({word for word in re.findall(r"[a-z0-9]+", value.lower()) if len(word) > 2 and word not in stop}))


def deduplicate_queries(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in values:
        key = (
            str(item.get("country", "")).upper(),
            str(item.get("language", "")).lower(),
            re.sub(r"\s+", " ", str(item.get("query", "")).strip().lower()),
        )
        if not key[2] or key in seen:
            continue
        seen.add(key)
        result.append(dict(item))
    return result


def stage_index(stage: str) -> int:
    normalized = stage.upper()
    for stages in (STAGES, LEGACY_STAGES):
        if normalized in stages:
            return stages.index(normalized)
    raise ValueError(f"unknown Laval stage: {stage}")


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))
