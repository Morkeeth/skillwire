"""Bounded incremental catalog refresh. Dry run by default: GitHub metadata only, no file bodies.

Identity rule: an entry id is sha256(stored repo + path)[:16]. A renamed GitHub repository keeps its
stored repo string as the catalog key, so ids and their votes survive. The new name is used only to fetch.
Unchanged sources are skipped. Only added or modified SKILL.md bodies are downloaded (raw files, never a
zipball). Output goes to evidence/hosted-catalog.next.json; the live catalog file is never overwritten.
"""
import argparse, copy, datetime, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from pull_catalog import field  # noqa: E402

SKILL = lambda p: p == 'SKILL.md' or p.endswith('/SKILL.md')


class Budget:
    """One serial network budget includes metadata and bodies, including failed repos."""
    def __init__(self, max_bytes, max_seconds):
        if max_bytes <= 0 or max_seconds <= 0:
            raise ValueError('positive byte and time bounds required')
        self.limit, self.used = max_bytes, 0
        self.deadline = time.monotonic() + max_seconds

    def remaining(self):
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError('batch deadline reached')
        return value

    def get(self, url, cap=1_000_000):
        import urllib.request
        self.remaining()
        available = min(cap, self.limit - self.used)
        if available <= 0:
            raise ValueError('batch byte cap reached')
        request = urllib.request.Request(url, headers={'User-Agent': 'skillwire-bounded-refresh', 'Accept': 'application/vnd.github+json'})
        chunks = []
        # No retries, no executors waiting beyond the deadline, no archives.
        with urllib.request.urlopen(request, timeout=min(15, self.remaining())) as response:
            while available:
                # A socket read may wait only until the common deadline.
                response.fp.raw._sock.settimeout(min(15, self.remaining()))
                part = response.read1(min(64_000, available))
                self.used += len(part)
                available -= len(part)
                if not part:
                    return b''.join(chunks)
                chunks.append(part)
                if response.length == 0:
                    return b''.join(chunks)
        raise ValueError('response reached byte cap; incomplete payload rejected')

    def api(self, path):
        return json.loads(self.get('https://api.github.com/' + path, cap=self.limit - self.used))


def gh(path):
    raise ValueError('metadata needs an explicit shared Budget')


def raw_get(url, cap=1_000_000):
    raise ValueError('downloads need an explicit shared Budget')


def skill_blobs(tree):
    if tree.get('truncated'):
        raise ValueError('GitHub recursive tree truncated; coverage incomplete')
    return {x['path']: (x['sha'], x.get('size', 0)) for x in tree['tree'] if x['type'] == 'blob' and SKILL(x['path']) and x.get('size', 0) <= 1_000_000}


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
                       fetch_sizes={p: new[p][1] for p in new if p not in old or new[p][0] != old[p][0]},
                       fetch_shas={p: new[p][0] for p in new if p not in old or new[p][0] != old[p][0]},
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


