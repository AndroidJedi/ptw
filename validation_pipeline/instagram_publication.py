"""Single-image Instagram publishing with durable identity and bounded media access."""
from __future__ import annotations

import base64
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import os
import re
import secrets
import threading
import time
from typing import Any, Mapping
from urllib.parse import urlsplit
from uuid import UUID, NAMESPACE_URL, uuid5

from commander.ids import new_uuid7
from .local_brief_store import utc_now
from .meta_ads import DatabaseMetaAdsAuthority, MetaAdsAdapter, MetaAdsProviderError, _sha, _uuid, _text

PERMISSIONS = ['pages_show_list', 'instagram_basic', 'instagram_content_publish', 'pages_read_engagement']
ANALYTICS_PERMISSION = 'instagram_manage_insights'
TERMINAL = {'published', 'published_unresolved', 'uncertain', 'failed'}


def jpeg_delivery(png: bytes, digest: str) -> bytes:
    from PIL import Image
    if hashlib.sha256(png).hexdigest() != digest:
        raise ValueError('Approved Post image digest mismatch')
    with Image.open(io.BytesIO(png)) as source:
        source.load()
        if source.width > 1080 or not 0.8 <= source.width / source.height <= 1.91:
            raise ValueError('Approved Post dimensions are unsupported by Instagram')
        rgba = source.convert('RGBA')
        image = Image.new('RGB', rgba.size, 'white')
        image.paste(rgba, mask=rgba.getchannel('A'))
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=95, subsampling=0, optimize=False, progressive=False)
    result = output.getvalue()
    if len(result) > 8 * 1024 * 1024:
        raise ValueError('Instagram image exceeds 8 MB')
    return result


def media_origin(value: str = "") -> str:
    value = (value or os.environ.get('META_INSTAGRAM_MEDIA_ORIGIN', '')).strip().rstrip('/')
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return ''
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.path or parts.query or parts.fragment or port not in {None, 443}
            or parts.hostname in {'localhost', '127.0.0.1', '::1'}):
        return ''
    return value


class InstagramAdapter(MetaAdsAdapter):
    def publishing_connection(self) -> dict[str, Any]:
        permissions = self._call('GET', 'me/permissions', outcome='Instagram permission verification failed')
        granted = {item.get('permission') for item in permissions.get('data', []) if item.get('status') == 'granted'}
        missing = sorted(set(PERMISSIONS) - granted)
        if missing:
            return {'verified': False, 'required_permissions': PERMISSIONS,
                    'explanation': 'Grant Instagram publishing permissions through the hidden-prompt configurator.'}
        page_result = self._call(
            'GET', 'me/accounts',
            params={'fields': 'id,name,instagram_business_account{id,username}', 'limit': 100},
            outcome='Instagram Page connection verification failed',
        )
        pages = page_result.get('data') if isinstance(page_result.get('data'), list) else []
        page = next((item for item in pages if isinstance(item, Mapping)
                     and str(item.get('id')) == self.configuration.page_id), None)
        if page is None:
            raise MetaAdsProviderError('Configured Facebook Page is not assigned to this system user')
        account = page.get('instagram_business_account') or {}
        if str(account.get('id')) != self.configuration.instagram_actor_id:
            raise MetaAdsProviderError('Configured Instagram account does not match the Facebook Page')
        # A bounded read confirms access independently of advertising permissions.
        quota = self._call('GET', f'{self.configuration.instagram_actor_id}/content_publishing_limit',
                   params={'fields': 'config,quota_usage'}, outcome='Instagram publishing quota verification failed')
        for item in quota.get('data', []):
            limit = (item.get('config') or {}).get('quota_total')
            if limit is not None and int(item.get('quota_usage', 0)) >= int(limit):
                raise MetaAdsProviderError('Instagram publishing quota is exhausted; wait before publishing')
        return {'verified': True, 'instagram': {'id': str(account['id']), 'username': account.get('username')},
                'required_permissions': PERMISSIONS}

    def analytics_connection(self) -> dict[str, Any]:
        permissions = self._call('GET', 'me/permissions', outcome='Instagram insights permission verification failed')
        granted = {item.get('permission') for item in permissions.get('data', []) if item.get('status') == 'granted'}
        available = ANALYTICS_PERMISSION in granted
        return {
            'provider': 'instagram', 'configured': True, 'available': available,
            'required_permissions': [ANALYTICS_PERMISSION],
            **({} if available else {'explanation': 'Reauthorize Meta with instagram_manage_insights to collect organic performance.'}),
        }

    def media_insights(self, identifier: str) -> dict[str, Any]:
        if not re.fullmatch(r'[0-9]{1,40}', str(identifier)):
            raise ValueError('Instagram media ID is invalid')
        result = self._call(
            'GET', f'{identifier}/insights',
            params={'metric': 'views,reach,likes,comments,shares,saved,total_interactions'},
            outcome='Instagram media insights refresh failed',
        )
        metrics: dict[str, Any] = {}
        for item in result.get('data', []):
            if not isinstance(item, Mapping):
                continue
            values = item.get('values')
            value = values[-1].get('value') if isinstance(values, list) and values and isinstance(values[-1], Mapping) else item.get('total_value', {}).get('value') if isinstance(item.get('total_value'), Mapping) else None
            if isinstance(item.get('name'), str) and isinstance(value, (int, float, str)):
                metrics[str(item['name'])] = value
        return metrics

    def create_container(self, url: str, caption: str) -> str:
        result = self._call('POST', f'{self.configuration.instagram_actor_id}/media',
                            data={'image_url': url, 'caption': caption}, outcome='Instagram image preparation failed')
        return str(result['id'])

    def container_status(self, identifier: str) -> str:
        result = self._call('GET', identifier, params={'fields': 'status_code'}, outcome='Instagram container status unavailable')
        return str(result.get('status_code', 'UNKNOWN'))

    def publish(self, identifier: str) -> str:
        result = self._call('POST', f'{self.configuration.instagram_actor_id}/media_publish',
                           data={'creation_id': identifier}, outcome='Instagram publication outcome is uncertain')
        return str(result['id'])

    def permalink(self, identifier: str) -> str:
        result = self._call('GET', identifier, params={'fields': 'id,permalink'}, outcome='Instagram post link unavailable')
        url = str(result.get('permalink', ''))
        if not re.fullmatch(r'https://(?:www\.)?instagram\.com/(?:p|reel)/[A-Za-z0-9_-]+/?', url):
            raise MetaAdsProviderError('Instagram returned no valid post link')
        return url


