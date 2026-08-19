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

    def test_only_one_heavy_codex_operation_can_be_active(self) -> None:
        first = self.store.create_command("plan", "inspect production")
        with self.assertRaisesRegex(ValueError, first["id"]):
            self.store.create_command("execute", "change production")
        first_digest = self.store.set_plan(first["id"], "1. Report")
        second = self.store.create_command("plan", "inspect after approval wait")
        self.assertEqual("planning", second["status"])
        self.assertEqual(second["id"], self.store.active_command()["id"])
        with self.assertRaisesRegex(ValueError, second["id"]):
            self.store.approve_once(first["id"], first_digest, destructive_allowed=False)

    def test_restart_fails_stale_active_commands_and_releases_the_guard(self) -> None:
        command = self.store.create_command("plan", "stale process")
        recovered = self.store.recover_interrupted_commands()
        self.assertEqual(command["id"], recovered[0]["id"])
        self.assertEqual("failed", self.store.command(command["id"])["status"])
        self.assertIsNone(self.store.active_command())
        replacement = self.store.create_command("plan", "fresh process")
        self.assertEqual("planning", replacement["status"])

    def test_websocket_ticket_is_bound_single_use_and_short_lived(self) -> None:
        ticket = self.store.issue_ticket("owner", "/api/v1/root-sessions")
        self.assertEqual("owner", self.store.consume_ticket(ticket, "/api/v1/root-sessions"))
        with self.assertRaises(PermissionError):
            self.store.consume_ticket(ticket, "/api/v1/root-sessions")
