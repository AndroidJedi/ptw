#!/usr/bin/env python3
"""Check ordered migration inventory against its applied checksum ledger."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def inventory(repository):
    result = {}
    for path in sorted((repository / "db/migrations").glob("*.sql")):
        if not re.fullmatch(r"[0-9]+_[a-zA-Z0-9_.-]+\.sql", path.name):
            raise ValueError("Invalid migration name")
        result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not result:
        raise ValueError("Migration inventory is empty")
    return result


def validate(repository, applied, base):
    expected = inventory(repository)
    for name, digest in applied.items():
        if name not in expected:
            raise ValueError("An applied migration was removed: " + name)
        previous = subprocess.check_output(["git", "-C", str(repository), "show", f"{base}:db/migrations/{name}"])
        accepted = hashlib.sha256(previous).hexdigest()
        if expected[name] != accepted or (digest and digest != accepted):
            raise ValueError("An applied migration was modified: " + name)
    pending = [name for name in expected if name not in applied]
    if applied and any(name <= max(applied) for name in pending):
        raise ValueError("New migrations must append to the ordered inventory")
    return expected, pending


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    command = ["docker", "exec", "-i", "ptw-commander-db-1", "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "ptw_commander", "-d", "ptw_commander"]
    raw = subprocess.check_output(command + ["-c", "SELECT coalesce(jsonb_object_agg(name,to_jsonb(m)->>'sha256'),'{}') FROM commander_schema_migrations m"], text=True)
    expected, pending = validate(args.repository, json.loads(raw), args.base)
    # Seed legacy checksums from the accepted revision, not untrusted new bytes.
    sql = "BEGIN; ALTER TABLE commander_schema_migrations ADD COLUMN IF NOT EXISTS sha256 text;\n"
    for name, digest in expected.items():
        sql += f"UPDATE commander_schema_migrations SET sha256='{digest}' WHERE name='{name}' AND sha256 IS NULL;\n"
    sql += "COMMIT;"
    subprocess.run(command, input=sql, text=True, check=True, stdout=subprocess.DEVNULL)
    print(json.dumps({"applied": len(expected) - len(pending), "pending": pending}))
