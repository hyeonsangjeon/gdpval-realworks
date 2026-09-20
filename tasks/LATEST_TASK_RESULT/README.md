# Latest Task Result

- Updated: 2026-09-20 (UTC)

## Current Task: Foundry GPT-5.6 Sol Codex Pilot Contract

### Scope and Outcome

The active next-model pilot now requests **Azure AI Foundry GPT-5.6 Sol through
Codex**, following the owner's provider correction. It does not request
GitHub Copilot, Sol Fast, Astra or a personal OpenAI account. The new plan is
`batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`,
with the sole active run ID `gpt56_sol_foundry_codex_pilot5_v1`.

The old `gpt56_sol_copilot_codex_pilot.yaml` retains its original identity,
controls and source pins. It now has `status: superseded`, a `superseded_by`
link and its existing disabled launch/full-run flags. The checker rejects it
even when passed explicitly through `--plan`. The separate GHCP Codex GPT-5.6
Sol VM TODO was not changed.

The new contract reuses the existing `azure` / `codex_foundry` / `direct-v1`
route, `endpoint_from_route: true`, `gdpval-foundry` provider and
`core.codex_azure_token` Entra helper. OIDC or a repository-approved Foundry
credential route is required for eventual execution. No endpoint or credential
value is committed, and no auth bridge or fallback is added. The explicit
client requests remain:

```toml
model_reasoning_effort="max"
model_context_window=1000000
```

These values do not prove a served model/version, Max capability or Long 1M
entitlement. The externally supplied account, project, deployment and reviewed
identity/capability evidence remain null. The request label is not a deployment
name. Native call/input/output token limits also remain null, not zero.

The checker retains both `launch_allowed: false` and `full_220_allowed: false`,
always exits 2 for a parsed valid or invalid registration, and cannot dispatch
a paid run. Active source-pin checks in the GPT-5.4 tests now read the Foundry
plan. The new 23-file source set includes the shared parser, this checker,
catalog/selection and seal helpers, Azure route/token helpers, dependency
manifest, baseline/grader/result contracts and the retired Copilot record.
The original Copilot source map is not refreshed.

### Fixed Five-Task Pilot

The unchanged `advance_check_5` order is:

1. `02aa1805-c658-4069-8a6a-02dec146063a`
2. `0112fc9b-c3b2-4084-8993-5a4abb1f54f1`
3. `2ea2e5b5-257f-42e6-a7dc-93763f28b19d`
4. `3baa0009-5a60-4ae8-ae99-4955cb328ff3`
5. `0818571f-5ff7-4d39-9d2c-ced5ae44299e`

Prompt/reference and parquet/catalog fingerprints, the dataset revision and
developer instruction are unchanged. One pilot retains fresh sessions, the
1,800-second attempt limit, three infrastructure retries, one logical turn,
zero provider request/stream retries, and no relay, resume or Self-QA. It does
not measure within-condition spread or automatically expand to 220 tasks.

Grading retains its existing template, source revision
`6ccd4ae346d302e3da0af455a3c5a72ec79a6984`, rubric revision, `v2.2` prompt,
Sol/Max judge and one pass. The historical full-run inference identity is not
reused. Deliverables/results retain `project_result_row`, grade schema `1.4`
and `cost-receipt-v1`. Unknown usage or price remains null/partial with its
reason under the record-only policy. Neither a requested deployment name nor
the existing cost adapter proves the served identity or a verified tariff.

A future pass permits leader review of all five tasks' identity, deliverable,
grading and usage evidence, followed by a separate full-run gate. Failure or
unverifiable identity stops progression and preserves the failed/partial rows.
This is a configuration pilot, not a model-only performance comparison.

### Immutable Base and Changed Files

The clean development branch
`b/gpt56-foundry-codex-pilot-contract-20260920` starts from immutable main
`5cbbe3d90d491fde71c268629bdeacc8917ad937`. The preservation checkout
`wip/local-main-preserved-20260719` was not used as a work branch or edited.
Existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was retained without changing Git
configuration, bypassing hooks or adding attribution trailers.

This task changes 13 files:

- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_codex_input_capture.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/tests/test_gpt54_prepared_input_attestation.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `batch-runner/tests/test_gpt54_workflow_gate.py`
- `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The six GPT-5.4 test files change only the active Sol plan path. No production
runtime/grader code, workflow, `core/qa.py`, HF upload script, historical result
or ledger bytes were changed. The GPT-5.4 four-run ABBA contract is unchanged.

### Exact Validation Evidence

Only this targeted selector ran, exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py::test_gpt56_sol_foundry_pilot_is_pinned_and_fails_closed
```

