"""Verify a completed public atomic-stock pilot and export local public-safe evidence. No inference."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lime_task_eval as t
from scripts.summarize_native_eval import summarize
ROOT=Path(__file__).resolve().parents[1]
def verify(run):
 run=run.resolve();seal=json.loads((run/'protocol-freeze.json').read_text());plan=json.loads((run/'plan.json').read_text());protocol=json.loads((run/'protocol.json').read_text());manifest=json.loads((run/'SKILL-SOURCES.json').read_text())
 assert protocol['case']=='atomic-stock' and protocol['mode']=='native_installed','Only reviewed public atomic-stock pilot may be exported here'
 for name,key in [('plan.json','plan_sha256'),('protocol.json','protocol_sha256'),('SKILL-SOURCES.json','sources_sha256')]:assert t.sha((run/name).read_bytes())==seal[key],'Frozen '+name+' changed'
 for name,key in [('TASK.md','task_sha256'),('grader.py','grader_sha256')]:assert t.sha((run/name).read_bytes())==plan[key]
 assert plan['ready'] and plan['controls']['reference']['passed'] is True and plan['controls']['deliberately_bad']['passed'] is False
 assert manifest['skills'][0]['id']=='d8861ee81d1cc2ce' and manifest['skills'][0]['sha256']=='5505d25bbaa8fc14a79e4d20163936958992a2995b7f1dd1d6197edc9ed722e0'
 proofs=[]
 for arm in ['without','with']:
  folder=run/'model-runs'/arm;boundary=json.loads((folder/'boundary.json').read_text());record=json.loads((folder/'record.json').read_text());grade=json.loads((folder/'outcome.json').read_text());children=json.loads((folder/'outcome.child-runs.json').read_text())
  assert boundary['passed'] and boundary['returncode']==0 and all(marker in boundary['stdout'] for marker in ['WORKSPACE_WRITE_ALLOWED','HIDDEN_READ_DENIED'])
  assert record['status']=='completed' and record['returncode']==0 and record['grade']==grade and grade['status']=='graded','Incomplete CLI or grader is not a valid task outcome'
  assert children[0]['returncode']==0 and children[0]['stdout'].strip()=='GRADER_CHILD_OK'
  assert all(c.get('returncode')!=71 for c in children),'Child runtime infrastructure failure invalidates grading'
  assert len(children)==9 and len(grade['checks'])==8 and all(type(c['passed']) is bool for c in grade['checks'])
  traces=(folder/'stdout.jsonl').read_bytes();workspace=Path(record['workspace']);artifacts=[]
  for name in ['app.py','test_app.py']:
   path=workspace/name;assert path.is_file() and not path.is_symlink();raw=path.read_bytes();assert (b'/' + b'Users/') not in raw,'Machine path in generated public artifact';artifacts.append({'path':name,'sha256':t.sha(raw),'content':raw.decode()})
  proofs.append({'arm':arm,'boundary_sha256':t.sha((folder/'boundary.json').read_bytes()),'record_sha256':t.sha((folder/'record.json').read_bytes()),'tool_trace_sha256':t.sha(traces),'child_runs_sha256':t.sha((folder/'outcome.child-runs.json').read_bytes()),'cli_version':record['cli_version'],'finished_at_utc':record['finished_at_utc'],'artifacts':artifacts})
  if arm=='with':
   assert record['read']['trace_sha256']==t.sha(traces)
   for source in manifest['skills']:
    for f in source['files']:assert t.sha((workspace/'.agents/skills'/source['folder']/f['path']).read_bytes())==f['sha256']
 # Post-run index references the earlier immutable pair seals; it is not a new preregistration.
 index={'public_fixture':True,'family':'tdd: atomic-stock native pilot','pairs_planned':1,'scope':'One bounded public repository-repair pilot. Baseline and treatment executed; not the planned ten-case study or a broad efficacy estimate.','entries':[{'case':'atomic-stock','run':str(run)}],'post_run_index':True}
 indexpath=run/'POST-RUN-PAIR-INDEX.json'
 if indexpath.exists():assert json.loads(indexpath.read_text())==index
 else:indexpath.write_text(json.dumps(index,indent=2)+'\n')
 study=summarize(indexpath);study.update({'study_class':'pilot','settings':{k:protocol[k] for k in ['model','reasoning','harness','tools','mode','budget','arm_order']},'sealed_at':seal['sealed_at'],'plan_sha256':seal['plan_sha256'],'protocol_sha256':seal['protocol_sha256'],'grader_sha256':plan['grader_sha256'],'source_manifest_sha256':seal['sources_sha256'],'verification':proofs,'task':(run/'TASK.md').read_text(),'read_limit':'Exact successful full-body tool output is observable. Offering, explicit invocation and internal influence are distinct; no claim of internal use.','interpretation':'Preserve observed ties and failures. One matched case cannot establish general skill benefit; interval remains wide.'})
 return study
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();study=verify(a.run);a.output.write_text(json.dumps({'studies':[study]},indent=2)+'\n');print(json.dumps({'valid_pairs':study['effect']['valid_pairs'],'without':study['cases'][0]['arms']['without']['task_passed'],'with':study['cases'][0]['arms']['with']['task_passed'],'read_observed':study['read_observed_treatments'],'effect':study['effect'],'inference_calls_by_verifier':0}))
