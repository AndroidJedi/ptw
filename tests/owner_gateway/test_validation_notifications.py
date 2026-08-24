from __future__ import annotations

from contextlib import contextmanager
import unittest

try:
    import httpx
    from owner_gateway.validation_notifications import ExistingBotValidationFailureNotifier
except ModuleNotFoundError:  # Owner Gateway runtime dependencies are tested in the built image.
    httpx = None
    ExistingBotValidationFailureNotifier = object  # type: ignore[assignment,misc]


FAILURE = {
    "target_id": "018f07ea-7f20-7000-8000-000000000001",
    "attempt_id": "018f07ea-7f20-7000-8000-000000000002",
    "stage": "ad_creative_batch",
    "attempt_number": 1,
    "error_code": "ValueError",
    "error_message": "creative 3 <offer> failed",
    "failed_at": "2026-08-24T09:44:17+00:00",
}


class Query:
    def __init__(self, stopped: bool) -> None:
        self.stopped = stopped

    def execute(self, *_args, **_kwargs):
        return self

    def fetchone(self):
        return (self.stopped,)


class Repository:
    def __init__(self, *, stopped: bool = False) -> None:
        self.stopped = stopped
        self.available = True
        self.results = []

    def reserve(self, *_args):
        if not self.available:
            return None
        self.available = False
        return dict(FAILURE)

    def record_result(self, _failure, **result):
        self.results.append(result)
        return {"status": result["status"], "attempt_id": FAILURE["attempt_id"]}

    @contextmanager
    def connection(self):
        yield Query(self.stopped)


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True, "result": {"message_id": 77}}


@unittest.skipUnless(httpx is not None, "httpx is verified in the Owner Gateway image")
class ExistingBotValidationFailureNotifierTests(unittest.TestCase):
    def notifier(self, repository: Repository, post) -> ExistingBotValidationFailureNotifier:
        return ExistingBotValidationFailureNotifier(
            repository,
            bot_token="bot-token",
            owner_chat_id=9,
            allowed_chat_ids=frozenset({9}),
            owner_console_url="https://console.example",
            post=post,
        )

    def test_one_direct_send_is_escaped_audited_and_not_repeated(self) -> None:
        repository = Repository()
        calls = []

        def post(*args, **kwargs):
            calls.append((args, kwargs))
            return Response()

        notifier = self.notifier(repository, post)
        first = notifier.notify(FAILURE["target_id"], FAILURE["attempt_id"], FAILURE["stage"])
        second = notifier.notify(FAILURE["target_id"], FAILURE["attempt_id"], FAILURE["stage"])

        self.assertEqual("sent", first["status"])
        self.assertEqual("already_reserved", second["status"])
        self.assertEqual(1, len(calls))
        message = calls[0][1]["json"]["text"]
        self.assertIn("creative 3 &lt;offer&gt; failed", message)
        self.assertIn("?page=ads", message)
        self.assertEqual(77, repository.results[0]["message_id"])

    def test_timeout_is_ambiguous_and_never_retried(self) -> None:
        repository = Repository()

        def timeout(*_args, **_kwargs):
            raise httpx.ReadTimeout("unknown delivery")

        notifier = self.notifier(repository, timeout)
        result = notifier.notify(FAILURE["target_id"], FAILURE["attempt_id"], FAILURE["stage"])
        self.assertEqual("ambiguous", result["status"])
        self.assertIn("not retried", repository.results[0]["error_message"])

    def test_emergency_stop_suppresses_without_calling_telegram(self) -> None:
        repository = Repository(stopped=True)
        notifier = self.notifier(repository, lambda *_args, **_kwargs: self.fail("must not send"))
        result = notifier.notify(FAILURE["target_id"], FAILURE["attempt_id"], FAILURE["stage"])
        self.assertEqual("suppressed", result["status"])


if __name__ == "__main__":
    unittest.main()
