"""Rank the working-set picks by measured use and attach dated GitHub stars.

Reads evidence/our-skill-usage-2026-11-08.json (counts and stars measured
outside this repo) and the published catalog. Writes site/oscar-picks.json.
No network calls: stars come only from the evidence file.
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/our-skill-usage-2026-11-08.json'
OUT = ROOT / 'site/oscar-picks.json'


def build():
    sys.path.insert(0, str(ROOT))
    import published_catalog
    catalog = {s['id']: s for s in published_catalog.load()['skills']}
    ev = json.loads(EVIDENCE.read_text())
    old = json.loads(OUT.read_text())
    previous = {p['name']: p for p in old['picks']}
    window = 'Used in {n} of our Claude Code session{s}, 9 Oct to 8 Nov 2026.'
    working = []
    for row in ev['skills']:
        if row['sessions'] <= 0:
            continue
        prev = previous.get(row['skill'], {})
        catalog_id = prev.get('catalog_id')
        if catalog_id is None and row.get('public_repo'):
            match = [s for s in catalog.values() if s['name'] == row['skill'] and s['repo'] == row['public_repo']]
            catalog_id = match[0]['id'] if match else None
        repo = catalog[catalog_id]['repo'] if catalog_id in catalog else None
        stars = ev['stars'].get(repo) if repo else None
        relation = prev.get('catalog_relation') or ('Public version in this catalogue.' if catalog_id else 'Local skill; no verified equivalent in this catalogue.')
        working.append({
            'name': row['skill'],
            'reason': prev.get('reason') or (catalog[catalog_id]['problem'] if catalog_id in catalog else ''),
            'basis': window.format(n=row['sessions'], s='' if row['sessions'] == 1 else 's'),
            'catalog_id': catalog_id,
            'catalog_relation': relation,
            'kind': 'working-set',
            'uses': row['sessions'],
            'stars': stars,
            'stars_repo': repo if stars is not None else None,
            'stars_as_of': ev['stars_as_of'] if stars is not None else None,
        })
    working.sort(key=lambda p: (-p['uses'], p['name']))
    for i, p in enumerate(working, 1):
        p['rank'] = i
    try_next = []
    for p in old['picks']:
        if p['kind'] != 'try-next':
            continue
        p = dict(p)
        repo = catalog[p['catalog_id']]['repo'] if p.get('catalog_id') in catalog else None
        stars = ev['stars'].get(repo) if repo else None
        p.update({'stars': stars, 'stars_repo': repo if stars is not None else None,
                  'stars_as_of': ev['stars_as_of'] if stars is not None else None})
        try_next.append(p)
    return {
        'counted_at': ev['counted_at'],
        'stars_as_of': ev['stars_as_of'],
        'usage_scope': ev['method'],
        'picks': working + try_next,
    }


def main():
    OUT.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + '\n')
    print(json.dumps({'picks': str(OUT.relative_to(ROOT)), 'network': False}))


if __name__ == '__main__':
    main()
