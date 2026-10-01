"""Real service envelopes and correction budgets for text-only Agent turns."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from tests.validation_pipeline.test_app_showcase import MemoryAuthority, service, showcase_content
from tests.validation_pipeline.test_landing_marketing import complete_marketing
from tests.validation_pipeline import test_post_template_switch as post_fixture
from tests.validation_pipeline import test_studio_creatives as phone_fixture
from validation_pipeline.landing_marketing import DEFAULT_CONFIGURATION
from validation_pipeline.landing_templates import APP_SHOWCASE_V2_DEFINITION
from validation_pipeline.provider import StructuredBridge, StructuredContractError
from validation_pipeline.studio_manual_agent import StudioManualAgentProviderError, _flatten_scalars
from validation_pipeline.local_brief_store import sha256_json


COPY_REQUEST = (
    'enhance this copies:\n\nВаш простір. Ваші можливості.\n\n'
    'Оберіть воду під свої потреби\n\n'
    'Для щоденного пиття, до їжі чи в дорогу — оберіть свої потреби зі списку '
    'й порівняйте воду з каталогу Natal. Перше порівняння трьох марок — '
    'безкоштовне, з поясненням вибору за вашим смаком і бажаною мінералізацією.'
)
REVISED_TITLE = 'Вода для вашого смаку й щоденних потреб'
BRIEF = {
    'schema_version': 1, 'language': 'uk',
    'product': 'Каталог бутильованої води Natal із порівнянням складу та поясненням показників.',
    'target_audience': 'Люди, які обирають воду для щоденного пиття, до їжі або в дорогу.',
    'main_pain': 'Дрібні етикетки й незрозумілі показники ускладнюють порівняння різних марок води.',
    'promise': 'Зіставляйте склад води та обирайте за своїм смаком і бажаною мінералізацією.',
    'key_benefits': ['Порівняння марок поруч', 'Прості пояснення складу', 'Вибір за власними вподобаннями'],
    'cta': 'Порівняти воду', 'trust_strategy': 'Показувати джерела й позначати відсутні дані без медичних обіцянок.',
    'offer': 'Перше порівняння трьох марок безкоштовне з поясненням вибору.',
}

BRIEF.update(schema_version=2, positioning={
    "marketing_approach": "identity_led", "desired_identity": "Я роблю усвідомлений вибір",
    "customer_tension": "Хочу зрозуміти етикетку без складної хімії",
    "category_frame": "Помічник для щоденних покупок",
    "functional_value": "Порівняння складу води та пояснення показників",
})

# Exercise the maximum serialized positioning budget, including Unicode bytes.
for _field in ("desired_identity", "customer_tension", "category_frame", "functional_value"):
    while len(BRIEF["positioning"][_field]) < 200:
        trial = deepcopy(BRIEF["positioning"])
        trial[_field] += "а"
        if len(json.dumps(trial, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()) > 1024:
            break
        BRIEF["positioning"] = trial


BRIEF.update(schema_version=3, brand_identity={
    "belief": "Щоденний вибір вартий розуміння.",
    "identity_signal": "Я обираю уважно, бо знаю, що порівнювати.",
    "values": "Допитливість, власний смак і зрозумілі пояснення.",
    "cultural_tension": "Складна етикетка не має вирішувати за покупця.",
    "category_reframe": "Від каталогу марок до помічника усвідомленого вибору.",
    "emotional_reward": "Задоволення від власного обґрунтованого рішення.",
    "competence_cue": "Спершу визначте смак, потім порівняйте склад.",
    "proof_anchor": "Каталог зіставляє склад і пояснює показники.",
    "voice": "Зрозуміло й без зверхності. Знай, що обираєш.",
    "visual_world": "Покупець порівнює дві пляшки біля полиці; етикетки й уважний жест.",
    "ritual": "Порівняти склад перед наступною покупкою.",
})
# Keep the new extension near its UTF-8 ceiling in populated real-service
# envelopes; the existing tests exercise the corrective response as well.
for _field in BRIEF["brand_identity"]:
    while len(BRIEF["brand_identity"][_field]) < 260:
        trial = deepcopy(BRIEF["brand_identity"])
        trial[_field] += "а"
        if len(json.dumps(trial, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()) > 3072:
            break
        BRIEF["brand_identity"] = trial


class CopyBridge(StructuredBridge):
    def __init__(self, path):
        super().__init__('https://bridge.invalid', 'unused', 'model')
        self.path, self.posts = path, []

    def _request(self, _url, payload, **_kwargs):
        if payload is not None:
            self.posts.append(payload)
            return {'request_id': len(self.posts)}
        return {'status': 'completed', 'result': {'response': {
            'edits': [{'path': self.path, 'value': REVISED_TITLE}],
            'image_actions': [], 'reply': 'x' * 801 if len(self.posts) == 1 else 'Оновлено заголовок.',
        }, 'invocation': {}}}


class StudioAgentCopyTests(unittest.TestCase):
    def assert_correction(self, bridge, result, original, path):
        self.assertEqual(2, len(bridge.posts))
        self.assertEqual([], result['image_actions'])
        self.assertIn(path, result['changed_paths'])
        self.assertEqual([path], result['changed_paths'])
        self.assertEqual(bridge.posts[0]['system_prompt'], bridge.posts[1]['system_prompt'])
        self.assertIn('_ptw_validation_correction', bridge.posts[1]['input_payload'])
        self.assertNotEqual(bridge.posts[0]['context_hash'], bridge.posts[1]['context_hash'])
        current = {}
        _flatten_scalars(bridge.posts[0]['input_payload']['current_editable_values'], '', current)
        self.assertEqual(original, current[path])

    def assert_brief(self, bridge, brief_id, document):
        expected = {'brief_id': brief_id, 'document_sha256': sha256_json(document), 'document': document}
        self.assertEqual(expected, bridge.posts[0]['input_payload']['approved_product_brief'])
        self.assertEqual(expected, bridge.posts[1]['input_payload']['approved_product_brief'])
        paths = bridge.posts[0]['output_schema']['properties']['edits']['items']['properties']['path']['enum']
        current = {}
        _flatten_scalars(bridge.posts[0]['input_payload']['current_editable_values'], '', current)
        self.assertEqual(set(paths), set(current))
        self.assertFalse(any(path.startswith('approved_product_brief') for path in paths))

    def test_ukrainian_showcase_copy_with_full_marketing_context_and_correction(self):
        with TemporaryDirectory() as root:
            authority = MemoryAuthority()
            brief_id = authority.page['source_brief_id']
            authority.brief = lambda requested: {
                'brief_id': requested, 'project_id': authority.page['project_id'],
                'approved': True, 'document': deepcopy(BRIEF if requested == brief_id else {'product': 'Other'}),
                'raw_idea': 'Private audit input, excluded from the provider envelope',
            }
            authority.page.update(status='draft', template_reference={
                k: v for k, v in APP_SHOWCASE_V2_DEFINITION.identity.to_reference().items() if k != 'surface'})
            bridge = CopyBridge('content.hero.title')
            active = service(Path(root), authority, provider=bridge)
            self.addCleanup(active.operations.close)
            pid, lid = authority.page['project_id'], authority.page['landing_id']
            workspace = active._workspace(lid)
            configuration = workspace._configuration()
            configuration['marketing'] = deepcopy(DEFAULT_CONFIGURATION)
            configuration['presentation']['language'] = 'uk'
            content = showcase_content()
            content['hero']['title'] = 'Оберіть воду під свої потреби'
            content['hero']['supporting_text'] = COPY_REQUEST.split('\n\n')[-1]
            content['marketing'] = complete_marketing()
            # A populated page, including the optional feedback fields, must fit
            # without truncating Ukrainian strings or dropping editable fields.
            paragraph = ('Порівнюйте склад води та обирайте варіант за смаком. ' * 3).strip()
            for row in content['features']:
                row['description'] = paragraph
            for row in content['faq']:
                row['answer'] = paragraph
            for row in content['app_screens']:
                row['description'] = paragraph
            for key in ('comparison_rows', 'walkthrough_steps', 'values'):
                for row in content['marketing'][key]:
                    for field in row:
                        if field in ('description', 'text'):
                            row[field] = paragraph
            content['marketing']['feedback_examples'] = [
                {'topic': 'Вибір води', 'statement': paragraph} for _ in range(3)]
            detail = workspace.save_configuration(base_sha256=workspace.state_sha256(), configuration=configuration, content=content)
            authority.page['state_sha256'] = detail['state_sha256']
            before = active.detail(pid, lid)
            content['hero']['title'] = 'Незбережений заголовок у відкритому редакторі'
            result = active.manual_agent_edit(pid, lid, request_id=str(uuid4()), base_sha256=detail['state_sha256'],
                message=COPY_REQUEST, history=[], screenshots=[], configuration=configuration, content=content)
            self.assert_correction(bridge, result, content['hero']['title'], 'content.hero.title')
            self.assert_brief(bridge, brief_id, BRIEF)
            expected = deepcopy(content); expected['hero']['title'] = REVISED_TITLE
            self.assertEqual(expected, result['content'])
            self.assertEqual(configuration, result['configuration'])
            self.assertEqual(before, active.detail(pid, lid))
            self.assertGreater(len(json.dumps(bridge.posts[0]['input_payload'], ensure_ascii=False).encode()), 14000)
            self.check_failures(active, lambda: active.manual_agent_edit(pid, lid, request_id=str(uuid4()),
                base_sha256=detail['state_sha256'], message=COPY_REQUEST, history=[], screenshots=[],
                configuration=configuration, content=content))
            self.assertEqual(before, active.detail(pid, lid))

    def test_phone_metrics_copy_and_provider_failures_preserve_draft(self):
        fixture = phone_fixture.StudioCreativeServiceTests(); fixture.setUp(); self.addCleanup(fixture.tearDown)
        pid, _, detail = fixture.generate_creative()
        fixture.add_approved_brief(pid, 'Later Brief')
        self.check_post(fixture.service, pid, detail, 'content.hero_title', detail['content']['hero_title'])

    def test_authored_post_copy_and_provider_failures_preserve_draft(self):
        fixture = post_fixture.PostTemplateSwitchTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        detail = fixture.switch(fixture.request())
        fixture.fixture.add_approved_brief(fixture.project, 'Later Brief')
        self.check_post(fixture.service, fixture.project, detail, 'content.template_text.title', detail['content']['template_text']['title'])

    def check_post(self, active, pid, detail, path, original):
        bridge = CopyBridge(path); active.structured_provider = bridge
        cid = detail['creative_id']
        request = dict(request_id=str(uuid4()), base_sha256=detail['state_sha256'], message=COPY_REQUEST,
            history=[], screenshots=[], configuration=detail['configuration'], content=detail['content'])
        result = active.manual_agent_edit(pid, cid, **request)
        self.assert_correction(bridge, result, original, path)
        self.assert_brief(bridge, detail['source_brief_id'], active.authority.brief(detail['source_brief_id'])['document'])
        self.assertEqual(detail, active.detail(pid, cid))
        self.check_failures(active, lambda: active.manual_agent_edit(pid, cid, **request))
        self.assertEqual(detail, active.detail(pid, cid))

    def check_failures(self, active, invoke):
        class Failed:
            def __init__(self, error): self.error = error
            def call(self, **_kwargs): raise self.error
        for error, contract_failed in ((ValueError('invalid provider copy'), False),
                                       (StructuredContractError('oversized server envelope'), True)):
            active.structured_provider = Failed(error)
            with self.assertRaises(StudioManualAgentProviderError) as caught:
                invoke()
            self.assertEqual(contract_failed, caught.exception.contract_failed)
            self.assertIs(error, caught.exception.__cause__)
