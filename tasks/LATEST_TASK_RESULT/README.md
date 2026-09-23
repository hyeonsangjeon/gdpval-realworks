# Latest task result

## PROJECT5-GRADING-CI-FIXES-0458

### Scope and observed blocker

Repair only four directly coupled regressions on the existing #668 branch,
starting at `efb5be35ac9750bf03a784f9967f2d4e6341041d`. The supplied main remains
`50676dd63b948bc8fa329f9b24871af75fe29c54`; no integration or new branch was made.
The leader read CI run `35906432566`, job `107335172560`: **4 failed, 13695 passed,
61 skipped, 46 deselected in 2047.85s**, with the other eight checks passing.
Those are test failures on the prior head, not a dependency-install failure or
evidence of live grading. This task did not query CI or repeat that suite.

The same extreme-reasoner returned APPROVE-WITH-CONDITIONS before changing the
HF helper and freeze-checker behavior. This bounded decision covers the repair
design, not approval of the resulting head. No workflow edit was needed.
Reporting/copyediting guidance keeps the leader's CI observation, the earlier
focused result and the new five-test result separate.

### Concrete corrections and freeze coverage

1. `_hf_client` now resolves an unset response limit to the current
   `MAX_RECORD_BYTES` once at context entry. `_session` forwards that unset
   sentinel. Exact-integer/positive/file-ceiling validation is unchanged, as are
   the ordinary 8 MiB default and the explicit bounded grading-payload override.
   The original 64-byte/65-byte real-stream test is unchanged and again reports
   `hf_response_bytes_exceeded`, HTTP 200 and exit 2. A JSON parse failure is not
   relabeled as a successful observation.
2. The ordinal contract verifies all six bindings: five job environments and
   the approval step. Both generic CLI flag paths and self-retrigger forwarding
   remain asserted. The pilot jobs pass the declared defaults to the real host
   validator, which accepts ordinal 1 and refuses ordinal 2. No repeat policy
   changed.
3. The real `check_grader_hash_freeze.py` now recognizes exact paid job name
   `pilot-live`. The existing freeze workflow collects unfinished `grade-run.yml`
   runs and their job conclusions, then invokes that checker under
   `set -euo pipefail`. A new offline CLI regression uses the actual workflow job
   identity and verifies exit 1 for a hash-moving diff with skipped generic paid
   jobs and a queued, approval-waiting or active pilot job; success/failure/cancelled
   job conclusions still block while the workflow is unfinished. Runs with every
   paid job skipped and completed-run cases return exit 0, as does a hash-neutral
   diff.
   The hashed-path set, classification predicates and fail-closed handling are
   unchanged. This tests checker enforcement, not repository branch-protection
   configuration or a live paid run.
4. The rc=7 contract includes `pilot-plan` and `pilot-live` and the already-present
   generic pilot-exclusion conditions. Every existing generic approval,
   committed-partial validation, resume, publication and verification assertion
   remains. Added assertions require separate pilot dry/live routing, protected
   paid approval, restricted permissions, no generic dependency or inherited
   approval path, no automatic resume and no public pilot artifacts.

The fixed grader source/hash closure, prompt/schema/configuration, runtime pins,
workflow bytes, one-use grading semantics and `pilot-grades-20260923` branch
policy are unchanged. Inference HF `main` isolation is unchanged. No hash guard
was relaxed or source pin rewritten.

### Focused offline validation

Tested SHA: `f210a789e2a0afa889fd5261858fcbc0b402327f`.
Result: **5 passed in 3.20s**, exit 0. One command selected only the four reported
failure nodes and the single new freeze-enforcement regression. It ran from
`batch-runner/` with a finite process deadline and a cleared environment:

```bash
timeout --signal=TERM --kill-after=5s 180s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -o junit_family=legacy -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/results.xml \
  'tests/test_codex_budget_pilot_output_target.py::test_output_target_no_response_and_parse_failure_never_invent_status[size-200-hf_response_bytes_exceeded]' \
  tests/test_gold_ceiling_contract.py::test_workflow_carries_the_ordinal_through_to_the_grader \
  tests/test_grader_hash_freeze.py::TestTheJobNamesStillExistInGradeRun::test_no_other_job_is_gated_on_dry_run_being_false \
  tests/test_step8_grade.py::test_grade_workflow_rc7_requires_valid_committed_partial \
  tests/test_grader_hash_freeze.py::TestTheCommandLine::test_pilot_live_enforces_freeze_with_generic_jobs_skipped
```

