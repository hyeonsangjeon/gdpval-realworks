# Native pilot: approved connection binding and public tariff evidence

The approved configured account, deployment and host are now bound to the
native call path. The source-held, explicit preflight clears that requirement
only: **1 cleared / 10 retained / 0 new** blockers, **exit 2**, with
`source_verified` and `inspect_plan` reached. Launch remains disabled. No model
or Azure management call, credential lookup, dispatch, push, PR or merge was
performed. This change grants no new study or retry right.

## What changed and what stayed fixed

Starting source was `ac0a49fa0ad41114d3a55db706e8532c70ba5989`. Code commit
`6c907d789bed4628d46173c72e27f92f8e15a68c` adds an approved-target reference to
`gpt56_pilot_deployment_binding.py`, checks it in `PilotWireReceiptSession`
before observer/SDK effects, and includes its bounded reference in attempt and
ready receipts. Receipts contain hashes and nonsecret historical metadata,
not account IDs, endpoints, credentials or conversation text. The implementation
is in the [route matcher](../gpt56_pilot_deployment_binding.py#L169),
[runtime admission](../gpt56_pilot_wire_receipt.py#L1843) and
[explicit preflight gate](../gpt56_sol_codex_pilot_preflight.py#L1059).
The [nonsecret reference](../experiments/execution_envelope/gpt56_sol_connection_reference_20261027.json)
has SHA256 `293ee682d01cbb64ee2b330f603b49a90522f07429dcd3cf036070808c271b76`.

Admission checks the actual provider URL and account/deployment ID files.
It requires the approved HTTPS host/path, provider/deployment, ARM hierarchy
and canonical selection digests. Existing raw-file byte hashes are also
required; the additional casefolded selection digest does not replace them.
The session rechecks the exact reference and its owned receipt metadata at
admission and final acceptance. Missing, changed or linked references and
different targets fail closed. Direct-v1 still requires no child-project ID.

The new source-only registration
`gpt56_sol_foundry_codex_pilot_source_20261027_connection.yaml` supersedes the
USD 200 registration without editing it. All **58** registered roles match;
only deployment-binding, wire and preflight pins change. The new JSON reference
is also held against reviewed Git blobs on admission and final recheck. Every
non-source plan value, predecessor seal, native cap, price-table byte and frozen
grader setting remains unchanged. The combined inference-plus-grading ceiling
remains **USD 200**; actual billing and server hard-limit claims remain false.

## Existing diagnostic: observed versus requested

The reference identifies run **39407062120**, number **16**, attempt **1**,
artifact **12257312458**. Exact regular non-symlink plan/result members were
rehashed and their observed fields were compared with the reference:

| Member | Bytes | SHA256 |
| --- | ---: | --- |
| `codex-foundry-plan.json` | 4155 | `79145baff122ee14341d9c4930e668ddb26869a1461bbb0e0c8a0e76655e8ada` |
| `codex-foundry-connection.json` | 4890 | `f3e9705bc1a2f934e3c5523638a127fc464bbc9be267e3bf09a38c525b7c6913` |

The artifact archive identity is service-reported; its ZIP was not locally
rehashed in this task. The member hashes above were checked locally. The
historical result says `connected`, a completed turn and the expected
`CONNECTED` response, with no tool execution observed. It used SDK/CLI
**0.147.0**, the `direct-v1` Responses route, and source
`6efe99cbd40bb839037e7a20711a734e0a4ce002`.

| Observed field | Retained value | Supported conclusion |
| --- | --- | --- |
| `runtime_model`, `runtime_model_provider`, `served_model` | `null` | No served model/version verification. |
| Served version, reasoning effort | Not retained | No Max verification; owner-reported version `2026-07-09` is not served evidence. |
| App-server `model_context_window` | 258400 | SDK usage metadata, not proof of provider capacity, 1M application or lack of 1M support. |
| Input / output / cached input / cache-write input | 9444 / 5 / 0 / 9441 | SDK-reported token usage, not reconciled billing. |
| Reasoning output tokens | 0 | A token counter, not a reasoning-effort setting. |

No raw Responses HTTP body is retained in these members. The diagnostic did
not request the pilot's Max/Long overrides. Missing fields are not filled from
requested values or the owner's inventory. The approved target is a configured
selection plus a historical connection reference, not a fresh management or
served-capability attestation.

## Public pricing lookup, 2026-10-27 UTC

The [official Azure pricing page](https://azure.microsoft.com/en-us/pricing/details/azure-openai/)
was fetched without authentication at **2026-10-27T03:36:01.516235Z**. It lists
Sol tiers and cache-write rows, but the fetched numeric cells are dynamic `$-`.
The [Azure Retail Prices API](https://prices.azure.com/api/retail/prices) returned
HTTP **200** at **2026-10-27T03:40:50.581942Z** for this exact query:

```text
api-version=2023-01-01-preview
currencyCode=USD
$filter=productName eq 'Azure OpenAI GPT5' and contains(skuName, '5.6 sol ') and armRegionName eq 'eastus2'
```

The complete filtered response has **32** items and `NextPageLink: null`,
**19709** bytes, SHA256
`cb082605ed3e2998f99762fcc94ae3f7c55bbe09369a92c083c6b7ec243674e1`.
The following rows are **Standard Global**, `Std Gl`, **USD per 1M tokens**,
`Consumption`, effective **2026-09-01** in `eastus2`:

| Context tier | Input | Cached input | Cache write | Output |
| --- | ---: | ---: | ---: | ---: |
| `ShortCo` | $4 | $0.4 | $5 | $20 |
| `LongCo` | $8 | $0.8 | $10 | $30 |

These are public list prices, not an invoice or a tenant-specific quote. The
owner's inventory reports GlobalStandard; this task did not refresh the
deployment SKU through management APIs. The consulted sources do not settle
Sol's short/long switching rule or the provider's cache-write usage-to-meter
mapping. An SDK cache-write counter does not establish that mapping. Exact
model-name queries returning no rows were followed by the API's actual spaced
SKU vocabulary; they were not treated as proof that Sol is unavailable.

The effective grading tariff therefore remains unverified.
`model_price_table.json` and `gpt56_pilot_usd_budget.grading_prices` are unchanged:
Sol grading still refuses with `usd_price_contract_unverified`. The new test
checks that this reference does not waive that refusal. Earlier reference
amounts and historical cost calculations have not been repriced using this
lookup. The USD 200 guard remains a modeled reservation limit, not a verified
combined bill, tax/service-charge limit or server token guarantee.

## All eleven launch requirements after this change

The table classifies complete closure, not whether another free investigation
is possible. Local assembly rows still require approved inputs and complete
upstream bundles; they are not permission to download inputs or run a model.

| # | Existing blocker | State and remaining condition |
| --- | --- | --- |
| 1 | `foundry_account_project_deployment_identity_unverified` | **Resolved for the approved configured route** by the source-held reference and runtime target match; no fresh management/served claim. |
| 2 | `foundry_served_model_version_unverified` | **Owner/provider evidence needed**: retained served model is null and version is absent. |
| 3 | `max_and_long_1m_capability_unverified` | **Owner/provider evidence needed**: no retained Max or applied-1M response evidence. |
| 4 | `native_call_and_token_limits_unresolved` | **Owner/provider evidence needed** for complete server-token/usage contract; existing client counters, estimates, timeouts and unknown-usage refusals remain. |
| 5 | `prepared_input_bytes_unverified` | **More free local work possible**: prepare and bind the approved five-task input bytes once upstream evidence is available. |
| 6 | `live_inference_identity_and_wire_unverified` | **Owner/provider evidence needed**: an actual pilot session witness, not this historical connection or fixtures. |
| 7 | `pilot_dispatch_and_grading_identity_not_wired` | **Owner review needed**: frozen grader source mismatch still refuses compilation; no repinning in this task. |
| 8 | `foundry_usage_and_tariff_mapping_unverified` | **Owner/provider evidence needed**: effective context tier and cache-write meter mapping; public numeric rates alone are insufficient. |
| 9 | `native_sandbox_and_result_bundle_host_unverified` | **Owner execution evidence needed**: an actual session-owned workspace/result witness. |
| 10 | `actual_pilot_deployment_not_prepared` | **More free local work possible**: assemble the inert config/deployment bundle after approved upstream bundles; no Azure deployment creation. |
| 11 | `prepared_request_capture_unverified` | **More free local work possible**: capture the exact prepared requests after the input/config/deployment bundles. |

## Offline validation and scope

At the fixed code, one related-selector invocation passed **379** unique test
cases, **0 failed/errors/skipped**, exit **0**. Pytest took **638.81 seconds**;
the outer wrapper took **639.388 seconds**. It includes the earlier native/budget
selector, the **24** new connection cases and targeted existing
wire/deployment/preflight contracts. Runtime fixtures use a synthetic approved
selection and local inputs; the real matcher and byte validators run. The real
pinned reference and current reviewed Git blobs are checked separately in the
source-registration test. No live target or served capability is validated by
the fixtures.

The preliminary new selector passed **24** cases in **82.20 seconds**, exit
**0**, after an initial fixture dependency import error. That preliminary run
and the earlier **961** passes are not pooled with the final **379**. The latter
is a related-suite result, not a provider, integration or full-project-suite
claim. Evidence, exact selections, logs, JUnit and timings are retained under
`/tmp/p5-native-identity.MpFccK/`.

The explicit source/reference plan-only command at the fixed code returned
**exit 2 / 3.314 seconds**, `configuration_valid: true`, `source_verified`, and the ten blockers
above. The absent-option behavior still retains all eleven default blockers.
The source checks require a clean committed HEAD; a documentation-only final
commit receives its own source-held plan-only recheck in `final-preflight.json`.
