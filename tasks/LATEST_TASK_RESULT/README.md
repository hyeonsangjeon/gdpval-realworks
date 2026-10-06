# Latest task result

## First callable F-derived grading executor

The draft adds a callable and CLI for the first registered V2 observation only:
`gpt54_time_budget_v1_v2_r1` / `sandbox_v2` / repeat 1 /
`02aa1805-c658-4069-8a6a-02dec146063a`. It consumes the accepted
`prepare_observation_grading` output and invokes its actual copied F Step8 once.
The implementation exists, but its executor assertions have no passing local
proof. Delivery remains HOLD; no real grade or observation was executed.

The work began in a new worktree and branch from accepted
`c051207c4033c97c4455215b1381aa88d25aef65`, tree
`da2f27bec5785db571ffd8caa20ddf2bd5a12ede`. The supplied reviewed basis is
the integrated consumer/preparation source from `2f7a7861a10b75946856c16d7fa5ffbef2b9b050`,
review `5421981543`. This does not approve the new executor. PR755 remains
untouched at conditionally reviewed `c766c3b80365d1ff4c7b1dc1e1a91bef569c7b9f`,
tree `b7ca9c4593db5b08aa08b778163940e8b7c1adaa`; its source or CI status was not
queried, and none of its unmerged adapter was borrowed.

### Source and admission boundaries

- Controller C is independently supplied as a full commit/tree and root. The
  helper checks its own and its imported controller-source bytes against that
  anchor, including final held-directory/source rereads.
- Observation runtime R comes from the independently supplied observation and
  its genuine registration. Its reviewed commit/tree is not inferred from C,
  preparation metadata or checkout HEAD.
