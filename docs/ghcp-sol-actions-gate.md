# GHCP Sol fixed-five Actions gate (local draft)

Owner decision 2026-10-24 00:01: use one GitHub Actions standard
`ubuntu-24.04` runner job per task. No nested VM or `/dev/kvm` prerequisite.
This draft does not grant push, dispatch, paid inference or grading approval.

## Installed CLI contract audit, 2026-10-25 12:15 KST

**The exact GHCP-to-Codex launch command remains unconfirmed.** Local help
confirms noninteractive and JSONL options, but not that this route applies
Sol, Max and a numeric 1M context together. No authenticated session, prompt,
model call, server startup or live event capture was run. The adapter and
collector are unchanged; only schema-shaped synthetic fixtures were added.

The retained help files below are in
`/ai-work/copilot/_tmp/ghcp-sol-cli-contract.9Qj6sx/`.

| Inspected host executable | Observed version | Boundary |
| --- | --- | --- |
| `/home/dev/.local/share/nas-copilot-desk/copilot-cli/node_modules/@github/copilot-linux-x64/copilot` | `--no-auto-update --version`: **1.0.103** | Sibling `package.json:3` says **1.0.98**. Package metadata is not the executable version. |
| `/usr/lib/node_modules/@github/copilot/node_modules/@github/copilot-linux-x64/copilot` | `--no-auto-update --version`: **1.0.79** | Sibling metadata agrees; this package contains the inspected runtime/SDK schema. An earlier unpinned invocation reported 1.0.103. |
| `/home/dev/.local/bin/codex` -> `/home/dev/.codex/packages/standalone/releases/0.144.5-x86_64-unknown-linux-musl/bin/codex` | **0.144.5** | This is the host executable, not VM version evidence. |

The earlier host observation of Copilot **1.0.83** was not reproduced; none
of these observations establishes the intended VM version. The default
`/usr/local/bin/copilot` wrapper was read, **not executed**: lines 20-29 run
entropy helpers and line 33 can call `gh auth token`. That wrapper is not an
approved authentication or launch binding for this adapter.

### Command syntax: confirmed options, unconfirmed route

`copilot-pinned-help.txt:38-40,53-63,103-107` documents `-p` (noninteractive,
exit on completion), `--model`, `--reasoning-effort max`,
`--context long_context`, `--stream on` and `--output-format json` (JSONL,
one object per line). `copilot-config-help-fixed.txt:148` lists `gpt-5.6-sol`.
The following is **partial syntax only; it was not executed**:

```text
<pinned-copilot> --no-auto-update --disable-client-telemetry -p <prompt> --model gpt-5.6-sol --reasoning-effort max --context long_context --output-format json --stream on
```

`--agent` explicitly selects a **custom agent**, not a verified Codex harness.
`long_context` is an eligible-model tier (`copilot-config-help-fixed.txt:165`),
not a numeric or applied 1M attestation. Sol/Max options are requested settings,
not served evidence. The config help also documents `continueOnAutoMode`
at lines 110-112; this investigation neither enabled it nor changed guards.

Codex `exec --help` confirms noninteractive execution, `--model`, TOML `-c`
and `--json` (stdout JSONL, `codex-exec-help.txt:92-93`). It does not establish
a GHCP authentication bridge or this four-part launch contract. The inspected
0.144.5 release did not supply an event schema among its bundled resources.
Only `app-server --help` and `app-server generate-json-schema --help` ran;
no server or schema generator was started. A newer repository SDK is not
substituted as evidence for this installed CLI.

### Event shape versus delivery

The packaged 1.0.79 runtime schema is
`/usr/lib/node_modules/@github/copilot/node_modules/@github/copilot-linux-x64/schemas/session-events.schema.json`,
SHA-256 `350df35914d4e2fdbadb8932ca66f1e58d759aad79b5be9291857c9052d31301`.
Its SDK and schema describe these fields; they do **not** prove that the
1.0.103 prompt-mode stdout stream emits every such event promptly.

| Field or marker | Installed evidence | What it does not prove |
| --- | --- | --- |
| `assistant.turn_start`, `data.turnId`, optional top-level `agentId` | Schema lines 1186-1260; absent `agentId` denotes the root agent. | Complete turn delivery from the eventual GHCP-to-Codex route. |
| `tool.execution_start`, `data.toolCallId`, `data.toolName` | Lines 15275-15386; IDs support per-agent counting. | Admission before a tool takes effect, or reliable delivery of all starts. |
| `assistant.usage.data.model`, optional `reasoningEffort` | Lines 1340-1543; the event requires `ephemeral: true`. | Applied settings or a complete native-request count. A valid event can omit effort. |
| `session.usage_info.data.tokenLimit` | Lines 15935-16036; also requires `currentTokens`, `messagesLength` and `ephemeral: true`. | A call-specific 1M context attestation. It remains a preceding session snapshot. |
| `session.idle`, `session.shutdown` | Lines 6760-6788 and 12527-12553: idle means no in-flight agents/attached shell commands; shutdown carries termination metrics. | A stdout flush barrier, a complete stream, or proof that all sub-agent events arrived. |

