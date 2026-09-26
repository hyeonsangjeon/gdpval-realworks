# Latest task result

## PROJECT5-FAILED-A1-NO-JUDGE-POLICY

Implemented a local, unpublished model-free UNGRADED terminal for the exact
recorded task4 A1 failure, and verification of that terminal as recorded B1's
immediate predecessor. This records the absence of a grade, not a zero score,
pass, rubric verdict or successful model result. No live record was written.

Work continued from `79c313a94be1a22093cf6cd00245a5564b0111d8`. The leader's
explicit policy decision resolves the earlier durable-evidence gap only for
this fixed pair. The required bounded extreme-reasoner review returned
APPROVE-WITH-CONDITIONS before production/workflow edits. A later bounded
inspection requested canonical-byte equality for the complete terminal;
that guard and its numeric-to-boolean mutation were included before testing.
No further policy change was identified by that review.

### Closed policy and source boundary

Both cells remain in `budget_pilot_ci_20260925_04`, with inference producer
`78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e` and the original order. Only these
two task4 fixed-content requests are registered:

| Cell | Ordinal | Original inference run | Completion request SHA-256 |
|---|---|---|---|
| `3baa0009-5a60-4ae8-ae99-4955cb328ff3_A_r1` | 18 | `36234320019` | `a913f0236e801e31ab7c0f58c8545ad6375d7092c06fa77f839225d03efe52d8` |
| `3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r1` | 19 | `36235926112` | `f3546942ebac25c3c3cd1788dfb792a80e3e10f465999bebf7730fb651cb2bde` |

The dedicated `record-ungraded` phase accepts only A1's fixed failed inference:
exit 1, `child_nonzero_exit`, one inference child, confirmed cleanup, no timeout
and zero deliverables. It revalidates the genuine failed materialization,
original result/ledger bytes, fixed completion, producer/run/input/object proof,
request approval and controller source. Its source/config-only staging verifies
the expected predecessor closure without a judge entry or rubric staging.
The separate readiness flag is `model_free_record_ready=true` with
`judge_ready=false`. The workflow's exact-A1 step cannot enter OIDC, Step8 or
model execution; ordinary judged readiness/publication conditions remain intact.

The distinct claim and terminal formats are
`codex-pilot-model-free-ungraded-claim-v1` and
`codex-pilot-model-free-ungraded-terminal-v1`. They preserve the verified
inference completion, original campaign denominator of 30 cells, receipt and
missingness. No judge child, numeric quality score or rubric verdict is added.
Recorder accounting is separately `not_measured`, with null monetary amounts
and HTTP request count, and `invoice_complete=false`; it is not a zero-cost
claim. The supplied partial known inference receipts remain USD 0.060359 for
A1 and USD 0.262451 for B1, not total costs or invoices. A1's underlying child
cause and internal attempt count remain unknown. The earlier supplied usage
and payload identities remain separately recorded below; none were recovered.

Two one-use reservations guard fixed-parent CAS claim and terminal writes on
the existing private grading ref. Canonical claim bytes are read back from the
server and cached independently before publication. The verifier checks the
original claim, immutable history, parent/object identity and the complete
canonical terminal bytes. A lost or ambiguous response remains unresolved
locally and consumes the attempt. A later separately authorized B1 may verify
durable server state without asserting that A1 received its lost response;
there is no acknowledgment-of-ack record, replay or old-receipt rewrite.

A1 still requires the actual immediate task3 A2 grade under the same explicitly
declared future controller. Its retained inference is
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r2`, run `36232859421`, completion
`f4de6c1d36c8f3a2c077be9e4be370545eeb5a11d9513752caa4d40bd08e1bd8`.
No actual task3 A2 grade run/revision or future controller is supplied here.
B1 accepts A1 only through the distinct UNGRADED verifier and full retained
inference-observation equality, never as a successful judged grade. The
ordinary judged-terminal verifier still requires a real Step8 child. Task3
A1's historical task2 A2 transition is unchanged.

### Exact offline evidence

Only `tests/test_codex_budget_pilot_ungraded.py::test_fixed_failed_a1_no_judge_policy`
was selected. It reuses genuine compiler, native-error/Step2 serialization,
ledger, materialization and retained-history helpers behind fake or blocked
external boundaries. One shared synthetic history feeds isolated mutations.
The positive history records A1 without invoking a judge child and then uses
that verified UNGRADED predecessor for B1's ordinary fake-child grading path.
These synthetic run IDs, bytes, revisions and calls are not live evidence.

| Invocation | Immutable tested SHA | Actual result |
|---|---|---|
| New selector | `e42c8c68f7e0f16366c1ec5a12fbc4e663c10ee1` | **1 failed, 40 passed in 75.30s**, exit **1**; **50** collected, **9** unexecuted |
| Corrected failure plus unexecuted cases only | `c4b539d210bb138ed2dd3afd68e6509d079dd8ec` | **10 passed, 40 deselected in 36.58s**, exit **0** |

The initial `[terminal_receipt]` mutation assigned null to an already-null
synthetic completion receipt. The fixture-only correction substitutes a
different schema-valid unavailable receipt and still requires refusal. No
production guard changed. The follow-up selected only `terminal_receipt`,
`terminal_controller`, `terminal_boolean`, `terminal_parent`,
`terminal_previous_hash`, `terminal_history`, `b1_missing`, `b1_observation`,
`replay` and `ordinary_refused`. The 40 earlier passes were not rerun; these
observations are not a single 50-case passing invocation.

Cases cover the exact pair/closed remainder, failure and deliverable checks,
source/run/completion/original-byte/privacy/approval/ref refusals, actual prior
grade and retained-observation equality, materialized bytes, source closure,
CAS, lost responses, server readback, cached admission, terminal types/scores/
children/receipts, predecessor tampering, replay and unchanged old state.
Python 3.10.12 / pytest 9.1.1 ran credential-free under `env -i`, offline HF
flags, disabled plugin autoload and
`-m 'not integration' -p no:cacheprovider --maxfail=1 -q`. No old passing family,
full suite or CI run was repeated. Logs are in
`/tmp/project5-no-judge-policy.3vuzHp/e42c8c68f-focused.log` and
`/tmp/project5-no-judge-policy.3vuzHp/c4b539d21-remaining.log`.

The prior gap reproduction remains separate: **1 failed, 15 passed in 29.96s**
at `0d22d32733b8c3238344fdd9dd19815b2ba8cb8f`, followed by the corrected
workflow fixture alone, **1 passed in 34.50s** at
`3e692fed1e1734f4e8c82b6d8c4d41b8e48e63f2`. Earlier task3 observations remain
unchanged below. Only these two completion records changed after the final
tested SHA.

### Remaining authority and limits

Main/inference source780 remains held. Published PR686 head
`e6c357374ea5b3b19e72f574e77dcaa5e3619a84`, direct review `5325618521` and
all 9 passing checks cover only that old head, not this unpublished delta.
Fresh leader review, later authorized CI/publication, the actual preceding
task3 A2 grade, a shared explicit reviewed controller and same-run protected
one-result request approval remain gates before any live operation. B1 needs
its own separately authorized grading request after a verified A1 record.

The completion checksums remain fixed-content requests, not invented private
terminal revisions or independent proof that original outer metadata was never
rewritten. Existing no-clobber resolution and producer/controller separation
remain. Inference/runtime/input/budgets and `default_v2_sol_max.yaml` /
GPT-5.6 Sol/max are unchanged; there is no general skip flag or task3 readout
registry. Other task4/task5 fixed-content requests remain closed. The leader's
context-only C1 retention update and C2 run `36242339639` were not queried,
polled or registered.

Nothing was pushed, republished, merged, dispatched or executed live. No live
HF/Azure/model/grade/readout call, Project or credential change, old-claim/grade
rewrite or held-source change occurred. The full skill catalog was reviewed
once. Experiment-design and the consolidated grading spec kept this
failure-evidence policy separate
from the unchanged comparison and scoring contract. Experiment-report-en then
im-not-ai-en preserved the split evidence and authority limits. The following
prior endpoint is a historical snapshot; its policy gap is superseded only by
the local implementation above.

## Prior PROJECT5-TASK4-FAILED-A1-AND-B1-PREP

Task4 A1/B1 grading preparation stops at a confirmed policy gap. A retained
execution failure can become a local ungraded preparation, but the existing
connector cannot publish that preparation as a no-judge grade terminal. The
requested recorded-content B1 continuation needs A1's actual preceding grade;
local preparation cannot substitute for it. No task4 registration, workflow,
production code or grading policy changed. The local delta contains one new
focused test, a directly coupled synthetic-input fixture extension and these
two completion records. Nothing was pushed or republished.

Work began in the clean owned PR686 worktree at
`e6c357374ea5b3b19e72f574e77dcaa5e3619a84`. The leader supplied direct review
`5325618521` and all **9** passing CI checks for that head only. They do not
approve these local changes. Main/inference source
`78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e` remains held and unchanged.

### What the existing contract permits

The bounded pre-edit reviewer returned **APPROVE-WITH-CONDITIONS** for a
focused offline reproduction and the two completion records only. The review
confirmed the distinction below and did not authorize a no-judge terminal writer
or a production registration change.

In `codex_budget_pilot_grading.py`, `prepare` preserves the failed inference and
materialized task status `error`, records
`retained_result_unsuccessful_ungraded`, and returns `grading_state=UNRUN` with
`judge_ready=false`. It returns before grader checkout, rubric staging or an
entry contract. `_ready` then refuses `claim`, `judge` and `publish` with
`bound_native_materialization_required`. No grading reservation, judge call or
HF write occurs on those paths.

Published terminal outcome `ungraded` means something different: `publish` and
`_grade_terminal` still require an actual judge entry and confirmed owned
cleanup. The workflow skips OIDC, claim and judge when preparation is not
ready; publication also requires a successful claim and a judge step that was
not skipped. The consolidated grading spec fixes the judge, scoring and rubric
contract; it supplies no authority to invent a no-judge terminal here.

The immediate-predecessor requirement belongs to the **recorded-content**
route. The generic same-source route can accept bootstrap and scan eligible
grades, so its behavior is not proof of that stricter continuation policy.
Both actual task4 selectors, their supplied completion checksums and a distinct
synthetic future controller still refuse with
`closed_retained_producer_binding_required`. This is a registration refusal,
not an observed downstream missing-predecessor refusal.

### Supplied retained pair, not recovered payloads

Both cells belong to `budget_pilot_ci_20260925_04`, use prefix
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_`, and retain inference producer
`78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e`. The leader supplied workflow
attempt **1**, job `cell`, one child, confirmed cleanup and no timeout for each.
These are two cells of one original task, not new tasks or grading results.

| Cell | Ordinal | Inference run / job | Completion payload SHA-256 | Retained execution |
|---|---|---|---|---|
| `A_r1` | 18 | `36234320019` / `108383230113` | `a913f0236e801e31ab7c0f58c8545ad6375d7092c06fa77f839225d03efe52d8` | Failed, exit 1, `child_nonzero_exit`, zero deliverables, no grade |
| `B_r1` | 19 | `36235926112` / `108387549004` | `f3546942ebac25c3c3cd1788dfb792a80e3e10f465999bebf7730fb651cb2bde` | Succeeded, exit 0, three deliverable identities, no grade |

On **2026-09-26 UTC**, A1's claim acknowledgment was recorded at
**10:00:17.3580246**, failed-terminal acknowledgment at **10:10:54.2467285**,
and run failure at **10:11:01**. The leader independently verified artifact
`10904001033`'s digest. Its result identity is **8965 bytes** /
`c1db49629a80a65a6b216101edf9c3d1ea71159b4bc2bde7df6639beaba5e60c`;
the ledger identity is **3429 bytes** /
`2fdde79a2820d80cbe8b1ddd9196cdc6ac61ab0072a3b41de9d8914d23380a73`.
The underlying child cause and internal attempt count are unknown. This is not
evidence of a rate limit, deadline expiry or attempt-cap exhaustion.

B1 executed **10:32:25–11:19:33 UTC**. That outer step lasted **47m08s**;
it does not establish an internal attempt count. Its claim acknowledgment was
recorded at **10:32:18.6021416**, terminal acknowledgment at
**11:19:39.4555176**, and run success at **11:19:46**. The leader verified
artifact `10904499820`'s digest. The three supplied deliverable sizes are
**1036**, **90703** and **2502 bytes**; names, formats and hashes were not
supplied. Execution success does not establish quality.

| Cell | Partial known inference USD | Input tokens | Output tokens | Cached input tokens | Reasoning tokens |
|---|---|---|---|---|---|
| A1 | 0.060359 | 23696 | 1457 | 9216 | 796 |
| B1 | 0.262451 | 237830 | 8156 | 201984 | 5397 |

These are separate partial usage-derived receipts, not total experiment costs
or reconciled invoices. Estimated costs and HTTP request counts are null;
`invoice_complete=false`. No task4 grade, score, raw payload or private terminal
SHA was supplied or recovered. The completion checksums identify fixed content,
not independently known terminal revisions or proof that every original outer
metadata envelope was never rewritten.

A1's actual inference predecessor remains task3 A2,
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r2`, producer780, run `36232859421`,
completion `f4de6c1d36c8f3a2c077be9e4be370545eeb5a11d9513752caa4d40bd08e1bd8`.
Its future grade ID is unknown. The required grade must be an actual preceding
grade under the same explicitly declared future controller, not one adopted
from remote metadata. Task3 A1's special historical task2 A2 transition remains
unchanged: writer `a5e5d2589caff21309f0a1c21bb7d9d333ad47c6`, grade run
`36214413190`, revision `3a8e135cd232ab900e003fc6d9c459957a0b990e`.

### Exact offline evidence

The new selector was
`tests/test_codex_budget_pilot_task4_failed_grading.py::test_failed_task4_a1_grading_policy_gap`.
It uses the real compiler, native-result/error projection, Step2 row serializer,
ledger export, fingerprints, retained controls and grading materializer. The
native turn, source/host, original inputs, install syscall and remote transport
are synthetic. Existing genuine synthetic history is shared, with isolated
copies for mutations. No successful A1 is produced and then relabeled failed;
no A1/B1 grade terminal is fabricated. Synthetic usage, hashes and revisions
are not the supplied live identities.

The diagnostic uses producer780 as both source and controller with a synthetic
immutable inference revision. It does not prove that a future controller is
eligible. B1's generic diagnostic stops at successful input preparation, with
no claim or judge; it does not prove the recorded continuation rule. The cases
also check source/byte/cleanup/publication-acknowledgment refusals, approval
refusals, unchanged prior bytes, no-clobber preparation, zero grading writes
and no judge entry. All external, credential and model boundaries are fake or
blocked. No native-host capability, live grading or quality claim follows.

| Invocation | Immutable tested SHA | Actual result |
|---|---|---|
| New task4 selector | `0d22d32733b8c3238344fdd9dd19815b2ba8cb8f` | **1 failed, 15 passed in 29.96s**, exit **1**; **16** collected |
| Corrected `[workflow_guards]` only | `3e692fed1e1734f4e8c82b6d8c4d41b8e48e63f2` | **1 passed in 34.50s**, exit **0**; **1** collected |

The sole initial failure was the new fixture's lookup of an unnamed workflow
step (`KeyError: 'name'`). The correction indexes named steps; every required
readiness/publication assertion remains. Only that failing parameter was
selected again. These are separate invocations, not a manufactured 16-case
pass. Only completion records changed after the corrected tested SHA.

Both invocations used Python **3.10.12**, pytest **9.1.1**, credential-free
`env -i`, offline HF flags, disabled plugin autoload,
`-m 'not integration' -p no:cacheprovider --maxfail=1 -q`. No prior selector,
full suite or CI run was repeated. Earlier observations remain separate:

| Earlier validation, not rerun | Immutable tested SHA | Recorded result |
|---|---|---|
| Task3 A1 initial | `9a48596e6dbfd19dd90add057a29ca1e5e649ae3` | **1 failed, 26 passed in 307.84s** |
| Task3 A1 follow-up | `aa1ec63ca98a35d289be5ee146a41f1ae69f6256` | **5 passed in 72.19s** |
| Task3 chain setup | `0b6e62d722cc7394c7eedb23d7265cad816599bd` | **1 setup error in 22.37s**, exit **1**; **39** collected, none passed, **38** unexecuted |
| Corrected task3 chain | `200bb89ce83bcab1f7c04c4d770f98e0a23a380b` | **39 passed in 55.71s**, exit **0** |
| Task3 A2-only | `342bc6d47a5ca2c2dd582519a5730111fc4190c9` | **20 passed in 37.62s**, exit **0** |

### Remaining policy and authority

The leader must decide whether to authorize a durable, model-free ungraded
predecessor record for a retained inference failure, or keep this recorded
grading chain blocked. Such a decision would need its own reviewed contract;
this task adds no terminal writer, skip rule, invented zero/pass score or
unnecessary judge invocation. Task3 A2's actual grade and a single explicitly
declared future controller also remain prerequisites. Neither is inferred from
the synthetic fixture. No task4 or task5 fixed-content registration was added.

At the leader's observation, task4 C1 run `36239016015`, job `108395938306`,
was executing from **2026-09-26T11:33:10Z**, without a terminal or artifact.
Its result remains unknown here; it was not queried, polled or registered.
The source780 hold remains active. The existing private inference/grading refs,
no-clobber resolution, source/input/byte/privacy proofs, approval, server
readback, one-use fixed-parent CAS, cleanup and no-replay controls are unchanged,
as are inference/runtime/budgets and
`default_v2_sol_max.yaml` / GPT-5.6 Sol/max. No task3 readout path was added.

The local changes require fresh leader review and any later authorized new-head
CI before publication or execution. Nothing was pushed, republished, merged or
dispatched. No live HF/Azure/model/grade/readout call, Project mutation,
credential change, old claim/grade change or source reseal occurred.

The full skill catalog was reviewed once. Experiment-design and the grading
spec kept the failed-inference/local-preparation/published-grade distinction
explicit. Experiment-report-en followed by im-not-ai-en preserved the split
validation and supplied-evidence limits. Prior detailed task3 records remain
in the reviewed baseline and unchanged changelog entry; the following sections
are historical snapshots, not new authority.

## Prior PROJECT5-TASK3-A1-GRADING-PREP

Prepared only the first grading of retained cell
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r1`, ordinal **12**, in
`budget_pilot_ci_20260925_04`. The route preserves its actual inference
producer and the historical task2 A2 grade while binding a distinct future
grading controller. It adds no sibling registration or general source override.
This is offline preparation, not a live grade or a quality result.

The final narrow follow-up returned **5 passed in 72.19s**, exit **0**, at
`aa1ec63ca98a35d289be5ee146a41f1ae69f6256`. The initial **1 failed, 26 passed
in 307.84s** result and **4** unexecuted cases remain separate below. Only the
two completion records changed after the follow-up SHA.

Work started in a new clean owned worktree/branch from supplied main/inference
source `78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e`. The leader reports it is
tree-identical to reviewed `c614e2b0215de6279f96279933fe73e7934ce7e1`, review
`5324900898`, with all **9** checks passed. The completed CI partition had
core **27m14s** and pilot **29m28s** within unchanged **45-minute** caps.
Those are supplied predecessor facts, not new measurements or approval of this
grading delta. Neither that work nor any old test family was repeated. The
preserved checkout, earlier PR branches and accepted task2 note are untouched.

### Closed source and predecessor boundary

A credential-free offline compile at baseline780 with this exact retained
tuple and a synthetic distinct controller refused with
`closed_retained_producer_binding_required` before any session or mutation.
That bounded reproduction is separate from the pytest observations.

The adapter reuses fixed-completion intake, immutable control/object readers
and the existing no-clobber resolution record. Both initial intake and restored
preparation require the fixed cell, ordinal, producer, inference run, completion
checksum and task2 A2 inference parent. The grade branch must still end at the
fixed A2 grade. Existing historical-writer helpers verify its original writer,
run, config and grader source closure, complete retained observation and
publication receipt. The selected inference predecessor must agree with that
verified A2 input. The fixed grade predecessor is checked again at local
admission before judge and during terminal validation.

