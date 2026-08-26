"""Channel adapters and deterministic previews for generic Result candidates."""

from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import textwrap
from typing import Any, Mapping, Protocol, Sequence

from commander.ids import new_uuid7

from .content import CandidateV2
from .studio import DEFAULT_GUARDS, DEFAULT_SOURCE_REFS, validate_recipe


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

    @staticmethod
    def _frame(
        instance_id: str, tool_id: str, frame: tuple[float, float, float, float], z: int,
        *, params: Mapping[str, Any], source_asset_ids: Sequence[str] = (),
    ) -> dict[str, Any]:
        x, y, width, height = frame
        return {
            "instance_id": instance_id, "tool_id": tool_id,
            "frame": {"x": x, "y": y, "width": width, "height": height},
            "z_index": z, "params": dict(params), "timeline": None,
            "source_asset_ids": list(source_asset_ids),
        }

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
        logo_id = brand.get("logo_source_asset_id")
        if not logo_id:
            raise ValueError("Instagram Result generation requires a Project brand kit logo")
        colors = list(brand.get("colors") or [])
        dark = colors[0] if colors else "#0C0E12"
        light = next((item for item in colors if item.upper() in {"#F4F6FA", "#FFFFFF"}), "#F4F6FA")
        accent = colors[-1] if colors else "#43BDD3"
        template_id = str(run["candidate_template_id"])
        parameters = dict(run["candidate_parameters"])
        layouts = {
            "moment_tension": {
                "media": (0, 0, 1, .52), "headline": (.06, .55, .88, .10),
                "body": (.06, .66, .88, .075), "headline_size": 54, "body_size": 25,
            },
            "contrast_reframe": {
                "media": (.50, .04, .50, .67), "headline": (.06, .10, .38, .21),
                "body": (.06, .35, .38, .24), "headline_size": 43, "body_size": 23,
            },
            "mechanism_proof": {
                "media": (.06, .05, .88, .43), "headline": (.06, .52, .88, .09),
                "body": (.06, .62, .88, .105), "headline_size": 46, "body_size": 24,
            },
            "human_story": {
                "media": (0, 0, 1, .56), "headline": (.06, .59, .88, .09),
                "body": (.06, .69, .88, .055), "headline_size": 45, "body_size": 22,
            },
            "direct_offer": {
                "media": (.61, .07, .33, .39), "headline": (.06, .12, .49, .17),
                "body": (.06, .33, .49, .15), "headline_size": 48, "body_size": 23,
            },
        }
        if template_id not in layouts:
            raise ValueError("Instagram adapter received an unknown template personality")
        layout = layouts[template_id]
        visual_by_role = {
            str(item["role"]): str(item["content"]) for item in candidate["visual_components"]
        }
        composition = visual_by_role.get("composition", "").casefold()
        focal_x = .30 if any(word in composition for word in ("left", "ліворуч", "зліва")) else (
            .70 if any(word in composition for word in ("right", "праворуч", "справа")) else .50
        )
        frame = self._frame
        frames = [
            frame(element_ids["background"], "studio.frame.shape.v1", (0, 0, 1, 1), 0,
                  params={"background": dark, "opacity": 1, "radius": 0}),
            frame(element_ids["primary_subject"], "studio.frame.media.v1", layout["media"], 1,
                  params={"fit": "cover", "focal_x": focal_x, "focal_y": .5}, source_asset_ids=[media_id]),
            frame(element_ids["headline_block"], "studio.frame.headline.v1", layout["headline"], 2,
                  params={"text": candidate["hook"], "color": light,
                          "font_size": layout["headline_size"], "min_font_size": 21,
                          "max_lines": 4, "line_height": 1.02}),
            frame(element_ids["supporting_text_block"], "studio.frame.body.v1", layout["body"], 3,
                  params={"text": candidate["supporting_text"], "color": light,
                          "font_size": layout["body_size"], "min_font_size": 17,
                          "max_lines": 6, "line_height": 1.04}),
            frame(element_ids["offer_block"], "studio.frame.offer.v1", (.06, .79, .88, .055), 4,
                  params={"text": candidate["offer"], "color": accent, "font_size": 27,
                          "min_font_size": 18, "max_lines": 2, "line_height": 1.02}),
            frame(new_uuid7(), "studio.frame.shape.v1", (.49, .86, .45, .08), 5,
                  params={"background": accent, "opacity": 1, "radius": 20}),
            frame(element_ids["cta_block"], "studio.frame.cta.v1", (.50, .87, .43, .06), 6,
                  params={"text": candidate["cta"], "color": dark, "font_size": 25,
                          "min_font_size": 17, "max_lines": 2, "align": "center", "vertical_align": "center"}),
            frame(element_ids["brand_mark"], "studio.frame.logo.v1", (.06, .865, .26, .07), 7,
                  params={"fit": "contain"}, source_asset_ids=[str(logo_id)]),
        ]
        return {
            "schema_version": 2, "parent_recipe_id": None,
            "placement_tool_id": "studio.placement.instagram.feed_square.v1",
            "duration_seconds": None, "frame_rate": None,
            "frames": frames,
            "modifiers": [{
                "instance_id": new_uuid7(), "tool_id": "studio.layout.single_visual.v1",
                "params": {
                    "template_personality": template_id,
                    "visual_complexity": int(parameters["visual_complexity"]),
                    "composition_direction": visual_by_role.get("composition", ""),
                    "lighting_style": visual_by_role.get("lighting_style", ""),
                },
            }],
            "strategy_ids": [
                "studio.strategy.one_message.v1", "studio.strategy.specific_cta.v1",
                "studio.strategy.visual_proof.v1",
            ],
            "validation_ids": list(DEFAULT_GUARDS),
            "source_reference_ids": list(DEFAULT_SOURCE_REFS),
            "share": {"caption": candidate["caption"], "alt_text": candidate["alt_text"]},
        }

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
            text_by_tool = {
                "studio.frame.headline.v1": candidate.value["hook"],
                "studio.frame.body.v1": candidate.value["supporting_text"],
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
