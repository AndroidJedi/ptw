from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient
    from commander.api import create_app, telegram_command
    from commander.settings import Settings
except ModuleNotFoundError:  # FastAPI is installed in the runtime image.
    TestClient = None
    create_app = None
    telegram_command = None
    Settings = None


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
    def test_normal_work_remains_unavailable_from_telegram(self) -> None:
        settings = Settings(
            database_url="postgresql://unused",
            platform_database_url="postgresql://unused-platform",
            telegram_bot_token="test-bot-token",
            allowed_user_ids=frozenset({111}), allowed_chat_ids=frozenset({222}),
            owner_web_url="https://owner.example",
        )
        update = {
            "message": {
                "from": {"id": 111}, "chat": {"id": 222},
                "text": "/create a Product Brief",
            },
        }
        with TestClient(create_app(settings)) as client:
            response = client.post(
                "/internal/telegram/update", json=update,
                headers={"X-PTW-Bridge-Token": "test-bot-token"},
            )
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn("only in the web console", response.json()["result"]["response"])


if __name__ == "__main__":
    unittest.main()
