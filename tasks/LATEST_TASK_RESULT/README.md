# Latest task result

## #794 subprocess-wait and retention-hash CI repair, 2026-10-30

Backend Tests run 41056682245 failed for two different reasons. The intake
workflow test hit CPython's bounded wait after pipe EOF but before waitpid
reported child exit; the fixture's global sleep denial incorrectly caught that
stdlib wait. Keep the five-second timeout and all global process/provider/sleep
refusals, restoring a real wait primitive only inside subprocess's namespace
for the explicitly allowed local shell. The three existing workflow cases now
force that race. A new timeout case verifies the child is reaped and arbitrary
processes/controller sleeps remain refused.

The retention test still expected the workflow bytes from before #794's one
core-ignore/one pilot-selection change. Check the new option-stripped hash
`46ba0b8f…5eb8e` and also reconstruct the unchanged old `7bd20c54…34068` hash by
removing exactly those two arguments. All actual tmp_path lifetime, exact argv,
single-option and 45-minute job assertions remain. The workflow itself remains
`75e6db77…ac65`; other current/historical hash guards, sealed sources and paid
policies are unchanged. No new skip, xfail or narrowed test selection.

Local reproduction: both exact CI assertions failed before the fix. Focused
full modules (intake, retention, partition, GHCP workflow pin, successor seal):
**237 passed / 0 failed / 0 skipped**. The pytest job's additional repo-root
script suite: **186 passed / 0 failed / 0 skipped**.
Both complete workflow selections were run without additional deselection:
core **13,817 passed / 115 failed / 117 skipped**, with the workflow's 47
integration deselections; time-budget **494 passed / 1 failed / 0 skipped**.
Those are the original full-run outcomes, not an all-green local claim.

Rechecking all 115 failed core nodes with corrected local tool/cache/temp
settings passed 30. Installing the declared PyAV dependency in an isolated
test environment passed the two remaining media cases. These 32 failures came
from local setup (missing sbin/cache lookup, long Unix-socket paths, missing
media dependencies), not changes to assertions. Remaining core cases are 82
NAS runner-admission refusals and the source-only test's deliberate clean-Git
requirement while this fix was uncommitted. Its clean-head recheck is recorded
after committing, in the external handoff. The time-budget failure is the
unchanged real-kernel positive: this NAS lacks /proc children and pidfd_open
(ENOSYS); it reached no provider or generation. The original failed CI intake
and retention tests pass in the complete runs. Existing host-capability/data
skips were retained; no skip or xfail was added to make this repair pass.

A separate, explicitly fake-client-only audio diagnostic passed all 14 cases
with the existing synthetic hosted-runner fixture, confirming the distinction;
it does not replace the unmodified full-job outcomes or prove NAS eligibility.
Commands, JUnit, all original failures and rechecks are under
`/ai-work/copilot/_tmp/p794-two-ci-jobs-20261030.jRg9EU/`.
No live model/judge call, dispatch, force operation or merge. The normal branch
push lets the unchanged Actions jobs perform the genuine hosted validation.

## Successor grader contract CI ownership repair, 2026-10-30

Run 41043462482's core job already passed the 21 successor-seal test cases,
but the family partition guard still expected 20 gpt56 files. The new file
was not explicitly owned by pilot-contracts. Add one core ignore and one
pilot selection; the inventory is now 21 total / 19 general pilot files.
Keep full node collection, disjoint coverage and exact commands. Four negative
ownership mutations are refused. Undoing just those two workflow arguments
recovers the preceding a2e0e2fe byte hash; the older canonical workflow hash,
historical GHCP pin, grader seal, source profiles and paid policies are intact.
Local partition guard, successor seal and dependent workflow-pin contracts:
**154 passed / 0 failed / 0 skipped**. New CI follows the normal branch push;
no model/judge call, dispatch, force push, Draft release or merge.
Evidence: `/ai-work/copilot/_tmp/p5-grader-ci-partition-20261030.icNe56/`.

## #794 follows merged pricing and long context, 2026-10-30

Rebase onto `c6fcacaf1` after #795/#796. The active source chain is
`capture_counters → list_prices → long_context → grader_seal`; the new last
edge only changes the reader pin and approved grader identity. Both predecessor
profiles and Claude's pricing/usage/catalog/response implementations remain
byte-identical to main. The 099755b0 grader seal and 1a5841ee historical review
manifest remain unchanged because the sealed closure did not change.

The original manifest's refusal-policy statement describes its 0140b4c12
review, not a rollback of owner decisions 2/3. Today's USD 200/integrity stops,
list-price/unknown-usage accounting, held 1M catalog and not_reported behavior
follow the merged, separately pinned helpers. Retain the old published PR head
as an ancestry-only parent so publication can use a normal push after rebase.
No paid/NAS benchmark, model/judge call, dispatch, PR merge or #793 operation.
Current rebase verification: **520 distinct passed / 0 failed / 0 skipped**
(36 source/seal/catalog, 286 policy/guard, 198 preflight; 143 deselected).
One earlier synthetic worker timeout remains in its original log; the same
test passed alone and in the full policy rerun without code/assertion changes.
The real source-held-reference preflight verifies the source and successor
seal, with valid configuration, but intentionally returns exit 2 and leaves
launch false with ten upper-evidence blockers. Final clean-head proof and
publication metadata: `/ai-work/copilot/_tmp/p5-grader-chain-20261030.vZvOhP/HANDOFF.md`.
The following test totals are the original review, not a new execution claim.

## Owner-reviewed successor grader seal, 2026-10-30

Owner option A authorizes the reviewed `8ac891e3e` → `0140b4c12` successor,
not a settings or refusal-policy change. Preserve the old `47effd1d…000fcf`
seal; separately register `099755b0…003fd7` and all old/new source bytes.
The delta is 11 files (9 modified, 2 added), classified conservatively as
6 admission/input/score-path impacts and 5 outside the pilot's score path.
The new source profile changes only the reader pin and grader-template hash.
Sol/Max, prompt v2.2, rubric, five task IDs and combined USD 200 remain fixed.

Full selected pilot-contracts/grading/source-proof invocation: **3,670 passed,
13 failed, 0 skipped** (5702.66s). All failures were two existing scripted-test
files lacking synthetic runner facts; the real guard correctly refused NAS.
Add only the existing fake hosted-runner fixture and explicit network denial
to those tests, leaving production and assertions unchanged. The complete
grader/USD/runner/seal recheck then passed **869 / 0 failed / 0 skipped**
(111.38s). Preflight: **198 passed / 0 failed / 0 skipped** (1111.95s), with
143 external-live cases excluded by the CI selection. Latest result per unique
testcase across these XML files: **3,881 passed / 0 failed / 0 skipped**, without
double-counting reruns. Earlier failures are retained separately. Three
synthetic reply cases agree old/new on requests, verdicts, denominators, scores
and summary JSON; four scoring/judging functions also have identical ASTs. See
[review and evidence boundaries](../../batch-runner/docs/gpt56_grader_successor_seal_20261030.md).
Logs/JUnit: `/ai-work/copilot/_tmp/p5-grader-seal-20261030.dX3prg/`.
No model/judge call, dispatch, secret access or merge. Claude's pricing/1M
changes and PR #793 are untouched and can require another reviewed seal.

## Historical source-bound fixture separation, 2026-10-29

CI at `9087c2c6e` found additional exact historical dependency pins and fixture
origin assumptions. Restore the budget-output helper to its sealed bytes as
well; all three historical readers remain unchanged. Old-study unit transports
explicitly use the historical input envelope, while current-format output must
still be refused by that reader. No saved record is stripped or rewritten.
Grading fixtures use the identical executor code with their checked synthetic
controller source origin; current-tree reuse is explicitly tested as refused.
New pilot receipt/admission behavior and every original seal/cap remain intact.
Related tests and final CI are still pending for this follow-up.

## Preserve the historical reader seal, 2026-10-29

The retention follow-up reached **209 passed / 1 failed / 1 skipped**; its
remaining failure correctly rejected changes to two frozen historical readers.
Restore those exact files, keeping their old metadata boundary and immutable
digests. The generic budget-pilot output reader retains the new validated
runner receipt; the wrong-hash/wrong-stage cases remain enforced. Do not refresh
the historical reader seal or treat it as accepting new-format results.

## Retention receipt compatibility follow-up, 2026-10-29

The clean integrated suite at `74a03d7ea` passed **1,110 tests**, no failures or
skips, in 173.25s. Further old-CI log review found a real metadata compatibility
defect: the three retention readers reprojected Step2 observability without
its new optional runner receipt. Preserve that input through the existing
hash/stage validator and exact equality check; never strip or accept unchecked
fields. Add wrong-stage/digest cases. Historical transport fixtures get explicit
synthetic runner facts, not permission to run on NAS or the legacy 22.04 host.
Related regression rerun and final full CI remain pending at this source commit.

## Queued PR integration and paid-diagnostic preparation, 2026-10-29

Under the owner's PR/CI and paid-run instructions, #785 is merged; the
publication candidate incorporates the reviewed heads of #786–#788 for a
combined CI check. No paid workflow runs on a push or PR. GHCP authentication
is still absent by metadata-only inspection and is not substituted or created.

Hosted sandbox proof 40924442821 succeeded with zero model calls. The Sol
diagnostic now requests/fingerprints Max and 1,000,000 context, and writes a
no-clobber USD 7.20 conservative full-attempt reference reservation before
authentication. It remains separate from the five-task ledger and explicitly
requires reconciliation before pilot progression. Actual tariff/served fields
are not inferred. Prior seals, USD 200 and the five task IDs remain unchanged.
Final integration tests/CI and paid dispatch are pending at this source commit.

## Native CI repair and hosted proof, 2026-10-29

PR #785 merged as `0a15af39b3dddb8275a82be0b609303c4bdc570d` under the
owner's instruction to handle the queued PRs. PR #789 remains in CI repair.
Model-free Actions 40924442821 at `62b29f343` passed both bubblewrap and
the pinned Codex 0.147.0 sandbox marker on hosted Ubuntu 24.04, image
20261026.354.1. The targeted AppArmor profile was added; the system-wide
userns restriction stayed enabled. This is host readiness, not a model result.

Preserve per-shard grading runner evidence, register the reviewed source-only
successor, and isolate historical test sources without weakening refusals.
The successor has 58 matching pins, eight changed from the unchanged response
capture predecessor; all non-source settings are identical. USD 200, fixed
five tasks and original grader/source seals remain unchanged. Current source
registration and expanded regression checks run after this commit, so no
passing final-head result is claimed here. No paid dispatch/model call yet.

## Native pilot publication and Actions preparation, 2026-10-29

The owner now approves publication/CI and paid execution of the existing
Foundry Sol five-task pilot, within the unchanged USD 200 combined ceiling.
Pushed reviewed head `271093150` and opened Draft PR #789. Add a model-free,
secret-free hosted Ubuntu 24.04 sandbox-readiness check and port the already
verified pytest 9.2 worktree fixture repair. Original source/grader seals and
fail-closed execution gates remain in force. No model execution is claimed.
Related workflow/host/fixture checks: **198 passed, 0 failures/errors/skips**,
24.02 seconds; broader PR CI repair is still in progress.
See [current progress and measurement boundaries](../../batch-runner/docs/native_pilot_actions_progress_20261029.md).

## Native runner/migration fixed-HEAD review, 2026-10-29

