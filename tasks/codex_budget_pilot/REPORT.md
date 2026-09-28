# Codex external-budget pilot: report for review

This leader-verified report contains **24 unique epoch04 projections: 18 graded and 6 model-free UNGRADED, with 0 pending and no duplicates**. Together with six separate frozen epoch03 T1 failure outcomes, it documents all 30 original cell IDs—not 30 successful same-protocol runs or 30 epoch04 cells.
The observations are high T2/T3 scores, moderate T4 scores with large exclusions, and poor or missing T5 grades. They do not establish a causal model or condition ranking.

## Conditions and original task identities

The [approved pilot design](../../batch-runner/experiments/execution_envelope/codex_external_budget_pilot.yaml) specifies 5 original tasks × A/B/C × 2 repetitions = 30 original cell IDs, ordered A1/B1/C1/C2/B2/A2 (ABC/CBA) within each task.
Inference settings are GPT-5.4 on Foundry `direct-v1`, `xhigh`, SDK `0.147.0`. Ordinary grading uses [default_v2_sol_max.yaml](../../batch-runner/grading_configs/default_v2_sol_max.yaml), GPT-5.6 Sol at `max`, once per result, with no low-score regrade.
There is 1 inference slot. Each cell has 180 cumulative minutes, including wait and recovery, with a 30-minute attempt limit; a restart does not reset that budget.
A allows at most 4 fresh attempts. B uses mechanical native continuation. C keeps the same budget and retention, adding host-validated adaptive feedback.
A/B confounds retry policy with retention. B/C is the feedback contrast, not retention-only proof. This finite pilot has no automatic monetary cap and authorizes no expansion to 30 tasks or 220 tasks.

| Label | Original task ID |
| --- | --- |
| T1 | `02aa1805-c658-4069-8a6a-02dec146063a` |
| T2 | `0112fc9b-c3b2-4084-8993-5a4abb1f54f1` |
| T3 | `2ea2e5b5-257f-42e6-a7dc-93763f28b19d` |
| T4 | `3baa0009-5a60-4ae8-ae99-4955cb328ff3` |
| T5 | `0818571f-5ff7-4d39-9d2c-ced5ae44299e` |

## Epoch04 readout results

Pairs are **included percentage / full-denominator percentage**. NG means model-free UNGRADED; a dash means no numeric grade, not zero. Each linked run is the supplied GitHub readout evidence; none was queried for this report.
Each T2 grade excludes 1 item worth 1 maximum point: included denominator 65, full denominator 66. T3 has no exclusions.
Each of the four T4 grades excludes 9 items worth 11 maximum points: included denominator 45, full denominator 56. Exclusion causes and overlap of excluded item IDs are **UNREAD**; identical counts do not establish identical exclusions.

| Task | Cell | Projection | Included % / full % | Readout run |
| --- | --- | --- | --- | --- |
| T2 | A1 | graded | 96.00 / 94.55 | [36183957201](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36183957201) |
| T2 | B1 | graded | 96.85 / 95.38 | [36209591238](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36209591238) |
| T2 | C1 | graded | 96.15 / 94.70 | [36217589922](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36217589922) |
| T2 | C2 | graded | 95.62 / 94.17 | [36217785761](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36217785761) |
| T2 | B2 | graded | 96.85 / 95.38 | [36219088500](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36219088500) |
| T2 | A2 | graded | 97.77 / 96.29 | [36220575848](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36220575848) |
| T3 | A1 | graded | 98.12 / 98.12 | [36307908959](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36307908959) |
| T3 | B1 | graded | 97.88 / 97.88 | [36308161995](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36308161995) |
| T3 | C1 | graded | 98.18 / 98.18 | [36309455833](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36309455833) |
| T3 | C2 | graded | 97.06 / 97.06 | [36309729266](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36309729266) |
| T3 | B2 | graded | 96.41 / 96.41 | [36311269603](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36311269603) |
| T3 | A2 | graded | 92.71 / 92.71 | [36312822662](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36312822662) |
| T4 | A1 | NG; no deliverable | — | [36314682247](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36314682247) |
| T4 | B1 | graded | 67.00 / 53.84 | [36316075585](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36316075585) |
| T4 | C1 | graded | 64.56 / 51.88 | [36317678630](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36317678630) |
| T4 | C2 | graded | 64.33 / 51.70 | [36319348118](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36319348118) |
| T4 | B2 | graded | 67.00 / 53.84 | [36319579609](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36319579609) |
| T4 | A2 | NG; no deliverable | — | [36326578241](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36326578241) |
| T5 | A1 | NG; no deliverable | — | [36328361091](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36328361091) |
| T5 | B1 | NG; no deliverable | — | [36330288675](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36330288675) |
| T5 | C1 | graded | 8.23 / 8.23 | [36332199214](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36332199214) |
| T5 | C2 | NG; no deliverable | — | [36334062307](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36334062307) |
| T5 | B2 | graded | 28.44 / 28.44 | [36335885361](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36335885361) |
| T5 | A2 | NG; no deliverable | — | [36337865696](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36337865696) |

