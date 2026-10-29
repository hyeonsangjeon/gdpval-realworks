# Five-task Foundry Sol pilot: approved USD ceiling and shared estimate guard

**The owner selected USD 1,000 as the total five-task inference-plus-grading
ceiling**, in the desk message **2026-10-26 23:09Z**, "총비용 상한 1000".
The amount decision is recorded; it is not permission to launch this offline
change. Inference and grading now share a durable estimated-USD admission ledger.
The current price table leaves Sol grading unpriced, so its real grading entrypoint
refuses before input loading, authentication or client construction.
**A hard ceiling on the actual combined bill is not established**: effective
tariff, cache accounting and server token bounds remain unverified. The **$799.20** below remains a conditional
stress reserve, not a forecast or a guaranteed all-in bill.

The original cost calculations use source `abb883c95f008331697db79132c62b13c294e8ef`,
the registered Foundry GPT-5.6 Sol + Codex pilot, and existing repository records.
The approval/guard update starts from proposal commit
`36cc47af5f5b8feb147063a61e53b3ad4cc1fb9d`. The shared-ledger follow-up starts from
`5906f24e0cd520c37099ff5e4b42ce95c55c6ee3`; its tested code identity is in LATEST.
It does not use the GHCP smoke's condition, credentials or usage. The source
plan, caps draft, frozen judge, model/host identities and all finite rights are
unchanged in their sealed originals. The active monetary decision is
`cost.approved_maximum_usd: 1000` in the new
[USD-cap companion](../experiments/execution_envelope/gpt56_sol_native_usd_cap_20261027.yaml).
The old plans/draft retain their historical **null** fields byte-for-byte; the
wire budget reads the companion, not a silently edited old registration. The
[source-only successor](../experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261027_shared_usd.yaml)
binds changed wire/preflight/Step 8 code and holds the actual shared-budget and
cost-metering modules, companion and price-table bytes through admission and
final rechecks. The companion's original enforcement description is historical;
the new source profile records the connected guard. No old seal or study/retry
right is changed.

## Registered quantities, without adding retries

