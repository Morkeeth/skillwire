"""Fill and seal a prepared local Lime trial. No model or network calls."""
import argparse,hashlib,json,secrets,sys
from pathlib import Path
import lime_task_eval as task

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--agent',choices=['codex','claude'],required=True);p.add_argument('--mode',choices=['native_installed','inline_reference'],default='native_installed');p.add_argument('--model',required=True);p.add_argument('--reasoning',choices=['low','medium','high'],default='low');p.add_argument('--order',choices=['random','without-first','with-first'],default='random');p.add_argument('--timeout',type=int,default=360);a=p.parse_args()
 root=a.run.resolve();protocol_path=root/'protocol.json'
 try:
  if (root/'protocol-freeze.json').exists():raise ValueError('Already sealed; use a new run for changed settings')
  old=json.loads(protocol_path.read_text())
  if old.get('status')!='NOT RUN':raise ValueError('Prepared protocol was already configured; inspect it instead of overwriting')
  if a.mode=='native_installed' and a.agent!='codex':raise ValueError('Native installed mode currently supports Codex only')
  if not 1<=a.timeout<=(360 if a.mode=='native_installed' else 300):raise ValueError('Timeout exceeds mode limit')
  order=secrets.choice([['without','with'],['with','without']]) if a.order=='random' else ['without','with'] if a.order=='without-first' else ['with','without']
  protocol={'status':'SEALED BEFORE INFERENCE','mode':a.mode,'model':a.model,'reasoning':a.reasoning,'harness':a.agent,'tools':'local_shell' if a.mode=='native_installed' else 'disabled','budget':{'max_cli_trials':2,'timeout_seconds':a.timeout},'arm_order':order}
  if a.mode=='native_installed':
   here=Path(__file__).resolve().parent
   protocol['adapter_sha256']=sha(here/'lime_agent_eval.py');protocol['task_runner_sha256']=sha(here/'lime_task_eval.py')
  protocol_path.write_text(json.dumps(protocol,indent=2)+'\n')
  task.seal(argparse.Namespace(run=root))
  print(json.dumps({'sealed_run':str(root),'mode':a.mode,'agent':a.agent,'model':a.model,'order':order,'model_calls':0}))
 except (ValueError,AssertionError,OSError,KeyError,json.JSONDecodeError) as e:p.error(str(e))
if __name__=='__main__':main()
