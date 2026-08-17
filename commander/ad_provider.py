"""Provider ports and OpenAI adapters for ten-context ad generation."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
import io
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol


@dataclass(frozen=True, slots=True)
class AdContextSnapshot:
    code: str
    version: int
    name: str
    prompt: str


@dataclass(frozen=True, slots=True)
class AdCreativeSpec:
    concept_name: str
    audience: str
    angle: str
    hook: str
    supporting_copy: str
    cta: str
    visual_prompt: str
    i18n: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AdCreativeSpec":
        limits = {
            "concept_name": 80,
            "audience": 300,
            "angle": 300,
            "hook": 180,
            "supporting_copy": 280,
            "cta": 60,
            "visual_prompt": 1800,
        }
        fields: dict[str, str] = {}
        localized: dict[str, Mapping[str, str]] = {}
        for key, limit in limits.items():
            stored_i18n = value.get("i18n")
            raw = stored_i18n.get(key) if key != "visual_prompt" and isinstance(stored_i18n, Mapping) and key in stored_i18n else value.get(key, "")
            if key != "visual_prompt" and isinstance(raw, Mapping):
                if set(raw) != {"en", "uk"}:
                    raise ValueError(f"ad creative spec {key} must contain exactly en and uk")
                en, uk = str(raw["en"]).strip(), str(raw["uk"]).strip()
                if not en or not uk:
                    raise ValueError(f"ad creative spec {key} translations are required")
                if max(len(en), len(uk)) > limit:
                    raise ValueError(f"ad creative spec {key} exceeds {limit} characters")
                item = en
                localized[key] = {"en": en, "uk": uk}
            else:
                item = str(raw).strip()
                if key != "visual_prompt":
                    localized[key] = {"en": item, "uk": item}
            if not item:
                raise ValueError(f"ad creative spec is missing {key}")
            if len(item) > limit:
                raise ValueError(f"ad creative spec {key} exceeds {limit} characters")
            fields[key] = item
        forbidden = (
            "guaranteed results",
            "millions of users",
            "#1 rated",
            "clinically proven",
            "customer testimonial",
        )
        searchable = " ".join(fields.values()).lower()
        if any(phrase in searchable for phrase in forbidden):
            raise ValueError("ad creative spec contains an unsupported proof claim")
        visual = fields["visual_prompt"].lower()
        if not any(
            marker in visual
            for marker in ("text-free", "without text", "no text", "no written")
        ):
            raise ValueError("visual_prompt must explicitly require a text-free visual")
        return cls(**fields, i18n=localized)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def display(self, field_name: str, language: str = "uk") -> str:
        values = self.i18n.get(field_name)
        return str(values.get(language, values.get("en", ""))) if values else str(getattr(self, field_name))


@dataclass(frozen=True, slots=True)
class AdContextConclusion:
    feedback_interpretation: str
    effective_elements: str
    improvements: str
    fulfilled_context_intent: bool
    recommended_direction: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AdContextConclusion":
        fields: dict[str, str] = {}
        for key in (
            "feedback_interpretation",
            "effective_elements",
            "improvements",
            "recommended_direction",
        ):
            item = str(value.get(key, "")).strip()
            if not item:
                raise ValueError(f"ad conclusion is missing {key}")
            fields[key] = item[:1200]
        fulfilled = value.get("fulfilled_context_intent")
        if type(fulfilled) is not bool:
            raise ValueError("fulfilled_context_intent must be boolean")
        return cls(fulfilled_context_intent=fulfilled, **fields)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GeneratedAdImage:
    content: bytes
    requested_model: str
    resolved_model: str
    prompt: str
    quality: str
    width: int
    height: int


class AdProvider(Protocol):
    spec_model: str
    image_model: str
    conclusion_model: str

    def generate_spec(
        self, idea: Mapping[str, Any], context: AdContextSnapshot
    ) -> AdCreativeSpec: ...

    def generate_image(self, spec: AdCreativeSpec) -> GeneratedAdImage: ...

    def conclude(
        self,
        *,
        idea: Mapping[str, Any],
        context: AdContextSnapshot,
        spec: AdCreativeSpec,
        image_path: Path,
        predicted_ctr: float,
        rating: int,
        comment: str,
    ) -> AdContextConclusion: ...


class UnavailableAdProvider:
    """Keeps queued work durable while surfacing missing provider configuration."""

    spec_model = "gpt-5-mini"
    image_model = "gpt-image-2"
    conclusion_model = "gpt-5-mini"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def _raise(self):
        raise RuntimeError(self.reason)

    def generate_spec(
        self, idea: Mapping[str, Any], context: AdContextSnapshot
    ) -> AdCreativeSpec:
        del idea, context
        return self._raise()

    def generate_image(self, spec: AdCreativeSpec) -> GeneratedAdImage:
        del spec
        return self._raise()

    def conclude(
        self,
        *,
        idea: Mapping[str, Any],
        context: AdContextSnapshot,
        spec: AdCreativeSpec,
        image_path: Path,
        predicted_ctr: float,
        rating: int,
        comment: str,
    ) -> AdContextConclusion:
        del idea, context, spec, image_path, predicted_ctr, rating, comment
        return self._raise()


class OpenAIAdProvider:
    """High-quality image generation plus owner-grounded multimodal conclusions."""

    def __init__(
        self,
        api_key: str,
        *,
        image_model: str = "gpt-image-2",
        conclusion_model: str = "gpt-5-mini",
        spec_model: str = "gpt-5-mini",
    ) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for ad generation")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.image_model = image_model
        self.conclusion_model = conclusion_model
        self.spec_model = spec_model

    def generate_spec(
        self, idea: Mapping[str, Any], context: AdContextSnapshot
    ) -> AdCreativeSpec:
        prompt = (
            "Create one honest pre-build image-ad specification. Return one JSON object "
            "with concept_name, audience, angle, hook, supporting_copy, and cta as objects "
            "containing exactly {en, uk}; visual_prompt remains an English string. English "
            "is the source contract and Ukrainian must be a faithful translation. Use the "
            "supplied English idea title as concept_name.en. The visual_prompt must request a text-free visual with a clear "
            "copy-safe area; do not ask the image model to draw words, logos, UI text, "
            "testimonials, usage numbers, rankings, guarantees, or unsupported proof. "
            "Use an honest LEARN MORE or JOIN THE WAITLIST CTA.\n\n"
            f"Context {context.code} v{context.version} — {context.name}:\n"
            f"{context.prompt}\n\nIdea snapshot:\n"
            f"{json.dumps(dict(idea), ensure_ascii=False, default=str)}"
        )
        response = self.client.responses.create(
            model=self.spec_model,
            input=prompt,
            store=False,
        )
        spec = AdCreativeSpec.from_mapping(_json_object(response.output_text))
        title = str(idea.get("title", "")).strip()
        if not title or spec.concept_name.casefold() != title.casefold():
            raise ValueError("ad concept_name must exactly match the idea title")
        if spec.cta.upper() not in {"LEARN MORE", "JOIN THE WAITLIST"}:
            raise ValueError("pre-build ad CTA must be LEARN MORE or JOIN THE WAITLIST")
        idea_numbers = set(re.findall(r"\d+(?:[.,]\d+)?%?", json.dumps(dict(idea))))
        copy_numbers = set(
            re.findall(
                r"\d+(?:[.,]\d+)?%?",
                " ".join((spec.angle, spec.hook, spec.supporting_copy)),
            )
        )
        if not copy_numbers.issubset(idea_numbers):
            raise ValueError("ad creative spec introduced an unsupported numeric claim")
        return spec

    def generate_image(self, spec: AdCreativeSpec) -> GeneratedAdImage:
        prompt = (
            f"{spec.visual_prompt}\n\n"
            "Create a premium portrait advertising visual. No written words, letters, "
            "numbers, logos, watermarks, app-interface text, fake testimonials, badges, "
            "or statistical claims. Reserve calm negative space for typography that will "
            "be added later. Use polished commercial art direction and coherent lighting."
        )
        response = self.client.images.generate(
            model=self.image_model,
            prompt=prompt,
            quality="high",
            size="1536x1920",
            output_format="png",
            n=1,
        )
        if not response.data or not response.data[0].b64_json:
            raise RuntimeError("GPT Image 2 returned no image data")
        return GeneratedAdImage(
            content=base64.b64decode(response.data[0].b64_json),
            requested_model=self.image_model,
            resolved_model=str(getattr(response, "model", None) or self.image_model),
            prompt=prompt,
            quality="high",
            width=1536,
            height=1920,
        )

    def conclude(
        self,
        *,
        idea: Mapping[str, Any],
        context: AdContextSnapshot,
        spec: AdCreativeSpec,
        image_path: Path,
        predicted_ctr: float,
        rating: int,
        comment: str,
    ) -> AdContextConclusion:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = (
            "You are the same context agent that produced this image post. Examine the "
            "actual final image and draw conclusions on top of the owner's feedback. "
            "Return one JSON object with feedback_interpretation, effective_elements, "
            "improvements, fulfilled_context_intent (boolean), and recommended_direction. "
            "Do not invent analytics or replace the owner's judgment.\n\n"
            f"Context {context.code} v{context.version} — {context.name}: {context.prompt}\n"
            f"Original specification: {json.dumps(spec.to_dict(), ensure_ascii=False)}\n"
            f"Idea: {json.dumps(dict(idea), ensure_ascii=False, default=str)}\n"
            f"Owner predicted link CTR: {predicted_ctr:g}%\n"
            f"Owner rating: {rating}/5\nOwner comment: {comment or '(none)'}"
        )
        response = self.client.responses.create(
            model=self.conclusion_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{encoded}",
                            "detail": "high",
                        },
                    ],
                }
            ],
            store=False,
        )
        return AdContextConclusion.from_mapping(_json_object(response.output_text))


class DeterministicAdProvider:
    """Dependency-free provider fake for tests and local workflow demos."""

    spec_model = "deterministic-ad-spec-v1"
    image_model = "deterministic-image-v1"
    conclusion_model = "deterministic-conclusion-v1"

    def __init__(self) -> None:
        self.spec_calls: list[str] = []
        self.image_calls: list[str] = []
        self.conclusion_calls: list[str] = []

    def generate_spec(
        self, idea: Mapping[str, Any], context: AdContextSnapshot
    ) -> AdCreativeSpec:
        self.spec_calls.append(context.code)
        title = str(idea["title"])
        return AdCreativeSpec.from_mapping(
            {
                "concept_name": title,
                "audience": str(idea.get("audience") or "People who feel this problem"),
                "angle": f"{context.name}: {idea.get('one_liner', title)}",
                "hook": f"{context.name}: a better way starts here",
                "supporting_copy": str(idea.get("one_liner") or title),
                "cta": "LEARN MORE",
                "visual_prompt": (
                    f"Text-free premium editorial scene for {title}; visual direction "
                    f"expresses {context.name}; generous copy-safe negative space."
                ),
            }
        )

    def generate_image(self, spec: AdCreativeSpec) -> GeneratedAdImage:
        from PIL import Image, ImageDraw

        self.image_calls.append(spec.angle)
        digest = sum(spec.angle.encode("utf-8"))
        color = (30 + digest % 80, 35 + (digest * 3) % 90, 85 + (digest * 5) % 120)
        image = Image.new("RGB", (1536, 1920), color)
        draw = ImageDraw.Draw(image)
        draw.ellipse((320, 320, 1340, 1340), fill=(230, 38, 112))
        draw.rectangle((0, 1450, 1536, 1920), fill=(12, 12, 28))
        stream = io.BytesIO()
        image.save(stream, "PNG")
        return GeneratedAdImage(
            content=stream.getvalue(),
            requested_model=self.image_model,
            resolved_model=self.image_model,
            prompt=spec.visual_prompt,
            quality="high",
            width=1536,
            height=1920,
        )

    def conclude(
        self,
        *,
        idea: Mapping[str, Any],
        context: AdContextSnapshot,
        spec: AdCreativeSpec,
        image_path: Path,
        predicted_ctr: float,
        rating: int,
        comment: str,
    ) -> AdContextConclusion:
        del idea, spec
        if not image_path.is_file():
            raise ValueError("final image is missing")
        self.conclusion_calls.append(context.code)
        return AdContextConclusion(
            feedback_interpretation=(
                f"The owner predicts {predicted_ctr:g}% CTR and rates this {rating}/5. "
                f"{comment or 'No additional comment was supplied.'}"
            ),
            effective_elements=f"The final image clearly expresses {context.name}.",
            improvements="Apply the owner's specific criticism in the next revision.",
            fulfilled_context_intent=rating >= 3,
            recommended_direction="Keep the strongest visual cue and simplify the next variation.",
        )


def _json_object(value: str) -> Mapping[str, Any]:
    body = value.strip()
    if body.startswith("```"):
        body = body.removeprefix("```json").removeprefix("```")
        body = body.removesuffix("```").strip()
    result = json.loads(body)
    if not isinstance(result, Mapping):
        raise ValueError("provider must return one JSON object")
    return result
