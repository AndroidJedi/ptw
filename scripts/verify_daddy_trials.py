#!/usr/bin/env python3
"""Six real, resumable Daddy trials in a disposable local authority.

Fixture Brief approvals enable the generation contract only. No owner Project,
Post approval, publishing, external application, or production DB is touched.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation_pipeline.local_brief_store import LocalBriefStore
from validation_pipeline.local_briefs import LocalBriefService
from validation_pipeline.local_codex import LocalCodexStructuredProvider
from validation_pipeline.openai_images import LocalCodexPhoneScreenImageProvider
from validation_pipeline.studio_creatives import LocalStudioAuthority, StudioCreativeService
from validation_pipeline.studio_workspace import PostStudioWorkspace
from validation_pipeline.visual_models import visual_agent_model

CASES = [
    ('app-benefit','en','benefit_led','phone_feature','An app for independent tutors to show available sessions and let students request a booking. No payments or automatic scheduling claims. Free early access.'),
    ('app-identity','uk','identity_led','playful_demo','A landscape matching game for children aged three to six, with parents choosing short sessions. Match everyday objects by shape or purpose. No developmental outcome promises, no subscription offer supplied.'),
    ('service-benefit','uk','benefit_led','lifestyle','A local bicycle workshop offering booked inspections and repairs. Customers describe a bicycle issue and request a suitable visit. No fixed price, turnaround or discount supplied.'),
    ('service-identity','en','identity_led','illustrated_metaphor','A service matching neighborhood residents with a gardening mentor to plan a balcony garden. A real conversation and a plant-care plan for their space, not guaranteed harvests. No price supplied.'),
    ('product-benefit','en','benefit_led','bold_poster','A reusable stainless steel lunch box with a removable divider. For adults packing lunch from home. No leakproof, dishwasher, recycled-content or environmental-impact claims. No price or offer supplied.'),
    ('product-identity','uk','identity_led','editorial_collage','An undated paper notebook with blank and lined pages for sketching plans and keeping everyday notes. For people who like thinking on paper. No productivity guarantees, sustainability claims, price or discount supplied.'),
]

def run_case(destination, case):
    name, language, approach, preset, idea = case
    folder = destination/name; folder.mkdir(parents=True,exist_ok=True)
    store=LocalBriefStore(folder/'authority')
    provider=LocalCodexStructuredProvider(model=visual_agent_model(),reasoning_effort='xhigh')
    briefs=LocalBriefService(store=store,provider=provider,repository_root=ROOT)
    images=LocalCodexPhoneScreenImageProvider(model=visual_agent_model())
    service=StudioCreativeService(root=folder/'studio',authority=LocalStudioAuthority(store),
        workspace_factory=lambda path:PostStudioWorkspace(path,image_provider=images),structured_provider=provider,
        composer_skill_path=ROOT/'skills/studio-creative-composer/SKILL.md',phone_skill_path=ROOT/'skills/studio-phone-hero-generator/SKILL.md',manual_agent_skill_path=ROOT/'skills/studio-manual-agent/SKILL.md')
    receipt=folder/'trial.json'
    saved=json.loads(receipt.read_text()) if receipt.exists() else {}
    try:
        if not saved:
            project,_=briefs.create_project(request_id=str(uuid4()),name=f'Daddy private trial: {name}',requested_by='disposable-test')
            _,brief,_=briefs.create_brief(project_id=project['project_id'],request_id=str(uuid4()),raw_idea=idea,required_language=language,requested_by='disposable-test',marketing_approach=approach)
            saved={'project_id':project['project_id'],'brief_id':brief['brief_id'],'case':name,'fixture_only':True}
            receipt.write_text(json.dumps(saved,indent=2))
        brief=briefs.get_brief(saved['brief_id'])
        if brief['status']=='queued':
            brief=briefs.generate_brief(brief['brief_id'])
        if brief['status']!='completed':
            raise RuntimeError('Brief generation did not complete; inspect private receipts')
        if not brief.get('approved'):
            briefs.approve_brief(brief['brief_id'],'disposable-test-fixture')
        (folder/'brief.json').write_text(json.dumps(brief['document'],ensure_ascii=False,indent=2))
        if not saved.get('creative_id'):
            style = 'artistic_illustration' if preset=='illustrated_metaphor' else 'tactile_handmade' if preset=='editorial_collage' else 'cinematic'
            creative,_=service.reserve_from_brief(brief_id=brief['brief_id'],template_id='daddy',requested_by='disposable-test',creative_direction={'schema':'ptw.studio.phone-hero-direction.v1','style':style,'background':'scene'})
            generation=creative.get('generation') or {}
            service.authority.update_creative(creative['creative_id'],generation={**generation,'daddy_owner_instruction':f'Use the {preset} composition for this trial. Preserve the Brief language and marketing approach. No hands in artwork.'})
            saved['creative_id']=creative['creative_id'];receipt.write_text(json.dumps(saved,indent=2))
        creative=service.authority.get_creative(saved['creative_id'])
        if creative['status']=='failed': service.retry_generation(saved['project_id'],saved['creative_id'])
        service.generate(saved['creative_id'])
        detail=service.detail(saved['project_id'],saved['creative_id'])
        rendered=service._workspace(saved['creative_id']).render_preview(state_sha256=detail['state_sha256'])
        (folder/'post.png').write_bytes(rendered['bytes'])
        (folder/'result.json').write_text(json.dumps({'detail':detail,'layout_issues':rendered.get('layout_issues',[])},ensure_ascii=False,indent=2))
        print(json.dumps({'case':name,'status':detail['status'],'preset':detail['configuration']['preset'],'issues':detail['generation']['daddy'].get('issues',[])},ensure_ascii=False),flush=True)
    except Exception as error:
        print(json.dumps({'case':name,'error':type(error).__name__,'message':str(error)[:500]}),flush=True)
        (folder/'failure.txt').write_text(f'{type(error).__name__}: {error}')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=ROOT/'.local/daddy-trials');parser.add_argument('--case',choices=[c[0] for c in CASES]);args=parser.parse_args()
    destination=args.output_dir.resolve()
    if not destination.is_relative_to(ROOT/'.local'): raise ValueError('Trial artifacts must remain private under .local')
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda case:run_case(destination,case),[c for c in CASES if not args.case or c[0]==args.case]))
