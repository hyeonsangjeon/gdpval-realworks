# Serial time-budget controller: model-free integration

This change connects the registered twenty observation IDs to a durable serial
dispatch/capture/F-input/stub-grade pipeline. It does **not** publish code,
dispatch a workflow, authorize a paid run, read private Task4 results, or relax
the existing live grader's cell-specific admission. The complete twenty-cell
test is synthetic, not performance or billing evidence.

## Entry points and ports

`batch-runner/gpt54_time_budget_serial_controller.py` provides
`SerialController(...).run(max_steps=200)`. Each `advance()` does bounded I/O;
`waiting` returns to the caller without sleeping or spawning a polling daemon.
The caller can persist its ledger and call `run()` again. CLI commands are
intentionally **read-only**, with no default gh executor, login or model client:

```bash
python batch-runner/gpt54_time_budget_serial_controller.py plan
python batch-runner/gpt54_time_budget_serial_controller.py status --ledger /absolute/owned/ledger
```

The programmatic integration used in offline tests is:

```python
controller = SerialController(
    plan=plan, source={"sha": reviewed_sha, "tree": reviewed_tree},
    directory=ledger_directory,
    gh=GhCommands(fake_gh_execute, synthetic=True),
    requests=approved_request_source,
    store=fake_store_at_exact_output_commit,
    pipeline=FixtureFrozenPipeline(stub_grader),
)
status = controller.run()
report = controller.readout()
```

All four ports are explicit. `GhCommands` emits the real `gh workflow run`,
`run list`, `run view` and `run download` argument shapes, but has **no subprocess
default**. The executor receives a JSON dispatch body on stdin, not an argv
containing request contents. Tests do not execute gh. `DirectoryRequests` reads
just-in-time `NN.json` requests with independent `NN.sha256` approvals; it never
invents a new admission window, run number, source review or private CAS parent.
Request-source fixtures generate only synthetic metadata. They are not proof
that the actual Actions canonical paths/original inputs/admission will pass.

## Ordering, identity and recovery

The unchanged scheduler supplies five V2-r1, five Codex-r1, five Codex-r2,
then five V2-r2 observations. It is ABBA by five-task blocks, not four runs of
each task interleaved. The controller and existing shared Actions concurrency
group both prohibit overlapping observations. A nonblocking file lock prevents
two local controllers from using the same ledger simultaneously.

`pending → dispatch_intent → observing → captured → prepare_intent → prepared → grade_intent → complete`

Every side-effecting intent is fsynced **before** its operation. The ledger binds
source SHA/tree, registration, schedule, image and all twenty IDs. Resume checks
the header and order, skips completed observations, and rechecks durable capture,
preparation and grade bytes before another dispatch. A different source cannot
create a fresh attempt for an occupied observation.

| Interruption/failure | Required behavior |
| --- | --- |
| Lost dispatch response / process interruption | Discover the one expected workflow run number at the exact source; never dispatch again |
| Zero runs after 120s, duplicate runs, wrong attempt/SHA | Mark `missing`, retain uncertainty and stop; never choose the newest candidate |
| Known run still active after 7,200s of confirmation waiting | Record `missing/null`, keep the run ID and stop; do not cancel, retry or start the next observation |
| Failed/timed-out Actions job or absent artifact | Stop with `missing/null`; no zero score, replay or reset |
| Partial download interrupted before admission | A resumed read may download again into a fresh directory, never overwrite prior files or replay dispatch |
| Lost F-preparation or grade acknowledgement | Stop; no adoption of unacknowledged files, duplicate input preparation or second judge attempt |
| Cleanly captured generation timeout | Keep the failed generation and its one input/grade record; its comparison score stays null. Advance only with verified cleanup and retained schedule state |

The 120s/7,200s values bound **controller confirmation**, not model execution.
They do not change the registered 1,200s/20s generation/cleanup deadlines, cancel
a remote request or establish a billing cap. The controller cannot reset a
stopped ledger. Unknown external state needs review, not an automatic retry.

## Capture and common grading boundary

The existing workflow artifacts contain only `completion.json`, not raw answers.
The store port must hydrate the independently authorized private output commit
named by completion. `gpt54_time_budget_serial_capture.py` binds the repository,
revision, admission, output manifest and `schedule-capture.json`; checks the
schedule ID, source, request digest, run/attempt, host/image and raw result hash;
then reuses the real canonical-payload, fingerprint and deliverable validators.
Runner images must be Ubuntu 24.04 and identical across the readout; 22.04 or a
different image version is not silently pooled. No source/artifact lookup picks
“latest.” No private storage credential or downloader is implemented by this
model-free change.

`FrozenInputQueue.prepare()` can materialize all twenty inputs through the
existing `prepare_observation_grading()` API. The fixture pipeline uses the
unchanged F byte checks, grade schema/judge/rubric/denominator checks and existing
paired readout, yielding ten `(task, repeat)` pairs. Missing/failed/partial
results remain null, including a failed generation with an otherwise valid
stub grade. Prepared inputs are not launch authority.

## What remains before a real twenty-observation run

The original live executor still admits only V2-r1 Task1 or Codex-r1 Task3
(`gpt54_time_budget_grading_execution.py`, `_checked_preparation`, lines 340/345).
The existing paired readout explicitly requires fixture evidence. Neither guard
was changed or relabeled. Consequently the supplied live pipeline refuses
**before any gh command** (`common_live_grading_admission_not_implemented`).
This is a remaining integration boundary, not a claim that the paid path is ready.

A future reviewed launcher needs publication/paid approval, a live common-grading
admission/executor and non-fixture readout, plus independently approved JIT
requests and a credential-scoped private-store adapter (including separate Task4
read authority). It also needs the actual Ubuntu 24.04 resource probe and CI.
Those are not silently replaced by the synthetic twenty-cell test.

Only new controller/intake/test/document files are added. The original 42 pins,
comparison registration, source successor, model/effort/input/grading contracts,
generation/cleanup budgets, existing workflows and all hash expectations stay
byte-identical. No hash update or source-guard exception is introduced.
