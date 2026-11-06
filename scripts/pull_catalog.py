"""Read-only GitHub catalog pull. Never executes repository content."""
import concurrent.futures, datetime, hashlib, io, json, re, urllib.request, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPOS=['anthropics/skills','openai/skills','vercel-labs/agent-skills','obra/superpowers','ComposioHQ/awesome-claude-skills','affaan-m/everything-claude-code','K-Dense-AI/claude-scientific-skills','travisvn/awesome-claude-skills','VoltAgent/awesome-agent-skills','sickn33/antigravity-awesome-skills','wshobson/agents','jeremylongshore/claude-code-plugins-plus-skills','mattpocock/skills','addyosmani/agent-skills','Leonxlnx/taste-skill']
TAXONOMY={'Documents':'pdf|docx|spreadsheet|xlsx|pptx|presentation|document','Design':'design|ui-ux|frontend|canvas|brand|visual','Testing':'test|debug|verification|review','Research':'research|scientific|biology|chemistry|paper|pubmed','Data':'data|sql|database|analytics|csv','Marketing':'marketing|seo|sales|campaign|social','Writing':'writing|copywriting|content|editing','Infrastructure':'deploy|docker|cloud|devops|kubernetes|terraform','Workflow':'workflow|planning|brainstorm|productivity|plan','Development':'.*'}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'lime-magnet-read-only'}),timeout=60) as r:
        raw=r.read(80_000_001)
    if len(raw)>80_000_000: raise ValueError('response exceeds safety cap')
    return raw
def field(body,key):
    m=re.search(r'^'+key+r':\s*(.*)$',body,re.M)
    return m.group(1).strip().strip('\"\'') if m else ''
def pull(repo):
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat(); rows=[]
    meta=json.loads(get('https://api.github.com/repos/'+repo)); revision=json.loads(get('https://api.github.com/repos/'+repo+'/commits/'+meta['default_branch']))['sha']
    archive_url='https://codeload.github.com/'+repo+'/zip/'+revision
    cached=ROOT/'data'/'hosted-sources'/repo.replace('/','--')/'source.zip'
    archive=get(archive_url)
    cache=ROOT/'data'/'hosted-sources'/repo.replace('/','--'); cache.mkdir(parents=True,exist_ok=True)
    (cache/'source.zip').write_bytes(archive)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        names=z.namelist(); readme=next((n for n in names if n.count('/')==1 and n.lower().endswith('/readme.md')),None)
        context=z.read(readme).decode(errors='replace') if readme else ''
        for n in names:
            if not n.endswith('/SKILL.md') or z.getinfo(n).file_size>1_000_000: continue
            raw=z.read(n); body=raw.decode(errors='replace'); path=n.split('/',1)[1]
            name=field(body,'name') or path.removesuffix('/SKILL.md').split('/')[-1]
            desc=field(body,'description')
            if desc in ('|','>','|-','>-',''): desc=next((l.strip() for l in body.splitlines() if len(l.strip())>35 and not l.startswith(('#','---'))),'Read the source to check the task this skill supports.')
            desc=re.sub('<[^>]+>','',desc)[:420]
            category=next(k for k,v in TAXONOMY.items() if re.search(v,name+' '+desc,re.I))
            models=[]; evidence=[]
            for label,pattern in [('Claude Code','claude code'),('Codex','codex'),('Cursor','cursor'),('Gemini CLI','gemini cli'),('Claude','claude')]:
                match=next((line for line in body.splitlines() if pattern in line.lower()),None)
                if match: models.append(label); evidence.append(match[:220])
            basis='stated in skill'
            if not models:
                basis='stated in repository'
                for label,pattern in [('Claude Code','claude code'),('Codex','codex'),('Cursor','cursor'),('Gemini CLI','gemini cli')]:
                    match=next((line for line in context.splitlines() if pattern in line.lower()),None)
                    if match: models.append(label); evidence.append(match[:220])
            if not models: models=['Agent Skills compatible']; basis='inferred from SKILL.md format'
            digest=hashlib.sha256(raw).hexdigest(); (cache/(digest+'.md')).write_bytes(raw)
            rows.append(dict(id=hashlib.sha256((repo+path).encode()).hexdigest()[:16],name=name,problem=desc,problem_basis='source description, automated extraction',category=category,category_basis='inferred by keyword rule',models=models,model_basis=basis,model_evidence=evidence,repo=repo,path=path,revision=revision,sha256=digest,source='https://github.com/'+repo+'/blob/'+revision+'/'+path,stars=meta['stargazers_count'],installs=None,fetched_at=stamp,license=(meta.get('license') or {}).get('spdx_id','Unknown'),eval={'status':'Not tested','n':0,'model':None,'date':None}))
    return rows,dict(repo=repo,stars=meta['stargazers_count'],revision=revision,fetched_at=stamp,skills=len(rows),archive_sha256=hashlib.sha256(archive).hexdigest(),license=(meta.get('license') or {}).get('spdx_id','Unknown'))
def main():
    skills=[]; sources=[]; errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(pull,r):r for r in REPOS}
        for f in concurrent.futures.as_completed(futures):
            try:
                rows,source=f.result(); skills+=rows;sources.append(source); print(source['repo'],len(rows),flush=True)
            except Exception as e: errors.append({'repo':futures[f],'error':str(e)});print(futures[f],str(e),flush=True)
    result=dict(fetched_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Explicit seed repositories, not an exhaustive census. Repository stars are not skill installs.',taxonomy=TAXONOMY,sources=sources,errors=errors,skills=sorted(skills,key=lambda s:(-s['stars'],s['name'])))
    from normalize_catalog import normalize
    result=normalize(result)
    from enrich_catalog import enrich
    result=enrich(result)
    (ROOT/'evidence'/'hosted-catalog.json').write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
