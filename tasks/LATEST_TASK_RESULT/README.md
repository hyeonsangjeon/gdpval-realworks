# Latest Task Result

- Updated: 2026-09-20 (UTC)

## Current Task: PR #629 Complete-Preparation Fixture Cache

### Scope and Outcome

The ineffective source-only fixture seed was first removed by manual patch in
normal commit `a9a7f631d2fcb83afebb9d08611f4960a27286f6`. The test file at that
commit is byte-equal to `a31dc33470674c5c6b1c0f5f4cb837f796056474`. No reset,
checkout restore, revert command, amend or rebase was used.

The replacement fixture runs real `prepare_workflow_execution` once for each
of the four ABBA recipes at module scope. Mutation cases get fresh linked
worktrees and exclusive single-link copies of generated config/input files,
reservations and ready markers. They do not copy Git registration metadata or
share mutable trees. Each case still creates its own source Git repository.
The seed's filesystem snapshot is unchanged at teardown; copied files are
checked for single-link isolation. Only immutable bytes, frozen typed prepared
records and actual preparation-order traces cross case boundaries.

The real CLI, preparation failure, handoff/quarantine and rerun-refusal paths
remain in the cases that test them. YAML/input-shape cases do not construct a
prepared seed. Real verifiers and all original assertions remain unchanged;
no validator verdict is cached. The existing #626 input seed and byte-keyed
parse/hash caches retain their original drift invalidation.

The final invocation reported `64 passed in 28.36s`, meeting the owner's
30-second local acceptance limit. This is distinct from the original
`64 passed in 80.13s (0:01:20)` and the removed source-only attempt's
`64 passed in 82.28s (0:01:22)`. No second invocation was made. Fresh automatic
Backend Tests must still establish full-suite headroom within the unchanged
45-minute timeout.

The parent PR's workflow gate is unchanged. Both owning workflows separate
GPT-5.4 comparison admission from provider secrets and OIDC, bind an explicit
caller-reviewed source SHA to the workflow/event commit, and reuse the existing
disposable-checkout preparer and runtime lineage verifier. The helper binds
exact compiled commands and cwd to the prepared checkout without executing
them. The mandatory launch check refuses execution. Both `launch_allowed` and
`full_220_allowed` remain false. The onboarding correction still includes
`comparison_reviewed_source_sha` in the expected input/default map, four owner
README tables and adjacent smoke examples.

The correction starts from PR HEAD
`e7f05a60696bbda1735aaba7da47cf4633a32c4e` in the existing development branch
`b/gpt54-workflow-execution-gate-20260919`. The immutable PR base remains
`1671d6d87c27894d6b1a4d75ee5e7be21170feaa`. The preservation checkout and prior
worktrees were not used for edits. Existing Git author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was retained without changing Git
configuration, bypassing commit hooks or adding trailers.

This correction changes exactly three files: the workflow-gate test,
`CHANGELOG.md` and this record. Production code, helpers, workflow logic,
timeouts, source pins, inputs/defaults, launch flags and historical evidence are
unchanged. The cumulative PR still changes these 26 files:

- `README.md`
- `README_KR.md`
- `batch-runner/README.md`
- `batch-runner/README_KR.md`
- `scripts/__tests__/onboarding-contract.test.mjs`
- `.github/workflows/agentic-v2-stage-run.yml`
- `.github/workflows/batch-run.yml`
- `batch-runner/gpt54_workflow_gate.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_workflow_gate.py`
- `batch-runner/tests/test_agentic_workflows.py`
- `batch-runner/tests/test_a_batch_dispatch_can_open_the_codex_gate.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_disposable_checkout.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `batch-runner/tests/test_gpt54_prepared_input_attestation.py`
- `batch-runner/tests/test_gpt54_codex_input_capture.py`
- `batch-runner/tests/test_gpt54_v2_input_capture.py`
- `batch-runner/tests/test_gpt54_run_input_bundle.py`
- `batch-runner/tests/test_gpt54_runtime_checkout.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Exact Validation Evidence

The original gate selector reported `64 passed in 80.13s (0:01:20)`, exit 0.
The leader then reported that Backend Tests run `35475698464`, job
`105984493581`, at HEAD `a31dc33470674c5c6b1c0f5f4cb837f796056474` ended with
`Run tests` cancelled at the 45-minute timeout and no reported test failure.
The supplied job interval was `2026-09-19T23:17:32Z` to
`2026-09-20T00:02:47Z`. The leader reported `validate`, `advance-check` and
`hosted-containment` as successful. These are supplied CI facts, not a fresh
post-correction result.

The removed source-only attempt at implementation HEAD
`f2c4d18b1696917a4dbe73039fe5b63b3b3f6c7e`, carried by
`e7f05a60696bbda1735aaba7da47cf4633a32c4e`, reported
`64 passed in 82.28s (0:01:22)`. That was `2.15s` slower than the original and
did not demonstrate budget recovery. It is prior evidence, not the final result.

