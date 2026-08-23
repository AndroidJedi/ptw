"""Bounded Natal brief derived only from an approved positioning revision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
from uuid import UUID

from .catalog import recommend_template


def _bounded(value: Any, name: str, *, limit: int, required: bool = True) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValueError(f"{name} is required")
    if len(result) > limit:
        raise ValueError(f"{name} must contain at most {limit} characters")
    return result


def _https(value: Any, name: str) -> str:
    result = _bounded(value, name, limit=2000)
    parsed = urlsplit(result)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{name} must be a public HTTPS URL")
    return result


def _sequence(value: Any, name: str, *, maximum: int) -> Sequence[Any]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValueError(f"{name} must contain at most {maximum} items")
    return value


def _pairs(value: Any, name: str, *, minimum: int, maximum: int) -> tuple[dict[str, str], ...]:
    result = []
    for item in _sequence(value, name, maximum=maximum):
        if not isinstance(item, Mapping):
            raise ValueError(f"each {name} item must be an object")
        result.append({
            "title": _bounded(item.get("title"), f"{name}.title", limit=160),
            "description": _bounded(item.get("description"), f"{name}.description", limit=600),
        })
    if len(result) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} item(s)")
    return tuple(result)


def _faq(value: Any) -> tuple[dict[str, str], ...]:
    result = []
    for item in _sequence(value, "faq", maximum=6):
        if not isinstance(item, Mapping):
            raise ValueError("each FAQ item must be an object")
        result.append({
            "question": _bounded(item.get("question"), "faq.question", limit=240),
            "answer": _bounded(item.get("answer"), "faq.answer", limit=1000),
        })
    return tuple(result)


@dataclass(frozen=True, slots=True)
class LandingBrief:
    business_idea: str
    target_audience: str
    pain: str
    promise: str
    honest_limitation: str
    key_features: tuple[dict[str, str], ...]
    steps: tuple[dict[str, str], ...]
    proof_points: tuple[str, ...]
    faq: tuple[dict[str, str], ...]
    cta: dict[str, str]
    privacy_policy_url: str
    language: str = "uk"
    source: Mapping[str, str] | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LandingBrief":
        language = str(value.get("language") or "uk").lower()
        if language not in {"uk", "en"}:
            raise ValueError("language must be uk or en")
        raw_source = value.get("source") if isinstance(value.get("source"), Mapping) else {}
        source: dict[str, str] = {}
        for key in ("positioning_project_id", "positioning_revision_id"):
            try:
                source[key] = str(UUID(str(raw_source.get(key))))
            except (TypeError, ValueError) as error:
                raise ValueError(f"source.{key} must be a UUID") from error
        raw_cta = value.get("cta") if isinstance(value.get("cta"), Mapping) else {}
        if str(raw_cta.get("url") or "#lead-form") != "#lead-form":
            raise ValueError("Natal CTA destination is protected")
        return cls(
            business_idea=_bounded(value.get("business_idea"), "business_idea", limit=500),
            target_audience=_bounded(value.get("target_audience"), "target_audience", limit=500),
            pain=_bounded(value.get("pain"), "pain", limit=1000),
            promise=_bounded(value.get("promise"), "promise", limit=1000),
            honest_limitation=_bounded(value.get("honest_limitation"), "honest_limitation", limit=1000),
            key_features=_pairs(value.get("key_features"), "key_features", minimum=1, maximum=6),
            steps=_pairs(value.get("steps"), "steps", minimum=2, maximum=5),
            proof_points=tuple(_bounded(item, "proof point", limit=280) for item in _sequence(value.get("proof_points"), "proof_points", maximum=4)),
            faq=_faq(value.get("faq")),
            cta={
                "label": _bounded(raw_cta.get("label") or ("Залишити контакти" if language == "uk" else "Leave details"), "cta.label", limit=100),
                "url": "#lead-form",
            },
            privacy_policy_url=_https(value.get("privacy_policy_url"), "privacy_policy_url"),
            language=language,
            source=source,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2, "brand": "Natal", "language": self.language,
            "source": dict(self.source or {}), "privacy_policy_url": self.privacy_policy_url,
            "business_idea": self.business_idea, "target_audience": self.target_audience,
            "pain": self.pain, "promise": self.promise,
            "honest_limitation": self.honest_limitation,
            "key_features": list(self.key_features), "steps": list(self.steps),
            "proof_points": list(self.proof_points), "faq": list(self.faq), "cta": dict(self.cta),
        }


def _show(statement: Mapping[str, Any]) -> str:
    return _bounded(statement.get("text"), "positioning statement", limit=2000)


def brief_from_positioning(
    project: Mapping[str, Any], revision: Mapping[str, Any], *, privacy_policy_url: str
) -> dict[str, Any]:
    """Map one active approved revision to the only accepted Landing source."""
    if not revision.get("approved") or revision.get("project_id") != project.get("id"):
        raise ValueError("Landing requires the active approved positioning revision")
    document = revision.get("document")
    if not isinstance(document, Mapping):
        raise ValueError("approved positioning document is unavailable")
    language = str(document.get("output_language") or "uk")
    foundation = document["positioning_foundation"]
    landing = document["landing_copy"]
    matrix = document["messaging_matrix"]
    features = [
        {"title": _show(item["feature"]), "description": _show(item["functional_benefit"])}
        for item in matrix[:6]
    ]
    jobs = foundation["jobs"]
    gains = foundation["gains"]
    steps = [
        {"title": f"{index + 1:02d}", "description": _show(item)}
        for index, item in enumerate([*jobs, *gains][:5])
    ]
    while len(steps) < 2:
        steps.append({"title": f"{len(steps) + 1:02d}", "description": _show(foundation["uvp"])})
    proof = []
    for item in landing["value_sections"]:
        body = item["body"]
        if body.get("source_ids") and body.get("assumption") is not True:
            proof.append(_show(body))
    faqs = [
        {"question": _show(item["question"]), "answer": " ".join(_show(item[key]) for key in ("definition", "data", "context"))}
        for item in document["aeo_faqs"]
    ]
    brief = LandingBrief.from_dict({
        "language": language,
        "source": {"positioning_project_id": project["id"], "positioning_revision_id": revision["id"]},
        "privacy_policy_url": privacy_policy_url,
        "business_idea": _show(landing["hero"]["headline"]),
        "target_audience": _show(foundation["definitive_audience"]),
        "pain": _show(foundation["pains"][0]),
        "promise": _show(foundation["uvp"]),
        "honest_limitation": _show(landing["honest_limitation"]),
        "key_features": features,
        "steps": steps,
        "proof_points": proof[:4],
        "faq": faqs,
        "cta": {"label": _show(landing["hero"]["cta"]), "url": "#lead-form"},
    }).to_dict()
    return {
        "positioning_project_id": project["id"],
        "positioning_revision_id": revision["id"],
        "recommended_template_id": recommend_template(document),
        "brief": brief,
    }
