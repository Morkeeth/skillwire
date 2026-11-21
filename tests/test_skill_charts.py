"""Expected values below were worked out by hand from the fixture weeks."""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import skill_charts as charts


def row(source, name, weeks, installs=None):
    return {'source': source, 'skillId': name, 'name': name, 'weeklyInstalls': weeks,
            'installs': sum(weeks) if installs is None else installs}


RISE = row('alice/tools', 'rise', [10, 10, 10, 10, 10, 10, 1000, 3000])
NEW = row('bob/tools', 'brand-new', [0, 0, 0, 0, 0, 0, 0, 900])
SMALL = row('carol/tools', 'small', [0, 0, 0, 0, 0, 0, 100, 400])
FALL = row('dave/tools', 'fall', [0, 0, 0, 0, 0, 0, 5000, 4000])
PACK = [row('pack/all', f'p{gain}', [0, 0, 0, 0, 0, 0, 1000, 1000 + gain])
        for gain in (5000, 4000, 3000, 2000, 1000)]
CLONE_A = row('m1/superpowers', 'clone', [7000, 7000, 7010, 7000, 7000, 6000, 7000, 9000])
CLONE_B = row('m2/superpowers', 'clone', [7010, 6990, 7000, 7020, 6980, 6100, 7050, 5000])
SAME_NAME = row('erin/other', 'clone', [100, 200, 300, 400, 500, 600, 700, 2000])


class Parse(unittest.TestCase):
    def test_reads_rows_from_escaped_page_payload(self):
        payload = json.dumps([RISE]).replace('"', '\\"')
        page = f'<script>self.__next_f.push([1,"53:{{\\"initialSkills\\":{payload},\\"x\\":1}}"])</script>'
        self.assertEqual(charts.parse_home(page), [RISE])

    def test_page_without_payload_is_an_error(self):
        with self.assertRaises(ValueError):
            charts.parse_home('<html>changed layout</html>')

    def test_rows_without_eight_weeks_are_dropped(self):
        short = row('x/y', 'short', [1, 2, 3])
        payload = json.dumps([RISE, short]).replace('"', '\\"')
        page = f'"initialSkills":{payload}'.replace('\\"initialSkills\\"', '"initialSkills"')
        self.assertEqual([r['name'] for r in charts.parse_home(page)], ['rise'])


class Hot(unittest.TestCase):
    def test_ranks_by_new_installs_with_hand_counted_growth(self):
        got = charts.hot([NEW, RISE])
        self.assertEqual([r['name'] for r in got], ['rise', 'brand-new'])
        self.assertEqual((got[0]['gain'], got[0]['pct']), (2000, 200))

    def test_new_entry_has_no_percentage(self):
        got = charts.hot([NEW])[0]
        self.assertTrue(got['is_new'])
        self.assertIsNone(got['pct'])

    def test_below_floor_and_falling_are_out(self):
        self.assertEqual(charts.hot([SMALL, FALL]), [])

    def test_one_repo_gets_three_places(self):
        self.assertEqual([r['gain'] for r in charts.hot(PACK)], [5000, 4000, 3000])

    def test_mirrored_listings_are_removed_and_counted(self):
        self.assertEqual(charts.mirrors([CLONE_A, CLONE_B, SAME_NAME]),
                         {('m1/superpowers', 'clone'), ('m2/superpowers', 'clone')})
        self.assertEqual([r['source'] for r in charts.hot([CLONE_A, CLONE_B, SAME_NAME])], ['erin/other'])

    def test_two_new_skills_with_one_name_are_not_mirrors(self):
        other = row('zed/tools', 'brand-new', [0, 0, 0, 0, 0, 0, 0, 800])
        self.assertEqual(charts.mirrors([NEW, other]), set())

    def test_same_named_repos_sharing_a_skill_pack_are_hidden(self):
        def pack(owner, base):
            return [row(f'{owner}/superpowers', name, [i * 11 + start + 1 for i in range(7)] + [9000])
                    for name, start in zip(('a', 'b', 'c'), (base, base * 3, base * 7))]
        one, two = pack('copy1', 100), pack('copy2', 900)
        original = row('obra/superpowers', 'a', [1, 2, 3, 4, 5, 6, 7, 9000])
        lone_overlap = row('other/tools', 'a', [1, 2, 3, 4, 5, 6, 7, 9000])
        hidden = charts.mirrors(one + two + [original, lone_overlap])
        self.assertEqual(len(hidden), 6)
        self.assertNotIn(('obra/superpowers', 'a'), hidden)
        self.assertNotIn(('other/tools', 'a'), hidden)

    def test_empty_input_is_empty(self):
        self.assertEqual(charts.hot([]), [])


