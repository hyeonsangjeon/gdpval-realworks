# Latest substantive task result

## PROJECT5-GPT56-RUNTIME-CAPS-USAGE-RECEIPT

Implemented a caps/usage receipt owner attached to the registered Foundry
GPT-5.6 Sol pilot's existing capture, wire and accepted-result session. The sole
authorized selector passed: `86 passed, 110 deselected in 939.90s (0:15:39)`,
exit 0. This is offline verifier evidence, not a live pilot receipt, proof of
native spending enforcement, a billing measurement or hosted CI headroom.
All launch/full-220 flags remain false.

### Scope and evidence boundary

The owner records the actual task/attempt order, infrastructure retry indices,
and one observed app-server thread and turn per attempt. Those counts are not
model-call counts. The transport observer retains exact native input, cached,
cache-write, output, reasoning and total token snapshots, including optional
null/absent fields and the reported context window. It checks cumulative
monotonicity, subcounts, reported totals, reviewed input/output thresholds and
any reported context-window mismatch. Missing required totals refuse result
acceptance. A notification can report an overrun after it occurred; these
checks do not establish provider-native preemptive enforcement.

The receipt binds the verified evidence bundle's `native_caps`, `usage` and
`tariff` artifact hashes, approved limits and meter identities. Reviewed
quantities and tariff rates do not become runtime observations. Model-call
count, native spending enforcement, Foundry HTTP/request identity, served
identity, billing quantity and currency conversion remain `not_available` on
the pinned route. Cost stays null/partial; no price is calculated or invented.

The wire owner installs the observer only when its registered pilot host owner
is present. Step 2's existing host acceptance and publication hooks require the
caps owner, so no runner or Step 2 source change was needed. Attempt receipts
bind the verified capture, wire record, accepted host record and accepted-row
fingerprint. Final publication binds the exact saved-result bytes and the host
ready marker without inserting a circular link back into those sealed results.
The owner rechecks parent bytes after publication and writes its ready marker
last. Failures poison the linked owners and retain partials for quarantine.
There is no disk-only adoption API, new CLI, offline receipt-consumption option
or runnable launch command. Legacy absent/null output behavior is unchanged.

Preflight still requires all six external evidence roles. Its closed clearing
map now removes only the three identity/capability requirements; a complete
offline export cannot remove the native-call or billing requirements. Even
after explicit verification of all local preparation bundles, these remain:

- `native_call_and_token_limits_unresolved`
- `live_inference_identity_and_wire_unverified`
- `foundry_usage_and_tariff_mapping_unverified`
- `native_sandbox_and_result_bundle_host_unverified`

The new receipt reports observed token-threshold checks but clears none of
those four blockers. Synthetic owners never establish real pilot service,
remote isolation, actual model calls or a billed meter quantity. Public receipt
files contain no prompt/output text, private host paths, raw resource IDs,
endpoint, credential, auth material or exception strings.

### Exact validation and implementation boundary

The new clean worktree and branch started from exactly
`0ae151d105258c6f716e22aea54c7df8cd0a8112`:
`b/gpt56-runtime-caps-usage-20260921`. Prior worktrees and the preserved local
main branch were not edited.