The same package's `copilot-sdk/session.d.ts:131-145` says `sendAndWait`
waits for `session.idle`; its timeout does **not** abort in-flight work.
`copilot-sdk/types.d.ts:1938-1953` describes streaming/sub-agent forwarding.
Neither establishes CLI stdout buffering, flush timing or loss-free delivery.
Ephemeral usage/idle events are not persisted in the session log. Reading a
saved session file alone therefore cannot supply all required evidence.
EOF, idle and shutdown do not upgrade `stream_completeness_verified`.

### Narrow fixture change and separate proofs

The existing parser already uses the documented field paths, so no parser,
helper, workflow, plan, cap, dependency, registration or permission changed.
Added an eight-event **synthetic** JSONL fixture with schema-required envelopes,
linked parent IDs, tool name, context fields and ephemeral markers. All eight
events pass the installed Draft-07 schema with format checking and internal
references only. Four fake-process variants check full metadata, absent
ephemeral events, optional effort missing, and absent terminal markers.
They retain private-canary exclusion, settings-only labels and false authority
and completeness flags. Fixture timestamps/zeros are not runtime measurements.

One combined invocation returned **295 passed, 4 failed, 0 skipped in 15.60s**
(wrapper **15.77s**, exit **1**). The four new cases failed because their fake
program read the JSON argument at index 4 rather than 3. After that one-line
fixture correction, **only those four** were rerun: **4 passed, 0 failed,
0 skipped in 0.30s** (wrapper **0.47s**, exit **0**). Assertions and production
code were unchanged. This is **not** a 299-pass final invocation. The earlier
**295/15.79s** proof below remains historical and separate. Both test commands
used **120s TERM + 5s KILL**; the first collection launcher also failed before
pytest because `/usr/bin/time` was absent. Its log is retained.

Direct help/version calls used a cleared inherited environment and an empty
evidence working directory. After discovering the relevant flags, calls used
`--no-auto-update` and `--disable-client-telemetry`. Initial calls lacked the
update-disable flag; **no audited zero-background-network claim is made**.
Attempted OS isolation was unavailable (user namespaces, Landlock, seccomp);
the guarded help launcher stopped before CLI execution. No OS setting was
changed. Three topic-help calls rejected unsupported `--config-dir`; removing
only that argument allowed help to complete. It was not a config/cache sandbox.
No update, login, token, model, network-fetch or dispatch command was issued.

The next free prerequisite is to identify the intended VM executable and its
exact **GHCP-to-Codex bridge plus stdout serializer contract**, from installed
source/help only. Tool-cap approval, authentication isolation, complete live
delivery and applied-settings proof remain separate gates; no launch or retry
right was granted. [The current record](../tasks/LATEST_TASK_RESULT/README.md)
binds file hashes, commands, failed and passing logs/JUnit, and local source.

## Disabled process adapter, 2026-10-25 10:35 KST

The leader authorized a local process-adapter skeleton after the earlier
execution-path audit. `batch-runner/ghcp_sol_execution_adapter.py::run_task`
now supervises an explicitly supplied argv. `execution_enabled` defaults to
false and rejects before configuration reads, task-state creation or process
launch. The caller must also supply a positive integer in
`execution_config["tool_calls_per_task"]`; missing, null and invalid values
refuse before launch. There is no default tool-call value or selected candidate.
The existing workflow and inert VM plan remain unchanged and cannot invoke it.

| Limit | Previously available | New adapter behavior |
| --- | --- | --- |
| 1200 seconds/task | Supplied-event collection only | Start a monotonic deadline before `Popen`; check after launch, while reading and after EOF. Stop a silent, partial-line or closed-stdout process with `task_timeout_exceeded`. |
| 64 turns/task | Supplied-event collection only | Count agent-scoped `assistant.turn_start`/`turnId` identities. Accept 64; stop when the 65th start is observed with `turn_cap_exceeded`. |
| Tool-call cap | Undefined | Require the caller's value, count `tool.execution_start`/`toolCallId` once per agent, and stop on the first observed count above it with `tool_call_cap_exceeded`. Malformed or repeated start identities refuse. |

The adapter creates one fresh private task directory and owns a new POSIX
process group. Every started-process exit path signals that group with TERM
and then KILL, including when the leader exits first. Cleanup allows one second
for TERM and four seconds for the final wait; `waitid(..., WNOWAIT)` keeps the
leader PID reserved until group signalling finishes. The receipt distinguishes
group signals, leader reaping and stdout closure. It does not claim that escaped
sessions were contained or every orphan was reaped. Partial files stay in
`private/files`; they are neither read into the receipt nor uploaded.

The JSONL reader retains the existing byte, line and event limits and reuses
the existing collector for allowlisted settings metadata. The outer receipt's
`limits` and `cleanup` describe the owned process; the nested collector receipt
keeps its separate collection-only labels. Commands, paths, raw events, stderr,
headers and credentials are not serialized. The child receives a minimal
environment without inherited credential channels, not an approved GHCP
authentication mechanism or proof that a CLI cannot discover a user cache.
Auto/BYOK checks are reused. Missing usage and cost remain null with
`not available`; settings stay settings only, and all paid/retry/live-proof
authority flags remain false.

