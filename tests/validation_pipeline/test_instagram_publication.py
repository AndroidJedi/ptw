from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from validation_pipeline.instagram_publication import (
    InstagramAdapter, InstagramPublicationService, LocalInstagramAuthority, jpeg_delivery,
)
from validation_pipeline.instagram_publication_routes import instagram_router, instagram_media_router
from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.meta_ads import LocalMetaAdsAuthority, MetaAdsConfiguration, MetaAdsService
from test_meta_ads import FakeStudio, FakeWorkspace, PROJECT_ID, CREATIVE_ID, REQUEST_ID


class InstagramFake:
    def __init__(self):
        self.containers = 0
        self.publishes = 0
        self.fail_publish = False
        self.fail_permalink = False
        self.status = 'FINISHED'
        self.url = ''

    def publishing_connection(self):
        return {'verified': True, 'instagram': {'id': '789', 'username': 'example'}}

    def create_container(self, url, caption):
        self.containers += 1
        self.url = url
        return 'container-1'

    def container_status(self, identifier):
        return self.status

    def publish(self, identifier):
        self.publishes += 1
        self.status = 'PUBLISHED'
        if self.fail_publish:
            raise httpx.ReadTimeout('private-token-and-url')
        return 'media-1'

    def permalink(self, identifier):
        if self.fail_permalink:
            raise httpx.ReadTimeout('private-token-and-url')
        return 'https://www.instagram.com/p/abc123/'


class InstagramPublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.store = LocalBriefStore(Path(self.directory.name))
        self.store.append('projects', PROJECT_ID, {'project_id': PROJECT_ID, 'name': 'Example'})
        png = io.BytesIO()
        Image.new('RGB', (1080, 1350), '#3267ff').save(png, format='PNG')
        self.studio = FakeStudio()
        self.studio.workspace = FakeWorkspace()
        self.studio.workspace.png = png.getvalue()
        self.ads = MetaAdsService(LocalMetaAdsAuthority(self.store), self.studio,
            MetaAdsConfiguration(access_token='never-return-this', page_id='456', instagram_actor_id='789'))
        self.adapter = InstagramFake()
        self.authority = LocalInstagramAuthority(self.store)
        self.service = InstagramPublicationService(self.authority, self.ads, self.adapter, origin='https://media.example.com', sleep=lambda _: None)
        self.request = {'request_id': REQUEST_ID, 'creative_id': CREATIVE_ID, 'version': 1, 'caption': 'Approved caption'}

    def tearDown(self):
        self.directory.cleanup()

    def reserve(self):
        return self.service.reserve(PROJECT_ID, self.request, 'owner-test')[0]

    def test_deterministic_jpeg_preserves_approved_png_and_cta_pixels(self):
        png = self.studio.workspace.png
        digest = hashlib.sha256(png).hexdigest()
        jpeg = jpeg_delivery(png, digest)
        self.assertEqual(jpeg, jpeg_delivery(png, digest))
        with Image.open(io.BytesIO(jpeg)) as image:
            self.assertEqual((1080, 1350), image.size)
            self.assertEqual('JPEG', image.format)
            self.assertLess(sum(abs(a-b) for a,b in zip(image.getpixel((100,1300)), (50,103,255))), 8)
        self.assertEqual(png, self.studio.workspace.png)
        with self.assertRaises(ValueError):
            jpeg_delivery(png, '0'*64)

    def test_publish_once_permalink_and_media_expiry(self):
        reserved = self.reserve()
        raw = self.authority.get(reserved['publication_id'])
        token = raw['state']['media_token']
        self.assertTrue(self.service.media(token).startswith(b'\xff\xd8'))
        self.assertNotIn(token, json.dumps(reserved))
        completed = self.service.execute(reserved['publication_id'])
        self.assertEqual('published', completed['status'])
        self.assertEqual('https://www.instagram.com/p/abc123/', completed['permalink'])
        self.service.execute(reserved['publication_id'])
        self.assertEqual(1, self.adapter.publishes)
        with self.assertRaises(KeyError):
            self.service.media(token)
        self.assertEqual(2, len(self.authority.attempts(reserved['publication_id'])))

    def test_replay_and_changed_input(self):
        first = self.reserve()
        self.ads.configuration = MetaAdsConfiguration()  # Reconciliation must not require a still-valid token.
        same, created = self.service.reserve(PROJECT_ID, self.request, 'owner-test')
        self.assertFalse(created)
        self.assertEqual(first['publication_id'], same['publication_id'])
        with self.assertRaises(ValueError):
            self.service.reserve(PROJECT_ID, {**self.request, 'caption': 'changed'}, 'owner-test')

    def test_uncertain_publish_never_republishes_after_restart_or_sync(self):
        value = self.reserve()
        self.adapter.fail_publish = True
        result = self.service.execute(value['publication_id'])
        self.assertEqual('uncertain', result['status'])
        self.assertNotIn('private-token', json.dumps(result))
        restarted = InstagramPublicationService(LocalInstagramAuthority(LocalBriefStore(Path(self.directory.name))), self.ads, self.adapter, origin=self.service.origin)
        result = restarted.execute(value['publication_id'], reconcile_only=True)
        self.assertEqual('published_unresolved', result['status'])
        self.assertEqual([], restarted.recover_interrupted())
        with self.assertRaises(RuntimeError):
            restarted.retry(PROJECT_ID, value['publication_id'])
        restarted.execute(value['publication_id'])
        self.assertEqual(1, self.adapter.publishes)
        self.assertEqual(1, self.adapter.containers)

    def test_link_failure_reconciles_saved_media_id(self):
        value = self.reserve()
        self.adapter.fail_permalink = True
        self.assertEqual('uncertain', self.service.execute(value['publication_id'])['status'])
        self.adapter.fail_permalink = False
        self.assertEqual('published', self.service.execute(value['publication_id'], reconcile_only=True)['status'])
        self.assertEqual(1, self.adapter.publishes)

    def test_crash_before_publish_response_does_not_replay_post(self):
        value = self.reserve()
        self.authority.update(value['publication_id'], container_id='container-1', publish_started=True, status='publishing')
        self.assertEqual([value['publication_id']], self.service.recover_interrupted())
        result = self.service.execute(value['publication_id'])
        self.assertEqual('uncertain', result['status'])
        self.assertEqual(0, self.adapter.publishes)

    def test_account_change_missing_config_and_cross_project(self):
        value = self.reserve()
        self.ads.configuration = MetaAdsConfiguration(access_token='different', page_id='456', instagram_actor_id='999')
        self.assertEqual('failed', self.service.execute(value['publication_id'])['status'])
        self.assertEqual(0, self.adapter.publishes)
        with self.assertRaises(KeyError):
            self.service.detail('01900000-0000-7000-8000-000000000099', value['publication_id'])
        self.service.origin = ''
        self.assertFalse(self.service.connection()['verified'])
        self.assertEqual(2, len(self.service.workspace(PROJECT_ID)['sources']))
        self.assertFalse(self.ads.connection()['verified']) # No Ad Account; organic was independently ready.

    def test_expired_media_and_failed_preparation_retry(self):
        value = self.reserve()
        token = self.authority.get(value['publication_id'])['state']['media_token']
        self.authority.update(value['publication_id'], media_expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
        with self.assertRaises(KeyError):
            self.service.media(token)
        self.assertEqual('failed', self.service.execute(value['publication_id'])['status'])
        self.assertEqual(0, self.adapter.containers)
        self.assertEqual('queued', self.service.retry(PROJECT_ID, value['publication_id'])['status'])

    def test_http_auth_project_scoping_and_public_media_allowlist(self):
        app = FastAPI()
        def auth(x_test: str = Header(default='')):
            if x_test != 'owner':
                raise HTTPException(401)
        app.include_router(instagram_router(self.service, prefix='/api/v1/instagram', dependencies=[Depends(auth)]))
        app.include_router(instagram_media_router(self.service, prefix='/api/v1/public/instagram-media'))
        with TestClient(app) as client:
            base = f'/api/v1/instagram/projects/{PROJECT_ID}'
            self.assertEqual(401, client.get(base).status_code)
            self.assertEqual(200, client.get(base, headers={'X-Test': 'owner'}).status_code)
            value = self.reserve()
            token = self.authority.get(value['publication_id'])['state']['media_token']
            response = client.get(f'/api/v1/public/instagram-media/{token}.jpg')
            self.assertEqual('image/jpeg', response.headers['content-type'])
            self.assertEqual('no-store', response.headers['cache-control'])
            self.assertEqual(404, client.get('/api/v1/public/instagram-media/invalid.jpg').status_code)
            self.assertEqual(400, client.post(base+'/publications', json={**self.request, 'active': True}, headers={'X-Test':'owner'}).status_code)
            response = client.post(base+'/publications', json=self.request, headers={'X-Test':'owner'})
            self.assertEqual(202, response.status_code)
            self.assertFalse(response.json()['created'])
            self.assertNotIn(token, response.text)


class InstagramAdapterTests(unittest.TestCase):
    def test_publishing_permissions_are_independent_of_ads(self):
        requests = []
        def handler(request):
            requests.append(request)
            path = request.url.path
            if path.endswith('/permissions'):
                return httpx.Response(200,json={'data':[{'permission':p, 'status':'granted'} for p in ['instagram_basic','instagram_content_publish','pages_read_engagement']]})
            if path.endswith('/456'):
                return httpx.Response(200,json={'instagram_business_account':{'id':'789','username':'example'}})
            return httpx.Response(200,json={'data':[]})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            adapter = InstagramAdapter(MetaAdsConfiguration(access_token='secret', page_id='456',instagram_actor_id='789'),client=client)
            self.assertTrue(adapter.publishing_connection()['verified'])
            self.assertFalse(any('adaccount' in str(request.url) for request in requests))
            for request in requests:
                self.assertNotIn('secret', str(request.url))
                self.assertEqual('Bearer secret', request.headers['authorization'])
