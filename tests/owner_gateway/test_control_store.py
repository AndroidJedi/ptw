from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from owner_gateway.control_store import ControlStore


class ControlStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = ControlStore(Path(self.temp.name) / "control.sqlite3")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_plan_digest_is_immutable_and_approval_is_single_use(self) -> None:
        command = self.store.create_command("plan", "inspect health")
        digest = self.store.set_plan(command["id"], "1. Inspect\n2. Report")
        with self.assertRaises(ValueError):
            self.store.set_plan(command["id"], "changed plan")
        approved = self.store.approve_once(command["id"], digest, destructive_allowed=False)
        self.assertEqual(1, approved["execution_count"])
        with self.assertRaises(ValueError):
            self.store.approve_once(command["id"], digest, destructive_allowed=False)

    def test_destructive_plan_requires_explicit_gate(self) -> None:
        command = self.store.create_command("execute", "clean the environment")
        digest = self.store.set_plan(command["id"], "Recreate the exact public schema")
        self.assertTrue(self.store.command(command["id"])["destructive"])
        with self.assertRaises(PermissionError):
            self.store.approve_once(command["id"], digest, destructive_allowed=False)
        self.store.approve_once(command["id"], digest, destructive_allowed=True)

    def test_websocket_ticket_is_bound_single_use_and_short_lived(self) -> None:
        ticket = self.store.issue_ticket("owner", "/api/v1/root-sessions")
        self.assertEqual("owner", self.store.consume_ticket(ticket, "/api/v1/root-sessions"))
        with self.assertRaises(PermissionError):
            self.store.consume_ticket(ticket, "/api/v1/root-sessions")
