"""Bounded incremental catalog refresh. Dry run by default: GitHub metadata only, no file bodies.

Identity rule: an entry id is sha256(stored repo + path)[:16]. A renamed GitHub repository keeps its
stored repo string as the catalog key, so ids and their votes survive. The new name is used only to fetch.
Unchanged sources are skipped. Only added or modified SKILL.md bodies are downloaded (raw files, never a
zipball). Output goes to evidence/hosted-catalog.next.json; the live catalog file is never overwritten.
"""
import argparse, concurrent.futures, copy, datetime, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from pull_catalog import field  # noqa: E402

SKILL = lambda p: p == 'SKILL.md' or p.endswith('/SKILL.md')


def gh(path):
    p = subprocess.run(['gh', 'api', path], capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise ValueError('GitHub metadata request failed: ' + path)
    return json.loads(p.stdout)


def raw_get(url, cap=1_000_000):
    import urllib.request
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'skillwire-incremental-read-only'}), timeout=60) as r:
        body = r.read(cap + 1)
    if len(body) > cap:
        raise ValueError('file exceeds cap')
    return body


def skill_blobs(tree):
    if tree.get('truncated'):
        raise ValueError('GitHub recursive tree truncated; coverage incomplete')
    return {x['path']: (x['sha'], x.get('size', 0)) for x in tree['tree'] if x['type'] == 'blob' and SKILL(x['path']) and x.get('size', 0) < 1_000_000}


def entry_id(key, path):
    return hashlib.sha256((key + path).encode()).hexdigest()[:16]


def plan(catalog, api=gh):
    """Metadata only. Returns one row per source with what a refresh would fetch and drop."""
    rows = []
    for src in catalog['sources']:
        key = src['repo']
        meta = api('repos/' + key)
        canonical = meta['full_name']
        head = api('repos/' + canonical + '/commits/' + meta['default_branch'])['sha']
        row = dict(key=key, canonical=canonical, old_revision=src['revision'], new_revision=head, changed=head != src['revision'],
                   stars=meta['stargazers_count'], license=(meta.get('license') or {}).get('spdx_id', 'Unknown'))
        if row['changed']:
            new_tree = api('repos/' + canonical + '/git/trees/' + head + '?recursive=1')
            new = skill_blobs(new_tree)
            old = skill_blobs(api('repos/' + canonical + '/git/trees/' + src['revision'] + '?recursive=1'))
            row.update(tree=new_tree, fetch=sorted(p for p in new if p not in old or new[p][0] != old[p][0]),
                       drop=sorted(p for p in old if p not in new), keep=sorted(p for p in new if p in old and new[p][0] == old[p][0]),
                       fetch_bytes=sum(new[p][1] for p in new if p not in old or new[p][0] != old[p][0]))
        rows.append(row)
    return rows


def new_entry(key, canonical, revision, path, body, readme, row, stamp):
    text = body.decode(errors='replace')
    names = [label for label, pat in [('Claude Code', 'claude code'), ('Codex', 'codex'), ('Cursor', 'cursor'), ('Gemini CLI', 'gemini cli')] if pat in text.lower()]
    basis = 'stated in skill'
    if not names:
        names = [label for label, pat in [('Claude Code', 'claude code'), ('Codex', 'codex'), ('Cursor', 'cursor'), ('Gemini CLI', 'gemini cli')] if pat in readme.lower()]
        basis = 'stated in repository'
    if not names:
        names, basis = ['Agent Skills compatible'], 'inferred from SKILL.md format'
    return dict(id=entry_id(key, path), name=field(text, 'name') or Path(path).parent.name or key.split('/')[-1], problem='', category='Development',
                category_basis='inferred by keyword rule', models=names, model_basis=basis, model_evidence=[], repo=key, path=path, revision=revision,
                sha256=hashlib.sha256(body).hexdigest(), source='https://github.com/' + canonical + '/blob/' + revision + '/' + path,
                stars=row['stars'], installs=None, fetched_at=stamp, license=row['license'], eval={'status': 'Not tested', 'n': 0, 'model': None, 'date': None})


