# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: Codex Requested Max and Long Context Wiring

### Scope and Outcome

Explicit Codex reasoning and context-window requests now reach generated
configuration through the existing preparation, provider, and runtime/thread
path. `CodexProviderSettings` has two optional typed fields,
`reasoning_effort` and `model_context_window`, both defaulting to `None`.
The existing `config_overrides` path supplies the configured client used by
`start_thread`; no new provider, authentication path, or execution framework
was added.

The Sol preregistration requests:

```toml
model_reasoning_effort="max"
model_context_window=1000000
```

The GPT-5.4 comparison requests `model_reasoning_effort="xhigh"` and no
context-window override. Both offline checkers use the adapter's serializer
to expose these exact requests. Invalid plans produce no override evidence.
These are client requests, not proof that the pinned CLI or provider accepts
them or that a model served Max, xhigh, or the Long 1M tier. A context window
is not a native-call or aggregate-token cap.

Work started from immutable main
`a5ed62bd55471c0fd8bdd637c9312315a17ebf4b` in branch
`b/codex-max-long-wiring-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-codex-max-long-wiring-20260919`.
The preservation checkout and prior worktrees were not changed.

Exactly 16 files differ from that base:

- `batch-runner/core/codex_runtime_config.py`
- `batch-runner/core/experiment_config.py`
- `batch-runner/core/executor.py`
- `batch-runner/step1_prepare_tasks.py`
- `batch-runner/step2_run_inference.py`
- `batch-runner/tests/test_codex_requested_model_controls.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Compatibility and Preregistration Boundaries

Omitted and explicit-null controls emit no new overrides. The new fields are
appended to preserve positional compatibility. Existing provider and sorted
query overrides retain their bytes and order. The generic
`condition_a.model.reasoning_effort` is not used as a fallback, so existing
Foundry experiment files do not acquire a new request.

Effort must be exactly one of `none`, `minimal`, `low`, `medium`, `high`,
`xhigh`, or `max`. Context must be an integer from 1 through `2**63 - 1`.
Wrong types, spelling/case/whitespace changes, booleans, numeric strings,
floats, NaN, infinity, zero, negative values, and overflow are rejected
without casts or fallback. Preparation retains explicit values unchanged;
literal and deferred configuration validation, direct executor construction,
and inference all use the same validation boundary.

The GPT-5.4 plan pins 15 source files, and the Sol plan pins 16, including its
shared plan reader. Both sets now cover the preparation and inference paths.
The source boundary advances to this task's immutable base, while grader
provenance stays at `96b181e1128039891f2cbbd9c26af9701e7e8e22` for GPT-5.4
and `6ccd4ae346d302e3da0af455a3c5a72ec79a6984` for Sol.
Task IDs/order, canonical content and input/reference fingerprints, repeats,
limits, grading configuration, result schemas, record-only costs, and
null/partial receipts are unchanged. Historical ledgers and sealed evidence
are untouched.

### Verification

The following targeted command ran exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_codex_requested_model_controls.py::test_codex_requested_model_controls batch-runner/tests/test_gpt54_comparison_preflight.py::test_gpt54_comparison_is_fixed_and_fails_closed batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py::test_gpt56_sol_copilot_pilot_is_pinned_and_fails_closed
```

Result: `105 passed in 22.13s`.

The adapter selector compares literal pre-change golden bytes with and without
query parameters, checks exact explicit overrides and invalid values, and
exercises preparation, both configuration-validation paths, direct executor
construction, and the real inference constructor expression. A fake SDK checks
the existing `open_runtime` to `start_thread` path without starting a real
process, authentication command, or model. The two preregistration selectors
check exact requests, required source pins and digests, and the remaining
fail-closed boundaries. Both retain `launch_allowed: false` and CLI exit 2;
the Sol pilot also retains `full_220_allowed: false`.

```bash
git diff --cached --check a5ed62bd55471c0fd8bdd637c9312315a17ebf4b
```

The diff check passed. Production code, plans, and tests were unchanged after
the targeted run. No broad suite or separate preflight ran. No provider
credentials or Copilot authentication were added. No live capability probe,
model/grader/VM execution, Azure API/CLI operation, paid workflow, dispatch,
Project edit, or benchmark launch was performed.

### Remaining Blockers and Review Boundary

Both plans remain launch-blocked. The Sol pilot still lacks the GitHub Copilot
route and verified Max/Long capability. The comparison still lacks verified
Codex xhigh capability and Sandbox V2 effort forwarding. Both need live
model/input verification, native call/token caps, dispatch with the pinned
grading identity, and usage/tariff evidence. Missing prices remain recorded
as unknown/partial under the existing record-only policy; this change does
not add a pricing-based spending prohibition.

There is still no compliant post-merge paid command for either plan. The
remaining wiring requires a separate reviewed change, refreshed source pins,
and capability/identity evidence before the approved five-task pilot or
four-run comparison. The pilot cannot advance automatically to 220 tasks.

The immutable starting boundary is
`a5ed62bd55471c0fd8bdd637c9312315a17ebf4b`. A bounded backend review checked
the forwarding and preregistration changes. That is not leader approval of
the new committed HEAD. Fresh immutable-HEAD review and automatic CI evidence
are pending; this record claims no approval, CI success, or merge result.

### Skills and Agent Use

The full available skill and repository-agent catalogs were inspected once
before editing. The matching `llm-systems-engineer` role was applied to the
adapter implementation and a bounded preregistration review. Its broader
testing guidance was limited by the owner's explicit targeted-test scope.
`openai-docs` supplied the official Codex configuration key/type references,
not evidence of Copilot access or served capability. `experiment-design` was
applied before configuration changes to preserve the existing study designs
and distinguish requested settings from verified controls. `im-not-ai-en`
was applied to the English specification, completion record, and PR wording;
protected literals and uncertainty were checked manually without an extra
verification-script run under the bounded validation scope.

Experiment-report skills do not apply because this task reports no experiment
results. Repository-readiness, UI, and animation skills do not apply. No
grading pipeline, workflow, `core/qa.py`, or HF upload code changed, so no
grading-engineer delegation or extreme-reasoner decision was required.

## Prior Result: #615 Sol Pilot Source-Pin Review Correction

[#615](https://github.com/hyeonsangjeon/gdpval-realworks/pull/615) added the
shared `gpt54_comparison_preflight.py` plan reader to the Sol pilot's required
source set and YAML digest pins. The corrected implementation HEAD was
`50821cdca20999ccf958f00720ead52ca24b5d93`. Its historical single-selector
result was `40 passed in 10.09s`, with launch still blocked. That result is
prior evidence, not the result of this task's updated selectors.
