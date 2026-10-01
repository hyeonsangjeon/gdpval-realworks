# Latest task result

## PROJECT5-LIVE-READOUT-TERMINAL-BOUNDARY

This change is diagnostic-only. The one authorized offline boundary test passed
at tested HEAD `8b60f526d3466993597875162eb987c2b77ab8d3`: 1 collected,
1 passed in 8.85s, exit 0. No concrete cause of the live refusal was established
by the bounded static trace, and no verification predicate was repaired or
relaxed. The live grade remains acknowledged and consumed; its numeric score
and grader accounting remain unread.

### Actual unpaid readout failure

The leader directly read
[run 36801558936 / attempt 1 / job 110176813572](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36801558936/job/110176813572)
at reader source `52e81f12c969771ae929c2456e06feb27d220f0f`. The workflow and
job failed. The supplied safe receipts on 2026-10-01 UTC were:

- `01:35:06.2898129Z`: source-free plan step 5 succeeded, `plan_only`,
  `stage=plan`.
- `01:35:09.8072326Z`: read step 6 failed, `outcome=refused`,
  `reason=retention_grade_readout_contract_refused`, `stage=grade_terminal`,
  `http_status=null`. Writer, paid and generic jobs were skipped.

The `grade_terminal` stage includes metadata lookup, terminal fetch, binding
and claim/history verification. The receipt does not identify which predicate
failed or establish successful terminal verification, a numeric score or usage.
It does not establish a credential failure, HTTP 403, missing retained data or
a bad grade. These are leader-supplied observations, not a new service read;
the bounded local check did not recover a separate saved full run log.

