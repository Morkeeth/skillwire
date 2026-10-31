import concurrent.futures,datetime,subprocess,unittest
from pathlib import Path
from postgres_store import Postgres
from voting import Directions,VoteError
class DirectionVotes(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.store=Postgres();cls.store.sql((Path(__file__).resolve().parents[1]/'migrations/20261031_direction_votes.sql').read_text())
 @classmethod
 def tearDownClass(cls):cls.store.close()
 def setUp(self):
  self.store.sql('truncate public.skillwire_directions,public.skillwire_direction_budget;');self.clock=datetime.datetime(2026,10,31,20,tzinfo=datetime.timezone.utc)
  self.v=Directions('test-only-secret-32-bytes-minimum!!',self.store,[{'id':'a'*16,'name':'Alpha','repo':'a/alpha'},{'id':'b'*16,'name':'Beta','repo':'b/beta'},{'id':'c'*16,'name':'Local','local_bundle':'example'}],'test',lambda:self.clock)
 def identity(self):
  s,c=self.v.status(None,'192.0.2.1');return c,s['csrf']
 def test_toggle_switch_idempotency_and_persistence_across_day(self):
  c,t=self.identity();a='a'*16
  self.v.cast(c,'192.0.2.1',a,t,1);self.v.cast(c,'192.0.2.1',a,t,1)
  self.assertEqual(self.v.status(c,'192.0.2.1')[0]['counts'][a],{'up':1,'down':0,'score':1})
  self.v.cast(c,'192.0.2.1',a,t,-1);self.assertEqual(self.v.status(c,'192.0.2.1')[0]['counts'][a]['score'],-1)
  self.clock+=datetime.timedelta(days=1);s,_=self.v.status(c,'192.0.2.1');self.assertEqual(s['mine'][a],-1)
  self.v.cast(c,'192.0.2.1',a,s['csrf'],0);self.assertNotIn(a,self.v.status(c,'192.0.2.1')[0]['mine'])
 def test_concurrent_duplicate_and_two_people(self):
  c,t=self.identity();a='a'*16
  with concurrent.futures.ThreadPoolExecutor(max_workers=6) as e:list(e.map(lambda _:self.v.cast(c,'192.0.2.1',a,t,1),range(10)))
  c2,t2=self.identity();self.v.cast(c2,'192.0.2.2',a,t2,-1)
  self.assertEqual(self.v.status(c,'192.0.2.1')[0]['counts'][a],{'up':1,'down':1,'score':0})
 def test_validation_and_no_private_identifiers(self):
  c,t=self.identity()
  for value in [True,'1',2,None]:
   with self.assertRaises(VoteError):self.v.cast(c,'192.0.2.1','a'*16,t,value)
  for skill,csrf,cookie in [('d'*16,t,c),('c'*16,t,c),('a'*16,'bad',c),('a'*16,t,c+'x')]:
   with self.assertRaises(VoteError):self.v.cast(cookie,'192.0.2.1',skill,csrf,1)
  self.v.cast(c,'192.0.2.1','a'*16,t,1);raw=self.store.sql('select row_to_json(t) from public.skillwire_directions t;');self.assertNotIn('192.0.2.1',raw);self.assertNotIn(c.split('.')[0],raw)
 def test_rate_budget_noop_and_namespace_isolation(self):
  c,t=self.identity();self.v.cast(c,'192.0.2.1','a'*16,t,1)
  self.store.sql("update public.skillwire_direction_budget set used=120 where scope='network';")
  self.v.cast(c,'192.0.2.1','a'*16,t,1)
  with self.assertRaises(VoteError) as e:self.v.cast(c,'192.0.2.1','b'*16,t,1)
  self.assertEqual(e.exception.status,429)
  self.v.cast(c,'192.0.2.1','a'*16,t,0);self.assertEqual(self.v.status(c,'192.0.2.1')[0]['mine'],{})
  self.assertEqual(Directions('test-only-secret-32-bytes-minimum!!',self.store,self.v.catalog,'preview',lambda:self.clock).status(c,'192.0.2.1')[0]['counts'],{})
 def test_rls_and_original_daily_votes_are_untouched(self):
  for role in ['anon','authenticated']:
   for q in ['select * from public.skillwire_directions',"select public.skillwire_direction_status('x','"+'a'*64+"')"]:
    with self.assertRaises(subprocess.CalledProcessError):self.store.sql('set role '+role+';'+q+';')
  self.assertEqual(self.store.sql("select count(*) from pg_class where relname in ('skillwire_directions','skillwire_direction_budget') and relrowsecurity;"),'2')
  c,t=self.identity();self.v.cast(c,'192.0.2.1','a'*16,t,1);self.assertEqual(self.store.sql('select count(*) from public.skillwire_daily_votes;'),'0')

class DirectionHTTP(DirectionVotes):
 def setUp(self):
  super().setUp()
  import threading
  from unittest.mock import patch
  from http.server import ThreadingHTTPServer
  from api.index import handler
  self.config=patch('voting.configured_directions',return_value=self.v);self.config.start();self.server=ThreadingHTTPServer(('127.0.0.1',0),handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.origin='http://127.0.0.1:'+str(self.server.server_port);self.origins=patch.dict('os.environ',{'SKILLWIRE_VOTE_ORIGINS':self.origin});self.origins.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.origins.stop();self.config.stop()
 def request(self,method,body=None,cookie=None,origin=None):
  import http.client,json
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);headers={'Content-Type':'application/json'}
  if cookie:headers['Cookie']=cookie
  if origin:headers['Origin']=origin
  c.request(method,'/api/directions' if method=='GET' else '/api/direction',json.dumps(body) if body is not None else None,headers);r=c.getresponse();data=json.loads(r.read());h=dict(r.getheaders());code=r.status;c.close();return code,h,data
 def test_real_http_cookie_origin_and_readback(self):
  code,h,s=self.request('GET');self.assertEqual(code,200);self.assertIn('HttpOnly; Secure; SameSite=Strict',h['Set-Cookie']);c=h['Set-Cookie'].split(';')[0]
  body={'skill_id':'a'*16,'csrf':s['csrf'],'value':1}
  self.assertEqual(self.request('POST',body,c)[0],403)
  self.assertEqual(self.request('POST',body,c,'https://evil.invalid')[0],403)
  self.assertEqual(self.request('POST',body,c,self.origin)[0],201)
  self.assertEqual(self.request('GET',cookie=c)[2]['mine']['a'*16],1)
  body['value']=0;self.assertEqual(self.request('POST',body,c,self.origin)[2]['mine'],{})
 def test_unavailable_store_is_not_fake_zero_or_acceptance(self):
  from unittest.mock import patch
  with patch.object(self.store,'rpc',side_effect=VoteError(503,'Community voting is temporarily unavailable.')):
   self.assertEqual(self.request('GET')[0],503)
