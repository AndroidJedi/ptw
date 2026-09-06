from __future__ import annotations

import unittest
import io
import stat
import tempfile
from pathlib import Path
import time
from unittest.mock import MagicMock, patch

from auth.service import AuthorizationController, device_login_details


class CodexAuthorizationOutputTests(unittest.TestCase):
    def test_exposes_only_exact_device_url_and_code(self) -> None:
        url, code = device_login_details(
            "Open \x1b[94mhttps://auth.openai.com/codex/device\x1b[0m and enter "
            "\x1b[94mQ7T2-4MNP\x1b[0m; secret=do-not-return"
        )
        self.assertEqual("https://auth.openai.com/codex/device", url)
        self.assertEqual("Q7T2-4MNP", code)

    def test_rejects_untrusted_url_and_unstructured_code(self) -> None:
        self.assertEqual((None, None), device_login_details("https://example.test/device ABCDEFGH"))


class CodexAuthorizationStatusTests(unittest.TestCase):
    @staticmethod
    def await_terminal(controller: AuthorizationController) -> dict[str, object]:
        for _ in range(100):
            value = controller.status()
            if value["status"] != "verifying":
                return value
            time.sleep(0.01)
        raise AssertionError("authorization verification did not finish")

    def test_existing_login_requires_a_working_test_before_authorized(self) -> None:
        controller = AuthorizationController("codex", Path("/tmp/test-codex-auth"))
        with (
            patch.object(controller, "_logged_in", return_value=True),
            patch.object(controller, "_working_test", return_value=True),
        ):
            self.assertEqual(
                {"status": "verifying", "test_status": None}, controller.status(),
            )
            self.assertEqual(
                {"status": "authorized", "test_status": "passed"},
                self.await_terminal(controller),
            )

    def test_stale_login_is_reported_failed_when_working_test_fails(self) -> None:
        controller = AuthorizationController("codex", Path("/tmp/test-codex-auth"))
        with (
            patch.object(controller, "_logged_in", return_value=True),
            patch.object(controller, "_working_test", return_value=False),
            patch("auth.service.WORKING_TEST_RETRY_DELAY_SECONDS", 0),
        ):
            self.assertEqual(
                {"status": "verifying", "test_status": None}, controller.status(),
            )
            self.assertEqual(
                {"status": "failed", "test_status": "failed"},
                self.await_terminal(controller),
            )

    def test_transient_working_test_failure_is_retried(self) -> None:
        controller = AuthorizationController("codex", Path("/tmp/test-codex-auth"))
        with (
            patch.object(controller, "_logged_in", return_value=True),
            patch.object(controller, "_working_test", side_effect=[False, True]) as working_test,
            patch("auth.service.WORKING_TEST_RETRY_DELAY_SECONDS", 0),
        ):
            self.assertEqual(
                {"status": "verifying", "test_status": None}, controller.status(),
            )
            self.assertEqual(
                {"status": "authorized", "test_status": "passed"},
                self.await_terminal(controller),
            )
        self.assertEqual(2, working_test.call_count)

    def test_device_login_uses_a_pseudo_terminal(self) -> None:
        controller = AuthorizationController("codex", Path("/tmp/test-codex-auth"))
        process = MagicMock()
        output = io.StringIO()
        with (
            patch("auth.service.pty.openpty", return_value=(10, 11)),
            patch("auth.service.subprocess.Popen", return_value=process) as popen,
            patch("auth.service.os.close") as close,
            patch("auth.service.os.fdopen", return_value=output) as fdopen,
        ):
            actual_process, actual_output = controller._start_device_login()

        self.assertIs(process, actual_process)
        self.assertIs(output, actual_output)
        popen.assert_called_once_with(
            ["codex", "login", "--device-auth"],
            stdin=11, stdout=11, stderr=11,
            env=controller._environment(), close_fds=True,
        )
        close.assert_called_once_with(11)
        fdopen.assert_called_once_with(10, "r", encoding="utf-8", errors="replace")

    def test_publishes_root_owned_group_readable_worker_credential(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth_file = Path(directory, "auth.json")
            auth_file.write_text("{}", encoding="utf-8")
            controller = AuthorizationController("codex", Path(directory))
            with (
                patch("auth.service.WORKER_CREDENTIAL_GID", 10001),
                patch("auth.service.os.chown") as chown,
            ):
                controller._publish_worker_credential()

            chown.assert_called_once_with(auth_file, -1, 10001)
            self.assertEqual(0o640, stat.S_IMODE(auth_file.stat().st_mode))
