# Native pilot hard token cap contract

## Prospective client precheck, 2026-10-26

The owner's 23:40 KST direction is implemented at code
`48632cd7c0b687051816b53723592e43de4831e2`. The attempt-owned loopback now
checks a request before constructing its upstream connection or reserving a
native forward. **This is a client admission check, not a verified server hard
token limit.** The existing post-usage stops remain in place.

| Check | Implemented behavior | Remaining boundary |
| --- | --- | --- |
| 300,000 input tokens per attempt | Compare the outgoing JSON's UTF-8 byte length, at one estimated token per byte, with the remaining input allowance. | A deliberately conservative heuristic, not a Sol tokenizer, measured consumption or a proven token upper bound. It includes serialized controls/tools and may reject valid requests. Provider rendering overhead is not established. |
| 10,000 output tokens per attempt | Require a positive integer `max_output_tokens` no larger than the remainder. Insert the remainder when the field is absent on supported `/responses` JSON; reject larger or invalid fields instead of clamping them. | The proxy can supply the field. Foundry Sol's acceptance and server enforcement remain unverified. |
| Usage between requests | Sum complete response-body totals once; use cumulative SDK totals as a floor, not an additional sum. Serialize requests until the prior response is settled; unknown usage blocks the next forward. | Missing, partial, failed or conflicting completion/usage evidence makes the remainder unknown. A later SDK sample cannot reopen it. |

Unknown or unsupported requests stop before upstream effects: opaque/remote
context, encrypted reasoning, image/file inputs, hosted tools, encoded bodies,
malformed/duplicate-key JSON and `/responses/compact`. The last route has no
established output-limit field here. This can stop an otherwise valid Codex
session; live compatibility has not been tested. No tokenizer or dependency
was installed. Request inspection is capped at **1 MiB**; the existing response
inspection limit remains **256 KiB**, with **64-KiB** transport chunks.

The receipt keeps `token_hard_limit_enforced=false` and adds
`runtime_caps.client_token_precheck`: enabled state, checked/blocked counts,
the named estimator, accounted usage, remaining allowances and the last
estimate/output limit. Its `server_hard_limit_verified` also remains false.
Unknown usage and remainders are null. Raw bodies, headers and errors are not
published. The existing stop/SDK cleanup path handles the fixed refusal codes:
`native_input_token_precheck_exceeded`, `native_output_token_precheck_exceeded`,
`native_output_token_limit_unavailable`, `native_token_request_unverified` and
`native_token_usage_unverified`. Closed receipts cannot be changed by a late
refusal; the regression was reproduced before correction and then passed.

The new `gpt56_sol_foundry_codex_pilot_source_20261026_token_precheck.yaml`
changes only the wire/preflight source pins relative to the sealed bindings
predecessor. All non-source plan fields, previous registrations, caps, models,
host/judge identities, retry policies and finite rights are preserved. Source
selection still verifies held Git blobs, actual imported paths and final
rechecks; the predecessor is included in those rechecks.

Two disjoint offline groups at the same code HEAD report **187 + 282 = 469
passed**, **0 failed/errors/skipped**; **214** host/external-receipt cases were
deselected. Plan-only validation reached `source_verified` and `inspect_plan`,
with `configuration_valid=true`, exit **2**, and **11** unchanged launch blockers.
The [current record](../../tasks/LATEST_TASK_RESULT/README.md) separates these
results from the two interrupted verification runs and the pre-fix regression.
No model call, paid execution, grading, dispatch, push or PR occurred.

