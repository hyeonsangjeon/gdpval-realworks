# Latest task result

## PR750 observation process ownership correction — 2026-10-05

The new-mode cleanup path now retains process ownership across parent exit and
reparenting. The single new offline selector reported **30 passed, 147 deselected
in 4.91s**, exit 0. The supported path was exercised with a controlled kernel
adapter. The isolated real-host case refused admission with
`time_budget_owned_process_host_required`, caused by `FileNotFoundError`, errno 2;
it did not exercise real orphan termination. Delivery remains **HOLD** for
whole-HEAD review and applicable CI acceptance. All launch gates remain closed.

### Correction and pre-edit review

The leader identified the P1 against `0cee74941b9a093109d7c32a289d563616626e99`,
tree `33e3f40304217fdc42d73b2f49e0310001f6c6be`. A current PPID walk can lose a
live descendant after its parent exits, so its empty result cannot authorize host
reuse. The prior persistence/finalization correction addresses review
`5413283960` at its stated software-evidence level; those I/O paths were not
re-investigated or re-tested here.

Before editing, the same-session `.github/agents/extreme-reasoner.md` charter
review classified the process boundary and the source roles. The decision was
APPROVE-WITH-CONDITIONS: an exclusive Linux subreaper must own subsequent children;
kernel-confirmed child pidfds must prevent collateral signals and PID substitution;
termination confirmation must spend the original cleanup remainder; uncertainty
must block reuse. The review covered orphan loss, concurrent/pre-existing work,
PID reuse, unsupported interfaces and expiry. Existing V2 pidfd primitives were
the source precedent, not permission for a bare-PID or process-group fallback.
This same-session check is not the pending independent whole-PR review.

`TimeBudgetObservation` now acquires process ownership before durable admission.
It requires one kernel thread, no live or unreaped children, default SIGCHLD
handling, working pidfd signalling and waitid interfaces, and a verified Linux
child-subreaper setting. An externally configured subreaper is not adopted.
Unsupported or already occupied hosts refuse before admission receipts or
provider setup. A process-wide ownership token prevents another receipt directory
from bypassing uncertain cleanup; forked hosts cannot inherit its authority.

The subreaper retains orphan attribution after parent exit, including descendants
created during termination. `/proc` child lists only locate candidates. Cleanup
opens pidfds and uses `waitid(P_PIDFD)` to confirm each target is a current child
before signalling through its handle. It never signals by process name, bare PID
or process group. TERM, KILL, orphan adoption and blocking reap share the existing
cleanup deadline. `waitid(P_ALL)` includes Linux clone children via `__WALL`;
only kernel ECHILD, together with a single-threaded host, confirms emptiness.
An empty candidate list or a signal attempt is not completion evidence.

Finalization rechecks ownership and child/thread state before host release. It
restores the subreaper setting only after confirmed cleanup, within the same
deadline. Incomplete confirmation retains a non-reusable result and ownership
uncertainty. Durable cleanup snapshots remain pending and non-reusable; the
existing one-use, before-deadline finalization confirmation remains required.
Returned evidence names the ownership mechanism and whether owned processes
were confirmed stopped. No runner hook or omitted-control production path changed.

Only the helper, its existing test module and its one prospective source pin
changed before proof. Existing deadline tests now use the same controlled kernel
adapter, and the directly coupled Codex fake models kernel-owned children rather
than treating an SDK handle as kill authority. Those earlier tests were not rerun.
No launch guard, historical profile, F-derived judge, hash algorithm, compiler,
workflow or provider interface changed in this correction.

### Source identities and unchanged policy

| Identity | Value |
| --- | --- |
| Clean tested correction | `c73a71b5307a8d1f3405cf3cc3f55cb3d8d4cb3e` |
| Tested tree | `c3935a504c1b5922f2e07405c0356df270f40239` |
| Changed helper SHA256 | `4ce90fd05e4c8f0c32d3a0267f089bbaf0a279ef704852c994af6debb12a6c26` |
| Prospective manifest SHA256 | `f86d4bd53473ee27089e7ff8e8b4dff31cdd1b9afb883ab937a4319bc2b35dba` |
| Accepted main | `f609aff0deefd3c5afd7a6322ba6473c8b3e6c98` |
| Accepted main tree | `3b318f9d70cbf2a080de28ff76fdfd5e278e1264` |

Frozen F remains `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, with genuine whole TEMPLATE
closure `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The changed runtime R cannot claim that judge identity. Both historical profiles,
paid RESULT/PARENT/READER bindings, input identities and prior receipts remain
immutable. The closed 30-cell/8-cell studies and 10800-second store are unchanged.

