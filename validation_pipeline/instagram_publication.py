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
            row = connection.execute('SELECT entity_id,delivery_jpeg FROM instagram_publications WHERE media_token_sha256=%s', (token_sha,)).fetchone()
        if row is None:
            raise KeyError('Media unavailable')
        return self.get(str(row[0])), bytes(row[1])


class InstagramPublicationService:
    def __init__(self, authority: Any, ads: Any, adapter: Any = None, *, origin: str | None = None, sleep: Any = time.sleep):
        self.authority, self.ads, self.adapter = authority, ads, adapter
        self.origin = media_origin(ads.configuration.instagram_media_origin) if origin is None else origin
        self.sleep = sleep

    def connection(self, *, verify: bool = True) -> dict[str, Any]:
        configured = bool(self.adapter and self.ads.configuration.access_token and self.ads.configuration.page_id
                          and self.ads.configuration.instagram_actor_id)
        result = {'configured': configured, 'verified': False, 'graph_version': self.ads.configuration.graph_version,
                  'required_permissions': PERMISSIONS, 'media_ready': bool(self.origin)}
        if not configured:
            return {**result, 'explanation': 'Configure the Meta token, Facebook Page and professional Instagram account. Export is available.'}
        if not verify:
            return result
        try:
            result.update(self.adapter.publishing_connection())
        except MetaAdsProviderError as error:
            result.update(verified=False, explanation=str(error))
        if not self.origin:
            result.update(verified=False, explanation='Configure a public HTTPS media origin for Instagram. Export is available.')
        return result

    @staticmethod
    def safe(value: dict[str, Any]) -> dict[str, Any]:
        state = {key: item for key, item in value['state'].items() if key != 'media_token'}
        return {key: deepcopy(value[key]) for key in ('publication_id', 'project_id', 'request_id', 'specification', 'created_at')} | state

    def workspace(self, project_id: str) -> dict[str, Any]:
        self.ads.authority.project(_uuid(project_id, 'project_id'))
        return {'connection': self.connection(verify=False), 'sources': self.ads._sources(project_id), 'landing': self.ads.landing(project_id),
                'publications': [self.safe(item) for item in self.authority.list(project_id)]}

    def publications(self, project_id: str) -> dict[str, Any]:
        self.ads.authority.project(_uuid(project_id, 'project_id'))
        return {'items': [self.safe(item) for item in self.authority.list(project_id)]}

    def detail(self, project_id: str, identifier: str) -> dict[str, Any]:
        value = self.authority.get(_uuid(identifier, 'publication_id'))
        if value['project_id'] != _uuid(project_id, 'project_id'):
            raise KeyError('Instagram publication not found in this Project')
        return {**self.safe(value), 'attempts': self.authority.attempts(identifier)}

    def reserve(self, project_id: str, request: Mapping[str, Any], actor: str) -> tuple[dict[str, Any], bool]:
        if set(request) != {'request_id', 'creative_id', 'version', 'caption'}:
            raise ValueError('Instagram publication fields are invalid')
        project_id = _uuid(project_id, 'project_id')
        request_id = _uuid(request['request_id'], 'request_id')
        creative_id = _uuid(request['creative_id'], 'creative_id')
        version = request['version']
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError('Approved Post version must be a positive integer')
        if not isinstance(request['caption'], str):
            raise ValueError('Instagram caption must be text')
        caption = _text(request['caption'], 'caption', 0, 2200)
        fingerprint = _sha({'project_id': project_id, 'creative_id': creative_id, 'version': version, 'caption': caption})
        with self.authority.lock('request:' + request_id):
            previous = self.authority.request(request_id)
            if previous:
                if previous['request_sha256'] != fingerprint:
                    raise ValueError('Request ID was reused with different publication input')
                return self.safe(previous), False
            artifact = self.ads._artifact(project_id, creative_id, version)
            connection = self.connection()
            if not connection['verified']:
                raise RuntimeError(connection.get('explanation', 'Instagram publishing is unavailable'))
            rendered, record = artifact['rendered'], artifact['record']
            jpeg = jpeg_delivery(rendered['bytes'], record['render_sha256'])
            token = secrets.token_urlsafe(32)
            source_id = record.get('version_id') or str(uuid5(NAMESPACE_URL, f"ptw-studio-version:{creative_id}:{version}:{record['version_sha256']}"))
            spec = {'creative_id': creative_id, 'version': version, 'source_version_id': source_id,
                    'source_version_sha256': record['version_sha256'], 'render_sha256': record['render_sha256'],
                    'delivery_sha256': hashlib.sha256(jpeg).hexdigest(), 'caption': caption,
                    'instagram_actor_id': self.ads.configuration.instagram_actor_id, 'instagram': connection.get('instagram'),
                    'landing': self.ads.landing(project_id), 'requested_by': actor}
            value = {'publication_id': new_uuid7(), 'project_id': project_id, 'request_id': request_id,
                     'request_sha256': fingerprint, 'specification': spec, 'created_at': utc_now(),
                     'media_token_sha256': hashlib.sha256(token.encode()).hexdigest(),
                     'state': {'status': 'queued', 'container_id': None, 'media_id': None, 'permalink': None,
                               'publish_started': False, 'media_token': token,
                               'media_expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), 'error': None}}
            return self.safe(self.authority.reserve(value, jpeg)), True

    def media(self, token: str) -> bytes:
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            raise KeyError('Media unavailable')
        value, jpeg = self.authority.delivery(hashlib.sha256(token.encode()).hexdigest())
        state = value['state']
        if state['status'] in TERMINAL or datetime.fromisoformat(state['media_expires_at']) <= datetime.now(timezone.utc):
            raise KeyError('Media unavailable')
        if hashlib.sha256(jpeg).hexdigest() != value['specification']['delivery_sha256']:
            raise KeyError('Media unavailable')
        return jpeg

    def execute(self, identifier: str, *, reconcile_only: bool = False) -> dict[str, Any]:
        with self.authority.lock('publication:' + identifier):
            value = self.authority.get(identifier)
            state = value['state']
            if state['status'] == 'published' and not reconcile_only:
                return self.safe(value)
            try:
                if not self.adapter or value['specification']['instagram_actor_id'] != self.ads.configuration.instagram_actor_id:
                    raise RuntimeError('The selected Instagram account is unavailable or has changed')
                if state.get('media_id'):
                    link = self.adapter.permalink(state['media_id'])
                    if reconcile_only:
                        self.authority.attempt(identifier, 'sync', 'published')
                    return self.safe(self.authority.update(identifier, status='published', permalink=link, error=None, media_token=None))
                container = state.get('container_id')
                if not container:
                    if reconcile_only:
                        return self.safe(value)
                    if datetime.fromisoformat(state['media_expires_at']) <= datetime.now(timezone.utc):
                        raise RuntimeError('Image access expired before preparation; create a new reviewed publication')
                    self.authority.update(identifier, status='creating_container', error=None)
                    container = self.adapter.create_container(f'{self.origin}/api/v1/public/instagram-media/{state["media_token"]}.jpg', value['specification']['caption'])
                    self.authority.update(identifier, container_id=container, status='preparing')
                    self.authority.attempt(identifier, 'container', 'completed')
                status = self.adapter.container_status(container)
                if reconcile_only:
                    self.authority.attempt(identifier, 'sync', status)
                if state.get('publish_started'):
                    # FINISHED after a lost response does not prove no publish happened.
                    result = 'published_unresolved' if status == 'PUBLISHED' else 'uncertain'
                    return self.safe(self.authority.update(identifier, status=result, media_token=None,
                        error='Publication outcome needs reconciliation. Check Instagram before creating another post.'))
                if status in {'ERROR', 'EXPIRED', 'PUBLISHED'}:
                    raise RuntimeError('Existing Instagram container cannot be published; inspect its status')
                if reconcile_only:
                    return self.safe(self.authority.get(identifier))
                for _ in range(5):
                    if status == 'FINISHED':
                        break
                    if status != 'IN_PROGRESS':
                        raise RuntimeError('Instagram container readiness is unknown')
                    self.sleep(60)
                    status = self.adapter.container_status(container)
                if status != 'FINISHED':
                    raise RuntimeError('Instagram image is not ready; retry preparation later')
                self.authority.update(identifier, status='publishing', publish_started=True)
                media_id = self.adapter.publish(container)
                self.authority.update(identifier, media_id=media_id, status='published_unresolved', media_token=None)
                self.authority.attempt(identifier, 'publish', 'completed')
                link = self.adapter.permalink(media_id)
                return self.safe(self.authority.update(identifier, status='published', permalink=link, error=None))
            except Exception as error:
                current = self.authority.get(identifier)['state']
                uncertain = current.get('publish_started', False)
                self.authority.attempt(identifier, current['status'], 'uncertain' if uncertain else 'failed')
                message = ('Publication may have succeeded. Sync status and check Instagram; PTW will not publish it again.' if uncertain
                           else 'Instagram publication failed. Check the connection and retry preparation or export the approved image.')
                if isinstance(error, MetaAdsProviderError):
                    message += ' ' + str(error)
                result = self.authority.update(identifier, status='uncertain' if uncertain else 'failed', error=message)
                return self.safe(result)

    def retry(self, project_id: str, identifier: str) -> dict[str, Any]:
        self.detail(project_id, identifier)
        with self.authority.lock('publication:' + identifier):
            value = self.authority.get(identifier)
            if value['state']['status'] != 'failed' or value['state'].get('publish_started'):
                raise RuntimeError('This publication must be reconciled instead of published again')
            return self.safe(self.authority.update(identifier, status='queued', error=None))

    def recover_interrupted(self) -> list[str]:
        return [item['publication_id'] for item in self.authority.list() if item['state']['status'] not in TERMINAL]