- Frozen F remains `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
  `45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, with TEMPLATE
  `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
  Every copied F file and the exact prepared config bytes are rechecked. The
  unchanged whole-source helper hashes the materialized config and source that
  will execute; that fingerprint must differ from TEMPLATE. R is never used
  as the grader source.

`require_execution_direction(GradingExecutionBinding, ...)` requires an
independently supplied direction-file SHA-256. Its exact binding includes the
observation/input/result/preparation identities, C/R/F, actual config and
materialized hash, canonical paths, command/cwd, local execution-context digest
and attempt-store device/inode. The direction has integer `not_before` and
`expires_at` admission times. Missing, extra, stale or mismatched data cannot
authorize a child. A file-provided digest or preparation flag is not permission.

An exclusive file in an existing private 0700 attempt store is keyed only by
study/run/condition/repeat/task. Its file and parent directory are fsynced before
the first process effect. The claim is never removed or renewed after failure,
timeout, interruption, a copied preparation or a different output destination.
This is local protection within that independently named store, not distributed
or global once-only admission across arbitrary stores.

The adapter uses only `codex_budget_pilot.LocalTransport.process` as the existing
owned-child primitive, not its historical selectors, approvals or HF routes.
It invokes `source/batch-runner/step8_grade.py` with the exact prepared config,
`--source local`, one task, limit 1 and no force/resume/retry switch. F Step8's
14400-second default and the existing 14520-second child envelope remain
unchanged. They are grading semantics, not an extension of the study's
1200-second generation / shared 20-second cleanup policy. Cleanup uncertainty
cannot publish a successful terminal result or permit another attempt.

Only grading-specific ExperimentConfig metadata is installed, no-clobber,
inside the derived source after the claim. F implementation/config bytes and
the original F checkout remain unchanged. F Step8 also requires a genuine
canonical `source_repo_id` and full `source_revision` in the Step2 result.
Missing values refuse; a dataset or runtime revision is not substituted for an
inference revision. The tests declare these locators as synthetic values, not
as real publication or authentication evidence.

### One failed proof and a separate fixture correction

The one offline invocation at `362587b029d069f8a27226fbd37e60a6484649b0`,
tree `bc326cbcc6b16ed3b39e5d3596b98ba28904f50a`, reported **31 failed,
49 deselected in 132.68s**, exit 1. Every selected case completed with the same
failure in `_execution_case`: `execution_context_sha256()` read
`/proc/self/ns/user`, which this NAS host lacks, and raised `FileNotFoundError`
with errno 2. This happened before direction construction and executor entry.
The intended positive, refusal and nonrenewability assertions were not reached;
none may be counted as proved. No case passed or was skipped, and the outer
timeout did not expire.

The subsequent test-only commit `3642428f88e5d7a6f159be9978e3a6137d7f4bf1`,
tree `58074aae1c1a83c7f00d47ef8b821795dc305c7b`, adds 11 fixture lines for
explicit synthetic PID/mount/user namespace link values. The real context
hashing, direction/source validators and production unsupported-host refusal
are unchanged. Those corrected cases were not rerun. The post-proof delta is
this one test file plus CHANGELOG and LATEST; production bytes remain those
of the tested commit. The final records commit adds only the two records.

The invocation used Python 3.10.12, pytest 9.1.1, an empty credential environment,
offline HF flags and a 300-second outer limit with 5 seconds termination grace,
without `-x`. Genuine temporary Git roots and explicitly synthetic
input/result/config bytes were used. No successful source/hash/direction
validator was replaced. The process fake was not reached in this invocation.

Selector, from `batch-runner`:

```text
python -m pytest -o addopts= -p no:cacheprovider -m 'not integration' -vv --tb=short --color=no tests/test_time_budget_grading_preparation.py -k time_budget_first_f_grading_executor
```

The exact command additionally contains source/clean-tree guards, environment
settings, absolute interpreter and temporary output paths, and the timeout
wrapper. Its hash below identifies those original command-file bytes, not this
shortened display. Evidence remains under
`/tmp/time-budget-first-f-grading-proof.Y22xYR/`; nothing was overwritten.

| Evidence file | Bytes | SHA-256 |
| --- | ---: | --- |
| `command.sh` | 1056 | `5bb3d748f5d8b4f1e1bbdb7abbfe3c71d246809e957ef1e4b9a1be1eb476628e` |
| `output.log` | 38246 | `62d9f00771c2a4e6fb9b3a7202b9ed0440e17eecd77149948ceda298b40db83e` |
| `junit.xml` | 33419 | `c81dfba78a11a373ff8975da3221c1863b46b1691a245bfa175cd02b1e739af0` |
| `receipt.json` | 3048 | `81a45ef0df4c3fe11315640f69f2f33d7e3fe77c548d4dd97a89966a12c37d53` |
| `pre-edit-review.md` | 3109 | `f6c91df709ce7596f1e323d62df8927483d5046fb44f269b3f8911550f0bb91a` |

All failed nodes use `tests/test_time_budget_grading_preparation.py::` followed
by the function and parameter ID below. This is the complete 31-node inventory:

- `test_time_budget_first_f_grading_executor_roundtrip`: `complete-completed`,
  `error-failed`, `partial-failed`, `timeout-timeout`,
  `cleanup_lost-cleanup_unconfirmed`, `missing-missing_grade`,
  `cancelled-cancelled`.
- `test_time_budget_first_f_grading_executor_direction_refusal`: `missing`,
  `digest`, `extra`, `binding`, `future`, `expired`, `context`.
- `test_time_budget_first_f_grading_executor_binding_refusal`:
  `preparation_digest`, `coherent_core`, `extra_member`, `result`, `input`,
  `missing_inference_source`, `result_fingerprint`, `materialized_config`,
  `controller`, `frozen_root`, `other_cell`, `clobber`.
- `test_time_budget_first_f_grading_executor_attempt_retention`:
  `second_preparation`, `claim_fsync`, `final_input_drift`, `ledger_drift`,
  `missing_ledger`.

### Callable shape and output

The following is the command shape for later authorized use, not a command run
in this task. Every capitalized identity is independently supplied. Paths must
be absolute, canonical and disjoint as checked by the adapter; the destination
must not exist. Observation and input-binding documents use canonical JSON
with independently supplied byte digests and sizes.

```bash
python /C/batch-runner/gpt54_time_budget_grading_execution.py \
  --controller-root /C --controller-source-sha C_COMMIT --controller-source-tree C_TREE \
  --runtime-root /R --reviewed-source-sha R_COMMIT \
  --frozen-grader-root /F --grader-source-sha 882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2 \
  --input-registration-root /I --input-source-sha I_COMMIT --input-registration-path I_ROLE \
  --dataset-parquet /inputs/registered.parquet --reference-root /references \
  --observation-file /bindings/observation.json --observation-sha256 OBS_SHA256 --observation-size OBS_BYTES \
  --input-binding-file /bindings/inputs.json --input-binding-sha256 INPUT_SHA256 --input-binding-size INPUT_BYTES \
  --result-path /result/result.json --result-sha256 RESULT_SHA256 --result-size RESULT_BYTES \
  --deliverables-root /result/upload \
  --preparation-directory /prepared --preparation-sha256 PREP_SHA256 --preparation-size PREP_BYTES \
  --direction-file /directions/grade.json --direction-sha256 DIRECTION_SHA256 \
  --execution-context-sha256 CONTEXT_SHA256 \
  --attempt-store /private/attempts --destination /new/grade-output
