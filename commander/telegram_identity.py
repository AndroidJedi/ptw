"""Print user/chat IDs from messages sent to an unregistered bot."""

from __future__ import annotations

import os

from .telegram_api import TelegramBotClient


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    found: set[tuple[int, int, str]] = set()
    for update in TelegramBotClient(token).get_updates():
        message = update.get("message") or update.get("callback_query", {}).get("message")
        sender = update.get("message", {}).get("from") or update.get("callback_query", {}).get("from")
        if not isinstance(message, dict) or not isinstance(sender, dict):
            continue
        found.add((int(sender["id"]), int(message["chat"]["id"]), str(sender.get("username", ""))))
    if not found:
        print("No messages found. Send /start to the bot, then run this command again.")
        return
    for user_id, chat_id, username in sorted(found):
        print(f"user_id={user_id} chat_id={chat_id} username={username or '-'}")


if __name__ == "__main__":
    main()
