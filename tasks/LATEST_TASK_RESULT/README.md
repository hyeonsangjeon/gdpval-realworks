# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Offline Pinned-Grading Plan

### Scope and Outcome

`compile_grading_plan` reuses `compile_dispatch_plan` to produce four frozen
grading specifications bound to the existing `step8_grade.py` entrypoint. Each
specification carries its inference run identity, ordered tasks, input paths,
grader config and rubric provenance, actual CLI arguments, and isolated
grade/receipt output templates. The preflight now emits and exact-checks a
combined canonical dispatch/grading document. It does not create clients,
materialize files or checkouts, or start execution.

Work started from immutable main
`5c3a69278a8f005db8ea0aed72d13d20909c57df` in branch
`b/gpt54-pinned-grading-plan-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-pinned-grading-plan-20260919`.
The preservation checkout and prior worktrees were not changed.

Exactly eight files differ from that base:

- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/step8_grade.py`
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
identity, explicit `xhigh` request, input/reference fingerprints, and inference
limits. All four grading specs use the same grader contract and config bytes.
Their grading ordinal is 1 because these are four distinct inference runs,
not repeat grading of one run. Comparison repeats remain 1, 1, 2, 2. The study
remains a configuration-bundle comparison, with no environment-only causal
claim and no new experimental condition.

### Compilation and Compatibility Boundaries

Each spec uses the dispatch run's separate reviewed-source checkout under
`comparison-runs/<run_id>`, with `batch-runner` as the working directory. Its
command is data only:

```text
python3 step8_grade.py execution_envelope/<run_id>
  --config comparison-grading.json --source local
  --tasks <the same five comma-separated task IDs> --limit 5
  --shard-count 1 --shard-index 0 --run-ordinal 1
  --source-experiment-id <run_id>
```

The compiler reuses `default_v2_sol_max.yaml`, `yaml.safe_load`, and
`validate_grading_config`. It changes only the generated copy's rubric revision
to `11e7900cdcac61bc4daf59e65feb238acda98fbf` and rubric cache directory to
`../data/gdpval-local`. Judge Sol/Max, prompt v2.2, tool/perception/retry settings,
and output defaults are unchanged. The generated JSON must be materialized
verbatim, without an added newline; its hash matches step8's `hash_config`.

The real input is `batch-runner/workspace/step2_inference_results.json`, with
deliverables under `batch-runner/workspace/upload/deliverable_files`. Codex
already produces the input file. V2 instead produces
`batch-runner/workspace/run_record.json` at `/run/results`; projecting those
rows and staging its deliverables remain explicit materialization gates.
Experiment metadata is specified at
`batch-runner/experiments/execution_envelope/<run_id>.yaml` for step8's existing
loader. No invented input option or alternate V2 inference recipe is used.

Explicit task/limit arguments retain the existing diagnostic policy. Output
templates remain under `data/grades/_diagnostic/<ordered-five-task-sha256>/`,
with adjacent `.cost_ledger.sqlite3` and `.cost_ledger.jsonl` templates. The
inference repository/revision and materialized-config grader source hash are
null until verified. No dataset SHA or Git base substitutes for live inference
identity. The existing resolver must bind those values before producing a
final filename. Grade schema 1.4, `grading_cost`, `cost_ledger`, and
`cost-receipt-v1` retain their existing absence/null/partial semantics.

The required source set grows from 21 to 22 by adding `step8_grade.py`. Its
existing `compute_grader_source_hash` also binds the full grader closure,
including core modules, requirements includes, schema, prompts, inference
download helper, and the original grader template. The new optional
`batch_root` preserves the helper's default behavior and hash algorithm.
`grading.source_sha` records the immutable starting provenance; the actual
template/source closure is
`c10ea303f212bab87ea6303cb41ee51e21430e6bc35df7a69b9a63d265f3a241`.
That is not the eventual hash of a materialized config. The Sol YAML changes
only its existing parser digest; its identity, 16-file pin set, and gates stay
unchanged. Production runtime/config defaults, pricing, schemas, and all
historical ledgers/evidence remain untouched.

### Verification

The following targeted command ran once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_comparison_preflight.py::test_gpt54_pinned_grading_plan_is_bound_and_non_executing
```

