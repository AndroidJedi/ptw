#!/usr/bin/env python3
"""Explicit real-provider canary from a public snapshot; writes local audit fixtures only."""
import argparse
import base64
from copy import deepcopy
import json
from pathlib import Path
import sys
from urllib.parse import urljoin
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation_pipeline.image_generation_policy import build_image_context, compile_image_prompt, instruction_context
from validation_pipeline.landing_showcase import SCREEN_SLOTS, screen_design, screen_direction
from validation_pipeline.landing_workspace import LandingWorkspace
from validation_pipeline.landing_marketing import GRADIENTS, initial_logo_color
from validation_pipeline.openai_images import LocalCodexPhoneScreenImageProvider


def fetch(url):
    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    return response.content


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-url', required=True)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--photo-focus-y', type=int, choices=range(101), metavar='0..100')
    args=parser.parse_args()
    root=args.output_dir; root.mkdir(parents=True, exist_ok=True)
    source_path=root/'public-snapshot.json'
    if not source_path.exists(): source_path.write_bytes(fetch(args.snapshot_url))
    snapshot=json.loads(source_path.read_text())
    before={'configuration':snapshot['configuration'],'content':snapshot['content'],'imageUrls':{}}
    for slot,url in snapshot['assets'].items():
        path=root/f'before-{slot}.png'
        if not path.exists(): path.write_bytes(fetch(urljoin(args.snapshot_url,url)))
        before['imageUrls'][slot]='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
    (root/'before.json').write_text(json.dumps(before,ensure_ascii=False))
    workspace=LandingWorkspace(root/'workspace',image_provider=LocalCodexPhoneScreenImageProvider(timeout_seconds=600))
    workspace.template_reference=snapshot['template_reference']
    if not (workspace.root/'content.json').exists():
        config=deepcopy(snapshot['configuration'])
        if 'marketing' in config:
            gradient=next(g for g in GRADIENTS if g['id']==config['marketing']['gradient_id'])
            config['marketing']['logo_color']=initial_logo_color(config['marketing']['logo_color'],gradient)
        workspace.save_configuration(base_sha256=workspace.state_sha256(),configuration=config,content=snapshot['content'])
    config,content=workspace._configuration(),workspace._content()
    if args.photo_focus_y is not None:
        config['presentation']['visual_break_focus']['y']=args.photo_focus_y
        workspace.save_configuration(base_sha256=workspace.state_sha256(),configuration=config,content=content)
    # This is a public-copy fixture, not a fabricated approved Brief or a production Project.
    brief={'document':{'product':content['hero']['title'],'promise':content['hero']['supporting_text'],
                       'key_benefits':content['features'],'language':config['presentation']['language']}}
    for slot in (*SCREEN_SLOTS,'walkthrough_visual'):
        if workspace._selected(slot): continue
        mode='app_screen' if slot in SCREEN_SLOTS else 'app_mockup'
        direction=screen_direction(content,slot)
        context=build_image_context(direction=direction,instruction=instruction_context(direction,origin='generated'),
            brief=brief,settings={'palette':config['theme'],'background':'isolated_key_element'},
            destination={'surface':'landing','mode':mode,'slot':slot,'template_id':'app_showcase',
                         'screen_design':screen_design(config),'screen_series':content['app_screens'],
                         'screen_language':config['presentation']['language'],
                         'steps':content.get('marketing',{}).get('walkthrough_steps',[])},
            operation='generate_new',base_sha256=workspace.state_sha256())
        prompt=compile_image_prompt(context)
        (root/f'{slot}.prompt.txt').write_text(prompt)
        print(f'Generating {slot} with Astra',flush=True)
        workspace.generate_visual(base_sha256=workspace.state_sha256(),slot=slot,visual_direction=direction,
                                  prompt=prompt,image_context=context)
        item=workspace._history(slot)[-1]
        print(f"Saved {slot}: {item['width']}x{item['height']} {item['sha256']}",flush=True)
    fixture={**before,'configuration':config,'content':content,'imageUrls':dict(before['imageUrls'])}
    for slot in (*SCREEN_SLOTS,'walkthrough_visual'):
        data=workspace.visual_image(slot,workspace._selected(slot))['bytes']
        fixture['imageUrls'][slot]='data:image/png;base64,'+base64.b64encode(data).decode()
        (root/f'{slot}.png').write_bytes(data)
    (root/'after.json').write_text(json.dumps(fixture,ensure_ascii=False))
    print(f'Local real-provider fixture: {root / "after.json"}',flush=True)


if __name__=='__main__': main()
