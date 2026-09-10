#!/usr/bin/env python3
"""Exercise legacy editor Save through real HTTP and disposable PostgreSQL."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.validation_pipeline.test_studio_creatives import FakeStructuredProvider, FakeImageProvider
from validation_pipeline.studio_creatives import StudioCreativeService, _state_snapshot
from validation_pipeline.studio_repository import DatabaseCreativeWorkspace, DatabaseStudioAuthority
from validation_pipeline.studio_routes import studio_creative_router
from validation_pipeline.studio_workspace import UniversalStudioWorkspace
from validation_pipeline.local_brief_store import sha256_json


def wait_database(url):
    for _ in range(80):
        try:
            with psycopg.connect(url) as connection:
                connection.execute("SELECT 1")
            return
        except psycopg.OperationalError:
            time.sleep(0.25)
    raise RuntimeError("Disposable PostgreSQL did not start")


def verify(url, root):
    authority = DatabaseStudioAuthority(url)
    project_id, brief_id, cid, source_id = [str(uuid4()) for _ in range(4)]
    with psycopg.connect(url) as connection:
        for identifier, kind in ((source_id, "source"), (project_id, "validation_project"),
                                 (brief_id, "product_brief"), (cid, "studio_workspace")):
            connection.execute("INSERT INTO commander_entities(id,kind) VALUES(%s,%s)", (identifier, kind))
        connection.execute("INSERT INTO commander_sources(entity_id,source_type,title,provider,external_id,content,content_sha256) VALUES(%s,'owner_idea','Test','owner','test','test',%s)", (source_id, "a" * 64))
        connection.execute("INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by) VALUES(%s,%s,%s,'Test','owner','test')", (project_id, uuid4(), source_id))
        connection.execute("INSERT INTO product_briefs(entity_id,project_id,request_id,owner_idea_source_id,status,requested_by) VALUES(%s,%s,%s,%s,'completed','test')", (brief_id, project_id, uuid4(), source_id))
        connection.execute("INSERT INTO universal_studio_workspaces(entity_id,project_id,source_brief_id,ordinal,origin,template_id,status,requested_by) VALUES(%s,%s,%s,1,'brief_generation','phone_metrics','draft','test')", (cid, project_id, brief_id))
    authority.ensure_project_skill(project_id)
    authority.ensure_global_skill()
    workspace = UniversalStudioWorkspace(root / "original", image_provider=FakeImageProvider())
    detail = workspace.apply_template(base_sha256=workspace.detail()["state_sha256"], template_id="phone_metrics")
    detail = workspace.generate_phone_screen(base_sha256=detail["state_sha256"], visual_direction="A calm blue glass staircase")
    workspace.approve_version(state_sha256=detail["state_sha256"], change_note="Original immutable version")
    original_png = workspace.version_render(1)["bytes"]
    detail = workspace.detail()
    baseline = _state_snapshot(detail)
    config = deepcopy(detail["configuration"])
    config["schema"] = "ptw.studio.phone-metrics-config.v8"
    config.pop("logo")
    config["phone_screen"].pop("logo_enabled")
    (workspace.root / "configuration.json").write_text(json.dumps(config))
    legacy = workspace._legacy_phone_state_sha256()
    authority.repository.persist_creative(workspace.root, workspace_id=cid, state_sha256=legacy,
        template_id="phone_metrics", template_version=22, template_sha256=detail["template_sha256"])
    authority.update_creative(cid, learning_baseline=baseline, learning_baseline_sha256=sha256_json(baseline))

    def service(directory):
        return StudioCreativeService(root=directory, authority=DatabaseStudioAuthority(url),
            workspace_factory=lambda path: DatabaseCreativeWorkspace(UniversalStudioWorkspace(path), authority.repository, path.name),
            structured_provider=FakeStructuredProvider(),
            composer_skill_path=ROOT / "skills/studio-creative-composer/SKILL.md",
            learner_skill_path=ROOT / "skills/studio-edit-learner/SKILL.md",
            phone_skill_path=ROOT / "skills/studio-phone-hero-generator/SKILL.md")

    original_files = authority.repository.load_creative(cid)
    active = service(root / "first-process")
    app = FastAPI()
    app.include_router(studio_creative_router(active, prefix="/studio"))
    path = f"/studio/projects/{project_id}/creatives/{cid}"
    with TestClient(app) as client:
        response = client.get(path)
        assert response.status_code == 200, response.text
        detail = response.json()
        assert detail["state_sha256"] != legacy
        assert original_files == authority.repository.load_creative(cid), "GET mutated authority"
        # An unchanged explicit Save must commit normalized files and metadata
        # together without manufacturing a learning checkpoint.
        response = client.post(path + "/save", json={"base_sha256": legacy,
            "configuration": detail["configuration"], "content": detail["content"]})
        assert response.status_code == 200, response.text
        assert not response.json()["checkpoint_created"], response.text
        detail = response.json()["creative"]
        changed = deepcopy(detail["content"])
        changed["hero_title"] = "Owner edits remain after restart"
        response = client.post(path + "/save", json={"base_sha256": detail["state_sha256"],
            "configuration": detail["configuration"], "content": changed})
        assert response.status_code == 200, response.text
        saved = response.json()
        assert saved["checkpoint_created"] and saved["checkpoint"]["status"] == "completed", saved
        assert saved["creative"]["content"] == changed
        assert client.post(path + "/save", json={"base_sha256": legacy,
            "configuration": detail["configuration"], "content": changed}).status_code == 409
    restored = service(root / "restarted-process")
    actual = restored.detail(project_id, cid)
    assert actual["content"] == changed
    assert actual["state_sha256"] == saved["creative"]["state_sha256"]
    assert restored._workspace(cid).version_render(1)["bytes"] == original_png
    before_repeat = authority.repository.load_creative(cid)
    repeated = restored.checkpoint(project_id, cid, kind="save", base_sha256=actual["state_sha256"],
        configuration=actual["configuration"], content=actual["content"])
    assert not repeated["checkpoint_created"]
    assert authority.repository.load_creative(cid) == before_repeat
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT count(*) FROM studio_edit_checkpoints WHERE workspace_id=%s", (cid,)).fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM universal_studio_versions WHERE workspace_id=%s", (cid,)).fetchone()[0] == 1
        checkpoint_id = saved["checkpoint"]["checkpoint_id"]
        assert connection.execute("SELECT count(*) FROM commander_relationships WHERE source_id=%s AND target_id=%s AND relation='contains'", (cid, checkpoint_id)).fetchone()[0] == 1
    print("PASS: real HTTP/PostgreSQL legacy Save, unchanged Save, completed learning, fresh service/cache restore, stale rejection, immutable PNG and checkpoint lineage.")


def main():
    name = "ptw-save-test-" + uuid4().hex[:12]
    subprocess.run(["docker", "run", "--rm", "-d", "--name", name, "-p", "127.0.0.1::5432",
        "-e", "POSTGRES_PASSWORD=disposable-only", "-e", "POSTGRES_DB=ptw_test", "postgres:16-alpine"], check=True, stdout=subprocess.DEVNULL)
    try:
        port = subprocess.check_output(["docker", "port", name, "5432/tcp"], text=True).strip().rsplit(":", 1)[1]
        url = f"postgresql://postgres:disposable-only@127.0.0.1:{port}/ptw_test"
        wait_database(url)
        with psycopg.connect(url, autocommit=True) as connection:
            for migration in sorted((ROOT / "db/migrations").glob("*.sql")):
                connection.execute(migration.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            verify(url, Path(temporary))
    finally:
        subprocess.run(["docker", "stop", name], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
