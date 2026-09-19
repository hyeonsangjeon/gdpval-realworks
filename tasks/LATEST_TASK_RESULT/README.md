# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Run Input Bundle Materializer and CI Runtime Correction

### Scope and Outcome

The comparison now has an offline materializer for the exact local inputs of
one caller-provided, pre-existing disposable checkout. It copies the pinned
parquet unchanged and installs only the registered `advance_check_5` references
under `data/gdpval-local`. Both V2 and Codex capture gates require verified
config and input bundles before provider, auth, model voice or client
construction. This closes input placement and runtime marker verification,
not checkout creation or launch readiness.

The CI correction changes test preparation only. The original 116-case
selector took 327.95 seconds locally. At PR HEAD
`ad93e14dff206da7aabbbd779efa9d77f414ccd9`, Backend Tests reached 91% before
the 45-minute job timeout cancelled it without a reported test failure. The
optimized selector retains all 116 cases and passed in 42.46 seconds. This
reduces the local selector time by 285.49 seconds; it does not establish that
the full CI suite now fits within its unchanged timeout.

Work started from immutable main
`a855c5a9604554499be9eed4e5eb5523e8ad95d5` in branch
`b/gpt54-run-input-bundle-materializer-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-run-input-bundle-materializer-20260919`.
The requested development worktree is separate from the preservation checkout
and prior worktrees. Neither the materializer nor its fixtures creates a Git
execution checkout or worktree. The existing Git identity was retained without
changing configuration, disabling hooks or adding attribution trailers.

Exactly sixteen files differ from the base:

- `batch-runner/gpt54_run_input_bundle.py`
- `batch-runner/gpt54_codex_input_capture.py`
- `batch-runner/gpt54_v2_input_capture.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_run_input_bundle.py`
- `batch-runner/tests/test_gpt54_prepared_input_attestation.py`
- `batch-runner/tests/test_gpt54_codex_input_capture.py`
- `batch-runner/tests/test_gpt54_v2_input_capture.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The correction continues in the same branch and worktree from immutable PR
HEAD `ad93e14dff206da7aabbbd779efa9d77f414ccd9`. Its delta is exactly three
of those files: `batch-runner/tests/test_gpt54_run_input_bundle.py`,
`CHANGELOG.md` and this record. No production source, preregistration, source
pin, workflow, timeout or historical artifact changes in the correction.

### Publication and Runtime Contract

The materializer requires the exact typed dispatch recipe, manifest, combined
plan and existing config bundle. It reuses #622's source snapshot to check
the pinned parquet, ordered five-task projection and exact reference inventory.
Each source is reread against its size and SHA256, and the accepted bytes are
held for publication. Extra references or empty directories, missing or changed
bytes, symlinks, hardlinks, traversal, source/target overlap and existing input
targets are refused before the first write. No other task's references are
copied, and no data is downloaded or regenerated.

After validation, the unchanged #623 writer publishes
`comparison-inputs-reserved.json` without replacement. This retained reservation
binds the intended ready document's size and SHA256. It is not a completion
signal. Required internal directories are created exclusively and held by
descriptors; an existing `data/` parent is reused only if held before publication.
The reservation prevents retry even if directory creation fails before
`data/gdpval-local` exists.

The same writer publishes the parquet and registered reference files. The
materializer rechecks the installed and source snapshots, config bundle,
reservation and parent directories, then publishes
`comparison-inputs-ready.json` last. On intermediate failure, partial files or
directories and the reservation remain without a ready marker. There is no
cleanup, adoption or overwrite path. This protocol does not promise a multi-file
transaction or power-loss durability.

The canonical input marker binds dataset revision, catalog and parquet digests,
file sizes, ordered task and source/text fingerprints, reference identities,
run/condition/repeat/ABBA identity, prepared-input linkage and the exact config
marker. It contains run-relative roles, not host absolute paths, authorization
flags or external inference identities. Runtime verification recompiles the
expected contract and rereads both bundles. Updating a file and both input
documents to matching attacker-supplied digests cannot bypass the source pins.

Existing absent/null controls retain their original branches, serialization
and execution order. The config materializer, atomic writer, capture/result
schemas, production grader/runtime defaults and cost-receipt semantics are
unchanged. The Sol manifest only refreshes its shared-parser digest. The current
source set has 30 pins. Its target evidence does not cover the whole target
grader closure or establish later wire consumption.

### Test Preparation Correction

The module-scoped seed runs the existing independent oracle and real config
materializer once for the fixed five-task data and four run configs. It retains
file contents and documents as immutable bytes, with a frozen typed plan.
Every case receives fresh single-link files and newly decoded mutable objects.
The seed's tree is checked for changes at teardown. Only this selector installs
the supplier overrides, and each case restores them afterward.

The compiler still executes its real validators. YAML parsing is cached by
exact input bytes or text and returns a deep copy; source-pin SHA256 calls
reuse a hash only for identical bytes and return a separate hasher. The real
grader helper computes the closure hash. Reuse requires identical arguments,
the complete core inventory, matching path types/link counts and every
dependency's actual bytes. Any mismatch delegates to the original helper.
No validation verdict or mutable target snapshot is cached.

The materializer, source/reference readers, target digest checks, no-clobber
writer and runtime gates remain real. Runtime cases still execute actual
input materialization, the Step 1 serializer, capture publication, Step 2,
restored-checkpoint and V2 entry gates as applicable. The parametrized case
list and existing write/refusal assertions are unchanged. Nothing is skipped
or removed, and no production behavior changes.

### Exact Verification Evidence

The same selector ran once for the original implementation and once after
this correction, with no broad suite or additional selector:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution
```

