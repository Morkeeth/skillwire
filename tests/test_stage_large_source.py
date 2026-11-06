import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import stage_large_source as st

A,B,C='a'*40,'b'*40,'c'*40
BODY=b'---\nname: bounded-stage\ndescription: Source instructions remain data.\n---\n'
SHA=st.blob_sha(BODY)
class FakeBudget:
 def __init__(self,fail=False,cap=100000):self.fail=fail;self.used=0;self.limit=cap;self.calls=[]
 def api(self,path):
  self.calls.append(path)
  if path.endswith('/'+A):return {'tree':[]}
  if path.endswith('/'+B):return {'tree':[{'path':'nested','type':'tree','sha':C,'mode':'040000'}]}
  if path.endswith('/'+C):
   if self.fail:raise ValueError('bounded chunk ended')
   return {'tree':[{'path':'SKILL.md','type':'blob','sha':SHA,'mode':'100644','size':len(BODY)}]}
  raise AssertionError(path)
 def get(self,url,cap=None):self.calls.append(url);self.used+=len(BODY);return BODY

def state():return {'key':'old/name','canonical':'new/name','old_revision':A,'new_revision':B,'queues':{'old':[[A,'']],'new':[[B,'']]},'visited':{'old':[],'new':[]},'files':{'old':{},'new':{}},'trees':{'old':[],'new':[]},'body_cache':{},'ready':False}
class Stage(unittest.TestCase):
 def test_nonrecursive_stage_keeps_stored_identity_and_verifies_body(self):
  with tempfile.TemporaryDirectory() as d:
   s=state();b=FakeBudget();st.stage(s,Path(d),b)
   self.assertTrue(s['ready']);self.assertEqual(s['key'],'old/name')
   self.assertEqual(s['fetch'],['nested/SKILL.md'])
   self.assertEqual((Path(d)/s['body_cache']['nested/SKILL.md']).read_bytes(),BODY)
   self.assertFalse(any('recursive=1' in x for x in b.calls))
 def test_partial_metadata_resume_does_not_refetch_completed_nodes(self):
  with tempfile.TemporaryDirectory() as d:
   s=state();b=FakeBudget(fail=True)
   with self.assertRaises(ValueError):st.stage(s,Path(d),b)
   saved=json.loads((Path(d)/'state.json').read_text());self.assertFalse(saved['ready'])
   self.assertEqual(saved['queues']['new'],[[C,'nested/']])
   resume=FakeBudget();st.stage(saved,Path(d),resume)
   self.assertFalse(any(x.endswith('/'+A) or x.endswith('/'+B) for x in resume.calls));self.assertTrue(saved['ready'])
 def test_complete_file_cannot_cross_chunk_byte_cap(self):
  with tempfile.TemporaryDirectory() as d:
   s=state();b=FakeBudget(cap=1)
   with self.assertRaises(ValueError):st.stage(s,Path(d),b)
   self.assertFalse(s['ready']);self.assertFalse(s['body_cache']);self.assertFalse(any(x.startswith('https:') for x in b.calls))
 def test_corrupt_body_is_never_committed_as_ready(self):
  with tempfile.TemporaryDirectory() as d:
   s=state();b=FakeBudget();b.get=lambda *_args,**_kwargs:b'wrong body'
   with self.assertRaises(ValueError):st.stage(s,Path(d),b)
   self.assertFalse(s['ready']);self.assertFalse(s['body_cache'])
 def test_oversized_skill_is_explicitly_incomplete_not_silently_dropped(self):
  with tempfile.TemporaryDirectory() as d:
   s=state();b=FakeBudget();original=b.api
   def api(path):
    if path.endswith('/'+C):return {'tree':[{'path':'SKILL.md','type':'blob','sha':SHA,'mode':'100644','size':1_000_001}]}
    return original(path)
   b.api=api
   with self.assertRaises(ValueError):st.stage(s,Path(d),b)
   self.assertFalse(s['ready']);self.assertEqual(s['unsupported']['new'][0]['path'],'nested/SKILL.md')
if __name__=='__main__':unittest.main()
