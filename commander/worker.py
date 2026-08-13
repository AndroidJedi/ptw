"""Transactional-outbox delivery worker."""

from __future__ import annotations

import argparse
import time

from .postgres_store import OutboxMessage, PostgresKnowledgeStore, connect_postgres
from .settings import Settings
from .telegram_api import TelegramBotClient


TOPICS = ("telegram.send_message", "telegram.send_photo", "telegram.answer_callback")


def deliver_once(
    store: PostgresKnowledgeStore, client: TelegramBotClient, *, limit: int = 20
) -> int:
    delivered = 0
    with store.transaction():
        for message in store.claim_outbox(topics=TOPICS, limit=limit):
            try:
                result = _deliver(client, message)
            except Exception as error:
                store.mark_outbox_failed(message.id, f"{type(error).__name__}: {error}")
            else:
                if message.topic == "telegram.send_photo" and message.payload.get("creative_id"):
                    store.record_telegram_delivery(
                        int(message.payload["chat_id"]),
                        int(result["message_id"]),
                        str(message.payload["creative_id"]),
                    )
                store.mark_outbox_published(message.id)
                delivered += 1
    return delivered


def _deliver(client: TelegramBotClient, message: OutboxMessage):
    payload = message.payload
    if message.topic == "telegram.send_message":
        return client.send_message(int(payload["chat_id"]), str(payload["text"]))
    elif message.topic == "telegram.send_photo":
        from pathlib import Path

        return client.send_photo(
            int(payload["chat_id"]), Path(str(payload["path"])), str(payload.get("caption", ""))
        )
    elif message.topic == "telegram.answer_callback":
        return client.answer_callback_query(str(payload["callback_query_id"]))
    else:
        raise ValueError(f"unsupported delivery topic: {message.topic}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    settings = Settings.from_environment()
    store = connect_postgres(settings.database_url)
    client = TelegramBotClient(settings.telegram_bot_token)
    while True:
        delivered = deliver_once(store, client)
        if args.once:
            return
        if delivered == 0:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
