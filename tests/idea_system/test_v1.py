import os,time,unittest
from idea_system.db import Database
from idea_system.engine import Engine
from idea_system.provider import MockProvider
from idea_system.control import Controller
from idea_system.recovery import recover,RecoveryExhausted
from idea_system.seed import seed

class V1Acceptance(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.url=os.environ['DATABASE_URL']; cls.db=Database(cls.url); seed(cls.url)
 @classmethod
 def tearDownClass(cls):
  with cls.db.connect() as c:c.execute("TRUNCATE telegram_events,reports,executions,guidance,idea_evaluations,ideas,idea_submissions,generations RESTART IDENTITY CASCADE");c.execute("UPDATE missions SET auto_enabled=false,run_series_remaining=0,stop_after_current_cycle=false,recovery_blocked=false,status='active'")
 def setUp(self):
  with self.db.connect() as c:c.execute("TRUNCATE telegram_events,reports,executions,guidance,idea_evaluations,ideas,idea_submissions,generations RESTART IDENTITY CASCADE");c.execute("UPDATE missions SET auto_enabled=false,run_series_remaining=0,stop_after_current_cycle=false,recovery_blocked=false,status='active'")
  self.provider=MockProvider();self.notes=[];self.engine=Engine(self.db,self.provider,self.notes.append);self.control=Controller(self.db,self.engine)
 def test_seed_idempotence_and_context_revision(self):
  seed(self.url);seed(self.url);self.assertEqual(self.db.one("SELECT count(*) n FROM missions")['n'],1);self.assertEqual(self.db.one("SELECT count(*) n FROM contexts WHERE active")['n'],10)
  before=self.db.one("SELECT version FROM contexts WHERE code='C03'")['version'];self.control.dispatch('/context_set C03 Replacement lens');self.control.dispatch('/context_restore C03 1');x=self.db.one("SELECT version FROM contexts WHERE code='C03'");self.assertEqual(x['version'],before+2);self.assertEqual(self.db.one("SELECT max(version) n FROM context_revisions WHERE context_id=(SELECT id FROM contexts WHERE code='C03')")['n'],before+2)
 def test_generation_invariants_archive_hof_and_prompt_bound(self):
  self.assertEqual(self.engine.run_one(),1);self.assertEqual(self.db.one('SELECT count(*) n FROM ideas')['n'],10);self.assertEqual(self.db.one('SELECT count(*) n FROM idea_evaluations')['n'],100)
  self.assertEqual(self.engine.run_one(),2);self.assertEqual(self.db.one('SELECT count(*) n FROM ideas')['n'],20);self.assertEqual(self.db.one('SELECT count(*) n FROM reports')['n'],2)
  evolves=[x for x in self.provider.calls if x['mode']=='evolve'];self.assertEqual(len(evolves),10);self.assertEqual(len(evolves[0]['input']['current_generation']),10);self.assertLessEqual(len(evolves[0]['input']['hall_of_fame']),3);self.assertEqual(len(evolves[0]['input']['failures']),2)
  modes=self.db.query("SELECT mode,count(*) n FROM ideas i JOIN generations g ON g.id=i.generation_id WHERE g.number=2 GROUP BY mode");self.assertEqual({x['mode']:x['n'] for x in modes},{'exploit':7,'explore':3})
 def test_owner_queue_slots_and_scoring(self):
  for x in range(2):self.control.dispatch(f'/idea_add owner concept {x}')
  self.engine.run_one();self.assertEqual(self.db.one("SELECT count(*) n FROM ideas WHERE mode='human'")['n'],2);self.assertEqual(self.db.one("SELECT count(*) n FROM idea_submissions WHERE status='inserted'")['n'],2);self.assertEqual(self.db.one('SELECT count(*) n FROM idea_evaluations')['n'],100)
 def test_commands_and_history(self):
  self.engine.run_one()
  for cmd in ('/status','/help','/task','/contexts','/ranking','/top','/history','/idea 1','/lineage 1','/report','/reports','/executions','/errors','/cost','/guidance x','/guidance_list','/keep 1 x','/reject 1 x','/feedback 1 x'):
   self.assertTrue(self.control.dispatch(cmd))
  self.assertIn('queued',self.control.dispatch('/idea_add test').lower());self.assertIn('test',self.control.dispatch('/idea_queue'))
 def test_recovery_exactly_two_and_terminal(self):
  attempts=[]
  def succeeds(n):
   attempts.append(n)
   if n<3: raise RuntimeError()
   return None
  recover('step',succeeds,self.notes.append);self.assertEqual(attempts,[1,2,3])
  attempts=[]
  with self.assertRaises(RecoveryExhausted):recover('step',lambda n:(attempts.append(n),(_ for _ in ()).throw(RuntimeError()))[1],self.notes.append)
  self.assertEqual(attempts,[1,2,3])
 def test_malformed_structured_output_recovers(self):
  class Repairing(MockProvider):
   def __init__(self):super().__init__();self.bad=2
   def generate_structured(self,mode,system_prompt,input_payload,output_schema):
    if mode=='evaluate' and self.bad:
     self.bad-=1;return {'evaluations':[]}
    return super().generate_structured(mode,system_prompt,input_payload,output_schema)
  notes=[];Engine(self.db,Repairing(),notes.append).run_one();self.assertEqual(self.db.one('SELECT count(*) n FROM idea_evaluations')['n'],100);self.assertTrue(any('2/2' in x for x in notes))
 def test_uniqueness_constraints(self):
  self.engine.run_one()
  with self.assertRaises(Exception):
   with self.db.connect() as c:c.execute("INSERT INTO generations(mission_id,number,status) VALUES((SELECT id FROM missions LIMIT 1),1,'creating')")
 def test_restart_reconciliation_no_duplicates(self):
  self.engine.run_one();g=self.db.latest_completed();self.db.execute("UPDATE generations SET status='evaluating',completed_at=NULL WHERE id=%s",(g['id'],));self.engine.reconcile();self.assertEqual(self.db.one("SELECT status FROM generations WHERE id=%s",(g['id'],))['status'],'completed');self.assertEqual(self.db.one('SELECT count(*) n FROM idea_evaluations')['n'],100)

if __name__=='__main__':unittest.main()
