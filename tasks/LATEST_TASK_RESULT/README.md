# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Workflow Execution Gate

### Scope and Outcome

Both owning workflows route registered or partially specified GPT-5.4
comparison requests into a separate admission job. That job has read-only
repository permissions, no provider secrets and no OIDC grant. It binds an
explicit caller-reviewed source SHA to the workflow/event commit before
checkout, then uses the existing disposable-checkout preparer and in-place
lineage verifier. The helper returns exact compiled command tuples and a cwd
inside the prepared checkout; it does not execute them. The mandatory launch
check still refuses execution.

Work started from immutable main
`1671d6d87c27894d6b1a4d75ee5e7be21170feaa` in the separate development branch
`b/gpt54-workflow-execution-gate-20260919`. The preservation checkout and prior
worktrees were not used for edits. Existing Git author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was retained without changing Git
configuration, bypassing commit hooks or adding trailers.

Exactly 21 files differ from the immutable base:

- `.github/workflows/agentic-v2-stage-run.yml`
- `.github/workflows/batch-run.yml`
- `batch-runner/gpt54_workflow_gate.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_workflow_gate.py`
- `batch-runner/tests/test_agentic_workflows.py`
- `batch-runner/tests/test_a_batch_dispatch_can_open_the_codex_gate.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_disposable_checkout.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `batch-runner/tests/test_gpt54_prepared_input_attestation.py`
- `batch-runner/tests/test_gpt54_codex_input_capture.py`
- `batch-runner/tests/test_gpt54_v2_input_capture.py`
- `batch-runner/tests/test_gpt54_run_input_bundle.py`
- `batch-runner/tests/test_gpt54_runtime_checkout.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Admission and Refusal Contract

The new optional `comparison_reviewed_source_sha` defaults to an empty string.
Registered IDs, comparison config names or an explicit review control cannot
enter the legacy V2 free/paid/collect or batch credentialed lanes. The comparison
jobs accept only a `workflow_dispatch` on `refs/heads/main`, with an explicit
lowercase full SHA equal to the event and workflow SHA. Neither `github.sha`,
`github.workflow_sha` nor the batch relay's `source_sha` supplies external review
approval. Checkout uses the explicit input and disables credential persistence.

Typed requests require exact owner-specific inputs, run identity and defaults.
The helper checks the source checkout and 34 pinned files, then calls the
real preparer and runtime verifier. It reuses ready/reservation/config/input
marker contracts, detached HEAD checks, exact run/condition/repeat/ABBA identity
and quarantine rules. Changed argv or a cwd in the original source checkout
is refused. Failed preparation is retained; failure after preparation triggers
best-effort no-clobber quarantine under the held parent, with publication status
reported. Normal refusal of false launch flags does not quarantine a valid
prepared checkout. There is no cleanup or reuse path.

The CLI prints local preparation evidence with `commands_executed: false`, then
returns exit 2 at the mandatory launch check. No execution, prepare-only or
launch-override path was added. Both `launch_allowed` and `full_220_allowed`
remain false. Existing input defaults and ordinary workflow step bodies are
unchanged, apart from relay forwarding of the new empty input. The comparison
source set grows from 31 to 34 pins; directly coupled count assertions and the
Sol parser pin are updated. Production runtime/grader code, ABBA, model/effort,
task cohort, limits, record-only null/partial cost semantics and historical
evidence are unchanged.

### Exact Validation Evidence

