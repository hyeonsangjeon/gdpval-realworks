# Latest task result

## Terminal accounting reconciliation for retained Codex cells

The correction passed one focused offline invocation:
`42 passed in 158.33s (0:02:38)`, exit 0, at implementation commit
`d486dc456e3caf8c2cacc4cfd480a9828796d0e5`. It covers 39 new crash,
invalid-state and unknown-usage cases, the existing nonterminal replay
regression, and two current/stale active-binding cases.

The leader's REQUEST-CHANGES review `5278280269` at
`0f3cbdca6326c4916f282d5f5796fd7bd02be15e` identified a real gap in the
earlier implementation. `observe_turn()` persisted usage before ledger
settlement, but terminal and expiry gates could return before the only replay
call. A crash before ledger commit left known usage reserved/unknown; a crash
after commit but before acknowledgment left its observation unacknowledged.
The earlier nonterminal replay test did not establish terminal recovery.

Host-only reconciliation now runs before native eligibility checks in the
public runner and before the outer retry gate. It validates the declared
cell/request/provider/settings identity, retained directory bindings, rendered
request digest and receipt ledger before replaying an observation through the
unchanged equality guard. Completed, filtered and expired cells can settle or
acknowledge an observed receipt without opening a runtime, admitting an attempt,
extending the expiry or clearing their terminal reason. Missing or incompatible
state still refuses. An unobserved gap stays missing/partial. Native completion
metadata does not become a reconstructed successful task result.

### Current focused evidence

`RESUME_PYTHON` denotes the already restored private isolated interpreter;
its absolute host path is omitted. From the repository root, the executed
environment and pytest argv were:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$RESUME_PYTHON" -m pytest -q -o addopts= batch-runner/tests/test_codex_native_resume.py::test_native_resume_crash_reconciliation_terminal_and_expired batch-runner/tests/test_codex_native_resume.py::test_native_resume_crash_reconciliation_refuses_unvalidated_state batch-runner/tests/test_codex_native_resume.py::test_native_resume_crash_reconciliation_keeps_unknown_usage_partial batch-runner/tests/test_codex_native_resume.py::test_native_resume_settlement_crash_replays_same_receipt_without_double_charge batch-runner/tests/test_codex_native_resume.py::test_native_resume_active_grader_template_source_bindings
```

The 24 crash cases cross B/C, public-runner/outer-retry entry, before-ledger/
post-ledger-before-ack interruption, and completion/filter/expired-downtime
states. Repeated host-store/runner/ledger reconstruction verifies one SQLite
settlement, acknowledged state, unchanged expiry/admissions/terminal reason,
retained partials and zero additional native requests. Thirteen refusal cases
retain the identity, path, checksum and ledger boundaries; two cases keep
unobserved or missing usage partial. The remaining three cases cover the
existing nonterminal replay path and current/stale active source bindings.

The installed SDK facade, request/response types and collector operate over
stubbed JSON-RPC transport and fake clocks. SDK/client constructors,
subprocesses, network, credential discovery and provider construction are
blocked. No native app-server, provider or model ran. The `158.33s` is pytest
wall time, not task latency or a cost measurement. No additional install,
test retry, full lane, suite, real-data or preparation operation was performed.
This is synthetic accounting/control-flow evidence, not live recovery or
complete API-call/invoice accounting.

### Preserved earlier evidence

The initial continuation slice passed its focused offline selection:
`45 passed in 188.99s (0:03:08)`, exit 0, at implementation commit
`db88d5301dd125704f06122645a049d8518de306`. The selection contains 41 new
resume/binding cases and four directly relevant deadline/legacy cases.

A later source-review correction made content-filter stops durable for all
three budgeted conditions. Its affected-only selection reported
`8 passed in 18.21s`, exit 0, at
`ee11f956d53225760b96040c2642e7ef0682b554`: six filter cases and two refreshed
current/stale binding cases. These are separate results; the 45-case selection
was not rerun at the filter-correction commit. Neither earlier selection was
rerun for this terminal-accounting correction.

The tests exercise the installed SDK facade, request/response types and turn
collector with a stubbed JSON-RPC transport and fake clocks. No Codex
app-server, provider or model was started. This is synthetic control-flow and
persistence evidence, not proof of live recovery, task quality or pilot results.

### Behavior and unchanged controls

Only the existing `execution.codex.task_deadline` opt-in changes behavior.
A cell means one declared run/task/condition/repetition. B/C share the same
continuation path; A keeps fresh-session attempts and its four-attempt cap.
Legacy exp035 and other modes retain their default retry, timeout and cleanup
behavior. No existing experiment is opted in by this change.

The existing private, locked deadline record now binds the native thread ID,
retained workspace/cwd, Codex home and task home directory identities, ordered
tasks, prepared/request digests, runtime/provider/settings and receipt ledger.
The adapter stages references once, persists the ID as soon as `thread/start`
returns, and uses the real pinned `Codex.thread_resume(thread_id, ...)` API for
continuation. It checks the returned ID before starting another turn and sends
the unchanged task request on that native thread. It does not synthesize a
conversation from earlier answers or fall back to a fresh thread.

A proven pre-thread runtime failure leaves a reusable staged workspace.
An uncertain thread-start response without a bound ID refuses. Missing,
corrupt, linked, replaced or cross-cell bindings and changed provider/config/
request identities refuse without restaging partials. A native resume refusal
also retains the binding. Older deadline files without continuation metadata
are not silently adopted or replaced with a new clock. Content-filter stops
remain terminal across restart for A/B/C, including refusals during turn
creation and streaming.

The same 180-minute expiry and durable attempt count remain authoritative.
Waits and restart downtime consume that expiry; native waiting remains bounded
by `min(1800, remaining_seconds)`. Exhaustion prevents another request.
Path-free observations add session policy, native-resume count and terminal
reason. Partial workspace files remain retained after failures and interruption.

Cumulative thread usage is differenced against a persisted observation
boundary. Observations are written before settlement; host-only reconciliation
now reaches the existing ledger's idempotent equality guard before terminal
or expiry refusals, under the same unique receipt ID. A lost response or
unobserved turn leaves an unknown boundary. Earlier cumulative tokens are not
charged again as new-turn usage, and missing usage remains missing/partial.
Decreasing counters refuse.
This does not establish per-HTTP-call counts, a complete bill or invoice
reconciliation. No pricing or automatic monetary cutoff changed.

### Dependency restoration and SDK contract

This correction reused the existing isolated `0.147.0` SDK environment without
installation. The following restoration facts belong to the initial slice.
The isolated task environment uses Python `3.10.12`. The repository's normal
`python3 -m venv` bootstrap reported missing `ensurepip`; it created the
isolated interpreter but could not seed pip. No OS or shared-environment
change was made. Existing pip `22.0.2` installed into the new private prefix
with `--isolated --ignore-installed --no-cache-dir --index-url https://pypi.org/simple`.
Both install commands exited 0: the exact SDK/companion pair, then the
necessary declared backend/test/renderer dependencies. Installer warnings
referenced unrelated packages visible to the system pip; they were not repaired.