The original connector result remains **64 passed in 47.42s** at
`f352eb87af8c794a677629229884f37061342535`. That family, the earlier
grading/retention/setup families and the full suite were not rerun. The original
local native installation returned `-1`, errno `22` (`EINVAL`), with CLI exit 2;
successful staging in that family used an explicit test double. This repair
does not validate native installation on the actual CI grading host. Only the
two completion records change after the new tested SHA.

### Review boundary and remaining work

The leader's #667 review `5294839155` remains scoped to
`cace64a840867c79362fa9aacd13af700ee9f363`; it does not approve #668 or this repair.
Accepted-input observation `35847871634` and consumed private setup
`35881609256` retain their separate scopes below. Neither was repeated. No live
claim, inference, output publication or grade is established here.

Remaining: leader review and final exact-head CI; one sealed execution SHA for
all 30 cells before payment; native atomic installation on the real grading
host; checked live grading-branch/write readiness; first admitted paid cell and
retained output; one fixed grade and all 30 outcomes. This task used no real HF
credential/API, branch creation, payload transfer, dependency installation,
workflow dispatch, setup replay, grant change, Azure/model/grader operation or
CI query/wait. The following wiring record is historical, not new validation.

## Historical PROJECT5-FIXED-GRADING-WIRING-0255

### Scope and interface

Connect the existing fixed grader to one canonical retained pilot cell, based on
exact main `50676dd63b948bc8fa329f9b24871af75fe29c54`. This is code/offline work:
no real HF credential/API call, branch creation, payload transfer, workflow
dispatch, inference, model, grader or Azure operation ran. CI was neither queried
nor awaited. This implementation still needs leader review and exact-head checks.

The mandatory extreme-reasoner decision preceded workflow/HF-write edits:
APPROVE-WITH-CONDITIONS. The same reviewer confirmed that a compiler-derived
grading pathname alias is a wiring correction, not a new grader policy. The
grading-engineer guidance and consolidated/stable specifications were applied.
Experiment-design guidance kept the inputs, five-task × A/B/C × two-repeat
denominator of 30, canonical inference order A1/B1/C1/C2/B2/A2, 180/30-minute
limits, A's four fresh attempts, B/C same-host continuation and C-only feedback
unchanged. Reporting/copyediting preserved the observation and proof boundaries
below. No additional semantic-audit wait was used.

The existing `grade-run.yml` accepts reserved `pilot/<canonical-cell>` and
`pilot/branch-setup` selectors through its existing inputs. Prefix routing is not
cell admission: the real compiler must select an exact registered cell. For a
cell, `inference_revision` means the explicitly selected immutable **terminal
confirmation** revision. The actual output revision is extracted only after its
terminal, claim, completion, manifest, object/history and cleanup checks pass.
It is not a moving HF HEAD, Git SHA, input revision or planned publication target.

`codex_budget_pilot_grading.py` defaults to local plan only. Its explicit host
phases are `setup`, `prepare`, `claim`, `judge`, `publish` and read-only remote
`reconcile`; these are not an automatic campaign launcher. Live workflow routing
requires explicit approval and the existing protected `grading` environment,
exact main/workflow/source identity and first attempt. Task, force, resume, chunk,
shard and repeat overrides are refused. The generic paid/resume/publication jobs
are excluded from this route. Inference completion-v1 still reports
`grading_launched=false`; it is not reused for real grading.

### Private branch, inputs and one-use grading

- The selected private repository is fixed by name SHA256
  `a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44`.
  All grading mutations explicitly name `pilot-grades-20260923`. Separate,
  explicitly directed branch setup can create that branch once from recorded
  bootstrap `bfc7ae01ed14490817ceb7cb406adcb9bb95f557`; an existing branch is
  refused, never adopted or reset. It does not create a dataset or touch the old
  public target. Ordinary preparation/grading never creates the branch.
- Preparation reads only the selected cell's manifest-allowlisted actual outputs
  and the registered immutable rubric parquet/selected references. Byte sizes,
  SHA256 identities, safe paths and the existing result/artifact/ledger contracts
  are checked before the canonical materializer. Original result, deliverable and
  ledger bytes are not mutated. Only the derived result receives the existing
  documented provenance augmentation and fingerprint. The identity document and
  receipt digest are derived from verified host publication/terminal evidence;
  they are not self-approved caller hashes or independent provider authentication
  of original inputs. A missing result or a validated error row stays ungraded.
