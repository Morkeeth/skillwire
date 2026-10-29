# SkillWire

## TLDR

Find public agent skills, inspect their pinned instructions and download a stack with source hashes.<br>
For people choosing skills for the coding-agent setup they already use.<br>
Popularity helps discovery; paired local trials let you compare a skill on your own task.

[skillwire.net](https://skillwire.net)

## The problem and approach

Skill files are scattered across repositories, star counts are not evidence they work, and anything downloaded from the internet is untrusted.  
Search the full pinned catalog by problem, category, harness and named model (Popular is a separate 50-entry browse view), build a stack of up to ten folders in your browser, and download it with per-file hashes, licence metadata and warning lines. No skill code runs during inspection or download.  
Trial runs a matched paired comparison on your own task through your own Codex or Claude subscription, judged blind; no general skill ranking is claimed. Try it at [skillwire.net](https://skillwire.net), no login.

## Review and pick up the work

[EVAL.md](EVAL.md) · [METHOD.md](METHOD.md) · [docs/eval-reproduction.md](docs/eval-reproduction.md) · [Agent guide](AGENTS.md)

Start with the linked source, setup and evidence. Recorded demos and sample data keep their original scope; use the repository instructions for a fresh run.

Find public agent skills by the problem they solve, category, harness and named model. A typed query searches the full pinned catalog; Popular is a separate 50-entry browse view you can choose explicitly. Inspect pinned instructions, build a stack in your browser and download the selected public folders with file hashes and source warnings.

## Run the product locally

```sh
python3 scripts/build_site.py
python3 scripts/serve_product.py --port 18828
```

Open http://127.0.0.1:18828. The product serves only the generated public `dist` files and catalog-ID-based public inspection/download endpoints. Stack choices stay in local browser storage. No server endpoint accepts private files or provider keys. Browser imports stay in the current tab. No skill code runs during inspection or download.

The Vercel deployment consists of the static directory plus a Python function in `api/index.py`. `vercel.json` declares the build and public API routes. The hosting source is an allowlisted export with a public file/hash manifest. Try the public product at [skillwire.net](https://skillwire.net). The custom domain serves the product without a login.

## What a stack contains

Download up to ten selected public skill folders. Each comes from the exact catalog revision, with a verified SKILL.md hash. The ZIP includes `SKILL-SOURCES.json`, per-file hashes, repository licence metadata, warning lines and install cautions. Skill-specific licences may differ from repository metadata; inspect the source terms. Original public files keep their bytes. The UI removes email addresses only from displayed text.

Folders are untrusted data. SkillWire never installs or executes them. Source failures, unsafe paths, symlinks, hash changes and oversized folders stop the download. Limits are documented by the returned error. An unmatched warning pattern is not proof that a skill is safe.

## Evidence

The source snapshot records exact revisions, hashes, fetch times, repository stars, licences and source links. Stars are not installs or evidence of efficacy. Categories and format compatibility are inferred and labelled. Model labels are model/family mentions with source quotes and line links; model tuning is not inferred from a harness or mention.

Selected public skills have narrow paired task outcomes from a frozen synthetic test set, run through a saved Codex ChatGPT subscription. The treatment supplied a public skill as inline reference; no separate read action was observable. Independent executable requirement checks grade outputs, not adherence to skill text. Both arms reached the available task-check ceiling, so these results do not establish a general skill benefit. A grading-harness capability correction is disclosed and original grades are retained. Unrun skills stay untested.

Public evidence is downloadable from `evaluations.json` in the built site. Every original run, error and output is retained locally for review; local credentials, private work and machine paths are excluded from the deployment source. There is no provider-key inference endpoint in the hosted product.

SkillWire source is MIT licensed. Public skill sources retain their own licences. See [CONTRIBUTING.md](CONTRIBUTING.md) for source and evaluation PRs. Contribute source, evaluation fixtures or improvements at [Morkeeth/skillwire](https://github.com/Morkeeth/skillwire).

## Evaluate through your own setup

Open Trial to choose one pinned skill, run a matched local comparison on your own task, judge its saved outputs blind, and then inspect the labelled evidence. Historical studies are shown after reveal. The earlier inline tasks and one native pilot reached their check ceilings; a later ten-pair TDD run has disputed grader contracts. There is no general skill ranking.

The downloadable local kit detects installed Codex/Claude CLIs and skill metadata. It freezes your own task, fixture, independent artifact grader and selected full local skill folder or reviewed public stack before an explicit paired trial through your existing subscription. Use `python3 lime_agent_eval.py doctor --project . > doctor.json` to import a pathless local inventory into Trial, or `python3 lime_agent_eval.py doctor --show-paths` for your own terminal, then read `EVAL-TOOLS.txt` in the ZIP or the Eval guide. Native Codex mode installs the selected folder only in treatment; the separate inline-reference mode disables tools and supplies the selected body in the prompt. No task/private skill is uploaded to SkillWire. Explicit trials send selected inputs to your chosen agent provider and consume subscription allowance. API-key/unknown auth is refused.

Validation status: a clean extraction of the current kit detected the installed Codex subscription and prepared/sealed both a full local skill folder and a pinned public stack with good/bad controls. These offline checks made no model calls. One prior native atomic-stock pair completed with equal 8/8 outcomes. The ten-pair TDD run recorded eight passing treatment arms and seven passing baseline arms, but a frozen reference disagreed with the task on ASCII DEL and other input boundaries need review. These counts are retained as disputed observations, not a benefit result. A new v2 family has all ten controls and seals ready but no model calls. A real own-task pair has completed locally with a browser-downloaded TDD skill, but its human blind verdict is pending; an unfamiliar user's own-task trial remains unverified.

Recheck saved public outcomes without model calls: `python3 scripts/recheck_public_outcomes.py`. For an offline preflight with the included bug, good/bad controls and grader, follow the [local trial example](docs/eval-reproduction.md#try-the-included-fixture-locally). Read EVAL.md for protocol and correction details.

After a completed pair, `lime_human_review.py prepare` makes a local blind A/B bundle from selected text artifacts. The browser review page hides arm names and automated grades, records A, B, tie or cannot judge with a reason, and downloads a local verdict. Trial opens labelled grades and commands only after that verdict, its blind bundle, and the withheld key are selected. The viewer compares their run links, sealed model and mode, installation and read claims, and supplied raw traces; missing trace evidence stays unverified. The gate and receipts are local consistency checks, not authentication of a person or model run. Ten bundles from completed native TDD pairs have been prepared for review, with their keys apart; no independent human verdict has been collected. Manual artifact pairs can exercise this review interface but do not prove model execution. A single preference is not a general skill effect. The earlier [Skill Issue SkillsBench report](https://github.com/Morkeeth/Skill-Issue-BenchFlow-Agent-Skill-Lift/blob/main/submission/RESULT.md) is historical context: its raw rollouts were deleted, and its reported numbers are not pooled with SkillWire outcomes.

Native installed-skill evaluation has a valid completed atomic-stock pilot: both arms passed 8/8, with a full pinned skill-body read observed in treatment. It is a one-case ceiling-limited tie, not general skill benefit. The older technical pilot remains invalid because of a task/reference mismatch (see EVAL.md): `--mode native_installed --workspaces /separate/disposable/root` requires a real restricted-read boundary probe, equal local tools and a verified existing Codex subscription. Select an entire local folder with `prepare --skill-folder`, or a reviewed pinned public stack ZIP. Current fixtures cover TDD behavior/regression tests and explicitly offline discovery/install tasks; live registry performance, interactive grill-me, real media preparation and browser persistence are not completed studies. See EVAL.md for exact limitations. The original 36-output ceiling-limited null remains unchanged.

## License and data boundaries

Code terms: [LICENSE](LICENSE). Data, provider responses, media, fonts and other third-party assets may have separate terms. Repository access alone does not grant rights to those materials. 
