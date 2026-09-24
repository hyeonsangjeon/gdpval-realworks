# Latest task result

## PROJECT5-EPOCH02-PREP-1511

### Closed replacement epoch, preparation only

Implemented the independent `budget_pilot_ci_20260924_02` on a new worktree from
`e23d8acc1d032b3e937ec099324e3221334c9b4b`. No epoch02 HF setup, inspection,
admission, inference or grading was performed. The leader reported #671 review
`5300302955` at `2ff94450d52fb4b5c80cded3ba0505321bac3a2f` and all 9 checks
passed for the preceding withholding repair. That review does not cover this
epoch02 implementation. The existing extreme-reasoner approved its bounded
CI/HF/cost contract with conditions before edits, for code/offline preparation
only. This base and the local test SHAs are not an execution-source seal.

Old01 remains frozen at `2fe1c6925e6d76c03b85851046d52216bee74a16`, with
1 admitted failed/unretained A1 and 29 not run. Its run `35954811341`, job
`107490761123`, execution exit 1 and retention exit 2 (`unsafe_result_fields`)
remain historical. Known partial cost is USD 0.175163, with a null estimate and
`invoice_complete=false`; it is not an invoice total or a request count. The raw
result/ledger, precise child cause, unsafe field and current remote claim state
remain unavailable or unknown as recorded below. No claim was settled, adopted,
deleted, overwritten, replayed or used as an epoch02 comparison result.

The proposed new scope is 30 independent cells, not the old remaining 29.
If all new cells are later admitted, old1 plus new30 means 31 admitted cells
across two histories. The same five original tasks, A1/B1/C1/C2/B2/A2 order,
GPT-5.4/direct-v1/xhigh, SDK/CLI 0.147.0, 180-minute cumulative budget including
wait/recovery, 30-minute attempts, A4 fresh attempts, B/C retained continuation,
C-only feedback, one inference slot and one fixed grade per eligible result
remain unchanged. There is no automatic monetary cutoff or automatic launcher.

### Fixed refs and existing gates

The new closed registration preserves the old registration. It names only the
existing private dataset fingerprint
`a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44` and recorded
bootstrap `bfc7ae01ed14490817ceb7cb406adcb9bb95f557`. The fixed refs are
`pilot-inference-20260924-02` and `pilot-grades-20260924-02`. Their actual
existence and current state have not been observed in this task.

The existing grading entry accepts `pilot/inference-branch-setup` and
`pilot/inference-branch-inspect` for the inference ref. `pilot/branch-setup` and
`pilot/branch-inspect` now select the new grading ref. Each explicit setup
invocation handles one ref and its own private no-clobber root, reservation and
receipt. Four logical requests at most verify exact private bootstrap access,
establish genuine revision absence, create once with `exist_ok=false`, and
verify readback at the actual bootstrap. Generic 404s, inaccessible/public or
foreign targets, existing refs, redirects, changed parents and ambiguous
responses refuse. No automatic second-ref creation, adoption, deletion or replay
is available. Inspection remains two bounded reads and cannot acknowledge an
earlier setup. Default planning does not look up tokens or make network calls.

Admission reads, claim/output/terminal CAS writes and terminal-parent checks use
only the new inference ref. Claims, output manifests/receipts, terminal records
and grading provenance bind the campaign, actual source and designated ref.
A1 requires the recorded bootstrap and an absent prefix; later cells require
the exact immediately preceding canonical terminal at the same source. Grading
writes only its new ref. Neither route writes dataset `main`,
`pilot-grades-20260923` or old01 paths. Standalone publication retains its `main`
default; it cannot publish a ref-tagged retained snapshot through that default.

The approved result-validation/withholding implementation is byte-identical to
the base. Failed/stopped withheld outputs still retain only bounded metadata,
unchanged local artifact identities and partial/missing accounting; missing
results remain ungraded. Privacy, source, hash, byte, path, cleanup, no-clobber,
CAS and acknowledgment gates remain. Unacknowledged output cannot authorize a
terminal or next cell. Workflow inputs, permissions, concurrency, runtime/model
controls and fixed-grader pins did not change. HF tokens remain in short host
scopes, outside model/judge children. No coupled source pin required an update.

### Focused offline evidence

