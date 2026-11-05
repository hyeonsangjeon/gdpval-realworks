# Pinned AHP session and native thread refusal diagnostics

Run `41988498753` passed both metadata GETs and authentication, but the observer
refused `thread/start` before forwarding it. The old records contain only
`session_policy_thread_contract_refused`, not its offending parameters. **The
specific live mismatch is not established.** This change adds evidence only;
it does not repair model selection, accept a default, or relax admission.

All upstream references below use VS Code commit
`2c33b50b16c472efe58357d1d2a8a5414bc23fbf`, whose generated protocol is from
Codex SDK **0.163.0**. The official [App Server lifecycle](https://developers.openai.com/codex/app-server/#lifecycle-overview)
separates creating a thread from starting a generation turn. The pinned schema,
not a newer documentation example or model, governs this probe.

## Two contracts, not one

`CreateSessionParams` requires a client-chosen session URI. `provider`,
`workingDirectories`, `config`, `activeClient` and `progressToken` are optional.
Our request fixes provider=`codex`, one workspace and the five configuration
values below. **There is no top-level `model` field** in this AHP command.
`protocolServerHandler.ts:2152` forwards config to the agent; :2161 forwards a
model only for the separate import-conversation path, which this probe does not
use. No guessed top-level model key, alias or permission preset is introduced.

The generated `ThreadStartParams.ts:23` makes model/provider, approval, sandbox,
permissions and config optional, and allows null for most of them. `config` is
a generic JSON-value map. `permissions` and `sandbox` cannot be combined.
Our zero-turn guard is deliberately stricter: explicit Sol/provider/approval,
one exact read-only representation, disabled web search, and no model fallback.
An SDK-valid null/default is not automatically acceptable to this fixed probe.

## Field-by-field comparison

The AHP values below are present in the last run's resolver result and creation
request. Native values marked **expected** are source projections, not recovered
parameters from the rejected live request.

| Field | Pinned contract / consumer | Probe requirement and refusal candidate |
| --- | --- | --- |
| AHP `channel`, `provider`, `workingDirectories`, `config` | `channels-session/commands.ts:47`; `protocolServerHandler.ts:2152` | One session, `codex`, one workspace, exact five keys. These passed local AHP validation; the refusal was later at native IPC. |
| Native `model` / `modelProvider` | Optional nullable strings: `ThreadStartParams.ts:24`; selection `codexAgent.ts:1856,1890,5349`; explicit thread overrides :6166 | Guard requires `gpt-5.6-sol` / `vscode-proxy`. Highest-priority candidate: missing AHP model selection chooses the catalog's first model, independently of native launch defaults. |
| `codex.approvalPolicy` → `approvalPolicy` | Agent enum `never`, `on-request`, `untrusted`: `codexAgent.ts:415`; SDK also permits granular policy: `AskForApproval.ts:9` | Sent `untrusted`; expected native `untrusted`. Raw read-only axes survive `codexSessionConfigKeys.ts:132,148`. A changed/default/preset value would be rejected. |
| `codex.sandboxMode` → `permissions` or `sandbox` | SDK sandbox enum: `SandboxMode.ts:9`; mutually exclusive named profile: `ThreadStartParams.ts:38`; conversion `codexLaunchConfig.ts:56` | Sent `read-only`. Expected `permissions=vscode-workspace-read-only` and **absent** sandbox; the other accepted representation is `sandbox=read-only` with absent permissions. Null is not absent. Customization may override the profile at `codexAgent.ts:6170`, so the actual selected profile is a candidate. |
| `codex.networkAccessEnabled` | Boolean config, `codexAgent.ts:522,2011`; profile inheritance `codexLaunchConfig.ts:39` | Sent false; the read-only profile inherits network disabled. No invented top-level `networkAccess` request field. Effective network still requires an SDK thread report, never a profile-name inference. |
| `codex.webSearchMode` → `config.web_search` | Agent enum disabled/cached/live: `codexAgent.ts:453`; thread assembly :6128 | Sent disabled; expected disabled. Missing or any other value is rejected. |
| `codex.modelReasoningEffort` / `config.model_reasoning_effort` | Agent config :466, effort selection :1948; turn options :2028; native thread config :6127 | Sent max, native launch also requests max. Thread config may omit this override; if present it must equal max. Null or another effort is rejected. No turn is sent to force effort evidence. |
| `config.model_context_window` | Native launch requests 1000000; per-model override `codexAgent.ts:1969` only applies catalog-offered sizes | Absent is allowed; if present it must be numeric 1000000. In the last catalog, Sol's **1M label meant 922000**, with maxContextWindow=1050000. Do not equate any of these values or replace the fixed request. |
| `allowProviderModelFallback` | Optional boolean, `ThreadStartParams.ts:29` | Absent or false only; true/null rejected. No fallback is enabled to get past the guard. |
| `config.mcp_servers` | Generic config; per-session construction `codexAgent.ts:6120,6134` | Zero entries only. The last native status list was empty and GitHub MCP was observed disabled, but rejected thread parameters were not retained. Names/URLs are not diagnostic output. |
| RPC id / result / error | Generated client request frame | id type must be string/number; result/error must be absent. These are also checked and now explained without logging payloads or identifier values. |

## Why native launch configuration is insufficient

The last run's SDK `config/read` reported Sol / max / 1000000 as base
configuration. That does not bind AHP's chat selection. The pinned
`_defaultModel()` at `codexAgent.ts:1856` chooses `models[0]`, and
`_resolveCreationModel()` at :5349 uses it when no selection is provided.
The last advertised catalog began with
`@provider=vscode-proxy:gpt-5.3-codex`, not Sol. The thread call then explicitly
passes the resolved model/provider at :6166, overriding native defaults.

This is a concrete source-level risk, not proof of which fields appeared in the
blocked packet. Security-profile customization and nullable/optional fields
also need the actual boundary values. The guarded model/policy request is left
unchanged until that evidence is available and a source-supported selection
path can be established. In particular, accepting the first model or a 922000
context would change the fixed conditions and is not a fix.

## Artifact shape and privacy

The unchanged refusal predicate now calls a diagnostic-only projection before
the same `blocked()` throw. Its `wire-capture.json.records` entry includes:

- `rejected_fields`: every failed guard field/composite rule, in guard order;
- `rejections`: `{field, expected, actual}` for each failure;
- scalar actual values with explicit types, distinguishing absent, null, false,
  strings and numbers; both sides of the exclusive sandbox/profile rule;
- MCP entry counts and RPC-field presence/type, never their payloads.

The projection does not authorize or modify a request, acquire a thread claim,
send a response/turn, or add network I/O. It passes through the existing seeded
redactor **before persistence**. Long values are entirely replaced rather than
truncated; nested objects/arrays are not dumped. No prompt, working directory,
tool body, credential, MCP URL, or raw rejected frame is retained. The failure
remains a failure and cannot become applied-setting evidence or admission.

Tests run the real observer against fake stdio/fetch. They cover individual and
multiple mismatches, the prior catalog's non-Sol default as a **synthetic**
counterexample, null versus absent, both read-only representations, typed
context, optional exact values, redaction/encoded credentials, and artifact
retention. Prior allowed cases retain byte-for-byte forwarding; rejected cases
have zero native writes, zero claim consumption and zero provider calls.

## Pinned source links

- [AHP creation fields:47](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/common/state/protocol/channels-session/commands.ts#L47), [handler:2152](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/protocolServerHandler.ts#L2152).
- [ThreadStartParams:23](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadStartParams.ts#L23), [AskForApproval:9](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/AskForApproval.ts#L9), [SandboxMode:9](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/SandboxMode.ts#L9).
- [Model selection:1856](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L1856), [thread construction:6109](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L6109).
- [Permission normalization:132](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexSessionConfigKeys.ts#L132), [read-only profile:56](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexLaunchConfig.ts#L56).
