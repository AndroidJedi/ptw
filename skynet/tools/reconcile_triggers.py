#!/usr/bin/env python3
"""Snapshot local evidence that can legitimately change SKYNET's next action."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


SCHEMA = "ptw.skynet.external-trigger-snapshot.v1"
TELEGRAM_STAGES = ("queue", "sending", "receipts")
OPTIONAL_AUTHORITY_RECORDS = (
    "state/approved-media.json",
    "state/provider-authorizations.json",
    ".local/approved-media.json",
    ".local/provider-authorizations.json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: Any) -> str:
    return _sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode())


def _root_confined_path(root: Path, path: Path) -> Path:
    lexical = Path(os.path.abspath(path))
    if root != lexical and root not in lexical.parents:
        raise ValueError("trigger path must stay inside the SKYNET root")
    cursor = root
    for part in lexical.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"trigger path must not contain symlinks: {lexical.relative_to(root)}")
    return lexical


def _read_json_file(root: Path, relative: str) -> dict[str, Any] | None:
    path = _root_confined_path(root, root / relative)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"trigger record must be one regular file: {relative}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"trigger record must contain one JSON object: {relative}")
    return value


def _file_record(root: Path, path: Path, stage: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Telegram {stage} record must be one regular file: {path.name}")
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"Telegram {stage} record must contain one JSON object: {path.name}")
    record: dict[str, Any] = {
        "event_id": str(value.get("event_id", path.stem)),
        "path": path.relative_to(root).as_posix(),
        "record_sha256": _sha256(payload),
        "stage": stage,
    }
    if stage == "receipts":
        record["status"] = value.get("status")
        record["recorded_at"] = value.get("recorded_at")
    artifact = value.get("artifact")
    if isinstance(artifact, dict) and isinstance(artifact.get("sha256"), str):
        record["artifact_sha256"] = artifact["sha256"]
    return record


def _owner_store_summary(root: Path) -> dict[str, Any]:
    relative = ".local/owner-experiments/store.json"
    value = _read_json_file(root, relative)
    if value is None:
        return {"path": relative, "present": False}
    payload = (root / relative).read_bytes()
    non_metadata_keys = sorted(set(value) - {"schema", "created_at", "updated_at"})
    return {
        "path": relative,
        "present": True,
        "record_sha256": _sha256(payload),
        "non_metadata_keys": non_metadata_keys,
        "potential_feedback_present": bool(non_metadata_keys),
    }


def _authority_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for relative in OPTIONAL_AUTHORITY_RECORDS:
        value = _read_json_file(root, relative)
        if value is not None:
            records.append({
                "path": relative,
                "record_sha256": _sha256((root / relative).read_bytes()),
                "schema": value.get("schema"),
            })
    return records


def capture(root: Path, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    root = root.resolve()
    telegram: list[dict[str, Any]] = []
    counts = {stage: 0 for stage in TELEGRAM_STAGES}
    for stage in TELEGRAM_STAGES:
        directory = _root_confined_path(root, root / "runtime" / "telegram" / stage)
        if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
            raise ValueError(f"Telegram {stage} path must be one real directory")
        if directory.is_dir():
            for path in sorted(directory.glob("*.json")):
                telegram.append(_file_record(root, path, stage))
                counts[stage] += 1

    owner_store = _owner_store_summary(root)
    authority_records = _authority_records(root)
    evidence = {
        "telegram": telegram,
        "telegram_counts": counts,
        "owner_store": owner_store,
        "authority_records": authority_records,
    }
    fingerprint = _canonical_sha256(evidence)
    previous_fingerprint = None if previous is None else previous.get("evidence_fingerprint")
    changed = None if previous_fingerprint is None else previous_fingerprint != fingerprint
    receipt_statuses = sorted({
        str(record.get("status"))
        for record in telegram
        if record["stage"] == "receipts"
    })
    return {
        "schema": SCHEMA,
        "captured_at": _now(),
        "evidence_fingerprint": fingerprint,
        "previous_evidence_fingerprint": previous_fingerprint,
        "changed_since_previous_snapshot": changed,
        "actionable_local_trigger_present": bool(
            counts["sending"]
            or counts["receipts"]
            or owner_store.get("potential_feedback_present")
            or authority_records
        ),
        "receipt_statuses": receipt_statuses,
        **evidence,
        "limits": [
            "This snapshot reads local durable records only and never polls Telegram.",
            "Absence of a local authorization record does not inspect or infer secrets.",
            "A record is a trigger for reconciliation, not automatic authorization to publish or mutate external systems.",
        ],
    }


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == payload:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    value.add_argument("--output", type=Path, default=Path("state/external-trigger-snapshot.json"))
    return value


def main() -> None:
    arguments = parser().parse_args()
    root = arguments.root.resolve()
    output = arguments.output if arguments.output.is_absolute() else root / arguments.output
    try:
        output = _root_confined_path(root, output)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    previous = None
    if output.exists():
        try:
            previous = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"previous trigger snapshot is unreadable: {error}") from None
    try:
        result = capture(root, previous)
        if (
            previous is not None
            and previous.get("evidence_fingerprint") == result["evidence_fingerprint"]
        ):
            result["captured_at"] = previous.get("captured_at", result["captured_at"])
        _atomic_json(output, result)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps({
        "actionable_local_trigger_present": result["actionable_local_trigger_present"],
        "changed_since_previous_snapshot": result["changed_since_previous_snapshot"],
        "evidence_fingerprint": result["evidence_fingerprint"],
        "telegram_counts": result["telegram_counts"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