One combined offline invocation passed **295 tests, 0 failed, 0 skipped in
15.79s**, with **15.96s** wrapper wall time: the unchanged **231** gate tests
and **64** new adapter tests. Only generated Python fake executables ran.
They cover boundaries, accelerated deadlines, malformed streams, private
canaries, refusal before spawn, partial-file retention, and child/grandchild
group termination, including ignored TERM and a leader that exits first.
The earlier 231-test results below remain separate historical proofs.
[The current result](../tasks/LATEST_TASK_RESULT/README.md) records the exact
source additions, invocation and log/JUnit identities.

**The actual GHCP-to-Codex route remains unbound.** No exact command, pinned
CLI version or real output stream was selected or tested. The documented
event envelope is a fixture contract, not proof of complete, prompt delivery
for this route or its sub-agents. Start events report effects already begun;
cancellation cannot prove that an excess turn/tool action never took effect.
An approved command/event binding, tool-call value, authentication isolation,
input and grader checks, applied-settings evidence and fixed-source review/CI
remain required before any separate execution decision. This change does not
enable the workflow, exercise a model, reopen a spent right or change a plan.

## Execution-path audit, 2026-10-25 02:40 KST

This historical audit predates the disabled adapter above.

**There is no GHCP/Codex task launcher in this gate to attach execution
limits to.** The current task therefore produces a source-backed blocker and
tool-cap options, not a new runtime guard. No executable, test, workflow,
plan, cap, dependency or authentication setting changed. The audit used local
source and previously cached public documentation only; no CLI was executed.

| Item | Actual execution path: before and after | What remains possible but unimplemented |
| --- | --- | --- |
| 1200 seconds/task | Not attachable in this branch: the live task launcher is absent. The collector enforces this value only while consuming supplied events. | An owned subprocess could have a deadline started before launch, process-tree termination and a retained partial receipt. There is no approved GHCP-to-Codex command/process owner here to wire or test. |
| 64 turns/task | Not attachable in this branch: there is no live event subscription or pre-turn admission hook. The collector stops at the 65th supplied turn-start event. | A live stream could trigger cancellation, but a start notification does not prove that the 65th turn was prevented before any effect. |
| Tool calls/task | Value still undefined; no tool-call cap is installed. | Counting events is documented; selecting a value and proving pre-effect enforcement remain separate requirements. |

The concrete route is
`.github/workflows/agentic-v2-ghcp-sol-gate.yml:27-35,58-66,74-83` ->
`batch-runner/ghcp_sol_actions_gate.py:485-527` -> `dry_capture:450-480`.
Both jobs refuse paid mode before checkout. The task step launches only the
model-free Python capture under **60 seconds plus 5 seconds for forced
termination**, with a **5-minute job limit**. It does not launch Copilot or
Codex. `collect_session_events:242-379` retains only supplied metadata; its
`subprocess_cleanup` is explicitly `not_applicable_no_subprocess_started`.
The separate inert VM plan still has `launch_enabled: false`, null CLI/SDK
versions and null execution-limit fields. Its validator preserves those facts.

The host's `/usr/local/bin/copilot:32-42` is not used by this workflow. Its
fallback credential resolution and binary selection must not be inherited as
an approved pilot adapter. Read-only package metadata reports **1.0.98** for
the wrapper's default runtime location and **1.0.79** for `/usr/bin/copilot`'s
package. Neither version is bound by the GHCP plan. Copilot's package README
identifies its own coding-agent harness; cached CLI reference [G3], line 658,
says `--agent` selects a custom agent, not the OpenAI Codex harness. Inventing
that binding would change the unresolved execution contract. No such
substitution, new launcher or fake-executable surrogate was added.

### Tool-event evidence and unselected values

The cached official streaming reference [G1], lines 297-305 and 417-428,
documents `assistant.turn_start` with `turnId` and `tool.execution_start`
with `toolCallId`; the latter means a tool **has begun executing**. Count
starts by bound session/agent/tool identity, not completion/progress events
again. The local **1.0.79** `session-events.schema.json:1244,15370` also
declares those event types. This is source/schema evidence, not an observed
session or a guarantee about the **1.0.98** runtime. The cached CLI reference
at line 711 describes JSONL output, but it does not establish that this
gate receives every event, including sub-agents. At line 697,
`--max-autopilot-continues` counts continuation messages, not these turns or
tool calls; it is not a substitute cap.

The separately installed OpenAI Codex SDK **0.147.0** declares `item/started`
and command/MCP/dynamic-tool items in `generated/v2_all.py:9183,9491,8239,4635,4663`.
Those could support a separately bound Codex counter; they are not GHCP
events. This branch's Foundry `batch-runner/core/codex_runner.py:1995-2050` has its own
turn watchdog but no numeric tool-call cap in the inspected runner. Native
HTTP requests, logical turns and tool executions are different units.

