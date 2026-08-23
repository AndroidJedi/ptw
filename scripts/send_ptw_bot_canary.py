#!/usr/bin/env python3
"""Send one clearly labelled v2 release check through the existing PTW bot."""

from __future__ import annotations

from datetime import datetime, timezone
import os

import httpx


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = int(os.environ.get("TELEGRAM_OWNER_CHAT_ID", "0"))
    allowed = {
        int(value.strip()) for value in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
        if value.strip()
    }
    if not token or chat_id == 0 or chat_id not in allowed:
        raise SystemExit("existing PTW bot and allowlisted owner chat are required")
    message = (
        "PTW v2 deployment canary — NOT A LEAD\n"
        "Direct sendMessage only; no lead row, webhook, worker, or polling process was created.\n"
        f"UTC: {datetime.now(timezone.utc).isoformat()}"
    )
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("ok") is not True:
        raise SystemExit("existing PTW bot rejected the deployment canary")
    print(f"existing PTW bot direct canary sent; message_id={int(payload['result']['message_id'])}")


if __name__ == "__main__":
    main()
