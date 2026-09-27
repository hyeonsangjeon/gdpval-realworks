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
The shared `inference_budget_snapshot` projection uses `null` plus a `missing` reason of `not_recorded` for omitted fields, or `unavailable` for explicitly null native clocks; actual zeros stay zero. Malformed present values are refused. Historical schema support does not prove that each payload contains a snapshot. No live snapshot values were observed for this addition.

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
The outcome rows remain leader-verified. This snapshot-access addition awaits new-head review and CI, with separate approval required for any live observation. It does not authorize more inference, grading, regrading, expansion or live readout calls. Merge and Project decisions remain with the leader.
