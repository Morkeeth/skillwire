"""Exercise the withheld mapping and task preference boundary."""
import argparse,json,tempfile,unittest
from pathlib import Path
import lime_human_review as h

class HumanReviewTests(unittest.TestCase):
 def test_blind_choice_reveals_only_after_verdict(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'TASK.md').write_text('Summarize a change for an end user.');arms={}
   for arm,text in [('without','Version 2 is available.'),('with','Version 2 now restores drafts after a lost connection.')]:
    folder=root/arm;folder.mkdir();(folder/'answer.txt').write_text(text);(folder/'facts.txt').write_text('Users sometimes lose their connection.');arms[arm]=folder
   args=argparse.Namespace(run=None,task=root/'TASK.md',without=arms['without'],with_skill=arms['with'],files=['answer.txt'],context=['facts.txt'],out=root/'review')
   h.prepare(args);out=args.out
   bundle=json.loads((out/'blind-review.json').read_text());key=json.loads((out/'reveal-key.json').read_text())
   self.assertNotIn('mapping',bundle);self.assertNotIn('grades',bundle)
   self.assertEqual(bundle['context'][0]['content'],'Users sometimes lose their connection.')
   self.assertEqual({bundle['files'][0][side]['content'] for side in ['A','B']},{(arms[arm]/'answer.txt').read_text() for arm in arms})
   verdict=root/'verdict.json';verdict.write_text(json.dumps({'schema':h.SCHEMA,'pair_id':bundle['pair_id'],'choice':'A','reason':'This answer gives a concrete user-facing change.','reviewed_both':True}))
   h.reveal(argparse.Namespace(bundle=out/'blind-review.json',key=out/'reveal-key.json',review=verdict,out=root/'revealed.json'))
   result=json.loads((root/'revealed.json').read_text());self.assertEqual(result['choice_condition'],key['mapping']['A']);self.assertEqual(result['source_kind'],'manual-artifacts');self.assertIsNone(result['automated_grades_after_review'])
   bundle['task']='Changed after review';(out/'blind-review.json').write_text(json.dumps(bundle))
   with self.assertRaisesRegex(ValueError,'do not match'):h.reveal(argparse.Namespace(bundle=out/'blind-review.json',key=out/'reveal-key.json',review=verdict,out=root/'second.json'))
   (arms['with']/'facts.txt').write_text('Different facts')
   args.out=root/'second-review'
   with self.assertRaisesRegex(ValueError,'Starting context differs'):h.prepare(args)

if __name__=='__main__':unittest.main()
