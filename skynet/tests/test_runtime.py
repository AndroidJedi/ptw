from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from skynet.host import telegram_sender
from skynet.tools.telegram_outbox import enqueue


ROOT = Path(__file__).resolve().parents[1]


class TelegramOutboxTests(unittest.TestCase):
    def test_text_event_is_idempotent_and_sent_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            enqueue(root, "skynet.test-event", "SKYNET · test event", None)
            with mock.patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "not-a-real-token",
                "TELEGRAM_ALLOWED_CHAT_IDS": "123",
                "TELEGRAM_OWNER_CHAT_ID": "123",
            }, clear=True), mock.patch.object(telegram_sender, "_send", return_value=77) as sender:
                result = telegram_sender.drain(root)
                self.assertEqual("sent", result[0]["status"])
                self.assertEqual(77, result[0]["telegram_message_id"])
                self.assertEqual(1, sender.call_count)
                self.assertEqual([], telegram_sender.drain(root))
                self.assertEqual(1, sender.call_count)
            with self.assertRaises(FileExistsError):
                enqueue(root, "skynet.test-event", "SKYNET · duplicate", None)

    def test_interrupted_reservation_becomes_ambiguous_without_send(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queued = enqueue(root, "skynet.interrupted", "SKYNET · interrupted", None)
            sending = root / "runtime" / "telegram" / "sending" / queued.name
            sending.parent.mkdir(parents=True)
            queued.replace(sending)
            with mock.patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "not-a-real-token",
                "TELEGRAM_ALLOWED_CHAT_IDS": "123",
                "TELEGRAM_OWNER_CHAT_ID": "123",
            }, clear=True), mock.patch.object(telegram_sender, "_send") as sender:
                result = telegram_sender.drain(root)
            self.assertEqual("ambiguous", result[0]["status"])
            sender.assert_not_called()

    def test_photo_is_copied_and_digest_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"test-payload")
            queued = enqueue(
                root,
                "skynet.photo-test",
                "SKYNET · experiment x · iteration 2 · artifact abc",
                source,
            )
            event = json.loads(queued.read_text())
            artifact = root / event["artifact"]["path"]
            self.assertEqual(event["artifact"]["sha256"], telegram_sender.hashlib.sha256(
                artifact.read_bytes()
            ).hexdigest())

    def test_photo_cannot_escape_through_path_or_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as outside:
            root = Path(temporary)
            outside_photo = Path(outside) / "outside.png"
            outside_photo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"outside")
            with self.assertRaises(ValueError):
                enqueue(root, "skynet.outside-photo", "SKYNET · outside", outside_photo)
            link = root / "linked.png"
            link.symlink_to(outside_photo)
            with self.assertRaises(ValueError):
                enqueue(root, "skynet.linked-photo", "SKYNET · linked", link)

    def test_sender_rejects_artifact_replaced_by_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as outside:
            root = Path(temporary)
            source = root / "source.png"
            payload = b"\x89PNG\r\n\x1a\n" + b"same-bytes"
            source.write_bytes(payload)
            queued = enqueue(root, "skynet.sender-link", "SKYNET · sender link", source)
            event = json.loads(queued.read_text())
            artifact = root / event["artifact"]["path"]
            artifact.unlink()
            outside_photo = Path(outside) / "outside.png"
            outside_photo.write_bytes(payload)
            artifact.symlink_to(outside_photo)
            with mock.patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "not-a-real-token",
                "TELEGRAM_ALLOWED_CHAT_IDS": "123",
                "TELEGRAM_OWNER_CHAT_ID": "123",
            }, clear=True), mock.patch.object(telegram_sender, "_send") as sender:
                result = telegram_sender.drain(root)
            self.assertEqual("failed", result[0]["status"])
            sender.assert_not_called()

    def test_requires_skynet_label_and_allowlisted_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                enqueue(root, "skynet.no-label", "ordinary status", None)
            enqueue(root, "skynet.bad-owner", "SKYNET · status", None)
            with mock.patch.dict(os.environ, {
                "TELEGRAM_BOT_TOKEN": "not-a-real-token",
                "TELEGRAM_ALLOWED_CHAT_IDS": "123",
                "TELEGRAM_OWNER_CHAT_ID": "999",
            }, clear=True):
                with self.assertRaises(RuntimeError):
                    telegram_sender.drain(root)


class RestartSupervisorTests(unittest.TestCase):
    def test_launcher_restarts_fresh_runs_and_forwards_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            fake = temporary_root / "fake-codex"
            calls = temporary_root / "calls.jsonl"
            fake.write_text(
                "#!/bin/sh\n"
                "python3 - \"$@\" <<'PY'\n"
                "import json, os, sys\n"
                "path = os.environ['SKYNET_TEST_CALLS']\n"
                "with open(path, 'a', encoding='utf-8') as stream:\n"
                "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                "PY\n"
                "sleep 0.05\n"
                "exit 17\n"
            )
            fake.chmod(0o755)
            environment = {
                **os.environ,
                "SKYNET_CODEX_BIN": str(fake),
                "SKYNET_RESTART_DELAY_SECONDS": "0",
                "SKYNET_TEST_CALLS": str(calls),
            }
            process = subprocess.Popen(
                [str(ROOT / "run.sh")],
                cwd=ROOT,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if calls.exists() and len(calls.read_text().splitlines()) >= 2:
                    break
                time.sleep(0.05)
            else:
                process.kill()
                self.fail("launcher did not restart the fake Codex process")
            process.send_signal(signal.SIGTERM)
            self.assertEqual(0, process.wait(timeout=5))
            invocations = [json.loads(line) for line in calls.read_text().splitlines()]
            self.assertGreaterEqual(len(invocations), 2)
            for invocation in invocations:
                self.assertIn("exec", invocation)
                self.assertIn("--ephemeral", invocation)
                self.assertIn("workspace-write", invocation)
                self.assertIn(str(ROOT), invocation)
                self.assertNotIn(str(ROOT.parent / "apps" / "commander-web"), invocation)


if __name__ == "__main__":
    unittest.main()
