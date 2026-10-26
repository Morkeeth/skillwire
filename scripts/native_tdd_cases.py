"""Independent public API contracts and plausible mutants for native TDD trials.
These are prospective fixtures; no task assertion is drawn from skill text.
"""
import argparse,datetime,hashlib,json,random,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lime_task_eval as t

def cases():
 return [
 ('version-ties','latest(rows): return dict rows selected per id by greatest integer version, breaking equal versions by last occurrence. Preserve first-seen id order and never mutate inputs.', 'latest',
 "def latest(rows):\n out={}\n for r in rows:\n  if r['id'] not in out or r['version']>=out[r['id']]['version']:out[r['id']]=dict(r)\n return list(out.values())\n",
 ["def latest(rows):\n return list({r['id']:r for r in rows}.values())\n", "def latest(rows):\n out={}\n for r in rows:\n  if r['id'] not in out or r['version']>out[r['id']]['version']:out[r['id']]=r\n return list(out.values())\n", "def latest(rows):\n return sorted(rows,key=lambda r:r['id'])\n"],
 [([ [{'id':'b','version':7,'v':'high'},{'id':'a','version':3},{'id':'b','version':7,'v':'last'},{'id':'b','version':2}] ],[{'id':'b','version':7,'v':'last'},{'id':'a','version':3}]),([[]],[])]),
 ('utf8-cap','truncate(text, cap): longest Unicode-codepoint prefix whose UTF-8 encoding fits nonnegative byte cap. Do not split codepoints. Return empty for cap zero; never mutate inputs.', 'truncate',
 "def truncate(text,cap):\n out=''\n for c in text:\n  if len((out+c).encode('utf-8'))>cap:break\n  out+=c\n return out\n",
 ["def truncate(text,cap):return text[:cap]\n", "def truncate(text,cap):return text.encode()[:cap].decode(errors='replace')\n", "def truncate(text,cap):return ''.join(c for c in text if len(c.encode())<=cap)\n"],
 [(['Aé🙂Z',6],'Aé'),(['éx',1],''),(['z',0],''),(['abc',2],'ab'),(['🙂a',5],'🙂a')]),
 ('idempotent-transactions','balance(start, events): each event is {id,delta}. Apply only the first occurrence of each id, even if duplicate content differs. Return final integer. Never mutate events.', 'balance',
 "def balance(start,events):\n seen=set()\n for e in events:\n  if e['id'] not in seen:start+=e['delta'];seen.add(e['id'])\n return start\n",
 ["def balance(start,events):return start+sum(e['delta'] for e in events)\n", "def balance(start,events):return start+sum({e['id']:e['delta'] for e in events}.values())\n", "def balance(start,events):return start+sum(e['delta'] for e in events if e['delta']>0)\n"],
 [([10,[{'id':'a','delta':-2},{'id':'a','delta':8},{'id':'b','delta':3}]],11),([0,[]],0),([5,[{'id':'x','delta':-5},{'id':'x','delta':-5}]],0)]),
 ('atomic-stock','update(stock, changes): changes is [[key,delta],...]. Apply in order to a copy; if any intermediate value would be negative or key absent return {ok:False,stock:original copy}; else {ok:True,stock:updated}. Never mutate stock/changes.', 'update',
 "def update(stock,changes):\n out=dict(stock)\n for k,d in changes:\n  if k not in out or out[k]+d<0:return {'ok':False,'stock':dict(stock)}\n  out[k]+=d\n return {'ok':True,'stock':out}\n",
 ["def update(stock,changes):\n out=dict(stock)\n for k,d in changes:\n  if k not in out or out[k]+d<0:return {'ok':False,'stock':out}\n  out[k]+=d\n return {'ok':True,'stock':out}\n", "def update(stock,changes):\n out=dict(stock)\n for k,d in changes:out[k]=out.get(k,0)+d\n return {'ok':all(v>=0 for v in out.values()),'stock':out}\n", "def update(stock,changes):\n for k,d in changes:stock[k]=stock.get(k,0)+d\n return {'ok':True,'stock':stock}\n"],
 [([{'a':2,'b':1},[['a',-1],['b',-2]]],{'ok':False,'stock':{'a':2,'b':1}}),([{'a':0},[['a',-1],['a',1]]],{'ok':False,'stock':{'a':0}}),([{},[['x',1]]],{'ok':False,'stock':{}}),([{'a':1},[['a',2]]],{'ok':True,'stock':{'a':3}})]),
 ('url-origin','allowed(url): accept only https URLs on hostname example.com (case insensitive), default or explicit443 port, no username/password, whose path is exactly /app or starts /app/. Reject malformed URLs. Ignore query and fragment.', 'allowed',
 "from urllib.parse import urlsplit\ndef allowed(url):\n try:\n  u=urlsplit(url);return u.scheme.lower()=='https' and u.hostname=='example.com' and u.port in (None,443) and u.username is None and u.password is None and (u.path=='/app' or u.path.startswith('/app/'))\n except ValueError:return False\n",
 ["def allowed(url):return url.startswith('https://example.com/app')\n", "from urllib.parse import urlsplit\ndef allowed(url):\n u=urlsplit(url);return u.hostname is not None and u.hostname.endswith('example.com') and u.path.startswith('/app')\n", "from urllib.parse import urlsplit\ndef allowed(url):\n u=urlsplit(url);return u.scheme=='https' and u.hostname=='example.com' and u.path.startswith('/app/')\n"],
 [(['https://example.com/app'],True),(['https://EXAMPLE.com:443/app/x?q=1'],True),(['https://example.com/apple'],False),(['https://evilexample.com/app/'],False),(['https://user@example.com/app/'],False),(['https://example.com:444/app/'],False),(['http://example.com/app/'],False),(['https://example.com:bad/app'],False)]),
 ('quoted-csv','parse(text): parse RFC-style comma-separated rows including quoted commas, escaped quotes and embedded newlines. Accept CRLF and LF. Return list of lists of strings, no extra empty trailing row.', 'parse',
 "import csv,io\ndef parse(text):return list(csv.reader(io.StringIO(text,newline='')))\n",
 ["def parse(text):return [r.split(',') for r in text.splitlines()]\n", "import csv\ndef parse(text):return list(csv.reader(text.splitlines()))\n", "import csv,io\ndef parse(text):return list(csv.reader(io.StringIO(text.replace('\\r\\n',''))))\n"],
 [(['a,"b,c"\r\n"d\ne","f""g"\r\n'],[['a','b,c'],['d\ne','f"g']]),(['x,y\nz,w\n'],[['x','y'],['z','w']]),([''],[])]),
 ('timezone-days','group(stamps, offset): ISO8601 timestamps with offsets or Z are absolute instants. Return counts by YYYY-MM-DD in fixed integer offset minutes, sorted by date insertion order. Empty input gives {}.', 'group',
 "from datetime import datetime,timedelta,timezone\ndef group(stamps,offset):\n out={}\n for s in stamps:\n  key=datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(timezone(timedelta(minutes=offset))).date().isoformat();out[key]=out.get(key,0)+1\n return dict(sorted(out.items()))\n",
 ["def group(stamps,offset):\n out={}\n for s in stamps:out[s[:10]]=out.get(s[:10],0)+1\n return out\n", "from datetime import datetime,timedelta\ndef group(stamps,offset):\n out={}\n for s in stamps:\n  k=(datetime.fromisoformat(s.replace('Z','+00:00'))+timedelta(hours=offset)).date().isoformat();out[k]=out.get(k,0)+1\n return out\n", "def group(stamps,offset):return {}\n"],
 [([['2026-10-25T23:45:00Z','2026-10-26T01:00:00+02:00'],60],{'2026-10-26':2}),([['2026-01-01T00:10:00Z'],-30],{'2025-12-31':1}),([[],0],{})]),
 ('stable-missing-sort','sort_rows(rows): return rows sorted ascending by numeric score, missing or None scores last. Preserve input order for ties and for missing rows. Never mutate any input.', 'sort_rows',
 "def sort_rows(rows):return sorted(rows,key=lambda r:(r.get('score') is None,r.get('score') if r.get('score') is not None else 0))\n",
 ["def sort_rows(rows):return sorted(rows,key=lambda r:r.get('score') or 0)\n", "def sort_rows(rows):return sorted(rows,key=lambda r:(r.get('score') is None,r.get('score') or 0,r['id']))\n", "def sort_rows(rows):\n rows.sort(key=lambda r:(r.get('score') is None,r.get('score') or 0));return rows\n"],
 [([[{'id':'z','score':2},{'id':'b'},{'id':'a','score':2},{'id':'x','score':None},{'id':'n','score':-1}]], [{'id':'n','score':-1},{'id':'z','score':2},{'id':'a','score':2},{'id':'b'},{'id':'x','score':None}]),([[]],[])]),
 ('windows-alias','safe(name): validate ONE portable filename component. Reject empty, dot/dotdot, slash/backslash, ASCII control characters, <>:"|?*, trailing dot or space, and Windows device basename CON PRN AUX NUL COM1..9 LPT1..9 before first dot, case-insensitive. Accept ordinary Unicode. Return bool.', 'safe',
 "def safe(name):\n if not name or name in ('.','..') or name[-1] in '. ' or any(ord(c)<32 or c in '/\\\\<>:\"|?*' for c in name):return False\n stem=name.split('.')[0].upper();return stem not in {'CON','PRN','AUX','NUL'}|{'COM'+str(i) for i in range(1,10)}|{'LPT'+str(i) for i in range(1,10)}\n",
 ["def safe(name):return bool(name) and '/' not in name\n", "def safe(name):return bool(name) and name.upper() not in {'CON','PRN','AUX','NUL'}\n", "def safe(name):return name.isascii() and name.isalnum()\n"],
 [(['con.txt'],False),(['LPT9.md'],False),(['COM10'],True),(['note.'],False),(['x\\y'],False),([''],False),(['résumé.txt'],True),(['..'],False),(['good-name_1.md'],True),(['bad\x01'],False)]),
 ('empty-no-mutation','unique(rows): return first occurrence of each hashable item in order, without mutating input. Empty input returns a new empty list. Equality follows Python item equality.', 'unique',
 "def unique(rows):\n out=[]\n for x in rows:\n  if x not in out:out.append(x)\n return out\n",
 ["def unique(rows):return sorted(set(rows))\n", "def unique(rows):\n if not rows:return None\n return list(dict.fromkeys(rows))\n", "def unique(rows):\n out=list(dict.fromkeys(rows));rows[:]=out;return rows\n"],
 [([[]],[]),([[3,1,3,2,1]],[3,1,2]),([['z','a','z']],['z','a'])])
 ]

