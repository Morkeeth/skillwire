"""Weekly refresh of the Hot this week data. Local only: it never deploys.

Takes the newest good daily snapshot, writes it to evidence/skills-sh-latest.json,
builds the chart pages twice and checks the ranking is identical, exports a release
directory, and compares the read date on the live site. Writes one receipt line.
Deploying the exported directory is a separate, human-approved step.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import skill_charts  # noqa: E402

LIVE = 'https://skillwire.net/hot'
MIN_ROWS = 300
STALE_DAYS = 3


def newest_snapshot(history):
    for path in sorted(history.glob('20??-??-??.json'), reverse=True):
        data = json.loads(path.read_text())
        if len(data.get('rows', [])) >= MIN_ROWS:
            return path, data
    raise ValueError(f'no snapshot with at least {MIN_ROWS} rows in {history}')


def week_curves(rows):
    return sorted((row['source'], row['skillId'], tuple(row['weeklyInstalls'])) for row in rows)


def page_hashes(out):
    skill_charts.build_for_site(ROOT, out)
    return {key: hashlib.sha256((out / f'{key}.html').read_bytes()).hexdigest() for key, _ in skill_charts.PAGES}


def live_read_date(url=LIVE):
    request = urllib.request.Request(url, headers={'User-Agent': 'SkillWire-weekly-refresh/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode('utf-8', 'replace')
    found = re.search(r'read (\d{1,2} [A-Z][a-z]{2} \d{4})', page)
    return datetime.strptime(found.group(1), '%d %b %Y').date() if found else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', type=Path, default=Path.home() / '.local/state/fleet/skillwire-history')
    parser.add_argument('--receipts', type=Path, default=Path.home() / '.local/state/fleet/skillwire-history/weekly-runs.jsonl')
    parser.add_argument('--no-export', action='store_true')
    parser.add_argument('--no-live', action='store_true')
    args = parser.parse_args()
    receipt = {'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'ok': False}
    try:
        fresh = subprocess.run([sys.executable, 'scripts/snapshot_skills.py', '--history', str(args.history)],
                               cwd=ROOT, capture_output=True, text=True, timeout=300)
        receipt['fresh_reading_ok'] = fresh.returncode == 0
        path, data = newest_snapshot(args.history)
        previous_path = ROOT / skill_charts.SNAPSHOT
        if previous_path.exists():
            previous = json.loads(previous_path.read_text())
            receipt['previous_read'] = previous['fetched_at'][:10]
            receipt['week_rolled'] = week_curves(previous['rows']) != week_curves(data['rows'])
        latest = {'schema': data.get('schema', 1), 'source': data['source'], 'fetched_at': data['fetched_at'], 'rows': data['rows']}
        (ROOT / skill_charts.SNAPSHOT).write_text(json.dumps(latest, separators=(',', ':'), ensure_ascii=False))
        receipt.update(snapshot=path.name, local_read=data['fetched_at'][:10], rows=len(data['rows']))
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first, second = page_hashes(Path(one)), page_hashes(Path(two))
        receipt['same_ranking_twice'] = first == second
        if first != second:
            raise ValueError('two builds from the same snapshot differ')
        hot = skill_charts.hot(data['rows'])
        receipt['hot_top3'] = [f'{row["source"]}/{row["skill_id"]}' for row in hot[:3]]
        build = subprocess.run([sys.executable, 'scripts/build_site.py'], cwd=ROOT, capture_output=True, text=True, timeout=600)
        if build.returncode:
            raise RuntimeError('build failed: ' + build.stderr[-300:])
        if not args.no_export:
            export = subprocess.run([sys.executable, 'scripts/export_release.py'], cwd=ROOT, capture_output=True, text=True, timeout=300)
            if export.returncode:
                raise RuntimeError('export failed: ' + export.stderr[-300:])
            release = export.stdout.strip().splitlines()[-1]
            receipt.update(release=release, deploy_command=f'vercel deploy {release} --prod --yes')
        receipt['ok'] = True
    except Exception as error:
        receipt['error'] = f'{type(error).__name__}: {error}'[:300]
    if not args.no_live:
        try:
            live = live_read_date()
            receipt['live_read'] = live.isoformat() if live else None
            if live and receipt.get('local_read'):
                behind = (date.fromisoformat(receipt['local_read']) - live).days
                receipt['live_behind_days'] = behind
                receipt['live_stale'] = behind >= STALE_DAYS
        except Exception as error:
            receipt['live_error'] = f'{type(error).__name__}: {error}'[:200]
    args.receipts.parent.mkdir(parents=True, exist_ok=True)
    with args.receipts.open('a') as log:
        log.write(json.dumps(receipt) + '\n')
    print(json.dumps(receipt))
    red = not receipt['ok'] or receipt.get('live_stale') or receipt.get('week_rolled') is False
    return 1 if red else 0


if __name__ == '__main__':
    raise SystemExit(main())
