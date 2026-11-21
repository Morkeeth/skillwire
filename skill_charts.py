"""Three static chart pages: Hot this week, All-time high, Curated.

Numbers come from a dated copy of the public skills.sh home page. The build makes
no network calls. Repository stars are never blended into a per-skill score.
"""
from datetime import date
from html import escape
import json
from pathlib import Path

WEEKS = 8
REPO_CAP = 3
HOT_FLOOR = 500
HOT_LIMIT = 30
ALL_TIME_LIMIT = 50
MIRROR_WEEKS = 5
MIRROR_TOLERANCE = 0.02
MIRROR_MIN_INSTALLS = 1000
PACK_MIN_SHARED = 3
NEVER_CURATED = {'job-hunt'}
SNAPSHOT = 'evidence/skills-sh-latest.json'
NOTES = 'site/curated-notes.json'
PICKS = 'site/oscar-picks.json'
PAGES = (('hot', 'Hot this week'), ('all-time', 'All-time high'), ('curated', 'Curated'))


def parse_home(page):
    text = page.replace('\\"', '"')
    marker = '"initialSkills":'
    start = text.find(marker)
    if start < 0:
        raise ValueError('skills.sh page has no skill list')
    rows, _ = json.JSONDecoder().raw_decode(text[start + len(marker):])
    return [row for row in rows if len(row.get('weeklyInstalls') or []) == WEEKS]


def _key(row):
    return row['source'], row['skillId']


def _owner(row):
    return row['source'].split('/')[0].casefold()


def _same_curve(a, b):
    first, second = a['weeklyInstalls'][:MIRROR_WEEKS], b['weeklyInstalls'][:MIRROR_WEEKS]
    if sum(first) < MIRROR_MIN_INSTALLS or sum(second) < MIRROR_MIN_INSTALLS:
        return False
    return all(abs(x - y) <= MIRROR_TOLERANCE * max(x, y) for x, y in zip(first, second))


def _copied_packs(rows):
    repos = {}
    for row in rows:
        repos.setdefault(row['source'], {})[row['skillId'].casefold()] = row
    found = set()
    names = sorted(repos)
    for index, a in enumerate(names):
        for b in names[index + 1:]:
            if '/' not in a or '/' not in b:
                continue
            owner_a, base_a = a.casefold().split('/', 1)
            owner_b, base_b = b.casefold().split('/', 1)
            shared = repos[a].keys() & repos[b].keys()
            if owner_a != owner_b and base_a == base_b and len(shared) >= PACK_MIN_SHARED:
                found.update(_key(repos[a][name]) for name in shared)
                found.update(_key(repos[b][name]) for name in shared)
    return found


def mirrors(rows):
    """Copied listings: one install history under two owners, or one skill pack in same-named repos."""
    found = _copied_packs(rows)
    by_name = {}
    for row in rows:
        by_name.setdefault(row['skillId'].casefold(), []).append(row)
    for group in by_name.values():
        for index, a in enumerate(group):
            for b in group[index + 1:]:
                if _owner(a) != _owner(b) and _same_curve(a, b):
                    found.update((_key(a), _key(b)))
    return found


def _capped(rows, limit):
    seen, kept = {}, []
    for row in rows:
        repo = row['source'].casefold()
        if seen.get(repo, 0) < REPO_CAP:
            seen[repo] = seen.get(repo, 0) + 1
            kept.append(row)
        if len(kept) == limit:
            break
    return kept


def _public(row):
    return {'name': row['name'], 'source': row['source'], 'skill_id': row['skillId'],
            'installs': row['installs'], 'weeks': list(row['weeklyInstalls'])}


def hot(rows, limit=HOT_LIMIT):
    hidden = mirrors(rows)
    ranked = []
    for row in rows:
        previous, latest = row['weeklyInstalls'][-2], row['weeklyInstalls'][-1]
        gain = latest - previous
        if _key(row) in hidden or gain < HOT_FLOOR:
            continue
        ranked.append({**_public(row), 'gain': gain, 'latest': latest, 'is_new': previous == 0,
                       'pct': round(gain / previous * 100) if previous else None})
    ranked.sort(key=lambda r: (-r['gain'], r['source'].casefold(), r['name']))
    return _capped(ranked, limit)


def all_time(rows, limit=ALL_TIME_LIMIT):
    hidden = mirrors(rows)
    ranked = [_public(r) for r in rows if _key(r) not in hidden]
    ranked.sort(key=lambda r: (-r['installs'], r['source'].casefold(), r['name']))
    return _capped(ranked, limit)


def curated(picks, notes):
    chosen = [{'name': p['name'], 'why': notes[p['name']], 'uses': p['uses'],
               'catalog_id': p.get('catalog_id')}
              for p in picks['picks']
              if p.get('kind') == 'working-set' and p['name'] not in NEVER_CURATED and notes.get(p['name'])]
    return sorted(chosen, key=lambda p: (-p['uses'], p['name']))


def _count(value):
    for limit, suffix in ((1_000_000, 'M'), (1_000, 'K')):
        if value >= limit:
            return f'{value / limit:.1f}'.rstrip('0').rstrip('.') + suffix
    return str(value)


