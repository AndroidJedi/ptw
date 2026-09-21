#!/usr/bin/env python3
"""Disposable real-HTTP Templates browser fixture. Only inference is scripted."""
import argparse
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi import Depends, FastAPI, Header, HTTPException
import uvicorn
from tests.validation_pipeline.test_template_authoring import ScriptedTemplateProvider
from validation_pipeline.template_authoring import TemplateAuthoringService
from validation_pipeline.template_routes import template_router
from validation_pipeline.template_store import TemplateStore

parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,required=True)
parser.add_argument('--directory',type=Path,required=True)
parser.add_argument('--project-post', action='store_true')
args=parser.parse_args()
if not args.directory.name.startswith('ptw-template-browser-'):
    raise ValueError('Use a disposable browser fixture directory')
provider=ScriptedTemplateProvider(adjust=True)
service=TemplateAuthoringService(TemplateStore(args.directory/'templates.sqlite3'),provider)
if not args.project_post and not service.store.list('run'):
    provider.timeout_phase = 'compare'
    service.asynchronous = False
    draft = service.start({'request_id':str(uuid4()), 'scope':'post',
        'instruction':'A recoverable draft with a persisted preview'})
    assert draft['status'] == 'failed', draft
    provider.timeout_phase = None
    service.asynchronous = True
@asynccontextmanager
async def lifespan(app):
    service.recover_interrupted()
    yield
    service.close()
app=FastAPI(lifespan=lifespan)
def owner(authorization: str=Header(default=''),x_firebase_appcheck: str=Header(default='')):
    if authorization!='Bearer e2e-owner-token' or x_firebase_appcheck!='e2e-app-check':
        raise HTTPException(401,'owner required')
app.include_router(template_router(service,prefix='/api/v1/templates',dependencies=[Depends(owner)]))
if args.project_post:
    from tests.validation_pipeline.test_studio_creatives import StudioCreativeServiceTests, FakeStructuredProvider, FakeImageProvider
    from validation_pipeline.local_brief_store import LocalBriefStore
    from validation_pipeline.studio_creatives import LocalStudioAuthority, StudioCreativeService
    from validation_pipeline.studio_workspace import PostStudioWorkspace
    from validation_pipeline.studio_routes import studio_creative_router
    fixture = StudioCreativeServiceTests()
    fixture.store = LocalBriefStore(args.directory / 'briefs')
    fixture.authority = LocalStudioAuthority(fixture.store)
    fixture.service = StudioCreativeService(root=args.directory/'studio', authority=fixture.authority,
        workspace_factory=lambda path: PostStudioWorkspace(path, image_provider=FakeImageProvider()),
        structured_provider=FakeStructuredProvider(),
        composer_skill_path=ROOT/'skills/studio-creative-composer/SKILL.md',
        phone_skill_path=ROOT/'skills/studio-phone-hero-generator/SKILL.md')
    fixture.service.template_registry = service.post_registry
    if not fixture.store.list('projects'):
        fixture.generate_creative()
        service.asynchronous = False
        run = service.start({'request_id':str(uuid4()), 'scope':'post', 'instruction':'A reusable title image and action'})
        assert run['status']=='proposed', run
        service.decide(run['run_id'], {'request_id':str(uuid4()), 'base_sha256':run['state_sha256'], 'decision':'accept'})
    app.include_router(studio_creative_router(fixture.service, prefix='/api/v1/studio', dependencies=[Depends(owner)]))
    @app.get('/api/v1/projects', dependencies=[Depends(owner)])
    def projects(): return {'items':[{**p, 'brief_count':1, 'status':'completed'} for p in fixture.store.list('projects')]}
    @app.get('/fixture', dependencies=[Depends(owner)])
    def fixture_identity():
        project = fixture.store.list('projects')[0]
        creative = fixture.authority.list_creatives(project['project_id'])[0]
        return {'project_id':project['project_id'], 'creative_id':creative['creative_id']}
@app.get('/healthz')
def health():return {'status':'ok'}
uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='warning')
