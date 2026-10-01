from io import BytesIO
import hashlib
import json
import unittest
from uuid import uuid4

import httpx
from PIL import Image

from tests.validation_pipeline import test_daddy as fixture
from validation_pipeline.image_errors import InvalidGeneratedImage
from validation_pipeline.openai_images import ResultBridgePhoneScreenImageProvider



def install_provider(test, outcomes):
    test.provider.preset = 'lifestyle'
    keys = []
    images = test.fixture.images
    original = images.generate
    images.supports_operation_tracking = True
    def generate(prompt, **kwargs):
        keys.append(kwargs['operation_key'])
        kwargs['progress']({'stage':'generating','provider_request_id':100+len(keys)})
        result = outcomes.pop(0) if outcomes else 'valid'
        if result == 'invalid':
            raise InvalidGeneratedImage(100+len(keys))
        if result == 'timeout':
            raise TimeoutError('Response unavailable')
        return original(prompt, output_spec=kwargs.get('output_spec'))
    images.generate = generate
    return keys



class DaddyRecoveryTests(unittest.TestCase):
    setUp = fixture.DaddyTests.setUp
    reserve = fixture.DaddyTests.reserve
    generate = fixture.DaddyTests.generate

    def test_corrupt_result_gets_one_fresh_attempt(self):
        keys = install_provider(self, ['invalid','valid'])
        project,identifier,detail = self.generate()
        self.assertEqual(2,len(keys)); self.assertNotEqual(*keys)
        self.assertEqual(3,len(self.provider.calls))
        record = next(iter(detail['generation']['daddy']['asset_operations'].values()))
        self.assertEqual('invalid_image',record['attempts']['0']['failure_code'])
        self.assertEqual(101,record['attempts']['0']['provider_request_id'])
        self.assertEqual('completed',record['attempts']['1']['status'])
        self.assertEqual([],detail['versions'])


    def test_exhaustion_explicit_retry_and_duplicate_uuid(self):
        keys = install_provider(self, ['invalid','invalid','valid'])
        project,identifier = self.reserve()
        with self.assertRaises(InvalidGeneratedImage): self.service.generate(identifier)
        failed = self.service.detail(project,identifier)
        self.assertEqual('scene',failed['generation']['daddy']['failure']['slot'])
        self.assertEqual(2,len(keys))
        # A restart without explicit Retry cannot consume a third attempt.
        with self.assertRaises(InvalidGeneratedImage): self.service.generate(identifier)
        self.assertEqual(2,len(keys))
        request = str(uuid4())
        self.service.retry_generation(project,identifier,request_id=request)
        self.service.retry_generation(project,identifier,request_id=request)
        self.service.generate(identifier)
        done = self.service.detail(project,identifier)
        self.assertEqual(failed['content'],done['content'])
        self.assertEqual(failed['configuration'],done['configuration'])
        self.assertEqual(3,len(keys))
        self.service.retry_generation(project,identifier,request_id=request)
        self.service.generate(identifier)
        self.assertEqual(3,len(keys))


    def test_timeout_reconciles_same_key_and_retains_provider_id(self):
        keys = install_provider(self, ['timeout','valid'])
        project,identifier = self.reserve()
        with self.assertRaises(TimeoutError): self.service.generate(identifier)
        state = self.service.authority.get_creative(identifier)['generation']['daddy']
        record = next(iter(state['asset_operations'].values()))
        self.assertEqual(101,record['attempts']['0']['provider_request_id'])
        self.service.retry_generation(project,identifier,request_id=str(uuid4()))
        self.service.generate(identifier)
        self.assertEqual(keys[0],keys[1])


    def test_bridge_transport_rejects_cached_truncated_png_and_recovers(self):
        self.provider.preset = 'lifestyle'
        out=BytesIO();Image.new('RGB',(1024,1280),'#556677').save(out,format='PNG')
        good=out.getvalue(); bad=good[:-400]
        requests={}; keys=[]
        def handler(request):
            path=request.url.path
            if path.endswith('/capabilities'):
                return httpx.Response(200,json={'image_generation_policies':['ptw.domain-image.v1'],'image_output_specs':['ptw.image-output.v1']})
            if request.method=='POST':
                key=json.loads(request.content)['idempotency_key'];keys.append(key)
                identifier=next((i for i,v in requests.items() if v==key),len(requests)+1)
                requests[identifier]=key
                return httpx.Response(200,json={'request_id':identifier})
            identifier=int(path.split('/')[-2] if path.endswith('/asset') else path.split('/')[-1])
            data=bad if identifier==1 else good
            if path.endswith('/asset'): return httpx.Response(200,content=data)
            digest=hashlib.sha256(data).hexdigest()
            return httpx.Response(200,json={'status':'completed','result':{'image':{'digest':digest,'output_digest':digest,'width':1024,'height':1280,'mime_type':'image/png'}}})
        client=httpx.Client(transport=httpx.MockTransport(handler));self.addCleanup(client.close)
        self.fixture.images=ResultBridgePhoneScreenImageProvider('https://bridge.test/images','test',client=client)
        self.generate()
        self.assertEqual(2,len(set(keys)))

    def test_release_canary_uses_disposable_authority_and_bridge_media(self):
        from types import SimpleNamespace
        from pathlib import Path
        from validation_pipeline.verify_daddy_bridge import verify
        project, brief = self.fixture.approved_brief()
        document = self.service.authority.brief(brief)['document']
        root = Path(__file__).resolve().parents[2]
        settings = SimpleNamespace(studio_composer_skill_path=root/'skills/studio-creative-composer/SKILL.md',
            studio_phone_skill_path=root/'skills/studio-phone-hero-generator/SKILL.md',
            studio_manual_agent_skill_path=root/'skills/studio-manual-agent/SKILL.md')
        original = self.fixture.images.generate
        def generate(prompt, **kwargs):
            value = original(prompt, **kwargs)
            value['source']['transport'] = 'authenticated_result_bridge'
            return value
        self.fixture.images.generate = generate
        self.provider.preset = 'lifestyle'
        scripted = self.provider
        class BridgeContract:
            def call(self, *, response_validator, **request):
                value = scripted.generate(**request)
                return {**value, 'response': response_validator(value['response'])}
        result = verify(settings,BridgeContract(),self.fixture.images,document,lambda *args:None)
        self.assertEqual('daddy_pipeline',result['mode'])
        self.assertEqual('scene',result['assets'][0]['slot'])
