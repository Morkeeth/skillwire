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
  self.store.sql('truncate public.skillwire_directions,public.skillwire_direction_budget,public.skillwire_direction_totals;');self.clock=datetime.datetime(2026,10,31,20,tzinfo=datetime.timezone.utc)
  self.v=Directions('test-only-secret-32-bytes-minimum!!',self.store,[{'id':'a'*16,'name':'Alpha','repo':'a/alpha'},{'id':'b'*16,'name':'Beta','repo':'b/beta'},{'id':'c'*16,'name':'Local','local_bundle':'example'}],'test',lambda:self.clock)
 def identity(self):
  c=self.v.new_cookie();s,_=self.v.status(c,'192.0.2.1');return c,s['csrf']
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
  self.assertEqual(self.store.sql("select count(*) from pg_class where relname in ('skillwire_directions','skillwire_direction_budget','skillwire_direction_totals') and relrowsecurity;"),'3')
  c,t=self.identity();self.v.cast(c,'192.0.2.1','a'*16,t,1);self.assertEqual(self.store.sql('select count(*) from public.skillwire_daily_votes;'),'0')

 def test_mint_quota_and_legacy_daily_cookie_are_not_direction_identity(self):
  from voting import Voting
  for i in range(3):
   s,_=self.v.status(None,'192.0.2.1');self.v.cast(None,'192.0.2.1','a'*16,s['csrf'],1,request_key=('%048x'%i))
  s,_=self.v.status(None,'192.0.2.1')
  with self.assertRaises(VoteError) as e:self.v.cast(None,'192.0.2.1','b'*16,s['csrf'],1,request_key='f'*48)
  self.assertEqual(e.exception.status,429)
  legacy=Voting('test-only-secret-32-bytes-minimum!!',self.store,self.v.catalog,'test',lambda:self.clock)
  old,c=legacy.status(None,'192.0.2.9')
  with self.assertRaises(VoteError):self.v.cast(c,'192.0.2.9','a'*16,old['csrf'],1)
 def test_stuffing_with_preissued_cookies_is_capped_at_three_per_network_per_skill(self):
  credentials=[]
  for i in range(20):
   c=self.v.new_cookie();s,_=self.v.status(c,'198.51.100.'+str(i+1));credentials.append((c,s['csrf']))
  accepted=0
  for i,(c,t) in enumerate(credentials):
   try:self.v.cast(c,'192.0.2.'+str(1+i%2),'a'*16,t,1);accepted+=1
   except VoteError as e:self.assertEqual(e.status,429)
  self.assertEqual(accepted,6)
  self.assertEqual(self.v.status(credentials[0][0],'192.0.2.1')[0]['counts']['a'*16]['up'],6)
 def test_aggregate_cache_stays_exact_through_undo_and_switch(self):
  c,t=self.identity()
  for skill,value in [('a'*16,1),('b'*16,-1),('a'*16,-1),('b'*16,0),('a'*16,0)]:
   self.v.cast(c,'192.0.2.1',skill,t,value)
   actual=self.v.status(c,'192.0.2.1')[0]
   raw=self.store.sql("select count(*) from public.skillwire_directions;")
   self.assertEqual(actual['total'],int(raw))
  self.assertEqual(actual['counts'],{})
  definition=self.store.sql("select pg_get_functiondef('public.skillwire_direction_status(text,text)'::regprocedure);")
  self.assertNotIn('count(*)',definition.lower());self.assertIn('skillwire_direction_totals',definition)

 def test_cookie_mint_is_atomic_under_concurrency(self):
  def mint(_):
   try:
    s,unused_cookie=self.v.status(None,'192.0.2.1');self.v.cast(None,'192.0.2.1','a'*16,s['csrf'],1,request_key=('%048x'%_));return True
   except VoteError as e:self.assertEqual(e.status,429);return False
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:accepted=list(pool.map(mint,range(12)))
  self.assertEqual(sum(accepted),3)

 def test_get_never_mints_or_exhausts_counts_for_fourth_visitor(self):
  for _ in range(12):
   s,c=self.v.status(None,'192.0.2.1');self.assertIsNone(c);self.assertEqual(s['mine'],{})
  self.assertEqual(self.store.sql("select count(*) from public.skillwire_direction_budget where scope='mint';"),'0')
 def test_ipv6_48_and_ipv4_mapped_normalisation(self):
  self.assertEqual(self.v.network_key('::ffff:192.0.2.1','x'),self.v.network_key('192.0.2.1','x'))
  keys={self.v.network_key('2001:db8:abcd:'+format(i,'x')+'::1','x') for i in range(30)};self.assertEqual(len(keys),1)
  self.assertNotEqual(self.v.network_key('2001:db8:abce::1','x'),next(iter(keys)))
 def test_network_skill_window_expires_without_removing_old_preferences(self):
  for i in range(3):
   c=self.v.new_cookie();s,_=self.v.status(c,'192.0.2.1');self.v.cast(c,'192.0.2.1','a'*16,s['csrf'],1)
  c=self.v.new_cookie();s,_=self.v.status(c,'192.0.2.1')
  with self.assertRaises(VoteError):self.v.cast(c,'192.0.2.1','a'*16,s['csrf'],1)
  self.store.sql("update public.skillwire_directions set network_at=now()-interval '25 hours';")
  self.v.cast(c,'192.0.2.1','a'*16,s['csrf'],1);self.assertEqual(self.v.status(c,'192.0.2.1')[0]['total'],4)
 def test_first_post_retries_share_identity_and_mint_once(self):
  s,_=self.v.status(None,'192.0.2.1');key='a'*48
  first,c=self.v.cast(None,'192.0.2.1','a'*16,s['csrf'],1,request_key=key)
  again,c2=self.v.cast(None,'192.0.2.1','a'*16,s['csrf'],1,request_key=key)
  self.assertEqual(c,c2);self.assertEqual(again['total'],1)
  self.assertEqual(self.store.sql("select used from public.skillwire_direction_budget where scope='mint';"),'1')

