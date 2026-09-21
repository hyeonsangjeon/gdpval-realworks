# Latest substantive task result

## PROJECT5-PR642-PILOT-PREFLIGHT-CI-PARTITION

Moved the complete GPT-5.6 preflight file into a sixth independent Backend
job, `pilot-preflight-contracts`, on the existing PR #642 branch. The seven
other general pilot files stay in `pilot-contracts`. No timeout was raised
and no test node was removed. The GHCP gate implementation was not
re-investigated or changed.

### Supplied hosted evidence and scope

At `b1f28554d636bf7763acbd50d0df7fca59dcc675`, Backend run `35574884052`,
`pilot-contracts` job `106254379443`, started at `2026-09-21 07:50:42Z`
and was cancelled at `2026-09-21 08:35:56Z` (45:14). Pytest began its
1253 items at `07:52:35Z`. The first seven GPT-5.6 files finished by
`08:00:12Z`, about 7:37 later. The final
`tests/test_gpt56_sol_codex_pilot_preflight.py` used about 35:42 and reached
98% before the shared 45-minute job ceiling cancelled the job. On that
same HEAD, validate, pytest, advance-check, comparison-contracts,
wire-contracts and native-host-contracts were green. These are the leader's
supplied timing facts; the cancelled job was not queried or rerun.

The workflow now has this exact partition:

| Job | Selection |
| --- | --- |
| `pytest` | Unchanged core command excludes the sorted union of 11 GPT-5.4 and 9 GPT-5.6 files; repo-root tests remain included. |
| `comparison-contracts` | The same 11 `tests/test_gpt54_*.py` files. |
| `pilot-contracts` | The seven general GPT-5.6 files listed below, each selected once without a keyword filter. |
| `pilot-preflight-contracts` | Only the full `tests/test_gpt56_sol_codex_pilot_preflight.py`. |
| `wire-contracts` | `tests/test_gpt56_pilot_wire_receipt.py -k "not native_result_host"`. |
| `native-host-contracts` | `tests/test_gpt56_pilot_wire_receipt.py -k native_result_host`. |

The sorted seven-file pilot selection is:

```text
tests/test_gpt56_evidence_preflight_gate.py
tests/test_gpt56_foundry_evidence_intake.py
tests/test_gpt56_pilot_config_bundle.py
tests/test_gpt56_pilot_deployment_binding.py
tests/test_gpt56_pilot_identity_plan.py
tests/test_gpt56_pilot_input_bundle.py
tests/test_gpt56_pilot_input_capture.py
```

The new `Run pilot preflight contracts` step runs the whole file with the
unchanged `-m "not integration" --tb=short -q -rs` flags. Its six setup
steps match the other five jobs exactly: dispatch SHA verification, pinned
full-history checkout without persisted credentials, exact-checkout guard,
pinned Python 3.10.12 with pip cache, dependency installation and the
integration-deselection guard. All jobs use `ubuntu-latest`, `contents: read`
and 45-minute ceilings under the existing ref-scoped concurrency. Triggers,
action pins and existing check names are unchanged. No secrets, OIDC,
credentials, matrix, job dependencies or job-level skips were added.

The existing static partition node requires six jobs, exact step names and
commands, identical setup, all 11 GPT-5.4 and 9 GPT-5.6 files, the seven-plus-one
pilot split, and complementary wire predicates. It retains keyword
confinement, exhaustive/disjoint node selection and repo-root coverage.

The user explicitly authorized updating only `WORKFLOW_SHA256` in
`test_ghcp_vm_gate_contract.py` to match the changed workflow bytes. Its final
value is `9814528133f1c3a55a9122f857ce79575ce2b8e99215f216bd833c90128a384a`.
The assertion, historical/Foundry pins, coverage and GHCP behavior are
unchanged. No other GHCP test line, production file, source pin, runtime
receipt or evidence mapping changed.

### Decision, validation and immutable review

The pre-edit `extreme-reasoner` verdict was APPROVE-WITH-CONDITIONS: preserve
security/setup parity, complete disjoint coverage, independent jobs and exact
check names, and require fresh final-HEAD CI. The nominal aggregate ceiling
rises from 5 x 45 = 225 to 6 x 45 = 270 runner-minutes (+45, +20%). This adds
one runner/setup cycle and one pytest process, not test nodes. It is not an
actual billing estimate or a guarantee of headroom; process separation may
also expose fixture or order dependence. Adding the check does not make it
externally required by branch protection. No external gate setting changed.
The memo's workflow-digest authorization blocker was resolved by the user's
explicit one-constant approval.

