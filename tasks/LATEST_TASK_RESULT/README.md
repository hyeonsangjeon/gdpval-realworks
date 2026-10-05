# Latest task result

## Project5 observation deadline and frozen-judge source binding — 2026-10-05

The prospective time-budget study now has an optional observation control in the
existing V2 and native Codex runners, plus independently anchored runtime and
frozen-judge source validation. No dispatcher or capture path selects this control
yet. Every existing launch refusal and execution-enable flag remains closed.
Delivery is **HOLD** for final-source review and applicable CI acceptance.

Two separately pinned invocations provide the offline evidence. The first
reported **5 failed, 46 passed, 75 deselected in 8.35s**, exit 1. After a narrow
repair, exactly its five failed node IDs passed in **7.55s**, exit 0. The original
failure is preserved; this is not a single 51-pass run or a full fixed-HEAD proof.
No passed node was rerun.

### Scope and implementation

The separate `gpt54_sandboxv2_codex_time_budget_v1` registration keeps GPT-5.4,
direct-v1/xhigh, five tasks, SandboxV2 versus native Codex, two ABBA repeats,
at most 20 observations and inference concurrency 1. There is no external
replay, resume or retry. V2's 9-turn/8192-output settings remain V2-specific.
Native request/retry/token counts are observation-only when available, otherwise
unavailable; no shared native request/token or money hard cap is claimed.
The original comparison and closed 30-cell/8-cell studies remain separate.

`TimeBudgetObservation` in `core/time_budget_observation_deadline.py` persists
exclusive admission before preparation. Its identity binds study, run, condition,
repeat, task, reviewed source SHA/tree and registration/input digests. The durable
key excludes those digests so changing them cannot mint another attempt at the
same observation. Existing admissions are not adopted, even by a new runner.

V2's `build_runner_factory`, `conversation_seam`, `run_model_conversation` and
`AgenticV2ScriptedRunner` share one control. The monotonic clock starts immediately
before the first `voice.next_turn`, after reservation. Codex starts supervision
before `thread.turn`, covering turn creation, `_await_turn` and native recovery.
Preparation does not start or spend the generation clock. Turns, waits and tool
work consume the same nonrenewable 1200 seconds.

The timeout is latched before interruption; a late answer cannot replace it.
Interruption, process waits, close, orphan checks, collection and removal spend
one cleanup remainder: first start plus 1220 seconds after timeout, or at most
20 seconds after an earlier terminal result. Substage limits only shorten that
remainder. No environment setting enlarges it. Unconfirmed cleanup is a
non-success and retains the host lease. Records distinguish the first start,
elapsed time, terminal reason, interruption attempt/acknowledgement and cleanup
completion/expiry without credentials or original bodies.

Supervision requires an owned Linux/POSIX main-thread host, `/proc` visibility and
no pre-existing real-time alarm. It interrupts blocking local generation I/O and
bounds owned-process teardown; it does not leave a daemon generation watchdog or
use an unbounded final join. Omitted-control behavior and the closed 10800-second
`CodexTaskDeadlineStore` contract remain unchanged. Local interruption and cleanup
evidence do not prove backend cancellation, live enforcement or a billing bound.

### Independent runtime and judge identities

The prospective `compile_registration` API takes `runtime_root`,
`expected_reviewed_source_sha`, `frozen_grader_root` and
`expected_grader_source_sha`. All four must be supplied together. There is no
HEAD, marker or environment fallback. Both roots use registered detached linked
worktrees, independently checked commit/tree identities, regular tracked blobs,
held directories and final byte/HEAD rereads.

Runtime R supplies current runtime facts and 41 prospective source bindings.
Frozen judge F is commit `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`. F supplies the unchanged 37-pin
local-source profile and genuine whole grader TEMPLATE closure
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The unchanged `compute_grader_source_hash` receives `config_path=F/GRADER` and
`batch_root=F/batch-runner`. R's changed core does not have F's template identity.

