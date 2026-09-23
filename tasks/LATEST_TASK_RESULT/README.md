# Latest task result

## Local grading-input adapter for one canonical pilot cell

This independent branch starts at exact main
`ea5dcc61c2beaad3a287d3d8dd064533ce33ed41`. It adds a local preparation entry
for one registered CI pilot cell, without publishing outputs or running the
grader. The implementation was committed at
`f13c2fa156b4a80f43620a2a1b4cf0a25eca241a`; the test-boundary correction and
latest focused validation are at `bc088ed8473dae362a76fd866763027f90d2a884`.
Later completion-record edits are not another test run or final-head approval.

### Interface and validation

[The adapter](../../batch-runner/codex_budget_pilot_grading_input.py) accepts
the exact registered campaign, selected cell and reviewed execution-source SHA.
It selects a member of the real `codex_budget_pilot.compile_pilot` output; it
does not accept a run ID by prefix or copy the 30-cell matrix. Compilation does
not materialize a campaign, inspect originals or require a live CI identity.

The selected one-task dispatch/config is passed through the existing fixed
grading-plan compiler, then its producer result role, one-task limit and local
materializer entry are adjusted for the cell. The judge/model/prompt/rubric
configuration stays unchanged. The shared internal seam retains all existing
result-fingerprint, terminal-row, artifact-byte, ledger-reference, external
identity and no-clobber checks. The parent-comparison entry retains its original
lookup and still refuses pilot runs. Its source pin was refreshed; no member of
the active full-grader source closure changed.

Example local invocation, with all paths and approvals supplied by the caller:

```bash
python batch-runner/codex_budget_pilot_grading_input.py \
  --campaign-id budget_pilot_ci_20260923_01 \
  --cell 02aa1805-c658-4069-8a6a-02dec146063a_A_r1 \
  --reviewed-source-sha "$REVIEWED_EXECUTION_SHA" \
  --inference-results "$CELL_RESULT" \
  --source-upload "$CELL_UPLOAD" \
  --inference-identity "$APPROVED_OUTPUT_IDENTITY" \
  --approved-identity-sha256 "$APPROVED_IDENTITY_SHA256" \
  --destination "$ABSENT_PRIVATE_GRADING_INPUT"
```

`source-upload` is the cell's upload root containing only the validated
`deliverable_files` tree. The optional ledger must match the existing result
reference and approved identity. Missing, changed, foreign, duplicate, unsafe
or inconsistent inputs refuse; an existing or partial destination is not
adopted. Invalid arguments produce closed errors without private paths or raw
exception messages. There is no execution, credential or network option.

The identity document uses the existing contract: `condition` remains `codex`,
while the A/B/C condition, task, repetition, settings, declared original inputs,
common host policy and reviewed source are bound by the compiler-derived
run/config/manifest/grading-plan hashes. The canonical producer run must match
the selected cell. The external expected SHA must match the identity document;
the document is not its own trust anchor.

For live use, the caller must supply the actual output HF repository and its
immutable publication revision. Original-dataset provenance, known Git/source
revisions and mutable revision names are rejected. This reader cannot establish
that a syntactically valid HF revision exists or authenticates output provenance.
The issuer remains responsible for the approved input/publication claims; a
caller declaration plus hash is not independent provider authentication. No
publication receipt is manufactured, and unmerged #662 code is not imported.

The existing installer creates an absent private tree with the result at
`batch-runner/workspace/step2_inference_results.json`, validated deliverables
under `batch-runner/workspace/upload/deliverable_files`, and any bound ledger
beside the result. Deliverable and ledger bytes are preserved exactly. The
original result is untouched; only its derived copy receives the existing
`source_repo_id`, `source_revision`, `source_identity_document_sha256` additions
and recomputed fingerprint. All other fields, task status, costs, missing/null
values and extensions remain unchanged. Terminal errors can be preserved as
errors with no successful deliverable; pending or missing results refuse.

The CLI returns a bounded private preparation manifest on stdout, including
source identities/hashes, the derived result identity and grading state `UNRUN`.
It contains no raw result content or absolute host paths. It is **not** the
public CI completion envelope. No grader config/source checkout, grade, output
publication, scheduler, remote admission lock or CI wiring is created.

### Focused offline evidence and native boundary

The single new test family uses synthetic results, artifacts, ledger bytes,
prepared fingerprints and external HF identities. The real compiler, CLI,
shared validators, fixed grader-config validator and local grading-input loader
are exercised. Network, credential access, subprocess launch, client creation,
rubric loading and grader construction are blocked. No original payload is
opened and no LLM judge runs.

Latest tested SHA: `bc088ed8473dae362a76fd866763027f90d2a884`.
`PILOT_GRADING_PYTHON` denotes the existing isolated Python 3.10.12 interpreter
from the private handoff, not a newly installed environment.

```bash
env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$PILOT_GRADING_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_grading_input.py
```

