# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Codex Pre-Execution Capture Wiring

### Scope and Outcome

The comparison's Codex r1/r2 path now records and verifies the existing
`gpt54-pre-execution-input-v1` contract. Step 1 builds the capture from actual
prepared/config/parquet/reference bytes. Step 2 recomputes it before provider,
auth, or client construction and requires exact canonical bytes, size, and
SHA256. This unit does not implement V2 capture or authorize execution.

Work started from immutable main
`e90040962aa16572a32c64808db93b38dceeefb9` in branch
`b/gpt54-codex-preexec-capture-wiring-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-codex-preexec-capture-wiring-20260919`.
The preservation checkout and prior worktrees were not used for edits.
The existing Git author/committer identity was retained without configuration
changes, attribution trailers, or disabled hooks.

Exactly sixteen files differ from the base:

- `batch-runner/core/experiment_config.py`
- `batch-runner/gpt54_codex_input_capture.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/gpt54_prepared_input_attestation.py`
- `batch-runner/step1_prepare_tasks.py`
- `batch-runner/step2_run_inference.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_codex_input_capture.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_prepared_input_attestation.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Binding, Compatibility, and Evidence Boundary

Only the generated GPT-5.4 Codex configs receive the typed
`execution.comparison_input_capture` control. The generated Step 2 command
also pins `--comparison-run-id`, so deleting or relabeling the prepared
opt-in cannot downgrade that command to the legacy path. Reserved comparison
IDs require the control. Runtime condition, mode, retry, resume, and timeout
overrides must match the fixed contract; checkpoint-only and resume paths
are refused before auth.

The runtime and offline attester share one source snapshot and capture
builder. They reuse the catalog selector, compiled dispatch/grading plan,
source projections, prepared fingerprint, and verified reference readers.
The capture binds 27 source pins and actual input bytes. Run-relative roles
identify the generated config, prepared JSON, and capture; host absolute
paths are not identity. The Sol manifest only refreshes directly coupled
shared-source digests. Its provider/auth route is unchanged.

Missing, extra, null, duplicate, noncanonical, or changed capture content;
config/prepared/parquet/reference/task/order/plan/pin drift; symlinks, path
escapes, and hardlinks are refused. Recomputing a prepared fingerprint or
forging a matching capture cannot excuse a source projection mismatch.
The safely reread prepared object must also match the object held by Step 2.
Existing reference staging retains its consumption-time byte checks.

Prepared JSON and capture files are each published through a private
temporary file and an atomic no-replace link under a held parent descriptor.
No existing file is overwritten. A rerun with a new publication generation
preserves an existing prepared/capture pair. The two-file operation is not
atomic as a pair: a later capture refusal can leave a complete prepared file
without a capture. Step 2 and a retry refuse that state. Temporary links are
cleaned up; there is no unsafe rename fallback. Single-file publication does
not remove the materializers' native directory no-clobber host requirement.

Final Step 2 results include `pre_execution_input_capture` before the result
fingerprint is computed. It carries the verified file SHA256 and linkage to
the run, manifest, combined plan, config, source pins, and ordered source
projection. It can be matched to a later attestation's `binding_file`.
It does not invent a four-run attestation digest or issue/approve an external
inference identity.

For genuine legacy experiments, absent/null controls cause no capture reads,
writes, or output fields. The ordinary prepared serializer and existing
provider request configuration remain unchanged. The targeted fixture proves
absent/null prepared-byte equality and the same pre-provider event order,
with capture helpers forbidden. Final-output attachment/fingerprint
statements are exercised without running inference; the absent case retains
the prior output shape.

This is evidence of local pre-execution input consistency. It does not prove
served deployment/model/effort capability, later rendered/wire-request
equality, or environment-only causality. The study remains a
configuration-bundle comparison.

### Exact Verification Evidence

The only pytest selector used was:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_codex_input_capture.py::test_codex_comparison_capture_gates_real_step1_and_step2
```

The initial invocation stopped at collection with `0 items / 1 error in 1.37s`
and exit 4. The new test used a bare sibling import that did not resolve from
the repository's test package. No cases ran. Immutable review identified
that import as the sole blocking finding.

