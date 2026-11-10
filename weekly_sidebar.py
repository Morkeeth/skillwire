"""Offline, dated evidence for Browse's weekly sidebar. No votes or model calls."""
from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path

METRIC = 'skills.sh reported installs (rounded)'


def day(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Observation timestamp needs a timezone')
    return parsed.date()


def count(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if math.isfinite(value) and value >= 0 and int(value) == value else None


def identity(skill):
    return skill['repo'].casefold() + '/' + skill['path']


def observation(catalog):
    source = catalog.get('marketplace_source', {})
    stamp = source.get('fetched_at')
    if not stamp or source.get('url') != 'https://skills.sh/':
        return None
    day(stamp)  # Never substitute build time or the repository-star fetch date.
    rows = {}
    for skill in catalog['skills']:
        value = count(skill.get('installs'))
        if value is not None:
            key = identity(skill)
            if key in rows and rows[key] != value:
                raise ValueError('Conflicting install counts for one skill')
            rows[key] = value
    return {'observed_at': stamp, 'provider': source['url'], 'metric': METRIC,
            'source_sha256': source.get('raw_sha256'), 'counts': rows}


def growth(catalog, history, issue_date):
    unavailable = {'status': 'unavailable', 'rows': [], 'reason':
                   'Two compatible install observations seven days apart are not retained.'}
    try:
        current = observation(catalog)
    except (ValueError, TypeError):
        return {**unavailable, 'reason': 'Install observation metadata is inconsistent; no ranking is published.'}
    if current is None:
        return {**unavailable, 'reason': 'No dated install observation is retained.'}
    unavailable['latest_observed_at'] = current['observed_at']
    snapshots = {}
    for item in [*history, current]:
        if item.get('provider') != current['provider'] or item.get('metric') != METRIC:
            continue
        stamp = item.get('observed_at', '')
        try:
            observed = day(stamp)
        except (ValueError, TypeError):
            continue
        if observed > issue_date:
            continue
        values = item.get('counts', {})
        if not isinstance(values, dict) or any(count(v) is None for v in values.values()):
            continue
        values = {k: count(v) for k, v in values.items()}
        if stamp in snapshots and snapshots[stamp]['counts'] != values:
            return {**unavailable, 'reason': 'Conflicting counts share one observation time; no ranking is published.'}
        snapshots[stamp] = {**item, 'counts': values}
    if not snapshots:
        return unavailable
    latest = max(snapshots.values(), key=lambda s: datetime.fromisoformat(s['observed_at'].replace('Z', '+00:00')))
    latest_day = day(latest['observed_at'])
    if (issue_date - latest_day).days > 7:
        return {**unavailable, 'reason': 'No recent weekly comparison is retained. The install observation is dated ' + latest_day.isoformat() + '.'}
    earlier = [s for s in snapshots.values() if (latest_day - day(s['observed_at'])).days == 7]
    if not earlier:
        return unavailable
    before = max(earlier, key=lambda s: s['observed_at'])
    rows = []
    matched = 0
    decreases = 0
    seen = set()
    for skill in sorted(catalog['skills'], key=lambda s: s['id']):
        key = identity(skill)
        if key in seen:
            continue
        seen.add(key)
        if key not in before['counts'] or key not in latest['counts']:
            continue
        matched += 1
        start, end = before['counts'][key], latest['counts'][key]
        if end < start:
            decreases += 1
            continue
        if end > start:
            rows.append({'id': skill['id'], 'name': skill['name'], 'repo': skill['repo'],
                         'before': start, 'after': end, 'change': end - start})
    rows.sort(key=lambda s: (-s['change'], s['repo'].casefold(), s['name'].casefold(), s['id']))
    return {'status': 'available', 'metric': METRIC, 'from': before['observed_at'],
            'to': latest['observed_at'], 'matched_entries': matched,
            'decreased_counters_excluded': decreases, 'rows': rows[:3],
            'reason': 'Largest increases among matched entries. Rounded source reports, not verified active users.'}


def feature(catalog, picks, issue_date):
    missing = {'status': 'unavailable', 'reason': 'No recent, dated host usage count is retained for a public catalog entry.'}
    try:
        counted = date.fromisoformat(picks['counted_at'])
    except (ValueError, KeyError, TypeError):
        return missing
    if not 0 <= (issue_date - counted).days <= 14:
        return missing
    skills = {s['id']: s for s in catalog['skills']}
    eligible = [p for p in picks.get('picks', []) if p.get('kind') == 'working-set'
                and p.get('catalog_id') in skills and count(p.get('uses')) not in (None, 0)]
    if not eligible:
        return missing
    eligible.sort(key=lambda p: (-count(p['uses']), p['catalog_id']))
    pick = eligible[0]
    skill = skills[pick['catalog_id']]
    return {'status': 'available', 'id': skill['id'], 'name': skill['name'],
            'repo': skill['repo'], 'uses': count(pick['uses']), 'counted_at': counted.isoformat(),
            'count_window_days': 30, 'basis': pick['basis'],
            'catalog_relation': pick['catalog_relation'],
            'method': 'Highest recorded host session count among catalog-linked working-set picks; ties use catalog ID. Counts cover 30 days, not one week. Not a public vote or quality score.'}


def build(catalog, picks, history, issue_date):
    issue = date.fromisoformat(issue_date)
    week = issue - timedelta(days=issue.weekday())
    return {'schema': 1, 'issue_date': issue.isoformat(), 'week_start': week.isoformat(),
            'week_end': (week + timedelta(days=6)).isoformat(),
            'fastest_growing': growth(catalog, history, issue),
            'skill_of_week': feature(catalog, picks, issue)}


def build_for_site(root, catalog, out):
    policy = json.loads((root/'site/weekly-policy.json').read_text())
    retained = json.loads((root/'evidence/weekly-install-observations.json').read_text())
    picks = json.loads((root/'site/oscar-picks.json').read_text())
    value = build(catalog, picks, retained['observations'], policy['issue_date'])
    (out/'weekly.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return value