Metadata in the isolated environment and the regression's genuine runtime-pin
check confirm `openai-codex==0.147.0` and `openai-codex-cli-bin==0.147.0`.
The SDK declares that same companion version. Its Pydantic dependency is
installed at `2.13.5`; the test runner is pytest `9.1.1`. The companion identity
comes from its distribution, not a global Codex executable. Neither executable
nor personal sign-in was invoked. Private installation logs and the isolated
environment are retained outside the repository.
Pytest used only synthetic files; no retained real workspace was opened or changed.

The installed declaration is `Codex.thread_resume(thread_id, ...) -> Thread`,
backed by `ThreadResumeParams`, `ThreadResumeResponse` and `thread/resume`.
It is distinct from `thread_fork`. The facade returns the response's native
thread ID; the adapter checks it against the host binding. This source/type
inspection does not establish a working live session or served model identity.

### Earlier exact commands and their scope

`RESUME_PYTHON` below denotes the private isolated interpreter; its absolute
host path is intentionally omitted. The remaining environment, pytest argv
and selected nodes are the executed commands, from the repository root.
The initial invocation at `db88d5301dd125704f06122645a049d8518de306` was:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$RESUME_PYTHON" -m pytest -q -o addopts= batch-runner/tests/test_codex_native_resume.py batch-runner/tests/test_codex_task_deadline.py::test_cumulative_task_deadline_retry_and_process_resume_do_not_reset batch-runner/tests/test_codex_task_deadline.py::test_cumulative_task_deadline_bounds_native_join_retains_partials_and_usage batch-runner/tests/test_codex_task_deadline.py::test_cumulative_task_deadline_legacy_retry_and_cleanup_unchanged
```

The tests reconstruct the host store, runner and ledger to simulate restart.
They verify equal B/C native-ID/workspace reuse, fresh A, pre-thread versus
uncertain/bound failures, cross-cell/target refusal, no request after expiry,
partial retention, content-filter finality and non-duplicated cumulative usage.
The real SDK's start/resume/turn methods and collector run over synthetic
messages validated by its actual types. SDK/client constructors, subprocesses,
network, credential discovery and provider construction are blocked.

Subsequent source inspection found that a content-filter exception during
turn creation was terminal for B/C but could still be retried by budgeted A.
The correction persists a cell-level stop for A/B/C and retains an uncertain
receipt if turn creation loses its response. This was a source-review gap,
not a failure reported by the initial 45-case selection. Only the affected
filter cases and refreshed binding checks were run at
`ee11f956d53225760b96040c2642e7ef0682b554`:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$RESUME_PYTHON" -m pytest -q -o addopts= batch-runner/tests/test_codex_native_resume.py::test_native_resume_content_filter_is_terminal_across_restart batch-runner/tests/test_codex_native_resume.py::test_native_resume_active_grader_template_source_bindings
```

