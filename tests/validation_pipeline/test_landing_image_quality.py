from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import base64
import hashlib
import json
import subprocess
import unittest

import httpx
from PIL import Image, ImageDraw

from validation_pipeline.image_output import IMAGE_OUTPUT_VERSION, output_specification, normalize_output_specification
from validation_pipeline.landing_image_preparation import prepare_mockup
from validation_pipeline.openai_images import LocalCodexPhoneScreenImageProvider, OpenAIPhoneScreenImageProvider, ResultBridgePhoneScreenImageProvider
from validation_pipeline.landing_workspace import LandingWorkspace
from validation_pipeline.visual_models import visual_agent_model
from tests.validation_pipeline.test_landing_workspace import FakeImages, complete_content
from tests.validation_pipeline.test_landing_marketing import complete_marketing
from validation_pipeline.landing_marketing import DEFAULT_CONFIGURATION


def png(width, height, *, alpha=False):
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0) if alpha else 'white')
    draw = ImageDraw.Draw(image)
    for x in (.1, .55):
        box = (round(width*x), round(height*.18), round(width*(x+.32)), round(height*.82))
        draw.rounded_rectangle(box, radius=12, fill='#17263c')
        draw.rectangle((box[0]+8,box[1]+20,box[2]-8,box[3]-20), fill='white')
    out = BytesIO(); image.save(out, 'PNG'); return out.getvalue()


class ImageOutputTests(unittest.TestCase):
    def test_specs_keep_post_default_and_express_screen_and_mockup_geometry(self):
        square = output_specification({'surface':'post','mode':'phone'})
        screen = output_specification({'mode':'app_screen'})
        mockup = output_specification({'mode':'app_mockup'})
        self.assertEqual((square['width'],square['height']), (1024,1024))
        self.assertAlmostEqual(screen['width']/screen['height'], 9/19.5)
        self.assertGreater(screen['safe_area']['top'], .06)
        self.assertEqual((mockup['width'],mockup['height'],mockup['background']), (1536,1152,'transparent'))
        for change in ({'width':True}, {'width':8192}, {'schema':'unknown'}, {'background':'scene'}, {'safe_area':{'top':1}}):
            with self.assertRaises(ValueError): normalize_output_specification({**screen,**change})

    def test_api_uses_requested_size_and_preserves_image_model(self):
        spec = output_specification({'mode':'app_screen'}); seen=[]
        def handle(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(png(864,1872)).decode()}]})
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            provider=OpenAIPhoneScreenImageProvider('test',client=client)
            result=provider.generate('A realistic Ukrainian hotel app screenshot',output_spec=spec)
            changed=provider.generate('A realistic Ukrainian hotel app screenshot',output_spec={**spec,'safe_area':{**spec['safe_area'],'top':.1}})
        self.assertNotEqual(result['source']['request_fingerprint'],changed['source']['request_fingerprint'])
        self.assertEqual(seen[0]['size'],'864x1872')
        self.assertEqual(seen[0]['model'],'gpt-image-2')
        self.assertEqual(result['source']['output_spec'],spec)

    def test_local_worker_pins_astra_and_rejects_square_screen_output_once(self):
        spec=output_specification({'mode':'app_screen'}); calls=[]
        with TemporaryDirectory() as directory:
            root=Path(directory)
            def execute(command, **kwargs):
                calls.append((command, kwargs['input']))
                path=root/'images'/'asset.png';path.parent.mkdir(exist_ok=True)
                path.write_bytes(png(1024,1024))
                Path(command[command.index('--output-last-message')+1]).write_text(str(path))
                return subprocess.CompletedProcess(command,0,stdout='',stderr='')
            provider=LocalCodexPhoneScreenImageProvider('test-codex',executor=execute,generated_root=root/'images',model='gpt-6-astra')
            with self.assertRaisesRegex(ValueError,'aspect ratio'):
                provider.generate('A realistic Ukrainian hotel app screenshot',output_spec=spec)
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0][0][calls[0][0].index('--model')+1],'gpt-6-astra')
            self.assertIn('864x1872',calls[0][1])
            self.assertFalse((root/'images'/'asset.png').exists())

    def test_bridge_output_capability_fails_before_submission(self):
        seen=[]
        def handle(request):
            seen.append(request.method)
            return httpx.Response(200,json={'image_generation_policies':['ptw.domain-image.v1']})
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            provider=ResultBridgePhoneScreenImageProvider('http://bridge','test',client=client)
            with self.assertRaisesRegex(RuntimeError,'image-output worker'):
                provider.generate('A realistic Ukrainian hotel app screenshot',output_spec=output_specification({'mode':'app_screen'}))
        self.assertEqual(seen,['GET'])

    def test_bridge_dimensions_background_and_fingerprint_survive_transport(self):
        requests=[]; generated=png(1536,1152,alpha=True); digest=hashlib.sha256(generated).hexdigest()
        def handle(request):
            if request.url.path.endswith('/capabilities'):
                return httpx.Response(200,json={'image_generation_policies':['ptw.domain-image.v1'],'image_output_specs':[IMAGE_OUTPUT_VERSION]})
            if request.method=='POST':
                requests.append(json.loads(request.content));return httpx.Response(200,json={'request_id':42})
            if request.url.path.endswith('/asset'):return httpx.Response(200,content=generated)
            return httpx.Response(200,json={'status':'completed','result':{'invocation':{'model':'gpt-6-astra'},'image':{'digest':digest,'output_digest':digest,'mime_type':'image/png','width':1536,'height':1152,'resolved_model':'test-pixel-model'}}})
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            provider=ResultBridgePhoneScreenImageProvider('http://bridge','test',client=client)
            spec=output_specification({'mode':'app_mockup'})
            result=provider.generate('Hotel app walkthrough with complete phones',output_spec=spec)
            provider.generate('Hotel app walkthrough with complete phones',output_spec={**spec,'background':'opaque'})
        self.assertEqual(requests[0]['input_payload']['output_spec'],spec)
        self.assertEqual(requests[0]['model'],'gpt-6-astra')
        self.assertNotEqual(requests[0]['idempotency_key'],requests[1]['idempotency_key'])
        self.assertEqual(result['source']['agent_model'],'gpt-6-astra')
        self.assertEqual(result['source']['image_model'],'test-pixel-model')


