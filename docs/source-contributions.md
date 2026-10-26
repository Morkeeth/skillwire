# Public source contributions

Start with the exact public repository and `SKILL.md` path. Explain which task the instructions address and why the source belongs in the catalog. An index link, repository star count or model mention alone does not prove that a skill works on that task.

## Evidence to include

| Field | Required evidence |
| --- | --- |
| Source identity | Canonical repository name, resolved 40-character revision and ordinary relative `SKILL.md` path |
| Content | SHA-256 of the original file bytes and a pinned source link |
| Retrieval | Fetch time, method, failed files and whether the upstream tree was truncated |
| Terms | Repository licence metadata plus pinned licence text when available; disclose skill-specific terms or missing permission |
| Supporting files | Folder/resource scope, per-file hashes, warning lines and download limits |
| Description | Source description or an attributed excerpt; mark inferred categories as inferred |
| Model/harness | Exact quoted source lines for mentions; compatibility and tuning remain unverified unless separately tested |
| Popularity | Repository stars and reported installs as separate fields, with provider and fetch time; missing installs are unknown |

Use original public bytes for hashes and downloads. A static warning scan records pattern matches; it does not certify a folder as safe. Do not execute fetched scripts to see what they do. Source failures, symlinks, traversal, hash changes and oversize folders must remain visible failures.

## Stage the source without replacing the catalog

The public checkout does not include `scripts/pull_catalog.py`, `scripts/expand_sources.py` or `scripts/pull_marketplace.py`. Those are maintainer-side source refresh tools, not commands a public contributor can run from this repository. The included build consumes the saved public snapshot; it does not fetch a new catalog.

Open a [source proposal](https://github.com/Morkeeth/skillwire/issues/new) or a small PR containing the proposed canonical repository and `SKILL.md` path, pinned revision/hash when available, source description, licence evidence and the reason to include or correct it. Disclose missing terms, partial retrieval or an unverified model claim. Do not invent a hash or count to complete a proposal.

Keep the proposal limited to reviewed public metadata and source links. Do not add downloaded archives, skill-body caches, private sources or local paths. If a source was renamed, include the old and canonical names so the maintainer can preserve its alias instead of counting it twice.

Maintainers perform the source refresh, preserve before/after snapshots, check the full source/licence manifest and review the resulting coverage and Popular selection. The included `scripts/enrich_catalog.py` is a metadata transformation that can rebuild a stars-based selection; it is not a source-fetch command or a harmless refresh of the current install-ranked snapshot. Do not rewrite the saved catalog or ranking as part of an unrelated docs or UI fix.

## Count and rank honestly

Catalog IDs and `(repository, path)` entries are the catalog denominator. Byte-identical `SKILL.md` copies collapse within a repository; equivalent copies across repositories can remain. Neither catalog size nor a source's repository stars measures globally unique skills, installations or quality.

Read `popular_method` from the exact built catalog you are changing. The current source snapshot selects up to 50 entries using matched reported installs first, repository stars as fallback, a per-repository diversity cap and documented tie breaks. It is a selection within the fetched snapshot, not an internet-wide quality ranking. Do not combine stars and installs into an unlabeled number or turn missing installs into zero.

Build with `python3 scripts/build_site.py` after the reviewed evidence is ready. Verify that a real pinned inspection and download use the same revision/hash as the displayed record. A source added to a local checkout is not yet part of the public product.
