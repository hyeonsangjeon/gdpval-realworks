# Registered time-budget ABBA schedule and source successor

Local implementation on `leader/time-budget-2404-guard-20261030`, directly
above `64f2720605b6e494d324ff682046234fe8beebc5`. This is the **GPT-5.4/xhigh**
configuration-bundle study, not the separate GPT-5.6 native pilot. No model,
judge, workflow, private Task4 readout or publication is authorized by this
change. All validation described here is offline and synthetic.

## Exactly twenty observations

The original registration's `runs` order is expanded **run first, task second**.
ABBA means four blocks, each containing the same five tasks; it does not mean
two additional ABBA blocks or forty observations.

| Sequence | ABBA position | Harness | Repeat | Task order |
| --- | --- | --- | --- | --- |
| 1–5 | 1 (A) | Sandbox V2 | 1 | T1, T2, T3, T4, T5 |
| 6–10 | 2 (B) | Codex | 1 | T1, T2, T3, T4, T5 |
| 11–15 | 3 (B) | Codex | 2 | T1, T2, T3, T4, T5 |
| 16–20 | 4 (A) | Sandbox V2 | 2 | T1, T2, T3, T4, T5 |

T1 `02aa1805-c658-4069-8a6a-02dec146063a`; T2 `0112fc9b-c3b2-4084-8993-5a4abb1f54f1`;
T3 `2ea2e5b5-257f-42e6-a7dc-93763f28b19d`; T4 `3baa0009-5a60-4ae8-ae99-4955cb328ff3`;
T5 `0818571f-5ff7-4d39-9d2c-ced5ae44299e`.

`gpt54_time_budget_schedule.py` emits deterministic model-free job descriptors.
Each has one cell, a unique SHA256 observation ID, one-based sequence and ABBA
position, schedule SHA256, the one-job workflow, and the preceding capture ID.
The ID binds study, task, run/harness, repeat and ABBA position, but deliberately
does not include the runtime source or runner image: changing either cannot
mint a second observation for a consumed cell. The existing digest-bound
request's cell and immutable registration determine that ID; a caller-supplied
ID is never independent authority.

Both workflows still have exactly one `observation` job, a 45-minute job limit,
and the **same** concurrency group with `cancel-in-progress: false`. Both early
shell guards and Python controllers accept integer repeats 1–2 only. V2's
underlying observation callable also accepts the registered second run.
Actions queue ordering is not assumed: a queued wrong cell is refused by the
durable order check. There is no automatic dispatch/credential acquisition in
the scheduler. Independently approved, digest-bound requests remain required.

## Durable serial admission and capture

Before an admission CAS, each controller inspects only the twenty registered
cell namespaces at the independently specified private parent commit. It
requires the occupied namespaces to be exactly the earlier schedule prefix.
Each earlier namespace must contain a verified `schedule-capture.json` binding
the same source, original registration, cell/ID and schedule, plus immutable
admission/output-manifest objects. Current/future occupied namespaces, holes,
missing metadata, changed bindings or uncertain completion stop admission.

The existing add-only CAS atomically writes `admission.json` together with
`schedule-admission.json`. The existing immutable object/byte readbacks must
acknowledge the commit before execution. A competing job with the same parent
loses CAS and cannot reach model execution. Host restart, lost response and
partially written local state do not allow re-claim, retry or state adoption.
NAS/local execution stays denied by the separate Ubuntu 24.04 host guards.

Retention atomically writes `output-manifest.json` and `schedule-capture.json`.
Only a real returned terminal capture with confirmed cleanup/reusability can
advance the schedule. An admitted failure/timeout with confirmed cleanup is
retained and advances too; scores never change the schedule or denominator.
Uncertainty is preserved as `uncertain_stop` and blocks later observations.
The existing result/completion schemas and unavailable-usage rules are not
changed; schedule metadata is separate and contains no prompt, response or
credential. Local `schedule-refusal.json` records only the fixed refusal code
and observation ID.

Old per-cell claims/output manifests are never overwritten, adopted as new
results, or automatically relabelled with schedule/image evidence. A prior
capture without the new order evidence stops with `previous_capture_unverified`.
No actual private history was read here. Reconciling any historical partial or
out-of-order study state requires separately reviewed evidence/direction; it
cannot be fixed by replaying a consumed observation.

