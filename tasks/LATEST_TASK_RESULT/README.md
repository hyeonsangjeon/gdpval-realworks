# Latest task result

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
