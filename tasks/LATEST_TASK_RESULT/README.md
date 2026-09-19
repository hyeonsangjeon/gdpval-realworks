# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Runtime Checkout Lineage Gate

### Scope and Outcome

Both registered comparison runtimes now verify the prepared checkout's local
lineage before provider, auth or client construction. Sandbox V2 also verifies
it before the free voice-safety preflight. The in-place helper reuses the
preparer's ready/reservation contracts and existing config/input validators;
it does not require the preparer's external source worktree path.

Work started from immutable main
`f89f8487f914b484e41431a22b2cb58508f74f20` in the separate development branch
`b/gpt54-runtime-checkout-lineage-gate-20260919`. The preservation checkout and
prior worktrees were not used for edits. The existing Git author and committer
identity, `hyeonsangjeon <wingnut0310@gmail.com>`, was retained without changing
Git configuration, bypassing development commit hooks or adding trailers.

Exactly thirteen files differ from the immutable base:

- `batch-runner/gpt54_disposable_checkout.py`
- `batch-runner/gpt54_codex_input_capture.py`
- `batch-runner/gpt54_v2_input_capture.py`
- `batch-runner/step2_run_inference.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_runtime_checkout.py`
- `batch-runner/tests/test_gpt54_codex_input_capture.py`
- `batch-runner/tests/test_gpt54_v2_input_capture.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Runtime Contract

`verify_runtime_checkout` checks canonical checkout-ready bytes, the full
reviewed commit/tree SHA, raw detached HEAD, bidirectional linked-worktree
registration, the exact sibling reservation and quarantine absence. It
reconstructs run/condition/repeat/ABBA and bundle identities from the existing
compiled plan and marker contracts. Existing validators check all 31 pinned
source files, generated configs and local input bytes. Marker, registration
and HEAD checks are repeated before the gate returns.

The gate uses only bounded local `rev-parse` calls with the existing fixed
environment, hook suppression and network/lazy-fetch refusal. It does not
inherit caller credentials, invoke the external-source verifier, publish files
or repair a checkout. Unsafe paths, links, missing or changed markers, attached
or moving HEAD, wrong run/condition and quarantine fail closed.

All four registered IDs require controls, including an ID passed to the wrong
harness. Non-comparison absent/null paths retain their existing serialization
and order. The two earlier non-Git capture fixtures use a labelled double only
for the new outer lineage boundary; their config/input/capture validators
remain real. The new selector exercises real lineage and both real runtime
entrypoints in temporary Git fixtures. Preflight evidence and directly coupled
source pins are updated; the source count remains 31.

This is evidence of local lineage and pinned-byte consistency, not approval of
external review or inference identity, served capability, wire equality or
launch. It does not scan unrelated tracked files with `status` or prevent
arbitrary concurrent filesystem writes. Production grader/runtime defaults,
ABBA, model/effort, task cohort, limits, receipt policy and historical evidence
are unchanged.

### Exact Validation Evidence

The following selector was invoked exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers
```

Result: `50 passed in 69.18s (0:01:09)`, exit 0.

The cases cover four ABBA successes; wrong, attached and moving HEAD;
missing/altered ready, reservation, config and input markers; noncanonical
ready bytes; altered member bytes; quarantine; wrong run/condition; links and
path traversal; legacy absent/null controls; and stripped opposite-harness
IDs. Successes stop at sentinels before Codex auth and V2 free safety, while
refusals do not reach those sentinels. Runtime Git is restricted to the five
expected `rev-parse` forms. Network, provider, model, grader and VM guards
recorded no calls. Caller-source and input-oracle snapshots stayed unchanged.

`git diff --check f89f8487f914b484e41431a22b2cb58508f74f20 HEAD` passed on the
implementation commit. Read-only digest inspection matched all comparison and
directly coupled Sol source pins. No broad suite, build, live execution-checkout
preparation, inference, grading, Azure/HF access, download, paid execution,
workflow dispatch, Project edit or merge was performed. Workflow files,
`core/qa.py` and HF upload code are unchanged.

### Immutable Review Boundary

Implementation HEAD `0028ab2dde3b8ffea4501883d47a92cf70031b23` received a fresh
read-only `first-reviewer` review covering
`f89f8487f914b484e41431a22b2cb58508f74f20..0028ab2dde3b8ffea4501883d47a92cf70031b23`.
The verdict was `APPROVE`, with no BLOCK, MAJOR or MINOR findings and no
second-review escalation. Independent read-only hashing confirmed all 31
comparison pins and both refreshed Sol pins. The reviewer ran no tests or
project code. This is static code review, not launch authorization or proof of
external inference identity or whole-target grader provenance.

Only `CHANGELOG.md` and this record follow the reviewed implementation HEAD
and are outside that review boundary. Leader review and fresh automatic CI
remain required. No carrying-PR merge result, future merge SHA/time or
execution authorization is claimed.

### Remaining Work

The fixed five-task cohort and V2 r1 → Codex r1 → Codex r2 → V2 r2 order are
unchanged, as are Foundry GPT-5.4/xhigh requests and null/partial record-only
cost semantics. `launch_allowed` and `full_220_allowed` remain false. The study
remains a configuration-bundle comparison.

- Leader review and fresh automatic CI for this change.
- External inference publication identity issuance and approval.
- A host supporting native no-clobber result-bundle installation.
- Actual workflow deployment and the workflow execution gate.
- Served deployment/model/effort capability and native call/token caps.
- Actual wire-request consumption and usage/tariff evidence.
- The separate Sol pilot's GitHub Copilot provider/auth route, still blocked
  by the missing official runtime handoff contract.

### Skills and Roles

The full skill and repository-agent catalogs were inspected once before
editing. `experiment-design` kept the comparison axes, evidence limits and
stop gates fixed. The `llm-systems-engineer` role supplied the focused offline
selector and bounded fixture changes. `first-reviewer` supplied the fresh
immutable review. `im-not-ai-en` was applied to the English changelog,
completion record and PR wording, preserving commands, SHAs, counts and
qualifications.

Experiment-report skills were not used because this is software validation,
not benchmark-result analysis. No grading implementation changed, so the
grading-engineer role was not needed. Workflows, core QA and HF upload are
untouched, so extreme-reasoner does not apply. Repository-readiness, UI and
animation skills are unrelated to this runtime gate.

## Prior Result: #627 Disposable Checkout Preparer

The preparer creates one reviewed detached checkout, seals its config/input
bundles and retains reservation/quarantine evidence after failure. The leader
reported green checks and `FINAL-APPROVE` at
`f5f55e226cc0643e8346857a5b18da1cf327f706`, then squash merge as
`f89f8487f914b484e41431a22b2cb58508f74f20`. These are supplied prior facts, not
a fresh CI query in this task. The prior record's original local result was
`14 failed, 28 passed in 9.94s` before its Git metadata compatibility correction;
that selector was not rerun here. The present gate adds runtime enforcement
without turning preparation markers into launch authorization.
