# GHCP-backed Codex Agent Host: model-free hosted probe

This is a candidate-path probe, not the Copilot CLI default-agent gate and
not a Sol benchmark. Its follow-up adds a **refusing AHP draft choice** to the
existing gate; no seal, task input, pricing or paid-run permission is changed.
The owner's 2026-10-29 execution policy is retained: NAS is for
source work and offline fixtures; actual Agent Host startup is Actions-only.

## Pins and execution boundary

- VS Code CLI/server **1.144.0**, release commit
  `2c33b50b16c472efe58357d1d2a8a5414bc23fbf`.
- The pinned server's `product.json` selects the **0.163.0** Codex SDK. Use
  that same public SDK, not a separate Codex CLI/Foundry authentication route.
- [The manifest](../batch-runner/ghcp_ahp_probe_manifest.json) holds exact
  HTTPS URLs, archive sizes and SHA256 values. CLI/server digests come from
  Microsoft's public update metadata. Source/SDK digests were measured from
  the public version-fixed archives; that distinction is recorded.
- [The workflow](../.github/workflows/ghcp-ahp-model-free-probe.yml) runs only
  on push to `leader/ghcp-ahp-probe-20261030`, on `ubuntu-24.04`, with
  `contents: read`, no environment binding, no authentication reference,
  persisted checkout credential, PR trigger or dispatch entry.
- Public downloads and static source checks happen before runtime isolation.
  No downloaded binary is run during preparation. Preseed the verified
  server cache and provide the documented Codex SDK-root setting so the
  runtime does not need to download or update a different distribution.
- The runtime has only loopback, its own PID/mount namespaces, a non-root
  PID-1 controller, no capabilities and no-new-privileges. Its children get
  a new HOME/config/cache and an explicit minimal environment. The CLI's
  transport token is disabled **only inside this private loopback space**;
  this is not permission to expose an unauthenticated host externally.

The only outgoing AHP methods are `initialize`, `resolveSessionConfig`,
`createSession` (`provider=codex`), `subscribe` and `disposeSession`, at most
five requests. No `authenticate`, generic action dispatch, chat creation,
initial message, prompt, turn or tool execution is permitted. An empty session
may succeed before authentication: report that honestly, without claiming
that a model can run. Record an actual `-32007` only if the host returns it;
do not transform a missing-provider/network error into an authentication error.

## What the pinned source establishes

| Question | Source-level finding; runtime proof remains separate |
| --- | --- |
| Headless host | `cli/src/commands/args.rs:238` exposes foreground/new-instance/local binding. `cli/src/tunnels/agent_host.rs:293` starts the packaged server; `:538` permits an existing pinned cache. |
| Codex provider | `src/vs/platform/agentHost/node/agentHostMain.ts:213` registers Codex when enabled; `common/agentService.ts:259` names the documented environment form of that setting. |
| Protocol | `common/state/protocol/common/commands.ts:152` specifies initialization; `channels-session/commands.ts:47` carries the provider and workspace, not a prompt. Protocol source version is 1.1.0. |
| Sol model selection | `common/codexModelSelection.ts:10` maps Copilot to `vscode-proxy`; `channels-root/state.ts:246` supplies `ModelSelection.id/config`. Candidate ID is `@provider=vscode-proxy:gpt-5.6-sol`; availability is **not verified**. |
| Max / 1M | `node/codex/codexAgent.ts:1920` exposes `thinkingLevel` and `contextSize`; `:1974` forwards context only if the model advertises that size. `node/codex/codexSessionConfigKeys.ts:186` accepts `max`. These fields are not applied-setting evidence. |
| Intrinsic caps | No request-before-send turn/tool/model-request ceiling is established by the reviewed Codex config surface. CLI `--idle-timeout` (`cli/src/commands/args.rs:332`) explicitly does **not** cut active sessions. The probe's 180s/zero-prompt limits are not native agent limits. |
| Capture | The protocol defines initial snapshots, ordered chat/tool actions and `fetchTurns`. This probe captures its actual JSON-RPC exchange, not a complete paid transcript or provider invoice. |

