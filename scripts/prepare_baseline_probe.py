"""Derive a separate baseline-only headroom probe from a sealed family; no inference."""
import argparse,contextlib,datetime,hashlib,json,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import lime_task_eval as task
import lime_agent_eval as agent

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def prepare(manifest,out):
 family=json.loads(manifest.read_text());assert len(family['entries'])==10
 assert family.get('version')=='v2-contract-repair'
 out.mkdir(parents=True,exist_ok=False);entries=[];before={}
 for entry in family['entries']:
  old=Path(entry['run']);plan=json.loads((old/'plan.json').read_text());seal=json.loads((old/'protocol-freeze.json').read_text());protocol=json.loads((old/'protocol.json').read_text())
  assert not(old/'model-runs').exists(),'Preserve prior attempts; choose the unrun source family'
  for name,key in [('plan.json','plan_sha256'),('protocol.json','protocol_sha256'),('SKILL-SOURCES.json','sources_sha256')]:assert digest(old/name)==seal[key],(entry['case'],name)
  assert digest(old/'TASK.md')==entry['task_sha256']==plan['task_sha256']
  assert digest(old/'grader.py')==entry['grader_sha256']==plan['grader_sha256']
  assert task.inventory(old/'without')==plan['initial_fixture']
  assert plan['ready']and plan['controls']['reference']['passed']and plan['controls']['deliberately_bad']['passed']is False
  run=out/'evaluator'/entry['case'];run.mkdir(parents=True)
  # Copy only sealed evaluator inputs, never old outcomes or runtime artifacts.
  for folder in ('without','with','reference','negative'):shutil.copytree(old/folder,run/folder)
  for name in ('TASK.md','grader.py','SKILL-SOURCES.json','plan.json'):shutil.copyfile(old/name,run/name)
  protocol.update(execution_arms=['without'],trial_scope='baseline-headroom-probe',inference_authorized=False,task_runner_sha256=digest(ROOT/'lime_task_eval.py'),adapter_sha256=digest(ROOT/'lime_agent_eval.py'))
  assert agent.native_execution_arms(protocol)==['without']
  (run/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
  with (out/'seal.log').open('a')as log,contextlib.redirect_stdout(log):task.seal(argparse.Namespace(run=run))
  assert digest(run/'TASK.md')==digest(old/'TASK.md')and digest(run/'grader.py')==digest(old/'grader.py')
  assert task.inventory(run/'without')==plan['initial_fixture']
  before[entry['case']]={n:digest(old/n)for n in ('TASK.md','grader.py','plan.json','protocol.json','protocol-freeze.json','SKILL-SOURCES.json')}
  entries.append({'case':entry['case'],'run':str(run),'source_run':str(old),'task_sha256':digest(run/'TASK.md'),'grader_sha256':digest(run/'grader.py'),'protocol_sha256':digest(run/'protocol.json'),'seal_sha256':digest(run/'protocol-freeze.json'),'execution_arms':['without'],'max_inference_invocations':1,'model':protocol['model'],'reasoning':protocol['reasoning'],'timeout_seconds':protocol['budget']['timeout_seconds']})
 frozen={'schema':'skillwire-baseline-headroom-probe/1','created_at':datetime.datetime.now().astimezone().isoformat(),'source_family':str(manifest),'source_family_sha256':digest(manifest),'family':'tdd-v2-contract-repair-baseline-probe','pairs_planned':0,'max_inference_invocations':10,'entries':entries,'runtime_source_sha256':{n:digest(ROOT/n)for n in ('lime_agent_eval.py','lime_task_eval.py','scripts/run_native_family.py','scripts/prepare_baseline_probe.py')},'inference_authorized':False,'model_calls':0,'decision_rule':'One baseline per case is an initial headroom screen only. All-pass cases are excluded from a later paired study; if none fails, report no headroom on these ten cases. Infrastructure errors are not evidence of headroom. No paired arm or benefit claim; a later study requires separate declaration, observed skill-body read and second baseline noise floor.','previous_results_preserved':True,'source_before':before}
 (out/'FROZEN.json').write_text(json.dumps(frozen,indent=2)+'\n')
 for entry in entries:
  old=Path(entry['source_run'])
  assert all(digest(old/name)==value for name,value in before[entry['case']].items())
 print(json.dumps({'manifest':str(out/'FROZEN.json'),'sha256':digest(out/'FROZEN.json'),'cases':len(entries),'max_invocations':10,'model_calls':0,'inference_authorized':False}))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();prepare(a.manifest.resolve(),a.out.resolve())
