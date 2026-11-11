"""Main-page rulings: no invented host-use list, real tested skills, company spots."""
import json, pathlib, subprocess, unittest
import published_catalog
ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'

class MainPageRulingTests(unittest.TestCase):
    def text(self, name):
        return (SITE / name).read_text()

    def test_oscar_pick_labels_are_absent(self):
        page = self.text('index.html') + self.text('app.js')
        for phrase in ("Oscar curation", "Oscar's pick", "Oscar’s pick", "Oscar's picks", "Oscar's task trials", "Oscar’s task trials"):
            self.assertNotIn(phrase, page)

    def test_required_main_page_labels(self):
        page = self.text('index.html')
        for phrase in ('Browse host', 'Fastest growing', 'Skill of the week', 'Tested skills', 'GitHub stars', 'Company spots', 'Own entries', 'Host uses'):
            self.assertIn(phrase, page)
        self.assertNotIn('data-tab="picks"', page)
        self.assertNotIn('id="research-picks"', page)
        self.assertIn('function hostUseIds(){return new Set();}', self.text('app.js'))

    def test_tested_skills_are_only_the_published_studies(self):
        catalog = published_catalog.load()
        tested = sorted(s['name'] for s in catalog['skills'] if s['eval']['status'] == 'Measured task outcomes' or (s.get('native_eval') or {}).get('effect', {}).get('valid_pairs', 0) > 0)
        self.assertEqual(tested, ['security-best-practices', 'systematic-debugging', 'tdd', 'xlsx'])
        # The page must not hard-code that list; it renders catalog rows that were measured.
        self.assertNotIn('security-best-practices', self.text('app.js'))

    def test_company_spots_group_vercel_and_heygen_and_keep_find_skills(self):
        script = r'''
const fs = require('fs');
const api = require(process.argv[1]);
const catalog = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const classifier = api.createClassifier(catalog);
const spots = api.companySpots(catalog, classifier);
const own = api.ownEntries(catalog, classifier).map(s => s.name);
const heygen = catalog.skills.filter(s => s.repo === 'heygen-com/hyperframes');
const heygenIds = new Set(heygen.map(s => classifier.get(s.id) && classifier.get(s.id).id));
const vercel = catalog.skills.filter(s => /(^|-)vercel(-|$)/i.test(s.name) && s.name.toLowerCase() !== 'find-skills');
const vercelIds = new Set(vercel.map(s => classifier.get(s.id) && classifier.get(s.id).id));
const find = catalog.skills.find(s => s.name === 'find-skills');
const rows = [find, ...heygen.slice(0, 3), ...vercel.slice(0, 2)];
const slots = api.groupRows(rows, classifier);
process.stdout.write(JSON.stringify({
  labels: spots.map(s => s.label),
  own,
  heygenIds: [...heygenIds],
  vercelIds: [...vercelIds],
  find: classifier.get(find.id),
  slotKinds: slots.map(s => s.kind === 'company' ? s.label : s.skill.name)
}));
'''
        result = subprocess.run(['node', '-e', script, str(SITE / 'company-groups.js'), str(ROOT / 'evidence' / 'hosted-catalog.json')], check=True, capture_output=True, text=True)
        data = json.loads(result.stdout)
        self.assertEqual(data['labels'][:2], ['Vercel', 'HeyGen'])
        self.assertEqual(data['own'], ['find-skills'])
        self.assertEqual(data['heygenIds'], ['heygen'])
        self.assertEqual(data['vercelIds'], ['vercel'])
        self.assertIsNone(data['find'])
        self.assertEqual(data['slotKinds'][0], 'find-skills')
        self.assertIn('HeyGen', data['slotKinds'])
        self.assertIn('Vercel', data['slotKinds'])

if __name__ == '__main__':
    unittest.main()
