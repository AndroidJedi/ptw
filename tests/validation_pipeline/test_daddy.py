from copy import deepcopy
import base64
from io import BytesIO
import tempfile
from pathlib import Path
import unittest
from uuid import uuid4

from PIL import Image

from tests.validation_pipeline import test_studio_creatives as fixture
from tests.validation_pipeline.test_studio_creatives import PHONE_DIRECTION, _png
from validation_pipeline.studio_daddy import PRESETS, COPY, default_configuration, normalize_configuration, required_slots, build_template, device_asset
from validation_pipeline.studio_workspace import PostStudioWorkspace
from validation_pipeline.post_templates import DADDY_DEFINITION, PHONE_METRICS_DEFINITION
from validation_pipeline.provider import enforce_structured_contract_budget
from validation_pipeline.approved_posts import approved_post_copy


class DaddyProvider:
    def __init__(self, preset='bold_poster', polish=False):
        self.preset, self.polish = preset, polish
        self.calls = []
        self.fail_review = False

    def generate(self, **request):
        self.calls.append(request)
        enforce_structured_contract_budget(mode=request['mode'], system_prompt=request['system_prompt'],
            input_payload=request['input_payload'], output_schema=request['output_schema'])
        payload = request['input_payload']
        if 'presets' in payload:
            result = {'preset':self.preset,'style':'photography','reason':'A single concrete product task.',
                      'assets':[{'slot':s,'direction':f'A complete original {s} illustrating the approved Brief, without hands.'} for s in PRESETS[self.preset]['slots']]}
        elif 'strategy' in payload:
            result = {'configuration':deepcopy(payload['configuration']), 'content':{**COPY, 'hero_title':'Make room for your next step'}}
        elif 'layout_issues' in payload:
            if self.fail_review:
                self.fail_review = False
                raise RuntimeError('Interrupted visual review')
            result = {'edits':[], 'image_actions':[], 'reply':'Reviewed the PNG.', 'ready':True, 'issues':[]}
            if self.polish:
                result.update(ready=False, issues=['Improve headline spacing.'], edits=[{'path':'configuration.message.gap','value':30}])
        else:
            result = {'edits':[{'path':'content.hero_title','value':'Owner-directed copy'}], 'image_actions':[], 'reply':'Adjusted only the headline.'}
        return {'response':result, 'invocation':{'provider':'scripted-daddy'}}


class DaddyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.StudioCreativeServiceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.service = self.fixture.service
        self.provider = DaddyProvider()
        self.service.structured_provider = self.provider

    def reserve(self):
        project, brief = self.fixture.approved_brief()
        creative, _ = self.service.reserve_from_brief(brief_id=brief,template_id='daddy',requested_by='test',creative_direction=PHONE_DIRECTION)
        return project,creative['creative_id']

    def generate(self):
        project, identifier = self.reserve()
        self.service.generate(identifier)
        detail = self.service.detail(project,identifier)
        self.assertEqual('draft',detail['status'],detail.get('generation'))
        return project,identifier,detail

    def test_text_only_brief_run_renders_without_image_analysis_and_stays_editable(self):
        project,identifier,detail = self.generate()
        run = detail['generation']['daddy']
        self.assertEqual('ready_for_manual_edit',run['phase'])
        self.assertEqual('manual',run['review_mode'])
        self.assertEqual(self.service._workspace(identifier).render_preview(state_sha256=detail['state_sha256'])['bytes_sha256'],run['render_sha256'])
        self.assertEqual([],self.fixture.images.prompts)
        self.assertEqual(2,len(self.provider.calls))
        self.assertTrue(all('input_artifacts' not in call for call in self.provider.calls))
        self.assertEqual([],detail['versions'])
        again = self.service.generate(identifier)
        self.assertEqual('draft',again['status'])
        self.assertEqual(2,len(self.provider.calls))
        result = self.service.manual_agent_edit(project,identifier,request_id=str(uuid4()),base_sha256=detail['state_sha256'],
            message='Change only the headline',history=[],configuration=detail['configuration'],content=detail['content'],screenshots=[])
        self.assertEqual('Owner-directed copy',result['content']['hero_title'])
        self.assertEqual(detail['configuration'],result['configuration'])
        self.assertEqual(detail['content'],self.service.detail(project,identifier)['content'])

    def test_automatic_polish_is_skipped_even_when_provider_would_request_it(self):
        self.provider.polish = True
        _project,_identifier,detail = self.generate()
        self.assertEqual(0,detail['generation']['daddy']['corrections'])
        self.assertEqual('ready_for_manual_edit',detail['generation']['daddy']['phase'])
        self.assertEqual(2,len(self.provider.calls))

    def test_review_provider_failure_cannot_block_manual_draft(self):
        self.provider.fail_review = True
        _project,_identifier,detail = self.generate()
        self.assertEqual('draft',detail['status'])
        self.assertEqual(2,len(self.provider.calls))

    def test_interrupted_old_polish_is_kept_as_history_without_applying_it(self):
        project,identifier,detail = self.generate()
        original_configuration = detail['configuration']
        generation = deepcopy(detail['generation'])
        generation['daddy']['pending_polish'] = [{'slot':'scene','visual_direction':'Old request','enhance_current':False}]
        self.service.authority.update_creative(identifier,status='failed',generation=generation)
        self.service.retry_generation(project,identifier,request_id=str(uuid4()))
        self.service.generate(identifier)
        recovered = self.service.detail(project,identifier)
        self.assertEqual(original_configuration,recovered['configuration'])
        self.assertEqual(2,len(self.provider.calls))
        self.assertEqual(generation['daddy']['pending_polish'],recovered['generation']['daddy']['skipped_polish'])
        self.assertNotIn('pending_polish',recovered['generation']['daddy'])

    def test_partial_asset_failure_retains_screen_and_resumes_only_missing_feature(self):
        self.provider.preset='phone_feature'
        original=self.fixture.images.generate
        calls=[]
        def failing(prompt,**kwargs):
            calls.append(prompt)
            if len(calls)==2:raise RuntimeError('Feature generation interrupted')
            return original(prompt,**kwargs)
        self.fixture.images.generate=failing
        project,identifier=self.reserve()
        with self.assertRaisesRegex(RuntimeError,'Feature'):
            self.service.generate(identifier)
        workspace=self.service._workspace(identifier)
        screen=workspace._asset_record('screen')['sha256']
        self.assertIsNone(workspace._asset_record('feature'))
        self.service.retry_generation(project,identifier)
        self.service.generate(identifier)
        self.assertEqual(3,len(calls))
        self.assertEqual(screen,workspace._asset_record('screen')['sha256'])
        self.assertEqual('draft',self.service.detail(project,identifier)['status'])

    def test_explicit_polish_is_idempotent_and_preserves_owner_copy(self):
        project,identifier,detail=self.generate()
        copy={**detail['content'],'hero_title':'The owner chose this headline'}
        request=dict(request_id=str(uuid4()),base_sha256=detail['state_sha256'],configuration=detail['configuration'],content=copy)
        _,created=self.service.recompose_daddy(project,identifier,**request)
        self.assertTrue(created)
        self.assertFalse(self.service.recompose_daddy(project,identifier,**request)[1])
        self.service.generate(identifier)
        self.assertEqual(copy,self.service.detail(project,identifier)['content'])
        self.assertFalse(self.service.recompose_daddy(project,identifier,**request)[1])

    def test_startup_requires_explicit_daddy_resume_without_repeating_completed_assets(self):
        project,identifier,detail=self.generate()
        self.service.authority.update_creative(identifier,status='composing')
        self.assertEqual([],self.service.recover_interrupted())
        self.assertEqual('failed',self.service.detail(project,identifier)['status'])
        self.assertEqual(2,len(self.provider.calls))
        self.service.retry_generation(project,identifier)
        self.service.generate(identifier)
        self.assertEqual(2,len(self.provider.calls))
        self.assertEqual('draft',self.service.detail(project,identifier)['status'])

    def test_independent_assets_idempotency_stale_history_approval_clone(self):
        project,identifier,detail = self.generate()
        request = {'slot':'subject','request_id':str(uuid4()),'base_sha256':detail['state_sha256'],'action':'upload',
                   'options':{'image':{'mime_type':'image/png','bytes_base64':base64.b64encode(_png('#FA4B39')).decode()}}}
        next_detail = self.service.mutate(project,identifier,'daddy_asset_operation',**request)
        repeated = self.service.mutate(project,identifier,'daddy_asset_operation',**request)
        self.assertEqual(next_detail['state_sha256'],repeated['state_sha256'])
        with self.assertRaises(RuntimeError):
            self.service.mutate(project,identifier,'daddy_asset_operation',**{**request,'request_id':str(uuid4())})
        with self.assertRaises(KeyError):
            self.service.mutate(str(uuid4()),identifier,'daddy_asset_operation',**request)
        workspace = self.service._workspace(identifier)
        history = workspace.daddy_asset_history('subject')
        self.assertEqual(1,len(history))
        self.assertEqual(_png('#FA4B39'),workspace.daddy_asset_image('subject',history[0]['sha256'])['bytes'])
        for color in ('#AABBCC','#DDEEFF','#112233'):
            next_detail = self.service.mutate(project,identifier,'daddy_asset_operation',**{**request,'request_id':str(uuid4()),'base_sha256':next_detail['state_sha256'],
                'options':{'image':{'mime_type':'image/png','bytes_base64':base64.b64encode(_png(color)).decode()}}})
        self.assertEqual(3,len(workspace.daddy_asset_history('subject')))
        approved = self.service.checkpoint(project,identifier,kind='approve',base_sha256=next_detail['state_sha256'],configuration=next_detail['configuration'],content=next_detail['content'],change_note='test')
        self.assertEqual(1,len(approved['creative']['versions']))
        clone,created = self.service.clone_approved_version(project_id=project,source_creative_id=identifier,source_version=1,request_id=str(uuid4()),requested_by='test')
        cloned = self.service.detail(project,clone['creative_id'])
        self.assertTrue(created)
        self.assertEqual('daddy',cloned['template_id'])
        self.assertEqual(next_detail['content'],cloned['content'])
        self.assertEqual(workspace._asset_record('subject')['sha256'],self.service._workspace(clone['creative_id'])._asset_record('subject')['sha256'])
        source = workspace._asset_record('subject')['source']
        clone_workspace = self.service._workspace(clone['creative_id'])
        self.assertEqual(_png('#112233'), (clone_workspace.assets / source['original_filename']).read_bytes())

    def test_switch_preserves_copy_and_returns_owner_configuration(self):
        project,identifier,detail = self.generate()
        content = {**detail['content'],'hero_title':'Owner headline'}
        configuration = deepcopy(detail['configuration']); configuration['message']['title_size']=68
        switched = self.service.mutate(project,identifier,'switch_template',request_id=str(uuid4()),base_sha256=detail['state_sha256'],
            template_reference=PHONE_METRICS_DEFINITION.identity.to_reference(),configuration=configuration,content=content)
        self.assertEqual('Owner headline',switched['content']['hero_title'])
        restored = self.service.mutate(project,identifier,'switch_template',request_id=str(uuid4()),base_sha256=switched['state_sha256'],
            template_reference=DADDY_DEFINITION.identity.to_reference(),configuration=switched['configuration'],content=switched['content'])
        self.assertEqual(68,restored['configuration']['message']['title_size'])
        self.assertEqual('Owner headline',restored['content']['hero_title'])

    def test_every_preset_english_ukrainian_and_visibility(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = PostStudioWorkspace(Path(root))
            detail=workspace.apply_template(base_sha256=workspace.state_sha256(),template_id='daddy')
            for preset in PRESETS:
                for headline in ('Make room for what matters','Знайдіть час для важливого'):
                    config=default_configuration(preset)
                    rendered=workspace.render_preview(state_sha256=detail['state_sha256'],configuration=config,content={**COPY,'hero_title':headline})
                    self.assertEqual((1080,1350),Image.open(BytesIO(rendered['bytes'])).size)
                    self.assertFalse(rendered['layout_issues'],(preset,headline,rendered['layout_issues']))
            config=default_configuration(); config['message']['enabled']=False; config['action']['enabled']=False
            self.assertEqual('',approved_post_copy({'configuration':config,'content':COPY})['instagram_caption'])
            self.assertNotIn('hero_title',build_template(config,COPY).document['semantic_roles'].get('headline',[]))

    def test_device_has_clearance_and_no_hand_pose(self):
        self.assertNotIn('handheld',PRESETS)
        for pose in ('portrait','landscape','angled'):
            image=Image.open(BytesIO(device_asset(_png(),pose)['bytes']))
            if pose=='angled':
                left,top,right,bottom=image.getbbox()
                self.assertGreater(left,0); self.assertGreater(top,0)
                self.assertLess(right,image.width);self.assertLess(bottom,image.height)
        config=default_configuration(); config['device']['pose']='handheld'
        with self.assertRaises(ValueError): normalize_configuration(config)

    def test_flow_uses_exact_font_and_optional_feature_and_price_are_semantic(self):
        from validation_pipeline.approved_posts import visible_post_content
        from validation_pipeline.studio import StudioRenderer
        config=default_configuration('phone_feature')
        copy={**COPY,'feature_title':'Book a lesson','feature_text':'Choose an available session'}
        config['device']['feature_enabled']=False
        self.assertNotIn('feature',required_slots(config))
        self.assertNotIn('feature_title',visible_post_content({'configuration':config,'content':copy}))
        config['message']['font']='Manrope'
        short=build_template(config,copy).document['root']['children']
        long=build_template(config,{**copy,'hero_title':'Плануйте заняття у зручний для вас час без зайвого листування'}).document['root']['children']
        by_id=lambda nodes,key:next(n['props'] for n in nodes if n['id']==key)
        self.assertEqual('Manrope',by_id(long,'hero_title')['font_family'])
        self.assertGreater(by_id(long,'device')['y'],by_id(short,'device')['y'])
        config=default_configuration('offer_collage')
        copy={**COPY,'offer':'2 900 грн','previous_price':'3 900 грн'}
        nodes=build_template(config,copy).document['root']['children']
        self.assertTrue(any(n['id']=='previous_price_strike' for n in nodes))
        self.assertIn('Раніше: 3 900 грн',approved_post_copy({'configuration':config,'content':copy})['instagram_caption'])
        copy['offer']=''
        self.assertNotIn('previous_price',visible_post_content({'configuration':config,'content':copy}))

    def test_missing_assets_block_approval_and_scoped_history_does_not_build_detail(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from validation_pipeline.studio_routes import studio_creative_router
        from unittest.mock import patch
        project,identifier,detail=self.generate()
        workspace=self.service._workspace(identifier)
        saved=workspace.save_configuration(base_sha256=detail['state_sha256'],configuration=default_configuration('blurred_phone'),content=detail['content'])
        with self.assertRaisesRegex(ValueError,'required Daddy images'):
            workspace.approve_version(state_sha256=saved['state_sha256'],change_note='Incomplete')
        app=FastAPI();app.include_router(studio_creative_router(self.service,prefix='/studio'))
        with TestClient(app) as client, patch.object(self.service,'detail',side_effect=AssertionError('Heavy detail must not run')):
            path=f'/studio/projects/{project}/creatives/{identifier}/assets/screen/history'
            self.assertEqual(200,client.get(path).status_code)
            self.assertEqual(404,client.get(path.replace(project,str(uuid4()))).status_code)

    def test_tuned_template_requires_review_and_preserves_only_reusable_settings(self):
        from validation_pipeline.template_authoring import TemplateAuthoringService
        from validation_pipeline.template_store import TemplateStore
        from tests.validation_pipeline.test_template_authoring import ScriptedTemplateProvider
        authoring = TemplateAuthoringService(TemplateStore(self.fixture.root/'templates.sqlite3'),ScriptedTemplateProvider(),asynchronous=False)
        self.addCleanup(authoring.close)
        config=default_configuration();config['message']['title_size']=92
        run=authoring.start({'request_id':str(uuid4()),'scope':'post','instruction':'Preserve this tuned composition.','daddy_configuration':config})
        self.assertEqual('proposed',run['status'],run.get('error'))
        self.assertEqual(1,run['iterations'])
        self.assertNotIn('content',run['documents']['post'])
        self.assertTrue(all(not c['asset_id'] for c in run['documents']['post']['components']))
        accepted=authoring.decide(run['run_id'],{'request_id':str(uuid4()),'base_sha256':run['state_sha256'],'decision':'accept'})
        definition=authoring.post_registry().resolve_reference({k:v for k,v in accepted['accepted_versions'][0].items() if k!='surface'})
        self.assertEqual('post.daddy.react',definition.editor_key)
        self.assertEqual(92,definition.default_configuration()['message']['title_size'])