Exactly one targeted pytest invocation ran from the worktree root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py -k runtime_caps_usage
```

Result: `86 passed, 110 deselected in 939.90s (0:15:39)`, exit 0, on initial
implementation `97b9e1c07149a7f85e9e33a85cb5d6b15dd99a96`. The selector
covers observed and unavailable fields, threshold boundaries, monotonicity,
context/correlation, retry/order, current evidence and parent links, forged
quantities/meters, privacy, no-clobber/partial publication, session reuse,
legacy no-op behavior and false flags. Scalar cases exercise the real transport
observer with a bounded owner stand-in; full-session cases use the real capture,
upstream, wire, host and saved-result verifiers. Module-scoped seeds share only
immutable bytes, each case copies fresh single-link files, and YAML parsing is
cached by current bytes rather than by verifier verdict.

No earlier selector, full wire file, core suite, contract job, broad suite or
manual workflow ran. The old count/blocker assertions were updated statically
and were not rerun locally. `git diff --check` and `git diff --cached --check`
passed. The unchanged four-way Backend partition remains responsible for
fresh automatic coverage of the full affected groups and their time budgets.

Both requested reviewers returned REQUEST-CHANGES on the initial implementation
because the existing reference-drift fixture started at the third task on a
fresh owner. The new order check correctly refused that start before the test
could mutate the reference or reach its refusal assertion. The test-only
correction completes the first two tasks through the real start, finish and
accept/record helpers before testing third-task drift. Production ordering and
all drift assertions remain intact. The stale evidence test name now says
three cleared requirements rather than five.

Fixed immutable implementation HEAD:
`e84761f3589cdade5ba0f9d066a490042cceaa86`. `llm-systems-engineer` and
`first-reviewer` both returned read-only APPROVE on that exact HEAD, with no
remaining blocking findings. The correction changed only two test files; no
production code or source pin changed after the passing selector. Neither the
selector nor the corrected reference-drift case was rerun locally. These static
approvals do not establish a new test result or hosted CI headroom. The
records-only commit follows both approvals and is outside the implementation
review boundary.
Fresh same-HEAD automatic CI remains required; no result is claimed here.

### Files, skills and remaining work

Production changes are limited to `gpt56_pilot_runtime_caps_usage.py`, its
wire/native-host hooks, the pilot preflight and the active Foundry contract.
The exact source closure grows from 55 to 56 files. Only directly affected
source pins and existing count/blocker expectations were refreshed. The new
cases are in `test_gpt56_sol_codex_pilot_preflight.py`; no test file was added.
Workflows, jobs, matrices, dependencies, timeouts, core/QA, grader and HF upload
code are unchanged. Model, five-task scope, reasoning/context request and
experiment limits are unchanged.

The full skill catalog was inspected once. `experiment-design` established
the single evidence-contract change and the falsifier: a missing, inconsistent
or stale observation must refuse acceptance, not become a complete receipt.
`llm-systems-engineer` supplied the helper and approved the fixed implementation;
`first-reviewer` independently approved the same immutable HEAD. `im-not-ai-en`
keeps the English records' commands, hashes, numbers and evidence limits exact.
UI/animation, grading and repo-readiness do not apply to this scope.
`extreme-reasoner` is not triggered because workflows, core/QA and HF upload
code are untouched.

Remaining work includes actual reviewed Foundry evidence acquisition, a
separately approved deployment/execution, live wire/served identity, a live
native-host result, observable native model-call enforcement and Foundry
usage/tariff/billing receipts. The pinned route still cannot expose every
required fact. No Azure/HF/OIDC, provider/model/client, grader, inference,
download, paid execution, Project or merge action occurred. Existing Git
identity `hyeonsangjeon <wingnut0310@gmail.com>` is unchanged, with no
attribution trailers, history rewrite, force push or hook bypass. This record
stops at pre-merge facts.

The #639 records below remain historical. They preserve the original
`1 failed, 70 passed, 84 deselected in 2790.26s (0:46:30)` result, the two
unrerun corrections, hosted 1179-item failure/cancellation evidence and the
subsequent `2 passed in 21.28s` correction selector. Neither those results nor
the earlier #638 hosted checks validate the caps/usage implementation above.

## Historical PROJECT5-PR639-PILOT-CI-FIX

Corrected the stale input-capture test expectation and split the native-host
cases into a fourth Backend job on the existing PR #639 branch. Production
code, experiment settings, source pins, launch flags and runtime evidence
boundaries are unchanged. The single authorized two-node selector passed;
fresh automatic CI is still required for all four jobs at the final HEAD.

### Hosted failure and static diagnosis

The leader supplied the following evidence for
`3d8336933ed26266332c97b3caf1235b95cb98e4`: Backend run `35529571789`,
`pilot-contracts` job `106127662743`, collected 1179 items. The log showed a
failure at the second input-capture test, reached the wire-receipt file at
about 80%, and remained there until cancellation after about 45:15. Core
`pytest`, `comparison-contracts`, validate, advance, freeze and containment
succeeded. The cancelled job was not rerun and no timeout was increased.

Collection order identifies the early failure as
`test_step2_and_final_output_bind_verified_capture_before_provider`.
Static tracing shows that Step 2 first verifies the capture, then the live
host-session constructor calls `wire_session._current()`, which verifies it
again before the host/auth boundaries. The test now expects the exact trace
`["verify", "verified", "verify", "verified", "host_boundary", "auth_boundary"]`.
The real verifiers, refusal assertions, final-output AST extraction and
fingerprint checks remain intact. No production fix was needed.

### Four-way partition and decision

| Check | Exact selection |
| --- | --- |
| `pytest` | Existing core command excludes the sorted union of all 11 GPT-5.4 and 9 GPT-5.6 files. The repo-root script-test step is unchanged. |
| `comparison-contracts` | The same sorted 11 `tests/test_gpt54_*.py` files. |
| `pilot-contracts` | The sorted eight `tests/test_gpt56_*.py` files other than `test_gpt56_pilot_wire_receipt.py`, then that wire file with `-k "not native_result_host"`. |
| `native-host-contracts` | Only `tests/test_gpt56_pilot_wire_receipt.py -k native_result_host`. |

The existing static node checks the four job names, identical six-step setup,
exact file lists, 20 core exclusions, complementary literal keyword predicates,
and complete, disjoint node selection. It uses pytest's expression parser and
the wire source AST without importing or collecting that file. The keyword
occurs only in the wire source among GPT-5.6 test files. All other files have
one selection without a keyword filter. The two pilot commands retain normal fail-fast
behavior: if the eight-file command fails, its following wire command does not
run. Exactly-once selection does not mean a failed job executed every node.

Before edits, `extreme-reasoner` returned APPROVE-WITH-CONDITIONS against the
correction base. The patch preserves `contents: read`, pinned actions,
`ubuntu-latest`, full-history checkout without persisted credentials, dispatch
and exact-checkout guards, Python 3.10.12, pip cache/dependencies, the integration
guard and explicit `-m "not integration"`. All four jobs retain 45-minute limits
and run independently under the existing ref-scoped concurrency/cancellation.
There is no matrix, dependency, new secret, OIDC permission or credential route.

The configured allowance rises from 3 × 45 = 135 to 4 × 45 = 180 runner-minutes,
an increase of 45 minutes or 33.3%. The new job adds a runner slot and setup
cycle; the extra pytest process adds collection/fixture work. This is not a
billing measurement or evidence of speedup or CI headroom. All four check
verdicts must succeed at the same final HEAD. External required-check settings
and the result-PR caller's existing 1,800-second wait are unchanged.

### Exact correction validation and review boundary

Exactly one targeted pytest invocation ran from the worktree root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt56_pilot_input_capture.py::test_step2_and_final_output_bind_verified_capture_before_provider batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts
```