Paths without the full prefix above are under `src/vs/platform/agentHost/`.
The JSON evidence includes exact source hashes, line numbers, snippets and
immutable GitHub links for all 27 citation groups (18 original + 5 controller +
4 connection references), checked against the pinned
source archive. See also the official [Agent Host architecture](https://code.visualstudio.com/docs/agents/concepts/agent-host)
and [AHP repository](https://github.com/microsoft/agent-host-protocol).
OpenAI's [IDE documentation](https://developers.openai.com/codex/ide/) alone
does not establish this Copilot-backed AHP contract.

The provider can fall back when a restored model is unavailable
(`codexAgent.ts:1890`). A future paid adapter must reject a mismatched actual
selection; a requested model string is not sufficient. Actual served model,
effort and context remain `not_reported` here. No authentication source is
chosen or supplied by this change.

## Evidence and offline tests

The Actions artifact contains `prepared.json`, `source-evidence.json`,
`probe.json` (including the source contract, runner image, version/hash,
redacted RPC/logs and cleanup boundary), and the offline JUnit result.
Preparation failures have a separate fixed-reason JSON record. It does not
upload archives, HOME, SDK/config directories or raw unredacted logs.
`probe_completed` means the model-free observation finished, not gate readiness;
`launch_allowed` and `gate_ready` remain false.

Offline tests replace all process/network effects. They cover workflow scope,
redaction, archive limits, namespace admission, byte bindings, WebSocket framing,
RPC allowlists, authentication/provider errors, and no implicit model retry:

Initial probe verification: **195 passed, 0 failed, 0 skipped** (114 new probe cases
plus 81 existing runner-admission cases). All 18 source-citation groups were
also checked against the downloaded pinned source, with no binary execution.

```bash
cd batch-runner
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -o addopts= -p no:cacheprovider tests/test_ghcp_ahp_probe.py
```

Do not run `prepare`, `probe`, `code agent host`, or a Codex host locally to
validate execution. The actual hosted result is collected after the single
branch publication; it is deliberately not invented in this pre-run commit.

## Client-side limit and capture follow-up (2026-10-30)

The previous hosted probe [41049869887](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/41049869887)
proved headless startup and Codex selection, then stopped at `-32007` (auth
required). It did **not** prove intrinsic caps or a complete paid transcript.
That first [controller](../batch-runner/ghcp_ahp_client.py) used only an injected
I/O port, exercised by synthetic events. The later connection-only section
below adds a separate dispatch entry; the push probe still has no authenticated
transport, authentication RPC or prompt path.

| Count/control | Admission and stop behavior | Worst-case boundary |
| --- | --- | --- |
| 64 AHP turns | Reserve each client turn before send, count unique observed turn IDs, serialize client work; at the limit close admission, cancel active turn(s), dispose session, terminate owned host. | **0** further client work notifications; **1** already-admitted client turn at most. AHP user turns are **not** internal model/premium requests. |
| 32 tool calls | Count unique `(turnId, toolCallId)` from all tool lifecycle events and snapshots. At 32 close admission and cancel; retain late events and measured overshoot. | **0** further client work notifications; server-internal tool/model overshoot has **no finite proven bound**. Tool events can arrive after execution starts. |
| 1,200 seconds | Monotonic check before every send/receive, separate deadline watchdog, **0.05s** receive polling target; **1s** control-send timeout per cancel/dispose and **4s** owned-host terminate timeout. | These are client timeout targets, **not** a proven wall-clock cancellation/billing ceiling; scheduling, transport and in-flight server work remain unbounded by this protocol evidence. |

The pinned protocol explicitly permits a tool to enter `running` at
`chat/toolCallReady` with `confirmed` already set:
[actions.ts:174](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/common/state/protocol/channels-chat/actions.ts#L174).
Client cancellation is the `dispatchAction` **notification** carrying
`chat/turnCancelled`, not an invented request/response cancel RPC
([actions.ts:443](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/common/state/protocol/channels-chat/actions.ts#L443),
[commands.ts:689](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/common/state/protocol/common/commands.ts#L689)).
`disposeSession` then cleans session resources; only the transport's owned-host
termination acknowledgement permits output-file collection. Failed cancellation
never reopens admission or triggers a retry. The counters are not a provider
request counter, nor a premium-request/cost meter. This still does **not** pass
the card's hard-cap execution condition.

### Capture contract and deliberate refusals

One exclusive `ghcp-ahp-client-v1` JSON contains all delivered, redacted wire
frames (including identical replay and late frames), snapshots/history, joined
text, tool lifecycle, tool inputs, terminal command/exit events, reported file
edits, changed/generated workspace bytes (UTF-8 or base64), hashes, stop reason
and cleanup status. File bytes are read only after host termination, without
following links; unchanged input files can be excluded by their baseline hash.
No raw transcript, HOME, token file or host cache is uploaded. Known credential
and credential-shaped strings are masked; split text/terminal deltas are checked
after joining. Binary credential exposure refuses export before base64 encoding.
This is not a scanner for arbitrary encrypted/obfuscated secrets.

`requested_model` is separate from `reported` and its provenance. Only retained
historical `message.model` values can populate reported model/config; client
requests/echoes, catalog entries and defaults cannot. This AHP selection record
is **not** a provider-served-model attestation: `served_model` and model version
remain `not_reported`. Absent effort/context also remain `not_reported`; no
requested value is substituted. An explicit historical mismatch stops work.

Scope is a fresh single chat. Reconnect, restored paginated history, extra
chats/background work, queued messages, resume/steering and implicit tool
approvals are not implemented. History needing `fetchTurns`, divergent replay,
per-channel reordering, stream loss, malformed events, output overflow or
unconfirmed host cleanup fails closed instead of claiming complete capture.
`serverSeq` gaps alone are not loss: sequences also cover unsubscribed channels.
`capture_boundary=all_delivered_frames_not_unseen_server_work` and
`gate_ready=false` remain explicit even when the synthetic session completes.

### Existing workflow option, not a second paid workflow

The existing `agentic-v2-ghcp-sol-gate.yml` gains dispatch input
`execution_adapter: copilot-cli | ahp-draft`; the legacy default is unchanged.
The initial draft refused even with a credential. The connection-only follow-up
below adds a single protected predecessor; an AHP task cannot skip it. The five
tasks still require the unresolved hard-cap/harness decision. No fallback to the
default Copilot CLI agent is permitted for an AHP request.

The **existing** branch-push model-free probe also runs the collector tests and
runner-admission tests. Its runtime RPC allowlist, isolated network, no-auth,
zero-prompt boundary and hosted-only rule are unchanged. Synthetic cap/capture
tests prove client wiring, not performance, provider enforcement or billing.

Final local follow-up regression: **947 passed / 0 failed / 0 skipped** across
`tests/test_ghcp*.py`, Python 3.10.12 / pytest 9.2.0, offline, **85.60s**.
That includes **84** new controller cases and **4** paid-draft refusal cases.
That version's existing push probe ran **279** cases (114 probe + 84 controller +
81 runner), then repeat only its credential-free hosted discovery. Its result
was collected after publication. These counts describe the preceding commit,
not the connection-only follow-up's tests.

## Connection-only prerequisite (2026-10-30)

The intervention is **one AHP user turn**, not a five-task benchmark and not a
promise of one provider/premium request. Its fixed prompt is
`Reply with exactly CONNECTED. Do not use any tools.` Requested settings remain
`@provider=vscode-proxy:gpt-5.6-sol`, `thinkingLevel=max`, `contextSize=1000000`.
The decision is whether response-side evidence supports those fixed conditions;
`CONNECTED` text alone cannot pass. No grader, benchmark input, scoring or seal
is touched. Fixtures validate this decision logic, not real provider behavior.

The existing gate workflow has one non-matrix `ahp-connection` job, only for
explicit `workflow_dispatch`, `execute_paid=true`, `dry_run=false`,
`execution_adapter=ahp-draft`. It and the existing task job are both protected
by `environment: ghcp-sol-gate`; **only their runtime steps** reference the
selected credential. All model-free jobs and the branch-push probe retain zero
credential references. An empty credential produces `auth_source_unavailable`
before host startup/authentication/model work. No alternate login is consulted.

The client admits **1** turn, **0** tool approvals, and a **120s** monotonic
deadline. It allows the admitted turn to complete (the ordinary 64-turn
controller's stop-on-limit behavior is unchanged), refuses a second turn before
send, and cancels/disposes/stops on the first observed tool, timeout, malformed
event, stream loss or contradictory evidence. The read-only sandbox,
`untrusted` approval policy, disabled web/network and empty client tools are
requested restrictions, **not a native zero-tool guarantee**. The first server
tool can already have started: observed overshoot can be **1 or more**, and
provider-internal model/tool overshoot still has **no finite proven bound**.
After closure the finite client bound is **0 new work notifications**, with at
most **1 previously admitted turn**. Do not equate any of these units with bills.

The transport authenticates only the Codex provider's advertised GitHub resource,
creates a fresh session/chat, never resumes, retries or sends tool approvals,
and uses the pinned host/SDK and an isolated HOME. The local WebSocket is bound
to loopback with a random 0600 transport-token file (not the Copilot token).
The Copilot credential is passed in memory by the authentication RPC, never in
argv, transcript or artifact. The job's private PID namespace and outer 130s
TERM/5s KILL guard bound cleanup operationally; they do not prove a 120s billing
ceiling. Host logs, authentication state and raw workspace are never uploaded.

`connection.json` separates `requested` and `observed` fields for served model,
thinking level, context size and usage, and records runner/run/commit identity.
Unreported values stay `not_reported`. It SHA256-binds `capture.json` (redacted
events, counts, stop/cleanup state) and `handshake.json` (redacted discovery and
auth exchange). An artifact/write/cleanup failure cannot yield `connected`.
Contradictory or missing Sol/Max/1M evidence exits 2 and prevents all five task
jobs. Missing usage remains explicit and is not invented or priced.

Important pinned-source finding: `codexAgent.ts:3929` passes `session.model?.id`
to `codexMapAppServerEvents.ts:514`, which copies it to `usage.model`. That is a
selection echo, **not** a served-model attestation. The mapper forwards
`usage._meta.modelContextWindow` from the SDK token-usage notification; it does
not report the actual thinking level. Therefore the current live parser leaves
served model and thinking level `not_reported` and **cannot admit the five tasks**.
Synthetic pass fixtures inject a test-only response-evidence reader; the live
parser explicitly ignores that metadata, and such receipts cannot be replayed
as live admission. The four added immutable-source citations in the probe
manifest bind these conclusions and the auth/local-transport protocol.

The owner's first command, **only after supplying authentication and choosing
to run this connection check**, is a draft (not executed during this work):

```bash
gh workflow run agentic-v2-ghcp-sol-gate.yml --repo hyeonsangjeon/gdpval-realworks --ref leader/ghcp-ahp-probe-20261030 -f dry_run=false -f execute_paid=true -f execution_adapter=ahp-draft -f connection_only=true
```

`connection_only=true` always skips the five tasks and Step8 contract job, even
if the connection predicate passes. A later five-task dispatch requires both
the predecessor's successful output and a same-run/attempt/commit receipt, plus
the still-closed native hard-cap/harness gate. Authentication alone opens none
of those conditions. No actual model call, credential lookup or dispatch is
part of this change's offline/push verification.

## Pre-session policy diagnostics and capability-only mode (2026-11-04)

Connection run **41873338947**, at source `1775857afbfd8`, stopped with
`connection_requested_policy_unavailable` before `createSession` or a prompt.
That reason is **our client-side fail-closed check**, not a server error code.
The client requires each of these keys in `resolveSessionConfig.result.schema.properties`
and an exactly matching resolved value in `result.values`:

| Policy key | Requested value |
| --- | --- |
| `codex.approvalPolicy` | `untrusted` |
| `codex.sandboxMode` | `read-only` |
| `codex.networkAccessEnabled` | `false` |
| `codex.webSearchMode` | `disabled` |
| `codex.modelReasoningEffort` | `max` |

The pinned VS Code source explains the incompatibility without another run:
[codexAgent.ts:534](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L534)
defines a **visible** schema containing only mode, permissions preset,
permissions and sensitive edit locations. Its
[resolver at line 9254](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L9254)
returns that schema even when preserving internal configuration values.
[AgentService at line 10204](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/agentService.ts#L10204)
routes this pre-session request to that resolver; host additions are worktree
metadata, not the five policy keys. Requiring the internal keys in the visible
schema therefore refuses even an exact value echo. The original run did not
retain its response, so this is a pinned-source explanation, not a recovered
observation of that response.

This is **not** proof that Sol or 1M is unavailable. Neither is inspected by
this particular policy check. Sol-specific `thinkingLevel`/`contextSize`
advertisements live in the model's `configSchema`, separately from session
policy properties. Advertisements and resolved defaults never count as
served-model, actual-thinking-level, context-usage or billing evidence.

The follow-up preserves all five policy requirements and their refusal code.
It also rejects numeric `0` masquerading as the requested boolean `false`.
There is no preset substitution, schema-key exemption, settings echo promotion
or relaxation of the existing five-task admission/served-attestation guard.

### Evidence retained even when context-manager entry fails

`handshake.json` now survives initialization/policy refusals before the opener
yields. It includes redacted initialize/RPC frames, root model-catalog updates,
agent capabilities, model reasoning/context schemas, resolved policy schema
and values, per-field refusals, and client session/turn request counters.
`connection.json` SHA256-binds that file and includes `advertised` separately
from `observed`, plus each `refused_fields` entry's field, requested value,
advertised schema/resolved value, and reason. CLI JSON logs print those same
refusal entries without raw host logs. An export failure is itself a refusal.

Credential values (including JSON/URL/base64 forms), credential-shaped text,
structured account/user/tenant identifiers, email addresses and working paths
are masked before export. Identifiers learned from a later auth reply also
redact earlier echoes. This is not a claim to decrypt arbitrary obfuscation.
Raw auth state, token files and host logs are not uploaded. Unknown fields
remain `not_reported`; an absent visible property is not a false/default value.

### Zero-session diagnostic branch in the existing workflow

The existing workflow adds `capability_only` (default **false**). With
`ahp-draft`, `connection_only=true` and the existing protected dispatch opt-in,
the CLI receives `--capability-only`. Only three RPCs are allowed, in order:
`initialize`, `authenticate`, `resolveSessionConfig`. Their parameter sets are
restricted; session creation, subscriptions, model/tool actions and further
RPCs are rejected at the wire boundary. No reader or inference session starts.
Its limits are **0 sessions, 0 turns, 0 tool calls, 3 RPCs, 120 seconds**.
The existing `execute_paid=true` input is still required to enter the protected
workflow job; in capability-only mode it does not enable model work.

A successful capability query is `capabilities_collected`, never `connected`;
`connection_verified`, `five_task_allowed` and the workflow `verified` output
remain false. Policy mismatch still exits 2 and preserves diagnostics. Both
the paid task job and Step8 job explicitly exclude capability-only dispatches,
including invalid adapter/connection-only combinations. Missing authentication
still refuses before opening the host. The separate branch-push model-free
probe and its no-auth/network-isolation/empty-session contract are unchanged.

All new transport/admission/export paths are exercised with fake host and
socket boundaries. They do not execute an Agent Host on NAS. The visible-schema
incompatibility is established from the pinned source, so **no capability or
connection dispatch is performed for this diagnostic change**.
