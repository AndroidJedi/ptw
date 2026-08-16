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
    llm_provider: str = "mock"
    llm_model: str = "mock-v1"
    openai_api_key: str = ""
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
        return cls(
            database_url=database_url,
            telegram_token=token,
            allowed_chat_ids=_ids(raw_ids),
            llm_provider=os.environ.get("LLM_PROVIDER", "mock").strip().lower(),
            llm_model=os.environ.get("LLM_MODEL", "mock-v1").strip(),
            openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            poll_timeout=max(1, int(os.environ.get("TELEGRAM_POLL_TIMEOUT", "30"))),
        )