From `batch-runner/`, the new selector
`tests/test_codex_budget_pilot_epoch02.py` returned **34 passed, 1 failed in
80.16s**, exit 1, at `63afe729b9edab8c59f888fc86c4b4b642999b71`. The failed test
read the checksummed input envelope as a raw retention record, causing
`KeyError: files_sha256`. The test now uses the existing validating checkpoint
reader; production code did not change after that run.

Only the failed node,
`tests/test_codex_budget_pilot_epoch02.py::test_real_retention_predecessor_and_grading_cas_use_distinct_refs`,
was rerun at `d514d811374d80bb7e14ad051e10a21e402c5575`: **1 passed in 27.90s**,
exit 0. This is split evidence, not a fresh 35-case pass. Both invocations used
the existing Python 3.10.12 interpreter, a credential-free `env -i` environment,
HF offline defaults and private JUnit/log files. Pytest options were
`-q -o addopts= -p no:cacheprovider --tb=short`; finite timeout bounds were
600 seconds for the selector and 180 seconds for the failed node.

The compiler, checksum/byte checks, serialization, deadline, admission,
publication/CAS, terminal validation and grading binding/ref-CAS helpers are
real. Inputs/outputs, source/runtime capability, child execution and HF replies
are synthetic. Setup uses the installed SDK and real bounded HTTP guard with
fake responses. Grading-CAS tests do not establish native atomic installation,
judge readiness or a grade. The prior 25-pass withholding family was not rerun;
its original SHA/result remains below. Only completion records changed after
the failed-node test snapshot.

### Remaining authority and observations

New immutable-head review and CI remain. The leader must separately authorize
each live ref setup and bind its actual readback/bootstrap, one common final
execution SHA for all new 30 cells, and one selected cell before admission.
Checked live write/admission/publication, the first epoch02 cell, actual grading
host installation and one fixed grade, and complete new 30-cell results remain.
This task grants no live permission and does not reseal old01.

Dataset setup `35881609256` stays consumed. Old grading setup `35939410006`
remains acknowledged/branch_verified; original setup `35920355055` remains
unresolved/consumed. Earlier failed A1 dispatches `35941493214` and `35943806328`
remain separate from the admitted failure. Their detailed receipts, hashes and
partial costs below are unchanged. No live HF/model/grader/Azure operation,
payload transfer, workflow dispatch or CI polling occurred.

The full skill catalog was checked once. Experiment-design kept this a closed
replacement with unchanged axes and an explicit old1/new30 denominator.
Experiment-report-en and im-not-ai-en preserved the split test evidence, partial
cost and unknown-state limits. UI/animation and repo-readiness guidance did not
apply to this bounded internal routing/evidence change.

The sections below are historical records at their stated sources, not epoch02
execution authority.

## PROJECT5-FAILED-RETENTION-1339

### Future-code repair and frozen admitted cell

Added a retention-only opt-in for an already finalized failed/stopped cell whose
bound result is refused with the exact code `unsafe_result_fields`. It retains
only a bounded metadata manifest after all other validation passes. It does not
recover the admitted A1 or change its source, claim, clock, status or accounting.
One new offline selector returned **25 passed in 288.82s**, exit 0, at
`3276b32761579af86392909b6d472c9c7f8f604b`.

The branch starts from leader-supplied main and ACTIVE pilot source
`2fe1c6925e6d76c03b85851046d52216bee74a16`. The leader reported #670 review
`5299471328` and all **9 checks passed** for the preceding bootstrap/count
correction. That review does not cover this repair. The existing extreme-reasoner
returned **APPROVE-WITH-CONDITIONS, future-code implementation only**, before
the publication-path edits. No new-head approval, live recovery or reseal is
asserted here.

### Observed failure and evidence limits

The leader supplied A1 run `35954811341`, job `107490761123`, on that active
source. Real input intake, the full sandbox gate and private claim passed.
Execution exited **1 at 04:20:18 UTC**; retention exited **2** with
`unsafe_result_fields` at **04:20:21.6482243 UTC**. One paid child was admitted.
This is not another bootstrap, original-input or authentication diagnosis.

Verified public completion artifact `10789759614` has envelope SHA256
`570b0bc196a21efaa0a23123958a46d0ae2b2a52a16d19fb0661aae6d8b046e6`.
It reports `failed` / `child_nonzero_exit`, `timeout=false`,
`child_invocations=1`, `cleanup_confirmed=true`, `other_cells_not_run=29` and
`deliverables=[]`. Its partial receipt reports **55033 input tokens**,
**4387 output tokens**, **12544 cached-input tokens** and **3566 reasoning
tokens**. Known cost is **USD 0.175163**; the estimate is **null** and
`invoice_complete=false`. These are not invoice totals or request counts.

