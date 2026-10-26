"""Summarize actual frozen native pairs without pooling inline or inventing missing outcomes."""
import argparse,json,math
from pathlib import Path

def cp(k,n,confidence=.975):
 if n==0:return [0.,1.]
 tail=(1-confidence)/2
 def ge(p):return sum(math.comb(n,j)*p**j*(1-p)**(n-j) for j in range(k,n+1))
 def le(p):return sum(math.comb(n,j)*p**j*(1-p)**(n-j) for j in range(k+1))
 def root(fn,target,increasing):
  lo=0.;hi=1.
  for _ in range(90):
   mid=(lo+hi)/2
   if (fn(mid)<target)==increasing:lo=mid
   else:hi=mid
  return (lo+hi)/2
 return [0. if k==0 else root(ge,tail,True),1. if k==n else root(le,tail,False)]

def effect(w,l,n,planned):
 if not n:return {'valid_pairs':0,'difference':None,'ci95':[-1.,1.],'missing_pair_bound':[-1.,1.],'exact_discordant_p':None}
 a,b=cp(w,n),cp(l,n);discord=w+l
 p=min(1.,2*sum(math.comb(discord,j) for j in range(min(w,l)+1))/2**discord) if discord else 1.
 return {'valid_pairs':n,'difference':(w-l)/n,'ci95':[max(-1.,a[0]-b[1]),min(1.,a[1]-b[0])],'missing_pair_bound':[(w-l-(planned-n))/planned,(w-l+(planned-n))/planned],'exact_discordant_p':p}

def summarize(path):
 frozen=json.loads(path.read_text());rows=[];wins=losses=bothpass=bothfail=valid=attempted=0;reads=0;errors=[]
 for entry in frozen['entries']:
  root=Path(entry['run']);p=root/'model-runs/records.json';records=json.loads(p.read_text()) if p.exists() else []
  attempted+=len(records);arms={r['arm']:r for r in records};states={}
  for arm in ['without','with']:
   r=arms.get(arm,{})
   grade=r.get('grade',{})
   states[arm]={'completion':r.get('status','not_run'),'task_passed':grade.get('passed') if grade.get('status')=='graded' and r.get('status')=='completed' else None,'checks':grade.get('checks',[]),'seconds':r.get('seconds'),'usage':r.get('usage'),'read':r.get('read',{}),'model_requested':r.get('model_requested')}
   if states[arm]['task_passed'] is None:errors.append({'case':entry['case'],'arm':arm,'status':states[arm]['completion'],'grader':grade.get('status')})
  without,with_=states['without']['task_passed'],states['with']['task_passed']
  if without is not None and with_ is not None:
   valid+=1;wins+=int(with_ and not without);losses+=int(without and not with_);bothpass+=int(with_ and without);bothfail+=int(not with_ and not without)
  reads+=int(states['with']['read'].get('status')=='full_body_tool_output_observed')
  rows.append({'case':entry['case'],'arms':states})
 first_plan=json.loads((Path(frozen['entries'][0]['run'])/'plan.json').read_text())
 return {'public_fixture':frozen.get('public_fixture',False),'skill':first_plan['skills'][0],'family':frozen['family'],'mode':'native_installed','pairs_planned':frozen['pairs_planned'],'attempted_invocations':attempted,'completed_invocations':sum(s['completion']=='completed' for r in rows for s in r['arms'].values()),'both_pass':bothpass,'both_fail':bothfail,'treatment_only_wins':wins,'baseline_only_wins':losses,'read_observed_treatments':reads,'effect':effect(wins,losses,valid,frozen['pairs_planned']),'cases':rows,'missing_or_infrastructure':errors,'interval_method':'Bonferroni subtraction of two97.5% exact Clopper-Pearson marginal intervals; at least95% coverage for paired difference; no catalog-wide claim.','limit':str(frozen['pairs_planned'])+' planned paired case(s) on one CLI setup. '+frozen.get('scope','Prospective independent case set.')+' No pooling with inline-reference studies, no ranking by p-values, no inference that installed means read or used.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=summarize(a.manifest);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['cases','missing_or_infrastructure']}))