| Binding | Required identity |
|---|---|
| Selected inference producer | `78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e` |
| Selected inference run | `36225255532`, attempt **1** |
| Selected completion request | `1fb1bc33acab5b2bdefd70744a899c808d984e9c231deded4217ad92d4dc7e3d` (checksum, not a terminal revision) |
| Previous task2 A2 grade | `3a8e135cd232ab900e003fc6d9c459957a0b990e` |
| Previous grade writer/run | `a5e5d2589caff21309f0a1c21bb7d9d333ad47c6` / `36214413190`, verified by readout `36220575848` |
| Previous inference producer/run | `e7a28db07ebe10d6508b9256137763cc82f9a1d1` / `36202190875` |
| Previous inference terminal | `e22f0c3de79bbfce084aedde64fa56c40959fde0` |
| New grading controller | Distinct, truthful, leader-bound reviewed source; not yet authorized |

The required bounded extreme-reasoner decision was **APPROVE-WITH-CONDITIONS**
before production/workflow edits. Its scope includes the singleton binding,
historical A2 proof, local admission guard and exactly three coupled producer
mappings in `grade-run.yml`. Protected approval/digest, ref-main execution,
renderer and atomic input installation, private
`pilot-inference-20260925-04` / `pilot-grades-20260925-04`, fixed-parent CAS,
one-use admission, cleanup, publication and redaction remain unchanged.
`default_v2_sol_max.yaml` / GPT-5.6 Sol/max and the fixed rubric/source
expectations remain unchanged, with one eventual grading invocation and no
low-score regrade. Inference model/runtime/input/budget code, source pins,
readout registrations and the completed backend CI partition are unchanged.

### Focused offline evidence

The only selector was
`tests/test_codex_budget_pilot_task3_a1_grading.py::test_fixed_task3_a1_grading_handoff`,
using the existing Python **3.10.12** / pytest **9.1.1** environment,
credential-free `env -i`, offline HF flags, disabled plugin autoload,
`-m "not integration"`, no pytest cache and stop-on-first-failure.

| Invocation | Immutable tested SHA | Actual result |
|---|---|---|
| Initial selector | `9a48596e6dbfd19dd90add057a29ca1e5e649ae3` | **1 failed, 26 passed in 307.84s**, exit **1**; **4** cases unexecuted |
| Failed case plus previously unexecuted cases | `aa1ec63ca98a35d289be5ee146a41f1ae69f6256` | **5 passed in 72.19s**, exit **0** |

The initial `terminal_parent` fixture called the verifier outside the existing
isolated session. The fake transport therefore rejected a synthetic token
environment variable before reaching the intended predecessor refusal. The
correction uses that same session helper and removes the unused clock import;
production bytes did not change. The follow-up selected only `terminal_parent`,
`cas`, `claim_lost`, `publication_lost` and `cleanup` by their exact node IDs.
No previously passing case was rerun, and these results are not one
**31-pass** invocation.

Existing genuine compiler, serialization, materialization, Step8 and ledger
writers construct a synthetic complete task2 predecessor chain and a selected
task3 result with two deliverables. The cases exercise advanced inference refs,
immutable resolution, source/run/hash/parent/receipt/cleanup/ref refusals,
workflow producer mappings and the actual inline approval digest, denied or
missing approval, reruns, local admission/terminal tampering, CAS, lost claim
and publication responses, no replay and unchanged old state. External/model
boundaries are fake or blocked. Native atomic installation uses the existing
explicit fixture double; this is not a new native-host capability, renderer,
authentication, live retention or judge measurement. Synthetic filenames,
bytes, run IDs and commit labels do not reconstruct historical payloads.

### Supplied retained A1 evidence and limits

The leader reports task3 A1 run `36225255532`, job `108357919770`, attempt
**1**, succeeded and was retained on **2026-09-26 UTC**. Claim verification was
at **06:59:21.2032352**, execution **06:59:34–07:08:51**, terminal verification
**07:08:57.0861555**, and run completion **07:09:05**. Artifact `10900452617`
has the independently recomputed completion payload checksum listed above.
The completion reports exit **0**, one child, confirmed owned cleanup and no
timeout. There is no grade; native state was not archived.

| Supplied identity only | Bytes | SHA-256 |
|---|---:|---|
| Deliverable 1 | 63889 | `4c8ba5cca837168faa60c7eb3d9ebcc35fbff1feafb22baaaa2bfd828c56b85c` |
| Deliverable 2 | 23176 | `3f0dc5ad09842503bdb585a1a9299cfc246b04208a68820f3969b40133e9ba30` |
| Result | 10052 | `337c66d7e078e96b4431cd2355aa3e8e267cbc576d77e4dda300fbcf94ef3af5` |
| Ledger | 1850 | `377bcd215aae8673dc81c27a6cce46a424829143be99d20367d43e1b5ef6df90` |

Names, formats and raw payloads were not supplied or recovered. Partial known
inference cost is **USD 0.987634**, with **922953 input / 43268 output /
875008 cached / 18706 reasoning tokens**. Estimated cost and HTTP request count
are null; invoice completeness is false. These receipts are not total experiment
or grading cost, a reconciled invoice, a request count or quality evidence.
No independent judge-validation evidence is newly supplied.

The new A1 private terminal SHA remains unsupplied. The request checksum is
resolved through existing immutable-history verification; it is never relabeled
as a revision. Fixed-content/publication-derived proof does not independently
authenticate that original outer metadata was never rewritten. Original and
derived result bytes, fingerprints and provenance remain distinct. No old
claim, grade, input, output, clock or source binding was rewritten.

### Exact future request and remaining authority

The following inputs describe one future request to `.github/workflows/grade-run.yml`
on `main`, only after the leader binds a distinct reviewed controller and lifts
the current source hold. They are not a dispatch instruction for held source780,
and no future merge SHA or private terminal is guessed.

```json
{
  "experiment_yaml": "pilot/2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r1",
  "inference_revision": "1fb1bc33acab5b2bdefd70744a899c808d984e9c231deded4217ad92d4dc7e3d",
  "grading_config": "default_v2_sol_max.yaml",
  "force": false,
  "tasks_limit": 0,
  "tasks": "",
  "dry_run": false,
  "paid_approval": true,
  "resume": false,
  "resume_chunk": 0,
  "shard_count": 1,
  "shard_index": 0,
  "run_ordinal": 1
}
```

The leader issued task3 B1 run `36226798976`, job `108362291447`, at
**07:26:49 UTC** on the same780 source and holds it for the remaining original
inference series. No B1 outcome was supplied or queried. This draft is not
permission to land during that hold. Fresh exact-head review, CI, truthful
future controller binding and one explicit leader-authorized first-grade
request remain. No live HF/readout/inference/judge call, workflow dispatch,
Azure management, credential change, Project mutation, main change, merge,
source reseal or CI polling occurred.

The full skill catalog was reviewed once. Experiment-design kept the source
boundary separate from the unchanged comparison contract; experiment-report-en
then im-not-ai-en preserved the split test results, partial accounting and proof
limits. No new experiment axis or score analysis was introduced. The sections
below preserve prior observations as historical snapshots, not current live
authority or new test evidence.

## Prior PROJECT5-CI-BUDGET-PILOT-PARTITION

Moved only the existing budget-pilot test family out of core `pytest` and into
a separate step in the existing `pilot-contracts` job. The focused offline
partition selector returned **1 passed in 11.30s**, exit **0**, at
`14e060b3bc0c578160ff05de6fc083492490725d`. This proves the checked selection
contract, not hosted runtime or sufficient timeout headroom. The **25-line**
task3 A1 adapter and its passing regression are byte-for-byte unchanged.

Work continued on the same clean owned PR685 branch at
`557ac9d981e089876a0a72b454e6d897c9ee24b6`, based on unchanged supplied main
`278cc1e135be3b8076ae9a8d4636e669deba7e29`. Leader FINAL-APPROVE review
`5324648143` was conditional on CI and covers only that old head. The new
workflow/test delta requires fresh leader review and CI. Baseline PR684's
review `5324446218` at `af978382f3013e5d32d79b17c8e0a61cc1552f81` and its
**9** successful checks remain separate predecessor evidence. The preserved
checkout, old worktrees, historical claims and accepted task-local task2 note
are untouched. No scores were re-analyzed or live operations performed.

### Supplied cancellation evidence, not a passing suite

The leader reports **8** successful checks and `pytest` **CANCELLED** for
Backend Tests run `36219000389`, job `108340566621`. The job started
**04:50:10 UTC** and ended **05:35:25 UTC**. The annotation states:
"The job has exceeded the maximum execution time of 45m0s". Its Run tests step
started **04:52:15 UTC** and was canceled **05:35:22 UTC**, reaching **99%** at
`tests/test_verify_cost_ledger.py`. Repo-root script tests were **SKIPPED**.
There is no final passing summary. **14279 collected / 14233 selected /
46 deselected / 2 skipped** are literal log counters, not a completed-pass
count. The new task3 family printed **23 dots** at **05:16:24 UTC**; this is
separate from its earlier **23 passed in 172.29s** focused result below.

An approximate attribution of timestamped progress-line completion intervals
places **1179.73 seconds** in `tests/test_codex_budget_pilot*.py`. Those spans
are not pytest duration measurements or a profiler. The existing
`pilot-contracts` job succeeded from **04:50:09 UTC** to **04:58:20 UTC**,
**8m11s including setup**. These supplied observations motivate redistribution;
they do not establish the new jobs' runtime or headroom. No logs or CI state
were queried, and the canceled run was not rerun.

### Exact partition and focused validation

Core adds only `--ignore-glob='tests/test_codex_budget_pilot*.py'`. The existing
pilot job gains this separate step after its unchanged Run pilot contracts:

```sh
cd batch-runner
python -m pytest -m "not integration" --tb=short -q -rs tests/test_codex_budget_pilot*.py
```

The target glob expands in the shell; the core ignore glob remains literal for
pytest. The new step has no `-k`, extra exclusion, skip or failure masking.
All old pilot/preflight selections and their `-k` expressions stay unchanged.
All eight check names, runners, setup, permissions, environment, source/dispatch
pinning, integration exclusions and the repo-root script step remain unchanged.
Core and pilot retain **45-minute** ceilings, native-host retains **60 minutes**,
and every other ceiling is unchanged. No runtime, inference, grading, model,
budget, registration or source-pin code changed.

The required bounded extreme-reasoner decision was **APPROVE-WITH-CONDITIONS**
before workflow edits. A bounded follow-up approved updating only the coupled
GHCP test's workflow-byte hash to
`19cd9099ad1e60865111d789207bd09fc8302095be7012eea75703c9490da09d`.
Its historical/Foundry hashes and all other pins are unchanged; the partition
selector checks that literal without running the GHCP family.

Only
`tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts`
was invoked, once, at the immutable tested SHA above. It checks the nonempty
**27-file** move, exact core-ignore/destination equality, recursive glob edge
cases, unique collected parameterized node IDs and disjoint/exhaustive ownership.
The existing preflight collection checks remain; one added child collection
covers only the moved files with the same marker and collection safeguards.
Those children execute no test bodies. No full suite, moved family, task3
regression or old passing family was executed. The invocation used the existing
Python **3.10.12** / pytest **9.1.1** environment with credential-free `env -i`,
offline HF flags, disabled plugin autoload and no pytest cache. Only the two
completion records changed after this passing test SHA.

### Preserved task3 handoff and unchanged controls

