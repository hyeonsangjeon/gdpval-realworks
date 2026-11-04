# GHCP Codex native/CAPI diagnostics — not an admission receipt

This collector preserves the fixed Codex harness, GPT-5.6 Sol (not Fast), Max,
1,000,000 context request and existing policy/admission checks. It does not
replace `policy_rejections` or `require_verified_connection`. Even complete,
matching synthetic evidence cannot open the connection or five-task gate.

## Runtime collection

`ghcp_ahp_wire_capture.py` verifies the original SDK archive, the extracted
native binary, and the original source archive against the existing manifest.
It does not patch or replace the pinned VS Code/SDK files. A separate
SHA256-bound Node preload, `ghcp_ahp_wire_preload.cjs`, observes two boundaries:

1. The existing Codex `app-server` child: exact native stdin JSONL requests and
   stdout replies/notifications, including RPC IDs and stream identity.
2. Agent Host's original `fetch` call for the GHCP Responses endpoint: request
   body and headers, response status/headers, original SSE events or JSON body.

The original native writes, response object, reader results, request arguments,
body, headers and AbortSignal are forwarded. No extra fetch, native request,
session or authentication call is added. Reads observe existing consumption;
there is no response clone/tee with an unbounded second buffer. The observer
does not enable VS Code's unredacted debug-dump environment variable.

VS Code strips `NODE_OPTIONS` when forking Agent Host. Only the exact pinned
`bootstrap-fork.js` with the Agent Host entrypoint receives this reviewed preload
via explicit `execArgv`; arbitrary inherited options are not restored. Diagnostic
bootstrap data and preload options are removed from the native child's environment.

`wire-capture.json` contains masked source records, requested settings, native
request records, applied-thread snapshots, SDK context reports, disk-level
configuration, CAPI request/response reports, integrity errors and provenance.
`bootstrap` binds observer/native hashes; `sources` quotes exact pinned file/line
links from the verified source archive. The receipt includes the JSON SHA256.

Known credentials (including JSON/URL/base64 forms), authorization/cookie values,
private account fields and emails are masked **before trace persistence**. HTTP
headers are the normalized Fetch-boundary headers, not a TCP/TLS packet capture;
automatically added lower-level headers are not claimed. Raw JSON/SSE text is
retained with redactions, not just selected model fields. Arbitrary unknown or
encrypted secret encodings cannot be reliably recognized. No raw host/auth
directory is uploaded. Per-frame bound is 2 MiB; persisted/export bound is
16 MiB, at most 8,192 records per process and 16 process files. Missing/truncated
streams, duplicates, unknown correspondence and failures cannot admit a run.

The existing connection opener installs the observer only after its existing
dispatch/runner/auth checks. A schema refusal still happens before createSession;
its diagnostic export records the absence of native/provider evidence honestly.
The separate push probe uses two AHP RPCs, no authentication, zero session-create
requests and kernel-denied external egress. Its observer also blocks native
session/turn RPCs and model HTTP routes. Partial native packets are refused
before forwarding in model-free mode, including packets completed by EOF.

## Evidence classification

| Item | Captured field/source | Classification and limit |
|---|---|---|
| Requested Sol / Max | native thread/turn requests; CAPI request `model`, `reasoning.effort` | **Request only**; not served identity or final reasoning proof |
| Native model / effort / sandbox / approval / network | `thread/start` reply; `thread/settings/updated.threadSettings`, sandbox `networkAccess` | **Provable as SDK-reported harness settings when present**; a thread snapshot is not independent per-turn or remote-model attestation |
| 1M context | `thread/tokenUsage/updated.tokenUsage.modelContextWindow` | **SDK report only**; null stays `not_reported`; not proof of provider capacity |
| Web search | thread config request `web_search`; disk `config/read` kept separately | **Request only** for effective-thread web search; no effective-thread reply field established, so it remains `not_reported` |
| Served model | CAPI HTTP JSON `.model`, or SSE `response.created/completed` → `data.response.model` | **Unavailable as a proven GHCP contract in this source-only run**. If actually returned, retain it as a provider response report, never synthesize it from the request |
| Response reasoning | HTTP JSON `.reasoning.effort`, or SSE `data.response.reasoning.effort` | **Unavailable as a proven GHCP applied-effort contract here**. A returned configuration report is not independent evidence of internal reasoning performed |
| Headers / usage | request IDs, response headers, token counts, reasoning-token counts | Correlation/accounting only. No documented GHCP served-model/effort header established; reasoning token count does not prove Max |
| AHP `usage.model` | chosen session model passed into the AHP mapper | **Request/selection echo only**, never promoted |

OpenAI's [Responses reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
defines response model and reasoning configuration fields. It is not a guarantee
that GitHub's CAPI returns them, returns them unchanged, or attests the same
semantics. The pinned GHCP client forwards the response; it does not manufacture
these fields. Therefore neither “GHCP always returns them” nor “every CAPI field
is only an echo” is established. A real, separately authorized response is needed.

The diagnostic `response_reported_candidate` classification only identifies
response-body provenance. Non-200, incomplete, malformed or conflicting evidence
is recorded separately. `admission_allowed`, `connection_verified`, `gate_ready`
and `proven_for_live_gate` remain false. Synthetic markers are sticky.

## Exact source pin

All links below use VS Code `2c33b50b16c472efe58357d1d2a8a5414bc23fbf`,
SDK protocol generated from Codex 0.163.0; no newer source is substituted.

- [Agent Host fork identity:95](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/nodeAgentHostStarter.ts#L95), [fork environment sanitizer:205](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/base/parts/ipc/node/ipc.cp.ts#L205).
- [native spawn:2700](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L2700), [thread-settings handling:3561](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L3561).
- [native ThreadSettings:20](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadSettings.ts#L20), [ThreadStartResponse:19](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadStartResponse.ts#L19), [SDK context:11](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadTokenUsage.ts#L11).
- [model effort:1948](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L1948), [authoritative turn effort:2047](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L2047), [web-search request:6128](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L6128).
- [global fetch selection:598](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/shared/copilotApiService.ts#L598), [CAPI Responses request:666](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/shared/copilotApiService.ts#L666), [final Fetch boundary:1126](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/shared/copilotApiService.ts#L1126).
- [upstream response reader:364](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexProxyService.ts#L364), [AHP selected-model echo:3929](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L3929).

## Verification without model execution

`tests/test_ghcp_ahp_wire_capture.py` drives the actual preload with fake spawn,
fork, fetch and streamed Response objects. Tests exercise one-byte splits,
masking, byte/argument preservation, missing/mismatched/conflicting responses,
header/usage echoes, non-success HTTP, incomplete streams, RPC correlation,
SDK/observer/source drift and zero-session/model transmission guards.

The push artifact includes `wire-fixture.json` (explicitly synthetic, five cases)
and `wire-capture.json` (real model-free observer startup/capabilities, with
unobserved applied/provider fields left missing). The latter must show the
observer installed in the actual Agent Host child, not merely its parent.
No fixture artifact is a live connection receipt or a paid launch permission.