class LocalInstagramAuthority:
    def __init__(self, store: Any):
        self.store = store
        self._lock = threading.RLock()

    @contextmanager
    def lock(self, key: str):
        import fcntl
        path = self.store.root / 'instagram-locks'
        path.mkdir(exist_ok=True)
        with self._lock, (path / hashlib.sha256(key.encode()).hexdigest()).open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def list(self, project_id: str | None = None) -> list[dict[str, Any]]:
        return [item for item in self.store.list('instagram_publications') if project_id is None or item['project_id'] == project_id]

    def get(self, identifier: str) -> dict[str, Any]:
        return self.store.get('instagram_publications', _uuid(identifier, 'publication_id'))

    def request(self, request_id: str) -> dict[str, Any] | None:
        return next((item for item in self.list() if item['request_id'] == request_id), None)

    def reserve(self, record: dict[str, Any], jpeg: bytes) -> dict[str, Any]:
        value = {**deepcopy(record), 'delivery_base64': base64.b64encode(jpeg).decode()}
        self.store.append('instagram_publications', value['publication_id'], value)
        source_id = value['specification']['source_version_id']
        if not self.store.history('studio_versions', source_id):
            self.store.append('studio_versions', source_id, {'version_id': source_id, 'creative_id': value['specification']['creative_id'], 'version': value['specification']['version'], 'version_sha256': value['specification']['source_version_sha256']})
        for source, relation, target in [(value['project_id'], 'contains', value['publication_id']),
                                         (value['publication_id'], 'derived_from', value['specification']['source_version_id'])]:
            self.store.edge(source_id=source, relation=relation, target_id=target)
        landing = value['specification'].get('landing')
        if landing:
            self.store.edge(source_id=value['publication_id'], relation='derived_from', target_id=landing['event_id'])
        return value

    def update(self, identifier: str, **patch: Any) -> dict[str, Any]:
        value = self.get(identifier)
        value['state'] = {**value['state'], **patch, 'updated_at': utc_now()}
        self.store.append('instagram_publications', identifier, value)
        return value

    def attempt(self, identifier: str, stage: str, status: str) -> None:
        attempt_id = new_uuid7()
        self.store.append('instagram_attempts', attempt_id, {'attempt_id': attempt_id, 'publication_id': identifier,
            'stage': stage, 'status': status, 'created_at': utc_now()})
        self.store.edge(source_id=identifier, relation='contains', target_id=attempt_id)

    def attempts(self, identifier: str) -> list[dict[str, Any]]:
        return [item for item in self.store.list('instagram_attempts') if item['publication_id'] == identifier]

    def delivery(self, token_sha: str) -> tuple[dict[str, Any], bytes]:
        value = next((item for item in self.list() if item['media_token_sha256'] == token_sha), None)
        if not value:
            raise KeyError('Media unavailable')
        self.store.get('projects', value['project_id'])
        return value, base64.b64decode(value['delivery_base64'], validate=True)