| Candidate only | Existing source and rationale | Limitation |
| --- | --- | --- |
| 8 tool calls/task | `batch-runner/core/agentic_sandbox_runner.py:43` and `batch-runner/core/agentic_tools.py:199-233` use an 8-call dispatch ceiling; the latter rejects an oversized batch before dispatch. This supplies a conservative existing reference. | It may stop file-heavy tasks early; no GHCP workload sufficiency was measured. |
| 32 tool calls/task | `batch-runner/core/agentic_v2_tools.py:56,141-145` and `batch-runner/core/agentic_v2_runner.py:753` use a 32-call dispatcher default with refusal before the next dispatch. This permits more tool work than the 8-call reference. | It is another harness's ceiling, not a GHCP entitlement or a measured requirement. It is unrelated to the native pilot's 32 HTTP requests. |

**Neither candidate is selected.** No new cap or reason code is introduced.
Existing `task_timeout_exceeded` and `turn_cap_exceeded` remain offline
collector reasons. Process-tree termination, retained live partial outputs
and fake-executable boundary/child-cleanup fixtures were **not implemented or
validated**, because no matching task execution adapter is present. This is
not a finding that GHCP cannot support a watchdog or emit countable events.
The next prerequisite is an explicitly bound GHCP-to-Codex launch/event
adapter with a process owner; it cannot be replaced by the host wrapper or
the separate Foundry runner without a new execution-contract decision.

On clean source `8d356e1c1dc13ae10193a045334c7e2ab089de35`, one combined
offline invocation reported **231 passed, 0 failed, 0 skipped in 11.36s**;
wrapper **11.575s**, exit **0**. This repeats the requested existing gate
bundle only: **138 Actions checks plus 93 VM checks**, including **4 Auto**
and **2 BYOK** refusals. No new test was added. The older **231/10.66s** proof
below remains separate. Exact source, invocation, log/JUnit hashes and
remaining gates are in the [current result](../tasks/LATEST_TASK_RESULT/README.md).

## Offline capture limits, 2026-10-25 00:15 KST

The collector now stops reading supplied events at the existing Actions draft's
1200-second deadline or its 65th documented `assistant.turn_start` event. This
is **offline collection enforcement, not live GHCP task enforcement**. The route
still has no GHCP-to-Codex adapter, model launcher or owned child process.
`paid_execution_allowed` and `live_enforcement_verified` remain false.

| Item | Before this change | After this change |
| --- | --- | --- |
| Wall-clock time | 1200 seconds/task was recorded only. The workflow already bounded a dry-run process to 60 seconds plus 5 seconds for forced termination, and a job to 5 minutes. | A local monotonic deadline and Linux real-time signal stop event collection with `task_timeout_exceeded`. The shorter workflow bounds are unchanged. No live task timeout is verified. |
| Tool calls | No value in this Actions draft or the inert GHCP VM execution block. | Still undefined: null plus `value_not_defined`. No tool-call cap or `tool_call_cap_exceeded` claim is invented. |
| Turns | 64 turns/task was recorded only. | The collector accepts at most 64 supplied turn-start events, including sub-agents, and stops on the 65th with `turn_cap_exceeded`. This does not prevent a historical turn or prove pre-call enforcement in a live adapter. |

The deadline begins when event collection starts, not when a historical task
started; setup and receipt writing are covered only by the existing workflow
process bound. Event timestamps cannot reset it. A timer interrupts a blocked
local iterator; unsupported platforms, non-main-thread callers or an existing
timer refuse with `task_timeout_guard_unavailable` before reading events.
Missing, malformed or duplicate turn identities refuse with
`turn_count_unverified`. Turn-start counts are not native-request or usage-event
counts, and a supplied stream without turn markers does not prove zero live
turns. No limit or approval is borrowed from the separate Foundry/native pilot.

The collector closes its explicit input generator and restores the signal
handler/timer on exit. Cleanup failure yields `session_event_cleanup_refused`.
The receipt identifies subprocess cleanup as not applicable because this route
starts no subprocess; termination of actual GHCP children remains unimplemented
and unverified. Adding a hypothetical launcher here would not close that gap.

Missing usage and cost keep their nullable numeric fields. New `usage_status`
and `cost_status` fields say `not available`, with fixed not-collected reasons.
No zero, tariff calculation or other estimate is substituted. Grade stays null.
Per-call model/effort/context observations remain settings only.

One combined offline invocation on clean local source
`6ab43d4c7198e9e720fabeac5cb0d796b68cc5c7` reported **231 passed, 0 failed in
10.66s**, wrapper **10.841s**, exit **0**: **25 new** capture-limit checks plus
**206 existing** Actions/VM gate checks. Fixtures test the 64/65-turn boundary,
cumulative deadline and EOF, an accelerated real OS alarm at a blocked read,
file closure, missing usage, unsafe timer ownership and canary non-egress.
No model or child-runtime process was used. Exact sources, commands and proof
hashes are in the [current task result](../tasks/LATEST_TASK_RESULT/README.md).

