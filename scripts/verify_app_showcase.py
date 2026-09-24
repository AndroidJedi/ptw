#!/usr/bin/env python3
"""Disposable PostgreSQL proof of Landing template preservation and publication."""
from pathlib import Path
import subprocess, sys, tempfile
from uuid import uuid4
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import psycopg
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.testclient import TestClient
from scripts.verify_studio_save_restart import verify as seed_post, wait_database
from tests.validation_pipeline.test_app_showcase import showcase_content
from tests.validation_pipeline.test_landing_marketing import complete_marketing
from validation_pipeline.landing_templates import APP_SHOWCASE_V2_DEFINITION
REFERENCE = {k:v for k,v in APP_SHOWCASE_V2_DEFINITION.identity.to_reference().items() if k != "surface"}
from tests.validation_pipeline.test_landing_workspace import FakeImages
from validation_pipeline.landing_pages import DatabaseLandingAuthority, DatabaseLandingWorkspace, LandingService
from validation_pipeline.landing_workspace import LandingWorkspace
from validation_pipeline.landing_routes import landing_page_router
from validation_pipeline.landing_publication import DatabaseLandingPublicationAuthority
from validation_pipeline.landing_showcase import VISUAL_SLOTS as SCREEN_VISUAL_SLOTS
VISUAL_SLOTS = (*SCREEN_VISUAL_SLOTS, "walkthrough_visual")


def verify(url, root):
    project, creative = seed_post(url, root / 'seed')
    authority = DatabaseLandingAuthority(url)
    def service(directory):
        return LandingService(root=directory, authority=authority, workspace_factory=lambda path: DatabaseLandingWorkspace(LandingWorkspace(path, image_provider=FakeImages()), authority, path.name), structured_provider=None, composer_skill_path=ROOT/'skills/landing-page-composer/SKILL.md')
    active = service(root/'active')
    # Seed a legacy-format Landing, then prove immutable version preservation.
    legacy, _ = authority.create_page(project_id=project, source_creative_id=creative, source_version=1, requested_by='test')
    active.detail(project, legacy['landing_id'])
    authority.update_page(legacy['landing_id'], status='draft')
    # Reserve a different Post source ordinal through the existing approved-variant gate.
    old_ws = active._workspace(legacy['landing_id'])
    from tests.validation_pipeline.test_landing_workspace import complete_content
    old = old_ws.save_configuration(base_sha256=old_ws.state_sha256(), configuration=old_ws._configuration(), content=complete_content())
    for slot in old_ws.visual_slots: old=old_ws.generate_visual(base_sha256=old['state_sha256'], slot=slot, visual_direction='Legacy sample image', prompt='sample')
    old_ws.approve_configuration(base_sha256=old['state_sha256'],configuration=old['configuration'],content=old['content'],change_note='Legacy version')
    historical=old_ws.version_detail(1)
    with psycopg.connect(url,autocommit=True) as db:
        db.execute((ROOT/'db/migrations/017_landing_marketing_sections.sql').read_text())
    assert old_ws.version_detail(1)==historical
    page, created=active.reserve_from_post(project_id=project,source_creative_id=creative,source_version=1,requested_by='test',additional=True,template_reference=REFERENCE)
    assert created
    lid=page['landing_id']; authority.update_page(lid,status='draft')
    app=FastAPI()
    def owner(authorization: str=Header(default='')):
        if authorization != 'Bearer canary': raise HTTPException(401,'owner required')
    app.include_router(landing_page_router(active,prefix='/landings',dependencies=[Depends(owner)]))
    base=f'/landings/projects/{project}/pages/{lid}'
    with TestClient(app) as client:
        assert client.get(base).status_code==401
        client.headers['Authorization']='Bearer canary'
        detail=client.get(base).json()
        content=showcase_content(); content['marketing']=complete_marketing()
        response=client.post(base+'/configuration',json={'base_sha256':detail['state_sha256'],'configuration':detail['configuration'],'content':content})
        assert response.status_code==200,response.text
        detail=response.json()
        for slot in VISUAL_SLOTS:
            response=client.post(base+f'/visuals/{slot}/generate',json={'base_sha256':detail['state_sha256'],'visual_direction':'A clean sample app interface'})
            assert response.status_code==200,response.text
            detail=response.json()
        response=client.post(base+'/visuals/walkthrough_visual/generate',json={'base_sha256':detail['state_sha256'],'visual_direction':'Enhance the three complete phone mockups','enhance_current':True})
        assert response.status_code==200,response.text
        detail=response.json()
        assert len(detail['assets'][-1]['history'])==2
        rejected=client.post(base+'/visuals/hero_visual/generate',json={'base_sha256':detail['state_sha256'],'visual_direction':'A clean sample app interface'})
        assert rejected.status_code==400,rejected.text
        response=client.post(base+'/approve',json={'base_sha256':detail['state_sha256'],'configuration':detail['configuration'],'content':detail['content'],'change_note':'Showcase approved'})
        assert response.status_code==200,response.text
        final=response.json()['landing']
    restarted=service(root/'fresh-cache')
    restored=restarted.detail(project,lid)
    assert restored['state_sha256']==final['state_sha256']
    assert restored['template_reference']==REFERENCE
    assert restarted._workspace(legacy['landing_id']).version_detail(1)==historical
    publication=DatabaseLandingPublicationAuthority(url)
    publication.publish(project_id=project,request_id=str(uuid4()),landing_id=lid,version=1,namespace='ai',slug='showcase-test',requested_by='test')
    snapshot=publication.snapshot('ai','showcase-test')
    assert snapshot['template_reference']==REFERENCE and set(snapshot['assets'])==set(VISUAL_SLOTS)
    for asset in restored['assets']:
        result=publication.asset('ai','showcase-test',snapshot['version_sha256'],asset['slot'],asset['sha256'])
        assert result['bytes']==restarted._workspace(lid).visual_image(asset['slot'],asset['sha256'])['bytes']
    print('PASS: authenticated HTTP, exact template, all five slots, mockup enhancement, approval, fresh-cache restart, public bytes, and historical version preservation.')


def main():
    name='ptw-showcase-test-'+uuid4().hex[:10]
    subprocess.run(['docker','run','--rm','-d','--name',name,'-p','127.0.0.1::5432','-e','POSTGRES_PASSWORD=disposable-only','-e','POSTGRES_DB=ptw_test','postgres:16-alpine'],check=True,stdout=subprocess.DEVNULL)
    try:
        port=subprocess.check_output(['docker','port',name,'5432/tcp'],text=True).strip().rsplit(':',1)[1]
        url=f'postgresql://postgres:disposable-only@127.0.0.1:{port}/ptw_test'
        wait_database(url)
        with psycopg.connect(url,autocommit=True) as db:
            for path in sorted((ROOT/'db/migrations').glob('*.sql')):
                if not path.name.startswith('017_'): db.execute(path.read_text())
        with tempfile.TemporaryDirectory() as temp: verify(url,Path(temp))
    finally: subprocess.run(['docker','stop',name],check=True,stdout=subprocess.DEVNULL)
if __name__=='__main__':main()
