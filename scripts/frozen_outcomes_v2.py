"""Independent observable outcomes for original synthetic Python tasks. No skill-text checks."""
from decimal import Decimal,ROUND_HALF_UP
import ast,types,urllib.parse
TASKS=[
 dict(id='money-totals',skill='f37b3e44c1645b37',prompt='Write Python function totals(rows). Each row is a dict with account and amount strings. Ignore rows whose amount is not a finite decimal. Strip account whitespace. Sum exact decimal amounts by account, rounding each final account total to 2 decimals with ROUND_HALF_UP. Return a dict of account to two-decimal strings, including negative values and empty account keys. Do not modify input rows. Use standard library only. Return JSON with a single code string containing function and necessary imports.',checks=6),
 dict(id='table-dedup',skill='f37b3e44c1645b37',prompt='Write Python function latest(rows). Each row has id and integer version. Return one original row per id: the greatest version wins; for equal versions the last row wins. Output order follows the first appearance of each id. Empty input returns []. Do not mutate rows or input. Return JSON with a single code string containing function and necessary standard-library imports.',checks=6),
 dict(id='escaped-record',skill='67b1408b4733c4e8',prompt='Fix this parser by returning complete Python function split_record(text): return text.split("|"). Required grammar: unescaped | separates fields, backslash escapes the next character (including | or backslash), a terminal unpaired backslash raises ValueError. Empty text is one empty field. Empty trailing fields must be kept. Return JSON with a single code string containing function and necessary standard-library imports.',checks=6),
 dict(id='time-window',skill='67b1408b4733c4e8',prompt='Fix Python function in_window(t,start,end) whose broken implementation is start <= t <= end. Inputs are minute-of-day integers 0..1439. Window start is inclusive and end exclusive. A window may cross midnight. start == end means empty, never a full day. Invalid input (including booleans or non-integers) raises ValueError. Return JSON with a single code string containing function and necessary standard-library imports.',checks=6),
 dict(id='redirect-policy',skill='0c66d793944e662f',prompt='Implement Python function allowed_redirect(url). Accept an absolute URL only when scheme is https, hostname is exactly example.com or www.example.com (case-insensitive), there is no username or password, and explicit port is absent or 443. Reject whitespace anywhere, backslashes anywhere, control characters, malformed port, relative and protocol-relative URLs, subdomains and lookalike suffixes. Return bool; never throw on a non-string input. You may import urllib.parse. No network or file access. Return JSON with a single code string containing function and necessary standard-library imports.',checks=6),
 dict(id='safe-filename',skill='0c66d793944e662f',prompt='Implement Python function valid_filename(name). Return True only for a nonempty ASCII string of at most 80 characters, composed solely of letters, digits, period, underscore and hyphen, that is neither . nor .., does not start with a period, and contains no run of two consecutive periods. Return False for nonstrings. No file operations or imports required. Return JSON with a single code string containing the function.',checks=6)
]
ALLOWED={'decimal','urllib.parse','re','math','collections','copy','unicodedata'}
def load(code):
    tree=ast.parse(code)
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):
            names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module]
            if any(x not in ALLOWED for x in names):raise ValueError('unsupported import')
        if isinstance(n,ast.Attribute) and n.attr.startswith('_'):raise ValueError('private attribute blocked')
        if isinstance(n,ast.Name) and (n.id.startswith('__') or n.id in {'open','eval','exec','compile','globals','locals','getattr','setattr','delattr','input','breakpoint','help','exit','quit'}):raise ValueError('unsupported capability')
    builtins=__import__('builtins');safe={k:getattr(builtins,k) for k in ['format','ord','chr','UnicodeError','KeyError','IndexError','abs','all','any','bool','dict','enumerate','filter','float','int','isinstance','len','list','map','max','min','range','repr','reversed','round','set','sorted','str','sum','tuple','type','zip','ValueError','TypeError','Exception']}
    safe['__import__']=lambda name,globals=None,locals=None,fromlist=(),level=0: __import__(name,globals,locals,fromlist,level) if name in ALLOWED else (_ for _ in ()).throw(ValueError('import blocked'))
    ns={'__builtins__':safe};exec(compile(tree,'submission','exec'),ns);return ns

