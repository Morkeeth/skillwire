"""Exercise the distributed kit, rather than the source checkout's fixtures."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts.build_site import build_eval_kit, EVAL_KIT_FILES

ROOT = Path(__file__).resolve().parents[1]


class DownloadedKitTests(unittest.TestCase):
    def test_clean_extraction_can_prepare_good_and_bad_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_eval_kit(ROOT, root)
            kit = root / 'extracted'
            with zipfile.ZipFile(root / 'local-eval-tools.zip') as archive:
                archive.extractall(kit)
            skill = root / 'skill'
            skill.mkdir()
            (skill / 'SKILL.md').write_text('---\nname: packaging-control\ndescription: Synthetic packaging check.\n---\nReview the result.\n')
            result = subprocess.run([
                sys.executable, 'lime_task_eval.py', 'prepare',
                '--fixture', 'eval-example/bug', '--reference', 'eval-example/good',
                '--negative', 'eval-example/bad', '--task', 'eval-example/TASK.md',
                '--grader', 'eval-example/grader.py', '--skill-folder', str(skill),
                '--out', str(root / 'run'), '--trust-grader',
            ], cwd=kit, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads((root / 'run/plan.json').read_text())
            self.assertTrue(plan['ready'])
            self.assertTrue(plan['controls']['reference']['passed'])
            self.assertFalse(plan['controls']['deliberately_bad']['passed'])

    def test_grade_without_any_run_reports_unverified_not_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_eval_kit(ROOT, root)
            kit = root / 'extracted'
            with zipfile.ZipFile(root / 'local-eval-tools.zip') as archive:
                archive.extractall(kit)
            steps = [
                ['lime_task_eval.py', 'prepare', '--fixture', 'eval-example/bug', '--reference', 'eval-example/good',
                 '--negative', 'eval-example/bad', '--task', 'eval-example/TASK.md', '--grader', 'eval-example/grader.py',
                 '--skill-folder', 'eval-example/demo-skill', '--out', 'runs/example', '--trust-grader'],
                ['lime_eval_setup.py', '--run', 'runs/example', '--agent', 'codex', '--mode', 'native_installed',
                 '--model', 'any-model', '--reasoning', 'low'],
                ['lime_task_eval.py', 'grade', '--run', 'runs/example'],
            ]
            for step in steps:
                result = subprocess.run([sys.executable, *step], cwd=kit, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            arms = json.loads((kit / 'runs/example/artifact-results.json').read_text())['arms']
            for arm in ('without', 'with'):
                self.assertEqual(arms[arm]['grade']['status'], 'unverified')
                self.assertIsNone(arms[arm]['grade']['passed'])
                self.assertEqual(arms[arm]['read']['status'], 'unobserved')

    def test_hosting_upload_missing_a_control_refuses_to_publish_kit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in EVAL_KIT_FILES:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            (root / 'eval-example/good/app.py').unlink()
            with self.assertRaisesRegex(ValueError, 'eval-example/good/app.py'):
                build_eval_kit(root, root)
            self.assertFalse((root / 'local-eval-tools.zip').exists())
