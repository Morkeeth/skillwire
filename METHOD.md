# Skill evaluation method

SkillWire carries MAGNET's pinned-source and exact-body-open receipts, paired
with the skills-truth with-and-without design. The old betting system,
characters, local model paths and private behavioral records are excluded.
The three included results remain labelled with their individual task and hash.
No older MAGNET behavioral result is included: its manifests contain local paths
and setup-specific traces. The public tool does not need those records.

## Before running

Choose representative recurring tasks before reading the skill. For each task,
write a rubric and minimum useful score difference. Do not copy criteria from
the skill. Freeze the task, rubric, model, output budget and skill revision.
Choose at least three pairs; the tool also permits one pair for a smoke check.
A single task result is evidence only for that task, setup, model and revision.
Repeat across different tasks before making broader claims.

Dry-run is the default. It reads only the task and skill files you name, makes
no provider call, and reports the pair count, hashes and a conservative cost
reservation. The generation reservation is 2 × pairs × per-run ceiling. Blind
grading costs are separate and unknown until supplied. A reservation is not a bill.

```sh
python3 skill_eval.py --task examples/task.txt --skill examples/SKILL.md --rubric examples/rubric.txt --pairs 3 --max-run-usd 0.25 --cap-usd 2
```

## Private skill sources

A private local skill works with exactly the same paired design. Point --skill
at SKILL.md inside your own private checkout or skill folder. Dry-run reads that
file locally, hashes it, and makes no provider call. It does not fetch private
repositories or require repository credentials.

```sh
python3 skill_eval.py --task examples/task.txt --skill "$PRIVATE_SKILL_FILE" --rubric examples/rubric.txt
```

In the Eval tab, choose a local private SKILL.md with the file picker. That file
takes precedence over the catalog selection. Its body goes only to the loopback
server to construct the plan, is not saved, and is not sent to a model. Clear
the picker to return to Finder or Watch skills. The browser path allows 32 KB;
the CLI accepts larger local files. Treat task text as private too.

If you later opt into a live provider trial, treatment may transmit the private
skill body to that provider after an actual read_skill call. Use a provider and
retention policy you accept, or supply a trusted local runner. Private material
never belongs in the public examples, release tree or public result cards.

## Opt-in live text trial

Set OPENAI_API_KEY in your own environment. Never put it in runner.json or a
saved result. Pick a Chat Completions model that supports tools. Create a runner
file locally, using your current Python executable and absolute adapter path:

```sh
python3 -c 'import json,sys; from pathlib import Path; print(json.dumps([sys.executable,str(Path("openai_runner.py").resolve()),"--input-usd-million",sys.argv[1],"--output-usd-million",sys.argv[2]]))' "$INPUT_RATE_CEILING" "$OUTPUT_RATE_CEILING" > data/runner.json
python3 skill_eval.py --task examples/task.txt --skill examples/SKILL.md --rubric examples/rubric.txt --model "$MODEL" --runner data/runner.json --pass-env OPENAI_API_KEY --max-run-usd 0.25 --cap-usd 2 --output data/eval/my-first-trial --live
```

First run `mkdir -p data` if needed. Set INPUT_RATE_CEILING and OUTPUT_RATE_CEILING to
current USD prices per million tokens, or higher ceilings, and MODEL to the
intended model. Missing or invalid rates stop before a call. No model or price
is guessed. Check the provider's current pricing yourself.

The built-in adapter sends only the selected task and, if the model calls
read_skill, the selected skill body. It sends these to OpenAI, so remove private
text first. It does not read your home folders or session transcripts. The key
is sent only to the fixed HTTPS OpenAI endpoint; redirects are rejected.
It uses at most four requests per run, each with 800 maximum completion tokens.
Before each request it reserves input bytes plus 4096 framing tokens and the
full output limit at your supplied rates. It stops before the next request
would exceed the run ceiling. Failed requests are never retried automatically.
This is an estimated ceiling at user-supplied rates, not an account billing
limit or a guarantee about provider pricing. Use a provider-side budget too.
See the [official API schema](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
for tool calls, completion limits and usage fields.

## Pairing, invocation and scoring

Each pair has baseline and treatment in shuffled order. Each run gets a new
temporary directory and the same task, model and budget. Only treatment has the
skill file. No ambient agent instructions, transcript history or skill shelf
are loaded by the built-in adapter. Skill content is data; fetched scripts are
never executed. The tool's optional read_skill event captures the actual body,
its SHA-256 and successful read. A mention of the name is never enough. Reading
is not proof the model followed the instructions.

Custom runners are trusted user programs, not sandboxed software. They must
honor max_cost_usd before making any request, use the requested model and fresh
workspace, disable ambient skills in baseline, and return only JSON on stdout:

```json
{"output":"answer","cost_usd":0.0,"reads":[]}
```

For an observed treatment read, reads contains an object with path `SKILL.md`,
sha256, content (the full exact body), and success true. Do not manufacture these
from a model claim. Capture actual tool I/O. SkillWire can verify byte matches,
not the honesty of arbitrary runner software. Only named --pass-env variables
are forwarded in addition to PATH, LANG and SYSTEMROOT. Keys stay out of receipts.

The run writes plan.json, runs.json, blind.json and private-mapping.json in a
new directory and refuses to overwrite an old experiment. Partial failed runs
are saved and stop the trial. Never turn failures or missing costs into zero.
Give only blind.json to a different model or a human. Keep runs and mapping
private: they reveal condition labels. Ask the scorer to use the frozen rubric
and return one numeric score per blind ID, then save grades.json like this
(with the actual output IDs and scores):

```json
{"scorer":"human-reviewer","scale_max":10,"cost_usd":0,"scores":{"output-001":7,"output-002":8,"output-003":7,"output-004":9,"output-005":8,"output-006":9}}
```

```sh
python3 skill_eval.py --output data/eval/my-first-trial --score data/grades.json
```

This checks all IDs, score bounds and scorer identity, then reports arm means,
difference, body-open count and generation cost. The threshold is set before
running with --threshold (default 1 point). It reports helps, no difference or
hurts only if every treatment opened the body. Otherwise it reports routing
failure and preserves the scores. A self-identifying output can break blinding;
inspect blind.json before grading and record that limit. One grader call is
not human agreement or a stable estimate of taste. A large sample does not fix
biased task selection. Do not turn these one-task trials into a leaderboard.

## Source history

Watch pins a full GitHub commit, saves source bytes and SHA-256, and retains
revision history. The API reports repository ownership; it does not verify a
human maintainer's identity. Refresh compares SKILL.md bodies, including added
and removed files. Supporting scripts and non-SKILL.md changes are outside this
watch diff. Limits: 100 skill bodies per repository and 256 KB per body. An
incomplete or oversized fetch fails before changing the saved watch state.
