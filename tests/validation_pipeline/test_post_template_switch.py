from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
import unittest
from uuid import uuid4
from unittest.mock import patch
from PIL import Image

from tests.validation_pipeline import test_studio_creatives as fixture
from tests.validation_pipeline.test_template_authoring import ScriptedTemplateProvider
from validation_pipeline.template_authoring import TemplateAuthoringService
from validation_pipeline.template_components import new_component, seed
from validation_pipeline.template_previews import render_designs
from validation_pipeline.template_store import TemplateStore
from validation_pipeline.studio_workspace import PostStudioWorkspace
from validation_pipeline.provider import enforce_structured_contract_budget
from validation_pipeline.studio_manual_agent import StudioManualAgentProviderError


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

    def agent(self, detail, *, screenshots=None, configuration=None, content=None):
        return self.service.manual_agent_edit(self.project, self.creative,
            request_id=str(uuid4()), base_sha256=detail['state_sha256'],
            message='Adjust the text and artwork using this screenshot', history=[],
            configuration=configuration or detail['configuration'],
            content=content or detail['content'], screenshots=screenshots or [])

    def test_authored_agent_edits_named_fields_and_plans_reference_image_without_writes(self):
        changed = self.switch(self.request())
        self.fixture.provider.manual_edits = [
            {'path': 'content.template_text.title', 'value': 'An agent-adjusted headline'},
            {'path': 'configuration.template_typography.title.font_size', 'value': 64},
            {'path': 'configuration.logo.symbol_color', 'value': '#112233'},
        ]
        self.fixture.provider.manual_image_actions = [{
            'slot': 'phone_screen', 'visual_direction': 'A complete subject inspired by the screenshot',
            'enhance_current': False, 'reference_index': 1,
        }]
        before = {path.relative_to(self.fixture.root): path.read_bytes()
                  for path in self.fixture.root.rglob('*') if path.is_file()}
        screenshot = fixture._png('#314159')
        result = self.agent(changed, screenshots=[screenshot])
        self.assertEqual('An agent-adjusted headline', result['content']['template_text']['title'])
        self.assertEqual(64, result['configuration']['template_typography']['title']['font_size'])
        self.assertEqual('#112233', result['configuration']['logo']['symbol_color'])
        self.assertEqual(changed['content']['hero_title'], result['content']['hero_title'])
        self.assertEqual(self.fixture.provider.manual_image_actions, result['image_actions'])
        call = self.fixture.provider.calls[-1]
        enforce_structured_contract_budget(mode=call['mode'], system_prompt=call['system_prompt'],
            input_payload=call['input_payload'], output_schema=call['output_schema'])
        paths = call['output_schema']['properties']['edits']['items']['properties']['path']['enum']
        self.assertIn('content.template_text.title', paths)
        self.assertIn('configuration.template_typography.title.font_size', paths)
        for path in ('content.hero_title', 'content.stats[0].value', 'configuration.device.x',
                     'configuration.logo.enabled', 'configuration.template_palette.gradient_start'):
            self.assertNotIn(path, paths)
        contract = call['input_payload']['agent_control_contract']
        self.assertEqual(changed['template_fields'], contract['text_fields'])
        self.assertEqual(180, contract['typography']['maximum'])
        self.assertEqual(hashlib.sha256(screenshot).hexdigest(), call['input_artifacts'][0]['sha256'])
        self.assertNotIn('bytes_base64', call['input_payload']['image_tools']['screenshot_references'][0])
        after = {path.relative_to(self.fixture.root): path.read_bytes()
                 for path in self.fixture.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(changed['state_sha256'], self.service.detail(self.project, self.creative)['state_sha256'])

    def test_authored_agent_noop_preserves_unsaved_copy_and_existing_font_overrides(self):
        changed = self.switch(self.request())
        configuration = deepcopy(changed['configuration'])
        configuration['template_typography'] = {'title': {'font_family': 'Oswald', 'font_size': 62}}
        content = deepcopy(changed['content'])
        content['template_text']['title'] = 'Pending owner copy'
        self.fixture.provider.manual_edits = []
        result = self.agent(changed, configuration=configuration, content=content)
        self.assertEqual(configuration, result['configuration'])
        self.assertEqual(content, result['content'])
        self.assertEqual([], result['changed_paths'])
        result = self.agent(changed)
        self.assertEqual(changed['configuration'], result['configuration'])
        self.assertNotIn('template_typography', result['configuration'])

    def test_authored_agent_rejects_hidden_paths_invalid_fonts_and_bounds(self):
        changed = self.switch(self.request())
        for path, value in [('configuration.device.x', 200),
                            ('content.template_text.unknown', 'Extra'),
                            ('configuration.template_typography.title.font_size', 181),
                            ('configuration.template_typography.title.font_family', 'Invented font')]:
            with self.subTest(path=path, value=value):
                self.fixture.provider.manual_edits = [{'path': path, 'value': value}]
                with self.assertRaises(StudioManualAgentProviderError) as caught:
                    self.agent(changed)
                self.assertIsInstance(caught.exception.__cause__, ValueError)
                self.assertEqual(changed['state_sha256'], self.workspace.state_sha256())
        before_calls = len(self.fixture.provider.calls)
        stale = {**changed, 'state_sha256': '0' * 64}
        with self.assertRaises(RuntimeError): self.agent(stale)
        self.assertEqual(before_calls, len(self.fixture.provider.calls))

    def test_authored_agent_shares_group_fonts_and_exposes_only_existing_palette(self):
        document = deepcopy(self.authoring.read(self.reference)['document'])
        document['components'].insert(0, {
            **new_component('backdrop', 'decoration', 'decoration', [0, 0, 1000, 1000]),
            'gradient': ['#1676CB', '#24C4CC'],
        })
        for index, item in enumerate(['benefit_primary', 'benefit_secondary']):
            document['components'].append({
                **new_component(item, 'text', 'description', [60, 400 + index * 70, 340, 40], 'Body text'),
                'font_family': 'Inter', 'font_size': 28,
            })
        document['text_groups'] = [{'id': 'benefits', 'items': ['benefit_primary', 'benefit_secondary'],
                                   'gap': 18, 'bullet_indent': 24}]
        renders = render_designs({'post': document})
        run = self.authoring.start({'request_id': str(uuid4()), 'scope': 'post',
            'instruction': 'Grouped benefits and gradient', 'source': self.reference})
        with self.authoring.store.transaction() as tx:
            for preview in renders.values(): tx.media(preview['bytes'])
        previews = {key: {name: value for name, value in preview.items() if name != 'bytes'}
                    for key, preview in renders.items()}
        run = self.authoring._update(run, documents={'post': document}, previews=previews,
            status='proposed', phase='compare')
        reference = self.authoring.decide(run['run_id'], {'request_id': str(uuid4()),
            'base_sha256': run['state_sha256'], 'decision': 'accept'})['accepted_versions'][0]
        changed = self.switch(self.request(reference))
        self.fixture.provider.manual_edits = []
        self.assertEqual(changed['configuration'], self.agent(changed)['configuration'])
        self.fixture.provider.manual_edits = [
            {'path': 'configuration.template_typography.benefit_secondary.font_size', 'value': 32},
            {'path': 'configuration.template_palette.gradient_end', 'value': '#445566'},
        ]
        result = self.agent(changed)
        for item in ['benefit_primary', 'benefit_secondary']:
            self.assertEqual({'font_family': 'Inter', 'font_size': 32}, result['configuration']['template_typography'][item])
        self.assertEqual({'gradient_start': '#1676CB', 'gradient_end': '#445566'}, result['configuration']['template_palette'])
        self.assertEqual(self.reference['template_sha256'], self.authoring.read(self.reference)['template_sha256'])

    def test_catalog_uses_injected_registry_and_each_choice_is_applicable(self):
        catalog = self.service.templates()
        self.assertEqual({'phone_metrics', self.reference['template_id']}, {
            item['template_id'] for item in catalog['items']
        })
        authored = next(
            item for item in catalog['items']
            if item['template_id'] == self.reference['template_id']
        )
        self.assertTrue(authored['capabilities']['supports_manual_agent'])
        self.assertTrue(authored['capabilities']['supports_generation'])
        exact_reference = {
            'surface': 'post',
            'template_id': authored['template_id'],
            'template_version': authored['template_version'],
            'template_sha256': authored['template_sha256'],
        }
        changed = self.switch(self.request(exact_reference))
        self.assertEqual(exact_reference, changed['template_reference'])
        restored = self.switch(self.request(self.detail['template_reference'], changed))
        self.assertEqual(self.detail['template_reference'], restored['template_reference'])

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

    def test_layout_overflow_renders_and_owner_can_save_and_approve(self):
        changed = self.switch(self.request())
        configuration = deepcopy(changed['configuration'])
        configuration['template_typography'] = {
            'title': {'font_family': 'Inter', 'font_size': 180},
        }
        content = deepcopy(changed['content'])
        content['template_text']['title'] = 'Long owner headline ' * 20
        before = self.workspace.state_sha256()
        rendered = self.workspace.render_preview(state_sha256=before,
            configuration=configuration, content=content)
        self.assertTrue(rendered['bytes'].startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertTrue(any('overflows' in issue['issue'] for issue in rendered['layout_issues']))
        self.assertEqual(before, self.workspace.state_sha256())
        saved = self.service.checkpoint(self.project, self.creative, kind='save',
            base_sha256=before, configuration=configuration, content=content)
        detail = saved['creative']
        approved = self.service.checkpoint(self.project, self.creative, kind='approve',
            base_sha256=detail['state_sha256'], configuration=configuration,
            content=content, change_note='Owner reviewed overflowing layout')
        self.assertEqual(1, len(approved['creative']['versions']))
        self.assertEqual(rendered['bytes'], self.workspace.version_render(1)['bytes'])

    def test_layout_overlap_and_canvas_bounds_are_advisory(self):
        changed = self.switch(self.request())
        failures = [
            {'role': 'headline', 'issue': 'Component exceeds canvas bounds', 'solvable': True},
            {'role': 'description', 'issue': 'Visible text overlaps headline', 'solvable': True},
        ]
        with patch('validation_pipeline.template_previews.geometry', return_value=([], failures)):
            rendered = self.workspace.render_preview(state_sha256=changed['state_sha256'])
        self.assertEqual(failures, rendered['layout_issues'])
        self.assertTrue(rendered['bytes'].startswith(b'\x89PNG'))

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

    def test_cutout_fixture_is_replaced_by_existing_post_image_and_fixed_assets_remain(self):
        source = Path(__file__).resolve().parents[2] / 'validation_pipeline/studio_assets/template-assets/neutral_person_stock_v1-source.jpg'
        image = Image.open(source).convert('RGB'); image.thumbnail((640,960))
        raw = BytesIO(); image.save(raw, format='PNG')
        self.detail = self.workspace.store_generated_phone_screen(
            base_sha256=self.detail['state_sha256'], data=raw.getvalue(),
            source={'origin':'codex_builtin_image_generation','text_in_screen':'prohibited_by_prompt'})
        document = seed('post')
        document['name'] = 'Gradient reusable post'
        document['components'] = [
            new_component('title','text','headline',[60,40,880,120],'Title'),
            {**new_component('person','cutout_image','hero',[470,170,470,650],'Image'),'fit':'contain'},
            {**new_component('motif','brand_motif','decoration',[90,300,120,120],'Natal symbol'),
                'border_color':'#67CBE5','opacity':.3,'fit':'contain'},
            {**new_component('app_store','store_badge','cta',[60,850,340,90],'App Store'),'fit':'contain'},
            {**new_component('google_play','store_badge','cta',[420,850,340,90],'Google Play'),'fit':'contain'},
        ]
        run = self.authoring.start({'request_id':str(uuid4()),'scope':'post','instruction':'Asset template'})
        renders = render_designs({'post':document})
        previews = {}
        with self.authoring.store.transaction() as tx:
            for key, preview in renders.items():
                self.assertEqual(preview['sha256'], tx.media(preview['bytes']))
                previews[key] = {name:value for name,value in preview.items() if name != 'bytes'}
        run = self.authoring._update(run, documents={'post':document}, previews=previews,
            status='proposed', phase='compare', comparison={'complete':True,'edits':[],
                'differences':[],'capability_gap':None})
        reference = self.authoring.decide(run['run_id'], {'request_id':str(uuid4()),
            'base_sha256':run['state_sha256'],'decision':'accept'})['accepted_versions'][0]
        changed = self.switch(self.request(reference))
        records = self.workspace._asset_records(changed['configuration'], changed['content'])
        screen = self.workspace._asset_record('phone_screen')
        self.assertIsNotNone(screen)
        self.assertNotEqual(screen['bytes'], records['person']['bytes'])
        cutout = Image.open(BytesIO(records['person']['bytes'])).convert('RGBA')
        self.assertEqual(0, cutout.getpixel((0,0))[3])
        self.assertEqual(255, cutout.getpixel((cutout.width//2,cutout.height//2))[3])
        self.assertEqual(raw.getvalue(), screen['bytes'])
        self.assertNotEqual(screen['bytes'], records['motif']['bytes'])
        self.assertNotEqual(screen['bytes'], records['app_store']['bytes'])
        self.assertNotEqual(records['app_store']['bytes'], records['google_play']['bytes'])