Exactly one pytest invocation ran for this correction:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts
```

It reported `1 passed in 0.31s`, exit 0, on the bytes committed as
`7e91cde2e26cfe7082e5e2e5584167e329dfbce0`. `first-reviewer` approved that
HEAD and noted one stale comment saying five job verdicts. A normal follow-up
commit changed that word to six and refreshed the coupled workflow digest.
The selector was not rerun after those two line changes. `git diff --check`
passed, including after the correction.

Final immutable implementation HEAD:
`1bba3aa4b091d1bed45f95c8db9263170e2c57f5`, reviewed against
`b1f28554d636bf7763acbd50d0df7fca59dcc675`. `first-reviewer` returned a fresh
read-only APPROVE with no remaining findings on the complete three-file
correction. The review used immutable Git objects and ran no tests or CI
queries. This later records-only update is outside that review boundary.
Fresh automatic CI on the final pushed HEAD is still required for all six
Backend jobs and other applicable checks. Its checks will be read once after
the normal push and reported in the completion response, not another commit.
No GHCP selector, pilot group, full suite, build, fidelity script or manual
workflow ran during this correction.

### Historical GHCP evidence and remaining blockers

The separate GHCP implementation at
`26e6ce0d659655547dcdc5ac01730c3611f2c97f` received read-only
`llm-systems-engineer` and `first-reviewer` APPROVE verdicts. Its command was
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_ghcp_vm_gate_contract.py -k ghcp_vm_gate_contract`,
which reported `93 passed in 9.51s`, exit 0. That selector was not rerun and
does not validate this CI correction or its refreshed workflow digest.

The historical Copilot pilot remains superseded and non-runnable. GHCP's
requested Sol/Max/1M identity remains a request, not served evidence; all nine
observed fields remain null. The exact five-task order, original input hashes,
deliverable/grader contracts and sixteen GHCP source pins are unchanged.
Every GHCP report still retains these 15 blockers:

```text
ghcp_route_served_identity_unverified
max_long_1m_capability_unverified
ghcp_codex_versions_unresolved
authentication_supply_disposal_unresolved
vm_image_os_packages_version_policy_unresolved
fresh_task_vm_reset_unverified
network_permission_policy_unresolved
native_execution_limits_unresolved
repeat_and_variance_plan_unresolved
five_task_time_cost_caps_unresolved
native_ghcp_usage_and_missing_usage_policy_unresolved
original_task_input_materialization_unverified
transcript_tool_command_file_exit_capture_unverified
grading_result_runtime_unwired
grader_validation_unverified
```

`launch_enabled`, `launch_allowed`, `paid_execution_enabled`,
`paid_execution_allowed`, `full_220_enabled` and `full_220_allowed` remain
false. Filling a null or setting a capability boolean cannot clear a blocker.
A separately reviewed unit must define acquisition and verification of served
identity/Max/1M, reproducible reset/capture, enforced limits, authentic GHCP
usage and the remaining operational decisions before a paid run can be
considered. Auth supply/disposal, VM image/version policy, repeat/variance,
time/cost limits, missing-usage policy, actual input materialization and grader
validation remain unresolved. This scheduling correction acquires none of
that evidence. The Foundry contract, source closure, runtime and live
wire/host/caps/billing boundaries remain separate and unchanged. Older task
and CI records below do not validate the six-job correction.

### Skills and ownership

The complete skill catalog was inspected once for this correction.
`extreme-reasoner` was the first relevant agent because a workflow and runner
budget changed. `first-reviewer` reviewed the immutable correction.
`im-not-ai-en` was applied to these English records, preserving commands,
times, counts, SHAs and evidence limits by manual comparison under the
selector-only validation restriction. No fidelity script was run.

`experiment-design` and `llm-systems-engineer` belong to the earlier GHCP
implementation, not this scheduling-only correction: no experiment setting,
LLM pipeline or runtime contract changed. UI/animation, grading and
repo-readiness skills do not apply because no interface, grading behavior or
publication-readiness audit is in scope. The repository's existing
author/committer identity `hyeonsangjeon <wingnut0310@gmail.com>` was preserved,
without attribution trailers or prohibited Git operations. No Azure/Foundry/HF/
OIDC, GHCP login/token, personal OpenAI/Codex account, provider/model/client,
VM, grader or paid execution was used. No Project or merge action occurred.
This record stops at pre-merge facts; PR #642 remains draft.

## Historical PROJECT5-GPT56-EXTERNAL-LIVE-RECEIPT-INTAKE