Result: `46 passed in 52.36s`, exit 0. This includes canonical A/B/C cells and
both repetitions, another canonical task, parent-entry compatibility and pilot
refusal, input/result/identity mismatches, changed/missing/unsafe files and
ledgers, existing/partial destinations, byte preservation and failed/partial/
missing accounting. All 34 invalid-input cases assert that installation is not
reached, so an unrelated OS error cannot satisfy their refusal assertions.

The successful-copy cases use the same test-only, single-threaded rename double
as the parent materializer's existing tests. All validation, file reads/writes,
private staging and byte comparisons remain real, but that double does not
prove atomicity under races. The separate native case calls the real
`RENAME_NOREPLACE`; on this host it observed errno 22 (`EINVAL`), refused without
a destination or staging residue, and left source bytes unchanged. Production
retains its mandatory atomic operation with **no fallback**. Successful native
atomic installation on the execution host remains unestablished by this run.

Earlier attempts are retained as failures, not folded into the pass count:

- At `f13c2fa156b4a80f43620a2a1b4cf0a25eca241a`, the same family command before
  the test-boundary correction reported `11 failed, 34 passed in 51.51s`, exit 1.
  The successful-copy cases reached the existing installer and encountered
  native errno 22.
- At that same SHA, only those 11 cases were retried with synthetic scratch
  files on tmpfs. Adding `--basetemp "$PILOT_GRADING_TMP/cases"` and
  `-k 'valid_a1 or valid_b1 or valid_c1 or valid_c2 or valid_b2 or valid_last_a2 or parent_compatibility or terminal_error or ledger_absent or ledger_null or missing_accounting'`
  reported `11 failed, 34 deselected in 14.42s`, exit 1, with the same native
  refusal. `PILOT_GRADING_TMP` was a fresh private directory created by
  `mktemp -d /dev/shm/codex-pilot-grading-input.XXXXXX`; this changed only test
  scratch storage, not the experiment host. No further filesystem probe or
  production portability workaround was added.

The correction changed tests only: it adopted the existing syscall-boundary
double, retained a real native refusal case, and strengthened pre-installation
refusal assertions. The old reader31/publisher66/HF71/error19/native71 families
and full suites were not run. These times are pytest wall time, not model or
grader latency.

### Prior observations and review boundaries

The leader supplied #662 FINAL-APPROVE `5289350726` at
`0ff95ba41ce7ce961ee333bbcac9f8e3db539697`, including its real Step2/ledger/CI-state
contract review. Its `66 passed in 109.70s` remains at
`731ec479c742a11bcbeb6ce05d8b4f2da971ed3d`. It covers a standalone private
publisher, not actual publication, output-target readiness or workflow wiring.

The leader supplied #663 FINAL-APPROVE `5289350480` at
`038f0fa911ec7971e69c03528385019de8c29b5f`. Its redirect-fix selector reported
`28 passed, 63 deselected in 2.81s` at
`44e276163e8a241a0a146304c14c64d7437e6914`. Its separate HEAD observation is not
a reconstruction of the original CI Location or a successful input transfer.
Both reviewed heads remain untouched; neither approval covers this adapter.

The leader's original HF input-check `35841798539`, job `107118366778`, at
`ea5dcc61c2beaad3a287d3d8dd064533ce33ed41` remains a refusal at 09:17:25 UTC:
`hf_original_redirect_refused`, `stage=hf_reference_1`, `http_status=307`.
Plan creation passed; OIDC, identity and model steps were skipped. That is not
evidence of invalid credentials. No input check or HEAD observation ran here.

The earlier GitHub input-check's release-metadata HTTP 403, owner-account
private asset upload, initial HTTP-400 upload with lost stderr, and connected
native diagnostic `35817078746` remain separate observations. Their detailed
records are preserved in the changelog and the
[prior source record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ea5dcc61c2beaad3a287d3d8dd064533ce33ed41/tasks/LATEST_TASK_RESULT/README.md).
None proves pilot execution, durable generated outputs or graded quality.

### Remaining work

New-head review and ordinary automatic final checks remain with the leader;
none was queried or awaited. Actual immutable-HF input acceptance, an approved
existing private output target and observed output publication, workflow wiring
of the publisher and this adapter, ordered execution of all 30 cells, cross-run
admission deduplication and separately directed fixed grading remain unfinished.

The original inputs, sealed NAS campaign and pending cells, reserved CI
campaign, gpt-5.4/direct-v1/xhigh settings, pinned host policy and 180-minute cell/
30-minute attempt limits are untouched. No workflow was edited or dispatched;
no permission/credential change, real-input transfer, model or grader run was
performed. Standing spend authority is unchanged; this is preparation, not
another budget-approval wait.

The grading-engineer baseline and `experiment-design` kept validation and fixed
controls intact. `experiment-report-en` and `im-not-ai-en` kept synthetic
evidence, native refusal, prior reviews and unknown live readiness distinct.
