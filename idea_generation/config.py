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
        )
