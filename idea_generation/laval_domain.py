"""Idea Laval domain constants, configuration, normalization, and scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit


STAGES = (
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

QUERY_FAMILIES = ("category", "problem", "alternative", "behavioral")
OPERATORS = (
    "invert",
    "remove",
    "extreme",
    "transfer",
    "resegment",
    "recombine",
    "distribution_first",
)

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
    try:
        return STAGES.index(stage.upper())
    except ValueError as error:
        raise ValueError(f"unknown Laval stage: {stage}") from error


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))
