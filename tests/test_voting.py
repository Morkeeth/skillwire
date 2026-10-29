import concurrent.futures,datetime,json,subprocess,tempfile,time,unittest
from pathlib import Path
from voting import Voting,VoteError
from postgres_store import Postgres
class DailyVotes(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.store=Postgres()
 @classmethod
 def tearDownClass(cls):cls.store.close()
 def setUp(self):
  self.store.clear();self.clock=datetime.datetime(2026,10,29,23,59,tzinfo=datetime.timezone.utc)
  self.v=Voting('test-only-secret-32-bytes-minimum!!',self.store,[{'id':'a'*16,'name':'Alpha','repo':'a/alpha'},{'id':'b'*16,'name':'Beta','repo':'b/beta'}],'test',lambda:self.clock)
 def person(self,ip='192.0.2.1'):
  s,c=self.v.status(None,ip);return c,s['csrf']
 def test_one_vote_total_per_browser_per_utc_day_and_restart(self):
  c,t=self.person();self.v.cast(c,'192.0.2.1','a'*16,t)
  with self.assertRaises(VoteError):self.v.cast(c,'192.0.2.2','b'*16,t)
  v=Voting('test-only-secret-32-bytes-minimum!!',self.store,self.v.catalog,'test',lambda:self.clock)
  self.assertEqual(v.status(c,'192.0.2.1')[0]['counts'],{'a'*16:1})
  self.clock+=datetime.timedelta(minutes=2);s,_=v.status(c,'192.0.2.1');v.cast(c,'192.0.2.1','b'*16,s['csrf']);self.assertEqual(v.status(c,'192.0.2.1')[0]['total'],2)
 def test_cookie_reset_is_limited_by_daily_network_budget(self):
  for _ in range(3):c,t=self.person();self.v.cast(c,'192.0.2.1','a'*16,t)
  c,t=self.person()
  with self.assertRaises(VoteError):self.v.cast(c,'192.0.2.1','a'*16,t)
  self.assertEqual(self.v.status(c,'192.0.2.1')[0]['total'],3)
 def test_concurrent_retries_increment_once(self):
  c,t=self.person()
  def vote(_):
   try:return self.v.cast(c,'192.0.2.1','a'*16,t)['accepted']
   except VoteError:return False
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:accepted=list(ex.map(vote,range(12)))
  self.assertEqual(sum(accepted),1);self.assertEqual(self.v.status(c,'192.0.2.1')[0]['total'],1)
 def test_csrf_origin_honeypot_unknown_skill_and_tamper_never_count(self):
  c,t=self.person()
  for args in [(c,'192.0.2.1','a'*16,'bad',True,''),(c,'192.0.2.1','a'*16,t,False,''),(c,'192.0.2.1','a'*16,t,True,'bot'),(c,'192.0.2.1','c'*16,t,True,''),(c+'x','192.0.2.1','a'*16,t,True,'')]:
   with self.assertRaises(VoteError):self.v.cast(*args)
  self.assertEqual(self.v.status(c,'192.0.2.1')[0]['total'],0)
 def test_hashes_only_no_ip_or_cookie_in_persisted_keys(self):
  c,t=self.person();self.v.cast(c,'192.0.2.1','a'*16,t)
  rows=self.store.sql("select row_to_json(v) from public.skillwire_daily_votes v;")
  self.assertNotIn('192.0.2.1',rows);self.assertNotIn(c.split('.')[0],rows)
  self.assertEqual(len(json.loads(rows)['voter_hash']),64)

 def test_preview_namespace_isolates_real_votes_and_storage_failure_fails_closed(self):
  c,t=self.person();self.v.cast(c,'192.0.2.1','b'*16,t)
  preview=Voting('test-only-secret-32-bytes-minimum!!',self.store,self.v.catalog,'preview',lambda:self.clock)
  self.assertEqual(preview.status(None,'192.0.2.1')[0]['total'],0)
  # The actual store is stopped: no in-memory acceptance or fabricated zero count.
  self.store.stop()
  try:
   with self.assertRaises(Exception):self.v.status(c,'192.0.2.1')
   with self.assertRaises(Exception):self.v.cast(c,'192.0.2.2','a'*16,t)
  finally:self.store.start()
 def test_rls_and_rpc_permissions_block_anon_and_authenticated(self):
  for role in ['anon','authenticated']:
   for query in ["select * from public.skillwire_daily_votes", "select public.skillwire_cast_vote('x','2026-10-29','"+'a'*64+"','"+'b'*64+"','"+'a'*16+"')"]:
    with self.assertRaises(subprocess.CalledProcessError):self.store.sql('set role '+role+';'+query+';')
  self.assertEqual(self.store.sql("select count(*) from pg_class where relname like 'skillwire_%' and relkind='r' and relrowsecurity;"),'5')
 def test_keepalive_preserves_counts_and_prunes_expired_claims(self):
  c,t=self.person();self.v.cast(c,'192.0.2.1','a'*16,t)
  self.store.sql("update public.skillwire_daily_votes set day='2000-01-01';update public.skillwire_daily_networks set day='2000-01-01';")
  self.assertTrue(self.store.keepalive()['ok'])
  self.assertEqual(self.store.sql('select count(*) from public.skillwire_daily_votes;'),'0')
  self.assertEqual(self.v.status(c,'192.0.2.1')[0]['total'],1)
