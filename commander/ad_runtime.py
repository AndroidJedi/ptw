"""Production composition for the ad generation engine."""

from __future__ import annotations

from .ad_generation import AdGenerationEngine
from .ad_provider import OpenAIAdProvider, UnavailableAdProvider
from .ad_repository import PostgresAdWorkflowRepository
from .policy import CommanderPolicy
from .postgres_store import PostgresKnowledgeStore
from .service import Commander
from .settings import Settings


def create_ad_engine(
    settings: Settings, store: PostgresKnowledgeStore, commander: Commander | None = None
) -> AdGenerationEngine:
    service = commander or Commander(store, CommanderPolicy.load(settings.policy_path))
    if settings.ad_image_model != "gpt-image-2":
        provider = UnavailableAdProvider(
            "COMMANDER_AD_IMAGE_MODEL must be gpt-image-2; older-model fallback is forbidden"
        )
    elif settings.ad_spec_model != "gpt-5-mini" or settings.ad_conclusion_model != "gpt-5-mini":
        provider = UnavailableAdProvider(
            "ad specification and conclusion models must be gpt-5-mini for this workflow"
        )
    elif settings.openai_api_key:
        provider = OpenAIAdProvider(
            settings.openai_api_key,
            image_model=settings.ad_image_model,
            spec_model=settings.ad_spec_model,
            conclusion_model=settings.ad_conclusion_model,
        )
    else:
        provider = UnavailableAdProvider(
            "OPENAI_API_KEY is not configured; add it to the Commander runtime and restart"
        )
    return AdGenerationEngine(
        service,
        PostgresAdWorkflowRepository(store),
        provider,
        settings.asset_directory,
    )
