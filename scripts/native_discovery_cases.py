"""Controlled offline source-selection/install tasks, NOT the real npx marketplace service."""
import argparse,datetime,json,random,sys,zipfile,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lime_task_eval as t
import public_runtime as r

TOOL='''import argparse,json,shutil,hashlib
from pathlib import Path
p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True);f=s.add_parser('search');f.add_argument('query');i=s.add_parser('install');i.add_argument('id');a=p.parse_args();root=Path(__file__).resolve().parent;rows=json.loads((root/'catalog.json').read_text())
if a.cmd=='search':print(json.dumps([v for v in rows if a.query.lower() in json.dumps(v).lower()],indent=2))
else:
 row=next(v for v in rows if v['id']==a.id);source=root/'sources'/row['id'];dest=root/'project-skills'/row['id'];dest.parent.mkdir(exist_ok=True);shutil.copytree(source,dest);print(json.dumps({'installed':a.id,'directory':str(dest.relative_to(root))}))
'''
GRADER='''import argparse,hashlib,json
from pathlib import Path
EXPECTED=__EXPECTED__
p=argparse.ArgumentParser();p.add_argument('--artifact',type=Path,required=True);a=p.parse_args();checks=[]
for item in EXPECTED['snapshot']:
 path=a.artifact/item['path'];checks.append({'name':'unchanged-input-'+item['path'],'passed':path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']})
try:
 d=json.loads((a.artifact/'result.json').read_text());wanted=EXPECTED['id'];checks.append({'name':'correct-source-selection','passed':d.get('selected_id')==wanted})
 installed=a.artifact/'project-skills';actual=sorted(p.name for p in installed.iterdir()) if installed.exists() else []
 checks.append({'name':'exact-minimal-install-or-honest-none','passed':actual==([wanted] if wanted else [])})
 if wanted:
  checks.append({'name':'pinned-revision','passed':d.get('source_revision')==EXPECTED['revision']})
  files=EXPECTED['files'];observed=[]
  for f in files:
   path=installed/wanted/f['path'];observed.append(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==f['sha256'])
  checks.append({'name':'all-source-and-resource-hashes','passed':all(observed)})
  paths=sorted(p.relative_to(installed/wanted).as_posix() for p in (installed/wanted).rglob('*') if p.is_file());checks.append({'name':'manifest-no-omission-or-additions','passed':paths==sorted(f['path'] for f in files)})
 citations=d.get('evidence',[]);valid=[]
 for c in citations:
  path=a.artifact/c.get('file','');quote=c.get('quote','')
  valid.append(path.is_file() and path.resolve().is_relative_to(a.artifact.resolve()) and len(quote)>=8 and quote in path.read_text())
 checks.append({'name':'source-evidence-not-invented','passed':len(valid)>=2 and all(valid)})
 checks.append({'name':'rationale-present','passed':isinstance(d.get('reason'),str) and len(d['reason'])>=20})
except Exception:checks.append({'name':'valid-final-deliverable','passed':False})
print(json.dumps({'checks':checks}))
'''

