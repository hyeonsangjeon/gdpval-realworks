# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GitHub Copilot GPT-5.6 Sol Codex Pilot Preregistration

### Scope and Outcome

The five-task pilot is preregistered, but its exact route and runtime controls
cannot yet be expressed and verified. Execution remains blocked. This work
starts from immutable main `6ccd4ae346d302e3da0af455a3c5a72ec79a6984` on branch
`b/gpt56-sol-codex-pilot-20260919`, in the new worktree
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt56-sol-codex-pilot-20260919`.
The preservation checkout and prior worktrees were not changed.

Exactly six files differ from that base:

- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The target is GitHub Copilot GPT-5.6 Sol, Codex SDK/CLI `0.147.0`, reasoning
Max, and Long context 1M. Fast, Astra, Foundry GPT-5.4, personal OpenAI routes,
and automatic model/effort/context fallbacks are excluded. The nominal 1M
tier is not a verified context-window measurement or client-side override.

One pilot uses the existing score-free `advance_check_5` task order, canonical
prompt hashes, dataset revision, and input/reference fingerprints. The plan
reuses the experiment parser, task selector, runtime constants, receipt schema,
plan reader, and seal helper. It inherits exp035's 1,800-second attempt
timeout, up to three infrastructure retries, one logical turn per attempt,
zero provider retries, and disabled Self-QA/resume. A logical turn is not one
native model request. Unenforced native call/token caps remain null and are
launch blockers, not unlimited-spend permission.

The pilot disables relays and automatic progression to 220 tasks. Grader
policy and rubric/prompt pins come from the existing exp035 Sol/Max grading
config, but its historical 220-task rerun identity must not be reused.
The result projector, grade schema `1.4`, and `cost-receipt-v1` remain intact.
Record-only costs preserve unknown/null/partial evidence. No Foundry or
OpenAI tariff is substituted for Copilot billing.

A pass supports leader review of the pilot evidence before a separate
full-run gate; failure stops progression. It is not a superiority test. The
specification lists model, route/auth, effort, context, cohort/order, relay,
billing/error, source/host/time differences against the historical exp035
full-220 reference. One pilot measures no within-condition spread, and a
Sol judge shares the solver's model family. No causal ranking is claimed.

### Verification

The only local selector ran once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py::test_gpt56_sol_copilot_pilot_is_pinned_and_fails_closed
```

Result: **`38 passed in 10.16s`**.

The unchanged registration validates. Model/provider/harness substitutions,
effort/context changes, fallback flags, task/input/instruction drift, limit
changes, repeat/relay/220-task expansion, grading/result/receipt changes,
tariff substitution, missing source pins, and launch enabling are rejected.
Every case retains `launch_allowed: false` and `full_220_allowed: false`.
The selector exercises the CLI entry point in process and checks exit code 2;
no separate preflight command ran.

The valid case also checks the real experiment/provider classes: the existing
Foundry config validates, a Copilot provider is rejected, a synthetic
non-Microsoft endpoint is refused, and the provider dataclass has no effort
or context fields. No SDK, authentication command, or model client is started.
The preflight checks 13 source-file pins and computes a canonical plan hash.
It does not verify live Copilot capability or downloaded input bytes and is
not wired into the existing paid workflows.

```bash
git diff --cached --check 6ccd4ae346d302e3da0af455a3c5a72ec79a6984
```

The diff check passed. The plan, checker, and selector were unchanged after
the targeted run. No broad suite, standalone preflight, model/grader call,
VM/guest execution, Azure API/CLI operation, workflow dispatch, Project edit,
or paid experiment ran. Historical ledgers and sealed evidence are untouched.

### Launch Blockers and Review Boundary

The owner approved the eventual pilot/full benchmark. Current blockers are
the absent GitHub Copilot route, missing Max/Long wiring and capability proof,
unresolved native call/token caps, unverified live identity/input bytes,
unwired pilot dispatch/grading identity, and unverified Copilot usage/tariff
mapping. The valid registration refuses launch; it is not a new runtime gate
on every spending path.

**There is no compliant post-merge paid pilot command on this base.** Reuse
`.github/workflows/batch-run.yml` only after separately reviewed provider,
control, usage, identity, and five-task dispatch wiring. Refresh the immutable
source boundary and pins for that implementation. Existing Foundry workflows
or a personal Codex session are not substitutes. Then run the pilot, retain
all evidence, and stop for the separate full-run gate.

This change has not received immutable-HEAD review. No approval, CI success,
or merge result is claimed. The next gate is leader review of the committed
configuration/specification and automatic CI evidence. The approved paid
pilot and full benchmark have not run in this task.

### Skills

The available skill and repository agent catalogs were inspected once.
`experiment-design` was applied before configuration work to fix the question,
controls, pass/fail decision, lack of repeat evidence, residual differences,
measurement units, grader limits, stop rules, and generalization boundary.
`openai-docs` was used for official Sol/Codex capability references, not as
proof of Copilot access or transport. `im-not-ai-en` was applied to English
specification, completion, and PR wording. Protected literals and evidence
limits were checked manually; no extra skill verification script ran under
the one-selector limit.

Experiment-report skills do not apply: no paid experimental results are
reported. Repository-readiness, UI, and animation skills do not apply.
No grading pipeline, workflow, `core/qa.py`, or HF upload script changed, so
no grading-engineer delegation or extreme-reasoner decision was needed.

## Prior Result: #614 GPT-5.4 Sandbox V2–Codex Preregistration

[#614](https://github.com/hyeonsangjeon/gdpval-realworks/pull/614) registered
the four-run configuration-bundle comparison while refusing launch on its
pinned adapters. Its implementation HEAD was
`b27c2fa0ed0d002909e842384dbd5c034537c1f0`. The recorded selector
`test_gpt54_comparison_is_fixed_and_fails_closed` reported
`23 passed in 6.55s`. That historical selector was not rerun here.
