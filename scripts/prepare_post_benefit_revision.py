#!/usr/bin/env python3
"""Prepare an owner-requested third benefit from a read-only Post snapshot."""
import argparse,base64,json,sys,tempfile
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from validation_pipeline.template_components import normalize_document,sha,RENDERER_VERSION
from validation_pipeline.template_assets import document_asset_manifest
from validation_pipeline.post_template_runtime import post_definition
from validation_pipeline.post_templates import POST_TEMPLATE_REGISTRY
from validation_pipeline.template_registry import TemplateRegistry
from validation_pipeline.studio_workspace import PostStudioWorkspace
from validation_pipeline.template_previews import render_designs
parser=argparse.ArgumentParser(description='Prepare a local third-benefit template revision and exact Project preview; never write to an authority.')
parser.add_argument('--source-snapshot',type=Path,required=True)
parser.add_argument('--output-dir',type=Path,required=True)
args=parser.parse_args()
folder=args.output_dir; folder.mkdir(parents=True,exist_ok=True)
source=json.loads(args.source_snapshot.read_text())
original=source['template']; document=deepcopy(original['document'])
secondary=next(c for c in document['components'] if c['id']=='benefit_secondary')
third=deepcopy(secondary); third['id']='benefit_tertiary'
for box in ('box','mobile_box'): third[box][1]+=55
index=document['components'].index(secondary)
document['components'].insert(index+1,third)
document=normalize_document(document)
assert len(document['components'])==len(original['document']['components'])+1
assert [c for c in document['components'] if c['id']!='benefit_tertiary']==normalize_document(original['document'])['components']
identity={'surface':'post','template_id':original['template_id'],'template_version':original['template_version']+1,
 'document':document,'post_reference':None,'renderer_key':RENDERER_VERSION,'asset_manifest':document_asset_manifest(document)}
record={**identity,'template_sha256':sha(identity)}
(folder/'template-candidate.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
old_definition=post_definition(original); new_definition=post_definition(record)
registry=TemplateRegistry('post',(*POST_TEMPLATE_REGISTRY.all(),old_definition,new_definition))
temporary=tempfile.TemporaryDirectory(prefix='ptw-benefit-review-')
workspace_path=Path(temporary.name)
for relative,encoded in source['files'].items():
 path=workspace_path/relative
 if Path(relative).is_absolute() or '..' in Path(relative).parts: raise ValueError('Snapshot file escaped workspace')
 path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(base64.b64decode(encoded,validate=True))
workspace=PostStudioWorkspace(workspace_path,template_registry=lambda:registry)
before=workspace.detail()
changed=workspace.switch_template(base_sha256=before['state_sha256'],template_reference=new_definition.identity.to_reference(),
 request_id=str(uuid4()),configuration=before['configuration'],content=before['content'])
assert changed['content']['template_text']['benefit_tertiary']==''
for key,text in before['content']['template_text'].items(): assert changed['content']['template_text'][key]==text
for relative,encoded in source['files'].items():
 if relative.startswith(('versions/','assets/')): assert (workspace_path/relative).read_bytes()==base64.b64decode(encoded)
render=workspace.render_preview(state_sha256=changed['state_sha256'])
(folder/'post-preview.png').write_bytes(render['bytes'])
filled=deepcopy(changed['content']); filled['template_text']['benefit_tertiary']='• Третя перевага'
render=workspace.render_preview(state_sha256=changed['state_sha256'],configuration=changed['configuration'],content=filled)
(folder/'third-benefit-demo.png').write_bytes(render['bytes'])
neutral=render_designs({'post':document})['post:desktop']
(folder/'template-preview.png').write_bytes(neutral['bytes'])
report={'reference':new_definition.identity.to_reference(),'new_field':'benefit_tertiary','initial_value':'',
 'previous_copy_preserved':True,'historical_assets_versions_preserved':True,'layout_issues':render.get('layout_issues',[]),
 'template_geometry_failures':neutral['failures'],'provenance':'Direct owner-requested component addition; local deterministic review; no model composition or comparison claimed.'}
(folder/'project-draft.json').write_text(json.dumps({k:changed[k] for k in ('template_reference','configuration','content')},ensure_ascii=False,indent=2)+'\n')
(folder/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
temporary.cleanup()
print(json.dumps(report,ensure_ascii=False))
