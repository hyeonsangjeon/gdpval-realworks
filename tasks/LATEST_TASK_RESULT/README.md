# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Disposable Checkout Preparer

### Scope and Outcome

The comparison has a local-only library and CLI for preparing one detached
disposable checkout at a caller-supplied, externally reviewed commit. It
validates the exact run recipe and reviewed source bytes, creates the checkout
with `git worktree add --detach`, and invokes the existing config and input
bundle materializers in that order. A checkout-ready marker binds the reviewed
commit, tree, run identity and both verified bundles. This implements checkout
creation and local bundle placement only. Validation of the corrected positive
path remains pending; no launch readiness is claimed.

Work started from immutable main
`474f5855283a9b4e47b81821f3bc59e9b7fedde4` in branch
`b/gpt54-disposable-checkout-preparer-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-disposable-checkout-preparer-20260919`.
The development worktree is separate from the preservation checkout and prior
worktrees. The preparer was invoked only in temporary Git fixtures, never
against the live repository. The existing Git author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was retained without changing Git
configuration or bypassing development commit hooks. No attribution trailers
were added.

Exactly fifteen files differ from the immutable base:

- `batch-runner/gpt54_disposable_checkout.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_disposable_checkout.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `batch-runner/tests/test_gpt54_codex_input_capture.py`
- `batch-runner/tests/test_gpt54_v2_input_capture.py`
- `batch-runner/tests/test_gpt54_prepared_input_attestation.py`
- `batch-runner/tests/test_gpt54_run_input_bundle.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Preparation and Failure Contract

The preparer requires a local repository sharing the trusted compiler's Git
common directory, an exact typed dispatch recipe, the manifest and combined
grading plan, pinned local parquet/reference inputs and an absent destination.
The source revision must be a full lowercase 40-hex commit SHA supplied by the
caller. Refs, abbreviated SHAs, non-commit objects and the manifest's historical
`source_base_sha` are not substitutes for external review. The tool does not
issue or verify the external review decision itself.

Before reservation, it checks source pins against reviewed commit blobs rather
than dirty source working files. It checks the exact plan, input snapshot,
tracked file modes, target absence and source/target separation. Links,
path traversal, existing sidecars and generated targets are refused. Only local
Git subprocesses are used, with a fixed environment and no hooks, filters,
network transport, lazy fetch or inherited authentication route. The caller's
source working tree, refs, index and configuration are not rewritten.

A no-clobber sidecar reservation precedes exclusive destination creation and
the detached Git worktree operation. Before publishing bundles, the preparer
checks detached HEAD, exact commit, bidirectional worktree registration, clean
tracked files and all 31 source pins. The unchanged materializers publish the
exact config bundle, pinned parquet and only the five-task reference set.
After verifying both bundles, the preparer publishes
`comparison-checkout-ready.json` last and rechecks HEAD, markers and file bytes.
The marker uses run-relative roles and contains no launch or external inference
identity approval.

On failure after reservation, the preparer retains remaining paths and attempts
to publish a quarantine sidecar. It reports the checkout, reservation and
quarantine paths, including whether each remains and whether quarantine could
be written. A reservation or quarantine prevents a later preparer invocation
from adopting or overwriting the destination. Quarantine also makes the checkout
verifier refuse a ready marker if final verification failed after publication.
There is no cleanup or retry path. This does not promise a multi-file
transaction, crash durability or a filesystem security sandbox.

Existing V2/Codex capture code is unchanged. Its config/input marker checks do
not by themselves enforce the new checkout lineage or quarantine sidecar;
integration with the execution workflow gate remains outstanding. Relative
linked-worktree metadata is unsupported and fails closed. The historical
manifest base and grader revision remain
`a855c5a9604554499be9eed4e5eb5523e8ad95d5`, distinct from the development base
and the source SHA a caller must have reviewed.

### Exact Validation Evidence