Only identities are available for the bound result and ledger:

- Result: **7460 bytes**, SHA256
  `c9313667c3890a1b4bc876d7bb771b41e430c2f595515c1a4bc0041e9fa1175b`.
- Ledger: **1838 bytes**, SHA256
  `116561470c73f4fbeae18a7db81c74947991e1b46f695411842f5bbd6153d93a`.

The raw bytes are unavailable here. Hashes neither preserve nor reconstruct
them. The child failure's precise cause and the unsafe field remain unknown.
The source trace confirms that `retain` calls `prepare` before
`TERMINAL_RESERVED`, the HF session and publication, so this retention invocation
published neither result nor terminal metadata. The refusal code is shared by
top-level, recursive and row/`failure_evidence` guards. The current remote claim
state is **not established**; no read or reconciliation was attempted.

### Guard-preserving behavior

Only retention opts into the new path. Standalone preparation/publication and
unsafe successful results still refuse. Eligibility requires failed/stopped
state, confirmed selected-cell cleanup and readable current result bytes matching
the recorded identity. Campaign/source/config/plan/host/input bindings, result
fingerprint and canonical identity, path/link/size limits, deliverable and ledger
bytes, and receipt/accounting checks remain mandatory. `_finish` rechecks a copy;
it never rewrites the original state. Recursive validation checks every branch's
depth before reporting unsafe fields, so an early field refusal cannot hide a
structure failure. No arbitrary exception or other refusal code gains a fallback.

The existing missing-payload path now also produces the withheld manifest:
`files=[]`, the existing missing-payload list, and exactly
`withheld={reason: unsafe_result_fields, artifacts: unchanged completion.artifacts}`.
The optional `withheld` field records local identities, not remote payload
availability. No rejected result, deliverable or ledger bytes are published.
The symmetric terminal validator requires exact fields, identities, failure
status, cleanup, empty published files and the existing bounds. Missing usage
remains missing; partial accounting, the execution reason and failed/ungraded
state are preserved. The public completion schema is unchanged.
Failed/stopped/missing outcomes remain in the 30-cell denominator.

Private-target and expected-parent checks, one-use reservations, CAS publication,
durable acknowledgment, remote-object checks and terminal confirmation remain
required. An unacknowledged output write cannot create a terminal record or
authorize advancement. Workflow, compiler, source pins, dependency/runtime pins,
model/budget/order controls and the fixed grader are unchanged.

### Single offline validation

Tested SHA: `3276b32761579af86392909b6d472c9c7f8f604b`.
Selector: `tests/test_codex_budget_pilot_failed_retention.py`.
Result: **25 passed in 288.82s**, exit 0. One invocation used the existing
Python 3.10.12 environment from `batch-runner/`; only the private JUnit path is
replaced below:

```bash
timeout --signal=TERM --kill-after=5s 300s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/results.xml tests/test_codex_budget_pilot_failed_retention.py
```

Private JUnit SHA256:
`af92c85b66dc61a3035090f6af56d25c0f5bdf5468e0d2ef875a173858301136`.
The cases use synthetic finalized outputs and the existing fake child/HF
boundaries with real JSON serialization, fingerprints, compiler, state/byte
checks, publisher/CAS and terminal validation. They cover failed/stopped field
variants, manifest-only publication without a private canary, unchanged files,
checkpoints and partial/missing accounting, safe success, unsafe-success and
standalone refusal, closed withheld identities/bounds, identity/source/path/byte/
cleanup/accounting/structure refusals, and lost-publication no-replay/no-advance.
Runtime/SDK admission and native execution are synthetic in the reused fixture;
this is not a native installation or live publication result. The cases do not
identify A1's lost field. No previous family or full suite was rerun. Only these
two completion records changed after the tested code/test snapshot.

### Required leader decision before any live use