```

`PREP_SHA256` / `PREP_BYTES` identify the accepted preparation marker, not an
invented bundle. R's tree is independently bound by the observation document;
F's tree/template are fixed by the existing compiler. The direction schema is
`time-budget-first-f-grading-direction-v1` with exactly `binding`, `not_before`
and `expires_at` alongside `direction_version`. Its binding is the exact
`GradingExecutionBinding.as_dict()` constructed from reverified facts. The
caller must independently review that binding and supply the direction digest;
the binding builder itself grants no permission. The context hash includes
boot, PID/mount/user namespaces, uid, interpreter and complete CI identity when
present. It is not proof of host cleanup capability.

The implementation writes a destination reservation and permanent store claim,
then installs only `source/batch-runner/experiments/gpt54_time_budget_v1_v2_r1.yaml`
in the consumed preparation. Step8 runs from `source/batch-runner` with
`source/batch-runner/time-budget-grading.json`. The new destination retains:

- `grader-owner.json`, the existing owned-process state;
- `grade.json`, unchanged Step8 schema 1.4 bytes when present and valid;
- bound ledger JSONL and any valid incomplete task checkpoint at their existing
  source-relative paths, so an unchanged grade pointer still resolves;
- `grading-execution.json`, with checked bindings, claim identity, actual exit
  code/terminal reason, interruption/cleanup status, grade/sidecar byte identities,
  usage availability and `retry_allowed: false`.

Missing, invalid or interrupted output cannot become a successful grade.
Partial files and the attempt claim remain if final validation/publication
refuses. The receipt distinguishes recorded Step8 usage from a complete bill;
it does not claim backend cancellation, a billing bound or global once-only
execution. The CLI returns 0 only for a completed result, 1 for a recorded
non-success terminal and 2 for refusal/uncertain incomplete state. These paths
remain unproved by the failed local invocation.

### Prior evidence and remaining gates

The [53-case consumer proof][consumer], [41-case preparation and eight-case
terminal correction][grading], and [PR755 evidence][first-v2] remain separate.
PR755's original 32 passed / 1 failed at `a1380d82`, its unrerun `9cf4429c`
fixture correction and 2 passed in 2.15s at
`53d17831df0bc3fd569c00baeffb6ac34d5c5d7c` are not combined into a pass claim.
Earlier actual-host CI evidence and the NAS refusal retain their original
scope; this task did not repeat or extend either.

The catalog was reviewed once. `experiment-design` was applied first to the
existing fixed 20-observation configuration-bundle comparison; no axis, judge,
model, limit or new spending decision was introduced. The consolidated grading
specification and grading-engineer/source-provenance/systems charters governed
the source and process boundary. The pre-edit note is the primary worker's
same-session charter application, not independent owner approval.
`im-not-ai-en` governed the English records with a bounded changed-passage
fidelity check. Experiment-result reporting, UI and animation skills did not
apply to this software task.

Corrected executor cases, final-HEAD source review and applicable ordinary CI
still need acceptance. A genuine terminal first-observation result with exact
inputs/deliverables and inference-source identity, reviewed C/R/F and actual
execution context, the existing approved provider connection and a leader-issued
digest-bound live direction remain prerequisites. The fixed 20-observation
policy, F judge, historical profiles/scores, core/ownership/finalization,
compiler/manifest, workflows and original launch refusals are unchanged. The
finished 30-cell and eight-cell studies remain closed. No private original,
receipt or consumed preparation was read; no model/grader/HF/Azure operation,
CI dispatch/retry/poll, Project mutation or merge occurred.

[consumer]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a9dd6d12ee52344d3f0e329d2d355d429a175df8/tasks/LATEST_TASK_RESULT/README.md
[grading]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/896a27fffbba23f2d1a1b75fa9fd61c0d83170ed/tasks/LATEST_TASK_RESULT/README.md
[first-v2]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/c766c3b80365d1ff4c7b1dc1e1a91bef569c7b9f/tasks/LATEST_TASK_RESULT/README.md