The preceding task3 preparation added **25 lines** to the existing retention
helper. It applies only to selected cell
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r1`, ordinal **12** in
`budget_pilot_ci_20260925_04`, and its immediate predecessor
`0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r2`, on inference ref
`pilot-inference-20260925-04`. The predecessor must satisfy its fixed producer
`e7a28db07ebe10d6508b9256137763cc82f9a1d1`, run `36202190875`, job `cell`,
attempt **1**, and completion payload digest
`d6d1309c2c81ef17ce18158bc9014ce962ce7dcd267f95f328b279050d4fd15e`.

The existing compiler reconstructs only A2's historical contract. Existing
terminal/control/object validators check its claim, manifest, completion,
byte identities and history at the captured branch head, using the new job's
freshly verified shared-input hashes. Only bounded control JSON is downloaded;
result, deliverable and ledger objects receive immutable metadata checks.
The adapter then checks the fixed run and completion digest. It does not
borrow input hashes from the old claim,
search for another terminal, refresh the CAS parent or adopt old state. Task3's
execution, host, source, claim and clock retain their own current bindings.
The previous B1 exception and other predecessor paths are unchanged.

The earlier bounded pre-edit extreme-reasoner decision was
**APPROVE-WITH-CONDITIONS** for this exact source boundary. That adapter patch changed no workflow,
registration, source-pin, schema, model, runtime, input, budget, grading,
ledger-note, diagnostic or privacy code.
The original five-task/**30-cell** IDs and order remain. The real compiler
produces task3 A1 config SHA256
`35a23a8842d378a8326ec8483553145ee5c63c9c63a383be3eb903bda77136a3` and order
SHA256 `f16a2a408160efe106e3e009144d4acc451d1f9051c8c23195d10cb24ce75030`.

Controls remain GPT-5.4 / Foundry `direct-v1` / `xhigh`, SDK **0.147.0**, original
`hf_originals` bundle/input pins, **180 minutes** cumulative including wait and
recovery, **30-minute** attempts, A maximum **4** fresh attempts, B/C with the
same budget and native-capability gates, one inference slot and no automatic
monetary cutoff. The fixed grader and all six retained task2 results are
unchanged. No new epoch, workflow input, arbitrary source override or scheduler
was added.

### Separate task3 focused evidence, not rerun

The earlier task3 invocations provide control-path evidence, not a new task
result or a quality measurement. They selected only
`tests/test_codex_budget_pilot_task3_a1.py::test_fixed_task3_a1_historical_predecessor`.
The separate observations are:

| Tested SHA | Result | Scope |
|---|---|---|
| `8529844bca48f4aea8fb87b0eecb972c76d4c596` | **23 failed in 275.33s**, exit **1** | The fixture prepared a synthetic host twice; the existing no-clobber gate refused before the new handoff. An interrupt did not stop this invocation. |
| `60328cef7928a33c0f0d0a3083ac73e88b40f90a` | **1 failed in 57.94s**, exit **1** | After the fixture correction, task3 admission succeeded; the positive case had a clock expectation off by one second. Stop-on-first-failure left the other **22** cases unexecuted in this invocation. |
| `7ed2f4c38e8c80f29e869c3cb96656ecb0e69a83` | **23 passed in 172.29s**, exit **0** | Corrected fixture and clock assertion; no previously passing case was repeated. |

Both correction commits changed only the new test fixture/assertion, not
production. At that handoff only the two completion records changed after the
passing test SHA. The existing Python **3.10.12** / pytest **9.1.1** environment
ran with credential-free `env -i`, offline HF flags, disabled plugin autoload
and no pytest cache. No pre-existing selector, full suite or CI run was repeated
in that preparation.

The existing fake children and HF server generate one synthetic six-cell task2
history through genuine compilation, admission, serialization, deadlines and
retention. The tests preserve that local state, clone the fake server per case
and substitute only the expected synthetic completion digest after asserting
the production pins. They do not reconstruct historical bytes. The selector
checks the old same-source refusal, the new handoff, source/run/content/config/
input/byte/history mismatches, wrong cell/ref/private target, cleanup and
publication refusals, CAS races and lost claim/output/terminal responses.
Refusals cannot start the current child; reservations cannot be replayed.
Old local and remote state stays unchanged, and the other cells remain unrun.
All model, HF, authentication, grader and process boundaries are fake or blocked.

### Supplied live evidence and proof limits

The leader reports A2 inference run `36202190875` completed on
**2026-09-25 at 23:49:54 UTC**, with `terminal_verified` at
**23:49:59.8771882 UTC** and artifact `10892208424`. The producer, run and
completion digest above remain fixed. At the original handoff its private
terminal SHA had not been independently supplied and was not looked up or
invented here. The later publication-derived identity in the accepted task-local
note does not retrofit the adapter or change these proof limits.

The completion digest authenticates fixed content. It does not independently
establish that the original outer metadata was never rewritten. A stale
terminal carried into an advanced branch head refuses, as do mismatched
source/run/content proofs. Without an independently pinned original terminal
SHA, this cannot categorically exclude a newly written, self-consistent outer
envelope retaining the fixed completion. The handoff validates the recorded
publication-receipt hash's format, not the original receipt or an independent
provider acknowledgment.

All four task2 C1/C2/B2/A2 grading operations finished on historical writer
`a5e5d2589caff21309f0a1c21bb7d9d333ad47c6`, according to the leader. Last A2
run `36214413190`, job `108327473087`, acknowledged publication at
**2026-09-26T03:29:05.7159336Z** after one Step8 invocation and owned cleanup.
At the task3 preparation handoff, the stored C1/C2/B2/A2 scores were unread here;
publication acknowledgment alone is not a quality result. C1 readout
`36217589922` was not polled or accessed by this worker. The leader has since
confirmed all six readouts complete and accepted the separate task-local note.
That note is unchanged and no scores were re-analyzed for this CI task. Earlier
readouts, partial costs, missing accounting and frozen failed histories remain
separate below; no values were pooled or repriced.

### Closed future request and remaining authority

The route below is a future request specification, not a dispatch or live
authorization. Its one unresolved value is the leader's exact reviewed main
source. The placeholder deliberately fails the existing SHA gate; neither
the historical producer nor this feature/test SHA substitutes for that future
authority. No predecessor revision input is needed or added.

```json
{
  "workflow": ".github/workflows/codex-budget-pilot-ci-cell.yml",
  "ref": "main",
  "inputs": {
    "reviewed_source_sha": "LEADER_BOUND_REVIEWED_MAIN_SHA",
    "cell_id": "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r1",
    "execute": true,
    "input_check": false,
    "output_target_check": false,
    "output_target_setup": false,
    "input_transport": "hf_originals",
    "input_release_id": "",
    "input_asset_id": "",
    "input_bundle_sha256": "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3"
  }
}
```

After new-head review and CI, the leader should bind one
new common inference source for the remaining **18** original cells, ordinals
**12–29**, to avoid per-cell source changes. This is a control intention, not
permission to run **18** cells or a prediction of a future merge SHA. The
preserved adapter prepares only task3 A1; the other **17** cells are untouched.
A later attempt
still requires exact source/host validation, verified originals, predecessor
proof, absence checks and one-use fixed-parent CAS admission. No old claim,
clock or result is adopted or settled.

Fresh leader review of the new head, final CI and the leader's explicit
source/attempt decision remain. The old conditional review is not approval of
this partition, and normal new-head CI is not permission to poll or manually
rerun it. No live HF/readout/inference/judge call, workflow dispatch, Azure
management, Project edit, main change, merge, source reseal or CI polling
occurred. The full skill catalog was reviewed once for this CI task;
experiment-report-en followed by im-not-ai-en kept the cancellation, coverage
test and older task3 results separate. No new experiment design, UI skill or
experiment axis was introduced. The sections below are historical snapshots,
not current instructions or new authority.

## Prior PROJECT5-BIND-A2-READOUT

Bound the final task2 A2 readout row to the issued grading run `36214413190`
on the existing PR684 branch. The new A2-only selection returned **5 passed,
39 deselected in 60.23s**, exit **0**, at
`b0b73343903f3e40d08a9e150c2a3668d7d65b46`. All four fixed run IDs are now
configured, but no A2 grade outcome, score or revision has been observed here.
This update does not authorize any live readout or grading.

The sole production change is `TASK2_GRADE_RUNS` for
`0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r2`. It addresses the leader's
REQUEST-CHANGES review `5324354239` at
`ac4332a2566099e042f70e6815deb1876974b41b`. The leader accepted the preceding
B2-only result; final source review and CI for this new binding remain.
Production traversal, workflow, grading admission and all
model/runtime/input/budget/rubric code are unchanged.

### Focused offline evidence

One invocation from `batch-runner/` selected only
`tests/test_codex_budget_pilot_task2_final_readout.py::test_task2_final_grade_readout`
with `-k A_r2`. The **5 passed, 39 deselected in 60.23s** result at
`b0b73343903f3e40d08a9e150c2a3668d7d65b46` used the existing Python
**3.10.12** / pytest **9.1.1** environment, credential-free `env -i`, offline HF
flags and disabled plugin autoload. Only the two completion records changed
after the tested commit.

The existing genuine writers construct synthetic C1, C2 and B2 predecessor
grades before A2, with fake external boundaries. The five cases cover positive
readout, a wrong selected run, a wrong B2 predecessor run, a predecessor-hash
mismatch and an attempt to skip B2. Source, byte, privacy, receipt, no-write and
no-judge assertions remain. The reader still verifies exactly one immediate
predecessor; the longer fixture sequence does not change production traversal.

The original **38 passed in 256.25s** at
`6d5be52861598bff3fe20c6b1cebc06b252dc334` and B2-only **5 passed,
36 deselected in 45.01s** at `1d49ba5a46d90ae4355daf8a7c875adc657e49fa` remain
separate evidence. Neither earlier selection was rerun. No prior suite or CI
was rerun.

### Supplied live evidence, not queried here

A2's first grading run is `36214413190`, attempt **1**, event
`workflow_dispatch`, created **2026-09-26T03:18:45Z**, protected approval
`6674065603`. Its historical source/writer is
`a5e5d2589caff21309f0a1c21bb7d9d333ad47c6` (A5), distinct from the future
readout observer. Only the issued ID is established; no outcome, score or grade
revision was supplied. Its original inference producer
`e7a28db07ebe10d6508b9256137763cc82f9a1d1`, run `36202190875` and completion
request checksum `d6d1309c2c81ef17ce18158bc9014ce962ce7dcd267f95f328b279050d4fd15e`
are unchanged. The checksum is not a resolved revision.

Separately, the leader supplied B2 run `36212846089`, job `108322891244`:
preparation passed at **02:51:14.6271929 UTC**, its claim was acknowledged at
**02:51:24.1345273 UTC**, one Step8 invocation completed with cleanup at
**02:57:48.5474544 UTC**, and publication was acknowledged at
**02:57:52.6218084 UTC**. Its stored score and outcome remain unread. This
confirms completion of the prior operation, not permission to read or regrade
it. Original A1/B1/C1/C2 observations and earlier accounting remain intact below.

### Remaining authority and proof limits

Hold main and the active grading controller at A5 until the leader confirms
A2 completion. Final source review, CI and explicit leader approval remain;
no pending result has been inferred. The historical source/claim/file bindings
and privacy guards are unchanged. Permitted reads still comprise inference
controls, selected/immediate-predecessor grade controls and selected verified
grade payloads; predecessor payloads receive metadata checks only. Receipt
verification remains a hash binding. Fixed-content proof does not establish
that outer metadata was never rewritten, direct Git-parent topology or
independent provider authentication.

No live HF/readout, model/judge/inference, workflow dispatch, Azure management,
Project edit, old claim/grade mutation, source reseal, merge or CI polling
occurred. The existing catalog/design/reviewer context was reused.
Experiment-report-en then im-not-ai-en preserved separate test evidence and
the distinction between issued IDs, publication acknowledgments and unread
outcomes. No new experiment-design, architecture or UI work was needed.
Earlier sections retain their original evidence snapshots.

## Prior PROJECT5-BIND-B2-READOUT

Bound the task2 B2 readout to the leader-supplied grading run `36212846089` in
the existing PR684 worktree. The only production change is the
`TASK2_GRADE_RUNS` entry for `0112fc9b-c3b2-4084-8993-5a4abb1f54f1_B_r2`.
The five newly configured B2 cases passed in **45.01s**, with **36 deselected**,
exit **0**, at `1d49ba5a46d90ae4355daf8a7c875adc657e49fa`. A2's run binding
remains null, and its readout refuses. This offline result does not establish
a live B2 grade outcome.

This follows the leader's REQUEST-CHANGES review `5324274069` at
`54c963915a900a41444287c0a4f2fa45b397c7a9`. The existing catalog, design and
bounded reviewer context were reused; no new architecture or pre-edit design
review was needed for the supplied-ID binding. Workflow, model, runtime, input,
budget, rubric and grading-admission code did not change.

### Supplied run evidence

B2's first grading run is `36212846089`, attempt **1**, event
`workflow_dispatch`, created **2026-09-26T02:48:36Z**, with protected approval
`6673811087`. Its historical source/writer is
`a5e5d2589caff21309f0a1c21bb7d9d333ad47c6` (A5), independently of the future
readout observer. This confirms the issued run ID only, not grade success,
revision, score or cost. Its original inference run `36200320037`, producer
`e7a28db07ebe10d6508b9256137763cc82f9a1d1` and completion request checksum
`b85346c5ee226bf1bfe2a34386394d4abea4617c408bedf2c3afe7016f9f904c` are unchanged.
The checksum is not a resolved revision, and no historical payload was recovered.

Separately, the leader supplied C2 run `36211281528`, job `108318247919`:
preparation passed at **02:21:39.9200661 UTC**, its claim was acknowledged at
**02:21:48.7272430 UTC**, one Step8 invocation completed with cleanup at
**02:28:34.7147869 UTC**, and publication was acknowledged at
**02:28:38.4848492 UTC**. The public projection has no score. Its stored outcome,
score, revision and costs remain unread here. The original C1/B1 observations
and all earlier accounting remain intact in the historical sections below.

### Focused offline validation

One invocation from `batch-runner/` selected only
`tests/test_codex_budget_pilot_task2_final_readout.py::test_task2_final_grade_readout`
with `-k B_r2`: **5 passed, 36 deselected in 45.01s**, exit **0**, at
`1d49ba5a46d90ae4355daf8a7c875adc657e49fa`. It used the existing Python
**3.10.12** / pytest **9.1.1** environment, credential-free `env -i`, offline HF
flags and disabled plugin autoload. Only the two completion records changed
after this tested commit.

The synthetic fixture uses the existing writers to publish C1 and C2 predecessor
grades before B2. The five cases cover successful
readout, a wrong selected run, a wrong C2 predecessor run, a predecessor-hash
mismatch and an attempt to skip C2. Existing byte, source, privacy, receipt,
no-write and no-judge assertions remain. The readout still verifies exactly one
immediate predecessor; constructing the fixture chain does not add recursion
to production. The prior **38 passed in 256.25s** at
`6d5be52861598bff3fe20c6b1cebc06b252dc334` remains separate original evidence.
No earlier passing case, prior selector, full suite or CI was rerun.

Only inference controls, selected/immediate-predecessor grade controls and the
selected grade's verified payloads may be read; predecessor payloads receive
metadata checks only. Publication-receipt verification remains a hash binding.
Fixed-content proof still does not establish that outer metadata was never
rewritten, direct Git-parent topology or independent provider authentication.
A1/B1 readout behavior and historical claims, grades and bytes are unchanged.

### Remaining authority

A2 has not been dispatched and its actual run ID is unknown. Its registry entry
remains null and refuses before source preflight, local root creation or
credentials. The leader must supply that ID before a later change; only the
changed A2 rows should then be validated in this same PR. No ID was queried,
guessed or awaited. Main and the active grading controller must stay at A5.

New-head review and CI remain. Final merge is held until all four live grade
requests are bound/finished and the leader approves. No live HF/readout,
model/judge/inference, workflow dispatch, Azure management, Project edit,
claim/grade mutation, source reseal, merge or CI polling occurred.
Experiment-report-en followed by im-not-ai-en kept issued IDs, publication
acknowledgments and unread outcomes distinct. No new experiment-design or UI
work was needed. Earlier sections retain their original evidence snapshots.

## Prior PROJECT5-TASK2-FINAL-READOUT

Prepared model-free readout routes bound to the task2 C1/C2 grade requests and
explicitly unconfigured B2/A2 routes. One focused offline selector passed
**38 cases in 256.25s**, exit **0**, at
`6d5be52861598bff3fe20c6b1cebc06b252dc334`. No live grade was read or produced.
C1's stored outcome remains unread here; C2 has no known result in the supplied
evidence. B2/A2 refuse until the leader supplies their actual grade run IDs.

Work used a new clean owned worktree from common main
`a5e5d2589caff21309f0a1c21bb7d9d333ad47c6` (A5), leaving main and the active
grading controller unchanged. The leader supplied PR683 review `5323958749`
at `0e744ab4e38d518ee6f9494f4bed43478b82a21f` and **9** passing checks. Those
gates cover the preceding handoff, not this patch.

### Closed readout scope

The existing `pilot/grade-readout` route now recognizes four additional fixed
task2 selections. It reuses `TASK2_RETAINED` completion checksums and producer
`e7a28db07ebe10d6508b9256137763cc82f9a1d1`, inference ref
`pilot-inference-20260925-04` and grading ref `pilot-grades-20260925-04`.
The full cell prefix is `0112fc9b-c3b2-4084-8993-5a4abb1f54f1_`:

| Cell suffix | Inference run | Completion request checksum | Expected grade run at A5 |
|---|---|---|---|
| `C_r1` | `36195731407` | `f3d1d3420b4dc23c018aa8b55ac1f4653a64e92b85eac50268e80aea55f2fbef` | `36209654516` |
| `C_r2` | `36198090626` | `1823893b4b4dfbce02b5b07d48f164cdd6228c3c38afd9608bb934c3e9bf417c` | `36211281528` |
| `B_r2` | `36200320037` | `b85346c5ee226bf1bfe2a34386394d4abea4617c408bedf2c3afe7016f9f904c` | Unconfigured: no supplied ID |
| `A_r2` | `36202190875` | `d6d1309c2c81ef17ce18158bc9014ce962ce7dcd267f95f328b279050d4fd15e` | Unconfigured: no supplied ID |

Configured grade runs require job `pilot-live`, attempt **1** and historical
writer A5. The future observer keeps its own truthful, distinct source. The
expected config SHA256
`62a6d99d9e74d187e517d60d9a5afb112e38926917710ac6e6606eb28404dfa0` and grader
source hash `0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df`
come from the genuine local A5 compiler/closure, not a remote claim. The closure
is unchanged from ecbe; the focused selector exercised the actual entry hash
calculation using that closure and compiled config.

Each configured read verifies the exact inference run, completion checksum,
source, original claim, terminal, manifest, full retained observation and
publication-receipt hash binding. A completion checksum remains a request
identity, not a resolved revision. The reader resolves the selected grade from
one branch snapshot, then verifies immutable grade terminal, claim and file
identities.

It also verifies exactly **one** immediate logical grade predecessor: that
grade's fixed writer/run/config, original claim, file metadata and retained
inference proof; the selected claim's exact predecessor identity; the unchanged
predecessor terminal in the selected claim snapshot; and equality between the
selected inference predecessor and the prior grade's retained observation.
C1 additionally requires the supplied B1 grade
`887c2373d456efc1eabf29a8bf3d3d7de12e43fe` and B1 inference terminal
`0a9a8b3263f41d86d723f84a723c9b467f04dea5`. These additional pins do not change
the delivered A1/B1 readers or grading admission helpers.

Only inference controls, selected and immediate-predecessor grade controls, and
the selected grade's verified payload files can be downloaded. Predecessor
grade payloads receive metadata checks only. There is no recursive history walk,
inference-payload download, OIDC, model/judge entry, claim or HF write. Existing
score denominators, excluded-item accounting,
graded/partial/failed/ungraded states and missing-cost handling are unchanged.
Fixed-content proof does not establish that outer metadata was never rewritten,
the direct Git parent edge, or independent provider authentication.

B2/A2 return the closed `grade_readout_writer_unconfigured` refusal with their
own cell/source and `grade_writer_run=null`, before source preflight, local root
creation, credentials or session entry. No placeholder run ID or input override
is accepted. The workflow delta is two descriptions only; inputs, permissions,
approval, grading admission, model/rubric/runtime/input/budget code and source
pins are unchanged. The bounded pre-edit reviewer approved this scope with
conditions; that decision is not exact-head source approval or live authority.

### Focused offline evidence

One invocation selected only
`tests/test_codex_budget_pilot_task2_final_readout.py::test_task2_final_grade_readout`
from `batch-runner/`, using Python **3.10.12**, a credential-free `env -i`,
offline HF flags and disabled pytest plugin autoload. It returned **38 passed
in 256.25s**, exit **0**, at `6d5be52861598bff3fe20c6b1cebc06b252dc334`.

Existing genuine compiler, materializer, Step8 writer, ledger exporter and
publication validators used fake external boundaries. Cases covered both known
read routes, all four stored outcomes, missing ledger/partial accounting,
advanced refs, run/source/hash/byte/receipt/privacy/cleanup refusals, predecessor
pins/link/history checks, forbidden downloads and both unconfigured rows in
plan and readout modes. No correction or rerun was needed. Only completion
records changed after that tested commit. These are offline contract results,
not live HF behavior, native execution, new grades or judge calibration.

Earlier observations remain separate below, including **29 failed in 134.97s**
at `c4ec9e321f31571b32be53b28355998f961471fb` and **29 passed in 132.48s** at
`dfc1fc93f46e2bd6e84cfed824ca75069b7fcd35`. No prior selector or suite was rerun.

### Supplied live evidence, not queried here

The leader reports B1 readout run `36209591238` verified original grade
`887c2373d456efc1eabf29a8bf3d3d7de12e43fe`, writer
`ecbe297e7dc2d798a834091f14da3ae486172a43` / run `36202409134`, and the e7
inference terminal `0a9a8b3263f41d86d723f84a723c9b467f04dea5`. B1 scored
**62.95 / 65 = 96.85%**, or **95.38%** with the full denominator. There was **one**
excluded item of maximum **1**. Its ledger reports **109 model calls**, not
HTTP requests, and **339415 input**, **15884 output**, **230032 cached-input**
and **9529 reasoning tokens**. Prices are missing (`price_missing`); all monetary
totals are null and invoice completeness is false. No regrade occurred. This is
one task/condition observation, not evidence of A/B/C superiority. The prior A1
grade, score and detailed limits remain unchanged below.

The leader reports C1 first grade `36209654516`, job `108313415675`, at A5:
preparation passed at **01:51:10.4479416 UTC**, the claim was acknowledged at
**01:51:20.4305652 UTC**, one Step8 invocation completed with cleanup at
**01:58:02.4464257 UTC**, and publication was acknowledged at
**01:58:06.8206654 UTC**. The public output does not expose its stored outcome,
score, revision or costs; those remain unread here.

C2 run `36211281528`, attempt **1**, was leader-dispatched at the same A5 and
protected approval was accepted. No result was supplied. B2/A2 had not been
dispatched in the supplied snapshot; neither actual grade run ID is known here.
No active run was polled or affected. All six task2 inference results remain
retained, and the older admissions, claims and partial accounting remain
separate and frozen. No task3 or new inference is authorized.

### Remaining configuration and authority

The leader must keep A5 unchanged while C1/C2/B2/A2 grading finishes. The exact
remaining code configuration is the actual B2 grade run ID for `B_r2` and actual
A2 grade run ID for `A_r2`; neither row may derive authority from remote claims.
After those IDs are supplied, only the changed rows should be validated in this
same PR, without repeating passing cases. Each future read uses the existing
`pilot/grade-readout` selector and its table checksum as `inference_revision`,
with `paid_approval=false` and the unchanged fixed controls. These specifications
are not dispatches or permission to query live state.

New-head review and final CI remain. Final merge is held until the four live
grade requests are bound/finished and the leader approves. No live HF read/write,
inference/grading/readout, workflow dispatch, Azure management, source reseal,
old-claim change, Project edit, merge or CI polling occurred. The full catalog
was read once. Experiment-design bounded the observer/writer evidence split;
experiment-report-en then im-not-ai-en preserved units, denominators, uncertainty
and authority. UI/animation and repo-readiness did not apply. Earlier sections
retain the evidence available when those tasks closed, not current live authority.

## Prior PROJECT5-TASK2-GRADE-COMPLETION

Prepared a read-only route for the already-published task2 B1 grade and closed
grading routes for individual future C1, C2, B2 and A2 requests. The focused
offline selector passed **29 cases in 132.48s** at
`dfc1fc93f46e2bd6e84cfed824ca75069b7fcd35`, after a fixture-only correction
described below. No live readout, grading, inference or workflow dispatch
occurred. B1's stored outcome, score, costs and resolved revisions remain unread.

Work used a new clean owned worktree from main
`ecbe297e7dc2d798a834091f14da3ae486172a43`; the preserved checkout was untouched.
The leader supplied delivered PR682 review `5323495504` at
`0d934c19347d04de81c9be9c3445e293c06ddd3d` and **9** passing checks. That review
covers the preceding B1 intake implementation, not this patch.

### B1 readout and the finite grading chain

The existing `pilot/grade-readout` selector now also accepts B1's fixed public
completion checksum. A1 readout is unchanged. B1 is bound to historical grading
writer `ecbe297e7dc2d798a834091f14da3ae486172a43`, run `36202409134` /
`pilot-live` / attempt **1**, and inference producer
`e7a28db07ebe10d6508b9256137763cc82f9a1d1`. Its expected grader/config hashes
come from the unchanged local ecbe grader closure and genuine compiled config,
not from the remote record. The observer retains its own truthful reviewed
source; it does not impersonate either historical source.

The grade's reported inference revision is only a candidate. Existing immutable
readers verify its original claim, manifest and completion against B1's fixed
run/source/checksum, then compare the whole retained observation and publication
receipt binding. The grade claim, terminal, file hashes and payload identities
are also validated. The read-only wrapper downloads only the selected inference
control records and verified grade files, never inference payloads. It has no
OIDC, Azure, model/judge, claim, branch or HF-write interface. Existing score
denominators, partial/failed/ungraded outcomes, missing-ledger state, recorded
costs, nulls and privacy exclusions remain unchanged.

One closed registration table extends the existing fixed-content intake from
B1 to the four remaining task2 results. All use producer e7 above, campaign
`budget_pilot_ci_20260925_04`, inference ref `pilot-inference-20260925-04`
and grading ref `pilot-grades-20260925-04`. The full cell prefix is
`0112fc9b-c3b2-4084-8993-5a4abb1f54f1_`:

| Cell suffix | Recorded inference run | Required completion checksum | Immediate grade predecessor |
|---|---|---|---|
| `C_r1` | `36195731407` | `f3d1d3420b4dc23c018aa8b55ac1f4653a64e92b85eac50268e80aea55f2fbef` | B1 |
| `C_r2` | `36198090626` | `1823893b4b4dfbce02b5b07d48f164cdd6228c3c38afd9608bb934c3e9bf417c` | C1 |
| `B_r2` | `36200320037` | `b85346c5ee226bf1bfe2a34386394d4abea4617c408bedf2c3afe7016f9f904c` | C2 |
| `A_r2` | `36202190875` | `d6d1309c2c81ef17ce18158bc9014ce962ce7dcd267f95f328b279050d4fd15e` | B2 |

Preparation resolves each cell's exact terminal-writing commit from immutable
history, even after the inference ref advances. The approval request retains
the original completion checksum, distinct from the resolved revision. A
no-clobber local resolution record binds both through later phases; those
phases do not resolve a new candidate or adopt the latest HEAD.

C1 requires the actual B1 grade under its pinned ecbe writer/run and grader
expectations. C2, B2 and A2 require their immediately preceding grade under the
same exact controller source declared for their own request, with locally
computed grader/config expectations. That common future controller must be
bound before dispatch. Bootstrap, skipped or unfinished predecessors, changed
controllers and a predecessor from another inference observation refuse.
B1's existing predecessor remains A1 grade
`a0ded8b7146c028516d007a9afaa0993797fa1ca`, writer
`6ed0139195c4ebf27bfb63d14b2c8d8c92f8f379` / run `36161541597`, producer
`b4c95f8eaee16ae2226f3bf6e0493051fa91d770`, inference terminal
`8083504edf4ceb63f3c4929aac57e0f4b6741593`. No historical claim, grade or receipt
is rewritten or adopted as new authority.

The required bounded extreme-reasoner decision was APPROVE-WITH-CONDITIONS
before production/workflow edits. Fixed-content verification establishes a
matching immutable publication; it does not prove that original outer metadata
was never rewritten. That accepted limit is unchanged. The decision grants no
live authority and is not exact-head source approval.

### Focused offline evidence

Both invocations used only
`tests/test_codex_budget_pilot_task2_grade_completion.py::test_task2_grade_completion`
from `batch-runner/`, with Python **3.10.12**, credential-free `env -i`, offline
HF flags and pytest plugin autoload disabled:

| Immutable tested SHA | Separate result | Interpretation |
|---|---|---|
| `c4ec9e321f31571b32be53b28355998f961471fb` | **29 failed in 134.97s**, exit **1** | New synthetic inference commit labels collided with the fixture's A1 grading claim. Every case refused at that missing claim before its intended assertion. |
| `dfc1fc93f46e2bd6e84cfed824ca75069b7fcd35` | **29 passed in 132.48s**, exit **0** | Only the shared fixture labels changed, with an explicit collision assertion. `--lf --lfnf=none` selected the 29 failed cases; no passing case was repeated. |

Genuine compiler, inference/Step8 serialization, cost-ledger export, native
materializer contract and claim/terminal/file validators run with fake external
boundaries. The selector covers B1 graded/partial/failed/ungraded and missing
ledger readouts, advanced refs, writer/run/completion/receipt/hash/byte/privacy/
cleanup refusals, the four separate grading operations, immediate predecessor
and controller checks, altered saved resolution, missing approval, and lost
claim/publication acknowledgments. It independently executes the workflow's
approval digest. No unapproved judge or write occurs at the fake boundaries.
These results do not establish live HF behavior, native installation or quality.
Only completion records changed after the successful tested commit.

The prior B1 selector remains **23 passed in 74.52s** at
`3545f585fd200fd08ae670227dce522b423e6f19`, not rerun or combined with these
results. All earlier split observations remain in the historical sections below.
No old selector or full suite was rerun.

### Supplied live observations, not reread here

The leader reports B1 grade run `36202409134`, job `108291769004`, succeeded
under ecbe. Preparation passed at **2026-09-25T23:51:20.6609991Z**, the claim was
acknowledged at **23:51:32.0451876Z**, one Step8 invocation completed with owned
cleanup at **23:57:43.4635191Z**, and publication was acknowledged at
**23:57:48.6085301Z**. Its inference run remains `36192851762` with completion
checksum `6a23d38158e81cd5ed184a05a7871545d140bb1d92dc1131326d96df29c236f8`.
Workflow success and publication acknowledgment do not establish a graded
outcome, score or complete costs. The actual B1 inference and grade revisions
remain unknown here; no hashes or payloads were reconstructed.

The leader also reports A2 inference run `36202190875`, job `108291038435`,
succeeded on event-pinned e7 before main changed. Execution ran
**23:47:54–23:49:54 UTC** on **2026-09-25**; the terminal was verified at
**23:49:59.8771882 UTC**. Artifact `10892208424` has the verified A2 completion
checksum in the table above, one child, confirmed cleanup and one **5386-byte**
deliverable. Partial accounting reports **USD 0.245066** known cost,
**123697 input**, **8336 output**, **84096 cached-input** and **5929 reasoning
tokens**. Estimate and HTTP request count are null; invoice completeness is
false. These are partial recorded quantities, not invoice totals or quality.

All **six** epoch04 task2 inferences A1/B1/C1/C2/B2/A2 are now retained according
to the leader. Only A1 quality has been read: **62.4 / 65 = 96.0%**, with
full-denominator **94.55%**, under the detailed exclusions and accounting limits
preserved below. It remains one-task/condition evidence, not cohort or A/B/C
superiority. The nine older admissions, partial costs, unknown causes, missing
raw files and claims remain separate and frozen. No task3 or new inference is
authorized by this task.

### Individual future requests and remaining authority

Use only existing `.github/workflows/grade-run.yml` inputs on truthful reviewed
`main`. For a B1 readout, select `experiment_yaml=pilot/grade-readout`,
`inference_revision=6a23d38158e81cd5ed184a05a7871545d140bb1d92dc1131326d96df29c236f8`,
`dry_run=false`, `paid_approval=false`. For each separate future grade, use
`experiment_yaml=pilot/<full cell ID>` and its table checksum as
`inference_revision`, with `dry_run=false`, `paid_approval=true`. Common controls
remain `grading_config=default_v2_sol_max.yaml`, `force=false`, `tasks_limit=0`,
empty/absent optional `tasks`, `resume=false`, `resume_chunk=0`, `shard_count=1`,
`shard_index=0`, `run_ordinal=1`, and workflow attempt **1**. These are request
specifications, not dispatches. Default planning remains offline and token-free.

Each grade still needs its own successful same-run protected approval,
exact-source checks, original retained-byte validation and one-use CAS claim.
There is no scheduler, automatic successor, task3 extension, new input or
free-form source override. Fixed `default_v2_sol_max` judging, inference/model/
runtime/original-input/budget code, the canonical **30**-cell plan and all old
privacy/retention repairs are unchanged. Lost acknowledgment remains fail-closed.

New-head review, final CI and the leader's exact source binding and individual
readout/grading authorization remain. No live HF read/write, model/judge call,
workflow dispatch, Azure management, source reseal, old-claim change, setup,
Project edit, merge or CI polling occurred. The full catalog was read once.
Experiment-design bounded this finite source/evidence policy; experiment-report-en
then im-not-ai-en kept observations, denominators, missingness and authority
separate. UI/animation and repo-readiness do not apply: no UI or new public
handoff was requested. Earlier sections retain the evidence available when
those tasks closed; they are not current permission to repeat an operation.

## Prior PROJECT5-B1-GRADING-PREP

Prepared the closed grading path for task2 B1, original ordinal **7**, cell
`0112fc9b-c3b2-4084-8993-5a4abb1f54f1_B_r1`, in
`budget_pilot_ci_20260925_04`. The sole focused offline selector passed
**23 cases in 74.52s** at `3545f585fd200fd08ae670227dce522b423e6f19`.
No live read, grading, inference or workflow dispatch occurred in this task.
Work used a new clean owned worktree from main
`e7a28db07ebe10d6508b9256137763cc82f9a1d1`; the preserved checkout was untouched.
The leader supplied PR681 review `5322745358` at
`37efcec2dc7e109ec8a30ad8808fa9bc72494927` and **9** passing checks for the
preceding inference-predecessor adapter, not this grading change.

### Fixed producer, controller and predecessor bindings

The offline fixture reproduces the reported source boundary: the original
`_branch_tip` pairing cannot validate the historical A1 grade under B1's
producer and a new controller. Only the recorded B1 route now verifies A1
separately at grade revision `a0ded8b7146c028516d007a9afaa0993797fa1ca`, under
writer `6ed0139195c4ebf27bfb63d14b2c8d8c92f8f379` / run `36161541597`, inference
producer `b4c95f8eaee16ae2226f3bf6e0493051fa91d770` and inference terminal
`8083504edf4ceb63f3c4929aac57e0f4b6741593`. The existing grade-readout constants
supply independent historical config/source expectations. Original claim,
binding and immutable file validators still apply; no A1 payload is downloaded
for this predecessor check. An unexpected grading tip, including bootstrap,
refuses before a B1 claim. Other routes retain their existing checks.

B1 keeps its actual inference producer
`e7a28db07ebe10d6508b9256137763cc82f9a1d1`. Its future grading controller uses
truthful `GITHUB_SHA` and workflow identity; it does not pretend to be e7 or
the historical A1 writer. The workflow's existing producer mapping and
independently executed protected-approval digest include only this fixed B1
exception. No free-form producer override or new workflow input was added.
Same-run successful protected approval, main/exact-source/attempt checks,
fixed-parent CAS, absent-cell and one-use guards remain required before a
judge. Lost claim or publication acknowledgment cannot authorize a retry.

### Resolve fixed completion content without inventing a terminal SHA

The existing `inference_revision` input accepts B1's exact public completion
checksum only for this fixed cell/producer/run. It is not treated as a Git
revision. Preparation snapshots `pilot-inference-20260925-04`, looks up only
B1's terminal control path, resolves its immutable writing commit, then
verifies the original claim, terminal, manifest and payload identities.
Checks bind inference run `36192851762` / `cell` / attempt **1**, e7 source,
the fixed completion and immediate A1 predecessor. The recorded numeric job
ID is not the claim's `GITHUB_JOB` value. Advancing the inference ref does not
select another cell or adopt the latest HEAD as the terminal.

The checksum means the public envelope's `sha256 == pilot._digest(payload)`;
it is not a wrapper-file or newline-terminated-record hash. Other framing
refuses. The approval digest retains this original checksum request.
Preparation writes a separate no-clobber local resolution record. Claim,
judge and publication revalidate its request/evidence binding and restore
the same resolved revision, without resolving the branch again.

The bounded extreme-reasoner decision was APPROVE-WITH-CONDITIONS before
production/workflow edits, with an explicit fixed-content interpretation.
This verifies a matching immutable publication; it does not establish an
independently known original outer-terminal revision or prove that an
authorized writer never changed only outer metadata. The focused test keeps
that counterexample explicit. If proof of the original outer-terminal identity
is required, the leader needs an independent anchor before dispatch. Reading
the original claim as evidence is not adopting inference state or replay
authority. The decision is not exact-head approval or live authorization.

### Focused offline evidence and unchanged controls

From `batch-runner/`, the single invocation at immutable tested SHA
`3545f585fd200fd08ae670227dce522b423e6f19` returned **23 passed in 74.52s**,
exit **0**:

```text
tests/test_codex_budget_pilot_b1_grading.py::test_fixed_b1_grading_intake_and_previous_source
```

Python **3.10.12** ran with credential-free `env -i`, offline HF flags and pytest
plugin autoload disabled. Genuine compiler, serializer, receipt, claim,
terminal, byte and grading validators are reused with fake HF/model/runtime/
renderer/native-materialization boundaries. Synthetic historical records are
newly serialized, not reconstructed from live identities. Coverage includes
accepted B1 grading, advanced inference snapshots, wrong run/source/hash/bytes/
ref, snapshot mismatch, prior grade/writer/source/hash/claim refusal, changed
saved resolution, missing/skipped approval, reruns, changed approval requests,
producer overrides, lost claim/publication acknowledgment and offline planning.
The workflow digest script executes independently against runtime-shaped input
JSON. No unapproved judge or write occurs at the fake boundaries.

The fixed refs remain `pilot-inference-20260925-04` and
`pilot-grades-20260925-04`. Source pins, ledger-note/privacy/diagnostic repairs,
model/runtime/original-input controls and `default_v2_sol_max.yaml` are unchanged.
The compiler retains **30** canonical IDs/order with prefix **0–5** out of scope.
B1's config hash remains
`85852f9b8bdbfa66e5c775283ca1fe092e60af21f51eafe82b0021b83109c049`, with
GPT-5.4 / Foundry `direct-v1` / `xhigh`, SDK/CLI **0.147.0**, **180 minutes**
cumulative including waits/recovery, **30-minute** attempts, B mechanical
continuation within its own retained native thread/deadline, one inference
slot and no automatic monetary cutoff. No model, rubric, budget, epoch or
storage framework changed. No prior selector or full suite was rerun.
Only completion records changed after the tested code commit.

The preceding inference-adapter observations stay separate:
`182ce105f7bd4300979a4012d0687c21abba52cd` had **18 failed, 1 passed in
210.38s** before admission because its fixture used a checkpoint reader on raw
config JSON; `9d5a14949dda2b6f28f507a01c36055f840810fa` then had **18 passed,
1 deselected in 243.17s** after that fixture-only correction. The already-passed
`other_cell` case was not repeated. These are not a fresh combined result.

### Supplied live evidence remains separate

The leader reports B1 run `36192851762`, job `108261828916`, succeeded on e7:
execution **21:43:54–21:46:07 UTC**, `terminal_verified` at
**21:46:13.2920082 UTC**. Public artifact `10889356436` has completion checksum
`6a23d38158e81cd5ed184a05a7871545d140bb1d92dc1131326d96df29c236f8`, one child,
confirmed cleanup and exit **0**. Its one deliverable is **5436 bytes**, SHA256
`7624528ee65a7d877adf74127b3adff9b16460cd6f66d2f9cf6ff3eb3e327c18`.
Partial accounting reports **USD 0.243915** known cost, **87241 input**,
**8748 output**, **46848 cached-input** and **6693 reasoning tokens**; invoice
completeness is false and HTTP request count is null. These are not invoice
totals or B1 quality evidence. No B1 grade exists in the supplied evidence.
Its actual private terminal SHA remains unknown here; no live lookup or raw
payload recovery occurred.

A1's supplied readout remains one-task/condition evidence: run `36183957201`,
job `108232749275`, observer `66e7ad05975ddf704b9e2aab2b1efce5cd533cef`, at
**20:11:07 UTC** returned `verified_retained_grade`, `grade_state=graded` and
the immutable A1 grade revision above. A1 earned **62.4 / 65 = 96.0%**, with
one excluded item of maximum **1**, full-denominator **94.55%** and exclusion
lift **1.45 percentage points**. **49** of **54** included items passed out of
**55** judge items. Its ledger records **110 model calls**, not HTTP requests,
and **339526 input**, **17687 output**, **229914 cached-input**, **11558 reasoning
tokens**. `price_missing`, null monetary totals and invoice completeness false
remain explicit. No regrade, cohort conclusion, A/B/C superiority or B1 quality
is inferred. This task did not fetch raw data or independently calibrate the judge.

Earlier grade runs `36132571260` and `36151684790` remain distinct failures.
The nine older admissions, partial costs, missing raw files, unknown causes and
claims remain frozen and separate from epoch04. The leader separately dispatched
C1 run `36195731407` on unchanged e7 with the same **180/30-minute** limits.
This task neither checked its status nor interfered with it.

### Closed future request and remaining authority

The following request uses the existing workflow inputs. It was not dispatched;
execution requires the leader's exact reviewed main/controller source and
attempt authorization after review and CI. The feature head and e7 are not
substituted for that future workflow authority:

```json
{
  "workflow": ".github/workflows/grade-run.yml",
  "ref": "main",
  "inputs": {
    "experiment_yaml": "pilot/0112fc9b-c3b2-4084-8993-5a4abb1f54f1_B_r1",
    "inference_revision": "6a23d38158e81cd5ed184a05a7871545d140bb1d92dc1131326d96df29c236f8",
    "grading_config": "default_v2_sol_max.yaml",
    "force": false,
    "tasks_limit": 0,
    "tasks": "",
    "dry_run": false,
    "paid_approval": true,
    "resume": false,
    "resume_chunk": 0,
    "shard_count": 1,
    "shard_index": 0,
    "run_ordinal": 1
  }
}
```

Default plan remains credential-free and offline. Actual B1 terminal resolution,
source-bound preparation, protected approval, grading claim, judge and publication
remain unperformed here. New-head review, final CI and explicit leader authority
are still required. No live HF/readout/model/judge request, workflow dispatch,
setup, Azure management, source reseal, old-claim change, permission change,
Project edit, merge or CI polling occurred. The full catalog was read once.
Experiment-design constrained this unchanged experimental source/evidence boundary;
experiment-report-en then im-not-ai-en preserved measurement scopes, denominators,
partial/null costs and remaining authority. UI/animation and repo-readiness did
not apply: no UI or new public handoff was requested.

## Prior PROJECT5-READOUT-COST-0404

Addressed PR680 REQUEST-CHANGES `5321675005` at
`e8cbc74f8bde6e4f34216ed6b20a9364dfaa9c88` on the same owned branch/worktree.
Only the `partial_cost` test fixture and its directly coupled assertions changed.
It now uses an existing synthetic price table for its positive-known-cost case;
real ledger export, receipt serialization and readout retain that subtotal.
Production prices, workflow, core, rubric, sources, model/grader config and
scoring remain unchanged. The corrected node passed once; separate evidence
and its limits are recorded below. The actual retained grade remained unread
at that task's completion; the subsequent supplied readout is recorded above.

The underlying closed, model-free reader was prepared from main
`6ed0139195c4ebf27bfb63d14b2c8d8c92f8f379` for PROJECT5-GRADE-READOUT-0201.
The leader supplied PR679's exact-head review `5319870032` and all **9** checks
passed for the preceding approval-input repair. That review does not cover
this reader. A bounded extreme-reasoner decision returned
APPROVE-WITH-CONDITIONS before production/workflow edits; it permits offline
implementation, not a live readout or regrading.

### Closed route and evidence boundary

The existing grading CLI now reserves selector `pilot/grade-readout` with an
explicit `readout` phase. Its default plan needs no credentials or network.
The existing `inference_revision` input must name
`8083504edf4ceb63f3c4929aac57e0f4b6741593`; there are no new workflow inputs.
Live readout requires `dry_run=false`, `paid_approval=false`, exact main/workflow
SHA, attempt **1**, the fixed controls and a separately reviewed observer source.
`pilot-readout` uses the protected `grading` environment, `contents: read` only
and HF credentials scoped to its final read step. It has no OIDC/Azure, input
preparation, rubric fetch, claim, judge, publication or branch-setup path.
Ordinary pilot planning, both paid pilot jobs and all generic jobs exclude it.

The reader accepts only campaign `budget_pilot_ci_20260925_04`, cell
`0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r1`, inference producer
`b4c95f8eaee16ae2226f3bf6e0493051fa91d770`, the inference terminal above,
writer/controller `6ed0139195c4ebf27bfb63d14b2c8d8c92f8f379`, writer run
`36161541597` / `pilot-live` / attempt **1**, and grading ref
`pilot-grades-20260925-04`. The observer reports its own source rather than
pretending its `GITHUB_SHA` is the writer's. The numeric job ID in the leader's
trace is not independently bound by the existing claim schema.

One branch snapshot locates the selected terminal's immutable writing commit.
Existing verifiers check the original claim, exact binding, cleanup, terminal
and up to three artifacts, each bounded to **8 MiB**, before projection.
The new HF interface exposes only exact-target metadata and staged immutable
file reads. No write or generic forwarding method is exposed. The expected
grader hash `0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df`
was derived locally from the original source closure and genuinely compiled
`batch-runner/comparison-grading.json`; its config SHA256 is
`62a6d99d9e74d187e517d60d9a5afb112e38926917710ac6e6606eb28404dfa0`.
Neither expectation is adopted from the remote record.

The shared publisher outcome rules must agree with the retained terminal.
The summary contains closed `graded`/`partial`/`failed`/`ungraded` state,
source/revision and file identities, recorded task earned/possible/percentage,
score-exclusion caveats, item-coverage denominators, receipt usage/known costs
and missingness. Ledger-derived accounting uses existing recorded-row
aggregation without repricing; it is separate from recorded task/run receipts.
Missing ledger is distinct from grade state. Progress is not a completed score.
The reader does not fetch or revalidate the original rubric; the publisher's
independent rubric gate remains intact. No rubric text, provider labels, raw
judge output, paths, notes or credentials are projected. Invoice completeness
stays false and HTTP request count stays null. Fixed grader/model/runtime/input/
budget controls, source pins, historical bytes and one-use guards are unchanged.

### Fixture correction and separate validation evidence

The committed receipt price table has no `azure:gpt-5.6-sol` entry. Settling
usage against that table does not establish a positive known cost, so the old
fixture's positive-subtotal assertion was unsupported. No positive recorded
amount was lost by the projection. Only `partial_cost` now copies the existing
`PRICE_TABLE` from `test_cost_receipts_keep_every_call_that_happened` into a
temporary, explicitly synthetic table for the unchanged fixed judge identity.
No production rate was added, historical row repriced or unknown amount filled
with zero. Other scenarios keep the real table. The real CostReceiptLedger,
Step8 writer, publisher and readout validators remain in the path.

At immutable tested SHA `161c9e306e2a483059e273bae2cd59bed8d1a5d7`, the only
invocation after that correction selected **1** node and returned **1 passed
in 5.55s**, exit **0**:

```text
tests/test_codex_budget_pilot_grade_readout.py::test_closed_retained_grade_readout[partial_cost]
```

The positive known subtotal matches the recorded task receipt and ledger-derived
receipt. Assertions retain **111** input, **23** output, **17** cached-input and
**8** reasoning tokens, **2** model calls in the ledger, partial status,
`call_reachability_unknown`, a null estimate, invoice completeness false and
HTTP request count null. The unsettled call remains explicit missingness;
the synthetic subtotal is neither a live price nor an invoice. Only completion
records changed after this tested commit.

The following earlier observations remain separate. At tested SHA
`2210aededc285dc324fcbe3ca2a00d4cbb6c079d`, the initial invocation
returned **19 failed, 6 passed in 29.37s**, exit **1**:

```text
tests/test_codex_budget_pilot_grade_readout.py::test_closed_retained_grade_readout
```

Local selections ran from `batch-runner/` with existing Python **3.10.12**,
credential-free `env -i`, offline flags and disabled pytest plugin autoload. Fixtures use the
real compiler, Step8 serialization, CostReceiptLedger export and publisher
with fake source/native/renderer/runtime/HF boundaries. Every readout mutation,
preparation and judge seam is forbidden after synthetic fixture publication.
The six passing cases are `ungraded`, `missing_ledger`, `plan`, `cross_phase`,
`rerun` and `observer_spoof`. All **19** failures stopped at the fixture's
publication assertion before their readout assertions, so that invocation
did not establish passing source/hash/privacy/accounting coverage.

Read-only inspection of the saved synthetic grade found
`summary.cost.unpriced_models=[]`. The fixture's summary rebuild omitted the
fixed model list supplied by the genuine Step8 writer, violating the existing
schema contract. Fixture-only commit `71d3b4ce0d79afaa72e41a42fc3203b372efd5e1`
restores that argument without changing production.

Review `5320991348` then authorized a restricted selection at
`e8cbc74f8bde6e4f34216ed6b20a9364dfaa9c88`. That invocation started before
PROJECT5-READOUT-COST-0404 arrived. It collected **25** cases, selected **19**
and deselected **6**, returning **1 failed, 18 passed, 6 deselected in 41.65s**,
exit **1**, using:

```text
tests/test_codex_budget_pilot_grade_readout.py::test_closed_retained_grade_readout
-k 'not (ungraded or missing_ledger or plan or cross_phase or rerun or observer_spoof)'
```

Only `partial_cost` failed: `known_cost_usd` was null and the positive-cost
comparison raised `TypeError`. The restricted selection was not repeated.

Separately, the leader supplied completed CI run `36168203527`, job
`108181029135`, at the same head: **1 failed, 14035 passed, 61 skipped,
46 deselected in 2267.66s**. Eight other checks passed. The readout file had
**24 passed, 1 failed**, again only `partial_cost`; this is supplied CI evidence,
not a local full-file pass. Review `5321675005` superseded the previous request
with this one-node cost-fixture correction. The earlier **6 passed / 3 running**
CI observation was not final gate approval. After the superseding request,
no passing case was repeated. These observations are not combined into a
25-case passing result. No full suite, live diagnostic or dependency
installation occurred here. The earlier approval-input result remains separate:
**37 passed in 5.35s** at `912a5f738db29d11628a859dec8f8855e94622f1` for
`tests/test_codex_budget_pilot_approval_inputs.py::test_dispatch_inputs_bind_actual_approval_to_connector`.
Earlier split test/CI observations and frozen partial-cost histories remain in
the historical records below and the unchanged changelog entries.

### Separate supplied live observations

The leader reports run `36161541597`, attempt **1**, controller
`6ed0139195c4ebf27bfb63d14b2c8d8c92f8f379`, completed SUCCESS. Job
`108159174144` passed exact route at **16:36:29.9825226 UTC** and retained
preparation at **16:36:43.3869995 UTC**. OIDC login/session passed; grade claim
was acknowledged at **16:36:53.7538589 UTC**. One Step8 invocation ran
**16:36:54–16:44:11 UTC**. Owned cleanup was confirmed at
**16:44:11.7879489 UTC** and grade publication acknowledged at
**16:44:16.8008223 UTC**. No new inference occurred. These receipts do not
establish the actual retained grade outcome, score, usage or cost; publication
can acknowledge partial, failed or ungraded output. Those values remained
unobserved at that task's completion, before the readout recorded above.

Earlier run `36132571260`, job `108062994893`, passed renderer and real native
retained-input preparation, recording `prepared/judge_ready=true` at
**12:04:38.7534969 UTC**. OIDC failed at **12:04:41 UTC** with `AADSTS700213`;
claim and Step8 were skipped. Separately, run `36151684790`, attempt **1**,
controller `bb39bb0c8c62856af054a69ddbc9c2984652a390`, passed protected approval
job `108126248176`, then job `108126543409` refused at **15:07:20.4670919 UTC**
with `pilot_grading_approval_request_mismatch`. Renderer/input/OIDC/CAS/judge/
publication were skipped. Neither failed run is a grade or a new inference.

The supplied retained deliverable identity remains **5099 bytes**, SHA256
`b7fc35b746bd837277ec5d4ef8e94e234bf8c8ab46777d98712494b8d9955191`.
No private payload was fetched or regenerated here. The existing epoch04 refs,
original grade/claims and nine older admissions remain frozen and separate.
Synthetic fixtures do not establish the contents of any live grade or recover
missing historical files.

At that task's completion, new-head delta review/final CI and explicit leader
authorization for one live readout remained. No live HF/Azure/model/judge
request, workflow dispatch/rerun,
paid action, inference regeneration, new epoch, source
reseal, claim settlement, credential/permission change, Project edit, merge or
CI polling occurred. The task's full-catalog, experiment-design and bounded
reviewer context was retained; no new design review was needed for this
fixture-only correction. Experiment-report-en then im-not-ai-en preserved
separate observations, synthetic-price limits and non-claims. UI/animation and
repo-readiness guidance did not apply because there is no UI work or new public
repository handoff.

## Prior PROJECT5-SOURCE-FIXTURE-2258

Addressed #678 REQUEST-CHANGES `5318640885` at
`ce00aa0e8c5d3db57eabc607e15423605a6b15bb` on the same clean owned branch.
Only `test_cli_source_refusal_has_closed_stage_before_local_or_remote_mutation`
now calls the existing `_authority(monkeypatch, source)` before injecting its
source defect. Without that call, the offline `GITHUB_ACTIONS=false` default
correctly stops at approval before the intended source-preflight boundary.
Production and the global fixture are unchanged.

Real temporary-Git ownership/dirty checks, exact `source_preflight` and
`grading_source_preflight_refused` diagnostics, `remote_mutation_possible=false`,
private-value redaction and no-local/remote-mutation assertions remain intact.
The test still refuses each source defect; no source success is substituted.

At tested SHA `ebe09790be15f152c8d0b1f3915d8ea72e6c5ee5`, the only test
invocation returned **3 passed in 5.22s**, exit 0:

```text
tests/test_codex_budget_pilot_grading_source.py::test_cli_source_refusal_has_closed_stage_before_local_or_remote_mutation
```

The `dirty`, `foreign_trust` and `arbitrary_exception` cases ran from
`batch-runner/` with the existing Python 3.10.12 interpreter, credential-free
`env -i`, offline flags and disabled pytest plugin autoload. Only completion
records changed after this tested snapshot.

The leader's completed CI run `36139756627`, job `108086409951`, reported
**3 failed, 13971 passed, 61 skipped, 46 deselected in 2442.93s**. Eight other
checks passed. Those three failures, the prior **28 passed in 10.11s** at
`81a8ae08a1e215799c67d9ed96fe95df47db4a08`, and the initial **6 failed,
22 passed in 5.40s** at `ec28d6d4f8c1d7c13af6fd4e159292dd46b405ba` remain
separate observations. No prior selector or full suite was rerun here.
Review `5318280295` remains scoped to unchanged production; it does not
authorize merging failed CI. New-head delta review and final CI remain.

The retained producer `b4c95f8eaee16ae2226f3bf6e0493051fa91d770` and terminal
`8083504edf4ceb63f3c4929aac57e0f4b6741593`, source policy, workflow and all
old claims remain unchanged. This fixture-only result does not establish
Azure token issuance or a real grade. Exact leader live authority remains;
no live HF/Azure-management/model/judge call, workflow rerun, inference
regeneration, epoch05, source reseal, Project edit, merge or CI polling occurred.

The full skill catalog was checked once. Experiment-report-en then im-not-ai-en
preserved test/CI provenance and prior evidence limits. No new design or UI
work was involved, so those skills did not apply.

## Prior PROJECT5-GRADING-OIDC-2126

### Grading approval and two explicit source identities

Prepared this grading-only repair in a new clean owned worktree from exact
main `b4c95f8eaee16ae2226f3bf6e0493051fa91d770`. The leader supplied #677's
delivered head `aac3ee35b0693f2a495e711a49799d6b7252774e`, review `5316268600`
and all **10** CI checks passed. That review covers the preceding fixed task2
gate, not this repair. The existing extreme-reasoner context returned
APPROVE-WITH-CONDITIONS before edits for the protected approval dependency,
same-run request binding, closed producer/controller split and unchanged
grader source closure. No additional owner policy choice was needed.

`grade-run.yml` now places the pilot's protected `grading` environment on
`pilot-approve-paid`. This job has no credentials or OIDC permission and
exports only a canonical request digest. `pilot-live` requires that exact
job's successful result and checks the digest before HF, renderer, OIDC,
claim or judge steps. The digest binds the controller and producer sources,
selector/cell, retained terminal, fixed grading controls, campaign/refs/target
and run ID/attempt. Failed, skipped, cancelled, inherited or foreign-request
approval cannot open the route. Main, exact workflow/checkout SHA, attempt1
and explicit paid flags remain required.

The execution job no longer carries an environment, preserving the ordinary
main-ref OIDC context while approval remains mandatory. This is an offline
routing result, not evidence that Azure will issue a token. No federated
credential configuration was inspected or changed. The existing OIDC identity,
route, session and model-connection checks remain before the grading claim.
The real freeze checker already covers the unchanged `pilot-live` name and
the new `Approve paid pilot grading` display name; its enforcement was tested,
not replaced by a new whitelist.

`--reviewed-source-sha` remains the actual reviewed controller/workflow SHA.
The optional `--producer-source-sha` accepts a distinct source only for the
recorded04 task2 A1 producer/cell/terminal below, with the existing fixed refs.
Branch setup/inspection rejects a producer binding. Workload plans, configs,
retained terminal/manifest/claim/input proofs and materialized inputs keep the
producer identity. Source preflight and the staged pinned grader use the
controller checkout. New prepared, claim, terminal-binding and public records
carry `controller_source_sha` separately; existing `source_sha` still names
the producer. Both sources and the approval digest are revalidated through
readiness, admission, publication and reconciliation. A missing historical
controller field is not adopted as new evidence.

### Supplied preparation pass, OIDC failure and skipped grading

The leader reports grading run `36132571260`, job `108062994893`:

- Renderer passed during **12:04:26–12:04:29 UTC**.
- Retained-byte checks and real native atomic input materialization passed
  during **12:04:29–12:04:38 UTC**; `prepared/judge_ready=true` was recorded at
  **12:04:38.7534969 UTC**.
- OIDC login failed at **12:04:41 UTC**, with `AADSTS700213` for subject
  `repo:hyeonsangjeon/gdpval-realworks:environment:grading`.
- The grading CAS claim and Step8 invocation were skipped. No grade or
  regrade is established.

The already-retained workload remains source
`b4c95f8eaee16ae2226f3bf6e0493051fa91d770`, cell
`0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r1`, terminal
`8083504edf4ceb63f3c4929aac57e0f4b6741593`. Its supplied deliverable identity
is **5099 bytes**, SHA256
`b7fc35b746bd837277ec5d4ef8e94e234bf8c8ab46777d98712494b8d9955191`.
The real terminal/source/byte/native preparation pass belongs to that run.
No payload was fetched here, and the offline fixtures do not recover or
revalidate those live bytes. Preparation is not a grade, score or invoice.

Campaign `budget_pilot_ci_20260925_04` and refs
`pilot-inference-20260925-04` / `pilot-grades-20260925-04` remain fixed in the
existing private target with name SHA256
`a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44`, rooted at
recorded bootstrap `bfc7ae01ed14490817ceb7cb406adcb9bb95f557`. This repair
does not regenerate or relabel the retained inference, settle a claim or
create an epoch05. The old nine admissions and their separate partial costs,
missing raw-file limits and unknown child causes remain frozen below.

### Focused offline validation

At tested SHA `81a8ae08a1e215799c67d9ed96fe95df47db4a08`, this selector
returned **28 passed in 10.11s**, exit 0:

```text
tests/test_codex_budget_pilot_grading_oidc.py
```

It ran from `batch-runner/` with the existing Python 3.10.12 interpreter,
credential-free `env -i`, offline flags and disabled pytest plugin autoload.
The earlier invocation of the same selector at
`ec28d6d4f8c1d7c13af6fd4e159292dd46b405ba` returned **6 failed, 22 passed in
5.40s**, exit 1. Its synthetic source fixture incorrectly equated the
historical manifest base with the reviewed controller. Only that fixture
assertion and a check that retained-proof refusals reach their intended
boundary changed before the passing run; production stayed byte-identical.
These are separate observations, not a combined result.

The family executes the actual workflow approval digest and real compiler,
materializer, entry/schema/hash validators, claim/CAS, publication and
reconciliation helpers. HF, original payloads, renderer, source host, native
rename and judge process are explicit test doubles. Coverage includes
no-network plan, failed/skipped approval and rerun refusal, main-ref routing,
old producer plus new controller, request/source/terminal/receipt/cleanup/byte
tampering, claim before judge, one-use replay refusal, token isolation and
unchanged inference refs/bytes across private grading actions. Lost publication
acknowledgment can be reconciled from valid server evidence without rewriting
the local unresolved receipt or rerunning the judge. No real native capability,
Azure token, HF mutation, grade or quality measurement is claimed by these tests.

Only the pilot workflow/connector, directly coupled fixtures/assertions, this
focused family and completion records changed. The Step2 producer, approved
retention repairs and diagnostics, original-input/model/budget behavior,
registration/refs, runtime/source pins, fixed grader/config/rubric and generic
grading jobs remain unchanged. No dependency was installed; no old22/24 family
or full suite was rerun. Only completion records changed after the passing
tested snapshot.

New-head review and CI remain. The leader must authorize an exact reviewed
controller and this unchanged producer/cell/terminal before any later live
OIDC, grading claim or single fixed-judge invocation. No inference rerun,
source reseal, claim settlement, workflow dispatch, live HF/model/grader call,
Azure management/permission change, Project edit or CI polling occurred here.

The full skill catalog was checked once. Experiment-design protected the
honest source boundary without adding a model axis. Experiment-report-en then
im-not-ai-en kept supplied live observations, synthetic test results and
remaining authority distinct. UI/animation and broad repository-readiness
guidance did not apply.

## Prior gate work and observations

### Prior #677 validation, not rerun

The alias-only correction addressed REQUEST-CHANGES `5315917785` at
`e6c6da71d67741a953a8e21b4bf5ddea020e783a`; source review `5315662337` was
scoped to unchanged production. Positive ordinals **6, 7, 29**, typed prefix
**0–5** refusals and the alias/run/config/standalone assertions remain intact.
The exact node
`tests/test_codex_budget_pilot_grading.py::test_aliases_preserve_fixed_config_and_canonical_run`
returned **1 passed in 2.29s**, exit 0, at
`c58196526672e5e5375b0b1830cd6aa97b8d33ac` in its credential-free Python
3.10.12 invocation. The leader's earlier CI run `36113064105`, job
`108000707569`, reported **1 failed, 13945 passed, 61 skipped, 46 deselected
in 2150.36s**; the stale positive index0 was its sole failure. Nine other
applicable checks passed and deploy was skipped. The later delivered #677
review/check scope is recorded above. The original **22 passed in 166.07s**
at `6c90e03a2683bdbccaae557c3a654a9d946e7f00` remains the separate prior gate
validation below. None of these earlier selectors or full CI was rerun here.

### Prior fixed task2 gate preparation, unchanged

Prepared the fixed corrective identity `budget_pilot_ci_20260925_04` from exact
main `0bb141f3bf93510ccb399800a4aa0901ceb36638` in a new clean owned worktree.
Its first eligible cell is original ordinal **6**,
`0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r1`. The compiler keeps the original
five tasks, 30 cell IDs and relative A1/B1/C1/C2/B2/A2 order. Ordinals **0–5**
are out of scope and refuse selection before source/host authority, local
state or remote admission; they are not manufactured completed cells. Only
fixed ordinal6 may use its own verified bootstrap without a predecessor.
Ordinal7 and every later eligible cell still require their immediate actual04
predecessor's validated terminal and acknowledged output evidence.

The new fixed refs are `pilot-inference-20260925-04` and
`pilot-grades-20260925-04`, each designated to start at recorded bootstrap
`bfc7ae01ed14490817ceb7cb406adcb9bb95f557` in the existing private target with
name SHA256 `a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44`.
No actual ref was created, inspected or changed. Existing four-request,
one-ref setup, genuine absence checks, independent one-use reservations,
readback and CAS remain. The first eligible grade keeps alias `pilot/cell-06`
and may claim its separate grading bootstrap after valid retained input;
it does not require invented earlier grades. Grading's control-path lookup
excludes the prefix and never writes the inference ref. No grading order,
start-offset option, workflow input, scheduler or storage framework was added.

The leader supplied #676 head `88b13f974b8be508cb5c5596db401447469e032c`,
review `5314792016` and all **9** checks passed for the preceding exact
empty-reflection-pair repair. That approval does not cover this activation.
The existing extreme-reasoner context returned APPROVE-WITH-CONDITIONS before
production edits for this fixed ordinal6 policy, prefix refusal, immediate
predecessor requirement and separate grading ref. No further design or budget
choice was required. The production delta changes only the closed registration,
selection/binding checks, the two inference bootstrap checks, grading's eligible
control paths and five workflow campaign literals. Directly coupled CI fixtures
now select task2 rather than the excluded prefix. Historical registrations and
standalone defaults remain unchanged.

This prepares only one possible later corrective task2 A1 admission. The other
**23** suffix cells have no execution authority. Old01 and epoch02 have **2**
frozen admissions; epoch03 has **7**, comprising six failed/terminal-verified
task1 cells and one execution-successful but unretained/ungraded task2 A1.
Those **9** stay separate. A later authorized gate would make **10** total
admissions across the histories, not another 30-cell restart or a pooled
comparison. It would not recover, replace or grade the old task2 A1 or its
5549-byte deliverable identity. No claim, source binding, clock or partial cost
was reset or adopted.

### Prior gate validation, not rerun

At tested SHA `6c90e03a2683bdbccaae557c3a654a9d946e7f00`, one invocation from
`batch-runner/` ran only:

```text
tests/test_codex_budget_pilot_epoch04_gate.py
```

Result: **22 passed in 166.07s**, exit 0. Only completion records changed between
that snapshot and the previously delivered head
`e6c6da71d67741a953a8e21b4bf5ddea020e783a`. The invocation used the existing
Python 3.10.12 interpreter,
credential-free `env -i`, HF/data/transformer offline flags, disabled plugin
autoload, `-q -o addopts= -p no:cacheprovider --tb=short --maxfail=1`, a local
JUnit report and a 480-second timeout with a 10-second termination grace.
No dependency was installed. No old 24/13/35-case family or full suite was run.

The selector verifies exact04 registration/ref/ordinal identity, all six prefix
refusals, unchanged original order/model/input/budget controls, separate old
namespaces, fixed-ref setup and no replay after a lost response or unproven
absence. It exercises genuine Step2 success serialization, unchanged retained
result/ledger/deliverable bytes, terminal/receipt binding, canonical grading
materialization and the first grading claim at its own bootstrap. It also
checks next7 admission only after actual04 cell6 evidence, same-cell replay
refusal, mixed epoch/source/ref refusals, unknown/unfinished or lost output
blocking, and rejection of a prefix grading tip. A lost terminal response can
advance only the next cell after valid server-side confirmation; the original
local unresolved receipt remains byte-identical and response delivery is not
asserted. Every fake grading action preserves the inference ref and old refs.

Compiler, dispatcher, deadline, producer serialization, byte/fingerprint/receipt
validators, publisher, terminal checks, materializer and claim/CAS logic are
real. Original-input provenance, reviewed-source/host capability, native turns,
HF/HTTP responses, native directory installation and grader-entry readiness are
explicit test doubles. No judge runs. The host-derived input identity is bound
to verified fake publication, not independent provider authentication. This is
not evidence of actual branch setup, live admission, native capability, retained
live output, a grade or output quality. The publisher's approved empty-pair and
ledger-note repairs, closed diagnostics, runtime/source pins, Step2, fixed
grader and model/input/budget implementation bytes are unchanged.

### Supplied live observation and frozen epoch03

The leader verified epoch03 second-task A1 run `36100954518`, job
`107963127255`, on source `fb232a074f395766f9f83ddc7195a9997a3428f5`.
Execution succeeded during **2026-09-25 06:03:40–06:04:31 UTC**, exit 0.
Retention refused `unsafe_result_fields` at **06:04:35.5824504 UTC**, exit 2.
The completion reports succeeded, null reason, confirmed cleanup, one child
invocation and no outer timeout. It is not relabeled failed to use withholding.
There is no established publication/terminal acknowledgment or grade.

The supplied identities are:

- Public artifact `10849486947`, envelope SHA256
  `138d888159062e3ccfe4ce390ea8ea756d2f5c38282268677ba18e7c7be3f9d4`.
- One deliverable, **5549 bytes**, SHA256
  `ccb6c2060f2abf5b8662859a72a5356e2e62aef162e9b712bc2b324bbde38c11`.
- Result, **7090 bytes**, SHA256
  `0888a099bae76ad876476fc57e34dc02b3f64831d3e7cc53940ca7e6f0b9da1d`.
- Ledger, **915 bytes**, SHA256
  `ea82ccbf770c0f923217f3836a6b47e1c7f9ac3bd944ee3f0f2d235696e41045`.

The partial receipt reports **57260 input**, **2955 output**, **43136 cached-input**
and **898 reasoning tokens**, with **USD 0.090419** known partial cost. Estimate
and HTTP count are null; `invoice_complete=false`. These values describe this
cell's partial receipt, not a bill, complete campaign cost, request count or
quality measurement. No costs for the other epoch03 cells are inferred here.

Raw result, deliverable and ledger files are unavailable. This task did not
fetch or reconstruct them, identify the historical offending key, recover a
payload or inspect/settle a claim. The leader reports that the first task's
A1/B1/C1/C2/B2/A2 all failed with verified terminals. The second task's A1 has
real execution-success evidence but remains unretained. Epoch03 source and
claims are frozen, alongside the independent old01 and epoch02 failures below.
The earlier repair authorized no epoch04 preparation. The present leader
decision supersedes that preparation restriction only for the fixed task2 gate;
no subsequent live cell, rerun, grade, source reseal or claim settlement is
authorized here.

### Prior #676 repair and validation, not rerun

The seven-line publisher repair from exact main
`fb232a074f395766f9f83ddc7195a9997a3428f5` accepts Step2's supported no-QA pair
`reflection_history: []` and `reflection_attempts: 0`, or both absent for
existing compatibility. A present history must be an exact empty list and
the count an exact integer zero. Nonempty history, partial pairs, bool/float/
nonzero counts, reflection scores, unknown fields and recursively forbidden
private fields still refuse. Its bounded pre-edit review approved only that
inert pair with unchanged original bytes and existing privacy/publication gates.

The actual Step2 CLI wrapper and final writer reproduced old-allowlist rejection
at `results[0].reflection_history` and `results[0].reflection_attempts`, even
with QA disabled. That establishes a supported producer/consumer mismatch,
not the offending key in the unavailable live payload. No original field is
stripped, normalized or re-fingerprinted for retention. Only the established
grading materializer adds provenance and computes a distinct derived
fingerprint. Unsafe succeeded results cannot use failed/stopped withholding.

At tested SHA `69709958aaad9ab940c3b01242c053086d98fd1c`, one completed
invocation from `batch-runner/` ran only:

```text
tests/test_codex_budget_pilot_success_retention.py::test_success_writer_retention_contract
```

Result: **24 passed in 215.31s**, exit 0. Only completion records changed between
that tested snapshot and the prior delivered head. It was one new focused
selector, not a rerun of the prior 13/27/35-case families or the full suite.

It covers no-token/no-network plan; the real Codex/Step2 success writer and
genuine ledger export; exact-pair and absent-pair compatibility; nonempty,
partial, bool/float/nonzero and scored reflection refusals; unknown, nested
secret, message and original-input fields; changed result/deliverable/ledger
bytes, declared dataset source, receipt and cleanup refusals; failed-result
withholding; and lost output acknowledgment without publication or inference
replay or next-cell advancement. Retention's actual fake returned commits bind
the real terminal validator, allowlisted fetches, identity builder and canonical
grading materializer. Changed grading-input bytes or the approved identity
document refuse. Original bytes, failed/succeeded status, partial accounting,
public completion bytes and the inference/grade ref separation are asserted.

Compiler, dispatcher, cumulative deadline, Codex reservation/settlement, Step2
CLI serialization, fingerprint/byte/receipt checks, publisher CAS, terminal
validation and grading materialization are real. Original-input provenance,
reviewed-source/host capability, native turns and HF responses are synthetic.
The grading install syscall is an explicit test double, not native capability
proof. Host-derived grading identity comes from the verified fake publication;
it is not independent provider authentication. No judge runs, and no test
establishes live retention, native installation/execution or output quality.

The invocation used the existing Python 3.10.12 interpreter, credential-free
`env -i`, HF/data/transformer offline flags, disabled plugin autoload,
`-q -o addopts= -p no:cacheprovider --tb=short --maxfail=1`, a task-owned local
JUnit report and a 480-second timeout with a 10-second termination grace.
No dependency was installed and no CI status was queried.

Earlier invocations of that prior selector are separate fixture evidence,
not added live failures or part of the 24-pass result:

| Tested SHA | Result | Fixture boundary |
|---|---|---|
| `9c2fd2703c4acbf6308f98920eab34e208075140` | 23 failed, 1 passed in 135.58s, exit 1 | The synthetic child lacked the existing connection-confirmation flag; no fake turn ran. |
| `3b7d9ac932b313de1bd0f49f5415746282620c78` | 23 failed, 1 passed in 174.98s, exit 1 | The fake turn callback lacked the existing `task_deadline` keyword; no fake turn observation was reached. |
| `7d47d78f257d7e41963bcfc4144f19f4530dfb83` | 1 failed, 1 passed in 13.92s, exit 1 | The assertion read the completion checksum envelope as its payload. |
| `526c70ad13c3933e2c2319bc59245dcfb1561c1a` | 1 failed, 4 passed in 38.46s, exit 1 | Python equality treated `False` as `0`, so the negative fixture did not write changed bytes. Canonical JSON comparison now preserves bool/int/float distinctions. |

Only the new fixture changed between these attempts and the passing snapshot;
the production seven-line addition did not change. The last three invocations
used fail-fast; the first two completed all cases. No earlier family or live
diagnostic was used to fill any gap.

### Prior gate preparation and reviews, not rerun

The #675 activation's delivered head was
`f7844c3444014b6b89b9c35d11831431ebfe9d7e`, with review `5305790700` and all
10 checks passed, as supplied by the leader. It was prepared from
`c739e5596cf874ef3f48d0943404101f10500372`. Its selector
`tests/test_codex_budget_pilot_epoch03_gate.py` remains **13 passed in 23.30s**,
exit 0, at `bda13885f4eee9d489e150bd2be97c1f043bedd8`, separate from the later
publication-contract evidence and this gate. Its original preparation scope
and offline setup/routing evidence remain recorded in the changelog; it was not authority
for this repair or for a live replay. Earlier #674 FINAL-APPROVE `5305021240`
at `075ab8f065d88207d9b7ad0de5d02df487867793` and all 9 checks covered the
closed diagnostic. Neither prior review approves this new head.

### Prior diagnostic validation, not rerun

The bounded exception follow-up addressed reviews `5304339793` and
`5304688416`. Its three existing `bytes`, `log_io` and `unexpected` nodes of
`tests/test_codex_budget_pilot_failure_category.py::test_diagnostic_rechecks_bytes_and_owned_cleanup_without_rewriting_completion`
returned **3 passed in 20.15s**, exit 0, at
`14b44aa2e04d018c27d41d9be01c8d6ecf1e9895`. It distinguishes expected
evidence I/O/validation failures from the explicitly supported internal
`AssertionError` and supported logger/sink failures. All unavailable signals
are fixed and non-authoritative, with no private canary in captured surfaces;
completion bytes, original exit 1 and partial accounting remain unchanged.
These are fake failure boundaries, not observed live errors.
Delivery is best effort, not guaranteed containment of arbitrary programming
faults. Category allowlisting, cleanup/hash/source/cell revalidation, silence
on success/plan/already-finalized state and duplicate guards remain unchanged.
Neither a category nor an unavailable signal grants terminal/publication or
admission authority. The earlier initial read of 7 passed/2 running was
superseded by the leader's final #674 observation above, not by a query here.

The same three-node selection previously returned **3 passed in 22.91s**,
exit 0, at `249d733f96941ce00269e3e19f8f43d613b8636c`. That observation covered
the earlier fixed signals with catch-all handling, not this narrowed revision.
Only completion records changed between that snapshot and
`9aa4b617f241d39df63f3fbf2ef2d2b51cd0a0a6`. It remains separate from this
invocation and the original full-family result below.

The original selector was
`tests/test_codex_budget_pilot_failure_category.py`. At tested SHA
`48868b2af70860285d8611b6a22d0e50c211b0aa`, it returned **27 passed in 178.61s**,
exit 0. Only completion records changed between that passing snapshot and
`f33bcd7dfbdbf579ecd7d995ac0ed493c2233afb`. That earlier invocation used the
existing Python 3.10.12 interpreter, credential-free
`env -i`, HF/data/transformer offline flags, disabled plugin autoload,
`-q -o addopts= -p no:cacheprovider --tb=short --maxfail=1`, a private JUnit report
and a 240-second timeout with a 10-second termination grace.

Compiler, dispatcher, deadline persistence, Codex category production, Step2
serialization/projection, CostReceiptLedger export, fingerprint/byte validation,
cleanup validation and CLI completion/logging are real. Input provenance,
reviewed-source/host-version admission, runtime observations and child transport
are explicit test doubles. Network, auth, native launch and HF publication are
forbidden. The SDK is not installed in this local interpreter; the test's fake
host-version metadata is not native-install or execution-capability evidence.

Coverage includes actual producer `rate_limited` and `runtime_start_failed`
branches, stopped output, missing/unknown/private-looking/nonstring categories,
hash/cell/run mismatch, missing/malformed output, nonzero exit with a successful
row, no diagnostic on success, changed result bytes, idle/foreign/unreaped
owners, logging failure, plan/input-only modes and later publisher refusal.
The public completion schema, original partial accounting and bytes are checked
unchanged. Revalidation and same-host final-state inspection neither repeat the
diagnostic nor invoke another child. No prior 31/35/25/8-case family or full
suite was rerun; no live cleanup, provider cause, write, invoice or grade is
established by these synthetic tests.

Earlier attempts of this same selector remain separate fixture evidence:

- `e9a1dc355c7e8b40f316e5fceb96074ffbe5e0c8`: **1 setup error in 1.68s**, exit 1,
  before the first case, because a reused older guard imported the absent
  `openai_codex` SDK merely to forbid its constructors.
- `8b92c0e1b01b1aeed17ecd0ae00cb16a60c6245b`: **1 failed in 8.88s**, exit 1.
  The fake turn observation used an unsupported constructor argument and did
  not reach the intended producer-category assertion.
- `6b215335bc558aa4232b3e54e3eca58c93bc668a`: **1 failed in 9.27s**, exit 1.
  An explicit producer-reached assertion exposed that same fixture error:
  HTTP status belongs in structured turn-error metadata, not a
  `TurnObservation` constructor argument.

The fixture now uses the existing SDK-independent boundary-guard convention
and the correct fake turn-error shape. No production code changed between
these attempts and the passing snapshot, and no dependency was installed.

### Prior ledger-note evidence, not rerun

The #673 repair accepts only the three exact nonsecret Codex note literals
alongside null/strict-code notes at both publisher checks, without rewriting
ledger bytes. That confirmed source mismatch also blocked otherwise-safe
successful output retention; it did not identify either historical child cause.
Its selector `tests/test_codex_budget_pilot_ledger_notes.py` remains **31 passed
in 68.87s** at `14bcae565a1b2212f3a0405d2ddf90f37e55d4cb`, exit 0, separately
from the initial **31 failed in 53.31s** at
`53c541cbe03c4579c6e63c75cee05e1a0f754bec`, exit 1. Those initial fixture
failures comprised 17 cases missing a test-owned `GDPVAL_CODEX_RUN_ROOT` and
14 cases whose empty deliverable list disagreed with the test-owned file tree.
They were not additional live failures. This task did not repeat those tests.

### Earlier two admitted failures remain separate and frozen

The following observations and artifact identities were supplied by the leader;
this task did not fetch logs, artifacts or private files.

**Epoch02.** Source `4aac36b6f92d2a14b8cac02d793356d6687ace6d` remains frozen.
Before admission, runs `35980633861` and `35980667641` actually verified the new
refs `pilot-inference-20260924-02` and `pilot-grades-20260924-02` at bootstrap
`bfc7ae01ed14490817ceb7cb406adcb9bb95f557`. A1 run `35983583688`, job
`107580952943`, claimed the cell, then execution exited 1 at **10:03:03 UTC**
and retention exited 2 with `unsafe_ledger_note` at **10:03:07.2463912 UTC**.
This was after admission. The earlier branch verification is not a claim that
the current inference ref still points to bootstrap.

**Old01.** Source `2fe1c6925e6d76c03b85851046d52216bee74a16` independently
remains frozen. A1 run `35954811341`, job `107490761123`, passed real input,
full sandbox and private claim, then execution exited 1 at **04:20:18 UTC**
and retention exited 2 with `unsafe_result_fields` at **04:20:21.6482243 UTC**.
That observation is not reinterpreted as the ledger-note defect.

Each public envelope reports failed/`child_nonzero_exit`, one child invocation,
confirmed cleanup, no timeout, no deliverables and **29 other cells not run**.
There are two admitted failed/unretained A1 cells across separate histories,
not two completed comparison results or a completed 30-cell campaign.

| History | Input tokens | Output tokens | Cached-input tokens | Reasoning tokens | Known partial cost (USD) |
|---|---:|---:|---:|---:|---:|
| Old01 | 55033 | 4387 | 12544 | 3566 | 0.175163 |
| Epoch02 | 89161 | 5442 | 47872 | 4073 | 0.196821 |

Both cost estimates are null and both receipts have `invoice_complete=false`;
epoch02's HTTP count is null. These are partial usage/cost observations, not
invoice totals, complete costs or request counts. The two histories' accounting
is kept separate, and old01 A1 is not a result in the epoch02 comparison.

The unavailable raw files remain bound only by the supplied identities:

- Epoch02: public artifact `10801891703`, envelope SHA256
  `f2b445662539281197c548794c1060b57034b2d06ae8e4810d74c84dd750e298`;
  result **8987 bytes**, SHA256
  `02440bfbb6cec71edf042a1d6eb8d36cf3f3ffa6f5a55552ec74fff288e52f0e`;
  ledger **3561 bytes**, SHA256
  `6c9ab614e2b8e287a165730b24837d51777515c0c8a3e61935253bc670be8048`.
- Old01: public artifact `10789759614`, envelope SHA256
  `570b0bc196a21efaa0a23123958a46d0ae2b2a52a16d19fb0661aae6d8b046e6`;
  result **7460 bytes**, SHA256
  `c9313667c3890a1b4bc876d7bb771b41e430c2f595515c1a4bc0041e9fa1175b`;
  ledger **1838 bytes**, SHA256
  `116561470c73f4fbeae18a7db81c74947991e1b46f695411842f5bbd6153d93a`.

No raw result/ledger was available or reconstructed from these hashes. The
precise offending field/note and actual child failure cause remain unknown in
both histories. No current remote claim state was inspected or settled here.
The new code cannot recover lost files or authorize a different source under
either existing admission.

### Prior gate preparation authority and unchanged controls

New-head review and final CI remain, followed by leader-authorized verification
of both new refs at their own bootstrap, binding of the exact final reviewed
source and one-use reservation for only ordinal6 task2 A1. This code cannot be
applied to a frozen admitted source by changing its claim or borrowing artifact
identities. Live setup/inspection, execution, source reseal, payload recovery,
settlement/adoption, replay, successors and grading remain unauthorized here.
Checked live retention and actual native grading-host capability remain
unproven by the offline tests.

The fixed private target name SHA256 remains
`a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44`, with immutable
bootstrap `bfc7ae01ed14490817ceb7cb406adcb9bb95f557`. New fixed refs
`pilot-inference-20260925-04` and `pilot-grades-20260925-04` are designated only;
their actual state was not inspected or changed. Epoch03 refs
`pilot-inference-20260924-03` and `pilot-grades-20260924-03`, dataset main, earlier
grade/inference refs, registrations, claims and receipts are untouched. Success still needs validated
retained deliverables and bound terminal/receipt evidence before separately
authorized fixed grading; execution success alone is not retention or quality
success. Failed cells remain failed and need their available closed category.
An unretained terminal or missing diagnostic blocks expansion. After the one
gate, stop for the leader's retention/grade decision regardless of outcome;
no automatic successor or replacement epoch is authorized.

The code retains the five-task/30-cell design and canonical A1/B1/C1/C2/B2/A2
order, GPT-5.4, direct-v1/xhigh, SDK 0.147.0, 180-minute cumulative budget
including wait/recovery,
30-minute attempts, A4 fresh attempts, B/C retained continuation, C-only feedback,
one inference slot and one fixed grade per eligible result. No budget axis,
automatic monetary cutoff, epoch/storage framework or model/grader change was
introduced. No live HF/model/grader or Azure-management request, workflow
dispatch, source reseal or CI polling occurred.

For the prior gate preparation, the full skill catalog was checked once.
Experiment-design applied first to the closed administrative/source-epoch
boundary and the one-gate stop rule;
no model comparison or budget axis changed. Experiment-report-en separated
historical partial observations, nine frozen admissions and synthetic04
evidence, then im-not-ai-en copyedited the records while protecting their
numbers, identities and limits. UI/animation and broader repository-readiness
skills were not applicable. Earlier records below remain historical
observations; their tests were not rerun.

## PROJECT5-REGISTRATION-FIXTURE-1715

### Fixture-only registration correction

Addressed leader REQUEST-CHANGES `5301707351` at
`263ce086813afb8a251a39ab3cd05f7d28e98fdb` on the same #672 branch. Existing
source approval `5301378872` remains scoped to unchanged production; it is not
approval of the new test delta. No production code, registration metadata,
source/runtime pins, workflow, ownership policy or existing assertion changed.

The leader reported completed CI run `35970394062`, job `107538875886`:
**8 failed, 13820 passed, 61 skipped, 46 deselected in 2052.50s**. Nine other
checks succeeded, pytest failed and deploy was skipped. All eight failures were
the four CLI selectors below, which returned `grading_contract_refused` with
stage null before their intended boundary; fake branch creation was not reached.
This supplied full-CI observation is separate from the local validation below.

The fixture rebound `pilot.ROOT` without moving its import-time parent and CI
registration paths. The real `ci._registration_bytes` validation could not
compute `pilot.REGISTRATION.relative_to(pilot.ROOT)` in those mixed coordinates.
The fixture now copies the genuine parent and closed epoch02 registration bytes
into the temporary checkout before its synthetic Git commit, then binds both
`pilot.REGISTRATION` and `ci.REGISTRATION` there before compiling the plan.
Clean-source checks remain meaningful; registration validation is not stubbed.

### One offline invocation, eight cases

At tested SHA `19280b44dad5e4842b681b32d38175ad5a40d7a1`, one invocation from
`batch-runner/` ran exactly these four selectors:

- `tests/test_codex_budget_pilot_grading_source.py::test_cli_plan_does_not_run_source_preflight_or_setup`
- `tests/test_codex_budget_pilot_grading_source.py::test_cli_source_refusal_has_closed_stage_before_local_or_remote_mutation`
- `tests/test_codex_budget_pilot_grading_source.py::test_cli_root_refusal_is_before_session_and_retains_partial_local_state`
- `tests/test_codex_budget_pilot_grading_source.py::test_cli_receipt_failure_preserves_reservation_and_unknown_mutation_without_replay`

Result: **8 passed in 12.75s**, exit 0, using the existing Python 3.10.12
interpreter, credential-free `env -i`, HF offline defaults and a 180-second
timeout. Tests retain real temporary Git and its test-only different-owner
switch, genuine registration/compiler/source checks, and forbidden auth, HF and
runtime boundaries. Plan, source refusal, root refusal and receipt failure reach
their intended assertions. Receipt cases use in-memory fake branch creation;
no remote branch, actual ownership change or native execution is demonstrated.
Only completion records changed after this tested snapshot.

### Preserved history and remaining authority

Earlier results remain separate: **34 passed, 1 failed in 80.16s** at
`63afe729b9edab8c59f888fc86c4b4b642999b71`, **1 passed in 27.90s** at
`d514d811374d80bb7e14ad051e10a21e402c5575`, and **2 passed in 3.23s** at
`4b6f196441b330ae4e177cfd7aeb29e2a3306d16`. The whole source family, 35-case,
25-case, 2-case and full-suite families were not rerun.

Old01/source `2fe1c6925e6d76c03b85851046d52216bee74a16` and its admitted claim,
partial accounting and unknown remote state remain frozen. Epoch02 and its
proposed new30 remain preparation-only, not continuation of old01. New-head
delta review and CI, then leader authorization of the exact live source,
actual ref bootstrap and selected cell, remain. No live HF/model/grader or
Azure-management operation, workflow dispatch, source reseal or CI polling
occurred. Existing historical records below are unchanged.

The full skill catalog was checked once. Experiment-report-en and im-not-ai-en
kept the supplied CI failure, bounded local result and review scopes separate.
No new experimental axis or UI work required design or UI skills.

## PROJECT5-SETUP-HTTP-STATUS-1613

### Setup status belongs to the current operation

Addressed leader REQUEST-CHANGES `5301122695` at
`0a863d91204554ecbed4dcc62cd4494bb52f6b2d` on the same #672 branch. The existing
extreme-reasoner approved this bounded CI/HF reporting correction before edits;
that decision is not approval of the resulting head.

`grading.setup` now clears `http_status` to null at its existing
`branch_absence`, `branch_create` and `branch_readback` transitions. The status
stays null until that operation receives a response. Bootstrap already starts
at null, and each real response remains in the `responses` list. Phase names,
reservation order, operation counts, ambiguity/no-replay handling and all
parent/role/private checks are unchanged. No workflow or HF transport changed.

The source distinction is important: `_hf_client` already clears status when
its transport is entered. The new resets also cover local refusals before that
entry, including the pre-request deadline checks. The selected transport-failure
tests preserve this contract; they do not demonstrate a live stale-status event.
Null means no response observed for the current operation, not that no remote
mutation occurred. A lost create response still leaves its reservation unresolved.

### Two-case offline evidence

At tested SHA `4b6f196441b330ae4e177cfd7aeb29e2a3306d16`, one invocation from
`batch-runner/` ran only these exact nodes:

- `tests/test_codex_budget_pilot_epoch02.py::test_setup_refusals_keep_reservation_and_never_create_other_ref[create_lost-3-True]`
- `tests/test_codex_budget_pilot_epoch02.py::test_setup_refusals_keep_reservation_and_never_create_other_ref[readback_unavailable-4-True]`

Result: **2 passed in 3.23s**, exit 0. The existing Python 3.10.12 interpreter ran
under credential-free `env -i`, HF offline defaults and a 180-second timeout.
The CLI, installed SDK, bounded transport guards and receipt serialization are
real; HF responses and mutation/lost-response scenarios are synthetic.

Both cases assert null current status and the exact stage in public output and
the private receipt. Lost creation preserves bootstrap 200 and absence 404;
unavailable readback additionally preserves creation 200. Neither inserts a
response for the lost operation. Existing no-clobber, reservation, replay and
other-ref exclusion assertions remain. The same status/history assertions also
cover the existing `create_parent` pre-request refusal case, which was not run.

Prior evidence remains separate: **34 passed, 1 failed in 80.16s** at
`63afe729b9edab8c59f888fc86c4b4b642999b71`, then **1 passed in 27.90s** at
`d514d811374d80bb7e14ad051e10a21e402c5575` after the test-only checkpoint-reader
correction. No 35-case, 25-case or full family was rerun. Only these completion
records changed after the new two-case tested snapshot.

### Unchanged histories and remaining authority

Old01/source `2fe1c6925e6d76c03b85851046d52216bee74a16` remains frozen with
1 admitted failed/unretained A1, 29 not run and known partial cost USD 0.175163
(`invoice_complete=false`). Its claim, raw-file identities, uncertainty and
receipts remain historical. Proposed new30 is independent; old1 plus new30 would
mean 31 admitted cells across the histories only if later authorized. No epoch,
namespace, source-binding, model, grader or experiment-control policy changed.

New-head delta review and CI remain, followed by the leader's exact live-source,
actual branch bootstrap and selected-cell authorization. No live HF setup or
inspection, model/grader call, workflow dispatch, source reseal or CI polling
occurred. The full skill catalog was checked once; experiment-report-en and
im-not-ai-en preserve evidence scope and English clarity. Experiment-design and
UI skills did not apply because no experimental axis or interface changed.

The sections below remain historical records at their stated sources.

## PROJECT5-EPOCH02-PREP-1511

### Closed replacement epoch, preparation only

Implemented the independent `budget_pilot_ci_20260924_02` on a new worktree from
`e23d8acc1d032b3e937ec099324e3221334c9b4b`. No epoch02 HF setup, inspection,
admission, inference or grading was performed. The leader reported #671 review
`5300302955` at `2ff94450d52fb4b5c80cded3ba0505321bac3a2f` and all 9 checks
passed for the preceding withholding repair. That review does not cover this
epoch02 implementation. The existing extreme-reasoner approved its bounded
CI/HF/cost contract with conditions before edits, for code/offline preparation
only. This base and the local test SHAs are not an execution-source seal.

Old01 remains frozen at `2fe1c6925e6d76c03b85851046d52216bee74a16`, with
1 admitted failed/unretained A1 and 29 not run. Its run `35954811341`, job
`107490761123`, execution exit 1 and retention exit 2 (`unsafe_result_fields`)
remain historical. Known partial cost is USD 0.175163, with a null estimate and
`invoice_complete=false`; it is not an invoice total or a request count. The raw
result/ledger, precise child cause, unsafe field and current remote claim state
remain unavailable or unknown as recorded below. No claim was settled, adopted,
deleted, overwritten, replayed or used as an epoch02 comparison result.

The proposed new scope is 30 independent cells, not the old remaining 29.
If all new cells are later admitted, old1 plus new30 means 31 admitted cells
across two histories. The same five original tasks, A1/B1/C1/C2/B2/A2 order,
GPT-5.4/direct-v1/xhigh, SDK/CLI 0.147.0, 180-minute cumulative budget including
wait/recovery, 30-minute attempts, A4 fresh attempts, B/C retained continuation,
C-only feedback, one inference slot and one fixed grade per eligible result
remain unchanged. There is no automatic monetary cutoff or automatic launcher.

### Fixed refs and existing gates

The new closed registration preserves the old registration. It names only the
existing private dataset fingerprint
`a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44` and recorded
bootstrap `bfc7ae01ed14490817ceb7cb406adcb9bb95f557`. The fixed refs are
`pilot-inference-20260924-02` and `pilot-grades-20260924-02`. Their actual
existence and current state have not been observed in this task.

The existing grading entry accepts `pilot/inference-branch-setup` and
`pilot/inference-branch-inspect` for the inference ref. `pilot/branch-setup` and
`pilot/branch-inspect` now select the new grading ref. Each explicit setup
invocation handles one ref and its own private no-clobber root, reservation and
receipt. Four logical requests at most verify exact private bootstrap access,
establish genuine revision absence, create once with `exist_ok=false`, and
verify readback at the actual bootstrap. Generic 404s, inaccessible/public or
foreign targets, existing refs, redirects, changed parents and ambiguous
responses refuse. No automatic second-ref creation, adoption, deletion or replay
is available. Inspection remains two bounded reads and cannot acknowledge an
earlier setup. Default planning does not look up tokens or make network calls.

Admission reads, claim/output/terminal CAS writes and terminal-parent checks use
only the new inference ref. Claims, output manifests/receipts, terminal records
and grading provenance bind the campaign, actual source and designated ref.
A1 requires the recorded bootstrap and an absent prefix; later cells require
the exact immediately preceding canonical terminal at the same source. Grading
writes only its new ref. Neither route writes dataset `main`,
`pilot-grades-20260923` or old01 paths. Standalone publication retains its `main`
default; it cannot publish a ref-tagged retained snapshot through that default.

The approved result-validation/withholding implementation is byte-identical to
the base. Failed/stopped withheld outputs still retain only bounded metadata,
unchanged local artifact identities and partial/missing accounting; missing
results remain ungraded. Privacy, source, hash, byte, path, cleanup, no-clobber,
CAS and acknowledgment gates remain. Unacknowledged output cannot authorize a
terminal or next cell. Workflow inputs, permissions, concurrency, runtime/model
controls and fixed-grader pins did not change. HF tokens remain in short host
scopes, outside model/judge children. No coupled source pin required an update.

### Focused offline evidence

From `batch-runner/`, the new selector
`tests/test_codex_budget_pilot_epoch02.py` returned **34 passed, 1 failed in
80.16s**, exit 1, at `63afe729b9edab8c59f888fc86c4b4b642999b71`. The failed test
read the checksummed input envelope as a raw retention record, causing
`KeyError: files_sha256`. The test now uses the existing validating checkpoint
reader; production code did not change after that run.

Only the failed node,
`tests/test_codex_budget_pilot_epoch02.py::test_real_retention_predecessor_and_grading_cas_use_distinct_refs`,
was rerun at `d514d811374d80bb7e14ad051e10a21e402c5575`: **1 passed in 27.90s**,
exit 0. This is split evidence, not a fresh 35-case pass. Both invocations used
the existing Python 3.10.12 interpreter, a credential-free `env -i` environment,
HF offline defaults and private JUnit/log files. Pytest options were
`-q -o addopts= -p no:cacheprovider --tb=short`; finite timeout bounds were
600 seconds for the selector and 180 seconds for the failed node.

The compiler, checksum/byte checks, serialization, deadline, admission,
publication/CAS, terminal validation and grading binding/ref-CAS helpers are
real. Inputs/outputs, source/runtime capability, child execution and HF replies
are synthetic. Setup uses the installed SDK and real bounded HTTP guard with
fake responses. Grading-CAS tests do not establish native atomic installation,
judge readiness or a grade. The prior 25-pass withholding family was not rerun;
its original SHA/result remains below. Only completion records changed after
the failed-node test snapshot.

### Remaining authority and observations

New immutable-head review and CI remain. The leader must separately authorize
each live ref setup and bind its actual readback/bootstrap, one common final
execution SHA for all new 30 cells, and one selected cell before admission.
Checked live write/admission/publication, the first epoch02 cell, actual grading
host installation and one fixed grade, and complete new 30-cell results remain.
This task grants no live permission and does not reseal old01.

Dataset setup `35881609256` stays consumed. Old grading setup `35939410006`
remains acknowledged/branch_verified; original setup `35920355055` remains
unresolved/consumed. Earlier failed A1 dispatches `35941493214` and `35943806328`
remain separate from the admitted failure. Their detailed receipts, hashes and
partial costs below are unchanged. No live HF/model/grader/Azure operation,
payload transfer, workflow dispatch or CI polling occurred.

The full skill catalog was checked once. Experiment-design kept this a closed
replacement with unchanged axes and an explicit old1/new30 denominator.
Experiment-report-en and im-not-ai-en preserved the split test evidence, partial
cost and unknown-state limits. UI/animation and repo-readiness guidance did not
apply to this bounded internal routing/evidence change.

The sections below are historical records at their stated sources, not epoch02
execution authority.

## PROJECT5-FAILED-RETENTION-1339

### Future-code repair and frozen admitted cell

Added a retention-only opt-in for an already finalized failed/stopped cell whose
bound result is refused with the exact code `unsafe_result_fields`. It retains
only a bounded metadata manifest after all other validation passes. It does not
recover the admitted A1 or change its source, claim, clock, status or accounting.
One new offline selector returned **25 passed in 288.82s**, exit 0, at
`3276b32761579af86392909b6d472c9c7f8f604b`.

The branch starts from leader-supplied main and ACTIVE pilot source
`2fe1c6925e6d76c03b85851046d52216bee74a16`. The leader reported #670 review
`5299471328` and all **9 checks passed** for the preceding bootstrap/count
correction. That review does not cover this repair. The existing extreme-reasoner
returned **APPROVE-WITH-CONDITIONS, future-code implementation only**, before
the publication-path edits. No new-head approval, live recovery or reseal is
asserted here.

### Observed failure and evidence limits

The leader supplied A1 run `35954811341`, job `107490761123`, on that active
source. Real input intake, the full sandbox gate and private claim passed.
Execution exited **1 at 04:20:18 UTC**; retention exited **2** with
`unsafe_result_fields` at **04:20:21.6482243 UTC**. One paid child was admitted.
This is not another bootstrap, original-input or authentication diagnosis.

Verified public completion artifact `10789759614` has envelope SHA256
`570b0bc196a21efaa0a23123958a46d0ae2b2a52a16d19fb0661aae6d8b046e6`.
It reports `failed` / `child_nonzero_exit`, `timeout=false`,
`child_invocations=1`, `cleanup_confirmed=true`, `other_cells_not_run=29` and
`deliverables=[]`. Its partial receipt reports **55033 input tokens**,
**4387 output tokens**, **12544 cached-input tokens** and **3566 reasoning
tokens**. Known cost is **USD 0.175163**; the estimate is **null** and
`invoice_complete=false`. These are not invoice totals or request counts.

Only identities are available for the bound result and ledger:

- Result: **7460 bytes**, SHA256
  `c9313667c3890a1b4bc876d7bb771b41e430c2f595515c1a4bc0041e9fa1175b`.
- Ledger: **1838 bytes**, SHA256
  `116561470c73f4fbeae18a7db81c74947991e1b46f695411842f5bbd6153d93a`.

The raw bytes are unavailable here. Hashes neither preserve nor reconstruct
them. The child failure's precise cause and the unsafe field remain unknown.
The source trace confirms that `retain` calls `prepare` before
`TERMINAL_RESERVED`, the HF session and publication, so this retention invocation
published neither result nor terminal metadata. The refusal code is shared by
top-level, recursive and row/`failure_evidence` guards. The current remote claim
state is **not established**; no read or reconciliation was attempted.

### Guard-preserving behavior

Only retention opts into the new path. Standalone preparation/publication and
unsafe successful results still refuse. Eligibility requires failed/stopped
state, confirmed selected-cell cleanup and readable current result bytes matching
the recorded identity. Campaign/source/config/plan/host/input bindings, result
fingerprint and canonical identity, path/link/size limits, deliverable and ledger
bytes, and receipt/accounting checks remain mandatory. `_finish` rechecks a copy;
it never rewrites the original state. Recursive validation checks every branch's
depth before reporting unsafe fields, so an early field refusal cannot hide a
structure failure. No arbitrary exception or other refusal code gains a fallback.

The existing missing-payload path now also produces the withheld manifest:
`files=[]`, the existing missing-payload list, and exactly
`withheld={reason: unsafe_result_fields, artifacts: unchanged completion.artifacts}`.
The optional `withheld` field records local identities, not remote payload
availability. No rejected result, deliverable or ledger bytes are published.
The symmetric terminal validator requires exact fields, identities, failure
status, cleanup, empty published files and the existing bounds. Missing usage
remains missing; partial accounting, the execution reason and failed/ungraded
state are preserved. The public completion schema is unchanged.
Failed/stopped/missing outcomes remain in the 30-cell denominator.

Private-target and expected-parent checks, one-use reservations, CAS publication,
durable acknowledgment, remote-object checks and terminal confirmation remain
required. An unacknowledged output write cannot create a terminal record or
authorize advancement. Workflow, compiler, source pins, dependency/runtime pins,
model/budget/order controls and the fixed grader are unchanged.

### Single offline validation

Tested SHA: `3276b32761579af86392909b6d472c9c7f8f604b`.
Selector: `tests/test_codex_budget_pilot_failed_retention.py`.
Result: **25 passed in 288.82s**, exit 0. One invocation used the existing
Python 3.10.12 environment from `batch-runner/`; only the private JUnit path is
replaced below:

```bash
timeout --signal=TERM --kill-after=5s 300s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/results.xml tests/test_codex_budget_pilot_failed_retention.py
```

Private JUnit SHA256:
`af92c85b66dc61a3035090f6af56d25c0f5bdf5468e0d2ef875a173858301136`.
The cases use synthetic finalized outputs and the existing fake child/HF
boundaries with real JSON serialization, fingerprints, compiler, state/byte
checks, publisher/CAS and terminal validation. They cover failed/stopped field
variants, manifest-only publication without a private canary, unchanged files,
checkpoints and partial/missing accounting, safe success, unsafe-success and
standalone refusal, closed withheld identities/bounds, identity/source/path/byte/
cleanup/accounting/structure refusals, and lost-publication no-replay/no-advance.
Runtime/SDK admission and native execution are synthetic in the reused fixture;
this is not a native installation or live publication result. The cases do not
identify A1's lost field. No previous family or full suite was rerun. Only these
two completion records changed after the tested code/test snapshot.

### Required leader decision before any live use

The admitted A1 remains frozen at `2fe1c6925e6d76c03b85851046d52216bee74a16`.
Its unavailable raw files cannot satisfy the new byte checks. The reviewer
requires separate leader authorization for an exact reviewed future source and
a new campaign/source epoch with noncolliding claim/output identity and an
approved bootstrap/parent. Any paid execution also needs explicit authorization
and the common-source requirement. This patch implements neither epoch migration
nor settlement, adoption, replay, reconciliation or replacement of the old claim.
No clock is reset. New-head review/final CI, that source/epoch decision and any
separately authorized claim settlement remain before further live activity.
No next cell or grade is authorized. Complete 30-cell results remain unavailable.

Historical failed/consumed A1 runs `35941493214` (omitted input hash before
intake) and `35943806328` (accepted inputs, then missing `bwrap`) remain distinct;
those earlier runs admitted no paid cell. Dataset setup `35881609256` remains
consumed. Grading setup `35939410006`, job `107443765950`, was acknowledged /
`branch_verified` at **00:43:02.5104178 UTC**; original setup `35920355055` remains
**UNRESOLVED/CONSUMED**. None was replayed or changed. No HF API call, workflow
dispatch or CI query, model/grader request, Azure operation, original-payload
transfer or live claim operation occurred in this task. Git source/handoff
operations are separate from those live boundaries.

The full skill catalog was checked once. Experiment-design guidance preserved
the immutable-source/claim boundary and unchanged experimental axes.
Experiment-report-en and im-not-ai-en kept partial accounting, observed failure,
synthetic validation and unknown causes separate. UI skills and repo-readiness
were not applicable to this bounded code/evidence correction.

The sections below preserve earlier observations and their then-current limits;
they do not replace the active-source and admitted-cell status above.

## PROJECT5-BOOTSTRAP-COUNTS-1207

### Test-only correction and review scope

Updated only the three coupled expectations on the existing #670 branch,
starting at `9cee38e586c859c47be54fa7ef1bc1ed2110736c`:

- Setup routing now expects **10** excluded steps instead of **8** and explicitly
  includes the installation and full-capability steps.
- Output-target routing now expects **4** exact shared-admission matches instead
  of **2**, with the four intended step names fixed in the assertion.
- The three parameterized HF-originals failure-gate cases now expect the same
  **4** downstream steps instead of **2**, with exact names.

The shared predicates, setup exclusion, input-failure checks, prior-success
requirements and downstream admission/OIDC/retention assertions are unchanged.
There is no dynamic-count substitute, skip, xfail or helper framework. The
29-line workflow addition, capability helper, runtime/config/source pins and
`tests/test_codex_budget_pilot_bootstrap.py` remain byte-identical to the starting
head. No production change or new CI/cost review was needed.

The leader supplied source approval `5299044787` for that head's workflow/helper
scope and exact-head REQUEST-CHANGES `5299205667` for these test expectations.
Neither review approves this new delta. Main remains
`c463bc57139a484214264adc2a22c655cd33ca47`; no merge or reseal occurred.

### CI evidence and single local invocation

The leader reported eight applicable checks passing and pytest failing on the
starting head. Completed full CI run `35947002035`, job `107467086938`, recorded
**5 failed, 13763 passed, 61 skipped, 46 deselected in 2039.71s**. All five
reported failures were the three stale count assertions, including three HF
parameter cases. The CI-captured `hf_original_inaccessible`/403 belongs to a
synthetic negative-path fixture, not a new live HF or authentication failure.

Tested SHA: `629b3365c0621b070cddc6a9aae84a157ede2c14`.
The one permitted invocation used the existing Python 3.10.12 environment and
only these three selectors from `batch-runner/`:

```bash
timeout --signal=TERM --kill-after=5s 180s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/results.xml tests/test_codex_budget_pilot_output_setup.py::test_setup_workflow_routing_is_static_and_keeps_model_input_and_publication_closed tests/test_codex_budget_pilot_output_target.py::test_output_target_workflow_contract_is_static_not_an_actions_execution tests/test_codex_ci_hf_originals.py::test_hf_originals_actual_cli_failure_cannot_open_workflow_oidc_gate
```

Result: **2 passed, 3 errors in 1.96s**, exit 1. The two static workflow contracts
passed. The HF cases (`fetch`, `installed_check`, `None`) stopped before their
bodies ran: the existing `offline` fixture could not import `openai_codex`.
This is a local environment limitation, not an observed assertion regression
or HF call. Those three cases remain locally unvalidated. No dependency install,
test double replacement, assertion weakening or second invocation was attempted.
The private JUnit report has SHA256
`6e35511b5ad9dc6810076424573ac098acc1ec1a958ffe35aa108f41ecafe6bb`.
Only these two records changed after the tested snapshot.

### Preserved evidence and remaining gates

The original **11 passed in 0.99s** at
`771e79a56e1928d839dc50901b96011a91306fa9` remains a separate result; its
bootstrap selector was not rerun and is not combined with this invocation.
The failed/consumed A1 runs `35941493214` (omitted hash) and `35943806328`
(accepted originals, then unavailable `bwrap`) retain their histories below.
Acknowledged/`branch_verified` setup `35939410006` remains distinct from
unresolved/consumed original setup `35920355055`; no target or branch was replayed.
No paid cell has been admitted by these failed runs.

Remaining are new-head delta review, final CI including the three locally
unexecuted HF cases, explicit leader reseal and actual runner admission.
No CI query/rerun, full suite, live diagnostic, HF/model/grader call, Azure
management operation, permission change or paid action occurred. English
reporting/copyediting guidance kept the CI assertion failures, local fixture
errors and original bootstrap evidence separate. Experiment-design, repo-readiness
and UI/animation skills were not applicable: no experimental axis, new public
handoff or interface changed.

## PROJECT5-BUBBLEWRAP-BOOTSTRAP-1105

### Result and scope

Added the existing Ubuntu 22.04 bubblewrap bootstrap to the single-cell workflow
on a new clean branch from `c463bc57139a484214264adc2a22c655cd33ca47`.
One focused offline selector returned **11 passed in 0.99s**, exit 0. This
validates the workflow shell and failure routing with synthetic processes,
not an actual runner installation or native sandbox execution.

Only two workflow steps were added. After successful, verified execute-mode
intake, the first checks for `bwrap` and, if missing, uses the existing Ubuntu
`apt` package convention for one update/install sequence. It retains acquisition
retries and lock/network bounds, with 240/420-second command limits, five-second
kill grace periods and a 12-minute step ceiling; there is no outer retry loop.
The original `codex_bubblewrap_unavailable` prerequisite is unchanged. The second
step then runs the unchanged `scripts/diagnose_codex_sandbox_host.py` under a
two-minute ceiling before private claim, OIDC and inference. Only the helper's
successful full sandbox probe establishes readiness on that future runner.

Both added steps require successful prior steps, `execute=true`, all three
non-execution mode flags false and `steps.intake.outputs.verified == 'true'`.
Plan, input-only, output-metadata and setup routes skip this bootstrap. Neither
step receives HF/model credentials. Package, missing-binary and capability
failures propagate and block admission; no sandbox guard or host policy is
relaxed. The existing completion projection and token boundaries are unchanged.
No source binding needed an update, and the old #669 worktree was not changed.

### Confirmed live failure and preserved setup history

The leader supplied the following evidence; no run was queried or repeated here.
Corrected A1 run `35943806328`, job `107457243061`, attempt 1, used exact source
`c463bc57139a484214264adc2a22c655cd33ca47`. At
`2026-09-24T01:40:49.3370131Z`, explicitly selected HF originals were accepted
with `original_inputs_verified=true`: canonical archive **2519040 bytes**,
SHA256 `757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
Intake succeeded at 01:40:53 UTC. The next prerequisite ran `command -v bwrap`,
emitted `codex_bubblewrap_unavailable` and exited 1. Private claim, OIDC,
execution and retention were skipped. This establishes unavailable `bwrap` on
that runner path, not an auth, provider or quota failure.

