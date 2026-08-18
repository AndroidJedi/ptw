from __future__ import annotations
import hashlib,json
from decimal import Decimal
from .recovery import recover,RecoveryExhausted

RUBRIC_KEYS={"exit_potential","founder_independence","distribution","scalability_economics","defensibility","speed_capital_efficiency"}

class Engine:
 def __init__(self,db,provider,notify=lambda text:None): self.db,self.provider,self.notify=db,provider,notify
 def _call(self,c,mission,generation,phase,context,payload,validator=None):
  def action(attempt):
   eid=c.execute("INSERT INTO executions(mission_id,generation_id,phase,status,context_id,attempt,model_name,prompt_hash,request_json) VALUES(%s,%s,%s,'running',%s,%s,%s,%s,%s::jsonb) RETURNING id",(mission['id'],generation['id'],phase,context.get('id'),attempt,'mock' if type(self.provider).__name__=='MockProvider' else 'configured',hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest(),json.dumps(payload,default=str))).fetchone()['id']; c.commit()
   try:
    result=self.provider.generate_structured(phase,'Idea Evolution v1',payload,{})
    if validator: validator(result)
    c.execute("UPDATE executions SET status='succeeded',response_json=%s::jsonb,completed_at=now() WHERE id=%s",(json.dumps(result),eid)); c.commit(); return result
   except Exception as error:
    c.execute("UPDATE executions SET status='failed',error_text=%s,completed_at=now() WHERE id=%s",(type(error).__name__,eid)); c.commit(); raise
  return recover(f"G{generation['number']} / {phase.upper()} / {context.get('code','owner')}",action,self.notify)
 def run_one(self):
  with self.db.connect() as c:
   mission=c.execute("SELECT * FROM missions WHERE code='MISSION_450M_5Y' FOR UPDATE").fetchone()
   if mission['status']!='active' or mission['recovery_blocked']: raise RuntimeError('mission is paused or recovery-blocked')
   if len(c.execute("SELECT 1 FROM contexts WHERE active").fetchall())!=10: raise RuntimeError('exactly 10 active contexts required')
   if c.execute("SELECT 1 FROM generations WHERE status IN('creating','evaluating')").fetchone(): raise RuntimeError('a generation is already running')
   failed=c.execute("SELECT g.* FROM generations g WHERE mission_id=%s AND status='failed' AND NOT EXISTS(SELECT 1 FROM ideas WHERE generation_id=g.id) ORDER BY number DESC LIMIT 1 FOR UPDATE",(mission['id'],)).fetchone()
   if failed:
    number=failed['number']; generation=c.execute("UPDATE generations SET status='creating',error_text=NULL,started_at=now(),completed_at=NULL WHERE id=%s RETURNING *",(failed['id'],)).fetchone()
   else:
    number=c.execute("SELECT coalesce(max(number),0)+1 AS number FROM generations WHERE mission_id=%s",(mission['id'],)).fetchone()['number']; generation=c.execute("INSERT INTO generations(mission_id,number,status) VALUES(%s,%s,'creating') RETURNING *",(mission['id'],number)).fetchone()
   c.commit()
   try: self._create(c,mission,generation); self._evaluate(c,mission,generation); self._report(c,mission,generation)
   except Exception as error:
    c.execute("UPDATE generations SET status='failed',error_text=%s WHERE id=%s",(type(error).__name__,generation['id']))
    if isinstance(error,RecoveryExhausted): c.execute("UPDATE missions SET recovery_blocked=true,stop_after_current_cycle=true WHERE id=%s",(mission['id'],))
    c.commit(); raise
   return number
 def _idea_insert(self,c,mission,generation,context,mode,data,submission=None):
  parents=[int(x) for x in data.get('parent_ids',[])]
  if parents:
   known={r['id'] for r in c.execute("SELECT id FROM ideas WHERE mission_id=%s AND id=ANY(%s)",(mission['id'],parents)).fetchall()}
   if known!=set(parents): raise ValueError('invalid parent IDs')
  required={'customer','problem','product','business_model','distribution','automation','five_year_exit_logic','key_risks','first_validation_test'}
  if not required.issubset(data.get('details',{})): raise ValueError('incomplete idea details')
  return c.execute("INSERT INTO ideas(mission_id,generation_id,creator_context_id,mode,title,one_liner,details,parent_ids,lineage_note,owner_submission_id) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s) RETURNING id",(mission['id'],generation['id'],context.get('id'),mode,data['title'],data['one_liner'],json.dumps(data['details']),parents,data.get('lineage_note'),submission)).fetchone()['id']
 def _validate_idea(self,c,mission,data):
  required={'customer','problem','product','business_model','distribution','automation','five_year_exit_logic','key_risks','first_validation_test'}
  if not {'title','one_liner','details'}.issubset(data) or not required.issubset(data.get('details',{})): raise ValueError('incomplete idea output')
  parents=[int(x) for x in data.get('parent_ids',[])]
  if parents and {r['id'] for r in c.execute("SELECT id FROM ideas WHERE mission_id=%s AND id=ANY(%s)",(mission['id'],parents)).fetchall()}!=set(parents): raise ValueError('invalid parent IDs')
 def _validate_evaluations(self,result,idea_ids):
  evaluations=result.get('evaluations',[]); ids=[int(e['idea_id']) for e in evaluations]
  if len(evaluations)!=10 or set(ids)!=set(idea_ids): raise ValueError('evaluation IDs invalid')
  for e in evaluations:
   if not 0<=float(e['score'])<=100 or set(e['criteria'])!=RUBRIC_KEYS or abs(sum(float(v) for v in e['criteria'].values())-float(e['score']))>.05: raise ValueError('evaluation rubric invalid')
 def _working_set(self,c,mission,current):
  rows=c.execute("SELECT i.id,i.title,i.one_liner,s.aggregate_score FROM ideas i JOIN idea_scores s ON s.idea_id=i.id WHERE i.generation_id=%s ORDER BY i.id",(current['id'],)).fetchall()
  hof=c.execute("SELECT i.id,i.title,s.aggregate_score FROM ideas i JOIN generations g ON g.id=i.generation_id JOIN idea_scores s ON s.idea_id=i.id WHERE i.mission_id=%s AND g.status='completed' AND g.number<%s ORDER BY s.aggregate_score DESC LIMIT 3",(mission['id'],current['number'])).fetchall()
  compact=[]
  for row in rows:
   item=dict(row); critiques=c.execute("SELECT score,critique,fatal_flaw FROM idea_evaluations WHERE idea_id=%s ORDER BY score",(row['id'],)).fetchall()
   item['median_critique']=critiques[len(critiques)//2]['critique']; item['critical_critique']=critiques[0]['critique']; item['fatal_flaw']=critiques[0]['fatal_flaw']; compact.append(item)
  failures=sorted(compact,key=lambda x:x['aggregate_score'])[:2]
  return compact,[dict(x) for x in hof],failures
 def _create(self,c,mission,generation):
  contexts=[dict(x) for x in c.execute("SELECT * FROM contexts WHERE active ORDER BY sort_order").fetchall()]
  submissions=c.execute("SELECT * FROM idea_submissions WHERE mission_id=%s AND status='pending' ORDER BY created_at,id LIMIT 10 FOR UPDATE SKIP LOCKED",(mission['id'],)).fetchall()
  for s in submissions: c.execute("UPDATE idea_submissions SET status='scheduled',target_generation_number=%s,updated_at=now() WHERE id=%s",(generation['number'],s['id']))
  c.commit(); created=0
  for s in submissions:
   payload={'raw_text':s['raw_text'],'context':{'code':'owner'}}; data=self._call(c,mission,generation,'normalize_human',{},payload,lambda d:self._validate_idea(c,mission,d))
   iid=self._idea_insert(c,mission,generation,{},'human',data,s['id']); c.execute("UPDATE idea_submissions SET inserted_idea_id=%s WHERE id=%s",(iid,s['id'])); c.commit(); created+=1
  prior=c.execute("SELECT * FROM generations WHERE mission_id=%s AND status='completed' ORDER BY number DESC LIMIT 1",(mission['id'],)).fetchone()
  remaining=10-created; exploit=0 if not prior else round(remaining*.7); explore=remaining-exploit
  if prior: current,hof,failures=self._working_set(c,mission,prior)
  for idx in range(remaining):
   ctx=contexts[(generation['number']-1+idx)%10]; mode='initial' if not prior else ('exploit' if idx<exploit else 'explore')
   payload={'task':mission['task_text'],'context':{'code':ctx['code'],'name':ctx['name'],'prompt':ctx['prompt_text']},'owner_guidance':[r['text'] for r in c.execute("SELECT text FROM guidance WHERE mission_id=%s AND active",(mission['id'],)).fetchall()]}
   if prior: payload.update(mode=mode,current_generation=current,hall_of_fame=hof,failures=failures,suggested_parent_ids=[current[idx%len(current)]['id']] if mode=='exploit' else [])
   data=self._call(c,mission,generation,'generate' if not prior else 'evolve',ctx,payload,lambda d:self._validate_idea(c,mission,d)); self._idea_insert(c,mission,generation,ctx,mode,data); c.commit()
  if c.execute("SELECT count(*) AS n FROM ideas WHERE generation_id=%s",(generation['id'],)).fetchone()['n']!=10: raise RuntimeError('generation size invariant failed')
  c.execute("UPDATE generations SET status='created' WHERE id=%s",(generation['id'],)); c.commit()
 def _evaluate(self,c,mission,generation):
  c.execute("UPDATE generations SET status='evaluating' WHERE id=%s",(generation['id'],)); c.commit()
  ideas=[dict(x) for x in c.execute("SELECT id,title,one_liner,details FROM ideas WHERE generation_id=%s ORDER BY id",(generation['id'],)).fetchall()]
  for ctx in c.execute("SELECT * FROM contexts WHERE active ORDER BY sort_order").fetchall():
   if c.execute("SELECT count(*) AS n FROM idea_evaluations e JOIN ideas i ON i.id=e.idea_id WHERE i.generation_id=%s AND e.evaluator_context_id=%s",(generation['id'],ctx['id'])).fetchone()['n']==10: continue
   idea_ids={i['id'] for i in ideas}; result=self._call(c,mission,generation,'evaluate',ctx,{'task':mission['task_text'],'evaluator':{'code':ctx['code'],'prompt':ctx['prompt_text']},'ideas':ideas},lambda r:self._validate_evaluations(r,idea_ids))
   evaluations=result['evaluations']
   for e in evaluations:
    c.execute("INSERT INTO idea_evaluations(idea_id,evaluator_context_id,score,criteria,strengths,critique,fatal_flaw) VALUES(%s,%s,%s,%s::jsonb,%s,%s,%s) ON CONFLICT DO NOTHING",(e['idea_id'],ctx['id'],e['score'],json.dumps(e['criteria']),e['strengths'],e['critique'],e.get('fatal_flaw')))
   c.commit()
  if c.execute("SELECT count(*) AS n FROM idea_evaluations e JOIN ideas i ON i.id=e.idea_id WHERE i.generation_id=%s",(generation['id'],)).fetchone()['n']!=100: raise RuntimeError('evaluation count invariant failed')
  c.execute("UPDATE generations SET status='completed',completed_at=now() WHERE id=%s",(generation['id'],)); c.execute("UPDATE idea_submissions SET status='inserted',updated_at=now() WHERE target_generation_number=%s AND status='scheduled'",(generation['number'],)); c.commit()
 def _report(self,c,mission,generation):
  ranked=c.execute("SELECT i.id,i.title,i.mode,s.aggregate_score FROM ideas i JOIN idea_scores s ON s.idea_id=i.id WHERE i.generation_id=%s ORDER BY s.aggregate_score DESC",(generation['id'],)).fetchall(); vals=[float(x['aggregate_score']) for x in ranked]
  previous=c.execute("SELECT max(s.aggregate_score) best FROM idea_scores s JOIN generations g ON g.id=s.generation_id WHERE g.mission_id=%s AND g.status='completed' AND g.number<%s",(mission['id'],generation['number'])).fetchone()['best']; delta=None if previous is None else vals[0]-float(previous)
  historical=c.execute("SELECT i.id,i.title,s.aggregate_score FROM ideas i JOIN idea_scores s ON s.idea_id=i.id JOIN generations g ON g.id=i.generation_id WHERE g.status='completed' ORDER BY s.aggregate_score DESC LIMIT 3").fetchall(); owners=[dict(x) for x in ranked if x['mode']=='human']; failures=[dict(x) for x in ranked[-2:]]
  disagree=c.execute("SELECT i.id,max(e.score)-min(e.score) spread FROM ideas i JOIN idea_evaluations e ON e.idea_id=i.id WHERE i.generation_id=%s GROUP BY i.id ORDER BY spread DESC LIMIT 1",(generation['id'],)).fetchone(); guidance=[x['text'] for x in c.execute("SELECT text FROM guidance WHERE mission_id=%s AND active",(mission['id'],)).fetchall()]; calls=c.execute("SELECT count(*) calls,coalesce(sum(input_tokens),0) input_tokens,coalesce(sum(output_tokens),0) output_tokens,count(*) FILTER(WHERE attempt>1) recoveries FROM executions WHERE generation_id=%s AND status='succeeded'",(generation['id'],)).fetchone()
  payload={'ranking':[dict(x) for x in ranked],'best':vals[0],'average':sum(vals)/10,'worst':vals[-1],'delta_best':delta,'historical_best':dict(historical[0]),'hall_of_fame':[dict(x) for x in historical],'owner_ideas':owners,'failures':failures,'evaluator_disagreement':dict(disagree),'top_lineage_root':ranked[0]['id'],'active_guidance':guidance,'recovery_incidents':calls['recoveries'],'model_summary':dict(calls)}
  lines=[f"G{generation['number']} complete",f"Best: #{ranked[0]['id']} — {vals[0]:.2f}",f"Average: {sum(vals)/10:.2f}",f"Worst: {vals[-1]:.2f}",f"Delta best: {'n/a' if delta is None else f'{delta:+.2f}'}",f"Historical best: #{historical[0]['id']} — {historical[0]['aggregate_score']}",f"Owner ideas: {len(owners)}",f"Recoveries: {calls['recoveries']}","\nRanking:"]+[f"{n}. #{x['id']} [{x['mode']}] {x['aggregate_score']} — {x['title']}" for n,x in enumerate(ranked,1)]+[f"\nBottom two: {', '.join('#'+str(x['id']) for x in failures)}",f"Largest evaluator spread: #{disagree['id']} ({disagree['spread']})",f"Top lineage: /lineage {ranked[0]['id']}",f"Active guidance: {len(guidance)}",f"Model calls: {calls['calls']}; tokens: {calls['input_tokens']}/{calls['output_tokens']}"]
  body='\n'.join(lines); c.execute("INSERT INTO reports(mission_id,generation_id,report_type,title,body_text,payload) VALUES(%s,%s,'generation',%s,%s,%s::jsonb)",(mission['id'],generation['id'],f"Generation G{generation['number']}",body,json.dumps(payload,default=str))); c.commit(); self.notify('✅ '+ '\n'.join(lines[:8])+f"\nTotal ideas: {generation['number']*10}\n\n/report G{generation['number']}")
 def reconcile(self):
  rows=self.db.query("SELECT id,status FROM generations WHERE status IN('creating','evaluating')")
  for row in rows:
   ideas=self.db.one("SELECT count(*) n FROM ideas WHERE generation_id=%s",(row['id'],))['n']; evals=self.db.one("SELECT count(*) n FROM idea_evaluations e JOIN ideas i ON i.id=e.idea_id WHERE i.generation_id=%s",(row['id'],))['n']
   if ideas==10 and evals==100: self.db.execute("UPDATE generations SET status='completed',completed_at=coalesce(completed_at,now()) WHERE id=%s",(row['id'],))
