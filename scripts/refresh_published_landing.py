#!/usr/bin/env python3
"""Explicitly refresh one published Landing; never enumerate projects for writes.

Run inside Validation after a preserving release, under the host maintenance lock.
The UUID and exact current published digest are required owner-selected boundaries.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
from uuid import UUID, uuid5

import httpx
import psycopg
from psycopg import sql

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validation_pipeline.config import Settings
from validation_pipeline.landing_pages import LandingService, DatabaseLandingAuthority, DatabaseLandingWorkspace
from validation_pipeline.landing_workspace import LandingWorkspace
from validation_pipeline.landing_publication import DatabaseLandingPublicationAuthority
from validation_pipeline.landing_reapply import reapply_approved


def other_applications(url, project):
    result={}
    with psycopg.connect(url) as db:
        for table,key,parent in (
            ('landing_workspaces','entity_id','landing_workspaces'),('landing_workspace_files','landing_id','landing_workspaces'),
            ('landing_assets','landing_id','landing_workspaces'),('landing_versions','landing_id','landing_workspaces'),
            ('landing_generation_runs','landing_id','landing_workspaces'),('landing_checkpoints','landing_id','landing_workspaces'),
            ('landing_publications','entity_id','landing_publications'),('landing_publication_events','publication_id','landing_publications')):
            query=sql.SQL("SELECT count(*),coalesce(sum(hashtextextended(to_jsonb(item)::text,0)::numeric),0)::text FROM {} item JOIN {} parent ON item.{}=parent.entity_id WHERE parent.project_id<>%s").format(sql.Identifier(table),sql.Identifier(parent),sql.Identifier(key))
            result[table]=db.execute(query,(project,)).fetchone()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slug',required=True)
    parser.add_argument('--project-id',required=True,type=UUID)
    parser.add_argument('--expected-version-sha256',required=True)
    parser.add_argument('--request-id',required=True,type=UUID)
    parser.add_argument('--publish',action='store_true',required=True)
    args=parser.parse_args();settings=Settings.from_environment()
    publications=DatabaseLandingPublicationAuthority(settings.database_url)
    publication,event,_,source=publications._active(args.slug)
    project=str(args.project_id)
    if publication['project_id']!=project or source['version_sha256']!=args.expected_version_sha256:
        raise RuntimeError('The published Project or version changed; reconcile publication before retrying')
    before=other_applications(settings.database_url,project)
    print(json.dumps({'stage':'before','project_id':project,'source_version_sha256':args.expected_version_sha256,'other_application_fingerprints':before}),flush=True)
    authority=DatabaseLandingAuthority(settings.database_url)
    with tempfile.TemporaryDirectory(prefix='landing-reapply-') as directory:
        service=LandingService(root=Path(directory),authority=authority,workspace_factory=lambda path:DatabaseLandingWorkspace(LandingWorkspace(path),authority,path.name),
            structured_provider=None,composer_skill_path=settings.landing_composer_skill_path,manual_agent_skill_path=settings.studio_manual_agent_skill_path)
        try:
            target=reapply_approved(service,project_id=project,landing_id=event['landing_id'],version=event['landing_version'],request_id=str(args.request_id),requested_by='owner-authorized-performance-refresh')
            assert target['configuration']==source['configuration'] and target['content']==source['content']
            assert {a['slot']:a['sha256'] for a in target['assets']}=={a['slot']:a['sha256'] for a in source['assets']}
            workspace=service._workspace(target['landing_id']);original_bytes=0;display_bytes=0
            for asset in target['assets']:
                if not asset['sha256']:continue
                raw=(workspace.assets/f"{asset['sha256']}.png").read_bytes();assert sha256(raw).hexdigest()==asset['sha256'];original_bytes+=len(raw)
                entry=next(item for item in asset['history'] if item['selected'])
                variants=entry['variants'];display_bytes+=variants[-1]['byte_count']
                for variant in variants:
                    encoded=workspace.display_image(asset['slot'],asset['sha256'],variant['sha256'])['bytes']
                    assert sha256(encoded).hexdigest()==variant['sha256']
            if display_bytes>original_bytes*.2: raise RuntimeError('Display images did not meet the requested 80% byte reduction')
            base=f'http://127.0.0.1:8080/internal/v1/landings/projects/{project}'
            with httpx.Client(headers={'X-PTW-Owner-Gateway-Token':settings.owner_gateway_token,'X-PTW-Actor':'owner-authorized-performance-refresh'},timeout=120) as client:
                def post(path,body):
                    response=client.post(base+path,json=body);response.raise_for_status();return response.json()
                payload={key:target[key] for key in ('configuration','content')};payload['base_sha256']=target['state_sha256']
                saved=post(f"/pages/{target['landing_id']}/save",payload)['landing']
                payload['base_sha256']=saved['state_sha256'];payload['change_note']='Preserve approved copy and artwork; prepare responsive display images.'
                approved=post(f"/pages/{target['landing_id']}/approve",payload)['landing']
                version=approved['versions'][-1]['version']
                published=post('/publication/publish',{'request_id':str(uuid5(args.request_id,'publish')),'landing_id':target['landing_id'],'version':version})
            assert service.approved_version_detail(project,event['landing_id'],event['landing_version'])['version_sha256']==args.expected_version_sha256
            after=other_applications(settings.database_url,project)
            if before!=after: raise RuntimeError('Another Project application changed during refresh; inspect the recorded scope')
            print(json.dumps({'project_id':project,'slug':args.slug,'previous_landing_id':event['landing_id'],'previous_version':event['landing_version'],'previous_version_sha256':args.expected_version_sha256,
                'landing_id':target['landing_id'],'version':version,'version_sha256':published['event']['landing_version_sha256'],
                'original_bytes':original_bytes,'maximum_display_bytes':display_bytes,'reduction':1-display_bytes/original_bytes,'other_applications_unchanged':True,'other_application_fingerprints':after}),flush=True)
        finally:service.operations.close()


if __name__=='__main__':main()
