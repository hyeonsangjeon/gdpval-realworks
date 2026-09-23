# Latest task result

## Canonical pilot grading-input adapter: exact-main integration

`PROJECT5-CI-OUTPUT-TARGET-CHECK-2044` brings the reviewed local grading-input
adapter onto exact main `7c3238f18f1e32d76c8f326b29bf674f8364d4a0` with one
ordinary non-squash merge. The first parent is reviewed adapter head
`e3653758bff6dde3fadd6e72ff0af5b595566af7`; the second parent is that exact
main. Their merge base is `ea5dcc61c2beaad3a287d3d8dd064533ce33ed41`.
Only `CHANGELOG.md` and this completion record overlapped. No implementation
conflict occurred, and no runtime, workflow, grader or experiment control changed.

### Identity checks and review boundary

Direct index-to-parent comparisons preserve these four reviewed adapter blobs:

| File | Git blob |
| --- | --- |
| `batch-runner/codex_budget_pilot_grading_input.py` | `caf58212bbac277c57dc574ba8365819be35c83c` |
| `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml` | `948f3b591fdab246d11bc0a675a9aa1ac5b330f3` |
| `batch-runner/gpt54_codex_grading_input.py` | `663717a3bf17633cd09a551bb5cda33cb328f4ab` |
| `batch-runner/tests/test_codex_budget_pilot_grading_input.py` | `fa171f881342a4f572456b7e7fde09afd5f616e1` |

With those four files and the two completion records excluded, every tracked
file matches incoming main. That includes all publisher, HF-originals intake,
equivalent-path redirect, workflow and test bytes. Parent/blob comparison and
diff checking are the only integration validation: no tests, static counters,
earlier audits, native installation or grading were rerun.

Leader review `5289680397` and the reported ten applicable passing checks with
deploy skipped belong to `e3653758bff6dde3fadd6e72ff0af5b595566af7`, before
the base moved. They are not approval or checks for this integration head.
The new head still needs leader review and ordinary automatic final checks;
none was queried or awaited. The branch is frozen again after the normal push.

## Preserved grading-input unit

The original unit started at `ea5dcc61c2beaad3a287d3d8dd064533ce33ed41`.
Its implementation SHA is `f13c2fa156b4a80f43620a2a1b4cf0a25eca241a`; the
test-boundary correction and latest focused validation are at
`bc088ed8473dae362a76fd866763027f90d2a884`. The
[reviewed adapter record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/e3653758bff6dde3fadd6e72ff0af5b595566af7/tasks/LATEST_TASK_RESULT/README.md)
retains the full original interface and evidence.

[The adapter](../../batch-runner/codex_budget_pilot_grading_input.py) selects
one exact cell from the real `codex_budget_pilot.compile_pilot` output for
`budget_pilot_ci_20260923_01`. It does not admit arbitrary IDs by prefix or
materialize a campaign. The selected run/task/config and fixed grading plan
pass through the existing shared materializer's result fingerprint, terminal
row, artifact-byte, ledger, external-identity and atomic no-clobber checks.
The parent-comparison entry retains its original lookup and refuses pilot runs.
One comparison source pin was refreshed by the original unit; no member of the
active full-grader source closure or judge/model/prompt/rubric setting changed.

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

The caller supplies actual output HF repository/revision identity and an
external expected identity SHA. Original-input revisions, known Git/source
revisions and mutable names are rejected as output provenance. A caller
declaration/hash is not independent provider authentication. No publication
receipt is invented. Missing, changed, foreign, duplicate, unsafe or inconsistent
inputs refuse; existing/partial destinations are not adopted.

The new private tree retains deliverable and optional bound ledger bytes.
Only the derived result copy receives the existing documented provenance fields
and recomputed fingerprint. Source files, original status/cost/usage and missing
values remain unchanged. Terminal errors remain errors; pending or missing
results refuse. The bounded private preparation manifest reports grading
`UNRUN`. This is not a public completion envelope, grader invocation, output
publication, scheduler, admission lock or CI wiring.

### Historical offline evidence and native boundary

Tested SHA: `bc088ed8473dae362a76fd866763027f90d2a884`.
`PILOT_GRADING_PYTHON` named the existing isolated Python 3.10.12 interpreter.

```bash
env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$PILOT_GRADING_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_budget_pilot_grading_input.py
```

Result: `46 passed in 52.36s`, exit 0. Synthetic external identities, results,
artifacts and ledgers exercised the real compiler, CLI, shared validators,
fixed grader-config validator and local loader without credentials/network or
a judge. All 34 invalid-input cases assert installation is not reached.

Successful-copy cases use the existing test-only single-threaded rename double;
that is not atomicity evidence. The real `RENAME_NOREPLACE` case observed native
errno 22 (`EINVAL`) on NAS and refused with cleanup and unchanged sources.
Production retains the mandatory atomic operation with no fallback. Successful
native installation and live grade readiness are not established.

Earlier failures at `f13c2fa156b4a80f43620a2a1b4cf0a25eca241a` remain failures:

