"""Strict environment configuration for executable Commander services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _ids(name: str) -> frozenset[int]:
    raw = os.environ.get(name, "")
    values = frozenset(int(value.strip()) for value in raw.split(",") if value.strip())
    if not values:
        raise RuntimeError(f"{name} must contain at least one numeric ID")
    return values


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    telegram_bot_token: str
    telegram_webhook_secret: str
    allowed_user_ids: frozenset[int]
    allowed_chat_ids: frozenset[int]
    asset_directory: Path
    policy_path: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        required = {
            name: os.environ.get(name, "").strip()
            for name in ("DATABASE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET")
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"missing required environment variables: {', '.join(missing)}")
        secret = required["TELEGRAM_WEBHOOK_SECRET"]
        if len(secret) < 32:
            raise RuntimeError("TELEGRAM_WEBHOOK_SECRET must be at least 32 characters")
        return cls(
            database_url=required["DATABASE_URL"],
            telegram_bot_token=required["TELEGRAM_BOT_TOKEN"],
            telegram_webhook_secret=secret,
            allowed_user_ids=_ids("TELEGRAM_ALLOWED_USER_IDS"),
            allowed_chat_ids=_ids("TELEGRAM_ALLOWED_CHAT_IDS"),
            asset_directory=Path(os.environ.get("COMMANDER_ASSET_DIR", "/var/lib/ptw/assets")),
            policy_path=Path(os.environ.get("COMMANDER_POLICY_PATH", "config/commander/policies.json")),
        )
