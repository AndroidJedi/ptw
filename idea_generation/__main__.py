from __future__ import annotations

from pathlib import Path

from .config import Settings
from .engine import EvolutionEngine
from .manage import ROOT
from .provider import MockLLMProvider, OpenAIProvider
from .seeds import load
from .store import PostgresStore
from .telegram import TelegramController, TelegramPoller


def main() -> None:
    settings = Settings.from_environment()
    store = PostgresStore(settings.database_url)
    store.migrate(ROOT / "db/idea_generation")
    mission, contexts = load(ROOT / "ideaGeneration")
    store.seed(mission, contexts)
    if settings.llm_provider == "mock":
        provider = MockLLMProvider()
    elif settings.llm_provider == "openai":
        provider = OpenAIProvider(settings.openai_api_key, settings.llm_model)
    else:
        raise RuntimeError("LLM_PROVIDER must be mock or openai")
    engine = EvolutionEngine(store, provider)
    controller = TelegramController(store, engine, settings.allowed_chat_ids)
    if store.mission()["run_series_remaining"] > 0:
        engine.continue_series()
    TelegramPoller(settings.telegram_token, controller, store, settings.poll_timeout).run_forever()


if __name__ == "__main__": main()
