"""Discover accessible repositories and report official OpenSSF Criticality Scores."""

import concurrent.futures
import json
import math
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def discover_repositories():
    # gh follows Link headers; --slurp preserves page boundaries as JSON arrays.
    result = subprocess.run(
        ['gh', 'api', '--paginate', '--slurp',
         '/user/repos?per_page=100&affiliation=owner,collaborator,organization_member&sort=full_name'],
        check=True, capture_output=True, text=True, timeout=120,
    )
    repositories = {repo['id']: repo for page in json.loads(result.stdout) for repo in page}
    return sorted(repositories.values(), key=lambda repo: repo['full_name'].lower())


def parse_score(output):
    value = float(json.loads(output)['criticality_score'])
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Invalid criticality score')
    return value


def score_repository(repo):
    command = [os.environ.get('CRITICALITY_SCORE_BIN', 'criticality_score'),
               '-depsdev-disable', '-format', 'json', '-scoring-column',
               'criticality_score', repo['html_url']]
    status = 'Collection failed'
    for attempt in range(2):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=180)
            if result.returncode == 0 and result.stdout.strip():
                return {'repository': repo['full_name'], 'url': repo['html_url'],
                        'score': parse_score(result.stdout), 'status': 'Scored'}
            if 'Repo cannot be collected' in result.stderr:
                status = 'Unsupported by OpenSSF collector'
                break
            if 'Could not resolve to a User' in result.stderr:
                status = 'OpenSSF contributor lookup failed'
                break
            if 'rate limit' in result.stderr.lower():
                status = 'GitHub rate limit reached'
            elif result.returncode == 0:
                status = 'No score returned by OpenSSF'
        except subprocess.TimeoutExpired:
            status = 'Collection timed out'
        except (ValueError, KeyError, TypeError):
            status = 'Invalid score returned by OpenSSF'
        if attempt == 0:
            time.sleep(5)
    return {'repository': repo['full_name'], 'url': repo['html_url'],
            'score': None, 'status': status}


def render_readme(results, updated):
    scored = sum(row['score'] is not None for row in results)
    lines = [
        '# OpenSSF Criticality Tracker', '',
        'Daily [OpenSSF Criticality Scores](https://github.com/ossf/criticality_score) '
        'for all repositories accessible to my GitHub account, including owned, '
        'collaborator, and organization repositories. Scores range from **0 to 1** '
        'and estimate project importance to the open-source ecosystem.', '',
        f'Updated: **{updated}** · **{scored}/{len(results)}** repositories scored.', '',
        '| Repository | Criticality score | Status |',
        '| --- | ---: | --- |',
    ]
    for row in sorted(results, key=lambda r: (
        r['score'] is None, -(r['score'] or 0), r['repository'].lower()
    )):
        score = f"{row['score']:.5f}" if row['score'] is not None else '—'
        name = row['repository'].replace('_', r'\_')
        lines.append(f"| [{name}]({row['url']}) | {score} | {row['status']} |")
    lines.extend([
        '', '<details>', '<summary>How this tracker works</summary>', '',
        '- Runs on every push, manually, and daily at midnight in `America/New_York` '
        '(GitHub may delay scheduled runs).',
        '- Uses the official OpenSSF Criticality Score **v2.0.4** default scoring '
        'configuration. Google Cloud/deps.dev collection is disabled; the default '
        'score uses GitHub signals.',
        '- Discovers all repositories returned by GitHub’s authenticated `/user/repos` '
        'API, including private, archived, and forked repositories. Access is limited '
        'by the token and any organization SSO restrictions.',
        '- Private repositories are attempted too, but open-source ecosystem signals '
        'may be incomplete. This is a criticality metric, not a security rating.',
        '- OpenSSF v2.0.4 can fail when a bot contributor (such as `Copilot`) is '
        'queried as a regular user. These repositories show `OpenSSF contributor '
        'lookup failed` instead of an invented score.',
        '- Unavailable scores are shown explicitly; previous scores are never presented '
        'as fresh results. Raw results are in [scores.json](scores.json).',
        '- `TRACKER_GITHUB_TOKEN` is an Actions secret initialized from the existing '
        'GitHub CLI login. Replace it if that credential expires or is revoked: '
        '`gh auth token | gh secret set TRACKER_GITHUB_TOKEN`. A replacement token '
        'needs access to the repositories being tracked (`repo` and `read:org` for '
        'a classic token, plus organization SSO authorization where required).',
        '- README commits use the repository’s built-in `GITHUB_TOKEN`, preventing '
        'recursive workflow runs. Push runs update the pushed branch; scheduled runs '
        'update the default branch.',
        '- Local use: install `gh` and `criticality_score` v2.0.4, export '
        '`GH_TOKEN`, then run `python3 scripts/update_readme.py`. '
        'Run checks with `python3 -m unittest discover -s tests`.',
        '', '</details>', '',
    ])
    return '\n'.join(lines)


def main():
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise SystemExit('Set GH_TOKEN to a GitHub token with repository access.')
    os.environ.update(GH_TOKEN=token, GITHUB_TOKEN=token, GITHUB_AUTH_TOKEN=token)
    repos = discover_repositories()
    if not repos:
        raise SystemExit('No accessible repositories found; preserving the existing report.')
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for row in pool.map(score_repository, repos):
            results.append(row)
            # Keep credentials and collector diagnostics out of workflow logs.
            print(f"Processed {len(results)}/{len(repos)}: {row['status']}", flush=True)
    updated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    report = {'updated_at': updated, 'criticality_score_version': 'v2.0.4',
              'repositories': results}
    (ROOT / 'scores.json').write_text(json.dumps(report, indent=2) + '\n')
    (ROOT / 'README.md').write_text(render_readme(results, updated))
    if all(row['score'] is None for row in results):
        raise SystemExit('No repositories could be scored; see the generated report.')


if __name__ == '__main__':
    main()
