"""Frozen synthetic outcome checks, authored independently of public skill instructions."""
import ast,copy,json,random,sys
from frozen_outcomes_v2 import load as restricted_load
TASKS=[
{'id':'atomic-stock-replay','skill':'67b1408b4733c4e8','checks':10,'prompt':'''Repair a stock event reducer. Return JSON {"code": "..."} implementing Python replay(initial, events). Standard library only, no I/O. initial is a dict of str SKU to exact nonnegative int (bool invalid). events is a list of dicts. Validate inputs; invalid raises ValueError and nothing mutates. Return {"stock": dict, "applied": list, "rejected": list}. Each event has nonempty str id and list moves; each move is [SKU, delta], SKU nonempty str, delta exact int. Extra keys are ignored. Invalid types/shapes raise ValueError even on duplicates or rejected events. For each event aggregate all deltas per SKU before checking feasibility. Reject if any resulting stock would be negative; append its id to rejected. Otherwise commit all moves atomically and append its id to applied. Unknown SKU starts at zero; a committed zero delta creates the SKU. Event ids are idempotency keys. Equality of duplicate content means equal aggregate mapping after dropping zero net deltas, independent of move order; duplicate with identical content is ignored entirely even if first occurrence rejected. Conflicting content for an existing id raises ValueError. Remember rejected ids too. Duplicate validation precedes ignoring it. Return lists follow first encounter order. Initial may contain empty SKU (preserve it) but moves may not. Empty moves is a valid committed event. Do not mutate or alias input initial/events; result stock must be separate. Broken code uses per-move balance checks, mutates initial and records ids only on success. Supply complete corrected function and imports.'''
},
{'id':'portable-archive-plan','skill':'0c66d793944e662f','checks':10,'prompt':'''Implement Python plan(entries) as JSON {"code": "..."}. No file or network operations. entries is a list of dicts with path (str), size (exact int >=0), kind ("file" or "dir"). Other fields ignored. Return ordered normalized file paths, excluding directory entries. Invalid input or conflict raises ValueError, never partially returns or mutates input. Validate ALL entries including dirs. Limits: <=100 files and sum of file sizes <=1,000,000 bytes. Dir size must be zero. Normalize Unicode path to NFC, replace backslashes with '/', then split; remove components exactly '.'; repeated '/' collapse. Reject leading slash, any '..' component, NUL or any Unicode control character category Cc, empty result, any colon in any component, trailing period or space in any component, and any Windows device component (case insensitive basename before FIRST period equals CON PRN AUX NUL COM1..COM9 or LPT1..LPT9). A trailing slash is allowed only for dirs, and only after normalization of separators. Reject file paths ending in slash. Case insensitive collision key is NFC normalized component.casefold() joined by '/'. Reject duplicate explicit entries of any kind, including identical dir entries. Also reject file/dir same key, and any file ancestor of another entry, whether explicit dir or file. Implicit parent dirs are allowed to later become an explicit dir ONCE. Preserve normalized component case in returned file strings and input order. A directory ancestor of another entry is valid. Reject malformed entries with ValueError (including booleans as size). Do not percent-decode; percent characters are literal. Empty entries returns []. Use only standard library. Supply complete function and imports.'''}]
# Expanded capabilities are frozen before any run, avoid the earlier execution-capability omission.
def load(code):
 import frozen_outcomes_v2 as base
 # Reuse AST capability restrictions but provide a complete ordinary pure-Python builtin set.
 tree=ast.parse(code)
 for n in ast.walk(tree):
  if isinstance(n,(ast.Import,ast.ImportFrom)):
   names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module]
   if any(x not in base.ALLOWED for x in names):raise ValueError('unsupported import')
  if isinstance(n,ast.Attribute) and n.attr.startswith('_'):raise ValueError('private attribute blocked')
  if isinstance(n,ast.Name) and (n.id.startswith('__') or n.id in {'open','eval','exec','compile','globals','locals','getattr','setattr','delattr','input','breakpoint','help','exit','quit'}):raise ValueError('unsupported capability')
 import builtins
 names='abs all any bool bytes bytearray callable chr dict enumerate filter float frozenset hash int isinstance issubclass iter len list map max min next object ord pow range repr reversed round set slice sorted str sum tuple type zip format Exception ValueError TypeError KeyError IndexError StopIteration UnicodeError OverflowError ArithmeticError RuntimeError AssertionError'.split()
 safe={k:getattr(builtins,k) for k in names}
 safe['__build_class__']=builtins.__build_class__
 safe['__import__']=lambda name,globals=None,locals=None,fromlist=(),level=0: __import__(name,globals,locals,fromlist,level) if name in base.ALLOWED else (_ for _ in ()).throw(ValueError('import blocked'))
 ns={'__builtins__':safe,'__name__':'submission'};exec(compile(tree,'submission','exec'),ns);return ns

def raises(f):
 try:f()
 except ValueError:return True
 return False

def reference_replay(initial,events):
 if not isinstance(initial,dict) or not isinstance(events,list) or any(not isinstance(k,str) or type(v)!=int or v<0 for k,v in initial.items()):raise ValueError()
 stock=dict(initial);seen={};applied=[];rejected=[]
 for event in events:
  if not isinstance(event,dict) or not isinstance(event.get('id'),str) or not event['id'] or not isinstance(event.get('moves'),list):raise ValueError()
  delta={}
  for m in event['moves']:
   if not isinstance(m,list) or len(m)!=2 or not isinstance(m[0],str) or not m[0] or type(m[1])!=int:raise ValueError()
   delta[m[0]]=delta.get(m[0],0)+m[1]
  signature={k:v for k,v in delta.items() if v}
  eid=event['id']
  if eid in seen:
   if seen[eid]!=signature:raise ValueError()
   continue
  seen[eid]=signature
  if any(stock.get(k,0)+v<0 for k,v in delta.items()):rejected.append(eid)
  else:
   for k,v in delta.items():stock[k]=stock.get(k,0)+v
   applied.append(eid)
 return {'stock':stock,'applied':applied,'rejected':rejected}

