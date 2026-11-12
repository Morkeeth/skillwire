"""Editorial ranks must identify real catalog entries and retain dated source evidence."""
import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CuratedRank(unittest.TestCase):
 def test_ranked_picks_are_unique_sourced_and_explain_their_scope(self):
  data=json.loads((ROOT/'site/research-picks.json').read_text())
  self.assertIn('editorial',data['ranking_basis'].lower())
  self.assertIn('usage',data['ranking_basis'].lower())
  self.assertEqual(sorted(p['rank'] for p in data['picks']),list(range(1,len(data['picks'])+1)))
  self.assertEqual(len({p['catalog_id'] for p in data['picks']}),len(data['picks']))
  import published_catalog
  catalog=published_catalog.load();ids={p['id'] for p in catalog['skills']}
  for pick in data['picks']:
   self.assertIn(pick['catalog_id'],ids)
   self.assertRegex(pick['source'],r'^https://github.com/[^/]+/[^/]+/blob/[0-9a-f]{40}/')
   self.assertTrue(pick['reason'].strip());self.assertNotIn('\n',pick['reason']);self.assertLessEqual(len(pick['reason']),180)
   self.assertTrue(pick['evidence']);self.assertTrue(pick['limits'])
  self.assertEqual(data['checked_at'],'2026-10-28') # re-ordering does not move the source-review clock
