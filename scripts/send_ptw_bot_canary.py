#!/usr/bin/env python3
"""Send one clearly labelled emergency-boundary check through the existing PTW bot."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
import json
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", help="Verify bot identity without sending a message")
    args = parser.parse_args()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    allowed = {
        int(value.strip()) for value in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
        if value.strip()
    }
    chat_id = int(os.environ.get("TELEGRAM_OWNER_CHAT_ID", "0"))
    if chat_id == 0 and allowed:
        chat_id = sorted(allowed)[0]
    if args.read_only:
        if not token:
            raise SystemExit("existing PTW bot token is required")
        request = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read())
        except Exception:
            raise SystemExit("existing PTW bot identity check failed") from None
        result = payload.get("result") or {}
        if payload.get("ok") is not True or result.get("is_bot") is not True or result.get("username") != "ptw_commander_bot":
            raise SystemExit("existing PTW bot identity did not match")
        print("existing PTW bot identity verified; no message sent")
        return
    if not token or chat_id == 0 or chat_id not in allowed:
        raise SystemExit("existing PTW bot and allowlisted owner chat are required")
    message = (
        "PTW deployment canary\n"
        "Direct sendMessage only; no job, webhook, or polling process was created.\n"
        f"UTC: {datetime.now(timezone.utc).isoformat()}"
    )
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({
            "chat_id": chat_id, "text": message, "disable_web_page_preview": True,
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read())
    if payload.get("ok") is not True:
        raise SystemExit("existing PTW bot rejected the deployment canary")
    print(f"existing PTW bot direct canary sent; message_id={int(payload['result']['message_id'])}")


if __name__ == "__main__":
    main()
