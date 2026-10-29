"""Shared atomic daily votes. No raw IPs, login, executable skills or model calls."""
from __future__ import annotations
import datetime as dt,hashlib,hmac,ipaddress,json,os,re,secrets,urllib.request
class VoteError(Exception):
 def __init__(self,status,message):self.status=status;super().__init__(message)
class SupabaseStore:
 def __init__(self,url,key):
  if not re.fullmatch(r'https://[a-z0-9]+\.supabase\.co',url) or not key:raise VoteError(503,'Community voting is temporarily unavailable.')
  self.url=url;self.key=key
 def rpc(self,name,**payload):
  req=urllib.request.Request(self.url+'/rest/v1/rpc/skillwire_'+name,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+self.key,'apikey':self.key,'Content-Type':'application/json'},method='POST')
  try:
   with urllib.request.urlopen(req,timeout=8) as r:raw=r.read()
   return json.loads(raw) if raw else None
  except Exception:raise VoteError(503,'Community voting is temporarily unavailable.') from None
 def snapshot(self,ns,day,person):return self.rpc('vote_status',p_namespace=ns,p_day=day,p_voter_hash=person)
 def cast(self,ns,day,person,network,skill):return self.rpc('cast_vote',p_namespace=ns,p_day=day,p_voter_hash=person,p_network_hash=network,p_skill=skill)
 def x_get(self,ns):return self.rpc('x_poll_get',p_namespace=ns)
 def x_claim(self,ns,day):return self.rpc('x_poll_claim',p_namespace=ns,p_day=day)
 def x_set(self,ns,result):return self.rpc('x_poll_set',p_namespace=ns,p_result=result)
 def keepalive(self):return self.rpc('keepalive')
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
 def person_key(self,ident,day):return self.mac('person:'+day+':'+ident)
 def network_key(self,ip,day):
  try:
   address=ipaddress.ip_address(ip);network=str(ipaddress.ip_network(str(address)+'/64',strict=False)) if address.version==6 else str(address)
  except ValueError:raise VoteError(503,'Network identity unavailable. Please try again.') from None
  return self.mac('network:'+day+':'+network)
 def status(self,cookie,ip):
  now,day,reset=self.clock();ident=self.identity(cookie)
  if not ident:ident=secrets.token_hex(24);cookie=ident+'.'+self.mac('cookie:'+ident)
  snapshot=self.store.snapshot(self.ns,day,self.person_key(ident,day))
  counts={k:int(v) for k,v in snapshot['counts'].items() if k in self.byid}
  ranked=sorted(counts,key=lambda k:(-counts[k],self.byid[k]['name'].lower(),k))[:50]
  ranking=[{k:self.byid[i].get(k,'') for k in ('id','name','repo')}|{'votes':counts[i]} for i in ranked]
  return {'day':day,'resets_at':reset.isoformat(),'selected_today':snapshot['selected_today'],'csrf':self.mac('csrf:'+ident+':'+day),'counts':counts,'ranking':ranking,'total':sum(counts.values()),'updated_at':now.isoformat(),'rule':'One vote per browser per UTC day. Shared-network limits also apply; repeat voting remains possible.'},cookie
 def cast(self,cookie,ip,skill_id,csrf,origin_valid=True,honeypot=''):
  now,day,reset=self.clock();ident=self.identity(cookie)
  if not origin_valid or honeypot or not ident or not isinstance(csrf,str) or not hmac.compare_digest(csrf,self.mac('csrf:'+ident+':'+day)):raise VoteError(403,'Refresh this page before voting.')
  if skill_id not in self.byid or self.byid[skill_id].get('local_bundle'):raise VoteError(400,'Choose a published skill.')
  result=self.store.cast(self.ns,day,self.person_key(ident,day),self.network_key(ip,day),skill_id)
  if result==0:raise VoteError(409,'You have used today’s vote. Come back after midnight UTC.')
  if result==-1:raise VoteError(429,'This network has reached today’s limit. Please try tomorrow.')
  if result!=1:raise VoteError(503,'Vote was not confirmed. Refresh before trying again.')
  return {'accepted':True,'day':day,'skill_id':skill_id}
def configured():
 import public_runtime
 namespace='production-v1' if os.environ.get('VERCEL_ENV')=='production' else 'preview-'+os.environ.get('VERCEL_URL','local').split('.')[0]
 return Voting(os.environ.get('SKILLWIRE_VOTE_SECRET',''),SupabaseStore(os.environ.get('SUPABASE_URL',''),os.environ.get('SUPABASE_SERVICE_ROLE_KEY','')),public_runtime.catalog()['skills'],namespace)