## Offline per-call capture, 2026-10-24 21:30

The model-free capture path now projects supplied GHCP JSON session events
into `capture.json` under `session_event_receipt`. It records each
`assistant.usage` event's allowlisted `model` and `reasoningEffort`, plus the
latest preceding `session.usage_info.tokenLimit` for the same agent. The
receipt identifies the context event's position and labels the association
`preceding_same_agent_session_snapshot_not_call_attestation`. A main-agent
snapshot cannot fill a sub-agent's missing context; a later snapshot cannot
repair an earlier call. A sub-agent origin without `agentId` also refuses;
the documented `initiator` or legacy `parentToolCallId` cannot implicitly
select the main-agent snapshot. Missing fields, non-Sol models, non-Max effort,
non-1000000 context limits, duplicate usage events and differences between
calls fail the attempt with fixed reasons and exit 2. No value is filled from
the requested settings. Arbitrary non-Sol model strings are suppressed as
null plus `served_model_mismatch`, not copied into the public receipt.

This is a document-based JSON projection tested with synthetic events, **not
an actual GHCP output capture or a GHCP-to-Codex execution adapter**. The
cached official event reference [G1] documents per-call model/optional effort
and session-level `tokenLimit`; [G2] says usage is ephemeral and includes
sub-agent calls. Codex's separate `modelContextWindow` signal [L1 below] has
no established GHCP binding here. Its receipt field remains null with
`not_in_documented_ghcp_event_contract`; the collector does not invent a
GHCP field or combine unbound streams from different harnesses.

Every receipt retains `evidence_level: settings_only`,
`applied_settings_verified: false`, `live_source_verified: false` and
`stream_completeness_verified: false`. Consistent metadata is not proof of
the actual served model, applied Max or a granted 1M window. Supplied usage
event counts are not a native-request counter. The dry-run runner itself
makes zero model/grader calls; usage, cost and grade stay null. Usage and cost
now also carry the explicit availability statuses described above. Paid execution
and retry authority remain false even for `consistent_settings_only`.

The default matrix/capture commands still perform an empty, model-free
rehearsal. For an explicitly supplied **offline synthetic** JSONL stream, add
`--session-events /absolute/synthetic-events.jsonl` to the existing capture
command. The reader does not discover session logs or credentials. It accepts
one regular, non-symlink file bounded to 1 MiB, 64 KiB per line and 4096
events; these are parser limits, not a paid-call allowance. Parse/read failures
retain only a failed metadata receipt. Raw conversations, errors, headers,
event IDs and credentials never enter that receipt or CLI output.

Before catalogue/event reads or capture writes, exact Sol selection is
required. `--model auto`, `--byok` and any `--provider-config` refuse.
Inherited `COPILOT_PROVIDER_*` or `COPILOT_PROVIDERS_CONFIG` names also refuse,
without inspecting their values. Inherited `COPILOT_MODEL` and `COPILOT_HOME`
refuse as unverified rather than being resolved. The default
`.copilot/providers.json` is checked only for existence: even an empty or
symlinked registry refuses, and its contents are never read. Tests substitute
a synthetic home; no real user configuration was examined. These are local
preflight checks, not a universal server-side no-fallback guarantee. A future
reviewed adapter still needs controlled configuration/authentication and a
subscription installed before any call, including sub-agent calls.

The initial fixture cases and existing Actions/VM gate tests report **204
passed, 0 failed in 9.89s** (pytest), **10.084s** wrapper wall time, exit **0**.
Source review then found the missing-agent-ID sub-agent edge above. A separate
follow-up on the corrected source reports **7 passed, 0 failed in 0.23s**,
wrapper **0.390s**, exit **0**: two new origin cases and five directly coupled
context cases. These are separate proofs, not a pooled full-suite pass on the
final source. No full suite or live session was run. The original source,
command and evidence hashes remain in local Git record
`fe863326f996fe8708cd4098b7ec6ad7dd61905b:tasks/LATEST_TASK_RESULT/README.md`;
they are not added to the new 231-case result.

## Evidence and authentication audit, 2026-10-24

This section preserves the earlier **18:45** audit at the source below.
The new offline collector does not close its live-runtime or authentication gaps.

**Paid execution remains blocked.** At inspected source
`f205207bb73f123ed7ff858e0feefd35d23e53ab` (tree
`942355a97c7c61fbe65aec6f0c5b070e0aeebb90`), the gate has no GHCP/Codex
inference adapter. All three requested properties are **settings only** in
this route, not observations that they took effect. This is a documentation
audit, not evidence that Sol is unavailable or that no supported route exists.
No CLI/session, authentication, model request or test was run for this audit.

### What can be established

The verdicts below apply to this exact GHCP + Codex gate. A documented signal
in another harness does not establish that the gate can collect it.