GRADER='''import argparse,copy,json,os,subprocess,sys,tempfile,shutil
from pathlib import Path
SPEC=__SPEC__
PREFIX=json.loads(os.environ.get('LIME_NATIVE_SANDBOX','[]'));TRACE=[]
BODY="import copy,json,runpy,sys;sys.dont_write_bytecode=True;args=json.loads(sys.stdin.read());before=copy.deepcopy(args);m=runpy.run_path(sys.argv[1]);value=m[sys.argv[2]](*args);print(json.dumps({'value':value,'unchanged':args==before}))"
def child(directory,code,arguments,stdin=None):
 env={k:os.environ[k] for k in ['PATH','LANG'] if k in os.environ};tmp=directory/'.tmp';tmp.mkdir(exist_ok=True);env['TMPDIR']=str(tmp)
 cmd=PREFIX+(['-C',str(directory),'--'] if PREFIX else [])+[sys.executable,'-I','-c',code]+arguments
 try:
  result=subprocess.run(cmd,cwd=directory,input=stdin,capture_output=True,text=True,timeout=2,env=env);TRACE.append({'argv':cmd,'stdin':stdin,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
  return result
 except subprocess.TimeoutExpired:
  TRACE.append({'argv':cmd,'stdin':stdin,'error':'timeout'});return None
def tests(artifact,implementation):
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp);(p/'app.py').write_text(implementation)
  source=artifact/'test_app.py'
  if not source.is_file():return False
  shutil.copyfile(source,p/'test_app.py')
  code="import sys,unittest;sys.path.insert(0,sys.argv[1]);s=unittest.defaultTestLoader.discover(sys.argv[1],pattern='test_app.py');r=unittest.TextTestRunner().run(s);sys.exit(0 if r.testsRun>0 and r.wasSuccessful() else 1)"
  r=child(p,code,[str(p)])
  return r is not None and r.returncode==0
p=argparse.ArgumentParser();p.add_argument('--artifact',type=Path,required=True);a=p.parse_args();checks=[]
# Prove child execution itself works; setup failure is infrastructure, not task failure.
with tempfile.TemporaryDirectory() as tmp:
 calibration=child(Path(tmp),"print('GRADER_CHILD_OK')",[])
 if calibration is None or calibration.returncode!=0 or calibration.stdout.strip()!='GRADER_CHILD_OK':
  if os.environ.get('LIME_GRADER_TRACE'):Path(os.environ['LIME_GRADER_TRACE']).write_text(json.dumps(TRACE,indent=2))
  print(json.dumps({'error':'grader child sandbox calibration failed'}));sys.exit(2)
# Expected outputs stay in this parent process. Generated code runs only in a child.
with tempfile.TemporaryDirectory() as tmp:
 directory=Path(tmp);source=a.artifact/'app.py'
 if source.is_file():shutil.copyfile(source,directory/'app.py')
 for i,(args,expected) in enumerate(SPEC['tests']):
  r=child(directory,BODY,[str(directory/'app.py'),SPEC['function']],json.dumps(args))
  try:d=json.loads(r.stdout);passed=r.returncode==0 and d['value']==expected and d['unchanged'] is True
  except Exception:passed=False
  checks.append({'name':'public-behavior-'+str(i+1),'passed':bool(passed)})
try:
 checks.append({'name':'submitted-tests-accept-correct','passed':tests(a.artifact,SPEC['good'])})
 for i,bad in enumerate(SPEC['mutants']):checks.append({'name':'submitted-tests-kill-mutant-'+str(i+1),'passed':not tests(a.artifact,bad) and (a.artifact/'test_app.py').is_file()})
except Exception:checks.append({'name':'submitted-tests-executable','passed':False})
if os.environ.get('LIME_GRADER_TRACE'):Path(os.environ['LIME_GRADER_TRACE']).write_text(json.dumps(TRACE,indent=2))
print(json.dumps({'checks':checks,'execution':'restricted child' if PREFIX else 'trusted authored controls only'}))
'''