- Original implementation: **116 passed in 327.95s (0:05:27)**, exit 0.
- CI correction: **116 passed in 42.46s**, exit 0.
- `git diff --check` and the staged equivalent passed for the correction.

The reported CI finding is run
[`35454998454`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35454998454),
job [`105928601144`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35454998454/job/105928601144),
on `ad93e14dff206da7aabbbd779efa9d77f414ccd9`. Backend Tests was
**CANCELLED at 91% / 45 minutes**, with no reported test failure. `Run tests`
ended at the job limit; the last log named
`test_the_partial_gold_run_cannot_read_as_final.py`. These are the supplied
CI facts, not evidence that the last-named test failed. The workflow's
40-minute warning remains a finding threshold, not a reason to raise its
timeout. No workflow file was edited and no manual rerun was requested.

The small temporary fixtures cover all four ABBA runs, relocation, existing or
absent `data/`, exact input/marker bytes, unchanged source/config files, drift,
extra/missing inputs, links, overlap and collisions. They also cover interrupted
file/directory publication, races, retained reservations, retry refusal and
forged input bytes with rewritten markers. Both real runtime entrypoints refuse
invalid bundles before provider construction; Codex Step 1 and restored
checkpoints also refuse them. Minimal existing V2/Codex success and absent/null
regressions run inside the same selector. Positive runtime cases stop at fake
construction boundaries.

The fixtures guard against subprocess, network, download, auth, model, grader,
provider and VM execution. They use synthetic five-task data and ordinary
temporary source directories, not a full dataset scan or target Git checkout.
No workflow, `core/qa.py`, HF upload, grading implementation, historical ledger
or sealed evidence changed. No live credentials, paid execution, workflow
dispatch, Project edits or merge were performed.

### Immutable Review Boundary

Original implementation HEAD `e2d50bf057521e626c6a1ad75264b82b113105bd`
contains the code, tests, source pins and specification that produced the
327.95-second result.
`first-reviewer` reviewed the immutable boundary
`a855c5a9604554499be9eed4e5eb5523e8ad95d5..e2d50bf057521e626c6a1ad75264b82b113105bd`.
The verdict was `APPROVE`, with no BLOCK, MAJOR or MINOR findings and no
second-review escalation. That earlier approval does not cover the new
correction HEAD.

The new immutable test implementation HEAD is
`4a05e26debacdbd5cea8df6d915a40175064998f`. A fresh read-only `first-reviewer`
review covered
`ad93e14dff206da7aabbbd779efa9d77f414ccd9..4a05e26debacdbd5cea8df6d915a40175064998f`.
The verdict was `APPROVE`, with no BLOCK, MAJOR or MINOR findings and no
second-review escalation. The reviewer confirmed cache isolation, real
validators and unchanged case/assertion coverage without rerunning tests or
executing project code. No further code correction or selector invocation was
needed. Only `CHANGELOG.md` and this record follow that implementation HEAD
and are outside its review boundary. Leader review and fresh automatic CI
evidence remain required. No carrying-PR merge result, future merge SHA/time
or execution authorization is claimed.

### Remaining Work

The fixed cohort, V2 r1 → Codex r1 → Codex r2 → V2 r2 order, Foundry
GPT-5.4/xhigh requests, limits, grading and record-only null/partial cost
contracts remain unchanged. `launch_allowed` and `full_220_allowed` remain
false. The compound materialization/workflow blocker remains because this unit
only implements local input publication and marker verification.

- Fresh automatic Backend Tests completion within the unchanged 45-minute
  limit, followed by leader review of the corrected PR HEAD. The local timing
  improvement is not a full-suite pass.
- Checkout creation and actual deployment on a reviewed execution host.
- External inference identity issuance and approval.
- A host supporting native no-clobber result-bundle installation.
- Full materialized grader provenance and workflow gates.
- Served deployment/model/effort capability and native call/token caps.
- Later consumption and rendered/wire-request evidence.
- Usage/tariff evidence under the existing null/partial policy.
- The separate Sol pilot's GitHub Copilot provider/auth route, blocked by the
  missing official runtime handoff contract.

The study remains a configuration-bundle comparison. A local fixture, input
marker or capture does not establish environment-only causality.

### Skills and Roles

For the original implementation, the full skill and repository-agent catalogs
were inspected once before editing. `experiment-design` preserved the
comparison inputs, ABBA repeats, interpretation and stop gates. The
`llm-systems-engineer` role mapped the runtime boundaries and supplied the
bounded offline test fixtures.
`first-reviewer` reviewed the original immutable implementation read-only.
The CI correction uses a fresh immutable review rather than carrying that
approval forward.

`im-not-ai-en` was applied to the correction's English changelog,
completion-record and PR wording. Commands, SHAs, counts, results and
qualifications were checked manually to honor the selector limit instead of
running an extra fidelity script. The correction changes no experiment
condition or design, so no new
`experiment-design` application or systems-agent delegation is needed.
Experiment-report skills do not apply to software verification.
Repository-readiness, UI and animation skills are unrelated. No grading
pipeline implementation changed, so no grading-engineer work was needed.
Workflows, `core/qa.py` and HF upload scripts are untouched, so no
extreme-reasoner scope was created.

## Prior Result: #625 Run Config Bundle Materializer

[#625](https://github.com/hyeonsangjeon/gdpval-realworks/pull/625) added exact
config publication and pre-provider bundle verification. Its final PR HEAD was
`82cd50cf13ab0a70c4cbb61c3b22288a19e4d106`. The reviewed combined boundary ended
at `c0c86d9b55bb0810fbda1a3a5cc1741cf60d5ec1` with `APPROVE` and no remaining
findings. Its single selector reported `99 passed in 94.30s (0:01:34)`.
Those are prior facts, not a rerun or live-execution evidence from this task.
