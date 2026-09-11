import json
import subprocess
import unittest
from unittest.mock import patch

from scripts.update_readme import discover_repositories, parse_score, render_readme, score_repository


class TrackerTests(unittest.TestCase):
    def test_discovers_every_page_and_deduplicates(self):
        a = {'id': 1, 'full_name': 'owner/a'}
        b = {'id': 2, 'full_name': 'org/b'}
        with patch('scripts.update_readme.subprocess.run') as run:
            run.return_value.stdout = json.dumps([[a], [a, b]])
            self.assertEqual(discover_repositories(), [b, a])
            self.assertIn('--paginate', run.call_args.args[0])

    def test_official_json_and_invalid_values(self):
        self.assertEqual(parse_score('{"criticality_score":"0.12345"}'), 0.12345)
        for value in ['NaN', 'Infinity', '-0.1', '1.1']:
            with self.assertRaises(ValueError):
                parse_score(json.dumps({'criticality_score': value}))

    def test_unsupported_repository_is_not_zero(self):
        repo = {'full_name': 'owner/fork', 'html_url': 'https://github.com/owner/fork'}
        with patch('scripts.update_readme.subprocess.run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, '', 'Repo cannot be collected')
            row = score_repository(repo)
            self.assertIsNone(row['score'])
            self.assertEqual(run.call_count, 1)

    def test_upstream_bot_lookup_failure_is_explicit(self):
        repo = {'full_name': 'owner/repo', 'html_url': 'https://github.com/owner/repo'}
        with patch('scripts.update_readme.subprocess.run') as run:
            run.return_value = subprocess.CompletedProcess(
                [], 1, '', "Could not resolve to a User with the login of 'Copilot'."
            )
            row = score_repository(repo)
            self.assertIsNone(row['score'])
            self.assertEqual(row['status'], 'OpenSSF contributor lookup failed')
            self.assertEqual(run.call_count, 1)

    def test_failure_does_not_discard_other_scores(self):
        rows = [
            {'repository': 'o/failed', 'url': 'https://github.com/o/failed', 'score': None, 'status': 'Collection failed'},
            {'repository': 'o/zero', 'url': 'https://github.com/o/zero', 'score': 0, 'status': 'Scored'},
            {'repository': 'o/high', 'url': 'https://github.com/o/high', 'score': .8, 'status': 'Scored'},
        ]
        readme = render_readme(rows, 'now')
        self.assertLess(readme.index('[o/high]'), readme.index('[o/zero]'))
        self.assertLess(readme.index('[o/zero]'), readme.index('[o/failed]'))
        self.assertIn('| 0.00000 | Scored |', readme)
        self.assertIn('| — | Collection failed |', readme)
        self.assertIn('**2/3**', readme)


if __name__ == '__main__':
    unittest.main()