Review `3f31968e5` and `ff7ab8efb` above `cf1401e1c` on the same local
`leader/runner-receipt-20261029` branch. Six loopback-only cases reproduced one
admission gap: waiting, body preparation or connection setup could outlive the
first runner check. Recheck before request reservation and before HTTP
headers/body, and retain the actual environment refusal in the receipt.
Already-spent connection/USD reservations remain conservative. Grading stops
remain control signals, not `judge_error` or reduced denominators.

Two disappearing sandbox-state fixtures keep ENOENT/ESRCH fail-closed; the
native process scan already handles disappearance. Correct exact historical
workflow/Step8/runner source-pin expectations, and make the synthetic native
handoff test prove sealing before its deliberately missing wire receipt.
Immutable sources/seals, prices, USD 200, model/limits and scoring are unchanged.

Final validation completed 33 full modules in three disjoint offline groups:
**305 + 161 + 1,892 = 2,358 passed / 0 failures/errors/skips**; one integration
case excluded. Complete JUnit/module/unique-ID checking exited 0. Two temporary
shell wrappers exited 2 after pytest completed because their running script
had been edited; the paired reproduction and complete test outcomes are kept
separate in the [review report](../../batch-runner/docs/native_runner_receipt_20261029.md).
The interrupted initial run and preliminary expectation failures are retained
separately, never pooled into the total. Evidence:
`/ai-work/copilot/_tmp/native-runner-review-20261029.inlxfD/`.

Latest fetched main `6efe99cbd40bb839037e7a20711a734e0a4ce002` is an ancestor
of the reviewed head: no conflict at that snapshot. No rebase, merge, B push,
PR, dispatch, secret-value query, model or Azure call. The PR body stays
uncommitted under `batch-runner/workspace/review-drafts/`; publication approval,
source re-registration, grader-seal decision and actual hosted sandbox proof
remain outstanding.

## Native Ubuntu 24.04 migration, 2026-10-29

On local `leader/runner-receipt-20261029`, based on `3f31968e5`, migrate the
connection diagnostic and Codex-only batch runner from 22.04 to explicit
GitHub-hosted 24.04. The admission rule rejects hosted 22.04; the independently
approved Azure VM rule is preserved. No native model/grade request, credential
lookup, Azure call, dispatch, push or PR was performed for this branch.

Before Azure credentials, require the pinned runtime and root-owned system
bwrap; if needed, add only its fixed AppArmor `userns` profile. Never clear a
sysctl, overwrite a profile or select a weaker sandbox backend. Both the full
bwrap namespace probe and the pinned CLI sandbox's exact local command marker
must pass. Missing dependencies, invalid runner metadata, failed/timed-out
probes, drift or an unwritable receipt stop before model calls. Reports keep
runner evidence and bounded nonsecret probe facts, not raw child output.

One final related invocation: **428 passed / 0 failed/errors/skipped**, **22.02s**,
exit **0**. Includes new denial/marker fixtures and existing grader parity,
host/receipt, diagnostic, model-control-byte and workspace contracts. The
development 48-pass run and later 16/1-failure runs are preserved separately,
not pooled. New-file tracking and synthetic test environment setup were fixed;
no assertion or production refusal was weakened.

The historical host observations are unchanged; the new prepared condition is
explicitly **not yet measured on Actions**. AppArmor attachment and pinned-CLI
compatibility need a model-free hosted check after publication approval.
Existing sealed plans/caps/prices/schema files remain unchanged; source review
and registration remain required, not bypassed. See the
[file inventory, sources and design boundary](../../batch-runner/docs/native_ubuntu24_migration_20261029.md).
Logs/JUnit: `/tmp/p5-native-ubuntu24.zLRltk/verified.{log,xml}`.

## Native runner admission and receipts, 2026-10-29

On `leader/runner-receipt-20261029`, based on `cf1401e1c`, bind diagnostic,
native inference and Step8 grading to observed GitHub-hosted Ubuntu metadata
or explicit direct-Azure-VM approval markers plus matching local DMI identity.
Missing/conflicting metadata refuses before model transmission; native HTTP
and grader/perception/retry requests recheck the admitted observation. Grading
host refusals stop the run rather than becoming a reduced-denominator verdict.
Runner evidence includes image/OS/architecture, run ID/attempt and a canonical
SHA256. The registered native handoff requires that same evidence **before**
its private-result hash is sealed; Step2 and grade outputs retain it.

Completed, disjoint offline checks: **1,151 + 7 + 8 = 1,166 passed**, **0 failed/
errors/skipped**. The 1,151-case direct-related suite ran once after final fixes
in **184.46s**; the real fixed-five handoff/missing/tampered evidence cases passed
7 in **295.80s**; representative native continuation/content-filter cases passed
8 in **39.29s**. These are three invocations, not one combined run. The expanded
1,476-case attempt timed out at 900 seconds and is **not** a full green result;
other interrupted/development failures are retained, not counted as passes.

Existing cost/grade schema files and all sealed plans/caps/price records remain
unchanged. New evidence is `native-runner-evidence-v1`; old records are not
retrospectively verified. Active source-profile mismatches increase from one
at the base to seven, and the new helper needs a reviewed source pin. Grader
source identity also changes: follow-up registration/seal review is required,
not bypassed. Ubuntu 22.04-to-24.04 migration and pilot Actions wiring are not
part of this change. Evidence is local metadata, not remote attestation.

No model, credential-value lookup, token issuance, Azure request, dispatch,
push or PR for this branch. SDK/CLI 0.147.0 types came from an existing isolated
environment; no CLI was launched. Evidence and detailed invocation history:
`/tmp/p5-native-runner-receipt.6RBA4c/`. The interrupted synthetic workspace was
moved there intact; test-only tmpfs storage was emptied, and its optional fixture
override was removed from the final changes. See
[runner admission](../../batch-runner/docs/native_runner_receipt_20261029.md).

## Grader USD guard: repair schema scope without turning money into marks

On local branch `leader/grader-guard-scope-20261028`, based on
`7c7a637967a0f2af4e5482d98d205a1d2ceeedf8`, fix two boundaries rather than remove
the required combined inference-plus-grading USD 200 admission. A Responses
function tool's parameters are JSON Schema, so its nullable `scope.type` is
validated as schema and still fully counted in the request reservation. Opaque
runtime input/overrides, missing output limits, invalid/external schemas,
unknown usage, hidden retries and over-budget requests remain fail-closed.

Typed money refusals now cross provider/judge retries as run control, not a
`judge_error`. Step8 exits 4 with the original grading reason, flushes metering
receipts, closes the judge and preserves only already completed tasks as partial.
The interrupted task contributes no manufactured verdict or reduced denominator.
Scoring/rubric/prompt code, frozen registrations, price table and caps are unchanged.

One final related offline invocation passed **598 tests, 0 failures/errors/skips**,
exit **0**, **88.98s** pytest / **88.961s** JUnit. It includes a comparison against
actual frozen Git source `8ac891e3e0e4752fe15a00139a2691ddf9df7dce`: under the same
fixed fake response, synthetic tariff and clock, the guarded request/grade/summary
matches the frozen output. This is not a real Sol or five-task score experiment.
Preliminary red/CLI-fixture/interrupted runs are retained separately, not pooled.

The original caps worktree remains clean at `7c7a637967a0`; no model, token/login,
dispatch, paid execution, push or PR. This local code fix does not renew any seal,
clear the pilot's existing source/evidence gates or grant launch authority.
See [scope and verification](../../batch-runner/docs/gpt56_grader_guard_scope.md)
and `/tmp/p5-grader-guard-fix.yWSNpq/` for exact logs/JUnit and the handoff.

## Native pilot: response capture ready; live proof and ten blockers remain

Prospective Sol connection diagnostics and the pilot now share response-side
capture: redacted body/headers in exclusive artifacts, SHA256 and fixed
model/version/effort/context fields in receipts. Missing fields are
`not_reported`, never copied from the request or SDK settings. Missing/mismatched
model, required Max/1M fields or safe storage prevent CLI response delivery and
`connected`; a failed pilot receipt also blocks subsequent tasks/retries.
The existing deadline can close sockets/SDK while an artifact writer is stalled;
late writes cannot revive success. No server-capability or billing claim follows.

At `7b2cd13d6ae23a7f65f4f481636976da436a1e42`, one related offline invocation
passed **618 cases, 0 failures/errors/skips**, exit **0**, **700.09s** pytest /
**700.676s** wrapper. This includes the previous 379-case selection, 188 diagnostic
contracts, 47 response fixtures and four new session gates, not separately pooled
proofs. The prior 617-case pass preceded a separately reproduced stalled-write
failure; its fix and new regression are included in the final 618. Synthetic
HTTP/SDK/process fixtures are not real model, integration or full-project tests.

Plan-only at the tested HEAD reaches `source_verified → inspect_plan`,
**exit 2 / 3.151s**, **0 newly cleared / 10 retained / 0 new** blockers.
Only the next-call capture readiness for model/version and Max/1M changed.
All 58 source pins match; the new helper, diagnostic and artifact workflow
also enter held reviewed-blob checks. The previous connection registration,
original run 39407062120 / artifact 12257312458, USD 200 combined ceiling,
native caps, prices and frozen grader pin remain unchanged. No model/smoke,
authentication/management call, dispatch, push, PR, merge or new finite right.

See the [response contract, changed files and ten-blocker report](../../batch-runner/docs/gpt56_native_response_capture.md).
Exact commands, logs, JUnit, timings and final-HEAD preflight are retained in
`/tmp/p5-native-response.tz5Zd7/`. The historical results below stay separate.

## Native pilot: approved target bound; ten launch requirements remain

Run **39407062120** / artifact **12257312458** is now linked to the approved
configured account/deployment/host through a pinned nonsecret reference. The
actual runtime target must match it before observer/SDK effects; attempt and
ready receipts carry the reference, and admission/final checks reject drift.
Existing resource-file byte checks remain; direct-v1 needs no child-project ID.
This closes configured-route selection only, not a fresh management or served
model fact. See the [binding, public prices and eleven-item status report](../../batch-runner/docs/gpt56_native_retained_identity_and_pricing.md).

The original diagnostic's exact members still match their hashes. Runtime and
served model are `null`; version and reasoning effort are not retained. The
**258400** app-server window and SDK-reported **9444 input / 5 output** are not
Max/1M proof or billing. No raw Responses HTTP body is retained. The diagnostic
did not request the pilot Max/Long overrides.

Unauthenticated public Retail API lookup found Standard Global Sol prices in
eastus2, USD per 1M tokens: Short input/cached/write/output **4 / 0.4 / 5 / 20**;
Long **8 / 0.8 / 10 / 30**, effective **2026-09-01**, retrieved **2026-10-27**.
The applicable short/long rule and provider cache-write mapping remain
unverified. Prices and the `usd_price_contract_unverified` grading refusal are
unchanged; no effective rate was guessed. The approved combined ceiling stays
**USD 200**, not a verified billing guarantee.

Code is fixed at `6c907d789bed4628d46173c72e27f92f8e15a68c`. One related offline
invocation reports **379 passed, 0 failed/errors/skipped**, **638.81s** pytest /
**639.388s** wrapper, exit **0**. This includes **24** new connection cases and
targeted existing contracts, not the full project or an integration/provider
suite. Synthetic route fixtures are not real target/capability proof. The
preliminary 24-case pass and its earlier fixture-setup error remain separate.
The explicit source/reference plan-only check reaches
`source_verified` / `inspect_plan`, **exit 2 / 3.314s**, with
**1 cleared / 10 retained / 0 new** blockers and launch disabled. All **58**
source pins match; only binding/wire/preflight pins change in a new successor,
and the exact reference is additionally held against reviewed Git blobs.

