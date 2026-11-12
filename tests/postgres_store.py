"""Owned temporary actual Postgres; invokes the exact deployed SQL RPCs."""
import json,os,secrets,subprocess,tempfile
from pathlib import Path
BIN=Path(os.environ.get('PG_BINDIR','/opt/homebrew/opt/postgresql@18/bin'))
class Postgres:
 def __init__(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.data=self.root/'db';self.port=str(secrets.randbelow(10000)+50000)
  subprocess.run([str(BIN/'initdb'),'-D',str(self.data),'--no-locale','--encoding=UTF8','--auth=trust'],check=True,capture_output=True)
  self.start()
  self.sql('create role anon;create role authenticated;create role service_role bypassrls;')
  self.sql((Path(__file__).resolve().parents[1]/'migrations/20261029_daily_votes.sql').read_text())
 def start(self):subprocess.run([str(BIN/'pg_ctl'),'-D',str(self.data),'-l',str(self.root/'server.log'),'-o',"-F -k "+str(self.root)+" -h '' -p "+self.port+' -c shared_buffers=16MB -c max_connections=20','-w','start'],check=True,capture_output=True)
 def stop(self):subprocess.run([str(BIN/'pg_ctl'),'-D',str(self.data),'-m','fast','-w','stop'],check=True,capture_output=True)
 def close(self):self.stop();self.tmp.cleanup()
 def sql(self,text):
  r=subprocess.run([str(BIN/'psql'),'-h',str(self.root),'-p',self.port,'-d','postgres','-X','-qAt','-v','ON_ERROR_STOP=1'],input=text,capture_output=True,text=True,check=True);return r.stdout.strip()
 def rpc(self,name,**payload):
  def value(v):return "'"+(json.dumps(v) if isinstance(v,dict) else str(v)).replace("'","''")+"'"+('::jsonb' if isinstance(v,dict) else '')
  args=','.join(k+' => '+value(v) for k,v in payload.items());raw=self.sql('set role service_role;select to_jsonb(public.skillwire_'+name+'('+args+'));');return json.loads(raw) if raw else None
 def snapshot(self,ns,day,person):return self.rpc('vote_status',p_namespace=ns,p_day=day,p_voter_hash=person)
 def cast(self,ns,day,person,network,skill):return self.rpc('cast_vote',p_namespace=ns,p_day=day,p_voter_hash=person,p_network_hash=network,p_skill=skill)
 def x_get(self,ns):return self.rpc('x_poll_get',p_namespace=ns)
 def x_claim(self,ns,day):return self.rpc('x_poll_claim',p_namespace=ns,p_day=day)
 def x_set(self,ns,result):return self.rpc('x_poll_set',p_namespace=ns,p_result=result)
 def keepalive(self):return self.rpc('keepalive')
 def clear(self):self.sql('truncate public.skillwire_vote_counts,public.skillwire_daily_votes,public.skillwire_daily_networks,public.skillwire_x_poll_cache,public.skillwire_x_poll_attempts;')
