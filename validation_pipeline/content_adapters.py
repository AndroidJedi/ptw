"""Channel adapters and deterministic previews for generic Result candidates."""

from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import textwrap
from typing import Any, Mapping, Protocol

from .content import CandidateV2
from .studio import validate_recipe
from .studio_templates import StudioTemplateRegistry, apply_studio_template


TEXT_PREVIEW_RENDERER_VERSION = "ptw-content-text-preview-v1"
GRAPHIC_PERMISSION_PATTERN = re.compile(
    r"(?:non[- ]human|abstract|без людей|без облич|неживу|абстрактн).{0,80}"
    r"(?:graphic|illustration|image|графік|ілюстрац|зображ)",
    re.IGNORECASE,
)


def task_permits_non_human_graphic(task: str) -> bool:
    return GRAPHIC_PERMISSION_PATTERN.search(task) is not None


class ResultProfileAdapter(Protocol):
    profile_id: str

    def materialize(
        self, *, candidate: CandidateV2, run: Mapping[str, Any],
        element_ids: Mapping[str, str], requested_by: str,
    ) -> Mapping[str, Any]: ...


class TextPreviewRenderer:
    WIDTH = 1080
    HEIGHT = 1080

    def __init__(self, font_path: Path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")) -> None:
        self.font_path = font_path

    def _font(self, size: int, *, bold: bool = False):
        from PIL import ImageFont

        paths = (
            self.font_path,
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        )
        for path in paths:
            try:
                font = ImageFont.truetype(str(path), size)
                if bold:
                    try:
                        font.set_variation_by_name("Bold")
                    except (AttributeError, OSError):
                        pass
                return font
            except OSError:
                continue
        raise RuntimeError("a deterministic Result preview font is unavailable")

    def render(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), "#F4F2EC")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((56, 48, 1024, 1032), radius=32, fill="#FFFFFF", outline="#D7D2C8", width=2)
        draw.text((92, 82), "PTW · TEXT RESULT PREVIEW", font=self._font(22, bold=True), fill="#5E5A52")
        y = 148
        for text, size, color, width, gap in (
            (str(candidate["hook"]), 58, "#111111", 29, 34),
            (str(candidate["headline"]), 38, "#2C2A27", 42, 26),
            (str(candidate["primary_text"]), 28, "#403D38", 61, 24),
            (str(candidate["supporting_text"]), 24, "#69645B", 70, 26),
        ):
            lines = textwrap.wrap(text, width=width)[:6]
            value = "\n".join(lines)
            font = self._font(size, bold=size >= 38)
            draw.multiline_text((92, y), value, font=font, fill=color, spacing=8)
            bounds = draw.multiline_textbbox((92, y), value, font=font, spacing=8)
            y = min(790, bounds[3] + gap)
        draw.rounded_rectangle((92, 838, 988, 916), radius=16, fill="#E6F4F6")
        draw.text((116, 856), textwrap.shorten(str(candidate["offer"]), width=58, placeholder="…"), font=self._font(27, bold=True), fill="#174B54")
        draw.rounded_rectangle((92, 938, 620, 1000), radius=15, fill="#111111")
        draw.text((116, 953), textwrap.shorten(str(candidate["cta"]), width=38, placeholder="…"), font=self._font(24, bold=True), fill="#FFFFFF")
        output = BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True, progressive=False)
        data = output.getvalue()
        return {
            "bytes": data, "sha256": hashlib.sha256(data).hexdigest(),
            "mime_type": "image/jpeg", "width": 1080, "height": 1080,
            "renderer_version": TEXT_PREVIEW_RENDERER_VERSION,
        }


class MarketingCopyAdapter:
    profile_id = "marketing_copy_v1"

    def __init__(self, preview_renderer: TextPreviewRenderer | None = None) -> None:
        self.preview_renderer = preview_renderer or TextPreviewRenderer()

    def materialize(
        self, *, candidate: CandidateV2, run: Mapping[str, Any],
        element_ids: Mapping[str, str], requested_by: str,
    ) -> Mapping[str, Any]:
        del run, element_ids, requested_by
        if candidate.value["media_request"]["kind"] != "none" or candidate.value["visual_components"]:
            raise ValueError("text Result candidates cannot cross the visual adapter boundary")
        return {"recipe": None, "render": None, "preview": self.preview_renderer.render(candidate.value)}


