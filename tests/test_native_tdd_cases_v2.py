"""Guard the prospectively fixed task/reference boundaries."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import native_tdd_cases as old
import native_tdd_cases_v2 as repaired


class ContractV2Tests(unittest.TestCase):
    def test_independent_witness_for_every_case(self):
        for name, _, function, good, mutants, _ in repaired.cases():
            args, expected = repaired.ORACLE[name]
            with self.subTest(name=name):
                self.assertTrue(repaired.test_source(function, good, args, expected))
                self.assertFalse(repaired.test_source(function, mutants[0], args, expected))

    def test_windows_del_changes_reference_result(self):
        before = next(case[3] for case in old.cases() if case[0] == 'windows-alias')
        after = repaired.GOOD['windows-alias']
        self.assertFalse(repaired.test_source('safe', before, ['file\x7f'], False))
        self.assertTrue(repaired.test_source('safe', after, ['file\x7f'], False))

    def test_url_empty_port_and_nonstring_are_rejected(self):
        code = repaired.GOOD['url-origin']
        for value in ['https://example.com:/app', 42, 'https://example.com/app/%ZZ']:
            with self.subTest(value=value):
                self.assertTrue(repaired.test_source('allowed', code, [value], False))

    def test_naive_timestamp_raises(self):
        scope = {}
        exec(repaired.GOOD['timezone-days'], scope)
        with self.assertRaises(ValueError):
            scope['group'](['2026-05-01T12:00:00'], 0)


if __name__ == '__main__':
    unittest.main()
