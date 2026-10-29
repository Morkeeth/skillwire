"""Create an allowlisted public deployment source. Never package local cache/auth/operator files."""
import datetime,hashlib,json,shutil,sys,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=['lime_task_eval.py','lime_agent_eval.py','lime_eval_setup.py','lime_human_review.py','EVAL-TOOLS.txt','site/eval-guide.html','site/human-review.html','site/human-review.js','eval-example/TASK.md','eval-example/grader.py','eval-example/bug/app.py','eval-example/good/app.py','eval-example/bad/app.py','.vercelignore','LICENSE','README.md','vercel.json','public_runtime.py','published_catalog.py','public_skill_finder.py','api/index.py','site/index.html','site/finder-base.css','site/finder.css','site/app.js','site/paired-inspector.js','site/installed-skills.js','site/adjacent.json','web/favicon.svg','scripts/build_site.py','scripts/enrich_catalog.py','scripts/serve_product.py','scripts/native_tdd_cases.py','scripts/native_tdd_cases_v2.py','.python-version','evidence/hosted-catalog.json','evidence/public-evaluation-results.json','evidence/judge-correction.json','evidence/public-harder-results.json','evidence/public-source-licences.json','evidence/runtime-catalog.json.gz']
if (ROOT/'evidence/public-native-evaluation.json').exists():FILES.append('evidence/public-native-evaluation.json')
FILES += ['CONTRIBUTING.md','docs/source-contributions.md','docs/eval-reproduction.md',
          'docs/usage-evidence.md','.github/PULL_REQUEST_TEMPLATE.md']
FILES += ['site/research-picks.js','site/research-picks.json']
def main():
    destination=ROOT/'data/release-source'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');destination.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for name in FILES:
        source=ROOT/name;target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        if source.is_symlink():raise ValueError('No source symlinks in public release')
        raw=source.read_bytes()
        if name=='evidence/judge-correction.json':
            d=json.loads(raw);d.pop('corrected_grades',None);raw=json.dumps(d,indent=2).encode()
        if (b'/' + b'Users/') in (gzip.decompress(raw) if name.endswith('.gz') else raw):raise ValueError('Local home path in public release: '+name)
        target.write_bytes(raw);manifest.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    (destination/'PUBLIC-SOURCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    (ROOT/'evidence/release-export-proof.json').write_text(json.dumps({'source_directory':str(destination.relative_to(ROOT)),'files':manifest,'privacy':'Exact allowlist. No data, credentials, private skills, historical article kit, git history, operator handovers, original raw auth/runtime files or environment values.'},indent=2))
    print(destination)
if __name__=='__main__':main()
