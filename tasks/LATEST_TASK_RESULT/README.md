# Latest task result

## PR750 deadline persistence and finalization correction — 2026-10-05

The diagnosed persistence and finalization gaps are repaired. One new offline
selector at the pinned correction reported **21 passed, 126 deselected in 6.51s**,
exit 0. No previously successful target was rerun. Delivery remains **HOLD** for
full-HEAD source review and applicable CI acceptance; the leader's first runtime
review found these gaps and did not complete the whole-PR review.

### Correction scope

`TimeBudgetObservation.terminal()` now arms supervision against the original
absolute cleanup deadline before terminal receipt I/O, including calls from the
one-shot generation alarm and calls outside a generation supervisor. Timeout
remains latched before interruption. Receipt writes use unbuffered I/O so alarm
unwinding cannot initiate another buffered flush. Intermediate deadline checks
catch an I/O operation that returns after expiry even without a delivered alarm.

`finish_cleanup()` supervises directory and lease checks, cleanup receipt
persistence, lease unlink/fsync and directory close. It samples time again after
supervisor teardown and confirms completion only when all finalization I/O has
returned before the same deadline. `cleanup_finished_monotonic` records that
confirmation; completed cleanup elapsed time is not extended by later readouts.
An already expired observation performs no new receipt write. Persistence errors
remain refusals, and timed-out finalization remains a non-success.

Durable `.cleanup.json` snapshots explicitly retain `finalization_pending=true`,
`cleanup_complete=false` and `host_reusable=false`. A snapshot cannot attest to
completion of its own fsync. Same-host reuse therefore needs a one-use in-memory
confirmation issued after finalization, bound to the process and held directory
identity. If unlink succeeds but fsync or close expires, retained admission history
still blocks another observation even though the lease pathname may be absent.
A restarted or forked host cannot adopt that uncertainty or infer release from a
receipt. Ordinary before-deadline completion still permits the same host process
to admit a different registered observation; it never permits an observation retry.

Only the deadline helper, its existing test module and its one prospective source
pin changed before proof. The helper's SHA256 is
`7ba7bffc898868a33a25b701af2335db8310cecbae3eac9e1e749ca84d33e9a3`;
the prospective manifest's SHA256 is
`f323937c6e7815f89a53d1d50da473d9fa0c7f8b4c58c60b2e68b6a816a1f94b`.
The existing expired-cleanup contract now checks the returned negative record and
absence of a post-deadline receipt instead of requiring an out-of-budget write.
That earlier target was not rerun in this selector.

The 1200-second generation budget and 20-second cleanup allowance are unchanged.
Timeout cleanup still ends at first start plus 1220 seconds; earlier terminal
outcomes retain at most 20 seconds. Finalization time is included, not excluded or
given a renewed grace period. The fixed 20-observation GPT-5.4/direct-v1/xhigh
configuration comparison still has five tasks, ABBA, two repeats, concurrency 1
and no external replay/resume/retry. Native counters remain observation-only when
available, with no native request/token or money hard-cap claim. The existing
runner callbacks, omitted-control paths and launch refusals were not changed.

### Source and review identities

The leader's finding is against PR750
`969aabfda810dfb0477c8ca55cbe2918f005666a`, tree
`3636cc62a40ed10128393e29e22e3fd02fdec190`. This correction uses the same
branch and worktree. Accepted main remains
`f609aff0deefd3c5afd7a6322ba6473c8b3e6c98`, tree
`3b318f9d70cbf2a080de28ff76fdfd5e278e1264`.

