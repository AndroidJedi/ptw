#!/usr/bin/env python3
"""Exercise retired-Post replacement against disposable PostgreSQL authority."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from validation_pipeline.studio_repository import DatabaseStudioAuthority


def wait_database(url: str) -> None:
    for _ in range(80):
        try:
            with psycopg.connect(url) as connection:
                connection.execute("SELECT 1")
            return
        except psycopg.OperationalError:
            time.sleep(0.25)
    raise RuntimeError("Disposable target database did not become queryable")


def verify(url: str) -> None:
    source_id, project_id, brief_id, legacy_id = (str(uuid4()) for _ in range(4))
    migrations = sorted((ROOT / "db/migrations").glob("*.sql"))
    with psycopg.connect(url, autocommit=True) as connection:
        for path in migrations:
            if path.name == "012_phone_metrics_only.sql":
                with connection.transaction():
                    for identifier, kind in (
                        (source_id, "source"), (project_id, "validation_project"),
                        (brief_id, "product_brief"), (legacy_id, "studio_workspace"),
                    ):
                        connection.execute("INSERT INTO commander_entities(id,kind) VALUES(%s,%s)", (identifier, kind))
                    connection.execute(
                        """INSERT INTO commander_sources(entity_id,source_type,title,provider,external_id,content,content_sha256)
                           VALUES(%s,'owner_idea','Disposable','owner','legacy-fixture','fixture',%s)""",
                        (source_id, "a" * 64),
                    )
                    connection.execute(
                        """INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by)
                           VALUES(%s,%s,%s,'Disposable Project','owner','test')""",
                        (project_id, uuid4(), source_id),
                    )
                    connection.execute(
                        """INSERT INTO product_briefs(entity_id,project_id,request_id,owner_idea_source_id,status,requested_by)
                           VALUES(%s,%s,%s,%s,'completed','test')""",
                        (brief_id, project_id, uuid4(), source_id),
                    )
                    connection.execute(
                        "INSERT INTO product_brief_approvals(id,brief_id,approved_by) VALUES(%s,%s,'test')",
                        (uuid4(), brief_id),
                    )
                    connection.execute(
                        """INSERT INTO universal_studio_workspaces(entity_id,project_id,source_brief_id,ordinal,origin,
                           template_id,template_version,template_sha256,status,state_sha256,requested_by)
                           VALUES(%s,%s,%s,1,'brief_generation','universal_ad',13,%s,'draft',%s,'test')""",
                        (legacy_id, project_id, brief_id, "b" * 64, "c" * 64),
                    )
            connection.execute(path.read_text())
        original = connection.execute(
            "SELECT row_to_json(w)::text FROM universal_studio_workspaces w WHERE entity_id=%s", (legacy_id,),
        ).fetchone()[0]

    authority = DatabaseStudioAuthority(url)
    direction = {"schema": "ptw.studio.phone-hero-direction.v1",
                 "style": "cinematic", "background": "scene"}
    current, created = authority.create_creative(
        project_id=project_id, brief_id=brief_id, template_id="phone_metrics",
        requested_by="test", origin="approved_variant", creative_direction=direction,
        require_approved_previous=True,
    )
    assert created and current["ordinal"] == 2 and current["source_brief_id"] == brief_id
    try:
        authority.create_creative(
            project_id=project_id, brief_id=brief_id, template_id="phone_metrics",
            requested_by="test", origin="approved_variant", creative_direction=direction,
            require_approved_previous=True,
        )
    except ValueError as error:
        assert "approve the current creative" in str(error)
    else:
        raise AssertionError("A second unapproved current Post was reserved")
    with psycopg.connect(url) as connection:
        assert connection.execute(
            "SELECT row_to_json(w)::text FROM universal_studio_workspaces w WHERE entity_id=%s", (legacy_id,),
        ).fetchone()[0] == original
        assert connection.execute(
            "SELECT count(*) FROM universal_studio_workspaces WHERE source_brief_id=%s", (brief_id,),
        ).fetchone()[0] == 2
        assert connection.execute(
            """SELECT count(*) FROM commander_relationships WHERE source_id=%s AND target_id=%s
               AND relation='derived_from'""", (current["creative_id"], brief_id),
        ).fetchone()[0] == 1
    print("PASS: one active Post reserved from the approved Brief; retained Universal row unchanged")


def main() -> None:
    name = "ptw-legacy-recovery-" + uuid4().hex[:12]
    subprocess.run([
        "docker", "run", "--rm", "-d", "--name", name, "-p", "127.0.0.1::5432",
        "-e", "POSTGRES_PASSWORD=disposable-only", "-e", "POSTGRES_DB=ptw_test",
        "postgres:16-alpine",
    ], check=True, stdout=subprocess.DEVNULL)
    try:
        port = subprocess.check_output(["docker", "port", name, "5432/tcp"], text=True).strip().rsplit(":", 1)[1]
        url = f"postgresql://postgres:disposable-only@127.0.0.1:{port}/ptw_test"
        wait_database(url)
        verify(url)
    finally:
        subprocess.run(["docker", "stop", name], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