- The original family reported `11 failed, 34 passed in 51.51s`, exit 1.
- Only the 11 blocked copy cases were retried on tmpfs, reporting
  `11 failed, 34 deselected in 14.42s`, exit 1, with the same native refusal.
  The exact subset/scratch command remains in the immutable reviewed record.

No result is relabeled as a new run for this integration; the times are pytest
wall time, not model or grader latency.

## Preserved incoming publisher and redirect history

Incoming main includes the standalone private-output publisher. Leader review
`5289973671` covers source-integration head
`fa53c74460aa0c63516eb5d6a34f30f0e12213b9`. The leader now reports all nine
checks passed and incorporated it into the supplied main. All four earlier
failed jobs stopped during dependency installation before tests/checks.
Failed-job-only attempt 2 of `35848830781` and `35848830515` succeeded on the
unchanged head; no manifest, dependency pin or code changed. The earlier
Ubuntu 22 resolver-only result was not an Ubuntu 24 install or cause proof.

Publisher review `5289350726` at `0ff95ba41ce7ce961ee333bbcac9f8e3db539697`
and `66 passed in 109.70s` at `731ec479c742a11bcbeb6ce05d8b4f2da971ed3d`
remain scoped to the original standalone unit. It validates one finalized
canonical cell and only allowlisted generated deliverables, bound result,
available valid ledger and logical manifest. Default plan is local/no-token.
Explicit publication requires caller-approved existing private storage, exact
parent and absent cell prefix; a one-use private reservation precedes one
add-only CAS commit. The private receipt records the actual returned revision;
failed/ambiguous responses stay unresolved and cannot replay. No target is
selected, no grade-ready claim is made, and the public completion schema stays
unchanged. The accepted lifecycle gap persists: Step2 leaves bytes on the
runner, while CI uploads only completion metadata. This standalone publisher
is not yet wired, so hashes do not establish durable output preservation.

Redirect review `5289350480` applies to
`038f0fa911ec7971e69c03528385019de8c29b5f`; its selector reported
`28 passed, 63 deselected in 2.81s` at
`44e276163e8a241a0a146304c14c64d7437e6914`. The original input-check
`35841798539`, job `107118366778`, source
`ea5dcc61c2beaad3a287d3d8dd064533ce33ed41`, remains a 09:17:25 UTC
`hf_original_redirect_refused` observation at `hf_reference_1`, HTTP 307.
The separate unauthenticated HEAD at 09:25:38.658426 UTC returned 307 in
0.25118 seconds with no body or redirect followed. It established equivalent
member encoding for that HEAD response, not the uncaptured original CI Location.
The exact repository/revision/member guard, host restrictions and original
byte pins remain unchanged by this merge.

The [incoming immutable record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/7c3238f18f1e32d76c8f326b29bf674f8364d4a0/tasks/LATEST_TASK_RESULT/README.md)
preserves full publisher/redirect commands, bounds and earlier histories.
The GitHub release-metadata HTTP 403, initial upload HTTP 400/lost stderr,
later private draft `394272629`/asset `582945947` upload, and connected native
diagnostic `35817078746` remain separate observations. None was repeated or
queried here, and none is a pilot result or grade.

## Newer leader-supplied observations

The later completed model-free input-check `35847871634`, job `107138294292`,
on exact source `b0abe87275e3aa4d403732a6a8de8dacfe591c7e`, observed
`original_inputs_verified=true` at 10:19:28 UTC on 2026-09-23. All four pins
and the canonical 2,519,040-byte bundle matched SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Artifact `10744386417` contains the checksum-matched completion with
`verified_inputs_sha256=40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38`,
source `b0abe87275e3aa4d403732a6a8de8dacfe591c7e`, status `pending`,
`execution_requested=false`, `child_invocations=0`, and empty receipt/result/
deliverables. OIDC, identity and Execute were skipped. This supersedes only
the earlier pending access observation: it proves accepted inputs, not output,
pilot execution, durable publication or grading.

At 11:20:13 UTC, the separate NAS output-target observation matched the tracked
name fingerprint `88c9f1ba301718d90f8d59d8ddb681ee0c5e8ae7c2cbfd1b9ad246c10e15cccf`,
but the process-local `HF_TOKEN` and known handoff were unavailable. Zero HF
calls occurred; remote privacy, HEAD and HTTP status remain unknown. This is
local credential unavailability, not remote refusal, target approval or proof
of write/prefix readiness. No credential discovery or secret transfer occurred.

## Remaining work and controls

Remaining: this integration head's leader review/final checks; the separately
authorized implementation and later CI target-metadata observation; approved
destination and private output publication/wiring; integration/use of this
grading adapter with actual output provenance; ordered 30-cell admission,
cross-run deduplication/execution; and fixed grading. No target is approved by
these records. The leader retains live-run control.

Original bytes, campaign state/order, host policy, GPT-5.4/direct-v1/xhigh,
fixed grader and the 180-minute cell/30-minute attempt limits are unchanged.
No tests, credentials, data transfer, API, workflow dispatch, model or grader
were used for this merge. `experiment-report-en` and `im-not-ai-en` kept prior
tests/reviews, native refusal, accepted inputs and unavailable metadata separate.
No additional audit agent or CI wait was used.