Earlier run `35941493214` failed before intake because the leader omitted
`input_bundle_sha256`. That dispatch mistake is not a code defect. Both
failed/consumed run records remain unchanged; neither admitted a paid cell.
The successful input gate was not repeated.

The leader separately reported grading-branch setup `35939410006`, job
`107443765950`, as acknowledged/`branch_verified` at 00:43:02.5104178 UTC.
Original setup `35920355055`, job `107382432896`, remains
**UNRESOLVED/CONSUMED**, with the original `grading_contract_refused`, null HTTP
status, exit 2 and unknown side effects. The later acknowledgment does not
rewrite the original receipt. Neither setup, target or branch was recreated,
inspected or replayed, and dataset setup `35881609256` remains consumed.

### Focused offline validation

Tested SHA: `771e79a56e1928d839dc50901b96011a91306fa9`.
Result: **11 passed in 0.99s**, exit 0. One invocation from `batch-runner/`
with a private temporary JUnit destination:

```bash
timeout --signal=TERM --kill-after=5s 60s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/results.xml tests/test_codex_budget_pilot_bootstrap.py
```

The private report has SHA256
`c990c5797635d842ddc7abc10552248ae937fb2c5bb4a3516349028cfe977dde`.
The tests execute the actual extracted Bash with fake `sudo`/package and
capability processes on an isolated PATH. They cover an existing binary,
successful installation, update/install failures and simulated timeout exits,
a still-missing binary after nominal installation, and capability refusals.
Structural checks cover ordering, all mode combinations, verified-input and
prior-success gates, credential boundaries, and downstream refusal, including
retention's `always()` guard. No real claim, OIDC, model or retention command runs.
Only these completion records changed after the tested workflow/test snapshot.
No previous 64-, 29- or 12-case family, full suite, package installation, native
connection diagnostic, original-input check or live test was run.

