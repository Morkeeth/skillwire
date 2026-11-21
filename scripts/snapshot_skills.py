"""Daily reading of the public skills.sh home page. One request, kept as dated history.

Writes HISTORY/YYYY-MM-DD.json and a run receipt. With --latest PATH it also refreshes
the copy the site build reads. A failed or short reading never replaces a good one.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import skill_charts

URL = 'https://www.skills.sh/'
MIN_ROWS = 300
GH = '/opt/homebrew/bin/gh'
FIELDS = ('source', 'skillId', 'name', 'installs', 'weeklyInstalls')


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(text)
    os.replace(temporary, path)


def snapshot(page, now):
    rows = [{key: row[key] for key in FIELDS} for row in skill_charts.parse_home(page)]
    if len(rows) < MIN_ROWS:
        raise ValueError(f'only {len(rows)} rows, expected at least {MIN_ROWS}')
    return {'schema': 1, 'source': URL, 'fetched_at': now.isoformat(timespec='seconds'), 'rows': rows}


def repo_stars(rows):
    """Best effort, for dated star growth later. A failure here never blocks the install reading."""
    repos = sorted({row['source'] for row in rows if re.fullmatch(r'[\w.-]+/[\w.-]+', row['source'])})
    stars = {}
    for start in range(0, len(repos), 40):
        batch = repos[start:start + 40]
        fields = ' '.join(
            f'r{index}: repository(owner: {json.dumps(repo.split("/")[0])}, name: {json.dumps(repo.split("/")[1])}) {{ stargazerCount }}'
            for index, repo in enumerate(batch))
        done = subprocess.run([GH, 'api', 'graphql', '-f', f'query={{ {fields} }}'], capture_output=True, text=True, timeout=40)
        data = json.loads(done.stdout or '{}').get('data') or {}
        for index, repo in enumerate(batch):
            if data.get(f'r{index}'):
                stars[repo] = data[f'r{index}']['stargazerCount']
    return stars


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', type=Path, default=Path.home() / '.local/state/fleet/skillwire-history')
    parser.add_argument('--latest', type=Path)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    receipt = {'at': now.isoformat(timespec='seconds'), 'ok': False}
    try:
        request = urllib.request.Request(URL, headers={'User-Agent': 'SkillWire-daily-snapshot/1.0'})
        with urllib.request.urlopen(request, timeout=30) as response:
            page = response.read().decode('utf-8', 'replace')
        data = snapshot(page, now)
        text = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        if args.latest:
            write_atomic(args.latest, text)
        try:
            data['repo_stars'] = repo_stars(data['rows'])
        except Exception as error:
            data['repo_stars'] = {}
            receipt['stars_error'] = f'{type(error).__name__}: {error}'[:200]
        write_atomic(args.history / f'{now:%Y-%m-%d}.json', json.dumps(data, separators=(',', ':'), ensure_ascii=False))
        receipt.update(ok=True, rows=len(data['rows']), repos_with_stars=len(data['repo_stars']))
    except Exception as error:
        receipt['error'] = f'{type(error).__name__}: {error}'[:300]
    args.history.mkdir(parents=True, exist_ok=True)
    with (args.history / 'runs.jsonl').open('a') as log:
        log.write(json.dumps(receipt) + '\n')
    print(json.dumps(receipt))
    return 0 if receipt['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
