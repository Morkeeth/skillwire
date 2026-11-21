"""Daily reading of the public skills.sh home page. One request, kept as dated history.

Writes HISTORY/YYYY-MM-DD.json and a run receipt. With --latest PATH it also refreshes
the copy the site build reads. A failed or short reading never replaces a good one.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import skill_charts

URL = 'https://www.skills.sh/'
MIN_ROWS = 300
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
        write_atomic(args.history / f'{now:%Y-%m-%d}.json', text)
        if args.latest:
            write_atomic(args.latest, text)
        receipt.update(ok=True, rows=len(data['rows']))
    except Exception as error:
        receipt['error'] = f'{type(error).__name__}: {error}'[:300]
    args.history.mkdir(parents=True, exist_ok=True)
    with (args.history / 'runs.jsonl').open('a') as log:
        log.write(json.dumps(receipt) + '\n')
    print(json.dumps(receipt))
    return 0 if receipt['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