### Review scope and remaining authorization

An existing extreme-reasoner context returned a bounded pre-edit
**APPROVE-WITH-CONDITIONS** decision for this bootstrap, requiring the single
bounded package sequence and existing capability gate. It is not approval of
this new head or authorization for a live operation. Experiment-design guidance
kept the correction outside the experimental axes; English reporting and
copyediting kept live, synthetic and unmeasured evidence separate.

The leader supplied complete review `5297993636` and ten passing checks for
prior #669 head `d21b5fa508657cd94b326ebaa3c50c15b2b7683c`. Those cover its
source-trust, closed-diagnostic and branch-inspection scope, not this addition.
The prior inspection result remains **29 passed in 4.67s** at
`2066971d10bcad322420fdadd89fa71d1511318c`, with synthetic HF/source boundaries
and static workflow checks. The historical 28-pass, 6-fail/939-pass comparison
and targeted 12-pass evidence remains separately recorded below.

Remaining are new-head review and CI, explicit leader reseal of one common
source for all 30 cells, and a newly authorized actual runner bootstrap,
capability check and first admission/execution with retention and one fixed
grade. No existing cell clock is reset. GPT-5.4/direct-v1/xhigh, SDK 0.147.0,
180-minute cumulative/30-minute attempt limits, A4 fresh attempts, B/C retained
state, C feedback, one inference slot and the fixed grader remain unchanged.
No live HF/model/grader request, Azure management operation, setup replay,
workflow dispatch/rerun, source reseal or paid action occurred. CI was not polled
or awaited.

