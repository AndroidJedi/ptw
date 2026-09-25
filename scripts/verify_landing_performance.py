#!/usr/bin/env python3
"""Exercise new Landing operations/delivery against disposable PostgreSQL only."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_studio_save_restart import wait_database
from tests.validation_pipeline.test_app_showcase import showcase_content
from tests.validation_pipeline.test_landing_workspace import FakeImages, complete_content
from tests.validation_pipeline.test_landing_marketing import complete_marketing
from validation_pipeline.landing_pages import LandingService, DatabaseLandingAuthority, DatabaseLandingWorkspace
from validation_pipeline.landing_workspace import LandingWorkspace, sha256_json
from validation_pipeline.landing_templates import PROJECT_LANDING_DEFINITION, APP_SHOWCASE_DEFINITION, APP_SHOWCASE_V2_DEFINITION
from validation_pipeline.landing_routes import landing_page_router
from validation_pipeline.landing_publication import DatabaseLandingPublicationAuthority
from validation_pipeline.landing_publication_routes import landing_publication_read_router
from validation_pipeline.landing_reapply import reapply_approved


def seed(url):
    source, project, brief, creative, version = [str(uuid4()) for _ in range(5)]
    document = {"language": "en", "idea": "An app to keep track of household items."}
    record = {"template_id": "phone_metrics", "template_sha256": "a"*64, "template_reference": {"template_version": 22},
              "configuration": {}, "content": {"hero_title": "Organize household items"}}
    with psycopg.connect(url) as db:
        for identifier, kind in ((source,"source"),(project,"validation_project"),(brief,"product_brief"),(creative,"studio_workspace"),(version,"studio_version")):
            db.execute("INSERT INTO commander_entities(id,kind) VALUES(%s,%s)", (identifier,kind))
        db.execute("INSERT INTO commander_sources(entity_id,source_type,title,provider,external_id,content,content_sha256) VALUES(%s,'owner_idea','Test','owner',%s,'test',%s)", (source,source,'a'*64))
        db.execute("INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by) VALUES(%s,%s,%s,'Test','owner','test')", (project,uuid4(),source))
        db.execute("INSERT INTO product_briefs(entity_id,project_id,request_id,owner_idea_source_id,status,requested_by,document,document_sha256) VALUES(%s,%s,%s,%s,'completed','test',%s,%s)", (brief,project,uuid4(),source,Jsonb(document),sha256_json(document)))
        db.execute("INSERT INTO product_brief_approvals(id,brief_id,approved_by) VALUES(%s,%s,'test')", (uuid4(),brief))
        db.execute("INSERT INTO universal_studio_workspaces(entity_id,project_id,source_brief_id,ordinal,origin,template_id,status,requested_by) VALUES(%s,%s,%s,1,'brief_generation','phone_metrics','draft','test')", (creative,project,brief))
        db.execute("INSERT INTO universal_studio_versions(entity_id,workspace_id,version,version_sha256,state_sha256,render_sha256,record,render_png) VALUES(%s,%s,1,%s,%s,%s,%s,%s)", (version,creative,sha256_json(record),'a'*64,'b'*64,Jsonb(record),b'fixture'))
    return project, creative


class Provider:
    def call(self, **kwargs):
        return {"response": kwargs["response_validator"]({"edits": [{"path":"content.hero.title", "value":"Updated item collection"}], "image_actions":[], "reply":"Updated the title."}), "invocation":{}}


def make_service(url, root, images):
    authority = DatabaseLandingAuthority(url)
    return LandingService(root=root, authority=authority,
        workspace_factory=lambda path: DatabaseLandingWorkspace(LandingWorkspace(path,image_provider=images),authority,path.name),
        structured_provider=Provider(), composer_skill_path=ROOT/'skills/landing-page-composer/SKILL.md',
        manual_agent_skill_path=ROOT/'skills/studio-manual-agent/SKILL.md')


def verify(url, root):
    publications = DatabaseLandingPublicationAuthority(url)
    for index, definition in enumerate((PROJECT_LANDING_DEFINITION,APP_SHOWCASE_DEFINITION,APP_SHOWCASE_V2_DEFINITION)):
        project, creative = seed(url)
        images = FakeImages()
        service = make_service(url,root/str(index),images)
        reference = {k:v for k,v in definition.identity.to_reference().items() if k!='surface'}
        page,_ = service.reserve_from_post(project_id=project, source_creative_id=creative,source_version=1,requested_by='test',template_reference=reference)
        landing = page['landing_id']; workspace=service._workspace(landing)
        content = showcase_content() if definition.identity.template_id=='app_showcase' else complete_content()
        config = workspace._configuration()
        if 'marketing' in config:
            content['marketing']=complete_marketing()
        detail=workspace.save_configuration(base_sha256=workspace.state_sha256(),configuration=config,content=content)
        for slot in workspace.visual_slots:
            detail=workspace.generate_visual(base_sha256=detail['state_sha256'],slot=slot,visual_direction='A clear household item interface',prompt='fixture')
        service.authority.update_page(landing,status='draft',state_sha256=detail['state_sha256'])
        def owner(x_test_owner: str = Header(default='')):
            if x_test_owner!='disposable-owner': raise HTTPException(status_code=401)
        app=FastAPI(); app.include_router(landing_page_router(service,prefix='/landing',dependencies=[Depends(owner)]))
        app.include_router(landing_publication_read_router(publications,prefix='/api/v1/public/landings'))
        path=f'/landing/projects/{project}/pages/{landing}'
        with TestClient(app) as client:
            assert client.get(path+'/operations').status_code==401
            client.headers['X-Test-Owner']='disposable-owner'
            request={'kind':'agent','request':{'request_id':str(uuid4()),'base_sha256':detail['state_sha256'],'configuration':config,'content':content,'history':[],'screenshots':[],'message':'Change the title to Updated item collection.'}}
            started=client.post(path+'/operations',json=request); assert started.status_code==202,started.text
            identifier=started.json()['operation_id']
            for _ in range(100):
                status=client.get(path+'/operations/'+identifier).json()
                if status['status'] not in {'running','queued'}: break
                time.sleep(.05)
            assert status['status']=='completed',status
            assert status['result']['content']['hero']['title']=='Updated item collection'
            assert client.post(path+'/operations',json=request).json()['operation_id']==identifier
            assert client.get(path.replace(project,str(uuid4()))+'/operations/'+identifier).status_code==404
            image_request={'kind':'image','request':{'request_id':str(uuid4()),'base_sha256':detail['state_sha256'],
                'slot':workspace.visual_slots[0],'configuration':config,'content':content,'visual_direction':'A clear household item interface'}}
            image_start=client.post(path+'/operations',json=image_request); assert image_start.status_code==202,image_start.text
            for _ in range(200):
                image_status=client.get(path+'/operations/'+image_start.json()['operation_id']).json()
                if image_status['status'] not in {'running','queued'}: break
                time.sleep(.05)
            assert image_status['status']=='completed',image_status
            assert image_status['jobs'][0]['status']=='completed'
            detail=service.detail(project,landing)
            saved=service.checkpoint(project,landing,kind='approve',base_sha256=detail['state_sha256'],configuration=config,content=content,change_note='Disposable verification')
            source_record=workspace.version_detail(1)
            publications.publish(project_id=project,request_id=str(uuid4()),landing_id=landing,version=1,slug=f'disposable-{index}',requested_by='test')
            snapshot=client.get(f'/api/v1/public/landings/disposable-{index}').json()
            for slot,variants in snapshot['asset_variants'].items():
                for variant in variants:
                    response=client.get(variant['url']); assert response.status_code==200,response.text
                    assert sha256(response.content).hexdigest()==variant['sha256']
                    assert 'immutable' in response.headers['cache-control']
                    assert client.head(variant['url']).content==b''
                    assert client.get(variant['url'].replace(variant['sha256'],'0'*64)).status_code==404
            original_rows=service.authority.load_workspace_files(landing)
            service.operations.close()
            restored=make_service(url,root/f'restored-{index}',images)
            assert restored.detail(project,landing)['state_sha256']==saved['landing']['state_sha256']
            assert service.authority.load_workspace_files(landing)==original_rows
            assert restored.operations.get(project,landing,identifier)['status']=='completed'
            replacement=reapply_approved(restored,project_id=project,landing_id=landing,version=1,request_id=str(uuid4()),requested_by='test')
            assert replacement['content']==source_record['content'] and replacement['configuration']==source_record['configuration']
            assert {a['slot']:a['sha256'] for a in replacement['assets']}=={a['slot']:a['sha256'] for a in source_record['assets']}
            assert workspace.version_detail(1)==source_record
            assert publications.snapshot(f'disposable-{index}')['version_sha256']==source_record['version_sha256']
            restored.operations.close()
        print(f'PASS: {definition.identity.template_id} v{definition.identity.template_version}: authenticated operation, UUID replay, durable restore, WebP routes, immutable original and replacement draft',flush=True)


def main():
    name='ptw-landing-performance-'+uuid4().hex[:10]
    subprocess.run(['docker','run','--rm','-d','--name',name,'-p','127.0.0.1::5432','-e','POSTGRES_PASSWORD=disposable-only','-e','POSTGRES_DB=ptw_test','postgres:16-alpine'],check=True,stdout=subprocess.DEVNULL)
    try:
        port=subprocess.check_output(['docker','port',name,'5432/tcp'],text=True).strip().rsplit(':',1)[1]
        url=f'postgresql://postgres:disposable-only@127.0.0.1:{port}/ptw_test'; wait_database(url)
        with psycopg.connect(url,autocommit=True) as db:
            for migration in sorted((ROOT/'db/migrations').glob('*.sql')): db.execute(migration.read_text())
        with tempfile.TemporaryDirectory() as temporary: verify(url,Path(temporary))
    finally:
        subprocess.run(['docker','stop',name],check=True,stdout=subprocess.DEVNULL)


if __name__=='__main__': main()