def e(i,*moves):return {'id':i,'moves':list(moves)}
def fentry(path,size=0,kind='file'):return {'path':path,'size':size,'kind':kind}
def stock_checks(f):
 def same(initial,events):
  before=copy.deepcopy((initial,events));r=f(initial,events);want=reference_replay(*before)
  return r==want and (initial,events)==before and r['stock'] is not initial
 def randomized():
  rng=random.Random(2601025)
  for case in range(80):
   initial={s:rng.randrange(8) for s in ['a','b','c']};events=[]
   for i in range(12):events.append(e(str(i),*[ [rng.choice(['a','b','c','d']),rng.randrange(-6,7)] for _ in range(rng.randrange(5))]))
   if not same(initial,events):return False
  return True
 return [
 ('empty-and-copy',lambda:same({},[]) and same({'':0},[])),
 ('aggregate-before-feasibility',lambda:same({'a':0},[e('x',['a',-5],['a',5])])),
 ('atomic-reject',lambda:same({'a':2,'b':0},[e('x',['a',3],['b',-1]),e('y',['a',-2])])),
 ('zero-creates-key',lambda:same({},[e('x',['z',0]),e('y')])),
 ('duplicate-permutation-zero',lambda:same({'a':3},[e('x',['a',-2],['b',0]),e('x',['a',-1],['a',-1]),e('y',['b',0])])),
 ('rejected-retry-stays-rejected',lambda:same({},[e('x',['a',-1]),e('s',['a',2]),e('x',['a',-1])])),
 ('conflicting-id',lambda:raises(lambda:f({'a':3},[e('x',['a',-1]),e('x',['a',-2])])) and raises(lambda:f({},[e('x',['a',-1]),e('x',['a',-2])]))),
 ('malformed-duplicate-still-validates',lambda:raises(lambda:f({},[e('x'),e('x',['a',False])])) and raises(lambda:f({},[e('x'),{'id':'x','moves':[('a',0)]}]))),
 ('input-shape-validation',lambda:all(raises(lambda i=i,v=v:f(i,v)) for i,v in [(None,[]),({},()),({'a':True},[]),({'a':-1},[]),({1:1},[]),({},[e('',['a',1])]),({},[e('x',['',1])]),({},[{'id':'x','moves':None}])])),
 ('seeded-replay-80',randomized)]
def archive_checks(f):
 def accept(entries,want):
  before=copy.deepcopy(entries);return f(entries)==want and entries==before
 def reject(*paths):return all(raises(lambda p=p:f([fentry(p)])) for p in paths)
 return [
 ('normalization-and-order',lambda:accept([fentry('A\\b.txt',2),fentry('x//./y',3),fentry('a/',0,'dir')],['A/b.txt','x/y'])),
 ('unicode-nfc-casefold-collisions',lambda:raises(lambda:f([fentry('café'),fentry('cafe\u0301')])) and raises(lambda:f([fentry('STRASSE/a'),fentry('Straße/A')]))),
 ('implicit-then-explicit-dir',lambda:accept([fentry('a/b'),fentry('A',0,'dir')],['a/b']) and accept([fentry('a',0,'dir'),fentry('A/b')],['A/b'])),
 ('duplicate-explicit-dirs',lambda:raises(lambda:f([fentry('a',0,'dir'),fentry('A/',0,'dir')]))),
 ('file-ancestor-both-orders',lambda:raises(lambda:f([fentry('a'),fentry('a/b',0,'dir')])) and raises(lambda:f([fentry('a/b'),fentry('A')])) and raises(lambda:f([fentry('a',0,'dir'),fentry('A')]))),
 ('traversal-and-control',lambda:reject('/a','\\a','a/../b','a\\..\\b','a/\x00x','a/\x85b', './', '')),
 ('device-and-ntfs-aliases',lambda:reject('aux.txt','x/COM9.more.txt','prn','x/a:stream','a./b','a /b','x/NuL.data')),
 ('literal-percent-and-ordinary-names',lambda:accept([fentry('%2e%2e/x'),fentry('COM10.txt'),fentry('console'),fentry('a...b')],['%2e%2e/x','COM10.txt','console','a...b'])),
 ('sizes-counts',lambda:accept([fentry(str(i),10000) for i in range(100)],[str(i) for i in range(100)]) and raises(lambda:f([fentry(str(i)) for i in range(101)])) and raises(lambda:f([fentry('a',1000001)]))),
 ('malformed-all-kinds',lambda:all(raises(lambda x=x:f(x)) for x in [None,{},[fentry('a',True)],[fentry('a',-1)],[fentry('a',1,'dir')],[fentry('a/',0,'file')],[fentry('a',0,'link')],[{}],[fentry(1)]]) and accept([],[]))]
def grade(case,code):
 ns=load(code);checks=stock_checks(ns['replay']) if case=='atomic-stock-replay' else archive_checks(ns['plan']);out=[]
 for name,check in checks:
  try:out.append({'name':name,'passed':bool(check()),'error':None})
  except Exception as ex:out.append({'name':name,'passed':False,'error':type(ex).__name__})
 return {'passed':sum(x['passed'] for x in out),'total':len(out),'outcomes':out}
if __name__=='__main__':
 d=json.load(sys.stdin)
 try:r=grade(d['case'],d['code'])
 except Exception as ex:r={'passed':0,'total':10,'error':type(ex).__name__+': '+str(ex)}
 print(json.dumps(r))
