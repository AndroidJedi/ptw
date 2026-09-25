from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Event, BoundedSemaphore
import time
import unittest
from unittest.mock import Mock
from uuid import uuid4

from PIL import Image
from tests.validation_pipeline.test_app_showcase import MemoryAuthority, service, showcase_content
from tests.validation_pipeline.test_landing_workspace import FakeImages, complete_content
from validation_pipeline.landing_templates import PROJECT_LANDING_DEFINITION, APP_SHOWCASE_DEFINITION, APP_SHOWCASE_V2_DEFINITION
from validation_pipeline.landing_workspace import LandingWorkspace
from validation_pipeline.landing_delivery import prepare, selected_variants
from validation_pipeline.landing_operation_store import OperationStore
from validation_pipeline.landing_publication import public_snapshot


class LandingPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def build(self, images=None, definition=APP_SHOWCASE_DEFINITION):
        authority = MemoryAuthority()
        authority.page['template_reference'] = {k: v for k, v in definition.identity.to_reference().items() if k != 'surface'}
        active = service(self.root, authority, images or FakeImages())
        pid, lid = authority.page['project_id'], authority.page['landing_id']
        workspace = active._workspace(lid)
        content = showcase_content() if definition.identity.template_id == 'app_showcase' else complete_content()
        detail = workspace.save_configuration(base_sha256=workspace.state_sha256(), configuration=workspace._configuration(), content=content)
        authority.update_page(lid, status='draft', state_sha256=detail['state_sha256'])
        self.addCleanup(active.operations.close)
        return active, pid, lid

    def request(self, active, pid, lid, slots):
        detail = active.detail(pid, lid)
        from validation_pipeline.landing_showcase import screen_direction
        active.manual_agent_edit = Mock(return_value={
            'configuration': detail['configuration'], 'content': detail['content'], 'reply': 'Adjusted the requested images.',
            'changed_paths': [], 'base_sha256': detail['state_sha256'], 'request_id': str(uuid4()),
            'owner_instruction': 'Update these images.', 'image_actions': [
                {'slot': slot, 'visual_direction': screen_direction(detail['content'], slot), 'enhance_current': False, 'reference_index': 0} for slot in slots]})
        return {'kind': 'agent', 'request': {'request_id': str(uuid4()), 'base_sha256': detail['state_sha256'], 'configuration': detail['configuration'], 'content': detail['content'], 'message': 'Update these images.', 'history': [], 'screenshots': []}}

    def finished(self, active, pid, lid, identifier):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            value = active.operations.get(pid, lid, identifier)
            if value['status'] not in {'queued', 'running'}:
                return value
            time.sleep(.01)
        self.fail('Operation did not finish')

    def test_parallel_slots_commit_independently_without_holding_page_reads(self):
        barrier = Barrier(2)
        gate = Event()
        class Images(FakeImages):
            def generate(self, prompt, **kwargs):
                barrier.wait(timeout=5); gate.wait(timeout=5)
                return super().generate(prompt, **kwargs)
        active, pid, lid = self.build(Images()); active.operations.concurrency = 2
        active.operations.image_capacity = BoundedSemaphore(2)
        request = self.request(active, pid, lid, ['app_screen_1', 'app_screen_2'])
        value = active.operations.start(pid, lid, request)
        self.assertEqual(value['operation_id'], active.operations.start(pid, lid, request)['operation_id'])
        detail = active.detail(pid, lid)
        self.assertEqual(detail['status'], 'draft')
        with self.assertRaisesRegex(RuntimeError, 'operation is running'):
            active.mutate(pid, lid, 'save_configuration', base_sha256=detail['state_sha256'], configuration=detail['configuration'], content=detail['content'])
        gate.set()
        final = self.finished(active, pid, lid, value['operation_id'])
        self.assertEqual('completed', final['status'], final)
        self.assertEqual(['completed', 'completed'], [job['status'] for job in final['jobs']])
        self.assertEqual(2, len(active._workspace(lid).image_provider.references))
        active.manual_agent_edit.assert_called_once()
        self.assertTrue(all(entry['history'][0]['variants'] for entry in active.detail(pid, lid)['assets'][:2]))

    def test_initial_generation_keeps_database_workspace_reads_available(self):
        from concurrent.futures import ThreadPoolExecutor
        from validation_pipeline.landing_pages import DatabaseLandingWorkspace
        entered, release = Event(), Event()
        class Images(FakeImages):
            def generate(self, prompt, **kwargs):
                entered.set(); release.wait(timeout=5)
                return super().generate(prompt, **kwargs)
        active,pid,lid=self.build(Images())
        original=active._workspace(lid)
        authority=Mock();authority.get_page.return_value=active.authority.get_page(lid);authority.load_workspace_files.return_value=None
        workspace=DatabaseLandingWorkspace(original,authority,lid)
        detail=workspace.detail()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(workspace.generate_visual,base_sha256=detail['state_sha256'],slot='app_screen_1',visual_direction='A clear app screen',prompt='A clear app screen')
            try:
                self.assertTrue(entered.wait(timeout=2))
                started=time.monotonic();workspace.detail()
                self.assertLess(time.monotonic()-started,.5)
            finally:release.set()
            self.assertTrue(future.result()['assets'][0]['available'])

    def test_partial_failure_retry_retains_completed_image_and_interpretation(self):
        class Images(FakeImages):
            calls = 0
            def generate(self, prompt, **kwargs):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError('provider failed')
                return super().generate(prompt, **kwargs)
        images = Images(); active, pid, lid = self.build(images)
        value = active.operations.start(pid, lid, self.request(active, pid, lid, ['app_screen_1', 'app_screen_2']))
        failed = self.finished(active, pid, lid, value['operation_id'])
        self.assertEqual('failed', failed['status'], failed)
        first = active.detail(pid, lid)['assets'][0]['sha256']
        active.operations.retry(pid, lid, value['operation_id'], {})
        completed = self.finished(active, pid, lid, value['operation_id'])
        self.assertEqual('completed', completed['status'], completed)
        self.assertEqual(first, active.detail(pid, lid)['assets'][0]['sha256'])
        self.assertEqual(images.calls, 3)
        active.manual_agent_edit.assert_called_once()
        restarted = OperationStore(active.root / 'operations.sqlite3')
        self.assertEqual(restarted.get(value['operation_id'])['status'], 'completed')

    def test_request_identity_and_project_isolation(self):
        active, pid, lid = self.build()
        request = self.request(active, pid, lid, [])
        value = active.operations.start(pid, lid, request)
        self.finished(active, pid, lid, value['operation_id'])
        changed = deepcopy(request); changed['request']['message'] = 'Different instruction'
        with self.assertRaises(RuntimeError): active.operations.start(pid, lid, changed)
        with self.assertRaises(KeyError): active.operations.get(str(uuid4()), lid, value['operation_id'])
        self.assertEqual([], active._workspace(lid).image_provider.references)
        active.detail = Mock(side_effect=AssertionError('Status must not read image files'))
        self.assertEqual('completed',active.operations.get(pid,lid,value['operation_id'])['status'])

    def test_latest_request_orders_operations_within_the_same_second(self):
        store=OperationStore(self.root/'ordered.sqlite3')
        landing,project=str(uuid4()),str(uuid4())
        for microsecond in ('100000','900000'):
            identifier=str(uuid4())
            store.save({'operation_id':identifier,'landing_id':landing,'project_id':project,'request_id':str(uuid4()),
                'status':'completed','started_at':f'2026-09-25T08:00:00.{microsecond}+00:00'})
        self.assertEqual(identifier,store.list(landing,limit=1)[0]['operation_id'])

    def test_restart_reconciles_committed_image_when_its_progress_event_was_lost(self):
        class Images(FakeImages):
            calls = 0
            def generate(self, prompt, **kwargs):
                self.calls += 1
                if self.calls == 2: raise RuntimeError('provider failed')
                return super().generate(prompt, **kwargs)
        images = Images(); active, pid, lid = self.build(images)
        admitted = active.operations.start(pid, lid, self.request(active, pid, lid, ['app_screen_1', 'app_screen_2']))
        self.finished(active, pid, lid, admitted['operation_id'])
        while admitted['operation_id'] in active.operations.running: time.sleep(.01)
        value = active.operations.store.get(admitted['operation_id'])
        original = value['jobs'][0]['sha256']
        value['jobs'][0].update(status='generating'); value['jobs'][0].pop('sha256')
        value.update(status='running', error=None, expected_sha256=value['configured_sha256'])
        active.operations.store.save(value, value['revision'])
        active.operations.recover_interrupted()
        interrupted = active.operations.get(pid,lid,admitted['operation_id'])
        self.assertEqual('interrupted', interrupted['status'])
        self.assertEqual(2, images.calls)
        active.operations.retry(pid,lid,admitted['operation_id'],{})
        result = self.finished(active,pid,lid,admitted['operation_id'])
        self.assertEqual('completed', result['status'],result)
        self.assertEqual(original, result['jobs'][0]['sha256'])
        self.assertEqual(3, images.calls)
        active.manual_agent_edit.assert_called_once()

    def test_uncertain_provider_response_reuses_frozen_request_key(self):
        class Images(FakeImages):
            supports_operation_tracking = True
            def __init__(self): super().__init__(); self.results = {}; self.keys = []
            def generate(self, prompt, *, operation_key=None, progress=None, **kwargs):
                self.keys.append(operation_key)
                if operation_key not in self.results:
                    self.results[operation_key] = super().generate(prompt, **kwargs)
                    raise TimeoutError('response timed out after provider completion')
                return self.results[operation_key]
        images = Images(); active,pid,lid = self.build(images)
        value = active.operations.start(pid,lid,self.request(active,pid,lid,['app_screen_1']))
        self.assertEqual('failed',self.finished(active,pid,lid,value['operation_id'])['status'])
        active.operations.retry(pid,lid,value['operation_id'],{})
        self.assertEqual('completed',self.finished(active,pid,lid,value['operation_id'])['status'])
        self.assertEqual(images.keys[0],images.keys[1])
        self.assertEqual(1,len(images.references))

    def test_retry_reconciles_a_provider_worker_restart_before_resubmission(self):
        class Images(FakeImages):
            supports_operation_tracking = True
            def __init__(self): super().__init__(); self.keys = []
            def operation_status(self, identifier):
                self.last_checked = identifier
                return 'failed'
            def generate(self, prompt, *, operation_key=None, progress=None, **kwargs):
                self.keys.append(operation_key)
                if len(self.keys)==1:
                    progress({'stage':'generating','provider_request_id':7})
                    raise TimeoutError('worker stopped before result persistence')
                return super().generate(prompt, **kwargs)
        images=Images();active,pid,lid=self.build(images)
        value=active.operations.start(pid,lid,self.request(active,pid,lid,['app_screen_1']))
        self.assertEqual('failed',self.finished(active,pid,lid,value['operation_id'])['status'])
        active.operations.retry(pid,lid,value['operation_id'],{})
        self.assertEqual('completed',self.finished(active,pid,lid,value['operation_id'])['status'])
        self.assertEqual(images.last_checked,7)
        self.assertNotEqual(images.keys[0],images.keys[1])

    def test_all_template_image_slots_prepare_variants_without_rewriting_originals(self):
        for definition in (PROJECT_LANDING_DEFINITION, APP_SHOWCASE_DEFINITION, APP_SHOWCASE_V2_DEFINITION):
            with self.subTest(template=definition.identity):
                workspace = LandingWorkspace(self.root / str(definition.identity.template_version) / definition.identity.template_id, image_provider=FakeImages())
                workspace.template_reference = {k:v for k,v in definition.identity.to_reference().items() if k != 'surface'}
                for slot in workspace.visual_slots:
                    detail = workspace.generate_visual(base_sha256=workspace.state_sha256(), slot=slot, visual_direction='A clear image', prompt='A clear image')
                    entry = next(a for a in detail['assets'] if a['slot'] == slot)['history'][0]
                    raw = workspace.visual_image(slot, entry['sha256'])['bytes']
                    self.assertEqual(sha256(raw).hexdigest(), entry['sha256'])
                    for variant in entry['variants']:
                        data = workspace.display_image(slot, entry['sha256'], variant['sha256'])['bytes']
                        self.assertEqual(Image.open(BytesIO(data)).format, 'WEBP')
                        self.assertLessEqual(variant['width'], entry['width'])
                before = {str(p): p.read_bytes() for p in workspace.root.rglob('*') if p.is_file()}
                workspace.detail()
                self.assertEqual(before, {str(p): p.read_bytes() for p in workspace.root.rglob('*') if p.is_file()})

    def test_display_alpha_and_original_dimensions(self):
        image = Image.new('RGBA', (720, 1200), (20, 40, 60, 0))
        image.paste((255, 255, 255, 255), (100, 100, 620, 1100))
        encoded = BytesIO(); image.save(encoded, 'PNG')
        variants, files = prepare(encoded.getvalue(), 'app_screen_1')
        same = next(v for v in variants if v['width'] == 720)
        data = next(value for path,value in files.items() if same['sha256'] in path)
        display = Image.open(BytesIO(data))
        self.assertEqual(display.getchannel('A').tobytes(), image.getchannel('A').tobytes())
        self.assertEqual(display.getpixel((360, 600)), (255, 255, 255, 255))

    def test_palette_transparency_is_preserved_in_display_copy(self):
        source = Image.new('P', (64,64), 0)
        source.putpalette([0,0,0,255,255,255]+[0]*762)
        source.paste(1,(10,10,54,54))
        encoded=BytesIO();source.save(encoded,'PNG',transparency=0)
        _, files=prepare(encoded.getvalue(),'hero_visual')
        display=Image.open(BytesIO(next(iter(files.values())))).convert('RGBA')
        self.assertEqual(display.getpixel((0,0))[3],0)
        self.assertEqual(display.getpixel((32,32)),(255,255,255,255))

    def test_reading_legacy_asset_never_adds_variants(self):
        active, pid, lid = self.build()
        workspace = active._workspace(lid)
        detail = workspace.generate_visual(base_sha256=workspace.state_sha256(), slot='app_screen_1', visual_direction='A clear screen', prompt='A clear screen')
        history = workspace._history('app_screen_1'); history[0].pop('variants')
        workspace._atomic_json(workspace.assets / 'app_screen_1.history.json', history)
        digest = workspace.state_sha256()
        self.assertEqual({}, selected_variants(workspace.detail()))
        self.assertEqual(digest, workspace.state_sha256())


if __name__ == '__main__': unittest.main()
