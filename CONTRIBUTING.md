# Contributing to SkillWire

PRs for source coverage, client behavior, documentation and reproducible evaluation are welcome. Describe one concrete problem and the resulting behavior. Keep product changes small enough to review and show the real flow when the change affects the interface.

SkillWire's own code and documentation use the [MIT licence](LICENSE). Contribute only material you have permission to share under the repository's licence. Downloaded public skills keep their source licences and notices; their inclusion in the catalog does not relicense them or establish permission to redistribute every supporting file. Unknown licence information stays unknown.

## Pick a contribution

- [Add or correct a public source](docs/source-contributions.md): pin repository, revision, path, hash and source terms. A catalog entry is not a globally unique skill.
- [Reproduce an evaluation](docs/eval-reproduction.md): start with saved public outcomes, or prepare a new local paired trial with separate controls and a new run ID.
- [Improve evidence and usage labels](docs/usage-evidence.md): keep popularity, download, installation, observed reading and task outcomes separate.
- Fix a client bug: include the steps, browser or CLI version, expected behavior and observed behavior. Screenshots or short recordings should use public or synthetic content.

Use a branch or isolated worktree. Do not edit generated `dist/` as the source of a fix. Product UI sources are in `site/`; public inspection and ZIP assembly are in `public_runtime.py`. The older local workbench in `web/` is a separate surface, so name the surface your change affects.

## Check the change

From the repository root:

```sh
python3 -m unittest discover -s tests
python3 scripts/build_site.py
git diff --check
```

The build uses saved public evidence and does not refresh sources or run a model. Some tests inspect public pinned sources and may need network access. State a failed or unavailable check as such, with its output; do not turn an unrun check into a pass. For a client change, also exercise the affected flow at desktop and phone widths, including its error and retry path. A browser download request does not prove that a file was saved to disk.

For an evidence-only change, include the exact source version and the check that can reject a wrong result. For a docs-only change, verify links, file paths and command help; a new model run is unnecessary.

## Keep a PR reviewable

Explain what failed, what the user can now do, and how you checked it. Include source revision/hash changes, known limits and any change in count or ranking denominator. Keep missing values distinct from zero. Preserve old experiment outputs, errors and corrections instead of replacing them with a cleaner result.

Do not commit credentials, `.env` files, local provider login state, private skills, personal prompts, local paths, downloaded repository archives or the `data/` cache. Use small public or synthetic fixtures. Do not attach a real task bundle or private review record to a public issue. If a problem involves private data or a credential, use a private contact method provided by the maintainer; do not put the sensitive content in a public issue or PR.

Deployment and public result promotion are maintainer actions. Opening a PR does not publish a catalog refresh, enable telemetry or approve an efficacy claim.
