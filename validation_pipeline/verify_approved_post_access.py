"""Read-only release check of project publishing sources and immutable PNG bytes."""
import hashlib

import httpx
import psycopg

from .config import Settings


def main() -> None:
    settings = Settings.from_environment()
    with psycopg.connect(settings.database_url) as connection:
        projects = [str(row[0]) for row in connection.execute('SELECT entity_id FROM validation_projects')]
        rows = connection.execute('''SELECT workspace.project_id,workspace.entity_id,version.version,version.render_sha256
            FROM universal_studio_versions version JOIN universal_studio_workspaces workspace
            ON workspace.entity_id=version.workspace_id''').fetchall()
    expected = {(str(row[0]), str(row[1]), int(row[2])): row[3] for row in rows}
    with httpx.Client(base_url='http://127.0.0.1:8080', timeout=30,
                     headers={'X-PTW-Owner-Gateway-Token': settings.owner_gateway_token}) as client:
        for project_id in projects:
            project_expected = {key: digest for key, digest in expected.items() if key[0] == project_id}
            for route in ('ads', 'instagram'):
                response = client.get(f'/internal/v1/{route}/projects/{project_id}')
                if response.status_code != 200:
                    raise RuntimeError(f'{route} source access failed for Project {project_id}: HTTP {response.status_code}')
                actual = {(project_id, item['creative_id'], item['version']): item['render_sha256']
                          for item in response.json()['sources']}
                if actual != project_expected:
                    raise RuntimeError(f'{route} approved sources differ from database authority for Project {project_id}')
            for (_, creative_id, version), digest in project_expected.items():
                response = client.get(f'/internal/v1/studio/projects/{project_id}/creatives/{creative_id}/versions/{version}/render')
                if response.status_code != 200 or hashlib.sha256(response.content).hexdigest() != digest:
                    raise RuntimeError(f'Approved PNG verification failed for Creative {creative_id} version {version}')
    print(f'Approved Post access verified: {len(projects)} Projects, {len(expected)} immutable PNGs; Ads and Instagram sources match PostgreSQL.')


if __name__ == '__main__':
    main()
