"""Run an already frozen native family with existing subscription. Never edits its checks."""
import argparse,concurrent.futures,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lime_agent_eval as a

def execute(entry,workspaces):
 root=Path(entry['run'])
 if (root/'model-runs').exists():return {'case':entry['case'],'status':'retained-existing-no-rerun'}
 try:
  a.run(argparse.Namespace(run=root,agent='codex',use_subscription=True,mode='native_installed',workspaces=workspaces))
  return {'case':entry['case'],'status':'attempt-retained','records':str(root/'model-runs/records.json')}
 except Exception as ex:
  p=root/'runner-error.json';p.write_text(json.dumps({'error_type':type(ex).__name__,'error':str(ex),'task_score':None},indent=2));return {'case':entry['case'],'status':'infrastructure_error','error':str(ex)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--workspaces',type=Path,required=True);p.add_argument('--workers',type=int,choices=[1,2],default=1);args=p.parse_args();f=json.loads(args.manifest.read_text());print('FROZEN MANIFEST',args.manifest,flush=True)
 args.workspaces.mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
  futures=[pool.submit(execute,e,args.workspaces) for e in f['entries']]
  results=[future.result() for future in futures]
 out=args.manifest.parent/'ATTEMPTS.json';out.write_text(json.dumps(results,indent=2));print(out,flush=True)
if __name__=='__main__':main()
