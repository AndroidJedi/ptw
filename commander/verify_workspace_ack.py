"""Post-restart probe for the durable Codex-workspace acknowledgement bridge."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request


def _request(url: str, token: str, *, body: dict[str, object] | None = None) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body).encode(),
        headers={
            "X-PTW-Bridge-Token": token,
            "Content-Type": "application/json",
        },
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Commander returned HTTP {error.code}: {detail}") from error


def verify(
    *,
    base_url: str,
    token: str,
    task_id: str,
    scope: str,
    session_id: str,
    chat_id: int,
    timeout_seconds: float,
) -> int:
    endpoint = f"{base_url.rstrip('/')}/internal/workspace/tasks"
    _request(
        endpoint,
        token,
        body={
            "task_id": task_id,
            "interpreted_scope": scope,
            "workspace_session_id": session_id,
            "chat_id": chat_id,
        },
    )
    deadline = time.monotonic() + timeout_seconds
    status_url = f"{endpoint}/{task_id}/acknowledgement"
    while time.monotonic() < deadline:
        result = _request(status_url, token)
        if result.get("may_start") is True and result.get("telegram_message_id") is not None:
            print(f"{task_id} acknowledged after restart; Telegram message ID recorded")
            return 0
        time.sleep(1)
    raise RuntimeError(f"{task_id} was not acknowledged within {timeout_seconds:g} seconds")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register a post-restart probe and wait for real Telegram delivery"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8091")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--chat-id", required=True, type=int)
    parser.add_argument("--timeout-seconds", type=float, default=60)
    args = parser.parse_args()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        parser.error("TELEGRAM_BOT_TOKEN must be present in the environment")
    raise SystemExit(
        verify(
            base_url=args.base_url,
            token=token,
            task_id=args.task_id,
            scope=args.scope,
            session_id=args.session_id,
            chat_id=args.chat_id,
            timeout_seconds=args.timeout_seconds,
        )
    )


if __name__ == "__main__":
    main()