The following selector was invoked exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_workflow_gate.py::test_workflow_execution_gate
```

Result: `64 passed in 80.13s (0:01:20)`, exit 0.

The cases cover both workflow YAML contracts, four ABBA preparations, exact CLI
bindings, owner/default/SHA refusals, collisions, unsafe paths and links, changed
source pins, attached/wrong/moving HEAD, missing or altered markers, quarantine,
changed argv/cwd, attempted launch-flag changes, preparation/handoff failures
and rerun refusal. Post-preparation mutations exercise the lineage verifier,
not merely the always-refusing launch check. The two repeat cases exercising
the real CLI report evidence and exit 2 without dispatch.

Canonical ordinary input/step projections match the immutable base, normalizing
only the added empty relay forwarding line. Existing immutable fixture caches
bound preparation cost without replacing validators. Temporary Git repositories
exercise the real preparer and runtime verifier; subprocess guards allow only
bounded local Git. Network, auth, provider, model, grader and VM guards recorded
no calls. Both workflow jobs explicitly omit provider secrets and OIDC access.

`git diff --check 1671d6d87c27894d6b1a4d75ee5e7be21170feaa HEAD` passed on the
implementation commit. No broad suite, build, live execution-checkout
preparation, workflow dispatch, Azure/HF access, download, credential lookup,
inference, grading, paid execution, Project edit or merge was performed.
`grade-run`, unrelated workflows, `core/qa.py` and HF upload code are unchanged.

### Immutable Review Boundary

Implementation HEAD `d54df8aa4187070c261103271dd8d587639ec735` received a fresh
read-only `first-reviewer` review against base
`1671d6d87c27894d6b1a4d75ee5e7be21170feaa`. The verdict was `APPROVE`, with no
BLOCK, MAJOR or MINOR findings and no second-review escalation. The reviewer
ran no tests or project code and made no network or credential calls. Approval
covers offline admission/preparation/refusal, not deployment or paid execution.

Before workflow edits, the `extreme-reasoner` role returned
`APPROVE-WITH-CONDITIONS`: isolate comparison admission from provider secrets
and OIDC, bind explicit reviewed/event/workflow identity, reuse the existing
preparer and verifier, and keep launch false. Its later mutable design check
identified the outer-handoff quarantine gap; that was corrected before the
single selector invocation. The mutable check is not immutable code approval.

Only `CHANGELOG.md` and this record follow the implementation HEAD. Leader
review and fresh automatic CI remain required. No carrying-PR merge result,
future merge SHA/time or execution authorization is claimed.

### Evidence Limits and Remaining Work

This gate proves local workflow-request binding and prepared-checkout
consistency in offline fixtures. It does not issue external source review or
inference identity approval, prove served capability or wire equality, or grant
permission to launch. No workflow was run. The comparison jobs require pinned
parquet/reference bytes already on disk; a fresh hosted checkout without those
bytes refuses, and no download path was added. Actual workflow execution is not
implemented by the inert-command helper.

The fixed five-task cohort and V2 r1 → Codex r1 → Codex r2 → V2 r2 order remain
unchanged, as do Foundry GPT-5.4/xhigh requests. The study remains a
configuration-bundle comparison. Remaining gates are:

- Leader review and fresh automatic CI for this change.
- External inference publication identity issuance and approval.
- A host supporting native no-clobber result-bundle installation.
- Actual runner deployment, local pinned data provisioning and workflow execution.
- V2 same-host approval/capture compatibility at the actual execution boundary.
- Served deployment/model/effort capability and native call/token caps.
- Actual wire-request consumption/equality and usage/tariff evidence.
- The separate Sol pilot's GitHub Copilot provider/auth route, still blocked by
  the missing official runtime handoff contract.

### Skills and Roles

The full skill and repository-agent catalogs were inspected once before edits.
`experiment-design` kept comparison axes, evidence limits and stop gates fixed.
`extreme-reasoner` supplied the required pre-edit cost/security/CI decision and
bounded design check. `llm-systems-engineer` implemented the offline helper and
checked its API/test boundary. `first-reviewer` supplied the fresh immutable
implementation review. These are role reviews in the available runtime, not
claims that unavailable externally named models ran. `im-not-ai-en` was applied
to the English changelog, completion record and PR wording; commands, SHAs,
counts and qualifications were protected during copyediting.

Experiment-report skills do not apply because this is software validation,
not benchmark-result analysis. No grading implementation changed, so the
grading-engineer role was not needed. Repository-readiness, UI and animation
skills are unrelated to this workflow gate.

## Prior Result: #628 Runtime Checkout Lineage Gate

The prior unit added in-place checkout lineage verification before the V2 and
Codex provider boundaries. Its recorded local selector result was
`50 passed in 69.18s (0:01:09)`; that selector was not rerun here. This task starts
from supplied main `1671d6d87c27894d6b1a4d75ee5e7be21170feaa`, whose commit records
the #628 change. The present unit adds workflow admission without turning
preparation or runtime markers into launch authorization.
