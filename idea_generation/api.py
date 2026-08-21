"""Internal HTTP API for the Idea Laval engine."""

from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from typing import Any, Mapping

from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse

from commander.telegram_api import TelegramBotClient

from .config import Settings
from .brand_pipeline import BrandPipeline
from .brand_providers import (
    CodexBridgeBrandProvider,
    CommanderBrandBridge,
    DeterministicBrandProvider,
    FixtureBrandPageProvider,
    OpenAIBrandProvider,
    PublicBrandPageProvider,
    UnavailableBrandProvider,
)
from .brand_repository import BrandRepository
from .brand_service import BrandRunner, BrandService
from .manage import ROOT
from .laval_pipeline import LavalPipeline
from .laval_notifications import LavalTelegramNotifier
from .laval_providers import (
    FixtureYouTubeObservationProvider,
    OfficialYouTubeObservationProvider,
    UnavailableYouTubeObservationProvider,
    providers_from_settings,
)
from .laval_repository import LavalRepository
from .laval_schemas import SCHEMAS
from .laval_service import LavalRunner, LavalService
from .operation_guard import HeavyOperationGuard, OperationConflict
from .provider import BridgeProvider, MockLLMProvider, OpenAIProvider
from .store import PostgresStore


def _provider(settings: Settings):
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.openai_api_key, settings.llm_model)
    if settings.llm_provider == "bridge":
        return BridgeProvider(settings.llm_bridge_url, settings.telegram_token, settings.llm_model)
    raise RuntimeError("LLM_PROVIDER must be mock, openai, or bridge")


