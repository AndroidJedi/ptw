from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from tests.validation_pipeline.test_template_authoring import ScriptedTemplateProvider
from validation_pipeline.landing_templates import APP_SHOWCASE_DEFINITION
from validation_pipeline.template_authoring import TemplateAuthoringService
from validation_pipeline.template_components import new_component, primitive, seed
from validation_pipeline.template_demo_assets import app_screen, walkthrough
from validation_pipeline.template_previews import builtins, landing_fixture
from validation_pipeline.template_store import TemplateStore


class TemplateQualityTests(unittest.TestCase):
    def test_post_palette_is_bounded_persisted_and_scoped_to_its_template(self):
        from copy import deepcopy
        from uuid import uuid4
        from validation_pipeline.post_template_runtime import post_definition, palette_defaults
        from validation_pipeline.post_templates import POST_TEMPLATE_REGISTRY
        from validation_pipeline.studio_workspace import PostStudioWorkspace
        from validation_pipeline.template_components import sha
        from validation_pipeline.template_registry import TemplateRegistry
        doc = seed('post')
        doc['components'] = [c for c in doc['components'] if c['type'] not in {'image', 'phone'}]
        backdrop = new_component('backdrop', 'decoration', 'decoration', [0, 0, 1000, 1000], '')
        backdrop['gradient'] = ['#1676CB', '#24C4CC']
        doc['components'].insert(0, backdrop)
        definition = post_definition({'surface': 'post', 'template_id': 'palette_test',
            'template_version': 1, 'template_sha256': sha(doc), 'document': doc})
        original = deepcopy(doc)
        palette = {'gradient_start': '#402429', 'gradient_end': '#85442D'}
        registry = TemplateRegistry('post', (*POST_TEMPLATE_REGISTRY.all(), definition))
        with tempfile.TemporaryDirectory() as directory:
            workspace = PostStudioWorkspace(Path(directory), template_registry=lambda: registry)
            detail = workspace.detail(); phone = detail['template_reference']
            def switch(reference):
                current = workspace.detail()
                return workspace.switch_template(base_sha256=current['state_sha256'], template_reference=reference,
                    request_id=str(uuid4()), configuration=current['configuration'], content=current['content'])
            detail = switch(definition.identity.to_reference())
            self.assertEqual(palette_defaults(doc), detail['template_palette_defaults'])
            self.assertNotIn('template_palette', detail['configuration'])
            before = workspace.render_preview(state_sha256=detail['state_sha256'])['bytes']
            config = {**detail['configuration'], 'template_palette': palette}
            detail = workspace.save_configuration(base_sha256=detail['state_sha256'], configuration=config, content=detail['content'])
            after = workspace.render_preview(state_sha256=detail['state_sha256'])['bytes']
            self.assertNotEqual(before, after)
            reopened = PostStudioWorkspace(Path(directory), template_registry=lambda: registry)
            self.assertEqual(palette, reopened.detail()['configuration']['template_palette'])
            self.assertEqual(palette, definition.component_settings(config, detail['content'])['template_palette'])
            with self.assertRaises(RuntimeError):
                workspace.save_configuration(base_sha256='0' * 64, configuration=config, content=detail['content'])
            workspace.approve_configuration(base_sha256=detail['state_sha256'], configuration=config,
                content=detail['content'], change_note='Palette review')
            approved_png = workspace.version_render(1)['bytes']
            self.assertEqual(after, approved_png)
            self.assertEqual(palette, workspace.version_detail(1)['configuration']['template_palette'])
            with self.assertRaises(ValueError):
                definition.normalize_configuration({**config, 'template_palette': {**palette, 'css': 'anything'}})
            with self.assertRaises(ValueError):
                definition.normalize_configuration({**config, 'template_palette': {**palette, 'gradient_start': 'red'}})
            restored = switch(phone)
            self.assertNotIn('template_palette', restored['configuration'])
            self.assertEqual(palette, switch(definition.identity.to_reference())['configuration']['template_palette'])
            self.assertEqual(approved_png, workspace.version_render(1)['bytes'])
            self.assertEqual(original, doc)

    def test_standalone_benefits_keep_value_context_and_authored_copy_wins(self):
        from validation_pipeline.post_template_runtime import bind_content, text_fields
        from validation_pipeline.post_templates import PHONE_METRICS_DEFINITION
        doc = seed('post')
        doc['components'].append(new_component('benefit', 'text', 'description', [60, 310, 880, 80], 'Body text'))
        content = PHONE_METRICS_DEFINITION.default_content()
        content['stats'][0] = {'value': 'Повна ціна', 'label': 'і умови до бронювання'}
        bound = bind_content(doc, content)
        self.assertEqual('Повна ціна — і умови до бронювання', bound['template_text']['benefit'])
        bound['template_text']['benefit'] = 'Owner edited this benefit'
        self.assertEqual('Owner edited this benefit', bind_content(doc, bound, text_fields(doc))['template_text']['benefit'])
        for i in range(4):
            doc['components'].append(new_component(f'meta_{i}', 'text', 'meta', [60, 410 + 90 * i, 880, 80], 'Caption'))
        self.assertEqual(content['stats'][0]['label'], bind_content(doc, content)['template_text']['benefit'])

    def test_neutral_screens_have_portrait_safe_areas_and_walkthrough_preserves_white(self):
        screens = [app_screen(index) for index in range(3)]
        self.assertEqual(3, len(set(screens)))
        for data in screens:
            image = Image.open(BytesIO(data)).convert('RGB')
            self.assertEqual((864, 1872), image.size)
            self.assertEqual(1, len(image.crop((0, 0, 864, 122)).getcolors()))
        composed = Image.open(BytesIO(walkthrough())).convert('RGBA')
        self.assertEqual((1536, 1152), composed.size)
        self.assertEqual(0, composed.getpixel((0, 0))[3])
        for point in [(220, 410), (730, 410), (1250, 410)]:
            pixel = composed.getpixel(point)
            self.assertEqual(255, pixel[3])
            self.assertGreater(min(pixel[:3]), 200)
        self.assertEqual(0, composed.getchannel('A').crop((0, 0, 1536, 32)).getextrema()[1])

    def test_complete_assets_never_stretch_or_crop_but_photos_keep_intentional_focus(self):
        doc = seed('post')
        for kind, placeholder in [('cutout_image', 'Image'), ('phone', 'Image'),
                                  ('store_badge', 'App Store'), ('brand_motif', 'Natal symbol'), ('brand', '')]:
            for fit in ('cover', 'stretch'):
                doc['components'] = [{**new_component('visual', kind, 'hero', [60, 60, 880, 500], placeholder), 'fit': fit}]
                node = primitive(doc, surface='post').document['root']['children'][0]
                self.assertEqual('contain', node['props']['fit'], kind)
        doc['components'] = [{**new_component('visual', 'image', 'hero', [60, 60, 880, 500], 'Image'), 'focal_x': .7}]
        node = primitive(doc, surface='post').document['root']['children'][0]
        self.assertEqual('cover', node['props']['fit'])
        self.assertEqual(.7, node['props']['focal_x'])

    def test_historical_builtin_resolves_exact_version_and_fixture(self):
        old = APP_SHOWCASE_DEFINITION.identity.to_reference()
        fixture = landing_fixture(reference={k: v for k, v in old.items() if k != 'surface'})
        self.assertNotIn('marketing', fixture['configuration'])
        self.assertNotIn('walkthrough_visual', fixture['imageUrls'])
        with tempfile.TemporaryDirectory() as directory:
            service = TemplateAuthoringService(TemplateStore(Path(directory) / 'templates.sqlite3'), ScriptedTemplateProvider(), asynchronous=False)
            self.addCleanup(service.close)
            with patch('validation_pipeline.template_authoring.render_builtin', side_effect=RuntimeError('offline')):
                self.assertEqual(old['template_sha256'], service.read(old)['template_sha256'])
                definition = service.registry('landing').resolve_reference({k: v for k, v in old.items() if k != 'surface'})
                self.assertEqual(old, definition.identity.to_reference())

    def test_preview_refresh_is_append_only_and_retry_preserves_previous_bytes(self):
        builtin = next(r for r in builtins() if r['surface'] == 'post')
        reference = {k: builtin[k] for k in ('surface', 'template_id', 'template_version', 'template_sha256')}
        def png(color):
            buffer = BytesIO(); Image.new('RGB', (32, 32), color).save(buffer, format='PNG'); return buffer.getvalue()
        old, new = png('blue'), png('green')
        with tempfile.TemporaryDirectory() as directory:
            store = TemplateStore(Path(directory) / 'templates.sqlite3')
            service = TemplateAuthoringService(store, ScriptedTemplateProvider(), asynchronous=False)
            self.addCleanup(service.close)
            with patch('validation_pipeline.template_authoring.builtin_preview_contract', return_value='a' * 64), patch('validation_pipeline.template_authoring.render_builtin', return_value={'bytes': old, 'geometry': []}) as render:
                before = service.read(reference)
                self.assertEqual(before, service.read(reference)); self.assertEqual(1, render.call_count)
            with patch('validation_pipeline.template_authoring.builtin_preview_contract', return_value='b' * 64):
                with patch('validation_pipeline.template_authoring.render_builtin', side_effect=RuntimeError('offline')):
                    self.assertEqual('failed', service.read(reference)['preview_status'])
                with patch('validation_pipeline.template_authoring.render_builtin', return_value={'bytes': new, 'geometry': []}):
                    after = service.read(reference)
            self.assertNotEqual(before['previews']['desktop']['sha256'], after['previews']['desktop']['sha256'])
            self.assertEqual(reference['template_sha256'], after['template_sha256'])
            self.assertEqual(old, service.preview(before['previews']['desktop']['sha256']))
            self.assertEqual(new, service.preview(after['previews']['desktop']['sha256']))
            self.assertEqual(2, len(store.list('builtin')))
            self.assertEqual([], store.list('version'))
