#!/usr/bin/env python3
"""Disposable PostgreSQL/HTTP proof of applying a template to an existing Post."""
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from scripts.verify_studio_save_restart import verify as seed_post, wait_database
from tests.validation_pipeline.test_template_authoring import ScriptedTemplateProvider
from validation_pipeline.template_authoring import TemplateAuthoringService
from validation_pipeline.template_store import TemplateStore
from validation_pipeline.studio_creatives import StudioCreativeService
from validation_pipeline.studio_repository import DatabaseCreativeWorkspace, DatabaseStudioAuthority
from validation_pipeline.studio_workspace import PostStudioWorkspace
from validation_pipeline.studio_routes import studio_creative_router


def verify(url, root):
    project, cid = seed_post(url, root / 'seed')
    authoring = TemplateAuthoringService(TemplateStore(database_url=url), ScriptedTemplateProvider(), asynchronous=False)
    try:
        run = authoring.start({'request_id': str(uuid4()), 'scope': 'post', 'instruction': 'A clear reusable Post'})
        assert run['status'] == 'proposed', run
        reference = authoring.decide(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256'], 'decision': 'accept'})['accepted_versions'][0]
        def service(directory):
            authority = DatabaseStudioAuthority(url)
            result = StudioCreativeService(root=directory, authority=authority,
                workspace_factory=lambda path: DatabaseCreativeWorkspace(PostStudioWorkspace(path), authority.repository, path.name),
                structured_provider=None, composer_skill_path=ROOT/'skills/studio-creative-composer/SKILL.md', phone_skill_path=ROOT/'skills/studio-phone-hero-generator/SKILL.md')
            result.template_registry = authoring.post_registry
            return result
        active = service(root / 'active')
        before = active.detail(project, cid)
        png = active._workspace(cid).version_render(1)['bytes']
        app = FastAPI()
        def owner(authorization: str = Header(default='')):
            if authorization != 'Bearer canary': raise HTTPException(401, 'owner required')
        app.include_router(studio_creative_router(active, prefix='/studio', dependencies=[Depends(owner)]))
        path = f'/studio/projects/{project}/creatives/{cid}'
        request = {'request_id': str(uuid4()), 'base_sha256': before['state_sha256'], 'template_reference': reference,
                   'configuration': before['configuration'], 'content': {**before['content'], 'hero_title': 'My existing Post in a new layout'}}
        with TestClient(app) as client:
            assert client.post(path+'/templates/apply', json=request).status_code == 401
            response = client.post(path+'/templates/apply', json=request, headers={'Authorization': 'Bearer canary'})
            assert response.status_code == 200, response.text
            changed = response.json()
            assert changed['template_reference'] == reference
            assert changed['content']['template_text']['title'] == request['content']['hero_title']
            repeated = client.post(path+'/templates/apply', json=request, headers={'Authorization': 'Bearer canary'})
            assert repeated.status_code == 200 and repeated.json()['state_sha256'] == changed['state_sha256'], repeated.text
            stale = client.post(path+'/templates/apply', json={**request, 'request_id': str(uuid4())}, headers={'Authorization': 'Bearer canary'})
            assert stale.status_code == 409, stale.text
            approved = client.post(path+'/approve', json={'base_sha256': changed['state_sha256'], 'configuration': changed['configuration'], 'content': changed['content'], 'change_note': 'New Post layout'}, headers={'Authorization': 'Bearer canary'})
            assert approved.status_code == 200, approved.text
        restored = service(root / 'fresh-cache')
        actual = restored.detail(project, cid)
        assert actual['template_reference'] == reference
        assert actual['phone_screen_history'] == before['phone_screen_history']
        assert len(actual['versions']) == 2
        assert restored._workspace(cid).version_render(1)['bytes'] == png
        from validation_pipeline.landing_pages import DatabaseLandingAuthority
        sources = DatabaseLandingAuthority(url)
        assert sources._source_version(project, cid, 1)['template_id'] == 'phone_metrics'
        assert sources._source_version(project, cid, 2)['template_id'] == reference['template_id']
        assert {r['template_id'] for r in sources.source_versions(project)} == {'phone_metrics', reference['template_id']}
        render = restored._workspace(cid).render_preview(state_sha256=actual['state_sha256'])
        (ROOT/'.local/post-template-canary.png').write_bytes(render['bytes'])
        with psycopg.connect(url) as db:
            assert db.execute('SELECT template_id FROM universal_studio_workspaces WHERE entity_id=%s', (cid,)).fetchone()[0] == reference['template_id']
        print('PASS: owner-authenticated PostgreSQL template apply, pending copy, exact pinned identity, response-loss reconciliation, stale rejection, approved history, raw image retention and fresh-cache restart.')
    finally: authoring.close()


def main():
    name = 'ptw-post-template-test-' + uuid4().hex[:12]
    subprocess.run(['docker','run','--rm','-d','--name',name,'-p','127.0.0.1::5432','-e','POSTGRES_PASSWORD=disposable-only','-e','POSTGRES_DB=ptw_test','postgres:16-alpine'],check=True,stdout=subprocess.DEVNULL)
    try:
        port = subprocess.check_output(['docker','port',name,'5432/tcp'],text=True).strip().rsplit(':',1)[1]
        url = f'postgresql://postgres:disposable-only@127.0.0.1:{port}/ptw_test'
        wait_database(url)
        with psycopg.connect(url, autocommit=True) as db:
            for migration in sorted((ROOT/'db/migrations').glob('*.sql')): db.execute(migration.read_text())
        with tempfile.TemporaryDirectory(prefix='ptw-post-template-') as directory: verify(url, Path(directory))
    finally: subprocess.run(['docker','stop',name],check=True,stdout=subprocess.DEVNULL)

if __name__ == '__main__': main()
