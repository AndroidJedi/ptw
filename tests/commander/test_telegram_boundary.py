from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
