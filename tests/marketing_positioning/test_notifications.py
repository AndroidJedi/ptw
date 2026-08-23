from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from marketing_positioning.notifications import ExistingBotPositioningNotifier


REVISION_ID = "018f07ea-7f20-7000-8000-000000000001"
PROJECT_ID = "018f07ea-7f20-7000-8000-000000000002"
ATTEMPT_ID = "018f07ea-7f20-7000-8000-000000000003"


class FakeRepository:
    def __init__(self, *, status: str = "completed", stopped: bool = False) -> None:
        self.status = status
        self.stopped = stopped
        self.recorded: list[dict[str, object]] = []

    def notification_attempt(self, _attempt_id: str):
        return self.recorded[-1] if self.recorded else None

    def get_revision(self, _revision_id: str):
        return {
            "id": REVISION_ID, "project_id": PROJECT_ID, "revision_number": 1,
            "status": self.status, "error_code": "FixtureError",
            "error_message": "failed <unsafe>",
        }

    def generation_attempt(self, _attempt_id: str):
        return {
            "id": ATTEMPT_ID, "revision_id": REVISION_ID, "attempt_number": 1,
            "status": "completed" if self.status == "completed" else "failed",
        }

    def emergency_stopped(self):
        return self.stopped

    def get_project(self, _project_id: str):
        return {
            "id": PROJECT_ID, "target_country": "US", "research_language": "en",
            "output_language": "uk", "raw_idea": "Idea <owner>",
        }

    def record_notification_attempt(self, revision_id: str, generation_attempt_id: str, **values):
        item = {
            "revision_id": revision_id, "generation_attempt_id": generation_attempt_id,
            **values,
        }
        self.recorded.append(item)
        return item


class PositioningNotificationTests(unittest.TestCase):
    def notifier(self, repository: FakeRepository) -> ExistingBotPositioningNotifier:
        return ExistingBotPositioningNotifier(
            repository, bot_token="existing-token", owner_chat_id=42,
            allowed_chat_ids=frozenset({42}),
        )

    def test_completed_notification_escapes_owner_text_and_is_idempotent(self) -> None:
        repository = FakeRepository()
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"ok": True, "result": {"message_id": 9001}},
        )
        transport = SimpleNamespace(post=Mock(return_value=response), TimeoutException=TimeoutError)
        with patch("marketing_positioning.notifications.httpx", transport):
            result = self.notifier(repository).notify(REVISION_ID, ATTEMPT_ID)
            duplicate = self.notifier(repository).notify(REVISION_ID, ATTEMPT_ID)
        self.assertEqual("sent", result["status"])
        self.assertEqual(result, duplicate)
        self.assertEqual(1, transport.post.call_count)
        message = transport.post.call_args.kwargs["json"]["text"]
        self.assertIn("Idea &lt;owner&gt;", message)
        self.assertNotIn("Idea <owner>", message)

    def test_failure_notification_contains_durable_error(self) -> None:
        repository = FakeRepository(status="failed")
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"ok": True, "result": {"message_id": 9002}},
        )
        transport = SimpleNamespace(post=Mock(return_value=response), TimeoutException=TimeoutError)
        with patch("marketing_positioning.notifications.httpx", transport):
            result = self.notifier(repository).notify(REVISION_ID, ATTEMPT_ID)
        self.assertEqual("failed", result["terminal_status"])
        message = transport.post.call_args.kwargs["json"]["text"]
        self.assertIn("FixtureError", message)
        self.assertIn("failed &lt;unsafe&gt;", message)

    def test_emergency_stop_suppresses_without_sending(self) -> None:
        repository = FakeRepository(stopped=True)
        transport = SimpleNamespace(post=Mock(), TimeoutException=TimeoutError)
        with patch("marketing_positioning.notifications.httpx", transport):
            result = self.notifier(repository).notify(REVISION_ID, ATTEMPT_ID)
        self.assertEqual("suppressed", result["status"])
        transport.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
