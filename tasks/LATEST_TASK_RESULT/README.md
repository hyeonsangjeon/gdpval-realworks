# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Run Input Bundle Materializer

### Scope and Outcome

The comparison now has an offline materializer for the exact local inputs of
one caller-provided, pre-existing disposable checkout. It copies the pinned
parquet unchanged and installs only the registered `advance_check_5` references
under `data/gdpval-local`. Both V2 and Codex capture gates require verified
config and input bundles before provider, auth, model voice or client
construction. This closes input placement and runtime marker verification,
not checkout creation or launch readiness.

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

### Exact Verification Evidence

The following selector ran exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_run_input_bundle.py::test_run_input_bundle_is_exact_atomic_and_gates_execution
```

Result: **116 passed in 327.95s (0:05:27)**, exit 0. `git diff --check` and
the staged equivalent passed. No other selector or suite was run.

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

Implementation HEAD `e2d50bf057521e626c6a1ad75264b82b113105bd` contains the
code, tests, source pins and specification that produced the result above.
`first-reviewer` reviewed the immutable boundary
`a855c5a9604554499be9eed4e5eb5523e8ad95d5..e2d50bf057521e626c6a1ad75264b82b113105bd`.
The verdict was `APPROVE`, with no BLOCK, MAJOR or MINOR findings and no
second-review escalation. The reviewer did not rerun tests or execute project
code. No implementation correction or selector rerun was needed. Only
`CHANGELOG.md` and this record follow that HEAD and are outside the review
boundary. Leader review and automatic CI evidence remain required. No
carrying-PR merge result, future merge SHA/time or execution authorization is
claimed.

### Remaining Work

The fixed cohort, V2 r1 → Codex r1 → Codex r2 → V2 r2 order, Foundry
GPT-5.4/xhigh requests, limits, grading and record-only null/partial cost
contracts remain unchanged. `launch_allowed` and `full_220_allowed` remain
false. The compound materialization/workflow blocker remains because this unit
only implements local input publication and marker verification.

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

The full skill and repository-agent catalogs were inspected once before
editing. `experiment-design` preserved the comparison inputs, ABBA repeats,
interpretation and stop gates. The `llm-systems-engineer` role mapped the
runtime boundaries and supplied the bounded offline test fixtures.
`first-reviewer` reviewed the immutable implementation read-only and found no
blocking, major or minor issues.

`im-not-ai-en` was applied to English changelog, completion-record and PR
wording. Commands, SHAs, counts, results and qualifications were checked
manually to honor the selector limit instead of running an extra fidelity
script. Experiment-report skills do not apply to software verification.
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
