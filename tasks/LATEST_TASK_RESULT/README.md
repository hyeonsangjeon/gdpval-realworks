# Latest task result

## PROJECT5-FIRST-RETENTION-RESULT-INTAKE

The offline result-intake contract passed at
`e1206a704d649aac18d029670029def4c70fc18e`: 1 collected, 1 passed in 8.03s,
exit 0, with no skipped case. The fixture-only correction recognizes the real
path guard's refusal in the member/marker namespace-swap cases; production code
is unchanged. This pass uses real validators with synthetic retained records
and transport, not independently verified live result bytes. The earlier 2.75s
and 6.58s failures remain separate below. Neither was a failed inference, a
grade, or evidence that the actual retained result is invalid. Only these
completion records changed after the new invocation.

Branch `b/codex-retention-result-intake-20260930` starts at exact producer/main
`e355faf9a6212175a288e8473968915ffb2408d0`, tree
`5e031758a309af635c3ac6aeaec33d16a9da98ec`. The leader supplied all 10 passing
checks at PR706 head `67b08ba1ab302525dedf1a2fb01cbe97bc5330fe`,
[review 5363998321](https://github.com/hyeonsangjeon/gdpval-realworks/pull/706#pullrequestreview-5363998321).
That review does not approve the new reader. Earlier branches/worktrees and
`wip/local-main-preserved-20260719` remain untouched. Previous failures and the
separate entrypoint regression remain in the
[immutable PR706 record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/67b08ba1ab302525dedf1a2fb01cbe97bc5330fe/tasks/LATEST_TASK_RESULT/README.md).

### Supplied successful producer observation

The leader directly read [run 36696961231, attempt 1](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36696961231/attempts/1),
[execution job 109837605787](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36696961231/job/109837605787).
At `2026-09-30T10:58:12.8033229Z`, its final receipt reported `status=succeeded`
for `3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1`, request
SHA256 `ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68`,
with `cleanup_confirmed=true`, `remote_terminal=acknowledged`, `grade=null`,
`grading_launched=false` and `invoice_complete=false`. The job and workflow
succeeded at the producer source above.

This is a produced inference outcome, not a score or independent verification
of retained bytes. No actual terminal/output revision or payload was read in
this task. The producer, this later reader and any historical input observer
have distinct identities; the historical observer was not invoked, and original
inputs were not reattested. The supplied facts are recorded here, not on the
leader's unavailable local M4 volume. Inference was not replayed or reapproved.

### Implemented contract and limits

The new `batch-runner/codex_retention_result_intake.py` has an inert default and
an explicit read mode for only this producer/request/cell/run/job. A bounded
auth/extreme-reasoner decision preceded the small `verify_terminal` extension:
an exact frozen `TerminalExpectation` may be supplied only with `document=None`.
It grants no authority. Original callers still hash the whole document and use
its source head. Static AST comparison preserved every existing terminal
predicate and return field, plus the producer snapshot, admission and CLI code.

Discovery uses only the fixed terminal path on the existing inference ref and
pins its `last_commit.oid`. An explicitly supplied immutable terminal SHA is
also supported. Control/object readers then verify terminal, claim, output,
hashes, sizes and write history at immutable revisions. Retained authority must
match the fixed request/run/job/reviewer/environment and hash-only job-origin
schema; that consistency check is not fresh signed-token authentication.

Supported payload roles are `step2_inference_results.json` up to 8 MiB,
at most 128 selected-task `deliverable_files/<task-id>/...` files up to 64 MiB
each, and optional `cost_ledger_condition_a.jsonl` up to 8 MiB and 10000 rows.
An empty bound ledger is allowed; it does not establish zero cost. Aggregate
payloads are limited to 128 MiB, each control record to 128 KiB. Existing
120-second transfer and 30-second request limits remain unchanged. The reader
uses the real result fingerprint, deliverable-byte and ledger validators.
Missing or partial accounting stays distinct; grade remains null and invoice
completion remains false. No grader or live execution path is added.

Publication requires a fresh private directory, rejects collisions and unsafe
paths, and writes through caller-held directory descriptors. Readback precedes
the final evidence-only record. That record requires consumer readback and does
not assert readiness. A separate hash-bound successful receipt is returned only
after final readback, fsync and identity checks. An ambiguous post-link failure
retains partial evidence and refuses reuse. The reused SDK caches have fresh,
held roots and containment checks; they are pathname-based, not FD-confined
against hostile concurrent directory replacement. These are implemented rules,
not a claim that every regression below completed.

Production SHA256 values are identical at all three tested heads:

- Reader: `df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196`.
- Terminal-verifier module: `8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c`.

These identify new bytes, not source approval. Workflows, runtime, grader,
model/budget settings, compiler/preparer, the registered 8 cells, the original
30 cells and their pins remain unchanged. No real credentials or original
private payloads were used. Every tracked byte outside the test and two completion
records still matches `9c34db608209a084b61b18fdbeea067634028e36`. The corrected test
SHA256 at `fdfb9b2757da9b164caf6985bd6155a48aaa6c0b` was
`14a2e3ecd89c16e4fee4a3e89dc078a54243cf4d841bff6fae9d952fdd119053`;
at the new tested head it is
`aae70721d354bb921a2f60c869440567e45b2eb35ed580d58c9112a08477eacd`.

### Three separate offline validation observations

From `batch-runner`, the same isolated command ran once at each tested head:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -p no:cacheprovider --tb=short -s \
  tests/test_codex_retention_result_intake.py::test_first_retention_result_intake_is_immutable_bound_and_read_only
```

At `9c34db608209a084b61b18fdbeea067634028e36`, the initial result was 1 collected,
1 failed in 2.75s, exit 1; no skipped case. Log SHA256:
`cd94b1a1d5b7b906722801e9bcb179a0f9237198d4d6bd7d307b0ef5d0ed516f`.
Static syntax and import checks confirmed that all 22 added guard targets were
present before the run.

The selector reached whole-document/expectation equivalence, exact-type and
early binding refusals, inert default behavior, and a valid missing-accounting
intake with final readback and a hash-bound receipt. The terminal/object/result
and deliverable validators were real; retained producer records and transport
were synthetic. This was not a read of the actual successful producer's bytes.
The reached no-effect checks confirmed no remote writes or protected execution.

The next case failed at test line 277 while `verify_terminal` line 683 required
canonical equality between the stored receipt and `project_cost_receipt`.
The safe refusal is `retention_accounting_mismatch`. Static source inspection
identifies the differing field: raw `CostReceipt.as_dict()` supplies
`runtime_cost_usd=0.0`; `_measured_amount` projects that placeholder under
`partial` to `null`. The real producer `_snapshot` already stores the projected
receipt, whereas this synthetic fixture stored the raw one. The validator was
not weakened.

Partial-accounting completion, empty-ledger, absent-terminal discovery,
corrupted-source/request/cell/object, authority/history, path/private-state,
cache-escape, collision/symlink, readback-tamper and interrupted-publication
assertions after that line were not reached in the initial invocation. Their
presence was not runtime evidence, and that failed partial run was not an
integration pass.

The follow-up adds only `partial = ci.project_cost_receipt(partial)` after the
positive `CostReceipt.as_dict()` construction and before `ResultHF` stores it.
It uses the same real projector as `_snapshot`; canonical equality, measured-zero
semantics, negative-case construction, guards and all production code are unchanged.

At `fdfb9b2757da9b164caf6985bd6155a48aaa6c0b`, the one authorized follow-up reported
1 collected, 1 failed in 6.58s, exit 1; no skipped case. Log SHA256:
`79335f1d3ba605f9012f6013494a81c0a7e09ba688ec3a3eb0b17bfd879b62a0`.
All earlier assertions completed, followed by projected partial-accounting,
empty-ledger, missing-terminal discovery, source/request/cell/object corruption,
authority/history/origin, private-state/path/cache-escape, role-bound and
collision/symlink/traversal assertions. These used real validators with synthetic
retained records and transport, not the actual producer's retained bytes.

At that head, the first `member` namespace-swap read at test line 396 raised
`core.reference_integrity.ReferenceIntegrityError` through
`ghcp_vm_input_bundle._write_no_clobber` / `check_parent` /
`_reject_symlink_components` (lines 237, 229 and 78). The test had moved its own
output directory aside and created an empty replacement, so the nested parent
was missing. The path guard wraps `FileNotFoundError` in `ReferenceIntegrityError`;
the expected exception tuple at test line 395 does not include that class.
Static ordering places this refusal before the writer's temporary-file creation.
The member case's post-refusal byte/no-marker/reuse checks were not reached;
neither were marker-swap, altered-readback, post-link fsync/readback or final
no-effect assertions. Work stopped after that failure; the correction below
was separately authorized. No push or PR followed either failed invocation.

This follow-up imports `ReferenceIntegrityError` from `core.reference_integrity`
and adds it to the existing refusal tuple only for `member` and `marker`, which
both use the same path guard. The `altered-readback` tuple and the distinct
post-link fsync/readback expectations are unchanged. Every post-refusal and
no-effect assertion remains, as does `partial = ci.project_cost_receipt(partial)`.

At `e1206a704d649aac18d029670029def4c70fc18e`, the one authorized invocation
reported 1 collected, 1 passed in 8.03s, exit 0; no skipped case. Log SHA256:
`ad50b9106f95457a826444617164d4372885bdb19a54928a0f979b170f95c701`.
It completed all earlier assertions and the member/marker namespace-swap checks:
empty replacement directories, retained original partials, no marker in either
namespace, original marker-phase deliverable bytes and refusal to reuse the
destination. Altered-readback and post-link fsync/readback checks also completed,
including evidence-only markers without success fields, retained deliverables
and reuse refusal. The final assertions confirmed the untouched outside sentinel,
no unauthorized outside files, no remote commits and no protected execution
effects. The validators and publication helpers were real; retained objects,
transport and injected failure conditions were synthetic. This is an offline
contract pass, not a read of the successful producer's actual retained bytes or
an inference, grade or invoice result.

### Remaining gates and provisional readout form

Immutable owner review and CI of the new source remain. The prior PR706 review
does not approve this reader or its expectation extension. Actual retained
intake requires separate live-read direction using the existing selected
credential. The form below is blocked now, not permission to run it; the output
must be an explicitly selected fresh directory under an existing private parent.

```bash
python3 batch-runner/codex_retention_result_intake.py --read --discover-terminal \
  --expected-producer-source e355faf9a6212175a288e8473968915ffb2408d0 \
  --expected-request-sha256 ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68 \
  --cell-id 3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1 \
  --expected-reader-sha256 df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196 \
  --output "${RETENTION_RESULT_NEW_DIRECTORY}"
```

Even a future successful read grants no admission, replay or grading authority.
The subsequent fixed grader must separately verify the intake and its own
input/config/materialized-grader/source binding for one authorized grade.
No live intake, grade, HF/token/OIDC/Azure/model/paid call, workflow dispatch,
permission change, CI poll or successor cell occurred. The successful producer
cell remains consumed. Both failed tested heads remain distinct from this
offline pass; the source handoff grants no live-read, replay or grading authority.