def apply(catalog, rows, repos, max_bytes, max_seconds, disk_floor_gb, get=raw_get, write_cache=True, protected_ids=()):
    """Fetch only the selected changed repos, inside hard limits. Returns (next catalog, receipt)."""
    start = time.monotonic()
    chosen = [r for r in rows if r['changed'] and r['key'] in repos]
    planned = sum(r['fetch_bytes'] for r in chosen)
    if planned > max_bytes:
        raise SystemExit(f'planned {planned} bytes exceeds --max-bytes {max_bytes}')
    free = shutil.disk_usage(ROOT).free / (1024 ** 3)
    if free < disk_floor_gb:
        raise SystemExit(f'free disk {free:.1f} GB is under the {disk_floor_gb} GB floor')
    out = copy.deepcopy(catalog)
    by_key = {s['repo']: s for s in out['sources']}
    receipt = dict(started=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), repos=[], fetched_bytes=0, removed_ids=[], added_ids=[], modified_ids=[], pinned_ids=[], errors=[])
    stamp = receipt['started']
    for r in chosen:
        if time.monotonic() - start > max_seconds:
            receipt['errors'].append({'repo': r['key'], 'error': 'time limit reached; repo left at old revision'})
            continue
        key, canonical, rev = r['key'], r['canonical'], r['new_revision']
        # Avoid README transfer entirely; compatibility inferred only from the fetched skill.
        readme, bodies, errors = '', {}, []
        for path in r['fetch']:
            try:
                if time.monotonic() - start >= max_seconds:
                    raise TimeoutError('batch deadline reached')
                body = get('https://raw.githubusercontent.com/' + canonical + '/' + rev + '/' + path)
                receipt['fetched_bytes'] += len(body)
                if receipt['fetched_bytes'] > max_bytes:
                    raise ValueError('actual body bytes exceeded cap')
                if len(body) != r['fetch_sizes'][path]:
                    raise ValueError('body size differs from pinned tree')
                blob = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
                if blob != r['fetch_shas'][path]:
                    raise ValueError('body hash differs from pinned tree')
                bodies[path] = body
            except Exception as exc:
                errors.append({'repo': key, 'path': path, 'error': str(exc)})
                break
        if errors:
            receipt['errors'] += errors
            continue
        cache = ROOT / 'data/hosted-sources' / key.replace('/', '--')
        if write_cache:
            cache.mkdir(parents=True, exist_ok=True)
            (cache / 'tree.json').write_text(json.dumps(r['tree']))
            for b in bodies.values():
                (cache / (hashlib.sha256(b).hexdigest() + '.md')).write_bytes(b)
        drop = set(r['drop'])
        existing = {s['path']: s for s in out['skills'] if s['repo'] == key}
        kept = []
        for s in out['skills']:
            if s['repo'] != key:
                kept.append(s); continue
            if (s['id'] in protected_ids or s.get('eval', {}).get('n', 0)) and (s['path'] in drop or s['path'] in bodies):
                receipt['pinned_ids'].append(s['id'])
                bodies.pop(s['path'], None)
                kept.append(s)
                continue
            if s['path'] in drop:
                receipt['removed_ids'].append(s['id']); continue
            if s['path'] in bodies:
                continue  # replaced below with the same id
            folder = Path(s['path']).parent.as_posix()
            prefix = '' if folder == '.' else folder + '/'
            s['folder_files'] = [dict(path=x['path'][len(prefix):], bytes=x.get('size', 0), git_blob_sha=x['sha'], symlink=x.get('mode') == '120000') for x in r['tree']['tree'] if x['type'] == 'blob' and x['path'].startswith(prefix)]
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
            if twin and p not in existing:
                # Existing entries win, so a new byte-identical copy never takes over an id that holds votes.
                twin.setdefault('duplicate_paths', []).append(p); continue
            if p not in existing:
                receipt['added_ids'].append(e['id'])
            folder = Path(p).parent.as_posix()
            prefix = '' if folder == '.' else folder + '/'
            e['folder_files'] = [dict(path=x['path'][len(prefix):], bytes=x.get('size', 0), git_blob_sha=x['sha'], symlink=x.get('mode') == '120000') for x in r['tree']['tree'] if x['type'] == 'blob' and x['path'].startswith(prefix)]
            if p in existing:
                for field in ('popular_ids', 'installs', 'installs_basis', 'installs_source', 'installs_as_of'):
                    if field in existing[p]: e[field] = copy.deepcopy(existing[p][field])
            seen[(key, e['sha256'])] = e
            kept.append(e)
        out['skills'] = kept
        by_key[key].pop('archive_sha256', None)
        by_key[key].update(revision=rev, stars=r['stars'], license=r['license'], fetched_at=stamp, skills=sum(1 for s in kept if s['repo'] == key),
                           canonical=canonical, fetch_mode='incremental: pinned tree + changed raw SKILL.md only')
        receipt['repos'].append(dict(key=key, canonical=canonical, revision=rev, fetched=len(bodies), dropped=len(drop)))
    if write_cache:
        finish_new(out, set(receipt['added_ids']) | set(receipt['modified_ids']))
    check_ids(catalog, out, rows, receipt)
    receipt['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    receipt['seconds'] = round(time.monotonic() - start, 1)
    # A partial refresh must not claim all 51 sources were re-fetched today.
    out['last_incremental_at'] = receipt['finished']
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


def protected_measurements():
    ids = set()
    path = ROOT / 'evidence/public-evaluation-results.json'
    if path.exists():
        ids.update(x['skill_id'] for x in json.loads(path.read_text())['evaluations'])
    path = ROOT / 'evidence/public-native-evaluation.json'
    if path.exists():
        ids.update(x['skill']['id'] for x in json.loads(path.read_text())['studies'])
    return ids


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument('--catalog', type=Path, default=ROOT / 'evidence/hosted-catalog.json')
    a.add_argument('--plan-out', type=Path, required=True)
    a.add_argument('--fetch', action='store_true')
    a.add_argument('--repos', required=True, help='comma-separated stored keys; only these get metadata requests')
    a.add_argument('--max-repos', type=int, required=True)
    a.add_argument('--max-bytes', type=int, required=True, help='metadata plus raw body bytes')
    a.add_argument('--max-seconds', type=int, required=True, help='common deadline including metadata')
    a.add_argument('--disk-floor-gb', type=float, default=6.0, help='minimum free GiB')
    x = a.parse_args(argv)
    repos = x.repos.split(',')
    if (not all(repos) or len(set(repos)) != len(repos) or not 0 < len(repos) <= x.max_repos <= 9
            or not 0 < x.max_bytes <= 2_000_000 or not 0 < x.max_seconds <= 300 or x.disk_floor_gb < 6):
        raise SystemExit('bounds: 1..9 unique repos, 1..2000000 bytes, 1..300 seconds, disk floor >=6 GiB')
    if shutil.disk_usage(ROOT).free < x.disk_floor_gb * 1024 ** 3:
        raise SystemExit('disk below requested GiB floor; no network request')
    catalog = json.loads(x.catalog.read_text())
    sources = {s['repo']: s for s in catalog['sources']}
    if set(repos) - sources.keys():
        raise SystemExit('unknown stored repo keys')
    budget = Budget(x.max_bytes, x.max_seconds)
    rows = plan({'sources': [sources[r] for r in repos]}, api=budget.api)
    x.plan_out.write_text(json.dumps(dict(planned_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), sources=rows), indent=1))
    if not x.fetch:
        print(json.dumps({'selected': len(rows), 'metadata_bytes': budget.used, 'body_bytes_planned': sum(r.get('fetch_bytes', 0) for r in rows)}))
        return 0
    out, receipt = apply(catalog, rows, set(repos), x.max_bytes - budget.used, budget.remaining(), x.disk_floor_gb,
                         get=budget.get, protected_ids=protected_measurements())
    receipt.update(network_bytes=budget.used, max_bytes=x.max_bytes, max_seconds=x.max_seconds, max_repos=x.max_repos, threads=1)
    (ROOT / 'evidence/hosted-catalog.next.json').write_text(json.dumps(out, indent=2))
    (ROOT / 'evidence/incremental-refresh-receipt.json').write_text(json.dumps(receipt, indent=1))
    print(json.dumps(receipt))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
