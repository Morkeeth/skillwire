"""Pull every GitHub skill source represented in a saved live publicly listed install snapshot."""
import datetime,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from expand_sources import pull
from normalize_catalog import normalize
from enrich_catalog import enrich

def installs(value):
    try:
        s=value.strip().replace(',','');suffix=s[-1:].upper();mult={'K':1000,'M':1000000,'B':1000000000}.get(suffix,1);return float(s[:-1] if suffix in 'KMB' else s)*mult
    except Exception:return None

def main():
    c=json.loads((ROOT/'evidence/hosted-catalog.json').read_text());m=json.loads((ROOT/'evidence/marketplace-live.json').read_text());existing={r['repo'].lower():r['repo'] for r in c['sources']};aliases={r.get('requested_repo',r['repo']).lower():r['repo'] for r in c['sources']};coverage=[];errors=[]
    for repo in dict.fromkeys(r['repo'] for r in m['rows']):
        if repo.lower().startswith('site/'):
            coverage.append({'repo':repo,'status':'external website distribution, not GitHub public-source scope'});continue
        if repo.lower() in existing or repo.lower() in aliases:
            coverage.append({'repo':repo,'status':'already pinned','canonical':existing.get(repo.lower(),aliases.get(repo.lower()))});continue
        try:
            rows,source,failures=pull(repo);canonical=source['repo'];aliases[repo.lower()]=canonical
            if canonical.lower() not in existing:c['sources'].append(source);c['skills']+=rows;existing[canonical.lower()]=canonical
            coverage.append({'repo':repo,'canonical':canonical,'status':'complete' if not failures else 'partial','skills':len(rows)});errors+=failures;print(repo,len(rows),'skills',len(failures),'errors',flush=True)
        except Exception as e:errors.append({'repo':repo,'error':str(e)});coverage.append({'repo':repo,'status':'failed'});print(repo,type(e).__name__,flush=True)
    c=normalize(c);c=enrich(c);unmatched=[]
    for row in m['rows']:
        canonical=existing.get(row['repo'].lower(),aliases.get(row['repo'].lower(),row['repo']))
        matches=[s for s in c['skills'] if s['repo'].lower()==canonical.lower() and (s['name'].lower()==row['slug'].lower() or Path(s['path']).parent.name.lower()==row['slug'].lower())]
        if not matches:unmatched.append(row);continue
        s=min(matches,key=lambda s:(len(s['path']),s['path']));s.update(installs=installs(row['installs_display']),installs_display=row['installs_display'],marketplace_rank=row['rank'],marketplace_source=row['marketplace_url'],installs_fetched_at=m['fetched_at'])
    c['marketplace_source']={'url':m['url'],'fetched_at':m['fetched_at'],'rows':len(m['rows']),'raw_sha256':m['raw_sha256']};c['errors']+=errors;c['fetched_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();(ROOT/'evidence/hosted-catalog.json').write_text(json.dumps(c,indent=2))
    (ROOT/'evidence/marketplace-coverage.json').write_text(json.dumps({'scope':'All GitHub public-source repositories represented in the saved live publicly listed installs snapshot. External website distributions are disclosed and excluded, not silently represented as GitHub.','source':c['marketplace_source'],'repos':coverage,'errors':errors,'unmatched_rows':unmatched},indent=2))
if __name__=='__main__':main()
