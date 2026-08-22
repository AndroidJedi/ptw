"""Bounded landing brief derived from completed Idea Laval evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from .catalog import recommend_template


def _text(value: Any, language: str = "uk") -> str:
    if isinstance(value, Mapping):
        return str(value.get(language) or value.get("en") or value.get("uk") or "").strip()
    return str(value or "").strip()


def _bounded(value: Any, name: str, *, limit: int, required: bool = True) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValueError(f"{name} is required")
    if len(result) > limit:
        raise ValueError(f"{name} must contain at most {limit} characters")
    return result


def _cta_url(value: Any) -> str:
    url = _bounded(value or "#contact", "cta.url", limit=2000)
    if url.startswith("#"):
        return url
    if url.startswith("/") and not url.startswith("//"):
        return url
    parsed = urlsplit(url)
    if parsed.scheme in {"https", "http"} and parsed.netloc:
        return url
    if parsed.scheme == "mailto" and parsed.path:
        return url
    raise ValueError("cta.url must be an HTTP(S), mailto, root-relative, or fragment URL")


@dataclass(frozen=True, slots=True)
class LandingBrief:
    business_idea: str
    target_audience: str
    pain: str
    promise: str
    key_features: tuple[dict[str, str], ...]
    steps: tuple[dict[str, str], ...]
    proof_points: tuple[str, ...]
    faq: tuple[dict[str, str], ...]
    cta: dict[str, str]
    language: str = "uk"
    source: Mapping[str, str] | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LandingBrief":
        language = str(value.get("language") or "uk").lower()
        if language not in {"uk", "en"}:
            raise ValueError("language must be uk or en")
        features = _pairs(value.get("key_features"), "key_features", minimum=1, maximum=6)
        steps = _pairs(value.get("steps"), "steps", minimum=2, maximum=5)
        faq = _faq(value.get("faq"))
        proof = tuple(
            _bounded(item, "proof point", limit=280)
            for item in _sequence(value.get("proof_points"), "proof_points", maximum=4)
        )
        raw_cta = value.get("cta") if isinstance(value.get("cta"), Mapping) else {}
        raw_source = value.get("source") if isinstance(value.get("source"), Mapping) else {}
        source = {
            key: _bounded(raw_source.get(key), f"source.{key}", limit=100, required=False)
            for key in ("laval_run_id", "thesis_id")
            if raw_source.get(key)
        }
        return cls(
            business_idea=_bounded(value.get("business_idea"), "business_idea", limit=500),
            target_audience=_bounded(value.get("target_audience"), "target_audience", limit=500),
            pain=_bounded(value.get("pain"), "pain", limit=1000),
            promise=_bounded(value.get("promise"), "promise", limit=1000),
            key_features=features,
            steps=steps,
            proof_points=proof,
            faq=faq,
            cta={
                "label": _bounded(raw_cta.get("label") or ("Спробувати Natal" if language == "uk" else "Try Natal"), "cta.label", limit=100),
                "url": _cta_url(raw_cta.get("url")),
            },
            language=language,
            source=source or None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "brand": "Natal",
            "language": self.language,
            "source": dict(self.source or {}),
            "business_idea": self.business_idea,
            "target_audience": self.target_audience,
            "pain": self.pain,
            "promise": self.promise,
            "key_features": list(self.key_features),
            "steps": list(self.steps),
            "proof_points": list(self.proof_points),
            "faq": list(self.faq),
            "cta": dict(self.cta),
        }


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
            raise ValueError("each faq item must be an object")
        result.append({
            "question": _bounded(item.get("question"), "faq.question", limit=240),
            "answer": _bounded(item.get("answer"), "faq.answer", limit=1000),
        })
    return tuple(result)


def brief_from_candidate(candidate: Mapping[str, Any], language: str = "uk") -> dict[str, Any]:
    """Map an already-completed evaluation into editable, source-ID-explicit copy."""

    theses = [item for item in candidate.get("theses") or [] if isinstance(item, Mapping)]
    recommended_id = str(candidate.get("recommended_thesis_id") or "")
    thesis = next(
        (item for item in theses if str(item.get("id")) == recommended_id),
        next((item for item in theses if item.get("recommended") is True), theses[0] if theses else {}),
    )
    mechanisms = [item for item in candidate.get("mechanisms") or [] if isinstance(item, Mapping)]
    wanted_ids = {str(item) for item in thesis.get("mechanism_ids") or []}
    selected_mechanisms = [item for item in mechanisms if not wanted_ids or str(item.get("id")) in wanted_ids]
    features = [
        {"title": _text(item.get("name"), language), "description": _text(item.get("description"), language)}
        for item in selected_mechanisms[:6]
        if _text(item.get("name"), language) and _text(item.get("description"), language)
    ]
    loop_steps = [_text(item, language) for item in thesis.get("loop_steps") or []]
    if not features:
        features = [
            {"title": f"{('Крок' if language == 'uk' else 'Step')} {index + 1}", "description": step}
            for index, step in enumerate(loop_steps[:4]) if step
        ]
    if not features:
        features = [{
            "title": "Ключова цінність" if language == "uk" else "Core value",
            "description": _text(candidate.get("owner_idea"), language),
        }]
    steps = [
        {"title": f"{index + 1:02d}", "description": step}
        for index, step in enumerate(loop_steps[:5]) if step
    ] or [
        {"title": "01", "description": _text(thesis.get("zero_audience_behavior"), language) or features[0]["description"]},
        {"title": "02", "description": _text(thesis.get("value_moment"), language) or features[-1]["description"]},
    ]
    business_idea = _text(thesis.get("title"), language) or _text(candidate.get("owner_idea"), language)
    target = _text(thesis.get("target_user"), language) or ("Цільова аудиторія з оцінки ідеї" if language == "uk" else "Target audience from the idea evaluation")
    pain = _text(thesis.get("problem"), language) or _text(candidate.get("owner_idea"), language)
    promise = _text(thesis.get("value_moment"), language) or business_idea
    run_id = str(candidate.get("idea_run_id") or "")
    thesis_id = str(thesis.get("id") or "")
    brief = LandingBrief.from_dict({
        "business_idea": business_idea,
        "target_audience": target,
        "pain": pain,
        "promise": promise,
        "key_features": features,
        "steps": steps,
        "proof_points": [],
        "faq": [],
        "cta": {
            "label": "Спробувати Natal" if language == "uk" else "Try Natal",
            "url": "#contact",
        },
        "language": language,
        "source": {"laval_run_id": run_id, **({"thesis_id": thesis_id} if thesis_id else {})},
    }).to_dict()
    return {
        "idea_run_id": run_id,
        "recommended_template_id": recommend_template(candidate),
        "brief": brief,
        "quality": dict(candidate.get("quality") or {}),
        "verdict": thesis.get("verdict"),
    }


def apply_brief_overrides(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Allow copy edits while retaining server-resolved source IDs and Natal brand."""

    allowed = {
        "business_idea", "target_audience", "pain", "promise", "key_features",
        "steps", "proof_points", "faq", "cta", "language",
    }
    merged = {**dict(base), **{key: value for key, value in overrides.items() if key in allowed}}
    merged["source"] = dict(base.get("source") or {})
    merged.pop("brand", None)
    return LandingBrief.from_dict(merged).to_dict()
