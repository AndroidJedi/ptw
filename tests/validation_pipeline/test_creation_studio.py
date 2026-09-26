from copy import deepcopy
import base64
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
import zipfile

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from tests.validation_pipeline.test_local_briefs import BRIEF
from tests.validation_pipeline.test_template_authoring import ScriptedTemplateProvider
from validation_pipeline.creation_studio import CreationStudio, BriefAdapter, XhighProvider
from validation_pipeline.creation_export import export_bundle, landing_html
from validation_pipeline.creation_routes import creation_router
from validation_pipeline.local_briefs import LocalBriefService
from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.template_authoring import TemplateAuthoringService
from validation_pipeline.template_components import sha
from validation_pipeline.template_store import TemplateStore, TemplateConflict

ROOT = Path(__file__).resolve().parents[2]


class CreationProvider(ScriptedTemplateProvider):
    def __init__(self):
        super().__init__()
        self.model = 'scripted-creation-test'
        self.fail_bind = False
        self.repair_crop = False
        self.review_count = 0
        self.compose_timeouts = 0
        self.pause_comparison = False
        self.invalid_composition = False

    def call(self, **kwargs):
        phase = kwargs['input_payload'].get('phase')
        if kwargs['mode'].startswith('product_brief'):
            if '[design timeout]' in str(kwargs['input_payload']):
                self.compose_timeouts = 2
            value = deepcopy(BRIEF)
            if kwargs['mode'] == 'product_brief_revision':
                value['product'] = 'Calm focus planner'
        elif phase == 'observe':
            value = {'description': 'A focus planner', 'style': 'Large typography, clear image and action.', 'photo_indexes': [0] if 'source_photo_0' in kwargs['input_payload'].get('image_order', []) else []}
        elif phase == 'bind':
            if self.fail_bind:
                raise TimeoutError('never expose raw stderr')
            value = {'bindings': {}, 'image_direction': 'A calm workspace with a notebook and soft daylight, without text.', 'replace_image': False}
            for surface, doc in kwargs['input_payload']['definitions'].items():
                value['bindings'][surface] = {c['id']: {'title': 'A calmer daily plan', 'support': 'Bring priorities together. Free early access.', 'action': 'Request early access'}.get(c['id'], 'Plan your day') for c in doc['components'] if c['type'] in {'text', 'button'}}
        elif phase == 'review':
            value = {'ready': True, 'issues': [], 'edits': []}
            self.review_count += 1
            if self.repair_crop and self.review_count == 1:
                value = {'ready': False, 'issues': ['Keep the complete subject on mobile.'], 'edits': [{'surface': 'landing', 'path': 'components.visual.fit', 'value': 'contain'}]}
        elif phase == 'compose' and self.compose_timeouts:
            self.compose_timeouts -= 1
            self.calls.append(kwargs)
            raise TimeoutError('private provider stderr')
        elif phase == 'compose' and self.invalid_composition:
            self.invalid_composition = False
            value = {'complete': False, 'differences': [], 'capability_gap': None,
                     'edits': [{'surface': 'post', 'path': 'components.title.radius', 'value': 999}]}
        elif phase == 'compare' and self.pause_comparison:
            self.pause_comparison = False
            value = {'complete': False, 'edits': [], 'capability_gap': None, 'differences': [
                {'surface': 'post', 'role': 'cta', 'severity': 'meaningful', 'solvable': True, 'issue': 'The action needs more space.'}]}
        else:
            return super().call(**kwargs)
        self.calls.append(kwargs)
        return {'response': kwargs['response_validator'](value), 'invocation': {'provider': 'scripted', 'model': self.model}}


class CreationImages:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        output = BytesIO()
        Image.new('RGB', (1000, 700), '#BBCDBB').save(output, format='PNG')
        return {'bytes': output.getvalue(), 'source': {'origin': 'scripted_test_fixture'}}


def make_service(path, *, asynchronous=False):
    provider = CreationProvider()
    briefs = LocalBriefService(store=LocalBriefStore(path/'briefs'), provider=XhighProvider(provider), repository_root=ROOT)
    templates = TemplateAuthoringService(TemplateStore(path/'templates.sqlite3'), provider, asynchronous=asynchronous)
    service = CreationStudio(TemplateStore(path/'creation.sqlite3', namespace='creation_studio'), templates, provider, BriefAdapter(briefs, briefs, local=True), CreationImages(), asynchronous=asynchronous)
    return service, briefs, provider


class CreationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='ptw-creation-test-')
        self.root = Path(self.directory.name)
        self.service, self.briefs, self.provider = make_service(self.root)
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.service.templates.close)
        self.addCleanup(self.service.close)

    def request(self, **changes):
        return {'request_id': str(uuid4()), 'mode': 'pack', 'scope': 'combined', 'instruction': 'A calm daily planner', 'url': '', 'language': 'en', 'reuse_images': False, 'reference_ids': [], **changes}

    def start(self, **changes):
        return self.service.start(self.request(**changes))

    def test_package_is_durable_and_exportable_without_approving_domain_entities(self):
        request = self.request()
        run = self.service.start(request)
        self.assertEqual('ready', run['status'], run.get('error'))
        self.assertEqual({'post:desktop', 'landing:desktop', 'landing:mobile'}, set(run['previews']))
        self.assertFalse(self.briefs.get_brief(run['brief']['brief_id'])['approved'])
        self.assertEqual([], self.briefs.store.list('creatives'))
        self.assertEqual([], self.briefs.store.list('landings'))
        before = len(self.provider.calls)
        self.assertEqual(run['state_sha256'], self.service.start(request)['state_sha256'])
        self.assertEqual(before, len(self.provider.calls))
        restored = TemplateStore(self.root/'creation.sqlite3', namespace='creation_studio').get('run', run['run_id'])
        self.assertEqual(run, restored)
        with zipfile.ZipFile(BytesIO(export_bundle(self.service, run))) as bundle:
            self.assertIn('landing.html', bundle.namelist())
            html = bundle.read('landing.html').decode()
            self.assertIn('<h1 id="title">A calmer daily plan</h1>', html)
            self.assertIn('@media(max-width:600px)', html)
            self.assertNotIn('<script', html)
            self.assertIn('disabled>', html)
            self.assertIn('alt="Natal"', html)
        self.assertTrue(all(c.get('reasoning_effort') == 'xhigh' for c in self.provider.calls))

    def test_brief_correction_preserves_learning_and_rebuilds_bound_copy(self):
        run = self.start()
        previous = run['brief']['brief_id']
        images_before = self.service.image_provider.calls
        edited = self.service.mutate(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256'], 'target': 'brief', 'instruction': 'Emphasize calmer focus'}, action='edit')
        self.assertEqual('ready', edited['status'], edited.get('error'))
        self.assertNotEqual(previous, edited['brief']['brief_id'])
        self.assertEqual('Calm focus planner', edited['brief']['document']['product'])
        self.assertEqual(1, len(self.briefs.store.list('feedback')))
        self.assertEqual(1, len(self.briefs.store.list('weight_updates')))
        self.assertEqual(images_before, self.service.image_provider.calls)
        with self.assertRaises(TemplateConflict):
            self.service.mutate(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256']}, action='retry')

    def test_provider_failure_keeps_stage_and_retry_does_not_duplicate_brief_or_design(self):
        self.provider.fail_bind = True
        run = self.start(mode='post')
        self.assertEqual('failed', run['status'])
        self.assertEqual('content', run['failed_stage'])
        self.assertNotIn('stderr', run['error'])
        self.provider.fail_bind = False
        resumed = self.service.mutate(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256']}, action='retry')
        self.assertEqual('ready', resumed['status'], resumed.get('error'))
        self.assertEqual(run['brief'], resumed['brief'])
        self.assertEqual(run['template_run_id'], resumed['template_run_id'])
        self.assertEqual(1, len(self.briefs.store.list('briefs')))

    def test_design_timeout_retries_once_automatically(self):
        self.provider.compose_timeouts = 1
        run = self.start(mode='post')
        self.assertEqual('ready', run['status'], run.get('error'))
        self.assertEqual(1, run['design_retries'])
        self.assertEqual(2, len([c for c in self.provider.calls if c['input_payload'].get('phase') == 'compose']))
        self.assertEqual(1, len(self.briefs.store.list('briefs')))

    def test_repeated_design_timeout_has_actionable_recovery_and_keeps_saved_brief(self):
        self.provider.compose_timeouts = 2
        run = self.start(mode='post')
        self.assertEqual('failed', run['status'])
        self.assertEqual(1, run['design_retries'])
        self.assertEqual(2, len([c for c in self.provider.calls if c['input_payload'].get('phase') == 'compose']))
        # The previously shipped UI recorded the same timeout as needs_review.
        run = self.service.update(run, status='needs_review', error='The design needs another agent pass.')
        detail = self.service.describe(run)
        self.assertEqual('design_timeout', detail['recovery']['code'])
        self.assertTrue(detail['recovery']['can_retry'])
        self.assertNotIn('stderr', str(detail))
        self.assertEqual(run['state_sha256'], detail['state_sha256'])
        self.assertNotIn('recovery', self.service.get(run['run_id']))
        request = {'request_id': str(uuid4()), 'base_sha256': run['state_sha256']}
        resumed = self.service.mutate(run['run_id'], request, action='retry')
        self.assertEqual('ready', resumed['status'], resumed.get('error'))
        self.assertEqual(run['brief'], resumed['brief'])
        self.assertEqual(run['template_run_id'], resumed['template_run_id'])
        count = len(self.provider.calls)
        self.assertEqual(resumed, self.service.mutate(run['run_id'], request, action='retry'))
        self.assertEqual(count, len(self.provider.calls))

    def test_layout_retry_refines_instead_of_repeating_unchanged_comparison(self):
        self.provider.pause_comparison = True
        run = self.start(mode='post')
        self.assertEqual('needs_review', run['status'])
        self.assertEqual('design_adjustment', self.service.describe(run)['recovery']['code'])
        resumed = self.service.mutate(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256']}, action='retry')
        self.assertEqual('ready', resumed['status'], resumed.get('error'))
        compose = [c for c in self.provider.calls if c['input_payload'].get('phase') == 'compose']
        self.assertEqual(2, len(compose))
        self.assertIn('The action needs more space.', compose[-1]['input_payload']['instruction'])
        self.assertEqual(run['brief'], resumed['brief'])

    def test_invalid_design_retry_carries_the_exact_validation_issue(self):
        self.provider.invalid_composition = True
        run = self.start(mode='post')
        self.assertEqual('failed', run['status'])
        self.assertEqual('design_invalid', self.service.describe(run)['recovery']['code'])
        resumed = self.service.mutate(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256']}, action='retry')
        self.assertEqual('ready', resumed['status'], resumed.get('error'))
        compose = [c for c in self.provider.calls if c['input_payload'].get('phase') == 'compose'][-1]
        self.assertIn('title.radius must be a finite number between 0 and 200', compose['input_payload']['instruction'])
        self.assertIn('A calm daily planner', compose['input_payload']['instruction'])
        self.assertEqual(run['brief'], resumed['brief'])

    def test_unfixable_review_does_not_offer_or_execute_a_noop_retry(self):
        run = self.start(mode='post')
        run = self.service.update(run, status='needs_review', failed_stage='review', visual_review={'ready': False, 'issues': ['The image needs a different subject.'], 'edits': []})
        self.assertFalse(self.service.describe(run)['recovery']['can_retry'])
        with self.assertRaisesRegex(TemplateConflict, 'repeating the same step'):
            self.service.mutate(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256']}, action='retry')

    def test_templates_accept_exact_pair_without_creating_a_project(self):
        run = self.start(mode='templates')
        self.assertEqual('ready', run['status'], run.get('error'))
        self.assertIsNone(run['brief'])
        self.assertEqual([], self.briefs.list_projects())
        run = self.service.mutate(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256']}, action='accept')
        self.assertEqual('ready', run['status'], run.get('error'))
        self.assertEqual(2, len(run['template_versions']))
        post, landing = run['template_versions']
        self.assertEqual({k:v for k,v in post.items() if k != 'surface'}, self.service.templates.read(landing)['post_reference'])

    def test_saved_pair_can_populate_another_idea_and_edits_create_a_derivative(self):
        template = self.start(mode='templates')
        template = self.service.mutate(template['run_id'], {'request_id': str(uuid4()), 'base_sha256': template['state_sha256']}, action='accept')
        source = self.service.templates.store.get('run', template['template_run_id'])
        before = len([c for c in self.provider.calls if c['input_payload'].get('phase') == 'compose'])
        run = self.start(template_source_id=source['run_id'])
        self.assertEqual('ready', run['status'], run.get('error'))
        self.assertEqual(source['documents'], run['documents'])
        self.assertEqual(before, len([c for c in self.provider.calls if c['input_payload'].get('phase') == 'compose']))
        landing = deepcopy(run['documents']['landing'])
        edited = self.service.mutate(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256'], 'target': 'post', 'instruction': 'Make the post warmer'}, action='edit')
        self.assertEqual('ready', edited['status'], edited.get('error'))
        self.assertNotEqual(source['run_id'], edited['template_run_id'])
        self.assertEqual(source, self.service.templates.store.get('run', source['run_id']))
        self.assertEqual(landing, edited['documents']['landing'])
        self.assertEqual(run['previews']['landing:desktop'], edited['previews']['landing:desktop'])
        self.assertEqual(run['brief'], edited['brief'])
        compose = [c for c in self.provider.calls if c['input_payload'].get('phase') == 'compose'][-1]
        self.assertEqual(['post'], compose['input_payload']['editable_surfaces'])
        with self.assertRaisesRegex(ValueError, 'did not authorize'):
            compose['response_validator']({'edits': [{'surface': 'landing', 'path': 'background', 'value': '#FFFFFF'}], 'differences': [], 'capability_gap': None, 'complete': False})

    def test_import_keeps_reviewed_template_identity_and_does_not_invent_a_provider_call(self):
        source = self.service.templates.start({'request_id': str(uuid4()), 'scope': 'combined', 'instruction': 'A Natal template pair'})
        count = len(self.provider.calls)
        request = {'request_id': str(uuid4()), 'template_run_id': source['run_id'], 'base_sha256': source['state_sha256']}
        run = self.service.import_template(request)
        self.assertEqual('ready', run['status'])
        self.assertEqual(count, len(self.provider.calls))
        self.assertEqual([], run['invocations'])
        self.assertEqual(source['documents'], run['documents'])
        self.assertEqual(run, self.service.import_template(request))

    def test_visual_refinement_rerenders_actual_content_without_changing_source_template(self):
        self.provider.repair_crop = True
        run = self.start()
        self.assertEqual('ready', run['status'], run.get('error'))
        self.assertEqual(1, run['visual_attempt'])
        self.assertEqual(2, self.provider.review_count)
        self.assertEqual(1, self.service.image_provider.calls)
        source = self.service.templates.store.get('run', run['template_run_id'])
        self.assertEqual('cover', next(c['fit'] for c in source['documents']['landing']['components'] if c['id'] == 'visual'))
        self.assertEqual('contain', next(c['fit'] for c in run['documents']['landing']['components'] if c['id'] == 'visual'))
        self.assertEqual(sha({k:v['sha256'] for k,v in run['previews'].items()}), run['visual_review']['preview_sha256'])
        last = [c for c in self.provider.calls if c['input_payload'].get('phase') == 'review'][-1]
        with self.assertRaisesRegex(ValueError, 'only adjust layout'):
            last['response_validator']({'ready': False, 'issues': ['Color'], 'edits': [{'surface': 'post', 'path': 'background', 'value': '#FF0000'}]})

    def test_reference_screenshots_are_temporary_and_source_art_requires_reuse(self):
        png = self.service.image_provider.generate('test')['bytes']
        captures = []
        def capture(url):
            captures.append(url)
            return {'title': 'Reference', 'url': url, 'text': 'Untrusted company text', 'images': [png], 'photos': [{'url': url+'/photo.png', 'alt': 'Workspace', 'bytes': png}]}
        self.service.capture = capture
        for reuse in (False, True):
            run = self.start(mode='post', instruction='', url='https://example.com', reuse_images=reuse)
            self.assertEqual('ready', run['status'], run.get('error'))
            self.assertEqual('owner_requested_source_reuse' if reuse else 'generated', run['image_assets'][0]['origin'])
            self.assertNotIn('bytes_base64', str(run))
            self.assertNotIn('Untrusted company text', str(run))
        self.assertEqual(2, len(captures))

    def test_http_auth_bounded_input_and_hash_verified_media(self):
        app = FastAPI()
        def owner(authorization: str = Header(default='')):
            if authorization != 'Bearer fixture':
                raise HTTPException(401)
        app.include_router(creation_router(self.service, prefix='/api/v1/create', dependencies=[Depends(owner)]))
        with TestClient(app) as client:
            self.assertEqual(401, client.get('/api/v1/create/runs').status_code)
            headers = {'Authorization': 'Bearer fixture'}
            self.assertEqual(422, client.post('/api/v1/create/runs', headers=headers, json={}).status_code)
            response = client.post('/api/v1/create/runs', headers=headers, json=self.request(mode='post'))
            self.assertEqual(202, response.status_code, response.text)
            run = response.json()
            self.assertEqual('ready', run['status'], run.get('error'))
            digest = run['previews']['post:desktop']['sha256']
            response = client.get('/api/v1/create/media/'+digest, headers=headers)
            self.assertEqual(digest, response.headers['x-ptw-content-sha256'])
            self.assertEqual('private, no-store', response.headers['cache-control'])
            self.assertEqual(413, client.post('/api/v1/create/runs', headers=headers, content='x'*40001).status_code)

    def test_interruption_is_explicit_and_namespace_cannot_leak_to_template_gallery(self):
        run = self.start(mode='brief')
        self.service.update(run, status='content')
        self.service.recover_interrupted()
        self.assertEqual('interrupted', self.service.get(run['run_id'])['status'])
        with self.assertRaises(KeyError):
            TemplateStore(self.root/'creation.sqlite3').get('run', run['run_id'])
        with self.assertRaises(ValueError):
            TemplateStore(self.root/'creation.sqlite3', namespace='unexpected_sql')

    def test_html_escapes_copy_and_preserves_canonical_identity(self):
        run = self.start(mode='landing')
        bindings = {**run['bindings']['landing'], 'title': '<script>alert(1)</script>'}
        html = landing_html(run['documents']['landing'], bindings, self.service.bound_assets(run, 'landing'))
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        for doc in run['documents'].values():
            self.assertEqual(['brand'], [c['type'] for c in doc['components'] if c['role'] == 'brand'])


if __name__ == '__main__':
    unittest.main()
