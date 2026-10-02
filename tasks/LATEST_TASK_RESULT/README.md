# Latest task result

## PROJECT5-KEEP-R2-GRADE-FILENAME-20261002-1418

The closed keep/r2 grading path now passes the authorized synthetic lifecycle
and coupled routing proof at `7d90f7dcce88537d8fe2fa271c19be68078ca019`:
2 collected, 2 passed in 36.42s, exit 0, with no timeout. The leader's dated
1418 APPROVE-WITH-CONDITIONS decision authorized only the unpublished selector
rename and its required bindings. This proof is ready for independent
immutable-head review and applicable CI; it is not a live grade or final source
approval. The 1316 and 1246 entries below are preserved historical snapshots of
their earlier stops, not the current publication status.

### Closed naming correction

The new selector changes from `retention/task4-keep-r2` to
`retention/keep-r2`. The long selector was never published or executed and is
refused, not retained as an alias or sent through generic grading. The adapter,
canonical context/command, emitted
`batch-runner/experiments/retention/keep-r2.yaml` metadata path, exact typed
ledger/run-ID binding and workflow plan/protected/live/reconciliation gates
use the short selector. Approval inputs and the new fixed-evidence digest bind
that spelling. The dispatcher still reaches the existing closed selector guard.

The cell remains
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r2`, ordinal 3 /
repetition 2, with the same producer, immutable result and same-run authority.
`retention/first-cell`, old pilot/readout selectors and historical evidence keep
their meanings. No UUID/hash truncation, random path, alias, global Step8 or
checkpoint naming change, relaxed `PC_NAME_MAX` check, judge/config/rubric/model
change, permission change or budget change was made. Both the canonical-context
mutation refusal and the actual-reader-byte corruption checks are retained.

### Measured filename boundary

Before pytest, the real fixed config, Step8 output resolver, judge slug and
checkpoint resolver produced these UTF-8 leaf lengths. Actual
`os.pathconf(..., "PC_NAME_MAX")` was 255 on both the worktree and task-owned
filesystem; the limit was not mocked.

| Derived leaf | Former long selector, bytes | New short selector, bytes |
| --- | ---: | ---: |
| Grade JSON | 219 | 213 |
| JSONL cost ledger | 232 | 226 |
| SQLite cost ledger | 234 | 228 |
| SQLite `-wal` | 238 | 232 |
| SQLite `-shm` | 238 | 232 |
| SQLite `-journal` | 242 | 236 |
| Checkpoint | 257 | 251 |
| Atomic checkpoint temporary | 261 | 255 |

The temporary checkpoint fits exactly, with no spare bytes. The targeted test
asserted every required length against the actual limit and completed a tiny
real checkpoint write/readback on its own filesystem, including the 255-byte
temporary leaf. This verifies the local boundary, not an unmeasured host's
capacity. The generated config hash is `62a6d99d9e74d187`; grader-source SHA256
remains `997c30a6b6b8ed8f53d75a6db180dca549df6d0ae31e549934b75eb27d1b0fc1`.
Full derived names and measurements are saved in
`/tmp/project5-keep-r2-grade-filename.Y8x8dU/filenames.json`, SHA256
`5d5dbf13a662280080b0f04862e81753c4b49482074c00b75af0aac53b1e43eb`.

### Pinned proof and earlier failures

The same-environment prerequisite verified
`/ai-work/venvs/gdpval-realworks-py310/bin/python`, CPython 3.10.12 / pytest
9.1.1, without installation. Its saved `prerequisite.log` in the measurement
directory has SHA256
`5513d294c3594784460699bb31a4f4ba3698c333c8f144c3b8085264a9d98b96`.
Exactly these two selectors passed at
`7d90f7dcce88537d8fe2fa271c19be68078ca019`:

| Selector in `tests/test_codex_retention_keep_r2_grade.py` | Result |
| --- | --- |
| `test_keep_r2_fixed_grade_is_bound_one_use_and_private` | Passed |
| `test_keep_r2_fixed_grade_workflow_approval_and_ledger_are_closed` | Passed |

From `batch-runner`, the single invocation was:

```text
timeout --signal=TERM --kill-after=10s 180s env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest tests/test_codex_retention_keep_r2_grade.py::test_keep_r2_fixed_grade_is_bound_one_use_and_private tests/test_codex_retention_keep_r2_grade.py::test_keep_r2_fixed_grade_workflow_approval_and_ledger_are_closed -vv -s --tb=short -p no:cacheprovider
```

The full log is
`/tmp/project5-keep-r2-grade-filename.Y8x8dU/targeted.log`, SHA256
`bef2f512c1d22474d69d564b38e965deda8c454a004e80901622ad45edf54c16`.
Both selectors passed in 36.42s, exit 0; the 180-second timeout did not fire.
Offline network/process/model guards and disabled plugin autoload remained
active. No separate collection probe, other suite, private integration or live
operation was run.

The lifecycle reached real marker/payload readback, materializer provenance and
derived fingerprint checks, the exact original rubric, the distinct keep/r1
grade-parent control/claim/history and current-parent CAS, one synthetic owned
judge, private publication and lost-ack read-only reconciliation. It retained
no-replay and one-result/one-judge assertions. The coupled selector verified
same-run approval, old defaults, exact typed ledger binding and secret/job/time
boundaries. These are synthetic transport/owned-child checks, not authentication
of live publications or an established writer acknowledgment.

The prior results remain separate:

- At `44fa6694f73fad8d6ad202855e5847b6c4212d6d`, 2 collected with 1 failed /
  1 passed in 7.32s, exit 1. The lifecycle expected
  `reviewed_retention_reader_required` but correctly encountered the earlier
  `retention_grade_context_changed` guard. The routing selector passed only
  against the former long selector. Log SHA256
  `3070012930c09ed096529c73e50ba0a6ee997f412da28874e8249ed661f5234e`.
- At `9a628e52732c162dd0a179ca96579dacc402a4d2`, the lifecycle-only follow-up
  failed in 8.64s, exit 1, without timeout. Corrected context-mutation and actual
  reader-byte checks completed; the first intended successful preparation
  refused at `codex_budget_pilot_grading.py:747` with
  `grading_filename_capacity_refused`, before successful preparation or later
  lifecycle assertions. Log SHA256
  `99ca382018a16c5b6145db7a200ef1d1ec67cd05a5ad81cc15c1873e44cf4ca1`.

The 1418 order separately authorized the naming correction and this two-selector
invocation because routing and authority bytes changed. Neither earlier failure
is relabeled as a passing lifecycle proof. Their logs and records remain intact.

### Current bindings and unchanged evidence

The new selector-bound evidence SHA256 is
`25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0`, replacing
only the unpublished long-route digest
`eacfc94a16f6fdee0d3259590d35abd0e9d365733742946b8b139b705d5def07`.
Historical first-cell evidence remains
`1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d`.

| Current source at the tested HEAD | SHA256 |
| --- | --- |
| `codex_retention_keep_r2_grade.py` | `bb8d1b3a46824a2597f31fe6567531fc59deabb79af87e85d98fd1a08ae3988e` |
| `codex_retention_fixed_grade.py` | `7790852b04f8496db8b13ac6957badf641175c501f422720a7d14896b340d5ac` |
| `codex_budget_pilot_output.py` | `635966f42c0310c9093d59e8f417259a0625b847c52f73342c07ec6c64fa2fdb` |
| `.github/workflows/grade-run.yml` | `a59762078a6dc81a9867490338873a2f6db2ebb8f456f37759874b40710b6824` |

The shared reader remains
`5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583`.
Frozen inference controller/producer/facade/CI-verifier/original-intake files,
grader configuration, grader source modules, rubric, prompt and dependency manifests
remain unchanged. Only the two completion records change after the tested HEAD.

Actual successful keep/r2 intake remains separate from this offline proof. Its
input is inference terminal `e55fac5d60191167dd66688510ec0fef472e594d`, result
fingerprint `909ef80ffdce0e59ffeae5010df929ef7d93510c2e54cd710624e61ec343b86a`.
The grading parent is instead keep/r1 grade terminal
`40712e0980cc05c31688fdbb98c693774fb90c0d` on `pilot-grades-20260925-04`.
Keep/r2 is consumed and ungraded: 6 recorded inference model calls, aggregate
known/model USD 0.22195 partial, with null generation cost. Recorded zero
generation counters do not establish free work. The earlier intake section
preserves all immutable identities, missing-usage fields and publication-derived
proof limits; no invoice, HTTP count, deliverable count, writer acknowledgment
or retention benefit is inferred. Old keep/r1 scores, failed-fresh partial
costs, null grades, unavailable causes and study limits remain unchanged.

The leader's independent review of the actual new immutable HEAD/diff/proof and
applicable CI remain required. A later live grade also requires a separately
approved exact source/run/request/result/budget/stop binding. No live read,
inference, grade, dispatch, consumed-result replay, HF mutation, Project edit,
merge, credential/permission change or Azure management action occurred.
Previous failed reviewer transports remain failures, not approvals, and were
not retried. The existing owner identity is unchanged.

The full skill catalog was checked once for this phase. `experiment-design`
and the grading-engineer domain/spec requirements preserved the registered
conditions and grader semantics. `experiment-report-en`, then protected
`im-not-ai-en`, kept this new evidence entry separate from historical failed
proofs and actual partial inference accounting; unrelated historical text was
not reprocessed.

## PROJECT5-KEEP-R2-GRADE-TEST-CORRECTION-20261002-1316

The authorized test-setup correction is pinned at
`9a628e52732c162dd0a179ca96579dacc402a4d2`. Its single follow-up lifecycle
invocation collected 1 selector and failed in 8.64s, exit 1. Both corrected
negative checks completed, but preparation then refused with
`grading_filename_capacity_refused`. The full lifecycle is still unverified.
No further repair, test invocation, push or draft PR followed. Both completion
records remain saved and uncommitted in the same grading worktree and branch.

The correction changes only the negative setup in
`tests/test_codex_retention_keep_r2_grade.py`. Post-compilation expected-pin
mutation still requires the earlier `retention_grade_context_changed` refusal.
A separate scoped wrapper delegates to the real `output._bytes` reader and
corrupts only the returned bytes for each exact dependency path. Expected pins
and the compiled context remain canonical; each case requires
`reviewed_retention_reader_required`, confirms the targeted read, and checks
that no private root, transport call or owned judge activity occurred.

The failure is at test line 234, in the first intended successful
`bridge.prepare` call. The trace reaches `codex_retention_fixed_grade.py:368`,
then `codex_budget_pilot_grading.py:747`, where `_entry_contract` raises
`grading_filename_capacity_refused`. This is the recorded refusal boundary,
not a diagnosis of its underlying cause. Successful preparation, derived-input
fingerprint/materialization assertions, grading-parent history/CAS, owned-judge
execution, private publication and lost-ack reconciliation assertions were not
reached. No production predicate was weakened or reordered.

The original proof at `44fa6694f73fad8d6ad202855e5847b6c4212d6d` remains
2 collected, 1 failed / 1 passed in 7.32s, exit 1. Its lifecycle failure expected
`reviewed_retention_reader_required` but received
`retention_grade_context_changed`; it was not a passing lifecycle proof.
The already-passed
`tests/test_codex_retention_keep_r2_grade.py::test_keep_r2_fixed_grade_workflow_approval_and_ledger_are_closed`
selector was not rerun. Its pass belongs only to that original tested HEAD.
The original log remains `/tmp/project5-keep-r2-fixed-grade.gz9e7b/targeted.log`,
SHA256 `3070012930c09ed096529c73e50ba0a6ee997f412da28874e8249ed661f5234e`.
The unchanged 1246 section below records that earlier order and its stop.

The new same-environment prerequisite verified
`/ai-work/venvs/gdpval-realworks-py310/bin/python`, CPython 3.10.12 and pytest
9.1.1, exit 0, without installation. Its log is
`/tmp/project5-keep-r2-grade-test-correction.uEdJ4x/prerequisite.log`, SHA256
`5513d294c3594784460699bb31a4f4ba3698c333c8f144c3b8085264a9d98b96`.
The single follow-up call ran from `batch-runner` under `env -i`, the same
offline settings, disabled implicit HF tokens and plugin autoload, and the
existing network/process/model guards. It used the following command, without
`-x`, another selector or a collection probe:

```text
timeout --signal=TERM --kill-after=10s 180s env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest tests/test_codex_retention_keep_r2_grade.py::test_keep_r2_fixed_grade_is_bound_one_use_and_private -vv -s --tb=short -p no:cacheprovider
```

The timeout did not fire. The complete follow-up log is
`/tmp/project5-keep-r2-grade-test-correction.uEdJ4x/lifecycle.log`, SHA256
`99ca382018a16c5b6145db7a200ef1d1ec67cd05a5ad81cc15c1873e44cf4ca1`.
No delivered suite, private integration, full suite or build was run.

Before and after the follow-up, a byte comparison against
`44fa6694f73fad8d6ad202855e5847b6c4212d6d` found no changes outside the test
file and these two records. Production, workflow, dependency manifests,
grader configuration, parent bindings and reader/producer pins are unchanged.
The shared reader remains
`5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583`.
The adapter/controller/workflow hashes and both fixed-evidence digests below
remain exact. The ordinary test-only commit retained the existing owner identity
`hyeonsangjeon <wingnut0310@gmail.com>` without attribution trailers.

The actual keep/r2 intake and accounting below remain separate from this
synthetic proof. Keep/r2 is consumed and ungraded, with 6 recorded model calls
and aggregate known/model cost USD 0.22195, partial; generation cost remains
null. The grading parent is `40712e0980cc05c31688fdbb98c693774fb90c0d`, not
inference terminal `e55fac5d60191167dd66688510ec0fef472e594d`. The result
fingerprint stays `909ef80ffdce0e59ffeae5010df929ef7d93510c2e54cd710624e61ec343b86a`.
No invoice, deliverable count, writer acknowledgment or retention benefit is
inferred. Earlier scores, partial costs, nulls, unavailable causes and the
previous reviewer/runner failures are preserved without another live read.

The 1246 conditional decision still covers unchanged production; it is not
final source approval. This new failed boundary requires leader direction
before another correction or proof. A passing authorized lifecycle proof,
independent immutable-HEAD review, applicable CI and a separately bound live
grading approval remain required. No live HF read/write, inference, grade,
dispatch, replay, Project change, merge, Azure or permission action occurred.
The full catalog was checked once for this phase; `experiment-design` preserved
the existing invariants, and `experiment-report-en` followed by protected
`im-not-ai-en` kept the two failed proofs and actual intake evidence distinct.
## PROJECT5-KEEP-R2-FIXED-GRADE-20261002-1246

The local fixed keep/r2 grading implementation did not clear its targeted
proof. At tested HEAD `44fa6694f73fad8d6ad202855e5847b6c4212d6d`, the one
invocation collected 2 selectors and reported 1 failed, 1 passed in 7.32s,
exit 1. The lifecycle selector stopped at a wrong-reader-hash assertion; the
workflow/approval/ledger selector passed. No source correction or rerun followed.
The implementation remains pinned locally, with these two completion records
uncommitted. Nothing was pushed and no draft PR was created.

The worktree is `codex-retention-keep-r2-fixed-grade-20261002-1246`, branch
`b/codex-retention-keep-r2-fixed-grade-20261002-1246`, from verified main/base
`f1f274f1b0510a9f4d7e7c969574913442105579`. Earlier worktrees and
`wip/local-main-preserved-20260719` were preserved. The existing author and
committer identity stayed `hyeonsangjeon <wingnut0310@gmail.com>`, without
attribution trailers. The leader's source-informed 1246
APPROVE-WITH-CONDITIONS decision authorized the closed pre-edit scope, not
unwritten code, this failed proof or a paid run. Prior reviewer transport
failures remain historical failures; none was retried or treated as approval.

Prior reader PR719 HEAD `2f865eb6491e236ebe54027f29c030d75e88cef0`, owner review
[5387838626](https://github.com/hyeonsangjeon/gdpval-realworks/pull/719#pullrequestreview-5387838626)
and all 10 checks passed their source gate. Its 1429-line review and separate
19.11s reader proof were not repeated and do not validate this grading route.

### Implementation scope and stopped proof

The six-file implementation adds only `retention/task4-keep-r2`, for Task4
KEEP ordinal 3 / repetition 2, through the existing fixed grading lifecycle.
Its adapter binds the verified result and the separate keep/r1 grading parent.
The source retains the original deliverables-only materializer staging,
recomputed provenance/fingerprint, exact rubric and grader checks, serial
current-parent CAS, one-use owned judge, private add-only publication and
same-job read-only lost-ack reconciliation. A second exact ledger-binding type
does not replace the first-cell type or widen pilot ledger identities.
Only the existing plan/protected/live workflow routes admit the new selector;
generic retention exclusions and old selectors remain. No new job, permission,
secret, arbitrary profile, experimental condition, retry policy or budget axis
was added. The existing `default_v2_sol_max.yaml`, original rubric revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, 240-minute judge, 242-minute owned
child and 300-minute job limits are unchanged. The full lifecycle remains
unverified by this invocation.

The same-environment prerequisite printed
`sys.executable=/ai-work/venvs/gdpval-realworks-py310/bin/python`,
`sys.version=3.10.12 (main, Jun 22 2026, 18:55:27) [GCC 11.4.0]` and
`pytest.__version__=9.1.1`, exit 0. No packages were installed. Prerequisite
log SHA256 is `5f1ef71b3a20194547eb67a95ef44e8a440bd619cf6be992e3b599c9469f60cb`.
The single test call ran from `batch-runner` with that absolute interpreter,
`env -i`, offline/implicit-token-disabled settings, no credential variables,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `timeout --signal=TERM --kill-after=10s 180s`
and `-m pytest -vv -s --tb=short -p no:cacheprovider`, without `-x`.
Production/workflow/test bytes matched the pinned HEAD before the call.

| Exact selector | Result |
| --- | --- |
| `tests/test_codex_retention_keep_r2_grade.py::test_keep_r2_fixed_grade_is_bound_one_use_and_private` | FAIL at line 195: expected `reviewed_retention_reader_required`; actual `retention_grade_context_changed` |
| `tests/test_codex_retention_keep_r2_grade.py::test_keep_r2_fixed_grade_workflow_approval_and_ledger_are_closed` | PASS |

The lifecycle selector reached canonical request compilation, frozen reader
identity checks, successful intake of synthetic KEEP_R2 payloads and pre-root
approval/source refusal checks. Its first wrong-reader-hash case was refused
by the earlier canonical-context guard. It did not reach the expected hash
refusal, successful grading preparation/materialization, grading-parent
control/history verification, claim/CAS, owned judge or publication assertions.
The passing selector executed the real protected-approval script and parsed
current workflow YAML, checked old defaults and closed routes, and exercised
the exact first-cell/keep-r2 ledger types and row refusals. Offline process,
network and model guards were active. These are synthetic test observations,
not live source approval, native installation or grading evidence.

The outer timeout did not fire. The complete saved log is
`/tmp/project5-keep-r2-fixed-grade.gz9e7b/targeted.log`, SHA256
`3070012930c09ed096529c73e50ba0a6ee997f412da28874e8249ed661f5234e`.
No second invocation, collection probe, delivered suite, private integration,
full suite or build ran. The prior missing-pytest failure and its replacement
proof remain separately recorded below; this was a reached assertion failure.

### Fixed input and grading-parent identities

The following are independent leader-supplied live evidence, not products of
the synthetic proof. The successful intake used workflow `370228282`, run
`36959616821` / attempt 1 / job `110690181822`, reader source
`f1f274f1b0510a9f4d7e7c969574913442105579` and reader SHA256
`5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583`.
Its `2026-10-02T03:21:22.9144192Z` receipt reports `intake_verified=true`,
`status=succeeded`, `cleanup_confirmed=true`,
`recorded_publication_acknowledged=true`, `grade=null`, `grading_launched=false`
and `invoice_complete=false`. Approval/execution jobs were skipped. No live
read was repeated in this implementation task.

The consumed producer is `b8351e561acb9675a4993419e819c12787b5b305`, run
`36947454688` / attempt 1 / execution job `110660390316`, cell
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r2`.
Its request SHA256 is
`8a06cc7df34cbf10896b635f6c8d9ad4e91313d3c685511f8fc5c159cb6ddec1`.
The original input bundle is
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`;
the path-specific materialized grader source is
`997c30a6b6b8ed8f53d75a6db180dca549df6d0ae31e549934b75eb27d1b0fc1`.

| Inference object | Immutable revision | SHA256 | Bytes |
| --- | --- | --- | --- |
| Terminal | `e55fac5d60191167dd66688510ec0fef472e594d` | `70fb8778ae15e369ef1ac4d03dbe4fa6f5d9852966b250fa812695d6bd77bf91` | 5885 |
| Claim | `f29f8d4a19710aa0e832dba720ff7d32701c309c` | `4af63e82ddcaf2b795595081c59d29369e2bf2a4bb2c37f81eb7f5409cd6b363` | 1888 |
| Output manifest | `54a4362ce3554b7c71b5ada00802efc9521038e6` | `93e1dada24779909cfc593dff7507b7f9c6452c6f36c12b2c5e86305e35d9a8c` | 2679 |

The output-object-set SHA256 is
`4bda1c0d48a5dd980bd683a6f8316b3d52808e95dca68099b86ad4de2d3e03b2`;
the full intake marker SHA256 is
`4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4`;
retained-authority SHA256 is
`7427be5a3d3f5692ca9d92920161c7ddf4491faf39f36f9ee9cee062f45f5705`.
The 10238-byte result has SHA256
`8d90bb52bc87f5989baba1eea59de205155523492e9b679087eac5c12b7e539e`
and fingerprint `909ef80ffdce0e59ffeae5010df929ef7d93510c2e54cd710624e61ec343b86a`.
Its recorded prepared fingerprint is
`fb6e4301ec91245601e80fc6f181076513dd71bd358bb0fbc856b5080e8108e8`,
and registered config SHA256 is
`307dc07923d377faa7d7c6bd6c4934de2fa5f99e9007dd0d723f3c3337e6d010`.
The inference predecessor remains failed fresh/r2 terminal
`1d5133590911f3704fc2a65279d4b64bee77c1d6` through the frozen producer's pins.
The safe receipt does not disclose a deliverable count or the full marker's
files/result-generation fields. None was fabricated. Future grading preparation
must revalidate the exact full marker and declared immutable payloads because
`consumer_readback_required=true`; the original fingerprint is not the
materializer's derived-input fingerprint.

The required parent on `pilot-grades-20260925-04` is the keep/r1 grade terminal
`40712e0980cc05c31688fdbb98c693774fb90c0d`, SHA256
`11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234`, 3119 bytes,
with claim `dec305d669e3ca2e53c7f7b9ebfbe7974d661350`, SHA256
`8e1e0a51b462a442e9024c2bd5140d3898b61424ce3f44d4adff9fa346cce53d`, 2384 bytes.
Its writer is `29e0353f1539265b1741e71be894fedf9be32a8b`, run `36776393736` /
job `pilot-live` / attempt 1, previously verified by readout `36820845596` at
source `f30c9efa392bc14cba790fb5d1dedf12071a5677`. Its inference terminal
`de50ff0aa6037c0ef6e3b713da519359abd1d08d` and result fingerprint
`3441f200e6e4c53faf1b36f216283c80eee68e5d3e7d827587ba6c3135c7d200` remain
historical. Existing readout predicates are reused for its controls, claim and
object history without payload-body reads. Historical verification is not
current branch-head evidence: exact current-parent equality remains required
before a new one-use CAS. Drift or uncertainty must refuse, not adopt or reset.

### Accounting, byte identities and remaining gate

Actual recorded keep/r2 inference accounting is partial: 6 model calls,
comprising 5 infrastructure-retry calls with known USD 0.22195 and 1 generation
call with `known_cost_usd=null` and recorded zero token counters. Aggregate
known/model cost is USD 0.22195, partial. Recorded usage is input 194536,
cached input 163840, output 6950 and reasoning 4096. Cached/reasoning counters
are subsets, not additional token totals. The generation component's zero
counters and null cost do not establish free work or zero actual usage.
Estimated cost, runtime cost and HTTP request count remain null; missing reasons
are `call_reachability_unknown` and `usage_absent`, with `invoice_complete=false`.
Model calls are not HTTP requests or native admissions/resumes. No grade exists.

This intake is publication-derived evidence, not independent provider,
original-input or CAS authentication; `writer_acknowledgment=not_established`.
Four of eight producer outcomes are reported, with four Task5 cells outstanding.
The original 30-cell pilot remains closed. Keep/r1 scores remain 68.0% included /
54.64% full with their exclusions; failed fresh/r1 remains 39 calls / known
USD 0.303358 partial, and failed fresh/r2 remains 39 calls / known USD 0.29944
partial. Their null grades and unavailable detailed cause/budget/recovery
evidence remain unchanged. Duration or retry labels do not identify a failure
cause, and these repeats do not establish a retention benefit.

New fixed-evidence SHA256 is
`eacfc94a16f6fdee0d3259590d35abd0e9d365733742946b8b139b705d5def07`.
The original first-cell digest stays
`1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d`.
At the tested HEAD, the new adapter SHA256 is
`5c403632d33cebf4e5cf0fb212c7a8262484a6dfe05be7e1acd67a672e978c91`;
the shared fixed-grade controller is
`e0b3c878b735e4e2e30b54b528c1887807f02cd326cfc0e32c2bf947106ab44f`.
The current reader and all six frozen producer/controller/verifier/intake
file hashes remain identical to base. No historical pin or receipt was migrated.

The reached assertion failure is preserved. Publication is blocked pending
leader direction for a bounded correction and a newly authorized focused proof;
the single invocation under this order is used. After a passing proof, final
independent review of the actual immutable HEAD/diff, applicable CI and separate
leader approval of an exact grading source/run/request/result/budget/stop binding
remain mandatory. No live read, HF branch mutation, dispatch, model/judge call,
grade, replay, Project edit, merge, credential/permission change or Azure
management action occurred. No failed reviewer call supplied approval.

The full skill catalog was checked once. `experiment-design` preserved the
registered condition and budgets; the repository grading-engineer domain/spec
requirements were applied without changing providers or rebuilding the grader.
`experiment-report-en`, then protected `im-not-ai-en`, kept the failed local
proof separate from the leader's actual intake and partial accounting. Only
these new record passages were edited; the historical text below is preserved.

## PROJECT5-KEEP-R2-READER-RUNNER-FIX-20261002-1113

The fixed keep/r2 reader extension passed the leader-authorized replacement
invocation at unchanged implementation HEAD
`bd4452d3fd4b77d9f7c86e0fc709179927eaef3f`: 2 collected, 2 passed in 19.11s,
exit 0, with no outer timeout. The intended existing CPython 3.10.12 runner
passed its interpreter/pytest import prerequisite; no dependency installation
or source, workflow, test, manifest or pin change was needed. The earlier
`No module named pytest` failure remains separately recorded below with its
original log. It was a pre-collection runner failure, not a code verdict.
These records accompany the unchanged implementation for the leader's final
immutable-head diff/proof review and applicable CI. No live reader ran.

This resumes the 1011 task in the same worktree from verified base
`b8351e561acb9675a4993419e819c12787b5b305`. The leader's dated 1042
APPROVE-WITH-CONDITIONS decision authorized the bounded pre-edit scope after
reading the source and decision charter. The prior reviewer calls failed with
HTTP 400, a disconnected stream, then HTTP 400 from a fresh same-session
reviewer. Those failures produced no approval and were not retried; no account
or provider was switched. At that earlier blocker there had been no
implementation or test invocation. The leader's decision resolved that
pre-edit blocker, but does not approve the actual new diff, waive CI or
authorize a live operation.

The implementation adds one identity-equal `KEEP_R2` profile to the existing
shared reader for
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r2`, ordinal 3 /
repetition 2, campaign `retention_bundle_diagnostic_20260929`. It binds KEEP,
the independent producer/run/request/job/input/grader identities below, and
the frozen keep/r2 producer's fresh/r2 predecessor. Both success and terminal
modes require the exact integer execution job and project it in their evidence.
Only this profile joins the existing contents-read result/terminal routes.
Default `FRESH_R1`, explicit `FRESH_R2`, both predecessor bindings, the original
keep/r1 route and default preparation/execution routing are preserved in source.
Locator remains keep/r1-only. No job, input, credential, permission, experiment
condition or execution authority was added. The replacement proof below uses
real validators and synthetic records; it does not validate live publications.

