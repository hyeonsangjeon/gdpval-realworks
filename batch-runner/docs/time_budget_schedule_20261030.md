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

Both workflows still have exactly one `observation` job, now a 55-minute V2 /
65-minute Codex outer job limit, and the **same** concurrency group with
`cancel-in-progress: false`. Both early
shell guards and Python controllers accept integer repeats 1–2 only. V2's
underlying observation callable also accepts the registered second run.
Actions queue ordering is not assumed: a queued wrong cell is refused by the
durable order check. There is no automatic dispatch/credential acquisition in
the scheduler. Independently approved, digest-bound requests remain required.

## Outer-job timeout repair (2026-10-30)

The immutable time-budget registration, not a workflow literal, owns generation
`seconds_per_observation: 1200`, cleanup `local_cleanup_grace_seconds: 20` and
`max_planned_host_lifecycle_seconds: 1220`. The earlier
`gpt54_sandboxv2_codex_comparison.yaml` is also unchanged; it is not the separate
time-budget policy. Neither model time, grading time, attempts, admission-window
duration nor the study's settings change in this repair.

The previous `jobs.observation.timeout-minutes: 45` cannot cover Codex's declared
step timeouts plus the registered lifecycle. V2 also lacks the selected minimum
operating reserve. Count every timed non-generation step, including retention
and completion checks, even when conditional; count the model lifecycle from the
registration exactly once. Reserve another **10 minutes** for the closed set of
untimed checkout/bootstrap/Python setup/login/artifact operations. Round the
result up to five-minute job increments, below the hosted six-hour maximum:

| Job | Declared steps + registered lifecycle | Minimum with reserve | Old -> new job limit / actual headroom |
| --- | --- | --- | --- |
| V2 | 23m + 1220s = 43m20s | 53m20s | 45m -> 55m / 11m40s |
| Codex | 30m + 1220s = 50m20s | 60m20s | 45m -> 65m / 14m40s |

The reserve is an **operational allowance, not a proven maximum for each
untimed action**, and does not guarantee runner/network speed or retention
under platform termination. Actual hosted resource/cleanup proof remains open.
This raises only the workflow job envelope; it does not extend the registered
generation deadline, relax a refusal or authorize another observation.

`tests/test_time_budget_workflow_timeouts.py` calculates that inequality from
the actual YAML and original registration. It also rejects missing/dynamic/
invalid timeouts, an over-six-hour job, missing/duplicate execution, an added
unaccounted untimed step, growth in timed steps which exhausts the reserve,
rounding 60m20s down to 60m, and a workflow-owned generation step deadline.
The original two registration files are held to their full SHA256 values.

The source-only successor advances exactly its two workflow helper hashes:

- Codex `929c303cac32da46a9981ce592a61ced8bc35e66fea1110be42d4ef4898bf5fe`
  -> `16202467dc87439223207e6bed9342349bc8377cfed3a2e4d5b7e548b9544270`.
- V2 `009c19187486d985fbd56783ffa3515363a1385471ba8c16b9a49517895e96b8`
  -> `59905fe19088209f3e983a16fa5a35f94c15f76edde44a356dab5170673e5432`.

The reason is the reviewed job timeout/comment change above. Old hashes remain
in the successor comments and this record. The original 42 pins, all other
helper pins, source-delta inventory, exact-byte validation and independently
reviewed runtime-commit guard remain intact. CI test jobs keep their existing
45-minute limits; only the two observation jobs change.

Consequently the successor file's whole SHA256 changes from
`e151003ef1812d66c96d1e32038d9023ce3e957ef92c2b371f9773f8867d68e4` to
`1e316eecccad614eba24034849a3bebf7bff549a59d7f6e127ac597192334dae`.
The paired-readout test retains its exact-hash assertion with that new expected
value; its original-registration, fixed grading scope and CI selection
assertions are not relaxed.

Final timeout-repair regression: **235 passed / 0 failed / 0 skipped** in
393.14s, including the previous 187-case core set, 39 new static timeout cases,
and nine existing workflow/controller cases. The pre-fix arithmetic reproduced
two failures. The first full run caught one stale successor-hash expectation;
the corrected entire selection passed, not just that one test. No actual hosted
startup, model/judge call, private result read, push or dispatch was performed.

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
The subsequent local implementation is described in
[`time_budget_paired_readout_20261030.md`](time_budget_paired_readout_20261030.md);
the paragraph here records what remained at this schedule commit.
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
