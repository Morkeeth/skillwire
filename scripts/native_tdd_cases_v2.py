"""Build a new sealed TDD family after auditing the v1 task/reference contract.

This never reads or changes v1 outcomes and never invokes a model. The public
contracts below were written from the task intent, not from the selected skill.
"""
import argparse
import datetime
import hashlib
import json
import random
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lime_task_eval as task_eval
import native_tdd_cases as v1


DOMAINS = {
    'version-ties': 'Input rows are a list of dictionaries with hashable ids and integer versions. The returned rows are shallow copies in first-seen id order.',
    'utf8-cap': 'Input text is a string and cap is a nonnegative integer. Prefix means a contiguous prefix of Unicode codepoints.',
    'idempotent-transactions': 'Input start and deltas are integers; event ids are hashable. A repeated id never applies a second delta.',
    'atomic-stock': 'Input stock maps string keys to nonnegative integer quantities; deltas are integers. A failed change returns a fresh copy of the original stock.',
    'url-origin': 'Input may be any value: non-strings return False. A valid URL has no raw whitespace, ASCII control, DEL or backslash; every percent sign must be followed by two hex digits. An empty explicit port, invalid port or malformed host is rejected. Host and scheme ignore case; path is case-sensitive. An explicit decimal port must equal 443.',
    'quoted-csv': 'Input is a string containing well-formed comma-separated records. Quoted fields may contain comma, double-quote escapes and CRLF or LF newlines. Malformed quoting is outside this task.',
    'timezone-days': 'Input stamps are ISO8601 strings with an explicit numeric offset or terminal Z. A timestamp lacking an offset raises ValueError. Input offset is an integer minute count in the valid fixed-offset range (-1439 to 1439).',
    'stable-missing-sort': 'Input rows are dictionaries; present scores are finite int or float values. Missing and None scores share the final stable group.',
    'windows-alias': 'Input may be any value: non-strings return False. ASCII control characters include U+0000 through U+001F and U+007F DEL. Compare the device basename before the first dot after removing trailing spaces from that basename.',
    'empty-no-mutation': 'Input is a list of hashable values. Equality decides duplicates; the result is a new list, including for empty input.',
}

GOOD = {
    'url-origin': '''import re
from urllib.parse import urlsplit

def allowed(url):
    if not isinstance(url, str) or not url or any(ord(c) < 33 or ord(c) == 127 for c in url):
        return False
    if '\\\\' in url or re.search(r'%(?![0-9A-Fa-f]{2})', url):
        return False
    try:
        parts = urlsplit(url)
        authority = parts.netloc.rsplit('@', 1)[-1]
        return (parts.scheme.lower() == 'https' and parts.hostname == 'example.com'
                and authority != '' and not authority.endswith(':')
                and parts.port in (None, 443) and parts.username is None
                and parts.password is None
                and (parts.path == '/app' or parts.path.startswith('/app/')))
    except (TypeError, ValueError):
        return False
''',
    'timezone-days': '''from datetime import datetime, timedelta, timezone

def group(stamps, offset):
    zone = timezone(timedelta(minutes=offset))
    result = {}
    for stamp in stamps:
        instant = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError('Timestamp needs an explicit offset or Z')
        day = instant.astimezone(zone).date().isoformat()
        result[day] = result.get(day, 0) + 1
    return dict(sorted(result.items()))
''',
    'windows-alias': '''def safe(name):
    if not isinstance(name, str) or not name or name in ('.', '..') or name[-1] in '. ':
        return False
    if any(ord(c) < 32 or ord(c) == 127 or c in '/\\\\<>:"|?*' for c in name):
        return False
    stem = name.split('.')[0].rstrip(' ').upper()
    devices = {'CON', 'PRN', 'AUX', 'NUL'} | {'COM' + str(i) for i in range(1, 10)} | {'LPT' + str(i) for i in range(1, 10)}
    return stem not in devices
''',
}

EXTRA_PUBLIC = {
    'url-origin': [([42], False), (['https://example.com:/app'], False),
                   ([' https://example.com/app'], False),
                   (['https://example.com/app/%ZZ'], False),
                   (['HTTPS://EXAMPLE.COM:443/app'], True)],
    'windows-alias': [(['file\x7f'], False), (['CON .txt'], False)],
}