- The actual execution host must complete the existing native atomic no-clobber
  installation before any grading claim or paid child. There is no fallback.
  Exact compiler-emitted source/config/input bytes, selected rubric references,
  renderer readiness, actual materialized grader-source/config hashes and output
  filename capacity are checked. Pilot aliases `pilot/cell-00` through
  `pilot/cell-29` come only from canonical indices; they do not impose a grading
  order. Canonical producer run IDs, experiment metadata, `--source-experiment-id`,
  Step8's `__` guard and fixed filename template remain unchanged.
- The fixed grading branch must be at bootstrap or a fully verified terminal
  grading tip. Unknown history or an active claim blocks mutation. A new absent
  canonical-cell prefix must win one expected-parent/CAS claim before precisely
  the compiled Step8 command is invoked. A local one-use reservation is additional
  to that remote guard. Existing claims/results, including unresolved or failed
  attempts, cannot be bypassed using another runner, path, source or run ID.
- After owned cleanup is confirmed, the connector validates the actual grade
  schema/source/task/config/rubric coverage, ledger run/digest binding and any
  existing task-progress checkpoint. One add-only parent-protected commit retains
  only those bytes and bounded terminal metadata on the grading branch. The
  manifest never names its own future commit; the private receipt records the
  actual returned immutable revision. Missing results/accounting remain explicit;
  partial/failure does not become a successful verdict, zero cost, complete invoice
  or known HTTP count. Raw SQLite, originals, native/auth state and logs are not
  published. No private payload or locator is uploaded as a public Actions artifact.
- A lost result acknowledgment leaves the local receipt unresolved. A bounded
  fresh read can separately verify an already committed, fully bound server result
  and permit an absent other cell's later claim. It does not recreate an
  acknowledgment, rewrite history, or rerun the judge/publication. Invalid/missing
  proof, uncertain cleanup, conflicting state or a failed read remains blocked.
  Inference HF `main` is never mutated by any grading-branch action.

HF tokens exist only in the selected host fetch/claim/publication scopes, not the
judge environment. Hub online mode is scoped and restored; the judge is HF-offline.
The existing bounded no-retry client is reused; original defaults stay intact,
with bounded payload reads permitted up to the publisher's existing file ceiling.
The only ledger exception is the exact compiler/Step8-derived grading cost run ID;
ordinary inference ledger validation is unchanged. The fixed grader source closure,
schema, prompts, model/settings, retries, dependency pins and source-pin files were
not changed. The isolated grading job uses the existing pinned grading image and
a 300-minute job ceiling around Step8's unchanged 14,400-second default plus a
14,520-second owned-child ceiling and private-save headroom. The inference job's
240-minute ceiling and all inference deadlines remain unchanged.

### Offline validation and native-install limit

Final tested SHA: `f352eb87af8c794a677629229884f37061342535`.
Selector: `batch-runner/tests/test_codex_budget_pilot_grading.py`.
Result: **64 passed in 47.42s**, exit 0. Only this new family ran; no previous
66/78/46/71 family or full suite was selected. A private JUnit report also records
the native boundary; it is not an Actions payload artifact.

```bash
timeout --signal=TERM --kill-after=5s 180s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3.10 -m pytest -q -o addopts= -o junit_family=legacy -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/results.xml batch-runner/tests/test_codex_budget_pilot_grading.py
```

The compiler, canonical materializer, Step8 entry/schema, fixed config, actual
byte/hash/path/no-clobber checks, private reservations, CAS and returned revision
binding are real. Source-host approval, retained outputs/rubric bytes, HF,
renderer and judge boundaries are explicitly synthetic. Cases cover no-network
plan, exact identities, metadata hashes without valid server evidence, native
refusal, claim-before-judge, duplicate prevention, immutable input bytes,
missing/error/partial evidence, private retention, lost acknowledgments and
inference `main` unchanged across grading-branch operations.

Successful materialization cases use a test-only rename double. The separate
actual-host call returned `-1`, errno `22` (`EINVAL`), with CLI exit `2`; no claim
or judge followed. This does not establish native installation on the actual CI
grading host. The earlier adapter's native `EINVAL` and `46 passed in 52.36s` at
`bc088ed8473dae362a76fd866763027f90d2a884` retain their original scopes.

