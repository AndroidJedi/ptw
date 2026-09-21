from copy import deepcopy
import unittest
from uuid import uuid4
from unittest.mock import patch

from tests.validation_pipeline import test_studio_creatives as fixture
from tests.validation_pipeline.test_template_authoring import ScriptedTemplateProvider
from validation_pipeline.template_authoring import TemplateAuthoringService
from validation_pipeline.template_store import TemplateStore
from validation_pipeline.studio_workspace import PostStudioWorkspace


class PostTemplateSwitchTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.StudioCreativeServiceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.service = self.fixture.service
        self.authoring = TemplateAuthoringService(TemplateStore(self.fixture.root / 'templates.sqlite3'), ScriptedTemplateProvider(), asynchronous=False)
        self.addCleanup(self.authoring.close)
        self.service.template_registry = self.authoring.post_registry
        self.project, _, self.detail = self.fixture.generate_creative()
        self.creative = self.detail['creative_id']
        self.workspace = self.service._workspace(self.creative)
        self.reference = self.accept_template()

    def accept_template(self, source=None):
        run = self.authoring.start({'request_id': str(uuid4()), 'scope': 'post', 'instruction': 'Clear design', **({'source': source} if source else {})})
        self.assertEqual('proposed', run['status'], run['error'])
        return self.authoring.decide(run['run_id'], {'request_id': str(uuid4()), 'base_sha256': run['state_sha256'], 'decision': 'accept'})['accepted_versions'][0]

    def request(self, reference=None, detail=None):
        detail = detail or self.detail
        return {'request_id': str(uuid4()), 'base_sha256': detail['state_sha256'], 'template_reference': reference or self.reference,
                'configuration': deepcopy(detail['configuration']), 'content': deepcopy(detail['content'])}

    def switch(self, request):
        return self.service.mutate(self.project, self.creative, 'switch_template', **request)

    def test_apply_keeps_pending_copy_image_history_and_exact_version_across_restart(self):
        original = self.service.checkpoint(self.project, self.creative, kind='approve', base_sha256=self.detail['state_sha256'], configuration=self.detail['configuration'], content=self.detail['content'], change_note='Original')
        png = self.workspace.version_render(1)['bytes']
        request = self.request()
        request['content']['hero_title'] = 'Unsaved owner headline'
        changed = self.switch(request)
        self.assertEqual('Unsaved owner headline', changed['content']['template_text']['title'])
        self.assertEqual(self.detail['phone_screen_history'], changed['phone_screen_history'])
        self.assertEqual(png, self.workspace.version_render(1)['bytes'])
        self.assertEqual(changed['state_sha256'], self.switch(request)['state_sha256'])
        self.assertEqual(self.reference, changed['template_reference'])
        new_reference = self.accept_template(self.reference)
        self.assertEqual(2, new_reference['template_version'])
        restored = PostStudioWorkspace(self.workspace.root, template_registry=self.authoring.post_registry)
        self.assertEqual(self.reference, restored.detail()['template_reference'])
        self.assertEqual(changed['state_sha256'], restored.state_sha256())
        rendered = restored.render_preview(state_sha256=changed['state_sha256'])
        self.assertNotEqual(png, rendered['bytes'])
        approved = self.service.checkpoint(self.project, self.creative, kind='approve', base_sha256=changed['state_sha256'], configuration=changed['configuration'], content=changed['content'], change_note='New layout')
        self.assertEqual(2, len(approved['creative']['versions']))
        self.assertEqual(self.reference, self.workspace.version_detail(2)['template_reference'])
        from validation_pipeline.approved_posts import approved_post_copy
        self.assertEqual('Unsaved owner headline', approved_post_copy(self.workspace.version_detail(2))['headline'])
        self.assertEqual(png, self.workspace.version_render(1)['bytes'])
        clone, _ = self.service.clone_approved_version(project_id=self.project, source_creative_id=self.creative, source_version=2, request_id=str(uuid4()), requested_by='test')
        self.assertEqual(self.reference, self.service.detail(self.project, clone['creative_id'])['template_reference'])

    def test_rejects_stale_forged_landing_and_cross_project_requests_without_changes(self):
        before = self.workspace.state_sha256()
        for changes in ({'surface': 'landing'}, {'template_sha256': '0' * 64}, {'template_version': 999}):
            with self.assertRaises((ValueError, KeyError)):
                self.switch(self.request({**self.reference, **changes}))
            self.assertEqual(before, self.workspace.state_sha256())
        request = self.request(); request['base_sha256'] = '0' * 64
        with self.assertRaises(RuntimeError): self.switch(request)
        other, _ = self.fixture.approved_brief('Other')
        with self.assertRaises(KeyError):
            self.service.mutate(other, self.creative, 'switch_template', **self.request())
        self.assertEqual(before, self.workspace.state_sha256())

    def test_render_failure_rolls_back_and_returning_to_phone_preserves_image(self):
        before = self.workspace.state_sha256()
        with patch.object(self.workspace, 'render_preview', side_effect=RuntimeError('render failed')):
            with self.assertRaises(RuntimeError): self.switch(self.request())
        self.assertEqual(before, self.workspace.state_sha256())
        changed = self.switch(self.request())
        restored = self.switch(self.request(self.detail['template_reference'], changed))
        self.assertEqual(self.detail['content'], restored['content'])
        self.assertEqual(self.detail['phone_screen_history'], restored['phone_screen_history'])

    def test_custom_copy_save_and_historical_phone_clone_after_switch(self):
        self.service.checkpoint(self.project, self.creative, kind='approve', base_sha256=self.detail['state_sha256'], configuration=self.detail['configuration'], content=self.detail['content'], change_note='Phone')
        changed = self.switch(self.request())
        from validation_pipeline.landing_pages import LocalLandingAuthority
        landing = LocalLandingAuthority(self.fixture.store, post_workspace_root=self.service.root)
        self.assertEqual('phone_metrics', landing._source_version(self.project, self.creative, 1)['template_id'])
        self.assertEqual('phone_metrics', landing.source_versions(self.project)[0]['template_id'])
        # Existing approved records predate explicit registry references.
        original = self.workspace.version_detail(1)
        original.pop('template_reference', None)
        content = deepcopy(changed['content']); content['template_text']['title'] = 'Custom text'
        result = self.service.checkpoint(self.project, self.creative, kind='save', base_sha256=changed['state_sha256'], configuration=changed['configuration'], content=content)
        self.assertEqual('Custom text', result['creative']['content']['template_text']['title'])
        with patch.object(self.workspace, 'version_detail', return_value=original):
            clone, _ = self.service.clone_approved_version(project_id=self.project, source_creative_id=self.creative, source_version=1, request_id=str(uuid4()), requested_by='test')
        detail = self.service.detail(self.project, clone['creative_id'])
        self.assertEqual('phone_metrics', detail['template_id'])
        self.assertEqual(self.detail['content'], detail['content'])
