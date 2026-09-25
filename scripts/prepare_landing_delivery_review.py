#!/usr/bin/env python3
"""Build local before/after delivery evidence from an immutable public snapshot."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from urllib.parse import urljoin

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation_pipeline.landing_delivery import prepare


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-url',required=True)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args(); root=args.output_dir; root.mkdir(parents=True,exist_ok=True)
    def fetch(url):
        response=httpx.get(url,timeout=45,follow_redirects=True); response.raise_for_status(); return response.content
    snapshot_path=root/'public-snapshot.json'
    if not snapshot_path.exists(): snapshot_path.write_bytes(fetch(args.snapshot_url))
    snapshot=json.loads(snapshot_path.read_text())
    fixture={'configuration':snapshot['configuration'],'content':snapshot['content'],'imageUrls':{},'imageVariants':{}}
    report={}; total=0; maximum=0
    for slot,url in snapshot['assets'].items():
        path=root/f'{slot}.png'
        if not path.exists(): path.write_bytes(fetch(urljoin(args.snapshot_url,url)))
        data=path.read_bytes(); variants,files=prepare(data,slot)
        for name,encoded in files.items():
            output=root/name; output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(encoded)
        fixture['imageUrls'][slot]='/'+path.name
        original=__import__('hashlib').sha256(data).hexdigest()
        fixture['imageVariants'][slot]=[{**v,'url':f'/delivery/webp-v1/{original}/{v["sha256"]}.webp'} for v in variants]
        report[slot]={'png_bytes':len(data),'variants':variants};total+=len(data);maximum+=variants[-1]['byte_count']
    shutil.copytree(ROOT/'.local/template-preview/assets',root/'assets',dirs_exist_ok=True)
    html=(ROOT/'.local/template-preview/index.html').read_text()
    for name,variants in [('before',{}),('after',fixture['imageVariants'])]:
        payload=json.dumps({**fixture,'imageVariants':variants},ensure_ascii=False).replace('</','<\\/')
        (root/f'{name}.html').write_text(html.replace('<head>','<head><script>window.templateFixture='+payload+'</script>'))
    (root/'fixture.json').write_text(json.dumps(fixture,ensure_ascii=False))
    report.update(original_bytes=total,maximum_display_bytes=maximum,reduction=1-maximum/total)
    (root/'delivery-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({key:report[key] for key in ('original_bytes','maximum_display_bytes','reduction')}))


if __name__=='__main__': main()
