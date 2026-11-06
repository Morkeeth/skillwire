"""Close the star-ranked discovery scope using pinned trees and public raw skill bodies."""
import concurrent.futures,datetime,hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from pull_catalog import get,field,TAXONOMY
from normalize_catalog import normalize
from enrich_catalog import enrich

def api(path):
    # gh handles existing authentication internally. No token is read or printed by this program.
    p=subprocess.run(['gh','api',path],capture_output=True,text=True,timeout=50)
    if p.returncode:raise ValueError('GitHub metadata request failed: '+path)
    return json.loads(p.stdout)
def pull(repo):
    meta=api('repos/'+repo);canonical=meta['full_name'];revision=api('repos/'+canonical+'/commits/'+meta['default_branch'])['sha'];tree=api('repos/'+canonical+'/git/trees/'+revision+'?recursive=1')
    if tree.get('truncated'):raise ValueError('GitHub recursive tree truncated; coverage incomplete')
    cache=ROOT/'data/hosted-sources'/canonical.replace('/','--');cache.mkdir(exist_ok=True,parents=True)
    (cache/'tree.json').write_text(json.dumps(tree));paths=[x['path'] for x in tree['tree'] if x['type']=='blob' and (x['path']=='SKILL.md' or x['path'].endswith('/SKILL.md')) and x.get('size',0)<1_000_000]
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();readme=''
    try:readme=get('https://raw.githubusercontent.com/'+canonical+'/'+revision+'/README.md').decode(errors='replace')
    except Exception:pass
    rows=[];errors=[]
    def body(path):return path,get('https://raw.githubusercontent.com/'+canonical+'/'+revision+'/'+path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        fs={pool.submit(body,p):p for p in paths}
        for f in concurrent.futures.as_completed(fs):
            try:
                path,raw=f.result();text=raw.decode(errors='replace');sha=hashlib.sha256(raw).hexdigest();(cache/(sha+'.md')).write_bytes(raw)
                names=[]
                for label,pattern in [('Claude Code','claude code'),('Codex','codex'),('Cursor','cursor'),('Gemini CLI','gemini cli')]:
                    if pattern in text.lower():names.append(label)
                basis='stated in skill'
                if not names:
                    names=[label for label,p in [('Claude Code','claude code'),('Codex','codex'),('Cursor','cursor'),('Gemini CLI','gemini cli')] if p in readme.lower()];basis='stated in repository'
                if not names:names=['Agent Skills compatible'];basis='inferred from SKILL.md format'
                rows.append(dict(id=hashlib.sha256((canonical+path).encode()).hexdigest()[:16],name=field(text,'name') or Path(path).parent.name or canonical.split('/')[-1],problem='',category='Development',category_basis='inferred by keyword rule',models=names,model_basis=basis,model_evidence=[],repo=canonical,path=path,revision=revision,sha256=sha,source='https://github.com/'+canonical+'/blob/'+revision+'/'+path,stars=meta['stargazers_count'],installs=None,fetched_at=stamp,license=(meta.get('license') or {}).get('spdx_id','Unknown'),eval={'status':'Not tested','n':0,'model':None,'date':None}))
            except Exception as e:errors.append({'repo':canonical,'path':fs[f],'error':type(e).__name__})
    return rows,dict(repo=canonical,requested_repo=repo,revision=revision,stars=meta['stargazers_count'],license=(meta.get('license') or {}).get('spdx_id','Unknown'),fetched_at=stamp,skills=len(rows),discovered_skill_files=len(paths),tree_sha256=hashlib.sha256(json.dumps(tree).encode()).hexdigest(),fetch_mode='pinned tree + raw SKILL.md; supporting files fetched on user download'),errors

def main():
    catalog=json.loads((ROOT/'evidence/hosted-catalog.json').read_text());discovery=json.loads((ROOT/'evidence/repository-discovery.json').read_text())
    current={s['repo'] for s in catalog['sources']}
    candidates=list(dict.fromkeys([r['full_name'] for r in discovery['items']]+[e['repo'] for e in catalog['errors']]))
    # Renamed affaan-m/ECC is already covered by its pinned old name; keep identity explicit.
    scope=[];new_errors=[]
    for repo in candidates:
        if repo in current:scope.append({'repo':repo,'status':'already source-pinned in catalog'});continue
        try:
            rows,source,errors=pull(repo)
            if source['repo'] in current:scope.append({'repo':repo,'status':'redirects to existing source','canonical':source['repo']});continue
            catalog['skills']+=rows;catalog['sources'].append(source);current.add(source['repo']);scope.append({'repo':repo,'canonical':source['repo'],'status':'complete' if not errors else 'partial','skills':len(rows),'skill_files':source['discovered_skill_files']});new_errors+=errors
            print(repo,len(rows),'skills',len(errors),'errors',flush=True)
        except Exception as e:new_errors.append({'repo':repo,'error':str(e)});scope.append({'repo':repo,'status':'failed'});print(repo,type(e).__name__,flush=True)
    old_raw=catalog.get('raw_skill_files',len(catalog['skills']));catalog['errors']=new_errors;catalog['fetched_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();catalog=normalize(catalog);catalog=enrich(catalog);catalog['prior_raw_skill_files']=old_raw
    (ROOT/'evidence/hosted-catalog.json').write_text(json.dumps(catalog,indent=2))
    (ROOT/'evidence/discovery-coverage-night.json').write_text(json.dumps({'scope':'Every repo in saved star-ranked GitHub discovery plus earlier failed seed repos. Not the whole internet.','sources':scope,'errors':new_errors,'fetched_at':catalog['fetched_at']},indent=2))
if __name__=='__main__':main()
