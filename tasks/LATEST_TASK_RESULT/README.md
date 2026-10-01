# Latest task result

## PROJECT5-FRESH-FAILED-TERMINAL-20261001-2250

The opt-in Task4 fresh/r1 terminal-only observer passed its single offline
invocation at tested HEAD `386390b8db59df92f8b297d21d0b99a712887da9`:
2 collected, 2 passed in 14.86s, exit 0, with no outer timeout. Both the new
control-only selector and the changed mode-routing selector completed. This
is synthetic offline proof, not a live observation or a new inference/grade.

Separately, the leader supplied the completed inference's acknowledged
`status=failed` receipt. The inference is consumed and must not be replayed.
Its detailed cause, immutable revisions, artifact declarations and accounting
remain unread. A green workflow is not model success; `grade=null` is not zero.

### Closed terminal observation and review boundary

`codex_retention_fresh_r1_result_intake.py --observe-terminal` binds only
ordinal 1, `3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_fresh_r1`,
in campaign `retention_bundle_diagnostic_20260929`. After one discovery of its
fixed terminal path, it downloads only the immutable terminal, hash-bound
claim and output manifest. Declared result, ledger and deliverable objects
receive metadata/history checks only. No payload bodies, original inputs,
predecessor payloads or native state are read.

Independent fixed expectations constrain the source/run/request/cell,
preceding inference reference and supplied execution job `110323708382`.
The failed/stopped validator retains their distinction, exact exit-code types,
cleanup and false grading fields, normalized recorded accounting, canonical
bytes, role/privacy/size bounds and immutable object history. Missing result
declarations require an empty file list under the writer's existing contract.
The default successful-result intake and its refusals remain unchanged; there
is no fallback from `--read` to terminal observation.

A distinct `retention-task4-fresh-r1-terminal-observation-v1` record and
`retention-fresh-r1-terminal-observation.json` marker support private
no-clobber publication/readback. Only final local acknowledgment returns
`outcome=terminal_verified`. An ambiguous marker remains private and cannot
be adopted as success. The receipt reports immutable identities, recorded
status/exit/cleanup, declared-role counts and recorded receipt/missing fields.
It never reports successful intake or grading readiness. Detailed failure,
budget and recovery exposure are unavailable/null with reason
`not_recorded_in_terminal_controls`; it does not infer a cause or absence of
deliverables from an empty declaration.

The proof is publication-derived, not independent provider authentication,
original-input revalidation or Git-parent/CAS ancestry verification. Expected
workflow/attempt and supplied grader/input digests remain separate from
recorded fields. `payload_bodies_verified=false`, `grading_input_ready=false`,
`writer_acknowledgment=not_established`, `grade=null`, HTTP request count null
and `invoice_complete=false` remain explicit. Recorded calls are not HTTP
requests; partial known cost is not a total or invoice.

The existing contents-read preparation job has an observe-only preflight/step
pair. Source/workflow equality and reader/helper hashes precede the same
step-scoped HF secret. `observe_terminal` defaults false and conflicts with
`read_result`, `prepare`, `execute` and `observe_locator`; only fresh/r1 is
allowed. Plan/preparation, protected approval and execution paths are excluded.
Keep/r1 command bodies and all frozen CI/intake/producer/controller/runtime/
model/input/grader/registration bytes are unchanged. No job, permission or
credential was added. Reader SHA256:
`bbb46c87ac840317a4f41959d2278677ed29e52e7ae28f49cf47db7a464eaafa`.