Compiled evidence names both roots and separates the template from a materialized
grader. Materialized config path/fingerprint fields remain null. A synthetic test
proves that actual materialized config bytes/path have a distinct fingerprint.
Future grading must execute from F-derived source, not hash F while executing R.
No production ROOT mutation, fabricated legacy grading plan, reduced hash scope
or historical fingerprint replacement is introduced. The omitted compiler and
historical runtime/workflow paths retain their refusals.

Only the six directly changed prospective runtime/compiler bindings advance.
The final time-budget manifest SHA256 is
`5520212d2c704ee0e4c9397619298f793586e03e099c8aea287e3467bb8c9e36`.
The original comparison manifest remains
`3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1`;
the local-source profile remains
`81b9930102a19f298dfbb5e45c8f0d39045b89512aa5dc9b4d5543312835cbbe`.
The legacy compiler, core deadline store, Step2, grader, capture guards and workflow
files are unchanged. Paid RESULT/PARENT/READER bindings, frozen registrations,
input identities and historical evidence are untouched.

### Reviewed basis and source-role audit

This fresh worktree started at accepted main
`f609aff0deefd3c5afd7a6322ba6473c8b3e6c98`, tree
`3b318f9d70cbf2a080de28ff76fdfd5e278e1264`. The leader supplied PR749's
reviewed `d901b119443a843784d81717943622f577fb43b4`, owner
[review 5411970743][prior-review], all 11 applicable checks successful and
PR-only deploy skipped. These are prior-source facts, not approval or CI for
this new change. Previous worktrees and the consumed 14d artifact were untouched.

Before coupled edits, the established same-session architecture and grading/source
charters and the consolidated grading specification were applied. The accepted
clock-placement and two-root decisions were implemented without another capability
or study-design investigation. The review required the whole F closure, distinct
materialized identity, genuine current-source refusals and unchanged launch gates.
It was not an independent external review or approval of this new runtime source.

The current-versus-frozen consumer audit kept historical hashes intact. Shared
legacy fixtures now explicitly demonstrate current R's refusal before compiling
their genuine frozen F bytes. Retained synthetic source trees copy F's complete
core closure. CURRENT observer/report expectations remain separately named; no
production CURRENT dependency repin was needed. The known default-comparison
refusal lists include the newly changed V2 conversation runner in manifest order.
Existing sentinels and source validators remain active.

### Exact offline evidence

Both invocations used Python 3.10.12, an empty token-free/offline environment,
synthetic inputs, fake monotonic clocks, controlled interruptible transports and
real temporary Git objects. Each had a 300-second outer limit and 5-second
termination grace. These are software-test limits, not experiment budgets or CI
timeout changes. No real input, prepared artifact, receipt, provider, model or
grader was accessed or executed.

| Invocation | Tested HEAD | Tested tree | Actual result |
| --- | --- | --- | --- |
| Combined selector | `1d5a9c2472e17fde1c0ad2dc1a0f3300772b5c95` | `20c0d2d4ddd60d2f67c88dee7105d22bd522345f` | 5 failed, 46 passed, 75 deselected in 8.35s; exit 1 |
| Failed-target continuation | `73a86933934ac0a9cc260a963f042414b61bc151` | `cae6626dfba04eb6d2caad83fe725e72dcb1243e` | 5 passed in 7.55s; exit 0 |

The first failure exposed three V2 timeout results mapped to `runner_internal_error`
instead of the existing control-stage `task_wall_time_exhausted`, a source fixture
that was not a registered linked worktree, and a shared-fixture import after the
process sentinel had replaced `Popen`. The correction changes only the timeout
result branch, its prospective pin and those directly coupled tests.

The first source-negative cases passed at an early layout refusal; they are not
claimed as deeper blob-check evidence. The repaired positive binding target first
establishes valid anchored roots, then completes the previously unreached checks
for swapped/coherently substituted roots/commits/digests, modified or untracked
source, symlink/hardlink substitutions and final byte/parent/HEAD races. It keeps
template and materialized fingerprints distinct and checks the unchanged launch
refusal. Neither the anchor nor a validation verdict is mocked away.

