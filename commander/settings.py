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
    owner_chat_id: int = 0
    internal_bridge_token: str = ""

    @classmethod
    def from_environment(cls) -> "Settings":
        database_url = os.environ.get("DATABASE_URL", "").strip()
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        platform_database_url = os.environ.get("PLATFORM_DATABASE_URL", "").strip()
        if not database_url or not platform_database_url or not token:
            raise RuntimeError("DATABASE_URL, PLATFORM_DATABASE_URL, and the existing TELEGRAM_BOT_TOKEN are required")
        users = _ids("TELEGRAM_ALLOWED_USER_IDS")
        chats = _ids("TELEGRAM_ALLOWED_CHAT_IDS", ",".join(map(str, users)))
        owner_chat_id = int(os.environ.get("TELEGRAM_OWNER_CHAT_ID", "0") or 0)
        if not owner_chat_id:
            if len(chats) != 1:
                raise RuntimeError("TELEGRAM_OWNER_CHAT_ID is required when multiple chats are authorized")
            owner_chat_id = next(iter(chats))
        if owner_chat_id not in chats:
            raise RuntimeError("TELEGRAM_OWNER_CHAT_ID must be an authorized chat")
        bridge_token = os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", "").strip()
        if not bridge_token:
            raise RuntimeError("OWNER_GATEWAY_BRIDGE_TOKEN is required for notification relay authorization")
        return cls(
            database_url=database_url, platform_database_url=platform_database_url,
            telegram_bot_token=token,
            allowed_user_ids=users, allowed_chat_ids=chats,
            owner_web_url=os.environ.get("OWNER_WEB_URL", "https://provethemwrong-86123.firebaseapp.com").rstrip("/"),
            owner_chat_id=owner_chat_id, internal_bridge_token=bridge_token,
        )
