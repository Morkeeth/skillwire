"""Prospective one-case reference/control correction. Never calls a model."""
import argparse,ast,contextlib,datetime,hashlib,json,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import lime_task_eval as task
import native_tdd_cases_v2 as repaired

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(p):return {str(f.relative_to(p)):sha(f)for f in p.rglob('*')if f.is_file()}

def repair(manifest,out):
 parent=json.loads(manifest.read_text());assert len(parent['entries'])==10
 assert parent['max_inference_invocations']==10 and all(e['execution_arms']==['without']for e in parent['entries'])
 out.mkdir(parents=True,exist_ok=False);entries=[];before={};controls=None;redgreen=[]
 for entry in parent['entries']:
  old=Path(entry['run']);assert not(old/'model-runs').exists()
  before[entry['case']]=tree(old);run=out/'evaluator'/entry['case'];shutil.copytree(old,run)
  e=dict(entry,run=str(run),source_run=str(old))
  if entry['case']=='url-origin':
   text=(run/'grader.py').read_text();assignment=next(n for n in ast.parse(text).body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='SPEC'for t in n.targets));spec=ast.literal_eval(assignment.value)
   old_good=spec['good'];good=repaired.GOOD['url-origin'];assert old_good!=good
   scope={};exec(old_good,scope)
   new_scope={};exec(good,new_scope)
   vectors=['https://example.com/app?q='+c for c in ('\u00a0','\u2003','\u2028')]
   for url in vectors:
    assert scope['allowed'](url)is True and new_scope['allowed'](url)is False
    redgreen.append({'codepoint':hex(ord(url[-1])),'before':True,'after':False,'expected_from_unchanged_task':False})
   for url,want in [('https://example.com/app?q=plain',True),('https://example.com/app?q= ',False),('https://example.com/app?q=%20',True)]:
    assert scope['allowed'](url)is want and new_scope['allowed'](url)is want
   spec['good']=good;spec['tests']+= [([url],False)for url in vectors]
   lines=text.splitlines(keepends=True);lines[assignment.lineno-1:assignment.end_lineno]=['SPEC='+repr(spec)+'\n'];(run/'grader.py').write_text(''.join(lines))
   (run/'reference/app.py').write_text(good)
   tests=(run/'reference/test_app.py').read_text()
   tests+=' def test_raw_unicode_whitespace_rejected(self):\n'
   for url in vectors:tests+='  self.assertFalse(allowed('+repr(url)+'))\n'
   (run/'reference/test_app.py').write_text(tests)
   croot=out/'controls';croot.mkdir()
   controls={'positive':task.judge(run/'grader.py',run/'reference',croot/'positive'),'original_negative':task.judge(run/'grader.py',run/'negative',croot/'original-negative'),'mutants':[]}
   for i,impl in enumerate(spec['mutants']+[old_good]):
    d=croot/('mutant-'+str(i));d.mkdir();(d/'app.py').write_text(impl);(d/'test_app.py').write_text(tests)
    controls['mutants'].append(task.judge(run/'grader.py',d,croot/('result-'+str(i))))
   assert controls['positive']['status']=='graded'and controls['positive']['passed']is True
   assert controls['original_negative']['status']=='graded'and controls['original_negative']['passed']is False
   assert all(x['status']=='graded'and x['passed']is False for x in controls['mutants'])
   plan=json.loads((run/'plan.json').read_text());assert task.inventory(run/'without')==plan['initial_fixture']
   plan['reference']=task.inventory(run/'reference');plan['grader_sha256']=sha(run/'grader.py');plan['controls']={'reference':controls['positive'],'deliberately_bad':controls['original_negative']}
   plan['reference_correction']={'scope':'Reject raw Unicode whitespace exactly as unchanged task requires','parent_plan_sha256':sha(old/'plan.json'),'observed_at':datetime.datetime.now().astimezone().isoformat()}
   (run/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
   protocol=json.loads((run/'protocol.json').read_text());protocol['reference_correction']='url-origin-raw-unicode-whitespace'
   assert protocol['task_runner_sha256']==sha(ROOT/'lime_task_eval.py')and protocol['adapter_sha256']==sha(ROOT/'lime_agent_eval.py')
   (run/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
   (run/'protocol-freeze.json').unlink() # new copied folder only; parent freeze is untouched
   with(out/'seal.log').open('w')as f,contextlib.redirect_stdout(f):task.seal(argparse.Namespace(run=run))
   e.update(grader_sha256=sha(run/'grader.py'),protocol_sha256=sha(run/'protocol.json'),seal_sha256=sha(run/'protocol-freeze.json'))
  else:assert tree(run)==before[entry['case']]
  assert sha(run/'TASK.md')==entry['task_sha256']
  assert task.inventory(run/'without')==task.inventory(old/'without')
  entries.append(e)
 assert controls is not None
 result=dict(parent,created_at=datetime.datetime.now().astimezone().isoformat(),family='tdd-v2-baseline-probe-url-whitespace-correction',parent_probe_manifest=str(manifest),parent_probe_sha256=sha(manifest),entries=entries,model_calls=0,inference_authorized=False)
 result['source_correction_sha256']={str(ROOT/n):sha(ROOT/n)for n in ('scripts/native_tdd_cases_v2.py','scripts/repair_baseline_url_whitespace.py')}
 (out/'FROZEN.json').write_text(json.dumps(result,indent=2)+'\n')
 for e in parent['entries']:assert tree(Path(e['run']))==before[e['case']]
 evidence={'status':'PASS_SOURCE_CONTROLS_ONLY','red_before_green_after':redgreen,'unchanged_ascii_plain_and_encoded_space_controls':True,'positive_reference_pass':controls['positive']['passed'],'old_reference_rejected':controls['mutants'][-1]['passed']is False,'three_original_mutants_rejected':all(x['passed']is False for x in controls['mutants'][:3]),'other_nine_inputs_seals_byte_identical':True,'all10_tasks_and_starting_fixtures_unchanged':True,'parent_probe_unchanged':True,'no_model_runs':True,'controls':controls}
 (out/'CORRECTION-CONTROLS.json').write_text(json.dumps(evidence,indent=2)+'\n')
 print(json.dumps({'manifest':str(out/'FROZEN.json'),'sha256':sha(out/'FROZEN.json'),'cases':10,'corrected_cases':['url-origin'],'controls':'PASS','model_calls':0,'inference_authorized':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();repair(a.manifest.resolve(),a.out.resolve())
