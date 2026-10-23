# Latest task result

## PR #785 pilot-contracts refusal-message regression corrected locally

Scope: diagnose CI run `39932101762` at
`dcf97b68663084b12472b8a8fd8d81799c47e938` on
`codex/gpt56-direct-account-contract-20261022`. Work was confined to the
direct-account integration worktree. No push or remote mutation was performed.

Cause: the intentional source-profile change in
`d02d8e08beab85d5c443baaf60f8036c2d7308d3` passes the supplied plan's seal
into the active-plan selector. Altering the expected grader hash changes that
seal, so source registration refuses the plan before the former
`active_contract_mismatch` check. The public compiler translates that refusal
to `pilot_identity_compile_refused`. CI reported **1 failed, 916 passed**.

Only the stale test expectation was changed, from `active_contract_mismatch`
to `pilot_identity_compile_refused`. The same test still directly requires
`grader_template_source_drift` for the altered hash. Production code, the
frozen grader hash, source checks, launch restrictions and all other test
assertions are unchanged; no skip or xfail was added.

### Local verification

Python 3.10.12, pytest 9.1.1; commands below run from `batch-runner/`.

```bash
python3 -m pytest 'tests/test_gpt56_pilot_identity_plan.py::test_active_grader_template_source_foundry_identity[stale_expected_hash]' -q
# Before the fix: 1 failed in 5.71s; same regex mismatch as CI.
python3 -m pytest tests/test_gpt56_pilot_identity_plan.py -q
# After the fix: 118 passed in 21.93s.
python3 -m pytest -m "not integration" --tb=short -q -rs tests/test_gpt56_evidence_preflight_gate.py tests/test_gpt56_foundry_evidence_intake.py tests/test_gpt56_pilot_config_bundle.py tests/test_gpt56_pilot_deployment_binding.py tests/test_gpt56_pilot_identity_plan.py tests/test_gpt56_pilot_input_bundle.py tests/test_gpt56_pilot_input_capture.py
# After the fix: 917 passed in 450.87s.
budget_contract_files=()
for budget_contract_file in tests/test_codex_budget_pilot*.py; do
  case "$budget_contract_file" in
    tests/test_codex_budget_pilot*readout*.py) ;;
    *) budget_contract_files+=("$budget_contract_file") ;;
  esac
done
(( ${#budget_contract_files[@]} > 0 ))
python3 -m pytest -m "not integration" --tb=short -q -rs "${budget_contract_files[@]}"
# After the fix: 1537 passed in 5294.29s.
```

The initial `python` command was unavailable; `python3` was used instead.
The first budget attempt was stopped after missing `openai_codex` setup errors;
a narrow diagnostic reported **1 error**. The repository-pinned
`openai-codex==0.147.0` and `openai-codex-cli-bin==0.147.0` dependencies were
installed into session-local storage, not the repository or shared Python
environment. A second budget attempt was stopped after inherited-token guard
failures; a narrow diagnostic reported **1 failed** with
`input_or_output_token_in_execution_environment`. For the completed budget
run, the four named Hub/GitHub token variables were unset in the test subprocess
without inspecting their values, and the session-local dependencies were made
available through `PYTHONPATH`. Interrupted attempts have no complete-suite
verdict and are not included in the passing counts.

### Evidence boundary and remaining work

The inspected CI head is `dcf97b68663084b12472b8a8fd8d81799c47e938`;
it is not final-source review approval. No new review was requested or claimed.
The tested code delta is one expected-message line; the two required completion
records were updated after validation. The local commit identity is
`hyeonsangjeon <wingnut0310@gmail.com>`, with no trailers.

No workflow was dispatched and no model, grader or credential acquisition was
invoked. Push approval remains absent. Final-source review/CI and the existing
frozen-grader binding and live-admission gates remain unresolved; these offline
tests do not authorize benchmark execution or change any spent/uncertain right.
