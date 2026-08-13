"""Register the configured public HTTPS Telegram webhook."""

from __future__ import annotations

import os

from .settings import Settings
from .telegram_api import TelegramBotClient


def main() -> None:
    settings = Settings.from_environment()
    public_base_url = os.environ.get("COMMANDER_PUBLIC_BASE_URL", "").rstrip("/")
    if not public_base_url.startswith("https://"):
        raise RuntimeError("COMMANDER_PUBLIC_BASE_URL must be a public HTTPS URL")
    TelegramBotClient(settings.telegram_bot_token).set_webhook(
        f"{public_base_url}/telegram/webhook", settings.telegram_webhook_secret
    )
    print("Telegram webhook registered.")


if __name__ == "__main__":
    main()
