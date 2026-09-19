# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Run Config Bundle Materializer

### Scope and Outcome

The comparison now has a materializer for one caller-provided, pre-existing
disposable source checkout. It reuses the typed dispatch and grading plans
to publish exact run configs without overwriting files. V2 and Codex capture
gates require the completed bundle and recheck its bytes before provider,
auth, model voice or client construction. This closes config placement and
runtime marker verification only, not checkout creation or launch readiness.

Work started from immutable main
`baa81d4f7ca65680c04f7f19d3a375cd60c8f39b` in branch
`b/gpt54-run-config-bundle-materializer-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-run-config-bundle-materializer-20260919`.
The requested development worktree is separate from the preservation checkout
and prior worktrees. Neither the materializer nor its fixtures creates a Git
checkout or worktree. The existing Git identity was retained without changing
configuration, disabling hooks or adding attribution trailers.

Exactly sixteen files differ from the base:

- `batch-runner/gpt54_run_config_bundle.py`
- `batch-runner/gpt54_codex_input_capture.py`
- `batch-runner/gpt54_v2_input_capture.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_run_config_bundle.py`
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

The materializer recompiles the manifest and requires exact typed
`ComparisonRunSpec` and `ComparisonGradingRunSpec` values, the combined plan,
ABBA identity and ordered task scope. It reads the target checkout's 29 pinned
sources independently. Missing or changed pins, unsafe paths, symlinks,
hardlinks and collisions are refused before the first write. All parent
directories must already exist.

It publishes four byte-identical compiler outputs:

- `comparison-plan.json`
- `batch-runner/comparison-run.json`
- `batch-runner/comparison-grading.json`
- `batch-runner/experiments/execution_envelope/<run_id>.yaml`

Each uses the unchanged #623 atomic no-clobber writer. After rechecking the
members, source bytes and held parent directories, the materializer publishes
`comparison-bundle-ready.json` last. A write failure may leave complete
individual files, but no ready marker. A partial tree, including another
repeat's generated config, cannot be adopted or overwritten. This protocol
does not promise a multi-file transaction or crash durability.

The canonical marker binds file sizes and SHA256 values, source pins,
manifest bytes, declared base, run/condition/repeat, ABBA index and task order.
Its prepared-input linkage carries the existing contract versions, static
plan/config/source fingerprints and run-relative capture role. It does not
invent future capture, prepared-projection or four-run attestation digests.
Host absolute paths are not identity.

Both capture gates recompile the expected bundle and compare the marker and
every member byte. Matching hashes in a forged marker cannot legitimize a
changed config. Codex also verifies the bundle before Step 1 publishes its
prepared file. Existing absent/null controls remain no-ops: the regression
checks legacy serialization, record fields and execution order with capture
helpers forbidden. The atomic writer and capture/result schemas are unchanged.
The Sol manifest only refreshes its shared-parser digest.

The marker's evidence boundary is `local_config_bundle_consistency`. Its
target witnesses cover the listed 29 pins, not the whole target grader closure.
The existing `template_source_sha256` check covers the executing compiler
checkout; `materialized_grader_source_hash` remains unresolved. The marker
does not establish Git review approval, actual prepared inputs, served
capability, wire-request equality, inference identity or launch permission.

### Exact Verification Evidence

The following selector ran exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_run_config_bundle.py::test_run_config_bundle_is_exact_atomic_and_gates_execution
```

Result: **99 passed in 94.30s (0:01:34)**, exit 0. `git diff --check` and
the staged equivalent passed. No other selector or suite was run.

The fixture covers all four ABBA runs, repeat identity, relocation, recipe,
plan/source/path drift, unsafe files, collisions, failure after each member
and at the final marker, refused retries, marker/member forgery and real
pre-provider runtime gates. It reuses only four existing capture regression
cases: successful r1 and absent/null legacy behavior for each harness.
It does not rerun their complete selector matrices. Accepted runtime cases
stop at fake construction boundaries; subprocess, network, downloads,
provider auth, model/grader/client and VM execution are guarded against.

Other coupled tests only refresh the pin count to 29. The synthetic fixtures
copy pinned source bytes into temporary ordinary directories and use small
five-task data, not production dataset scans or execution-target Git checkouts.
No workflow, `core/qa.py`, HF upload, grading implementation, historical ledger
or sealed evidence changed. No live credentials, paid execution, workflow
dispatch, Project edits or merge were performed.

### Immutable Review Boundary

The initial implementation HEAD
`58386ae32fc82d32f8fe651590c29865a4b7bca2` received `APPROVE`, with no BLOCK
or MAJOR findings. The sole MINOR finding was a historical base label in the
specification. A two-line correction preserves the original V2 capture base
and gives the bundle materializer a separate provenance entry. It changes
no code, tests or pins, and the selector was not rerun.

The combined immutable boundary
`baa81d4f7ca65680c04f7f19d3a375cd60c8f39b..c0c86d9b55bb0810fbda1a3a5cc1741cf60d5ec1`
received `APPROVE`, with no remaining BLOCK, MAJOR or MINOR findings and no
second-review escalation. The reviewer combined the original review with
the documentation delta and did not rerun tests or execute project code.
Only this record and `CHANGELOG.md` follow the corrected HEAD and are
outside the review boundary. Leader review and automatic CI evidence remain
required. No carrying-PR merge result, future merge SHA/time or execution
authorization is claimed.

### Remaining Work

The fixed five-task cohort, V2 r1 → Codex r1 → Codex r2 → V2 r2 order,
Foundry GPT-5.4/xhigh requests, limits, grading and record-only null/partial
cost contracts remain unchanged. `launch_allowed` and `full_220_allowed`
remain false. The compound materialization/workflow blocker remains because
this unit closes only local config publication and marker verification.

- Checkout creation and actual dataset/reference deployment.
- External inference identity issuance and approval.
- A host supporting native no-clobber result-bundle installation.
- Full materialized grader provenance and workflow gates.
- Served deployment/model/effort capability and native call/token caps.
- Later staged consumption and rendered/wire-request evidence.
- Usage/tariff evidence under the existing null/partial policy.
- The separate Sol pilot's GitHub Copilot provider/auth route, blocked by the
  missing official runtime handoff contract.

The study remains a configuration-bundle comparison. A local fixture, ready
marker or capture does not prove environment-only causality.

### Skills and Roles

The full available skill and repository-agent catalogs were inspected once
before editing. `experiment-design` preserved the fixed comparison inputs,
ABBA repeats, interpretation and stop gates. The `llm-systems-engineer` role
mapped construction boundaries, supplied the bounded test fixture and audited
the production changes read-only. `first-reviewer` reviewed the immutable
implementation and documentation correction without rerunning tests or
accessing external services.

`im-not-ai-en` was applied to English changelog, completion-record and PR
wording. Commands, SHAs, counts, results and qualifications were checked
manually to honor the selector limit instead of running an extra fidelity
script. Experiment-report skills do not apply to software verification.
Repository-readiness, UI and animation skills are unrelated. No grading
pipeline implementation changed, so no grading-engineer work was needed.
Workflows, `core/qa.py` and HF upload scripts are untouched, so no
extreme-reasoner scope was created.

## Prior Result: #624 V2 Pre-Execution Capture

[#624](https://github.com/hyeonsangjeon/gdpval-realworks/pull/624) added V2
pre-provider capture, immediate verification and run-record linkage.
Reviewed implementation `15cf7045c53dd9413fee8783b972654a7735d934` received
`APPROVE` after a producer/materializer path correction. Its final targeted
result was `73 passed in 57.65s`. Those are prior facts, not a rerun or
live-consumption evidence from this task.
