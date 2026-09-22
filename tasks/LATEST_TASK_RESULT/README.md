# Latest task result

## Owned-child cleanup for the Codex pilot dispatcher

The four affected lifecycle cases passed at implementation commit
`d9bed6851a611787fa14f3e67c156d6369b11875`:
`4 passed in 127.23s (0:02:07)`, exit 0. The initial selection's six passing
capability/owner-state cases retain their separate source scope below. There
was no fresh ten-pass run or full dispatcher-suite rerun. This is offline
process-lifecycle evidence, not a paid-pilot or model-recovery result.

REQUEST-CHANGES review `5282428403` at
`47e725bc3ff1945f12cc6756c0d610646dc7feb3` identified the gap. The former
`subprocess.run(timeout=remaining+60)` could kill and reap Step 2 while leaving
Codex/app-server/tool descendants alive. The dispatcher then marked the cell
stopped and advanced. An inherited lock protects a surviving direct child
after dispatcher death; it did not establish descendant cleanup after that
child was killed. Step 2's own `finally` cleanup cannot be relied on after
SIGKILL.

### Correction and preserved controls

Each real Step 1/Step 2 child now has a private supervisor session. The
supervisor enables Linux child-subreaper behavior for itself only, so orphaned
descendants remain its children even if they create another session. It
reuses the repository's descendant discovery and TERM-then-KILL convention.
Before sending a signal, `waitpid` must establish that the target is its own
unreaped direct child. That child cannot be recycled before signaling because
the supervisor does not reap it in between. Deeper descendants are adopted
as their parents exit and handled in subsequent cleanup passes. No process
name, shared process or unrelated dispatcher child is a kill target.

Cleanup waits are bounded. Completion requires the supervisor to observe no
remaining children after reaping, report that fact through its private
control channel, and itself be reaped by the dispatcher. The same cleanup
applies when the payload exits while leaving descendants behind. This does
not depend on Step 2 or a tool running cleanup after SIGKILL. Linux
subreaper/process visibility remains a host requirement; it is not waived.

The host-owned `owned-child.json` checkpoint reserves the serial slot before
launch. The supervisor and payload inherit the serial lock. Missing or
incompatible ownership state refuses. Unconfirmed cleanup keeps a durable
unresolved record and leaves the cell running with an explicit reason and
missing accounting. Every restore checks that global record before skipping
finished cells or starting any child. Even if the OS lock is later released,
restore does not infer cleanup from a missing process or silently adopt the
cell. Resolving an unacknowledged cleanup requires separate investigation;
there is no automatic clearance flag in this change.

Confirmed timeout retains a stopped cell with an unknown cell exit and partial
accounting. Confirmed host interruption retains the running cell for explicit
restore. Partial files are not overwritten or deleted by cleanup. The original
deadline and durable attempt count remain authoritative; restore does not
initialize a new clock. A successful child exit without a result remains a
failure, and failed/filtered/expired cells stay in the denominator.

The dispatcher still defaults to plan-only. The existing `advance_check_5`
cohort has exactly 30 cells, A1/B1/C1/C2/B2/A2 per task, with one active cell
tree. The GPT-5.4 Foundry/xhigh profile, original task/reference bytes, base
requests, provider, context, tools and fixed grader remain unchanged. A keeps
four fresh attempts; B/C share retained-state capability and fixed backoff.
C's only intervention remains the reviewed host error feedback. The
180-minute cumulative and 30-minute attempt limits are unchanged. There is
no new wait optimizer, monetary cutoff, model setting or grading dispatch.
Self-QA and legacy resume rounds stay disabled; there is no low-score retry.
The registered grader remains `default_v2_sol_max.yaml`, GPT-5.6-sol/max,
prompt v2.2 and one grade per task, with launch separately directed.
A versus B still changes both retention and attempt policy; it is not a
retention-only causal comparison. B versus C isolates the feedback intervention.

### Integrated source and remaining execution guards

The single authorized fetch returned exact main
`9b572a39af8ecd48850e427d1bccf8cb65b7c65a`. An ordinary non-destructive merge
preserved the dispatcher and #652 histories; conflicts were confined to the
two completion records. Imported core, feedback tests and active binding
bytes match that main exactly. The local correction changes only
`batch-runner/codex_budget_pilot.py`, its existing test module and the two
records. The dispatcher is outside the full grader closure, so no additional
active digest refresh or source-count change was needed. The genuine compiler
and exact 37/58 source sets remain in force; historical identities and results
were not rewritten.

The real integrated source reports
`c_host_feedback_present=true` and no missing-C capability requirement. The
negative capability gate remains tested. The focused cases also retain the
explicit-input refusal, real pinned-runtime/connection check and real
development-host refusal. The runtime/host cases use genuine validators after
synthetic Git metadata; the missing-input case uses the existing fake execution
boundary. No production pin or guard is changed.
The registered route and other source/input guards remain wired; this
selection is not a live validation of them. C availability is not paid-launch
readiness, and compilation still sets launch authorization and grading flags
false.

### Exact focused evidence

