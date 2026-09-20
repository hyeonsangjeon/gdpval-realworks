# Latest substantive task result

## PROJECT5-GPT56-LIVE-WIRE-RECEIPT

The registered Foundry GPT-5.6 Sol pilot now has a session-owned Codex transport
receipt and a result-acceptance gate. It observes the pinned app-server route,
not Foundry HTTP or served-model identity. No live pilot ran, and
`live_inference_identity_and_wire_unverified` remains unresolved.

### Scope and evidence boundary

The pinned `openai-codex==0.147.0` SDK exposes serialized JSON-RPC requests on
stdio, correlated app-server replies and native thread-usage notifications.
The narrow hook hashes the exact UTF-8 string handed to stdin, including its
newline, only after a complete write and successful flush. It does not hash a
second serialization or retain prompt/output text. Returned thread settings
are recorded as app-server settings, not as served identity.

Each receipt binds the exact registered run, ordered task, actual infrastructure
attempt, verified prepared capture and upstream bundle digests to the requested
provider/profile/deployment/model/effort/context. Native token fields preserve
observed values, absent fields and nulls without filling SDK defaults or
inventing prices. Foundry HTTP payload, provider request ID, served
model/version/deployment, complete model-call count and pricing remain explicitly
`not_available` because this route does not expose them to Python.

Step 2 creates the session after the real capture gate and passes the actual
attempt index to the runner. The runner checks the prepared request and route
before workspace/auth/client startup. Completion and file acceptance require
the session's own observation plus current receipt/capture/upstream bytes.
Saved or rehashed synthetic documents cannot recreate this in-process witness.
The existing no-clobber writer and held-parent checks publish a reservation,
per-attempt files and the ready marker last. Failed partials are neither adopted
nor deleted. Legacy absent/null execution keeps its existing branch and output
shape; retry declarations are unchanged.

The runtime privately binds the endpoint account to the digest-verified account
resource leaf. Receipts and refusal messages publish no endpoint, account,
project/resource ID, auth material, prompt/output, private host path or exception
string. Refusal uses `pilot_wire_receipt_refused`.

The boundary is
`codex_app_server_transport_not_foundry_http_or_served_identity`. SHA256 checks
establish local consistency, not remote fact authenticity. No disk-only receipt
consumption option or launch command was added to preflight. `launch_enabled`,
`launch_allowed`, `full_220_enabled` and `full_220_allowed` remain false. The
model, Max effort, 1M request, fixed five-task cohort and grading behavior are
unchanged.

### Exact validation evidence

Exactly one pytest invocation ran from the new worktree's `batch-runner`
directory against implementation `59aa7f00de5505e0ed5c1bff8e8ae7757ff9398a`:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q tests/test_gpt56_pilot_wire_receipt.py --tb=short
```

Result: `88 passed in 642.32s (0:10:42)`, exit 0, 88 collected. The selector uses
synthetic transport events with real capture and upstream bundle validators.
It covers exact serialization, usage preservation, correlation, missing/forged/
duplicate receipts, request and upstream drift, task/run/attempt/retry mismatch,
route settings, unavailable served fields, no-clobber/path/link/partial cases,
mid-publication drift, privacy, legacy no-op behavior, false launch flags and
result acceptance before file saving. Offline guards forbid network, auth,
provider/model/client/grader construction and subprocess execution.

Both reviewers then found the account-binding defect described below. Its
correction adds one wrong-account/same-deployment parameter, bringing the
selector to 89 cases. That corrected selector was not rerun locally. The
88-case result is not test evidence for the corrected HEAD; automatic CI is
still required. The measured duration is local test time, not inference or
billing evidence, and full Backend timing remains unmeasured.

`git diff --check` and `git diff --cached --check` passed. No full suite,
`comparison-contracts`, earlier pilot selector or manual workflow was run.

### Immutable review boundary

The new clean branch `b/gpt56-live-wire-receipt-20260920` starts at fetched main
`0cd4c5e76805384a77afabf28b3663a3ad6596c0`. Initial implementation
`59aa7f00de5505e0ed5c1bff8e8ae7757ff9398a` received REQUEST-CHANGES from both
`llm-systems-engineer` and `first-reviewer`: checking only the direct route and
deployment leaf allowed a different account with the same deployment name.

The correction rereads deployment-ready bytes against the capture digest,
verifies current single-link account-resource bytes against the sealed size and
SHA256, and compares the endpoint account with that resource leaf before
workspace/auth/client startup. Positive fixture endpoints now match their
evidence. The added regression checks refusal before runtime, no receipt
creation and no disclosure.

Reviewed implementation HEAD: `89e9a33baa3b6c4b3c404f7c2c6f61798003a868`.
Both reviewers returned APPROVE with no remaining blocking findings and checked
the source pins against this fixed HEAD. Their verdicts are read-only static
reviews, not test or launch approval. Neither reviewer ran tests, runtime code
or network calls. This record and the changelog are a later records-only commit
outside the implementation review boundary.

### Changed files

- `batch-runner/gpt56_pilot_wire_receipt.py`
- `batch-runner/core/codex_runner.py`
- `batch-runner/core/executor.py`
- `batch-runner/step2_run_inference.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/tests/test_gpt56_pilot_wire_receipt.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_gpt56_foundry_evidence_intake.py`
- `batch-runner/tests/test_gpt56_pilot_identity_plan.py`
- `batch-runner/tests/test_gpt56_pilot_config_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_input_bundle.py`
- `batch-runner/tests/test_gpt56_pilot_deployment_binding.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The new recorder expands the active pilot source closure from 51 to 52 files.
The six existing test files change only their exact source-count expectations.
Both active plans refresh changed source pins and grader closure metadata
because the latter includes core Python sources. No grader production, rubric,
prompt, workflow, `core/qa.py` or HF upload code changes.

### Skills, ownership and remaining work

The complete skill catalog was inspected once. `experiment-design` was applied
before planning to separate requested settings, local transport observations
and unobserved served identity without changing experiment axes.
`llm-systems-engineer` contributed the runtime hook and reviewed the immutable
implementation; `first-reviewer` independently reviewed it. `im-not-ai-en` was
applied to the English completion records and PR text while preserving commands,
hashes, results and caveats.

UI/animation skills do not apply because the interface is unchanged. Grading skills
do not apply because grader behavior is unchanged; closure metadata alone does
not introduce a grading task. `repo-readiness` does not apply because this is
not a repository publication/readiness audit. `extreme-reasoner` does not apply
because workflows, `core/qa.py` and HF upload code are untouched.

No Azure or HF API/CLI query, credential/OIDC lookup, provider/model/client/grader
execution, inference, grading, download, paid execution or manual workflow
dispatch occurred. The preserved checkout and the prior task's worktree were
not used or edited. Existing Git author/committer identity
`hyeonsangjeon <wingnut0310@gmail.com>` was preserved without configuration
changes, attribution trailers, history rewriting, force push or hook bypass.
Project and merge decisions remain with the leader.

Remaining work includes corrected-HEAD automatic CI, separately reviewed real
Foundry evidence acquisition, actual HTTP/input-consumption/wire and served
identity observation, native sandbox/result-bundle hosting, actual deployment
and execution, native-cap enforcement, and usage/tariff/billing receipts. The
current pilot's live identity/wire blocker remains present. Synthetic fixtures
prove verifier behavior only; they are not evidence that the pilot was served.
