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
        # Reproduce the deployed failure without leaving a row in the fixture.
        db.execute('SAVEPOINT daddy_stage_probe')
        probe_id=uuid4()
        db.execute("INSERT INTO commander_entities(id,kind) VALUES(%s,'studio_generation_run')",(probe_id,))
        try:
            db.execute("INSERT INTO studio_generation_runs(entity_id,workspace_id,attempt,stage,status) VALUES(%s,%s,1,'daddy_strategy','completed')",(probe_id,cid))
        except psycopg.errors.CheckViolation:
            db.execute('ROLLBACK TO SAVEPOINT daddy_stage_probe')
        else:
            raise AssertionError('Migration 022 did not reproduce the Daddy stage failure')
        db.execute((ROOT/'db/migrations/023_daddy_generation_stages.sql').read_text())
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
    # Exercise the production database path that the in-memory Daddy tests miss.
    stages=('composition','phone_image','daddy_strategy','daddy_composition',
        'daddy_assets','daddy_asset:scene','daddy_asset:screen','daddy_asset:subject',
        'daddy_asset:feature','daddy_asset:prop_one','daddy_asset:prop_two',
        'daddy_review','daddy_polish','daddy_ready','daddy_needs_review')
    for stage in stages:
        active.authority.record_generation(creative_id=cid,stage=stage,status='completed')
    with psycopg.connect(url) as db:
        assert [row[0] for row in db.execute('SELECT stage FROM studio_generation_runs WHERE workspace_id=%s ORDER BY attempt',(cid,))]==list(stages)
    try:
        active.authority.record_generation(creative_id=cid,stage='daddy_unknown',status='failed')
    except psycopg.errors.CheckViolation:
        pass
    else:
        raise AssertionError('Unsupported Daddy generation stage was accepted')
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
    # The image recovery cursor and rejected attempt survive fresh PG workspaces.
    from validation_pipeline.image_errors import InvalidGeneratedImage
    from validation_pipeline.studio_daddy import default_configuration
    from tests.validation_pipeline.test_daddy import DaddyProvider
    clone_id = cloned['creative_id']
    configuration = default_configuration('lifestyle')
    updated = restored.mutate(project,clone_id,'save_configuration',base_sha256=actual['state_sha256'],configuration=configuration,content=actual['content'])
    generation = {'creative_direction':{'schema':'ptw.studio.phone-hero-direction.v1','style':'ultra_realistic_lifestyle','background':'scene'},
        'daddy':{'phase':'assets','composed':True,'assets':{},'corrections':0,
            'strategy':{'preset':'lifestyle','style':'photography','reason':'Recovery canary','assets':[{'slot':'scene','direction':'A complete contextual scene without hands.'}]}}}
    restored.authority.update_creative(clone_id,status='queued',generation=generation)
    keys = []
    class Images:
        supports_operation_tracking = True
        broken = True
        def generate(self,prompt,**options):
            keys.append(options['operation_key'])
            options['progress']({'stage':'generating','provider_request_id':1347+len(keys)})
            if self.broken: raise InvalidGeneratedImage(1347+len(keys))
            return {'bytes':_png(),'mime_type':'image/png','source':{'origin':'disposable-fixture'}}
    images = Images()
    def recovery(path):
        instance = service(path)
        instance.workspace_factory = lambda p:DatabaseCreativeWorkspace(PostStudioWorkspace(p,image_provider=images),instance.authority.repository,p.name)
        instance.structured_provider = DaddyProvider('lifestyle')
        return instance
    from psycopg.types.json import Jsonb
    from validation_pipeline.local_brief_store import sha256_json
    document={'schema_version':1,'language':'en','product':'A useful service','target_audience':'Independent operators',
        'main_pain':'Unclear next step','promise':'Understand the next step','key_benefits':['A clear plan'],
        'cta':'Learn more','trust_strategy':'Explain the process','offer':'A guided first setup'}
    with psycopg.connect(url) as db:
        db.execute('UPDATE product_briefs SET document=%s,document_sha256=%s WHERE entity_id=%s',
            (Jsonb(document),sha256_json(document),actual['source_brief_id']))
        db.execute('INSERT INTO product_brief_approvals(id,brief_id,approved_by) VALUES(%s,%s,%s)',
            (uuid4(),actual['source_brief_id'],'disposable-test'))
    first = recovery(root/'recovery-first')
    try: first.generate(clone_id)
    except InvalidGeneratedImage: pass
    else: raise AssertionError('Corrupt image was accepted')
    second = recovery(root/'recovery-second')
    failed = second.detail(project,clone_id)
    assert failed['status']=='failed'
    record = next(iter(failed['generation']['daddy']['asset_operations'].values()))
    assert record['attempt']==1 and record['attempts']['1']['failure_code']=='invalid_image'
    assert len(keys)==2 and keys[0]!=keys[1]
    images.broken = False
    retry_id = str(uuid4())
    second.retry_generation(project,clone_id,request_id=retry_id)
    third = recovery(root/'recovery-third')
    third.retry_generation(project,clone_id,request_id=retry_id)
    third.generate(clone_id)
    done = recovery(root/'recovery-fourth').detail(project,clone_id)
    assert done['status']=='draft' and done['content']==actual['content']
    assert len(keys)==3 and len(set(keys))==3
    assert done['generation']['retry_requests']==[retry_id]
    assert restored._workspace(cid).version_render(1)['bytes']==original
    print('Disposable PostgreSQL: migration preserves old rows/files/PNG; Daddy stages, assets, duplicate requests, approval, clone, Landing source and three fresh caches passed.')


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
