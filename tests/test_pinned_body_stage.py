import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import fetch_pinned_plan_bodies as stage
BODY=b'pinned source data'
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
class BodyStage(unittest.TestCase):
 def test_exact_size_cap_and_zero_size_materialization(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);plan=root/'plan.json';out=root/'new-stage'
   row={'key':'old/name','canonical':'new/name','new_revision':'a'*40,'tree':{'truncated':False},'fetch':['one/SKILL.md','empty/SKILL.md'],'fetch_sizes':{'one/SKILL.md':len(BODY),'empty/SKILL.md':0},'fetch_shas':{'one/SKILL.md':blob(BODY),'empty/SKILL.md':blob(b'')}}
   plan.write_text(json.dumps({'planned_at':'2026-11-06T12:52:31+01:00','sources':[row]}));calls=[]
   class Budget:
    def __init__(self,*_):self.used=0
    def get(self,url,cap=None):calls.append((url,cap));self.used+=len(BODY);return BODY
   with mock.patch.object(stage,'Budget',Budget):
    self.assertEqual(stage.main(['--plan',str(plan),'--plan-sha256',hashlib.sha256(plan.read_bytes()).hexdigest(),'--output',str(out),'--max-bytes','1000000','--max-seconds','180']),0)
   self.assertEqual(len(calls),1);self.assertEqual(calls[0][1],len(BODY))
   receipt=json.loads((out/'receipt.json').read_text());self.assertEqual(receipt['response_bytes'],len(BODY));self.assertEqual([b['network_fetched'] for b in receipt['bodies']],[True,False]);self.assertEqual(receipt['metadata_requests'],0)
 def test_cli_cannot_exceed_one_million_bytes_or_180_seconds(self):
  for amount,seconds in [('1000001','180'),('1000000','181')]:
   with self.assertRaises(SystemExit),mock.patch.object(stage,'Budget',side_effect=AssertionError('network must not start')):
    stage.main(['--plan','/nonexistent','--plan-sha256','x','--output','/nonexistent-output','--max-bytes',amount,'--max-seconds',seconds])
 def test_corrupt_or_wrong_size_body_refused(self):
  expected={'bytes':len(BODY),'git_blob_sha':blob(BODY)}
  self.assertEqual(stage.verify_body(BODY,expected),hashlib.sha256(BODY).hexdigest())
  for raw in [BODY+b'!',b'x'*len(BODY)]:
   with self.assertRaises(ValueError):stage.verify_body(raw,expected)
if __name__=='__main__':unittest.main()