Prior PR718 HEAD `305c3539f93854248d41558a98e8d3d8cba8e72e`, owner review
[5387019458](https://github.com/hyeonsangjeon/gdpval-realworks/pull/718#pullrequestreview-5387019458)
and all 10 checks passed the producer source gate. Its
[immutable completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/305c3539f93854248d41558a98e8d3d8cba8e72e/tasks/LATEST_TASK_RESULT/README.md)
preserves the separate 61.31s proof and full implementation scope. Those reviews
and tests were not repeated and do not approve this reader extension.

### Preserved pre-collection runner failure

Pinned implementation/attempted validation HEAD:
`bd4452d3fd4b77d9f7c86e0fc709179927eaef3f`. That attempt used
`/ai-work/copilot/.codex-dependency-install-20260923.JN278b/validation-env/bin/python`;
its `pyvenv.cfg` records Python 3.10.12. The command used `env -i`, offline and
implicit-token-disabled settings, no credential variables, plugin autoload
disabled, `timeout --signal=KILL 180s`, and
`python -m pytest -vv -s --tb=short -p no:cacheprovider` without `-x`.

| Exact selector | Result |
| --- | --- |
| `tests/test_codex_retention_keep_r2_read.py::test_keep_r2_reads_only_its_fixed_result_or_terminal` | Not collected / not executed |
| `tests/test_codex_retention_ci_read_result.py::test_retention_result_read_workflow_is_fixed_and_model_free` | Not collected / not executed |

Python module lookup failed with `No module named pytest`; runner exit was 1.
The outer timeout did not fire. There is no pytest duration or test result
count. Log SHA256:
`c0e5bafd4836ede09b9b58927734f402e2f170996d60c387df7ecc9519d2735c`.
The saved one-shot runner has SHA256
`a24088e1e954e86ca4d3f48b1b15d07ee63e8553ad1c62a255ca2763cf3d34f4`.
Pytest collection, offline fixture guards, reader binding checks, successful
payload intake, unsuccessful control-only observation, historical compatibility
and routing assertions were all not reached. No private input, network/model,
grade or remote-write operation ran. This is a runner setup failure, not an
observed reader-validator failure or model outcome. No repair or rerun occurred
under that earlier order. The 1113 order subsequently authorized the separate
runner-only replacement below, without changing the pinned implementation.

### Authorized replacement proof at the same implementation HEAD

One prerequisite check used the exact intended executable
`/ai-work/venvs/gdpval-realworks-py310/bin/python` under the same token-free
environment as the replacement test. It printed that `sys.executable`,
`sys.version=3.10.12 (main, Jun 22 2026, 18:55:27) [GCC 11.4.0]` and
`pytest.__version__=9.1.1`, and exited 0. No packages or interpreter were
changed. The prerequisite log has SHA256
`5f1ef71b3a20194547eb67a95ef44e8a440bd619cf6be992e3b599c9469f60cb`.

The single replacement invocation ran from `batch-runner` at tested HEAD
`bd4452d3fd4b77d9f7c86e0fc709179927eaef3f`, using that absolute interpreter,
`env -i`, offline/implicit-token-disabled settings, no credential variables,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `timeout --signal=KILL 180s` and
`-m pytest -vv -s --tb=short -p no:cacheprovider`, without `-x`.
Production/workflow/test bytes matched the pinned HEAD before the call; the
current reader and all six frozen file hashes also matched their exact pins.

| Exact replacement selector | Result |
| --- | --- |
| `tests/test_codex_retention_keep_r2_read.py::test_keep_r2_reads_only_its_fixed_result_or_terminal` | PASS |
| `tests/test_codex_retention_ci_read_result.py::test_retention_result_read_workflow_is_fixed_and_model_free` | PASS |

Pytest collected 2 cases and reported 2 passed in 19.11s; runner exit was 0.
The 180-second outer timeout did not fire. This is offline test duration/count
evidence, not model usage or an experiment outcome. The saved replacement log
is `/tmp/project5-keep-r2-reader-replacement.rXVNdW/pytest.log`, SHA256
`a3df4696dbaacc611ceb4fdadcff015f868ee392c1a0b67a107a22b5f522dc17`.
The replacement runner script has SHA256
`c637f892ac2d1099feb7ff7ba46ae1ec2428a9498dfef4b36f0a4efba21f51f9`.
The original failure log remains unchanged at its separate path and hash.

The reader selector reached successful declared-payload validation and
failed/stopped control-only observation with real validators and synthetic
transport. Its safe marker confirms `exact_job_both_modes=true`,
`old_bindings_preserved=true` and `private_no_clobber_readback=true`.
Identity/treatment/hash/history/type/role/privacy/bounds, missing-control and
no-clobber refusal assertions completed; terminal mode read no payload bodies.
The coupled selector parsed the current YAML, exercised 192 cell/mode cases
and confirmed `three_jobs=true`, `old_routes_preserved=true`,
`keep_r2_reads_added=true` and `current_pins_before_credentials=true`.
Both markers report `live_effects=0`. Offline process/network guards were
active; no private integration, full suite, delivered suite, live read, remote
write, model or grade ran. This authorized replacement was not followed by
another test invocation. Synthetic success is not live successful-result intake.

### Actual keep/r2 preparation, approval and succeeded receipt

The leader supplied workflow `370228282`, run `36947454688` / attempt 1 at
producer `b8351e561acb9675a4993419e819c12787b5b305`. Preparation job
`110652687444` succeeded; its receipt at `2026-10-02T00:47:12.1461147Z` is
`prepared_not_admitted`, request SHA256
`8a06cc7df34cbf10896b635f6c8d9ad4e91313d3c685511f8fc5c159cb6ddec1`.
The path-specific materialized grader is
`997c30a6b6b8ed8f53d75a6db180dca549df6d0ae31e549934b75eb27d1b0fc1`;
four original roles were verified from bundle
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
The receipt reports KEEP/B/no C, 10800 cumulative seconds, 1800 native-turn
wait, one slot, no reset, no fixed admission count and no automatic money cap.
These are prepared settings, not observed model behavior or success.

The leader posted and read back one exact owner approval in `grading`
`18744914306`, deployment `6798561339`; approval job `110653531434`.
The one authorized jobs-metadata projection independently returned
`retention-execute` job `110660390316`, run `36947454688`, attempt 1 and exact
source `b8351e561acb9675a4993419e819c12787b5b305`; the response listed 3 jobs.
That one-time metadata read was not repeated. It did not read logs or the
outcome, and no live reader or status polling occurred in this coding task.

The leader subsequently supplied the final safe CLI receipt from execution
job `110660390316` at `2026-10-02T01:38:40.0275325Z`, with the exact cell and
request above: `status=succeeded`, `cleanup_confirmed=true`,
`remote_terminal=acknowledged`, `grade=null`, `grading_launched=false`,
`invoice_complete=false`. All workflow jobs are green, but the reported task
success comes from this explicit receipt, not job status or approval alone.
The inference is completed and consumed and must not be replayed.

Terminal/claim/output revisions, deliverable contents and counts, usage and
costs have not yet been read. Keep/r2 remains ungraded; none of those unknown
values is borrowed from keep/r1 or either fresh cell. This producer receipt is
not a verified successful-result intake, independent provider authentication,
an invoice or a causal retention result. The replacement's synthetic proof
does not verify this consumed inference's unread payloads or accounting.

### Actual failed fresh/r2 control observation

The leader directly read
[observation run 36936506988 / job 110617920889](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36936506988/job/110617920889)
at historical observer `0f68701d62ae7d86a95ba8fd6b9f1cc65a4cf2d6`. The receipt at
`2026-10-01T22:43:16.1975611Z` is `terminal_verified`, observation SHA256
`50f13364c7a261010f210959d425420509bf879040257daeec9b16fea025e9d3`, with historical
reader SHA256 `5bfba1a2cb4d4f5190b0d146fd7b2b890c72ecf3904974d37babfea9ed8661f0`.
Approval/execution jobs were skipped. No payload bodies were read. This coding
task did not query or repeat the observation.

The consumed fresh/r2 inference is `status=failed`, exit 1,
`cleanup_confirmed=true`, `recorded_publication_acknowledged=true`, `grade=null`,
`grading_launched=false` and `invoice_complete=false`. Its cell is
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_fresh_r2`, producer
`5a9614ac04464c4e0a5e80297f54c3a5c9443bae`, run `36907894862` / attempt 1 /
execution job `110535767415`, request SHA256
`4798c119ea2d06c7c902ae51638bdba25c5bfaf683a2223d286fd7e652d3b317`.

| Verified control identity | Recorded value |
| --- | --- |
| Terminal | `1d5133590911f3704fc2a65279d4b64bee77c1d6`; SHA256 `c1ab656b3ee0556aa5934dc976dfa6086ac59f4f3e2abf936a600a9fcb7fda2b`; 4200 bytes |
| Claim | `98724c1fc83af2b45f65533648162692ba8d12b0`; SHA256 `d2718f7635870efbb3edefaf7d38ed20691fed40c1c39389b93e53947a6ceeb4`; 1889 bytes |
| Output | `46fff9e31bc844a55ced352926aba49479869624`; manifest SHA256 `f44c09d86d48d59579ff6ae3355633740b5d2888c7b38e33cd6c132bb45cf882`; 2119 bytes |
| Output object set | `output_objects_sha256=029c0b29cd7e3b593fb28ec0dfe4a6c3d6999b8867f980496cde1da335d18c3a` |

Declared roles are inference result 1, ledger 1 and deliverables 0, with 3 total
objects including the manifest. These are control/metadata declarations, not
proof of absent partial work or verified grading input. The proof is
`verified_publication_derived_not_independent_provider_authentication`, not
independent original-input or CAS authentication. Recorded publication
acknowledgment does not establish writer acknowledgment by the observer.
Grade null is not zero, and workflow success is not task success.

R2 records 39 model calls: infrastructure-retry 38 / known USD `0.253777`,
generation 1 / known USD `0.045663`; aggregate known/model USD `0.29944`, partial.
Recorded usage is input 105233, cached input 27648, output 6571 and reasoning
3979. Cached/reasoning values are subsets, not extra totals. Calls are not HTTP
requests or native admissions/resumes; partial known cost is not an invoice.
Estimated/runtime cost and HTTP request count remain null, with missing reasons
`call_reachability_unknown` and `usage_absent`. These are not r1's costs below.
`detailed_failure`, `budget` and `recovery_exposure` remain unavailable/null with
reason `not_recorded_in_terminal_controls`. Duration and retry labels do not
establish timeout or rate-limit causality or justify another read/repeat.

### Historical producer proof, not reader validation

The prior producer task tested `bf0bcfdb9e4364d8d8bd7ec72dac4b481556d8a3`:
2 collected, 2 passed in 61.31s, exit 0; the 180-second timeout did not fire.
Its single invocation used CPython 3.10.12 / pytest 9.1.1, `env -i` with token-free
CI-shaped ambient metadata, existing network/process/credential guards and no
`-x`. Its runner was `python -m pytest -vv -s --tb=short -p no:cacheprovider`,
with plugin autoload disabled and `timeout --signal=KILL 180s`.

| Selector, relative to `batch-runner` | Result |
| --- | --- |
| `tests/test_codex_retention_task4_keep_r2.py::test_task4_keep_r2_advances_failed_fresh_r2_without_cross_cell_state` | PASS |
| `tests/test_codex_retention_ci_observation.py::test_retention_keep_r2_routes_preserve_read_and_authority_boundaries` | PASS |

Both completed in the historical aggregate 61.31s above. Log SHA256:
`6a6f2559224e89acb9cd9e64e6e008aac00ca423362cf75c2c7e71b675d1d628`.
Real validators and synthetic transport/owned child reached packet/staging,
canonical request, approval, failed-predecessor claim, child, output, terminal
and immutable reconciliation. The proof covered 21 predecessor cases, wrong
source/run/request/cell/job/cleanup/history, branch drift, duplicate/no-replay,
guard ordering, cleanup, timeout and ambiguous publication. KEEP recovery
retained this cell's thread/directories/output across synthetic wait and
downtime with the original expiry and no C feedback; cross-cell substitution
refused. Old cell schemas and both reader bindings passed small compatibility
checks with the new current pins. Wrong hashes refused before credentials or
effects; predecessor verification made no payload-body downloads.

The coupled selector evaluated current YAML across 192 cell/mode cases and
checked the shared execution assertions, unchanged read allowlists and exact
precredential hashes. Synthetic fixture identities were derived from authored
bytes, not returned controls or canned validator success. This does not verify
the actual live predecessor or current remote parent. No live execution, model,
remote write or grade occurred. No delivered reader suite, private integration,
full suite or second invocation ran.

For that producer task, the bounded auth/runtime/storage/workflow reviewer
approved the scope and 11-file delta, then closed the review with APPROVE after
reading the proof. This remains a historical producer review. The leader's
1042 decision is the separate current pre-edit authority; independent review
of the actual new diff and the saved replacement proof remains pending.
The current reader's offline pass grants no live-read authority.

### Current reader migration and frozen historical bindings

This implementation changes only the CURRENT shared reader hash, from
`cd88a768e573d57c82d8f14bcb266ae455187933fb8a5b70da0fadafe17bea46` to
`5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583`, in both
read preflights and CLI expectations. The keep/r2 route checks its unchanged
facade and fresh/r2 dependency before lazy import and before the step-scoped
HF credential. The replacement proof exercised exact current-pin refusals
before credentials/effects. Historical producer/observer/reader/receipt
identities remain immutable.

The following migration belongs only to the prior producer task and explains
the current frozen controller and this task's starting reader bytes:

| Current-byte role | Before SHA256 | After SHA256 |
| --- | --- | --- |
| Shared controller | `a7c44ce7224b02f31865620e482d0ff6964f36d2b4c4753658e3ecfc72dcbc58` | `957934b869ed5071923add7e9554aa68de941c9488f3e6d650557d27f6179601` |
| Shared fresh reader | `5bfba1a2cb4d4f5190b0d146fd7b2b890c72ecf3904974d37babfea9ed8661f0` | `cd88a768e573d57c82d8f14bcb266ae455187933fb8a5b70da0fadafe17bea46` |

In that prior task, only the reader's current controller pin changed. This
reader extension does not alter that controller or its exact current pin.
The unchanged keep/r2 facade
has SHA256 `12106b5423e25ffefa1b04023e2e98742861762762966a04bf17fe3da1851450`.
R2 already explicitly refuses keep/r2 before source/private-input reads; its
producer bytes and exact pre-import/credential pin did not need a migration.

| Unchanged current-byte role | SHA256 |
| --- | --- |
| Fresh/r1 facade and shared publication helper | `a0710039c33c17af85f226269ceeaccdb1c17bbc7238a46a15614226afed26e3` |
| Fresh/r2 producer | `8b387ec5d172f74c4e6d2e1b93973c674e973f3cbba47b640184c126312ab00f` |
| CI verifier | `8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c` |
| Original keep/r1 intake | `df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196` |

Core/runtime/model/input/grader/registration bytes remain unchanged. Historical
observer source 910, reader `bbb46c87ac840317a4f41959d2278677ed29e52e7ae28f49cf47db7a464eaafa`
and observation `36df4b36135d0c45db53a23c4f88fde360695f80bad0437735436516ebb626ea`
remain immutable; current helper checks do not replace old evidence.

Prior PR717 HEAD `60f2a334bd76de197cdac668a635ffe1c2e427af`, owner review
[5384875894](https://github.com/hyeonsangjeon/gdpval-realworks/pull/717#pullrequestreview-5384875894)
and all 10 checks passed their source gate. Its
[immutable completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/60f2a334bd76de197cdac668a635ffe1c2e427af/tasks/LATEST_TASK_RESULT/README.md)
preserves the separate tested `d92cac628490baf40ceb8c0a76e38fb6cfd6e985`
2-pass/14.64s reader proof, r2 preparation/approval and one jobs-metadata binding,
plus the PR716 compatibility decision and 49.90s/2.61s proofs. None was repeated
or relabeled as current reader validation.

### Preserved fresh/r1 terminal-only observation and consumed inference

The leader directly read
[observation run 36884357472 / job 110443771878](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36884357472/job/110443771878)
at source `910cbdbc49da764a76932bab3af4af231a0b6771`. Its receipt at
`2026-10-01T15:29:46.3223244Z` reports `terminal_verified`, observation SHA256
`36df4b36135d0c45db53a23c4f88fde360695f80bad0437735436516ebb626ea`.
Its historical reader SHA256 remains
`bbb46c87ac840317a4f41959d2278677ed29e52e7ae28f49cf47db7a464eaafa`.
Approval/execution jobs were skipped. This coding task did not repeat that read.

Fresh/r1 is consumed with recorded `status=failed`, exit code 1,
`cleanup_confirmed=true`, `recorded_publication_acknowledged=true` and
`grade=null`. The fixed producer is `e39d8d1aadcb816d09588829a5ec4929b33083e6`,
run `36845127347` / attempt 1 / execution job `110323708382`, request SHA256
`5bbb0e4cb5ae9444eac9c804ac3c8d2f6d39acbec63e7f7de78d7f2ee35fcf02`.

| Verified control identity | Recorded value |
| --- | --- |
| Terminal | `45f54eb0a24aee5d40dd41b276ff5df777f06d73`; SHA256 `2fa29205d842956fcbd857e4b1e1878af4551ebddc7573e480d7e17d01b63faa`; 4206 bytes |
| Claim | `4bff20bdae3cddb28519eadec9f032af5b6843d5`; SHA256 `0ed2ab8979fd918218415ee08eee5ad99d9d3a9e08b41695f0b30e2afd0cc1c4`; 1484 bytes |
| Output | `3b27e0a7e9d05c9ecfb400040bd8c025bc7f2484`; manifest SHA256 `f48abaab90af661811b257d709a0934819ef057854976694a543e4ed76cd3380`; 2125 bytes |
| Output object set | `output_objects_sha256=1ac663171c092a21edd0287e2749daab3e216dcbee1efa14b5ea70eab4853c1a` |

Declared payload roles are inference result 1, ledger 1 and deliverables 0;
3 output objects include the manifest. These are verified declarations and
metadata, not payload-body verification or proof that all work/files are absent.
The publication-derived observation is not independent provider authentication,
original-input revalidation or Git-parent/CAS ancestry verification. Recorded
publication acknowledgment does not make the observer the writer;
`writer_acknowledgment=not_established`, `payload_bodies_verified=false` and
`grading_input_ready=false` remain explicit. Grade null is not zero.

The recorded receipt has 39 model calls: an infrastructure-retry component of
38 and a generation component of 1. Known/model cost is USD `0.303358`, partial;
`estimated_cost_usd`, `runtime_cost_usd` and HTTP request count are null, with
missing reasons `call_reachability_unknown` and `usage_absent`, and
`invoice_complete=false`. Recorded usage is input 104289, cached input 22144,
output 6164 and reasoning 3863. Cached input and reasoning are subsets, not
additional token totals. Calls are not HTTP requests or native admission/resume
counts, and partial known cost is not a total or invoice.

`detailed_failure`, `budget` and `recovery_exposure` remain unavailable/null with
reason `not_recorded_in_terminal_controls`. Neither the roughly 180-minute step
nor retry labels establish timeout, rate limiting or another cause. These
unknowns do not justify a repeat, another observer or expanded data access.

The earlier final CLI receipt remains distinct from this later control read.

The leader directly read
[run 36845127347 / attempt 1 / execution job 110323708382](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36845127347/job/110323708382)
at producer `e39d8d1aadcb816d09588829a5ec4929b33083e6`, workflow `370228282`,
`.github/workflows/codex-retention-first-cell.yml`. All workflow jobs completed
successfully. The actual final CLI receipt at `2026-10-01T13:22:50.8088344Z`
reported the exact fresh cell, `status=failed`, `remote_terminal=acknowledged`,
`cleanup_confirmed=true`, `grade=null`, `grading_launched=false` and
`invoice_complete=false`, with request SHA256
`5bbb0e4cb5ae9444eac9c804ac3c8d2f6d39acbec63e7f7de78d7f2ee35fcf02`.
Its green workflow status is not task success. The later observation above
supplies control identities and recorded accounting, not a failure explanation.

Execution-side preparation reproduced that request digest and fresh materialized
grader source `298da1d3a36482cf87e7f896d47c8c6c64bf5e1df91dd244847640d9d00a3689`;
signed approval verification succeeded. This is not the consumed keep/r1 grader
identity `c391424e7ff45f375c6bb17135440aab85b29748fa0c52215805594a1517a320`.
Earlier preparation job `110313331439` reported `prepared_not_admitted` at
`2026-10-01T09:51:41.9510199Z`, verifying four original input roles from bundle
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Exactly one owner approval was confirmed in environment `grading`
`18744914306`, deployment `6781320183`, using
`approve-retention-first-cell sha256:`; approval job `110314366065` was queued
afterward. Those preparation/approval facts remain distinct from the later
failed receipt. This coding task did not follow, poll or read that run.

### Actual verified keep/r1 readout, separate from offline proof

The leader directly read
[run 36820845596 / attempt 1 / pilot-readout job 110235885096](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36820845596/job/110235885096)
at source `f30c9efa392bc14cba790fb5d1dedf12071a5677`. Its receipt at
`2026-10-01T05:43:22.3151574Z` reported `verified_writer_recorded_grade`, stage
`verified`. All paid/writer/generic jobs were skipped. That read did not call a
model or regrade; this coding task did not retrieve raw private grade content.

The consumed grade writer is `29e0353f1539265b1741e71be894fedf9be32a8b`,
run `36776393736` / `pilot-live` / attempt 1. Grade terminal
`40712e0980cc05c31688fdbb98c693774fb90c0d` has SHA256
`11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234`,
3119 bytes, and claim `dec305d669e3ca2e53c7f7b9ebfbe7974d661350`.

For keep/r1 cell
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1`:

| Recorded projection | Value and limit |
| --- | --- |
| Score | 30.6 / included possible 45 = 68.0%; full-denominator percentage 54.64% |
| Exclusions | 9 items, maximum score 11.0; the 13.36 percentage-point difference is a denominator effect, not treatment uplift |
| Task outcome | One scored task, no recorded task error; payload `run_status=diagnostic` |
| Coverage | `judge_items=49`, `rubric_items=40`, `passed_items=25`, `rubric_item_coverage=0.625`; recorded projection, not independent rubric revalidation or a validated quality explanation |
| Grader ledger | Present; 93 recorded model calls, `input_tokens=270190`, `cached_input_tokens=212025`, `output_tokens=16031`, `reasoning_tokens=10481` |
| Grader cost | Partial, `missing_reasons=[price_missing]`; known/model/estimated/runtime USD fields null, HTTP request count null, `invoice_complete=false` |

Cached input and reasoning tokens are subsets, not additions to their parent
token counts. Recorded model calls are not HTTP requests. No price or invoice
was reconstructed. Coverage and excluded items do not independently explain
the quality of this result.

The proof is
`verified_publication_derived_not_independent_provider_authentication`.
`materialized_input_fingerprint` remains `{status: unavailable, value: null,
comparison: null, reason: materialized_input_fingerprint_not_recorded}`.
The original result fingerprint, preparation digest and materialized grading
input remain distinct; this read does not fabricate an intermediate comparison.

### Fixed predecessor, study limits and remaining live gate

Keep/r2 requires the failed fresh/r2 terminal `1d5133590911f3704fc2a65279d4b64bee77c1d6`
and the independently fixed control identities above. The actual shared inference
branch must still equal that terminal before one-use CAS; drift refuses without
adoption or reset. Fresh/r2 retains its historical failed-fresh/r1 predecessor
`45f54eb0a24aee5d40dd41b276ff5df777f06d73`
and its fresh/r1 control identities in the preserved section. A completed failure
with confirmed cleanup can
precede the next predeclared cell; an incomplete or ambiguous claim cannot.
Neither the keep/r1 terminal nor its grade is the fresh/r2 predecessor.

The keep/r1 inference remains fresh/r1's historical predecessor, not its grade:
producer `e355faf9a6212175a288e8473968915ffb2408d0`, run `36696961231`, request
SHA256 `ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68`;
terminal `de50ff0aa6037c0ef6e3b713da519359abd1d08d`, SHA256
`0821af11393cab65d1e14259e43b14872b94a431496e8c1e3c38e719f33f21b8`,
6449 bytes; claim `3fc283087a020caec574e8c9b8e9bc3ca593e88a`; output
`43cbf8e265297813857172ecee51256cc17f2d36`. The delivered fresh/r1 reader checks
this exact recorded reference, never adopts it as the fresh result or replays it.

The registered order remains Task4 keep1/fresh1/fresh2/keep2, then Task5
fresh1/keep1/keep2/fresh2. Four of eight producer outcomes are now reported;
fresh/r1 and fresh/r2 are consumed with verified failed controls and unavailable
detailed causes. Keep/r2 is consumed with a leader-reported succeeded receipt,
but its publications and accounting remain unread and it is ungraded.
Four Task5 cells remain outstanding. The original
30-cell pilot is complete and is not reopened. This eight-cell study is
post-selected and not representative; one score is not evidence of benefit.
Two repetitions, service variation and an uncalibrated judge remain registered
limitations. The keep/fresh comparison changes the native-thread/owned-files
retention bundle under mechanical B, not the model, inputs, rubric, budget
policy or C feedback.
The decision rule still requires keep-only deliverable advantage in both pairs
within a predeclared task with no reverse pair. No recovery opportunity stays
in the denominator and is uninformative about retention.

GPT-5.4 direct-v1/xhigh, SDK/CLI 0.147.0 and original input/rubric revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf` remain fixed. Mechanical B, no C,
the registered KEEP bundle for ordinal 3, temporary carveouts and one concurrent
inference are unchanged. By registration, this distinct cell's 10800-second
cumulative clock starts at its own admission and includes waits, recovery and downtime
without reset; it does not reset either consumed fresh cell's clock. The
1800-second native-turn wait is not an all-in attempt ceiling. There is no fixed
admission count or automatic monetary cutoff.

One task's repeats do not establish retention benefit or explain either fresh
failure. This reader task grants no launch or replay authority. The pre-edit
decision is resolved, and the 1113 runner-only replacement passed at the
unchanged tested HEAD after the preserved pre-collection failure. The actual
new diff and saved proof still need independent final source review and
applicable CI before the leader separately authorizes a successful-result
read bound to the reviewed reader source/hash and exact producer/run/attempt/
request/cell/job above. That later route requires `read_result=true`,
`observe_terminal=false`, `prepare=false`, `execute=false` and
`observe_locator=false`, with the exact keep/r2 cell. Keep/r2's unread terminal
is discovered once, with immutable revisions thereafter.
Missing, ambiguous or corrupt records must refuse without polling, fallback,
replay or budget reset. Terminal-only mode remains explicitly separate and
cannot turn the known succeeded receipt into failed/stopped evidence or a
successful payload intake. No live observer or grade ran.
The leader's local M4 files remain unavailable and were not updated.

### Preserved history and reporting scope

The [immutable prior observer record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ea8e7d36693678cedb54fbe277af5cc874360061/tasks/LATEST_TASK_RESULT/README.md)
retains the separate tested `386390b8db59df92f8b297d21d0b99a712887da9` proof:
2 collected, 2 passed in 14.86s, exit 0, no timeout, with both exact selectors
and all reached boundaries. Log SHA256:
`d9f7c3217cb1f1d843e47f6854e5fd2bd832eb0fd7568b6f5a98b0148318a128`.
Its observation marker, default-success isolation, frozen hashes and review
history remain intact. That synthetic proof is neither the actual later
terminal observation nor fresh/r2 validation.

The [immutable prior reader record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/710860be12f26bcf5b60312974c31aff7499eda4/tasks/LATEST_TASK_RESULT/README.md)
retains the separate `56bb86a7cdca02c7f0f9ef8055d3e44f8df8aaaf` proof:
2 collected, 2 passed in 11.06s, exit 0, no timeout; log SHA256
`eabc583e6f50aa61211cfc28aefc132c0326892b923eedcbe6989bb0f15c037e`.
Its successful-result intake, type-coercion review correction and prior source
review `5377303231` are not current keep/r2 reader validation.

The [immutable prior completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/e39d8d1aadcb816d09588829a5ec4929b33083e6/tasks/LATEST_TASK_RESULT/README.md)
retains the exact reached/unreached boundaries and logs for `c291670`'s 2.68s
source-pin failure, `53e5dc2`'s 5.71s missing-`run_id` fixture failure,
`5b788b7`'s separate 34.90s two-selector pass, PR713 CI run `36834022780` /
job `110276977686` (1 failed, 13303 passed, 64 skipped, 46 deselected in
1301.15s), and `a378df8`'s separate 2.08s entrypoint pass. They were not replayed
or relabeled as current reader proof.

Failed readouts `36801558936` and `36811186015`, earlier offline failures and
passes, successful producer `36696961231`, verified intake `36739260150`, the
consumed grade and the NAS prerequisite refusal remain distinct in that
record and its immutable history links. Original inference accounting remains
partial: 10 recorded model calls, known cost USD `0.409894`, runtime cost null,
missing `call_reachability_unknown`, not grader accounting or an invoice.
Its original `grade=null` / `grading_launched=false` receipt is
not rewritten by the later grade and numeric readout.

The full skill catalog was checked once for this phase. `experiment-design` preserved the
registered constraints without a new treatment, sample, repeat or budget.
`experiment-report-en`, then protected `im-not-ai-en`, applied only to the
bounded runner-failure/replacement-proof and remaining-gate update. Unchanged
score/accounting/limit paragraphs were not re-audited or rewritten. Literal checks and a local
reverse-condition check do not constitute independent review or implementation
validation. UI/animation, new-study and generic-framework skills were not
applicable. Only these completion records change after the tested HEAD; the
reader, workflow, tests and all pins remain identical to the replacement proof.

The old PR713/PR714/PR715/PR716/PR717/PR718 worktrees, other records, `wip/local-main-preserved-20260719` and
private NAS refusal directory remain untouched. The existing Git identity is
`hyeonsangjeon <wingnut0310@gmail.com>`, without attribution/session trailers.
The leader's local M4 checkout is unavailable and was not updated. No workflow
dispatch/polling, live HF/OIDC/Azure/model/grade/readout, inference replay,
permission change, Project edit or merge occurred. These records stop at
pre-merge facts.