class DirectionHTTP(DirectionVotes):
 def setUp(self):
  super().setUp()
  import threading
  from unittest.mock import patch
  from http.server import ThreadingHTTPServer
  from api.index import handler
  self.config=patch('voting.configured_directions',return_value=self.v);self.config.start();self.server=ThreadingHTTPServer(('127.0.0.1',0),handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.origin='http://127.0.0.1:'+str(self.server.server_port);self.origins=patch.dict('os.environ',{'SKILLWIRE_VOTE_ORIGINS':self.origin});self.origins.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.origins.stop();self.config.stop()
 def request(self,method,body=None,cookie=None,origin=None,extra_headers=None):
  import http.client,json
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);headers={'Content-Type':'application/json'}
  if cookie:headers['Cookie']=cookie
  if origin:headers['Origin']=origin
  headers.update(extra_headers or {})
  c.request(method,'/api/directions' if method=='GET' else '/api/direction',json.dumps(body) if body is not None else None,headers);r=c.getresponse();data=json.loads(r.read());h=dict(r.getheaders());code=r.status;c.close();return code,h,data
 def test_real_http_cookie_origin_and_readback(self):
  code,h,s=self.request('GET');self.assertEqual(code,200);self.assertNotIn('Set-Cookie',h)
  body={'skill_id':'a'*16,'csrf':s['csrf'],'value':1,'request_key':'a'*48}
  self.assertEqual(self.request('POST',body)[0],403)
  self.assertEqual(self.request('POST',body,origin='https://evil.invalid')[0],403)
  code,h,s=self.request('POST',body,origin=self.origin);self.assertEqual(code,201);self.assertTrue(h['Set-Cookie'].startswith('sw_direction='));self.assertIn('HttpOnly; Secure; SameSite=Strict',h['Set-Cookie']);c=h['Set-Cookie'].split(';')[0]
  self.assertEqual(self.request('GET',cookie=c)[2]['mine']['a'*16],1)
  body.update(csrf=s['csrf'],value=0);self.assertEqual(self.request('POST',body,c,self.origin)[2]['mine'],{})
 def test_unavailable_store_is_not_fake_zero_or_acceptance(self):
  from unittest.mock import patch
  with patch.object(self.store,'rpc',side_effect=VoteError(503,'Community voting is temporarily unavailable.')):
   self.assertEqual(self.request('GET')[0],503)

 def test_forwarded_headers_cannot_change_loopback_identity(self):
  from unittest.mock import patch
  with patch.dict('os.environ',{'VERCEL':''}):
   codes=[]
   for i in range(4):
    headers={'x-vercel-forwarded-for':'192.0.2.'+str(i+1),'x-forwarded-for':'198.51.100.'+str(i+1)}
    code,h,s=self.request('GET',extra_headers=headers);self.assertEqual(code,200)
    codes.append(self.request('POST',{'skill_id':'a'*16,'csrf':s['csrf'],'value':1,'request_key':'%048x'%(100+i)},origin=self.origin,extra_headers=headers)[0])
   self.assertEqual(codes,[201,201,201,429])
  # This proves loopback ignores spoofed headers, not that Vercel sanitizes them.
 def test_vercel_mode_missing_trusted_header_fails_closed(self):
  from unittest.mock import patch
  with patch.dict('os.environ',{'VERCEL':'1'}):
   code,h,s=self.request('GET');self.assertEqual(code,200);self.assertIsNone(s['csrf']);self.assertNotIn('Set-Cookie',h)
   self.assertEqual(self.request('POST',{'skill_id':'a'*16,'csrf':None,'value':1,'request_key':'a'*48},origin=self.origin)[0],403)

 def test_fourth_visitor_reads_counts_even_after_three_first_posts(self):
  for i in range(3):
   code,h,s=self.request('GET');self.assertNotIn('Set-Cookie',h)
   code,h,body=self.request('POST',{'skill_id':'a'*16,'csrf':s['csrf'],'value':1,'request_key':'%048x'%i},origin=self.origin);self.assertEqual(code,201)
  code,h,s=self.request('GET');self.assertEqual(code,200);self.assertNotIn('Set-Cookie',h);self.assertEqual(s['counts']['a'*16]['up'],3)
  self.assertEqual(self.request('POST',{'skill_id':'a'*16,'csrf':s['csrf'],'value':1,'request_key':'f'*48},origin=self.origin)[0],429)
  self.assertEqual(self.request('GET')[0],200)
