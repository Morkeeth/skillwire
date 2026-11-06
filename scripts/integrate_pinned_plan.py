"""Offline integration of an immutable metadata plan and complete verified body stage.

Only new catalog/receipt paths and bounded isolated-worktree source cache are written.
No API, raw download, build, install or downloaded code execution occurs.
"""
import argparse,copy,hashlib,json
from pathlib import Path
import incremental_refresh as ir
from integrate_staged_source import read_body

def integrate(catalog,plan,stage,folder,plan_sha,pin_manifest):
    if stage.get('status')!='COMPLETE_BODIES_ONLY_CATALOG_NOT_INTEGRATED' or stage.get('plan_sha256')!=plan_sha or stage.get('errors'):
        raise ValueError('body stage is not complete for this exact plan')
    if pin_manifest.get('schema')!='skillwire-public-measurement-pins/1' or not pin_manifest.get('pins'):
        raise ValueError('explicit pinned measurement manifest required')
    pinned={x['id']:x['sha256'] for x in pin_manifest['pins']}
    original={s['id']:s for s in catalog['skills']}
    if any(sid not in original or original[sid]['sha256']!=sha for sid,sha in pinned.items()):
        raise ValueError('input catalog violates measurement pin')
    rows=plan['sources'];sources={x['repo']:x for x in catalog['sources']};lookup={}
    for body in stage['bodies']:
        key=(body['repo'],body['path'])
        if key in lookup:raise ValueError('duplicate staged body')
        lookup[key]=body
    expected=set()
    for row in rows:
        if row['old_revision']!=sources[row['key']]['revision'] or row.get('tree',{}).get('truncated'):raise ValueError('source revision or tree coverage drift')
        for path in row.get('fetch',[]):
            key=(row['key'],path);expected.add(key);body=lookup[key]
            if body['revision']!=row['new_revision'] or body['canonical']!=row['canonical'] or body['bytes']!=row['fetch_sizes'][path] or body['git_blob_sha']!=row['fetch_shas'][path]:raise ValueError('staged body does not match pinned metadata')
            raw=read_body(folder,body['cache'])
            if len(raw)!=body['bytes'] or hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=body['git_blob_sha']:raise ValueError('cached body hash/size drift')
    if expected!=lookup.keys():raise ValueError('unexpected or missing staged bodies')
    urls={('https://raw.githubusercontent.com/'+b['canonical']+'/'+b['revision']+'/'+b['path']):b for b in lookup.values()}
    def cached(url):
        if url not in urls:raise ValueError('offline join requested an unstaged source')
        return read_body(folder,urls[url]['cache'])
    total=sum(r.get('fetch_bytes',0) for r in rows)
    out,receipt=ir.apply(catalog,rows,{r['key'] for r in rows},max(1,total),60,6,get=cached,protected_ids=set(pinned))
    if receipt['errors']:raise ValueError('offline join errors; candidate not emitted: '+str(receipt['errors']))
    before={s['id']:s for s in catalog['skills']};present={s['id'] for s in out['skills']};retained=[]
    for sid in receipt['removed_ids']:
        if sid not in present:
            old=copy.deepcopy(before[sid]);old['upstream_status']='Removed from new pinned tree; previous pinned source retained for saved votes/history'
            out['skills'].append(old);retained.append(sid)
    assert before.keys()<={s['id'] for s in out['skills']},'existing identity lost'
    assert catalog.get('popular_ids')==out.get('popular_ids'),'Popular order changed'
    assert set(out.get('popular_ids',[]))<={s['id'] for s in out['skills']},'Popular points to a missing entry'
    changed=set(receipt['added_ids'])|set(receipt['modified_ids'])
    for skill in out['skills']:
        if skill['id'] in changed:skill['fetched_at']=stage['finished']
    for src in out['sources']:
        if src['repo'] in {r['key'] for r in rows}:
            row=next(r for r in rows if r['key']==src['repo'])
            src['last_checked_at']=plan['planned_at'];src['metadata_checked_at']=plan['planned_at']
            src['fetched_at']=stage['finished'] if row.get('fetch') else plan['planned_at']
            src['skills']=sum(s['repo']==src['repo'] for s in out['skills'])
            src['retained_removed_entries']=sum(before[sid]['repo']==src['repo'] for sid in retained)
    refreshed={s['id']:s for s in out['skills']}
    if any(refreshed[sid]['sha256']!=sha for sid,sha in pinned.items()):raise ValueError('output violates frozen measurement pin')
    join_started,join_finished=receipt.pop('started'),receipt.pop('finished')
    cached_bytes=receipt.pop('fetched_bytes')
    out['last_incremental_at']=stage['finished'];out['offline_integrated_at']=join_finished
    out['incremental_refresh']['started']=stage['started'];out['incremental_refresh']['finished']=stage['finished']
    out['incremental_refresh']['fetched_bytes']=stage['response_bytes']
    receipt.update(network_bytes=0,cached_body_bytes=cached_bytes,integration_started_at=join_started,integration_finished_at=join_finished,retained_removed_ids=retained,metadata_checked_at=plan['planned_at'],bodies_fetched_at=stage['finished'],source_observation_clock_preserved=True,isolated_cache_writes=True,mode='offline join, not a new fetch or head check')
    out['incremental_refresh']['metadata_checked_at']=plan['planned_at'];out['incremental_refresh']['bodies_fetched_at']=stage['finished'];out['incremental_refresh']['network_bytes_this_join']=0
    return out,receipt

def read_pinned(path,digest):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('immutable input hash drift: '+str(path))
    return json.loads(raw)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ['catalog','plan','body-stage','measurement-pins','next-out','receipt-out']:p.add_argument('--'+flag,type=Path,required=True)
    for flag in ['catalog-sha256','plan-sha256','body-receipt-sha256','measurement-pins-sha256']:p.add_argument('--'+flag,required=True)
    x=p.parse_args(argv);inputs=[x.catalog.resolve(),x.plan.resolve(),(x.body_stage/'receipt.json').resolve(),x.measurement_pins.resolve()];outputs=[x.next_out.resolve(),x.receipt_out.resolve()]
    if set(inputs)&set(outputs) or len(set(outputs))!=2 or any(p.exists() for p in outputs):p.error('new independent output paths required')
    catalog=read_pinned(x.catalog,x.catalog_sha256);plan=read_pinned(x.plan,x.plan_sha256);stage=read_pinned(x.body_stage/'receipt.json',x.body_receipt_sha256)
    pins=read_pinned(x.measurement_pins,x.measurement_pins_sha256)
    out,receipt=integrate(catalog,plan,stage,x.body_stage,x.plan_sha256,pins)
    x.next_out.parent.mkdir(parents=True,exist_ok=True);x.receipt_out.parent.mkdir(parents=True,exist_ok=True)
    with x.next_out.open('x') as f:json.dump(out,f,indent=2)
    with x.receipt_out.open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(receipt))
if __name__=='__main__':main()
