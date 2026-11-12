import importlib.util,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ReleaseExport(unittest.TestCase):
 def test_exact_allowlist_builds_and_preserves_live_kit_contents(self):
  spec=importlib.util.spec_from_file_location('release_export',ROOT/'scripts/export_release.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory() as tmp:
   m.ROOT=Path(tmp)
   for name in m.FILES:
    dst=m.ROOT/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)
   m.main();out=next((m.ROOT/'data/release-source').iterdir());r=subprocess.run(['python3','scripts/build_site.py'],cwd=out,capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr);self.assertTrue((out/'eval-example/demo-skill/SKILL.md').is_file());self.assertTrue((out/'migrations/20261031_direction_votes.sql').is_file());self.assertFalse((out/'design-previews').exists())
   manifest=json.loads((out/'PUBLIC-SOURCE-MANIFEST.json').read_text());self.assertEqual(set(x['path'] for x in manifest),set(m.FILES))

   weekly=json.loads((out/'dist/weekly.json').read_text())
   self.assertEqual(weekly['fastest_growing']['status'],'unavailable')
   self.assertEqual(weekly['skill_of_week']['counted_at'],'2026-11-08')
   self.assertEqual(weekly['skill_of_week']['count_window_days'],30)
   self.assertIn('14 days',weekly['skill_of_week']['method'])
   self.assertTrue((out/'dist/weekly-sidebar.js').is_file())
   self.assertTrue((out/'dist/weekly-sidebar.css').is_file())
   self.assertFalse((out/'evidence/weekly-snapshot-inventory.json').exists())
   self.assertIn('weekly-sidebar.js',(out/'dist/index.html').read_text())