The admitted A1 remains frozen at `2fe1c6925e6d76c03b85851046d52216bee74a16`.
Its unavailable raw files cannot satisfy the new byte checks. The reviewer
requires separate leader authorization for an exact reviewed future source and
a new campaign/source epoch with noncolliding claim/output identity and an
approved bootstrap/parent. Any paid execution also needs explicit authorization
and the common-source requirement. This patch implements neither epoch migration
nor settlement, adoption, replay, reconciliation or replacement of the old claim.
No clock is reset. New-head review/final CI, that source/epoch decision and any
separately authorized claim settlement remain before further live activity.
No next cell or grade is authorized. Complete 30-cell results remain unavailable.

Historical failed/consumed A1 runs `35941493214` (omitted input hash before
intake) and `35943806328` (accepted inputs, then missing `bwrap`) remain distinct;
those earlier runs admitted no paid cell. Dataset setup `35881609256` remains
consumed. Grading setup `35939410006`, job `107443765950`, was acknowledged /
`branch_verified` at **00:43:02.5104178 UTC**; original setup `35920355055` remains
**UNRESOLVED/CONSUMED**. None was replayed or changed. No HF API call, workflow
dispatch or CI query, model/grader request, Azure operation, original-payload
transfer or live claim operation occurred in this task. Git source/handoff
operations are separate from those live boundaries.

The full skill catalog was checked once. Experiment-design guidance preserved
the immutable-source/claim boundary and unchanged experimental axes.
Experiment-report-en and im-not-ai-en kept partial accounting, observed failure,
synthetic validation and unknown causes separate. UI skills and repo-readiness
were not applicable to this bounded code/evidence correction.

The sections below preserve earlier observations and their then-current limits;
they do not replace the active-source and admitted-cell status above.

## PROJECT5-BOOTSTRAP-COUNTS-1207

### Test-only correction and review scope

Updated only the three coupled expectations on the existing #670 branch,
starting at `9cee38e586c859c47be54fa7ef1bc1ed2110736c`:

- Setup routing now expects **10** excluded steps instead of **8** and explicitly
  includes the installation and full-capability steps.
- Output-target routing now expects **4** exact shared-admission matches instead
  of **2**, with the four intended step names fixed in the assertion.
- The three parameterized HF-originals failure-gate cases now expect the same
  **4** downstream steps instead of **2**, with exact names.

The shared predicates, setup exclusion, input-failure checks, prior-success
requirements and downstream admission/OIDC/retention assertions are unchanged.
There is no dynamic-count substitute, skip, xfail or helper framework. The
29-line workflow addition, capability helper, runtime/config/source pins and
`tests/test_codex_budget_pilot_bootstrap.py` remain byte-identical to the starting
head. No production change or new CI/cost review was needed.

The leader supplied source approval `5299044787` for that head's workflow/helper
scope and exact-head REQUEST-CHANGES `5299205667` for these test expectations.
Neither review approves this new delta. Main remains
`c463bc57139a484214264adc2a22c655cd33ca47`; no merge or reseal occurred.

### CI evidence and single local invocation

The leader reported eight applicable checks passing and pytest failing on the
starting head. Completed full CI run `35947002035`, job `107467086938`, recorded
**5 failed, 13763 passed, 61 skipped, 46 deselected in 2039.71s**. All five
reported failures were the three stale count assertions, including three HF
parameter cases. The CI-captured `hf_original_inaccessible`/403 belongs to a
synthetic negative-path fixture, not a new live HF or authentication failure.

Tested SHA: `629b3365c0621b070cddc6a9aae84a157ede2c14`.
The one permitted invocation used the existing Python 3.10.12 environment and
only these three selectors from `batch-runner/`:

```bash
timeout --signal=TERM --kill-after=5s 180s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/results.xml tests/test_codex_budget_pilot_output_setup.py::test_setup_workflow_routing_is_static_and_keeps_model_input_and_publication_closed tests/test_codex_budget_pilot_output_target.py::test_output_target_workflow_contract_is_static_not_an_actions_execution tests/test_codex_ci_hf_originals.py::test_hf_originals_actual_cli_failure_cannot_open_workflow_oidc_gate
```

Result: **2 passed, 3 errors in 1.96s**, exit 1. The two static workflow contracts
passed. The HF cases (`fetch`, `installed_check`, `None`) stopped before their
bodies ran: the existing `offline` fixture could not import `openai_codex`.
This is a local environment limitation, not an observed assertion regression
or HF call. Those three cases remain locally unvalidated. No dependency install,
test double replacement, assertion weakening or second invocation was attempted.
The private JUnit report has SHA256
`6e35511b5ad9dc6810076424573ac098acc1ec1a958ffe35aa108f41ecafe6bb`.
Only these two records changed after the tested snapshot.