class DatabaseInstagramAuthority(DatabaseMetaAdsAuthority):
    @contextmanager
    def lock(self, key: str):
        # Session lock spans network calls; all writes commit independently before side effects.
        import psycopg
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            connection.execute('SELECT pg_advisory_lock(hashtextextended(%s,0))', ('instagram:' + key,))
            try:
                yield
            finally:
                connection.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))', ('instagram:' + key,))

    @staticmethod
    def _record(row: Any) -> dict[str, Any]:
        return {'publication_id': str(row[0]), 'project_id': str(row[1]), 'request_id': str(row[2]),
                'request_sha256': row[3], 'specification': dict(row[4]), 'state': dict(row[5]),
                'media_token_sha256': row[6], 'created_at': row[7].isoformat()}

    _select = 'SELECT entity_id,project_id,request_id,request_sha256,specification,state,media_token_sha256,created_at FROM instagram_publications'

    def list(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(self._select + (' WHERE project_id=%s' if project_id else '') + ' ORDER BY created_at DESC',
                                      (UUID(project_id),) if project_id else ()).fetchall()
        return [self._record(row) for row in rows]

    def get(self, identifier: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(self._select + ' WHERE entity_id=%s', (UUID(identifier),)).fetchone()
        if row is None:
            raise KeyError('Instagram publication not found')
        return self._record(row)

    def request(self, request_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(self._select + ' WHERE request_id=%s', (UUID(request_id),)).fetchone()
        return None if row is None else self._record(row)

    def reserve(self, record: dict[str, Any], jpeg: bytes) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        spec = record['specification']
        identifier = record['publication_id']
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'instagram_publication',%s)",
                               (UUID(identifier), Jsonb({'project_id': record['project_id']})))
            connection.execute('''INSERT INTO instagram_publications(entity_id,project_id,source_creative_id,source_version_id,
                request_id,request_sha256,specification,state,delivery_jpeg,media_token_sha256)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (UUID(identifier), UUID(record['project_id']), UUID(spec['creative_id']), UUID(spec['source_version_id']),
                 UUID(record['request_id']), record['request_sha256'], Jsonb(spec), Jsonb(record['state']), jpeg, record['media_token_sha256']))
            self._edge(connection, record['project_id'], 'contains', identifier, {'member': 'instagram_publication'})
            self._edge(connection, identifier, 'derived_from', spec['source_version_id'], {'input': 'approved_post'})
            if spec.get('landing'):
                self._edge(connection, identifier, 'derived_from', spec['landing']['event_id'], {'input': 'published_landing'})
        return self.get(identifier)

    def update(self, identifier: str, **patch: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute('UPDATE instagram_publications SET state=state || %s WHERE entity_id=%s',
                               (Jsonb({**patch, 'updated_at': utc_now()}), UUID(identifier)))
        return self.get(identifier)

    def attempt(self, identifier: str, stage: str, status: str) -> None:
        from psycopg.types.json import Jsonb
        attempt_id = new_uuid7()
        record = {'attempt_id': attempt_id, 'publication_id': identifier, 'stage': stage, 'status': status, 'created_at': utc_now()}
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'instagram_publication_attempt',%s)",
                               (UUID(attempt_id), Jsonb({'stage': stage})))
            connection.execute('INSERT INTO instagram_publication_attempts(entity_id,publication_id,record) VALUES(%s,%s,%s)',
                               (UUID(attempt_id), UUID(identifier), Jsonb(record)))
            self._edge(connection, identifier, 'contains', attempt_id, {'member': 'instagram_publication_attempt'})

    def attempts(self, identifier: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return [dict(row[0]) for row in connection.execute('SELECT record FROM instagram_publication_attempts WHERE publication_id=%s ORDER BY created_at', (UUID(identifier),)).fetchall()]

    def delivery(self, token_sha: str) -> tuple[dict[str, Any], bytes]:
        with self.connection() as connection:
            row = connection.execute(
                '''SELECT publication.entity_id,publication.delivery_jpeg
                     FROM instagram_publications publication
                     JOIN validation_projects project ON project.entity_id=publication.project_id
                    WHERE publication.media_token_sha256=%s AND project.deleted_at IS NULL''',
                (token_sha,),
            ).fetchone()
        if row is None:
            raise KeyError('Media unavailable')
        return self.get(str(row[0])), bytes(row[1])


class InstagramPublicationService:
    def __init__(self, authority: Any, ads: Any, adapter: Any = None, *, origin: str | None = None, sleep: Any = time.sleep):
        from .social_publishing.engine import SocialPublishingEngine
        from .social_publishing.providers.instagram import InstagramPublishingAdapter
        self.authority, self.ads, self.adapter = authority, ads, adapter
        self._origin = media_origin(ads.configuration.instagram_media_origin) if origin is None else origin
        self.sleep = sleep
        self.publisher = InstagramPublishingAdapter(
            ads, adapter, origin=self._origin, sleep=sleep,
        )
        self.engine = SocialPublishingEngine(
            authority, ads, self.publisher, origin=self._origin,
        )

    @property
    def origin(self) -> str:
        return self._origin

    @origin.setter
    def origin(self, value: str) -> None:
        self._origin = value
        self.publisher.origin = value
        self.engine.origin = value.rstrip('/')

    def connection(self, *, verify: bool = True) -> dict[str, Any]:
        return self.engine.connection(verify=verify)

    def safe(self, value: dict[str, Any]) -> dict[str, Any]:
        return self.engine.safe(value)

    def workspace(self, project_id: str) -> dict[str, Any]:
        return self.engine.workspace(project_id)

    def analytics_connection(self, *, verify: bool = True) -> dict[str, Any]:
        if self.adapter is None or not self.ads.configuration.access_token:
            return {'provider': 'instagram', 'configured': False, 'available': False,
                    'required_permissions': [ANALYTICS_PERMISSION],
                    'explanation': 'Configure the Meta connection before collecting Instagram insights.'}
        if not verify:
            return {'provider': 'instagram', 'configured': True, 'available': None,
                    'required_permissions': [ANALYTICS_PERMISSION],
                    'explanation': 'Use Refresh to verify the separate Instagram insights permission.'}
        try:
            return self.adapter.analytics_connection()
        except (MetaAdsProviderError, RuntimeError) as error:
            return {'provider': 'instagram', 'configured': True, 'available': False,
                    'required_permissions': [ANALYTICS_PERMISSION], 'explanation': str(error)}

    def insights(self, post_ids: list[str]) -> dict[str, Any]:
        readiness = self.analytics_connection(verify=True)
        if not readiness.get('available'):
            raise RuntimeError(str(readiness.get('explanation') or 'Instagram analytics is unavailable'))
        if len(post_ids) != 1:
            raise ValueError('Instagram insight refresh requires one published media ID')
        return self.adapter.media_insights(post_ids[0])

    def publications(self, project_id: str) -> dict[str, Any]:
        return self.engine.publications(project_id)

    def detail(self, project_id: str, identifier: str) -> dict[str, Any]:
        return self.engine.detail(project_id, identifier)

    def reserve(self, project_id: str, request: Mapping[str, Any], actor: str) -> tuple[dict[str, Any], bool]:
        return self.engine.reserve(project_id, request, actor)

    def media(self, token: str) -> bytes:
        return self.engine.media(token)

    def execute(self, identifier: str, *, reconcile_only: bool = False) -> dict[str, Any]:
        return self.engine.execute(identifier, reconcile_only=reconcile_only)

    def retry(self, project_id: str, identifier: str) -> dict[str, Any]:
        return self.engine.retry(project_id, identifier)

    def recover_interrupted(self) -> list[str]:
        return self.engine.recover_interrupted()

    def maintain(self) -> None:
        self.engine.maintain()
