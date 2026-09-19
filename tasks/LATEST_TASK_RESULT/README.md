# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Sandbox V2 Pre-Execution Capture Wiring

### Scope and Outcome

The comparison's V2 r1/r2 path now builds and immediately verifies the existing
`gpt54-pre-execution-input-v1` contract before the free voice-safety preflight
and provider, auth, model voice or client construction. It binds actual
plan/parquet/reference bytes to the `TaskToRun` objects handed to the driver.
The run record carries the verified capture digest and attestation linkage.
This is local input evidence, not launch authorization.

Work started from immutable main
`871e138558c3ada8d9c3cd93de2b07b676faeab9` in branch
`b/gpt54-v2-preexec-capture-wiring-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-v2-preexec-capture-wiring-20260919`.
The preservation checkout and prior worktrees were not used for edits. The
existing Git identity was retained without configuration changes, attribution
trailers or disabled hooks.

Exactly fifteen files differ from the base:

- `batch-runner/gpt54_v2_input_capture.py`
- `batch-runner/gpt54_prepared_input_attestation.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/scripts/run_agentic_v2_stage.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_v2_input_capture.py`
- `batch-runner/tests/test_gpt54_codex_input_capture.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_prepared_input_attestation.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Binding and Compatibility

Only the generated V2 comparison plans receive the typed
`comparison_input_capture` control. Its sole field is `binding_version`, so
both V2 config byte sequences remain identical. Explicit registered
`--run-id` values select r1 or r2. Reserved IDs require the control even if
it is removed or null. A control without a registered explicit V2 ID refuses.

The runtime and attester share the source snapshot and exact V2 consumer
projection. They reuse the catalog selector, compiled dispatch/grading plans,
source fingerprints and verified reference readers. All 28 source pins are
bound. The fresh snapshot must match the actual held plan and bound tasks,
not a replacement set created solely to pass validation. Config, plan,
task/order, parquet, reference and pin drift, changed captures, symlinks,
path escapes and hardlinks are refused.

Paths use the compiled run-relative roles or their exact checkout locations;
host absolute paths are not capture identity. Other stages, all shards,
dry-run, rehearsal and isolation overrides are refused. A workspace with any
existing file or directory refuses implicit journal/ledger resume even if
an earlier capture was removed.

The unchanged #623 writer publishes a complete, fsynced temporary file using
an atomic no-replace link under a held parent descriptor. Existing files are
not overwritten; temporary links are cleaned up. Immediate verification
rereads sources, compares held tasks and checks published bytes/size/SHA256.
A later refusal may leave a complete capture, but no provider is reached and
a retry cannot overwrite it. This single-file primitive does not replace
the materializers' native directory `RENAME_NOREPLACE` requirement.

`request_conditions.pre_execution_input_capture` contains the verified path,
size, SHA256 and run/condition/repeat, manifest, combined-plan, source-pin,
config and ordered-source-projection linkage. A later four-run attester can
match its `binding_file`. This path does not invent an overall attestation
digest or issue an inference identity. The existing materializer's
working-directory-relative `plan_file.path` stays `comparison-run.json` with
the verified config SHA; it is distinct from the capture's checkout-relative
path. Materializer validation is unchanged.

Legacy absent/null controls add no capture reads, writes or record fields.
The original load, preflight and binding sequence is retained. The fixture
checks unchanged request fields, unattached record serialization and event
order with capture helpers forbidden. Codex's capture module, Step 1,
Step 2 and production core code remain byte-identical to the base. The Sol
manifest only refreshes the shared parser pin; no provider route changes.

### Exact Verification Evidence

The only pytest selector used was:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_v2_input_capture.py::test_v2_comparison_capture_gates_stage_before_provider
```

The initial invocation reported **73 passed in 57.82s**, exit 0. Immutable
review then identified one blocking producer/materializer path mismatch.
After correcting the path, its contract assertion, source pin and specification,
the same command ran once more as authorized: **73 passed in 57.65s**, exit 0.
`git diff --check` passed. No other selector or suite was run, and no further
test execution is planned in this unit.

