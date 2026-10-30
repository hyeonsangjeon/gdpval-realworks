# GHCP-backed Codex Agent Host: model-free hosted probe

This is a new candidate-path probe, not the Copilot CLI default-agent gate and
not a Sol benchmark. It changes no existing gate, seal, task input, pricing or
paid workflow. The owner's 2026-10-29 execution policy is retained: NAS is for
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
immutable GitHub links for all 18 citation groups, checked against the pinned
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

Local verification: **195 passed, 0 failed, 0 skipped** (114 new probe cases
plus 81 existing runner-admission cases). All 18 source-citation groups were
also checked against the downloaded pinned source, with no binary execution.

```bash
cd batch-runner
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -o addopts= -p no:cacheprovider tests/test_ghcp_ahp_probe.py
```

Do not run `prepare`, `probe`, `code agent host`, or a Codex host locally to
validate execution. The actual hosted result is collected after the single
branch publication; it is deliberately not invented in this pre-run commit.