class AllTime(unittest.TestCase):
    def test_uses_reported_total_with_repo_cap_and_no_mirrors(self):
        rows = [row('pack/all', f't{n}', [1] * 8, installs=9000 - n) for n in range(5)]
        rows += [row('m1/superpowers', 'clone', CLONE_A['weeklyInstalls'], installs=99999),
                 row('m2/superpowers', 'clone', CLONE_B['weeklyInstalls'], installs=99998),
                 row('solo/one', 'solo', [1] * 8, installs=100)]
        self.assertEqual([r['name'] for r in charts.all_time(rows)], ['t0', 't1', 't2', 'solo'])


class Curated(unittest.TestCase):
    PICKS = {'counted_at': '2026-11-08', 'picks': [
        {'name': 'keep', 'kind': 'working-set', 'uses': 9, 'reason': 'Catalog reason.', 'catalog_id': 'abc'},
        {'name': 'job-hunt', 'kind': 'working-set', 'uses': 99, 'reason': 'Private.', 'catalog_id': None},
        {'name': 'later', 'kind': 'try-next', 'reason': 'Not used yet.', 'catalog_id': 'def'},
    ]}

    def test_only_used_skills_and_never_career_material(self):
        got = charts.curated(self.PICKS, {'keep': 'I reach for this first.', 'job-hunt': 'Must never appear.'})
        self.assertEqual([r['name'] for r in got], ['keep'])
        self.assertEqual(got[0]['why'], 'I reach for this first.')

    def test_missing_note_never_borrows_catalog_text(self):
        self.assertEqual(charts.curated(self.PICKS, {}), [])


class Render(unittest.TestCase):
    DATA = {'as_of': '2026-11-21', 'hidden_mirrors': 2,
            'hot': charts.hot([RISE, NEW]), 'all_time': charts.all_time([RISE, NEW]),
            'curated': [{'name': 'keep', 'why': 'I reach for this first.', 'uses': 9, 'catalog_id': 'abc'}]}

    def test_three_pages_link_to_each_other_and_mark_current(self):
        for page in ('hot', 'all-time', 'curated'):
            html = charts.render(page, self.DATA)
            for href in ('/hot', '/all-time', '/curated'):
                self.assertIn(f'href="{href}"', html)
            self.assertEqual(html.count('aria-current="page"'), 1)
            self.assertRegex(html, rf'href="/{page}"[^>]*aria-current="page"')

    def test_pages_obey_the_site_content_policy(self):
        for page in ('hot', 'all-time', 'curated'):
            html = charts.render(page, self.DATA)
            self.assertNotIn(' style=', html)
            self.assertIsNone(re.search(r'<script(?![^>]*\bsrc=)', html))
            self.assertIsNone(re.search(r'\son[a-z]+=', html))

    def test_sparkline_has_one_point_per_week(self):
        html = charts.render('hot', self.DATA)
        points = re.search(r'<polyline[^>]*points="([^"]+)"', html).group(1).split()
        self.assertEqual(len(points), 8)

    def test_empty_hot_page_says_unavailable_and_shows_no_zero_rows(self):
        html = charts.render('hot', {**self.DATA, 'hot': []})
        self.assertIn('No weekly numbers', html)
        self.assertNotIn('<polyline', html)

    def test_skill_text_is_escaped(self):
        bad = row('a/b', '<img src=x>', [0, 0, 0, 0, 0, 0, 0, 900])
        html = charts.render('hot', {**self.DATA, 'hot': charts.hot([bad])})
        self.assertNotIn('<img src=x>', html)

    def test_curated_link_opens_the_exact_catalog_skill(self):
        self.assertIn('href="/search#abc"', charts.render('curated', self.DATA))

    def test_growth_label_is_short_enough_for_a_phone_row(self):
        html = charts.render('hot', self.DATA)
        self.assertIn('<small>+200%</small>', html)
        self.assertIn('<small>new</small>', html)

    def test_page_shows_source_and_date(self):
        html = charts.render('hot', self.DATA)
        self.assertIn('skills.sh', html)
        self.assertIn('21 Nov 2026', html)


if __name__ == '__main__':
    unittest.main()