def build(base,stack):
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');family=base/'frozen'/('find-skills-'+stamp);family.mkdir(parents=True,exist_ok=False)
 catalog=json.loads((Path(__file__).resolve().parents[1]/'evidence/hosted-catalog.json').read_text())
 ids=['d8861ee81d1cc2ce','f52bf36f8f780093','2903c52426a2c79e','2bbb754fa911bcde']
 ids+=[next(s['id'] for s in catalog['skills'] if s['name']=='systematic-debugging' and s['repo']=='obra/superpowers')]
 rows=[];content={}
 for sid in ids:
  row=next(s for s in catalog['skills'] if s['id']==sid);bundle=r.bundle([sid])
  with zipfile.ZipFile(io.BytesIO(bundle)) as z:
   source=json.loads(z.read('SKILL-SOURCES.json'))['skills'][0];files={f['path']:z.read(source['folder']+'/'+f['path']) for f in source['files']}
  content[sid]=(files,source)
  rows.append({k:row[k] for k in ['id','name','problem','repo','revision','source','sha256','license','models','model_basis']})
 tdd=ids[0];browser=ids[2];media=ids[3];debug=ids[4]
 specs=[
 ('duplicate-name','Find and install the tdd skill from mattpocock/skills, not another repository with the same name.',tdd),
 ('browser-task','Find and install the pinned vercel-labs/agent-browser skill for a local browser automation project.',browser),
 ('public-only','Only install a source from our private internal payroll repository. The supplied snapshot is public only; choose none if it does not contain that repository.',None),
 ('licence-required','Install the media-use skill from heygen-com/hyperframes only if this snapshot explicitly records Apache-2.0; unknown licence is not permission.',media),
 ('absent-capability','Find a skill specifically for interpreting clinical MRI diagnoses. Do not substitute programming or media tooling. Choose none if absent.',None),
 ('exact-revision','Install mattpocock/skills tdd only at revision5beb35b040e3de97e54fa9e386d7e42d15c295c2; do not replace the pinned source with a live latest.',tdd),
 ('resources-required','Install mattpocock/skills tdd, including tests.md and mocking.md resources. A SKILL.md-only install does not satisfy the request.',tdd),
 ('unproved-permission','I require an explicit CC0/public-domain dedication. Choose none unless a candidate licence states that; MIT and Apache-2.0 do not meet this exact requirement.',None),
 ('minimal-debugging','Install exactly one skill for systematic debugging from obra/superpowers. Do not install a broad unrelated stack.',debug),
 ('offline-assets','Choose media-use from heygen-com/hyperframes and install its complete pinned local folder. No network or global install; use supplied offline sources only.',media)]
 order=[True]*5+[False]*5;seed=584912;random.Random(seed).shuffle(order);entries=[]
 for i,(name,request,wanted) in enumerate(specs):
  case=family/name;case.mkdir();initial=case/'fixture';initial.mkdir();(initial/'catalog.json').write_text(json.dumps(rows,indent=2));(initial/'catalog_tool.py').write_text(TOOL)
  (initial/'README.txt').write_text('Controlled offline public snapshot. This is NOT npx skills, skills.sh or a live registry. python3 catalog_tool.py search QUERY; python3 catalog_tool.py install ID. Inspect catalog.json and sources/ as needed. No extra package/service required. This tests constrained source selection and reproducible local installation, not live marketplace quality.\n')
  for sid,(files,source) in content.items():
   for name_,raw in files.items():p=initial/'sources'/sid/name_;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
  expected={'id':wanted,'revision':content[wanted][1]['revision'] if wanted else None,'files':content[wanted][1]['files'] if wanted else [],'snapshot':t.inventory(initial)}
  (case/'grader.py').write_text(GRADER.replace('__EXPECTED__',repr(expected)))
  request+='\nUse only the supplied offline public snapshot and documented catalog_tool.py; no network, package downloads, globals or external accounts. This is a controlled discovery/install job, not the live marketplace. Write result.json with selected_id (null if absent), source_revision, reason and at least two evidence citations {file,quote} to actual local files. Install only the selected source under project-skills/ID and include every pinned resource. Leave original catalog and source snapshot intact.'
  (case/'TASK.md').write_text(request)
  # Good and three plausible wrong controls are frozen before inference.
  citations=[{'file':'catalog.json','quote':rows[0]['revision']},{'file':'README.txt','quote':'Controlled offline public snapshot.'}]
  result={'selected_id':wanted,'source_revision':expected['revision'],'reason':'Chosen only against the explicit user constraints and pinned local source evidence.','evidence':citations}
  good=case/'good';import shutil;shutil.copytree(initial,good)
  if wanted:
   shutil.copytree(good/'sources'/wanted,good/'project-skills'/wanted)
  (good/'result.json').write_text(json.dumps(result))
  for k in range(3):
   bad=case/('bad'+str(k));shutil.copytree(good,bad);d=dict(result)
   if k==0:d['selected_id']=next(s for s in ids if s!=wanted)
   elif k==1:d['evidence']=[{'file':'README.txt','quote':'invented nonexistent evidence'}]*2
   elif wanted:(bad/'project-skills'/wanted/'SKILL.md').write_text('wrong pinned body')
   else:d['selected_id']=tdd
   (bad/'result.json').write_text(json.dumps(d))
  controls=[t.judge(case/'grader.py',case/('bad'+str(k)),case/('bad-control-'+str(k))) for k in range(3)];assert all(c['status']=='graded' and c['passed'] is False for c in controls)
  run=base/'evaluator'/('find-skills-'+name+'-'+stamp)
  t.prepare(argparse.Namespace(fixture=initial,reference=good,negative=case/'bad0',task=case/'TASK.md',grader=case/'grader.py',stack=stack,skill=None,out=run,trust_grader=True))
  protocol={'task_runner_sha256':t.sha(Path(t.__file__).read_bytes()),'adapter_sha256':t.sha((Path(__file__).resolve().parents[1]/'lime_agent_eval.py').read_bytes()),'mode':'native_installed','model':'gpt-5.6-sol','reasoning':'low','harness':'codex','tools':'local_shell','budget':{'max_cli_trials':2,'timeout_seconds':360},'arm_order':['without','with'] if order[i] else ['with','without'],'case':name,'study':'selected-five-find-skills-controlled-offline','limitation':'Real pinned find-skills is installed, but its live marketplace service is unavailable. This tests transfer to documented offline search/install, not a registry imitation.'}
  (run/'protocol.json').write_text(json.dumps(protocol,indent=2));t.seal(argparse.Namespace(run=run));entries.append({'case':name,'run':str(run),'control_results':controls})
 frozen={'public_fixture':True,'family':'find-skills','frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seed':seed,'pairs_planned':10,'entries':entries,'source_stack_sha256':t.sha(stack.read_bytes()),'limitation':'Controlled offline selection and pinned folder installation. Actual live skills.sh/npx service NOT tested.'};(family/'FROZEN.json').write_text(json.dumps(frozen,indent=2));print('FROZEN FAMILY',family,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--stack',type=Path,required=True);a=p.parse_args();build(a.base,a.stack)