Result: `2 passed in 21.28s`, exit 0. `git diff --check` and
`git diff --cached --check` passed. No native-host selector, full wire file,
pilot group, prior selector, full suite or manual workflow ran in this
correction. The two-node result does not validate the full native-host contract
or predict the new job durations.

The correction base is `3d8336933ed26266332c97b3caf1235b95cb98e4`; the immutable
implementation HEAD is `360af26eb9c8fd051c301e2463ba297c747ca198`.
Both `llm-systems-engineer` and `first-reviewer` returned APPROVE with no
findings on that exact HEAD. Their reviews inspected immutable Git objects
without running tests, imports, collection, network calls or CI queries.
These are static implementation approvals, not hosted runtime-budget evidence.
This record and CHANGELOG belong to a subsequent records-only commit outside
the implementation-review boundary.

### Preserved evidence, scope and remaining work

The original native-host selector remains `1 failed, 70 passed, 84 deselected in
2790.26s (0:46:30)`, exit 1. Its later `pilot.inspect` to `pilot.inspect_plan`
correction and content-keyed text-stream YAML fixture-cache correction were not
followed by a local native-host rerun. Neither a passing native-host selector
nor a cache speedup is claimed. The full original record and PR #638 evidence
remain below; they do not validate this correction.

This correction changes only `.github/workflows/backend-tests.yml`,
`batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py`,
`batch-runner/tests/test_gpt56_pilot_input_capture.py`, `CHANGELOG.md` and this
record. The mandatory `extreme-reasoner` decision covers the added CI runner;
`llm-systems-engineer` and `first-reviewer` cover the immutable implementation.
`im-not-ai-en` preserves the English records' commands, hashes, timings and
evidence limits. No experiment/runtime contract changed, so experiment-design
was not repeated. UI/animation, grading and repo-readiness do not apply.

For the real pilot, `native_sandbox_and_result_bundle_host_unverified` and
`live_inference_identity_and_wire_unverified` remain unresolved. Actual Foundry
evidence acquisition/approval, separately approved deployment/execution,
native-cap enforcement and usage/tariff/billing receipts remain separate work.
All launch/full-220 flags stay false. No Azure/HF/OIDC, provider/model/client,
grader, paid execution, Project or merge action occurred. Existing Git identity
`hyeonsangjeon <wingnut0310@gmail.com>` is unchanged; there are no attribution
trailers, history rewrites, force pushes or hook bypasses. This record stops at
pre-merge facts. Fresh same-HEAD automatic CI and duration evidence remain
required.

## Historical PROJECT5-GPT56-NATIVE-RESULT-HOST

