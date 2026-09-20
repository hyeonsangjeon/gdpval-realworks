# Latest Task Result

- Updated: 2026-09-20 (UTC)

## Current Task: PR #629 Backend Comparison Shard

### Scope and Outcome

Backend Tests now partitions its batch-runner test files between two independent
jobs. The existing required check name `pytest` remains the core job. It excludes
only the 11 actual `batch-runner/tests/test_gpt54_*.py` files, each named by an
explicit `--ignore` argument. The read-only `comparison-contracts` job names
those same files exactly once. Tests under repo-root `scripts/__tests__` remain
in core only.

Both jobs use the same `ubuntu-latest` runner, pinned checkout/setup actions,
Python `3.10.12`, `requirements.txt`, pip cache settings and 45-minute timeout.
Both enforce the existing dispatch SHA/checkout contract and integration safety
filter. Workflow permissions, triggers and concurrency are unchanged. There is
no matrix, job dependency, new package, credential, OIDC grant or paid route.
No test was removed, newly skipped or marked xfail. Existing test bodies,
including the 64-case workflow gate and its full-preparation cache, are unchanged.

The correction starts from immutable PR HEAD
`55904cc068888df4c95226ff558dc9ddaf2f1097` on the existing branch
`b/gpt54-workflow-execution-gate-20260919`. The immutable PR base remains
`1671d6d87c27894d6b1a4d75ee5e7be21170feaa`. The preservation checkout and prior
worktrees were not edited. Existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was retained without changing Git
configuration, bypassing hooks or adding trailers.

This correction changes four files:

- `.github/workflows/backend-tests.yml`
- `batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The parent PR's comparison admission helper, both owning execution workflows,
onboarding correction, source pins, experiment contracts and runtime/grader
behavior are unchanged by this unit. Both `launch_allowed` and `full_220_allowed`
remain false. The cumulative PR changes 28 files:

- `.github/workflows/agentic-v2-stage-run.yml`
- `.github/workflows/backend-tests.yml`
- `.github/workflows/batch-run.yml`
- `CHANGELOG.md`
- `README.md`
- `README_KR.md`
- `batch-runner/README.md`
- `batch-runner/README_KR.md`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/gpt54_workflow_gate.py`
- `batch-runner/tests/test_a_batch_dispatch_can_open_the_codex_gate.py`
- `batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py`
- `batch-runner/tests/test_agentic_workflows.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/tests/test_gpt54_codex_input_capture.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_disposable_checkout.py`
- `batch-runner/tests/test_gpt54_prepared_input_attestation.py`
- `batch-runner/tests/test_gpt54_run_input_bundle.py`
- `batch-runner/tests/test_gpt54_runtime_checkout.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `batch-runner/tests/test_gpt54_v2_input_capture.py`
- `batch-runner/tests/test_gpt54_workflow_gate.py`
- `scripts/__tests__/onboarding-contract.test.mjs`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Exact Validation Evidence

The owner reported two fresh Backend pytest runs cancelled at the unchanged
45-minute ceiling without reported test failures. This is supplied CI evidence;
the failed jobs were not rerun or re-investigated in this turn. The split responds
to that repeated budget failure without extending the timeout or reducing tests.

Only this new static selector ran, exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts
```

Result: `1 passed in 0.17s`, exit 0, on Python `3.10.12`. The selector parses
the actual YAML commands and compares their explicit paths with the actual
11-file collection. It verifies uniqueness, complete/non-overlapping coverage,
the unchanged core check name, setup/dependency/cache/timeout parity, dispatch
and checkout identity checks, read-only permissions, concurrency, the existing
integration filter and core-only script tests. It reads filenames and workflow
configuration; it does not collect or run the comparison suite.

`git diff --check` passed before the implementation commit. No broad suite,
64-case selector rerun, build, manual workflow run, live checkout preparation,
Azure/HF access, download, OIDC/token lookup, provider/model/grader call, paid
execution, Project edit or merge was performed.

### Immutable Review Boundary

Before editing, `extreme-reasoner` reviewed incoming HEAD
`55904cc068888df4c95226ff558dc9ddaf2f1097` and returned
`APPROVE-WITH-CONDITIONS`. The conditions require an exact file partition,
identical setup and free-test/dispatch safeguards, unchanged core check identity
and timeout, and explicit review of both job verdicts. Branch protection is
outside this correction; no aggregate success is manufactured.

Implementation HEAD `3d188805ad6240fcbdbc47091f949289d7e143c3` received fresh
read-only reviews against that incoming HEAD. `extreme-reasoner` returned
`APPROVE`, with all pre-edit conditions satisfied and no blocking or
high-confidence code findings. `first-reviewer` returned `APPROVE`, with no
BLOCK, MAJOR or MINOR findings and no second-review escalation. Both confirmed
the exact file partition, preserved tests, setup/safety parity and unchanged
45-minute limits. Neither ran tests, project imports, network calls or mutations.