The independent runtime/frozen-judge binding is unchanged. Frozen F remains
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, with genuine whole TEMPLATE
closure `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The historical comparison profiles, compiler, grader, paid RESULT/PARENT/READER
bindings, input identities, frozen receipts and closed 30-cell/8-cell studies are unchanged.
The accepted architecture/source-provenance decisions were not reopened. This
repair advances only the genuinely changed prospective helper pin, not F or a
historical fingerprint.

### New targeted proof

The clean tested correction is `d6bff25dc037c96bccf418a0fe06b00402592bc7`,
tree `fd2c78441106f4f1aba1cf7a0067dc214fb2d447`. The invocation ran from
2026-10-05T10:58:22Z to 2026-10-05T10:58:29Z using Python 3.10.12, with a
300-second outer limit and 5-second termination grace. Those limits apply only to
this software proof, not the study or CI.

The 21 selected cases comprise four pending terminal-persistence cases, fourteen
finalization I/O-expiry cases and three ordinary-completion/reuse cases. They use
fake monotonic clocks, controlled I/O and synthetic fixtures. Expiry is exercised
both through the alarm and through late-return checks. Failure assertions cover
returned and durable non-reusable state, retained admission/lease uncertainty and
refusal of a new observation. Successful finalization, lost process confirmation
and inherited fork state are distinguished. Provider/auth/private-input guards
remain active. There was no provider run, live filesystem stall or long sleep.

This public command display redacts private executable, worktree and evidence
locators. Its text is not the exact private script identified by the hash below.
From the worktree's `batch-runner` directory:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 TMPDIR=<private-evidence-directory> \
  PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  DO_NOT_TRACK=1 GIT_NO_LAZY_FETCH=1 \
  timeout --kill-after=5s 300s <existing-py310> -m pytest \
  -vv -ra --tb=short --color=no -p no:cacheprovider -m 'not integration' \
  --basetemp <new-private-directory> tests/test_gpt54_time_budget_comparison.py \
  -k time_budget_observation_deadline_finalization
```

| New evidence | SHA256 | Bytes |
| --- | --- | --- |
| Exact private command | `99a7bfab57f45553aeb111ea85cb2441cefb24d085c7fe510f5a49e8adc845f9` | 807 |
| Combined stdout/stderr log | `1ad7ac04a51e9958ae13986704702f5808f0b8697304715212e3132d8db20a5a` | 3583 |
| Private receipt with all 21 passed node IDs | `06734fc949875629881844709de26e575416277c4e3cb5b4a2765ac0f435a6f4` | 4721 |

### Prior evidence stays separate

The [immutable prior record][prior-record] retains the original command/log/receipt
identities, exact passed/failed-node inventory, reviewed basis and prior scope.
Those local evidence files remain untouched.

| Earlier proof | Tested HEAD | Actual result |
| --- | --- | --- |
| Original combined selector | `1d5a9c2472e17fde1c0ad2dc1a0f3300772b5c95` | 5 failed, 46 passed, 75 deselected in 8.35s; exit 1 |
| Five-failed-target continuation | `73a86933934ac0a9cc260a963f042414b61bc151` | 5 passed in 7.55s; exit 0 |

These are not an aggregate 51-pass result or a whole-HEAD proof. The new selector
does not replace either earlier observation or turn the original failure into a
pass. Only `CHANGELOG.md` and this single current task record follow the new proof.

### Remaining limits and gates

The software supervision assumes an owned Linux/POSIX main-thread host and
signal-interruptible local I/O. SIGALRM does not establish a hard real-time bound
on uninterruptible kernel stalls or a descheduled host. These fake-I/O cases do
not measure that behavior, live enforcement, backend cancellation or billing.
Unconfirmed finalization provides no reusable-host authority.

Full corrected-HEAD source review, applicable CI and delivery acceptance remain
pending. Dispatcher/capture selection, verified credentialed inputs, F-derived
grading materialization and a separately reviewed source-bound live direction
remain unresolved. Every launch gate stays closed. No CI job was queried,
polled, dispatched or rerun; no Node/HF test, broad suite or earlier successful
selector was repeated. No private original, consumed artifact, real preparation,
provider/model/grader/HF/Azure call, Project edit or merge occurred.

The catalog was inspected once. The existing `experiment-design` guardrails kept
the study fixed during the prospective pin update; `im-not-ai-en` preserved the
facts, hashes and evidence limits in these English records. No unrelated skill or
new study-design investigation was used.

[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/969aabfda810dfb0477c8ca55cbe2918f005666a/tasks/LATEST_TASK_RESULT/README.md
