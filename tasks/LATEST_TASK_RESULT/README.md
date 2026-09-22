# Latest task result

## Lightweight deadline validation after main integration

Deadline control parsing and config validation no longer import host
persistence or the HF SDK. The corrected cold-process family passes all five
cases. Five host-state/binding cases passed in the earlier focused invocation;
the requested Node subtest remains locally unvalidated because the worktree
lacks the JavaScript `yaml` package. This is implementation and synthetic
offline evidence, not a pilot result, model observation or execution approval.

One authorized fetch returned exact main
`a8872bb1db11fa7420ca1e83e1efb66f853c5127`, integrated through an ordinary merge
in correction `57c9548091fb9447727f85d88945f346e6ea9e0e`. #649's selector/test
bytes, isolated-import correction and active-binding regressions are preserved;
its history and #648's real preprocessing entry remain in the changelog.
Expected completion-record and active-hash overlaps were resolved without
changing either feature's controls. No second fetch occurred.

### Supplied failure and correction

The leader supplied validate run `35708485032`, job `106683066256`, at
`d6dd36557379279dda55add439f6b2118a844424`, completed
`2026-09-22T09:07:17Z`. Node reported `545 passed, 1 failed, 546 total`.
The failing subtest at `scripts/__tests__/onboarding-contract.test.mjs:239`
was `workflow input tables mirror defaults and watchdog delegation`.
The supplied trace is `ExperimentConfig.validate()` at
`experiment_config.py:561` → `core.codex_task_deadline:26` →
`core.hf_publication:15` → `ModuleNotFoundError: huggingface_hub`.
Backend packages installed locally had masked this eager-import dependency.
No full logs were fetched and the unchanged failure was not reproduced.

The correction imports the existing private JSON/path helpers only when
deadline state is initialized, read, written or used for attempt admission.
It also defers host locking/runtime-path imports to state use. Validation
remains active for legacy configurations and valid/invalid opt-ins. No secure
persistence helper was duplicated, and no dependency/workflow workaround was
added. The 180-minute cumulative policy, 30-minute attempt timeout and legacy
defaults are unchanged.

### New focused evidence

At immutable correction `57c9548091fb9447727f85d88945f346e6ea9e0e`, one process
ran:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_codex_task_deadline_import_boundary.py batch-runner/tests/test_codex_task_deadline.py::test_cumulative_task_deadline_lazy_persistence_helpers_initialize_and_restore batch-runner/tests/test_codex_task_deadline.py::test_cumulative_task_deadline_active_grader_bindings batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_preserves_history_foundry_and_backend_partition
```

Result: `5 failed, 5 passed in 3.73s`, exit 1. The real host-state helpers
passed initialization/restore with unchanged expiry and 120 seconds of fake
elapsed time. Three binding cases accepted the combined closure and refused
the selector-only and deadline-only hashes; launch flags remained false.
The coupled Foundry/GHCP digest guard also passed. The five cold processes
failed before config validation because `-I` excluded installed user-site
PyYAML. A direct availability check confirmed PyYAML `6.0.3` in that user site.

Test-only correction `83002a0d0d725321c833ebf23cc100563265c15d` replaces `-I`
with `-B`, preserving installed parser dependencies. Each case still starts a
fresh interpreter and makes `core.hf_publication` and `huggingface_hub`
unavailable through an import finder. It asserts neither was attempted or
loaded. The actual `ExperimentConfig.from_yaml()`, `from_dict()` and
`validate()` paths accept legacy/legacy-Codex and valid deadline configs, and
reject invalid repetition and timeout controls. Child network/process
boundaries remain blocked; no expected-success parser stub is used.

Only the five affected cold-process cases were rerun at that correction:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_codex_task_deadline_import_boundary.py
```

Result: `5 passed in 0.78s`, exit 0. The earlier five passing cases were not
rerun. These separate selections are not a fresh full-lane validation.

The following requested Node command was attempted once at
`57c9548091fb9447727f85d88945f346e6ea9e0e`:

```bash
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 node --test --test-name-pattern="workflow input tables mirror defaults and watchdog delegation" scripts/__tests__/onboarding-contract.test.mjs
```

