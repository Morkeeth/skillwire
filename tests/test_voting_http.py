import http.client,json,threading,unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from api.index import handler
from test_voting import DailyVotes
class VoteHTTP(DailyVotes):
 def setUp(self):
  super().setUp();self.patch=patch('voting.configured',return_value=self.v);self.patch.start();self.server=ThreadingHTTPServer(('127.0.0.1',0),handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.port=self.server.server_port
  self.origins=patch.dict('os.environ',{'SKILLWIRE_VOTE_ORIGINS':'http://127.0.0.1:'+str(self.port)});self.origins.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.patch.stop();self.origins.stop()
 def request(self,method,path,body=None,headers=None):
  c=http.client.HTTPConnection('127.0.0.1',self.port);c.request(method,path,json.dumps(body) if body else None,headers or {});r=c.getresponse();data=r.read();result=(r.status,dict(r.getheaders()),json.loads(data));c.close();return result
 def test_cookie_csrf_real_http_and_duplicate_readback(self):
  status,h,s=self.request('GET','/api/votes');self.assertEqual(status,200);self.assertIn('HttpOnly',h['Set-Cookie']);cookie=h['Set-Cookie'].split(';')[0]
  headers={'Cookie':cookie,'Origin':'http://127.0.0.1:'+str(self.port),'Content-Type':'application/json'};body={'skill_id':'a'*16,'csrf':s['csrf'],'website':''}
  self.assertEqual(self.request('POST','/api/vote',body,headers)[0],201)
  self.assertEqual(self.request('POST','/api/vote',body,headers)[0],409)
  result=self.request('GET','/api/votes',headers={'Cookie':cookie})[2];self.assertEqual(result['total'],1);self.assertEqual(result['selected_today'],'a'*16)
  headers['Origin']='https://evil.invalid';self.assertEqual(self.request('POST','/api/vote',body,headers)[0],403)
