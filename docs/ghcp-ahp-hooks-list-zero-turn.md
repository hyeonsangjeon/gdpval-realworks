# One additional zero-turn metadata method: hooks/list

This implements the leader's follow-up to run 42919729794. It does not open
model turns, inference HTTP, hook execution, a paid connection or the five-task
gate. The existing read-only RPC set is unchanged. The additional
`ZERO_TURN_CATALOG_RPC` set contains exactly **hooks/list** and is consulted only
with both `modelFree=true` and `sessionOnly=true`.

## Accepted request, not the entire SDK schema

The fixed SDK 0.163.0 schema permits optional `cwds`; the zero-turn gate accepts
only the concrete shape sent by the pinned host:

```json
{"id": 10, "method": "hooks/list", "params": {"cwds": ["<owned probe state>/workspace"]}}
```

The envelope may additionally have `jsonrpc: "2.0"`, and nothing else. The id
must be a nonnegative safe integer or a nonempty string of at most 256 code
units. Params must contain only `cwds`, with exactly one entry matching the
workspace derived from the verified fork contract's absolute, normalized state
root. Missing/empty/default cwd, other paths, extra params, reply/error envelopes,
and unknown fields are refused before the original stdin write. No prefix,
case folding, wildcard or alias is used. Capability-only mode still refuses
even a well-formed hooks/list request.

Source: VS Code commit `2c33b50b16c472efe58357d1d2a8a5414bc23fbf`,
[`codexAgent.ts:8589`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L8589)
and [`8610`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/codexAgent.ts#L8610);
[`HooksListParams.ts:9`](https://github.com/microsoft/vscode/blob/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost/node/codex/protocol/generated/v2/HooksListParams.ts#L9).
The earlier classification and native metadata handler sources are in
[the refusal investigation](ghcp-ahp-rpc-refusal-diagnostics.md). Listing command,
prompt or agent hook metadata is not executing those hooks.

## Receipt and accounting

`wire-capture.json.native_hooks_list` records each query's process/stream,
request inspection ordinal, observer event sequence, bounded params summary,
and attempted-delivery status. The owned path is learned by the existing
redactor before raw request capture; only its redacted placeholder and
`{fields:["cwds"], cwd_count:1, cwd_scope:"owned_probe_workspace"}` survive.
It also records whether a correlated response arrived, response kind,
pre-redaction UTF-8 JSONL bytes including the newline, cwd-entry count and
hook-entry count. These bytes are not tokens or usage. Missing replies or
unmeasured/malformed fields remain `not_reported`, not zero. Response bodies
continue through existing secret/identity redaction; they are not executed.

The wire export receipt carries the same query ledger into probe and handshake
receipts. The independent auth-smoke consumer accepts only the matching narrow
redacted envelope/summary, not every request with that method name. No response
field is promoted to applied policy, served model or admission.

A rejected outgoing frame retains its original exception and remains pending.
EOF or a later write still throws that exception without re-evaluating the
frame, emitting another refusal, or authorizing a later packet. Two genuine
queries with separate request ids still count separately. Historical evidence
is not deduplicated or rewritten. Batched chunks remain all-or-nothing before
the underlying write, including a valid catalog query followed by a forbidden
turn.

## Verification and stop rule

Offline fixtures cover valid byte-preserving queries, the pinned nine-message
prelude, fragmented Unicode responses, two genuine queries versus EOF,
bad params/envelopes/paths, hooks execution/registration/mutation and unknown
names, capability-only denial, failure latching, batched-turn refusal,
redaction, receipt propagation, and independent-consumer forgery rejection.
No vendor host or model runs locally. Only one hosted authenticated zero-turn
dispatch is permitted after green push CI; on a new refusal or 401/403, collect
evidence and stop without repair or redispatch. Pins, both patches, admission,
turn/HTTP guards and `execution_allowed=false` are retained.
