"""Resume one pinned source in bounded metadata/body chunks; no catalog mutation or archives.

Nonrecursive Git trees avoid an oversized recursive response. Only once the complete
old/new trees and changed bodies are present can a later offline integration consume
the stage. API data and skill text are never instructions or executable code.
"""
import argparse,datetime,hashlib,json,os,re,shutil,signal,subprocess,time,urllib.request
from pathlib import Path
from incremental_refresh import Budget,SKILL

class AuthBudget(Budget):
    def __init__(self,*args):
        super().__init__(*args)
        token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not token:
            # Existing authenticated CLI credential only; never print or persist it.
            p=subprocess.run(['gh','auth','token'],capture_output=True,text=True,timeout=min(10,self.remaining()))
            if p.returncode:raise RuntimeError('existing GitHub authentication unavailable')
            token=p.stdout.strip()
        self.token=token
    def get(self,url,cap=1_000_000):
        available=min(cap,self.limit-self.used)
        if available<=0:raise ValueError('chunk response-byte budget exhausted')
        headers={'User-Agent':'skillwire-pinned-source-stage','Accept':'application/vnd.github+json'}
        if url.startswith('https://api.github.com/'):
            headers['Authorization']='Bearer '+self.token
        req=urllib.request.Request(url,headers=headers);chunks=[]
        with urllib.request.urlopen(req,timeout=min(15,self.remaining())) as response:
            while available:
                response.fp.raw._sock.settimeout(min(15,self.remaining()))
                part=response.read1(min(64000,available));self.used+=len(part);available-=len(part)
                if not part:return b''.join(chunks)
                chunks.append(part)
                if response.length==0:return b''.join(chunks)
        raise ValueError('chunk byte limit reached; incomplete response discarded')

def save(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=1));temp.replace(path)

def blob_sha(body):return hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()

def init_state(catalog,repo,budget):
    source=next(s for s in catalog['sources'] if s['repo']==repo)
    meta=budget.api('repos/'+repo);canonical=meta['full_name']
    if meta.get('private'):raise ValueError('catalog staging accepts public sources only')
    head=budget.api('repos/'+canonical+'/commits/'+meta['default_branch'])['sha']
    for sha in (source['revision'],head):
        if not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('invalid pinned revision')
    return {'schema':'skillwire-source-stage/1','key':repo,'canonical':canonical,'old_revision':source['revision'],'new_revision':head,'stars':meta['stargazers_count'],'license':(meta.get('license') or {}).get('spdx_id','Unknown'),'created':datetime.datetime.now(datetime.timezone.utc).isoformat(),'queues':{'old':[[source['revision'],'']],'new':[[head,'']]},'visited':{'old':[],'new':[]},'files':{'old':{},'new':{}},'trees':{'old':[],'new':[]},'body_cache':{},'ready':False}