def apply(catalog, rows, repos, max_bytes, max_seconds, disk_floor_gb, get=raw_get, write_cache=True):
    """Fetch only the selected changed repos, inside hard limits. Returns (next catalog, receipt)."""
    start = time.monotonic()
    chosen = [r for r in rows if r['changed'] and r['key'] in repos]
    planned = sum(r['fetch_bytes'] for r in chosen)
    if planned > max_bytes:
        raise SystemExit(f'planned {planned} bytes exceeds --max-bytes {max_bytes}')
    free = shutil.disk_usage(ROOT).free / 1e9
    if free < disk_floor_gb:
        raise SystemExit(f'free disk {free:.1f} GB is under the {disk_floor_gb} GB floor')
    out = copy.deepcopy(catalog)
    by_key = {s['repo']: s for s in out['sources']}
    receipt = dict(started=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), repos=[], fetched_bytes=0, removed_ids=[], added_ids=[], modified_ids=[], errors=[])
    stamp = receipt['started']
    for r in chosen:
        if time.monotonic() - start > max_seconds:
            receipt['errors'].append({'repo': r['key'], 'error': 'time limit reached; repo left at old revision'})
            continue
        key, canonical, rev = r['key'], r['canonical'], r['new_revision']
        try:
            readme = get('https://raw.githubusercontent.com/' + canonical + '/' + rev + '/README.md').decode(errors='replace')
        except Exception:
            readme = ''
        bodies, errors = {}, []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(get, 'https://raw.githubusercontent.com/' + canonical + '/' + rev + '/' + p): p for p in r['fetch']}
            for f in concurrent.futures.as_completed(futures):
                try:
                    bodies[futures[f]] = f.result()
                except Exception as e:
                    errors.append({'repo': key, 'path': futures[f], 'error': type(e).__name__})
        if errors:
            # All or nothing per repo: a partial repo would mix revisions.
            receipt['errors'] += errors
            continue
        cache = ROOT / 'data/hosted-sources' / key.replace('/', '--')
        if write_cache:
            cache.mkdir(parents=True, exist_ok=True)
            (cache / 'tree.json').write_text(json.dumps(r['tree']))
            for b in bodies.values():
                (cache / (hashlib.sha256(b).hexdigest() + '.md')).write_bytes(b)
        receipt['fetched_bytes'] += sum(map(len, bodies.values()))
        drop = set(r['drop'])
        existing = {s['path']: s for s in out['skills'] if s['repo'] == key}
        kept = []
        for s in out['skills']:
            if s['repo'] != key:
                kept.append(s); continue
            if s['path'] in drop:
                receipt['removed_ids'].append(s['id']); continue
            if s['path'] in bodies:
                continue  # replaced below with the same id
            s['revision'] = rev
            s['source'] = 'https://github.com/' + canonical + '/blob/' + rev + '/' + s['path']
            kept.append(s)
        seen = {(s['repo'], s['sha256']): s for s in kept if s['repo'] == key}
        for p in sorted(bodies, key=len):
            e = new_entry(key, canonical, rev, p, bodies[p], readme, r, stamp)
            if p in existing:
                e.update({k: existing[p][k] for k in ('eval',) if k in existing[p]})
                receipt['modified_ids'].append(e['id'])
            twin = seen.get((key, e['sha256']))
            if twin:
                # Existing entries win, so a new byte-identical copy never takes over an id that holds votes.
                twin.setdefault('duplicate_paths', []).append(p); continue
            if p not in existing:
                receipt['added_ids'].append(e['id'])
            seen[(key, e['sha256'])] = e
            kept.append(e)
        out['skills'] = kept
        by_key[key].update(revision=rev, stars=r['stars'], license=r['license'], fetched_at=stamp, skills=sum(1 for s in kept if s['repo'] == key),
                           canonical=canonical, fetch_mode='incremental: pinned tree + changed raw SKILL.md only')
        receipt['repos'].append(dict(key=key, canonical=canonical, revision=rev, fetched=len(bodies), dropped=len(drop)))
    if write_cache:
        finish_new(out, set(receipt['added_ids']) | set(receipt['modified_ids']))
    check_ids(catalog, out, rows, receipt)
    receipt['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    receipt['seconds'] = round(time.monotonic() - start, 1)
    out['fetched_at'] = receipt['finished']
    out['incremental_refresh'] = {k: receipt[k] for k in ('started', 'finished', 'fetched_bytes')} | {'repos': [x['key'] for x in receipt['repos']]}
    return out, receipt


def finish_new(out, ids):
    """Same description, category and model fields the full pipeline gives, applied to new bodies only.
    Popular stays frozen: enrich() would re-rank it, and the landing vote list reads it."""
    from normalize_catalog import description
    from curate_catalog import RULES, plain
    from enrich_catalog import enrich
    fresh = [s for s in out['skills'] if s['id'] in ids]
    for s in fresh:
        body = (ROOT / 'data/hosted-sources' / s['repo'].replace('/', '--') / (s['sha256'] + '.md')).read_text()
        d = description(body)
        s['problem'] = plain(d[:500]) if d else 'Use ' + s['name'].replace('-', ' ') + ' instructions for the task described in the source.'
        s['problem_basis'] = 'source-description summary/excerpt; not independently verified' if d else 'inferred from skill name; source lacks a usable description'
        s['category'] = next(k for k, pat in RULES.items() if __import__('re').search(pat, s['name'].replace('-', ' ') + ' ' + s['problem'], __import__('re').I))
        s['category_basis'] = 'inferred from name/description keyword rules'
    done = {s['id']: s for s in enrich({'skills': fresh})['skills']}
    out['skills'] = [done.get(s['id'], s) for s in out['skills']]


def check_ids(before, after, rows, receipt):
    """Every old entry must keep its id unless its file was removed upstream, or it collapsed into a twin."""
    gone = set(receipt['removed_ids'])
    now = {s['id'] for s in after['skills']}
    lost = [s['id'] for s in before['skills'] if s['id'] not in now and s['id'] not in gone]
    if lost:
        raise SystemExit(f'{len(lost)} existing ids would disappear without an upstream removal, e.g. {lost[:3]}')
    bad = [s['id'] for s in after['skills'] if s['id'] != entry_id(s['repo'], s['path'])]
    if bad:
        raise SystemExit(f'{len(bad)} ids no longer equal sha256(repo+path), e.g. {bad[:3]}')


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument('--catalog', type=Path, default=ROOT / 'evidence/hosted-catalog.json')
    a.add_argument('--plan-out', type=Path, required=True)
    a.add_argument('--fetch', action='store_true', help='download changed SKILL.md bodies; without it nothing is downloaded')
    a.add_argument('--repos', default='', help='comma-separated stored repo keys to refresh in this batch')
    a.add_argument('--max-repos', type=int, default=0)
    a.add_argument('--max-bytes', type=int, default=0)
    a.add_argument('--max-seconds', type=int, default=0)
    a.add_argument('--disk-floor-gb', type=float, default=5.0)
    x = a.parse_args(argv)
    catalog = json.loads(x.catalog.read_text())
    rows = plan(catalog)
    slim = [{k: v for k, v in r.items() if k != 'tree'} | ({'fetch': len(r['fetch']), 'drop': len(r['drop']), 'keep': len(r['keep'])} if r['changed'] else {}) for r in rows]
    x.plan_out.write_text(json.dumps(dict(planned_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), sources=slim), indent=1))
    print(json.dumps(dict(changed=sum(r['changed'] for r in rows), fetch_files=sum(len(r.get('fetch', [])) for r in rows),
                          fetch_bytes=sum(r.get('fetch_bytes', 0) for r in rows), drop_files=sum(len(r.get('drop', [])) for r in rows))))
    if not x.fetch:
        return 0
    repos = [r for r in x.repos.split(',') if r]
    if not repos or not x.max_repos or not x.max_bytes or not x.max_seconds or len(repos) > x.max_repos:
        raise SystemExit('--fetch needs --repos, and explicit --max-repos >= len(repos), --max-bytes and --max-seconds')
    out, receipt = apply(catalog, rows, set(repos), x.max_bytes, x.max_seconds, x.disk_floor_gb)
    (ROOT / 'evidence/hosted-catalog.next.json').write_text(json.dumps(out, indent=2))
    (ROOT / 'evidence/incremental-refresh-receipt.json').write_text(json.dumps(receipt, indent=1))
    print(json.dumps({k: receipt[k] for k in ('seconds', 'fetched_bytes', 'errors')} | {'added': len(receipt['added_ids']), 'modified': len(receipt['modified_ids']), 'removed': len(receipt['removed_ids'])}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