def _day(value):
    parsed = date.fromisoformat(value[:10])
    return f'{parsed.day} {parsed:%b %Y}'


def _spark(weeks):
    top = max(weeks) or 1
    step = 84 / (len(weeks) - 1)
    points = ' '.join(f'{index * step + 2:.1f},{24 - value / top * 20:.1f}' for index, value in enumerate(weeks))
    return (f'<svg class="spark" viewBox="0 0 88 28" role="img" aria-label="Installs over {len(weeks)} weeks">'
            f'<polyline points="{points}"/></svg>')


def _listing(row):
    return f'https://skills.sh/{escape(row["source"], True)}/{escape(row["skill_id"], True)}'


def _hot_rows(rows):
    items = []
    for rank, row in enumerate(rows, 1):
        change = 'new' if row['is_new'] else f'+{row["pct"]}%'
        items.append(
            f'<li><span class="rank">{rank}</span><span class="who"><a href="{_listing(row)}">{escape(row["name"])}</a>'
            f'<small>{escape(row["source"])}</small></span>{_spark(row["weeks"])}'
            f'<span class="num"><b>+{_count(row["gain"])}</b><small>{_count(row["latest"])} this week</small>'
            f'<small class="pct">{change}</small></span></li>')
    return items


def _all_time_rows(rows):
    return [
        f'<li><span class="rank">{rank}</span><span class="who"><a href="{_listing(row)}">{escape(row["name"])}</a>'
        f'<small>{escape(row["source"])}</small></span>{_spark(row["weeks"])}'
        f'<span class="num"><b>{_count(row["installs"])}</b><small>installs</small></span></li>'
        for rank, row in enumerate(rows, 1)]


def _curated_rows(rows):
    items = []
    for rank, row in enumerate(rows, 1):
        name = escape(row['name'])
        title = f'<a href="/search#{escape(row["catalog_id"], True)}">{name}</a>' if row.get('catalog_id') else f'<strong>{name}</strong>'
        items.append(
            f'<li class="pick"><span class="rank">{rank}</span><span class="who">{title}<small>{escape(row["why"])}</small></span>'
            f'<span class="num"><b>{row["uses"]}</b><small>sessions</small></span></li>')
    return items


def render(page, data):
    as_of = _day(data['as_of'])
    hidden = data.get('hidden_mirrors', 0)
    copies = f' {hidden} copied listings are hidden.' if hidden else ''
    if page == 'hot':
        heading, intro, items = 'Hot this week', (
            f'Biggest jump in weekly installs on skills.sh, latest week against the week before, read {as_of}. '
            f'Each repo gets three places at most.{copies}'), _hot_rows(data['hot'])
        empty = 'No weekly numbers right now. The last reading could not be used.'
    elif page == 'all-time':
        heading, intro, items = 'All-time high', (
            f'Most installs ever reported by skills.sh, read {as_of}. '
            f'Each repo gets three places at most.{copies}'), _all_time_rows(data['all_time'])
        empty = 'No install totals right now. The last reading could not be used.'
    else:
        heading, intro, items = 'Curated', (
            'The skills Oscar keeps coming back to, ordered by sessions in the 30 days to 8 Nov 2026.'
        ), _curated_rows(data['curated'])
        empty = 'No picks yet.'
    tabs = ''.join(
        f'<a href="/{key}"{" aria-current=\"page\"" if key == page else ""}>{label}</a>' for key, label in PAGES)
    body = f'<ol class="chart">{"".join(items)}</ol>' if items else f'<p class="empty">{empty}</p>'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{heading} · SkillWire</title><meta name="referrer" content="strict-origin">
<link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/charts.css"><script defer src="/analytics.js"></script><script src="/skill-link.js"></script></head>
<body><div class="window"><header class="bar"><img src="/favicon.svg" alt=""><strong>SkillWire</strong><a class="find" href="/search">Search all skills</a></header>
<nav class="tabs" aria-label="Charts">{tabs}</nav>
<main><h1>{heading}</h1><p class="intro">{intro}</p>{body}</main>
<footer>Installs are reported by <a href="https://skills.sh/">skills.sh</a>. They show what people download, and they do not show whether a skill helps.</footer>
</div></body></html>
'''


def build_for_site(root, out):
    root, out = Path(root), Path(out)
    snapshot_path = root / SNAPSHOT
    snapshot = json.loads(snapshot_path.read_text()) if snapshot_path.exists() else {'fetched_at': date.today().isoformat(), 'rows': []}
    rows = snapshot['rows']
    data = {'as_of': snapshot['fetched_at'], 'hidden_mirrors': len(mirrors(rows)), 'hot': hot(rows),
            'all_time': all_time(rows),
            'curated': curated(json.loads((root / PICKS).read_text()), json.loads((root / NOTES).read_text())['notes'])}
    for key, _ in PAGES:
        (out / f'{key}.html').write_text(render(key, data))
    return {key: len(data[name]) for key, name in (('hot', 'hot'), ('all-time', 'all_time'), ('curated', 'curated'))}