### Preserved evidence and remaining gates

The original **11 passed in 0.99s** at
`771e79a56e1928d839dc50901b96011a91306fa9` remains a separate result; its
bootstrap selector was not rerun and is not combined with this invocation.
The failed/consumed A1 runs `35941493214` (omitted hash) and `35943806328`
(accepted originals, then unavailable `bwrap`) retain their histories below.
Acknowledged/`branch_verified` setup `35939410006` remains distinct from
unresolved/consumed original setup `35920355055`; no target or branch was replayed.
No paid cell has been admitted by these failed runs.

Remaining are new-head delta review, final CI including the three locally
unexecuted HF cases, explicit leader reseal and actual runner admission.
No CI query/rerun, full suite, live diagnostic, HF/model/grader call, Azure
management operation, permission change or paid action occurred. English
reporting/copyediting guidance kept the CI assertion failures, local fixture
errors and original bootstrap evidence separate. Experiment-design, repo-readiness
and UI/animation skills were not applicable: no experimental axis, new public
handoff or interface changed.

## PROJECT5-BUBBLEWRAP-BOOTSTRAP-1105

### Result and scope

Added the existing Ubuntu 22.04 bubblewrap bootstrap to the single-cell workflow
on a new clean branch from `c463bc57139a484214264adc2a22c655cd33ca47`.
One focused offline selector returned **11 passed in 0.99s**, exit 0. This
validates the workflow shell and failure routing with synthetic processes,
not an actual runner installation or native sandbox execution.

Only two workflow steps were added. After successful, verified execute-mode
intake, the first checks for `bwrap` and, if missing, uses the existing Ubuntu
`apt` package convention for one update/install sequence. It retains acquisition
retries and lock/network bounds, with 240/420-second command limits, five-second
kill grace periods and a 12-minute step ceiling; there is no outer retry loop.
The original `codex_bubblewrap_unavailable` prerequisite is unchanged. The second
step then runs the unchanged `scripts/diagnose_codex_sandbox_host.py` under a
two-minute ceiling before private claim, OIDC and inference. Only the helper's
successful full sandbox probe establishes readiness on that future runner.

Both added steps require successful prior steps, `execute=true`, all three
non-execution mode flags false and `steps.intake.outputs.verified == 'true'`.
Plan, input-only, output-metadata and setup routes skip this bootstrap. Neither
step receives HF/model credentials. Package, missing-binary and capability
failures propagate and block admission; no sandbox guard or host policy is
relaxed. The existing completion projection and token boundaries are unchanged.
No source binding needed an update, and the old #669 worktree was not changed.

### Confirmed live failure and preserved setup history

