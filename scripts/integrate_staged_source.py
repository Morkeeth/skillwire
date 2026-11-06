"""Offline join of a complete pinned source stage. New output paths only; no network/build."""
import argparse,copy,hashlib,json,re,shutil,sys
from pathlib import Path
import incremental_refresh as ir

def read_body(folder,relative):
    if not isinstance(relative,str) or not re.fullmatch(r'bodies/[0-9a-f]{64}\.md',relative):
        raise ValueError('stage body path is not content-addressed')
    base=folder.resolve();path=folder/relative
    if path.is_symlink() or not path.resolve().is_relative_to(base/'bodies'):
        raise ValueError('stage body path escapes the stage')
    if path.stat().st_size>1_000_000:raise ValueError('stage body exceeds supported size')
    body=path.read_bytes()
    if hashlib.sha256(body).hexdigest()!=path.stem:raise ValueError('content-addressed body drift')
    return body

def integrate(catalog,state,folder):
    if not state.get('ready') or any(state.get('queues',{}).values()) or any(state.get('unsupported',{}).values()):
        raise ValueError('source stage is incomplete')
    source=next(x for x in catalog['sources'] if x['repo']==state['key'])
    if source['revision']!=state['old_revision']:raise ValueError('input source revision drift')
    old,new=state['files']['old'],state['files']['new']
    fetch=state.get('fetch',[])
    for path in fetch:
        body=read_body(folder,state['body_cache'][path])
        if len(body)!=new[path]['size'] or hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()!=new[path]['sha']:
            raise ValueError('staged body hash/size drift')
    row={'key':state['key'],'canonical':state['canonical'],'old_revision':state['old_revision'],'new_revision':state['new_revision'],'changed':state['old_revision']!=state['new_revision'],'stars':state['stars'],'license':state['license'],'tree':{'tree':state['trees']['new']},'fetch':fetch,'drop':state.get('drop',[]),'keep':sorted(p for p in new if p in old and new[p]['sha']==old[p]['sha']),'fetch_sizes':{p:new[p]['size'] for p in fetch},'fetch_shas':{p:new[p]['sha'] for p in fetch},'fetch_bytes':sum(new[p]['size'] for p in fetch)}
    def cached(url):
        prefix='https://raw.githubusercontent.com/'+state['canonical']+'/'+state['new_revision']+'/'
        if not url.startswith(prefix):raise ValueError('offline source URL mismatch')
        path=url[len(prefix):]
        if path not in state['body_cache']:raise ValueError('body was not staged')
        return read_body(folder,state['body_cache'][path])
    # Explicit, bounded isolated-worktree scratch writes are intentional: apply caches
    # verified tree/body data for the existing offline enrichment functions. No source
    # catalog/runtime/dist file is written and no downloaded code is executed.
    out,receipt=ir.apply(catalog,[row],{state['key']},max(1,row['fetch_bytes']),60,6,get=cached,protected_ids=ir.protected_measurements())
    # Removed upstream paths retain their old id/pinned bytes for saved votes/history.
    # They are explicitly historical, never presented as refreshed at the new revision.
    before={s['id']:s for s in catalog['skills']};present={s['id'] for s in out['skills']}
    retained=[]
    for sid in receipt['removed_ids']:
        if sid not in present:
            entry=copy.deepcopy(before[sid]);entry['upstream_status']='Removed from latest pinned tree; previous pinned source retained for saved votes and history'
            out['skills'].append(entry);retained.append(sid)
    receipt['retained_removed_ids']=retained
    assert before.keys()<={s['id'] for s in out['skills']},'an existing id disappeared'
    assert catalog.get('popular_ids')==out.get('popular_ids'),'Popular changed'
    updated=next(s for s in out['sources'] if s['repo']==state['key']);updated['skills']=sum(s['repo']==state['key'] for s in out['skills']);updated['retained_removed_entries']=len(retained)
    receipt.update(network_bytes=0,isolated_worktree_cache_writes=True,mode='offline verified stage integration',source_stage_revision=state['new_revision'])
    return out,receipt

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--stage',type=Path,required=True);p.add_argument('--next-out',type=Path,required=True);p.add_argument('--receipt-out',type=Path,required=True);x=p.parse_args(argv)
    paths=[x.catalog.resolve(),x.next_out.resolve(),x.receipt_out.resolve(),(x.stage/'state.json').resolve()]
    if len(set(paths))!=len(paths) or x.next_out.exists() or x.receipt_out.exists():p.error('distinct input and new outputs required')
    if (x.stage/'RUNNING.lock').exists():raise SystemExit('source stage still owned; no integration')
    catalog=json.loads(x.catalog.read_text());state=json.loads((x.stage/'state.json').read_text())
    out,receipt=integrate(catalog,state,x.stage)
    x.next_out.parent.mkdir(parents=True,exist_ok=True);x.receipt_out.parent.mkdir(parents=True,exist_ok=True)
    with x.next_out.open('x') as f:json.dump(out,f,indent=2)
    with x.receipt_out.open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(receipt))
if __name__=='__main__':main()