# These samples are separate from the grader's public vectors. Each one checks
# the intended contract directly against the reference and the original bug.
ORACLE = {
    'version-ties': ([ [{'id':'x','version':1},{'id':'y','version':2},{'id':'x','version':3},{'id':'x','version':0}] ], [{'id':'x','version':3},{'id':'y','version':2}]),
    'utf8-cap': (['🙂éZ', 5], '🙂'),
    'idempotent-transactions': ([4,[{'id':'a','delta':2},{'id':'a','delta':100},{'id':'b','delta':-1}]], 5),
    'atomic-stock': ([{'x':2},[['x',-1],['x',-2]]], {'ok':False,'stock':{'x':2}}),
    'url-origin': (['https://example.com/application'], False),
    'quoted-csv': (['"a,b",c\r\n'], [['a,b','c']]),
    'timezone-days': ([['2026-01-01T00:10:00Z'], -30], {'2025-12-31':1}),
    'stable-missing-sort': ([[{'id':'a'},{'id':'b','score':0},{'id':'c','score':-2}]], [{'id':'c','score':-2},{'id':'b','score':0},{'id':'a'}]),
    'windows-alias': (['file\x7f'], False),
    'empty-no-mutation': ([[2,1,2]], [2,1]),
}


def cases():
    result=[]
    for name,contract,function,old_good,mutants,tests in v1.cases():
        assert name in DOMAINS and name in ORACLE
        result.append((name,contract+' '+DOMAINS[name],function,GOOD.get(name,old_good),mutants,tests+EXTRA_PUBLIC.get(name,[])))
    assert len(result)==10
    return result


def create_stack(old_run, destination):
    """Repackage identical pinned source bytes from v1, with original metadata."""
    manifest=json.loads((old_run/'SKILL-SOURCES.json').read_text())
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as target:
        target.writestr('SKILL-SOURCES.json',json.dumps(manifest))
        for skill in manifest['skills']:
            for entry in skill['files']:
                path=skill['folder']+'/'+entry['path']
                raw=(old_run/'with/.agents/skills'/path).read_bytes()
                assert hashlib.sha256(raw).hexdigest()==entry['sha256']
                target.writestr(path,raw)
    return manifest


def test_source(function,source,args,expected):
    scope={}
    exec(compile(source,'<authored-contract-reference>','exec'),scope)
    return scope[function](*args)==expected