`PILOT_PYTHON` denotes the existing private isolated interpreter with the
declared `openai-codex==0.147.0` and companion environment; its host locator is
omitted. No dependency was installed or upgraded. From the repository root,
the initial invocation at `789995071ed1b7630f2da1e239704301845a36cc` was:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$PILOT_PYTHON" -m pytest -q -o addopts= batch-runner/tests/test_codex_budget_pilot.py -k 'owned_child or integrated_capability or real_capability_gate_before_source_or_process'
```

Result: `4 failed, 6 passed, 24 deselected, 1 error in 22.00s`, exit 1.
The host returns `ENOSYS` for `pidfd_open`. That newly introduced dependency
caused four lifecycle cases to fail; one also raised a teardown error. The
six capability/owner-state cases passed under their original source scope.
Three harmless fixtures left by the failed setup were identity-checked and
terminated by their exact PIDs; a subsequent exact-PID check found none.
No shared or unrelated process was targeted.

The correction removes the pidfd dependency and uses unreaped direct-child
ownership with bounded SIGCHLD-driven waits. Only the four affected cases
were rerun at `d9bed6851a611787fa14f3e67c156d6369b11875`:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$PILOT_PYTHON" -m pytest -q -o addopts= batch-runner/tests/test_codex_budget_pilot.py::test_pilot_owned_child_tree_reaped_before_next_cell_or_restore batch-runner/tests/test_codex_budget_pilot.py::test_pilot_owned_child_cleanup_refusal_keeps_lock_and_durable_unresolved_cell
```

Result: `4 passed in 127.23s (0:02:07)`, exit 0. These cases traverse the
actual CLI/runner and owned-process transport. The narrow process allowance
starts the private supervisor, a harmless Python payload, a descendant that
creates its own session and ignores TERM, and an unrelated harmless control
process. Tests verify actual descendant disappearance and reaping, the unaffected control
process, serial-lock retention, no next-cell admission before cleanup,
repeated restore refusal after lost cleanup acknowledgment, retained partials,
unchanged expiry, preserved prior admissions and missing receipts. Timeout
injection and an actual host SIGTERM exercise the interruption boundary; a
normal payload exit also leaves a descendant for the supervisor to reap.

Original inputs and pipeline outputs are synthetic, and budget time uses fake
clocks. Other cells use the existing fake child transport. In the dispatcher
test process, SDK/client, credential, network, model/provider and grader
boundaries stay blocked. The controlled subprocess allowance runs only the
supervisor and fixed harmless fixtures, with offline flags inherited. No Codex
app-server, real preparation, dataset, VM, model or grading run occurred.
Both durations are pytest wall times, not task latency. Both logs are retained
privately. Partial preservation is checked before ordinary test-fixture
teardown; original inputs, historical real checkouts and published artifacts
remain untouched.

### Earlier evidence and review boundary

The initial dispatcher result remains `25 passed in 286.25s (0:04:46)`, exit 0,
at `6967ce8158459fd32506a14c25fa924e5b4747f8`. That invocation used synthetic
children/capability and provides offline dispatch/persistence evidence, not owned-tree
cleanup or model consumption. Its full 25-case selection was not rerun here.

The #652 feedback record retains its split evidence: at
`8805bb7f3b10ad267ea0970fdc6667a388ea1d32`,
`12 failed, 15 passed in 175.91s (0:02:55)`, exit 1; after a test-only fixture
correction at `df083e5306793db9e071365efd4a7efeaacfd38e`, only the twelve
affected cases ran again, reporting `12 passed in 93.91s (0:01:33)`, exit 0.
Neither selection was rerun here. These are offline feedback/accounting
results, not this dispatcher's lifecycle evidence or a fresh 27-pass run.
The complete dispatcher/feedback changelog entries and prior #648/#649/#650/
#651 evidence remain intact under their original scopes.

The leader supplied #652 FINAL-APPROVE review `5281735646` at
`b116563744351ab03769e356eb00fcfa39565da9` and all fourteen applicable checks
before integration. That approval covers the feedback intervention, not this
dispatcher or cleanup correction. REQUEST-CHANGES review `5282428403` at
`47e725bc3ff1945f12cc6756c0d610646dc7feb3` identifies the defect addressed here;
no new approval or carrying-HEAD CI success is claimed.

Full immutable dispatcher review and carrying-HEAD automatic checks remain
required. Actual local-input/runtime readiness, live execution validation,
separately directed pilot execution and fixed grading remain outstanding.
The leader already holds numeric-budget and paid-run authority; this is not
a new owner-approval wait. No live recovery, quality gain, invoice completeness,
whole-pilot result or Project-card completion is established.

The full skill catalog was reviewed once. Experiment-design kept seriality,
order, controls and causal limits fixed; backend/LLM guidance kept cleanup
within owned process boundaries. Experiment-report-en and im-not-ai-en preserve
the failed selection, narrow rerun and historical review scopes. UI/animation,
workflow, core QA, upload, pricing and framework work were outside this task.
No Azure/HF/provider/model/grader or paid operation, Project edit, PR merge,
CI query/manual rerun, broad suite or review waiting was performed.