T5 C1 earned 10.375/126 points; B2 earned 35.84/126. Both are graded without exclusions. The reported `critical_items=20` does **not** mean 20 failed items.
Final T5 A2 readout `36337865696` (job `108672077172`, attempt 1) succeeded at `2026-09-27T17:45:27Z` on observer `74ae7277a636643d37c4a7e854728df1aec83676`; its verified projection is model-free UNGRADED, not an ordinary numeric grade.
Its original inference `36277325255` ended with exit 1 / `child_nonzero_exit`, timeout false, cleanup true and no deliverables. Expected results 1, scored results 0 and score `NULL` mean no numeric grade, not zero points; the internal cause is unknown.

## Frozen epoch03 Task1, kept separate

All six T1 inference cells below are FROZEN, with no grades or deliverables and confirmed cleanup. Original prefix 0..5 was not replayed and is **not marked completed in epoch04**. These are inference runs, not readout runs.

| Cell | Inference run | Frozen reason |
| --- | --- | --- |
| A1 | [36024206206](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36024206206) | `task_attempt_budget_exhausted` |
| B1 | [36028188572](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36028188572) | `timeout` |
| C1 | [36042694350](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36042694350) | `task_deadline_exhausted` |
| C2 | [36066170616](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36066170616) | `task_deadline_exhausted` |
| B2 | [36083636761](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36083636761) | `task_deadline_exhausted` |
| A2 | [36098267935](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36098267935) | `task_attempt_budget_exhausted` |

T1 B1's timeout does not prove exhaustion of the whole 180-minute cell budget.
Three earlier admissions, comprising two historical T1 failures and the epoch03 T2 retention refusal, are separate operational corrections, not extra independent repeats.

## Source history and claim limits

Corrective epoch04 starts at ordinal 6, T2 A1. The [epoch03](../../batch-runner/experiments/execution_envelope/codex_external_budget_ci_pilot_epoch03.yaml) and [epoch04](../../batch-runner/experiments/execution_envelope/codex_external_budget_ci_pilot_epoch04.yaml) registrations preserve distinct histories.

| Scope | Immutable source / role |
| --- | --- |
| Epoch03 T1 inference | `fb232a074f395766f9f83ddc7195a9997a3428f5` |
| Epoch04 T2 A1 inference | `b4c95f8eaee16ae2226f3bf6e0493051fa91d770` |
| Remaining T2 inference | `e7a28db07ebe10d6508b9256137763cc82f9a1d1` |
| T3–T5 inference producer | `78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e` |
| T3–T5 grading writer | `69e56fc58daf50af2ac9e8b52691ffcbf5af4f96` |

Observer SHAs are separate from producer/writer SHAs. Source changes and corrective admissions prevent treating the report as one unchanged protocol or cohort; no pooled causal claim is made.
These are recorded rubric outcomes; the supplied rows do not establish independent judge calibration. The retention-only contrast remains unanswered.

## Budget-snapshot availability

