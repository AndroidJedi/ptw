from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    owner_gateway_token: str
    bridge_url: str
    bridge_token: str
    pexels_api_key: str
    model: str = "codex-cli-default"
    product_brief_skill_path: Path = Path("/run/ptw-auth/skills/product-brief-generator/SKILL.md")
    content_candidate_generator_skill_path: Path = Path(
        "/run/ptw-auth/skills/content-candidate-generator/SKILL.md"
    )
    content_result_critic_skill_path: Path = Path(
        "/run/ptw-auth/skills/content-result-critic/SKILL.md"
    )

    @classmethod
    def from_environment(cls) -> "Settings":
        required = {
            "DATABASE_URL": os.environ.get("DATABASE_URL", "").strip(),
            "OWNER_GATEWAY_BRIDGE_TOKEN": os.environ.get("OWNER_GATEWAY_BRIDGE_TOKEN", "").strip(),
            "LLM_BRIDGE_URL": os.environ.get("VALIDATION_LLM_BRIDGE_URL", os.environ.get("LLM_BRIDGE_URL", "")).strip(),
            "LLM_BRIDGE_TOKEN": os.environ.get("LLM_BRIDGE_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip(),
            "PEXELS_API_KEY": os.environ.get("PEXELS_API_KEY", "").strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"missing Validation settings: {', '.join(missing)}")
        return cls(
            database_url=required["DATABASE_URL"],
            owner_gateway_token=required["OWNER_GATEWAY_BRIDGE_TOKEN"],
            bridge_url=required["LLM_BRIDGE_URL"].rstrip("/"),
            bridge_token=required["LLM_BRIDGE_TOKEN"],
            pexels_api_key=required["PEXELS_API_KEY"],
            model=os.environ.get("VALIDATION_LLM_MODEL", "codex-cli-default").strip(),
            product_brief_skill_path=Path(os.environ.get(
                "PRODUCT_BRIEF_SKILL_PATH", "/run/ptw-auth/skills/product-brief-generator/SKILL.md"
            )),
            content_candidate_generator_skill_path=Path(os.environ.get(
                "CONTENT_CANDIDATE_GENERATOR_SKILL_PATH",
                "/run/ptw-auth/skills/content-candidate-generator/SKILL.md",
            )),
            content_result_critic_skill_path=Path(os.environ.get(
                "CONTENT_RESULT_CRITIC_SKILL_PATH",
                "/run/ptw-auth/skills/content-result-critic/SKILL.md",
            )),
        )