Result: `36 passed in 22.79s`.

The selector uses the real step8 parser, grader config validator, experiment
loader, local inference loader, task filter, and output resolver with temporary
fixtures. It checks all 22 pins, grader-closure/config byte drift, canonical
stability, dispatch/grading document binding, task/condition/repeat identity,
argv, schema, and grade/receipt isolation. It also proves that omitted and
explicit helper roots produce the same hash and that generated config changes
are limited to the two rubric fields. Fixture-only source identities never
enter the compiled plan.

Subprocess, network, provider auth, route preflight, grader/rubric-loader
construction, typed Azure client creation, and cost-recorder construction are
forbidden. Refusal cases assert no forbidden calls. The preflight CLI runs in
process and still returns 2. The Sol parser digest is checked without running
its selector. `git diff --check` and the staged implementation diff check passed.

No other pytest selector, broad suite, build, standalone preflight, actual
five-task run, 220-task run, model/grader/VM call, Azure/HF operation, live
credential lookup, workflow dispatch, or Project edit was performed.

### Immutable Review Boundary

The implementation and specification are committed at
`e9d62ffac93ff69f151e113b4d84e7e725824f0a`. The read-only `first-reviewer`
audit compared that exact HEAD with the immutable base and returned `APPROVE`,
with no BLOCK, MAJOR, or MINOR findings and no escalation requested. It ran no
tests, preflights, clients, or network calls. No review correction or selector
rerun was needed. The earlier grading-engineer working-diff audit also found
no concrete blocking defect.

Only this completion record and `CHANGELOG.md` differ from that reviewed HEAD;
the implementation, plans, tests, and specification are unchanged. Review
covers the offline artifact, not the deferred execution gates. Leader review
and automatic CI evidence remain pending; this record claims neither CI
success nor a carrying-PR merge result.

### Remaining Work

Only the offline artifact/source-binding portion of
`comparison_pinned_grading_not_wired` is closed. The remaining blockers are:

- `v2_reasoning_effort_capability_unverified`
- `codex_reasoning_effort_capability_unverified`
- `codex_native_model_call_and_token_limits_unenforced`
- `live_deployment_identity_and_input_bytes_not_verified`
- `comparison_materialization_and_workflow_gates_not_wired`
- `comparison_usage_and_tariff_evidence_unverified`

Actual checkout/config/input/deliverable materialization, verified inference
publication identity, workflow gates, and the evidence above need separate
reviewed work. The real task filter preserves input order rather than
reordering it from `--tasks`, so materialization must verify the fixed order.
Both `launch_allowed` and `full_220_allowed` remain false. The compiler is not a
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
fixed comparison question, configuration-bundle scope, repetitions, task/input
pins, units, and stop boundaries. The consolidated grading specification and
`tasks/grading_task` contract were read before implementation, and the required
`grading-engineer` role audited the real CLI/config/source and receipt paths.
The requested `first-reviewer` role reviewed the immutable implementation HEAD.
These roles use the available engine, not an external paid model invocation.

`im-not-ai-en` was applied to the English changelog, completion record, and PR
wording. Protected commands, SHAs, counts, and uncertainty were checked manually;
the owner's one-selector validation scope takes precedence over an additional
fidelity-script run. Experiment-report skills do not apply because there are
no measured experimental outcomes. Repository-readiness, UI, and animation
skills do not apply to this existing offline compiler. Workflow files,
`core/qa.py`, and HF upload code are unchanged, so no extreme-reasoner scope
was created. No new API/provider or authentication contract is introduced.

## Prior Result: #618 Offline Dispatch Plan

[#618](https://github.com/hyeonsangjeon/gdpval-realworks/pull/618) compiled the
four ABBA dispatch specs without executing them. Its reviewed implementation
HEAD was `f58da12cf3a835b0a37674b5e8ccd53a4715c9fe`, and its final branch HEAD was
`5ed50968146eebccd1044e95134a1ceccc98f2eb`. The historical targeted result was
`25 passed in 9.44s`. That selector was not rerun in this task.
