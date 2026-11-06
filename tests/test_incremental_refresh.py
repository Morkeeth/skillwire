import hashlib,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import incremental_refresh as ir

OLD,NEW='a'*40,'b'*40
def blob(p,body):return {'path':p,'type':'blob','sha':hashlib.sha1(body).hexdigest(),'size':len(body)}
OLD_FILES={'keep/SKILL.md':b'name: keep\n','mod/SKILL.md':b'name: mod\nv1','gone/SKILL.md':b'name: gone\n'}
NEW_FILES={'keep/SKILL.md':b'name: keep\n','mod/SKILL.md':b'name: mod\nv2','new/SKILL.md':b'name: new\n','copy/of/keep/SKILL.md':b'name: keep\n'}
def entry(key,p,body,rev=OLD):return dict(id=ir.entry_id(key,p),name=p.split('/')[0],repo=key,path=p,revision=rev,sha256=hashlib.sha256(body).hexdigest(),source='x',stars=1,eval={'status':'Measured','n':3})
def catalog():
    return {'sources':[{'repo':'old/name','revision':OLD},{'repo':'same/repo','revision':'c'*40}],
            'skills':[entry('old/name',p,b) for p,b in OLD_FILES.items()]+[entry('same/repo','SKILL.md',b'name: s\n','c'*40)]}
def api(path):
    if path=='repos/old/name':return {'full_name':'new/name','default_branch':'main','stargazers_count':9,'license':None}
    if path=='repos/same/repo':return {'full_name':'same/repo','default_branch':'main','stargazers_count':2,'license':None}
    if path.endswith('/commits/main'):return {'sha':NEW if 'new/name' in path else 'c'*40}
    if path=='repos/new/name/git/trees/'+NEW+'?recursive=1':return {'tree':[blob(p,b) for p,b in NEW_FILES.items()]}
    if path=='repos/new/name/git/trees/'+OLD+'?recursive=1':return {'tree':[blob(p,b) for p,b in OLD_FILES.items()]}
    raise AssertionError('unexpected metadata call '+path)
calls=[]
def get(url):
    calls.append(url)
    assert url.startswith('https://raw.githubusercontent.com/new/name/'+NEW+'/'),url
    p=url.split(NEW+'/',1)[1]
    if p=='README.md':return b'Works with Claude Code'
    return NEW_FILES[p]

class IncrementalRefresh(unittest.TestCase):
    def setUp(self):
        calls.clear();self.c=catalog();self.rows=ir.plan(self.c,api)
    def test_plan_is_metadata_only_and_skips_unchanged(self):
        self.assertEqual(calls,[])
        same=[r for r in self.rows if r['key']=='same/repo'][0];self.assertFalse(same['changed'])
        r=[r for r in self.rows if r['key']=='old/name'][0]
        self.assertEqual(r['fetch'],['copy/of/keep/SKILL.md','mod/SKILL.md','new/SKILL.md']);self.assertEqual(r['drop'],['gone/SKILL.md'])
    def test_rename_keeps_ids_and_fetches_only_changed_files(self):
        out,rc=ir.apply(self.c,self.rows,{'old/name'},10_000,60,0,get=get,write_cache=False)
        ids={s['id']:s for s in out['skills']}
        for p in ('keep/SKILL.md','mod/SKILL.md'):self.assertIn(ir.entry_id('old/name',p),ids)
        self.assertNotIn(ir.entry_id('old/name','gone/SKILL.md'),ids);self.assertEqual(rc['removed_ids'],[ir.entry_id('old/name','gone/SKILL.md')])
        self.assertTrue(all(s['repo']=='old/name' for s in out['skills'] if s['path']!='SKILL.md'))
        self.assertFalse(any(c.endswith('keep/SKILL.md') and 'copy' not in c for c in calls),'unchanged body was downloaded')
        mod=ids[ir.entry_id('old/name','mod/SKILL.md')];self.assertEqual(mod['revision'],NEW);self.assertEqual(mod['eval']['n'],3)
        self.assertIn('github.com/new/name/blob/'+NEW,mod['source'])
        keep=ids[ir.entry_id('old/name','keep/SKILL.md')];self.assertEqual(keep['duplicate_paths'],['copy/of/keep/SKILL.md'])
        self.assertNotIn(ir.entry_id('old/name','copy/of/keep/SKILL.md'),ids,'a byte-identical new copy must not take a new id')
        self.assertEqual(rc['added_ids'],[ir.entry_id('old/name','new/SKILL.md')])
    def test_limits_stop_before_any_download(self):
        with self.assertRaises(SystemExit):ir.apply(self.c,self.rows,{'old/name'},5,60,0,get=get,write_cache=False)
        with self.assertRaises(SystemExit):ir.apply(self.c,self.rows,{'old/name'},10_000,60,10_000,get=get,write_cache=False)
        self.assertEqual(calls,[])
    def test_failed_file_leaves_repo_at_old_revision(self):
        def broken(url):
            if url.endswith('new/SKILL.md'):raise OSError('down')
            return get(url)
        out,rc=ir.apply(self.c,self.rows,{'old/name'},10_000,60,0,get=broken,write_cache=False)
        self.assertEqual({s['id'] for s in out['skills']},{s['id'] for s in self.c['skills']});self.assertTrue(rc['errors'])
    def test_id_guard_fails_on_lost_id(self):
        after={'skills':self.c['skills'][1:]}
        with self.assertRaises(SystemExit):ir.check_ids(self.c,after,self.rows,{'removed_ids':[]})
    def test_fetch_needs_explicit_bounds(self):
        import tempfile
        from unittest import mock
        with mock.patch.object(ir,'plan',lambda c,api=None:[]),self.assertRaises(SystemExit):
            ir.main(['--catalog',str(Path(__file__).resolve().parents[1]/'evidence/hosted-catalog.json'),'--plan-out',tempfile.mktemp(),'--fetch','--repos','x'])
if __name__=='__main__':unittest.main()
