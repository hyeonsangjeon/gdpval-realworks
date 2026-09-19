# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Offline Dispatch-Plan Compiler

### Scope and Outcome

`compile_dispatch_plan` now converts the existing GPT-5.4 comparison manifest
into four frozen `ComparisonRunSpec` objects. It validates the manifest controls
and source pins before producing canonical JSON configs and argument tuples for
the existing V2 stage and Codex preparation/inference entrypoints. It does not
write those files, create checkouts, authenticate, or dispatch anything.

Work started from immutable main
`2a1ecaf7d6a6f18ba21add7884414d041bc1b5d8` in branch
`b/gpt54-offline-dispatch-plan-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-offline-dispatch-plan-20260919`.
The preservation checkout and prior worktrees were not changed.

Exactly seven files differ from that base:

- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The fixed matrix remains:

| Order | Condition | Repeat | Run ID |
| --- | --- | --- | --- |
| 1 | Sandbox V2 | 1 | `gpt54_v2_codex_v1_v2_r1` |
| 2 | Codex | 1 | `gpt54_v2_codex_v1_codex_r1` |
| 3 | Codex | 2 | `gpt54_v2_codex_v1_codex_r2` |
| 4 | Sandbox V2 | 2 | `gpt54_v2_codex_v1_v2_r2` |

Each row retains the same ordered `advance_check_5` tasks, Foundry GPT-5.4
identity, and explicit `xhigh` request. The plan retains all shared input and
reference fingerprints, limits, grading provenance, result/receipt contracts,
and record-only cost policy. This remains a configuration-bundle comparison,
not a claim about environment-only causality or a new experiment design.

### Compilation and Compatibility Boundaries

The V2 recipe supplies the existing stage entrypoint with an explicit five-task
stage, config, parquet and reference-root paths, run ID, and output directory.
The Codex recipe supplies `step1_prepare_tasks.py --config` followed by
`step2_run_inference.py --condition condition_a --max-retries 0
--resume-max-rounds 0 --no-resume`. The existing experiment parser validates
the generated Codex config without resolving a live endpoint.

Every row requires a separate reviewed-source checkout under
`comparison-runs/<run_id>`. This matters because batch workspace paths follow
the source location, not the process working directory. Each checkout uses
`data/gdpval-local` for the fixed snapshot and
`batch-runner/comparison-run.json` for its generated config. Creating those
copies and verifying their live input bytes remain outside this compiler.

The preflight emits the compiled plan and its seal. Its optional
`--dispatch-plan` input must match the plan derived from the manifest exactly.
Changed config content, arguments, order, repeats, paths, pins, controls, or
launch flags are rejected. Manifest key order does not change output bytes.
The compiler reads no credentials and invokes no subprocess or runtime.

The required source set grows from 17 to 21 by adding the compiler/parser,
the source-relative path constants, the seal helper, and the task selector.
The Sol YAML changes only its existing shared-parser digest; its identity,
16-file source set, and launch gates remain unchanged.

All Foundry provider/runtime code, execution entrypoints, original templates,
pricing arithmetic, schemas, and historical ledgers remain byte-identical to
the base. The generated run copies carry the comparison overrides; production
defaults are not rewritten. V2 template safety/cost machinery is retained,
and its historical budget records are not treated as a new comparison approval.

### Verification

The following targeted command ran once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_comparison_preflight.py::test_gpt54_offline_dispatch_plan_is_bound_and_non_executing
```

Result: `25 passed in 9.44s`.

The selector checks the real template readers and experiment parser, all 21
required pins and their digests, changed source bytes, exact entrypoint
arguments against their parser declarations, canonical output stability,
shared controls, and refusal of mutated manifests or compiled plans. Network,
subprocess, Azure-route resolution, and provider-auth calls are forbidden by
the fixture. The preflight CLI is exercised in process and still returns 2.
The dependent Sol parser digest is checked without running the Sol selector.

The staged diff against the immutable base passed:

```bash
git diff --cached --check 2a1ecaf7d6a6f18ba21add7884414d041bc1b5d8
```

No other pytest selector, broad suite, build, standalone preflight, actual
five-task run, 220-task run, model/grader/VM call, Azure/HF operation, live
credential lookup, workflow dispatch, or Project edit was performed.

### Immutable Review Boundary

The implementation and its specification are committed at
`f58da12cf3a835b0a37674b5e8ccd53a4715c9fe`. The read-only `first-reviewer`
audit compared that exact HEAD with the immutable base and returned `APPROVE`,
with no BLOCK, MAJOR, or MINOR findings and no escalation requested. It did
not rerun tests or invoke a runtime. No review correction or selector rerun
was needed.

Only this completion record and `CHANGELOG.md` were added after that review;
the implementation, plans, tests, and specification are unchanged. This review
covers the offline artifact, not the deferred execution gates. Leader review
and automatic CI evidence remain pending; this record claims neither CI
success nor a carrying-PR merge result.

### Remaining Work

Only offline dispatch artifact generation and source binding are implemented.
The combined dispatch/grading blocker becomes
`comparison_pinned_grading_not_wired`. The other five blockers remain:

- `v2_reasoning_effort_capability_unverified`
- `codex_reasoning_effort_capability_unverified`
- `codex_native_model_call_and_token_limits_unenforced`
- `live_deployment_identity_and_input_bytes_not_verified`
- `comparison_usage_and_tariff_evidence_unverified`

Actual checkout/config/input materialization, workflow execution gates, pinned
grading, and the evidence above still need separate reviewed work. Both
`launch_allowed` and `full_220_allowed` remain false. The compiler is not a
guard over every paid entrypoint in the repository, and no compliant paid
comparison command is supplied here. Unknown or unpriced usage stays
null/partial under the existing record-only policy.

The separate GPT-5.6 Sol Copilot provider/auth route remains blocked because
no official runtime-to-Codex authentication handoff contract was established.
This task does not add a guessed endpoint, token bridge, Copilot SDK
substitution, or personal OpenAI/Foundry fallback for that pilot.

### Skills and Review Role

The full available skill catalog was inspected once before implementation.
`experiment-design` was applied before code and plan changes. It preserved the
fixed comparison question, configuration-bundle scope, two repeats per condition,
input selection, measurement units, and stop boundaries, while keeping declared
controls separate from evidence of enforcement. `im-not-ai-en` was applied to
the English changelog, completion record, and PR wording. Protected commands,
SHAs, counts, and uncertainty were checked manually; the owner's narrow
validation scope took precedence over an additional fidelity-script run.

The explicitly requested `first-reviewer` role is used for the immutable-HEAD
review, not an external model invocation. Experiment-report skills do not apply
because no experimental outcomes are reported. Repository-readiness, UI, and
animation skills do not apply to this existing offline compiler. No grading
pipeline, workflow file, `core/qa.py`, or HF upload code changed, so no
grading-engineer or extreme-reasoner step was needed. No new API/provider
contract was introduced; existing pinned helpers are reused without a new
documentation or authentication investigation.

## Prior Result: #617 V2 Reasoning-Effort Forwarding

[#617](https://github.com/hyeonsangjeon/gdpval-realworks/pull/617) carried an
explicit V2 `xhigh` value through stage validation and voice construction into
the Responses request, preserving absent/null default bytes. Its implementation
HEAD was `5bb3bd1d4e09499c94d3a06c163f0fd919bcd61b`, with the historical result
`55 passed in 14.05s`. Those request selectors were not rerun in this task.
