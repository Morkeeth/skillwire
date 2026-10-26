"""Offline paired artifact evaluation. Never invokes a model, uploads files or installs skills globally."""
import argparse,datetime,hashlib,io,json,os,re,shutil,subprocess,sys,zipfile
from pathlib import Path,PurePosixPath

def sha(b):return hashlib.sha256(b).hexdigest()
def inventory(root):
 rows=[]
 for p in sorted(root.rglob('*')):
  if p.is_symlink():raise ValueError('Symlinks are not accepted in a frozen fixture')
  if p.is_file():
   rel=p.relative_to(root).as_posix()
   if any(v in p.relative_to(root).parts for v in ['.git','.agents','.codex','.aws','.ssh','.npmrc','.netrc','auth.json','credentials.json','__pycache__']) or any(v.startswith('.env') for v in p.relative_to(root).parts):raise ValueError('Remove agent/config/private/generated files from fixture: '+rel)
   b=p.read_bytes()
   if len(b)>2*1024*1024:raise ValueError('Fixture file exceeds2MiB')
   rows.append({'path':rel,'sha256':sha(b),'bytes':len(b)})
 if not rows or sum(r['bytes'] for r in rows)>12*1024*1024:raise ValueError('Choose a nonempty fixture below12MiB')
 return rows

def judge(grader,artifact,dest,sandbox_launcher=None):
 env={k:os.environ[k] for k in ['PATH','LANG','TMPDIR'] if k in os.environ}
 if sandbox_launcher is not None:
  env['LIME_NATIVE_SANDBOX']=json.dumps(sandbox_launcher);env['LIME_GRADER_TRACE']=str(dest.with_suffix('.child-runs.json').resolve())
 try:p=subprocess.run([sys.executable,'-I',str(grader.resolve()),'--artifact',str(artifact.resolve())],capture_output=True,text=True,timeout=120 if sandbox_launcher is not None else 15,env=env,cwd=artifact)
 except subprocess.TimeoutExpired:
  result={'status':'grader_error','passed':None,'error':'timeout'}
 else:
  (dest.with_suffix('.stdout')).write_text(p.stdout);(dest.with_suffix('.stderr')).write_text(p.stderr)
  try:
   d=json.loads(p.stdout);checks=d['checks'];assert isinstance(checks,list) and checks and all(isinstance(x,dict) and type(x['passed']) is bool and isinstance(x['name'],str) for x in checks)
   result={'status':'graded','passed':all(x['passed'] for x in checks),'checks':checks} if p.returncode==0 else {'status':'grader_error','passed':None,'error':'nonzero grader exit'}
  except Exception:result={'status':'grader_error','passed':None,'error':'invalid grader output'}
 dest.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');return result

def read_evidence(path,skills):
 if path is None:return {'status':'unobserved','limit':'No tool trace supplied. Reference presence is not reading or use.'}
 # Only successful tool-command OUTPUT matching the exact full pinned body counts, never model self-report.
 matched=[];events=0;parse_errors=0
 for line in path.read_text().splitlines():
  try:d=json.loads(line)
  except Exception:parse_errors+=1;continue
  events+=1;item=d.get('item',{})
  if d.get('type')=='item.completed' and item.get('type')=='command_execution' and item.get('exit_code')==0 and isinstance(item.get('aggregated_output'),str):
   h=sha(item['aggregated_output'].encode())
   matched += [s['id'] for s in skills if h==s['sha256']]
 return {'status':'full_body_tool_output_observed' if matched else 'unobserved','matched_skill_ids':sorted(set(matched)),'trace_sha256':sha(path.read_bytes()),'events':events,'parse_errors':parse_errors,'limit':'Local trace evidence, not authenticated telemetry. Internal model use is unobservable. Partial/trimmed/inline reads are not inferred.'}

