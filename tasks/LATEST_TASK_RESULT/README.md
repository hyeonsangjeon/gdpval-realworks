# Latest task result

## Five-task native-cap proposal, local only (2026-10-24)

Scope: draft retry-inclusive native call, turn, token and wall-clock caps from
existing evidence, and compare deployment-name references without Azure access.
Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`;
branch: `codex/gpt56-native-pilot-caps-20261024`; inspected base:
`2bc77ad14cf7205694d11aa5909a9ea67cbb2891`.
This is not independent source-review approval. No new reviewed execution
head is established; final-source review remains required.

### Outcome and derivation

The inert proposal is
`batch-runner/experiments/execution_envelope/gpt56_sol_native_caps_draft_20261024.yaml`.
No runtime consumes it. Sealed plans, source pins, production code, workflows,
credentials, grader identity and execution rights are unchanged.

| Scope | Native requests | Logical turns | Input tokens | Output tokens | Wall seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Attempt | 32 | 1 | 300,000 | 10,000 | 1,800 |
| Task, all four attempts | 128 | 4 | 1,200,000 | 40,000 | 7,620 |
| Pilot, all five tasks | 640 | 20 | 6,000,000 | 200,000 | 38,100 |

Sources and explicit policy choices:

- `tests/fixtures/run_record/step2_inference_results.json` and
  `cost_ledger_condition_a.jsonl` under `batch-runner/` preserve
  `exp033_codex_foundry_fixed5:34528903950:1`: five tasks, nine ledger turns,
  595,243 input / 22,253 output tokens. Maximum per-task input/output is
  289,404 / 8,381 on task `2ea2e5b5`; rounding upward to the next 100,000 /
  10,000 gives the proposed attempt token caps. These partial GPT-5.4
  observations are not a Sol usage forecast. Cached input and reasoning
  output are subcounts, not additional tokens.
- The leader reports diagnostic `39407062120` at 9,444 input / 5 output.
  Its archive was not found in the local repository/worktree artifact search;
  these quantities are attributed to the instruction, not independently
  verified. `ceil(300000 / 9444) = 32` is only a provisional native-call
  planning heuristic. Request sizes vary; token budgets do not enforce a
  request count. The historical ledger explicitly counts turns, not the
  native model requests inside them. Native measurement/enforcement remains
  unresolved; the proposal does not claim otherwise.
- The registered source profile fixes one turn and 1,800 seconds per
  attempt, with three infrastructure retries: four attempts per task.
  `step2_run_inference.py::INFRA_RETRY_BACKOFF_SECONDS` is 60/120/240.
  Task time is `4 * 1800 + 420 = 7620`; pilot totals multiply by five.
  This is a proposed serial inference/retry deadline, excluding preparation,
  upload and grading, not an existing enforced whole-pilot timeout.
- `approved_maximum_usd: null # owner decision`; no USD amount was selected.

### Deployment comparison

Both Foundry plan YAMLs and the preflight request `identity.model:
gpt-5.6-sol`; the judge label also matches. Their actual
`foundry_identity.deployment` is null, as is the generated runtime template
in `gpt56_pilot_config_bundle.py::_runtime`.
The referenced `exp035_codex_foundry_full220.yaml` instead has
`condition_a.model.deployment` and `execution.codex.model` set to `gpt-5.4`.
That historical baseline must not be dispatched unchanged as the Sol pilot.

`codex-foundry-connection-diagnostic.yml` requires a deployment string with no
default and forwards `inputs.deployment` through `DEPLOYMENT` to
`--deployment`; it does not hard-code `gpt-5.6-sol`.
`batch-run.yml` reads deployment from the selected experiment's
`condition_a.model.deployment`. Neither file proves the historical dispatch
input. Without the archived diagnostic input/result, exact deployment-name
agreement is **unverified**, not a confirmed match or a confirmed live mismatch.
No Azure, identity-platform, GitHub API or workflow operation was used.

### Verification

Python 3.10.12 / pytest 9.1.1. Final focused invocations used an empty inherited
environment, explicit PATH and installed user-package PYTHONPATH, offline
Hub/dataset settings, disabled plugin autoload and no pytest cache:

```text
python3 -m pytest -m "not integration" -o addopts= -p no:cacheprovider --tb=short -q
  tests/test_gpt56_pilot_caps_draft.py tests/test_gpt56_pilot_deployment_binding.py
```

**165 passed, 0 failed (114.95s)** in the proposal worktree.
The unchanged `tests/test_sol_source_registration.py` additionally passed
**1 passed, 0 failed (14.67s)** at the inspected base in a temporary clean
source-check worktree. That test requires an entirely clean Git status.
The earlier combined invocation had **165 passed, 1 failed (117.67s)**:
the real source-registration guard correctly rejected the untracked proposal
files. It was not skipped, mocked or weakened; the clean-base rerun passed.
An initial empty-environment attempt could not import user-installed pytest;
explicit PYTHONPATH resolved that without installing any dependencies.
An earlier narrow selection separately passed seven tests; counts are not
cumulative unique-test totals.

After the proposal was committed and the worktree was clean, the combined
selection above plus `tests/test_sol_source_registration.py` passed
**166 passed, 0 failed (117.81s)** at
`73d2a71f31ad78fdf90fa9a5e433412a019ed45b`.
The real source-profile preflight therefore also passes at the proposal head,
while preserving launch refusal and the frozen-grader blocker. This tested
head is not an independently reviewed execution head. The subsequent
completion-record update changes only this README and the changelog.

### Remaining work and boundary

Owner approval of these provisional noncurrency caps and a USD cap; archived
connection deployment comparison and externally reviewed account/deployment,
served-model/version and Max/Long evidence; native request counting plus
per-task/per-pilot hard enforcement including partial/uncertain usage;
frozen-grader binding, prepared-input and live wire/host/usage evidence; and
independent review of the fixed final execution source remain required.
No model call, grading, dispatch, push, merge, approval or secret read occurred.
All completion facts stop before any delivery/merge outcome.