Earlier observations in this new family are retained, not relabeled as passes:

- `47e417596cd352edb3329614cce9197b1df140b3`: the same family with a 600-second
  ceiling, without the JUnit options, returned **27 failed, 34 passed in 21.16s**,
  exit 1. The common preparation failure was a positional call to Step8's
  keyword-only `make_cost_run_id`; a separate error fixture left an extra synthetic
  deliverable. One failed-node diagnostic reproduced the preparation failure:
  `test_materializes_actual_retained_bytes_without_self_approved_provenance`,
  **1 failed in 2.95s**, 60-second ceiling, exit 1. That diagnostic ran with
  uncommitted test-only diagnostics based on the first SHA; it is not claimed as
  an immutable-head result.
- `7533fcaa0689c9099418dcda858af611a63dcca7`: the same family with a 180-second
  ceiling, without the JUnit options, returned **1 failed, 60 passed in 34.64s**,
  exit 1. The remaining fixture expected success when owned cleanup was deliberately
  unconfirmed; production correctly refused. The final family also adds explicit
  schema, full-rubric coverage and exact artifact-path refusal cases.

No real provider latency, model consumption, pricing, invoices, HTTP counts or
benchmark grades are established by these process/test timings. Code/workflow/test
bytes in the record commit match the final tested SHA; subsequent checks are
diff/blob comparisons only, not another test or audit run.

### Separate actual observations, review scope and remaining work