The leader supplied the following evidence; no run was queried or repeated here.
Corrected A1 run `35943806328`, job `107457243061`, attempt 1, used exact source
`c463bc57139a484214264adc2a22c655cd33ca47`. At
`2026-09-24T01:40:49.3370131Z`, explicitly selected HF originals were accepted
with `original_inputs_verified=true`: canonical archive **2519040 bytes**,
SHA256 `757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Intake succeeded at 01:40:53 UTC. The next prerequisite ran `command -v bwrap`,
emitted `codex_bubblewrap_unavailable` and exited 1. Private claim, OIDC,
execution and retention were skipped. This establishes unavailable `bwrap` on
that runner path, not an auth, provider or quota failure.

Earlier run `35941493214` failed before intake because the leader omitted
`input_bundle_sha256`. That dispatch mistake is not a code defect. Both
failed/consumed run records remain unchanged; neither admitted a paid cell.
The successful input gate was not repeated.

The leader separately reported grading-branch setup `35939410006`, job
`107443765950`, as acknowledged/`branch_verified` at 00:43:02.5104178 UTC.
Original setup `35920355055`, job `107382432896`, remains
**UNRESOLVED/CONSUMED**, with the original `grading_contract_refused`, null HTTP
status, exit 2 and unknown side effects. The later acknowledgment does not
rewrite the original receipt. Neither setup, target or branch was recreated,
inspected or replayed, and dataset setup `35881609256` remains consumed.

### Focused offline validation

Tested SHA: `771e79a56e1928d839dc50901b96011a91306fa9`.
Result: **11 passed in 0.99s**, exit 0. One invocation from `batch-runner/`
with a private temporary JUnit destination:

```bash
timeout --signal=TERM --kill-after=5s 60s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/results.xml tests/test_codex_budget_pilot_bootstrap.py
```

The private report has SHA256
`c990c5797635d842ddc7abc10552248ae937fb2c5bb4a3516349028cfe977dde`.
The tests execute the actual extracted Bash with fake `sudo`/package and
capability processes on an isolated PATH. They cover an existing binary,
successful installation, update/install failures and simulated timeout exits,
a still-missing binary after nominal installation, and capability refusals.
Structural checks cover ordering, all mode combinations, verified-input and
prior-success gates, credential boundaries, and downstream refusal, including
retention's `always()` guard. No real claim, OIDC, model or retention command runs.
Only these completion records changed after the tested workflow/test snapshot.
No previous 64-, 29- or 12-case family, full suite, package installation, native
connection diagnostic, original-input check or live test was run.

### Review scope and remaining authorization

An existing extreme-reasoner context returned a bounded pre-edit
**APPROVE-WITH-CONDITIONS** decision for this bootstrap, requiring the single
bounded package sequence and existing capability gate. It is not approval of
this new head or authorization for a live operation. Experiment-design guidance
kept the correction outside the experimental axes; English reporting and
copyediting kept live, synthetic and unmeasured evidence separate.

The leader supplied complete review `5297993636` and ten passing checks for
prior #669 head `d21b5fa508657cd94b326ebaa3c50c15b2b7683c`. Those cover its
source-trust, closed-diagnostic and branch-inspection scope, not this addition.
The prior inspection result remains **29 passed in 4.67s** at
`2066971d10bcad322420fdadd89fa71d1511318c`, with synthetic HF/source boundaries
and static workflow checks. The historical 28-pass, 6-fail/939-pass comparison
and targeted 12-pass evidence remains separately recorded below.

Remaining are new-head review and CI, explicit leader reseal of one common
source for all 30 cells, and a newly authorized actual runner bootstrap,
capability check and first admission/execution with retention and one fixed
grade. No existing cell clock is reset. GPT-5.4/direct-v1/xhigh, SDK 0.147.0,
180-minute cumulative/30-minute attempt limits, A4 fresh attempts, B/C retained
state, C feedback, one inference slot and the fixed grader remain unchanged.
No live HF/model/grader request, Azure management operation, setup replay,
workflow dispatch/rerun, source reseal or paid action occurred. CI was not polled
or awaited.

## PROJECT5-RUNTIME-SOURCE-INDEPENDENCE-0730

### Result and live evidence boundary

Corrected the eager external-source lookup on the existing #669 branch,
starting at `2b64888cb422d7a5a9d0df847a063b8a84002b95`. One targeted offline
selector passed **12 tests in 17.92s** at
`3790e4d370f25700ea7a18d46233575135e4191b`, exit 0. Main remains the supplied
`02a9682747e371d8675d1d0afb63155f3c3bce82`; no integration or reseal was made.

The leader reported comparison CI `35926036972`, job `107401241366`, on the
starting head: **6 failed, 939 passed in 1294.77s**. The eager `_root(TRUSTED_ROOT)`
call introduced an external-source dependency into every runtime Git command.
It preempted the six tests that deliberately make the old compiler unavailable
after preparation. The new selector restores their original provider-boundary
and post-validation HEAD-move assertions without editing those tests. The
initial **28 passed in 29.37s** at
`13032a864a115c0150f944e18aa277a1e212e541` remains separate evidence; it did not
establish runtime independence. Neither the 28-case family nor the 945-case
comparison run or full suite was repeated, and CI was not queried.

This repair does **not** establish the cause or side effects of the original
live grading setup failure, current HF branch state, or paid-execution readiness.

The leader supplied this observation from run `35920355055`, job
`107382432896`, on sealed source `02a9682747e371d8675d1d0afb63155f3c3bce82`:

- Plan succeeded at `21:09:59.868579 UTC`.
- Setup refused at `21:10:01.622976 UTC`, exit 2, with these reported fields:

  ```json
  {"outcome":"refused","reason":"grading_contract_refused","http_status":null,"grade_success":false,"inference_requested":false,"automatic_retry":false}
  ```

- Judge and grade publication were skipped. The generic refusal does not show
  which contract stage failed or whether a branch was created before receipt
  persistence failed. This task did not read, retry or reconcile that operation.

The grading-branch setup reservation remains **UNRESOLVED/CONSUMED**. The
leader's execution seal remains **BLOCKED_PRE_EXECUTION**, not replaced by this
branch or its tested SHA. Dataset setup `35881609256` and private bootstrap
`bfc7ae01ed14490817ceb7cb406adcb9bb95f557` remain valid and consumed; neither
setup may be replayed.

### Runtime independence and historical ownership mechanism

The supplied runtime contract is unchanged: once preparation has completed,
runtime lineage uses only the selected checkout's reviewed HEAD/tree, config,
input and receipt bindings. It must not call the external-source verifier or
require the old compiler directory to exist. The corrected `_git` validates
the actual command repository with `_root`, then uses `Path(TRUSTED_ROOT)` only
for lexical comparison. On mismatch it performs no `stat`, `resolve`, open,
existence check or `_root` call against the unrelated path and adds no trust
allowance. On exact equality it validates that trusted path before adding the
single exact `safe.directory` option. There is no fallback trust on failure.

All six runtime test nodes and their assertions remain byte-for-byte unchanged.
The r1/r2 cases reach the expected synthetic `ProviderBoundary`; the two
`head_moves` cases reach the injected move after real bundle validation and
then refuse at the intended lineage gate. The directly affected new trust test
also refuses foreign ownership with existing, missing and aliased comparison
roots. The unsafe-path test now selects its unsafe path as the command
repository; its no-Git assertion remains. No missing external directory was
created and no runtime fixture was redirected to the original compiler.

The original ownership reproduction remains a separate historical observation:

The grading entry's source-check path is `grade-run.yml`'s containerized `pilot-live` job, then
`codex_budget_pilot_grading.main`, `LocalTransport.require_source`, and
`gpt54_disposable_checkout._repository` / `_git`. The workflow installs an exact
global `safe.directory` entry. The helper deliberately uses
`GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_SYSTEM=/dev/null`, so that entry
cannot affect its commands.

A bounded pre-edit reproduction used real Git 2.34.1, synthetic temporary
repositories and Git's process-local `GIT_TEST_ASSUME_DIFFERENT_OWNER=1` switch.
It changed no filesystem ownership or real-repository permissions. Ordinary
Git with the exact isolated global allowance returned 0; the original hardened
helper returned 128 with a locally detected dubious-ownership refusal. An exact
command-local allowance returned 0; a foreign allowance remained refused at
128. The reproduction command exited 0. Raw stderr and temporary paths remain
private. This proves the compatibility mechanism locally, not that it was the
unreported stage in job `107382432896`.

Only exact lexical equality followed by trusted-path validation permits one
command-local `-c safe.directory=<canonical checkout>`; the same validated
command repository is passed to `-C`. Selected symlink/traversal roots and
wildcard/control-bearing trusted paths remain refused. No sibling, ancestor,
common-directory, wildcard, environment-selected or globally trusted path is
added. The ownership test switch exists only in test child processes, never
production configuration.

The fixed Git executable, stripped environment, global/system isolation,
hooks/fsmonitor/attributes protections, filter/include/partial-clone refusals,
no-lazy-transport policy, timeout and captured/redacted errors remain intact.
Source SHA, clean worktree, object type, tree paths/modes, manifest and pinned
blob checks are unchanged. The prior 28-case selector covered a synthetic
shallow clean commit without ancestor traversal; that case was not rerun.
No workflow or fetch-depth change was justified or made.
`require_source` still does not call `require_pinned_runtime`; no Python,
dependency or runtime-configuration change was made.

The only source-pin adjustment is the checkout helper's SHA256 in
`batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`:

- Previous #669 helper: `de40ae571d66635f121d2ca538f30114125c2fbf12e679db854c4ae46d6b9862`.
- Corrected helper: `0dbbab8911e1cba106745087aed471dca0a8b7f904058b4958df1e07864bb885`.

The genuine compiler validates that coupling. No fixed-grader source/hash
closure, model, prompt, rubric, judge policy, grading branch, inference-main
isolation, budget or 30-cell order changed.

### Unchanged CLI diagnostics and mutation limits

The source/root/receipt diagnostics introduced in the initial correction are
unchanged. Their original 28-case evidence is not a new CLI rerun. The real CLI
keeps refusal/exit 2 and these fixed local mappings:

| Boundary | `stage` | `reason` | `remote_mutation_possible` |
|---|---|---|---|
| Compile and validate reviewed source | `source_preflight` | `grading_source_preflight_refused` | `false` |
| Prepare private setup root and enter its lock | `branch_root` | `grading_root_refused` | `false` |
| Persist the final private setup receipt | `branch_receipt` | `grading_receipt_refused` | `true` |

For these local failures, HTTP status is null; grade success, inference request
and automatic retry remain false. The mutation flag describes **this invocation
only**: false does not prove an absent branch or unused reservation from an
earlier invocation; true is conservative, not proof of a mutation. Unrelated
outer failures retain their existing typed reason/HTTP context, or generic
`grading_contract_refused`, with stage and mutation possibility null. No raw Git
stderr, path, config value, token or arbitrary exception text is emitted.

Root/lock failure leaves any partial local state intact. Receipt failure after
a fake branch mutation preserves the real private local reservation and refuses
another invocation against that root before another fake session/mutation. The
initial selector included both an acknowledged fake creation and a lost fake response.
Neither case reconstructs the historical receipt or authorizes a live retry.

### Focused offline validation

Tested SHA: `3790e4d370f25700ea7a18d46233575135e4191b`.
Result: **12 passed in 17.92s**, exit 0. One invocation from `batch-runner/`
selected only the six reported runtime nodes and six directly affected
exact-trust/foreign-owner/unsafe-path cases. The private JUnit destination was
required to be absent before running:

```bash
timeout --signal=TERM --kill-after=5s 300s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -o junit_family=legacy -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/runtime-independence-results.xml \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-r1]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-r1]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-r2]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-r2]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-head_moves]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-head_moves]' \
  tests/test_codex_budget_pilot_grading_source.py::test_real_git_global_trust_is_ignored_but_exact_command_trust_works \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[symlink]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[traversal]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[wildcard]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[newline]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[control]'
