from __future__ import annotations

import os
from dataclasses import dataclass


def _ids(value: str) -> frozenset[int]:
    result = frozenset(int(item.strip()) for item in value.split(",") if item.strip())
    if not result:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_IDS must contain at least one numeric ID")
    return result


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    telegram_token: str
    allowed_chat_ids: frozenset[int]
    allowed_user_ids: frozenset[int]
    llm_provider: str = "mock"
    llm_model: str = "mock-v1"
    openai_api_key: str = ""
    llm_bridge_url: str = ""
    ad_batch_bridge_url: str = ""
    owner_gateway_token: str = ""
    poll_timeout: int = 30
    search_provider: str = "fixture"
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    dataforseo_verified: bool = False
    dataforseo_poll_timeout: int = 3600
    trend_provider: str = "fixture"
    trend_bridge_url: str = ""
    trend_bridge_token: str = ""
    research_bridge_url: str = ""
    max_spend_usd: float = 0.05
    reserved_spend_usd: float = 0.04

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.environ.get("DATABASE_URL", "").strip()
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not database_url or not token:
            raise RuntimeError("DATABASE_URL and TELEGRAM_BOT_TOKEN are required")
        raw_ids = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "") or os.environ.get(
            "TELEGRAM_ALLOWED_USER_IDS", ""
        )
        raw_user_ids = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "") or raw_ids
        max_spend_usd = min(0.05, max(0.0, float(os.environ.get("LAVAL_MAX_SPEND_USD", "0.05"))))
        reserved_spend_usd = min(max_spend_usd, 0.04, max(0.0, float(os.environ.get("LAVAL_RESERVED_SPEND_USD", "0.04"))))
        return cls(
            database_url=database_url,
            telegram_token=token,
            allowed_chat_ids=_ids(raw_ids),
            allowed_user_ids=_ids(raw_user_ids),
            llm_provider=os.environ.get("LLM_PROVIDER", "mock").strip().lower(),
            llm_model=os.environ.get("LLM_MODEL", "mock-v1").strip(),
            openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            llm_bridge_url=os.environ.get("LLM_BRIDGE_URL", "").strip(),
            ad_batch_bridge_url=os.environ.get("AD_BATCH_BRIDGE_URL", "").strip(),
            owner_gateway_token=os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", "").strip(),
            poll_timeout=max(1, int(os.environ.get("TELEGRAM_POLL_TIMEOUT", "30"))),
            search_provider=os.environ.get(
                "LAVAL_SEARCH_PROVIDER", os.environ.get("SEARCH_PROVIDER", "fixture")
            ).strip().lower(),
            dataforseo_login=os.environ.get("DATAFORSEO_LOGIN", "").strip(),
            dataforseo_password=os.environ.get("DATAFORSEO_PASSWORD", "").strip(),
            dataforseo_verified=os.environ.get("DATAFORSEO_VERIFIED", "").strip() == "1",
            dataforseo_poll_timeout=max(60, int(os.environ.get("DATAFORSEO_POLL_TIMEOUT_SECONDS", "3600"))),
            trend_provider=os.environ.get(
                "LAVAL_TREND_PROVIDER", os.environ.get("TREND_PROVIDER", "fixture")
            ).strip().lower(),
            trend_bridge_url=os.environ.get("GOOGLE_TRENDS_BRIDGE_URL", "").strip(),
            trend_bridge_token=os.environ.get("GOOGLE_TRENDS_BRIDGE_TOKEN", "").strip(),
            research_bridge_url=os.environ.get(
                "LAVAL_RESEARCH_BRIDGE_URL",
                "http://ptw-commander-api:8080/internal/research/laval",
            ).strip(),
            max_spend_usd=max_spend_usd,
            reserved_spend_usd=reserved_spend_usd,
        )
