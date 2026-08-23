from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _ids(value: str) -> frozenset[int]:
    return frozenset(int(item.strip()) for item in value.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    owner_gateway_token: str
    bridge_url: str
    bridge_token: str
    telegram_bot_token: str
    owner_chat_id: int
    telegram_allowed_chat_ids: frozenset[int]
    model: str = "codex-cli-default"
    skill_path: Path = Path("/run/ptw-auth/skills/marketing-positioning/SKILL.md")

    @classmethod
    def from_environment(cls) -> "Settings":
        required = {
            "DATABASE_URL": os.environ.get("DATABASE_URL", "").strip(),
            "OWNER_GATEWAY_BRIDGE_TOKEN": os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", "").strip(),
            "LLM_BRIDGE_URL": os.environ.get("LLM_BRIDGE_URL", "").strip(),
            "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            "TELEGRAM_OWNER_CHAT_ID": os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip(),
            "TELEGRAM_ALLOWED_CHAT_IDS": os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"missing Marketing Positioning settings: {', '.join(missing)}")
        owner_chat_id = int(required["TELEGRAM_OWNER_CHAT_ID"])
        allowed_chat_ids = _ids(required["TELEGRAM_ALLOWED_CHAT_IDS"])
        if owner_chat_id not in allowed_chat_ids:
            raise RuntimeError("TELEGRAM_OWNER_CHAT_ID must be in the existing TELEGRAM_ALLOWED_CHAT_IDS")
        return cls(
            database_url=required["DATABASE_URL"],
            owner_gateway_token=required["OWNER_GATEWAY_BRIDGE_TOKEN"],
            bridge_url=required["LLM_BRIDGE_URL"].rstrip("/"),
            bridge_token=required["TELEGRAM_BOT_TOKEN"],
            telegram_bot_token=required["TELEGRAM_BOT_TOKEN"],
            owner_chat_id=owner_chat_id,
            telegram_allowed_chat_ids=allowed_chat_ids,
            model=os.environ.get("POSITIONING_LLM_MODEL", "codex-cli-default").strip(),
            skill_path=Path(os.environ.get(
                "MARKETING_POSITIONING_SKILL_PATH",
                "/run/ptw-auth/skills/marketing-positioning/SKILL.md",
            )),
        )