## Source-only successor, original contract unchanged

`experiments/execution_envelope/gpt54_time_budget_source_20261030_schedule.yaml`
links the unchanged original registration SHA256
`e1d16d350aeb21af34104cede0d3acc0f6dc8db134338708e70168fbd9642699` and the hash of
its 42-pin inventory. It lists **exactly five** previous→current byte hashes:

| Registered file | Why the successor names it |
| --- | --- |
| `core/codex_runner.py` | Reviewed 24.04 admission/runner evidence affects this observation path. New hash `b5f29c5aef7fc594ed3f042085a078e9e13c3f3754f5840c1df19bae75235c34`. |
| `.github/workflows/batch-run.yml` | Previously reviewed drift; not the dedicated observation workflow. Still hash-checked. |
| `step2_run_inference.py` | Previously reviewed generic projection drift; dedicated capture does not invoke this entrypoint. Still hash-checked. |
| `step8_grade.py` | Previously reviewed runtime drift; this study still materializes/executes the frozen F grader, not current Step8. Still hash-checked. |
| `gpt54_time_budget_comparison.py` | Adds successor validation, with no study-policy/score change. |

The detailed four-file review and evidence lines remain in
`time_budget_ubuntu24_guard_20261030.md`. The successor also pins the scheduler,
both controllers/workflows, V2 callable, runner classifier and sandbox preparer.
All 42 effective source pins, the exact helper set, unchanged original bytes,
old hashes, exact delta list and independently reviewed full runtime Git
commit/tree are checked. Neither omitting a changed file nor changing a hash
alone waives a guard. The old no-successor validation path remains strict.

Model GPT-5.4/xhigh, prompt/input hashes, the fixed five tasks, one external
attempt, 1,200-second generation + separate 20-second cleanup, no external
retry/resume/replay, native-usage availability rules and pairing `(task, repeat)`
are unchanged. Cost remains the registered findings-only/null approval policy;
the other pilot's USD 200 rule is not imported into this study. Grading remains
Sol/Max, prompt v2.2, frozen F source `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`,
whole-template SHA256 `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.

## Offline evidence and next integration

Tests cover all twenty IDs/selections, repeat-2 callable roundtrips, serial
claim→capture transitions through both real CAS implementations, duplicate,
out-of-order, >20, uncertainty, lost/racing claims, source/manifest mutation,
old-registration preservation and anchored successor compilation. Synthetic
predecessor metadata is declared explicitly in fixtures; no successful guard
is monkeypatched and no private historic Task4 output is used.

Recommendation 3 still needs a model-free end-to-end chain from these captures
through frozen-F grading preparation/stub execution to `(task, repeat)` paired
aggregation, retaining failed/missing outcomes and image/source identities.
The historical grading/readout controllers' fixed-cell assumptions must be
checked before wiring all twenty cells; this change does not silently expand
their authority. Real Ubuntu 24.04 sandbox/kernel proof, publication and live
dispatch approval remain separate. These tests do not prove hosted readiness,
native billing cancellation or score reproducibility.

Final local verification: **944 distinct offline tests passed, 0 failed,
0 errors, 0 skipped**, counting each case's latest completed result, not
summing overlapping runs. Reports and the counting manifest are under
`/ai-work/copilot/_tmp/time-budget-schedule-20261030.9t6sbe/`.
The disjoint core sets passed 340 + 101 + 65 cases. The 438-case related suite
initially had eight failures and two setup errors; the entire affected
14-case grading-CI and 65-case readout modules then passed. Corrections were
explicit synthetic registration/predecessor facts and the shared fixture's
generation-versus-grading namespace distinction. Parallel NAS worktree setup
timeouts were rechecked in isolated temporary storage with the CI's
`tmp_path_retention_policy=failed`; no timeout or production assertion was
relaxed. The unsupported real-kernel positive was not selected on NAS; its
separate static workflow contract passed. Existing JUnit property-format
warnings are not test failures or evidence of hosted readiness.
