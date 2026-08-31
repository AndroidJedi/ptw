#!/usr/bin/env python3
"""Drain SKYNET's Telegram outbox through the existing outbound-only PTW bot."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import tempfile
from typing import Any
import urllib.error
import urllib.request


SCHEMA = "ptw.skynet.telegram-outbox.v1"
RECEIPT_SCHEMA = "ptw.skynet.telegram-receipt.v1"
EVENT_ID = re.compile(r"[a-z0-9][a-z0-9._-]{7,95}")
MAX_PHOTO_BYTES = 10 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _credentials() -> tuple[str, int]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    allowed: set[int] = set()
    for value in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(","):
        if value.strip():
            allowed.add(int(value.strip()))
    owner = int(os.environ.get("TELEGRAM_OWNER_CHAT_ID", "0"))
    if owner == 0 and allowed:
        owner = sorted(allowed)[0]
    if not token or not allowed or owner == 0 or owner not in allowed:
        raise RuntimeError("existing PTW bot and allowlisted owner chat are required")
    return token, owner


def _load_event(root: Path, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("outbox event is unreadable") from error
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("outbox event has an unsupported schema")
    event_id = str(value.get("event_id", ""))
    if EVENT_ID.fullmatch(event_id) is None or path.stem != event_id:
        raise ValueError("outbox event ID is invalid")
    text = value.get("text")
    if not isinstance(text, str) or "skynet" not in text.casefold():
        raise ValueError("outbox event must identify SKYNET")
    kind = value.get("kind")
    artifact = value.get("artifact")
    if kind == "text":
        if artifact is not None or not 1 <= len(text) <= 4_096:
            raise ValueError("text event is invalid")
    elif kind == "photo":
        if not isinstance(artifact, dict) or not 1 <= len(text) <= 1_024:
            raise ValueError("photo event is invalid")
        relative = Path(str(artifact.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("photo path escapes the SKYNET root")
        lexical = root / relative
        artifacts_root = root / "runtime" / "telegram" / "artifacts"
        if artifacts_root not in lexical.parents:
            raise ValueError("photo is outside the trusted artifact directory")
        cursor = root
        for part in lexical.relative_to(root).parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError("photo path must not contain symlinks")
        if not lexical.is_file():
            raise ValueError("photo is outside the trusted artifact directory")
        photo = lexical
        payload = photo.read_bytes()
        if not payload or len(payload) > MAX_PHOTO_BYTES:
            raise ValueError("photo size is invalid")
        if hashlib.sha256(payload).hexdigest() != artifact.get("sha256"):
            raise ValueError("photo digest does not match its outbox event")
        if len(payload) != artifact.get("byte_count"):
            raise ValueError("photo byte count does not match its outbox event")
        media_type = artifact.get("media_type")
        valid_png = media_type == "image/png" and payload.startswith(b"\x89PNG\r\n\x1a\n")
        valid_jpeg = (
            media_type == "image/jpeg"
            and payload.startswith(b"\xff\xd8")
            and payload.endswith(b"\xff\xd9")
        )
        if not valid_png and not valid_jpeg:
            raise ValueError("photo bytes do not match their declared media type")
        value["_photo_path"] = photo
    else:
        raise ValueError("outbox event kind is invalid")
    return value


def _multipart(fields: dict[str, str], photo: Path) -> tuple[bytes, str]:
    boundary = f"ptw-skynet-{secrets.token_hex(16)}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(),
            b"\r\n",
        ))
    media_type = mimetypes.guess_type(photo.name)[0] or "application/octet-stream"
    chunks.extend((
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="photo"; filename="{photo.name}"\r\n'.encode(),
        f"Content-Type: {media_type}\r\n\r\n".encode(),
        photo.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _send(token: str, chat_id: int, event: dict[str, Any]) -> int:
    method = "sendPhoto" if event["kind"] == "photo" else "sendMessage"
    if method == "sendPhoto":
        data, content_type = _multipart(
            {"chat_id": str(chat_id), "caption": event["text"]}, event["_photo_path"]
        )
    else:
        data = json.dumps({
            "chat_id": chat_id,
            "text": event["text"],
            "disable_web_page_preview": True,
        }).encode()
        content_type = "application/json"
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        headers={"Content-Type": content_type},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    if payload.get("ok") is not True:
        raise RuntimeError("existing PTW bot rejected the outbound event")
    return int(payload["result"]["message_id"])


def _receipt(event: dict[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "event_id": event["event_id"],
        "event_sha256": hashlib.sha256(
            json.dumps(
                {key: value for key, value in event.items() if not key.startswith("_")},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        "status": status,
        "recorded_at": _now(),
        **extra,
    }


def drain(root: Path, maximum_events: int = 20) -> list[dict[str, Any]]:
    root = root.resolve()
    runtime = root / "runtime" / "telegram"
    queue = runtime / "queue"
    sending = runtime / "sending"
    receipts = runtime / "receipts"
    sending.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for stale in sorted(sending.glob("*.json")):
        try:
            event = _load_event(root, stale)
            receipt = _receipt(event, "ambiguous", reason="sender interrupted after reservation")
        except ValueError:
            receipt = {
                "schema": RECEIPT_SCHEMA,
                "event_id": stale.stem,
                "status": "failed",
                "recorded_at": _now(),
                "reason": "reserved event became invalid",
            }
        _atomic_json(receipts / stale.name, receipt)
        stale.unlink(missing_ok=True)
        results.append(receipt)

    token, chat_id = _credentials()
    for queued in sorted(queue.glob("*.json"))[:maximum_events]:
        reserved = sending / queued.name
        try:
            queued.replace(reserved)
        except FileNotFoundError:
            continue
        try:
            event = _load_event(root, reserved)
        except ValueError as error:
            receipt = {
                "schema": RECEIPT_SCHEMA,
                "event_id": reserved.stem,
                "status": "failed",
                "recorded_at": _now(),
                "reason": str(error),
            }
        else:
            try:
                message_id = _send(token, chat_id, event)
            except urllib.error.HTTPError as error:
                receipt = _receipt(event, "failed", reason=f"Telegram HTTP {error.code}")
            except (OSError, TimeoutError, urllib.error.URLError):
                receipt = _receipt(event, "ambiguous", reason="Telegram transport outcome is unknown")
            except (KeyError, RuntimeError, TypeError, ValueError) as error:
                receipt = _receipt(event, "failed", reason=str(error))
            else:
                receipt = _receipt(event, "sent", telegram_message_id=message_id)
        _atomic_json(receipts / reserved.name, receipt)
        reserved.unlink(missing_ok=True)
        results.append(receipt)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--maximum-events", type=int, default=20)
    arguments = parser.parse_args()
    if not 1 <= arguments.maximum_events <= 100:
        raise SystemExit("maximum events must be between 1 and 100")
    try:
        results = drain(arguments.root, arguments.maximum_events)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from None
    counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1
    print("Telegram outbox drained: " + ", ".join(
        f"{status}={count}" for status, count in sorted(counts.items())
    ) if counts else "Telegram outbox is empty")


if __name__ == "__main__":
    main()