The following record describes the original implementation before the CI
correction above. Its unchanged-workflow and three-job statements apply to that
earlier scope, not the current four-job partition.

Implemented a session-owned native workspace and accepted-result receipt for
the registered Foundry GPT-5.6 Sol five-task pilot. The current pilot still has
no live host evidence. Both `native_sandbox_and_result_bundle_host_unverified`
and `live_inference_identity_and_wire_unverified` remain unresolved, and all
launch/full-220 flags remain false.

The sole local selector reported `1 failed, 70 passed, 84 deselected in
2790.26s (0:46:30)`, exit 1. The test-only API error was corrected without a
rerun. A fixture-cache correction was also made after the run; its speedup is
unmeasured. Fresh automatic CI is required for the corrected implementation
and its runtime budget.

### Scope and evidence boundary

The new helper attaches to the exact live pre-execution capture/wire-receipt
session. The runner requires that owner before runtime/auth, holds the actual
local workspace directory identities, and rechecks collected bytes and the
runner handoff before cleanup. It records the sandbox/approval policy observed
in the app-server request. It does not infer remote or kernel isolation.

Step 2 verifies the runner handoff before accepting or saving deliverables.
The host binds task order and attempt indices, wire-receipt linkage, relative
deliverable paths/sizes/SHA256 values, saved-file records, accepted task rows,
and error/no-output state. Final publication binds a non-circular fingerprint
of the payload before host linkage. It rereads the actual saved result files
and publishes the host ready marker last.

Unsafe paths, links, special files, hidden/runtime files, duplicate or colliding
names, stale links, altered handoffs, changed output bytes, partial publication
and witness/session reuse fail closed. No-clobber writes retain failed partials
for quarantine; another session cannot adopt them. Public host receipts contain
no prompt/output text, private host paths, resource IDs, credentials or exception
strings. The existing Step 2 result retains its ordinary content; the receipt
contains only its digest and the allowed identities.

There is no saved-JSON adoption API, new CLI, offline preflight consumption
option or runnable launch command. A future runtime-owned verified host bundle
may satisfy only the native-host blocker. It cannot satisfy live wire/served
identity, native-cap enforcement, usage/tariff/billing or launch requirements.
Synthetic fixtures establish verifier behavior only.

Legacy absent/null paths keep their collector, saver and output shapes. The
active source closure grows from 52 to 55 files, adding the host helper and two
existing fingerprint/public-error helpers. Only directly affected source pins,
grader source-closure hashes and count expectations were refreshed. The grader
implementation, five-task scope, model, Max effort, 1M request and experiment
settings are unchanged. The three-way Backend partition is unchanged.

### Exact validation and post-run corrections

Exactly one pytest command ran, from the new worktree root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt56_pilot_wire_receipt.py -k native_result_host
```

Pytest collected 155 cases, selected 71 and deselected 84. The selected set has
66 new native-host cases and five adapted existing runner/Step 2 boundary cases.
The result was `1 failed, 70 passed, 84 deselected in 2790.26s (0:46:30)`, exit 1.
The failing node was
`test_native_result_host_five_task_real_verifiers_ready_last_and_private_result_digest`.
It reached its preflight assertion after the receipt checks, then raised
`AttributeError` because the test called nonexistent `pilot.inspect`.
The call now uses the existing `pilot.inspect_plan` API.

Static cost inspection found that `ExperimentConfig.from_yaml()` passes an open
text stream to `yaml.safe_load`, bypassing the existing string/bytes parse cache.
The shared fixture now reads the current `io.TextIOBase` contents into the same
content-keyed cache and returns a fresh `deepcopy`. Changed contents change the
key. Real validators, source hashes, path/link checks, current-byte checks and
session/witness checks still run; no validator verdict or mutable tree is shared.

Neither post-run correction was rerun locally. The 46:30 measurement belongs to
the pre-cache run, not the corrected HEAD. No passing selector, speedup or hosted
CI headroom is claimed. `git diff --check` and `git diff --cached --check` passed.
No full wire selector, prior pilot selector, core suite, contract job, broad
suite or manual workflow ran locally.

### Immutable review boundary

The new clean worktree and branch
`b/gpt56-native-result-host-20260921` start at requested main
`f6d76e2084bcda75de5dad15b98503f598734bc0`.
The implementation review HEAD is
`d2850e6dd4d12ab5180bdaaeef17c840a2a90fa3`.
The initial implementation commit was
`c2fbd6f3696058403b571b35b767a318423ad253`; its only follow-up change corrects a
source-count comment from 52 to 55. Both `llm-systems-engineer` and
`first-reviewer` returned APPROVE on the final implementation HEAD, with no
remaining findings. Their reviews were read-only and ran no tests, imports,
runtime, network calls or CI queries. They checked the 55 source pins and the
actual caller/handoff/result boundary. These are static review verdicts, not
passing test, live-runtime or CI-readiness evidence. This record and the
changelog are a subsequent records-only commit, outside that boundary.

### Historical PR #638 evidence, not validation of this code

The original wire-receipt selector ran from `batch-runner`:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q tests/test_gpt56_pilot_wire_receipt.py --tb=short
```

