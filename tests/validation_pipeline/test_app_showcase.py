from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import unittest

from tests.validation_pipeline.test_landing_workspace import FakeImages, complete_content
from validation_pipeline.landing_templates import APP_SHOWCASE_DEFINITION, LANDING_TEMPLATE_REGISTRY
from validation_pipeline.landing_workspace import LandingWorkspace, normalize_configuration, normalize_content
from validation_pipeline.landing_pages import LandingService, LocalLandingAuthority, landing_generation_schema
from validation_pipeline.landing_publication import public_snapshot, selected_assets
from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.landing_showcase import SCREEN_SLOTS, VISUAL_SLOTS

REFERENCE = {key: value for key, value in APP_SHOWCASE_DEFINITION.identity.to_reference().items() if key != 'surface'}


def showcase_content():
    value = complete_content()
    value.pop('app_feature')
    value['social_proof']['items'] = []
    value['app_screens'] = [{'title': title, 'description': 'A clear next step for your home inventory.', 'visual_direction': f'A clean portrait app screen for {title}, with concise labels and the shared blue and teal palette.'} for title in ('Your inventory', 'Add an item', 'Review categories')]
    return value


class MemoryAuthority:
    def __init__(self):
        self.page = {'landing_id': str(uuid4()), 'project_id': str(uuid4()), 'source_brief_id': str(uuid4()), 'status': 'queued', 'template_reference': REFERENCE,
                     'source_post_snapshot': {'template_id': 'phone_metrics', 'content': {'hero_title': 'Organize your home inventory'}, 'configuration': {}, 'version_sha256': 'a' * 64}}
        self.runs = []
    def get_page(self, _id): return deepcopy(self.page)
    def update_page(self, _id, **patch): self.page.update(deepcopy(patch)); return self.get_page(_id)
    def brief(self, _id): return {'approved': True, 'document': {'language': 'en', 'idea': 'An app to organize a home inventory. Add an item with a photo, browse your items and review categories. No prices or performance claims.'}}
    def record_generation_run(self, **value): self.runs.append(value)


class ContentProvider:
    def __init__(self): self.calls = []
    def call(self, **kwargs):
        self.calls.append(kwargs)
        content = showcase_content(); content['contacts']['email'] = ''
        return {'response': kwargs['response_validator']({'content': content}), 'invocation': {}}


def service(root, authority, images=None, provider=None):
    return LandingService(root=root, authority=authority, workspace_factory=lambda path: LandingWorkspace(path, image_provider=images or FakeImages()),
                          structured_provider=provider or ContentProvider(), composer_skill_path=Path('skills/landing-page-composer/SKILL.md'), manual_agent_skill_path=Path('skills/studio-manual-agent/SKILL.md'))


class AppShowcaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.images = FakeImages()
        self.workspace = LandingWorkspace(self.directory.name, image_provider=self.images)
        self.workspace.template_reference = REFERENCE

    def populated(self):
        detail = self.workspace.detail()
        detail = self.workspace.save_configuration(base_sha256=detail['state_sha256'], configuration=detail['configuration'], content=showcase_content())
        for slot in VISUAL_SLOTS:
            detail = self.workspace.generate_visual(base_sha256=detail['state_sha256'], slot=slot, visual_direction='A sample app interface', prompt='sample')
        return detail

    def test_contract_rejects_unknown_slots_wrong_template_and_invalid_screens(self):
        detail = self.workspace.detail()
        self.assertEqual(tuple(detail['catalog']['visual_slots']), VISUAL_SLOTS)
        with self.assertRaises(ValueError): self.workspace.generate_visual(base_sha256=detail['state_sha256'], slot='hero_visual', visual_direction='Sample image', prompt='sample')
        with self.assertRaises(ValueError): normalize_content({**showcase_content(), 'app_screens': []})
        with self.assertRaises(ValueError): normalize_configuration({**detail['configuration'], 'showcase': {'gradient_end': '#ffffff', 'screen_scale': 9, 'screen_offset': 0}})
        with self.assertRaises(ValueError): self.workspace.save_configuration(base_sha256=detail['state_sha256'], configuration=detail['configuration'], content=complete_content())
        self.assertFalse(self.images.references)

    def test_approval_requires_all_screens_and_is_atomic(self):
        detail = self.workspace.detail()
        with self.assertRaises(ValueError): self.workspace.approve_configuration(base_sha256=detail['state_sha256'], configuration=detail['configuration'], content=showcase_content(), change_note='Sample')
        self.assertEqual(self.workspace.state_sha256(), detail['state_sha256'])
        detail = self.populated()
        self.workspace.approve_configuration(base_sha256=detail['state_sha256'], configuration=detail['configuration'], content=detail['content'], change_note='Sample')
        record = self.workspace.version_detail(1)
        self.assertEqual(record['template_reference'], REFERENCE)
        self.assertEqual(set(selected_assets(record)), set(VISUAL_SLOTS))
        snapshot = public_snapshot({'slug': 'sample'}, 'Sample', {'landing_version_sha256': record['version_sha256'], 'created_at': 'now'}, record)
        self.assertEqual(snapshot['template_reference'], REFERENCE)
        self.assertNotIn('source_post_snapshot', snapshot)
        broken = deepcopy(record); broken['assets'].pop()
        with self.assertRaises(RuntimeError): selected_assets(broken)

    def test_history_enhancement_restart_and_approved_media_retention(self):
        detail = self.populated()
        original = self.workspace.visual_image('app_screen_1', detail['assets'][0]['sha256'])
        self.workspace.approve_configuration(base_sha256=detail['state_sha256'], configuration=detail['configuration'], content=detail['content'], change_note='Sample')
        for _ in range(4):
            self.workspace.generate_visual(base_sha256=self.workspace.state_sha256(), slot='app_screen_1', visual_direction='Update the screen title', prompt='sample', enhance_current=True)
        self.assertEqual(self.images.references[4], original['bytes'])
        self.assertTrue((self.workspace.assets / f"{original['sha256']}.png").is_file())
        restored = LandingWorkspace(self.directory.name, image_provider=self.images); restored.template_reference = REFERENCE
        self.assertEqual(restored.detail(), self.workspace.detail())
        self.assertEqual(len(restored.detail()['assets'][0]['history']), 3)
        with self.assertRaises(RuntimeError): restored.select_visual(base_sha256='0'*64, slot='app_screen_1', sha256=restored.detail()['assets'][0]['sha256'])

    def test_registered_photo_has_provenance_and_no_provider_call(self):
        detail = self.workspace.reuse_visual(base_sha256=self.workspace.state_sha256(), slot='visual_break_visual', asset_id='showcase_lifestyle')
        self.assertTrue(detail['assets'][-1]['available'])
        self.assertEqual(self.workspace._history('visual_break_visual')[0]['source']['origin'], 'registered_reference')
        self.assertEqual(self.images.references, [])

    def test_generation_retries_only_missing_images_and_preserves_edits(self):
        class FailsOnce(FakeImages):
            failed = False
            def generate(self, prompt, **kwargs):
                if len(self.references) == 1 and not self.failed:
                    self.failed = True; raise RuntimeError('Provider unavailable')
                return super().generate(prompt, **kwargs)
        images, provider, authority = FailsOnce(), ContentProvider(), MemoryAuthority()
        active = service(Path(self.directory.name) / 'service', authority, images, provider)
        lid, pid = authority.page['landing_id'], authority.page['project_id']
        self.assertEqual(active.generate(lid)['status'], 'failed')
        partial = active.detail(pid, lid); first = partial['assets'][0]['sha256']
        partial['content']['hero']['title'] = 'Keep my edit'
        partial['content']['app_screens'][1]['visual_direction'] = 'Keep this owner-requested orange Add photo button'
        active.mutate(pid, lid, 'save_configuration', base_sha256=partial['state_sha256'], configuration=partial['configuration'], content=partial['content'])
        active.retry_generation(pid, lid)
        self.assertEqual(active.generate(lid)['status'], 'draft')
        final = active.detail(pid, lid)
        self.assertEqual(final['configuration']['presentation']['language'], 'en')
        self.assertEqual(final['content']['hero']['title'], 'Keep my edit')
        self.assertEqual(final['content']['contacts']['email'], 'welcome@natal-service.com')
        self.assertEqual(final['content']['contacts']['phone'], '+380 93 725 64 69')
        self.assertEqual(final['assets'][0]['sha256'], first)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(len(images.references), 4)
        screen = active._workspace(lid)._history('app_screen_2')[-1]['source']['image_context']
        self.assertEqual(screen['instruction']['origin'], 'owner')
        self.assertEqual(screen['destination']['template_id'], 'app_showcase')
        self.assertEqual(screen['destination']['crop']['fit'], 'contain')
        with self.assertRaises(KeyError): active.detail(str(uuid4()), lid)

    def test_manual_agent_can_tune_screens_but_cannot_change_contacts(self):
        authority = MemoryAuthority(); active = service(Path(self.directory.name) / 'service', authority)
        lid, pid = authority.page['landing_id'], authority.page['project_id']; active.generate(lid)
        class Agent:
            def call(self, **kwargs):
                self.kwargs = kwargs
                return {'response': kwargs['response_validator']({'edits': [{'path': 'content.app_screens[1].visual_direction', 'value': 'Change only the label to Add photo'}], 'image_actions': [{'slot': 'app_screen_2', 'visual_direction': 'Change only the label to Add photo', 'enhance_current': True, 'reference_index': 0}], 'reply': 'Updated screen 2.'})}
        active.structured_provider = Agent(); detail = active.detail(pid, lid)
        result = active.manual_agent_edit(pid, lid, request_id=str(uuid4()), base_sha256=detail['state_sha256'], message='Change the label on screen two', history=[], screenshots=[], configuration=detail['configuration'], content=detail['content'])
        self.assertEqual(result['image_actions'][0]['slot'], 'app_screen_2')
        self.assertIn('configuration.presentation.language', active.structured_provider.kwargs['input_payload']['current_editable_values'])
        self.assertEqual(active.detail(pid, lid)['state_sha256'], detail['state_sha256'])
        self.assertEqual(result['content']['contacts'], detail['content']['contacts'])

    def test_reservation_reference_conflict_and_legacy_default(self):
        store = LocalBriefStore(Path(self.directory.name) / 'authority')
        authority = LocalLandingAuthority(store, post_workspace_root=Path(self.directory.name))
        pid, cid, bid = str(uuid4()), str(uuid4()), str(uuid4())
        authority._source_version = lambda *_: {'source_brief_id': bid, 'version_sha256': 'a'*64}
        request = dict(project_id=pid, source_creative_id=cid, source_version=1, requested_by='test')
        with self.assertRaises(ValueError): authority.create_page(**request, template_reference=3)
        page, created = authority.create_page(**request, template_reference=REFERENCE)
        self.assertTrue(created)
        self.assertFalse(authority.create_page(**request, template_reference=REFERENCE)[1])
        old = {k:v for k,v in LANDING_TEMPLATE_REGISTRY.get('project_landing').identity.to_reference().items() if k != 'surface'}
        with self.assertRaises(RuntimeError): authority.create_page(**request, template_reference=old)
        attempt = str(uuid4())
        variant, created = authority.create_page(**request, additional=True, template_reference=old, request_id=attempt)
        self.assertTrue(created)
        self.assertEqual(old, variant['template_reference'])
        self.assertEqual(page, authority.get_page(page['landing_id']))
        # Response loss and authority restart reuse the same reservation.
        restarted = LocalLandingAuthority(store, post_workspace_root=Path(self.directory.name))
        restarted._source_version = authority._source_version
        repeat, created = restarted.create_page(**request, additional=True, template_reference=old, request_id=attempt)
        self.assertFalse(created)
        self.assertEqual(variant['landing_id'], repeat['landing_id'])
        with self.assertRaisesRegex(RuntimeError, 'request ID'):
            authority.create_page(**request, additional=True, template_reference=REFERENCE, request_id=attempt)
        with self.assertRaisesRegex(RuntimeError, 'request ID'):
            authority.create_page(**{**request, 'source_version': 2}, additional=True, template_reference=old, request_id=attempt)
        with self.assertRaisesRegex(ValueError, 'UUID'):
            authority.create_page(**request, additional=True, template_reference=old, request_id='invalid')
        self.assertFalse(authority.create_page(**request)[1])

    def test_local_graph_sync_retains_each_screen_and_source_lineage(self):
        store = LocalBriefStore(Path(self.directory.name) / 'authority')
        authority = LocalLandingAuthority(store, post_workspace_root=Path(self.directory.name))
        pid, cid, bid = str(uuid4()), str(uuid4()), str(uuid4())
        authority._source_version = lambda *_: {'source_brief_id': bid, 'version_sha256': 'a'*64}
        page, _ = authority.create_page(project_id=pid, source_creative_id=cid, source_version=1, requested_by='test', template_reference=REFERENCE)
        detail = self.populated()
        self.workspace.approve_configuration(base_sha256=detail['state_sha256'], configuration=detail['configuration'], content=detail['content'], change_note='Sample')
        authority.synchronize_workspace(page['landing_id'], self.workspace)
        self.assertEqual({item['slot'] for item in store.list('landing_assets')}, set(VISUAL_SLOTS))
        self.assertEqual(len(store.list('landing_versions')), 1)
        authority.synchronize_workspace(page['landing_id'], self.workspace)
        self.assertEqual(len(store.list('landing_assets')), 4)
        self.assertEqual(len(store.list('landing_versions')), 1)

    def test_late_image_result_cannot_overwrite_a_newer_edit(self):
        workspace = self.workspace
        class EditingProvider(FakeImages):
            def generate(self, prompt, **kwargs):
                detail = workspace.detail()
                detail['content']['hero']['title'] = 'A newer owner edit'
                workspace.save_configuration(base_sha256=detail['state_sha256'], configuration=detail['configuration'], content=detail['content'])
                return super().generate(prompt, **kwargs)
        workspace.image_provider = EditingProvider()
        with self.assertRaises(RuntimeError):
            workspace.generate_visual(base_sha256=workspace.state_sha256(), slot='app_screen_1', visual_direction='A new app screenshot', prompt='sample')
        self.assertFalse(workspace.detail()['assets'][0]['available'])
        self.assertEqual(workspace.detail()['content']['hero']['title'], 'A newer owner edit')

    def test_bundled_reference_assets_match_their_provenance(self):
        import hashlib, json
        root = Path('validation_pipeline/studio_assets/app-showcase')
        manifest = json.loads((root / 'manifest.json').read_text())
        for item in manifest['assets']:
            data = (root / item['file']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
            self.assertTrue(item['source_url'].startswith('repo:'))
            if item['file'].endswith('.svg'):
                self.assertNotIn(b'<script', data.lower())
                self.assertNotIn(b'<foreignobject', data.lower())

    def test_composition_schema_has_three_screens(self):
        schema = landing_generation_schema('app_showcase')['properties']['content']
        self.assertIn('app_screens', schema['required'])
        self.assertNotIn('app_feature', schema['properties'])
        self.assertEqual(schema['properties']['app_screens']['minItems'], 3)
