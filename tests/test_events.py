from common.events import _safe_payload


def test_event_payload_redacts_secret_fields_recursively() -> None:
    payload = {
        "command": "/ping",
        "nested": {"telegram_bot_token": "do-not-store"},
        "items": [{"password": "do-not-store"}],
    }
    assert _safe_payload(payload) == {
        "command": "/ping",
        "nested": {"telegram_bot_token": "[REDACTED]"},
        "items": [{"password": "[REDACTED]"}],
    }
