#!/usr/bin/env python3
"""Bound declared migration transformations and verify them on clone and live DB."""
import json
from pathlib import Path
import re
import subprocess
import sys


def contracts(repository, pending, baseline):
    projection = {table: list(columns) for table, columns in baseline.items()}
    checks = []
    for name in pending:
        path = repository / "db/migration-contracts" / (name + ".json")
        if not path.exists():
            continue  # Undeclared migrations must preserve every existing value.
        contract = json.loads(path.read_text())
        if set(contract) != {"transformed_columns", "verify", "rollback_verify"}:
            raise ValueError("Migration contract must declare transformations and both verification checks")
        for table, columns in contract["transformed_columns"].items():
            if table not in baseline or not isinstance(columns, list) or not set(columns) <= set(baseline[table]):
                raise ValueError("Transformation names unknown existing columns")
            projection[table] = [column for column in projection[table] if column not in columns]
            if not projection[table]:
                raise ValueError("Transformations must retain a stable identity projection")
        for kind in ("verify", "rollback_verify"):
            relative = contract[kind]
            if not isinstance(relative, str) or not re.fullmatch(r"db/migration-checks/[a-zA-Z0-9_.-]+\.sql", relative):
                raise ValueError("Verification must name a bounded SQL check")
            check = repository / relative
            if check.is_symlink() or not check.is_file() or check.stat().st_size > 65536:
                raise ValueError("Invalid migration verification file")
            checks.append(relative)
    return projection, checks


def main():
    action, repo, directory, *rest = sys.argv[1:]
    repository, backup = Path(repo), Path(directory)
    if str(repository) != "/root/ptw" or not str(backup).startswith("/opt/ptw/backups/commander/migration."):
        raise SystemExit(2)
    database = rest[0] if rest else "ptw_commander"
    if database != "ptw_commander" and not re.fullmatch(r"ptw_rehearsal_[0-9]+_[0-9]+", database):
        raise SystemExit(2)
    command = ["docker", "exec", "-i", "ptw-commander-db-1", "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "ptw_commander", "-d", database]
    if action == "prepare":
        applied = subprocess.check_output(command + ["-c", "SELECT name FROM commander_schema_migrations ORDER BY name"], text=True).splitlines()
        pending = [p.name for p in sorted((repository / "db/migrations").glob("*.sql")) if p.name not in applied]
        projection, checks = contracts(repository, pending, json.loads((backup / "schema.json").read_text()))
        (backup / "schema.json").write_text(json.dumps(projection))
        (backup / "checks.json").write_text(json.dumps(checks))
    elif action == "verify":
        for check in json.loads((backup / "checks.json").read_text()):
            sql = "BEGIN TRANSACTION READ ONLY;\n" + (repository / check).read_text() + "\nROLLBACK;"
            result = subprocess.check_output(command, input=sql, text=True).strip()
            if result != "t":
                raise ValueError("Migration transformation or previous-runtime compatibility check failed: " + check)
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
