from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from skynet.tools.reconcile_triggers import capture
from skynet.tools.telegram_outbox import enqueue


class TriggerReconciliationTests(unittest.TestCase):
    def test_unchanged_snapshot_is_stable_and_not_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = root / ".local" / "owner-experiments" / "store.json"
            store.parent.mkdir(parents=True)
            store.write_text(json.dumps({
                "schema": "ptw.local-owner-experiment-store.v1",
                "created_at": "2026-08-31T00:00:00Z",
            }))
            enqueue(root, "skynet.trigger-test", "SKYNET · trigger test", None)
            first = capture(root)
            second = capture(root, first)
            self.assertEqual(first["evidence_fingerprint"], second["evidence_fingerprint"])
            self.assertFalse(second["changed_since_previous_snapshot"])
            self.assertFalse(second["actionable_local_trigger_present"])
            self.assertEqual({"queue": 1, "sending": 0, "receipts": 0}, second["telegram_counts"])

    def test_receipt_and_owner_record_are_actionable_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queued = enqueue(root, "skynet.receipt-test", "SKYNET · receipt test", None)
            first = capture(root)
            receipt = root / "runtime" / "telegram" / "receipts" / queued.name
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({
                "schema": "ptw.skynet.telegram-receipt.v1",
                "event_id": "skynet.receipt-test",
                "status": "sent",
                "recorded_at": "2026-08-31T00:00:01Z",
            }))
            queued.unlink()
            store = root / ".local" / "owner-experiments" / "store.json"
            store.parent.mkdir(parents=True)
            store.write_text(json.dumps({
                "schema": "ptw.local-owner-experiment-store.v1",
                "feedback": [{"candidate_id": "cand-test", "result": "winner"}],
            }))
            second = capture(root, first)
            self.assertTrue(second["changed_since_previous_snapshot"])
            self.assertTrue(second["actionable_local_trigger_present"])
            self.assertEqual(["sent"], second["receipt_statuses"])
            self.assertTrue(second["owner_store"]["potential_feedback_present"])

    def test_explicit_authority_record_is_actionable_without_secret_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = root / "state" / "approved-media.json"
            record.parent.mkdir(parents=True)
            record.write_text(json.dumps({
                "schema": "ptw.skynet.approved-media.v1",
                "assets": [],
            }))
            result = capture(root)
            self.assertTrue(result["actionable_local_trigger_present"])
            self.assertEqual("state/approved-media.json", result["authority_records"][0]["path"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_owner_store_cannot_escape_through_parent_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, tempfile.TemporaryDirectory() as outside:
            root = Path(temporary)
            external = Path(outside) / "owner-experiments"
            external.mkdir()
            (external / "store.json").write_text(json.dumps({"feedback": []}))
            local = root / ".local"
            local.mkdir()
            (local / "owner-experiments").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "must not contain symlinks"):
                capture(root)


if __name__ == "__main__":
    unittest.main()
