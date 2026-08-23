from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _enabled(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    owner_gateway_token: str
    bridge_url: str
    bridge_token: str
    model: str = "codex-cli-default"
    research_provider: str = "dataforseo"
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    dataforseo_verified: bool = False
    dataforseo_poll_timeout_seconds: int = 900
    max_spend_usd: float = 0.05
    skill_path: Path = Path("/run/ptw-auth/skills/marketing-positioning/SKILL.md")

    @classmethod
    def from_environment(cls) -> "Settings":
        required = {
            "DATABASE_URL": os.environ.get("DATABASE_URL", "").strip(),
            "OWNER_GATEWAY_BRIDGE_TOKEN": os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", "").strip(),
            "LLM_BRIDGE_URL": os.environ.get("LLM_BRIDGE_URL", "").strip(),
            # The already configured PTW bot token is an existing internal bridge
            # credential. This service never calls Telegram.
            "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"missing Marketing Positioning settings: {', '.join(missing)}")
        maximum = min(0.05, max(0.0, float(os.environ.get("POSITIONING_MAX_SPEND_USD", "0.05"))))
        return cls(
            database_url=required["DATABASE_URL"],
            owner_gateway_token=required["OWNER_GATEWAY_BRIDGE_TOKEN"],
            bridge_url=required["LLM_BRIDGE_URL"].rstrip("/"),
            bridge_token=required["TELEGRAM_BOT_TOKEN"],
            model=os.environ.get("POSITIONING_LLM_MODEL", "codex-cli-default").strip(),
            research_provider=os.environ.get("POSITIONING_RESEARCH_PROVIDER", "dataforseo").strip().lower(),
            dataforseo_login=os.environ.get("DATAFORSEO_LOGIN", "").strip(),
            dataforseo_password=os.environ.get("DATAFORSEO_PASSWORD", "").strip(),
            dataforseo_verified=_enabled("DATAFORSEO_VERIFIED"),
            dataforseo_poll_timeout_seconds=max(
                60, int(os.environ.get("DATAFORSEO_POLL_TIMEOUT_SECONDS", "900"))
            ),
            max_spend_usd=maximum,
            skill_path=Path(os.environ.get(
                "MARKETING_POSITIONING_SKILL_PATH",
                "/run/ptw-auth/skills/marketing-positioning/SKILL.md",
            )),
        )