def grade(case,code):
    ns=load(code);tests=[]
    if case=='money-totals':
        f=ns['totals'];tests=[lambda:f([])=={},lambda:f([{'account':' A ','amount':'0.1'},{'account':'A','amount':'0.2'}])=={'A':'0.30'},lambda:f([{'account':'x','amount':'1.005'}])=={'x':'1.01'},lambda:f([{'account':'x','amount':'-1.005'}])=={'x':'-1.01'},lambda:f([{'account':'','amount':'NaN'},{'account':'','amount':'Infinity'},{'account':'','amount':'3'}])=={'':'3.00'},lambda:f([{'account':'a','amount':'bad'},{'account':'b','amount':'0'}])=={'b':'0.00'}]
    elif case=='table-dedup':
        f=ns['latest'];r=[{'id':'a','version':2,'x':'first'},{'id':'b','version':9},{'id':'a','version':2,'x':'last'},{'id':'a','version':1}];tests=[lambda:f([])==[],lambda:f(r)==[r[2],r[1]],lambda:f([{'id':0,'version':-1},{'id':0,'version':0}])==[{'id':0,'version':0}],lambda:f([{'id':'x','version':-4}])==[{'id':'x','version':-4}],lambda:f([{'id':'','version':0}])==[{'id':'','version':0}],lambda:not_mutated(f,r)]
    elif case=='escaped-record':
        f=ns['split_record'];tests=[lambda:f('')==[''],lambda:f('a|')==['a',''],lambda:f('|a||')==['','a','',''],lambda:f(r'a\|b|c')==['a|b','c'],lambda:f(r'a\\|b')==['a\\','b'],lambda:raises(lambda:f('a\\'))]
    elif case=='time-window':
        f=ns['in_window'];tests=[lambda:f(60,60,90) is True and f(90,60,90) is False,lambda:f(1430,1400,30) is True and f(20,1400,30) is True,lambda:f(30,1400,30) is False and f(60,1400,30) is False,lambda:f(10,10,10) is False,lambda:raises(lambda:f(True,0,2)) and raises(lambda:f(1.0,0,2)),lambda:raises(lambda:f(1440,0,1)) and raises(lambda:f(1,-1,5))]
    elif case=='redirect-policy':
        f=ns['allowed_redirect'];tests=[lambda:all(f(u) is True for u in ['https://example.com','https://WWW.EXAMPLE.COM:443/a?q=1']),lambda:all(f(u) is False for u in ['http://example.com','//example.com','/path']),lambda:all(f(u) is False for u in ['https://example.com.evil.test','https://a.example.com','https://example.com@evil.test','https://x@example.com']),lambda:all(f(u) is False for u in ['https://example.com:444','https://example.com:bad','https://example.com:99999']),lambda:all(f(u) is False for u in ['https://example.com/a b','https://example.com\\x','https://example.com\n',' https://example.com']),lambda:all(f(u) is False for u in [None,2,{},'https://example.com\x00'])]
    elif case=='safe-filename':
        f=ns['valid_filename'];tests=[lambda:all(f(n) is True for n in ['a','file.txt','A-Z_09','a'*80]),lambda:all(f(n) is False for n in ['',None,0,False]),lambda:all(f(n) is False for n in ['.','..','.hidden','a..b']),lambda:all(f(n) is False for n in ['../file','a/b','a\\b','a:b']),lambda:all(f(n) is False for n in ['é','中文','a\n','a b','a\x00']),lambda:f('a'*81) is False]
    outcomes=[]
    for n,t in enumerate(tests,1):
        try:outcomes.append({'check':n,'passed':bool(t()),'error':None})
        except Exception as e:outcomes.append({'check':n,'passed':False,'error':type(e).__name__})
    return {'passed':sum(t['passed'] for t in outcomes),'total':len(outcomes),'outcomes':outcomes}
def raises(f):
    try:f()
    except ValueError:return True
    return False
def not_mutated(f,rows):
    import copy
    before=copy.deepcopy(rows);f(rows);return rows==before
if __name__=='__main__':
    import json,sys
    data=json.load(sys.stdin)
    try:result=grade(data['case'],data['code'])
    except Exception as e:result={'passed':0,'total':6,'error':type(e).__name__+': '+str(e)}
    print(json.dumps(result))
