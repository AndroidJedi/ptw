#!/usr/bin/env python3
"""Verify Templates migration, atomic paired acceptance and restart in disposable PG."""
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import psycopg
from fastapi import Depends,FastAPI,Header,HTTPException
from fastapi.testclient import TestClient
from scripts.verify_studio_save_restart import wait_database
from tests.validation_pipeline.test_template_authoring import ScriptedTemplateProvider
from validation_pipeline.template_authoring import TemplateAuthoringService
from validation_pipeline.template_components import canonical
from validation_pipeline.template_routes import template_router
from validation_pipeline.template_store import TemplateStore


def verify(url):
    provider=ScriptedTemplateProvider(adjust=True)
    service=TemplateAuthoringService(TemplateStore(database_url=url),provider,asynchronous=False)
    def owner(authorization:str=Header(default='')):
        if authorization!='Bearer canary':raise HTTPException(401,'owner required')
    app=FastAPI();app.include_router(template_router(service,prefix='/templates',dependencies=[Depends(owner)]))
    headers={'Authorization':'Bearer canary'}
    try:
        with TestClient(app) as client:
            request={'request_id':str(uuid4()),'scope':'combined','instruction':'A reusable title image and action'}
            response=client.post('/templates/runs',headers=headers,json=request)
            assert response.status_code==202,response.text
            run=response.json();assert run['status']=='proposed',run
            assert client.post('/templates/runs',headers=headers,json=request).json()==run
            decision={'request_id':str(uuid4()),'base_sha256':run['state_sha256'],'decision':'accept'}
            accepted=client.post('/templates/runs/'+run['run_id']+'/decision',headers=headers,json=decision)
            assert accepted.status_code==200,accepted.text
            refs=accepted.json()['accepted_versions'];assert len(refs)==2
            before=[service.read(ref) for ref in refs]
            media=[service.preview(p['sha256']) for record in before for p in record['previews'].values()]
        restored=TemplateAuthoringService(TemplateStore(database_url=url),provider,asynchronous=False)
        try:
            restored.recover_interrupted()
            assert before==[restored.read(ref) for ref in refs]
            assert media==[restored.preview(p['sha256']) for record in before for p in record['previews'].values()]
            assert restored.decide(run['run_id'],decision)['accepted_versions']==refs
            assert before[1]['post_reference']=={k:v for k,v in refs[0].items() if k!='surface'}
        finally:restored.close()
        with psycopg.connect(url) as db:
            assert db.execute("SELECT count(*) FROM template_authoring_records WHERE kind='version'").fetchone()[0]==2
            for table in ('template_authoring_records','template_authoring_media'):
                try:
                    with db.transaction():db.execute('DELETE FROM '+table)
                except psycopg.errors.RaiseException:pass
                else:raise AssertionError('Immutable guard missing')
            assert db.execute('SELECT count(*) FROM validation_projects').fetchone()[0]==0
        print('PASS: real authenticated HTTP/PostgreSQL combined acceptance, exact references, request reconciliation, immutable history/media, restart and no Project records.')
    finally:service.close()


def main():
    name='ptw-template-test-'+uuid4().hex[:12]
    subprocess.run(['docker','run','--rm','-d','--name',name,'-p','127.0.0.1::5432','-e','POSTGRES_PASSWORD=disposable-only','-e','POSTGRES_DB=ptw_test','postgres:16-alpine'],check=True,stdout=subprocess.DEVNULL)
    try:
        port=subprocess.check_output(['docker','port',name,'5432/tcp'],text=True).strip().rsplit(':',1)[1]
        url=f'postgresql://postgres:disposable-only@127.0.0.1:{port}/ptw_test'
        wait_database(url)
        with psycopg.connect(url,autocommit=True) as db:
            for path in sorted((ROOT/'db/migrations').glob('*.sql')):db.execute(path.read_text())
        verify(url)
    finally:subprocess.run(['docker','stop',name],check=True,stdout=subprocess.DEVNULL)

if __name__=='__main__':main()