Only `CHANGELOG.md` and this record follow the reviewed implementation commit.
These reviews do not establish hosted completion time, CI-budget recovery or
merge readiness. Both job verdicts must be checked at the final carrying
HEAD; prior approvals do not substitute for those results.

### Prior Validation and Review Evidence

The original workflow gate reported `64 passed in 80.13s (0:01:20)`. The removed
source-only fixture attempt reported `64 passed in 82.28s (0:01:22)`, so it did
not demonstrate a speedup. It was manually removed in normal commit
`a9a7f631d2fcb83afebb9d08611f4960a27286f6` before the complete-preparation cache.
That cache reported `64 passed in 28.36s`, meeting its 30-second local limit.
These are distinct prior invocations, not measurements made for this shard.

The unchanged prior selector was:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_workflow_gate.py::test_workflow_execution_gate
```

The earlier supplied Backend Tests cancellation was run `35475698464`, job
`105984493581`, at HEAD `a31dc33470674c5c6b1c0f5f4cb837f796056474`. Its supplied
interval was `2026-09-19T23:17:32Z` to `2026-09-20T00:02:47Z`; `Run tests` reached
the 45-minute timeout without a reported test failure. The newer owner report
confirms that the full-preparation cache did not by itself close the CI budget
gate. No hosted-timeout recovery is claimed here.

The onboarding correction followed `validate` failure run `35474119808`, job
`105980280399`, at HEAD `b1f4a5da0bccc6760d2b78b0708770d35df848dd`. Its exact
selector was:

```bash
PYTHONDONTWRITEBYTECODE=1 node --test --test-name-pattern='^workflow input tables mirror defaults and watchdog delegation$' scripts/__tests__/onboarding-contract.test.mjs
```

Its prior result was `1 passed, 0 failed, 0 skipped`, exit 0; subtest
`514.103645 ms`, total `696.085328 ms`. It was not rerun here. The original gate,
onboarding and full-cache implementation reviews returned `APPROVE` at
`d54df8aa4187070c261103271dd8d587639ec735`,
`545e6a4309eef7286efd0fc0c9b4f639355542c4` and
`413e94b7fb7b63ffe7cc49211ffb787c44340866`, respectively. Those approvals are
prior evidence, not approval of the new shard.

### Skills and Roles

The supplied skill catalog and repository agent catalog were inspected.
`extreme-reasoner` supplies the mandatory new workflow decision and immutable
review; `first-reviewer` reviews the implementation diff. Roles use the available
runtime, not the unavailable external models named in their role files.
`im-not-ai-en` applies to the English changelog, completion record and PR text,
preserving commands, SHAs, counts, timings and uncertainty.

This changes CI scheduling, not the experiment design, inputs or grading
contract, so no new experiment-design or grading-engineer pass applies.
Experiment-report skills do not apply to software validation. Repository-readiness,
UI and animation skills are unrelated. The parent comparison workflow's earlier
experiment-design and systems-engineering boundaries remain unchanged.

### Evidence Limits and Remaining Work

The static selector establishes the partition and configuration parity, not
hosted execution or restored timeout headroom. The additional runner repeats
checkout, Python setup, dependency installation and collection work. Each job
keeps its 45-minute ceiling; the configured aggregate exposure is now up to
90 runner-minutes rather than 45, excluding queueing. Neither actual duration
nor billed minutes were measured here.

A green `pytest` now means core passed. The leader must inspect both `pytest`
and `comparison-contracts`; this edit does not make the new check required in
branch protection. The existing bot-result flow reads overall Backend Tests
workflow success, which includes both jobs. Automatic CI after the normal push
must still establish both verdicts. No future merge SHA, time or outcome is
recorded.

No comparison workflow was dispatched. The parent gate still proves only
offline admission, local preparation and refusal, not external source-review or
inference-identity approval, served capability, wire equality or launch permission.
ABBA, model/effort, task cohort, limits and record-only null/partial cost semantics
remain fixed. Execution work still includes:

- External inference identity issuance and approval.
- A host supporting native no-clobber result-bundle installation.
- Actual runner deployment, pinned data provisioning and workflow execution.
- V2 same-host approval/capture compatibility at the execution boundary.
- Served deployment/model/effort capability and native call/token caps.
- Actual wire-request consumption/equality and usage/tariff evidence.
- The separate Sol pilot's GitHub Copilot provider/auth route, still blocked by
  the missing official runtime handoff contract.
