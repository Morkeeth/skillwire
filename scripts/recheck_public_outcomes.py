"""Recheck published code artifacts with saved independent checks, no model calls."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 total=0
 for file,judge,key in [('public-evaluation-results.json','frozen_outcomes_v2.py','records'),('public-harder-results.json','harder_outcomes.py','runs')]:
  data=json.loads((ROOT/'evidence'/file).read_text())
  for row in data[key]:
   launch="import runpy,sys;sys.path.insert(0,sys.argv[1]);runpy.run_path(sys.argv[2],run_name='__main__')"
   p=subprocess.run([sys.executable,'-I','-c',launch,str(ROOT/'scripts'),str(ROOT/'scripts'/judge)],input=json.dumps({'case':row['case'],'code':row['code']}),text=True,capture_output=True,timeout=5,env={k:os.environ[k] for k in ['PATH','LANG'] if k in os.environ})
   assert p.returncode==0,(file,row['case'],'grader process failure');grade=json.loads(p.stdout);assert grade['passed']==row['score']['passed'] and grade['total']==row['score']['total'],(file,row['case'],'saved outcome differs')
   total+=1
 print(json.dumps({'public_outputs_rechecked':total,'model_calls':0,'interpretation':'Replay verifies saved task outcomes only. Does not establish model execution provenance, skill reading or efficacy.'}))
if __name__=='__main__':main()
