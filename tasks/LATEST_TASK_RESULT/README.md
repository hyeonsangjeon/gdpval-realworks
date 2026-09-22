# Latest task result

## Condition C receives host-observed recovery feedback

Condition C now receives a small host-generated recovery context after an
eligible transient failure. B continues mechanically with the unchanged task
request. Both use the existing native-thread/workspace continuation and fixed
backoff. The offline evidence covers the submitted input, persistence,
refusals and accounting; it does not measure whether error feedback improves
task solving or demonstrate live recovery.

The implementation starts from exact main
`149d89afd43e54a46b6f172b71c2cf23d0cb7a17`. The leader reports fourteen
applicable checks passing for #651 at
`a9daa0ebdb02b60679771ff7f6241f7754e661fa`, with FINAL-APPROVE review
`5281145545`. That approval covers the preceding continuation and its
terminal-accounting/reference corrections, not this recovery-feedback change.
The old branch and all prior real artifacts remain untouched.

### The single intervention and its limits

Only the existing `execution.codex.task_deadline` opt-in with condition C adds
feedback. A keeps fresh sessions and four attempts. The first request is
identical across A/B/C. B/C keep the same retained-state capability,
model/provider/effort/context/tools, fixed retry backoff, 180-minute cumulative
deadline and 30-minute attempt bound. Legacy defaults and existing experiment
settings are unchanged; no experiment is newly opted in by this unit.

The existing automatic retry categories remain `rate_limited` and
`turn_start_failed`. After one of those observed failures, C's next native
turn appends a fixed instruction to reuse retained work and choose its next
task-solving strategy. Its structured context contains only the recorded
failure category, HTTP status when actually observed, opaque failed/current
attempt IDs, and the remaining cumulative seconds at the current attempt's
durable admission. That time is a snapshot, not a new allowance or a promise
that reopening the runtime takes no time. The host still bounds native
waiting by `min(1800, remaining_seconds)` and owns the expiry.

The installed `openai-codex==0.147.0` contract provides `TurnError.message`,
free-form `additional_details` and structured HTTP-status variants. It has no
typed retry-guidance field on that error. `retry_guidance` therefore remains
null; no Retry-After is inferred. Raw exceptions, free-form details, host
paths, credentials, grader/gold feedback and model-authored instructions do
not populate the context. No feedback is attached to the first request, an
unobserved failure or a noneligible failure. This variant does not optimize
external wait scheduling or let Codex change limits.

The host persists the whitelisted observation at the turn boundary, before
usage settlement. Each admitted C context is derived from the immediately
preceding failed turn and bound to the immutable cell/input/runtime identity.
The base request digest is still checked. A separate digest binds the full
input for each retained-thread turn before submission, including its permitted
C addition and developer instructions. Accounting restore validates those
bindings before settlement; stale, cross-cell, forged or missing context and
arbitrary base-input changes refuse. The continuation format is now
`codex-native-continuation-v2`.
Existing v1 continuation state is refused, not rewritten, silently adopted or
given a fresh clock.

Verified references keep their ordered declared identities and SHA256/size
through the normal Step 2 temporary staging path. Retries do not restage over
retained partials. Completion, content filtering and expiry remain closed to
native work. Host-only accounting restore admits no attempt, opens no runtime
and clears no terminal reason. SDK-reported cumulative usage, including any
C input, is differenced at the existing receipt boundary; prior totals are
not charged again. Unobserved or missing usage stays missing/partial. This
does not establish per-HTTP-call counts or invoice completeness.

### Focused offline evidence

The existing isolated SDK environment was reused without installation.
The genuine runtime-pin check confirmed both `openai-codex` and
`openai-codex-cli-bin` at `0.147.0`. Tests use the real SDK facade,
request/response types and collector over stubbed JSON-RPC transport and fake
clocks. SDK/client constructors, subprocesses, network, credential discovery
and provider construction are blocked. Synthetic reference files go through
the real `_execute_single_task()` default resolution/staging path; no original
dataset or prepared artifact is read. No native app-server, provider, model,
VM or grader ran.

