# Native Foundry connection diagnostic

`scripts/diagnose_codex_foundry_connection.py --send-request` uses the existing
Codex runner to open one native turn. Without that flag, the script emits a
plan rather than sending a turn. The workflow's existing `native_only` route,
deployment/authentication inputs and request/stream retry settings are unchanged.
This document does not authorize a live request or supply a deployment binding.

## Stream deadline and cleanup

`--timeout` defaults to120 seconds. It now limits native stream consumption
with one monotonic deadline set before the stream worker starts. Events do not
reset the deadline. The synchronous `observe_stream` helper still preserves
structured turn errors, usage and final-answer observations; ordinary successful
records keep the `codex_foundry_connection/3` schema and their existing output.

Previously, the script passed120 seconds to `CodexAgentRunner` but consumed
the native stream directly, bypassing the runner's deadline loop. The existing
20-minute workflow timeout was the only effective outer cap for a stalled
stream. The script now uses the runner's established daemon-worker/bounded-join
pattern without changing core or switching to another SDK/runtime.

After a stream timeout, the script attempts to interrupt the turn if its stream
worker is still active, then close the runtime and clean the workspace. Only
the stream worker closes its iterator. Cleanup shares the existing
`CODEX_INTERRUPT_GRACE_SECONDS` bound, which defaults to20 seconds;
interrupt waiting uses at most half the remaining grace so a stuck interrupt
does not prevent the close attempt. Cleanup does not refresh the stream deadline
or start another turn.

A timed-out stream produces `turn_timed_out` and CLI exit1. If interruption,
iterator close, runtime close or workspace cleanup fails, or a cleanup worker
outlives the grace period, the receipt instead reports `unclassified_failure`
with error stage `cleanup` and exit1. Fixed cleanup wording does not expose SDK
error text. A previously completed turn cannot retain a `connected` verdict
when cleanup was not established. Missing usage stays unknown, not zero cost.

The receipt retains the latest matching usage notification actually received
through the bounded cleanup attempt, even when the stream times out, later
raises, or cleanup fails. The existing parser publishes a fresh `_usage_record`
projection for each update; the final receipt snapshots it without another
wait. A worker surviving cleanup cannot mutate that receipt with later updates
or turn a late completion into success. No matching usage event leaves `usage`
null; recorded zero counters remain zero. Thread-total and most-recent-request
counters stay separate and are not combined into a price or invoice.

Authentication, runtime initialization and thread/turn-start handshakes remain
outside the stream deadline. The20-minute workflow cap remains an outer limit,
not proof that a child was successfully terminated. A daemon worker that does
not stop within cleanup's grace is reported as a failure; the script cannot
establish successful child cleanup merely by returning. No orphan-process sweep
or additional runtime hook was added.

## Evidence and live boundary

The focused offline selector
`tests/test_codex_foundry_connection_probe.py::test_native_stream_deadline_and_cleanup_are_bounded`
uses local fake streams, bounded event synchronization and a virtual monotonic
clock. It covers normal completion, cumulative expiry despite individual events
arriving within the limit, stalled reads, cancellation, and cleanup failures.
The usage-retention correction also covers usage before a stall or stream
error, true missingness, wrong-turn notifications, latest and zero-valued
updates, and receipt stability after the cleanup grace. The earlier13-case1.40s
deadline proof remains separate history; the changed19-case selector passed
in1.69s. These are authored fixtures and pytest durations, not live observations.
Its exact source state, command, result and log identities are in the
[latest completion record](../../tasks/LATEST_TASK_RESULT/README.md).

These fixtures do not prove live Foundry connectivity, deployment identity,
child-process termination, GPT-5.6 Sol service, Max enforcement,1M entitlement,
sandbox tool execution, benchmark readiness or complete provider billing. A
native turn is not an HTTP-request count: the unchanged runtime can remint auth
and resend even with request/stream retries configured to0. Thread-total usage
and most-recent-request usage retain their separate meanings; an unpriced or
missing receipt is not a free one.

The next live direction still requires final immutable-source review and CI,
an approved private deployment-to-GPT-5.6-Sol binding, and separate leader
execution direction. The missing binding is not a request for generic budget
approval. Do not execute or redispatch the prepared Foundry candidate from this
documentation or infer a deployment from the model label.
