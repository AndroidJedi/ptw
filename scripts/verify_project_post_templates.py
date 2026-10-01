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
        from psycopg.types.json import Jsonb
        from tests.validation_pipeline.test_studio_creatives import FakeStructuredProvider, FakeImageProvider, PHONE_DIRECTION
        from validation_pipeline.local_brief_store import sha256_json
        source_id, fresh_project, brief_id = (str(uuid4()) for _ in range(3))
        document = {
            'schema_version': 1, 'language': 'en', 'product': 'Useful product',
            'target_audience': 'Independent operators', 'main_pain': 'Lost time',
            'promise': 'Reach the next decision faster',
            'key_benefits': ['Clear next step', 'Less busywork', 'Honest guidance'],
            'cta': 'Start now', 'trust_strategy': 'Show the workflow',
            'offer': 'A guided first setup',
        }
        with psycopg.connect(url) as db:
            for identifier, kind in ((source_id, 'source'), (fresh_project, 'validation_project'), (brief_id, 'product_brief')):
                db.execute('INSERT INTO commander_entities(id,kind) VALUES(%s,%s)', (identifier, kind))
            db.execute("INSERT INTO commander_sources(entity_id,source_type,title,provider,external_id,content,content_sha256) VALUES(%s,'owner_idea','Initial template','owner','initial-template','A useful product',%s)", (source_id, 'a' * 64))
            db.execute("INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by) VALUES(%s,%s,%s,'Initial template','owner','test')", (fresh_project, uuid4(), source_id))
            db.execute("INSERT INTO product_briefs(entity_id,project_id,request_id,owner_idea_source_id,status,document,document_sha256,requested_by) VALUES(%s,%s,%s,%s,'completed',%s,%s,'test')", (brief_id, fresh_project, uuid4(), source_id, Jsonb(document), sha256_json(document)))
        def initial_service(directory):
            authority = DatabaseStudioAuthority(url)
            result = StudioCreativeService(
                root=directory, authority=authority,
                workspace_factory=lambda path: DatabaseCreativeWorkspace(
                    PostStudioWorkspace(path, image_provider=FakeImageProvider()),
                    authority.repository, path.name,
                ),
                structured_provider=FakeStructuredProvider(),
                composer_skill_path=ROOT/'skills/studio-creative-composer/SKILL.md',
                phone_skill_path=ROOT/'skills/studio-phone-hero-generator/SKILL.md',
            )
            result.template_registry = authoring.post_registry
            return result
        initial = initial_service(root / 'initial-selected')
        _brief, approved_now, first, created_now = initial.approve_brief_and_reserve(
            brief_id=brief_id, template_id=reference['template_id'],
            template_reference=reference, creative_direction=PHONE_DIRECTION,
            requested_by='test', brief_approver=lambda *_: None,
        )
        assert approved_now and created_now
        first_detail = initial.detail(fresh_project, first['creative_id'])
        assert first_detail['template_reference'] == reference and first_detail['status'] == 'queued'
        initial.generate(first['creative_id'])
        first_detail = initial.detail(fresh_project, first['creative_id'])
        assert first_detail['status'] == 'draft', first_detail['generation']
        assert first_detail['template_reference'] == reference and first_detail['content']['template_text']
        assert first_detail['generation']['phone_image']['status'] == 'completed'
        first_png = initial._workspace(first['creative_id']).render_preview(state_sha256=first_detail['state_sha256'])['bytes']
        assert first_png.startswith(b'\x89PNG\r\n\x1a\n')
        saved = initial.checkpoint(fresh_project, first['creative_id'], kind='save',
            base_sha256=first_detail['state_sha256'], configuration=first_detail['configuration'],
            content={**first_detail['content'], 'template_text': {
                **first_detail['content']['template_text'],
                next(iter(first_detail['content']['template_text'])): 'Owner edited selected template',
            }})
        approved = initial.checkpoint(fresh_project, first['creative_id'], kind='approve',
            base_sha256=saved['creative']['state_sha256'], configuration=saved['creative']['configuration'],
            content=saved['creative']['content'], change_note='Approve selected template')
        assert approved['version_created']
        restored_first = initial_service(root / 'initial-selected-restart').detail(fresh_project, first['creative_id'])
        assert restored_first['template_reference'] == reference
        assert restored_first['versions'] == approved['creative']['versions']
        with psycopg.connect(url) as db:
            stored = db.execute('SELECT template_id,template_version,template_sha256 FROM universal_studio_workspaces WHERE entity_id=%s', (first['creative_id'],)).fetchone()
            assert stored == (reference['template_id'], reference['template_version'], restored_first['template_sha256'])
        print('PASS: owner-authenticated PostgreSQL template apply, pending copy, exact pinned identity, response-loss reconciliation, stale rejection, approved history, raw image retention and fresh-cache restart.')
        print('PASS: first Brief creative starts on the accepted version, composes and renders artwork, saves, approves and restores without a Phone Metrics creative.')
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