| Property | Current verdict | Source and remaining evidence boundary |
| --- | --- | --- |
| Actual response model | Settings only (`설정 표시만`) | `batch-runner/ghcp_sol_actions_gate.py:25-31,56-75` copies requested Sol and sets every served value to `not available`. Copilot SDK documents per-call `assistant.usage.model` [G1, G2], a useful observation candidate. A pinned GHCP-to-Codex adapter and evidence that its value comes from the responding service, not the requested model, are still missing. |
| Reasoning Max | Settings only (`설정 표시만`) | `gpt56_sol_ghcp_codex_vm_gate.yaml:16-31` labels `max` as a request. Copilot SDK documents optional per-call `assistant.usage.reasoningEffort` [G1]. Missing effort must remain unknown; reasoning-token counts do not prove a tier. The CLI reference accepts an effort flag but describes `max` in an Anthropic context [G3]; this is not a provider-specific guarantee for GHCP Sol. Do not silently map `xhigh` to Max. |
| Context 1M | Settings only (`설정 표시만`) | The same plan declares a nominal `1000000`, not a verified server allowance. Copilot `session.usage_info.tokenLimit` and Codex `modelContextWindow` expose runtime context-window metadata [G1, G2, L1]. That metadata alone does not prove the GHCP service accepted the requested window or that this workload exercised it. OpenAI's Sol page advertises **1,050,000** context tokens [O1], which is neither the plan's nominal **1,000,000** nor a GHCP entitlement receipt. |

OpenAI documents Sol support for `reasoning.effort=max` [O1], and Codex
documents `model_reasoning_effort`, `model_context_window` and the separate
auto-compaction threshold [O2]. These establish configuration/capability
semantics, not this account's effective GHCP settings. Changing the window
or inspecting token usage would not establish that all history was retained
without compaction.

The installed, repository-pinned `openai-codex` / `openai-codex-cli-bin`
**0.147.0** pair is a different surface from Copilot SDK:

- `openai_codex/client.py:238-272` starts a Codex app-server subprocess and
  exchanges JSON-RPC; it is not a Python HTTP model client.
- `openai_codex/generated/v2_all.py:10241-10271` returns thread configuration
  including `model`, `modelProvider` and `reasoningEffort`. A thread-start
  response is not a provider completion. Its `Turn`/`TurnStartResponse`
  schema at `9643-9695` does not supply the provider response body's model.
- The same file at `3204-3219` names efforts through `xhigh` but accepts
  unknown nonempty enum strings. Parsing `max` therefore does not prove CLI
  or provider support. At `5294-5303` and `8579-8594`, token counts and optional
  `modelContextWindow` remain distinct from an applied-Max/1M receipt.

These installed-file references are **L1**, not executed runtime evidence.
The inspected venv has no `github-copilot-sdk` package. Locally installed
`@github/copilot/package.json:4` reports **1.0.98**, but its `README.md:5`
identifies the Copilot coding-agent harness. `--agent` selects a custom agent
in the current CLI reference [G3]; naming it `codex` would not prove use of
OpenAI's Codex harness. Current web documentation is not a version guarantee
for that installed binary. The separate Foundry native observer is not a
GHCP adapter and is not imported or credited as this gate's proof.

### Fallback prevention and detection

The unchanged plan's `automatic_fallback_allowed: false` and `fallbacks: []`
are declarations, not implemented provider controls. The current Python
entrypoint still refuses paid mode before capture
(`ghcp_sol_actions_gate.py:133-141`).

For a future reviewed adapter, select the exact registered model, never
`auto`; Auto explicitly routes between models [G3, G8]. Keep the GHCP provider
and authenticated identity fixed. Reject alternate providers/BYOK: GitHub
documents that BYOK variables can route model requests elsewhere despite
GitHub authentication [G4]. Do not accept Fast, another model, or an
unreviewed alias as Sol. These are proposed checks, not new runtime code.

Install metadata capture before execution begins, record each call's
model/effort including sub-agent calls, then compare the full observed sequence
with the registration.
`assistant.usage` is ephemeral: ordinary saved session logs/resume do not
recover it [G1, G2]. No actual session log or private transcript was read here.
Retain only allowlisted metadata with call/source bindings; do not publish
raw events, prompts, headers, tool output or credentials. Missing, conflicting
or unbound metadata must stop acceptance and further requests, not authorize
a retry. Detection after a call cannot undo that call's spend.

Codex 0.147.0 also defines `model/rerouted` metadata with source/target model
and thread/turn IDs (`v2_all.py:2436-2451`). Its documented schema reason is
`highRiskCyberActivity`; it is not a universal report of every possible
provider substitution. No inspected contract establishes a universal
server-side no-fallback switch. A missing reroute event or unchanged requested
model is not proof that silent provider fallback cannot occur.

### Authentication drafts, not authorization

**Conditional recommendation: job-scoped `GITHUB_TOKEN`**, only after the
existing repository's organization eligibility, billing identity, policy and
selected runtime support are explicitly established. None was queried here.
If those conditions do not hold, stop for an owner choice; do not move the
repository, change the billing identity, or automatically select another option.

