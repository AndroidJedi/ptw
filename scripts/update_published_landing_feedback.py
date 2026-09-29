#!/usr/bin/env python3
"""Review or explicitly publish a feedback-only revision of one named Landing.

Run inside Validation under the host maintenance lock. Retain the UUID on retry.
This copies approved artwork to a replacement draft; it never rewrites a version.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
from uuid import UUID, uuid5

import httpx
import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validation_pipeline.config import Settings
from validation_pipeline.landing_pages import LandingService, DatabaseLandingAuthority, DatabaseLandingWorkspace
from validation_pipeline.landing_workspace import LandingWorkspace
from validation_pipeline.landing_publication import DatabaseLandingPublicationAuthority
from validation_pipeline.landing_reapply import reapply_approved
from validation_pipeline.landing_marketing import normalize_content


def other_applications(url, project):
    result = {}
    with psycopg.connect(url) as db:
        for table, key, parent in (
            ('landing_workspaces', 'entity_id', 'landing_workspaces'), ('landing_workspace_files', 'landing_id', 'landing_workspaces'),
            ('landing_assets', 'landing_id', 'landing_workspaces'), ('landing_versions', 'landing_id', 'landing_workspaces'),
            ('landing_generation_runs', 'landing_id', 'landing_workspaces'), ('landing_checkpoints', 'landing_id', 'landing_workspaces'),
            ('landing_publications', 'entity_id', 'landing_publications'), ('landing_publication_events', 'publication_id', 'landing_publications'),
        ):
            query = sql.SQL('SELECT count(*),coalesce(sum(hashtextextended(to_jsonb(item)::text,0)::numeric),0)::text FROM {} item JOIN {} parent ON item.{}=parent.entity_id WHERE parent.project_id<>%s').format(sql.Identifier(table), sql.Identifier(parent), sql.Identifier(key))
            result[table] = db.execute(query, (project,)).fetchone()
    return result


def feedback_content(source, examples):
    content = deepcopy(source)
    if 'marketing' not in content:
        raise ValueError('The selected Landing must already have marketing sections')
    content['marketing']['feedback_examples'] = examples
    content['marketing'] = normalize_content(content['marketing'])
    if any(not item['topic'] or not item['statement'] for item in content['marketing']['feedback_examples']):
        raise ValueError('Complete all three feedback examples before publication')
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--project-id', required=True, type=UUID)
    parser.add_argument('--expected-version-sha256', required=True)
    parser.add_argument('--request-id', required=True, type=UUID)
    parser.add_argument('--feedback-file', required=True, type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    settings = Settings.from_environment()
    publications = DatabaseLandingPublicationAuthority(settings.database_url)
    publication, event, _, source = publications._active(args.slug)
    project = str(args.project_id)
    if publication['project_id'] != project or source['version_sha256'] != args.expected_version_sha256:
        raise RuntimeError('Published Project or digest changed; reconcile before retrying')
    revised = feedback_content(source['content'], json.loads(args.feedback_file.read_text()))
    configuration = deepcopy(source['configuration'])
    configuration['marketing']['reference_reviews_enabled'] = True
    print(json.dumps({'stage': 'review', 'project_id': project, 'previous_version_sha256': args.expected_version_sha256,
                      'feedback_examples': revised['marketing']['feedback_examples']}, ensure_ascii=False), flush=True)
    if not args.publish:
        return
    before = other_applications(settings.database_url, project)
    authority = DatabaseLandingAuthority(settings.database_url)
    with tempfile.TemporaryDirectory(prefix='landing-feedback-') as directory:
        service = LandingService(root=Path(directory), authority=authority,
            workspace_factory=lambda path: DatabaseLandingWorkspace(LandingWorkspace(path), authority, path.name),
            structured_provider=None, composer_skill_path=settings.landing_composer_skill_path,
            manual_agent_skill_path=settings.studio_manual_agent_skill_path)
        try:
            original = service.detail(project, event['landing_id'])
            original_version = service.approved_version_detail(project, event['landing_id'], event['landing_version'])
            target = reapply_approved(service, project_id=project, landing_id=event['landing_id'],
                version=event['landing_version'], request_id=str(args.request_id), requested_by='owner-authorized-feedback-revision')
            if target['configuration'] != source['configuration'] or target['content'] != source['content']:
                raise RuntimeError('Replacement draft differs from approved source; reconcile before retrying')
            expected_assets = {a['slot']: a['sha256'] for a in source['assets']}
            if {a['slot']: a['sha256'] for a in target['assets']} != expected_assets:
                raise RuntimeError('Replacement artwork differs from approved source')
            workspace = service._workspace(target['landing_id'])
            for asset in target['assets']:
                if asset['sha256'] and sha256((workspace.assets / f"{asset['sha256']}.png").read_bytes()).hexdigest() != asset['sha256']:
                    raise RuntimeError('Replacement artwork digest mismatch')
            base = f'http://127.0.0.1:8080/internal/v1/landings/projects/{project}'
            with httpx.Client(headers={'X-PTW-Owner-Gateway-Token': settings.owner_gateway_token,
                                      'X-PTW-Actor': 'owner-authorized-feedback-revision'}, timeout=120) as client:
                def post(path, body):
                    response = client.post(base + path, json=body)
                    response.raise_for_status()
                    return response.json()
                payload = {'configuration': configuration, 'content': revised, 'base_sha256': target['state_sha256']}
                saved = post(f"/pages/{target['landing_id']}/save", payload)['landing']
                payload['base_sha256'] = saved['state_sha256']
                payload['change_note'] = 'Restore feedback cards with domain-specific, labelled example expectations.'
                approved = post(f"/pages/{target['landing_id']}/approve", payload)['landing']
                version = approved['versions'][-1]['version']
                published = post('/publication/publish', {'request_id': str(uuid5(args.request_id, 'publish')),
                    'landing_id': target['landing_id'], 'version': version})
            if service.detail(project, event['landing_id']) != original:
                raise RuntimeError('Original draft changed; inspect before continuing')
            if service.approved_version_detail(project, event['landing_id'], event['landing_version']) != original_version:
                raise RuntimeError('Original approved version changed')
            if other_applications(settings.database_url, project) != before:
                raise RuntimeError('Another Project Landing changed')
            print(json.dumps({'stage': 'published', 'project_id': project, 'landing_id': target['landing_id'],
                'version': version, 'version_sha256': published['event']['landing_version_sha256'],
                'original_draft_and_version_unchanged': True, 'other_project_landings_unchanged': True,
                'artwork_digests_unchanged': True}), flush=True)
        finally:
            service.operations.close()


if __name__ == '__main__':
    main()