After replacing that fixture with complete preparation seeds, the same targeted
selector was invoked exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_workflow_gate.py::test_workflow_execution_gate
```

Result: `64 passed in 28.36s`, exit 0. No case was removed, skipped or
marked xfail. The unchanged matrix contains two workflow YAML cases, four ABBA
preparations and 58 refusal cases. It retains owner/default/SHA checks,
provider-before ordering, collisions, unsafe paths and links, source-pin drift,
attached/wrong/moving HEAD, missing or changed markers, quarantine, changed
argv/cwd, attempted launch-flag changes, preparation/handoff failures and rerun
refusal. Post-preparation mutations still exercise the real lineage verifier,
not merely the always-refusing launch check. Both r2 cases exercise the real CLI
in-process and return exit 2 without dispatch.

The four ABBA seeds use real checkout and config/input bundle preparation.
Copied fixtures use fresh linked worktrees and real verification after case
mutations. Their ordering assertion uses the actual trace captured during that
run's real seed preparation; no synthetic callbacks are added. CLI and failure
cases still observe their own real preparation calls. Subprocess guards allow
only bounded local Git. Network, auth, provider, model, grader and VM guards
recorded no calls. No baseline rerun, broad suite, build,
manual workflow rerun, live execution-checkout preparation, workflow dispatch,
Azure/HF access, download, OIDC/token lookup, inference, grading, paid execution,
Project edit or merge was performed.

`git diff --check e7f05a60696bbda1735aaba7da47cf4633a32c4e HEAD` passed on the
implementation commit. The local selector establishes correctness for these
fixtures; it does not establish restored full-suite headroom. The timing is one
invocation, not a repeated or controlled performance comparison.

### Immutable Review Boundary

Implementation HEAD `413e94b7fb7b63ffe7cc49211ffb787c44340866` received a fresh
read-only `first-reviewer` review against incoming HEAD
`e7f05a60696bbda1735aaba7da47cf4633a32c4e` and the original fixture at
`a31dc33470674c5c6b1c0f5f4cb837f796056474`. The verdict was `APPROVE`, with no
BLOCK, MAJOR or MINOR findings and no second-review escalation. The reviewer
confirmed four real preparation seeds, independent linked worktrees and
exclusive single-link files, seed immutability, all 64 cases and original
assertions, real verifiers, CLI/refusal/quarantine coverage and actual ordering
evidence. Review involved no tests, imports, project execution, network or
mutations.

Approval covers fixture correctness and isolation. The `28.36s` result meets
the local 30-second limit but does not prove full-CI timeout resolution or merge
readiness. Only `CHANGELOG.md` and this record follow the reviewed implementation
HEAD. Leader review and fresh automatic CI remain required; no future
carrying-PR merge SHA, time or outcome is claimed.

### Prior Review and Onboarding Evidence

The original gate review at `d54df8aa4187070c261103271dd8d587639ec735` and the
onboarding correction review at `545e6a4309eef7286efd0fc0c9b4f639355542c4` both
returned `APPROVE`. They are prior evidence, not approval of the current HEAD.

The onboarding correction followed the `validate` failure at
`b1f4a5da0bccc6760d2b78b0708770d35df848dd`, run `35474119808`, job
`105980280399`. The failing selector reads `batch-run.yml` and the owner tables:

```bash
PYTHONDONTWRITEBYTECODE=1 node --test --test-name-pattern='^workflow input tables mirror defaults and watchdog delegation$' scripts/__tests__/onboarding-contract.test.mjs
```

Its prior one-time result was `1 passed, 0 failed, 0 skipped`, exit 0; subtest
`514.103645 ms`, total `696.085328 ms`. It was not rerun for either fixture
correction.

### Skills and Roles

The full skill and repository-agent catalogs were inspected before the original
gate edits. `experiment-design`, `llm-systems-engineer` and the pre-edit
`extreme-reasoner` decision bounded that implementation. The decision was
`APPROVE-WITH-CONDITIONS` for secret/OIDC separation, explicit source identity,
preparer/verifier reuse and false launch flags; that boundary is unchanged.

This correction uses `first-reviewer` for the fresh immutable review and
`im-not-ai-en` for English changelog, completion and PR wording. Copyediting
preserves commands, SHAs, counts, timestamps, the failed attempt and the final
measurement's limits. Roles ran in the available runtime; unavailable externally
named models are not claimed. Fixture preparation does not change experiment
design or workflow logic, so no new experiment-design or extreme-reasoner
decision was needed. Experiment-report skills do not apply to software
validation. No grading implementation changed; grading-engineer was not needed.
Repository-readiness, UI and animation skills are unrelated.

### Evidence Limits and Remaining Work

The local 30-second criterion is met, but no new full-suite success is claimed.
The supplied 45-minute CI cancellation remains historical evidence. Automatic
checks after the normal push must establish that the Backend Tests budget has
recovered; they remain a separate gate.

The unchanged workflow gate proves offline request binding and local prepared
checkout consistency, not external source-review or inference-identity approval,
served capability, actual wire equality or launch permission. No comparison
workflow was dispatched. ABBA, model/effort, task cohort, limits and record-only
null/partial cost semantics remain fixed. Remaining execution work includes:

- External inference identity issuance and approval.
- A host supporting native no-clobber result-bundle installation.
- Actual runner deployment, local pinned data provisioning and workflow execution.
- V2 same-host approval/capture compatibility at the actual execution boundary.
- Served deployment/model/effort capability and native call/token caps.
- Actual wire-request consumption/equality and usage/tariff evidence.
- The separate Sol pilot's GitHub Copilot provider/auth route, still blocked by
  the missing official runtime handoff contract.

## Prior Result: #628 Runtime Checkout Lineage Gate

The prior unit added in-place checkout lineage verification before the V2 and
Codex provider boundaries. Its recorded local selector result was
`50 passed in 69.18s (0:01:09)` and was not rerun here. The present PR adds
workflow admission without turning local preparation into launch authorization.
