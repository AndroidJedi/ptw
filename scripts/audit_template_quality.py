#!/usr/bin/env python3
"""Export a read-only catalog audit. Never approves, publishes or edits a Project.

Run after build:template-preview, then use audit-template-quality.mjs for browsers.
Optional SQLite input is opened read-only; Project workspaces are copied first.
"""
from argparse import ArgumentParser
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation_pipeline.landing_templates import LANDING_TEMPLATE_REGISTRY
from validation_pipeline.post_templates import POST_TEMPLATE_REGISTRY
from validation_pipeline.post_template_runtime import post_definition
from validation_pipeline.studio_workspace import PostStudioWorkspace
from validation_pipeline.template_components import render, sha
from validation_pipeline.template_previews import builtin_record, geometry, landing_fixture, render_builtin
from validation_pipeline.template_registry import TemplateRegistry


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--template-store', type=Path)
    parser.add_argument('--workspace-root', type=Path)
    args = parser.parse_args()
    root = args.output_dir.resolve(); root.mkdir(parents=True, exist_ok=True)
    posts = root / 'posts'; posts.mkdir(exist_ok=True)
    fixtures = root / 'fixtures'; fixtures.mkdir(exist_ok=True)
    catalog, pages, renders = [], [], []

    def save_post(name, result, identity, sample='neutral'):
        path = posts / f'{name}.png'; path.write_bytes(result['bytes'])
        observations, failures = geometry(result)
        role_by_id = {i: r for r, ids in result.get('resolved', {}).get('semantic_roles', {}).items() for i in ids}
        # Report review targets independently of hard overflow failures.
        small = [{'id': key, 'font_size': node['text_layout']['font_size']} for key, node in result.get('resolved', {}).get('nodes', {}).items()
                 if node.get('text_layout') and role_by_id.get(key) == 'description'
                 and node['text_layout']['font_size'] < 24 * result['width'] / 1080]
        renders.append({'file': str(path.relative_to(root)), 'identity': identity, 'sample': sample,
                        'geometry': observations, 'failures': failures, 'small_secondary_text': small})
        print(name, 'failures:', len(failures), 'small text:', len(small), flush=True)

    for registry in (POST_TEMPLATE_REGISTRY, LANDING_TEMPLATE_REGISTRY):
        for definition in registry.registered_versions():
            record = builtin_record(definition); catalog.append(record)
            name = f"{record['template_id']}-v{record['template_version']}"
            if record['surface'] == 'post':
                save_post(name, render_builtin(record), definition.identity.to_reference())
                continue
            value = landing_fixture(reference={k: v for k, v in definition.identity.to_reference().items() if k != 'surface'})
            modes = ('neutral', 'uk-long', 'marketing-uk-long') if record['template_id'] == 'project_landing' else ('neutral', 'uk-long')
            for mode in modes:
                fixture = deepcopy(value)
                if mode == 'marketing-uk-long':
                    shared = landing_fixture('app_showcase')
                    fixture['configuration']['marketing'] = shared['configuration']['marketing']
                    fixture['content']['marketing'] = shared['content']['marketing']
                    fixture['imageUrls']['walkthrough_visual'] = shared['imageUrls']['walkthrough_visual']
                if mode != 'neutral':
                    c, v = fixture['configuration'], fixture['content']
                    c['presentation'].update(language='uk', heading_scale=1.2, spacing='airy')
                    v['hero'].update(title='Усі важливі справи поруч — оберіть потрібне та додайте деталі у застосунку',
                        supporting_text='Це демонстрація компонування з довшим українським текстом. Перевірте, чи зручно читати пояснення, переглядати інтерфейс і переходити до наступного кроку на різних екранах.',
                        cta_label='Переглянути всі можливості застосунку')
                    v['features'] = [{'title': f'Зрозумілий наступний крок {i + 1}', 'description': 'Довше пояснення можливості має залишатися читабельним, з достатніми відступами й без обрізаного тексту.'} for i in range(3)]
                    for i, screen in enumerate(v.get('app_screens', [])):
                        screen.update(title=['Оберіть потрібну можливість', 'Додайте всі важливі деталі запиту', 'Перевірте перед надсиланням'][i],
                                      description='Короткий опис дії.' if i == 0 else 'Довший підпис до інтерфейсу перевіряє вирівнювання телефонів і читабельність на планшеті та смартфоні.')
                    for item in v['faq']:
                        item.update(question='Як переглянути доступні можливості та перейти до наступного кроку?', answer='Демонстраційний текст відповіді перевіряє перенесення рядків і вертикальні відступи у відкритому блоці запитань.')
                    if 'marketing' in v:
                        v['marketing'].update(store_label='Переглянути можливості застосунку', walkthrough_heading='Від першого кроку до перевірки всіх деталей запиту')
                    if 'app_feature' in v:
                        v['app_feature'].update(title='Ваші щоденні справи', description='Оберіть потрібну дію та додайте деталі.', action_label='Переглянути можливості')
                        v['app_feature']['items'] = [{'label': 'Переглянути доступні можливості', 'value': 'Опис і наступний крок'} for _ in range(3)]
                path = fixtures / f'{name}-{mode}.json'; write_json(path, fixture)
                pages.append({'name': f'{name}-{mode}', 'file': str(path.relative_to(root)), 'template': record['template_id'], 'mode': mode})

    accepted = []
    if args.template_store:
        with sqlite3.connect(args.template_store.resolve().as_uri() + '?mode=ro', uri=True) as db:
            accepted = [json.loads(row[0]) for row in db.execute("SELECT payload FROM template_authoring_records WHERE kind='version' ORDER BY record_key")]
        for record in accepted:
            if record['state_sha256'] != sha({k: v for k, v in record.items() if k != 'state_sha256'}):
                raise RuntimeError('Accepted template integrity check failed')
            catalog.append({k: record[k] for k in ('surface', 'template_id', 'template_version', 'template_sha256', 'name')})
            name = f"{record['template_id']}-v{record['template_version']}"
            write_json(root / f'{name}.json', record)
            if record['surface'] == 'post':
                save_post(name, render(record['document'], surface='post'), catalog[-1])
            else:
                for mobile in (False, True):
                    save_post(name + ('-mobile' if mobile else ''), render(record['document'], surface='landing', mobile=mobile), catalog[-1])

    if args.workspace_root:
        registry = TemplateRegistry('post', (*POST_TEMPLATE_REGISTRY.all(), *(post_definition(r) for r in accepted if r['surface'] == 'post')))
        for source in sorted(args.workspace_root.iterdir()):
            if not (source / 'content.json').is_file():
                continue
            for definition in registry.registered_versions():
                with tempfile.TemporaryDirectory(prefix='ptw-quality-project-') as temporary:
                    copy = Path(temporary) / 'workspace'; shutil.copytree(source, copy)
                    workspace = PostStudioWorkspace(copy, template_registry=lambda: registry)
                    detail = workspace.detail()
                    if definition.identity.to_reference() != detail['template_reference']:
                        detail = workspace.switch_template(base_sha256=detail['state_sha256'], request_id=str(uuid4()),
                            template_reference=definition.identity.to_reference(), configuration=detail['configuration'], content=detail['content'])
                    name = f'{definition.identity.template_id}-v{definition.identity.template_version}-{source.name}'
                    save_post(name, workspace.render_preview(state_sha256=detail['state_sha256']), definition.identity.to_reference(), source.name)
    write_json(root / 'catalog.json', {'templates': catalog, 'pages': pages, 'renders': renders})
    print(f'Exported {len(catalog)} definitions, {len(pages)} Landing fixtures and {len(renders)} native renders to {root}')
    if any(item['failures'] for item in renders):
        raise SystemExit('Native template geometry failed; inspect catalog.json')


if __name__ == '__main__':
    main()
