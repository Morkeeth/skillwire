"""Daily X poll mirror. OFF by default; no credential discovery or posting."""
import datetime as dt,hmac,json,os,re,urllib.request
from voting import VoteError

def public_status(store,ns):
 if os.environ.get('SKILLWIRE_X_POLL_ENABLED')!='1':return {'enabled':False,'message':'X poll not connected.'}
 raw=store.command('GET',ns+':x-poll')
 return json.loads(raw) if raw else {'enabled':True,'message':'Waiting for the first X poll read.'}
def sync(auth,now=lambda:dt.datetime.now(dt.timezone.utc),service=None,fetch=None):
 if os.environ.get('SKILLWIRE_X_POLL_ENABLED')!='1':return {'enabled':False,'fetched':False}
 secret=os.environ.get('CRON_SECRET','')
 if not secret or not hmac.compare_digest(auth,'Bearer '+secret):raise VoteError(401,'Unauthorized job.')
 token=os.environ.get('X_API_BEARER_TOKEN','');post=os.environ.get('SKILLWIRE_X_POLL_POST_ID','')
 if not token or not re.fullmatch(r'[0-9]{1,25}',post):raise VoteError(503,'X poll access is not configured.')
 if service is None:
  import voting
  service=voting.configured()
 clock=now().astimezone(dt.timezone.utc);day=clock.date().isoformat()
 # One attempt per UTC day, even if a response is lost. No billable retry loop.
 if not service.store.command('SET',service.ns+':x-attempt:'+day,'1','NX','EX',172800):return {'enabled':True,'fetched':False,'already_attempted_today':True}
 url='https://api.x.com/2/tweets/'+post+'?expansions=attachments.poll_ids&poll.fields=options,voting_status,end_datetime,duration_minutes'
 try:
  if fetch:data=fetch(url,token)
  else:
   req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
   with urllib.request.urlopen(req,timeout=10) as r:data=json.load(r)
  if data.get('data',{}).get('id')!=post:raise ValueError('Wrong post')
  ids=data['data']['attachments']['poll_ids'];polls=data['includes']['polls'];poll=next(p for p in polls if p['id'] in ids)
  if not 2<=len(poll['options'])<=4:raise ValueError('Unexpected poll')
  options=[]
  for p in poll['options']:
   if not isinstance(p['label'],str) or len(p['label'])>100 or type(p['votes']) is not int or p['votes']<0:raise ValueError('Invalid result')
   options.append({'label':p['label'],'votes':p['votes']})
  result={'enabled':True,'post_url':'https://x.com/i/status/'+post,'options':options,'voting_status':poll['voting_status'],'ends_at':poll.get('end_datetime'),'fetched_at':clock.isoformat(),'source':'X community poll, separate from on-site votes.'}
  service.store.command('SET',service.ns+':x-poll',json.dumps(result));return {'enabled':True,'fetched':True}
 except Exception:raise VoteError(502,'X poll could not refresh. The previous dated result is retained.') from None