Evidence: `/tmp/p5-native-identity.MpFccK/`. The prior USD 200 proof below is
historical and is not pooled into this result. This turn used public pricing
GETs and local work only: no model/Azure management call, credential lookup,
paid grade, dispatch, push, PR, merge or new study/retry right.

## Five-task native pilot: owner-approved USD 200 combined ceiling

The owner's **2026-10-27 10:56 KST** card decision (**01:56Z**) sets the same
five-task inference-plus-grading ceiling to **USD 200**. It supersedes the
**2026-10-26 23:09Z USD 1,000** decision; no further amount approval was requested.
This is an offline cap change, not a launch, paid grade, billing reconciliation
or new attempt/study right. The earlier records and cost proposal below are
dated history and do not supply the current allowance.

The named [monetary companion](../../batch-runner/experiments/execution_envelope/gpt56_sol_native_usd_cap_20261027.yaml)
now carries `cost.approved_maximum_usd: 200`, the local/UTC decision timestamps,
and the superseded record's exact commit/path/hash. Its new SHA256 is
`a0f67d8845a165fd660c7600dbb3c233d07f9008e7efb44edb4054e3070cb9c6`.
The old companion bytes remain at commit
`32c79f6774a9b4620c9fbf77f9756e32c30f6c0b` with SHA256
`df64cdb0d1e1f242b7500debbca2ca5dac0eab988783e2a03da80c57a940992f`.
All sealed registrations, native caps, prices, grader configuration and the
cost proposal remain byte-identical. The companion's native-estimate policy
sub-block is retained; the shared runtime receipt records connected grading.

Native admission, the persistent common ledger, receipt validation and the
preflight amount report now agree on **USD 200**. `usd_ceiling_exceeded` still
refuses before either inference or grading is forwarded and records its origin.
Missing/partial usage consumes its reservation and blocks later requests.
An old-cap ledger/receipt is refused without replacing its files or refilling
money/attempt rights; no automatic migration or budget reset is added.

The [source-only successor](../../batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261027_usd200.yaml)
preserves **58 registered roles** and all non-source plan values. It adds held
checks of the sealed shared-USD predecessor and updates only the wire/preflight
pins plus the already-held monetary/helper hashes. The inherited plan null is
historical; active admission reads the approved companion. A bounded grep of
active code/new profile finds **zero** old amount literals. The companion's
only `1000` is `supersedes_monetary_decision.previous_value`, not an allowance.
Historical source profiles, old reports and the explicitly superseded-decision
test retain their old facts; context size **1,000,000** is not a dollar cap.
A wider check of pilot modules, metering and Steps 2/8 finds only nine remaining
`1000` literals used to convert seconds and milliseconds, not monetary limits.

### Reservation amounts and five-task simulation

Reservation rules were not reduced. Native input **300,000**, output **10,000**,
request counts, **1,800 seconds**, cache policy, retries and every existing
unknown-usage/unpriced-model refusal remain unchanged.

| Request fixture | Input reserve | Output reserve | Cache-write reserve | Total USD reserved |
| --- | ---: | ---: | ---: | ---: |
| First native request in a full-allowance attempt | 300,000 x $10/M = $3.00 | 10,000 x $45/M = $0.45 | 300,000 x $12.50/M = $3.75 | **$7.20** |
| Maximum admitted visible-text grading fixture; frozen output field | 1,048,576 UTF-8 bytes x $10/M = $10.48576 | 2,400 x $45/M = $0.108 | 1,048,576 x $12.50/M = $13.10720 | **$23.70096** |

