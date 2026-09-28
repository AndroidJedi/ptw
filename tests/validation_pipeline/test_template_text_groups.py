import unittest
from copy import deepcopy

from validation_pipeline.template_components import apply_edits, new_component, normalize_document, render
from validation_pipeline.post_template_runtime import post_definition
from validation_pipeline.studio import StudioRenderer


class TemplateTextGroupTests(unittest.TestCase):
    def setUp(self):
        self.ids = ['benefit_primary', 'benefit_secondary', 'benefit_tertiary']
        self.doc = normalize_document({
            'name': 'Flowing benefits', 'description': 'Reusable shared type and hanging bullets.',
            'canvas': {'width': 1080, 'height': 1080, 'mobile_height': 1080}, 'background': '#14243A',
            'components': [{**new_component(item, 'text', 'description', [43, 390 + index * 55, 310, 40], 'Body text'),
                'font_size': 28, 'font_weight': 400, 'color': '#FFFFFF'} for index, item in enumerate(self.ids)],
            'text_groups': [{'id': 'benefits', 'items': self.ids, 'gap': 18, 'bullet_indent': 24}],
        })

    def render(self, copy, mobile=False):
        return render(self.doc, surface='post', mobile=mobile, content=dict(zip(self.ids, copy)))

    def text_nodes(self, result):
        return [dict(n, id=key) for key, n in result['resolved']['nodes'].items() if key in self.ids]

    def test_equal_type_wrapping_hanging_bullets_and_constant_gaps(self):
        copy = ['• 100+ зразків води проаналізовано.', '25+ зразків з інших країн.', 'Методологія ВООЗ.']
        for mobile in (False, True):
            result = self.render(copy, mobile)
            nodes = self.text_nodes(result)
            self.assertEqual(3, len(nodes))
            self.assertEqual(1, len({n['text_layout']['font_size'] for n in nodes}))
            self.assertTrue(all(not n['text_layout']['overflow'] and not n['text_layout']['truncated'] for n in nodes))
            self.assertGreater(nodes[0]['text_layout']['line_count'], 1)
            bullets = {key: n for key, n in result['resolved']['nodes'].items() if key.endswith('_bullet')}
            self.assertEqual(3, len(bullets))
            for node in nodes:
                self.assertGreater(node['box']['x'], bullets[node['id'] + '_bullet']['box']['x'])
            for previous, current in zip(nodes, nodes[1:]):
                gap = (current['box']['y'] - previous['box']['y'] - previous['box']['height']) * 1080
                self.assertAlmostEqual(18 * (.6 if mobile else 1), gap, places=4)

    def test_longer_item_moves_next_item_and_blank_items_consume_no_space(self):
        short = self.text_nodes(self.render(['First', 'Second', 'Third']))
        long = self.text_nodes(self.render(['A longer benefit that wraps onto another line and grows naturally.', 'Second', 'Third']))
        self.assertGreater(long[1]['box']['y'], short[1]['box']['y'])
        self.assertEqual(short[0]['text_layout']['font_size'], long[0]['text_layout']['font_size'])
        empty = self.render(['First', '', 'Third'])
        self.assertEqual([self.ids[0], self.ids[2]], [n['id'] for n in self.text_nodes(empty)])
        self.assertNotIn(self.ids[1] + '_bullet', set(empty['resolved']['nodes']))
        self.assertEqual(short[1]['box']['y'], self.text_nodes(empty)[1]['box']['y'])

    def test_grouped_owner_font_override_reflows_all_items_without_changing_copy(self):
        definition = post_definition({'surface': 'post', 'template_id': 'flow_benefits', 'template_version': 1,
                                      'template_sha256': 'a' * 64, 'document': self.doc})
        configuration = definition.default_configuration()
        configuration['template_typography'] = {self.ids[1]: {'font_family': 'Inter', 'font_size': 36}}
        configuration = definition.normalize_configuration(configuration)
        self.assertEqual(set(self.ids), set(configuration['template_typography']))
        content = definition.default_content()
        content['template_text'] = dict(zip(self.ids, ['• A long benefit with natural wrapping', '• Second', '• Third']))
        before = deepcopy(content)
        result = StudioRenderer().render_preview(definition.build_template(configuration, content), semantic_data={}, assets={})
        self.assertEqual({36}, {n['text_layout']['font_size'] for n in self.text_nodes(result)})
        self.assertEqual(before, content)
        configuration['template_typography'][self.ids[0]]['font_size'] = 40
        with self.assertRaisesRegex(ValueError, 'same font and size'):
            definition.normalize_configuration(configuration)

    def test_bounded_group_edits_and_legacy_documents(self):
        legacy = deepcopy(self.doc)
        groups = legacy.pop('text_groups')
        self.assertNotIn('text_groups', normalize_document(legacy))
        self.assertEqual(self.doc, apply_edits({'post': legacy}, [{'surface': 'post', 'path': 'text_groups', 'value': groups}])['post'])
        for invalid in (groups + groups, [{**groups[0], 'items': ['missing', self.ids[0]]}], [{**groups[0], 'gap': -1}]):
            with self.assertRaises(ValueError):
                normalize_document({**legacy, 'text_groups': invalid})


if __name__ == '__main__':
    unittest.main()