The reader projects only the selected inference result's existing `observability.task_deadline` fields: `total_seconds`, `started_unix`, `expires_unix`, `remaining_seconds`, `wait_seconds`, `attempts_admitted` and `native_resumes`. This adds measurement access without changing the model, intervention or budget.
`total_seconds` is the budget, and the Unix timestamps mark its recorded start and expiry. `remaining_seconds` is zero-clamped, not exact uncapped elapsed time. `wait_seconds` records retry backoff, not all recovery or downtime; GitHub job wall time is not cell inference-budget elapsed.
`attempts_admitted` counts durable admissions, not successful, model or HTTP attempts. `native_resumes` counts confirmed native-thread resume bindings, not resume requests, turns or Step2 `resume_rounds_used`.
The shared `inference_budget_snapshot` projection uses `null` plus a `missing` reason of `not_recorded` for omitted fields, or `unavailable` for explicitly null native clocks; actual zeros stay zero. Malformed present values are refused. Historical schema support does not prove that each payload contains a snapshot. All six Task4 budget snapshots are now leader-verified, completing Task4 budget evidence only: 6 of 24 epoch04 cells. The other 18 cells' budget snapshots remain unobserved here, not zero or `not_recorded`.

For existing Task4 B1, `3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r1`, the leader verified read-only run [36356813899](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36356813899), attempt 1, job `108726076308`: the read step completed at `2026-09-27T22:57:11Z` and the job succeeded at `2026-09-27T22:57:13Z`, on observer `8e188db9cb4e937f33ba8723d88ffd2b52b359cc`.
The historical writer is `69e56fc58daf50af2ac9e8b52691ffcbf5af4f96` (grade run `36292532223`) and producer is `78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e`. Verified bindings are request `f3546942ebac25c3c3cd1788dfb792a80e3e10f465999bebf7730fb651cb2bde`, grade revision `6443b834b06b6cee08f649640dbe07b5597e5303`, claim revision `b176b367a3a04b238fcc2401caed3f835afc50a8` and inference terminal `e8c7bf89d2c2119ad0a3bb41fdf06c7122aa137d`.
The exact snapshot is `total_seconds=10800`, `started_unix=1790418755.651576`, `expires_unix=1790429555.651576`, `remaining_seconds=7982.99290561676`, `wait_seconds=2340.6372985839844`, `attempts_admitted=12`, `native_resumes=11`, `missing={}`.
This records 12 durable admissions and 11 confirmed native resumes, with 2340.6372985839844 seconds of retry backoff (about 39.01 minutes), not all recovery or downtime. B1 continued beyond four admissions; this does not mean 12 HTTP/model calls or 12 successes, and does not prove that resuming improved quality. `total_seconds - remaining_seconds` is not exact uncapped elapsed time.
The leader compared the projection with original readout `36316075585`: every old field matches except `observer_source_sha`, and the only added key is `inference_budget_snapshot`. The original score remains 67.00% included / 53.84% full; prices, exclusions, source history and proof limits are unchanged. This observes unchanged historical bytes, not new inference, grading, regrading, a repetition or a 31st original cell.

For existing Task4 A1, `3baa0009-5a60-4ae8-ae99-4955cb328ff3_A_r1`, the leader verified model-free readout [36358392037](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36358392037), attempt 1, job `108730558766`: the read completed at `2026-09-27T23:23:58Z` and the job succeeded at `2026-09-27T23:24:01Z`, on observer `8e188db9cb4e937f33ba8723d88ffd2b52b359cc`.
Historical writer `69e56fc58daf50af2ac9e8b52691ffcbf5af4f96` and producer `78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e` are unchanged. Verified bindings are request `a913f0236e801e31ab7c0f58c8545ad6375d7092c06fa77f839225d03efe52d8`, record revision `ac03574d424d3315d15d340184af4f8e8b8b6b1d`, claim revision `3954eec39746549ed1f61e25c0bb062569137016` and inference terminal `3eeca585491d6567f860d5d6363ad285cb14ceff`.
The exact A1 snapshot is `total_seconds=10800`, `started_unix=1790416844.1516893`, `expires_unix=1790427644.1516893`, `remaining_seconds=10196.292588472366`, `wait_seconds=420.1196165084839`, `attempts_admitted=4`, `native_resumes=0`, `missing={}`.
This records four durable admissions, zero confirmed native resumes and 420.1196165084839 seconds of retry backoff (about 7.00 minutes), not all recovery or downtime. The remaining snapshot is about 169.94 minutes, not an observation of full 180-minute exhaustion. It does not establish the internal failure cause, that the four-attempt cap specifically caused failure, or exact uncapped elapsed time.
The leader compared A1 with original readout `36314682247`: every original projection field matches except `observer_source_sha`, and the only added key is `inference_budget_snapshot`. No deliverable, UNGRADED, score `NULL` and partial accounting remain unchanged; `NULL` is not zero. These are new observations of old results, not new inference, grading, regrading, repetitions or extra original cells.
Compared with B1's 12 durable admissions, 11 confirmed native resumes and about 39.01 minutes of retry backoff, A/B still changes retry policy and retention together. One task/repeat is not a causal retention or model-quality result.

