from __future__ import annotations

import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from commander.api import create_app
    from commander.settings import Settings
except ModuleNotFoundError:  # FastAPI is installed in the runtime image.
    TestClient = None
    create_app = None
    Settings = None

try:
    from commander.api import telegram_command
except ModuleNotFoundError:  # FastAPI is installed in the runtime image.
    telegram_command = None


@unittest.skipIf(telegram_command is None, "fastapi is required")
class TelegramBoundaryTests(unittest.TestCase):
    def test_only_three_slash_commands_are_recognized(self) -> None:
        self.assertEqual("/help", telegram_command("/help"))
        self.assertEqual("/status", telegram_command("/status@ptw_commander_bot"))
        self.assertEqual("/stop", telegram_command("/stop emergency"))
        for value in ("help", "status", "stop", "/start", "/create", "publish campaign"):
            with self.subTest(value=value):
                self.assertEqual("", telegram_command(value))


@unittest.skipIf(TestClient is None, "fastapi is required")
class ReviewNotificationRelayTests(unittest.TestCase):
    @staticmethod
    def settings():
        return Settings(
            database_url="postgresql://unused",
            platform_database_url="postgresql://unused-platform",
            telegram_bot_token="test-bot-token",
            allowed_user_ids=frozenset({111}), allowed_chat_ids=frozenset({222}),
            owner_web_url="https://owner.example", owner_chat_id=222,
            internal_bridge_token="internal-token",
        )

    def test_relay_uses_server_owner_chat_and_web_only_deep_link(self) -> None:
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            @staticmethod
            def read():
                return b'{"ok":true,"result":{"message_id":731}}'

        def urlopen(outgoing, **_kwargs):
            import json

            captured["url"] = outgoing.full_url
            captured["body"] = json.loads(outgoing.data)
            return Response()

        event = {
            "schema": "ptw.owner-review-notification.v1",
            "notification_id": "01900000-0000-7000-8000-000000000001",
            "run_id": "01900000-0000-7000-8000-000000000002",
            "project_id": "01900000-0000-7000-8000-000000000003",
            "project_name": "Decision Session", "platform": "instagram",
            "creative_count": 5,
        }
        with patch("commander.api.request.urlopen", side_effect=urlopen):
            with TestClient(create_app(self.settings())) as client:
                self.assertEqual(403, client.post(
                    "/internal/review-notifications", json=event,
                ).status_code)
                delivered = client.post(
                    "/internal/review-notifications", json=event,
                    headers={"Authorization": "Bearer internal-token"},
                )
        self.assertEqual(200, delivered.status_code, delivered.text)
        self.assertEqual("delivered", delivered.json()["status"])
        self.assertEqual("731", delivered.json()["provider_message_id"])
        self.assertEqual(222, captured["body"]["chat_id"])
        self.assertIn("Decision Session · instagram", captured["body"]["text"])
        self.assertIn("five posts ready", captured["body"]["text"])
        self.assertIn("view=result-review", captured["body"]["text"])
        self.assertTrue(captured["url"].endswith("/sendMessage"))

    def test_review_actions_remain_unavailable_from_telegram(self) -> None:
        update = {
            "message": {
                "from": {"id": 111}, "chat": {"id": 222},
                "text": "/approve 01900000-0000-7000-8000-000000000001",
            },
        }
        with TestClient(create_app(self.settings())) as client:
            response = client.post(
                "/internal/telegram/update", json=update,
                headers={"X-PTW-Bridge-Token": "test-bot-token"},
            )
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn("only in the web console", response.json()["result"]["response"])


if __name__ == "__main__":
    unittest.main()