The worktree began from verified main
`0f8a1c6a8330c51761d7cd1099b5ef084a33e254`. The mandatory bounded
CI/auth/storage/workflow decision preceded edits; the narrow diff review
approved the implementation later pinned as the tested HEAD. Prior reader
HEAD `710860be12f26bcf5b60312974c31aff7499eda4`, owner review
[5378531408](https://github.com/hyeonsangjeon/gdpval-realworks/pull/714#pullrequestreview-5378531408)
and its all-10-check result remain prior evidence, not approval of this delta.
The delivered reader's 1553-line review and 11.06s selector were not repeated.

### Actual failed inference, separate from offline proof

The leader directly read
[run 36845127347 / attempt 1 / execution job 110323708382](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36845127347/job/110323708382)
at producer `e39d8d1aadcb816d09588829a5ec4929b33083e6`, workflow `370228282`,
`.github/workflows/codex-retention-first-cell.yml`. All workflow jobs completed
successfully. The actual final CLI receipt at `2026-10-01T13:22:50.8088344Z`
reported the exact fresh cell, `status=failed`, `remote_terminal=acknowledged`,
`cleanup_confirmed=true`, `grade=null`, `grading_launched=false` and
`invoice_complete=false`, with request SHA256
`5bbb0e4cb5ae9444eac9c804ac3c8d2f6d39acbec63e7f7de78d7f2ee35fcf02`.
The roughly 180-minute step does not establish timeout, rate limiting or
another failure cause. Terminal/claim/output revisions, declared artifact
counts, usage/cost, detailed reason and recovery exposure have not been read.

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

### Exact offline validation

```text
tests/test_codex_retention_fresh_r1_terminal_observation.py::test_fresh_r1_terminal_observation_is_controls_only_and_non_authorizing
tests/test_codex_retention_ci_read_result.py::test_retention_result_read_workflow_is_fixed_and_model_free
```

Each selector passed in the single 14.86s invocation under CPython 3.10.12 /
pytest 9.1.1, `-v --tb=short -p no:cacheprovider`, plugin autoload disabled,
token-free `GITHUB_ACTIONS=true` and synthetic `pull_request`/`pytest` metadata.
Existing process/network/credential guards remained active. The 180-second
outer timeout did not fire. Log SHA256:
`d9f7c3217cb1f1d843e47f6854e5fd2bd832eb0fd7568b6f5a98b0148318a128`.

Real validators with synthetic controls/transport reached failed/stopped
observation with absent, result-only and partial-payload declarations; exact
identity/proof limits; source/run/request/cell/predecessor and job refusals;
corruption/history/type-coercion/role/privacy/bounds refusals; missing controls;
no-clobber and ambiguous acknowledgment; safe error redaction; default success
isolation; and final no-effects assertions. Payload downloads were forbidden.
The coupled routing selector covered all 32 mode combinations, unchanged keep
command bodies, exclusive read credentials and paid-route exclusion. No
selected assertion remained unreached. No successful validator verdict was
substituted, and no prior reader selector or live integration was replayed.

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

Fresh/r1's fixed predecessor is the keep/r1 inference, not its grade:
producer `e355faf9a6212175a288e8473968915ffb2408d0`, run `36696961231`, request
SHA256 `ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68`;
terminal `de50ff0aa6037c0ef6e3b713da519359abd1d08d`, SHA256
`0821af11393cab65d1e14259e43b14872b94a431496e8c1e3c38e719f33f21b8`,
6449 bytes; claim `3fc283087a020caec574e8c9b8e9bc3ca593e88a`; output
`43cbf8e265297813857172ecee51256cc17f2d36`. The reader checks this exact recorded
reference, never adopts the predecessor as the fresh result or replays it.

The registered order remains Task4 keep1/fresh1/fresh2/keep2, then Task5
fresh1/keep1/keep2/fresh2. Fresh/r1 is consumed with an acknowledged failed
status; its detailed control evidence remains unread. The other six cells
remain outstanding. The original
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
the fresh bundle for ordinal 1, temporary carveouts and one concurrent inference
are unchanged. The 10800-second cumulative clock includes waits, recovery and
downtime without reset; 1800 seconds is the native-turn wait, not an all-in
attempt ceiling. There is no fixed admission count or automatic monetary cutoff.

The failed fresh receipt does not establish retention benefit from this pair
or explain the failure. Immutable new-HEAD owner review and CI remain required.
A later terminal-only observation needs separate leader direction at the
then-reviewed main reader/workflow SHA: exact fresh cell, `observe_terminal=true`,
`read_result=false`, `prepare=false`, `execute=false`, `observe_locator=false`.
The producer source/run/request/job above remain fixed and separate from the
reader source. Missing, ambiguous or corrupt controls refuse; there is no
automatic retry, inference replay, regrading or authority for another cell.

### Preserved history and reporting scope

The [immutable prior reader record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/710860be12f26bcf5b60312974c31aff7499eda4/tasks/LATEST_TASK_RESULT/README.md)
retains the separate `56bb86a7cdca02c7f0f9ef8055d3e44f8df8aaaf` proof:
2 collected, 2 passed in 11.06s, exit 0, no timeout; log SHA256
`eabc583e6f50aa61211cfc28aefc132c0326892b923eedcbe6989bb0f15c037e`.
Its successful-result intake, type-coercion review correction and prior source
review `5377303231` are not this terminal-only observation's validation.

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

The old PR713/PR714 worktrees, other records, `wip/local-main-preserved-20260719` and
private NAS refusal directory remain untouched. The existing Git identity is
`hyeonsangjeon <wingnut0310@gmail.com>`, without attribution/session trailers.
The leader's local M4 checkout is unavailable and was not updated. No workflow
dispatch/polling, live HF/OIDC/Azure/model/grade/readout, inference replay,
permission change, Project edit or merge occurred. These records stop at
pre-merge facts.
