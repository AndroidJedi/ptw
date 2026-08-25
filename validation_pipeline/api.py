from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import Response

from .config import Settings
from .images import PexelsClient, SquareCreativeRenderer
from .notifications import FailureNotificationClient
from .provider import StructuredBridge
from .repository import ValidationRepository
from .service import ValidationRunner, validate_create_input, validate_revision_input
from .studio import (
    MAX_VIDEO_BYTES, StudioRenderer, _v2_submission, inspect_media,
    studio_recipe_revision_output_schema, tool_catalog,
)


def _matches_media(data: bytes, mime_type: str) -> bool:
    try:
        inspect_media(data, mime_type)
        return True
    except (ValueError, RuntimeError):
        return False


def _requests_generated_graphic(instruction: str) -> bool:
    value = instruction.casefold()
    nouns = ("image", "graphic", "background", "зображ", "графік", "фон", "ілюстра")
    verbs = ("generate", "create", "replace", "regenerate", "згенер", "створ", "замін", "намал")
    return any(word in value for word in nouns) and any(word in value for word in verbs)


def create_app(
    settings: Settings | None = None,
    *,
    repository: ValidationRepository | None = None,
    runner: ValidationRunner | None = None,
    studio_renderer: StudioRenderer | None = None,
    studio_recipe_provider: Any | None = None,
) -> FastAPI:
    settings = settings or Settings.from_environment()
    repository = repository or ValidationRepository(settings.database_url)
    studio_renderer = studio_renderer or StudioRenderer()
    studio_pexels = PexelsClient(settings.pexels_api_key)
    studio_bridge = StructuredBridge(settings.bridge_url, settings.bridge_token, settings.model)
    runner_error: Exception | None = None
    if runner is None:
        try:
            runner = ValidationRunner(
                repository,
                StructuredBridge(settings.bridge_url, settings.bridge_token, settings.model),
                PexelsClient(settings.pexels_api_key),
                SquareCreativeRenderer(),
                product_brief_skill_path=settings.product_brief_skill_path,
                ad_creative_skill_path=settings.ad_creative_skill_path,
                failure_notifier=FailureNotificationClient(
                    settings.failure_notification_url,
                    settings.owner_gateway_token,
                ),
            )
        except Exception as error:
            runner_error = error
    tasks: set[asyncio.Task[Any]] = set()
    stopped = False

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await asyncio.to_thread(repository.recover_interrupted)
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(
        title="PTW Validation API", version="1.0.0", docs_url=None, redoc_url=None, lifespan=lifespan
    )

    def authorize(x_ptw_owner_gateway_token: str = Header(default="")) -> None:
        if not settings.owner_gateway_token or x_ptw_owner_gateway_token != settings.owner_gateway_token:
            raise HTTPException(status_code=401, detail="owner gateway authentication required")

    def require_runner() -> ValidationRunner:
        if runner is None:
            raise HTTPException(status_code=503, detail=str(runner_error or "validation runner is unavailable"))
        if stopped:
            raise HTTPException(status_code=423, detail="PTW emergency stop is active")
        return runner

    def workspace_asset(relative: str) -> Path:
        installed = Path("/app/natal/assets") / relative
        if installed.is_file():
            return installed
        return Path(__file__).resolve().parents[1] / "natal" / "assets" / relative

    def wizard_proposal_builder(
        recipe: Mapping[str, Any], *, instruction: str, target_instance_id: str | None,
        requested_by: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
        if studio_recipe_provider is not None:
            return studio_recipe_provider(
                recipe, instruction=instruction, target_instance_id=target_instance_id,
                requested_by=requested_by,
            )
        if not settings.ad_studio_skill_path.is_file():
            raise RuntimeError("canonical Ad Studio Composer skill is unavailable")
        reference_root = settings.ad_studio_skill_path.parent / "references"
        reference_paths = [reference_root / "recipe-contract.md", reference_root / "owner-lessons.md"]
        if any(not path.is_file() for path in reference_paths):
            raise RuntimeError("canonical Ad Studio recipe references are unavailable")
        skill_snapshot = "\n\n".join(
            [settings.ad_studio_skill_path.read_text(), *[path.read_text() for path in reference_paths]]
        )
        skill_sha256 = hashlib.sha256(skill_snapshot.encode()).hexdigest()
        approved_brief = repository.get_brief(str(recipe["brief_id"]))
        brand_kit = repository.get_studio_brand_kit(str(recipe["brand_kit_id"]))
        project_sources = [{
            key: item.get(key) for key in (
                "source_asset_id", "origin", "title", "mime_type", "width", "height",
                "provider", "external_id", "bytes_sha256", "license", "attribution",
            )
        } for item in repository.list_studio_source_assets(str(recipe["project_id"]))]
        generated_source: dict[str, Any] | None = None
        graphic_invocation: dict[str, Any] | None = None
        if _requests_generated_graphic(instruction):
            graphic = studio_bridge.generate_studio_graphic(
                system_prompt=(
                    skill_snapshot
                    + "\nGenerate exactly one non-human square abstract graphic. No people, faces, text, "
                      "letters, numbers, logos, watermarks, zodiac glyphs, or unsafe claims."
                ),
                input_payload={
                    "instruction": instruction, "target_instance_id": target_instance_id,
                    "brand": {"name": "Natal", "colors": ["#0C0E12", "#181C25", "#43BDD3", "#87D0DD", "#F4F6FA"]},
                },
                output_schema={
                    "type": "object", "additionalProperties": False,
                    "required": ["title", "alt_text"],
                    "properties": {
                        "title": {"type": "string", "minLength": 1, "maxLength": 120},
                        "alt_text": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                },
            )
            image = dict(graphic["image"])
            data = bytes(image.pop("bytes"))
            image.pop("asset_url", None)
            decoded_image = inspect_media(data, "image/png")
            if (
                decoded_image["width"] != int(image.get("width") or 0)
                or decoded_image["height"] != int(image.get("height") or 0)
            ):
                raise ValueError("Studio graphic decoded dimensions do not match its bridge provenance")
            graphic_invocation = dict(graphic["invocation"])
            generated_source = repository.create_studio_source_asset(
                str(recipe["project_id"]), title=str(graphic["response"].get("title") or "AI Studio graphic"),
                data=data, mime_type="image/png", origin="ai_generated",
                provider=str(image["provider"]), external_id=f'bridge:{image["request_id"]}',
                source_uri=None, license_name="PTW generated brand graphic",
                attribution="Generated for Natal under the non-human Studio policy",
                metadata={
                    **image, "bridge_invocation": graphic_invocation,
                    "skill_sha256": skill_sha256, "no_synthetic_people": True,
                    "alt_text": graphic["response"]["alt_text"],
                }, requested_by=requested_by,
            )
        revision = studio_bridge.generate_studio_recipe_revision(
            system_prompt=(
                skill_snapshot
                + "\nReturn one bounded typed recipe revision. Preserve exact offer and CTA text. "
                  "Return only the requested JSON object. Use only IDs already present in the recipe, "
                  "plus exactly generated_source_asset_id when it is non-null. Each patch entry must "
                  "use op=replace, one schema-listed target, and a concise summary."
            ),
            input_payload={
                "recipe": _v2_submission(recipe), "instruction": instruction,
                "target_instance_id": target_instance_id,
                "generated_source_asset_id": None if generated_source is None else generated_source["source_asset_id"],
                "approved_brief": approved_brief["document"],
                "brand_kit": brand_kit,
                "project_sources": project_sources,
                "tool_catalog": tool_catalog(),
            },
            output_schema=studio_recipe_revision_output_schema(recipe),
        )
        response = revision["response"]
        if set(response) != {"patch", "document"} or not isinstance(response["patch"], list) or not isinstance(response["document"], Mapping):
            raise ValueError("Studio wizard returned an invalid typed proposal")
        return [dict(item) for item in response["patch"]], dict(response["document"]), {
            "generated_source_asset_id": None if generated_source is None else generated_source["source_asset_id"],
            "provider_provenance": {
                "skill_sha256": skill_sha256,
                "brief_id": recipe["brief_id"], "brand_kit_id": recipe["brand_kit_id"],
                "brand_kit_sha256": brand_kit["document_sha256"],
                "recipe_revision": dict(revision["invocation"]),
                "graphic_generation": graphic_invocation,
                "generated_source": None if generated_source is None else {
                    key: generated_source[key] for key in (
                        "source_asset_id", "origin", "provider", "external_id", "bytes_sha256", "metadata",
                    )
                },
            },
        }

    def import_exact_pexels(project_id: str, photo_id: str, actor: str) -> dict[str, Any]:
        photo = studio_pexels.get(photo_id)
        data = studio_pexels.download(photo)
        metadata = photo.source_metadata()
        mime_type = next((candidate for candidate in (
            "image/jpeg", "image/png", "image/webp",
        ) if _matches_media(data, candidate)), None)
        if mime_type is None:
            raise ValueError("Pexels source is not a supported decoded image")
        return repository.create_studio_source_asset(
            project_id, title=photo.alt or metadata["attribution"], data=data,
            mime_type=mime_type, origin="pexels", provider="pexels",
            external_id=photo.photo_id, source_uri=photo.page_url,
            license_name=metadata["license"], attribution=metadata["attribution"],
            metadata=metadata, requested_by=actor,
        )

    def bootstrap_sample_sources(project_id: str, actor: str) -> tuple[dict[str, Any], dict[str, str]]:
        logo_path = workspace_asset("logo-natal.png")
        if not logo_path.is_file():
            raise RuntimeError("canonical Natal logo is unavailable")
        brand_kit = repository.ensure_natal_brand_kit(
            project_id, logo_data=logo_path.read_bytes(), requested_by=actor,
        )
        photos = {
            "emotional": import_exact_pexels(project_id, "16664910", actor),
            "practical": import_exact_pexels(project_id, "19232289", actor),
            "authority": import_exact_pexels(project_id, "7640442", actor),
        }
        manifest_path = workspace_asset("studio/manifest.json")
        if not manifest_path.is_file():
            raise RuntimeError("reviewed Studio graphic manifest is unavailable")
        manifest = json.loads(manifest_path.read_text())
        review = manifest.get("review")
        if not isinstance(review, Mapping) or review.get("status") != "approved" or not review.get("reviewed_by") or not review.get("reviewed_at"):
            raise ValueError("Studio graphics require explicit completed review evidence")
        expected = {
            "curiosity": "astrology-hidden-route-v1.png",
            "problem_first": "astrology-generic-vs-personal-v1.png",
        }
        generated: dict[str, dict[str, Any]] = {}
        for angle, filename in expected.items():
            asset_meta = next((item for item in manifest.get("assets") or [] if item.get("file") == filename), None)
            if not isinstance(asset_meta, Mapping):
                raise ValueError("reviewed Studio graphic is missing from its manifest")
            if asset_meta.get("reviewed") is not True:
                raise ValueError("Studio graphic is not approved for the sample set")
            path = workspace_asset(f"studio/{filename}")
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != asset_meta.get("sha256") or digest != asset_meta.get("output_sha256"):
                raise ValueError("reviewed Studio graphic digest does not match its manifest")
            prompt_digest = hashlib.sha256(str(asset_meta.get("prompt") or "").encode()).hexdigest()
            if prompt_digest != asset_meta.get("prompt_sha256"):
                raise ValueError("reviewed Studio graphic prompt digest does not match its manifest")
            generated[angle] = repository.create_studio_source_asset(
                project_id, title="Natal reviewed abstract Studio graphic", data=data,
                mime_type="image/png", origin="ai_generated",
                provider=str(manifest["provider"]), external_id=f'{manifest["request_id"]}:{filename}',
                source_uri=f"natal/assets/studio/{filename}", license_name="PTW generated brand graphic",
                attribution="Generated for Natal with reviewed non-human image policy",
                metadata={
                    "provider": manifest["provider"], "resolved_model": manifest["resolved_model"],
                    "request_id": manifest["request_id"], "prompt": asset_meta["prompt"],
                    "prompt_sha256": prompt_digest, "output_sha256": digest,
                    "no_synthetic_people": True, "generation_policy": dict(manifest["policy"]),
                    "owner_review_required": True, "review": dict(review), "reviewed": True,
                }, requested_by=actor,
            )
        return brand_kit, {
            **{angle: item["source_asset_id"] for angle, item in photos.items()},
            **{angle: item["source_asset_id"] for angle, item in generated.items()},
        }

    def background(method: Any, target_id: str, *, reserved: bool = False) -> None:
        active = require_runner()
        async def execute() -> None:
            try:
                await asyncio.to_thread(method, target_id, operation_reserved=reserved)
            except Exception:
                return
        task = asyncio.create_task(execute())
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> dict[str, Any]:
        active = require_runner()
        try:
            with repository.connection() as connection:
                connection.execute("SELECT 1").fetchone()
            return active.verify_ready()
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"validation dependency unavailable: {type(error).__name__}") from error

    @app.get("/internal/activity", dependencies=[Depends(authorize)])
    def activity() -> dict[str, Any]:
        return repository.activity()

    @app.post("/internal/emergency-stop", dependencies=[Depends(authorize)])
    def emergency_stop(request: Mapping[str, Any]) -> dict[str, bool]:
        nonlocal stopped
        if set(request) != {"active", "actor"} or not isinstance(request.get("active"), bool):
            raise HTTPException(status_code=400, detail="active boolean and actor are required")
        stopped = bool(request["active"])
        return {"emergency_stop": stopped}

    @app.post("/internal/v1/briefs", dependencies=[Depends(authorize)], status_code=202)
    async def create_brief(request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        active = require_runner()
        try:
            value = validate_create_input(request)
            brief, created = repository.create_brief(**value, requested_by=x_ptw_actor[:200])
            if brief["status"] == "queued":
                if repository.acquire_operation("product_brief", brief["brief_id"]):
                    background(active.generate_brief, brief["brief_id"], reserved=True)
            return {
                "project": repository.get_project(brief["project_id"]),
                "brief": brief,
                "created": created,
            }
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/projects", dependencies=[Depends(authorize)])
    def projects(limit: int = Query(default=100, ge=1, le=100)) -> dict[str, Any]:
        return {"items": repository.list_projects(limit), "next_cursor": None}

    @app.post("/internal/v1/projects/{project_id}/rename", dependencies=[Depends(authorize)])
    def rename_project(
        project_id: str,
        request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        if set(request) != {"name"} or not isinstance(request.get("name"), str):
            raise HTTPException(status_code=400, detail="Project rename requires one name")
        try:
            return repository.rename_project(
                str(UUID(project_id)), name=str(request["name"]), requested_by=x_ptw_actor[:200]
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Validation Project not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/internal/v1/briefs", dependencies=[Depends(authorize)])
    def briefs(
        project_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            normalized_project_id = None if project_id is None else str(UUID(project_id))
            return {
                "items": repository.list_briefs(limit, project_id=normalized_project_id),
                "next_cursor": None,
            }
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Validation Project ID") from error

    @app.get("/internal/v1/briefs/{brief_id}", dependencies=[Depends(authorize)])
    def brief(brief_id: str) -> dict[str, Any]:
        try:
            return repository.get_brief(str(UUID(brief_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error

    @app.post("/internal/v1/briefs/{brief_id}/correct", dependencies=[Depends(authorize)], status_code=202)
    async def revise_brief(brief_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        active = require_runner()
        try:
            value = validate_revision_input(request)
            replacement, created = repository.create_revision(
                base_brief_id=str(UUID(brief_id)), requested_by=x_ptw_actor[:200], **value
            )
            if replacement["status"] == "queued":
                if repository.acquire_operation("product_brief", replacement["brief_id"]):
                    background(active.generate_brief, replacement["brief_id"], reserved=True)
            return {"brief": replacement, "created": created}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="base Product Brief not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/briefs/{brief_id}/retry", dependencies=[Depends(authorize)], status_code=202)
    async def retry_brief(brief_id: str) -> dict[str, Any]:
        active = require_runner()
        try:
            brief_id = str(UUID(brief_id))
            acquired = repository.acquire_operation("product_brief", brief_id)
            if not acquired:
                return repository.get_brief(brief_id)
            try:
                value = repository.queue_retry(brief_id, stage="product_brief")
            except Exception:
                repository.release_operation(brief_id)
                raise
            background(active.generate_brief, brief_id, reserved=True)
            return value
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/briefs/{brief_id}/approve", dependencies=[Depends(authorize)], status_code=202)
    async def approve_brief(brief_id: str, x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        active = require_runner()
        try:
            batch, should_start = repository.approve_and_queue_batch(str(UUID(brief_id)), x_ptw_actor[:200])
            if should_start:
                background(active.generate_batch, batch["batch_id"], reserved=True)
            return {
                "brief": repository.get_brief(brief_id),
                "batch": batch,
                "generation_started": should_start,
            }
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Product Brief not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/ad-batches", dependencies=[Depends(authorize)])
    def batches(
        brief_id: str | None = None,
        project_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            normalized_brief_id = None if brief_id is None else str(UUID(brief_id))
            normalized_project_id = None if project_id is None else str(UUID(project_id))
            return {
                "items": repository.list_batches(
                    limit, brief_id=normalized_brief_id, project_id=normalized_project_id
                ),
                "next_cursor": None,
            }
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Brief or Project ID") from error

    @app.get("/internal/v1/ad-batches/{batch_id}", dependencies=[Depends(authorize)])
    def batch(batch_id: str) -> dict[str, Any]:
        try:
            return repository.get_batch(str(UUID(batch_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="creative batch not found") from error

    @app.post("/internal/v1/ad-batches/{batch_id}/retry", dependencies=[Depends(authorize)], status_code=202)
    async def retry_batch(batch_id: str) -> dict[str, Any]:
        active = require_runner()
        try:
            batch_id = str(UUID(batch_id))
            acquired = repository.acquire_operation("ad_creative_batch", batch_id)
            if not acquired:
                return repository.get_batch(batch_id)
            try:
                value = repository.queue_retry(batch_id, stage="ad_creative_batch")
            except Exception:
                repository.release_operation(batch_id)
                raise
            background(active.generate_batch, batch_id, reserved=True)
            return value
        except KeyError as error:
            raise HTTPException(status_code=404, detail="creative batch not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/ad-batches/{batch_id}/rerun", dependencies=[Depends(authorize)], status_code=202)
    async def rerun_batch(
        batch_id: str,
        request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        active = require_runner()
        if set(request) != {"request_id"}:
            raise HTTPException(status_code=400, detail="request_id is required")
        try:
            _, skill_sha256 = active.ad_creative_skill_snapshot()
            value, should_start = repository.create_lesson_rerun(
                str(UUID(batch_id)),
                request_id=str(UUID(str(request["request_id"]))),
                requested_by=x_ptw_actor[:200],
                skill_sha256=skill_sha256,
            )
            if should_start:
                background(active.generate_batch, value["batch_id"], reserved=True)
            return {"batch": value, "generation_started": should_start}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="creative batch not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/ad-creatives/{creative_id}/image", dependencies=[Depends(authorize)])
    def creative_image(creative_id: str, if_none_match: str = Header(default="")) -> Response:
        try:
            value = repository.image(str(UUID(creative_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="creative image not found") from error
        etag = f'"{value["sha256"]}"'
        headers = {"ETag": etag, "Cache-Control": "private, max-age=31536000, immutable"}
        if if_none_match == etag:
            return Response(status_code=304, headers=headers)
        return Response(value["bytes"], media_type=value["mime_type"], headers=headers)

    @app.get("/internal/v1/ad-studio/tools", dependencies=[Depends(authorize)])
    def studio_tools() -> dict[str, Any]:
        return tool_catalog()

    @app.get("/internal/v1/ad-studio/brand-kits", dependencies=[Depends(authorize)])
    def studio_brand_kits(project_id: str) -> dict[str, Any]:
        try:
            return {"items": repository.list_studio_brand_kits(str(UUID(project_id)))}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Validation Project ID") from error

    @app.post("/internal/v1/ad-studio/brand-kits", dependencies=[Depends(authorize)], status_code=201)
    def create_studio_brand_kit(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"project_id", "parent_brand_kit_id", "document"} or not isinstance(request.get("document"), Mapping):
            raise HTTPException(status_code=400, detail="Studio brand-kit request fields do not match")
        try:
            return repository.create_studio_brand_kit(
                str(UUID(str(request["project_id"]))), document=request["document"],
                parent_brand_kit_id=None if request["parent_brand_kit_id"] is None else str(UUID(str(request["parent_brand_kit_id"]))),
                requested_by=x_ptw_actor[:200],
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Validation Project not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/internal/v1/ad-studio/templates", dependencies=[Depends(authorize)])
    def studio_templates(project_id: str) -> dict[str, Any]:
        try:
            return {"items": repository.list_studio_templates(str(UUID(project_id)))}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Validation Project ID") from error

    @app.post("/internal/v1/ad-studio/templates", dependencies=[Depends(authorize)], status_code=201)
    def create_studio_template(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"project_id", "name", "document"} or not isinstance(request.get("document"), Mapping):
            raise HTTPException(status_code=400, detail="Studio template request fields do not match")
        try:
            return repository.create_studio_template(
                str(UUID(str(request["project_id"]))), name=str(request["name"]),
                document=request["document"], requested_by=x_ptw_actor[:200],
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Validation Project not found") from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/internal/v1/ad-studio/templates/{template_id}/apply", dependencies=[Depends(authorize)])
    def apply_studio_template(
        template_id: str, request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        if set(request) != {"request_id", "brief_id", "creative_id", "brand_kit_id"}:
            raise HTTPException(status_code=400, detail="Studio template apply fields do not match")
        try:
            normalized_template_id = str(UUID(template_id))
            creative_id = None if request["creative_id"] is None else str(UUID(str(request["creative_id"])))
            source_asset_id = repository.studio_sample_template_media(normalized_template_id)
            if creative_id is not None:
                creative = repository.get_creative(creative_id)
                if source_asset_id is None:
                    photo_id = str(creative["image"]["source_photo_id"])
                    if photo_id in {"34183731", "32446190"}:
                        raise ValueError("this mismatched source photo is excluded from Studio templates")
                    imported = import_exact_pexels(
                        creative["project_id"], photo_id, x_ptw_actor[:200],
                    )
                    source_asset_id = imported["source_asset_id"]
            return repository.apply_studio_template(
                normalized_template_id, brief_id=str(UUID(str(request["brief_id"]))),
                creative_id=creative_id, brand_kit_id=str(UUID(str(request["brand_kit_id"]))),
                photo_source_asset_id=source_asset_id,
                request_id=str(UUID(str(request["request_id"]))), requested_by=x_ptw_actor[:200],
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Studio template resource not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.get("/internal/v1/ad-studio/sources", dependencies=[Depends(authorize)])
    def studio_sources(project_id: str) -> dict[str, Any]:
        try:
            return {"items": repository.list_studio_source_assets(str(UUID(project_id)))}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Validation Project ID") from error

    @app.get("/internal/v1/ad-studio/sources/{source_asset_id}/asset", dependencies=[Depends(authorize)])
    def studio_source_asset(source_asset_id: str, if_none_match: str = Header(default="")) -> Response:
        try:
            asset = repository.studio_source_asset(str(UUID(source_asset_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Studio source asset not found") from error
        etag = f'"{asset["sha256"]}"'
        headers = {"ETag": etag, "Cache-Control": "private, max-age=31536000, immutable"}
        if if_none_match == etag:
            return Response(status_code=304, headers=headers)
        return Response(asset["bytes"], media_type=asset["mime_type"], headers=headers)

    @app.post("/internal/v1/ad-studio/sources/upload", dependencies=[Depends(authorize)], status_code=201)
    def upload_studio_source(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"project_id", "title", "mime_type", "base64"}:
            raise HTTPException(status_code=400, detail="Studio upload request fields do not match")
        try:
            encoded = str(request["base64"])
            if len(encoded) > ((MAX_VIDEO_BYTES + 2) // 3) * 4:
                raise ValueError("Studio upload exceeds the bounded size")
            data = base64.b64decode(encoded, validate=True)
            return repository.create_studio_source_asset(
                str(UUID(str(request["project_id"]))), title=str(request["title"]), data=data,
                mime_type=str(request["mime_type"]), origin="owner_upload", provider="owner",
                external_id=None, source_uri=None, license_name="Owner supplied",
                attribution="Owner-supplied media", metadata={}, requested_by=x_ptw_actor[:200],
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Validation Project not found") from error
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/internal/v1/ad-studio/pexels/search", dependencies=[Depends(authorize)])
    def search_studio_pexels(query: str = Query(min_length=1, max_length=160)) -> dict[str, Any]:
        try:
            return {"items": [{
                "photo_id": item.photo_id, "width": item.width, "height": item.height,
                "image_url": item.image_url, "source_url": item.page_url,
                "photographer": item.photographer, "photographer_url": item.photographer_url,
                "alt": item.alt,
            } for item in studio_pexels.search(query)]}
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/internal/v1/ad-studio/sources/pexels", dependencies=[Depends(authorize)], status_code=201)
    def import_studio_pexels(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"project_id", "query", "photo_id"}:
            raise HTTPException(status_code=400, detail="Pexels import request fields do not match")
        try:
            matches = [item for item in studio_pexels.search(str(request["query"])) if item.photo_id == str(request["photo_id"])]
            if not matches:
                raise ValueError("selected Pexels photo is no longer available for this query")
            photo = matches[0]; data = studio_pexels.download(photo); metadata = photo.source_metadata()
            mime_type = next((candidate for candidate in ("image/jpeg", "image/png", "image/webp") if _matches_media(data, candidate)), None)
            if mime_type is None:
                raise ValueError("Pexels source is not a supported decoded image")
            return repository.create_studio_source_asset(
                str(UUID(str(request["project_id"]))), title=photo.alt or metadata["attribution"],
                data=data, mime_type=mime_type, origin="pexels", provider="pexels",
                external_id=photo.photo_id, source_uri=photo.page_url,
                license_name=metadata["license"], attribution=metadata["attribution"],
                metadata=metadata, requested_by=x_ptw_actor[:200],
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Validation Project not found") from error
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/internal/v1/ad-studio/sample-sets", dependencies=[Depends(authorize)])
    def studio_sample_sets(project_id: str) -> dict[str, Any]:
        try:
            return {"items": repository.list_studio_sample_sets(str(UUID(project_id)))}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Validation Project ID") from error

    @app.post("/internal/v1/ad-studio/sample-sets", dependencies=[Depends(authorize)], status_code=201)
    def create_studio_sample_set(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"batch_id"}:
            raise HTTPException(status_code=400, detail="Studio sample set requires one completed batch_id")
        actor = x_ptw_actor[:200]
        try:
            batch_id = str(UUID(str(request["batch_id"])))
            existing = repository.get_studio_sample_set_for_batch(batch_id)
            if existing is not None:
                return existing
            if not repository.acquire_operation("ad_studio_sample_set", batch_id):
                raise ValueError("another heavy operation is already active")
            try:
                batch = repository.get_batch(batch_id)
                brand_kit, media_by_angle = bootstrap_sample_sources(batch["project_id"], actor)
                return repository.create_studio_sample_set(
                    batch_id, brand_kit_id=brand_kit["brand_kit_id"],
                    media_by_angle=media_by_angle, renderer=studio_renderer, requested_by=actor,
                )
            finally:
                repository.release_operation(batch_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="completed creative batch not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.get("/internal/v1/ad-studio/sample-sets/{sample_set_id}", dependencies=[Depends(authorize)])
    def studio_sample_set(sample_set_id: str) -> dict[str, Any]:
        try:
            return repository.get_studio_sample_set(str(UUID(sample_set_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Studio sample set not found") from error

    @app.get("/internal/v1/ad-studio/sample-sets/{sample_set_id}/download", dependencies=[Depends(authorize)])
    def studio_sample_set_download(
        sample_set_id: str, if_none_match: str = Header(default="")
    ) -> Response:
        try:
            package = repository.studio_sample_set_download(str(UUID(sample_set_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Studio sample set not found") from error
        etag = f'"{package["sha256"]}"'
        headers = {
            "ETag": etag, "Cache-Control": "private, max-age=31536000, immutable",
            "Content-Disposition": f'attachment; filename="ptw-studio-{sample_set_id}.zip"',
        }
        if if_none_match == etag:
            return Response(status_code=304, headers=headers)
        return Response(package["bytes"], media_type=package["mime_type"], headers=headers)

    @app.get("/internal/v1/ad-studio/recipes", dependencies=[Depends(authorize)])
    def studio_recipes(project_id: str) -> dict[str, Any]:
        try:
            return {"items": repository.list_studio_recipes(str(UUID(project_id)))}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Validation Project ID") from error

    @app.get("/internal/v1/ad-studio/recipes/{recipe_id}", dependencies=[Depends(authorize)])
    def studio_recipe(recipe_id: str) -> dict[str, Any]:
        try:
            return repository.get_studio_recipe(str(UUID(recipe_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Studio recipe not found") from error

    @app.post("/internal/v1/ad-studio/recipes", dependencies=[Depends(authorize)], status_code=201)
    def create_studio_recipe(
        request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"project_id", "brief_id", "brand_kit_id", "document"} or not isinstance(request.get("document"), Mapping):
            raise HTTPException(status_code=400, detail="Studio recipe request fields do not match")
        try:
            return repository.create_studio_recipe(
                str(UUID(str(request["project_id"]))), brief_id=str(UUID(str(request["brief_id"]))),
                brand_kit_id=str(UUID(str(request["brand_kit_id"]))), document=request["document"],
                requested_by=x_ptw_actor[:200],
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Studio Project resource not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/ad-studio/recipes/{recipe_id}/render", dependencies=[Depends(authorize)], status_code=201)
    def render_studio_recipe(recipe_id: str) -> dict[str, Any]:
        try:
            recipe_id = str(UUID(recipe_id))
            if not repository.acquire_operation("ad_studio_render", recipe_id):
                raise ValueError("another heavy operation is already active")
            try:
                return repository.render_studio_recipe(recipe_id, studio_renderer)
            finally:
                repository.release_operation(recipe_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Studio recipe not found") from error
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/ad-studio/recipes/{recipe_id}/renders", dependencies=[Depends(authorize)])
    def studio_recipe_renders(recipe_id: str) -> dict[str, Any]:
        try:
            return {"items": repository.list_studio_renders(str(UUID(recipe_id)))}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Studio recipe ID") from error

    @app.post(
        "/internal/v1/ad-studio/recipes/{recipe_id}/wizard-proposals",
        dependencies=[Depends(authorize)], status_code=201,
    )
    def create_studio_wizard_proposal(
        recipe_id: str, request: Mapping[str, Any],
        x_ptw_actor: str = Header(default="owner-web"),
    ) -> dict[str, Any]:
        if set(request) != {"instruction", "target_instance_id"}:
            raise HTTPException(status_code=400, detail="wizard proposal fields do not match")
        try:
            normalized_recipe_id = str(UUID(recipe_id))
            if not repository.acquire_operation("ad_studio_wizard", normalized_recipe_id):
                raise ValueError("another heavy operation is already active")
            try:
                return repository.create_studio_wizard_proposal(
                    normalized_recipe_id, instruction=str(request["instruction"]),
                    target_instance_id=(None if request["target_instance_id"] is None else str(UUID(str(request["target_instance_id"])))),
                    proposal_builder=wizard_proposal_builder, renderer=studio_renderer,
                    requested_by=x_ptw_actor[:200],
                )
            finally:
                repository.release_operation(normalized_recipe_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Studio recipe not found") from error
        except (ValueError, RuntimeError, TimeoutError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get(
        "/internal/v1/ad-studio/recipes/{recipe_id}/wizard-proposals",
        dependencies=[Depends(authorize)],
    )
    def studio_wizard_proposals(recipe_id: str) -> dict[str, Any]:
        try:
            return {"items": repository.list_studio_wizard_proposals(str(UUID(recipe_id)))}
        except ValueError as error:
            raise HTTPException(status_code=400, detail="invalid Studio recipe ID") from error

    @app.get(
        "/internal/v1/ad-studio/wizard-proposals/{proposal_id}/preview",
        dependencies=[Depends(authorize)],
    )
    def studio_wizard_preview(proposal_id: str, if_none_match: str = Header(default="")) -> Response:
        try:
            preview = repository.studio_wizard_preview(str(UUID(proposal_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Studio wizard proposal not found") from error
        etag = f'"{preview["sha256"]}"'
        headers = {"ETag": etag, "Cache-Control": "private, max-age=31536000, immutable"}
        if if_none_match == etag:
            return Response(status_code=304, headers=headers)
        return Response(preview["bytes"], media_type=preview["mime_type"], headers=headers)

    @app.post(
        "/internal/v1/ad-studio/wizard-proposals/{proposal_id}/apply",
        dependencies=[Depends(authorize)],
    )
    def apply_studio_wizard_proposal(
        proposal_id: str, x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        try:
            normalized_proposal_id = str(UUID(proposal_id))
            if not repository.acquire_operation("ad_studio_wizard", normalized_proposal_id):
                raise ValueError("another heavy operation is already active")
            try:
                return repository.apply_studio_wizard_proposal(
                    normalized_proposal_id, renderer=studio_renderer, requested_by=x_ptw_actor[:200],
                )
            finally:
                repository.release_operation(normalized_proposal_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Studio wizard proposal not found") from error
        except (ValueError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/ad-studio/renders/{render_id}/asset", dependencies=[Depends(authorize)])
    def studio_render_asset(render_id: str, if_none_match: str = Header(default="")) -> Response:
        try:
            artifact = repository.studio_render_asset(str(UUID(render_id)))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Studio render not found") from error
        etag = f'"{artifact["sha256"]}"'
        headers = {"ETag": etag, "Cache-Control": "private, max-age=31536000, immutable"}
        if if_none_match == etag:
            return Response(status_code=304, headers=headers)
        return Response(artifact["bytes"], media_type=artifact["mime_type"], headers=headers)

    @app.get("/internal/v1/ad-studio/renders/{render_id}/manifest", dependencies=[Depends(authorize)])
    def studio_render_manifest(render_id: str) -> dict[str, Any]:
        try:
            return repository.get_studio_render(str(UUID(render_id)))["manifest"]
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Studio render not found") from error

    @app.post("/internal/v1/ad-studio/renders/{render_id}/publish", dependencies=[Depends(authorize)])
    def publish_studio_render(
        render_id: str, x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        try:
            return repository.publish_studio_render(str(UUID(render_id)), requested_by=x_ptw_actor[:200])
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Studio render not found") from error

    @app.post("/internal/v1/ad-studio/renders/{render_id}/feedback", dependencies=[Depends(authorize)])
    def studio_render_feedback(
        render_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")
    ) -> dict[str, Any]:
        if set(request) != {"comment"}:
            raise HTTPException(status_code=400, detail="Studio feedback requires one comment")
        try:
            return repository.record_studio_feedback(
                str(UUID(render_id)), comment=str(request["comment"]), requested_by=x_ptw_actor[:200]
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Studio render not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/ad-creatives/{creative_id}/feedback", dependencies=[Depends(authorize)])
    def creative_feedback(creative_id: str, request: Mapping[str, Any], x_ptw_actor: str = Header(default="owner-web")) -> dict[str, Any]:
        if set(request) != {"comment"}:
            raise HTTPException(status_code=400, detail="feedback requires one comment")
        try:
            return repository.record_creative_feedback(
                str(UUID(creative_id)), comment=str(request["comment"]), requested_by=x_ptw_actor[:200]
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="creative not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/v1/skill-proposals/{domain}", dependencies=[Depends(authorize)])
    def proposals(domain: str, target_id: str | None = None) -> dict[str, Any]:
        try:
            return {"items": repository.proposals(domain, target_id=target_id)}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/{domain}/{proposal_id}/update", dependencies=[Depends(authorize)])
    def update_proposal(domain: str, proposal_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"lesson"}:
            raise HTTPException(status_code=400, detail="lesson is required")
        try:
            return repository.update_proposal(domain, str(UUID(proposal_id)), lesson=str(request["lesson"]))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/{domain}/{proposal_id}/dismiss", dependencies=[Depends(authorize)])
    def dismiss_proposal(domain: str, proposal_id: str) -> dict[str, Any]:
        try:
            return repository.update_proposal(domain, str(UUID(proposal_id)), status="rejected")
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/{domain}/plan", dependencies=[Depends(authorize)])
    def plan_grouped_proposals(domain: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"proposal_ids", "command_session_id"}:
            raise HTTPException(status_code=400, detail="proposal_ids and command_session_id are required")
        raw_ids = request.get("proposal_ids")
        if not isinstance(raw_ids, list):
            raise HTTPException(status_code=400, detail="proposal_ids must be a list")
        try:
            proposal_ids = [str(UUID(str(value))) for value in raw_ids]
            return repository.plan_proposals(
                domain, proposal_ids,
                command_session_id=str(UUID(str(request["command_session_id"]))),
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/{domain}/{proposal_id}/plan", dependencies=[Depends(authorize)])
    def plan_proposal(domain: str, proposal_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"lesson", "command_session_id"}:
            raise HTTPException(status_code=400, detail="lesson and command_session_id are required")
        try:
            return repository.update_proposal(
                domain, str(UUID(proposal_id)), lesson=str(request["lesson"]), status="planning",
                command_session_id=str(UUID(str(request["command_session_id"]))),
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/by-command/{command_session_id}/finish", dependencies=[Depends(authorize)])
    def finish_proposal(command_session_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if set(request) != {"status"} or request.get("status") not in {"promoted", "failed"}:
            raise HTTPException(status_code=400, detail="status must be promoted or failed")
        try:
            return repository.finish_proposal(
                str(UUID(command_session_id)), status=str(request["status"])
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/v1/skill-proposals/by-command/{command_session_id}/restore", dependencies=[Depends(authorize)])
    def restore_proposals(command_session_id: str) -> dict[str, Any]:
        try:
            return repository.restore_proposals(str(UUID(command_session_id)))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


def create_app_from_env() -> FastAPI:
    return create_app(Settings.from_environment())