Added offline intake for sanitized external Foundry receipt claims. The intake
binds caller-pinned bytes to the original finalized capture, wire, accepted-result
host and caps/usage owners. It verifies consistency, not provider authenticity.
No real receipt was acquired and no current pilot blocker was cleared. All
launch/full-220 flags remain false.

### Scope and evidence boundary

The closed schema extends the existing Foundry evidence schema. It preserves
the five-task order and every recorded attempt, infrastructure retry, request
digest/size, local correlation hash, accepted-row/result digest and upstream
ready/reservation linkage. It checks explicit UTC windows and the caller's full
reviewed source SHA. Null and partial fields remain unknown. Declared synthetic
or self-issued sources, guessed model aliases, non-Foundry tariffs, malformed
or stale claims, duplicate attempts/correlations and private fields are refused.

External provider correlation, served identity and billing claims remain
unverified. The pinned route witnesses app-server serialization and local RPC,
thread and turn identities; those are not provider HTTP identities. Source and
issuer labels, hashes and an in-process owner cannot distinguish a real export
from synthetic data disguised as one. Every published bundle therefore reports
`provenance_status: unverified`, `authenticity: not_authenticated_offline`,
`eligible_facts: []` and `cleared_blockers: []`. Present usage quantities must
match available cumulative native counters. Billing quantities remain separate
external assertions, not quantities reconstructed from app-server tokens.
Missing fields are not zero, model calls are not inferred, and cost remains
null/partial. No price or currency conversion is calculated.

Publication uses the existing held-parent and no-clobber helpers. The caller
pins the source artifact's SHA256 and size separately; current source, schema
and upstream bytes are rechecked before and after publication, with ready last.
Collisions, changed bytes, links, extra files, partial reuse and owner reuse fail
closed with static refusals. Failed partials remain for quarantine. A
pre-validation review found that the shared reader's earlier path-size check
did not bound the opened descriptor. The optional bound now checks `fstat` and
the read loop; the legacy unbounded call retains its existing behavior.

There is no disk-only adoption path, runnable CLI or offline preflight receipt
option. Preflight and the active contract register the new helper without
changing blocker mappings. Only directly affected pins/counts were refreshed,
increasing the source closure from 56 to 57 files. Tests extend the existing
preflight selector file; no test file, dependency or framework was added.
Workflows, the four-way Backend partition, core/QA, grader production, HF upload,
experiment settings and execution limits are unchanged.

### Exact validation and immutable reviews

