from __future__ import annotations

import os
import unittest
from uuid import uuid4

from owner_gateway.validation_notifications import (
    ExistingBotValidationFailureNotifier,
    ValidationFailureNotificationRepository,
)
from validation_pipeline.domain import ProductBriefV1
from validation_pipeline.repository import ValidationRepository


DATABASE_URL = os.environ.get("PTW_VALIDATION_TEST_DATABASE_URL", "")


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True, "result": {"message_id": 91}}


@unittest.skipUnless(DATABASE_URL, "PTW_VALIDATION_TEST_DATABASE_URL is required")
class ValidationFailureNotificationIntegrationTests(unittest.TestCase):
    def test_failed_batch_is_reserved_sent_recorded_and_never_repeated(self) -> None:
        validation = ValidationRepository(DATABASE_URL)
        brief, _ = validation.create_brief(
            request_id=str(uuid4()),
            raw_idea="Online psychologist consultations",
            requested_by="integration-owner",
        )
        brief_attempt, _ = validation.start_attempt(brief["brief_id"], stage="product_brief")
        document = {
            "schema_version": 1,
            "language": "en",
            "product": "Online psychologist consultations.",
            "target_audience": "First-time therapy seekers.",
            "main_pain": "Starting support feels risky.",
            "promise": "Take a trustworthy first step.",
            "key_benefits": ["Real profiles", "Easy booking", "Low-risk start"],
            "cta": "Get free consultation",
            "trust_strategy": "Real consultants and clear pricing.",
            "offer": "First consultation free.",
        }
        value = ProductBriefV1.from_dict(document, raw_idea="Online psychologist consultations")
        validation.finish_brief(
            brief["brief_id"], brief_attempt, value.to_dict(), value.digest, value.quality_gates
        )
        batch, _ = validation.approve_and_queue_batch(brief["brief_id"], "integration-owner")
        attempt_id, _ = validation.start_attempt(batch["batch_id"], stage="ad_creative_batch")
        validation.fail_attempt(
            batch["batch_id"],
            attempt_id,
            stage="ad_creative_batch",
            error=ValueError("creative 3 offer wording failed"),
        )
        validation.release_operation(batch["batch_id"])

        calls = []
        notifier = ExistingBotValidationFailureNotifier(
            ValidationFailureNotificationRepository(DATABASE_URL),
            bot_token="fixture-token",
            owner_chat_id=9,
            allowed_chat_ids=frozenset({9}),
            owner_console_url="https://console.example",
            post=lambda *args, **kwargs: calls.append((args, kwargs)) or Response(),
        )
        first = notifier.notify(batch["batch_id"], attempt_id, "ad_creative_batch")
        second = notifier.notify(batch["batch_id"], attempt_id, "ad_creative_batch")

        self.assertEqual("sent", first["status"])
        self.assertEqual("already_reserved", second["status"])
        self.assertEqual(1, len(calls))
        notification = validation.get_batch(batch["batch_id"])["failure_notification"]
        self.assertEqual("sent", notification["status"])
        self.assertEqual(attempt_id, notification["attempt_id"])


if __name__ == "__main__":
    unittest.main()