For existing Task4 C1, `3baa0009-5a60-4ae8-ae99-4955cb328ff3_C_r1`, the leader verified budget readout [36360105814](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36360105814), attempt 1, job `108735460955`: the read completed at `2026-09-27T23:54:36Z` and the job succeeded at `2026-09-27T23:54:38Z`, on observer `8e188db9cb4e937f33ba8723d88ffd2b52b359cc`.
Historical writer `69e56fc58daf50af2ac9e8b52691ffcbf5af4f96` and producer `78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e` are unchanged. Verified bindings are request `76c1904cfbed0588f5fcb6c15f48f66cd065933a8c829cbd18fcfb323f8ab710`, grade revision `f506f13d106676498fada64125586d500733783b`, claim revision `3e461db0490b0b15d96ab716c26dc8cd6a9ba1c3` and inference terminal `3c24d2354df2da79678e8ef8a9215c40d3e07b72`.
The exact C1 snapshot is `total_seconds=10800`, `started_unix=1790422399.534317`, `expires_unix=1790433199.534317`, `remaining_seconds=9081.397119045258`, `wait_seconds=1380.4454476833344`, `attempts_admitted=8`, `native_resumes=7`, `missing={}`.
This records eight durable admissions, seven confirmed native resumes and 1380.4454476833344 seconds of retry backoff (about 23.01 minutes), not all recovery or downtime. The counts are not HTTP/model calls or successful attempts, and the snapshot does not give exact uncapped elapsed time.
The leader's field-by-field comparison with original readout `36317678630` found every original projection field identical except `observer_source_sha`; only `inference_budget_snapshot` was added. The original score remains 64.56% included / 51.88% full, with 29.05/45 included points and 9 excluded items / 11 maximum points. All accounting and proof fields are unchanged.
In this one Task4 first-repeat comparison, B1 has 12 durable admissions, 11 confirmed native resumes, about 39.01 minutes of recorded retry backoff and a 53.84% full-denominator score; C1 has 8 admissions, 7 resumes, about 23.01 minutes of recorded retry backoff and a 51.88% full-denominator score. These are descriptive observations, not evidence that C's feedback causally reduced waiting or established superiority or inferiority.
Time-varying service errors, only two repeats, joint A/B retry-policy and retention changes, unread exclusion IDs/causes, judge calibration and incomplete costs still limit attribution. A1 remains a failure with a `NULL` grade, not zero; the retention-only contrast remains unanswered.
These observations of historical results add no inference, grading, regrading, repetitions or original cells.

For existing Task4 C2, `3baa0009-5a60-4ae8-ae99-4955cb328ff3_C_r2`, the leader verified budget readout [36362019549](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36362019549), attempt 1, job `108740926194`: the read completed at `2026-09-28T00:25:40Z` and the job succeeded at `2026-09-28T00:25:42Z`, on observer `8e188db9cb4e937f33ba8723d88ffd2b52b359cc`.
Historical writer `69e56fc58daf50af2ac9e8b52691ffcbf5af4f96` and producer `78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e` remain fixed. Verified bindings are request `817d2515c4719b7f12b40c5c58e446661e2e41fd5d8023a78045208548e4dcbd`, grade revision `5373485149d7b44a0fe5702957a3bb2dd535aaa7`, claim revision `f521b7b64aef2a0196512ccdc87b301c9eb9d2a5` and inference terminal `cb471fe3b555cc19ef86de3533f5e98c69e4206b`.
The exact C2 snapshot is `total_seconds=10800`, `started_unix=1790426237.5542438`, `expires_unix=1790437037.5542438`, `remaining_seconds=9571.179827451706`, `wait_seconds=900.3586511611938`, `attempts_admitted=6`, `native_resumes=5`, `missing={}`.
This records six durable admissions, five confirmed native resumes and 900.3586511611938 seconds of retry backoff (about 15.01 minutes), not all recovery or downtime. The counts are not HTTP/model requests or successful attempts, and the snapshot does not give exact uncapped elapsed time.
The leader's field-by-field comparison with original readout `36319348118` found every original projection field identical except `observer_source_sha`; the only new key is `inference_budget_snapshot`. The original score remains 64.33% included / 51.70% full, with 28.95/45 included points and 9 excluded items / 11 maximum points. Accounting and proof fields are unchanged.
C1 and C2 now both have observed budgets, but two repetitions of one task do not identify a feedback effect, model superiority, a service-error cause or a retention-only benefit.
Missing prices, unread exclusion IDs/causes, judge calibration, source/epoch changes and the joint A/B retry-policy and retention changes still limit attribution. Nothing is repriced or regraded; this observation adds no inference, grading, regrading, repetition or original cell.