def prepare(a):
 if not a.trust_grader:raise ValueError('Pass --trust-grader only after inspecting your local grader. It executes with your user permissions, not a hostile-code sandbox.')
 if a.out.exists():raise ValueError('Use a new output directory; never overwrite a run')
 fixture=a.fixture.resolve();reference=a.reference.resolve();negative=a.negative.resolve()
 for folder in [fixture,reference,negative]:
  if a.out.resolve().is_relative_to(folder):raise ValueError('Output must be outside the input fixture/control folders')
  inventory(folder)
 task=a.task.read_bytes();grader=a.grader.read_bytes()
 if not task or len(task)>128*1024 or len(grader)>128*1024:raise ValueError('Task/grader empty or exceeds128KiB')
 # Validate archive before creating the run. No archive source is executed.
 files=[];skills=[]
 archive=a.stack
 selected_folder=getattr(a,'skill_folder',None)
 if a.skill is not None or selected_folder is not None:
  skill_path=selected_folder/'SKILL.md' if selected_folder is not None else a.skill
  body=skill_path.read_bytes()
  if skill_path.name!='SKILL.md' or not body or len(body)>2*1024*1024:raise ValueError('Select one installed SKILL.md below2MiB')
  entries=inventory(selected_folder) if selected_folder is not None else [{'path':'SKILL.md','sha256':sha(body),'bytes':len(body)}]
  if len(entries)>120:raise ValueError('Selected folder exceeds120files; no resources silently omitted')
  sid=sha(body)[:16];name=skill_path.parent.name;folder='selected-'+sid
  selected={'id':sid,'name':name,'repo':'local-installed','source':'local selected folder, no hosted upload','revision':'local-content-hash','sha256':sha(body),'license':'not established by selection','folder':folder,'visibility':'local-not-publicly-classified','files':entries}
  archive=io.BytesIO()
  with zipfile.ZipFile(archive,'w') as target:
   target.writestr('SKILL-SOURCES.json',json.dumps({'skills':[selected]}))
   for entry in entries:target.writestr(folder+'/'+entry['path'],(selected_folder/entry['path']).read_bytes() if selected_folder is not None else body)
  archive.seek(0)
 total=0;seen_paths=set();seen_folders=set()
 with zipfile.ZipFile(archive) as z:
  manifest=json.loads(z.read('SKILL-SOURCES.json'))
  if not 1<=len(manifest['skills'])<=10:raise ValueError('Choose one to ten pinned skills')
  for s in manifest['skills']:
   if s['folder'] in seen_folders:raise ValueError('Duplicate skill folder')
   seen_folders.add(s['folder'])
   if not 1<=len(s['files'])<=120:raise ValueError('Stack folder file limit exceeded')
   for f in s['files']:
    rel=PurePosixPath(f['path']);folder=PurePosixPath(s['folder'])
    if '\\' in f['path'] or str(folder) in ['.','..'] or not re.fullmatch(r'[A-Za-z0-9_.-]+',s['folder']) or rel.is_absolute() or folder.is_absolute() or '..' in rel.parts or '..' in folder.parts or len(folder.parts)!=1:raise ValueError('Unsafe source path')
    key=s['folder']+'/'+str(rel)
    if str(rel)=='.' or key in seen_paths:raise ValueError('Empty or duplicate source path')
    seen_paths.add(key)
    info=z.getinfo(s['folder']+'/'+f['path'])
    if info.file_size>2*1024*1024:raise ValueError('Stack file too large')
    total+=info.file_size
    if total>12*1024*1024:raise ValueError('Stack too large')
    raw=z.read(info)
    if sha(raw)!=f['sha256']:raise ValueError('Stack file hash mismatch')
    files.append((s['folder'],rel,raw))
   skill_body=z.read(s['folder']+'/SKILL.md')
   if sha(skill_body)!=s['sha256']:raise ValueError('Skill body hash mismatch')
   skills.append({k:s[k] for k in ['id','name','repo','source','revision','sha256','license']})
 a.out.mkdir(parents=True,exist_ok=False);root=a.out.resolve();(root/'grader.py').write_bytes(grader)
 (root/'TASK.md').write_bytes(task);(root/'SKILL-SOURCES.json').write_text(json.dumps(manifest,indent=2)+'\n')
 for label,folder in [('without',fixture),('with',fixture),('reference',reference),('negative',negative)]:shutil.copytree(folder,root/label)
 for folder,rel,raw in files:
  target=root/'with'/'.agents/skills'/folder/Path(*rel.parts);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 # Controls run BEFORE freeze. Failure leaves all receipts; plan is not marked ready.
 positive=judge(root/'grader.py',root/'reference',root/'positive-control');bad=judge(root/'grader.py',root/'negative',root/'negative-control')
 ready=positive['status']=='graded' and positive['passed'] is True and bad['status']=='graded' and bad['passed'] is False
 plan={'schema':1,'frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ready':ready,'task_sha256':sha(task),'grader_sha256':sha(grader),'initial_fixture':inventory(fixture),'reference':inventory(reference),'negative':inventory(negative),'skills':skills,'controls':{'reference':positive,'deliberately_bad':bad},'protocol':{'unit':'One user task; report every pair separately. Freeze model/version, reasoning, harness/tools, budget and order before inference in protocol.json.','arms':'Same task and initial fixture. without has no selected skills; with has only selected pinned skills. Disable unrelated global/project skills in both sessions.','read':'Require retained tool trace if full-body read is to be observed; otherwise unobserved. Reading is not use.','outcome':'Execute the independent artifact grader. Grader failure is infrastructure, not a task failure. Keep every error and original artifact.','scope':'No inference performed by this tool. One pair is not general efficacy. Grader is trusted local code, not an OS sandbox.'}}
 (root/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');(root/'protocol.json').write_text(json.dumps({'status':'NOT RUN','model':None,'reasoning':None,'harness':None,'tools':None,'budget':None,'arm_order':None,'instruction':'Fill and hash this before model runs; never add missing fields after observing outcomes.'},indent=2)+'\n')
 print(json.dumps({'ready':ready,'directory':str(a.out),'inference':False,'next':'Freeze protocol.json then use separate fresh sessions to complete TASK.md in each arm. This tool does not run them.'}));return 0 if ready else 1

def seal(a):
 root=a.run.resolve();plan=json.loads((root/'plan.json').read_text());assert plan['ready'],'Preflight did not pass'
 protocol=json.loads((root/'protocol.json').read_text())
 assert sha((root/'TASK.md').read_bytes())==plan['task_sha256'],'Frozen task changed'
 assert sha((root/'grader.py').read_bytes())==plan['grader_sha256'],'Frozen grader changed'
 for field in ['model','reasoning','harness','tools','budget','arm_order']:
  if protocol.get(field) is None:raise ValueError('Set protocol field before inference: '+field)
 if protocol['harness'] not in ['codex','claude'] or protocol['tools']!=('local_shell' if protocol.get('mode')=='native_installed' else 'disabled'):raise ValueError('Choose tools disabled for inline_reference or local_shell for native_installed')
 if protocol['reasoning'] not in ['low','medium','high']:raise ValueError('Choose low/medium/high reasoning effort')
 budget=protocol['budget']
 if not isinstance(budget,dict) or budget.get('max_cli_trials')!=2 or type(budget.get('timeout_seconds'))!=int or not 1<=budget['timeout_seconds']<=(360 if protocol.get('mode')=='native_installed' else 300):raise ValueError('budget must set max_cli_trials2 and timeout_seconds1..300; subscription tokens are not a dollar budget')
 if protocol['arm_order'] not in [['without','with'],['with','without']]:raise ValueError('arm_order must contain both arms once')
 assert inventory(root/'without')==plan['initial_fixture'],'Baseline fixture already changed'
 skill_manifest=json.loads((root/'SKILL-SOURCES.json').read_text())
 for skill in skill_manifest['skills']:
  for f in skill['files']:
   assert sha((root/'with'/'.agents/skills'/skill['folder']/f['path']).read_bytes())==f['sha256'],'Treatment source changed'
 # Compare fixture bytes in treatment separately from its installed skill folder.
 for f in plan['initial_fixture']:assert sha((root/'with'/f['path']).read_bytes())==f['sha256'],'Treatment fixture already changed'
 receipt={'sealed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protocol_sha256':sha((root/'protocol.json').read_bytes()),'plan_sha256':sha((root/'plan.json').read_bytes()),'sources_sha256':sha((root/'SKILL-SOURCES.json').read_bytes()),'inference':False,'note':'This records an offline pre-run seal, not proof a model ran.'}
 with (root/'protocol-freeze.json').open('x') as out:json.dump(receipt,out,indent=2)
 print(json.dumps(receipt))

def grade(a):
 root=a.run.resolve();plan=json.loads((root/'plan.json').read_text());assert plan['ready'],'Preflight did not pass'
 assert sha((root/'grader.py').read_bytes())==plan['grader_sha256'],'Frozen grader changed'
 assert sha((root/'TASK.md').read_bytes())==plan['task_sha256'],'Frozen task changed'
 seal=json.loads((root/'protocol-freeze.json').read_text())
 assert seal['plan_sha256']==sha((root/'plan.json').read_bytes()),'Plan changed after seal'
 assert seal['protocol_sha256']==sha((root/'protocol.json').read_bytes()),'Protocol changed after seal'
 result_path=root/'artifact-results.json'
 if result_path.exists():raise ValueError('Results already exist; retain them, use a fresh run for new outputs')
 result={'plan_sha256':sha((root/'plan.json').read_bytes()),'protocol_sha256':sha((root/'protocol.json').read_bytes()),'model_execution':'Not verified by this offline grader; attach raw run evidence, not self-reported efficacy.','arms':{},'inference':False}
 for name,trace in [('without',a.without_trace),('with',a.with_trace)]:
  result['arms'][name]={'grade':judge(root/'grader.py',root/name,root/(name+'-grade')),'read':read_evidence(trace,plan['skills'])}
 result_path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 s=sub.add_parser('prepare')
 for name in ['fixture','reference','negative','task','grader','out']:s.add_argument('--'+name,type=Path,required=True)
 choice=s.add_mutually_exclusive_group(required=True);choice.add_argument('--stack',type=Path);choice.add_argument('--skill',type=Path);choice.add_argument('--skill-folder',type=Path)
 s.add_argument('--trust-grader',action='store_true')
 s=sub.add_parser('seal');s.add_argument('--run',type=Path,required=True)
 s=sub.add_parser('grade');s.add_argument('--run',type=Path,required=True);s.add_argument('--without-trace',type=Path);s.add_argument('--with-trace',type=Path)
 a=p.parse_args()
 try:return prepare(a) if a.command=='prepare' else seal(a) if a.command=='seal' else grade(a)
 except (ValueError,AssertionError,KeyError,OSError,zipfile.BadZipFile) as ex:p.error(str(ex))
if __name__=='__main__':sys.exit(main())