After the package-relative import correction, the same command ran once
more, as authorized for review corrections: **77 passed in 94.30s**, exit 0.
No further selector or suite was run. `git diff --check` passed.

The small synthetic fixture uses the real Step 1 serializer, capture writer,
Step 2 entry gate, source/fingerprint/reference helpers, and offline attester.
It covers both Codex repeats, relocation, default no-op behavior, byte and
control drift, unsafe paths, collisions, atomic-publication failures, and
checkpoint/CLI refusals. Accepted runs stop at a fake auth boundary before
construction; rejected runs do not reach it. Subprocess, network, provider
auth, model/grader/client construction, and downloads are guarded against.
This is not a verification of the production dataset or an inference run.

The V2/Codex materializer tests only change their source-pin count and were
not rerun. The attester fixture still supplies independent captures while
using the real serializer. Production grader code, schemas, workflows,
`core/qa.py`, HF upload scripts, historical ledgers, and sealed evidence are
unchanged. No live credentials, paid execution, workflow dispatch, Project
edits, or merge were performed.

### Immutable Review Boundary

The first review of implementation HEAD
`b20dd15ef7cd3dba37a4a0656dfce40d45172ffb` returned `REQUEST-CHANGES` for the
test import only. Corrected implementation HEAD
`aeed86d3c416128675d6263c088301eed3e77b95` received `APPROVE`, with no remaining
BLOCK, MAJOR, or MINOR findings and no escalation requested. The reviewer
combined the full fourteen-file review with the exact one-line correction
delta and did not rerun tests or execute runtime/network/auth paths.

Only this record and `CHANGELOG.md` follow that reviewed implementation HEAD.
Approval excludes these completion records and all live execution gates.
Leader review and automatic CI evidence remain required. No carrying-PR
merge result, future merge SHA/time, or launch readiness is claimed.

### Remaining Work

The fixed five-task cohort, ABBA order, two repeats per condition, Foundry
GPT-5.4/xhigh requests, limits, grading, and result/receipt contracts remain
unchanged. `launch_allowed` and `full_220_allowed` remain false.

- External inference identity issuance and approval.
- V2 capture wiring and its connection to consumption time.
- A host with native no-clobber bundle installation support.
- Actual checkout/config materialization and workflow gates.
- Served deployment/model/effort capability and native call/token caps.
- Usage/tariff evidence under the existing record-only null/partial policy.
- The separate Sol pilot's GitHub Copilot provider/auth route, still blocked
  by the missing official runtime handoff contract.

### Skills and Roles

The full available skill and repository-agent catalogs were inspected once
before editing. `experiment-design` preserved the comparison's fixed inputs,
repeat matrix, configuration-bundle interpretation, evidence limits, and stop
gates. The required `llm-systems-engineer` role reviewed the backend contracts
and implementation read-only. Its pre-test audit found an overwrite risk on
a Step 1 rerun; no-clobber prepared publication and a generation-changing
collision regression addressed it before the implementation commit.
`first-reviewer` reviewed both immutable implementation heads read-only.
These roles used the available engine without an external paid model call.

`im-not-ai-en` was applied to English changelog, completion-record, and PR
wording. Commands, SHAs, counts, results, and qualifications were checked
manually to honor the targeted-selector limit instead of running an extra
fidelity script. Experiment-report skills do not apply to this software
verification record. Repository-readiness, UI, and animation skills are
unrelated to the input boundary. No grading pipeline code changed, so no
grading-engineer implementation was needed. Workflows, `core/qa.py`, and HF
upload scripts are untouched, so no extreme-reasoner scope was created.

## Prior Result: #622 Prepared-Input Attestation

[#622](https://github.com/hyeonsangjeon/gdpval-realworks/pull/622) added the
read-only four-run attestation compiler. Its reviewed implementation
`b4e4c9dfd7fa1384a3dca84469b677cefc874af0` received `APPROVE`; its one targeted
selector reported `86 passed in 49.43s`. Those are prior facts, not a test
rerun or a claim that V2 capture or live consumption was verified here.