For existing Task4 B2, `3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2`, the leader verified budget readout [36363889837](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36363889837), attempt 1, job `108746339870`: the read completed at `2026-09-28T00:56:26Z` and the job succeeded at `2026-09-28T00:56:28Z`, on observer `8e188db9cb4e937f33ba8723d88ffd2b52b359cc`.
Historical writer `69e56fc58daf50af2ac9e8b52691ffcbf5af4f96` and producer `78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e` are unchanged. Verified bindings are request `ec4221834b04014e58775a4a4d94fc139e49ad2b7b45321e7fd2ccd58d75ef41`, grade revision `a73abd00ab159437bfbef65a58bdc2ec5de9083d`, claim revision `2c6051f60662ab9f3a2c50b084d316bdc4b332bc` and inference terminal `7c08b218bfb9c75f0092dccb881239a9d9f3e945`.
The exact B2 snapshot is `total_seconds=10800`, `started_unix=1790427905.665129`, `expires_unix=1790438705.665129`, `remaining_seconds=9598.128176927567`, `wait_seconds=900.3099925518036`, `attempts_admitted=6`, `native_resumes=5`, `missing={}`.
This records six durable admissions, five confirmed native resumes and 900.3099925518036 seconds of retry backoff (about 15.01 minutes), not all recovery or downtime. Admissions are not HTTP/model calls or successful attempts, and the snapshot does not give exact uncapped elapsed time.
The leader compared B2 with original readout `36319579609`: every original field matches except `observer_source_sha`, and only `inference_budget_snapshot` was added. The original score remains 67.00% included / 53.84% full, with 30.15/45 included points and 9 excluded items / 11 maximum points. Accounting and proof fields are unchanged.
B2 and C2 each record 6 durable admissions, 5 confirmed native resumes and about 15.01 minutes of retry backoff. B2's full-denominator score is 53.84%, versus C2's 51.70%; the first-repeat B1/C1 backoff difference is not repeated in this second pair.
These are descriptive observations only, not statistically established feedback effects, superiority, service-error causes or retention-only proof. Existing `NULL` failure grades are not zero.
Missing prices, unread exclusion IDs/causes, source/epoch changes, judge calibration and joint A/B retry-policy and retention changes still limit attribution; no complete costs are inferred. This observation adds no inference, grading, regrading, repetition or original cell.

For existing Task4 A2, `3baa0009-5a60-4ae8-ae99-4955cb328ff3_A_r2`, the leader verified model-free budget readout [36365781987](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36365781987), attempt 1, job `108751786517`: the read completed at `2026-09-28T01:25:40Z` and the job succeeded at `2026-09-28T01:25:43Z`, on observer `8e188db9cb4e937f33ba8723d88ffd2b52b359cc`.
Historical writer `69e56fc58daf50af2ac9e8b52691ffcbf5af4f96` and producer `78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e` are unchanged. Verified bindings are request `8f2f6edd7bb2fda964d8a24b4532b8af725bcefbb1513d9a60df86e983446fe9`, NG record revision `ce5eaf4040781514a896662c0af7d26dcf534892`, claim revision `38b66fed8ac217c8f20232c219f8fe21c787ccf2` and inference terminal `337ae5c072ca1c1053776b5b1f3588c7db6d3aad`.
The exact A2 snapshot is `total_seconds=10800`, `started_unix=1790429725.4813406`, `expires_unix=1790440525.4813406`, `remaining_seconds=10222.363258361816`, `wait_seconds=420.10989904403687`, `attempts_admitted=4`, `native_resumes=0`, `missing={}`.
The leader compared A2 with original readout `36326578241`: every original field matches except `observer_source_sha`, and only `inference_budget_snapshot` was added. UNGRADED, no deliverable, score `NULL` and partial accounting are unchanged; `NULL` is not zero.
This records four durable admissions, zero confirmed native resumes and 420.10989904403687 seconds of retry backoff. Admissions are not HTTP/model calls or successful attempts; retry backoff is not all recovery or downtime, and the snapshot does not give exact uncapped elapsed time.
The substantial remaining snapshot budget does not show full budget exhaustion or establish the internal failure cause or that the four-attempt cap caused failure.

