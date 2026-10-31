# Serial time-budget controller: model-free integration

The registered twenty observation IDs connect to durable serial dispatch,
capture, frozen-F input admission, the actual F Step8 entrypoint, and ten paired
readouts. The fixture API remains separate. This does **not** publish code,
dispatch a workflow, authorize a paid run or read private Task4 results.
Offline tests are unit fixtures, not performance, hosted execution or billing
evidence; the existing V2-first/native-Task3 APIs keep their original scopes.

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

## Scheduled common grading admission

Use the programmatic adapter after independent execution approval:

```python
pipeline = CommonFrozenPipeline(
    controller_root=reviewed_controller, controller_source_sha=controller_sha,
    controller_source_tree=controller_tree, execution_root=grade_root,
    attempt_store=private_once_store, directions=read_independent_direction,
)
```

`gpt54_time_budget_common_grading.py` revalidates the serial completion, exact
retained revision, claim, manifest, schedule ID, runner image and original
payload/deliverable bytes. Its opaque preparation handle lives only inside the
checked intake scope. The existing executor reconstructs every materialized F
file, rubric snapshot, original input, config and helper-source identity. The
unmodified F Step8 and F core run from that materialization, not current R.
Controller helpers are bound to an independently reviewed controller commit and
tree; none of the original 42 or successor 8 pin expectations are advanced.

For both conditions a separate grading-only copy gains the authenticated
retained repository/revision and capture-document digest. Its fingerprint is
recomputed; original capture and prepared F bytes are never rewritten. These
annotations do not replace task bodies, file inventories, rubric, prompt or
judge settings. Serialized markers alone cannot recreate a closed intake.

Before a model effect, the adapter requires GitHub-hosted Ubuntu 24.04 and
Docker inspection of the current job container and image. Its immutable image
is the same `ghcr.io/hyeonsangjeon/gdpval-grading@sha256:0f6782c056e31e1ea1d693fc2f8f873da160b232926fa1b6cde75c24e5344a04`
used by the existing grade-run and native-Task3 workflows; the registration's
grading contract refers to F, not a new image. Image ID/digest, renderer and
runner/run metadata are bound into the independent direction and reread before
claim/launch. Local/NAS execution, missing inspection or drift fails closed.
These observations are operational evidence, not cryptographic attestation.

Each direction binds the exact command, task, input hashes, F sources, image,
execution context, paths and one local attempt-store inode. The supplier reads
an independently issued `NN.direction.json` and `NN.direction.sha256`; it never
calculates permission from the JSON. A durable, nonrenewable claim precedes the
owned child. The existing 14,400s Step8 / 14,520s child grading envelope is kept;
it is separate from unchanged 1,200s generation / 20s cleanup. There is no
automatic retry, regrade or adoption after a lost grade acknowledgement.

`aggregate_observation_pairs()` checks execution/direction/claim identities,
the actual grade schema, task, rubric, judge identity, renderer and retained
sidecars. It calls the same ten-pair arithmetic as the fixture reader, but
rejects synthetic/stub markers in captures, preparations or grades. A failed
generation, timeout, cancellation, missing grade, partial grade, judge error or
reduced denominator stays missing/null. Cancellation or unconfirmed grader cleanup also stops
the serial controller before its next dispatch; a known clean failed grade
can be retained as null without a second attempt.

## What remains before a real twenty-observation run

A reviewed launcher still needs publication/paid approval, independently approved JIT
requests and a credential-scoped private-store adapter (including separate Task4
read authority). It also needs the actual Ubuntu 24.04 resource probe and CI.
In particular, Docker socket access, image inspection and owned-child
cleanup in the pinned grading job container must be verified on Actions; the
adapter refuses if unavailable. No claim is made that twenty serial operations
fit one six-hour job or that a local ledger is a distributed once-only store.
The caller must retain/handoff its evidence and once-store across job lifetimes.
None of these hosted facts is replaced by a synthetic twenty-cell test.

The original 42 pins,
comparison registration, source successor, model/effort/input/grading contracts,
generation/cleanup budgets, existing workflows and all hash expectations stay
byte-identical. No hash update or source-guard exception is introduced.
