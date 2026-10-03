# Eight-cell retention diagnostic

The finite diagnostic has eight recorded producer outcomes: two succeeded and
six failed. Task4 KEEP succeeded in 2/2 cells and FRESH in 0/2; Task5 KEEP and
FRESH each succeeded in 0/2. These are descriptive results from two post-selected
tasks, not a causal retention or model-performance finding. The six failures
have null grades, not zero scores.

The execution and available-accounting scope is closed to this evidence. The
leader still owns the report review and card decision; this closeout does not
resolve all Project5 work, missing costs or causal questions, and authorizes no
new execution, read, grade or repetition. The [machine-readable table](retention_diagnostic_readout.json)
contains the full identities and missing reasons. The separate [original pilot report](REPORT.md)
remains closed at 24 epoch04 outcomes (18 graded and 6 model-free UNGRADED) plus
6 frozen epoch03 failures, not 30 identical-source successes.

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

## Inference and grading accounting stay separate

Adding the recorded inference amounts with Decimal gives USD 5.206594 across
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
cells, and absence of all partial work is not established. Detailed failure,
budget and recovery exposure are unavailable with
`not_recorded_in_terminal_controls`; neither duration nor retry labels identify
a timeout, rate limit or other cause.

Publication-derived evidence does not independently authenticate provider
activity, original inputs or actual compare-and-swap operations. Observer
`writer_acknowledgment=not_established` remains distinct from the producer's
acknowledged publication. The fixed Task5 keep/r1 reader still has null supplied
grader provenance; the later supplied actual preparation hash
`75f38c05e5c348e481e54f4c0b2000772c2414d7bae7519b1f2a38d92e1e0dc5` does not
backfill or rewrite that historical field.

## Limits and finite closeout

Post-selection, two repetitions, fixed order and service variation, evolving
source wrappers, unavailable realized budget/recovery detail and uncalibrated
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
not validation of this new report. The [latest task record](../LATEST_TASK_RESULT/README.md)
records the separate bounded local consistency check. Further paid scope or
causal study design would require a new leader decision; none is proposed or
authorized by this closeout.
