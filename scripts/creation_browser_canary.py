#!/usr/bin/env python3
"""Real HTTP/storage/rendering browser fixture; only inference is scripted."""
import argparse
from contextlib import asynccontextmanager
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi import FastAPI, Depends, Header, HTTPException
import uvicorn
from tests.validation_pipeline.test_creation_studio import make_service
from validation_pipeline.creation_routes import creation_router

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, required=True)
parser.add_argument('--directory', type=Path, required=True)
args = parser.parse_args()
if not args.directory.name.startswith('ptw-creation-browser-'):
    raise ValueError('Use a disposable browser directory')
service, _, _ = make_service(args.directory, asynchronous=True)

@asynccontextmanager
async def lifespan(app):
    service.templates.recover_interrupted()
    service.recover_interrupted()
    yield
    service.close()
    service.templates.close()

app = FastAPI(lifespan=lifespan)
def owner(authorization: str = Header(default=''), x_firebase_appcheck: str = Header(default='')):
    if authorization != 'Bearer e2e-owner-token' or x_firebase_appcheck != 'e2e-app-check':
        raise HTTPException(401, 'Owner required')
app.include_router(creation_router(service, prefix='/api/v1/create', dependencies=[Depends(owner)]))
@app.get('/healthz')
def health():
    return {'status': 'ok'}
uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')
