from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from owner_gateway.settings import Settings


def environment(platform_database_url: str) -> dict[str, str]:
    return {
        "FIREBASE_OWNER_UID": "owner-uid",
        "IDEA_DATABASE_URL": "postgresql://idea:secret@idea/idea",
        "COMMANDER_DATABASE_URL": "postgresql://commander:secret@commander/commander",
        "PLATFORM_DATABASE_URL": platform_database_url,
        "PLATFORM_OWNER_TELEGRAM_ID": "1",
    }


class SettingsTests(unittest.TestCase):
    def test_platform_database_password_is_required(self) -> None:
        with patch.dict(os.environ, environment("postgresql://ptw@postgres/ptw"), clear=True):
            with self.assertRaisesRegex(RuntimeError, "must include a database password"):
                Settings.from_environment()

    def test_password_protected_platform_database_is_accepted(self) -> None:
        with patch.dict(os.environ, environment("postgresql://ptw:secret@postgres/ptw"), clear=True):
            settings = Settings.from_environment()
        self.assertEqual("postgresql://ptw:secret@postgres/ptw", settings.platform_database_url)


if __name__ == "__main__":
    unittest.main()