`RESUME_PYTHON` below denotes that private isolated interpreter; only its
absolute host locator is omitted. From the repository root, the initial
invocation at `8805bb7f3b10ad267ea0970fdc6667a388ea1d32` was:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$RESUME_PYTHON" -m pytest -q -o addopts= batch-runner/tests/test_codex_recovery_feedback.py
```

It reported `12 failed, 15 passed in 175.91s (0:02:55)`, exit 1. The fifteen
passing cases covered identical first requests and C-only input, B/C restart
replay, post-ledger/pre-ack terminal recovery, unknown usage, closed boundaries
and current/stale active bindings. Twelve new crash cases failed because the
fixture interrupted `_settle_call()` while startup replayed an already-settled
first receipt, before the intended second turn existed. This was a fixture
error, not an observed live-runtime failure.

Test-only correction `df083e5306793db9e071365efd4a7efeaacfd38e` passes that
settled replay through the unchanged real equality guard and interrupts the
pending ledger commit. Only the twelve failed cases were rerun:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$RESUME_PYTHON" -m pytest -q -o addopts= 'batch-runner/tests/test_codex_recovery_feedback.py::test_recovery_feedback_terminal_accounting_never_reopens_native_work[completed-before_ledger]' 'batch-runner/tests/test_codex_recovery_feedback.py::test_recovery_feedback_terminal_accounting_never_reopens_native_work[content_filter-before_ledger]' 'batch-runner/tests/test_codex_recovery_feedback.py::test_recovery_feedback_terminal_accounting_never_reopens_native_work[expired-before_ledger]' batch-runner/tests/test_codex_recovery_feedback.py::test_recovery_feedback_forged_or_stale_context_refuses_before_request_and_settlement
```

Result: `12 passed in 93.91s (0:01:33)`, exit 0. Three cases reconcile a pending
C-turn receipt after completion, filtering or expiry without another native
request. Nine cases refuse forged/stale/cross-cell context, invented guidance,
raw instructions, missing context, altered submitted/base input or an old
format before a request or invalid settlement. The earlier fifteen passes
keep their original scope and SHA. Production and active-binding bytes are
identical between the two commits; there was no fresh single 27-pass run or
full-suite/final-HEAD validation. Both durations are pytest wall times, not
task latency. Both logs are retained privately.

### Active identities and preserved history

The unchanged `step8_grade.compute_grader_source_hash()` used each original
template role and actual configuration bytes. Only coupled active future
bindings, source pins and the Foundry YAML digest guard changed.

| Original template under `batch-runner/grading_configs/` | Prior main closure | Recovery-feedback closure |
|---|---|---|
| `default_v2_sol_max.yaml` | `ec325c4715e739700006c8f33dc9b503162120dc9a5882bb6aad524ca2634e6d` | `f38ccc5bf00b457147b7e91794a1ea806b863b16201b6f247ee791ef0f3e557d` |
| `exp035_codex_foundry_full220_v2_sol_max.yaml` | `65427741a0c8f6370ce49befe31fde8ef9e9c4bc8ecb6f150d0eadb1a37c753c` | `47effd1db4c1de5ff7cf0473a034ece7748312e682597fb06ee480678e000fcf` |

The active Foundry YAML digest is
`f51d92c35f388f016488f15d5e96acd1f9de10345fb2379dac7e194eadbbe2fd`.
Source sets remain exactly 37/58; no production source module was added.
The current/stale checks use real validators and preserve equality guards,
all live blockers and false launch flags. `WORKFLOW_SHA256`, original source/base provenance,
historical templates, grades, receipts and prior prepared artifacts are
unchanged. A source-identity refresh does not upgrade any historical result.

Earlier #651 evidence remains separate and was not rerun:

| Scope | Tested implementation SHA | Original result |
|---|---|---|
| Initial native continuation and related deadline/legacy cases | `db88d5301dd125704f06122645a049d8518de306` | 45 passed in 188.99s |
| Durable content-filter correction and bindings | `ee11f956d53225760b96040c2642e7ef0682b554` | 8 passed in 18.21s |
| Terminal-accounting correction and bindings | `d486dc456e3caf8c2cacc4cfd480a9828796d0e5` | 42 passed in 158.33s |
| Stable-reference correction and related guards/bindings | `76178074c1ad1e7a11f7b7a40d0773c26295ef20` | 43 passed in 165.28s |

Those are synthetic offline results, each exit 0 with its own selection and
closure. The existing changelog retains their full history, along with
#648's real preprocessing and #649/#650's selector/deadline history.

### Review boundary and remaining work

This feedback implementation remains unreviewed. Immutable-HEAD leader review
and carrying-HEAD automatic CI are still required; no CI query or success is
claimed for this change. Live native recovery and the effect of error feedback
remain unmeasured. The 30-cell dispatcher and external wait optimization are
not implemented. The intended pilot remains `advance_check_5` × A/B/C × two
repetitions, ABC then CBA per task, one active inference execution on the same
deployment, with fixed task/model/effort/context/grading policies and the
unchanged 180/30-minute limits. The leader already has delegated paid-run
authority; a separately directed launch follows review and technical
readiness, not a new owner-approval wait. No whole-experiment or Project-card
completion is claimed.

The full skill catalog was reviewed once. Experiment-design fixed the single
feedback intervention and its limited causal claim; backend/LLM and SDK
guidance kept integration on the existing runner and installed contract.
Experiment-report-en and im-not-ai-en preserved the split test evidence,
historical scopes and review limits in these bounded records. No workflow,
QA, upload, pricing, UI/animation, framework, dependency-install, real-data,
Azure/HF/provider/model/VM/grader or paid work was performed. No Project edit,
PR merge, CI polling or review waiting was performed.