### Task4 summary (six retained snapshots)

All six snapshots have `total_seconds=10800` and `missing={}`. These are six re-observations of unchanged historical cells, not additional experiment runs, inference, grading, regrading, repetitions or original cells.

| Task4 cell | Durable admissions | Confirmed native resumes | Retry-backoff seconds | Full-denominator score / UNGRADED |
| --- | --- | --- | --- | --- |
| A1 | 4 | 0 | 420.1196165084839 | UNGRADED / `null` |
| B1 | 12 | 11 | 2340.6372985839844 | 53.84% |
| C1 | 8 | 7 | 1380.4454476833344 | 51.88% |
| C2 | 6 | 5 | 900.3586511611938 | 51.70% |
| B2 | 6 | 5 | 900.3099925518036 | 53.84% |
| A2 | 4 | 0 | 420.10989904403687 | UNGRADED / `null` |

The leader reports six unique cell IDs in this order in `project5-task4-budget-evidence-complete-1021.json`, SHA-256 `724f9df1c9d23698e25775118a545b363f3b6a1f6d3d9d93d7b84690742210bf`. This reference identifies a leader-local artifact, not a file supplied in this worktree.
In this one Task4 sample, both A records ended after 4 durable admissions and no confirmed native resume, with no deliverable and substantial remaining snapshot budget. The B/C records made 6–12 admissions and 5–11 resumes with deliverables. This is an observed association. It does not show that the four-attempt cap caused failure, isolate a retention-only effect, establish whole-pilot success or demonstrate model/feedback superiority.
The second B/C pair records the same 6 admissions / 5 resumes / about 15 minutes of retry backoff; two repeats and changing service errors do not establish causality. Neither exact uncapped elapsed time nor total recovery/downtime was measured by these snapshots. Missing prices, unknown exclusion causes/item overlap, unvalidated independent judge calibration and source/epoch histories remain limits; A/B still changes retry policy and retention together.
Task4 budget evidence is complete, not the whole card. The retention-only contrast and complete costs remain unresolved. No new 30/220-task expansion, inference, grading or regrading is authorized.

## Accounting and remaining decision

All graded readouts report `price_missing` as a missing reason, with monetary totals `NULL`; they are not invoices. HTTP request counts are unknown. Model-call counts must not be converted into HTTP counts.
The following amounts are known **partial NG inference USD**, not complete cell or pilot bills. Their model-call counts are kept in a separate column.

| Cell | Known partial inference USD | Model calls |
| --- | --- | --- |
| T4 A1 | 0.060359 | 4 |
| T4 A2 | 0.084485 | 4 |
| T5 A1 | 0.203863 | 3 |
| T5 B1 | 0.347961 | 33 |
| T5 C2 | 0.240000 | 6 |
| T5 A2 | 0.406518 | 4 |

For T5 A2, all three original inference cost views agree on USD 0.406518 known partial cost. The receipt records 4 model calls and 300390 input, 11097 output, 227072 cached and 5380 reasoning tokens; its status is `partial` and `call_reachability_unknown` is a missing reason. Estimated cost is `NULL`, invoice is false and HTTP count is `null`.
Recorder accounting remains `NOT_MEASURED`, not zero, and separate from inference receipts. No whole-pilot bill or cost-efficiency ranking is available from these facts.
All 30 original IDs now have documented outcomes across the two epochs, with no pending epoch04 projection. This is outcome accounting, not evidence of one unchanged cohort or condition/model superiority. Exclusion causes/ID overlap, missing prices, source changes and the unresolved retention-only contrast remain limits.
The outcome rows and all six Task4 budget snapshots remain leader-verified; no Task4 budget observation is pending. This combined report update awaits leader review. It does not authorize more inference, grading, regrading, expansion or live readout calls. Merge and Project decisions remain with the leader.