The second row uses the current guard's **1 MiB** serialized request limit and
the unchanged grader's **2,400** output field, not a measured grading prompt.
Real grading reservations vary with bytes and the explicit output limit.
Bytes are a client estimate, not a verified Sol tokenizer/server bound.
Rates **10/45/12.50 USD/M** are explicit synthetic fixtures using the stored
reference numbers; the real Sol table remains deliberately unpriced.
See the actual [request allowance/admission](../../batch-runner/gpt56_pilot_usd_budget.py#L476)
and [frozen judge settings](../../batch-runner/grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml#L283).

The card reports **$0.06–$0.99 per solving attempt** and **$2–$6 per graded task**.
No per-task raw usage or request sizes accompany those ranges. The tests replay
their endpoints as synthetic settled USD against the exact five registered task
IDs; they do not invent provider tokens or claim to reverify those measurements.
There are **16 scenarios**: low/high endpoints, one/four solving attempts,
one/two synthetic grading calls per task, and zero/1.25 extra write factor.
Four attempts means the existing initial plus three infrastructure retry slots,
not permission to retry; grading-call counts are fixture choices, not actual
grade call counts. The extra write factor is conditional on one write per
uncached input token at the stated reference rates, not an observed/proven maximum.

| Five-task scenario | Settled USD without extra writes | With conditional 1.25x IO write reserve |
| --- | ---: | ---: |
| One solving attempt per task | **$10.30–$34.95** | **$23.175–$78.6375** |
| All four allowed attempt slots per task | **$11.20–$49.80** | **$25.20–$112.05** |

All 16 scenarios finish below **$200** with no monetary refusal. The largest
**settled plus pending** exposure is **$129.00096**. The largest sum of
reservations over time is **$381.00960**, which is not simultaneous spend: after
complete settlement, unused reservation is released. Missing usage never
receives that release. A small final bill alone cannot establish that every
future request shape will fit; media/opaque requests and hidden retries remain
refused, and the fixture does not establish a runnable real grade.

The separate maximum-consumption stress fills all **20** native attempt slots
at **$7.20**, consuming **$144**. Two full grading fixtures then reach
**$191.40192**. The **third grading request** is refused before reservation:
its **$23.70096** would reach **$215.10288**. The reason remains
`usd_ceiling_exceeded`, origin `grading`. This is a demonstrated worst-case
stop, not a claim that the card's normal reported amounts would stop there.

### Remaining requirements, not eleven failed tests

Plan-only at the tested code reports `source_verified` then `inspect_plan`,
configuration valid, **exit 2 / 1.964s**, launch false and **0 cleared / 11 retained /
0 new** blockers. This call supplies no runtime/evidence/input bundles; retaining
a requirement is not proof that its artifact is unavailable elsewhere. The
separate price refusal below overlaps the tariff requirement; it is not a
twelfth preflight blocker. Classification distinguishes free local assembly
from an owner decision about evidence/proposed execution; approval cannot make
an unverified provider fact true.

| Requirement | What this invocation lacks | Free local work / owner or external dependency |
| --- | --- | --- |
| Grading price refusal, `usd_price_contract_unverified` | Exact applicable Sol tier/zone/write contract; table deliberately refuses it. | Free validation of supplied facts; **owner/external evidence needed** to bind the applicable tariff. Do not select a speculative price or edit the table here. |
| `foundry_account_project_deployment_identity_unverified` | Fresh approved account/deployment/host identity bundle bound to this source. | **Free assembly possible** from approved retained evidence; owner supplies/authorizes the record if absent. `direct-v1` does not require a child-project ID. |
| `foundry_served_model_version_unverified` | Actual served model/version evidence, not the requested label. | **Owner execution/evidence decision needed**; existing valid receipts could be checked free. No new call in this task. |
| `max_and_long_1m_capability_unverified` | Evidence that Max/Long 1M was supported/applied, not just configured. | Free document/receipt validation; **owner/external capability or execution evidence needed**. Approval alone is not proof. |
| `native_call_and_token_limits_unresolved` | Complete native/server-token limit contract and qualifying observed usage. | Free contract investigation remains possible; **owner/external contract or execution evidence needed** for complete closure. Client estimates are not server bounds. |
| `prepared_input_bytes_unverified` | Verified local parquet/reference/input bundle for these five tasks. | **Free assembly possible**, conditional on the approved local inputs and upstream bundles; no download or model call here. |
| `live_inference_identity_and_wire_unverified` | A real session-owned inference/wire receipt. | **Owner execution decision needed**; fixtures and saved unsigned claims cannot supply the live witness. |
| `pilot_dispatch_and_grading_identity_not_wired` | Accepted reviewed source/grader identity and its compiled bundle. | Free compilation is implemented; **owner review/decision needed** for the frozen grader source mismatch. No repinning or merge authority here. |
| `foundry_usage_and_tariff_mapping_unverified` | Provider usage mapped to the applicable tariff/cache meters. | Free reconciliation of supplied records; **owner/provider evidence needed**, not an assumed bill from the synthetic prices. |
| `native_sandbox_and_result_bundle_host_unverified` | Session-owned host/workspace/result evidence tied to actual inference. | **Owner execution decision needed** for the real witness; local cleanup fixtures do not prove the live host. |
| `actual_pilot_deployment_not_prepared` | Verified inert runtime/config/deployment binding for the chosen account/deployment. | **Free assembly possible** after approved upstream identity/config/input bundles; not Azure deployment creation or a new child-project request. |
| `prepared_request_capture_unverified` | Exact local prepared-request capture linked to the preceding bundles. | **Free assembly possible** once those local inputs and bindings are supplied; it still does not prove model consumption. |

These are the existing [preflight requirements](../../batch-runner/gpt56_sol_codex_pilot_preflight.py#L244),
with [direct-account project omission](../../batch-runner/gpt56_sol_codex_pilot_preflight.py#L883)
and [price refusal](../../batch-runner/gpt56_pilot_usd_budget.py#L429) preserved.
The frozen grader hash mismatch is still refused, not approved by this amount
change. No new monetary decision is needed: the current approved amount is $200.

### Offline proof and limits

Start `32c79f6774a9b4620c9fbf77f9756e32c30f6c0b`; fixed code
`5b3c25885fd9e4debbdd9c4f0ff6b3e5d1047838`, tree
`0fbb902953b8b0d6cd33dd7be1d27496dde39685`. Evidence is in
`/tmp/p5-native-usd200.8MGVKz/`, including exact selectors, logs, JUnit/timings,
simulation properties, source/protected hashes and the old decision bytes.

| Final group at the fixed code | Result | Pytest / wrapper seconds; exit |
| --- | --- | --- |
| Native, source registration and USD 200 scenarios | **296 passed, 0 failed/errors/skipped** | **109.20 / 109.869; 0** |
| Existing grading/metering/receipt regressions | **383 passed, 0 failed/errors/skipped** | **43.10 / 43.494; 0** |
| Wire/preflight contracts | **282 passed, 0 failed/errors/skipped** | **1446.23 / 1446.652; 0** |

Final aggregate is **961 passed, 0 failed/errors/skipped**, with disjoint JUnit
identities. The previous **943** cases are preserved after seven parameter-name
translations for the new currency boundary; **18** new USD 200 cases are added.
The contract selector retains the previous **214 deselections**; no
full-project-suite claim. The preliminary **104 passed**
(`83.75 / 84.154s`, exit 0) and old **943-test** proof are separate, not pooled.
Price/usage ambiguity still fails closed. Actual tariff, server token bounds,
cache accounting, non-model/service/tax charges and filesystem rollback remain
unverified; actual billing flags remain false. Reports distinguish modelled USD
from bills under the experimental-reporting/copyediting checks. No model/Azure
call, paid grade, dispatch, push, PR or merge occurred.

The following records are historical snapshots; their earlier USD 1,000
allowance and source identifiers are superseded by the decision above.
## Five-task native pilot: shared persistent USD admission

Inference and grading now use one durable reservation ledger for the owner's
**USD 1,000 combined ceiling**, approved **2026-10-26 23:09Z**. This is prospective
client-side admission, not a reconciled bill or a pilot execution result.
**Actual Sol grading is still refused before task inputs, authentication or
client construction because its price contract is deliberately unpriced.**
No current pricing, server-token or cache-billing guarantee is inferred.

### Actual call boundaries

| Origin | Bound runtime entrypoint | Admission behavior |
| --- | --- | --- |
| Inference | `PilotWireReceiptSession` / `_NativeRequestBudget.reserve_priced` | Reserve remaining attempt input allowance, outgoing output maximum and the existing modelled cache-write allowance before the loopback constructs an upstream connection. |
| Grading | Step 8 `main` / `open_grading_admission` / `CostRecorder` / `MeteredClient._around` | Require exact configured-model prices and the inference-bound financial file; reserve before invoking the judge/perception/retry wrapper's provider call. |

The new `gpt56_pilot_usd_budget.py` uses SQLite transactions under the verified
capture workspace, `.pilot-usd-budget/ledger.sqlite3`. Its identity file binds
the run, capture digest, ordered five tasks, cap/price hashes, amount and unique
ledger identity. A grading process must reopen that existing identity via
`--pilot-usd-workspace`; it cannot initialize its own fresh allowance.
Atomic reservations share the same USD 1,000 across both origins. Complete
usage settles once. SDK cumulative usage is a floor, not another charge.

Unknown, partial, failed or mismatched usage consumes the reservation and
blocks future admission. Dead owners' pending reservations are consumed on
reopen; a pending close also preserves the held amount. Neither restoration
from an old cost receipt nor repeated settlement refills the budget. The
financial state can outlive a process, but this grants no native live-session
adoption, new study right or automatic resumption of a spent attempt.
Same-host retained files are required; cross-host recovery and restoring older
valid filesystem snapshots are not protected by this mechanism.

`usd_ceiling_exceeded` records the originating inference/grading side. Other
fixed reasons are `usd_usage_unverified`, `usd_reservation_exceeded`,
`usd_price_contract_unverified` and `usd_ledger_unverified`. The native socket/SDK
cleanup and previous request/token/deadline guards remain. Amounts finer than
the existing **1e-8 USD** receipt precision are refused rather than rounded into
the cap. Grading rejects hidden SDK retries at wrapping and before each call;
it also refuses missing output limits, opaque/media/streaming requests and
body overrides. These are refusals, not new verified live capabilities.

The exact stored table still lists `azure:gpt-5.6-sol` as deliberately unpriced.
Grading cannot substitute the native long-context reference scenario or a
nearby model's rate. Tests use explicitly synthetic priced fixtures; they do
not alter the real price table. The separate historical audit ledger still
reserves audit rows, while the new common ledger reserves monetary amounts.

The persistent receipt adds `runtime_caps.usd_ceiling.shared_budget`, showing
known modelled amounts, pending/consumed-unknown reserves and both origins.
`grading_included=true` means admission is wired, not that a paid grade passed.
`grading_usd` is a known modelled subtotal, not a complete bill; unknown amounts
remain separately reserved. `actual_total_pilot_usd` stays null and both
effective-tariff/actual-billing-hard-limit flags stay false. Native cache-write
allowances and grading's visible UTF-8 byte estimate are not provider/token
theorems. Non-model runtime/service/tax charges remain outside this guarantee.

### Source and completed evidence

This worktree/branch started clean at
`5906f24e0cd520c37099ff5e4b42ce95c55c6ee3`. The fixed implementation HEAD is
`979082af62c5a546e95cd7a15d4531e479165006`, tree
`e0585f6711f1baa56284c6aed263691ba33bd043`. No other checkout was modified.
The [source-only successor](../../batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261027_shared_usd.yaml)
preserves **58 registered roles** and all non-source plan values; it updates
wire/preflight/Step 8 pins and holds the actual shared-budget/metering modules
as auxiliary reviewed blobs. Step 8 additionally checks the imported helper's
actual file and includes it in the pilot grader's existing source closure.
The frozen grader configuration, prompts and grading algorithm are not changed.
Its old source mismatch remains a refusal, not a newly approved judge hash.

Evidence: `/tmp/p5-native-shared-usd.nrwZrl/`. Existing Python **3.10.12** and SDK
**0.147.0**, synthetic inputs/replies, loopback-only fake providers and harmless
child processes only. Verification clears the environment, disables online
Hub/dataset access, bytecode, pytest plugin autoload/cache and Git lazy fetch.
Native/contract commands use **TERM1800s/KILL5s**; grading uses **TERM600s/KILL5s**.
These are verification bounds, not changed execution limits.

| Group at the fixed code | Result | Pytest / wrapper seconds; exit |
| --- | --- | --- |
| Native, source-registration and shared amount fixtures | **278 passed, 0 failed/errors/skipped** | **65.61 / 66.243; 0** |
| Existing grading/metering/receipt regressions | **383 passed, 0 failed/errors/skipped** | **34.70 / 35.122; 0** |
| Wire receipt and preflight contracts | **282 passed, 0 failed/errors/skipped** | **1468.01 / 1468.438; 0** |

Final JUnit reconciliation: **943 passed, 0 failed/errors/skipped**, with disjoint
case identities across the three groups. All **506** original case identities
are present in these fresh results. The contract selector retains the previous
**214 deselections** (`native_result_host` / `external_live_receipt`); this is not
a full-project-suite claim. The earlier **506-test** proof remains historical,
not pooled into these runs.
`validation-commands.md` records exact selectors/environment/bounds; `final-*`
files retain stdout, JUnit and timings. `diagnostic-results.md` separately keeps
the early **35-pass** selector, stale-current-hash **1-failure**, earlier **383-pass**
and **276-pass** runs, and the contract **84 passed / 1 failed** stale drift-list
expectation. Exact expectations were updated without weakening any refusal.

`validated-preflight.*` at this code reaches `source_verified`/`inspect_plan`,
configuration valid, **exit 2 / 1.915s**, launch false and **0 cleared / 11 retained /
0 new** blockers. It reports connected grading admission AND unverified grading
prices. The original owner companion and all old caps/registrations/price/grader
records remain byte-identical; its old enforcement fields are historical.
`protected.sha256` and the final code manifest bind those boundaries.

No model/Azure call, smoke, five-task run, grading service, token issuance,
dispatch, push, PR or merge occurred. All finite rights remain unchanged.
The [cost report](../../batch-runner/docs/gpt56_native_pilot_cost_ceiling_proposal.md)
retains the conditional **$799.20** scenario and separates approval, estimates
and actual billing under the experimental-reporting/copyediting checks.

The following records are historical snapshots, including the earlier
inference-only implementation; their old disconnection status is not current.
## Five-task native pilot: approved USD 1,000 and inference estimate guard

The owner's desk message **2026-10-26 23:09Z**, "총비용 상한 1000", selects
**USD 1,000 for the five-task inference-plus-grading total**. The amount is now
recorded in the pinned [monetary companion](../../batch-runner/experiments/execution_envelope/gpt56_sol_native_usd_cap_20261027.yaml),
`cost.approved_maximum_usd: 1000`. The old sealed plans/caps retain their
historical nulls byte-for-byte. This offline change grants no launch or retry
right. **Actual combined-bill enforcement is not established.**

### Implemented scope

The existing wire session owns one in-process USD estimate ledger shared across
tasks and permitted attempts. Before constructing an upstream connection, it
atomically reserves the remaining attempt input allowance, outgoing
`max_output_tokens`, and one full-input cache-write reserve. It reads pinned
Standard Global long reference prices from `model_price_table.json`:
**$10 input / $45 output / $12.50 cache write per million tokens**, without a
cached-read discount. These are stored reference prices, not a verified tariff.

Complete provider usage settles once; SDK cumulative usage is a floor, not an
extra sum. Missing/partial/failed or unpriceable usage retains reservations and
blocks later admission. Fixed stop codes are `usd_ceiling_exceeded`,
`usd_usage_unverified`, `usd_reservation_exceeded` and
`usd_price_contract_unverified`. The existing socket/SDK cleanup, native/token/
deadline guards and retry allowlists remain. Unknown monetary usage now blocks
the session even when an infrastructure retry would otherwise be eligible.
No persisted-ledger adoption, refill or resume API is added.

`provider_observation.runtime_caps.usd_ceiling` records estimated costs,
reservations and remaining modeled USD. Unobserved cache writes remain null;
their separate reserve is not billed usage or a proven provider maximum.
`effective_tariff_verified=false`, `actual_billing_hard_limit_verified=false`,
`grading_included=false`, `grading_usd=null` and `actual_total_pilot_usd=null`.
The existing `token_hard_limit_enforced=false` boundary is unchanged.

Grading was investigated only: [Step 8](../../batch-runner/step8_grade.py#L2817)
has a separate persistent ledger, and its [meter](../../batch-runner/core/cost_metering.py#L921)
reserves an audit row before a call and settles usage afterward. It has no
shared USD-amount admission owner with this wire session. Combining receipts
afterward cannot prevent incurred charges; integrating every grading/perception/
runtime charge requires a common atomic owner. No grader code or price table changed.

### Source identity and completed offline proof

Worktree `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`,
branch `codex/gpt56-native-pilot-caps-20261024`, started clean at
`36cc47af5f5b8feb147063a61e53b3ad4cc1fb9d`. Tested code is
`01001d4448eba62e254d7a6ae570222cdbc673a2`, tree
`18eeb71f3f05add86068bb138bb467399945ac7a`. Later reporting edits do not change
tested executable/profile bytes. No other worktree or branch was modified.

The new [source-only profile](../../batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261027_usd_cap.yaml)
keeps **58 registered roles** and refreshes the wire/preflight pins. Its held
auxiliary records include the monetary companion, existing price table and
predecessor profile. Admission/final rereads also compare returned local bytes
with the immutable Git blob; no hash/refusal check is weakened. `tested-code.sha256`
and `protected.sha256` in the evidence directory bind changed and preserved files.

Evidence: `/tmp/p5-native-usd-cap.1hIeAd/`. Existing Python **3.10.12** and SDK
**0.147.0**, synthetic inputs/loopback responses and harmless SDK child processes
only. Commands use **env -i / TERM1800s/KILL5s**, offline Hub/dataset flags, no
pytest plugin autoload/cache, no bytecode writes and no Git lazy fetch.

| Completed group at the tested code | Actual result | Pytest / wrapper seconds; exit |
| --- | --- | --- |
| Native, source-registration, caps and new USD fixtures | **224 passed, 0 failed/errors/skipped** | **55.14 / 55.727; 0** |
| Wire receipt and preflight contracts | **282 passed, 0 failed/errors/skipped; 214 deselected** | **1447.58 / 1448.003; 0** |

The JUnit identity sets are disjoint: **506 unique passed tests** preserve all
**469 historical cases**, plus **33 USD** and **4 cleanup-reason** cases. These
are two completed related bundles, not a pooled live experiment or full-suite
claim. Host/external-live-receipt selectors remain excluded. Exact invocations,
stdout, JUnit and timings are in `confirmed-native.*`/`confirmed-contracts.*`.

Earlier diagnostics are retained separately in `initial-validation-status.md`:
**29 passed** before four added cases; **1 failed** returned-byte drift test;
an intentionally stopped contract run (**exit 143**); then **128 passed / 1 failed**
because the new model check masked an existing token-limit reason; and a
**14-pass** targeted cleanup regression. Fixes strengthened byte binding and
restored refusal precedence. No assertions were weakened or failed runs pooled.

### Plan-only and remaining conditions

At the tested code, `tested-preflight.*` records explicit
`source_plan_snapshot(expected_plan_sha256=seal(plan), reviewed_source_sha=...)`
then `inspect_plan(loaded)` under **env -i / TERM120s/KILL5s**. It reaches
`source_verified` and `inspect_plan`, **configuration_valid=true**, no configuration
problems, **launch_allowed=false**, **exit 2 / 1.691s**. The report includes the
approved USD 1,000 companion; the launch-blocker list remains **0 cleared /
11 retained / 0 new**. Exit 2 is the intentional plan-only non-launch result.

The amount decision is closed, but effective tariff, cache-write accounting,
server token bounds and combined grading admission remain open. No model,
smoke, five-task run, grading, token issuance, dispatch, push, PR or merge ran.
All previous finite rights, frozen grader and source seals remain unchanged.
The [cost report](../../batch-runner/docs/gpt56_native_pilot_cost_ceiling_proposal.md)
preserves $799.20 as a conditional stress scenario, not an actual or guaranteed bill.
`experiment-report-en`/`im-not-ai-en` keep approval, estimates, observed usage,
unknown billing and the separate failed/interrupted diagnostics distinct.

The following sections preserve historical results and the amount status before
this approval; their old null/proposal wording is not the current decision.

## Five-task native pilot: owner USD-ceiling proposal

At clean source `abb883c95f008331697db79132c62b13c294e8ef`, prepare the
[cost-ceiling proposal](../../batch-runner/docs/gpt56_native_pilot_cost_ceiling_proposal.md)
without changing code, registrations, caps, judge, host, model or permissions.
Only that document, this record and CHANGELOG change; local commit only, no push.

Registered arithmetic is **5 × (1 + 3) = 20 attempt slots**, each with
**300,000 input / 10,000 output tokens**, totalling **6,000,000 / 200,000**.
There are **five grading passes**, not five judge calls or twenty grading passes.
The committed Azure Standard Global Sol meters give a no-write solver allowance
of **$36.00 short / $69.00 long**; the applicable live tariff is still unbound.
Using the larger of two explicitly quoted historical per-task grading high
endpoints, **$58.24**, is a proposal premise, not a proven future upper bound.
Five such allocations give **$291.20**, for a combined **$360.20** before writes.

The separate one-write-per-uncached-token stress assumption adds **$75.00** for
solving and **$364.00** for grading, producing **$799.20** conditionally.
Owner-choice ceilings are **$800 / $1,000 / $1,200**, not approved amounts.
Unknown extras remain `U`; **no finite all-in worst-case bill is established**.
`approved_maximum_usd` and the tariff-evidence hash remain **null**. No future
grade is guaranteed to fit the historical allocation; no cap is operationalized.

Run **39407062120** supplies the separate connection-shaped reference of
**9,444 input / 5 output**, served model **null**. Applying stored rates gives
**$0.047370–$0.094665**, not an invoice or task forecast. No artifact was fetched
or replayed. The prior **469-test** proof below remains unchanged and was not rerun.

Evidence: `/tmp/p5-native-cost-proposal.Php740/`. The first arithmetic selector
also matched a non-cost verification row and asserted; its status is retained.
Selecting the exact two per-task cost rows preserved the value assertions and
the final Decimal checks passed. This is arithmetic validation, not pytest.
Protected-source hashes and documentation scope are checked. No model call,
grading, source edit, private input preparation, dispatch or new paid right.

## Native pilot client token precheck

The owner's **2026-10-26 23:40 KST** local implementation direction is complete
at the tested code below. The loopback refuses a request before upstream
connection/reservation when its input estimate or output field exceeds the
remaining allowance, or the required evidence is unknown. **Server hard-token
enforcement remains unverified.** This is not a pilot execution result.

### Behavior and limits

- Input remains **300,000 tokens per attempt**. The estimate is the outgoing
  JSON's UTF-8 byte length, at one estimated token per byte. It is not a Sol
  tokenizer, measured usage or a proven token upper bound. Opaque/remote state,
  images/files, encrypted reasoning and hosted tools are refused; valid live
  Codex requests may therefore be refused. Requests over **1 MiB** are not
  inspected. Existing **256-KiB** response inspection and **64-KiB** chunks stay.
- Output remains **10,000 tokens per attempt**. Supported `/responses` JSON
  receives the remaining `max_output_tokens` if absent. Existing values above
  the remainder, invalid/ambiguous fields and `/responses/compact` are refused.
  No value is silently clamped and no maximum of zero is sent.
- Requests are serialized. Complete response input/output totals are summed
  once; cumulative SDK totals are a floor, not an extra sum. Missing, partial,
  failed or conflicting usage/completion leaves the next allowance unknown.
  Later SDK totals cannot reopen that state. Existing reported-overage stops
  and owned SDK/socket cleanup remain; late refusals cannot alter closed receipts.
- `runtime_caps.client_token_precheck` records enabled/check counts, the named
  estimator, accounted usage, remaining allowances and last request limits.
  Unknown usage/remainders are null. `token_hard_limit_enforced` and
  `server_hard_limit_verified` both remain **false**. No private body is published.

The [contract](../../batch-runner/docs/gpt56_native_hard_token_contract.md)
gives fixed refusal codes and preserves the previous server-contract findings.
Native request caps **32 per attempt / 128 per task / 640 per pilot** and the **1,800-second** attempt deadline
are unchanged. So are monetary-cap null, model/host/judge identity, QA,
dependencies, workflows, retry allowlists and all earlier sealed registrations.

### Source identity

Worktree `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`,
branch `codex/gpt56-native-pilot-caps-20261024`, started clean at
`ef7181a740b385745726950940c6aa3200621c82` (tree
`6a3efa3a1ec4b57b9135249ff5060929b1973f07`). Only this worktree was edited.

| Role | Identity |
| --- | --- |
| Tested code HEAD | `48632cd7c0b687051816b53723592e43de4831e2` |
| Tested tree | `53fadeb30cd68f983dc5626eebbdec85b79e30f9` |
| New source profile | `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261026_token_precheck.yaml` |
| Profile bytes SHA256 | `fbabe0aa40f6513bc77d86a29ae9ac9af35cfbd64b5b70fe3f6150aa0a6e1a44` |
| Canonical plan seal | `40db69bb3a26252fe4fa7ebe01b07f8ee448ee4fa0de809316ee165349213add` |
| Sealed bindings predecessor SHA256 | `740ec085c047ad359b4c5e56a8bf5867ebc2cb6c229d479262d6815fbe8154cf` |

The source-only successor changes the wire/preflight pins, with every non-source
field unchanged. All **58** registered source hashes match. The predecessor is
held/rechecked alongside the earlier seals; its old CLI selection still refuses.
The runtime changes are in `gpt56_pilot_wire_receipt.py`; the source selector is
in `gpt56_sol_codex_pilot_preflight.py`. Four test files cover the new behavior
and existing contracts. Final documentation-only HEAD/tree are returned in the
handoff; `verified-code.sha256` checks unchanged tested executable/profile bytes.
This is not independent owner review or CI approval.

### Offline verification

Evidence: `/tmp/p5-native-token-precheck.E4mVGq/`. The existing Python **3.10.12**
environment and SDK **0.147.0** were used. Upstream HTTP was loopback-only,
responses/inputs were synthetic, and SDK cleanup used harmless child processes.
The real Codex CLI, model, credentials and grading services were not invoked.
Each command cleared the environment and disabled online Hub/dataset access,
bytecode writes, pytest plugin autoload/cache and Git lazy fetch. No install.

| Completed group at the tested HEAD | Result | Pytest / wrapper seconds; exit |
| --- | --- | --- |
| Source registration, token precheck, provider observation, remaining caps and caps draft | **187 passed, 0 failed/errors/skipped** | **112.64 / 113.284424; 0** |
| Wire receipt and plan-preflight contracts | **282 passed, 0 failed/errors/skipped; 214 deselected** | **1438.81 / 1439.264116; 0** |

Both groups used **TERM1800s/KILL5s** verification bounds, not changed pilot
limits. Their source files match and JUnit case identities are disjoint:
**469 unique passed tests**, not a pooled model experiment. Host/external-live-
receipt selections were excluded; no full-suite or live compatibility claim.
`verified-native.*` and `verified-contracts.*` retain exact invocations, source
HEAD/tree, stdout, JUnit and timing. The new module includes all five requested
scenarios plus format, concurrency, non-egress and closed-receipt regressions.

Earlier attempts remain separate:

| Evidence prefix and source | Actual outcome |
| --- | --- |
| `test`, code `2710db3b5999f79ea3ca8165145c39f9eca5b64d` | **exit 124 / 600.017692s**; no final pytest summary or JUnit. Collection had selected 461/675 nodes. |
| `final-test`, code `ad43facccf5b36f1805831e1897f33fc596da694` | **exit 124 / 1200.013353s**; no final pytest summary or JUnit. The filename is historical, not a final-pass claim. |
| `close-race-before`, runtime code `ad43facccf5b36f1805831e1897f33fc596da694` plus the retained new-test diff | **1 failed**, pytest **2.37s**, wrapper **2.798549s**, exit **1**: a late refusal changed the already-closed blocked count from 0 to 1. Fixed in the tested HEAD; its regression passed in the 187-test group. |

The **76,803-byte** `tested-code.patch` has SHA256
`a77ebcd8b3974f57bbd9b47613094a7ebbc8506a1384aa5a265a8267832a845e`.
`verified-code.sha256` and `proof.sha256` bind sources and retained evidence.
Earlier **34-pass**, **6002-pass** and schema-only proofs remain in the
[immutable preceding record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ef7181a740b385745726950940c6aa3200621c82/tasks/LATEST_TASK_RESULT/README.md),
not in the new totals. The prior server-contract section remains unchanged.

### Plan-only result and remaining conditions

`verified-preflight.invocation.txt` records the explicit new profile and tested
40-hex source, under **env -i / TERM120s/KILL5s**. It reached `source_verified`
and `inspect_plan`: **configuration_valid=true**, no configuration problems,
**launch_allowed=false**, **exit 2 / 1.710567s**. All eleven original launch
blockers remain: **0 cleared / 11 retained / 0 new**. Exit 2 is the intentional
non-launch result, not a failed source/plan check. No identity/input/capture,
model capability, provider limit, usage-price or sandbox evidence is inferred.

The [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
supports the generic `max_output_tokens` description, including reasoning
output. The retained **1,101,821-byte** page has SHA256
`ddea039b39d8d48cae34cc1460127949856f08e751fe307a0104c94aa07f40d5`.
It does not establish a model/version-bound Foundry hard-limit contract.
The earlier reference 403 and size-limit refusal are not supporting evidence.

Final-source review/CI, environment approval and separately authorized live
evidence remain required. Input-estimator error, live Codex payload compatibility
and actual server enforcement are unmeasured. The frozen-grader source refusal
is unchanged, not a new twelfth blocker. `direct-v1` does not require a child-
project ID. Task3 run `37756891578` remains uncertain, spent and nonretryable.
No finite right was consumed/reset; no model, Azure/auth/management call,
dispatch, grading, push, PR or user-checkout edit occurred. Public documentation
GETs and loopback fixtures are not zero network activity.

`openai-docs` supported the generic-field documentation check;
`experiment-report-en` and `im-not-ai-en` preserve measurement units, source
identities, failed/interrupted evidence and server-unknown limits. No experiment
redesign or UI/animation work applies. Existing Git identity and no-trailer
policy are preserved. Reporting review is not runtime or publication approval.

## Task4 time-budget guard alignment

Scope: repair the two stale guards reported in PR #786's backend CI run
`40015357524`, job `120625917401`, after baseline
`88d757fd9ed3b3f23dac700246b13d64f901712c`. Work is confined to the designated
`task4-control-reader-publish-20261023` worktree on
`leader/task4-control-reader-20261023`.

Update only the owned-host comparison inventory expectation from 12 to 13 and
the retention guard's exact workflow hash (after removing its one retention
option) to
`58ecfccbacc6a887780b821692d07b8e03bf6eac120b703ffdf1d9bab600a3a4`.
Uniqueness, exact reconstruction, retention behavior and all other assertions
remain intact. No workflow or production code changed.

Verification: searched tests for the old hash, `== 12` and backend workflow
hash references. In `batch-runner`, ran `python3 -m pytest -m "not integration"
-q tests/test_time_budget_owned_host_ci.py
tests/test_time_budget_tmp_path_retention.py
tests/test_a_test_file_nobody_runs_is_not_a_test.py
tests/test_ghcp_vm_gate_contract.py`: **172 passed in 42.21s**.
The first run reported **171 passed, 1 failed** because the partition guard's
child collection lacked `openai_codex`. The passing rerun used temporary
worktree-local installations of repository-pinned `openai-codex==0.147.0`
and `openai-codex-cli-bin==0.147.0` on `PYTHONPATH`.

Reviewed head SHA: no review gate or reviewed head supplied for this test-only
follow-up; the baseline is not review approval.
Remaining work: new PR CI and owner review. No merge, manual workflow dispatch,
experiment run, model/grader call or private Task4 read was performed. Records
stop at pre-merge facts.

## Codex Foundry five-category evidence closeout, 2026-10-24

### Scope and outcome

Local-only, documentation-only follow-up to
`d8b91893071ed06ccd711acce8d9c019d9b66ed6`, on the same branch
`investigate/foundry-task5-remaining-20261024`, in
`/ai-work/copilot/gdpval-realworks/_tmp_worktrees/foundry-task5-remaining-20261024`.
No model call, dispatch, grading, remote read, push or Project update occurred.

Added an eight-row audit to the same
[diagnostic report](../codex_budget_pilot/RETENTION_DIAGNOSTIC_REPORT.md).
For each of the six failures and two successes, rate limit, communication
failure, timeout, output-length limit and content filter are **not recorded**:
none is identifiable from accessible retained evidence. Successful completion
does not rule out recovered events. All six failed terminal details and all
eight budget receipts retain their missing-cause fields; no cause is guessed
from exit code, waits, resumes, remaining time or source classifier capability.
The report names the discriminating provider reason, transport/timeout log or
attempt history needed for each category and each cell.

Inspected the committed per-cell controls, receipts, snapshots, report provenance
and historical source record, and checked this report worktree and repository
workspace for matching raw job artifacts. Historical sibling-worktree inspection
was denied by the non-interactive access boundary. Their contents are not claimed
absent or inspected; the conclusion is bounded to accessible retained evidence.

**Criterion verdict: closed with limitation**, not a successful empirical
five-way classification. The previous per-condition measurement and C/B
feedback-effect conclusions remain inconclusive; no execution is pending and
no further paid work is authorized.

### Verification

After the report edit, the same existing offline selector passed:
**1 passed in 2.65s**, exit 0, under TERM120s/KILL5s:

```sh
env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
  GIT_NO_LAZY_FETCH=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  timeout --signal=TERM --kill-after=5s 120s python3 -m pytest \
  -q -p no:cacheprovider batch-runner/tests/test_codex_retention_budget_report.py
```

The selector's process/network/constructor guards and zero-effects assertion
passed; no old lifecycle, inference, reader or grading selector ran.
A standard-library evidence-preservation check passed all eight new table
run/outcome/exit bindings and missing-cause fields. Removing only the new audit
section restores the entire prior report byte for byte. The readout, original
pilot and root README are byte-identical to the parent:

| Evidence | SHA256 |
| --- | --- |
| `retention_diagnostic_readout.json` | `cda3068a6f46ab8395aac0127e5f2252847e1f6d9af475d3d96068179bd12287` |
| Original `REPORT.md` | `88a37d8cfdae6c3c05a79db78827bfe2d59fdcd944067e4f6fcd7f387dddae0e` |
| Root `README.md` | `2e7573f75ddf36bf9577cddfc28adf903a0cb3f8d724017df6c129325be0b5bf` |

`git diff --check` passed. Only the diagnostic report and the two required
completion records change; execution evidence and runtime/test files do not.
The generic `python` command was unavailable, so validation used `python3`.
No dependency installation was needed.

### Review boundary and remaining work

No new-head review or CI approval is claimed; the parent SHA is an evidence
comparison base, not a reviewed-head approval. Publishing and the leader's
existing review/acceptance disposition remain, including acceptance of the
inconclusive measurements and this explicit category-evidence limitation.
There is no additional execution or grading prerequisite. The remote card was
not changed. No carrying-PR state, merge SHA or merge time is recorded.

## GHCP PR #788: two CI fixture failures repaired, 2026-10-29

Read both failed jobs from Backend Tests run `40829408586`. The GHCP cleanup
observer lacked `ProcessLookupError` handling when `/proc/<pid>/stat` vanished
during a read. It now handles only that exception and `FileNotFoundError` as
exited; permission errors, other OS errors and non-exited states still fail.
Production process-group cleanup and its existing assertions are unchanged.

The time-budget failure is **pytest 9.2.0 directory numbering**, not a workflow
hash/file-count guard. Under the same Git 2.34.1, 9.1.1 passed and 9.2.0 reproduced
the exact child `[reuse]` failure (`...1` versus `...0`). Explicitly reusing the
fixture-owned removed directory now passes with all original preservation,
prune/add, identity and cleanup assertions intact. Failures remain retained.

Final combined relevant checks at pytest 9.2.0: **806 passed / 0 failed/errors/
skipped**, **96.70s**, exit 0 (two existing JUnit warnings). Direct 16-case checks
also pass on 9.1.1; do not pool those repeated cases into 806. Evidence, including
red reproduction/child receipts: `/ai-work/copilot/_tmp/ghcp-ci-repair-20261029.xHARGo/`.
The 9.2.0 environment is separate; existing pins, model/security/limit code and
workflow remain unchanged. Only an ordinary branch push is authorized; no
model, secret-value inspection, paid dispatch, merge or Draft release occurred.

## GHCP dispatch-only protected task wiring, 2026-10-29

The new `paid-task` matrix is conditional on explicit workflow_dispatch,
`execute_paid=true` and `dry_run=false`, uses `environment: ghcp-sol-gate`,
and references `COPILOT_GITHUB_TOKEN` only in its runtime step. Push/PR cannot
enter it. Missing/blank auth refuses before Copilot; no credential was read or
supplied here. Fixed five tasks use separate hosted Ubuntu 24.04 jobs, pinned
original inputs and CLI, fresh task state, the existing 1,200-second/64-turn
limits and 32-tool cap, with serial fail-fast scheduling and no rerun retry.
Checked paid outputs connect to the existing model-free Step8 contract job;
missing captures do not fall back to the dry artifacts. Actual judge execution
and unmaterialized inference/grading identities are not fabricated or enabled.

Final combined local offline suite: **729 passed, 0 failed/errors/skipped**,
exit **0**, **62.94 seconds**. The initial focused suite found one new preparation
bug (parquet incorrectly subjected to the reference-files-only path validator):
242 passed / 1 failed, then corrected before the full run. Evidence:
`/tmp/p5-ghcp-paid-wiring.JScehj/`. No model/secret-value access or dispatch.
The authorized ordinary push's source-specific Actions result is collected
separately; its paid job must be skipped and the eight model-free jobs succeed.

Read-only registration checks: default branch `main`; workflow contents on
main HTTP **404**, on this branch **200**; workflow API now **200**, active ID
**400083239**. The earlier 404's exact cause is not established. Manual dispatch
still requires default-branch registration, owner-protected authentication and
an explicit `--ref`; the proposed command is documented but has not been run.
No frozen Step8 source/template/plan/limit, PR or merge was changed.

## GHCP model-free Step8 input bridge, 2026-10-29

The workflow now connects its five empty dry captures to a fresh Step8 manifest
and deliverable-directory layout on hosted Ubuntu 24.04. The new
`grader-contract` job downloads only the current run's capture artifacts and
uses the unchanged Step8 input readers and policy validators. Missing/malformed,
extra, linked, changed or non-model-free captures refuse. Network, subprocess,
provider-SDK, grader and rubric-loader effects are blocked during validation.
No Step8 source, frozen plan/template, limit or real grading identity changed.

The report separates `step8_layout_valid=true` and `grader_policy_valid=true`
from **`ready_for_grading=false`, `gate5_passed=false`**. Dry rows stay pending;
no answers, inference revision or grades are fabricated. Actual live identity
checks still refuse missing inference identity and full-220 identity reuse.
Real answers/rubric and a materialized five-task identity remain necessary for
grading. This rehearsal neither runs nor authorizes a judge or model.

One complete local fixture suite passed **689 tests, 0 failures/errors/skips**,
exit **0**, **60.29 seconds**: previous 640 plus 39 bridge and 10 job-guard
cases. Evidence: `/tmp/p5-ghcp-grader-contract.2zzJok/full.log` and
`full.junit.xml`. Local tests use synthetic hosted metadata, not a NAS benchmark.
The authorized normal push will produce the source-specific Actions run; its
eight jobs and new `ghcp-sol-step8-input-contract` artifact are collected in the
same evidence directory and reported separately after completion.

Authentication recommendation is unchanged: a short-lived personal fine-grained
PAT with Copilot Requests via a protected environment, subject to owner choice.
OAuth and user-to-server tokens are also documented, whereas the automatic job
installation token is not established as a Copilot credential. Official sources
and the one-line decision draft are in `docs/ghcp-sol-actions-gate.md`.
No secret reference, auth/model/judge request, paid dispatch, PR or merge occurs.

## GHCP hosted Ubuntu 24.04 admission and model-free CI, 2026-10-29

The owner's 2026-10-29 09:20 host decision supersedes the NAS execution route
recorded below. Every enabled adapter path now requires GitHub-hosted Linux,
`ImageOS=ubuntu24`, actual Ubuntu `VERSION_ID=24.04`, and complete runner/image
metadata. Refusal precedes auth, binary reads and task/process creation; a
pre-spawn recheck catches drift. Receipts retain bounded host metadata while
explicitly denying cryptographic-host and live model-setting attestation.

One full model-free suite in a fresh minimal dependency environment passed
**640 tests, 0 failures/errors/skips**, exit **0**, **58.08 seconds**. It includes
the existing 543 cases and 97 additions: host rejection on the smoke/five task
entries, OS/label disagreements, drift, development-only dry capture, workflow
guards and version/fake-auth script checks. The separate focused 229-pass run
is not pooled into this count. No installed CLI, real auth source or model was
used locally. Evidence: `/tmp/p5-ghcp-actions-2404.mCx1ix/full.log` and
`full.junit.xml`.

Workflow lookup returned HTTP 404; the new trigger is limited to this branch's
gate-related pushes. The workflow checks the real hosted runner, installs and
hash-verifies Copilot CLI 1.0.103, invokes only its version command in a fresh
empty-auth HOME, runs this suite once and performs fake-token projection only.
Five subsequent captures remain empty/model-free. No secret reference, token
issuance, installed-CLI prompt, paid gate, PR or merge is part of this route.
Actions results belong to the source-specific run produced by the authorized
normal push and are reported separately, not inferred from local tests.

Official documentation distinguishes the accepted `GITHUB_TOKEN` variable name
from the automatic Actions installation token; the latter's Copilot support is
unverified, so it is not selected. A personal fine-grained PAT with Copilot
Requests through a protected environment is a proposed supply option, not the
only supported token type: OAuth and GitHub App user-to-server tokens are also
documented. Owner choice and actual model authorization remain pending. Sources
and a two-line owner-decision draft are in `docs/ghcp-sol-actions-gate.md`.

## GHCP owner-file injection and model-free entitlement check

Existing stored gh login: **yes**, `GET /copilot_internal/user`, HTTP **200**,
plan **enterprise**. Only those projected metadata fields were retained; raw
responses and headers were discarded. No token-export, token-issuance or
completion endpoint was used.
General Copilot entitlement is not installed-CLI acceptance or Sol/Max/1M proof.

The single explicit auth selector now supports `COPILOT_GITHUB_TOKEN_FILE`:
an absolute, owned, regular, single-link **0600** file outside source/capture
trees, with a bounded read and rechecks. Bad/missing/empty files refuse before
launch; the value goes only to the child `COPILOT_GITHUB_TOKEN` environment and
the transient leak guard. No file copy or parent-env mutation occurs. Existing
`GH_TOKEN` injection remains the opt-in interface for a future approved gh
wrapper; the adapter never extracts a gh token or chooses a fallback.
Receipts store the source name only. File-source pipe/transcript/receipt/handoff
leak tests fail closed and mask retained metadata. Arbitrary CLI logs, encodings
and same-user process access remain outside that guarantee; this is not a VM.

One combined offline gate run: **543 passed, 0 failed/errors/skipped**, exit
**0**, **57.18 pytest / 57.463 wall seconds**. It includes all previous 500 cases
and 43 new cases. The initial incomplete 102-pass invocation stopped on pytest
progress reporting versus the existing names-only environment fixture; only
output settings changed before the final full pass, not guards/assertions.
Evidence: `/tmp/p5-ghcp-token-file.IUoE0w/`, including the metadata projection,
exact command, final log/JUnit/timing and preserved incomplete-run diagnostic.

The [owner's B procedure](../../docs/ghcp-sol-actions-gate.md) has five steps
covering permission, expiry, protected file location, explicit selection and
revocation. The owner has not chosen a source; no real PAT was created/read,
no installed Copilot CLI or smoke/model/five-task run, dispatch or PR occurred.
Plans, caps, workflow and finite rights remain unchanged. Commit and normal
push are restricted to this GHCP branch; other worktrees are untouched.

## GHCP masked-prefix authentication follow-up

At source `303e1f987`, default-masked `gh auth status` returned exit **0** and
the nonsecret prefix **`gho_`**, identifying the existing gh token as **OAuth**.
Scopes: **gist, project, read:org, repo, workflow**. The official Copilot CLI
authentication documentation supports this token type; Copilot entitlement,
billing identity and isolated supply remain **unverified**. No raw status output,
token value or credential file content was retained or copied, and no token
export/login command ran. The earlier JSON-projected result remains historical.

[The authentication-choice section](../../docs/ghcp-sol-actions-gate.md)
now separates operator actions, adapter behavior, risks and current feasibility
for an existing-gh bridge, dedicated fine-grained PAT and protected Actions
secret. None is selected or supplied. Only documentation/completion records change.
Related synthetic tests: **23 passed, 0 failed/errors/skipped, 38 deselected**,
exit **0**, **1.05 pytest / 1.225 wall seconds**. The old full **500-test** proof
is separate and was not rerun. Evidence: `/tmp/p5-ghcp-auth-kind.2zmgsj/`.
No model, installed Copilot CLI, real smoke, five-task run, PR, dispatch or merge.

## GHCP authentication inventory and fixed-five mock preflight

Starting at clean, pushed `d99081b74`, the final combined offline suite passed
**500 tests, 0 failed/errors/skipped**, exit **0**, in **55.77 pytest / 56.053
wall seconds**. The new **45 cases** cover five fixed task IDs with nine fake
input/event conditions each. The generic command path now shares the existing
fresh HOME/config/cache environment; no live five-task command is enabled.
Capture/temporary-directory disposal is a test-only controller. The actual
adapter/parser/counter/receipt/process-group cleanup is exercised. Expected
refusals, missing usage and false paid/settings-proof authority are preserved.

Metadata-only `gh auth status` reports active account `hyeonsangjeon`, success,
and scopes **gist, project, read:org, repo, workflow**. Token type and Copilot
entitlement are **unknown**. All three allowed auth environment names are absent.
The default Copilot config file exists, but its contents/stored-login status and
keychain-item presence remain **unknown**. No secret value or credential file
content was inspected, printed, recorded or copied; no login or token export.
Owner choices and their required actions are in
[the updated gate document](../../docs/ghcp-sol-actions-gate.md).

The first launcher failed before pytest because `/usr/bin/time` was absent.
The first actual suite was **455 passed / 45 failed**; the new fixtures omitted
a required usage-event ID. Only that fake event was corrected before the full
final run; checks and assertions were not weakened. Prior evidence is retained.
Evidence: `/tmp/p5-ghcp-free-preflight.HkdCO8/`. No model, installed Copilot CLI,
new smoke, paid task, PR, merge or dispatch ran. No source was chosen for auth;
Sol/Max/1M live evidence and usage remain unavailable. Commit and ordinary push
are limited to this GHCP branch; the separate cost-proposal branch is untouched.

## GHCP authentication opt-in: source absent, smoke skipped

At base `4a10996f2c8927896f711dd4722d57a6808d5c83`, add a name-selected,
disabled-by-default authentication path to the fixed Copilot CLI smoke. The
allowlist is `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN`; only the explicitly
chosen existing name is forwarded. Receipts contain `auth_source` as a name,
not a value. Missing/invalid selection or an unavailable source refuses before
executable validation, directory creation or spawning. No authentication file is copied.

The three names are **all false/absent in this worker's inherited environment**.
The CLI's retained 1.0.103 help documents their precedence. Static source names
in `/usr/local/bin/copilot:32-34` show a GitHub CLI authentication bridge to
`GH_TOKEN`; no wrapper or token command ran. The active Desk's stored-login
kind remains **unknown**, not a claim of keychain/config absence. Values,
credential stores and private configuration contents were not inspected.

**No new smoke was started**, so the current smoke exit is **null**, and
`served_model`, `reasoningEffort`, `tokenLimit` remain **null / unverified**.
Usage is **not available**, not zero. No five-task/220-task run, retry, login,
token creation, credential change, PR, merge or workflow dispatch occurred.
The preceding actual CLI exit 1 / adapter exit 2 belongs only to the prior
attempt; it is not reused as a new execution result.

One combined offline gate invocation passed **455 tests, 0 failed/errors/skipped**,
**50.87 pytest / 51.157132434 wrapper seconds**, exit **0**. The added fixtures
cover names-only presence inspection, explicit source selection, pre-launch
refusal and literal/JSON-escaped value non-egress through stdout, stderr,
receipt and adapter-owned transcript, including split chunks. The guard is not
a general encoding detector or a scan of arbitrary CLI stores/logs. No real
credentials or installed CLI were used by fixtures. The earlier 433-test proof
remains separate, not a pooled total.

Evidence: `/tmp/p5-ghcp-auth-optin.F5QHs2/`, including
`auth-source-observation.json`, `tested-code.sha256`, `tested-code.patch` and
`gate-tests.*` with the exact command, log, JUnit and timings. Only this GHCP
worktree changed. Fresh work/HOME/config/cache, 1,200 seconds, 64 turn starts,
32 tool starts, model selection and the blocked five-task route are preserved.
Final commit/push identity is returned in the handoff, not presumed here.

## GHCP Copilot CLI agent + GPT-5.6 Sol: one NAS smoke

The leader selected the installed Copilot CLI default agent and a NAS isolated
directory, **VM 아님, 격리 디렉터리**. The owner-authorized single prompt was
`Reply with exactly CONNECTED`. It reported **`No authentication information
found`**, CLI exit **1**, adapter exit **2**. No model/effort/context event was
observed: **model=null, reasoningEffort=null, tokenLimit=null**, all **unverified**.
No retry or five-task run followed. This does not establish a lack of credentials
elsewhere, and it does not establish zero billed usage.

### Source and implementation

Worktree `/ai-work/copilot/_tmp_worktrees/ghcp-sol-gate-actions-20261024`, branch
`leader/ghcp-sol-gate-actions-20261024`, started clean at
`1fbbd9040e55546ccfc0ab9454fb3d158f42efc8`. Implementation commit
`b2ee44f3b80cc18663b2993b2a95230efb00468f`, tree
`0312f7a9f1295d02df4aa537ea6fcf10657f3759`, binds the CLI and receipt projection.
Only this worktree changed. The final documentation commit/push identity is
returned in the handoff; publication is not assumed in this record.

- Pin executable **1.0.103**, SHA256
  `f19b3554a6b62605db3a26d5255ebe2a3ee39fcd6a357edb18301ea5037f6f0d`.
  Four preparatory help/version commands used fresh configuration and disabled
  auto-update/telemetry. They are not smoke prompts or model evidence.
- The real adapter defaults disabled and accepts only the fixed smoke on this
  bound route. Five GDPVal task IDs refuse. Fresh work/HOME/config/cache/data/
  state/tmp directories and an allowlisted child environment prevent adopting
  a prior session. Existing auth variables may be passed, never printed or
  copied into records. No credential store was inspected or changed.
- Retain **1,200 seconds / 64 turn starts** and use the leader's **32 tool
  starts**. Group TERM/KILL cleanup closes both pipes and reaps the leader.
  This is not VM isolation or proof about descendants escaping the group.
- Record original allowlisted event fields separately from requested values.
  Missing/conflicting settings refuse. Any `verified` status concerns field
  agreement, not provider attestation. Usage sources are separate, never summed
  into invented totals. Missing consumption stays `not available`.

### Verification and the one actual prompt attempt

Evidence root: `/tmp/p5-ghcp-cli-smoke.0tE4vK/`.

| Invocation | Outcome | Pytest / wrapper seconds; exit |
| --- | --- | --- |
| `gate-tests.*`, before the smoke | **432 passed, 0 failed/errors/skipped** | **51.66 / 51.994685640; 0** |
| `smoke.*`, one installed CLI prompt | Authentication error; no setting events | Wrapper **1.986582998; 2**, CLI **1** |
| `verified-tests.*`, after the duration-only correction | **433 passed, 0 failed/errors/skipped** | **49.94 / 50.215530831; 0** |

The final combined invocation covers **138 Actions**, **82 adapter**,
**93 VM contract**, **81 input-bundle** and **39 CLI-smoke** cases, including
existing Auto/BYOK refusals.
Tests use Python **3.10.12**, a cleared offline environment and fake executables;
no installed CLI or credentials are used in fixtures. The final 433 results
are not added to the previous 432 or the historical 313-test proof below.

The smoke used base `1fbbd9040e55546ccfc0ab9454fb3d158f42efc8` plus
`tested-code.patch`, SHA256
`1ce93e3b48fbd0d3f95410f9cfb99c979b1c3c6bc864a0b45249d0fad64f1153`.
Final `verified-code.patch` SHA256 is
`bdda028ee81200e9d592a4210093d0a042e852eae991d017e86044539f4b1ba0`.
`verified-code.sha256` binds the tested executable/test bytes to the code commit.

The original `smoke.receipt.json` has SHA256
`bfa2b17ba9f24682433e669433bdf54480ccb0ed3f5c3e9502dad342578efa35`.
Its only usage-file projection was **`totalApiDurationMs=0`**, incorrectly
classified as available usage. That value is milliseconds, not tokens or money.
The original receipt is preserved; `smoke-observation.json` corrects the
interpretation to **usage/cost not available**, with no new execution. The
final code removes duration fields from the usage projection and has a new
synthetic regression. It was **not** used for a second real smoke.

The actual process receipt records group signals, leader reaping and closed
stdout/stderr. Model, effort, context, provider request count, billing and full
event delivery remain unverified. No token search, credential change, login,
grading, model retry, five-task/220-task run, PR, merge or workflow dispatch
occurred. The next prerequisite is authentication approved for the fresh CLI
environment and a new leader instruction. Original VM plans, other worktrees,
frozen graders, dependencies and all prior finite rights are unchanged.

`experiment-design` bounded this to a connectivity/metadata smoke, not a
benchmark. `experiment-report-en` and `im-not-ai-en` preserve the source/run
boundaries and distinguish a zero timing field from unavailable consumption.
The [implementation contract](../../docs/ghcp-sol-actions-gate.md) retains the
historical investigations below the new NAS condition.

## Historical completion record retained unchanged

## GHCP Sol gate: execution approval and publication boundary

Scope: the owner's **2026-10-26** request to proceed with paid experiments,
pipeline work and ordinary commit/push. Worktree
`/ai-work/copilot/_tmp_worktrees/ghcp-sol-gate-actions-20261024`, branch
`leader/ghcp-sol-gate-actions-20261024`, started clean at
`2f0773b361a688ab7e93a8d8ae61adc5e568bece`, tree
`6ac9e67f82557631f07a31e97a8ab170d8a4372c`. No other checkout was changed.

### Result

**Paid execution and publication are now owner-authorized, but this branch
does not implement a runnable GHCP-backed Codex task route.** No paid task,
grading or pipeline dispatch ran. Approval has not been substituted for a
working command, isolated authentication or missing execution-limit values.

| Question | Finding and boundary |
| --- | --- |
| Model capacity | OpenAI's GPT-5.6 Sol model page advertises a **1,050,000-token context window**. This is a published model specification, not a measurement of the GHCP session's applied context. |
| Actual execution | `.github/workflows/agentic-v2-ghcp-sol-gate.yml` is dry-only. The adapter has no GHCP command/authentication binding and is not wired into that workflow. `code` and `code-insiders` are not on PATH; no installation or account-entitlement conclusion is inferred. |
| Remaining limits | The existing **1,200-second / 64-turn** requirements are unchanged. The inert registration's tool-call and USD ceilings remain null. No Foundry limit or pricing was imported. |
| Publication and dispatch | The exact origin project was confirmed. The bounded remote-head lookup exited 0 with no matching branch. The workflow metadata GET returned **HTTP 404**, which does not identify whether the record is absent or inaccessible. No dispatch was attempted. The ordinary push outcome belongs to the final handoff, not an anticipated success in this record. |

The original GHCP/Codex condition is preserved. Switching to Copilot CLI's
default harness would be a different condition, not an implementation fix.
The owner can supply the missing Codex connection contract or explicitly
choose that scope change. The
[route matrix and official sources](../../docs/ghcp-sol-actions-gate.md#product-routes-and-scope-decision-2026-10-25-2145-kst)
give the per-route yes/no/unknown decisions and their conditions.

### Current evidence and checks

Evidence directory: `/tmp/p5-ghcp-execution-20261026.GQp0K1/`.
The [official model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
returned HTTP 200. Its retained 461,900-byte body has SHA256
`7bde0883be9345f5a4ef44ccbb5a1843ddd9f0672d0970ad35ae2ab03151d451`.
The attempted official search URL redirected and then returned 404; it is
not treated as search evidence. Only the fetched model page supports the
capacity statement. Public reads had 20-second and 2-MiB bounds with no
supplied credentials. No model response or private input was read, and no
credential value was inspected or exposed.

The preceding installed-CLI/version evidence and eleven help/version
invocations remain in the [prior document](../../docs/ghcp-sol-actions-gate.md#default-agent-evidence-refinement-2026-10-26).
The prior route findings, public-page digests and diagnostic limitations remain
in the [immutable record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/ff8249cd8d94d07349cbc81292365c5e0f782262/tasks/LATEST_TASK_RESULT/README.md).
Neither investigation was repeated. Git comparison confirmed that the
workflow, collector, adapter and three gate test modules/fixtures are unchanged
from the retained 313-test source below. No tests or collection reran.
Only the direct document, this record and CHANGELOG change in this update;
verification covers documentation scope, protected evidence and unchanged
runtime hashes. This is not independent fixed-HEAD review or CI approval.

### Last retained synthetic proof; no tests rerun

Prior evidence directory: `/ai-work/copilot/_tmp/ghcp-sol-harness-schema.zoULYD/`.
The last tests used clean HEAD `59c23a1446533cc988cf74840cd00eb1a23c3605`, tree
`49033ac832de59987d19d41817f3fc6d6f4567ad`; the subsequent documentation-only
head was `b9440698014eae3a941ea31d86f6b6bf5599a595`. The
[immutable pre-audit record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/b9440698014eae3a941ea31d86f6b6bf5599a595/tasks/LATEST_TASK_RESULT/README.md)
binds that proof. Its implementation, tests and fixture hashes still match.
**No tests, collection or static fixture verification were rerun here.**

| Invocation | Outcome | Pytest / wrapper time; exit |
| --- | --- | --- |
| Collection, three gate modules | **313 nodes** | **0.40s / 0.56s; 0** |
| One combined body invocation | **313 passed, 0 failed, 0 skipped** | **16.50s / 16.66s; 0** |

The retained JUnit contains **138 Actions + 93 VM + 82 adapter** cases, including eight
Auto/BYOK-named refusals. No test failure, retry or warning was reported. A
separate prior static check validated the fixture's **four session events**
against the exact installed Draft-07 schema with format checking and internal
references only. Its fifth, CLI-only result is outside the session schema.
Synthetic timestamps/zeros and fake-process cleanup are not runtime or cost
measurements, complete delivery proof or general containment guarantees.

That prior invocation used the existing Python 3.10.12 environment in `batch-runner/`, under
**120s TERM + 5s KILL**, cleared environment/offline flags and existing network/
provider guards. Adapter subprocesses were generated fake executables only.
The exact collection and body commands are in `invocation.txt`; the body was:

```bash
timeout --signal=TERM --kill-after=5s 120s env -i PATH=/usr/local/bin:/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 /ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python -m pytest -q -ra --tb=short -o addopts= -p no:cacheprovider --junitxml=/ai-work/copilot/_tmp/ghcp-sol-harness-schema.zoULYD/junit.xml tests/test_ghcp_sol_actions_gate.py tests/test_ghcp_vm_gate_contract.py tests/test_ghcp_sol_execution_adapter.py
```

| Tested source | SHA-256 |
| --- | --- |
| `batch-runner/ghcp_sol_execution_adapter.py` | `9a5fb7ee55be3a990d61ec565c56314d235847c8f0c8ef29ec3213255bc01558` |
| `batch-runner/tests/test_ghcp_sol_execution_adapter.py` | `4f4746c015d4f76eba338783abfe26a14793a4f075c28e4104147b7bd1311006` |
| Retained `ghcp_sol_copilot_1079_stdout.jsonl` | `5d28496a0d825c80f0165b192bcd70641ba9ed415450eba1b786647f88ba0459` |
| Unchanged collector `ghcp_sol_actions_gate.py` | `d757aafd7c18c32f6682b79ebd4f51bc901d58f2fa97c8c50030e1b4762ed698` |
| Inspected installed 1.0.79 event schema | `350df35914d4e2fdbadb8932ca66f1e58d759aad79b5be9291857c9052d31301` |

| Artifact | Bytes, where listed | SHA-256 |
| --- | --- | --- |
| `test.log` | 421 | `d58de7d756370bc651f4acbf51fef6302728efc51c33130bd4c6ef5dfb92ba8b` |
| `junit.xml` | 48745 | `533e6bc12092a2518dc115583b55620f2246b19247ea6bb16353acb610a6a2fa` |
| `tested-code.patch` | 12917 | `3fb98d42c8758e460df9fb93a910929c72772b3e973eea4b20b7b20d213d0f34` |
| `invocation.txt` | — | `d7d9ec7ab6140fcfc50b56a9582e2f04837f56c20a4931907e90a62223fac771` |
| `timing.txt` | — | `59a49055ea0b11ba106be7b2a35d81134b574a9437a5ecd877ff1be452e2511b` |
| `schema-validation.log` | — | `49a4e1e67fe2f5f8fdcdb0d4fd794296ad082bc7483e9715757f4aca2a32b3c4` |
| `proof.sha256` | — | `94d59e69f83bd17963003480ed1e498cc695e75afd4ca1e1bcc8011df2a9882d` |

`proof.sha256` also binds collection/timing, installed-source excerpts,
package manifests and unchanged-scope hashes. The previous **295 passed,
4 failed** and separate **4 passed** proof, original help diagnostics and
unverified background-network behavior remain in the
[immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/8eb449d90a43fab68cd553ee73b95907a55a00e3/tasks/LATEST_TASK_RESULT/README.md)
and its unchanged `/ai-work/copilot/_tmp/ghcp-sol-cli-contract.9Qj6sx/` evidence.
They are not pooled with, or relabeled by, that later 313-test proof.

### Remaining gates and authority

The adapter remains disabled by default, and the workflow remains dry-only.
The actual VM/harness command binding, an unfiltered complete/prompt event
channel, served/applied model/Max/1M evidence, approved tool-call cap,
authentication isolation/disposal, input/grader bindings and fixed-HEAD
review/CI remain required before execution. Event-based
cancellation is not pre-effect admission of turn/tool limits. Paid/retry and
completion fields in the unchanged inert contract remain false; no performance,
cost or score is inferred. The owner's new execution approval does not make
those operational prerequisites true or reset consumed rights.

Ordinary branch publication is authorized. Repository metadata access uses
existing configured Git/GitHub authentication; no login, token extraction,
credential-store inspection or secret movement was performed. No raw session,
private input, model call, dispatch, grading, PR, merge or Project operation
ran. Plans, limits, runtime refusal behavior and prior evidence are unchanged.

`openai-docs` guided the model-specification check. `experiment-design` kept
the registered condition and unknown cost/tool limits explicit without
inventing them. `experiment-report-en` and `im-not-ai-en` preserve the boundary
between the owner's approval, public specifications, prior synthetic proof
and unobserved runtime behavior. No UI work or experiment redesign was done.
No specialist, CI or runtime endorsement is claimed.