def stage(state,folder,budget):
    state.setdefault('unsupported',{'old':[],'new':[]})
    # One bounded API response at a time, committing completed nodes only.
    for side in ('old','new'):
        while state['queues'][side]:
            sha,prefix=state['queues'][side][0]
            node=budget.api('repos/'+state['canonical']+'/git/trees/'+sha)
            if node.get('truncated'):raise ValueError('nonrecursive node truncated; source remains incomplete')
            children=[];files={};items=[]
            for item in node['tree']:
                path=prefix+item['path']
                if item['type']=='tree':children.append([item['sha'],path+'/'])
                elif item['type']=='blob':
                    full=dict(item,path=path);items.append(full)
                    if SKILL(path) and item.get('mode')!='120000':
                        if item.get('size',0)>1_000_000:
                            state['unsupported'][side].append({'path':path,'size':item['size']})
                        else:
                            files[path]={'sha':item['sha'],'size':item.get('size',0)}
            state['queues'][side].pop(0);state['queues'][side].extend(children)
            state['files'][side].update(files);state['trees'][side].extend(items);state['visited'][side].append([sha,prefix])
            save(folder/'state.json',state)
    if any(state['unsupported'].values()):
        state['ready']=False;save(folder/'state.json',state)
        raise ValueError('oversized SKILL.md paths present; source completeness is not established')
    old,new=state['files']['old'],state['files']['new']
    state['fetch']=sorted(p for p in new if p not in old or new[p]['sha']!=old[p]['sha'])
    state['drop']=sorted(p for p in old if p not in new)
    save(folder/'state.json',state)
    for path in state['fetch']:
        if path in state['body_cache']:
            body=(folder/state['body_cache'][path]).read_bytes()
            if blob_sha(body)==new[path]['sha']:continue
            raise ValueError('existing staged body drift')
        size=new[path]['size']
        if size>budget.limit-budget.used:raise ValueError('next complete body exceeds remaining chunk budget')
        body=budget.get('https://raw.githubusercontent.com/'+state['canonical']+'/'+state['new_revision']+'/'+path,cap=size or 1)
        if len(body)!=size or blob_sha(body)!=new[path]['sha']:raise ValueError('pinned size/hash mismatch')
        name=hashlib.sha256(body).hexdigest()+'.md';cache=folder/'bodies';cache.mkdir(exist_ok=True)
        target=cache/name
        if target.exists():
            if target.read_bytes()!=body:raise ValueError('content-addressed cache drift')
        else:
            with target.open('xb') as f:f.write(body)
        state['body_cache'][path]='bodies/'+name;save(folder/'state.json',state)
    state['ready']=True;save(folder/'state.json',state)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--repo',required=True);p.add_argument('--stage',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--max-bytes',type=int,required=True);p.add_argument('--max-seconds',type=int,required=True);p.add_argument('--disk-floor-gib',type=float,default=6);x=p.parse_args(argv)
    if not 0<x.max_bytes<=2_000_000 or not 0<x.max_seconds<=300 or x.disk_floor_gib<6:p.error('bounds require <=2Mbytes/300sec and >=6GiB')
    if x.receipt.exists() or x.receipt.resolve()==x.catalog.resolve() or x.stage.resolve()==x.catalog.resolve():p.error('new independent receipt/stage required')
    for path in (x.catalog,x.stage,x.receipt.parent):
        while not path.exists():path=path.parent
        if shutil.disk_usage(path).free<x.disk_floor_gib*1024**3:raise SystemExit('disk floor not met on input or output volume')
    x.stage.mkdir(parents=True,exist_ok=True);x.receipt.parent.mkdir(parents=True,exist_ok=True)
    lock=x.stage/'RUNNING.lock';lockfd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(lockfd)
    # SIGKILL leaves the lock intentionally; root must verify no owner before manual removal.
    lock.write_text(json.dumps({'pid':os.getpid(),'created':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
    start=time.monotonic();budget=None;state=None;receipt={'repo':x.repo,'started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'max_bytes':x.max_bytes,'max_seconds':x.max_seconds,'thread_count':1,'catalog_mutated':False}
    def alarm(*_):raise TimeoutError('chunk hard deadline reached')
    prior=signal.signal(signal.SIGALRM,alarm);signal.alarm(x.max_seconds)
    try:
        budget=AuthBudget(x.max_bytes,x.max_seconds)
        state_path=x.stage/'state.json'
        if state_path.exists():
            state=json.loads(state_path.read_text());assert state['key']==x.repo
            current=next(s for s in json.loads(x.catalog.read_text())['sources'] if s['repo']==x.repo)
            if current['revision']!=state['old_revision']:raise ValueError('input revision changed; do not rebase in-progress stage')
        else:
            state=init_state(json.loads(x.catalog.read_text()),x.repo,budget);save(state_path,state)
        stage(state,x.stage,budget);receipt['status']='READY_FOR_OFFLINE_INTEGRATION'
    except Exception as exc:
        receipt.update(status='INCOMPLETE_CATALOG_UNCHANGED',error=type(exc).__name__+': '+str(exc))
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,prior)
        receipt.update(seconds=round(time.monotonic()-start,3),response_bytes=budget.used if budget else 0,finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
        if state:receipt.update(old_revision=state['old_revision'],new_revision=state['new_revision'],canonical=state['canonical'],pending_tree_nodes=sum(map(len,state['queues'].values())),changed_files=len(state.get('fetch',[])),cached_bodies=len(state['body_cache']),ready=state['ready'])
        with x.receipt.open('x') as f:json.dump(receipt,f,indent=2)
        lock.unlink();print(json.dumps(receipt))
    return 0 if receipt['status']=='READY_FOR_OFFLINE_INTEGRATION' else 2
if __name__=='__main__':raise SystemExit(main())
