"""Use an existing local agent subscription for a sealed paired artifact trial. No hosted service."""
import argparse,datetime,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
import lime_task_eval as task

def clean_env():return {k:os.environ[k] for k in ['PATH','HOME','LANG','TMPDIR','SHELL','USER','CODEX_HOME'] if k in os.environ}
def subscription(agent):
 env=clean_env()
 if agent=='codex':
  p=subprocess.run(['codex','login','status'],capture_output=True,text=True,env=env,timeout=20)
  return p.returncode==0 and 'ChatGPT' in p.stdout+p.stderr
 p=subprocess.run(['claude','auth','status','--json'],capture_output=True,text=True,env=env,timeout=20)
 try:d=json.loads(p.stdout);return p.returncode==0 and d.get('loggedIn') is True and d.get('authMethod') in ['oauth','claude_ai']
 except Exception:return False

def doctor(a):
 clis=[]
 for name in ['codex','claude','cursor-agent']:
  path=shutil.which(name)
  if path:
   ready=subscription(name) if name in ['codex','claude'] else False
   clis.append({'name':name,'installed':True,'subscription_verified':ready,'adapter':name in ['codex','claude'],'note':'API-key and unknown auth are refused by the trial runner.'})
 skills=[];seen=set()
 for root in [Path.home()/'.agents/skills',Path.home()/'.codex/skills',Path.home()/'.claude/skills',a.project/'.agents/skills',a.project/'.claude/skills']:
  if not root.is_dir():continue
  for p in sorted(root.rglob('SKILL.md')):
   if str(p.resolve()) in seen:continue
   seen.add(str(p.resolve()));raw=p.read_bytes()
   if len(raw)>2*1024*1024:continue
   text=raw.decode(errors='replace');m=re.search(r'^name:\s*(.+)$',text,re.M)
   row={'name':m.group(1).strip(' "\'') if m else p.parent.name,'sha256':task.sha(raw),'bytes':len(raw),'scope':'project' if p.is_relative_to(a.project) else 'user'}
   if a.show_paths:row['path']=str(p)
   skills.append(row)
 print(json.dumps({'clis':clis,'installed_skills':skills,'model_calls':0,'privacy':'Metadata detection only. Skill bodies stay local until the user selects a stack and explicitly runs a trial through their existing agent.'},indent=2))

