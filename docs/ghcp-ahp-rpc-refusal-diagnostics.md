# Native RPC refusal diagnostics (zero turns)

This change records evidence only. The native RPC allowlist, refusal predicates,
thread policy, HTTP boundary, admission, runtime pins and two-patch manifest are
unchanged. `execution_allowed=false` remains mandatory. Only hosted Actions may
run the real host; local tests use inert stdio, never the SDK or a provider.

## Reconstructing run 42906454540

The original wire artifact contains nine forwarded/attempted native messages,
ending in `skills/list`, followed by two `wire_model_free_rpc_refused` records
(process `wire-60.jsonl`, event sequences 27 and 28). Neither old record contains
a method. Its backend log reports a transport error and then cancellation of
both `skills/list` and `hooks/list`. These old records alone cannot identify two
distinct methods, nor can the missing fields be backfilled as observations.

The source-reconstructed sequence is:

1. `_fetchSkillHookContainers` starts `skills/list`, then `hooks/list`, in
   `Promise.all`: pinned VS Code
   [`codexAgent.ts:8569`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L8569)
   and [`8589`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L8589).
2. The preload rejects the unlisted method before the original stdin write.
   `_writeMessage` emits `onTransportError`:
   [`codexAppServerClient.ts:350`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAppServerClient.ts#L350).
3. The host tears down that connection:
   [`codexAgent.ts:2762`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L2762),
   [`4689`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L4689).
4. `dispose()` calls `stdin.end()`:
   [`codexAppServerClient.ts:451`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAppServerClient.ts#L451).
   The unchanged preload frame parser has not removed the rejected frame, so EOF
   inspects it again. Two refusals can represent **one RPC**, not two calls or a
   retry. The fixture fixes this sequence; the next authorized zero-turn run
   must confirm method/trigger/ordinal rather than treating this as measured.

## Diagnostic contract

Native refusals now include a bounded, redacted `method`, its scalar type,
`stream`, `rpc_sequence`, `write_sequence`, `trigger`, message **shape only**,
and `forwarded=false`. Existing event `sequence` is process-local;
`rpc_sequence` counts per-stream inspections and may count the same buffered
frame again on EOF. `write_sequence` counts inspected chunks, not successful
native writes. No ids, params, cwd, response bodies or raw refused frames are
retained. Long/non-scalar methods are replaced by explicit sentinels. Missing
old diagnostics remain missing, not inferred.

`wire-capture.json.native_rpc_refusals` and the wire export receipt preserve
these fields. Existing receipt propagation carries them into
`probe.json.wire_capture` and `handshake.json.wire_capture`. The original
producer `summary.md` is uploaded beside JSON, so the existing mandatory
Markdown/hash-chain verification can run on downloaded artifacts. No consumer
recreates that summary. The historical workflow hash is still checked after
an exact, single-match inverse of this upload-path addition.

## Future classification, not authorization

`hooks/list` is category **(a), metadata candidate**, not permission to run a
hook. The pinned 0.163.0 generated
[`HooksListParams.ts:9`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/HooksListParams.ts#L9)
accepts only optional cwd selectors; its response describes hook metadata.
The native tag `rust-v0.163.0`, commit
`83086188ae0614bd882818ff1aa23f3194962012`, routes it to
[`catalog_processor.rs:150`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/app-server/src/request_processors/catalog_processor.rs#L150)
and [`613`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/app-server/src/request_processors/catalog_processor.rs#L613):
load cwd configuration/plugin catalog, call `codex_hooks::list_hooks`, return
metadata/warnings/errors. This is not `thread/start`, `turn/start`, hook
execution or a config-write RPC; the implementation of
[`registry.rs:304`](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/hooks/src/registry.rs#L304)
only discovers entries and returns warnings. Plugin/config loading is a dependency to audit
before any future allowance; the method name alone is not a safety guarantee.
Keep it blocked this turn, along with login, config writes, execution and turn
RPCs. EOF reinspection has no separate RPC to allow.

The current [official App Server documentation](https://developers.openai.com/codex/app-server/)
describes the JSON-RPC lifecycle, but the fixed-version sources above govern
this investigation. No newer model or protocol version substitutes for the pin.

## Verification and stop condition

Fixtures cover the nine-message prelude, write refusal followed by EOF refusal,
both free modes, response/error envelopes, dangerous methods, per-stream
ordinals, batched writes, bounded/redacted diagnostics, legacy unknown fields,
and receipt export. They cannot establish real thread or served-model settings.
Only one new authenticated zero-turn dispatch is authorized after green push
CI. Any failure, including 401/403, ends that run with no redispatch or retry.
