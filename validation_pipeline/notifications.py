"""Bounded callback for existing-bot generation failure notifications."""

from __future__ import annotations

import json
from typing import Any, Mapping
import urllib.request


class FailureNotificationClient:
    """Make one authenticated callback; Telegram delivery stays in Owner Gateway."""

    def __init__(self, url: str, token: str, *, timeout_seconds: int = 30) -> None:
        if not url or not token:
            raise RuntimeError("the Owner Gateway failure notification callback is required")
        self.url = url
        self.token = token
        self.timeout_seconds = timeout_seconds

    def notify(self, *, target_id: str, attempt_id: str, stage: str) -> Mapping[str, Any]:
        payload = json.dumps(
            {"target_id": target_id, "attempt_id": attempt_id, "stage": stage}
        ).encode()
        request = urllib.request.Request(
            self.url,
            data=payload,
            headers={
                "X-PTW-Owner-Gateway-Token": self.token,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            value = json.loads(response.read())
        if not isinstance(value, Mapping) or value.get("status") not in {
            "sent", "failed", "ambiguous", "suppressed", "already_reserved",
        }:
            raise RuntimeError("Owner Gateway returned an invalid notification result")
        return value
