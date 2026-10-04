# Retention-budget evidence: original pilot and eight-cell diagnostic

The finite diagnostic has eight recorded producer outcomes: two succeeded and
six failed. Task4 KEEP succeeded in 2/2 cells and FRESH in 0/2; Task5 KEEP and
FRESH each succeeded in 0/2. These are descriptive results from two post-selected
tasks, not a causal retention or model-performance finding. The six failures
have null grades, not zero scores.

All eight diagnostic cells now have leader-verified RESULT-only budget
observations, including both successful Task4 KEEP cells. First-cell KEEP/r1
records 7912.227738618851 remaining seconds, 1860.7502946853638 retry-backoff
seconds, 10 native admissions and 9 confirmed resumes. KEEP/r2 records
9564.73209309578 remaining seconds, 900.3846650123596 retry-backoff seconds,
6 native admissions and 5 confirmed resumes. These stored fields do not
establish a causal benefit or exact uncapped elapsed time. All eight budget
observations are verified and consumed, not eight successful tasks.

The finite execution and available-accounting scope is closed to this evidence.
Coverage of the retained budget fields is complete for these eight cells;
realized recovery exposure, complete costs and attribution remain unresolved.
The leader owns the report review and card decision; this draft does not close
the whole card or all Project5 work, and authorizes no execution, read, grade
or repetition. The [machine-readable table](retention_diagnostic_readout.json)
keeps full identities, historical missingness and later observations separate.
The completed field coverage is evidence for the leader's acceptance decision,
not an instruction to mark the whole card complete or run another experiment.

## Original pilot and separate diagnostic

The [original A/B/C pilot report](REPORT.md) remains unchanged and closed at
24 epoch04 outcomes (18 graded and 6 model-free UNGRADED) plus 6 frozen epoch03
Task1 failures. These account for 30 original cell IDs, not 30 identical-source
successes. Its 24 retained epoch04 budget snapshots are observed; they are not
30 budget observations. The frozen epoch03 failures, source changes and
corrective admissions remain separate from epoch04.

The pilot compared A's at-most-four fresh attempts, B's mechanical native
continuation and C's host-validated adaptive feedback on top of B's budget and
retention. A/B changes retry policy and retention together. B/C is the feedback
contrast. The later eight-cell diagnostic holds mechanical B recovery fixed
and changes the within-cell state bundle through KEEP/FRESH, with no C feedback
and no fixed admission cap. It uses two post-selected tasks, not a new run of
the five-task pilot or a larger sample.

The accepted pilot findings are high Task2/Task3 grades, moderate Task4 grades
with large exclusions, and poor or missing Task5 grades. They did not establish
a C-over-B benefit. In original-pilot Task4, B1/B2 each scored 53.84% on the full
denominator, versus C1's 51.88% and C2's 51.70%. This is a negative C-versus-B
descriptive result in both repetitions, not proof that feedback caused harm.
All four grades exclude 9 items worth a maximum of 11 points; included/full
denominators are 45/56, and exclusion causes/item overlap remain unread.
B2/C2 each recorded 6 admissions and 5 resumes with about 15 minutes of backoff;
the first pair's backoff difference did not recur in the second pair. Those
pilot values are not the later diagnostic's grades or budget observations.
The original report retains the complete outcome, budget and accounting tables;
no pilot result is replayed, regraded or recomputed here.

## What was compared

The [registered diagnostic](../../batch-runner/experiments/execution_envelope/codex_retention_diagnostic.yaml)
compares a bundle of within-cell state under mechanical B recovery, with no C
feedback. KEEP preserves that cell's native thread, workspace, HOME, CODEX_HOME
and owned outputs across eligible recovery. FRESH retires only that cell's
eligible native continuation and owned files through the guarded fresh path,
preserving settled accounting and the cumulative clock. Neither treatment
imports its predecessor's state. This is not a thread-only versus files-only
comparison, and KEEP/FRESH do not have different budgets.

The fixed configuration is GPT-5.4 / direct-v1 / xhigh, SDK/CLI 0.147.0 and one
concurrent inference. Each cell has 10800 cumulative seconds from first
admission, including waits, recovery and downtime without reset. The
1800-second native-turn wait is not an all-in attempt ceiling. There is no fixed
admission count or automatic monetary cap. These are registered conditions;
they do not establish the realized recovery opportunities or time allocation.