## PROJECT5-RUNTIME-SOURCE-INDEPENDENCE-0730

### Result and live evidence boundary

Corrected the eager external-source lookup on the existing #669 branch,
starting at `2b64888cb422d7a5a9d0df847a063b8a84002b95`. One targeted offline
selector passed **12 tests in 17.92s** at
`3790e4d370f25700ea7a18d46233575135e4191b`, exit 0. Main remains the supplied
`02a9682747e371d8675d1d0afb63155f3c3bce82`; no integration or reseal was made.

The leader reported comparison CI `35926036972`, job `107401241366`, on the
starting head: **6 failed, 939 passed in 1294.77s**. The eager `_root(TRUSTED_ROOT)`
call introduced an external-source dependency into every runtime Git command.
It preempted the six tests that deliberately make the old compiler unavailable
after preparation. The new selector restores their original provider-boundary
and post-validation HEAD-move assertions without editing those tests. The
initial **28 passed in 29.37s** at
`13032a864a115c0150f944e18aa277a1e212e541` remains separate evidence; it did not
establish runtime independence. Neither the 28-case family nor the 945-case
comparison run or full suite was repeated, and CI was not queried.

This repair does **not** establish the cause or side effects of the original
live grading setup failure, current HF branch state, or paid-execution readiness.

