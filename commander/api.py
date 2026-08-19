"""Executable FastAPI composition for Telegram Commander."""

from __future__ import annotations

import hmac
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from fastapi import FastAPI, Header, HTTPException

from .model import EntityKind
from .model import RelationType
from .policy import CommanderPolicy
from .postgres_store import PostgresKnowledgeStore, connect_postgres
from .service import Commander
from .settings import Settings
from .telegram import TelegramControlPlane, TelegramUnauthorized
from .telegram_api import TelegramBotClient
from .openai_research import CodexCreativeResearchProvider, OpenAICreativeResearchProvider
import os
import re
from .research import CreativeIdeationResearchService, ResearchFinding, ResearchKnowledgeService
from .research_agents import RESEARCH_AGENTS
from .checkpoint import checkpoint_response, startup_checkpoint_canary
if TYPE_CHECKING:
    from .ad_generation import AdGenerationEngine


def create_app(
    settings: Settings,
    store: PostgresKnowledgeStore,
    telegram_client: TelegramBotClient,
    ad_engine: "AdGenerationEngine | None" = None,
) -> FastAPI:
    commander = Commander(store, CommanderPolicy.load(settings.policy_path))
    if (
        settings.creative_runtime_enabled
        and ad_engine is None
        and isinstance(store, PostgresKnowledgeStore)
    ):
        from .ad_runtime import create_ad_engine

        ad_engine = create_ad_engine(settings, store, commander)
    research_provider = (
        OpenAICreativeResearchProvider(settings.openai_api_key, model=settings.research_model)
        if settings.openai_api_key
        else CodexCreativeResearchProvider(settings.codex_executable)
        if os.path.isfile(settings.codex_executable)
        else None
    )
    research_service = CreativeIdeationResearchService(commander, research_provider) if research_provider else None
    control = TelegramControlPlane(
        commander,
        allowed_user_ids=set(settings.allowed_user_ids),
        allowed_chat_ids=set(settings.allowed_chat_ids),
        research_service=research_service,
        ad_engine=ad_engine,
    )
    app = FastAPI(title="PTW Commander", version="0.1.0")
    app.state.checkpoint_canary = startup_checkpoint_canary(
        store, settings.checkpoint_max_age_seconds
    )
    app.state.restored_checkpoint = app.state.checkpoint_canary.get("checkpoint")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def ready() -> dict[str, object]:
        try:
            store.ping()
        except Exception as error:
            raise HTTPException(status_code=503, detail="database unavailable") from error
        canary = app.state.checkpoint_canary
        if settings.checkpoint_required and canary["status"] != "fresh":
            raise HTTPException(
                status_code=503,
                detail=f"checkpoint startup canary: {canary['status']}",
            )
        return {"status": "ready", "checkpoint_canary": canary["status"]}

    @app.post("/telegram/webhook")
    def telegram_webhook(
        update: Mapping[str, Any],
        x_telegram_bot_api_secret_token: str = Header(default=""),
    ) -> dict[str, object]:
        if not hmac.compare_digest(
            x_telegram_bot_api_secret_token, settings.telegram_webhook_secret
        ):
            raise HTTPException(status_code=403, detail="invalid webhook secret")
        return _process_update(update)

    @app.post("/internal/telegram/update")
    def internal_telegram_update(
        update: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        # The established PTW poller already owns getUpdates for this bot. It
        # authenticates to this internal-only route with the shared bot token.
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        return _process_update(update)

    @app.post("/internal/emergency-stop")
    def internal_emergency_stop(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, bool]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        active = request.get("active") is True
        with store.transaction():
            commander.set_emergency_stop(
                active, actor=str(request.get("actor") or "owner-gateway")
            )
        return {"emergency_stop": active}

    @app.post("/internal/ad-batches")
    def create_ad_batch(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not settings.creative_runtime_enabled:
            raise HTTPException(status_code=410, detail="creative runtime is retired")
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        if ad_engine is None:
            raise HTTPException(status_code=503, detail="ad generation is not configured")
        try:
            chat_id = int(request.get("chat_id"))
            if chat_id not in settings.allowed_chat_ids:
                raise HTTPException(status_code=403, detail="unauthorized Telegram chat")
            batch = ad_engine.enqueue_batch(
                idea_snapshot=dict(request["idea"]),
                chat_id=chat_id,
                requested_by=str(request.get("requested_by") or "idea-evolution"),
                idempotency_key=str(request["idempotency_key"]),
            )
        except HTTPException:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"batch_id": batch.campaign_id, "status": batch.status}

    @app.post("/internal/ad-batches/{batch_id}/metrics")
    def import_ad_metrics(
        batch_id: str,
        request: Mapping[str, Any],
        x_ptw_bridge_token: str = Header(default=""),
    ) -> Mapping[str, Any]:
        if not settings.creative_runtime_enabled:
            raise HTTPException(status_code=410, detail="creative runtime is retired")
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        if ad_engine is None:
            raise HTTPException(status_code=503, detail="ad generation is not configured")
        try:
            return ad_engine.import_metrics(
                batch_id=batch_id,
                payload=request,
                actor=str(request.get("imported_by") or "analytics-bridge"),
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/internal/workspace/tasks")
    def register_workspace_task(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not settings.outbound_notifications_enabled:
            raise HTTPException(status_code=410, detail="workspace acknowledgements are retired")
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        task_id = str(request.get("task_id", "")).strip()
        scope = str(request.get("interpreted_scope", "")).strip()
        session_id = str(request.get("workspace_session_id", "")).strip()
        try:
            chat_id = int(request.get("chat_id"))
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail="chat_id must be numeric") from error
        if not re.fullmatch(r"TASK-[0-9]+", task_id):
            raise HTTPException(status_code=400, detail="task_id must match TASK-<number>")
        if not scope or len(scope) > 2000:
            raise HTTPException(status_code=400, detail="interpreted_scope must be 1-2000 characters")
        if not session_id or len(session_id) > 200:
            raise HTTPException(status_code=400, detail="workspace_session_id must be 1-200 characters")
        if chat_id not in settings.allowed_chat_ids:
            raise HTTPException(status_code=403, detail="unauthorized Telegram chat")
        try:
            record = store.register_workspace_task(
                task_id=task_id,
                interpreted_scope=scope,
                workspace_session_id=session_id,
                chat_id=chat_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _workspace_ack_response(record)

    @app.get("/internal/workspace/tasks/{task_id}/acknowledgement")
    def workspace_task_acknowledgement(
        task_id: str, x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not settings.outbound_notifications_enabled:
            raise HTTPException(status_code=410, detail="workspace acknowledgements are retired")
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        try:
            record = store.workspace_task_acknowledgement(task_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _workspace_ack_response(record)

    @app.put("/internal/workspace/checkpoint")
    def save_workspace_checkpoint(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        try:
            checkpoint = store.save_session_checkpoint(request)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        app.state.checkpoint_canary = checkpoint_response(
            checkpoint, settings.checkpoint_max_age_seconds
        )
        app.state.restored_checkpoint = checkpoint
        return app.state.checkpoint_canary

    @app.get("/internal/workspace/checkpoint")
    def restore_workspace_checkpoint(
        scope: str = "commander", x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        try:
            checkpoint = store.latest_session_checkpoint(scope)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        result = checkpoint_response(checkpoint, settings.checkpoint_max_age_seconds)
        if result["status"] == "corrupt":
            raise HTTPException(status_code=409, detail="checkpoint integrity check failed")
        return result

    @app.get("/internal/research/context/{hypothesis_id}")
    def research_context(hypothesis_id: str, x_ptw_bridge_token: str = Header(default="")) -> dict[str, object]:
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        try:
            hypothesis = store.get_entity(hypothesis_id)
            if hypothesis.kind != EntityKind.HYPOTHESIS:
                raise ValueError("research context ID must identify a hypothesis")
            source_ids = [edge.target_id for edge in store.relationships()
                          if edge.source_id == hypothesis.id and edge.relation == RelationType.DERIVED_FROM
                          and store.get_entity(edge.target_id).kind == EntityKind.SOURCE]
            sources = [store.get_entity(source_id) for source_id in source_ids]
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "hypothesis_id": hypothesis.id,
            "owner_agent": hypothesis.attributes.get("owner_agent"),
            "knowledge_domain": hypothesis.attributes.get("knowledge_domain"),
            "research_type": hypothesis.attributes.get("research_type"),
            "claim": hypothesis.attributes.get("claim"),
            "direction": hypothesis.attributes.get("creative_direction"),
            "sources": [{"id": item.id, "title": item.attributes.get("title"),
                         "uri": item.attributes.get("source_uri"),
                         "summary": item.attributes.get("finding_summary")}
                        for item in sources],
        }

    @app.post("/internal/research/laval")
    def record_laval_research(
        request: Mapping[str, Any], x_ptw_bridge_token: str = Header(default="")
    ) -> dict[str, object]:
        """Route Laval evidence through the canonical typed research service."""
        if not hmac.compare_digest(x_ptw_bridge_token, settings.telegram_bot_token):
            raise HTTPException(status_code=403, detail="invalid bridge token")
        raw_findings = request.get("findings") or []
        raw_hypotheses = request.get("hypotheses") or []
        if not isinstance(raw_findings, list) or len(raw_findings) > 500:
            raise HTTPException(status_code=400, detail="findings must be a list of at most 500 items")
        if not isinstance(raw_hypotheses, list) or len(raw_hypotheses) > 50:
            raise HTTPException(status_code=400, detail="hypotheses must be a list of at most 50 items")
        research = ResearchKnowledgeService(commander)
        product_agent = RESEARCH_AGENTS["product"]
        existing_sources = {
            str(item.attributes.get("external_id")): item
            for item in store.entities(EntityKind.SOURCE)
            if item.attributes.get("external_id")
        }
        existing_hypotheses = {
            str(item.attributes.get("idea_laval_variant_id")): item
            for item in store.entities(EntityKind.HYPOTHESIS)
            if item.attributes.get("idea_laval_variant_id")
        }
        sources: dict[str, Any] = {}
        hypotheses: dict[str, Any] = {}
        try:
            with store.transaction():
                for raw in raw_findings:
                    if not isinstance(raw, Mapping):
                        raise ValueError("each finding must be an object")
                    external_id = str(raw.get("external_id") or "").strip()
                    if not external_id or len(external_id) > 200:
                        raise ValueError("finding external_id is required")
                    source = existing_sources.get(external_id)
                    if source is None:
                        published = raw.get("published_on")
                        source = research.record_finding(
                            ResearchFinding(
                                title=str(raw.get("title") or "")[:1000],
                                source_uri=str(raw.get("source_uri") or "")[:4000],
                                finding_summary=str(raw.get("finding_summary") or "")[:10_000],
                                publisher=str(raw.get("publisher") or "")[:1000],
                                published_on=date.fromisoformat(str(published)) if published else None,
                                credibility=float(raw.get("credibility", .5)),
                                external_id=external_id,
                                research_type="product_discovery",
                            ),
                            actor="idea-laval",
                            agent=product_agent,
                        )
                        existing_sources[external_id] = source
                    sources[external_id] = source.id
                for raw in raw_hypotheses:
                    if not isinstance(raw, Mapping):
                        raise ValueError("each hypothesis must be an object")
                    external_id = str(raw.get("external_id") or "").strip()
                    if not external_id:
                        raise ValueError("hypothesis external_id is required")
                    hypothesis = existing_hypotheses.get(external_id)
                    if hypothesis is None:
                        evidence = []
                        for source_external_id in raw.get("evidence_external_ids") or []:
                            source = existing_sources.get(str(source_external_id))
                            if source is None:
                                raise ValueError("hypothesis references an unknown finding external_id")
                            evidence.append(source)
                        for source_id in raw.get("source_ids") or []:
                            source = store.get_entity(str(source_id))
                            if source.kind != EntityKind.SOURCE:
                                raise ValueError("hypothesis source_ids must identify Source entities")
                            evidence.append(source)
                        unique_evidence = tuple({item.id: item for item in evidence}.values())
                        attributes = dict(raw.get("attributes") or {})
                        attributes.update({
                            "research_type": "product_discovery",
                            "owner_agent": product_agent.owner_agent,
                            "knowledge_domain": product_agent.knowledge_domain,
                            "idea_laval_variant_id": external_id,
                        })
                        hypothesis = research.propose_hypothesis(
                            claim=str(raw.get("claim") or "")[:10_000],
                            success_metric=str(raw.get("success_metric") or "validated_demand_signal")[:500],
                            threshold=float(raw.get("threshold", .1)),
                            scope=str(raw.get("scope") or "idea_laval")[:2000],
                            findings=unique_evidence,
                            actor="idea-laval",
                            attributes=attributes,
                        )
                        existing_hypotheses[external_id] = hypothesis
                    hypotheses[external_id] = hypothesis.id
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"sources": sources, "hypotheses": hypotheses}

    def _process_update(update: Mapping[str, Any]) -> dict[str, object]:
        result: dict[str, object] = {}
        try:
            update_id = int(update["update_id"])
            with store.transaction():
                if not store.record_inbox_once(update_id):
                    return {"ok": True, "duplicate": True}
                reply = control.handle_update(update)
                if settings.outbound_notifications_enabled:
                    store.enqueue_outbox(
                        "telegram.send_message", None,
                        {"chat_id": reply.chat_id, "text": reply.text},
                    )
                result = {"response": reply.text}
                if settings.outbound_notifications_enabled and reply.callback_query_id:
                    store.enqueue_outbox(
                        "telegram.answer_callback", None,
                        {"callback_query_id": reply.callback_query_id},
                    )
        except TelegramUnauthorized as error:
            raise HTTPException(status_code=403, detail="unauthorized Telegram identity") from error
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"ok": True, "duplicate": False, "result": result}

    return app


def _workspace_ack_response(record: Any) -> dict[str, object]:
    return {
        "task_id": record.task_id,
        "interpreted_scope": record.interpreted_scope,
        "workspace_session_id": record.workspace_session_id,
        "acknowledgement_status": record.status,
        "telegram_message_id": record.telegram_message_id,
        "may_start": record.status == "acknowledged",
    }


def create_app_from_env() -> FastAPI:
    settings = Settings.from_environment()
    store = connect_postgres(settings.database_url)
    return create_app(settings, store, TelegramBotClient(settings.telegram_bot_token))
