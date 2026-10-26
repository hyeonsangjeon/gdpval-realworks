# Five-task Foundry Sol pilot: proposed USD ceilings

**Owner-decision candidates: $800, $1,000 or $1,200. None is approved.** The
arithmetic below produces a **$799.20 conditional stress reserve**, not a forecast
or a guaranteed all-in bill. A finite unconditional worst-case cost remains
**unknown** because future grading usage, applicable billing axes and provider
token enforcement are not fully bound. Choosing a number does not authorize a run.

This document uses source `abb883c95f008331697db79132c62b13c294e8ef`, the
registered Foundry GPT-5.6 Sol + Codex pilot, and existing repository records.
It does not use the GHCP smoke's condition, credentials or usage. The source
plan, caps draft, frozen judge, model/host identities and all finite rights are
unchanged. `approved_maximum_usd` remains **null**.

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
The plan's tariff-evidence hash and approved USD maximum remain null, and using
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

## Owner options; no plan change

| Proposed USD ceiling | Headroom over $799.20 | Decision tradeoff |
| --- | ---: | --- |
| **$800** | $0.80 | Nearly no room beyond the explicit stress assumptions. |
| **$1,000** | $200.80 | Suggested discussion option, roughly 25% room above that scenario. |
| **$1,200** | $400.80 | More room for uncertainty; still not a validated all-in bound. |

These are proposed authorization ceilings, not expected charges or assurance
that all five tasks can finish. Unknown extra cost is a parameter `U`, not zero:
the scenario is `$799.20 + U`, and `U` has no verified upper bound. Before any
chosen ceiling can be operational, pricing and monetary admission/stop checks
must be bound; an owner choice alone does not close the existing launch gates.
No option is written into the plan or granted execution authority by this document.

## Connection-shaped reference, not a task forecast

The retained metadata for run **39407062120** reports **9,444 input / 5 output
tokens**, requested deployment `gpt-5.6-sol`, but **served model=null**
([caps diagnostic:62](../experiments/execution_envelope/gpt56_sol_native_caps_draft_20261024.yaml#L62)).
Applying the stored short/long rates to those counts, without write charges,
gives **$0.047370–$0.094665** for one connection-shaped sample, or
**$0.236850–$0.473325** for five hypothetical copies. These are new arithmetic
illustrations on old reported usage, not measured dollars, new calls, a
five-task forecast or evidence that Sol/Max/1M was actually served.

Only local source/record reads and Decimal arithmetic were used. No model,
grading, preparation, dispatch, external pricing lookup or test replay ran.
The existing 469-test implementation evidence is preserved separately; this
document does not renew it or turn it into financial-enforcement proof.