The leader supplied this observation from run `35920355055`, job
`107382432896`, on sealed source `02a9682747e371d8675d1d0afb63155f3c3bce82`:

- Plan succeeded at `21:09:59.868579 UTC`.
- Setup refused at `21:10:01.622976 UTC`, exit 2, with these reported fields:

  ```json
  {"outcome":"refused","reason":"grading_contract_refused","http_status":null,"grade_success":false,"inference_requested":false,"automatic_retry":false}
  ```

- Judge and grade publication were skipped. The generic refusal does not show
  which contract stage failed or whether a branch was created before receipt
  persistence failed. This task did not read, retry or reconcile that operation.

The grading-branch setup reservation remains **UNRESOLVED/CONSUMED**. The
leader's execution seal remains **BLOCKED_PRE_EXECUTION**, not replaced by this
branch or its tested SHA. Dataset setup `35881609256` and private bootstrap
`bfc7ae01ed14490817ceb7cb406adcb9bb95f557` remain valid and consumed; neither
setup may be replayed.

### Runtime independence and historical ownership mechanism

The supplied runtime contract is unchanged: once preparation has completed,
runtime lineage uses only the selected checkout's reviewed HEAD/tree, config,
input and receipt bindings. It must not call the external-source verifier or
require the old compiler directory to exist. The corrected `_git` validates
the actual command repository with `_root`, then uses `Path(TRUSTED_ROOT)` only
for lexical comparison. On mismatch it performs no `stat`, `resolve`, open,
existence check or `_root` call against the unrelated path and adds no trust
allowance. On exact equality it validates that trusted path before adding the
single exact `safe.directory` option. There is no fallback trust on failure.

