#!/usr/bin/env python3
"""Exercise Brief V1/V2/V3 persistence against a disposable local PostgreSQL only.

Run with .venv/bin/python scripts/verify_brief_brand_migration.py (Docker needed).
Uses scripted inference; never connects to an existing database or publishes.
"""
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.validation_pipeline.test_local_briefs import FakeProvider
from validation_pipeline.marketing import generation_settings
from validation_pipeline.repository import ValidationRepository
from validation_pipeline.service import ValidationRunner


def main():
    name = "ptw-brand-canary-" + uuid4().hex[:12]
    subprocess.run(["docker", "run", "--rm", "-d", "--name", name,
                    "-e", "POSTGRES_PASSWORD=disposable-only", "-p", "127.0.0.1::5432",
                    "postgres:16-alpine"], check=True, stdout=subprocess.DEVNULL)
    try:
        port = subprocess.check_output(["docker", "port", name, "5432"], text=True).strip().rsplit(":", 1)[1]
        dsn = f"postgresql://postgres:disposable-only@127.0.0.1:{port}/postgres"
        for _ in range(60):
            try:
                with psycopg.connect(dsn):
                    break
            except psycopg.OperationalError:
                time.sleep(0.25)
        else:
            raise RuntimeError("Disposable PostgreSQL did not start")
        for migration in sorted((ROOT / "db/migrations").glob("*.sql")):
            if migration.name >= "021_":
                continue
            with psycopg.connect(dsn) as connection:
                connection.execute(migration.read_text())
        repo = ValidationRepository(dsn)
        old_settings = {**generation_settings("identity_led"), "output_schema_version": 2}
        project, _ = repo.create_project(request_id=str(uuid4()), name="Private migration trial", requested_by="test")
        request = dict(project_id=project["project_id"], request_id=str(uuid4()), raw_idea="Daily planner", required_language="en", requested_by="test", marketing_approach="identity_led")
        with patch("validation_pipeline.repository.generation_settings", return_value=old_settings):
            old, _ = repo.create_brief(**request)
        # An already-reserved historical V1 correction has NULL settings.
        legacy_id, feedback_id = str(uuid4()), str(uuid4())
        with psycopg.connect(dsn) as connection:
            connection.execute("INSERT INTO commander_entities(id,kind) VALUES(%s,'product_brief')", (legacy_id,))
            connection.execute("INSERT INTO commander_entities(id,kind) VALUES(%s,'human_feedback')", (feedback_id,))
            connection.execute("""INSERT INTO commander_human_feedback(entity_id,target_id,domain,section_id,instruction,actor)
                VALUES(%s,%s,'product_brief','product_brief','Clarify the promise','test')""", (feedback_id, old["brief_id"]))
            connection.execute("""INSERT INTO product_briefs(entity_id,project_id,request_id,owner_idea_source_id,
                base_brief_id,feedback_id,status,requested_by) VALUES(%s,%s,%s,%s,%s,%s,'queued','test')""",
                (legacy_id, project["project_id"], str(uuid4()), old["owner_idea_source_id"], old["brief_id"], feedback_id))
            before = connection.execute("SELECT to_jsonb(b) FROM product_briefs b ORDER BY entity_id").fetchall()
            connection.execute((ROOT / "db/migrations/021_brief_brand_identity.sql").read_text())
            assert before == connection.execute("SELECT to_jsonb(b) FROM product_briefs b ORDER BY entity_id").fetchall()
        runner = ValidationRunner(repo, FakeProvider(), product_brief_skill_path=ROOT / "skills/product-brief-generator/SKILL.md")
        assert runner.generate_brief(old["brief_id"])["document"]["schema_version"] == 2
        assert runner.generate_brief(legacy_id)["document"]["schema_version"] == 1
        saved_old = repo.get_brief(old["brief_id"])
        correction = dict(request_id=str(uuid4()), instruction="Develop the brand identity", requested_by="test")
        new, _ = repo.create_revision(old["brief_id"], **correction)
        assert new["generation_settings"]["output_schema_version"] == 3
        assert repo.create_revision(old["brief_id"], **correction)[0]["brief_id"] == new["brief_id"]
        generated = runner.generate_brief(new["brief_id"])
        assert generated["document"]["brand_identity"]["belief"]
        assert not generated["approved"]
        assert saved_old == repo.get_brief(old["brief_id"])
        assert generated["document"] == ValidationRepository(dsn).get_brief(new["brief_id"])["document"]
        for brief_id in (legacy_id, old["brief_id"], new["brief_id"]):
            try:
                with psycopg.connect(dsn) as connection:
                    connection.execute("UPDATE product_briefs SET generation_settings=%s WHERE entity_id=%s",
                                       (Jsonb(generation_settings("benefit_led")), brief_id))
            except psycopg.errors.RaiseException as error:
                assert "immutable" in str(error)
            else:
                raise AssertionError("Brief settings were mutable")
        assert repo.create_brief(**request)[0]["generation_settings"] == old_settings
        try:
            repo.create_brief(**{**request, "marketing_approach": "benefit_led"})
        except ValueError:
            pass
        else:
            raise AssertionError("Duplicate request accepted another approach")
        print("Disposable PostgreSQL: historical rows unchanged; V1/V2 reservations, V3 correction, duplicate identity, restart reads and immutability passed.")
    finally:
        subprocess.run(["docker", "stop", name], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
