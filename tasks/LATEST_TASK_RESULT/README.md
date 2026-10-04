# Latest task result

## PROJECT5-NATIVE-DEADLINE-RETAIN-OBSERVED-USAGE-20261004-1241

The native Foundry diagnostic now retains usage actually received before a
timeout, later stream error or cleanup failure. One newly authorized invocation
of the changed bounded offline selector passed:19 passed in1.69s at
implementation`a2f36d9bdde300446c981fc0dd1b7195596fa9b6`.
Selector, invocation and all log/status-capture exits were0, with no timeout
and zero guarded live effects. These are19 authored fake-stream cases, not
live turns, model calls or a measured Foundry improvement.

Reviewed HEAD`025a1c122d5c03bf56d8d4781dc5c98fd40391c5` is HOLD for loss of
observed failure usage, not approval. Its prior13-case1.40s deadline proof is
preserved below as separate evidence, not coverage of this correction.

### Scope and reached cleanup boundary

Only the diagnostic script and its existing focused test module changed in
the correction's implementation commit. An optional usage callback in the
existing `observe_stream` parser publishes fresh `_usage_record` projections
for matching notifications; its default synchronous return contract stays
unchanged. The receipt snapshots the latest projection after the existing
bounded cleanup attempt, including failure records constructed before cleanup.
A surviving worker replaces its own state slot and cannot mutate the returned
receipt. No event parsing is duplicated and no extra wait or turn is added.

Ordinary successful output, the `codex_foundry_connection/3` schema, retry
settings and the effective cumulative deadline remain unchanged. Notifications
cannot reset the monotonic deadline, and a completion beyond that deadline
cannot become success. Without a matching notification at the snapshot
boundary, usage stays unknown, not zero cost. Recorded zero stays zero;
thread-total and most-recent-request counters remain separate, not an inferred
per-request difference, price or invoice.

The earlier120-second value was passed to `CodexAgentRunner` but bypassed by
the script's direct stream consumption. Its only effective outer cap was the
20-minute workflow timeout. The new120-second default applies to stream
consumption; authentication, runtime initialization and thread/turn-start
handshakes remain outside it. Native-only workflow routing and all YAML,
core/runtime, graders, registration/source pins, deployment/auth settings,
provider permissions and historical data remain unchanged.

Cleanup attempts to interrupt the turn if the stream worker is still active,
then uses the existing runtime close/workspace cleanup path. It shares
`CODEX_INTERRUPT_GRACE_SECONDS`, default20 seconds;
interrupt waiting uses at most half the remaining grace to leave time for
close. Only the stream worker closes its iterator. A stream timeout produces
`turn_timed_out`/exit1. Any cleanup failure or worker surviving the grace
produces `unclassified_failure`, error stage `cleanup`, and exit1 instead of
retaining `connected`. Cleanup messages are fixed; stream failures retain the
existing redaction path. No child termination is inferred from a daemon worker
or the20-minute job limit.

The19 cases covered completion, structured turn failure, no completion,
stream error/redaction, a stalled stream, cumulative events, failed/stalled
interrupt, failed/stalled runtime close, failed/stalled iterator close and
workspace cleanup failure. They also covered no usage before a stall,
wrong-turn usage, latest and zero-valued updates, usage during cleanup and a
worker that finishes only after cleanup's grace. In17 fixtures, matching usage
was retained;2 with no matching usage remained null. A late update during
cleanup was retained without reviving success. An update after the receipt's
snapshot did not mutate it. The cumulative fixture advanced a virtual clock
by60 seconds per event across3 events: each gap was below120 seconds, while
their180-second sum exceeded the one deadline. These are synthetic clock
values, not measured latency. Actual blocking fixtures used a0.03-second
stream limit and0.08-second cleanup grace with bounded event synchronization.

Runtime close was attempted in every case. The deliberately stalled-close
case returned a cleanup failure while its fake close worker was still alive;
workspace cleanup had not yet run at that return boundary. The new
`usage_after_cleanup_grace` case returned failure while the fake stream worker
was still alive, retaining the usage already received. Only fixture teardown
released these workers, after which every fake worker stopped and every test
workspace was cleaned. The returned record and written JSON remained unchanged.
This proves reporting of incomplete cleanup, not
successful real-child termination. The guards recorded zero network, child,
token, runtime-launch, legacy-probe and sleep effects. No real auth command,
model call, grading, live observation, workflow dispatch or replay occurred.
See the [diagnostic usage boundary](../../batch-runner/docs/codex_foundry_connection.md).

### Exact tested state and one proof

The clean implementation HEAD is`a2f36d9bdde300446c981fc0dd1b7195596fa9b6`,
tree`ee5e643e76ea9413e1ce732e5ae767c958613b4e`, parent/HOLD source
`025a1c122d5c03bf56d8d4781dc5c98fd40391c5`; main base remains
`c4608db7857329491fcbd492c990cdb99362d936`. Script SHA256 is
`e5e7994319bea17e70dca806bafb0d472a7ff51b26b9b31b6adaa0fe51147202`;
test SHA256 is`6f32fcd6dd830bc79095adde4d4cfa4be6a54e604317ad6be061c8711ec93578`.
Those implementation bytes remain fixed after the proof; the follow-up adds
only directly related usage documentation and completion records.

Exact token-free invocation:

```text
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/ai-work/copilot/worktrees/codex-native-stream-deadline-20261004-1139/batch-runner bash /tmp/native-deadline-retain-usage-20261004-1241.PqpiFf/run-selector.sh
```

