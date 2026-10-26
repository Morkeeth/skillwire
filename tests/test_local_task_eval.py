import argparse,contextlib,io,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import lime_task_eval as t
import lime_agent_eval as a
ROOT=Path(__file__).resolve().parents[1]
class LocalEvaluationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.skill=self.root/'selected'/'SKILL.md';self.skill.parent.mkdir();self.skill.write_text('---\nname: fixture-only\ndescription: Original local test source, no model use.\n---\nReview the actual outcome.\n')
 def tearDown(self):self.temp.cleanup()
 def prepare(self,reference='good'):
  args=argparse.Namespace(fixture=ROOT/'eval-example/bug',reference=ROOT/'eval-example'/reference,negative=ROOT/'eval-example/bad',task=ROOT/'eval-example/TASK.md',grader=ROOT/'eval-example/grader.py',stack=None,skill=self.skill,out=self.root/'pair',trust_grader=True)
  with contextlib.redirect_stdout(io.StringIO()):t.prepare(args)
  return args.out
 def seal(self,root):
  p=root/'protocol.json';p.write_text(json.dumps({'model':'fixture-only-no-model','reasoning':'low','harness':'codex','tools':'disabled','budget':{'max_cli_trials':2,'timeout_seconds':30},'arm_order':['without','with']}))
  with contextlib.redirect_stdout(io.StringIO()):t.seal(argparse.Namespace(run=root))
 def test_real_good_bad_controls_and_recorded_artifact_change(self):
  root=self.prepare();plan=json.loads((root/'plan.json').read_text());self.assertTrue(plan['ready']);self.assertTrue(plan['controls']['reference']['passed']);self.assertFalse(plan['controls']['deliberately_bad']['passed']);self.assertFalse((root/'without/.agents').exists());self.seal(root)
  shutil.copyfile(ROOT/'eval-example/good/app.py',root/'with/app.py')
  with contextlib.redirect_stdout(io.StringIO()):t.grade(argparse.Namespace(run=root,without_trace=None,with_trace=None))
  result=json.loads((root/'artifact-results.json').read_text());self.assertFalse(result['arms']['without']['grade']['passed']);self.assertTrue(result['arms']['with']['grade']['passed']);self.assertEqual(result['arms']['with']['read']['status'],'unobserved')
  # This is a deliberate artifact substitution control, never a model/skill result.
 def test_bad_reference_does_not_freeze_ready(self):
  root=self.prepare('bad');self.assertFalse(json.loads((root/'plan.json').read_text())['ready'])
  with self.assertRaises(AssertionError):self.seal(root)
 def test_protocol_changes_refused_and_results_never_overwritten(self):
  root=self.prepare();self.seal(root);(root/'protocol.json').write_text('{}')
  with self.assertRaises(AssertionError):t.grade(argparse.Namespace(run=root,without_trace=None,with_trace=None))
 def test_self_report_does_not_count_as_instruction_read(self):
  p=self.root/'trace.jsonl';body=self.skill.read_text();skill={'id':'fixture','sha256':t.sha(body.encode())}
  p.write_text(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':body}})+'\n');self.assertEqual(t.read_evidence(p,[skill])['status'],'unobserved')
  p.write_text(json.dumps({'type':'item.completed','item':{'type':'command_execution','exit_code':0,'aggregated_output':body}})+'\n');self.assertEqual(t.read_evidence(p,[skill])['status'],'full_body_tool_output_observed')
 def test_changed_task_refused_before_subscription_or_model(self):
  root=self.prepare();self.seal(root);(root/'TASK.md').write_text('Changed after freeze')
  with patch.object(a,'subscription') as auth,patch.object(a.subprocess,'run') as model:
   with self.assertRaisesRegex(AssertionError,'Frozen task changed'):a.run(argparse.Namespace(run=root,agent='codex',use_subscription=True))
   auth.assert_not_called();model.assert_not_called()
 def test_no_subscription_never_invokes_model(self):
  root=self.prepare();self.seal(root)
  with patch.object(a,'subscription',return_value=False),patch.object(a.shutil,'which',return_value='codex'),patch.object(a.subprocess,'run') as run:
   with self.assertRaisesRegex(ValueError,'subscription login not verified'):a.run(argparse.Namespace(run=root,agent='codex',use_subscription=True))
   run.assert_not_called()
 def test_native_mode_is_separate_and_boundary_failure_stops_inference(self):
  work=self.root/'workspace';hidden=self.root/'hidden';hidden.mkdir()
  with patch.object(a.subprocess,'run',return_value=argparse.Namespace(returncode=1,stdout='',stderr='denied')) as process:
   with self.assertRaisesRegex(ValueError,'Native isolation probe failed'):a.native_boundary(work,hidden,hidden/'boundary.json')
   self.assertEqual(process.call_count,1)
   self.assertIn('--permission-profile',process.call_args.args[0]);self.assertNotIn('exec',process.call_args.args[0])
 def test_paired_interval_does_not_collapse_all_ties(self):
  import sys
  sys.path.insert(0,str(ROOT/'scripts'))
  from summarize_native_eval import effect
  result=effect(0,0,10,10)
  self.assertEqual(result['difference'],0);self.assertLess(result['ci95'][0],0);self.assertGreater(result['ci95'][1],0)
  missing=effect(0,0,0,10);self.assertIsNone(missing['difference']);self.assertEqual(missing['missing_pair_bound'],[-1.,1.])
 def test_selected_local_folder_preserves_resources_without_public_claim(self):
  (self.skill.parent/'reference.txt').write_text('A local resource, never executed')
  args=argparse.Namespace(fixture=ROOT/'eval-example/bug',reference=ROOT/'eval-example/good',negative=ROOT/'eval-example/bad',task=ROOT/'eval-example/TASK.md',grader=ROOT/'eval-example/grader.py',stack=None,skill=None,skill_folder=self.skill.parent,out=self.root/'full-folder',trust_grader=True)
  with contextlib.redirect_stdout(io.StringIO()):t.prepare(args)
  manifest=json.loads((args.out/'SKILL-SOURCES.json').read_text())['skills'][0]
  self.assertEqual(manifest['visibility'],'local-not-publicly-classified');self.assertEqual({f['path'] for f in manifest['files']},{'SKILL.md','reference.txt'})
  self.assertEqual((args.out/'with/.agents/skills'/manifest['folder']/'reference.txt').read_text(),'A local resource, never executed')
 def test_exact_binomial_interval_known_boundary(self):
  from scripts.summarize_native_eval import cp
  self.assertAlmostEqual(cp(0,10)[1],1-.0125**.1,places=10)
  self.assertAlmostEqual(cp(10,10)[0],.0125**.1,places=10)
if __name__=='__main__':unittest.main()