class MockupPreparationTests(unittest.TestCase):
    def test_native_alpha_trim_preserves_both_devices_and_white_screens(self):
        raw=png(768,576,alpha=True)
        with patch('validation_pipeline.landing_image_preparation.cutout_png',side_effect=AssertionError('native alpha must not be segmented')):
            prepared,meta=prepare_mockup(raw)
        image=Image.open(BytesIO(prepared))
        self.assertEqual(meta['method'],'native_alpha')
        self.assertLess(image.width,768);self.assertLess(image.height,576)
        dx,dy=meta['crop_box'][:2]
        for x in (round(768*.25),round(768*.7)):
            self.assertEqual(image.getpixel((x-dx,288-dy)),(255,255,255,255))
        self.assertEqual(image.getpixel((round(768*.49)-dx,288-dy))[3],0)
        self.assertEqual(meta['raw_sha256'],hashlib.sha256(raw).hexdigest())

    def test_opaque_segmentation_fills_enclosed_white_screen_holes(self):
        raw=png(768,576)
        segmented=Image.open(BytesIO(png(768,576,alpha=True)))
        ImageDraw.Draw(segmented).rectangle((110,140,290,430),fill=(255,255,255,0))
        data=BytesIO();segmented.save(data,'PNG')
        with patch('validation_pipeline.landing_image_preparation.cutout_png',return_value=data.getvalue()):
            prepared,meta=prepare_mockup(raw)
        image=Image.open(BytesIO(prepared));dx,dy=meta['crop_box'][:2]
        self.assertEqual(image.getpixel((200-dx,250-dy)),(255,255,255,255))
        self.assertEqual(meta['method'],'pinned_cutout')

    def test_failures_stale_results_raw_retention_and_restart(self):
        with TemporaryDirectory() as directory:
            images=FakeImages();w=LandingWorkspace(directory,image_provider=images)
            c=w._configuration();c['marketing']=deepcopy(DEFAULT_CONFIGURATION)
            v=complete_content();v['marketing']=complete_marketing()
            w.save_configuration(base_sha256=w.state_sha256(),configuration=c,content=v)
            context={'output_spec':output_specification({'mode':'app_mockup'}), 'instruction':{'origin':'generated'}}
            for slot in w.visual_slots:
                w.generate_visual(base_sha256=w.state_sha256(),slot=slot,visual_direction='Hotel workflow mockups',prompt='test',image_context=context if slot=='walkthrough_visual' else None)
            w.approve_configuration(base_sha256=w.state_sha256(),configuration=c,content=v,change_note='Test prepared publication')
            approved=w.version_detail(1);meta=approved['assets'][-1]['preparation']
            raw_path=w.assets/'raw'/f"{meta['raw_sha256']}.png"
            self.assertTrue(raw_path.is_file())
            before=w.detail()
            with patch('validation_pipeline.landing_image_preparation.prepare_mockup',side_effect=ValueError('Cannot separate background')):
                with self.assertRaises(ValueError):
                    w.generate_visual(base_sha256=w.state_sha256(),slot='walkthrough_visual',visual_direction='Improve phone mockups',prompt='test',image_context=context)
            self.assertEqual(w.detail(),before)
            for _ in range(4):
                w.generate_visual(base_sha256=w.state_sha256(),slot='walkthrough_visual',visual_direction='Improve phone mockups',prompt='test',image_context=context)
            self.assertTrue(raw_path.is_file())
            self.assertEqual(w.version_detail(1),approved)
            restored=LandingWorkspace(directory,image_provider=images)
            self.assertEqual(restored.detail(),w.detail())
            # Late preparation must not overwrite owner changes either.
            original=prepare_mockup
            def stale(data):
                content=w._content();content['hero']['title']='Keep latest owner edit'
                w.save_configuration(base_sha256=w.state_sha256(),configuration=c,content=content)
                return original(data)
            selected=w._selected('walkthrough_visual')
            with patch('validation_pipeline.landing_image_preparation.prepare_mockup',side_effect=stale):
                with self.assertRaisesRegex(RuntimeError,'changed'):
                    w.generate_visual(base_sha256=w.state_sha256(),slot='walkthrough_visual',visual_direction='Improve phone mockups',prompt='test',image_context=context)
            self.assertEqual(w._selected('walkthrough_visual'),selected)


