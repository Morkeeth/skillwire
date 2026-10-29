"""Shared atomic daily votes. No raw IPs, login, executable skills or model calls."""
from __future__ import annotations
import datetime as dt,hashlib,hmac,ipaddress,json,os,re,secrets,urllib.request
class VoteError(Exception):
 def __init__(self,status,message):self.status=status;super().__init__(message)
class RedisREST:
 def __init__(self,url,token):
  if not url.startswith('https://') or not token:raise VoteError(503,'Community voting is temporarily unavailable.')
  self.url=url.rstrip('/');self.token=token
 def command(self,*args):
  req=urllib.request.Request(self.url,data=json.dumps(list(args)).encode(),headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'},method='POST')
  try:
   with urllib.request.urlopen(req,timeout=8) as r:d=json.load(r)
   if d.get('error'):raise ValueError('Store command failed')
   return d['result']
  except Exception:raise VoteError(503,'Community voting is temporarily unavailable.') from None
# All checks precede writes. Both identity and network budgets are claimed atomically.
CAST='''
if redis.call('EXISTS',KEYS[1]) == 1 then return 0 end
local used=tonumber(redis.call('GET',KEYS[2]) or '0')
if used >= tonumber(ARGV[3]) then return -1 end
redis.call('SET',KEYS[1],ARGV[1],'EX',ARGV[2])
redis.call('INCR',KEYS[2]); redis.call('EXPIRE',KEYS[2],ARGV[2])
redis.call('ZINCRBY',KEYS[3],1,ARGV[1]); redis.call('INCR',KEYS[4])
return 1
'''
class Voting:
 def __init__(self,secret,store,catalog,namespace,now=lambda:dt.datetime.now(dt.timezone.utc)):
  if len(secret)<32 or not re.fullmatch(r'[a-zA-Z0-9:_-]{1,100}',namespace):raise VoteError(503,'Community voting is temporarily unavailable.')
  self.secret=secret.encode();self.store=store;self.catalog=catalog;self.byid={s['id']:s for s in catalog};self.ns='skillwire:'+namespace;self.now=now
 def mac(self,text):return hmac.new(self.secret,text.encode(),hashlib.sha256).hexdigest()
 def identity(self,cookie):
  if not isinstance(cookie,str) or not re.fullmatch(r'[a-f0-9]{48}\.[a-f0-9]{64}',cookie):return None
  ident,sig=cookie.split('.')
  return ident if hmac.compare_digest(sig,self.mac('cookie:'+ident)) else None
 def clock(self):
  now=self.now().astimezone(dt.timezone.utc);day=now.date().isoformat();reset=dt.datetime.combine(now.date()+dt.timedelta(days=1),dt.time(),tzinfo=dt.timezone.utc)
  return now,day,reset
 def person_key(self,ident,day):return self.ns+':person:'+day+':'+self.mac('person:'+day+':'+ident)
 def network_key(self,ip,day):
  try:
   address=ipaddress.ip_address(ip);network=str(ipaddress.ip_network(str(address)+'/64',strict=False)) if address.version==6 else str(address)
  except ValueError:raise VoteError(503,'Network identity unavailable. Please try again.') from None
  return self.ns+':network:'+day+':'+self.mac('network:'+day+':'+network)
 def status(self,cookie,ip):
  now,day,reset=self.clock();ident=self.identity(cookie)
  if not ident:ident=secrets.token_hex(24);cookie=ident+'.'+self.mac('cookie:'+ident)
  pairs=self.store.command('ZREVRANGE',self.ns+':counts',0,-1,'WITHSCORES') or []
  if pairs and isinstance(pairs[0],list):pairs=[v for pair in pairs for v in pair]
  counts={pairs[i]:int(float(pairs[i+1])) for i in range(0,len(pairs),2) if pairs[i] in self.byid}
  ranked=sorted(counts,key=lambda k:(-counts[k],self.byid[k]['name'].lower(),k))[:50]
  ranking=[{k:self.byid[i].get(k,'') for k in ('id','name','repo')}|{'votes':counts[i]} for i in ranked]
  return {'day':day,'resets_at':reset.isoformat(),'selected_today':self.store.command('GET',self.person_key(ident,day)),'csrf':self.mac('csrf:'+ident+':'+day),'counts':counts,'ranking':ranking,'total':sum(counts.values()),'updated_at':now.isoformat(),'rule':'One vote per browser per UTC day. Shared-network limits also apply; repeat voting remains possible.'},cookie
 def cast(self,cookie,ip,skill_id,csrf,origin_valid=True,honeypot=''):
  now,day,reset=self.clock();ident=self.identity(cookie)
  if not origin_valid or honeypot or not ident or not isinstance(csrf,str) or not hmac.compare_digest(csrf,self.mac('csrf:'+ident+':'+day)):raise VoteError(403,'Refresh this page before voting.')
  if skill_id not in self.byid or self.byid[skill_id].get('local_bundle'):raise VoteError(400,'Choose a published skill.')
  ttl=max(1,int((reset-now).total_seconds())+86400)
  result=self.store.command('EVAL',CAST,4,self.person_key(ident,day),self.network_key(ip,day),self.ns+':counts',self.ns+':total',skill_id,ttl,3)
  if result==0:raise VoteError(409,'You have used today’s vote. Come back after midnight UTC.')
  if result==-1:raise VoteError(429,'This network has reached today’s limit. Please try tomorrow.')
  if result!=1:raise VoteError(503,'Vote was not confirmed. Refresh before trying again.')
  return {'accepted':True,'day':day,'skill_id':skill_id}
def configured():
 import public_runtime
 namespace='production-v1' if os.environ.get('VERCEL_ENV')=='production' else 'preview-'+os.environ.get('VERCEL_URL','local').split('.')[0]
 return Voting(os.environ.get('SKILLWIRE_VOTE_SECRET',''),RedisREST(os.environ.get('UPSTASH_REDIS_REST_URL',''),os.environ.get('UPSTASH_REDIS_REST_TOKEN','')),public_runtime.catalog()['skills'],namespace)
