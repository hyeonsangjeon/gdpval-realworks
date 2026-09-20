# Latest substantive task result

## PROJECT5-PR638-BACKEND-PARTITION-FIX

The existing Backend partition now moves the exact sorted union of 11 GPT-5.4
and 9 GPT-5.6 contract files out of core `pytest` and into `comparison-contracts`.
The prescribed static selector passed once. This corrects file selection; it
does not establish that either fresh CI job finishes within its unchanged
45-minute ceiling.

### CI finding and correction scope

The leader reported that Backend run `35514065313`, job `106086906143`, at
`c88f76f02c43ef9b2672e61d6cdd6d4630235305` was cancelled after `45:13` while
still progressing at `87%`, with no assertion failure. `comparison-contracts`
succeeded. That successful job selected only the 11 GPT-5.4 files; all 9 GPT-5.6
files, including the 89-case wire receipt selector, still ran in core discovery.
Neither job result establishes a complete passing Backend run for that HEAD.

Only the two literal workflow selections, their family comment and the existing
static partition test change. Core now ignores every member of the 20-file
union, and comparison selects the identical ordered list exactly once. The
test derives both filename families from disk, requires each family to be
represented, and retains exact-list equality, duplicate rejection, disjointness
and complete coverage of every discovered `test_*.py` file.

Both job/check names, the two-job topology, runner, setup, pinned actions,
dependencies, pip cache, dispatch/checkout SHA checks, integration filter,
repo-root script tests, triggers, permissions, concurrency and 45-minute limits
are unchanged. No job dependency, matrix, secret, credential or OIDC access was
added. No test deletion, skip or xfail was introduced. The cancelled run was
not rerun and no timeout was increased.

### Exact comparison partition

These are the sorted paths relative to `batch-runner`, excluded only from core
and selected by the comparison job:

```text
tests/test_gpt54_codex_grading_input.py
tests/test_gpt54_codex_input_capture.py
tests/test_gpt54_comparison_preflight.py
tests/test_gpt54_disposable_checkout.py
tests/test_gpt54_prepared_input_attestation.py
tests/test_gpt54_run_config_bundle.py
tests/test_gpt54_run_input_bundle.py
tests/test_gpt54_runtime_checkout.py
tests/test_gpt54_v2_grading_input.py
tests/test_gpt54_v2_input_capture.py
tests/test_gpt54_workflow_gate.py
tests/test_gpt56_evidence_preflight_gate.py
tests/test_gpt56_foundry_evidence_intake.py
tests/test_gpt56_pilot_config_bundle.py
tests/test_gpt56_pilot_deployment_binding.py
tests/test_gpt56_pilot_identity_plan.py
tests/test_gpt56_pilot_input_bundle.py
tests/test_gpt56_pilot_input_capture.py
tests/test_gpt56_pilot_wire_receipt.py
tests/test_gpt56_sol_codex_pilot_preflight.py
```

### Exact validation evidence

Exactly one pytest invocation ran for this correction, from the existing PR
worktree root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts
```

Result: `1 passed in 0.18s`, exit 0, one collected. This is static workflow and
filesystem partition evidence, not execution of the 20 contract files or a
measurement of full-suite duration. `git diff --check` and
`git diff --cached --check` passed. No core pytest suite, comparison-contracts
suite, wire receipt selector, earlier pilot selector, broad suite or manual
workflow was run locally.

The prior receipt evidence is preserved as historical evidence only. Its single
local command, run from `batch-runner`, was:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q tests/test_gpt56_pilot_wire_receipt.py --tb=short
```

That command reported `88 passed in 642.32s (0:10:42)`, exit 0, at
`59aa7f00de5505e0ed5c1bff8e8ae7757ff9398a`. Both reviewers subsequently found
the endpoint-account binding defect. The corrected receipt implementation
`89e9a33baa3b6c4b3c404f7c2c6f61798003a868` added a wrong-account parameter,
bringing its selector to 89 cases. That corrected selector has not been rerun
locally. The 88-pass result does not validate the correction, and the cancelled
core run is not a completed pass. Fresh automatic CI is still required.

### Mandatory pre-edit decision

`extreme-reasoner` was invoked before editing and returned
APPROVE-WITH-CONDITIONS against
`c88f76f02c43ef9b2672e61d6cdd6d4630235305`. Its structured memo identified
omission/duplication, moving the timeout problem to the comparison job, and
weakening untrusted-PR controls as the main risks. It required the exact
filesystem-derived union with both families present and preservation of all
existing setup, security, timeout and topology controls.

The memo kept the nominal aggregate allowance at two 45-minute jobs,
approximately 90 runner-minutes excluding shutdown overhead. Actual duration,
collection effects and CI headroom remain unmeasured. No extra job or paid API
operation was authorized. Ref-scoped cancellation and independent job verdicts
remain unchanged. If separately authorized, a normal forward patch can restore
both command lists and their guard together; that would restore the known core
imbalance, not fix its timeout. This was a design decision, not CI or launch
approval.

### Immutable review boundary

Correction base: `c88f76f02c43ef9b2672e61d6cdd6d4630235305`.
Fixed implementation HEAD: `70334bb35f7916a4db7a1e1d1a18da10847cb9e1`.
Both `llm-systems-engineer` and `first-reviewer` returned APPROVE with no
blocking findings on this exact HEAD. Both reviews were read-only; neither
reviewer ran tests, network calls or runtime code. The reviews confirmed the
mandatory decision memo's partition and preservation conditions.
These reviews cover only the two-file partition correction. This record and
the changelog are a later records-only commit outside that implementation
review boundary. The prior receipt implementation's two APPROVE verdicts at
`89e9a33baa3b6c4b3c404f7c2c6f61798003a868` remain separate static evidence.

The existing branch and worktree are retained:
`b/gpt56-live-wire-receipt-20260920`, originally based on main
`0cd4c5e76805384a77afabf28b3663a3ad6596c0`. No new checkout or branch was created
for this correction.

### Changed files

- `.github/workflows/backend-tests.yml`
- `batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

Runtime receipt logic, experiment settings, source pins, launch flags and
grading behavior are untouched. No other workflow, `core/qa.py` or HF upload
code changes.

### Unchanged live-wire limits and remaining work

The receipt still observes the pinned Codex app-server's actual serialized
stdio requests, correlated replies and native thread usage. It does not
observe Foundry HTTP payloads or returned served-model identity. Unavailable
fields remain `not_available`, and
`live_inference_identity_and_wire_unverified` stays unresolved. The boundary
remains `codex_app_server_transport_not_foundry_http_or_served_identity`.
Synthetic fixtures prove verifier behavior only, not that the pilot was served.
`launch_enabled`, `launch_allowed`, `full_220_enabled` and `full_220_allowed`
remain false; no launch command was added.

Fresh results and duration evidence for both Backend jobs remain required.
Real Foundry evidence acquisition/approval, actual HTTP/input-consumption/wire
and served identity, native sandbox/result-bundle hosting, deployment/execution,
native-cap enforcement and usage/tariff/billing receipts remain separate work.

No Azure/HF/OIDC lookup, provider/model/client/grader execution, inference,
grading, download, paid execution or manual workflow dispatch occurred. The
preserved checkout and other worktrees were not edited. Git author/committer
identity
`hyeonsangjeon <wingnut0310@gmail.com>` was preserved without configuration
changes, attribution trailers, history rewriting, force push or hook bypass.
Project and merge decisions remain with the leader. This record stops at
pre-merge facts.
