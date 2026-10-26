# Catalog scope and provenance

Current source: evidence/hosted-catalog.json. It contains every SKILL.md discovered in the saved source scope, after exact-body deduplication and repository-alias cleanup. Source counts describe source files or catalog entries as labeled, not quality-approved products.

Scope: the official Anthropic, OpenAI and Vercel sources, large seed community repositories, every repository in the saved star-ranked GitHub repository-discovery.json result, earlier failed seed sources, and every GitHub repository represented in the live publicly listed marketplace snapshot. discovery-coverage-night.json records completion and zero fetch errors for that scope. Repositories with no SKILL.md are retained as lists, not counted as skill-bearing repos. This is a complete pull of the declared scope, not an exhaustive census of the internet or every marketplace link.

GitHub metadata is read with gh internally. No token is extracted or printed. Trees resolve to exact commits. All downloaded bodies are data, never executed. Raw source material remains under ignored data/hosted-sources. Pinned file metadata enables small folder downloads from large repositories without fetching giant archives.

Categories use whole-word name/description rules. They remain inferred and labeled. Problem summaries come from source descriptions, shortened at word boundaries, and are not independent validation. Model/family mentions come from exact skill lines with quotes and links; absent models stay not stated. A harness is never used to infer a model, and a mention is not a tuning claim.

Popularity uses observed marketplace installs for exactly matched skill entries and fetched repository stars otherwise. Unmatched installs stay unknown. Popular is a 50-entry cut, at most three distinct skill names per canonical repository, with documented task-skill tie breaks. Draft, archive and localization paths are excluded from that view. Full catalog remains searchable. Duplicate translations and differing bodies can remain there. Repository licences do not settle skill-specific terms.

Published strings remove email addresses. Inspect displays sanitized text and explicitly says the original download bytes retain public source content. Exact hashes refer to original public bytes. Private skills, user files, auth state, local paths and historical operator material are not hosting inputs.

Reproduction sequence in the development checkout: pull_catalog.py (seed sources), expand_sources.py (saved star discovery), snapshot_marketplace.py and pull_marketplace.py (all publicly listed ranked entries), curate_catalog.py, attach_file_lists.py, build_site.py. public evaluation outcomes join by both catalog ID and exact skill hash through published_catalog.py. An unchanged name never transfers a result to new bytes.

The observed marketplace page lists 185 ranked entries, with gaps in the provider rank sequence. The snapshot retains those gaps and does not claim contiguous ranks 1 through 100. All represented GitHub repositories were read. Forty-two marketplace entries have no exact matching SKILL.md or use external website distribution; Sources names them. No fake skill folder or install match is invented.

Desktop design follows the live 8811 reference: original shell/CSS, 12px Tahoma, 258px side panel and 24px result rows at measured desktop widths. The hero/card replacement is removed. Visual approval remains a separate check.