Exactly one pytest invocation ran in the new worktree based on
`20c2fea35fbd0bc9cd197f5fd07c5b4f4113377a`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py -k external_live_receipt
```

Result: `143 passed, 196 deselected in 2606.67s (0:43:26)`, exit 0.
`git diff --check` and the staged whitespace check passed. The local selector
alone approaches the existing hosted pilot job's 45-minute ceiling. Hosted CI
headroom is unresolved; no workflow or timeout was changed.

The fixtures exercise real session owners and verifiers under offline guards.
Pure shape cases share immutable serialized inputs; destructive publication
cases use fresh trees and owners. Synthetic success establishes verifier
behavior only. It does not establish a live pilot or hosted CI headroom.
No earlier selector, contract job, broad/full suite or manual workflow ran.

Immutable implementation HEAD:
`010f7ec0f80c29b6acd8a92077c424ef8f59ef4a`. Its implementation bytes match
the completed selector. Both `llm-systems-engineer` and `first-reviewer`
returned read-only APPROVE verdicts with no remaining findings. They inspected
immutable Git objects without rerunning tests or querying CI. The records-only
commit follows both approvals and is outside their implementation review
boundary. Fresh final-HEAD automatic CI remains required.

### Remaining work and preserved history

All 11 plan-only blockers remain unchanged. After separately verified local
preparation, the existing four unresolved requirements are still
`native_call_and_token_limits_unresolved`,
`live_inference_identity_and_wire_unverified`,
`foundry_usage_and_tariff_mapping_unverified` and
`native_sandbox_and_result_bundle_host_unverified`. This intake clears none.
Actual provider evidence acquisition and authentication, independently reviewed
request/served identity and billing facts, and separately approved deployment
and execution remain future work. Unexposed native model-call counts remain
blocked. No Azure/HF/OIDC, credential, provider/model/client, grader, inference
or paid execution occurred.

The historical #640 record remains distinct: the caps/usage selector reported
`86 passed, 110 deselected in 939.90s (0:15:39)` at
`97b9e1c07149a7f85e9e33a85cb5d6b15dd99a96`; subsequent fixture/name fixes at
`e84761f3589cdade5ba0f9d066a490042cceaa86` were not rerun locally. Hosted run
`35549673553`, job `106181955827`, later reported
`1 failed, 1109 passed in 1552.54s`. The test-only input-bundle expectation
correction at `ffd841ee2d58b1bdc538227baa712c486429aa60` reported
`2 passed in 7.73s`. Those results, and the older #639/#638 records below, do
not validate this new intake.

### Skills and ownership

The complete skill catalog was inspected once. `experiment-design` constrained
the unit to offline consistency evidence and no blocker clearing.
`llm-systems-engineer` supported implementation and immutable review;
`first-reviewer` provided the independent immutable review. `im-not-ai-en`
preserved the exact commands, numbers, SHAs and qualifications in these English
records. UI/animation, grading, repo-readiness and extreme-reasoner did not
apply: no interface, grading behavior, publication-readiness audit or workflow
security boundary changed.

The existing Git identity `hyeonsangjeon <wingnut0310@gmail.com>` was preserved,
without attribution trailers or prohibited Git operations. No Project edit or
merge action occurred. This record stops at pre-merge facts.

## Historical PROJECT5-PR640-INPUT-BUNDLE-EXPECTATION-FIX

Corrected only the expected ordered blocker list in the linked input-bundle
case. The exact correction selector passed both parameter cases:
`2 passed in 7.73s`, exit 0. Production, source pins, workflows, launch flags,
evidence mappings and every other test are unchanged.

### Hosted failure and correction

The leader supplied the failure evidence for PR #640 HEAD
`be06873cee480a7db6b03557af20f85ebf848bb0`: Backend run `35549673553`,
`pilot-contracts` job `106181955827`, completed in 25:52 and reported
`1 failed, 1109 passed in 1552.54s`. The exact failure was
`tests/test_gpt56_pilot_input_bundle.py::test_explicit_verified_bundle_closes_only_prepared_input_requirement`
at line 306.

The linked case's expected list omitted
`native_call_and_token_limits_unresolved` and
`foundry_usage_and_tariff_mapping_unverified`. The unchanged production mapping
correctly keeps both requirements because complete offline declarations do not
establish runtime call or billing observations. The correction adds them in
the existing canonical order, before and after the live-wire requirement.
All other list entries and assertions are unchanged. The explicit input-bundle
gate still clears only `prepared_input_bytes_unverified`.

### Exact validation and immutable review

Exactly one local pytest command ran on the existing PR branch/worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt56_pilot_input_bundle.py::test_explicit_verified_bundle_closes_only_prepared_input_requirement
```

Result: `2 passed in 7.73s`, exit 0. Both `linked=False` and `linked=True`
parameter cases passed. `git diff --check` passed. No pilot-contracts,
runtime_caps_usage, native-host, wire, broad/full suite or manual workflow
was run locally.

Test-only immutable correction HEAD:
`ffd841ee2d58b1bdc538227baa712c486429aa60`. Fresh read-only
`llm-systems-engineer` and `first-reviewer` verdicts are both APPROVE, with no
findings. Both reviewers checked immutable Git objects without running tests
or querying CI. Completion records follow both approvals and are outside that
test-only review boundary. Fresh automatic CI at the final HEAD is still required.

### Preserved evidence and remaining blockers

The original caps/usage selector reported
`86 passed, 110 deselected in 939.90s (0:15:39)` at
`97b9e1c07149a7f85e9e33a85cb5d6b15dd99a96`. The reference-drift fixture and
stale evidence-test-name corrections at
`e84761f3589cdade5ba0f9d066a490042cceaa86` received both immutable approvals
but were not rerun locally. This correction's two-case result is separate
evidence; it does not validate the full caps/usage or native-host selectors.
The earlier #639 and #638 records below remain historical.

This linked input-only path retains native call/token limits, live identity/wire,
Foundry usage/tariff mapping, native host, actual deployment and prepared-request
capture requirements. Even after all separately verified local preparation,
the four caps, billing, live-wire and native-host blockers recorded below remain
unresolved for the current pilot. All launch/full-220 flags stay false. No live
receipt or new capability evidence was produced.

`im-not-ai-en` was applied to the English records to preserve exact commands,
SHAs, counts, timings and the distinction between hosted failure, local
correction evidence and prior unrerun fixes. Existing Git identity
`hyeonsangjeon <wingnut0310@gmail.com>` is unchanged, with no attribution
trailers or prohibited Git operations. No Azure/HF/OIDC, provider/model/client,
grader or paid execution, Project edit or merge action occurred. This record
stops at pre-merge facts.

## Historical PROJECT5-GPT56-RUNTIME-CAPS-USAGE-RECEIPT

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
