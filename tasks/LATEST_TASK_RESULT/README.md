# Latest task result

## PROJECT5-FRESH-R2-READER-20261002-0400

The fixed fresh/r2 result and terminal read paths passed at tested HEAD
`d92cac628490baf40ceb8c0a76e38fb6cfd6e985`: 2 collected, 2 passed in 14.64s,
exit 0. The 180-second outer timeout did not fire. This is synthetic offline
reader evidence, not a live read, model usage or an observed fresh/r2 outcome.

The existing fresh reader now accepts exactly two fixed r1/r2 bindings. Public
constants and calls without an explicit binding remain r1, including the frozen
r2 producer's failed-r1 predecessor validation. Successful-result mode still
requires success and verifies declared immutable payloads. Explicit terminal
mode accepts only failed/stopped controls and downloads only terminal, claim
and manifest bodies plus declared-object metadata/history. It does not verify
payload bodies, establish grading readiness or silently fall back between modes.

Both r2 routes use the existing contents-read preparation job, mutually exclusive
modes and precredential source/reader/helper checks. Keep/r1 commands are
unchanged. The three-job set, workflow inputs, permissions, secret scope,
controller and producer bytes remain unchanged; preparation, approval,
execution, model and grade paths remain unreachable from either read route. Only the existing fresh read
conditions and commands were extended to the exact r2 cell.

### Actual r2 preparation and approval, not an observed outcome

