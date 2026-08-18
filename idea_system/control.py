from __future__ import annotations
import json,re,threading

class Controller:
 def __init__(self,db,engine): self.db,self.engine=db,engine; self.lock=threading.Lock()
 def _fmt(self,rows): return '\n'.join(f"#{r['id']} [{r.get('mode','')}] — {float(r.get('aggregate_score') or 0):.2f} — {r['title']}" for r in rows) or 'No data.'
 def dispatch(self,text):
  text=text.strip(); low=text.lower()
  aliases={'покажи рейтинг':'/ranking','покажи текущий рейтинг':'/ranking','что сейчас выполняется?':'/status','покажи всю историю':'/history'}
  low=aliases.get(low,low)
  if low.startswith('добавь мою идею:'): text='/idea_add '+text.split(':',1)[1].strip(); low=text.lower()
  if low.startswith('покажи контекст '): text='/context '+text.rsplit(' ',1)[1]; low=text.lower()
  if low.startswith('измени контекст '): text='/context_set '+text.split(' ',2)[2].replace(':',' ',1); low=text.lower()
  parts=text.split(maxsplit=1); cmd=low.split(maxsplit=1)[0]; arg=parts[1] if len(parts)>1 else ''
  m=self.db.mission()
  if cmd=='/status':
   running=self.db.one("SELECT g.number,g.status,(SELECT count(DISTINCT evaluator_context_id) FROM idea_evaluations e JOIN ideas i ON i.id=e.idea_id WHERE i.generation_id=g.id) progress FROM generations g WHERE status IN('creating','evaluating') ORDER BY number DESC LIMIT 1"); latest=self.db.latest_completed(); total=self.db.one('SELECT count(*) n FROM ideas')['n']; pending=self.db.one("SELECT count(*) n FROM idea_submissions WHERE status='pending'")['n']; err=self.db.one("SELECT error_text FROM generations WHERE error_text IS NOT NULL ORDER BY id DESC LIMIT 1")
   return f"Mission: {m['status'].upper()}\nAutopilot: {'ON' if m['auto_enabled'] else 'OFF'}\nRunning: {'YES' if running else 'NO'}"+(f"\nGeneration: G{running['number']}\nPhase: {running['status'].upper()}\nProgress: {running['progress']}/10 evaluator contexts" if running else '')+f"\nLatest completed: {'none' if not latest else 'G'+str(latest['number'])}\nTotal ideas stored: {total}\nPending owner ideas: {pending}\nRun-series remaining: {m['run_series_remaining']}\nLast error: {err['error_text'] if err else 'none'}"
  if cmd=='/run':
   n=int(arg or 1)
   if n<1 or n>100: return 'Run count must be 1..100.'
   if not self.lock.acquire(False): return self.dispatch('/status')
   self.db.execute("UPDATE missions SET run_series_remaining=%s,stop_after_current_cycle=false WHERE id=%s",(n,m['id']))
   threading.Thread(target=self._series,daemon=True).start(); return f"Started {n} generation{'s' if n!=1 else ''}."
  if cmd=='/stop': self.db.execute("UPDATE missions SET stop_after_current_cycle=true WHERE id=%s",(m['id'],)); return 'Stop requested at the next safe generation boundary.'
  if cmd=='/continue':
   if m['recovery_blocked']: return 'Cannot continue until recovery state is healthy.'
   n=m['run_series_remaining']; return 'No preserved run series.' if not n else self.dispatch(f'/run {n}')
  if cmd=='/pause': self.db.execute("UPDATE missions SET status='paused',auto_enabled=false WHERE id=%s",(m['id'],)); return 'Mission paused. Autopilot OFF.'
  if cmd=='/resume': self.db.execute("UPDATE missions SET status='active' WHERE id=%s",(m['id'],)); return 'Mission resumed. Autopilot remains OFF.'
  if cmd=='/autopilot':
   if arg not in {'on','off','24h'}: return 'Usage: /autopilot on|off|24h'
   enabled=arg!='off'; self.db.execute("UPDATE missions SET auto_enabled=%s,cadence_hours=24 WHERE id=%s",(enabled,m['id'])); return f"Autopilot {'ON (24h)' if enabled else 'OFF'}."
  if cmd in {'/ranking','/generation'}:
   number=int(arg) if cmd=='/generation' and arg.isdigit() else None; return self._fmt(self.db.ranking(number,10))
  if cmd=='/top':
   n=min(int(arg or 10),100); rows=self.db.query("SELECT i.id,i.title,i.mode,s.aggregate_score FROM ideas i JOIN idea_scores s ON s.idea_id=i.id JOIN generations g ON g.id=i.generation_id WHERE g.status='completed' ORDER BY s.aggregate_score DESC LIMIT %s",(n,)); return self._fmt(rows)
  if cmd=='/history':
   n=min(int(arg or 20),100); rows=self.db.query("SELECT g.number,max(s.aggregate_score) best,avg(s.aggregate_score) avg,min(s.aggregate_score) worst FROM generations g JOIN idea_scores s ON s.generation_id=g.id WHERE g.status='completed' GROUP BY g.id ORDER BY g.number DESC LIMIT %s",(n,)); return '\n'.join(f"G{x['number']} best {x['best']} / avg {x['avg']:.2f} / worst {x['worst']}" for x in reversed(rows)) or 'No history.'
  if cmd=='/idea':
   if not arg.isdigit(): return 'Usage: /idea ID'
   x=self.db.one("SELECT i.*,s.aggregate_score FROM ideas i LEFT JOIN idea_scores s ON s.idea_id=i.id WHERE i.id=%s",(int(arg),)); return 'Idea not found.' if not x else f"#{x['id']} — {x['title']}\nScore: {x['aggregate_score']}\n{x['one_liner']}\nMode: {x['mode']}\nParents: {x['parent_ids']}\n{json.dumps(x['details'],ensure_ascii=False,indent=2)}"
  if cmd=='/lineage': return self._lineage(int(arg)) if arg.isdigit() else 'Usage: /lineage ID'
  if cmd in {'/report','/reports'}:
   if cmd=='/reports': rows=self.db.query("SELECT id,title,created_at FROM reports ORDER BY id DESC LIMIT %s",(min(int(arg or 10),100),)); return '\n'.join(f"#{x['id']} {x['title']} — {x['created_at']}" for x in rows) or 'No reports.'
   number=int(arg[1:]) if re.fullmatch(r'G\d+',arg,re.I) else None; row=self.db.one("SELECT r.* FROM reports r LEFT JOIN generations g ON g.id=r.generation_id WHERE r.report_type='generation' AND (%s::int IS NULL OR g.number=%s) ORDER BY r.id DESC LIMIT 1",(number,number)); return row['body_text'] if row else 'No report.'
  if cmd=='/idea_add':
   if not arg: return 'Usage: /idea_add TEXT'
   sid=self.db.one("INSERT INTO idea_submissions(mission_id,raw_text) VALUES(%s,%s) RETURNING id",(m['id'],arg))['id']; return f"Owner idea queued as submission {sid}."
  if cmd=='/idea_queue': return '\n'.join(f"{x['id']}: {x['raw_text']}" for x in self.db.query("SELECT * FROM idea_submissions WHERE status='pending' ORDER BY id")) or 'Queue empty.'
  if cmd=='/idea_cancel': changed=self.db.execute("UPDATE idea_submissions SET status='cancelled',updated_at=now() WHERE id=%s AND status='pending'",(int(arg or 0),)); return 'Cancelled.' if changed else 'Pending submission not found.'
  if cmd in {'/guidance','/feedback','/keep','/reject'}:
   if cmd=='/guidance':
    if not arg:return 'Usage: /guidance TEXT'
    gid=self.db.one("INSERT INTO guidance(mission_id,text) VALUES(%s,%s) RETURNING id",(m['id'],arg))['id']; return f'Guidance {gid} active.'
   p=arg.split(maxsplit=1)
   if not p or not p[0].isdigit(): return f'Usage: {cmd} IDEA_ID [TEXT]'
   text2=(p[1] if len(p)>1 else cmd[1:]); self.db.execute("INSERT INTO guidance(mission_id,idea_id,text) VALUES(%s,%s,%s)",(m['id'],int(p[0]),text2)); return 'Feedback recorded for future generations.'
  if cmd=='/guidance_list': return '\n'.join(f"{x['id']}: {x['text']}" for x in self.db.query("SELECT * FROM guidance WHERE active ORDER BY id")) or 'No active guidance.'
  if cmd=='/guidance_clear': changed=self.db.execute("UPDATE guidance SET active=false WHERE id=%s",(int(arg or 0),)); return 'Cleared.' if changed else 'Guidance not found.'
  if cmd=='/contexts': return '\n'.join(f"{x['code']} v{x['version']} {'ON' if x['active'] else 'OFF'} — {x['name']}" for x in self.db.query('SELECT * FROM contexts ORDER BY sort_order'))
  if cmd.startswith('/context'): return self._context(cmd,arg)
  if cmd=='/executions': return '\n'.join(f"#{x['id']} {x['phase']} {x['status']} attempt {x['attempt']}" for x in self.db.query("SELECT * FROM executions ORDER BY id DESC LIMIT %s",(min(int(arg or 10),100),))) or 'No executions.'
  if cmd=='/errors':
   rows=self.db.query("SELECT e.*,g.number,c.code context_code FROM executions e LEFT JOIN generations g ON g.id=e.generation_id LEFT JOIN contexts c ON c.id=e.context_id WHERE e.status='failed' ORDER BY e.id DESC LIMIT %s",(min(int(arg or 10),100),)); m=self.db.mission()
   return ('\n'.join(f"Execution #{x['id']} — G{x['number']} / {x['phase'].upper()} / {x['context_code'] or 'owner'}\nAttempt: {x['attempt']}\nCause: {x['error_text']}" for x in rows)+f"\n\nRecovery blocked: {'YES' if m['recovery_blocked'] else 'NO'}\nRun-series remaining: {m['run_series_remaining']}") if rows else 'No errors.'
  if cmd=='/cost': x=self.db.one("SELECT count(*) calls,coalesce(sum(input_tokens),0) input,coalesce(sum(output_tokens),0) output FROM executions WHERE status='succeeded'"); return f"Calls: {x['calls']}\nInput tokens: {x['input']}\nOutput tokens: {x['output']}"
  if cmd=='/task': return m['task_text']
  if cmd=='/help': return 'Execution: /status /run [N] /stop /continue /pause /resume /autopilot on|off|24h\nHistory: /ranking /generation N /idea ID /top [N] /history [N] /lineage ID\nReports: /report [G#] /reports [N]\nOwner: /idea_add /idea_queue /idea_cancel /guidance /guidance_list /guidance_clear /feedback /keep /reject\nContexts: /contexts /context /context_set /context_name /context_history /context_restore /context_enable /context_disable\nAudit: /executions /errors /cost /task /help'
  return 'Unsupported command. Use /help.'
 def _series(self):
  start=self.db.one("SELECT coalesce(max(number),0) n FROM generations WHERE status='completed'")['n']; requested=self.db.mission()['run_series_remaining']; reason='completed'
  try:
   while True:
    m=self.db.mission()
    if m['run_series_remaining']<=0 or m['stop_after_current_cycle'] or m['status']!='active': break
    try:self.engine.run_one()
    except Exception:reason='recovery failure';break
    self.db.execute("UPDATE missions SET run_series_remaining=greatest(run_series_remaining-1,0) WHERE id=%s",(m['id'],))
   end=self.db.one("SELECT coalesce(max(number),0) n FROM generations WHERE status='completed'")['n']; remaining=self.db.mission()['run_series_remaining']
   if remaining and reason=='completed': reason='owner stop or pause'
   rows=self.db.query("SELECT g.number,max(s.aggregate_score) best FROM generations g JOIN idea_scores s ON s.generation_id=g.id WHERE g.number>%s AND g.status='completed' GROUP BY g.id ORDER BY g.number",(start,)); best=self.db.one("SELECT i.id,i.title,s.aggregate_score FROM ideas i JOIN idea_scores s ON s.idea_id=i.id JOIN generations g ON g.id=i.generation_id WHERE g.number>%s AND g.status='completed' ORDER BY s.aggregate_score DESC LIMIT 1",(start,))
   body=f"Run series requested: {requested}\nCompleted: {end-start}\nEnded: {reason}\nRemaining: {remaining}"+(f"\nBest discovered: #{best['id']} — {best['aggregate_score']}\nTrend: "+', '.join(f"G{x['number']}={x['best']}" for x in rows) if best else '')
   self.db.execute("INSERT INTO reports(mission_id,report_type,title,body_text,payload) VALUES(%s,'run_series','Run series',%s,%s::jsonb)",(self.db.mission()['id'],body,json.dumps({'requested':requested,'completed':end-start,'reason':reason,'remaining':remaining,'trend':[dict(x) for x in rows]},default=str))); self.engine.notify(body)
  finally:self.lock.release()
 def _lineage(self,i,depth=0,seen=None):
  seen=seen or set()
  if i in seen:return '  '*depth+f'#{i} (cycle)'
  x=self.db.one('SELECT id,title,parent_ids FROM ideas WHERE id=%s',(i,));
  if not x:return 'Idea not found.'
  seen.add(i); return '\n'.join(['  '*depth+f"#{i} {x['title']}"]+[self._lineage(p,depth+1,seen) for p in x['parent_ids']])
 def _context(self,cmd,arg):
  p=arg.split(maxsplit=1); code=p[0].upper() if p else ''; x=self.db.one('SELECT * FROM contexts WHERE code=%s',(code,))
  if not x:return 'Context not found.'
  if cmd=='/context':return f"{code} v{x['version']} — {x['name']}\n{x['prompt_text']}"
  if cmd=='/context_history':return '\n'.join(f"v{r['version']} {r['created_at']} {r['change_note'] or ''}" for r in self.db.query('SELECT * FROM context_revisions WHERE context_id=%s ORDER BY version DESC',(x['id'],)))
  if cmd in {'/context_enable','/context_disable'}: self.db.execute('UPDATE contexts SET active=%s,updated_at=now() WHERE id=%s',(cmd.endswith('enable'),x['id'])); return f"{code} {'enabled' if cmd.endswith('enable') else 'disabled'}. A run still requires exactly 10 active contexts."
  if cmd=='/context_restore':
   if len(p)<2 or not p[1].isdigit():return 'Usage: /context_restore CODE VERSION'
   old=self.db.one('SELECT * FROM context_revisions WHERE context_id=%s AND version=%s',(x['id'],int(p[1]))); return 'Revision not found.' if not old else self._rev(x,old['name'],old['prompt_text'],f"restored from v{p[1]}")
  if len(p)<2:return f'Usage: {cmd} CODE TEXT'
  return self._rev(x,p[1] if cmd=='/context_name' else x['name'],p[1] if cmd=='/context_set' else x['prompt_text'],cmd[1:])
 def _rev(self,x,name,prompt,note):
  with self.db.connect() as c:
   y=c.execute('SELECT * FROM contexts WHERE id=%s FOR UPDATE',(x['id'],)).fetchone(); v=y['version']+1
   c.execute('INSERT INTO context_revisions(context_id,version,name,prompt_text,changed_by,change_note) VALUES(%s,%s,%s,%s,\'owner\',%s)',(x['id'],v,name,prompt,note)); c.execute('UPDATE contexts SET name=%s,prompt_text=%s,version=%s,updated_at=now() WHERE id=%s',(name,prompt,v,x['id']))
  return f"{x['code']} updated to v{v}. Future calls only."
