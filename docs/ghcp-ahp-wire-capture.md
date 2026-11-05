# GHCP Codex native/CAPI diagnostics — not an admission receipt

This collector preserves the fixed Codex harness, GPT-5.6 Sol (not Fast), Max,
1,000,000 context request and existing policy/admission checks. It does not
replace `policy_rejections` or `require_verified_connection`. Even complete,
matching synthetic evidence cannot open the connection or five-task gate.

## Authenticated zero-turn dispatch

The existing fixed-five workflow has a separate `authenticated_zero_turn`
boolean input, default false. It requires `execution_adapter=ahp-draft`,
`dry_run=true`, `execute_paid=false`, `connection_only=false` and
`capability_only=false`. Only `ahp-zero-turn` uses the `ghcp-sol-gate`
environment in this mode. The dry five, paid five, one-turn connection, cohort
plan and grading jobs are skipped. The ordinary push probe stays unauthenticated.

The authenticated job reads `COPILOT_GITHUB_TOKEN` only on the hosted runner,
then removes it from the driver's environment. The value is not a command-line
argument or file. The child receives only an in-memory observer redaction seed,
removed before native spawn. AHP receives one exact `authenticate` request for
`https://api.github.com`, after verifying Codex advertises that resource.
The five source-defined policy keys and Sol/max/1M native launch settings are
unchanged. No new alias, preset or fallback is accepted.

This mode still uses a loopback-only kernel network namespace, an isolated PID
namespace, dropped privileges, the strict session-only native observer and a
120-second overall runtime deadline. Authentication does **not** permit token
exchange, model catalogs or other HTTP: every Agent Host fetch is blocked before
the original fetch is called. A watchdog stops the owned host on the first
blocked boundary or turn/tool/CAPI event, including while authentication waits.
The AHP client checks that watchdog before sending and after receiving each RPC.
There is no retry or second session/thread. Cleanup is mandatory on every exit.

The allowed AHP sequence is initialize → authenticate → resolveSessionConfig →
createSession → subscribe → disposeSession (at most six requests). Per-thread
reports alone populate `thread-policy.json` and `handshake.json.observed`;
`wire-capture.json` retains their native provenance. Missing values remain
`not_reported`. Echoes and `config/read` are not application or served-model
proof. These diagnostic schemas cannot satisfy the paid connection receipt.

Authentication itself may require HTTP. In the pinned harness,
[codexAgent.ts:1634](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L1634)
resolves GitHub MCP configuration before storing the token and queuing model
refresh. Such an attempt is recorded with a nonsecret destination category and
`forwarded=false`, fails this zero-HTTP mode, and is not silently allowed just
because it is not a model turn. Even a safe thread reply need not provide every
applied field; admission stays closed for missing/mismatched values.