Work started in a new clean worktree from that exact reader source, tree
`a78f000f6c8792416667f38473a8df4c121b6b4f`. The tree matches prior PR710
reviewed HEAD `5116cc0d94bad5bcc9ffc2f0f11df7a8a17b9efa`,
[review 5373734862](https://github.com/hyeonsangjeon/gdpval-realworks/pull/710#pullrequestreview-5373734862),
with all 10 checks passing as reported by the leader. That review and CI
evidence do not cover this new diagnostic change.

### Closed diagnostics; unchanged verification

The trace was limited to `_ReadOnlyGrade.verify` through `output._metadata`,
`retained._control`, `_terminal_contract` / `_entry`, and `bridge._terminal`,
using the fixed writer and current reader sources. It found no concrete static
integration defect. The narrowly bounded CI/auth/privacy reviewer approved
the diagnostic scope before production edits and found no blockers in the
final diff. This is not immutable-head owner approval or live-read authority.

Only `batch-runner/codex_retention_grade_readout.py` and its test changed before
the tested commit: 43 and 189 added lines respectively. Caught terminal-stage
refusals retain the public reason, exit 2 and existing HTTP-status policy.
They now add `verification_reason` from a literal allowlist and
`verification_substage` from five fixed values: `metadata`, `terminal_control`,
`terminal_binding`, `claim_history` and `terminal_identity`.

A substage names attempted work, not a successful verification boundary.
In particular, `claim_history` includes the existing terminal reread, claim
bytes and object-history checks; it does not prove any of them succeeded.
Only an exact canonical `OutputPublicationRefused` with one exact string
argument matching an enumerated code is classified. Unknown exceptions,
subclasses, string subclasses, extra arguments and wrapped causes remain
`unclassified_verification_error`; unknown substages become
`unclassified_verification_substage`. The diagnostic helper never stringifies
errors or follows causes. It emits no arbitrary exception text or class name,
private value, path, payload, HTTP body, token or repository name.

All terminal/claim/file/source/config/task/run/hash/history/privacy predicates,
pins, roles, call order and payload gates remain. Verification still allows
1 pinned metadata call, 2 terminal downloads, 1 claim download and 5 path
checks. No metadata call, role, retry, permission, credential scope, workflow
route or execution authority was added. Schemas, the numeric projector,
writer/admission controls, bounds and cleanup requirements are unchanged.

### One offline invocation

The sole selector was
`tests/test_codex_retention_grade_readout.py::test_retention_grade_terminal_diagnostics_are_closed_and_read_only`.
It ran under CPython 3.10.12 / pytest 9.1.1 with a token-free CI-shaped ambient
envelope: `GITHUB_ACTIONS=true`, `GITHUB_EVENT_NAME=pull_request`,
`GITHUB_JOB=pytest`, `GITHUB_REF=refs/pull/710/merge` and synthetic
`GITHUB_SHA=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee`. Offline flags and the
existing network/process/credential guards remained enabled. Scoped local
cases restored that ambient envelope before the complete synthetic readout
CI setup. The 180-second outer timeout did not fire. No second invocation ran.

Real fixture serializers and terminal/claim/object validators were used with
synthetic transport and both defining-module Git simulations. Successful
synthetic terminal verification completed the exact metadata/path/control-read
counts without a grade-payload read. Nine real refusal cases covered private
target, terminal hash/history, writer binding, entry config hash, claim
hash/history, inherited claim history and file history. The terminal-hash case
corrupted the expected synthetic digest and exercised real byte-identity
validation; it was not a separate corrupt-download experiment.

The test also completed classifier checks and five simulated external-error
cases through the real CLI catch. It checked redaction of arbitrary secret-like
errors, unchanged HTTP 503 status, wrapped causes and an exception whose
`__str__` must not run. Every refusal kept exit 2 and the same top-level reason;
no score, terminal-verification or publication claim was emitted. Immutable
transport snapshots and final no-write/admission/judge/model/grader-effect
assertions completed. No successful validator verdict was substituted.
Grade-payload fetching/projection was forbidden. The unchanged full reader,
Step8 route, previous passing selectors, full suite and private 295.37s
integration were not replayed. The saved test log SHA256 is
`fae783326ada15ea35e7fd7b2793a96a5699b9a06a5365935d7a9d36ced39f4d`.

### Consumed grade and evidence limit

The actual grade remains the leader-observed acknowledged publication from
[run 36776393736 / job 110095775811](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36776393736/job/110095775811):

| Identity | Fixed value |
|---|---|
| Writer source | `29e0353f1539265b1741e71be894fedf9be32a8b` |
| Writer run | `36776393736`, `pilot-live`, attempt 1 |
| Grade terminal | `40712e0980cc05c31688fdbb98c693774fb90c0d` |
| Terminal SHA256 / size | `11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234` / 3119 bytes |
| Grade claim | `dec305d669e3ca2e53c7f7b9ebfbe7974d661350` |

Protected approval, claim, judge and publication succeeded in that writer run.
At `2026-09-30T21:09:56.1203808Z`, publication was acknowledged with
`grading_state=graded`; cleanup was confirmed, `invoice_complete=false`,
`inference_launched=false` and `automatic_retry=false`. These receipts did not
emit a numeric score. The full receipts, fixed cell/path/config/rubric and
separate producer/input identities remain in the
[immutable grade record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/5116cc0d94bad5bcc9ffc2f0f11df7a8a17b9efa/tasks/LATEST_TASK_RESULT/README.md#actual-completed-grade-separate-from-offline-reader-validation).

The accepted writer-recorded contract remains publication-derived, not
independent reconstruction of intermediate inputs or fresh provider
authentication. The materialized-input-fingerprint field remains
`status=unavailable`, `value=null`, `comparison=null`, with reason
`materialized_input_fingerprint_not_recorded`. The original fingerprint
`3441f200e6e4c53faf1b36f216283c80eee68e5d3e7d827587ba6c3135c7d200`, opaque
preparation digest and materialized grading input keep their distinct roles.
No missing comparison was invented or reported as true or zero.

### Earlier evidence remains separate

The earlier offline failures and passes are preserved in the
[immutable schema/diagnostic record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/5116cc0d94bad5bcc9ffc2f0f11df7a8a17b9efa/tasks/LATEST_TASK_RESULT/README.md#project5-readout-exact-schema-predicate)
and [CI-isolation record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/5116cc0d94bad5bcc9ffc2f0f11df7a8a17b9efa/tasks/LATEST_TASK_RESULT/README.md#project5-pr710-local-ci-test-isolation),
including their reached/unreached boundaries:

| Source | Separate observation |
|---|---|
| `98951a5b0d4c25d79f4f245de9dd32d2ba1a5c44` | 2 collected, 1 failed in 7.20s, exit 1; safe inner cause was not exposed. |
| `d32e519f074e3ca182338bc7e489aa43b2c796e2` | 2 collected, 1 failed in 7.60s, exit 1; synthetic terminal/claim checks passed before `grade_payload`. |
| `663423bbc7290233b6e818be8fcb14d20ec7e9b6` | Diagnostic-only: 2 collected, 1 failed in 7.82s, exit 1; real schema refusal before payload identity/ledger/projection. |
| `969a944895877e92b665af792d87efece68a9942` | 2 passed in 40.06s, exit 0; empty ambient environment did not cover inherited CI metadata. |
| `e2dc103de4269491a8c47ea964034ef8c798710e` | Actual CI run 36793228751 / job 110150692589: 1 failed, 13300 passed, 64 skipped, 46 deselected in 1487.18s; local-script isolation failure. |
| `d644fab1d08278300d44eae4904c9b9463804693` | 2 passed in 43.19s, exit 0; corrected test isolation under CI-shaped ambient metadata. |

None is rewritten as the present live refusal or as a live score. The
[immutable producer/intake history](https://github.com/hyeonsangjeon/gdpval-realworks/blob/5116cc0d94bad5bcc9ffc2f0f11df7a8a17b9efa/tasks/LATEST_TASK_RESULT/README.md#preserved-producer-intake-and-historical-evidence)
preserves successful inference run 36696961231 and verified retained intake run
36739260150 separately. Inference accounting remains partial: 10 recorded model
calls, known cost USD `0.409894`, `runtime_cost_usd=null`,
`missing_reasons=[call_reachability_unknown]`, `invoice_complete=false`.
These are not HTTP request counts, grader accounting or an invoice. Its original
`grade=null` / `grading_launched=false` receipt was not rewritten by the later
grade. The historical inference terminal and model-free UNGRADED grading parent
remain distinct from this consumed grade terminal.

The [immutable PR709 handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/4245b3f66d6cd341be197f0f1d38bd58a6cdfebd/tasks/LATEST_TASK_RESULT/README.md)
retains the earlier bridge/routing results and failures. The
[immutable PR708 record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ece7057a838e6a97d0c7441b2b2617f503a5adc2/tasks/LATEST_TASK_RESULT/README.md)
retains the NAS `explicit_hf_token_required` prerequisite refusal and prior
intake-fixture failures. No failed operation or consumed inference/grade was
replayed to repair an offline contract or obtain missing evidence.

### Remaining gates and preservation

New-head immutable owner review and CI are still required. A diagnostic read,
if needed, requires a new explicit leader instruction bound to that reviewed
source. This change does not authorize a retry of run 36801558936, a read of
other data, or any claim/judge/publication/inference replay. No live HF, OIDC,
Azure, model, grade, readout or dispatch occurred during this task; no private
payload, score or grader usage was read. There was no permission change,
Project edit or merge. The authorized Git publication is separate from
retained-store access.

Only the two completion records changed after the tested commit. Reporting
used `experiment-report-en` followed by protected `im-not-ai-en`, replacing the
stale current status while preserving historical detail through immutable
links. Earlier worktrees, `wip/local-main-preserved-20260719`, uncommitted NAS
refusal records and `/ai-work/copilot/retention-intake-private-20260930-2239`
were left unchanged. The leader's unavailable M4 files were not updated.
