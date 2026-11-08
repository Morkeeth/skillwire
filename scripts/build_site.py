"""Reproducible offline static production export for Vercel."""
import argparse, json, shutil, re, sys, gzip, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EVAL_KIT_FILES=('lime_task_eval.py','lime_agent_eval.py','lime_eval_setup.py','lime_human_review.py','EVAL-TOOLS.txt','LICENSE','eval-example/TASK.md','eval-example/grader.py','eval-example/bug/app.py','eval-example/good/app.py','eval-example/bad/app.py','eval-example/demo-skill/SKILL.md')
def build_eval_kit(root,out):
    # These controls are required by the documented clean-extraction example.
    # Never publish a kit that silently loses them at the hosting upload boundary.
    missing=[name for name in EVAL_KIT_FILES if not (root/name).is_file()]
    if missing:raise ValueError('Local evaluation kit missing required files: '+', '.join(missing))
    with zipfile.ZipFile(out/'local-eval-tools.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in EVAL_KIT_FILES:
            info=zipfile.ZipInfo(name,(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,(root/name).read_bytes())
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,help='staged source catalog; requires an isolated --output')
    parser.add_argument('--output',type=Path,help='new isolated output directory, including its runtime catalog')
    args=parser.parse_args(argv)
    if args.catalog and not args.output:
        parser.error('--catalog requires an isolated --output')
    out=args.output.resolve() if args.output else ROOT/'dist'
    if args.output:
        protected=[ROOT/'dist',ROOT/'evidence',ROOT/'site',ROOT/'assets']
        if out.is_relative_to(ROOT.resolve()):
            parser.error('--output must be outside the source worktree')
        if any(out==p.resolve() or p.resolve().is_relative_to(out) for p in protected):
            parser.error('--output overlaps source or production artifacts')
        if out.exists():
            parser.error('--output must be a new directory')
    sys.path.insert(0,str(ROOT))
    import published_catalog
    catalog=published_catalog.load(args.catalog)
    assert catalog['skills'], 'empty catalog'
    from enrich_catalog import EMAIL
    assert not EMAIL.search(json.dumps(catalog)), 'email in public catalog'
    assert all('target_models' in s for s in catalog['skills'])
    ids=set()
    for s in catalog['skills']:
        assert s['id'] not in ids;ids.add(s['id'])
        assert s['category'] in catalog['taxonomy'] and s['problem'] and s['models']
        assert (s['source'].startswith('https://github.com/') or s.get('local_bundle')) and len(s['revision'])==40
        assert (s['eval']['status']=='Not tested' and s['eval']['n']==0) or (s['eval']['status']=='Measured task outcomes' and s['eval']['skill_sha256']==s['sha256'])
    runtime_keys=['id','name','repo','path','source','revision','sha256','license','folder_files','local_bundle']
    runtime={'skills':[{k:s[k] for k in runtime_keys if k in s} for s in catalog['skills']],'sources':[{k:s[k] for k in ['repo','revision','archive_sha256'] if k in s} for s in catalog['sources']]}
    out.mkdir(parents=True,exist_ok=not bool(args.output))
    runtime_path=out/'runtime-catalog.json.gz' if args.output else ROOT/'evidence/runtime-catalog.json.gz'
    runtime_path.write_bytes(gzip.compress(json.dumps(runtime,separators=(',',':')).encode(),mtime=0))
    from catalog_egg import files, FOLDER
    payload=out/'assets'/FOLDER;payload.mkdir(parents=True,exist_ok=True)
    for name,raw in files().items():(payload/name).write_bytes(raw)
    old_style=out/'style.css'
    if old_style.exists():old_style.unlink()
    for n in ('index.html','analytics.js','finder-base.css','finder.css','app.js','paired-inspector.js','installed-skills.js','adjacent.json','human-review.html','human-review.js','research-picks.js','research-picks.json','oscar-picks.json','votes.js','votes.css','v3.css'):shutil.copyfile(ROOT/'site'/n,out/n)
    shutil.copyfile(ROOT/'web/favicon.svg',out/'favicon.svg')
    (out/'catalog.json').write_text(json.dumps(catalog,separators=(',',':')))
    from catalog_views import project
    views=project(catalog)
    for name,raw in views['files'].items():
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    html=(out/'index.html').read_text()
    html=html.replace('<html ', '<html data-catalog-index="'+views['index_url']+'" ',1)
    (out/'index.html').write_text(html)
    if (ROOT/'evidence/public-evaluation-results.json').exists():
        shutil.copyfile(ROOT/'evidence/public-evaluation-results.json',out/'evaluations.json')
        correction=json.loads((ROOT/'evidence/judge-correction.json').read_text());correction.pop('corrected_grades',None)
        (out/'judge-correction.json').write_text(json.dumps(correction,indent=2))
    shutil.copyfile(ROOT/'evidence/public-harder-results.json',out/'harder-evaluations.json')
    shutil.copyfile(ROOT/'site/eval-guide.html',out/'eval-guide.html')
    original=json.loads((ROOT/'evidence/public-evaluation-results.json').read_text());harder=json.loads((ROOT/'evidence/public-harder-results.json').read_text())
    tasks=[]
    for skill in original['evaluations']:
        for t in skill['tasks']:tasks.append({'task':t['id'],'skill':skill['name'],'n':t['baseline_n'],'groups':t['checks_per_run'],'baseline_passes':sum(x==t['checks_per_run'] for x in t['baseline_checks_passed']),'treatment_passes':sum(x==t['checks_per_run'] for x in t['treatment_checks_passed'])})
    native_path=ROOT/'evidence/public-native-evaluation.json'
    (out/'native-studies.json').write_text(native_path.read_text() if native_path.exists() else json.dumps({'studies':[],'status':'No completed native study published. Existing inline results retain their original scope.'}))
    studies=[{'title':'Original exploratory function tasks','model':original['evaluations'][0]['model'],'completed_outputs':len(original['records']),'protocol':'Pinned reference inline; tool use disabled; post-run grader capability correction.','tasks':tasks,'evidence':'evaluations.json'},{'title':'Separately frozen harder follow-up','model':harder['model'],'completed_outputs':len(harder['runs']),'protocol':'Pinned reference inline; tool use disabled; frozen checks, corrected grader launch path.','tasks':[{'task':t['case'],'skill':next(v['name'] for v in harder['skills'] if v['id']==t['skill']),'n':t['n_per_arm'],'groups':t['outcome_groups'],'baseline_passes':t['all_groups_pass']['baseline'],'treatment_passes':t['all_groups_pass']['treatment']} for t in harder['summary']],'evidence':'harder-evaluations.json'}]
    (out/'eval-studies.json').write_text(json.dumps({'studies':studies},indent=2))
    build_eval_kit(ROOT,out)
    print(json.dumps({'build':'static production export','skills':len(ids),'repos':len(catalog['sources']),'output':str(out) if args.output else 'dist','runtime_output':str(runtime_path),'catalog_input':str(args.catalog or ROOT/'evidence/hosted-catalog.json'),'network':False}))
if __name__=='__main__':main()