The following selector was invoked exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_disposable_checkout.py::test_disposable_checkout_is_reviewed_local_and_quarantines_failures
```

Result: `14 failed, 28 passed in 9.94s` across 42 collected cases, exit 1.
Git 2.34.1 rejected `git worktree list --porcelain -z`. Positive paths and
failure-injection cases that depended on that step stopped at registration
verification. This was not a passing selector, and later positive-path
assertions were not reached.

The implementation now uses `git rev-parse --absolute-git-dir` and exact,
single-link reads of the checkout's `.git` file and the registered `gitdir` and
`commondir` files. Read-only inspection of an existing temporary fixture
confirmed that metadata format. The corrected code has not been rerun locally,
to preserve the one-invocation limit. Fresh passing CI evidence is still
required. No Git manual was available locally; no fresh documentation check or
passing regression result is attributed to the metadata inspection.

The new selector contains four ABBA success recipes plus refusal and failure
cases for source SHA, plan and pin drift, dirty or attached targets, collisions,
links, changed bundles and partial quarantine. It reuses the immutable cached
input fixture and real materializers/validators. Its subprocess guards permit
only bounded Git operations in temporary repositories and forbid network,
provider, authentication, model and grader calls. These are coverage intentions,
not a claim that all 42 cases passed.

`git diff --check 474f5855283a9b4e47b81821f3bc59e9b7fedde4 HEAD` passed on the
implementation commit. No broad suite, build, download, actual inference,
grading, paid execution, workflow dispatch, Project edit or merge was performed.
Workflow files, `core/qa.py`, HF upload code, production capture/grader defaults
and historical ledger/evidence bytes are unchanged.

### Immutable Review Boundary

Implementation HEAD `b7f2d04de4082889950718c33fffcd6c1a1d9fcf` contains the code,
tests, pins, specification and Git compatibility correction. A fresh read-only
`first-reviewer` review covered
`474f5855283a9b4e47b81821f3bc59e9b7fedde4..b7f2d04de4082889950718c33fffcd6c1a1d9fcf`.
The verdict was `APPROVE`, with no BLOCK, MAJOR or MINOR findings and no
second-review escalation. The reviewer confirmed that all 31 source pins
match this immutable HEAD without running tests or project code. This is a
static code-review verdict, not passing validation or launch authorization.
Only `CHANGELOG.md` and this record follow the reviewed implementation HEAD
and are outside that review boundary. Leader review and fresh passing CI
remain required. No carrying-PR merge result, future merge SHA/time or
execution authorization is claimed.

### Remaining Work

The fixed five-task cohort, V2 r1 → Codex r1 → Codex r2 → V2 r2 order,
Foundry GPT-5.4/xhigh requests, limits, grading and null/partial record-only
cost contracts are unchanged. `launch_allowed` and `full_220_allowed` remain
false. The study remains a configuration-bundle comparison.

- Fresh passing validation of the corrected implementation and leader review.
- External inference publication identity issuance and approval.
- A host supporting native no-clobber result-bundle installation.
- Actual reviewed-host deployment and the workflow gate, including checkout
  lineage and quarantine enforcement.
- Served deployment/model/effort capability and native call/token caps.
- Actual rendered/wire-request consumption and usage/tariff evidence.
- The separate Sol pilot's GitHub Copilot provider/auth route, still blocked
  by the missing official runtime handoff contract.

No marker authorizes a model, grader or 220-task run. Preparation does not
establish served capabilities, wire-prompt equality or environment-only
causality.

### Skills and Roles

The full skill and repository-agent catalogs were inspected once before
editing. `experiment-design` preserved the fixed comparison contract, evidence
limits and stop gates. The `llm-systems-engineer` role supplied the bounded
offline fixture and audited Git registration metadata. `first-reviewer` supplied
the fresh immutable read-only review. `im-not-ai-en` was applied to the English
changelog, completion record and PR wording without changing commands, SHAs,
counts or qualifications.

Experiment-report skills were not used because this task validates software;
it does not analyze benchmark results. No grading pipeline implementation changed, so no
grading-engineer work was needed. Workflow, core QA and HF upload files are
untouched, so no extreme-reasoner scope was created. Repository-readiness, UI
and animation skills are unrelated to this local preparer.

## Prior Result: #626 Run Input Bundle Materializer

[#626](https://github.com/hyeonsangjeon/gdpval-realworks/pull/626) added pinned
five-task input publication and runtime verification of both config and input
bundles. Its final PR HEAD was
`a5d12efea791d6216ebf6974ba522d67ec0fe57a`. The original selector reported
`116 passed in 327.95s`; Backend Tests was then cancelled at 91% by its
45-minute timeout without a reported test failure. The test-fixture correction
reported `116 passed in 42.46s`, with all 116 cases retained. Its reviewed
correction implementation was `4a05e26debacdbd5cea8df6d915a40175064998f`.
Those results are prior-task evidence, not validation of this preparer.
