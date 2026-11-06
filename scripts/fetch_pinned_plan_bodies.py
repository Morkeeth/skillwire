"""Fetch only hash-pinned bodies from an already saved metadata plan. No API metadata calls.

Writes verified content-addressed scratch files and one receipt. Never updates a
catalog or runs any downloaded code. A partial run remains explicitly incomplete.
"""
import argparse,datetime,hashlib,json,re,signal,shutil,time
from pathlib import Path,PurePosixPath
from urllib.parse import quote
from incremental_refresh import Budget

def verify_body(body,expected):
    if len(body)!=expected['bytes']:raise ValueError('pinned body size mismatch')
    blob=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
    if blob!=expected['git_blob_sha']:raise ValueError('pinned Git blob hash mismatch')
    return hashlib.sha256(body).hexdigest()

def main(argv=None):
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--plan',type=Path,required=True);a.add_argument('--plan-sha256',required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--max-bytes',type=int,required=True);a.add_argument('--max-seconds',type=int,required=True);a.add_argument('--disk-floor-gib',type=float,default=6);x=a.parse_args(argv)
    if not 0<x.max_bytes<=1_000_000 or not 0<x.max_seconds<=180 or x.disk_floor_gib<6:a.error('bounded byte/time/disk limits required')
    if x.output.exists() or x.output.resolve()==x.plan.resolve():a.error('new independent output directory required')
    raw=x.plan.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=x.plan_sha256:raise ValueError('frozen metadata plan drift')
    plan=json.loads(raw);rows=plan['sources'];tasks=[]
    if len(rows)>9 or len({r['key'] for r in rows})!=len(rows):raise ValueError('plan must contain <=9 unique sources')
    for r in rows:
        if not re.fullmatch('[0-9a-f]{40}',r['new_revision']) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',r['canonical']) or r.get('tree',{}).get('truncated'):raise ValueError('unpinned or incomplete metadata')
        for p in r.get('fetch',[]):
            if PurePosixPath(p).is_absolute() or '..' in PurePosixPath(p).parts or not (p=='SKILL.md' or p.endswith('/SKILL.md')):
                raise ValueError('invalid skill body path')
            size=r['fetch_sizes'][p]
            if not 0<=size<=1_000_000:raise ValueError('unsupported body size')
            tasks.append({'repo':r['key'],'canonical':r['canonical'],'revision':r['new_revision'],'path':p,'bytes':size,'git_blob_sha':r['fetch_shas'][p]})
    if sum(t['bytes'] for t in tasks)>x.max_bytes:raise ValueError('planned bodies exceed this new job budget')
    volume=x.output.resolve().parent
    while not volume.exists():volume=volume.parent
    if shutil.disk_usage(volume).free<x.disk_floor_gib*1024**3:raise SystemExit('output disk floor not met')
    x.output.mkdir(parents=True,exist_ok=False);(x.output/'bodies').mkdir();start=time.monotonic();budget=Budget(x.max_bytes,x.max_seconds)
    receipt={'schema':'skillwire-pinned-body-stage/1','started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':x.plan_sha256,'metadata_requests':0,'metadata_snapshot_at':plan['planned_at'],'checked_heads':[{'repo':r['key'],'revision':r['new_revision']} for r in rows],'planned_files':len(tasks),'planned_raw_bytes':sum(t['bytes'] for t in tasks),'bodies':[],'errors':[],'catalog_mutated':False,'threads':1}
    def alarm(*_):raise TimeoutError('body-stage hard wall deadline reached')
    old=signal.signal(signal.SIGALRM,alarm);signal.alarm(x.max_seconds)
    try:
        for task in tasks:
            # A bounded cache read can be consumed only after its complete hash is verified.
            if task['bytes']==0:
                # A size-zero blob has exactly one possible body; its pinned Git hash
                # still must verify. This is materialization, not a network fetch.
                body=b''
            else:
                body=budget.get('https://raw.githubusercontent.com/'+task['canonical']+'/'+task['revision']+'/'+quote(task['path'],safe='/'),cap=task['bytes'])
            digest=verify_body(body,task);cache='bodies/'+digest+'.md';path=x.output/cache
            if path.exists():
                if path.read_bytes()!=body:raise ValueError('content-addressed scratch drift')
            else:
                with path.open('xb') as f:f.write(body)
            receipt['bodies'].append(dict(task,sha256=digest,cache=cache,network_fetched=task['bytes']>0))
            tmp=x.output/'progress.tmp';tmp.write_text(json.dumps(receipt,indent=1));tmp.replace(x.output/'progress.json')
        receipt['status']='COMPLETE_BODIES_ONLY_CATALOG_NOT_INTEGRATED'
    except Exception as exc:
        receipt['status']='INCOMPLETE_CATALOG_UNCHANGED';receipt['errors'].append(type(exc).__name__+': '+str(exc))
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,old)
        receipt.update(response_bytes=budget.used,seconds=round(time.monotonic()-start,3),finished=datetime.datetime.now(datetime.timezone.utc).isoformat())
        with (x.output/'receipt.json').open('x') as f:json.dump(receipt,f,indent=2)
        print(json.dumps(receipt))
    return 0 if receipt['status'].startswith('COMPLETE_') else 2
if __name__=='__main__':raise SystemExit(main())