It exited 1 at module loading with `ERR_MODULE_NOT_FOUND` for the JavaScript
`yaml` package, before the named subtest ran. The harness reported one failed
test-file entry, not a new result for the hosted 546-test suite or the selected
assertions. No packages were installed, no alternate Node run was attempted,
and no dependency manifest or workflow was changed. Validation of that subtest
with its declared dependencies remains outstanding.

### Combined active source identities

The unchanged `step8_grade.compute_grader_source_hash()` used each original
template path and its actual configuration bytes after integration and the
lazy-import correction. Neither branch's previous closure was reused.

| Original template role | Combined full-source SHA256 |
|---|---|
| `default_v2_sol_max.yaml` | `dd970ba3f5fff8ae4d8e006dfc33c023804e3e32d32123681fb76feadd5f10df` |
| `exp035_codex_foundry_full220_v2_sol_max.yaml` | `ec77798f9c2fba1043bc1015c855f3f75a96920e78e6b64c007e33785f2e2170` |

The current/stale regressions reject both main's selector-only pair
(`c92bf13696fa506c84dbee649d5ba3c03fb33244810f30e2be4a05630ca204e1`,
`785352daa052b105f0dfce08d8de7b3f41633a8e6b312111bec5bdbc8806144b`)
and the deadline-only pair recorded below. Coupled active pins bind
`core/codex_task_deadline.py` as
`cf9cddabc394d3e3129afc41ddb0ddaba9d29561382768d238840d75fcae250b`
and the Foundry preflight as
`7313d1c49955449806ad5bdd1545259ccf4bbbab829df9354a8689d68bc0b121`.
The Foundry YAML guard is now
`7d40b6de154ba8552204f6ace9e863eeda903c80bb6ba02486ada8e1caeedb6f`.
Source counts remain 37/58. Equality checks, `WORKFLOW_SHA256`, original
source/base provenance, tasks, models, effort, repeats, grader configs, live
blockers and false launch flags remain unchanged. Historical hashes/results
are not upgraded by these future-plan bindings.

### Behavior and default boundary

The opt-in `execution.codex.task_deadline` block declares `condition: A`, `B`
or `C` and `repetition: 1` or `2`. Existing configs are not opted in. The
consumer requires `codex_foundry`, one prepared condition, a stable run lineage,
`timeout: 1800`, `max_retries: 3`, no Self-QA/preprocessors and an explicit
host-owned `--codex-deadline-state` directory. New cells require explicit
initialization into an absent directory; restart/resume must restore that same
state, not initialize another directory.

One 180-minute expiry is persisted per run/task/condition/repetition and bound
to the ordered task IDs and prepared fingerprint. It includes backoff and
restart downtime. Missing, incompatible, linked, checksum-tampered or
backward-clock restore state refuses. Atomic private-JSON persistence and a
nonblocking process lock protect the host record outside agent-writable roots.
The checksum detects damaged/edited state, not a hostile host replacing both
payload and checksum.

The existing retry loop and `TaskExecutor` pass this deadline to the real Codex
turn runner. Every attempt is admitted against remaining time. Native waiting
is bounded by `min(1800, remaining_seconds)`; backoff cannot extend the expiry.
A retains four durable attempt admissions. B/C replace that cap with the
cumulative deadline and retain identical partial-artifact capabilities. The
existing transient-error retry categories are unchanged; this is not an
adaptive retry policy. `task_deadline_exhausted` records exhaustion without an
additional turn. Missing/invalid state records `task_deadline_state_refused`.

Interrupted attempt workspaces remain available. Path-free result records
carry expiry, remaining time, admissions and observed completed waits. The
existing receipt ledger records observed token usage with missing-call/cost
qualifications, not complete API-call or invoice accounting. There is no
automatic monetary cutoff. Without the opt-in, legacy exp035 and other modes
retain their existing retry, timeout and cleanup behavior.

### Preserved first-slice evidence