The leader supplied accepted-input run `35847871634`/job `107138294292` on source
`b0abe87275e3aa4d403732a6a8de8dacfe591c7e`: at 10:19:28 UTC all four pins and the
canonical 2,519,040-byte archive with SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3` were accepted.
Artifact `10744386417` has verified-inputs SHA256
`40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38`:
pending, execution not requested, zero children and no results/deliverables.
OIDC/identity/Execute were skipped. It is accepted input, not a pilot result.

The leader supplied private setup run `35881609256`/job `107251200144`, source
`053e2e33c22775e23e3c13a13773090613fc200b`, at
`2026-09-23T15:29:34.308692Z`: created, private=true, HTTP 200, stage
`created_metadata`, reason=null, actual bootstrap
`bfc7ae01ed14490817ceb7cb406adcb9bb95f557`, and the selected name fingerprint
above. Its reservation is CREATED/CONSUMED; setup must never be replayed. This is
destination selection and an actual setup observation, not a grading-branch write,
cell-prefix readiness or authorization for paid execution here. Native connectivity
`35817078746`, prior intake failures, private staging and the old public-target
privacy observation remain distinct historical facts below; none was repeated.

#667 review `5294839155` applies to
`cace64a840867c79362fa9aacd13af700ee9f363`. The leader reports ten applicable
exact-head passes/deploy skip and its inclusion in supplied main. Its split
48-pass reports before timeout/exit 124 plus `18 passed in 208.63s` remain at
`498c99d09f573707c2f9a9abd6afe8ac7b99e370`, not a single successful 66-case run.
No live claim, inference or output publication had run at that leader observation.
Neither that review nor the pre-edit design decision approves this new head.

Remaining: leader exact-head review/final CI and one sealed execution SHA for all
30 before any paid inference; explicitly directed grading-branch setup/write checks
and native atomic installation on the actual CI host; first canonical admission,
inference and private output publication; one fixed grade; then all 30 ordered
inference outcomes and fixed grading, including failed/ungraded/missing accounting.
This task authorizes none of those live operations and creates no new budget or
permission prerequisite. There is no carrying PR's future merge fact in this record.

## Historical record: PROJECT5-RETAINED-CELL-EXECUTION-0051 / TERMINAL-ADMISSION-POLICY-0122

The following retained record describes the earlier implementation and its then-current scope.

### Current scope

Wire the existing single-cell CI execution to private CAS admission, same-runner
output publication and terminal confirmation, starting from exact main
`053e2e33c22775e23e3c13a13773090613fc200b`. This task is code/offline only.
No real HF credential, request, claim, publication, setup replay, original payload
transfer, workflow dispatch, Azure, model or grader operation occurred. No CI
state was queried or awaited. The new head needs leader review and final checks;
the design decision and earlier approvals do not approve this implementation head.

The mandatory extreme-reasoner decision preceded workflow/HF-write-path edits:
**APPROVE-WITH-CONDITIONS**. The same reviewer closed the pending terminal-response
condition after the leader's `PROJECT5-TERMINAL-ADMISSION-POLICY-0122` decision.
There was no new audit loop or additional owner-budget approval requirement.
Experiment-design guidance kept the inputs, controls, order and denominator fixed;
English reporting/copyediting preserved the distinctions below.

### Admission, retention and confirmation

`codex_budget_pilot_retention.py` defaults to local plan/validation without token
lookup or network. Its internal `--admit` and `--retain` entry points reuse the
real compiler, existing CI bindings, private file helpers, publisher and completion
projection. They add no dispatch inputs, scheduler, service, arbitrary target or
grading entry. The fixed target is derived from the fingerprint-matched tracked
namespace and must have name SHA256
`a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44`.

1. Before inference, admission requires the exact private target, verified local
   inputs and pristine local cell state. At the same immutable parent, both the
   selected claim and output prefixes must be absent. The first canonical cell
   requires bootstrap `bfc7ae01ed14490817ceb7cb406adcb9bb95f557`. Later cells require
   a verified terminal record for the immediately preceding compiler-ordered cell.
   A tiny host-generated claim binds campaign/cell/order, source/config/input
   identities, actual CI run/job/attempt, workflow, host instance and expected parent.
   One add-only server-parent/CAS commit is verified before a private acknowledged
   admission receipt is written. The token-free CI `--execute` gate checks that
   receipt itself; a workflow condition alone is insufficient.
2. After the existing dispatcher finishes and owned cleanup is confirmed, the
   publisher uses the actual admission commit as its exact parent. It preserves
   the validated result, deliverables and valid ledger bytes. Failed/stopped cells
   without a result may retain only an explicit failure manifest, with missing
   result/ledger/usage still missing and `grade_ready=false`. The standalone
   publisher still refuses missing results by default. A narrow dispatcher fix
   binds an already written valid result on timeout without changing its stopped
   status, original deadline, bytes or accounting.
3. Only acknowledged publication with a durably saved private receipt and verified
   immutable output objects may produce a terminal confirmation. That confirmation
   is one CAS commit against the actual output revision. It binds the claim,
   existing output manifest, completion/status/cleanup and byte identities; it
   does not name its own future commit. No Git SHA or input revision is used as
   an HF publication revision.

The server terminal state, not delivery of its response, is authoritative for
**only the immediate successor**. A bounded fresh read checks the terminal,
claim and output manifest at their immutable commits, plus provider Git/LFS object
metadata for the already verified output bytes. It does not redownload generated
payloads. Per-run instance hashes may differ; each writer's own plan/run binding
and the common host policy must validate. Unknown tips, partial markers, foreign
identities, changed bytes and unverified hashes refuse.

A lost terminal response remains unresolved in the original local receipt. The
next runner writes a separate verified-server-state observation without claiming
that the prior writer received an acknowledgment. There is no acknowledgment-of-
acknowledgment chain. Ambiguous **output publication**, absent/invalid confirmation,
unconfirmed cleanup or a failed reconciliation read remains blocked. The successor
must still win its own absent-prefix/CAS claim. The same claimed cell cannot be
re-admitted on a new runner, skipped, replayed or given a new clock. Failed/stopped
rows are not changed to success. Missing/partial accounting is not changed to
complete accounting or zero cost. A local reservation remains distinct from the
durable remote claim.

Admission and retention have separate HF-token steps and short online scopes,
using the existing 30-second request and 120-second operation bounds, a 130-second
process limit plus five-second kill grace, and three-minute steps. SDK retries and
debug output remain suppressed. Execution refuses input/output tokens, and the
child launcher strips them. Ordinary plan, input-check, historical inspection and
setup retain their existing modes. No setup or old public dataset is touched.
Private receipts/locators/payloads do not enter the public artifact; only the
unchanged allowlisted completion envelope is uploaded. Safe retention CLI output
contains closed metadata, not raw errors, paths, URLs, credentials or native state.
Observed privacy and CAS do not atomically lock repository visibility.

The global concurrency guard, reviewed-main/attempt-one/source gates,
`contents:read`, 240-minute job ceiling, 180-minute cumulative/30-minute attempt
limits, A's four fresh attempts, B/C same-live-host continuation and C-only feedback
are unchanged. The canonical order remains A1/B1/C1/C2/B2/A2 for each of five tasks;
the denominator remains 30, including failed/stopped/missing outcomes. No automatic
30-run launcher or grading is added. Dependency/runtime/model/grader settings and
the active grading source pin are unchanged.

### Focused offline validation

The only selected family was
`batch-runner/tests/test_codex_budget_pilot_retention.py` (66 new cases, not the
earlier publisher family). The command used the existing Python 3.10.12,
pytest 9.1.1 and huggingface_hub 1.23.0; no dependency install/resolution ran.

```bash
timeout --signal=TERM --kill-after=5s 480s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_retention.py
```

At `a0c39e042b93ac2938c6f18d97693d2b0cc5091a`, the invocation ended with
**`66 errors in 4.03s`**, exit 1: the imported fixture required an absent
`openai_codex` package, so no test body ran. A test-only correction blocks the
repository's native/model/auth constructors without requiring that package and
supplies explicitly synthetic pinned-version metadata. Production pins and
execution checks were not relaxed; no native installation was established.

Corrected tested SHA: **`498c99d09f573707c2f9a9abd6afe8ac7b99e370`**.
The same selector emitted **48 passing case reports**, then reached its
480-second process limit, exit **124**, without a full pytest summary. It is not
a successful full-family command. Only the 18 unfinished cases were then selected
at that same SHA, with the same offline environment/options and a 300-second limit:
**`18 passed in 208.63s (0:03:28)`**, exit 0. The completed cases were not repeated.
This is split evidence, not an invented single `66 passed` invocation. The
process/test times are not model latency or changes to any CI/model budget.

The remaining-only selector used these explicit nodes in the same file:

```text
test_retention_invalid_predecessor_or_same_cell_never_advances[source]
test_retention_invalid_predecessor_or_same_cell_never_advances[manifest_hash]
test_retention_invalid_predecessor_or_same_cell_never_advances[output_bytes]
test_retention_invalid_predecessor_or_same_cell_never_advances[claim_bytes]
test_retention_invalid_predecessor_or_same_cell_never_advances[acknowledged]
test_retention_invalid_predecessor_or_same_cell_never_advances[unknown_tip]
test_retention_invalid_predecessor_or_same_cell_never_advances[read_failed]
test_retention_invalid_predecessor_or_same_cell_never_advances[same_cell]
test_retention_unconfirmed_cleanup_and_changed_output_refuse_before_network
test_retention_output_rechecks_private_identity_and_exact_admission_parent
test_retention_raw_errors_are_redacted_and_no_response_status_is_not_guessed
test_retention_target_fingerprint_refuses_before_credential_or_network
test_retention_current_byte_mismatch_refuses_before_publication
test_retention_conflicting_modes_refuse_before_token
test_retention_workflow_token_scopes_and_existing_controls
```

The real compiler, dispatcher/deadline, publisher, file/hash/no-clobber/CAS and
completion logic ran behind fake HF/child boundaries and synthetic input provenance,
CI/source capability and SDK-version metadata. Cases cover claim-before-child,
token isolation, strict canonical order/private/parent/duplicate refusals,
unchanged bytes, failed/stopped/partial/missing accounting, actual fake-returned
commit binding, cleanup/publication failure, and lost terminal response with valid
server proof admitting only the successor. Socket/process/auth/grader and real
HF boundaries were blocked. No original inputs or native SDK were exercised.

The source, workflow and test bytes in the documentation head match the corrected
tested SHA. Diff/identity checks also confirm unchanged dependency, backend-CI,
fixed-grader/shared-materializer and profile-control files. Five older test files
received coupled fixture or workflow-guard/token-scope updates; those families and
the prior 78/66/46/71/31/19 families were not rerun. No full suite, live check,
additional audit or CI wait ran.

### Separate observations and review scopes

The leader supplied actual setup success from run `35881609256`, job
`107251200144`, on exact source `053e2e33c22775e23e3c13a13773090613fc200b`:
at `2026-09-23T15:29:34.308692Z`, `outcome=created`, `private=true`, HTTP 200,
`stage=created_metadata`, `reason=null`, actual HF HEAD
`bfc7ae01ed14490817ceb7cb406adcb9bb95f557`, and candidate name SHA256
`a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44`.
The source gate bound the authenticated user/namespace, repository-level 404,
one private create and post-create metadata. Input/OIDC/Execute were skipped;
publication/model/grading were false and write/prefix readiness was not established.
The leader's durable setup reservation is CREATED/CONSUMED and must not be replayed.
The leader selected only that repository as the output destination. This is not
authorization for live writes/inference in this task or proof that retention ran.

Review `5293033879` applies to #666 at
`a45e5bb66c350ee2de432f0e9488d39ec3cabf34`. Its setup-family result remains
`78 passed in 58.90s` at `46d3bd32c3317e0e0cc41b4741c7087dd3584e42`, not live
setup evidence and not this implementation's validation or approval.

The leader supplied completed metadata run `35870090309`, job `107211610516`,
at 13:54:56 UTC on 2026-09-23. The historical target matched name SHA256
`88c9f1ba301718d90f8d59d8ddb681ee0c5e8ae7c2cbfd1b9ad246c10e15cccf`:
`exact_identity_match=true`, HTTP 200, `private=false`, HEAD
`6c7e07ee7365f145dfcf898263365b5c8c97b224`, `eligible_private_target=false`,
reason `private_output_target_required`, exit 2. Write access was not established;
publication was not authorized and no model was requested. Input transfer,
OIDC and model steps were skipped. This was a successful privacy observation
and intentional refusal, not invalid credentials or failure to fetch. It says
nothing about the new destination by itself; its later setup is a separate
observation above. The old public repository remains untouched.

The earlier NAS observation at 11:20:13 UTC made zero HF calls because the
process token/known handoff were unavailable. That remains local unavailability,
not remote refusal. No secret search/transfer or repeated observation occurred.

Leader review `5291537877` and nine passing exact-head checks apply to #665 at
`dc4f1bc2dc6ea59e73612ef89452f7de23f5740c`, included in supplied main. Earlier
review `5290860576` applies to `79c43ca20bac525d7ff77cc3e7a042ec81bdc2a3`.
The original inspection evidence remains `1 failed, 58 passed in 31.61s` at
`faa64ef15fce0e101c3911a092a312563fff2486`, then failed-fixture-only
`1 passed in 1.80s` at `668cdbed6574d0b0b458d87cda9e3ad87a1cbfed`; it is not
a new 59-case result. #664 review `5290860366` and ten applicable passes/deploy
skip apply to `054761aaa6e1ddae295840a1cf30ede36aa96f81`. Its
`46 passed in 52.36s` remains at `bc088ed8473dae362a76fd866763027f90d2a884`,
with successful test-double copies separate from native `EINVAL` refusal.
Publisher review `5289973671` applies to `fa53c74460aa0c63516eb5d6a34f30f0e12213b9`;
its `66 passed in 109.70s` remains at `731ec479c742a11bcbeb6ce05d8b4f2da971ed3d`.
Unchanged-head failed-install-only CI recovery did not establish the historical
index/cache cause or justify dependency changes. None of these approvals covers
the new retention code or this head.

Accepted-input run `35847871634`/job `107138294292` on
`b0abe87275e3aa4d403732a6a8de8dacfe591c7e` verified all four pins at
10:19:28 UTC on 2026-09-23 and the canonical 2,519,040-byte archive, SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Artifact `10744386417` carries checksum-matched
`verified_inputs_sha256=40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38`,
status `pending`, no execution/child and empty receipt/result/deliverables.
Native-connectivity diagnostic `35817078746` separately connected on
`0f0911b435d7f704db8e2f2131a00ade310d5c1f` with diagnostic defaults, not the
pilot treatment. Neither is a pilot result, durable output or grade.

The earlier GitHub metadata 403, HF redirect 307, separate HEAD observation,
initial upload 400/lost stderr and later private staging success remain distinct;
the original CI Location is still not reconstructed. Full prior commands,
identities and histories remain in the
[source record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/053e2e33c22775e23e3c13a13773090613fc200b/tasks/LATEST_TASK_RESULT/README.md)
and changelog, not relabeled as new validation.

### Remaining work

New-head leader review/final checks; separately authorized, checked live admission,
write/prefix and output-publication observations; the first paid cell; canonical
grading-adapter workflow wiring using an actual output revision and Ubuntu 22.04
atomic grading-input installation; all 30 ordered cell outcomes and fixed grading.
The code now supplies serial next-cell admission and private retention, but no
live claim, retained pilot output, executed pilot cell or grade was observed here.
There is no automatic campaign launch, model retry, setup replay or new target.