The leader supplied run `36907894862` / attempt 1 / workflow `370228282` at
producer `5a9614ac04464c4e0a5e80297f54c3a5c9443bae`, verified as main before
selecting this clean worktree. The cell is ordinal 2 in campaign
`retention_bundle_diagnostic_20260929`:
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_fresh_r2`.
It is the next registered repetition, not a retry of consumed failed fresh/r1.

Preparation job `110522963099` succeeded. Its receipt at
`2026-10-01T18:37:35.5826822Z` reported `prepared_not_admitted`, exact fresh
scope and request SHA256
`4798c119ea2d06c7c902ae51638bdba25c5bfaf683a2223d286fd7e652d3b317`.
The path-specific materialized grader identity is
`4860a408791b7b313e2c06c2863b4a1ddbae467c8425365af8908be7a3c032d6`.
Preparation verified four original roles from bundle
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
These are supplied preparation facts, not independent input verification by
this reader. Exactly one owner approval bound that request in environment
`grading` `18744914306`, deployment `6792272908`; approval job `110524083305`
was queued afterward.

The one authorized jobs-metadata read bound `retention-execute` job
`110535767415` to that exact source, run and attempt. Saved projection SHA256:
`5f8e2b2b4ab295ec0bd6719787319e2e828569d9476105e09442528dd6bcf24b`.
No logs or status projection were read, and no second query was made. Model
admission, outcome, terminal revision, usage, cost and grade remain unobserved.
The reader independently fixes source/run/request/cell/job and the preceding
failed-r1 terminal `45f54eb0a24aee5d40dd41b276ff5df777f06d73`; it never treats
a fetched terminal as its own expected evidence.

### One offline proof

The single invocation used CPython 3.10.12 / pytest 9.1.1, token-free CI-shaped
ambient metadata, existing network/process/credential guards and no `-x`.

| Selector, relative to `batch-runner` | Result |
| --- | --- |
| `tests/test_codex_retention_fresh_r2_read.py::test_fresh_r2_reads_only_its_fixed_result_or_terminal` | PASS |
| `tests/test_codex_retention_ci_read_result.py::test_retention_result_read_workflow_is_fixed_and_model_free` | PASS |

Both completed in the aggregate 14.64s above. Log SHA256:
`bd2129ca0fd2bb111207e7659472ef33e17e05aaff2d565f72a716cd8ddafe37`.
Real validators with synthetic transport reached successful payload intake and
failed/stopped control-only observation, exact identities/proof limits, wrong
source/run/request/cell/job/predecessor refusals, type/hash/history/role/privacy/
bounds checks, missing or ambiguous controls, no-clobber/readback and redaction.
Wrong current hashes refused before credentials or effects. The route selector
checked current YAML, all 32 mode combinations, unchanged keep/r1 routing and
real no-token refusals for both fresh cells.

Small compatibility checks retained default-r1 successful intake and the frozen
r2 producer's omitted-binding r1 control validation. Its independent real-world
byte pins then correctly refused the synthetic predecessor; no pin or validator
verdict was substituted. Terminal mode made no payload-body downloads, and no
execution, model, remote write, claim or grade effect occurred. No delivered
reader suite, private integration, full suite or second invocation ran.

The required bounded auth/storage/workflow reviewer approved the closed binding
before edits, approved the seven-file delta, and closed the review with APPROVE
after reading the saved proof. This does not replace new-head owner review, CI
or explicit leader direction for a later live read.

### Current reader hash migration, not historical evidence replacement

Only the current reader module hash changed, from
`c19c970d0a0cd1c206a3f3a9286995f7c75e3237791f0220ccaf951c857bcdd9` to
`5bfba1a2cb4d4f5190b0d146fd7b2b890c72ecf3904974d37babfea9ed8661f0`.
Both fresh workflow preflights and CLI expectations carry the new exact hash.
R2 also checks its unchanged producer file before import and before credentials.

| Unchanged current-byte role | SHA256 |
| --- | --- |
| Shared controller | `a7c44ce7224b02f31865620e482d0ff6964f36d2b4c4753658e3ecfc72dcbc58` |
| Fresh/r1 facade and shared publication helper | `a0710039c33c17af85f226269ceeaccdb1c17bbc7238a46a15614226afed26e3` |
| Fresh/r2 producer | `8b387ec5d172f74c4e6d2e1b93973c674e973f3cbba47b640184c126312ab00f` |
| CI verifier | `8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c` |
| Original keep/r1 intake | `df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196` |

Core/runtime/model/input/grader/registration bytes remain unchanged. Historical
observer source 910, reader `bbb46c87ac840317a4f41959d2278677ed29e52e7ae28f49cf47db7a464eaafa`
and observation `36df4b36135d0c45db53a23c4f88fde360695f80bad0437735436516ebb626ea`
remain immutable; current helper checks do not replace old evidence.

Prior PR716 source `a3bb5e066b2ad842c98b1f85c91eb54e37c17d96`, owner review
[5383384460](https://github.com/hyeonsangjeon/gdpval-realworks/pull/716#pullrequestreview-5383384460)
and all 10 checks passed their source gate. The
[immutable prior completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/a3bb5e066b2ad842c98b1f85c91eb54e37c17d96/tasks/LATEST_TASK_RESULT/README.md)
retains the pre-edit freeze blocker, explicit compatibility decision, original
hash migration and review `5383071826`. Its tested
`f7d11ae4c8ac225b4027086df07771adfb96d78e` 2-pass/49.90s proof and
`04c203b9e8bd5a0ac61cd8b7a6e5ac462712f682` 1-pass/2.61s correction remain
separate from this reader proof; neither was rerun or relabeled.

### Actual terminal-only observation and consumed inference

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

Fresh/r2 requires the failed fresh/r1 terminal `45f54eb0a24aee5d40dd41b276ff5df777f06d73`
and the exact identities above. A completed failure with confirmed cleanup can
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
fresh1/keep1/keep2/fresh2. Two of eight outcomes are recorded; fresh/r1 is
consumed with a verified failed terminal and unavailable detailed cause.
Six cells remain outstanding, beginning with fresh/r2. The original
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
the registered fresh bundle for ordinal 2, temporary carveouts and one concurrent
inference are unchanged. This distinct cell's 10800-second cumulative clock
would start at its own admission and include waits, recovery and downtime
without reset; it does not reset fresh/r1's clock. The 1800-second native-turn
wait is not an all-in attempt ceiling. There is no fixed admission
count or automatic monetary cutoff.

The failed fresh receipt does not establish retention benefit from this pair
or explain the failure. The existing r2 run was separately approved; this coding
task neither followed its execution nor established an outcome. After new-head
owner review and CI, the leader must separately authorize a read bound to the
reviewed reader source and the exact producer/run/attempt/request/cell/job above.
Use `read_result` only for successful intake or explicit `observe_terminal` for
failed/stopped controls, with every other mode false. This task dispatches
neither mode. Missing, ambiguous or corrupt controls must refuse without
polling or fallback; no new inference, replay, regrading or budget reset is
authorized. The leader's local M4 files remain unavailable and were not updated.

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
review `5377303231` are not the new r2 read validation.

The [immutable prior completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/e39d8d1aadcb816d09588829a5ec4929b33083e6/tasks/LATEST_TASK_RESULT/README.md)
retains the exact reached/unreached boundaries and logs for `c291670`'s 2.68s
source-pin failure, `53e5dc2`'s 5.71s missing-`run_id` fixture failure,
`5b788b7`'s separate 34.90s two-selector pass, PR713 CI run `36834022780` /
job `110276977686` (1 failed, 13303 passed, 64 skipped, 46 deselected in
1301.15s), and `a378df8`'s separate 2.08s entrypoint pass. They were not replayed
or relabeled as this reader's proof.

Failed readouts `36801558936` and `36811186015`, earlier offline failures and
passes, successful producer `36696961231`, verified intake `36739260150`, the
consumed grade and the NAS prerequisite refusal remain distinct in that
record and its immutable history links. Original inference accounting remains
partial: 10 recorded model calls, known cost USD `0.409894`, runtime cost null,
missing `call_reachability_unknown`, not grader accounting or an invoice.
Its original `grade=null` / `grading_launched=false` receipt is
not rewritten by the later grade and numeric readout.

The full skill catalog was checked once. `experiment-design` preserved the
registered constraints without a new treatment, sample, repeat or budget.
`experiment-report-en`, then protected `im-not-ai-en`, applied only to the
bounded current-result update; unchanged score/accounting/limit paragraphs
were not broadly rewritten. UI/animation, new-study and generic-framework
skills were not applicable.

The old PR713/PR714/PR715/PR716 worktrees, other records, `wip/local-main-preserved-20260719` and
private NAS refusal directory remain untouched. The existing Git identity is
`hyeonsangjeon <wingnut0310@gmail.com>`, without attribution/session trailers.
The leader's local M4 checkout is unavailable and was not updated. No workflow
dispatch/polling, live HF/OIDC/Azure/model/grade/readout, inference replay,
permission change, Project edit or merge occurred. These records stop at
pre-merge facts.