```

Compiler and source-pin checks, temporary Git, preparation/runtime lineage,
bundle/receipt validation, repeated HEAD checks and path/ownership refusals are
real. Input fixtures and provider boundaries are synthetic. The four r1/r2
passes mean the intended intercepted provider boundary was reached, not that
auth or a model was called. Both head-movement tests prove the deliberately
changed HEAD is refused after the real validation hook, not before it.
No HF, model, grader, branch mutation, full-suite, native-install or live test
ran. The JUnit report remains private; only the two completion records change
after this tested source snapshot.

### Review scope and remaining gates

The same extreme-reasoner returned **APPROVE-WITH-CONDITIONS** before this
bounded Git-trust correction, clarifying the existing decision: validate an
actual command repository, but do not validate an unrelated compiler path merely
to select a trust allowance or require it to exist at runtime.
That memo covers the design, not approval of the resulting head. No new audit
loop was started. English reporting/copyediting guidance keeps the initial
28-pass result, supplied six CI failures, new 12-pass selector and original
unresolved live refusal separate. No current-head approval is claimed.

Prior #668 review `5296511923` and all ten passing checks apply to
`d97d250cfc1a6f2f6ad485d9bb44a8fa58d79227`, not this correction. Historical
results remain **64 passed in 47.42s** at
`f352eb87af8c794a677629229884f37061342535` and **5 passed in 3.20s** at
`f210a789e2a0afa889fd5261858fcbc0b402327f`; neither selector was repeated.
Accepted-input run `35847871634` and consumed dataset setup `35881609256` remain
separate observations, not paid-cell results or grades. The prior local native
atomic-install `EINVAL` refusal and successful rename-test-double cases do not
establish actual CI grading-host capability.

Remaining: leader review/final exact-head CI; separately authorized, checked
read-only reconciliation of the unresolved grading branch; an explicit source
reseal and live gates; actual grading-host native installation; the first paid
cell with retained output, one fixed grade, and all 30 recorded outcomes. There
was no real HF credential/API/read/write, branch creation, setup replay, payload
transfer, workflow dispatch, grant change, Azure/model/grader operation or CI
query/wait in this task. The original reservation and blocked seal are unchanged.