The small five-row fixture exercises the real V2 CLI, capture writer,
immediate verifier, source/catalog/reference helpers and offline attester.
It covers both repeats, relative argv, new workspaces, defaults, byte/control
and held-object drift, stage/shard/run-ID overrides, implicit resume, unsafe
paths, collisions and atomic-publication failures. Actual record-attachment
and serialization statements run without executing tasks. The same selector
invokes only three existing Codex cases: r1, r2 and default absent/null
behavior, not the previous 77-case selector.

Accepted cases stop at a fake auth boundary before construction. Rejected
cases reach neither the free preflight nor backend/provider setup. Free
preflight safety probes are replaced by a fixture verdict to avoid creating
voices/backends. Network, subprocess, auth, model/grader/client/VM construction
and downloads are guarded against. This is not verification of the production
dataset, inference or a benchmark result.

Existing coupled tests only update pin counts and were not separately rerun.
Grading code, schemas, workflows, `core/qa.py`, HF upload scripts, historical
ledgers and sealed evidence are unchanged. No live credentials, paid execution,
workflow dispatch, Project edits or merge were performed.

### Immutable Review Boundary

The first review of implementation HEAD
`2cacd941859aab68428e43396f958c6e71fd7f5f` returned `REQUEST-CHANGES` for one
blocking path mismatch. The producer used a checkout-relative plan path while
the existing V2 materializer requires a working-directory-relative path.
The correction preserves the consumer contract and adds the missing assertion.
Corrected implementation HEAD `15cf7045c53dd9413fee8783b972654a7735d934`
received `APPROVE`, with no remaining BLOCK, MAJOR or MINOR findings and no
second-review escalation. The reviewer combined the prior full review with
the four-file correction delta and did not rerun tests or execute runtime,
network or authentication paths.
Only this record and `CHANGELOG.md` follow the implementation HEAD and are
outside that review boundary. Leader review and automatic CI evidence remain
required; no carrying-PR merge result, future merge SHA/time or launch
readiness is claimed.

### Remaining Work

The fixed five-task cohort, ABBA order, two repeats per condition, Foundry
GPT-5.4/xhigh requests, limits, grading and null/partial receipt contracts
remain unchanged. `launch_allowed` and `full_220_allowed` remain false.

- External inference identity issuance and approval.
- A host with native no-clobber bundle installation support.
- Actual checkout/config materialization and workflow gates.
- Served deployment/model/effort capability and native call/token caps.
- Later staged consumption and rendered/wire-request evidence. The capture
  binds the local snapshot and held tasks, not later requests.
- Usage/tariff evidence under the existing record-only null/partial policy.
- The separate Sol pilot's GitHub Copilot provider/auth route, blocked by the
  missing official runtime handoff contract.

The study remains a configuration-bundle comparison. A passing fixture or
capture does not prove environment-only causality or authorize execution.

### Skills and Roles

The full available skill and repository-agent catalogs were inspected once
before editing. `experiment-design` preserved the input contract, repeats,
configuration-bundle interpretation and stop gates. The required
`llm-systems-engineer` role mapped construction boundaries read-only. Its
finding that free preflight constructs safety fixtures placed this gate
before the entire preflight. `first-reviewer` reviewed both immutable
implementation heads read-only.

`im-not-ai-en` was applied to English changelog, completion-record and PR
wording. Commands, SHAs, counts, results and qualifications were checked
manually to honor the selector limit instead of running an extra fidelity
script. Experiment-report skills do not apply to software verification.
Repository-readiness, UI and animation skills are unrelated. No grading
pipeline code changed, so no grading-engineer implementation was needed.
Workflows, `core/qa.py` and HF upload scripts are untouched, so no
extreme-reasoner scope was created.

## Prior Result: #623 Codex Pre-Execution Capture

[#623](https://github.com/hyeonsangjeon/gdpval-realworks/pull/623) added the
Codex Step 1 capture and Step 2 pre-provider check. Reviewed implementation
`aeed86d3c416128675d6263c088301eed3e77b95` received `APPROVE`; after a package
import correction, its targeted selector reported `77 passed in 94.30s`.
Those are prior facts, not a rerun of that selector or live-consumption
evidence from this task.