| Draft | Scope and supply | Lifetime and disposal | Exposure and unresolved condition |
| --- | --- | --- | --- |
| **A. Job `GITHUB_TOKEN` (conditionally recommended)** | GitHub documents organization-owned Actions use with `copilot-requests: write` and the organization Copilot CLI billing policy [G5, G6]. The current workflow has only `contents: read`; no permission is changed here. Supply only to the approved runtime, not to model tools. | GitHub issues a token per job; it expires when the job finishes, subject to the hosted-runner maximum lifetime [G7]. Close runtime/credential channels and discard ephemeral runner state. Job-token expiry is not an execution timeout. | No new long-lived secret, but an exposed token can spend against the organization during its validity. Current organization/policy/billing and pinned-runtime eligibility are unverified. The docs' recommendation to use another workflow framework is not adopted. |
| B. Owner fine-grained PAT in a protected Actions environment | Personal-account-owned token with the **Copilot Requests** account permission; no unrelated repository write permissions. A separate checkout credential stays separate. Use an explicitly selected credential channel, such as runtime-only `COPILOT_GITHUB_TOKEN` [G4]. | Set the shortest owner-approved supported expiration. Remove process exposure at exit; revoke the PAT on GitHub after the approved execution window, including cancellation/failure. Removing an Actions secret or a local file does not revoke a copied PAT. | The permission is account-level, not a five-task or model-specific spending cap. Same-user tools, process environments, diagnostics or artifacts can expose it. Protected-environment approval and credential isolation are required; no PAT was read, created or stored. |
| C. Existing approved GitHub App installation token | Organization **Copilot Requests: Read-only** (`organization_copilot_requests: read`), with organization installation/billing approval [G6]. An approved service would supply only the short-lived token, never its signing key, to the runtime. | Installation tokens expire after **one hour** [G6]; revoke the installation token at the end and discard local exposure. App authorization/signing-key revocation is a separate owner action if compromised. No refresh loop is proposed. | Requires an existing approved App/token supplier and matching billing identity, neither established here. GitHub recommends A for Actions. An App signing key would create a larger persistent secret risk; this audit does not authorize creating a broker or App. |

For SDKs that support it, explicit token injection plus
`useLoggedInUser: false` disables credential discovery [G6]; setting that
flag while relying only on environment-token discovery would be incorrect.
Do not reuse a developer login/cache or allow an automatic account fallback.
The inspected local `/usr/local/bin/copilot:32-42` wrapper invokes
`gh auth token` when token variables are absent and can select another binary;
it was **read as code, never executed**. GitHub also documents keychain and
`gh` fallback, and that `/logout` removes local credentials without revoking
them on GitHub [G4].

All options require a fixed reviewed source, no untrusted/fork code in the
credential step, a boundary that keeps tokens out of the model's tools, and
metadata-only output. Step-local environment variables and log masking alone
do not isolate a token from same-user processes. Cleanup needs an expiry or
owner-controlled revocation backstop; a workflow `always()` step alone cannot
guarantee cleanup after runner loss. No option proves model/effort/context or
enforces timeout/tool/turn limits. Those remain independent stop-before-spend
conditions; authentication is not permission to run this pilot.

### Audit sources

Public documentation was fetched on **2026-10-24**, without account access.
The mutable documentation is evidence of its stated interface, not proof
of this project's entitlement or installed-version behavior. Local source and
documentation hashes are retained with this audit's completion record.