class InstagramStaticAdapter:
    profile_id = "instagram_static_ad_v1"

    def __init__(self, repository: Any, renderer: Any, pexels: Any, bridge: Any) -> None:
        self.repository = repository
        self.renderer = renderer
        self.pexels = pexels
        self.bridge = bridge

    def _resolve_media(
        self, *, request: Mapping[str, Any], run: Mapping[str, Any], requested_by: str,
    ) -> tuple[Mapping[str, Any], bool]:
        approved = {
            item["source_asset_id"]: item for item in run["context_bundle"]["approved_sources"]
            if item.get("source_asset_id")
        }
        kind = request["kind"]
        if kind in {"pexels_real_photo", "non_human_graphic"}:
            persisted = self.repository.get_candidate_media_asset(run["candidate_id"])
            if persisted is not None:
                expected = hashlib.sha256(json.dumps(
                    request, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ).encode()).hexdigest()
                if persisted["metadata"].get("media_request_sha256") != expected:
                    raise ValueError("candidate media request cannot change after source resolution")
                return persisted, False
        if kind == "approved_asset":
            source_id = str(request["source_asset_id"])
            if source_id not in approved:
                raise ValueError("candidate media is not one of the snapshotted approved Project assets")
            return self.repository.get_project_asset(source_id), False
        if kind == "pexels_real_photo":
            photo, data = self.pexels.select(
                str(request["query"]), str(run["context_bundle"]["brief"]["document"]["product"]),
                used_ids=set(run.get("used_pexels_ids") or []),
            )
            metadata = photo.source_metadata()
            request_digest = hashlib.sha256(json.dumps(
                request, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()
            source = self.repository.create_project_asset(
                run["project_id"], title=f"Pexels · {photo.photographer}", data=data,
                mime_type="image/jpeg", origin="pexels", provider="pexels",
                external_id=photo.photo_id, source_uri=photo.page_url,
                license_name=metadata["license"], attribution=metadata["attribution"],
                metadata={
                    **metadata, "alt": photo.alt, "no_synthetic_people": True,
                    "content_candidate_id": run["candidate_id"],
                    "media_request_sha256": request_digest,
                },
                requested_by=requested_by,
            )
            return source, False
        if kind == "non_human_graphic":
            if not task_permits_non_human_graphic(str(run["task"])):
                raise ValueError("the owner task did not explicitly permit a non-human generated graphic")
            if int(run["budget_state"].get("graphic_generation_remaining", 0)) < 1:
                raise ValueError("the one-call non-human graphic budget is exhausted")
            graphic = self.bridge.generate_non_human_graphic(
                system_prompt=(
                    "Generate exactly one square non-human graphic. No people, faces, text, letters, "
                    "numbers, logos, watermarks, proof claims, urgency, or brand impersonation."
                ),
                input_payload={
                    "instruction": request["query"],
                    "brand": run["context_bundle"]["brand_kit"]["document"],
                    "run_id": run["run_id"],
                },
                output_schema={
                    "type": "object", "additionalProperties": False,
                    "required": ["title", "alt_text"],
                    "properties": {
                        "title": {"type": "string", "minLength": 1, "maxLength": 120},
                        "alt_text": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                },
                prompt_version="ptw-content-non-human-graphic-v1",
                idempotency_key=f"{run['run_id']}:content_non_human_graphic_generation",
            )
            image = dict(graphic["image"])
            data = bytes(image.pop("bytes"))
            image.pop("asset_url", None)
            source = self.repository.create_project_asset(
                run["project_id"], title=str(graphic["response"]["title"]), data=data,
                mime_type="image/png", origin="ai_generated", provider=str(image["provider"]),
                external_id=f'content-bridge:{image["request_id"]}', source_uri=None,
                license_name="PTW generated non-human graphic",
                attribution="Generated for this PTW Result under the non-human media policy",
                metadata={
                    **image, "bridge_invocation": graphic["invocation"],
                    "no_synthetic_people": True, "alt_text": graphic["response"]["alt_text"],
                    "content_candidate_id": run["candidate_id"],
                    "media_request_sha256": hashlib.sha256(json.dumps(
                        request, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                    ).encode()).hexdigest(),
                }, requested_by=requested_by, approval_status="pending_review",
            )
            return source, True
        raise ValueError("Instagram Result media request is unsupported")

    def _recipe(
        self, *, candidate: Mapping[str, Any], run: Mapping[str, Any],
        element_ids: Mapping[str, str], media_id: str,
    ) -> Mapping[str, Any]:
        brand = run["context_bundle"]["brand_kit"]["document"]
        template_id = str(run["candidate_template_id"])
        parameters = dict(run["candidate_parameters"])
        studio_template = StudioTemplateRegistry().get(template_id)
        context_version = next((
            item for item in run["context_bundle"]["template_versions"]
            if item["template_id"] == template_id
        ), None)
        if context_version is None:
            raise ValueError("Instagram adapter cannot resolve the snapshotted strategy template")
        if (
            int(context_version["studio_template_version"]) != studio_template.version
            or context_version["studio_template_sha256"] != studio_template.digest
        ):
            raise ValueError("snapshotted strategy and Studio template identities do not match")
        return apply_studio_template(
            template=studio_template,
            strategy_template={
                "template_id": template_id, "version": int(context_version["version"]),
                "sha256": str(context_version["digest"]),
            },
            slider_values=parameters, candidate=candidate,
            brief=run["context_bundle"]["brief"]["document"],
            brand_document=brand, media_asset_id=media_id,
            semantic_instance_ids=element_ids,
            parent_recipe_id=run.get("parent_recipe_id"),
            base_recipe_sha256=run.get("base_recipe_sha256"),
        )

    def materialize(
        self, *, candidate: CandidateV2, run: Mapping[str, Any],
        element_ids: Mapping[str, str], requested_by: str,
    ) -> Mapping[str, Any]:
        existing_recipe = self.repository.get_candidate_recipe(run["candidate_id"])
        if existing_recipe is not None:
            render = self.repository.get_recipe_render(existing_recipe["recipe_id"])
            if render is None:
                render = self.repository.render_recipe(existing_recipe["recipe_id"], self.renderer)
            primary = next(
                item for item in existing_recipe["document"]["frames"]
                if item["tool_id"] == "studio.frame.media.v1"
            )
            media_ids = list(primary["source_asset_ids"])
            if len(media_ids) != 1:
                raise ValueError("persisted candidate recipe has no exact primary media source")
            template_version = int(
                existing_recipe["document"]["modifiers"][0]["params"]["studio_template"]["version"]
            )
            text_by_tool = {
                "studio.frame.headline.v1": candidate.value[
                    "headline" if template_version >= 3 else "hook"
                ],
                "studio.frame.body.v1": candidate.value[
                    "primary_text" if template_version >= 3 else "supporting_text"
                ],
                "studio.frame.offer.v1": candidate.value["offer"],
                "studio.frame.cta.v1": candidate.value["cta"],
            }
            for frame in existing_recipe["document"]["frames"]:
                expected_text = text_by_tool.get(frame["tool_id"])
                if expected_text is not None and frame["params"].get("text") != expected_text:
                    raise ValueError("persisted candidate recipe copy cannot change on restart")
            if existing_recipe["document"]["share"] != {
                "caption": candidate.value["caption"], "alt_text": candidate.value["alt_text"],
            }:
                raise ValueError("persisted candidate share copy cannot change on restart")
            return {
                "recipe": existing_recipe, "render": render, "preview": None,
                "media_source": self.repository.get_project_asset(media_ids[0]),
                "graphic_generation_consumed": False,
            }
        media, consumed_graphic = self._resolve_media(
            request=candidate.value["media_request"], run=run, requested_by=requested_by,
        )
        recipe_submission = self._recipe(
            candidate=candidate.value, run=run, element_ids=element_ids,
            media_id=str(media["source_asset_id"]),
        )
        # Validate at the adapter boundary before any immutable Studio row is written.
        validate_recipe(
            recipe_submission, project_id=run["project_id"], brief_id=run["brief_id"],
            brand_kit_id=run["brand_kit_id"], brief=run["context_bundle"]["brief"]["document"],
            brand_document=run["context_bundle"]["brand_kit"]["document"],
        )
        recipe = self.repository.create_recipe(
            run["project_id"], candidate_id=run["candidate_id"], brief_id=run["brief_id"],
            brand_kit_id=run["brand_kit_id"],
            document=recipe_submission, requested_by=requested_by,
        )
        render = self.repository.render_recipe(recipe["recipe_id"], self.renderer)
        return {
            "recipe": recipe, "render": render, "preview": None,
            "media_source": media, "graphic_generation_consumed": consumed_graphic,
        }


def adapter_for_profile(
    profile: str, *, repository: Any, renderer: Any, pexels: Any, bridge: Any,
) -> ResultProfileAdapter:
    if profile == "marketing_copy_v1":
        return MarketingCopyAdapter()
    if profile == "instagram_static_ad_v1":
        return InstagramStaticAdapter(repository, renderer, pexels, bridge)
    raise ValueError("unknown Result output profile")