def run(a):
 if getattr(a,'mode','inline_reference')=='native_installed':return run_native(a)
 if not a.use_subscription:raise ValueError('Explicit --use-subscription is required. Uses existing plan allowance, not a free-usage claim.')
 root=a.run.resolve();plan=json.loads((root/'plan.json').read_text());seal=json.loads((root/'protocol-freeze.json').read_text());protocol=json.loads((root/'protocol.json').read_text())
 assert plan['ready'] and seal['plan_sha256']==task.sha((root/'plan.json').read_bytes()) and seal['protocol_sha256']==task.sha((root/'protocol.json').read_bytes()),'Frozen protocol changed'
 assert task.sha((root/'TASK.md').read_bytes())==plan['task_sha256'],'Frozen task changed'
 assert task.sha((root/'grader.py').read_bytes())==plan['grader_sha256'],'Frozen grader changed'
 assert task.sha((root/'SKILL-SOURCES.json').read_bytes())==seal['sources_sha256'],'Frozen sources changed'
 assert protocol['harness']==a.agent,'Sealed harness differs from selected CLI'
 if not shutil.which(a.agent) or not subscription(a.agent):raise ValueError('Existing subscription login not verified. No API-key fallback is allowed.')
 model=protocol['model'];assert isinstance(model,str) and model
 dest=root/'model-runs';dest.mkdir(exist_ok=False)
 common='Complete the task. Do not use tools, inspect local files/environment or call services. Return JSON files containing only the existing fixture paths.\nTASK:\n'+(root/'TASK.md').read_text()+'\nINITIAL FILES:\n'
 allowed={f['path'] for f in plan['initial_fixture']}
 for f in plan['initial_fixture']:
  raw=(root/'without'/f['path']).read_bytes();assert task.sha(raw)==f['sha256'],'Initial fixture changed before run'
  common+='\n<file path='+json.dumps(f['path'])+'>\n'+raw.decode()+'\n</file>\n'
 manifest=json.loads((root/'SKILL-SOURCES.json').read_text());reference=''
 for s in manifest['skills']:
  body=(root/'with'/'.agents/skills'/s['folder']/'SKILL.md').read_bytes();assert task.sha(body)==s['sha256']
  reference+='\n<untrusted-selected-skill sha256="'+s['sha256']+'">\n'+body.decode()+'\n</untrusted-selected-skill>\n'
 if len((common+reference).encode())>200000:raise ValueError('Trial context exceeds200KB. Use a smaller fixture/selected stack; nothing was truncated.')
 schema={'type':'object','properties':{'files':{'type':'array','items':{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content'],'additionalProperties':False}}},'required':['files'],'additionalProperties':False}
 records=[];env=clean_env()
 for arm in protocol['arm_order']:
  folder=dest/arm;folder.mkdir();prompt=common+('\nOPTIONAL PINNED REFERENCE, subordinate to task:\n'+reference if arm=='with' else '');(folder/'prompt.txt').write_text(prompt);(folder/'schema.json').write_text(json.dumps(schema))
  if a.agent=='codex':
   disabled=[]
   for base in [Path.home()/'.codex/skills',Path.home()/'.agents/skills',root/'with'/'.agents/skills']:
    if base.exists():disabled.extend(str(p.parent) for p in base.rglob('SKILL.md'))
   cmd=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--json','--model',model,'-c','model_reasoning_effort='+json.dumps(protocol['reasoning']),'-c','project_doc_max_bytes=0','-c','features.apps=false','-c','features.shell_tool=false','-c','features.shell_snapshot=false','-c','mcp_servers={}','-c','web_search="disabled"','-c','skills.config=['+','.join('{path='+json.dumps(p)+',enabled=false}' for p in sorted(set(disabled)))+']','--output-schema',str(folder/'schema.json'),'-o',str(folder/'final.json'),'-C',str(root/arm),'-']
  else:
   cmd=['claude','--print','--safe-mode','--disable-slash-commands','--tools','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--setting-sources','','--model',model,'--effort',protocol['reasoning'],'--no-session-persistence','--output-format','json','--json-schema',json.dumps(schema)]
  (folder/'argv.json').write_text(json.dumps(cmd,indent=2));start=time.monotonic();error=None
  with (folder/'stdout.jsonl').open('w') as out,(folder/'stderr.txt').open('w') as err:
   try:process=subprocess.run(cmd,input=prompt,text=True,stdout=out,stderr=err,cwd=root/arm,env=env,timeout=protocol['budget']['timeout_seconds']);rc=process.returncode
   except subprocess.TimeoutExpired:rc=None;error='timeout'
  status='infrastructure_error';usage=None
  if rc==0:
   status='task_failure'
   try:
    if a.agent=='codex':
     response=json.loads((folder/'final.json').read_text());events=[json.loads(x) for x in (folder/'stdout.jsonl').read_text().splitlines()];completed=[x for x in events if x.get('type')=='turn.completed'];assert completed;usage=completed[-1].get('usage')
    else:
     result=json.loads((folder/'stdout.jsonl').read_text());assert not result.get('is_error');response=result.get('structured_output') or json.loads(result['result']);usage=result.get('usage')
    paths=[f['path'] for f in response['files']];assert len(paths)==len(set(paths)) and set(paths)<=allowed and paths
    for f in response['files']:
     target=root/arm/f['path'];assert target.resolve().is_relative_to(root/arm) and not target.is_symlink();target.write_text(f['content'])
    status='completed'
   except Exception as ex:error=type(ex).__name__
  record={'arm':arm,'status':status,'returncode':rc,'error':error,'model':model,'agent':a.agent,'seconds':round(time.monotonic()-start,3),'usage':usage,'reference_supplied':arm=='with','full_body_read':None if arm=='with' else False,'read_basis':'Inline selected skill body supplied. Separate read/internal use unobservable; tools disabled.','output_artifact_hashes':[{ 'path':f['path'],'sha256':task.sha((root/arm/f['path']).read_bytes())} for f in plan['initial_fixture']]}
  (folder/'record.json').write_text(json.dumps(record,indent=2)+'\n');records.append(record);print(arm,status,flush=True)
 (dest/'records.json').write_text(json.dumps(records,indent=2)+'\n')
 if all(r['status'] in ['completed','task_failure'] for r in records):
  task.grade(argparse.Namespace(run=root,without_trace=None,with_trace=None))
  path=root/'artifact-results.json';result=json.loads(path.read_text())
  for record in records:
   if record['status']=='task_failure':result['arms'][record['arm']]['grade']={'status':'graded','passed':False,'checks':[{'name':'valid-requested-artifact-format','passed':False}],'error':record['error']}
  result['inference']=True;result['model_execution']='Local CLI completion and raw structured output observed by runner; native skill invocation not tested.';result['runner_records_sha256']=task.sha((dest/'records.json').read_bytes());path.write_text(json.dumps(result,indent=2)+'\n')
 else:print('Infrastructure errors retained. No artifact task scores assigned to incomplete model runs.')

def native_config(workspace):
 """Restricted-read policy applies to tools; provider auth stays in the native parent."""
 python_runtime=Path(sys.base_prefix).resolve()
 if python_runtime==Path('/'):raise ValueError('Refuse broad Python runtime read root')
 rules={'default_permissions':'lime_trial','approval_policy':'never','project_doc_max_bytes':0,'features.apps':False,'features.shell_snapshot':False,'mcp_servers':{},'web_search':'disabled','permissions.lime_trial.extends':':workspace','permissions.lime_trial.filesystem':{':root':'deny',':minimal':'read',':workspace_roots':'write',':tmpdir':'write',':slash_tmp':'deny','/opt/homebrew':'read'},'permissions.lime_trial.network.enabled':False,'shell_environment_policy.inherit':'none','shell_environment_policy.set':{'PATH':os.environ.get('PATH','/usr/bin:/bin'),'TMPDIR':str(workspace/'.tmp')}}
 rules['permissions.lime_trial.filesystem'][str(python_runtime)]='read'
 rules['permissions.lime_trial.filesystem'][str(Path(sys.executable).resolve())]='read'
 disabled=[]
 for base in [Path.home()/'.codex/skills',Path.home()/'.agents/skills',Path.home()/'.claude/skills']:
  if base.exists():disabled.extend({'path':str(p.parent),'enabled':False} for p in base.rglob('SKILL.md'))
 # TOML inline tables, unlike JSON objects, use equals.
 def toml(v):
  if isinstance(v,dict):return '{'+','.join(json.dumps(str(k))+'='+toml(x) for k,x in v.items())+'}'
  if isinstance(v,list):return '['+','.join(toml(x) for x in v)+']'
  return json.dumps(v)
 rules['skills.config']=disabled
 flags=[]
 for k,v in rules.items():flags+=['-c',k+'='+toml(v)]
 return flags

def native_boundary(workspace,hidden,output):
 """Exercise same Codex permission profile before any counted model output."""
 workspace.mkdir(parents=True,exist_ok=True);(workspace/'.tmp').mkdir(exist_ok=True)
 canary=hidden/'BOUNDARY-CANARY.txt';canary.write_text('EVALUATOR MUST NOT BE READ BY MODEL TOOLS')
 probe="from pathlib import Path;import sys;p=Path(sys.argv[1]);q=Path('boundary-write.txt');q.write_text('ok');assert q.read_text()=='ok';print('WORKSPACE_WRITE_ALLOWED');\ntry:p.read_bytes()\nexcept PermissionError:print('HIDDEN_READ_DENIED');sys.exit(0)\nraise SystemExit('HIDDEN_READ_WAS_ALLOWED')"
 cmd=['codex']+native_config(workspace)+['sandbox','--permission-profile','lime_trial','-C',str(workspace),'--',sys.executable,'-I','-c',probe,str(canary)]
 p=subprocess.run(cmd,cwd=workspace,env=clean_env(),capture_output=True,text=True,timeout=30)
 receipt={'argv':cmd,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'passed':p.returncode==0 and 'HIDDEN_READ_DENIED' in p.stdout and 'WORKSPACE_WRITE_ALLOWED' in p.stdout}
 output.write_text(json.dumps(receipt,indent=2)+'\n')
 if not receipt['passed']:raise ValueError('Native isolation probe failed. No model call permitted; retained '+str(output))
 return receipt

def run_native(a):
 if not a.use_subscription or a.agent!='codex':raise ValueError('Native adapter currently requires explicit existing Codex subscription')
 root=a.run.resolve();plan=json.loads((root/'plan.json').read_text());seal=json.loads((root/'protocol-freeze.json').read_text());protocol=json.loads((root/'protocol.json').read_text())
 for name,key in [('plan.json','plan_sha256'),('protocol.json','protocol_sha256'),('SKILL-SOURCES.json','sources_sha256')]:assert task.sha((root/name).read_bytes())==seal[key],'Frozen '+name+' changed'
 assert task.sha((root/'TASK.md').read_bytes())==plan['task_sha256'] and task.sha((root/'grader.py').read_bytes())==plan['grader_sha256'],'Task or grader changed'
 if protocol.get('task_runner_sha256'):assert task.sha(Path(task.__file__).read_bytes())==protocol['task_runner_sha256'],'Frozen task runner changed'
 if protocol.get('adapter_sha256'):assert task.sha(Path(__file__).read_bytes())==protocol['adapter_sha256'],'Frozen native adapter changed; do not run main outputs under changed policy'
 assert plan['ready'] and protocol['mode']=='native_installed' and protocol['tools']=='local_shell' and protocol['harness']=='codex'
 assert task.inventory(root/'without')==plan['initial_fixture'],'Starting baseline changed'
 assert protocol['budget']['max_cli_trials']==2 and 1<=protocol['budget']['timeout_seconds']<=360
 if not subscription('codex'):raise ValueError('Existing ChatGPT subscription not verified, no API fallback')
 dest=root/'model-runs';dest.mkdir(exist_ok=False)
 cli_version=subprocess.run(['codex','--version'],capture_output=True,text=True,env=clean_env(),timeout=10).stdout.strip()
 # Model workspaces are outside the hidden evaluator tree and cannot read it.
 workbase=a.workspaces.resolve();assert not workbase.is_relative_to(root) and not root.is_relative_to(workbase),'Separate evaluator and workspace roots required'
 manifest=json.loads((root/'SKILL-SOURCES.json').read_text());records=[]
 for arm in protocol['arm_order']:
  workspace=workbase/(root.name+'-'+arm);shutil.copytree(root/arm,workspace);(workspace/'TASK.md').write_bytes((root/'TASK.md').read_bytes());(workspace/'.tmp').mkdir()
  for f in plan['initial_fixture']:assert task.sha((workspace/f['path']).read_bytes())==f['sha256'],'Starting fixture changed'
  if arm=='with':
   for s in manifest['skills']:
    for f in s['files']:assert task.sha((workspace/'.agents/skills'/s['folder']/f['path']).read_bytes())==f['sha256'],'Pinned source changed'
  folder=dest/arm;folder.mkdir();native_boundary(workspace,root,folder/'boundary.json')
  prompt='Complete the user request in TASK.md. Work only in this disposable project. Save the requested deliverables here. There is no interactive user; follow the agreed public interface in TASK.md. Do not use external services, install packages, or modify global configuration. Local project resources are available normally. Report what you actually completed.'
  cmd=['codex','exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check','--json','--model',protocol['model'],'-c','model_reasoning_effort='+json.dumps(protocol['reasoning'])]+native_config(workspace)+['-o',str(folder/'final.txt'),'-C',str(workspace),'-']
  (folder/'argv.json').write_text(json.dumps(cmd,indent=2));(folder/'prompt.txt').write_text(prompt);start=time.monotonic();error=None
  env=clean_env();env['TMPDIR']=str(workspace/'.tmp')
  with (folder/'stdout.jsonl').open('w') as out,(folder/'stderr.txt').open('w') as err:
   try:p=subprocess.run(cmd,input=prompt,text=True,stdout=out,stderr=err,cwd=workspace,env=env,timeout=protocol['budget']['timeout_seconds']);rc=p.returncode
   except subprocess.TimeoutExpired:rc=None;error='timeout'
  events=[]
  for line in (folder/'stdout.jsonl').read_text().splitlines():
   try:events.append(json.loads(line))
   except ValueError:pass
  completed=[e for e in events if e.get('type')=='turn.completed'];status='completed' if rc==0 and completed else 'infrastructure_error'
  # Missing/invalid deliverables after a completed response are graded as task failures.
  resource_reads=[]
  if arm=='with':
   for event in events:
    item=event.get('item',{})
    if event.get('type')=='item.completed' and item.get('type')=='command_execution' and item.get('exit_code')==0 and isinstance(item.get('aggregated_output'),str):
     h=task.sha(item['aggregated_output'].encode())
     for source in manifest['skills']:
      resource_reads.extend({'skill_id':source['id'],'path':f['path'],'sha256':h} for f in source['files'] if f['path']!='SKILL.md' and f['sha256']==h)
  record={'mode':'native_installed','adapter_sha256':task.sha(Path(__file__).read_bytes()),'cli_version':cli_version,'finished_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'subscription_auth':'verified ChatGPT login, native profile in place','arm':arm,'status':status,'returncode':rc,'error':error,'seconds':round(time.monotonic()-start,3),'usage':completed[-1].get('usage') if completed else None,'model_requested':protocol['model'],'skill_installed':arm=='with','skill_listed_observed':None,'explicit_invocation_observed':None,'full_resource_outputs_observed':resource_reads,'skill_offered_basis':'Pinned project .agents/skills folder; normal native CLI discovery, not forced read.' if arm=='with' else 'Selected folder absent','read':task.read_evidence(folder/'stdout.jsonl',plan['skills']) if arm=='with' else {'status':'not_supplied'},'workspace':str(workspace)}
  if status=='completed':
   if any(p.is_symlink() for p in workspace.rglob('*')):record['grade']={'status':'graded','passed':False,'checks':[{'name':'artifact-contains-no-unsafe-symlinks','passed':False}]}
   else:record['grade']=task.judge(root/'grader.py',workspace,folder/'outcome',sandbox_launcher=['codex']+native_config(workspace)+['sandbox','--permission-profile','lime_trial'])
  (folder/'record.json').write_text(json.dumps(record,indent=2)+'\n');records.append(record);(dest/'records.json').write_text(json.dumps(records,indent=2)+'\n');print(arm,status,flush=True)
 result={'mode':'native_installed','inference':any(r['status']=='completed' for r in records),'model_execution':'Native CLI completed events and raw tool traces retained; model internal influence remains unknown.','arms':{r['arm']:{'status':r['status'],'grade':r.get('grade',{'status':'infrastructure_error','passed':None,'checks':[]}),'read':r['read']} for r in records},'plan_sha256':task.sha((root/'plan.json').read_bytes()),'protocol_sha256':seal['protocol_sha256']}
 (root/'artifact-results.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'mode':'native_installed','records':records,'limit':'Skill installed/offered is not evidence of reading or internal influence. Every failure retained.'},indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True);d=s.add_parser('doctor');d.add_argument('--project',type=Path,default=Path.cwd());d.add_argument('--show-paths',action='store_true');r=s.add_parser('run');r.add_argument('--run',type=Path,required=True);r.add_argument('--agent',choices=['codex','claude'],required=True);r.add_argument('--use-subscription',action='store_true');r.add_argument('--mode',choices=['inline_reference','native_installed'],default='inline_reference');r.add_argument('--workspaces',type=Path);a=p.parse_args()
 try:return doctor(a) if a.command=='doctor' else run(a)
 except (ValueError,AssertionError,OSError,KeyError) as ex:p.error(str(ex))
if __name__=='__main__':main()
