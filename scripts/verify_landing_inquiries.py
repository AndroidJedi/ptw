#!/usr/bin/env python3
"""Verify private inquiry receipts against disposable PostgreSQL, never a target DB."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_studio_save_restart import wait_database
from scripts.verify_landing_performance import seed, make_service
from tests.validation_pipeline.test_landing_workspace import FakeImages, complete_content
from validation_pipeline.landing_inquiries import LandingInquiries, DatabaseInquiryAudit, inquiry_router, ACTION
from validation_pipeline.landing_publication import DatabaseLandingPublicationAuthority


def fingerprints(url):
    from psycopg import sql
    with psycopg.connect(url) as db:
        tables = db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'commander_audit_events' ORDER BY tablename").fetchall()
        return {table: db.execute(sql.SQL('SELECT count(*),coalesce(sum(hashtextextended(to_jsonb(item)::text,0)::numeric),0)::text FROM {} item').format(sql.Identifier(table))).fetchone() for (table,) in tables}


def verify(url, root):
    project, creative = seed(url)
    service = make_service(url, root, FakeImages())
    try:
        page, _ = service.reserve_from_post(project_id=project, source_creative_id=creative, source_version=1, requested_by='disposable-test')
        landing = page['landing_id']; workspace = service._workspace(landing)
        config = workspace._configuration(); content = complete_content()
        detail = workspace.save_configuration(base_sha256=workspace.state_sha256(), configuration=config, content=content)
        for slot in workspace.visual_slots:
            detail = workspace.generate_visual(base_sha256=detail['state_sha256'], slot=slot, visual_direction='Disposable fixture', prompt='fixture')
        service.authority.update_page(landing, status='draft', state_sha256=detail['state_sha256'])
        service.checkpoint(project, landing, kind='approve', base_sha256=detail['state_sha256'], configuration=config, content=content, change_note='Disposable verification')
        publications = DatabaseLandingPublicationAuthority(url)
        publications.publish(project_id=project, request_id=str(uuid4()), landing_id=landing, version=1, slug='inquiry-check', requested_by='disposable-test')
        snapshot = publications.snapshot('inquiry-check')
        payload = {'request_id': str(uuid4()), 'source': 'apple', 'question': 'Disposable verification question', 'contact': '@disposable_test', 'contact_channel': 'telegram', 'website': '', 'landing_version_sha256': snapshot['version_sha256']}
        before = fingerprints(url)

        def new_service():
            return LandingInquiries(DatabaseInquiryAudit(url), DatabaseLandingPublicationAuthority(url))

        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(lambda _: new_service().submit('inquiry-check', payload), range(4)))
        assert sum(receipt['created'] for receipt in receipts) == 1
        assert all(receipt['accepted'] and 'contact' not in receipt for receipt in receipts)
        assert new_service().submit('inquiry-check', payload)['created'] is False
        inbox = new_service().inbox(project)['items']
        assert len(inbox) == 1 and inbox[0]['contact'] == payload['contact']
        assert inbox[0]['request_id'] == payload['request_id']
        assert before == fingerprints(url), 'Inquiry mutated another authority'
        with psycopg.connect(url) as db:
            row = db.execute('SELECT target_id,details FROM commander_audit_events WHERE id=%s AND action=%s', (payload['request_id'], ACTION)).fetchone()
            assert str(row[0]) == inbox[0]['landing_version_id']
            assert row[1]['project_id'] == project

        app = FastAPI()
        def owner(x_test_owner: str = Header(default='')):
            if x_test_owner != 'disposable-owner':
                raise HTTPException(status_code=401)
        app.include_router(inquiry_router(new_service(), prefix='/public', public=True))
        app.include_router(inquiry_router(new_service(), prefix='/private', public=False, dependencies=[Depends(owner)]))
        with TestClient(app) as client:
            assert client.get(f'/private/projects/{project}/inquiries').status_code == 401
            client.headers['X-Test-Owner'] = 'disposable-owner'
            response = client.get(f'/private/projects/{project}/inquiries')
            assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
            assert response.json()['items'][0]['request_id'] == payload['request_id']
            assert client.post('/public/inquiry-check/inquiries', json={**payload, 'question': 'Changed input'}).status_code == 400
            assert client.post('/public/inquiry-check/inquiries', json={**payload, 'landing_version_sha256': '0' * 64}).status_code == 400
            assert client.post('/public/inquiry-check/inquiries', json={**payload, 'website': 'bot'}).status_code == 400
            for _ in range(29):
                assert client.post('/public/inquiry-check/inquiries', json={**payload, 'request_id': str(uuid4())}).status_code == 202
            assert client.post('/public/inquiry-check/inquiries', json={**payload, 'request_id': str(uuid4())}).status_code == 429
            assert len(new_service().inbox(project)['items']) == 30
            assert before == fingerprints(url)
            publications.unpublish(project_id=project, request_id=str(uuid4()), requested_by='disposable-test')
            assert client.post('/public/inquiry-check/inquiries', json={**payload, 'request_id': str(uuid4())}).status_code == 404
        print('PASS: real PostgreSQL receipts, concurrent/restarted retry, exact version lineage, private inbox/no-store, rate bound, invalid and unpublished-page rejection; other authority fingerprints unchanged')
    finally:
        service.operations.close()


def main():
    name = 'ptw-inquiry-test-' + uuid4().hex[:10]
    subprocess.run(['docker', 'run', '--rm', '-d', '--name', name, '-p', '127.0.0.1::5432', '-e', 'POSTGRES_PASSWORD=disposable-only', '-e', 'POSTGRES_DB=ptw_test', 'postgres:16-alpine'], check=True, stdout=subprocess.DEVNULL)
    try:
        port = subprocess.check_output(['docker', 'port', name, '5432/tcp'], text=True).strip().rsplit(':', 1)[1]
        url = f'postgresql://postgres:disposable-only@127.0.0.1:{port}/ptw_test'
        wait_database(url)
        with psycopg.connect(url, autocommit=True) as db:
            for migration in sorted((ROOT / 'db/migrations').glob('*.sql')):
                db.execute(migration.read_text())
        with tempfile.TemporaryDirectory() as directory:
            verify(url, Path(directory))
    finally:
        subprocess.run(['docker', 'stop', name], check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