Public command displays below redact private executable, worktree and evidence
locators. The SHA256 values identify the exact private command scripts, not these
redacted displays. From the source worktree's `batch-runner` directory, each script
uses this environment and bound:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 TMPDIR=<private-evidence-directory> \
  PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  DO_NOT_TRACK=1 GIT_NO_LAZY_FETCH=1 \
  timeout --kill-after=5s 300s <existing-py310> -m pytest \
  -vv -ra --tb=short --color=no -p no:cacheprovider -m 'not integration' \
  --basetemp <new-private-directory> <selection-below>
```

The first selection was:

```text
tests/test_gpt54_time_budget_comparison.py
-k 'time_budget_observation_deadline or time_budget_frozen_judge_binding or time_budget_legacy_role_compatibility'
```

The continuation selected exactly these five node IDs, without `-x`:

```text
tests/test_gpt54_time_budget_comparison.py::test_time_budget_observation_deadline_v2_actual_factory[late_success]
tests/test_gpt54_time_budget_comparison.py::test_time_budget_observation_deadline_v2_actual_factory[tool_wait]
tests/test_gpt54_time_budget_comparison.py::test_time_budget_observation_deadline_v2_actual_factory[blocking_responses]
tests/test_gpt54_time_budget_comparison.py::test_time_budget_frozen_judge_binding_genuine_dual_roots
tests/test_gpt54_time_budget_comparison.py::test_time_budget_legacy_role_compatibility_shared_retained_source
```

The explicit log node IDs show that the continuation equals the first failed set
and is disjoint from its 46 passed nodes. Together the records account for all
51 originally selected IDs, but they do not constitute a fabricated combined
pytest summary or evidence that every node ran at the corrected HEAD.

| Evidence | First invocation SHA256 | Continuation SHA256 |
| --- | --- | --- |
| Exact private command | `e13e9b5563233fee086e74d6d749dc5216b111791847142e1d76edd31a810a7d` | `66c00e910a970fb33ee4803fb4a5c3c679f37fb55048d248b1de4ec0ffe1f5e1` |
| Combined stdout/stderr log | `7fb1fd2e018df4356a9a79e1e0b0e5daa9718665d28588f1914c21bd10601f9f` | `d97043efafc16676c0cef92dbf043843d81ac7ecf23526eabef2728739c151a2` |
| Private receipt | `a68a2c3f4d5c68b3d150ab76abc15884a3003837d34457b14339394f5c114c29` | `6554f195f1d30738e5b6db423f5fd48de9b43c8b06100f2844ab312da57379cd` |

Command/log/receipt sizes are 883/13475/1497 bytes for the first invocation and
1312/1056/1945 bytes for the continuation. All original evidence files are retained.
Only CHANGELOG and this single current LATEST record change after the continuation.
Usage documentation was included before proof.

### Remaining work

The next execution integration unit is a reviewed dispatcher/capture path that
selects this persisted control, supplies independently reviewed R/F roots and
binds verified inputs. Credentialed-input/CI authority, served-model identity,
F-derived grading materialization and a separate source-bound live direction
remain unresolved. Existing launch gates must remain closed until their own
requirements are met. No delegated spending decision is being reopened.

Final-HEAD review, applicable CI and delivery acceptance are pending. No CI job
was queried, polled, dispatched or retried. No successful prior registration/HF
selector or broad suite was repeated. The [immutable PR749 record][prior-record]
retains its original 75-case proof, separate CI corrections and historical detail.

The catalog was inspected once. `experiment-design` preserved the fixed study
controls during prospective binding changes; `im-not-ai-en` was applied to the
bounded English documentation and records. Unrelated UI/animation, experiment
reporting and renewed native-SDK capability work were not used.

[prior-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/749#pullrequestreview-5411970743
[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/d901b119443a843784d81717943622f577fb43b4/tasks/LATEST_TASK_RESULT/README.md