Task4 is `3baa0009-5a60-4ae8-ae99-4955cb328ff3`; Task5 is
`0818571f-5ff7-4d39-9d2c-ced5ae44299e`. Each has two repetitions per treatment.
The exact order is Task4 keep1/fresh1/fresh2/keep2, then Task5
fresh1/keep1/keep2/fresh2. Each JSON row carries its full
`<task_id>_retention_bundle_v1_<keep|fresh>_r<1|2>` cell ID. The original input
and rubric revision is `11e7900cdcac61bc4daf59e65feb238acda98fbf`; the supplied
bundle SHA256 is `757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Supplied hashes are provenance, not independent input authentication by a reader.

Success below means the explicit producer outcome, followed by successful
payload intake where recorded. It does not mean a high rubric score or a green
workflow alone. The two later grades used the fixed `default_v2_sol_max.yaml`
judge, GPT-5.6 Sol / max, once per produced result without low-score regrading.
The available evidence does not independently calibrate that judge.

## Eight outcomes in registered order

USD amounts are known partial inference amounts, not invoices or grading costs.
Grade pairs are included percentage / full-denominator percentage. Every
producer ran at attempt 1. Source and inference-terminal prefixes below resolve
to full SHAs, request/job bindings, control hashes and read provenance in the JSON.

| Ordinal | Cell | Producer outcome | Recorded model calls | Known partial inference USD | Grade % included / full | Producer run | Source / inference terminal |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| 0 | Task4 keep/r1 | succeeded | 10 | 0.409894 | 68.0 / 54.64 | [36696961231](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36696961231) | `e355faf9` / `de50ff0a` |
| 1 | Task4 fresh/r1 | failed | 39 | 0.303358 | null | [36845127347](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36845127347) | `e39d8d1a` / `45f54eb0` |
| 2 | Task4 fresh/r2 | failed | 39 | 0.29944 | null | [36907894862](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36907894862) | `5a9614ac` / `1d513359` |
| 3 | Task4 keep/r2 | succeeded | 6 | 0.22195 | 67.44 / 54.20 | [36947454688](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36947454688) | `b8351e56` / `e55fac5d` |
| 4 | Task5 fresh/r1 | failed | 18 | 2.576093 | null | [37032230813](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37032230813) | `e5e338aa` / `94628d12` |
| 5 | Task5 keep/r1 | failed | 13 | 0.413364 | null | [37066171719](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37066171719) | `a8353cd4` / `33278d9c` |
| 6 | Task5 keep/r2 | failed | 38 | 0.847605 | null | [37081963299](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37081963299) | `bdb7c211` / `3be1c0b8` |
| 7 | Task5 fresh/r2 | failed | 1 | 0.13489 | null | [37101934436](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37101934436) | `dfa812a2` / `4fdd9c2e` |

The denominator is eight cells, not eight successes. The Task4 pattern is a
keep-only success pattern in both repetitions, but unavailable realized recovery
exposure prevents treating it as evidence that retained state caused the
difference. The registered preliminary rule concerns keep-only deliverable
advantage in both pairs within a task with no reverse pair; it is not a causal
test. A cell without a recovery opportunity remains in the denominator and is
uninformative about retention. Task5 supplies no successful cell in either treatment.

Only the two Task4 KEEP cells have historical successful full-payload intake
and numeric grades. The later KEEP/r2 budget receipt declares 3 deliverables
but does not read their bodies or establish a new delivery. The first-cell
historical safe intake summary does not disclose a deliverable count; its later
budget observation declares 4 without reading those bodies. The six failed
cells declare no deliverables in their controls; neither that declaration nor
a later RESULT-only read proves absence of all partial work.

## Eight recorded budget points

These are stored inference-result snapshots, observed later through model-free
readers. All eight supplied snapshots record `total_seconds=10800` and
`missing={}`. Start/expiry timestamps and exact receipt bindings are retained
in each JSON row's separate `current_budget_observation`. Historical missing
fields remain in the original rows; they are not replaced with the later values.

| Registered cell | Budget evidence | Remaining seconds | Retry-backoff wait seconds | Native admissions | Confirmed native resumes |
| --- | --- | ---: | ---: | ---: | ---: |
| Task4 keep/r1 | RESULT-only | 7912.227738618851 | 1860.7502946853638 | 10 | 9 |
| Task4 fresh/r1 | RESULT-only | 0.0 | 8983.719460487366 | 39 | 0 |
| Task4 fresh/r2 | RESULT-only | 0.0 | 8985.385900974274 | 39 | 0 |
| Task4 keep/r2 | RESULT-only | 9564.73209309578 | 900.3846650123596 | 6 | 5 |
| Task5 fresh/r1 | RESULT-only | 4909.906562328339 | 3781.06050658226 | 18 | 0 |
| Task5 keep/r1 | RESULT-only | 7373.157982349396 | 2580.858815908432 | 13 | 12 |
| Task5 keep/r2 | RESULT-only | 0.0 | 8742.75936126709 | 38 | 37 |
| Task5 fresh/r2 | RESULT-only | 10724.012340545654 | 0.0 | 1 | 0 |

Remaining time is zero-clamped, not exact uncapped elapsed time. Wait measures
retry backoff, not all recovery or downtime. Admissions count durable native
admissions, and resumes count confirmed native bindings; neither is a model
or HTTP-call count. The recorded zeroes are actual fields, not imputations.
Positive remaining time, zero remaining time and zero backoff do not identify
a failure cause or rule out provider errors or unrecorded recovery.

Task4 KEEP/r2 succeeded while both Task4 FRESH cells failed. Among Task5's four
failures, both KEEP points record confirmed resumes, both FRESH points record
none, and remaining time varies. These are recorded count differences,
not an estimate of retention benefit. Detailed eligible recovery opportunities
and realized state-retention exposure remain unavailable. All eight reads are
consumed; none was queried or replayed for this draft.

## Inference and grading accounting stay separate

The accepted Decimal sum of recorded inference amounts is USD 5.206594 across
164 recorded model calls. Task4 contributes USD 1.234642 / 94 calls and Task5
USD 3.971952 / 70 calls. These are sums of known partial inference only. They
exclude unknown charges and grading costs and are not a complete diagnostic bill.

All inference rows retain `call_reachability_unknown`; Task4 fresh/r1,
fresh/r2 and keep/r2 also retain `usage_absent`. Estimated/runtime costs and
HTTP request counts remain null. Model-call counts are neither HTTP requests
nor native admissions/resumes. Cached input is part of input, and reasoning
is part of output, so these token counters must not be added again. Task4
keep/r2's generation component has null cost and recorded zero token counters;
that does not establish free work or zero actual usage.

Per-cell recorded input, cached-input, output and reasoning counters remain in
the JSON's `inference.usage` fields. Task4 keep/r1's usage remains unavailable
with `not_in_current_retained_summary`; no diagnostic-wide token total is
imputed. The original pilot's separate partial NG inference amounts and null
graded monetary totals stay in its [accounting section](REPORT.md#accounting-and-remaining-decision),
without being combined with this diagnostic's inference or grade accounting.

Task4 keep/r1 earned 30.6/45 = 68.0% included and 54.64% on the full denominator.
Keep/r2 earned 30.35/45 = 67.44% included and 54.20% full. Each excludes 9 items
worth a maximum of 11 points from the full maximum of 56. Equal exclusion
counts do not establish identical excluded items, and exclusion causes/item
overlap remain unread. The denominator change is not treatment uplift.

The keep/r1 grade records 93 model calls; keep/r2 records 91. Both retain
`price_missing`, null known/model/estimated/runtime USD, null HTTP request
count and `invoice_complete=false`. Their fixed grade terminals are
`40712e0980cc05c31688fdbb98c693774fb90c0d` and
`76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e`; neither is an inference predecessor.
The JSON keeps their distinct writer/readout sources, runs, fingerprints and
historical reader evidence. There is no global grade average or cost-efficiency
ranking. Missing materialized-input fingerprint comparisons remain unavailable.

## Original card criteria and evidence disposition

The following mapping uses already accepted source and proof records. It is
not a new code audit or a change to Project checkboxes. "Supported" means the
named implementation boundary has source/offline evidence, not that every
live path or causal claim is established. "Partial" retains an explicit gap;
"unavailable" means the necessary observation or attribution is absent here.

| Implementation criterion | Disposition | Accepted evidence and boundary |
| --- | --- | --- |
| Cumulative external limits without reset | Supported in source/offline proof; realized allocation partial | The [deadline store][deadline-source] persists the original start/expiry and charges waits to it; the [final producer proof][producer-proof] covered the cumulative clock and settled accounting through guarded FRESH recovery. The diagnostic retains 10800 cumulative seconds and a 1800-second native-turn wait, not an all-in attempt ceiling. Stored remaining time does not measure uncapped elapsed time or all downtime. |
| Authority separation | Supported for the fixed workflow/read boundaries | The [accepted first-cell reader record][first-budget-proof] documents the separation of source/request approval and paid execution from fixed read routes, with precredential hashes and private safe receipts preserved. It records all576 mode cases with zero recorded paid effects. Publication-derived controls do not independently authenticate the provider, original input or actual CAS. |
| Error/retry classification and retry hints | Partial; typed retry hints unavailable | The accepted [core classifier][core-classification-source] and [runner][runner-classification-source] distinguish `rate_limited`, `transport_error`, `timeout`, `content_filtered` and other failures, retaining unknown fallbacks `execution_error`/`turn_failed`. The unchanged [recovery allowlist][recovery-source] admits only `rate_limited` and `turn_start_failed`; it is not the full failure taxonomy. The [offline analyzer][offline-classification-source] optionally adds `output_limit_exceeded` only with a complete explicit local reason and an unknown recorded fallback; known categories and recorded fields remain unchanged. This is not runtime output-limit emission or new recovery eligibility. SDK 0.147.0 supplies no typed Retry-After/retry guidance in this contract; free-form messages are not instructions. The separate [exp035 compact observation][compact-classification-evidence] of 3 diagnoses in220 rows does not diagnose the 30-cell pilot or eight-cell retention study. Detailed causes and recovery exposure of the six retention failures remain unavailable. |
| State preservation and no replay | Supported in source/offline proof; realized exposure partial | The [owned retirement contract][retirement-source] preserves host accounting and the clock while retiring only an eligible FRESH cell's owned state. KEEP retains its own state, never its predecessor's. The [producer proof][producer-proof] exercised current-parent CAS, child completion, terminal acknowledgment, lost-ack reconciliation, no replay and timeout/cleanup. The budget receipts do not reveal every realized recovery opportunity. |
| Offline fault injection | Supported for the tested synthetic boundaries | The accepted [producer][producer-proof], [successful KEEP/r2 budget][success-budget-proof] and [legacy first-cell budget][first-budget-proof] selectors covered identity/metadata refusals, interrupted or lost acknowledgments, no-clobber/readback and mode isolation at their recorded scopes. Synthetic tests do not reproduce live provider failures or prove an outcome cause. None was rerun here. |

The final producer selector passed at
`7031b4784d76b1ebfcf270f7df96b5c1ea153e2a` in 48.22s, including 288 then-current
routing cases. The successful KEEP/r2 budget selector passed at
`a4950d6b968714bb79e237f8dc944290c01ec5bf` in11.47s, and the legacy first-cell
selector at `a66015685ef5e9d3850d7e3e45ff618862be68f7` in14.34s; both covered
all576 mode cases at their own source revisions. These are consumed historical
proofs, not checks of this draft. PR736 HEAD
`fc0c9795864ab73b2a998e8baf7ecffcfd3e522b`, owner review
[5402409555](https://github.com/hyeonsangjeon/gdpval-realworks/pull/736#pullrequestreview-5402409555)
and all10 checks are the supplied acceptance evidence for this draft's base
`8494f7c9602c90a9cc354db8b683e9ab01b14426`.

| Measurement or tradeoff criterion | Disposition | What the available evidence answers, and what it cannot answer |
| --- | --- | --- |
| Finite outcomes, deliverables and grades | Supported for recorded outcomes; quality inference partial | All 30 pilot IDs have outcomes across the two epochs. The separate diagnostic has eight outcomes, two historical successful intakes and two numeric grades; six failure grades remain null. Whole-denominator grades and exclusions are retained, with no global average or claim that a success is high quality. |
| Realized budget points | Supported for retained-field coverage; allocation partial | The pilot has 24 observed epoch04 snapshots, not 30; the separate diagnostic has eight of eight. The snapshots record budget/start/expiry/remaining fields, not an uncapped elapsed-time trace. |
| Wait, admission and resume measurements | Partial | Eight diagnostic points expose retry backoff and native counts. They do not measure all recovery/downtime, HTTP calls, every eligible recovery opportunity or every retained-state transition. |
| Usage and cost | Partial; complete bill unavailable | The diagnostic retains164 inference calls and known partialUSD5.206594, per-cell usage/missing reasons and separate93/91 grade-call counts. Missing prices, usage and reachability remain unknown. Neither the pilot nor this diagnostic supplies a full invoice or a cost-efficiency ranking. |
| Retention/feedback tradeoff and attribution | Unavailable as a causal estimate | Original-pilot A/B mixes retry policy and retention; its C-versus-B findings do not establish feedback benefit. The separate KEEP/FRESH observations have post-selection, two repeats, fixed order, service/source variation and uncalibrated judging. Complete snapshot coverage does not isolate a causal effect or justify expansion. |

All 30 original pilot outcomes, all eight separate diagnostic outcomes and all
eight diagnostic budget reads are finished and consumed, including failures.
An inconclusive result is not an unexecuted cell. The finite execution/accounting
closeout remains narrower than the card's measurement and attribution criteria.
Missing detailed failure/recovery exposure, complete costs, independent
authentication and causal attribution are historical evidence limitations,
not unfinished cells. Rewriting records cannot supply those measurements.
The epoch split, post-selection, two repeats, service/source variation and
uncalibrated judging remain unchanged.

The dispositions above remain in force; this mapping establishes no additional
undelivered implementation. Typed retry hints remain unavailable in the pinned
SDK, and offline diagnosis does not supply them. Separately, the leader-reported
Foundry5.6 private deployment binding and Sol VM KVM/image handoff remain
external-input blockers for their own work, not missing pilot or retention
results. The leader owns acceptance against the original criteria and any future
scope; neither a 30-task nor a 220-task expansion is authorized. This
clarification authorizes no experiment or replay.

## Final outcome and evidence boundaries

The leader supplied the final Task5 fresh/r2 producer receipt at
`2026-10-03T06:40:58.8935285Z`: FAILED, cleanup true, remote terminal acknowledged
and grade null. It binds producer `dfa812a2b7ad10b1aa3c7e873b4fabef9b195bd6`,
run `37101934436`, execution `111147701025` and request
`797141f8291078b82cf0d7a31c20fdadb5105bd0ad45d58f1225b8a39658c05a`.
Its terminal is `4fdd9c2e3da1dbd7ef30d335d5fe378a4cddc84c`, not its predecessor
`3be1c0b892a199fdfccf3d5c4379d40c782119e5`.

The final [terminal observer](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37108712457)
used read job `111162238261` at source
`f7439da4f3443ea67dc02ddea0cb3a1806622e0d` and completed at
`2026-10-03T08:11:30.6738396Z`; approval/execution were skipped. The leader
checked exact source/cell/run/job/request, cleanup, supplied grader hash
`9f656008909dbaf1e299cf42fecfabce11ced81a01d9aeff335a13d8e55d2cca` and immutable
controls/history. The JSON retains the full terminal/claim/manifest tuple,
object-set, observation and retained-authority hashes. This report did not
query either consumed operation.

The final receipt records one generation component, one model call and known
USD 0.13489, with input 66249, cached input 37632, output 3596 and reasoning
2675 tokens. One recorded component does not prove that unrecorded provider
errors or native retries were absent. Its estimated/runtime costs and HTTP
request count are null, with `call_reachability_unknown` and invoice false.

All six failed-terminal observations declare 1 result, 1 ledger, 0 deliverables
and 3 objects including the manifest. They verified controls and declared
metadata/history, not payload bodies: `payload_bodies_verified=false` and
`grading_input_ready=false`. No successful intake or grade exists for those
cells, and absence of all partial work is not established. Those original
terminal-only reads left detailed failure, budget and recovery exposure
unavailable, with `not_recorded_in_terminal_controls`; neither duration nor retry labels identify
a timeout, rate limit or other cause.

Publication-derived evidence does not independently authenticate provider
activity, original inputs or actual compare-and-swap operations. Observer
`writer_acknowledgment=not_established` remains distinct from the producer's
acknowledged publication. The fixed Task5 keep/r1 reader still has null supplied
grader provenance; the later supplied actual preparation hash
`75f38c05e5c348e481e54f4c0b2000772c2414d7bae7519b1f2a38d92e1e0dc5` does not
backfill or rewrite that historical field.

## Later RESULT-only budget observation

The following receipt provenance supplements the eight-point table. Each
observation is stored separately from its cell's original intake or terminal-only
record; no earlier read is relabeled as having inspected RESULT.

The leader's 2026-10-03 20:11 KST supplement supplies the first actual retained
budget observation for Task5 fresh/r2. [Run 37119043633](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37119043633),
read job `111191419176`, succeeded at `2026-10-03T11:17:04.8848163Z`;
approval/execution were skipped. Its fixed producer, terminal and control
identities match the final row above. The new JSON field
`cells[7].current_budget_observation` records this later receipt separately;
the original terminal-only read, missing fields and closeout limits remain
historical evidence and are not backfilled as RESULT verification.

The verified RESULT is 6069 bytes, SHA256
`f68a695c50e26caa4f37984e190216c1bb5eb0553dd4c5c778edc3be521efdd1`.
The JSON retains its result/prepared fingerprints and registered configuration
hash. Observation SHA256 is
`02892ab81228f52767087c2196be84bbeb2f7c399fdd600f773b4f4b74fbce36`;
the unchanged projector is
`96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815`.

| Stored field | Recorded value | Measurement boundary |
| --- | ---: | --- |
| `total_seconds` | 10800 | Registered cumulative budget in seconds |
| `started_unix` | 1791009579.9246106 | Stored Unix timestamp in seconds |
| `expires_unix` | 1791020379.9246106 | Stored Unix timestamp in seconds |
| `remaining_seconds` | 10724.012340545654 | Zero-clamped remaining time at the stored snapshot |
| `wait_seconds` | 0.0 | Recorded retry backoff only, in seconds |
| `attempts_admitted` | 1 | Recorded native admissions, not model calls |
| `native_resumes` | 0 | Confirmed native bindings, not HTTP requests |

The snapshot's `missing` object is empty. Remaining time is not zero, but this
does not identify the final failure cause, uncapped elapsed time or an absence
of provider errors. RESULT-body verification is true; overall payload, ledger
and deliverable-body verification and grading readiness remain false. The
source outcome remains failed/exit 1/cleanup true/grade null, with 1 recorded
model call and known partial USD 0.13489. Detailed failure/recovery exposure
and independent provider/input/CAS authentication remain unavailable. Observer
`writer_acknowledgment=not_established` is still distinct from producer acknowledgment.

The leader's 2026-10-03 22:15 KST supplement adds the paired Task5 keep/r2
RESULT-only observation. [Run 37125749122](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37125749122),
read job `111210580807`, succeeded at `2026-10-03T13:21:06.8522139Z`;
approval/execution were skipped. The fixed producer identity and control tuple
are unchanged. `cells[6].current_budget_observation` records this later receipt
without backfilling its terminal-only read or historical missing fields.

The verified KEEP RESULT is 7619 bytes, SHA256
`d17695351a36522df6b66a1e0fe0860e90410af92c11ec157672a0750ea282ff`.
Its observation SHA256 is
`eca874ea9123475d5632c08c90dc072942a296d3badb1f8923c44db48bb3b043`;
the projector is unchanged. The JSON retains the result/prepared fingerprints
and sealed KEEP configuration hash. Its stored total is 10800 seconds,
`started_unix=1790987596.6290615`, `expires_unix=1790998396.6290615`,
and `missing={}`.

The leader's 2026-10-04 00:19 KST supplement supplies both Task5 r1 observations
at source `3d43a674e47d700dd874680c053a91bc1807b693`, using reader
`dd23824360e03f415feb5c7d247024ac7d67300c4ed7f2120e0eb2c9d6e47eb9`
and the unchanged projector. FRESH/r1 [run 37131238762](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37131238762),
read job `111226607598`, succeeded at `2026-10-03T14:55:40.4040030Z`;
KEEP/r1 [run 37131339406](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37131339406),
read job `111227047774`, succeeded at `2026-10-03T14:58:10.8491476Z`.
Approval/execution were skipped in both. Their observation SHA256 values are
`883f64c6f1c8190c9fde011ba11d33b436438b6ea9c62577d6099f41a398d5c3`
and `a55103477c3be7571e736546b76d338dda6cd12ba908b569af65aef3b7e9febc`,
respectively.

The verified FRESH/r1 RESULT is 7635 bytes, SHA256
`eda9982c2812a5d4e1519c952f65438d1395b5526d07515fcf066dc604a1579a`;
the KEEP/r1 RESULT is 7593 bytes, SHA256
`137dec5dc2c4c2c0614ba253732bc6ebc0388ac9d1d511908f0d618ed7c09a54`.
Both snapshots record 10800 total seconds and `missing={}`. FRESH/r1 records
`started_unix=1790959571.661407` and `expires_unix=1790970371.661407`;
KEEP/r1 records `started_unix=1790976592.4457858` and
`expires_unix=1790987392.4457858`. These are stored timestamps in seconds.
The new `cells[4:6].current_budget_observation` fields retain the exact
result/prepared fingerprints and sealed configuration hashes without changing
the terminal-only evidence. KEEP/r1's supplied-grader field remains null,
distinct from the later preparation hash documented above.

The leader's 2026-10-04 02:23 KST supplement supplies both Task4 FRESH points
at source `c4828cc83892fb9f844599bb6c3be3d66500d9e8`, using reader
`9359eab1be22b54bc6f18092560308058a820dde0a55c365a9ee263f6f9c0f09`
and the unchanged projector. FRESH/r1 [run 37138725894](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37138725894),
read job `111248535588`, succeeded at `2026-10-03T16:59:36.1876048Z`;
FRESH/r2 [run 37138900161](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37138900161),
read job `111249054328`, succeeded at `2026-10-03T17:02:20.9246243Z`.
Approval/execution were skipped. Observation SHA256 values are
`d2b354bc9ad165fc18d90318dac3eb852e64f455f0fa31f89de3f2330f9c896c`
and `7304dd060ec089542085d8156f295f20fd8e3bdfd9ead8af5766894a59c17c83`.

The verified Task4 FRESH/r1 RESULT is 7771 bytes, SHA256
`b93c0d4b0d629ea8f351b60865eb7aa49c2a52e8634c73206d026aebd5112b5f`;
FRESH/r2 is 7737 bytes, SHA256
`c865b09977ca9a904c979531057f573ccc0c5358e20cfec90197853011afbf42`.
Both record 10800 total seconds and `missing={}`. FRESH/r1 records
`started_unix=1790850168.3271084`, `expires_unix=1790860968.3271084`;
FRESH/r2 records `started_unix=1790881801.5121758`,
`expires_unix=1790892601.5121758`. The new `cells[1:3].current_budget_observation`
fields retain exact result/prepared fingerprints, sealed configurations and
the newly derived authority digests
`220b35dec4130fb5c83ffa3a1367f7acab41c9e3e3f740e228628df30de866c0`
and `dfee46e28de07e107384fb986bdc9c0d4d43e21fbefd200818a9004893a396a2`.
Those digests belong only to these new observations; the older terminal-only
records still have no separately supplied authority digest.

The leader's 2026-10-04 05:28 KST supplement adds successful Task4 KEEP/r2.
[Run 37146242626](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37146242626),
read job `111270679161`, has receipt timestamp
`2026-10-03T19:01:45.8846626Z`, with approval/execution skipped. Its observer
source is `5acffea43bc621daf1ae7fba014aa47a559e6ca1`, reader SHA256
`631dd2a76faecd28ae65bdbe69d755f598aa4b025cfc66a8280872c2f3a2bc96`
and the same unchanged projector. Observation SHA256 is
`42ed9d57052c6c062e1686f469b0c9d38d92d58d6bfcdefb2a79905f958c9355`.
The producer source/run/job/request and immutable controls match cells[3], including
retained authority
`7427be5a3d3f5692ca9d92920161c7ddf4491faf39f36f9ee9cee062f45f5705`.

Its verified RESULT is 10238 bytes, SHA256
`8d90bb52bc87f5989baba1eea59de205155523492e9b679087eac5c12b7e539e`.
The JSON preserves result fingerprint
`909ef80ffdce0e59ffeae5010df929ef7d93510c2e54cd710624e61ec343b86a`,
recorded prepared fingerprint
`fb6e4301ec91245601e80fc6f181076513dd71bd358bb0fbc856b5080e8108e8`
and registered configuration SHA256
`307dc07923d377faa7d7c6bd6c4934de2fa5f99e9007dd0d723f3c3337e6d010`.
The snapshot records `total_seconds=10800`,
`started_unix=1790903881.1127117`, `expires_unix=1790914681.1127117` and
`missing={}`; the remaining/backoff/admission/resume values appear in the
eight-point table. The new `cells[3].current_budget_observation` leaves every
historical field and the existing grade unchanged.

This receipt reports a succeeded source outcome, exit0 and confirmed cleanup.
It declares 1 result, 1 ledger and 3 deliverables but verifies only RESULT.
Ledger/deliverable-body and overall-payload verification remain false, as do
new full intake, delivery, grading readiness, a new grade and independent
provider/input/CAS authentication. Its `grade=null` is the budget receipt's
absence of a new grade, not a replacement for the source cell's 30.35/45,
67.44% included / 54.20% full grade. Observer acknowledgment remains
`not_established`, while recorded producer acknowledgment is true. Detailed
failure/recovery exposure remains unavailable with
`not_recorded_in_terminal_controls`; the successful source does not turn
missing detail into an observed absence.

The leader's 2026-10-04 05:59 KST supplement supplies the last point, first-cell
Task4 KEEP/r1. [Run 37151823235](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37151823235),
read job `111287106594`, has receipt timestamp `2026-10-03T20:33:49.6433784Z`;
approval/execution were skipped. Observer source is
`8494f7c9602c90a9cc354db8b683e9ab01b14426`, reader SHA256
`043100017cb1db06f74b562b5feca1a6de8e3eed99ff153645e9a33b3481d975`,
and the projector is unchanged. Observation SHA256 is
`50403a8d9e7b4324e969df5adc5b7e62a37fcf7a9e87b3f882ed1c32da2a9123`.
The primary terminal/claim/output/manifest tuple matches the historical first
row and fixed legacy facade; it does not replace the successful full intake.

The verified RESULT is 10972 bytes, SHA256
`07f335a07ffc8d921a0cfa0c7ab6bbc3728d704adc7c31f7ac1d3594728e3f67`,
with result fingerprint
`3441f200e6e4c53faf1b36f216283c80eee68e5d3e7d827587ba6c3135c7d200`,
recorded prepared fingerprint
`e9ffd87a8da6f06e26449b7f8d68468e674ea241e787a84568dace72774a2247`
and registered configuration SHA256
`08b29f44cb57312fd5757a3192c1a64855922bcd3d48d8e02fed96c4160683cb`.
The snapshot records `total_seconds=10800`,
`started_unix=1790763001.2195864`, `expires_unix=1790773801.2195864` and
`missing={}`; the eight-point table retains the remaining/backoff/native counts.

Newly derived values exist only inside `cells[0].current_budget_observation`:
claim identity 1287 bytes/SHA256
`2934d7cc0607be4cd96b5a9f57a7726530cef72548acf81388577dcbbc9addb0`,
output-object-set SHA256
`ec8c97776d5e1d426f4c506cc571721a1a89d330c25f171612699c7a05813b76`,
retained authority
`110fbd2bbced7528236fda846bf930198006d6867a100cf690b03b7a1d55777c`
and recorded source exit_code0. The original row still lacks a numeric
exit_code key and keeps null claim hash/size and object-set digest with their
historical missing reasons. This is a later observation, not a backfill.

The source remains succeeded with cleanup true. The receipt declares 1 result,
1 ledger, 4 deliverables and 7 output objects, and verifies only RESULT.
Ledger/deliverable/overall-body verification, new full intake, delivery,
grading readiness, new grade and independent provider/input/CAS authentication
remain false. Observer acknowledgment remains `not_established`, while recorded
producer acknowledgment is true. Detailed failure/recovery exposure remains
unavailable with `not_recorded_in_terminal_controls`. The existing grade
30.6/45, 68.0% included / 54.64% full and all costs remain unchanged; this
budget receipt's null grade does not replace that historical grade.

Remaining time is zero-clamped, not exact uncapped elapsed time. Wait is retry
backoff only. Native admissions and confirmed resumes are not model calls or
HTTP requests. The six failed source outcomes remain failed/exit 1/cleanup true/grade null;
both KEEP points retain their succeeded source outcomes. No inference cost
or grade changed. All eight receipts verify only RESULT bodies, not ledger,
deliverables or overall payload, and none establishes new grading readiness or
independent provider/input/CAS authentication. Detailed failure/recovery exposure
remains unavailable. The stored differences do not
identify a failure cause, absence of provider errors or a causal retention effect.
Observer `writer_acknowledgment=not_established` remains distinct from producer
acknowledgment.

All eight budget observations are verified and consumed. None was queried or
replayed here, and no raw payload was supplied. Retained budget/backoff/native
field coverage is complete for the diagnostic; detailed recovery exposure,
all downtime, complete costs and causal attribution remain unavailable. This
does not by itself complete every card criterion; the finite execution and
available-accounting closeout is unchanged.

## Limits and finite closeout

Post-selection, two repetitions, fixed order and service variation, evolving
source wrappers, unavailable recovery detail and uncalibrated
judging prevent a causal retention or general model-performance claim. The
public report and JSON disclose only task IDs, control identities and aggregate
measurements; private metadata, secret dataset names, original task bodies and
deliverable bodies are excluded.

Rows 0–6 come from the [retained completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/f7439da4f3443ea67dc02ddea0cb3a1806622e0d/tasks/LATEST_TASK_RESULT/README.md)
and fixed source bindings at that revision. Row 7's completed outcome comes
from the leader's 2026-10-03 17:05 KST evidence; its source/run/request binding
was already fixed. The older pending status is superseded, not rewritten as a
completed historical read. No conflicting numeric value was found in those
sources. Unavailable fields retain explicit missing reasons in the JSON.

Public checking can reproduce row counts, Decimal arithmetic and comparison
with committed identities. It cannot reproduce private payload authentication,
provider behavior or the original executions. No producer, reader, grading run
or prior test was rerun for this report. Accepted reader HEAD
`70c80baa5c150d1734bb77de7fac1ebaac17b303`, review
[5399481664](https://github.com/hyeonsangjeon/gdpval-realworks/pull/729#pullrequestreview-5399481664),
all ten checks and its consumed 17.09s proof are historical acceptance evidence,
not validation of this consolidated revision. The [latest task record](../LATEST_TASK_RESULT/README.md)
separates this report's local evidence checks from the consumed lifecycle,
reader and earlier report proofs; none of those earlier proofs was repeated.

This unit adds only the two successful-cell current observations to the JSON,
updates the report and directly coupled evidence expectations, and records
the finalization evidence. The original pilot, runtime, workflows, all budget
readers and grading code remain unchanged. Removing only cells[0] and cells[3]'s
new observation fields restores the accepted prior JSON semantically; its
original raw and canonical hashes retain their historical scope. Source,
structural and candidate checkpoints and a protected condition/difference
ledger are retained locally. Public consistency checks cannot establish new
private-payload, provider or CAS authentication.

Independent immutable-HEAD review, applicable same-HEAD CI and the leader's
acceptance decision remain required. The measured fields support a finite
evidence-based card decision without requiring fresh model runs to fill every
explanatory gap. Further paid scope or causal study design would require a
new leader decision; none is proposed or authorized, and no 30/220-task
expansion is authorized.

[deadline-source]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/8494f7c9602c90a9cc354db8b683e9ab01b14426/batch-runner/core/codex_task_deadline.py#L519
[recovery-source]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/8494f7c9602c90a9cc354db8b683e9ab01b14426/batch-runner/core/codex_task_deadline.py#L204
[core-classification-source]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a999a74d767cd52e2963259a0f0d1832a420740f/batch-runner/core/execution_errors.py#L83
[runner-classification-source]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a999a74d767cd52e2963259a0f0d1832a420740f/batch-runner/core/codex_runner.py#L527
[offline-classification-source]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a999a74d767cd52e2963259a0f0d1832a420740f/batch-runner/scripts/analyze_codex_run.py#L112
[compact-classification-evidence]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/0f9162093444e3143960e631a95edac6e46f3b29/batch-runner/docs/analyze_codex_run.md#L46
[retirement-source]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/8494f7c9602c90a9cc354db8b683e9ab01b14426/batch-runner/core/codex_task_deadline.py#L601
[producer-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/d34dc6e0426239f0707327160eb0967ae8fa7c26/tasks/LATEST_TASK_RESULT/README.md
[success-budget-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/c0b5ea5f1f14036d011609ddf887de533bc8d0d1/tasks/LATEST_TASK_RESULT/README.md
[first-budget-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/fc0c9795864ab73b2a998e8baf7ecffcfd3e522b/tasks/LATEST_TASK_RESULT/README.md
