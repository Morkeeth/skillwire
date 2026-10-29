import concurrent.futures,datetime,json,subprocess,tempfile,time,unittest
from pathlib import Path
from voting import Voting,VoteError
class Redis:
 def __init__(self,sock):self.sock=sock
 def command(self,*args):
  r=subprocess.run(['redis-cli','-s',self.sock,'--json',*[str(a) for a in args]],capture_output=True,text=True,check=True)
  d=json.loads(r.stdout)
  if isinstance(d,dict) and 'error' in d:raise RuntimeError(d['error'])
  return d
class DailyVotes(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.sock=str(Path(cls.tmp.name)/'redis.sock')
  cls.proc=subprocess.Popen(['redis-server','--port','0','--unixsocket',cls.sock,'--save','','--appendonly','no'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cls.store=Redis(cls.sock)
  for _ in range(100):
   try:
    if cls.store.command('PING')=='PONG':break
   except Exception:time.sleep(.02)
  else:raise RuntimeError('Owned test Redis did not start')
 @classmethod
 def tearDownClass(cls):cls.proc.terminate();cls.proc.wait(timeout=5);cls.tmp.cleanup()
 def setUp(self):
  self.store.command('FLUSHDB');self.clock=datetime.datetime(2026,10,29,23,59,tzinfo=datetime.timezone.utc)
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
  keys=self.store.command('KEYS','*');self.assertTrue(keys);self.assertNotIn('192.0.2.1',str(keys));self.assertNotIn(c,str(keys))
 def test_preview_namespace_isolates_real_votes_and_storage_failure_fails_closed(self):
  c,t=self.person();self.v.cast(c,'192.0.2.1','b'*16,t)
  preview=Voting('test-only-secret-32-bytes-minimum!!',self.store,self.v.catalog,'preview',lambda:self.clock)
  self.assertEqual(preview.status(None,'192.0.2.1')[0]['total'],0)
  # The actual store is stopped: no in-memory acceptance or fabricated zero count.
  self.proc.terminate();self.proc.wait(timeout=5)
  with self.assertRaises(Exception):self.v.status(c,'192.0.2.1')
  with self.assertRaises(Exception):self.v.cast(c,'192.0.2.2','a'*16,t)
  self.__class__.proc=subprocess.Popen(['redis-server','--port','0','--unixsocket',self.sock,'--save','','--appendonly','no'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(100):
   try:
    if self.store.command('PING')=='PONG':break
   except Exception:time.sleep(.02)
  else:raise RuntimeError('Test Redis restart failed')
