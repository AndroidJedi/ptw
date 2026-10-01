#!/usr/bin/env python3
"""Preservation, independent assets, approval and restart in disposable PostgreSQL."""
from pathlib import Path
import base64
import subprocess
import sys
import tempfile
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import psycopg
from scripts.verify_studio_save_restart import verify as seed_post, wait_database
from tests.validation_pipeline.test_studio_creatives import _png
from validation_pipeline.post_templates import DADDY_DEFINITION
from validation_pipeline.studio_creatives import StudioCreativeService
from validation_pipeline.studio_repository import DatabaseStudioAuthority, DatabaseCreativeWorkspace
from validation_pipeline.studio_workspace import PostStudioWorkspace


def verify(url, root):
    project,cid=seed_post(url,root/'seed')
    with psycopg.connect(url) as db:
        before=db.execute('SELECT to_jsonb(w) FROM universal_studio_workspaces w ORDER BY entity_id').fetchall()
        files=db.execute('SELECT workspace_id,relative_path,content_sha256 FROM universal_studio_workspace_files ORDER BY workspace_id,relative_path').fetchall()
        db.execute((ROOT/'db/migrations/022_daddy_post.sql').read_text())
        assert before==db.execute('SELECT to_jsonb(w) FROM universal_studio_workspaces w ORDER BY entity_id').fetchall()
        assert files==db.execute('SELECT workspace_id,relative_path,content_sha256 FROM universal_studio_workspace_files ORDER BY workspace_id,relative_path').fetchall()
    def service(path):
        authority=DatabaseStudioAuthority(url)
        return StudioCreativeService(root=path,authority=authority,
            workspace_factory=lambda p:DatabaseCreativeWorkspace(PostStudioWorkspace(p),authority.repository,p.name),
            structured_provider=None,composer_skill_path=ROOT/'skills/studio-creative-composer/SKILL.md',phone_skill_path=ROOT/'skills/studio-phone-hero-generator/SKILL.md')
    active=service(root/'first')
    detail=active.detail(project,cid)
    original=active._workspace(cid).version_render(1)['bytes']
    # Existing legacy copy contains supported owner figures, retained without mutation.
    switched=active.mutate(project,cid,'switch_template',base_sha256=detail['state_sha256'],request_id=str(uuid4()),template_reference=DADDY_DEFINITION.identity.to_reference(),configuration=detail['configuration'],content=detail['content'])
    request={'slot':'subject','request_id':str(uuid4()),'base_sha256':switched['state_sha256'],'action':'upload',
        'options':{'image':{'mime_type':'image/png','bytes_base64':base64.b64encode(_png('#FEDDCA')).decode()}}}
    updated=active.mutate(project,cid,'daddy_asset_operation',**request)
    restarted=service(root/'second')
    detail=restarted.detail(project,cid)
    assert detail['state_sha256']==updated['state_sha256']
    assert restarted.mutate(project,cid,'daddy_asset_operation',**request)['state_sha256']==updated['state_sha256']
    assert len(restarted._workspace(cid).daddy_asset_history('subject'))==1
    approved=restarted.checkpoint(project,cid,kind='approve',base_sha256=detail['state_sha256'],configuration=detail['configuration'],content=detail['content'],change_note='Disposable Daddy check')
    version=approved['creative']['versions'][-1]['version']
    cloned,_=restarted.clone_approved_version(project_id=project,source_creative_id=cid,source_version=version,request_id=str(uuid4()),requested_by='test')
    restored=service(root/'third')
    assert restored._workspace(cid).version_render(1)['bytes']==original
    actual=restored.detail(project,cloned['creative_id'])
    assert actual['template_id']=='daddy'
    assert restored._workspace(cloned['creative_id'])._asset_record('subject')['bytes']==_png('#FEDDCA')
    from validation_pipeline.landing_pages import DatabaseLandingAuthority
    source=DatabaseLandingAuthority(url)._source_version(project,cid,version)
    assert source['template_id']=='daddy'
    assert source['content']['hero_title']==detail['content']['hero_title']
    print('Disposable PostgreSQL: migration preserves old rows/files/PNG; Daddy assets, duplicate requests, approval, clone, Landing source and three fresh caches passed.')


if __name__=='__main__':
    name='ptw-daddy-test-'+uuid4().hex[:12]
    subprocess.run(['docker','run','--rm','-d','--name',name,'-p','127.0.0.1::5432','-e','POSTGRES_PASSWORD=disposable-only','postgres:16-alpine'],check=True,stdout=subprocess.DEVNULL)
    try:
        port=subprocess.check_output(['docker','port',name,'5432/tcp'],text=True).strip().rsplit(':',1)[1]
        url=f'postgresql://postgres:disposable-only@127.0.0.1:{port}/postgres'
        wait_database(url)
        with psycopg.connect(url,autocommit=True) as db:
            for migration in sorted((ROOT/'db/migrations').glob('*.sql')):
                if migration.name<'022_':db.execute(migration.read_text())
        with tempfile.TemporaryDirectory(prefix='ptw-daddy-db-') as temporary:verify(url,Path(temporary))
    finally:subprocess.run(['docker','stop',name],check=True,stdout=subprocess.DEVNULL)