The [official app-server lifecycle](https://developers.openai.com/codex/app-server/)
distinguishes thread creation from `turn/start`. The pinned GHCP integration,
not that general guide, determines this adapter's authentication and policy
parameter paths. Offline tests cover both the real workflow routing expressions
and real RPC/parser/export paths with only fake process, wire and provider data.

## Runtime collection

`ghcp_ahp_wire_capture.py` verifies the original SDK archive, the extracted
native binary, and the original source archive against the existing manifest.
It does not patch or replace the pinned VS Code/SDK files. A separate
SHA256-bound Node preload, `ghcp_ahp_wire_preload.cjs`, observes two boundaries:

1. The existing Codex `app-server` child: exact native stdin JSONL requests and
   stdout replies/notifications, including RPC IDs and stream identity.
2. Agent Host's original `fetch` call for the GHCP Responses endpoint: request
   body and headers, response status/headers, original SSE events or JSON body.

Native bootstrap discovery reads the installed wrapper's `optionalDependencies`
and the bundled platform package's `os`/`cpu` and `codex-package.json` entrypoint.
Package metadata and executable bytes must match the pinned SDK archive. The
resolver also inventories installed/archive candidates, refuses ambiguity,
missing declared entrypoints, symlinks, unsigned files and hash/size drift, and
never runs a package launcher to discover a binary. `bootstrap.native_binary_discovery`
records every attempted candidate and its status; a refusal carries the same
record in `probe.json` (or the connection receipt) with its original reason code.

The public 0.163.0 package declares `entrypoint: bin/codex`; its native ELF is
296,865,480 bytes. The earlier `/codex/codex` and 256 MiB native-size assumptions
were incorrect. Compressed download bounds and archive SHA256 stay unchanged;
native bytes must have the verified archive's **exact** size and SHA256, within
the existing **2 GiB whole-archive expansion limit**. Tests use an independently
recorded public package inventory, not a path copied from the resolver.

`ghcp_ahp_errors.Refused` is shared by the standalone CLI and imported modules.
Loading the probe as `__main__` no longer creates a second exception type that
hides a bootstrap code behind the generic class name `Refused`. Arbitrary
exception messages are still not written to artifacts.

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
The original `--capability-only` mode still uses two AHP RPCs and no session.
The push probe now explicitly selects the bounded `--session-policy-probe`
described below. Neither mode authenticates or inherits credentials, and both
retain kernel-denied external egress. Partial native packets are refused before
forwarding, including packets completed by EOF.

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
SDK/observer/source drift, the original zero-session mode and the bounded
session-only mode's zero-turn/provider-HTTP guards.

The push artifact includes `wire-fixture.json` (explicitly synthetic, five cases)
and `wire-capture.json` (real model-free observer/session-attempt evidence, with
unobserved applied/provider fields left missing). The latter must show the
observer installed in the actual Agent Host child, not merely its parent.
No fixture artifact is a live connection receipt or a paid launch permission.

## Backend startup diagnostics

Run `41931364159` reached the supervisor, but not the Agent Host observer. Its
`-15` supervisor exit was recorded **after cleanup**, not evidence of a backend
crash. The pinned supervisor captures backend stdout/stderr at
[debug level:389](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/cli/src/tunnels/agent_host.rs#L389)
and [405](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/cli/src/tunnels/agent_host.rs#L405),
which the previous info-level receipt omitted. Its
[30-second fallback:419](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/cli/src/tunnels/agent_host.rs#L419)
sets `ready=true` even without the listening message; the subsequent "Server
ready" banner is therefore not backend readiness proof. That explains a
misleading readiness signal, **not the original startup delay**.

The capability-only probe now selects the advertised `--log debug` option and
retains `backend-startup.json` before the invocation-owned temporary tree is
deleted. It contains redacted supervisor/backend output, allowlisted VS Code
startup logs, pre/post-cleanup supervisor status, descendant process state/exit
status when reported, socket arguments and directory metadata. Missing exit
status stays null. A post-cleanup SIGTERM is never promoted to a spontaneous
exit. The original WebSocket/bootstrap error stays first in `probe.json`;
observer/diagnostic/cleanup errors are secondary and still fail closed.

Collection is bounded to 512 tree entries/errors, 32 owned processes, and 12
allowlisted logs of 128 KiB each. Truncation/read races are explicit. Symlink
directories are not followed; symlinks, sockets and FIFOs are never read as log
content. `/proc` reads follow only the supervisor's descendants, retain only
socket-path command arguments, and never read `environ`. No credential store or
configuration content is read. The collector opens no socket and starts no
process. Its JSON is diagnostic-only (`admission_allowed=false`).

The upstream binaries and their 30-second fallback, the 180-second probe limit,
network/PID isolation, source/SDK pins, zero-session RPC allowlist, and paid
fail-closed gates are unchanged. Only the push-trigger Actions probe runs a real backend;
NAS tests use inert processes, synthetic filesystem/proc entries and fake RPC.

## Exact Agent Host fork contract and positive readiness

Run `41941392305` retained the real `wire_agent_fork_refused` stack at the old
preload line 156, but **did not retain the rejected fork arguments**. Its directory
inventory plus pinned source reconstruct the request; this is not relabeled as
an observed request. The regression fixture explicitly records that limitation.

| Field | Pinned runtime contract | Previous check |
| --- | --- | --- |
| Node executable | Installed `server/node`, byte-identical to the pinned server archive | Not separately checked at this fork |
| Module request | `server/out/bootstrap-fork` (no extension); Node resolves the pinned `bootstrap-fork.js` | String comparison required the `.js` suffix |
| Arguments | `--type=agentHost --logsPath <one current log directory> --user-data-dir <state>/server-data/data --telemetry-level off` | Array shape only |
| Extra options | Empty original `execArgv`, exact entrypoint/SDK/socket environment, no `execPath`/`NODE_OPTIONS` override | Not an exact argument contract |

The pinned [caller:181](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/nodeAgentHostStarter.ts#L181)
passes an extensionless module to
[Node fork:207](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/base/parts/ipc/node/ipc.cp.ts#L207).
The caller's [argument vector:145](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/nodeAgentHostStarter.ts#L145)
uses server data, not the supervisor's endpoint-registry directory. The
[server default:42](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/server/node/server.main.ts#L42)
adds `/data`; the [logs getter:73](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/environment/common/environmentService.ts#L73)
selects one timestamp directory there.

Installation now verifies Node, server-main and bootstrap-fork bytes against the
unchanged pinned archive. The preload accepts only the exact extensionless
request resolving to that verified file and the exact argument vector. The logs
directory is the single existing directory of this invocation, not a wildcard
or a clock guess. Different paths, aliases, shadow files, options, environment
bindings, symlinks, extra/missing/reordered arguments and file drift refuse
before the original fork. Every attempt now records masked actual versus
expected fields and mismatch names, including on refusal; unknown credential
flag values are redacted before persistence. Non-matching forks are not passed
through. Model/HTTP guards and admission checks are not relaxed.

After the lazy WebSocket handshake, both instrumented probe modes require
the real [listener-bound signal:683–687](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/agentHostMain.ts#L683)
and the exact registered Unix socket within this invocation. The supervisor's
"Server ready" banner does not count. Missing, truncated, conflicting or
post-timeout evidence refuses **before the first AHP RPC**, even if a transport
handshake succeeds. No startup timeout increase, new readiness sleep, vendor
patch, session or model request is added by this readiness check. `backend_readiness` records the
decision; a positive result only proves the local listener, not model settings.

## Bounded session-policy probe: request is not application

`ghcp_ahp_thread_policy.py` sends the five exact internal Codex keys through
`resolveSessionConfig.config` and `createSession.config`. The pinned resolver
preserves these raw values even though the public schema does not advertise
them. No alias, `codex.permissionsPreset`, unknown model field, or copied
server-default preset is sent. The source path is:

| Setting | Pinned consumer in `codexAgent.ts` | Native boundary / observation |
| --- | --- | --- |
| `codex.approvalPolicy=untrusted` | raw permission resolution at 2002; thread call at 6169 | `approvalPolicy`; SDK response `approvalPolicy` |
| `codex.sandboxMode=read-only` | 2002, 2011; thread call at 6170 | harness-owned permission profile; SDK `sandbox` is checked, never inferred from its name |
| `codex.networkAccessEnabled=false` | 2011–2015 | profile network setting; SDK `sandbox.networkAccess` |
| `codex.webSearchMode=disabled` | 6128 | `thread/start.config.web_search`; no applied field in the pinned thread response |
| `codex.modelReasoningEffort=max` | 1948–1954, 2035–2047 | final turn effort/collaboration settings; initial SDK effort is a separate observation |

These are source-defined keys in
[`common/codexSessionConfigKeys.ts:17`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/common/codexSessionConfigKeys.ts#L17).
The [resolver at 9254](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L9254)
preserves them; the [AHP creation handler at 2152](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/protocolServerHandler.ts#L2152)
forwards `config`. **AHP `CreateSessionParams` has no `model` field.** Sending one
would not select a model, so this client explicitly rejects that shape.

Sol/Max/1M instead use the existing supported native-launch configuration:
`model="gpt-5.6-sol"`, `model_provider="vscode-proxy"`,
`model_reasoning_effort="max"`, `model_context_window=1000000`.
[`agentService.ts:371`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/common/agentService.ts#L371)
defines the JSON argument environment; `codexAgent.ts:2682–2685` passes it to
`buildCodexLaunchConfig`, and the generated native `Config.ts:28,33` defines
these exact keys. These are **requests**, not evidence that a session selected
Sol or that a provider supports 1M. The native guard rejects a different
thread model/provider or an enabled fallback; it never substitutes a model.

The AHP sequence has at most five requests: initialize, resolve, one creation,
subscribe and dispose. A known upstream refusal is recorded verbatim without
retrying or using a turn to force startup. A created session waits at most ten
seconds (within the existing 180-second runtime limit) for prewarm evidence,
then is disposed. `codexAgent.ts:6274–6305` shows that prewarm can create a
thread without a message when its prerequisites are met; session creation alone
does not prove a native thread exists.

The dedicated `session-only` observer permits at most one exact `thread/start`
and cleanup of that returned thread. A shared exclusive claim survives native
or observer restarts. It rejects turn/resume/fork/command calls, foreign
cleanup, model fallback, mismatched security inputs, and incoming turn/tool
events before forwarding. It checks the four native launch overrides before
spawning the SDK. It blocks **all fetch calls before the original function**,
including catalog/auth HTTP; external egress remains kernel-denied. Local AHP
WebSocket handshakes are not provider/CAPI calls. No credential is read or
accepted by this mode.

`thread-policy.json` separates requested policy/model, resolver/session result,
native thread reports, report origins and missing/mismatched values.
`admission_allowed` requires every typed requested value to match real,
bound observer evidence, a successful session and no safety violation.
Requests, schema advertisements, config echoes, process-wide `config/read`,
foreign-thread reports and synthetic fixtures cannot fill missing applied
values. Native model/provider are configured values, never served-model proof.
The pinned thread schemas do not report applied web-search mode, and CAPI
responses are deliberately absent here, so neither value is invented.

**CI success means the diagnostic probe completed safely**, not that a session
or native thread was created or that admission passed. Read `session_error`,
`session_created`, `native_thread_responses` and `admission_allowed` together.
Unexpected forbidden activity fails the probe. Authentication/catalog or
missing-evidence refusals do not authorize a model turn. The existing paid
connection schema/admission checks and dispatch workflow remain unchanged.
