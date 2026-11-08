"""Working-set picks must follow measured use and carry the evidence file's stars."""
import json, subprocess, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


class OscarPicks(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'site/oscar-picks.json').read_text())
        self.ev = json.loads((ROOT / 'evidence/our-skill-usage-2026-11-08.json').read_text())
        self.working = [p for p in self.data['picks'] if p['kind'] == 'working-set']

    def test_ranked_by_measured_sessions(self):
        self.assertEqual([p['rank'] for p in self.working], list(range(1, len(self.working) + 1)))
        uses = [p['uses'] for p in self.working]
        self.assertEqual(uses, sorted(uses, reverse=True))
        measured = {r['skill']: r['sessions'] for r in self.ev['skills']}
        for p in self.working:
            self.assertIn(p['name'], measured)
            self.assertEqual(p['uses'], measured[p['name']])
            self.assertGreater(p['uses'], 0)

    def test_catalog_ids_and_stars_match_evidence(self):
        sys.path.insert(0, str(ROOT))
        import published_catalog
        catalog = {s['id']: s for s in published_catalog.load()['skills']}
        for p in self.data['picks']:
            if p['catalog_id']:
                self.assertIn(p['catalog_id'], catalog)
            if p.get('stars') is not None:
                self.assertEqual(p['stars_repo'], catalog[p['catalog_id']]['repo'])
                self.assertEqual(p['stars'], self.ev['stars'][p['stars_repo']])
                self.assertEqual(p['stars_as_of'], self.ev['stars_as_of'])
            else:
                self.assertIsNone(p.get('stars_repo'))

    def test_no_unmeasured_wording_left(self):
        for name in ('site/oscar-picks.json', 'site/index.html', 'site/app.js'):
            self.assertNotIn('not measured', (ROOT / name).read_text())

    def test_generator_is_deterministic(self):
        before = (ROOT / 'site/oscar-picks.json').read_bytes()
        subprocess.run([sys.executable, str(ROOT / 'scripts/build_oscar_picks.py')], check=True, capture_output=True)
        self.assertEqual((ROOT / 'site/oscar-picks.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
