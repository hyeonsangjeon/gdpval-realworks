# Latest substantive task result

## PROJECT5-PR637-CORE-PYTEST-FIX

The four reported Backend pytest failures in PR #637 now pass in one targeted
local run: `4 passed in 5.39s`, exit 0. The correction restores the legacy
manifest guards' original failure paths and adds the existing prepared-request
capture blocker to an exact test expectation. The registered Foundry pilot still
requires capture inputs before Step 1 proceeds.

### CI failure and correction scope

The leader reported four failures at
`155279f6458ea3341f2c894a1177aaa698bc053d` in Backend pytest run `35506466839`,
job `106067021054`. At that HEAD, `comparison-contracts`, `validate`,
`advance-check` and `freeze-check` succeeded. This correction does not claim
that the new HEAD has passed automatic CI.

`test_real_validators_exact_pilot_scope_and_ready_last[True]` omitted
`prepared_request_capture_unverified` from its exact remaining-blocker list.
The production transition was correct. Only that expected list changes; the
test still compares the complete ordered list, uses the real bundle validators
and checks both false launch flags.

Three Step 1 manifest tests used an existing `SimpleNamespace` config without
`execution`. Directly reading `config.execution.pilot_input_capture` raised
`AttributeError` before the intended missing, legacy-schema and byte-drift
manifest checks. `_prepare_tasks` now obtains `execution` and the optional pilot
control with `getattr(..., None)`. The independent registered run-ID refusal
remains in place, and an explicit non-null pilot control still requires capture
sources. No execution field was injected into a test double. The manifest tests,
their fixtures and their refusal assertions are unchanged.

The two active GPT-5.4/GPT-5.6 source-pin maps also refresh only the Step 1 hash
to `c487fd25710155e5bbf07461dd0c3c2d806babe1a64e8ca7cd7931c50461c742`.
This is required metadata for the changed source bytes, not an experiment or
capture behavior change. Leaving those pins stale would make the real source
verifiers reject the corrected implementation. Source counts, grader closure
metadata, historical registrations and evidence bytes are unchanged.

No other production code, capture helper, Step 2 gate, preflight transition,
workflow, timeout, model setting, task cohort or grader behavior changed.

### Exact correction selector

Exactly one pytest invocation ran, selecting only the four reported failures:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short 'batch-runner/tests/test_gpt56_pilot_config_bundle.py::test_real_validators_exact_pilot_scope_and_ready_last[True]' batch-runner/tests/test_manifest_pipeline_guard.py::test_step1_missing_manifest_fails_before_prepared_write batch-runner/tests/test_manifest_pipeline_guard.py::test_step1_legacy_manifest_fails_before_prepared_write batch-runner/tests/test_manifest_pipeline_guard.py::test_step1_manifest_byte_drift_fails_before_prepared_write
```

Result: `4 passed in 5.39s`, exit 0, four cases collected. The positive bundle
case retains real evidence, identity, config and static step8 validation under
the existing offline guards. The three manifest cases retain their original
expected exceptions and no-prepared-file assertions.

The full `comparison-contracts` selector and the 124-case capture selector were
not rerun locally. No broad/full suite or manual workflow ran. `git diff --check`
and `git diff --cached --check` passed before the correction commit.

The initial capture selector remains historical evidence:
`2 failed, 122 passed in 284.01s (0:04:44)`, exit 1. Its test-only connection-confirmation correction
was not rerun locally. The leader subsequently reported automatic
`comparison-contracts` success at `155279f6458ea3341f2c894a1177aaa698bc053d`.
Neither that earlier CI result nor this four-case selector proves that the full
new-HEAD Backend suite is green.

### Immutable review boundary

Correction base: `155279f6458ea3341f2c894a1177aaa698bc053d`.
Reviewed correction HEAD: `a81985b1f9f74f246d265a273913a9c3ec4cb31e`.
Both `llm-systems-engineer` and `first-reviewer` returned APPROVE with no blocking
findings. They confirmed the legacy guard paths, independent registered-pilot
refusal, exact blocker expectation and both source pins through read-only static
review. Neither reviewer reran tests or executed runtime code.
The reviews cover the four-file correction against that base. This completion
record and the changelog are a subsequent documentation-only commit outside
the implementation review boundary.

The same development branch, `b/gpt56-pre-execution-capture-20260920`, is used.
Its original main base is `140cbf4eef59a2b3c6ee731ac3dd4c75d9e005d7`.
The preserved checkout `wip/local-main-preserved-20260719` was not used or edited.
The repository's existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was preserved without configuration
changes. No attribution trailer, history rewrite, force push, hook bypass or
forbidden Git cleanup was used.

### Files changed by this correction

- `batch-runner/step1_prepare_tasks.py`
- `batch-runner/tests/test_gpt56_pilot_config_bundle.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Preserved capture outcome and remaining work

The original implementation still binds real Step 1 prepared rows to the
runtime candidate and five verified upstream bundles, publishes prepared and
capture files without clobbering, and verifies current bytes before Step 2
provider/auth/client setup. Explicit preflight consumption still clears only
`prepared_request_capture_unverified`. Legacy absent/null behavior and the
registered pilot's required-capture boundary are preserved.

The evidence boundary remains
`prepared_request_intent_not_wire_or_served_identity`. Local prepared-input
consistency does not prove actual model consumption, wire bytes, live inference
identity, served capability or launch permission. `launch_allowed` and
`full_220_allowed` remain false, as do `launch_enabled` and `full_220_enabled`
in the active contract. Real external evidence acquisition/review, live
identity/input consumption/wire binding, native sandbox/result hosting, actual
deployment/execution, native-cap enforcement and usage/tariff receipts remain
unresolved. New-HEAD automatic CI remains a separate gate.

`experiment-design` kept the source-pin refresh separate from experimental
changes. This is an offline four-case regression check, not a model-performance
experiment. `llm-systems-engineer` and `first-reviewer` provide the immutable
reviews. `im-not-ai-en` was applied to the English records while preserving
results, commands, hashes and evidence limits. `extreme-reasoner` is not required
because no workflow, `core/qa.py` or HF upload code changes. Grader production and
UI/animation are outside this correction.

No Azure/HF/OIDC/provider/model/client/grader execution, credential lookup,
inference, grading, download, paid execution or manual workflow dispatch
occurred. Project and merge decisions remain with the leader. This record stops
at pre-merge facts and contains no carrying-PR merge SHA, time or state.