The fixed 20-observation GPT-5.4/direct-v1/xhigh configuration comparison retains
five tasks, ABBA, two repeats, concurrency 1 and no external replay/resume/retry.
Generation remains 1200 seconds from first start. Cleanup still ends at first
start plus 1220 seconds after timeout, or at most 20 seconds after an earlier
terminal outcome, including finalization. No grace is reset or enlarged. Native
counters remain observation-only when available; there is no native request/token
or money hard-cap claim.

### One new targeted proof

The clean correction was pinned before this token-free/offline Python 3.10.12
invocation, which began at 2026-10-05T11:32:56Z. The 300-second outer limit and
5-second termination grace bound this software check, not the study or CI.
The command selected only `time_budget_observation_deadline_process_ownership`.
No earlier successful node, finalization selector, broad suite or CI job was run.

The 30 cases cover two orphan-adoption timings, thirteen admission refusals,
three child-pidfd/PID-substitution cases, six incomplete-cleanup cases, three
ownership-loss cases, exclusive release/re-admission, the prospective pin and
the isolated platform contract. Fake clocks and controlled kernel transitions
exercise the supported path and expiry without a provider or long stall. Assertions
cover unrelated processes, returned/durable non-reusable state, retained leases
and refusal to bypass uncertainty through another directory. The platform result
is an explicit local refusal, not a supported-kernel success or a skipped failure.

This public display redacts private executable, worktree and evidence locators.
It is not the exact private script identified by the command hash below. From
the worktree's `batch-runner` directory:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 TMPDIR=<private-evidence-directory> \
  PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  DO_NOT_TRACK=1 GIT_NO_LAZY_FETCH=1 \
  timeout --kill-after=5s 300s <existing-py310> -m pytest \
  -vv -rA --tb=short --color=no -p no:cacheprovider -m 'not integration' \
  --basetemp <new-private-directory> tests/test_gpt54_time_budget_comparison.py \
  -k time_budget_observation_deadline_process_ownership
```

| New private evidence | SHA256 | Bytes |
| --- | --- | --- |
| Exact command | `7929ea0bef8794cdc27fc6b1b9fc2d62127fe44b0ea8bd822ec5057e24b2ce69` | 905 |
| Combined stdout/stderr log | `6beeafaf7e4d5d2d28e9baf3485555e4a78c2924ea2972ee94ab51e4efc58b4a` | 9650 |
| Receipt with all 30 passed node IDs and platform outcome | `f2e73a2882efdbce45dec6ad38eb9432e57d7f4a443706b183a6d23efaa7bbdf` | 6116 |

### Prior proofs remain separate

The [immutable prior correction record][prior-record] retains the original
command/log/receipt identities and links to the earlier passed/failed-node
inventories. All prior local evidence files remain untouched.

| Earlier invocation | Tested HEAD | Actual result |
| --- | --- | --- |
| Original combined selector | `1d5a9c2472e17fde1c0ad2dc1a0f3300772b5c95` | 5 failed, 46 passed, 75 deselected in 8.35s; exit 1 |
| Five-failed-target continuation | `73a86933934ac0a9cc260a963f042414b61bc151` | 5 passed in 7.55s; exit 0 |
| Persistence/finalization selector | `d6bff25dc037c96bccf418a0fe06b00402592bc7` | 21 passed, 126 deselected in 6.51s; exit 0 |

These are separate observations at different commits, not an aggregate 51-pass
or whole-HEAD proof. The new selector replaces none of them. Only `CHANGELOG.md`
and this single current task record follow the new pinned proof.

### Remaining limits and gates

Real orphan cleanup on a host supporting all required Linux/proc/pidfd interfaces
remains unproved here. The current host refused admission. SIGALRM supervision
does not establish a hard real-time bound on uninterruptible kernel stalls or a
descheduled host. Controlled lifecycle cases do not establish live enforcement,
backend cancellation, remote process ownership or billing.

Whole corrected-HEAD review, applicable CI and delivery acceptance remain pending.
Dispatcher/capture selection, verified credentialed inputs, F-derived grading
materialization and a separately reviewed source-bound live direction remain.
No CI query/poll/dispatch/rerun, Node/HF check, private original/consumed-artifact
access, real preparation, provider/model/grader/HF/Azure call, Project edit or merge
occurred. Previous worktrees and the consumed preparation remain untouched.

The catalog was inspected once. The source-provenance/architecture charter
constrained the ownership change; `experiment-design` preserved the fixed policy
during the prospective pin update. `im-not-ai-en` preserved the facts, hashes and
limits in these English records. No unrelated skill or new design investigation
was used.

[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/0cee74941b9a093109d7c32a289d563616626e99/tasks/LATEST_TASK_RESULT/README.md
