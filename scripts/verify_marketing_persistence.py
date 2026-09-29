#!/usr/bin/env python3
"""Exercise migration and repository behavior exclusively in a disposable DB."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import psycopg
from validation_pipeline.repository import ValidationRepository
from validation_pipeline.service import ValidationRunner
from tests.validation_pipeline.test_local_briefs import FakeProvider, BRIEF


def main():
    name = "ptw-marketing-test-" + uuid4().hex[:10]
    subprocess.run(["docker", "run", "--rm", "-d", "--name", name,
                    "-p", "127.0.0.1::5432", "-e", "POSTGRES_DB=ptw_marketing_test",
                    "-e", "POSTGRES_USER=ptw_test", "-e", "POSTGRES_PASSWORD=disposable-test-only",
                    "postgres:16-alpine"], check=True, stdout=subprocess.DEVNULL)
    try:
        port = subprocess.check_output(["docker", "port", name, "5432"], text=True).strip().rsplit(":", 1)[1]
        dsn = f"postgresql://ptw_test:disposable-test-only@127.0.0.1:{port}/ptw_marketing_test"
        for _ in range(40):
            try:
                with psycopg.connect(dsn):
                    break
            except psycopg.OperationalError:
                time.sleep(.25)
        with psycopg.connect(dsn) as connection:
            for migration in sorted((ROOT / "db/migrations").glob("*.sql")):
                if migration.name.startswith("020_"):
                    continue
                connection.execute(migration.read_text())
            # Simulate a queued historical reservation before applying the extension.
            project, source, brief, request = [uuid4() for _ in range(4)]
            for identifier, kind in ((project, "validation_project"), (source, "source"), (brief, "product_brief")):
                connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,%s,'{}')", (identifier, kind))
            connection.execute("INSERT INTO commander_sources(entity_id,source_type,title,provider,external_id,content,content_sha256,metadata) VALUES(%s,'owner_idea','Test','owner','test','Planner',%s,'{\"required_language\":\"en\"}')", (source, "a" * 64))
            connection.execute("INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by) VALUES(%s,%s,%s,'Legacy','owner','test')", (project, uuid4(), source))
            connection.execute("INSERT INTO product_briefs(entity_id,project_id,request_id,owner_idea_source_id,status,requested_by) VALUES(%s,%s,%s,%s,'queued','test')", (brief, project, request, source))
            connection.execute((ROOT / "db/migrations/020_brief_marketing_approaches.sql").read_text())
        repository = ValidationRepository(dsn)
        runner = ValidationRunner(repository, FakeProvider(), product_brief_skill_path=ROOT / "skills/product-brief-generator/SKILL.md")
        legacy = runner.generate_brief(str(brief))
        assert legacy["generation_settings"] is None and legacy["document"] == BRIEF
        project, _ = repository.create_project(request_id=str(uuid4()), name="Marketing", requested_by="test")
        request = dict(project_id=project["project_id"], request_id=str(uuid4()), raw_idea="Planner",
                       required_language="en", requested_by="test", marketing_approach="identity_led")
        with ThreadPoolExecutor(max_workers=2) as pool:
            records = list(pool.map(lambda _: repository.create_brief(**request), range(2)))
        assert sum(created for _, created in records) == 1
        queued = records[0][0]
        completed = runner.generate_brief(queued["brief_id"])
        assert completed["document"]["positioning"]["marketing_approach"] == "identity_led"
        assert ValidationRepository(dsn).get_brief(queued["brief_id"]) == completed
        for update in ("generation_settings=NULL", "document='{}'"):
            try:
                with psycopg.connect(dsn) as connection:
                    connection.execute(f"UPDATE product_briefs SET {update} WHERE entity_id=%s", (queued["brief_id"],))
            except psycopg.errors.RaiseException:
                pass
            else:
                raise AssertionError("Immutable record changed")
        for changes in ({"marketing_approach": "benefit_led"}, {"raw_idea": "Other idea"}):
            try:
                repository.create_brief(**{**request, **changes})
            except ValueError:
                pass
            else:
                raise AssertionError("Conflicting request was accepted")
        correction = dict(request_id=str(uuid4()), instruction="Use the selected approach", requested_by="test", marketing_approach="benefit_led")
        with ThreadPoolExecutor(max_workers=2) as pool:
            replacements = list(pool.map(lambda _: repository.create_revision(queued["brief_id"], **correction), range(2)))
        assert sum(created for _, created in replacements) == 1
        with patch("validation_pipeline.repository.correction_settings", side_effect=AssertionError("duplicate must reuse the reservation")):
            repeated, created = repository.create_revision(queued["brief_id"], **correction)
            assert not created and repeated["brief_id"] == replacements[0][0]["brief_id"]
        replacement = runner.generate_brief(replacements[0][0]["brief_id"])
        assert replacement["document"]["positioning"]["marketing_approach"] == "benefit_led" and not replacement["approved"]
        assert repository.get_brief(queued["brief_id"]) == completed
        with psycopg.connect(dsn) as connection:
            assert connection.execute("SELECT count(*) FROM commander_human_feedback WHERE target_id=%s", (queued["brief_id"],)).fetchone()[0] == 1
            assert connection.execute("SELECT count(*) FROM commander_weight_updates WHERE feedback_id=%s", (replacement["feedback_id"],)).fetchone()[0] == 1
        print("Passed disposable migration, V1/V2 generation, concurrent idempotency, immutable snapshots and correction lineage.")
    finally:
        subprocess.run(["docker", "stop", name], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