From `batch-runner`, the launcher ran exactly:

```text
timeout --signal=KILL 180s /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q -s tests/test_codex_foundry_connection_probe.py::test_native_stream_deadline_and_cleanup_are_bounded --tb=short -x
```

Python3.10.12/pytest9.1.1 collected19 items; all19 passed in1.69s. The180-second
launcher bound was not reached. The1.69s is pytest duration; outer elapsed was
not measured. No prerequisite probe, timing wrapper, dependency install, old
selector or broad suite ran. There was no retry.

| Evidence | SHA256 |
| --- | --- |
| selector.log | 02087cfcf3ee689d491a51547c93b1fcef88754ae77153fda5a7df56f40cbfee |
| selector.status | 67a36859a82b6160ea609eaaf16718f72f3f10a3a68f46c8fa2cac3c8548ee0a |
| invocation.log | 2a09f1ba8bfff221c712f8a91db8c29bc438b043fbe04720f09f70fed73f15f8 |
| invocation.status | 0ee12bd089d3b9d1d70110bee6408ea428e19d53dea06f206ca30aa55330c463 |
| run-selector.sh | 9157828626316dd7b2546f159ba95866a3a70f93713cb327cbdbc30fae81fee6 |
| tested-state.md | 4c2173286cd2e377af0a1212efa67ec75c453acdcea5c324520cbbd22d8c6f68 |

Evidence and reporting checkpoints are retained under
`/tmp/native-deadline-retain-usage-20261004-1241.PqpiFf`. The base-to-HEAD diff is the
scope check; no repository-wide file inventory or new immutability assertion
was added to the test.

### Prior evidence and remaining gates

The original deadline proof was13 passed in1.40s at
`a243203e11b7f96125c47d14fa116add39810d1a`, tree
`7673f5b4634c65b690d8b14755e5fa816f7a9e4b`. Its log SHA256 is
`c886afb2e217f348c4c5a89ac67a6d270f608d1808fed0e75b775863295d8e60`,
preserved at `/tmp/native-stream-deadline-20261004-1139.wqxj4M/selector.log`.
Its commands, capture statuses, source hashes and limits remain in the
[historical completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/025a1c122d5c03bf56d8d4781dc5c98fd40391c5/tasks/LATEST_TASK_RESULT/README.md).
That successful narrow proof did not cover retention of usage on failure.
The leader's HOLD at025a1c identifies that gap; it is not source approval.
The new invocation validates changed implementation/tests, not a rerun or
relabeling of the unchanged historical candidate.

The leader supplied accepted PR739 HEAD`0f9162093444e3143960e631a95edac6e46f3b29`,
tree`1a4008d275e4c88397fc574c922b49a4ec80e33a`, owner
review[5403796916](https://github.com/hyeonsangjeon/gdpval-realworks/pull/739#pullrequestreview-5403796916)
and all10 applicable checks, delivered as this task's main base
`c4608db7857329491fcbd492c990cdb99362d936`. Its
[accepted completion and proof provenance](https://github.com/hyeonsangjeon/gdpval-realworks/blob/0f9162093444e3143960e631a95edac6e46f3b29/tasks/LATEST_TASK_RESULT/README.md)
remain history, not new validation of this usage-retention change. No accepted proof
or consumed observation was rerun, queried or relabeled. The original30-cell
pilot,8-cell retention study and retrospective exp035 data remain separate
and unchanged, including all outcomes, grades, costs and epoch boundaries.

The prior private handoff at
`/tmp/foundry56-existing-native-direction-20261004-1108.1rqRTo/handoff.json`,
SHA256`71d1979ec1e5158118033747134fc00284775dd0cb65bb7f86047c131dcee502`,
is source-inspection evidence, not a successful live test. No deployment
binding was supplied. The leader found no deployment/model/Foundry-named
repository-variable candidate; this task did not repeat that search. The
live request remains blocked on an approved private deployment-to-GPT-5.6-Sol
binding, not generic budget approval. The existing pilot stays launch-disabled;
its null identity/capability fields are not measured absence.

Final immutable-HEAD review, applicable same-HEAD CI and leader acceptance
remain outstanding. Any live direction also requires the private binding and
separate leader execution direction. No Foundry connectivity, Max enforcement,
1M entitlement, tool execution, five-task readiness, comparison with GPT-5.4
or complete billing is established. One native turn is not exactly one HTTP
request because the unchanged auth-remint path can resend. Missing usage or
cost remains unavailable, not zero. The prepared Foundry candidate was not run.

The full skill catalog was reviewed once. experiment-report-en then protected
im-not-ai-en applied to these numerical records and usage text. Source,
structural and candidate checkpoints, the change ledger and literal/fidelity
reconciliation are retained. Reverse-condition review is explicitly
same-session, not an independent verdict; no failed editorial transport was
retried. experiment-design is not applicable because no benchmark axis or
configuration is being designed. UI/animation, repository audit and provider
research are outside this narrow script correction.

This correction continued only in the existing PR740 worktree/branch from
025a1c. No branch/worktree/PR creation or repeated duplicate search occurred.
Finished worktrees and the preserved checkout remain untouched. Existing
author/committer identity is
hyeonsangjeon <wingnut0310@gmail.com>, without attribution trailers. No Project
mutation, merge, Azure management, credential/permission change, experiment
expansion or CI polling occurred. These records stop at pre-merge facts and
do not claim the carrying PR's future merge state, SHA or time.
