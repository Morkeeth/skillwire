import copy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from weekly_sidebar import METRIC, build, build_for_site, growth, observation

ROOT = Path(__file__).resolve().parents[1]


class WeeklySidebar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT/'evidence/hosted-catalog.json').read_text())
        cls.picks = json.loads((ROOT/'site/oscar-picks.json').read_text())

    def comparison(self):
        # Mutate retained real records into a clearly isolated boundary control.
        catalog = copy.deepcopy(self.catalog)
        catalog['marketplace_source']['fetched_at'] = '2026-11-09T20:52:37+00:00'
        current = observation(catalog)
        previous = copy.deepcopy(current)
        previous['observed_at'] = '2026-11-02T20:52:37+00:00'
        key = next(iter(previous['counts']))
        previous['counts'][key] -= 200
        return catalog, previous, key

    def test_real_data_never_turns_build_copies_into_growth(self):
        with tempfile.TemporaryDirectory() as out:
            result = build_for_site(ROOT, self.catalog, Path(out))
            self.assertEqual(result['fastest_growing']['status'], 'unavailable')
            self.assertEqual(result['fastest_growing']['rows'], [])
            self.assertEqual(result['fastest_growing']['latest_observed_at'][:10], '2026-10-25')
            self.assertEqual(result['skill_of_week']['name'], 'animate')
            self.assertEqual(result['skill_of_week']['uses'], 11)
            self.assertEqual(result['skill_of_week']['counted_at'], '2026-11-08')
            self.assertIn('different bytes', result['skill_of_week']['catalog_relation'])
            self.assertEqual(json.loads((Path(out)/'weekly.json').read_text()), result)

    def test_seven_day_same_identity_comparison_uses_real_counter_delta(self):
        catalog, previous, key = self.comparison()
        value = growth(catalog, [previous], date(2026, 11, 10))
        self.assertEqual(value['status'], 'available')
        self.assertEqual(value['rows'][0]['change'], 200)
        self.assertEqual(value['matched_entries'], len(previous['counts']))
        self.assertEqual(len(value['rows']), 1)

    def test_same_date_changed_build_is_not_a_second_observation(self):
        catalog, previous, key = self.comparison()
        previous['observed_at'] = catalog['marketplace_source']['fetched_at']
        value = growth(catalog, [previous], date(2026, 11, 10))
        self.assertEqual(value['status'], 'unavailable')
        self.assertIn('Conflicting', value['reason'])

    def test_other_metric_and_future_counts_are_not_ranked(self):
        catalog, previous, key = self.comparison()
        for mutation in [{'metric': 'repository stars'}, {'provider': 'https://other.example/'},
                         {'observed_at': '2026-11-20T20:00:00+00:00'},
                         {'observed_at': '2026-11-02T20:00:00'}]:
            changed = {**previous, **mutation}
            self.assertEqual(growth(catalog, [changed], date(2026, 11, 10))['status'], 'unavailable')

    def test_unknown_install_date_does_not_fall_back_to_build_date(self):
        catalog = copy.deepcopy(self.catalog)
        catalog['marketplace_source'].pop('fetched_at')
        catalog['fetched_at'] = '2026-11-09T00:00:00+00:00'
        self.assertIsNone(observation(catalog))
        self.assertEqual(growth(catalog, [], date(2026, 11, 10))['status'], 'unavailable')

    def test_counter_reset_and_unknown_baseline_are_not_growth(self):
        catalog, previous, key = self.comparison()
        previous['counts'][key] += 400
        value = growth(catalog, [previous], date(2026, 11, 10))
        self.assertEqual(value['rows'], [])
        self.assertEqual(value['decreased_counters_excluded'], 1)
        previous['counts'].pop(key)
        self.assertEqual(growth(catalog, [previous], date(2026, 11, 10))['rows'], [])

    def test_all_feature_choices_are_dated_usage_not_votes_or_local_only(self):
        picks = copy.deepcopy(self.picks)
        picks['picks'].append({'name': 'fake vote leader', 'kind': 'try-next',
                               'catalog_id': self.catalog['skills'][0]['id'], 'uses': 100000})
        self.assertEqual(build(self.catalog, picks, [], '2026-11-10')['skill_of_week']['name'], 'animate')
        self.assertEqual(build(self.catalog, picks, [], '2026-12-01')['skill_of_week']['status'], 'unavailable')
        self.assertEqual(build(self.catalog, picks, [], '2026-11-01')['skill_of_week']['status'], 'unavailable')

    def test_feature_tie_break_and_source_order_are_deterministic(self):
        picks = copy.deepcopy(self.picks)
        eligible = [p for p in picks['picks'] if p.get('catalog_id') and p.get('uses')]
        for p in eligible:
            p['uses'] = 11
        a = build(self.catalog, picks, [], '2026-11-10')
        picks['picks'].reverse()
        b = build(self.catalog, picks, [], '2026-11-10')
        self.assertEqual(a, b)
        self.assertEqual(a['skill_of_week']['id'], min(p['catalog_id'] for p in eligible))


if __name__ == '__main__':
    unittest.main()
