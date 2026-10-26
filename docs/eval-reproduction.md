# Reproducing evaluation evidence

Keep four facts separate: instructions were available, a skill was installed, its body was observed in a successful tool read, and a task outcome met its checks. None establishes internal model use. Preserve a missing read trace as unobserved rather than a failed read.

## Replay the saved public artifacts first

```sh
python3 scripts/recheck_public_outcomes.py
```

This regrades saved public code with the corresponding saved checks and makes no model calls. It verifies the recorded task outcomes, not the identity of a model run, skill reading, useful work or general skill efficacy. It executes the saved public code locally; inspect the inputs and graders before running them. Ordinary Python isolation flags are not a hostile-code sandbox.

Public evidence records live in `evidence/public-evaluation-results.json`, `evidence/public-harder-results.json` and, when present, `evidence/public-native-evaluation.json`. Read [EVAL.md](../EVAL.md) for the exact protocols, retained errors, grader corrections and scope. The original inline study, harder follow-up, native pilot and disputed TDD family are different cohorts; do not pool them. A both-pass ceiling or one preferred output cannot establish a general win.

## Prepare a new local comparison

Use a new directory and run ID. Never replace an old run or selectively rerun only failed arms. The current local tools keep their historical `lime_*.py` filenames even though the product is SkillWire. Read their actual options:

```sh
python3 lime_agent_eval.py doctor --help
python3 lime_task_eval.py prepare --help
python3 lime_task_eval.py seal --help
python3 lime_agent_eval.py run --help
python3 lime_human_review.py prepare --help
python3 lime_human_review.py reveal --help
```

Freeze the task, equal initial files, exact full skill folder or reviewed public stack, source revision/hash, model/settings, tools, arm order and budget before inference. Use an independent artifact grader with a known-good control and deliberately wrong controls. The controls must actually pass/reject before a result is trusted. Do not derive outcome requirements from the skill being evaluated.

Use disposable workspaces and the runner's required boundary probe. Preserve both arm records, commands, tool outputs, artifacts, usage, errors and grading results. Separate model/task failures from failures that occurred before the model or grader ran. An explicit trial consumes the chosen subscription allowance; a setup check or local doctor is not a completed trial.

## Try the included fixture locally

This is an offline setup check for the provided `eval-example` bug. It is not a study of your task or evidence that a selected skill helps. First inspect `eval-example/grader.py`, then download and review **one** public skill ZIP in SkillWire. Use the actual path where your browser saved that ZIP:

```sh
STACK_ZIP=/absolute/path/to/skillwire-skill-stack.zip
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
RUN_DIR="runs/example-$RUN_ID"
python3 lime_task_eval.py prepare \
  --fixture eval-example/bug --reference eval-example/good \
  --negative eval-example/bad --task eval-example/TASK.md \
  --grader eval-example/grader.py --stack "$STACK_ZIP" \
  --out "$RUN_DIR" --trust-grader
```

`prepare` makes **zero model calls**. Stop unless it reports `ready: true`: the included good solution must pass and the bad one must fail. Inspect `"$RUN_DIR/plan.json"` and `"$RUN_DIR/SKILL-SOURCES.json"` before sealing. The selected ZIP's skill may have no relevance to this example; the check only exercises the controls and frozen file handling.

To continue with your **own supported Codex subscription**, replace `your-supported-Codex-model` with an actual model identifier available in your CLI. The setup command seals one model, settings, random arm order and the two-trial budget without inference:

```sh
MODEL_NAME=your-supported-Codex-model
python3 lime_eval_setup.py --run "$RUN_DIR" --agent codex \
  --mode native_installed --model "$MODEL_NAME" --reasoning low
```

Stop here if you only wanted the offline check. The next command is the **explicit subscription boundary**: it sends the selected task and skill to your Codex provider, uses your plan allowance, and writes raw arm records. It requires separate disposable workspaces. Do not run it on private material you would not send to that provider.

```sh
python3 lime_agent_eval.py run --run "$RUN_DIR" --agent codex \
  --mode native_installed --workspaces "../skillwire-workspaces-$RUN_ID" \
  --use-subscription
```

After a completed pair, prepare the blind A/B review using the saved `app.py` output. Keep the reveal key and grades away from the reviewer until they save a choice. A local example result is not a public quality rating or a general skill effect. For a real decision, replace the included task, starting files, good/bad controls and independent grader with your own relevant task **before** sealing; use a new run folder.

## Review before revealing the conditions

Prepare a blind A/B bundle only from the intended completed pair. Keep its reveal key and automated grades apart from the reviewer. Record A, B, tie or cannot judge with a reason, save the verdict, then reveal. Verify the bundle, verdict, source and run bindings. These local checks establish consistency, not a person's identity or authenticity of an arbitrary imported report.

Keep private tasks, prompts, generated code, private skill bodies and review reasons local. Do not upload them in a PR, an issue, telemetry or a public result export. A public evidence PR needs an explicitly reviewed public/synthetic subset, original and corrected grades where relevant, per-file hashes, all planned cases including failures/missing outcomes, and the exact denominator. Publishing that subset is a separate maintainer action.

Any proposed quality score must name the exact tested skill hash, task family, model/settings, valid pair count, outcome rule and uncertainty. Community ratings need their own real rating count and scope. Repository stars, downloads and test presence are not substitutes for either measure. An untested or unrated entry remains untested or unrated.
