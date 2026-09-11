import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.verify_ptw_migration_inventory import inventory, validate
from scripts.ptw_migration_contracts import contracts


class MigrationContractsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "db/migrations").mkdir(parents=True)
        (self.repo / "db/migrations/001_initial.sql").write_text("SELECT 1;\n")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-qm", "Baseline"], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_append_inventory_and_applied_checksum(self):
        applied = inventory(self.repo)
        (self.repo / "db/migrations/002_next.sql").write_text("SELECT 2;\n")
        self.assertEqual(["002_next.sql"], validate(self.repo, applied, "HEAD")[1])
        (self.repo / "db/migrations/001_initial.sql").write_text("SELECT 3;\n")
        with self.assertRaisesRegex(ValueError, "modified"):
            validate(self.repo, applied, "HEAD")

    def test_legacy_ledger_uses_accepted_bytes(self):
        applied = {"001_initial.sql": None}
        self.assertFalse(validate(self.repo, applied, "HEAD")[1])
        (self.repo / "db/migrations/001_initial.sql").write_text("SELECT 3;\n")
        with self.assertRaises(ValueError):
            validate(self.repo, applied, "HEAD")

    def test_declared_transformations_keep_other_values_and_require_rollback_check(self):
        baseline = {"items": ["id", "label", "owner"]}
        self.assertEqual((baseline, []), contracts(self.repo, ["002_next.sql"], baseline))
        folder = self.repo / "db/migration-contracts"
        folder.mkdir()
        check = self.repo / "db/migration-checks/check.sql"
        check.parent.mkdir()
        check.write_text("SELECT true;\n")
        path = folder / "002_next.sql.json"
        value = {"transformed_columns": {"items": ["label"]}, "verify": "db/migration-checks/check.sql", "rollback_verify": "db/migration-checks/check.sql"}
        path.write_text(json.dumps(value))
        projection, checks = contracts(self.repo, ["002_next.sql"], baseline)
        self.assertEqual(["id", "owner"], projection["items"])
        self.assertEqual(2, len(checks))
        value.pop("rollback_verify")
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            contracts(self.repo, ["002_next.sql"], baseline)