| Quantity | Value used | Source |
| --- | --- | --- |
| Tasks and repeats | 5 tasks, 1 repeat | [source registration:161](../experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261026_token_precheck.yaml#L161) |
| Attempt slots | Initial + up to 3 infrastructure retries per task = 4; at most 20 across the pilot | [registration:197](../experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261026_token_precheck.yaml#L197), [sealed caps draft:7](../experiments/execution_envelope/gpt56_sol_native_caps_draft_20261024.yaml#L7) |
| Other retry mechanisms | Request retries 0, stream retries 0, resume rounds 0; Self-QA false | [registration:201](../experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261026_token_precheck.yaml#L201) |
| Tokens per attempt | 300,000 input; 10,000 output | [caps draft:20](../experiments/execution_envelope/gpt56_sol_native_caps_draft_20261024.yaml#L20) |
| Pilot token totals | 6,000,000 input; 200,000 output | [caps draft:37](../experiments/execution_envelope/gpt56_sol_native_caps_draft_20261024.yaml#L37) |
| Grading | 1 pass per task, 5 tasks; frozen Sol/Max identity | [registration:214](../experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261026_token_precheck.yaml#L214) |

Infrastructure retries apply only to `rate_limited` and `turn_start_failed`,
not arbitrary failed outcomes ([Step 2:177](../step2_run_inference.py#L177)).
The calculation reserves a full token allowance for every possible attempt
slot; it does not claim every slot will run or be billed in full. The separate
32-request cap is **not** another token multiplier. Input already includes
cached input; output already includes reasoning tokens. Neither subcount is
added again ([caps accounting:99](../experiments/execution_envelope/gpt56_sol_native_caps_draft_20261024.yaml#L99)).

The YAML's native-cap declarations and draft status are preserved, not rewritten
as financial approval. The [client precheck contract](gpt56_native_hard_token_contract.md)
still distinguishes a byte-based input estimate from a proven tokenizer/server
bound. Its `token_hard_limit_enforced=false` boundary remains in force.

## Stored Foundry prices, not a newly verified tariff

The repository has Azure-published Sol meters. They are not OpenAI or Copilot
prices. Units are **USD per 1,000,000 tokens**; the recorded retrieval date is
**2026-08-29** ([price-table provenance:213](../experiments/execution_envelope/model_price_table.json#L213)).

| Standard Global meter | Input | Cached input | Cache write | Output |
| --- | ---: | ---: | ---: | ---: |
| Short context, [line 245](../experiments/execution_envelope/model_price_table.json#L245) | $5.00 | $0.50 | $6.25 | $30.00 |
| Long context, [line 249](../experiments/execution_envelope/model_price_table.json#L249) | $10.00 | $1.00 | $12.50 | $45.00 |

The effective tariff is **still unverified**. The table deliberately leaves
`azure:gpt-5.6-sol` unpriced because tier, zone and write-token accounting are
unresolved ([line 153](../experiments/execution_envelope/model_price_table.json#L153)).
The sealed plan's tariff-evidence hash and legacy USD-maximum field remain null;
the separate owner-approved companion now supplies **USD 1,000**. Using
OpenAI/Copilot tariffs for Foundry is false ([registration:235](../experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261026_token_precheck.yaml#L235)).
The numerical scenarios assume Standard Global and use the higher of its two
context rows. They do not settle that assumption or refresh the stored prices.

## Problem-solving allowance

With `P_in` and `P_out` denoting applicable USD-per-million rates:

```text
N = 5 × (1 + 3) = 20 attempt slots
I = N × 300,000 = 6,000,000 tokens
O = N × 10,000 = 200,000 tokens
M = (I × P_in + O × P_out) / 1,000,000 = 6 P_in + 0.2 P_out
Short Standard Global: M = 6 × 5 + 0.2 × 30 = $36.00
Long Standard Global:  M = 6 × 10 + 0.2 × 45 = $69.00
```

These are conditional allowances assuming the registered token budgets hold.
They take no cached-read discount and do not yet include cache-write charges.
They are not an unconditional provider-enforced spending ceiling.

## Grading reserve from recorded expensive tasks

One grading pass is not one model call. The frozen grader permits per-item
tool loops, visual/audio calls and retries ([template:271](../grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml#L271)).
The five passes are **not** multiplied by the four solver attempt slots.

[PR3_COST_BUDGET.md:110](../../tasks/rebuilding_grading_task/PR3_COST_BUDGET.md#L110)
explicitly tabulates these historical per-task high endpoints:

| Recorded grading cohort | Task prefix | Calls | Short/long estimated range |
| --- | --- | ---: | ---: |
| gold-185 | `19403010` | 163 | $29.59–$58.24 |
| Published sol-220 | `47ef842d` | 159 | $29.52–$58.03 |

Use `h = max(58.24, 58.03) = $58.24` as a **proposal premise**: each future
grade is provisionally allocated the larger of these two cited endpoints.
Then `G_reference = 5 × h = $291.20`, and `M + G_reference = $360.20` at long
Standard Global rates, before write charges. This is not an observed pilot cost,
an exhaustive maximum over every historical run, or an enforced future limit.

The source ranges exclude cache writes; the gold cohort's non-Sol audio calls
are also excluded ([historical rule:35](../../tasks/rebuilding_grading_task/PR3_COST_BUDGET.md#L35)).
Different deliverables can change grading work. The later exp035 grading report
still records `price_missing` rather than a dollar total ([report:105](run_records/exp035_grading_coverage_220.md#L105)).
No missing charge is treated as zero, and no historical mean is sold as an upper bound.

## Explicit cache-write stress scenario

To avoid silently omitting writes, add a separate counterfactual using the
recorded **$12.50/M** long-context write rate. Assume **at most one write per
uncached input token**, and retain the preceding `h` allocation for every grade.
These quantities are not observed or enforced. The existing historical budget
also treats all uncached input as a possible write scenario ([PR3:263](../../tasks/rebuilding_grading_task/PR3_COST_BUDGET.md#L263)).

For grading, additionally assume actual no-write charges fit `G_reference`.
All components are nonnegative, so at $10/M for uncached input this implies
`G_reference >= 10 × I_uncached / 1,000,000`. Under the one-write premise,
write charges are therefore at most `(12.50 / 10) × G_reference` **within this
scenario**, not for arbitrary future grades.

| Component | No-write reference | Conditional write addition | Stress reserve |
| --- | ---: | ---: | ---: |
| Solver, all 20 attempt slots | $69.00 | `6 × 12.50 = $75.00` | $144.00 |
| Five grades under the cited historical allocation | $291.20 | `1.25 × 291.20 = $364.00` | $655.20 |
| Combined | **$360.20** | **$439.00** | **$799.20** |

Audio outside the reference, other attributable runtime/service charges, taxes,
contract-rate differences, provider overruns and failures of these premises
remain unknown. There is **no finite all-in worst-case bound established here**.

## Owner selection and retained proposal alternatives

| Original proposed USD ceiling | Headroom over $799.20 | Decision tradeoff |
| --- | ---: | --- |
| **$800** | $0.80 | Nearly no room beyond the explicit stress assumptions. |
| **$1,000 — selected** | $200.80 | Owner-selected limit, roughly 25% room above that conditional scenario. |
| **$1,200** | $400.80 | More room for uncertainty; still not a validated all-in bound. |

The selected **$1,000** is a limit, not expected charges or assurance that all
five tasks can finish. The other amounts remain unselected alternatives from
the proposal. Unknown extra cost is a parameter `U`, not zero:
the scenario is `$799.20 + U`, and `U` has no verified upper bound. Before any
chosen ceiling can protect the combined bill, pricing and monetary admission/stop
checks across inference AND grading must be bound; an owner choice alone does
not close the existing launch gates. The companion records the amount, and the
shared estimate guard below is only one part of that work. No launch occurs.

## Runtime estimate guard and remaining billing gap

`gpt56_pilot_wire_receipt.py` reads the pinned companion and existing price-table
bytes. Actual pilot wire sessions now open the common SQLite amount ledger in
`.pilot-usd-budget/ledger.sqlite3` under their verified capture workspace.
The companion identity file binds the run, capture digest, ordered five tasks,
price-table digest, approved amount and a unique ledger identity. Native and
grading requests use atomic transactions on that same file.

Before constructing an upstream connection, native admission reserves the
**remaining attempt input-token allowance**, the request's
`max_output_tokens`, and the one-full-input-write reserve at the stored long
Standard Global rates. Concurrent reservations share the same **USD 1,000**.
There is no cached-read discount, new per-task allocation or refill. Financial
state can be reopened after a process restart; the native live-session witness
and study rights still cannot be adopted from disk.

Complete provider usage settles a reservation once. SDK cumulative totals are
a floor, not another sum; a pending reservation excludes the portion already
accounted by that floor. Missing, partial, failed or unpriceable response usage
consumes the reservation and stops further admission against the shared budget.
Reopening detects a dead process's pending requests and consumes their held
amounts rather than recovering unused credit. Already-accounted usage is not
charged twice. An existing directory with missing, foreign or mismatched state
is refused, not initialized as a fresh budget. This requires the same retained
local files; it is not cross-host recovery or protection against restoring an
older valid filesystem snapshot. A request
whose estimate would exceed the ceiling stops before upstream construction with
`usd_ceiling_exceeded`. Other fixed reasons are `usd_usage_unverified`,
`usd_reservation_exceeded`, `usd_price_contract_unverified` and
`usd_ledger_unverified`. Each shared-ledger account identifies inference or
grading; refusal snapshots preserve the source. Existing native
request/token/deadline guards, stop cleanup and retry allowlists are preserved.
Unknown monetary usage is a new fail-closed stop even where an infrastructure
retry would otherwise have been eligible; no automatic retry resets that ledger.

The receipt's `runtime_caps.usd_ceiling.shared_budget` separates known modelled
subtotals for both origins, pending amounts, consumed-unknown reserves and
remaining modeled USD. Missing actual
cache-write counts stay **null**; the reserve is **not observed billing** or a
proven provider limit. Request token admission is still a client check, not a
proven server bound. `actual_billing_hard_limit_verified` and
`effective_tariff_verified` remain **false**. In the persistent path,
`grading_included=true` means its admission is connected; `grading_usd` is a
known modelled subtotal, not the bill. Unknown consumed reserve is separate,
and `actual_total_pilot_usd` stays **null**. A zero known subtotal does not price
an unknown request at zero. Legacy isolated-fixture receipt fields retain their
earlier shape and do not claim shared admission.

Step 8 now requires `--pilot-usd-workspace` for this pilot. It verifies the
saved inference wire-ready digest and exact ledger binding, and opens an existing
financial ledger only. It passes `GradingUsdAdmission` through `CostRecorder` to
`MeteredClient._around`, covering the judge, perception and retry wrappers.
The separate historical [audit ledger](../step8_grade.py) still reserves an audit
row before a call; the new [amount admission](../core/cost_metering.py) additionally
reserves shared USD before invoking the provider and settles returned usage.

Grading requires an exact, unambiguous price for every configured model from the
pinned table. It cannot use the numerical scenario above as a fallback. The
actual `azure:gpt-5.6-sol` entry is deliberately unpriced, so current Sol grading
is refused with `usd_price_contract_unverified`. Offline priced fixtures do not
change that table or establish a real tariff. If prices are available, the
request guard requires an explicit output maximum and visible-text inputs;
opaque/media/streaming requests and SDK body overrides are refused. Its input
reservation uses serialized UTF-8 bytes, not a proven model-token upper bound.
Internal SDK retries must be confirmed as zero at wrapping and before each call;
the frozen retry policy is not silently rewritten. Missing/partial usage or a
different response model consumes the reservation and blocks later requests.

The grader algorithm, prompts and configuration are unchanged. Its existing
frozen source mismatch remains a refusal; the source-only update does not repin
or approve a new judge. Non-model runtime/service charges, actual tariffs and
server/cache bounds remain outside the verified amount guarantee. No historical
grading estimate is booked as spend, and no paid grading occurred.

## Connection-shaped reference, not a task forecast

The retained metadata for run **39407062120** reports **9,444 input / 5 output
tokens**, requested deployment `gpt-5.6-sol`, but **served model=null**
([caps diagnostic:62](../experiments/execution_envelope/gpt56_sol_native_caps_draft_20261024.yaml#L62)).
Applying the stored short/long rates to those counts, without write charges,
gives **$0.047370–$0.094665** for one connection-shaped sample, or
**$0.236850–$0.473325** for five hypothetical copies. These are new arithmetic
illustrations on old reported usage, not measured dollars, new calls, a
five-task forecast or evidence that Sol/Max/1M was actually served.

The original proposal used only local source/record reads and Decimal arithmetic,
with no test replay. The first approval/guard proof remains at
`/tmp/p5-native-usd-cap.1hIeAd/`, separately from the earlier 469-test proof.
The persistent shared-ledger follow-up adds synthetic priced/unpriced,
cross-process and real-call-seam fixtures; its exact current results are kept in
LATEST and `/tmp/p5-native-shared-usd.nrwZrl/`, not pooled with earlier diagnostics.
No model, grading service, paid preparation, dispatch, external pricing lookup
or five-task execution ran. Offline tests do not attest provider billing.
