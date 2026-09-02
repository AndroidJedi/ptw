from __future__ import annotations

from dataclasses import dataclass
import os


def _ids(name: str, fallback: str = "") -> frozenset[int]:
    raw = os.environ.get(name, fallback)
    result = frozenset(int(item.strip()) for item in raw.split(",") if item.strip())
    if not result:
        raise RuntimeError(f"{name} must contain at least one numeric ID")
    return result


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    platform_database_url: str
    telegram_bot_token: str
    allowed_user_ids: frozenset[int]
    allowed_chat_ids: frozenset[int]
    owner_web_url: str = "https://provethemwrong-86123.firebaseapp.com"

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.environ.get("DATABASE_URL", "").strip()
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        platform_database_url = os.environ.get("PLATFORM_DATABASE_URL", "").strip()
        if not database_url or not platform_database_url or not token:
            raise RuntimeError("DATABASE_URL, PLATFORM_DATABASE_URL, and the existing TELEGRAM_BOT_TOKEN are required")
        users = _ids("TELEGRAM_ALLOWED_USER_IDS")
        chats = _ids("TELEGRAM_ALLOWED_CHAT_IDS", ",".join(map(str, users)))
        return cls(
            database_url=database_url, platform_database_url=platform_database_url,
            telegram_bot_token=token,
            allowed_user_ids=users, allowed_chat_ids=chats,
            owner_web_url=os.environ.get("OWNER_WEB_URL", "https://provethemwrong-86123.firebaseapp.com").rstrip("/"),
        )
