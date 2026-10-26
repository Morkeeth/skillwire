"""Trusted local example grader. Executes the artifact; not a hostile-code sandbox."""
import argparse,copy,json,runpy
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--artifact',type=Path,required=True);a=p.parse_args()
f=runpy.run_path(str(a.artifact/'app.py'))['latest'];rows=[{'id':'a','version':2,'v':'first'},{'id':'b','version':3},{'id':'a','version':2,'v':'last'},{'id':'a','version':1}];before=copy.deepcopy(rows)
checks=[]
for name,fn in [('empty',lambda:f([])==[]),('greatest-and-last-tie',lambda:f(rows)==[rows[2],rows[1]]),('first-id-order',lambda:f([{'id':'z','version':0},{'id':'a','version':1}])==[{'id':'z','version':0},{'id':'a','version':1}]),('no-input-mutation',lambda:rows==before)]:
 try:checks.append({'name':name,'passed':bool(fn())})
 except Exception:checks.append({'name':name,'passed':False})
print(json.dumps({'checks':checks}))
