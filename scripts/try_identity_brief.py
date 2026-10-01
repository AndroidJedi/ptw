#!/usr/bin/env python3
"""Generate one real private Brief through the local production-equivalent service.

Example: .venv/bin/python scripts/try_identity_brief.py --idea 'car sharing'
No approval, publication or automatic learning. Reuse the saved request on rerun;
use another --output-dir for a fresh experiment after instruction changes.
"""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.local_briefs import LocalBriefService
from validation_pipeline.local_codex import LocalCodexStructuredProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--idea', default='car sharing')
    parser.add_argument('--language', choices=['uk', 'en'], default='uk')
    parser.add_argument('--approach', choices=['identity_led', 'benefit_led'], default='identity_led')
    parser.add_argument('--model', default='gpt-6-astra')
    parser.add_argument('--output-dir', type=Path, default=ROOT / '.local/car-sharing-identity')
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if not destination.is_relative_to(ROOT / '.local'):
        parser.error('Output must be inside this checkout’s private .local directory')
    destination.mkdir(parents=True, exist_ok=True)
    inputs = {'idea': args.idea, 'language': args.language, 'approach': args.approach, 'model': args.model}
    path = destination / 'request.json'
    service = LocalBriefService(store=LocalBriefStore(destination / 'store'), repository_root=ROOT,
        provider=LocalCodexStructuredProvider(model=args.model, reasoning_effort='xhigh'))
    if path.exists():
        request = json.loads(path.read_text())
        if request['inputs'] != inputs:
            parser.error('Saved inputs differ; select a new output directory')
    else:
        request = {'inputs': inputs, 'project_request_id': str(uuid4()), 'brief_request_id': str(uuid4())}
        path.write_text(json.dumps(request, ensure_ascii=False, indent=2))
    project, _ = service.create_project(request_id=request['project_request_id'],
        name=f"Private {args.approach} trial", requested_by='local-owner-trial')
    _, brief, _ = service.create_brief(project_id=project['project_id'], request_id=request['brief_request_id'],
        raw_idea=args.idea, required_language=args.language, marketing_approach=args.approach,
        requested_by='local-owner-trial')
    if brief['status'] == 'queued':
        brief = service.generate_brief(brief['brief_id'])
    if brief['status'] != 'completed':
        raise RuntimeError(f"Saved Brief is {brief['status']}; inspect local receipts before retrying")
    (destination / 'brief.json').write_text(json.dumps(brief, ensure_ascii=False, indent=2))
    doc = brief['document']
    report = [f"# {doc['product']}", '', doc['promise'], '', f"Audience: {doc['target_audience']}",
              f"Tension: {doc['main_pain']}", f"Offer: {doc['offer']}", f"CTA: {doc['cta']}", '',
              *[f"- {v}" for v in doc['key_benefits']], '',
              *[f"{k}: {v}" for k, v in doc['positioning'].items()], '',
              '## Brand identity', '', *[f"**{k}**: {v}" for k, v in doc.get('brand_identity', {}).items() if v], '',
              f"Brief: {brief['brief_id']}", f"Policy: {brief['generation_settings']['policy_sha256']}",
              'Private unapproved hypothesis. Editorial review is not conversion evidence.']
    (destination / 'review.md').write_text('\n'.join(report) + '\n')
    print(json.dumps({'brief_id': brief['brief_id'], 'promise': doc['promise'], 'offer': doc['offer'],
                      'review': str(destination / 'review.md')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