That invocation reported `8 passed in 18.21s`, exit 0. The six filter cases
cover A/B/C at turn creation and streaming, including durable refusal after
host-state restore. The two binding cases accepted that commit's closure and
refused stale identities while preserving false launch flags and blockers.
Both `188.99s` and `18.21s` are pytest wall times, not task-latency measurements.
No full suite, earlier source-count/selector selection, dataset or real
preparation was rerun.

### Active source bindings

The unchanged `step8_grade.compute_grader_source_hash()` was called with each
original template path and actual configuration bytes. Only coupled active
future bindings/pins and the Foundry/GHCP digest guard were refreshed.

| Original template under `batch-runner/grading_configs/` | Main baseline | Prior continuation at `0f3cbdca6326c4916f282d5f5796fd7bd02be15e` | Current correction |
|---|---|---|---|
| `default_v2_sol_max.yaml` | `dd970ba3f5fff8ae4d8e006dfc33c023804e3e32d32123681fb76feadd5f10df` | `fdb0d71b7e02a55d28aef32b35a3e6a3e6cad45af35c5fbda03c766cb8d6c2fa` | `7f4632672a947cfca96a791cbb3d608655514036cec13fe6f7062e6132c00de1` |
| `exp035_codex_foundry_full220_v2_sol_max.yaml` | `ec77798f9c2fba1043bc1015c855f3f75a96920e78e6b64c007e33785f2e2170` | `7bcaebd4e51a22fdc1ab8d9e6f29735e53c1d9151597744a504656b9b3686ae0` | `7f51012275d5cd0c5129da2e333eb1214759f45ae22e390a80f595db9fd8cdbd` |

The current Foundry YAML digest is
`799d8f27bb7d755705befe34b3064d4a383a33db54e1e163f31dc452aedf7fa4`;
the prior continuation digest was
`aa8d3c1a3e5cc0a7f8aeb86d12c88fd5a0b40155d97bc479d84041b94349beab`.
Source sets remain 37 and 58; no source module or count assertion was added.
The current identities were checked in the 42-case reconciliation result;
the earlier 45/8 results covered their own closures. These selections use
the real helper and validators and retain every launch blocker and false
launch flag.
`WORKFLOW_SHA256`, original source/base provenance, historical templates,
grades, receipts and prior prepared artifacts are unchanged.

### Review boundary and remaining work

Main remains `237fdc429420d417909fd109232710d933c5ce63`, the branch's original
baseline. No fetch or integration was needed for this correction.
The leader reports that #650 passed all fourteen applicable checks at
`846b7dddc7d4cf674f4da68ca5d6e1d330e3b6b5`, with final review `5276986025`
and original runtime review `5276488086`. Those reviews cover the prior
deadline slice and its corrections, not this continuation implementation.
Its historical evidence, and #648/#649's operational/selector history, remain
unchanged in the changelog. The old #650 branch was not edited.

Review `5278280269` requested changes at
`0f3cbdca6326c4916f282d5f5796fd7bd02be15e`; it is not approval of this fix.
This correction still needs immutable-HEAD leader review and carrying-HEAD CI. Native
app-server recovery and paid behavior were not exercised. Adaptive policy and
the 30-cell dispatcher remain unimplemented. The intended pilot remains
`advance_check_5` × A/B/C × two repetitions, ABC then CBA per task, one active
inference execution on the same deployment, with the unchanged 180-minute
cumulative/30-minute attempt policy. Model, effort, context, task selection,
fixed grading and other policies are unchanged. The supervisor's settings do
not select the experiment model. The leader already holds delegated paid-run
authority; a separately directed launch still follows review and readiness.
No Project card or whole experiment is complete.

The full skill catalog was reviewed once. Experiment-design preserved B/C
equality and A's baseline; backend/LLM guidance and openai-docs guided use of
the installed pinned SDK and existing seams. Experiment-report-en and
im-not-ai-en kept this synthetic evidence, dependency facts and review limits
separate in the bounded English records. UI/animation, workflow, QA, upload,
pricing and framework work were not applicable. No CI query, model/provider,
Azure/HF operation, VM, grader, real-artifact retry, Project edit or PR merge
was performed.