It reported `88 passed in 642.32s (0:10:42)`, exit 0, at implementation
`59aa7f00de5505e0ed5c1bff8e8ae7757ff9398a`, before the endpoint-account correction.
The corrected implementation
`89e9a33baa3b6c4b3c404f7c2c6f61798003a868` had 89 cases; that full selector was
not rerun locally. The 88-pass result does not validate the account correction
or this native-host implementation.

The subsequent partition history remains distinct:

| HEAD | Backend run / job | Result |
| --- | --- | --- |
| `c88f76f02c43ef9b2672e61d6cdd6d4630235305` | `35514065313` / `106086906143` (`pytest`) | Cancelled at `45:13` / `87%`, with no assertion failure. |
| `8117a667a49133cfd11f3401d17ddfd36d82db55` | `35517208735` / `106095045010` (`pytest`) | Succeeded in about `25:13`. |
| `8117a667a49133cfd11f3401d17ddfd36d82db55` | `35517208735` / `106095045151` (`comparison-contracts`) | Cancelled at about `45:16` / `91%`, with no assertion failure. |

The three-way partition's static selector reported `1 passed in 0.18s` at
reviewed implementation `c6bf7269480bfc804e7f2aaf6427613cdab3fda9`.
The final historical HEAD was
`9e6e42b85e56478f8082cd7bc9ae1fb6feb31812`. A single read of its hosted checks
confirmed all three Backend jobs succeeded in run `35520193108`. They all
started at `2026-09-20T15:38:03Z`:

| Check | Job | Completed UTC | Duration | Result |
| --- | --- | --- | --- | --- |
| `comparison-contracts` | `106102829162` | `2026-09-20T15:55:57Z` | `17:54` | success |
| `pilot-contracts` | `106102829266` | `2026-09-20T15:56:30Z` | `18:27` | success |
| `pytest` | `106102829319` | `2026-09-20T16:03:28Z` | `25:25` | success |

Those hosted results validate the historical HEAD only. They do not establish
success or CI headroom for the new native-host code. No cancelled job was rerun.

### Changed files

- `batch-runner/gpt56_pilot_native_result_host.py`
- `batch-runner/core/codex_runner.py`
- `batch-runner/step2_run_inference.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/tests/test_gpt56_pilot_wire_receipt.py`
- `batch-runner/tests/test_gpt56_foundry_evidence_intake.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_gpt56_pilot_identity_plan.py`
- `batch-runner/tests/test_gpt56_pilot_config_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_input_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_deployment_binding.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Skills and remaining work

The complete skill catalog was inspected once. `experiment-design` was applied
before planning to keep the change confined to local evidence, with no new
experiment axis or launch authority. `llm-systems-engineer` covered implementation
and review; `first-reviewer` covered the immutable implementation. `im-not-ai-en`
was applied to the English records while preserving commands, hashes, counts,
timings and evidence limits.

UI/animation and repo-readiness do not apply to this backend evidence unit.
Grading behavior is unchanged, so no grading skill or execution is needed.
No workflow, `core/qa.py` or HF upload code changed, so the extreme-reasoner
decision boundary was not triggered.

Fresh automatic checks and duration evidence remain required. Actual Foundry
evidence acquisition/approval, a separately approved pilot deployment and
execution, live input consumption/HTTP wire/served identity, a real runtime-owned
native-host receipt, native-cap enforcement and usage/tariff/billing receipts
remain separate work. `launch_enabled`, `launch_allowed`, `full_220_enabled` and
`full_220_allowed` remain false.

No Azure/HF/OIDC/credential lookup, provider/model/client/grader execution,
inference, grading, download, paid execution or manual workflow dispatch occurred.
The preserved checkout and prior worktrees were not edited. Existing Git identity
`hyeonsangjeon <wingnut0310@gmail.com>` was retained without configuration changes,
attribution trailers, history rewriting, force push or hook bypass. Project and
merge actions were not taken. This record stops at pre-merge facts.
