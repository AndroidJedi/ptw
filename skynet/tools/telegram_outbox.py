#!/usr/bin/env python3
"""Queue one outbound-only SKYNET Telegram event without access to credentials."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


SCHEMA = "ptw.skynet.telegram-outbox.v1"
EVENT_ID = re.compile(r"[a-z0-9][a-z0-9._-]{7,95}")
MAX_PHOTO_BYTES = 10 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise FileExistsError(f"Telegram event already exists: {path.stem}")
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _photo_metadata(path: Path) -> tuple[bytes, str]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("photo must be one regular file")
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_PHOTO_BYTES:
        raise ValueError("photo must contain 1 byte to 10 MiB")
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        suffix = ".png"
    elif payload.startswith(b"\xff\xd8") and payload.endswith(b"\xff\xd9"):
        suffix = ".jpg"
    else:
        raise ValueError("photo must be a valid-looking PNG or JPEG")
    return payload, suffix


def _regular_file_below(root: Path, path: Path) -> Path:
    root = root.resolve()
    absolute = Path(os.path.abspath(path))
    lexical = absolute.parent.resolve() / absolute.name
    if root != lexical and root not in lexical.parents:
        raise ValueError("photo must be inside the SKYNET root")
    cursor = root
    for part in lexical.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("photo path must not contain symlinks")
    if not lexical.is_file():
        raise ValueError("photo must be one regular file")
    return lexical


def enqueue(root: Path, event_id: str, text: str, photo: Path | None) -> Path:
    root = root.resolve()
    if EVENT_ID.fullmatch(event_id) is None:
        raise ValueError("event ID must be 8-96 lowercase letters, digits, dots, dashes, or underscores")
    normalized = text.strip()
    if "skynet" not in normalized.casefold():
        raise ValueError("Telegram text must identify SKYNET")
    maximum = 1_024 if photo else 4_096
    if not 1 <= len(normalized) <= maximum:
        raise ValueError(f"Telegram text must contain 1-{maximum} characters")

    runtime = root / "runtime" / "telegram"
    queue_path = runtime / "queue" / f"{event_id}.json"
    known_paths = (
        queue_path,
        runtime / "sending" / f"{event_id}.json",
        runtime / "receipts" / f"{event_id}.json",
    )
    if any(path.exists() for path in known_paths):
        raise FileExistsError(f"Telegram event already exists: {event_id}")

    artifact: dict[str, object] | None = None
    if photo is not None:
        payload, suffix = _photo_metadata(_regular_file_below(root, photo))
        artifact_path = runtime / "artifacts" / f"{event_id}{suffix}"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(artifact_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise FileExistsError(f"Telegram artifact already exists: {event_id}") from error
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        artifact = {
            "path": artifact_path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
            "media_type": "image/png" if suffix == ".png" else "image/jpeg",
        }

    record: dict[str, object] = {
        "schema": SCHEMA,
        "event_id": event_id,
        "created_at": _now(),
        "kind": "photo" if artifact else "text",
        "text": normalized,
        "artifact": artifact,
    }
    try:
        _atomic_json(queue_path, record)
    except Exception:
        if artifact:
            (root / str(artifact["path"])).unlink(missing_ok=True)
        raise
    return queue_path


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    value.add_argument("--event-id", required=True)
    value.add_argument("--text", required=True)
    value.add_argument("--photo", type=Path)
    return value


def main() -> None:
    arguments = parser().parse_args()
    try:
        path = enqueue(arguments.root, arguments.event_id, arguments.text, arguments.photo)
    except (FileExistsError, OSError, ValueError) as error:
        raise SystemExit(str(error)) from None
    print(f"queued {arguments.event_id} at {path.relative_to(arguments.root.resolve())}")


if __name__ == "__main__":
    main()