All six runtime test nodes and their assertions remain byte-for-byte unchanged.
The r1/r2 cases reach the expected synthetic `ProviderBoundary`; the two
`head_moves` cases reach the injected move after real bundle validation and
then refuse at the intended lineage gate. The directly affected new trust test
also refuses foreign ownership with existing, missing and aliased comparison
roots. The unsafe-path test now selects its unsafe path as the command
repository; its no-Git assertion remains. No missing external directory was
created and no runtime fixture was redirected to the original compiler.

The original ownership reproduction remains a separate historical observation:

The grading entry's source-check path is `grade-run.yml`'s containerized `pilot-live` job, then
`codex_budget_pilot_grading.main`, `LocalTransport.require_source`, and
`gpt54_disposable_checkout._repository` / `_git`. The workflow installs an exact
global `safe.directory` entry. The helper deliberately uses
`GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_SYSTEM=/dev/null`, so that entry
cannot affect its commands.

A bounded pre-edit reproduction used real Git 2.34.1, synthetic temporary
repositories and Git's process-local `GIT_TEST_ASSUME_DIFFERENT_OWNER=1` switch.
It changed no filesystem ownership or real-repository permissions. Ordinary
Git with the exact isolated global allowance returned 0; the original hardened
helper returned 128 with a locally detected dubious-ownership refusal. An exact
command-local allowance returned 0; a foreign allowance remained refused at
128. The reproduction command exited 0. Raw stderr and temporary paths remain
private. This proves the compatibility mechanism locally, not that it was the
unreported stage in job `107382432896`.

Only exact lexical equality followed by trusted-path validation permits one
command-local `-c safe.directory=<canonical checkout>`; the same validated
command repository is passed to `-C`. Selected symlink/traversal roots and
wildcard/control-bearing trusted paths remain refused. No sibling, ancestor,
common-directory, wildcard, environment-selected or globally trusted path is
added. The ownership test switch exists only in test child processes, never
production configuration.

The fixed Git executable, stripped environment, global/system isolation,
hooks/fsmonitor/attributes protections, filter/include/partial-clone refusals,
no-lazy-transport policy, timeout and captured/redacted errors remain intact.
Source SHA, clean worktree, object type, tree paths/modes, manifest and pinned
blob checks are unchanged. The prior 28-case selector covered a synthetic
shallow clean commit without ancestor traversal; that case was not rerun.
No workflow or fetch-depth change was justified or made.
`require_source` still does not call `require_pinned_runtime`; no Python,
dependency or runtime-configuration change was made.

The only source-pin adjustment is the checkout helper's SHA256 in
`batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`:

- Previous #669 helper: `de40ae571d66635f121d2ca538f30114125c2fbf12e679db854c4ae46d6b9862`.
- Corrected helper: `0dbbab8911e1cba106745087aed471dca0a8b7f904058b4958df1e07864bb885`.

The genuine compiler validates that coupling. No fixed-grader source/hash
closure, model, prompt, rubric, judge policy, grading branch, inference-main
isolation, budget or 30-cell order changed.

### Unchanged CLI diagnostics and mutation limits

The source/root/receipt diagnostics introduced in the initial correction are
unchanged. Their original 28-case evidence is not a new CLI rerun. The real CLI
keeps refusal/exit 2 and these fixed local mappings:

| Boundary | `stage` | `reason` | `remote_mutation_possible` |
|---|---|---|---|
| Compile and validate reviewed source | `source_preflight` | `grading_source_preflight_refused` | `false` |
| Prepare private setup root and enter its lock | `branch_root` | `grading_root_refused` | `false` |
| Persist the final private setup receipt | `branch_receipt` | `grading_receipt_refused` | `true` |

For these local failures, HTTP status is null; grade success, inference request
and automatic retry remain false. The mutation flag describes **this invocation
only**: false does not prove an absent branch or unused reservation from an
earlier invocation; true is conservative, not proof of a mutation. Unrelated
outer failures retain their existing typed reason/HTTP context, or generic
`grading_contract_refused`, with stage and mutation possibility null. No raw Git
stderr, path, config value, token or arbitrary exception text is emitted.

Root/lock failure leaves any partial local state intact. Receipt failure after
a fake branch mutation preserves the real private local reservation and refuses
another invocation against that root before another fake session/mutation. The
initial selector included both an acknowledged fake creation and a lost fake response.
Neither case reconstructs the historical receipt or authorizes a live retry.

### Focused offline validation

Tested SHA: `3790e4d370f25700ea7a18d46233575135e4191b`.
Result: **12 passed in 17.92s**, exit 0. One invocation from `batch-runner/`
selected only the six reported runtime nodes and six directly affected
exact-trust/foreign-owner/unsafe-path cases. The private JUnit destination was
required to be absent before running:

```bash
timeout --signal=TERM --kill-after=5s 300s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -o junit_family=legacy -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/runtime-independence-results.xml \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-r1]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-r1]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-r2]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-r2]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-head_moves]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-head_moves]' \
  tests/test_codex_budget_pilot_grading_source.py::test_real_git_global_trust_is_ignored_but_exact_command_trust_works \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[symlink]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[traversal]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[wildcard]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[newline]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[control]'
```

Compiler and source-pin checks, temporary Git, preparation/runtime lineage,
bundle/receipt validation, repeated HEAD checks and path/ownership refusals are
real. Input fixtures and provider boundaries are synthetic. The four r1/r2
passes mean the intended intercepted provider boundary was reached, not that
auth or a model was called. Both head-movement tests prove the deliberately
changed HEAD is refused after the real validation hook, not before it.
No HF, model, grader, branch mutation, full-suite, native-install or live test
ran. The JUnit report remains private; only the two completion records change
after this tested source snapshot.

### Review scope and remaining gates

The same extreme-reasoner returned **APPROVE-WITH-CONDITIONS** before this
bounded Git-trust correction, clarifying the existing decision: validate an
actual command repository, but do not validate an unrelated compiler path merely
to select a trust allowance or require it to exist at runtime.
That memo covers the design, not approval of the resulting head. No new audit
loop was started. English reporting/copyediting guidance keeps the initial
28-pass result, supplied six CI failures, new 12-pass selector and original
unresolved live refusal separate. No current-head approval is claimed.

Prior #668 review `5296511923` and all ten passing checks apply to
`d97d250cfc1a6f2f6ad485d9bb44a8fa58d79227`, not this correction. Historical
results remain **64 passed in 47.42s** at
`f352eb87af8c794a677629229884f37061342535` and **5 passed in 3.20s** at
`f210a789e2a0afa889fd5261858fcbc0b402327f`; neither selector was repeated.
Accepted-input run `35847871634` and consumed dataset setup `35881609256` remain
separate observations, not paid-cell results or grades. The prior local native
atomic-install `EINVAL` refusal and successful rename-test-double cases do not
establish actual CI grading-host capability.

Remaining: leader review/final exact-head CI; separately authorized, checked
read-only reconciliation of the unresolved grading branch; an explicit source
reseal and live gates; actual grading-host native installation; the first paid
cell with retained output, one fixed grade, and all 30 recorded outcomes. There
was no real HF credential/API/read/write, branch creation, setup replay, payload
transfer, workflow dispatch, grant change, Azure/model/grader operation or CI
query/wait in this task. The original reservation and blocked seal are unchanged.