def build(base,old_family):
    base.mkdir(parents=True,exist_ok=False)
    old=json.loads((old_family/'FROZEN.json').read_text())
    assert len(old['entries'])==10
    stack=base/'PINNED-SOURCE.zip'
    source_manifest=create_stack(Path(old['entries'][0]['run']),stack)
    orders=[True]*5+[False]*5
    seed=779221
    random.Random(seed).shuffle(orders)
    entries=[]
    for i,(name,contract,function,good,mutants,tests) in enumerate(cases()):
        old_entry=old['entries'][i]
        assert old_entry['case']==name
        case=base/'cases'/name;case.mkdir(parents=True)
        spec={'function':function,'good':good,'mutants':mutants,'tests':tests}
        args,expected=ORACLE[name]
        assert test_source(function,good,args,expected),(name,'reference oracle')
        assert not test_source(function,mutants[0],args,expected),(name,'bug oracle')
        # Keep the exact v1 starting fixture. Changing even its comments would
        # create a different baseline while the question is about the judge.
        shutil.copytree(Path(old_entry['run'])/'without',case/'bug')
        for label,implementation in [('good',good)]+[('bad'+str(k),code) for k,code in enumerate(mutants)]:
            folder=case/label;folder.mkdir();(folder/'app.py').write_text(implementation)
            test='import unittest,copy\nfrom app import '+function+'\nclass ContractTests(unittest.TestCase):\n def test_contract(self):\n'
            for inputs,want in tests:
                test+='  args='+repr(inputs)+';before=copy.deepcopy(args);self.assertEqual('+function+'(*args),'+repr(want)+');self.assertEqual(args,before)\n'
            if name=='timezone-days':
                test+=' def test_naive_timestamp_rejected(self):\n  with self.assertRaises(ValueError):group(["2026-05-01T12:00:00"],0)\n'
            if name=='windows-alias':
                test+=' def test_nonstring_rejected(self):\n  self.assertFalse(safe(b"file"))\n'
            (folder/'test_app.py').write_text(test)
        (case/'TASK.md').write_text('Repair app.py and add independent unittest regression tests in test_app.py. Agreed public seam: app.'+function+'. '+contract+'\nRun the submitted tests. Keep the public API and use Python standard library only. Do not change this task file. Deliver repaired app.py and test_app.py.\n')
        (case/'grader.py').write_text(v1.GRADER.replace('__SPEC__',repr(spec)))
        mutant_controls=[task_eval.judge(case/'grader.py',case/('bad'+str(k)),case/('bad-control-'+str(k))) for k in range(3)]
        assert all(x['status']=='graded' and x['passed'] is False for x in mutant_controls),(name,mutant_controls)
        run=base/'evaluator'/name
        task_eval.prepare(argparse.Namespace(fixture=case/'bug',reference=case/'good',negative=case/'bad0',task=case/'TASK.md',grader=case/'grader.py',stack=stack,skill=None,skill_folder=None,out=run,trust_grader=True))
        plan=json.loads((run/'plan.json').read_text())
        assert plan['ready'] and plan['controls']['reference']['passed'] is True and plan['controls']['deliberately_bad']['passed'] is False
        old_sources=json.loads((Path(old_entry['run'])/'SKILL-SOURCES.json').read_text())
        assert json.loads((run/'SKILL-SOURCES.json').read_text())==old_sources
        protocol={'task_runner_sha256':task_eval.sha(Path(task_eval.__file__).read_bytes()),'adapter_sha256':task_eval.sha((Path(__file__).resolve().parents[1]/'lime_agent_eval.py').read_bytes()),'mode':'native_installed','model':'gpt-5.6-sol','reasoning':'low','harness':'codex','tools':'local_shell','budget':{'max_cli_trials':2,'timeout_seconds':360},'arm_order':['without','with'] if orders[i] else ['with','without'],'case':name,'study':'tdd-v2-contract-repair','source_independent_contract':True,'inference_authorized':False}
        (run/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
        task_eval.seal(argparse.Namespace(run=run))
        entries.append({'case':name,'run':str(run),'task_sha256':task_eval.sha((case/'TASK.md').read_bytes()),'grader_sha256':task_eval.sha((case/'grader.py').read_bytes()),'reference_sha256':task_eval.sha((case/'good/app.py').read_bytes()),'v1_task_sha256':task_eval.sha((Path(old_entry['run'])/'TASK.md').read_bytes()),'v1_grader_sha256':old_entry['grader_sha256'],'positive_control':plan['controls']['reference'],'negative_control':plan['controls']['deliberately_bad'],'mutant_controls':mutant_controls,'independent_oracle':{'args':args,'expected':expected,'reference_green':True,'original_bug_red':True},'protocol_sha256':task_eval.sha((run/'protocol.json').read_bytes())})
    manifest={'schema':'lime-tdd-v2-frozen-v1','family':'tdd','version':'v2-contract-repair','frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'supersedes_for_future_inference':str(old_family/'FROZEN.json'),'v1_results_preserved':True,'model_calls':0,'inference_authorized':False,'pairs_planned':10,'seed':seed,'source_stack_sha256':task_eval.sha(stack.read_bytes()),'source_skill_body_sha256':source_manifest['skills'][0]['sha256'],'entries':entries,'interpretation':'Prepared controls and seals only. Do not infer a skill effect or rerun models until root reviews the task/reference contracts. All ten cases are a new prospective family; v1 raw records and scores remain separate.'}
    target=base/'FROZEN.json';target.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'manifest':str(target),'cases':len(entries),'model_calls':0,'inference_authorized':False}))
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--old-family',type=Path,required=True)
    args=parser.parse_args()
    build(args.base,args.old_family)
