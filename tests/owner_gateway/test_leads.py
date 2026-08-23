from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from owner_gateway.leads import ExistingBotLeadNotifier, LandingLeadRepository


class LeadValidationTests(unittest.TestCase):
    def test_exact_form_allowlists_and_validation(self) -> None:
        self.assertEqual(
            LandingLeadRepository._fields("waitlist", {"email": "owner@example.com"}),
            {"email": "owner@example.com"},
        )
        with self.assertRaisesRegex(ValueError, "email is invalid"):
            LandingLeadRepository._fields("waitlist", {"email": "not-an-email"})
        with self.assertRaisesRegex(ValueError, "Telegram handle"):
            LandingLeadRepository._fields(
                "community_interest", {"name": "A", "email": "a@example.com", "telegram_handle": "bad handle"}
            )

    def test_notification_escapes_every_visitor_field_and_includes_exact_context(self) -> None:
        message = ExistingBotLeadNotifier._message({
            "id": "018f07ea-7f20-7000-8000-000000000001",
            "form_id": "contact_request",
            "build_id": "018f07ea-7f20-7000-8000-000000000002",
            "template_id": "product",
            "positioning_project_id": "018f07ea-7f20-7000-8000-000000000003",
            "positioning_revision_id": "018f07ea-7f20-7000-8000-000000000004",
            "submitted_at": "2026-08-23T12:00:00+00:00",
            "fields": {"name": "<b>Visitor</b>", "note": "A & B"},
        })
        self.assertNotIn("<b>Visitor</b>", message)
        self.assertIn("&lt;b&gt;Visitor&lt;/b&gt;", message)
        self.assertIn("A &amp; B", message)
        self.assertIn("Positioning revision", message)

    def test_emergency_stop_suppresses_without_calling_telegram(self) -> None:
        class Repository:
            def get(self, _lead_id): return {}
            def attempts(self, _lead_id): return []
            def record_attempt(self, _lead_id, **values): return values

        notifier = ExistingBotLeadNotifier(
            Repository(), bot_token="existing-token", owner_chat_id=42,
            allowed_chat_ids=frozenset({42}), emergency_stopped=lambda: True,
        )
        transport = SimpleNamespace(post=lambda *_args, **_kwargs: self.fail("Telegram must not be called"), TimeoutException=TimeoutError)
        with patch("owner_gateway.leads.httpx", transport):
            attempt = notifier.notify("lead")
        self.assertEqual("suppressed", attempt["status"])

    def test_failed_send_is_recorded_and_never_raises_to_visitor_path(self) -> None:
        lead = {
            "id": "lead", "form_id": "waitlist", "build_id": "build", "template_id": "waitlist",
            "positioning_project_id": "project", "positioning_revision_id": "revision",
            "submitted_at": "now", "fields": {"email": "test@example.com"},
        }
        class Repository:
            def get(self, _lead_id): return lead
            def attempts(self, _lead_id): return []
            def record_attempt(self, _lead_id, **values): return values

        def fail(*_args, **_kwargs):
            raise RuntimeError("network failed")
        notifier = ExistingBotLeadNotifier(
            Repository(), bot_token="existing-token", owner_chat_id=42,
            allowed_chat_ids=frozenset({42}), emergency_stopped=lambda: False,
        )
        transport = SimpleNamespace(post=fail, TimeoutException=TimeoutError)
        with patch("owner_gateway.leads.httpx", transport):
            attempt = notifier.notify("lead")
        self.assertEqual("failed", attempt["status"])
        self.assertEqual("RuntimeError", attempt["error_code"])
        self.assertNotIn("network failed", attempt["error_message"])


if __name__ == "__main__":
    unittest.main()