class VisualRoutingTests(unittest.TestCase):
    def test_visual_setting_does_not_change_brief_setting(self):
        from validation_pipeline.config import Settings
        with patch.dict('os.environ',{'PTW_VISUAL_AGENT_MODEL':'gpt-6-astra','VALIDATION_LLM_MODEL':'brief-model','DATABASE_URL':'postgresql://unused','OWNER_GATEWAY_BRIDGE_TOKEN':'test','LLM_BRIDGE_URL':'http://bridge','LLM_BRIDGE_TOKEN':'test','PEXELS_API_KEY':'test'}):
            settings=Settings.from_environment()
        self.assertEqual(settings.visual_model,'gpt-6-astra');self.assertEqual(settings.model,'brief-model')
        with patch.dict('os.environ',{'PTW_VISUAL_AGENT_MODEL':''}):
            self.assertEqual(visual_agent_model(),'gpt-6-astra')
        with patch.dict('os.environ',{'PTW_VISUAL_AGENT_MODEL':'visual-override'}):
            self.assertEqual(ResultBridgePhoneScreenImageProvider('http://bridge','test').model,'visual-override')
            self.assertEqual(LocalCodexPhoneScreenImageProvider('test',executor=lambda *a,**k: None).model,'visual-override')

    def test_production_factory_routes_visual_services_separately(self):
        from validation_pipeline.api import create_app
        from validation_pipeline.config import Settings
        from unittest.mock import MagicMock
        settings=Settings(database_url='postgresql://unused',owner_gateway_token='test',bridge_url='http://bridge',bridge_token='test',pexels_api_key='test',model='brief-and-analytics',visual_model='gpt-6-astra')
        names=['StudioCreativeService','LandingService','TemplateAuthoringService','CreativeAnalyticsService','ValidationRunner']
        with __import__('contextlib').ExitStack() as stack:
            constructors={name:stack.enter_context(patch('validation_pipeline.api.'+name)) for name in names}
            stack.enter_context(patch('validation_pipeline.api.TemplateStore'))
            create_app(settings=settings,repository=MagicMock(),landing_publication_service=MagicMock(),instagram_service=MagicMock())
        self.assertEqual(constructors['StudioCreativeService'].call_args.kwargs['structured_provider'].model,'gpt-6-astra')
        self.assertEqual(constructors['LandingService'].call_args.kwargs['structured_provider'].model,'gpt-6-astra')
        self.assertEqual(constructors['TemplateAuthoringService'].call_args.args[1].model,'gpt-6-astra')
        self.assertEqual(constructors['CreativeAnalyticsService'].call_args.kwargs['structured_provider'].model,'brief-and-analytics')
        self.assertEqual(constructors['ValidationRunner'].call_args.args[1].model,'brief-and-analytics')

    def test_local_factory_keeps_brief_and_analytics_independent(self):
        from validation_pipeline.studio_local_api import create_app
        from unittest.mock import MagicMock
        from contextlib import ExitStack
        with TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.dict('os.environ', {
                'STUDIO_WORKSPACE_PATH': str(Path(directory)/'studio'),
                'LOCAL_BRIEF_PATH': str(Path(directory)/'brief'),
                'STUDIO_PHONE_IMAGE_PROVIDER': 'disabled',
                'LOCAL_CODEX_MODEL': 'brief-local', 'PTW_VISUAL_AGENT_MODEL': 'gpt-6-astra',
                'LOCAL_CODEX_REASONING_EFFORT': 'high',
            }))
            names=['StudioCreativeService','LandingService','TemplateAuthoringService','CreativeAnalyticsService']
            constructors={name:stack.enter_context(patch('validation_pipeline.studio_local_api.'+name)) for name in names}
            stack.enter_context(patch('validation_pipeline.studio_local_api.TemplateStore'))
            stack.enter_context(patch('validation_pipeline.studio_local_api.LocalAuthorization'))
            create_app(instagram_service=MagicMock())
            for name in ['StudioCreativeService','LandingService']:
                provider=constructors[name].call_args.kwargs['structured_provider']
                self.assertEqual(provider.model,'gpt-6-astra')
                self.assertEqual(provider.reasoning_effort,'high')
            self.assertEqual(constructors['TemplateAuthoringService'].call_args.args[1].model,'gpt-6-astra')
            self.assertEqual(constructors['CreativeAnalyticsService'].call_args.kwargs['structured_provider'].model,'brief-local')