The first-slice command ran once at implementation
`fe4d772df69c1653709bdfaf5bede8d005a6bf01`, based on
`eba56139f95443a715e8309e75c57fe5688c1f2b`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_codex_task_deadline.py batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_preserves_history_foundry_and_backend_partition
```

Result: `30 passed in 40.83s`, exit 0. The 29 deadline/binding cases cover retry
and process resume without resetting expiry; bounded native waits; backoff;
no turn after exhaustion, including expiry during receipt reservation; new
cell identities; retained partials and observed usage; invalid restore refusal;
config/CLI propagation; legacy behavior; and genuine current/stale grader
bindings. The additional case preserves the coupled Foundry/GHCP digest and
workflow/history assertions. Clocks and the native runtime were stubbed;
provider/auth/network/subprocess construction and real sleeps were blocked.
No full lane, selector family, prior binding family or real-data preparation
was rerun. `git diff --check` passed. This historical selection did not test
the cold lightweight-import boundary and was not rerun in this correction.

The unchanged helper produced these historical first-slice identities from
the original template paths and bytes, before selector integration:

| Template role | Pre-slice SHA256 | Deadline-only SHA256 |
|---|---|---|
| `default_v2_sol_max.yaml` | `40ada97c41117e3966e5a192c19dafcf4db34d4dd2ddd4230c4b729f421d6e08` | `fdfb7b9160635859d2c46ee9a79d5d908bc4ad546f9d240893da98159752258d` |
| `exp035_codex_foundry_full220_v2_sol_max.yaml` | `56fdb74e2f9fd1afbe9d064fc2cb1e1410d5cebec55edcca8324effd1a1dc9e1` | `c85f5b7ac5a723266172fedae39d38a69bd93cebae25888c63469f038c97ef01` |

That slice's binding updates affected only active GPT-5.4/Foundry plans and
coupled guards. The deadline module became an explicit pin, with source counts 37 and
58. Its historical Foundry YAML digest was
`824533c9e08b1b24217c66497ee9c269e2c156411e3a5d95238a1bcc578e80f0`.
Historical source/base identities, grader templates/results, task/control
settings, live blockers and false launch flags remain unchanged. No workflow,
model/effort/context, pricing, `core/qa.py` or HF-upload code changes.

### Remaining work and review boundary

The intended pilot remains `advance_check_5` × A/B/C × two repetitions, 30
executions, ABC then CBA per task, with one active inference execution on the
same deployment. This slice does not implement that dispatcher, agent-session
rehydration or adaptive planning. End-to-end state recovery and equal B/C
continuation behavior still need later implementation/review. The supervisor's
Astra Max/1M settings are not a target-model selection. Leader-directed paid
launch remains separate from this implementation-only authorization.

`REQUEST-CHANGES` review `5276176303` at
`d6dd36557379279dda55add439f6b2118a844424` identifies the eager-import defect;
the leader has not approved the first deadline slice. That review and #649's
earlier approval do not approve this integration/correction or these later
records. Full implementation review and final-HEAD automatic checks remain
outstanding. Code inspection is not proof of runtime deadline enforcement;
the earlier fake-clock tests retain only their stated synthetic scope.

The leader already holds delegated budget/paid-run authority; no new owner
approval wait is introduced. Paid launch still requires a separate leader
direction and is not authorized here. No CI query, manual rerun, review wait,
Project edit or PR merge occurred. No Azure/HF/provider/model, VM, grader or
paid operation ran. Original inputs, prepared/failed real artifacts, published
grades and prior operational changelog entries were untouched. No agent
rehydration, adaptive policy or 30-cell dispatcher was added. The branch is
frozen after this correction's publication. This does not complete the pilot
or Project card.

The full skill catalog was checked once for this phase. `experiment-design`
kept the approved controls fixed before active pin edits. Repository backend
and LLM-systems guidance governed the lazy persistence boundary; grading
guidance governed genuine source-identity coupling, not grading.
`experiment-report-en` separated supplied CI, synthetic tests, the local
dependency refusal and unmeasured outcomes.
`im-not-ai-en` preserved exact commands, values and qualifications. UI/animation,
framework, workflow, QA/upload, pricing and repository-publication skills did
not match this bounded implementation.
