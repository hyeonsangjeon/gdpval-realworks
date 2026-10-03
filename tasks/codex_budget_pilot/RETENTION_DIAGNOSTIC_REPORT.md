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

## Later RESULT-only budget observation

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

| Recorded point | Remaining seconds | Retry-backoff wait seconds | Native admissions | Confirmed native resumes |
| --- | ---: | ---: | ---: | ---: |
| Task4 fresh/r1 | 0.0 | 8983.719460487366 | 39 | 0 |
| Task4 fresh/r2 | 0.0 | 8985.385900974274 | 39 | 0 |
| Task5 fresh/r1 | 4909.906562328339 | 3781.06050658226 | 18 | 0 |
| Task5 keep/r1 | 7373.157982349396 | 2580.858815908432 | 13 | 12 |
| Task5 keep/r2 | 0.0 | 8742.75936126709 | 38 | 37 |
| Task5 fresh/r2 | 10724.012340545654 | 0.0 | 1 | 0 |

Remaining time is zero-clamped, not exact uncapped elapsed time. Wait is retry
backoff only. Native admissions and confirmed resumes are not model calls or
HTTP requests. All six source outcomes remain failed/exit 1/cleanup true/grade null;
no inference cost or grade changed. All six receipts verify only RESULT bodies, not ledger,
deliverables or overall payload, and none establishes grading readiness or
independent provider/input/CAS authentication. Detailed failure/recovery exposure
remains unavailable. The stored differences do not
identify a failure cause, absence of provider errors or a causal retention effect.
Observer `writer_acknowledgment=not_established` remains distinct from producer
acknowledgment.

Both r2 budget observations are consumed, as are both Task5 r1 and both Task4
FRESH observations. None was queried or replayed here, and no raw payload was
supplied. Both successful Task4 KEEP budgets remain unobserved. These six
stored points do not complete the card's realized
budget, wait, admission,
resume and attribution criteria; the finite execution/accounting closeout is
unchanged.

## Limits and finite closeout

Post-selection, two repetitions, fixed order and service variation, evolving
source wrappers, limited realized budget evidence, unavailable recovery detail and uncalibrated
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