def build(base,stack):
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');family=base/'frozen'/('tdd-'+stamp);family.mkdir(parents=True,exist_ok=False)
 order=[True]*5+[False]*5;seed=483991;random.Random(seed).shuffle(order);entries=[]
 for i,(name,contract,function,good,mutants,tests) in enumerate(cases()):
  case=family/name;case.mkdir();spec={'function':function,'good':good,'mutants':mutants,'tests':tests}
  for label,impl in [('bug',mutants[0]),('good',good)]+[('bad'+str(k),v) for k,v in enumerate(mutants)]:
   d=case/label;d.mkdir();(d/'app.py').write_text(impl)
   # Literal independent assertions also ensure controls have real submitted tests.
   test='import unittest,copy\nfrom app import '+function+'\nclass ContractTests(unittest.TestCase):\n def test_contract(self):\n'
   for args,expected in tests:test+='  args='+repr(args)+';before=copy.deepcopy(args);self.assertEqual('+function+'(*args),'+repr(expected)+');self.assertEqual(args,before)\n'
   (d/'test_app.py').write_text(test if label!='bug' else 'import unittest\n# Existing project has no regression test for this bug yet.\n')
  (case/'TASK.md').write_text('Repair app.py and add independent unittest regression tests in test_app.py. Agreed public seam: app.'+function+'. '+contract+'\nRun the submitted tests. Keep the public API and use Python standard library only. Do not change this task file. Deliver repaired app.py and test_app.py.\n')
  (case/'grader.py').write_text(GRADER.replace('__SPEC__',repr(spec)))
  control=[]
  for k in range(3):control.append(t.judge(case/'grader.py',case/('bad'+str(k)),case/('bad-control-'+str(k))))
  assert all(c['status']=='graded' and c['passed'] is False for c in control),(name,control)
  run=base/'evaluator'/('tdd-'+name+'-'+stamp)
  t.prepare(argparse.Namespace(fixture=case/'bug',reference=case/'good',negative=case/'bad0',task=case/'TASK.md',grader=case/'grader.py',stack=stack,skill=None,out=run,trust_grader=True))
  protocol={'task_runner_sha256':t.sha(Path(t.__file__).read_bytes()),'adapter_sha256':t.sha((Path(__file__).resolve().parents[1]/'lime_agent_eval.py').read_bytes()),'mode':'native_installed','model':'gpt-5.6-sol','reasoning':'low','harness':'codex','tools':'local_shell','budget':{'max_cli_trials':2,'timeout_seconds':360},'arm_order':['without','with'] if order[i] else ['with','without'],'case':name,'study':'selected-five-tdd-main','source_independent_contract':True}
  (run/'protocol.json').write_text(json.dumps(protocol,indent=2));t.seal(argparse.Namespace(run=run));entries.append({'case':name,'run':str(run),'grader_sha256':t.sha((case/'grader.py').read_bytes()),'control_results':control})
 manifest={'public_fixture':True,'family':'tdd','frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seed':seed,'pairs_planned':10,'entries':entries,'source_stack_sha256':t.sha(stack.read_bytes()),'outcome':'All independent behavior checks and submitted regression tests must pass; tests accept good implementation and reject three fixed plausible mutants. No tests-first/style criterion.'}
 (family/'FROZEN.json').write_text(json.dumps(manifest,indent=2));print('FROZEN FAMILY',family,flush=True)
 return family
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--stack',type=Path,required=True);a=p.parse_args();build(a.base,a.stack)