Result: `1 failed, 95 passed in 29.78s`, exit 1, with 96 cases collected on
Python `3.10.12`. The single failure was an overbroad assertion looking for
`copilot` anywhere in generated config values. The actual Foundry auth argv
includes this development checkout's `/ai-work/copilot/...` path, so the test
mistook a directory name for a provider/auth choice.

Before the implementation commit, that assertion was corrected to check the
exact `gdpval-foundry` provider ID and provider-key prefix, retain the exact
auth module/scope checks, and reject API-key/environment-key controls. The
selector was not rerun under the owner's one-invocation limit. This record
does not claim 96 passes or passing local validation of the corrected HEAD.
Automatic CI must still establish that result.

The cases use the real plan parser, catalog selector, configuration validator,
Foundry endpoint validator and Codex override serializer. Subprocess, network,
credential and Azure/provider client construction are forbidden by the fixture;
live sign-in discovery is replaced with an empty fake surface. The suite covers
identity/control drift, source-pin removal/digest drift, historical retirement,
duplicate active registrations and unchanged fixed task/grader/result contracts.

`git diff --check` passed before the implementation commit. No broad suite,
build, second selector invocation, manual workflow run, Azure API/CLI,
credential/token lookup, deployment creation, dataset download, model/grader/VM
call, actual pilot/full benchmark, paid execution, Project edit or merge was
performed.

### Immutable Review Boundary

`first-reviewer` returned `APPROVE` on implementation HEAD
`9941a2c611a0d1cc83053dd1000e07e1b972b210` against immutable base
`5cbbe3d90d491fde71c268629bdeacc8917ad937`, with no BLOCK, MAJOR or MINOR
findings and no second-review escalation. The 11-file reviewed diff includes
the assertion correction. The reviewer confirmed that the corrected predicates
agree with the actual override builder by static inspection, but explicitly
did not claim a passing selector. No tests, project imports, network calls or
mutations were performed during review.

Only the changelog and this record follow the implementation commit. Review
approval does not establish passing CI, served capability or launch permission.

### Skills and Roles

The complete supplied skill catalog and repository role catalog were inspected
once. `experiment-design` was invoked before configuration. It kept the fixed
cohort, decision/stop rules, record-only cost policy and the distinction between
requested and served capabilities explicit. It also records the moving axes
against the historical baseline, lack of repeat evidence, Sol judge/solver
shared-bias caveat, and the limit on transferring account-specific claims.

`llm-systems-engineer` performed a read-only contract review of the existing
Foundry route, auth, deployment naming and receipt boundaries. `first-reviewer`
provided the immutable code review using the available runtime. `im-not-ai-en`
applies to the English specification, changelog, completion record and PR text,
preserving IDs, hashes, commands, counts, timing and the failed-test evidence.

`extreme-reasoner` does not apply because no workflow, `core/qa.py` or HF upload
code changes. No grading-pipeline implementation or grader role is needed.
UI/animation skills do not apply to this offline experiment contract.
Experiment-report skills do not apply to software-test evidence; no model
benchmark result was produced.

### Remaining Work and Evidence Limits

The existing provider path is available in code; it is not live deployment
evidence. The active Foundry pilot remains blocked on:

- Externally supplied and reviewed account/project/deployment identity and
  served Sol model/version, with no Fast, Copilot or personal OpenAI substitute.
- Verified Max and requested 1M capability for that deployment, and enforced
  native call/input/output token caps.
- Actual staged input bytes, pilot dispatch/grading and external inference
  identity approval, without reusing a historical full-run identity.
- A verified native sandbox/result-bundle host and actual pilot deployment.
- Foundry usage and deployment/tier tariff receipt mapping. Unknown or partial
  usage, cache-write/audio gaps and native-call reachability stay explicit.
- Passing validation of the corrected implementation and leader review of the
  exact configuration/source HEAD before any execution work.

Copilot auth handoff is not a blocker for this Foundry contract. The separate
GHCP VM TODO is not implemented here. No compliant paid launch command exists
from this contract alone, and both launch flags remain false. No future merge
SHA, time or outcome is recorded.
