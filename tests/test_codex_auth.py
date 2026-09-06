from __future__ import annotations

import unittest

from auth.service import device_login_details


class CodexAuthorizationOutputTests(unittest.TestCase):
    def test_exposes_only_exact_device_url_and_code(self) -> None:
        url, code = device_login_details(
            "Open https://auth.openai.com/codex/device and enter Q7T2-4MNP; secret=do-not-return"
        )
        self.assertEqual("https://auth.openai.com/codex/device", url)
        self.assertEqual("Q7T2-4MNP", code)

    def test_rejects_untrusted_url_and_unstructured_code(self) -> None:
        self.assertEqual((None, None), device_login_details("https://example.test/device ABCDEFGH"))
