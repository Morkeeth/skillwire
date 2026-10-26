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

Open a source proposal first if no small maintained refresh path exists for the source. `scripts/pull_catalog.py` contains the explicit seed list and a `pull(repo)` function. Its `main()` rebuilds that seed catalog; it is **not** a harmless refresh of every current source. `scripts/enrich_catalog.py` also rebuilds a stars-based Popular selection. Running either against the current evidence can change coverage or ranking.

For discovery beyond the seed set, `scripts/expand_sources.py` records canonical repository redirects, pinned trees and partial-fetch errors. `scripts/pull_marketplace.py` joins a saved `skills.sh` snapshot to exact source matches. These are maintainer refresh tools that write shared evidence. Inspect them before use, work in an isolated checkout and keep before/after snapshots. Do not run them as part of an ordinary docs or UI fix.

A source PR should include the proposed repository/path and minimal reviewed metadata, the resulting count difference, and the expected effect on Popular. Keep downloaded bodies and archives in ignored `data/`; do not add caches to the PR. Preserve canonical repository aliases so a renamed source is not counted twice. Maintainers can perform the reviewed refresh and verify its full source/licence manifest.

## Count and rank honestly

Catalog IDs and `(repository, path)` entries are the catalog denominator. Byte-identical `SKILL.md` copies collapse within a repository; equivalent copies across repositories can remain. Neither catalog size nor a source's repository stars measures globally unique skills, installations or quality.

Read `popular_method` from the exact built catalog you are changing. The current source snapshot selects up to 50 entries using matched reported installs first, repository stars as fallback, a per-repository diversity cap and documented tie breaks. It is a selection within the fetched snapshot, not an internet-wide quality ranking. Do not combine stars and installs into an unlabeled number or turn missing installs into zero.

Build with `python3 scripts/build_site.py` after the reviewed evidence is ready. Verify that a real pinned inspection and download use the same revision/hash as the displayed record. A source added to a local checkout is not yet part of the public product.