- [O1: OpenAI GPT-5.6 Sol model reference](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
- [O2: Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference), the official redirect target of `developers.openai.com/codex/config-reference`.
- [G1: Copilot SDK streaming events](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/streaming-events#assistantusage), including `assistant.usage` and `session.usage_info`.
- [G2: Copilot SDK usage and billing](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing#per-call-token-counts).
- [G3: Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference), model/effort flags and custom-agent selection.
- [G4: Copilot CLI authentication](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli), supported credentials, selection order and revocation distinction.
- [G5: Copilot CLI in Actions with GITHUB_TOKEN](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-in-actions).
- [G6: Copilot SDK server-to-server authentication](https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/server-to-server-tokens).
- [G7: GITHUB_TOKEN lifecycle](https://docs.github.com/en/actions/concepts/security/github_token).
- [G8: Copilot auto model selection](https://docs.github.com/en/copilot/concepts/models/auto-model-selection).

## Existing path surveyed

| Workflow | Inputs and task layout | Credentials and retained evidence |
| --- | --- | --- |
| `agentic-v2-stage-run.yml` | `stage`, `mode`, `isolation`, `plan`, `run_id`, `resume_from_github_run`, `comparison_reviewed_source_sha`; free planning, paid shard matrix, collection and comparison admission. Planner packs up to 13 tasks/shard, so advance-check five normally share one shard/job. | HF_TOKEN for pinned input fetch, Azure OIDC client/tenant/subscription IDs and Foundry endpoint; GITHUB_TOKEN for resume downloads, paid job permissions include actions read and OIDC. Uploads the full run directory including hidden exec streams, separate host proofs and cost rollup. **Do not reuse its broad artifact upload for private inputs.** |
| `agentic-v2-stage-a-probe.yml` | `mode=dry-run/paid`; free check then one paid probe task, not the five-task run. | HF_TOKEN, Azure OIDC and Foundry endpoint. Paid artifact is metadata-only model-call record, not prompt/reply/reasoning text. Even its free job fetches the dataset; it is not this card's input-free rehearsal. |
| `gpt54-time-budget-first-v2.yml` | `reviewed_source_sha`, `reviewed_source_tree`, `request_sha256`, `request_json`; one source-bound registered task/job, with no replay. | Validates before credentials; HF private input/claim/retention and Azure OIDC separated by phase. Only validated `completion.json` is uploaded; canonical outputs remain private. This is the stronger privacy pattern reused here. |
| `agentic-sandbox-preflight.yml` | Image/SBOM/AppArmor inputs; self-hosted model-free containment checks. | No model credential permitted. Not the selected standard-runner execution route. |

The surveyed V2 workflows contain no explicit `::add-mask::` step.
GitHub's masking of configured secrets is not a privacy boundary for task
wording, reference contents, tool output or generated deliverables. The new
route supplies no secrets, prints only fixed status, reads only the public
score-free catalogue, and uploads exactly one generated `capture.json` per
task. It never uploads a directory, raw stream or file hashes.

This is an additive sibling in the existing `.github/workflows/agentic-v2-*`
path, reusing its plan-to-matrix structure and pinned checkout/Python/artifact
actions. It does **not** invoke the paid V2 conversation runner, Firecracker
boot action, Azure route, or legacy shard/resume logic; those would inherit
unapproved spending, private capture and obsolete VM requirements.

## Fixed cohort and grading contract

`core/execution_envelope_tasks.py::select_advance_check_tasks` derives the five
ordered IDs from `experiments/execution_envelope/gdpval_task_catalog.json`.
`advance_check_plan.yaml` pins the same order and input versions.
`experiments/execution_envelope/gpt56_sol_ghcp_codex_vm_gate.yaml` binds the
GHCP identity, original-input policy, inherited developer instructions and
grader policy. That older inert VM prerequisite contract remains unchanged;
its VM/reset blockers are not assertions about this new Actions target.

The grader template is
`grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml`: rubric revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, prompt v2.2, Sol/Max judge,
one pass/task, grade schema 1.4. The GHCP gate uses only its policy blocks,
**not** its 220-task rerun identity. Five-task inference identity, original
input verification and grader validation remain unresolved. Nothing is graded.

## Local rehearsal and capture

From `batch-runner`, `python3 ghcp_sol_actions_gate.py --matrix` emits the
five-task matrix. For each returned ID, run:

```bash
python3 ghcp_sol_actions_gate.py --dry-run true --task-id TASK_ID \
  --state-root /absolute/fresh/parent/ghcp-sol-gate
python3 -m pytest -q tests/test_ghcp_sol_actions_gate.py
```

The state-root parent must exist. Each task gets a fresh directory; reuse
refuses. `private/` contains empty transcript/tool-call/command streams, empty
input/output hash arrays, a dry-run exit record and an empty `files/` directory.
These are path placeholders, **not** real input staging or transcript evidence.
Only `capture.json` is artifact-eligible; it contains relative logical paths,
requested settings, actual Python/OS versions and explicit unavailable CLI/
served values. Local execution does not prove the requested hosted image ran.

Proposed paid caps are 1200 seconds/task (the V2 stage cap), 64 model turns/task
(draft choice), zero retries; neither approval nor live enforcement is claimed.
The offline collector now applies the time/turn values only as described above.
The dry-run workflow enforces 60 seconds/process and five minutes/job with
zero model turns. Unknown usage/cost/grade stay null, never inferred as zero;
usage and cost have explicit `not available` statuses.
Both planner and task jobs independently reject every `dry_run` value except
the exact string `true` before checkout. The Python entrypoint separately
rejects false or malformed values before catalogue reads or capture writes.
Local tests execute both shell guards with true, false, missing/empty,
case-changed, numeric and whitespace-bearing values; they do not dispatch
Actions or prove hosted behavior.

## Questions blocking paid execution

- How are scoped GHCP/Copilot credentials supplied, kept outside model tools,
  and disposed of on standard Actions runners? Is this unattended use supported?
- Which supported route actually selects the Codex agent harness, pinned CLI/
  SDK versions, Sol model, Max effort and 1M context without fallback? What
  independent served metadata proves each rather than repeating requested values?
- How are original prompts/references verified and staged privately, and raw
  transcript/tool/file captures retained privately without leaking in logs,
  artifacts, action diagnostics, credentials or caches?
- What network/tool permissions, budget/usage policy, paid timeout/turn/tool/
  token caps, cancellation handling and no-retry admission are approved?
- What five-task inference/grader identity, judge validation, repeat/variance
  plan and pass/fail criteria govern the decision? No quality result follows
  from this wiring rehearsal or from these five cases alone.
- Who reviews the exact source and authorizes push, hosted dry-run dispatch,
  and separately paid inference/grading? All remain unapproved on this card.