The [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
describes the generic per-response `max_output_tokens` field, including
reasoning output. It is not a version-bound Foundry Sol hard-limit contract.

## Prior fixed-source server-contract investigation

The following investigation and its no-implementation/no-online-read statements
are retained at their original source; they do not describe the new client code.

At source `af685f5c4a436a7f476a41c5cf4f44a702c0a67d`, this offline investigation
does **not establish server-enforced token caps** for the registered Foundry
GPT-5.6 Sol pilot through Codex SDK/CLI **0.147.0**. Both attempt limits remain
client checks of reported usage. No request field, runtime source, plan, cap,
registration, dependency or workflow was changed.

## Verdicts for the existing attempt limits

| Limit | Current classification | Evidence and unresolved condition |
| --- | --- | --- |
| 300,000 input tokens per attempt | **Client post-check only** | `gpt56_pilot_wire_receipt.py:482` checks reported totals and stops with `native_input_token_cap_exceeded`. No configurable input-reservation field was established in the inspected request schemas. A model context window is not the sum of input tokens across native requests. |
| 10,000 output tokens per attempt | **Client post-check only** | The same method stops with `native_output_token_cap_exceeded` when the reported total exceeds the limit. The generic OpenAI schema documents a per-response `max_output_tokens`, but its passage through this Codex runtime and enforcement by Foundry Sol remain unverified. It does not by itself bound the attempt's sum. |

Neither verdict means that the service can never support a hard limit. It means
the evidence required to implement one on this fixed path is missing. The
receipt correctly retains `token_hard_limit_enforced=false`
(`gpt56_pilot_wire_receipt.py:149,677`). Stopping after provider work cannot undo
tokens already consumed. Unknown usage stays unknown; cached and reasoning
subcounts are not added a second time.

The existing native request caps, **32 per attempt / 128 per task / 640 per
pilot**, and **1,800-second** attempt deadline are unchanged. The monetary cap
remains null. No execution right was consumed, restored or retried.

## What was inspected

The already installed packages were used without installation or downloads.
Here `P/` means
`/ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/lib/python3.10/site-packages/`.
The SDK and binary distributions each declare version **0.147.0** in their
`METADATA:2-3`; `codex_cli_bin/codex-package.json:3` also declares that version.
The bundled binary's `--version` returned `codex-cli 0.147.0`.

`P/openai_codex/client.py:241-267` starts the packaged Rust CLI as
`app-server --listen stdio://` and passes `--config` configuration overrides. Python
then speaks the app-server protocol. It does not construct provider Responses
requests with the separate `openai` Python client.

| Setting or field | Pinned local evidence | What that evidence does not establish |
| --- | --- | --- |
| `model_context_window` | `P/openai_codex/generated/v2_all.py:8952` and the generated `v2/ConfigReadResponse.json:353` declare a nullable integer. Repository `core/codex_runtime_config.py:1096-1142` validates and passes the requested override and explicitly excludes a spend-cap interpretation. | A provider request field or an arbitrary server-enforced input budget. Changing the registered context request to 300,000 would not implement its cumulative input limit. |
| `model_auto_compact_token_limit` | SDK `generated/v2_all.py:8950` and generated `v2/ConfigReadResponse.json:336` declare a nullable integer. | A server token reservation, a transmitted maximum, or a cumulative attempt ceiling. This configuration/readback shape is not a provider request schema. |
| `model_max_output_tokens` | Not a declared field in the inspected SDK `Config` or generated app-server `Config`/`TurnStartParams` schemas. | Global rejection or universal absence of this key: `Config` allows additional properties, and thread start accepts an arbitrary config object. Accepting a key is not proof that the Rust sender uses it. |
| `max_output_tokens` | The separate installed OpenAI Python **2.46.0** schema, `types/responses/response_create_params.py:103-108`, describes an upper bound on one response's visible output plus reasoning tokens. Its `resources/responses/responses.py:1004-1013` serializes this field into a `/responses` body. | This is not the Codex Rust sender. It establishes neither Codex forwarding nor a model-specific Foundry guarantee nor a sum across the attempt. |
| `max_input_tokens` / a turn token reservation | Neither this field nor `max_output_tokens` is declared in SDK `TurnStartParams` at `generated/v2_all.py:8638` or the binary-generated experimental turn-start schema. | A supported input-budget contract elsewhere in the service, or a guarantee that arbitrary config keys are rejected. |

The wheel file inventories contain the Python SDK and compiled CLI, not the
Rust provider serializer source or the full `ConfigToml` schema. The binary's
offline schema generator supplies the app-server protocol, including its
extensible configuration readback; that is not the missing provider schema.
Bounded binary-string inspection found the context/compaction names and
`max_output_tokens`, including in tool-output contexts. String presence alone cannot show
which fields the provider serializer emits. No real CLI turn or request capture
was used to fill this gap.

The current loopback recorder forwards request body chunks without decoding or
changing their JSON (`gpt56_pilot_wire_receipt.py:565-578`). That code establishes
that the recorder adds no token-cap field; it does not establish every field
the upstream Rust CLI might already generate.

## Foundry and aggregate boundaries

The local Microsoft `azure-ai-projects` **2.3.0** source describes a wrapper
around the `openai` client (`P/azure/ai/projects/_patch.py:207-230`). This is not
a versioned hard-cap contract for the pilot's **direct-v1** account endpoint
and **gpt-5.6-sol** deployment. No child-project ID is requested here.
The inspected `codex_foundry_connection.md` connection note and
`docs/first-experiment.md` guide supply no such contract. Statements about a
different reporting path or a configured model label cannot establish the
pilot's provider behavior.

No official online document was fetched under the offline order. Foundry Sol's
acceptance and enforcement of `max_output_tokens`, including reasoning tokens,
remain **unverified in the inspected local evidence**. This is not a finding
that the deployment or account is unavailable. Deployment TPM/quota controls
are **owner/external** matters; a rate quota is not this attempt's token budget.

Even a supported per-response output maximum would need an evidence-backed
remaining-budget rule across native requests to enforce the existing attempt
limit. A fixed 10,000 on every request would not suffice. Missing usage,
incomplete responses and concurrent requests must not reopen that budget.
For input, `response_create_params.py:303-310` describes truncation or rejection
at a model context window, not an arbitrary cumulative input allowance.
Compaction, context size, token estimates and byte counts are not substitutes.
The earlier rejection of an unverified Sol tokenizer estimate remains in force.

The next prerequisite is an approved evidence package that binds the fixed
Codex provider serialization path and the exact Foundry Sol API/version to the
claimed hard-limit semantics. Only then can a request guard validate the field
and remaining allowance before transmission. No implementation, trial request
or permission to gather live evidence is inferred from this investigation.

## Offline evidence and validation

Evidence is retained at
`/ai-work/copilot/_tmp/p5-native-hard-token-contract.aOpcll/`.
`invocation.txt` records the bounded package/schema commands.
`package-hashes.sha256` records the installed evidence files. The **258278208-byte**
CLI binary has SHA256
`cb0a15567e9a60a5820d54b0f6ae86d504dc3805c1eab21a47f70e3eb7b73a40`.

The existing binary ran `app-server generate-json-schema --experimental --out`
under **env -i / TERM60s / KILL5s**. It exited **0** in **0.041 seconds** of
Bash wall time; stdout/stderr were empty. This is schema generation, not a
test suite, model call, app-server session or provider observation.

| Generated file, relative to `app-server-schema/` | Bytes | SHA256 |
| --- | ---: | --- |
| `v2/ConfigReadResponse.json` | 21726 | `448bc42d33055b6ed2ffdccb2bbda3914047518def4f333c996a32ea24c4c8ef` |
| `v2/ThreadStartParams.json` | 12725 | `18e546303ecfe878b179a50da73e6fb99f634be4bc3f7650d5870f31787079b2` |
| `v2/TurnStartParams.json` | 19160 | `95f35a9f01beea390cc4e478b4030e46ef37e5d769438d50f40b7aeabbf1ad74` |

`schema-observations.json` preserves the inspected properties and explicit
missing-field results, SHA256
`668e3bddf8dde7244601ef9bf0a17764415808d228be46f21d13deb312e36bca`.
Because the outcome is documentation-only, no synthetic test or plan-only
preflight was rerun and no new source registration was needed. There is no
new pytest pass/fail/skip result or JUnit. Prior proofs remain separate in the
[immutable preceding record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/af685f5c4a436a7f476a41c5cf4f44a702c0a67d/tasks/LATEST_TASK_RESULT/README.md).
The existing launch ledger remains **0 cleared / 11 retained / 0 new**;
this is not a fresh preflight verdict. Final-source owner review, CI,
environment approval and separately authorized live evidence remain required.