def _llm_contract_readiness(llm: Any) -> dict[str, Any]:
    required_modes = set(SCHEMAS)
    if not isinstance(llm, BridgeProvider):
        return {
            "llm_live_ready": True,
            "llm_required_modes": sorted(required_modes),
            "llm_missing_modes": [],
            "llm_unexpected_modes": [],
            "llm_max_request_bytes": None,
            "llm_contract_error": None,
        }
    try:
        capabilities = llm.capabilities()
        actual_modes = set(capabilities["laval_modes"])
    except Exception as error:
        return {
            "llm_live_ready": False,
            "llm_required_modes": sorted(required_modes),
            "llm_missing_modes": sorted(required_modes),
            "llm_unexpected_modes": [],
            "llm_max_request_bytes": None,
            "llm_contract_error": type(error).__name__,
        }
    missing = sorted(required_modes - actual_modes)
    unexpected = sorted(actual_modes - required_modes)
    return {
        "llm_live_ready": not missing and not unexpected,
        "llm_required_modes": sorted(required_modes),
        "llm_missing_modes": missing,
        "llm_unexpected_modes": unexpected,
        "llm_max_request_bytes": capabilities["max_request_bytes"],
        "llm_contract_error": None,
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    store = PostgresStore(settings.database_url)
    store.migrate(ROOT / "db/idea_generation")
    store.seed_laval_mission()

    llm = _provider(settings)
    laval_repository = LavalRepository(store)
    provider_bundle = providers_from_settings(settings, llm)
    laval_pipeline = LavalPipeline(laval_repository, provider_bundle)
    laval_notifier = (
        LavalTelegramNotifier(
            laval_repository,
            tuple(settings.allowed_chat_ids),
            TelegramBotClient(settings.telegram_token, timeout_seconds=10),
        )
        if settings.laval_telegram_notifications_enabled
        else None
    )
    operation_guard = HeavyOperationGuard()
    laval_runner = LavalRunner(laval_pipeline, laval_notifier, operation_guard)
    readiness = {
        **_llm_contract_readiness(llm),
        "llm_provider": settings.llm_provider,
        "search_provider": settings.search_provider,
        "trend_provider": settings.trend_provider,
        "search_live_ready": settings.search_provider == "dataforseo" and settings.dataforseo_verified and bool(settings.dataforseo_login and settings.dataforseo_password),
        "trends_live_ready": settings.trend_provider == "google_trends" and bool(settings.trend_bridge_url),
        "youtube_provider": provider_bundle.youtube.name,
        "youtube_live_ready": bool(settings.youtube_api_key and settings.youtube_verified),
        "demo_available": settings.search_provider == "fixture" and settings.trend_provider in {"fixture", "manual"},
        "max_spend_usd": settings.max_spend_usd,
        "reserved_spend_usd": settings.reserved_spend_usd,
    }
    laval = LavalService(laval_repository, laval_runner, readiness=readiness, notifier=laval_notifier)

    brand_contract_error = None
    if settings.brand_provider == "fixture":
        brand_provider = DeterministicBrandProvider()
        brand_web = FixtureBrandPageProvider()
        brand_youtube = FixtureYouTubeObservationProvider()
        brand_ready = True
    elif settings.brand_provider == "bridge":
        brand_provider = CodexBridgeBrandProvider(
            settings.llm_bridge_url,
            settings.telegram_token,
            settings.brand_text_model,
            settings.brand_image_model,
            settings.brand_asset_directory.parent,
        )
        brand_web = PublicBrandPageProvider()
        brand_youtube = (
            OfficialYouTubeObservationProvider(settings.youtube_api_key)
            if settings.youtube_api_key and settings.youtube_verified
            else UnavailableYouTubeObservationProvider()
        )
        try:
            brand_provider.capabilities()
            brand_ready = True
        except Exception as error:
            brand_ready = False
            brand_contract_error = type(error).__name__
    elif settings.brand_provider == "openai":
        brand_provider = (
            OpenAIBrandProvider(
                settings.openai_api_key,
                settings.brand_text_model,
                settings.brand_image_model,
            )
            if settings.openai_api_key
            else UnavailableBrandProvider(
                settings.brand_text_model, settings.brand_image_model
            )
        )
        brand_web = PublicBrandPageProvider()
        brand_youtube = (
            OfficialYouTubeObservationProvider(settings.youtube_api_key)
            if settings.youtube_api_key and settings.youtube_verified
            else UnavailableYouTubeObservationProvider()
        )
        brand_ready = bool(settings.openai_api_key)
    else:
        raise RuntimeError("BRAND_PROVIDER must be fixture, bridge, or openai")
    brand_readiness = {
        "ready": brand_ready,
        "provider": brand_provider.name,
        "configured_provider": settings.brand_provider,
        "text_model": brand_provider.text_model,
        "image_model": brand_provider.image_model,
        "text_ready": brand_ready,
        "image_ready": brand_ready,
        "missing": (
            []
            if brand_ready
            else ["openai_api_key"]
            if settings.brand_provider == "openai"
            else ["codex_brand_bridge_contract"]
        ),
        "contract_error": brand_contract_error,
        "credential_source": (
            "existing_codex_chatgpt_auth"
            if settings.brand_provider == "bridge"
            else "openai_api_key"
            if settings.brand_provider == "openai"
            else "fixture"
        ),
        "web_provider": brand_web.name,
        "youtube_provider": brand_youtube.name,
        "youtube_ready": brand_youtube.name != "unavailable",
        "paid_seo_enabled": False,
        "caption_scraping_enabled": False,
        "pipeline_version": "branding_v1",
    }
    brand_repository = BrandRepository(store)
    brand_pipeline = BrandPipeline(
        brand_repository,
        brand_provider,
        brand_web,
        brand_youtube,
        CommanderBrandBridge(settings.brand_commander_bridge_url, settings.telegram_token),
        settings.brand_asset_directory,
    )
    brand_runner = BrandRunner(brand_pipeline, operation_guard)
    branding = BrandService(
        brand_repository,
        brand_runner,
        brand_pipeline,
        readiness=brand_readiness,
    )
    laval_runner.on_idle = brand_runner.resume_incomplete
    brand_runner.on_idle = laval_runner.resume_incomplete

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        laval_runner.resume_incomplete()
        brand_runner.resume_incomplete()
        try:
            yield
        finally:
            store.close()

    app = FastAPI(title="PTW Idea and Branding", version="4.0.0", docs_url=None, redoc_url=None, lifespan=lifespan)

    @app.get("/healthz")
    def health() -> dict[str, Any]:
        current = store.mission()
        return {
            "status": "ok",
            "mission": current["status"],
            "laval_active_runs": store.fetchone(
                "SELECT COUNT(*) n FROM laval_runs WHERE status IN ('pending','running')"
            )["n"],
            "laval_total_runs": store.fetchone("SELECT COUNT(*) n FROM laval_runs")["n"],
            "branding_active_runs": store.fetchone(
                "SELECT COUNT(*) n FROM brand_runs WHERE status IN ('pending','running')"
            )["n"],
            "branding_total_runs": store.fetchone("SELECT COUNT(*) n FROM brand_runs")["n"],
        }

    def require_owner_gateway(token: str) -> None:
        if not settings.owner_gateway_token or not hmac.compare_digest(
            token, settings.owner_gateway_token
        ):
            raise HTTPException(status_code=403, detail="invalid owner gateway token")

    @app.get("/internal/web/laval/runs")
    def list_laval_runs(
        limit: int = Query(default=30, ge=1, le=100),
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        return laval.list(limit)

    @app.get("/internal/web/laval/providers")
    def laval_providers(
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        missing = []
        if not readiness["search_live_ready"]:
            missing.append("dataforseo_credentials")
        if not readiness["youtube_live_ready"] and settings.search_provider != "fixture":
            missing.append("youtube_api_key")
        if not readiness["llm_live_ready"] and settings.search_provider != "fixture":
            missing.append("llm_bridge_contract")
        return {
            **readiness,
            "demo_available": readiness["demo_available"],
            "default_evidence_mode": "demo_fixture" if settings.search_provider == "fixture" else "live_market_signals",
            "missing": missing,
            "optional_sources": {
                "google_trends": {
                    "ready": readiness["trends_live_ready"],
                    "required": False,
                }
            },
            "required_sources": {
                "youtube": {"ready": readiness["youtube_live_ready"]},
                "llm_bridge": {
                    "ready": readiness["llm_live_ready"],
                    "missing_modes": readiness["llm_missing_modes"],
                    "unexpected_modes": readiness["llm_unexpected_modes"],
                },
            },
        }

    @app.get("/internal/web/laval/activity")
    def laval_activity(
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        return operation_guard.snapshot()

    @app.get("/internal/web/activity")
    def heavy_activity(
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        return operation_guard.snapshot()

    @app.get("/internal/web/branding/providers")
    def branding_providers(
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        return brand_readiness

    @app.get("/internal/web/branding/cases")
    def branding_cases(
        limit: int = Query(default=30, ge=1, le=100),
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        return brand_repository.candidates(limit)

    @app.get("/internal/web/branding/runs")
    def branding_runs(
        limit: int = Query(default=30, ge=1, le=100),
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        return brand_repository.list(limit)

    @app.post("/internal/web/branding/runs")
    def create_branding_run(
        request: Mapping[str, Any],
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return branding.create(
                request, actor=str(request.get("actor") or "owner-gateway")
            )
        except OperationConflict as error:
            raise HTTPException(status_code=409, detail={"active_operation": error.active}) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/web/branding/runs/{run_id}")
    def branding_status(
        run_id: str, x_ptw_owner_gateway_token: str = Header(default="")
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            result = brand_repository.status(run_id)
            result["runner_active"] = brand_runner.active(run_id)
            return result
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/internal/web/branding/runs/{run_id}/stages")
    def branding_stages(
        run_id: str, x_ptw_owner_gateway_token: str = Header(default="")
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return {"items": brand_repository.stages(run_id)}
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/internal/web/branding/runs/{run_id}/show")
    def branding_show(
        run_id: str,
        stage: str,
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return brand_repository.stage(run_id, stage)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/internal/web/branding/runs/{run_id}/directions")
    def branding_directions(
        run_id: str, x_ptw_owner_gateway_token: str = Header(default="")
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return {"items": brand_repository.directions(run_id)}
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/internal/web/branding/runs/{run_id}/directions/{direction_id}/regenerate"
    )
    def regenerate_branding_logo(
        run_id: str,
        direction_id: str,
        request: Mapping[str, Any],
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return branding.regenerate_logo(
                run_id, direction_id, str(request.get("feedback_id") or ""),
                actor=str(request.get("actor") or "owner-gateway"),
            )
        except OperationConflict as error:
            raise HTTPException(
                status_code=409, detail={"active_operation": error.active}
            ) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/web/branding/runs/{run_id}/{action}")
    def control_branding_run(
        run_id: str,
        action: str,
        request: Mapping[str, Any],
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        actor = str(request.get("actor") or "owner-gateway")
        try:
            if action == "pause":
                return branding.pause(run_id, actor=actor)
            if action == "resume":
                return branding.resume(run_id, actor=actor)
            if action == "rerun":
                return branding.rerun(run_id, str(request.get("stage") or ""), actor=actor)
            if action == "approve":
                return branding.approve(
                    run_id, str(request.get("direction_id") or ""), actor=actor
                )
            raise HTTPException(status_code=404, detail="unknown Branding action")
        except OperationConflict as error:
            raise HTTPException(status_code=409, detail={"active_operation": error.active}) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/web/branding/kits/{kit_id}")
    def branding_kit(
        kit_id: str, x_ptw_owner_gateway_token: str = Header(default="")
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return brand_repository.kit(kit_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/internal/web/branding/assets/{digest}")
    def branding_asset(
        digest: str, x_ptw_owner_gateway_token: str = Header(default="")
    ) -> FileResponse:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            path, mime = brand_repository.artifact_path(
                digest, settings.brand_asset_directory
            )
        except (KeyError, PermissionError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Branding artifact file is missing")
        return FileResponse(
            path,
            media_type=mime,
            filename=path.name,
            headers={"Cache-Control": "private, no-store"},
        )

    @app.post("/internal/web/laval/runs")
    def create_laval_run(
        request: Mapping[str, Any], x_ptw_owner_gateway_token: str = Header(default="")
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return laval.create(
                str(request.get("text") or ""),
                request.get("config") if isinstance(request.get("config"), Mapping) else {},
                actor=str(request.get("actor") or "owner-gateway"),
                requested_mode=str(request.get("mode") or "demo"),
            )
        except (TypeError, ValueError, RuntimeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/internal/web/laval/runs/{run_id}")
    def laval_status(
        run_id: str, x_ptw_owner_gateway_token: str = Header(default="")
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            result = laval_repository.status(run_id)
            result["runner_active"] = laval_runner.active(run_id)
            return result
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/internal/web/laval/runs/{run_id}/stages")
    def laval_stages(
        run_id: str, x_ptw_owner_gateway_token: str = Header(default="")
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return {"items": laval_repository.stages(run_id)}
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/internal/web/laval/runs/{run_id}/theses")
    def laval_theses(
        run_id: str, x_ptw_owner_gateway_token: str = Header(default="")
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return laval.theses(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/internal/web/laval/runs/{run_id}/theses/{thesis_id}/select")
    def select_laval_thesis(
        run_id: str,
        thesis_id: str,
        request: Mapping[str, Any],
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return laval.select_thesis(
                run_id, thesis_id, str(request.get("workspace_id") or ""),
                actor=str(request.get("actor") or "owner-gateway"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/web/laval/runs/{run_id}/youtube-transcripts")
    def add_youtube_transcript(
        run_id: str,
        request: Mapping[str, Any],
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return laval.add_manual_youtube_transcript(
                run_id,
                video_url=str(request.get("video_url") or ""),
                title=str(request.get("title") or ""),
                transcript=str(request.get("transcript") or ""),
                actor=str(request.get("actor") or "owner-gateway"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/internal/web/laval/runs/{run_id}/show")
    def laval_show(
        run_id: str,
        stage: str,
        view: str | None = None,
        country: str | None = None,
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            return laval_repository.show(run_id, stage.upper(), view=view, country=country)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/internal/web/laval/runs/{run_id}/export")
    def laval_export(
        run_id: str,
        stage: str | None = None,
        format: str = Query(default="json", pattern="^(json|md|pdf)$"),
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> Response:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            filename, media_type, content = laval_repository.export(run_id, stage=stage.upper() if stage else None, format=format)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store, private"})

    @app.post("/internal/web/laval/runs/{run_id}/{action}")
    def control_laval_run(
        run_id: str,
        action: str,
        request: Mapping[str, Any],
        x_ptw_owner_gateway_token: str = Header(default=""),
    ) -> dict[str, Any]:
        require_owner_gateway(x_ptw_owner_gateway_token)
        try:
            if action == "run":
                return laval.start(run_id, through_stage=str(request.get("through_stage") or "") or None)
            if action == "pause":
                return laval.pause(run_id)
            if action == "resume":
                return laval.resume(run_id, actor=str(request.get("actor") or "owner-gateway"))
            if action == "resume-market-signals":
                return laval.resume_with_market_signals(
                    run_id, actor=str(request.get("actor") or "owner-gateway")
                )
            if action == "approve":
                return laval.approve(run_id, str(request.get("stage") or ""), actor=str(request.get("actor") or "owner-gateway"))
            if action == "rerun":
                return laval.rerun(run_id, str(request.get("stage") or ""), country=str(request.get("country") or "") or None, force=request.get("force") is True, actor=str(request.get("actor") or "owner-gateway"))
            if action == "override":
                return laval.override(run_id, request, actor=str(request.get("actor") or "owner-gateway"))
            if action == "notify":
                if not settings.outbound_notifications_enabled:
                    raise HTTPException(
                        status_code=410, detail="outbound notifications are retired"
                    )
                return laval.notify(run_id, actor=str(request.get("actor") or "owner-gateway"))
            raise HTTPException(status_code=404, detail="unknown Laval action")
        except OperationConflict as error:
            raise HTTPException(status_code=409, detail={"active_operation": error.active}) from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError, RuntimeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/internal/emergency-stop")
    def internal_emergency_stop(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, bool]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        active = request.get("active") is True
        if active:
            laval_repository.pause_all()
            brand_repository.pause_all()
        store.update_mission(
            status="paused" if active else "active",
            auto_enabled=False,
            run_series_remaining=0,
            stop_after_current_cycle=active,
        )
        return {"emergency_stop": active}

    return app
