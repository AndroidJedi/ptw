#!/usr/bin/env python3
"""Verify migration and publication persistence using a disposable PostgreSQL only."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import re
from types import SimpleNamespace
import sys
import time
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests/validation_pipeline')]
from test_meta_ads import FakeAdapter, FakeStudio, FakeWorkspace, PROJECT_ID, CREATIVE_ID, BRIEF_ID, REQUEST_ID
from test_instagram_publication import InstagramFake
from validation_pipeline.meta_ads import DatabaseMetaAdsAuthority, MetaAdsConfiguration, MetaAdsService
from validation_pipeline.instagram_publication import DatabaseInstagramAuthority, InstagramPublicationService


def main():
    name = 'ptw-instagram-test-' + uuid4().hex[:12]
    subprocess.run(['docker', 'run', '--rm', '-d', '--name', name, '-p', '127.0.0.1::5432',
                    '-e', 'POSTGRES_PASSWORD=disposable-only', '-e', 'POSTGRES_DB=ptw_test', 'postgres:16-alpine'], check=True, stdout=subprocess.DEVNULL)
    try:
        port = subprocess.check_output(['docker', 'port', name, '5432/tcp'], text=True).strip().rsplit(':',1)[1]
        url = f'postgresql://postgres:disposable-only@127.0.0.1:{port}/ptw_test'
        for _ in range(40):
            try:
                with psycopg.connect(url) as connection:
                    connection.execute('SELECT 1')
                break
            except psycopg.OperationalError:
                time.sleep(0.25)
        with psycopg.connect(url, autocommit=True) as connection:
            for path in sorted((ROOT/'db/migrations').glob('*.sql'))[:4]:
                connection.execute(path.read_text())
            source_id = '01900000-0000-7000-8000-000000000010'
            version_id = '01900000-0000-7000-8000-000000000005'
            campaign_id = '01900000-0000-7000-8000-000000000015'
            for identifier, kind in [(source_id,'source'),(PROJECT_ID,'validation_project'),(BRIEF_ID,'product_brief'),(CREATIVE_ID,'studio_workspace'),(version_id,'studio_version'),(campaign_id,'meta_ads_experiment')]:
                connection.execute('INSERT INTO commander_entities(id,kind) VALUES(%s,%s)',(identifier,kind))
            connection.execute("INSERT INTO commander_sources(entity_id,source_type,title,provider,external_id,content,content_sha256) VALUES(%s,'owner_idea','Test','owner','test','test',%s)",(source_id,'a'*64))
            connection.execute("INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by) VALUES(%s,%s,%s,'Test','owner','test')",(PROJECT_ID,str(uuid4()),source_id))
            connection.execute("INSERT INTO product_briefs(entity_id,project_id,request_id,owner_idea_source_id,status,requested_by) VALUES(%s,%s,%s,%s,'completed','test')",(BRIEF_ID,PROJECT_ID,str(uuid4()),source_id))
            connection.execute("INSERT INTO universal_studio_workspaces(entity_id,project_id,source_brief_id,ordinal,origin,template_id,status,requested_by) VALUES(%s,%s,%s,1,'brief_generation','phone_metrics','draft','test')",(CREATIVE_ID,PROJECT_ID,BRIEF_ID))
            png = io.BytesIO()
            Image.new('RGB',(1080,1350),'#3267ff').save(png,format='PNG')
            studio = FakeStudio(); studio.workspace = FakeWorkspace(); studio.workspace.png = png.getvalue()
            record = studio.workspace.version_detail(1)
            connection.execute('INSERT INTO universal_studio_versions(entity_id,workspace_id,version,version_sha256,state_sha256,render_sha256,record,render_png) VALUES(%s,%s,1,%s,%s,%s,%s,%s)',(version_id,CREATIVE_ID,record['version_sha256'],'a'*64,record['render_sha256'],Jsonb(record),png.getvalue()))
            connection.execute("INSERT INTO meta_ads_workspaces(entity_id,project_id,campaign_name,special_ad_categories,meta_campaign_id,status) VALUES(%s,%s,'Existing Direct','[\"NONE\"]','old-meta-id','staged')",(campaign_id,PROJECT_ID))
            tables = [row[0] for row in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
            baseline = {table: connection.execute(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text').fetchall() for table in tables}
            # Exercise the deployer's actual heredocs with psql variables/stdin,
            # including preservation of defaulted new columns and Landing tables.
            deployer = (ROOT/'scripts/deploy_ptw_in_place.sh').read_text()
            snapshot = deployer.split('snapshot_database() {', 1)[1].split('\n}\n', 1)[0]
            sql_blocks = re.findall(r"<<'SQL'\n(.*?)\nSQL", snapshot, re.S)
            assert len(sql_blocks) == 2
            def psql(sql, *args):
                return subprocess.check_output(['docker','exec','-i',name,'psql','-X','-qAt',
                    '-v','ON_ERROR_STOP=1','-U','postgres','-d','ptw_test',*args], input=sql, text=True).strip()
            baseline_schema = psql(sql_blocks[0])
            before_fingerprints = psql(sql_blocks[1], '-v', 'baseline_schema=' + baseline_schema)
            assert 'landing_workspaces=' in before_fingerprints
            connection.execute((ROOT/'db/migrations/005_instagram_publication_v1.sql').read_text())
            assert psql(sql_blocks[1], '-v', 'baseline_schema=' + baseline_schema) == before_fingerprints
            connection.execute("UPDATE validation_projects SET name='Changed' WHERE entity_id=%s", (PROJECT_ID,))
            assert psql(sql_blocks[1], '-v', 'baseline_schema=' + baseline_schema) != before_fingerprints
            connection.execute("UPDATE validation_projects SET name='Test' WHERE entity_id=%s", (PROJECT_ID,))
            for table in tables:
                after = connection.execute(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text').fetchall()
                if table == 'meta_ads_workspaces':
                    after = [({key:value for key,value in row[0].items() if key != 'objective'},) for row in after]
                assert after == baseline[table], f'Existing rows changed: {table}'
            authority = DatabaseMetaAdsAuthority(url)
            direct = authority.ensure_experiment(PROJECT_ID,'ignored',['NONE'])
            assert direct['meta_campaign_id'] == 'old-meta-id'
            traffic = authority.ensure_experiment(PROJECT_ID,'Website',['NONE'],'OUTCOME_TRAFFIC')
            assert traffic['experiment_id'] != direct['experiment_id']
            assert authority.ensure_experiment(PROJECT_ID,'ignored',['NONE'],'OUTCOME_TRAFFIC')['experiment_id'] == traffic['experiment_id']
            authority.update_experiment(traffic['experiment_id'], meta_campaign_id='website-meta-id', status='staged')
            assert authority.get_experiment(PROJECT_ID,direct['experiment_id'])['meta_campaign_id'] == 'old-meta-id'
            ads = MetaAdsService(authority,studio,MetaAdsConfiguration(access_token='test-only',page_id='456',instagram_actor_id='789'))
            event_id = str(uuid4())
            connection.execute("INSERT INTO commander_entities(id,kind) VALUES(%s,'landing_publication_event')", (event_id,))
            landing = {'publication_id': str(uuid4()), 'current_event_id': event_id, 'status': 'published',
                'canonical_url': 'https://natal-service.com/la/example', 'events': [
                    {'event_id': event_id, 'landing_version': 1, 'landing_version_sha256': 'a'*64}]}
            ads.configuration = MetaAdsConfiguration(access_token='test-only',ad_account_id='123',page_id='456',instagram_actor_id='789')
            ads.adapter = FakeAdapter()
            ads.landing_publications = SimpleNamespace(get=lambda _: landing)
            preset = ads.create_preset({'name':'Test audience','countries':['UA'],'age_min':25,'age_max':44,'gender':'all','daily_budget_minor':500})['preset']
            ad_request = {'request_id': str(uuid4()), 'creative_id':CREATIVE_ID,'version':1,'preset_id':preset['preset_id'],
                'headline':'Approved title','primary_text':'Approved text','special_ad_categories':['NONE'],
                'destination_type':'WEBSITE','landing_event_id':event_id}
            deployment, created = ads.reserve(PROJECT_ID,ad_request)
            assert created and deployment['experiment_id'] == traffic['experiment_id']
            assert ads.execute(deployment['deployment_id'])['status'] == 'staged'
            assert ads.reserve(PROJECT_ID,ad_request)[1] is False
            assert connection.execute("SELECT count(*) FROM commander_relationships WHERE source_id=%s AND target_id=%s AND relation='derived_from'", (deployment['deployment_id'],event_id)).fetchone()[0] == 1
            publishing = InstagramPublicationService(DatabaseInstagramAuthority(url),ads,InstagramFake(),origin='https://test.example')
            request = {'request_id':REQUEST_ID,'creative_id':CREATIVE_ID,'version':1,'caption':'Reviewed caption'}
            value, created = publishing.reserve(PROJECT_ID,request,'test')
            assert created
            raw = publishing.authority.get(value['publication_id'])
            token = raw['state']['media_token']
            assert hashlib.sha256(publishing.media(token)).hexdigest() == value['specification']['delivery_sha256']
            result = publishing.execute(value['publication_id'])
            assert result['status'] == 'published', result
            restarted = InstagramPublicationService(DatabaseInstagramAuthority(url),ads,InstagramFake(),origin='https://test.example')
            replay, created = restarted.reserve(PROJECT_ID,request,'test')
            assert not created and replay['permalink'] == result['permalink']
            assert not restarted.recover_interrupted()
            assert len(restarted.authority.attempts(value['publication_id'])) == 2
            for sql, params in [
                ("UPDATE instagram_publications SET specification='{}' WHERE entity_id=%s", (value['publication_id'],)),
                ("UPDATE instagram_publications SET state=state || '{\"publish_started\":false}' WHERE entity_id=%s",(value['publication_id'],)),
                ("DELETE FROM instagram_publication_attempts WHERE publication_id=%s",(value['publication_id'],)),
                ("UPDATE meta_ads_workspaces SET objective='OUTCOME_ENGAGEMENT' WHERE entity_id=%s",(traffic['experiment_id'],)),
            ]:
                try:
                    connection.execute(sql,params)
                except psycopg.Error:
                    pass
                else:
                    raise AssertionError('Immutable data was writable')
            rows = connection.execute('SELECT relation FROM commander_relationships WHERE source_id=%s',(value['publication_id'],)).fetchall()
            assert ('derived_from',) in rows and ('contains',) in rows
            print('PASS: migration preserves prior rows; campaign identities, JPEG persistence, graph lineage, restart/replay and immutable guards verified in disposable PostgreSQL.')
    finally:
        subprocess.run(['docker','stop',name],check=True,stdout=subprocess.DEVNULL)

if __name__ == '__main__':
    main()
