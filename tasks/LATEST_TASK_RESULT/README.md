# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Sandbox V2–Codex Comparison Preregistration

### Scope and Outcome

The four-run configuration/specification is registered, but paid execution
remains blocked. This work starts from immutable main
`96b181e1128039891f2cbbd9c26af9701e7e8e22` on branch
`b/gpt54-sandboxv2-codex-comparison-20260919`, in the new worktree
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-sandboxv2-codex-comparison-20260919`.
The preservation checkout and prior worktrees were not changed.

Exactly six files differ from that base:

- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

Both conditions share the same target Foundry account and GPT-5.4 deployment,
`xhigh` effort, fixed `advance_check_5` task order, canonical prompt and input
fingerprints, technical limits, grader revision, and result/receipt contracts.
The plan reuses the existing task-selection and V2 ceiling helpers. Its four
5-task runs are V2 repeat 1, Codex repeat 1, Codex repeat 2, then V2 repeat 2:
20 task-condition observations, with fresh sessions and result namespaces.
No 30-task or 220-task escalation is registered.

This is a **configuration-bundle comparison**, not an environment-only
causal study. First-request instructions and tools, conversation/replay,
reference presentation, sandbox/package/network policies, usage granularity,
and time-varying host/provider/grader behavior remain different. The
specification separates these residuals from the launch blockers below.
Two repeats measure observed spread; they do not establish a general winner
or validate the grader. Costs remain record-only, with unknown/unpriced
usage preserved as null/partial evidence rather than zero.

### Verification

The only local selector ran once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_comparison_preflight.py::test_gpt54_comparison_is_fixed_and_fails_closed
```

Result: **`23 passed in 6.55s`**.

The unchanged plan validates. Mutations of model identity, effort (including
a shared downgrade), task order/content, input fingerprints, limits, grading,
schema, repeats, cohort size, cost policy, source pins, launch permission, or
the causal label are rejected. Every case retains `launch_allowed: false`.
The selector exercises the CLI entry point in process and asserts exit code
2; no separate preflight command ran. The valid case also inspects the V2
dataclass and generated Codex overrides without constructing a model client
or executing the provider authentication command.

The preflight checks 11 pinned source files and computes the plan's canonical
JSON fingerprint. It does not download inputs, inspect a live deployment,
or sit in front of the existing paid workflows. Passing this selector is
not evidence that those workflows can execute the registered comparison.

```bash
git diff --cached --check 96b181e1128039891f2cbbd9c26af9701e7e8e22
```

The diff check passed. The plan, checker, and selector were unchanged after
the targeted run. No broad suite, standalone preflight, model/grader call,
VM/guest execution, Azure API/CLI operation, workflow dispatch, Project edit,
or paid experiment ran. Historical ledgers and sealed evidence are untouched.

### Launch Blockers and Review Boundary

The owner approved the eventual paid comparison. That approval does not make
the current adapters capable of enforcing the registered controls:

- V2's model request does not carry an explicit reasoning effort.
- Codex's provider overrides and thread creation do not carry that effort.
- Codex's logical turn does not enforce V2-equivalent native model-call and
  token limits.
- Exact live deployment/model-version identity, support for the requested
  effort, and downloaded input bytes have not been verified.
- Existing workflow dispatch and a run-specific, revision-pinned grader
  config are not connected to this contract.

The offline checker refuses launch even for the valid plan. It is not a new
runtime gate on all spending paths. No lower-effort or alternate-model
substitution was made.

**There is no compliant post-merge paid launch command on this base.** The
reuse targets are `.github/workflows/agentic-v2-stage-run.yml` and
`.github/workflows/batch-run.yml`, after separately reviewed adapter/limit
wiring, pre-spend identity/input checks, and dispatch integration. Those
changes require a new immutable source boundary and refreshed source pins;
the current templates must not be dispatched as substitutes.

This change has not received immutable-HEAD review. No approval, CI success,
or merge result is claimed. The next gate is leader review of the committed
configuration/specification and automatic CI evidence. The approved paid
comparison has not run.

### Skills

The available skill and repository agent catalogs were inspected once.
`experiment-design` was applied before configuration work to fix the question,
controls, minimum repeats, residual differences, measurement units, grader
limits, stop rules, and the boundary on generalization. `openai-docs` was used
to check the official GPT-5.4 and Codex effort documentation; that check does
not establish Foundry deployment support. `im-not-ai-en` was applied to English
completion and PR wording, preserving identifiers and evidence limits. No
extra skill verification script ran under the one-selector limit.

Experiment-report skills do not apply: no paid experimental results are
reported. Repository-readiness, UI, and animation skills do not apply.
No grading pipeline, workflow, `core/qa.py`, or HF upload script changed, so
no grading-engineer delegation or extreme-reasoner decision was needed.

## Prior Result: #613 HF Cost Ledger Source Binding

[#613](https://github.com/hyeonsangjeon/gdpval-realworks/pull/613) bound the
optional top-level `cost_ledger` to the canonical inference source before
staged-file validation and HF API calls. Its implementation HEAD was
`bfd9b196a7c47dd4658a0d8520ddc165669ba551`. The recorded selector
`test_publication_binds_optional_cost_ledger_to_source` reported
`8 passed in 0.51s`, with `api.calls == []` in all five rejected cases.
That historical selector was not rerun here.
