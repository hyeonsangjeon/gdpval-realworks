# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: Sandbox V2 Requested Reasoning Effort Wiring

### Scope and Outcome

Sandbox V2 now carries an explicit stage-plan `model.reasoning_effort` through
its existing voice construction path into `AzureFoundryVoice.next_turn`.
The new typed field defaults to `None` and is appended to preserve existing
constructor positions. A shared pure helper validates and serializes the
optional Responses fields; no new request framework was introduced.

The GPT-5.4 comparison declares `reasoning_effort: xhigh` in the V2 condition's
request block. With that value in the stage plan, the captured fake-client
request contains the following fields; its other fields remain unchanged:

```json
{"model":"gpt-5.4","reasoning":{"effort":"xhigh"}}
```

This is proof of a client request, not proof that the Foundry deployment served
the requested capability. The preflight still refuses launch, and no dispatch
connection from the comparison contract to a paid stage was added.

Work started from immutable main
`34b3327d8a9beda58754efbf88e6bbf6d643cc60` in branch
`b/v2-reasoning-effort-wiring-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-v2-reasoning-effort-wiring-20260919`.
The preservation checkout and prior worktrees were not changed.

Exactly 11 files differ from that base:

- `batch-runner/core/agentic_v2_model_voice.py`
- `batch-runner/scripts/run_agentic_v2_stage.py`
- `batch-runner/tests/test_agentic_v2_model_voice.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Compatibility and Preregistration Boundaries

Omission and explicit null add no `reasoning` key. Literal pre-change request
bytes, including key order and the real tool schema, match the captured default
request. Both existing replay modes are exercised. The historical V2 template,
request helpers, replay logic, tool definitions, and receipt behavior are
unchanged.

Effort must be exactly one of `none`, `low`, `medium`, `high`, or `xhigh`, as
documented for [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4).
The [Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
defines the nested `reasoning.effort` field. Its broader vocabulary does not
establish GPT-5.4 support for `minimal` or `max`; this adapter rejects both.
Case/whitespace changes, empty or unknown strings, numbers, booleans, lists,
and mappings are also rejected without casts or fallback. The real stage
`verdict_for` validates immediately after loading YAML, before other preflight
checks or client construction; direct voice construction validates too.

The comparison now pins 17 source files. The V2 stage entry point and its
existing `agentic_v2_stage_one_budget.py` plan reader are newly required and
digest-checked. Its immutable base advances to this task's starting commit;
grader provenance remains `96b181e1128039891f2cbbd9c26af9701e7e8e22`.
The Sol YAML changes only its existing shared-parser digest because it imports
the GPT-5.4 plan reader. Its contract and 16-file source set are unchanged.

The four five-task runs remain V2 r1, Codex r1, Codex r2, V2 r2. Task IDs/order,
canonical content and input/reference fingerprints, limits, grader configuration,
result schemas, record-only costs, and null/partial receipts are unchanged.
Historical ledgers and sealed evidence are untouched.

### Verification

The following targeted command ran exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_agentic_v2_model_voice.py::test_v2_requested_reasoning_effort batch-runner/tests/test_gpt54_comparison_preflight.py::test_gpt54_comparison_is_fixed_and_fails_closed
```

Result: `55 passed in 14.05s` (19 V2 request cases and 36 comparison cases).

The request selector uses the real YAML loader and stage validation, executes
the stage's original nested `voice_for` constructor extracted unchanged from
its AST, and captures the real voice's `next_turn` request with the existing
fake client. Unrelated cost/cohort checks are stand-ins. This does not execute
the paid driver, authenticate, build a real client, or start a VM. Invalid
values also exercise the real stage `main()` only through its immediate
validation refusal, before the free accounting checks; no request is made.

The comparison selector checks exact V2 and Codex request evidence, request
drift, required pins and digests, and the unchanged launch refusal. It also
checks the Sol YAML's refreshed parser digest without running the Sol selector.
Every comparison case retains `launch_allowed: false` and CLI exit 2. No
separate preflight command, Codex selector, Sol selector, or broad suite ran.

```bash
git diff --cached --check 34b3327d8a9beda58754efbf88e6bbf6d643cc60
```

The diff check passed. Production code, plans, and tests were unchanged after
the targeted run. No live capability probe, authentication, model/grader/VM
execution, Azure API/CLI operation, workflow dispatch, Project edit, or paid
experiment was performed.

### Remaining Blockers and Review Boundary

Only `v2_reasoning_effort_unwired` was replaced, with
`v2_reasoning_effort_capability_unverified`. The other five blockers remain:

- `codex_reasoning_effort_capability_unverified`
- `codex_native_model_call_and_token_limits_unenforced`
- `live_deployment_identity_and_input_bytes_not_verified`
- `comparison_dispatch_and_pinned_grading_not_wired`
- `comparison_usage_and_tariff_evidence_unverified`

There is still no compliant post-merge paid comparison command. Live
capability/identity and input evidence, native caps, dispatch/grading wiring,
and usage/tariff evidence require separate work and a refreshed immutable
review boundary. Missing prices remain unknown/partial under the record-only
policy, not a new pricing-based spending prohibition. The Sol pilot's launch
and 220-task gates are not changed by its parser-digest refresh.

The immutable starting boundary is
`34b3327d8a9beda58754efbf88e6bbf6d643cc60`. A bounded backend review found
no blocker in the forwarding and preregistration delta. That is not leader
approval of a new committed HEAD. Fresh immutable-HEAD review and automatic CI
evidence are pending; this record claims no approval, CI success, or merge result.

### Skills and Agent Use

The full available skill and repository-agent catalogs were inspected once
before editing. The matching `llm-systems-engineer` role covered implementation
and a bounded delta review. The owner's targeted-test limit took precedence
over its broad-suite guidance. `openai-docs` supplied the official GPT-5.4
vocabulary and Responses request shape before editing, not live Foundry
capability evidence. `experiment-design` preserved the comparison's existing
conditions and distinguished a request from verified control. `im-not-ai-en`
was applied to the English specification correction, completion record, and
PR wording. Protected literals and uncertainty were checked manually without
an extra fidelity-script run under the bounded validation scope.

Experiment-report skills do not apply because this task reports no experiment
results. Repository-readiness, UI, and animation skills do not apply. No
grading pipeline, workflow, `core/qa.py`, or HF upload code changed, so no
grading-engineer delegation or extreme-reasoner decision was required.

## Prior Result: #616 Codex Requested Reasoning and Context Controls

[#616](https://github.com/hyeonsangjeon/gdpval-realworks/pull/616) added optional
Codex reasoning and context-window forwarding while preserving default
configuration bytes and both launch refusals. The prior recorded implementation
HEAD was `b562fa922909d592fa90a05d7d7ec2236c0b1c32`, with
`105 passed in 22.13s`. That historical evidence is not this task's result;
the Codex and Sol selectors were not rerun here.
