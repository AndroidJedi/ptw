"""Model routing for agents that compose or generate visual artifacts."""
import os

DEFAULT_VISUAL_AGENT_MODEL = "gpt-6-astra"


def visual_agent_model() -> str:
    return os.environ.get("PTW_VISUAL_AGENT_MODEL", "").strip() or DEFAULT_VISUAL_AGENT_MODEL
