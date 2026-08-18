from __future__ import annotations
import asyncio,os
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI,Header,HTTPException
from .control import Controller
from .db import Database
from .engine import Engine
from .provider import BridgeProvider,DisabledProvider,MockProvider
from .seed import seed

def ids(name,fallback=''):
 return {int(x.strip()) for x in os.getenv(name,fallback).split(',') if x.strip()}

def create_app(db=None,provider=None,sender=None):
 db=db or Database(os.environ['DATABASE_URL']); configured=os.getenv('LLM_PROVIDER','bridge'); provider=provider or (MockProvider() if configured=='mock' else BridgeProvider() if configured=='bridge' else DisabledProvider())
 token=os.getenv('TELEGRAM_BOT_TOKEN',''); allowed_users=ids('TELEGRAM_ALLOWED_USER_IDS'); allowed_chats=ids('TELEGRAM_ALLOWED_CHAT_IDS',os.getenv('TELEGRAM_ALLOWED_USER_IDS',''))
 async def telegram_send(chat_id,text):
  if sender:return await sender(chat_id,text)
  async with httpx.AsyncClient(timeout=15) as client:
   r=await client.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':chat_id,'text':text[:4096]}); r.raise_for_status()
 def notify(text):
  for chat in allowed_chats:
   try: asyncio.run(telegram_send(chat,text))
   except RuntimeError: pass
 engine=Engine(db,provider,notify); controller=Controller(db,engine)
 @asynccontextmanager
 async def lifespan(app):
  if os.getenv('SKIP_SEED')!='1': await asyncio.to_thread(seed,db.url)
  await asyncio.to_thread(engine.reconcile)
  task=asyncio.create_task(scheduler())
  yield
  task.cancel(); await asyncio.gather(task,return_exceptions=True)
 async def scheduler():
  while True:
   await asyncio.sleep(60)
   m=await asyncio.to_thread(db.mission)
   if m['auto_enabled'] and m['status']=='active' and not m['recovery_blocked']:
    recent=await asyncio.to_thread(db.one,"SELECT count(*) n FROM generations WHERE status='completed' AND completed_at>now()-interval '1 day'")
    if recent['n']<m['max_generations_per_day']: await asyncio.to_thread(controller.dispatch,'/run')
 app=FastAPI(title='Idea Evolution v1',docs_url=None,redoc_url=None,lifespan=lifespan)
 @app.get('/healthz')
 def health():
  m=db.mission(); return {'status':'ok','mission':bool(m),'contexts':db.one('SELECT count(*) n FROM contexts WHERE active')['n'],'autopilot':bool(m and m['auto_enabled']),'generations':db.one("SELECT count(*) n FROM generations WHERE status='completed'")['n']}
 @app.post('/internal/telegram/update')
 async def telegram(update:dict,x_ptw_bridge_token:str=Header(default='')):
  if not token or x_ptw_bridge_token!=token: raise HTTPException(403,'invalid bridge token')
  message=update.get('message') or {}; sender_id=(message.get('from') or {}).get('id'); chat_id=(message.get('chat') or {}).get('id'); text=message.get('text') or message.get('caption') or ''
  if sender_id not in allowed_users or chat_id not in allowed_chats: raise HTTPException(403,'unauthorized')
  db.event(chat_id,'in','command',text); response=await asyncio.to_thread(controller.dispatch,text)
  try: await telegram_send(chat_id,response)
  except Exception as error: db.event(chat_id,'out','send_failed',type(error).__name__); raise HTTPException(503,'Telegram send failed')
  db.event(chat_id,'out','response',response); return {'ok':True}
 return app
