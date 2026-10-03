from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json, unittest
from validation_pipeline import landing_marketing as marketing
from validation_pipeline.landing_workspace import LandingWorkspace, normalize_configuration, normalize_content
from validation_pipeline.landing_templates import APP_SHOWCASE_V2_DEFINITION
from validation_pipeline.landing_pages import landing_generation_schema
from validation_pipeline.landing_publication import selected_assets
from validation_pipeline.image_generation_policy import compile_image_prompt
from tests.validation_pipeline.test_app_showcase import service, MemoryAuthority, showcase_content
from tests.validation_pipeline.test_landing_workspace import FakeImages, complete_content


def complete_marketing():
    value = deepcopy(marketing.DEFAULT_CONTENT)
    for key in marketing.TEXT_LIMITS: value[key] = 'Project grounded example content'
    for key in ('comparison_rows', 'walkthrough_steps', 'values'):
        for row in value[key]:
            for field in row:
                if field != 'enabled': row[field] = 'Project grounded example content'
    return value


class MarketingTests(unittest.TestCase):
    def test_feedback_publication_patch_changes_only_optional_examples(self):
        from scripts.update_published_landing_feedback import feedback_content
        original = complete_content(); original['marketing'] = complete_marketing()
        snapshot = deepcopy(original)
        examples = [{'topic': 'Composition', 'statement': 'I want to understand the label.'} for _ in range(3)]
        revised = feedback_content(original, examples)
        self.assertEqual(original, snapshot)
        self.assertEqual(revised['social_proof'], original['social_proof'])
        revised['marketing'].pop('feedback_examples')
        self.assertEqual(revised, original)
        with self.assertRaisesRegex(ValueError, 'Complete all three'):
            feedback_content(original, [{'topic': '', 'statement': ''} for _ in range(3)])

    def test_optional_feedback_survives_save_approval_restart_without_changing_legacy_content(self):
        legacy = complete_marketing()
        self.assertEqual(marketing.normalize_content(legacy), legacy)
        self.assertNotIn('feedback_examples', legacy)
        v = complete_content(); v['marketing'] = legacy
        v['social_proof']['items'] = []
        v['marketing']['feedback_examples'] = [
            {'topic': 'Compare water labels', 'statement': 'I want to compare water composition in one place.'},
            {'topic': 'Understand composition', 'statement': 'I would like plain explanations of mineralization.'},
            {'topic': 'Match my taste', 'statement': 'I want a choice that reflects my preferences.'},
        ]
        with TemporaryDirectory() as root:
            w = LandingWorkspace(root, image_provider=FakeImages())
            c = w._configuration(); c['marketing'] = deepcopy(marketing.DEFAULT_CONFIGURATION)
            d = w.save_configuration(base_sha256=w.state_sha256(), configuration=c, content=v)
            for slot in w.visual_slots:
                d = w.generate_visual(base_sha256=d['state_sha256'], slot=slot, visual_direction='Full mockup composition', prompt='sample')
            w.approve_configuration(base_sha256=d['state_sha256'], configuration=c, content=v, change_note='Product feedback expectations')
            restored = LandingWorkspace(root, image_provider=FakeImages())
            self.assertEqual(restored.detail()['content'], v)
            self.assertEqual(restored.version_detail(1)['content'], v)
            self.assertEqual(restored.detail()['content']['social_proof']['items'], [])

    def test_feedback_count_shape_and_lengths_and_visible_incomplete_approval(self):
        v = complete_marketing()
        v['feedback_examples'] = [{'topic': 'Topic', 'statement': 'An illustrative expectation.'} for _ in range(3)]
        self.assertEqual(marketing.normalize_content(v), v)
        for mutate in (
            lambda x: x['feedback_examples'].pop(),
            lambda x: x['feedback_examples'][0].update(attribution='Invented visitor'),
            lambda x: x['feedback_examples'][0].update(topic='x' * 121),
            lambda x: x['feedback_examples'][0].update(statement='x' * 361),
        ):
            bad = deepcopy(v); mutate(bad)
            with self.assertRaises(ValueError): marketing.normalize_content(bad)
        v['feedback_examples'][0]['statement'] = ''
        self.assertEqual(marketing.normalize_content(v), v)
        c = {'marketing': deepcopy(marketing.DEFAULT_CONFIGURATION)}
        with self.assertRaisesRegex(ValueError, 'feedback examples'):
            marketing.approval_ready(c, {'marketing': v})
        c['marketing']['reference_reviews_enabled'] = False
        marketing.approval_ready(c, {'marketing': v})
        c['marketing']['reference_reviews_enabled'] = True
        marketing.approval_ready(c, {'marketing': v, 'social_proof': {'items': [{'statement': 'Editable feedback', 'attribution': 'Visitor'}]}})

    def test_preserving_normalization_and_bounded_sections(self):
        directory = TemporaryDirectory(); self.addCleanup(directory.cleanup)
        legacy = LandingWorkspace(directory.name)
        self.assertNotIn('marketing', legacy._configuration())
        self.assertEqual(len(legacy.visual_slots), 2)
        c = legacy._configuration(); c['marketing'] = deepcopy(marketing.DEFAULT_CONFIGURATION)
        v = complete_content(); v['marketing'] = complete_marketing()
        self.assertEqual(normalize_content(v), v)
        self.assertEqual(normalize_configuration(c), c)
        for field, invalid in [('gradient_id', 'arbitrary'), ('logo_color', 'red'), ('motifs_enabled', 1), ('carousel_speed', 0), ('motif_opacity', 2)]:
            bad = deepcopy(c); bad['marketing'][field] = invalid
            with self.assertRaises(ValueError): normalize_configuration(bad)
        for url in ['javascript:alert(1)', 'https://example.com/app', 'https://apps.apple.com.evil.test/app']:
            bad = deepcopy(v); bad['marketing']['apple_url'] = url
            with self.assertRaises(ValueError): normalize_content(bad)
        bad = deepcopy(v); bad['marketing']['comparison_rows'].pop()
        with self.assertRaises(ValueError): normalize_content(bad)

    def test_logo_inheritance_domain_gradients_and_browser_defaults(self):
        inherited = marketing.initial_design({'product': 'Aura meditation'}, {'configuration': {'logo': {'symbol_color': '#ABCDEF', 'name_color': '#112233'}}})
        self.assertEqual(inherited['logo_color'], '#102335')
        self.assertEqual(marketing.initial_design({'product': 'Aura meditation'}, {'configuration': {'logo': {'symbol_color': '#102335'}}})['logo_color'], '#102335')
        # Explicit saved colors are normalized, never silently contrast-corrected.
        self.assertEqual(marketing.normalize_configuration({**inherited, 'logo_color': '#abcdef'})['logo_color'], '#abcdef')
        self.assertEqual(inherited['gradient_id'], 'aurora')
        self.assertEqual(len(marketing.GRADIENTS), 10)
        self.assertEqual(marketing.initial_design({}, {'configuration': {'logo': {'symbol_color': '#ffffff'}}})['gradient_id'], 'ocean')
        data = json.loads(Path('apps/commander-web/src/landing/marketing-defaults.json').read_text())
        self.assertEqual(data, {'configuration': marketing.DEFAULT_CONFIGURATION, 'content': marketing.DEFAULT_CONTENT, 'gradients': marketing.GRADIENTS})

    def test_missing_items_require_completion_or_hiding(self):
        c = {'marketing': deepcopy(marketing.DEFAULT_CONFIGURATION)}
        v = {'marketing': complete_marketing()}
        v['marketing']['comparison_rows'][4]['text'] = ''
        with self.assertRaisesRegex(ValueError, 'Complete or hide'): marketing.approval_ready(c, v)
        v['marketing']['comparison_rows'][4]['enabled'] = False
        marketing.approval_ready(c, v)
        self.assertEqual(len(v['marketing']['comparison_rows']), 6)

    def test_optional_mockup_generation_enhancement_restart_and_public_selection(self):
        with TemporaryDirectory() as root:
            images = FakeImages(); w = LandingWorkspace(root, image_provider=images)
            c = w._configuration(); c['marketing'] = deepcopy(marketing.DEFAULT_CONFIGURATION)
            v = complete_content(); v['marketing'] = complete_marketing()
            d = w.save_configuration(base_sha256=w.state_sha256(), configuration=c, content=v)
            for slot in w.visual_slots:
                d = w.generate_visual(base_sha256=d['state_sha256'],slot=slot,visual_direction='Full mockup composition',prompt='sample')
            first = w.visual_image('walkthrough_visual', d['assets'][-1]['sha256'])['bytes']
            d = w.generate_visual(base_sha256=d['state_sha256'],slot='walkthrough_visual',visual_direction='Enhance the second phone',prompt='sample',enhance_current=True)
            self.assertEqual(images.references[-1], first)
            w.approve_configuration(base_sha256=d['state_sha256'],configuration=c,content=v,change_note='Marketing sections')
            record = w.version_detail(1)
            self.assertIn('walkthrough_visual', selected_assets(record))
            restored = LandingWorkspace(root, image_provider=images)
            self.assertEqual(restored.state_sha256(), w.state_sha256())
            self.assertEqual(len(restored.detail()['assets'][-1]['history']), 2)
            c['marketing']['walkthrough_enabled'] = False
            d = w.save_configuration(base_sha256=w.state_sha256(), configuration=c, content=v)
            self.assertTrue(d['assets'][-1]['available'])
            w.approve_configuration(base_sha256=d['state_sha256'], configuration=c,content=v,change_note='Hide walkthrough')
            self.assertNotIn('walkthrough_visual', selected_assets(w.version_detail(2)))
            self.assertIn('walkthrough_visual', selected_assets(record))

    def test_agent_controls_mockups_and_preserves_endpoints(self):
        class Agent:
            def call(self, **kwargs):
                self.payload = kwargs['input_payload']
                self.system_prompt = kwargs['system_prompt']
                return {'response': kwargs['response_validator']({'edits': [{'path': 'configuration.marketing.gradient_id', 'value': 'aurora'}, {'path': 'content.marketing.walkthrough_visual_direction', 'value': 'Enhance the phone mockups with a calm violet palette'}, {'path': 'content.social_proof.items[0].statement', 'value': 'The item list is easier to compare at a glance.'}, {'path': 'content.social_proof.items[0].attribution', 'value': 'Olena, Kyiv'}], 'image_actions': [{'slot': 'walkthrough_visual', 'visual_direction': 'Enhance the phone mockups with a calm violet palette', 'enhance_current': False, 'reference_index': 0}], 'reply': 'Updated mockups and feedback'}), 'invocation': {}}
        with TemporaryDirectory() as root:
            authority=MemoryAuthority(); authority.page['status']='draft'; provider=Agent(); active=service(Path(root),authority,provider=provider)
            w=active._workspace(authority.page['landing_id']); c=w._configuration(); c['marketing']=deepcopy(marketing.DEFAULT_CONFIGURATION); v=showcase_content();v['marketing']=complete_marketing()
            v['social_proof']['items'] = [{'statement': 'The list is helpful.', 'attribution': 'Visitor'}]
            d=w.save_configuration(base_sha256=w.state_sha256(),configuration=c,content=v)
            from uuid import uuid4
            result=active.manual_agent_edit(authority.page['project_id'],authority.page['landing_id'],request_id=str(uuid4()),base_sha256=d['state_sha256'],message='Use aurora and generate calm phone mockups',history=[],screenshots=[],configuration=c,content=v)
            self.assertEqual(result['configuration']['marketing']['gradient_id'],'aurora')
            self.assertEqual(result['content']['social_proof']['items'][0], {'statement': 'The item list is easier to compare at a glance.', 'attribution': 'Olena, Kyiv'})
            self.assertIn('Change feedback copy or registered portraits only when the owner requests it.', provider.system_prompt)
            self.assertEqual(result['image_actions'][0]['slot'],'walkthrough_visual')
            context=active._image_context(authority.page,'walkthrough_visual',v['marketing']['walkthrough_visual_direction'],c,base_sha256=d['state_sha256'])
            self.assertEqual(context['destination']['mode'],'app_mockup')
            self.assertEqual(context['destination']['crop']['fit'],'contain')
            self.assertIn('complete phone hardware',compile_image_prompt(context))
            self.assertEqual(context['settings']['primary_gradient']['id'],'ocean')

    def test_new_template_retains_v1_and_composition_structure(self):
        from validation_pipeline.landing_templates import APP_SHOWCASE_DEFINITION, APP_SHOWCASE_V2_DEFINITION, LANDING_TEMPLATE_REGISTRY
        ref={k:v for k,v in APP_SHOWCASE_DEFINITION.identity.to_reference().items() if k!='surface'}
        self.assertEqual(LANDING_TEMPLATE_REGISTRY.resolve_reference(ref).identity.template_version,1)
        self.assertEqual(LANDING_TEMPLATE_REGISTRY.get('app_showcase').identity.template_version,3)
        ref2={k:v for k,v in APP_SHOWCASE_V2_DEFINITION.identity.to_reference().items() if k!='surface'}
        self.assertEqual(LANDING_TEMPLATE_REGISTRY.resolve_reference(ref2).identity.template_version,2)
        schema=landing_generation_schema('app_showcase',marketing=True)['properties']['content']['properties']['marketing']['properties']
        self.assertEqual(schema['comparison_rows']['minItems'],6)
        self.assertEqual(schema['walkthrough_steps']['maxItems'],4)
        self.assertNotIn('apple_url',schema)
        feedback = landing_generation_schema('app_showcase', marketing=True)['properties']['content']['properties']['social_proof']['properties']['items']
        self.assertEqual((feedback['minItems'], feedback['maxItems']), (5, 5))
        self.assertEqual(feedback['items']['properties']['statement']['maxLength'], 360)
        self.assertEqual(feedback['items']['properties']['attribution']['maxLength'], 120)
